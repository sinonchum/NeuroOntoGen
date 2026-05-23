from pathlib import Path

from typer.testing import CliRunner

from neuro_onto_gen.cli import app

runner = CliRunner()


def test_company_examples_include_runnable_readme_and_turtle_files() -> None:
    example_dir = Path("examples/company")

    assert (example_dir / "README.md").exists()
    assert (example_dir / "valid_abox.ttl").exists()
    assert (example_dir / "invalid_abox.ttl").exists()

    readme = (example_dir / "README.md").read_text(encoding="utf-8")
    assert "neuro-onto-gen compile-schema" in readme
    assert "neuro-onto-gen validate-turtle" in readme
    assert "valid_abox.ttl" in readme
    assert "invalid_abox.ttl" in readme


def test_company_valid_example_conforms_via_cli(tmp_path: Path) -> None:
    schema_dir = tmp_path / "schema"
    compile_result = runner.invoke(
        app,
        ["compile-schema", "schemas/company_schema.yaml", str(schema_dir)],
    )
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(
        app,
        [
            "validate-turtle",
            "examples/company/valid_abox.ttl",
            str(schema_dir / "company_schema.shacl.ttl"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "conforms: true" in result.output.lower()


def test_company_invalid_example_reports_required_clearance_via_cli(tmp_path: Path) -> None:
    schema_dir = tmp_path / "schema"
    compile_result = runner.invoke(
        app,
        ["compile-schema", "schemas/company_schema.yaml", str(schema_dir)],
    )
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(
        app,
        [
            "validate-turtle",
            "examples/company/invalid_abox.ttl",
            str(schema_dir / "company_schema.shacl.ttl"),
        ],
    )

    assert result.exit_code == 1
    assert "conforms: false" in result.output.lower()
    assert "requiredClearance" in result.output
