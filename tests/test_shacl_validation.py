from pathlib import Path

from neuro_onto_gen.core.models import (
    ABoxPayload,
    ExtractedEmployee,
    ExtractedRelation,
    ExtractedSecureAsset,
)
from neuro_onto_gen.core.serializer import serialize_abox_to_turtle
from neuro_onto_gen.core.validation import validate_abox_turtle
from neuro_onto_gen.schema.compiler import compile_schema


def test_validate_abox_turtle_conforms_to_generated_shacl(tmp_path: Path) -> None:
    artifacts = compile_schema(Path("tests/fixtures/company_schema.yaml"), tmp_path)
    payload = ABoxPayload(
        employees=[ExtractedEmployee(emp_id="E-001", has_access_level=3)],
        secure_assets=[ExtractedSecureAsset(asset_id="VPN", required_clearance=2)],
        relations=[ExtractedRelation(subject_emp_id="E-001", predicate="operates", object_asset_id="VPN")],
    )

    report = validate_abox_turtle(serialize_abox_to_turtle(payload), artifacts["shacl"])

    assert report.conforms is True
    assert report.report_text


def test_validate_abox_turtle_reports_missing_required_property(tmp_path: Path) -> None:
    artifacts = compile_schema(Path("tests/fixtures/company_schema.yaml"), tmp_path)
    invalid_turtle = """
        @prefix ex: <http://example.org/company/> .

        <http://example.org/company/asset/VPN> a ex:SecureAsset ;
            ex:assetId "VPN" .
    """

    report = validate_abox_turtle(invalid_turtle, artifacts["shacl"])

    assert report.conforms is False
    assert "requiredClearance" in report.report_text
