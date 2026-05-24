"""Cold-start schema discovery from candidate domain terms.

This module intentionally produces *draft* schema suggestions only.  Clustering can
surface candidate TBox classes, but the output must be reviewed by a human domain
expert before it is promoted into a production ontology.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

NumberVector = Sequence[float]
EmbeddingMap = Mapping[str, NumberVector]


@dataclass(frozen=True)
class ClusterMember:
    """A candidate term assigned to a discovered cluster."""

    term: str
    similarity_to_exemplar: float

    def to_json_dict(self) -> dict[str, object]:
        return {
            "term": self.term,
            "similarity_to_exemplar": round(self.similarity_to_exemplar, 6),
        }


@dataclass(frozen=True)
class DiscoveredCluster:
    """Human-reviewable cluster of candidate terms."""

    label: str
    exemplar: str
    members: tuple[ClusterMember, ...]
    requires_human_review: bool = True

    def to_json_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "exemplar": self.exemplar,
            "requires_human_review": self.requires_human_review,
            "members": [member.to_json_dict() for member in self.members],
        }


@dataclass(frozen=True)
class SchemaDiscoveryReport:
    """Result of clustering candidate terms into draft schema concepts."""

    clusters: tuple[DiscoveredCluster, ...]
    term_count: int
    backend: str
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def cluster_count(self) -> int:
        return len(self.clusters)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "term_count": self.term_count,
            "cluster_count": self.cluster_count,
            "backend": self.backend,
            "warnings": list(self.warnings),
            "clusters": [cluster.to_json_dict() for cluster in self.clusters],
        }

    def to_linkml_draft(self, schema_name: str = "discovered_schema") -> dict[str, object]:
        """Render a minimal LinkML-compatible draft from discovered clusters."""
        classes: dict[str, dict[str, object]] = {}
        for cluster in self.clusters:
            class_name = _to_pascal_case(cluster.label)
            member_terms = ", ".join(member.term for member in cluster.members)
            classes[class_name] = {
                "description": (
                    "Discovered from candidate terms; requires human ontology review. "
                    f"Terms: {member_terms}."
                ),
                "annotations": {
                    "cluster_exemplar": cluster.exemplar,
                    "requires_human_review": "true",
                    "source_terms": member_terms,
                },
            }

        return {
            "id": f"https://example.org/{_to_snake_case(schema_name)}",
            "name": schema_name,
            "prefixes": {schema_name: f"https://example.org/{_to_snake_case(schema_name)}/"},
            "default_prefix": schema_name,
            "annotations": {
                "generation_status": "schema_discovery_draft_requires_human_review",
                "discovery_backend": self.backend,
            },
            "classes": classes,
        }


_SIMPLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def extract_terms(texts: Iterable[str], *, min_frequency: int = 1) -> list[str]:
    """Extract lightweight candidate terms without requiring SpaCy.

    The optional production path can later swap in SpaCy noun chunks, but the base
    SDK keeps a deterministic regex fallback so cloning the repository does not
    require heavyweight model downloads.
    """
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    for text in texts:
        candidates = _candidate_phrases(text)
        for candidate in candidates:
            normalized = _normalize_term(candidate)
            if not normalized or normalized in _SIMPLE_STOPWORDS:
                continue
            counts[normalized.lower()] += 1
            display.setdefault(normalized.lower(), normalized)

    return [display[key] for key, count in counts.items() if count >= min_frequency]


def discover_schema_from_texts(
    texts: Iterable[str],
    *,
    embeddings: EmbeddingMap | None = None,
    min_frequency: int = 1,
    similarity_threshold: float = 0.78,
) -> SchemaDiscoveryReport:
    """Extract terms from text and cluster them into schema-discovery suggestions."""
    terms = extract_terms(texts, min_frequency=min_frequency)
    return discover_schema_from_terms(
        terms,
        embeddings=embeddings,
        similarity_threshold=similarity_threshold,
    )


def discover_schema_from_terms(
    terms: Iterable[str],
    *,
    embeddings: EmbeddingMap | None = None,
    similarity_threshold: float = 0.78,
) -> SchemaDiscoveryReport:
    """Cluster candidate terms and return a human-reviewable schema draft report.

    If explicit embeddings are supplied, they are used directly. Otherwise the
    function uses deterministic character n-gram vectors so the base package has
    no mandatory clustering/embedding dependency.  If scikit-learn is installed,
    callers can still install the optional ``clustering`` extra for future heavy
    integrations; this function keeps the smoke path deterministic and light.
    """
    unique_terms = _dedupe_terms(terms)
    if not unique_terms:
        return SchemaDiscoveryReport(
            clusters=(),
            term_count=0,
            backend="deterministic-similarity-fallback",
            warnings=("No candidate terms were provided.",),
        )

    vector_map = _vectors_for_terms(unique_terms, embeddings)
    labels = _cluster_by_similarity(unique_terms, vector_map, similarity_threshold)
    clusters = _build_clusters(unique_terms, labels, vector_map)
    return SchemaDiscoveryReport(
        clusters=tuple(clusters),
        term_count=len(unique_terms),
        backend="deterministic-similarity-fallback",
        warnings=(
            "Generated clusters are schema-discovery suggestions only and require human review.",
        ),
    )


def _candidate_phrases(text: str) -> list[str]:
    capitalized = re.findall(r"\b[A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*)*\b", text)
    tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{2,}\b", text)
    lower_ngrams: list[str] = []
    for size in (2, 3):
        for index in range(0, max(len(tokens) - size + 1, 0)):
            window = tokens[index : index + size]
            if any(token[0].isupper() for token in window):
                continue
            lower_ngrams.append(" ".join(window))
    return [*capitalized, *lower_ngrams, *tokens]


def _normalize_term(term: str) -> str:
    cleaned = re.sub(r"\s+", " ", term.strip(" .,:;()[]{}\n\t"))
    words = [word for word in cleaned.split(" ") if word.lower() not in _SIMPLE_STOPWORDS]
    if not words:
        return ""
    return " ".join(words)


def _dedupe_terms(terms: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        normalized = _normalize_term(term)
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            unique.append(normalized)
    return unique


def _vectors_for_terms(terms: Sequence[str], embeddings: EmbeddingMap | None) -> dict[str, tuple[float, ...]]:
    if embeddings is not None:
        missing = [term for term in terms if term not in embeddings]
        if missing:
            raise ValueError(f"Missing embeddings for terms: {', '.join(missing)}")
        return {term: tuple(float(value) for value in embeddings[term]) for term in terms}
    return {term: _char_ngram_vector(term) for term in terms}


def _cluster_by_similarity(
    terms: Sequence[str],
    vectors: Mapping[str, tuple[float, ...]],
    threshold: float,
) -> dict[str, int]:
    parent = {term: term for term in terms}

    def find(term: str) -> str:
        while parent[term] != term:
            parent[term] = parent[parent[term]]
            term = parent[term]
        return term

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for index, left in enumerate(terms):
        for right in terms[index + 1 :]:
            if _cosine(vectors[left], vectors[right]) >= threshold:
                union(left, right)

    root_to_label: dict[str, int] = {}
    labels: dict[str, int] = {}
    for term in terms:
        root = find(term)
        root_to_label.setdefault(root, len(root_to_label))
        labels[term] = root_to_label[root]
    return labels


def _build_clusters(
    terms: Sequence[str],
    labels: Mapping[str, int],
    vectors: Mapping[str, tuple[float, ...]],
) -> list[DiscoveredCluster]:
    grouped: dict[int, list[str]] = defaultdict(list)
    for term in terms:
        grouped[labels[term]].append(term)

    clusters: list[DiscoveredCluster] = []
    for label_id in sorted(grouped):
        cluster_terms = grouped[label_id]
        exemplar = _choose_exemplar(cluster_terms, vectors)
        members = tuple(
            ClusterMember(term=term, similarity_to_exemplar=_cosine(vectors[term], vectors[exemplar]))
            for term in sorted(cluster_terms, key=str.lower)
        )
        clusters.append(
            DiscoveredCluster(
                label=_to_pascal_case(exemplar),
                exemplar=exemplar,
                members=members,
            )
        )
    return sorted(clusters, key=lambda cluster: cluster.label)


def _choose_exemplar(terms: Sequence[str], vectors: Mapping[str, tuple[float, ...]]) -> str:
    def score(term: str) -> tuple[float, int, str]:
        similarities = [_cosine(vectors[term], vectors[other]) for other in terms]
        return (sum(similarities) / len(similarities), -len(term), term.lower())

    return max(terms, key=score)


def _char_ngram_vector(term: str) -> tuple[float, ...]:
    text = f"  {term.lower()}  "
    grams = Counter(text[index : index + 3] for index in range(max(len(text) - 2, 1)))
    ordered = sorted(grams)
    # Hash into a small deterministic vector to avoid a variable-size sparse dependency.
    buckets = [0.0] * 64
    for gram in ordered:
        buckets[sum(ord(ch) for ch in gram) % len(buckets)] += float(grams[gram])
    return tuple(buckets)


def _cosine(left: NumberVector, right: NumberVector) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding vectors must have the same dimensionality.")
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _to_pascal_case(value: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", value)
    return "".join(word[:1].upper() + word[1:] for word in words) or "DiscoveredClass"


def _to_snake_case(value: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", value.lower())
    return "_".join(words) or "discovered_schema"
