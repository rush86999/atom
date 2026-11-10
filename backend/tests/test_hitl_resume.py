"""A HITL decision must resume the work it paused.

Regression: POST /api/agents/approvals/{id} returned 200 and flipped the row
to APPROVED, but a paused goal run stayed paused_hitl with its
pending_decision intact forever. Same for workflow PAUSED executions.
These tests lock the shared resume bridge.
"""
import asyncio

import core.hitl_resume as hitl_resume


def _action(**overrides):
    base = {
        "id": "hitl-1",
        "workspace_id": "default",
        "tenant_id": "default",
        "action_type": "goal_run_decision",
        "params": {"run_id": "run-1", "decision": {
            "decision": "ASK_HUMAN",
            "decision_id": "dec-1",
            "decision_generation": 1,
            "decision_binding": "bind-1",
        }},
        "reason": "needs a human",
    }
    base.update(overrides)
    return base


def test_goal_run_decision_approval_resumes(monkeypatch):
    calls = {}

    class FakeService:
        def __init__(self, workspace_id, tenant_id):
            calls["bound"] = (workspace_id, tenant_id)

        async def resume(self, run_id, approved, reviewer, guidance,
                         expected_decision_id=None,
                         expected_decision_binding=None):
            calls.update(run_id=run_id, approved=approved, reviewer=reviewer,
                         guidance=guidance,
                         expected_decision_id=expected_decision_id,
                         expected_decision_binding=expected_decision_binding)
            return {"resumed": True, "approved": approved,
                    "run": {"id": run_id, "status": "active"}}

    monkeypatch.setattr(hitl_resume, "_load_action", lambda *_, **__: _action())
    monkeypatch.setattr(
        "core.goals.goal_run_service.GoalRunService", FakeService)

    result = asyncio.run(hitl_resume.resume_after_hitl_decision(
        "hitl-1", approved=True, reviewer_id="admin-1", guidance="go ahead"))

    assert result["handled"] is True
    assert result["resumed"] is True
    assert result["kind"] == "decision"
    assert calls == {
        "bound": ("default", "default"),
        "run_id": "run-1",
        "approved": True,
        "reviewer": "admin-1",
        "guidance": "go ahead",
        "expected_decision_id": "dec-1",
        "expected_decision_binding": "bind-1",
    }


def test_goal_run_checkpoint_rejection_rewinds(monkeypatch):
    calls = {}

    class FakeService:
        def __init__(self, workspace_id, tenant_id):
            pass

        def consume_wake(self, run_id, event):
            calls["wake"] = (run_id, event)
            return {"consumed": True}

        def rewind_to_work_before(self, run_id, step_id):
            calls["rewind"] = (run_id, step_id)

        def complete_checkpoint(self, run_id, step_id):
            calls["complete"] = (run_id, step_id)

        async def advance(self, run_id, event):
            calls["advance"] = (run_id, event)
            return {"advanced": True}

    monkeypatch.setattr(hitl_resume, "_load_action", lambda *_, **__: _action(
        action_type="goal_run_checkpoint",
        params={"run_id": "run-1", "step_id": "cp1"},
    ))
    monkeypatch.setattr(
        "core.goals.goal_run_service.GoalRunService", FakeService)

    result = asyncio.run(hitl_resume.resume_after_hitl_decision(
        "hitl-1", approved=False, reviewer_id="lead-1",
        guidance="price is wrong"))

    assert result["handled"] is True and result["resumed"] is True
    assert calls["wake"][1]["approved"] is False
    assert calls["rewind"] == ("run-1", "cp1")
    assert "complete" not in calls
    assert calls["advance"][1]["approved"] is False


def test_workflow_approval_resumes_execution(monkeypatch):
    calls = {}

    class FakeStateManager:
        async def get_execution_state(self, execution_id):
            calls["state"] = execution_id
            return {"workflow_id": "wf-1", "status": "PAUSED"}

        async def update_execution_status(self, *args, **kwargs):
            calls["status"] = (args, kwargs)

    class FakeEngine:
        async def resume_workflow(self, execution_id, workflow, inputs):
            calls["resume"] = (execution_id, workflow.get("id"), inputs)
            return True

    monkeypatch.setattr(hitl_resume, "_load_action", lambda *_, **__: _action(
        action_type="execute_command",
        params={"execution_id": "exec-1", "workflow_id": "wf-1"},
    ))
    monkeypatch.setattr(
        "core.execution_state_manager.get_state_manager",
        lambda: FakeStateManager())
    monkeypatch.setattr(
        "core.workflow_endpoints.load_workflows", lambda: [{"id": "wf-1"}])
    monkeypatch.setattr(
        "core.workflow_engine.get_workflow_engine", lambda: FakeEngine())

    result = asyncio.run(hitl_resume.resume_after_hitl_decision(
        "hitl-1", approved=True, reviewer_id="lead-1"))

    assert result["handled"] is True
    assert result["resumed"] is True
    assert calls["resume"][0:2] == ("exec-1", "wf-1")
    assert calls["resume"][2]["approved"] is True


def test_workflow_rejection_fails_execution(monkeypatch):
    calls = {}

    class FakeStateManager:
        async def get_execution_state(self, execution_id):
            return {"workflow_id": "wf-1", "status": "PAUSED"}

        async def update_execution_status(self, execution_id, status, error=None):
            calls["failed"] = (execution_id, status, error)

    monkeypatch.setattr(hitl_resume, "_load_action", lambda *_, **__: _action(
        action_type="execute_command",
        params={"execution_id": "exec-1", "workflow_id": "wf-1"},
    ))
    monkeypatch.setattr(
        "core.execution_state_manager.get_state_manager",
        lambda: FakeStateManager())

    result = asyncio.run(hitl_resume.resume_after_hitl_decision(
        "hitl-1", approved=False, reviewer_id="lead-1",
        guidance="do not touch production"))

    assert result["handled"] is True
    assert result["resumed"] is False
    assert calls["failed"][0:2] == ("exec-1", "FAILED")
    assert "production" in calls["failed"][2]


def test_non_durable_action_is_not_claimed(monkeypatch):
    monkeypatch.setattr(hitl_resume, "_load_action", lambda *_, **__: _action(
        action_type="recall_episodes", params={"query": "x"}))
    result = asyncio.run(hitl_resume.resume_after_hitl_decision(
        "hitl-1", approved=True))
    assert result["handled"] is False
    assert "durable waiter" in result["reason"]


def test_goal_run_legacy_unbound_action_is_refused(monkeypatch):
    """A legacy HITL row without a reviewed decision binding must not resume."""
    calls = {}

    class FakeService:
        def __init__(self, workspace_id, tenant_id):
            calls["constructed"] = True

        async def resume(self, *args, **kwargs):  # pragma: no cover
            calls["resume"] = True
            return {"resumed": True}

    monkeypatch.setattr(hitl_resume, "_load_action", lambda *_, **__: _action(
        params={"run_id": "run-1", "decision": {"decision": "ASK_HUMAN"}}))
    monkeypatch.setattr(
        "core.goals.goal_run_service.GoalRunService", FakeService)

    result = asyncio.run(hitl_resume.resume_after_hitl_decision(
        "hitl-1", approved=True, reviewer_id="admin-1"))

    assert result["handled"] is True
    assert result["resumed"] is False
    assert result["stale_review"] is True
    assert result["reason"] == "decision_review_required"
    assert "resume" not in calls


def test_goal_run_stale_action_returns_refresh_required(monkeypatch):
    calls = {}

    class FakeService:
        def __init__(self, workspace_id, tenant_id):
            pass

        async def resume(self, run_id, approved, reviewer, guidance,
                         expected_decision_id=None,
                         expected_decision_binding=None):
            calls.update(
                run_id=run_id,
                expected_decision_id=expected_decision_id,
                expected_decision_binding=expected_decision_binding)
            return {"resumed": False, "stale_review": True,
                    "reason": "stale_decision_review",
                    "current_decision_id": "dec-2"}

    monkeypatch.setattr(hitl_resume, "_load_action", lambda *_, **__: _action(
        params={"run_id": "run-1", "decision": {
            "decision": "ADVANCE",
            "decision_id": "dec-1",
            "decision_generation": 1,
            "decision_binding": "bind-1",
        }}))
    monkeypatch.setattr(
        "core.goals.goal_run_service.GoalRunService", FakeService)

    result = asyncio.run(hitl_resume.resume_after_hitl_decision(
        "hitl-1", approved=True, reviewer_id="admin-1"))

    assert result["resumed"] is False
    assert result["stale_review"] is True
    assert result["current_decision_id"] == "dec-2"
    assert calls["expected_decision_id"] == "dec-1"
    assert calls["expected_decision_binding"] == "bind-1"


def test_preflight_goal_decision_rejects_stale_review(monkeypatch):
    action = _action(params={"run_id": "run-1", "decision": {
        "decision": "ADVANCE",
        "decision_id": "dec-a",
        "decision_generation": 1,
        "decision_binding": "bind-a",
    }})
    monkeypatch.setattr(hitl_resume, "_load_action", lambda *_, **__: action)

    class FakeService:
        def __init__(self, workspace_id, tenant_id, session_factory=None):
            pass

        def get_run(self, run_id):
            return {
                "id": run_id, "workspace_id": "default",
                "tenant_id": "default", "status": "paused_hitl",
                "human_interventions": 2, "material_revision": 2,
                "pending_decision": {
                    "decision": "REPLAN",
                    "rationale": "newer",
                    "decision_id": "dec-b",
                    "decision_generation": 2,
                    "decision_binding": "bind-b",
                },
            }

    monkeypatch.setattr(
        "core.goals.goal_run_service.GoalRunService", FakeService)
    out = hitl_resume.preflight_hitl_decision("hitl-1")
    assert out["valid"] is False
    assert out["reason"] == "stale_decision_review"
    assert out["current_decision_id"] == "dec-b"


def test_preflight_goal_decision_rejects_decision_rewrite(monkeypatch):
    action = _action(params={"run_id": "run-1", "decision": {
        "decision": "ADVANCE",
        "decision_id": "dec-a",
        "decision_generation": 1,
        "decision_binding": "bind-a",
    }})
    monkeypatch.setattr(hitl_resume, "_load_action", lambda *_, **__: action)
    out = hitl_resume.preflight_hitl_decision(
        "hitl-1", {"decision": {"decision": "REPLAN"}})
    assert out["valid"] is False
    assert out["reason"] == "decision_review_required"


def test_preflight_non_goal_action_is_unaffected(monkeypatch):
    monkeypatch.setattr(hitl_resume, "_load_action", lambda *_, **__: _action(
        action_type="send_email",
        params={"to": "x@y.example", "subject": "hi"}))
    assert hitl_resume.preflight_hitl_decision("hitl-1")["valid"] is True
