"""Shared postcondition families for local canvas and goal mutations."""
from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.models import Canvas, CanvasAudit, GoalObjective, GoalRun
from core.oracle import validate
from core.presentation_material import material_sha256, presentation_material
import core.oracle.postcondition_verifiers  # noqa: F401 - registers checks
from core.task_lifecycle import _approval_payload_hash


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _canvas(db, *, content=None):
    canvas = Canvas(
        id=f"canvas-{uuid.uuid4().hex[:8]}",
        tenant_id="tenant-1", workspace_id="default",
        created_by="user-1", name="Test canvas", canvas_type="document",
        content=content if content is not None else {"text": "initial"},
    )
    db.add(canvas)
    db.commit()
    return canvas


def _audit(db, canvas, *, action_type="update", details=None):
    row = CanvasAudit(
        id=str(uuid.uuid4()), canvas_id=canvas.id, tenant_id="tenant-1",
        action_type=action_type, canvas_type=canvas.canvas_type,
        details_json=details or {},
    )
    db.add(row)
    db.commit()
    return row


def test_canvas_present_family_verifies_exact_material_and_operation(db):
    canvas = _canvas(db)
    markdown_material = presentation_material(
        "canvas.present_markdown", {"content": "APPROVED total 350.00"})
    markdown = _audit(
        db, canvas, action_type="present",
        details={
            "component_type": "markdown", "title": "Quote",
            "material": markdown_material,
            "material_sha256": material_sha256(markdown_material),
            "operation_id": "op-markdown-1",
            "workspace_id": "default", "tenant_id": "tenant-1",
        })
    good = asyncio.run(validate("canvas.present_markdown", {
        "db": db, "canvas_id": canvas.id, "audit_id": markdown.id,
        "_oracle_expected_canvas_id": canvas.id,
        "_oracle_expected_operation_id": "op-markdown-1",
        "_oracle_expected_material_sha256": material_sha256(markdown_material),
        "_oracle_expected_workspace_id": "default",
        "_oracle_expected_tenant_id": "tenant-1",
    }))
    assert good is not None and good.verified is True, good

    wrong_material = presentation_material(
        "canvas.present_markdown", {"content": "WRONG total 999.00"})
    wrong_audit = _audit(
        db, canvas, action_type="present",
        details={
            "component_type": "markdown", "title": "Quote",
            "material": wrong_material,
            "material_sha256": material_sha256(wrong_material),
            "operation_id": "op-markdown-2",
            "workspace_id": "default", "tenant_id": "tenant-1",
        })
    wrong = asyncio.run(validate("canvas.present_markdown", {
        "db": db, "canvas_id": canvas.id, "audit_id": wrong_audit.id,
        "_oracle_expected_canvas_id": canvas.id,
        "_oracle_expected_operation_id": "op-markdown-2",
        "_oracle_expected_material_sha256": material_sha256(markdown_material),
        "_oracle_expected_workspace_id": "default",
        "_oracle_expected_tenant_id": "tenant-1",
    }))
    assert wrong is not None and wrong.verified is False

    chart_material = presentation_material(
        "canvas.present_chart",
        {"chart_type": "bar_chart",
         "data": [{"x": "A", "y": 350}, {"x": "B", "y": 10}]})
    chart = _audit(
        db, canvas, action_type="present",
        details={
            "component_type": "chart", "chart_type": "bar_chart",
            "data_points": 2, "title": "Totals",
            "material": chart_material,
            "material_sha256": material_sha256(chart_material),
            "operation_id": "op-chart-1",
            "workspace_id": "default", "tenant_id": "tenant-1",
        })
    chart_ok = asyncio.run(validate("canvas.present_chart", {
        "db": db, "canvas_id": canvas.id, "audit_id": chart.id,
        "_oracle_expected_canvas_id": canvas.id,
        "_oracle_expected_operation_id": "op-chart-1",
        "_oracle_expected_material_sha256": material_sha256(chart_material),
        "_oracle_expected_workspace_id": "default",
        "_oracle_expected_tenant_id": "tenant-1",
    }))
    assert chart_ok is not None and chart_ok.verified is True, chart_ok

    wrong_chart = presentation_material(
        "canvas.present_chart",
        {"chart_type": "bar_chart",
         "data": [{"x": "A", "y": 999}, {"x": "B", "y": 10}]})
    wrong_chart_audit = _audit(
        db, canvas, action_type="present",
        details={
            "component_type": "chart", "chart_type": "bar_chart",
            "data_points": 2, "title": "Totals",
            "material": wrong_chart,
            "material_sha256": material_sha256(wrong_chart),
            "operation_id": "op-chart-2",
            "workspace_id": "default", "tenant_id": "tenant-1",
        })
    chart_bad = asyncio.run(validate("canvas.present_chart", {
        "db": db, "canvas_id": canvas.id, "audit_id": wrong_chart_audit.id,
        "_oracle_expected_canvas_id": canvas.id,
        "_oracle_expected_operation_id": "op-chart-2",
        "_oracle_expected_material_sha256": material_sha256(chart_material),
        "_oracle_expected_workspace_id": "default",
        "_oracle_expected_tenant_id": "tenant-1",
    }))
    assert chart_bad is not None and chart_bad.verified is False


def test_canvas_update_family_verifies_content_and_mirror(db):
    content = {"text": "approved quote", "rows": [1, 2]}
    canvas = _canvas(db, content=content)
    audit = _audit(db, canvas, details={
        "content": content, "operation_id": "op-canvas-1",
        "review_status": "accepted",
    })
    digest = _approval_payload_hash(content)
    good = asyncio.run(validate("canvas.update", {
        "db": db, "canvas_id": canvas.id, "audit_id": audit.id,
        "write_outcome": "committed", "content": content,
        "_oracle_expected_canvas_id": canvas.id,
        "_oracle_expected_canvas_content_sha256": digest,
        "_oracle_expected_operation_id": "op-canvas-1",
    }))
    assert good is not None and good.verified is True, good

    wrong = asyncio.run(validate("canvas.update", {
        "db": db, "canvas_id": canvas.id, "audit_id": audit.id,
        "write_outcome": "committed", "content": {"text": "different"},
        "_oracle_expected_canvas_id": canvas.id,
    }))
    assert wrong is not None and wrong.verified is False

    unknown = asyncio.run(validate("canvas.update", {
        "db": db, "canvas_id": canvas.id, "audit_id": audit.id,
        "write_outcome": "unknown", "content": content,
        "_oracle_expected_canvas_id": canvas.id,
        "_oracle_expected_canvas_content_sha256": digest,
    }))
    assert unknown is not None and unknown.verified is False


def test_canvas_restore_family_verifies_original_target(db):
    original = {"text": "version one"}
    canvas = _canvas(db, content=original)
    target = _audit(db, canvas, details={"content": original})
    restored = _audit(db, canvas, details={
        "content": original,
        "restored_from": {"audit_id": target.id},
        "review_status": "accepted",
    })
    canvas.content = original
    db.commit()
    good = asyncio.run(validate("canvas.restore_version", {
        "db": db, "canvas_id": canvas.id, "audit_id": restored.id,
        "write_outcome": "committed",
        "_oracle_expected_canvas_id": canvas.id,
        "_oracle_expected_restore_audit_id": target.id,
    }))
    assert good is not None and good.verified is True, good

    missing = asyncio.run(validate("canvas.restore_version", {
        "db": db, "canvas_id": canvas.id, "audit_id": restored.id,
        "write_outcome": "committed",
        "_oracle_expected_canvas_id": canvas.id,
        "_oracle_expected_restore_audit_id": "not-the-target",
    }))
    assert missing is not None and missing.verified is False

    no_change = asyncio.run(validate("canvas.restore_version", {
        "db": db, "canvas_id": canvas.id, "no_change": True,
        "write_outcome": "not_attempted",
        "_oracle_expected_canvas_id": canvas.id,
        "_oracle_expected_restore_audit_id": target.id,
    }))
    assert no_change is not None and no_change.verified is True, no_change


def test_goal_create_and_evaluate_families(db):
    goal = GoalObjective(
        id=f"goal-{uuid.uuid4().hex[:8]}", tenant_id="tenant-1",
        workspace_id="default", title="Close the quarter",
        status="active", progress=0.0, criteria=[], key_results=[],
    )
    db.add(goal)
    db.commit()
    created = asyncio.run(validate("goals.create", {
        "db": db, "goal": {"id": goal.id},
        "_oracle_expected_goal_id": goal.id,
        "_oracle_expected_goal_title": "Close the quarter",
        "_oracle_expected_workspace_id": "default",
    }))
    assert created is not None and created.verified is True, created
    wrong = asyncio.run(validate("goals.create", {
        "db": db, "goal": {"id": goal.id},
        "_oracle_expected_goal_title": "Different",
    }))
    assert wrong is not None and wrong.verified is False

    goal.status = "achieved"
    goal.progress = 100.0
    db.commit()
    evaluated = asyncio.run(validate("goals.evaluate", {
        "db": db, "goal_id": goal.id, "status": "achieved",
        "progress": 100.0,
        "_oracle_expected_goal_id": goal.id,
    }))
    assert evaluated is not None and evaluated.verified is True, evaluated
    mismatch = asyncio.run(validate("goals.evaluate", {
        "db": db, "goal_id": goal.id, "status": "active",
        "progress": 10.0,
        "_oracle_expected_goal_id": goal.id,
    }))
    assert mismatch is not None and mismatch.verified is False


def test_goal_run_and_plan_families(db):
    goal = GoalObjective(
        id=f"goal-{uuid.uuid4().hex[:8]}", tenant_id="tenant-1",
        workspace_id="default", title="Run", status="active",
        progress=0.0, criteria=[], key_results=[],
    )
    db.add(goal)
    run = GoalRun(
        id=f"run-{uuid.uuid4().hex[:8]}", tenant_id="tenant-1",
        workspace_id="default", goal_id=goal.id, agent_id="agent-1",
        role="operations", status="active", supervision_mode="shadow",
    )
    db.add(run)
    db.commit()
    started = asyncio.run(validate("goal_runs.start", {
        "db": db, "id": run.id, "run": {"id": run.id},
        "_oracle_expected_goal_id": goal.id,
        "_oracle_expected_agent_id": "agent-1",
    }))
    assert started is not None and started.verified is True, started
    wrong_agent = asyncio.run(validate("goal_runs.start", {
        "db": db, "id": run.id,
        "_oracle_expected_goal_id": goal.id,
        "_oracle_expected_agent_id": "agent-2",
    }))
    assert wrong_agent is not None and wrong_agent.verified is False

    plan = {
        "method": "standard",
        "subtasks": [
            {"id": "clarify", "depends_on": []},
            {"id": "execute", "depends_on": ["clarify"]},
            {"id": "verify", "depends_on": ["execute"]},
        ],
        "execution_groups": [["clarify"], ["execute"], ["verify"]],
        "cycles": [],
    }
    produced = asyncio.run(validate("goals.decompose", {"plan": plan}))
    assert produced is not None and produced.verified is True, produced
    bad_plan = json.loads(json.dumps(plan))
    bad_plan["subtasks"][1]["depends_on"] = ["missing"]
    bad = asyncio.run(validate("goals.decompose", {"plan": bad_plan}))
    assert bad is not None and bad.verified is False


def test_tasks_create_family_accepts_nested_task_payload(db):
    from core.models_board import BoardTask

    board_id = str(uuid.uuid4())
    task = BoardTask(
        id=str(uuid.uuid4()), board_id=board_id, column_id=str(uuid.uuid4()),
        title="Approved task", status="backlog", priority="normal",
    )
    db.add(task)
    db.commit()
    good = asyncio.run(validate("tasks.create", {
        "db": db, "task": {"id": task.id},
        "_oracle_expected_task_title": "Approved task",
        "_oracle_expected_board_id": board_id,
    }))
    assert good is not None and good.verified is True, good
    wrong = asyncio.run(validate("tasks.create", {
        "db": db, "task": {"id": task.id},
        "_oracle_expected_task_title": "Different",
    }))
    assert wrong is not None and wrong.verified is False


def test_adapter_uses_shared_canvas_update_postcondition(db, monkeypatch):
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter

    content = {"text": "adapter-approved"}
    canvas = _canvas(db, content=content)
    audit = _audit(db, canvas, details={
        "content": content, "operation_id": "op-adapter-canvas",
        "review_status": "accepted",
    })
    action = action_registry.get_action("canvas.update")

    async def handler(args, context):
        return {
            "success": True, "write_outcome": "committed",
            "canvas_id": args["canvas_id"], "audit_id": audit.id,
            "operation_id": args.get("operation_id"),
            "canvas_type": "document",
        }

    monkeypatch.setattr(action, "handler", handler)
    result = asyncio.run(_action_registry_adapter(
        {"action": "canvas.update", "arguments": {
            "canvas_id": canvas.id, "content": content,
            "operation_id": "op-adapter-canvas",
        }},
        {"workspace_id": "default", "employee_id": "user-1",
         "tenant_id": "tenant-1", "run_id": "r1",
         "assignment_id": "a1", "db": db},
    ))
    assert result["status"] == "applied", result
    assert result["oracle_verified"] is True


def test_adapter_downgrades_wrong_local_canvas_content(db, monkeypatch):
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter

    content = {"text": "authorized"}
    different = {"text": "handler-wrote-something-else"}
    canvas = _canvas(db, content=content)
    audit = _audit(db, canvas, details={
        "content": different, "operation_id": "op-wrong-canvas",
        "review_status": "accepted",
    })
    action = action_registry.get_action("canvas.update")

    async def handler(args, context):
        return {
            "success": True, "write_outcome": "committed",
            "canvas_id": args["canvas_id"], "audit_id": audit.id,
            "operation_id": args.get("operation_id"),
            "canvas_type": "document",
        }

    monkeypatch.setattr(action, "handler", handler)
    result = asyncio.run(_action_registry_adapter(
        {"action": "canvas.update", "arguments": {
            "canvas_id": canvas.id, "content": content,
            "operation_id": "op-wrong-canvas",
        }},
        {"workspace_id": "default", "employee_id": "user-1",
         "tenant_id": "tenant-1", "run_id": "r1",
         "assignment_id": "a1", "db": db},
    ))
    assert result["status"] == "uncertain", result
    assert result["oracle_verified"] is False


def test_adapter_uses_shared_goal_and_task_postconditions(db, monkeypatch):
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter
    from core.models_board import BoardTask

    goal = GoalObjective(
        id=f"goal-{uuid.uuid4().hex[:8]}", tenant_id="tenant-1",
        workspace_id="default", title="Adapter goal", status="active",
        progress=0.0, criteria=[], key_results=[],
    )
    board_id = str(uuid.uuid4())
    task = BoardTask(
        id=str(uuid.uuid4()), board_id=board_id,
        column_id=str(uuid.uuid4()), title="Adapter task",
        status="backlog", priority="normal",
    )
    db.add_all([goal, task])
    db.commit()

    goal_action = action_registry.get_action("goals.create")

    async def goal_handler(args, context):
        return {"success": True, "goal": {"id": goal.id}}

    monkeypatch.setattr(goal_action, "handler", goal_handler)
    goal_result = asyncio.run(_action_registry_adapter(
        {"action": "goals.create", "arguments": {
            "title": "Adapter goal", "criteria": []}},
        {"workspace_id": "default", "employee_id": "user-1",
         "tenant_id": "tenant-1", "run_id": "r1",
         "assignment_id": "a1", "db": db},
    ))
    assert goal_result["status"] == "applied", goal_result
    assert goal_result["oracle_verified"] is True

    task_action = action_registry.get_action("tasks.create")

    async def task_handler(args, context):
        return {"success": True, "task": {"id": task.id}}

    monkeypatch.setattr(task_action, "handler", task_handler)
    task_result = asyncio.run(_action_registry_adapter(
        {"action": "tasks.create", "arguments": {
            "title": "Adapter task", "board_id": board_id}},
        {"workspace_id": "default", "employee_id": "user-1",
         "tenant_id": "tenant-1", "run_id": "r1",
         "assignment_id": "a1", "db": db},
    ))
    assert task_result["status"] == "applied", task_result
    assert task_result["oracle_verified"] is True


def _presentation_audit(db, canvas, action_name, args, *, operation_id,
                        workspace_id="default", tenant_id="tenant-1"):
    material = presentation_material(action_name, args)
    return _audit(
        db, canvas, action_type="present",
        details={
            "component_type": (
                "markdown" if action_name.endswith("markdown") else "chart"),
            "title": args.get("title") or "Quote",
            "material": material,
            "material_sha256": material_sha256(material),
            "operation_id": operation_id,
            "workspace_id": workspace_id,
            "tenant_id": tenant_id,
        })


def test_adapter_presentation_positive_binds_exact_audit(db, monkeypatch):
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter

    name = "canvas.present_markdown"
    canvas = _canvas(db)
    args = {"canvas_id": canvas.id, "content": "APPROVED total 350.00",
            "title": "Quote", "operation_id": "op-present-1"}
    audit = _presentation_audit(db, canvas, name, args,
                                operation_id="op-present-1")
    action = action_registry.get_action(name)

    async def handler(arguments, context):
        return {"success": True, "status": "applied",
                "action_result": "applied", "canvas_id": canvas.id,
                "remote_id": canvas.id, "audit_id": audit.id}

    monkeypatch.setattr(action, "handler", handler)
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": args},
        {"workspace_id": "default", "employee_id": "user-1",
         "tenant_id": "tenant-1", "run_id": "r1",
         "assignment_id": "a1", "db": db},
    ))
    assert result["status"] == "applied", result
    assert result["oracle_verified"] is True


def test_adapter_presentation_handler_mutation_is_refuted(db, monkeypatch):
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter

    name = "canvas.present_markdown"
    canvas = _canvas(db)
    approved = {"canvas_id": canvas.id, "content": "APPROVED total 350.00",
                "title": "Quote", "operation_id": "op-present-2"}
    wrong = {**approved, "content": "WRONG total 999.00"}
    wrong_audit = _presentation_audit(
        db, canvas, name, wrong, operation_id="op-present-2")
    action = action_registry.get_action(name)
    calls = {"count": 0}

    async def handler(arguments, context):
        calls["count"] += 1
        arguments["content"] = "WRONG total 999.00"
        return {"success": True, "status": "applied",
                "action_result": "applied", "canvas_id": canvas.id,
                "remote_id": canvas.id, "audit_id": wrong_audit.id}

    monkeypatch.setattr(action, "handler", handler)
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": approved},
        {"workspace_id": "default", "employee_id": "user-1",
         "tenant_id": "tenant-1", "run_id": "r1",
         "assignment_id": "a1", "db": db},
    ))
    assert result["status"] == "uncertain", result
    assert calls["count"] == 1


def test_adapter_old_audit_cannot_certify_new_operation(db, monkeypatch):
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter

    name = "canvas.present_markdown"
    canvas = _canvas(db)
    args = {"canvas_id": canvas.id, "content": "New presentation",
            "title": "Quote", "operation_id": "op-new"}
    old_audit = _presentation_audit(
        db, canvas, name, args, operation_id="op-old")
    action = action_registry.get_action(name)

    async def handler(arguments, context):
        return {"success": True, "status": "applied",
                "action_result": "applied", "canvas_id": canvas.id,
                "remote_id": canvas.id, "audit_id": old_audit.id}

    monkeypatch.setattr(action, "handler", handler)
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": args},
        {"workspace_id": "default", "employee_id": "user-1",
         "tenant_id": "tenant-1", "run_id": "r1",
         "assignment_id": "a1", "db": db},
    ))
    assert result["status"] == "uncertain", result


def test_adapter_missing_presentation_material_refuses_before_dispatch(
        db, monkeypatch):
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter

    name = "canvas.present_markdown"
    canvas = _canvas(db)
    action = action_registry.get_action(name)
    calls = {"count": 0}

    async def handler(arguments, context):  # pragma: no cover - must not run
        calls["count"] += 1
        return {"success": True}

    monkeypatch.setattr(action, "handler", handler)
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": {"canvas_id": canvas.id}},
        {"workspace_id": "default", "employee_id": "user-1",
         "tenant_id": "tenant-1", "run_id": "r1",
         "assignment_id": "a1", "db": db},
    ))
    assert result["status"] == "failed", result
    assert result["error_class"] == "presentation_binding_unavailable"
    assert calls["count"] == 0
