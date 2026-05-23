"""Small deterministic metrics for benchmark scaffolding."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Sequence


def exact_match(prediction: str, reference: str) -> float:
    """Return 1.0 when normalized strings match exactly, otherwise 0.0."""
    return 1.0 if _normalize_text(prediction) == _normalize_text(reference) else 0.0


def fuzzy_token_f1(prediction: str, reference: str) -> float:
    """Compute token-overlap F1 between two short text artifacts."""
    prediction_tokens = _tokenize(prediction)
    reference_tokens = _tokenize(reference)
    if not prediction_tokens or not reference_tokens:
        return 0.0

    prediction_counts = Counter(prediction_tokens)
    reference_counts = Counter(reference_tokens)
    overlap = sum((prediction_counts & reference_counts).values())
    if overlap == 0:
        return 0.0

    precision = overlap / len(prediction_tokens)
    recall = overlap / len(reference_tokens)
    return 2 * precision * recall / (precision + recall)


def shacl_conformance_rate(conformance_results: Iterable[bool]) -> float:
    """Return the share of SHACL validation results that conform."""
    results = list(conformance_results)
    if not results:
        return 0.0
    return sum(1 for result in results if result) / len(results)


def repair_success_rate(successes: int, attempts: int) -> float:
    """Return the share of repair attempts that succeeded."""
    if attempts <= 0:
        return 0.0
    return successes / attempts


def prompt_stability_score(outputs: Sequence[str]) -> float:
    """Return the share of outputs matching the first observed output exactly."""
    if not outputs:
        return 0.0
    canonical = outputs[0]
    return sum(1 for output in outputs if output == canonical) / len(outputs)


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", text.lower())
