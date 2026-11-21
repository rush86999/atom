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

The server-known stock invoice launch id is different: both authenticated
execute routes now assert its small public input contract before shared
admission, while scheduling deliberately stays on the catalog preflight path.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

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


def _stock_invoice_steps():
    """Self-contained shape of the stock invoice template used by #1029."""
    return [
        {"id": "lookup_invoice", "name": "Lookup Invoice",
         "step_type": "action", "service": "invoice", "action": "lookup"},
        {"id": "check_status", "name": "Check Status",
         "step_type": "action"},
        {"id": "send_reminder", "name": "Send Reminder",
         "step_type": "action"},
        {"id": "await_commitment", "name": "Await Commitment",
         "step_type": "trigger", "depends_on": ["send_reminder"]},
        {"id": "escalate", "name": "Escalate", "step_type": "action"},
        {"id": "confirm_settled", "name": "Confirm Settled",
         "step_type": "action"},
    ]


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


def test_editor_route_requires_stock_invoice_launch_contract(
        capability_sources, monkeypatch):
    try:
        import api.workflow_template_routes as routes
    except ModuleNotFoundError as exc:  # partial public-code packet
        pytest.skip(f"full backend modules unavailable: {exc}")

    execute = getattr(routes.execute_template, "__wrapped__", None)
    if execute is None:
        pytest.skip("governance decorator does not expose the route body")

    try:
        import core.workflow_endpoints  # noqa: F401
    except ModuleNotFoundError as exc:  # partial public-code packet
        pytest.skip(f"full backend modules unavailable: {exc}")

    invoice_steps = _invoice_steps()

    class FakeManager:
        def get_template(self, _template_id):
            return SimpleNamespace(steps=invoice_steps)

        def create_workflow_from_template(
                self, *args, **kwargs):
            raise AssertionError(
                "stock input must not reach generic template dispatch")

    async def allow_executor(*_args, **_kwargs):
        return None

    started = []

    class FakeEngine:
        async def start_workflow(self, *args, **kwargs):
            started.append((args, kwargs))
            return "should-not-run"

    monkeypatch.setattr(
        routes, "get_template_manager", lambda: FakeManager())
    monkeypatch.setattr(
        routes, "require_workflow_executor_definition", allow_executor)
    monkeypatch.setattr(
        "core.workflow_engine.get_workflow_engine", lambda: FakeEngine())

    user = SimpleNamespace(id="u1", tenant_id="t1", workspace_id="w1")

    def invoke(parameters, request):
        with pytest.raises(Exception) as raised:
            asyncio.run(execute(
                template_id="htn_invoice_followup",
                parameters=parameters,
                request=request,
                current_user=user,
                db=None,
                agent_id=None,
            ))
        return raised.value

    # Invoice number alone is not enough: the required idempotency key is
    # absent, so the stock input contract is refused before generic dispatch.
    error = invoke({"invoice_number": "INV-1"}, None)
    assert getattr(error, "status_code", None) == 422
    assert error.detail["error"] == "validation_error"
    assert error.detail["field"] == "idempotency_key"

    request = SimpleNamespace(headers={"Idempotency-Key": "idem-1"})

    # The account owner binding is explicit in the public contract (including
    # the nullable form); absence is not "infer the caller".
    error = invoke({"invoice_number": "INV-1"}, request)
    assert getattr(error, "status_code", None) == 422
    assert error.detail["error"] == "validation_error"
    assert error.detail["field"] == "account_owner_user_id"

    # A blank invoice number is refused as a field error, not by the generic
    # template engine.
    error = invoke(
        {"invoice_number": "   ", "account_owner_user_id": None}, request)
    assert getattr(error, "status_code", None) == 422
    assert error.detail["error"] == "validation_error"
    assert error.detail["field"] == "invoice_number"
    assert started == [], "stock input refusal must not start a run"


def test_editor_route_projects_stock_launch_admission(
        capability_sources, monkeypatch):
    try:
        import api.workflow_template_routes as routes
    except ModuleNotFoundError as exc:  # partial public-code packet
        pytest.skip(f"full backend modules unavailable: {exc}")

    execute = getattr(routes.execute_template, "__wrapped__", None)
    if execute is None:
        pytest.skip("governance decorator does not expose the route body")

    try:
        import core.workflow_endpoints  # noqa: F401
    except ModuleNotFoundError as exc:  # partial public-code packet
        pytest.skip(f"full backend modules unavailable: {exc}")

    try:
        import core.invoice_launch_admission as admission
    except ModuleNotFoundError as exc:  # partial public-code packet
        pytest.skip(f"full backend modules unavailable: {exc}")

    class FakeManager:
        def get_template(self, _template_id):
            return SimpleNamespace(steps=[])

    async def allow_executor(*_args, **_kwargs):
        return None

    async def fake_admit(*_args, **_kwargs):
        return {
            "execution_id": "exec-stock",
            "run_id": "run-stock",
            "status": "attached",
            "attached": True,
            "paused": False,
            "review_required": False,
            "requires_review": False,
        }

    monkeypatch.setattr(
        routes, "get_template_manager", lambda: FakeManager())
    monkeypatch.setattr(
        routes, "require_workflow_executor_definition", allow_executor)
    monkeypatch.setattr(
        admission, "build_stock_invoice_launch_workflow",
        lambda *args, **kwargs: {"steps": []})
    monkeypatch.setattr(
        admission, "admit_stock_invoice_launch", fake_admit)

    user = SimpleNamespace(id="u1", tenant_id="t1", workspace_id="w1")
    request = SimpleNamespace(headers={"Idempotency-Key": "idem-1"})

    result = asyncio.run(execute(
        template_id="htn_invoice_followup",
        parameters={
            "invoice_number": "INV-1",
            "account_owner_user_id": None,
        },
        request=request,
        current_user=user,
        db=None,
        agent_id=None,
    ))

    assert result == {
        "execution_id": "exec-stock",
        "state": "attached",
        "next_action": "wait",
        "run_id": "run-stock",
    }

    async def fake_invalid_owner(*_args, **_kwargs):
        raise admission.InvalidStockInvoiceAccountOwner()

    monkeypatch.setattr(
        admission, "admit_stock_invoice_launch", fake_invalid_owner)

    with pytest.raises(Exception) as raised:
        asyncio.run(execute(
            template_id="htn_invoice_followup",
            parameters={
                "invoice_number": "INV-1",
                "account_owner_user_id": "u2",
            },
            request=request,
            current_user=user,
            db=None,
            agent_id=None,
        ))

    error = raised.value
    assert getattr(error, "status_code", None) == 422
    assert error.detail == {
        "error": "validation_error",
        "field": "account_owner_user_id",
        "message": "account_owner_user_id is not valid for this request",
    }
    assert "u2" not in json.dumps(error.detail)


@pytest.mark.parametrize("step_type", ["action", "api_call"])
def test_editor_route_dispatches_bound_ai_summarize_via_canonical_engine(
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
                "workflow_id": "workflow-generated",
                "workflow_definition": {
                    "name": "AI Summarize",
                    "steps": [{**step, "step_id": step["id"]}
                              for step in steps],
                },
            }

    async def allow_executor(*_args, **_kwargs):
        return None

    started = []

    class FakeEngine:
        async def start_workflow(
                self, definition, input_data, background_tasks, scope=None):
            started.append((definition, input_data, scope))
            return "exec-ai-summarize"

    monkeypatch.setattr(
        routes, "get_template_manager", lambda: FakeManager())
    monkeypatch.setattr(
        routes, "require_workflow_executor_definition", allow_executor)
    monkeypatch.setattr(
        "core.workflow_engine.get_workflow_engine", lambda: FakeEngine())

    user = SimpleNamespace(id="u1", tenant_id="t1", workspace_id="w1")

    result = asyncio.run(execute(
        template_id="ai_summarize_template",
        parameters={},
        request=None,
        current_user=user,
        db=None,
        agent_id=None,
    ))

    assert result["execution_id"] == "exec-ai-summarize"
    assert result["workflow_status"] == "running"
    assert len(started) == 1
    definition, _input_data, scope = started[0]
    assert definition["_template_catalog"] is True
    assert definition["steps"][0]["service"] == "ai"
    assert definition["steps"][0]["action"] == "summarize"
    assert scope == {"workspace_id": "w1", "tenant_id": "t1", "user_id": "u1"}


def test_editor_route_executes_stock_goal_driven_template_canonically(
        capability_sources, monkeypatch, tmp_path):
    try:
        import api.workflow_template_routes as routes
    except ModuleNotFoundError as exc:  # partial public-code packet
        pytest.skip(f"full backend modules unavailable: {exc}")

    execute = getattr(routes.execute_template, "__wrapped__", None)
    if execute is None:
        pytest.skip("governance decorator does not expose the route body")

    # The stock fixture's bindings are real built-in engine services. (The
    # public packet has no WorkflowEngine implementation, so pin the registry
    # explicitly, as the other admission tests do.)
    monkeypatch.setattr(
        preflight, "_engine_services",
        lambda: frozenset({"goal_management", "workflow_notification"}),
    )

    manager = WorkflowTemplateManager(template_dir=str(tmp_path))
    goal = next(
        template for template in manager.list_templates(limit=100)
        if template.name == "Goal-Driven Automation"
    )

    class FakeManager:
        def get_template(self, _template_id):
            return goal

        def create_workflow_from_template(self, *args, **kwargs):
            return manager.create_workflow_from_template(
                template_id=goal.template_id,
                workflow_name="Goal-Driven Automation Run",
                template_parameters=kwargs.get("template_parameters") or {},
            )

    async def allow_executor(*_args, **_kwargs):
        return None

    started = []

    class FakeEngine:
        async def start_workflow(
                self, definition, input_data, background_tasks, scope=None):
            started.append((definition, input_data, scope))
            return "exec-goal-durable"

    monkeypatch.setattr(
        routes, "get_template_manager", lambda: FakeManager())
    monkeypatch.setattr(
        routes, "require_workflow_executor_definition", allow_executor)
    monkeypatch.setattr(
        "core.workflow_engine.get_workflow_engine", lambda: FakeEngine())

    user = SimpleNamespace(id="u1", tenant_id="t1", workspace_id="w1")
    parameters = {
        "goal_text": "Close the Q4 sales deal with Acme Corp",
        "target_date": "2026-12-31T23:59:59Z",
    }

    result = asyncio.run(execute(
        template_id=goal.template_id,
        parameters=parameters,
        request=None,
        current_user=user,
        db=None,
        agent_id=None,
    ))

    assert result == {
        "status": "success",
        "execution_id": "exec-goal-durable",
        "workflow_status": "running",
        "message": "Workflow started. Status: running",
    }
    assert len(started) == 1
    definition, input_data, scope = started[0]
    assert definition["id"] == goal.template_id
    assert definition["_template_catalog"] is True
    by_id = {step["id"]: step for step in definition["steps"]}
    assert by_id["init_goal"]["service"] == "goal_management"
    assert by_id["init_goal"]["action"] == "create_goal"
    assert by_id["init_goal"]["parameters"]["title"] == (
        "${input.goal_text}")
    assert by_id["notify_user"]["service"] == "workflow_notification"
    assert by_id["notify_user"]["action"] == "notify_caller"
    assert input_data == parameters
    assert scope == {"workspace_id": "w1", "tenant_id": "t1", "user_id": "u1"}


def test_editor_route_refuses_mixed_supported_and_unsupported_steps(
        capability_sources, monkeypatch):
    try:
        import api.workflow_template_routes as routes
    except ModuleNotFoundError as exc:  # partial public-code packet
        pytest.skip(f"full backend modules unavailable: {exc}")

    execute = getattr(routes.execute_template, "__wrapped__", None)
    if execute is None:
        pytest.skip("governance decorator does not expose the route body")

    monkeypatch.setattr(
        preflight, "_engine_services",
        lambda: frozenset({"goal_management"}),
    )

    steps = [
        {
            "id": "init_goal",
            "name": "Initialize Goal",
            "step_type": "goal_initialization",
            "service": "goal_management",
            "action": "create_goal",
        },
        {
            "id": "unknown",
            "name": "Unknown Step",
            "step_type": "action",
            "service": "external_unknown",
            "action": "query",
        },
    ]

    class FakeManager:
        def get_template(self, _template_id):
            return SimpleNamespace(steps=steps)

        def create_workflow_from_template(self, *args, **kwargs):
            return {
                "workflow_id": "workflow-generated",
                "workflow_definition": {
                    "name": "Mixed Steps",
                    "steps": [{**step, "step_id": step["id"]}
                              for step in steps],
                },
            }

    async def allow_executor(*_args, **_kwargs):
        return None

    started = []

    class FakeEngine:
        async def start_workflow(self, *args, **kwargs):
            started.append((args, kwargs))
            return "should-not-run"

    monkeypatch.setattr(
        routes, "get_template_manager", lambda: FakeManager())
    monkeypatch.setattr(
        routes, "require_workflow_executor_definition", allow_executor)
    monkeypatch.setattr(
        "core.workflow_engine.get_workflow_engine", lambda: FakeEngine())

    user = SimpleNamespace(id="u1", tenant_id="t1", workspace_id="w1")

    with pytest.raises(Exception) as raised:
        asyncio.run(execute(
            template_id="mixed_steps",
            parameters={},
            request=None,
            current_user=user,
            db=None,
            agent_id=None,
        ))

    error = raised.value
    assert getattr(error, "status_code", None) == 422
    assert error.detail["error"] == "execution_blocked"
    assert {item["step_id"] for item in error.detail["blockers"]} == {
        "unknown"}
    assert started == [], "no execution receipt may be created"


def test_editor_route_refuses_unknown_binding_without_starting_engine(
        capability_sources, monkeypatch):
    try:
        import api.workflow_template_routes as routes
    except ModuleNotFoundError as exc:  # partial public-code packet
        pytest.skip(f"full backend modules unavailable: {exc}")

    execute = getattr(routes.execute_template, "__wrapped__", None)
    if execute is None:
        pytest.skip("governance decorator does not expose the route body")

    steps = [{
        "id": "lookup",
        "name": "Lookup",
        "step_type": "action",
        "service": "external_unknown",
        "action": "query",
    }]

    class FakeManager:
        def get_template(self, _template_id):
            return SimpleNamespace(steps=steps)

        def create_workflow_from_template(self, *args, **kwargs):
            return {
                "workflow_id": "workflow-generated",
                "workflow_definition": {
                    "name": "Unknown Binding",
                    "steps": [{**steps[0], "step_id": "lookup"}],
                },
            }

    async def allow_executor(*_args, **_kwargs):
        return None

    started = []

    class FakeEngine:
        async def start_workflow(self, *args, **kwargs):
            started.append((args, kwargs))
            return "should-not-run"

    monkeypatch.setattr(
        routes, "get_template_manager", lambda: FakeManager())
    monkeypatch.setattr(
        routes, "require_workflow_executor_definition", allow_executor)
    monkeypatch.setattr(
        "core.workflow_engine.get_workflow_engine", lambda: FakeEngine())

    user = SimpleNamespace(id="u1", tenant_id="t1", workspace_id="w1")

    with pytest.raises(Exception) as raised:
        asyncio.run(execute(
            template_id="unknown_binding",
            parameters={},
            request=None,
            current_user=user,
            db=None,
            agent_id=None,
        ))

    error = raised.value
    assert getattr(error, "status_code", None) == 422
    assert error.detail["error"] == "execution_blocked"
    assert error.detail["blockers"][0]["step_id"] == "lookup"
    assert started == [], "no execution receipt may be created"


def test_editor_route_refuses_catalog_only_external_fallback(
        capability_sources, monkeypatch):
    try:
        import api.workflow_template_routes as routes
    except ModuleNotFoundError as exc:  # partial public-code packet
        pytest.skip(f"full backend modules unavailable: {exc}")

    execute = getattr(routes.execute_template, "__wrapped__", None)
    if execute is None:
        pytest.skip("governance decorator does not expose the route body")

    steps = [{
        "id": "sync",
        "name": "Sync",
        "step_type": "action",
        "service": "external_crm",
        "action": "sync",
    }]

    class FakeManager:
        def get_template(self, _template_id):
            return SimpleNamespace(steps=steps)

        def create_workflow_from_template(self, *args, **kwargs):
            return {
                "workflow_id": "workflow-generated",
                "workflow_definition": {
                    "name": "External Sync",
                    "steps": [{**steps[0], "step_id": "sync"}],
                },
            }

    async def allow_executor(*_args, **_kwargs):
        return None

    started = []

    class FakeEngine:
        async def start_workflow(self, *args, **kwargs):
            started.append((args, kwargs))
            return "should-not-run"

    # The catalog knows the action, but the canonical engine's built-in
    # registry does not. The editor must not silently take over the
    # Workflows-list route's external fallback.
    monkeypatch.setattr(
        preflight, "_catalog_actions",
        lambda service: [{"name": "sync"}]
        if service == "external_crm" else None)
    monkeypatch.setattr(
        routes, "get_template_manager", lambda: FakeManager())
    monkeypatch.setattr(
        routes, "require_workflow_executor_definition", allow_executor)
    monkeypatch.setattr(
        "core.workflow_engine.get_workflow_engine", lambda: FakeEngine())

    user = SimpleNamespace(id="u1", tenant_id="t1", workspace_id="w1")

    with pytest.raises(Exception) as raised:
        asyncio.run(execute(
            template_id="external_sync",
            parameters={},
            request=None,
            current_user=user,
            db=None,
            agent_id=None,
        ))

    error = raised.value
    assert getattr(error, "status_code", None) == 422
    assert error.detail["error"] == "execution_blocked"
    assert error.detail["blockers"][0]["code"] == "service_not_available"
    assert started == [], "no execution receipt may be created"


def test_workflows_route_requires_stock_invoice_launch_contract(
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

    # Invoice number alone is not enough: the stock public contract also
    # requires the idempotency key and an explicit account owner binding.
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
    assert error.detail["error"] == "validation_error"
    assert error.detail["field"] == "idempotency_key"
    assert started == [], "no execution receipt may be created"

    # The documented body fallback is accepted; with it present, the next
    # missing contract field is the explicit owner binding.
    with pytest.raises(Exception) as raised:
        asyncio.run(endpoints.execute_workflow(
            "htn_invoice_followup",
            BackgroundTasks(),
            {"invoice_number": "INV-1", "idempotency_key": "idem-body"},
            user,
            None,
        ))

    error = raised.value
    assert getattr(error, "status_code", None) == 422
    assert error.detail["error"] == "validation_error"
    assert error.detail["field"] == "account_owner_user_id"
    assert started == [], "no execution receipt may be created"

    request = SimpleNamespace(headers={"Idempotency-Key": "idem-1"})
    with pytest.raises(Exception) as raised:
        asyncio.run(endpoints.execute_workflow(
            "htn_invoice_followup",
            BackgroundTasks(),
            {"invoice_number": "INV-1"},
            user,
            None,
            request,
        ))

    error = raised.value
    assert getattr(error, "status_code", None) == 422
    assert error.detail["error"] == "validation_error"
    assert error.detail["field"] == "account_owner_user_id"
    assert started == [], "no execution receipt may be created"


def test_schedule_route_refuses_catalog_template_before_installing_job(
        capability_sources, monkeypatch):
    try:
        import core.workflow_endpoints as endpoints
    except ModuleNotFoundError as exc:  # partial public-code packet
        pytest.skip(f"full backend modules unavailable: {exc}")

    template_definition = {
        "id": "htn_invoice_followup",
        "name": "Invoice Follow-up Sequence",
        "description": "",
        "steps": _stock_invoice_steps(),
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

    scheduler = SimpleNamespace(
        schedule_workflow=MagicMock(return_value="job_should_not_exist"))

    def freeze_scope(input_data, **_kwargs):
        return dict(input_data or {})

    monkeypatch.setattr(
        "core.workflow_engine.freeze_execution_scope", freeze_scope)
    monkeypatch.setattr(
        "ai.workflow_scheduler.workflow_scheduler", scheduler)

    user = SimpleNamespace(id="u1", tenant_id="t1", workspace_id="w1")

    with pytest.raises(Exception) as raised:
        asyncio.run(endpoints.schedule_workflow(
            "htn_invoice_followup",
            {
                "trigger_type": "interval",
                "trigger_config": {"minutes": 30},
                "input_data": {"invoice_number": "INV-1"},
            },
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
    scheduler.schedule_workflow.assert_not_called()


def test_schedule_route_installs_supported_catalog_template(
        capability_sources, monkeypatch):
    try:
        import core.workflow_endpoints as endpoints
    except ModuleNotFoundError as exc:  # partial public-code packet
        pytest.skip(f"full backend modules unavailable: {exc}")

    template_definition = {
        "id": "supported_goal",
        "name": "Supported Goal",
        "description": "",
        "steps": [{
            "id": "notify",
            "name": "Notify",
            "step_type": "action",
            "service": "email",
            "action": "send",
            "parameters": {"to": "ops@example.test"},
        }],
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
    monkeypatch.setattr(
        endpoints.RBACService, "check_permission",
        lambda *_args, **_kwargs: True,
    )

    scheduler = SimpleNamespace(
        schedule_workflow=MagicMock(return_value="job_supported"))

    def freeze_scope(input_data, **_kwargs):
        return dict(input_data or {})

    monkeypatch.setattr(
        "core.workflow_engine.freeze_execution_scope", freeze_scope)
    monkeypatch.setattr(
        "ai.workflow_scheduler.workflow_scheduler", scheduler)

    user = SimpleNamespace(id="u1", tenant_id="t1", workspace_id="w1")

    result = asyncio.run(endpoints.schedule_workflow(
        "supported_goal",
        {
            "trigger_type": "interval",
            "trigger_config": {"minutes": 30},
            "input_data": {},
        },
        user,
        None,
    ))

    assert result["success"] is True
    assert result["job_id"] == "job_supported"
    scheduler.schedule_workflow.assert_called_once()


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
