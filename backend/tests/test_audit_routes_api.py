"""
Tests for the agent action audit read API (api/audit_routes.py).

Uses an in-memory SQLite database with the real AuditLog / AgentExecution
tables, exercising the endpoints through FastAPI's TestClient with auth
overridden.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.audit_routes import router
from api.audit_routes import get_db as route_get_db
from core.auth import get_current_user
from core.models import AgentExecution, AuditLog


@pytest.fixture
def audit_db():
    from sqlalchemy.pool import StaticPool

    # StaticPool: a single shared connection, otherwise each new connection
    # to the in-memory database sees a fresh empty schema.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    AuditLog.__table__.create(engine)
    AgentExecution.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def client(audit_db):
    app = FastAPI()
    app.include_router(router)

    mock_user = MagicMock()
    mock_user.id = "user-1"

    app.dependency_overrides[get_current_user] = lambda: mock_user
    # Key the override on the exact object the router bound at import time
    # (a conftest plugin may swap core.database.get_db afterwards, which
    # would make a late import a different object and silently no-op).
    app.dependency_overrides[route_get_db] = lambda: audit_db
    return TestClient(app)


def _mk_event(
    event_type="agent_action",
    action="tool:browser_navigate",
    execution_id="exec-1",
    agent_id="agent-1",
    success=True,
    ts=None,
    extra_meta=None,
):
    meta = {"agent_id": agent_id}
    if execution_id:
        meta["agent_execution_id"] = execution_id
    meta.update(extra_meta or {})
    return AuditLog(
        id=str(uuid.uuid4()),
        event_type=event_type,
        security_level="low",
        threat_level="none",
        timestamp=ts or datetime.now(timezone.utc),
        user_id="user-1",
        workspace_id="default",
        resource=agent_id,
        action=action,
        description=f"event {action}",
        metadata_json=json.dumps(meta),
        success=success,
    )


class TestEventsEndpoint:
    def test_lists_events_with_filters(self, client, audit_db):
        audit_db.add_all([
            _mk_event(action="tool:a", execution_id="e1", success=True),
            _mk_event(action="tool:b", execution_id="e1", success=False),
            _mk_event(event_type="llm_call", action="llm_call:gpt-4o", execution_id="e1"),
            _mk_event(action="tool:c", execution_id="e2", agent_id="agent-2"),
        ])
        audit_db.commit()

        resp = client.get("/api/audit/events")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 4

        resp = client.get("/api/audit/events", params={"success": "false"})
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["action"] == "tool:b"

        resp = client.get("/api/audit/events", params={"agent_id": "agent-2"})
        assert resp.json()["total"] == 1

        resp = client.get("/api/audit/events", params={"event_type": "llm_call"})
        assert resp.json()["total"] == 1

        resp = client.get("/api/audit/events", params={"execution_id": "e1"})
        assert resp.json()["total"] == 3

    def test_pagination(self, client, audit_db):
        audit_db.add_all([_mk_event(action=f"tool:t{i}") for i in range(5)])
        audit_db.commit()
        body = client.get("/api/audit/events", params={"limit": 2, "offset": 3}).json()
        assert len(body["items"]) == 2
        assert body["total"] == 5
        assert body["offset"] == 3


class TestExecutionTimeline:
    def test_full_timeline(self, client, audit_db):
        audit_db.add_all([
            _mk_event(action="execution_start", execution_id="e1",
                      extra_meta={"task_input": "close the books"}),
            _mk_event(action="tool:browser_navigate", execution_id="e1"),
            _mk_event(event_type="llm_call", action="llm_call:gpt-4o", execution_id="e1"),
            _mk_event(action="execution_complete", execution_id="e1",
                      extra_meta={"status": "success"}),
        ])
        audit_db.commit()

        resp = client.get("/api/audit/executions/e1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["found_events"] is True
        assert len(body["events"]) == 4
        assert body["counts"] == {"tool_calls": 1, "llm_calls": 1, "failed_events": 0}
        assert body["execution"]["status"] == "success"
        assert body["execution"]["task_input"] == "close the books"

    def test_unknown_execution_404(self, client):
        assert client.get("/api/audit/executions/nope").status_code == 404

    def test_falls_back_to_agent_execution_row(self, client, audit_db):
        audit_db.add(AgentExecution(
            id="legacy-1", agent_id="agent-9", status="success",
            input_summary="old run",
        ))
        audit_db.commit()
        resp = client.get("/api/audit/executions/legacy-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["found_events"] is False
        assert body["execution"]["input_summary"] == "old run"
        assert body["events"] == []


class TestExecutionList:
    def test_lists_runs_with_counts_and_status(self, client, audit_db):
        audit_db.add_all([
            _mk_event(action="execution_start", execution_id="e1",
                      extra_meta={"task_input": "task one"}),
            _mk_event(action="tool:a", execution_id="e1"),
            _mk_event(action="tool:b", execution_id="e1", success=False),
            _mk_event(action="execution_complete", execution_id="e1",
                      extra_meta={"status": "failed"}),
            _mk_event(action="execution_start", execution_id="e2"),
        ])
        audit_db.commit()

        body = client.get("/api/audit/executions").json()
        assert body["total"] == 2
        by_id = {item["execution_id"]: item for item in body["items"]}
        assert by_id["e1"]["status"] == "failed"
        assert by_id["e1"]["tool_calls"] == 2
        assert by_id["e1"]["failed_events"] == 1
        assert by_id["e1"]["task_input"] == "task one"
        assert by_id["e2"]["status"] == "running"

    def test_agent_filter(self, client, audit_db):
        audit_db.add_all([
            _mk_event(action="execution_start", execution_id="e1", agent_id="a1"),
            _mk_event(action="execution_start", execution_id="e2", agent_id="a2"),
        ])
        audit_db.commit()
        body = client.get("/api/audit/executions", params={"agent_id": "a1"}).json()
        assert body["total"] == 1
        assert body["items"][0]["execution_id"] == "e1"


class TestSummary:
    def test_summary_aggregates(self, client, audit_db):
        now = datetime.now(timezone.utc)
        audit_db.add_all([
            _mk_event(action="tool:a", execution_id="e1", ts=now),
            _mk_event(action="tool:a", execution_id="e1", success=False, ts=now),
            _mk_event(event_type="llm_call", action="llm_call:m", execution_id="e1", ts=now),
            _mk_event(action="execution_start", execution_id="e1", ts=now),
            # Outside the default 7-day window.
            _mk_event(action="tool:old", execution_id="e0", ts=now - timedelta(days=30)),
        ])
        audit_db.commit()

        body = client.get("/api/audit/summary").json()
        assert body["total_events"] == 4
        assert body["by_event_type"] == {"agent_action": 3, "llm_call": 1}
        assert body["failures"] == 1
        assert body["success_rate"] == 75.0
        assert body["executions_tracked"] == 1

    def test_summary_empty(self, client):
        body = client.get("/api/audit/summary").json()
        assert body["total_events"] == 0
        assert body["success_rate"] is None

def test_debug_override(audit_db, client):
    audit_db.add(_mk_event(action="tool:zz", execution_id="e9"))
    audit_db.commit()
    assert audit_db.query(AuditLog).count() == 1
    body = client.get("/api/audit/events").json()
    assert body["total"] == 1, f"expected 1 got {body['total']}"
