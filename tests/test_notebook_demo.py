import json
from pathlib import Path


NOTEBOOK_PATH = Path("notebooks/end_to_end_demo.ipynb")


def _load_notebook() -> dict:
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))


def test_end_to_end_demo_notebook_exists_with_required_sections() -> None:
    notebook = _load_notebook()
    sources = ["".join(cell.get("source", [])) for cell in notebook["cells"]]
    joined = "\n".join(sources)

    assert notebook["nbformat"] == 4
    assert "# NeuroOntoGen end-to-end demo" in joined
    assert "## 1. Compile the LinkML schema" in joined
    assert "## 2. Build a typed ABox payload" in joined
    assert "## 3. Serialize the ABox to Turtle" in joined
    assert "## 4. Validate the Turtle graph with SHACL" in joined
    assert "## 5. Show a SHACL violation" in joined
    assert "## 6. Run bounded mock repair" in joined
    assert "## 7. Display the final valid Turtle graph" in joined


def test_end_to_end_demo_notebook_uses_sdk_pipeline_not_hardcoded_outputs() -> None:
    notebook = _load_notebook()
    code = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )

    assert "compile_schema(" in code
    assert "ABoxPayload(" in code
    assert "serialize_abox_to_turtle(" in code
    assert "validate_abox_turtle(" in code
    assert "parse_shacl_violations(" in code
    assert "RepairController(" in code
    assert "requiredClearance" in code
    assert "assert valid_report.conforms is True" in code
    assert "assert invalid_report.conforms is False" in code
    assert "assert repair_result.final_report.conforms is True" in code


def test_dev_extra_includes_notebook_execution_tools() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "nbconvert" in pyproject
    assert "ipykernel" in pyproject
