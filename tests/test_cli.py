import json
from pathlib import Path

from typer.testing import CliRunner

from neuro_onto_gen.cli import app
from neuro_onto_gen.core.extraction import JsonExtractionAdapter

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


def test_extract_command_uses_xiaomi_mimo_provider_and_prints_validated_json(
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

    monkeypatch.setattr(
        "neuro_onto_gen.cli.build_extraction_adapter",
        lambda provider_name: adapter,
    )

    result = runner.invoke(
        app,
        ["extract", "Employee E-001 operates secure asset VPN."],
    )

    assert result.exit_code == 0, result.output
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

        raise ProviderConfigurationError("XIAOMI_API_KEY is required")

    monkeypatch.setattr(
        "neuro_onto_gen.cli.build_extraction_adapter",
        raise_configuration_error,
    )

    result = runner.invoke(app, ["extract", "Employee E-001 operates VPN."])

    assert result.exit_code == 2
    assert "provider_config_error" in result.output
    assert "XIAOMI_API_KEY" in result.output
