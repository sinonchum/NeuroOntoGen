"""Schema-constrained prompt construction for extraction adapters."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Sequence

from pydantic import BaseModel

from neuro_onto_gen.core.models import ABoxPayload

PROMPT_VERSION = "nog.prompt.v1"


@dataclass(frozen=True)
class PromptSection:
    """A named section in a deterministic extraction prompt."""

    title: str
    body: str

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("prompt section title must not be empty")
        if not self.body.strip():
            raise ValueError("prompt section body must not be empty")

    def render(self) -> str:
        """Render this section as Markdown."""
        return f"## {self.title}\n\n{self.body.strip()}"


@dataclass(frozen=True)
class ExtractionPrompt:
    """Versioned prompt artifact for schema-constrained ABox extraction."""

    ontology_name: str
    output_model_name: str
    sections: tuple[PromptSection, ...]
    version: str = PROMPT_VERSION

    def render(self) -> str:
        """Render a deterministic Markdown prompt for provider adapters."""
        header = "\n".join(
            (
                "# NeuroOntoGen Extraction Prompt",
                f"Prompt-Version: {self.version}",
                f"Ontology: {self.ontology_name}",
                f"Output-Model: {self.output_model_name}",
            )
        )
        rendered_sections = "\n\n".join(section.render() for section in self.sections)
        return f"{header}\n\n{rendered_sections}\n"


def build_extraction_prompt(
    *,
    ontology_name: str,
    source_text: str,
    output_model: type[BaseModel],
    allowed_entity_types: Sequence[str],
    allowed_relations: Sequence[str],
    normalization_rules: Sequence[str] = (),
) -> ExtractionPrompt:
    """Build a versioned prompt that constrains extraction to a typed schema.

    The rendered prompt is provider-neutral. It can be handed to an LLM adapter,
    saved as an artifact, or compared in prompt-stability tests.
    """
    if not ontology_name.strip():
        raise ValueError("ontology_name must not be empty")
    if not source_text.strip():
        raise ValueError("source_text must not be empty")
    if not allowed_entity_types:
        raise ValueError("allowed_entity_types must not be empty")
    if not allowed_relations:
        raise ValueError("allowed_relations must not be empty")

    sections = (
        PromptSection(
            title="Role",
            body=(
                "You are an ontology extraction component. Propose ABox facts from "
                "the source text, but do not validate yourself; NeuroOntoGen will "
                "validate the JSON with Pydantic, RDF, and SHACL."
            ),
        ),
        PromptSection(
            title="Context",
            body=(
                "Extract only facts that are explicitly supported by the source text. "
                "Do not invent entity types, relation predicates, or fields outside "
                "the output schema."
            ),
        ),
        PromptSection(
            title="Normalization Rules",
            body=_render_bullets(
                normalization_rules
                or (
                    "Return JSON only, with no Markdown fence or commentary.",
                    "Use stable source identifiers when they are present.",
                    "Omit unsupported facts instead of guessing missing values.",
                )
            ),
        ),
        PromptSection(
            title="Ontology Specification",
            body=(
                "Allowed entity types:\n"
                f"{_render_bullets(allowed_entity_types)}\n\n"
                "Allowed relations:\n"
                f"{_render_bullets(allowed_relations)}"
            ),
        ),
        PromptSection(title="Source Text", body=source_text.strip()),
        PromptSection(title="Output Schema", body=_render_output_schema(output_model)),
    )
    return ExtractionPrompt(
        ontology_name=ontology_name.strip(),
        output_model_name=output_model.__name__,
        sections=sections,
    )


def build_company_access_prompt(source_text: str) -> ExtractionPrompt:
    """Build the default CompanyAccess ABox extraction prompt."""
    return build_extraction_prompt(
        ontology_name="CompanyAccess",
        source_text=source_text,
        output_model=ABoxPayload,
        allowed_entity_types=(
            "Person",
            "Employee",
            "Contractor",
            "Department",
            "SecureAsset",
            "DigitalAsset",
            "PhysicalAsset",
            "AccessPolicy",
        ),
        allowed_relations=("memberOf", "manages", "operates", "assignedPolicy", "managedBy", "ownerDepartment"),
        normalization_rules=(
            "Return JSON only, with no Markdown fence or commentary.",
            "Use stable identifiers: person_id, emp_id, contractor_id, dept_id, asset_id, and policy_id.",
            "Use snake_case JSON fields from the output schema, including member_of_dept_id, assigned_policy_id, managed_by_emp_id, and owner_department_dept_id.",
            "Use relation endpoint fields that match the predicate, such as subject_emp_id/object_asset_id for operates or subject_asset_id/object_policy_id for assignedPolicy.",
            "Omit unsupported facts instead of guessing missing values.",
        ),
    )


def _render_output_schema(output_model: type[BaseModel]) -> str:
    schema = output_model.model_json_schema()
    return json.dumps(schema, indent=2, sort_keys=True)


def _render_bullets(items: Sequence[str]) -> str:
    cleaned_items = [item.strip() for item in items if item.strip()]
    if not cleaned_items:
        raise ValueError("bullet list must contain at least one non-empty item")
    return "\n".join(f"- {item}" for item in cleaned_items)
