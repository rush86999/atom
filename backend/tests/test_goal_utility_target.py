"""GOAL-02: deterministic utility-target ranking for goal trajectories.

These controls exercise the real production services, not a disconnected
helper:

- ``GoalService`` persists the target on the existing GoalObjective row and
  ranks the goal's durable GoalRun rows;
- ``GoalService.evaluate`` exposes the read-only ranking without letting it
  change status/progress;
- ``GoalRunService`` -> ``GoalRunRouter`` consumes that durable summary on the
  production decision path.

Scratch sqlite only (TESTING=1, per-test temp file); no live DB, model, or
provider call.
"""

import math
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.agent_objective import Objective, objective_from_context
from core.goals.goal_run_router import GoalRunRouter
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.models import AuditLog, GoalObjective, GoalRun, User, UserRole

TARGET_MIN_INTERVENTIONS = {
    "metric": "human_interventions",
    "direction": "minimize",
    "source": "goal_run",
    "description": "prefer trajectories that need less supervision",
}


@pytest.fixture()
def world(tmp_path):
    db_path = tmp_path / f"goal02_utility_{uuid.uuid4().hex}.db"
    engine = create_engine(f"sqlite:///{db_path}")
    for table in (GoalObjective.__table__, GoalRun.__table__, User.__table__,
                  AuditLog.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return {"path": db_path, "engine": engine, "factory": factory}


def _add_goal(factory, goal_id="g-1", criteria=None, metadata=None):
    with factory() as session:
        session.add(GoalObjective(
            id=goal_id, tenant_id="t", workspace_id="ws",
            title=f"Goal {goal_id}", status="active",
            criteria=list(criteria or []),
            key_results=[], metadata_json=dict(metadata or {})))
        session.commit()


def _add_run(factory, run_id, goal_id="g-1", status="achieved",
             human_interventions=0, steps_executed=1, replan_count=0,
             decision_log=None, workspace_id="ws", created_at=None):
    with factory() as session:
        session.add(GoalRun(
            id=run_id, tenant_id="t", workspace_id=workspace_id,
            goal_id=goal_id,
            status=status, supervision_mode="shadow",
            plan=[], parameters={}, decision_log=list(decision_log or []),
            human_interventions=human_interventions,
            steps_executed=steps_executed, replan_count=replan_count,
            created_at=created_at))
        session.commit()


def _service(world):
    return GoalService(workspace_id="ws", tenant_id="t",
                       session_factory=world["factory"])


def _runs(world):
    return GoalRunService(workspace_id="ws", tenant_id="t",
                          session_factory=world["factory"])


class TestTargetDefinition:
    """Failure-first: only an explicit accepted definition earns a target."""

    @pytest.mark.parametrize("bad_target", [
        None,
        {},
        "human_interventions",
        {"metric": "human_interventions", "source": "goal_run"},
        {"metric": "unknown_metric", "direction": "minimize",
         "source": "goal_run"},
        {"metric": "human_interventions", "direction": "sideways",
         "source": "goal_run"},
        {"metric": "human_interventions", "direction": "minimize"},
        {"metric": "human_interventions", "direction": "minimize",
         "source": "caller_supplied"},
        {"metric": "human_interventions", "direction": "minimize",
         "source": "goal_run", "extra": 1},
    ])
    def test_malformed_target_is_rejected_before_persistence(self, world,
                                                             bad_target):
        _add_goal(world["factory"])
        with pytest.raises(ValueError):
            _service(world).set_utility_target("g-1", bad_target)
        assert _service(world).get_utility_target("g-1") is None

    def test_create_goal_persists_explicit_target(self, world):
        goal = _service(world).create_goal(
            "Reduce support handling time", utility_target=TARGET_MIN_INTERVENTIONS)
        assert goal["utility_target"]["metric"] == "human_interventions"
        assert goal["utility_target"]["direction"] == "minimize"

    def test_target_survives_fresh_service_engine_and_objective_injection(
            self, world):
        _add_goal(world["factory"])
        _service(world).set_utility_target("g-1", TARGET_MIN_INTERVENTIONS)
        world["engine"].dispose()

        fresh_engine = create_engine(f"sqlite:///{world['path']}")
        fresh_factory = sessionmaker(bind=fresh_engine, expire_on_commit=False)
        fresh = GoalService(workspace_id="ws", tenant_id="t",
                            session_factory=fresh_factory)
        assert fresh.get_utility_target("g-1") == TARGET_MIN_INTERVENTIONS
        objective = fresh.to_objective("g-1")
        assert objective.utility_target == TARGET_MIN_INTERVENTIONS
        fresh_engine.dispose()

    def test_clear_removes_the_signal(self, world):
        _add_goal(world["factory"])
        svc = _service(world)
        svc.set_utility_target("g-1", TARGET_MIN_INTERVENTIONS)
        assert svc.utility_ranking("g-1") is not None
        cleared = svc.clear_utility_target("g-1")
        assert cleared["utility_target"] is None
        assert svc.utility_ranking("g-1") is None


class TestDeterministicRanking:
    def test_higher_utility_ranks_higher_when_maximized(self, world):
        _add_goal(world["factory"])
        _add_run(world["factory"], "run-low", steps_executed=3)
        _add_run(world["factory"], "run-high", steps_executed=9)
        svc = _service(world)
        svc.set_utility_target("g-1", {
            "metric": "steps_executed", "direction": "maximize",
            "source": "goal_run"})

        ranking = svc.utility_ranking("g-1")
        assert ranking["winner"] == "run-high"
        assert [e["id"] for e in ranking["ranking"]] == [
            "run-high", "run-low"]
        assert ranking["ranking"][0]["utility"] == 9.0
        assert ranking["ranking"][0]["rank"] == 1
        assert ranking["ranking"][1]["utility"] == 3.0
        assert ranking["ranking"][1]["rank"] == 2

    def test_higher_utility_ranks_higher_when_minimized(self, world):
        _add_goal(world["factory"])
        _add_run(world["factory"], "run-chatty", human_interventions=5)
        _add_run(world["factory"], "run-clean", human_interventions=2)
        svc = _service(world)
        svc.set_utility_target("g-1", TARGET_MIN_INTERVENTIONS)

        ranking = svc.utility_ranking("g-1")
        assert ranking["winner"] == "run-clean"
        assert [e["id"] for e in ranking["ranking"]] == [
            "run-clean", "run-chatty"]
        # Normalized utility: a lower raw intervention count is HIGHER utility.
        assert ranking["ranking"][0]["utility"] > ranking["ranking"][1]["utility"]

    def test_failed_outcome_cannot_win_on_a_better_metric(self, world):
        _add_goal(world["factory"])
        _add_run(world["factory"], "run-completed", status="achieved",
                 human_interventions=5)
        _add_run(world["factory"], "run-failed", status="failed",
                 human_interventions=0)
        svc = _service(world)
        svc.set_utility_target("g-1", TARGET_MIN_INTERVENTIONS)

        ranking = svc.utility_ranking("g-1")
        assert ranking["winner"] == "run-completed"
        by_id = {e["id"]: e for e in ranking["ranking"]}
        assert by_id["run-failed"]["eligible"] is False
        assert by_id["run-failed"]["rank"] is None
        assert by_id["run-failed"]["reason"] == "not_completed"
        assert by_id["run-failed"]["utility"] is None

    def test_cancelled_run_cannot_win_even_with_a_better_metric(self, world):
        _add_goal(world["factory"])
        _add_run(world["factory"], "run-clean", human_interventions=5)
        _add_run(world["factory"], "run-cancelled", status="cancelled",
                 human_interventions=0)
        svc = _service(world)
        svc.set_utility_target("g-1", TARGET_MIN_INTERVENTIONS)

        ranking = svc.utility_ranking("g-1")
        assert ranking["winner"] == "run-clean"
        cancelled = next(e for e in ranking["ranking"]
                         if e["id"] == "run-cancelled")
        assert cancelled["eligible"] is False
        assert cancelled["rank"] is None
        assert cancelled["reason"] == "not_completed"

    def test_missing_and_nonfinite_metric_never_earns_a_rank(self):
        from core.goals.utility_target import (
            outcome_from_goal_run, rank_trajectories,
        )
        target = {"metric": "steps_executed", "direction": "maximize",
                  "source": "goal_run"}
        # The production projector is what GoalService.utility_ranking uses;
        # a run whose durable field is absent must stay unknown.
        projected = outcome_from_goal_run({
            "id": "run-missing", "goal_id": "g-1", "status": "achieved",
            "steps_executed": None,
        })
        ranking = rank_trajectories(target, [projected])
        missing = ranking["ranking"][0]
        assert ranking["winner"] is None
        assert missing["eligible"] is False
        assert missing["rank"] is None
        assert missing["utility"] is None
        assert missing["reason"] == "metric_unknown"

        objective = Objective(goal="maximize steps", utility_target=target)
        for bad in (float("nan"), float("inf"), float("-inf"),
                    "9", True):
            result = objective.rank_outcomes([{
                "id": "bad", "completed": True, "constraints_ok": True,
                "metrics": {"steps_executed": bad}}])
            assert result["winner"] is None
            assert result["ranking"][0]["reason"] == "metric_unknown"

    def test_negative_and_huge_counts_never_earn_a_rank(self, world):
        from core.goals.utility_target import (
            finite_metric, outcome_from_goal_run, rank_trajectories,
        )
        target = {"metric": "steps_executed", "direction": "maximize",
                  "source": "goal_run"}
        for bad in (-1, -5, 2.5, -1.0, 10 ** 400):
            assert finite_metric(bad) is None
        # A huge int must not raise OverflowError out of the production
        # projector/ranking path.
        projected = outcome_from_goal_run({
            "id": "run-huge", "goal_id": "g-1", "status": "achieved",
            "steps_executed": 10 ** 400,
        })
        ranking = rank_trajectories(target, [projected])
        assert ranking["winner"] is None
        assert ranking["ranking"][0]["reason"] == "metric_unknown"

        _add_goal(world["factory"])
        _add_run(world["factory"], "run-negative",
                 human_interventions=-2)
        _add_run(world["factory"], "run-clean", human_interventions=4)
        svc = _service(world)
        svc.set_utility_target("g-1", TARGET_MIN_INTERVENTIONS)
        durable = svc.utility_ranking("g-1")
        assert durable["winner"] == "run-clean"
        negative = next(e for e in durable["ranking"]
                        if e["id"] == "run-negative")
        assert negative["eligible"] is False
        assert negative["rank"] is None
        assert negative["reason"] == "metric_unknown"

    def test_constraints_gate_is_checked_before_utility(self):
        objective = Objective(
            goal="maximize useful work",
            utility_target={"metric": "steps_executed",
                            "direction": "maximize",
                            "source": "goal_run"})
        result = objective.rank_outcomes([
            {"id": "unsafe", "completed": True, "constraints_ok": False,
             "metrics": {"steps_executed": 10_000}},
            {"id": "safe", "completed": True, "constraints_ok": True,
             "metrics": {"steps_executed": 1}},
        ])
        assert result["winner"] == "safe"
        unsafe = next(e for e in result["ranking"] if e["id"] == "unsafe")
        assert unsafe["reason"] == "constraint_failed"
        assert unsafe["utility"] is None

    def test_missing_target_means_no_ranking(self, world):
        _add_goal(world["factory"])
        _add_run(world["factory"], "run-1")
        svc = _service(world)
        assert svc.utility_ranking("g-1") is None
        evaluated = svc.evaluate("g-1")
        assert "utility" not in evaluated

    def test_ranking_is_scoped_to_the_requested_goal_and_workspace(self, world):
        _add_goal(world["factory"], goal_id="g-1")
        _add_goal(world["factory"], goal_id="g-2")
        _add_run(world["factory"], "run-own", goal_id="g-1",
                 human_interventions=5)
        _add_run(world["factory"], "run-other-goal", goal_id="g-2",
                 human_interventions=0)
        _add_run(world["factory"], "run-other-workspace", goal_id="g-1",
                 workspace_id="ws-other", human_interventions=0)
        svc = _service(world)
        svc.set_utility_target("g-1", TARGET_MIN_INTERVENTIONS)

        ranking = svc.utility_ranking("g-1")
        assert ranking["winner"] == "run-own"
        assert [e["id"] for e in ranking["ranking"]] == ["run-own"]

    def test_complete_coverage_beyond_the_old_hundred_run_cap(self, world):
        """PR707 finding: the 101st (latest, best) run was silently omitted.

        Complete coverage means every terminal run for the scoped goal is
        compared; the winner is not an artifact of insertion order plus a
        hidden cap.
        """
        _add_goal(world["factory"], goal_id="g-1")
        started = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        for index in range(100):
            _add_run(world["factory"], f"run-old-{index:03d}",
                     human_interventions=10,
                     created_at=started + timedelta(seconds=index))
        # The best candidate is intentionally the 101st row by time.
        _add_run(world["factory"], "run-latest-best",
                 human_interventions=0,
                 created_at=started + timedelta(seconds=100))
        svc = _service(world)
        svc.set_utility_target("g-1", TARGET_MIN_INTERVENTIONS)

        ranking = svc.utility_ranking("g-1")
        assert ranking["eligible_count"] == 101
        assert len(ranking["ranking"]) == 101
        assert ranking["winner"] == "run-latest-best"
        assert ranking["ranking"][0]["id"] == "run-latest-best"
        assert ranking["ranking"][0]["rank"] == 1
        assert ranking["ranking"][0]["utility"] == 0.0

    def test_invalid_latest_candidate_beyond_cap_cannot_win(self, world):
        """Negative boundary twin: complete coverage still withholds unknown
        evidence at the 101st position; it cannot displace a known better-than
        nothing completed run."""
        _add_goal(world["factory"], goal_id="g-1")
        started = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        for index in range(100):
            _add_run(world["factory"], f"run-old-{index:03d}",
                     human_interventions=10,
                     created_at=started + timedelta(seconds=index))
        _add_run(world["factory"], "run-latest-invalid",
                 human_interventions=-1,
                 created_at=started + timedelta(seconds=100))
        svc = _service(world)
        svc.set_utility_target("g-1", TARGET_MIN_INTERVENTIONS)

        ranking = svc.utility_ranking("g-1")
        assert ranking["winner"] == "run-old-000"
        invalid = next(e for e in ranking["ranking"]
                       if e["id"] == "run-latest-invalid")
        assert invalid["eligible"] is False
        assert invalid["rank"] is None
        assert invalid["reason"] == "metric_unknown"
        assert ranking["eligible_count"] == 100


class TestProductionConsumers:
    def test_goal_evaluate_exposes_ranking_without_changing_satisfaction(
            self, world):
        _add_goal(world["factory"],
                  criteria=[{"type": "manual", "note": "human sign-off"}])
        _add_run(world["factory"], "run-slow", human_interventions=4)
        _add_run(world["factory"], "run-fast", human_interventions=1)
        svc = _service(world)
        svc.set_utility_target("g-1", TARGET_MIN_INTERVENTIONS)

        evaluated = svc.evaluate("g-1")
        # The manual criterion is unsatified: utility is NOT completion.
        assert evaluated["status"] == "active"
        assert evaluated["progress"] == 0.0
        assert evaluated["satisfied"] == 0
        # But the deterministic comparison is available to the consumer.
        assert evaluated["utility"]["winner"] == "run-fast"
        assert evaluated["utility"]["ranking"][0]["utility"] == -1.0

    def test_goal_run_loop_and_router_consume_the_durable_ranking(self, world):
        _add_goal(world["factory"])
        _add_run(world["factory"], "run-slow", human_interventions=4)
        _add_run(world["factory"], "run-fast", human_interventions=1)
        svc = _service(world)
        svc.set_utility_target("g-1", TARGET_MIN_INTERVENTIONS)

        runs = _runs(world)
        created = runs.create_run("g-1")
        run = runs.get_run(created["id"])
        goal_state = runs._evaluate_goal(run)
        assert goal_state["utility"]["winner"] == "run-fast"

        context = runs._router_context(run, goal_state, None, None)
        prompt = GoalRunRouter(workspace_id="ws", tenant_id="t")._build_prompt(
            context)
        assert "UTILITY TARGET" in prompt
        assert "never a substitute for goal criteria" in prompt
        assert "run-fast" in prompt
        # The ranking is advisory; the fixed decision vocabulary is unchanged.
        assert "DECISION RULES" in prompt

    def test_ranking_survives_fresh_service_and_engine(self, world):
        _add_goal(world["factory"])
        _add_run(world["factory"], "run-slow", human_interventions=4)
        _add_run(world["factory"], "run-fast", human_interventions=1)
        _service(world).set_utility_target("g-1", TARGET_MIN_INTERVENTIONS)
        world["engine"].dispose()

        fresh_engine = create_engine(f"sqlite:///{world['path']}")
        fresh_factory = sessionmaker(bind=fresh_engine, expire_on_commit=False)
        fresh = GoalService(workspace_id="ws", tenant_id="t",
                            session_factory=fresh_factory)
        ranking = fresh.utility_ranking("g-1")
        assert ranking["target"] == TARGET_MIN_INTERVENTIONS
        assert ranking["winner"] == "run-fast"
        assert [e["id"] for e in ranking["ranking"]] == [
            "run-fast", "run-slow"]
        fresh_engine.dispose()

    def test_flag_off_preserves_the_pre_p5_loop(self, world, monkeypatch):
        _add_goal(world["factory"])
        _service(world).set_utility_target("g-1", TARGET_MIN_INTERVENTIONS)
        monkeypatch.setenv("ATOM_OBJECTIVE_LOOP_ENABLED", "false")
        assert objective_from_context({"goal_id": "g-1",
                                       "workspace_id": "ws"}) is None
        # The durable target remains readable; flag-off only removes the loop's
        # objective injection, exactly as before GOAL-02.
        assert _service(world).get_utility_target("g-1") == \
            TARGET_MIN_INTERVENTIONS


class TestGoalApiBoundary:
    def _client(self, api, user_id: str):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.goal_routes import router as goals_router
        from core.auth import get_current_user
        from core.database import get_db

        app = FastAPI()
        app.include_router(goals_router)
        user = type("U", (), {
            "id": user_id, "tenant_id": None, "status": "active",
            "workspace_id": "ws",
        })()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: api["session"]
        return TestClient(app)

    @pytest.fixture()
    def api(self, world):
        with world["factory"]() as db:
            db.add(User(id="lead", email="lead@example.com",
                        first_name="Lead", last_name="User",
                        role=UserRole.TEAM_LEAD.value, status="active",
                        is_active=True, workspace_id="ws"))
            db.add(User(id="member", email="member@example.com",
                        first_name="Member", last_name="User",
                        role=UserRole.MEMBER.value, status="active",
                        is_active=True, workspace_id="ws"))
            db.commit()
        _add_goal(world["factory"])
        _add_run(world["factory"], "run-slow", human_interventions=4)
        _add_run(world["factory"], "run-fast", human_interventions=1)
        session = world["factory"]()
        yield {"world": world, "session": session}
        session.close()

    def test_supervisor_sets_target_and_any_member_reads_ranking(self, api):
        lead = self._client(api, "lead")
        put = lead.put("/api/goals/g-1/utility",
                       json=TARGET_MIN_INTERVENTIONS)
        assert put.status_code == 200, put.text
        assert put.json()["utility_target"]["metric"] == "human_interventions"

        member = self._client(api, "member")
        read = member.get("/api/goals/g-1/utility")
        assert read.status_code == 200, read.text
        body = read.json()
        assert body["target"] == TARGET_MIN_INTERVENTIONS
        assert body["winner"] == "run-fast"

    def test_member_cannot_set_or_clear_the_target(self, api):
        member = self._client(api, "member")
        assert member.put("/api/goals/g-1/utility",
                          json=TARGET_MIN_INTERVENTIONS).status_code == 403
        assert member.delete("/api/goals/g-1/utility").status_code == 403

    def test_create_goal_with_target_is_supervisor_grade(self, api):
        member = self._client(api, "member")
        assert member.post("/api/goals", json={
            "title": "Member goal",
            "utility_target": TARGET_MIN_INTERVENTIONS,
        }).status_code == 403
        lead = self._client(api, "lead")
        created = lead.post("/api/goals", json={
            "title": "Lead goal",
            "utility_target": TARGET_MIN_INTERVENTIONS,
        })
        assert created.status_code == 200, created.text
        assert created.json()["goal"]["utility_target"] == \
            TARGET_MIN_INTERVENTIONS

    def test_api_rejects_malformed_target_and_reads_absent_target(self, api):
        lead = self._client(api, "lead")
        absent = lead.get("/api/goals/g-1/utility")
        assert absent.status_code == 200
        assert absent.json()["target"] is None
        bad = lead.put("/api/goals/g-1/utility", json={
            "metric": "caller_supplied_metric",
            "direction": "maximize",
            "source": "goal_run",
        })
        assert bad.status_code == 422, bad.text
        assert lead.get("/api/goals/g-1/utility").json()["target"] is None
