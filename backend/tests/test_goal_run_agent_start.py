"""Agent-started goal runs (2026-09-12).

``goal_runs.start`` / ``goal_runs.list`` close the last severed link in the
"start → work → finish a long-running goal" journey: the AGENT side. A human
could start a run (``POST /api/goal-runs``); an agent could create the goal
(``goals.create``) but not the run — so the agent always had to hand the work
back to the user for the boring part.

The agent surface deliberately mirrors the MEMBER ladder from
api/goal_run_routes (role from the bound agent's own data, playbook-seeded
plan, training/shadow only, governance knobs stripped) plus one extra guard
the human API doesn't need: an agent directs only ITSELF, and may not stack
duplicate runs of the same goal.

Pattern: direct action_registry.execute_action on the conftest scratch DB
(get_db_session routed to the test session — the same fixture shape
test_canvas_version_tools uses), stub router like test_goal_journey_gaps.
"""

import asyncio
import os
from contextlib import contextmanager

import pytest

os.environ.setdefault("TESTING", "1")

import core.database as db_mod
from core.action_registry import action_registry
from core.models import AgentRegistry, GoalRun, GoalObjective, User, UserRole

WS = "ws-agent-run"
CTX = {"workspace_id": WS, "tenant_id": "default",
       "agent_id": "agent-sales", "user_id": "u-owner"}


@pytest.fixture(autouse=True)
def patched_session(db_session):
    """Route core.database.get_db_session to the test session — the action
    and GoalRunService both open their own sessions through it."""
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
    """Deterministic router: always ADVANCE (the real router is a live LLM
    call, covered in test_goal_run_loop.py)."""

    class _Stub:
        async def decide(self, context):
            return {"decision": "ADVANCE", "rationale": "stub",
                    "confidence": 0.9}

    from core.goals.goal_run_service import GoalRunService
    monkeypatch.setattr(GoalRunService, "_default_router", lambda self: _Stub())


@pytest.fixture(autouse=True)
def silence_side_effects(monkeypatch):
    """Holds/waits fan out notifications on the REAL session; keep the
    scratch-DB tests hermetic (same shape as test_goal_journey_gaps)."""
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
        id="u-owner", email="owner@example.com", first_name="Ow",
        last_name="Ner", role=UserRole.MEMBER.value, status="active"))
    db_session.add(AgentRegistry(
        id="agent-sales", name="Sales Agent", category="Sales",
        specialty="sales", module_path="agents.sales",
        class_name="SalesAgent", status="active"))
    db_session.add(GoalObjective(
        id="goal-a", workspace_id=WS, tenant_id="default",
        title="Prepare a quote for the WFS lead", status="active"))
    db_session.commit()
    return db_session


def _start(env, args=None, context=None):
    return asyncio.run(action_registry.execute_action(
        "goal_runs.start", args or {"goal_id": "goal-a"},
        context or CTX))


# ------------------------------------------------------------- start

class TestAgentStartsRun:

    def test_start_creates_working_run_bound_to_the_agent(self, env):
        result = _start(env)
        assert result["success"] is True, result
        assert result["seed_source"] == "fallback"  # no playbooks on scratch DB
        assert result["run_url"] == f"/goal-runs/{result['id']}"
        assert result["started"]["advanced"] is True

        run = env.query(GoalRun).filter(GoalRun.id == result["id"]).one()
        assert run.agent_id == "agent-sales"
        # role derived from the business's own data (agent specialty)
        assert run.role == "sales"
        assert run.status == "active"
        # "start" means started: the first loop turn ran
        assert run.steps_executed >= 1
        assert any(d.get("kind") == "decision" for d in run.decision_log)
        # the owner (the human the agent acts for) is the creator — the
        # notifications route to them, not to the agent
        assert run.created_by == "u-owner"
        # provenance the run page can show
        assert any(d.get("kind") == "started_by_agent"
                   and d.get("agent_id") == "agent-sales"
                   for d in run.decision_log)

    def test_role_explicit_beats_agent_derivation(self, env):
        result = _start(env, {"goal_id": "goal-a", "role": "field sales"})
        assert result["success"] is True
        assert env.query(GoalRun).filter(
            GoalRun.id == result["id"]).one().role == "field sales"

    def test_training_mode_holds_first_decision_for_the_owner(self, env):
        result = _start(env, {"goal_id": "goal-a",
                              "supervision_mode": "training"})
        assert result["success"] is True
        run = env.query(GoalRun).filter(GoalRun.id == result["id"]).one()
        assert run.status == "paused_hitl"
        assert run.pending_decision["decision"] == "ADVANCE"
        assert run.supervision_mode == "training"

    def test_start_false_stages_a_dormant_run(self, env):
        result = _start(env, {"goal_id": "goal-a", "start": False})
        assert result["success"] is True
        run = env.query(GoalRun).filter(GoalRun.id == result["id"]).one()
        assert run.status == "active"
        assert run.steps_executed == 0

    def test_governance_params_stripped(self, env):
        result = _start(env, {
            "goal_id": "goal-a", "start": False,
            "parameters": {"replan_budget": 99, "wait_ceiling_days": 365,
                           "region": "emea"}})
        assert result["success"] is True
        params = env.query(GoalRun).filter(
            GoalRun.id == result["id"]).one().parameters
        assert "replan_budget" not in params
        assert "wait_ceiling_days" not in params
        assert params.get("region") == "emea"


# -------------------------------------------------------------- guards

class TestAgentStartGuards:

    def test_no_self_promotion_to_autonomous(self, env):
        result = _start(env, {"goal_id": "goal-a",
                              "supervision_mode": "autonomous"})
        assert result["success"] is False
        assert "autonomous" in result["error"]

    def test_agent_directs_only_itself(self, env):
        result = _start(env, {"goal_id": "goal-a",
                              "agent_id": "agent-somebody-else"})
        assert result["success"] is False
        assert "only for itself" in result["error"]

    def test_agentless_context_refused(self, env):
        result = _start(env, {"goal_id": "goal-a"},
                        {"workspace_id": WS, "tenant_id": "default"})
        assert result["success"] is False
        assert "role-bound" in result["error"]

    def test_unknown_goal(self, env):
        result = _start(env, {"goal_id": "goal-nope"})
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_goal_from_another_workspace_refused(self, env):
        env.add(GoalObjective(id="goal-elsewhere", workspace_id="ws-other",
                              tenant_id="default", title="Elsewhere",
                              status="active"))
        env.commit()
        result = _start(env, {"goal_id": "goal-elsewhere"})
        assert result["success"] is False
        assert "another workspace" in result["error"]

    def test_duplicate_active_run_refused(self, env):
        first = _start(env)
        assert first["success"] is True
        second = _start(env)
        assert second["success"] is False
        assert second["id"] == first["id"]
        # and nothing new was created
        assert env.query(GoalRun).count() == 1

    def test_finished_run_does_not_block_a_new_one(self, env):
        first = _start(env, {"goal_id": "goal-a", "start": False})
        from core.goals.goal_run_service import GoalRunService
        svc = GoalRunService(workspace_id=WS, tenant_id="default")
        svc.cancel(first["id"])
        again = _start(env)
        assert again["success"] is True
        assert again["id"] != first["id"]


# --------------------------------------------------------------- listing

class TestAgentListsRuns:

    def test_list_shows_the_run_summary(self, env):
        started = _start(env)
        out = asyncio.run(action_registry.execute_action(
            "goal_runs.list", {}, CTX))
        assert out["success"] is True
        match = [r for r in out["runs"] if r["id"] == started["id"]]
        assert match, out
        summary = match[0]
        assert summary["status"] == "active"
        assert summary["role"] == "sales"
        assert summary["next_step"], "summary should name the current step"
        assert "decision_log" not in summary  # compact — no raw log in lists

    def test_run_detail_carries_plan_and_decisions(self, env):
        started = _start(env)
        out = asyncio.run(action_registry.execute_action(
            "goal_runs.list", {"run_id": started["id"]}, CTX))
        assert out["success"] is True
        run = out["run"]
        assert run["plan"], "detail should expose the plan"
        assert any(d.get("kind") == "started_by_agent"
                   for d in run["recent_decisions"])

    def test_goal_filter_and_unknown_run(self, env):
        _start(env)
        filtered = asyncio.run(action_registry.execute_action(
            "goal_runs.list", {"goal_id": "goal-a"}, CTX))
        assert all(r["goal_id"] == "goal-a" for r in filtered["runs"])
        assert filtered["runs"]

        missing = asyncio.run(action_registry.execute_action(
            "goal_runs.list", {"run_id": "run-nope"}, CTX))
        assert missing["success"] is False
