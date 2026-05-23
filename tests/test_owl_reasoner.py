from pathlib import Path

from typer.testing import CliRunner

from neuro_onto_gen.cli import app
from neuro_onto_gen.core.owl_reasoner import (
    OwlReasonerEngine,
    OwlReasonerUnavailable,
    check_owl_reasoner_available,
    reason_owl_turtle,
)

DISJOINT_CONFLICT_TURTLE = """
@prefix ex: <http://example.org/owl-test/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

ex:Person a owl:Class .
ex:Machine a owl:Class .
ex:Person owl:disjointWith ex:Machine .
ex:alice a ex:Person, ex:Machine .
"""


def test_owl_reasoner_dependency_status_has_clear_install_hint() -> None:
    status = check_owl_reasoner_available()

    assert status.engine is OwlReasonerEngine.PELLET
    assert isinstance(status.available, bool)
    assert "pip install -e '.[owl]'" in status.install_hint
    if not status.available:
        assert status.reason


def test_owl_reasoner_reports_clear_unavailable_error_when_optional_deps_missing() -> None:
    status = check_owl_reasoner_available()
    if status.available:
        return

    try:
        reason_owl_turtle(DISJOINT_CONFLICT_TURTLE)
    except OwlReasonerUnavailable as exc:
        assert status.reason in str(exc)
        assert "pip install -e '.[owl]'" in str(exc)
    else:
        raise AssertionError("reason_owl_turtle should fail clearly when optional deps are missing")


def test_cli_reason_owl_reports_unavailable_optional_dependency(tmp_path: Path) -> None:
    status = check_owl_reasoner_available()
    if status.available:
        return

    turtle_path = tmp_path / "conflict.ttl"
    turtle_path.write_text(DISJOINT_CONFLICT_TURTLE, encoding="utf-8")

    result = CliRunner().invoke(app, ["reason-owl", str(turtle_path)])

    assert result.exit_code == 2
    assert "available: false" in result.output
    assert "pip install -e '.[owl]'" in result.output


def test_owl_reasoner_detects_disjoint_class_conflict_when_available() -> None:
    status = check_owl_reasoner_available()
    if not status.available:
        return

    report = reason_owl_turtle(DISJOINT_CONFLICT_TURTLE)

    assert report.available is True
    assert report.consistent is False
    assert report.engine is OwlReasonerEngine.PELLET
    assert "inconsistent" in report.message.lower()
