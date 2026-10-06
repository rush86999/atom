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


def test_forced_failure_hook_armed_only_by_env_and_marker(monkeypatch):
    from integrations.chat_orchestrator import (
        _ForcedTurnFailure,
        _maybe_force_turn_failure,
    )

    session = {}
    monkeypatch.delenv("ATOM_TEST_FORCE_TURN_FAILURE", raising=False)
    _maybe_force_turn_failure(session, "e1", "provisional", "ask [force-fail]")
    assert session == {}
    monkeypatch.setenv("ATOM_TEST_FORCE_TURN_FAILURE", "1")
    _maybe_force_turn_failure(session, "e1", "provisional", "plain ask")
    assert session == {}
    try:
        _maybe_force_turn_failure(session, "e1", "provisional", "ask [force-fail]")
    except _ForcedTurnFailure as forced:
        assert forced.provisional == "provisional"
    else:
        raise AssertionError("hook must raise when armed")
    assert session.get("_provisional_persisted_for") == "e1"


def test_m2_rewrite_captures_pre_finalization(monkeypatch, session):
    import hashlib

    monkeypatch.setenv("CHAT_FINALIZATION_M2", "1")
    session.add(_assistant_row("session-1", "execution-1", "provisional text here"))
    session.commit()
    response = {
        "success": False,
        "message": "This turn failed and nothing it attempted should be assumed complete.",
        "session_id": "session-1",
        "execution_id": "execution-1",
    }

    _persist_finalized_outcome(session, response, "session-1")

    row, meta = _row_for(session, "execution-1")
    assert row.content == response["message"]
    assert meta["pre_finalization"]["sha256"] == hashlib.sha256(
        b"provisional text here").hexdigest()
    assert "provisional" in meta["pre_finalization"]["head"]
    assert response["data"]["persistence"]["status"] == "persisted"


def test_m2_unchanged_content_writes_no_pre_capture(monkeypatch, session):
    monkeypatch.setenv("CHAT_FINALIZATION_M2", "1")
    session.add(_assistant_row("session-1", "execution-1", "same text"))
    session.commit()
    response = {
        "success": True,
        "message": "same text",
        "session_id": "session-1",
        "execution_id": "execution-1",
    }

    _persist_finalized_outcome(session, response, "session-1")

    _, meta = _row_for(session, "execution-1")
    assert "pre_finalization" not in meta


# ── M2 + task lifecycle: the delivery ledger ────────────────────────────
# The durable row is the load-bearing delivery record; the task's ledger
# is the audit trail that says which operations and evidence produced the
# exact bytes that left.

def _fake_lifecycle(record_calls):
    lifecycle = MagicMock()
    lifecycle.get_task.return_value = {
        "operations": [
            {"operation_id": "op-1", "execution_id": "execution-1"},
            {"operation_id": "op-2", "execution_id": "execution-other"},
        ],
    }

    def _record(run_id, **kwargs):
        record_calls.append({"run_id": run_id, **kwargs})
        return {"delivery_id": "del-1"}

    lifecycle.record_delivery.side_effect = _record
    return lifecycle


def test_m2_records_the_delivery_in_the_task_ledger(monkeypatch, session):
    monkeypatch.setenv("CHAT_FINALIZATION_M2", "1")
    monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")
    session.add(_assistant_row("session-1", "execution-1", "before"))
    session.commit()
    calls = []
    monkeypatch.setattr(
        "integrations.chat_orchestrator._task_lifecycle_for",
        lambda *a, **k: _fake_lifecycle(calls))
    response = {
        "success": True,
        "message": "delivered bytes",
        "session_id": "session-1",
        "execution_id": "execution-1",
        "data": {"task_run_id": "run-1", "finalization_version": "v4"},
    }

    _persist_finalized_outcome(session, response, "session-1")

    assert len(calls) == 1
    call = calls[0]
    assert call["run_id"] == "run-1"
    assert call["execution_id"] == "execution-1"
    # Only this turn's operations, never another execution's.
    assert call["operation_ids"] == ["op-1"]
    assert call["finalization_version"] == "v4"
    # The exact row and the exact delivered bytes.
    assert call["message_id"] and len(call["message_id"]) > 0
    import hashlib
    assert call["content_sha256"] == hashlib.sha256(
        b"delivered bytes").hexdigest()
    assert response["data"]["delivery"]["status"] == "recorded"
    assert response["data"]["delivery"]["delivery_id"] == "del-1"


def test_m2_no_task_run_records_no_delivery(monkeypatch, session):
    monkeypatch.setenv("CHAT_FINALIZATION_M2", "1")
    monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")
    session.add(_assistant_row("session-1", "execution-1", "before"))
    session.commit()
    calls = []
    monkeypatch.setattr(
        "integrations.chat_orchestrator._task_lifecycle_for",
        lambda *a, **k: _fake_lifecycle(calls))
    response = {
        "success": True,
        "message": "no task here",
        "session_id": "session-1",
        "execution_id": "execution-1",
    }

    result = _persist_finalized_outcome(session, response, "session-1")

    assert calls == []
    assert "delivery" not in result["data"]


def test_m2_ledger_failure_does_not_block_the_row(monkeypatch, session):
    """The durable row is the load-bearing record; a ledger failure is
    reported, never raised into the response."""
    monkeypatch.setenv("CHAT_FINALIZATION_M2", "1")
    monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")
    session.add(_assistant_row("session-1", "execution-1", "before"))
    session.commit()
    lifecycle = _fake_lifecycle([])
    lifecycle.record_delivery.side_effect = RuntimeError("store down")
    monkeypatch.setattr(
        "integrations.chat_orchestrator._task_lifecycle_for",
        lambda *a, **k: lifecycle)
    response = {
        "success": True,
        "message": "still delivered",
        "session_id": "session-1",
        "execution_id": "execution-1",
        "data": {"task_run_id": "run-1"},
    }

    result = _persist_finalized_outcome(session, response, "session-1")

    row, _ = _row_for(session, "execution-1")
    assert row.content == "still delivered"
    assert result["data"]["persistence"]["status"] == "persisted"
    assert result["data"]["delivery"]["status"] == "failed"
    assert result["data"]["delivery"]["reason"] == "RuntimeError"


def test_m2_ledger_off_records_nothing(monkeypatch, session):
    monkeypatch.setenv("CHAT_FINALIZATION_M2", "1")
    monkeypatch.delenv("ATOM_TASK_LIFECYCLE_ENABLED", raising=False)
    session.add(_assistant_row("session-1", "execution-1", "before"))
    session.commit()
    response = {
        "success": True,
        "message": "delivered bytes",
        "session_id": "session-1",
        "execution_id": "execution-1",
        "data": {"task_run_id": "run-1"},
    }

    _persist_finalized_outcome(session, response, "session-1")

    assert "delivery" not in response["data"]


def test_failed_provider_envelope_survives_route_serialization():
    """Case-5 finding (2026-10-06): the orchestrator AND the M1
    finalizer both preserve failure_reason/recovery_url on a terminal
    provider failure, but ChatMessageResponse did not DECLARE
    failure_reason — FastAPI's response_model silently dropped it at
    route serialization, so the client could never render the distinct
    retry/top-up UI. This pins the full envelope at the model boundary."""
    from core.finalization import finalize_payload
    from integrations.chat_routes import ChatMessageResponse

    drafted = {
        "success": False,
        "message": "I couldn't generate a response — every configured "
                   "provider is out of credits (opencode-go).",
        "session_id": "s-x", "intent": "search", "confidence": 0.5,
        "suggested_actions": [], "requires_confirmation": False,
        "next_steps": [], "timestamp": "2026-10-06T00:00:00",
        "execution_id": "exec-1",
        "error_code": "no_llm_provider",
        "failure_reason": "provider_credits_exhausted",
        "recovery_url": "/settings/billing",
    }
    finalized = finalize_payload(
        {"execution_id": "exec-1", "status": "failed",
         "result_summary": drafted["message"], "failure_stage": "reply"},
        drafted)
    model = ChatMessageResponse(**finalized)
    dumped = model.model_dump()
    assert dumped["success"] is False
    assert dumped["error_code"] == "no_llm_provider"
    assert dumped["failure_reason"] == "provider_credits_exhausted"
    assert dumped["recovery_url"] == "/settings/billing"
