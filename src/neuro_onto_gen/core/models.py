"""Core extraction models for NeuroOntoGen ABox payloads."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExtractedPerson(BaseModel):
    """Person individual extracted from unstructured input."""

    model_config = ConfigDict(frozen=True)

    person_id: str = Field(min_length=1)
    entity_id: str | None = None
    display_name: str | None = None
    member_of_dept_id: str | None = None


class ExtractedEmployee(BaseModel):
    """Employee individual extracted from unstructured input."""

    model_config = ConfigDict(frozen=True)

    emp_id: str = Field(min_length=1)
    entity_id: str | None = None
    has_access_level: int = Field(ge=0)
    display_name: str | None = None
    member_of_dept_id: str | None = None


class ExtractedContractor(BaseModel):
    """Contractor individual extracted from unstructured input."""

    model_config = ConfigDict(frozen=True)

    contractor_id: str = Field(min_length=1)
    entity_id: str | None = None
    display_name: str | None = None
    member_of_dept_id: str | None = None
    access_expires_on: str | None = None


class ExtractedDepartment(BaseModel):
    """Department individual extracted from unstructured input."""

    model_config = ConfigDict(frozen=True)

    dept_id: str = Field(min_length=1)
    entity_id: str | None = None
    name: str = Field(min_length=1)


class ExtractedAccessPolicy(BaseModel):
    """Access policy individual extracted from unstructured input."""

    model_config = ConfigDict(frozen=True)

    policy_id: str = Field(min_length=1)
    entity_id: str | None = None
    minimum_clearance: int = Field(ge=0)
    owner_department_dept_id: str | None = None


class ExtractedSecureAsset(BaseModel):
    """Secure asset individual extracted from unstructured input."""

    model_config = ConfigDict(frozen=True)

    asset_id: str = Field(min_length=1)
    entity_id: str | None = None
    required_clearance: int = Field(ge=0)
    assigned_policy_id: str | None = None
    managed_by_emp_id: str | None = None


class ExtractedDigitalAsset(ExtractedSecureAsset):
    """Digital secure asset such as an application, VPN, or database."""

    network_zone: str | None = None


class ExtractedPhysicalAsset(ExtractedSecureAsset):
    """Physical secure asset such as a lab, vault, or restricted device."""

    site_code: str | None = None


RelationPredicate = Literal[
    "memberOf",
    "manages",
    "operates",
    "assignedPolicy",
    "managedBy",
    "ownerDepartment",
]


class ExtractedRelation(BaseModel):
    """Relation between extracted company ontology individuals.

    Endpoint fields are predicate-specific. The legacy ``operates`` shape using
    ``subject_emp_id`` and ``object_asset_id`` remains supported, while the
    extended CompanyOntology relations can reference contractors, departments,
    policies, and asset management endpoints.
    """

    model_config = ConfigDict(frozen=True)

    predicate: RelationPredicate
    subject_person_id: str | None = Field(default=None, min_length=1)
    subject_emp_id: str | None = Field(default=None, min_length=1)
    subject_contractor_id: str | None = Field(default=None, min_length=1)
    subject_asset_id: str | None = Field(default=None, min_length=1)
    subject_policy_id: str | None = Field(default=None, min_length=1)
    object_department_id: str | None = Field(default=None, min_length=1)
    object_asset_id: str | None = Field(default=None, min_length=1)
    object_policy_id: str | None = Field(default=None, min_length=1)
    object_emp_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_predicate_shape(self) -> ExtractedRelation:
        """Ensure every predicate carries the endpoint fields it needs."""
        if self.predicate == "memberOf":
            if not (self.subject_person_id or self.subject_emp_id or self.subject_contractor_id):
                raise ValueError("memberOf requires a person, employee, or contractor subject")
            if not self.object_department_id:
                raise ValueError("memberOf requires object_department_id")
        elif self.predicate == "manages":
            if not self.subject_emp_id:
                raise ValueError("manages requires subject_emp_id")
            if not self.object_department_id:
                raise ValueError("manages requires object_department_id")
        elif self.predicate == "operates":
            if not (self.subject_person_id or self.subject_emp_id or self.subject_contractor_id):
                raise ValueError("operates requires a person, employee, or contractor subject")
            if not self.object_asset_id:
                raise ValueError("operates requires object_asset_id")
        elif self.predicate == "assignedPolicy":
            if not self.subject_asset_id:
                raise ValueError("assignedPolicy requires subject_asset_id")
            if not self.object_policy_id:
                raise ValueError("assignedPolicy requires object_policy_id")
        elif self.predicate == "managedBy":
            if not self.subject_asset_id:
                raise ValueError("managedBy requires subject_asset_id")
            if not self.object_emp_id:
                raise ValueError("managedBy requires object_emp_id")
        elif self.predicate == "ownerDepartment":
            if not self.subject_policy_id:
                raise ValueError("ownerDepartment requires subject_policy_id")
            if not self.object_department_id:
                raise ValueError("ownerDepartment requires object_department_id")
        return self


class ABoxPayload(BaseModel):
    """Validated set of extracted individuals and object-property assertions."""

    persons: list[ExtractedPerson] = Field(default_factory=list)
    employees: list[ExtractedEmployee] = Field(default_factory=list)
    contractors: list[ExtractedContractor] = Field(default_factory=list)
    departments: list[ExtractedDepartment] = Field(default_factory=list)
    access_policies: list[ExtractedAccessPolicy] = Field(default_factory=list)
    secure_assets: list[ExtractedSecureAsset] = Field(default_factory=list)
    digital_assets: list[ExtractedDigitalAsset] = Field(default_factory=list)
    physical_assets: list[ExtractedPhysicalAsset] = Field(default_factory=list)
    relations: list[ExtractedRelation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_relation_endpoints(self) -> ABoxPayload:
        """Ensure relation endpoints refer to individuals present in this payload."""
        person_ids = {person.person_id for person in self.persons}
        employee_ids = {employee.emp_id for employee in self.employees}
        contractor_ids = {contractor.contractor_id for contractor in self.contractors}
        department_ids = {department.dept_id for department in self.departments}
        policy_ids = {policy.policy_id for policy in self.access_policies}
        asset_ids = {
            asset.asset_id
            for asset in [*self.secure_assets, *self.digital_assets, *self.physical_assets]
        }

        for employee in self.employees:
            self._validate_optional_reference(employee.member_of_dept_id, department_ids, "department")
        for contractor in self.contractors:
            self._validate_optional_reference(contractor.member_of_dept_id, department_ids, "department")
        for person in self.persons:
            self._validate_optional_reference(person.member_of_dept_id, department_ids, "department")
        for policy in self.access_policies:
            self._validate_optional_reference(policy.owner_department_dept_id, department_ids, "department")
        for asset in [*self.secure_assets, *self.digital_assets, *self.physical_assets]:
            self._validate_optional_reference(asset.assigned_policy_id, policy_ids, "access policy")
            self._validate_optional_reference(asset.managed_by_emp_id, employee_ids, "employee")

        for relation in self.relations:
            self._validate_relation_endpoint_ids(
                relation,
                person_ids=person_ids,
                employee_ids=employee_ids,
                contractor_ids=contractor_ids,
                department_ids=department_ids,
                policy_ids=policy_ids,
                asset_ids=asset_ids,
            )
        return self

    @staticmethod
    def _validate_optional_reference(value: str | None, known_ids: set[str], label: str) -> None:
        if value is not None and value not in known_ids:
            raise ValueError(f"unknown {label}: {value}")

    @classmethod
    def _validate_relation_endpoint_ids(
        cls,
        relation: ExtractedRelation,
        *,
        person_ids: set[str],
        employee_ids: set[str],
        contractor_ids: set[str],
        department_ids: set[str],
        policy_ids: set[str],
        asset_ids: set[str],
    ) -> None:
        cls._validate_optional_reference(relation.subject_person_id, person_ids, "person")
        cls._validate_optional_reference(relation.subject_emp_id, employee_ids, "employee")
        cls._validate_optional_reference(relation.subject_contractor_id, contractor_ids, "contractor")
        cls._validate_optional_reference(relation.subject_asset_id, asset_ids, "secure asset")
        cls._validate_optional_reference(relation.subject_policy_id, policy_ids, "access policy")
        cls._validate_optional_reference(relation.object_department_id, department_ids, "department")
        cls._validate_optional_reference(relation.object_asset_id, asset_ids, "secure asset")
        cls._validate_optional_reference(relation.object_policy_id, policy_ids, "access policy")
        cls._validate_optional_reference(relation.object_emp_id, employee_ids, "employee")
