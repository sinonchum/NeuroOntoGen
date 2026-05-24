from neuro_onto_gen.core.owl_reasoner import (
    OwlReasonerEngine,
    OwlReasoningReport,
    build_owl_repair_diagnostic,
)
from neuro_onto_gen.core.repair import LlmTurtleRepairer, OwlRepairController

INCONSISTENT_TURTLE = """
@prefix ex: <http://example.org/owl-test/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
ex:Person a owl:Class .
ex:Machine a owl:Class .
ex:Person owl:disjointWith ex:Machine .
ex:alice a ex:Person, ex:Machine .
"""


class CapturingProvider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


class FixedRepairer:
    def __init__(self, repaired_turtle: str) -> None:
        self.repaired_turtle = repaired_turtle
        self.diagnostics_seen: list[object] = []

    def repair(self, turtle: str, violations: list[object], attempt_number: int) -> str:
        self.diagnostics_seen.extend(violations)
        assert attempt_number == 1
        assert "ex:alice" in turtle
        return self.repaired_turtle


def test_builds_structured_owl_inconsistency_diagnostic_for_repair_prompt() -> None:
    report = OwlReasoningReport(
        available=True,
        consistent=False,
        engine=OwlReasonerEngine.PELLET,
        message="Ontology is inconsistent: disjoint classes Person and Machine share individual alice",
    )

    diagnostic = build_owl_repair_diagnostic(INCONSISTENT_TURTLE, report)

    assert diagnostic.focus_node == "<ontology>"
    assert diagnostic.result_path == "owl:consistency"
    assert diagnostic.source_constraint_component == "OWLConsistencyConstraintComponent"
    assert diagnostic.severity == "Violation"
    assert "disjoint classes" in diagnostic.message
    assert diagnostic.diagnostic_type == "owl_inconsistency"


def test_llm_repair_prompt_accepts_owl_diagnostics_not_only_shacl_violations() -> None:
    provider = CapturingProvider("@prefix ex: <http://example.org/owl-test/> .\nex:alice a ex:Person .")
    repairer = LlmTurtleRepairer(provider=provider)
    diagnostic = build_owl_repair_diagnostic(
        INCONSISTENT_TURTLE,
        OwlReasoningReport(True, False, OwlReasonerEngine.PELLET, "disjoint classes Person/Machine"),
    )

    repaired = repairer.repair(INCONSISTENT_TURTLE, [diagnostic], attempt_number=1)

    assert "ex:alice a ex:Person" in repaired
    prompt = provider.prompts[0]
    assert "OWLConsistencyConstraintComponent" in prompt
    assert "diagnostic_type=owl_inconsistency" in prompt
    assert "disjoint classes Person/Machine" in prompt


def test_owl_repair_controller_reasons_repairs_and_revalidates_until_consistent() -> None:
    repaired_turtle = "@prefix ex: <http://example.org/owl-test/> .\nex:alice a ex:Person ."
    reports = [
        OwlReasoningReport(True, False, OwlReasonerEngine.PELLET, "disjoint classes conflict"),
        OwlReasoningReport(True, True, OwlReasonerEngine.PELLET, "Ontology is consistent."),
    ]

    def fake_reasoner(turtle: str) -> OwlReasoningReport:
        assert turtle
        return reports.pop(0)

    repairer = FixedRepairer(repaired_turtle)
    controller = OwlRepairController(reasoner=fake_reasoner, repairer=repairer, max_attempts=2)

    result = controller.repair_until_consistent(INCONSISTENT_TURTLE)

    assert result.succeeded is True
    assert result.final_turtle == repaired_turtle
    assert result.final_report.consistent is True
    assert len(result.attempts) == 1
    assert repairer.diagnostics_seen[0].diagnostic_type == "owl_inconsistency"
