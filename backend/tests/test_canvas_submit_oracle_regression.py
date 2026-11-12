"""Focused regression coverage for the registered ``canvas.submit`` oracle.

These controls exercise the shared pieces production already uses:

* the real mounted ``POST /api/canvas/submit`` route;
* the real canvas writer/service and a file-backed scratch SQLite database;
* the registered ``canvas.submit`` postcondition verifier, called directly to
  prove it re-derives success from durable evidence rather than the caller's
  self-report.

The positive case is a genuinely committed form submission. The negative cases
are plausible success claims with no matching audit row, and with a durable row
that belongs to a different operation, so the oracle cannot certify a lie.
"""
from __future__ import annotations

import asyncio

import pytest

from core.models import Canvas, CanvasAudit
from core.oracle import get_postcondition, validate
from tests.test_canvas_lifecycle_verified import (  # noqa: F401
    app_client,
    probe,
    _canvas,
    _user,
)


def _seed_submit_form(app_client):
    with app_client.Session() as db:
        actor = _user(
            db,
            user_id="submit-actor",
            tenant_id="submit-tenant",
            workspace_id="submit-workspace",
        )
        canvas = _canvas(
            db,
            canvas_id="submit-canvas",
            owner_id=actor.id,
            tenant_id=actor.tenant_id,
            workspace_id=actor.workspace_id,
            canvas_type="form",
            content={"schema": {"fields": [{"name": "quantity"}]}},
        )
    app_client.users["current"] = actor
    return actor, canvas


def _frozen_submit_context(
    *,
    canvas_id: str,
    audit_id: str,
    operation_id: str,
    material_sha256: str,
    actor_id: str = "submit-actor",
    actor_tenant_id: str = "submit-tenant",
    actor_workspace_id: str = "submit-workspace",
    canvas_tenant_id: str = "submit-tenant",
    canvas_workspace_id: str = "submit-workspace",
    agent_id: str = "",
    agent_execution_id: str = "",
):
    """Exactly the request-bound context the production service freezes."""
    return {
        "canvas_id": canvas_id,
        "audit_id": audit_id,
        "write_outcome": "committed",
        "_oracle_action": "canvas.submit",
        "_oracle_expected_canvas_id": canvas_id,
        "_oracle_expected_operation_id": operation_id,
        "_oracle_expected_material_sha256": material_sha256,
        "_oracle_expected_actor_id": actor_id,
        "_oracle_expected_actor_tenant_id": actor_tenant_id,
        "_oracle_expected_actor_workspace_id": actor_workspace_id,
        "_oracle_expected_canvas_tenant_id": canvas_tenant_id,
        "_oracle_expected_canvas_workspace_id": canvas_workspace_id,
        "_oracle_expected_agent_id": agent_id,
        "_oracle_expected_agent_execution_id": agent_execution_id,
    }


def test_registered_canvas_submit_oracle_verifies_real_committed_form(app_client):
    actor, canvas = _seed_submit_form(app_client)
    payload = {
        "canvas_id": canvas.id,
        "form_data": {"quantity": 0, "approved": False, "note": ""},
        "operation_id": "oracle-canonical-operation",
    }

    response = app_client.client.post("/api/canvas/submit", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verification"]["status"] == "verified", body
    assert body["operation_id"] == payload["operation_id"]
    assert body["material_sha256"]

    # Prove the durable evidence exists independently of the route response.
    with app_client.Session() as db:
        audit = db.get(CanvasAudit, body["audit_id"])
        assert audit is not None
        assert audit.canvas_id == canvas.id
        assert audit.action_type == "submit"
        assert audit.user_id == actor.id
        details = audit.details_json
        assert details["operation_id"] == payload["operation_id"]
        assert details["form_data"] == payload["form_data"]
        assert details["material_sha256"] == body["material_sha256"]

    # The verifier must be registered, and a direct call (no request session)
    # must certify only the exact durable receipt.
    assert get_postcondition("canvas.submit") is not None
    result = asyncio.run(validate(
        "canvas.submit",
        _frozen_submit_context(
            canvas_id=canvas.id,
            audit_id=body["audit_id"],
            operation_id=body["operation_id"],
            material_sha256=body["material_sha256"],
        ),
    ))
    assert result is not None and result.verified is True, result
    assert body["audit_id"][:12] in result.evidence
    assert body["material_sha256"][:12] in result.evidence

    with app_client.Session() as db:
        assert db.query(CanvasAudit).filter_by(
            canvas_id=canvas.id, action_type="submit").count() == 1


def test_canvas_submit_oracle_refutes_plausible_self_report_without_audit(app_client):
    """A fabricated success claim must not create or imply a durable event."""
    from tools.canvas_crud_tool import (
        deterministic_submit_audit_id,
        submit_material_digest,
    )

    actor, canvas = _seed_submit_form(app_client)
    operation_id = "self-reported-only-operation"
    form_data = {"quantity": 0, "approved": True}
    fabricated_audit_id = deterministic_submit_audit_id(
        actor.id, canvas.id, operation_id)
    # A self-consistent self-report: its digest really is the canonical digest
    # of the claimed material, but no writer has ever appended that ledger row.
    claimed_digest = submit_material_digest(
        canvas.id,
        form_data,
        actor_id=actor.id,
        tenant_id=actor.tenant_id,
        workspace_id=actor.workspace_id,
    )
    assert claimed_digest

    result = asyncio.run(validate(
        "canvas.submit",
        _frozen_submit_context(
            canvas_id=canvas.id,
            audit_id=fabricated_audit_id,
            operation_id=operation_id,
            material_sha256=claimed_digest,
        ),
    ))
    assert result is not None and result.verified is False, result
    assert "not found" in result.evidence

    with app_client.Session() as db:
        assert db.query(CanvasAudit).filter_by(
            canvas_id=canvas.id, action_type="submit").count() == 0
        assert db.query(Canvas).filter(Canvas.id == canvas.id).count() == 1


def test_canvas_submit_oracle_refutes_self_report_bound_to_another_operation(app_client):
    """Pointing at a real receipt for a different operation is still a lie."""
    from tools.canvas_crud_tool import submit_material_digest

    actor, canvas = _seed_submit_form(app_client)
    committed = app_client.client.post("/api/canvas/submit", json={
        "canvas_id": canvas.id,
        "form_data": {"quantity": 0},
        "operation_id": "actually-committed-operation",
    })
    assert committed.status_code == 200, committed.text
    committed_body = committed.json()

    claimed_operation = "claimed-but-not-committed-operation"
    claimed_digest = submit_material_digest(
        canvas.id,
        {"quantity": 0},
        actor_id=actor.id,
        tenant_id=actor.tenant_id,
        workspace_id=actor.workspace_id,
    )
    result = asyncio.run(validate(
        "canvas.submit",
        _frozen_submit_context(
            canvas_id=canvas.id,
            audit_id=committed_body["audit_id"],
            operation_id=claimed_operation,
            material_sha256=claimed_digest,
        ),
    ))
    assert result is not None and result.verified is False, result
    assert "operation_id" in result.evidence

    with app_client.Session() as db:
        rows = db.query(CanvasAudit).filter_by(
            canvas_id=canvas.id, action_type="submit").all()
        assert len(rows) == 1
        assert rows[0].details_json["operation_id"] == (
            "actually-committed-operation")


def test_submit_service_refuses_writer_self_report_without_durable_row(
        app_client, monkeypatch):
    """The production envelope never promotes a writer's claim to success."""
    import core.canvas_write_service as service
    from tools.canvas_crud_tool import deterministic_submit_audit_id

    actor, canvas = _seed_submit_form(app_client)
    operation_id = "self-reported-service-operation"
    claimed_audit_id = deterministic_submit_audit_id(
        actor.id, canvas.id, operation_id)

    async def fabricated_success(**_kwargs):
        # Exactly the shape a lying/faulty writer could return: success,
        # committed outcome and a deterministic-looking receipt id.
        return {
            "success": True,
            "write_outcome": "committed",
            "canvas_id": canvas.id,
            "canvas_type": "form",
            "audit_id": claimed_audit_id,
            "operation_id": operation_id,
            "action_type": "submit",
            "agent_id": None,
            "agent_execution_id": None,
            "material_sha256": "f" * 64,
            "submitted_at": "2026-11-12T00:00:00+00:00",
        }

    monkeypatch.setattr(service, "submit_canvas_event", fabricated_success)
    response = app_client.client.post("/api/canvas/submit", json={
        "canvas_id": canvas.id,
        "form_data": {"quantity": 0},
        "operation_id": operation_id,
    })
    assert response.status_code == 503, response.text
    body = response.json()
    assert body["success"] is False
    assert body["status"] == "committed_unverified"
    assert body["verification"]["status"] == "refuted"
    assert body["verification"]["replay"] == "do_not_repeat"
    assert body["audit_id"] == claimed_audit_id

    with app_client.Session() as db:
        assert db.query(CanvasAudit).filter_by(
            canvas_id=canvas.id, action_type="submit").count() == 0


@pytest.mark.parametrize("missing_key", [
    "audit_id",
    "_oracle_expected_operation_id",
    "_oracle_expected_material_sha256",
    "_oracle_expected_actor_id",
])
def test_canvas_submit_oracle_refuses_incomplete_self_report(app_client, missing_key):
    actor, canvas = _seed_submit_form(app_client)
    ctx = _frozen_submit_context(
        canvas_id=canvas.id,
        audit_id="missing-receipt",
        operation_id="missing-binding",
        material_sha256="0" * 64,
    )
    ctx.pop(missing_key)
    result = asyncio.run(validate("canvas.submit", ctx))
    assert result is not None and result.verified is False, result
