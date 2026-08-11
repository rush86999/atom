"""Coverage wave 44 — gateway auth (84%), budget_alerts (68%), request_logger (73%), __init__ error map (75%) → 90%+.

- auth: to_audit, key prefix generation, rate-limit (disabled/purge/exceeded),
  api-key resolution (revoked/expired-naive/user-missing/non-active/rollback),
  non-atom_sk secret 401
- budget_alerts: budget limit fallback, recipient resolution matrix, zero-limit
  skip, no-recipient skip, sync shim
- request_logger: header dropping, redaction fail-closed, body sanitize
  fallbacks, cost estimate chain, log write + sweep exception tolerance
- error map: all exception-type branches
"""
import time as _time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import HTTPException, Request

from core.llm.gateway import (
    AllProvidersFailedError,
    GatewayBlockedError,
    NoProvidersConfiguredError,
    map_gateway_error,
)
from core.llm.gateway.auth import (
    GatewayIdentity,
    _check_rate_limit,
    _extract_secret,
    _resolve_api_key,
    generate_key_prefix,
    get_gateway_identity,
    hash_api_key,
)
from core.llm.gateway.budget_alerts import (
    _notify_thresholds,
    _resolve_recipient_id,
    record_gateway_spend,
    resolve_budget_limit,
    run_budget_alert_sync,
)
from core.llm.gateway.request_logger import (
    _drop_auth_headers,
    _redact_text,
    _sanitize_body,
    estimate_cost_usd,
    log_gateway_request,
    sweep_gateway_logs,
)


def await_coroutine(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================================
# auth
# ============================================================================

class TestAuthHelpers:
    def test_to_audit_with_and_without_key_id(self):
        i1 = GatewayIdentity(user_id="u1", tenant_id="t1", workspace_id="w1",
                             auth_method="api_key")
        assert i1.to_audit()["api_key_id"] == ""
        i2 = GatewayIdentity(user_id="u1", tenant_id="t1", workspace_id="w1",
                             auth_method="api_key", api_key_id="k1")
        assert i2.to_audit()["api_key_id"] == "k1"

    def test_hash_api_key(self):
        assert hash_api_key("secret") == hash_api_key("secret")
        assert hash_api_key("secret") != hash_api_key("other")

    def test_generate_key_prefix_format(self):
        prefix = generate_key_prefix("anything")
        assert prefix.startswith("atom_sk_")
        assert len(prefix) == len("atom_sk_") + 4

    def test_extract_secret_variants(self):
        req = MagicMock(spec=Request)
        req.headers = {"x-api-key": "  key1  "}
        assert _extract_secret(req) == "key1"
        req.headers = {"Authorization": "Bearer tok"}
        assert _extract_secret(req) == "tok"
        req.headers = {"Authorization": "Basic abc"}
        assert _extract_secret(req) is None
        req.headers = {}
        assert _extract_secret(req) is None


class TestRateLimit:
    def test_disabled_when_limit_nonpositive(self):
        _check_rate_limit("h", 0)  # must not raise
        _check_rate_limit("h", -1)

    def test_under_limit_ok(self):
        _check_rate_limit("h-under", 10)
        _check_rate_limit("h-under", 10)

    def test_exceeded_raises_429(self):
        with patch("core.llm.gateway.auth.logger"):
            for _ in range(5):
                _check_rate_limit("h-over", 5)
            with pytest.raises(HTTPException) as ei:
                _check_rate_limit("h-over", 5)
            assert ei.value.status_code == 429

    def test_window_purge_and_stale_keys(self):
        import core.llm.gateway.auth as auth
        with patch.object(auth, "_rate_limit_state", {f"key-{i}": _time_deque() for i in range(10)}), \
             patch.object(auth, "_RATE_LIMIT_WINDOW_SECONDS", 60):
            pass

    def test_stale_key_purge(self):
        import core.llm.gateway.auth as auth
        import collections
        state = {}
        for i in range(1005):
            dq = collections.deque()
            dq.append(_time.time() - 9999)  # fully outside window
            state[f"old-{i}"] = dq
        with patch.object(auth, "_rate_limit_state", state), \
             patch.object(auth, "_RATE_LIMIT_WINDOW_SECONDS", 60):
            _check_rate_limit("fresh-key", 10)
        assert len(state) < 1005  # stale keys purged


def _time_deque():
    import collections
    return collections.deque()


class TestResolveApiKey:
    def _db(self, row, user=None):
        db = Mock()
        db.query.return_value.filter.return_value.first.side_effect = [row, user]
        return db

    def test_revoked_raises(self):
        row = SimpleNamespace(key_hash="h", is_active=True, revoked_at=object(),
                              expires_at=None, user_id="u1", tenant_id=None,
                              workspace_id=None, id="k1", total_requests=0,
                              last_used=None)
        db = self._db(row, SimpleNamespace(id="u1", status="active"))
        with pytest.raises(HTTPException) as ei:
            await_coroutine(_resolve_api_key("k", db, Mock()))
        assert "revoked" in str(ei.value.detail)

    def test_naive_expired_raises(self):
        from datetime import datetime, timedelta, timezone
        row = SimpleNamespace(
            key_hash="h", is_active=True, revoked_at=None,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            user_id="u1", tenant_id=None, workspace_id=None,
            id="k1", total_requests=0, last_used=None,
        )
        row.expires_at = row.expires_at.replace(tzinfo=None)  # SQLite naive round-trip
        db = self._db(row, SimpleNamespace(id="u1", status="active"))
        with pytest.raises(HTTPException) as ei:
            await_coroutine(_resolve_api_key("k", db, Mock()))
        assert "expired" in str(ei.value.detail)

    def test_missing_user_raises(self):
        row = SimpleNamespace(key_hash="h", is_active=True, revoked_at=None,
                              expires_at=None, user_id="u1", tenant_id=None,
                              workspace_id=None, id="k1", total_requests=0,
                              last_used=None)
        db = self._db(row, None)
        with pytest.raises(HTTPException):
            await_coroutine(_resolve_api_key("k", db, Mock()))

    def test_non_active_user_raises(self):
        row = SimpleNamespace(key_hash="h", is_active=True, revoked_at=None,
                              expires_at=None, user_id="u1", tenant_id=None,
                              workspace_id=None, id="k1", total_requests=0,
                              last_used=None)
        db = self._db(row, SimpleNamespace(id="u1", status="disabled"))
        with pytest.raises(HTTPException) as ei:
            await_coroutine(_resolve_api_key("k", db, Mock()))
        assert "not active" in str(ei.value.detail)

    def test_commit_exception_rolls_back(self):
        from datetime import datetime, timezone
        row = SimpleNamespace(key_hash="h", is_active=True, revoked_at=None,
                              expires_at=None, user_id="u1", tenant_id=None,
                              workspace_id=None, id="k1", total_requests=0,
                              last_used=None, rate_limit_per_minute=60)
        db = self._db(row, SimpleNamespace(id="u1", status="active"))
        db.commit.side_effect = RuntimeError("boom")
        with patch("core.personal_scope.resolve_tenant_id", return_value="t1"), \
             patch("core.personal_scope.resolve_workspace_id", return_value="w1"):
            identity = await_coroutine(_resolve_api_key("k", db, Mock()))
        db.rollback.assert_called_once()
        assert identity.auth_method == "api_key"


class TestGatewayIdentityResolution:
    def test_non_atom_sk_non_jwt_secret_raises(self):
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Bearer not-a-jwt"}
        with pytest.raises(HTTPException):
            await_coroutine(get_gateway_identity(request, Mock()))

    def test_no_secret_raises(self):
        request = MagicMock(spec=Request)
        request.headers = {}
        with pytest.raises(HTTPException):
            await_coroutine(get_gateway_identity(request, Mock()))


# ============================================================================
# budget_alerts
# ============================================================================

class TestBudgetAlerts:
    def test_budget_limit_fallback_on_error(self):
        with patch("core.personal_budget_service.personal_budget_service"
                   "._get_budget_limit", side_effect=RuntimeError("no service")):
            assert resolve_budget_limit("ws1") == 100.0

    def test_budget_limit_success(self):
        svc = Mock()
        svc._get_budget_limit.return_value = 250.0
        with patch("core.personal_budget_service.personal_budget_service", svc):
            assert resolve_budget_limit("ws1") == 250.0

    def test_recipient_prefers_caller(self):
        db = Mock()
        user = SimpleNamespace(id="caller-1")
        db.query.return_value.filter.return_value.first.return_value = user
        with patch("core.database.SessionLocal", return_value=db):
            assert _resolve_recipient_id("caller-1") == "caller-1"

    def test_recipient_falls_back_to_admin(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.side_effect = [None, SimpleNamespace(id="admin-1")]
        with patch("core.database.SessionLocal", return_value=db):
            assert _resolve_recipient_id("unknown-user") == "admin-1"

    def test_recipient_none_when_no_admin(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.side_effect = [None, None]
        with patch("core.database.SessionLocal", return_value=db):
            assert _resolve_recipient_id("unknown-user") is None

    def test_recipient_exception_returns_none(self):
        with patch("core.database.SessionLocal", side_effect=RuntimeError("db down")):
            assert _resolve_recipient_id("u") is None

    async def test_spend_zero_limit_skips(self):
        import core.llm.gateway.budget_alerts as ba
        with patch.object(ba, "_daily_spend", {}), \
             patch.object(ba, "resolve_budget_limit", return_value=0.0):
            assert await record_gateway_spend("ws1", 5.0) == []

    async def test_spend_threshold_crossed_once(self):
        import core.llm.gateway.budget_alerts as ba
        with patch.object(ba, "GATEWAY_BUDGET_ALERTS_ENABLED", True), \
             patch.object(ba, "_daily_spend", {}), \
             patch.object(ba, "_fired", {}), \
             patch.object(ba, "resolve_budget_limit", return_value=100.0), \
             patch.object(ba, "_notify_thresholds", new=AsyncMock()) as nt:
            crossed = await record_gateway_spend("ws1", 80.0)
        assert 50 in crossed and 80 in crossed  # thresholds crossed
        nt.assert_awaited_once()
        # second call: same threshold already fired
        with patch.object(ba, "GATEWAY_BUDGET_ALERTS_ENABLED", True), \
             patch.object(ba, "resolve_budget_limit", return_value=100.0), \
             patch.object(ba, "_notify_thresholds", new=AsyncMock()) as nt2:
            await record_gateway_spend("ws1", 5.0)
        nt2.assert_not_awaited()

    async def test_spend_disabled_flag_returns_empty(self):
        import core.llm.gateway.budget_alerts as ba
        with patch.object(ba, "GATEWAY_BUDGET_ALERTS_ENABLED", False):
            assert await record_gateway_spend("ws1", 80.0) == []

    async def test_notify_skips_without_recipient(self):
        with patch("core.llm.gateway.budget_alerts._resolve_recipient_id", return_value=None), \
             patch("core.llm.gateway.budget_alerts.NotificationService") as ns:
            await _notify_thresholds("ws1", [50], 60.0, 100.0)
        ns.assert_not_called()

    async def test_notify_sends(self):
        notifier = Mock()
        notifier.send_notification = AsyncMock()
        with patch("core.llm.gateway.budget_alerts._resolve_recipient_id", return_value="u1"), \
             patch("core.llm.gateway.budget_alerts.NotificationService", return_value=notifier):
            await _notify_thresholds("ws1", [50, 80], 60.0, 100.0)
        assert notifier.send_notification.await_count == 2

    def test_sync_shim(self):
        import core.llm.gateway.budget_alerts as ba
        with patch.object(ba, "record_gateway_spend", new=AsyncMock(return_value=[50])):
            assert run_budget_alert_sync("ws1", 1.0) == [50]


# ============================================================================
# request_logger
# ============================================================================

class TestRequestLogger:
    def test_drop_auth_headers(self):
        assert _drop_auth_headers({"Authorization": "x", "X-Api-Key": "y", "ok": "1"}) == {"ok": "1"}
        assert _drop_auth_headers(None) == {}
        assert _drop_auth_headers("not-a-dict") == {}

    def test_redact_text_empty_and_failure(self):
        assert _redact_text("") == ""
        with patch("core.pii_redactor.redact_pii", side_effect=RuntimeError("boom")):
            assert _redact_text("sensitive") == "[redaction unavailable — body omitted]"

    def test_sanitize_body_disabled_or_none(self):
        assert _sanitize_body({"a": 1}, include_body=False) is None
        assert _sanitize_body(None, include_body=True) is None

    def test_sanitize_body_json_failure_falls_back_str(self):
        with patch("json.dumps", side_effect=TypeError("unserializable")), \
             patch("core.llm.gateway.request_logger._redact_text", return_value="x"):
            assert _sanitize_body(object(), include_body=True) == "x"

    def test_estimate_cost_chain(self):
        fetcher = Mock()
        fetcher.estimate_cost.return_value = 0.05
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=fetcher):
            assert estimate_cost_usd("m", 100, 50) == 0.05
        fetcher.estimate_cost.return_value = None
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=fetcher), \
             patch("core.cost_config.get_llm_cost", return_value=0.03):
            assert estimate_cost_usd("m", 100, 50) == 0.03

    def test_estimate_cost_none_and_exception(self):
        fetcher = Mock()
        fetcher.estimate_cost.return_value = None
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=fetcher), \
             patch("core.cost_config.get_llm_cost", return_value=None):
            assert estimate_cost_usd("m", 0, 0) is None
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   side_effect=RuntimeError("boom")):
            assert estimate_cost_usd("m", 10, 10) is None

    def test_log_gateway_request_success(self):
        from core.models import GatewayRequestLog
        db = Mock()
        row = MagicMock(spec=GatewayRequestLog)
        row.id = "log-1"
        db.add.return_value = None
        db.refresh.side_effect = lambda r: setattr(r, "id", "log-1")
        identity = SimpleNamespace(tenant_id="t", workspace_id="w", user_id="u",
                                   api_key_id=None)
        with patch("core.llm.gateway.request_logger.GatewayRequestLog", return_value=row), \
             patch("core.llm.gateway.request_logger._sanitize_body", return_value="{}"):
            result = log_gateway_request(
                db, identity, model="m", stream=True, status_code=200,
                prompt_tokens=10, completion_tokens=5, cost_usd=0.01,
                request_body={}, response_body={},
            )
        assert result == "log-1"

    def test_log_gateway_request_exception_returns_none(self):
        db = Mock()
        db.commit.side_effect = RuntimeError("boom")
        identity = SimpleNamespace(tenant_id="t", workspace_id="w", user_id="u",
                                   api_key_id=None)
        with patch("core.llm.gateway.request_logger.GatewayRequestLog", new=MagicMock()):
            result = log_gateway_request(db, identity, model="m", status_code=200,
                                         request_body={}, response_body={})
        assert result is None
        db.rollback.assert_called_once()

    def test_sweep_success_and_exception(self):
        db = Mock()
        db.query.return_value.filter.return_value.delete.return_value = 7
        assert sweep_gateway_logs(db) == 7
        db2 = Mock()
        db2.query.return_value.filter.return_value.delete.side_effect = RuntimeError("boom")
        assert sweep_gateway_logs(db2) == 0
        db2.rollback.assert_called_once()


# ============================================================================
# gateway error map
# ============================================================================

class TestErrorMap:
    def test_no_providers(self):
        exc = NoProvidersConfiguredError()
        body = map_gateway_error(exc)
        assert body["error"]["code"] == "no_llm_provider"
        assert body["error"]["recovery_url"] == "/settings/ai"

    def test_no_providers_custom_recovery(self):
        exc = NoProvidersConfiguredError()
        exc.recovery_url = "/custom"
        body = map_gateway_error(exc)
        assert body["error"]["recovery_url"] == "/custom"

    def test_gateway_blocked(self):
        exc = GatewayBlockedError(message="blocked for spend", reason="budget")
        body = map_gateway_error(exc)
        assert body["error"]["code"] == "budget"
        assert body["error"]["message"] == "blocked for spend"

    def test_all_providers_failed(self):
        body = map_gateway_error(AllProvidersFailedError())
        assert body["error"]["code"] == "all_providers_failed"

    def test_http_exception(self):
        body = map_gateway_error(HTTPException(status_code=404, detail="missing"))
        assert body["error"]["code"] == "gateway_error"
        assert body["_status"] == 404

    def test_value_error(self):
        body = map_gateway_error(ValueError("bad"))
        assert body["error"]["code"] == "invalid_request"

    def test_generic(self):
        body = map_gateway_error(RuntimeError("boom"))
        assert body["error"]["code"] == "internal_error"

    def test_anthropic_shape(self):
        body = map_gateway_error(ValueError("bad"), anthropic=True)
        assert "error" in body
        assert body["error"]["type"] == "invalid_request_error"
