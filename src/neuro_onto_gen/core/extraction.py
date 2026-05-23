"""Extraction adapter interfaces and JSON normalization helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from neuro_onto_gen.core.models import ABoxPayload

T = TypeVar("T", bound=BaseModel)
RawExtraction = str | bytes | bytearray | Mapping[str, Any]


@runtime_checkable
class ExtractorProtocol(Protocol):
    """Protocol for components that turn raw text into a validated ABox payload."""

    def extract(self, raw_text: str) -> ABoxPayload:
        """Extract a typed ABox payload from raw text."""
        ...


def parse_abox_payload(raw_output: RawExtraction) -> ABoxPayload:
    """Normalize raw extraction output into a validated ``ABoxPayload``.

    Args:
        raw_output: Either a JSON string/bytes object or a mapping produced by an
            extraction provider.

    Returns:
        A validated ABox payload.
    """
    return parse_model(raw_output, ABoxPayload)


def parse_model(raw_output: RawExtraction, output_model: type[T]) -> T:
    """Parse raw JSON-like extraction output into a Pydantic model."""
    if isinstance(raw_output, str | bytes | bytearray):
        return output_model.model_validate_json(raw_output)
    if isinstance(raw_output, Mapping):
        return output_model.model_validate(dict(raw_output))
    raise TypeError(
        "raw extraction output must be a JSON string, bytes, bytearray, or mapping; "
        f"got {type(raw_output).__name__}"
    )


@dataclass(frozen=True)
class JsonExtractionAdapter:
    """Deterministic adapter for tests, fixtures, and provider integration boundaries.

    This adapter does not call an LLM. It represents the normalized output that a
    provider-specific extractor is expected to return, then validates it with the
    same Pydantic path used by production adapters.
    """

    raw_output: RawExtraction

    def extract(self, raw_text: str) -> ABoxPayload:
        """Return the configured raw output as a validated ABox payload."""
        del raw_text
        return parse_abox_payload(self.raw_output)
