"""Command line interface for NeuroOntoGen."""

from __future__ import annotations

from pathlib import Path

import typer
from pydantic import ValidationError

from neuro_onto_gen.core.extraction import ExtractorProtocol, PromptedExtractionAdapter
from neuro_onto_gen.core.owl_reasoner import OwlReasonerUnavailable, reason_owl_turtle
from neuro_onto_gen.core.repair import (
    LlmTurtleRepairer,
    OwlRepairController,
    OwlRepairFailure,
    RepairController,
    RepairFailure,
)
from neuro_onto_gen.core.validation import parse_shacl_violations, validate_abox_turtle
from neuro_onto_gen.providers import (
    DeepSeekProvider,
    OpenAICompatibleProvider,
    ProviderConfigurationError,
    ProviderResponseError,
    XiaomiMiMoProvider,
)
from neuro_onto_gen.schema.compiler import compile_schema

app = typer.Typer(help="NeuroOntoGen command line interface.")


def build_extraction_adapter(provider_name: str) -> ExtractorProtocol:
    """Build an extraction adapter for a named production provider."""
    normalized = provider_name.strip().lower()
    if normalized in {"xiaomi", "xiaomi-mimo", "mimo"}:
        return PromptedExtractionAdapter(provider=XiaomiMiMoProvider.from_env())
    if normalized in {"deepseek", "deepseek-v4-pro"}:
        return PromptedExtractionAdapter(provider=DeepSeekProvider.from_env())
    if normalized in {"openai", "openai-compatible", "openai-relay", "relay"}:
        return PromptedExtractionAdapter(provider=build_openai_compatible_provider())
    raise ProviderConfigurationError(f"unsupported extraction provider: {provider_name}")


def build_completion_provider(provider_name: str):
    """Build a raw completion provider for production repair/extraction commands."""
    normalized = provider_name.strip().lower()
    if normalized in {"xiaomi", "xiaomi-mimo", "mimo"}:
        return XiaomiMiMoProvider.from_env()
    if normalized in {"deepseek", "deepseek-v4-pro"}:
        return DeepSeekProvider.from_env()
    if normalized in {"openai", "openai-compatible", "openai-relay", "relay"}:
        return build_openai_compatible_provider()
    raise ProviderConfigurationError(f"unsupported completion provider: {provider_name}")


def build_openai_compatible_provider() -> OpenAICompatibleProvider:
    """Build a generic OpenAI-compatible provider from OPENAI_* env vars."""
    return OpenAICompatibleProvider.from_env_vars(
        provider_name="openai-compatible",
        api_key_env="OPENAI_API_KEY",
        base_url_env="OPENAI_BASE_URL",
        model_env="OPENAI_MODEL",
        timeout_env="OPENAI_TIMEOUT",
        max_retries_env="OPENAI_MAX_RETRIES",
        retry_delay_env="OPENAI_RETRY_DELAY",
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
    )


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


@app.command("repair-turtle")
def repair_turtle_command(
    turtle_path: Path = typer.Argument(..., help="Path to the RDF/Turtle data graph to repair."),
    shacl_path: Path = typer.Argument(..., help="Path to the SHACL shapes graph."),
    provider: str = typer.Option(
        "deepseek",
        "--provider",
        help="Completion provider name. Supported: xiaomi-mimo, deepseek, openai-compatible.",
    ),
    max_attempts: int = typer.Option(2, "--max-attempts", help="Maximum repair attempts."),
) -> None:
    """Repair a non-conforming Turtle graph using structured SHACL violations and an LLM."""
    try:
        completion_provider = build_completion_provider(provider)
        repairer = LlmTurtleRepairer(provider=completion_provider)
        controller = RepairController(
            shacl_path=shacl_path,
            repairer=repairer,
            max_attempts=max_attempts,
        )
        result = controller.repair_until_valid(turtle_path.read_text(encoding="utf-8"))
    except ProviderConfigurationError as exc:
        typer.echo(f"provider_config_error: {exc}")
        raise typer.Exit(code=2) from exc
    except ProviderResponseError as exc:
        typer.echo(f"provider_response_error: {exc}")
        raise typer.Exit(code=3) from exc
    except RepairFailure as exc:
        typer.echo(f"repair_failed: {exc.result.failure_reason}")
        if exc.result.error_message:
            typer.echo(f"error_message: {exc.result.error_message}")
        typer.echo(f"attempts: {len(exc.result.attempts)}")
        raise typer.Exit(code=5) from exc

    typer.echo(result.final_turtle)


@app.command("repair-owl")
def repair_owl_command(
    turtle_path: Path = typer.Argument(..., help="Path to the OWL/RDF Turtle ontology to repair."),
    provider: str = typer.Option(
        "deepseek",
        "--provider",
        help="Completion provider name. Supported: xiaomi-mimo, deepseek, openai-compatible.",
    ),
    max_attempts: int = typer.Option(2, "--max-attempts", help="Maximum OWL repair attempts."),
) -> None:
    """Repair an OWL-inconsistent Turtle ontology using an LLM and re-run the reasoner."""

    class LazyProviderRepairer:
        def __init__(self, provider_name: str) -> None:
            self.provider_name = provider_name
            self._repairer: LlmTurtleRepairer | None = None

        def repair(self, turtle: str, violations, attempt_number: int) -> str:
            if self._repairer is None:
                self._repairer = LlmTurtleRepairer(
                    provider=build_completion_provider(self.provider_name),
                    ontology_name="OWLConsistency",
                )
            return self._repairer.repair(turtle, violations, attempt_number)

    try:
        controller = OwlRepairController(
            reasoner=reason_owl_turtle,
            repairer=LazyProviderRepairer(provider),
            max_attempts=max_attempts,
        )
        result = controller.repair_until_consistent(turtle_path.read_text(encoding="utf-8"))
    except OwlReasonerUnavailable as exc:
        typer.echo("available: false")
        typer.echo(f"reason: {exc.status.reason}")
        typer.echo(f"install_hint: {exc.status.install_hint}")
        raise typer.Exit(code=2) from exc
    except ProviderConfigurationError as exc:
        typer.echo(f"provider_config_error: {exc}")
        raise typer.Exit(code=2) from exc
    except ProviderResponseError as exc:
        typer.echo(f"provider_response_error: {exc}")
        raise typer.Exit(code=3) from exc
    except OwlRepairFailure as exc:
        typer.echo(f"owl_repair_failed: {exc.result.failure_reason}")
        if exc.result.error_message:
            typer.echo(f"error_message: {exc.result.error_message}")
        typer.echo(f"attempts: {len(exc.result.attempts)}")
        raise typer.Exit(code=5) from exc

    typer.echo(result.final_turtle)


@app.command("extract")
def extract_command(
    text: str = typer.Argument(..., help="Source text to extract into validated ABox JSON."),
    provider: str = typer.Option(
        "deepseek",
        "--provider",
        help="Extraction provider name. Supported: deepseek, openai-compatible. Xiaomi MiMo remains available only when explicitly requested.",
    ),
) -> None:
    """Extract a validated CompanyAccess ABox payload from source text."""
    try:
        adapter = build_extraction_adapter(provider)
        payload = adapter.extract(text)
    except ProviderConfigurationError as exc:
        typer.echo(f"provider_config_error: {exc}")
        raise typer.Exit(code=2) from exc
    except ProviderResponseError as exc:
        typer.echo(f"provider_response_error: {exc}")
        raise typer.Exit(code=3) from exc
    except ValidationError as exc:
        typer.echo("extraction_validation_error:")
        typer.echo(str(exc))
        raise typer.Exit(code=4) from exc

    typer.echo(payload.model_dump_json(indent=2))


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
