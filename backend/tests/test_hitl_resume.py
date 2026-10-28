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
        "params": {"run_id": "run-1", "decision": {"decision": "ASK_HUMAN"}},
        "reason": "needs a human",
    }
    base.update(overrides)
    return base


def test_goal_run_decision_approval_resumes(monkeypatch):
    calls = {}

    class FakeService:
        def __init__(self, workspace_id, tenant_id):
            calls["bound"] = (workspace_id, tenant_id)

        async def resume(self, run_id, approved, reviewer, guidance):
            calls.update(run_id=run_id, approved=approved, reviewer=reviewer,
                         guidance=guidance)
            return {"resumed": True, "approved": approved,
                    "run": {"id": run_id, "status": "active"}}

    monkeypatch.setattr(hitl_resume, "_load_action", lambda _: _action())
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

    monkeypatch.setattr(hitl_resume, "_load_action", lambda _: _action(
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

    monkeypatch.setattr(hitl_resume, "_load_action", lambda _: _action(
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

    monkeypatch.setattr(hitl_resume, "_load_action", lambda _: _action(
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
    monkeypatch.setattr(hitl_resume, "_load_action", lambda _: _action(
        action_type="recall_episodes", params={"query": "x"}))
    result = asyncio.run(hitl_resume.resume_after_hitl_decision(
        "hitl-1", approved=True))
    assert result["handled"] is False
    assert "durable waiter" in result["reason"]
