from pathlib import Path

from neuro_onto_gen.schema.compiler import compile_schema


def test_compile_schema_creates_nonempty_artifacts(tmp_path: Path) -> None:
    schema_path = Path("tests/fixtures/company_schema.yaml")

    artifacts = compile_schema(schema_path=schema_path, output_dir=tmp_path)

    assert set(artifacts) == {"json_schema", "shacl", "turtle"}
    for artifact_path in artifacts.values():
        assert artifact_path.exists()
        assert artifact_path.stat().st_size > 0

    assert artifacts["json_schema"].suffix == ".json"
    assert artifacts["shacl"].name.endswith(".shacl.ttl")
    assert artifacts["turtle"].name.endswith(".ttl")
