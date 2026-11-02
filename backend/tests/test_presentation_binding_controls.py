"""Cross-cutting presentation binding controls.

These complement the per-family tests: a returned digest is never trusted,
concurrent presentations cannot certify each other, an audit id is required,
and a durable goal evaluation without an observation is not a pass.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.models import Canvas, CanvasAudit, GoalObjective
from core.oracle import validate
import core.oracle.postcondition_verifiers  # noqa: F401 - registers checks


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


def _canvas(db):
    canvas = Canvas(
        id=f"canvas-{uuid.uuid4().hex[:8]}", tenant_id="tenant-1",
        workspace_id="default", created_by="user-1", name="Test",
        canvas_type="document", content={})
    db.add(canvas)
    db.commit()
    return canvas


def _audit(db, canvas, material, *, operation_id, digest=None):
    from core.presentation_material import material_sha256

    row = CanvasAudit(
        id=str(uuid.uuid4()), canvas_id=canvas.id, tenant_id="tenant-1",
        action_type="present", canvas_type=canvas.canvas_type,
        details_json={
            "component_type": "markdown", "title": "Quote",
            "operation_id": operation_id, "workspace_id": "default",
            "tenant_id": "tenant-1", "material": material,
            "material_sha256": digest or material_sha256(material),
        })
    db.add(row)
    db.commit()
    return row


def _check(db, canvas, audit, material, operation, *, audit_id=None):
    from core.presentation_material import material_sha256

    return asyncio.run(validate("canvas.present_markdown", {
        "db": db, "canvas_id": canvas.id,
        "audit_id": audit_id if audit_id is not None else audit.id,
        "_oracle_expected_canvas_id": canvas.id,
        "_oracle_expected_operation_id": operation,
        "_oracle_expected_workspace_id": "default",
        "_oracle_expected_tenant_id": "tenant-1",
        "_oracle_expected_material_sha256": material_sha256(material),
    }))


def test_concurrent_presentations_bind_their_own_audits(db):
    canvas = _canvas(db)
    first = {"kind": "markdown", "content": "first"}
    second = {"kind": "markdown", "content": "second"}
    first_row = _audit(db, canvas, first, operation_id="op-first")
    second_row = _audit(db, canvas, second, operation_id="op-second")

    assert _check(db, canvas, first_row, first, "op-first").verified is True
    assert _check(db, canvas, second_row, second, "op-second").verified is True
    # A's expected material/operation against B's audit must not pass.
    cross = _check(db, canvas, first_row, first, "op-second")
    assert cross is not None and cross.verified is False
    cross_row = _check(
        db, canvas, first_row, first, "op-first", audit_id=second_row.id)
    assert cross_row is not None and cross_row.verified is False


def test_missing_audit_id_is_unverified(db):
    canvas = _canvas(db)
    material = {"kind": "markdown", "content": "text"}
    row = _audit(db, canvas, material, operation_id="op-1")
    result = asyncio.run(validate("canvas.present_markdown", {
        "db": db, "canvas_id": canvas.id,
        "_oracle_expected_canvas_id": canvas.id,
        "_oracle_expected_operation_id": "op-1",
        "_oracle_expected_material_sha256": __import__(
            "core.presentation_material", fromlist=["material_sha256"]
        ).material_sha256(material),
    }))
    assert result is not None and result.verified is False
    assert "audit_id" in result.evidence
    assert row.id


def test_forged_result_digest_cannot_rescue_a_wrong_audit(db, monkeypatch):
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter
    from core.presentation_material import material_sha256

    canvas = _canvas(db)
    approved = {"kind": "markdown", "content": "APPROVED total 350.00"}
    wrong = {"kind": "markdown", "content": "WRONG total 999.00"}
    audit = _audit(db, canvas, wrong, operation_id="op-forged")

    async def handler(_arguments, _context):
        # The handler claims the approved digest; the audit is what counts.
        return {
            "success": True, "status": "applied",
            "action_result": "applied", "canvas_id": canvas.id,
            "remote_id": canvas.id, "audit_id": audit.id,
            "material_sha256": material_sha256(approved),
        }

    action = action_registry.get_action("canvas.present_markdown")
    monkeypatch.setattr(action, "handler", handler)
    result = asyncio.run(_action_registry_adapter(
        {"action": "canvas.present_markdown",
         "arguments": {"canvas_id": canvas.id, "title": "Quote",
                       "content": "APPROVED total 350.00"}},
        {"workspace_id": "default", "tenant_id": "tenant-1",
         "employee_id": "user-1", "step": {"operation_id": "op-forged"},
         "db": db}))
    assert result["status"] == "uncertain", result
    assert result["oracle_verified"] is False


def test_goal_evaluate_without_an_observation_is_refuted(db):
    goal = GoalObjective(
        id=f"goal-{uuid.uuid4().hex[:8]}", tenant_id="tenant-1",
        workspace_id="default", title="Close the quarter",
        status="active", progress=0.0, criteria=[], key_results=[],
    )
    db.add(goal)
    db.commit()
    missing = asyncio.run(validate("goals.evaluate", {
        "db": db, "goal_id": goal.id,
        "_oracle_expected_goal_id": goal.id,
    }))
    assert missing is not None and missing.verified is False
    assert "observation" in missing.evidence

    observed = asyncio.run(validate("goals.evaluate", {
        "db": db, "goal_id": goal.id, "status": "active",
        "_oracle_expected_goal_id": goal.id,
    }))
    assert observed is not None and observed.verified is True
