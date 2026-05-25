from rdflib import Graph, Literal, Namespace, RDF

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
from neuro_onto_gen.core.serializer import serialize_abox_to_turtle

EX = Namespace("http://example.org/company/")


def test_serialize_abox_to_turtle_emits_company_individuals_and_relation() -> None:
    payload = ABoxPayload(
        employees=[ExtractedEmployee(emp_id="E-001", has_access_level=3)],
        secure_assets=[ExtractedSecureAsset(asset_id="VPN", required_clearance=2)],
        relations=[ExtractedRelation(subject_emp_id="E-001", predicate="operates", object_asset_id="VPN")],
    )

    turtle = serialize_abox_to_turtle(payload)

    graph = Graph()
    graph.parse(data=turtle, format="turtle")
    assert (EX["employee/E-001"], RDF.type, EX.Employee) in graph
    assert (EX["employee/E-001"], EX.empId, Literal("E-001")) in graph
    assert (EX["employee/E-001"], EX.hasAccessLevel, Literal(3)) in graph
    assert (EX["asset/VPN"], RDF.type, EX.SecureAsset) in graph
    assert (EX["asset/VPN"], EX.requiredClearance, Literal(2)) in graph
    assert (EX["employee/E-001"], EX.operates, EX["asset/VPN"]) in graph


def test_serialize_abox_to_turtle_emits_extended_company_schema_graph() -> None:
    payload = ABoxPayload(
        departments=[ExtractedDepartment(dept_id="D-SEC", name="Security")],
        employees=[ExtractedEmployee(emp_id="E-001", has_access_level=3, member_of_dept_id="D-SEC")],
        contractors=[ExtractedContractor(contractor_id="C-007", member_of_dept_id="D-SEC")],
        access_policies=[ExtractedAccessPolicy(policy_id="P-VPN", minimum_clearance=2, owner_department_dept_id="D-SEC")],
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
            ExtractedRelation(subject_emp_id="E-001", predicate="manages", object_department_id="D-SEC"),
            ExtractedRelation(subject_contractor_id="C-007", predicate="operates", object_asset_id="DB"),
        ],
    )

    graph = Graph()
    graph.parse(data=serialize_abox_to_turtle(payload), format="turtle")

    assert (EX["department/D-SEC"], RDF.type, EX.Department) in graph
    assert (EX["department/D-SEC"], EX.deptId, Literal("D-SEC")) in graph
    assert (EX["department/D-SEC"], EX.name, Literal("Security")) in graph
    assert (EX["employee/E-001"], EX.memberOf, EX["department/D-SEC"]) in graph
    assert (EX["contractor/C-007"], RDF.type, EX.Contractor) in graph
    assert (EX["policy/P-VPN"], EX.ownerDepartment, EX["department/D-SEC"]) in graph
    assert (EX["asset/DB"], RDF.type, EX.DigitalAsset) in graph
    assert (EX["asset/DB"], EX.networkZone, Literal("prod")) in graph
    assert (EX["asset/LAB-A"], RDF.type, EX.PhysicalAsset) in graph
    assert (EX["asset/LAB-A"], EX.siteCode, Literal("PAR-1")) in graph
    assert (EX["asset/DB"], EX.assignedPolicy, EX["policy/P-VPN"]) in graph
    assert (EX["asset/DB"], EX.managedBy, EX["employee/E-001"]) in graph
    assert (EX["employee/E-001"], EX.manages, EX["department/D-SEC"]) in graph
    assert (EX["contractor/C-007"], EX.operates, EX["asset/DB"]) in graph
