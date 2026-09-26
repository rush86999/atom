# -*- coding: utf-8 -*-
"""Keyed transport idempotency (work order Step 3).

Same identity + same payload replays without execution; same identity +
different payload conflicts; same identity while running returns
in-progress without a second execution; reservations arbitrate
concurrent duplicates to one executor; completion persists the finalized
response across restarts.
"""
from __future__ import annotations

import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core import chat_transport as ct
from core.models_registration import Base


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def get_db_session():
        session = factory()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    import core.database as database_module

    old = database_module.get_db_session
    database_module.get_db_session = get_db_session
    yield factory
    database_module.get_db_session = old
    engine.dispose()


def _scope(**over):
    base = {"tenant_id": "t", "user_id": "u", "session_id": "s",
            "request_id": "r1"}
    base.update(over)
    return base


def test_payload_hash_covers_entire_request():
    a = ct.payload_hash(message="hi", session_id="s", user_id="u",
                        context={"k": 1}, agent_id=None, images=None)
    b = ct.payload_hash(message="hi", session_id="s", user_id="u",
                        context={"k": 2}, agent_id=None, images=None)
    assert a != b
    assert a == ct.payload_hash(
        message="hi", session_id="s", user_id="u", context={"k": 1},
        agent_id=None, images=None)


def test_reserve_then_replay(db):
    factory = db
    session = factory()
    action, rec = ct.check(
        session, **_scope(), digest="h1", payload_text="{}")
    assert action == "execute"
    ct.complete(session, rec, execution_id="e1",
                finalized={"success": True, "message": "done"})
    session.close()

    session2 = factory()
    action2, rec2 = ct.check(
        session2, **_scope(), digest="h1", payload_text="{}")
    assert action2 == "replay"
    assert ct.stored_response(rec2) == {"success": True, "message": "done"}
    assert rec2.execution_id == "e1"
    session2.close()


def test_conflict_on_different_payload(db):
    session = db()
    action, _ = ct.check(session, **_scope(), digest="h1", payload_text="{}")
    assert action == "execute"
    ct.complete(session, session.query(
        __import__("core.models", fromlist=["ChatRequestRecord"])
        .ChatRequestRecord).first(), finalized={"success": True})
    action2, rec2 = ct.check(
        session, **_scope(), digest="OTHER", payload_text="{}")
    assert action2 == "conflict"
    session.close()


def test_in_progress_no_second_execution(db):
    session = db()
    action, _ = ct.check(session, **_scope(), digest="h1", payload_text="{}")
    assert action == "execute"
    action2, _ = ct.check(session, **_scope(), digest="h1", payload_text="{}")
    assert action2 == "in_progress"
    session.close()


def test_concurrent_reserve_single_executor(tmp_path):
    # File database: separate connections per thread with real locking
    # (in-memory StaticPool shares one connection and cannot arbitrate).
    import time as _time

    from sqlalchemy import create_engine as _create_engine
    from sqlalchemy.orm import sessionmaker as _sessionmaker

    engine = _create_engine(
        f"sqlite:///{tmp_path}/race.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    factory = _sessionmaker(bind=engine, expire_on_commit=False)
    outcomes = []
    barrier = threading.Barrier(4)

    def _try():
        session = factory()
        try:
            barrier.wait(timeout=10)
            action, _ = ct.check(
                session, **_scope(), digest="h1", payload_text="{}")
            outcomes.append(action)
        finally:
            session.close()

    threads = [threading.Thread(target=_try) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes.count("execute") == 1, outcomes
    assert set(outcomes) <= {"execute", "in_progress"}
    engine.dispose()


def test_completion_persists_across_sessions(db):
    factory = db
    session = factory()
    _, rec = ct.check(session, **_scope(request_id="r-restart"),
                      digest="h", payload_text="{}")
    ct.complete(session, rec, execution_id="e9",
                assistant_message_id="m9",
                finalized={"success": True, "message": "kept"})
    session.close()
    # A new process reads the same database file: the replay survives.
    session2 = factory()
    action, rec2 = ct.check(session2, **_scope(request_id="r-restart"),
                            digest="h", payload_text="{}")
    assert action == "replay"
    assert rec2.assistant_message_id == "m9"
    assert ct.stored_response(rec2)["message"] == "kept"
    session2.close()


@pytest.mark.asyncio
async def test_http_replay_skips_execution_render_history(monkeypatch):
    """Same request ID + same payload over HTTP: the stored finalized
    response returns with zero orchestrator execution, zero renders, and
    zero new history rows."""
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock, patch

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine as _create_engine
    from sqlalchemy.orm import sessionmaker as _sessionmaker
    from sqlalchemy.pool import StaticPool

    from core.database import get_db
    from core.models import ChatMessage, ChatRequestRecord
    from core.models_registration import Base as _Base
    from core.security_dependencies import get_current_user
    from integrations import chat_routes as cr

    engine = _create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool)
    _Base.metadata.create_all(engine)
    factory = _sessionmaker(bind=engine, expire_on_commit=False)
    seed = factory()
    message = "find the price of U-22 in w.xlsx"
    digest = ct.payload_hash(
        message=message, session_id="s-http", user_id="user_1",
        context=None, agent_id=None, images=None)
    stored = {"success": True, "message": "STORED FINAL",
              "session_id": "s-http", "intent": "search", "confidence": 0.9,
              "suggested_actions": [], "requires_confirmation": False,
              "next_steps": [], "timestamp": "2026-09-26T00:00:00",
              "metadata": {}, "model": "deterministic",
              "provider": "structured", "execution_id": "exec-kept"}
    seed.add(ChatRequestRecord(
        tenant_id="t1", user_id="user_1", session_id="s-http",
        request_id="req-http-1", payload_sha256=digest,
        request_payload="{}", state=ct.COMPLETED,
        execution_id="exec-kept",
        finalized_response=__import__("json").dumps(stored)))
    seed.commit()
    seed.close()

    application = FastAPI()
    application.include_router(cr.router)
    application.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="user_1", tenant_id="t1")
    application.dependency_overrides[get_db] = lambda: factory()

    with patch.object(cr.chat_orchestrator, "process_chat_message",
                      new=AsyncMock(side_effect=AssertionError(
                          "must not execute"))) as proc:
        body = TestClient(application).post(
            "/api/chat/message",
            json={"message": message, "session_id": "s-http",
                  "user_id": "user_1", "request_id": "req-http-1"}).json()
    assert proc.await_count == 0
    assert body["message"] == "STORED FINAL"
    assert body["execution_id"] == "exec-kept"
    check = factory()
    assert check.query(ChatMessage).count() == 0
    assert check.query(ChatRequestRecord).filter(
        ChatRequestRecord.request_id == "req-http-1").count() == 1
    check.close()
    engine.dispose()


def test_completion_never_replaces_a_pinned_response(db):
    """Delivery history and retry identity are separate.

    A later re-finalization of the same message row is recorded as a NEW
    event in the task's delivery ledger, but the response this request id
    was pinned with is a client contract: a retry of the same request must
    return the same bytes. History belongs in the ledger, not in an
    overwritten pin.
    """
    factory = db
    session = factory()
    _, rec = ct.check(session, **_scope(request_id="r-pin"),
                      digest="h", payload_text="{}")
    ct.complete(session, rec, execution_id="e1",
                assistant_message_id="m1",
                finalized={"success": True, "message": "original"})
    session.close()

    # Something re-finalizes the row later and tries to complete again.
    session2 = factory()
    action, rec2 = ct.check(session2, **_scope(request_id="r-pin"),
                            digest="h", payload_text="{}")
    assert action == "replay"
    ct.complete(session2, rec2, execution_id="e1",
                assistant_message_id="m1",
                finalized={"success": True, "message": "rewritten"})
    session2.close()

    session3 = factory()
    _, rec3 = ct.check(session3, **_scope(request_id="r-pin"),
                       digest="h", payload_text="{}")
    assert ct.stored_response(rec3)["message"] == "original"
    assert rec3.execution_id == "e1"
    assert rec3.assistant_message_id == "m1"
    session3.close()


def test_completion_of_a_fresh_record_still_pins(db):
    """The append-only guard must not break the normal first completion."""
    factory = db
    session = factory()
    _, rec = ct.check(session, **_scope(request_id="r-fresh"),
                      digest="h", payload_text="{}")
    ct.complete(session, rec, execution_id="e2",
                assistant_message_id="m2",
                finalized={"success": True, "message": "first"})
    assert rec.state == ct.COMPLETED
    assert ct.stored_response(rec)["message"] == "first"
    session.close()


def test_pin_survives_restart_and_later_refinalization(db):
    """The full contract: restart, then re-finalize the same row.

    The original request identity must keep returning its original pinned
    response across BOTH. The re-finalization is a real event and belongs
    in the task's delivery ledger as a NEW delivery — it must not rewrite
    what this request id promised, or a client's retry would silently
    return different bytes than its first attempt.
    """
    factory = db

    # Turn one: the request is completed and pinned.
    session = factory()
    _, rec = ct.check(session, **_scope(request_id="r-restart-2"),
                      digest="h", payload_text="{}")
    ct.complete(session, rec, execution_id="e1", assistant_message_id="m1",
                finalized={"success": True, "message": "original bytes",
                           "session_id": "s1"})
    original = ct.stored_response(rec)
    session.close()

    # The process restarts: a brand new session, same database.
    session2 = factory()
    action, rec2 = ct.check(session2, **_scope(request_id="r-restart-2"),
                            digest="h", payload_text="{}")
    assert action == "replay"
    assert ct.stored_response(rec2)["message"] == "original bytes"

    # Something re-finalizes the row and tries to complete the pin again.
    ct.complete(session2, rec2, execution_id="e1", assistant_message_id="m1",
                finalized={"success": True, "message": "REWRITTEN bytes",
                           "session_id": "s1"})
    session2.close()

    # A second restart, then the same request id again.
    session3 = factory()
    action, rec3 = ct.check(session3, **_scope(request_id="r-restart-2"),
                            digest="h", payload_text="{}")
    assert action == "replay"
    assert ct.stored_response(rec3) == original
    assert rec3.execution_id == "e1"
    assert rec3.assistant_message_id == "m1"
    session3.close()

    # A DIFFERENT request id is a different turn and may be pinned
    # independently — the append-only guard is per request identity.
    session4 = factory()
    _, rec4 = ct.check(session4, **_scope(request_id="r-restart-3"),
                       digest="h2", payload_text="{}")
    ct.complete(session4, rec4, execution_id="e2", assistant_message_id="m2",
                finalized={"success": True, "message": "second turn bytes"})
    assert ct.stored_response(rec4)["message"] == "second turn bytes"
    session4.close()


def test_pin_survives_a_huge_metadata_blob(db):
    """A workbook turn's metadata is the whole structured result and
    coverage report. The pin must not be truncated by it.

    This is a real regression: the pin used to be sliced to a byte limit,
    which cut the JSON mid-string, so a correct turn answered 500 on
    retry with `idempotent_replay_unavailable`.
    """
    factory = db
    huge = {"rows": [{"i": i, "cell": "X" * 400} for i in range(4000)]}
    response = {
        "success": True, "message": "the answer", "session_id": "s1",
        "execution_id": "e1", "intent": "file_ask",
        "metadata": huge,
    }
    session = factory()
    _, rec = ct.check(session, **_scope(request_id="r-huge"),
                      digest="h", payload_text="{}")
    ct.complete(session, rec, execution_id="e1", assistant_message_id="m1",
                finalized=response)
    session.close()

    session2 = factory()
    action, rec2 = ct.check(session2, **_scope(request_id="r-huge"),
                            digest="h", payload_text="{}")
    assert action == "replay"
    stored = ct.stored_response(rec2)
    assert stored is not None, "the pin must be parseable JSON"
    # The retry contract survives verbatim.
    assert stored["message"] == "the answer"
    assert stored["execution_id"] == "e1"
    assert stored["session_id"] == "s1"
    # The oversized metadata is not duplicated into the pin; it lives on
    # the assistant message row this record points at.
    assert "metadata" not in stored
    assert len(rec2.finalized_response) < 60000
    session2.close()


def test_replay_projection_keeps_the_retry_contract():
    response = {
        "success": False, "message": "m", "session_id": "s", "intent": "i",
        "confidence": 0.5, "execution_id": "e", "error_code": "boom",
        "model": "x", "provider": "y", "timestamp": "t",
        "suggested_actions": [], "next_steps": [], "requires_confirmation": False,
        "metadata": {"anything": 1},
    }
    projection = ct.replay_projection(response)
    assert projection["message"] == "m"
    assert projection["execution_id"] == "e"
    assert projection["error_code"] == "boom"
    assert "metadata" not in projection
    assert ct.replay_projection(None) == {}
    assert ct.replay_projection("not a dict") == {}


def test_route_error_handler_preserves_deliberate_statuses():
    """A deliberate status must survive the route's error handler.

    The handler converted EVERY exception to 500, so the keyed-conflict
    409 reached the client as a server failure. The acceptance run read
    that as a broken conflict contract when the conflict had been
    detected correctly all along.
    """
    import inspect

    from fastapi import HTTPException

    from integrations import chat_routes as cr

    source = inspect.getsource(cr.send_chat_message)
    assert "except HTTPException:" in source, (
        "send_chat_message must re-raise HTTPException, not convert a "
        "deliberate 409/429/503 into a 500")
    rethrow = source.index("except HTTPException:")
    # The blanket handler that FOLLOWS the passthrough, not any earlier
    # unrelated `except Exception` inside the function.
    blanket = source.index("except Exception", rethrow)
    assert rethrow < blanket, (
        "the HTTPException passthrough must come BEFORE the blanket "
        "Exception -> 500 conversion")
    between = source[rethrow:blanket]
    assert "raise" in between, (
        "the HTTPException branch must re-raise, not fall through")

    # And the conversion still applies to a genuine unexpected failure.
    assert "status_code=500" in source


def test_keyed_conflict_detail_is_a_409_shaped_payload():
    """The conflict the route raises must carry a machine-readable code
    so a client can distinguish it from a transient failure."""
    from fastapi import HTTPException

    exc = HTTPException(status_code=409, detail={
        "error": "request_id_conflict",
        "request_id": "r-1",
        "detail": "this request ID was already used with a different "
                  "payload; mint a new ID for a new turn.",
    })
    assert exc.status_code == 409
    assert exc.detail["error"] == "request_id_conflict"


def test_pin_persistence_failure_is_explicit_and_never_re_executes(monkeypatch):
    """A pin that cannot be persisted after execution.

    The answer is still delivered — the turn already ran, and withholding
    it would punish the user for a bookkeeping failure — but the response
    must NOT claim durable replay protection, and the turn must not be
    executed again to reconstruct it.
    """
    from integrations import chat_routes as cr

    record = MagicMock()
    record.state = "in_progress"
    record.request_id = "r-pinfail"
    db = MagicMock()

    class _Resp:
        def __init__(self):
            self.metadata = {}

        def model_dump(self):
            return {"message": "the answer", "session_id": "s1",
                    "execution_id": "e1", "metadata": self.metadata}

    def _boom(*a, **k):
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(cr.chat_orchestrator, "conversation_sessions", {})
    import core.chat_transport as transport_mod
    monkeypatch.setattr(transport_mod, "complete", _boom)

    resp = _Resp()
    ok = cr._complete_transport_request(db, (record, "default"), resp)
    assert ok is False, "a failed pin must be reported as not durable"
    # The client is told, in the response it can see.
    pinned = resp.metadata["replay_pin"]
    assert pinned["status"] == "unavailable"
    assert pinned["durable"] is False
    # The record is annotated for an operator.
    assert record.error and "pin persistence failed" in record.error


def test_successful_pin_is_reported_durable(monkeypatch):
    from integrations import chat_routes as cr

    record = MagicMock()
    record.state = "in_progress"
    db = MagicMock()
    monkeypatch.setattr(cr.chat_orchestrator, "conversation_sessions", {})

    class _Resp:
        def __init__(self):
            self.metadata = {}

        def model_dump(self):
            return {"message": "a", "session_id": "s", "execution_id": "e",
                    "metadata": self.metadata}

    resp = _Resp()
    assert cr._complete_transport_request(db, (record, "default"), resp) is True
    assert resp.metadata["replay_pin"] == {"status": "pinned",
                                           "durable": True}


def test_unkeyed_request_reports_no_pin_requirement(monkeypatch):
    """No request id means no pin to lose; nothing is claimed either way."""
    from integrations import chat_routes as cr

    monkeypatch.setattr(cr.chat_orchestrator, "conversation_sessions", {})
    assert cr._complete_transport_request(MagicMock(), None, MagicMock()) is True
