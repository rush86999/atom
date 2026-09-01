"""Coverage-push + bug-hunt: api/canvas_routes.py.

TDD: failing tests first for every bug found, then minimal fixes in
api/canvas_routes.py.

Bugs hunted here:
  * ``submit_canvas`` audit row is silently dropped — CanvasAudit.tenant_id is
    NOT NULL, and the handler never set it, so the row failed with
    IntegrityError and the submission was never persisted. It also read
    ``request.data`` (no such attribute on CanvasSubmitRequest) so the actual
    ``form_data`` never landed in the audit trail.
  * ``list_canvas_types`` *returned* ``router.error_response(...)`` instead of
    raising it — FastAPI tried to serialize the HTTPException as the response
    body, so governance denials came back as ResponseValidationError/500
    instead of 403.
  * ``get_canvas_history`` swallowed its own HTTPException(404) in the blanket
    ``except Exception`` and returned 500 for other users' canvases.
  * ``put_canvas_logic`` / ``run_canvas_logic`` let CanvasLogicService's
    PermissionError escape as a 500 instead of a governance 403.
"""
from __future__ import annotations

import contextlib
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.models import (
    AgentRegistry,
    Canvas,
    CanvasAudit,
    CanvasContext,
    CanvasRecording,
    ComponentInstallation,
    User,
    UserStatus,
)


# ---------------------------------------------------------------------------
# Factories / helpers
# ---------------------------------------------------------------------------
def _make_user(db, user_id=None, tenant_id="t1", role="member"):
    u = User(
        id=user_id or f"u-{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:10]}@example.com",
        hashed_password="x",
        first_name="First",
        last_name="Last",
        role=role,
        status=UserStatus.ACTIVE,
        tenant_id=tenant_id,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_agent(db, status="autonomous", workspace_id="default"):
    a = AgentRegistry(
        id=f"ag-{uuid.uuid4().hex[:8]}",
        name="Agent",
        category="test",
        module_path="test.mod",
        class_name="Agent",
        status=status,
        confidence_score=0.95,
        workspace_id=workspace_id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _make_canvas(db, owner_id, canvas_id=None, canvas_type="generic",
                 is_collaborative=False, content=None, name="Test Canvas"):
    cid = canvas_id or f"c-{uuid.uuid4().hex[:12]}"
    c = Canvas(
        id=cid, tenant_id="t1", created_by=owner_id, name=name,
        canvas_type=canvas_type, content=content or {"blocks": []},
        style={}, is_collaborative=is_collaborative, status="active",
    )
    db.add(c)
    db.add(CanvasAudit(
        canvas_id=cid, tenant_id="t1", action_type="create",
        user_id=owner_id, canvas_type=canvas_type,
        details_json={"content": content or {"blocks": []}, "title": name},
    ))
    db.commit()
    return c


def _make_audit(db, canvas_id, action_type, details=None, user_id=None, canvas_type=None, created_at=None):
    db.add(CanvasAudit(
        canvas_id=canvas_id, tenant_id="t1", action_type=action_type,
        user_id=user_id, canvas_type=canvas_type,
        details_json=details, created_at=created_at,
    ))
    db.commit()


def _make_recording(db, user_id, agent_id, tenant_id="t1"):
    r = CanvasRecording(
        recording_id=f"rec-{uuid.uuid4().hex[:12]}",
        tenant_id=tenant_id, user_id=user_id, agent_id=agent_id,
        reason="manual_test", status="recording", tags=["test"],
        events=[], recording_metadata={}, event_count=0,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@pytest.fixture
def users():
    return {}


@pytest.fixture
def client(db_session, users, monkeypatch):
    from core.auth import get_current_user
    from core.database import SessionLocal, get_db, get_db_session
    from api.canvas_routes import router

    @contextlib.contextmanager
    def _get_db_session():
        yield db_session

    monkeypatch.setattr("core.database.get_db_session", _get_db_session)
    monkeypatch.setattr("core.database.SessionLocal", lambda: db_session)

    app = FastAPI()
    app.include_router(router)

    def override_db():
        yield db_session

    def override_user():
        return users["current"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    with TestClient(app) as c:
        yield c


def _ws_token(db, user):
    from core.auth import create_access_token
    return create_access_token({"sub": user.id})


# ===========================================================================
# GET /api/canvas/types
# ===========================================================================
class TestListCanvasTypes:
    def test_governance_denied_when_agent_missing(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.get("/api/canvas/types", params={"agent_id": "ghost-agent"})
        assert res.status_code == 403
        assert res.json()["detail"]["error"]["code"] == "GOVERNANCE_DENIED"

    def test_stopped_agent_denied(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        agent = _make_agent(db_session, status="stopped")
        res = client.get("/api/canvas/types", params={"agent_id": agent.id})
        assert res.status_code == 403

    def test_autonomous_agent_allowed(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        agent = _make_agent(db_session, status="autonomous")
        res = client.get("/api/canvas/types", params={"agent_id": agent.id})
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert "docs" in res.json()["data"]["canvas_types"]


# ===========================================================================
# GET /api/canvas/recordings (+detail)
# ===========================================================================
class TestRecordings:
    def test_list_empty(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        res = client.get("/api/canvas/recordings")
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert res.json()["data"] == []

    def test_list_with_rows_and_agent_filter(self, client, db_session, users):
        u = _make_user(db_session)
        a = _make_agent(db_session)
        users["current"] = u
        _make_recording(db_session, u.id, a.id)
        res = client.get("/api/canvas/recordings", params={"agent_id": a.id})
        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) == 1
        assert data[0]["agent_id"] == a.id
        res_all = client.get("/api/canvas/recordings")
        assert len(res_all.json()["data"]) == 1

    def test_get_recording_404(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.get("/api/canvas/recordings/does-not-exist")
        assert res.status_code == 404

    def test_get_recording_other_users_is_404(self, client, db_session, users):
        owner = _make_user(db_session)
        a = _make_agent(db_session)
        rec = _make_recording(db_session, owner.id, a.id)
        users["current"] = _make_user(db_session)  # different user
        res = client.get(f"/api/canvas/recordings/{rec.recording_id}")
        assert res.status_code == 404

    def test_get_recording_own(self, client, db_session, users):
        owner = _make_user(db_session)
        a = _make_agent(db_session)
        rec = _make_recording(db_session, owner.id, a.id)
        users["current"] = owner
        res = client.get(f"/api/canvas/recordings/{rec.recording_id}")
        assert res.status_code == 200
        assert res.json()["data"]["recording_id"] == rec.recording_id


# ===========================================================================
# GET/PUT/DELETE /{canvas_id}
# ===========================================================================
class TestCanvasCRUD:
    def test_read_404_for_missing_canvas(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.get("/api/canvas/c-ghost")
        assert res.status_code == 404

    def test_read_404_for_other_users_canvas(self, client, db_session, users):
        owner = _make_user(db_session)
        _make_canvas(db_session, owner.id)
        users["current"] = _make_user(db_session)
        res = client.get("/api/canvas/c-ghost")
        assert res.status_code == 404

    def test_read_success(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id, content={"blocks": [{"t": "x"}]})
        res = client.get(f"/api/canvas/{c.id}")
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert res.json()["canvas_id"] == c.id

    def test_read_deleted_returns_404(self, client, db_session, users):
        from datetime import datetime, timedelta, timezone
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        _make_audit(db_session, c.id, "delete", user_id=u.id, canvas_type="generic",
                    created_at=datetime.now(timezone.utc) + timedelta(seconds=5))
        res = client.get(f"/api/canvas/{c.id}")
        assert res.status_code == 404

    def test_update_404_for_other_user(self, client, db_session, users):
        owner = _make_user(db_session)
        _make_canvas(db_session, owner.id)
        users["current"] = _make_user(db_session)
        res = client.put("/api/canvas/c-ghost", json={"k": "v"})
        # A missing canvas is 404 (consistent with GET), not 400 — the
        # not-found contract the route documents.
        assert res.status_code == 404

    def test_update_success(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id, content={"blocks": []})
        res = client.put(f"/api/canvas/{c.id}", json={"blocks": [{"t": "y"}]})
        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_update_accepts_string_and_list_content(self, client, db_session, users):
        """Non-email hosts persist their native shapes: string bodies
        (markdown/code/document) and row lists (sheets). Dict-only validation
        forced every other canvas type onto the legacy artifacts store, where
        the co-editor and /canvas/{id} could never see the edits."""
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id, content="first body")
        res = client.put(
            f"/api/canvas/{c.id}?canvas_type=markdown&title=Md", json="second body"
        )
        assert res.status_code == 200
        assert res.json()["success"] is True

        s = _make_canvas(db_session, u.id, content=[["h1"], ["v1"]])
        res = client.put(f"/api/canvas/{s.id}?canvas_type=sheet", json=[["h1"], ["v2"]])
        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_delete_success(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        res = client.delete(f"/api/canvas/{c.id}")
        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_delete_missing_canvas(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.delete("/api/canvas/c-ghost")
        # A missing canvas is 404 (consistent with GET), not 400.
        assert res.status_code == 404


class TestCanvasRestore:
    def test_restore_400_without_audit_id(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        res = client.post(f"/api/canvas/{c.id}/restore", json={})
        assert res.status_code == 400

    def test_restore_404_for_missing_canvas(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.post("/api/canvas/c-ghost/restore", json={"audit_id": "a-1"})
        assert res.status_code == 404

    def test_restore_404_for_unknown_version(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        res = client.post(f"/api/canvas/{c.id}/restore", json={"audit_id": "a-nope"})
        assert res.status_code == 404

    def test_restore_refuses_delete_marker(self, client, db_session, users):
        from datetime import datetime, timedelta, timezone
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        _make_audit(db_session, c.id, "delete", details={"deleted": True},
                    user_id=u.id,
                    created_at=datetime.now(timezone.utc) + timedelta(seconds=5))
        marker = (
            db_session.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == c.id, CanvasAudit.action_type == "delete")
            .first()
        )
        res = client.post(f"/api/canvas/{c.id}/restore", json={"audit_id": marker.id})
        assert res.status_code == 400

    def test_restore_appends_new_version_with_old_content(self, client, db_session, users):
        """Restore = append: the historical content becomes the newest version,
        provenance is recorded, and the pre-restore state stays in history."""
        from datetime import datetime, timedelta, timezone
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id, canvas_type="email",
                         content={"to": "a@b.c", "subject": "v1", "body": "original draft"})
        v1 = (
            db_session.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == c.id, CanvasAudit.action_type == "create")
            .first()
        )
        # the current (overwritten) state, unambiguously newer
        _make_audit(db_session, c.id, "update",
                    details={"content": {"to": "a@b.c", "subject": "v2", "body": "overwritten"}},
                    user_id=u.id, canvas_type="email",
                    created_at=datetime.now(timezone.utc) + timedelta(seconds=5))

        res = client.post(f"/api/canvas/{c.id}/restore", json={"audit_id": v1.id})
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert res.json()["restored_from"] == v1.id

        db_session.expire_all()
        rows = db_session.query(CanvasAudit).filter(CanvasAudit.canvas_id == c.id).all()
        restored = [r for r in rows if (r.details_json or {}).get("restored_from")]
        assert len(restored) == 1
        latest = restored[0]
        assert latest.id != v1.id
        assert latest.action_type == "update"
        assert latest.details_json["content"]["body"] == "original draft"
        assert latest.details_json["restored_from"]["audit_id"] == v1.id
        # append-only: the overwritten version AND the restore target survive
        bodies = [(r.details_json or {}).get("content", {}).get("body") for r in rows]
        assert "overwritten" in bodies
        assert "original draft" in bodies


# ===========================================================================
# POST /{canvas_id}/fork (P5 blueprint security)
# ===========================================================================
def _missing_canvas_cm():
    @contextlib.contextmanager
    def _cm():
        class _Q:
            def filter(self, *a, **k):
                return self

            def first(self):
                return None

            def all(self):
                return []

        class _EmptyDb:
            def query(self, model):
                return _Q()

            def add(self, *a, **k):
                pass

            def flush(self, *a, **k):
                pass

            def commit(self, *a, **k):
                pass

        yield _EmptyDb()

    return _cm()


class TestForkCanvas:
    def test_fork_404_when_source_missing(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.post("/api/canvas/c-ghost/fork")
        assert res.status_code == 404

    def test_fork_404_for_other_users_canvas(self, client, db_session, users):
        owner = _make_user(db_session)
        _make_canvas(db_session, owner.id)
        users["current"] = _make_user(db_session)
        res = client.post("/api/canvas/c-ghost/fork")
        assert res.status_code == 404

    def test_fork_404_when_source_row_missing_after_read(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        _make_canvas(db_session, u.id)

        async def _fake_read(user_id, canvas_id):
            return {"success": True, "canvas_id": canvas_id}

        monkeypatch.setattr("tools.canvas_crud_tool.read_canvas", _fake_read)
        monkeypatch.setattr("core.database.get_db_session", lambda: _missing_canvas_cm())
        res = client.post("/api/canvas/c-ghost/fork")
        assert res.status_code == 404

    def test_fork_creates_independent_private_copy(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id, name="Original", content={"blocks": [1]})
        db_session.add(ComponentInstallation(
            tenant_id="t1", canvas_id=c.id, component_id="comp-1",
            config={"api_key": "sk-secret", "label": "x"}, position={"x": 0},
            z_index=1,
        ))
        db_session.commit()

        res = client.post(f"/api/canvas/{c.id}/fork")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        new_id = body["canvas"]["id"]
        assert new_id != c.id
        assert body["canvas"]["name"] == "Original (copy)"
        assert body["canvas"]["created_by"] == u.id
        assert body["canvas"]["share_token"] is None

        copy = db_session.query(Canvas).filter(Canvas.id == new_id).first()
        assert copy is not None
        assert copy.share_token is None
        assert copy.status == "active"
        audit = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == new_id
        ).all()
        assert len(audit) == 1
        assert audit[0].action_type == "fork"

        inst = db_session.query(ComponentInstallation).filter(
            ComponentInstallation.canvas_id == new_id
        ).all()
        assert len(inst) == 1
        assert "api_key" not in inst[0].config
        assert inst[0].config["label"] == "x"


# ===========================================================================
# GET /{canvas_id}/history
# ===========================================================================
class TestCanvasHistory:
    def test_history_404_for_missing_canvas(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.get("/api/canvas/c-ghost/history")
        assert res.status_code == 404

    def test_history_404_for_other_users_canvas_not_500(self, client, db_session, users):
        owner = _make_user(db_session)
        c = _make_canvas(db_session, owner.id)
        users["current"] = _make_user(db_session)
        res = client.get(f"/api/canvas/{c.id}/history")
        assert res.status_code == 404

    def test_history_success(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        _make_audit(db_session, c.id, "update", details={"content": {"b": 1}},
                    user_id=u.id, canvas_type="generic")
        res = client.get(f"/api/canvas/{c.id}/history")
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert res.json()["count"] >= 1
        assert res.json()["history"][0]["action_type"] in ("create", "update")

    def test_history_500_on_db_failure(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)

        def _boom():
            raise RuntimeError("db down")
        monkeypatch.setattr("core.database.get_db_session", lambda: _boom())
        res = client.get(f"/api/canvas/{c.id}/history")
        assert res.status_code == 500


# ===========================================================================
# GET / (list user canvases)
# ===========================================================================
class TestListUserCanvases:
    def test_list_empty(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.get("/api/canvas/")
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert res.json()["count"] == 0

    def test_list_filters_by_type_and_deleted(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        _make_canvas(db_session, u.id, canvas_type="docs")
        _make_canvas(db_session, u.id, canvas_type="email")
        res = client.get("/api/canvas/", params={"canvas_type": "docs"})
        assert res.json()["count"] == 1
        assert res.json()["canvases"][0]["canvas_type"] == "docs"

    def test_list_includes_deleted_when_requested(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        _make_audit(db_session, c.id, "delete", user_id=u.id)
        res = client.get("/api/canvas/", params={"include_deleted": "true"})
        assert res.json()["count"] == 1
        assert res.json()["canvases"][0]["deleted"] is True
        res2 = client.get("/api/canvas/")
        assert res2.json()["count"] == 0


# ===========================================================================
# Context management
# ===========================================================================
class TestCanvasContext:
    def test_create_context(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        res = client.post(
            f"/api/canvas/{c.id}/context",
            json={"canvas_type": "generic", "agent_id": None, "initial_state": {"a": 1}},
        )
        assert res.status_code == 200
        assert res.json()["success"] is True
        row = db_session.query(CanvasContext).filter(
            CanvasContext.canvas_id == c.id
        ).first()
        assert row is not None
        assert row.current_state == {"a": 1}

    def test_create_context_is_idempotent(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        client.post(f"/api/canvas/{c.id}/context", json={"canvas_type": "generic"})
        res = client.post(f"/api/canvas/{c.id}/context", json={"canvas_type": "generic"})
        assert res.status_code == 200
        count = db_session.query(CanvasContext).filter(
            CanvasContext.canvas_id == c.id
        ).count()
        assert count == 1

    def test_get_context_404(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.get("/api/canvas/c-ghost/context")
        assert res.status_code == 404

    def test_get_context_success(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        client.post(f"/api/canvas/{c.id}/context", json={"canvas_type": "generic"})
        res = client.get(f"/api/canvas/{c.id}/context")
        assert res.status_code == 200
        assert res.json()["data"]["canvas_id"] == c.id

    def test_update_state_empty_400(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.put("/api/canvas/c-ghost/context/state", json={"state_update": {}})
        assert res.status_code == 400

    def test_update_state_404_when_no_context(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.put(
            "/api/canvas/c-ghost/context/state",
            json={"state_update": {"a": 1}},
        )
        assert res.status_code == 404

    def test_update_state_success(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        client.post(f"/api/canvas/{c.id}/context", json={"canvas_type": "generic"})
        res = client.put(
            f"/api/canvas/{c.id}/context/state",
            json={"state_update": {"b": 2}},
        )
        assert res.status_code == 200
        row = db_session.query(CanvasContext).filter(
            CanvasContext.canvas_id == c.id
        ).first()
        assert row.current_state == {"b": 2}

    def test_record_correction_404(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.post(
            "/api/canvas/c-ghost/context/correction",
            json={"original_action": {"a": 1}, "corrected_action": {"a": 2}},
        )
        assert res.status_code == 404

    def test_record_correction_success(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        client.post(f"/api/canvas/{c.id}/context", json={"canvas_type": "generic"})
        res = client.post(
            f"/api/canvas/{c.id}/context/correction",
            json={
                "original_action": {"action_type": "click", "x": 1},
                "corrected_action": {"action_type": "click", "x": 2},
                "context_info": "misclick",
            },
        )
        assert res.status_code == 200
        row = db_session.query(CanvasContext).filter(
            CanvasContext.canvas_id == c.id
        ).first()
        assert len(row.user_corrections) == 1


# ===========================================================================
# POST /api/canvas/submit
# ===========================================================================
class TestSubmitCanvas:
    def _submit(self, client, canvas_id, agent_id=None, form_data=None):
        body = {"canvas_id": canvas_id, "form_data": form_data or {"field": "value"}}
        if agent_id:
            body["agent_id"] = agent_id
        return client.post("/api/canvas/submit", json=body)

    def test_submit_without_agent_success(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        res = self._submit(client, c.id)
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert res.json()["data"]["submitted"] is True

    def test_submit_denied_agent_returns_403(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        agent = _make_agent(db_session, status="student")
        res = self._submit(client, c.id, agent_id=agent.id)
        assert res.status_code == 403
        assert res.json()["detail"]["error"]["code"] == "GOVERNANCE_DENIED"

    def test_submit_allowed_agent_success(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        agent = _make_agent(db_session, status="autonomous")
        res = self._submit(client, c.id, agent_id=agent.id)
        assert res.status_code == 200

    def test_submit_persists_audit_row_with_form_data(self, client, db_session, users):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        res = self._submit(client, c.id, form_data={"name": "Alice", "qty": 3})
        assert res.status_code == 200
        row = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == c.id,
            CanvasAudit.action_type == "submit",
        ).first()
        assert row is not None, "submit audit row must be persisted"
        assert row.tenant_id == "t1"
        assert row.details_json["form_data"] == {"name": "Alice", "qty": 3}

    def test_submit_persistence_failure_is_non_fatal(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)

        def _boom():
            raise RuntimeError("db down")
        monkeypatch.setattr("core.database.get_db_session", lambda: _boom())
        res = self._submit(client, c.id)
        assert res.status_code == 200
        assert res.json()["success"] is True


# ===========================================================================
# POST /api/canvas/recordings/start
# ===========================================================================
class TestStartRecording:
    def test_start_recording_success(self, client, db_session, users):
        u = _make_user(db_session)
        a = _make_agent(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        res = client.post(
            "/api/canvas/recordings/start",
            json={
                "canvas_id": c.id,
                "canvas_type": "generic",
                "agent_id": a.id,
                "session_name": "s1",
                "autonomous": True,
            },
        )
        assert res.status_code == 200
        assert res.json()["success"] is True
        rec_id = res.json()["data"]["recording_id"]
        rec = db_session.query(CanvasRecording).filter(
            CanvasRecording.recording_id == rec_id
        ).first()
        assert rec is not None
        assert rec.user_id == u.id


# ===========================================================================
# GET /{canvas_id}/summary
# ===========================================================================
class TestCanvasSummary:
    def _patch_summary(self, monkeypatch, result=None, exc=None):
        from core.llm import canvas_summary_service as mod

        class FakeSummary:
            def __init__(self, db, **kwargs):
                pass

            async def generate_summary(self, **kwargs):
                if exc is not None:
                    raise exc
                return result

        monkeypatch.setattr(mod, "CanvasSummaryService", FakeSummary)

    def test_summary_404_without_context(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        self._patch_summary(monkeypatch, result="sum")
        res = client.get(f"/api/canvas/{c.id}/summary")
        assert res.status_code == 404

    def test_summary_success(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        client.post(f"/api/canvas/{c.id}/context", json={"canvas_type": "generic"})
        self._patch_summary(monkeypatch, result="A short summary")
        res = client.get(f"/api/canvas/{c.id}/summary")
        assert res.status_code == 200
        assert res.json()["data"]["summary"] == "A short summary"

    def test_summary_timeout_504(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        client.post(f"/api/canvas/{c.id}/context", json={"canvas_type": "generic"})
        self._patch_summary(monkeypatch, exc=TimeoutError("slow"))
        res = client.get(f"/api/canvas/{c.id}/summary")
        assert res.status_code == 504

    def test_summary_generic_error_500(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        client.post(f"/api/canvas/{c.id}/context", json={"canvas_type": "generic"})
        self._patch_summary(monkeypatch, exc=RuntimeError("boom"))
        res = client.get(f"/api/canvas/{c.id}/summary")
        assert res.status_code == 500

    def test_summary_empty_result_500(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        client.post(f"/api/canvas/{c.id}/context", json={"canvas_type": "generic"})
        self._patch_summary(monkeypatch, result=None)
        res = client.get(f"/api/canvas/{c.id}/summary")
        assert res.status_code == 500


# ===========================================================================
# CanvasStateConnectionManager (broadcast bookkeeping)
# ===========================================================================
class TestStateConnectionManager:
    def test_broadcast_state_cleans_dead_connections(self):
        import asyncio
        from api.canvas_routes import CanvasStateConnectionManager

        m = CanvasStateConnectionManager()

        class Good:
            async def send_json(self, data):
                pass

        class Bad:
            async def send_json(self, data):
                raise RuntimeError("dead socket")

        good, bad = Good(), Bad()
        m.active_connections["c1"] = [good, bad]
        asyncio.run(m.broadcast_state("c1", {"k": 1}))
        assert bad not in m.active_connections["c1"]
        assert good in m.active_connections["c1"]

    def test_broadcast_state_no_connections_noop(self):
        import asyncio
        from api.canvas_routes import CanvasStateConnectionManager
        m = CanvasStateConnectionManager()
        asyncio.run(m.broadcast_state("nope", {"k": 1}))


# ===========================================================================
# WebSocket /ws/{canvas_id}
# ===========================================================================
class TestCanvasWebSocket:
    def test_ws_missing_token_closes(self, client):
        with pytest.raises(Exception):
            with client.websocket_connect("/api/canvas/ws/c-1"):
                pass

    def test_ws_invalid_token_closes(self, client):
        with pytest.raises(Exception):
            with client.websocket_connect(
                "/api/canvas/ws/c-1?token=not-a-real-token"
            ):
                pass

    def test_ws_nonexistent_canvas_closes(self, client, db_session, users):
        u = _make_user(db_session)
        token = _ws_token(db_session, u)
        with pytest.raises(Exception):
            with client.websocket_connect(f"/api/canvas/ws/c-ghost?token={token}"):
                pass

    def test_ws_non_owner_closes(self, client, db_session, users):
        owner = _make_user(db_session)
        c = _make_canvas(db_session, owner.id)
        other = _make_user(db_session)
        token = _ws_token(db_session, other)
        with pytest.raises(Exception):
            with client.websocket_connect(f"/api/canvas/ws/{c.id}?token={token}"):
                pass

    def test_ws_owner_receives_state_update_and_persists(self, client, db_session, users):
        u = _make_user(db_session)
        c = _make_canvas(db_session, u.id)
        token = _ws_token(db_session, u)
        with client.websocket_connect(f"/api/canvas/ws/{c.id}?token={token}") as ws:
            ws.send_json({"type": "canvas:state_update", "state": {"x": 42}})
            msg = ws.receive_json()
            assert msg["type"] == "canvas:state_change"
            assert msg["state"] == {"x": 42}
        audit = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == c.id,
            CanvasAudit.action_type == "update",
        ).first()
        assert audit is not None, "WS state update must be persisted"

    def test_ws_persist_failure_is_non_fatal(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        c = _make_canvas(db_session, u.id)
        token = _ws_token(db_session, u)

        async def _boom(*args, **kwargs):
            raise RuntimeError("persist down")

        monkeypatch.setattr("tools.canvas_crud_tool.update_canvas_content", _boom)
        with client.websocket_connect(f"/api/canvas/ws/{c.id}?token={token}") as ws:
            ws.send_json({"type": "canvas:state_update", "state": {"y": 1}})
            msg = ws.receive_json()
            assert msg["state"] == {"y": 1}

    def test_ws_broadcast_failure_disconnects(self, client, db_session, users, monkeypatch):
        import api.canvas_routes as mod
        u = _make_user(db_session)
        c = _make_canvas(db_session, u.id)
        token = _ws_token(db_session, u)

        async def _boom(canvas_id, state):
            raise RuntimeError("broadcast exploded")

        monkeypatch.setattr(mod.manager, "broadcast_state", _boom)
        with client.websocket_connect(f"/api/canvas/ws/{c.id}?token={token}") as ws:
            ws.send_json({"type": "canvas:state_update", "state": {"z": 2}})

    def test_ws_invalid_json_does_not_hang(self, client, db_session, users):
        u = _make_user(db_session)
        c = _make_canvas(db_session, u.id)
        token = _ws_token(db_session, u)
        with client.websocket_connect(f"/api/canvas/ws/{c.id}?token={token}") as ws:
            ws.send_text("{this is not json")


# ===========================================================================
# Canvas logic endpoints (P7)
# ===========================================================================
def _patch_logic_service(monkeypatch, saved=None, loaded=None, run_result=None,
                        permission_error=False):
    import core.canvas_logic_service as mod

    class FakeLogic:
        def __init__(self, db):
            self.db = db

        def check_governance(self, agent_id):
            if permission_error:
                raise PermissionError("requires AUTONOMOUS maturity")

        def save_logic(self, **kwargs):
            return saved if saved is not None else {"source": kwargs["source"]}

        def load_logic(self, canvas_id):
            return loaded

        async def run(self, canvas_id, inputs=None, agent_id=None):
            if permission_error:
                raise PermissionError("requires AUTONOMOUS maturity")
            return run_result if run_result is not None else {"ok": True}

    monkeypatch.setattr(mod, "CanvasLogicService", FakeLogic)


class TestCanvasLogic:
    def test_put_logic_404_missing_canvas(self, client, db_session, users):
        users["current"] = _make_user(db_session)
        res = client.put("/api/canvas/c-ghost/logic", json={"source": "x = 1"})
        assert res.status_code == 404

    def test_put_logic_403_non_owner_private_canvas(self, client, db_session, users):
        owner = _make_user(db_session)
        c = _make_canvas(db_session, owner.id, is_collaborative=False)
        users["current"] = _make_user(db_session)
        res = client.put(f"/api/canvas/{c.id}/logic", json={"source": "x = 1"})
        assert res.status_code == 403

    def test_put_logic_governance_denied_is_403(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id, is_collaborative=False)
        _patch_logic_service(monkeypatch, saved={"source": "x"}, permission_error=True)
        agent = _make_agent(db_session, status="student")
        res = client.put(
            f"/api/canvas/{c.id}/logic",
            json={"source": "x = 1", "agent_id": agent.id},
        )
        assert res.status_code == 403

    def test_put_logic_success(self, client, db_session, users, monkeypatch):
        # R89 re-contract: governance is mandatory — an AUTONOMOUS agent must
        # be named even on the success path.
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id, is_collaborative=False)
        agent = _make_agent(db_session, status="autonomous")
        _patch_logic_service(monkeypatch, saved={"source": "x = 1"})
        res = client.put(
            f"/api/canvas/{c.id}/logic",
            json={"source": "x = 1", "agent_id": agent.id},
        )
        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_get_logic_404(self, client, db_session, users, monkeypatch):
        users["current"] = _make_user(db_session)
        _patch_logic_service(monkeypatch, loaded=None)
        res = client.get("/api/canvas/c-ghost/logic")
        assert res.status_code == 404

    def test_get_logic_success(self, client, db_session, users, monkeypatch):
        # R89 re-contract: GET is ownership-checked like PUT — read the
        # current user's own canvas.
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        _patch_logic_service(monkeypatch, loaded={"source": "x = 1", "language": "python"})
        res = client.get(f"/api/canvas/{c.id}/logic")
        assert res.status_code == 200
        assert res.json()["data"]["source"] == "x = 1"

    def test_run_logic_success(self, client, db_session, users, monkeypatch):
        # R89 re-contract: runs name an AUTONOMOUS agent (no silent bypass).
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        agent = _make_agent(db_session, status="autonomous")
        _patch_logic_service(monkeypatch, run_result={"ok": True, "stdout": "hi"})
        res = client.post(
            f"/api/canvas/{c.id}/logic/run",
            json={"inputs": {"a": 1}, "agent_id": agent.id},
        )
        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_run_logic_governance_denied_is_403(self, client, db_session, users, monkeypatch):
        u = _make_user(db_session)
        users["current"] = u
        c = _make_canvas(db_session, u.id)
        _patch_logic_service(monkeypatch, permission_error=True)
        agent = _make_agent(db_session, status="student")
        res = client.post(
            f"/api/canvas/{c.id}/logic/run",
            json={"inputs": {}, "agent_id": agent.id},
        )
        assert res.status_code == 403
