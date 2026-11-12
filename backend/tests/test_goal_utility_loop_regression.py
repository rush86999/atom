"""GOAL-02 regression: utility ranking from REAL executed Goal Runs.

The existing utility-target controls (``test_goal_utility_target.py``) seed
``GoalRun`` rows directly to exercise scoring. This regression instead builds
the evidence the way production does it:

- the goal (with its persisted utility target) is created through the public
  ``POST /api/goals`` boundary;
- every ``GoalRun`` row is created by ``GoalRunService.create_run`` and driven
  through the real ``GoalRunService.advance`` loop with a scripted router and
  the real executors (agent delegation short-circuited, exactly like
  ``test_goal_run_loop.py``);
- the ranking metrics (``steps_executed`` / ``human_interventions``) are only
  ever written by the loop, never by this test.

Two completed strategies therefore carry different *loop-derived* metrics:
a thorough training-mode run (3 held approvals, 2 executed steps) and a lean
shadow-mode run (1 held approval, 1 executed step). A third, cancelled run has
the best raw metric of all and must still be withheld because it never
completed. The scratch sqlite is then closed and reopened with fresh services
(and a fresh HTTP client) to prove the ranking is durable and derived from the
persisted run history.

Scratch DB only: the repo pytest bootstrap (``tests/conftest.py``) forces
``TESTING=1`` and a test-only ``DATABASE_URL``, and the per-test ``tmp_path``
scratch sqlite isolates every run. This module mutates no environment and
still makes no live DB, model, provider, notification, or network call.
"""

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.goals.goal_run_executors import GoalRunExecutors
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.models import (
    AuditLog,
    Canvas,
    CanvasAudit,
    GoalObjective,
    GoalRun,
    HITLAction,
    User,
    UserRole,
)

WORKSPACE = "ws-goal02"
TENANT = "default"
LEAD_ID = "goal02-lead"

TARGET_MIN_INTERVENTIONS = {
    "metric": "human_interventions",
    "direction": "minimize",
    "source": "goal_run",
    "description": "prefer strategies that need less supervision",
}

# Deliberately manual: the goal can never become machine-satisfied, so a run
# reaches ``achieved`` only through the loop's verified/approved DONE path.
MANUAL_CRITERIA = [{"type": "manual", "note": "supervisor signs off"}]

THOROUGH_PLAN = [
    {"id": "draft", "kind": "canvas_work", "title": "Draft the quote",
     "canvas_type": "document"},
    {"id": "review", "kind": "canvas_work", "title": "Review the quote",
     "canvas_type": "document"},
]
LEAN_PLAN = [
    {"id": "draft", "kind": "canvas_work", "title": "Draft the quote",
     "canvas_type": "document"},
]

# Decisions that actually execute a step and therefore increment the durable
# ``steps_executed`` counter (GoalRunService.execute_decision).
EXECUTED_STEP_DECISIONS = (
    "ADVANCE", "BRANCH_NEW_CANVAS", "SKIP", "REVISE_CURRENT",
)


def _decision(kind, **extra):
    return {"decision": kind, "rationale": f"scripted {kind}",
            "confidence": 0.9, **extra}


class ScriptedRouter:
    """Deterministic router: one scripted decision per advance() call."""

    def __init__(self, decisions):
        self.decisions = [_decision(d) if isinstance(d, str) else d
                          for d in decisions]
        self.calls = []

    async def decide(self, context):
        self.calls.append(context)
        if not self.decisions:
            raise AssertionError("scripted router exhausted")
        return self.decisions.pop(0)


class ControlledExecutors(GoalRunExecutors):
    """Real executors with only agent delegation short-circuited (same
    approach as test_goal_run_loop.RecordingExecutors)."""

    async def _delegate_agent_work(self, run, step_id, directive, canvas_id):
        return False


def _client(factory):
    """Public goal API bound to a fresh session per request."""
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.goal_routes import router as goals_router
    from core.auth import get_current_user
    from core.database import get_db

    app = FastAPI()
    app.include_router(goals_router)
    user = SimpleNamespace(
        id=LEAD_ID, tenant_id=TENANT, status="active",
        workspace_id=WORKSPACE, role=UserRole.TEAM_LEAD.value)

    def _session():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = _session
    return TestClient(app)


def _advance(svc, run_id, router, executors):
    return asyncio.run(svc.advance(run_id, router=router, executors=executors))


def _approve(svc, run_id):
    pending = svc.get_run(run_id)["pending_decision"]
    result = asyncio.run(svc.resume(
        run_id, approved=True, reviewer=LEAD_ID,
        expected_decision_id=pending["decision_id"],
        expected_decision_binding=pending["decision_binding"]))
    assert result.get("resumed") is True, result
    return result


def _drive_scripted_run(svc, executors, goal_id, plan, mode, decisions):
    """Create one run through the public service API and drive it with the
    scripted router. Every held decision is approved through ``resume`` so the
    loop itself writes the intervention and step counters."""
    created = svc.create_run(goal_id, supervision_mode=mode, plan=plan)
    run_id = created["id"]
    svc.transition(run_id, "active")
    router = ScriptedRouter(decisions)
    for _ in decisions:
        out = _advance(svc, run_id, router, executors)
        assert out.get("advanced") is True, out
        if out.get("held"):
            assert out["run"]["status"] == "paused_hitl", out
            _approve(svc, run_id)
    return svc.get_run(run_id)


@pytest.fixture()
def executed_world(tmp_path):
    """Execute the two completed strategies plus one incomplete run in a
    per-test scratch sqlite file, then close the engine. Tests reopen the
    file through fresh sessions/engines."""
    db_path = tmp_path / "runs.db"
    engine = create_engine(f"sqlite:///{db_path}")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  Canvas.__table__, CanvasAudit.__table__,
                  HITLAction.__table__, User.__table__, AuditLog.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    with factory() as session:
        session.add(User(
            id=LEAD_ID, email="goal02-lead@example.com",
            first_name="Goal", last_name="Lead",
            role=UserRole.TEAM_LEAD.value, status="active", is_active=True,
            workspace_id=WORKSPACE, tenant_id=TENANT))
        session.commit()

    # Ordinary public API: goal + persisted utility target.
    client = _client(factory)
    created = client.post("/api/goals", json={
        "title": "Quote every qualified lead",
        "description": "GOAL-02 loop-derived ranking regression",
        "criteria": MANUAL_CRITERIA,
        "utility_target": TARGET_MIN_INTERVENTIONS,
    })
    assert created.status_code == 200, created.text
    goal_id = created.json()["goal"]["id"]
    assert created.json()["goal"]["utility_target"] == \
        TARGET_MIN_INTERVENTIONS

    svc = GoalRunService(workspace_id=WORKSPACE, tenant_id=TENANT,
                         session_factory=factory)
    executors = ControlledExecutors(svc)

    # Strategy A — thorough: training mode holds every decision, so the loop
    # records 3 human interventions and executes 2 canvas steps.
    thorough = _drive_scripted_run(
        svc, executors, goal_id, THOROUGH_PLAN, "training",
        ["ADVANCE", "ADVANCE", "DONE"])

    # Strategy B — lean: shadow mode executes the single step without a hold
    # and needs one approval only for the DONE claim. 1 intervention, 1 step.
    lean = _drive_scripted_run(
        svc, executors, goal_id, LEAN_PLAN, "shadow",
        ["ADVANCE", "DONE"])

    # Strategy C — incomplete: real loop turn (1 executed step, 0
    # interventions), then cancelled through the public lifecycle API. Its
    # raw metric is better than the winner's, so only completion may withhold
    # it from ranking.
    incomplete_created = svc.create_run(
        goal_id, supervision_mode="shadow", plan=list(LEAN_PLAN))
    incomplete_id = incomplete_created["id"]
    svc.transition(incomplete_id, "active")
    out = _advance(svc, incomplete_id,
                   ScriptedRouter(["ADVANCE"]), executors)
    assert out.get("advanced") is True and not out.get("held"), out
    cancelled = svc.cancel(incomplete_id, reason="superseded by lean strategy")
    assert cancelled["status"] == "cancelled"
    incomplete = svc.get_run(incomplete_id)

    assert thorough["status"] == "achieved"
    assert lean["status"] == "achieved"
    assert incomplete["status"] == "cancelled"

    captured = {
        "path": db_path,
        "goal_id": goal_id,
        "runs": {"thorough": thorough, "lean": lean,
                 "incomplete": incomplete},
        "run_ids": {thorough["id"], lean["id"], incomplete_id},
    }
    engine.dispose()
    return captured


def _reopen(world):
    engine = create_engine(f"sqlite:///{world['path']}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return engine, factory


def test_two_completed_strategies_rank_from_loop_derived_metrics_after_reopen(
        executed_world):
    thorough = executed_world["runs"]["thorough"]
    lean = executed_world["runs"]["lean"]

    # The metrics under comparison were written by the loop, not the test.
    assert (thorough["human_interventions"], thorough["steps_executed"]) == (3, 2)
    assert (lean["human_interventions"], lean["steps_executed"]) == (1, 1)
    assert thorough["steps_executed"] != lean["steps_executed"]
    assert thorough["human_interventions"] != lean["human_interventions"]

    engine, factory = _reopen(executed_world)
    try:
        service = GoalService(workspace_id=WORKSPACE, tenant_id=TENANT,
                              session_factory=factory)
        ranking = service.utility_ranking(executed_world["goal_id"])
        assert ranking is not None
        assert ranking["target"] == TARGET_MIN_INTERVENTIONS
        assert ranking["winner"] == lean["id"]
        assert ranking["eligible_count"] == 2
        assert len(ranking["ranking"]) == 3

        by_id = {entry["id"]: entry for entry in ranking["ranking"]}
        assert by_id[lean["id"]]["eligible"] is True
        assert by_id[lean["id"]]["rank"] == 1
        assert by_id[lean["id"]]["utility"] == -1.0
        assert by_id[thorough["id"]]["eligible"] is True
        assert by_id[thorough["id"]]["rank"] == 2
        assert by_id[thorough["id"]]["utility"] == -3.0
        assert [entry["id"] for entry in ranking["ranking"]] == [
            lean["id"], thorough["id"], executed_world["runs"]["incomplete"]["id"]]

        for expected in (lean, thorough):
            evidence = by_id[expected["id"]]["evidence"]
            assert evidence["source"] == "goal_runs"
            assert evidence["run_id"] == expected["id"]
            assert evidence["goal_id"] == executed_world["goal_id"]
            assert evidence["status"] == "achieved"
            assert evidence["supervision_mode"] == expected["supervision_mode"]
            assert evidence["updated_at"]
    finally:
        engine.dispose()


def test_persisted_counters_match_the_loop_history_not_synthetic_rows(
        executed_world):
    """Reopened rows contain only the runs the loop created, and each run's
    durable counters equal what its own persisted decision log records."""
    engine, factory = _reopen(executed_world)
    try:
        service = GoalRunService(workspace_id=WORKSPACE, tenant_id=TENANT,
                                 session_factory=factory)
        runs = service.list_runs(goal_id=executed_world["goal_id"],
                                 include_terminal=True)
        assert {run["id"] for run in runs} == executed_world["run_ids"]
        assert len(runs) == 3

        for run in runs:
            log = run["decision_log"]
            held = sum(1 for entry in log
                       if entry.get("kind") == "held_for_approval")
            executed_steps = sum(
                1 for entry in log
                if entry.get("kind") == "decision"
                and entry.get("decision") in EXECUTED_STEP_DECISIONS)
            assert run["human_interventions"] == held, run["id"]
            assert run["steps_executed"] == executed_steps, run["id"]
            assert all(entry.get("ts") for entry in log), run["id"]
            if run["status"] == "achieved":
                assert any(entry.get("kind") == "run_done"
                           for entry in log), run["id"]

        # Completion came from the loop's verified/approved DONE path, not
        # from pre-satisfied goal criteria.
        goal = GoalService(workspace_id=WORKSPACE, tenant_id=TENANT,
                           session_factory=factory).get_goal(
            executed_world["goal_id"])
        assert goal["status"] == "active"
        assert goal["progress"] == 0.0
        assert goal["utility_target"] == TARGET_MIN_INTERVENTIONS
    finally:
        engine.dispose()


def test_incomplete_run_is_withheld_after_reopen(executed_world):
    incomplete = executed_world["runs"]["incomplete"]

    # It has the best raw metric (0 interventions) yet never reached the goal.
    assert incomplete["human_interventions"] == 0
    assert incomplete["human_interventions"] < \
        executed_world["runs"]["lean"]["human_interventions"]

    engine, factory = _reopen(executed_world)
    try:
        ranking = GoalService(
            workspace_id=WORKSPACE, tenant_id=TENANT,
            session_factory=factory).utility_ranking(
                executed_world["goal_id"])
        entry = next(item for item in ranking["ranking"]
                     if item["id"] == incomplete["id"])
        assert entry["eligible"] is False
        assert entry["rank"] is None
        assert entry["utility"] is None
        assert entry["reason"] == "not_completed"
        assert entry["evidence"]["status"] == "cancelled"
        assert entry["evidence"]["run_id"] == incomplete["id"]
        assert incomplete["id"] != ranking["winner"]
        assert ranking["eligible_count"] == 2
    finally:
        engine.dispose()


def test_fresh_public_api_serves_the_same_durable_ranking(executed_world):
    engine, factory = _reopen(executed_world)
    try:
        # Fresh engine + fresh sessions: nothing is served from the writer's
        # in-memory state.
        client = _client(factory)
        response = client.get(
            f"/api/goals/{executed_world['goal_id']}/utility")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["target"] == TARGET_MIN_INTERVENTIONS
        assert body["winner"] == executed_world["runs"]["lean"]["id"]
        assert body["eligible_count"] == 2
        assert [entry["id"] for entry in body["ranking"]] == [
            executed_world["runs"]["lean"]["id"],
            executed_world["runs"]["thorough"]["id"],
            executed_world["runs"]["incomplete"]["id"],
        ]
        withheld = body["ranking"][-1]
        assert withheld["eligible"] is False
        assert withheld["reason"] == "not_completed"
        assert withheld["rank"] is None
        assert withheld["utility"] is None

        goal = client.get(f"/api/goals/{executed_world['goal_id']}")
        assert goal.status_code == 200, goal.text
        assert goal.json()["utility_target"] == TARGET_MIN_INTERVENTIONS
        assert goal.json()["status"] == "active"
    finally:
        engine.dispose()
