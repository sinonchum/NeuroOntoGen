from pathlib import Path

from typer.testing import CliRunner

from neuro_onto_gen.cli import app

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
