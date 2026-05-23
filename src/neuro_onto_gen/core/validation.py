"""SHACL validation helpers for serialized ontology ABox graphs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyshacl import validate


@dataclass(frozen=True)
class ShaclValidationReport:
    """Result of validating an RDF data graph against a SHACL shapes graph."""

    conforms: bool
    report_graph: Any
    report_text: str


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
