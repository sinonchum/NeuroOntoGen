from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/ci.yml")


def test_github_actions_ci_workflow_exists() -> None:
    assert WORKFLOW_PATH.exists()


def test_ci_workflow_runs_core_quality_gates() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "actions/checkout" in workflow
    assert "actions/setup-python" in workflow
    assert "python -m pip install -e '.[dev]'" in workflow
    assert "python -m pytest -q" in workflow
    assert "ruff check ." in workflow


def test_ci_workflow_runs_cli_smoke_commands() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "neuro-onto-gen compile-schema" in workflow
    assert "examples/company/valid_abox.ttl" in workflow
    assert "examples/company/invalid_abox.ttl" in workflow
    assert "requiredClearance" in workflow


def test_ci_workflow_runs_benchmark_smoke_command() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "python benchmarks/run_benchmark.py --dataset examples/company --quick" in workflow
