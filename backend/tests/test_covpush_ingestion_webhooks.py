# -*- coding: utf-8 -*-
"""
Coverage-push tests for api/routes/webhooks/ingestion_webhooks.py — HMAC auth,
payload validation, fail-closed conventions (Round 45/46), and all batch
handlers (Zoho / PM-CRM / Communication / Dev-Prod / E-commerce).

TDD target (RED first): zoho_webhook_handler crashes with a 500 when the
payload is a JSON array (list payloads are explicitly supported by the code
path, but payload.get() runs before the isinstance(list) guard).
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

from api.routes.webhooks import ingestion_webhooks as iw


def make_client(db=None):
    app = FastAPI()
    app.include_router(iw.router)
    app.dependency_overrides[get_db] = lambda: db if db is not None else MagicMock()
    client = TestClient(app, raise_server_exceptions=False)

    # R89 re-contract: the zoho/pm-crm/communication/dev-prod families are
    # fail-closed verified now. Sign family requests transparently so the
    # business-logic tests below keep testing dispatch, not auth.
    import hashlib
    import hmac as _hmac
    import json as _json

    _FAMILY_ENVS = {
        "/webhooks/zoho/": "ATOM_ZOHO_WEBHOOK_SECRET",
        "/webhooks/pm-crm/": "ATOM_PMCRM_WEBHOOK_SECRET",
        "/webhooks/communication/": "ATOM_COMMUNICATION_WEBHOOK_SECRET",
        "/webhooks/dev-prod/": "ATOM_DEVPROD_WEBHOOK_SECRET",
    }
    orig_post = client.post

    def _signing_post(url, **kwargs):
        for prefix, env_name in _FAMILY_ENVS.items():
            if url.startswith(prefix):
                secret = os.getenv(env_name, "")
                if secret:
                    if "json" in kwargs:
                        body = _json.dumps(kwargs.pop("json")).encode()
                        kwargs["content"] = body
                    elif "data" in kwargs:
                        from urllib.parse import urlencode as _urlencode

                        body = _urlencode(kwargs.pop("data")).encode()
                        kwargs["content"] = body
                    else:
                        body = kwargs.get("content") or b""
                    sig = _hmac.new(
                        secret.encode(), body, hashlib.sha256
                    ).hexdigest()
                    headers = kwargs.setdefault("headers", {})
                    headers["X-Atom-Webhook-Signature"] = sig
                break
        return orig_post(url, **kwargs)

    client.post = _signing_post
    return client


@pytest.fixture(autouse=True)
def _family_secrets(monkeypatch):
    """R89: the generic webhook families reject unsigned traffic; tests opt
    in by setting the shared secrets (the signing client above signs)."""
    monkeypatch.setenv("ATOM_ZOHO_WEBHOOK_SECRET", "test-zoho-secret")
    monkeypatch.setenv("ATOM_PMCRM_WEBHOOK_SECRET", "test-pmcrm-secret")
    monkeypatch.setenv("ATOM_COMMUNICATION_WEBHOOK_SECRET", "test-comm-secret")
    monkeypatch.setenv("ATOM_DEVPROD_WEBHOOK_SECRET", "test-devprod-secret")


def _discovery(tenant_id="tenant-1"):
    service = MagicMock()
    service.get_tenant_id_by_external_id = AsyncMock(return_value=tenant_id)
    return patch.object(iw, "TenantDiscoveryService", return_value=service)


def _dispatch(result=None):
    import core.webhook_crud_dispatch as wcd

    return patch.object(
        wcd,
        "crud_dispatch",
        new=AsyncMock(return_value={"status": "enqueued", "records": 1} if result is None else result),
    )


def _queue():
    queue = MagicMock()
    queue.enqueue_ingestion_job = AsyncMock(return_value="job-1")
    queue.get_queue_depth = AsyncMock(return_value=3)
    return patch.object(iw, "webhook_queue", queue)


def _hmac(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _integration(config=None, active=True):
    integration = MagicMock()
    integration.config = config if config is not None else {}
    integration.is_active = active
    return integration


@pytest.fixture
def db():
    return MagicMock()


class TestSlackWebhook:
    def test_url_verification_challenge(self, db):
        with _discovery():
            resp = make_client(db).post(
                "/webhooks/slack/events", json={"type": "url_verification", "challenge": "abc"}
            )
        assert resp.status_code == 200
        assert resp.json()["challenge"] == "abc"

    def test_missing_team_id_400(self, db):
        with _discovery():
            resp = make_client(db).post(
                "/webhooks/slack/events", json={"type": "event_callback", "event": {}}
            )
        assert resp.status_code == 400

    def test_team_id_from_event(self, db):
        with _discovery() as discovery:
            resp = make_client(db).post(
                "/webhooks/slack/events",
                json={"type": "event_callback", "event": {"type": "message", "team": "T2"}},
            )
        assert resp.status_code in (401, 503)
        discovery.return_value.get_tenant_id_by_external_id.assert_awaited_once_with(
            "slack", "T2"
        )

    def test_tenant_not_found_ignored(self, db):
        with _discovery(None):
            resp = make_client(db).post(
                "/webhooks/slack/events", json={"type": "event_callback", "team_id": "T1"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_integration_not_configured_401(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with _discovery():
            resp = make_client(db).post(
                "/webhooks/slack/events", json={"type": "event_callback", "team_id": "T1"}
            )
        assert resp.status_code == 401

    def test_missing_signing_secret_503(self, db):
        db.query.return_value.filter.return_value.first.return_value = _integration({"other": "x"})
        with _discovery():
            resp = make_client(db).post(
                "/webhooks/slack/events", json={"type": "event_callback", "team_id": "T1"}
            )
        assert resp.status_code == 503

    def test_invalid_signature_401(self, db):
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"slack_signing_secret": "secret"}
        )
        with _discovery():
            resp = make_client(db).post(
                "/webhooks/slack/events",
                json={"type": "event_callback", "team_id": "T1"},
                headers={"X-Slack-Signature": "deadbeef", "X-Slack-Request-Timestamp": "123"},
            )
        assert resp.status_code == 401

    def test_valid_signature_dispatches(self, db):
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"slack_signing_secret": "secret"}
        )
        payload = {"type": "event_callback", "team_id": "T1", "event": {"type": "message", "text": "hi"}}
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/slack/events",
                content=body,
                headers={
                    "X-Slack-Signature": _hmac(body, "secret"),
                    "X-Slack-Request-Timestamp": "123",
                },
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()

    def test_handler_exception_returns_200(self, db):
        db.query.side_effect = Exception("boom")
        with _discovery():
            resp = make_client(db).post(
                "/webhooks/slack/events", json={"type": "event_callback", "team_id": "T1"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"


class TestHubspotWebhook:
    def test_missing_portal_continue(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/hubspot/events", json=[{"type": "contact.creation", "objectId": 1}]
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "enqueued"
        dispatch.assert_not_awaited()

    def test_tenant_not_found_continue(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with _discovery(None), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/hubspot/events",
                json=[{"portalId": "P1", "type": "contact.creation", "objectId": 1}],
            )
        assert resp.status_code == 200
        dispatch.assert_not_awaited()

    def test_unconfigured_fail_closed(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/hubspot/events",
                json=[{"portalId": "P1", "type": "contact.creation", "objectId": 1}],
            )
        assert resp.status_code in (401, 503)
        dispatch.assert_not_awaited()

    def test_bad_signature_401(self, db):
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/hubspot/events",
                json=[{"portalId": "P1", "type": "contact.creation", "objectId": 1}],
                headers={"X-HubSpot-Signature": "deadbeef"},
            )
        assert resp.status_code == 401
        dispatch.assert_not_awaited()

    def test_valid_signature_batch_dispatches(self, db):
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        payload = [
            {"portalId": "P1", "type": "contact.creation", "objectId": 1},
            {"portalId": "P1", "type": "deal.updates", "objectId": 2},
        ]
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/hubspot/events",
                content=body,
                headers={"X-HubSpot-Signature": _hmac(body, "s3cr3t")},
            )
        assert resp.status_code == 200
        assert dispatch.await_count == 2

    def test_non_list_payload(self, db):
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        payload = {"portalId": "P1", "type": "contact.creation", "objectId": 1}
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch():
            resp = make_client(db).post(
                "/webhooks/hubspot/events",
                content=body,
                headers={"X-HubSpot-Signature": _hmac(body, "s3cr3t")},
            )
        assert resp.status_code == 200


class TestSalesforceWebhook:
    def test_missing_org_id_400(self, db):
        with _discovery():
            resp = make_client(db).post("/webhooks/salesforce/events", json={"eventType": "x"})
        assert resp.status_code == 400

    def test_tenant_not_found_ignored(self, db):
        with _discovery(None):
            resp = make_client(db).post(
                "/webhooks/salesforce/events", json={"orgId": "O1", "eventType": "x"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_unconfigured_fail_closed(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/salesforce/events", json={"orgId": "O1", "eventType": "created"}
            )
        assert resp.status_code in (401, 503)
        dispatch.assert_not_awaited()

    def test_bad_signature_401(self, db):
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        with _discovery():
            resp = make_client(db).post(
                "/webhooks/salesforce/events",
                json={"orgId": "O1", "eventType": "created"},
                headers={"X-Salesforce-Signature": "deadbeef"},
            )
        assert resp.status_code == 401

    def test_valid_signature_dispatches(self, db):
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        payload = {"orgId": "O1", "eventType": "created", "objectType": "Account", "recordIds": ["a1"]}
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/salesforce/events",
                content=body,
                headers={"X-Salesforce-Signature": _hmac(body, "s3cr3t")},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()


class TestGmailWebhook:
    # Gmail Pub/Sub push webhooks require the GMAIL_WEBHOOK_VERIFY_TOKEN
    # query param (fail-closed gate added in the 2026-08-09 bug-hunt).
    _TOKEN = "gmail-verify-tok"

    def _url(self):
        return f"/webhooks/gmail/events?token={self._TOKEN}"

    def test_unconfigured_secret_fails_closed(self, db):
        with _discovery(), _queue():
            resp = make_client(db).post("/webhooks/gmail/events", json={"historyId": "h1"})
        assert resp.status_code == 503

    def test_wrong_token_rejected(self, db):
        with _discovery(), _queue(), patch.dict(
            os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": self._TOKEN}
        ):
            resp = make_client(db).post(
                "/webhooks/gmail/events?token=attacker-tok", json={"historyId": "h1"}
            )
        assert resp.status_code == 401

    def test_missing_email_address_400(self, db):
        with _discovery(), patch.dict(os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": self._TOKEN}):
            resp = make_client(db).post(self._url(), json={"historyId": "h1"})
        assert resp.status_code == 400

    def test_tenant_not_found_ignored(self, db):
        with _discovery(None), patch.dict(os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": self._TOKEN}):
            resp = make_client(db).post(
                self._url(), json={"historyId": "h1", "emailAddress": "a@b.c"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_success_enqueues(self, db):
        conn = MagicMock()
        conn.id = "conn-1"
        db.query.return_value.filter.return_value.first.return_value = conn
        with _discovery(), _queue() as queue, patch.dict(
            os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": self._TOKEN}
        ):
            resp = make_client(db).post(
                self._url(), json={"historyId": "h1", "emailAddress": "a@b.c"}
            )
        assert resp.status_code == 200
        assert resp.json()["job_id"] == "job-1"
        queue.enqueue_ingestion_job.assert_awaited_once()

    def test_pubsub_wrapped_payload(self, db):
        conn = MagicMock()
        conn.id = "conn-1"
        db.query.return_value.filter.return_value.first.return_value = conn
        inner = json.dumps({"historyId": "h9", "emailAddress": "a@b.c"}).encode()
        b64 = base64.b64encode(inner).decode()
        with _discovery(), _queue() as queue, patch.dict(
            os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": self._TOKEN}
        ):
            resp = make_client(db).post(
                self._url(),
                json={"message": {"data": b64, "messageId": "m1"}},
            )
        assert resp.status_code == 200
        kwargs = queue.enqueue_ingestion_job.call_args.kwargs
        assert kwargs["payload"]["historyId"] == "h9"

    def test_pubsub_padding_fixed(self, db):
        conn = MagicMock()
        conn.id = "conn-1"
        db.query.return_value.filter.return_value.first.return_value = conn
        inner = json.dumps({"historyId": "h9", "emailAddress": "a@b.c"}).encode()
        b64 = base64.b64encode(inner).decode().rstrip("=")
        with _discovery(), _queue(), patch.dict(
            os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": self._TOKEN}
        ):
            resp = make_client(db).post(
                self._url(),
                json={"message": {"data": b64, "messageId": "m1"}},
            )
        assert resp.status_code == 200

    def test_pubsub_invalid_base64_falls_through(self, db):
        with _discovery(None), patch.dict(
            os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": self._TOKEN}
        ):
            resp = make_client(db).post(
                self._url(),
                json={"message": {"data": "!!!not-base64!!!"}},
            )
        assert resp.status_code == 400


class TestNotionWebhook:
    def test_missing_workspace_400(self, db):
        with _discovery():
            resp = make_client(db).post("/webhooks/notion/events", json={"type": "page.created"})
        assert resp.status_code == 400

    def test_tenant_not_found_ignored(self, db):
        with _discovery(None):
            resp = make_client(db).post(
                "/webhooks/notion/events", json={"workspace_id": "W1", "type": "page.created"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_unconfigured_fail_closed(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/notion/events", json={"workspace_id": "W1", "type": "page.created"}
            )
        assert resp.status_code in (401, 503)
        dispatch.assert_not_awaited()

    def test_bad_signature_401(self, db):
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        with _discovery():
            resp = make_client(db).post(
                "/webhooks/notion/events",
                json={"workspace_id": "W1", "type": "page.created"},
                headers={"X-Notion-Signature": "deadbeef"},
            )
        assert resp.status_code == 401

    def test_valid_signature_dispatches(self, db):
        db.query.return_value.filter.return_value.first.return_value = _integration(
            {"client_secret": "s3cr3t"}
        )
        payload = {"workspace_id": "W1", "type": "page.created", "id": "p1"}
        body = json.dumps(payload).encode()
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/notion/events",
                content=body,
                headers={"X-Notion-Signature": _hmac(body, "s3cr3t")},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()


class TestOutlookWebhook:
    def test_validation_token_handshake(self, db):
        with _queue():
            resp = make_client(db).get(
                "/webhooks/communication/outlook?validationToken=verify-123"
            )
        assert resp.status_code == 200
        assert resp.text == "verify-123"

    def test_empty_body_lifecycle(self, db):
        with _queue():
            resp = make_client(db).post(
                "/webhooks/communication/outlook", content=b"", headers={"content-length": "0"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_invalid_json(self, db):
        with _queue():
            resp = make_client(db).post(
                "/webhooks/communication/outlook", content=b"{not json", headers={"content-length": "9"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_empty_notifications(self, db):
        with _queue():
            resp = make_client(db).post(
                "/webhooks/communication/outlook", json={"value": []}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_missing_client_state_skipped(self, db):
        with _queue():
            resp = make_client(db).post(
                "/webhooks/communication/outlook",
                json={"value": [{"changeType": "created", "resource": "x"}]},
            )
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 0

    def test_invalid_client_state_fail_closed(self, db, monkeypatch):
        monkeypatch.setattr(
            "core.webhook_security.verify_client_state", MagicMock(return_value=False)
        )
        with _queue():
            resp = make_client(db).post(
                "/webhooks/communication/outlook",
                json={"value": [{"changeType": "created", "clientState": "forged"}]},
            )
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 0

    def test_valid_client_state_enqueues(self, db, monkeypatch):
        monkeypatch.setattr(
            "core.webhook_security.verify_client_state", MagicMock(return_value=True)
        )
        monkeypatch.setattr(
            "core.webhook_security.get_client_state_data",
            MagicMock(return_value='{"c": "conn-prefix"}'),
        )
        tenant = MagicMock()
        tenant.id = "tenant-1"
        db.query.return_value.filter.return_value.first.return_value = tenant
        conn = MagicMock()
        conn.id = "conn-prefix-abc"
        db.query.return_value.filter.return_value.first.side_effect = [tenant, conn]
        with _queue() as queue:
            resp = make_client(db).post(
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
            )
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 1
        queue.enqueue_ingestion_job.assert_awaited_once()
        kwargs = queue.enqueue_ingestion_job.call_args.kwargs
        assert kwargs["source_connection_id"] == "conn-prefix-abc"

    def test_deletion_event(self, db, monkeypatch):
        monkeypatch.setattr(
            "core.webhook_security.verify_client_state", MagicMock(return_value=True)
        )
        monkeypatch.setattr(
            "core.webhook_security.get_client_state_data",
            MagicMock(return_value='{"c": ""}'),
        )
        tenant = MagicMock()
        tenant.id = "tenant-1"
        entity = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [entity]
        db.query.return_value.filter.return_value.first.side_effect = [tenant, None]
        with _queue():
            resp = make_client(db).post(
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

    def test_deletion_missing_message_id(self, db, monkeypatch):
        monkeypatch.setattr(
            "core.webhook_security.verify_client_state", MagicMock(return_value=True)
        )
        monkeypatch.setattr(
            "core.webhook_security.get_client_state_data", MagicMock(return_value="{}")
        )
        tenant = MagicMock()
        tenant.id = "tenant-1"
        db.query.return_value.filter.return_value.first.return_value = tenant
        with _queue():
            resp = make_client(db).post(
                "/webhooks/communication/outlook",
                json={"value": [{"changeType": "deleted", "clientState": "signed", "resource": ""}]},
            )
        assert resp.status_code == 200

    def test_no_subdomain_skipped(self, db, monkeypatch):
        monkeypatch.setattr(
            "core.webhook_security.verify_client_state", MagicMock(return_value=True)
        )
        monkeypatch.setattr(
            "core.webhook_security.get_client_state_data", MagicMock(return_value="{}")
        )
        with _queue():
            resp = make_client(db).post(
                "/webhooks/communication/outlook",
                json={"value": [{"changeType": "created", "clientState": "signed"}]},
                headers={"host": ""},
            )
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 0

    def test_no_tenant_found_skipped(self, db, monkeypatch):
        monkeypatch.setattr(
            "core.webhook_security.verify_client_state", MagicMock(return_value=True)
        )
        monkeypatch.setattr(
            "core.webhook_security.get_client_state_data", MagicMock(return_value="{}")
        )
        db.query.return_value.filter.return_value.first.return_value = None
        with _queue():
            resp = make_client(db).post(
                "/webhooks/communication/outlook",
                json={"value": [{"changeType": "created", "clientState": "signed"}]},
            )
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 0


class TestZohoWebhook:
    def test_unsupported_integration_400(self, db):
        resp = make_client(db).post("/webhooks/zoho/mystery", json={})
        assert resp.status_code == 400

    def test_missing_org_400(self, db):
        with _discovery():
            resp = make_client(db).post("/webhooks/zoho/zoho_crm", json={"module": {"api_name": "Leads"}})
        assert resp.status_code == 400

    def test_tenant_not_found_ignored(self, db):
        with _discovery(None):
            resp = make_client(db).post(
                "/webhooks/zoho/zoho_crm", json={"orgId": "O1", "module": {"api_name": "Leads"}}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_fallback_zoho_connector(self, db):
        service = MagicMock()
        service.get_tenant_id_by_external_id = AsyncMock(side_effect=[None, "tenant-9"])
        with patch.object(iw, "TenantDiscoveryService", return_value=service), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/zoho/zoho_books", json={"orgId": "O1", "module": "Invoice"}
            )
        assert resp.status_code == 200
        assert service.get_tenant_id_by_external_id.await_args_list[1].args[0] == "zoho"
        dispatch.assert_awaited_once()

    def test_success_dispatches(self, db):
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/zoho/zoho_crm",
                json={"orgId": "O1", "module": {"api_name": "Leads"}, "key_id": "1"},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()
        kwargs = dispatch.call_args.kwargs
        assert kwargs["integration_id"] == "zoho_crm"

    def test_invalid_json_fallback_empty(self, db):
        with _discovery():
            resp = make_client(db).post("/webhooks/zoho/zoho_crm", content=b"not json")
        assert resp.status_code == 400

    def test_list_payload_does_not_500(self, db):
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/zoho/zoho_crm",
                json=[{"orgId": "O1", "module": {"api_name": "Leads"}, "key_id": "1"}],
            )
        assert resp.status_code != 500
        dispatch.assert_awaited_once()


class TestPmCrmWebhook:
    def test_head_handshake(self, db):
        resp = make_client(db).head("/webhooks/pm-crm/trello")
        assert resp.status_code == 200

    def test_unsupported_integration_400(self, db):
        resp = make_client(db).post("/webhooks/pm-crm/mystery", json={})
        assert resp.status_code == 400

    def test_asana_hook_secret_handshake(self, db):
        resp = make_client(db).post(
            "/webhooks/pm-crm/asana", json={}, headers={"X-Hook-Secret": "sec-1"}
        )
        assert resp.status_code == 200
        assert resp.headers["X-Hook-Secret"] == "sec-1"

    def test_monday_challenge(self, db):
        resp = make_client(db).post("/webhooks/pm-crm/monday", json={"challenge": "ch-1"})
        assert resp.status_code == 200
        assert resp.json()["challenge"] == "ch-1"

    def test_no_external_id_ignored(self, db):
        with _discovery():
            resp = make_client(db).post("/webhooks/pm-crm/jira", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_tenant_not_found_ignored(self, db):
        with _discovery(None):
            resp = make_client(db).post(
                "/webhooks/pm-crm/jira", json={"clientKey": "ck-1", "issue": {"id": "1"}}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_success_dispatches(self, db):
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/pm-crm/jira",
                json={"clientKey": "ck-1", "issue": {"id": "1", "key": "J-1", "fields": {}}},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()
        assert dispatch.call_args.kwargs["integration_id"] == "jira"

    def test_query_param_external_id(self, db):
        with _discovery() as discovery, _dispatch():
            resp = make_client(db).post(
                "/webhooks/pm-crm/jira?clientKey=ck-2", json={"issue": {"id": "1"}}
            )
        assert resp.status_code == 200
        discovery.return_value.get_tenant_id_by_external_id.assert_awaited()


class TestCommunicationWebhook:
    def test_head_handshake(self, db):
        resp = make_client(db).head("/webhooks/communication/discord")
        assert resp.status_code == 200

    def test_unsupported_integration_400(self, db):
        resp = make_client(db).post("/webhooks/communication/mystery", json={})
        assert resp.status_code == 400

    def test_tenant_not_found_ignored(self, db):
        with _discovery(None):
            resp = make_client(db).post(
                "/webhooks/communication/discord", json={"guild_id": "g1"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_twilio_form_encoded(self, db):
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/communication/twilio",
                data={"AccountSid": "AC1", "MessageSid": "SM1", "From": "+1", "To": "+2"},
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()

    def test_telegram_nested_chat(self, db):
        with _discovery() as discovery, _dispatch():
            resp = make_client(db).post(
                "/webhooks/communication/telegram",
                json={"message": {"text": "hi", "chat": {"id": "chat-1"}}},
            )
        assert resp.status_code == 200
        discovery.return_value.get_tenant_id_by_external_id.assert_awaited()

    def test_query_param_fallback(self, db):
        with _discovery() as discovery, _dispatch():
            resp = make_client(db).post(
                "/webhooks/communication/discord?guild_id=g2", json={}
            )
        assert resp.status_code == 200
        discovery.return_value.get_tenant_id_by_external_id.assert_awaited()

    def test_success_dispatches(self, db):
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/communication/intercom",
                json={"app_id": "app-1", "data": {"id": "1"}},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()

    def test_invalid_json_fallback(self, db):
        with _discovery(None):
            resp = make_client(db).post("/webhooks/communication/discord", content=b"nope")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"


class TestDevProdWebhook:
    def test_dropbox_challenge(self, db):
        resp = make_client(db).get("/webhooks/dev-prod/dropbox?challenge=ch-1")
        assert resp.status_code == 200
        assert resp.text == "ch-1"

    def test_onedrive_validation_token(self, db):
        resp = make_client(db).get("/webhooks/dev-prod/onedrive?validationToken=vt-1")
        assert resp.status_code == 200
        assert resp.text == "vt-1"

    def test_unsupported_integration_400(self, db):
        resp = make_client(db).post("/webhooks/dev-prod/mystery", json={})
        assert resp.status_code == 400

    def test_github_ping(self, db):
        resp = make_client(db).post(
            "/webhooks/dev-prod/github", json={}, headers={"X-GitHub-Event": "ping"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_github_zen_ping(self, db):
        resp = make_client(db).post(
            "/webhooks/dev-prod/github", json={"zen": "Keep it simple"}
        )
        assert resp.status_code == 200
        assert resp.json()["zen"] == "Keep it simple"

    def test_tenant_not_found_ignored(self, db):
        with _discovery(None):
            resp = make_client(db).post(
                "/webhooks/dev-prod/github", json={"repository": {"owner": {"login": "org1"}}}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_success_dispatches(self, db):
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/dev-prod/github",
                json={"repository": {"owner": {"login": "org1"}}, "ref": "main"},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()

    def test_query_param_fallback(self, db):
        with _discovery() as discovery, _dispatch():
            resp = make_client(db).post("/webhooks/dev-prod/box?org_id=o1", json={})
        assert resp.status_code == 200
        discovery.return_value.get_tenant_id_by_external_id.assert_awaited()


class TestEcommerceMarketingWebhook:
    def test_head_handshake(self, db):
        resp = make_client(db).head("/webhooks/ecommerce-marketing/shopify")
        assert resp.status_code == 200

    def test_get_validation(self, db):
        resp = make_client(db).get("/webhooks/ecommerce-marketing/mailchimp")
        assert resp.status_code == 200

    def test_unsupported_integration_400(self, db):
        resp = make_client(db).post("/webhooks/ecommerce-marketing/mystery", json={})
        assert resp.status_code == 400

    def test_zoom_url_validation(self, db):
        resp = make_client(db).post(
            "/webhooks/ecommerce-marketing/zoom",
            json={"event": "endpoint.url_validation", "payload": {"plainToken": "pt-1"}},
        )
        assert resp.status_code == 200
        assert resp.json()["plainToken"] == "pt-1"

    def test_tenant_not_found_ignored(self, db):
        with _discovery(None):
            resp = make_client(db).post(
                "/webhooks/ecommerce-marketing/shopify", json={"domain": "shop1.myshopify.com"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_mailchimp_form_encoded(self, db):
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/ecommerce-marketing/mailchimp?list_id=list-1",
                data={"type": "subscribe"},
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()

    def test_sendgrid_list_payload(self, db):
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/ecommerce-marketing/sendgrid",
                json=[{"useragent": "ua-1", "event": "delivered"}],
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()

    def test_success_dispatches(self, db):
        with _discovery(), _dispatch() as dispatch:
            resp = make_client(db).post(
                "/webhooks/ecommerce-marketing/shopify",
                json={"domain": "shop1.myshopify.com", "topic": "orders/create", "id": "1"},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()

    def test_query_param_fallback(self, db):
        with _discovery() as discovery, _dispatch():
            resp = make_client(db).post("/webhooks/ecommerce-marketing/stripe?account_id=acct_1", json={})
        assert resp.status_code == 200
        discovery.return_value.get_tenant_id_by_external_id.assert_awaited()
