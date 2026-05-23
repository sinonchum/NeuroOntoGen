"""Core extraction models for NeuroOntoGen ABox payloads."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExtractedEmployee(BaseModel):
    """Employee individual extracted from unstructured input."""

    model_config = ConfigDict(frozen=True)

    emp_id: str = Field(min_length=1)
    has_access_level: int = Field(ge=0)


class ExtractedSecureAsset(BaseModel):
    """Secure asset individual extracted from unstructured input."""

    model_config = ConfigDict(frozen=True)

    asset_id: str = Field(min_length=1)
    required_clearance: int = Field(ge=0)


class ExtractedRelation(BaseModel):
    """Relation between extracted company ontology individuals."""

    model_config = ConfigDict(frozen=True)

    subject_emp_id: str = Field(min_length=1)
    predicate: Literal["operates"]
    object_asset_id: str = Field(min_length=1)


class ABoxPayload(BaseModel):
    """Validated set of extracted individuals and object-property assertions."""

    employees: list[ExtractedEmployee] = Field(default_factory=list)
    secure_assets: list[ExtractedSecureAsset] = Field(default_factory=list)
    relations: list[ExtractedRelation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_relation_endpoints(self) -> ABoxPayload:
        """Ensure relation endpoints refer to individuals present in this payload."""
        employee_ids = {employee.emp_id for employee in self.employees}
        asset_ids = {asset.asset_id for asset in self.secure_assets}

        for relation in self.relations:
            if relation.subject_emp_id not in employee_ids:
                raise ValueError(f"relation references unknown employee: {relation.subject_emp_id}")
            if relation.object_asset_id not in asset_ids:
                raise ValueError(f"relation references unknown secure asset: {relation.object_asset_id}")
        return self
