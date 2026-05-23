"""SHACL validation helpers for serialized ontology ABox graphs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyshacl import validate
from rdflib import RDF, URIRef
from rdflib.namespace import SH


@dataclass(frozen=True)
class ShaclValidationReport:
    """Result of validating an RDF data graph against a SHACL shapes graph."""

    conforms: bool
    report_graph: Any
    report_text: str


@dataclass(frozen=True)
class ShaclViolation:
    """Structured SHACL validation result for downstream repair controllers."""

    focus_node: str
    result_path: str | None
    source_constraint_component: str
    severity: str
    message: str


def validate_abox_turtle(turtle: str, shacl_path: Path) -> ShaclValidationReport:
    """Validate Turtle ABox data against a SHACL shapes file."""
    shacl_path = Path(shacl_path)
    if not shacl_path.exists():
        raise FileNotFoundError(f"SHACL file does not exist: {shacl_path}")
    if not shacl_path.is_file():
        raise ValueError(f"SHACL path is not a file: {shacl_path}")

    conforms, report_graph, report_text = validate(
        data_graph=turtle,
        shacl_graph=str(shacl_path),
        data_graph_format="turtle",
        shacl_graph_format="turtle",
        inference="rdfs",
        serialize_report_graph=False,
    )
    return ShaclValidationReport(
        conforms=bool(conforms),
        report_graph=report_graph,
        report_text=str(report_text),
    )


def parse_shacl_violations(report: ShaclValidationReport) -> list[ShaclViolation]:
    """Parse a pySHACL report graph into structured violation records."""
    if report.conforms:
        return []

    violations: list[ShaclViolation] = []
    for result_node in report.report_graph.subjects(RDF.type, SH.ValidationResult):
        focus_node = report.report_graph.value(result_node, SH.focusNode)
        result_path = report.report_graph.value(result_node, SH.resultPath)
        source_constraint_component = report.report_graph.value(
            result_node, SH.sourceConstraintComponent
        )
        severity = report.report_graph.value(result_node, SH.resultSeverity)
        message = report.report_graph.value(result_node, SH.resultMessage)

        violations.append(
            ShaclViolation(
                focus_node=_node_to_string(focus_node),
                result_path=_optional_node_to_string(result_path),
                source_constraint_component=_node_to_string(source_constraint_component),
                severity=_node_to_string(severity),
                message=_optional_node_to_string(message) or "",
            )
        )
    return violations


def _node_to_string(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, URIRef):
        return str(node)
    return str(node)


def _optional_node_to_string(node: Any) -> str | None:
    if node is None:
        return None
    return _node_to_string(node)
