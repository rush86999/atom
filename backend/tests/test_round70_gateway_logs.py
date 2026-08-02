"""Round 70 — B4: GatewayRequestLog persistence + redaction + log viewer."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.database import get_db
from core.llm.gateway import request_logger as rl
from core.models import GatewayRequestLog


class TestRequestLogger:
    def test_drop_auth_headers(self):
        h = rl._drop_auth_headers(
            {"Authorization": "Bearer x", "x-api-key": "k", "content-type": "json", "Cookie": "s=1"}
        )
        assert h == {"content-type": "json"}

    def test_sanitize_body_only_when_enabled(self):
        body = {"messages": [{"content": "hi john@example.com"}]}
        # Mock the redactor so the test verifies the LOGGER's contract (redaction
        # is applied) independent of whether the fallback regex redactor catches
        # emails in this environment.
        with patch.object(rl, "GATEWAY_LOG_BODIES", True), \
             patch("core.pii_redactor.redact_pii", return_value="[REDACTED]"):
            out = rl._sanitize_body(body, True)
            assert out is not None
            assert "john@example.com" not in out  # PII redacted
        assert rl._sanitize_body(body, False) is None

    def test_redaction_fails_closed(self):
        """When the PII redactor import fails, the body is replaced with a
        placeholder rather than persisted raw (fail-closed)."""
        body = {"messages": [{"content": "secret stuff"}]}
        with patch.object(rl, "GATEWAY_LOG_BODIES", True):
            with patch("core.pii_redactor.redact_pii", side_effect=ImportError("no redactor")):
                out = rl._sanitize_body(body, True)
        assert out is not None
        assert "secret stuff" not in out
        assert "redaction unavailable" in out.lower()

    def test_truncate(self):
        big = "x" * (rl.MAX_LOG_BODY_CHARS + 10)
        assert len(rl._truncate(big)) == rl.MAX_LOG_BODY_CHARS

    def test_log_gateway_request_writes_row(self):
        db = MagicMock()
        identity = MagicMock()
        identity.tenant_id = "t-1"
        identity.workspace_id = "ws-1"
        identity.user_id = "u-1"
        identity.api_key_id = "key-1"
        row = MagicMock()
        row.id = "log-1"
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock(side_effect=lambda r: setattr(r, "id", "log-1"))
        with patch.object(rl, "GATEWAY_LOG_BODIES", True):
            lid = rl.log_gateway_request(
                db, identity, provider="openai", model="gpt-4o", status_code=200,
                prompt_tokens=5, completion_tokens=3, cost_usd=0.01,
                request_body={"messages": [{"role": "user", "content": "hi"}]},
                response_body={"choices": [{"message": {"content": "hey"}}]},
            )
        assert lid == "log-1"
        added = db.add.call_args[0][0]
        assert isinstance(added, GatewayRequestLog)
        assert added.user_id == "u-1"
        assert added.request_json is not None

    def test_sweep_deletes_old(self):
        db = MagicMock()
        q = MagicMock()
        db.query.return_value = q
        q.filter.return_value.delete.return_value = 3
        assert rl.sweep_gateway_logs(db) == 3


class TestLogRoutes:
    def _client(self, db):
        from api.gateway_log_routes import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: db
        return TestClient(app, raise_server_exceptions=False)

    def test_list_logs_requires_auth(self):
        r = self._client(MagicMock()).get("/api/v1/gateway/logs")
        assert r.status_code == 401

    def test_list_logs_owner_scoped(self):
        db = MagicMock()
        row = MagicMock(spec=GatewayRequestLog)
        row.id = "log-1"
        row.provider = "openai"
        row.model = "gpt-4o"
        row.stream = False
        row.status_code = 200
        row.latency_ms = 5
        row.prompt_tokens = 5
        row.completion_tokens = 3
        row.cost_usd = 0.01
        row.created_at = None
        row.request_json = None
        row.response_json = None
        q = MagicMock()
        q.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [row]
        db.query.return_value = q

        from core.auth import get_current_user

        async def fake_current_user():
            u = MagicMock()
            u.id = "u-1"
            return u

        app = FastAPI()
        from api.gateway_log_routes import router

        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = fake_current_user
        client = TestClient(app, raise_server_exceptions=False)

        r = client.get("/api/v1/gateway/logs")
        assert r.status_code == 200
        assert r.json()["data"][0]["id"] == "log-1"
        # Owner-scoped filter applied to user_id
        filter_called = q.filter.call_args[0][0]
        assert filter_called.left.name == "user_id"
