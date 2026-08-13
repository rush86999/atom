"""Coverage wave 90 — api/satellite_routes.py (28% → 95%+).

WebSocket handshake paths: missing key → 1008, unknown key → 1008
(previously ANY "sk-" string authenticated — auth bypass fixed in an
earlier round, regression-pinned here), valid key → connect + listen
loop → disconnect; unhandled exception → close 1011 (incl. the
close-failure debug path). HTTP key retrieval/rotation: success,
missing-key auto-generation, 404 no workspace, 401 anonymous.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from unittest.mock import AsyncMock, MagicMock, patch

import api.satellite_routes as sr
from core.auth import get_current_user


class FakeUser:
    id = "u-1"


class _DB:
    """get_db_session context-manager stand-in yielding a MagicMock session."""

    def __init__(self, workspace=None):
        self.db = MagicMock()
        self.workspace = workspace

    def __enter__(self):
        q = MagicMock()
        f = MagicMock()
        f.first.return_value = self.workspace
        q.filter.return_value = f
        self.db.query.return_value = q
        return self.db

    def __exit__(self, *exc):
        return False


@pytest.fixture
def mock_service():
    svc = MagicMock()
    # The real SatelliteService.connect() accepts the WebSocket; mirror that
    # so the route's listen loop runs.
    async def _connect(ws, tid):
        await ws.accept()
    svc.connect = AsyncMock(side_effect=_connect)
    svc.disconnect = MagicMock()
    svc.handle_message = AsyncMock()
    return svc


@pytest.fixture
def app(mock_service):
    app = FastAPI()
    app.include_router(sr.router)
    app.dependency_overrides[get_current_user] = lambda: FakeUser()
    with patch.object(sr, "satellite_service", mock_service):
        yield app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(sr.router)
    return TestClient(app)


class TestWebSocketHandshake:
    def test_missing_key_closes_1008(self, client):
        with patch.object(sr, "get_db_session", return_value=_DB()):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect("/api/ws/satellite/connect"):
                    pass
        assert exc_info.value.code == 1008

    def test_unknown_key_closes_1008(self, client):
        """Regression pin: sk-prefixed garbage must NOT authenticate."""
        with patch.object(sr, "get_db_session", return_value=_DB(workspace=None)):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(
                    "/api/ws/satellite/connect?key=sk-forged"
                ):
                    pass
        assert exc_info.value.code == 1008

    def test_valid_key_connects_and_handles_message(self, client, mock_service):
        workspace = MagicMock()
        workspace.id = "ws-1"
        workspace.satellite_api_key = "sk-valid"
        with patch.object(sr, "get_db_session", return_value=_DB(workspace=workspace)):
            with client.websocket_connect("/api/ws/satellite/connect?key=sk-valid") as ws:
                ws.send_json({"type": "ping"})
                # exiting the context disconnects the client; the server loop
                # then sees WebSocketDisconnect and tears down cleanly
        mock_service.connect.assert_called_once()
        assert mock_service.connect.call_args[0][1] == "ws-1"
        mock_service.handle_message.assert_called_once_with("ws-1", {"type": "ping"})

    def test_disconnect_cleanup(self, client, mock_service):
        workspace = MagicMock()
        workspace.id = "ws-1"
        workspace.satellite_api_key = "sk-valid"
        with patch.object(sr, "get_db_session", return_value=_DB(workspace=workspace)):
            with client.websocket_connect(
                "/api/ws/satellite/connect?key=sk-valid"
            ) as ws:
                ws.send_json({"type": "bye"})
        mock_service.disconnect.assert_called_once_with("ws-1")

    def test_loop_exception_closes_1011(self, client, mock_service):
        workspace = MagicMock()
        workspace.id = "ws-1"
        workspace.satellite_api_key = "sk-valid"
        mock_service.handle_message.side_effect = RuntimeError("boom")
        with patch.object(sr, "get_db_session", return_value=_DB(workspace=workspace)):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(
                    "/api/ws/satellite/connect?key=sk-valid"
                ) as ws:
                    ws.send_json({"type": "ping"})
                    ws.receive_json()
        assert exc_info.value.code == 1011

    def test_close_failure_is_tolerated(self, client, mock_service, caplog):
        """Second close() failing only logs debug — connection already gone."""
        workspace = MagicMock()
        workspace.id = "ws-1"
        workspace.satellite_api_key = "sk-valid"
        mock_service.handle_message.side_effect = RuntimeError("boom")
        with patch.object(sr, "get_db_session", return_value=_DB(workspace=workspace)), \
             patch(
                 "starlette.websockets.WebSocket.close",
                 new=AsyncMock(side_effect=RuntimeError("already closed")),
             ), \
             caplog.at_level("DEBUG", logger="api.satellite_routes"):
            with client.websocket_connect(
                "/api/ws/satellite/connect?key=sk-valid"
            ) as ws:
                ws.send_json({"type": "ping"})
        assert "Failed to close WebSocket" in caplog.text


class TestGetKey:
    def _override_db(self, client, db):
        """Depends(get_db) resolves via the captured function object — patch
        the app's dependency_overrides, NOT the module attribute."""
        client.app.dependency_overrides[sr.get_db] = lambda: db
        return client

    def test_get_key_requires_auth(self, anon_client):
        assert anon_client.get("/api/satellite/key").status_code == 401

    def test_get_key_returns_existing(self, client):
        db = MagicMock()
        ws = MagicMock()
        ws.satellite_api_key = "sk-existing"
        db.query.return_value.first.return_value = ws
        self._override_db(client, db)
        resp = client.get("/api/satellite/key")
        assert resp.status_code == 200
        assert resp.json()["data"]["api_key"] == "sk-existing"

    def test_get_key_auto_generates_when_missing(self, client):
        db = MagicMock()
        ws = MagicMock()
        ws.satellite_api_key = None
        db.query.return_value.first.return_value = ws
        self._override_db(client, db)
        with patch.object(sr, "generate_satellite_key", return_value="sk-fresh"):
            resp = client.get("/api/satellite/key")
        assert resp.status_code == 200
        assert resp.json()["data"]["api_key"] == "sk-fresh"
        assert ws.satellite_api_key == "sk-fresh"
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(ws)

    def test_get_key_no_workspace_404(self, client):
        db = MagicMock()
        db.query.return_value.first.return_value = None
        self._override_db(client, db)
        resp = client.get("/api/satellite/key")
        assert resp.status_code == 404


class TestRotate:
    def _override_db(self, client, db):
        client.app.dependency_overrides[sr.get_db] = lambda: db
        return client

    def test_rotate_requires_auth(self, anon_client):
        assert anon_client.post("/api/satellite/rotate").status_code == 401

    def test_rotate_regenerates_key(self, client):
        db = MagicMock()
        ws = MagicMock()
        ws.satellite_api_key = "sk-old"
        db.query.return_value.first.return_value = ws
        self._override_db(client, db)
        with patch.object(sr, "generate_satellite_key", return_value="sk-new"):
            resp = client.post("/api/satellite/rotate")
        assert resp.status_code == 200
        assert resp.json()["data"]["api_key"] == "sk-new"
        assert ws.satellite_api_key == "sk-new"
        db.commit.assert_called_once()

    def test_rotate_no_workspace_404(self, client):
        db = MagicMock()
        db.query.return_value.first.return_value = None
        self._override_db(client, db)
        resp = client.post("/api/satellite/rotate")
        assert resp.status_code == 404
