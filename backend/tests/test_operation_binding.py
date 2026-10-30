"""Operation binding and registry-dispatch controls (Patch 1/2).

Scratch sqlite only. No provider calls.
"""
from __future__ import annotations

import asyncio
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.models import GoalObjective, GoalRun, TaskOperationRecord
from core.task_lifecycle import (
    OPERATION_BINDING_VERSION,
    TaskLifecycle,
    TaskLifecycleError,
    operation_binding_sha256,
)


def _lifecycle(tmp_path, workspace="ws_bind", tenant="tenant_bind"):
    engine = create_engine(f"sqlite:///{tmp_path}/bind-{workspace}.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  TaskOperationRecord.__table__):
        table.create(engine, checkfirst=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    runs = GoalRunService(
        workspace_id=workspace, tenant_id=tenant, session_factory=factory)
    goals = GoalService(
        workspace_id=workspace, tenant_id=tenant, session_factory=factory)
    return TaskLifecycle(runs, goals), factory


def _task(lifecycle):
    return lifecycle.create_task("conv-bind", "prepare an outbound effect")


def _binding(**overrides):
    payload = {
        "action_name": "email.send",
        "workspace_id": "ws_bind",
        "account_id": "sender@example.invalid",
        "task_revision": 1,
        "arguments": {
            "to": ["a@example.invalid"],
            "subject": "Subject",
            "body": "Body",
        },
        "artifact_refs": [{
            "artifact_id": "draft-1", "revision": "rev-1",
            "sha256": "abc123",
        }],
        "authorization_ref": "approval-1",
        "prerequisite_operation_ids": ["op-1"],
        "prerequisite_evidence_revisions": ["source-v1"],
    }
    payload.update(overrides)
    return payload


def test_same_key_same_binding_replays(tmp_path):
    lifecycle, _ = _lifecycle(tmp_path)
    created = _task(lifecycle)
    first = lifecycle.create_operation(
        created["run_id"], op_type="outbound",
        requested_change="send the prepared reply",
        idempotency_key="key-1", binding=_binding())
    second = lifecycle.create_operation(
        created["run_id"], op_type="outbound",
        requested_change="send the prepared reply",
        idempotency_key="key-1", binding=_binding())
    assert first["operation_id"] == second["operation_id"]
    assert first["binding_sha256"] == second["binding_sha256"]
    assert len(lifecycle.get_task(created["run_id"])["operations"]) == 1


def test_same_key_changed_recipient_conflicts(tmp_path):
    lifecycle, _ = _lifecycle(tmp_path)
    created = _task(lifecycle)
    lifecycle.create_operation(
        created["run_id"], op_type="outbound",
        requested_change="send the prepared reply",
        idempotency_key="key-1", binding=_binding())
    with pytest.raises(TaskLifecycleError):
        lifecycle.create_operation(
            created["run_id"], op_type="outbound",
            requested_change="send the prepared reply",
            idempotency_key="key-1",
            binding=_binding(arguments={
                "to": ["attacker@example.invalid"],
                "subject": "Subject",
                "body": "Body",
            }))


def test_same_key_changed_attachment_revision_conflicts(tmp_path):
    lifecycle, _ = _lifecycle(tmp_path)
    created = _task(lifecycle)
    lifecycle.create_operation(
        created["run_id"], op_type="outbound",
        requested_change="send the prepared reply",
        idempotency_key="key-1", binding=_binding())
    with pytest.raises(TaskLifecycleError):
        lifecycle.create_operation(
            created["run_id"], op_type="outbound",
            requested_change="send the prepared reply",
            idempotency_key="key-1",
            binding=_binding(artifact_refs=[{
                "artifact_id": "draft-1", "revision": "rev-2",
                "sha256": "different",
            }]))


def test_different_workspace_does_not_share_reservation(tmp_path):
    first, _ = _lifecycle(tmp_path, workspace="ws_a")
    second, _ = _lifecycle(tmp_path, workspace="ws_b")
    run_a = first.create_task("conv-a", "effect a")["run_id"]
    run_b = second.create_task("conv-b", "effect b")["run_id"]
    op_a = first.create_operation(
        run_a, op_type="outbound", requested_change="send",
        idempotency_key="shared-key",
        binding=_binding(workspace_id="ws_a"))
    op_b = second.create_operation(
        run_b, op_type="outbound", requested_change="send",
        idempotency_key="shared-key",
        binding=_binding(workspace_id="ws_b"))
    assert op_a["operation_id"] != op_b["operation_id"]


def test_binding_survives_new_session(tmp_path):
    lifecycle, factory = _lifecycle(tmp_path)
    created = _task(lifecycle)
    operation = lifecycle.create_operation(
        created["run_id"], op_type="outbound",
        requested_change="send", idempotency_key="key-1",
        binding=_binding())
    restarted, _ = _lifecycle(tmp_path)
    stored = restarted.get_task(created["run_id"])["operations"][0]
    assert stored["operation_binding"]["binding_version"] == (
        OPERATION_BINDING_VERSION)
    assert stored["binding_sha256"] == operation["binding_sha256"] == (
        operation_binding_sha256(stored["operation_binding"]))


def test_oversized_arguments_rejected_without_truncation(tmp_path):
    lifecycle, _ = _lifecycle(tmp_path)
    created = _task(lifecycle)
    with pytest.raises(TaskLifecycleError):
        lifecycle.create_operation(
            created["run_id"], op_type="outbound",
            requested_change="send", idempotency_key="key-1",
            binding=_binding(arguments={"body": "x" * 9000}))


def test_binding_requires_action_and_workspace(tmp_path):
    lifecycle, _ = _lifecycle(tmp_path)
    created = _task(lifecycle)
    with pytest.raises(TaskLifecycleError):
        lifecycle.create_operation(
            created["run_id"], op_type="outbound",
            requested_change="send", idempotency_key="key-1",
            binding=_binding(action_name=""))
    with pytest.raises(TaskLifecycleError):
        lifecycle.create_operation(
            created["run_id"], op_type="outbound",
            requested_change="send", idempotency_key="key-2",
            binding=_binding(workspace_id=""))


def test_registry_dispatch_is_the_execution_boundary(tmp_path, monkeypatch):
    from core.action_registry import action_registry
    from core.assignment_executor import AssignmentExecutor
    from core.assignment_plan import new_assignment, new_step, new_teaching_snapshot

    received = {}

    async def handler(arguments, context):
        received.update(arguments)
        received["workspace_id"] = context.get("workspace_id")
        return {"ok": True}

    action_registry.register(
        "test.bound.action", handler,
        parameters_schema={"type": "object", "properties": {}, "required": []},
        effects=[{"effect": "read"}])
    lifecycle, factory = _lifecycle(tmp_path)
    executor = AssignmentExecutor(lifecycle)
    plan = new_assignment(
        objective="Run a registered action",
        workspace_id="ws_bind",
        tenant_id="tenant_bind",
        employee_id="user-bind",
        teaching_snapshot=new_teaching_snapshot(revision="t1"),
        steps=[new_step(
            step_id="act", title="Run the registered action",
            operation_type="calculate", adapter="action.registry",
            inputs={"action": "test.bound.action",
                    "arguments": {"value": 7}},
            effect="read_only")],
    )
    record = executor.create_assignment("conv-reg" , "Run a registered action",
                                        assignment=plan)
    result = asyncio.run(executor.execute(record["run_id"]))
    assert result["assignment"]["status"] == "completed", result
    assert received == {"value": 7, "workspace_id": "ws_bind"}
    stored = lifecycle.get_task(record["run_id"])["operations"][0]
    assert stored["operation_binding"]["action_name"] == "action.registry"
    assert stored["operation_binding"]["arguments"]["action"] == (
        "test.bound.action")
