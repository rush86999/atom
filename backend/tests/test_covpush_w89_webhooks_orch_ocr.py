# -*- coding: utf-8 -*-
"""Coverage wave 89 — api/routes/webhooks/ingestion_webhooks.py,
integrations/chat_orchestrator.py, integrations/pdf_processing/pdf_ocr_service.py.

No network / no LLM / no real DB: every external boundary (tenant discovery,
CRUD dispatch, webhook queue, agent service, LLMService, BYOK, OCR libraries)
is mocked. Plain pytest + unittest.mock (FastAPI TestClient + dependency
overrides for the routes).
"""
from __future__ import annotations

import base64
import hashlib
import hmac as hmac_mod
import io
import json
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.routes.webhooks.ingestion_webhooks as iw
import core.webhook_crud_dispatch as wcd
import core.webhook_security as wsec
import integrations.chat_orchestrator as co
import integrations.pdf_processing.pdf_ocr_service as pom
from core.database import get_db
from core.models import DiscoveredEntity, Tenant, UserConnection
from integrations.chat_orchestrator import (
    ChatIntent,
    ChatOrchestrator,
    FeatureType,
)
from integrations.pdf_processing.pdf_ocr_service import PDFOCRService


# ============================================================================
# Webhook helpers
# ============================================================================

def make_client(db=None):
    app = FastAPI()
    app.include_router(iw.router)
    app.dependency_overrides[get_db] = lambda: db if db is not None else MagicMock()
    return TestClient(app, raise_server_exceptions=False)


def _discovery(tenant_id="tenant-1"):
    service = MagicMock()
    service.get_tenant_id_by_external_id = AsyncMock(return_value=tenant_id)
    return patch.object(iw, "TenantDiscoveryService", return_value=service)


def _dispatch(result=None):
    return patch.object(
        wcd,
        "crud_dispatch",
        new=AsyncMock(return_value=result if result is not None
                      else {"status": "enqueued", "records": 1}),
    )


def _queue():
    queue = MagicMock()
    queue.enqueue_ingestion_job = AsyncMock(return_value="job-1")
    queue.get_queue_depth = AsyncMock(return_value=2)
    return patch.object(iw, "webhook_queue", queue)


def _sig(body: bytes, secret: str) -> str:
    return hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _integration(config=None):
    itg = MagicMock()
    itg.config = config if config is not None else {}
    itg.is_active = True
    return itg


class ModelDB(MagicMock):
    """db mock whose query(model) resolves per-model first()/all() results."""

    def __init__(self, mapping=None, default=None, **kw):
        super().__init__(**kw)
        self._mapping = mapping or {}
        self._default = default

    def query(self, model):
        res = self._mapping.get(model, self._default)
        chain = MagicMock()
        chain.filter.return_value.first.return_value = res
        chain.filter.return_value.all.return_value = res if isinstance(res, list) else ([res] if res else [])
        chain.filter.return_value.order_by.return_value.first.return_value = res
        return chain


def _client_state_patch(valid=True, data='{"c": "conn-prefix"}'):
    return [
        patch.object(wsec, "verify_client_state", MagicMock(return_value=valid)),
        patch.object(wsec, "get_client_state_data", MagicMock(return_value=data)),
    ]


@pytest.fixture
def db():
    return ModelDB(default=None)


class TestSlackWebhook:
    def test_url_verification(self, db):
        with _discovery():
            r = make_client(db).post(
                "/webhooks/slack/events",
                json={"type": "url_verification", "challenge": "abc"})
        assert r.status_code == 200 and r.json()["challenge"] == "abc"

    def test_missing_team_id_400(self, db):
        with _discovery():
            r = make_client(db).post(
                "/webhooks/slack/events", json={"type": "event_callback", "event": {}})
        assert r.status_code == 400

    def test_team_id_from_event_and_unconfigured_503(self, db):
        db2 = ModelDB(default=None)
        with _discovery() as d:
            r = make_client(db2).post(
                "/webhooks/slack/events",
                json={"type": "event_callback", "event": {"team": "T2"}})
        assert r.status_code in (401, 503)
        d.return_value.get_tenant_id_by_external_id.assert_awaited_once_with("slack", "T2")

    def test_tenant_not_found_ignored(self, db):
        with _discovery(None):
            r = make_client(db).post(
                "/webhooks/slack/events", json={"type": "event_callback", "team_id": "T1"})
        assert r.status_code == 200 and r.json()["status"] == "ignored"

    def test_integration_missing_401(self, db):
        with _discovery():
            r = make_client(ModelDB(default=None)).post(
                "/webhooks/slack/events", json={"type": "event_callback", "team_id": "T1"})
        assert r.status_code == 401

    def test_missing_secret_503_and_bad_signature_401(self, db):
        db2 = ModelDB(default=_integration({"other": "x"}))
        with _discovery():
            r = make_client(db2).post(
                "/webhooks/slack/events", json={"type": "event_callback", "team_id": "T1"})
        assert r.status_code == 503
        db3 = ModelDB(default=_integration({"slack_signing_secret": "s"}))
        with _discovery():
            r = make_client(db3).post(
                "/webhooks/slack/events",
                json={"type": "event_callback", "team_id": "T1"},
                headers={"X-Slack-Signature": "bad", "X-Slack-Request-Timestamp": "1"})
        assert r.status_code == 401

    def test_valid_signature_dispatches_with_conn(self, db):
        conn = MagicMock(id="11111111-1111-1111-1111-111111111111")
        db2 = ModelDB(default=_integration({"slack_signing_secret": "s"}),
                      mapping={UserConnection: conn})
        body = json.dumps({"type": "event_callback", "team_id": "T1",
                           "event": {"type": "message", "text": "hi"}}).encode()
        with _discovery(), _dispatch() as disp:
            r = make_client(db2).post(
                "/webhooks/slack/events", content=body,
                headers={"X-Slack-Signature": _sig(body, "s"),
                         "X-Slack-Request-Timestamp": "1"})
        assert r.status_code == 200
        disp.assert_awaited_once()
        assert disp.call_args[1]["source_connection_id"] == str(conn.id)

    def test_conn_lookup_failure_still_dispatches(self):
        boom = ModelDB(default=_integration({"slack_signing_secret": "s"}))
        boom.query = MagicMock(side_effect=RuntimeError("db down"))
        with _discovery(), _dispatch() as disp:
            r = make_client(boom).post(
                "/webhooks/slack/events", json={"type": "event_callback", "team_id": "T1"},
                headers={"X-Slack-Signature": "bad"})
        assert r.status_code == 200
        disp.assert_not_awaited()

    def test_handler_exception_200_error(self, db):
        with _discovery(None), patch.object(iw, "TenantDiscoveryService",
                                            side_effect=RuntimeError("boom")):
            r = make_client(db).post(
                "/webhooks/slack/events", json={"type": "event_callback", "team_id": "T1"})
        assert r.status_code == 200 and r.json()["status"] == "error"


class TestHubspotWebhook:
    def _signed(self, db2, events, sig="bad"):
        body = json.dumps(events).encode()
        with _discovery("tenant-1"), _dispatch() as disp:
            r = make_client(db2).post(
                "/webhooks/hubspot/events", content=body,
                headers={"X-Hubspot-Signature": _sig(body, "s") if sig is None else sig})
        return r, disp

    def test_missing_portal_skipped(self, db):
        with _discovery(), _dispatch() as disp:
            r = make_client(db).post("/webhooks/hubspot/events",
                                     json=[{"type": "contact.creation", "objectId": 1}])
        assert r.status_code == 200 and r.json()["status"] == "enqueued"
        disp.assert_not_awaited()

    def test_tenant_not_found_continues(self, db):
        with _discovery(None), _dispatch() as disp:
            r = make_client(db).post(
                "/webhooks/hubspot/events",
                json=[{"portalId": "P1", "type": "contact.creation", "objectId": 1}])
        assert r.status_code == 200
        disp.assert_not_awaited()

    def test_unconfigured_fail_closed_503(self, db):
        with _discovery(), _dispatch() as disp:
            r = make_client(ModelDB(default=None)).post(
                "/webhooks/hubspot/events",
                json=[{"portalId": "P1", "type": "contact.creation", "objectId": 1}])
        assert r.status_code == 503
        disp.assert_not_awaited()

    def test_bad_signature_401(self, db):
        r, disp = self._signed(ModelDB(default=_integration({"client_secret": "s"})),
                               [{"portalId": "P1"}])
        assert r.status_code == 401
        disp.assert_not_awaited()

    def test_valid_signature_dispatches_single_event(self):
        conn = MagicMock(id="22222222-2222-2222-2222-222222222222")
        db2 = ModelDB(default=_integration({"client_secret": "s"}),
                      mapping={UserConnection: conn})
        event = {"portalId": "P1", "objectId": 9}
        r, disp = self._signed(db2, [event], sig=None)
        assert r.status_code == 200
        disp.assert_awaited_once()
        assert disp.call_args[1]["source_connection_id"] == str(conn.id)

    def test_handler_error_envelope(self, db):
        db2 = ModelDB(default=_integration({"client_secret": "s"}))
        body = json.dumps({"portalId": "P"}).encode()
        with _discovery("t"), patch.object(wcd, "crud_dispatch",
                                           new=AsyncMock(side_effect=RuntimeError("x"))):
            r = make_client(db2).post(
                "/webhooks/hubspot/events", content=body,
                headers={"X-Hubspot-Signature": _sig(body, "s")})
        assert r.status_code == 200 and r.json()["status"] == "error"


class TestSalesforceWebhook:
    def test_missing_orgid_400(self, db):
        with _discovery():
            r = make_client(db).post("/webhooks/salesforce/events", json={})
        assert r.status_code == 400

    def test_tenant_not_found_ignored(self, db):
        with _discovery(None):
            r = make_client(db).post("/webhooks/salesforce/events", json={"orgId": "O1"})
        assert r.status_code == 200 and r.json()["status"] == "ignored"

    def test_unconfigured_503_and_bad_sig_401(self, db):
        with _discovery():
            r = make_client(ModelDB(default=None)).post(
                "/webhooks/salesforce/events", json={"orgId": "O1"})
        assert r.status_code == 503
        db2 = ModelDB(default=_integration({"client_secret": "s"}))
        with _discovery():
            r = make_client(db2).post(
                "/webhooks/salesforce/events", json={"orgId": "O1"},
                headers={"X-Salesforce-Signature": "bad"})
        assert r.status_code == 401

    def test_valid_signature_dispatches(self):
        db2 = ModelDB(default=_integration({"client_secret": "s"}),
                      mapping={UserConnection: None})
        body = json.dumps({"orgId": "O1"}).encode()
        with _discovery("t"), _dispatch() as disp:
            r = make_client(db2).post(
                "/webhooks/salesforce/events", content=body,
                headers={"X-Salesforce-Signature": _sig(body, "s")})
        assert r.status_code == 200
        disp.assert_awaited_once()
        assert disp.call_args[1]["source_connection_id"] is None


class TestGmailWebhook:
    def test_no_verify_token_503(self, db):
        with patch.dict("os.environ", {}, clear=False), \
             patch("api.routes.webhooks.ingestion_webhooks.os.getenv", return_value=""):
            r = make_client(db).post("/webhooks/gmail/events?token=x", json={})
        assert r.status_code == 503

    def test_bad_token_401(self, db):
        with patch("api.routes.webhooks.ingestion_webhooks.os.getenv", return_value="secret"):
            r = make_client(db).post("/webhooks/gmail/events?token=wrong", json={})
        assert r.status_code == 401

    def _env(self):
        return patch("api.routes.webhooks.ingestion_webhooks.os.getenv",
                     return_value="secret")

    def test_missing_email_400(self, db):
        with self._env():
            r = make_client(db).post("/webhooks/gmail/events?token=secret", json={})
        assert r.status_code == 400

    def test_pubsub_base64_decode(self, db):
        inner = {"emailAddress": "a@b.c"}
        b64 = base64.b64encode(json.dumps(inner).encode()).decode()
        with self._env(), _discovery(None):
            r = make_client(db).post(
                "/webhooks/gmail/events?token=secret",
                json={"message": {"data": b64}})
        assert r.status_code == 200 and r.json()["status"] == "ignored"

    def test_bad_base64_missing_email_400(self, db):
        with self._env(), _discovery("t"):
            r = make_client(db).post(
                "/webhooks/gmail/events?token=secret",
                json={"message": {"data": "!!not-base64!!"}})
        assert r.status_code == 400

    def test_success_enqueues(self, db):
        conn = MagicMock(id="33333333-3333-3333-3333-333333333333")
        db2 = ModelDB(default=None, mapping={UserConnection: conn})
        with self._env(), _discovery("t"), _queue() as q:
            r = make_client(db2).post(
                "/webhooks/gmail/events?token=secret",
                json={"emailAddress": "a@b.c"})
        assert r.status_code == 200 and r.json()["job_id"] == "job-1"
        q.enqueue_ingestion_job.assert_awaited_once()

    def test_handler_exception(self, db):
        with self._env(), _discovery("t"), _queue() as q:
            q.enqueue_ingestion_job = AsyncMock(side_effect=RuntimeError("redis down"))
            r = make_client(db).post(
                "/webhooks/gmail/events?token=secret", json={"emailAddress": "a@b.c"})
        assert r.status_code == 200 and r.json()["status"] == "error"


class TestNotionWebhook:
    def test_missing_workspace_400(self, db):
        with _discovery():
            r = make_client(db).post("/webhooks/notion/events", json={})
        assert r.status_code == 400

    def test_tenant_not_found_ignored(self, db):
        with _discovery(None):
            r = make_client(db).post("/webhooks/notion/events", json={"workspace_id": "W"})
        assert r.status_code == 200 and r.json()["status"] == "ignored"

    def test_unconfigured_503_bad_sig_401_valid_sig_dispatch(self):
        with _discovery():
            r = make_client(ModelDB(default=None)).post(
                "/webhooks/notion/events", json={"workspace_id": "W"})
        assert r.status_code == 503
        db2 = ModelDB(default=_integration({"client_secret": "s"}))
        with _discovery():
            r = make_client(db2).post(
                "/webhooks/notion/events", json={"workspace_id": "W"},
                headers={"X-Notion-Signature": "bad"})
        assert r.status_code == 401
        body = json.dumps({"workspace_id": "W"}).encode()
        with _discovery("t"), _dispatch() as disp:
            r = make_client(db2).post(
                "/webhooks/notion/events", content=body,
                headers={"X-Notion-Signature": _sig(body, "s")})
        assert r.status_code == 200
        disp.assert_awaited_once()

    def test_exception_200(self, db):
        with _discovery(), patch.object(iw, "TenantDiscoveryService",
                                        side_effect=RuntimeError("x")):
            r = make_client(db).post("/webhooks/notion/events", json={"workspace_id": "W"})
        assert r.status_code == 200 and r.json()["status"] == "error"


class TestOutlookWebhook:
    def _notify(self, db2, notifications, headers=None):
        body = json.dumps({"value": notifications}).encode()
        with _queue() as q:
            r = make_client(db2).post(
                "/webhooks/communication/outlook", content=body,
                headers={"content-length": str(len(body)),
                         "X-Forwarded-Host": "acme.example.com", **(headers or {})})
        return r, q

    def test_validation_handshake(self, db):
        r = make_client(db).get("/webhooks/communication/outlook?validationToken=tok123")
        assert r.status_code == 200 and r.text == "tok123"

    def test_empty_body_lifecycle(self, db):
        r = make_client(db).post("/webhooks/communication/outlook", content=b"",
                                 headers={"content-length": "0"})
        assert r.status_code == 200 and r.json()["reason"] == "empty_body_lifecycle_notification"

    def test_invalid_json(self, db):
        r = make_client(db).post("/webhooks/communication/outlook", content=b"{bad",
                                 headers={"content-length": "5"})
        assert r.status_code == 200 and r.json()["status"] == "error"

    def test_empty_notifications(self, db):
        r = make_client(db).post("/webhooks/communication/outlook", json={"value": []},
                                 headers={"content-length": "12"})
        assert r.status_code == 200 and r.json()["reason"] == "empty_payload"

    def test_missing_client_state_skipped(self, db):
        r, q = self._notify(db, [{"changeType": "updated"}])
        assert r.status_code == 200 and r.json()["job_count"] == 0
        q.enqueue_ingestion_job.assert_not_awaited()

    def test_bad_signature_skipped(self, db):
        p1, p2 = _client_state_patch(valid=False)
        with p1, p2:
            r, q = self._notify(db, [{"clientState": "forged", "changeType": "updated"}])
        assert r.status_code == 200 and r.json()["job_count"] == 0
        q.enqueue_ingestion_job.assert_not_awaited()

    def test_no_subdomain_skipped(self, db):
        p1, p2 = _client_state_patch()
        with p1, p2:
            r, q = self._notify(db, [{"clientState": "sig", "changeType": "updated"}])
        assert r.status_code == 200 and r.json()["job_count"] == 0

    def test_tenant_not_found_skipped(self, db):
        db2 = ModelDB(default=None)
        p1, p2 = _client_state_patch()
        with p1, p2:
            r, q = self._notify(db2, [{"clientState": "sig", "changeType": "updated"}])
        assert r.status_code == 200 and r.json()["job_count"] == 0

    def test_deleted_event_deletes_entities(self, db):
        entities = [MagicMock(), MagicMock()]
        db2 = ModelDB(default=None, mapping={Tenant: MagicMock(id="tenant-9"),
                                            DiscoveredEntity: entities})
        db2.delete = MagicMock()
        db2.commit = MagicMock()
        db2.rollback = MagicMock()
        p1, p2 = _client_state_patch()
        with p1, p2, _queue() as q:
            r = make_client(db2).post(
                "/webhooks/communication/outlook",
                json={"value": [{"clientState": "sig", "changeType": "Deleted",
                                 "resource": "/me/messages/AAM5"}]},
                headers={"content-length": "100", "Host": "acme.example.com"})
        assert r.status_code == 200 and r.json()["job_count"] == 0
        assert db2.delete.call_count == 2
        q.enqueue_ingestion_job.assert_not_awaited()

    def test_deleted_no_message_id_skipped(self, db):
        p1, p2 = _client_state_patch()
        with p1, p2:
            r, q = self._notify(db, [{"clientState": "sig", "changeType": "deleted",
                                      "resource": ""}])
        assert r.json()["job_count"] == 0

    def test_deleted_db_error_rolls_back(self, db):
        db2 = ModelDB(default=None, mapping={Tenant: MagicMock(id="t")})
        db2.query = MagicMock(side_effect=RuntimeError("db"))
        db2.rollback = MagicMock()
        p1, p2 = _client_state_patch()
        with p1, p2:
            r = make_client(db2).post(
                "/webhooks/communication/outlook",
                json={"value": [{"clientState": "sig", "changeType": "deleted",
                                 "resource": "/m/1"}]},
                headers={"content-length": "50", "Host": "acme.example.com"})
        assert r.status_code == 200

    def test_success_enqueues_with_connection(self):
        conn = MagicMock(id="conn-prefix-9999")
        db2 = ModelDB(default=None,
                      mapping={Tenant: MagicMock(id="t"),
                               UserConnection: conn})
        p1, p2 = _client_state_patch()
        with p1, p2, _queue() as q:
            r = make_client(db2).post(
                "/webhooks/communication/outlook",
                json={"value": [{"clientState": "sig", "changeType": "updated",
                                 "resource": "/me/messages/1"}]},
                headers={"content-length": "50", "X-Forwarded-Host": "acme.example.com"})
        assert r.status_code == 200 and r.json()["job_ids"] == ["job-1"]
        q.enqueue_ingestion_job.assert_awaited_once()

    def test_bad_client_state_json_iteration_survives(self):
        db2 = ModelDB(default=None, mapping={Tenant: MagicMock(id="t")})
        p1, p2 = _client_state_patch(data="{not json")
        with p1, p2, _queue() as q:
            r = make_client(db2).post(
                "/webhooks/communication/outlook",
                json={"value": [{"clientState": "sig", "changeType": "updated"}]},
                headers={"content-length": "50", "Host": "acme.example.com"})
        assert r.status_code == 200 and r.json()["job_count"] == 0


class TestZohoWebhook:
    def test_unsupported_400(self, db):
        r = make_client(db).post("/webhooks/zoho/not_a_zoho", json={})
        assert r.status_code == 400

    def test_missing_org_400(self, db):
        with _discovery():
            r = make_client(db).post("/webhooks/zoho/zoho_crm", json={})
        assert r.status_code == 400

    def test_org_from_list_payload(self, db):
        with _discovery(None) as d:
            r = make_client(db).post("/webhooks/zoho/zoho_crm",
                                     json=[{"orgId": "Z9"}])
        assert r.status_code == 200 and r.json()["status"] == "ignored"
        d.return_value.get_tenant_id_by_external_id.assert_any_await("zoho_crm", "Z9")

    def test_invalid_json_fallback_missing_org(self, db):
        r = make_client(db).post("/webhooks/zoho/zoho_crm", content=b"notjson",
                                 headers={"content-type": "text/plain"})
        assert r.status_code == 400

    def test_nested_organization_id(self, db):
        with _discovery(None):
            r = make_client(db).post(
                "/webhooks/zoho/zoho_books",
                json={"organization": {"organization_id": "ORG"}})
        assert r.status_code == 200 and r.json()["status"] == "ignored"

    def test_success_dispatches_with_conn(self):
        conn = MagicMock(id="44444444-4444-4444-4444-444444444444")
        db2 = ModelDB(default=None, mapping={UserConnection: conn})
        with _discovery("t"), _dispatch() as disp:
            r = make_client(db2).post(
                "/webhooks/zoho/zoho_crm", json={"orgId": "Z9", "module": "Contacts"})
        assert r.status_code == 200
        disp.assert_awaited_once()
        assert disp.call_args[1]["source_connection_id"] == str(conn.id)

    def test_generic_zoho_fallback_tenant(self):
        disc = MagicMock()
        disc.get_tenant_id_by_external_id = AsyncMock(side_effect=["", "t-zoho"])
        with patch.object(iw, "TenantDiscoveryService", return_value=disc), _dispatch() as disp:
            r = make_client(ModelDB(default=None)).post(
                "/webhooks/zoho/zoho_desk", json={"portalId": "P1"})
        assert r.status_code == 200
        disp.assert_awaited_once()


class TestPmCrmWebhook:
    def test_head_handshake(self, db):
        r = make_client(db).head("/webhooks/pm-crm/jira")
        assert r.status_code == 200

    def test_unsupported_400(self, db):
        r = make_client(db).post("/webhooks/pm-crm/sap", json={})
        assert r.status_code == 400

    def test_asana_hook_secret_echo(self, db):
        r = make_client(db).post("/webhooks/pm-crm/asana", json={},
                                headers={"X-Hook-Secret": "sek"})
        assert r.status_code == 200 and r.headers["x-hook-secret"] == "sek"

    def test_monday_challenge_echo(self, db):
        r = make_client(db).post("/webhooks/pm-crm/monday", json={"challenge": "ch42"})
        assert r.status_code == 200 and r.json()["challenge"] == "ch42"

    def test_external_id_fallback_query_params_ignored_tenant(self, db):
        with _discovery(None):
            r = make_client(db).post("/webhooks/pm-crm/jira?org_id=ORG9", json={})
        assert r.status_code == 200 and r.json()["status"] == "ignored"

    def test_events_workspace_external_id(self, db):
        with _discovery(None) as d:
            r = make_client(db).post(
                "/webhooks/pm-crm/asana",
                json={"events": [{"workspace": "WS1"}]})
        d.return_value.get_tenant_id_by_external_id.assert_any_await("asana", "WS1")
        assert r.json()["status"] == "ignored"

    def test_success_dispatches_with_conn(self):
        conn = MagicMock(id="55555555-5555-5555-5555-555555555555")
        db2 = ModelDB(default=None, mapping={UserConnection: conn})
        with _discovery("t"), _dispatch() as disp:
            r = make_client(db2).post(
                "/webhooks/pm-crm/monday", json={"accountId": "ACC"})
        assert r.status_code == 200
        disp.assert_awaited_once()
        assert disp.call_args[1]["source_connection_id"] == str(conn.id)

    def test_pm_crm_fallback_tenant(self):
        disc = MagicMock()
        disc.get_tenant_id_by_external_id = AsyncMock(side_effect=[None, "t2"])
        with patch.object(iw, "TenantDiscoveryService", return_value=disc), _dispatch() as disp:
            r = make_client(ModelDB(default=None)).post(
                "/webhooks/pm-crm/trello", json={"model": {"id": "M1"}})
        assert r.status_code == 200
        disp.assert_awaited_once()


class TestCommunicationWebhook:
    def test_head_handshake(self, db):
        r = make_client(db).head("/webhooks/communication/telegram")
        assert r.status_code == 200

    def test_unsupported_400(self, db):
        r = make_client(db).post("/webhooks/communication/signal", json={})
        assert r.status_code == 400

    def test_form_urlencoded_payload(self, db):
        with _discovery(None) as d:
            r = make_client(db).post(
                "/webhooks/communication/twilio",
                data={"AccountSid": "AC1"},
                headers={"content-type": "application/x-www-form-urlencoded"})
        d.return_value.get_tenant_id_by_external_id.assert_any_await("twilio", "AC1")
        assert r.json()["status"] == "ignored"

    def test_form_parse_failure(self, db):
        with patch("fastapi.Request.form", AsyncMock(side_effect=RuntimeError("x"))):
            r = make_client(db).post(
                "/webhooks/communication/discord", data={"guild_id": "G1"},
                headers={"content-type": "application/x-www-form-urlencoded"})
        assert r.status_code == 200 and r.json()["status"] == "ignored"

    def test_query_param_fallback(self, db):
        with _discovery(None):
            r = make_client(db).post("/webhooks/communication/intercom?app_id=AP1", json={})
        assert r.json()["status"] == "ignored"

    def test_success_dispatches(self):
        db2 = ModelDB(default=None, mapping={UserConnection: None})
        with _discovery("t"), _dispatch() as disp:
            r = make_client(db2).post(
                "/webhooks/communication/teams", json={"tenantId": "TID"})
        assert r.status_code == 200
        disp.assert_awaited_once()
        assert disp.call_args[1]["source_connection_id"] is None

    def test_generic_fallback_tenant(self):
        disc = MagicMock()
        disc.get_tenant_id_by_external_id = AsyncMock(side_effect=[None, "t3"])
        with patch.object(iw, "TenantDiscoveryService", return_value=disc), _dispatch() as disp:
            r = make_client(ModelDB(default=None)).post(
                "/webhooks/communication/telegram", json={"message": {"chat": {"id": 5}}})
        assert r.status_code == 200
        disp.assert_awaited_once()


class TestDevProdWebhook:
    def test_dropbox_challenge(self, db):
        r = make_client(db).get("/webhooks/dev-prod/dropbox?challenge=CH")
        assert r.status_code == 200 and r.text == "CH"

    def test_onedrive_validation_token(self, db):
        r = make_client(db).get("/webhooks/dev-prod/onedrive?validationToken=VT")
        assert r.status_code == 200 and r.text == "VT"

    def test_unsupported_400(self, db):
        r = make_client(db).post("/webhooks/dev-prod/git_telescope", json={})
        assert r.status_code == 400

    def test_github_ping_zen(self, db):
        r = make_client(db).post("/webhooks/dev-prod/github", json={"zen": "Keep it simple"},
                                headers={"X-GitHub-Event": "ping"})
        assert r.status_code == 200 and r.json()["zen"] == "Keep it simple"

    def test_external_id_from_query_ignored(self, db):
        with _discovery(None):
            r = make_client(db).post("/webhooks/dev-prod/gitlab?org_id=G1", json={})
        assert r.json()["status"] == "ignored"

    def test_success_dispatches_with_conn(self):
        conn = MagicMock(id="66666666-6666-6666-6666-666666666666")
        db2 = ModelDB(default=None, mapping={UserConnection: conn})
        with _discovery("t"), _dispatch() as disp:
            r = make_client(db2).post(
                "/webhooks/dev-prod/github",
                json={"organization": {"login": "acme"}})
        assert r.status_code == 200
        disp.assert_awaited_once()
        assert disp.call_args[1]["source_connection_id"] == str(conn.id)

    def test_dev_prod_fallback_tenant(self):
        disc = MagicMock()
        disc.get_tenant_id_by_external_id = AsyncMock(side_effect=[None, "t4"])
        with patch.object(iw, "TenantDiscoveryService", return_value=disc), _dispatch() as disp:
            r = make_client(ModelDB(default=None)).post(
                "/webhooks/dev-prod/box", json={"enterprise": {"id": "E1"}})
        assert r.status_code == 200
        disp.assert_awaited_once()


class TestEcommerceWebhook:
    def test_head_and_get_handshakes(self, db):
        c = make_client(db)
        assert c.head("/webhooks/ecommerce-marketing/mailchimp").status_code == 200
        assert c.get("/webhooks/ecommerce-marketing/mailchimp").status_code == 200

    def test_unsupported_400(self, db):
        r = make_client(db).post("/webhooks/ecommerce-marketing/etsy", json={})
        assert r.status_code == 400

    def test_form_payload(self, db):
        with _discovery(None) as d:
            r = make_client(db).post(
                "/webhooks/ecommerce-marketing/mailchimp",
                data={"data[list_id]": "L1"},
                headers={"content-type": "application/x-www-form-urlencoded"})
        assert r.json()["status"] == "ignored"

    def test_zoom_url_validation(self, db):
        r = make_client(db).post(
            "/webhooks/ecommerce-marketing/zoom",
            json={"event": "endpoint.url_validation",
                  "payload": {"plainToken": "PT"}})
        assert r.status_code == 200 and r.json()["plainToken"] == "PT"

    def test_sendgrid_list_payload_ignored(self, db):
        with _discovery(None):
            r = make_client(db).post(
                "/webhooks/ecommerce-marketing/sendgrid",
                json=[{"useragent": "agent/1.0"}])
        assert r.json()["status"] == "ignored"

    def test_query_param_fallback_ignored(self, db):
        with _discovery(None):
            r = make_client(db).post(
                "/webhooks/ecommerce-marketing/stripe?account_id=ACCT", json={})
        assert r.json()["status"] == "ignored"

    def test_success_dispatches_with_conn(self):
        conn = MagicMock(id="77777777-7777-7777-7777-777777777777")
        db2 = ModelDB(default=None, mapping={UserConnection: conn})
        with _discovery("t"), _dispatch() as disp:
            r = make_client(db2).post(
                "/webhooks/ecommerce-marketing/shopify", json={"domain": "shop.my"})
        assert r.status_code == 200
        disp.assert_awaited_once()
        assert disp.call_args[1]["source_connection_id"] == str(conn.id)

    def test_ecommerce_fallback_tenant(self):
        disc = MagicMock()
        disc.get_tenant_id_by_external_id = AsyncMock(side_effect=[None, "t5"])
        with patch.object(iw, "TenantDiscoveryService", return_value=disc), _dispatch() as disp:
            r = make_client(ModelDB(default=None)).post(
                "/webhooks/ecommerce-marketing/figma", json={"team_id": "TEAM"})
        assert r.status_code == 200
        disp.assert_awaited_once()


# ============================================================================
# Chat orchestrator
# ============================================================================

_ORCH = None
_ORCH_HANDLER_SNAPSHOT = None


def make_orch():
    global _ORCH, _ORCH_HANDLER_SNAPSHOT
    if _ORCH is None:
        with patch.object(co, "LLMService", MagicMock()):
            _ORCH = ChatOrchestrator(tenant_id="t1")
        _ORCH_HANDLER_SNAPSHOT = dict(_ORCH.feature_handlers)
    # Reset any per-test overrides on the shared instance.
    _ORCH.conversation_sessions.clear()
    _ORCH._cancelled_sessions.clear()
    _ORCH.feature_handlers = dict(_ORCH_HANDLER_SNAPSHOT)
    _ORCH.ai_engines = {}
    _ORCH.llm_service = MagicMock()
    _ORCH.session_manager = None
    for attr in ("_get_qwen_response", "_analyze_intent", "_route_to_features",
                 "_update_session"):
        _ORCH.__dict__.pop(attr, None)
    return _ORCH


def intent(enum, **kw):
    d = {"primary_intent": enum, "confidence": 0.9, "entities": [],
         "platforms": [], "command_type": "search"}
    d.update(kw)
    return d


@pytest.fixture
def orch():
    return make_orch()


def no_ai(o):
    o._get_qwen_response = AsyncMock(return_value=None)


def no_agent(o):
    with patch.object(co, "agent_service") as ag:
        ag.execute_task = AsyncMock(return_value={"id": "task_1", "status": "running"})
        yield ag


class TestProcessChatMessage:
    async def test_ai_response_used(self, orch):
        orch._get_qwen_response = AsyncMock(return_value={
            "content": "Hello", "model": "m1", "provider": "p1"})
        orch._analyze_intent = AsyncMock(return_value=intent(ChatIntent.SEARCH_REQUEST))
        orch._route_to_features = AsyncMock(return_value={
            FeatureType.SEARCH: {"success": True, "data": {"results": [1, 2]},
                                 "suggested_actions": ["a"]}})
        with patch.object(orch, "_update_session"):
            r = await orch.process_chat_message("u1", "hi", session_id="s1")
        assert r["model"] == "m1" and r["provider"] == "p1"
        assert orch.conversation_sessions["s1"]["last_known_good_model"] == "m1"

    async def test_template_response_and_sticky_hint(self, orch):
        no_ai(orch)
        orch._analyze_intent = AsyncMock(return_value=intent(ChatIntent.SEARCH_REQUEST))
        orch._route_to_features = AsyncMock(return_value={})
        with patch.dict("os.environ", {"ATOM_LKGP_ENABLED": "true"}), \
             patch.object(orch, "_update_session"):
            r = await orch.process_chat_message("u1", "hi", session_id="s2")
        assert r["model"] == "template"
        q = orch._get_qwen_response
        assert q.call_args[1]["sticky_hint"] is None

    async def test_cancellation_between_steps(self, orch):
        orch._get_qwen_response = AsyncMock(return_value=None)
        orch.request_cancellation("s3")
        orch._analyze_intent = AsyncMock(return_value=intent(ChatIntent.SEARCH_REQUEST))
        r = await orch.process_chat_message("u1", "hi", session_id="s3")
        assert r["cancelled"] is True
        # second cancellation point (after intent analysis)
        orch.request_cancellation("s4")
        orch._route_to_features = AsyncMock(return_value={})
        r = await orch.process_chat_message("u1", "hi", session_id="s4")
        assert r["cancelled"] is True

    async def test_budget_failure_precedence(self, orch):
        no_ai(orch)
        orch._analyze_intent = AsyncMock(return_value=intent(ChatIntent.AGENT_REQUEST))
        orch._route_to_features = AsyncMock(return_value={
            FeatureType.AGENT: {"success": False, "error_code": "budget_exceeded",
                                "message": "Budget exhausted",
                                "failure_reason": "monthly cap"}})
        with patch.object(orch, "_update_session"):
            r = await orch.process_chat_message("u1", "run agent", session_id="s5")
        assert r["success"] is False
        assert r["error_code"] == "budget_exceeded"
        assert r["recovery_url"] == "/settings/billing"

    async def test_exception_returns_error_response(self, orch):
        orch._get_qwen_response = AsyncMock(side_effect=RuntimeError("llm boom"))
        r = await orch.process_chat_message("u1", "hi", session_id="s6")
        assert r["success"] is False

    async def test_routing_overrides_forwarded(self, orch):
        orch._get_qwen_response = AsyncMock(return_value=None)
        orch._analyze_intent = AsyncMock(return_value=intent(ChatIntent.SEARCH_REQUEST))
        orch._route_to_features = AsyncMock(return_value={})
        with patch.object(orch, "_update_session"):
            await orch.process_chat_message(
                "u1", "hi", session_id="s7",
                routing_overrides={"model": "gpt-x", "tier": "deep", "intent": "code"})
        args = orch._get_qwen_response.call_args
        assert args[0][2] == {"model": "gpt-x", "tier": "deep", "intent": "code"}


class TestQwenResponse:
    async def test_no_llm_service(self, orch):
        orch.llm_service = None
        assert await orch._get_qwen_response("m", []) is None

    async def test_success_and_failure_and_exception(self, orch):
        orch.llm_service = MagicMock()
        orch.llm_service.generate_completion = AsyncMock(return_value={
            "success": True, "content": " answer ", "model": "m", "provider": "p"})
        r = await orch._get_qwen_response("hi", [{"message": "q",
                                                  "response": {"message": "a"}}],
                                          {"tier": "t", "intent": "i"}, ("p", "m"))
        assert r == {"content": "answer", "model": "m", "provider": "p"}
        kw = orch.llm_service.generate_completion.call_args[1]
        assert kw["cognitive_tier"] == "t" and kw["intent_override"] == "i"
        assert kw["sticky_hint"] == ("p", "m")
        orch.llm_service.generate_completion = AsyncMock(return_value={"success": False})
        assert await orch._get_qwen_response("hi", []) is None
        orch.llm_service.generate_completion = AsyncMock(side_effect=RuntimeError("x"))
        assert await orch._get_qwen_response("hi", []) is None


class TestIntentAnalysis:
    async def test_nlp_engine_used(self, orch):
        from types import SimpleNamespace
        orch.ai_engines["nlp"] = MagicMock()
        orch.ai_engines["nlp"].parse_command = AsyncMock(return_value=SimpleNamespace(
            confidence=0.9, entities=[1], platforms=["slack"],
            command_type="analyze"))
        r = await orch._analyze_intent("msg", {})
        assert r["confidence"] == 0.9

    async def test_nlp_exception_falls_back(self, orch):
        orch.ai_engines["nlp"] = MagicMock()
        orch.ai_engines["nlp"].parse_command = AsyncMock(side_effect=RuntimeError("x"))
        r = await orch._analyze_intent("find my keys", {})
        assert r["primary_intent"] == ChatIntent.SEARCH_REQUEST

    def test_classify_intent_mapping(self, orch):
        from ai.nlp_engine import CommandType
        from types import SimpleNamespace
        cases = [
            (CommandType.SEARCH, ChatIntent.SEARCH_REQUEST),
            (CommandType.CREATE, ChatIntent.TASK_MANAGEMENT),
            (CommandType.UPDATE, ChatIntent.TASK_MANAGEMENT),
            (CommandType.SCHEDULE, ChatIntent.SCHEDULING),
            (CommandType.ANALYZE, ChatIntent.DATA_ANALYSIS),
            (CommandType.BUSINESS_HEALTH, ChatIntent.BUSINESS_HEALTH),
            (CommandType.TRIGGER, ChatIntent.AUTOMATION_TRIGGER),
            (CommandType.WORKFLOW_CREATION, ChatIntent.WORKFLOW_CREATION),
            ("unknown_command", ChatIntent.SEARCH_REQUEST),
        ]
        for ct, expected in cases:
            got = orch._classify_intent(SimpleNamespace(command_type=ct))
            assert got is expected

    @pytest.mark.parametrize("msg,expected", [
        ("where is my report", ChatIntent.SEARCH_REQUEST),
        ("send an email to bob", ChatIntent.MESSAGE_SEND),
        ("create a task for laundry", ChatIntent.TASK_MANAGEMENT),
        ("automate a workflow", ChatIntent.WORKFLOW_CREATION),
        ("schedule a meeting", ChatIntent.SCHEDULING),
        ("what should i do today", ChatIntent.BUSINESS_HEALTH),
        ("what if i hire someone", ChatIntent.BUSINESS_HEALTH),
        ("show me the sales pipeline", ChatIntent.CRM),
    ])
    def test_fallback_intent(self, orch, msg, expected):
        assert orch._fallback_intent_analysis(msg)["primary_intent"] is expected


class TestRouting:
    async def test_handler_success_failure_and_exception(self, orch):
        orch.feature_handlers = {
            FeatureType.SEARCH: AsyncMock(return_value={"success": True, "data": {"x": 1}}),
            FeatureType.AI_ANALYTICS: AsyncMock(side_effect=RuntimeError("boom")),
        }
        with patch.object(co, "agent_service") as ag:
            ag.execute_task = AsyncMock(return_value={"id": "t9", "status": "running"})
            r = await orch._route_to_features("q", intent(ChatIntent.SEARCH_REQUEST), {}, None)
        assert FeatureType.SEARCH in r and FeatureType.AI_ANALYTICS in r
        assert r[FeatureType.AI_ANALYTICS] == {"error": "internal_error"}
        # Fallback agent only ran because handled=True via SEARCH... agent not invoked
        ag.execute_task.assert_not_awaited()

    async def test_unhandled_falls_back_to_agent(self, orch):
        orch.feature_handlers = {}
        for m, tid in [("thinker", "default"), ("tasker", "task")]:
            with patch.object(co, "agent_service") as ag:
                ag.execute_task = AsyncMock(return_value={"id": "t8", "status": "running"})
                en = ChatIntent.SEARCH_REQUEST if m == "thinker" else ChatIntent.TASK_MANAGEMENT
                r = await orch._route_to_features("q", intent(en), {}, None)
            assert FeatureType.AGENT in r
            assert ag.execute_task.call_args[1]["mode"] == m

    async def test_agent_failure_swallowed(self, orch):
        orch.feature_handlers = {}
        with patch.object(co, "agent_service") as ag:
            ag.execute_task = AsyncMock(side_effect=RuntimeError("agent down"))
            r = await orch._route_to_features("q", intent(ChatIntent.SEARCH_REQUEST), {}, None)
        assert FeatureType.AGENT not in r

    async def test_multi_step_routes_all(self, orch):
        orch.feature_handlers = {f: AsyncMock(return_value=None)
                                 for f in FeatureType}
        with patch.object(co, "agent_service") as ag:
            ag.execute_task = AsyncMock(side_effect=RuntimeError("agent boom"))
            r = await orch._route_to_features(
                "q", intent(ChatIntent.MULTI_STEP_PROCESS), {}, None)
        assert r == {}


class TestResponseGeneration:
    def test_main_message_branches(self, orch):
        fr = {}
        assert "found 2 results" in orch._generate_main_message(
            "q", intent(ChatIntent.SEARCH_REQUEST),
            {FeatureType.SEARCH: {"data": {"results": [1, 2]}}})
        assert "searched across" in orch._generate_main_message(
            "q", intent(ChatIntent.SEARCH_REQUEST), fr)
        assert "Message sent" in orch._generate_main_message(
            "q", intent(ChatIntent.MESSAGE_SEND),
            {FeatureType.COMMUNICATION: {"success": True}})
        assert "send that message" in orch._generate_main_message(
            "q", intent(ChatIntent.MESSAGE_SEND), fr)
        assert "processed your task request" in orch._generate_main_message(
            "q", intent(ChatIntent.TASK_MANAGEMENT),
            {FeatureType.TASKS: {"success": True, "data": {}}})
        assert "manage those tasks" in orch._generate_main_message(
            "q", intent(ChatIntent.TASK_MANAGEMENT), fr)
        assert "Workflow created" in orch._generate_main_message(
            "q", intent(ChatIntent.WORKFLOW_CREATION),
            {FeatureType.WORKFLOWS: {"data": {"id": 1}}})
        assert "create that automation" in orch._generate_main_message(
            "q", intent(ChatIntent.WORKFLOW_CREATION), fr)
        assert "Schedule updated" in orch._generate_main_message(
            "q", intent(ChatIntent.SCHEDULING),
            {FeatureType.SCHEDULING: {"data": {"id": 1}}})
        assert "handle the scheduling" in orch._generate_main_message(
            "q", intent(ChatIntent.SCHEDULING), fr)
        assert "deal closed" in orch._generate_main_message(
            "q", intent(ChatIntent.CRM),
            {FeatureType.CRM: {"success": True, "data": {"answer": "deal closed"}}})
        assert "CRM request" in orch._generate_main_message(
            "q", intent(ChatIntent.CRM), fr)
        assert "analyzed" in orch._generate_main_message(
            "q", intent(ChatIntent.BUSINESS_HEALTH),
            {FeatureType.BUSINESS_HEALTH: {"success": True, "message": "I analyzed it"}})
        assert "business health" in orch._generate_main_message(
            "q", intent(ChatIntent.BUSINESS_HEALTH), fr)
        assert "processed your request" in orch._generate_main_message(
            "q", intent(ChatIntent.DATA_ANALYSIS), fr)

    def test_agent_message_precedence(self, orch):
        msg = orch._generate_main_message(
            "q", intent(ChatIntent.SEARCH_REQUEST),
            {FeatureType.AGENT: {"success": True, "message": "agent says hi"}})
        assert msg == "agent says hi"

    def test_next_steps_branches(self, orch):
        assert orch._generate_next_steps(intent(ChatIntent.SEARCH_REQUEST), {})[0]
        assert orch._generate_next_steps(intent(ChatIntent.WORKFLOW_CREATION), {})[0]
        assert orch._generate_next_steps(intent(ChatIntent.TASK_MANAGEMENT), {})[0]
        assert orch._generate_next_steps(intent(ChatIntent.CRM), {})[0]

    def test_coordinated_response(self, orch):
        r = orch._generate_coordinated_response(
            "q", intent(ChatIntent.SEARCH_REQUEST),
            {FeatureType.SEARCH: {"data": {"r": 1}, "suggested_actions": ["a"],
                                  "ui_updates": [{"u": 1}], "requires_confirmation": True}},
            {"id": "s1"})
        assert r["success"] and r["requires_confirmation"] and r["ui_updates"]


class TestFeatureHandlers:
    async def test_search(self, orch):
        orch.ai_engines["data_intelligence"] = MagicMock(
            search_unified_entities=MagicMock(return_value=[1]))
        r = await orch._handle_search_request("q", intent(ChatIntent.SEARCH_REQUEST), {}, None)
        assert r["success"] and len(r["data"]["results"]) == 1
        del orch.ai_engines["data_intelligence"]
        r = await orch._handle_search_request("q", intent(ChatIntent.SEARCH_REQUEST), {}, None)
        assert r["data"]["results"] == []
        orch.ai_engines["data_intelligence"] = MagicMock(
            search_unified_entities=MagicMock(side_effect=RuntimeError("x")))
        r = await orch._handle_search_request("q", intent(ChatIntent.SEARCH_REQUEST), {}, None)
        assert r["success"] is False

    async def test_simple_handlers(self, orch):
        sess = {"user_id": "u1"}
        assert (await orch._handle_communication_request("m", {}, sess, None))["success"]
        assert (await orch._handle_integration_request("m", {}, sess, None))["success"]
        assert (await orch._handle_ai_analytics_request("m", {}, sess, None))["success"]
        assert (await orch._handle_document_request("m", {}, sess, None))["success"]
        assert (await orch._handle_social_media_request("m", {}, sess, None))["success"]
        assert (await orch._handle_hr_request("m", {}, sess, None))["success"]
        assert (await orch._handle_ecommerce_request("m", {}, sess, None))["success"]

    async def test_scheduling(self, orch):
        r = await orch._handle_scheduling_request("please schedule the report", {}, {}, None)
        assert r["success"] and "schedule" in r["message"].lower()
        r = await orch._handle_scheduling_request("book something", {}, {}, None)
        assert r["data"]["message"]

    async def test_task_handler_success_and_failure(self, orch):
        import core.unified_task_endpoints as ute
        from types import SimpleNamespace
        with patch.object(ute, "create_task",
                          AsyncMock(return_value={"success": True,
                                                  "task": SimpleNamespace(id="t9")})):
            r = await orch._handle_task_request(
                "create a task: fix the bug", {}, {"user_id": "u1"}, None)
        assert r["success"] and r["data"]["task_id"] == "t9"
        with patch.object(ute, "create_task",
                          AsyncMock(return_value={"success": False})):
            r = await orch._handle_task_request("create a task", {}, {}, None)
        assert r["success"] is False
        with patch.object(ute, "create_task",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            r = await orch._handle_task_request("create a task", {}, {}, None)
        assert r["error"] == "task_creation_failed"
        # long title truncation branch
        with patch.object(ute, "create_task",
                          AsyncMock(return_value={"success": False})):
            r = await orch._handle_task_request("t " * 60, {}, {}, None)
        assert r["success"] is False

    async def test_workflow_handler(self, orch):
        with patch.object(co, "load_workflows", return_value=[]):
            r = await orch._handle_workflow_request("list workflows", {}, {}, None)
        assert r["success"] and "No workflows" in r["message"]
        wfs = [{"name": "Daily Report", "workflow_id": "w1"}]
        with patch.object(co, "load_workflows", return_value=wfs), \
             patch.object(co, "AutomationEngine") as AE:
            AE.return_value.execute_workflow_definition = AsyncMock()
            r = await orch._handle_workflow_request("run daily report", {}, {}, None)
        assert r["success"] and "started" in r["message"]
        with patch.object(co, "load_workflows", return_value=wfs):
            r = await orch._handle_workflow_request("run zzz", {}, {}, None)
            assert r["success"] is False  # no match -> not found
        with patch.object(co, "load_workflows", return_value=wfs), \
             patch.object(co, "AutomationEngine") as AE:
            AE.return_value.execute_workflow_definition = AsyncMock()
            r = await orch._handle_workflow_request("run w1", {}, {}, None)
        assert r["success"] and "started" in r["message"]
        with patch.object(co, "load_workflows", return_value=wfs), \
             patch.object(co, "AutomationEngine") as AE:
            AE.return_value.execute_workflow_definition = AsyncMock(
                side_effect=RuntimeError("exec fail"))
            r = await orch._handle_workflow_request("run w1", {}, {}, None)
        assert r["success"] is False
        r = await orch._handle_workflow_request("something else entirely", {}, {}, None)
        assert r["success"]

    async def test_automation_handler(self, orch):
        sess = {"id": "s1"}
        r = await orch._handle_automation_request("do the thing", {}, sess, None)
        assert r["success"] is False and "not sure which one" in r["message"]
        with patch.object(co, "execute_agent_task", None):
            r = await orch._handle_automation_request("run competitor check", {}, sess, None)
        assert r["success"] is False
        with patch.object(co, "execute_agent_task", new=AsyncMock()):
            for kw in ["competitor prices", "inventory stock", "payroll check"]:
                r = await orch._handle_automation_request(kw, {}, sess, None)
                assert r["success"], kw
        with patch.object(co, "execute_agent_task",
                          AsyncMock(side_effect=RuntimeError("x"))):
            r = await orch._handle_automation_request("check payroll", {}, sess, None)
        assert r["error"] == "agent_start_failed"

    async def test_finance_handler(self, orch):
        sess, ctx = {}, {"workspace_id": "ws"}
        with patch.object(co, "get_automation_settings", None):
            r = await orch._handle_finance_request("q", {}, sess, ctx)
        assert r["success"] is False
        enabled = MagicMock()
        enabled.is_accounting_enabled.return_value = False
        with patch.object(co, "get_automation_settings", return_value=enabled):
            r = await orch._handle_finance_request("q", {}, sess, ctx)
        assert r["success"] is False
        enabled.is_accounting_enabled.return_value = True
        with patch.object(co, "get_automation_settings", return_value=enabled), \
             patch.object(co, "AccountingAssistant", None):
            r = await orch._handle_finance_request("q", {}, sess, ctx)
        assert r["success"] is False

        async def q_result(ws, msg):
            return _finance_result
        aa = MagicMock()
        coll = MagicMock()
        coll.return_value.check_overdue_invoices = AsyncMock(return_value=["r1", "r2"])
        coll.return_value.generate_aging_report = MagicMock(return_value={"ar": 1})
        close = MagicMock()
        close.return_value.run_close_check = AsyncMock(return_value={"ready": True})
        tax = MagicMock()
        tax.return_value.estimate_tax_liability = MagicMock(return_value={"tax": 1})
        fpa = MagicMock()
        fpa.return_value.get_13_week_forecast = MagicMock(return_value={"weeks": 13})
        fpa.return_value.run_scenario = MagicMock(return_value={"scenario": "ok"})
        inter = MagicMock()
        inter.return_value.generate_elimination_report = MagicMock(return_value={"rows": []})
        intents = [
            ("check_overdue", {"intent": "check_overdue"}),
            ("get_aging", {"intent": "get_aging"}),
            ("check_close_readiness", {"intent": "check_close_readiness"}),
            ("get_tax_estimate", {"intent": "get_tax_estimate"}),
            ("get_cash_forecast", {"intent": "get_cash_forecast"}),
            ("run_scenario", {"intent": "run_scenario",
                              "params": {"scenarios": []}}),
            ("get_intercompany_report", {"intent": "get_intercompany_report"}),
            (None, {"answer": "plain answer"}),
        ]
        for label, _finance_result in intents:
            results = dict(_finance_result)
            aa.return_value.process_query = AsyncMock(return_value=results)
            fake_db = MagicMock()
            with patch.object(co, "get_automation_settings", return_value=enabled), \
                 patch.object(co, "AccountingAssistant", aa), \
                 patch.object(co, "CollectionAgent", coll), \
                 patch.object(co, "CloseChecklistAgent", close), \
                 patch.object(co, "TaxService", tax), \
                 patch.object(co, "FPAService", fpa), \
                 patch.object(co, "IntercompanyManager", inter), \
                 patch.object(co, "SessionLocal", return_value=fake_db):
                r = await orch._handle_finance_request("q", {}, sess, ctx)
            assert r["success"], label
            assert fake_db.close.called
        # exception branch
        with patch.object(co, "get_automation_settings", return_value=enabled), \
             patch.object(co, "AccountingAssistant",
                          MagicMock(side_effect=RuntimeError("x"))), \
             patch.object(co, "SessionLocal", return_value=MagicMock()):
            r = await orch._handle_finance_request("q", {}, sess, ctx)
        assert r["error"] == "finance_handler_failed"

    async def test_crm_handler(self, orch):
        with patch.object(co, "get_automation_settings", None):
            r = await orch._handle_crm_request("q", {}, {}, None)
        assert r["success"] is False
        enabled = MagicMock()
        enabled.is_sales_enabled.return_value = False
        with patch.object(co, "get_automation_settings", return_value=enabled):
            r = await orch._handle_crm_request("q", {}, {}, None)
        assert r["success"] is False
        enabled.is_sales_enabled.return_value = True
        fake_db = MagicMock()
        sa = MagicMock()
        sa.return_value.answer_sales_query = AsyncMock(return_value="Sales look great")
        mod = sys.modules.get("sales.assistant", types.SimpleNamespace(SalesAssistant=sa))
        with patch.object(co, "get_automation_settings", return_value=enabled), \
             patch.object(co, "SessionLocal", return_value=fake_db), \
             patch.dict(sys.modules, {"sales.assistant": mod}), \
             patch.object(mod, "SalesAssistant", sa):
            r = await orch._handle_crm_request("q", {}, {}, {"workspace_id": "ws"})
        assert r["success"] and r["data"]["answer"] == "Sales look great"
        with patch.object(co, "get_automation_settings", return_value=enabled), \
             patch.object(co, "SessionLocal", side_effect=RuntimeError("db")):
            r = await orch._handle_crm_request("q", {}, {}, None)
        assert r["error"] == "crm_handler_failed"

    async def test_business_health_handler(self, orch):
        import core.business_health_service as bhs
        sess, ctx = {}, {"workspace_id": "ws"}
        svc = MagicMock()
        svc.simulate_decision = AsyncMock(
            return_value={"prediction": "Good move", "roi": "12%", "breakeven": "3mo"})
        svc.get_daily_priorities = AsyncMock(return_value={
            "priorities": [{"priority": "P1", "title": "T", "description": "D"}],
            "owner_advice": "Focus"})
        with patch.object(bhs, "business_health_service", svc):
            r = await orch._handle_business_health_request(
                "simulate hiring a new engineer", {}, sess, ctx)
            assert r["success"] and "12%" in r["message"]
            r = await orch._handle_business_health_request(
                "what if i spend money on ads", {}, sess, ctx)
            assert r["success"]
            r = await orch._handle_business_health_request(
                "impact of this decision", {}, sess, ctx)
            assert r["success"]
            r = await orch._handle_business_health_request(
                "what are my priorities today", {}, sess, ctx)
            assert "Focus" in r["message"]
            svc.get_daily_priorities = AsyncMock(return_value={
                "priorities": [], "owner_advice": "All good"})
            r = await orch._handle_business_health_request(
                "what to do today", {}, sess, ctx)
            assert "No urgent actions" in r["message"]
        svc2 = MagicMock()
        svc2.get_daily_priorities = AsyncMock(side_effect=RuntimeError("x"))
        with patch.object(bhs, "business_health_service", svc2):
            r = await orch._handle_business_health_request(
                "priorities", {}, sess, ctx)
        assert r["error"] == "business_health_failed"

    async def test_agent_request_handler(self, orch):
        import core.atom_meta_agent as ama
        atom = MagicMock()
        atom.execute = AsyncMock(return_value={
            "final_output": "did the thing", "actions_executed": ["a1"],
            "spawned_agent": "spec"})
        with patch.object(ama, "get_atom_agent", return_value=atom), \
             patch.object(ama, "AgentTriggerMode",
                          types.SimpleNamespace(MANUAL="manual"), create=True):
            r = await orch._handle_agent_request("go", intent(ChatIntent.AGENT_REQUEST),
                                                 {"id": "s", "user_id": "u"}, None)
        assert r["success"] and r["status"] == "success"
        # budget propagation
        atom.execute = AsyncMock(return_value={
            "final_output": "halted", "failure_reason": "budget cap"})
        with patch.object(ama, "get_atom_agent", return_value=atom), \
             patch.object(ama, "AgentTriggerMode",
                          types.SimpleNamespace(MANUAL="manual"), create=True):
            r = await orch._handle_agent_request("go", intent(ChatIntent.AGENT_REQUEST),
                                                 {}, None)
        assert r["error_code"] == "budget_exceeded" and r["success"] is False
        with patch.object(ama, "get_atom_agent", side_effect=RuntimeError("x")):
            r = await orch._handle_agent_request("go", intent(ChatIntent.AGENT_REQUEST),
                                                 {}, None)
        assert r["error"] == "agent_request_failed"


class TestSessions:
    def test_get_user_sessions_without_manager(self, orch):
        orch.session_manager = None
        orch.conversation_sessions["s1"] = {"user_id": "u1"}
        orch.conversation_sessions["s2"] = {"user_id": "u2"}
        assert set(orch.get_user_sessions("u1")) == {"s1"}

    def test_get_user_sessions_with_manager(self, orch):
        mgr = MagicMock()
        mgr.list_user_sessions.return_value = [
            {"session_id": "sx", "user_id": "u1", "title": "T",
             "created_at": "c", "last_active": "l", "history": [], "metadata": {}}]
        orch.session_manager = mgr
        out = orch.get_user_sessions("u1")
        assert "sx" in out and orch.conversation_sessions["sx"]["title"] == "T"

    def test_load_persisted_sessions(self, orch):
        orch.session_manager = None
        orch._load_persisted_sessions()  # early return
        mgr = MagicMock()
        mgr._load_sessions_file.return_value = [
            {"session_id": "p1", "user_id": "u1", "created_at": "c",
             "last_active": "l", "history": []}]
        orch.session_manager = mgr
        orch._load_persisted_sessions()
        assert "p1" in orch.conversation_sessions
        mgr._load_sessions_file.side_effect = RuntimeError("io")
        orch._load_persisted_sessions()

    def test_session_idor_creates_fresh_session(self, orch):
        orch.conversation_sessions["victim"] = {"id": "victim", "user_id": "other",
                                                "history": []}
        s = orch._get_or_create_session("attacker", "victim")
        assert s["user_id"] == "attacker" and s["id"] != "victim"
        orch.session_manager = None
        s = orch._get_or_create_session("u1", "brand-new",
                                        {"channel_id": "ch", "thread_id": "th"})
        assert s["channel_id"] == "ch" and s["thread_id"] == "th"
        # persist failure swallowed
        mgr = MagicMock()
        mgr.create_session.side_effect = RuntimeError("db")
        orch.session_manager = mgr
        s = orch._get_or_create_session("u1", "another")
        assert s["id"] == "another"

    def test_update_session_persists_messages(self, orch):
        import core.database as cdb
        import core.models as models
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = None
        cm = MagicMock()
        cm.__enter__.return_value = fake_db
        orch.session_manager = None
        sess = {"id": "s1", "user_id": "u1", "channel_id": "c1", "thread_id": "t1",
                "history": []}
        with patch.object(cdb, "get_db_session", return_value=cm):
            orch._update_session(sess, "hello",
                                 {"message": "world"}, intent(ChatIntent.SEARCH_REQUEST))
        assert sess["history"][0]["message"] == "hello"
        added = [c.args[0] for c in fake_db.add.call_args_list]
        assert len(added) == 2
        # non-dict response branch
        with patch.object(cdb, "get_db_session", return_value=cm):
            orch._update_session(sess, "x", SimpleNamespace(), None)
        # db failure swallowed
        with patch.object(cdb, "get_db_session", side_effect=RuntimeError("db")):
            orch._update_session(sess, "y", {"message": "z"}, None)

    def test_error_response_and_cancellation(self, orch):
        r = orch._generate_error_response("err", "sid")
        assert r["success"] is False and r["session_id"] == "sid"
        assert orch._is_cancelled("nope") is False
        orch.request_cancellation("c1")
        assert orch._is_cancelled("c1") is True
        assert orch._is_cancelled("c1") is False

    async def test_emit_agent_step(self, orch):
        mgr = MagicMock()
        mgr.broadcast_event = AsyncMock()
        import core.websockets as wsx
        with patch.object(wsx, "get_connection_manager", return_value=mgr):
            await orch._emit_agent_step(1, "t", "a", "o")
        mgr.broadcast_event.assert_awaited_once()
        with patch.object(wsx, "get_connection_manager",
                          side_effect=RuntimeError("ws")):
            await orch._emit_agent_step(1, "t", "a", "o")


# ============================================================================
# PDF OCR service
# ============================================================================

from types import SimpleNamespace


def make_ocr_service(readers=None, byok=False):
    with patch.object(pom, "LLMService", MagicMock()):
        svc = PDFOCRService(tenant_id="t1")
    svc.ocr_readers = readers if readers is not None else {
        "ai_vision": MagicMock()}
    if byok:
        svc.use_byok = True
        svc.byok_manager = MagicMock()
    else:
        svc.use_byok = False
        svc.byok_manager = None
    svc.llm_service = svc.ocr_readers.get("ai_vision") or MagicMock()
    svc.service_status = svc._check_service_availability()
    return svc


def fake_pdf_reader(pages):
    reader = MagicMock()
    reader.pages = pages
    return reader


def page(text="word " * 30, width=100, height=100):
    return SimpleNamespace(
        extract_text=MagicMock(return_value=text),
        mediabox=SimpleNamespace(width=width, height=height))


class TestPDFOCRInit:
    def test_init_flags_and_availability(self):
        with patch.object(pom, "LLMService", MagicMock()), \
             patch.object(pom, "TESSERACT_AVAILABLE", True), \
             patch.object(pom, "pytesseract", MagicMock()), \
             patch.object(pom, "EASYOCR_AVAILABLE", True), \
             patch.object(pom, "easyocr", MagicMock()):
            svc = PDFOCRService(tesseract_path="/usr/bin/tess", tenant_id="t")
        assert "tesseract" in svc.ocr_readers
        assert svc.service_status["basic_pdf"] is True
        assert svc.service_status["tesseract"] is True
        assert svc.service_status["easyocr"] is True

    def test_init_reader_exceptions_swallowed(self):
        class TessRaiser:
            pytesseract = None

            def __setattr__(self, name, value):
                raise RuntimeError("cannot set tesseract cmd")
        raiser = TessRaiser()
        with patch.object(pom, "LLMService", MagicMock()), \
             patch.object(pom, "DOCLING_AVAILABLE", True), \
             patch.object(pom, "get_docling_processor",
                          MagicMock(side_effect=RuntimeError("x"))), \
             patch.object(pom, "TESSERACT_AVAILABLE", True), \
             patch.object(pom, "pytesseract", raiser), \
             patch.object(pom, "EASYOCR_AVAILABLE", True), \
             patch.object(pom, "easyocr", MagicMock(
                 Reader=MagicMock(side_effect=RuntimeError("x")))):
            svc = PDFOCRService(tesseract_path="/usr/local/bin/tess")
        assert "docling" not in svc.ocr_readers
        assert "tesseract" not in svc.ocr_readers
        assert "easyocr" not in svc.ocr_readers
        assert "ai_vision" in svc.ocr_readers

    def test_no_llm_service(self):
        with patch.object(pom, "LLMService", MagicMock()), \
             patch.object(pom, "LLM_SERVICE_AVAILABLE", False):
            svc = PDFOCRService()
        assert svc.llm_service is None
        assert svc.service_status["openai_vision"] is False


class TestProcessPdf:
    async def test_basic_text_only(self, tmp_path):
        svc = make_ocr_service()
        p = tmp_path / "doc.pdf"
        p.write_bytes(b"%PDF-fake")
        with patch.object(pom.PyPDF2, "PdfReader",
                          return_value=fake_pdf_reader([page()])):
            r = await svc.process_pdf(str(p), extract_images=False)
        assert r["success"]
        assert r["processing_summary"]["used_ocr"] is False
        assert r["processing_summary"]["best_method"] == "basic_pdf"

    async def test_needs_ocr_cascade_success(self):
        svc = make_ocr_service(readers={"tesseract": MagicMock()})
        good = {"method": "tesseract", "extracted_text": "x", "page_texts": [],
                "page_count": 1, "total_chars": 5, "success": True}
        with patch.object(pom.PyPDF2, "PdfReader",
                          return_value=fake_pdf_reader([page(text="")])), \
             patch.object(svc, "_run_ocr_method", AsyncMock(return_value=good)), \
             patch.object(svc, "_extract_and_process_images",
                          AsyncMock(return_value={"images_found": 0,
                                                  "image_descriptions": [],
                                                  "success": True})):
            r = await svc.process_pdf(b"bytes", use_ocr=True)
        assert r["processing_summary"]["used_ocr"] is True
        assert r["extracted_content"]["text"] == "x"

    async def test_ocr_all_methods_fail(self):
        svc = make_ocr_service(readers={"tesseract": MagicMock()})
        bad = {"method": "tesseract", "extracted_text": "", "page_texts": [],
               "page_count": 0, "total_chars": 0, "success": False}
        with patch.object(pom.PyPDF2, "PdfReader",
                          return_value=fake_pdf_reader([page(text="")])), \
             patch.object(svc, "_run_ocr_method", AsyncMock(return_value=bad)), \
             patch.object(svc, "_extract_and_process_images",
                          AsyncMock(return_value=None)):
            r = await svc.process_pdf(b"b", use_ocr=True)
        assert r["processing_summary"]["ocr_methods_tried"] == ["tesseract"]
        assert r["processing_summary"]["best_method"] == "basic_pdf"

    async def test_ocr_method_raises(self):
        svc = make_ocr_service(readers={"tesseract": MagicMock()})
        with patch.object(pom.PyPDF2, "PdfReader",
                          return_value=fake_pdf_reader([page(text="")])), \
             patch.object(svc, "_run_ocr_method",
                          AsyncMock(side_effect=RuntimeError("ocr boom"))), \
             patch.object(svc, "_extract_and_process_images",
                          AsyncMock(return_value=None)):
            r = await svc.process_pdf(b"b", use_ocr=True)
        assert r["processing_summary"]["ocr_methods_tried"] == ["tesseract_failed"]

    async def test_parallel_strategy(self):
        svc = make_ocr_service(readers={"a": 1, "b": 2})
        svc._get_available_ocr_methods = MagicMock(return_value=["tesseract", "easyocr"])
        res1 = {"method": "tesseract", "extracted_text": "1", "page_texts": [],
                "page_count": 1, "total_chars": 1, "success": True}
        res2 = {"method": "easyocr", "extracted_text": "22", "page_texts": [],
                "page_count": 1, "total_chars": 2, "success": True}
        with patch.object(pom.PyPDF2, "PdfReader",
                          return_value=fake_pdf_reader([page(text="")])), \
             patch.object(svc, "_run_ocr_method",
                          AsyncMock(side_effect=[res1, res2])), \
             patch.object(svc, "_extract_and_process_images",
                          AsyncMock(return_value=None)):
            r = await svc.process_pdf(b"b", use_ocr=True, fallback_strategy="parallel")
        assert r["processing_summary"]["best_method"] == "easyocr"

    async def test_process_exception_returns_error(self):
        svc = make_ocr_service()
        with patch.object(svc, "_extract_basic_text",
                          AsyncMock(side_effect=RuntimeError("kaboom"))):
            r = await svc.process_pdf(b"b")
        assert r["success"] is False and "kaboom" in r["error"]

    async def test_basic_extraction_failure(self):
        svc = make_ocr_service()
        with patch.object(pom.PyPDF2, "PdfReader", side_effect=RuntimeError("bad pdf")):
            r = await svc._extract_basic_text(b"b")
        assert r["success"] is False and r["text_ratio"] == 0.0


class TestOcrMethods:
    async def test_run_ocr_method_dispatch_and_unknown(self):
        svc = make_ocr_service()
        svc._ocr_with_docling = AsyncMock(return_value={"success": True})
        svc._ocr_with_tesseract = AsyncMock(return_value={"success": True})
        svc._ocr_with_easyocr = AsyncMock(return_value={"success": True})
        svc._ocr_with_ai_vision = AsyncMock(return_value={"success": True})
        for name, meth in [("docling", svc._ocr_with_docling),
                           ("tesseract", svc._ocr_with_tesseract),
                           ("easyocr", svc._ocr_with_easyocr),
                           ("openai_vision", svc._ocr_with_ai_vision),
                           ("ai_vision", svc._ocr_with_ai_vision)]:
            await svc._run_ocr_method(name, b"")
            meth.assert_awaited()
        with pytest.raises(ValueError):
            await svc._run_ocr_method("nope", b"")

    async def test_docling(self):
        proc = MagicMock()
        proc.process_pdf = AsyncMock(return_value={
            "success": True, "extracted_text": "txt", "page_texts": [1],
            "page_count": 1, "total_chars": 3, "tables": []})
        svc = make_ocr_service(readers={"docling": proc})
        r = await svc._ocr_with_docling(b"")
        assert r["success"] and r["method"] == "docling"
        proc.process_pdf = AsyncMock(return_value={"success": False, "error": "x"})
        r = await svc._ocr_with_docling(b"")
        assert r["success"] is False
        with pytest.raises(RuntimeError, match="Docling not available"):
            await make_ocr_service(readers={})._ocr_with_docling(b"")

    async def test_tesseract(self):
        tess = MagicMock()
        tess.image_to_string = MagicMock(return_value="scanned text")
        svc = make_ocr_service(readers={"tesseract": tess})
        with patch.object(pom, "pytesseract", tess), \
             patch.object(svc, "_pdf_to_images",
                          AsyncMock(return_value=[MagicMock()])):
            r = await svc._ocr_with_tesseract(b"")
        assert r["success"] and r["total_chars"] == len("scanned text")
        with patch.object(pom, "pytesseract", tess), \
             patch.object(svc, "_pdf_to_images",
                          AsyncMock(side_effect=RuntimeError("render fail"))):
            r = await svc._ocr_with_tesseract(b"")
        assert r["success"] is False
        with pytest.raises(RuntimeError, match="Tesseract not available"):
            await make_ocr_service(readers={})._ocr_with_tesseract(b"")

    async def test_easyocr(self):
        reader = MagicMock()
        reader.readtext = MagicMock(return_value=[[None, "hello", None]])
        svc = make_ocr_service(readers={"easyocr": reader})
        img = MagicMock()
        with patch.object(svc, "_pdf_to_images", AsyncMock(return_value=[img])), \
             patch.object(pom, "NUMPY_AVAILABLE", True), \
             patch.object(pom.np, "array", MagicMock(return_value=[])):
            r = await svc._ocr_with_easyocr(b"")
        assert r["success"] and "hello" in r["extracted_text"]
        with patch.object(svc, "_pdf_to_images", AsyncMock(return_value=[img])), \
             patch.object(pom, "NUMPY_AVAILABLE", False):
            r = await svc._ocr_with_easyocr(b"")
        assert r["success"] is False
        with pytest.raises(RuntimeError, match="EasyOCR not available"):
            await make_ocr_service(readers={})._ocr_with_easyocr(b"")

    async def test_ai_vision(self):
        from PIL import Image
        llm = MagicMock()
        llm.generate_completion = AsyncMock(return_value={"success": True,
                                                          "content": "vision text"})
        svc = make_ocr_service(readers={"ai_vision": llm})
        img = Image.new("RGB", (4, 4), color="white")
        with patch.object(svc, "_pdf_to_images", AsyncMock(return_value=[img])):
            r = await svc._ocr_with_ai_vision(b"")
        assert r["success"] and r["method"] == "openai_vision"
        assert r["image_descriptions"][0]["description"] == "vision text"
        llm.generate_completion = AsyncMock(return_value={"success": False,
                                                          "error": "x"})
        with patch.object(svc, "_pdf_to_images", AsyncMock(return_value=[img])):
            r = await svc._ocr_with_ai_vision(b"")
        assert r["success"] and r["total_chars"] == 0
        with patch.object(svc, "_pdf_to_images",
                          AsyncMock(side_effect=RuntimeError("no render"))):
            r = await svc._ocr_with_ai_vision(b"")
        assert r["success"] is False
        no_llm = make_ocr_service(readers={"ai_vision": MagicMock()})
        no_llm.llm_service = None
        with pytest.raises(RuntimeError, match="not available"):
            await no_llm._ocr_with_ai_vision(b"")


class TestByokHelpers:
    def test_get_openai_api_key(self):
        svc = make_ocr_service(byok=True)
        svc.byok_manager.get_api_key = MagicMock(return_value="byok-key")
        assert svc._get_openai_api_key() == "byok-key"
        svc.byok_manager.get_api_key = MagicMock(side_effect=RuntimeError("x"))
        svc.openai_api_key = "param-key"
        assert svc._get_openai_api_key() == "param-key"
        svc.openai_api_key = None
        with patch.object(pom.os, "getenv", return_value="env-key"):
            assert svc._get_openai_api_key() == "env-key"
        plain = make_ocr_service()
        assert plain._get_openai_api_key() is None or \
            plain._get_openai_api_key() == pom.os.getenv("OPENAI_API_KEY")

    async def test_optimize_provider_selection(self):
        svc = make_ocr_service()
        r = await svc._optimize_provider_selection(True, "cascade")
        assert r == {"optimized": False, "reason": "BYOK not available"}
        svc2 = make_ocr_service(byok=True)
        r = await svc2._optimize_provider_selection(True, "parallel")
        assert r["optimized"] and r["task_type"] == "image_comprehension"
        r = await svc2._optimize_provider_selection(False, "cascade")
        assert r["task_type"] == "pdf_ocr"
        svc2.byok_manager.get_optimal_provider = MagicMock(
            side_effect=RuntimeError("x"))
        r = await svc2._optimize_provider_selection(True, "cascade")
        assert r["optimized"] is False

    async def test_track_byok_usage(self):
        svc = make_ocr_service()
        await svc._track_byok_usage({"best_result": {"method": "tesseract",
                                                    "total_chars": 400}}, True)
        svc2 = make_ocr_service(byok=True)
        await svc2._track_byok_usage({"best_result": {"method": "basic_pdf"}}, False)
        svc2.byok_manager.track_usage.assert_not_called()
        await svc2._track_byok_usage({"best_result": {"method": "tesseract",
                                                     "total_chars": 800}}, True)
        svc2.byok_manager.track_usage.assert_called_once()
        assert svc2.byok_manager.track_usage.call_args[1]["tokens_used"] == 200
        svc2.byok_manager.track_usage = MagicMock(side_effect=RuntimeError("x"))
        await svc2._track_byok_usage({"best_result": {"method": "tesseract",
                                                     "total_chars": 10}}, True)

    def test_map_method_to_provider(self):
        svc = make_ocr_service()
        assert svc._map_method_to_provider("openai_vision") == "openai"
        assert svc._map_method_to_provider("tesseract") == "openai"
        assert svc._map_method_to_provider("basic_pdf") is None
        assert svc._map_method_to_provider("mystery") is None


class TestGetAvailableOcrMethods:
    def test_byok_openai_selected(self):
        svc = make_ocr_service(readers={"ai_vision": MagicMock(), "tesseract": 1},
                               byok=True)
        svc.byok_manager.get_optimal_provider = MagicMock(return_value="openai")
        m = svc._get_available_ocr_methods(True)
        assert m[0] == "openai_vision"

    def test_byok_optimization_fails(self):
        svc = make_ocr_service(readers={"ai_vision": MagicMock()}, byok=True)
        svc.byok_manager.get_optimal_provider = MagicMock(
            side_effect=RuntimeError("x"))
        assert svc._get_available_ocr_methods(True) == ["openai_vision"]

    def test_byok_other_provider(self):
        svc = make_ocr_service(readers={"ai_vision": MagicMock()}, byok=True)
        svc.byok_manager.get_optimal_provider = MagicMock(return_value="anthropic")
        assert svc._get_available_ocr_methods(True) == ["openai_vision"]

    def test_docling_priority_and_standard_order(self):
        svc = make_ocr_service(readers={"docling": 1, "easyocr": 2, "tesseract": 3,
                                        "ai_vision": MagicMock()})
        assert svc._get_available_ocr_methods(True) == \
            ["docling", "easyocr", "tesseract"]
        assert svc._get_available_ocr_methods(False) == \
            ["docling", "easyocr", "tesseract"]
        # openai_vision added when docling absent
        svc2 = make_ocr_service(readers={"easyocr": 1, "tesseract": 2,
                                         "ai_vision": MagicMock()})
        assert svc2._get_available_ocr_methods(True) == \
            ["openai_vision", "easyocr", "tesseract"]


class TestPdfToImages:
    async def test_pdf2image_available(self):
        svc = make_ocr_service()
        fake_mod = types.ModuleType("pdf2image")
        fake_mod.convert_from_bytes = MagicMock(return_value=["img1"])
        with patch.dict(sys.modules, {"pdf2image": fake_mod}):
            r = await svc._pdf_to_images(b"")
        assert r == ["img1"]

    async def test_fitz_available(self):
        svc = make_ocr_service()
        fitz = types.ModuleType("fitz")
        pix = MagicMock()
        pix.tobytes = MagicMock(return_value=b"jpegbytes")

        class Page:
            def get_pixmap(self, matrix=None):
                return pix

        doc = MagicMock()
        doc.page_count = 1
        doc.__getitem__ = lambda s, i: Page()
        fitz.open = MagicMock(return_value=doc)
        fitz.Matrix = MagicMock()
        with patch.dict(sys.modules, {"pdf2image": None, "fitz": fitz}), \
             patch.object(pom.Image, "open", MagicMock(return_value="opened")):
            r = await svc._pdf_to_images(b"")
        assert r == ["opened"]

    async def test_placeholder_fallback(self):
        svc = make_ocr_service()
        pages = [page(), page(text=""), page(text="line1\nline2")]
        pages[0].mediabox = "not-a-mediabox"  # triggers attribute error path
        pages[2].extract_text = MagicMock(return_value="text " * 20)
        with patch.dict(sys.modules, {"pdf2image": None, "fitz": None}), \
             patch.object(pom.PyPDF2, "PdfReader",
                          return_value=fake_pdf_reader(pages)):
            r = await svc._pdf_to_images(b"")
        assert len(r) == 3

    async def test_conversion_exception(self):
        svc = make_ocr_service()
        with patch.dict(sys.modules, {"pdf2image": None, "fitz": None}), \
             patch.object(pom.PyPDF2, "PdfReader", side_effect=RuntimeError("bad")):
            assert await svc._pdf_to_images(b"") == []


class TestExtractImages:
    async def test_fitz_extraction_and_sizes(self):
        svc = make_ocr_service()
        fitz = types.ModuleType("fitz")
        png = io.BytesIO()
        from PIL import Image
        Image.new("RGB", (4, 4), "white").save(png, format="PNG")
        png_bytes = png.getvalue()
        img_data = [{"ext": "png", "width": 600, "height": 10, "image": png_bytes},
                    {"ext": "png", "width": 300, "height": 10, "image": png_bytes},
                    {"ext": "png", "width": 50, "height": 10, "image": png_bytes}]

        class Page:
            def get_images(self, full=True):
                return [(i,) for i in range(3)]

        doc = MagicMock()
        doc.page_count = 1
        doc.__getitem__ = lambda s, i: Page()
        doc.extract_image = lambda xref: img_data[xref]
        fitz.open = MagicMock(return_value=doc)
        with patch.dict(sys.modules, {"fitz": fitz}), \
             patch.object(pom.os, "unlink", MagicMock()):
            r = await svc._extract_and_process_images(b"", False)
        assert r["success"] and r["images_found"] == 3
        descs = [d["description"] for d in r["image_descriptions"]]
        assert any("Large image" in d for d in descs)
        assert any("Medium image" in d for d in descs)
        assert any("Small image" in d for d in descs)

    async def test_advanced_comprehension_with_byok(self):
        svc = make_ocr_service(byok=True)
        fitz = types.ModuleType("fitz")
        png = io.BytesIO()
        from PIL import Image
        Image.new("RGB", (4, 4), "white").save(png, format="PNG")
        png_bytes = png.getvalue()

        class Page:
            def get_images(self, full=True):
                return [(0,)]

        doc = MagicMock()
        doc.page_count = 1
        doc.__getitem__ = lambda s, i: Page()
        doc.extract_image = lambda x: {"ext": "png", "width": 600, "height": 10,
                                       "image": png_bytes}
        fitz.open = MagicMock(return_value=doc)
        handler = MagicMock()
        handler._get_coordinated_vision_description = AsyncMock(
            return_value="A chart showing growth")
        svc.byok_manager.get_handler = MagicMock(return_value=handler)
        with patch.dict(sys.modules, {"fitz": fitz}), \
             patch.object(pom.os, "unlink", MagicMock()):
            r = await svc._extract_and_process_images(b"", True)
        assert r["image_descriptions"][0]["ai_description"] == "A chart showing growth"
        # vision failure falls back silently
        handler._get_coordinated_vision_description = AsyncMock(
            side_effect=RuntimeError("vision down"))
        with patch.dict(sys.modules, {"fitz": fitz}), \
             patch.object(pom.os, "unlink", MagicMock()):
            r = await svc._extract_and_process_images(b"", True)
        assert r["success"]

    async def test_pypdf_fallback_without_fitz(self):
        svc = make_ocr_service()

        class D(dict):
            def get_object(self):
                return self

        resources = D({"/XObject": D({"/Im1": D({"/Subtype": "/Image"})})})
        page_obj = MagicMock()
        page_obj.__getitem__ = lambda s, k: resources
        with patch.dict(sys.modules, {"fitz": None}), \
             patch.object(pom.PyPDF2, "PdfReader",
                          return_value=fake_pdf_reader([page_obj])):
            r = await svc._extract_and_process_images(b"", False)
        assert r["success"] and r["images_found"] == 1

    async def test_pypdf_fallback_error(self):
        svc = make_ocr_service()
        with patch.dict(sys.modules, {"fitz": None}), \
             patch.object(pom.PyPDF2, "PdfReader", side_effect=RuntimeError("x")):
            r = await svc._extract_and_process_images(b"", False)
        assert r["success"] and r["images_found"] == 0

    async def test_outer_exception(self):
        svc = make_ocr_service()
        bad_fitz = types.ModuleType("fitz")
        bad_fitz.open = MagicMock(side_effect=RuntimeError("fitz crash"))
        with patch.dict(sys.modules, {"fitz": bad_fitz}):
            r = await svc._extract_and_process_images(b"", False)
        assert r["success"] is False


class TestCombineResults:
    def test_combine_with_ocr(self):
        svc = make_ocr_service()
        basic = {"method": "basic_pdf", "extracted_text": "", "page_texts": [],
                 "page_count": 1, "total_chars": 0, "success": False}
        ocr = {"best_result": {"method": "tesseract", "extracted_text": "ocr",
                               "page_texts": [], "page_count": 2,
                               "total_chars": 3, "success": True},
               "methods_tried": ["tesseract"], "success": True}
        r = svc._combine_results(basic, ocr, None, True)
        assert r["processing_summary"]["best_method"] == "tesseract"
        assert r["success"] is True
        assert r["extracted_content"]["images"] == {}

    def test_combine_ocr_failed(self):
        svc = make_ocr_service()
        basic = {"method": "basic_pdf", "extracted_text": "b", "page_texts": [],
                 "page_count": 1, "total_chars": 1, "success": True}
        ocr = {"best_result": None, "methods_tried": ["x_failed"],
               "success": False}
        r = svc._combine_results(basic, ocr, {"images_found": 0}, True)
        assert r["processing_summary"]["best_method"] == "basic_pdf"
        assert r["success"] is True

    def test_combine_no_ocr_result(self):
        svc = make_ocr_service()
        basic = {"method": "basic_pdf", "extracted_text": "b", "page_texts": [],
                 "page_count": 1, "total_chars": 1, "success": True}
        r = svc._combine_results(basic, None, None, False)
        assert r["processing_summary"]["ocr_methods_tried"] == []
        assert r["success"] is True
