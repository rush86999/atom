# -*- coding: utf-8 -*-
"""Coverage wave 99 — api/reasoning_routes.py.

TestClient-based coverage of the Reasoning Audit surface:
- GET /api/reasoning/chain/{chain_id}: found (dataclass chain), not found
  (404), and **anonymous -> 401** (auth verified on every endpoint).
- POST /api/reasoning/feedback: thumbs_up/thumbs_down/comment payloads flow
  into AgentGovernanceService.submit_feedback, governance error -> 500,
  missing fields -> 422, and **anonymous -> 401**.

No LLM spend, no network; the governance service is mocked at the class
level and the reasoning tracker at the module level.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.reasoning_routes import router
from core.auth import get_current_user
from core.database import get_db
from core.reasoning_chain import (
    ReasoningChain,
    ReasoningStep,
    ReasoningStepType,
)


@pytest.fixture()
def user():
    u = MagicMock()
    u.id = "user-1"
    return u


@pytest.fixture()
def app(user):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = lambda: user
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def anon_app():
    """App WITHOUT the get_current_user override — real 401 checks."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
def anon_client(anon_app):
    return TestClient(anon_app)


def _chain(chain_id="chain-1"):
    step = ReasoningStep(
        id="step-1",
        agent_id="agent-1",
        step_type=ReasoningStepType.DECISION,
        description="thinking",
        inputs={},
        outputs={},
        confidence=0.9,
        duration_ms=1.0,
        timestamp=datetime.now(timezone.utc),
    )
    return ReasoningChain(
        execution_id=chain_id,
        started_at=datetime.now(timezone.utc),
        steps=[step],
    )


def _feedback_payload(**overrides):
    payload = {
        "agent_id": "agent-1",
        "run_id": "run-1",
        "step_index": 2,
        "step_content": {"thought": "check the ledger", "action": "query"},
        "feedback_type": "thumbs_up",
    }
    payload.update(overrides)
    return payload


# ============================================================================
# GET /api/reasoning/chain/{chain_id}
# ============================================================================

class TestGetReasoningChain:
    def test_chain_found(self, client, user):
        tracker = MagicMock()
        tracker.get_chain.return_value = _chain()
        with patch("core.reasoning_chain.get_reasoning_tracker", return_value=tracker):
            resp = client.get("/api/reasoning/chain/chain-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["execution_id"] == "chain-1"
        assert len(data["steps"]) == 1
        tracker.get_chain.assert_called_once_with("chain-1")

    def test_chain_not_found(self, client, user):
        tracker = MagicMock()
        tracker.get_chain.return_value = None
        with patch("core.reasoning_chain.get_reasoning_tracker", return_value=tracker):
            resp = client.get("/api/reasoning/chain/nope")
        assert resp.status_code == 404
        body = resp.json()
        detail = body["detail"]
        assert detail["success"] is False
        assert "not found" in detail["error"]["message"].lower()

    def test_chain_anonymous_401(self, anon_client):
        resp = anon_client.get("/api/reasoning/chain/chain-1")
        assert resp.status_code == 401


# ============================================================================
# POST /api/reasoning/feedback
# ============================================================================

class TestSubmitStepFeedback:
    @pytest.fixture()
    def app(self, user):
        # The /feedback idempotency guard queries AgentFeedback.first() —
        # the shared fixture's bare MagicMock reads as "duplicate" and
        # short-circuits submissions before governance runs.
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: user
        yield app
        app.dependency_overrides.clear()

    def test_thumbs_up_success(self, client, user):
        gov = MagicMock()
        gov.submit_feedback = AsyncMock(return_value=MagicMock(id="fb-1"))
        with patch("api.reasoning_routes.AgentGovernanceService", return_value=gov):
            resp = client.post("/api/reasoning/feedback", json=_feedback_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["id"] == "fb-1"
        call_kwargs = gov.submit_feedback.call_args.kwargs
        assert call_kwargs["agent_id"] == "agent-1"
        assert call_kwargs["user_id"] == "user-1"
        assert call_kwargs["user_correction"] == "thumbs_up"
        assert call_kwargs["original_output"] == '"check the ledger"'
        assert call_kwargs["input_context"] is not None

    def test_thumbs_down_with_comment_uses_comment(self, client, user):
        gov = MagicMock()
        gov.submit_feedback = AsyncMock(return_value=MagicMock(id="fb-2"))
        with patch("api.reasoning_routes.AgentGovernanceService", return_value=gov):
            resp = client.post(
                "/api/reasoning/feedback",
                json=_feedback_payload(feedback_type="thumbs_down",
                                       comment="wrong channel"),
            )
        assert resp.status_code == 200
        assert gov.submit_feedback.call_args.kwargs["user_correction"] == "wrong channel"

    def test_missing_thought_defaults_empty(self, client, user):
        gov = MagicMock()
        gov.submit_feedback = AsyncMock(return_value=MagicMock(id="fb-3"))
        with patch("api.reasoning_routes.AgentGovernanceService", return_value=gov):
            resp = client.post(
                "/api/reasoning/feedback",
                json=_feedback_payload(step_content={"action": "no thought"}),
            )
        assert resp.status_code == 200
        assert gov.submit_feedback.call_args.kwargs["original_output"] == '""'

    def test_governance_error_returns_500(self, client, user):
        gov = MagicMock()
        gov.submit_feedback = AsyncMock(side_effect=RuntimeError("governance down"))
        with patch("api.reasoning_routes.AgentGovernanceService", return_value=gov):
            resp = client.post("/api/reasoning/feedback", json=_feedback_payload())
        assert resp.status_code == 500
        body = resp.json()
        detail = body["detail"]
        assert detail["success"] is False
        assert "Internal error" in detail["error"]["message"]

    def test_missing_required_fields_422(self, client, user):
        resp = client.post("/api/reasoning/feedback", json={"agent_id": "a"})
        assert resp.status_code == 422

    def test_feedback_anonymous_401(self, anon_client):
        resp = anon_client.post("/api/reasoning/feedback", json=_feedback_payload())
        assert resp.status_code == 401
