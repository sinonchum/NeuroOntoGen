from pathlib import Path

from neuro_onto_gen.core.repair import RepairAttempt, RepairController, RepairFailure
from neuro_onto_gen.schema.compiler import compile_schema

INVALID_TURTLE = """
    @prefix ex: <http://example.org/company/> .

    <http://example.org/company/asset/VPN> a ex:SecureAsset ;
        ex:assetId "VPN" .
"""

VALID_TURTLE = """
    @prefix ex: <http://example.org/company/> .

    <http://example.org/company/asset/VPN> a ex:SecureAsset ;
        ex:assetId "VPN" ;
        ex:requiredClearance 2 .
"""


class RecordingRepairer:
    def __init__(self, repaired_turtle: str) -> None:
        self.repaired_turtle = repaired_turtle
        self.calls: list[tuple[str, int, int]] = []

    def repair(self, turtle: str, violations: list, attempt_number: int) -> str:
        self.calls.append((turtle, len(violations), attempt_number))
        return self.repaired_turtle


def test_repair_controller_succeeds_after_one_fake_repair(tmp_path: Path) -> None:
    artifacts = compile_schema(Path("tests/fixtures/company_schema.yaml"), tmp_path)
    repairer = RecordingRepairer(VALID_TURTLE)
    controller = RepairController(shacl_path=artifacts["shacl"], repairer=repairer, max_attempts=2)

    result = controller.repair_until_valid(INVALID_TURTLE)

    assert result.succeeded is True
    assert result.final_report.conforms is True
    assert result.final_turtle == VALID_TURTLE
    assert len(result.attempts) == 1
    assert isinstance(result.attempts[0], RepairAttempt)
    assert result.attempts[0].attempt_number == 1
    assert result.attempts[0].violations[0].result_path == "http://example.org/company/requiredClearance"
    assert repairer.calls == [(INVALID_TURTLE, 1, 1)]


def test_repair_controller_returns_immediately_when_initial_graph_conforms(tmp_path: Path) -> None:
    artifacts = compile_schema(Path("tests/fixtures/company_schema.yaml"), tmp_path)
    repairer = RecordingRepairer(INVALID_TURTLE)
    controller = RepairController(shacl_path=artifacts["shacl"], repairer=repairer, max_attempts=2)

    result = controller.repair_until_valid(VALID_TURTLE)

    assert result.succeeded is True
    assert result.final_report.conforms is True
    assert result.attempts == []
    assert repairer.calls == []


def test_repair_controller_raises_hard_failure_after_max_attempts(tmp_path: Path) -> None:
    artifacts = compile_schema(Path("tests/fixtures/company_schema.yaml"), tmp_path)
    repairer = RecordingRepairer(INVALID_TURTLE)
    controller = RepairController(shacl_path=artifacts["shacl"], repairer=repairer, max_attempts=2)

    try:
        controller.repair_until_valid(INVALID_TURTLE)
    except RepairFailure as exc:
        failure = exc.result
    else:
        raise AssertionError("repair controller should hard-fail after max attempts")

    assert failure.succeeded is False
    assert failure.final_report.conforms is False
    assert len(failure.attempts) == 2
    assert [attempt.attempt_number for attempt in failure.attempts] == [1, 2]
    assert [call[2] for call in repairer.calls] == [1, 2]
