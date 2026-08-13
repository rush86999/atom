# -*- coding: utf-8 -*-
"""W71C — coverage push for 5 backend modules (standalone >=95% each).

Targets:
1. api/routes/webhooks/slack_webhooks.py    (100% via existing suites; re-covered here)
2. api/routes/webhooks/shopify_webhooks.py  (100%)
3. api/routes/webhooks/monitoring.py        (100%)
4. api/routes/webhooks/base.py              (100%)
5. core/privsec/audit_logger.py             (24% baseline — the real work)

Style: FastAPI TestClient + app.dependency_overrides; patches use real
module names (no `backend.` prefix). Mock HMAC/signatures, tenant discovery,
cache, registry, webhook bridge. Zero LLM spend, zero network, no real DB.

Webhook conventions exercised: shared-secret fail-closed (401/503 when the
secret is unconfigured), HMAC verification, malformed payloads, dedup,
service exceptions, tenant resolution fallbacks. Audit logger branches:
singleton/init, all four log_* action paths, query methods (incl. corrupt
lines and missing file), rotation, retention cleanup (incl. failure paths),
async wrappers.
"""

from __future__ import annotations

import asyncio
import base64
import gzip
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import get_db
from core.models import Base, TenantIntegration, UserConnection

# ============================================================================
# Shared fixtures / helpers
# ============================================================================


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    yield Session()
    engine.dispose()


@pytest.fixture
def webhook_app(db_session):
    from api.routes.webhooks.slack_webhooks import router as slack_router
    from api.routes.webhooks.shopify_webhooks import router as shopify_router
    from api.routes.webhooks.monitoring import router as monitoring_router

    application = FastAPI()
    application.include_router(shopify_router, prefix="/webhooks")
    application.include_router(slack_router, prefix="/webhooks")
    application.include_router(monitoring_router, prefix="/webhooks/monitoring")

    def override_get_db():
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    return application


@pytest.fixture
def client(webhook_app):
    return TestClient(webhook_app, raise_server_exceptions=False)


@pytest.fixture
def mock_registry():
    """Registry override whose execute_operation is an AsyncMock."""
    from api.routes.webhooks.base import get_webhook_registry

    registry = MagicMock()
    registry.execute_operation = AsyncMock(return_value={"status": "ok"})
    return registry


@pytest.fixture
def registry_client(webhook_app, mock_registry):
    from api.routes.webhooks.base import get_webhook_registry

    webhook_app.dependency_overrides[get_webhook_registry] = lambda: mock_registry
    yield TestClient(webhook_app, raise_server_exceptions=False), mock_registry


def _shopify_hmac(data: bytes, secret: str, encoding: str = "hex") -> str:
    digest = hmac.new(secret.encode(), data, hashlib.sha256).digest()
    return digest.hex() if encoding == "hex" else base64.b64encode(digest).decode()


def _add_slack_integration(db, secret="sec", tenant_id="tenant-1"):
    db.add(
        TenantIntegration(
            tenant_id=tenant_id,
            connector_id="slack",
            config={"slack_signing_secret": secret},
        )
    )
    db.commit()


@pytest.fixture
def bridge_result():
    from api.routes.webhooks.webhook_bridge import webhook_bridge

    with patch.object(
        webhook_bridge,
        "process_event",
        new=AsyncMock(return_value={"status": "success", "events": []}),
    ) as m:
        yield m


# ============================================================================
# api/routes/webhooks/base.py
# ============================================================================


class TestWebhookBase:
    def test_verify_hmac_signature_missing_inputs(self):
        from api.routes.webhooks.base import verify_hmac_signature

        assert verify_hmac_signature(b"data", "", "secret") is False
        assert verify_hmac_signature(b"data", "sig", "") is False
        assert verify_hmac_signature(b"data", None, "secret") is False

    def test_verify_hmac_signature_hex_match(self):
        from api.routes.webhooks.base import verify_hmac_signature

        data = b"payload"
        sig = hmac.new(b"secret", data, hashlib.sha256).hexdigest()
        assert verify_hmac_signature(data, sig, "secret") is True

    def test_verify_hmac_signature_base64_match(self):
        from api.routes.webhooks.base import verify_hmac_signature

        data = b"payload"
        sig = base64.b64encode(hmac.new(b"secret", data, hashlib.sha256).digest()).decode()
        assert verify_hmac_signature(data, sig, "secret") is True

    def test_verify_hmac_signature_wrong_secret(self):
        from api.routes.webhooks.base import verify_hmac_signature

        sig = hmac.new(b"right", b"data", hashlib.sha256).hexdigest()
        assert verify_hmac_signature(b"data", sig, "wrong") is False

    def test_verify_hmac_signature_bad_algorithm_false(self):
        """Digest computation guarded — never raises (500)."""
        from api.routes.webhooks.base import verify_hmac_signature

        with patch("api.routes.webhooks.base.hmac.new", side_effect=RuntimeError("boom")):
            assert verify_hmac_signature(b"d", "s", "sec") is False

    def test_verify_hmac_signature_bad_secret_type_false(self):
        """A non-str secret used to be a 500; must be a clean False."""
        from api.routes.webhooks.base import verify_hmac_signature

        assert verify_hmac_signature(b"d", "s", 12345) is False

    def test_get_webhook_registry(self, db_session):
        from api.routes.webhooks.base import get_webhook_registry
        from core.integration_registry import IntegrationRegistry

        reg = get_webhook_registry(db_session)
        assert isinstance(reg, IntegrationRegistry)


# ============================================================================
# api/routes/webhooks/shopify_webhooks.py
# ============================================================================


class TestShopifyWebhook:
    def test_missing_signature_header_401(self, client):
        resp = client.post("/webhooks/shopify", json={})
        assert resp.status_code == 401
        assert "signature" in resp.json()["detail"].lower()

    def test_no_secret_configured_503(self, client):
        with patch("api.routes.webhooks.shopify_webhooks._shopify_secret", return_value=None):
            resp = client.post(
                "/webhooks/shopify",
                content=b'{"ok": true}',
                headers={"X-Shopify-Hmac-Sha256": "deadbeef"},
            )
        assert resp.status_code == 503

    def test_invalid_signature_401(self, client):
        with patch("api.routes.webhooks.shopify_webhooks._shopify_secret", return_value="secret"):
            resp = client.post(
                "/webhooks/shopify",
                content=b'{"ok": true}',
                headers={"X-Shopify-Hmac-Sha256": "invalid"},
            )
        assert resp.status_code == 401

    def test_malformed_body_400(self, client):
        with patch("api.routes.webhooks.shopify_webhooks._shopify_secret", return_value="secret"):
            resp = client.post(
                "/webhooks/shopify",
                content=b"not-json",
                headers={"X-Shopify-Hmac-Sha256": _shopify_hmac(b"not-json", "secret")},
            )
        assert resp.status_code == 400

    def test_valid_webhook_dispatches(self, registry_client):
        client, registry = registry_client
        body = json.dumps({"order": 1}).encode()
        sig = _shopify_hmac(body, "secret")
        with patch("api.routes.webhooks.shopify_webhooks._shopify_secret", return_value="secret"):
            resp = client.post(
                "/webhooks/shopify",
                content=body,
                headers={
                    "X-Shopify-Hmac-Sha256": sig,
                    "X-Shopify-Shop-Domain": "shop1.myshopify.com",
                    "X-Shopify-Topic": "orders/create",
                },
            )
        assert resp.status_code == 200
        registry.execute_operation.assert_awaited_once()
        args, kwargs = registry.execute_operation.await_args
        assert args[0] == "shopify"
        assert args[1] == "shop1.myshopify.com"
        assert args[2] == "handle_webhook_event"
        assert args[3] == {"payload": {"order": 1}, "topic": "orders/create"}

    def test_valid_webhook_base64_signature(self, registry_client):
        client, registry = registry_client
        body = json.dumps({"order": 2}).encode()
        sig = _shopify_hmac(body, "secret", encoding="base64")
        with patch("api.routes.webhooks.shopify_webhooks._shopify_secret", return_value="secret"):
            resp = client.post(
                "/webhooks/shopify",
                content=body,
                headers={"X-Shopify-Hmac-Sha256": sig},
            )
        assert resp.status_code == 200
        assert registry.execute_operation.await_count == 1

    def test_default_tenant_when_domain_missing(self, registry_client):
        """No shop-domain header → 'default' tenant after verification."""
        client, registry = registry_client
        body = json.dumps({"a": 1}).encode()
        sig = _shopify_hmac(body, "secret")
        with patch("api.routes.webhooks.shopify_webhooks._shopify_secret", return_value="secret"):
            resp = client.post(
                "/webhooks/shopify",
                content=body,
                headers={"X-Shopify-Hmac-Sha256": sig},
            )
        assert resp.status_code == 200
        assert registry.execute_operation.await_args.args[1] == "default"

    def test_secret_falls_back_to_api_secret(self, registry_client):
        """SHOPIFY_API_SECRET fallback when SHOPIFY_WEBHOOK_SECRET unset."""
        client, registry = registry_client
        real_getenv = os.getenv

        def fake_getenv(key, default=None):
            if key == "SHOPIFY_WEBHOOK_SECRET":
                return None
            if key == "SHOPIFY_API_SECRET":
                return "api-secret"
            return real_getenv(key, default)

        body = json.dumps({"order": 3}).encode()
        sig = _shopify_hmac(body, "api-secret")
        with patch(
            "api.routes.webhooks.shopify_webhooks.os.getenv",
            side_effect=fake_getenv,
        ):
            resp = client.post(
                "/webhooks/shopify",
                content=body,
                headers={"X-Shopify-Hmac-Sha256": sig},
            )
        assert resp.status_code == 200
        assert registry.execute_operation.await_count == 1

    def test_service_exception_500(self, registry_client):
        """Registry crash surfaces as 500 (service-exception path)."""
        client, registry = registry_client
        registry.execute_operation = AsyncMock(side_effect=RuntimeError("boom"))
        body = json.dumps({"order": 4}).encode()
        sig = _shopify_hmac(body, "secret")
        with patch("api.routes.webhooks.shopify_webhooks._shopify_secret", return_value="secret"):
            resp = client.post(
                "/webhooks/shopify",
                content=body,
                headers={"X-Shopify-Hmac-Sha256": sig},
            )
        assert resp.status_code == 500


# ============================================================================
# api/routes/webhooks/slack_webhooks.py
# ============================================================================


class TestSlackWebhook:
    def test_invalid_json_400(self, client):
        resp = client.post("/webhooks/slack", content=b"not-json")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid JSON"

    def test_url_verification_challenge(self, client):
        resp = client.post(
            "/webhooks/slack", json={"type": "url_verification", "challenge": "abc"}
        )
        assert resp.status_code == 200
        assert resp.json() == {"challenge": "abc"}

    def test_missing_team_id_400(self, client):
        resp = client.post("/webhooks/slack", json={"type": "event_callback", "event": {}})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Missing team_id"

    def test_team_id_from_nested_event(self, client):
        """team_id inside event.team (fallback lookup)."""
        with patch("api.routes.webhooks.slack_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value=None)
            resp = client.post(
                "/webhooks/slack",
                json={"type": "event_callback", "event": {"team": "T-nested"}},
            )
        assert resp.status_code == 200
        TDS.return_value.get_tenant_id_by_external_id.assert_awaited_once_with(
            "slack", "T-nested"
        )

    def test_tenant_not_found_ignored(self, client):
        with patch("api.routes.webhooks.slack_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value=None)
            resp = client.post(
                "/webhooks/slack", json={"type": "event_callback", "team_id": "T1"}
            )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ignored", "reason": "tenant_not_found"}

    def test_no_signing_secret_401(self, client):
        with patch("api.routes.webhooks.slack_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value="tenant-1")
            resp = client.post(
                "/webhooks/slack", json={"type": "event_callback", "team_id": "T1"}
            )
        assert resp.status_code == 401
        assert "signing secret" in resp.json()["detail"].lower()

    def test_bad_signature_401(self, client, db_session):
        _add_slack_integration(db_session)
        with patch("api.routes.webhooks.slack_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value="tenant-1")
            with patch(
                "api.routes.webhooks.slack_webhooks.verify_slack_webhook",
                return_value=False,
            ):
                resp = client.post(
                    "/webhooks/slack", json={"type": "event_callback", "team_id": "T1"}
                )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid signature"

    def test_duplicate_event_skipped(self, client, db_session, bridge_result):
        _add_slack_integration(db_session)
        with patch("api.routes.webhooks.slack_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value="tenant-1")
            with patch("api.routes.webhooks.slack_webhooks.verify_slack_webhook", return_value=True):
                cache = AsyncMock()
                cache.get_async = AsyncMock(return_value="1")
                with patch("core.cache.UniversalCacheService", return_value=cache):
                    resp = client.post(
                        "/webhooks/slack",
                        json={
                            "type": "event_callback",
                            "team_id": "T1",
                            "event_id": "evt-1",
                            "event": {"type": "message"},
                        },
                    )
        assert resp.status_code == 200
        assert resp.json() == {"status": "duplicate", "event_id": "evt-1"}
        bridge_result.assert_not_awaited()

    def test_valid_event_dispatches_and_sets_cache(self, client, db_session, bridge_result):
        _add_slack_integration(db_session)
        with patch("api.routes.webhooks.slack_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value="tenant-1")
            with patch("api.routes.webhooks.slack_webhooks.verify_slack_webhook", return_value=True):
                cache = AsyncMock()
                cache.get_async = AsyncMock(return_value=None)
                with patch("core.cache.UniversalCacheService", return_value=cache):
                    resp = client.post(
                        "/webhooks/slack",
                        json={
                            "type": "event_callback",
                            "team_id": "T1",
                            "event_id": "evt-2",
                            "event": {"type": "message", "text": "hi", "user": "U1"},
                        },
                    )
        assert resp.status_code == 200
        assert resp.json() == {"status": "success", "events": []}
        cache.set_async.assert_awaited_once()
        assert cache.set_async.await_args.args[0] == "slack_event:tenant-1:evt-2"
        assert cache.set_async.await_args.kwargs["ttl"] == 3600

    def test_nested_event_id_dedup_key(self, client, db_session, bridge_result):
        """event_id missing top-level → pulled from event.event_id."""
        _add_slack_integration(db_session)
        with patch("api.routes.webhooks.slack_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value="tenant-1")
            with patch("api.routes.webhooks.slack_webhooks.verify_slack_webhook", return_value=True):
                cache = AsyncMock()
                cache.get_async = AsyncMock(return_value=None)
                with patch("core.cache.UniversalCacheService", return_value=cache):
                    resp = client.post(
                        "/webhooks/slack",
                        json={
                            "type": "event_callback",
                            "team_id": "T1",
                            "event": {"type": "message", "event_id": "evt-nested"},
                        },
                    )
        assert resp.status_code == 200
        cache.set_async.assert_awaited_once_with(
            "slack_event:tenant-1:evt-nested", "1", ttl=3600
        )

    def test_no_event_id_skips_dedup(self, client, db_session, bridge_result):
        """No event_id anywhere → dedup block skipped entirely."""
        _add_slack_integration(db_session)
        with patch("api.routes.webhooks.slack_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value="tenant-1")
            with patch("api.routes.webhooks.slack_webhooks.verify_slack_webhook", return_value=True):
                cache = AsyncMock()
                with patch("core.cache.UniversalCacheService", return_value=cache) as ucs:
                    resp = client.post(
                        "/webhooks/slack",
                        json={"type": "event_callback", "team_id": "T1", "event": {}},
                    )
        assert resp.status_code == 200
        ucs.assert_not_called()

    def test_cache_error_falls_through(self, client, db_session, bridge_result):
        """Cache outage must not break event processing (best-effort dedup)."""
        _add_slack_integration(db_session)
        with patch("api.routes.webhooks.slack_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value="tenant-1")
            with patch("api.routes.webhooks.slack_webhooks.verify_slack_webhook", return_value=True):
                cache = AsyncMock()
                cache.get_async = AsyncMock(side_effect=RuntimeError("cache down"))
                with patch("core.cache.UniversalCacheService", return_value=cache):
                    resp = client.post(
                        "/webhooks/slack",
                        json={
                            "type": "event_callback",
                            "team_id": "T1",
                            "event_id": "evt-3",
                            "event": {"type": "message"},
                        },
                    )
        assert resp.status_code == 200
        assert resp.json() == {"status": "success", "events": []}

    def test_falsy_cache_skips_set(self, client, db_session, bridge_result):
        """UniversalCacheService() returning None → dedup skipped, still dispatches."""
        _add_slack_integration(db_session)
        with patch("api.routes.webhooks.slack_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value="tenant-1")
            with patch("api.routes.webhooks.slack_webhooks.verify_slack_webhook", return_value=True):
                with patch("core.cache.UniversalCacheService", return_value=None):
                    resp = client.post(
                        "/webhooks/slack",
                        json={
                            "type": "event_callback",
                            "team_id": "T1",
                            "event_id": "evt-4",
                            "event": {"type": "message"},
                        },
                    )
        assert resp.status_code == 200
        assert resp.json() == {"status": "success", "events": []}

    def test_bridge_result_returned(self, client, db_session, bridge_result):
        """Dispatch result is the response body (no event_id → no dedup key)."""
        _add_slack_integration(db_session)
        bridge_result.return_value = {"status": "ignored", "reason": "test"}
        with patch("api.routes.webhooks.slack_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value="tenant-1")
            with patch("api.routes.webhooks.slack_webhooks.verify_slack_webhook", return_value=True):
                resp = client.post(
                    "/webhooks/slack",
                    json={"type": "event_callback", "team_id": "T1", "event": {"type": "message"}},
                )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ignored", "reason": "test"}
        bridge_result.assert_awaited_once()
        assert bridge_result.await_args.args[0] == "slack"
        assert bridge_result.await_args.args[1] == "tenant-1"


# ============================================================================
# api/routes/webhooks/monitoring.py — plain endpoints
# ============================================================================


class TestWebhookMonitoringRoutes:
    def test_health(self, client):
        resp = client.get("/webhooks/monitoring/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
        assert resp.json()["service"] == "webhook_monitoring"

    def test_circuit_states(self, client):
        resp = client.get("/webhooks/monitoring/circuit-states")
        assert resp.status_code == 200
        states = resp.json()["circuit_states"]
        assert states["slack"] == "closed"
        assert states["github"] == "closed"

    def test_status_with_data(self, client):
        from core.webhook_monitoring import (
            get_monitoring_service,
            get_rate_limit_tracker,
            get_subscription_monitor,
        )

        service = get_monitoring_service()
        tracker = get_rate_limit_tracker()
        monitor = get_subscription_monitor()
        tracker._rate_limits.clear()
        monitor._subscriptions.clear()

        rate_status = MagicMock()
        rate_status.connector_id = "slack"
        rate_status.tenant_id = "tenant-abcdef"
        rate_status.remaining = 100
        rate_status.limit = 500
        rate_status.percentage_remaining = 20.0
        tracker._rate_limits["slack:tenant-abcdef"] = rate_status

        sub_status = MagicMock()
        sub_status.tenant_id = "tenant-abcdef"
        sub_status.connector_id = "slack"
        sub_status.subscription_id = "sub-1"
        sub_status.expires_at = datetime.now(timezone.utc)
        monitor._subscriptions["slack:tenant-abcdef"] = sub_status

        with patch.object(
            service,
            "get_health_summary",
            return_value={
                "timestamp": "2026-01-01T00:00:00Z",
                "subscriptions_tracked": 1,
                "rate_limits_tracked": 1,
            },
        ):
            resp = client.get("/webhooks/monitoring/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["subscriptions_tracked"] == 1
        assert body["circuit_states"]["slack"] == "closed"
        assert body["rate_limits"]["slack:tenant-a"] == {
            "remaining": 100,
            "limit": 500,
            "percentage_remaining": 20.0,
        }
        assert body["subscriptions"][0]["subscription_id"] == "sub-1"

    def test_status_empty_trackers(self, client):
        from core.webhook_monitoring import (
            get_monitoring_service,
            get_rate_limit_tracker,
            get_subscription_monitor,
        )

        service = get_monitoring_service()
        get_rate_limit_tracker()._rate_limits.clear()
        get_subscription_monitor()._subscriptions.clear()
        with patch.object(
            service,
            "get_health_summary",
            return_value={
                "timestamp": "2026-01-01T00:00:00Z",
                "subscriptions_tracked": 0,
                "rate_limits_tracked": 0,
            },
        ):
            resp = client.get("/webhooks/monitoring/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["rate_limits"] == {}
        assert body["subscriptions"] == []

    def test_subscriptions_counts(self, client):
        from core.webhook_monitoring import get_subscription_monitor

        monitor = get_subscription_monitor()
        monitor._subscriptions.clear()

        def mk(key, expires_at):
            s = MagicMock()
            s.tenant_id = "t1"
            s.connector_id = "slack"
            s.subscription_id = key
            s.expires_at = expires_at
            monitor._subscriptions[key] = s

        mk("exp", datetime.now(timezone.utc) - timedelta(hours=5))
        mk("soon", datetime.now(timezone.utc) + timedelta(hours=24))
        mk("far", datetime.now(timezone.utc) + timedelta(days=10))

        resp = client.get("/webhooks/monitoring/subscriptions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 3
        assert body["expired_count"] == 1
        assert body["expiring_soon_count"] == 1
        by_id = {s["subscription_id"]: s for s in body["subscriptions"]}
        assert by_id["exp"]["is_expired"] is True
        assert by_id["exp"]["hours_remaining"] == 0
        assert by_id["soon"]["is_expired"] is False
        assert by_id["far"]["hours_remaining"] > 72

    def test_subscription_status_found(self, client):
        with patch(
            "api.routes.webhooks.monitoring.get_subscription_status",
            return_value={"tenant_id": "t1", "connector_id": "slack", "ok": True},
        ):
            resp = client.get("/webhooks/monitoring/subscriptions/slack/t1")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_subscription_status_not_found(self, client):
        with patch(
            "api.routes.webhooks.monitoring.get_subscription_status",
            return_value=None,
        ):
            resp = client.get("/webhooks/monitoring/subscriptions/slack/ghost")
        assert resp.status_code == 200
        body = resp.json()
        assert body["error"] == "Subscription not found"
        assert body["connector_id"] == "slack"
        assert body["tenant_id"] == "ghost"

    def test_rate_limits_low_and_healthy(self, client):
        from core.webhook_monitoring import get_rate_limit_tracker

        tracker = get_rate_limit_tracker()
        tracker._rate_limits.clear()

        def mk(key, pct):
            s = MagicMock()
            s.connector_id = "slack"
            s.tenant_id = key
            s.remaining = 10
            s.limit = 100
            s.percentage_remaining = pct
            tracker._rate_limits[key] = s

        mk("low", 10.0)
        mk("ok", 50.0)

        resp = client.get("/webhooks/monitoring/rate-limits")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 2
        assert body["low_quota_count"] == 1
        lows = [rl for rl in body["rate_limits"] if rl["is_low"]]
        assert lows[0]["tenant_id"] == "low"

    def test_rate_limit_status_endpoint(self, client):
        with patch(
            "api.routes.webhooks.monitoring.check_rate_limit_health",
            return_value={"healthy": True, "remaining": 5},
        ):
            resp = client.get("/webhooks/monitoring/rate-limits/slack/t1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["healthy"] is True
        assert body["connector_id"] == "slack"
        assert body["tenant_id"] == "t1"

    def test_metrics_export(self, client):
        with patch("api.routes.webhooks.monitoring.get_webhook_metrics") as GWM:
            m = MagicMock()
            m.export_prometheus = MagicMock(return_value="# TYPE webhook counter")
            GWM.return_value = m
            resp = client.get("/webhooks/monitoring/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["format"] == "prometheus"
        assert "# TYPE webhook counter" in body["metrics"]

    def test_check_alerts(self, client):
        from core.webhook_monitoring import get_monitoring_service

        service = get_monitoring_service()
        with patch.object(
            service, "check_subscription_expirations", return_value=[{"x": 1}, {"y": 2}]
        ):
            resp = client.post("/webhooks/monitoring/subscriptions/check-alerts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["alert_count"] == 2
        assert body["alerts"][0] == {"x": 1}


# ============================================================================
# api/routes/webhooks/monitoring.py — connection endpoints
# ============================================================================


class TestWebhookMonitoringConnections:
    def _add_conn(self, db_session, **overrides):
        defaults = dict(
            id="c1",
            user_id="raj-test-tenant-id",
            tenant_id="t1",
            integration_id="slack",
            status="active",
            connection_name="slack main",
            credentials={},
        )
        defaults.update(overrides)
        db_session.add(UserConnection(**defaults))
        db_session.commit()
        return defaults["id"]

    def test_health_dashboard_no_connections(self, client):
        resp = client.get("/webhooks/monitoring/health-dashboard")
        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["total_connections"] == 0
        assert body["connections"] == []

    def test_health_dashboard_healthy_with_dates(self, client, db_session):
        self._add_conn(
            db_session,
            last_refresh_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        with patch("core.connection_service.ConnectionService") as CS:
            svc = CS.return_value
            svc.get_connection_health_status = MagicMock(
                return_value={"health_status": "healthy"}
            )
            svc._decrypt = MagicMock(return_value={"subscription_id": "sub-9"})
            resp = client.get("/webhooks/monitoring/health-dashboard")
        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["healthy_connections"] == 1
        conn = body["connections"][0]
        assert conn["subscription_id"] == "sub-9"
        assert conn["last_refresh_at"] is not None
        assert conn["expires_at"] is not None
        assert conn["metrics"] == {
            "success_rate_percentage": 100.0,
            "delivered_count": 100,
            "failed_count": 0,
        }

    def test_health_dashboard_error_warning_states(self, client, db_session):
        self._add_conn(db_session, id="c-err", refresh_failure_count=2)
        self._add_conn(db_session, id="c-warn")
        with patch("core.connection_service.ConnectionService") as CS:
            svc = CS.return_value
            svc.get_connection_health_status = MagicMock(
                side_effect=[
                    {"health_status": "error"},
                    {"health_status": "expiring_soon"},
                ]
            )
            svc._decrypt = MagicMock(return_value={"subscription_ids": ["sub-a", "sub-b"]})
            resp = client.get("/webhooks/monitoring/health-dashboard")
        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["error_connections"] == 1
        assert body["summary"]["warning_connections"] == 1
        err = [c for c in body["connections"] if c["connection_id"] == "c-err"][0]
        assert err["metrics"] == {
            "success_rate_percentage": 0.0,
            "delivered_count": 0,
            "failed_count": 2,
        }
        warn = [c for c in body["connections"] if c["connection_id"] == "c-warn"][0]
        assert warn["metrics"] == {
            "success_rate_percentage": 95.0,
            "delivered_count": 95,
            "failed_count": 5,
        }
        assert warn["subscription_id"] == "sub-a"

    def test_health_dashboard_expired_and_degraded(self, client, db_session):
        """'expired' → error bucket; unknown health → warning bucket."""
        self._add_conn(db_session, id="c-exp")
        self._add_conn(db_session, id="c-deg", status=None)
        with patch("core.connection_service.ConnectionService") as CS:
            svc = CS.return_value
            svc.get_connection_health_status = MagicMock(
                side_effect=[
                    {"health_status": "expired"},
                    {"health_status": "degraded"},
                ]
            )
            svc._decrypt = MagicMock(return_value={})
            resp = client.get("/webhooks/monitoring/health-dashboard")
        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["error_connections"] == 1
        assert body["summary"]["warning_connections"] == 1
        deg = [c for c in body["connections"] if c["connection_id"] == "c-deg"][0]
        assert deg["status"] == "active"  # status None → "active"
        assert deg["subscription_id"] is None
        assert deg["last_refresh_at"] is None
        assert deg["expires_at"] is None
        assert deg["refresh_failure_count"] == 0

    def test_manual_renew_not_found(self, client):
        resp = client.post("/webhooks/monitoring/connections/nope/renew")
        assert resp.status_code == 200
        assert resp.json() == {"status": "error", "message": "Connection not found"}

    def test_manual_renew_success_with_dates(self, client, db_session):
        conn_id = self._add_conn(
            db_session,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            last_refresh_at=datetime.now(timezone.utc),
        )
        with patch("core.webhook_renewal_service.ScheduledWebhookRenewalService") as SWR:
            SWR.return_value.renew_subscription_for_connection = AsyncMock(
                return_value={"status": "success"}
            )
            resp = client.post(f"/webhooks/monitoring/connections/{conn_id}/renew")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["expires_at"] is not None
        assert body["last_refresh_at"] is not None

    def test_manual_renew_success_without_dates(self, client, db_session):
        conn_id = self._add_conn(db_session)
        with patch("core.webhook_renewal_service.ScheduledWebhookRenewalService") as SWR:
            SWR.return_value.renew_subscription_for_connection = AsyncMock(
                return_value={"status": "success"}
            )
            resp = client.post(f"/webhooks/monitoring/connections/{conn_id}/renew")
        assert resp.status_code == 200
        assert resp.json()["expires_at"] is None
        assert resp.json()["last_refresh_at"] is None

    def test_manual_renew_failure(self, client, db_session):
        conn_id = self._add_conn(db_session)
        with patch("core.webhook_renewal_service.ScheduledWebhookRenewalService") as SWR:
            SWR.return_value.renew_subscription_for_connection = AsyncMock(
                return_value={"status": "failed", "error": "oauth expired"}
            )
            resp = client.post(f"/webhooks/monitoring/connections/{conn_id}/renew")
        assert resp.status_code == 200
        assert resp.json() == {"status": "failed", "error": "oauth expired"}

    def test_troubleshoot_not_found(self, client):
        resp = client.get("/webhooks/monitoring/connections/nope/troubleshoot")
        assert resp.status_code == 200
        assert resp.json() == {"status": "error", "message": "Connection not found"}

    def test_troubleshoot_slack_all_passed(self, client, db_session):
        conn_id = self._add_conn(db_session)
        with patch("core.connection_service.ConnectionService") as CS:
            svc = CS.return_value
            svc._decrypt = MagicMock(return_value={"subscription_id": "sub-7"})
            svc._ensure_aware_datetime = MagicMock(return_value=datetime.now(timezone.utc))
            resp = client.get(f"/webhooks/monitoring/connections/{conn_id}/troubleshoot")
        assert resp.status_code == 200
        body = resp.json()
        assert body["diagnostics"] == {
            "vault_decryption": "passed",
            "token_expiration": "active",
            "status_flag": "healthy",
            "overall_verdict": "all_passed",
        }
        assert "Trigger Slack Event Webhook Ingestion" in body["cli_troubleshooting_tools"][0]["title"]

    def test_troubleshoot_slack_default_sub_id(self, client, db_session):
        """Outlook conn with empty creds → default mock-sub-1234 in the curl."""
        conn_id = self._add_conn(db_session, id="c-oauth", integration_id="outlook")
        with patch("core.connection_service.ConnectionService") as CS:
            svc = CS.return_value
            svc._decrypt = MagicMock(return_value={})
            resp = client.get(f"/webhooks/monitoring/connections/{conn_id}/troubleshoot")
        assert resp.status_code == 200
        assert "mock-sub-1234" in resp.json()["cli_troubleshooting_tools"][0]["command"]

    def test_troubleshoot_outlook_vault_fail(self, client, db_session):
        conn_id = self._add_conn(db_session, id="c-out", integration_id="outlook")
        with patch("core.connection_service.ConnectionService") as CS:
            svc = CS.return_value
            svc._decrypt = MagicMock(side_effect=RuntimeError("decrypt failed"))
            resp = client.get(f"/webhooks/monitoring/connections/{conn_id}/troubleshoot")
        assert resp.status_code == 200
        body = resp.json()
        assert body["diagnostics"]["vault_decryption"] == "failed"
        assert body["diagnostics"]["status_flag"] == "healthy"
        assert body["cli_troubleshooting_tools"][0]["title"] == "Simulate Live Webhook Notification"

    def test_troubleshoot_microsoft365_expired_degraded(self, client, db_session):
        conn_id = self._add_conn(
            db_session,
            id="c-365",
            integration_id="microsoft365",
            status="inactive",
            expires_at=datetime.now(timezone.utc),
        )
        with patch("core.connection_service.ConnectionService") as CS:
            svc = CS.return_value
            svc._decrypt = MagicMock(return_value={"subscription_id": "s365"})
            svc._ensure_aware_datetime = MagicMock(
                return_value=datetime.now(timezone.utc) - timedelta(days=1)
            )
            resp = client.get(f"/webhooks/monitoring/connections/{conn_id}/troubleshoot")
        assert resp.status_code == 200
        body = resp.json()
        assert body["diagnostics"] == {
            "vault_decryption": "passed",
            "token_expiration": "expired",
            "status_flag": "degraded",
            "overall_verdict": "requires_attention",
        }
        assert "Simulate Live Webhook Notification" in body["cli_troubleshooting_tools"][0]["title"]

    def test_troubleshoot_no_expiry_generic(self, client, db_session):
        """expires_at None → token not expired; generic connector command."""
        conn_id = self._add_conn(db_session, id="c-gen", integration_id="hubspot")
        with patch("core.connection_service.ConnectionService") as CS:
            svc = CS.return_value
            svc._decrypt = MagicMock(return_value={})
            resp = client.get(f"/webhooks/monitoring/connections/{conn_id}/troubleshoot")
        assert resp.status_code == 200
        body = resp.json()
        assert body["diagnostics"]["token_expiration"] == "active"
        assert body["cli_troubleshooting_tools"][0]["title"] == "Simulate Webhook Delivery"
        assert "pm-crm/hubspot" in body["cli_troubleshooting_tools"][0]["command"]


# ============================================================================
# core/privsec/audit_logger.py
# ============================================================================


@pytest.fixture
def audit(tmp_path, monkeypatch):
    """Fresh AuditLogger bound to a per-test temp log file."""
    import importlib
    import sys

    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "logs" / "audit.log"))
    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "30")
    if "core.privsec.audit_logger" in sys.modules:
        mod = importlib.reload(sys.modules["core.privsec.audit_logger"])
    else:
        import core.privsec.audit_logger as mod

    for instance in (mod.AuditLogger._instance, mod._audit_logger_instance):
        if instance is not None and hasattr(instance, "_audit_handler"):
            instance._audit_handler.close()
    yield mod
    instance = mod.AuditLogger._instance
    if instance is not None and hasattr(instance, "_audit_handler"):
        instance._audit_handler.close()


def _set_mtime(path, days_ago):
    ts = time.time() - days_ago * 86400
    os.utime(path, (ts, ts))


def _read_log_lines(path):
    return [line for line in open(path) if line.strip()]


class TestPrivsecAuditLogger:
    def test_module_constants_from_env(self, audit):
        assert audit.AUDIT_LOG_PATH.endswith("logs/audit.log")
        assert audit.AUDIT_LOG_RETENTION_DAYS == 30

    def test_singleton(self, audit):
        a1 = audit.AuditLogger()
        a2 = audit.AuditLogger()
        assert a1 is a2
        assert audit.get_audit_logger() is a1

    def test_init_runs_once(self, audit):
        a = audit.AuditLogger()
        a2 = audit.AuditLogger()  # __init__ early-returns via _initialized
        assert a2._initialized is True
        assert a._log_path.exists()  # mkdir + FileHandler created the file

    def test_log_media_action(self, audit):
        audit.AuditLogger().log_media_action(
            user_id="u1",
            agent_id="a1",
            action="pause_playback",
            service="spotify",
            details={"device_id": "dev-1"},
            result="success",
        )
        entries = [json.loads(l) for l in _read_log_lines(audit.AuditLogger()._log_path)]
        entry = entries[-1]
        assert entry["user_id"] == "u1"
        assert entry["agent_id"] == "a1"
        assert entry["action"] == "pause_playback"
        assert entry["category"] == "media"
        assert entry["service"] == "spotify"
        assert entry["details"] == {"device_id": "dev-1"}
        assert entry["result"] == "success"
        assert entry["ip_address"] is None
        assert entry["timestamp"].endswith("Z")

    def test_log_smarthome_action(self, audit):
        audit.AuditLogger().log_smarthome_action(
            user_id="u2",
            agent_id=None,
            action="turn_on",
            service="hue",
            details={"light_id": 3},
            result="blocked",
        )
        entries = [json.loads(l) for l in _read_log_lines(audit.AuditLogger()._log_path)]
        entry = entries[-1]
        assert entry["category"] == "smarthome"
        assert entry["agent_id"] is None
        assert entry["details"] == {"light_id": 3}

    def test_log_creative_action_merges_operation(self, audit):
        audit.AuditLogger().log_creative_action(
            user_id="u3",
            agent_id="a3",
            action="trim_video",
            operation="ffmpeg -i in.mp4 out.mp4",
            details={"input_path": "/tmp/in.mp4"},
            result="success",
        )
        entries = [json.loads(l) for l in _read_log_lines(audit.AuditLogger()._log_path)]
        entry = entries[-1]
        assert entry["category"] == "creative"
        assert entry["service"] == "ffmpeg"
        assert entry["details"] == {
            "input_path": "/tmp/in.mp4",
            "operation": "ffmpeg -i in.mp4 out.mp4",
        }

    def test_log_local_only_block(self, audit):
        logger = audit.AuditLogger()
        logger.log_local_only_block(
            user_id="u4",
            agent_id=None,
            service="notion",
            attempted_action="list_pages",
            reason="local_only_mode",
        )
        logger.log_local_only_block(
            user_id="u5",
            agent_id="a5",
            service="spotify",
            attempted_action="play",
        )
        entries = [json.loads(l) for l in _read_log_lines(audit.AuditLogger()._log_path)]
        with_reason, without_reason = entries[-2], entries[-1]
        assert with_reason["action"] == "blocked_list_pages"
        assert with_reason["category"] == "local_only_block"
        assert with_reason["details"] == {
            "attempted_action": "list_pages",
            "reason": "local_only_mode",
        }
        assert with_reason["result"] == "blocked"
        assert without_reason["details"] == {"attempted_action": "play"}

    def test_get_user_audit_log(self, audit):
        logger = audit.AuditLogger()
        logger.log_media_action("u1", None, "a", "spotify", {}, "success")
        logger.log_media_action("u2", None, "b", "spotify", {}, "success")
        logger.log_media_action("u1", None, "c", "spotify", {}, "success")
        with open(audit.AuditLogger()._log_path, "a") as f:
            f.write("this is not json\n")
        entries = logger.get_user_audit_log("u1")
        assert [e["action"] for e in entries] == ["c", "a"]  # most recent first

    def test_get_user_audit_log_limit(self, audit):
        logger = audit.AuditLogger()
        for i in range(5):
            logger.log_media_action("u1", None, f"act-{i}", "spotify", {}, "success")
        assert len(logger.get_user_audit_log("u1", limit=2)) == 2

    def test_get_user_audit_log_missing_file(self, audit):
        logger = audit.AuditLogger()
        logger._log_path.unlink(missing_ok=True)
        assert logger.get_user_audit_log("u1") == []

    def test_get_service_audit_log(self, audit):
        logger = audit.AuditLogger()
        logger.log_media_action("u1", None, "a", "spotify", {}, "success")
        logger.log_media_action("u1", None, "b", "sonos", {}, "success")
        logger.log_media_action("u1", None, "c", "spotify", {}, "success")
        with open(audit.AuditLogger()._log_path, "a") as f:
            f.write("{broken\n")
        entries = logger.get_service_audit_log("spotify")
        assert [e["action"] for e in entries] == ["c", "a"]

    def test_get_service_audit_log_limit_and_missing(self, audit):
        logger = audit.AuditLogger()
        for i in range(4):
            logger.log_smarthome_action("u1", None, f"s-{i}", "hue", {}, "success")
        assert len(logger.get_service_audit_log("hue", limit=1)) == 1
        assert logger.get_service_audit_log("ghost_service") == []

    def test_get_service_audit_log_missing_file(self, audit):
        logger = audit.AuditLogger()
        logger._log_path.unlink(missing_ok=True)
        assert logger.get_service_audit_log("spotify") == []

    def test_rotate_no_file_noop(self, audit):
        logger = audit.AuditLogger()
        logger._log_path.unlink(missing_ok=True)
        logger.rotate_audit_logs()
        assert not logger._log_path.exists()

    def test_rotate_same_day_noop(self, audit):
        logger = audit.AuditLogger()
        logger.log_media_action("u1", None, "a", "spotify", {}, "success")
        logger.rotate_audit_logs()
        assert logger._log_path.exists()
        assert not list(logger._log_path.parent.glob("*.log.gz"))

    def test_rotate_yesterday_compresses(self, audit):
        logger = audit.AuditLogger()
        logger.log_media_action("u1", None, "a", "spotify", {}, "success")
        _set_mtime(logger._log_path, 3)
        logger.rotate_audit_logs()

        parent = logger._log_path.parent
        gzs = list(parent.glob("*.log.gz"))
        assert len(gzs) == 1
        with gzip.open(gzs[0], "rt") as f:
            assert "spotify" in f.read()
        # Handler re-created → a fresh (empty) audit.log exists again; the
        # rotated uncompressed file is gone.
        remaining_logs = list(parent.glob("*.log"))
        assert remaining_logs == [logger._log_path]
        assert _read_log_lines(logger._log_path) == []

        # Subsequent writes land in the fresh audit.log
        logger.log_media_action("u2", None, "b", "sonos", {}, "success")
        assert json.loads(_read_log_lines(logger._log_path)[-1])["service"] == "sonos"

    def test_cleanup_old_audit_logs(self, audit, caplog):
        logger = audit.AuditLogger()
        logger.log_media_action("u1", None, "a", "spotify", {}, "success")
        rotated = logger._log_path.with_suffix(".2026-01-01.log")
        rotated.write_text('{"rotated": true}\n')
        _set_mtime(rotated, 200)
        _set_mtime(logger._log_path, 0)

        logger.cleanup_old_audit_logs()
        assert not rotated.exists()
        assert logger._log_path.exists()
        # Regression (W71C): the naive-vs-aware datetime comparison used to
        # raise TypeError inside the loop → swallowed → nothing removed AND a
        # spurious error logged. Old file must be gone with NO error record.
        assert not [r for r in caplog.records if "Failed to remove old audit log" in r.getMessage()]

    def test_cleanup_removes_only_old_files(self, audit):
        logger = audit.AuditLogger()
        logger.log_media_action("u1", None, "a", "spotify", {}, "success")
        old = logger._log_path.with_suffix(".2026-02-02.log")
        old.write_text('{"old": true}\n')
        _set_mtime(old, 200)
        fresh = logger._log_path.with_suffix(".2026-08-12.log")
        fresh.write_text('{"fresh": true}\n')
        _set_mtime(fresh, 1)

        logger.cleanup_old_audit_logs()
        assert not old.exists()
        assert fresh.exists()

    def test_cleanup_stat_failure_logged(self, audit, caplog):
        logger = audit.AuditLogger()
        logger.log_media_action("u1", None, "a", "spotify", {}, "success")
        old = logger._log_path.with_suffix(".2026-01-01.log")
        old.write_text('{"old": true}\n')
        _set_mtime(old, 200)

        class BoomDT(datetime):
            @classmethod
            def fromtimestamp(cls, ts):
                raise RuntimeError("stat boom")

        with patch.object(audit, "datetime", BoomDT):
            logger.cleanup_old_audit_logs()
        # Failure is logged, no crash, file left behind
        assert any("Failed to remove old audit log" in r.getMessage() for r in caplog.records)
        assert old.exists()

    def test_log_media_action_async(self, audit):
        asyncio.run(
            audit.log_media_action_async("u1", None, "play", "spotify", {"track": "x"}, "success")
        )
        entries = [json.loads(l) for l in _read_log_lines(audit.AuditLogger()._log_path)]
        entry = entries[-1]
        assert entry["action"] == "play"
        assert entry["category"] == "media"

    def test_log_smarthome_action_async(self, audit):
        asyncio.run(
            audit.log_smarthome_action_async(
                "u2", "a2", "set_color", "hue", {"color": "red"}, "failed"
            )
        )
        entries = [json.loads(l) for l in _read_log_lines(audit.AuditLogger()._log_path)]
        entry = entries[-1]
        assert entry["action"] == "set_color"
        assert entry["result"] == "failed"

    def test_get_audit_logger_reuse(self, audit):
        assert audit.get_audit_logger() is audit.get_audit_logger()
        assert audit.get_audit_logger() is audit.AuditLogger()

    def test_ip_address_included(self, audit):
        audit.AuditLogger()._write_audit_log(
            user_id="u1",
            agent_id=None,
            action="secret_action",
            category="media",
            service="sonos",
            details={"speaker_ip": "10.0.0.5"},
            result="success",
            ip_address="192.168.1.100",
        )
        entries = [json.loads(l) for l in _read_log_lines(audit.AuditLogger()._log_path)]
        assert entries[-1]["ip_address"] == "192.168.1.100"
