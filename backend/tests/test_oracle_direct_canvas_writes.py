"""ORACLE-01 bounded slice: verified direct HTTP canvas save/restore.

The direct PUT/restore routes now freeze the request material, dispatch the
existing canvas CRUD tool, and re-derive the committed result with the existing
canvas.update / canvas.restore_version postcondition verifiers. These controls
exercise the mounted routes, authentication, CRUD and SQLite persistence, with
only the verifier fault seam doubled where needed.
"""
from __future__ import annotations

import asyncio

import pytest

from core.models import Canvas, CanvasAudit
from core.oracle import OracleResult, validate
from core.oracle.postcondition_verifiers import canvas_content_digest
from tests.test_covpush_canvasroutes import (  # noqa: F401
    client,
    users,
    _make_audit,
    _make_canvas,
    _make_user,
)


def _latest_audit(db, canvas_id):
    return (
        db.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == canvas_id)
        .order_by(CanvasAudit.created_at.desc(), CanvasAudit.id.desc())
        .first()
    )


def _audit_count(db, canvas_id):
    return db.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == canvas_id).count()


def test_direct_put_is_verified_against_durable_material(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id, content={"blocks": []})
    payload = {"blocks": [{"type": "paragraph", "text": "exact material"}]}
    before = _audit_count(db_session, canvas.id)

    response = client.put(f"/api/canvas/{canvas.id}", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "verified", body
    assert body["verification"]["status"] == "verified", body
    assert body["write_outcome"] == "committed"
    assert body["audit_id"]

    db_session.expire_all()
    assert _audit_count(db_session, canvas.id) == before + 1
    latest = _latest_audit(db_session, canvas.id)
    assert latest.id == body["audit_id"]
    assert (latest.details_json or {}).get("content") == payload
    mirror = db_session.query(Canvas).filter(Canvas.id == canvas.id).one()
    assert mirror.content == payload


def test_direct_put_same_title_and_length_still_checks_exact_content(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"blocks": [{"t": "old"}]},
        name="same title")
    payload = {"blocks": [{"t": "new"}]}

    response = client.put(
        f"/api/canvas/{canvas.id}?title=same%20title", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "verified", body
    db_session.expire_all()
    latest = _latest_audit(db_session, canvas.id)
    assert (latest.details_json or {}).get("content") == payload


def test_direct_put_duplicate_operation_is_idempotent(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)
    payload = {"blocks": [{"t": "once"}]}

    first = client.put(
        f"/api/canvas/{canvas.id}?operation_id=op-direct-1", json=payload)
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["status"] == "verified", first_body
    count_after_first = _audit_count(db_session, canvas.id)

    second = client.put(
        f"/api/canvas/{canvas.id}?operation_id=op-direct-1", json=payload)
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert second_body["success"] is True
    assert second_body["already_applied"] is True, second_body
    assert second_body["audit_id"] == first_body["audit_id"]
    assert second_body["verification"]["status"] == "verified"
    assert _audit_count(db_session, canvas.id) == count_after_first


def test_direct_put_byte_identical_without_operation_is_a_distinct_edit(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)
    payload = {"blocks": [{"t": "deliberate"}]}
    before = _audit_count(db_session, canvas.id)

    first = client.put(f"/api/canvas/{canvas.id}", json=payload)
    second = client.put(f"/api/canvas/{canvas.id}", json=payload)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["status"] == "verified"
    assert second.json()["status"] == "verified"
    assert _audit_count(db_session, canvas.id) == before + 2


def test_direct_restore_is_verified_and_append_only(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, canvas_type="email",
        content={"to": "a@b.c", "subject": "v1", "body": "original"})
    target = (
        db_session.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == canvas.id,
                CanvasAudit.action_type == "create")
        .first()
    )
    _make_audit(
        db_session, canvas.id, "update",
        details={"content": {
            "to": "a@b.c", "subject": "v2", "body": "overwritten"}},
        user_id=user.id, canvas_type="email")
    before = _audit_count(db_session, canvas.id)

    response = client.post(
        f"/api/canvas/{canvas.id}/restore", json={"audit_id": target.id})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "verified", body.get("verification")
    assert body["verification"]["status"] == "verified", body.get("verification")
    assert body["restored_from"] == target.id
    assert body["audit_id"]
    assert _audit_count(db_session, canvas.id) == before + 1
    db_session.expire_all()
    latest = _latest_audit(db_session, canvas.id)
    assert latest.id == body["audit_id"]
    assert latest.details_json["restored_from"]["audit_id"] == target.id
    assert latest.details_json["content"]["body"] == "original"


def test_direct_restore_no_change_is_truthful_and_adds_no_audit(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)
    target = (
        db_session.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == canvas.id,
                CanvasAudit.action_type == "create")
        .first()
    )
    before = _audit_count(db_session, canvas.id)

    response = client.post(
        f"/api/canvas/{canvas.id}/restore", json={"audit_id": target.id})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["no_change"] is True
    assert body["status"] == "no_change", body
    assert body["verification"]["status"] == "verified"
    assert body["restored_from"] == target.id
    assert _audit_count(db_session, canvas.id) == before


def test_direct_put_workspace_mismatch_is_committed_but_unverified(
        client, db_session, users):
    user = _make_user(db_session)
    user.workspace_id = "ws-expected"
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)
    canvas.workspace_id = "ws-other"
    db_session.commit()
    payload = {"blocks": [{"t": "scope"}]}

    response = client.put(f"/api/canvas/{canvas.id}", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "committed_unverified", body
    assert body["verification"]["status"] == "refuted", body
    assert body["verification"]["replay"] == "do_not_repeat"
    assert body["audit_id"]

    # The committed effect is still there; the response did not lie about it.
    db_session.expire_all()
    latest = _latest_audit(db_session, canvas.id)
    assert latest.id == body["audit_id"]
    assert (latest.details_json or {}).get("content") == payload


def test_direct_put_stale_prior_audit_is_refused_without_effect(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)
    stale = (
        db_session.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == canvas.id,
                CanvasAudit.action_type == "create")
        .first()
    )
    first = client.put(
        f"/api/canvas/{canvas.id}", json={"blocks": [{"t": "first"}]})
    assert first.status_code == 200
    before = _audit_count(db_session, canvas.id)

    response = client.put(
        f"/api/canvas/{canvas.id}"
        f"?expected_prior_audit_id={stale.id}",
        json={"blocks": [{"t": "stale"}]})
    assert response.status_code == 409, response.text
    assert _audit_count(db_session, canvas.id) == before


def test_direct_restore_foreign_canvas_is_refused_without_effect(
        client, db_session, users):
    owner = _make_user(db_session)
    canvas = _make_canvas(db_session, owner.id)
    target = (
        db_session.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == canvas.id,
                CanvasAudit.action_type == "create")
        .first()
    )
    users["current"] = _make_user(db_session)
    before = _audit_count(db_session, canvas.id)

    response = client.post(
        f"/api/canvas/{canvas.id}/restore", json={"audit_id": target.id})
    assert response.status_code == 404, response.text
    assert _audit_count(db_session, canvas.id) == before


def test_direct_put_oracle_unavailable_preserves_committed_identity(
        client, db_session, users, monkeypatch):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)
    payload = {"blocks": [{"t": "oracle-down"}]}

    async def _unavailable(_action, _ctx):
        return None

    monkeypatch.setattr(
        "core.canvas_write_service.validate", _unavailable)
    response = client.put(f"/api/canvas/{canvas.id}", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "committed_unverified", body
    assert body["verification"]["status"] == "unavailable"
    assert body["verification"]["replay"] == "do_not_repeat"
    assert body["audit_id"]

    db_session.expire_all()
    latest = _latest_audit(db_session, canvas.id)
    assert latest.id == body["audit_id"]
    assert (latest.details_json or {}).get("content") == payload


def test_direct_put_oracle_refuted_preserves_committed_identity(
        client, db_session, users, monkeypatch):
    from core.oracle import OracleResult

    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)

    async def _refuted(action, _ctx):
        return OracleResult(
            action=action, verified=False, evidence="forced refutation")

    monkeypatch.setattr(
        "core.canvas_write_service.validate", _refuted)
    response = client.put(
        f"/api/canvas/{canvas.id}", json={"blocks": [{"t": "refuted"}]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "committed_unverified", body
    assert body["verification"]["status"] == "refuted"
    assert body["verification"]["replay"] == "do_not_repeat"
    assert body["audit_id"]


def test_direct_put_kill_switch_never_fabricates_verified(
        client, db_session, users, monkeypatch):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)
    monkeypatch.setattr(
        "core.canvas_write_service.oracle_verifier_enabled",
        lambda: False)

    response = client.put(
        f"/api/canvas/{canvas.id}", json={"blocks": [{"t": "disabled"}]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "committed_unverified", body
    assert body["verification"]["status"] == "disabled"
    assert body["verification"]["replay"] == "do_not_repeat"
    assert body["audit_id"]


def test_direct_put_verifier_gets_no_request_session(
        client, db_session, users, monkeypatch):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)
    captured = {}

    async def _capture(action, ctx):
        captured.update(ctx)
        return OracleResult(action=action, verified=True, evidence="captured")

    monkeypatch.setattr("core.canvas_write_service.validate", _capture)
    response = client.put(
        f"/api/canvas/{canvas.id}", json={"blocks": [{"t": "ctx"}]})
    assert response.status_code == 200, response.text
    assert "db" not in captured, (
        "the verifier must open its own read session, not reuse the request's")
    assert captured["_oracle_expected_actor_id"] == user.id
    assert captured["_oracle_expected_canvas_id"] == canvas.id


def test_direct_put_tenant_mismatch_is_committed_but_unverified(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)
    canvas.tenant_id = "t2"
    db_session.commit()
    payload = {"blocks": [{"t": "tenant"}]}

    response = client.put(f"/api/canvas/{canvas.id}", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "committed_unverified", body
    assert body["verification"]["status"] == "refuted"
    db_session.expire_all()
    latest = _latest_audit(db_session, canvas.id)
    assert latest.id == body["audit_id"]


def test_direct_put_oracle_exception_preserves_committed_identity(
        client, db_session, users, monkeypatch):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)

    async def _raise(_action, _ctx):
        raise RuntimeError("oracle crashed")

    monkeypatch.setattr("core.canvas_write_service.validate", _raise)
    response = client.put(
        f"/api/canvas/{canvas.id}", json={"blocks": [{"t": "crash"}]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "committed_unverified", body
    assert body["verification"]["status"] == "unavailable"
    assert body["audit_id"]


def test_direct_restore_wrong_canvas_audit_is_refused_without_effect(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)
    other = _make_canvas(db_session, user.id)
    other_audit = (
        db_session.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == other.id,
                CanvasAudit.action_type == "create")
        .first()
    )
    before = _audit_count(db_session, canvas.id)

    response = client.post(
        f"/api/canvas/{canvas.id}/restore",
        json={"audit_id": other_audit.id})
    assert response.status_code == 404, response.text
    assert _audit_count(db_session, canvas.id) == before


def test_direct_restore_old_identical_material_is_no_change(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"blocks": [{"t": "same"}]})
    target = (
        db_session.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == canvas.id,
                CanvasAudit.action_type == "create")
        .first()
    )
    _make_audit(
        db_session, canvas.id, "update",
        details={"content": {"blocks": [{"t": "same"}]}},
        user_id=user.id, canvas_type="generic")
    before = _audit_count(db_session, canvas.id)

    response = client.post(
        f"/api/canvas/{canvas.id}/restore", json={"audit_id": target.id})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["no_change"] is True
    assert body["status"] == "no_change", body
    assert _audit_count(db_session, canvas.id) == before


def _verifier_ctx(db, canvas, audit, content, **overrides):
    ctx = {
        "db": db,
        "canvas_id": canvas.id,
        "audit_id": audit.id,
        "write_outcome": "committed",
        "_oracle_expected_canvas_id": canvas.id,
        "_oracle_expected_canvas_content_sha256": (
            canvas_content_digest(content)),
        "_oracle_expected_tenant_id": canvas.tenant_id,
        "_oracle_expected_actor_id": audit.user_id,
        "_oracle_expected_workspace_id": canvas.workspace_id or "",
    }
    ctx.update(overrides)
    return ctx


def test_verifier_refuses_operation_mismatch(db_session):
    user = _make_user(db_session)
    canvas = _make_canvas(db_session, user.id)
    content = {"blocks": [{"t": "op"}]}
    canvas.content = content
    audit = CanvasAudit(
        canvas_id=canvas.id, tenant_id="t1", action_type="update",
        user_id=user.id, canvas_type="generic",
        details_json={
            "content": content, "operation_id": "op-actual",
            "review_status": "accepted"})
    db_session.add(audit)
    db_session.commit()

    result = asyncio.run(validate(
        "canvas.update",
        _verifier_ctx(
            db_session, canvas, audit, content,
            _oracle_expected_operation_id="op-expected")))
    assert result is not None and result.verified is False
    assert "operation_id" in result.evidence


def test_verifier_refuses_absent_audit(db_session):
    user = _make_user(db_session)
    canvas = _make_canvas(db_session, user.id)
    content = {"blocks": [{"t": "absent"}]}
    result = asyncio.run(validate(
        "canvas.update",
        {
            "db": db_session,
            "canvas_id": canvas.id,
            "audit_id": "missing-audit",
            "write_outcome": "committed",
            "_oracle_expected_canvas_id": canvas.id,
            "_oracle_expected_canvas_content_sha256": (
                canvas_content_digest(content)),
            "_oracle_expected_tenant_id": canvas.tenant_id,
            "_oracle_expected_actor_id": user.id,
        }))
    assert result is not None and result.verified is False
    assert "not found" in result.evidence


def test_verifier_refuses_stale_mirror(db_session):
    user = _make_user(db_session)
    canvas = _make_canvas(db_session, user.id)
    content = {"blocks": [{"t": "audit"}]}
    canvas.content = content
    audit = CanvasAudit(
        canvas_id=canvas.id, tenant_id="t1", action_type="update",
        user_id=user.id, canvas_type="generic",
        details_json={"content": content, "review_status": "accepted"})
    db_session.add(audit)
    db_session.commit()
    canvas.content = {"blocks": [{"t": "stale-mirror"}]}
    db_session.commit()

    result = asyncio.run(validate(
        "canvas.update",
        _verifier_ctx(db_session, canvas, audit, content)))
    assert result is not None and result.verified is False
    assert "mirror" in result.evidence


def test_verifier_refuses_restore_target_mismatch(db_session):
    user = _make_user(db_session)
    canvas = _make_canvas(db_session, user.id)
    content = {"blocks": [{"t": "restore"}]}
    canvas.content = content
    audit = CanvasAudit(
        canvas_id=canvas.id, tenant_id="t1", action_type="update",
        user_id=user.id, canvas_type="generic",
        details_json={
            "content": content,
            "restored_from": {"audit_id": "target-actual"},
            "review_status": "accepted"})
    db_session.add(audit)
    db_session.commit()

    result = asyncio.run(validate(
        "canvas.restore_version",
        _verifier_ctx(
            db_session, canvas, audit, content,
            _oracle_expected_restore_audit_id="target-expected")))
    assert result is not None and result.verified is False
    assert "restored_from" in result.evidence
