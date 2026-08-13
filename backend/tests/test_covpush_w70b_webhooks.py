# -*- coding: utf-8 -*-
"""W70B — coverage push for 8 backend modules (standalone >=95% each).

Targets:
1. api/routes/webhooks/twilio_webhooks.py      (100% baseline combined)
2. api/routes/webhooks/discord_webhooks.py     (100%)
3. api/routes/webhooks/webhook_bridge.py       (100%)
4. api/routes/webhooks/teams_webhooks.py       (100%)
5. api/routes/webhooks/whatsapp_webhooks.py    (100%)
6. api/routes/webhooks/ingestion_webhooks.py   (100%)
7. integrations/adapters/hubspot_adapter.py    (53% baseline)
8. integrations/adapters/messenger_adapter.py  (23% baseline)

Style: FastAPI TestClient + app.dependency_overrides; patches use real
module names (no `backend.` prefix). Mock signatures/HMACs + httpx.
Zero LLM spend, zero network, no real DB.

Webhook conventions exercised: shared-secret auth (fail-closed when the
secret is unconfigured), HMAC/signature verification, malformed payloads,
service exceptions, tenant resolution fallbacks, PostgreSQL RLS branches.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.database import get_db

# ============================================================================
# Shared helpers
# ============================================================================


def make_webhook_client(router, db=None, registry=None, base_url=None):
    """Build a TestClient for a webhook router with overridden deps."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db if db is not None else MagicMock()
    if registry is not None:
        from api.routes.webhooks.base import get_webhook_registry

        app.dependency_overrides[get_webhook_registry] = lambda: registry
    kwargs = {"raise_server_exceptions": False}
    if base_url is not None:
        kwargs["base_url"] = base_url
    return TestClient(app, **kwargs)


def bridge_process_event(result=None):
    """Patch the shared webhook_bridge.process_event to a known result."""
    from api.routes.webhooks.webhook_bridge import webhook_bridge

    return patch.object(
        webhook_bridge,
        "process_event",
        new=AsyncMock(
            return_value={"status": "success", "processed": True}
            if result is None
            else result
        ),
    )


def _hmac_sha256(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _pg_db():
    """MagicMock db whose dialect claims postgresql -> SET LOCAL lines run."""
    db = MagicMock()
    db.bind.dialect.name = "postgresql"
    db.execute = MagicMock()
    return db


# ============================================================================
# 1. twilio_webhooks.py
# ============================================================================


class TestTwilioWebhooks:
    @staticmethod
    def _twilio_os(token):
        import os as _os

        fake = MagicMock()
        fake.getenv.side_effect = (
            lambda key, default=None: token
            if key == "TWILIO_AUTH_TOKEN"
            else _os.getenv(key, default)
        )
        return fake

    @staticmethod
    def _twilio_sig(url: str, params: dict, token: str) -> str:
        from urllib.parse import urlencode

        data = (url + urlencode(sorted(params.items()))).encode()
        return base64.b64encode(hmac.new(token.encode(), data, hashlib.sha1).digest()).decode()

    def _client(self):
        from api.routes.webhooks.twilio_webhooks import router

        return make_webhook_client(router, db=MagicMock(), registry=MagicMock())

    def test_sms_no_token_fail_closed_401(self):
        with patch("api.routes.webhooks.twilio_webhooks.os", self._twilio_os("")):
            resp = self._client().post("/twilio/sms", data={"To": "+123"})
        assert resp.status_code == 401

    def test_sms_missing_signature_401(self):
        with patch("api.routes.webhooks.twilio_webhooks.os", self._twilio_os("tok")):
            resp = self._client().post("/twilio/sms", data={"To": "+123"})
        assert resp.status_code == 401

    def test_sms_bad_signature_401(self):
        with patch("api.routes.webhooks.twilio_webhooks.os", self._twilio_os("tok")):
            resp = self._client().post(
                "/twilio/sms",
                data={"To": "+123"},
                headers={"X-Twilio-Signature": "bad"},
            )
        assert resp.status_code == 401

    def test_sms_valid_signature_dispatches(self):
        from api.routes.webhooks.twilio_webhooks import router

        params = {"To": "+123", "From": "+456", "Body": "hello"}
        url = "http://testserver/twilio/sms"
        sig = self._twilio_sig(url, params, "tok")
        with patch("api.routes.webhooks.twilio_webhooks.os", self._twilio_os("tok")):
            with bridge_process_event() as bridge:
                resp = make_webhook_client(
                    router, db=MagicMock(), registry=MagicMock()
                ).post(
                    "/twilio/sms",
                    data=params,
                    headers={"X-Twilio-Signature": sig},
                )
        assert resp.status_code == 200
        bridge.assert_awaited_once()
        assert bridge.call_args.args[:2] == ("twilio", "+123")

    def test_sms_https_proxy_rewrite(self):
        from api.routes.webhooks.twilio_webhooks import router

        params = {"To": "+123", "Body": "x"}
        signed_url = "https://example.com/twilio/sms"
        sig = self._twilio_sig(signed_url, params, "tok")
        with patch("api.routes.webhooks.twilio_webhooks.os", self._twilio_os("tok")):
            with bridge_process_event() as bridge:
                client = make_webhook_client(
                    router,
                    db=MagicMock(),
                    registry=MagicMock(),
                    base_url="http://example.com",
                )
                resp = client.post(
                    "/twilio/sms",
                    data=params,
                    headers={"X-Twilio-Signature": sig, "X-Forwarded-Proto": "https"},
                )
        assert resp.status_code == 200
        bridge.assert_awaited_once()
    def test_status_valid_signature_ok(self):
        from api.routes.webhooks.twilio_webhooks import router

        params = {"To": "+123", "MessageStatus": "delivered"}
        url = "http://testserver/twilio/status"
        sig = self._twilio_sig(url, params, "tok")
        registry = MagicMock()
        registry.execute_operation = AsyncMock(return_value={"ok": True})
        with patch("api.routes.webhooks.twilio_webhooks.os", self._twilio_os("tok")):
            resp = make_webhook_client(router, db=MagicMock(), registry=registry).post(
                "/twilio/status",
                data=params,
                headers={"X-Twilio-Signature": sig},
            )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        registry.execute_operation.assert_awaited_once_with(
            "twilio", "+123", "track_status_callback", {"data": params}
        )

    def test_status_bad_signature_401(self):
        with patch("api.routes.webhooks.twilio_webhooks.os", self._twilio_os("tok")):
            resp = self._client().post(
                "/twilio/status",
                data={"To": "+123", "MessageStatus": "failed"},
                headers={"X-Twilio-Signature": "bad"},
            )
        assert resp.status_code == 401

    def test_status_no_token_fail_closed_401(self):
        with patch("api.routes.webhooks.twilio_webhooks.os", self._twilio_os("")):
            resp = self._client().post("/twilio/status", data={"To": "+123"})
        assert resp.status_code == 401

    def test_status_tenant_default_when_no_to(self):
        from api.routes.webhooks.twilio_webhooks import router

        params = {"MessageStatus": "delivered"}
        url = "http://testserver/twilio/status"
        sig = self._twilio_sig(url, params, "tok")
        registry = MagicMock()
        registry.execute_operation = AsyncMock(return_value={"ok": True})
        with patch("api.routes.webhooks.twilio_webhooks.os", self._twilio_os("tok")):
            resp = make_webhook_client(router, db=MagicMock(), registry=registry).post(
                "/twilio/status",
                data=params,
                headers={"X-Twilio-Signature": sig},
            )
        assert resp.status_code == 200
        registry.execute_operation.assert_awaited_once_with(
            "twilio", "default", "track_status_callback", {"data": params}
        )


# ============================================================================
# 2. discord_webhooks.py
# ============================================================================


class TestDiscordWebhooks:
    def _client(self):
        from api.routes.webhooks.discord_webhooks import router

        return make_webhook_client(router, db=MagicMock())

    def test_invalid_json_400(self):
        resp = self._client().post("/discord", content=b"not-json")
        assert resp.status_code == 400

    def test_challenge_response(self):
        resp = self._client().post("/discord", json={"type": 1})
        assert resp.status_code == 200
        assert resp.json() == {"type": 1}

    def test_missing_guild_400(self):
        resp = self._client().post("/discord", json={"type": 2})
        assert resp.status_code == 400

    def test_tenant_not_found_ignored(self):
        with patch(
            "api.routes.webhooks.discord_webhooks.TenantDiscoveryService"
        ) as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value=None)
            resp = self._client().post("/discord", json={"guild_id": "g1"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "ignored", "reason": "tenant_not_found"}

    def test_bad_signature_401(self):
        with patch(
            "api.routes.webhooks.discord_webhooks.TenantDiscoveryService"
        ) as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(
                return_value="tenant-1"
            )
            with patch("api.routes.webhooks.discord_webhooks.DiscordAdapter") as DA:
                DA.return_value.verify_request = AsyncMock(return_value=False)
                resp = self._client().post("/discord", json={"guild_id": "g1"})
        assert resp.status_code == 401

    def test_valid_flow_dispatches(self):
        with patch(
            "api.routes.webhooks.discord_webhooks.TenantDiscoveryService"
        ) as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(
                return_value="tenant-1"
            )
            with patch("api.routes.webhooks.discord_webhooks.DiscordAdapter") as DA:
                DA.return_value.verify_request = AsyncMock(return_value=True)
                with bridge_process_event() as bridge:
                    resp = self._client().post(
                        "/discord", json={"guild_id": "g1", "text": "hi"}
                    )
        assert resp.status_code == 200
        bridge.assert_awaited_once()
        assert bridge.call_args.args[:2] == ("discord", "tenant-1")


# ============================================================================
# 3. teams_webhooks.py
# ============================================================================


class TestTeamsWebhooks:
    def _client(self):
        from api.routes.webhooks.teams_webhooks import router

        return make_webhook_client(router, db=MagicMock())

    def test_invalid_json_400(self):
        resp = self._client().post("/teams", content=b"not-json")
        assert resp.status_code == 400

    def test_missing_tenant_400(self):
        resp = self._client().post("/teams", json={"type": "message"})
        assert resp.status_code == 400

    def test_tenant_from_channel_data_400_when_unknown(self):
        with patch("api.routes.webhooks.teams_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(
                return_value="tenant-1"
            )
            with patch("api.routes.webhooks.teams_webhooks.TeamsAdapter") as TA:
                TA.return_value.verify_request = AsyncMock(return_value=False)
                resp = self._client().post(
                    "/teams", json={"channelData": {"tenant": {"id": "t-ms"}}}
                )
        assert resp.status_code == 401
        TDS.return_value.get_tenant_id_by_external_id.assert_awaited_once_with(
            "teams", "t-ms"
        )

    def test_tenant_not_found_ignored(self):
        with patch("api.routes.webhooks.teams_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value=None)
            resp = self._client().post(
                "/teams", json={"conversation": {"tenantId": "t-ms"}}
            )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ignored", "reason": "tenant_not_found"}

    def test_bad_signature_401(self):
        with patch("api.routes.webhooks.teams_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(
                return_value="tenant-1"
            )
            with patch("api.routes.webhooks.teams_webhooks.TeamsAdapter") as TA:
                TA.return_value.verify_request = AsyncMock(return_value=False)
                resp = self._client().post(
                    "/teams", json={"conversation": {"tenantId": "t-ms"}}
                )
        assert resp.status_code == 401

    def test_valid_flow_dispatches(self):
        with patch("api.routes.webhooks.teams_webhooks.TenantDiscoveryService") as TDS:
            TDS.return_value.get_tenant_id_by_external_id = AsyncMock(
                return_value="tenant-1"
            )
            with patch("api.routes.webhooks.teams_webhooks.TeamsAdapter") as TA:
                TA.return_value.verify_request = AsyncMock(return_value=True)
                with bridge_process_event() as bridge:
                    resp = self._client().post(
                        "/teams", json={"conversation": {"tenantId": "t-ms"}}
                    )
        assert resp.status_code == 200
        bridge.assert_awaited_once()
        assert bridge.call_args.args[:2] == ("teams", "tenant-1")


# ============================================================================
# 4. whatsapp_webhooks.py
# ============================================================================


class TestWhatsAppWebhooks:
    def _client(self):
        from api.routes.webhooks.whatsapp_webhooks import router

        return make_webhook_client(router, db=MagicMock())

    @staticmethod
    def _wa_os(secret_value):
        import os as _os

        fake = MagicMock()
        fake.getenv.side_effect = (
            lambda key, default=None: secret_value
            if key == "WHATSAPP_APP_SECRET"
            else _os.getenv(key, default)
        )
        return fake

    def test_verification_success(self):
        with patch.dict(
            os.environ, {"WHATSAPP_WEBHOOK_VERIFY_TOKEN": "tok"}
        ):
            resp = self._client().get(
                "/whatsapp",
                params={
                    "hub.mode": "subscribe",
                    "hub.challenge": "456",
                    "hub.verify_token": "tok",
                },
            )
        assert resp.status_code == 200
        assert resp.json() == 456

    def test_verification_wrong_token_403(self):
        with patch.dict(
            os.environ, {"WHATSAPP_WEBHOOK_VERIFY_TOKEN": "tok"}
        ):
            resp = self._client().get(
                "/whatsapp",
                params={
                    "hub.mode": "subscribe",
                    "hub.challenge": "456",
                    "hub.verify_token": "wrong",
                },
            )
        assert resp.status_code == 403

    def test_verification_wrong_mode_403(self):
        with patch.dict(
            os.environ, {"WHATSAPP_WEBHOOK_VERIFY_TOKEN": "tok"}
        ):
            resp = self._client().get(
                "/whatsapp",
                params={
                    "hub.mode": "unsubscribe",
                    "hub.challenge": "456",
                    "hub.verify_token": "tok",
                },
            )
        assert resp.status_code == 403

    def test_post_no_secret_fail_closed_401(self):
        with patch("api.routes.webhooks.whatsapp_webhooks.os", self._wa_os("")):
            resp = self._client().post("/whatsapp", content=b"{}")
        assert resp.status_code == 401

    def test_post_missing_signature_401(self):
        with patch("api.routes.webhooks.whatsapp_webhooks.os", self._wa_os("sec")):
            resp = self._client().post("/whatsapp", content=b"{}")
        assert resp.status_code == 401

    def test_post_bad_signature_401(self):
        with patch("api.routes.webhooks.whatsapp_webhooks.os", self._wa_os("sec")):
            resp = self._client().post(
                "/whatsapp",
                content=b"{}",
                headers={"X-Hub-Signature-256": "sha256=deadbeef"},
            )
        assert resp.status_code == 401

    def test_post_no_entries(self):
        body = json.dumps({"entry": []}).encode()
        sig = "sha256=" + hmac.new(b"sec", body, hashlib.sha256).hexdigest()
        with patch("api.routes.webhooks.whatsapp_webhooks.os", self._wa_os("sec")):
            resp = self._client().post(
                "/whatsapp",
                content=body,
                headers={"X-Hub-Signature-256": sig},
            )
        assert resp.status_code == 200
        assert resp.json() == {"status": "no_entries"}

    def test_post_malformed_json_with_valid_signature_500(self):
        body = b"not-json"
        sig = "sha256=" + hmac.new(b"sec", body, hashlib.sha256).hexdigest()
        with patch("api.routes.webhooks.whatsapp_webhooks.os", self._wa_os("sec")):
            resp = self._client().post(
                "/whatsapp",
                content=body,
                headers={"X-Hub-Signature-256": sig},
            )
        assert resp.status_code == 500

    def test_post_tenant_not_found(self):
        body = json.dumps(
            {
                "entry": [
                    {"changes": [{"value": {"metadata": {"phone_number_id": "pn-1"}}}]}
                ]
            }
        ).encode()
        sig = "sha256=" + hmac.new(b"sec", body, hashlib.sha256).hexdigest()
        with patch("api.routes.webhooks.whatsapp_webhooks.os", self._wa_os("sec")):
            with patch(
                "api.routes.webhooks.whatsapp_webhooks.find_tenant_by_platform_id",
                return_value=None,
            ):
                resp = self._client().post(
                    "/whatsapp",
                    content=body,
                    headers={"X-Hub-Signature-256": sig},
                )
        assert resp.status_code == 200
        assert resp.json() == {"status": "tenant_not_found"}

    def test_post_without_phone_number_id_tenant_not_found(self):
        body = json.dumps({"entry": [{"changes": [{"value": {}}]}]}).encode()
        sig = "sha256=" + hmac.new(b"sec", body, hashlib.sha256).hexdigest()
        with patch("api.routes.webhooks.whatsapp_webhooks.os", self._wa_os("sec")):
            with patch(
                "api.routes.webhooks.whatsapp_webhooks.find_tenant_by_platform_id",
                return_value=None,
            ):
                resp = self._client().post(
                    "/whatsapp",
                    content=body,
                    headers={"X-Hub-Signature-256": sig},
                )
        assert resp.status_code == 200
        assert resp.json() == {"status": "tenant_not_found"}

    def test_post_processed(self):
        body = json.dumps(
            {
                "entry": [
                    {
                        "changes": [
                            {
                                "value": {
                                    "metadata": {"phone_number_id": "pn-1"},
                                    "messages": [{"id": "m1"}],
                                }
                            }
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
                with bridge_process_event() as bridge:
                    resp = self._client().post(
                        "/whatsapp",
                        content=body,
                        headers={"X-Hub-Signature-256": sig},
                    )
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"
        assert resp.json()["tenant_id"] == "tenant-1"
        bridge.assert_awaited_once()
        assert bridge.call_args.args[:2] == ("whatsapp", "tenant-1")


# ============================================================================
# 5. webhook_bridge.py
# ============================================================================


class TestWebhookBridgeStandalone:
    @pytest.fixture(autouse=True)
    def _mock_cb(self):
        with patch("api.routes.webhooks.webhook_bridge.circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_success = AsyncMock()
            cb.record_failure = AsyncMock()
            yield cb

    def _bridge(self):
        from api.routes.webhooks.webhook_bridge import WebhookBridge

        return WebhookBridge()

    def _msg(self, content="hello", sender="U1", metadata_json=None):
        msg = MagicMock()
        msg.content = content
        msg.sender_id = sender
        msg.metadata_json = metadata_json if metadata_json is not None else {}
        return msg

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

    async def test_ucb_returns_none(self):
        bridge = self._bridge()
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(return_value=None)
            result = await bridge.process_event("slack", "t1", {}, MagicMock(), MagicMock())
        assert result == {"status": "ignored", "reason": "ucb_ignored_or_error"}

    async def test_interaction_type(self):
        bridge = self._bridge()
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                return_value={"type": "interaction", "result": {"clicked": True}}
            )
            result = await bridge.process_event("slack", "t1", {}, MagicMock(), MagicMock())
        assert result["status"] == "success"
        assert result["type"] == "interaction"

    async def test_unsupported_ucb_type(self):
        bridge = self._bridge()
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(return_value={"type": "weird"})
            result = await bridge.process_event("slack", "t1", {}, MagicMock(), MagicMock())
        assert result == {"status": "ignored", "reason": "unsupported_ucb_type"}

    async def test_full_message_flow_with_response(self):
        bridge = self._bridge()
        orchestrator = AsyncMock()
        orchestrator.process_chat_message = AsyncMock(return_value={"message": "hi back"})
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                return_value={"type": "message", "message": self._msg()}
            )
            UCB.return_value.send_message = AsyncMock()
            with patch("api.routes.webhooks.webhook_bridge.IngestionPipelineService") as IPS:
                IPS.return_value.process_webhook_payload_tiered = AsyncMock()
                with patch.object(bridge, "_get_orchestrator", return_value=orchestrator):
                    result = await bridge.process_event(
                        "slack", "t1", {}, MagicMock(), MagicMock()
                    )
        assert result["status"] == "success"
        assert result["processed"] is True
        orchestrator.process_chat_message.assert_awaited_once()
        UCB.return_value.send_message.assert_awaited_once()
        kwargs = orchestrator.process_chat_message.call_args.kwargs
        assert kwargs["user_id"] == "ext_U1"
        assert kwargs["session_id"] == "slack_U1"

    async def test_full_flow_with_thread_metadata(self):
        bridge = self._bridge()
        orchestrator = AsyncMock()
        orchestrator.process_chat_message = AsyncMock(return_value={"message": "hi"})
        msg = self._msg(metadata_json={"thread_id": "th-9"})
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                return_value={"type": "message", "message": msg}
            )
            UCB.return_value.send_message = AsyncMock()
            with patch("api.routes.webhooks.webhook_bridge.IngestionPipelineService") as IPS:
                IPS.return_value.process_webhook_payload_tiered = AsyncMock()
                with patch.object(bridge, "_get_orchestrator", return_value=orchestrator):
                    await bridge.process_event("slack", "t1", {}, MagicMock(), MagicMock())
        ctx = orchestrator.process_chat_message.call_args.kwargs["context"]
        assert ctx["thread_id"] == "th-9"
        send_kwargs = UCB.return_value.send_message.call_args.kwargs
        assert send_kwargs["metadata"]["thread_ts"] == "th-9"

    async def test_no_response_message_no_send(self):
        bridge = self._bridge()
        orchestrator = AsyncMock()
        orchestrator.process_chat_message = AsyncMock(return_value={})
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                return_value={"type": "message", "message": self._msg()}
            )
            with patch("api.routes.webhooks.webhook_bridge.IngestionPipelineService") as IPS:
                IPS.return_value.process_webhook_payload_tiered = AsyncMock()
                with patch.object(bridge, "_get_orchestrator", return_value=orchestrator):
                    result = await bridge.process_event(
                        "slack", "t1", {}, MagicMock(), MagicMock()
                    )
        assert result["status"] == "success"
        assert result["orchestrator_response"] == {}

    async def test_command_run_triggered(self):
        bridge = self._bridge()
        msg = self._msg(content="/run invoice-bot write invoice")
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                return_value={"type": "message", "message": msg}
            )
            result = await bridge.process_event("slack", "t1", {}, MagicMock(), MagicMock())
        assert result == {"status": "command_triggered", "command": "run", "agent": "invoice-bot"}

    async def test_command_run_default_task(self):
        bridge = self._bridge()
        msg = self._msg(content="/run invoice-bot")
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                return_value={"type": "message", "message": msg}
            )
            result = await bridge.process_event("slack", "t1", {}, MagicMock(), MagicMock())
        assert result["status"] == "command_triggered"
        assert result["agent"] == "invoice-bot"

    async def test_command_ignored(self):
        bridge = self._bridge()
        msg = self._msg(content="/help")
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                return_value={"type": "message", "message": msg}
            )
            result = await bridge.process_event("slack", "t1", {}, MagicMock(), MagicMock())
        assert result == {"status": "command_ignored", "command": "help"}

    async def test_orchestrator_unavailable(self):
        bridge = self._bridge()
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                return_value={"type": "message", "message": self._msg()}
            )
            with patch.object(bridge, "_get_orchestrator", return_value=None):
                result = await bridge.process_event("slack", "t1", {}, MagicMock(), MagicMock())
        assert result == {"status": "error", "message": "ChatOrchestrator unavailable"}

    async def test_ingestion_failure_continues(self):
        bridge = self._bridge()
        orchestrator = AsyncMock()
        orchestrator.process_chat_message = AsyncMock(return_value={})
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                return_value={"type": "message", "message": self._msg()}
            )
            with patch("api.routes.webhooks.webhook_bridge.IngestionPipelineService") as IPS:
                IPS.return_value.process_webhook_payload_tiered = AsyncMock(
                    side_effect=RuntimeError("ingest boom")
                )
                with patch.object(bridge, "_get_orchestrator", return_value=orchestrator):
                    result = await bridge.process_event(
                        "slack", "t1", {}, MagicMock(), MagicMock()
                    )
        assert result["status"] == "success"

    async def test_ucb_exception_records_failure(self, _mock_cb):
        bridge = self._bridge()
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                side_effect=RuntimeError("ucb exploded")
            )
            result = await bridge.process_event("slack", "t1", {}, MagicMock(), MagicMock())
        assert result["status"] == "error"
        _mock_cb.record_failure.assert_awaited()

    async def test_no_connection_no_workspace_flow(self):
        """No conn row and no workspace row -> workspace_id falls back to tenant_id."""
        bridge = self._bridge()
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        db.query.return_value.filter.return_value.first.return_value = None
        orchestrator = AsyncMock()
        orchestrator.process_chat_message = AsyncMock(return_value={})
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                return_value={"type": "message", "message": self._msg()}
            )
            with patch("api.routes.webhooks.webhook_bridge.IngestionPipelineService") as IPS:
                IPS.return_value.process_webhook_payload_tiered = AsyncMock()
                with patch.object(bridge, "_get_orchestrator", return_value=orchestrator):
                    result = await bridge.process_event("slack", "t1", {}, MagicMock(), db)
        assert result["status"] == "success"
        call_kwargs = IPS.return_value.process_webhook_payload_tiered.call_args.kwargs
        assert call_kwargs["source_connection_id"] is None
        assert IPS.call_args.kwargs["workspace_id"] == "t1"

    async def test_org_scope_connection(self):
        bridge = self._bridge()
        db = MagicMock()
        conn = MagicMock()
        conn.scope = "org"
        conn.id = "conn-org"
        workspace = MagicMock()
        workspace.id = "w-org"
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = conn
        db.query.return_value.filter.return_value.first.return_value = workspace
        orchestrator = AsyncMock()
        orchestrator.process_chat_message = AsyncMock(return_value={})
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                return_value={"type": "message", "message": self._msg()}
            )
            with patch("api.routes.webhooks.webhook_bridge.IngestionPipelineService") as IPS:
                IPS.return_value.process_webhook_payload_tiered = AsyncMock()
                with patch.object(bridge, "_get_orchestrator", return_value=orchestrator):
                    result = await bridge.process_event("slack", "t1", {}, MagicMock(), db)
        assert result["status"] == "success"
        assert IPS.call_args.kwargs["workspace_id"] == "w-org"
        assert IPS.return_value.process_webhook_payload_tiered.call_args.kwargs[
            "source_connection_id"
        ] == "conn-org"

    async def test_org_scope_no_workspace_row(self):
        bridge = self._bridge()
        db = MagicMock()
        conn = MagicMock()
        conn.scope = "org"
        conn.id = "conn-org"
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = conn
        db.query.return_value.filter.return_value.first.return_value = None
        orchestrator = AsyncMock()
        orchestrator.process_chat_message = AsyncMock(return_value={})
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                return_value={"type": "message", "message": self._msg()}
            )
            with patch("api.routes.webhooks.webhook_bridge.IngestionPipelineService") as IPS:
                IPS.return_value.process_webhook_payload_tiered = AsyncMock()
                with patch.object(bridge, "_get_orchestrator", return_value=orchestrator):
                    await bridge.process_event("slack", "t1", {}, MagicMock(), db)
        assert IPS.call_args.kwargs["workspace_id"] == "t1"

    async def test_personal_scope_connection(self):
        bridge = self._bridge()
        db = MagicMock()
        conn = MagicMock()
        conn.scope = "personal"
        conn.id = "conn-pers"
        conn.workspace_id = "w-pers"
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = conn
        orchestrator = AsyncMock()
        orchestrator.process_chat_message = AsyncMock(return_value={})
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                return_value={"type": "message", "message": self._msg()}
            )
            with patch("api.routes.webhooks.webhook_bridge.IngestionPipelineService") as IPS:
                IPS.return_value.process_webhook_payload_tiered = AsyncMock()
                with patch.object(bridge, "_get_orchestrator", return_value=orchestrator):
                    await bridge.process_event("slack", "t1", {}, MagicMock(), db)
        assert IPS.call_args.kwargs["workspace_id"] == "w-pers"
        assert IPS.return_value.process_webhook_payload_tiered.call_args.kwargs[
            "source_connection_id"
        ] == "conn-pers"

    async def test_connection_lookup_error_swallowed(self):
        bridge = self._bridge()
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = (
            RuntimeError("lookup boom")
        )
        orchestrator = AsyncMock()
        orchestrator.process_chat_message = AsyncMock(return_value={})
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                return_value={"type": "message", "message": self._msg()}
            )
            with patch("api.routes.webhooks.webhook_bridge.IngestionPipelineService") as IPS:
                IPS.return_value.process_webhook_payload_tiered = AsyncMock()
                with patch.object(bridge, "_get_orchestrator", return_value=orchestrator):
                    result = await bridge.process_event("slack", "t1", {}, MagicMock(), db)
        assert result["status"] == "success"

    async def test_postgres_row_security_branches(self):
        bridge = self._bridge()
        fake_db = MagicMock()
        fake_db.bind = MagicMock()
        fake_db.bind.dialect = MagicMock()
        fake_db.bind.dialect.name = "postgresql"
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.first.return_value = None
        fake_db.query.side_effect = lambda *a, **k: q
        fake_db.execute.side_effect = [MagicMock(), RuntimeError("rls restore failed")]
        orchestrator = AsyncMock()
        orchestrator.process_chat_message = AsyncMock(return_value={})
        with patch(
            "api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge"
        ) as UCB:
            UCB.return_value.receive_message = AsyncMock(
                return_value={"type": "message", "message": self._msg()}
            )
            with patch("api.routes.webhooks.webhook_bridge.IngestionPipelineService") as IPS:
                IPS.return_value.process_webhook_payload_tiered = AsyncMock()
                with patch.object(bridge, "_get_orchestrator", return_value=orchestrator):
                    result = await bridge.process_event("slack", "t1", {}, MagicMock(), fake_db)
        assert result["status"] == "success"

    async def test_fallback_schedules_sync(self):
        bridge = self._bridge()
        db = MagicMock()
        conn = MagicMock()
        conn.id = "conn-1"
        db.query.return_value.filter.return_value.first.return_value = conn
        with patch("core.database.SessionLocal", return_value=db):
            with patch("core.historical_sync_service.HistoricalSyncService") as HSS:
                HSS.return_value.start_historical_sync = AsyncMock(return_value="job-1")
                await bridge._on_circuit_open_fallback("slack:t1", {})
        assert HSS.return_value.start_historical_sync.called
        kwargs = HSS.return_value.start_historical_sync.call_args.kwargs
        assert kwargs["integration_id"] == "slack"
        assert kwargs["use_worker_queue"] is True

    async def test_fallback_no_connection(self):
        bridge = self._bridge()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db):
            with patch("core.historical_sync_service.HistoricalSyncService") as HSS:
                await bridge._on_circuit_open_fallback("slack:t1", {})
        assert not HSS.return_value.start_historical_sync.called

    async def test_fallback_non_service_key(self):
        bridge = self._bridge()
        await bridge._on_circuit_open_fallback("no-colon-key", {})

    async def test_fallback_exception_swallowed(self):
        bridge = self._bridge()
        with patch(
            "core.database.SessionLocal",
            side_effect=RuntimeError("db down"),
        ):
            await bridge._on_circuit_open_fallback("slack:t1", {})

    def test_get_orchestrator_initializes(self):
        bridge = self._bridge()
        with patch("integrations.chat_orchestrator.ChatOrchestrator") as CO:
            CO.return_value = MagicMock()
            orch = bridge._get_orchestrator()
        assert orch is not None
        assert bridge._orchestrator is orch

    def test_get_orchestrator_failure(self):
        bridge = self._bridge()
        with patch(
            "integrations.chat_orchestrator.ChatOrchestrator",
            side_effect=RuntimeError("init failed"),
        ):
            assert bridge._get_orchestrator() is None

    def test_unified_incoming_message_defaults(self):
        from api.routes.webhooks.webhook_bridge import UnifiedIncomingMessage

        msg = UnifiedIncomingMessage(
            platform="slack", sender_id="U1", recipient_id="bot", text="hi"
        )
        assert msg.timestamp is not None
        assert msg.thread_id is None
        assert msg.metadata == {}
        assert msg.raw_payload == {}


# ============================================================================
# 6. integrations/adapters/hubspot_adapter.py
# ============================================================================


class TestHubSpotAdapter:
    def _adapter(self, config=None):
        from integrations.adapters.hubspot_adapter import HubSpotAdapter

        with patch("integrations.adapters.hubspot_adapter.HubSpotService") as HS:
            HS.return_value = MagicMock()
            return HubSpotAdapter(tenant_id="t-1", config=config), HS

    def test_init_default_tenant_and_service(self):
        from integrations.adapters.hubspot_adapter import HubSpotAdapter

        with patch("integrations.adapters.hubspot_adapter.HubSpotService") as HS:
            adapter = HubSpotAdapter()
        assert adapter.tenant_id == "default"
        assert adapter.workspace_id == "default"
        assert adapter.config == {}
        HS.assert_called_once_with()

    def test_init_with_tenant_and_config(self):
        adapter, _ = self._adapter({"access_token": "tok"})
        assert adapter.tenant_id == "t-1"
        assert adapter.workspace_id == "t-1"
        assert adapter.config == {"access_token": "tok"}

    def test_httpx_import_guard_unavailable(self):
        """The try/except ImportError guard at import time: HTTPX_AVAILABLE
        must become False and the adapter must still construct (disabled)."""
        import importlib
        import sys

        import integrations.adapters.messenger_adapter as ma

        saved_httpx = sys.modules.get("httpx")
        saved_mod = sys.modules.get("integrations.adapters.messenger_adapter")
        try:
            sys.modules["httpx"] = None
            reloaded = importlib.reload(ma)
            assert reloaded.HTTPX_AVAILABLE is False
            adapter = reloaded.MessengerAdapter({"page_access_token": "tok"})
            assert adapter.is_enabled is False
        finally:
            if saved_httpx is not None:
                sys.modules["httpx"] = saved_httpx
            else:
                sys.modules.pop("httpx", None)
            if saved_mod is not None:
                sys.modules["integrations.adapters.messenger_adapter"] = saved_mod
                importlib.reload(saved_mod)

    def test_get_capabilities(self):
        adapter, _ = self._adapter()
        caps = adapter.get_capabilities()
        assert caps["supports_webhooks"] is True
        assert "get_contacts" in caps["operations"]
        assert caps["required_params"] == ["access_token"]

    def test_health_check(self):
        adapter, _ = self._adapter()
        health = adapter.health_check()
        assert health["healthy"] is True

    def test_get_supported_operations(self):
        adapter, _ = self._adapter()
        assert adapter.get_supported_operations() == [
            "get_contacts",
            "create_contact",
            "get_deals",
            "create_deal",
        ]

    async def test_execute_missing_token(self):
        adapter, _ = self._adapter()
        result = await adapter.execute_operation("get_contacts", {"limit": 5})
        assert result.success is False
        assert result.error.value == "AUTH_EXPIRED"
        assert "Missing HubSpot access token" in result.message

    async def test_execute_get_contacts_success(self):
        adapter, HS = self._adapter({"access_token": "tok"})
        service = HS.return_value
        service.get_contacts = AsyncMock(return_value=[{"id": "c1"}])
        result = await adapter.execute_operation("get_contacts", {"limit": 7})
        assert result.success is True
        assert result.data == {"contacts": [{"id": "c1"}]}
        service.get_contacts.assert_awaited_once_with(token="tok", limit=7)

    async def test_execute_get_contacts_token_from_params(self):
        adapter, HS = self._adapter()
        service = HS.return_value
        service.get_contacts = AsyncMock(return_value=[])
        result = await adapter.execute_operation(
            "get_contacts", {"access_token": "param-tok", "limit": 3}
        )
        assert result.success is True
        service.get_contacts.assert_awaited_once_with(token="param-tok", limit=3)

    async def test_execute_create_contact_success(self):
        adapter, HS = self._adapter({"access_token": "tok"})
        service = HS.return_value
        service.create_contact = AsyncMock(return_value={"id": "c9"})
        props = {"email": "a@b.c", "first_name": "Ann", "last_name": "B", "company": "ACME", "phone": "555"}
        result = await adapter.execute_operation("create_contact", {"properties": props})
        assert result.success is True
        assert result.data == {"id": "c9"}
        service.create_contact.assert_awaited_once_with(
            email="a@b.c",
            first_name="Ann",
            last_name="B",
            company="ACME",
            phone="555",
            token="tok",
        )

    async def test_execute_unsupported_operation(self):
        adapter, _ = self._adapter({"access_token": "tok"})
        result = await adapter.execute_operation("delete_contact", {})
        assert result.success is False
        assert result.error.value == "NOT_FOUND"

    async def test_execute_service_exception(self):
        adapter, HS = self._adapter({"access_token": "tok"})
        service = HS.return_value
        service.get_contacts = AsyncMock(side_effect=RuntimeError("api down"))
        result = await adapter.execute_operation("get_contacts", {})
        assert result.success is False
        assert result.error.value == "EXECUTION_EXCEPTION"
        assert "api down" in result.message


# ============================================================================
# 7. integrations/adapters/messenger_adapter.py
# ============================================================================


class TestMessengerAdapter:
    def _adapter(self, config=None):
        from integrations.adapters.messenger_adapter import MessengerAdapter

        return MessengerAdapter(config)

    def test_init_defaults_from_env(self):
        with patch.dict(
            os.environ,
            {
                "FACEBOOK_PAGE_ACCESS_TOKEN": "env-tok",
                "FACEBOOK_APP_SECRET": "env-secret",
            },
            clear=False,
        ):
            adapter = self._adapter()
        assert adapter.page_access_token == "env-tok"
        assert adapter.app_secret == "env-secret"
        assert adapter.verify_token == "atom_verify_token"
        assert adapter.is_enabled is True
        assert adapter.graph_api_url == "https://graph.facebook.com/v18.0"
        assert adapter.client is None

    def test_init_with_config(self):
        adapter = self._adapter(
            {
                "page_access_token": "cfg-tok",
                "app_secret": "cfg-secret",
                "verify_token": "cfg-verify",
            }
        )
        assert adapter.page_access_token == "cfg-tok"
        assert adapter.app_secret == "cfg-secret"
        assert adapter.verify_token == "cfg-verify"
        assert adapter.is_enabled is True

    def test_init_not_configured(self):
        with patch.dict(
            os.environ, {}, clear=True
        ):
            with patch(
                "integrations.adapters.messenger_adapter.HTTPX_AVAILABLE", True
            ):
                adapter = self._adapter()
        assert adapter.is_enabled is False

    async def test_get_client_unavailable(self):
        with patch("integrations.adapters.messenger_adapter.HTTPX_AVAILABLE", False):
            adapter = self._adapter()
            assert await adapter._get_client() is None

    async def test_get_client_lazy_init_and_reuse(self):
        adapter = self._adapter()
        client = MagicMock()
        with patch("httpx.AsyncClient", return_value=client) as AC:
            first = await adapter._get_client()
            second = await adapter._get_client()
        assert first is client
        assert second is client
        AC.assert_called_once_with(timeout=30.0)

    async def test_close_with_client(self):
        adapter = self._adapter()
        client = MagicMock()
        client.aclose = AsyncMock()
        adapter.client = client
        await adapter.close()
        client.aclose.assert_awaited_once()
        assert adapter.client is None

    async def test_close_without_client(self):
        adapter = self._adapter()
        await adapter.close()
        assert adapter.client is None

    def test_verify_webhook_success(self):
        adapter = self._adapter({"verify_token": "tok"})
        result = adapter.verify_webhook("subscribe", "tok", "ch-1")
        assert result == {"ok": True, "challenge": "ch-1"}

    def test_verify_webhook_bad_token(self):
        adapter = self._adapter({"verify_token": "tok"})
        result = adapter.verify_webhook("subscribe", "wrong", "ch-1")
        assert result == {"ok": False, "error": "Invalid verification token"}

    def test_verify_webhook_bad_mode(self):
        adapter = self._adapter({"verify_token": "tok"})
        result = adapter.verify_webhook("unsubscribe", "tok", "ch-1")
        assert result == {"ok": False, "error": "Invalid mode"}

    def test_verify_webhook_exception(self):
        adapter = self._adapter({"verify_token": "tok"})

        class Boom:
            def __eq__(self, other):
                raise RuntimeError("boom")

        adapter.verify_token = Boom()
        result = adapter.verify_webhook("subscribe", "tok", "ch-1")
        assert result["ok"] is False
        assert result["error"] == "boom"

    def test_verify_signature_no_secret_skips(self):
        adapter = self._adapter({"app_secret": None})
        assert adapter.verify_signature(b"payload", "anything") is True

    def test_verify_signature_valid_sha1_prefix(self):
        adapter = self._adapter({"app_secret": "sec"})
        expected = hmac.new(b"sec", b"payload", hashlib.sha1).hexdigest()
        assert adapter.verify_signature(b"payload", f"sha1={expected}") is True

    def test_verify_signature_valid_raw(self):
        adapter = self._adapter({"app_secret": "sec"})
        expected = hmac.new(b"sec", b"payload", hashlib.sha1).hexdigest()
        assert adapter.verify_signature(b"payload", expected) is True

    def test_verify_signature_mismatch(self):
        adapter = self._adapter({"app_secret": "sec"})
        assert adapter.verify_signature(b"payload", "deadbeef") is False

    def test_verify_signature_exception(self):
        adapter = self._adapter({"app_secret": "sec"})
        with patch(
            "integrations.adapters.messenger_adapter.hmac.new",
            side_effect=RuntimeError("boom"),
        ):
            assert adapter.verify_signature(b"payload", "sig") is False

    async def test_send_message_success(self):
        adapter = self._adapter({"page_access_token": "tok"})
        client = MagicMock()
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={"message_id": "mid-1"})
        client.post = AsyncMock(return_value=resp)
        adapter.client = client
        result = await adapter.send_message("psid-1", "hello")
        assert result == {
            "ok": True,
            "message_id": "mid-1",
            "recipient_id": "psid-1",
        }
        client.post.assert_awaited_once()
        kwargs = client.post.call_args.kwargs
        assert kwargs["params"] == {"access_token": "tok"}
        assert kwargs["json"]["recipient"]["id"] == "psid-1"
        assert kwargs["json"]["message"]["text"] == "hello"

    async def test_send_message_with_quick_replies(self):
        adapter = self._adapter({"page_access_token": "tok"})
        client = MagicMock()
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={"message_id": "mid-2"})
        client.post = AsyncMock(return_value=resp)
        adapter.client = client
        qr = [{"content_type": "text", "title": "Yes", "payload": "YES"}]
        await adapter.send_message("psid-1", "pick", quick_replies=qr)
        kwargs = client.post.call_args.kwargs
        assert kwargs["json"]["message"]["quick_replies"] == qr

    async def test_send_message_no_client(self):
        adapter = self._adapter({"page_access_token": None})
        with patch("integrations.adapters.messenger_adapter.HTTPX_AVAILABLE", False):
            result = await adapter.send_message("psid-1", "hello")
        assert result["ok"] is False
        assert "httpx not available" in result["error"]

    async def test_send_message_exception(self):
        adapter = self._adapter({"page_access_token": "tok"})
        client = MagicMock()
        client.post = AsyncMock(side_effect=RuntimeError("net down"))
        adapter.client = client
        result = await adapter.send_message("psid-1", "hello")
        assert result["ok"] is False
        assert result["error"] == "net down"

    async def test_send_attachment_success(self):
        adapter = self._adapter({"page_access_token": "tok"})
        client = MagicMock()
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={"message_id": "mid-3", "attachment_id": "att-1"})
        client.post = AsyncMock(return_value=resp)
        adapter.client = client
        result = await adapter.send_attachment("psid-1", "image", "https://x/y.png")
        assert result["ok"] is True
        assert result["attachment_id"] == "att-1"
        kwargs = client.post.call_args.kwargs
        assert kwargs["json"]["message"]["attachment"]["type"] == "image"

    async def test_send_attachment_no_client(self):
        adapter = self._adapter({"page_access_token": None})
        with patch("integrations.adapters.messenger_adapter.HTTPX_AVAILABLE", False):
            result = await adapter.send_attachment("psid-1", "image", "https://x/y.png")
        assert result["ok"] is False
        assert result["error"] == "Client not available"

    async def test_send_attachment_exception(self):
        adapter = self._adapter({"page_access_token": "tok"})
        client = MagicMock()
        client.post = AsyncMock(side_effect=RuntimeError("boom"))
        adapter.client = client
        result = await adapter.send_attachment("psid-1", "image", "https://x/y.png")
        assert result["ok"] is False
        assert result["error"] == "boom"

    async def test_get_user_info_success(self):
        adapter = self._adapter({"page_access_token": "tok"})
        client = MagicMock()
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(
            return_value={"first_name": "A", "last_name": "B", "profile_pic": "https://p"}
        )
        client.get = AsyncMock(return_value=resp)
        adapter.client = client
        result = await adapter.get_user_info("psid-1")
        assert result["ok"] is True
        assert result["first_name"] == "A"
        kwargs = client.get.call_args.kwargs
        assert kwargs["params"]["fields"] == "first_name,last_name,profile_pic"

    async def test_get_user_info_no_client(self):
        adapter = self._adapter({"page_access_token": None})
        with patch("integrations.adapters.messenger_adapter.HTTPX_AVAILABLE", False):
            result = await adapter.get_user_info("psid-1")
        assert result["ok"] is False
        assert result["error"] == "Client not available"

    async def test_get_user_info_exception(self):
        adapter = self._adapter({"page_access_token": "tok"})
        client = MagicMock()
        client.get = AsyncMock(side_effect=RuntimeError("boom"))
        adapter.client = client
        result = await adapter.get_user_info("psid-1")
        assert result["ok"] is False
        assert result["error"] == "boom"

    async def test_handle_webhook_no_entry(self):
        adapter = self._adapter()
        result = await adapter.handle_webhook_event({})
        assert result == {"ok": False, "error": "No entry in webhook"}

    async def test_handle_webhook_no_messaging_events(self):
        adapter = self._adapter()
        result = await adapter.handle_webhook_event({"entry": [{"messaging": []}]})
        assert result["ok"] is True
        assert result["event_type"] == "unknown"

    async def test_handle_webhook_message_event(self):
        adapter = self._adapter()
        event = {
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": "s1"},
                            "recipient": {"id": "r1"},
                            "message": {"text": "hi", "attachments": [], "mid": "m1"},
                        }
                    ]
                }
            ]
        }
        result = await adapter.handle_webhook_event(event)
        assert result["event_type"] == "message"
        assert result["text"] == "hi"
        assert result["sender_id"] == "s1"
        assert result["message_id"] == "m1"

    async def test_handle_webhook_delivery_event(self):
        adapter = self._adapter()
        event = {
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": "s1"},
                            "recipient": {"id": "r1"},
                            "delivery": {"watermark": 123, "mids": ["m1", "m2"]},
                        }
                    ]
                }
            ]
        }
        result = await adapter.handle_webhook_event(event)
        assert result["event_type"] == "delivery"
        assert result["watermark"] == 123
        assert result["message_ids"] == ["m1", "m2"]

    async def test_handle_webhook_read_event(self):
        adapter = self._adapter()
        event = {
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": "s1"},
                            "recipient": {"id": "r1"},
                            "read": {"watermark": 456},
                        }
                    ]
                }
            ]
        }
        result = await adapter.handle_webhook_event(event)
        assert result["event_type"] == "read"
        assert result["watermark"] == 456

    async def test_handle_webhook_postback_event(self):
        adapter = self._adapter()
        event = {
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": "s1"},
                            "recipient": {"id": "r1"},
                            "postback": {"payload": "BUY_NOW"},
                        }
                    ]
                }
            ]
        }
        result = await adapter.handle_webhook_event(event)
        assert result["event_type"] == "postback"
        assert result["payload"] == "BUY_NOW"

    async def test_handle_webhook_unknown_event(self):
        adapter = self._adapter()
        event = {
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": "s1"},
                            "recipient": {"id": "r1"},
                            "account_linking": {"status": "linked"},
                        }
                    ]
                }
            ]
        }
        result = await adapter.handle_webhook_event(event)
        assert result["event_type"] == "unknown"
        assert result["sender_id"] == "s1"

    async def test_handle_webhook_exception(self):
        adapter = self._adapter()
        event = MagicMock()
        event.get.side_effect = RuntimeError("boom")
        result = await adapter.handle_webhook_event(event)
        assert result == {"ok": False, "error": "boom"}

    async def test_get_capabilities(self):
        adapter = self._adapter()
        caps = await adapter.get_capabilities()
        assert caps["platform"] == "Facebook Messenger"
        assert caps["features"]["messaging"] is True
        assert caps["governance"]["autonomous"]["full_access"] is True

    async def test_get_service_status_active(self):
        adapter = self._adapter({"page_access_token": "tok"})
        status = await adapter.get_service_status()
        assert status["status"] == "active"
        assert status["configured"] is True

    async def test_get_service_status_inactive(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = self._adapter()
        status = await adapter.get_service_status()
        assert status["status"] == "inactive"
        assert status["configured"] is False


# ============================================================================
# 8. api/routes/webhooks/ingestion_webhooks.py
# ============================================================================


def _ingestion_client(db=None):
    from api.routes.webhooks import ingestion_webhooks as iw

    return iw, make_webhook_client(iw.router, db=db if db is not None else MagicMock())


def _discovery(tenant_id="tenant-1"):
    from api.routes.webhooks import ingestion_webhooks as iw

    service = MagicMock()
    service.get_tenant_id_by_external_id = AsyncMock(return_value=tenant_id)
    return patch.object(iw, "TenantDiscoveryService", return_value=service)


def _dispatch(result=None):
    import core.webhook_crud_dispatch as wcd

    if isinstance(result, Exception):
        return patch.object(
            wcd,
            "crud_dispatch",
            new=AsyncMock(side_effect=result),
        )
    return patch.object(
        wcd,
        "crud_dispatch",
        new=AsyncMock(return_value={"status": "enqueued", "records": 1} if result is None else result),
    )


def _queue():
    from api.routes.webhooks import ingestion_webhooks as iw

    queue = MagicMock()
    queue.enqueue_ingestion_job = AsyncMock(return_value="job-1")
    queue.get_queue_depth = AsyncMock(return_value=3)
    return patch.object(iw, "webhook_queue", queue)


def _integration(config=None, active=True):
    integration = MagicMock()
    integration.config = config if config is not None else {}
    integration.is_active = active
    return integration


def _conn(cid="conn-1"):
    conn = MagicMock()
    conn.id = cid
    return conn


class TestIngestionSlackWebhook:
    def test_url_verification_challenge(self):
        _, client = _ingestion_client()
        resp = client.post(
            "/webhooks/slack/events", json={"type": "url_verification", "challenge": "abc"}
        )
        assert resp.status_code == 200
        assert resp.json()["challenge"] == "abc"

    def test_missing_team_id_400(self):
        _, client = _ingestion_client()
        resp = client.post("/webhooks/slack/events", json={"type": "event_callback", "event": {}})
        assert resp.status_code == 400

    def test_team_id_from_nested_event(self):
        db = MagicMock()
        with _discovery() as discovery:
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/slack/events",
                json={"type": "event_callback", "event": {"type": "message", "team": "T2"}},
            )
        assert resp.status_code in (401, 503)
        discovery.return_value.get_tenant_id_by_external_id.assert_awaited_once_with(
            "slack", "T2"
        )

    def test_tenant_not_found_ignored(self):
        db = MagicMock()
        with _discovery(None):
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/slack/events", json={"type": "event_callback", "team_id": "T1"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_integration_not_configured_401(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with _discovery():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/slack/events", json={"type": "event_callback", "team_id": "T1"}
            )
        assert resp.status_code == 401

    def test_integration_config_empty_401(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _integration()
        with _discovery():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/slack/events", json={"type": "event_callback", "team_id": "T1"}
            )
        assert resp.status_code == 401

    def test_missing_signing_secret_503(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _integration({"other": "x"})
        with _discovery():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/slack/events", json={"type": "event_callback", "team_id": "T1"}
            )
        assert resp.status_code == 503

    def test_invalid_signature_401(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"slack_signing_secret": "secret"}
        )
        with _discovery():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/slack/events",
                json={"type": "event_callback", "team_id": "T1"},
                headers={"X-Slack-Signature": "deadbeef", "X-Slack-Request-Timestamp": "123"},
            )
        assert resp.status_code == 401

    def test_valid_signature_dispatches_with_connection(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"slack_signing_secret": "secret"}
        )
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = _conn(
            "conn-1"
        )
        payload = {"type": "event_callback", "team_id": "T1", "event": {"type": "message", "text": "hi"}}
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch() as dispatch:
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/slack/events",
                content=body,
                headers={
                    "X-Slack-Signature": _hmac_sha256(body, "secret"),
                    "X-Slack-Request-Timestamp": "123",
                },
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()
        assert dispatch.call_args.kwargs["source_connection_id"] == "conn-1"

    def test_valid_signature_crud_defaults(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"slack_signing_secret": "secret"}
        )
        payload = {"type": "event_callback", "team_id": "T1", "event": {"type": "message"}}
        body = json.dumps(payload).encode()
        import core.webhook_crud_dispatch as wcd

        with _discovery(), _dispatch(), \
             patch.object(wcd, "extract_crud_metadata", return_value=(None, None)) as extract:
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/slack/events",
                content=body,
                headers={
                    "X-Slack-Signature": _hmac_sha256(body, "secret"),
                    "X-Slack-Request-Timestamp": "123",
                },
            )
        assert resp.status_code == 200
        extract.assert_called_once()

    def test_postgres_rls_and_connection_lookup_error(self):
        db = _pg_db()
        db.query.return_value.filter.return_value.first.side_effect = [
            _integration({"slack_signing_secret": "secret"}),
        ]
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = (
            RuntimeError("boom")
        )
        payload = {"type": "event_callback", "team_id": "T1", "event": {"type": "message"}}
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/slack/events",
                content=body,
                headers={
                    "X-Slack-Signature": _hmac_sha256(body, "secret"),
                    "X-Slack-Request-Timestamp": "123",
                },
            )
        assert resp.status_code == 200
        assert db.execute.call_count >= 4

    def test_handler_exception_returns_200(self):
        db = MagicMock()
        db.query.side_effect = Exception("boom")
        with _discovery():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/slack/events", json={"type": "event_callback", "team_id": "T1"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"


class TestIngestionHubspotWebhook:
    def test_missing_portal_continue(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with _discovery(), _dispatch() as dispatch:
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/hubspot/events", json=[{"type": "contact.creation", "objectId": 1}]
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "enqueued"
        dispatch.assert_not_awaited()

    def test_tenant_not_found_continue(self):
        db = MagicMock()
        with _discovery(None), _dispatch() as dispatch:
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/hubspot/events",
                json=[{"portalId": "P1", "type": "contact.creation", "objectId": 1}],
            )
        assert resp.status_code == 200
        dispatch.assert_not_awaited()

    def test_unconfigured_fail_closed_503(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with _discovery(), _dispatch() as dispatch:
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/hubspot/events",
                json=[{"portalId": "P1", "type": "contact.creation", "objectId": 1}],
            )
        assert resp.status_code == 503
        dispatch.assert_not_awaited()

    def test_config_missing_client_secret_503(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _integration({})
        with _discovery():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/hubspot/events",
                json=[{"portalId": "P1", "type": "contact.creation", "objectId": 1}],
            )
        assert resp.status_code == 503

    def test_bad_signature_401(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        with _discovery(), _dispatch() as dispatch:
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/hubspot/events",
                json=[{"portalId": "P1", "type": "contact.creation", "objectId": 1}],
                headers={"X-HubSpot-Signature": "deadbeef"},
            )
        assert resp.status_code == 401
        dispatch.assert_not_awaited()

    def test_valid_signature_batch_dispatches(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        payload = [
            {"portalId": "P1", "type": "contact.creation", "objectId": 1},
            {"portalId": "P1", "type": "deal.updates", "objectId": 2},
        ]
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch() as dispatch:
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/hubspot/events",
                content=body,
                headers={"X-HubSpot-Signature": _hmac_sha256(body, "s3cr3t")},
            )
        assert resp.status_code == 200
        assert dispatch.await_count == 2

    def test_non_list_payload(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        payload = {"portalId": "P1", "type": "contact.creation", "objectId": 1}
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/hubspot/events",
                content=body,
                headers={"X-HubSpot-Signature": _hmac_sha256(body, "s3cr3t")},
            )
        assert resp.status_code == 200

    def test_postgres_rls_with_connection(self):
        db = _pg_db()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = _conn(
            "conn-hs"
        )
        payload = [{"portalId": "P1", "type": "contact.creation", "objectId": 1}]
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch() as dispatch:
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/hubspot/events",
                content=body,
                headers={"X-HubSpot-Signature": _hmac_sha256(body, "s3cr3t")},
            )
        assert resp.status_code == 200
        assert db.execute.call_count >= 4
        assert dispatch.call_args.kwargs["source_connection_id"] == "conn-hs"

    def test_connection_lookup_error_swallowed(self):
        db = _pg_db()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = (
            RuntimeError("boom")
        )
        payload = [{"portalId": "P1", "type": "contact.creation", "objectId": 1}]
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/hubspot/events",
                content=body,
                headers={"X-HubSpot-Signature": _hmac_sha256(body, "s3cr3t")},
            )
        assert resp.status_code == 200

    def test_dispatch_error_returns_200(self):
        db = _pg_db()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        payload = [{"portalId": "P1", "type": "contact.creation", "objectId": 1}]
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch(result=RuntimeError("boom")):
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/hubspot/events",
                content=body,
                headers={"X-HubSpot-Signature": _hmac_sha256(body, "s3cr3t")},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_crud_defaults_when_extract_returns_none(self):
        """extract_crud_metadata -> (None, None) defaults to created/generic."""
        db = _pg_db()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        import core.webhook_crud_dispatch as wcd

        payload = [{"portalId": "P1", "type": "contact.creation", "objectId": 1}]
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch() as dispatch, \
             patch.object(wcd, "extract_crud_metadata", return_value=(None, None)):
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/hubspot/events",
                content=body,
                headers={"X-HubSpot-Signature": _hmac_sha256(body, "s3cr3t")},
            )
        assert resp.status_code == 200
        kwargs = dispatch.call_args.kwargs
        assert kwargs["change_type"] == "created"
        assert kwargs["resource_id"] == "generic"


class TestIngestionSalesforceWebhook:
    def test_missing_org_id_400(self):
        with _discovery():
            _, client = _ingestion_client()
            resp = client.post("/webhooks/salesforce/events", json={"eventType": "x"})
        assert resp.status_code == 400

    def test_tenant_not_found_ignored(self):
        with _discovery(None):
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/salesforce/events", json={"orgId": "O1", "eventType": "x"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_unconfigured_fail_closed_503(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with _discovery():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/salesforce/events", json={"orgId": "O1", "eventType": "created"}
            )
        assert resp.status_code == 503

    def test_bad_signature_401(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        with _discovery():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/salesforce/events",
                json={"orgId": "O1", "eventType": "created"},
                headers={"X-Salesforce-Signature": "deadbeef"},
            )
        assert resp.status_code == 401

    def test_valid_signature_dispatches(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = _conn(
            "conn-sf"
        )
        payload = {"orgId": "O1", "eventType": "created", "objectType": "Account", "recordIds": ["a1"]}
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch() as dispatch:
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/salesforce/events",
                content=body,
                headers={"X-Salesforce-Signature": _hmac_sha256(body, "s3cr3t")},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()
        assert dispatch.call_args.kwargs["source_connection_id"] == "conn-sf"

    def test_postgres_rls_and_conn_error(self):
        db = _pg_db()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = (
            RuntimeError("boom")
        )
        payload = {"orgId": "O1", "eventType": "created"}
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/salesforce/events",
                content=body,
                headers={"X-Salesforce-Signature": _hmac_sha256(body, "s3cr3t")},
            )
        assert resp.status_code == 200

    def test_dispatch_error_returns_200(self):
        db = _pg_db()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        payload = {"orgId": "O1", "eventType": "created", "objectType": "Account"}
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch(result=RuntimeError("boom")):
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/salesforce/events",
                content=body,
                headers={"X-Salesforce-Signature": _hmac_sha256(body, "s3cr3t")},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"


class TestIngestionGmailWebhook:
    _TOKEN = "gmail-verify-tok"

    def _url(self):
        return f"/webhooks/gmail/events?token={self._TOKEN}"

    def test_unconfigured_secret_fails_closed_503(self):
        _, client = _ingestion_client()
        resp = client.post("/webhooks/gmail/events", json={"historyId": "h1"})
        assert resp.status_code == 503

    def test_wrong_token_rejected_401(self):
        with patch.dict(os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": self._TOKEN}):
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/gmail/events?token=attacker-tok", json={"historyId": "h1"}
            )
        assert resp.status_code == 401

    def test_missing_email_address_400(self):
        with patch.dict(os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": self._TOKEN}):
            _, client = _ingestion_client()
            resp = client.post(self._url(), json={"historyId": "h1"})
        assert resp.status_code == 400

    def test_tenant_not_found_ignored(self):
        with _discovery(None), patch.dict(
            os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": self._TOKEN}
        ):
            _, client = _ingestion_client()
            resp = client.post(
                self._url(), json={"historyId": "h1", "emailAddress": "a@b.c"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_success_enqueues_with_connection(self):
        db = MagicMock()
        conn = MagicMock()
        conn.id = "conn-1"
        db.query.return_value.filter.return_value.first.return_value = conn
        with _discovery(), _queue() as queue, patch.dict(
            os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": self._TOKEN}
        ):
            _, client = _ingestion_client(db)
            resp = client.post(
                self._url(), json={"historyId": "h1", "emailAddress": "a@b.c"}
            )
        assert resp.status_code == 200
        assert resp.json()["job_id"] == "job-1"
        kwargs = queue.enqueue_ingestion_job.call_args.kwargs
        assert kwargs["source_connection_id"] == "conn-1"

    def test_success_without_connection(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with _discovery(), _queue() as queue, patch.dict(
            os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": self._TOKEN}
        ):
            _, client = _ingestion_client(db)
            resp = client.post(
                self._url(), json={"historyId": "h1", "emailAddress": "a@b.c"}
            )
        assert resp.status_code == 200
        assert queue.enqueue_ingestion_job.call_args.kwargs["source_connection_id"] is None

    def test_pubsub_wrapped_payload(self):
        db = MagicMock()
        conn = MagicMock()
        conn.id = "conn-1"
        db.query.return_value.filter.return_value.first.return_value = conn
        inner = json.dumps({"historyId": "h9", "emailAddress": "a@b.c"}).encode()
        b64 = base64.b64encode(inner).decode()
        with _discovery(), _queue() as queue, patch.dict(
            os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": self._TOKEN}
        ):
            _, client = _ingestion_client(db)
            resp = client.post(
                self._url(),
                json={"message": {"data": b64, "messageId": "m1"}},
            )
        assert resp.status_code == 200
        assert queue.enqueue_ingestion_job.call_args.kwargs["payload"]["historyId"] == "h9"

    def test_pubsub_padding_fixed(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        inner = json.dumps({"historyId": "h9", "emailAddress": "a@b.c"}).encode()
        b64 = base64.b64encode(inner).decode().rstrip("=")
        with _discovery(), _queue(), patch.dict(
            os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": self._TOKEN}
        ):
            _, client = _ingestion_client(db)
            resp = client.post(
                self._url(),
                json={"message": {"data": b64, "messageId": "m1"}},
            )
        assert resp.status_code == 200

    def test_pubsub_invalid_base64_falls_through(self):
        with _discovery(None), patch.dict(
            os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": self._TOKEN}
        ):
            _, client = _ingestion_client()
            resp = client.post(
                self._url(),
                json={"message": {"data": "!!!not-base64!!!"}},
            )
        assert resp.status_code == 400

    def test_postgres_rls_branches(self):
        db = _pg_db()
        db.query.return_value.filter.return_value.first.return_value = None
        with _discovery(), _queue(), patch.dict(
            os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": self._TOKEN}
        ):
            _, client = _ingestion_client(db)
            resp = client.post(
                self._url(), json={"historyId": "h1", "emailAddress": "a@b.c"}
            )
        assert resp.status_code == 200
        assert db.execute.call_count == 2

    def test_enqueue_error_returns_200(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with _discovery(), _queue_error(), patch.dict(
            os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": self._TOKEN}
        ):
            _, client = _ingestion_client(db)
            resp = client.post(
                self._url(), json={"historyId": "h1", "emailAddress": "a@b.c"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"


def _queue_error():
    from api.routes.webhooks import ingestion_webhooks as iw

    queue = MagicMock()
    queue.enqueue_ingestion_job = AsyncMock(side_effect=RuntimeError("boom"))
    queue.get_queue_depth = AsyncMock(return_value=3)
    return patch.object(iw, "webhook_queue", queue)


class TestIngestionNotionWebhook:
    def test_missing_workspace_400(self):
        with _discovery():
            _, client = _ingestion_client()
            resp = client.post("/webhooks/notion/events", json={"type": "page.created"})
        assert resp.status_code == 400

    def test_tenant_not_found_ignored(self):
        with _discovery(None):
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/notion/events", json={"workspace_id": "W1", "type": "page.created"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_unconfigured_fail_closed_503(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with _discovery():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/notion/events", json={"workspace_id": "W1", "type": "page.created"}
            )
        assert resp.status_code == 503

    def test_bad_signature_401(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        with _discovery():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/notion/events",
                json={"workspace_id": "W1", "type": "page.created"},
                headers={"X-Notion-Signature": "deadbeef"},
            )
        assert resp.status_code == 401

    def test_valid_signature_dispatches(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            _integration({"client_secret": "s3cr3t"}),
            _conn("conn-nt"),
        ]
        payload = {"workspace_id": "W1", "type": "page.created", "id": "p1"}
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch() as dispatch:
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/notion/events",
                content=body,
                headers={"X-Notion-Signature": _hmac_sha256(body, "s3cr3t")},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()

    def test_postgres_rls_and_conn_error(self):
        db = _pg_db()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = (
            RuntimeError("boom")
        )
        payload = {"workspace_id": "W1", "type": "page.created", "id": "p1"}
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/notion/events",
                content=body,
                headers={"X-Notion-Signature": _hmac_sha256(body, "s3cr3t")},
            )
        assert resp.status_code == 200

    def test_dispatch_error_returns_200(self):
        db = _pg_db()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        payload = {"workspace_id": "W1", "type": "page.created", "id": "p1"}
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch(result=RuntimeError("boom")):
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/notion/events",
                content=body,
                headers={"X-Notion-Signature": _hmac_sha256(body, "s3cr3t")},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_crud_defaults_when_extract_returns_none(self):
        """extract_crud_metadata -> (None, None) defaults to created/generic."""
        db = _pg_db()
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        import core.webhook_crud_dispatch as wcd

        payload = {"workspace_id": "W1", "type": "page.created", "id": "p1"}
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch() as dispatch, \
             patch.object(wcd, "extract_crud_metadata", return_value=(None, None)):
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/notion/events",
                content=body,
                headers={"X-Notion-Signature": _hmac_sha256(body, "s3cr3t")},
            )
        assert resp.status_code == 200
        kwargs = dispatch.call_args.kwargs
        assert kwargs["change_type"] == "created"
        assert kwargs["resource_id"] == "generic"


class TestIngestionOutlookWebhook:
    def test_validation_token_handshake(self):
        _, client = _ingestion_client()
        resp = client.get("/webhooks/communication/outlook?validationToken=verify-123")
        assert resp.status_code == 200
        assert resp.text == "verify-123"

    def test_empty_body_lifecycle(self):
        _, client = _ingestion_client()
        resp = client.post(
            "/webhooks/communication/outlook", content=b"", headers={"content-length": "0"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_invalid_json(self):
        _, client = _ingestion_client()
        resp = client.post(
            "/webhooks/communication/outlook",
            content=b"{not json",
            headers={"content-length": "9"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_empty_notifications(self):
        _, client = _ingestion_client()
        resp = client.post("/webhooks/communication/outlook", json={"value": []})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_missing_client_state_skipped(self):
        with _queue():
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/communication/outlook",
                json={"value": [{"changeType": "created", "resource": "x"}]},
            )
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 0

    def test_invalid_client_state_fail_closed(self):
        with patch("core.webhook_security.verify_client_state", return_value=False):
            with _queue():
                _, client = _ingestion_client()
                resp = client.post(
                    "/webhooks/communication/outlook",
                    json={"value": [{"changeType": "created", "clientState": "forged"}]},
                )
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 0

    def test_valid_client_state_enqueues_with_connection(self):
        db = MagicMock()
        tenant = MagicMock()
        tenant.id = "tenant-1"
        conn = MagicMock()
        conn.id = "conn-prefix-abc"
        db.query.return_value.filter.return_value.first.side_effect = [tenant, conn]
        with patch("core.webhook_security.verify_client_state", return_value=True), \
             patch("core.webhook_security.get_client_state_data", return_value='{"c": "conn-"}'), \
             _queue() as queue:
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/communication/outlook",
                json={
                    "value": [
                        {
                            "changeType": "created",
                            "clientState": "signed-data",
                            "resource": "Users/u/Messages/m1",
                            "id": "n1",
                        }
                    ]
                },
                headers={"x-forwarded-host": "acme.example.com"},
            )
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 1
        assert queue.enqueue_ingestion_job.call_args.kwargs["source_connection_id"] == "conn-prefix-abc"

    def test_valid_client_state_no_connection_match(self):
        db = MagicMock()
        tenant = MagicMock()
        tenant.id = "tenant-1"
        db.query.return_value.filter.return_value.first.side_effect = [tenant, None]
        with patch("core.webhook_security.verify_client_state", return_value=True), \
             patch("core.webhook_security.get_client_state_data", return_value='{"c": "zzz"}'), \
             _queue() as queue:
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/communication/outlook",
                json={
                    "value": [
                        {
                            "changeType": "updated",
                            "clientState": "signed-data",
                            "resource": "Users/u/mailFolders/inbox/messages/m1",
                        }
                    ]
                },
            )
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 1
        assert queue.enqueue_ingestion_job.call_args.kwargs["source_connection_id"] is None

    def test_deletion_event(self):
        db = MagicMock()
        tenant = MagicMock()
        tenant.id = "tenant-1"
        entity = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [tenant, None]
        db.query.return_value.filter.return_value.all.return_value = [entity]
        with patch("core.webhook_security.verify_client_state", return_value=True), \
             patch("core.webhook_security.get_client_state_data", return_value='{"c": ""}'), \
             _queue():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/communication/outlook",
                json={
                    "value": [
                        {
                            "changeType": "deleted",
                            "clientState": "signed-data",
                            "resource": "Users/u/Messages/msg-42?$select=x",
                        }
                    ]
                },
            )
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 0
        db.delete.assert_called_once_with(entity)
        db.commit.assert_called()

    def test_deletion_db_error_rolls_back(self):
        db = _pg_db()
        tenant = MagicMock()
        tenant.id = "tenant-1"
        db.query.return_value.filter.return_value.first.return_value = tenant
        db.query.return_value.filter.return_value.all.side_effect = RuntimeError("boom")
        with patch("core.webhook_security.verify_client_state", return_value=True), \
             patch("core.webhook_security.get_client_state_data", return_value="{}"), \
             _queue():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/communication/outlook",
                json={
                    "value": [
                        {
                            "changeType": "deleted",
                            "clientState": "signed",
                            "resource": "Users/u/Messages/msg-9",
                        }
                    ]
                },
            )
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 0
        db.rollback.assert_called()

    def test_deletion_missing_message_id(self):
        db = MagicMock()
        tenant = MagicMock()
        tenant.id = "tenant-1"
        db.query.return_value.filter.return_value.first.return_value = tenant
        with patch("core.webhook_security.verify_client_state", return_value=True), \
             patch("core.webhook_security.get_client_state_data", return_value="{}"), \
             _queue():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/communication/outlook",
                json={"value": [{"changeType": "deleted", "clientState": "signed", "resource": ""}]},
            )
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 0

    def test_no_subdomain_skipped(self):
        with patch("core.webhook_security.verify_client_state", return_value=True), \
             patch("core.webhook_security.get_client_state_data", return_value="{}"), \
             _queue():
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/communication/outlook",
                json={"value": [{"changeType": "created", "clientState": "signed"}]},
                headers={"host": ""},
            )
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 0

    def test_no_tenant_found_skipped(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.webhook_security.verify_client_state", return_value=True), \
             patch("core.webhook_security.get_client_state_data", return_value="{}"), \
             _queue():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/communication/outlook",
                json={"value": [{"changeType": "created", "clientState": "signed"}]},
            )
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 0

    def test_loop_level_catch(self):
        db = _pg_db()
        db.query.return_value.filter.return_value.first.side_effect = RuntimeError("boom")
        with patch("core.webhook_security.verify_client_state", return_value=True), \
             patch("core.webhook_security.get_client_state_data", return_value="{}"), \
             _queue():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/communication/outlook",
                json={
                    "value": [
                        {
                            "clientState": "signed",
                            "changeType": "updated",
                            "resource": "Users/u/mailFolders/inbox/messages/m1",
                        }
                    ]
                },
            )
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 0

    def test_outer_error_non_list_value(self):
        _, client = _ingestion_client()
        resp = client.post("/webhooks/communication/outlook", json={"value": 1})
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"


class TestIngestionZohoWebhook:
    def test_unsupported_integration_400(self):
        _, client = _ingestion_client()
        resp = client.post("/webhooks/zoho/mystery", json={})
        assert resp.status_code == 400

    def test_hyphen_normalized(self):
        _, client = _ingestion_client()
        resp = client.post("/webhooks/zoho/zoho-crm", json={"orgId": "O1"})
        assert resp.status_code != 400

    def test_missing_org_400(self):
        with _discovery():
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/zoho/zoho_crm", json={"module": {"api_name": "Leads"}}
            )
        assert resp.status_code == 400

    def test_org_from_list_payload(self):
        with _discovery() as discovery, _dispatch():
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/zoho/zoho_crm",
                json=[{"orgId": "O1", "module": {"api_name": "Leads"}}],
            )
        assert resp.status_code == 200
        discovery.return_value.get_tenant_id_by_external_id.assert_awaited()

    def test_tenant_not_found_ignored(self):
        with _discovery(None):
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/zoho/zoho_crm",
                json={"orgId": "O1", "module": {"api_name": "Leads"}},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_fallback_zoho_connector(self):
        service = MagicMock()
        service.get_tenant_id_by_external_id = AsyncMock(side_effect=[None, "tenant-9"])
        from api.routes.webhooks import ingestion_webhooks as iw

        with patch.object(iw, "TenantDiscoveryService", return_value=service), _dispatch() as dispatch:
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/zoho/zoho_books",
                json={"orgId": "O1", "module": "Invoice"},
            )
        assert resp.status_code == 200
        assert service.get_tenant_id_by_external_id.await_args_list[1].args[0] == "zoho"
        dispatch.assert_awaited_once()

    def test_success_dispatches(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = _conn(
            "conn-z"
        )
        with _discovery(), _dispatch() as dispatch:
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/zoho/zoho_crm",
                json={"orgId": "O1", "module": {"api_name": "Leads"}, "key_id": "1"},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()
        assert dispatch.call_args.kwargs["integration_id"] == "zoho_crm"
        assert dispatch.call_args.kwargs["source_connection_id"] == "conn-z"

    def test_invalid_json_fallback_missing_org_400(self):
        with _discovery():
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/zoho/zoho_crm", content=b"not json", headers={"Content-Type": "application/json"}
            )
        assert resp.status_code == 400

    def test_postgres_rls_and_conn_error(self):
        db = _pg_db()
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = (
            RuntimeError("boom")
        )
        with _discovery(), _dispatch():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/zoho/zoho_crm",
                json={"orgId": "O1", "operation": "create", "data": {"id": "1"}},
            )
        assert resp.status_code == 200

    def test_dispatch_error_500(self):
        db = _pg_db()
        with _discovery(), _dispatch(result=RuntimeError("boom")):
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/zoho/zoho_crm",
                json={"orgId": "O1", "operation": "create", "data": {"id": "1"}},
            )
        assert resp.status_code == 500


class TestIngestionPmCrmWebhook:
    def test_head_handshake(self):
        _, client = _ingestion_client()
        resp = client.head("/webhooks/pm-crm/trello")
        assert resp.status_code == 200

    def test_unsupported_integration_400(self):
        _, client = _ingestion_client()
        resp = client.post("/webhooks/pm-crm/mystery", json={})
        assert resp.status_code == 400

    def test_asana_hook_secret_handshake(self):
        _, client = _ingestion_client()
        resp = client.post(
            "/webhooks/pm-crm/asana", json={}, headers={"X-Hook-Secret": "sec-1"}
        )
        assert resp.status_code == 200
        assert resp.headers["X-Hook-Secret"] == "sec-1"

    def test_monday_challenge(self):
        _, client = _ingestion_client()
        resp = client.post("/webhooks/pm-crm/monday", json={"challenge": "ch-1"})
        assert resp.status_code == 200
        assert resp.json()["challenge"] == "ch-1"

    def test_no_external_id_ignored(self):
        with _discovery():
            _, client = _ingestion_client()
            resp = client.post("/webhooks/pm-crm/jira", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_tenant_not_found_ignored(self):
        with _discovery(None):
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/pm-crm/jira", json={"clientKey": "ck-1", "issue": {"id": "1"}}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_fallback_pm_crm_connector(self):
        service = MagicMock()
        service.get_tenant_id_by_external_id = AsyncMock(side_effect=[None, "tenant-9"])
        from api.routes.webhooks import ingestion_webhooks as iw

        with patch.object(iw, "TenantDiscoveryService", return_value=service), _dispatch():
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/pm-crm/jira",
                json={"clientKey": "ck-1", "issue": {"id": "1"}},
            )
        assert resp.status_code == 200
        assert service.get_tenant_id_by_external_id.await_args_list[1].args[0] == "pm_crm"

    def test_success_dispatches(self):
        with _discovery(), _dispatch() as dispatch:
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/pm-crm/jira",
                json={"clientKey": "ck-1", "issue": {"id": "1", "key": "J-1", "fields": {}}},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()
        assert dispatch.call_args.kwargs["integration_id"] == "jira"

    def test_external_id_variants(self):
        variants = [
            {"accountId": "a1"},
            {"event": {"accountId": "a2"}},
            {"organizationId": "o1"},
            {"company_id": "c1"},
            {"team_id": "t1"},
            {"webhook_id": "w1"},
            {"account_id": "ac1"},
            {"insightly_org_id": "i1"},
            {"serverInfo": {"baseUrl": "https://jira.example.com"}},
            {"model": {"idOrganization": "org-9"}},
            {"model": {"id": "m1"}},
            {"events": [{"workspace": "ws-1"}]},
        ]
        for payload in variants:
            with _discovery() as discovery, _dispatch():
                _, client = _ingestion_client()
                resp = client.post("/webhooks/pm-crm/linear", json=payload)
            assert resp.status_code == 200
            discovery.return_value.get_tenant_id_by_external_id.assert_awaited()

    def test_query_param_external_id(self):
        with _discovery() as discovery, _dispatch():
            _, client = _ingestion_client()
            resp = client.post("/webhooks/pm-crm/jira?clientKey=ck-2", json={"issue": {"id": "1"}})
        assert resp.status_code == 200
        discovery.return_value.get_tenant_id_by_external_id.assert_awaited()

    def test_invalid_json_fallback_ignored(self):
        with _discovery(None):
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/pm-crm/jira",
                content=b"nope{",
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_postgres_rls_and_conn_error(self):
        db = _pg_db()
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = (
            RuntimeError("boom")
        )
        with _discovery(), _dispatch():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/pm-crm/jira",
                json={"clientKey": "ck-1", "issue": {"id": "1"}},
            )
        assert resp.status_code == 200

    def test_dispatch_error_500(self):
        db = _pg_db()
        with _discovery(), _dispatch(result=RuntimeError("boom")):
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/pm-crm/jira",
                json={"clientKey": "ck-1", "issue": {"id": "1"}},
            )
        assert resp.status_code == 500


class TestIngestionCommunicationWebhook:
    def test_head_handshake(self):
        _, client = _ingestion_client()
        resp = client.head("/webhooks/communication/discord")
        assert resp.status_code == 200

    def test_unsupported_integration_400(self):
        _, client = _ingestion_client()
        resp = client.post("/webhooks/communication/mystery", json={})
        assert resp.status_code == 400

    def test_tenant_not_found_ignored(self):
        with _discovery(None):
            _, client = _ingestion_client()
            resp = client.post("/webhooks/communication/discord", json={"guild_id": "g1"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_fallback_communication_connector(self):
        service = MagicMock()
        service.get_tenant_id_by_external_id = AsyncMock(side_effect=[None, "tenant-9"])
        from api.routes.webhooks import ingestion_webhooks as iw

        with patch.object(iw, "TenantDiscoveryService", return_value=service), _dispatch():
            _, client = _ingestion_client()
            resp = client.post("/webhooks/communication/discord", json={"guild_id": "g1"})
        assert resp.status_code == 200
        assert service.get_tenant_id_by_external_id.await_args_list[1].args[0] == "communication"

    def test_twilio_form_encoded(self):
        with _discovery(), _dispatch() as dispatch:
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/communication/twilio",
                data={"AccountSid": "AC1", "MessageSid": "SM1", "From": "+1", "To": "+2"},
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()

    def test_form_parse_error_fallback(self):
        with _discovery(None):
            _, client = _ingestion_client()
            with patch("starlette.requests.Request.form", side_effect=RuntimeError("bad form")):
                resp = client.post(
                    "/webhooks/communication/discord",
                    data={"guild_id": "G1"},
                    headers={"content-type": "application/x-www-form-urlencoded"},
                )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_external_id_variants(self):
        variants = [
            {"app_id": "app-1"},
            {"tenantId": "t-ms"},
            {"conversation": {"tenantId": "t-ms2"}},
            {"channelData": {"tenant": {"id": "t-ms3"}}},
            {"message": {"chat": {"id": "chat-1"}}},
            {"edited_message": {"chat": {"id": "chat-2"}}},
            {"guild_id": "g1"},
            {"channel_id": "ch-1"},
        ]
        for payload in variants:
            with _discovery() as discovery, _dispatch():
                _, client = _ingestion_client()
                resp = client.post("/webhooks/communication/telegram", json=payload)
            assert resp.status_code == 200
            discovery.return_value.get_tenant_id_by_external_id.assert_awaited()

    def test_query_param_fallback(self):
        with _discovery() as discovery, _dispatch():
            _, client = _ingestion_client()
            resp = client.post("/webhooks/communication/discord?guild_id=g2", json={})
        assert resp.status_code == 200
        discovery.return_value.get_tenant_id_by_external_id.assert_awaited()

    def test_success_dispatches(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = _conn(
            "conn-comm"
        )
        with _discovery(), _dispatch() as dispatch:
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/communication/intercom",
                json={"app_id": "app-1", "data": {"id": "1"}},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()
        assert dispatch.call_args.kwargs["source_connection_id"] == "conn-comm"

    def test_invalid_json_fallback(self):
        with _discovery(None):
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/communication/discord",
                content=b"nope",
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_postgres_rls_and_conn_error(self):
        db = _pg_db()
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = (
            RuntimeError("boom")
        )
        with _discovery(), _dispatch():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/communication/discord",
                json={"guild_id": "G1", "event": {"type": "message"}},
            )
        assert resp.status_code == 200

    def test_dispatch_error_500(self):
        db = _pg_db()
        with _discovery(), _dispatch(result=RuntimeError("boom")):
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/communication/intercom",
                json={"app_id": "app-1"},
            )
        assert resp.status_code == 500


class TestIngestionDevProdWebhook:
    def test_dropbox_challenge(self):
        _, client = _ingestion_client()
        resp = client.get("/webhooks/dev-prod/dropbox?challenge=ch-1")
        assert resp.status_code == 200
        assert resp.text == "ch-1"

    def test_onedrive_validation_token(self):
        _, client = _ingestion_client()
        resp = client.get("/webhooks/dev-prod/onedrive?validationToken=vt-1")
        assert resp.status_code == 200
        assert resp.text == "vt-1"

    def test_unsupported_integration_400(self):
        _, client = _ingestion_client()
        resp = client.post("/webhooks/dev-prod/mystery", json={})
        assert resp.status_code == 400

    def test_github_ping_header(self):
        _, client = _ingestion_client()
        resp = client.post(
            "/webhooks/dev-prod/github", json={}, headers={"X-GitHub-Event": "ping"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_github_zen_ping(self):
        _, client = _ingestion_client()
        resp = client.post("/webhooks/dev-prod/github", json={"zen": "Keep it simple"})
        assert resp.status_code == 200
        assert resp.json()["zen"] == "Keep it simple"

    def test_tenant_not_found_ignored(self):
        with _discovery(None):
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/dev-prod/github",
                json={"repository": {"owner": {"login": "org1"}}},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_fallback_dev_prod_connector(self):
        service = MagicMock()
        service.get_tenant_id_by_external_id = AsyncMock(side_effect=[None, "tenant-9"])
        from api.routes.webhooks import ingestion_webhooks as iw

        with patch.object(iw, "TenantDiscoveryService", return_value=service), _dispatch():
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/dev-prod/github",
                json={"repository": {"owner": {"login": "org1"}}},
            )
        assert resp.status_code == 200
        assert service.get_tenant_id_by_external_id.await_args_list[1].args[0] == "dev_prod"

    def test_external_id_variants(self):
        variants = [
            {"organization": {"login": "acme"}},
            {"organization": {"id": 7}},
            {"repository": {"owner": {"login": "acme"}}},
            {"repository": {"owner": {"id": 8}}},
            {"project": {"path_with_namespace": "grp/proj"}},
            {"project": {"id": 9}},
            {"repository": {"workspace": {"uuid": "ws-u"}}},
            {"repository": {"uuid": "repo-u"}},
            {"channelId": "ch-1"},
            {"resourceId": "res-1"},
            {"accounts": ["acct-1"]},
            {"enterprise": {"id": "ent-1"}},
            {"value": [{"clientState": "cs-1"}]},
            {"tenant_id": "t-1"},
            {"account_id": "a-1"},
        ]
        for payload in variants:
            with _discovery() as discovery, _dispatch():
                _, client = _ingestion_client()
                resp = client.post("/webhooks/dev-prod/github", json=payload)
            assert resp.status_code == 200
            discovery.return_value.get_tenant_id_by_external_id.assert_awaited()

    def test_success_dispatches(self):
        with _discovery(), _dispatch() as dispatch:
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/dev-prod/github",
                json={"repository": {"owner": {"login": "org1"}}, "ref": "main"},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()

    def test_query_param_fallback(self):
        with _discovery() as discovery, _dispatch():
            _, client = _ingestion_client()
            resp = client.post("/webhooks/dev-prod/box?org_id=o1", json={})
        assert resp.status_code == 200
        discovery.return_value.get_tenant_id_by_external_id.assert_awaited()

    def test_invalid_json_fallback_ignored(self):
        with _discovery(None):
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/dev-prod/github",
                content=b"broken{",
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_postgres_rls_and_conn_error(self):
        db = _pg_db()
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = (
            RuntimeError("boom")
        )
        with _discovery(), _dispatch():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/dev-prod/github",
                json={
                    "hook": {"events": ["push"]},
                    "organization": {"login": "acme-org"},
                    "repository": {"id": "r1"},
                },
            )
        assert resp.status_code == 200

    def test_dispatch_error_500(self):
        db = _pg_db()
        with _discovery(), _dispatch(result=RuntimeError("boom")):
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/dev-prod/github",
                json={"organization": {"login": "acme-org"}, "repository": {"id": "r1"}},
            )
        assert resp.status_code == 500


class TestIngestionEcommerceMarketingWebhook:
    def test_head_handshake(self):
        _, client = _ingestion_client()
        resp = client.head("/webhooks/ecommerce-marketing/shopify")
        assert resp.status_code == 200

    def test_get_validation(self):
        _, client = _ingestion_client()
        resp = client.get("/webhooks/ecommerce-marketing/mailchimp")
        assert resp.status_code == 200

    def test_unsupported_integration_400(self):
        _, client = _ingestion_client()
        resp = client.post("/webhooks/ecommerce-marketing/mystery", json={})
        assert resp.status_code == 400

    def test_zoom_url_validation(self):
        _, client = _ingestion_client()
        resp = client.post(
            "/webhooks/ecommerce-marketing/zoom",
            json={"event": "endpoint.url_validation", "payload": {"plainToken": "pt-1"}},
        )
        assert resp.status_code == 200
        assert resp.json()["plainToken"] == "pt-1"

    def test_zoom_url_validation_no_payload(self):
        _, client = _ingestion_client()
        resp = client.post(
            "/webhooks/ecommerce-marketing/zoom",
            json={"event": "endpoint.url_validation"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"plainToken": "", "encryptedToken": ""}

    def test_tenant_not_found_ignored(self):
        with _discovery(None):
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/ecommerce-marketing/shopify", json={"domain": "shop1.myshopify.com"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_fallback_ecommerce_connector(self):
        service = MagicMock()
        service.get_tenant_id_by_external_id = AsyncMock(side_effect=[None, "tenant-9"])
        from api.routes.webhooks import ingestion_webhooks as iw

        with patch.object(iw, "TenantDiscoveryService", return_value=service), _dispatch():
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/ecommerce-marketing/shopify", json={"domain": "d1.myshopify.com"}
            )
        assert resp.status_code == 200
        assert (
            service.get_tenant_id_by_external_id.await_args_list[1].args[0]
            == "ecommerce_marketing"
        )

    def test_mailchimp_form_encoded(self):
        with _discovery(), _dispatch() as dispatch:
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/ecommerce-marketing/mailchimp?list_id=list-1",
                data={"type": "subscribe"},
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()

    def test_form_parse_error_fallback(self):
        with _discovery(None):
            _, client = _ingestion_client()
            with patch("starlette.requests.Request.form", side_effect=RuntimeError("bad form")):
                resp = client.post(
                    "/webhooks/ecommerce-marketing/mailchimp",
                    data={"type": "subscribe"},
                    headers={"content-type": "application/x-www-form-urlencoded"},
                )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_external_id_variants(self):
        variants = [
            {"domain": "shop1.myshopify.com"},
            {"shop_id": "s1"},
            {"store_url": "https://w.com"},
            {"store_hash": "h1"},
            {"producer": "p1"},
            {"store_id": "st1"},
            {"account": "acct_1"},
            {"data": {"list_id": "L1"}},
            {"account_name": "an1"},
            {"contact": {"campaign_id": "cg1"}},
            {"base_id": "b1"},
            {"webhookId": "wh1"},
            {"orgId": "o1"},
            {"accountId": "acc1"},
            {"team_id": "tm1"},
        ]
        for payload in variants:
            with _discovery() as discovery, _dispatch():
                _, client = _ingestion_client()
                resp = client.post("/webhooks/ecommerce-marketing/stripe", json=payload)
            assert resp.status_code == 200
            discovery.return_value.get_tenant_id_by_external_id.assert_awaited()

    def test_sendgrid_list_payload(self):
        with _discovery(), _dispatch() as dispatch:
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/ecommerce-marketing/sendgrid",
                json=[{"useragent": "ua-1", "event": "delivered"}],
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()

    def test_sendgrid_list_payload_ip_fallback(self):
        with _discovery() as discovery, _dispatch():
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/ecommerce-marketing/sendgrid",
                json=[{"ip": "1.2.3.4", "event": "delivered"}],
            )
        assert resp.status_code == 200
        discovery.return_value.get_tenant_id_by_external_id.assert_awaited()

    def test_query_param_fallback(self):
        with _discovery() as discovery, _dispatch():
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/ecommerce-marketing/stripe?account_id=acct_1", json={}
            )
        assert resp.status_code == 200
        discovery.return_value.get_tenant_id_by_external_id.assert_awaited()

    def test_invalid_json_fallback(self):
        with _discovery(None):
            _, client = _ingestion_client()
            resp = client.post(
                "/webhooks/ecommerce-marketing/shopify",
                content=b"broken{",
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code == 200

    def test_postgres_rls_and_conn_error(self):
        db = _pg_db()
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = (
            RuntimeError("boom")
        )
        with _discovery(), _dispatch():
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/ecommerce-marketing/shopify",
                json={"domain": "acme.myshopify.com", "topic": "orders/create"},
            )
        assert resp.status_code == 200

    def test_dispatch_error_500(self):
        db = _pg_db()
        with _discovery(), _dispatch(result=RuntimeError("boom")):
            _, client = _ingestion_client(db)
            resp = client.post(
                "/webhooks/ecommerce-marketing/shopify",
                json={"domain": "acme.myshopify.com", "topic": "orders/create"},
            )
        assert resp.status_code == 500
