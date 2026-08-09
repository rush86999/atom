"""Bug-hunt 2026-08-09: mini-app record store cap enforcement.

Two documented caps were defined but never enforced in the host-mediated
record store (core/mini_app_db_service.py):

1. Rows/series cap (``DEFAULT_MAX_RECORDS_PER_SERIES`` = 10_000, overridable
   per-app via manifest ``db.max_records_per_series``) — ``append_record``
   inserted unbounded rows; the constant was dead code and the manifest value
   was validated but never consulted.
2. Per-record size cap (100 KiB) — ``update_record``/``update_many_records``
   deep-merged a validated delta onto an existing payload WITHOUT re-validating
   the merged result, so a record could silently exceed the cap.

Both caps must be enforced at the service layer (so the API routes, the
record_ops microVM envelope, and the agent tool all inherit them) and wired
through the record_ops envelope path.
"""
import json
import uuid

import pytest

from core.models import Canvas, CanvasLogic, CanvasState, MiniApp, MiniAppAsset


def _make_app(db, name="store", manifest_extra=None):
    canvas_id = f"c-{uuid.uuid4().hex[:12]}"
    app_id = f"app-{uuid.uuid4().hex[:12]}"
    manifest = {
        "declared_scopes": ["*"],
        "skills": [], "mcp_servers": [], "entrypoint": "logic",
        "dependencies": [], "base_image": "python:3.11-slim", "assets": [],
        "storage": {"enabled": True, "backend": "local", "max_bytes_per_object": 5 * 1024 * 1024},
        "initial_state": {}, "blueprint": {},
    }
    if manifest_extra:
        manifest.update(manifest_extra)
    db.add(Canvas(
        id=canvas_id, tenant_id="t1", created_by="u1", name=name,
        canvas_type="mini_app", content={"blocks": []}, style={}, status="active",
        mini_app_id=app_id,
    ))
    db.add(CanvasLogic(canvas_id=canvas_id, language="python", source="state = state", created_by="u1"))
    db.add(MiniApp(
        id=app_id, tenant_id="t1", workspace_id="w1", created_by="u1", name=name,
        manifest=manifest, blueprint_canvas_id=canvas_id, status="draft",
    ))
    db.add(CanvasState(canvas_id=canvas_id, tenant_id="t1", state={}, version=1))
    db.commit()
    return app_id, canvas_id


@pytest.fixture
def canvas_fixture(db_session):
    return _make_app(db_session)


# ---------------------------------------------------------------------------
# Service layer: rows/series cap
# ---------------------------------------------------------------------------
class TestSeriesCap:
    def test_append_beyond_cap_rejected(self, db_session):
        from core.mini_app_db_service import append_record, count_records

        canvas_id, tenant_id, app_id = "c-cap1", "t1", "a1"
        for i in range(3):
            append_record(db_session, canvas_id, tenant_id, app_id, "s", {"i": i})
        assert count_records(db_session, canvas_id, series="s") == 3

        with pytest.raises(ValueError, match="cap"):
            append_record(db_session, canvas_id, tenant_id, app_id, "s", {"i": 3}, max_records=3)
        assert count_records(db_session, canvas_id, series="s") == 3

    def test_append_cap_is_per_series(self, db_session):
        from core.mini_app_db_service import append_record, count_records

        canvas_id, tenant_id, app_id = "c-cap2", "t1", "a1"
        for i in range(3):
            append_record(db_session, canvas_id, tenant_id, app_id, "s1", {"i": i}, max_records=3)
        # A different series on the same canvas is unaffected.
        append_record(db_session, canvas_id, tenant_id, app_id, "s2", {"i": 0}, max_records=3)
        assert count_records(db_session, canvas_id, series="s2") == 1

    def test_default_cap_constant_is_10k(self):
        from core.mini_app_db_service import DEFAULT_MAX_RECORDS_PER_SERIES

        assert DEFAULT_MAX_RECORDS_PER_SERIES == 10_000


# ---------------------------------------------------------------------------
# Service layer: post-merge size cap
# ---------------------------------------------------------------------------
class TestMergeSizeCap:
    def test_update_merge_over_cap_rejected(self, db_session):
        from core.mini_app_db_service import append_record, get_record, update_record

        big = "x" * (60 * 1024)
        row = append_record(db_session, "c-cap3", "t1", "a1", "s", {"a": big})
        assert json.dumps(row["data"]) and len(json.dumps(row["data"]).encode()) <= 100 * 1024

        with pytest.raises(ValueError, match="cap"):
            update_record(db_session, "c-cap3", "s", row["id"], {"b": big}, max_bytes=100 * 1024)
        stored = get_record(db_session, "c-cap3", "s", row["id"])
        assert "b" not in stored["data"]

    def test_update_many_merge_over_cap_rejected(self, db_session):
        from core.mini_app_db_service import (
            append_record, count_records, query_records, update_many_records,
        )

        big = "y" * (60 * 1024)
        r1 = append_record(db_session, "c-cap4", "t1", "a1", "s", {"k": "a", "a": big})
        append_record(db_session, "c-cap4", "t1", "a1", "s", {"k": "b", "a": big})
        with pytest.raises(ValueError, match="cap"):
            update_many_records(
                db_session, "c-cap4", "s", {"k": "a"}, {"b": big}, max_bytes=100 * 1024
            )
        rows = query_records(db_session, "c-cap4", "s", order="asc")
        assert len(rows) == 2
        assert all("b" not in r["data"] for r in rows)

    def test_update_merge_within_cap_ok(self, db_session):
        from core.mini_app_db_service import append_record, get_record, update_record

        row = append_record(db_session, "c-cap5", "t1", "a1", "s", {"a": 1})
        updated = update_record(db_session, "c-cap5", "s", row["id"], {"b": 2}, max_bytes=1024)
        assert updated is not None and updated["data"] == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# record_ops envelope wiring (microVM path)
# ---------------------------------------------------------------------------
def _fake_runtime(monkeypatch, envelope):
    import core.mini_app_service as svc

    class FakeRuntime:
        async def execute_python(self, code, *, policy=None, inputs=None, cwd=None, image=None, callback_handler=None, **kwargs):
            res = type("R", (), {
                "success": True, "exit_code": 0, "stderr": "",
                "stdout": "__MINIAPP_STATE__:" + json.dumps(envelope),
                "metadata": {},
            })()
            return res

    monkeypatch.setattr(svc, "get_miniapp_runtime", FakeRuntime)


def _patch_db(monkeypatch, db_session):
    import contextlib
    import core.mini_app_service as svc

    @contextlib.contextmanager
    def _cm():
        yield db_session
    monkeypatch.setattr("core.database.get_db_session", _cm)


class TestEnvelopeCaps:
    @pytest.mark.asyncio
    async def test_envelope_append_beyond_manifest_cap_rejected(
        self, db_session, canvas_fixture, monkeypatch
    ):
        import core.mini_app_service as svc
        from core.models import CanvasRecord

        _, canvas_id = canvas_fixture
        app = db_session.query(MiniApp).filter(MiniApp.id == canvas_fixture[0]).first()
        new_manifest = dict(app.manifest)
        new_manifest["db"] = {"enabled": True, "max_records_per_series": 2, "max_record_bytes": 1024}
        app.manifest = new_manifest
        db_session.commit()

        _fake_runtime(monkeypatch, {
            "state": {},
            "record_ops": [
                {"op": "append", "series": "s", "data": {"i": 1}},
                {"op": "append", "series": "s", "data": {"i": 2}},
                {"op": "append", "series": "s", "data": {"i": 3}},
            ],
        })
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(canvas_id, user_id="u1", scopes=("*",))
        assert result["success"]
        assert len(result["record_results"]) == 3
        assert [r["ok"] for r in result["record_results"]] == [True, True, False]
        assert result["record_results"][2]["error"] == "series_cap"
        stored = db_session.query(CanvasRecord).filter(CanvasRecord.canvas_id == canvas_id).all()
        assert len(stored) == 2

    @pytest.mark.asyncio
    async def test_envelope_update_merge_over_cap_rejected(
        self, db_session, canvas_fixture, monkeypatch
    ):
        import core.mini_app_service as svc
        from core.models import CanvasRecord

        app_id, canvas_id = canvas_fixture
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        new_manifest = dict(app.manifest)
        new_manifest["db"] = {"enabled": True, "max_record_bytes": 1024}
        app.manifest = new_manifest
        db_session.commit()

        from core.mini_app_db_service import append_record

        big = "x" * 700
        r = append_record(db_session, canvas_id, "t1", app_id, "s", {"a": big})
        _fake_runtime(monkeypatch, {
            "state": {},
            "record_ops": [{"op": "update", "series": "s", "id": r["id"], "data": {"b": big}}],
        })
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(canvas_id, user_id="u1", scopes=("*",))
        assert result["success"]
        assert result["record_results"][0]["ok"] is False
        assert result["record_results"][0]["error"] == "size_cap"
        row = db_session.query(CanvasRecord).filter(CanvasRecord.id == r["id"]).first()
        assert "b" not in (row.data or {})


# ---------------------------------------------------------------------------
# core/user_preference_routes.py — unauthenticated IDOR (client-supplied
# user_id/workspace_id, no get_current_user dependency)
# ---------------------------------------------------------------------------
class TestUserPreferenceAuth:
    @pytest.fixture(autouse=True)
    def _ensure_pref_table(self, db_session):
        # UserPreference is declared on core.database.Base (separate from the
        # main models_registration Base), so conftest.create_all misses it.
        from sqlalchemy import inspect
        from core.user_preference_service import UserPreference

        if not inspect(db_session.bind).has_table("user_preferences"):
            UserPreference.__table__.create(db_session.bind)
        yield

    def _client(self, db_session):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from core.database import get_db
        from core.user_preference_routes import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1/preferences")

        def _get_db():
            yield db_session

        app.dependency_overrides[get_db] = _get_db
        return TestClient(app)

    def _user(self, db_session, user_id, tenant_id="t1"):
        from core.models import User

        user = User(
            id=user_id, email=f"{user_id}@example.com",
            tenant_id=tenant_id, status="active",
            hashed_password="x", role="member",
            first_name="T", last_name="User",
        )
        db_session.add(user)
        db_session.commit()
        return user

    def _token(self, user_id):
        from datetime import datetime, timedelta, timezone

        from jose import jwt
        from core.auth import ALGORITHM, SECRET_KEY

        return jwt.encode(
            {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            SECRET_KEY, algorithm=ALGORITHM,
        )

    def _seed_victim_pref(self, db_session, victim_id, workspace_id):
        from core.user_preference_service import UserPreferenceService

        UserPreferenceService(db_session).set_preference(
            victim_id, workspace_id, "secret", "victim-data"
        )

    def test_get_all_requires_auth(self, db_session):
        client = self._client(db_session)
        resp = client.get(
            "/api/v1/preferences",
            params={"user_id": "victim", "workspace_id": "w1"},
        )
        assert resp.status_code == 401

    def test_get_one_requires_auth(self, db_session):
        client = self._client(db_session)
        resp = client.get(
            "/api/v1/preferences/theme",
            params={"user_id": "victim", "workspace_id": "w1"},
        )
        assert resp.status_code == 401

    def test_post_requires_auth(self, db_session):
        client = self._client(db_session)
        resp = client.post(
            "/api/v1/preferences",
            json={"user_id": "victim", "workspace_id": "w1", "key": "theme", "value": "dark"},
        )
        assert resp.status_code == 401

    def test_authed_user_cannot_read_victims_prefs(self, db_session):
        victim = self._user(db_session, "victim-user")
        attacker = self._user(db_session, "attacker-user")
        self._seed_victim_pref(db_session, victim.id, "w-victim")
        client = self._client(db_session)

        resp = client.get(
            "/api/v1/preferences",
            params={"user_id": victim.id, "workspace_id": "w-victim"},
            headers={"Authorization": f"Bearer {self._token(attacker.id)}"},
        )
        assert resp.status_code == 200
        assert "secret" not in resp.json()
        assert resp.json() == {}

    def test_authed_user_cannot_write_victims_prefs(self, db_session):
        victim = self._user(db_session, "victim-user2")
        attacker = self._user(db_session, "attacker-user2")
        client = self._client(db_session)

        resp = client.post(
            "/api/v1/preferences",
            json={"user_id": victim.id, "workspace_id": "w-victim", "key": "theme", "value": "dark"},
            headers={"Authorization": f"Bearer {self._token(attacker.id)}"},
        )
        assert resp.status_code == 200

        # Victim's store must be untouched — attacker's write landed under
        # the attacker's own identity, never under the spoofed victim id.
        from core.user_preference_service import UserPreferenceService

        victim_val = UserPreferenceService(db_session).get_preference(
            victim.id, "w-victim", "theme"
        )
        assert victim_val is None
