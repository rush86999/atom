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
