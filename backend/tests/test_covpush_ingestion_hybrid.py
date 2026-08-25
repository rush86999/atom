# -*- coding: utf-8 -*-
"""
Coverage-push tests for core/hybrid_data_ingestion.py.

TDD target: routine DEBUG messages logged at ERROR level in __init__ and
enable_auto_sync pollute error logs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.hybrid_data_ingestion as hdi
from core.hybrid_data_ingestion import (
    HybridDataIngestionService,
    SyncConfiguration,
    SyncMode,
)


class _FakeSession:
    def __init__(self, token=None):
        self.token = token
        self.closed = 0

    def query(self, model):
        q = MagicMock()
        q.filter.return_value.first.return_value = self.token
        return q

    def close(self):
        self.closed += 1


@pytest.fixture
def hybrid_factory(monkeypatch):
    fake_memory = MagicMock()
    fake_graphrag = MagicMock()
    # Bug-fix alignment: sync_integration_data awaits graphrag.ingest_document
    # (it is a coroutine); the mock must be awaitable or every record errors.
    fake_graphrag.ingest_document = AsyncMock(return_value=None)
    fake_llm = MagicMock()
    monkeypatch.setattr("core.lancedb_handler.get_lancedb_handler", lambda *a, **k: fake_memory)
    monkeypatch.setattr("core.graphrag_engine.GraphRAGEngine", lambda *a, **k: fake_graphrag)
    monkeypatch.setattr("core.llm_service.get_llm_service", lambda *a, **k: fake_llm)
    return {"memory": fake_memory, "graphrag": fake_graphrag, "llm": fake_llm}


@pytest.fixture
def hybrid(hybrid_factory):
    return HybridDataIngestionService(workspace_id="ws-h", tenant_id="t-h")


class TestSyncConfig:
    def test_sync_mode_enum_values(self):
        assert SyncMode.INCREMENTAL == "incremental"
        assert SyncMode.FULL == "full"
        assert SyncMode.DISCOVERY == "discovery"
        assert SyncMode.HYBRID == "hybrid"

    def test_sync_configuration_defaults(self):
        config = SyncConfiguration(integration_id="slack")
        assert config.entity_types == []
        assert config.sync_last_n_days == 30
        assert config.max_records_per_sync == 1000

    def test_default_sync_configs_present(self):
        for integration in ["salesforce", "hubspot", "slack", "gmail", "notion", "zoho"]:
            assert integration in hdi.DEFAULT_SYNC_CONFIGS


class TestHybridUsageStats:
    def test_record_usage_new(self, hybrid):
        hybrid.record_integration_usage("slack", "Slack")
        stats = hybrid.usage_stats["slack"]
        assert stats.total_calls == 1
        assert stats.successful_calls == 1
        assert stats.last_used is not None

    def test_record_usage_existing_and_failed(self, hybrid):
        hybrid.record_integration_usage("slack", "Slack")
        hybrid.record_integration_usage("slack", "Slack", success=False)
        stats = hybrid.usage_stats["slack"]
        assert stats.total_calls == 2
        assert stats.successful_calls == 1

    def test_check_auto_enable_missing_stats(self, hybrid):
        assert hybrid._check_auto_enable_sync("nope") is None

    def test_check_auto_enable_below_threshold(self, hybrid):
        for _ in range(5):
            hybrid.record_integration_usage("hubspot", "HubSpot")
        assert hybrid.usage_stats["hubspot"].auto_sync_enabled is False

    def test_check_auto_enable_above_threshold(self, hybrid):
        for _ in range(11):
            hybrid.record_integration_usage("hubspot", "HubSpot")
        assert hybrid.usage_stats["hubspot"].auto_sync_enabled is True
        assert "hubspot" in hybrid.sync_configs

    def test_enable_auto_sync_custom_config(self, hybrid):
        config = SyncConfiguration(integration_id="jira", entity_types=["issues"])
        hybrid.enable_auto_sync("jira", config)
        assert hybrid.usage_stats["jira"].auto_sync_enabled is True
        assert hybrid.sync_configs["jira"] is config

    def test_enable_auto_sync_default_config(self, hybrid):
        hybrid.enable_auto_sync("salesforce")
        assert hybrid.sync_configs["salesforce"].entity_types == [
            "contacts",
            "leads",
            "opportunities",
            "accounts",
        ]

    def test_enable_auto_sync_unknown_basic_config(self, hybrid):
        hybrid.enable_auto_sync("mystery_app")
        assert hybrid.sync_configs["mystery_app"].entity_types == ["records"]
        assert hybrid.sync_configs["mystery_app"].sync_last_n_days == 30

    def test_disable_auto_sync(self, hybrid):
        hybrid.enable_auto_sync("slack")
        task = MagicMock()
        hybrid._sync_tasks["slack"] = task
        hybrid.disable_auto_sync("slack")
        assert hybrid.usage_stats["slack"].auto_sync_enabled is False
        task.cancel.assert_called_once()
        assert "slack" not in hybrid._sync_tasks

    def test_disable_auto_sync_untracked(self, hybrid):
        hybrid.disable_auto_sync("nope")
        assert "nope" not in hybrid.usage_stats

    def test_get_usage_summary(self, hybrid):
        hybrid.record_integration_usage("slack", "Slack")
        hybrid.enable_auto_sync("hubspot")
        summary = hybrid.get_usage_summary()
        assert summary["workspace_id"] == "ws-h"
        assert len(summary["integrations"]) == 2
        assert summary["auto_sync_enabled_count"] == 1
        hubspot = [i for i in summary["integrations"] if i["id"] == "hubspot"][0]
        assert hubspot["entity_types"] == ["contacts", "companies", "deals", "tickets"]

    def test_get_usage_summary_last_used(self, hybrid):
        hybrid.record_integration_usage("slack", "Slack")
        summary = hybrid.get_usage_summary()
        assert summary["integrations"][0]["last_used"] is not None

    def test_init_no_debug_error_logs(self, hybrid_factory, caplog):
        import logging

        with caplog.at_level(logging.ERROR):
            HybridDataIngestionService(workspace_id="ws-q", tenant_id="t-q")
        assert not any("DEBUG:" in r.message for r in caplog.records)

    def test_enable_auto_sync_no_debug_error_logs(self, hybrid, caplog):
        import logging

        with caplog.at_level(logging.ERROR):
            hybrid.enable_auto_sync("salesforce")
        assert not any("DEBUG:" in r.message for r in caplog.records)


class TestHybridModule:
    def test_record_integration_call_module(self, hybrid_factory):
        original = hdi._ingestion_service
        try:
            hdi._ingestion_service = None
            hdi.record_integration_call("slack", "Slack")
            assert hdi._ingestion_service is not None
            assert hdi._ingestion_service.usage_stats["slack"].total_calls == 1
        finally:
            hdi._ingestion_service = original

    def test_get_hybrid_ingestion_service_singleton(self, hybrid_factory):
        original = hdi._ingestion_service
        try:
            hdi._ingestion_service = None
            s1 = hdi.get_hybrid_ingestion_service("ws-singleton-a")
            s2 = hdi.get_hybrid_ingestion_service("ws-singleton-a")
            assert s1 is s2
            s3 = hdi.get_hybrid_ingestion_service("ws-singleton-b")
            assert s3 is not s1
        finally:
            hdi._ingestion_service = original


class TestHybridSync:
    @pytest.mark.asyncio
    async def test_sync_no_config(self, hybrid):
        result = await hybrid.sync_integration_data("nope")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_sync_recently_synced_skipped(self, hybrid):
        hybrid.enable_auto_sync("slack")
        hybrid.usage_stats["slack"].last_synced = datetime.now(timezone.utc)
        result = await hybrid.sync_integration_data("slack")
        assert result.get("skipped") is True

    @pytest.mark.asyncio
    async def test_sync_success(self, hybrid, hybrid_factory):
        hybrid.enable_auto_sync("hubspot")
        records = [
            {
                "id": "1",
                "type": "contact",
                "name": "Alice",
                "email": "alice@example.com",
                "company": "Acme",
            },
            {
                "id": "2",
                "type": "deal",
                "name": "Big Deal",
                "stage": "closed",
                "amount": 100,
            },
        ]
        hybrid_factory["memory"].add_document.return_value = True
        hybrid_factory["graphrag"].ingest_document.return_value = {
            "entities": 2,
            "relationships": 1,
        }
        with patch.object(hybrid, "_fetch_integration_data", new=AsyncMock(return_value=records)):
            result = await hybrid.sync_integration_data("hubspot")
        assert result["success"] is True
        assert result["records_fetched"] == 2
        assert result["records_ingested"] == 2
        assert result["entities_extracted"] == 4
        assert result["relationships_extracted"] == 2
        assert hybrid.usage_stats["hubspot"].last_synced is not None
        assert result["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_sync_skips_short_text(self, hybrid, hybrid_factory):
        hybrid.enable_auto_sync("slack")
        hybrid._record_to_text = MagicMock(return_value="x")
        with patch.object(
            hybrid,
            "_fetch_integration_data",
            new=AsyncMock(return_value=[{"id": "1", "type": "message", "text": "hi"}]),
        ):
            result = await hybrid.sync_integration_data("slack")
        assert result["records_ingested"] == 0
        hybrid_factory["memory"].add_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_record_error_partial(self, hybrid, hybrid_factory):
        hybrid.enable_auto_sync("slack")
        # R84: two writes per record now — index row + business_facts row.
        hybrid_factory["memory"].add_document.side_effect = [
            Exception("boom"), True,   # record 1: index fails, fact ok
            True, True,                # record 2: both ok
        ]
        records = [
            {"id": "1", "type": "message", "text": "some long enough message text here"},
            {"id": "2", "type": "message", "text": "another long enough message here"},
        ]
        with patch.object(hybrid, "_fetch_integration_data", new=AsyncMock(return_value=records)):
            result = await hybrid.sync_integration_data("slack")
        assert result["success"] is True
        assert result["partial"] is True
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_sync_majority_failed_not_synced(self, hybrid, hybrid_factory):
        hybrid.enable_auto_sync("slack")
        hybrid_factory["memory"].add_document.side_effect = Exception("boom")
        records = [{"id": str(i), "type": "message", "text": "some long text"} for i in range(5)]
        with patch.object(hybrid, "_fetch_integration_data", new=AsyncMock(return_value=records)):
            result = await hybrid.sync_integration_data("slack")
        assert result["success"] is False
        assert result["partial"] is True
        assert hybrid.usage_stats["slack"].last_synced is None

    @pytest.mark.asyncio
    async def test_sync_fetch_exception(self, hybrid):
        hybrid.enable_auto_sync("slack")
        with patch.object(
            hybrid, "_fetch_integration_data", new=AsyncMock(side_effect=Exception("api down"))
        ):
            result = await hybrid.sync_integration_data("slack")
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_sync_no_memory_handler(self, hybrid_factory, monkeypatch):
        monkeypatch.setattr("core.lancedb_handler.get_lancedb_handler", lambda *a, **k: None)
        service = HybridDataIngestionService(workspace_id="ws-nm")
        service.enable_auto_sync("slack")
        with patch.object(
            service,
            "_fetch_integration_data",
            new=AsyncMock(
                return_value=[{"id": "1", "type": "message", "text": "some long text"}]
            ),
        ):
            result = await service.sync_integration_data("slack")
        assert result["records_ingested"] == 0
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_estimate_api_cost_modes(self, hybrid):
        assert await hybrid._estimate_api_cost("x", SyncMode.DISCOVERY) == 100
        assert await hybrid._estimate_api_cost("x", SyncMode.HYBRID) == 30
        assert await hybrid._estimate_api_cost("x", SyncMode.FULL) == 50
        assert await hybrid._estimate_api_cost("x", SyncMode.INCREMENTAL) == 10
        assert await hybrid._estimate_api_cost("x", "garbage") == 10


class TestHybridFetch:
    @pytest.mark.asyncio
    async def test_fetch_dispatch_salesforce(self, hybrid):
        config = SyncConfiguration(integration_id="salesforce", max_records_per_sync=500)
        with patch.object(
            hybrid, "_fetch_salesforce_data", new=AsyncMock(return_value=[{"id": 1}])
        ):
            assert len(await hybrid._fetch_integration_data("salesforce", config)) == 1

    @pytest.mark.asyncio
    async def test_fetch_dispatch_universal(self, hybrid):
        config = SyncConfiguration(integration_id="hubspot", max_records_per_sync=500)
        with patch.object(
            hybrid, "_fetch_universal_adapter_data", new=AsyncMock(return_value=[{"id": 1}])
        ):
            assert len(await hybrid._fetch_integration_data("hubspot", config)) == 1

    @pytest.mark.asyncio
    async def test_fetch_dispatch_slack(self, hybrid):
        config = SyncConfiguration(integration_id="slack", max_records_per_sync=500)
        with patch.object(hybrid, "_fetch_slack_data", new=AsyncMock(return_value=[{"id": 1}])):
            assert len(await hybrid._fetch_integration_data("slack", config)) == 1

    @pytest.mark.asyncio
    async def test_fetch_dispatch_gmail(self, hybrid):
        config = SyncConfiguration(integration_id="gmail", max_records_per_sync=500)
        with patch.object(hybrid, "_fetch_gmail_data", new=AsyncMock(return_value=[{"id": 1}])):
            assert len(await hybrid._fetch_integration_data("gmail", config)) == 1

    @pytest.mark.asyncio
    async def test_fetch_dispatch_zendesk(self, hybrid):
        config = SyncConfiguration(integration_id="zendesk", max_records_per_sync=500)
        with patch.object(hybrid, "_fetch_zendesk_data", new=AsyncMock(return_value=[{"id": 1}])):
            assert len(await hybrid._fetch_integration_data("zendesk", config)) == 1

    @pytest.mark.asyncio
    async def test_fetch_dispatch_shopify(self, hybrid):
        config = SyncConfiguration(integration_id="shopify", max_records_per_sync=500)
        with patch.object(hybrid, "_fetch_shopify_data", new=AsyncMock(return_value=[{"id": 1}])):
            assert len(await hybrid._fetch_integration_data("shopify", config)) == 1

    @pytest.mark.asyncio
    async def test_fetch_dispatch_onedrive(self, hybrid):
        config = SyncConfiguration(integration_id="onedrive", max_records_per_sync=500)
        with patch.object(hybrid, "_fetch_onedrive_data", new=AsyncMock(return_value=[{"id": 1}])):
            assert len(await hybrid._fetch_integration_data("onedrive", config)) == 1

    @pytest.mark.asyncio
    async def test_fetch_dispatch_google_drive(self, hybrid):
        config = SyncConfiguration(integration_id="google_drive", max_records_per_sync=500)
        with patch.object(
            hybrid, "_fetch_google_drive_data", new=AsyncMock(return_value=[{"id": 1}])
        ):
            assert len(await hybrid._fetch_integration_data("google_drive", config)) == 1

    @pytest.mark.asyncio
    async def test_fetch_dispatch_telegram(self, hybrid):
        config = SyncConfiguration(integration_id="telegram", max_records_per_sync=500)
        with patch.object(hybrid, "_fetch_telegram_data", new=AsyncMock(return_value=[{"id": 1}])):
            assert len(await hybrid._fetch_integration_data("telegram", config)) == 1

    @pytest.mark.asyncio
    async def test_fetch_dispatch_unknown(self, hybrid):
        config = SyncConfiguration(integration_id="unknown_app", max_records_per_sync=500)
        assert await hybrid._fetch_integration_data("unknown_app", config) == []

    @pytest.mark.asyncio
    async def test_fetch_dispatch_error(self, hybrid):
        config = SyncConfiguration(integration_id="slack", max_records_per_sync=500)
        with patch.object(
            hybrid, "_fetch_slack_data", new=AsyncMock(side_effect=Exception("x"))
        ):
            assert await hybrid._fetch_integration_data("slack", config) == []

    @pytest.mark.asyncio
    async def test_fetch_respects_max_records(self, hybrid):
        config = SyncConfiguration(integration_id="slack", max_records_per_sync=2)
        with patch.object(
            hybrid,
            "_fetch_slack_data",
            new=AsyncMock(return_value=[{"id": 1}, {"id": 2}, {"id": 3}]),
        ):
            records = await hybrid._fetch_integration_data("slack", config)
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_fetch_salesforce_data(self, monkeypatch, hybrid):
        client = MagicMock()
        client.query.side_effect = [
            {
                "records": [
                    {
                        "Id": "c1",
                        "Name": "Alice",
                        "Email": "a@b.c",
                        "Title": "CEO",
                        "Account": {"Name": "Acme"},
                    }
                ]
            },
            {"records": [{"Id": "o1", "Name": "Opp", "StageName": "Won", "Amount": 100}]},
        ]
        async def _get_sf_client(ws, db_conn_pool=None):
            return client

        monkeypatch.setattr(
            "integrations.salesforce_service.get_salesforce_client", _get_sf_client
        )
        config = SyncConfiguration(
            integration_id="salesforce", entity_types=["contacts", "opportunities"]
        )
        records = await hybrid._fetch_salesforce_data(config)
        assert len(records) == 2
        assert records[0]["type"] == "contact"
        assert records[1]["type"] == "opportunity"

    @pytest.mark.asyncio
    async def test_fetch_salesforce_data_error(self, monkeypatch, hybrid):
        monkeypatch.setattr(
            "integrations.salesforce_service.get_salesforce_client",
            MagicMock(side_effect=Exception("boom")),
        )
        config = SyncConfiguration(integration_id="salesforce")
        assert await hybrid._fetch_salesforce_data(config) == []

    @pytest.mark.asyncio
    async def test_fetch_hubspot_data(self, monkeypatch, hybrid):
        service = MagicMock()
        service.get_contacts = AsyncMock(return_value=[
            {"id": "c1", "properties": {
                "firstname": "Alice", "lastname": "B",
                "email": "a@b.c", "company": "Acme"}}])
        service.get_deals = AsyncMock(return_value=[
            {"id": "d1", "properties": {"dealname": "Deal", "dealstage": "Won", "amount": "10"}}])
        monkeypatch.setattr("integrations.hubspot_service.get_hubspot_service",
                            lambda: service, raising=False)
        config = SyncConfiguration(integration_id="hubspot", entity_types=["contacts", "deals"])
        records = await hybrid._fetch_hubspot_data(config)
        assert len(records) == 2
        assert records[0]["name"] == "Alice B"

    @pytest.mark.asyncio
    async def test_fetch_hubspot_data_error(self, monkeypatch, hybrid):
        monkeypatch.setattr(
            "integrations.hubspot_service.get_hubspot_client",
            MagicMock(side_effect=Exception("boom")),
            raising=False,
        )
        config = SyncConfiguration(integration_id="hubspot")
        assert await hybrid._fetch_hubspot_data(config) == []

    @pytest.mark.asyncio
    async def test_fetch_slack_data_module_missing(self, hybrid):
        config = SyncConfiguration(integration_id="slack")
        assert await hybrid._fetch_slack_data(config) == []

    @pytest.mark.asyncio
    async def test_fetch_gmail_data(self, monkeypatch, hybrid):
        service = MagicMock()
        service.get_messages.return_value = [
            {"id": "m1", "threadId": "t1", "subject": "Hi", "from": "x@y.z"}
        ]
        monkeypatch.setattr("integrations.gmail_service.get_gmail_service", lambda: service)
        config = SyncConfiguration(integration_id="gmail")
        records = await hybrid._fetch_gmail_data(config)
        assert len(records) == 1
        assert records[0]["type"] == "email"

    @pytest.mark.asyncio
    async def test_fetch_gmail_data_import_error(self, monkeypatch, hybrid):
        def raise_import():
            raise ImportError("no gmail")

        monkeypatch.setattr("integrations.gmail_service.get_gmail_service", raise_import)
        config = SyncConfiguration(integration_id="gmail")
        assert await hybrid._fetch_gmail_data(config) == []

    @pytest.mark.asyncio
    async def test_fetch_gmail_data_error(self, monkeypatch, hybrid):
        monkeypatch.setattr(
            "integrations.gmail_service.get_gmail_service", MagicMock(side_effect=Exception("x"))
        )
        config = SyncConfiguration(integration_id="gmail")
        assert await hybrid._fetch_gmail_data(config) == []

    @pytest.mark.asyncio
    async def test_fetch_notion_data(self, monkeypatch, hybrid):
        service = MagicMock()
        service.search_pages_in_workspace.return_value = [
            {"id": "p1", "title": "Page", "url": "u", "created_time": "t", "archived": False}
        ]
        service.get_block_children.return_value = {"results": [{"id": "b1"}]}
        service.search_databases_in_workspace.return_value = [
            {"id": "d1", "title": [{"plain_text": "DB"}], "created_time": "t", "properties": {"a": 1}}
        ]
        service.get_database.return_value = {"title": [{"plain_text": "DB"}], "properties": {"a": 1}}
        monkeypatch.setattr("integrations.notion_service.NotionService",
                            lambda *a, **kw: service, raising=False)
        config = SyncConfiguration(integration_id="notion", entity_types=["pages", "databases"])
        records = await hybrid._fetch_notion_data(config)
        assert len(records) == 2
        assert records[0]["type"] == "page"
        assert records[1]["type"] == "database"

    @pytest.mark.asyncio
    async def test_fetch_notion_data_error(self, monkeypatch, hybrid):
        monkeypatch.setattr(
            "integrations.notion_service.get_notion_service", MagicMock(side_effect=Exception("x")), raising=False
        )
        config = SyncConfiguration(integration_id="notion")
        assert await hybrid._fetch_notion_data(config) == []

    @pytest.mark.asyncio
    async def test_fetch_jira_data(self, monkeypatch, hybrid):
        service = MagicMock()
        service.search_issues.return_value = {"issues": [
            {"key": "J-1", "fields": {
                "summary": "Summary", "status": {"name": "Open"},
                "assignee": {"displayName": "Bob"}, "priority": {"name": "High"}}}]}
        monkeypatch.setattr(
            "integrations.jira_service.get_jira_service", lambda: service, raising=False
        )
        config = SyncConfiguration(integration_id="jira")
        records = await hybrid._fetch_jira_data(config)
        assert len(records) == 1
        assert records[0]["type"] == "issue"
        assert records[0]["assignee"] == "Bob"

    @pytest.mark.asyncio
    async def test_fetch_zendesk_data(self, monkeypatch, hybrid):
        service = MagicMock()
        service.get_tickets = AsyncMock(return_value=[{"id": 1, "subject": "S", "status": "open"}])
        service.get_users = AsyncMock(return_value=[{"id": 2, "name": "U", "email": "e"}])
        monkeypatch.setattr("integrations.zendesk_service.ZendeskService",
                            lambda *a, **kw: service, raising=False)
        config = SyncConfiguration(integration_id="zendesk", entity_types=["tickets", "users"])
        records = await hybrid._fetch_zendesk_data(config)
        assert len(records) == 2
        assert records[0]["type"] == "ticket"
        assert records[1]["type"] == "user"

    @pytest.mark.asyncio
    async def test_fetch_zendesk_data_error(self, monkeypatch, hybrid):
        monkeypatch.setattr(
            "integrations.zendesk_service.get_zendesk_service", MagicMock(side_effect=Exception("x")), raising=False
        )
        config = SyncConfiguration(integration_id="zendesk")
        assert await hybrid._fetch_zendesk_data(config) == []

    @pytest.mark.asyncio
    async def test_fetch_zoho_multi_app(self, monkeypatch, hybrid):
        adapter = MagicMock()
        adapter.ensure_token = AsyncMock()
        adapter.get_leads = AsyncMock(return_value=[{"id": "L1", "type": "crm_leads"}])
        adapter.get_invoices = AsyncMock(return_value=[{"id": "I1"}])
        adapter.get_items = AsyncMock(return_value=[{"id": "IT1"}])
        adapter.get_sales_orders = AsyncMock(return_value=[{"id": "SO1"}])

        def make_adapter(db, workspace_id, instance_url):
            return adapter

        monkeypatch.setattr(
            "core.integrations.adapters.zoho.ZohoAdapter", make_adapter
        )
        token = MagicMock()
        token.instance_url = "https://zoho.com"
        token.credential_metadata = {"organization_id": "org1"}
        session = _FakeSession(token=token)
        monkeypatch.setattr(hdi, "SessionLocal", lambda: session)
        config = SyncConfiguration(
            integration_id="zoho",
            entity_types=["crm_leads", "books_invoices", "inventory_items", "inventory_sales_orders"],
        )
        records = await hybrid._fetch_zoho_multi_app_data(config)
        assert len(records) == 4

    @pytest.mark.asyncio
    async def test_fetch_zoho_no_token(self, monkeypatch, hybrid):
        adapter = MagicMock()
        adapter.ensure_token = AsyncMock()
        monkeypatch.setattr(
            "core.integrations.adapters.zoho.ZohoAdapter",
            lambda db, workspace_id, instance_url: adapter,
        )
        session = _FakeSession(token=None)
        monkeypatch.setattr(hdi, "SessionLocal", lambda: session)
        config = SyncConfiguration(integration_id="zoho", entity_types=["crm_leads"])
        records = await hybrid._fetch_zoho_multi_app_data(config)
        assert records == []

    @pytest.mark.asyncio
    async def test_fetch_zoho_projects_discovery(self, monkeypatch, hybrid):
        adapter = MagicMock()
        adapter.ensure_token = AsyncMock()
        adapter.get_portals = AsyncMock(return_value=[{"id": "portal1"}])
        adapter.get_projects = AsyncMock(return_value=[{"id": "proj1"}])
        adapter.get_tasks = AsyncMock(return_value=[{"id": "t1", "type": "projects_tasks"}])
        monkeypatch.setattr(
            "core.integrations.adapters.zoho.ZohoAdapter",
            lambda db, workspace_id, instance_url: adapter,
        )
        token = MagicMock()
        token.instance_url = "https://zoho.com"
        token.credential_metadata = {"organization_id": "org1"}
        session = _FakeSession(token=token)
        monkeypatch.setattr(hdi, "SessionLocal", lambda: session)
        config = SyncConfiguration(integration_id="zoho", entity_types=["projects_tasks"])
        records = await hybrid._fetch_zoho_multi_app_data(config, discovery_mode=True)
        assert len(records) == 1
        adapter.get_tasks.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fetch_zoho_error(self, monkeypatch, hybrid):
        monkeypatch.setattr(
            "core.integrations.adapters.zoho.ZohoAdapter", MagicMock(side_effect=Exception("boom"))
        )
        config = SyncConfiguration(integration_id="zoho")
        assert await hybrid._fetch_zoho_multi_app_data(config) == []

    @pytest.mark.asyncio
    async def test_fetch_shopify_missing_token(self, monkeypatch, hybrid):
        service = MagicMock()
        service.config = {}
        service.shop_name = None
        monkeypatch.setattr("integrations.shopify_service.ShopifyService", lambda *a, **k: service)
        monkeypatch.delenv("SHOPIFY_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("SHOPIFY_SHOP_NAME", raising=False)
        monkeypatch.delenv("SHOPIFY_SHOP_DOMAIN", raising=False)
        config = SyncConfiguration(integration_id="shopify")
        assert await hybrid._fetch_shopify_data(config) == []

    @pytest.mark.asyncio
    async def test_fetch_shopify_data(self, monkeypatch, hybrid):
        service = MagicMock()
        service.config = {"access_token": "tok"}
        service.shop_name = "shop.example.com"
        service.get_products = AsyncMock(return_value=[{"id": 1}])
        service.get_orders = AsyncMock(return_value=[{"id": 2}])
        service.get_customers = AsyncMock(return_value=[{"id": 3}])
        monkeypatch.setattr("integrations.shopify_service.ShopifyService", lambda *a, **k: service)
        config = SyncConfiguration(
            integration_id="shopify", entity_types=["products", "orders", "customers"]
        )
        records = await hybrid._fetch_shopify_data(config)
        assert len(records) == 3
        assert records[0]["source"] == "shopify"
        assert records[0]["type"] == "shopify_product"

    @pytest.mark.asyncio
    async def test_fetch_shopify_error(self, monkeypatch, hybrid):
        monkeypatch.setattr(
            "integrations.shopify_service.ShopifyService", MagicMock(side_effect=Exception("x"))
        )
        config = SyncConfiguration(integration_id="shopify")
        assert await hybrid._fetch_shopify_data(config) == []

    @pytest.mark.asyncio
    async def test_fetch_onedrive_no_token(self, monkeypatch, hybrid):
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value=None)
        monkeypatch.setattr("integrations.onedrive_service.OneDriveService", lambda *a, **k: service)
        config = SyncConfiguration(integration_id="onedrive")
        assert await hybrid._fetch_onedrive_data(config) == []

    @pytest.mark.asyncio
    async def test_fetch_onedrive_list_fail(self, monkeypatch, hybrid):
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value="tok")
        service.list_files = AsyncMock(return_value={"status": "error", "message": "nope"})
        monkeypatch.setattr("integrations.onedrive_service.OneDriveService", lambda *a, **k: service)
        config = SyncConfiguration(integration_id="onedrive")
        assert await hybrid._fetch_onedrive_data(config) == []

    @pytest.mark.asyncio
    async def test_fetch_onedrive_data(self, monkeypatch, hybrid):
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value="tok")
        service.list_files = AsyncMock(
            return_value={
                "status": "success",
                "data": {
                    "value": [
                        {"id": "f1", "name": "doc.docx", "webUrl": "u", "size": 10},
                        {"id": "f2", "name": "folder", "folder": {}},
                    ]
                },
            }
        )
        service.download_file_bytes = AsyncMock(return_value=b"content bytes")
        monkeypatch.setattr("integrations.onedrive_service.OneDriveService", lambda *a, **k: service)
        doc_ingestor = MagicMock()
        doc_ingestor.process_file_bytes = AsyncMock()
        monkeypatch.setattr(
            "core.auto_document_ingestion.AutoDocumentIngestionService", lambda **k: doc_ingestor
        )
        config = SyncConfiguration(integration_id="onedrive")
        records = await hybrid._fetch_onedrive_data(config)
        assert len(records) == 1
        assert records[0]["type"] == "onedrive_file"
        doc_ingestor.process_file_bytes.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fetch_google_drive_data(self, monkeypatch, hybrid):
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value="tok")
        service.list_files = AsyncMock(
            return_value={
                "status": "success",
                "data": {
                    "value": [
                        {"id": "g1", "name": "doc.pdf", "mimeType": "application/pdf"},
                        {
                            "id": "g2",
                            "name": "folder",
                            "mimeType": "application/vnd.google-apps.folder",
                        },
                    ]
                },
            }
        )
        service.download_file_bytes = AsyncMock(return_value=b"bytes")
        monkeypatch.setattr(
            "integrations.google_drive_service.GoogleDriveService", lambda *a, **k: service
        )
        doc_ingestor = MagicMock()
        doc_ingestor.process_file_bytes = AsyncMock()
        monkeypatch.setattr(
            "core.auto_document_ingestion.AutoDocumentIngestionService", lambda: doc_ingestor
        )
        config = SyncConfiguration(integration_id="google_drive")
        records = await hybrid._fetch_google_drive_data(config)
        assert len(records) == 2
        assert records[0]["object_type"] == "file"
        assert records[1]["object_type"] == "folder"
        doc_ingestor.process_file_bytes.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fetch_google_drive_no_token(self, monkeypatch, hybrid):
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value=None)
        monkeypatch.setattr(
            "integrations.google_drive_service.GoogleDriveService", lambda *a, **k: service
        )
        config = SyncConfiguration(integration_id="google_drive")
        assert await hybrid._fetch_google_drive_data(config) == []

    @pytest.mark.asyncio
    async def test_fetch_telegram_data(self, monkeypatch, hybrid):
        adapter = MagicMock()
        adapter.get_updates = AsyncMock(
            return_value=[
                {"message": {"message_id": 1, "text": "hi", "chat": {"id": 1}, "from": {"id": 9}}},
                {"channel_post": {"message_id": 2, "text": "post", "chat": {"id": 2}}},
                {"edited_message": {"message_id": 3}},
            ]
        )
        monkeypatch.setattr("core.communication.adapters.telegram.TelegramAdapter", lambda: adapter)
        config = SyncConfiguration(integration_id="telegram")
        records = await hybrid._fetch_telegram_data(config)
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_fetch_telegram_empty(self, monkeypatch, hybrid):
        adapter = MagicMock()
        adapter.get_updates = AsyncMock(return_value=[])
        monkeypatch.setattr("core.communication.adapters.telegram.TelegramAdapter", lambda: adapter)
        config = SyncConfiguration(integration_id="telegram")
        assert await hybrid._fetch_telegram_data(config) == []

    @pytest.mark.asyncio
    async def test_fetch_universal_no_method(self, monkeypatch, hybrid):
        monkeypatch.setattr("core.service_factory.ServiceFactory", type("SF", (), {}))
        config = SyncConfiguration(integration_id="hubspot")
        assert await hybrid._fetch_universal_adapter_data("hubspot", config) == []

    @pytest.mark.asyncio
    async def test_fetch_universal_adapter_error(self, monkeypatch, hybrid):
        monkeypatch.setattr(
            "core.service_factory.ServiceFactory", MagicMock(side_effect=Exception("boom"))
        )
        config = SyncConfiguration(integration_id="hubspot")
        assert await hybrid._fetch_universal_adapter_data("hubspot", config) == []

    @pytest.mark.asyncio
    async def test_fetch_universal_pagination(self, monkeypatch, hybrid):
        adapter = MagicMock()
        adapter.ensure_token = AsyncMock()
        pages = [
            {"results": [{"id": i, "name": f"r{i}"} for i in range(100)]},
            {"results": [{"id": 100}]},
        ]
        adapter.fetch_records = AsyncMock(side_effect=pages)

        class FakeSF:
            @staticmethod
            def get_hubspot_adapter(db=None, workspace_id=None):
                return adapter

        monkeypatch.setattr("core.service_factory.ServiceFactory", FakeSF)
        config = SyncConfiguration(
            integration_id="hubspot", entity_types=["contacts"], max_records_per_sync=500
        )
        records = await hybrid._fetch_universal_adapter_data("hubspot", config)
        assert len(records) == 101
        assert all(r["source"] == "hubspot" for r in records)
        assert all("type" in r for r in records)

    @pytest.mark.asyncio
    async def test_fetch_universal_cap_stops_pagination(self, monkeypatch, hybrid):
        adapter = MagicMock()
        adapter.ensure_token = AsyncMock()
        adapter.fetch_records = AsyncMock(
            return_value={"results": [{"id": i} for i in range(100)]}
        )

        class FakeSF:
            @staticmethod
            def get_hubspot_adapter(db=None, workspace_id=None):
                return adapter

        monkeypatch.setattr("core.service_factory.ServiceFactory", FakeSF)
        config = SyncConfiguration(
            integration_id="hubspot", entity_types=["contacts"], max_records_per_sync=150
        )
        records = await hybrid._fetch_universal_adapter_data("hubspot", config)
        assert len(records) == 200

    @pytest.mark.asyncio
    async def test_fetch_universal_discovery_mode(self, monkeypatch, hybrid):
        adapter = MagicMock()
        adapter.ensure_token = AsyncMock()
        adapter.get_available_schemas = AsyncMock(
            return_value=[{"name": "new_type"}, {"name": "contacts"}]
        )
        adapter.fetch_records = AsyncMock(return_value={"results": [{"id": 1}]})

        class FakeSF:
            @staticmethod
            def get_hubspot_adapter(db=None, workspace_id=None):
                return adapter

        monkeypatch.setattr("core.service_factory.ServiceFactory", FakeSF)
        config = SyncConfiguration(
            integration_id="hubspot", entity_types=["contacts"], max_records_per_sync=500
        )
        records = await hybrid._fetch_universal_adapter_data("hubspot", config, discovery_mode=True)
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_fetch_universal_fallback_zoho(self, monkeypatch, hybrid):
        adapter = MagicMock()
        adapter.ensure_token = AsyncMock()
        del adapter.fetch_records

        class FakeSF:
            @staticmethod
            def get_zoho_adapter(db=None, workspace_id=None):
                return adapter

        monkeypatch.setattr("core.service_factory.ServiceFactory", FakeSF)
        config = SyncConfiguration(integration_id="zoho", max_records_per_sync=500)
        with patch.object(
            hybrid, "_fetch_zoho_multi_app_data", new=AsyncMock(return_value=[{"id": 1}])
        ):
            records = await hybrid._fetch_universal_adapter_data("zoho", config)
        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_fetch_universal_no_fetch_records_warning(self, monkeypatch, hybrid):
        adapter = MagicMock()
        adapter.ensure_token = AsyncMock()

        class FakeSF:
            @staticmethod
            def get_hubspot_adapter(db=None, workspace_id=None):
                return adapter

        monkeypatch.setattr("core.service_factory.ServiceFactory", FakeSF)
        config = SyncConfiguration(integration_id="hubspot", entity_types=["contacts"])
        records = await hybrid._fetch_universal_adapter_data("hubspot", config)
        assert records == []

    @pytest.mark.asyncio
    async def test_fetch_universal_fetch_error_per_entity(self, monkeypatch, hybrid):
        adapter = MagicMock()
        adapter.ensure_token = AsyncMock()
        adapter.fetch_records = AsyncMock(side_effect=Exception("boom"))

        class FakeSF:
            @staticmethod
            def get_hubspot_adapter(db=None, workspace_id=None):
                return adapter

        monkeypatch.setattr("core.service_factory.ServiceFactory", FakeSF)
        config = SyncConfiguration(integration_id="hubspot", entity_types=["contacts"])
        records = await hybrid._fetch_universal_adapter_data("hubspot", config)
        assert records == []


class TestHybridSchema:
    @pytest.mark.asyncio
    async def test_discover_schema_types(self, hybrid):
        record = {
            "name": "x",
            "count": 3,
            "score": 1.5,
            "ok": True,
            "nested": {"a": 1},
            "items": [1],
        }
        schema = await hybrid._discover_schema(record)
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["count"]["type"] == "integer"
        assert schema["properties"]["score"]["type"] == "number"
        assert schema["properties"]["ok"]["type"] == "boolean"
        assert schema["properties"]["nested"]["type"] == "object"
        assert schema["properties"]["items"]["type"] == "array"

    @pytest.mark.asyncio
    async def test_discover_schema_skips_raw_metadata(self, hybrid):
        schema = await hybrid._discover_schema({"raw_metadata": {"a": 1}, "name": "x"})
        assert "raw_metadata" not in schema["properties"]

    @pytest.mark.asyncio
    async def test_discover_schema_llm_refinement(self, hybrid, hybrid_factory):
        hybrid_factory["llm"].generate_structured_response = AsyncMock(
            return_value=MagicMock(
                display_names={"name": "Full Name"}, descriptions={"name": "The name"}
            )
        )
        schema = await hybrid._discover_schema({"name": "x"})
        assert schema["properties"]["name"]["title"] == "Full Name"
        assert schema["properties"]["name"]["description"] == "The name"

    @pytest.mark.asyncio
    async def test_discover_schema_llm_failure(self, hybrid, hybrid_factory):
        hybrid_factory["llm"].generate_structured_response = AsyncMock(
            side_effect=Exception("boom")
        )
        schema = await hybrid._discover_schema({"name": "x"})
        assert schema["properties"]["name"]["type"] == "string"

    def test_record_to_text(self, hybrid):
        record = {
            "type": "contact",
            "name": "Alice",
            "email": "a@b.c",
            "company": "Acme",
            "stage": "won",
        }
        text = hybrid._record_to_text(record, "hubspot")
        assert "Contact from hubspot" in text
        assert "Alice" in text
        assert "Acme" in text

    def test_record_to_text_empty(self, hybrid):
        assert hybrid._record_to_text({}, "hubspot") == "Record from hubspot"


class TestHybridSchedule:
    @pytest.mark.asyncio
    async def test_run_scheduled_syncs(self, hybrid, hybrid_factory):
        hybrid.enable_auto_sync("slack")
        hybrid.usage_stats["slack"].last_synced = datetime.now(timezone.utc) - timedelta(hours=2)
        with patch.object(
            hybrid, "sync_integration_data", new=AsyncMock(return_value={"success": True})
        ) as sync, patch.object(hdi.asyncio, "sleep", new=AsyncMock()):
            hybrid._running = True

            async def stop_loop(*args):
                hybrid._running = False

            hdi.asyncio.sleep.side_effect = stop_loop
            await hybrid.run_scheduled_syncs()
        sync.assert_awaited()

    @pytest.mark.asyncio
    async def test_run_scheduled_syncs_not_due(self, hybrid):
        hybrid.enable_auto_sync("slack")
        hybrid.usage_stats["slack"].last_synced = datetime.now(timezone.utc)
        with patch.object(
            hybrid, "sync_integration_data", new=AsyncMock(return_value={"success": True})
        ) as sync, patch.object(hdi.asyncio, "sleep", new=AsyncMock()):
            hybrid._running = True

            async def stop_loop(*args):
                hybrid._running = False

            hdi.asyncio.sleep.side_effect = stop_loop
            await hybrid.run_scheduled_syncs()
        sync.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_scheduled_syncs_error(self, hybrid):
        hybrid.enable_auto_sync("slack")
        hybrid.usage_stats["slack"].last_synced = None
        with patch.object(
            hybrid, "sync_integration_data", new=AsyncMock(side_effect=Exception("boom"))
        ), patch.object(hdi.asyncio, "sleep", new=AsyncMock()):
            hybrid._running = True

            async def stop_loop(*args):
                hybrid._running = False

            hdi.asyncio.sleep.side_effect = stop_loop
            await hybrid.run_scheduled_syncs()

    def test_stop(self, hybrid):
        task = MagicMock()
        hybrid._sync_tasks["a"] = task
        hybrid._running = True
        hybrid.stop()
        assert hybrid._running is False
        task.cancel.assert_called_once()
