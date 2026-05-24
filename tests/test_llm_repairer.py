from pathlib import Path

from neuro_onto_gen.core.repair import LlmTurtleRepairer
from neuro_onto_gen.core.validation import parse_shacl_violations, validate_abox_turtle
from neuro_onto_gen.schema.compiler import compile_schema

INVALID_TURTLE = """
    @prefix ex: <http://example.org/company/> .

    <http://example.org/company/asset/VPN> a ex:SecureAsset ;
        ex:assetId "VPN" .
"""

REPAIRED_TURTLE = """
    @prefix ex: <http://example.org/company/> .

    <http://example.org/company/asset/VPN> a ex:SecureAsset ;
        ex:assetId "VPN" ;
        ex:requiredClearance 2 .
"""


class RecordingProvider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def test_llm_turtle_repairer_builds_prompt_from_structured_shacl_violations(tmp_path: Path) -> None:
    artifacts = compile_schema(Path("tests/fixtures/company_schema.yaml"), tmp_path)
    report = validate_abox_turtle(INVALID_TURTLE, artifacts["shacl"])
    violations = parse_shacl_violations(report)
    provider = RecordingProvider(REPAIRED_TURTLE)
    repairer = LlmTurtleRepairer(provider=provider, ontology_name="CompanyAccess")

    repaired = repairer.repair(INVALID_TURTLE, violations, attempt_number=1)

    assert repaired == REPAIRED_TURTLE.strip()
    assert len(provider.prompts) == 1
    prompt = provider.prompts[0]
    assert "# NeuroOntoGen Turtle Repair Prompt" in prompt
    assert "Ontology: CompanyAccess" in prompt
    assert "Attempt: 1" in prompt
    assert "## Current Turtle" in prompt
    assert "ex:assetId \"VPN\"" in prompt
    assert "## SHACL Violations" in prompt
    assert "http://example.org/company/asset/VPN" in prompt
    assert "http://example.org/company/requiredClearance" in prompt
    assert "MinCountConstraintComponent" in prompt
    assert "Return only repaired Turtle" in prompt


def test_llm_turtle_repairer_strips_markdown_turtle_fence() -> None:
    provider = RecordingProvider("```turtle\n@prefix ex: <http://example.org/company/> .\n```\n")
    repairer = LlmTurtleRepairer(provider=provider)

    repaired = repairer.repair("bad", [], attempt_number=2)

    assert repaired == "@prefix ex: <http://example.org/company/> ."
