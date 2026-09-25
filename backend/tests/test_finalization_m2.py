import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import get_db
from core.models import AgentExecution, ChatMessage
from core.models_registration import Base
from core.security_dependencies import get_current_user
from integrations import chat_routes as cr
from integrations.chat_routes import _persist_finalized_outcome


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    yield db
    db.close()
    engine.dispose()


def _assistant_row(session_id, execution_id, content):
    return ChatMessage(
        conversation_id=session_id,
        tenant_id="default",
        role="assistant",
        content=content,
        metadata_json=json.dumps({"execution_id": execution_id}),
        created_at=datetime.now(timezone.utc),
    )


def _row_for(session, execution_id):
    rows = (
        session.query(ChatMessage)
        .filter(ChatMessage.role == "assistant")
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .all()
    )
    for row in rows:
        meta = json.loads(row.metadata_json or "{}")
        if meta.get("execution_id") == execution_id:
            return row, meta
    return None, {}


def test_m2_flag_off_leaves_persisted_row_untouched(monkeypatch, session):
    monkeypatch.delenv("CHAT_FINALIZATION_M2", raising=False)
    session.add(_assistant_row("session-1", "execution-1", "original"))
    session.commit()
    response = {
        "success": False,
        "message": "updated",
        "session_id": "session-1",
        "execution_id": "execution-1",
    }

    assert _persist_finalized_outcome(session, response, "session-1") is response
    row, _ = _row_for(session, "execution-1")
    assert row.content == "original"


def test_m2_failed_outcome_reaches_the_durable_row(monkeypatch, session):
    monkeypatch.setenv("CHAT_FINALIZATION_M2", "1")
    session.add(_assistant_row("session-1", "execution-1", "Message processed successfully"))
    session.commit()
    response = {
        "success": False,
        "message": "This turn failed: editor failed (execution execution-1)",
        "session_id": "session-1",
        "execution_id": "execution-1",
        "error_code": "execution_failed",
    }

    result = _persist_finalized_outcome(session, response, "session-1")

    assert result is response
    row, meta = _row_for(session, "execution-1")
    assert row.content == response["message"]
    assert meta["execution_id"] == "execution-1"
    assert meta["success"] is False
    assert meta["error_code"] == "execution_failed"
    assert meta["quality"] == "error"


def test_m2_concurrent_turns_never_touch_each_other(monkeypatch, session):
    monkeypatch.setenv("CHAT_FINALIZATION_M2", "1")
    session.add(_assistant_row("session-1", "execution-a", "reply A"))
    session.add(_assistant_row("session-1", "execution-b", "reply B"))
    session.commit()

    _persist_finalized_outcome(
        session,
        {
            "success": False,
            "message": "turn A failed",
            "session_id": "session-1",
            "execution_id": "execution-a",
        },
        "session-1",
    )

    row_a, _ = _row_for(session, "execution-a")
    row_b, _ = _row_for(session, "execution-b")
    assert row_a.content == "turn A failed"
    assert row_b.content == "reply B"


def test_m2_duplicate_retry_updates_one_row(monkeypatch, session):
    monkeypatch.setenv("CHAT_FINALIZATION_M2", "1")
    session.add(_assistant_row("session-1", "execution-1", "first delivery"))
    session.commit()
    response = {
        "success": False,
        "message": "second delivery",
        "session_id": "session-1",
        "execution_id": "execution-1",
    }

    _persist_finalized_outcome(session, response, "session-1")
    _persist_finalized_outcome(session, response, "session-1")

    count = session.query(ChatMessage).filter(ChatMessage.role == "assistant").count()
    row, _ = _row_for(session, "execution-1")
    assert count == 1
    assert row.content == "second delivery"


def test_m2_missing_row_inserts_nothing(monkeypatch, session):
    monkeypatch.setenv("CHAT_FINALIZATION_M2", "1")
    response = {
        "success": False,
        "message": "turn failed",
        "session_id": "session-1",
        "execution_id": "execution-unknown",
    }

    assert _persist_finalized_outcome(session, response, "session-1") is response
    assert session.query(ChatMessage).count() == 0


def test_m2_lookup_failure_never_breaks_delivery(monkeypatch):
    monkeypatch.setenv("CHAT_FINALIZATION_M2", "1")

    class _BrokenSession:
        def query(self, *args, **kwargs):
            raise RuntimeError("database unavailable")

        def rollback(self):
            pass

    response = {"success": False, "message": "turn failed", "execution_id": "execution-1"}

    assert _persist_finalized_outcome(_BrokenSession(), response, "session-1") is response


@pytest.fixture
def app(session):
    application = FastAPI()
    application.include_router(cr.router)
    application.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="user_1", tenant_id="t1")
    application.dependency_overrides[get_db] = lambda: session
    return application


@pytest.fixture
def orch():
    with patch.object(cr, "chat_orchestrator") as m:
        m.session_manager = MagicMock()
        m.conversation_sessions = {}
        yield m


def test_m2_http_and_history_agree_on_failed_turn(monkeypatch, app, orch, session):
    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")
    monkeypatch.setenv("CHAT_FINALIZATION_M2", "1")
    session.add(
        AgentExecution(
            id="execution-1",
            status="failed",
            started_at=datetime.now(timezone.utc),
            result_summary="editor failed",
            metadata_json={"session_id": "session-1"},
        )
    )
    session.add(_assistant_row("session-1", "execution-1", "Message processed successfully"))
    session.commit()
    orch.process_chat_message = AsyncMock(
        return_value={
            "success": False,
            "message": "Message processed successfully",
            "session_id": "session-1",
            "execution_id": "execution-1",
            "data": {},
        }
    )

    body = TestClient(app).post("/api/chat/message", json={"message": "hi", "user_id": "u"}).json()

    assert body["execution_id"] == "execution-1"
    assert body["success"] is False
    assert "editor failed" in body["message"]
    row, meta = _row_for(session, "execution-1")
    assert row.content == body["message"]
    assert meta["execution_id"] == "execution-1"
