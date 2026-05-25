import pytest
from pydantic import ValidationError

from neuro_onto_gen.core.models import (
    ABoxPayload,
    ExtractedAccessPolicy,
    ExtractedContractor,
    ExtractedDepartment,
    ExtractedDigitalAsset,
    ExtractedEmployee,
    ExtractedPhysicalAsset,
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
    with pytest.raises(ValidationError, match="Input should be"):
        ExtractedRelation(subject_emp_id="E-001", predicate="owns", object_asset_id="VPN")


def test_abox_payload_accepts_extended_company_schema_entities_and_relations() -> None:
    payload = ABoxPayload(
        departments=[ExtractedDepartment(dept_id="D-SEC", name="Security")],
        employees=[
            ExtractedEmployee(
                emp_id="E-001",
                has_access_level=3,
                display_name="Alice Analyst",
                member_of_dept_id="D-SEC",
            )
        ],
        contractors=[
            ExtractedContractor(
                contractor_id="C-007",
                display_name="Casey Contractor",
                access_expires_on="2026-12-31",
                member_of_dept_id="D-SEC",
            )
        ],
        access_policies=[
            ExtractedAccessPolicy(policy_id="P-VPN", minimum_clearance=2, owner_department_dept_id="D-SEC")
        ],
        secure_assets=[
            ExtractedSecureAsset(
                asset_id="VPN",
                required_clearance=2,
                assigned_policy_id="P-VPN",
                managed_by_emp_id="E-001",
            )
        ],
        digital_assets=[
            ExtractedDigitalAsset(
                asset_id="DB",
                required_clearance=3,
                assigned_policy_id="P-VPN",
                managed_by_emp_id="E-001",
                network_zone="prod",
            )
        ],
        physical_assets=[
            ExtractedPhysicalAsset(
                asset_id="LAB-A",
                required_clearance=2,
                assigned_policy_id="P-VPN",
                managed_by_emp_id="E-001",
                site_code="PAR-1",
            )
        ],
        relations=[
            ExtractedRelation(subject_emp_id="E-001", predicate="memberOf", object_department_id="D-SEC"),
            ExtractedRelation(subject_emp_id="E-001", predicate="manages", object_department_id="D-SEC"),
            ExtractedRelation(subject_contractor_id="C-007", predicate="operates", object_asset_id="VPN"),
            ExtractedRelation(subject_asset_id="VPN", predicate="assignedPolicy", object_policy_id="P-VPN"),
            ExtractedRelation(subject_asset_id="VPN", predicate="managedBy", object_emp_id="E-001"),
            ExtractedRelation(subject_policy_id="P-VPN", predicate="ownerDepartment", object_department_id="D-SEC"),
        ],
    )

    assert payload.departments[0].dept_id == "D-SEC"
    assert payload.contractors[0].contractor_id == "C-007"
    assert payload.access_policies[0].owner_department_dept_id == "D-SEC"
    assert payload.digital_assets[0].network_zone == "prod"
    assert payload.physical_assets[0].site_code == "PAR-1"
    assert {relation.predicate for relation in payload.relations} == {
        "memberOf",
        "manages",
        "operates",
        "assignedPolicy",
        "managedBy",
        "ownerDepartment",
    }


def test_abox_payload_rejects_extended_relation_to_unknown_endpoint() -> None:
    with pytest.raises(ValidationError, match="unknown department"):
        ABoxPayload(
            employees=[ExtractedEmployee(emp_id="E-001", has_access_level=3)],
            relations=[
                ExtractedRelation(subject_emp_id="E-001", predicate="memberOf", object_department_id="D-404")
            ],
        )
