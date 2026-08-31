# -*- coding: utf-8 -*-
"""Chat-store session fork ("fork from here") for the /chat page.

The chat page persists conversations as SQL ChatMessage rows (not the
atom-agent LanceDB store), so forking at a specific message operates on
those rows. Covers:

- POST /api/chat/sessions/{id}/fork — full copy and inclusive truncation
  at up_to_message_id, lineage metadata, cross-user 403, unknown ids
- GET /api/chat/history/{id} — durable rows are authoritative and expose
  real message ids the fork button needs

Zero network, zero LLM spend; DB is the shared in-memory SQLite factory.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from integrations.chat_routes import router as chat_router
from integrations.chat_routes import chat_orchestrator

USER = "fork-user-1"
OTHER_USER = "fork-user-2"
SESSION_ID = "sess-fork-src-1"


def _seed_conversation(db, session_id=SESSION_ID, user_id=USER):
    """Seed a ChatSession + 4 messages (2 exchanges); returns message ids.

    The worker DB is session-scoped, so clear any earlier seed for this
    session first — re-seeding must not trip UNIQUE collisions.
    """
    from core.models import ChatMessage as ChatMessageModel
    from core.models import ChatSession as ChatSessionModel

    db.query(ChatMessageModel).filter(
        ChatMessageModel.conversation_id == session_id
    ).delete()
    db.query(ChatSessionModel).filter(
        ChatSessionModel.id == session_id
    ).delete()
    db.commit()

    db.add(ChatSessionModel(
        id=session_id,
        user_id=user_id,
        title="Source Chat",
        message_count=4,
    ))
    base = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)
    ids = []
    for i, (role, content) in enumerate([
        ("user", "first question"),
        ("assistant", "first answer"),
        ("user", "second question"),
        ("assistant", "second answer"),
    ]):
        mid = f"{session_id}-msg-{i}"
        ids.append(mid)
        db.add(ChatMessageModel(
            id=mid,
            conversation_id=session_id,
            tenant_id="default",
            role=role,
            content=content,
            created_at=base.replace(minute=i),
        ))
    db.commit()
    return ids


@pytest.fixture
def app():
    a = FastAPI()
    a.include_router(chat_router)
    return a


@pytest.fixture
def client(app, worker_database):
    from core.auth import get_current_user
    from core.database import get_db

    user = MagicMock()
    user.id = USER

    SessionLocal = worker_database

    def _override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    chat_orchestrator.conversation_sessions.pop(SESSION_ID, None)


class TestForkSession:
    def test_full_copy(self, client, worker_database):
        db = worker_database()
        _seed_conversation(db)
        db.close()

        resp = client.post(f"/api/chat/sessions/{SESSION_ID}/fork", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["messages_copied"] == 4
        assert body["forked_from"] == SESSION_ID
        assert body["title"] == "Fork: Source Chat"

        from core.models import ChatMessage as ChatMessageModel
        from core.models import ChatSession as ChatSessionModel

        db = worker_database()
        try:
            fork_row = db.query(ChatSessionModel).filter(
                ChatSessionModel.id == body["session_id"]
            ).first()
            assert fork_row is not None
            assert fork_row.user_id == USER
            assert fork_row.metadata_json["forked_from"] == SESSION_ID
            copied = db.query(ChatMessageModel).filter(
                ChatMessageModel.conversation_id == body["session_id"]
            ).order_by(ChatMessageModel.created_at.asc()).all()
            assert [m.role for m in copied] == ["user", "assistant", "user", "assistant"]
            assert [m.content for m in copied][0] == "first question"
            # fresh ids — a copy never aliases the source rows
            assert all(m.id.startswith(body["session_id"]) is False for m in copied)
            # source untouched
            assert db.query(ChatMessageModel).filter(
                ChatMessageModel.conversation_id == SESSION_ID
            ).count() == 4
        finally:
            db.close()

    def test_up_to_message_id_truncates_inclusive(self, client, worker_database):
        db = worker_database()
        ids = _seed_conversation(db)
        db.close()

        # fork through the FIRST assistant reply
        resp = client.post(
            f"/api/chat/sessions/{SESSION_ID}/fork",
            json={"up_to_message_id": ids[1]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["messages_copied"] == 2

        from core.models import ChatMessage as ChatMessageModel

        db = worker_database()
        try:
            copied = db.query(ChatMessageModel).filter(
                ChatMessageModel.conversation_id == body["session_id"]
            ).order_by(ChatMessageModel.created_at.asc()).all()
            assert [m.content for m in copied] == ["first question", "first answer"]
        finally:
            db.close()

    def test_unknown_up_to_message_id_fails(self, client, worker_database):
        db = worker_database()
        _seed_conversation(db)
        db.close()

        resp = client.post(
            f"/api/chat/sessions/{SESSION_ID}/fork",
            json={"up_to_message_id": "ghost-message"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "not found" in body["error"]

    def test_missing_session_returns_error(self, client):
        resp = client.post("/api/chat/sessions/sess-nope/fork", json={})
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_other_users_session_forbidden(self, client, worker_database):
        db = worker_database()
        _seed_conversation(db, user_id=OTHER_USER)
        db.close()

        # Known session owned by someone else → 403, never a copy.
        chat_orchestrator.conversation_sessions[SESSION_ID] = {
            "id": SESSION_ID, "user_id": OTHER_USER, "history": [],
        }
        resp = client.post(f"/api/chat/sessions/{SESSION_ID}/fork", json={})
        assert resp.status_code == 403


class TestHistoryExposesMessageIds:
    def _patch_db_session(self, worker_database):
        """Point the endpoint's get_db_session at the worker test DB."""
        from contextlib import contextmanager

        SessionLocal = worker_database

        @contextmanager
        def _fake():
            session = SessionLocal()
            try:
                yield session
            finally:
                session.close()

        return patch("core.database.get_db_session", _fake)

    def test_history_returns_durable_rows_with_ids(self, client, worker_database):
        db = worker_database()
        ids = _seed_conversation(db)
        db.close()

        chat_orchestrator.conversation_sessions[SESSION_ID] = {
            "id": SESSION_ID,
            "user_id": USER,
            # stale in-memory turn that must NOT shadow the durable rows
            "history": [{"message": "stale", "response": {"message": "stale"}, "timestamp": ""}],
        }
        try:
            with self._patch_db_session(worker_database):
                resp = client.get(f"/api/chat/history/{SESSION_ID}")
            assert resp.status_code == 200
            messages = resp.json()["messages"]
            assert [m["id"] for m in messages] == ids
            assert messages[0]["role"] == "user"
            assert messages[0]["message"] == "first question"
            assert messages[1]["response"]["message"] == "first answer"
        finally:
            chat_orchestrator.conversation_sessions.pop(SESSION_ID, None)

    def test_history_falls_back_to_memory_when_no_rows(self, client, worker_database):
        # A session id no SQL rows exist for (worker DB is shared across tests).
        mem_sid = "sess-fork-mem-only-1"
        chat_orchestrator.conversation_sessions[mem_sid] = {
            "id": mem_sid,
            "user_id": USER,
            "history": [{"message": "in-memory q", "response": {"message": "in-memory a"}, "timestamp": ""}],
        }
        try:
            with self._patch_db_session(worker_database):
                resp = client.get(f"/api/chat/history/{mem_sid}")
            assert resp.status_code == 200
            messages = resp.json()["messages"]
            assert len(messages) == 1
            assert messages[0]["message"] == "in-memory q"
        finally:
            chat_orchestrator.conversation_sessions.pop(mem_sid, None)
