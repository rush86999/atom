"""
Delete agent chat session — DELETE /api/chat/sessions/{session_id} (PR #625).

A chat session lives in three stores at once: the orchestrator's in-memory
map, the session manager's DB row (+ ChatMessage rows, which are NOT
FK-cascaded), and the legacy JSON file fallback. The sidebar lists from the
manager, so a delete that misses any store resurrects the conversation on
the next refresh. Pins:

- ownership: another user's chat must not be deletable (403); an
  unauthenticated call must be rejected before any ownership logic;
- full cleanup in one call: ChatMessage rows deleted explicitly (no
  reliance on cascade), the ChatSession row removed, the in-memory copy
  popped, and the session-manager fallback cleaned;
- 404 for unknown sessions — DELETE never lazy-creates (fork's
  _get_or_create_session behavior must not leak into deletion);
- unauthenticated callers must never reach the delete path.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security_dependencies import get_current_user
from integrations import chat_routes as cr

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

OWNER = "user_1"
OTHER = "other_user"


def make_session(session_id="s1", owner=OWNER):
    return {
        "id": session_id,
        "session_id": session_id,
        "user_id": owner,
        "title": "My chat",
        "created_at": "2026-01-01T00:00:00",
        "last_updated": "2026-01-01T00:00:00",
        "history": [{"role": "user", "content": "private payload"}],
        "context": {},
    }


def make_db(messages_deleted=5):
    """Fake SQLAlchemy session: the endpoint bulk-deletes ChatMessage rows
    and loads the ChatSession row for db.delete()."""
    db = MagicMock(name="db")
    msg_query = MagicMock(name="msg_query")
    msg_query.filter.return_value.delete.return_value = messages_deleted
    sess_query = MagicMock(name="sess_query")
    row = SimpleNamespace(id="s1")
    sess_query.filter.return_value.first.return_value = row

    def _query(model):
        return msg_query if getattr(model, "__name__", "") == "ChatMessage" else sess_query

    db.query.side_effect = _query
    db.msg_query = msg_query
    db.sess_query = sess_query
    db.session_row = row
    return db


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(cr.router)
    return application


@pytest.fixture
def fake_db():
    return make_db()


@pytest.fixture
def client(app, fake_db):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=OWNER, tenant_id="t1")
    app.dependency_overrides[cr.get_db] = lambda: fake_db
    return TestClient(app)


@pytest.fixture
def anon_client(app, fake_db):
    app.dependency_overrides[cr.get_db] = lambda: fake_db
    return TestClient(app)


@pytest.fixture
def orch():
    with patch.object(cr, "chat_orchestrator") as m:
        m.session_manager = MagicMock()
        m.session_manager.get_session.return_value = None
        m.conversation_sessions = {}
        yield m


class TestDeleteOwnership:
    def test_unauthenticated_delete_rejected(self, anon_client, orch, fake_db):
        """No token: the mandatory dependency must 401 BEFORE any ownership
        or store-mutation logic (same class of regression as PR #591)."""
        orch.conversation_sessions = {"s1": make_session(owner=OWNER)}
        resp = anon_client.delete("/api/chat/sessions/s1")
        assert resp.status_code in (401, 403), resp.text[:120]
        assert "s1" in orch.conversation_sessions
        fake_db.commit.assert_not_called()

    def test_cross_user_delete_denied(self, client, orch, fake_db):
        """A delete must not leak another user's chat — 403 and every store
        left untouched."""
        orch.conversation_sessions = {"s1": make_session(owner=OTHER)}
        resp = client.delete("/api/chat/sessions/s1")
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Access denied"
        assert "s1" in orch.conversation_sessions
        fake_db.commit.assert_not_called()
        orch.session_manager.delete_session.assert_not_called()


class TestDeleteCleanup:
    def test_owner_delete_cleans_all_stores(self, client, orch, fake_db):
        orch.conversation_sessions = {"s1": make_session(owner=OWNER)}
        resp = client.delete("/api/chat/sessions/s1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["session_id"] == "s1"
        assert body["messages_deleted"] == 5

        # Messages are NOT FK-cascaded from chat_sessions — the bulk delete
        # must happen explicitly.
        fake_db.msg_query.filter.return_value.delete.assert_called_once_with(
            synchronize_session=False)
        fake_db.sess_query.filter.return_value.first.assert_called_once()
        fake_db.delete.assert_called_once_with(fake_db.session_row)
        fake_db.commit.assert_called_once()

        # In-memory copy dropped so the next list cannot resurrect the
        # session...
        assert "s1" not in orch.conversation_sessions
        # ...and the manager (DB row + legacy JSON file) cleaned too.
        orch.session_manager.delete_session.assert_called_once_with("s1")

    def test_delete_missing_session_row_is_fine(self, client, orch, fake_db):
        """A session known to the orchestrator/manager but with no ChatSession
        row (legacy file-only) must still delete cleanly — the DB row delete
        is conditional, everything else proceeds."""
        fake_db.sess_query.filter.return_value.first.return_value = None
        orch.conversation_sessions = {"s1": make_session(owner=OWNER)}
        resp = client.delete("/api/chat/sessions/s1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        fake_db.delete.assert_not_called()
        fake_db.commit.assert_called_once()
        assert "s1" not in orch.conversation_sessions
        orch.session_manager.delete_session.assert_called_once_with("s1")

    def test_unknown_session_404_never_creates(self, client, orch, fake_db):
        """DELETE must not lazy-create (fork uses _get_or_create_session;
        deletion must not) — unknown sessions 404 with no store writes."""
        resp = client.delete("/api/chat/sessions/nope")
        assert resp.status_code == 404
        assert orch.conversation_sessions == {}
        fake_db.commit.assert_not_called()
        orch.session_manager.delete_session.assert_not_called()

    def test_manager_fallback_resolves_session(self, client, orch, fake_db):
        """A session evicted from memory but known to the manager (the boot
        path: sessions reload from the manager at startup) must still be
        deletable by its owner."""
        orch.conversation_sessions = {}
        orch.session_manager.get_session.return_value = make_session(owner=OWNER)
        resp = client.delete("/api/chat/sessions/s1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert "s1" not in orch.conversation_sessions
        orch.session_manager.delete_session.assert_called_once_with("s1")
