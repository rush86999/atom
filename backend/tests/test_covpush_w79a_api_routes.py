# -*- coding: utf-8 -*-
"""Coverage wave 79a — 7 API route modules (each >=95% standalone).

Targets (before % measured 2026-08-14 with existing suites):
- api/device_capabilities.py  (46% — existing suite broken: 21 fixture errors)
- api/feedback_phase2.py      (100% via w89 — regression re-run standalone)
- api/memory_routes.py        (97% — missing store_memory defensive except)
- api/messaging_routes.py     (100% via w54 — regression re-run standalone)
- api/mini_app_routes.py      (98% — 10 endpoint branches)
- api/office_routes.py        (100% via w50 — regression re-run standalone)
- api/openai_gateway_routes.py(100% via w45 — regression re-run standalone)

No LLM spend, no network, no real DB: FastAPI TestClient + dependency_overrides
+ service/mock patches on REAL module names (no `backend.` prefix). 401 tests
run the real auth dependency chain (no token -> 401).
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.database import get_db


# ============================================================================
# Shared helpers
# ============================================================================

def _app(router):
    app = FastAPI()
    app.include_router(router)
    return app


def _anon_client(router):
    return TestClient(_app(router), raise_server_exceptions=False)


def _auth_client(router, user=None, db=None):
    app = _app(router)
    if user is not None:
        app.dependency_overrides[get_db] = lambda: None
    if db is not None:
        app.dependency_overrides[get_db] = lambda: db
    return app, TestClient(app, raise_server_exceptions=False)


class FakeUser:
    def __init__(self, id="user-1", tenant_id="t1", workspace_id="w1"):
        self.id = id
        self.tenant_id = tenant_id
        self.workspace_id = workspace_id
        self.email = f"{id}@test.local"
        self.status = "active"


class _FakeQuery:
    def __init__(self, fake_db, model):
        self._db = fake_db
        self._model = model

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def limit(self, n):
        return self

    def first(self):
        return self._db._first.get(self._model)

    def all(self):
        return self._db._all.get(self._model, [])


class FakeDB:
    def __init__(self, first=None, all_rows=None):
        self._first = first or {}
        self._all = all_rows or {}

    def query(self, model):
        return _FakeQuery(self, model)


def await_coroutine(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def collect_asyncgen(agen):
    async def _inner():
        out = []
        async for item in agen:
            out.append(item)
        return out

    return await_coroutine(_inner())


# ============================================================================
# api/device_capabilities.py
# ============================================================================

class TestDeviceCapabilities:
    def _client(self, db=None):
        from api.device_capabilities import router
        from core.security_dependencies import get_current_user

        app = _app(router)
        app.dependency_overrides[get_db] = lambda: (db if db is not None else FakeDB())
        app.dependency_overrides[get_current_user] = lambda: FakeUser()
        return TestClient(app, raise_server_exceptions=False)

    def _anon(self):
        from api.device_capabilities import router
        return TestClient(_app(router), raise_server_exceptions=False)

    def _patch_tool(self, name, return_value=None, side_effect=None):
        from api import device_capabilities as mod
        mock = AsyncMock(return_value=return_value)
        if side_effect is not None:
            mock.side_effect = side_effect
        return patch.object(mod, name, mock)

    def _patch_resolver(self, agent=None, exc=None):
        from api import device_capabilities as mod
        resolver_cls = MagicMock()
        if exc is not None:
            resolver_cls.return_value.resolve_agent_for_request = AsyncMock(side_effect=exc)
        else:
            resolver_cls.return_value.resolve_agent_for_request = AsyncMock(
                return_value=(SimpleNamespace(id=agent) if agent else None, {}))
        return patch.object(mod, "AgentContextResolver", resolver_cls)

    # ---------------- auth ----------------
    ENDPOINTS = [
        ("post", "/api/devices/camera/snap", {"device_node_id": "d1"}),
        ("post", "/api/devices/screen/record/start", {"device_node_id": "d1"}),
        ("post", "/api/devices/screen/record/stop", {"session_id": "s1"}),
        ("post", "/api/devices/location", {"device_node_id": "d1"}),
        ("post", "/api/devices/notification", {"device_node_id": "d1", "title": "t", "body": "b"}),
        ("post", "/api/devices/execute", {"device_node_id": "d1", "command": "ls"}),
        ("get", "/api/devices/d1", None),
        ("get", "/api/devices", None),
        ("get", "/api/devices/d1/audit", None),
        ("get", "/api/devices/sessions/active", None),
    ]

    @pytest.mark.parametrize("method,path,body", ENDPOINTS)
    def test_unauth_401(self, method, path, body):
        kwargs = {"json": body} if body is not None else {}
        r = getattr(self._anon(), method)(path, **kwargs)
        assert r.status_code == 401

    def test_missing_required_field_422(self):
        r = self._client().post("/api/devices/camera/snap", json={})
        assert r.status_code == 422

    # ---------------- resolve_agent_for_request ----------------
    def test_resolve_agent_explicit(self):
        from api import device_capabilities as mod
        assert await_coroutine(mod.resolve_agent_for_request(
            Mock(), "u1", "agent-x")) == "agent-x"

    def test_resolve_agent_via_resolver_found(self):
        from api import device_capabilities as mod
        with self._patch_resolver(agent="a-1"):
            assert await_coroutine(mod.resolve_agent_for_request(Mock(), "u1", None)) == "a-1"

    def test_resolve_agent_via_resolver_none(self):
        from api import device_capabilities as mod
        with self._patch_resolver(agent=None):
            assert await_coroutine(mod.resolve_agent_for_request(Mock(), "u1", None)) is None

    def test_resolve_agent_resolver_exception_returns_none(self):
        from api import device_capabilities as mod
        with self._patch_resolver(exc=RuntimeError("boom")):
            assert await_coroutine(mod.resolve_agent_for_request(Mock(), "u1", None)) is None

    # ---------------- camera snap ----------------
    def test_camera_snap_success_explicit_agent(self):
        with self._patch_tool("device_camera_snap", {
            "success": True, "file_path": "/tmp/a.png",
        }) as tool:
            r = self._client().post("/api/devices/camera/snap", json={
                "device_node_id": "d1", "agent_id": "ag1",
                "camera_id": "cam0", "resolution": "640x480", "save_path": "/tmp"})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["file_path"] == "/tmp/a.png"
        assert body["camera_id"] == "cam0"
        kwargs = tool.call_args.kwargs
        assert kwargs["agent_id"] == "ag1"
        assert kwargs["user_id"] == "user-1"

    def test_camera_snap_success_resolved_agent(self):
        with self._patch_tool("device_camera_snap", {
            "success": True, "file_path": "/tmp/a.png",
        }), self._patch_resolver(agent="a-1"):
            r = self._client().post("/api/devices/camera/snap", json={"device_node_id": "d1"})
        assert r.status_code == 200
        assert r.json()["message"] == "Camera snapshot captured successfully"

    def test_camera_snap_governance_blocked_403(self):
        with self._patch_tool("device_camera_snap", {
            "success": False, "governance_blocked": True, "error": "INTERN required",
        }):
            r = self._client().post("/api/devices/camera/snap", json={"device_node_id": "d1"})
        assert r.status_code == 403

    def test_camera_snap_failure_400(self):
        with self._patch_tool("device_camera_snap", {
            "success": False, "error": "lens blocked",
        }):
            r = self._client().post("/api/devices/camera/snap", json={"device_node_id": "d1"})
        assert r.status_code == 400
        assert r.json()["detail"]["error"]["code"] == "CAMERA_SNAP_FAILED"

    def test_camera_snap_permission_exception_403(self):
        with self._patch_tool("device_camera_snap", side_effect=PermissionError("permission denied")):
            r = self._client().post("/api/devices/camera/snap", json={"device_node_id": "d1"})
        assert r.status_code == 403

    def test_camera_snap_governance_exception_403(self):
        with self._patch_tool("device_camera_snap", side_effect=RuntimeError("governance check failed")):
            r = self._client().post("/api/devices/camera/snap", json={"device_node_id": "d1"})
        assert r.status_code == 403

    def test_camera_snap_generic_exception_500(self):
        with self._patch_tool("device_camera_snap", side_effect=RuntimeError("boom")):
            r = self._client().post("/api/devices/camera/snap", json={"device_node_id": "d1"})
        assert r.status_code == 500

    def test_camera_snap_httpexception_passthrough(self):
        with self._patch_tool("device_camera_snap", side_effect=HTTPException(status_code=404, detail="gone")):
            r = self._client().post("/api/devices/camera/snap", json={"device_node_id": "d1"})
        assert r.status_code == 404

    # ---------------- screen record start ----------------
    def test_screen_record_start_success(self):
        with self._patch_tool("device_screen_record_start", {
            "success": True, "session_id": "s1", "duration_seconds": 30,
            "audio_enabled": True, "resolution": "1280x720", "output_format": "webm",
        }):
            r = self._client().post("/api/devices/screen/record/start", json={
                "device_node_id": "d1", "agent_id": "ag1"})
        assert r.status_code == 200
        body = r.json()
        assert body["session_id"] == "s1"
        assert body["duration_seconds"] == 30
        assert body["audio_enabled"] is True
        assert body["output_format"] == "webm"

    def test_screen_record_start_governance_blocked_403(self):
        with self._patch_tool("device_screen_record_start", {
            "success": False, "governance_blocked": True, "error": "need SUPERVISED",
        }):
            r = self._client().post("/api/devices/screen/record/start", json={"device_node_id": "d1"})
        assert r.status_code == 403

    def test_screen_record_start_failure_400(self):
        with self._patch_tool("device_screen_record_start", {"success": False, "error": "no camera"}):
            r = self._client().post("/api/devices/screen/record/start", json={"device_node_id": "d1"})
        assert r.status_code == 400
        assert r.json()["detail"]["error"]["code"] == "SCREEN_RECORD_START_FAILED"

    def test_screen_record_start_permission_exception_403(self):
        with self._patch_tool("device_screen_record_start", side_effect=RuntimeError("permission denied")):
            r = self._client().post("/api/devices/screen/record/start", json={"device_node_id": "d1"})
        assert r.status_code == 403

    def test_screen_record_start_exception_500(self):
        with self._patch_tool("device_screen_record_start", side_effect=RuntimeError("boom")):
            r = self._client().post("/api/devices/screen/record/start", json={"device_node_id": "d1"})
        assert r.status_code == 500

    def test_screen_record_start_httpexception_passthrough(self):
        with self._patch_tool("device_screen_record_start", side_effect=HTTPException(status_code=429, detail="busy")):
            r = self._client().post("/api/devices/screen/record/start", json={"device_node_id": "d1"})
        assert r.status_code == 429

    # ---------------- screen record stop ----------------
    def test_screen_record_stop_success(self):
        with self._patch_tool("device_screen_record_stop", {
            "success": True, "session_id": "s1", "file_path": "/tmp/r.mp4",
            "duration_seconds": 12,
        }):
            r = self._client().post("/api/devices/screen/record/stop", json={"session_id": "s1"})
        assert r.status_code == 200
        assert r.json()["file_path"] == "/tmp/r.mp4"
        assert r.json()["duration_seconds"] == 12

    def test_screen_record_stop_failure_400(self):
        with self._patch_tool("device_screen_record_stop", {"success": False, "error": "no active session"}):
            r = self._client().post("/api/devices/screen/record/stop", json={"session_id": "s1"})
        assert r.status_code == 400
        assert r.json()["detail"]["error"]["code"] == "SCREEN_RECORD_STOP_FAILED"

    def test_screen_record_stop_exception_500(self):
        with self._patch_tool("device_screen_record_stop", side_effect=RuntimeError("boom")):
            r = self._client().post("/api/devices/screen/record/stop", json={"session_id": "s1"})
        assert r.status_code == 500

    def test_screen_record_stop_httpexception_passthrough(self):
        with self._patch_tool("device_screen_record_stop", side_effect=HTTPException(status_code=404, detail="no session")):
            r = self._client().post("/api/devices/screen/record/stop", json={"session_id": "s1"})
        assert r.status_code == 404

    # ---------------- location ----------------
    def test_get_location_success(self):
        with self._patch_tool("device_get_location", {
            "success": True, "latitude": 37.77, "longitude": -122.41, "accuracy": "high",
        }):
            r = self._client().post("/api/devices/location", json={"device_node_id": "d1", "agent_id": "ag1"})
        assert r.status_code == 200
        body = r.json()
        assert body["latitude"] == 37.77
        assert body["accuracy"] == "high"

    def test_get_location_governance_blocked_403(self):
        with self._patch_tool("device_get_location", {
            "success": False, "governance_blocked": True, "error": "INTERN required",
        }):
            r = self._client().post("/api/devices/location", json={"device_node_id": "d1"})
        assert r.status_code == 403

    def test_get_location_failure_400(self):
        with self._patch_tool("device_get_location", {"success": False, "error": "gps off"}):
            r = self._client().post("/api/devices/location", json={"device_node_id": "d1"})
        assert r.status_code == 400

    def test_get_location_permission_exception_403(self):
        with self._patch_tool("device_get_location", side_effect=RuntimeError("permission not granted")):
            r = self._client().post("/api/devices/location", json={"device_node_id": "d1"})
        assert r.status_code == 403

    def test_get_location_generic_exception_500(self):
        with self._patch_tool("device_get_location", side_effect=RuntimeError("boom")):
            r = self._client().post("/api/devices/location", json={"device_node_id": "d1"})
        assert r.status_code == 500

    # ---------------- notification ----------------
    def test_send_notification_success(self):
        with self._patch_tool("device_send_notification", {
            "success": True, "title": "Alert",
        }) as tool:
            r = self._client().post("/api/devices/notification", json={
                "device_node_id": "d1", "title": "Alert", "body": "hello",
                "icon": "bell", "sound": "ding", "agent_id": "ag1"})
        assert r.status_code == 200
        body = r.json()
        assert body["title"] == "Alert"
        assert body["message"] == "Notification sent successfully"
        kwargs = tool.call_args.kwargs
        assert kwargs["icon"] == "bell"
        assert kwargs["sound"] == "ding"

    def test_send_notification_governance_blocked_403(self):
        with self._patch_tool("device_send_notification", {
            "success": False, "governance_blocked": True, "error": "INTERN required",
        }):
            r = self._client().post("/api/devices/notification", json={
                "device_node_id": "d1", "title": "t", "body": "b"})
        assert r.status_code == 403

    def test_send_notification_failure_400(self):
        with self._patch_tool("device_send_notification", {"success": False, "error": "device offline"}):
            r = self._client().post("/api/devices/notification", json={
                "device_node_id": "d1", "title": "t", "body": "b"})
        assert r.status_code == 400

    def test_send_notification_permission_exception_403(self):
        with self._patch_tool("device_send_notification", side_effect=RuntimeError("governance denied")):
            r = self._client().post("/api/devices/notification", json={
                "device_node_id": "d1", "title": "t", "body": "b"})
        assert r.status_code == 403

    def test_send_notification_generic_exception_500(self):
        with self._patch_tool("device_send_notification", side_effect=RuntimeError("boom")):
            r = self._client().post("/api/devices/notification", json={
                "device_node_id": "d1", "title": "t", "body": "b"})
        assert r.status_code == 500

    def test_send_notification_httpexception_passthrough(self):
        with self._patch_tool("device_send_notification", side_effect=HTTPException(status_code=400, detail="bad")):
            r = self._client().post("/api/devices/notification", json={
                "device_node_id": "d1", "title": "t", "body": "b"})
        assert r.status_code == 400

    # ---------------- execute command ----------------
    def _agent_db(self, agent):
        from core.models import AgentRegistry
        return FakeDB(first={AgentRegistry: agent})

    def _autonomous_agent(self):
        return SimpleNamespace(status="autonomous")

    def test_execute_command_success(self):
        db = self._agent_db(self._autonomous_agent())
        with self._patch_tool("device_execute_command", {
            "success": True, "exit_code": 0, "stdout": "ok", "stderr": "",
        }) as tool:
            r = self._client(db).post("/api/devices/execute", json={
                "device_node_id": "d1", "command": "ls", "agent_id": "ag1",
                "working_dir": "/tmp", "timeout_seconds": 5, "environment": {"A": "1"}})
        assert r.status_code == 200
        body = r.json()
        assert body["exit_code"] == 0
        assert body["stdout"] == "ok"
        assert tool.call_args.kwargs["timeout_seconds"] == 5
        assert tool.call_args.kwargs["environment"] == {"A": "1"}

    def test_execute_command_no_agent_403(self):
        with self._patch_tool("device_execute_command"):
            r = self._client().post("/api/devices/execute", json={
                "device_node_id": "d1", "command": "ls"})
        assert r.status_code == 403

    def test_execute_command_non_autonomous_agent_403(self):
        db = self._agent_db(SimpleNamespace(status="intern"))
        with self._patch_tool("device_execute_command"):
            r = self._client(db).post("/api/devices/execute", json={
                "device_node_id": "d1", "command": "ls", "agent_id": "ag1"})
        assert r.status_code == 403
        assert r.json()["detail"]["error"]["code"] == "PERMISSION_DENIED"

    def test_execute_command_missing_agent_403(self):
        db = self._agent_db(None)
        with self._patch_tool("device_execute_command"):
            r = self._client(db).post("/api/devices/execute", json={
                "device_node_id": "d1", "command": "ls", "agent_id": "ag1"})
        assert r.status_code == 403

    def test_execute_command_governance_blocked_403(self):
        db = self._agent_db(self._autonomous_agent())
        with self._patch_tool("device_execute_command", {
            "success": False, "governance_blocked": True, "error": "blocked",
        }):
            r = self._client(db).post("/api/devices/execute", json={
                "device_node_id": "d1", "command": "ls", "agent_id": "ag1"})
        assert r.status_code == 403

    def test_execute_command_failure_400(self):
        db = self._agent_db(self._autonomous_agent())
        with self._patch_tool("device_execute_command", {"success": False, "error": "bad cmd"}):
            r = self._client(db).post("/api/devices/execute", json={
                "device_node_id": "d1", "command": "ls", "agent_id": "ag1"})
        assert r.status_code == 400
        assert r.json()["detail"]["error"]["code"] == "EXECUTE_COMMAND_FAILED"

    def test_execute_command_permission_exception_403(self):
        db = self._agent_db(self._autonomous_agent())
        with self._patch_tool("device_execute_command", side_effect=RuntimeError("permission revoked")):
            r = self._client(db).post("/api/devices/execute", json={
                "device_node_id": "d1", "command": "ls", "agent_id": "ag1"})
        assert r.status_code == 403

    def test_execute_command_generic_exception_500(self):
        db = self._agent_db(self._autonomous_agent())
        with self._patch_tool("device_execute_command", side_effect=RuntimeError("boom")):
            r = self._client(db).post("/api/devices/execute", json={
                "device_node_id": "d1", "command": "ls", "agent_id": "ag1"})
        assert r.status_code == 500

    # ---------------- get device info ----------------
    def _device_row(self, user_id="user-1"):
        return SimpleNamespace(user_id=user_id)

    def _device_result(self):
        return {
            "id": "d1", "device_id": "dev-1", "name": "Cam", "node_type": "camera",
            "status": "online", "platform": "ios", "capabilities": ["camera"],
            "last_seen": "2026-01-01T00:00:00Z",
        }

    def test_get_device_info_success(self):
        from core.models import DeviceNode
        db = FakeDB(first={DeviceNode: self._device_row()})
        with self._patch_tool("get_device_info", self._device_result()):
            r = self._client(db).get("/api/devices/dev-1")
        assert r.status_code == 200
        body = r.json()
        assert body["device_id"] == "dev-1"
        assert body["capabilities"] == ["camera"]

    def test_get_device_info_not_found_404(self):
        with self._patch_tool("get_device_info", None):
            r = self._client().get("/api/devices/dev-1")
        assert r.status_code == 404

    def test_get_device_info_ownership_denied_403(self):
        from core.models import DeviceNode
        db = FakeDB(first={DeviceNode: self._device_row(user_id="other-user")})
        with self._patch_tool("get_device_info", self._device_result()):
            r = self._client(db).get("/api/devices/dev-1")
        assert r.status_code == 403

    def test_get_device_info_exception_not_found_404(self):
        with self._patch_tool("get_device_info", side_effect=ValueError("device not found")):
            r = self._client().get("/api/devices/dev-1")
        assert r.status_code == 404

    def test_get_device_info_generic_exception_500(self):
        with self._patch_tool("get_device_info", side_effect=RuntimeError("boom")):
            r = self._client().get("/api/devices/dev-1")
        assert r.status_code == 500

    # ---------------- list devices ----------------
    def test_list_devices_success(self):
        with self._patch_tool("list_devices", [self._device_result()]):
            r = self._client().get("/api/devices")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_list_devices_empty(self):
        with self._patch_tool("list_devices", []):
            r = self._client().get("/api/devices")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_devices_status_filter(self):
        with self._patch_tool("list_devices", []) as tool:
            self._client().get("/api/devices", params={"status": "offline"})
        assert tool.call_args.args[1:] == ("user-1", "offline")

    def test_list_devices_exception_500(self):
        with self._patch_tool("list_devices", side_effect=RuntimeError("boom")):
            r = self._client().get("/api/devices")
        assert r.status_code == 500

    # ---------------- device audit ----------------
    def _audit_rows(self):
        return [
            SimpleNamespace(
                id="a1", action_type="snap", success=True, result_summary="ok",
                error_message=None, file_path="/tmp/a.png", duration_ms=5,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                agent_id="ag1", user_id="user-1"),
            SimpleNamespace(
                id="a2", action_type="snap", success=False, result_summary=None,
                error_message="boom", file_path=None, duration_ms=None,
                created_at=None, agent_id=None, user_id="user-1"),
        ]

    def test_get_device_audit_success(self):
        from core.models import DeviceAudit, DeviceNode
        db = FakeDB(
            first={DeviceNode: self._device_row()},
            all_rows={DeviceAudit: self._audit_rows()},
        )
        with self._patch_tool("get_device_info", self._device_result()):
            r = self._client(db).get("/api/devices/dev-1/audit")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 2
        assert rows[0]["created_at"] is not None
        assert rows[1]["created_at"] is None

    def test_get_device_audit_with_limit(self):
        from core.models import DeviceAudit, DeviceNode
        db = FakeDB(
            first={DeviceNode: self._device_row()},
            all_rows={DeviceAudit: self._audit_rows()},
        )
        r = self._client(db).get("/api/devices/dev-1/audit", params={"limit": 5})
        assert r.status_code == 200

    def test_get_device_audit_not_found_404(self):
        from core.models import DeviceNode
        db = FakeDB(first={DeviceNode: None})
        r = self._client(db).get("/api/devices/dev-1/audit")
        assert r.status_code == 404

    def test_get_device_audit_ownership_denied_403(self):
        from core.models import DeviceNode
        db = FakeDB(first={DeviceNode: self._device_row(user_id="other")})
        r = self._client(db).get("/api/devices/dev-1/audit")
        assert r.status_code == 403

    def test_get_device_audit_exception_not_found_404(self):
        db = FakeDB()
        db.query = Mock(side_effect=ValueError("device not found"))
        r = self._client(db).get("/api/devices/dev-1/audit")
        assert r.status_code == 404

    def test_get_device_audit_generic_exception_500(self):
        from core.models import DeviceNode
        db = FakeDB()
        db.query = Mock(side_effect=RuntimeError("boom"))
        r = self._client(db).get("/api/devices/dev-1/audit")
        assert r.status_code == 500

    # ---------------- active sessions ----------------
    def _sessions(self):
        return [
            SimpleNamespace(
                session_id="s1", session_type="camera", device_node_id="d1",
                status="active", configuration={"res": "1080p"},
                started_at=datetime(2026, 1, 1, tzinfo=timezone.utc), agent_id="ag1"),
            SimpleNamespace(
                session_id="s2", session_type="screen", device_node_id="d1",
                status="active", configuration=None,
                started_at=None, agent_id=None),
        ]

    def test_get_active_sessions_success(self):
        from core.models import DeviceSession
        db = FakeDB(all_rows={DeviceSession: self._sessions()})
        r = self._client(db).get("/api/devices/sessions/active")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 2
        assert rows[0]["session_type"] == "camera"
        assert rows[0]["created_at"] is not None
        assert rows[1]["created_at"] is None

    def test_get_active_sessions_empty(self):
        from core.models import DeviceSession
        db = FakeDB(all_rows={DeviceSession: []})
        r = self._client(db).get("/api/devices/sessions/active")
        assert r.status_code == 200
        assert r.json() == []

    def test_get_active_sessions_exception_500(self):
        db = FakeDB()
        db.query = Mock(side_effect=RuntimeError("boom"))
        r = self._client(db).get("/api/devices/sessions/active")
        assert r.status_code == 500


# ============================================================================
# api/feedback_phase2.py
# ============================================================================

class TestFeedbackPhase2:
    def _client(self):
        from api.feedback_phase2 import router
        from core.auth import get_current_user

        app = _app(router)
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[get_current_user] = lambda: FakeUser()
        return TestClient(app, raise_server_exceptions=False)

    def _anon(self):
        from api.feedback_phase2 import router
        return TestClient(_app(router), raise_server_exceptions=False)

    @pytest.fixture()
    def services(self):
        promo_cls = MagicMock()
        promo_cls.return_value.get_promotion_suggestions.return_value = [
            {"agent_id": "a1", "readiness_score": 0.9}]
        promo_cls.return_value.get_promotion_path.return_value = {"status": "ready"}
        promo_cls.return_value.is_agent_ready_for_promotion.return_value = {
            "ready": True, "score": 0.9, "target_status": "supervised"}
        export_cls = MagicMock()
        export_cls.return_value.export_to_json.return_value = '{"items": []}'
        export_cls.return_value.export_to_csv.return_value = "id,title\n1,foo"
        export_cls.return_value.export_summary_to_json.return_value = '{"summary": {}}'
        export_cls.return_value.get_export_filters.return_value = {
            "agent_ids": ["a1"], "types": ["correction"], "statuses": ["pending"]}
        analytics_cls = MagicMock()
        analytics_cls.return_value.analyze_feedback_performance_correlation.return_value = {
            "correlation": 0.5}
        analytics_cls.return_value.analyze_feedback_by_agent_cohort.return_value = {
            "cohorts": []}
        analytics_cls.return_value.predict_agent_performance.return_value = {
            "prediction": "stable"}
        analytics_cls.return_value.analyze_feedback_velocity.return_value = {
            "pattern": "uniform"}
        with patch("api.feedback_phase2.AgentPromotionService", promo_cls), \
             patch("api.feedback_phase2.FeedbackExportService", export_cls), \
             patch("api.feedback_phase2.AdvancedFeedbackAnalytics", analytics_cls):
            yield {"promo": promo_cls, "export": export_cls, "analytics": analytics_cls}

    ENDPOINTS = [
        ("get", "/api/feedback/phase2/promotion-suggestions"),
        ("get", "/api/feedback/phase2/promotion-path/a1"),
        ("get", "/api/feedback/phase2/promotion-check/a1"),
        ("get", "/api/feedback/phase2/export"),
        ("get", "/api/feedback/phase2/export/summary"),
        ("get", "/api/feedback/phase2/export/filters"),
        ("get", "/api/feedback/phase2/analytics/advanced/correlation/a1"),
        ("get", "/api/feedback/phase2/analytics/advanced/cohorts"),
        ("get", "/api/feedback/phase2/analytics/advanced/prediction/a1"),
        ("get", "/api/feedback/phase2/analytics/advanced/velocity/a1"),
    ]

    @pytest.mark.parametrize("method,path", ENDPOINTS)
    def test_unauth_401(self, method, path):
        assert getattr(self._anon(), method)(path).status_code == 401

    def test_promotion_suggestions_success(self, services):
        r = self._client().get("/api/feedback/phase2/promotion-suggestions")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["data"]["total_suggestions"] == 1

    def test_promotion_suggestions_limit_param(self, services):
        r = self._client().get("/api/feedback/phase2/promotion-suggestions", params={"limit": 50})
        assert r.status_code == 200
        assert services["promo"].return_value.get_promotion_suggestions.call_args.kwargs["limit"] == 50

    @pytest.mark.parametrize("limit", [0, 51])
    def test_promotion_suggestions_limit_422(self, services, limit):
        r = self._client().get("/api/feedback/phase2/promotion-suggestions", params={"limit": limit})
        assert r.status_code == 422

    def test_promotion_path_success(self, services):
        r = self._client().get("/api/feedback/phase2/promotion-path/a1")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "ready"

    def test_promotion_path_not_found_404(self, services):
        services["promo"].return_value.get_promotion_path.return_value = {"error": "unknown agent"}
        r = self._client().get("/api/feedback/phase2/promotion-path/a1")
        assert r.status_code == 404

    def test_promotion_check_success(self, services):
        r = self._client().get("/api/feedback/phase2/promotion-check/a1")
        assert r.status_code == 200
        assert r.json()["data"]["ready"] is True

    def test_promotion_check_with_target_status(self, services):
        r = self._client().get("/api/feedback/phase2/promotion-check/a1", params={"target_status": "autonomous"})
        assert r.status_code == 200
        assert services["promo"].return_value.is_agent_ready_for_promotion.call_args.kwargs["target_status"] == "autonomous"

    def test_promotion_check_not_found_404(self, services):
        services["promo"].return_value.is_agent_ready_for_promotion.return_value = {"error": "nope"}
        r = self._client().get("/api/feedback/phase2/promotion-check/a1")
        assert r.status_code == 404

    def test_export_json(self, services):
        r = self._client().get("/api/feedback/phase2/export")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/json")
        assert "attachment" in r.headers["content-disposition"]

    def test_export_csv(self, services):
        r = self._client().get("/api/feedback/phase2/export", params={"format": "csv"})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")

    def test_export_invalid_format_422(self, services):
        r = self._client().get("/api/feedback/phase2/export", params={"format": "xml"})
        assert r.status_code == 422

    @pytest.mark.parametrize("params", [
        {"days": 0}, {"days": 366}, {"limit": 0}, {"limit": 10001}])
    def test_export_query_validation_422(self, services, params):
        assert self._client().get("/api/feedback/phase2/export", params=params).status_code == 422

    def test_export_filters_passed(self, services):
        self._client().get("/api/feedback/phase2/export", params={
            "agent_id": "a1", "days": 7, "feedback_type": "correction", "status": "pending", "limit": 500})
        kwargs = services["export"].return_value.export_to_json.call_args.kwargs
        assert kwargs["agent_id"] == "a1"
        assert kwargs["days"] == 7
        assert kwargs["limit"] == 500

    def test_export_summary(self, services):
        r = self._client().get("/api/feedback/phase2/export/summary")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/json"
        assert services["export"].return_value.export_summary_to_json.call_args.kwargs["days"] == 30

    def test_export_filters(self, services):
        r = self._client().get("/api/feedback/phase2/export/filters")
        assert r.status_code == 200
        assert r.json()["data"]["agent_ids"] == ["a1"]

    def test_correlation(self, services):
        r = self._client().get("/api/feedback/phase2/analytics/advanced/correlation/a1")
        assert r.status_code == 200
        assert r.json()["data"]["correlation"] == 0.5

    def test_correlation_days_param(self, services):
        self._client().get("/api/feedback/phase2/analytics/advanced/correlation/a1", params={"days": 90})
        assert services["analytics"].return_value.analyze_feedback_performance_correlation.call_args.kwargs["days"] == 90

    def test_cohorts(self, services):
        r = self._client().get("/api/feedback/phase2/analytics/advanced/cohorts")
        assert r.status_code == 200
        assert r.json()["data"]["cohorts"] == []

    def test_prediction(self, services):
        r = self._client().get("/api/feedback/phase2/analytics/advanced/prediction/a1")
        assert r.status_code == 200
        assert r.json()["data"]["prediction"] == "stable"

    def test_velocity(self, services):
        r = self._client().get("/api/feedback/phase2/analytics/advanced/velocity/a1")
        assert r.status_code == 200
        assert r.json()["data"]["pattern"] == "uniform"


# ============================================================================
# api/memory_routes.py
# ============================================================================

class TestMemoryRoutes:
    @pytest.fixture(autouse=True)
    def _clean(self):
        import api.memory_routes as mr

        mr._memory_store.clear()
        mr._context_store.clear()
        yield
        mr._memory_store.clear()
        mr._context_store.clear()

    def _client(self):
        from api.memory_routes import router
        from core.auth import get_current_user

        app = _app(router)
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[get_current_user] = lambda: FakeUser()
        return TestClient(app, raise_server_exceptions=False)

    def _anon(self):
        from api.memory_routes import router
        return TestClient(_app(router), raise_server_exceptions=False)

    ENDPOINTS = [
        ("get", "/api/memory/stats"),
        ("get", "/api/memory/search", {"q": "x"}),
        ("get", "/api/memory/context/s1"),
        ("post", "/api/memory/context/s1", {"a": 1}),
        ("post", "/api/memory", {"key": "k", "value": "v"}),
        ("delete", "/api/memory/k"),
    ]

    @pytest.mark.parametrize("method,path,params", [
        (m, p, (d or {})) for m, p, *d in ENDPOINTS])
    def test_unauth_401(self, method, path, params):
        kwargs = {"json": params} if method == "post" else {}
        r = getattr(self._anon(), method)(path, **kwargs)
        assert r.status_code == 401

    def test_stats_from_lancedb(self):
        from core.lancedb_handler import get_lancedb_handler

        handler = MagicMock()
        handler.list_documents.return_value = [
            {"metadata": {"integration_id": "outlook"}},
            {"metadata": {}},
            {"metadata": None},
        ]
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler):
            r = self._client().get("/api/memory/stats?workspace_id=ws-1")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total_entities"] == 3
        assert data["by_integration"] == {"outlook": 1, "unknown": 2}

    def test_stats_import_error_empty(self):
        with patch("core.lancedb_handler.get_lancedb_handler", side_effect=ImportError("no lancedb")):
            r = self._client().get("/api/memory/stats")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total_entities"] == 0
        assert data["error"] == "LanceDB not available"

    def test_stats_generic_error_no_leak(self):
        with patch("core.lancedb_handler.get_lancedb_handler", side_effect=RuntimeError("db exploded /var/lib/x")):
            r = self._client().get("/api/memory/stats")
        assert r.status_code == 200
        payload = r.json()["data"]
        assert "exploded" not in str(payload)
        assert payload["error"] == "Failed to retrieve statistics"

    def test_store_and_retrieve_roundtrip(self):
        c = self._client()
        r = c.post("/api/memory", json={"key": "k1", "value": {"a": 1}, "metadata": {"m": 2}})
        assert r.status_code == 200
        body = r.json()
        assert body["key"] == "k1"
        assert body["value"] == {"a": 1}
        assert body["metadata"] == {"m": 2}

        r2 = c.get("/api/memory/k1")
        assert r2.status_code == 200
        assert r2.json()["value"] == {"a": 1}

    def test_store_without_metadata(self):
        r = self._client().post("/api/memory", json={"key": "k2", "value": "plain"})
        assert r.status_code == 200
        assert r.json()["metadata"] == {}

    def test_retrieve_missing_404(self):
        assert self._client().get("/api/memory/ghost").status_code == 404

    def test_delete_success_and_404(self):
        c = self._client()
        c.post("/api/memory", json={"key": "k3", "value": "v"})
        r = c.delete("/api/memory/k3")
        assert r.status_code == 200
        assert r.json()["message"] == "Memory key 'k3' deleted"
        assert c.delete("/api/memory/k3").status_code == 404
        assert c.get("/api/memory/k3").status_code == 404

    def test_search_hits_and_limit(self):
        c = self._client()
        c.post("/api/memory", json={"key": "a", "value": "Hello World"})
        c.post("/api/memory", json={"key": "b", "value": "Hello Again"})
        c.post("/api/memory", json={"key": "c", "value": "Goodbye"})
        r = c.get("/api/memory/search?q=hello&limit=1")
        assert r.status_code == 200
        body = r.json()
        assert body["metadata"]["count"] == 1
        assert body["data"][0]["key"] == "a"
        r2 = c.get("/api/memory/search?q=zzz")
        assert r2.json()["metadata"]["count"] == 0

    def test_context_get_empty_then_update_merge(self):
        c = self._client()
        r = c.get("/api/memory/context/sess-1")
        assert r.status_code == 200
        assert r.json()["context"] == {}

        assert c.post("/api/memory/context/sess-1", json={"topic": "math"}).status_code == 200
        c.post("/api/memory/context/sess-1", json={"difficulty": "hard"})
        ctx = c.get("/api/memory/context/sess-1").json()["context"]
        assert ctx["topic"] == "math"
        assert ctx["difficulty"] == "hard"
        assert "_updated_at" in ctx

    def test_store_memory_exception_path_500(self):
        """Defensive except in store_memory (line 204-206): force a failure
        after entry construction by breaking MemoryResponse construction.
        A real starlette Request with no agent id keeps the require_governance
        wrapper on the user-initiated path so the inner function body runs."""
        import api.memory_routes as mr
        from fastapi import HTTPException
        from starlette.requests import Request

        starlette_request = Request({
            "type": "http", "method": "POST", "path": "/api/memory",
            "headers": [], "query_string": b"", "client": None, "server": None,
            "scheme": "http",
        })

        async def _call():
            return await mr.store_memory(
                mr.MemoryStoreRequest(key="k", value="v"),
                http_request=starlette_request,
                current_user=MagicMock(id="u1"),
                db=MagicMock(),
            )

        with patch("api.memory_routes.MemoryResponse", side_effect=ValueError("boom")):
            with pytest.raises(HTTPException) as ei:
                await_coroutine(_call())
        assert ei.value.status_code == 500


# ============================================================================
# api/messaging_routes.py
# ============================================================================

class TestMessagingRoutes:
    def _client(self, user=None):
        from api.messaging_routes import router
        from core.auth import get_current_user

        app = _app(router)
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[get_current_user] = lambda: user or FakeUser()
        return TestClient(app, raise_server_exceptions=False)

    def _anon(self):
        from api.messaging_routes import router
        return TestClient(_app(router), raise_server_exceptions=False)

    def _msg_resp(self, status="PENDING", msg_id="msg-1"):
        return {
            "id": msg_id,
            "agent_id": "agent-1",
            "agent_name": "Agent",
            "agent_maturity_level": "autonomous",
            "platform": "slack",
            "recipient_id": "chan-1",
            "content": "Hello",
            "scheduled_for": None,
            "send_now": True,
            "status": status,
            "approved_by": None,
            "approved_at": None,
            "rejection_reason": None,
            "sent_at": None,
            "error_message": None,
            "platform_message_id": None,
            "created_at": "2026-08-12T00:00:00Z",
            "updated_at": None,
        }

    def _svc(self):
        s = MagicMock()
        s.create_proactive_message.return_value = self._msg_resp()
        s.get_pending_messages.return_value = []
        s.approve_message.return_value = self._msg_resp("APPROVED")
        s.reject_message.return_value = self._msg_resp("CANCELLED")
        s.cancel_message.return_value = self._msg_resp("CANCELLED")
        s.get_message_history.return_value = []
        s.get_message.return_value = None
        s.send_scheduled_messages = AsyncMock(return_value={"sent": 1, "failed": 0})
        return patch("api.messaging_routes.ProactiveMessagingService", return_value=s), s

    def _msg(self, **over):
        base = {
            "agent_id": "agent-1",
            "platform": "slack",
            "recipient_id": "chan-1",
            "content": "Hello",
            "send_now": True,
        }
        base.update(over)
        return base

    ENDPOINTS = [
        ("post", "/api/v1/messaging/proactive/send", True),
        ("post", "/api/v1/messaging/proactive/schedule", True),
        ("get", "/api/v1/messaging/proactive/queue", False),
        ("post", "/api/v1/messaging/proactive/approve/m1", True),
        ("post", "/api/v1/messaging/proactive/reject/m1", True),
        ("delete", "/api/v1/messaging/proactive/cancel/m1", False),
        ("get", "/api/v1/messaging/proactive/history", False),
        ("get", "/api/v1/messaging/proactive/m1", False),
        ("post", "/api/v1/messaging/proactive/_send_scheduled", False),
    ]

    @pytest.mark.parametrize("method,path,body", ENDPOINTS)
    def test_unauth_401(self, method, path, body):
        kwargs = {"json": self._msg()} if body else {}
        r = getattr(self._anon(), method)(path, **kwargs)
        assert r.status_code == 401

    def test_send_success(self):
        p, svc = self._svc()
        with p:
            r = self._client().post("/api/v1/messaging/proactive/send", json=self._msg())
        assert r.status_code == 200
        assert r.json()["id"] == "msg-1"
        kwargs = svc.create_proactive_message.call_args.kwargs
        assert kwargs["agent_id"] == "agent-1"
        assert kwargs["send_now"] is True
        assert kwargs["governance_metadata"] is None

    def test_send_with_optional_fields(self):
        p, svc = self._svc()
        with p:
            self._client().post("/api/v1/messaging/proactive/send", json=self._msg(
                scheduled_for="2026-09-01T00:00:00Z", governance_metadata={"a": 1}))
        kwargs = svc.create_proactive_message.call_args.kwargs
        assert kwargs["scheduled_for"] is not None
        assert kwargs["governance_metadata"] == {"a": 1}

    def test_send_missing_required_422(self):
        p, _ = self._svc()
        with p:
            r = self._client().post("/api/v1/messaging/proactive/send", json={"agent_id": "a1"})
        assert r.status_code == 422

    def test_send_service_403_propagates(self):
        p, svc = self._svc()
        svc.create_proactive_message.side_effect = HTTPException(status_code=403, detail="STUDENT blocked")
        with p:
            r = self._client().post("/api/v1/messaging/proactive/send", json=self._msg())
        assert r.status_code == 403

    def test_schedule_success_forces_send_now_false(self):
        p, svc = self._svc()
        with p:
            r = self._client().post("/api/v1/messaging/proactive/schedule", json=self._msg(
                scheduled_for="2026-09-01T00:00:00Z", send_now=True))
        assert r.status_code == 200
        assert svc.create_proactive_message.call_args.kwargs["send_now"] is False

    def test_schedule_missing_scheduled_for_422(self):
        p, _ = self._svc()
        with p:
            r = self._client().post("/api/v1/messaging/proactive/schedule", json=self._msg())
        assert r.status_code == 422

    def test_queue_defaults(self):
        p, svc = self._svc()
        with p:
            r = self._client().get("/api/v1/messaging/proactive/queue")
        assert r.status_code == 200
        assert r.json() == []
        kwargs = svc.get_pending_messages.call_args.kwargs
        assert kwargs["agent_id"] is None
        assert kwargs["limit"] == 100

    def test_queue_filters(self):
        p, svc = self._svc()
        with p:
            self._client().get("/api/v1/messaging/proactive/queue", params={
                "agent_id": "a1", "platform": "slack", "limit": 5})
        kwargs = svc.get_pending_messages.call_args.kwargs
        assert kwargs == {"agent_id": "a1", "platform": "slack", "limit": 5}

    def test_approve_token_attribution(self):
        user = FakeUser(id="approver-1")
        p, svc = self._svc()
        with p:
            r = self._client(user).post(
                "/api/v1/messaging/proactive/approve/m1",
                json={"approver_user_id": "attacker-id"})
        assert r.status_code == 200
        assert svc.approve_message.call_args.kwargs["approver_user_id"] == "approver-1"

    def test_reject_token_attribution(self):
        user = FakeUser(id="rejecter-1")
        p, svc = self._svc()
        with p:
            r = self._client(user).post(
                "/api/v1/messaging/proactive/reject/m1",
                json={"rejecter_user_id": "attacker-id", "rejection_reason": "spam"})
        assert r.status_code == 200
        assert svc.reject_message.call_args.kwargs["rejecter_user_id"] == "rejecter-1"
        assert svc.reject_message.call_args.kwargs["rejection_reason"] == "spam"

    def test_reject_missing_reason_422(self):
        p, _ = self._svc()
        with p:
            r = self._client().post("/api/v1/messaging/proactive/reject/m1", json={})
        assert r.status_code == 422

    def test_cancel(self):
        p, svc = self._svc()
        with p:
            r = self._client().delete("/api/v1/messaging/proactive/cancel/m1")
        assert r.status_code == 200
        assert r.json()["status"] == "CANCELLED"
        assert svc.cancel_message.call_args.kwargs["message_id"] == "m1"

    def test_history_defaults_and_filters(self):
        p, svc = self._svc()
        with p:
            r = self._client().get("/api/v1/messaging/proactive/history")
            assert r.status_code == 200
            assert svc.get_message_history.call_args.kwargs["limit"] == 100
            self._client().get("/api/v1/messaging/proactive/history", params={
                "agent_id": "a1", "recipient_id": "r1", "platform": "discord",
                "message_status": "SENT", "limit": 3})
        kwargs = svc.get_message_history.call_args.kwargs
        assert kwargs["status"] == "SENT"
        assert kwargs["agent_id"] == "a1"
        assert kwargs["recipient_id"] == "r1"
        assert kwargs["platform"] == "discord"
        assert kwargs["limit"] == 3

    def test_get_message_found(self):
        p, svc = self._svc()
        svc.get_message.return_value = self._msg_resp()
        with p:
            r = self._client().get("/api/v1/messaging/proactive/m1")
        assert r.status_code == 200
        assert r.json()["id"] == "msg-1"

    def test_get_message_404(self):
        p, _ = self._svc()
        with p:
            r = self._client().get("/api/v1/messaging/proactive/m1")
        assert r.status_code == 404

    def test_send_scheduled_success(self, monkeypatch):
        monkeypatch.setenv("ATOM_SCHEDULER_SECRET", "s3cr3t")
        p, svc = self._svc()
        with p:
            r = self._client().post(
                "/api/v1/messaging/proactive/_send_scheduled",
                headers={"X-Scheduler-Secret": "s3cr3t"})
        assert r.status_code == 200
        assert r.json() == {"sent": 1, "failed": 0}

    def test_send_scheduled_wrong_secret_401(self, monkeypatch):
        monkeypatch.setenv("ATOM_SCHEDULER_SECRET", "s3cr3t")
        p, _ = self._svc()
        with p:
            r = self._client().post(
                "/api/v1/messaging/proactive/_send_scheduled",
                headers={"X-Scheduler-Secret": "wrong"})
        assert r.status_code == 401

    def test_send_scheduled_unset_secret_401(self, monkeypatch):
        monkeypatch.delenv("ATOM_SCHEDULER_SECRET", raising=False)
        p, _ = self._svc()
        with p:
            r = self._client().post("/api/v1/messaging/proactive/_send_scheduled")
        assert r.status_code == 401


# ============================================================================
# api/mini_app_routes.py
# ============================================================================

class TestMiniAppRoutes:
    @pytest.fixture()
    def db_session(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from core.database import Base
        from core.models import (
            Canvas, CanvasLogic, CanvasRecord, CanvasState, MiniApp,
            MiniAppAsset, MiniAppInstallation,
        )

        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine, tables=[
            MiniApp.__table__, Canvas.__table__, CanvasLogic.__table__,
            MiniAppAsset.__table__, CanvasState.__table__, CanvasRecord.__table__,
            MiniAppInstallation.__table__,
        ])
        session = sessionmaker(bind=engine)()
        yield session
        session.close()

    @pytest.fixture()
    def client(self, db_session):
        from api.mini_app_routes import router
        from core.auth import get_current_user

        app = _app(router)

        def override_db():
            yield db_session

        def override_user():
            return FakeUser(id="user-1")

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user
        return TestClient(app, raise_server_exceptions=False)

    def _anon(self):
        from api.mini_app_routes import router
        return TestClient(_app(router), raise_server_exceptions=False)

    @staticmethod
    def _valid_manifest(**over):
        m = {
            "name": "my-app", "version": "1.0.0", "declared_scopes": ["*"],
            "dependencies": [], "base_image": "python:3.11-slim",
            "initial_state": {}, "blueprint": {},
        }
        m.update(over)
        return m

    def _create(self, client, manifest=None, name="my-app"):
        return client.post("/api/mini-apps", json={
            "name": name, "description": "d", "version": "1.0.0",
            "manifest": manifest or self._valid_manifest(),
        })

    @staticmethod
    def _make_app(db, app_id="app-1", owner="user-1", status="draft",
                  manifest=None, blueprint_canvas_id="src-1",
                  runtime_image="img", is_public=False, is_approved=False,
                  share_token=None, runtime_version=1):
        from core.models import MiniApp
        app = MiniApp(
            id=app_id, tenant_id="t1", workspace_id="w1", created_by=owner,
            name="my-app", description="desc", version="1.0.0", status=status,
            manifest=manifest or TestMiniAppRoutes._valid_manifest(),
            blueprint_canvas_id=blueprint_canvas_id,
            runtime_image=runtime_image, runtime_version=runtime_version,
            is_public=is_public, is_approved=is_approved, share_token=share_token,
        )
        db.add(app)
        db.commit()
        db.refresh(app)
        return app

    @staticmethod
    def _make_canvas(db, canvas_id="canvas-1", owner="user-1", mini_app_id="app-1"):
        from core.models import Canvas
        canvas = Canvas(
            id=canvas_id, tenant_id="t1", created_by=owner,
            name=f"instance {canvas_id}", canvas_type="mini_app",
            content={}, style={}, status="active", mini_app_id=mini_app_id,
        )
        db.add(canvas)
        db.commit()
        db.refresh(canvas)
        return canvas

    class FakeStorage:
        def __init__(self):
            self.objects = {}

        def store(self, key, data, content_type=None):
            self.objects[key] = data
            return f"uri://{key}"

        def retrieve(self, key):
            return self.objects.get(key)

        def delete(self, key):
            return self.objects.pop(key, None) is not None

    # ---------------- auth ----------------
    ANON_ENDPOINTS = [
        ("post", "/api/mini-apps", True),
        ("post", "/api/mini-apps/scaffold", True),
        ("post", "/api/mini-apps/app-1/logic", True),
        ("post", "/api/mini-apps/app-1/dev-run", True),
        ("get", "/api/mini-apps", False),
        ("get", "/api/mini-apps/app-1", False),
        ("put", "/api/mini-apps/app-1", True),
        ("post", "/api/mini-apps/app-1/publish", False),
        ("post", "/api/mini-apps/app-1/share", False),
        ("post", "/api/mini-apps/app-1/approve", False),
        ("post", "/api/mini-apps/by-token/tok1/install", False),
        ("get", "/api/mini-apps/instances/c1/update-check", False),
        ("post", "/api/mini-apps/app-1/install", False),
        ("post", "/api/mini-apps/instances/c1/assets", False),
        ("get", "/api/mini-apps/instances/c1/assets", False),
        ("get", "/api/mini-apps/instances/c1/assets/k1", False),
        ("delete", "/api/mini-apps/instances/c1/assets/k1", False),
        ("get", "/api/mini-apps/instances/c1/records/series", False),
        ("get", "/api/mini-apps/instances/c1/records", False),
        ("post", "/api/mini-apps/instances/c1/records", True),
        ("post", "/api/mini-apps/instances/c1/records/query", True),
        ("post", "/api/mini-apps/instances/c1/records/count", True),
        ("get", "/api/mini-apps/instances/c1/records/r1", False),
        ("put", "/api/mini-apps/instances/c1/records/r1", True),
        ("delete", "/api/mini-apps/instances/c1/records/r1", False),
        ("delete", "/api/mini-apps/instances/c1/records", False),
    ]

    @pytest.mark.parametrize("method,path,body", ANON_ENDPOINTS)
    def test_unauth_401(self, method, path, body):
        kwargs = {"json": {"a": 1}} if body else {}
        r = getattr(self._anon(), method)(path, **kwargs)
        assert r.status_code == 401

    # ---------------- create ----------------
    def test_create_success(self, client):
        r = self._create(client)
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["app"]["status"] == "draft"

    def test_create_invalid_manifest_400(self, client):
        r = self._create(client, manifest={"name": "n", "declared_scopes": ["bogus_scope"]})
        assert r.status_code == 400

    def test_create_with_source_canvas(self, client, db_session):
        r = client.post("/api/mini-apps", json={
            "name": "n", "version": "1.1.0", "source_canvas_id": "src-9",
            "manifest": self._valid_manifest()})
        assert r.status_code == 200
        assert r.json()["app"]["name"] == "n"

    # ---------------- scaffold ----------------
    def test_scaffold_success(self, client):
        app = SimpleNamespace(
            id="app-s", name="scaff", status="draft",
            manifest=self._valid_manifest(blueprint={"logic_source": "print(1)"}))
        with patch("core.mini_app_service.scaffold", return_value=(app, "canvas-s")) as sc:
            r = client.post("/api/mini-apps/scaffold", json={
                "name": "scaff", "spec": {"ui": "chart"}, "declared_scopes": ["canvas.read"],
                "dependencies": ["numpy"], "base_image": "python:3.11-slim"})
        assert r.status_code == 200
        body = r.json()
        assert body["canvas_id"] == "canvas-s"
        assert body["logic_source"] == "print(1)"
        assert body["manifest"]["name"] == "my-app"
        assert sc.call_args.kwargs["viewer"].id == "user-1"

    def test_scaffold_no_logic_source(self, client):
        app = SimpleNamespace(id="app-s", name="scaff", status="draft", manifest={})
        with patch("core.mini_app_service.scaffold", return_value=(app, "canvas-s")):
            r = client.post("/api/mini-apps/scaffold", json={"name": "scaff"})
        assert r.status_code == 200
        assert r.json()["logic_source"] == ""

    # ---------------- save logic ----------------
    def test_save_logic_success(self, client, db_session):
        self._make_app(db_session)
        with patch("core.mini_app_service.syntax_check") as sc, \
             patch("core.canvas_logic_service.CanvasLogicService") as cls:
            cls.return_value.save_logic.return_value = None
            r = client.post("/api/mini-apps/app-1/logic", json={"source": "print(1)"})
        assert r.status_code == 200
        assert r.json()["success"] is True
        sc.assert_called_once_with("print(1)")
        cls.return_value.save_logic.assert_called_once()

    def test_save_logic_404(self, client):
        r = client.post("/api/mini-apps/app-1/logic", json={"source": "print(1)"})
        assert r.status_code == 404

    def test_save_logic_non_owner_403(self, client, db_session):
        self._make_app(db_session, owner="other-user")
        r = client.post("/api/mini-apps/app-1/logic", json={"source": "print(1)"})
        assert r.status_code == 403

    def test_save_logic_no_blueprint_400(self, client, db_session):
        self._make_app(db_session, blueprint_canvas_id=None)
        r = client.post("/api/mini-apps/app-1/logic", json={"source": "print(1)"})
        assert r.status_code == 400

    def test_save_logic_syntax_error_400(self, client, db_session):
        self._make_app(db_session)
        with patch("core.mini_app_service.syntax_check", side_effect=SyntaxError("bad token")):
            r = client.post("/api/mini-apps/app-1/logic", json={"source": "print("})
        assert r.status_code == 400
        assert "SyntaxError" in r.json()["detail"]

    # ---------------- dev run ----------------
    def test_dev_run_success(self, client, db_session):
        self._make_app(db_session)
        with patch("core.mini_app_service.prepare_runtime") as prep, \
             patch("core.mini_app_service.run_stateful", AsyncMock(return_value={
                 "success": True, "state": {"n": 1}, "proposed_ops": []})):
            r = client.post("/api/mini-apps/app-1/dev-run", json={"inputs": {"x": 1}})
        assert r.status_code == 200
        assert r.json()["state"] == {"n": 1}
        prep.assert_called_once()

    def test_dev_run_no_blueprint_400(self, client, db_session):
        self._make_app(db_session, blueprint_canvas_id=None)
        r = client.post("/api/mini-apps/app-1/dev-run", json={"inputs": {}})
        assert r.status_code == 400
        assert r.json()["detail"] == "App has no blueprint canvas"

    def test_dev_run_failure_500(self, client, db_session):
        self._make_app(db_session)
        with patch("core.mini_app_service.prepare_runtime"), \
             patch("core.mini_app_service.run_stateful", AsyncMock(
                 return_value={"success": False, "error": "runtime crashed"})):
            r = client.post("/api/mini-apps/app-1/dev-run", json={"inputs": {}})
        assert r.status_code == 500

    def test_dev_run_404(self, client):
        r = client.post("/api/mini-apps/ghost/dev-run", json={"inputs": {}})
        assert r.status_code == 404

    # ---------------- list / get ----------------
    def test_list_empty(self, client):
        r = client.get("/api/mini-apps")
        assert r.status_code == 200
        assert r.json() == {"success": True, "apps": []}

    def test_list_owned_and_public(self, client, db_session):
        self._make_app(db_session, app_id="mine")
        self._make_app(db_session, app_id="theirs", owner="other", is_public=True,
                       manifest=self._valid_manifest(integrations=["slack"],
                                                     declared_scopes=["*"]))
        r = client.get("/api/mini-apps")
        apps = {a["id"]: a for a in r.json()["apps"]}
        assert set(apps) == {"mine", "theirs"}
        assert apps["theirs"]["integrations_count"] == 1
        assert apps["mine"]["created_by"] == "user-1"

    def test_list_search_q(self, client, db_session):
        self._make_app(db_session, app_id="alpha")
        from core.models import MiniApp
        app = db_session.query(MiniApp).filter(MiniApp.id == "alpha").first()
        app.name = "AlphaChart"
        app.description = "charts only"
        db_session.commit()
        r = client.get("/api/mini-apps", params={"q": "chart"})
        assert r.status_code == 200
        assert [a["id"] for a in r.json()["apps"]] == ["alpha"]

    def test_list_integrations_mcp_fallback(self, client, db_session):
        self._make_app(db_session, app_id="mcp1",
                       manifest=self._valid_manifest(mcp_servers=["svc"]))
        r = client.get("/api/mini-apps")
        assert r.json()["apps"][0]["integrations_count"] == 1

    def test_list_created_at_none(self, client, db_session):
        self._make_app(db_session, app_id="no-ts")
        from core.models import MiniApp
        app = db_session.query(MiniApp).filter(MiniApp.id == "no-ts").first()
        app.created_at = None
        db_session.commit()
        r = client.get("/api/mini-apps")
        assert r.json()["apps"][0]["created_at"] is None

    def test_get_app_success(self, client, db_session):
        self._make_app(db_session)
        r = client.get("/api/mini-apps/app-1")
        assert r.status_code == 200
        body = r.json()["app"]
        assert body["id"] == "app-1"
        assert body["runtime_image"] == "img"
        assert body["blueprint_canvas_id"] == "src-1"

    def test_get_app_manifest_credential_stripped(self, client, db_session):
        manifest = self._valid_manifest()
        manifest["api_key"] = "sk-super-secret"
        self._make_app(db_session, manifest=manifest)
        r = client.get("/api/mini-apps/app-1")
        assert "sk-super-secret" not in r.text

    def test_get_app_404(self, client):
        assert client.get("/api/mini-apps/ghost").status_code == 404

    # ---------------- update ----------------
    def test_update_name_version(self, client, db_session):
        self._make_app(db_session)
        r = client.put("/api/mini-apps/app-1", json={"name": "renamed", "version": "2.0.0"})
        assert r.status_code == 200
        assert r.json()["app_id"] == "app-1"
        body = client.get("/api/mini-apps/app-1").json()["app"]
        assert body["name"] == "renamed"
        assert body["version"] == "2.0.0"

    def test_update_description_only(self, client, db_session):
        self._make_app(db_session)
        r = client.put("/api/mini-apps/app-1", json={"description": "new desc"})
        assert r.status_code == 200
        assert client.get("/api/mini-apps/app-1").json()["app"]["description"] == "new desc"

    def test_update_manifest_same_deps_keeps_image(self, client, db_session):
        self._make_app(db_session)
        m = self._valid_manifest(dependencies=[])
        client.put("/api/mini-apps/app-1", json={"manifest": m})
        assert client.get("/api/mini-apps/app-1").json()["app"]["runtime_image"] == "img"

    def test_update_manifest_deps_change_clears_image(self, client, db_session):
        self._make_app(db_session)
        m = self._valid_manifest(dependencies=["pandas"])
        client.put("/api/mini-apps/app-1", json={"manifest": m})
        assert client.get("/api/mini-apps/app-1").json()["app"]["runtime_image"] is None

    def test_update_invalid_manifest_400(self, client, db_session):
        self._make_app(db_session)
        r = client.put("/api/mini-apps/app-1", json={"manifest": {"declared_scopes": ["nope"]}})
        assert r.status_code == 400

    def test_update_non_owner_403(self, client, db_session):
        self._make_app(db_session, owner="other")
        assert client.put("/api/mini-apps/app-1", json={"name": "x"}).status_code == 403

    def test_update_404(self, client):
        assert client.put("/api/mini-apps/ghost", json={"name": "x"}).status_code == 404

    # ---------------- publish ----------------
    def test_publish_success_private(self, client, db_session):
        self._make_app(db_session)
        with patch("core.mini_app_service.publish", return_value={"published": True}) as pub:
            r = client.post("/api/mini-apps/app-1/publish")
        assert r.status_code == 200
        assert r.json() == {"published": True}
        assert pub.call_args.kwargs["public"] is False

    def test_publish_success_public(self, client, db_session):
        self._make_app(db_session)
        with patch("core.mini_app_service.publish", return_value={"published": True}):
            r = client.post("/api/mini-apps/app-1/publish?public=true")
        assert r.status_code == 200

    def test_publish_runtime_error_500(self, client, db_session):
        self._make_app(db_session)
        with patch("core.mini_app_service.publish", side_effect=RuntimeError("rootfs missing")):
            r = client.post("/api/mini-apps/app-1/publish")
        assert r.status_code == 500

    def test_publish_value_error_400(self, client, db_session):
        self._make_app(db_session)
        with patch("core.mini_app_service.publish", side_effect=ValueError("bad manifest")):
            r = client.post("/api/mini-apps/app-1/publish")
        assert r.status_code == 400

    def test_publish_non_owner_403(self, client, db_session):
        self._make_app(db_session, owner="other")
        assert client.post("/api/mini-apps/app-1/publish").status_code == 403

    # ---------------- share ----------------
    def test_share_makes_public_generates_token(self, client, db_session):
        self._make_app(db_session, share_token=None, is_public=False)
        r = client.post("/api/mini-apps/app-1/share")
        assert r.status_code == 200
        body = r.json()
        assert body["is_public"] is True
        assert body["share_token"]

    def test_share_keeps_existing_token(self, client, db_session):
        self._make_app(db_session, share_token="tok-existing")
        r = client.post("/api/mini-apps/app-1/share")
        assert r.json()["share_token"] == "tok-existing"

    def test_unshare_clears_token(self, client, db_session):
        self._make_app(db_session, share_token="tok-1")
        r = client.post("/api/mini-apps/app-1/share?public=false")
        assert r.status_code == 200
        assert r.json()["is_public"] is False
        assert r.json()["share_token"] is None

    def test_share_non_owner_403(self, client, db_session):
        self._make_app(db_session, owner="other")
        assert client.post("/api/mini-apps/app-1/share").status_code == 403

    # ---------------- approve ----------------
    def test_approve_success(self, client, db_session):
        self._make_app(db_session)
        admin = FakeUser(id="admin-1")
        from api.mini_app_routes import router
        from core.auth import get_current_user
        app = _app(router)

        def override_db():
            yield db_session

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id="admin-1", is_admin=True, is_staff=False)
        r = TestClient(app, raise_server_exceptions=False).post("/api/mini-apps/app-1/approve")
        assert r.status_code == 200
        assert r.json()["is_approved"] is True

    def test_approve_staff_success(self, client, db_session):
        self._make_app(db_session)
        from api.mini_app_routes import router
        from core.auth import get_current_user
        app = _app(router)

        def override_db():
            yield db_session

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id="staff-1", is_admin=False, is_staff=True)
        assert TestClient(app, raise_server_exceptions=False).post(
            "/api/mini-apps/app-1/approve").status_code == 200

    def test_approve_non_admin_403(self, client, db_session):
        self._make_app(db_session)
        assert client.post("/api/mini-apps/app-1/approve").status_code == 403

    # ---------------- install by token ----------------
    def test_install_by_token_success(self, client, db_session):
        self._make_app(db_session, status="published", is_public=True,
                       is_approved=True, share_token="tok-1")
        with patch("core.mini_app_service.install", return_value="canvas-new") as inst:
            r = client.post("/api/mini-apps/by-token/tok-1/install")
        assert r.status_code == 200
        assert r.json()["canvas_id"] == "canvas-new"
        assert inst.call_args[0][1].id == "user-1"

    def test_install_by_token_not_found_404(self, client):
        r = client.post("/api/mini-apps/by-token/ghost/install")
        assert r.status_code == 404

    def test_install_by_token_not_public_404(self, client, db_session):
        self._make_app(db_session, share_token="tok-1", is_public=False)
        assert client.post("/api/mini-apps/by-token/tok-1/install").status_code == 404

    def test_install_by_token_pending_review_403(self, client, db_session):
        self._make_app(db_session, share_token="tok-1", is_public=True, is_approved=False)
        assert client.post("/api/mini-apps/by-token/tok-1/install").status_code == 403

    def test_install_by_token_value_error_400(self, client, db_session):
        self._make_app(db_session, share_token="tok-1", is_public=True,
                       is_approved=True, status="draft")
        with patch("core.mini_app_service.install", side_effect=ValueError("not published")):
            r = client.post("/api/mini-apps/by-token/tok-1/install")
        assert r.status_code == 400

    # ---------------- update check ----------------
    def test_update_check_no_installation(self, client, db_session):
        self._make_app(db_session, status="published")
        self._make_canvas(db_session)
        r = client.get("/api/mini-apps/instances/canvas-1/update-check")
        assert r.status_code == 200
        assert r.json() == {"success": True, "update_available": False,
                            "reason": "no_installation_record"}

    def test_update_check_app_deleted(self, client, db_session):
        from core.models import MiniAppInstallation
        self._make_app(db_session, status="published")
        self._make_canvas(db_session)
        db_session.add(MiniAppInstallation(canvas_id="canvas-1", app_id="ghost",
                                           tenant_id="t1", installed_version="1.0.0"))
        db_session.commit()
        r = client.get("/api/mini-apps/instances/canvas-1/update-check")
        assert r.status_code == 200
        assert r.json()["reason"] == "app_deleted"

    def test_update_check_update_available(self, client, db_session):
        from core.models import MiniAppInstallation
        self._make_app(db_session, status="published", runtime_version=2)
        self._make_canvas(db_session)
        db_session.add(MiniAppInstallation(canvas_id="canvas-1", app_id="app-1",
                                           tenant_id="t1", installed_version="1.0.0",
                                           installed_runtime_version=1))
        db_session.commit()
        r = client.get("/api/mini-apps/instances/canvas-1/update-check")
        body = r.json()
        assert body["update_available"] is True
        assert body["latest_version"] == "1.0.0"

    def test_update_check_no_update(self, client, db_session):
        from core.models import MiniAppInstallation
        self._make_app(db_session, status="published", runtime_version=1)
        self._make_canvas(db_session)
        db_session.add(MiniAppInstallation(canvas_id="canvas-1", app_id="app-1",
                                           tenant_id="t1", installed_version="1.0.0",
                                           installed_runtime_version=1))
        db_session.commit()
        r = client.get("/api/mini-apps/instances/canvas-1/update-check")
        assert r.json()["update_available"] is False

    def test_update_check_instance_403_for_stranger(self, client, db_session):
        self._make_app(db_session, status="published")
        self._make_canvas(db_session, owner="other-user")
        r = client.get("/api/mini-apps/instances/canvas-1/update-check")
        assert r.status_code == 403

    def test_update_check_instance_404(self, client):
        r = client.get("/api/mini-apps/instances/ghost/update-check")
        assert r.status_code == 404

    # ---------------- install ----------------
    def test_install_owner_success(self, client, db_session):
        self._make_app(db_session, status="draft")
        with patch("core.mini_app_service.install", return_value="canvas-new"):
            r = client.post("/api/mini-apps/app-1/install")
        assert r.status_code == 200
        assert r.json()["canvas_id"] == "canvas-new"

    def test_install_public_approved_success(self, client, db_session):
        self._make_app(db_session, owner="other", status="published",
                       is_public=True, is_approved=True)
        with patch("core.mini_app_service.install", return_value="canvas-new"):
            r = client.post("/api/mini-apps/app-1/install")
        assert r.status_code == 200

    def test_install_pending_review_403(self, client, db_session):
        self._make_app(db_session, owner="other", is_public=True, is_approved=False)
        r = client.post("/api/mini-apps/app-1/install")
        assert r.status_code == 403
        assert r.json()["detail"] == "App is pending review"

    def test_install_private_other_user_403(self, client, db_session):
        self._make_app(db_session, owner="other", is_public=False)
        r = client.post("/api/mini-apps/app-1/install")
        assert r.status_code == 403

    def test_install_value_error_400(self, client, db_session):
        self._make_app(db_session, status="draft")
        with patch("core.mini_app_service.install", side_effect=ValueError("not published")):
            r = client.post("/api/mini-apps/app-1/install")
        assert r.status_code == 400

    # ---------------- assets ----------------
    def _asset_client(self, db_session, user_id="user-1"):
        from api.mini_app_routes import router
        from core.auth import get_current_user
        app = _app(router)

        def override_db():
            yield db_session

        def override_user():
            return FakeUser(id=user_id)

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user
        return TestClient(app, raise_server_exceptions=False)

    def test_upload_asset_new(self, client, db_session):
        self._make_app(db_session, status="published")
        self._make_canvas(db_session)
        storage = self.FakeStorage()
        with patch("api.mini_app_routes.get_mini_app_storage", return_value=storage):
            r = client.post("/api/mini-apps/instances/canvas-1/assets",
                            data={"key": "logo.png"},
                            files={"file": ("logo.png", b"PNG", "image/png")})
        assert r.status_code == 200
        assert r.json()["uri"] == "uri://logo.png"
        from core.models import MiniAppAsset
        assert db_session.query(MiniAppAsset).count() == 1

    def test_upload_asset_overwrites(self, client, db_session):
        self._make_app(db_session, status="published")
        self._make_canvas(db_session)
        storage = self.FakeStorage()
        with patch("api.mini_app_routes.get_mini_app_storage", return_value=storage):
            client.post("/api/mini-apps/instances/canvas-1/assets",
                        data={"key": "logo.png"},
                        files={"file": ("logo.png", b"AA", "image/png")})
            r = client.post("/api/mini-apps/instances/canvas-1/assets",
                            data={"key": "logo.png"},
                            files={"file": ("logo.png", b"BB", "image/png")})
        assert r.status_code == 200
        from core.models import MiniAppAsset
        assert db_session.query(MiniAppAsset).count() == 1

    def test_upload_asset_too_large_413(self, client, db_session):
        self._make_app(db_session, status="published")
        self._make_canvas(db_session)
        with patch("api.mini_app_routes.get_max_object_bytes", return_value=4):
            r = client.post("/api/mini-apps/instances/canvas-1/assets",
                            data={"key": "big.bin"},
                            files={"file": ("big.bin", b"x" * 100, "application/octet-stream")})
        assert r.status_code == 413

    def test_upload_asset_invalid_key_400(self, client, db_session):
        self._make_app(db_session, status="published")
        self._make_canvas(db_session)
        with patch("api.mini_app_routes.get_mini_app_storage", return_value=self.FakeStorage()):
            r = client.post("/api/mini-apps/instances/canvas-1/assets",
                            data={"key": "../evil"},
                            files={"file": ("e.bin", b"x", "application/octet-stream")})
        assert r.status_code == 400

    def test_upload_asset_non_owner_403(self, client, db_session):
        self._make_app(db_session, status="published", is_public=True)
        self._make_canvas(db_session, owner="other-user")
        c = self._asset_client(db_session, user_id="user-1")
        r = c.post("/api/mini-apps/instances/canvas-1/assets",
                   data={"key": "k.png"},
                   files={"file": ("k.png", b"x", "image/png")})
        assert r.status_code == 403
        assert r.json()["detail"] == "Not the instance owner"

    def test_list_assets(self, client, db_session):
        from core.models import MiniAppAsset
        self._make_app(db_session, status="published")
        self._make_canvas(db_session)
        db_session.add(MiniAppAsset(canvas_id="canvas-1", tenant_id="t1", key="k1",
                                    uri="uri://k1", content_type="text/plain",
                                    size=3, created_by="user-1"))
        db_session.commit()
        r = client.get("/api/mini-apps/instances/canvas-1/assets")
        assert r.status_code == 200
        assert r.json()["assets"][0]["key"] == "k1"

    def test_list_assets_created_at_none(self, client, db_session):
        from core.models import MiniAppAsset
        self._make_app(db_session, status="published")
        self._make_canvas(db_session)
        db_session.add(MiniAppAsset(canvas_id="canvas-1", tenant_id="t1", key="k1",
                                    uri="uri://k1", content_type=None,
                                    size=3, created_by="user-1"))
        db_session.commit()
        row = db_session.query(MiniAppAsset).filter(MiniAppAsset.key == "k1").first()
        row.created_at = None
        db_session.commit()
        r = client.get("/api/mini-apps/instances/canvas-1/assets")
        assert r.json()["assets"][0]["created_at"] is None

    def test_download_asset(self, client, db_session):
        from core.models import MiniAppAsset
        self._make_app(db_session, status="published")
        self._make_canvas(db_session)
        db_session.add(MiniAppAsset(canvas_id="canvas-1", tenant_id="t1", key="k1",
                                    uri="uri://k1", content_type="text/plain",
                                    size=3, created_by="user-1"))
        db_session.commit()
        storage = self.FakeStorage()
        storage.objects["k1"] = b"data"
        with patch("api.mini_app_routes.get_mini_app_storage", return_value=storage):
            r = client.get("/api/mini-apps/instances/canvas-1/assets/k1")
        assert r.status_code == 200
        assert r.content == b"data"
        assert r.headers["content-type"].startswith("text/plain")

    def test_download_asset_no_row_default_media_type(self, client, db_session):
        self._make_app(db_session, status="published")
        self._make_canvas(db_session)
        storage = self.FakeStorage()
        storage.objects["k1"] = b"data"
        with patch("api.mini_app_routes.get_mini_app_storage", return_value=storage):
            r = client.get("/api/mini-apps/instances/canvas-1/assets/k1")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/octet-stream"

    def test_download_asset_404(self, client, db_session):
        self._make_app(db_session, status="published")
        self._make_canvas(db_session)
        with patch("api.mini_app_routes.get_mini_app_storage", return_value=self.FakeStorage()):
            r = client.get("/api/mini-apps/instances/canvas-1/assets/k1")
        assert r.status_code == 404

    def test_delete_asset(self, client, db_session):
        from core.models import MiniAppAsset
        self._make_app(db_session, status="published")
        self._make_canvas(db_session)
        db_session.add(MiniAppAsset(canvas_id="canvas-1", tenant_id="t1", key="k1",
                                    uri="uri://k1", content_type=None,
                                    size=3, created_by="user-1"))
        db_session.commit()
        storage = self.FakeStorage()
        storage.objects["k1"] = b"data"
        with patch("api.mini_app_routes.get_mini_app_storage", return_value=storage):
            r = client.delete("/api/mini-apps/instances/canvas-1/assets/k1")
        assert r.status_code == 200
        assert r.json()["deleted"] is True
        assert db_session.query(MiniAppAsset).count() == 0

    def test_delete_asset_missing_in_storage(self, client, db_session):
        self._make_app(db_session, status="published")
        self._make_canvas(db_session)
        with patch("api.mini_app_routes.get_mini_app_storage", return_value=self.FakeStorage()):
            r = client.delete("/api/mini-apps/instances/canvas-1/assets/k1")
        assert r.status_code == 200
        assert r.json()["deleted"] is False

    def test_delete_asset_non_owner_403(self, client, db_session):
        self._make_app(db_session, status="published", is_public=True)
        self._make_canvas(db_session, owner="other-user")
        c = self._asset_client(db_session, user_id="user-1")
        r = c.delete("/api/mini-apps/instances/canvas-1/assets/k1")
        assert r.status_code == 403
        assert r.json()["detail"] == "Not the instance owner"

    # ---------------- records: series / query ----------------
    def _record_fixture(self, db_session, app_id="app-1", canvas_id="canvas-1",
                        owner="user-1", db_cfg=None, status="published"):
        manifest = self._valid_manifest()
        if db_cfg is not None:
            manifest["db"] = db_cfg
        self._make_app(db_session, app_id=app_id, status=status, manifest=manifest)
        self._make_canvas(db_session, canvas_id=canvas_id, mini_app_id=app_id,
                          owner=owner)
        return app_id, canvas_id

    def test_records_series_list(self, client, db_session):
        self._record_fixture(db_session)
        r = client.get("/api/mini-apps/instances/canvas-1/records/series")
        assert r.status_code == 200
        assert r.json()["series"] == []

    def test_records_series_list_after_append(self, client, db_session):
        self._record_fixture(db_session)
        client.post("/api/mini-apps/instances/canvas-1/records",
                    json={"series": "s1", "data": {"a": 1}})
        r = client.get("/api/mini-apps/instances/canvas-1/records/series")
        assert r.json()["series"] == [{"series": "s1", "count": 1}]

    def test_records_query_success(self, client, db_session):
        self._record_fixture(db_session)
        client.post("/api/mini-apps/instances/canvas-1/records",
                    json={"series": "s1", "data": {"a": 1}})
        r = client.get("/api/mini-apps/instances/canvas-1/records", params={"series": "s1"})
        assert r.status_code == 200
        assert r.json()["count"] == 1

    def test_records_query_bad_order_400(self, client, db_session):
        self._record_fixture(db_session)
        r = client.get("/api/mini-apps/instances/canvas-1/records",
                       params={"series": "s1", "order": "sideways"})
        assert r.status_code == 400

    def test_records_query_bad_series_400(self, client, db_session):
        self._record_fixture(db_session)
        r = client.get("/api/mini-apps/instances/canvas-1/records", params={"series": "Bad!"})
        assert r.status_code == 400

    def test_records_query_limit_bounds_422(self, client, db_session):
        self._record_fixture(db_session)
        r = client.get("/api/mini-apps/instances/canvas-1/records",
                       params={"series": "s1", "limit": 10001})
        assert r.status_code == 422

    def test_records_append_success(self, client, db_session):
        self._record_fixture(db_session)
        r = client.post("/api/mini-apps/instances/canvas-1/records",
                        json={"series": "chart", "data": {"label": "Jan", "value": 12}})
        assert r.status_code == 200
        assert r.json()["record"]["seq"] == 1

    def test_records_append_bad_series_400(self, client, db_session):
        self._record_fixture(db_session)
        r = client.post("/api/mini-apps/instances/canvas-1/records",
                        json={"series": "UPPER!", "data": {}})
        assert r.status_code == 400

    def test_records_append_invalid_data_400(self, client, db_session):
        self._record_fixture(db_session)
        with patch("core.mini_app_db_service.validate_record_data", return_value=False):
            r = client.post("/api/mini-apps/instances/canvas-1/records",
                            json={"series": "s1", "data": {"x": 1}})
        assert r.status_code == 400

    def test_records_append_manifest_db_disabled_503(self, client, db_session):
        self._record_fixture(db_session, db_cfg={"enabled": False})
        r = client.post("/api/mini-apps/instances/canvas-1/records",
                        json={"series": "s1", "data": {"a": 1}})
        assert r.status_code == 503
        assert r.json()["detail"] == "db_disabled"

    def test_records_append_series_cap_400(self, client, db_session):
        self._record_fixture(db_session, db_cfg={"enabled": True, "max_records_per_series": 1})
        assert client.post("/api/mini-apps/instances/canvas-1/records",
                           json={"series": "s1", "data": {"a": 1}}).status_code == 200
        r = client.post("/api/mini-apps/instances/canvas-1/records",
                        json={"series": "s1", "data": {"a": 2}})
        assert r.status_code == 400
        assert "cap reached" in r.json()["detail"]

    def test_records_append_non_owner_403(self, client, db_session):
        self._record_fixture(db_session, owner="other-user")
        c = self._asset_client(db_session)
        r = c.post("/api/mini-apps/instances/canvas-1/records",
                   json={"series": "s1", "data": {"a": 1}})
        assert r.status_code == 403

    def test_records_kill_switch_503(self, client, db_session):
        self._record_fixture(db_session)
        with patch("api.mini_app_routes.db_store_enabled", return_value=False):
            r = client.get("/api/mini-apps/instances/canvas-1/records/series")
        assert r.status_code == 503

    def test_records_query_body_success(self, client, db_session):
        self._record_fixture(db_session)
        client.post("/api/mini-apps/instances/canvas-1/records",
                    json={"series": "s1", "data": {"a": 1}})
        r = client.post("/api/mini-apps/instances/canvas-1/records/query",
                        json={"series": "s1", "filter": {"a": 1}, "limit": 10, "order": "asc"})
        assert r.status_code == 200
        assert r.json()["count"] == 1

    def test_records_query_body_bad_filter_400(self, client, db_session):
        self._record_fixture(db_session)
        r = client.post("/api/mini-apps/instances/canvas-1/records/query",
                        json={"series": "s1", "filter": {"a": [1, 2]}})
        assert r.status_code == 400

    def test_records_query_body_bad_order_400(self, client, db_session):
        self._record_fixture(db_session)
        r = client.post("/api/mini-apps/instances/canvas-1/records/query",
                        json={"series": "s1", "order": "x"})
        assert r.status_code == 400

    def test_records_count(self, client, db_session):
        self._record_fixture(db_session)
        client.post("/api/mini-apps/instances/canvas-1/records",
                    json={"series": "s1", "data": {"a": 1}})
        r = client.post("/api/mini-apps/instances/canvas-1/records/count", json={})
        assert r.status_code == 200
        assert r.json()["count"] == 1

    def test_records_count_with_series(self, client, db_session):
        self._record_fixture(db_session)
        r = client.post("/api/mini-apps/instances/canvas-1/records/count",
                        json={"series": "s1"})
        assert r.json()["count"] == 0

    def test_records_count_bad_filter_400(self, client, db_session):
        self._record_fixture(db_session)
        r = client.post("/api/mini-apps/instances/canvas-1/records/count",
                        json={"filter": {"a": {"nested": True}}})
        assert r.status_code == 400

    def test_records_count_bad_series_400(self, client, db_session):
        self._record_fixture(db_session)
        r = client.post("/api/mini-apps/instances/canvas-1/records/count",
                        json={"series": "!!"})
        assert r.status_code == 400

    def test_records_get(self, client, db_session):
        self._record_fixture(db_session)
        rid = client.post("/api/mini-apps/instances/canvas-1/records",
                          json={"series": "s1", "data": {"a": 1}}).json()["record"]["id"]
        r = client.get("/api/mini-apps/instances/canvas-1/records/{}".format(rid),
                       params={"series": "s1"})
        assert r.status_code == 200
        assert r.json()["record"]["id"] == rid

    def test_records_get_404(self, client, db_session):
        self._record_fixture(db_session)
        r = client.get("/api/mini-apps/instances/canvas-1/records/nope",
                       params={"series": "s1"})
        assert r.status_code == 404

    def test_records_update(self, client, db_session):
        self._record_fixture(db_session)
        rid = client.post("/api/mini-apps/instances/canvas-1/records",
                          json={"series": "s1", "data": {"a": 1}}).json()["record"]["id"]
        r = client.put("/api/mini-apps/instances/canvas-1/records/{}".format(rid),
                       json={"series": "s1", "data": {"b": 2}})
        assert r.status_code == 200
        assert r.json()["record"]["data"]["b"] == 2

    def test_records_update_invalid_data_400(self, client, db_session):
        self._record_fixture(db_session)
        rid = client.post("/api/mini-apps/instances/canvas-1/records",
                          json={"series": "s1", "data": {"a": 1}}).json()["record"]["id"]
        with patch("core.mini_app_db_service.validate_record_data", return_value=False):
            r = client.put("/api/mini-apps/instances/canvas-1/records/{}".format(rid),
                           json={"series": "s1", "data": {"b": 2}})
        assert r.status_code == 400

    def test_records_update_merged_size_cap_400(self, client, db_session):
        self._record_fixture(db_session, db_cfg={"enabled": True, "max_record_bytes": 60})
        rid = client.post("/api/mini-apps/instances/canvas-1/records",
                          json={"series": "s1", "data": {"a": "x" * 50}}).json()["record"]["id"]
        r = client.put("/api/mini-apps/instances/canvas-1/records/{}".format(rid),
                       json={"series": "s1", "data": {"b": "y" * 40}})
        assert r.status_code == 400
        assert "size cap" in r.json()["detail"]

    def test_records_update_missing_404(self, client, db_session):
        self._record_fixture(db_session)
        r = client.put("/api/mini-apps/instances/canvas-1/records/nope",
                       json={"series": "s1", "data": {"b": 2}})
        assert r.status_code == 404

    def test_records_update_db_disabled_503(self, client, db_session):
        self._record_fixture(db_session, db_cfg={"enabled": False})
        r = client.put("/api/mini-apps/instances/canvas-1/records/r1",
                       json={"series": "s1", "data": {"b": 2}})
        assert r.status_code == 503

    def test_records_delete(self, client, db_session):
        self._record_fixture(db_session)
        rid = client.post("/api/mini-apps/instances/canvas-1/records",
                          json={"series": "s1", "data": {"a": 1}}).json()["record"]["id"]
        r = client.delete("/api/mini-apps/instances/canvas-1/records/{}".format(rid),
                          params={"series": "s1"})
        assert r.status_code == 200
        assert r.json()["deleted"] is True

    def test_records_delete_db_disabled_503(self, client, db_session):
        self._record_fixture(db_session, db_cfg={"enabled": False})
        r = client.delete("/api/mini-apps/instances/canvas-1/records/nope",
                          params={"series": "s1"})
        assert r.status_code == 503

    def test_records_delete_404(self, client, db_session):
        self._record_fixture(db_session)
        r = client.delete("/api/mini-apps/instances/canvas-1/records/nope",
                          params={"series": "s1"})
        assert r.status_code == 404

    def test_records_delete_series(self, client, db_session):
        self._record_fixture(db_session)
        client.post("/api/mini-apps/instances/canvas-1/records",
                    json={"series": "s1", "data": {"a": 1}})
        r = client.delete("/api/mini-apps/instances/canvas-1/records", params={"series": "s1"})
        assert r.status_code == 200
        assert r.json()["deleted"] == 1

    def test_records_delete_series_db_disabled_503(self, client, db_session):
        self._record_fixture(db_session, db_cfg={"enabled": False})
        r = client.delete("/api/mini-apps/instances/canvas-1/records", params={"series": "s1"})
        assert r.status_code == 503


# ============================================================================
# api/office_routes.py
# ============================================================================

class TestOfficeRoutes:
    def _client(self):
        from api.office_routes import router
        from core.auth import get_current_user
        from core.database import get_db_session

        app = _app(router)
        app.dependency_overrides[get_current_user] = lambda: FakeUser()
        app.dependency_overrides[get_db_session] = lambda: Mock()
        return TestClient(app, raise_server_exceptions=False)

    @pytest.fixture()
    def client(self):
        return self._client()

    def _anon(self):
        from api.office_routes import router
        return TestClient(_app(router), raise_server_exceptions=False)

    def _office(self):
        svc = MagicMock()
        for name in ("read_range", "write_cell"):
            getattr(svc.excel, name).return_value = {"success": True, "data": {}}
        for name in ("recalculate", "insert_rows", "insert_columns",
                     "get_evaluated_range", "add_pivot_table", "run_excel_macro"):
            m = AsyncMock(return_value={"success": True, "data": {}})
            setattr(svc.excel, name, m)
        svc.word.read_document.return_value = {"success": True, "data": {}}
        svc.word.modify_document.return_value = {"success": True, "data": {}}
        svc.pptx.read_slides.return_value = {"success": True, "data": {}}
        svc.pptx.modify_slides.return_value = {"success": True, "data": {}}
        return svc

    @pytest.fixture()
    def office(self, monkeypatch):
        svc = self._office()
        monkeypatch.setattr("api.office_routes.office_service", svc)
        monkeypatch.setattr("api.office_routes._validate_office_path", lambda p: p)
        return svc

    def test_unauth_401(self):
        assert self._anon().get("/excel", params={"file_path": "a.xlsx"}).status_code == 401

    def _path400(self, monkeypatch):
        monkeypatch.setattr("api.office_routes._validate_office_path",
                            lambda p: (_ for _ in ()).throw(ValueError("outside scope")))

    # ---------------- excel ----------------
    def test_read_excel_success(self, client, office):
        r = client.get("/excel", params={"file_path": "a.xlsx", "cell_path": "/Sheet1/A1"})
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_read_excel_service_failure_400(self, client, office):
        office.excel.read_range.return_value = {"success": False, "error": "bad"}
        assert client.get("/excel", params={"file_path": "a.xlsx"}).status_code == 400

    def test_read_excel_path_validation_400(self, client, monkeypatch):
        self._path400(monkeypatch)
        assert client.get("/excel", params={"file_path": "../evil.xlsx"}).status_code == 400

    def test_write_excel_success(self, client, office):
        r = client.post("/excel", json={
            "file_path": "a.xlsx", "cell_path": "/Sheet1/A1", "value": 5})
        assert r.status_code == 200
        kwargs = office.excel.write_cell.call_args.kwargs
        assert kwargs["is_formula"] is False

    def test_write_excel_formula(self, client, office):
        client.post("/excel", json={
            "file_path": "a.xlsx", "cell_path": "/Sheet1/A1", "value": "=1+1",
            "is_formula": True})
        assert office.excel.write_cell.call_args.kwargs["is_formula"] is True

    def test_write_excel_failure_400(self, client, office):
        office.excel.write_cell.return_value = {"success": False, "error": "bad"}
        assert client.post("/excel", json={
            "file_path": "a.xlsx", "cell_path": "/Sheet1/A1", "value": 5}).status_code == 400

    def test_recalculate_success_and_failure(self, client, office):
        assert client.post("/excel/recalculate", params={"file_path": "a.xlsx"}).status_code == 200
        office.excel.recalculate.return_value = {"success": False, "error": "bad"}
        assert client.post("/excel/recalculate", params={"file_path": "a.xlsx"}).status_code == 400

    def test_insert_rows_success_and_failure(self, client, office):
        assert client.post("/excel/insert-rows", params={
            "file_path": "a.xlsx", "sheet_name": "S", "row": 2}).status_code == 200
        office.excel.insert_rows.return_value = {"success": False, "error": "bad"}
        assert client.post("/excel/insert-rows", params={
            "file_path": "a.xlsx", "sheet_name": "S", "row": 2}).status_code == 400

    def test_insert_columns_success_and_failure(self, client, office):
        assert client.post("/excel/insert-columns", params={
            "file_path": "a.xlsx", "sheet_name": "S", "column": 2}).status_code == 200
        office.excel.insert_columns.return_value = {"success": False, "error": "bad"}
        assert client.post("/excel/insert-columns", params={
            "file_path": "a.xlsx", "sheet_name": "S", "column": 2}).status_code == 400

    def test_formula_result_success_and_failure(self, client, office):
        assert client.get("/excel/formula-result", params={
            "file_path": "a.xlsx", "cell_path": "/Sheet1/A4"}).status_code == 200
        office.excel.get_evaluated_range.return_value = {"success": False, "error": "bad"}
        assert client.get("/excel/formula-result", params={
            "file_path": "a.xlsx", "cell_path": "/Sheet1/A4"}).status_code == 400

    def test_pivot_table_success_and_failure(self, client, office):
        body = {"file_path": "a.xlsx", "sheet_name": "S", "pivot_sheet_name": "P",
                "data_range": "A1:C10", "rows": ["r"], "columns": ["c"], "values": []}
        assert client.post("/excel/pivot-table", json=body).status_code == 200
        office.excel.add_pivot_table.return_value = {"success": False, "error": "bad"}
        assert client.post("/excel/pivot-table", json=body).status_code == 400

    def test_run_macro_success_and_failure(self, client, office):
        assert client.post("/excel/run-macro", json={
            "file_path": "a.xlsx", "macro_name": "DoIt"}).status_code == 200
        office.excel.run_excel_macro.return_value = {"success": False, "error": "bad"}
        assert client.post("/excel/run-macro", json={
            "file_path": "a.xlsx", "macro_name": "DoIt"}).status_code == 400

    # ---------------- word ----------------
    def test_read_word_success_and_failure(self, client, office):
        assert client.get("/word", params={"file_path": "a.docx"}).status_code == 200
        office.word.read_document.return_value = {"success": False, "error": "bad"}
        assert client.get("/word", params={"file_path": "a.docx"}).status_code == 400

    def test_modify_word_success_and_failure(self, client, office):
        body = {"file_path": "a.docx", "action": "append", "content": "hi",
                "options": {"x": 1}}
        assert client.post("/word", json=body).status_code == 200
        office.word.modify_document.return_value = {"success": False, "error": "bad"}
        assert client.post("/word", json=body).status_code == 400

    # ---------------- pptx ----------------
    def test_read_pptx_success_and_failure(self, client, office):
        assert client.get("/pptx", params={"file_path": "a.pptx"}).status_code == 200
        office.pptx.read_slides.return_value = {"success": False, "error": "bad"}
        assert client.get("/pptx", params={"file_path": "a.pptx"}).status_code == 400

    def test_modify_pptx_success_and_failure(self, client, office):
        body = {"file_path": "a.pptx", "action": "add_slide", "options": {"t": "title"}}
        assert client.post("/pptx", json=body).status_code == 200
        office.pptx.modify_slides.return_value = {"success": False, "error": "bad"}
        assert client.post("/pptx", json=body).status_code == 400

    # ---------------- present / sync ----------------
    def test_present_success_generates_canvas(self, client, office):
        r = client.post("/present", json={"file_path": "a.xlsx", "user_id": "spoofed"})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["canvas_id"].startswith("canvas_")

    def test_present_uses_token_identity(self, client, office):
        sync_svc = MagicMock()
        with patch("api.office_routes.OfficeSyncService", return_value=sync_svc):
            r = client.post("/present", json={
                "file_path": "a.xlsx", "canvas_id": "c-1", "user_id": "spoofed"})
        assert r.status_code == 200
        assert r.json()["canvas_id"] == "c-1"
        assert sync_svc.broadcast_file_update.call_args.kwargs["user_id"] == "user-1"

    def test_sync_update_success(self, client, office):
        sync_svc = MagicMock()
        sync_svc.sync_canvas_to_file.return_value = {"success": True, "data": {}}
        with patch("api.office_routes.OfficeSyncService", return_value=sync_svc) as cls:
            r = client.post("/sync-update", json={
                "canvas_id": "c-1", "file_path": "a.xlsx", "user_id": "spoofed",
                "edit_type": "cell", "data": {"A1": 5}})
        assert r.status_code == 200
        kwargs = cls.return_value.sync_canvas_to_file.call_args.kwargs
        assert kwargs["user_id"] == "user-1"
        assert kwargs["canvas_id"] == "c-1"

    def test_sync_update_failure_400(self, client, office):
        sync_svc = MagicMock()
        sync_svc.sync_canvas_to_file.return_value = {"success": False, "error": "bad"}
        with patch("api.office_routes.OfficeSyncService", return_value=sync_svc):
            r = client.post("/sync-update", json={
                "canvas_id": "c-1", "file_path": "a.xlsx", "user_id": "u",
                "edit_type": "cell", "data": {}})
        assert r.status_code == 400

    def test_present_sync_service_broadcast(self, client, office):
        sync_svc = MagicMock()
        with patch("api.office_routes.OfficeSyncService", return_value=sync_svc) as cls:
            r = client.post("/present", json={"file_path": "a.xlsx", "user_id": "spoofed"})
        assert r.status_code == 200
        kwargs = cls.return_value.broadcast_file_update.call_args.kwargs
        assert kwargs["user_id"] == "user-1"
        assert kwargs["file_path"] == "a.xlsx"


# ============================================================================
# api/openai_gateway_routes.py
# ============================================================================

