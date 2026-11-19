"""Import persistence: imported workflows must be editable, not orphaned.

Previously ``POST /api/workflow-templates/{id}/import`` generated a workflow
definition and returned its id — but nothing was persisted under that id, so
``GET /{template_id}`` (what the editor loads) 404'd and the post-import
deep link dead-ended. These tests lock the bridge: import → persist as a
private editable copy → resolvable through the same surface the editor reads.
"""

from pathlib import Path

import pytest

from api import workflow_template_routes as wtr
from core.workflow_template_system import WorkflowTemplateManager

_REPO_STARTER = (
    Path(__file__).resolve().parents[1]
    / "workflow_templates"
    / "personal_invoice_chase.json"
)


def _param_name(param):
    return param.get("name") if isinstance(param, dict) else getattr(param, "name", None)


def _param_default(param):
    if isinstance(param, dict):
        return param.get("default_value")
    return getattr(param, "default_value", None)


def _add_required_invoice_input(data):
    """Give the stock starter a required runtime input (the failing shape).

    The source Atom is a published stock template, so the regression must
    prove import works even when a required input has no default. The step
    keeps a symbolic placeholder to prove import does not resolve it early.
    """
    data.setdefault("inputs", [])
    data["inputs"] = [
        item for item in data["inputs"] if item.get("name") != "invoice_number"
    ]
    data["inputs"].append({
        "name": "invoice_number",
        "label": "Invoice Number",
        "description": "Invoice to follow up on",
        "type": "string",
        "required": True,
        "default_value": None,
        "example_value": "INV-1042",
    })

    steps = data.setdefault("steps", [])
    if not steps:
        return data
    target = next(
        (step for step in steps if step.get("name") == "Scan inbox for invoice threads"),
        steps[0],
    )
    params = target.get("parameters")
    if isinstance(params, dict):
        params["invoice_number"] = "{{invoice_number}}"
    else:
        if not isinstance(params, list):
            params = []
            target["parameters"] = params
        existing = next(
            (
                param for param in params
                if isinstance(param, dict) and param.get("name") == "invoice_number"
            ),
            None,
        )
        if existing is None:
            params.append({
                "name": "invoice_number",
                "label": "Invoice Number",
                "type": "string",
                "default_value": "{{invoice_number}}",
            })
        else:
            existing["default_value"] = "{{invoice_number}}"
    return data


@pytest.fixture()
def manager(tmp_path):
    import json

    starter_dir = tmp_path / "templates"
    starter_dir.mkdir()
    with open(_REPO_STARTER) as f:
        data = json.load(f)
    # Fresh id so the fixture never collides with repo state.
    data["template_id"] = "template_src_chase"
    data["is_public"] = True
    _add_required_invoice_input(data)
    with open(starter_dir / "template_src_chase.json", "w") as f:
        json.dump(data, f)
    return WorkflowTemplateManager(template_dir=str(starter_dir))


def test_import_persists_an_editable_copy(manager):
    template = manager.get_template("template_src_chase")
    result = wtr._persist_imported_workflow(
        manager,
        template=template,
        workflow_name="Imported Personal: Invoice Chase (Freelancer)",
        author_email="solo@example.com",
    )

    assert result["editor_url"] == f"/workflows/editor/{result['workflow_id']}"
    imported = manager.get_template(result["workflow_id"])
    assert imported is not None, "imported id must resolve via GET /{template_id}"
    assert imported.is_public is False
    assert "imported" in imported.tags
    assert len(imported.steps) == len(template.steps)
    assert imported.name.startswith("Imported ")


def test_imported_steps_keep_parameter_data(manager):
    """The input_parameters→parameters remap must not drop step config."""
    template = manager.get_template("template_src_chase")
    result = wtr._persist_imported_workflow(
        manager,
        template=template,
        workflow_name="Imported chase",
        author_email=None,
    )
    imported = manager.get_template(result["workflow_id"])

    by_name = {s.name: s for s in imported.steps}
    scan = by_name["Scan inbox for invoice threads"]
    params = scan.parameters
    assert params, "step parameters lost during import persistence"

    # Dict-form source config is preserved as named parameters (dict or
    # declared-list form both acceptable round-trips).
    def _param_name(p):
        return p.get("name") if isinstance(p, dict) else getattr(p, "name", None)

    names = {_param_name(p) for p in params}
    assert "query" in names


def test_import_is_private_even_when_source_is_featured(manager):
    template = manager.get_template("template_src_chase")
    result = wtr._persist_imported_workflow(
        manager,
        template=template,
        workflow_name="Imported again",
        author_email="x@y.z",
    )
    imported = manager.get_template(result["workflow_id"])
    assert imported.is_public is False


def test_import_keeps_required_input_and_symbolic_placeholders(manager):
    """A required runtime input must not block import or be resolved early."""
    template = manager.get_template("template_src_chase")
    result = wtr._persist_imported_workflow(
        manager,
        template=template,
        workflow_name="Imported invoice follow-up draft",
        author_email="admin@example.com",
    )

    imported = manager.get_template(result["workflow_id"])
    assert imported is not None
    assert [step.step_id for step in imported.steps] == [
        step.step_id for step in template.steps
    ]

    invoice_input = next(
        (item for item in imported.inputs if item.name == "invoice_number"),
        None,
    )
    assert invoice_input is not None
    assert invoice_input.required is True
    assert invoice_input.default_value is None

    scan = next(
        step for step in imported.steps
        if step.name == "Scan inbox for invoice threads"
    )
    placeholder = next(
        (param for param in scan.parameters if _param_name(param) == "invoice_number"),
        None,
    )
    assert placeholder is not None
    assert _param_default(placeholder) == "{{invoice_number}}"


def test_imported_draft_survives_manager_reload(manager):
    """The imported copy is file-backed and still editable after a reload."""
    template = manager.get_template("template_src_chase")
    result = wtr._persist_imported_workflow(
        manager,
        template=template,
        workflow_name="Imported durable draft",
        author_email="admin@example.com",
    )

    reloaded_manager = WorkflowTemplateManager(template_dir=str(manager.template_dir))
    imported = reloaded_manager.get_template(result["workflow_id"])
    assert imported is not None
    assert imported.is_public is False
    assert "imported" in imported.tags

    invoice_input = next(
        (item for item in imported.inputs if item.name == "invoice_number"),
        None,
    )
    assert invoice_input is not None
    assert invoice_input.required is True
    assert invoice_input.default_value is None


def test_runtime_instantiation_still_requires_the_missing_input(manager):
    """Draft import must not weaken runtime required-input validation."""
    template = manager.get_template("template_src_chase")
    result = wtr._persist_imported_workflow(
        manager,
        template=template,
        workflow_name="Imported draft for runtime check",
        author_email="admin@example.com",
    )

    with pytest.raises(
        ValueError,
        match="Required parameter 'invoice_number' is missing",
    ):
        manager.create_workflow_from_template(
            template_id=result["workflow_id"],
            workflow_name="Run without invoice number",
            template_parameters={},
        )


def test_import_accepts_compatible_supplied_values(manager):
    """Explicit valid values remain accepted without overwriting source data."""
    template = manager.get_template("template_src_chase")
    result = wtr._persist_imported_workflow(
        manager,
        template=template,
        workflow_name="Imported prebound invoice draft",
        author_email="admin@example.com",
        template_parameters={"invoice_number": "INV-1042"},
    )

    imported = manager.get_template(result["workflow_id"])
    assert imported is not None
    # The template input contract (required, no default) is preserved.
    invoice_input = next(
        item for item in imported.inputs if item.name == "invoice_number"
    )
    assert invoice_input.required is True
    assert invoice_input.default_value is None

    # The same supplied value is compatible with a real runtime instantiation.
    instantiated = manager.create_workflow_from_template(
        template_id=result["workflow_id"],
        workflow_name="Run prebound invoice draft",
        template_parameters={"invoice_number": "INV-1042"},
    )
    assert instantiated["parameters_applied"]["invoice_number"] == "INV-1042"
