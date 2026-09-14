"""GoalRun access control (2026-09-13) — cross-workspace IDOR fix.

``GoalRunService`` is constructed workspace-bound by every surface (the
API routes bind it to the requester's workspace; events to the event's
workspace). Before the fix, ``get_run``/``_load`` queried by id ONLY, so
any signed-in user could read any run's full decision log and parameters
(``GET /api/goal-runs/{id}``, ``/decisions``, ``/canvases`` — no access
check), and a team_lead of workspace A could advance/cancel workspace B's
runs (the owner-or-supervisor check had no workspace scoping). The
service now scopes reads AND writes by its workspace, and the route guard
refuses run dicts outside the requester's workspace (404 — no existence
leak).

Pattern: service-level on the conftest scratch DB + isolated FastAPI app
with dependency overrides (same shape as test_goal_journey_gaps).
"""

import asyncio
import os
from contextlib import contextmanager
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("TESTING", "1")

import core.database as db_mod
from api.goal_run_routes import router as goal_runs_router
from core.auth import get_current_user
from core.database import get_db as _get_db
from core.goals.goal_run_service import GoalRunService
from core.models import GoalObjective, GoalRun, User, UserRole

WS_A = "ws-acme"
WS_B = "ws-globex"


@pytest.fixture(autouse=True)
def patched_session(db_session):
    """Route the module-level get_db_session (used by goal_runs.list and
    the service's default sessions) to the test session."""
    original = db_mod.get_db_session

    @contextmanager
    def _test_session():
        yield db_session

    db_mod.get_db_session = _test_session
    try:
        yield db_session
    finally:
        db_mod.get_db_session = original


@pytest.fixture(autouse=True)
def stub_router(monkeypatch):
    class _Stub:
        async def decide(self, context):
            return {"decision": "WAIT",
                    "rationale": "stub wait",
                    "wait_spec": {"event": "timer",
                                  "deadline": "2026-10-01T00:00:00+00:00"},
                    "confidence": 0.9}

    monkeypatch.setattr(GoalRunService, "_default_router",
                        lambda self: _Stub())


@pytest.fixture(autouse=True)
def silence_side_effects(monkeypatch):
    monkeypatch.setattr(
        "core.goals.goal_run_notifications.schedule_notification",
        lambda coro: coro.close() if hasattr(coro, "close") else None)

    async def _noop_outcome(service, run, outcome):
        return None

    monkeypatch.setattr(
        "core.goals.goal_run_learning.record_run_outcome", _noop_outcome)


@pytest.fixture
def env(db_session):
    db_session.add(User(
        id="lead-a", email="lead-a@example.com", first_name="Lead",
        last_name="A", role=UserRole.TEAM_LEAD.value, status="active"))
    db_session.add(User(
        id="lead-b", email="lead-b@example.com", first_name="Lead",
        last_name="B", role=UserRole.TEAM_LEAD.value, status="active"))
    db_session.add(User(
        id="member-a", email="member-a@example.com", first_name="Mem",
        last_name="A", role=UserRole.MEMBER.value, status="active"))
    db_session.add(User(
        id="member-a2", email="member-a2@example.com", first_name="Mem",
        last_name="A2", role=UserRole.MEMBER.value, status="active"))
    db_session.add(GoalObjective(
        id="goal-a", workspace_id=WS_A, tenant_id="default",
        title="Acme goal", status="active"))
    # The run under attack: workspace A, started by member-a. The decision
    # log carries text a workspace-B reader must never see.
    db_session.add(GoalRun(
        id="run-a", workspace_id=WS_A, tenant_id="default",
        goal_id="goal-a", status="active", supervision_mode="shadow",
        plan=[{"id": "s1", "kind": "canvas_work", "title": "Acme step"}],
        cursor="s1", created_by="member-a",
        decision_log=[{"ts": "2026-09-13T00:00:00+00:00",
                       "kind": "decision", "decision": "ADVANCE",
                       "rationale": "acme@acme.internal quote details"}]))
    db_session.commit()
    return db_session


def _client(env, user_id: str, workspace: str) -> TestClient:
    app = FastAPI()
    app.include_router(goal_runs_router)
    user = Mock(id=user_id, tenant_id=None, status="active",
                workspace_id=workspace)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[_get_db] = lambda: env
    return TestClient(app)


# ------------------------------------------------------ service-level scope

class TestServiceWorkspaceScoping:

    def test_other_workspace_service_cannot_read_the_run(self, env):
        svc_b = GoalRunService(workspace_id=WS_B, tenant_id="default")
        assert svc_b.get_run("run-a") is None
        assert svc_b.get_decisions("run-a") == []
        assert svc_b.list_runs() == []

    def test_own_workspace_service_reads_it(self, env):
        svc_a = GoalRunService(workspace_id=WS_A, tenant_id="default")
        run = svc_a.get_run("run-a")
        assert run and run["id"] == "run-a"
        assert svc_a.get_decisions("run-a")[0]["decision"] == "ADVANCE"

    def test_other_workspace_service_cannot_mutate(self, env):
        """The transition/writes go through _load — scoped the same way as
        the reads, so a team_lead service of workspace B cannot cancel or
        advance workspace A's run."""
        from core.goals.goal_run_service import GoalRunTransitionError
        svc_b = GoalRunService(workspace_id=WS_B, tenant_id="default")
        with pytest.raises(GoalRunTransitionError):
            svc_b.transition("run-a", "cancelled")
        with pytest.raises(ValueError):
            svc_b.set_wait("run-a", {"event": "timer"})
        with pytest.raises(ValueError):
            svc_b.patch_parameters("run-a", {"x": 1})
        # nothing changed
        svc_a = GoalRunService(workspace_id=WS_A, tenant_id="default")
        assert svc_a.get_run("run-a")["status"] == "active"

    def test_advance_from_wrong_workspace_is_a_no_op_not_found(self, env):
        svc_b = GoalRunService(workspace_id=WS_B, tenant_id="default")
        out = asyncio.run(svc_b.advance("run-a"))
        assert out == {"advanced": False, "reason": "run not found"}


# ----------------------------------------------------------- route-level

class TestRouteAccess:

    def test_cross_workspace_reads_are_404_not_data(self, env):
        """The IDOR: lead-b (team_lead of workspace B) must not read
        workspace A's run, decisions or canvases — 404, never the payload."""
        client = _client(env, "lead-b", WS_B)
        assert client.get("/api/goal-runs/run-a").status_code == 404
        assert (client.get("/api/goal-runs/run-a/decisions")
                .status_code) == 404
        assert (client.get("/api/goal-runs/run-a/canvases")
                .status_code) == 404

    def test_cross_workspace_writes_are_404(self, env):
        client = _client(env, "lead-b", WS_B)
        assert client.post("/api/goal-runs/run-a/advance").status_code == 404
        assert client.post("/api/goal-runs/run-a/cancel").status_code == 404

    def test_same_workspace_member_non_owner_is_403(self, env):
        client = _client(env, "member-a2", WS_A)
        resp = client.post("/api/goal-runs/run-a/advance")
        assert resp.status_code == 403
        assert client.get("/api/goal-runs/run-a").status_code == 200

    def test_owner_and_workspace_supervisor_can_act(self, env):
        owner = _client(env, "member-a", WS_A)
        assert owner.post("/api/goal-runs/run-a/advance").status_code == 200
        lead = _client(env, "lead-a", WS_A)
        assert lead.post("/api/goal-runs/run-a/advance").status_code == 200

    def test_run_still_visible_to_its_owner_after_scoping(self, env):
        owner = _client(env, "member-a", WS_A)
        body = owner.get("/api/goal-runs/run-a").json()
        assert body["id"] == "run-a"
        assert owner.get("/api/goal-runs/run-a/decisions").json()[
            "decisions"][0]["decision"] == "ADVANCE"


# ------------------------------------------------- agent action surface

class TestAgentListDetailScoping:

    def test_goal_runs_list_detail_is_workspace_scoped(self, env):
        """goal_runs.list with run_id used svc.get_run (id-only) — an
        agent in workspace B could read workspace A's run detail."""
        from core.action_registry import action_registry
        in_b = asyncio.run(action_registry.execute_action(
            "goal_runs.list", {"run_id": "run-a"},
            {"workspace_id": WS_B, "tenant_id": "default",
             "agent_id": "agent-b"}))
        assert in_b["success"] is False
        assert "not found" in in_b["error"]
        assert "run" not in in_b

        in_a = asyncio.run(action_registry.execute_action(
            "goal_runs.list", {"run_id": "run-a"},
            {"workspace_id": WS_A, "tenant_id": "default",
             "agent_id": "agent-a"}))
        assert in_a["success"] is True
        assert in_a["run"]["id"] == "run-a"
