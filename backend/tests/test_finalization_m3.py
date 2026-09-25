from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.async_turn_continuation import (
    AsyncTurnContinuation,
    _apply_effects,
    _finish_durable_record,
)


@pytest.fixture
def database(monkeypatch):
    from core import database as database_module
    from core.models_registration import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def get_db_session():
        db = factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    monkeypatch.setattr(database_module, "get_db_session", get_db_session)
    yield factory
    engine.dispose()


def _cont(continuation_id="cont-1", execution_id="exec-1", outcome="applied"):
    cont = AsyncTurnContinuation(
        continuation_id=continuation_id,
        user_id="user-1",
        session_id="session-1",
        message="rebuild the draft",
        canvas={"canvas_id": "canvas-1", "canvas_type": "email", "content": {"body": "x"}},
        execution_id=execution_id,
        agent_id=None,
        history_snapshot=[],
    )
    cont.outcome = outcome
    cont.summary = "edit applied"
    return cont


def _seed_execution(factory, continuation_id):
    from core.models import AgentExecution

    with factory() as db:
        db.add(
            AgentExecution(
                id=continuation_id,
                status="running",
                triggered_by="continuation",
                started_at=datetime.now(timezone.utc),
                metadata_json={"continuation": {}},
            )
        )
        db.commit()


def _continuation_meta(factory, continuation_id):
    from core.models import AgentExecution

    with factory() as db:
        row = db.query(AgentExecution).filter(AgentExecution.id == continuation_id).first()
        return dict((row.metadata_json or {}).get("continuation") or {})


class _BroadcastStub:
    def __init__(self):
        self.events = []

    async def broadcast_event(self, channel, event_type, payload):
        self.events.append((channel, event_type, payload))


@pytest.fixture
def broadcast(monkeypatch):
    import core.websockets as websockets_module

    stub = _BroadcastStub()
    monkeypatch.setattr(websockets_module, "get_connection_manager", lambda: stub)
    return stub


def _notify_stub(monkeypatch, success):
    import core.notification_service as notification_module

    calls = []

    class _Service:
        async def send_notification(self, user_id, ntype, data):
            calls.append((user_id, ntype, data))
            return {"success": success, "notification_id": "n-1"}

    monkeypatch.setattr(notification_module, "NotificationService", _Service)
    return calls


def test_m3_off_keeps_legacy_notified_stamp(monkeypatch, database):
    monkeypatch.delenv("CHAT_FINALIZATION_M3", raising=False)
    _seed_execution(database, "cont-1")

    _finish_durable_record(_cont(), "applied", "edit applied")

    assert _continuation_meta(database, "cont-1").get("notified") is True


def test_m3_on_leaves_notified_unset_until_delivery(monkeypatch, database):
    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    _seed_execution(database, "cont-1")

    _finish_durable_record(_cont(), "applied", "edit applied")

    assert "notified" not in _continuation_meta(database, "cont-1")


@pytest.mark.asyncio
async def test_m3_delivery_binds_execution_and_marks_notified(monkeypatch, database, broadcast):
    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    _seed_execution(database, "cont-1")
    _notify_stub(monkeypatch, True)

    await _apply_effects(_cont())

    meta = _continuation_meta(database, "cont-1")
    assert meta.get("notified") is True
    assert broadcast.events
    _, event_type, payload = broadcast.events[-1]
    assert event_type == "chat_continuation"
    assert payload["originating_execution_id"] == "exec-1"
    assert payload["status"] == "applied"


@pytest.mark.asyncio
async def test_m3_failed_delivery_keeps_history_but_not_notified(monkeypatch, database, broadcast):
    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    _seed_execution(database, "cont-1")
    calls = _notify_stub(monkeypatch, False)

    await _apply_effects(_cont())

    assert calls
    assert "notified" not in _continuation_meta(database, "cont-1")


@pytest.mark.asyncio
async def test_m3_durable_row_carries_origin_binding(monkeypatch, database, broadcast):
    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    _notify_stub(monkeypatch, True)
    from core.models import ChatMessage

    await _apply_effects(_cont())

    with database() as db:
        rows = db.query(ChatMessage).filter(ChatMessage.role == "assistant").all()
    assert len(rows) == 1
    import json as _json

    meta = _json.loads(rows[0].metadata_json or "{}")
    assert meta["continuation"]["originating_execution_id"] == "exec-1"


@pytest.fixture
def verify_db(monkeypatch):
    from core import database as database_module
    from core.models_registration import Base
    from sqlalchemy import create_engine as _create_engine
    from sqlalchemy.orm import sessionmaker as _sessionmaker
    from sqlalchemy.pool import StaticPool as _StaticPool

    engine = _create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=_StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = _sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def get_db_session():
        db = factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    monkeypatch.setattr(database_module, "get_db_session", get_db_session)
    yield factory
    engine.dispose()


@pytest.mark.asyncio
async def test_m3b_flag_off_never_reconciles(monkeypatch, verify_db):
    from integrations.chat_orchestrator import ChatOrchestrator

    monkeypatch.delenv("CHAT_FINALIZATION_M3", raising=False)
    out = await ChatOrchestrator._m3_reconcile_stream_done(
        "I've updated item 4 to reflect that pricing.",
        {"canvas_id": "canvas-1"},
        "session-1",
        "user-1",
        False,
        execution_id="execution-1",
    )
    assert out is None


@pytest.mark.asyncio
async def test_m3b_unbacked_claim_reconciles_stream_close(monkeypatch, verify_db):
    from integrations.chat_orchestrator import ChatOrchestrator

    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    out = await ChatOrchestrator._m3_reconcile_stream_done(
        "I've updated item 4 to reflect that pricing.",
        {"canvas_id": "canvas-1"},
        "session-1",
        "user-1",
        False,
        execution_id="execution-1",
    )
    assert out is not None
    assert "I've updated item 4" not in out
    assert "Unverified" in out


@pytest.mark.asyncio
async def test_m3b_claim_free_stream_keeps_legacy_empty(monkeypatch, verify_db):
    from integrations.chat_orchestrator import ChatOrchestrator

    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    out = await ChatOrchestrator._m3_reconcile_stream_done(
        "The price is 8880.",
        {"canvas_id": "canvas-1"},
        "session-1",
        "user-1",
        False,
        execution_id="execution-1",
    )
    assert out is None


@pytest.mark.asyncio
async def test_m3b_correction_failure_keeps_legacy_empty(monkeypatch, verify_db):
    from unittest.mock import patch

    from integrations.chat_orchestrator import ChatOrchestrator

    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    with patch.object(
        ChatOrchestrator,
        "_canvas_claim_correction",
        side_effect=RuntimeError("guard down"),
    ):
        out = await ChatOrchestrator._m3_reconcile_stream_done(
            "I've updated item 4 to reflect that pricing.",
            {"canvas_id": "canvas-1"},
            "session-1",
            "user-1",
            False,
            execution_id="execution-1",
        )
    assert out is None
