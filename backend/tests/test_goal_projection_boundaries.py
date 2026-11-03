"""Projection ownership and explicit native-dispatch boundaries.

A task-lifecycle projection is readable assignment state, never native goal
work. These controls exercise actual consumption: the service/executor return
a durable refusal, create no canvas and advance no counter.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.assignment_executor import AssignmentExecutor, default_adapter_registry
from core.assignment_plan import new_assignment, new_step
from core.goals.goal_plan_validation import (
    normalize_step_kind,
    validate_assignment_projection,
)
from core.goals.goal_run_executors import GoalRunExecutors
from core.goals.goal_run_ownership import is_assignment_owned
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.models import (
    Canvas,
    GoalObjective,
    GoalRun,
    TaskOperationRecord,
)
from core.task_lifecycle import TaskLifecycle


def _factory(tmp_path, name="projection.db"):
    engine = create_engine(
        f"sqlite:///{tmp_path / name}", connect_args={"timeout": 30})
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  Canvas.__table__, TaskOperationRecord.__table__):
        table.create(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _add_goal(factory, goal_id="goal-family"):
    with factory() as session:
        session.add(GoalObjective(
            id=goal_id, workspace_id="ws-a", tenant_id="t-a",
            title="Prepare a quote", status="active",
            criteria=[], key_results=[]))
        session.commit()


def _service(tmp_path, name="projection.db"):
    engine, factory = _factory(tmp_path, name)
    _add_goal(factory)
    return engine, factory, GoalRunService(
        workspace_id="ws-a", tenant_id="t-a", session_factory=factory)


def _run_record(factory, run_id):
    with factory() as session:
        return session.query(GoalRun).filter(GoalRun.id == run_id).one()


def _canvas_count(factory, run_id):
    with factory() as session:
        return session.query(Canvas).filter(
            Canvas.goal_run_id == run_id).count()


def _assignment_executor(tmp_path, name="assignment-projection.db"):
    engine, factory = _factory(tmp_path, name)
    runs = GoalRunService(
        workspace_id="ws-a", tenant_id="t-a", session_factory=factory)
    goals = GoalService(
        workspace_id="ws-a", tenant_id="t-a", session_factory=factory)
    lifecycle = TaskLifecycle(runs, goals)
    return engine, factory, runs, AssignmentExecutor(
        lifecycle, adapters=default_adapter_registry.clone())


def test_forged_task_lifecycle_marker_cannot_execute_projection(tmp_path):
    engine, factory, svc = _service(tmp_path)
    run_id = svc.create_run(
        "goal-family", role="sales",
        plan=[{"id": "projected-read", "kind": "operation",
               "title": "Assignment operation"}],
        parameters={"task_lifecycle": {}})["id"]
    svc.transition(run_id, "active")
    assert is_assignment_owned(svc.get_run(run_id)) is False
    cursor_before = svc.get_run(run_id)["cursor"]

    result = asyncio.run(svc.execute_decision(
        run_id, {"decision": "ADVANCE", "human_approved": True,
                 "rationale": "native advance"}))

    assert result["advanced"] is False
    assert result["result"]["not_executed"] is True
    assert _canvas_count(factory, run_id) == 0
    current = svc.get_run(run_id)
    assert current["steps_executed"] == 0
    assert current["cursor"] == cursor_before
    engine.dispose()


def test_forged_marker_cannot_write_operation_projection(tmp_path):
    engine, factory, svc = _service(tmp_path)
    run_id = svc.create_run(
        "goal-family", role="sales", parameters={"task_lifecycle": {}})["id"]
    svc.transition(run_id, "active")

    with pytest.raises(ValueError, match="trusted assignment ownership"):
        svc.set_plan(run_id, [{
            "id": "projected-read", "kind": "operation",
            "title": "Assignment operation"}])

    assert _run_record(factory, run_id).plan == []
    engine.dispose()


def test_unknown_kind_creates_no_canvas_or_counter(tmp_path):
    engine, factory, svc = _service(tmp_path)
    run_id = svc.create_run("goal-family", role="sales", plan=[])["id"]
    svc.transition(run_id, "active")
    with factory() as session:
        row = session.query(GoalRun).filter(GoalRun.id == run_id).one()
        row.plan = [{"id": "mystery", "kind": "mystery", "title": "Unknown"}]
        row.cursor = "mystery"
        row.material_revision = (row.material_revision or 0) + 1
        session.commit()

    result = asyncio.run(svc.execute_decision(
        run_id, {"decision": "ADVANCE", "human_approved": True,
                 "rationale": "unknown kind"}))

    assert result["advanced"] is False
    assert result["result"]["not_executed"] is True
    assert _canvas_count(factory, run_id) == 0
    assert svc.get_run(run_id)["steps_executed"] == 0
    engine.dispose()


def test_legacy_and_normalized_canvas_kinds_dispatch(tmp_path):
    engine, factory, svc = _service(tmp_path)
    run_id = svc.create_run("goal-family", role="sales", plan=[])["id"]
    svc.transition(run_id, "active")
    executors = GoalRunExecutors(svc)
    seen = []

    async def canvas(run, decision, step, revise=False):
        seen.append((step.get("id"), normalize_step_kind(step)))
        return {"canvas_id": "controlled"}

    executors._canvas_work = canvas
    for step in ({"id": "legacy", "title": "Legacy"},
                 {"id": "spaced", "kind": "  Canvas_Work  ",
                  "title": "Spaced"}):
        result = asyncio.run(executors._run_current_step(
            {"id": run_id, "plan": [step], "cursor": step["id"]},
            {"decision": "ADVANCE"}, revise=False))
        assert result["canvas_id"] == "controlled"
    assert [item[1] for item in seen] == ["canvas_work", "canvas_work"]
    engine.dispose()


def test_genuine_assignment_projection_is_readable_and_native_refused(
        tmp_path):
    engine, factory, svc, executor = _assignment_executor(tmp_path)
    step = new_step(
        step_id="read-1", title="Read the approved source",
        operation_type="retrieve", adapter="test")
    assignment = new_assignment(
        objective="Read the approved source",
        employee_id="user-1", workspace_id="ws-a", tenant_id="t-a",
        steps=[step])
    record = executor.create_assignment(
        f"conv-{uuid.uuid4().hex[:8]}", "Read the approved source",
        assignment=assignment)
    run_id = record["run_id"]

    run = svc.get_run(run_id)
    assert is_assignment_owned(run) is True
    assert [item["kind"] for item in run["plan"]] == ["operation"]
    assert run["plan"][0]["id"] == "read-1"
    task = executor.lifecycle.get_task(run_id)
    assert task["assignment"]["assignment_id"] == (
        assignment["assignment_id"])

    class BombRouter:
        async def decide(self, _context):
            raise AssertionError("native router must not run")

    advanced = asyncio.run(svc.advance(run_id, router=BombRouter()))
    assert advanced["advanced"] is False
    assert advanced["assignment_continuation_required"] is True

    result = asyncio.run(svc.execute_decision(
        run_id, {"decision": "ADVANCE", "human_approved": True,
                 "rationale": "native advance"}))
    assert result["advanced"] is False
    assert result["assignment_continuation_required"] is True
    assert _canvas_count(factory, run_id) == 0
    assert svc.get_run(run_id)["steps_executed"] == 0

    resumed = asyncio.run(svc.resume(
        run_id, approved=True, reviewer="lead-a"))
    assert resumed["resumed"] is False
    assert resumed["assignment_continuation_required"] is True

    # A fresh service/session sees the same ownership and read model.
    restarted = GoalRunService(
        workspace_id="ws-a", tenant_id="t-a", session_factory=factory)
    restarted_run = restarted.get_run(run_id)
    assert is_assignment_owned(restarted_run) is True
    assert restarted_run["plan"][0]["id"] == "read-1"
    engine.dispose()


def test_assignment_parameter_write_bumps_material_revision(tmp_path):
    engine, factory, svc, executor = _assignment_executor(
        tmp_path, "assignment-material.db")
    step = new_step(
        step_id="read-1", title="Read the approved source",
        operation_type="retrieve", adapter="test")
    assignment = new_assignment(
        objective="Read the approved source",
        employee_id="user-1", workspace_id="ws-a", tenant_id="t-a",
        steps=[step])
    record = executor.create_assignment(
        f"conv-{uuid.uuid4().hex[:8]}", "Read the approved source",
        assignment=assignment)
    run_id = record["run_id"]
    before = svc.get_run(run_id)["material_revision"]
    assignment["plan_revision"] = 2
    executor.lifecycle.put_assignment(
        run_id, assignment, rationale="material change")
    assert svc.get_run(run_id)["material_revision"] > before
    engine.dispose()


def test_projection_validator_rejects_executable_or_malformed_entries():
    assert validate_assignment_projection([{
        "id": "read-1", "kind": "canvas_work", "title": "Not a projection",
    }])
    assert validate_assignment_projection([
        {"id": "read-1", "kind": "operation", "title": "One"},
        {"id": "read-1", "kind": "operation", "title": "Duplicate"},
    ])
    assert validate_assignment_projection([{
        "id": "read-1", "kind": "operation", "title": "One",
        "depends_on": ["read-1"]}])
    assert validate_assignment_projection([{
        "id": "read-1", "kind": "operation", "title": "One",
        "depends_on": ["later"]},
        {"id": "later", "kind": "operation", "title": "Later"}]) == []
    assert validate_assignment_projection([{
        "id": "read-1", "kind": "operation", "title": "One",
        "operation_type": "retrieve"}]) == []
