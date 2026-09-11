"""GoalRun user-journey gap closure (2026-09-10).

The trace of "start → work → finish a long-running goal for an agent" found
three severed links at the START of the journey and two at the FINISH:

A. The WHAT had no user-facing surface. Goals were creatable only by the
   agent action ``goals.create``; nothing listed them and nothing exposed
   them over HTTP, so a supervisor could not pick or create the goal a run
   needs (``POST /api/goal-runs`` 404s on an unknown goal). → ``/api/goals``.
B. Starting a run did not start it. ``POST /api/goal-runs`` activated the
   row and returned — nothing ran the first loop turn, so a freshly started
   run sat ``active`` with a cursor and did no work until a human found the
   "Advance" button (and the UI had no way to create the run at all).
   → ``start`` kicks off the first ``advance()``.
C. Terminal runs kept accepting "advance" with a 200 no-op, which the UI
   reported as success ("Advanced one decision cycle") while nothing moved.

Pattern: isolated FastAPI app + dependency overrides (mirrors
test_goal_run_routes.py) on the conftest worker scratch DB.
"""

import os
from contextlib import contextmanager
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("TESTING", "1")

from api.goal_routes import router as goals_router
from api.goal_run_routes import router as goal_runs_router
from core.auth import get_current_user
from core.database import get_db as _get_db
from core.models import AgentRegistry, Canvas, GoalObjective, GoalRun, User, UserRole


def _make_app(db, viewer_id: str) -> TestClient:
    app = FastAPI()
    app.include_router(goals_router)
    app.include_router(goal_runs_router)
    user = Mock(id=viewer_id, tenant_id=None, status="active",
                workspace_id="ws-test")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[_get_db] = lambda: db
    return TestClient(app)


@pytest.fixture(autouse=True)
def stub_router(monkeypatch):
    """Deterministic router: always ADVANCE (the real router is a live LLM
    call and is covered in test_goal_run_loop.py)."""

    class _Stub:
        async def decide(self, context):
            return {"decision": "ADVANCE", "rationale": "stub", "confidence": 0.9}

    from core.goals.goal_run_service import GoalRunService
    monkeypatch.setattr(GoalRunService, "_default_router", lambda self: _Stub())


@pytest.fixture(autouse=True)
def silence_side_effects(monkeypatch):
    """Terminal transitions fan out notifications + world-model outcomes on
    the REAL session; keep the scratch-DB tests hermetic."""
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
        id="gj-lead", email="gj-lead@example.com", first_name="Goal",
        last_name="Lead", role=UserRole.TEAM_LEAD.value, status="active"))
    db_session.add(User(
        id="gj-emp", email="gj-emp@example.com", first_name="Emp",
        last_name="Loyee", role=UserRole.MEMBER.value, status="active"))
    db_session.add(User(
        id="gj-emp2", email="gj-emp2@example.com", first_name="Other",
        last_name="Member", role=UserRole.MEMBER.value, status="active"))
    db_session.commit()
    return db_session


# ------------------------------------------------------------------ A: goals

class TestGoalsSurface:
    def test_list_goals_is_any_signed_in(self, env):
        env.add(GoalObjective(id="g-listed", workspace_id="ws-test",
                              tenant_id=None, title="Prepare a quote",
                              status="active"))
        env.commit()
        client = _make_app(env, "gj-emp")
        resp = client.get("/api/goals")
        assert resp.status_code == 200, resp.text
        titles = [g["title"] for g in resp.json()["goals"]]
        assert "Prepare a quote" in titles

    def test_member_creates_simple_goal_but_not_criteria(self, env):
        """Role-based model: the person doing a piece of work (any business —
        a lead, a claim, a candidate) may create the goal for it. Criteria
        and target dates shape how every agent terminates → supervisor."""
        member = _make_app(env, "gj-emp")
        ok = member.post("/api/goals", json={"title": "Quote for a lead"})
        assert ok.status_code == 200, ok.text
        assert ok.json()["goal"]["title"] == "Quote for a lead"
        assert ok.json()["goal"]["owner_id"] == "gj-emp"
        gated = member.post("/api/goals", json={
            "title": "X", "criteria": [{"type": "manual"}]})
        assert gated.status_code == 403, gated.text
        assert "supervisor" in gated.json()["detail"]
        gated_date = member.post("/api/goals", json={
            "title": "X", "target_date": "2026-12-31"})
        assert gated_date.status_code == 403

        lead = _make_app(env, "gj-lead")
        resp = lead.post("/api/goals", json={
            "title": "Prepare a quote for the Acme lead",
            "description": "multi-touch process",
            "criteria": [{"type": "manual", "description": "lead replied"}]})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True and body["goal"]["id"]
        assert body["goal"]["title"] == "Prepare a quote for the Acme lead"
        assert body["goal"]["source"] == "api"
        # persisted + retrievable
        got = lead.get(f"/api/goals/{body['goal']['id']}").json()
        assert got["title"] == "Prepare a quote for the Acme lead"

    def test_create_goal_rejects_blank_title(self, env):
        lead = _make_app(env, "gj-lead")
        assert lead.post("/api/goals", json={"title": "   "}).status_code == 422

    def test_create_run_accepts_inline_new_goal_id(self, env):
        """The start dialog's flow: create goal → create run → run is live."""
        lead = _make_app(env, "gj-lead")
        goal_id = lead.post("/api/goals", json={
            "title": "Prepare a quote"}).json()["goal"]["id"]
        resp = lead.post("/api/goal-runs", json={
            "goal_id": goal_id, "role": "sales", "supervision_mode": "shadow"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["run"]["goal_id"] == goal_id


# ------------------------------------ role-based run access (any business type)

class TestRoleBasedRunAccess:
    """The sales/quoting case is ONE instance. The rule is general: whoever
    does the external-facing work in ANY business (support reps, claims
    handlers, recruiters, buyers) starts and works their OWN role-based run;
    team_lead+ keeps the broader powers."""

    def _goal(self, env, gid="goal-rbac"):
        env.add(GoalObjective(id=gid, workspace_id="ws-test", tenant_id=None,
                              title="Resolve a customer request",
                              status="active"))
        env.commit()
        return gid

    def test_member_starts_own_role_based_run(self, env):
        gid = self._goal(env)
        client = _make_app(env, "gj-emp")
        resp = client.post("/api/goal-runs", json={
            "goal_id": gid, "role": "support", "supervision_mode": "training"})
        assert resp.status_code == 200, resp.text
        run = resp.json()["run"]
        assert run["role"] == "support"
        assert run["created_by"] == "gj-emp"

    def test_role_derived_from_the_business_agent(self, env):
        """No hardcoded industry list: the role comes from the agent the
        business configured (specialty, else category)."""
        gid = self._goal(env)
        env.add(AgentRegistry(
            id="agent-support", name="Support Agent",
            category="Customer Service", specialty="support",
            module_path="agents.support", class_name="SupportAgent",
            status="active"))
        env.commit()
        client = _make_app(env, "gj-emp")
        resp = client.post("/api/goal-runs", json={
            "goal_id": gid, "agent_id": "agent-support"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["run"]["role"] == "support"

    def test_member_cannot_author_plan_or_self_promote(self, env):
        gid = self._goal(env)
        client = _make_app(env, "gj-emp")
        plan = client.post("/api/goal-runs", json={
            "goal_id": gid, "role": "support",
            "plan": [{"id": "s1", "kind": "canvas_work", "title": "x"}]})
        assert plan.status_code == 403, plan.text
        auto = client.post("/api/goal-runs", json={
            "goal_id": gid, "role": "support",
            "supervision_mode": "autonomous"})
        assert auto.status_code == 403, auto.text

    def test_member_governance_params_stripped(self, env):
        gid = self._goal(env)
        client = _make_app(env, "gj-emp")
        resp = client.post("/api/goal-runs", json={
            "goal_id": gid, "role": "support", "start": False,
            "parameters": {"replan_budget": 99, "wait_ceiling_days": 365,
                           "region": "emea"}})
        assert resp.status_code == 200, resp.text
        params = resp.json()["run"]["parameters"]
        assert "replan_budget" not in params
        assert "wait_ceiling_days" not in params
        assert params.get("region") == "emea"

    def test_member_without_role_or_agent_is_422(self, env):
        gid = self._goal(env)
        client = _make_app(env, "gj-emp")
        resp = client.post("/api/goal-runs", json={"goal_id": gid})
        assert resp.status_code == 422, resp.text

    def test_owner_acts_other_member_refused_supervisor_can(self, env):
        gid = self._goal(env)
        owner = _make_app(env, "gj-emp")
        run_id = owner.post("/api/goal-runs", json={
            "goal_id": gid, "role": "support", "start": False}).json()["id"]
        other = _make_app(env, "gj-emp2")
        assert other.post(f"/api/goal-runs/{run_id}/advance").status_code == 403
        assert other.post(f"/api/goal-runs/{run_id}/cancel").status_code == 403
        assert other.post(
            f"/api/goal-runs/{run_id}/checkpoints/h1/resolve",
            json={"approved": True}).status_code == 403
        assert owner.post(f"/api/goal-runs/{run_id}/advance").status_code == 200
        lead = _make_app(env, "gj-lead")
        assert lead.post(f"/api/goal-runs/{run_id}/advance").status_code == 200

    def test_owner_resolves_own_held_decision(self, env):
        gid = self._goal(env)
        owner = _make_app(env, "gj-emp")
        created = owner.post("/api/goal-runs", json={
            "goal_id": gid, "role": "support",
            "supervision_mode": "training"}).json()
        assert created["run"]["status"] == "paused_hitl"
        run_id = created["id"]
        other = _make_app(env, "gj-emp2")
        assert other.post(f"/api/goal-runs/{run_id}/resume",
                          json={"approved": True}).status_code == 403
        resumed = owner.post(f"/api/goal-runs/{run_id}/resume",
                             json={"approved": True})
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["resumed"] is True

    def test_member_cannot_change_mode_or_distill(self, env):
        """Promotion and distillation shape the whole role → supervisor."""
        gid = self._goal(env)
        owner = _make_app(env, "gj-emp")
        run_id = owner.post("/api/goal-runs", json={
            "goal_id": gid, "role": "support", "start": False}).json()["id"]
        assert owner.post(
            f"/api/goal-runs/{run_id}/mode",
            json={"supervision_mode": "autonomous"}).status_code == 403
        assert owner.post(f"/api/goal-runs/{run_id}/distill").status_code == 403


# --------------------------------------------------------------- B: kickoff

class TestRunStartsOnCreate:
    def _run(self, client, **overrides):
        payload = {"goal_id": "goal-start", "supervision_mode": "shadow",
                   "role": "sales"}
        payload.update(overrides)
        return client.post("/api/goal-runs", json=payload)

    def test_create_kicks_off_first_loop_turn(self, env):
        env.add(GoalObjective(id="goal-start", workspace_id="ws-test",
                              tenant_id=None, title="Prepare a quote",
                              status="active"))
        env.commit()
        client = _make_app(env, "gj-lead")
        resp = self._run(client)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        run = body["run"]
        # The first decision ran: a decision is logged and a linked canvas
        # exists — the run is actually working, not a dormant shell.
        assert run["steps_executed"] >= 1
        assert any(d.get("kind") == "decision" for d in run["decision_log"])
        canvases = client.get(f"/api/goal-runs/{run['id']}/canvases").json()
        assert canvases["canvases"], "first step produced no canvas"
        assert body["started"]["advanced"] is True

    def test_create_start_false_leaves_run_dormant(self, env):
        """Explicit opt-out keeps the create/start contract available to
        callers that want to stage a run (and keeps the pre-2026-09-10
        tests honest about which behavior they pin)."""
        env.add(GoalObjective(id="goal-start", workspace_id="ws-test",
                              tenant_id=None, title="Prepare a quote",
                              status="active"))
        env.commit()
        client = _make_app(env, "gj-lead")
        resp = self._run(client, start=False)
        assert resp.status_code == 200, resp.text
        run = resp.json()["run"]
        assert run["steps_executed"] == 0
        assert run["decision_log"] == []
        assert resp.json()["started"] is None

    def test_training_mode_kickoff_holds_first_decision(self, env):
        """Journey B step 1: the run starts and EVERY decision waits for the
        supervisor — the first one included."""
        env.add(GoalObjective(id="goal-start", workspace_id="ws-test",
                              tenant_id=None, title="Prepare a quote",
                              status="active"))
        env.commit()
        client = _make_app(env, "gj-lead")
        run = self._run(client, supervision_mode="training").json()["run"]
        assert run["status"] == "paused_hitl"
        assert run["pending_decision"]["decision"] == "ADVANCE"
        # and the held decision is resolvable through the normal journey
        resumed = client.post(f"/api/goal-runs/{run['id']}/resume",
                              json={"approved": True}).json()
        assert resumed["resumed"] is True


# -------------------------------------------------------------- C: terminal

class TestTerminalRunIsFinal:
    def _terminal(self, env, client, goal_id: str, status="achieved"):
        run_id = client.post("/api/goal-runs", json={
            "goal_id": goal_id, "start": False}).json()["id"]
        from core.goals.goal_run_service import GoalRunService

        @contextmanager
        def _sess():
            yield env

        svc = GoalRunService(workspace_id="ws-test", tenant_id="default",
                             session_factory=_sess)
        # create already activated the row (start=False only skips the loop turn)
        svc.transition(run_id, status)
        return run_id

    def test_advance_on_terminal_run_is_409_not_silent_success(self, env):
        env.add(GoalObjective(id="goal-term", workspace_id="ws-test",
                              tenant_id=None, title="Done", status="active"))
        env.commit()
        client = _make_app(env, "gj-lead")
        run_id = self._terminal(env, client, "goal-term")
        resp = client.post(f"/api/goal-runs/{run_id}/advance")
        assert resp.status_code == 409, resp.text
        assert "achieved" in resp.json()["detail"]

    def test_distill_allowed_for_failed_and_cancelled(self, env):
        """The doc's "finished run" includes failure/cancellation — the
        decision log of a failed run is exactly what a role should learn
        from. Route-level gate only; the learning fn is covered elsewhere."""
        for i, status in enumerate(("failed", "cancelled")):
            goal_id = f"goal-term-{i}"
            env.add(GoalObjective(id=goal_id, workspace_id="ws-test",
                                  tenant_id=None, title="Done", status="active"))
            env.commit()
            client = _make_app(env, "gj-lead")
            run_id = self._terminal(env, client, goal_id, status)
            resp = client.post(f"/api/goal-runs/{run_id}/distill")
            # 409 = "nothing to distill / deduped" (thin log), NOT
            # "run is still active" — the run is terminal so it passed the gate.
            assert resp.status_code == 409
            detail = resp.json()["detail"]
            assert "Nothing new to distill" in str(detail)
