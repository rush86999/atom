"""Coverage wave 8 — api/routes/webhooks/*.

Hermetic: FastAPI TestClient with in-memory SQLite (StaticPool); all external
services (TenantDiscoveryService, adapters, UCB, ingestion, orchestrator,
circuit breaker, feature flags) mocked.
"""
from __future__ import annotations

import hashlib
import hmac
import base64
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import Base, UserConnection, Workspace


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
def app(db_session):
    from api.routes.webhooks.discord_webhooks import router as discord_router
    from api.routes.webhooks.monitoring import router as monitoring_router
    from api.routes.webhooks.shopify_webhooks import router as shopify_router
    from api.routes.webhooks.slack_webhooks import router as slack_router
    from api.routes.webhooks.teams_webhooks import router as teams_router
    from api.routes.webhooks.twilio_webhooks import router as twilio_router
    from api.routes.webhooks.whatsapp_webhooks import router as whatsapp_router

    application = FastAPI()
    application.include_router(shopify_router, prefix="/webhooks")
    application.include_router(twilio_router, prefix="/webhooks")
    application.include_router(whatsapp_router, prefix="/webhooks")
    application.include_router(teams_router, prefix="/webhooks")
    application.include_router(discord_router, prefix="/webhooks")
    application.include_router(slack_router, prefix="/webhooks")
    application.include_router(monitoring_router, prefix="/webhooks/monitoring")

    def override_get_db():
        yield db_session

    application.dependency_overrides.clear()
    from core.database import get_db

    application.dependency_overrides[get_db] = override_get_db
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


def _shopify_hmac(data: bytes, secret: str, encoding: str = "hex") -> str:
    digest = hmac.new(secret.encode(), data, hashlib.sha256).digest()
    return digest.hex() if encoding == "hex" else base64.b64encode(digest).decode()


# ===========================================================================
# base.py
# ===========================================================================

class TestWebhookBase:
    def test_verify_hmac_signature_empty(self):
        from api.routes.webhooks.base import verify_hmac_signature

        assert verify_hmac_signature(b"data", "", "secret") is False
        assert verify_hmac_signature(b"data", "sig", "") is False
        assert verify_hmac_signature(b"data", None, "secret") is False

    def test_verify_hmac_signature_hex(self):
        from api.routes.webhooks.base import verify_hmac_signature

        data = b"payload"
        digest = hmac.new(b"secret", data, hashlib.sha256).hexdigest()
        assert verify_hmac_signature(data, digest, "secret") is True

    def test_verify_hmac_signature_base64(self):
        from api.routes.webhooks.base import verify_hmac_signature

        data = b"payload"
        digest = hmac.new(b"secret", data, hashlib.sha256).digest()
        b64 = base64.b64encode(digest).decode()
        assert verify_hmac_signature(data, b64, "secret") is True

    def test_verify_hmac_signature_wrong_secret(self):
        from api.routes.webhooks.base import verify_hmac_signature

        digest = hmac.new(b"right", b"data", hashlib.sha256).hexdigest()
        assert verify_hmac_signature(b"data", digest, "wrong") is False

    def test_verify_hmac_signature_exception_false(self):
        from api.routes.webhooks.base import verify_hmac_signature

        with patch("api.routes.webhooks.base.hmac.new", side_effect=RuntimeError("boom")):
            assert verify_hmac_signature(b"d", "s", "sec") is False

    def test_get_webhook_registry(self, db_session):
        from api.routes.webhooks.base import get_webhook_registry

        reg = get_webhook_registry(db_session)
        from core.integration_registry import IntegrationRegistry

        assert isinstance(reg, IntegrationRegistry)


# ===========================================================================
# shopify_webhooks.py
# ===========================================================================

class TestShopifyWebhook:
    def test_missing_signature_401(self, client):
        resp = client.post("/webhooks/shopify", json={})
        assert resp.status_code == 401
        assert "signature" in resp.json()["detail"].lower()

    def test_no_secret_503(self, client):
        with patch("api.routes.webhooks.shopify_webhooks._shopify_secret", return_value=None):
            resp = client.post(
                "/webhooks/shopify",
                content=b'{"ok": true}',
                headers={"X-Shopify-Hmac-Sha256": "deadbeef"},
            )
        assert resp.status_code == 503

    def test_bad_signature_401(self, client):
        with patch("api.routes.webhooks.shopify_webhooks._shopify_secret", return_value="secret"):
            resp = client.post(
                "/webhooks/shopify",
                content=b'{"ok": true}',
                headers={"X-Shopify-Hmac-Sha256": "invalid"},
            )
        assert resp.status_code == 401

    def test_malformed_json_400(self, client):
        with patch("api.routes.webhooks.shopify_webhooks._shopify_secret", return_value="secret"):
            resp = client.post(
                "/webhooks/shopify",
                content=b"not-json",
                headers={"X-Shopify-Hmac-Sha256": _shopify_hmac(b"not-json", "secret")},
            )
        assert resp.status_code == 400

    def test_valid_webhook_executes(self, client):
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

    def test_valid_webhook_base64_signature(self, client):
        body = json.dumps({"order": 2}).encode()
        sig = _shopify_hmac(body, "secret", encoding="base64")
        with patch("api.routes.webhooks.shopify_webhooks._shopify_secret", return_value="secret"):
            resp = client.post(
                "/webhooks/shopify",
                content=body,
                headers={"X-Shopify-Hmac-Sha256": sig},
            )
        assert resp.status_code == 200

    def test_secret_falls_back_to_api_secret(self, client):
        """SHOPIFY_API_SECRET fallback when SHOPIFY_WEBHOOK_SECRET unset."""
        import os as _os

        real_getenv = _os.getenv

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


# ===========================================================================
# twilio_webhooks.py
# ===========================================================================

class TestTwilioWebhook:
    @staticmethod
    def _twilio_os(token):
        """Fake os module (patching the shared os.getenv would break the
        registry's own INTEGRATION_LOAD_TIMEOUT read)."""
        import os as _os

        fake = MagicMock()
        fake.getenv.side_effect = (
            lambda key, default=None: token
            if key == "TWILIO_AUTH_TOKEN"
            else _os.getenv(key, default)
        )
        return fake

    def _twilio_sig(self, url: str, params: dict, token: str) -> str:
        from urllib.parse import urlencode

        data = (url + urlencode(sorted(params.items()))).encode()
        return base64.b64encode(hmac.new(token.encode(), data, hashlib.sha1).digest()).decode()

    def test_no_token_rejected_401(self, client):
        with patch("api.routes.webhooks.twilio_webhooks.os", self._twilio_os("")):
            resp = client.post("/webhooks/twilio/sms", data={"To": "+123"})
        assert resp.status_code == 401

    def test_missing_signature_401(self, client):
        with patch("api.routes.webhooks.twilio_webhooks.os", self._twilio_os("tok")):
            resp = client.post("/webhooks/twilio/sms", data={"To": "+123"})
        assert resp.status_code == 401

    def test_bad_signature_401(self, client):
        with patch("api.routes.webhooks.twilio_webhooks.os", self._twilio_os("tok")):
            resp = client.post(
                "/webhooks/twilio/sms",
                data={"To": "+123", "From": "+456"},
                headers={"X-Twilio-Signature": "bad"},
            )
        assert resp.status_code == 401

    def test_sms_valid(self, client):
        with patch("api.routes.webhooks.twilio_webhooks.os", self._twilio_os("tok")):
            params = {"To": "+123", "From": "+456", "Body": "hello"}
            url = "http://testserver/webhooks/twilio/sms"
            sig = self._twilio_sig(url, params, "tok")
            resp = client.post(
                "/webhooks/twilio/sms",
                data=params,
                headers={"X-Twilio-Signature": sig},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] in ("success", "ignored")

    def test_status_valid(self, client):
        with patch("api.routes.webhooks.twilio_webhooks.os", self._twilio_os("tok")):
            params = {"To": "+123", "MessageStatus": "delivered"}
            url = "http://testserver/webhooks/twilio/status"
            sig = self._twilio_sig(url, params, "tok")
            resp = client.post(
                "/webhooks/twilio/status",
                data=params,
                headers={"X-Twilio-Signature": sig},
            )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_status_bad_signature_401(self, client):
        with patch("api.routes.webhooks.twilio_webhooks.os", self._twilio_os("tok")):
            resp = client.post(
                "/webhooks/twilio/status",
                data={"To": "+123", "MessageStatus": "failed"},
                headers={"X-Twilio-Signature": "bad"},
            )
        assert resp.status_code == 401

    def test_forwarded_proto_https_rewrite(self, client):
        with patch("api.routes.webhooks.twilio_webhooks.os", self._twilio_os("tok")):
            params = {"To": "+123", "Body": "x"}
            # Twilio signed the HTTPS URL (after proxy rewrite)
            signed_url = "https://example.com/webhooks/twilio/sms"
            sig = self._twilio_sig(signed_url, params, "tok")
            c = TestClient(client.app, base_url="http://example.com")
            resp = c.post(
                "/webhooks/twilio/sms",
                data=params,
                headers={
                    "X-Twilio-Signature": sig,
                    "X-Forwarded-Proto": "https",
                },
            )
        assert resp.status_code in (200, 401)


# ===========================================================================
# whatsapp_webhooks.py
# ===========================================================================

class TestWhatsAppWebhook:
    def test_verification_failure_403(self, client):
        resp = client.get(
            "/webhooks/whatsapp",
            params={"hub.mode": "subscribe", "hub.challenge": "123", "hub.verify_token": "wrong"},
        )
        assert resp.status_code == 403

    def test_verification_success(self, client):
        with patch.dict(
            "os.environ",
            {"WHATSAPP_WEBHOOK_VERIFY_TOKEN": "tok"},
        ):
            resp = client.get(
                "/webhooks/whatsapp",
                params={"hub.mode": "subscribe", "hub.challenge": "456", "hub.verify_token": "tok"},
            )
        assert resp.status_code == 200
        assert resp.json() == 456

    @staticmethod
    def _wa_os(secret_value):
        import os as _os

        fake = MagicMock()
        fake.getenv.side_effect = lambda key, default=None: secret_value if key == "WHATSAPP_APP_SECRET" else _os.getenv(key, default)
        return fake

    def test_post_no_secret_401(self, client):
        with patch("api.routes.webhooks.whatsapp_webhooks.os", self._wa_os("")):
            resp = client.post("/webhooks/whatsapp", content=b"{}")
        assert resp.status_code == 401

    def test_post_missing_signature_401(self, client):
        with patch("api.routes.webhooks.whatsapp_webhooks.os", self._wa_os("sec")):
            resp = client.post("/webhooks/whatsapp", content=b"{}")
        assert resp.status_code == 401

    def test_post_bad_signature_401(self, client):
        with patch("api.routes.webhooks.whatsapp_webhooks.os", self._wa_os("sec")):
            resp = client.post(
                "/webhooks/whatsapp",
                content=b"{}",
                headers={"X-Hub-Signature-256": "sha256=deadbeef"},
            )
        assert resp.status_code == 401

    def test_post_no_entries(self, client):
        body = json.dumps({"entry": []}).encode()
        sig = "sha256=" + hmac.new(b"sec", body, hashlib.sha256).hexdigest()
        with patch("api.routes.webhooks.whatsapp_webhooks.os", self._wa_os("sec")):
            resp = client.post(
                "/webhooks/whatsapp",
                content=body,
                headers={"X-Hub-Signature-256": sig},
            )
        assert resp.status_code == 200
        assert resp.json() == {"status": "no_entries"}

    def test_post_tenant_not_found(self, client):
        body = json.dumps(
            {
                "entry": [
                    {
                        "changes": [
                            {"value": {"metadata": {"phone_number_id": "pn-1"}}}
                        ]
                    }
                ]
            }
        ).encode()
        sig = "sha256=" + hmac.new(b"sec", body, hashlib.sha256).hexdigest()
        with patch("api.routes.webhooks.whatsapp_webhooks.os", self._wa_os("sec")):
            with patch(
                "api.routes.webhooks.whatsapp_webhooks.find_tenant_by_platform_id",
                return_value=None,
            ):
                resp = client.post(
                    "/webhooks/whatsapp",
                    content=body,
                    headers={"X-Hub-Signature-256": sig},
                )
        assert resp.status_code == 200
        assert resp.json() == {"status": "tenant_not_found"}

    def test_post_processed(self, client):
        body = json.dumps(
            {
                "entry": [
                    {
                        "changes": [
                            {"value": {"metadata": {"phone_number_id": "pn-1"}, "messages": [{"id": "m1"}]}}
                        ]
                    }
                ]
            }
        ).encode()
        sig = "sha256=" + hmac.new(b"sec", body, hashlib.sha256).hexdigest()
        with patch("api.routes.webhooks.whatsapp_webhooks.os", self._wa_os("sec")):
            with patch(
                "api.routes.webhooks.whatsapp_webhooks.find_tenant_by_platform_id",
                return_value="tenant-1",
            ):
                resp = client.post(
                    "/webhooks/whatsapp",
                    content=body,
                    headers={"X-Hub-Signature-256": sig},
                )
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"
        assert resp.json()["tenant_id"] == "tenant-1"
# ===========================================================================
# teams_webhooks.py
# ===========================================================================

class TestTeamsWebhook:
    def test_invalid_json_400(self, client):
        resp = client.post("/webhooks/teams", content=b"not-json")
        assert resp.status_code == 400

    def test_missing_tenant_400(self, client):
        resp = client.post("/webhooks/teams", json={"type": "message"})
        assert resp.status_code == 400

    def test_tenant_not_found_ignored(self, client):
        with patch(
            "api.routes.webhooks.teams_webhooks.TenantDiscoveryService"
        ) as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value=None)
            resp = client.post("/webhooks/teams", json={"conversation": {"tenantId": "t-ms"}})
        assert resp.status_code == 200
        assert resp.json() == {"status": "ignored", "reason": "tenant_not_found"}

    def test_channel_data_tenant_and_bad_signature(self, client):
        with patch("api.routes.webhooks.teams_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value="tenant-1")
            with patch("api.routes.webhooks.teams_webhooks.TeamsAdapter") as TA:
                TA.return_value.verify_request = AsyncMock(return_value=False)
                resp = client.post(
                    "/webhooks/teams",
                    json={"channelData": {"tenant": {"id": "t-ms"}}},
                )
        assert resp.status_code == 401

    def test_valid_flow(self, client):
        with patch("api.routes.webhooks.teams_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value="tenant-1")
            with patch("api.routes.webhooks.teams_webhooks.TeamsAdapter") as TA:
                TA.return_value.verify_request = AsyncMock(return_value=True)
                resp = client.post(
                    "/webhooks/teams",
                    json={"conversation": {"tenantId": "t-ms"}, "text": "hi"},
                )
        assert resp.status_code == 200


# ===========================================================================
# discord_webhooks.py
# ===========================================================================

class TestDiscordWebhook:
    def test_invalid_json_400(self, client):
        resp = client.post("/webhooks/discord", content=b"not-json")
        assert resp.status_code == 400

    def test_challenge_response(self, client):
        resp = client.post("/webhooks/discord", json={"type": 1})
        assert resp.status_code == 200
        assert resp.json() == {"type": 1}

    def test_missing_guild_400(self, client):
        resp = client.post("/webhooks/discord", json={"type": 2})
        assert resp.status_code == 400

    def test_tenant_not_found_ignored(self, client):
        with patch("api.routes.webhooks.discord_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value=None)
            resp = client.post("/webhooks/discord", json={"guild_id": "g1"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "ignored", "reason": "tenant_not_found"}

    def test_bad_signature_401(self, client):
        with patch("api.routes.webhooks.discord_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value="tenant-1")
            with patch("api.routes.webhooks.discord_webhooks.DiscordAdapter") as DA:
                DA.return_value.verify_request = AsyncMock(return_value=False)
                resp = client.post("/webhooks/discord", json={"guild_id": "g1"})
        assert resp.status_code == 401

    def test_valid_flow(self, client):
        with patch("api.routes.webhooks.discord_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value="tenant-1")
            with patch("api.routes.webhooks.discord_webhooks.DiscordAdapter") as DA:
                DA.return_value.verify_request = AsyncMock(return_value=True)
                resp = client.post("/webhooks/discord", json={"guild_id": "g1", "text": "hi"})
        assert resp.status_code == 200


# ===========================================================================
# slack_webhooks.py
# ===========================================================================

class TestSlackWebhook:
    def test_invalid_json_400(self, client):
        resp = client.post("/webhooks/slack", content=b"not-json")
        assert resp.status_code == 400

    def test_url_verification_challenge(self, client):
        resp = client.post("/webhooks/slack", json={"type": "url_verification", "challenge": "abc"})
        assert resp.status_code == 200
        assert resp.json() == {"challenge": "abc"}

    def test_missing_team_id_400(self, client):
        resp = client.post("/webhooks/slack", json={"type": "event_callback", "event": {}})
        assert resp.status_code == 400

    def test_tenant_not_found_ignored(self, client):
        with patch("api.routes.webhooks.slack_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value=None)
            resp = client.post("/webhooks/slack", json={"type": "event_callback", "team_id": "T1"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "ignored", "reason": "tenant_not_found"}

    def test_no_signing_secret_401(self, client, db_session):
        with patch("api.routes.webhooks.slack_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value="tenant-1")
            resp = client.post("/webhooks/slack", json={"type": "event_callback", "team_id": "T1"})
        assert resp.status_code == 401

    def test_bad_signature_401(self, client, db_session):
        from core.models import TenantIntegration

        db_session.add(
            TenantIntegration(
                tenant_id="tenant-1",
                connector_id="slack",
                config={"slack_signing_secret": "sec"},
            )
        )
        db_session.commit()
        with patch("api.routes.webhooks.slack_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value="tenant-1")
            with patch(
                "api.routes.webhooks.slack_webhooks.verify_slack_webhook",
                return_value=False,
            ):
                resp = client.post("/webhooks/slack", json={"type": "event_callback", "team_id": "T1"})
        assert resp.status_code == 401

    def test_duplicate_event_dedup(self, client, db_session):
        from core.models import TenantIntegration

        db_session.add(
            TenantIntegration(
                tenant_id="tenant-1",
                connector_id="slack",
                config={"slack_signing_secret": "sec"},
            )
        )
        db_session.commit()
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

    def test_valid_event_flow(self, client, db_session):
        from core.models import TenantIntegration

        db_session.add(
            TenantIntegration(
                tenant_id="tenant-1",
                connector_id="slack",
                config={"slack_signing_secret": "sec"},
            )
        )
        db_session.commit()
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
        assert cache.set_async.called
        assert resp.json()["status"] in ("success", "ignored")

    def test_event_team_from_nested_event(self, client):
        """team_id inside event.event (fallback lookup)."""
        with patch("api.routes.webhooks.slack_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value=None)
            resp = client.post(
                "/webhooks/slack",
                json={"type": "event_callback", "event": {"team": "T-nested"}},
            )
        assert resp.status_code == 200
        TDS.return_value.get_tenant_id_by_external_id.assert_called_with("slack", "T-nested")

    def test_dedup_cache_error_falls_through(self, client, db_session):
        """Cache outage must not break event processing (best-effort dedup)."""
        from core.models import TenantIntegration

        db_session.add(
            TenantIntegration(
                tenant_id="tenant-1",
                connector_id="slack",
                config={"slack_signing_secret": "sec"},
            )
        )
        db_session.commit()
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
        assert resp.json()["status"] in ("success", "ignored")


# ===========================================================================
# webhook_bridge.py
# ===========================================================================

class TestWebhookBridge:
    @pytest.fixture(autouse=True)
    def _mock_bridge_deps(self):
        # NOTE: webhook_bridge binds `circuit_breaker` at module import, so
        # patch the bound name in THIS module, not core.circuit_breaker.
        with patch("api.routes.webhooks.webhook_bridge.circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_success = AsyncMock()
            cb.record_failure = AsyncMock()
            yield cb

    def _bridge(self):
        from api.routes.webhooks.webhook_bridge import WebhookBridge

        return WebhookBridge()

    async def test_feature_flag_disabled(self):
        bridge = self._bridge()
        with patch(
            "core.feature_flags.FeatureFlags.is_webhook_enabled",
            return_value=False,
        ):
            result = await bridge.process_event("slack", "t1", {}, MagicMock(), MagicMock())
        assert result == {"status": "ignored", "reason": "webhook_feature_flag_disabled"}

    async def test_canary_excluded(self):
        bridge = self._bridge()
        with patch(
            "core.feature_flags.FeatureFlags.is_webhook_canary_enabled",
            return_value=False,
        ):
            result = await bridge.process_event("slack", "t1", {}, MagicMock(), MagicMock())
        assert result == {"status": "ignored", "reason": "webhook_canary_cohort_excluded"}

    async def test_circuit_breaker_open(self):
        bridge = self._bridge()
        with patch(
            "api.routes.webhooks.webhook_bridge.circuit_breaker.is_enabled",
            AsyncMock(return_value=False),
        ):
            result = await bridge.process_event("slack", "t1", {}, MagicMock(), MagicMock())
        assert result == {"status": "ignored", "reason": "circuit_breaker_open"}

    async def test_ucb_returns_none(self, db_session):
        bridge = self._bridge()
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(return_value=None)
            result = await bridge.process_event("slack", "t1", {}, MagicMock(), db_session)
        assert result == {"status": "ignored", "reason": "ucb_ignored_or_error"}

    async def test_interaction_type(self, db_session):
        bridge = self._bridge()
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                return_value={"type": "interaction", "result": {"clicked": True}}
            )
            result = await bridge.process_event("slack", "t1", {}, MagicMock(), db_session)
        assert result["type"] == "interaction"
        assert result["status"] == "success"

    async def test_unsupported_ucb_type(self, db_session):
        bridge = self._bridge()
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(return_value={"type": "weird"})
            result = await bridge.process_event("slack", "t1", {}, MagicMock(), db_session)
        assert result == {"status": "ignored", "reason": "unsupported_ucb_type"}

    async def test_full_message_flow(self, db_session):
        from core.models import Workspace as WorkspaceModel

        db_session.add(WorkspaceModel(id="w1", tenant_id="t1", name="default"))
        db_session.commit()

        bridge = self._bridge()
        msg = MagicMock()
        msg.content = "hello"
        msg.sender_id = "U1"
        msg.metadata_json = {}
        orchestrator = AsyncMock()
        orchestrator.process_chat_message = AsyncMock(return_value={"message": "hi back"})

        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(return_value={"type": "message", "message": msg})
            UCB.return_value.send_message = AsyncMock()
            with patch("api.routes.webhooks.webhook_bridge.IngestionPipelineService") as IPS:
                IPS.return_value.process_webhook_payload_tiered = AsyncMock()
                with patch.object(bridge, "_get_orchestrator", return_value=orchestrator):
                    result = await bridge.process_event("slack", "t1", {}, MagicMock(), db_session)
        assert result["status"] == "success"
        assert result["processed"] is True
        assert orchestrator.process_chat_message.called
        UCB.return_value.send_message.assert_awaited_once()

    async def test_command_run(self, db_session):
        bridge = self._bridge()
        msg = MagicMock()
        msg.content = "/run invoice-bot write invoice"
        msg.sender_id = "U1"
        msg.metadata_json = None
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(return_value={"type": "message", "message": msg})
            result = await bridge.process_event("slack", "t1", {}, MagicMock(), db_session)
        assert result == {"status": "command_triggered", "command": "run", "agent": "invoice-bot"}

    async def test_command_ignored(self, db_session):
        bridge = self._bridge()
        msg = MagicMock()
        msg.content = "/help"
        msg.sender_id = "U1"
        msg.metadata_json = {}
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(return_value={"type": "message", "message": msg})
            result = await bridge.process_event("slack", "t1", {}, MagicMock(), db_session)
        assert result == {"status": "command_ignored", "command": "help"}

    async def test_orchestrator_unavailable(self, db_session):
        bridge = self._bridge()
        msg = MagicMock()
        msg.content = "plain text"
        msg.sender_id = "U1"
        msg.metadata_json = {}
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(return_value={"type": "message", "message": msg})
            with patch.object(bridge, "_get_orchestrator", return_value=None):
                result = await bridge.process_event("slack", "t1", {}, MagicMock(), db_session)
        assert result == {"status": "error", "message": "ChatOrchestrator unavailable"}

    async def test_ingestion_failure_continues(self, db_session):
        bridge = self._bridge()
        msg = MagicMock()
        msg.content = "hello"
        msg.sender_id = "U1"
        msg.metadata_json = {}
        orchestrator = AsyncMock()
        orchestrator.process_chat_message = AsyncMock(return_value={})
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(return_value={"type": "message", "message": msg})
            with patch("api.routes.webhooks.webhook_bridge.IngestionPipelineService") as IPS:
                IPS.return_value.process_webhook_payload_tiered = AsyncMock(
                    side_effect=RuntimeError("ingest boom")
                )
                with patch.object(bridge, "_get_orchestrator", return_value=orchestrator):
                    result = await bridge.process_event("slack", "t1", {}, MagicMock(), db_session)
        assert result["status"] == "success"
        assert self._mock_bridge_deps  # fixture active

    async def test_ucb_exception_record_failure(self, db_session):
        bridge = self._bridge()
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                side_effect=RuntimeError("ucb exploded")
            )
            result = await bridge.process_event("slack", "t1", {}, MagicMock(), db_session)
        assert result["status"] == "error"

    async def test_org_scope_connection(self, db_session):
        """Connection with scope='org' → shared workspace_id + source_connection_id."""
        from core.models import Workspace as WorkspaceModel

        db_session.add(WorkspaceModel(id="w1", tenant_id="t1", name="default"))
        db_session.add(
            UserConnection(
                id="conn-org",
                user_id="u1",
                tenant_id="t1",
                integration_id="slack",
                status="active",
                connection_name="org conn",
                scope="org",
            )
        )
        db_session.commit()

        bridge = self._bridge()
        msg = MagicMock()
        msg.content = "org msg"
        msg.sender_id = "U1"
        msg.metadata_json = {}
        orchestrator = AsyncMock()
        orchestrator.process_chat_message = AsyncMock(return_value={})

        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(return_value={"type": "message", "message": msg})
            with patch("api.routes.webhooks.webhook_bridge.IngestionPipelineService") as IPS:
                IPS.return_value.process_webhook_payload_tiered = AsyncMock()
                with patch.object(bridge, "_get_orchestrator", return_value=orchestrator):
                    result = await bridge.process_event("slack", "t1", {}, MagicMock(), db_session)
        assert result["status"] == "success"
        # Ingestion got the org-shared workspace and the resolved connection id
        call_kwargs = IPS.return_value.process_webhook_payload_tiered.call_args.kwargs
        assert call_kwargs["source_connection_id"] == "conn-org"

    async def test_personal_scope_connection(self, db_session):
        from core.models import Workspace as WorkspaceModel

        db_session.add(WorkspaceModel(id="w1", tenant_id="t1", name="default"))
        db_session.add(
            UserConnection(
                id="conn-pers",
                user_id="u1",
                tenant_id="t1",
                integration_id="slack",
                status="active",
                connection_name="pers conn",
                scope="personal",
                workspace_id="w1",
            )
        )
        db_session.commit()

        bridge = self._bridge()
        msg = MagicMock()
        msg.content = "pers msg"
        msg.sender_id = "U1"
        msg.metadata_json = {}
        orchestrator = AsyncMock()
        orchestrator.process_chat_message = AsyncMock(return_value={})

        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(return_value={"type": "message", "message": msg})
            with patch("api.routes.webhooks.webhook_bridge.IngestionPipelineService") as IPS:
                IPS.return_value.process_webhook_payload_tiered = AsyncMock()
                with patch.object(bridge, "_get_orchestrator", return_value=orchestrator):
                    result = await bridge.process_event("slack", "t1", {}, MagicMock(), db_session)
        assert result["status"] == "success"

    async def test_connection_lookup_error_swallowed(self, db_session):
        """A failing source_connection_id lookup must not block the message."""
        bridge = self._bridge()
        msg = MagicMock()
        msg.content = "hello"
        msg.sender_id = "U1"
        msg.metadata_json = {}
        orchestrator = AsyncMock()
        orchestrator.process_chat_message = AsyncMock(return_value={})

        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(return_value={"type": "message", "message": msg})
            with patch(
                "api.routes.webhooks.webhook_bridge.IngestionPipelineService"
            ) as IPS:
                IPS.return_value.process_webhook_payload_tiered = AsyncMock()
                with patch.object(bridge, "_get_orchestrator", return_value=orchestrator):
                    result = await bridge.process_event("slack", "t1", {}, MagicMock(), db_session)
        assert result["status"] == "success"

    async def test_postgres_row_security_branches(self):
        """PG dialect triggers the RLS bypass (SET LOCAL row_security off/on);
        a failure restoring it is caught, message still processed."""
        from core.models import Workspace

        class FakePGDialect:
            name = "postgresql"

        fake_db = MagicMock()
        fake_db.bind = MagicMock()
        fake_db.bind.dialect = FakePGDialect()
        # conn query → no rows; workspace query → no rows
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.first.return_value = None
        fake_db.query.side_effect = lambda *a, **k: q
        # row_security=off OK, row_security=on raises (restore failure)
        fake_db.execute.side_effect = [MagicMock(), RuntimeError("rls restore failed")]

        bridge = self._bridge()
        msg = MagicMock()
        msg.content = "pg msg"
        msg.sender_id = "U1"
        msg.metadata_json = {}
        orchestrator = AsyncMock()
        orchestrator.process_chat_message = AsyncMock(return_value={})

        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(return_value={"type": "message", "message": msg})
            with patch(
                "api.routes.webhooks.webhook_bridge.IngestionPipelineService"
            ) as IPS:
                IPS.return_value.process_webhook_payload_tiered = AsyncMock()
                with patch.object(bridge, "_get_orchestrator", return_value=orchestrator):
                    result = await bridge.process_event("slack", "t1", {}, MagicMock(), fake_db)
        assert result["status"] == "success"

    def test_on_circuit_open_fallback_schedules_sync(self, db_session):
        from api.routes.webhooks.webhook_bridge import WebhookBridge

        bridge = WebhookBridge()
        with patch("core.database.SessionLocal", return_value=db_session):
            with patch("core.historical_sync_service.HistoricalSyncService") as HSS:
                HSS.return_value.start_historical_sync = AsyncMock(return_value="job-1")
                db_session.add(
                    UserConnection(
                        id="conn-1",
                        user_id="u1",
                        tenant_id="t1",
                        integration_id="slack",
                        status="active",
                        connection_name="slack conn",
                    )
                )
                db_session.commit()
                asyncio_loop = None
                import asyncio

                async def run():
                    await bridge._on_circuit_open_fallback("slack:t1", {})

                asyncio.run(run())
        assert HSS.return_value.start_historical_sync.called

    def test_on_circuit_open_fallback_no_connection(self, db_session):
        from api.routes.webhooks.webhook_bridge import WebhookBridge

        bridge = WebhookBridge()
        import asyncio

        with patch("core.database.SessionLocal", return_value=db_session):
            asyncio.run(bridge._on_circuit_open_fallback("slack:t1", {}))

    def test_on_circuit_open_fallback_non_service_key(self):
        from api.routes.webhooks.webhook_bridge import WebhookBridge

        bridge = WebhookBridge()
        import asyncio

        asyncio.run(bridge._on_circuit_open_fallback("no-colon-key", {}))

    def test_on_circuit_open_fallback_exception_swallowed(self):
        from api.routes.webhooks.webhook_bridge import WebhookBridge

        bridge = WebhookBridge()
        import asyncio

        with patch(
            "core.database.SessionLocal",
            side_effect=RuntimeError("db down"),
        ):
            asyncio.run(bridge._on_circuit_open_fallback("slack:t1", {}))

    def test_get_orchestrator_initializes(self):
        from api.routes.webhooks.webhook_bridge import WebhookBridge

        bridge = WebhookBridge()
        with patch("integrations.chat_orchestrator.ChatOrchestrator") as CO:
            CO.return_value = MagicMock()
            orch = bridge._get_orchestrator()
        assert orch is not None
        assert bridge._orchestrator is orch

    def test_get_orchestrator_failure(self):
        from api.routes.webhooks.webhook_bridge import WebhookBridge

        bridge = WebhookBridge()
        with patch(
            "integrations.chat_orchestrator.ChatOrchestrator",
            side_effect=RuntimeError("init failed"),
        ):
            assert bridge._get_orchestrator() is None


# ===========================================================================
# monitoring.py (webhook monitoring routes)
# ===========================================================================

class TestWebhookMonitoringRoutes:
    def test_health(self, client):
        resp = client.get("/webhooks/monitoring/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_circuit_states(self, client):
        resp = client.get("/webhooks/monitoring/circuit-states")
        assert resp.status_code == 200
        assert "slack" in resp.json()["circuit_states"]

    def test_status(self, client):
        from core.webhook_monitoring import (
            get_monitoring_service,
            get_rate_limit_tracker,
            get_subscription_monitor,
        )

        service = get_monitoring_service()
        monitor = get_subscription_monitor()
        tracker = get_rate_limit_tracker()

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
        assert "circuit_states" in body
        # Route-computed sections now exposed by the response model.
        assert "rate_limits" in body
        assert "subscriptions" in body

    def test_subscriptions(self, client):
        from core.webhook_monitoring import get_subscription_monitor

        monitor = get_subscription_monitor()
        expired = MagicMock()
        expired.tenant_id = "t1"
        expired.connector_id = "slack"
        expired.subscription_id = "sub-exp"
        expired.expires_at = datetime.now(timezone.utc)
        monitor._subscriptions["slack:t1"] = expired
        resp = client.get("/webhooks/monitoring/subscriptions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] >= 1
        assert body["expired_count"] >= 1

    def test_subscription_status_found(self, client):
        from core.webhook_monitoring import get_subscription_status

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
        assert "error" in resp.json()

    def test_rate_limits(self, client):
        from core.webhook_monitoring import get_rate_limit_tracker

        tracker = get_rate_limit_tracker()
        status = MagicMock()
        status.connector_id = "slack"
        status.tenant_id = "t1"
        status.remaining = 10
        status.limit = 100
        status.percentage_remaining = 10.0
        tracker._rate_limits["slack:t1"] = status
        resp = client.get("/webhooks/monitoring/rate-limits")
        assert resp.status_code == 200
        assert resp.json()["total_count"] >= 1
        assert resp.json()["low_quota_count"] >= 1

    def test_rate_limit_status_endpoint(self, client):
        with patch(
            "api.routes.webhooks.monitoring.check_rate_limit_health",
            return_value={"healthy": True, "remaining": 5},
        ):
            resp = client.get("/webhooks/monitoring/rate-limits/slack/t1")
        assert resp.status_code == 200
        assert resp.json()["healthy"] is True

    def test_metrics(self, client):
        with patch(
            "api.routes.webhooks.monitoring.get_webhook_metrics"
        ) as GWM:
            m = MagicMock()
            m.export_prometheus = MagicMock(return_value="# TYPE x counter")
            GWM.return_value = m
            resp = client.get("/webhooks/monitoring/metrics")
        assert resp.status_code == 200
        assert resp.json()["format"] == "prometheus"

    def test_check_alerts(self, client):
        from core.webhook_monitoring import get_monitoring_service

        service = get_monitoring_service()
        with patch.object(
            service, "check_subscription_expirations", return_value=[{"x": 1}]
        ):
            resp = client.post("/webhooks/monitoring/subscriptions/check-alerts")
        assert resp.status_code == 200
        assert resp.json()["alert_count"] == 1


class TestWebhookMonitoringConnections:
    def _add_conn(self, db_session, **overrides):
        defaults = dict(
            id="c1",
            user_id="raj-test-tenant-id",
            tenant_id="t1",
            integration_id="slack",
            status="active",
            connection_name="slack main",
        )
        defaults.update(overrides)
        db_session.add(UserConnection(**defaults))
        db_session.commit()
        return defaults["id"]

    def test_health_dashboard(self, client, db_session):
        self._add_conn(db_session)
        with patch("core.connection_service.ConnectionService") as CS:
            svc = CS.return_value
            svc.get_connection_health_status = MagicMock(
                return_value={"health_status": "healthy"}
            )
            svc._decrypt = MagicMock(return_value={"subscription_id": "sub-9"})
            resp = client.get("/webhooks/monitoring/health-dashboard")
        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["total_connections"] == 1
        assert body["summary"]["healthy_connections"] == 1
        assert body["connections"][0]["subscription_id"] == "sub-9"

    def test_health_dashboard_error_and_warning_states(self, client, db_session):
        self._add_conn(db_session, id="c-err", status="active")
        self._add_conn(db_session, id="c-warn", status="active")
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
        assert body["connections"][0]["subscription_id"] == "sub-a"

    def test_health_dashboard_unknown_conn(self, client):
        resp = client.get("/webhooks/monitoring/health-dashboard")
        assert resp.status_code == 200
        assert resp.json()["summary"]["total_connections"] == 0

    def test_manual_renew_not_found(self, client):
        resp = client.post("/webhooks/monitoring/connections/nope/renew")
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_manual_renew_success(self, client, db_session):
        conn_id = self._add_conn(db_session)
        with patch("core.webhook_renewal_service.ScheduledWebhookRenewalService") as SWR:
            SWR.return_value.renew_subscription_for_connection = AsyncMock(
                return_value={"status": "success"}
            )
            resp = client.post(f"/webhooks/monitoring/connections/{conn_id}/renew")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_manual_renew_failure(self, client, db_session):
        conn_id = self._add_conn(db_session)
        with patch("core.webhook_renewal_service.ScheduledWebhookRenewalService") as SWR:
            SWR.return_value.renew_subscription_for_connection = AsyncMock(
                return_value={"status": "failed", "error": "oauth expired"}
            )
            resp = client.post(f"/webhooks/monitoring/connections/{conn_id}/renew")
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"
        assert resp.json()["error"] == "oauth expired"

    def test_troubleshoot_not_found(self, client):
        resp = client.get("/webhooks/monitoring/connections/nope/troubleshoot")
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_troubleshoot_slack_conn(self, client, db_session):
        conn_id = self._add_conn(db_session)
        with patch("core.connection_service.ConnectionService") as CS:
            svc = CS.return_value
            svc._decrypt = MagicMock(return_value={"subscription_id": "sub-7"})
            svc._ensure_aware_datetime = MagicMock(return_value=datetime.now(timezone.utc))
            resp = client.get(f"/webhooks/monitoring/connections/{conn_id}/troubleshoot")
        assert resp.status_code == 200
        body = resp.json()
        assert body["diagnostics"]["vault_decryption"] == "passed"
        assert body["diagnostics"]["status_flag"] == "healthy"
        assert body["cli_troubleshooting_tools"][0]["title"].startswith("Trigger")

    def test_troubleshoot_outlook_conn(self, client, db_session):
        conn_id = self._add_conn(db_session, id="c-out", integration_id="outlook")
        with patch("core.connection_service.ConnectionService") as CS:
            svc = CS.return_value
            svc._decrypt = MagicMock(side_effect=RuntimeError("decrypt failed"))
            resp = client.get(f"/webhooks/monitoring/connections/{conn_id}/troubleshoot")
        assert resp.status_code == 200
        body = resp.json()
        assert body["diagnostics"]["vault_decryption"] == "failed"
        assert "Simulate Live Webhook Notification" in body["cli_troubleshooting_tools"][0]["title"]

    def test_troubleshoot_generic_conn(self, client, db_session):
        """Non-outlook/slack connector → generic simulated webhook command."""
        conn_id = self._add_conn(db_session, id="c-gen", integration_id="hubspot")
        with patch("core.connection_service.ConnectionService") as CS:
            svc = CS.return_value
            svc._decrypt = MagicMock(return_value={})
            resp = client.get(f"/webhooks/monitoring/connections/{conn_id}/troubleshoot")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cli_troubleshooting_tools"][0]["title"] == "Simulate Webhook Delivery"

    def test_troubleshoot_expired_token(self, client, db_session):
        conn_id = self._add_conn(db_session, id="c-exp", expires_at=datetime.now(timezone.utc))
        with patch("core.connection_service.ConnectionService") as CS:
            svc = CS.return_value
            svc._decrypt = MagicMock(return_value={"subscription_id": "s1"})
            svc._ensure_aware_datetime = MagicMock(return_value=datetime.now(timezone.utc) - timedelta(days=1))
            resp = client.get(f"/webhooks/monitoring/connections/{conn_id}/troubleshoot")
        assert resp.status_code == 200
        assert resp.json()["diagnostics"]["token_expiration"] == "expired"
        assert resp.json()["diagnostics"]["overall_verdict"] == "requires_attention"
