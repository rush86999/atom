"""Agent-started goal runs (2026-09-12).

``goal_runs.start`` / ``goal_runs.list`` close the last severed link in the
"start → work → finish a long-running goal" journey: the AGENT side. A human
could start a run (``POST /api/goal-runs``); an agent could create the goal
(``goals.create``) but not the run — so the agent always had to hand the work
back to the user for the boring part.

The agent surface mirrors the MEMBER ladder from api/goal_run_routes (role
from the bound agent's own data, playbook-seeded plan, governance knobs
stripped) EXCEPT supervision, which follows the agent's EARNED maturity
(graduated autonomy): an AUTONOMOUS-maturity agent runs autonomous by
default; everyone else runs shadow; nobody below autonomous maturity may
request it. Extra guards the human API doesn't need: an agent directs only
ITSELF, and may not stack duplicate runs of the same goal. The loop itself
belongs to the agent too — the router sees the agent's maturity tier and
identity, and step work is delegated to the agent's own objective loop.

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
        class_name="SalesAgent", status="intern"))
    db_session.add(AgentRegistry(
        id="agent-trusted", name="Trusted Agent", category="Sales",
        specialty="sales", module_path="agents.sales",
        class_name="SalesAgent", status="autonomous"))
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

    def test_supervision_follows_earned_maturity(self, env):
        """Graduated autonomy: an AUTONOMOUS-maturity agent runs autonomous
        by default (HITL shrinks to the maturity-independent moments);
        everyone else defaults to shadow."""
        trusted_ctx = dict(CTX, agent_id="agent-trusted")
        result = asyncio.run(action_registry.execute_action(
            "goal_runs.start", {"goal_id": "goal-b"}, trusted_ctx))
        assert result["success"] is False  # goal-b doesn't exist yet
        env.add(GoalObjective(id="goal-b", workspace_id=WS,
                              tenant_id="default", title="Nurture the lead",
                              status="active"))
        env.commit()
        result = asyncio.run(action_registry.execute_action(
            "goal_runs.start", {"goal_id": "goal-b"}, trusted_ctx))
        assert result["success"] is True
        run = env.query(GoalRun).filter(GoalRun.id == result["id"]).one()
        assert run.supervision_mode == "autonomous"
        assert run.status == "active"  # no blanket hold on the first decision

        junior = _start(env, {"goal_id": "goal-a"})
        assert junior["success"] is True
        junior_run = env.query(GoalRun).filter(
            GoalRun.id == junior["id"]).one()
        assert junior_run.supervision_mode == "shadow"

    def test_trusted_agent_may_request_any_mode(self, env):
        env.add(GoalObjective(id="goal-c", workspace_id=WS,
                              tenant_id="default", title="Follow up",
                              status="active"))
        env.commit()
        result = asyncio.run(action_registry.execute_action(
            "goal_runs.start",
            {"goal_id": "goal-c", "supervision_mode": "training"},
            dict(CTX, agent_id="agent-trusted")))
        assert result["success"] is True
        assert env.query(GoalRun).filter(
            GoalRun.id == result["id"]).one().supervision_mode == "training"

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


# ------------------------------------------------- the loop belongs to the agent

class TestLoopBelongsToTheAgent:
    """The run is the agent's job assignment, not an independent mechanism:
    the router decision carries the agent's identity and EARNED maturity
    (ASK_HUMAN propensity scales with it), and the step work is executed by
    the agent's own objective loop under its own maturity gates."""

    def test_router_sees_agent_identity_and_maturity(self, env, monkeypatch):
        seen = {}

        class _CapturingRouter:
            async def decide(self, context):
                seen.update(context)
                return {"decision": "ADVANCE", "rationale": "stub",
                        "confidence": 0.9}

        from core.goals.goal_run_service import GoalRunService
        monkeypatch.setattr(GoalRunService, "_default_router",
                            lambda self: _CapturingRouter())
        result = _start(env, {"goal_id": "goal-a", "start": False})
        asyncio.run(GoalRunService(workspace_id=WS,
                                   tenant_id="default").advance(result["id"]))
        assert seen.get("maturity_tier") == "intern"
        assert seen.get("agent_name") == "Sales Agent"

    def test_step_work_delegates_to_the_agent(self, env, monkeypatch):
        """Delegation is the default path: the run's agent executes the
        step through its own GenericAgent loop (constructed from the real
        AgentRegistry row — the old call passed the id string where the
        constructor takes the model, so delegation never worked)."""
        import core.generic_agent as ga

        calls = {}

        class _StubAgent:
            def __init__(self, agent_model, workspace_id="default", **kw):
                calls["agent_id"] = agent_model.id
                calls["workspace_id"] = workspace_id

            async def execute(self, task, context=None, **kw):
                calls["task"] = task
                calls["context"] = context or {}
                return {"ok": True}

        monkeypatch.setattr(ga, "GenericAgent", _StubAgent)
        monkeypatch.setenv("ATOM_GOAL_RUN_AGENT_WORK", "1")
        result = _start(env, {"goal_id": "goal-a"})
        assert result["success"] is True
        assert result["started"]["result"]["agent_delegated"] is True
        assert calls["agent_id"] == "agent-sales"
        assert calls["workspace_id"] == WS
        assert calls["context"]["goal_run_id"] == result["id"]
        assert calls["context"]["goal_id"] == "goal-a"
        assert calls["context"]["user_id"] == "u-owner"
        assert calls["context"]["canvas_id"]

    def test_delegation_flag_forces_off(self, env, monkeypatch):
        import core.generic_agent as ga

        class _Boom:
            def __init__(self, *a, **kw):
                raise AssertionError("delegation must not construct an agent")

        monkeypatch.setattr(ga, "GenericAgent", _Boom)
        monkeypatch.setenv("ATOM_GOAL_RUN_AGENT_WORK", "0")
        result = _start(env, {"goal_id": "goal-a"})
        assert result["success"] is True
        assert result["started"]["result"]["agent_delegated"] is False

    def test_unavailable_agent_falls_back_to_co_editing(self, env, monkeypatch):
        """A paused agent (or a registry miss) keeps the canvas on the
        human co-editing path instead of delegating."""
        import core.generic_agent as ga

        class _Boom:
            def __init__(self, *a, **kw):
                raise AssertionError("paused agent must not be delegated to")

        monkeypatch.setattr(ga, "GenericAgent", _Boom)
        monkeypatch.setenv("ATOM_GOAL_RUN_AGENT_WORK", "1")
        env.query(AgentRegistry).filter(
            AgentRegistry.id == "agent-sales").one().status = "paused"
        env.commit()
        result = _start(env, {"goal_id": "goal-a"})
        assert result["success"] is True
        assert result["started"]["result"]["agent_delegated"] is False


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
