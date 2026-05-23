from rdflib import Graph, Literal, Namespace, RDF

from neuro_onto_gen.core.models import (
    ABoxPayload,
    ExtractedEmployee,
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
