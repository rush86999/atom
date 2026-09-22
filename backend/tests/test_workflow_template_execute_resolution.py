"""Issue #618 — "Use Template → Execute" never started.

The Workflows page lists templates from the FILE-BACKED template system
(``GET /api/workflow-templates``, ids like
``template_personal_candidate_pipeline``) and posts that id straight to
``/api/v1/workflows/workflows/{id}/execute``. The execute endpoint only
resolved durable workflows plus DB-UUID ``WorkflowTemplate`` rows, so every
template execution 404'd ("Workflow not found").

``_load_template_definition`` now falls through to the file-backed system.
These tests pin: resolution works, steps carry the engine's execution
contract (service/action/parameters), and declared (list-shaped) step
parameters bind through the engine's ``${input.<name>}`` convention with
declared defaults preferred.
"""
import pytest

from core.workflow_endpoints import _load_template_definition
from core.workflow_template_system import WorkflowTemplateManager

TEMPLATE_ID = "template_exec_resolution_test"


def _write_template(tmp_path) -> WorkflowTemplateManager:
    manager = WorkflowTemplateManager(template_dir=str(tmp_path))
    manager.create_template({
        "template_id": TEMPLATE_ID,
        "name": "Exec Resolution Test",
        "description": "template executed straight from the catalog",
        "category": "automation",
        "complexity": "beginner",
        "tags": [],
        "author": "test",
        "is_public": True,
        "steps": [
            {
                "id": "s1",
                "name": "Fan out",
                "service": "workflow",
                "action": "noop",
                "parameters": {"sources": ["email", "form"]},
            },
            {
                "id": "s2",
                "name": "Notify",
                "service": "email",
                "action": "send",
                "parameters": [
                    {"name": "to_address", "type": "string", "label": "To",
                     "required": True, "default_value": None},
                    {"name": "subject", "type": "string", "label": "Subject",
                     "required": False, "default_value": "Weekly digest"},
                ],
            },
        ],
        "inputs": [],
    })
    return manager


@pytest.fixture
def template_dir(tmp_path, monkeypatch):
    """Point the resolver's WorkflowTemplateManager at the scratch store —
    the same patching seam the endpoint's function-level import provides."""
    real_cls = WorkflowTemplateManager

    def _factory():
        return real_cls(template_dir=str(tmp_path))

    monkeypatch.setattr(
        "core.workflow_template_system.WorkflowTemplateManager", _factory)
    return tmp_path


def test_file_backed_template_id_resolves_to_executable_definition(template_dir):
    _write_template(template_dir)

    definition = _load_template_definition(TEMPLATE_ID)

    assert definition is not None
    assert definition["id"] == TEMPLATE_ID
    assert definition["name"] == "Exec Resolution Test"
    assert len(definition["steps"]) == 2


def test_resolved_steps_carry_engine_contract(template_dir):
    """WorkflowEngine._execute_step reads step["service"], step["action"] and
    resolves step["parameters"] as a plain {name: value} dict — the resolved
    definition must satisfy that for both parameter shapes."""
    _write_template(template_dir)

    steps = _load_template_definition(TEMPLATE_ID)["steps"]
    by_id = {s["id"]: s for s in steps}

    assert by_id["s1"]["service"] == "workflow"
    assert by_id["s1"]["action"] == "noop"
    assert by_id["s1"]["parameters"] == {"sources": ["email", "form"]}

    assert by_id["s2"]["service"] == "email"
    assert by_id["s2"]["action"] == "send"
    # Declared parameter list → {name: value}: default preferred, otherwise
    # bind to the execution input the modal collected.
    assert by_id["s2"]["parameters"]["subject"] == "Weekly digest"
    assert by_id["s2"]["parameters"]["to_address"] == "${input.to_address}"


def test_unknown_id_still_returns_none(template_dir):
    assert _load_template_definition("template_does_not_exist") is None
