"""Command line interface for NeuroOntoGen."""

from __future__ import annotations

from pathlib import Path

import typer

from neuro_onto_gen.core.owl_reasoner import OwlReasonerUnavailable, reason_owl_turtle
from neuro_onto_gen.core.validation import parse_shacl_violations, validate_abox_turtle
from neuro_onto_gen.schema.compiler import compile_schema

app = typer.Typer(help="NeuroOntoGen command line interface.")


@app.callback()
def main() -> None:
    """NeuroOntoGen CLI."""


@app.command("compile-schema")
def compile_schema_command(
    schema_path: Path = typer.Argument(..., help="Path to the LinkML YAML schema."),
    output_dir: Path = typer.Argument(..., help="Directory for generated schema artifacts."),
) -> None:
    """Compile a LinkML schema into JSON Schema, SHACL, and Turtle artifacts."""
    artifacts = compile_schema(schema_path=schema_path, output_dir=output_dir)
    for artifact_name, artifact_path in artifacts.items():
        typer.echo(f"{artifact_name}: {artifact_path}")


@app.command("validate-turtle")
def validate_turtle_command(
    turtle_path: Path = typer.Argument(..., help="Path to the RDF/Turtle data graph."),
    shacl_path: Path = typer.Argument(..., help="Path to the SHACL shapes graph."),
) -> None:
    """Validate a Turtle data graph against a SHACL shapes graph."""
    turtle = turtle_path.read_text(encoding="utf-8")
    report = validate_abox_turtle(turtle=turtle, shacl_path=shacl_path)

    typer.echo(f"conforms: {str(report.conforms).lower()}")
    if report.conforms:
        return

    violations = parse_shacl_violations(report)
    for index, violation in enumerate(violations, start=1):
        typer.echo(f"violation {index}:")
        typer.echo(f"  focus_node: {violation.focus_node}")
        if violation.result_path is not None:
            typer.echo(f"  result_path: {violation.result_path}")
        typer.echo(f"  source_constraint_component: {violation.source_constraint_component}")
        typer.echo(f"  severity: {violation.severity}")
        typer.echo(f"  message: {violation.message}")
    raise typer.Exit(code=1)


@app.command("reason-owl")
def reason_owl_command(
    turtle_path: Path = typer.Argument(..., help="Path to an OWL/RDF Turtle ontology."),
) -> None:
    """Run an optional OWL consistency check over a Turtle ontology."""
    turtle = turtle_path.read_text(encoding="utf-8")
    try:
        report = reason_owl_turtle(turtle)
    except OwlReasonerUnavailable as exc:
        typer.echo("available: false")
        typer.echo(f"reason: {exc.status.reason}")
        typer.echo(f"install_hint: {exc.status.install_hint}")
        raise typer.Exit(code=2) from exc

    typer.echo("available: true")
    typer.echo(f"engine: {report.engine.value}")
    typer.echo(f"consistent: {str(report.consistent).lower()}")
    typer.echo(f"message: {report.message}")
    if report.consistent is False:
        raise typer.Exit(code=1)
