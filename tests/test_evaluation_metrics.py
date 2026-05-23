from neuro_onto_gen.evaluation.metrics import (
    exact_match,
    fuzzy_token_f1,
    prompt_stability_score,
    repair_success_rate,
    shacl_conformance_rate,
)


def test_exact_match_normalizes_surrounding_whitespace() -> None:
    assert exact_match("  VPN access approved  ", "VPN access approved") == 1.0
    assert exact_match("VPN access denied", "VPN access approved") == 0.0


def test_fuzzy_token_f1_uses_token_overlap() -> None:
    score = fuzzy_token_f1("employee operates vpn", "employee operates secure vpn")

    assert round(score, 3) == 0.857


def test_shacl_conformance_rate_counts_true_reports() -> None:
    assert shacl_conformance_rate([True, False, True]) == 2 / 3
    assert shacl_conformance_rate([]) == 0.0


def test_repair_success_rate_counts_successes_after_repair_attempts() -> None:
    assert repair_success_rate(successes=2, attempts=5) == 0.4
    assert repair_success_rate(successes=0, attempts=0) == 0.0


def test_prompt_stability_score_counts_outputs_matching_canonical_output() -> None:
    outputs = ["same graph", "same graph", "different graph", "same graph"]

    assert prompt_stability_score(outputs) == 0.75
    assert prompt_stability_score([]) == 0.0
