"""
Coverage push: integrations intgr_c wave (14 atom_* integration modules).

Targets the remaining uncovered lines after the bug-hunt wave. All HTTP,
IMAP, Slack SDK, Graph API and LanceDB calls are mocked — no real network.
"""

import asyncio
import builtins
import json
import os
import subprocess
import time
import sys
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from integrations import (
    atom_communication_apps_lancedb_integration as lancedb_intgr,
)
from integrations import atom_communication_live_api as comm_live
from integrations import atom_communication_memory_api as memory_api_mod
from integrations import (
    atom_communication_memory_production_api as prod_api_mod,
)
from integrations import atom_communication_memory_webhooks as webhooks_mod
from integrations import atom_communication_ingestion_pipeline as pipeline_mod
from integrations import atom_finance_live_api as finance_mod
from integrations.atom_ingestion_pipeline import (
    AtomIngestionPipeline,
    atom_ingestion_pipeline as global_pipeline,
)
from integrations import atom_projects_live_api as projects_mod
from integrations.atom_projects_memory_pipeline import ProjectsMemoryPipeline
from integrations import atom_sales_live_api as sales_mod
from integrations.atom_sales_memory_pipeline import SalesMemoryPipeline
from integrations import atom_teams_integration as teams_mod
from integrations import atom_whatsapp_integration as whatsapp_mod
from integrations.ingestion_models import RecordType
from integrations.atom_communication_ingestion_pipeline import (
    CommunicationAppType,
    CommunicationData,
    CommunicationIngestionPipeline,
    IngestionConfig,
    LanceDBMemoryManager,
    get_ingestion_pipeline,
    get_memory_manager,
)


def route_endpoint(router, path, method="POST"):
    for r in router.routes:
        if getattr(r, "path", None) == path and method in (r.methods or set()):
            return r.endpoint
    raise AssertionError(f"route {method} {path} not found")


def comm_data(**kw):
    base = dict(
        id="m1", app_type="slack", timestamp=datetime(2026, 1, 1),
        direction="inbound", sender="u1", recipient="c1", subject="s",
        content="hello world content", attachments=[], metadata={"k": "v"},
        status="active", priority="normal", tags=["x"], vector_embedding=None,
    )
    base.update(kw)
    return CommunicationData(**base)


def make_request(body: bytes):
    scope = {
        "type": "http", "method": "POST", "path": "/webhook", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "scheme": "http",
        "client": ("1.2.3.4", 1234),
    }
    req = types.SimpleNamespace()
    async def _body():
        return body
    req.body = _body
    return req


def teams_channel(**kw):
    o = SimpleNamespace(
        channel_id="c1", display_name="General", description="desc",
        channel_type="standard", workspaceName="Team One", is_archived=False,
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
# atom_ingestion_pipeline
# ============================================================================

class TestAtomIngestionPipeline:
    def test_normalize_hubspot_contact(self):
        p = AtomIngestionPipeline()
        out = p._normalize_record("hubspot", RecordType.CONTACT,
                                  {"properties": {"firstname": "A", "lastname": "B", "email": "a@b.c"}})
        assert "A B" in out["content"] and "a@b.c" in out["content"]

    def test_normalize_hubspot_campaign(self):
        p = AtomIngestionPipeline()
        out = p._normalize_record("hubspot", RecordType.CAMPAIGN, {"name": "N", "description": "D"})
        assert "Campaign: N - D" == out["content"]

    def test_normalize_salesforce_lead(self):
        p = AtomIngestionPipeline()
        out = p._normalize_record("salesforce", RecordType.LEAD,
                                  {"FirstName": "A", "LastName": "B", "Company": "C"})
        assert "Lead: A B at C" == out["content"]

    def test_normalize_salesforce_deal_and_record(self):
        p = AtomIngestionPipeline()
        out = p._normalize_record("salesforce", RecordType.DEAL, {"Name": "X", "StageName": "Y"})
        assert "Opportunity: X" in out["content"]
        out2 = p._normalize_record("salesforce", RecordType.GENERIC, {"Name": "R", "StageName": "S"})
        assert "Opportunity: R" in out2["content"]

    def test_normalize_meta_whatsapp(self):
        p = AtomIngestionPipeline()
        out = p._normalize_record("whatsapp", RecordType.COMMUNICATION, {"text": "hi"})
        assert "Message (whatsapp): hi" == out["content"]
        out2 = p._normalize_record("meta_business", RecordType.COMMUNICATION, {"content": "yo"})
        assert "Message (meta_business): yo" == out2["content"]
        out3 = p._normalize_record("meta_business", RecordType.AD_PERFORMANCE,
                                   {"spend": 10, "conversions": 2})
        assert "10 spend, 2 conv" in out3["content"]

    def test_normalize_ecommerce(self):
        p = AtomIngestionPipeline()
        out = p._normalize_record("shopify", RecordType.ORDER,
                                  {"id": "o1", "total_price": "9.99", "email": "e@x.com"})
        assert "Order o1" in out["content"]
        out2 = p._normalize_record("amazon", RecordType.INVENTORY, {"sku": "s1", "quantity": 5})
        assert "s1 -> 5" in out2["content"]

    def test_normalize_marketing(self):
        p = AtomIngestionPipeline()
        out = p._normalize_record("google_ads", RecordType.AD_PERFORMANCE, {"spend": 1, "roas": 2.5})
        assert "ROI: 2.5" in out["content"]
        out2 = p._normalize_record("tiktok_ads", RecordType.CAMPAIGN, {"name": "C", "status": "on"})
        assert "Campaign C: on" == out2["content"]

    def test_normalize_document_spreadsheet(self):
        p = AtomIngestionPipeline()
        out = p._normalize_record("drive", RecordType.DOCUMENT, {"logic_snippet": "L", "file_path": "/f"})
        assert "Business Logic Snippet: L" == out["content"]
        assert out["metadata"]["file_path"] == "/f"
        out2 = p._normalize_record("sheets", RecordType.SPREADSHEET, {"content": "C"})
        assert "Business Logic Snippet: C" == out2["content"]

    def test_normalize_fallback_content(self):
        p = AtomIngestionPipeline()
        out = p._normalize_record("custom", RecordType.GENERIC, {"foo": "bar"})
        assert out["content"] == "{'foo': 'bar'}"

    def test_ingest_record_without_manager_logs(self, caplog):
        p = AtomIngestionPipeline(memory_manager=None)
        assert asyncio.run(p.ingest_record("hubspot", "contact", {"id": "1"})) is True

    def test_ingest_record_uses_generic_manager(self):
        mgr = Mock()
        mgr.ingest_generic_record = Mock(return_value=True)
        p = AtomIngestionPipeline(memory_manager=mgr)
        assert asyncio.run(p.ingest_record("hubspot", "contact", {"id": "1"})) is True
        mgr.ingest_generic_record.assert_called_once()

    def test_ingest_record_falls_back_to_communication(self):
        mgr = Mock()
        del mgr.ingest_generic_record
        mgr.ingest_communication = Mock(return_value=True)
        p = AtomIngestionPipeline(memory_manager=mgr)
        assert asyncio.run(p.ingest_record("slack", "communication",
                                           {"id": "1", "content": "hi"})) is True
        mgr.ingest_communication.assert_called_once()

    def test_ingest_record_invalid_record_type(self):
        p = AtomIngestionPipeline(memory_manager=Mock())
        assert asyncio.run(p.ingest_record("hubspot", "nope", {})) is False

    def test_ingest_record_generic_exception(self):
        mgr = Mock()
        mgr.ingest_generic_record = Mock(side_effect=RuntimeError("boom"))
        p = AtomIngestionPipeline(memory_manager=mgr)
        assert asyncio.run(p.ingest_record("hubspot", "contact", {})) is False

    def test_global_instance_exists(self):
        assert global_pipeline is not None

    def test_module_import_fallback_when_heavy_deps_missing(self, tmp_path):
        # Import a copy of the module in an isolated package with lancedb/pyarrow
        # blocked so the ImportError fallback block executes.
        import importlib.util
        import shutil

        pkg = tmp_path / "covpkg"
        pkg.mkdir()
        pkg_mod = types.ModuleType("covpkg")
        pkg_mod.__path__ = [str(pkg)]
        sys.modules["covpkg"] = pkg_mod
        shutil.copy("integrations/atom_communication_ingestion_pipeline.py",
                    pkg / "pipeline_copy.py")
        shutil.copy("integrations/ingestion_models.py", pkg / "ingestion_models.py")

        real_import = builtins.__import__
        blocked_names = {"lancedb", "pyarrow"}

        def _blocked(name, *a, **k):
            if name.split(".")[0] in blocked_names:
                raise ImportError(f"blocked: {name}")
            return real_import(name, *a, **k)

        spec = importlib.util.spec_from_file_location(
            "covpkg.pipeline_copy", pkg / "pipeline_copy.py")
        mod = importlib.util.module_from_spec(spec)
        with patch("builtins.__import__", side_effect=_blocked):
            spec.loader.exec_module(mod)
        assert mod.lancedb is not None  # MagicMock fallback
        assert mod.LanceDBMemoryManager is not None
        assert mod.CommunicationAppType.WHATSAPP.value == "whatsapp"


# ============================================================================
# atom_communication_live_api
# ============================================================================

class TestCommunicationLiveApiCoverage:
    def test_fetch_slack_no_token(self, monkeypatch):
        monkeypatch.setattr(comm_live, "SLACK_AVAILABLE", True)
        with patch("core.user_context_manager.get_user_context_manager") as ucm:
            ucm.return_value.get_token_with_context = Mock(return_value=None)
            assert asyncio.run(comm_live.fetch_slack_recent()) == []

    def test_fetch_slack_token_but_empty_channels(self, monkeypatch):
        monkeypatch.setattr(comm_live, "SLACK_AVAILABLE", True)
        with patch("core.user_context_manager.get_user_context_manager") as ucm:
            ucm.return_value.get_token_with_context = Mock(return_value={"token": "t", "source": "bot"})
            with patch.object(comm_live, "slack_unified_service") as svc:
                svc.list_channels = AsyncMock(return_value=[])
                assert asyncio.run(comm_live.fetch_slack_recent()) == []

    def test_fetch_slack_messages_with_history(self, monkeypatch):
        monkeypatch.setattr(comm_live, "SLACK_AVAILABLE", True)
        with patch("core.user_context_manager.get_user_context_manager") as ucm:
            ucm.return_value.get_token_with_context = Mock(return_value={"token": "t", "source": "bot"})
            with patch.object(comm_live, "slack_unified_service") as svc:
                svc.list_channels = AsyncMock(return_value=[{"id": "C1", "name": "gen"}])
                svc.get_channel_history = AsyncMock(return_value={
                    "messages": [
                        {"ts": "1700000000.1", "user": "u1", "text": "hi"},
                        {"ts": "1700000000.2", "subtype": "channel_join"},
                    ]})
                msgs = asyncio.run(comm_live.fetch_slack_recent())
        assert len(msgs) == 1
        assert msgs[0]["id"] == "slack_C1_1700000000.1"

    def test_fetch_slack_exception(self, monkeypatch):
        monkeypatch.setattr(comm_live, "SLACK_AVAILABLE", True)
        with patch("core.user_context_manager.get_user_context_manager") as ucm:
            ucm.return_value.get_token_with_context = Mock(side_effect=RuntimeError("boom"))
            assert asyncio.run(comm_live.fetch_slack_recent()) == []

    def test_fetch_zoho_no_token(self, monkeypatch):
        monkeypatch.setattr(comm_live, "ZOHO_MAIL_AVAILABLE", True)
        monkeypatch.delenv("ZOHO_CRM_ACCESS_TOKEN", raising=False)
        assert asyncio.run(comm_live.fetch_zoho_mail_recent()) == []

    def test_fetch_zoho_exception(self, monkeypatch):
        monkeypatch.setattr(comm_live, "ZOHO_MAIL_AVAILABLE", True)
        monkeypatch.setenv("ZOHO_CRM_ACCESS_TOKEN", "t")
        with patch.object(comm_live, "ZohoMailService") as zcls:
            zcls.return_value.get_recent_inbox = AsyncMock(side_effect=RuntimeError("boom"))
            assert asyncio.run(comm_live.fetch_zoho_mail_recent()) == []

    def test_fetch_outlook_success(self, monkeypatch):
        monkeypatch.setattr(comm_live, "M365_AVAILABLE", True)
        monkeypatch.setenv("MICROSOFT_365_ACCESS_TOKEN", "t")
        with patch.object(comm_live, "OutlookService") as ocls:
            ocls.return_value.get_user_emails = AsyncMock(return_value=[{
                "id": "m1", "body_preview": "pre", "subject": "S",
                "sender": {"emailAddress": {"address": "a@b.c"}},
                "received_date_time": "2026-01-01T10:00:00Z", "web_link": "w", "is_read": False}])
            msgs = asyncio.run(comm_live.fetch_outlook_recent())
        assert msgs[0]["provider"] == "outlook" and msgs[0]["status"] == "unread"

    def test_fetch_outlook_exception(self, monkeypatch):
        monkeypatch.setattr(comm_live, "M365_AVAILABLE", True)
        monkeypatch.setenv("MICROSOFT_365_ACCESS_TOKEN", "t")
        with patch.object(comm_live, "OutlookService") as ocls:
            ocls.return_value.get_user_emails = AsyncMock(side_effect=RuntimeError("boom"))
            assert asyncio.run(comm_live.fetch_outlook_recent()) == []

    def test_fetch_teams_success(self, monkeypatch):
        monkeypatch.setattr(comm_live, "M365_AVAILABLE", True)
        monkeypatch.setenv("MICROSOFT_365_ACCESS_TOKEN", "t")
        with patch.object(comm_live, "TeamsService") as tcls:
            svc = tcls.return_value
            svc.get_teams = Mock(return_value=[{"id": "T1"}])
            svc.get_channels = Mock(return_value=[{"id": "C1", "displayName": "Gen"}])
            svc.get_messages = Mock(return_value=[{
                "id": "msg1", "body": {"content": "hi"},
                "from": {"user": {"displayName": "Bob"}},
                "createdDateTime": "2026-01-01T10:00:00Z"}])
            msgs = asyncio.run(comm_live.fetch_teams_recent())
        assert msgs[0]["id"] == "teams_msg1"

    def test_fetch_teams_exception(self, monkeypatch):
        monkeypatch.setattr(comm_live, "M365_AVAILABLE", True)
        monkeypatch.setenv("MICROSOFT_365_ACCESS_TOKEN", "t")
        with patch.object(comm_live, "TeamsService") as tcls:
            tcls.return_value.get_teams = Mock(side_effect=RuntimeError("boom"))
            assert asyncio.run(comm_live.fetch_teams_recent()) == []

    def test_get_live_inbox_aggregates(self, monkeypatch):
        monkeypatch.setattr(comm_live, "SLACK_AVAILABLE", True)
        with patch.object(comm_live, "fetch_slack_recent", AsyncMock(return_value=[
                {"timestamp": "2026-01-02T00:00:00", "sender": "a"}])), \
             patch.object(comm_live, "fetch_zoho_mail_recent", AsyncMock(return_value=[
                {"timestamp": "2026-01-03T00:00:00", "sender": "b"}])), \
             patch.object(comm_live, "fetch_outlook_recent", AsyncMock(return_value=[
                {"timestamp": "2026-01-01T00:00:00", "sender": "c"}])), \
             patch.object(comm_live, "fetch_teams_recent", AsyncMock(return_value=[])):
            result = asyncio.run(comm_live.get_live_inbox(limit=10))
        assert result["count"] == 3
        assert result["messages"][0]["sender"] == "b"

    def test_get_live_channels(self):
        result = asyncio.run(comm_live.get_live_channels())
        assert result["ok"] is True

    def test_recent_contacts_dedupe_and_filters(self, monkeypatch):
        monkeypatch.setattr(comm_live, "SLACK_AVAILABLE", True)
        monkeypatch.setattr(comm_live, "GMAIL_AVAILABLE", True)
        monkeypatch.setattr(comm_live, "DISCORD_AVAILABLE", False)
        monkeypatch.setattr(comm_live, "M365_AVAILABLE", False)
        monkeypatch.setattr(comm_live, "ZOHO_MAIL_AVAILABLE", False)
        with patch.object(comm_live, "fetch_slack_recent", AsyncMock(return_value=[
                {"sender": "u1"}, {"sender": "u1"}, {"sender": "Unknown"}, {"sender": "slackbot"}])):
            # fetch_discord_recent does not exist — the per-provider guard must
            # swallow the NameError and still collect slack contacts.
            result = asyncio.run(comm_live.get_recent_contacts(limit=10))
        assert len(result["contacts"]) == 1
        assert result["contacts"][0]["status"] == "online"


# ============================================================================
# atom_communication_memory_api
# ============================================================================

class TestMemoryApiCoverage:
    def _router(self):
        return memory_api_mod.AtomCommunicationMemoryAPI().router

    def test_status_endpoint(self):
        mm = Mock()
        mm.db = Mock()
        mm.db.table_names = Mock(return_value=["atom_communications"])
        mm.db_path = "path/to/db"
        table = Mock()
        table.to_pandas = Mock(return_value=Mock(
            __len__=Mock(return_value=2),
            __getitem__=Mock(return_value=Mock(value_counts=Mock(return_value=Mock(to_dict=Mock(return_value={"slack": 2})))))))
        mm.connections_table = table
        with patch.object(memory_api_mod, "memory_manager", mm), \
             patch.object(memory_api_mod, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(return_value={
                "configured_apps": ["slack"], "active_streams": ["slack"],
                "total_messages": 2})
            result = asyncio.run(route_endpoint(self._router(), "/api/atom/communication/memory/status", "GET")())
        assert result["status"] == "active"
        assert result["total_apps_configured"] == 1

    def test_status_endpoint_error(self):
        mm = Mock()
        mm.db = None
        mm.initialize = Mock(side_effect=RuntimeError("boom"))
        with patch.object(memory_api_mod, "memory_manager", mm), \
             pytest.raises(Exception) as exc:
            asyncio.run(route_endpoint(self._router(), "/api/atom/communication/memory/status", "GET")())
        assert getattr(exc.value, "status_code", None) == 500

    def test_apps_endpoint(self):
        with patch.object(memory_api_mod, "ingestion_pipeline") as pipe:
            pipe.ingestion_configs = {"slack": {"enabled": True, "real_time": True,
                                                "batch_size": 10, "ingest_attachments": True,
                                                "embed_content": True}}
            result = asyncio.run(route_endpoint(self._router(), "/api/atom/communication/memory/apps", "GET")())
        assert result["total"] == len(CommunicationAppType)
        slack = next(a for a in result["apps"] if a["id"] == "slack")
        assert slack["memory_ingestion_enabled"] is True

    def test_ingest_endpoint_failure(self):
        with patch.object(memory_api_mod, "ingestion_pipeline") as pipe, \
             patch.object(memory_api_mod, "memory_manager") as mm:
            mm.db = Mock()
            pipe.ingest_message = AsyncMock(return_value=False)
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(self._router(), "/api/atom/communication/memory/ingest")(
                    app_id="slack", message_data={"id": "1"}))
        assert getattr(exc.value, "status_code", None) == 500

    def test_ingest_endpoint_invalid_app_id(self):
        with patch.object(memory_api_mod, "ingestion_pipeline") as pipe, \
             patch.object(memory_api_mod, "memory_manager") as mm:
            mm.db = Mock()
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(self._router(), "/api/atom/communication/memory/ingest")(
                    app_id="not-an-app", message_data={}))
        assert getattr(exc.value, "status_code", None) == 404

    def test_ingest_endpoint_exception(self):
        with patch.object(memory_api_mod, "ingestion_pipeline") as pipe, \
             patch.object(memory_api_mod, "memory_manager") as mm:
            mm.db = Mock()
            pipe.ingest_message = AsyncMock(side_effect=RuntimeError("boom"))
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(self._router(), "/api/atom/communication/memory/ingest")(
                    app_id="slack", message_data={}))
        assert getattr(exc.value, "status_code", None) == 500

    def test_batch_endpoint_invalid_app_id(self):
        with patch.object(memory_api_mod, "ingestion_pipeline") as pipe, \
             patch.object(memory_api_mod, "memory_manager") as mm:
            mm.db = Mock()
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(self._router(), "/api/atom/communication/memory/ingest/batch")(
                    app_id="nope", messages=[]))
        assert getattr(exc.value, "status_code", None) == 404

    def test_search_time_based(self):
        mm = Mock()
        mm.db = Mock()
        mm.get_communications_by_timeframe = Mock(return_value=[
            {"app_type": "slack", "content": "Meeting about sales", "tags": ["sales"]},
            {"app_type": "teams", "content": "other", "tags": []}])
        with patch.object(memory_api_mod, "memory_manager", mm):
            result = asyncio.run(route_endpoint(self._router(), "/api/atom/communication/memory/search", "GET")(
                query="sales", app_id="slack", limit=10,
                time_start="2026-01-01", time_end="2026-01-02", tag="sales"))
        assert result["total_results"] == 1

    def test_search_regular_and_value_error(self):
        mm = Mock()
        mm.db = Mock()
        mm.search_communications = Mock(return_value=[])
        with patch.object(memory_api_mod, "memory_manager", mm):
            result = asyncio.run(route_endpoint(self._router(), "/api/atom/communication/memory/search", "GET")(
                query="q", app_id=None, limit=10, time_start=None, time_end=None, tag=None))
        assert result["total_results"] == 0

    def test_communications_endpoint_time_and_regular(self):
        mm = Mock()
        mm.db = Mock()
        mm.get_communications_by_timeframe = Mock(return_value=[
            {"app_type": "slack"}, {"app_type": "teams"}])
        mm.get_communications_by_app = Mock(return_value=[{"app_type": "slack"}])
        with patch.object(memory_api_mod, "memory_manager", mm):
            result = asyncio.run(route_endpoint(self._router(), "/api/atom/communication/memory/communications/{app_id}", "GET")(
                app_id="slack", limit=50, time_start="2026-01-01", time_end="2026-01-02"))
            assert result["total_results"] == 1
            result2 = asyncio.run(route_endpoint(self._router(), "/api/atom/communication/memory/communications/{app_id}", "GET")(
                app_id="slack", limit=50, time_start=None, time_end=None))
            assert result2["total_results"] == 1
            mm.get_communications_by_app.assert_called_with("slack", 50)

    def test_communications_endpoint_invalid(self):
        mm = Mock()
        mm.db = Mock()
        with patch.object(memory_api_mod, "memory_manager", mm), pytest.raises(Exception) as exc:
            asyncio.run(route_endpoint(self._router(), "/api/atom/communication/memory/communications/{app_id}", "GET")(
                app_id="nope", limit=50, time_start=None, time_end=None))
        assert getattr(exc.value, "status_code", None) == 404

    def test_analytics_endpoint_full(self):
        mm = Mock()
        mm.db = Mock()
        table = Mock()
        df = Mock()
        records = [
            {"app_type": "slack", "direction": "inbound", "priority": "high",
             "status": "active", "timestamp": "2026-01-01T10:00:00",
             "metadata": json.dumps({"thread_id": "t1"}), "subject": "s1", "id": "1"},
            {"app_type": "slack", "direction": "outbound", "priority": "normal",
             "status": "active", "timestamp": "2026-01-01T10:05:00",
             "metadata": json.dumps({"thread_id": "t1"}), "subject": "s1", "id": "2"},
        ]
        df.to_dict = Mock(return_value=records)
        table.to_pandas = Mock(return_value=df)
        mm.connections_table = table
        with patch.object(memory_api_mod, "memory_manager", mm), \
             patch.object(memory_api_mod, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(return_value={"configured_apps": ["slack"]})
            result = asyncio.run(route_endpoint(self._router(), "/api/atom/communication/memory/analytics", "GET")(
                time_start="2026-01-01", time_end="2026-01-02"))
        assert result["analytics"]["summary"]["total_messages"] == 2
        assert result["analytics"]["performance"]["total_responses"] == 1

    def test_analytics_endpoint_bad_timestamp_skips_record(self):
        mm = Mock()
        mm.db = Mock()
        table = Mock()
        df = Mock()
        df.to_dict = Mock(return_value=[
            {"app_type": "slack", "direction": "inbound", "priority": "high",
             "status": "active", "timestamp": "not-a-date", "metadata": "{}", "id": "1"},
        ])
        table.to_pandas = Mock(return_value=df)
        mm.connections_table = table
        with patch.object(memory_api_mod, "memory_manager", mm), \
             patch.object(memory_api_mod, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(return_value={"configured_apps": []})
            result = asyncio.run(route_endpoint(self._router(), "/api/atom/communication/memory/analytics", "GET")(
                time_start=None, time_end=None))
        assert result["analytics"]["timeline_data"] == {}

    def test_configure_endpoint(self):
        config = pipeline_mod.IngestionConfig(
            app_type=CommunicationAppType.SLACK, enabled=True, real_time=True,
            batch_size=10, ingest_attachments=True, embed_content=True, retention_days=30)
        with patch.object(memory_api_mod, "ingestion_pipeline") as pipe:
            result = asyncio.run(route_endpoint(self._router(), "/api/atom/communication/memory/configure")(
                app_id="slack", config=config))
        assert result["success"] is True
        pipe.configure_app.assert_called_once()

    def test_configure_endpoint_invalid(self):
        with pytest.raises(Exception) as exc:
            asyncio.run(route_endpoint(self._router(), "/api/atom/communication/memory/configure")(
                app_id="nope", config=None))
        assert getattr(exc.value, "status_code", None) == 404


# ============================================================================
# atom_communication_memory_production_api
# ============================================================================

class TestProductionApiCoverage:
    def _api(self):
        return prod_api_mod.AtomCommunicationMemoryProductionAPI()

    def test_health_check(self):
        mm = Mock()
        mm.db = Mock()
        with patch.object(prod_api_mod, "memory_manager", mm), \
             patch.object(prod_api_mod, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(return_value={"configured_apps": ["slack"]})
            result = asyncio.run(route_endpoint(self._api().router, "/api/atom/communication/memory/health", "GET")())
        assert result["status"] == "healthy"

    def test_health_check_unhealthy_and_error(self):
        mm = Mock()
        mm.db = None
        with patch.object(prod_api_mod, "memory_manager", mm), \
             patch.object(prod_api_mod, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(side_effect=RuntimeError("boom"))
            result = asyncio.run(route_endpoint(self._api().router, "/api/atom/communication/memory/health", "GET")())
        assert result["status"] == "unhealthy"

    def test_status_endpoint_with_table(self):
        mm = Mock()
        mm.db = Mock()
        mm.db.table_names = Mock(return_value=["atom_communications"])
        mm.db_path = "db"
        table = Mock()
        df = Mock()
        df.empty = False
        df.__len__ = Mock(return_value=3)
        df.__getitem__ = Mock(return_value=Mock(
            value_counts=Mock(return_value=Mock(to_dict=Mock(return_value={"slack": 3})))))
        df.min = Mock(return_value="2026-01-01")
        df.max = Mock(return_value="2026-01-02")
        table.to_pandas = Mock(return_value=df)
        mm.connections_table = table
        with patch.object(prod_api_mod, "memory_manager", mm), \
             patch.object(prod_api_mod, "ingestion_pipeline") as pipe, \
             patch.object(prod_api_mod, "check_uptime", return_value={
                 "uptime_formatted": "1d", "uptime_percentage": 99.5}):
            pipe.get_ingestion_stats = Mock(return_value={"configured_apps": ["slack"]})
            result = asyncio.run(route_endpoint(self._api().router, "/api/atom/communication/memory/status", "GET")())
        assert result["database"]["statistics"]["total_records"] == 3

    def test_status_endpoint_error(self):
        mm = Mock()
        mm.db = None
        mm.connections_table = Mock()
        mm.connections_table.to_pandas = Mock(side_effect=RuntimeError("boom"))
        with patch.object(prod_api_mod, "memory_manager", mm), pytest.raises(Exception) as exc:
            asyncio.run(route_endpoint(self._api().router, "/api/atom/communication/memory/status", "GET")())
        assert getattr(exc.value, "status_code", None) == 500

    def test_ingest_single_value_error_and_failure(self):
        with patch.object(prod_api_mod, "ingestion_pipeline") as pipe, \
             patch.object(prod_api_mod, "memory_manager") as mm:
            mm.db = Mock()
            pipe.ingest_message = AsyncMock(return_value=False)
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(self._api().router, "/api/atom/communication/memory/ingest/single")(
                    app_id="slack", message_data={}, token={"sub": "u"}))
        assert getattr(exc.value, "status_code", None) == 500
        with pytest.raises(Exception) as exc2:
            asyncio.run(route_endpoint(self._api().router, "/api/atom/communication/memory/ingest/single")(
                app_id="nope", message_data={}, token={"sub": "u"}))
        assert getattr(exc2.value, "status_code", None) == 404

    def test_batch_empty_messages(self):
        with patch.object(prod_api_mod, "ingestion_pipeline") as pipe, \
             patch.object(prod_api_mod, "memory_manager") as mm:
            mm.db = Mock()
            pipe.ingest_message = AsyncMock(return_value=True)
            result = asyncio.run(route_endpoint(self._api().router, "/api/atom/communication/memory/ingest/batch")(
                app_id="slack", messages=[], token={"sub": "u"}))
        assert result["batch_id"] is None
        assert result["success_count"] == 0

    def test_search_time_based_no_metadata(self):
        mm = Mock()
        mm.db = Mock()
        mm.get_communications_by_timeframe = Mock(return_value=[
            {"app_type": "slack", "content": "alpha", "metadata": {"x": 1}, "vector": [1], "search_vector": [1]}])
        with patch.object(prod_api_mod, "memory_manager", mm):
            result = asyncio.run(route_endpoint(self._api().router, "/api/atom/communication/memory/search/production", "GET")(
                query="alpha", app_id="slack", limit=10, time_start="2026-01-01",
                time_end="2026-01-02", include_metadata=False, token={"sub": "u"}))
        assert result["results"][0].get("metadata") is None

    def test_analytics_with_filters_and_detailed_metrics(self, tmp_path):
        mm = Mock()
        mm.db = Mock()
        table = Mock()
        df = Mock()
        records = [
            {"app_type": "slack", "direction": "inbound", "priority": "high",
             "status": "active", "timestamp": "2026-01-01T10:00:00", "content": "a" * 50,
             "attachments": json.dumps([{"id": 1}])},
            {"app_type": "teams", "direction": "outbound", "priority": "normal",
             "status": "active", "timestamp": "2026-01-02T10:00:00", "content": "b" * 30,
             "attachments": "[]"},
        ]
        df.to_dict = Mock(return_value=records)
        table.to_pandas = Mock(return_value=df)
        mm.connections_table = table
        mm.db_path = str(tmp_path)
        (tmp_path / "x.bin").write_bytes(b"12345")
        with patch.object(prod_api_mod, "memory_manager", mm), \
             patch.object(prod_api_mod, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(return_value={"configured_apps": []})
            result = asyncio.run(route_endpoint(self._api().router, "/api/atom/communication/memory/analytics/production", "GET")(
                time_start="2026-01-01", time_end="2026-01-03", app_id=None,
                include_detailed_metrics=True, token={"sub": "u"}))
        assert result["analytics"]["detailed_metrics"]["total_messages"] == 2
        assert result["analytics"]["detailed_metrics"]["total_attachments"] == 1

    def test_analytics_db_path_missing_fallback(self):
        mm = Mock()
        mm.db = Mock()
        mm.connections_table = None
        mm.db_path = "/nonexistent/db/path"
        with patch.object(prod_api_mod, "memory_manager", mm), \
             patch.object(prod_api_mod, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(return_value={"configured_apps": []})
            result = asyncio.run(route_endpoint(self._api().router, "/api/atom/communication/memory/analytics/production", "GET")(
                time_start=None, time_end=None, app_id="slack",
                include_detailed_metrics=True, token={"sub": "u"}))
        assert result["analytics"]["summary"]["app_filter"] == "slack"


# ============================================================================
# atom_communication_memory_webhooks — remaining branches
# ============================================================================

class TestWebhooksCoverage:
    def _wh(self):
        return webhooks_mod.AtomCommunicationMemoryWebhooks()

    def test_health_endpoint(self):
        wh = self._wh()
        result = asyncio.run(route_endpoint(wh.router, "/api/webhooks/communication/health", "GET")())
        assert result["status"] == "healthy"

    def test_verify_webhook_signature_no_secret(self, monkeypatch):
        wh = self._wh()
        assert wh.verify_webhook_signature("gmail", None, "sig", b"body") is False

    def test_verify_webhook_signature_matches(self, monkeypatch):
        monkeypatch.setenv("ATOM_SLACK_WEBHOOK_SECRET", "s")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        import hashlib, hmac as hmac_mod
        sig = hmac_mod.new(b"s", b"body", hashlib.sha256).hexdigest()
        assert wh.verify_webhook_signature("slack", None, sig, b"body") is True

    def test_verify_webhook_signature_exception(self, monkeypatch):
        monkeypatch.setenv("ATOM_SLACK_WEBHOOK_SECRET", "s")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        with patch.object(webhooks_mod.hmac, "new", side_effect=RuntimeError("boom")):
            assert wh.verify_webhook_signature("slack", None, "sig", b"body") is False

    def test_whatsapp_endpoint_invalid_json_500(self, monkeypatch):
        monkeypatch.setenv("ATOM_WHATSAPP_WEBHOOK_SECRET", "w")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/whatsapp")
        body = b"not-json{{"
        sig = "sha256=" + __import__("hashlib").sha256(b"w".__add__(b"") and b"" or b"").hexdigest()
        # compute real sig
        import hashlib, hmac
        sig = "sha256=" + hmac.new(b"w", body, hashlib.sha256).hexdigest()
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(body), background_tasks=Mock(),
                                 x_hub_signature_256=sig, token={}))
        assert getattr(exc.value, "status_code", None) == 500

    def test_slack_endpoint_bad_timestamp_format(self, monkeypatch):
        monkeypatch.setenv("ATOM_SLACK_WEBHOOK_SECRET", "s")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/slack")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                 x_slack_signature="v0=abc", x_slack_request_timestamp="notanint",
                                 token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_telegram_endpoint_valid_secret(self, monkeypatch):
        monkeypatch.setenv("ATOM_TELEGRAM_WEBHOOK_SECRET", "tg")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/telegram")
        body = json.dumps({"message": {"message_id": 1}}).encode()
        import hashlib, hmac
        sig = hmac.new(b"tg", body, hashlib.sha256).hexdigest()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            result = asyncio.run(endpoint(request=make_request(body), background_tasks=Mock(),
                                          x_telegram_bot_api_secret_token=sig, token={}))
        assert result["status"] == "received"

    def test_discord_endpoint_valid_signature(self, monkeypatch):
        monkeypatch.setenv("ATOM_DISCORD_WEBHOOK_SECRET", "d")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/discord")
        body = json.dumps({"message": {"id": "1"}}).encode()
        import hashlib, hmac
        sig = hmac.new(b"d", body, hashlib.sha256).hexdigest()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            result = asyncio.run(endpoint(request=make_request(body), background_tasks=Mock(),
                                          x_signature_ed25519=sig, x_signature_timestamp="123", token={}))
        assert result["status"] == "received"

    def test_gmail_endpoint_valid_secret(self, monkeypatch):
        monkeypatch.setenv("ATOM_GMAIL_WEBHOOK_SECRET", "g")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/gmail")
        body = json.dumps({"message": {"id": "1"}}).encode()
        import hashlib, hmac
        sig = hmac.new(b"g", body, hashlib.sha256).hexdigest()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            result = asyncio.run(endpoint(request=make_request(body), background_tasks=Mock(),
                                          x_atom_webhook_secret=sig, token={}))
        assert result["status"] == "received"

    def test_outlook_endpoint_valid_secret(self, monkeypatch):
        monkeypatch.setenv("ATOM_OUTLOOK_WEBHOOK_SECRET", "o")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/outlook")
        body = json.dumps({"value": [{"id": "1"}]}).encode()
        import hashlib, hmac
        sig = hmac.new(b"o", body, hashlib.sha256).hexdigest()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            result = asyncio.run(endpoint(request=make_request(body), background_tasks=Mock(),
                                          x_atom_webhook_secret=sig, token={}))
        assert result["status"] == "received"

    def test_processors_with_empty_payloads(self):
        wh = self._wh()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            asyncio.run(wh._process_whatsapp_webhook({"entry": []}))
            asyncio.run(wh._process_slack_webhook({"event": {"type": "reaction_added"}}))
            asyncio.run(wh._process_discord_webhook({}))
            asyncio.run(wh._process_telegram_webhook({}))
            asyncio.run(wh._process_gmail_webhook({}))
            asyncio.run(wh._process_outlook_webhook({"value": []}))
            pipe.ingest_message.assert_not_awaited()

    def test_processors_exception_path(self):
        wh = self._wh()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(side_effect=RuntimeError("boom"))
            asyncio.run(wh._process_slack_webhook({"event": {"type": "message", "ts": "1"}}))


# ============================================================================
# atom_communication_apps_lancedb_integration — remaining branches
# ============================================================================

class TestLanceDBIntegrationCoverage:
    def _router(self):
        return lancedb_intgr.CommunicationAppIngestionIntegration().router

    def test_status_endpoint(self):
        mm = Mock()
        mm.db = Mock()
        mm.db_path = "db"
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(return_value={
                "configured_apps": ["slack"], "active_streams": [], "total_messages": 0, "app_stats": {}})
            result = asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/status", "GET")())
        assert result["status"] == "active"

    def test_status_endpoint_error(self):
        mm = Mock()
        mm.db = None
        mm.initialize = Mock(side_effect=RuntimeError("boom"))
        with patch.object(lancedb_intgr, "memory_manager", mm), pytest.raises(Exception) as exc:
            asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/status", "GET")())
        assert getattr(exc.value, "status_code", None) == 500

    def test_apps_endpoint(self):
        result = asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/apps", "GET")())
        assert result["total"] == len(CommunicationAppType)

    def test_app_config_endpoints(self):
        with patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.ingestion_configs = {"slack": {"enabled": True}}
            result = asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/apps/{app_id}", "GET")(
                app_id="slack"))
            assert result["app_id"] == "slack"
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/apps/{app_id}", "GET")(
                    app_id="teams"))
            assert getattr(exc.value, "status_code", None) == 404
            with pytest.raises(Exception) as exc2:
                asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/apps/{app_id}", "GET")(
                    app_id="nope"))
            assert getattr(exc2.value, "status_code", None) == 404

    def test_ingest_failure_and_invalid(self):
        with patch.object(lancedb_intgr, "ingestion_pipeline") as pipe, \
             patch.object(lancedb_intgr, "memory_manager") as mm:
            mm.db = Mock()
            pipe.ingest_message = AsyncMock(return_value=False)
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/ingest/{app_id}")(
                    app_id="slack", message_data={}))
            assert getattr(exc.value, "status_code", None) == 500
            with pytest.raises(Exception) as exc2:
                asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/ingest/{app_id}")(
                    app_id="nope", message_data={}))
            assert getattr(exc2.value, "status_code", None) == 404

    def test_batch_invalid_app(self):
        with patch.object(lancedb_intgr, "ingestion_pipeline") as pipe, \
             patch.object(lancedb_intgr, "memory_manager") as mm:
            mm.db = Mock()
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/ingest/{app_id}/batch")(
                    app_id="nope", messages=[]))
            assert getattr(exc.value, "status_code", None) == 404

    def test_stream_start_paths(self):
        with patch.object(lancedb_intgr, "ingestion_pipeline") as pipe, \
             patch.object(lancedb_intgr, "memory_manager") as mm:
            mm.db = Mock()
            pipe.start_real_time_stream = Mock(return_value=True)
            result = asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/stream/start/{app_id}")(
                app_id="slack"))
            assert result["success"] is True
            pipe.start_real_time_stream = Mock(return_value=False)
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/stream/start/{app_id}")(
                    app_id="slack"))
            assert getattr(exc.value, "status_code", None) == 500
            with pytest.raises(Exception) as exc2:
                asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/stream/start/{app_id}")(
                    app_id="nope"))
            assert getattr(exc2.value, "status_code", None) == 404

    def test_search_endpoint_error(self):
        mm = Mock()
        mm.db = Mock()
        mm.search_communications = Mock(side_effect=RuntimeError("boom"))
        with patch.object(lancedb_intgr, "memory_manager", mm), pytest.raises(Exception) as exc:
            asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/search", "GET")(
                query="q"))
        assert getattr(exc.value, "status_code", None) == 500

    def test_timeline_endpoint_filters_and_errors(self):
        mm = Mock()
        mm.db = Mock()
        mm.get_communications_by_timeframe = Mock(return_value=[
            {"app_type": "slack"}, {"app_type": "teams"}])
        with patch.object(lancedb_intgr, "memory_manager", mm):
            result = asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/communications/timeline", "GET")(
                start_date="2026-01-01", end_date="2026-01-02", app_id="slack"))
            assert result["total_results"] == 1
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/communications/timeline", "GET")(
                    start_date="notadate", end_date="2026-01-02", app_id=None))
            assert getattr(exc.value, "status_code", None) == 400

    def test_communications_endpoint(self):
        mm = Mock()
        mm.db = Mock()
        mm.get_communications_by_app = Mock(return_value=[{"app_type": "slack"}])
        with patch.object(lancedb_intgr, "memory_manager", mm):
            result = asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/communications/{app_id}", "GET")(
                app_id="slack", limit=100))
            assert result["total_results"] == 1

    def test_memory_stats_endpoint(self):
        mm = Mock()
        mm.db = Mock()
        mm.db.table_names = Mock(return_value=["atom_communications"])
        mm.db_path = "db"
        table = Mock()
        df = Mock()
        df.__len__ = Mock(return_value=2)
        df.__getitem__ = Mock(return_value=Mock(
            value_counts=Mock(return_value=Mock(to_dict=Mock(return_value={"slack": 2})))))
        table.to_pandas = Mock(return_value=df)
        mm.connections_table = table
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(return_value={"configured_apps": ["slack"]})
            result = asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/memory/stats", "GET")())
        assert result["database_stats"]["total_communications"] == 2

    def test_memory_stats_error(self):
        mm = Mock()
        mm.db = None
        mm.initialize = Mock(side_effect=RuntimeError("boom"))
        with patch.object(lancedb_intgr, "memory_manager", mm), pytest.raises(Exception) as exc:
            asyncio.run(route_endpoint(self._router(), "/api/memory/ingestion/memory/stats", "GET")())
        assert getattr(exc.value, "status_code", None) == 500


# ============================================================================
# finance / projects / sales live APIs — remaining branches
# ============================================================================

class TestFinanceCoverage:
    def test_map_stripe_payment(self):
        tx = finance_mod.map_stripe_payment({"id": "p1", "description": "d", "amount": 1234,
                                             "currency": "usd", "created": 1700000000, "status": "succeeded"})
        assert tx.amount == 12.34
        assert "stripe" in tx.url

    def test_map_xero_invoice_missing_date(self):
        tx = finance_mod.map_xero_invoice({"InvoiceID": "x", "InvoiceNumber": "1", "Total": 5.0})
        assert tx.date

    def test_map_dynamics_invoice(self):
        tx = finance_mod.map_dynamics_invoice({})
        assert tx.platform == "dynamics" and tx.status == "active"
        tx2 = finance_mod.map_dynamics_invoice({"resourceVisualization": {"title": "T"},
                                                "resourceReference": {"webUrl": "w"}})
        assert tx2.description == "T" and tx2.url == "w"

    def test_endpoint_stripe_and_xero_paths(self, monkeypatch):
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk")
        monkeypatch.setenv("XERO_ACCESS_TOKEN", "xero")
        monkeypatch.delenv("ZOHO_CRM_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("MICROSOFT_365_ACCESS_TOKEN", raising=False)
        sdk = Mock()
        sdk.Charge.list = Mock(return_value={"data": [{"id": "p", "amount": 1000,
                                                       "currency": "usd", "created": 1700000000,
                                                       "status": "succeeded"}]})
        with patch.object(finance_mod, "stripe_sdk", sdk):
            with patch("integrations.xero_service.XeroService") as xcls:
                xcls.return_value.get_invoices = AsyncMock(return_value=[
                    {"InvoiceID": "x", "InvoiceNumber": "1", "Total": 50.0,
                     "CurrencyCode": "USD", "DateString": "2026-01-01", "Status": "PAID"}])
                result = asyncio.run(finance_mod.get_live_financial_overview(limit=10))
        assert result.providers["stripe"] is True
        assert result.providers["xero"] is True
        assert result.stats.total_revenue == 60.0

    def test_endpoint_stripe_failure_continues(self, monkeypatch):
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk")
        sdk = Mock()
        sdk.Charge.list = Mock(side_effect=RuntimeError("stripe down"))
        with patch.object(finance_mod, "stripe_sdk", sdk):
            result = asyncio.run(finance_mod.get_live_financial_overview(limit=10))
        assert result.providers["stripe"] is False

    def test_endpoint_stripe_httpx_fallback(self, monkeypatch):
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk")
        class FakeResp:
            status_code = 200
            def json(self):
                return {"data": [{"id": "p", "amount": 1000, "currency": "usd",
                                  "created": 1700000000, "status": "succeeded"}]}
        fake_client = AsyncMock()
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)
        fake_client.get = AsyncMock(return_value=FakeResp())
        with patch.object(finance_mod, "stripe_sdk", None), \
             patch("httpx.AsyncClient", return_value=fake_client):
            result = asyncio.run(finance_mod.get_live_financial_overview(limit=10))
        assert result.providers["stripe"] is True

    def test_endpoint_dynamics_path(self, monkeypatch):
        monkeypatch.setenv("MICROSOFT_365_ACCESS_TOKEN", "ms")
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        monkeypatch.delenv("XERO_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("ZOHO_CRM_ACCESS_TOKEN", raising=False)
        with patch.object(finance_mod, "microsoft365_service") as msvc:
            msvc.get_dynamics_invoices = AsyncMock(return_value={
                "status": "success", "data": {"value": [{"id": "d1", "resourceVisualization": {"title": "T"}}]}})
            result = asyncio.run(finance_mod.get_live_financial_overview(limit=10))
        assert result.providers["dynamics"] is True

    def test_endpoint_zoho_error_path(self, monkeypatch):
        monkeypatch.setenv("ZOHO_CRM_ACCESS_TOKEN", "z")
        monkeypatch.setenv("ZOHO_BOOKS_ORG_ID", "org")
        with patch.object(finance_mod, "ZohoBooksService") as zcls:
            zcls.return_value._get_headers = Mock(side_effect=RuntimeError("boom"))
            result = asyncio.run(finance_mod.get_live_financial_overview(limit=10))
        assert result.providers["zoho"] is False


class TestProjectsCoverage:
    def test_asana_no_token(self, monkeypatch):
        monkeypatch.delenv("ASANA_ACCESS_TOKEN", raising=False)
        with patch.object(projects_mod, "get_jira_service", return_value=None):
            result = asyncio.run(projects_mod.get_live_project_board(limit=10))
        assert result.providers["asana"] is False

    def test_jira_paths(self, monkeypatch):
        monkeypatch.delenv("ASANA_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("ZOHO_CRM_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("MICROSOFT_365_ACCESS_TOKEN", raising=False)
        jira = Mock()
        jira.test_connection = Mock(return_value={"authenticated": False})
        with patch.object(projects_mod, "get_jira_service", return_value=jira):
            result = asyncio.run(projects_mod.get_live_project_board(limit=10))
        assert result.providers["jira"] is False
        jira.test_connection = Mock(return_value={"authenticated": True})
        jira.base_url = "https://x.atlassian.net"
        jira.search_issues = Mock(return_value={"issues": [
            {"key": "K-1", "fields": {"summary": "S", "status": {"name": "Open"},
                                      "priority": {"name": "High"}, "assignee": {"displayName": "A"},
                                      "duedate": "2026-01-01", "project": {"name": "P"}}}]})
        with patch.object(projects_mod, "get_jira_service", return_value=jira):
            result2 = asyncio.run(projects_mod.get_live_project_board(limit=10))
        assert result2.providers["jira"] is True
        assert result2.tasks[0].id == "K-1"

    def test_jira_exception(self, monkeypatch):
        monkeypatch.delenv("ASANA_ACCESS_TOKEN", raising=False)
        with patch.object(projects_mod, "get_jira_service", side_effect=RuntimeError("boom")):
            result = asyncio.run(projects_mod.get_live_project_board(limit=10))
        assert result.providers["jira"] is False

    def test_zoho_path(self, monkeypatch):
        monkeypatch.delenv("ASANA_ACCESS_TOKEN", raising=False)
        monkeypatch.setenv("ZOHO_CRM_ACCESS_TOKEN", "z")
        monkeypatch.setenv("ZOHO_PROJECTS_PORTAL_ID", "p")
        monkeypatch.delenv("MICROSOFT_365_ACCESS_TOKEN", raising=False)
        with patch.object(projects_mod, "get_jira_service", return_value=None), \
             patch.object(projects_mod, "ZohoProjectsService") as zcls:
            zcls.return_value.get_all_active_tasks = AsyncMock(return_value=[
                {"id_string": "t1", "name": "T", "status": {"type": "completed"},
                 "priority": "high", "created_person": "u", "end_date": "2026-01-01", "project_name": "P"}])
            result = asyncio.run(projects_mod.get_live_project_board(limit=10))
        assert result.providers["zoho"] is True
        assert result.tasks[0].status == "completed"

    def test_planner_path(self, monkeypatch):
        monkeypatch.delenv("ASANA_ACCESS_TOKEN", raising=False)
        monkeypatch.setenv("MICROSOFT_365_ACCESS_TOKEN", "ms")
        with patch.object(projects_mod, "get_jira_service", return_value=None), \
             patch.object(projects_mod, "microsoft365_service") as msvc:
            msvc.get_planner_tasks = AsyncMock(return_value={
                "status": "success", "data": {"value": [{"id": "p1", "title": "P",
                                                        "completedDateTime": "2026-01-01",
                                                        "dueDateTime": "2026-01-02"}]}})
            result = asyncio.run(projects_mod.get_live_project_board(limit=10))
        assert result.providers["planner"] is True
        assert result.tasks[0].status == "completed"


class TestSalesCoverage:
    def test_map_salesforce_opportunity(self):
        d = sales_mod.map_salesforce_opportunity(
            {"Id": "1", "Name": "N", "Amount": "100", "StageName": "Closed Won",
             "CloseDate": "2026-01-01", "Probability": "90"}, "https://x")
        assert d.url == "https://x/1" and d.probability == 90.0
        d2 = sales_mod.map_salesforce_opportunity({"Id": "2", "Name": "N2"})
        assert d2.status == "unknown"

    def test_map_zoho_deal(self):
        d = sales_mod.map_zoho_deal({"id": "z1", "Deal_Name": "Z", "Amount": "10",
                                     "Stage": "Won", "Account_Name": {"name": "A"},
                                     "Closing_Date": "2026-01-01", "Owner": {"name": "O"}})
        assert d.company == "A" and d.owner == "O"
        d2 = sales_mod.map_zoho_deal({"id": "z2"})
        assert d2.status == "unknown"

    def test_map_dynamics_deal(self):
        d = sales_mod.map_dynamics_deal({"resourceVisualization": {"title": "T"},
                                         "resourceReference": {"webUrl": "w"}})
        assert d.deal_name == "T" and d.url == "w"

    def test_hubspot_failure(self, monkeypatch):
        monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "t")
        with patch.object(sales_mod, "get_hubspot_service") as hsvc:
            hsvc.return_value.get_deals = AsyncMock(side_effect=RuntimeError("boom"))
            result = asyncio.run(sales_mod.get_live_pipeline(limit=10))
        assert result.providers["hubspot"] is False

    def test_salesforce_via_token_storage(self, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("SALESFORCE_ACCESS_TOKEN", raising=False)
        with patch.object(sales_mod, "token_storage") as ts:
            ts.get_token = Mock(return_value={"access_token": "t", "instance_url": "https://x"})
            with patch.object(sales_mod, "create_client_with_token") as ctor:
                sf = Mock()
                sf.query_all = Mock(return_value={"records": [
                    {"Id": "1", "Name": "N", "Amount": "5", "StageName": "Open"}]})
                ctor.return_value = sf
                result = asyncio.run(sales_mod.get_live_pipeline(limit=10))
        assert result.providers["salesforce"] is True

    def test_zoho_and_dynamics_paths(self, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        monkeypatch.setenv("ZOHO_CRM_ACCESS_TOKEN", "z")
        monkeypatch.setenv("MICROSOFT_365_ACCESS_TOKEN", "ms")
        with patch.object(sales_mod, "get_hubspot_service") as hsvc, \
             patch.object(sales_mod, "ZohoCRMService") as zcls, \
             patch.object(sales_mod, "microsoft365_service") as msvc:
            hsvc.return_value.get_deals = AsyncMock(return_value=[])
            zcls.return_value.get_deals = AsyncMock(return_value=[
                {"id": "z1", "Deal_Name": "Z", "Amount": "10", "Stage": "Won"}])
            msvc.get_dynamics_deals = AsyncMock(return_value={
                "status": "success", "data": {"value": [{"id": "d1"}]}})
            result = asyncio.run(sales_mod.get_live_pipeline(limit=10))
        assert result.providers["zoho"] is True
        assert result.providers["dynamics"] is True
        assert result.stats.win_rate == 50.0

    def test_salesforce_create_client_none(self, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        with patch.object(sales_mod, "token_storage") as ts:
            ts.get_token = Mock(return_value=None)
            with patch.object(sales_mod, "create_client_with_token", return_value=None):
                result = asyncio.run(sales_mod.get_live_pipeline(limit=10))
        assert result.providers["salesforce"] is False


# ============================================================================
# projects / sales memory pipelines
# ============================================================================

class TestProjectsMemoryPipeline:
    def test_run_pipeline_broadcasts(self):
        pipe = ProjectsMemoryPipeline(workspace_id="ws1")
        pipe.memory_manager = Mock()
        with patch.object(pipe, "_ingest_jira", new_callable=AsyncMock) as ij, \
             patch("integrations.atom_projects_memory_pipeline.manager") as mgr:
            mgr.broadcast_event = AsyncMock()
            asyncio.run(pipe.run_pipeline())
            ij.assert_awaited_once()
            mgr.broadcast_event.assert_awaited_once()

    def test_run_pipeline_broadcast_failure(self):
        pipe = ProjectsMemoryPipeline(workspace_id="ws1")
        pipe.memory_manager = Mock()
        with patch.object(pipe, "_ingest_jira", new_callable=AsyncMock), \
             patch("integrations.atom_projects_memory_pipeline.manager") as mgr:
            mgr.broadcast_event = AsyncMock(side_effect=RuntimeError("ws down"))
            asyncio.run(pipe.run_pipeline())

    def test_ingest_jira_unauthenticated(self):
        pipe = ProjectsMemoryPipeline(workspace_id="ws1")
        pipe.memory_manager = Mock()
        with patch("integrations.atom_projects_memory_pipeline.get_jira_service") as gj:
            jira = Mock()
            jira.test_connection = Mock(return_value={"authenticated": False})
            gj.return_value = jira
            asyncio.run(pipe._ingest_jira())
        jira.search_issues.assert_not_called()

    def test_ingest_jira_success(self):
        pipe = ProjectsMemoryPipeline(workspace_id="ws1")
        pipe.memory_manager = Mock()
        with patch("integrations.atom_projects_memory_pipeline.get_jira_service") as gj:
            jira = Mock()
            jira.test_connection = Mock(return_value={"authenticated": True})
            jira.search_issues = Mock(return_value={"issues": [{
                "key": "K-1", "id": "1", "fields": {
                    "summary": "S", "description": "D", "status": {"name": "Open"},
                    "creator": {"displayName": "A"}, "priority": {"name": "High"}}}]})
            gj.return_value = jira
            pipe.memory_manager.ingest_communication = Mock(return_value=True)
            asyncio.run(pipe._ingest_jira())
        pipe.memory_manager.ingest_communication.assert_called_once()

    def test_ingest_jira_exception(self):
        pipe = ProjectsMemoryPipeline(workspace_id="ws1")
        pipe.memory_manager = Mock()
        with patch("integrations.atom_projects_memory_pipeline.get_jira_service",
                   side_effect=RuntimeError("boom")):
            asyncio.run(pipe._ingest_jira())

    def test_ingest_task_error(self):
        pipe = ProjectsMemoryPipeline(workspace_id="ws1")
        pipe.memory_manager = Mock()
        pipe.memory_manager.ingest_communication = Mock(side_effect=RuntimeError("boom"))
        assert pipe._ingest_task("jira", {"key": "K", "fields": {}}) is False


class TestSalesMemoryPipeline:
    def test_run_pipeline_no_token(self, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        pipe = SalesMemoryPipeline(workspace_id="ws1")
        pipe.memory_manager = Mock()
        with patch("integrations.atom_sales_memory_pipeline.manager") as mgr:
            mgr.broadcast_event = AsyncMock()
            asyncio.run(pipe.run_pipeline())
            mgr.broadcast_event.assert_awaited_once()

    def test_ingest_hubspot_success(self, monkeypatch):
        monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "t")
        pipe = SalesMemoryPipeline(workspace_id="ws1")
        pipe.memory_manager = Mock()
        pipe.memory_manager.ingest_communication = Mock(return_value=True)
        with patch("integrations.atom_sales_memory_pipeline.get_hubspot_service") as gf:
            svc = Mock()
            svc.get_deals = AsyncMock(return_value={"results": [{"id": "d1", "properties": {
                "dealname": "D", "amount": "10", "dealstage": "open"}}]})
            gf.return_value = svc
            asyncio.run(pipe._ingest_hubspot())
        pipe.memory_manager.ingest_communication.assert_called_once()

    def test_ingest_hubspot_service_missing(self, monkeypatch):
        monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "t")
        pipe = SalesMemoryPipeline(workspace_id="ws1")
        pipe.memory_manager = Mock()
        with patch("integrations.atom_sales_memory_pipeline.get_hubspot_service", return_value=None):
            asyncio.run(pipe._ingest_hubspot())
        pipe.memory_manager.ingest_communication.assert_not_called()

    def test_ingest_hubspot_failure(self, monkeypatch):
        monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "t")
        pipe = SalesMemoryPipeline(workspace_id="ws1")
        pipe.memory_manager = Mock()
        with patch("integrations.atom_sales_memory_pipeline.get_hubspot_service") as gf:
            gf.return_value.get_deals = AsyncMock(side_effect=RuntimeError("boom"))
            asyncio.run(pipe._ingest_hubspot())

    def test_ingest_deal_error(self):
        pipe = SalesMemoryPipeline(workspace_id="ws1")
        pipe.memory_manager = Mock()
        pipe.memory_manager.ingest_communication = Mock(side_effect=RuntimeError("boom"))
        assert pipe._ingest_deal("hubspot", {"id": "d1", "properties": {}}) is False


# ============================================================================
# atom_teams_integration — remaining branches
# ============================================================================

class TestTeamsIntegrationCoverage:
    def _svc(self):
        svc = teams_mod.AtomTeamsIntegration({
            "atom_memory_service": Mock(), "atom_search_service": Mock(),
            "atom_workflow_service": Mock()})
        return svc

    def test_initialize_unified_data(self):
        svc = self._svc()
        svc.atom_memory.query = AsyncMock(return_value=[])
        asyncio.run(svc._initialize_unified_data())

    def test_initialize_unified_data_error(self):
        svc = self._svc()
        svc.atom_memory.query = AsyncMock(side_effect=RuntimeError("boom"))
        asyncio.run(svc._initialize_unified_data())

    def test_get_unified_workspaces_error(self):
        svc = self._svc()
        svc.teams_service = Mock()
        svc.teams_service.get_workspaces = AsyncMock(side_effect=RuntimeError("boom"))
        assert asyncio.run(svc.get_unified_workspaces("u1")) == []

    def test_get_unified_channels_error(self):
        svc = self._svc()
        svc.teams_service = Mock()
        svc.teams_service.get_channels = AsyncMock(side_effect=RuntimeError("boom"))
        assert asyncio.run(svc.get_unified_channels("teams_t1", "u1")) == []

    def test_get_unified_messages_error(self):
        svc = self._svc()
        svc.teams_service = Mock()
        svc.teams_service.get_channel_messages = AsyncMock(side_effect=RuntimeError("boom"))
        assert asyncio.run(svc.get_unified_messages("teams_t1", "teams_c1")) == []

    def test_unified_search_error(self):
        svc = self._svc()
        svc.teams_service = Mock()
        svc.teams_service.search_messages = AsyncMock(side_effect=RuntimeError("boom"))
        assert asyncio.run(svc.unified_search("q", workspace_id="teams_t1", channel_id="teams_c1")) == []

    def test_send_message_teams_failure_returns_error(self):
        svc = self._svc()
        svc.teams_service = Mock()
        svc.teams_service.send_message = AsyncMock(return_value={"ok": False, "error": "nope"})
        result = asyncio.run(svc.send_unified_message("teams_t1", "teams_c1", "hi"))
        assert result["ok"] is False

    def test_send_message_exception(self):
        svc = self._svc()
        svc.teams_service = Mock()
        svc.teams_service.send_message = AsyncMock(side_effect=RuntimeError("boom"))
        result = asyncio.run(svc.send_unified_message("teams_t1", "teams_c1", "hi"))
        assert result["ok"] is False

    def test_create_workflow_no_workflow_service(self):
        svc = teams_mod.AtomTeamsIntegration({})
        svc.atom_workflow = None
        result = asyncio.run(svc.create_unified_workflow({"triggers": [], "actions": []}))
        assert result["ok"] is False

    def test_create_workflow_exception(self):
        svc = self._svc()
        svc.atom_workflow.create_workflow = AsyncMock(side_effect=RuntimeError("boom"))
        result = asyncio.run(svc.create_unified_workflow({"name": "N", "triggers": [], "actions": []}))
        assert result["ok"] is False

    def test_get_unified_analytics_error(self):
        svc = self._svc()
        svc.teams_analytics = Mock()
        svc.teams_analytics.get_analytics = AsyncMock(side_effect=RuntimeError("boom"))
        result = asyncio.run(svc.get_unified_analytics("m", "7d"))
        assert result["ok"] is False

    def test_store_message_in_memory_without_service(self):
        svc = teams_mod.AtomTeamsIntegration({})
        asyncio.run(svc._store_message_in_memory({"message_id": "1"}, "teams"))

    def test_index_message_in_search_without_service(self):
        svc = teams_mod.AtomTeamsIntegration({})
        asyncio.run(svc._index_message_in_search({"message_id": "1"}, "teams"))

    def test_trigger_workflows_without_service(self):
        svc = teams_mod.AtomTeamsIntegration({})
        asyncio.run(svc._trigger_workflows({"message_id": "1"}, "evt"))

    def test_store_message_error(self):
        svc = self._svc()
        svc.atom_memory.store = AsyncMock(side_effect=RuntimeError("boom"))
        asyncio.run(svc._store_message_in_memory({"message_id": "1"}, "teams"))

    def test_index_message_error(self):
        svc = self._svc()
        svc.atom_search.index = AsyncMock(side_effect=RuntimeError("boom"))
        asyncio.run(svc._index_message_in_search({"message_id": "1"}, "teams"))

    def test_trigger_workflows_error(self):
        svc = self._svc()
        svc.atom_workflow.trigger_workflows = AsyncMock(side_effect=RuntimeError("boom"))
        asyncio.run(svc._trigger_workflows({"message_id": "1"}, "evt"))

    def test_handle_teams_file_and_user_events(self):
        svc = self._svc()
        svc._index_file_in_search = AsyncMock()
        svc._store_file_in_memory = AsyncMock()
        svc._update_user_profile_cross_platform = AsyncMock()
        with patch.object(svc, "_trigger_workflows", new_callable=AsyncMock) as t:
            asyncio.run(svc._handle_teams_file_cross_platform({}))
            svc._index_file_in_search.assert_awaited_once()
            svc._store_file_in_memory.assert_awaited_once()
            t.assert_awaited_once()
        with patch.object(svc, "_trigger_workflows", new_callable=AsyncMock) as t2:
            asyncio.run(svc._handle_teams_user_event_cross_platform({}))
            svc._update_user_profile_cross_platform.assert_awaited_once()
            t2.assert_awaited_once()

    def test_cross_platform_handler_errors(self):
        svc = self._svc()
        svc.atom_memory.store = AsyncMock(side_effect=RuntimeError("boom"))
        asyncio.run(svc._handle_teams_message_cross_platform({"message_id": "1"}))
        svc.atom_search.index = AsyncMock(side_effect=RuntimeError("boom"))
        asyncio.run(svc._handle_teams_message_cross_platform({"message_id": "1"}))
        svc.atom_workflow.trigger_workflows = AsyncMock(side_effect=RuntimeError("boom"))
        asyncio.run(svc._handle_teams_message_cross_platform({"message_id": "1"}))

    def test_generate_search_highlights_empty(self):
        svc = self._svc()
        assert svc._generate_search_highlights("", "") == []

    def test_workers_loop_once(self):
        svc = self._svc()
        with patch("asyncio.sleep", AsyncMock(side_effect=asyncio.CancelledError())):
            with pytest.raises(asyncio.CancelledError):
                asyncio.run(svc._teams_message_ingestion_worker())

    def test_event_processing_worker_error_path(self):
        svc = self._svc()
        with patch("asyncio.sleep", AsyncMock(side_effect=[RuntimeError("boom"), asyncio.CancelledError()])):
            with pytest.raises(asyncio.CancelledError):
                asyncio.run(svc._teams_event_processing_worker())

    def test_unified_search_indexing_worker(self):
        svc = self._svc()
        svc.atom_search = Mock()
        svc.atom_memory = Mock()
        svc.atom_memory.query = AsyncMock(return_value=[{"id": "m1", "message_id": "1"}])
        svc.atom_memory.update = AsyncMock()
        with patch.object(svc, "_index_message_in_search", new_callable=AsyncMock), \
             patch("asyncio.sleep", AsyncMock(side_effect=asyncio.CancelledError())):
            with pytest.raises(asyncio.CancelledError):
                asyncio.run(svc._unified_search_indexing_worker())
        svc.atom_memory.update.assert_awaited_once()

    def test_unified_search_indexing_worker_error(self):
        svc = self._svc()
        svc.atom_search = Mock()
        svc.atom_memory = Mock()
        svc.atom_memory.query = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("asyncio.sleep", AsyncMock(side_effect=[asyncio.CancelledError()])):
            with pytest.raises(asyncio.CancelledError):
                asyncio.run(svc._unified_search_indexing_worker())

    def test_start_integration_workers(self):
        svc = self._svc()
        with patch.object(svc, "_teams_message_ingestion_worker", new=AsyncMock()) as w1, \
             patch.object(svc, "_teams_event_processing_worker", new=AsyncMock()) as w2, \
             patch.object(svc, "_unified_search_indexing_worker", new=AsyncMock()) as w3:
            asyncio.run(svc._start_integration_workers())
            asyncio.sleep(0)
            assert w1.await_count + w2.await_count + w3.await_count == 3


# ============================================================================
# atom_whatsapp_integration — remaining branches
# ============================================================================

class TestWhatsAppCoverage:
    def _wa(self):
        return whatsapp_mod.AtomWhatsAppIntegration({
            "access_token": "tok", "phone_number_id": "ph1", "webhook_url": None,
            "enable_enterprise_features": True})

    def test_verify_api_connection_success_and_failure(self):
        wa = self._wa()
        resp = Mock()
        resp.status_code = 200
        wa.http_session = Mock()
        wa.http_session.get = AsyncMock(return_value=resp)
        asyncio.run(wa._verify_api_connection())
        # Fail-closed: non-200 or transport error must raise so initialize()
        # cannot claim success over a dead API connection.
        resp.status_code = 401
        with pytest.raises(RuntimeError):
            asyncio.run(wa._verify_api_connection())
        wa.http_session.get = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError):
            asyncio.run(wa._verify_api_connection())

    def test_setup_webhook_paths(self):
        wa = self._wa()
        wa.whatsapp_config["webhook_url"] = "https://x/webhook"
        wa.whatsapp_config["webhook_secret"] = "secret"
        resp = Mock()
        resp.status_code = 200
        wa.http_session = Mock()
        wa.http_session.post = AsyncMock(return_value=resp)
        asyncio.run(wa._setup_webhook())
        resp.status_code = 400
        asyncio.run(wa._setup_webhook())
        wa.http_session.post = AsyncMock(side_effect=RuntimeError("boom"))
        asyncio.run(wa._setup_webhook())

    def test_setup_enterprise_features_services_missing(self):
        wa = self._wa()
        wa.enterprise_security = None
        wa.enterprise_automation = None
        asyncio.run(wa._setup_enterprise_features())

    def test_setup_enterprise_features_full(self):
        wa = self._wa()
        wa.enterprise_security = Mock()
        wa.enterprise_automation = Mock()
        with patch.object(wa, "_setup_security_policies", new_callable=AsyncMock), \
             patch.object(wa, "_setup_compliance_rules", new_callable=AsyncMock), \
             patch.object(wa, "_setup_automation_triggers", new_callable=AsyncMock):
            asyncio.run(wa._setup_enterprise_features())

    def test_setup_security_policies(self):
        wa = self._wa()
        asyncio.run(wa._setup_security_policies())
        assert "message_content_filter" in wa.security_policies

    def test_setup_compliance_rules(self):
        wa = self._wa()
        asyncio.run(wa._setup_compliance_rules())
        assert "message_retention" in wa.compliance_rules

    def test_setup_automation_triggers(self):
        wa = self._wa()
        asyncio.run(wa._setup_automation_triggers())
        assert "message_received" in wa.automation_triggers

    def test_setup_automation_service_missing(self):
        wa = self._wa()
        wa.enterprise_automation = None
        asyncio.run(wa._setup_automation())

    def test_setup_automation_success_and_fail(self):
        wa = self._wa()
        wa.enterprise_automation = Mock()
        wa.enterprise_automation.create_integration_automation = AsyncMock(return_value={"ok": True})
        asyncio.run(wa._setup_automation())
        wa.enterprise_automation.create_integration_automation = AsyncMock(
            return_value={"ok": False, "error": "x"})
        asyncio.run(wa._setup_automation())
        wa.enterprise_automation.create_integration_automation = AsyncMock(
            side_effect=RuntimeError("boom"))
        asyncio.run(wa._setup_automation())

    def test_setup_security_and_compliance_disabled(self):
        wa = self._wa()
        wa.whatsapp_config["enable_enterprise_features"] = False
        asyncio.run(wa._setup_security_and_compliance())

    def test_setup_security_and_compliance_full(self):
        wa = self._wa()
        with patch.object(wa, "_setup_security_monitoring", new_callable=AsyncMock), \
             patch.object(wa, "_setup_compliance_monitoring", new_callable=AsyncMock):
            asyncio.run(wa._setup_security_and_compliance())

    def test_setup_monitoring_and_load_data(self):
        wa = self._wa()
        asyncio.run(wa._setup_monitoring())
        asyncio.run(wa._load_existing_data())

    def test_perform_ai_search_no_service(self):
        wa = self._wa()
        wa.ai_service = None
        assert asyncio.run(wa._perform_ai_search("q")) == []

    def test_perform_ai_search_with_service(self):
        wa = self._wa()
        svc = Mock()
        resp = Mock()
        resp.ok = True
        resp.output_data = {"results": [{"id": "r1"}]}
        svc.process_ai_request = AsyncMock(return_value=resp)
        wa.ai_service = svc
        class _T:
            SEARCH_QUERY = "search"
        class _M:
            GPT_4 = "gpt4"
        class _S:
            OPENAI = "openai"
        with patch.object(whatsapp_mod, "AIRequest", Mock(return_value=Mock())) as reqcls, \
             patch.object(whatsapp_mod, "AITaskType", _T), \
             patch.object(whatsapp_mod, "AIModelType", _M), \
             patch.object(whatsapp_mod, "AIServiceType", _S):
            result = asyncio.run(wa._perform_ai_search("q"))
        assert result == [{"id": "r1"}]
        reqcls.assert_called_once()
        resp2 = Mock()
        resp2.ok = False
        resp2.output_data = None
        svc.process_ai_request = AsyncMock(return_value=resp2)
        assert asyncio.run(wa._perform_ai_search("q")) == []
        svc.process_ai_request = AsyncMock(side_effect=RuntimeError("boom"))
        assert asyncio.run(wa._perform_ai_search("q")) == []

    def test_log_message_event_no_service(self):
        wa = self._wa()
        wa.enterprise_security = None
        asyncio.run(wa._log_message_event("evt", "c1", {}))
        wa.enterprise_security = Mock()
        wa.enterprise_security.audit_event = AsyncMock(side_effect=RuntimeError("boom"))
        asyncio.run(wa._log_message_event("evt", "c1", {}))

    def test_search_ai_path_in_perform_intelligent_search(self):
        wa = self._wa()
        wa.ai_service = Mock()
        with patch.object(wa, "_perform_ai_search", new_callable=AsyncMock, return_value=[{"id": "ai1"}]):
            result = asyncio.run(wa.perform_intelligent_search("q", "u1"))
        assert result == [{"id": "ai1"}]

    def test_intelligent_search_exception(self):
        wa = self._wa()
        wa.message_history = {}
        wa.ai_service = None
        assert asyncio.run(wa.perform_intelligent_search("q", "u1", "ws")) == []

    def test_get_intelligent_workspaces_error(self):
        wa = self._wa()
        class Boom:
            def __getattr__(self, name):
                raise RuntimeError("boom")
        wa.active_chats = {"c1": Boom()}
        assert asyncio.run(wa.get_intelligent_workspaces("u1")) == []

    def test_get_intelligent_channels_inactive(self):
        wa = self._wa()
        chat = SimpleNamespace(chat_id="c1", name="C", chat_type=whatsapp_mod.WhatsAppChatType.GROUP,
                               member_count=1, description=None, last_message=datetime(2026, 1, 1),
                               security_level="s", permissions=[], participants=["u1"],
                               admin_participants=[], is_active=False)
        wa.active_chats = {"c1": chat}
        result = asyncio.run(wa.get_intelligent_channels("c1", "u1"))
        assert result[0]["is_active"] is False

    def test_get_service_status_uptime(self):
        wa = self._wa()
        wa._start_time = time.time() - 100
        result = asyncio.run(wa.get_service_status())
        assert result["uptime"] > 90

    def test_get_service_status_error(self):
        wa = self._wa()
        wa.analytics_metrics = Mock(side_effect=RuntimeError("boom"))
        result = asyncio.run(wa.get_service_status())
        assert "error" in result

    def test_close_error(self):
        wa = self._wa()
        wa.http_session = Mock()
        wa.http_session.aclose = AsyncMock(side_effect=RuntimeError("boom"))
        asyncio.run(wa.close())


# ============================================================================
# atom_communication_ingestion_pipeline — remaining 64 lines
# ============================================================================

class TestPipelineWebhookHelpers:
    def _pipeline(self):
        mgr = Mock()
        return pipeline_mod.CommunicationIngestionPipeline(mgr)

    def test_enable_and_status_webhook(self):
        pipe = self._pipeline()
        pipe.enable_webhook_ingestion("slack")
        assert pipe.is_webhook_enabled("slack") is True
        pipe.enable_webhook_ingestion("slack", enabled=False)
        assert pipe.is_webhook_enabled("slack") is False
        status = pipe.get_webhook_status()
        assert set(status.keys()) == {"slack", "teams", "gmail", "outlook"}

    def test_handle_webhook_message_no_app_type(self):
        pipe = self._pipeline()
        with patch.object(pipe, "ingest_message", new_callable=AsyncMock) as im:
            asyncio.run(pipe._handle_webhook_message({}))
            im.assert_not_awaited()

    def test_handle_webhook_message_disabled(self):
        pipe = self._pipeline()
        pipe.webhook_enabled["slack"] = False
        with patch.object(pipe, "ingest_message", new_callable=AsyncMock) as im:
            asyncio.run(pipe._handle_webhook_message({"app_type": "slack"}))
            im.assert_not_awaited()

    def test_handle_webhook_message_success_failure(self):
        pipe = self._pipeline()
        pipe.webhook_enabled["slack"] = True
        with patch.object(pipe, "ingest_message", new_callable=AsyncMock, return_value=True) as im:
            asyncio.run(pipe._handle_webhook_message({"app_type": "slack"}))
            im.assert_awaited_once()
        with patch.object(pipe, "ingest_message", new_callable=AsyncMock, return_value=False) as im2:
            asyncio.run(pipe._handle_webhook_message({"app_type": "slack"}))
        pipe.webhook_enabled["slack"] = True
        with patch.object(pipe, "ingest_message",
                          new_callable=AsyncMock, side_effect=RuntimeError("boom")) as im3:
            asyncio.run(pipe._handle_webhook_message({"app_type": "slack"}))

    def test_sentence_transformer_import_success(self):
        import builtins as _b
        real_import = _b.__import__
        fake_mod = types.ModuleType("sentence_transformers")
        fake_mod.SentenceTransformer = Mock(return_value=Mock())
        def _fake_import(name, *a, **k):
            if name == "sentence_transformers":
                return fake_mod
            return real_import(name, *a, **k)
        pipeline_mod._sentence_transformer_checked = False
        pipeline_mod.SentenceTransformer = None
        with patch("builtins.__import__", side_effect=_fake_import):
            cls = pipeline_mod._get_sentence_transformer()
        assert cls is fake_mod.SentenceTransformer
        # Restore module state so subsequent tests re-run the real import check
        pipeline_mod._sentence_transformer_checked = False
        pipeline_mod.SentenceTransformer = None

    def test_start_real_time_stream_paths(self):
        pipe = self._pipeline()
        assert pipe.start_real_time_stream("unknown") is False
        pipe.ingestion_configs["slack"] = {"real_time": False}
        assert pipe.start_real_time_stream("slack") is False

    def test_start_real_time_stream_success_and_loop(self):
        pipe = self._pipeline()
        pipe.ingestion_configs["slack"] = {"real_time": True}
        pipe.app_configs["slack"] = {"polling_interval_seconds": 1}

        async def _run():
            ok = pipe.start_real_time_stream("slack")
            assert ok is True
            assert "slack" in pipe.active_streams
            await asyncio.sleep(0)
            pipe.active_streams["slack"].cancel()
            try:
                await pipe.active_streams["slack"]
            except asyncio.CancelledError:
                pass

        with patch.object(pipe, "_fetch_new_messages", new_callable=AsyncMock, return_value=[{
                "id": "1", "content": "hi"}]), \
             patch.object(pipe, "ingest_message", new_callable=AsyncMock), \
             patch("asyncio.sleep", AsyncMock(side_effect=asyncio.CancelledError())):
            with pytest.raises(asyncio.CancelledError):
                asyncio.run(_run())

    def test_real_time_ingestion_error_path(self):
        pipe = self._pipeline()
        pipe.app_configs["slack"] = {"polling_interval_seconds": 1}
        with patch.object(pipe, "_fetch_new_messages", new_callable=AsyncMock,
                          side_effect=RuntimeError("boom")), \
             patch("asyncio.sleep", AsyncMock(side_effect=[None, asyncio.CancelledError()])):
            with pytest.raises(asyncio.CancelledError):
                asyncio.run(pipe._real_time_ingestion("slack"))

    def test_fetch_new_messages_unknown_app(self):
        pipe = self._pipeline()
        msgs = asyncio.run(pipe._fetch_new_messages("unknown_app"))
        assert msgs == []

    def test_fetch_new_messages_teams_dispatches(self):
        pipe = self._pipeline()
        with patch.object(pipe, "_fetch_teams_messages", new_callable=AsyncMock, return_value=[{"id": "1"}]):
            msgs = asyncio.run(pipe._fetch_new_messages(CommunicationAppType.MICROSOFT_TEAMS.value))
        assert msgs == [{"id": "1"}]

    def test_fetch_new_messages_error(self):
        pipe = self._pipeline()
        with patch.object(pipe, "_fetch_slack_messages", new_callable=AsyncMock,
                          side_effect=RuntimeError("boom")):
            assert asyncio.run(pipe._fetch_new_messages("slack")) == []

    def test_fetch_whatsapp_messages_import_error(self):
        pipe = self._pipeline()
        with patch("builtins.__import__", side_effect=ImportError("no whatsapp")):
            assert asyncio.run(pipe._fetch_whatsapp_messages(None)) == []

    def test_fetch_whatsapp_messages_error(self):
        pipe = self._pipeline()
        with patch("integrations.atom_whatsapp_integration.atom_whatsapp_integration") as wa:
            wa.get_messages = AsyncMock(side_effect=RuntimeError("boom"))
            assert asyncio.run(pipe._fetch_whatsapp_messages(None)) == []

    def test_fetch_slack_no_token(self, monkeypatch):
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        pipe = self._pipeline()
        assert asyncio.run(pipe._fetch_slack_messages(None)) == []

    def test_fetch_slack_no_channels(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb")
        pipe = self._pipeline()
        pipe.app_configs["slack"] = {}
        assert asyncio.run(pipe._fetch_slack_messages(None)) == []

    def test_fetch_slack_full_flow(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb")
        pipe = self._pipeline()
        pipe.app_configs["slack"] = {"monitored_channels": ["C1"], "include_bot_messages": False}

        client = Mock()
        client.close = AsyncMock()
        client.conversations_info = AsyncMock(return_value={"ok": True, "channel": {"name": "gen"}})
        responses = [
            {"ok": True, "messages": [
                {"ts": "1700000000.1", "type": "message", "user": "u1", "text": "hi"},
                {"ts": "1700000000.2", "type": "message", "bot_id": "b1", "text": "bot"},
                {"ts": "1700000000.3", "type": "message", "subtype": "message_deleted", "user": "u2"},
                {"ts": "1700000000.4", "type": "non_message"},
            ], "response_metadata": {"next_cursor": ""}},
        ]
        client.conversations_history = AsyncMock(side_effect=responses)

        slack_sdk = types.ModuleType("slack_sdk")
        slack_sdk.errors = types.ModuleType("slack_sdk.errors")
        class SlackApiError(Exception):
            def __init__(self, message, response=None):
                super().__init__(message)
                self.response = response or {}
        slack_sdk.errors.SlackApiError = SlackApiError
        async_client_mod = types.ModuleType("slack_sdk.web.async_client")
        async_client_mod.AsyncWebClient = Mock(return_value=client)
        sys.modules["slack_sdk"] = slack_sdk
        sys.modules["slack_sdk.errors"] = slack_sdk.errors
        sys.modules["slack_sdk.web"] = types.ModuleType("slack_sdk.web")
        sys.modules["slack_sdk.web.async_client"] = async_client_mod
        try:
            msgs = asyncio.run(pipe._fetch_slack_messages(datetime(2026, 1, 1)))
        finally:
            for mod in ("slack_sdk", "slack_sdk.errors", "slack_sdk.web", "slack_sdk.web.async_client"):
                sys.modules.pop(mod, None)
        assert len(msgs) == 1
        assert msgs[0]["id"] == "1700000000.1"

    def test_fetch_slack_no_more_messages(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb")
        pipe = self._pipeline()
        pipe.app_configs["slack"] = {"monitored_channels": ["C1"]}
        client = Mock()
        client.close = AsyncMock()
        client.conversations_history = AsyncMock(return_value={"ok": True, "messages": []})
        slack_sdk = types.ModuleType("slack_sdk")
        slack_sdk.errors = types.ModuleType("slack_sdk.errors")
        class SlackApiError(Exception):
            def __init__(self, message, response=None):
                super().__init__(message)
                self.response = response or {}
        slack_sdk.errors.SlackApiError = SlackApiError
        async_client_mod = types.ModuleType("slack_sdk.web.async_client")
        async_client_mod.AsyncWebClient = Mock(return_value=client)
        sys.modules["slack_sdk"] = slack_sdk
        sys.modules["slack_sdk.errors"] = slack_sdk.errors
        sys.modules["slack_sdk.web"] = types.ModuleType("slack_sdk.web")
        sys.modules["slack_sdk.web.async_client"] = async_client_mod
        try:
            assert asyncio.run(pipe._fetch_slack_messages(None)) == []
        finally:
            for mod in ("slack_sdk", "slack_sdk.errors", "slack_sdk.web", "slack_sdk.web.async_client"):
                sys.modules.pop(mod, None)

    def test_fetch_slack_not_ok_and_rate_limited(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb")
        pipe = self._pipeline()
        pipe.app_configs["slack"] = {"monitored_channels": ["C1", "C2"]}
        client = Mock()
        client.close = AsyncMock()

        async def _history(channel=None, oldest=None, limit=None, cursor=None, inclusive=None):
            if channel == "C1":
                return {"ok": False, "error": "channel_not_found"}
            raise SlackApiError("ratelimited", {"error": "ratelimited", "headers": {"Retry-After": "1"}})
        client.conversations_history = _history

        slack_sdk = types.ModuleType("slack_sdk")
        slack_sdk.errors = types.ModuleType("slack_sdk.errors")
        class SlackApiError(Exception):
            def __init__(self, message, response=None):
                super().__init__(message)
                self.response = response or {}
        slack_sdk.errors.SlackApiError = SlackApiError
        async_client_mod = types.ModuleType("slack_sdk.web.async_client")
        async_client_mod.AsyncWebClient = Mock(return_value=client)
        sys.modules["slack_sdk"] = slack_sdk
        sys.modules["slack_sdk.errors"] = slack_sdk.errors
        sys.modules["slack_sdk.web"] = types.ModuleType("slack_sdk.web")
        sys.modules["slack_sdk.web.async_client"] = async_client_mod
        try:
            assert asyncio.run(pipe._fetch_slack_messages(None)) == []
        finally:
            for mod in ("slack_sdk", "slack_sdk.errors", "slack_sdk.web", "slack_sdk.web.async_client"):
                sys.modules.pop(mod, None)

    def test_fetch_slack_import_error(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb")
        pipe = self._pipeline()
        real_import = builtins.__import__
        def _block(name, *a, **k):
            if name == "slack_sdk" or name.startswith("slack_sdk."):
                raise ImportError("slack_sdk not installed")
            return real_import(name, *a, **k)
        with patch("builtins.__import__", side_effect=_block):
            assert asyncio.run(pipe._fetch_slack_messages(None)) == []

    def test_get_channel_name(self):
        pipe = self._pipeline()
        client = Mock()
        client.conversations_info = AsyncMock(return_value={"ok": True, "channel": {"name": "gen"}})
        assert asyncio.run(pipe._get_channel_name(client, "C1")) == "gen"
        client.conversations_info = AsyncMock(return_value={"ok": False})
        assert asyncio.run(pipe._get_channel_name(client, "C1")) is None
        client.conversations_info = AsyncMock(side_effect=RuntimeError("boom"))
        assert asyncio.run(pipe._get_channel_name(client, "C1")) is None

    def test_fetch_teams_no_token(self):
        pipe = self._pipeline()
        with patch("core.token_storage.token_storage") as ts:
            ts.get_token = Mock(return_value=None)
            assert asyncio.run(pipe._fetch_teams_messages(None)) == []

    def test_fetch_teams_chat_messages(self):
        pipe = self._pipeline()

        class FakeResp:
            def __init__(self, status, data):
                self.status_code = status
                self._data = data
                self.headers = {}
            def json(self):
                return self._data

        client = Mock()
        calls = {
            "https://graph.microsoft.com/v1.0/me/chats": FakeResp(200, {"value": [
                {"id": "chat1", "chatType": "group", "topic": "Proj"}]}),
            "https://graph.microsoft.com/v1.0/me/chats/chat1/messages": FakeResp(200, {"value": [
                {"id": "msg1", "from": {"user": {"displayName": "A", "email": "a@b.c"}},
                 "body": {"content": "hi", "contentType": "text"}, "attachments": [],
                 "createdDateTime": "2026-01-01T10:00:00Z"}]}),
        }
        async def _get(url, headers=None, params=None):
            return calls[url]
        client.get = _get

        msgs = asyncio.run(pipe._fetch_teams_chat_messages(client, {"Authorization": "x"}, datetime(2026, 1, 1)))
        assert msgs[0]["id"] == "msg1"

    def test_fetch_teams_chat_messages_rate_limited_and_skips(self):
        pipe = self._pipeline()

        class FakeResp:
            def __init__(self, status, data=None, headers=None):
                self.status_code = status
                self._data = data or {}
                self.headers = headers or {}
            def json(self):
                return self._data

        client = Mock()
        calls = {
            "https://graph.microsoft.com/v1.0/me/chats": FakeResp(200, {"value": [
                {},  # no id → skipped
                {"id": "chat1"}]}),
            "https://graph.microsoft.com/v1.0/me/chats/chat1/messages": FakeResp(429, headers={"Retry-After": "1"}),
        }
        async def _get(url, headers=None, params=None):
            return calls[url]
        client.get = _get
        with patch("asyncio.sleep", AsyncMock()):
            msgs = asyncio.run(pipe._fetch_teams_chat_messages(client, {"Authorization": "x"}, None))
        assert msgs == []

    def test_fetch_teams_chat_messages_error_paths(self):
        pipe = self._pipeline()

        class FakeResp:
            status_code = 200
            def json(self):
                return {"value": [{"id": "chat1"}]}

        client = Mock()
        async def _get(url, headers=None, params=None):
            if url.endswith("/messages"):
                raise RuntimeError("graph down")
            return FakeResp()
        client.get = _get
        assert asyncio.run(pipe._fetch_teams_chat_messages(client, {"Authorization": "x"}, None)) == []

        async def _get2(url, headers=None, params=None):
            return FakeResp()
        client.get = _get2
        msgs = asyncio.run(pipe._fetch_teams_chat_messages(client, {"Authorization": "x"}, None))
        assert msgs[0]["id"] == "chat1"

    def test_fetch_teams_channel_messages(self):
        pipe = self._pipeline()

        class FakeResp:
            def __init__(self, status, data, headers=None):
                self.status_code = status
                self._data = data
                self.headers = headers or {}
            def json(self):
                return self._data

        client = Mock()
        calls = {
            "https://graph.microsoft.com/v1.0/me/joinedTeams": FakeResp(200, {"value": [
                {"id": "team1", "displayName": "T1"}, {"id": None}]}),
            "https://graph.microsoft.com/v1.0/teams/team1/channels": FakeResp(200, {"value": [
                {"id": "chan1", "displayName": "Gen"}]}),
            "https://graph.microsoft.com/v1.0/teams/team1/channels/chan1/messages": FakeResp(200, {"value": [
                {"id": "m1", "from": {"user": {"displayName": "A", "email": "a@b.c"}},
                 "body": {"content": "hi", "contentType": "text"}, "attachments": [],
                 "createdDateTime": "2026-01-01T10:00:00Z", "replyToId": None}]}),
        }
        async def _get(url, headers=None, params=None):
            return calls[url]
        client.get = _get
        msgs = asyncio.run(pipe._fetch_teams_channel_messages(client, {"Authorization": "x"}, datetime(2026, 1, 1)))
        assert msgs[0]["recipient"] == "T1/Gen"

    def test_fetch_teams_channel_messages_skip_paths(self):
        pipe = self._pipeline()

        class FakeResp:
            def __init__(self, status, data=None, headers=None):
                self.status_code = status
                self._data = data or {}
                self.headers = headers or {}
            def json(self):
                return self._data

        client = Mock()
        calls = {
            "https://graph.microsoft.com/v1.0/me/joinedTeams": FakeResp(200, {"value": [
                {"id": "team1"}]}),
            "https://graph.microsoft.com/v1.0/teams/team1/channels": FakeResp(200, {"value": [
                {}, {"id": "chan1"}]}),
            "https://graph.microsoft.com/v1.0/teams/team1/channels/chan1/messages": FakeResp(429, headers={"Retry-After": "1"}),
        }
        async def _get(url, headers=None, params=None):
            return calls[url]
        client.get = _get
        with patch("asyncio.sleep", AsyncMock()):
            assert asyncio.run(pipe._fetch_teams_channel_messages(client, {"Authorization": "x"}, None)) == []

    def test_fetch_teams_channel_messages_non200_and_error(self):
        pipe = self._pipeline()

        class FakeResp:
            def __init__(self, status, data=None):
                self.status_code = status
                self._data = data or {}
            def json(self):
                return self._data

        client = Mock()
        calls = {
            "https://graph.microsoft.com/v1.0/me/joinedTeams": FakeResp(403),
        }
        async def _get(url, headers=None, params=None):
            return calls[url]
        client.get = _get
        assert asyncio.run(pipe._fetch_teams_channel_messages(client, {"Authorization": "x"}, None)) == []

        calls["https://graph.microsoft.com/v1.0/me/joinedTeams"] = FakeResp(200, {"value": [{"id": "t1"}]})
        calls["https://graph.microsoft.com/v1.0/teams/t1/channels"] = FakeResp(200, {"value": [{"id": "c1"}]})
        async def _get2(url, headers=None, params=None):
            if url.endswith("/messages"):
                raise RuntimeError("boom")
            return calls[url]
        client.get = _get2
        assert asyncio.run(pipe._fetch_teams_channel_messages(client, {"Authorization": "x"}, None)) == []

    def test_fetch_teams_outer_error(self):
        pipe = self._pipeline()
        with patch("core.token_storage.token_storage") as ts:
            ts.get_token = Mock(side_effect=RuntimeError("boom"))
            assert asyncio.run(pipe._fetch_teams_messages(None)) == []

    def test_fetch_email_no_credentials(self, monkeypatch):
        monkeypatch.delenv("IMAP_SERVER", raising=False)
        pipe = self._pipeline()
        assert asyncio.run(pipe._fetch_email_messages(None)) == []

    def test_fetch_email_imap_flow(self, monkeypatch):
        monkeypatch.setenv("IMAP_SERVER", "imap.x.com")
        monkeypatch.setenv("IMAP_USER", "u")
        monkeypatch.setenv("IMAP_PASSWORD", "p")
        pipe = self._pipeline()
        with patch.object(pipe, "_fetch_imap_messages", return_value=[{"id": "1"}]) as fimap:
            assert asyncio.run(pipe._fetch_email_messages(None)) == [{"id": "1"}]
            fimap.assert_called_once()

    def test_fetch_email_imap_error(self, monkeypatch):
        monkeypatch.setenv("IMAP_SERVER", "imap.x.com")
        monkeypatch.setenv("IMAP_USER", "u")
        monkeypatch.setenv("IMAP_PASSWORD", "p")
        pipe = self._pipeline()
        with patch.object(pipe, "_fetch_imap_messages", side_effect=RuntimeError("boom")):
            assert asyncio.run(pipe._fetch_email_messages(None)) == []

    def test_fetch_imap_messages_full(self):
        pipe = self._pipeline()
        mail = Mock()
        mail.login = Mock()
        mail.select = Mock()
        mail.search = Mock(return_value=("OK", [b"1 2 3"]))
        mail.fetch = Mock(return_value=("OK", [(b"1", make_email_message())]))
        mail.close = Mock()
        mail.logout = Mock()
        imaplib_mod = types.ModuleType("imaplib")
        imaplib_mod.IMAP4_SSL = Mock(return_value=mail)
        with patch.dict(sys.modules, {"imaplib": imaplib_mod}):
            msgs = pipe._fetch_imap_messages("srv", "u", "p", datetime(2026, 1, 1))
        assert len(msgs) == 3
        assert msgs[0]["id"] == "1"
        assert "plain body" in msgs[0]["content"]
        assert msgs[0]["subject"] == "Hello World"
        assert len(msgs[0]["attachments"]) == 1
        mail.logout.assert_called_once()

    def test_fetch_imap_messages_error(self):
        pipe = self._pipeline()
        imaplib_mod = types.ModuleType("imaplib")
        imaplib_mod.IMAP4_SSL = Mock(side_effect=RuntimeError("connect fail"))
        with patch.dict(sys.modules, {"imaplib": imaplib_mod}):
            assert pipe._fetch_imap_messages("srv", "u", "p", None) == []

    def test_fetch_gmail_auth_failure(self):
        pipe = self._pipeline()
        with patch("integrations.gmail_service.GmailService") as gcls:
            svc = gcls.return_value
            svc.service = None
            svc._authenticate = Mock(side_effect=RuntimeError("auth fail"))
            assert asyncio.run(pipe._fetch_gmail_messages(None)) == []

    def test_fetch_gmail_no_service(self):
        pipe = self._pipeline()
        with patch("integrations.gmail_service.GmailService") as gcls:
            svc = gcls.return_value
            svc.service = None
            svc._authenticate = Mock()
            assert asyncio.run(pipe._fetch_gmail_messages(None)) == []

    def test_fetch_gmail_full(self):
        pipe = self._pipeline()
        with patch("integrations.gmail_service.GmailService") as gcls:
            svc = gcls.return_value
            svc.service = Mock()
            svc.get_messages = AsyncMock(return_value=[
                {"id": "g1", "timestamp": "2026-01-01T10:00:00", "sender": "Name <a@b.c>",
                 "recipient": "x@y.z", "attachments": [{"id": "at1", "filename": "f.pdf", "size": 2, "contentType": "pdf"}],
                 "subject": "S", "body": "B", "threadId": "t1", "labelIds": ["IMPORTANT"], "snippet": "sn"},
                {"id": "g2", "timestamp": "1700000000", "sender": "plain@b.c",
                 "recipient": "", "attachments": [], "subject": "", "body": "", "labelIds": []},
                {"id": "g3", "sender": "", "recipient": "", "attachments": [],
                 "subject": "", "body": "", "labelIds": []},
            ])
            loop = Mock()
            loop.run_in_executor = Mock(side_effect=lambda *a, **k: a[1]() if callable(a[1]) else a[1])
            with patch("asyncio.get_event_loop", return_value=loop):
                msgs = asyncio.run(pipe._fetch_gmail_messages(datetime(2026, 1, 1)))
        assert len(msgs) == 3
        assert msgs[0]["sender"] == "Name"
        assert msgs[0]["priority"] == "high"

    def test_fetch_gmail_import_error(self):
        pipe = self._pipeline()
        real_import = builtins.__import__
        def _block(name, *a, **k):
            if name == "integrations.gmail_service":
                raise ImportError("no gmail")
            return real_import(name, *a, **k)
        with patch("builtins.__import__", side_effect=_block):
            assert asyncio.run(pipe._fetch_gmail_messages(None)) == []

    def test_fetch_outlook_full_with_pagination(self):
        pipe = self._pipeline()

        class FakeResp:
            def __init__(self, status, data, headers=None):
                self.status_code = status
                self._data = data
                self.headers = headers or {}
            def json(self):
                return self._data

        client = Mock()
        calls = {
            "https://graph.microsoft.com/v1.0/me/messages": FakeResp(200, {
                "value": [{"id": "m1", "receivedDateTime": "2026-01-01T10:00:00Z",
                           "from": {"emailAddress": {"address": "a@b.c", "name": "A"}},
                           "toRecipients": [{"emailAddress": {"address": "r@x.y"}}],
                           "body": {"content": "B", "contentType": "html"},
                           "attachments": [{"id": "at", "name": "f", "size": 1, "contentType": "pdf", "isInline": False}],
                           "subject": "S", "conversationId": "c1", "parentFolderId": "pf",
                           "importance": "High", "isRead": True, "isDraft": False, "flag": {},
                           "webLink": "w", "categories": ["cat1"]}],
                "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/messages?page=2"}),
            "https://graph.microsoft.com/v1.0/me/messages?page=2": FakeResp(200, {"value": []}),
        }
        async def _get(url, headers=None, params=None):
            return calls[url]
        client.get = _get
        class _AC:
            def __init__(self, *a, **k):
                self._inner = client
            async def __aenter__(self):
                return self._inner
            async def __aexit__(self, *a):
                return False
        with patch("integrations.atom_communication_ingestion_pipeline.httpx.AsyncClient", _AC), \
             patch("core.token_storage.token_storage") as ts:
            ts.get_token = Mock(return_value={"access_token": "tok"})
            msgs = asyncio.run(pipe._fetch_outlook_messages(None))
        assert len(msgs) == 1
        assert "cat1" in msgs[0]["tags"]
        assert msgs[0]["priority"] == "high"

    def test_fetch_outlook_rate_limited_then_ok(self):
        pipe = self._pipeline()

        class FakeResp:
            def __init__(self, status, data=None, headers=None):
                self.status_code = status
                self._data = data or {}
                self.headers = headers or {}
            def json(self):
                return self._data

        client = Mock()
        calls = {
            "https://graph.microsoft.com/v1.0/me/messages": [FakeResp(429, headers={"Retry-After": "1"}),
                                                             FakeResp(200, {"value": [{
                                                                 "id": "m1", "receivedDateTime": None,
                                                                 "from": {}, "toRecipients": [],
                                                                 "body": {}, "attachments": [],
                                                                 "subject": "", "categories": []}]}),
                                                             FakeResp(403)],
        }
        idx = {"n": 0}
        async def _get(url, headers=None, params=None):
            n = idx["n"]
            idx["n"] += 1
            return calls[url][min(n, 2)]
        client.get = _get
        class _AC:
            def __init__(self, *a, **k):
                self._inner = client
            async def __aenter__(self):
                return self._inner
            async def __aexit__(self, *a):
                return False
        with patch("integrations.atom_communication_ingestion_pipeline.httpx.AsyncClient", _AC), \
             patch("core.token_storage.token_storage") as ts, \
             patch("asyncio.sleep", AsyncMock()):
            ts.get_token = Mock(return_value={"access_token": "tok"})
            msgs = asyncio.run(pipe._fetch_outlook_messages(None))
        assert len(msgs) == 1
        assert msgs[0]["status"] == "unread"

    def test_fetch_outlook_no_token(self):
        pipe = self._pipeline()
        with patch("core.token_storage.token_storage") as ts:
            ts.get_token = Mock(return_value=None)
            assert asyncio.run(pipe._fetch_outlook_messages(None)) == []

    def test_fetch_outlook_import_error(self):
        pipe = self._pipeline()
        with patch("core.token_storage.token_storage") as ts:
            ts.get_token = Mock(side_effect=ImportError("no token storage"))
            assert asyncio.run(pipe._fetch_outlook_messages(None)) == []

    def test_get_ingestion_stats_error(self):
        pipe = self._pipeline()
        pipe.memory_manager.metadata_table.search = Mock(side_effect=RuntimeError("boom"))
        stats = pipe.get_ingestion_stats()
        assert "error" in stats

    def test_get_ingestion_stats_success(self):
        pipe = self._pipeline()
        table = Mock()
        df = Mock()
        df.iterrows = Mock(return_value=iter([
            (0, {"app_type": "slack", "total_messages": 5, "last_ingested": "2026-01-01", "status": "active"}),
        ]))
        table.search = Mock(return_value=Mock(to_pandas=Mock(return_value=df)))
        pipe.memory_manager.metadata_table = table
        pipe.ingestion_configs = {"slack": {}}
        stats = pipe.get_ingestion_stats()
        assert stats["total_messages"] == 5

    def test_initialize_and_tables(self, tmp_path):
        mm = LanceDBMemoryManager(db_path=str(tmp_path), workspace_id="cov1")
        assert mm.initialize() is True
        assert mm.db is not None and mm.connections_table is not None and mm.metadata_table is not None

    def test_search_communications_filters_and_errors(self, tmp_path):
        mm = LanceDBMemoryManager(db_path=str(tmp_path), workspace_id="cov2")
        mm.initialize()

        class FakeBuilder:
            def __init__(self):
                self.wheres = []
                self.query = None
            def vector(self, v):
                self.query = v
                return self
            def text(self, t):
                return self
            def limit(self, n):
                return self
            def where(self, w):
                self.wheres.append(w)
                return self
            def to_pandas(self):
                import pandas as pd
                return pd.DataFrame([{"id": "1", "app_type": "slack", "tags": ["sales"]}])

        builder = FakeBuilder()
        with patch.object(mm.connections_table, "search", return_value=builder):
            results = mm.search_communications("hello", app_type="slack", tag="sales")
        assert any(r["id"] == "1" for r in results)
        assert any("slack" in w for w in builder.wheres)
        assert any("array_has_any" in w for w in builder.wheres)
        with patch.object(mm.connections_table, "search", side_effect=RuntimeError("boom")):
            assert mm.search_communications("q") == []

    def test_get_communications_by_app_and_timeframe(self, tmp_path):
        mm = LanceDBMemoryManager(db_path=str(tmp_path), workspace_id="cov3")
        mm.initialize()
        mm.ingest_communication(comm_data(id="1", app_type="slack", content="one"))
        assert any(r["id"] == "1" for r in mm.get_communications_by_app("slack"))
        assert any(r["id"] == "1" for r in mm.get_communications_by_timeframe(
            datetime(2026, 1, 1), datetime(2026, 1, 2)))
        with patch.object(mm.connections_table, "search", side_effect=RuntimeError("boom")):
            assert mm.get_communications_by_app("slack") == []
            assert mm.get_communications_by_timeframe(datetime(2026, 1, 1), datetime(2026, 1, 2)) == []

    def test_update_metadata_both_branches(self, tmp_path):
        mm = LanceDBMemoryManager(db_path=str(tmp_path), workspace_id="cov4")
        mm.initialize()
        mm._update_metadata("slack", 1)
        mm._update_metadata("slack", 2)
        df = mm.metadata_table.search().to_pandas()
        row = df[df["app_type"] == "slack"].iloc[0]
        assert row["total_messages"] == 3

    def test_update_metadata_error(self, tmp_path):
        mm = LanceDBMemoryManager(db_path=str(tmp_path), workspace_id="cov5")
        mm.initialize()
        mm.metadata_table = Mock()
        mm.metadata_table.search = Mock(side_effect=RuntimeError("boom"))
        mm._update_metadata("slack", 1)

    def test_search_hybrid_fallback(self, tmp_path):
        mm = LanceDBMemoryManager(db_path=str(tmp_path), workspace_id="cov6")
        mm.initialize()

        class FakeBuilder:
            def vector(self, v):
                return self
            def text(self, t):
                return self
            def limit(self, n):
                return self
            def where(self, w):
                return self
            def to_pandas(self):
                import pandas as pd
                return pd.DataFrame([{"id": "1", "app_type": "slack", "content": "unique term xyz"}])

        class FallbackBuilder:
            def __init__(self):
                self.query = None
            def vector(self, v):
                self.query = v
                return self
            def text(self, t):
                return self
            def limit(self, n):
                return self
            def where(self, w):
                return self
            def to_pandas(self):
                import pandas as pd
                return pd.DataFrame([{"id": "1", "app_type": "slack", "content": "unique term xyz"}])

        with patch.object(mm.connections_table, "search",
                          side_effect=[TypeError("hybrid not supported"), FallbackBuilder()]):
            results = mm.search_communications("unique term xyz")
        assert any(r["id"] == "1" for r in results)

    def test_ingest_communication_no_table(self):
        mm = LanceDBMemoryManager(db_path="/tmp", workspace_id="cov7")
        assert mm.ingest_communication(comm_data()) is False

    def test_ingest_batch_empty(self):
        mm = LanceDBMemoryManager(db_path="/tmp", workspace_id="cov8")
        assert mm.ingest_batch([]) is False

    def test_get_memory_manager_workspace_isolation(self):
        m1 = get_memory_manager("ws-cov-a")
        m2 = get_memory_manager("ws-cov-a")
        m3 = get_memory_manager("ws-cov-b")
        assert m1 is m2
        assert m1 is not m3

    def test_get_ingestion_pipeline(self):
        pipe = get_ingestion_pipeline("ws-cov-c")
        assert isinstance(pipe, CommunicationIngestionPipeline)
        assert pipe.memory_manager is get_memory_manager("ws-cov-c")


def make_email_message():
    return (
        b"Subject: =?utf-8?q?Hello_World?=\n"
        b"From: a@b.c\nTo: r@x.y\nMessage-ID: <1>\n"
        b"Date: Mon, 1 Jan 2026 10:00:00 +0000\n"
        b"MIME-Version: 1.0\n"
        b"Content-Type: multipart/mixed; boundary=b\n\n"
        b"--b\nContent-Type: text/plain\n\nplain body\n"
        b"--b\nContent-Type: text/plain\nContent-Disposition: attachment; filename=x.txt\n\nattach\n"
        b"--b--\n")


# ============================================================================
# Gap-fill wave — remaining uncovered lines
# ============================================================================

class TestGapFillWhatsApp:
    def _wa(self, **kw):
        cfg = {"access_token": "tok", "phone_number_id": "ph1", "webhook_url": None,
               "enable_enterprise_features": True}
        cfg.update(kw)
        return whatsapp_mod.AtomWhatsAppIntegration(cfg)

    def test_initialize_with_webhook_and_exception_path(self):
        wa = self._wa(webhook_url="https://x/wa")
        with patch.object(wa, "_verify_api_connection", new_callable=AsyncMock), \
             patch.object(wa, "_setup_webhook", new_callable=AsyncMock) as sw, \
             patch.object(wa, "_setup_enterprise_features", new_callable=AsyncMock), \
             patch.object(wa, "_setup_security_and_compliance", new_callable=AsyncMock), \
             patch.object(wa, "_setup_automation", new_callable=AsyncMock), \
             patch.object(wa, "_setup_monitoring", new_callable=AsyncMock), \
             patch.object(wa, "_load_existing_data", new_callable=AsyncMock):
            assert asyncio.run(wa.initialize()) is True
            sw.assert_awaited_once()
        wa2 = self._wa()
        with patch.object(wa2, "_verify_api_connection", new_callable=AsyncMock,
                          side_effect=RuntimeError("boom")):
            assert asyncio.run(wa2.initialize()) is False

    def test_get_intelligent_channels_exception(self):
        wa = self._wa()
        class Boom:
            def __getattr__(self, name):
                raise RuntimeError("boom")
        wa.active_chats = {"c1": Boom()}
        assert asyncio.run(wa.get_intelligent_channels("c1", "u1")) == []

    def test_send_intelligent_message_exception(self):
        wa = self._wa()
        wa.http_session = Mock()
        wa.http_session.post = AsyncMock(side_effect=RuntimeError("boom"))
        result = asyncio.run(wa.send_intelligent_message("+1", "hi"))
        assert result["success"] is False

    def test_perform_intelligent_search_skips_other_workspace(self):
        wa = self._wa()
        msg = SimpleNamespace(message_id="m1", chat_id="c1", user_id="u1",
                              message_type=whatsapp_mod.WhatsAppMessageType.TEXT,
                              content="sales", timestamp=datetime(2026, 1, 1), metadata={})
        wa.message_history = {"c1": [msg]}
        wa.ai_service = None
        assert asyncio.run(wa.perform_intelligent_search("sales", "u1", "other_ws")) == []

    def test_get_user_conversation_history_exception(self):
        wa = self._wa()
        class Boom:
            @property
            def user_id(self):
                raise RuntimeError("boom")
        wa.message_history = {"c1": [Boom()]}
        assert asyncio.run(wa.get_user_conversation_history("u1", "c1")) == []

    def test_setup_enterprise_features_exception(self):
        wa = self._wa()
        wa.enterprise_security = Mock()
        wa.enterprise_automation = Mock()
        with patch.object(wa, "_setup_security_policies", new_callable=AsyncMock,
                          side_effect=RuntimeError("boom")):
            asyncio.run(wa._setup_enterprise_features())

    def test_setup_bodies_and_exception_paths(self):
        wa = self._wa()
        asyncio.run(wa._setup_security_monitoring())
        assert "message_anomaly_detection" in wa.security_monitoring
        asyncio.run(wa._setup_compliance_monitoring())
        assert "message_compliance_checking" in wa.compliance_monitoring
        logger = whatsapp_mod.logger
        with patch.object(logger, "info", side_effect=RuntimeError("boom")):
            asyncio.run(wa._setup_security_policies())
            asyncio.run(wa._setup_compliance_rules())
            asyncio.run(wa._setup_automation_triggers())
            asyncio.run(wa._setup_security_monitoring())
            asyncio.run(wa._setup_compliance_monitoring())
            asyncio.run(wa._setup_monitoring())
            asyncio.run(wa._load_existing_data())

    def test_security_and_compliance_exception(self):
        wa = self._wa()
        with patch.object(wa, "_setup_security_monitoring", new_callable=AsyncMock,
                          side_effect=RuntimeError("boom")):
            asyncio.run(wa._setup_security_and_compliance())

    def test_relevance_score_exception(self):
        wa = self._wa()
        assert wa._calculate_relevance_score(1, "content") == 0.0

    def test_ai_search_empty_result_branch(self):
        wa = self._wa()
        svc = Mock()
        resp = Mock()
        resp.ok = True
        resp.output_data = {}
        svc.process_ai_request = AsyncMock(return_value=resp)
        wa.ai_service = svc
        class _T:
            SEARCH_QUERY = "search"
        class _M:
            GPT_4 = "gpt4"
        class _S:
            OPENAI = "openai"
        with patch.object(whatsapp_mod, "AIRequest", Mock(return_value=Mock())), \
             patch.object(whatsapp_mod, "AITaskType", _T), \
             patch.object(whatsapp_mod, "AIModelType", _M), \
             patch.object(whatsapp_mod, "AIServiceType", _S):
            assert asyncio.run(wa._perform_ai_search("q")) == []

    def test_import_fallbacks_when_optional_modules_missing(self, tmp_path):
        import importlib.util
        import shutil

        pkg = tmp_path / "wapkg"
        pkg.mkdir()
        pkg_mod = types.ModuleType("wapkg")
        pkg_mod.__path__ = [str(pkg)]
        sys.modules["wapkg"] = pkg_mod
        shutil.copy("integrations/atom_whatsapp_integration.py", pkg / "wa_copy.py")
        real_import = builtins.__import__
        blocked = {"numpy", "pandas", "ai_enhanced_service", "atom_slack_integration",
                   "atom_memory_service", "atom_search_service", "atom_workflow_service",
                   "integrations.atom_ai_integration", "integrations.atom_discord_integration",
                   "integrations.atom_enterprise_security_service",
                   "integrations.atom_enterprise_unified_service",
                   "integrations.atom_google_chat_integration",
                   "integrations.atom_ingestion_pipeline",
                   "integrations.atom_teams_integration",
                   "integrations.atom_telegram_integration",
                   "integrations.atom_workflow_automation_service"}

        def _blocked(name, *a, **k):
            if name.split(".")[0] in blocked:
                raise ImportError(f"blocked: {name}")
            return real_import(name, *a, **k)

        spec = importlib.util.spec_from_file_location("wapkg.wa_copy", pkg / "wa_copy.py")
        mod = importlib.util.module_from_spec(spec)
        with patch("builtins.__import__", side_effect=_blocked):
            spec.loader.exec_module(mod)
        assert mod.np is None
        assert mod.AIRequest is None
        assert mod.AtomMemoryService is None
        assert mod.atom_slack_integration is None


class TestGapFillTeams:
    def _svc(self):
        return teams_mod.AtomTeamsIntegration({
            "atom_memory_service": Mock(), "atom_search_service": Mock(),
            "atom_workflow_service": Mock()})

    def test_initialize_exception(self):
        svc = self._svc()
        svc.teams_service = Mock()
        with patch.object(svc, "_start_integration_workers", new_callable=AsyncMock,
                          side_effect=RuntimeError("boom")):
            assert asyncio.run(svc.initialize()) is False

    def test_create_workflow_action_loop_teams_detection(self):
        svc = self._svc()
        svc.atom_workflow = None
        result = asyncio.run(svc.create_unified_workflow({
            "name": "N", "triggers": [], "actions": [{"platform": "microsoft_teams"}]}))
        assert result["ok"] is False

    def test_create_workflow_teams_engine_path(self):
        svc = self._svc()
        engine = Mock()
        engine.register_workflow = Mock(return_value=True)
        twf = Mock()
        twf.id = "twf1"
        with patch.object(teams_mod, "teams_workflow_engine", engine), \
             patch("integrations.atom_teams_integration.TeamsWorkflow", Mock(return_value=twf), create=True), \
             patch("integrations.atom_teams_integration.TeamsWorkflowTrigger", Mock(return_value=Mock()), create=True), \
             patch("integrations.atom_teams_integration.TeamsWorkflowAction", Mock(return_value=Mock()), create=True):
            result = asyncio.run(svc.create_unified_workflow({
                "name": "N", "description": "d", "triggers": [
                    {"platform": "microsoft_teams", "event": "message"},
                    {"platform": "slack", "event": "message"}],
                "actions": [{"platform": "microsoft_teams", "action": "send"}],
                "created_by": "u", "category": "teams", "tags": ["t"]}))
        assert result["ok"] is True
        assert result["workflow_id"] == "twf1"
        engine.register_workflow = Mock(return_value=False)
        with patch.object(teams_mod, "teams_workflow_engine", engine), \
             patch("integrations.atom_teams_integration.TeamsWorkflow", Mock(return_value=twf), create=True), \
             patch("integrations.atom_teams_integration.TeamsWorkflowTrigger", Mock(return_value=Mock()), create=True), \
             patch("integrations.atom_teams_integration.TeamsWorkflowAction", Mock(return_value=Mock()), create=True):
            result2 = asyncio.run(svc.create_unified_workflow({
                "name": "N", "triggers": [{"platform": "microsoft_teams"}], "actions": []}))
        assert result2["ok"] is False

    def test_cross_platform_handler_exceptions(self):
        svc = self._svc()
        with patch.object(svc, "_store_message_in_memory", new_callable=AsyncMock,
                          side_effect=RuntimeError("boom")):
            asyncio.run(svc._handle_teams_message_cross_platform({"message_id": "1"}))
        svc._index_file_in_search = AsyncMock(side_effect=RuntimeError("boom"))
        svc._store_file_in_memory = AsyncMock()
        with patch.object(svc, "_trigger_workflows", new_callable=AsyncMock):
            asyncio.run(svc._handle_teams_file_cross_platform({}))
        svc._update_user_profile_cross_platform = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(svc, "_trigger_workflows", new_callable=AsyncMock):
            asyncio.run(svc._handle_teams_user_event_cross_platform({}))

    def test_generate_search_highlights_exception(self):
        svc = self._svc()
        assert svc._generate_search_highlights(None, "q") == []

    def test_message_ingestion_worker_error_path(self):
        svc = self._svc()
        with patch("asyncio.sleep",
                   AsyncMock(side_effect=[RuntimeError("boom"), asyncio.CancelledError()])):
            with pytest.raises(asyncio.CancelledError):
                asyncio.run(svc._teams_message_ingestion_worker())

    def test_get_unified_messages_returns_empty_for_non_teams(self):
        svc = self._svc()
        assert asyncio.run(svc.get_unified_messages("slack_w", "teams_c1")) == []


class TestGapFillMemoryApi:
    def test_apps_endpoint_exception(self):
        with patch.object(memory_api_mod, "CommunicationAppType", Mock()), pytest.raises(Exception) as exc:
            asyncio.run(route_endpoint(memory_api_mod.AtomCommunicationMemoryAPI().router,
                                       "/api/atom/communication/memory/apps", "GET")())
        assert getattr(exc.value, "status_code", None) == 500

    def test_initialize_called_when_db_none(self):
        mm = Mock()
        mm.db = None
        mm.connections_table = None
        def _init():
            mm.db = Mock()
            mm.db.table_names = Mock(return_value=[])
        mm.initialize = Mock(side_effect=_init)
        with patch.object(memory_api_mod, "memory_manager", mm), \
             patch.object(memory_api_mod, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(return_value={"configured_apps": []})
            asyncio.run(route_endpoint(memory_api_mod.AtomCommunicationMemoryAPI().router,
                                       "/api/atom/communication/memory/status", "GET")())
        mm.initialize.assert_called_once()

    def test_batch_endpoint_exception(self):
        with patch.object(memory_api_mod, "ingestion_pipeline") as pipe, \
             patch.object(memory_api_mod, "memory_manager") as mm:
            mm.db = Mock()
            pipe.ingest_message = AsyncMock(side_effect=RuntimeError("boom"))
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(memory_api_mod.AtomCommunicationMemoryAPI().router,
                                           "/api/atom/communication/memory/ingest/batch")(
                    app_id="slack", messages=[{"id": "1"}]))
        assert getattr(exc.value, "status_code", None) == 500

    def test_search_value_error_and_exception(self):
        mm = Mock()
        mm.db = Mock()
        mm.get_communications_by_timeframe = Mock(side_effect=ValueError("bad date"))
        with patch.object(memory_api_mod, "memory_manager", mm), pytest.raises(Exception) as exc:
            asyncio.run(route_endpoint(memory_api_mod.AtomCommunicationMemoryAPI().router,
                                       "/api/atom/communication/memory/search", "GET")(
                query="q", app_id=None, limit=10, time_start="bad", time_end="bad2", tag=None))
        assert getattr(exc.value, "status_code", None) == 400
        mm.search_communications = Mock(side_effect=RuntimeError("boom"))
        with patch.object(memory_api_mod, "memory_manager", mm), pytest.raises(Exception) as exc2:
            asyncio.run(route_endpoint(memory_api_mod.AtomCommunicationMemoryAPI().router,
                                       "/api/atom/communication/memory/search", "GET")(
                query="q", app_id=None, limit=10, time_start=None, time_end=None, tag=None))
        assert getattr(exc2.value, "status_code", None) == 500

    def test_communications_exception(self):
        mm = Mock()
        mm.db = Mock()
        mm.get_communications_by_app = Mock(side_effect=RuntimeError("boom"))
        with patch.object(memory_api_mod, "memory_manager", mm), pytest.raises(Exception) as exc:
            asyncio.run(route_endpoint(memory_api_mod.AtomCommunicationMemoryAPI().router,
                                       "/api/atom/communication/memory/communications/{app_id}", "GET")(
                app_id="slack", limit=50, time_start=None, time_end=None))
        assert getattr(exc.value, "status_code", None) == 500

    def test_analytics_branch_coverage(self):
        mm = Mock()
        mm.db = Mock()
        table = Mock()
        df = Mock()
        records = [
            {"app_type": "slack", "direction": "inbound", "priority": "normal",
             "status": "active", "timestamp": datetime(2026, 1, 1, 10, 0),
             "metadata": {"thread_id": "t1"}, "subject": "s", "id": "1"},
            {"app_type": "slack", "direction": "outbound", "priority": "normal",
             "status": "active", "timestamp": "2026-01-01T10:00:30",
             "metadata": json.dumps({"thread_id": "t1"}), "subject": "s", "id": "2"},
            {"app_type": "slack", "direction": "inbound", "priority": "normal",
             "status": "active", "timestamp": "2026-01-01T11:00:00",
             "metadata": "{}", "subject": "s3", "id": "3"},
            {"app_type": "slack", "direction": "inbound", "priority": "normal",
             "status": "active", "timestamp": "2026-01-01T12:00:00",
             "metadata": "{}", "subject": None, "id": "4"},
            {"app_type": "slack", "direction": "inbound", "priority": "normal",
             "status": "active", "timestamp": "2026-01-01T13:00:00",
             "metadata": "bad-json{", "subject": "s5", "id": "5"},
        ]
        df.to_dict = Mock(return_value=records)
        table.to_pandas = Mock(return_value=df)
        mm.connections_table = table
        with patch.object(memory_api_mod, "memory_manager", mm), \
             patch.object(memory_api_mod, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(return_value={"configured_apps": []})
            result = asyncio.run(route_endpoint(memory_api_mod.AtomCommunicationMemoryAPI().router,
                                                "/api/atom/communication/memory/analytics", "GET")(
                time_start=None, time_end=None))
        assert result["analytics"]["performance"]["total_responses"] == 1
        # 30s response time → "30s" format; second: subj_ group; third: ungrouped id
        assert result["analytics"]["performance"]["avg_response_time"] == "30s"

    def test_analytics_error_paths(self):
        mm = Mock()
        mm.db = Mock()
        mm.connections_table = None
        with patch.object(memory_api_mod, "memory_manager", mm), \
             patch.object(memory_api_mod, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(side_effect=ValueError("bad"))
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(memory_api_mod.AtomCommunicationMemoryAPI().router,
                                           "/api/atom/communication/memory/analytics", "GET")(
                    time_start=None, time_end=None))
        assert getattr(exc.value, "status_code", None) == 400

    def test_configure_endpoint_exception(self):
        config = pipeline_mod.IngestionConfig(
            app_type=CommunicationAppType.SLACK, enabled=True, real_time=True,
            batch_size=10, ingest_attachments=True, embed_content=True, retention_days=30)
        with patch.object(memory_api_mod, "ingestion_pipeline") as pipe:
            pipe.configure_app = Mock(side_effect=RuntimeError("boom"))
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(memory_api_mod.AtomCommunicationMemoryAPI().router,
                                           "/api/atom/communication/memory/configure")(
                    app_id="slack", config=config))
        assert getattr(exc.value, "status_code", None) == 500


class TestGapFillProductionApi:
    def test_verify_token_passthrough(self):
        api = prod_api_mod.AtomCommunicationMemoryProductionAPI()
        assert api.verify_token({"sub": "u"}) == {"sub": "u"}

    def test_batch_value_error_and_exception(self):
        with patch.object(prod_api_mod, "ingestion_pipeline") as pipe, \
             patch.object(prod_api_mod, "memory_manager") as mm:
            mm.db = Mock()
            pipe.ingest_message = AsyncMock(return_value=True)
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(prod_api_mod.AtomCommunicationMemoryProductionAPI().router,
                                           "/api/atom/communication/memory/ingest/batch")(
                    app_id="nope", messages=[{"id": "1"}], token={"sub": "u"}))
            assert getattr(exc.value, "status_code", None) == 404
            pipe.ingest_message = AsyncMock(side_effect=RuntimeError("boom"))
            with pytest.raises(Exception) as exc2:
                asyncio.run(route_endpoint(prod_api_mod.AtomCommunicationMemoryProductionAPI().router,
                                           "/api/atom/communication/memory/ingest/batch")(
                    app_id="slack", messages=[{"id": "1"}], token={"sub": "u"}))
            assert getattr(exc2.value, "status_code", None) == 500

    def test_search_include_metadata_and_errors(self):
        mm = Mock()
        mm.db = Mock()
        mm.search_communications = Mock(return_value=[{"id": "1", "content": "c", "metadata": {}}])
        with patch.object(prod_api_mod, "memory_manager", mm):
            result = asyncio.run(route_endpoint(prod_api_mod.AtomCommunicationMemoryProductionAPI().router,
                                                "/api/atom/communication/memory/search/production", "GET")(
                query="q", app_id=None, limit=10, time_start=None, time_end=None,
                include_metadata=True, token={"sub": "u"}))
        assert result["total_results"] == 1
        mm.get_communications_by_timeframe = Mock(side_effect=ValueError("bad date"))
        with patch.object(prod_api_mod, "memory_manager", mm), pytest.raises(Exception) as exc:
            asyncio.run(route_endpoint(prod_api_mod.AtomCommunicationMemoryProductionAPI().router,
                                       "/api/atom/communication/memory/search/production", "GET")(
                query="q", app_id=None, limit=10, time_start="bad", time_end="bad",
                include_metadata=True, token={"sub": "u"}))
        assert getattr(exc.value, "status_code", None) == 400
        mm.search_communications = Mock(side_effect=RuntimeError("boom"))
        with patch.object(prod_api_mod, "memory_manager", mm), pytest.raises(Exception) as exc2:
            asyncio.run(route_endpoint(prod_api_mod.AtomCommunicationMemoryProductionAPI().router,
                                       "/api/atom/communication/memory/search/production", "GET")(
                query="q", app_id=None, limit=10, time_start=None, time_end=None,
                include_metadata=True, token={"sub": "u"}))
        assert getattr(exc2.value, "status_code", None) == 500

    def test_analytics_attachment_and_storage_errors(self, tmp_path):
        mm = Mock()
        mm.db = Mock()
        table = Mock()
        df = Mock()
        records = [
            {"app_type": "slack", "direction": "inbound", "priority": "high",
             "status": "active", "timestamp": "2026-01-01T10:00:00", "content": "x" * 100,
             "attachments": "not-json"},
            {"app_type": "slack", "direction": "inbound", "priority": "high",
             "status": "active", "timestamp": "2026-01-01T10:00:00", "content": "y" * 100,
             "attachments": json.dumps([{"id": 1}])},
        ]
        df.to_dict = Mock(return_value=records)
        table.to_pandas = Mock(return_value=df)
        mm.connections_table = table
        mm.db_path = str(tmp_path)
        (tmp_path / "a.bin").write_bytes(b"12345678")
        with patch.object(prod_api_mod, "memory_manager", mm), \
             patch.object(prod_api_mod, "ingestion_pipeline") as pipe, \
             patch("os.walk", side_effect=RuntimeError("fs error")):
            pipe.get_ingestion_stats = Mock(return_value={"configured_apps": []})
            result = asyncio.run(route_endpoint(prod_api_mod.AtomCommunicationMemoryProductionAPI().router,
                                                "/api/atom/communication/memory/analytics/production", "GET")(
                time_start=None, time_end=None, app_id=None,
                include_detailed_metrics=True, token={"sub": "u"}))
        assert result["analytics"]["detailed_metrics"]["total_attachments"] == 1
        assert result["analytics"]["detailed_metrics"]["storage_efficiency"]

    def test_analytics_value_error_and_exception(self):
        mm = Mock()
        mm.db = Mock()
        mm.connections_table = None
        with patch.object(prod_api_mod, "memory_manager", mm), \
             patch.object(prod_api_mod, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(side_effect=ValueError("bad"))
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(prod_api_mod.AtomCommunicationMemoryProductionAPI().router,
                                           "/api/atom/communication/memory/analytics/production", "GET")(
                    time_start=None, time_end=None, app_id=None,
                    include_detailed_metrics=True, token={"sub": "u"}))
        assert getattr(exc.value, "status_code", None) == 400
        with patch.object(prod_api_mod, "memory_manager", mm), \
             patch.object(prod_api_mod, "ingestion_pipeline") as pipe2, \
             pytest.raises(Exception) as exc2:
            pipe2.get_ingestion_stats = Mock(side_effect=RuntimeError("boom"))
            asyncio.run(route_endpoint(prod_api_mod.AtomCommunicationMemoryProductionAPI().router,
                                       "/api/atom/communication/memory/analytics/production", "GET")(
                time_start=None, time_end=None, app_id=None,
                include_detailed_metrics=True, token={"sub": "u"}))
        assert getattr(exc2.value, "status_code", None) == 500


class TestGapFillWebhooks:
    def test_verify_token_method(self):
        assert webhooks_mod.verify_token({"sub": "u"}) == {"sub": "u"}

    def test_whatsapp_missing_header(self, monkeypatch):
        monkeypatch.setenv("ATOM_WHATSAPP_WEBHOOK_SECRET", "w")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/whatsapp")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                 x_hub_signature_256=None, token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_slack_invalid_json_500(self, monkeypatch):
        monkeypatch.setenv("ATOM_SLACK_WEBHOOK_SECRET", "s")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/slack")
        import hashlib, hmac
        body = b"bad-json{"
        ts = str(int(time.time()))
        sig = "v0=" + hmac.new(b"s", f"v0:{ts}:".encode() + body, hashlib.sha256).hexdigest()
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(body), background_tasks=Mock(),
                                 x_slack_signature=sig, x_slack_request_timestamp=ts, token={}))
        assert getattr(exc.value, "status_code", None) == 500

    def test_discord_missing_header(self, monkeypatch):
        monkeypatch.setenv("ATOM_DISCORD_WEBHOOK_SECRET", "d")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/discord")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                 x_signature_ed25519=None, x_signature_timestamp=None, token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_discord_invalid_json_500(self, monkeypatch):
        monkeypatch.setenv("ATOM_DISCORD_WEBHOOK_SECRET", "d")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/discord")
        import hashlib, hmac
        body = b"bad{"
        sig = hmac.new(b"d", body, hashlib.sha256).hexdigest()
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(body), background_tasks=Mock(),
                                 x_signature_ed25519=sig, x_signature_timestamp="123", token={}))
        assert getattr(exc.value, "status_code", None) == 500

    def test_telegram_missing_header(self, monkeypatch):
        monkeypatch.setenv("ATOM_TELEGRAM_WEBHOOK_SECRET", "t")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/telegram")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                 x_telegram_bot_api_secret_token=None, token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_telegram_invalid_json_500(self, monkeypatch):
        monkeypatch.setenv("ATOM_TELEGRAM_WEBHOOK_SECRET", "t")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/telegram")
        import hashlib, hmac
        body = b"bad{"
        sig = hmac.new(b"t", body, hashlib.sha256).hexdigest()
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(body), background_tasks=Mock(),
                                 x_telegram_bot_api_secret_token=sig, token={}))
        assert getattr(exc.value, "status_code", None) == 500

    def test_gmail_and_outlook_missing_header(self, monkeypatch):
        monkeypatch.setenv("ATOM_GMAIL_WEBHOOK_SECRET", "g")
        monkeypatch.setenv("ATOM_OUTLOOK_WEBHOOK_SECRET", "o")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        gendpoint = route_endpoint(wh.router, "/api/webhooks/communication/gmail")
        with pytest.raises(Exception) as exc:
            asyncio.run(gendpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                  x_atom_webhook_secret=None, token={}))
        assert getattr(exc.value, "status_code", None) == 401
        oendpoint = route_endpoint(wh.router, "/api/webhooks/communication/outlook")
        with pytest.raises(Exception) as exc2:
            asyncio.run(oendpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                  x_atom_webhook_secret=None, token={}))
        assert getattr(exc2.value, "status_code", None) == 401

    def test_gmail_invalid_json_500(self, monkeypatch):
        monkeypatch.setenv("ATOM_GMAIL_WEBHOOK_SECRET", "g")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/gmail")
        import hashlib, hmac
        body = b"bad{"
        sig = hmac.new(b"g", body, hashlib.sha256).hexdigest()
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(body), background_tasks=Mock(),
                                 x_atom_webhook_secret=sig, token={}))
        assert getattr(exc.value, "status_code", None) == 500

    def test_outlook_invalid_json_500(self, monkeypatch):
        monkeypatch.setenv("ATOM_OUTLOOK_WEBHOOK_SECRET", "o")
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/outlook")
        import hashlib, hmac
        body = b"bad{"
        sig = hmac.new(b"o", body, hashlib.sha256).hexdigest()
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(body), background_tasks=Mock(),
                                 x_atom_webhook_secret=sig, token={}))
        assert getattr(exc.value, "status_code", None) == 500

    @pytest.mark.parametrize("name,payload", [
        ("_process_whatsapp_webhook", {"entry": []}),
        ("_process_discord_webhook", {"message": {"id": "1"}}),
        ("_process_telegram_webhook", {"message": {"message_id": 1}}),
        ("_process_gmail_webhook", {"message": {"id": "1"}}),
        ("_process_outlook_webhook", {"value": [{"id": "1"}]}),
    ])
    def test_processor_exception_paths(self, name, payload):
        wh = webhooks_mod.AtomCommunicationMemoryWebhooks()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(side_effect=RuntimeError("boom"))
            asyncio.run(getattr(wh, name)(payload))


class TestGapFillLanceDBIntegration:
    def test_apps_endpoint_exception(self):
        with patch.object(lancedb_intgr, "CommunicationAppType", Mock()), pytest.raises(Exception) as exc:
            asyncio.run(route_endpoint(lancedb_intgr.CommunicationAppIngestionIntegration().router,
                                       "/api/memory/ingestion/apps", "GET")())
        assert getattr(exc.value, "status_code", None) == 500

    def test_app_config_exception(self):
        with patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.ingestion_configs = Mock()
            pipe.ingestion_configs.get = Mock(side_effect=RuntimeError("boom"))
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(lancedb_intgr.CommunicationAppIngestionIntegration().router,
                                           "/api/memory/ingestion/apps/{app_id}", "GET")(app_id="slack"))
        assert getattr(exc.value, "status_code", None) == 500

    def test_ingest_batch_exception(self):
        with patch.object(lancedb_intgr, "ingestion_pipeline") as pipe, \
             patch.object(lancedb_intgr, "memory_manager") as mm:
            mm.db = Mock()
            pipe.ingest_message = AsyncMock(side_effect=RuntimeError("boom"))
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(lancedb_intgr.CommunicationAppIngestionIntegration().router,
                                           "/api/memory/ingestion/ingest/{app_id}/batch")(
                    app_id="slack", messages=[{"id": "1"}]))
        assert getattr(exc.value, "status_code", None) == 500

    def test_initialize_branches_and_search_success(self):
        mm = Mock()
        mm.db = None
        mm.initialize = Mock()
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            asyncio.run(route_endpoint(lancedb_intgr.CommunicationAppIngestionIntegration().router,
                                       "/api/memory/ingestion/ingest/{app_id}")(
                app_id="slack", message_data={"id": "1"}))
            mm.initialize.assert_called_once()
        mm2 = Mock()
        mm2.db = Mock()
        mm2.search_communications = Mock(return_value=[{"id": "1"}])
        with patch.object(lancedb_intgr, "memory_manager", mm2):
            result = asyncio.run(route_endpoint(lancedb_intgr.CommunicationAppIngestionIntegration().router,
                                                "/api/memory/ingestion/search", "GET")(query="q"))
        assert result["total_results"] == 1

    def test_stream_start_initialize_and_invalid(self):
        mm = Mock()
        mm.db = None
        mm.initialize = Mock()
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.start_real_time_stream = Mock(return_value=True)
            asyncio.run(route_endpoint(lancedb_intgr.CommunicationAppIngestionIntegration().router,
                                       "/api/memory/ingestion/stream/start/{app_id}")(app_id="slack"))
            mm.initialize.assert_called_once()
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(lancedb_intgr.CommunicationAppIngestionIntegration().router,
                                           "/api/memory/ingestion/stream/start/{app_id}")(app_id="nope"))
            assert getattr(exc.value, "status_code", None) == 404

    def test_communications_initialize_and_errors(self):
        mm = Mock()
        mm.db = None
        mm.initialize = Mock()
        mm.get_communications_by_app = Mock(return_value=[{"app_type": "slack"}])
        with patch.object(lancedb_intgr, "memory_manager", mm):
            result = asyncio.run(route_endpoint(lancedb_intgr.CommunicationAppIngestionIntegration().router,
                                                "/api/memory/ingestion/communications/{app_id}", "GET")(
                app_id="slack", limit=100))
            assert result["total_results"] == 1
            mm.initialize.assert_called_once()
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(lancedb_intgr.CommunicationAppIngestionIntegration().router,
                                           "/api/memory/ingestion/communications/{app_id}", "GET")(
                    app_id="nope", limit=100))
            assert getattr(exc.value, "status_code", None) == 404
        mm.get_communications_by_app = Mock(side_effect=RuntimeError("boom"))
        mm.db = Mock()
        with patch.object(lancedb_intgr, "memory_manager", mm), pytest.raises(Exception) as exc2:
            asyncio.run(route_endpoint(lancedb_intgr.CommunicationAppIngestionIntegration().router,
                                       "/api/memory/ingestion/communications/{app_id}", "GET")(
                app_id="slack", limit=100))
        assert getattr(exc2.value, "status_code", None) == 500

    def test_timeline_generic_exception(self):
        mm = Mock()
        mm.db = Mock()
        mm.get_communications_by_timeframe = Mock(side_effect=RuntimeError("boom"))
        with patch.object(lancedb_intgr, "memory_manager", mm), pytest.raises(Exception) as exc:
            asyncio.run(route_endpoint(lancedb_intgr.CommunicationAppIngestionIntegration().router,
                                       "/api/memory/ingestion/communications/timeline", "GET")(
                start_date="2026-01-01", end_date="2026-01-02", app_id=None))
        assert getattr(exc.value, "status_code", None) == 500

    def test_memory_stats_initialize(self):
        mm = Mock()
        mm.db = None
        mm.connections_table = None
        def _init():
            mm.db = Mock()
            mm.db.table_names = Mock(return_value=[])
        mm.initialize = Mock(side_effect=_init)
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(return_value={"configured_apps": []})
            asyncio.run(route_endpoint(lancedb_intgr.CommunicationAppIngestionIntegration().router,
                                       "/api/memory/ingestion/memory/stats", "GET")())
            mm.initialize.assert_called_once()


class TestGapFillLiveApi:
    def test_fetch_zoho_outlook_teams_no_token(self, monkeypatch):
        monkeypatch.setattr(comm_live, "ZOHO_MAIL_AVAILABLE", True)
        monkeypatch.setattr(comm_live, "M365_AVAILABLE", True)
        monkeypatch.delenv("ZOHO_CRM_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("MICROSOFT_365_ACCESS_TOKEN", raising=False)
        assert asyncio.run(comm_live.fetch_zoho_mail_recent()) == []
        assert asyncio.run(comm_live.fetch_outlook_recent()) == []
        assert asyncio.run(comm_live.fetch_teams_recent()) == []

    def test_recent_contacts_per_provider_errors_and_success(self, monkeypatch):
        monkeypatch.setattr(comm_live, "SLACK_AVAILABLE", True)
        monkeypatch.setattr(comm_live, "GMAIL_AVAILABLE", True)
        monkeypatch.setattr(comm_live, "DISCORD_AVAILABLE", True)
        monkeypatch.setattr(comm_live, "ZOHO_MAIL_AVAILABLE", True)
        monkeypatch.setattr(comm_live, "M365_AVAILABLE", True)
        with patch("integrations.atom_communication_live_api.fetch_slack_recent",
                   AsyncMock(side_effect=RuntimeError("slack down"))), \
             patch("integrations.atom_communication_live_api.fetch_gmail_recent",
                   AsyncMock(return_value=[{"sender": "gm@x.com"}]), create=True), \
             patch("integrations.atom_communication_live_api.fetch_discord_recent",
                   AsyncMock(return_value=[{"sender": "dc@x.com"}]), create=True), \
             patch("integrations.atom_communication_live_api.fetch_zoho_mail_recent",
                   AsyncMock(side_effect=RuntimeError("zoho down"))), \
             patch("integrations.atom_communication_live_api.fetch_outlook_recent",
                   AsyncMock(side_effect=RuntimeError("outlook down"))), \
             patch("integrations.atom_communication_live_api.fetch_teams_recent",
                   AsyncMock(side_effect=RuntimeError("teams down"))):
            result = asyncio.run(comm_live.get_recent_contacts(limit=10))
        senders = {c["name"] for c in result["contacts"]}
        assert {"gm@x.com", "dc@x.com"} <= senders


class TestGapFillSmall:
    def test_sales_live_provider_exceptions(self, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        monkeypatch.setenv("SALESFORCE_ACCESS_TOKEN", "t")
        monkeypatch.setenv("SALESFORCE_INSTANCE_URL", "https://x")
        monkeypatch.setenv("ZOHO_CRM_ACCESS_TOKEN", "z")
        monkeypatch.setenv("MICROSOFT_365_ACCESS_TOKEN", "ms")
        with patch.object(sales_mod, "get_hubspot_service") as hsvc, \
             patch.object(sales_mod, "token_storage") as ts, \
             patch.object(sales_mod, "ZohoCRMService") as zcls, \
             patch.object(sales_mod, "microsoft365_service") as msvc:
            ts.get_token = Mock(return_value={"access_token": "t", "instance_url": "https://x"})
            sf = Mock()
            sf.query_all = Mock(side_effect=RuntimeError("sf down"))
            with patch.object(sales_mod, "create_client_with_token", return_value=sf):
                pass
            hsvc.return_value.get_deals = AsyncMock(return_value=[])
            zcls.return_value.get_deals = AsyncMock(side_effect=RuntimeError("zoho down"))
            msvc.get_dynamics_deals = AsyncMock(side_effect=RuntimeError("ms down"))
            with patch.object(sales_mod, "create_client_with_token", return_value=sf):
                result = asyncio.run(sales_mod.get_live_pipeline(limit=10))
        assert result.providers["salesforce"] is False
        assert result.providers["zoho"] is False
        assert result.providers["dynamics"] is False

    def test_projects_live_provider_exceptions(self, monkeypatch):
        monkeypatch.setenv("ASANA_ACCESS_TOKEN", "a")
        monkeypatch.setenv("ZOHO_CRM_ACCESS_TOKEN", "z")
        monkeypatch.setenv("ZOHO_PROJECTS_PORTAL_ID", "p")
        monkeypatch.setenv("MICROSOFT_365_ACCESS_TOKEN", "ms")
        with patch.object(projects_mod, "asana_service") as asvc, \
             patch.object(projects_mod, "get_jira_service", return_value=None), \
             patch.object(projects_mod, "ZohoProjectsService") as zcls, \
             patch.object(projects_mod, "microsoft365_service") as msvc:
            asvc.get_tasks = AsyncMock(side_effect=RuntimeError("asana down"))
            zcls.return_value.get_all_active_tasks = AsyncMock(side_effect=RuntimeError("zoho down"))
            msvc.get_planner_tasks = AsyncMock(side_effect=RuntimeError("ms down"))
            result = asyncio.run(projects_mod.get_live_project_board(limit=10))
        assert result.providers["asana"] is False
        assert result.providers["zoho"] is False
        assert result.providers["planner"] is False

    def test_finance_xero_and_dynamics_exceptions(self, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        monkeypatch.setenv("XERO_ACCESS_TOKEN", "x")
        monkeypatch.setenv("MICROSOFT_365_ACCESS_TOKEN", "ms")
        with patch("integrations.xero_service.XeroService") as xcls, \
             patch.object(finance_mod, "microsoft365_service") as msvc:
            xcls.return_value.get_invoices = AsyncMock(side_effect=RuntimeError("xero down"))
            msvc.get_dynamics_invoices = AsyncMock(side_effect=RuntimeError("ms down"))
            result = asyncio.run(finance_mod.get_live_financial_overview(limit=10))
        assert result.providers["xero"] is False
        assert result.providers["dynamics"] is False

    def test_sales_memory_broadcast_failure(self):
        pipe = SalesMemoryPipeline(workspace_id="ws1")
        pipe.memory_manager = Mock()
        with patch("integrations.atom_sales_memory_pipeline.manager") as mgr:
            mgr.broadcast_event = AsyncMock(side_effect=RuntimeError("ws down"))
            asyncio.run(pipe.run_pipeline())

    def test_sales_memory_list_deals_shape(self, monkeypatch):
        monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "t")
        pipe = SalesMemoryPipeline(workspace_id="ws1")
        pipe.memory_manager = Mock()
        pipe.memory_manager.ingest_communication = Mock(return_value=True)
        with patch("integrations.atom_sales_memory_pipeline.get_hubspot_service") as gf:
            gf.return_value.get_deals = AsyncMock(return_value=[
                {"id": "d1", "properties": {"dealname": "D", "amount": "1", "dealstage": "s"}}])
            asyncio.run(pipe._ingest_hubspot())
        pipe.memory_manager.ingest_communication.assert_called_once()


class TestGapFillImportBranches:
    def test_live_api_unavailable_flags(self, monkeypatch):
        monkeypatch.setattr(comm_live, "SLACK_AVAILABLE", False)
        monkeypatch.setattr(comm_live, "ZOHO_MAIL_AVAILABLE", False)
        monkeypatch.setattr(comm_live, "M365_AVAILABLE", False)
        assert asyncio.run(comm_live.fetch_slack_recent()) == []
        assert asyncio.run(comm_live.fetch_zoho_mail_recent()) == []
        assert asyncio.run(comm_live.fetch_outlook_recent()) == []
        assert asyncio.run(comm_live.fetch_teams_recent()) == []

    def test_whatsapp_intelligent_search_exception(self):
        wa = whatsapp_mod.AtomWhatsAppIntegration({
            "access_token": "tok", "phone_number_id": "ph1"})
        wa.ai_service = None
        class Boom:
            @property
            def content(self):
                raise RuntimeError("boom")
        wa.message_history = {"c1": [Boom()]}
        assert asyncio.run(wa.perform_intelligent_search("q", "u1")) == []

    def test_reload_live_api_import_fallbacks(self):
        # Re-import the real module with every optional provider blocked so the
        # ImportError fallback branches execute, then restore via clean reload.
        import importlib
        real_import = builtins.__import__
        blocked = {"integrations.slack_service_unified", "integrations.discord_service",
                   "integrations.gmail_service", "integrations.zoho_mail_service",
                   "integrations.microsoft365_service"}

        def _blocked(name, *a, **k):
            if name in blocked:
                raise ImportError(f"blocked: {name}")
            return real_import(name, *a, **k)

        with patch("builtins.__import__", side_effect=_blocked):
            mod = importlib.reload(comm_live)
        assert mod.SLACK_AVAILABLE is False
        assert mod.DISCORD_AVAILABLE is False
        assert mod.GMAIL_AVAILABLE is False
        assert mod.ZOHO_MAIL_AVAILABLE is False
        assert mod.M365_AVAILABLE is False
        # Restore the fully-loaded module for the rest of the suite
        importlib.reload(comm_live)
        assert comm_live.SLACK_AVAILABLE is True

    def test_reload_teams_import_fallback(self):
        import importlib
        real_import = builtins.__import__
        blocked = {"integrations.teams_enhanced_service"}

        def _blocked(name, *a, **k):
            if name in blocked:
                raise ImportError(f"blocked: {name}")
            return real_import(name, *a, **k)

        with patch("builtins.__import__", side_effect=_blocked):
            mod = importlib.reload(teams_mod)
        assert mod.teams_enhanced_service is None
        importlib.reload(teams_mod)
        assert teams_mod.teams_enhanced_service is not None

    def test_reload_ingestion_pipeline_import_fallback(self):
        import importlib
        real_import = builtins.__import__
        blocked = {"core.lancedb_handler"}

        def _blocked(name, *a, **k):
            if name in blocked:
                raise ImportError(f"blocked: {name}")
            return real_import(name, *a, **k)

        with patch("builtins.__import__", side_effect=_blocked):
            import importlib as il
            from integrations import atom_ingestion_pipeline as aip
            mod = il.reload(aip)
        assert mod.AtomIngestionPipeline is not None
        importlib.reload(aip)
        assert aip.AtomIngestionPipeline is not None

    def test_reload_whatsapp_import_fallbacks(self):
        import importlib
        if not isinstance(whatsapp_mod, types.ModuleType) or \
                sys.modules.get("integrations.atom_whatsapp_integration") is not whatsapp_mod:
            # Another suite (test_proactive_messaging_minimal) replaces
            # sys.modules['integrations.atom_whatsapp_integration'] with a
            # MagicMock at import time — cannot reload a mock.
            pytest.skip("whatsapp module replaced by sys.modules mock from another suite")
        real_import = builtins.__import__
        blocked = {"numpy", "pandas", "ai_enhanced_service", "atom_slack_integration",
                   "atom_memory_service", "atom_search_service", "atom_workflow_service",
                   "integrations.atom_ai_integration", "integrations.atom_discord_integration",
                   "integrations.atom_enterprise_security_service",
                   "integrations.atom_enterprise_unified_service",
                   "integrations.atom_google_chat_integration",
                   "integrations.atom_ingestion_pipeline",
                   "integrations.atom_teams_integration",
                   "integrations.atom_telegram_integration",
                   "integrations.atom_workflow_automation_service"}

        def _blocked(name, *a, **k):
            if name in blocked or name.split(".")[0] in blocked:
                raise ImportError(f"blocked: {name}")
            return real_import(name, *a, **k)

        with patch("builtins.__import__", side_effect=_blocked):
            mod = importlib.reload(whatsapp_mod)
        assert mod.np is None
        assert mod.AIRequest is None
        assert mod.atom_slack_integration is None
        assert mod.atom_ai_integration is None
        assert mod.atom_discord_integration is None
        assert mod.atom_google_chat_integration is None
        assert mod.atom_teams_integration is None
        assert mod.atom_telegram_integration is None
        assert mod.AtomIngestionPipeline is None
        assert mod.atom_enterprise_unified_service is None
        # Restore the fully-loaded module
        importlib.reload(whatsapp_mod)
        assert whatsapp_mod.atom_enterprise_security_service is not None
        assert whatsapp_mod.atom_teams_integration is not None
