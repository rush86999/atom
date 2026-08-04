"""
Authorization tests for the canvas state-sync WebSocket
(`api/canvas_routes.py::canvas_state_websocket`).

The C2 fix added an ownership check so an authenticated user can't inject
``canvas:state_update`` into another user's canvas. These tests guard that fix
AND close a fail-open gap: the original check only rejected when the canvas
existed and was owned by someone else — a NONEXISTENT canvas_id was accepted
(the check short-circuited on `canvas is None`). Fail-closed behavior requires
rejecting unknown canvas ids too.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.canvas_routes import router


def _ws_connect_rejects(client, url):
    """Connect a WS and assert the server closes it immediately (authz denial).

    Returns the close code if the server denied; raises AssertionError if the
    server wrongly accepted (stayed open). When the server denies during the
    handshake, the ``websocket_connect`` context manager raises
    WebSocketDisconnect on ``__enter__`` — so we must catch at the call site.
    """
    from starlette.websockets import WebSocketDisconnect

    try:
        with client.websocket_connect(url) as ws:
            # If we get here, the server accepted (handshake completed). Try a
            # receive — it will hang on an accepted connection, but the server
            # should have denied; reaching here means the gate failed.
            ws.receive_text()
    except WebSocketDisconnect as e:
        return e.code
    raise AssertionError(
        "Expected the server to close the connection (authz denial), but "
        "the WS stayed open — the connection was wrongly accepted."
    )


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def app():
    a = FastAPI()
    a.include_router(router)
    return a


@pytest.fixture
def authed_user():
    u = MagicMock()
    u.id = "user-a"
    u.email = "a@test.local"
    return u


@pytest.fixture
def patched_auth(app, authed_user, worker_database, monkeypatch):
    """Patch the WS auth + DB session factory so the endpoint sees our test
    user and the in-memory DB.

    The endpoint does lazy imports of ``get_current_user_ws`` and
    ``SessionLocal`` inside the handler, so we patch them at their source
    modules.
    """
    from core import auth as auth_mod
    from core import database as db_mod

    async def _fake_get_current_user_ws(token, db):
        return authed_user

    monkeypatch.setattr(auth_mod, "get_current_user_ws", _fake_get_current_user_ws)
    # Point the endpoint's SessionLocal at the in-memory test DB.
    monkeypatch.setattr(db_mod, "SessionLocal", worker_database)
    # The endpoint also imports SessionLocal lazily inside the function via
    # `from core.database import SessionLocal` — patch the canvas_routes module
    # reference too in case it was already imported.
    monkeypatch.setattr("api.canvas_routes.SessionLocal", worker_database, raising=False)
    return authed_user


def _make_canvas(db, canvas_id, created_by, tenant_id="tenant-1"):
    from core.models import Canvas, Tenant
    # Ensure the tenant row exists (Canvas.tenant_id has an FK to tenants).
    if not db.query(Tenant).filter(Tenant.id == tenant_id).first():
        db.add(Tenant(id=tenant_id, name="Test Tenant", subdomain=f"t-{tenant_id}"))
        db.flush()
    c = Canvas(
        id=canvas_id,
        tenant_id=tenant_id,
        created_by=created_by,
        name="Test Canvas",
    )
    db.add(c)
    db.commit()
    return c


# ============================================================================
# Authorization contract tests
# ============================================================================

class TestCanvasWsAuthorization:

    def test_nonexistent_canvas_is_rejected_not_accepted(self, app, patched_auth, worker_database):
        """An authenticated user connecting to a NONEXISTENT canvas id must be
        rejected (fail-closed). The original ownership check only fired when
        the canvas existed; a None canvas short-circuited the guard and the
        connection was accepted — letting a user hold an authorized WS for an
        id that didn't belong to them."""
        SessionLocal = worker_database
        db = SessionLocal()
        try:
            from core.models import Canvas
            assert not db.query(Canvas).filter(Canvas.id == "ghost-canvas").first()
        finally:
            db.close()

        client = TestClient(app)
        code = _ws_connect_rejects(
            client, "/api/canvas/ws/ghost-canvas?token=fake-token"
        )
        # 1008 = policy violation (the code the endpoint uses for authz denial).
        assert code == 1008, f"Expected close code 1008, got {code}"

    def test_non_owner_is_rejected(self, app, patched_auth, worker_database):
        """User A cannot connect to a canvas created by user B."""
        SessionLocal = worker_database
        db = SessionLocal()
        try:
            _make_canvas(db, "canvas-b-owned", created_by="user-b")
        finally:
            db.close()

        # patched_auth authenticates as user-a.
        client = TestClient(app)
        code = _ws_connect_rejects(
            client, "/api/canvas/ws/canvas-b-owned?token=fake-token"
        )
        assert code == 1008, f"Expected close code 1008, got {code}"

    def test_owner_is_accepted(self, app, patched_auth, worker_database):
        """The canvas owner can connect — the WS stays open (no denial).

        We send a state update; if the server had denied the connection, the
        send would raise. A successful send confirms the owner was accepted.
        We then close immediately to avoid blocking on the server's receive
        loop (which has nothing to send back).
        """
        SessionLocal = worker_database
        db = SessionLocal()
        try:
            _make_canvas(db, "canvas-a-owned", created_by="user-a")
        finally:
            db.close()

        client = TestClient(app)
        with client.websocket_connect(
            "/api/canvas/ws/canvas-a-owned?token=fake-token"
        ) as ws:
            # If the server had closed (authz denial), this raises. A clean
            # send means the owner connection was accepted.
            ws.send_json({"type": "canvas:state_update", "state": {"foo": "bar"}})
