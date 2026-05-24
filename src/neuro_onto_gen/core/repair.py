"""Bounded self-repair loop for non-conforming ABox Turtle graphs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence, runtime_checkable

from neuro_onto_gen.core.owl_reasoner import (
    OwlReasoningReport,
    build_owl_repair_diagnostic,
    reason_owl_turtle,
)
from neuro_onto_gen.core.validation import (
    ShaclValidationReport,
    parse_shacl_violations,
    validate_abox_turtle,
)


@runtime_checkable
class RepairCompletionProviderProtocol(Protocol):
    """Protocol for LLM clients used by production repairers."""

    def complete(self, prompt: str) -> str:
        """Return repaired Turtle text for a rendered repair prompt."""
        ...


@dataclass(frozen=True)
class LlmTurtleRepairer:
    """Production repairer that asks an LLM to fix Turtle from SHACL diagnostics."""

    provider: RepairCompletionProviderProtocol
    ontology_name: str = "CompanyAccess"

    def repair(self, turtle: str, violations: Sequence[Any], attempt_number: int) -> str:
        """Render a repair prompt, call the provider, and normalize fenced output."""
        prompt = self._build_prompt(turtle, violations, attempt_number)
        return _strip_markdown_turtle_fence(self.provider.complete(prompt))

    def _build_prompt(
        self,
        turtle: str,
        violations: Sequence[Any],
        attempt_number: int,
    ) -> str:
        violation_lines = []
        for index, violation in enumerate(violations, start=1):
            fields = []
            diagnostic_type = getattr(violation, "diagnostic_type", None)
            if diagnostic_type is not None:
                fields.append(f"diagnostic_type={diagnostic_type}")
            fields.extend(
                [
                    f"focus_node={violation.focus_node}",
                    f"result_path={violation.result_path or '<none>'}",
                    f"source_constraint_component={violation.source_constraint_component}",
                    f"severity={violation.severity}",
                    f"message={violation.message}",
                ]
            )
            violation_lines.append(f"{index}. " + "; ".join(fields))
        rendered_violations = "\n".join(violation_lines) if violation_lines else "No structured violations supplied."
        return (
            "# NeuroOntoGen Turtle Repair Prompt\n"
            f"Ontology: {self.ontology_name}\n"
            f"Attempt: {attempt_number}\n\n"
            "## Task\n\n"
            "Repair the RDF/Turtle data graph so it satisfies the SHACL diagnostics. "
            "Preserve supported facts and do not invent unrelated entities. "
            "Return only repaired Turtle, with no Markdown fence or commentary.\n\n"
            "## Current Turtle\n\n"
            f"{turtle.strip()}\n\n"
            "## SHACL Violations\n\n"
            f"{rendered_violations}\n\n"
            "## Output Contract\n\n"
            "Return only repaired Turtle."
        )


def _strip_markdown_turtle_fence(text: str) -> str:
    """Strip a single Markdown code fence when providers ignore the prompt contract."""
    stripped = text.strip()
    match = re.fullmatch(r"```(?:turtle|ttl)?\s*\n(?P<body>.*?)\n?```", stripped, flags=re.DOTALL)
    if match is None:
        return stripped
    return match.group("body").strip()


@runtime_checkable
class RepairerProtocol(Protocol):
    """Protocol for components that propose a repaired Turtle graph."""

    def repair(self, turtle: str, violations: Sequence[Any], attempt_number: int) -> str:
        """Return a repaired Turtle graph candidate."""
        ...


@dataclass(frozen=True)
class RepairAttempt:
    """One repair attempt and the violations that motivated it."""

    attempt_number: int
    input_turtle: str
    output_turtle: str
    violations: list[Any]


@dataclass(frozen=True)
class OwlRepairResult:
    """Final result of a bounded OWL consistency repair loop."""

    succeeded: bool
    final_turtle: str
    final_report: OwlReasoningReport
    attempts: list[RepairAttempt]
    failure_reason: RepairFailureReason | None = None
    error_message: str | None = None


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
    """Raised when bounded SHACL repair cannot produce a conforming graph."""

    def __init__(self, result: RepairResult) -> None:
        super().__init__(f"repair failed after {len(result.attempts)} attempt(s)")
        self.result = result


class OwlRepairFailure(RuntimeError):
    """Raised when bounded OWL repair cannot produce a consistent ontology."""

    def __init__(self, result: OwlRepairResult) -> None:
        super().__init__(f"OWL repair failed after {len(result.attempts)} attempt(s)")
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


@dataclass(frozen=True)
class OwlRepairController:
    """Reason, repair, and re-reason an OWL/Turtle ontology with a hard retry limit."""

    repairer: RepairerProtocol
    reasoner: Callable[[str], OwlReasoningReport] = reason_owl_turtle
    max_attempts: int = 2

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

    def repair_until_consistent(self, turtle: str) -> OwlRepairResult:
        """Run bounded OWL repair until the ontology is consistent or the limit is reached."""
        current_turtle = turtle
        attempts: list[RepairAttempt] = []
        current_report = self.reasoner(current_turtle)
        if current_report.consistent is True:
            return OwlRepairResult(
                succeeded=True,
                final_turtle=current_turtle,
                final_report=current_report,
                attempts=attempts,
            )
        if current_report.consistent is not False:
            result = OwlRepairResult(
                succeeded=False,
                final_turtle=current_turtle,
                final_report=current_report,
                attempts=attempts,
                failure_reason=RepairFailureReason.REPAIRER_RAISED_EXCEPTION,
                error_message="OWL reasoner did not return a consistency verdict.",
            )
            raise OwlRepairFailure(result)

        for attempt_number in range(1, self.max_attempts + 1):
            diagnostic = build_owl_repair_diagnostic(current_turtle, current_report)
            try:
                repaired_turtle = self.repairer.repair(current_turtle, [diagnostic], attempt_number)
            except Exception as exc:
                result = OwlRepairResult(
                    succeeded=False,
                    final_turtle=current_turtle,
                    final_report=current_report,
                    attempts=attempts,
                    failure_reason=RepairFailureReason.REPAIRER_RAISED_EXCEPTION,
                    error_message=str(exc),
                )
                raise OwlRepairFailure(result) from exc
            attempts.append(
                RepairAttempt(
                    attempt_number=attempt_number,
                    input_turtle=current_turtle,
                    output_turtle=repaired_turtle,
                    violations=[diagnostic],
                )
            )
            current_turtle = repaired_turtle
            current_report = self.reasoner(current_turtle)
            if current_report.consistent is True:
                return OwlRepairResult(
                    succeeded=True,
                    final_turtle=current_turtle,
                    final_report=current_report,
                    attempts=attempts,
                )

        result = OwlRepairResult(
            succeeded=False,
            final_turtle=current_turtle,
            final_report=current_report,
            attempts=attempts,
            failure_reason=RepairFailureReason.MAX_ATTEMPTS_EXCEEDED,
        )
        raise OwlRepairFailure(result)
