from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.finalization import UNKNOWN_OUTCOME_MESSAGE
from core.models import AgentExecution
from core.models_registration import Base
from core.security_dependencies import get_current_user
from integrations import chat_routes as cr
from integrations.chat_routes import (
    ChatMessageResponse,
    _finalize_chat_response,
)


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


def _failed_execution(execution_id, summary, session_id="session-1"):
    return AgentExecution(
        id=execution_id,
        status="failed",
        started_at=datetime.now(timezone.utc),
        result_summary=summary,
        metadata_json={"session_id": session_id},
    )


def test_m1_seam_leaves_default_path_untouched(monkeypatch, session):
    monkeypatch.delenv("CHAT_FINALIZATION_M1", raising=False)
    response = {"success": True, "message": "hello", "session_id": "session-1"}

    assert _finalize_chat_response(session, response) is response
    assert "baseline_id" not in response
    assert "error_code" not in response


def test_m1_seam_binds_overlapping_turns_by_exact_id(monkeypatch, session):
    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")
    session.add(_failed_execution("execution-a", "failure A"))
    session.add(_failed_execution("execution-b", "failure B"))
    session.commit()

    first = _finalize_chat_response(
        session,
        {
            "success": False,
            "message": "Message processed successfully",
            "session_id": "session-1",
            "execution_id": "execution-a",
            "data": {},
        },
    )
    second = _finalize_chat_response(
        session,
        {
            "success": False,
            "message": "Message processed successfully",
            "session_id": "session-1",
            "execution_id": "execution-b",
            "data": {},
        },
    )

    assert first["execution_id"] == "execution-a"
    assert "failure A" in first["message"]
    assert "failure B" not in first["message"]
    assert second["execution_id"] == "execution-b"
    assert "failure B" in second["message"]
    assert "failure A" not in second["message"]


def test_m1_seam_never_borrows_another_turn_row(monkeypatch, session):
    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")
    session.add(_failed_execution("execution-b", "failure B"))
    session.commit()

    result = _finalize_chat_response(
        session,
        {
            "success": False,
            "message": "Message processed successfully",
            "session_id": "session-1",
            "execution_id": "execution-a",
            "data": {},
        },
    )

    assert result["execution_id"] == "execution-a"
    assert result["success"] is False
    assert result["message"] == UNKNOWN_OUTCOME_MESSAGE
    assert "failure B" not in result["message"]


def test_m1_seam_marks_missing_identity_unverified(monkeypatch, session):
    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")

    result = _finalize_chat_response(
        session,
        {
            "success": True,
            "message": "Message processed successfully",
            "session_id": "session-1",
        },
    )

    assert result["success"] is False
    assert result["message"] == UNKNOWN_OUTCOME_MESSAGE
    assert "execution_id" not in result


def test_m1_seam_fails_closed_on_lookup_failure(monkeypatch):
    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")

    class _BrokenSession:
        def query(self, *args, **kwargs):
            raise RuntimeError("database unavailable")

    result = _finalize_chat_response(
        _BrokenSession(),
        {
            "success": True,
            "message": "All requested checks are complete.",
            "session_id": "session-1",
            "execution_id": "execution-1",
        },
    )

    assert result["success"] is False
    assert result["execution_id"] == "execution-1"
    assert result["session_id"] == "session-1"
    assert result["message"] == UNKNOWN_OUTCOME_MESSAGE


def test_m1_production_response_carries_no_baseline():
    assert "baseline_id" not in ChatMessageResponse.model_fields


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(cr.router)
    return application


@pytest.fixture
def client(app):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="user_1", tenant_id="t1")
    return TestClient(app)


@pytest.fixture
def orch():
    with patch.object(cr, "chat_orchestrator") as m:
        m.session_manager = MagicMock()
        yield m


@pytest.fixture
def exec_db(monkeypatch):
    from sqlalchemy import create_engine as _create_engine
    from sqlalchemy.orm import sessionmaker as _sessionmaker
    from sqlalchemy.pool import StaticPool as _StaticPool

    from core import database as _database_module
    from core.models_registration import Base as _Base

    engine = _create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=_StaticPool,
    )
    _Base.metadata.create_all(engine)
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

    monkeypatch.setattr(_database_module, "get_db_session", get_db_session)
    yield factory
    engine.dispose()


def _failed_row(factory, execution_id, metadata=None):
    from datetime import datetime, timezone

    from core.models import AgentExecution

    with factory() as db:
        db.add(
            AgentExecution(
                id=execution_id,
                status="failed",
                started_at=datetime.now(timezone.utc),
                result_summary="editor failed",
                metadata_json=(metadata if metadata is not None else {"session_id": "session-1"}),
            )
        )
        db.commit()


def _stored_operations(factory, execution_id):
    from core.execution_outcome import STORAGE_KEY
    from core.models import AgentExecution

    with factory() as db:
        row = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
        meta = row.metadata_json if isinstance(row.metadata_json, dict) else {}
        stored = meta.get(STORAGE_KEY) or {}
        return stored.get("operations") or {}


def test_m4_failed_turn_persists_delivery_record(monkeypatch, exec_db):
    from integrations.chat_routes import _finalize_chat_response

    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")
    _failed_row(exec_db, "execution-1")
    with exec_db() as db:
        result = _finalize_chat_response(
            db,
            {
                "success": False,
                "message": "Message processed successfully",
                "session_id": "session-1",
                "execution_id": "execution-1",
                "data": {},
            },
        )

    assert result["success"] is False
    assert "editor failed" in result["message"]
    operations = _stored_operations(exec_db, "execution-1")
    assert operations["execution-1"]["execution_status"] == "failed"
    assert operations["execution-1"]["delivery_status"] == "delivered"


def test_m4_sibling_operations_coexist(monkeypatch, exec_db):
    from integrations.chat_routes import _finalize_chat_response

    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")
    _failed_row(exec_db, "execution-a")
    _failed_row(exec_db, "execution-b")
    with exec_db() as db:
        _finalize_chat_response(
            db,
            {
                "success": False,
                "message": "Message processed successfully",
                "session_id": "session-1",
                "execution_id": "execution-a",
                "data": {},
            },
        )
    with exec_db() as db:
        _finalize_chat_response(
            db,
            {
                "success": False,
                "message": "Message processed successfully",
                "session_id": "session-1",
                "execution_id": "execution-b",
                "data": {},
            },
        )

    assert set(_stored_operations(exec_db, "execution-a")) == {"execution-a"}
    assert set(_stored_operations(exec_db, "execution-b")) == {"execution-b"}


def test_m4_unmapped_row_status_falls_back_to_finalized_outcome(monkeypatch, exec_db):
    from integrations.chat_routes import _finalize_chat_response

    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")
    _failed_row(exec_db, "execution-1")
    with exec_db() as db:
        from core.models import AgentExecution

        row = db.query(AgentExecution).filter(AgentExecution.id == "execution-1").first()
        row.status = "success"
        db.commit()
        result = _finalize_chat_response(
            db,
            {
                "success": True,
                "message": "done",
                "session_id": "session-1",
                "execution_id": "execution-1",
                "data": {},
            },
        )

    assert result["success"] is True
    assert _stored_operations(exec_db, "execution-1")["execution-1"]["execution_status"] == "succeeded"


def test_m4_flag_off_writes_no_record(monkeypatch, exec_db):
    from integrations.chat_routes import _finalize_chat_response

    monkeypatch.delenv("CHAT_FINALIZATION_M1", raising=False)
    _failed_row(exec_db, "execution-1")
    with exec_db() as db:
        result = _finalize_chat_response(
            db,
            {
                "success": False,
                "message": "Message processed successfully",
                "session_id": "session-1",
                "execution_id": "execution-1",
                "data": {},
            },
        )

    assert result["message"] == "Message processed successfully"
    assert _stored_operations(exec_db, "execution-1") == {}


def test_m4_corrupt_metadata_is_never_rewritten(monkeypatch, exec_db):
    from integrations.chat_routes import _finalize_chat_response

    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")
    _failed_row(exec_db, "execution-1", metadata="not-json{{{")
    with exec_db() as db:
        result = _finalize_chat_response(
            db,
            {
                "success": False,
                "message": "Message processed successfully",
                "session_id": "session-1",
                "execution_id": "execution-1",
                "data": {},
            },
        )

    assert "editor failed" in result["message"]
    from core.models import AgentExecution

    with exec_db() as db:
        row = db.query(AgentExecution).filter(AgentExecution.id == "execution-1").first()
        assert row.metadata_json == "not-json{{{"
        assert _stored_operations(exec_db, "execution-1") == {}


def test_m1_turn_budget_early_return_bypasses_finalizer(monkeypatch, client, orch):
    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")
    orch.process_chat_message = AsyncMock(
        return_value={
            "success": False,
            "message": "This turn ran past its time budget.",
            "session_id": "session-1",
            "execution_id": "execution-1",
            "error_code": "turn_budget_exceeded",
        }
    )

    body = client.post("/api/chat/message", json={"message": "hi", "user_id": "u"}).json()

    assert body["error_code"] == "turn_budget_exceeded"
    assert body["message"] == "This turn ran past its time budget."
    assert "This turn failed" not in body["message"]
