import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from neuro_onto_gen.core.extraction import (
    JsonExtractionAdapter,
    PromptedExtractionAdapter,
    parse_abox_payload,
)
from neuro_onto_gen.core.serializer import serialize_abox_to_turtle
from neuro_onto_gen.core.validation import validate_abox_turtle
from neuro_onto_gen.schema.compiler import compile_schema


def test_parse_abox_payload_accepts_raw_extraction_dict() -> None:
    payload = parse_abox_payload(
        {
            "employees": [{"emp_id": "E-001", "has_access_level": 3}],
            "secure_assets": [{"asset_id": "VPN", "required_clearance": 2}],
            "relations": [
                {
                    "subject_emp_id": "E-001",
                    "predicate": "operates",
                    "object_asset_id": "VPN",
                }
            ],
        }
    )

    assert payload.employees[0].emp_id == "E-001"
    assert payload.secure_assets[0].asset_id == "VPN"
    assert payload.relations[0].predicate == "operates"


def test_parse_abox_payload_accepts_raw_extraction_json_string() -> None:
    raw_json = json.dumps(
        {
            "employees": [{"emp_id": "E-001", "has_access_level": 3}],
            "secure_assets": [{"asset_id": "VPN", "required_clearance": 2}],
            "relations": [
                {
                    "subject_emp_id": "E-001",
                    "predicate": "operates",
                    "object_asset_id": "VPN",
                }
            ],
        }
    )

    payload = parse_abox_payload(raw_json)

    assert payload.employees[0].has_access_level == 3


def test_parse_abox_payload_rejects_unknown_relation_endpoint() -> None:
    with pytest.raises(ValidationError, match="unknown secure asset"):
        parse_abox_payload(
            {
                "employees": [{"emp_id": "E-001", "has_access_level": 3}],
                "secure_assets": [],
                "relations": [
                    {
                        "subject_emp_id": "E-001",
                        "predicate": "operates",
                        "object_asset_id": "VPN",
                    }
                ],
            }
        )


def test_json_extraction_adapter_normalizes_output_into_validated_abox() -> None:
    adapter = JsonExtractionAdapter(
        raw_output={
            "employees": [{"emp_id": "E-001", "has_access_level": 3}],
            "secure_assets": [{"asset_id": "VPN", "required_clearance": 2}],
            "relations": [
                {
                    "subject_emp_id": "E-001",
                    "predicate": "operates",
                    "object_asset_id": "VPN",
                }
            ],
        }
    )

    payload = adapter.extract("Employee E-001 operates VPN.")

    assert payload.employees[0].emp_id == "E-001"


class RecordingProvider:
    def __init__(self, raw_output: str) -> None:
        self.raw_output = raw_output
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.raw_output


def test_prompted_extraction_adapter_builds_prompt_and_normalizes_provider_output() -> None:
    provider = RecordingProvider(
        json.dumps(
            {
                "employees": [{"emp_id": "E-001", "has_access_level": 3}],
                "secure_assets": [{"asset_id": "VPN", "required_clearance": 2}],
                "relations": [
                    {
                        "subject_emp_id": "E-001",
                        "predicate": "operates",
                        "object_asset_id": "VPN",
                    }
                ],
            }
        )
    )
    adapter = PromptedExtractionAdapter(provider=provider)

    payload = adapter.extract("Employee E-001 operates secure asset VPN.")

    assert payload.employees[0].emp_id == "E-001"
    assert payload.secure_assets[0].asset_id == "VPN"
    assert len(provider.prompts) == 1
    assert "# NeuroOntoGen Extraction Prompt" in provider.prompts[0]
    assert "Employee E-001 operates secure asset VPN." in provider.prompts[0]


def test_prompted_extraction_adapter_rejects_invalid_provider_output() -> None:
    provider = RecordingProvider(
        json.dumps(
            {
                "employees": [{"emp_id": "E-001", "has_access_level": 3}],
                "secure_assets": [],
                "relations": [
                    {
                        "subject_emp_id": "E-001",
                        "predicate": "operates",
                        "object_asset_id": "VPN",
                    }
                ],
            }
        )
    )
    adapter = PromptedExtractionAdapter(provider=provider)

    with pytest.raises(ValidationError, match="unknown secure asset"):
        adapter.extract("Employee E-001 operates secure asset VPN.")


def test_raw_extraction_json_to_shacl_validated_turtle(tmp_path: Path) -> None:
    artifacts = compile_schema(Path("tests/fixtures/company_schema.yaml"), tmp_path)
    payload = parse_abox_payload(
        {
            "employees": [{"emp_id": "E-001", "has_access_level": 3}],
            "secure_assets": [{"asset_id": "VPN", "required_clearance": 2}],
            "relations": [
                {
                    "subject_emp_id": "E-001",
                    "predicate": "operates",
                    "object_asset_id": "VPN",
                }
            ],
        }
    )

    turtle = serialize_abox_to_turtle(payload)
    report = validate_abox_turtle(turtle, artifacts["shacl"])

    assert report.conforms is True
