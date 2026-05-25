import json
import subprocess
import sys
from pathlib import Path


def test_quick_benchmark_outputs_json_summary() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "benchmarks/run_benchmark.py",
            "--dataset",
            "examples/company",
            "--quick",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["dataset"] == "examples/company"
    assert summary["mode"] == "quick"
    assert summary["cases_total"] == 2
    assert summary["shacl_conformance_rate"] == 0.5
    assert summary["exact_match_score"] == 0.5
    assert 0.0 < summary["fuzzy_token_f1"] < 1.0
    assert summary["prompt_stability_score"] == 1.0
    assert summary["prompt_stability"]["variant_count"] == 2
    assert summary["prompt_stability"]["exact_graph_stability"] == 1.0
    assert summary["schema_discovery"]["term_count"] > 0
    assert summary["schema_discovery"]["cluster_count"] > 0
    assert summary["schema_discovery"]["draft_schema"]["annotations"]["generation_status"] == (
        "schema_discovery_draft_requires_human_review"
    )
    assert summary["cases"]["valid_abox.ttl"]["conforms"] is True
    assert summary["cases"]["invalid_abox.ttl"]["conforms"] is False
    assert "requiredClearance" in summary["cases"]["invalid_abox.ttl"]["report_text"]


def test_quick_benchmark_can_write_markdown_summary(tmp_path: Path) -> None:
    output_markdown = tmp_path / "summary.md"

    result = subprocess.run(
        [
            sys.executable,
            "benchmarks/run_benchmark.py",
            "--dataset",
            "examples/company",
            "--quick",
            "--output-markdown",
            str(output_markdown),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    markdown = output_markdown.read_text(encoding="utf-8")
    assert "# NeuroOntoGen benchmark summary" in markdown
    assert "SHACL conformance rate: 0.5" in markdown
    assert "Exact match score: 0.5" in markdown
    assert "Fuzzy token F1:" in markdown
    assert "Prompt stability score: 1.0" in markdown
    assert "Prompt variants: 2" in markdown
    assert "Schema discovery clusters:" in markdown
    assert "invalid_abox.ttl" in markdown
