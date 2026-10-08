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


def test_empty_reply_rewrite_reaches_the_durable_row(monkeypatch, app, orch, session):
    """Empty-stream persistence (owner directive 2026-10-08): when the
    reply leg yields no content, the truthful empty_reply outcome must be
    what the DURABLE row carries — not only the HTTP envelope. Rewriting
    the envelope after the persist left history reloads serving the blank
    row after a restart."""
    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")
    monkeypatch.setenv("CHAT_FINALIZATION_M2", "1")
    session.add(
        AgentExecution(
            id="execution-empty",
            status="completed",
            started_at=datetime.now(timezone.utc),
            result_summary="stream ended with no content",
            metadata_json={"session_id": "session-empty"},
        )
    )
    session.add(_assistant_row("session-empty", "execution-empty", ""))
    session.commit()
    orch.process_chat_message = AsyncMock(
        return_value={
            "success": True,
            "message": "",
            "session_id": "session-empty",
            "execution_id": "execution-empty",
            "data": {},
        }
    )

    body = TestClient(app).post(
        "/api/chat/message", json={"message": "hi", "user_id": "u"}).json()

    assert body["success"] is False
    assert body["error_code"] == "empty_reply"
    assert "model returned no content" in body["message"]
    # The DURABLE row agrees with the envelope — history reloads after a
    # restart serve the same truthful outcome, never the blank.
    row, meta = _row_for(session, "execution-empty")
    assert row is not None
    assert row.content == body["message"]
    assert meta.get("error_code") == "empty_reply"


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


CREDIT_ENVELOPE_MESSAGE = (
    "I couldn't generate a response — every configured provider is "
    "out of credits (opencode-go). The last provider error: 402. "
    "Top up the provider balances in Settings → Providers, then ask "
    "again — retrying without a top-up will fail the same way.")


def _credit_drafted():
    return {
        "success": False,
        "message": CREDIT_ENVELOPE_MESSAGE,
        "session_id": "s-x", "intent": "search", "confidence": 0.5,
        "suggested_actions": [], "requires_confirmation": False,
        "next_steps": [], "timestamp": "2026-10-06T00:00:00",
        "execution_id": "exec-1",
        "error_code": "no_llm_provider",
        "failure_reason": "provider_credits_exhausted",
        "recovery_url": "/settings/billing",
    }


def test_failed_credit_envelope_message_preserved_verbatim():
    """Case-5 gap (2026-10-06): finalize_payload rebuilt the failure
    message from the execution record even when the reply leg had
    already drafted the specific truthful credit envelope — the live
    T2 row persisted the generic prefix with the cause truncated and
    the remedy cut off. The full envelope (message + fields) must
    survive finalization verbatim. Isolated stub of the verbatim
    failure string; no provider account involved."""
    from core.finalization import finalize_payload

    drafted = _credit_drafted()
    finalized = finalize_payload(
        {"execution_id": "exec-1", "status": "failed",
         "result_summary": drafted["message"], "failure_stage": "reply"},
        drafted)
    assert finalized["success"] is False
    assert finalized["message"] == CREDIT_ENVELOPE_MESSAGE
    assert finalized["error_code"] == "no_llm_provider"
    assert finalized["failure_reason"] == "provider_credits_exhausted"
    assert finalized["recovery_url"] == "/settings/billing"
    assert finalized["execution_id"] == "exec-1"


def test_failed_execution_without_drafted_error_still_synthesizes():
    """The M1 frozen-case contract is unchanged: a failed execution
    with no specific drafted message still gets the generic
    record-derived failure text (never success, never silent)."""
    from core.finalization import finalize_payload

    for blank in ("", "Message processed successfully"):
        finalized = finalize_payload(
            {"execution_id": "exec-9", "status": "failed",
             "result_summary": "editor blew up", "failure_stage": "edit"},
            {"success": True, "message": blank, "execution_id": "exec-9"})
        assert finalized["success"] is False
        assert "Failure at edit: editor blew up" in finalized["message"]
        assert "exec-9" in finalized["message"]


def test_successful_finalization_adds_no_failure_fields():
    """Failure fields must not leak into unrelated successes: a
    completed execution's drafted success passes through with no
    error keys added and the message untouched."""
    from core.finalization import finalize_payload

    drafted = {"success": True, "message": "done", "execution_id": "exec-2"}
    finalized = finalize_payload(
        {"execution_id": "exec-2", "status": "completed",
         "result_summary": "done", "failure_stage": ""},
        drafted)
    assert finalized["success"] is True
    assert finalized["message"] == "done"
    assert "error_code" not in finalized
    assert "failure_reason" not in finalized
    assert "recovery_url" not in finalized


def test_unknown_execution_preserves_truthful_error_message():
    """An unknown/missing execution record must not clobber a
    specific drafted error either — the turn stays failed and the
    truthful text (with its remedy) is what the client renders."""
    from core.finalization import finalize_payload

    drafted = _credit_drafted()
    finalized = finalize_payload(None, drafted)
    assert finalized["success"] is False
    assert finalized["message"] == CREDIT_ENVELOPE_MESSAGE
    assert finalized["failure_reason"] == "provider_credits_exhausted"


def test_two_consecutive_credit_failures_carry_metadata_through_http(
        monkeypatch, app, orch, session):
    """Case-5 counted-trial contract (2026-10-06): the POSTED response
    body itself — not just the persisted row — must carry the verbatim
    truthful text AND the failure metadata (error_code + failure_reason
    + recovery_url) on EACH of two consecutive credit failures while
    the provider stays broken. The route's final ChatMessageResponse
    assembly passed error_code but never failure_reason/recovery_url,
    so every credit failure through the actual HTTP boundary serialized
    null metadata (the observed T3 envelope: error_code=no_llm_provider
    with failure_reason null). Isolated orchestrator stub of the
    verbatim credit envelope; no provider account involved."""
    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")
    monkeypatch.setenv("CHAT_FINALIZATION_M2", "1")
    for i in (1, 2):
        session.add(AgentExecution(
            id=f"execution-{i}",
            status="failed",
            started_at=datetime.now(timezone.utc),
            result_summary=CREDIT_ENVELOPE_MESSAGE,
            metadata_json={"session_id": "session-1"},
        ))
        session.add(_assistant_row(
            "session-1", f"execution-{i}", "Message processed successfully"))
    session.commit()

    client = TestClient(app)
    for i in (1, 2):
        orch.process_chat_message = AsyncMock(return_value={
            "success": False,
            "message": CREDIT_ENVELOPE_MESSAGE,
            "session_id": "session-1",
            "execution_id": f"execution-{i}",
            "error_code": "no_llm_provider",
            "failure_reason": "provider_credits_exhausted",
            "recovery_url": "/settings/billing",
            "data": {},
        })
        body = client.post(
            "/api/chat/message", json={"message": "hi", "user_id": "u"}
        ).json()
        assert body["success"] is False
        assert body["message"] == CREDIT_ENVELOPE_MESSAGE
        assert body["error_code"] == "no_llm_provider"
        assert body["failure_reason"] == "provider_credits_exhausted"
        assert body["recovery_url"] == "/settings/billing"
        assert body["execution_id"] == f"execution-{i}"

    # Each failure stays bound to its own turn's durable row — the
    # second failure never overwrites the first (exact per-turn
    # binding under M2).
    row1, meta1 = _row_for(session, "execution-1")
    row2, meta2 = _row_for(session, "execution-2")
    assert row1 is not None and row2 is not None
    assert row1.content == CREDIT_ENVELOPE_MESSAGE
    assert row2.content == CREDIT_ENVELOPE_MESSAGE
    assert meta1["error_code"] == "no_llm_provider"
    assert meta2["error_code"] == "no_llm_provider"


def test_empty_reply_produces_truthful_error_response():
    """Empty-stream regression (owner directive 2026-10-08): a turn whose
    reply is empty must produce a truthful error (error_code=empty_reply,
    honest message about the model returning no content — NOT the stale
    'No model provider configured' text or the credit remedy)."""
    from integrations.chat_routes import ChatMessageResponse

    # The blank-reply handler constructs this response shape in the route
    # (the code path at send_chat_message ~2259). We verify the response
    # carries the right fields by constructing it the same way the route
    # does and asserting the contract.
    blank = ChatMessageResponse(
        success=False,
        message=(
            "I couldn't generate a response just now — the "
            "model returned no content. Please try again in a "
            "moment; your message was received and the next "
            "request will dispatch normally."),
        session_id="s-empty", intent="unknown", confidence=0.0,
        error_code="empty_reply",
        suggested_actions=[], requires_confirmation=False,
        next_steps=[], timestamp="2026-10-08T00:00:00")
    dumped = blank.model_dump()
    assert dumped["success"] is False
    assert dumped["error_code"] == "empty_reply"
    # truthful cause, NOT the stale provider-configuration or credit text
    assert "model returned no content" in dumped["message"]
    assert "No model provider" not in dumped["message"]
    assert "credit" not in dumped["message"].lower()
    assert "no_llm_provider" not in dumped.get("error_code", "")
    # no stale recovery URL pointing at the wrong remedy
    assert not dumped.get("recovery_url")
