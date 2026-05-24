"""Optional OWL reasoning adapter for ontology consistency checks.

The core MVP must not require Java, JPype, or owlready2. This module keeps those
imports lazy and reports a structured unavailable state when the optional OWL
stack is not installed.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OwlRepairDiagnostic:
    """Structured OWL inconsistency diagnostic that can feed the repair loop."""

    focus_node: str
    result_path: str
    source_constraint_component: str
    severity: str
    message: str
    diagnostic_type: str = "owl_inconsistency"


class OwlReasonerEngine(str, Enum):
    """Supported optional OWL reasoner engines."""

    PELLET = "pellet"
    HERMIT = "hermit"


@dataclass(frozen=True)
class OwlReasonerStatus:
    """Availability status for an optional OWL reasoner backend."""

    available: bool
    engine: OwlReasonerEngine
    reason: str | None = None
    install_hint: str = "pip install -e '.[owl]' and ensure Java is available on PATH"


@dataclass(frozen=True)
class OwlReasoningReport:
    """Result of running an OWL consistency check."""

    available: bool
    consistent: bool | None
    engine: OwlReasonerEngine
    message: str


class OwlReasonerUnavailable(RuntimeError):
    """Raised when the optional OWL reasoning stack is not available."""

    def __init__(self, status: OwlReasonerStatus) -> None:
        reason = status.reason or "OWL reasoner is unavailable"
        super().__init__(f"{reason}. Install with: {status.install_hint}")
        self.status = status


def check_owl_reasoner_available(
    engine: OwlReasonerEngine = OwlReasonerEngine.PELLET,
) -> OwlReasonerStatus:
    """Return whether the optional OWL reasoner backend can run in this environment."""
    try:
        _import_owlready2()
    except ModuleNotFoundError:
        return OwlReasonerStatus(
            available=False,
            engine=engine,
            reason="owlready2 is not installed",
        )

    if shutil.which("java") is None:
        return OwlReasonerStatus(
            available=False,
            engine=engine,
            reason="Java runtime is not available on PATH",
        )

    return OwlReasonerStatus(available=True, engine=engine)


def reason_owl_turtle(
    turtle: str,
    engine: OwlReasonerEngine = OwlReasonerEngine.PELLET,
) -> OwlReasoningReport:
    """Run an optional OWL consistency check over a Turtle ontology string.

    Args:
        turtle: RDF/Turtle ontology content to reason over.
        engine: Pellet or HermiT backend. Pellet is the default because owlready2
            can run it directly for consistency checks.

    Raises:
        OwlReasonerUnavailable: If owlready2 or Java is unavailable.
    """
    status = check_owl_reasoner_available(engine=engine)
    if not status.available:
        raise OwlReasonerUnavailable(status)

    owlready2 = _import_owlready2()
    with tempfile.TemporaryDirectory(prefix="neuro-onto-gen-owl-") as tmpdir:
        ontology_path = Path(tmpdir) / "ontology.ttl"
        ontology_path.write_text(turtle, encoding="utf-8")
        ontology = owlready2.get_ontology(ontology_path.as_uri()).load(format="turtle")

        try:
            with ontology:
                if engine is OwlReasonerEngine.HERMIT:
                    owlready2.sync_reasoner()
                else:
                    owlready2.sync_reasoner_pellet()
        except owlready2.base.OwlReadyInconsistentOntologyError as exc:
            return OwlReasoningReport(
                available=True,
                consistent=False,
                engine=engine,
                message=f"Ontology is inconsistent: {exc}",
            )

    return OwlReasoningReport(
        available=True,
        consistent=True,
        engine=engine,
        message="Ontology is consistent.",
    )


def build_owl_repair_diagnostic(turtle: str, report: OwlReasoningReport) -> OwlRepairDiagnostic:
    """Convert an inconsistent OWL reasoning report into a repair diagnostic.

    The diagnostic mirrors the SHACL violation fields consumed by the generic
    LLM repair prompt while explicitly marking the source as OWL consistency,
    not SHACL validation.
    """
    if report.consistent is not False:
        raise ValueError("OWL repair diagnostics require an inconsistent reasoning report")
    compact_turtle = " ".join(line.strip() for line in turtle.splitlines() if line.strip())
    message = report.message
    if compact_turtle:
        message = f"{message} | ontology_excerpt={compact_turtle[:500]}"
    return OwlRepairDiagnostic(
        focus_node="<ontology>",
        result_path="owl:consistency",
        source_constraint_component="OWLConsistencyConstraintComponent",
        severity="Violation",
        message=message,
    )


def _import_owlready2() -> Any:
    import owlready2  # type: ignore[import-not-found]

    return owlready2
