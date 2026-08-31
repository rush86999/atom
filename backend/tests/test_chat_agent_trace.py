# -*- coding: utf-8 -*-
"""Chat agent-trace: session-linked execution traces + step feedback write-through.

Covers the pipeline that feeds the Agent Workspace panel:
- ChatOrchestrator._normalize_step_record — `output` → `observation` payload
  normalization the UI depends on
- GET /api/chat/trace/{session_id} — history restore of persisted runs joined
  to their chat session via AgentExecution.metadata_json
- POST /api/reasoning/feedback — write-through of thumbs polarity onto
  AgentReasoningStep.feedback_score so training consumers can query it

Zero network, zero LLM spend; DB is the shared in-memory SQLite factory.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from integrations.chat_routes import router as chat_router
from integrations.chat_routes import chat_orchestrator
from api.reasoning_routes import router as reasoning_router


SESSION_ID = "sess-trace-1"
EXEC_ID = "exec-trace-1"

_seed_counter = {"n": 0}


def _seed_run(db, execution_id=EXEC_ID, session_id=SESSION_ID, status="completed"):
    """Seed one execution + two reasoning steps; returns the execution id.

    The worker DB is session-scoped, so callers that don't pass an explicit
    id get a unique one to avoid cross-test UNIQUE collisions.
    """
    from core.models import AgentExecution, AgentReasoningStep

    if execution_id == EXEC_ID:
        _seed_counter["n"] += 1
        execution_id = f"{EXEC_ID}-{_seed_counter['n']}"

    execution = AgentExecution(
        id=execution_id,
        agent_id="atom_main",
        tenant_id="default",
        status=status,
        input_summary="research competitors",
        triggered_by="manual",
        started_at=datetime.now(timezone.utc),
        metadata_json={"session_id": session_id, "channel": "chat"},
    )
    db.add(execution)
    db.flush()
    db.add_all([
        AgentReasoningStep(
            execution_id=execution_id,
            step_number=1,
            step_type="action",
            thought="Planning the research",
            action={"tool": "web_search", "params": {"query": "competitors"}},
            observation="Found 3 competitor reports",
            confidence=0.92,
            verified="verified",
            duration_ms=810.0,
            resolved_model="qwen-max",
        ),
        AgentReasoningStep(
            execution_id=execution_id,
            step_number=2,
            step_type="final_answer",
            thought=None,
            action=None,
            observation="Compiled the competitive landscape summary",
            confidence=0.88,
            verified="unverified",
            duration_ms=240.0,
        ),
    ])
    db.commit()
    return execution_id


@pytest.fixture
def app():
    a = FastAPI()
    a.include_router(chat_router)
    a.include_router(reasoning_router)
    return a


@pytest.fixture
def client(app, worker_database):
    from core.auth import get_current_user
    from core.database import get_db

    user = MagicMock()
    user.id = "trace-user-1"

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


# ============================================================================
# Payload normalization
# ============================================================================

class TestNormalizeStepRecord:
    def test_output_becomes_observation(self):
        from integrations.chat_orchestrator import ChatOrchestrator

        step = ChatOrchestrator._normalize_step_record({
            "step": 2, "thought": "t", "action": "a", "output": "result text",
        })
        assert step["observation"] == "result text"
        assert step["output"] == "result text"  # original key preserved
        assert step["timestamp"]  # stamped for the UI
        assert step["action_input"] == ""

    def test_observation_wins_and_none_record_tolerated(self):
        from integrations.chat_orchestrator import ChatOrchestrator

        step = ChatOrchestrator._normalize_step_record({
            "step": 1, "observation": "obs", "output": "ignored",
        })
        assert step["observation"] == "obs"
        assert ChatOrchestrator._normalize_step_record(None)["observation"] == ""


# ============================================================================
# GET /api/chat/trace/{session_id}
# ============================================================================

class TestSessionTraceEndpoint:
    def test_empty_session_returns_no_runs(self, client):
        resp = client.get(f"/api/chat/trace/{SESSION_ID}-unknown")
        assert resp.status_code == 200
        assert resp.json()["runs"] == []

    def test_returns_runs_with_steps_in_order(self, client, worker_database):
        db = worker_database()
        exec_id = _seed_run(db)
        try:
            resp = client.get(f"/api/chat/trace/{SESSION_ID}")
            assert resp.status_code == 200
            body = resp.json()
            assert len(body["runs"]) == 1
            run = body["runs"][0]
            assert run["execution_id"] == exec_id
            assert run["agent_id"] == "atom_main"
            assert run["input_summary"] == "research competitors"
            assert len(run["steps"]) == 2
            first, second = run["steps"]
            assert first["step_number"] == 1
            assert first["thought"] == "Planning the research"
            # action dict {tool, params} is split into the UI's string shape
            assert first["action"] == "web_search"
            assert "competitors" in first["action_input"]
            assert first["verified"] == "verified"
            assert first["resolved_model"] == "qwen-max"
            assert second["step_number"] == 2
            assert second["feedback_score"] is None
        finally:
            db.close()

    def test_other_users_session_denied(self, client):
        chat_orchestrator.conversation_sessions[SESSION_ID] = {
            "id": SESSION_ID, "user_id": "owner-user", "history": [],
        }
        try:
            resp = client.get(f"/api/chat/trace/{SESSION_ID}")
            assert resp.status_code == 403
        finally:
            del chat_orchestrator.conversation_sessions[SESSION_ID]

    def test_unauthenticated_rejected(self, app, worker_database):
        client = TestClient(app)
        resp = client.get(f"/api/chat/trace/{SESSION_ID}")
        assert resp.status_code == 401


# ============================================================================
# POST /api/reasoning/feedback — write-through onto AgentReasoningStep
# ============================================================================

class TestFeedbackWriteThrough:
    def _post(self, client, exec_id, **overrides):
        payload = {
            "agent_id": "atom_main",
            "run_id": exec_id,
            "step_index": 0,
            "step_content": {"thought": "Planning the research"},
            "feedback_type": "thumbs_up",
            "comment": "great plan",
            "execution_id": exec_id,
            "step_number": 1,
        }
        payload.update(overrides)
        with patch("api.reasoning_routes.AgentGovernanceService") as gov_cls:
            gov = MagicMock()
            feedback_row = MagicMock()
            feedback_row.id = "fb-1"
            gov.submit_feedback = AsyncMock(return_value=feedback_row)
            gov_cls.return_value = gov
            resp = client.post("/api/reasoning/feedback", json=payload)
        return resp

    def test_thumbs_up_stamped_on_step_row(self, client, worker_database):
        db = worker_database()
        exec_id = _seed_run(db)
        try:
            resp = self._post(client, exec_id)
            assert resp.status_code == 200
            from core.models import AgentReasoningStep

            row = (
                db.query(AgentReasoningStep)
                .filter(
                    AgentReasoningStep.execution_id == exec_id,
                    AgentReasoningStep.step_number == 1,
                )
                .first()
            )
            assert row.feedback_score == 1
            assert row.feedback_text == "great plan"
            # Sibling steps untouched
            other = (
                db.query(AgentReasoningStep)
                .filter(
                    AgentReasoningStep.execution_id == exec_id,
                    AgentReasoningStep.step_number == 2,
                )
                .first()
            )
            assert other.feedback_score is None
        finally:
            db.close()

    def test_thumbs_down_sets_negative_score(self, client, worker_database):
        db = worker_database()
        exec_id = _seed_run(db)
        try:
            resp = self._post(
                client, exec_id, feedback_type="thumbs_down", comment=None, step_number=2
            )
            assert resp.status_code == 200
            from core.models import AgentReasoningStep

            row = (
                db.query(AgentReasoningStep)
                .filter(
                    AgentReasoningStep.execution_id == exec_id,
                    AgentReasoningStep.step_number == 2,
                )
                .first()
            )
            assert row.feedback_score == -1
            assert row.feedback_text is None  # no comment → text untouched
        finally:
            db.close()

    def test_unknown_step_still_succeeds(self, client):
        resp = self._post(client, "ghost-exec")
        assert resp.status_code == 200

    def test_without_execution_ids_skips_write_through(self, client, worker_database):
        db = worker_database()
        exec_id = _seed_run(db)
        try:
            resp = self._post(client, exec_id, execution_id=None, step_number=None)
            assert resp.status_code == 200
            from core.models import AgentReasoningStep

            rows = (
                db.query(AgentReasoningStep)
                .filter(AgentReasoningStep.execution_id == exec_id)
                .all()
            )
            assert all(r.feedback_score is None for r in rows)
        finally:
            db.close()
