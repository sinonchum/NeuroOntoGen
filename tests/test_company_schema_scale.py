from pathlib import Path

import yaml

from neuro_onto_gen.schema.compiler import compile_schema


def test_company_schema_contains_production_scale_entities_and_constraints() -> None:
    schema = yaml.safe_load(Path("schemas/company_schema.yaml").read_text(encoding="utf-8"))

    classes = schema["classes"]
    assert set(classes) >= {
        "CompanyEntity",
        "Person",
        "Employee",
        "Contractor",
        "Department",
        "SecureAsset",
        "DigitalAsset",
        "PhysicalAsset",
        "AccessPolicy",
    }
    assert classes["Employee"]["is_a"] == "Person"
    assert classes["Contractor"]["is_a"] == "Person"
    assert classes["DigitalAsset"]["is_a"] == "SecureAsset"
    assert classes["PhysicalAsset"]["is_a"] == "SecureAsset"

    slots = schema["slots"]
    assert slots["memberOf"]["domain"] == "Person"
    assert slots["memberOf"]["range"] == "Department"
    assert slots["assignedPolicy"]["domain"] == "SecureAsset"
    assert slots["assignedPolicy"]["range"] == "AccessPolicy"
    assert slots["managedBy"]["domain"] == "SecureAsset"
    assert slots["managedBy"]["range"] == "Employee"
    assert slots["operates"]["domain"] == "Person"
    assert slots["operates"]["range"] == "SecureAsset"
    assert classes["Employee"]["attributes"]["empId"]["required"] is True
    assert classes["AccessPolicy"]["attributes"]["policyId"]["required"] is True


def test_compiled_company_shacl_contains_domain_range_and_cardinality_shapes(tmp_path: Path) -> None:
    artifacts = compile_schema(Path("schemas/company_schema.yaml"), tmp_path)
    shacl_text = artifacts["shacl"].read_text(encoding="utf-8")

    assert "ex:Employee" in shacl_text
    assert "ex:Contractor" in shacl_text
    assert "ex:DigitalAsset" in shacl_text
    assert "ex:PhysicalAsset" in shacl_text
    assert "ex:AccessPolicy" in shacl_text
    assert "ex:memberOf" in shacl_text
    assert "ex:assignedPolicy" in shacl_text
    assert "ex:managedBy" in shacl_text
    assert "sh:class ex:Department" in shacl_text
    assert "sh:class ex:AccessPolicy" in shacl_text
    assert "sh:class ex:Employee" in shacl_text
    assert "sh:minCount 1" in shacl_text
