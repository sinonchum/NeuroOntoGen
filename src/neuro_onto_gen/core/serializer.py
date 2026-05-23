"""RDF serialization helpers for extracted ABox payloads."""

from __future__ import annotations

from rdflib import Graph, Literal, Namespace, RDF, URIRef

from neuro_onto_gen.core.models import ABoxPayload

EX = Namespace("http://example.org/company/")


def serialize_abox_to_turtle(payload: ABoxPayload) -> str:
    """Serialize a validated company ontology ABox payload to Turtle."""
    graph = Graph()
    graph.bind("ex", EX)

    for employee in payload.employees:
        employee_uri = _employee_uri(employee.emp_id)
        graph.add((employee_uri, RDF.type, EX.Employee))
        graph.add((employee_uri, EX.empId, Literal(employee.emp_id)))
        graph.add((employee_uri, EX.hasAccessLevel, Literal(employee.has_access_level)))

    for asset in payload.secure_assets:
        asset_uri = _asset_uri(asset.asset_id)
        graph.add((asset_uri, RDF.type, EX.SecureAsset))
        graph.add((asset_uri, EX.assetId, Literal(asset.asset_id)))
        graph.add((asset_uri, EX.requiredClearance, Literal(asset.required_clearance)))

    for relation in payload.relations:
        graph.add((_employee_uri(relation.subject_emp_id), EX.operates, _asset_uri(relation.object_asset_id)))

    return graph.serialize(format="turtle")


def _employee_uri(emp_id: str) -> URIRef:
    return EX[f"employee/{emp_id}"]


def _asset_uri(asset_id: str) -> URIRef:
    return EX[f"asset/{asset_id}"]
