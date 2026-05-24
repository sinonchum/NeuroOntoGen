import json
from pathlib import Path

from typer.testing import CliRunner

from neuro_onto_gen.cli import app
from neuro_onto_gen.core.extraction import JsonExtractionAdapter
from neuro_onto_gen.core.owl_reasoner import (
    OwlReasonerEngine,
    OwlReasonerStatus,
    OwlReasonerUnavailable,
    OwlReasoningReport,
)

runner = CliRunner()


VALID_TURTLE = """
@prefix ex: <http://example.org/company/> .

<http://example.org/company/employee/E-001> a ex:Employee ;
    ex:empId "E-001" ;
    ex:hasAccessLevel 3 .

<http://example.org/company/asset/VPN> a ex:SecureAsset ;
    ex:assetId "VPN" ;
    ex:requiredClearance 2 .

<http://example.org/company/employee/E-001> ex:operates <http://example.org/company/asset/VPN> .
"""


INVALID_TURTLE = """
@prefix ex: <http://example.org/company/> .

<http://example.org/company/asset/VPN> a ex:SecureAsset ;
    ex:assetId "VPN" .
"""

OWL_CONFLICT_TURTLE = """
@prefix ex: <http://example.org/owl-test/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
ex:Person a owl:Class .
ex:Machine a owl:Class .
ex:Person owl:disjointWith ex:Machine .
ex:alice a ex:Person, ex:Machine .
"""

OWL_REPAIRED_TURTLE = """
@prefix ex: <http://example.org/owl-test/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
ex:Person a owl:Class .
ex:Machine a owl:Class .
ex:Person owl:disjointWith ex:Machine .
ex:alice a ex:Person .
"""


def test_compile_schema_command_writes_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "schema"

    result = runner.invoke(
        app,
        ["compile-schema", "tests/fixtures/company_schema.yaml", str(output_dir)],
    )

    assert result.exit_code == 0, result.output
    assert (output_dir / "company_schema.schema.json").exists()
    assert (output_dir / "company_schema.shacl.ttl").exists()
    assert (output_dir / "company_schema.ttl").exists()
    assert "json_schema" in result.output
    assert "shacl" in result.output
    assert "turtle" in result.output


def test_validate_turtle_command_exits_zero_for_conforming_graph(tmp_path: Path) -> None:
    schema_dir = tmp_path / "schema"
    compile_result = runner.invoke(
        app,
        ["compile-schema", "tests/fixtures/company_schema.yaml", str(schema_dir)],
    )
    assert compile_result.exit_code == 0, compile_result.output
    data_path = tmp_path / "valid.ttl"
    data_path.write_text(VALID_TURTLE, encoding="utf-8")

    result = runner.invoke(
        app,
        ["validate-turtle", str(data_path), str(schema_dir / "company_schema.shacl.ttl")],
    )

    assert result.exit_code == 0, result.output
    assert "conforms: true" in result.output.lower()


def test_validate_turtle_command_exits_nonzero_and_prints_violations(
    tmp_path: Path,
) -> None:
    schema_dir = tmp_path / "schema"
    compile_result = runner.invoke(
        app,
        ["compile-schema", "tests/fixtures/company_schema.yaml", str(schema_dir)],
    )
    assert compile_result.exit_code == 0, compile_result.output
    data_path = tmp_path / "invalid.ttl"
    data_path.write_text(INVALID_TURTLE, encoding="utf-8")

    result = runner.invoke(
        app,
        ["validate-turtle", str(data_path), str(schema_dir / "company_schema.shacl.ttl")],
    )

    assert result.exit_code == 1
    assert "conforms: false" in result.output.lower()
    assert "requiredClearance" in result.output


def test_extract_command_defaults_to_deepseek_provider_and_prints_validated_json(
    monkeypatch,
) -> None:
    raw_output = {
        "employees": [{"emp_id": "E-001", "has_access_level": 3}],
        "secure_assets": [{"asset_id": "VPN", "required_clearance": 2}],
        "relations": [
            {
                "subject_emp_id": "E-001",
                "predicate": "operates",
                "object_asset_id": "VPN",
            }
        ],
    }
    adapter = JsonExtractionAdapter(raw_output=raw_output)
    seen_provider_names = []

    def fake_build(provider_name):
        seen_provider_names.append(provider_name)
        return adapter

    monkeypatch.setattr(
        "neuro_onto_gen.cli.build_extraction_adapter",
        fake_build,
    )

    result = runner.invoke(
        app,
        ["extract", "Employee E-001 operates secure asset VPN."],
    )

    assert result.exit_code == 0, result.output
    assert seen_provider_names == ["deepseek"]
    parsed = json.loads(result.output)
    assert parsed["employees"][0]["emp_id"] == "E-001"
    assert parsed["secure_assets"][0]["asset_id"] == "VPN"
    assert parsed["relations"][0]["predicate"] == "operates"


def test_extract_command_accepts_deepseek_provider_name(monkeypatch) -> None:
    seen_provider_names = []
    adapter = JsonExtractionAdapter(
        raw_output={"employees": [], "secure_assets": [], "relations": []}
    )

    def fake_build(provider_name):
        seen_provider_names.append(provider_name)
        return adapter

    monkeypatch.setattr("neuro_onto_gen.cli.build_extraction_adapter", fake_build)

    result = runner.invoke(app, ["extract", "No supported facts.", "--provider", "deepseek"])

    assert result.exit_code == 0, result.output
    assert seen_provider_names == ["deepseek"]
    assert json.loads(result.output) == {"employees": [], "secure_assets": [], "relations": []}


def test_repair_turtle_command_uses_provider_revalidates_and_prints_fixed_turtle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    schema_dir = tmp_path / "schema"
    compile_result = runner.invoke(
        app,
        ["compile-schema", "tests/fixtures/company_schema.yaml", str(schema_dir)],
    )
    assert compile_result.exit_code == 0, compile_result.output
    data_path = tmp_path / "invalid.ttl"
    data_path.write_text(INVALID_TURTLE, encoding="utf-8")

    class FixedProvider:
        def complete(self, prompt: str) -> str:
            assert "SHACL Violations" in prompt
            assert "requiredClearance" in prompt
            return VALID_TURTLE

    monkeypatch.setattr(
        "neuro_onto_gen.cli.build_completion_provider",
        lambda provider_name: FixedProvider(),
    )

    result = runner.invoke(
        app,
        [
            "repair-turtle",
            str(data_path),
            str(schema_dir / "company_schema.shacl.ttl"),
            "--provider",
            "deepseek",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "ex:requiredClearance 2" in result.output
    assert "ex:operates" in result.output


def test_extract_command_reports_provider_configuration_errors(monkeypatch) -> None:
    def raise_configuration_error(_provider_name):
        from neuro_onto_gen.providers import ProviderConfigurationError

        raise ProviderConfigurationError("DEEPSEEK_API_KEY is required")

    monkeypatch.setattr(
        "neuro_onto_gen.cli.build_extraction_adapter",
        raise_configuration_error,
    )

    result = runner.invoke(app, ["extract", "Employee E-001 operates VPN."])

    assert result.exit_code == 2
    assert "provider_config_error" in result.output
    assert "DEEPSEEK_API_KEY" in result.output


def test_repair_owl_command_uses_provider_rereasons_and_prints_consistent_turtle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    turtle_path = tmp_path / "conflict.ttl"
    turtle_path.write_text(OWL_CONFLICT_TURTLE, encoding="utf-8")
    reasoner_reports = [
        OwlReasoningReport(True, False, OwlReasonerEngine.PELLET, "disjoint classes conflict"),
        OwlReasoningReport(True, True, OwlReasonerEngine.PELLET, "Ontology is consistent."),
    ]
    seen_provider_names = []

    class FixedProvider:
        def complete(self, prompt: str) -> str:
            assert "diagnostic_type=owl_inconsistency" in prompt
            assert "OWLConsistencyConstraintComponent" in prompt
            assert "disjoint classes conflict" in prompt
            return OWL_REPAIRED_TURTLE

    def fake_reasoner(turtle: str) -> OwlReasoningReport:
        assert turtle
        return reasoner_reports.pop(0)

    def fake_build(provider_name: str) -> FixedProvider:
        seen_provider_names.append(provider_name)
        return FixedProvider()

    monkeypatch.setattr("neuro_onto_gen.cli.reason_owl_turtle", fake_reasoner)
    monkeypatch.setattr("neuro_onto_gen.cli.build_completion_provider", fake_build)

    result = runner.invoke(app, ["repair-owl", str(turtle_path)])

    assert result.exit_code == 0, result.output
    assert seen_provider_names == ["deepseek"]
    assert "ex:alice a ex:Person" in result.output
    assert "ex:Machine" in result.output
    assert not reasoner_reports


def test_repair_owl_command_reports_unavailable_reasoner(tmp_path: Path, monkeypatch) -> None:
    turtle_path = tmp_path / "conflict.ttl"
    turtle_path.write_text(OWL_CONFLICT_TURTLE, encoding="utf-8")
    status = OwlReasonerStatus(
        available=False,
        engine=OwlReasonerEngine.PELLET,
        reason="owlready2 is not installed",
    )

    def raise_unavailable(_turtle: str):
        raise OwlReasonerUnavailable(status)

    monkeypatch.setattr("neuro_onto_gen.cli.reason_owl_turtle", raise_unavailable)

    result = runner.invoke(app, ["repair-owl", str(turtle_path)])

    assert result.exit_code == 2
    assert "available: false" in result.output
    assert "owlready2 is not installed" in result.output
    assert "pip install -e '.[owl]'" in result.output
