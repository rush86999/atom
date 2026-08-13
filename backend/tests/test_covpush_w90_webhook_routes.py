"""Coverage wave 90 — api/webhook_routes.py (59% → 95%+).

External-ingestion surface. Teams/Gmail verified: shared-secret Bearer
dependency fails CLOSED (401 when env unset / token wrong / missing).
Slack passes through to the processor (handler does HMAC verification
itself) including the URL-verification challenge echo. Health endpoint
covered. All processor calls mocked — zero network.
"""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.webhook_routes as wr


@pytest.fixture
def mock_processor():
    proc = MagicMock()
    proc.process_slack_webhook = AsyncMock(return_value={"status": "success"})
    proc.process_teams_webhook = AsyncMock(return_value={"status": "success"})
    proc.process_gmail_webhook = AsyncMock(return_value={"status": "success"})
    proc.processed_events = {}
    return proc


@pytest.fixture
def client(mock_processor):
    app = FastAPI()
    app.include_router(wr.router)
    with patch.object(wr, "webhook_processor", mock_processor):
        yield TestClient(app)


class TestSlack:
    def test_slack_passthrough_success(self, client, mock_processor):
        resp = client.post(
            "/api/webhooks/slack",
            content='{"type": "event_callback"}',
            headers={
                "X-Slack-Request-Timestamp": "1700000000",
                "X-Slack-Signature": "v0=abc",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        mock_processor.process_slack_webhook.assert_awaited_once()

    def test_slack_url_verification_challenge(self, client, mock_processor):
        mock_processor.process_slack_webhook.return_value = {"challenge": "xyz123"}
        resp = client.post("/api/webhooks/slack", content='{"challenge": "xyz123"}')
        assert resp.status_code == 200
        assert resp.json() == {"challenge": "xyz123"}

    def test_slack_no_challenge_returns_plain_result(self, client, mock_processor):
        mock_processor.process_slack_webhook.return_value = {"status": "ignored"}
        resp = client.post("/api/webhooks/slack", content="{}")
        assert resp.json() == {"status": "ignored"}


class TestTeamsSecret:
    def test_teams_fails_closed_without_secret(self, client):
        with patch.dict(os.environ, {}, clear=True):
            resp = client.post("/api/webhooks/teams", json={})
        assert resp.status_code == 401
        assert "not configured" in resp.json()["detail"]

    def test_teams_rejects_wrong_token(self, client):
        with patch.dict(os.environ, {"ATOM_TEAMS_WEBHOOK_SECRET": "correct"}):
            resp = client.post(
                "/api/webhooks/teams",
                json={},
                headers={"Authorization": "Bearer wrong"},
            )
        assert resp.status_code == 401
        assert "Invalid webhook token" in resp.json()["detail"]

    def test_teams_rejects_missing_header(self, client):
        with patch.dict(os.environ, {"ATOM_TEAMS_WEBHOOK_SECRET": "correct"}):
            resp = client.post("/api/webhooks/teams", json={})
        assert resp.status_code == 401

    def test_teams_success_with_valid_token(self, client, mock_processor):
        with patch.dict(os.environ, {"ATOM_TEAMS_WEBHOOK_SECRET": "correct"}):
            resp = client.post(
                "/api/webhooks/teams",
                json={},
                headers={"Authorization": "Bearer correct"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        mock_processor.process_teams_webhook.assert_awaited_once()

    def test_teams_token_whitespace_stripped(self, client):
        with patch.dict(os.environ, {"ATOM_TEAMS_WEBHOOK_SECRET": "correct"}):
            resp = client.post(
                "/api/webhooks/teams",
                json={},
                headers={"Authorization": "   Bearer correct   "},
            )
        assert resp.status_code == 200


class TestGmailSecret:
    def test_gmail_fails_closed_without_secret(self, client):
        with patch.dict(os.environ, {}, clear=True):
            resp = client.post("/api/webhooks/gmail", json={})
        assert resp.status_code == 401

    def test_gmail_rejects_wrong_token(self, client):
        with patch.dict(os.environ, {"ATOM_GMAIL_WEBHOOK_SECRET": "correct"}):
            resp = client.post(
                "/api/webhooks/gmail",
                json={},
                headers={"Authorization": "Bearer nope"},
            )
        assert resp.status_code == 401

    def test_gmail_success_with_valid_token(self, client, mock_processor):
        with patch.dict(os.environ, {"ATOM_GMAIL_WEBHOOK_SECRET": "correct"}):
            resp = client.post(
                "/api/webhooks/gmail",
                json={},
                headers={"Authorization": "Bearer correct"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        mock_processor.process_gmail_webhook.assert_awaited_once()


class TestHealth:
    def test_health_reports_healthy(self, client, mock_processor):
        mock_processor.processed_events = {"e1": 1, "e2": 2}
        resp = client.get("/api/webhooks/health")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "healthy"
        assert data["webhooks"] == {
            "slack": "enabled",
            "teams": "enabled",
            "gmail": "enabled",
        }
        assert data["processed_events"] == 2
