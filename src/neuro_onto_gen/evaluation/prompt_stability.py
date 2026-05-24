"""Cross-prompt RDF graph stability evaluation utilities."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import Graph

TripleSet = frozenset[tuple[str, str, str]]


@dataclass(frozen=True)
class PromptVariantOutput:
    """A single ontology output produced by one prompt variant."""

    prompt_id: str
    output_turtle: str


@dataclass(frozen=True)
class PromptVariantScore:
    """Per-prompt agreement diagnostics against the canonical prompt output."""

    prompt_id: str
    triple_count: int
    jaccard_to_canonical: float
    precision_to_canonical: float
    recall_to_canonical: float
    f1_to_canonical: float
    missing_from_canonical: list[tuple[str, str, str]] = field(default_factory=list)
    extra_vs_canonical: list[tuple[str, str, str]] = field(default_factory=list)
    missing_from_consensus: list[tuple[str, str, str]] = field(default_factory=list)
    parse_error: str | None = None


@dataclass(frozen=True)
class PromptStabilityReport:
    """Aggregate graph-level stability report for prompt variants."""

    variant_count: int
    valid_variant_count: int
    invalid_variants: list[str]
    canonical_prompt_id: str | None
    canonical_triple_count: int
    consensus_triple_count: int
    exact_graph_stability: float
    mean_jaccard_to_canonical: float
    mean_jaccard_to_consensus: float
    stable_triple_ratio: float
    unstable_triples: list[tuple[str, str, str]]
    prompt_scores: dict[str, PromptVariantScore]

    def to_json_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return {
            "variant_count": self.variant_count,
            "valid_variant_count": self.valid_variant_count,
            "invalid_variants": self.invalid_variants,
            "canonical_prompt_id": self.canonical_prompt_id,
            "canonical_triple_count": self.canonical_triple_count,
            "consensus_triple_count": self.consensus_triple_count,
            "exact_graph_stability": self.exact_graph_stability,
            "mean_jaccard_to_canonical": self.mean_jaccard_to_canonical,
            "mean_jaccard_to_consensus": self.mean_jaccard_to_consensus,
            "stable_triple_ratio": self.stable_triple_ratio,
            "unstable_triples": self.unstable_triples,
            "prompt_scores": {
                prompt_id: {
                    "triple_count": score.triple_count,
                    "jaccard_to_canonical": score.jaccard_to_canonical,
                    "precision_to_canonical": score.precision_to_canonical,
                    "recall_to_canonical": score.recall_to_canonical,
                    "f1_to_canonical": score.f1_to_canonical,
                    "missing_from_canonical": score.missing_from_canonical,
                    "extra_vs_canonical": score.extra_vs_canonical,
                    "missing_from_consensus": score.missing_from_consensus,
                    "parse_error": score.parse_error,
                }
                for prompt_id, score in self.prompt_scores.items()
            },
        }


def parse_turtle_triples(turtle: str) -> TripleSet:
    """Parse Turtle and return canonical triples independent of serialization order."""
    graph = Graph()
    graph.parse(data=turtle, format="turtle")
    triples = ((subject.n3(), predicate.n3(), object_.n3()) for subject, predicate, object_ in graph)
    return frozenset(sorted(triples))


def evaluate_prompt_stability(variants: Iterable[PromptVariantOutput]) -> PromptStabilityReport:
    """Evaluate graph-level robustness across prompt-variant Turtle outputs.

    The first parseable variant is treated as the canonical reference. The consensus graph is
    the intersection of all parseable variant graphs. This makes the metric deterministic and
    useful for smoke-scale regression tests before real LLM providers are wired in.
    """
    variants = list(variants)
    parsed: dict[str, TripleSet] = {}
    scores: dict[str, PromptVariantScore] = {}
    invalid_variants: list[str] = []

    for variant in variants:
        try:
            parsed[variant.prompt_id] = parse_turtle_triples(variant.output_turtle)
        except Exception as exc:  # rdflib raises parser-specific exceptions
            invalid_variants.append(variant.prompt_id)
            scores[variant.prompt_id] = PromptVariantScore(
                prompt_id=variant.prompt_id,
                triple_count=0,
                jaccard_to_canonical=0.0,
                precision_to_canonical=0.0,
                recall_to_canonical=0.0,
                f1_to_canonical=0.0,
                parse_error=str(exc),
            )

    if not parsed:
        return PromptStabilityReport(
            variant_count=len(variants),
            valid_variant_count=0,
            invalid_variants=invalid_variants,
            canonical_prompt_id=None,
            canonical_triple_count=0,
            consensus_triple_count=0,
            exact_graph_stability=0.0,
            mean_jaccard_to_canonical=0.0,
            mean_jaccard_to_consensus=0.0,
            stable_triple_ratio=0.0,
            unstable_triples=[],
            prompt_scores=scores,
        )

    canonical_prompt_id = next(prompt_id for prompt_id in (v.prompt_id for v in variants) if prompt_id in parsed)
    canonical = parsed[canonical_prompt_id]
    consensus = frozenset.intersection(*parsed.values())

    exact_matches = 0
    canonical_scores: list[float] = []
    consensus_scores: list[float] = []
    for prompt_id, triples in parsed.items():
        if triples == canonical:
            exact_matches += 1
        jaccard_to_canonical = _jaccard(triples, canonical)
        precision_to_canonical = _precision(triples, canonical)
        recall_to_canonical = _coverage(triples, canonical)
        canonical_scores.append(jaccard_to_canonical)
        consensus_scores.append(_coverage(triples, consensus))
        scores[prompt_id] = PromptVariantScore(
            prompt_id=prompt_id,
            triple_count=len(triples),
            jaccard_to_canonical=jaccard_to_canonical,
            precision_to_canonical=precision_to_canonical,
            recall_to_canonical=recall_to_canonical,
            f1_to_canonical=_f1(precision_to_canonical, recall_to_canonical),
            missing_from_canonical=sorted(canonical - triples),
            extra_vs_canonical=sorted(triples - canonical),
            missing_from_consensus=sorted(consensus - triples),
            parse_error=None,
        )

    unstable_triples = sorted(canonical - consensus)
    return PromptStabilityReport(
        variant_count=len(variants),
        valid_variant_count=len(parsed),
        invalid_variants=invalid_variants,
        canonical_prompt_id=canonical_prompt_id,
        canonical_triple_count=len(canonical),
        consensus_triple_count=len(consensus),
        exact_graph_stability=exact_matches / len(parsed),
        mean_jaccard_to_canonical=sum(canonical_scores) / len(canonical_scores),
        mean_jaccard_to_consensus=sum(consensus_scores) / len(consensus_scores),
        stable_triple_ratio=_coverage(consensus, canonical),
        unstable_triples=unstable_triples,
        prompt_scores=scores,
    )


def _from_jsonl(path: Path) -> PromptStabilityReport:
    variants: list[PromptVariantOutput] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        try:
            variants.append(
                PromptVariantOutput(
                    prompt_id=str(record["prompt_id"]),
                    output_turtle=str(record["output_turtle"]),
                )
            )
        except KeyError as exc:
            missing_key = exc.args[0]
            raise ValueError(f"{path}:{line_number} missing required key {missing_key!r}") from exc
    return evaluate_prompt_stability(variants)


def _jaccard(left: TripleSet, right: TripleSet) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def _coverage(candidate: TripleSet, reference: TripleSet) -> float:
    if not reference:
        return 1.0
    return len(candidate & reference) / len(reference)


def _precision(candidate: TripleSet, reference: TripleSet) -> float:
    if not candidate:
        return 1.0 if not reference else 0.0
    return len(candidate & reference) / len(candidate)


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# Keep the public API compact while exposing a convenient loader for tests/CLI callers.
evaluate_prompt_stability.from_jsonl = _from_jsonl  # type: ignore[attr-defined]
