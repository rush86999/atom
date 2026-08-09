"""
TDD bug hunt: integrations intgr_c wave (14 atom_* integration modules).

RED tests first — each test asserts the CORRECT behavior and fails against
the pre-fix source (run before the source patch to see the failure, then
re-run after the minimal source fix to see green).

Covers:
- un-awaited async ingestion calls (webhooks / memory API / lancedb routes)
- fail-open webhook signature verification (slack/discord/telegram/gmail/outlook)
- whatsapp "sha256=" signature prefix + HTTPException swallowed into 500
- token payload sliced as string in production API
- phantom fetch_gmail_recent / fetch_discord_recent NameError cascade
- UnifiedLiveMessage missing subject param
- finance zoho httpx NameError + case-sensitive revenue status matching
- projects asana undefined user_id + phantom get_user_tasks + missing id field
- sales pipeline None-status crash
- route shadowing /communications/{app_id} vs /communications/timeline
- teams/whatsapp poisoned bare-import fallbacks (whole integration disabled)
"""

import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from starlette.background import BackgroundTasks
from starlette.requests import Request

from core.auth import get_current_user
from integrations import (
    atom_communication_apps_lancedb_integration as lancedb_intgr,
)
from integrations import (
    atom_communication_live_api as comm_live,
)
from integrations import (
    atom_communication_memory_api as memory_api_mod,
)
from integrations import (
    atom_communication_memory_production_api as prod_api_mod,
)
from integrations import atom_communication_memory_webhooks as webhooks_mod
from integrations import (
    atom_communication_ingestion_pipeline as pipeline_mod,
)
from integrations import atom_finance_live_api as finance_mod
from integrations import atom_projects_live_api as projects_mod
from integrations import atom_sales_live_api as sales_mod
from integrations import atom_teams_integration as teams_mod
from integrations import atom_whatsapp_integration as whatsapp_mod


# ============================================================================
# Helpers
# ============================================================================

def route_endpoint(router, path, method="POST"):
    for r in router.routes:
        if getattr(r, "path", None) == path and method in (r.methods or set()):
            return r.endpoint
    raise AssertionError(f"route {method} {path} not found")


def make_request(body: bytes):
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/webhook",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "scheme": "http",
        "client": ("1.2.3.4", 1234),
    }
    req = Request(scope)
    req._body = body
    return req


def hmac_sig(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class FakeMsg(dict):
    pass


def teams_workspace(**kw):
    o = SimpleNamespace(
        team_id="t1", display_name="Team One", is_active=True, member_count=5,
        channel_count=2, tenant_id="ten", visibility="private",
        web_url="https://teams/t1", last_sync=None,
    )
    for k, v in kw.items():
        setattr(o, k, v)
    return o


def teams_channel(**kw):
    o = SimpleNamespace(
        channel_id="c1", display_name="General", description="desc",
        channel_type="standard", workspace_id="t1", is_archived=False,
        member_count=5, message_count=3, unread_count=0, last_activity_at=None,
        is_muted=False, membership_type="standard", email=None, web_url=None,
        allow_cross_team_posts=False,
    )
    for k, v in kw.items():
        setattr(o, k, v)
    return o


def teams_message(**kw):
    o = SimpleNamespace(
        message_id="m1", text="hello world", html="<p>hello</p>",
        user_id="u1", user_name="Alice", user_email="a@x.com", timestamp="2026-01-01T10:00:00Z",
        thread_id=None, reply_to_id=None, message_type="message", importance="normal",
        subject=None, is_edited=False, edit_timestamp=None, reactions=[],
        attachments=[], mentions=[], files=[], tenant_id="ten", etag="e1",
        channel_identity=None, participant_count=1, metadata={},
    )
    for k, v in kw.items():
        setattr(o, k, v)
    return o


# ============================================================================
# 1. atom_communication_memory_webhooks — fail-open + broken whatsapp
# ============================================================================

class TestMemoryWebhooksFailClosed:
    def _wh(self, monkeypatch, **env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        return webhooks_mod.AtomCommunicationMemoryWebhooks()

    def test_slack_webhook_fails_closed_when_signature_missing(self, monkeypatch):
        wh = self._wh(monkeypatch, ATOM_SLACK_WEBHOOK_SECRET="s3cret")
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/slack")
        body = json.dumps({"event": {"type": "message", "text": "spoof"}}).encode()
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(body), background_tasks=BackgroundTasks(),
                                 x_slack_signature=None, x_slack_request_timestamp=None,
                                 token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_discord_webhook_fails_closed_when_signature_missing(self, monkeypatch):
        wh = self._wh(monkeypatch, ATOM_DISCORD_WEBHOOK_SECRET="dsc")
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/discord")
        body = json.dumps({"message": {"id": "x"}}).encode()
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(body), background_tasks=BackgroundTasks(),
                                 x_signature_ed25519=None, x_signature_timestamp=None, token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_telegram_webhook_fails_closed_when_secret_missing(self, monkeypatch):
        wh = self._wh(monkeypatch, ATOM_TELEGRAM_WEBHOOK_SECRET="tg")
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/telegram")
        body = json.dumps({"message": {"message_id": 1}}).encode()
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(body), background_tasks=BackgroundTasks(), token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_gmail_webhook_fails_closed_when_secret_missing(self, monkeypatch):
        wh = self._wh(monkeypatch, ATOM_GMAIL_WEBHOOK_SECRET="gm")
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/gmail")
        body = json.dumps({"message": {"id": "1"}}).encode()
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(body), background_tasks=BackgroundTasks(),
                                 x_atom_webhook_secret=None, token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_outlook_webhook_fails_closed_when_secret_missing(self, monkeypatch):
        wh = self._wh(monkeypatch, ATOM_OUTLOOK_WEBHOOK_SECRET="ol")
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/outlook")
        body = json.dumps({"value": [{"id": "1"}]}).encode()
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(body), background_tasks=BackgroundTasks(),
                                 x_atom_webhook_secret=None, token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_whatsapp_webhook_rejects_when_secret_unconfigured(self, monkeypatch):
        wh = self._wh(monkeypatch, ATOM_WHATSAPP_WEBHOOK_SECRET="")
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/whatsapp")
        body = json.dumps({"entry": []}).encode()
        sig = hmac_sig("", body)
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(body), background_tasks=BackgroundTasks(),
                                 x_hub_signature_256=sig, token={}))
        assert getattr(exc.value, "status_code", None) == 401


class TestMemoryWebhooksWhatsappSignature:
    def test_whatsapp_accepts_sha256_prefixed_signature(self, monkeypatch):
        monkeypatch.setenv("ATOM_WHATSAPP_WEBHOOK_SECRET", "wa-secret")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/whatsapp")
        body = json.dumps({"entry": [{"changes": [{"value": {"messages": []}}]}]}).encode()
        sig = "sha256=" + hmac_sig("wa-secret", body)
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            result = asyncio.run(endpoint(request=make_request(body),
                                          background_tasks=BackgroundTasks(),
                                          x_hub_signature_256=sig, token={}))
        assert result["status"] == "received"

    def test_whatsapp_invalid_signature_returns_401_not_500(self, monkeypatch):
        monkeypatch.setenv("ATOM_WHATSAPP_WEBHOOK_SECRET", "wa-secret")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/whatsapp")
        body = json.dumps({"entry": []}).encode()
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(body), background_tasks=BackgroundTasks(),
                                 x_hub_signature_256="sha256=deadbeef", token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_slack_webhook_rejects_stale_timestamp(self, monkeypatch):
        monkeypatch.setenv("ATOM_SLACK_WEBHOOK_SECRET", "s3cret")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/slack")
        body = json.dumps({"event": {"type": "message", "text": "hi"}}).encode()
        stale_ts = str(int(time.time()) - 600)
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(body), background_tasks=BackgroundTasks(),
                                 x_slack_signature="v0=deadbeef", x_slack_request_timestamp=stale_ts,
                                 token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_slack_webhook_accepts_valid_signature(self, monkeypatch):
        monkeypatch.setenv("ATOM_SLACK_WEBHOOK_SECRET", "s3cret")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/slack")
        body = json.dumps({"event": {"type": "message", "text": "hi"}}).encode()
        ts = str(int(time.time()))
        sig = "v0=" + hmac.new(b"s3cret", f"v0:{ts}:".encode() + body, hashlib.sha256).hexdigest()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            result = asyncio.run(endpoint(request=make_request(body),
                                          background_tasks=BackgroundTasks(),
                                          x_slack_signature=sig, x_slack_request_timestamp=ts,
                                          token={}))
        assert result["status"] == "received"


class TestMemoryWebhooksProcessorsAwaitIngest:
    @pytest.mark.parametrize("name,payload", [
        ("_process_whatsapp_webhook", {"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "1"}, "messages": [{"id": "m1", "from": "x", "text": {"body": "hi"}}]}}]}]}),
        ("_process_slack_webhook", {"event": {"type": "message", "ts": "123", "user": "u", "channel": "c", "text": "hi"}}),
        ("_process_discord_webhook", {"message": {"id": "m1", "author": {"id": "a"}, "channel_id": "c", "content": "hi"}}),
        ("_process_telegram_webhook", {"message": {"message_id": 1, "from": {"id": 1}, "chat": {"id": 2}, "text": "hi"}}),
        ("_process_gmail_webhook", {"message": {"id": "m1", "sender": "a@b.c", "body": "hi"}}),
        ("_process_outlook_webhook", {"value": [{"id": "m1", "from": {"emailAddress": {"address": "a@b.c"}}, "subject": "s"}]}),
    ])
    def test_processor_awaits_ingestion(self, name, payload):
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            asyncio.run(getattr(wh, name)(payload))
            pipe.ingest_message.assert_awaited()
            assert pipe.ingest_message.await_count == 1


# ============================================================================
# 2. memory API / production API / lancedb routes — un-awaited ingest + token
# ============================================================================

class TestMemoryApiAwaitIngest:
    def test_ingest_endpoint_awaits_pipeline(self):
        router = memory_api_mod.AtomCommunicationMemoryAPI().router
        endpoint = route_endpoint(router, "/api/atom/communication/memory/ingest")
        with patch.object(memory_api_mod, "ingestion_pipeline") as pipe, \
             patch.object(memory_api_mod, "memory_manager") as mm:
            mm.db = Mock()
            pipe.ingest_message = AsyncMock(return_value=True)
            result = asyncio.run(endpoint(app_id="slack", message_data={"id": "1", "content": "hi"}))
        assert result["success"] is True
        pipe.ingest_message.assert_awaited_once_with("slack", {"id": "1", "content": "hi"})

    def test_ingest_batch_awaits_pipeline(self):
        router = memory_api_mod.AtomCommunicationMemoryAPI().router
        endpoint = route_endpoint(router, "/api/atom/communication/memory/ingest/batch")
        with patch.object(memory_api_mod, "ingestion_pipeline") as pipe, \
             patch.object(memory_api_mod, "memory_manager") as mm:
            mm.db = Mock()
            pipe.ingest_message = AsyncMock(return_value=True)
            result = asyncio.run(endpoint(app_id="slack", messages=[{"id": "1"}, {"id": "2"}]))
        assert result["success_count"] == 2
        pipe.ingest_message.assert_awaited()


class TestLanceDBRoutesAwaitIngest:
    def test_ingest_single_awaits_pipeline(self):
        router = lancedb_intgr.CommunicationAppIngestionIntegration().router
        endpoint = route_endpoint(router, "/api/memory/ingestion/ingest/{app_id}")
        with patch.object(lancedb_intgr, "ingestion_pipeline") as pipe, \
             patch.object(lancedb_intgr, "memory_manager") as mm:
            mm.db = Mock()
            pipe.ingest_message = AsyncMock(return_value=True)
            result = asyncio.run(endpoint(app_id="slack", message_data={"id": "1"}))
        assert result["success"] is True
        pipe.ingest_message.assert_awaited()

    def test_ingest_batch_awaits_pipeline(self):
        router = lancedb_intgr.CommunicationAppIngestionIntegration().router
        endpoint = route_endpoint(router, "/api/memory/ingestion/ingest/{app_id}/batch")
        with patch.object(lancedb_intgr, "ingestion_pipeline") as pipe, \
             patch.object(lancedb_intgr, "memory_manager") as mm:
            mm.db = Mock()
            pipe.ingest_message = AsyncMock(return_value=True)
            result = asyncio.run(endpoint(app_id="slack", messages=[{"id": "1"}, {"id": "2"}]))
        assert result["success_count"] == 2
        pipe.ingest_message.assert_awaited()


class TestProductionApiTokenHandling:
    def test_ingest_single_handles_token_payload_dict(self):
        api = prod_api_mod.AtomCommunicationMemoryProductionAPI()
        endpoint = route_endpoint(api.router, "/api/atom/communication/memory/ingest/single")
        with patch.object(prod_api_mod, "ingestion_pipeline") as pipe, \
             patch.object(prod_api_mod, "memory_manager") as mm:
            mm.db = Mock()
            pipe.ingest_message = AsyncMock(return_value=True)
            result = asyncio.run(endpoint(app_id="slack", message_data={"id": "1"}, token={"sub": "user-1"}))
        assert result["success"] is True
        pipe.ingest_message.assert_awaited()

    def test_ingest_batch_handles_token_payload_dict(self):
        api = prod_api_mod.AtomCommunicationMemoryProductionAPI()
        endpoint = route_endpoint(api.router, "/api/atom/communication/memory/ingest/batch")
        with patch.object(prod_api_mod, "ingestion_pipeline") as pipe, \
             patch.object(prod_api_mod, "memory_manager") as mm:
            mm.db = Mock()
            pipe.ingest_message = AsyncMock(return_value=True)
            result = asyncio.run(endpoint(app_id="slack", messages=[{"id": "1"}], token={"sub": "user-1"}))
        assert result["success_count"] == 1

    def test_search_handles_token_payload_dict(self):
        api = prod_api_mod.AtomCommunicationMemoryProductionAPI()
        endpoint = route_endpoint(api.router, "/api/atom/communication/memory/search/production", method="GET")
        with patch.object(prod_api_mod, "memory_manager") as mm:
            mm.db = Mock()
            mm.search_communications = Mock(return_value=[])
            result = asyncio.run(endpoint(query="q", app_id=None, limit=10,
                                          time_start=None, time_end=None,
                                          include_metadata=True, token={"sub": "user-1"}))
        assert result["success"] is True

    def test_analytics_handles_token_payload_dict(self):
        api = prod_api_mod.AtomCommunicationMemoryProductionAPI()
        endpoint = route_endpoint(api.router, "/api/atom/communication/memory/analytics/production", method="GET")
        with patch.object(prod_api_mod, "ingestion_pipeline") as pipe, \
             patch.object(prod_api_mod, "memory_manager") as mm:
            mm.db = Mock()
            mm.connections_table = None
            pipe.get_ingestion_stats = Mock(return_value={"configured_apps": []})
            result = asyncio.run(endpoint(time_start=None, time_end=None, app_id=None,
                                          include_detailed_metrics=True, token={"sub": "user-1"}))
        assert result["success"] is True


# ============================================================================
# 3. atom_communication_live_api — phantom fetchers + subject param
# ============================================================================

class TestCommunicationLiveApi:
    def test_unified_live_message_supports_subject(self):
        msg = comm_live.UnifiedLiveMessage(
            id="zoho_1", provider="zoho", content="body", sender="s@x.com",
            timestamp=datetime(2026, 1, 1), subject="Hello")
        d = msg.to_dict()
        assert d["subject"] == "Hello"

    def test_zoho_mapping_passes_subject(self, monkeypatch):
        monkeypatch.setenv("ZOHO_CRM_ACCESS_TOKEN", "zoho-tok")
        with patch.object(comm_live, "ZohoMailService") as zcls:
            zcls.return_value.get_recent_inbox = AsyncMock(return_value=[{
                "messageId": "m1", "sender": "a@b.c", "subject": "Re: hi",
                "summary": "sum", "sentTimeInMS": 1735689600000, "status": "read"}])
            msgs = asyncio.run(comm_live.fetch_zoho_mail_recent(limit=10))
        assert len(msgs) == 1
        assert msgs[0]["subject"] == "Re: hi"

    def test_recent_contacts_survives_missing_gmail_and_discord_fetchers(self, monkeypatch):
        # GMAIL_AVAILABLE/DISCORD_AVAILABLE are True but the fetch helpers do not exist.
        monkeypatch.setattr(comm_live, "SLACK_AVAILABLE", False)
        monkeypatch.setattr(comm_live, "GMAIL_AVAILABLE", True)
        monkeypatch.setattr(comm_live, "DISCORD_AVAILABLE", True)
        monkeypatch.setattr(comm_live, "M365_AVAILABLE", True)
        monkeypatch.setenv("MICROSOFT_365_ACCESS_TOKEN", "ms-tok")
        with patch.object(comm_live, "fetch_outlook_recent", AsyncMock(return_value=[{
                "sender": "out@x.com", "timestamp": "2026-01-01T00:00:00"}])), \
             patch.object(comm_live, "fetch_teams_recent", AsyncMock(return_value=[{
                "sender": "team@x.com", "timestamp": "2026-01-01T00:00:00"}])), \
             patch.object(comm_live, "fetch_zoho_mail_recent", AsyncMock(return_value=[{
                "sender": "zoho@x.com", "timestamp": "2026-01-01T00:00:00"}])), \
             patch.object(comm_live, "fetch_slack_recent", AsyncMock(return_value=[])):
            result = asyncio.run(comm_live.get_recent_contacts(limit=10))
        senders = {c["name"] for c in result["contacts"]}
        assert {"out@x.com", "team@x.com", "zoho@x.com"} <= senders


# ============================================================================
# 4. finance / projects / sales live APIs
# ============================================================================

class TestFinanceLiveApi:
    def test_zoho_books_fetch_works_with_tokens(self, monkeypatch):
        monkeypatch.setenv("ZOHO_CRM_ACCESS_TOKEN", "zoho")
        monkeypatch.setenv("ZOHO_BOOKS_ORG_ID", "org1")
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        monkeypatch.delenv("XERO_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("MICROSOFT_365_ACCESS_TOKEN", raising=False)

        class FakeResp:
            status_code = 200
            def json(self):
                return {"invoices": [{
                    "invoice_id": "inv1", "invoice_number": "INV-1",
                    "total": 100.0, "currency_code": "USD", "date": "2026-01-01",
                    "status": "paid", "customer_name": "Acme"}]}

        fake_client = AsyncMock()
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)
        fake_client.get = AsyncMock(return_value=FakeResp())

        with patch.object(finance_mod, "ZohoBooksService") as zcls:
            zcls.return_value._get_headers = Mock(return_value={"Authorization": "x"})
            zcls.return_value.base_url = "https://books.zoho.com/api/v3"
            with patch("httpx.AsyncClient", return_value=fake_client):
                result = asyncio.run(finance_mod.get_live_financial_overview(limit=10))
        assert result.providers["zoho"] is True
        assert any(t.platform == "zoho" for t in result.transactions)

    def test_total_revenue_counts_uppercase_paid_status(self, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        monkeypatch.delenv("XERO_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("ZOHO_CRM_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("MICROSOFT_365_ACCESS_TOKEN", raising=False)
        # Simulate a Xero invoice with uppercase "PAID" status via direct mapping
        tx = finance_mod.map_xero_invoice({
            "InvoiceID": "x1", "InvoiceNumber": "X-1", "Total": "200.0",
            "CurrencyCode": "USD", "DateString": "2026-01-01", "Status": "PAID"})
        assert tx.status == "PAID"


class TestProjectsLiveApi:
    def test_asana_fetch_works_when_token_configured(self, monkeypatch):
        monkeypatch.setenv("ASANA_ACCESS_TOKEN", "asana-tok")
        monkeypatch.delenv("ZOHO_CRM_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("ZOHO_PROJECTS_PORTAL_ID", raising=False)
        monkeypatch.delenv("MICROSOFT_365_ACCESS_TOKEN", raising=False)
        with patch.object(projects_mod, "asana_service") as asvc, \
             patch.object(projects_mod, "get_jira_service", return_value=None):
            asvc.get_tasks = AsyncMock(return_value={"data": [
                {"gid": "g1", "name": "Ship it", "completed": False, "due_on": "2026-02-01"}]})
            result = asyncio.run(projects_mod.get_live_project_board(limit=10))
        assert result.providers["asana"] is True
        assert any(t.name == "Ship it" for t in result.tasks)

    def test_unified_task_has_id_field(self):
        t = projects_mod.map_asana_task({"gid": "g1", "name": "T", "completed": False})
        assert t.id == "g1"
        j = projects_mod.map_jira_issue({"key": "K-1", "fields": {"summary": "S"}}, "https://x")
        assert j.id == "K-1"
        z = projects_mod.map_zoho_task({"id_string": "z1", "name": "Z"})
        assert z.id == "z1"
        p = projects_mod.map_planner_task({"id": "p1", "title": "P"})
        assert p.id == "p1"


class TestSalesLiveApi:
    def test_pipeline_does_not_crash_on_none_status(self, monkeypatch):
        monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "hub-tok")
        monkeypatch.delenv("SALESFORCE_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("ZOHO_CRM_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("MICROSOFT_365_ACCESS_TOKEN", raising=False)
        with patch.object(sales_mod, "get_hubspot_service") as hsvc:
            hsvc.return_value.get_deals = AsyncMock(return_value=[
                {"id": "d1", "properties": {"dealname": "Deal", "amount": "50", "dealstage": None}}])
            result = asyncio.run(sales_mod.get_live_pipeline(limit=10))
        assert result.ok is True
        assert result.stats.total_pipeline_value == 50.0

    def test_limit_out_of_range_rejected(self, monkeypatch):
        with pytest.raises(Exception) as exc:
            asyncio.run(sales_mod.get_live_pipeline(limit=0))
        assert getattr(exc.value, "status_code", None) == 400


# ============================================================================
# 5. lancedb integration — timeline route shadowed by {app_id}
# ============================================================================

class TestLanceDBTimelineRoute:
    def test_timeline_route_not_shadowed(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        router = lancedb_intgr.CommunicationAppIngestionIntegration().router
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
        with patch.object(lancedb_intgr, "memory_manager") as mm:
            mm.db = Mock()
            mm.get_communications_by_timeframe = Mock(return_value=[{"id": "1", "app_type": "slack"}])
            client = TestClient(app)
            resp = client.get("/api/memory/ingestion/communications/timeline",
                              params={"start_date": "2026-01-01", "end_date": "2026-01-02"})
        assert resp.status_code == 200
        assert resp.json()["total_results"] == 1


# ============================================================================
# 6. atom_teams_integration — poisoned imports disable the whole integration
# ============================================================================

class TestTeamsIntegrationServices:
    def test_teams_enhanced_service_loaded_with_qualified_imports(self):
        assert teams_mod.teams_enhanced_service is not None, (
            "teams_enhanced_service must load via qualified integrations. import"
        )

    def test_integration_initializes_with_services(self):
        svc = teams_mod.AtomTeamsIntegration({
            "atom_memory_service": Mock(),
            "atom_search_service": Mock(),
            "atom_workflow_service": Mock(),
        })
        svc.teams_service = Mock()
        svc.teams_service.event_handlers = {}
        svc.teams_analytics = Mock()
        with patch.object(svc, "_start_integration_workers", new_callable=AsyncMock), \
             patch.object(svc, "_initialize_unified_data", new_callable=AsyncMock), \
             patch.object(svc, "_setup_cross_platform_handlers", new_callable=AsyncMock):
            assert asyncio.run(svc.initialize()) is True
        assert svc.is_initialized is True

    def test_initialize_returns_false_when_services_missing(self):
        svc = teams_mod.AtomTeamsIntegration({})
        svc.teams_service = None
        assert asyncio.run(svc.initialize()) is False

    def test_get_unified_workspaces(self):
        svc = teams_mod.AtomTeamsIntegration({})
        svc.teams_service = Mock()
        svc.teams_service.get_workspaces = AsyncMock(return_value=[teams_workspace()])
        result = asyncio.run(svc.get_unified_workspaces("u1"))
        assert result[0]["id"] == "teams_t1"
        assert result[0]["name"] == "Team One"

    def test_get_unified_workspaces_error_returns_empty(self):
        svc = teams_mod.AtomTeamsIntegration({})
        svc.teams_service = Mock()
        svc.teams_service.get_workspaces = AsyncMock(side_effect=RuntimeError("boom"))
        assert asyncio.run(svc.get_unified_workspaces("u1")) == []

    def test_get_unified_channels_non_teams_workspace_returns_empty(self):
        svc = teams_mod.AtomTeamsIntegration({})
        assert asyncio.run(svc.get_unified_channels("slack_1", "u1")) == []

    def test_get_unified_channels(self):
        svc = teams_mod.AtomTeamsIntegration({})
        svc.teams_service = Mock()
        svc.teams_service.get_channels = AsyncMock(return_value=[teams_channel()])
        result = asyncio.run(svc.get_unified_channels("teams_t1", "u1"))
        assert result[0]["id"] == "teams_c1"
        assert svc.communication_channels  # stored

    def test_send_unified_message_success(self):
        svc = teams_mod.AtomTeamsIntegration({})
        svc.teams_service = Mock()
        svc.teams_service.send_message = AsyncMock(return_value={"ok": True, "message_id": "m1"})
        with patch.object(svc, "_store_message_in_memory", new_callable=AsyncMock), \
             patch.object(svc, "_index_message_in_search", new_callable=AsyncMock), \
             patch.object(svc, "_trigger_workflows", new_callable=AsyncMock):
            result = asyncio.run(svc.send_unified_message("teams_t1", "teams_c1", "hello"))
        assert result["ok"] is True
        assert result["message_id"] == "m1"

    def test_send_unified_message_invalid_workspace(self):
        svc = teams_mod.AtomTeamsIntegration({})
        svc.teams_service = Mock()
        result = asyncio.run(svc.send_unified_message("slack_w", "teams_c1", "hello"))
        assert result["ok"] is False
        assert "Invalid workspace ID" not in result["error"]  # no str(e) leak

    def test_send_unified_message_non_teams_channel(self):
        svc = teams_mod.AtomTeamsIntegration({})
        result = asyncio.run(svc.send_unified_message("slack_w", "slack_c", "hello"))
        assert result["ok"] is False
        assert result["error"] == "Unsupported platform"

    def test_get_unified_messages(self):
        svc = teams_mod.AtomTeamsIntegration({})
        svc.teams_service = Mock()
        svc.teams_service.get_channel_messages = AsyncMock(return_value=[teams_message()])
        result = asyncio.run(svc.get_unified_messages("teams_t1", "teams_c1", limit=10))
        assert result[0]["id"] == "teams_m1"

    def test_unified_search(self):
        svc = teams_mod.AtomTeamsIntegration({})
        svc.teams_service = Mock()
        svc.teams_service.search_messages = AsyncMock(return_value={"ok": True, "messages": [teams_message()]})
        result = asyncio.run(svc.unified_search("hello", workspace_id="teams_t1", channel_id="teams_c1"))
        assert result[0]["id"] == "teams_m1"

    def test_unified_search_without_channel_returns_empty(self):
        svc = teams_mod.AtomTeamsIntegration({})
        assert asyncio.run(svc.unified_search("hello")) == []

    def test_create_unified_workflow_non_teams_delegates(self):
        svc = teams_mod.AtomTeamsIntegration({})
        svc.atom_workflow = Mock()
        svc.atom_workflow.create_workflow = AsyncMock(return_value={"ok": True, "id": "wf1"})
        result = asyncio.run(svc.create_unified_workflow({"name": "N", "triggers": [], "actions": []}))
        assert result["ok"] is True
        svc.atom_workflow.create_workflow.assert_awaited_once()

    def test_create_unified_workflow_teams_engine_unavailable(self):
        svc = teams_mod.AtomTeamsIntegration({})
        result = asyncio.run(svc.create_unified_workflow({
            "name": "N", "triggers": [{"platform": "microsoft_teams", "event": "x"}], "actions": []}))
        assert result["ok"] is False

    def test_get_unified_analytics(self):
        svc = teams_mod.AtomTeamsIntegration({})
        point = SimpleNamespace(timestamp=datetime(2026, 1, 1), value=1.0, dimensions={}, metadata={})
        svc.teams_analytics = Mock()
        svc.teams_analytics.get_analytics = AsyncMock(return_value=[point])
        result = asyncio.run(svc.get_unified_analytics("messages", "7d", "teams_t1"))
        assert result["total_points"] == 1

    def test_generate_search_highlights(self):
        svc = teams_mod.AtomTeamsIntegration({})
        hl = svc._generate_search_highlights("the quick brown fox jumps over the lazy dog", "fox")
        assert hl and "fox" in hl[0]

    def test_setup_cross_platform_handlers_registers_handlers(self):
        svc = teams_mod.AtomTeamsIntegration({})
        svc.teams_service = Mock()
        svc.teams_service.event_handlers = {"message": [], "file_upload": [], "user_join": []}
        with patch("integrations.atom_teams_integration.TeamsEventType") as tet:
            tet.MESSAGE = "message"
            tet.FILE_UPLOAD = "file_upload"
            tet.USER_JOIN = "user_join"
            asyncio.run(svc._setup_cross_platform_handlers())
        assert svc.teams_service.event_handlers["message"]

    def test_cross_platform_handlers_work(self):
        svc = teams_mod.AtomTeamsIntegration({})
        svc.atom_memory = Mock()
        svc.atom_memory.store = AsyncMock()
        svc.atom_search = Mock()
        svc.atom_search.index = AsyncMock()
        svc.atom_workflow = Mock()
        svc.atom_workflow.trigger_workflows = AsyncMock()
        asyncio.run(svc._handle_teams_message_cross_platform({"message_id": "m1", "text": "hi"}))
        svc.atom_memory.store.assert_awaited_once()
        svc.atom_search.index.assert_awaited_once()
        svc.atom_workflow.trigger_workflows.assert_awaited_once()


# ============================================================================
# 7. atom_whatsapp_integration — poisoned imports disable enterprise services
# ============================================================================

class TestWhatsAppIntegrationServices:
    def test_enterprise_services_loaded_from_qualified_imports(self):
        assert whatsapp_mod.atom_enterprise_security_service is not None
        assert whatsapp_mod.atom_workflow_automation_service is not None
        assert whatsapp_mod.atom_ai_integration is not None
        assert whatsapp_mod.atom_discord_integration is not None
        assert whatsapp_mod.atom_teams_integration is not None

    def _wa(self):
        return whatsapp_mod.AtomWhatsAppIntegration({
            "access_token": "tok123",
            "phone_number_id": "ph1",
            "webhook_url": None,
        })

    def test_initialize_without_token_returns_false(self):
        wa = whatsapp_mod.AtomWhatsAppIntegration({"access_token": None})
        assert asyncio.run(wa.initialize()) is False

    def test_initialize_success(self, monkeypatch):
        wa = self._wa()
        with patch.object(wa, "_verify_api_connection", new_callable=AsyncMock), \
             patch.object(wa, "_setup_webhook", new_callable=AsyncMock), \
             patch.object(wa, "_setup_enterprise_features", new_callable=AsyncMock), \
             patch.object(wa, "_setup_security_and_compliance", new_callable=AsyncMock), \
             patch.object(wa, "_setup_automation", new_callable=AsyncMock), \
             patch.object(wa, "_setup_monitoring", new_callable=AsyncMock), \
             patch.object(wa, "_load_existing_data", new_callable=AsyncMock):
            assert asyncio.run(wa.initialize()) is True
        assert wa.is_initialized is True

    def test_send_intelligent_message_success(self):
        wa = self._wa()
        resp = Mock()
        resp.status_code = 200
        resp.json = Mock(return_value={"messages": [{"id": "wamid1"}]})
        wa.http_session = Mock()
        wa.http_session.post = AsyncMock(return_value=resp)
        with patch.object(wa, "_log_message_event", new_callable=AsyncMock) as log:
            result = asyncio.run(wa.send_intelligent_message("+123", "hello"))
        assert result["success"] is True
        assert result["message_id"] == "wamid1"
        log.assert_awaited_once()

    def test_send_intelligent_message_failure(self):
        wa = self._wa()
        resp = Mock()
        resp.status_code = 400
        resp.json = Mock(return_value={"error": {"message": "invalid"}})
        wa.http_session = Mock()
        wa.http_session.post = AsyncMock(return_value=resp)
        result = asyncio.run(wa.send_intelligent_message("+123", "hello"))
        assert result["success"] is False
        assert result["error"] == "invalid"

    def test_get_intelligent_workspaces(self):
        wa = self._wa()
        chat = SimpleNamespace(chat_id="c1", name="Chat", chat_type=whatsapp_mod.WhatsAppChatType.GROUP,
                               member_count=3, description="d", last_message=datetime(2026, 1, 1),
                               security_level="std", permissions=[], participants=["u1"],
                               admin_participants=["u1"], is_active=True)
        wa.active_chats = {"c1": chat}
        result = asyncio.run(wa.get_intelligent_workspaces("u1"))
        assert result[0]["id"] == "c1"

    def test_get_intelligent_channels_denies_non_participant(self):
        wa = self._wa()
        chat = SimpleNamespace(chat_id="c1", name="Chat", chat_type=whatsapp_mod.WhatsAppChatType.PRIVATE,
                               member_count=1, description=None, last_message=datetime(2026, 1, 1),
                               security_level="std", permissions=[], participants=["u1"],
                               admin_participants=[], is_active=True)
        wa.active_chats = {"c1": chat}
        assert asyncio.run(wa.get_intelligent_channels("c1", "u2")) == []

    def test_perform_intelligent_search(self):
        wa = self._wa()
        msg = SimpleNamespace(message_id="m1", chat_id="c1", user_id="u1",
                              message_type=whatsapp_mod.WhatsAppMessageType.TEXT,
                              content="sales pipeline update", timestamp=datetime(2026, 1, 1),
                              metadata={})
        wa.message_history = {"c1": [msg]}
        wa.ai_service = None
        result = asyncio.run(wa.perform_intelligent_search("sales", "u1"))
        assert result[0]["id"] == "m1"

    def test_get_user_conversation_history(self):
        wa = self._wa()
        msgs = [SimpleNamespace(message_id=f"m{i}", chat_id="c1", user_id="u1",
                                message_type=whatsapp_mod.WhatsAppMessageType.TEXT,
                                content=f"msg {i}", timestamp=datetime(2026, 1, i + 1), metadata={})
                for i in range(3)]
        wa.message_history = {"c1": msgs}
        result = asyncio.run(wa.get_user_conversation_history("u1", "c1", limit=2))
        assert len(result) == 2

    def test_get_service_status(self):
        wa = self._wa()
        result = asyncio.run(wa.get_service_status())
        assert result["platform"] == "whatsapp"
        assert result["status"] == "inactive"

    def test_calculate_relevance_score(self):
        wa = self._wa()
        assert wa._calculate_relevance_score("sales update", "the sales update is here") > 0

    def test_close(self):
        wa = self._wa()
        wa.http_session = Mock()
        wa.http_session.aclose = AsyncMock()
        asyncio.run(wa.close())
        wa.http_session.aclose.assert_awaited_once()

    def test_log_message_event_audits(self):
        wa = self._wa()
        wa.enterprise_security = Mock()
        wa.enterprise_security.audit_event = AsyncMock()
        asyncio.run(wa._log_message_event("message_sent", "c1", {"user_id": "u1"}))
        wa.enterprise_security.audit_event.assert_awaited_once()
