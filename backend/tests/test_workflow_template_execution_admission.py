"""Truthful execution admission for catalog templates.

The same catalog template used to take two different paths:

* ``POST /api/workflow-templates/{id}/execute`` mapped unknown business step
  types to the orchestrator's simulated ``API_CALL`` handler and reported
  ``completed``;
* ``POST /api/v1/workflows/workflows/{id}/execute`` handed the declared
  service/action to the canonical engine and persisted a durable ``FAILED``
  run when the service was not in the integration catalog.

These tests pin the shared preflight: unavailable steps are identified from
the template's own source before either engine creates a run, while real
generic bindings and draft import keep working.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.workflow_template_preflight as preflight
from core.workflow_template_system import WorkflowTemplateManager


TEMPLATE_FILE = (
    Path(__file__).resolve().parents[1]
    / "workflow_templates"
    / "htn_invoice_followup.json"
)


@pytest.fixture
def capability_sources(monkeypatch):
    """Make capability resolution deterministic without a live DB/catalog."""
    monkeypatch.setattr(
        preflight, "_engine_services",
        lambda: frozenset({"email", "workflow", "ai"}),
    )
    monkeypatch.setattr(preflight, "_catalog_actions", lambda _service: None)
    monkeypatch.setattr(
        preflight, "_native_orchestrator_step_types",
        lambda: preflight._NATIVE_ORCHESTRATOR_STEP_TYPES_FALLBACK,
    )


def _invoice_steps():
    return json.loads(TEMPLATE_FILE.read_text())["steps"]


def _codes(blockers):
    return {blocker.step_id: blocker.code for blocker in blockers}


def test_invoice_template_reports_every_unavailable_step(capability_sources):
    blockers = preflight.preflight_template_steps(
        _invoice_steps(), target="orchestrator")

    codes = _codes(blockers)
    assert codes["lookup_invoice"] == "service_not_available"
    for step_id in (
        "check_status", "send_reminder", "escalate", "confirm_settled",
    ):
        assert codes[step_id] == "missing_action_binding"
    # A business wait expressed as a design-time trigger is not a runtime
    # wait and must not be admitted as a completed no-op.
    assert codes["await_commitment"] == "design_time_trigger"
    assert len(blockers) == 6


def test_canonical_engine_binding_positives_still_pass(capability_sources):
    steps = [
        {"id": "notify", "step_type": "action",
         "service": "email", "action": "send"},
        {"id": "sub", "step_type": "workflow",
         "parameters": {"service": "workflow", "action": "noop"}},
    ]

    # The Workflows list dispatches by binding, so these stay executable.
    assert preflight.preflight_template_steps(
        steps, target="workflow_engine") == []

    # The editor route lowers both business names to API_CALL; a canonical
    # engine binding must not turn that simulator into a real admission.
    assert _codes(preflight.preflight_template_steps(
        steps, target="orchestrator")) == {
            "notify": "simulated_api_call",
            "sub": "simulated_api_call",
        }


def test_explicit_ai_summarize_is_admitted_only_for_binding_dispatch(
        capability_sources):
    steps = [{
        "id": "summarize",
        "step_type": "action",
        "service": "ai",
        "action": "summarize",
        "parameters": {"text": "invoice follows up"},
    }]

    # Canonical list route: ai/summarize has a real scoped handler.
    assert preflight.preflight_template_steps(
        steps, target="workflow_engine") == []

    # Same template through the editor: "action" is not an orchestrator
    # native type, so it dispatches to the simulated API_CALL handler.
    assert _codes(preflight.preflight_template_steps(
        steps, target="orchestrator")) == {
            "summarize": "simulated_api_call"}


def test_orchestrator_refuses_explicit_api_call_binding(capability_sources):
    steps = [{
        "id": "lookup",
        "step_type": "api_call",
        "service": "ai",
        "action": "summarize",
    }]

    # API_CALL is a simulation even with a resolvable canonical binding.
    assert _codes(preflight.preflight_template_steps(
        steps, target="orchestrator")) == {
            "lookup": "simulated_api_call"}

    # The binding-dispatched list route is unaffected.
    assert preflight.preflight_template_steps(
        steps, target="workflow_engine") == []


def test_orchestrator_admits_native_positive_delay(capability_sources):
    steps = [
        {"id": "start", "step_type": "trigger"},
        {"id": "hold", "step_type": "delay",
         "parameters": {"duration": 0.05, "unit": "seconds"}},
    ]

    assert preflight.preflight_template_steps(
        steps, target="orchestrator") == []


def test_catalog_service_and_action_are_both_checked(monkeypatch):
    monkeypatch.setattr(preflight, "_engine_services", lambda: frozenset())
    monkeypatch.setattr(
        preflight, "_catalog_actions",
        lambda service: (
            [{"name": "query"}] if service == "knowledge" else None),
    )
    monkeypatch.setattr(
        preflight, "_native_orchestrator_step_types",
        lambda: preflight._NATIVE_ORCHESTRATOR_STEP_TYPES_FALLBACK,
    )

    assert preflight.preflight_template_steps([
        {"id": "ok", "step_type": "action",
         "service": "knowledge", "action": "query"},
    ]) == []

    codes = _codes(preflight.preflight_template_steps([
        {"id": "bad-action", "step_type": "action",
         "service": "knowledge", "action": "delete"},
        {"id": "bad-service", "step_type": "action",
         "service": "missing", "action": "query"},
    ]))
    assert codes == {
        "bad-action": "action_not_available",
        "bad-service": "service_not_available",
    }


def test_start_trigger_is_a_marker_but_native_steps_need_the_right_engine(
        capability_sources):
    steps = [
        {"id": "start", "step_type": "trigger"},
        {"id": "hold", "step_type": "delay"},
    ]

    assert preflight.preflight_template_steps(
        steps, target="orchestrator") == []

    engine_codes = _codes(preflight.preflight_template_steps(
        steps, target="workflow_engine"))
    assert engine_codes == {
        "start": "step_type_not_executable",
        "hold": "missing_action_binding",
    }


def test_mid_graph_trigger_is_refused_for_every_target(capability_sources):
    steps = [
        {"id": "send", "step_type": "action",
         "service": "email", "action": "send"},
        {"id": "wait", "step_type": "trigger", "depends_on": ["send"]},
    ]

    for target in ("catalog", "orchestrator", "workflow_engine"):
        codes = _codes(preflight.preflight_template_steps(
            steps, target=target))
        assert codes["wait"] == "design_time_trigger"

    # The editor additionally refuses the business "action" step because it
    # lowers to the API_CALL simulator; binding dispatch targets do not.
    assert _codes(preflight.preflight_template_steps(
        steps, target="orchestrator")) == {
            "send": "simulated_api_call",
            "wait": "design_time_trigger",
        }
    assert _codes(preflight.preflight_template_steps(
        steps, target="catalog")) == {"wait": "design_time_trigger"}
    assert _codes(preflight.preflight_template_steps(
        steps, target="workflow_engine")) == {"wait": "design_time_trigger"}


def test_generated_definition_preserves_declared_binding(tmp_path):
    manager = WorkflowTemplateManager(template_dir=str(tmp_path))
    manager.create_template({
        "template_id": "binding_preservation",
        "name": "Binding Preservation",
        "description": "declared bindings survive instantiation",
        "category": "automation",
        "complexity": "beginner",
        "steps": [{
            "id": "lookup",
            "name": "Lookup",
            "step_type": "action",
            "service": "knowledge",
            "action": "knowledge.query",
        }],
        "inputs": [],
    })

    result = manager.create_workflow_from_template(
        template_id="binding_preservation",
        workflow_name="Binding Preservation Run",
        template_parameters={},
    )

    step = result["workflow_definition"]["steps"][0]
    assert step["service"] == "knowledge"
    assert step["action"] == "knowledge.query"


def test_editor_route_refuses_before_orchestrator_dispatch(
        capability_sources, monkeypatch):
    try:
        import api.workflow_template_routes as routes
    except ModuleNotFoundError as exc:  # partial public-code packet
        pytest.skip(f"full backend modules unavailable: {exc}")

    execute = getattr(routes.execute_template, "__wrapped__", None)
    if execute is None:
        pytest.skip("governance decorator does not expose the route body")

    invoice_steps = _invoice_steps()

    class FakeManager:
        def get_template(self, _template_id):
            return SimpleNamespace(steps=invoice_steps)

        def create_workflow_from_template(
                self, *args, **kwargs):
            return {
                "workflow_id": "workflow-should-not-run",
                "workflow_definition": {
                    "name": "Invoice Follow-up",
                    "steps": [
                        {
                            **step,
                            "step_id": step.get("step_id") or step.get("id"),
                        }
                        for step in invoice_steps
                    ],
                },
            }

    async def allow_executor(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        routes, "get_template_manager", lambda: FakeManager())
    monkeypatch.setattr(
        routes, "require_workflow_executor_definition", allow_executor)

    user = SimpleNamespace(id="u1", tenant_id="t1", workspace_id="w1")

    with pytest.raises(Exception) as raised:
        asyncio.run(execute(
            template_id="htn_invoice_followup",
            parameters={"invoice_number": "INV-1"},
            request=None,
            current_user=user,
            db=None,
            agent_id=None,
        ))

    error = raised.value
    assert getattr(error, "status_code", None) == 422
    assert error.detail["error"] == "execution_blocked"
    assert len(error.detail["blockers"]) == 6


@pytest.mark.parametrize("step_type", ["action", "api_call"])
def test_editor_route_refuses_bound_ai_summarize_simulation(
        capability_sources, monkeypatch, step_type):
    try:
        import api.workflow_template_routes as routes
    except ModuleNotFoundError as exc:  # partial public-code packet
        pytest.skip(f"full backend modules unavailable: {exc}")

    execute = getattr(routes.execute_template, "__wrapped__", None)
    if execute is None:
        pytest.skip("governance decorator does not expose the route body")

    steps = [{
        "id": "summarize",
        "name": "Summarize",
        "step_type": step_type,
        "service": "ai",
        "action": "summarize",
    }]

    class FakeManager:
        def get_template(self, _template_id):
            return SimpleNamespace(steps=steps)

        def create_workflow_from_template(self, *args, **kwargs):
            return {
                "workflow_id": "workflow-should-not-run",
                "workflow_definition": {
                    "name": "AI Summarize",
                    "steps": [{**step, "step_id": step["id"]}
                              for step in steps],
                },
            }

    async def allow_executor(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        routes, "get_template_manager", lambda: FakeManager())
    monkeypatch.setattr(
        routes, "require_workflow_executor_definition", allow_executor)

    user = SimpleNamespace(id="u1", tenant_id="t1", workspace_id="w1")

    with pytest.raises(Exception) as raised:
        asyncio.run(execute(
            template_id="ai_summarize_template",
            parameters={},
            request=None,
            current_user=user,
            db=None,
            agent_id=None,
        ))

    error = raised.value
    assert getattr(error, "status_code", None) == 422
    assert error.detail["error"] == "execution_blocked"
    assert [item["code"] for item in error.detail["blockers"]] == [
        "simulated_api_call"]


def test_workflows_route_refuses_before_engine_creates_a_receipt(
        capability_sources, monkeypatch):
    from fastapi import BackgroundTasks

    try:
        import core.workflow_endpoints as endpoints
    except ModuleNotFoundError as exc:  # partial public-code packet
        pytest.skip(f"full backend modules unavailable: {exc}")

    template_definition = {
        "id": "htn_invoice_followup",
        "name": "Invoice Follow-up Sequence",
        "description": "",
        "steps": _invoice_steps(),
        "_template_catalog": True,
    }
    monkeypatch.setattr(
        endpoints, "_find_visible_workflow", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        endpoints, "_load_template_definition",
        lambda *_args, **_kwargs: template_definition,
    )

    async def allow_executor(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        endpoints, "require_workflow_executor", allow_executor)

    started = []

    class FakeEngine:
        async def start_workflow(self, *args, **kwargs):
            started.append((args, kwargs))
            return "should-not-exist"

    monkeypatch.setattr(
        "core.workflow_engine.get_workflow_engine", lambda: FakeEngine())

    user = SimpleNamespace(id="u1", tenant_id="t1", workspace_id="w1")

    with pytest.raises(Exception) as raised:
        asyncio.run(endpoints.execute_workflow(
            "htn_invoice_followup",
            BackgroundTasks(),
            {"invoice_number": "INV-1"},
            user,
            None,
        ))

    error = raised.value
    assert getattr(error, "status_code", None) == 422
    assert error.detail["error"] == "execution_blocked"
    assert {item["step_id"] for item in error.detail["blockers"]} == {
        "lookup_invoice", "check_status", "send_reminder",
        "await_commitment", "escalate", "confirm_settled",
    }
    assert started == [], "no execution receipt may be created"


def test_draft_import_still_accepts_unresolved_required_inputs(tmp_path):
    source = json.loads(TEMPLATE_FILE.read_text())
    manager = WorkflowTemplateManager(template_dir=str(tmp_path))
    manager.create_template({
        **source,
        "template_id": "draft_invoice_import",
    })

    # Draft import deliberately leaves invoice_number unresolved; execution
    # admission is a separate increment and must not block editor drafts.
    result = manager.create_workflow_from_template(
        template_id="draft_invoice_import",
        workflow_name="Imported Invoice Follow-up",
        template_parameters={},
        require_all_inputs=False,
    )

    assert result["parameters_applied"]["invoice_number"] is None
    assert result["workflow_definition"]["steps"][0]["step_id"] == (
        "lookup_invoice")


def test_empty_catalog_steps_are_refused_on_execution_targets(
        capability_sources):
    assert {
        target: [
            blocker.code
            for blocker in preflight.preflight_template_steps(
                [], target=target)
        ]
        for target in ("orchestrator", "workflow_engine")
    } == {
        "orchestrator": ["no_steps"],
        "workflow_engine": ["no_steps"],
    }
