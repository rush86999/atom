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
from sqlalchemy.orm import sessionmaker

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


def test_direct_put_foreign_workspace_refuses_before_effect(
        client, db_session, users):
    user = _make_user(db_session)
    user.workspace_id = "ws-current"
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"blocks": [{"t": "old"}]})
    canvas.workspace_id = "ws-other"
    db_session.commit()
    payload = {"blocks": [{"t": "unauthorized"}]}
    before = _audit_count(db_session, canvas.id)
    mirror_before = canvas.content

    response = client.put(f"/api/canvas/{canvas.id}", json=payload)
    assert response.status_code == 403, response.text
    assert _audit_count(db_session, canvas.id) == before
    db_session.expire_all()
    mirror = db_session.query(Canvas).filter(Canvas.id == canvas.id).one()
    assert mirror.content == mirror_before


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


def test_direct_put_foreign_tenant_refuses_before_effect(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"blocks": [{"t": "old"}]})
    canvas.tenant_id = "t-other"
    db_session.commit()
    payload = {"blocks": [{"t": "unauthorized"}]}
    before = _audit_count(db_session, canvas.id)
    mirror_before = canvas.content

    response = client.put(f"/api/canvas/{canvas.id}", json=payload)
    assert response.status_code == 403, response.text
    assert _audit_count(db_session, canvas.id) == before
    db_session.expire_all()
    mirror = db_session.query(Canvas).filter(Canvas.id == canvas.id).one()
    assert mirror.content == mirror_before


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


def test_direct_put_duplicate_operation_after_later_edit_is_not_verified(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)
    payload_a = {"blocks": [{"t": "operation-a"}]}
    payload_b = {"blocks": [{"t": "later-edit"}]}

    first = client.put(
        f"/api/canvas/{canvas.id}?operation_id=op-late-1", json=payload_a)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "verified", first.json()

    later = client.put(f"/api/canvas/{canvas.id}", json=payload_b)
    assert later.status_code == 200, later.text
    assert later.json()["status"] == "verified", later.json()

    before = _audit_count(db_session, canvas.id)
    retry = client.put(
        f"/api/canvas/{canvas.id}?operation_id=op-late-1", json=payload_a)
    assert retry.status_code == 200, retry.text
    body = retry.json()
    assert body["already_applied"] is True, body
    assert body["audit_id"] == first.json()["audit_id"]
    assert body["status"] == "committed_unverified", body
    assert body["verification"]["status"] == "refuted", body
    assert body["verification"]["replay"] == "do_not_repeat"
    assert _audit_count(db_session, canvas.id) == before

    db_session.expire_all()
    latest = _latest_audit(db_session, canvas.id)
    assert latest.details_json["content"] == payload_b
    mirror = db_session.query(Canvas).filter(Canvas.id == canvas.id).one()
    assert mirror.content == payload_b, (
        "a duplicate retry must not revert a later edit")


def test_direct_put_effect_unknown_keeps_identity(
        client, db_session, users, monkeypatch):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)
    payload = {"blocks": [{"t": "unknown-effect"}]}

    async def _unknown(**_kwargs):
        return {
            "success": False,
            "write_outcome": "unknown",
            "audit_id": "audit-maybe-committed",
            "operation_id": "op-unknown-1",
            "error": "commit status unknown",
        }

    monkeypatch.setattr(
        "core.canvas_write_service.update_canvas_content", _unknown)
    response = client.put(
        f"/api/canvas/{canvas.id}?operation_id=op-unknown-1", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is False
    assert body["status"] == "effect_unknown", body
    assert body["verification"]["status"] == "unavailable"
    assert body["verification"]["effect"] == "unknown"
    assert body["verification"]["replay"] == "do_not_repeat"
    assert body["audit_id"] == "audit-maybe-committed"
    assert body["operation_id"] == "op-unknown-1"


def test_direct_restore_no_change_kill_switch_is_unverified_no_effect(
        client, db_session, users, monkeypatch):
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
    monkeypatch.setattr(
        "core.canvas_write_service.oracle_verifier_enabled",
        lambda: False)

    response = client.post(
        f"/api/canvas/{canvas.id}/restore", json={"audit_id": target.id})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["no_change"] is True
    assert body["status"] == "no_change_unverified", body
    assert body["verification"]["status"] == "disabled"
    assert body["verification"]["effect"] == "none"
    assert body["verification"]["replay"] == "do_not_repeat"
    assert body["restored_from"] == target.id
    assert _audit_count(db_session, canvas.id) == before


def test_direct_restore_foreign_workspace_refuses_before_effect(
        client, db_session, users):
    user = _make_user(db_session)
    user.workspace_id = "ws-current"
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"blocks": [{"t": "old"}]})
    canvas.workspace_id = "ws-other"
    db_session.commit()
    target = (
        db_session.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == canvas.id,
                CanvasAudit.action_type == "create")
        .first()
    )
    before = _audit_count(db_session, canvas.id)
    mirror_before = canvas.content

    response = client.post(
        f"/api/canvas/{canvas.id}/restore", json={"audit_id": target.id})
    assert response.status_code == 403, response.text
    assert _audit_count(db_session, canvas.id) == before
    db_session.expire_all()
    mirror = db_session.query(Canvas).filter(Canvas.id == canvas.id).one()
    assert mirror.content == mirror_before


def test_direct_restore_foreign_tenant_refuses_before_effect(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"blocks": [{"t": "old"}]})
    canvas.tenant_id = "t-other"
    db_session.commit()
    target = (
        db_session.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == canvas.id,
                CanvasAudit.action_type == "create")
        .first()
    )
    before = _audit_count(db_session, canvas.id)
    mirror_before = canvas.content

    response = client.post(
        f"/api/canvas/{canvas.id}/restore", json={"audit_id": target.id})
    assert response.status_code == 403, response.text
    assert _audit_count(db_session, canvas.id) == before
    db_session.expire_all()
    mirror = db_session.query(Canvas).filter(Canvas.id == canvas.id).one()
    assert mirror.content == mirror_before


def test_direct_restore_no_change_stale_mirror_is_not_verified(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"text": "accepted"})
    target = (
        db_session.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == canvas.id,
                CanvasAudit.action_type == "create")
        .first()
    )
    canvas.content = {"text": "stale mirror"}
    db_session.commit()
    before = _audit_count(db_session, canvas.id)

    response = client.post(
        f"/api/canvas/{canvas.id}/restore", json={"audit_id": target.id})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["no_change"] is True
    assert body["status"] == "no_change_unverified", body
    assert body["verification"]["status"] == "refuted", body
    assert body["verification"]["effect"] == "none"
    assert body["verification"]["replay"] == "do_not_repeat"
    assert "mirror_match=False" in body["verification"]["evidence"]
    assert "audit_id" not in body or body.get("audit_id") is None
    assert "operation_id" not in body or body.get("operation_id") is None
    assert _audit_count(db_session, canvas.id) == before
    db_session.expire_all()
    mirror = db_session.query(Canvas).filter(Canvas.id == canvas.id).one()
    assert mirror.content == {"text": "stale mirror"}


def test_direct_put_old_identical_audit_is_not_verified(
        client, db_session, users, monkeypatch):
    user = _make_user(db_session)
    users["current"] = user
    payload = {"text": "same material"}
    canvas = _make_canvas(db_session, user.id, content=payload)
    old = CanvasAudit(
        canvas_id=canvas.id, tenant_id=user.tenant_id,
        action_type="update", user_id=user.id, canvas_type="generic",
        details_json={"content": payload, "review_status": "accepted"})
    db_session.add(old)
    db_session.commit()
    old_id = old.id
    before = _audit_count(db_session, canvas.id)

    async def _stale_result(**_kwargs):
        return {
            "success": True,
            "write_outcome": "committed",
            "canvas_id": canvas.id,
            "audit_id": old_id,
            "already_applied": False,
        }

    monkeypatch.setattr(
        "core.canvas_write_service.update_canvas_content", _stale_result)
    response = client.put(f"/api/canvas/{canvas.id}", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "committed_unverified", body
    assert body["verification"]["status"] == "refuted", body
    assert body["verification"]["replay"] == "do_not_repeat"
    assert body["audit_id"] == old_id
    assert _audit_count(db_session, canvas.id) == before


def test_direct_put_manual_save_gets_server_operation_identity(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)
    payload = {"blocks": [{"t": "server identity"}]}

    first = client.put(f"/api/canvas/{canvas.id}", json=payload)
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["status"] == "verified", first_body
    assert first_body["operation_id"].startswith("http-canvas-update:")
    db_session.expire_all()
    latest = _latest_audit(db_session, canvas.id)
    assert latest.id == first_body["audit_id"]
    assert (latest.details_json or {}).get("operation_id") == (
        first_body["operation_id"])

    second = client.put(f"/api/canvas/{canvas.id}", json=payload)
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert second_body["status"] == "verified", second_body
    assert second_body["operation_id"] != first_body["operation_id"]
    assert second_body["audit_id"] != first_body["audit_id"]


def test_direct_put_operation_id_different_material_is_refused(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)

    first = client.put(
        f"/api/canvas/{canvas.id}?operation_id=op-bound-1",
        json={"blocks": [{"t": "first material"}]})
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "verified"
    before = _audit_count(db_session, canvas.id)

    second = client.put(
        f"/api/canvas/{canvas.id}?operation_id=op-bound-1",
        json={"blocks": [{"t": "different material"}]})
    assert second.status_code == 409, second.text
    assert _audit_count(db_session, canvas.id) == before
    db_session.expire_all()
    latest = _latest_audit(db_session, canvas.id)
    assert (latest.details_json or {}).get("content") == {
        "blocks": [{"t": "first material"}]}


def test_direct_restore_gets_server_operation_identity(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"blocks": [{"t": "target"}]})
    target = (
        db_session.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == canvas.id,
                CanvasAudit.action_type == "create")
        .first()
    )
    _make_audit(
        db_session, canvas.id, "update",
        details={"content": {"blocks": [{"t": "newer"}]}},
        user_id=user.id, canvas_type="generic")

    response = client.post(
        f"/api/canvas/{canvas.id}/restore", json={"audit_id": target.id})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "verified", body
    assert body["operation_id"].startswith("http-canvas-restore:")
    db_session.expire_all()
    latest = _latest_audit(db_session, canvas.id)
    assert latest.id == body["audit_id"]
    assert (latest.details_json or {}).get("operation_id") == (
        body["operation_id"])


def test_writer_rechecks_scope_after_service_preflight(
        client, db_session, users, monkeypatch):
    user = _make_user(db_session)
    user.workspace_id = "ws-current"
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"blocks": [{"t": "old"}]})
    canvas.workspace_id = "ws-other"
    db_session.commit()
    before = _audit_count(db_session, canvas.id)
    mirror_before = canvas.content

    # Simulate a canvas moved after the service preflight: the writer's
    # same-transaction scope gate must still refuse before any append.
    monkeypatch.setattr(
        "core.canvas_write_service._preflight_scope",
        lambda *args, **kwargs: None)
    response = client.put(
        f"/api/canvas/{canvas.id}",
        json={"blocks": [{"t": "moved"}]})
    assert response.status_code == 403, response.text
    assert _audit_count(db_session, canvas.id) == before
    db_session.expire_all()
    mirror = db_session.query(Canvas).filter(Canvas.id == canvas.id).one()
    assert mirror.content == mirror_before


def test_direct_put_post_commit_stale_mirror_is_committed_unverified(
        client, db_session, users, monkeypatch):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)
    payload = {"blocks": [{"t": "authorized commit"}]}

    from core.canvas_write_service import update_canvas_content as real_update

    async def _commit_then_stale(**kwargs):
        result = await real_update(**kwargs)
        db_session.expire_all()
        mirror = (
            db_session.query(Canvas)
            .filter(Canvas.id == kwargs["canvas_id"])
            .one()
        )
        mirror.content = {"blocks": [{"t": "stale after commit"}]}
        db_session.commit()
        return result

    monkeypatch.setattr(
        "core.canvas_write_service.update_canvas_content",
        _commit_then_stale)
    response = client.put(f"/api/canvas/{canvas.id}", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "committed_unverified", body
    assert body["verification"]["status"] == "refuted", body
    assert body["verification"]["replay"] == "do_not_repeat"
    assert body["audit_id"]
    db_session.expire_all()
    latest = _latest_audit(db_session, canvas.id)
    assert latest.id == body["audit_id"]
    assert (latest.details_json or {}).get("content") == payload


def test_same_scope_coeditor_can_save_without_creator_ownership(
        client, db_session, users):
    owner = _make_user(db_session)
    coeditor = _make_user(db_session)
    coeditor.workspace_id = "ws-shared"
    canvas = _make_canvas(db_session, owner.id)
    canvas.workspace_id = "ws-shared"
    db_session.commit()
    _make_audit(
        db_session, canvas.id, "update",
        details={"content": {"blocks": [{"t": "coeditor history"}]}},
        user_id=coeditor.id, canvas_type="generic")
    users["current"] = coeditor

    response = client.put(
        f"/api/canvas/{canvas.id}",
        json={"blocks": [{"t": "coeditor save"}]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "verified", body
    db_session.expire_all()
    latest = _latest_audit(db_session, canvas.id)
    assert latest.user_id == coeditor.id
    assert (latest.details_json or {}).get("content") == {
        "blocks": [{"t": "coeditor save"}]}


def test_direct_put_commits_across_real_sessions(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from api.canvas_routes import router
    from core.auth import get_current_user
    from core.database import Base, get_db
    from core.models import Canvas, CanvasAudit, User, UserStatus

    engine = create_engine(
        f"sqlite:///{tmp_path}/oracle-multisession.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session() as setup:
        user = User(
            id="u-multisession",
            email="multisession@example.com",
            hashed_password="x",
            first_name="Multi",
            last_name="Session",
            role="member",
            status=UserStatus.ACTIVE,
            tenant_id="t1",
        )
        setup.add(user)
        setup.commit()
        canvas = Canvas(
            id="c-multisession",
            tenant_id="t1",
            created_by=user.id,
            name="Multi session",
            canvas_type="generic",
            content={"blocks": []},
            style={},
            status="active",
        )
        setup.add(canvas)
        setup.add(CanvasAudit(
            canvas_id=canvas.id,
            tenant_id="t1",
            action_type="create",
            user_id=user.id,
            canvas_type="generic",
            details_json={
                "content": {"blocks": []},
                "review_status": "accepted",
            },
            created_at=datetime.now(timezone.utc),
        ))
        setup.commit()
        user_id = user.id
        canvas_id = canvas.id

    @contextmanager
    def _fresh_session():
        session = Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr("core.database.SessionLocal", Session)
    monkeypatch.setattr("core.database.get_db_session", _fresh_session)

    app = FastAPI()
    app.include_router(router)

    def _request_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _request_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=user_id,
        email="multisession@example.com",
        tenant_id="t1",
        workspace_id=None,
        role="member",
    )

    payload = {"blocks": [{"t": "durable across sessions"}]}
    with TestClient(app) as client:
        response = client.put(f"/api/canvas/{canvas_id}", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "verified", body

    with Session() as fresh:
        latest = (
            fresh.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == canvas_id)
            .order_by(CanvasAudit.created_at.desc(), CanvasAudit.id.desc())
            .first()
        )
        assert latest.id == body["audit_id"]
        assert (latest.details_json or {}).get("content") == payload
        assert (latest.details_json or {}).get("operation_id") == (
            body["operation_id"])
        mirror = fresh.query(Canvas).filter(Canvas.id == canvas_id).one()
        assert mirror.content == payload
    engine.dispose()


def test_direct_restore_foreign_target_tenant_refuses_before_effect(
        client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"blocks": [{"t": "current"}]})
    target = CanvasAudit(
        canvas_id=canvas.id,
        tenant_id="t-other",
        action_type="update",
        user_id=user.id,
        canvas_type="generic",
        details_json={
            "content": {"blocks": [{"t": "foreign"}]},
            "review_status": "accepted",
        },
    )
    db_session.add(target)
    db_session.commit()
    before = _audit_count(db_session, canvas.id)
    mirror_before = canvas.content

    response = client.post(
        f"/api/canvas/{canvas.id}/restore", json={"audit_id": target.id})
    assert response.status_code == 403, response.text
    assert _audit_count(db_session, canvas.id) == before
    db_session.expire_all()
    mirror = db_session.query(Canvas).filter(Canvas.id == canvas.id).one()
    assert mirror.content == mirror_before


def test_direct_put_null_workspace_cannot_edit_scoped_canvas(
        client, db_session, users):
    user = _make_user(db_session)
    user.workspace_id = None
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"blocks": [{"t": "old"}]})
    canvas.workspace_id = "ws-real"
    db_session.commit()
    before = _audit_count(db_session, canvas.id)
    mirror_before = canvas.content

    response = client.put(
        f"/api/canvas/{canvas.id}",
        json={"blocks": [{"t": "legacy principal"}]})
    assert response.status_code == 403, response.text
    assert _audit_count(db_session, canvas.id) == before
    db_session.expire_all()
    mirror = db_session.query(Canvas).filter(Canvas.id == canvas.id).one()
    assert mirror.content == mirror_before


def test_direct_put_workspace_principal_can_edit_legacy_unscoped_canvas(
        client, db_session, users):
    user = _make_user(db_session)
    user.workspace_id = "ws-current"
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"blocks": [{"t": "legacy"}]})
    assert canvas.workspace_id is None
    payload = {"blocks": [{"t": "legacy save"}]}

    response = client.put(f"/api/canvas/{canvas.id}", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "verified", body
    db_session.expire_all()
    latest = _latest_audit(db_session, canvas.id)
    assert latest.id == body["audit_id"]
    assert (latest.details_json or {}).get("content") == payload


def test_direct_put_post_commit_scope_change_is_committed_unverified(
        client, db_session, users, monkeypatch):
    user = _make_user(db_session)
    user.workspace_id = "ws-current"
    users["current"] = user
    canvas = _make_canvas(db_session, user.id)
    canvas.workspace_id = "ws-current"
    db_session.commit()
    payload = {"blocks": [{"t": "authorized then moved"}]}

    from core.canvas_write_service import update_canvas_content as real_update

    async def _commit_then_move(**kwargs):
        result = await real_update(**kwargs)
        db_session.expire_all()
        moved = (
            db_session.query(Canvas)
            .filter(Canvas.id == kwargs["canvas_id"])
            .one()
        )
        moved.workspace_id = "ws-other"
        db_session.commit()
        return result

    monkeypatch.setattr(
        "core.canvas_write_service.update_canvas_content",
        _commit_then_move)
    response = client.put(f"/api/canvas/{canvas.id}", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "committed_unverified", body
    assert body["verification"]["status"] == "refuted", body
    assert body["verification"]["replay"] == "do_not_repeat"
    assert body["audit_id"]
    db_session.expire_all()
    latest = _latest_audit(db_session, canvas.id)
    assert latest.id == body["audit_id"]
    assert (latest.details_json or {}).get("content") == payload


def _scope_move_after_check(monkeypatch, db_session, canvas_id, field, value):
    """Move the canvas scope in a separate committed session after the final check."""
    from sqlalchemy.orm import sessionmaker

    from tools import canvas_crud_tool as crud

    original = crud.canvas_write_scope_error
    moved = []

    def check_then_move(db, *args, **kwargs):
        error = original(db, *args, **kwargs)
        if error is None and kwargs.get("lock") and not moved:
            with sessionmaker(bind=db.get_bind())() as other:
                other.query(Canvas).filter_by(id=canvas_id).update(
                    {field: value})
                other.commit()
            moved.append(True)
        return error

    monkeypatch.setattr(crud, "canvas_write_scope_error", check_then_move)
    return moved


def test_direct_put_scope_move_after_writer_check_refuses_before_commit(
        client, db_session, users, monkeypatch):
    user = _make_user(db_session)
    user.workspace_id = "ws-original"
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"text": "current"})
    canvas.workspace_id = "ws-original"
    db_session.commit()
    before = _audit_count(db_session, canvas.id)
    mirror_before = canvas.content
    broadcasts = []
    corrections = []

    async def _record_broadcast(*args, **kwargs):
        broadcasts.append(args)

    monkeypatch.setattr(
        "tools.canvas_crud_tool._broadcast_canvas_update",
        _record_broadcast)
    monkeypatch.setattr(
        "api.canvas_routes._maybe_record_canvas_correction",
        lambda *args, **kwargs: corrections.append(args))
    moved = _scope_move_after_check(
        monkeypatch, db_session, canvas.id, "workspace_id", "ws-revoked")

    response = client.put(
        f"/api/canvas/{canvas.id}", json={"text": "out-of-scope effect"})
    assert moved
    assert response.status_code == 409, response.text
    with sessionmaker(bind=db_session.get_bind())() as read:
        row = read.query(Canvas).filter_by(id=canvas.id).one()
        count = read.query(CanvasAudit).filter_by(
            canvas_id=canvas.id).count()
    assert row.workspace_id == "ws-revoked"
    assert row.content == mirror_before
    assert count == before
    assert broadcasts == []
    assert corrections == []


def test_direct_restore_scope_move_after_writer_check_refuses_before_commit(
        client, db_session, users, monkeypatch):
    from datetime import datetime, timezone, timedelta

    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"text": "current"})
    target = CanvasAudit(
        canvas_id=canvas.id,
        tenant_id=user.tenant_id,
        action_type="update",
        user_id=user.id,
        canvas_type="generic",
        details_json={
            "content": {"text": "historical"},
            "review_status": "accepted",
        },
        created_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(target)
    db_session.commit()
    before = _audit_count(db_session, canvas.id)
    mirror_before = canvas.content
    broadcasts = []

    async def _record_broadcast(*args, **kwargs):
        broadcasts.append(args)

    monkeypatch.setattr(
        "tools.canvas_crud_tool._broadcast_canvas_update",
        _record_broadcast)
    moved = _scope_move_after_check(
        monkeypatch, db_session, canvas.id, "tenant_id", "t-revoked")

    response = client.post(
        f"/api/canvas/{canvas.id}/restore",
        json={"audit_id": target.id})
    assert moved
    assert response.status_code == 409, response.text
    with sessionmaker(bind=db_session.get_bind())() as read:
        row = read.query(Canvas).filter_by(id=canvas.id).one()
        count = read.query(CanvasAudit).filter_by(
            canvas_id=canvas.id).count()
    assert row.tenant_id == "t-revoked"
    assert row.content == mirror_before
    assert count == before
    assert broadcasts == []


def test_direct_put_duplicate_operation_scope_move_refuses_mirror_refresh(
        client, db_session, users, monkeypatch):
    user = _make_user(db_session)
    user.workspace_id = "ws-original"
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"text": "current"})
    canvas.workspace_id = "ws-original"
    db_session.commit()
    payload = {"text": "first save"}
    first = client.put(
        f"/api/canvas/{canvas.id}?operation_id=op-scope-dup", json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "verified"
    before = _audit_count(db_session, canvas.id)
    broadcasts = []

    async def _record_broadcast(*args, **kwargs):
        broadcasts.append(args)

    monkeypatch.setattr(
        "tools.canvas_crud_tool._broadcast_canvas_update",
        _record_broadcast)
    moved = _scope_move_after_check(
        monkeypatch, db_session, canvas.id, "workspace_id", "ws-revoked")

    retry = client.put(
        f"/api/canvas/{canvas.id}?operation_id=op-scope-dup", json=payload)
    assert moved
    assert retry.status_code == 409, retry.text
    with sessionmaker(bind=db_session.get_bind())() as read:
        row = read.query(Canvas).filter_by(id=canvas.id).one()
        count = read.query(CanvasAudit).filter_by(
            canvas_id=canvas.id).count()
    assert row.workspace_id == "ws-revoked"
    assert row.content == payload
    assert count == before
    assert broadcasts == []


def test_direct_put_workspace_scoped_unchanged_still_verifies(
        client, db_session, users):
    user = _make_user(db_session)
    user.workspace_id = "ws-original"
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"text": "current"})
    canvas.workspace_id = "ws-original"
    db_session.commit()
    payload = {"text": "same-scope save"}

    response = client.put(f"/api/canvas/{canvas.id}", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "verified", body
    with sessionmaker(bind=db_session.get_bind())() as read:
        row = read.query(Canvas).filter_by(id=canvas.id).one()
        latest = (
            read.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == canvas.id)
            .order_by(CanvasAudit.created_at.desc(),
                      CanvasAudit.id.desc())
            .first()
        )
    assert row.workspace_id == "ws-original"
    assert row.content == payload
    assert latest.id == body["audit_id"]
    assert (latest.details_json or {}).get("content") == payload


def test_direct_restore_workspace_scoped_unchanged_still_verifies(
        client, db_session, users):
    from datetime import datetime, timezone, timedelta

    user = _make_user(db_session)
    user.workspace_id = "ws-original"
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"text": "current"})
    canvas.workspace_id = "ws-original"
    target = CanvasAudit(
        canvas_id=canvas.id,
        tenant_id=user.tenant_id,
        action_type="update",
        user_id=user.id,
        canvas_type="generic",
        details_json={
            "content": {"text": "historical"},
            "review_status": "accepted",
        },
        created_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(target)
    db_session.commit()

    response = client.post(
        f"/api/canvas/{canvas.id}/restore",
        json={"audit_id": target.id})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "verified", body
    with sessionmaker(bind=db_session.get_bind())() as read:
        row = read.query(Canvas).filter_by(id=canvas.id).one()
        latest = (
            read.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == canvas.id)
            .order_by(CanvasAudit.created_at.desc(),
                      CanvasAudit.id.desc())
            .first()
        )
    assert row.workspace_id == "ws-original"
    assert row.content == {"text": "historical"}
    assert latest.id == body["audit_id"]


def test_direct_put_null_to_default_scope_move_refuses_before_commit(
        client, db_session, users, monkeypatch):
    user = _make_user(db_session)
    user.workspace_id = "ws-original"
    users["current"] = user
    canvas = _make_canvas(
        db_session, user.id, content={"text": "current"})
    assert canvas.workspace_id is None
    before = _audit_count(db_session, canvas.id)
    mirror_before = canvas.content
    moved = _scope_move_after_check(
        monkeypatch, db_session, canvas.id, "workspace_id", "default")

    response = client.put(
        f"/api/canvas/{canvas.id}", json={"text": "out-of-scope effect"})
    assert moved
    assert response.status_code == 409, response.text
    with sessionmaker(bind=db_session.get_bind())() as read:
        row = read.query(Canvas).filter_by(id=canvas.id).one()
        count = read.query(CanvasAudit).filter_by(
            canvas_id=canvas.id).count()
    assert row.workspace_id == "default"
    assert row.content == mirror_before
    assert count == before


def test_read_revision_is_latest_event_not_older_content_identity(client, db_session, users):
    from datetime import timedelta
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id, canvas_type="document", content="Original body")
    content_row = _latest_audit(db_session, canvas.id)
    _make_audit(db_session, canvas.id, "email_send_attempt", details={"status":"refused"}, user_id=user.id,
                canvas_type="document", created_at=content_row.created_at + timedelta(seconds=1))
    latest = _latest_audit(db_session, canvas.id)
    response = client.get(f"/api/canvas/{canvas.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "Original body"
    assert body["audit_id"] == content_row.id
    assert body["revision_audit_id"] == latest.id
    assert latest.id != content_row.id


def test_loaded_prior_revision_refuses_after_peer_commits(client, db_session, users):
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id, canvas_type="document", content="Original body")
    loaded = client.get(f"/api/canvas/{canvas.id}").json()["revision_audit_id"]
    peer = client.put(f"/api/canvas/{canvas.id}", params={"canvas_type":"document","expected_prior_audit_id":loaded}, json="Peer winner")
    assert peer.status_code == 200, peer.text
    assert peer.json()["verification"]["status"] == "verified"
    count = _audit_count(db_session, canvas.id)
    stale = client.put(f"/api/canvas/{canvas.id}", params={"canvas_type":"markdown","retype":True,"expected_prior_audit_id":loaded}, json="Stale overwrite")
    assert stale.status_code == 409, stale.text
    assert _audit_count(db_session, canvas.id) == count
    fresh = client.get(f"/api/canvas/{canvas.id}").json()
    assert fresh["content"] == "Peer winner"
    assert fresh["revision_audit_id"] == peer.json()["audit_id"]


def test_verified_update_broadcast_carries_its_exact_revision(client, db_session, users, monkeypatch):
    from unittest.mock import AsyncMock
    from core.websockets import manager
    user = _make_user(db_session)
    users["current"] = user
    canvas = _make_canvas(db_session, user.id, canvas_type="document", content="Before")
    broadcast = AsyncMock()
    monkeypatch.setattr(manager, "broadcast", broadcast)
    response = client.put(f"/api/canvas/{canvas.id}", params={"canvas_type":"document"}, json="After")
    assert response.status_code == 200, response.text
    assert response.json()["verification"]["status"] == "verified"
    broadcast.assert_awaited_once()
    args = broadcast.await_args.args
    assert args[0] == f"user:{user.id}"
    assert args[1]["data"]["revision_audit_id"] == response.json()["audit_id"]
    assert args[1]["data"]["data"] == "After"
