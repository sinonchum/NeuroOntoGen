import pytest
from pydantic import ValidationError

from neuro_onto_gen.core.models import (
    ABoxPayload,
    ExtractedEmployee,
    ExtractedRelation,
    ExtractedSecureAsset,
)


def test_abox_payload_accepts_company_extractions() -> None:
    payload = ABoxPayload(
        employees=[ExtractedEmployee(emp_id="E-001", has_access_level=3)],
        secure_assets=[ExtractedSecureAsset(asset_id="VPN", required_clearance=2)],
        relations=[ExtractedRelation(subject_emp_id="E-001", predicate="operates", object_asset_id="VPN")],
    )

    assert payload.employees[0].emp_id == "E-001"
    assert payload.secure_assets[0].required_clearance == 2
    assert payload.relations[0].predicate == "operates"


def test_abox_payload_rejects_relations_to_unknown_entities() -> None:
    with pytest.raises(ValidationError, match="unknown employee"):
        ABoxPayload(
            employees=[ExtractedEmployee(emp_id="E-001", has_access_level=3)],
            secure_assets=[ExtractedSecureAsset(asset_id="VPN", required_clearance=2)],
            relations=[
                ExtractedRelation(
                    subject_emp_id="E-404",
                    predicate="operates",
                    object_asset_id="VPN",
                )
            ],
        )


def test_abox_payload_rejects_unsupported_predicates() -> None:
    with pytest.raises(ValidationError, match="Input should be 'operates'"):
        ExtractedRelation(subject_emp_id="E-001", predicate="owns", object_asset_id="VPN")
