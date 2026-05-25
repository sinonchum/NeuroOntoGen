"""RDF serialization helpers for extracted ABox payloads."""

from __future__ import annotations

from rdflib import Graph, Literal, Namespace, RDF, URIRef

from neuro_onto_gen.core.models import ABoxPayload, ExtractedSecureAsset

EX = Namespace("http://example.org/company/")


def serialize_abox_to_turtle(payload: ABoxPayload) -> str:
    """Serialize a validated company ontology ABox payload to Turtle."""
    graph = Graph()
    graph.bind("ex", EX)

    for department in payload.departments:
        department_uri = _department_uri(department.dept_id)
        graph.add((department_uri, RDF.type, EX.Department))
        _add_optional_literal(graph, department_uri, EX.entityId, department.entity_id)
        graph.add((department_uri, EX.deptId, Literal(department.dept_id)))
        graph.add((department_uri, EX.name, Literal(department.name)))

    for person in payload.persons:
        person_uri = _person_uri(person.person_id)
        graph.add((person_uri, RDF.type, EX.Person))
        _add_optional_literal(graph, person_uri, EX.entityId, person.entity_id)
        _add_optional_literal(graph, person_uri, EX.displayName, person.display_name)
        _add_optional_uri(graph, person_uri, EX.memberOf, person.member_of_dept_id, _department_uri)

    for employee in payload.employees:
        employee_uri = _employee_uri(employee.emp_id)
        graph.add((employee_uri, RDF.type, EX.Employee))
        _add_optional_literal(graph, employee_uri, EX.entityId, employee.entity_id)
        graph.add((employee_uri, EX.empId, Literal(employee.emp_id)))
        graph.add((employee_uri, EX.hasAccessLevel, Literal(employee.has_access_level)))
        _add_optional_literal(graph, employee_uri, EX.displayName, employee.display_name)
        _add_optional_uri(graph, employee_uri, EX.memberOf, employee.member_of_dept_id, _department_uri)

    for contractor in payload.contractors:
        contractor_uri = _contractor_uri(contractor.contractor_id)
        graph.add((contractor_uri, RDF.type, EX.Contractor))
        _add_optional_literal(graph, contractor_uri, EX.entityId, contractor.entity_id)
        graph.add((contractor_uri, EX.contractorId, Literal(contractor.contractor_id)))
        _add_optional_literal(graph, contractor_uri, EX.displayName, contractor.display_name)
        _add_optional_literal(graph, contractor_uri, EX.accessExpiresOn, contractor.access_expires_on)
        _add_optional_uri(graph, contractor_uri, EX.memberOf, contractor.member_of_dept_id, _department_uri)

    for policy in payload.access_policies:
        policy_uri = _policy_uri(policy.policy_id)
        graph.add((policy_uri, RDF.type, EX.AccessPolicy))
        _add_optional_literal(graph, policy_uri, EX.entityId, policy.entity_id)
        graph.add((policy_uri, EX.policyId, Literal(policy.policy_id)))
        graph.add((policy_uri, EX.minimumClearance, Literal(policy.minimum_clearance)))
        _add_optional_uri(graph, policy_uri, EX.ownerDepartment, policy.owner_department_dept_id, _department_uri)

    for asset in payload.secure_assets:
        _add_secure_asset(graph, asset, EX.SecureAsset)
    for asset in payload.digital_assets:
        asset_uri = _add_secure_asset(graph, asset, EX.DigitalAsset)
        _add_optional_literal(graph, asset_uri, EX.networkZone, asset.network_zone)
    for asset in payload.physical_assets:
        asset_uri = _add_secure_asset(graph, asset, EX.PhysicalAsset)
        _add_optional_literal(graph, asset_uri, EX.siteCode, asset.site_code)

    for relation in payload.relations:
        if relation.predicate == "memberOf":
            subject_uri = _person_relation_subject_uri(relation)
            graph.add((subject_uri, EX.memberOf, _department_uri(relation.object_department_id or "")))
        elif relation.predicate == "manages":
            graph.add((_employee_uri(relation.subject_emp_id or ""), EX.manages, _department_uri(relation.object_department_id or "")))
        elif relation.predicate == "operates":
            subject_uri = _person_relation_subject_uri(relation)
            graph.add((subject_uri, EX.operates, _asset_uri(relation.object_asset_id or "")))
        elif relation.predicate == "assignedPolicy":
            graph.add((_asset_uri(relation.subject_asset_id or ""), EX.assignedPolicy, _policy_uri(relation.object_policy_id or "")))
        elif relation.predicate == "managedBy":
            graph.add((_asset_uri(relation.subject_asset_id or ""), EX.managedBy, _employee_uri(relation.object_emp_id or "")))
        elif relation.predicate == "ownerDepartment":
            graph.add((_policy_uri(relation.subject_policy_id or ""), EX.ownerDepartment, _department_uri(relation.object_department_id or "")))

    return graph.serialize(format="turtle")


def _add_secure_asset(graph: Graph, asset: ExtractedSecureAsset, class_uri: URIRef) -> URIRef:
    asset_uri = _asset_uri(asset.asset_id)
    graph.add((asset_uri, RDF.type, EX.SecureAsset))
    if class_uri != EX.SecureAsset:
        graph.add((asset_uri, RDF.type, class_uri))
    _add_optional_literal(graph, asset_uri, EX.entityId, asset.entity_id)
    graph.add((asset_uri, EX.assetId, Literal(asset.asset_id)))
    graph.add((asset_uri, EX.requiredClearance, Literal(asset.required_clearance)))
    _add_optional_uri(graph, asset_uri, EX.assignedPolicy, asset.assigned_policy_id, _policy_uri)
    _add_optional_uri(graph, asset_uri, EX.managedBy, asset.managed_by_emp_id, _employee_uri)
    return asset_uri


def _add_optional_literal(graph: Graph, subject: URIRef, predicate: URIRef, value: str | None) -> None:
    if value is not None:
        graph.add((subject, predicate, Literal(value)))


def _add_optional_uri(
    graph: Graph,
    subject: URIRef,
    predicate: URIRef,
    value: str | None,
    uri_builder,
) -> None:
    if value is not None:
        graph.add((subject, predicate, uri_builder(value)))


def _person_relation_subject_uri(relation) -> URIRef:
    if relation.subject_emp_id:
        return _employee_uri(relation.subject_emp_id)
    if relation.subject_contractor_id:
        return _contractor_uri(relation.subject_contractor_id)
    return _person_uri(relation.subject_person_id or "")


def _person_uri(person_id: str) -> URIRef:
    return EX[f"person/{person_id}"]


def _employee_uri(emp_id: str) -> URIRef:
    return EX[f"employee/{emp_id}"]


def _contractor_uri(contractor_id: str) -> URIRef:
    return EX[f"contractor/{contractor_id}"]


def _department_uri(dept_id: str) -> URIRef:
    return EX[f"department/{dept_id}"]


def _policy_uri(policy_id: str) -> URIRef:
    return EX[f"policy/{policy_id}"]


def _asset_uri(asset_id: str) -> URIRef:
    return EX[f"asset/{asset_id}"]
