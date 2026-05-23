"""Bounded self-repair loop for non-conforming ABox Turtle graphs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable

from neuro_onto_gen.core.validation import (
    ShaclValidationReport,
    ShaclViolation,
    parse_shacl_violations,
    validate_abox_turtle,
)


@runtime_checkable
class RepairerProtocol(Protocol):
    """Protocol for components that propose a repaired Turtle graph."""

    def repair(self, turtle: str, violations: list[ShaclViolation], attempt_number: int) -> str:
        """Return a repaired Turtle graph candidate."""
        ...


@dataclass(frozen=True)
class RepairAttempt:
    """One repair attempt and the violations that motivated it."""

    attempt_number: int
    input_turtle: str
    output_turtle: str
    violations: list[ShaclViolation]


class RepairFailureReason(str, Enum):
    """Machine-readable reasons for bounded repair failure."""

    MAX_ATTEMPTS_EXCEEDED = "max_attempts_exceeded"
    REPAIRER_RAISED_EXCEPTION = "repairer_raised_exception"


@dataclass(frozen=True)
class RepairResult:
    """Final result of a bounded repair loop."""

    succeeded: bool
    final_turtle: str
    final_report: ShaclValidationReport
    attempts: list[RepairAttempt]
    failure_reason: RepairFailureReason | None = None
    error_message: str | None = None


class RepairFailure(RuntimeError):
    """Raised when bounded repair cannot produce a conforming graph."""

    def __init__(self, result: RepairResult) -> None:
        super().__init__(f"repair failed after {len(result.attempts)} attempt(s)")
        self.result = result


@dataclass(frozen=True)
class RepairController:
    """Validate, repair, and revalidate a Turtle graph with a hard retry limit."""

    shacl_path: Path
    repairer: RepairerProtocol
    max_attempts: int = 2

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

    def repair_until_valid(self, turtle: str) -> RepairResult:
        """Run bounded repair until the graph conforms or the limit is reached."""
        current_turtle = turtle
        attempts: list[RepairAttempt] = []

        current_report = validate_abox_turtle(current_turtle, self.shacl_path)
        if current_report.conforms:
            return RepairResult(
                succeeded=True,
                final_turtle=current_turtle,
                final_report=current_report,
                attempts=attempts,
            )

        for attempt_number in range(1, self.max_attempts + 1):
            violations = parse_shacl_violations(current_report)
            try:
                repaired_turtle = self.repairer.repair(current_turtle, violations, attempt_number)
            except Exception as exc:
                result = RepairResult(
                    succeeded=False,
                    final_turtle=current_turtle,
                    final_report=current_report,
                    attempts=attempts,
                    failure_reason=RepairFailureReason.REPAIRER_RAISED_EXCEPTION,
                    error_message=str(exc),
                )
                raise RepairFailure(result) from exc
            attempts.append(
                RepairAttempt(
                    attempt_number=attempt_number,
                    input_turtle=current_turtle,
                    output_turtle=repaired_turtle,
                    violations=violations,
                )
            )
            current_turtle = repaired_turtle
            current_report = validate_abox_turtle(current_turtle, self.shacl_path)
            if current_report.conforms:
                return RepairResult(
                    succeeded=True,
                    final_turtle=current_turtle,
                    final_report=current_report,
                    attempts=attempts,
                )

        result = RepairResult(
            succeeded=False,
            final_turtle=current_turtle,
            final_report=current_report,
            attempts=attempts,
            failure_reason=RepairFailureReason.MAX_ATTEMPTS_EXCEEDED,
        )
        raise RepairFailure(result)
