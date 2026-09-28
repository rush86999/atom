from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.execution_outcome import STORAGE_KEY
from integrations.chat_orchestrator import ChatOrchestrator


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


@pytest.fixture
def orch():
    orchestrator = ChatOrchestrator.__new__(ChatOrchestrator)
    orchestrator.tenant_id = "default"
    return orchestrator


def _operations(factory, execution_id):
    from core.models import AgentExecution

    with factory() as db:
        row = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
        meta = row.metadata_json if isinstance(row.metadata_json, dict) else {}
        stored = meta.get(STORAGE_KEY) or {}
        return stored.get("operations") or {}


def test_m4_start_opens_running_record(monkeypatch, database, orch):
    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")

    execution_id = orch._start_chat_execution("session-1", None, "hi", user_id="u1")

    assert execution_id
    record = _operations(database, execution_id)[execution_id]
    assert record["execution_status"] == "running"
    assert [t["to"] for t in record["transitions"]] == ["running"]


def test_m4_finish_success_closes_record(monkeypatch, database, orch):
    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")
    execution_id = orch._start_chat_execution("session-1", None, "hi", user_id="u1")

    orch._finish_chat_execution(execution_id, "success", "done")

    record = _operations(database, execution_id)[execution_id]
    assert record["execution_status"] == "succeeded"
    assert [t["to"] for t in record["transitions"]] == ["running", "succeeded"]


def test_m4_finish_failed_without_start_record(monkeypatch, database, orch):
    from datetime import datetime, timezone

    from core.models import AgentExecution

    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")
    with database() as db:
        db.add(AgentExecution(id="exec-9", status="running", started_at=datetime.now(timezone.utc)))
        db.commit()

    orch._finish_chat_execution("exec-9", "failed", "boom")

    record = _operations(database, "exec-9")["exec-9"]
    assert record["execution_status"] == "failed"


def test_m4_terminal_record_rejects_rewrite(monkeypatch, database, orch):
    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")
    execution_id = orch._start_chat_execution("session-1", None, "hi", user_id="u1")
    orch._finish_chat_execution(execution_id, "success", "done")

    orch._finish_chat_execution(execution_id, "failed", "late failure")

    record = _operations(database, execution_id)[execution_id]
    assert record["execution_status"] == "succeeded"


def test_m4_unmapped_status_leaves_record_open(monkeypatch, database, orch):
    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")
    execution_id = orch._start_chat_execution("session-1", None, "hi", user_id="u1")

    orch._finish_chat_execution(execution_id, "cancelled", "stopped")

    record = _operations(database, execution_id)[execution_id]
    assert record["execution_status"] == "running"


def test_m4_flag_off_writes_no_record(monkeypatch, database, orch):
    monkeypatch.delenv("CHAT_FINALIZATION_M1", raising=False)
    execution_id = orch._start_chat_execution("session-1", None, "hi", user_id="u1")
    orch._finish_chat_execution(execution_id, "success", "done")

    assert _operations(database, execution_id) == {}


def test_m4_corrupt_metadata_is_never_rewritten(monkeypatch, database, orch):
    from datetime import datetime, timezone

    from core.models import AgentExecution

    monkeypatch.setenv("CHAT_FINALIZATION_M1", "1")
    with database() as db:
        db.add(
            AgentExecution(
                id="exec-9", status="running", started_at=datetime.now(timezone.utc), metadata_json="not-json{{{"
            )
        )
        db.commit()

    orch._finish_chat_execution("exec-9", "failed", "boom")

    with database() as db:
        row = db.query(AgentExecution).filter(AgentExecution.id == "exec-9").first()
        assert row.metadata_json == "not-json{{{"
    assert _operations(database, "exec-9") == {}
