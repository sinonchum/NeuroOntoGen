import json
from pathlib import Path

import pytest

from neuro_onto_gen.evaluation.prompt_stability import (
    PromptVariantOutput,
    evaluate_prompt_stability,
    parse_turtle_triples,
)


BASE_TURTLE = """
@prefix ex: <http://example.org/company/> .

<http://example.org/company/employee/E-001> a ex:Employee ;
    ex:empId "E-001" ;
    ex:hasAccessLevel 3 .

<http://example.org/company/asset/VPN> a ex:SecureAsset ;
    ex:assetId "VPN" ;
    ex:requiredClearance 2 .

<http://example.org/company/employee/E-001> ex:operates <http://example.org/company/asset/VPN> .
"""

REORDERED_TURTLE = """
@prefix ex: <http://example.org/company/> .

<http://example.org/company/asset/VPN> ex:requiredClearance 2 ;
    a ex:SecureAsset ;
    ex:assetId "VPN" .

<http://example.org/company/employee/E-001> ex:operates <http://example.org/company/asset/VPN> ;
    ex:hasAccessLevel 3 ;
    a ex:Employee ;
    ex:empId "E-001" .
"""

MISSING_RELATION_TURTLE = """
@prefix ex: <http://example.org/company/> .

<http://example.org/company/employee/E-001> a ex:Employee ;
    ex:empId "E-001" ;
    ex:hasAccessLevel 3 .

<http://example.org/company/asset/VPN> a ex:SecureAsset ;
    ex:assetId "VPN" ;
    ex:requiredClearance 2 .
"""


def test_parse_turtle_triples_canonicalizes_serialization_order() -> None:
    assert parse_turtle_triples(BASE_TURTLE) == parse_turtle_triples(REORDERED_TURTLE)


def test_evaluate_prompt_stability_scores_triple_level_agreement() -> None:
    report = evaluate_prompt_stability(
        [
            PromptVariantOutput(prompt_id="direct", output_turtle=BASE_TURTLE),
            PromptVariantOutput(prompt_id="schema_first", output_turtle=REORDERED_TURTLE),
            PromptVariantOutput(prompt_id="minimal", output_turtle=MISSING_RELATION_TURTLE),
        ]
    )

    assert report.variant_count == 3
    assert report.valid_variant_count == 3
    assert report.canonical_triple_count == 7
    assert report.consensus_triple_count == 6
    assert report.exact_graph_stability == 2 / 3
    assert report.mean_jaccard_to_consensus == 1.0
    assert report.stable_triple_ratio == 6 / 7
    assert len(report.unstable_triples) == 1
    assert report.prompt_scores["minimal"].precision_to_canonical == 1.0
    assert report.prompt_scores["minimal"].recall_to_canonical == 6 / 7
    assert report.prompt_scores["minimal"].f1_to_canonical == pytest.approx(12 / 13)
    assert report.prompt_scores["minimal"].missing_from_consensus == []
    assert report.prompt_scores["minimal"].extra_vs_canonical == []
    assert report.prompt_scores["minimal"].jaccard_to_canonical == 6 / 7


def test_evaluate_prompt_stability_records_invalid_variant_without_crashing() -> None:
    report = evaluate_prompt_stability(
        [
            PromptVariantOutput(prompt_id="valid", output_turtle=BASE_TURTLE),
            PromptVariantOutput(prompt_id="broken", output_turtle="not valid turtle"),
        ]
    )

    assert report.variant_count == 2
    assert report.valid_variant_count == 1
    assert report.invalid_variants == ["broken"]
    assert report.prompt_scores["broken"].parse_error is not None
    assert report.prompt_scores["broken"].jaccard_to_canonical == 0.0


def test_evaluate_prompt_stability_can_load_jsonl_fixture(tmp_path: Path) -> None:
    fixture = tmp_path / "variants.jsonl"
    fixture.write_text(
        "\n".join(
            [
                json.dumps({"prompt_id": "direct", "output_turtle": BASE_TURTLE}),
                json.dumps({"prompt_id": "schema_first", "output_turtle": REORDERED_TURTLE}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = evaluate_prompt_stability.from_jsonl(fixture)

    assert report.variant_count == 2
    assert report.exact_graph_stability == 1.0
