#!/usr/bin/env python
"""Run a small deterministic NeuroOntoGen benchmark smoke evaluation."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from neuro_onto_gen.core.validation import validate_abox_turtle
from neuro_onto_gen.evaluation.metrics import shacl_conformance_rate
from neuro_onto_gen.evaluation.prompt_stability import PromptVariantOutput, evaluate_prompt_stability
from neuro_onto_gen.schema.compiler import compile_schema


CASE_FILES = ("valid_abox.ttl", "invalid_abox.ttl")


def run_quick_benchmark(dataset: Path) -> dict[str, Any]:
    """Run the quick company example benchmark and return a JSON-ready summary."""
    dataset = Path(dataset)
    with tempfile.TemporaryDirectory(prefix="neuro-onto-gen-benchmark-") as temporary_dir:
        artifacts = compile_schema(
            schema_path=Path("schemas/company_schema.yaml"),
            output_dir=Path(temporary_dir) / "schema",
        )

        cases: dict[str, dict[str, Any]] = {}
        conformance_results: list[bool] = []
        for case_file in CASE_FILES:
            turtle_path = dataset / case_file
            report = validate_abox_turtle(
                turtle=turtle_path.read_text(encoding="utf-8"),
                shacl_path=artifacts["shacl"],
            )
            conformance_results.append(report.conforms)
            cases[case_file] = {
                "conforms": report.conforms,
                "report_text": report.report_text,
            }

        prompt_stability = evaluate_prompt_stability(
            [
                PromptVariantOutput(
                    prompt_id="direct",
                    output_turtle=(dataset / "valid_abox.ttl").read_text(encoding="utf-8"),
                ),
                PromptVariantOutput(
                    prompt_id="schema_first",
                    output_turtle=(dataset / "valid_abox.ttl").read_text(encoding="utf-8"),
                ),
            ]
        )

    return {
        "dataset": str(dataset),
        "mode": "quick",
        "cases_total": len(cases),
        "shacl_conformance_rate": shacl_conformance_rate(conformance_results),
        "repair_success_rate": 0.0,
        "prompt_stability_score": prompt_stability.exact_graph_stability,
        "prompt_stability": prompt_stability.to_json_dict(),
        "cases": cases,
    }


def render_markdown_summary(summary: dict[str, Any]) -> str:
    """Render a compact Markdown benchmark summary."""
    lines = [
        "# NeuroOntoGen benchmark summary",
        "",
        f"Dataset: {summary['dataset']}",
        f"Mode: {summary['mode']}",
        f"Cases total: {summary['cases_total']}",
        f"SHACL conformance rate: {summary['shacl_conformance_rate']}",
        f"Repair success rate: {summary['repair_success_rate']}",
        f"Prompt stability score: {summary['prompt_stability_score']}",
        f"Prompt variants: {summary['prompt_stability']['variant_count']}",
        f"Prompt exact graph stability: {summary['prompt_stability']['exact_graph_stability']}",
        "",
        "## Cases",
    ]
    for case_name, case_summary in summary["cases"].items():
        lines.extend(
            [
                "",
                f"### {case_name}",
                "",
                f"- conforms: {str(case_summary['conforms']).lower()}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run NeuroOntoGen benchmark smoke checks.")
    parser.add_argument("--dataset", type=Path, required=True, help="Benchmark dataset directory.")
    parser.add_argument("--quick", action="store_true", help="Run the quick built-in smoke suite.")
    parser.add_argument(
        "--output-markdown",
        type=Path,
        help="Optional path for a Markdown summary.",
    )
    args = parser.parse_args()

    if not args.quick:
        parser.error("Only --quick mode is implemented in the current benchmark skeleton.")

    summary = run_quick_benchmark(args.dataset)
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(render_markdown_summary(summary), encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
