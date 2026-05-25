from pathlib import Path

from neuro_onto_gen.core.prompting import (
    ExtractionPrompt,
    PromptSection,
    build_company_access_prompt,
    build_extraction_prompt,
    derive_prompt_constraints_from_linkml,
)
from neuro_onto_gen.core.models import ABoxPayload


def test_build_extraction_prompt_contains_ordered_schema_sections():
    prompt = build_extraction_prompt(
        ontology_name="CompanyAccess",
        source_text="Alice, employee E-001, can operate the VPN appliance.",
        output_model=ABoxPayload,
        allowed_entity_types=("Employee", "SecureAsset"),
        allowed_relations=("operates",),
        normalization_rules=("Use source-stable identifiers only.",),
    )

    section_titles = [section.title for section in prompt.sections]

    assert section_titles == [
        "Role",
        "Context",
        "Normalization Rules",
        "Ontology Specification",
        "Source Text",
        "Output Schema",
    ]
    assert prompt.version == "nog.prompt.v1"
    assert prompt.output_model_name == "ABoxPayload"


def test_rendered_prompt_is_deterministic_and_schema_constrained():
    prompt = build_extraction_prompt(
        ontology_name="CompanyAccess",
        source_text="Employee E-001 operates asset VPN.",
        output_model=ABoxPayload,
        allowed_entity_types=("Employee", "SecureAsset"),
        allowed_relations=("operates",),
        normalization_rules=("Return JSON only.",),
    )

    rendered_once = prompt.render()
    rendered_twice = prompt.render()

    assert rendered_once == rendered_twice
    assert "# NeuroOntoGen Extraction Prompt" in rendered_once
    assert "Prompt-Version: nog.prompt.v1" in rendered_once
    assert "Ontology: CompanyAccess" in rendered_once
    assert "Allowed entity types:" in rendered_once
    assert "- Employee" in rendered_once
    assert "- SecureAsset" in rendered_once
    assert "Allowed relations:" in rendered_once
    assert "- operates" in rendered_once
    assert "Source Text" in rendered_once
    assert "Employee E-001 operates asset VPN." in rendered_once
    assert '"employees"' in rendered_once
    assert '"secure_assets"' in rendered_once
    assert '"relations"' in rendered_once
    assert "Do not invent entity types, relation predicates, or fields" in rendered_once


def test_prompt_constraints_are_derived_from_linkml_company_schema() -> None:
    constraints = derive_prompt_constraints_from_linkml(Path("schemas/company_schema.yaml"))

    assert constraints.allowed_entity_types == (
        "Person",
        "Employee",
        "Contractor",
        "Department",
        "SecureAsset",
        "DigitalAsset",
        "PhysicalAsset",
        "AccessPolicy",
    )
    assert "CompanyEntity" not in constraints.allowed_entity_types
    assert constraints.allowed_relations == (
        "memberOf",
        "manages",
        "operates",
        "assignedPolicy",
        "managedBy",
        "ownerDepartment",
    )
    assert "entityId" not in constraints.allowed_relations
    assert "hasAccessLevel" not in constraints.allowed_relations


def test_build_company_access_prompt_uses_project_default_contract():
    prompt = build_company_access_prompt("E-007 operates vault door VAULT-1.")

    rendered = prompt.render()

    assert isinstance(prompt, ExtractionPrompt)
    assert "Ontology: CompanyAccess" in rendered
    assert "Employee" in rendered
    assert "SecureAsset" in rendered
    assert "operates" in rendered
    assert "has_access_level" in rendered
    assert "required_clearance" in rendered


def test_prompt_section_rejects_empty_title_and_body():
    try:
        PromptSection(title="", body="content")
    except ValueError as exc:
        assert "title" in str(exc)
    else:
        raise AssertionError("empty prompt section title should fail")

    try:
        PromptSection(title="Role", body="")
    except ValueError as exc:
        assert "body" in str(exc)
    else:
        raise AssertionError("empty prompt section body should fail")
