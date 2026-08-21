"""
Zendesk inbound ingestion (P0.4 audit §7 — largest gap: zero inbound).

RED:
  - no `/webhooks/zendesk/events` route exists
  - no `_transform_zendesk_payload` (only the CRM-shaped sell variant)
  - "zendesk" ∉ `_KNOWN_COMM_INTEGRATIONS` → no Pipeline A even if bridged

Contracts pinned here:
  - route: fail-closed R69 pattern — ZENDESK_WEBHOOK_SECRET unset → 503;
    invalid HMAC signature (X-Zendesk-Webhook-Signature, SHA-256 over the
    RAW body) → 401; valid → job enqueued, 200.
  - transformer: comment-shaped payloads become comm records
    ({type: "zendesk_message", content, from, ticket_id, subject,
    direction, event_type}); empty/degenerate payloads degrade to a
    notification stub rather than [] so the audit trail keeps flowing.
  - comm membership: "zendesk" ∈ _KNOWN_COMM_INTEGRATIONS.
  - queue bridge: process_webhook_payload("zendesk", …) routes records to
    CommunicationIngestionPipeline.ingest_message("zendesk", record) with
    the same per-record raw-write fallback as gmail/teams/discord.
"""

import hashlib
import hmac
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.ingestion_pipeline import IngestionPipelineService


SECRET = "zendesk-shared-secret"


def base64_hmac(body: bytes, secret: str = SECRET) -> str:
    import base64

    return base64.b64encode(
        hmac.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode()


def _comment_payload():
    return {
        "ticket": {
            "id": 1234,
            "subject": "Cannot export invoices",
            "requester": {"name": "Client Ops", "email": "ops@acme.com"},
        },
        "current_comment": {
            "body": "Export fails at 80% with error code E-42 every time",
            "author_id": 987,
            "public": True,
        },
        "event_type": "ticket_comment_added",
    }


@pytest.fixture()
def client():
    from api.routes.webhooks.ingestion_webhooks import router
    from core.database import get_db

    app = FastAPI()
    app.include_router(router)

    def _mock_db():
        db = MagicMock()
        db.bind = None  # skip pg row_security branch
        conn = SimpleNamespace(id="conn-1", tenant_id="t-1", status="active")
        db.query.return_value.filter.return_value.first.return_value = conn
        return db

    app.dependency_overrides[get_db] = _mock_db
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def secret_env():
    with patch.dict("os.environ", {"ZENDESK_WEBHOOK_SECRET": SECRET}):
        yield


class TestZendeskWebhookRoute:
    def test_no_secret_configured_rejects_503(self, client):
        with patch.dict("os.environ", {}, clear=False):
            import os

            env = dict(os.environ)
            env.pop("ZENDESK_WEBHOOK_SECRET", None)
            with patch.dict("os.environ", env, clear=True):
                resp = client.post(
                    "/webhooks/zendesk/events", json=_comment_payload()
                )
        assert resp.status_code == 503

    def test_invalid_signature_rejects_401(self, client, secret_env):
        resp = client.post(
            "/webhooks/zendesk/events",
            json=_comment_payload(),
            headers={"X-Zendesk-Webhook-Signature": "bogus"},
        )
        assert resp.status_code == 401

    def test_missing_signature_rejects_401(self, client, secret_env):
        resp = client.post("/webhooks/zendesk/events", json=_comment_payload())
        assert resp.status_code == 401

    def test_valid_signature_enqueues(self, client, secret_env):
        body = _comment_payload()
        with patch("api.routes.webhooks.ingestion_webhooks.webhook_queue") as q:
            q.enqueue_ingestion_job = AsyncMock(return_value="job-zd-1")
            # sign the exact bytes the server will read: build request manually
            import json as _json

            raw_body = _json.dumps(body).encode()
            sig = base64_hmac(raw_body)
            resp = client.post(
                "/webhooks/zendesk/events",
                content=raw_body,
                headers={
                    "Content-Type": "application/json",
                    "X-Zendesk-Webhook-Signature": sig,
                },
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "enqueued"


class TestZendeskTransformer:
    @pytest.mark.asyncio
    async def test_comment_payload_becomes_message_record(self):
        svc = IngestionPipelineService.__new__(IngestionPipelineService)
        svc.tenant_id = "t-1"
        svc.workspace_id = "w-1"
        records = await svc._transform_zendesk_payload(_comment_payload())
        assert len(records) == 1
        rec = records[0]
        assert rec["type"] == "zendesk_message"
        assert rec["ticket_id"] == 1234
        assert "E-42" in rec["content"]
        assert rec["direction"] == "inbound"
        assert rec["event_type"] == "ticket_comment_added"

    @pytest.mark.asyncio
    async def test_degenerate_payload_degrades_to_stub(self):
        svc = IngestionPipelineService.__new__(IngestionPipelineService)
        svc.tenant_id = "t-1"
        svc.workspace_id = "w-1"
        records = await svc._transform_zendesk_payload({"event_type": "ping"})
        assert len(records) == 1
        assert records[0]["type"] == "zendesk_message"


class TestZendeskCommMembershipAndBridge:
    def test_zendesk_is_known_comm_integration(self):
        from core.ingestion_pipeline import IngestionPipelineService as Svc

        assert "zendesk" in Svc._KNOWN_COMM_INTEGRATIONS

    @pytest.mark.asyncio
    async def test_queue_records_bridge_to_ingest_message(self):
        svc = IngestionPipelineService.__new__(IngestionPipelineService)
        svc.tenant_id = "t-1"
        svc.workspace_id = "w-1"
        svc.graphrag = MagicMock()
        svc.usage_tracker = MagicMock()
        record = {
            "type": "zendesk_message",
            "id": "zd_1234",
            "content": "Export fails at 80% with error code E-42 every time",
            "from": "Client Ops",
            "ticket_id": 1234,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "direction": "inbound",
            "event_type": "ticket_comment_added",
        }
        async def fake_transform(iid, data):
            return [record]

        with patch.object(svc, "_transform_webhook_payload", side_effect=fake_transform), \
             patch("core.lancedb_handler.LanceDBHandler") as raw_cls, \
             patch(
                 "integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline"
             ) as factory:
            pipe = MagicMock()
            pipe.ingest_message = AsyncMock(return_value={"success": True})
            factory.return_value = pipe
            await svc.process_webhook_payload("zendesk", {})

        assert pipe.ingest_message.await_count == 1
        args = pipe.ingest_message.await_args.args
        assert args[0] == "zendesk"
        assert args[1]["id"] == "zd_1234"
        raw_cls.return_value.add_document.assert_not_called()