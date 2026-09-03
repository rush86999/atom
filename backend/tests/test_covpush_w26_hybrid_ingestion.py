"""Coverage wave 26 — core/hybrid_data_ingestion.py (TDD, mocked services).

Drives usage tracking, auto-sync enablement, the full sync pipeline
(discovery, embedding ingest, GraphRAG, error-rate partial semantics),
the integration fetchers (universal adapter + app-specific), schema
discovery, usage summary and the scheduled-sync loop — all with mocked
dependencies, no network, no LLM, no spend.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.hybrid_data_ingestion import (
    DEFAULT_SYNC_CONFIGS,
    HybridDataIngestionService,
    IntegrationUsageStats,
    SyncConfiguration,
    SyncMode,
    _ZOHO_PER_MODULE_SYNC_LIMIT,
    get_hybrid_ingestion_service,
    record_integration_call,
)


def make_service(**kwargs):
    with patch("core.lancedb_handler.get_lancedb_handler", return_value=MagicMock()), \
         patch("core.graphrag_engine.GraphRAGEngine", return_value=MagicMock()), \
         patch("core.llm_service.get_llm_service", return_value=MagicMock()):
        return HybridDataIngestionService(
            workspace_id=kwargs.pop("workspace_id", "default"),
            tenant_id=kwargs.pop("tenant_id", "default"),
            **kwargs,
        )


def make_config(entity_types=None, **kw):
    defaults = dict(integration_id="x", entity_types=entity_types or ["records"],
                    sync_last_n_days=30, max_records_per_sync=1000)
    defaults.update(kw)
    return SyncConfiguration(**defaults)


class TestSyncModeAndCost:
    def test_sync_mode_enum(self):
        assert SyncMode("incremental") == SyncMode.INCREMENTAL

    async def test_estimate_cost_all_modes(self):
        svc = make_service()
        assert await svc._estimate_api_cost("x", SyncMode.DISCOVERY) == 100
        assert await svc._estimate_api_cost("x", SyncMode.HYBRID) == 30
        assert await svc._estimate_api_cost("x", SyncMode.FULL) == 50
        assert await svc._estimate_api_cost("x", SyncMode.INCREMENTAL) == 10
        assert await svc._estimate_api_cost("x", "full") == 50
        assert await svc._estimate_api_cost("x", "bogus_mode") == 10


class TestUsageTracking:
    def test_record_new_and_existing(self):
        svc = make_service()
        svc.record_integration_usage("slack", "Slack", success=True)
        svc.record_integration_usage("slack", "Slack", success=False)
        stats = svc.usage_stats["slack"]
        assert stats.total_calls == 2
        assert stats.successful_calls == 1
        assert stats.last_used is not None

    def test_auto_enable_at_threshold(self):
        svc = make_service()
        # Auto-sync defaults ON — the usage threshold only re-enables after
        # an explicit opt-out.
        svc.record_integration_usage("hubspot", "HubSpot")
        svc.disable_auto_sync("hubspot")
        with patch.object(svc, "enable_auto_sync", new=MagicMock()) as enable:
            for i in range(svc.AUTO_SYNC_USAGE_THRESHOLD - 1):
                svc.record_integration_usage("hubspot", "HubSpot")
        enable.assert_called_once_with("hubspot")

    def test_check_auto_enable_no_stats(self):
        svc = make_service()
        svc._check_auto_enable_sync("ghost")  # no crash

    def test_check_auto_enable_below_threshold(self):
        svc = make_service()
        with patch.object(svc, "enable_auto_sync", new=MagicMock()) as enable:
            svc._check_auto_enable_sync("ghost")
        enable.assert_not_called()


class TestAutoSyncControl:
    def test_enable_with_config(self):
        svc = make_service()
        cfg = make_config(integration_id="salesforce", entity_types=["contacts"])
        svc.enable_auto_sync("salesforce", cfg)
        assert svc.sync_configs["salesforce"] is cfg
        assert svc.usage_stats["salesforce"].auto_sync_enabled is True

    def test_enable_with_default_config(self):
        svc = make_service()
        svc.enable_auto_sync("salesforce")
        assert svc.sync_configs["salesforce"] is DEFAULT_SYNC_CONFIGS["salesforce"]

    def test_enable_basic_config(self):
        svc = make_service()
        svc.enable_auto_sync("custom_api")
        cfg = svc.sync_configs["custom_api"]
        assert cfg.integration_id == "custom_api"
        assert cfg.entity_types == ["records"]

    def test_disable_auto_sync(self):
        svc = make_service()
        task = MagicMock()
        svc._sync_tasks["slack"] = task
        svc.usage_stats["slack"] = IntegrationUsageStats("slack", "Slack")
        svc.usage_stats["slack"].auto_sync_enabled = True
        svc.disable_auto_sync("slack")
        assert svc.usage_stats["slack"].auto_sync_enabled is False
        assert "slack" not in svc._sync_tasks
        task.cancel.assert_called_once()


class TestSyncPipeline:
    async def test_no_config_returns_error(self):
        svc = make_service()
        result = await svc.sync_integration_data("ghost")
        assert "error" in result

    async def test_recently_synced_skipped(self):
        svc = make_service()
        svc.sync_configs["slack"] = make_config(integration_id="slack")
        stats = IntegrationUsageStats("slack", "Slack")
        stats.last_synced = datetime.now(timezone.utc)
        stats.sync_frequency_minutes = 60
        svc.usage_stats["slack"] = stats
        result = await svc.sync_integration_data("slack")
        assert result["skipped"] is True

    async def test_force_bypasses_recent_check(self):
        svc = make_service()
        svc.sync_configs["slack"] = make_config(integration_id="slack")
        stats = IntegrationUsageStats("slack", "Slack")
        stats.last_synced = datetime.now(timezone.utc)
        svc.usage_stats["slack"] = stats
        with patch.object(svc, "_fetch_integration_data", new=AsyncMock(return_value=[])):
            result = await svc.sync_integration_data("slack", force=True)
        assert result["success"] is True
        assert stats.last_synced is not None

    async def test_full_pipeline_with_discovery_and_graphrag(self):
        svc = make_service()
        svc.sync_configs["slack"] = make_config(integration_id="slack")
        record = {"id": "r1", "type": "message", "text": "hello world this is long enough"}
        with patch.object(svc, "_fetch_integration_data", new=AsyncMock(return_value=[record])), \
             patch.object(svc, "_discover_schema", new=AsyncMock(return_value={"type": "object"})), \
             patch("core.entity_type_service.EntityTypeService") as et_cls, \
             patch("core.database.SessionLocal") as session_cls:
            session_cls.return_value.close = MagicMock()
            et_cls.return_value.resolve_or_create_draft = MagicMock()
            svc.memory_handler.add_document.return_value = True
            svc.graphrag.ingest_document = AsyncMock(
                return_value={"entities": 2, "relationships": 1})
            result = await svc.sync_integration_data("slack")
        assert result["success"] is True
        assert result["records_fetched"] == 1
        assert result["records_ingested"] == 1
        assert result["entities_extracted"] == 2
        assert result["relationships_extracted"] == 1
        et_cls.return_value.resolve_or_create_draft.assert_called_once()

    async def test_short_text_skipped(self):
        svc = make_service()
        svc.sync_configs["x"] = make_config(integration_id="x")
        record = {"id": "r1", "type": "message", "text": "short"}
        with patch.object(svc, "_fetch_integration_data", new=AsyncMock(return_value=[record])), \
             patch.object(svc, "_record_to_text", return_value="short"):
            result = await svc.sync_integration_data("x")
        assert result["records_ingested"] == 0
        svc.memory_handler.add_document.assert_not_called()

    async def test_record_error_majority_partial_failure(self):
        svc = make_service()
        svc.sync_configs["x"] = make_config(integration_id="x")

        def _fail_text(record, integration_id):
            raise RuntimeError("boom")

        records = [{"id": f"r{i}", "type": "message", "text": "long enough text"} for i in range(4)]
        with patch.object(svc, "_fetch_integration_data", new=AsyncMock(return_value=records)), \
             patch.object(svc, "_record_to_text", new=_fail_text):
            result = await svc.sync_integration_data("x")
        assert result["success"] is False
        assert result["partial"] is True
        assert len(result["errors"]) == 4

    async def test_minority_errors_mark_partial_success(self):
        svc = make_service()
        svc.sync_configs["x"] = make_config(integration_id="x")

        def _fail_one(record, integration_id):
            if record["id"] == "r2":
                raise RuntimeError("boom")
            return "ok " * 20

        records = [{"id": f"r{i}", "type": "message", "text": "long"} for i in range(4)]
        with patch.object(svc, "_fetch_integration_data", new=AsyncMock(return_value=records)), \
             patch.object(svc, "_record_to_text", new=_fail_one):
            svc.memory_handler.add_document.return_value = True
            svc.graphrag.ingest_document = AsyncMock(return_value={})
            result = await svc.sync_integration_data("x")
        assert result["success"] is True
        assert result["partial"] is True

    async def test_outer_exception(self):
        svc = make_service()
        svc.sync_configs["x"] = make_config(integration_id="x")
        with patch.object(svc, "_fetch_integration_data",
                          new=AsyncMock(side_effect=RuntimeError("fetch exploded"))):
            result = await svc.sync_integration_data("x")
        assert result["success"] is False
        assert "fetch exploded" in result["error"]

    async def test_discovery_failure_tolerated(self):
        svc = make_service()
        svc.sync_configs["x"] = make_config(integration_id="x")
        record = {"id": "r1", "type": "custom:type", "text": "long enough text here"}
        with patch.object(svc, "_fetch_integration_data", new=AsyncMock(return_value=[record])), \
             patch.object(svc, "_discover_schema",
                          new=AsyncMock(side_effect=RuntimeError("schema down"))), \
             patch("core.database.SessionLocal") as session_cls:
            session_cls.return_value.close = MagicMock()
            svc.memory_handler.add_document.return_value = True
            svc.graphrag.ingest_document = AsyncMock(return_value={})
            result = await svc.sync_integration_data("x")
        assert result["success"] is True
        assert result["records_ingested"] == 1


class TestFetchDispatcher:
    async def test_salesforce_dispatch(self):
        svc = make_service()
        config = make_config(integration_id="salesforce")
        with patch.object(svc, "_fetch_salesforce_data", new=AsyncMock(return_value=[{"id": 1}])):
            records = await svc._fetch_integration_data("salesforce", config)
        assert records == [{"id": 1}]

    @pytest.mark.parametrize("integration_id", ["hubspot", "notion", "airtable", "jira", "zoho", "zoho_crm"])
    async def test_universal_dispatch(self, integration_id):
        svc = make_service()
        config = make_config(integration_id=integration_id)
        with patch.object(svc, "_fetch_universal_adapter_data", new=AsyncMock(return_value=[])):
            records = await svc._fetch_integration_data(integration_id, config)
        assert records == []

    async def test_unknown_integration(self):
        svc = make_service()
        config = make_config(integration_id="ghost")
        records = await svc._fetch_integration_data("ghost", config)
        assert records == []

    async def test_fetcher_exception_tolerated(self):
        svc = make_service()
        config = make_config(integration_id="slack")
        with patch.object(svc, "_fetch_slack_data",
                          new=AsyncMock(side_effect=RuntimeError("slack down"))):
            records = await svc._fetch_integration_data("slack", config)
        assert records == []

    async def test_max_records_cap(self):
        svc = make_service()
        config = make_config(integration_id="salesforce", max_records_per_sync=2)
        with patch.object(svc, "_fetch_salesforce_data",
                          new=AsyncMock(return_value=[{"id": 1}, {"id": 2}, {"id": 3}])):
            records = await svc._fetch_integration_data("salesforce", config)
        assert len(records) == 2


class TestUniversalAdapter:
    async def _adapter_env(self, svc, adapter, integration_id="hubspot"):
        db = MagicMock()
        db.close = MagicMock()
        factory = MagicMock()
        adapter_method = getattr(factory, f"get_{integration_id.replace('_crm', '')}_adapter")
        adapter_method.return_value = adapter
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.service_factory.ServiceFactory", factory):
            return await svc._fetch_universal_adapter_data(integration_id, make_config(integration_id=integration_id))

    async def test_missing_adapter_method(self):
        svc = make_service()
        db = MagicMock()
        db.close = MagicMock()
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.service_factory.ServiceFactory", MagicMock()):
            records = await svc._fetch_universal_adapter_data("mystery", make_config(integration_id="mystery"))
        assert records == []

    async def test_paginated_fetch(self):
        svc = make_service()
        adapter = MagicMock()
        adapter.ensure_token = AsyncMock()
        adapter.fetch_records = AsyncMock(side_effect=[
            {"results": [{"id": f"a{i}"} for i in range(100)]},  # full page
            {"results": [{"id": "c"}]},                           # partial page → stop
        ])
        records = await self._adapter_env(svc, adapter, "hubspot")
        assert len(records) == 101
        assert records[0]["type"] == "records"
        assert adapter.fetch_records.call_count == 2
        assert adapter.ensure_token.called

    async def test_pagination_cap(self):
        svc = make_service()
        adapter = MagicMock()
        adapter.ensure_token = AsyncMock()
        adapter.fetch_records = AsyncMock(return_value={"results": [{"id": f"r{i}"} for i in range(100)]})
        db = MagicMock()
        db.close = MagicMock()
        factory = MagicMock()
        factory.get_hubspot_adapter.return_value = adapter
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.service_factory.ServiceFactory", factory):
            records = await svc._fetch_universal_adapter_data(
                "hubspot", make_config(integration_id="hubspot", max_records_per_sync=150))
        assert len(records) == 200
        assert adapter.fetch_records.call_count == 2

    async def test_fetch_error_per_entity(self):
        svc = make_service()
        adapter = MagicMock()
        adapter.fetch_records = AsyncMock(side_effect=RuntimeError("entity failed"))
        records = await self._adapter_env(svc, adapter, "hubspot")
        assert records == []

    async def test_discovery_mode_hubspot(self):
        svc = make_service()
        adapter = MagicMock()
        adapter.ensure_token = AsyncMock()
        adapter.get_available_schemas = AsyncMock(return_value=[{"name": "custom_objects"}, {"name": "contacts"}])
        adapter.fetch_records = AsyncMock(return_value={"results": []})
        db = MagicMock()
        db.close = MagicMock()
        factory = MagicMock()
        factory.get_hubspot_adapter.return_value = adapter
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.service_factory.ServiceFactory", factory):
            records = await svc._fetch_universal_adapter_data(
                "hubspot", make_config(integration_id="hubspot", entity_types=["contacts"]), discovery_mode=True)
        assert records == []
        called_types = [c.kwargs["entity_type"] for c in adapter.fetch_records.call_args_list]
        assert "custom_objects" in called_types

    async def test_no_fetch_records_zoho_fallback(self):
        svc = make_service()
        adapter = MagicMock()
        adapter.ensure_token = AsyncMock()
        del adapter.fetch_records
        db = MagicMock()
        db.close = MagicMock()
        factory = MagicMock()
        factory.get_zoho_adapter.return_value = adapter
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.service_factory.ServiceFactory", factory), \
             patch.object(svc, "_fetch_zoho_multi_app_data", new=AsyncMock(return_value=[{"id": "z"}])):
            records = await svc._fetch_universal_adapter_data(
                "zoho", make_config(integration_id="zoho"))
        assert records == [{"id": "z"}]
        adapter.ensure_token.assert_awaited_once()

    async def test_no_fetch_records_other_warns(self):
        svc = make_service()
        adapter = MagicMock()
        del adapter.fetch_records
        records = await self._adapter_env(svc, adapter, "jira")
        assert records == []

    async def test_outer_exception(self):
        svc = make_service()
        with patch("core.database.SessionLocal", side_effect=RuntimeError("db down")):
            records = await svc._fetch_universal_adapter_data(
                "hubspot", make_config(integration_id="hubspot"))
        assert records == []


class TestAppFetchers:
    async def test_salesforce_fetch(self):
        svc = make_service()
        client = MagicMock()
        client.query.side_effect = [
            {"records": [{"Id": "1", "Name": "N", "Email": "e@x", "Title": "T",
                          "Account": {"Name": "AC"}}]},
            {"records": [{"Id": "2", "Name": "O", "StageName": "S", "Amount": 10}]},
        ]
        with patch("integrations.salesforce_service.get_salesforce_client",
                   new=AsyncMock(return_value=client)):
            records = await svc._fetch_salesforce_data(
                make_config(integration_id="salesforce", entity_types=["contacts", "opportunities"]))
        assert len(records) == 2
        assert records[0]["type"] == "contact"
        assert records[0]["company"] == "AC"
        assert records[1]["type"] == "opportunity"

    async def test_salesforce_no_client(self):
        svc = make_service()
        with patch("integrations.salesforce_service.get_salesforce_client",
                   new=AsyncMock(return_value=None)):
            records = await svc._fetch_salesforce_data(make_config(integration_id="salesforce"))
        assert records == []

    async def test_salesforce_fetch_error(self):
        svc = make_service()
        with patch("integrations.salesforce_service.get_salesforce_client",
                   new=AsyncMock(side_effect=RuntimeError("sf down"))):
            records = await svc._fetch_salesforce_data(make_config(integration_id="salesforce"))
        assert records == []

    async def test_hubspot_fetch(self):
        svc = make_service()
        service = MagicMock()
        service.get_contacts = AsyncMock(return_value=[
            {"id": "c1", "properties": {"firstname": "F", "lastname": "L", "email": "e", "company": "C"}}])
        service.get_deals = AsyncMock(return_value=[
            {"id": "d1", "properties": {"dealname": "D", "dealstage": "S", "amount": "5"}}])
        with patch("integrations.hubspot_service.get_hubspot_service", return_value=service):
            records = await svc._fetch_hubspot_data(
                make_config(integration_id="hubspot", entity_types=["contacts", "deals"]))
        assert len(records) == 2
        assert records[0]["name"] == "F L"
        assert records[1]["type"] == "deal"

    async def test_hubspot_not_configured(self):
        svc = make_service()
        with patch("integrations.hubspot_service.get_hubspot_service", return_value=None):
            records = await svc._fetch_hubspot_data(make_config(integration_id="hubspot"))
        assert records == []

    async def test_hubspot_fetch_error(self):
        svc = make_service()
        with patch("integrations.hubspot_service.get_hubspot_service",
                   side_effect=RuntimeError("hs down")):
            records = await svc._fetch_hubspot_data(make_config(integration_id="hubspot"))
        assert records == []

    async def test_slack_fetch(self):
        svc = make_service()
        with patch("core.token_storage.token_storage.get_token",
                   return_value={"access_token": "t"}), \
             patch("integrations.slack_service_unified.slack_unified_service.list_channels",
                   new=AsyncMock(return_value=[{"id": "c1", "name": "general"}])), \
             patch("integrations.slack_service_unified.slack_unified_service.get_channel_history",
                   new=AsyncMock(return_value={
                       "messages": [{"type": "message", "ts": "1.1", "text": "hi", "user": "u1"},
                                    {"type": "bot_message", "ts": "1.2", "text": "ignored"}]})):
            records = await svc._fetch_slack_data(make_config(integration_id="slack"))
        assert len(records) == 1
        assert records[0]["channel"] == "general"

    async def test_slack_no_token(self):
        svc = make_service()
        with patch("core.token_storage.token_storage.get_token", return_value=None):
            records = await svc._fetch_slack_data(make_config(integration_id="slack"))
        assert records == []

    async def test_gmail_fetch(self):
        svc = make_service()
        gmail = MagicMock()
        gmail.get_messages.return_value = [{"id": "m1", "threadId": "t1", "subject": "S",
                                            "from": "a@b", "snippet": "snip"}]
        with patch("integrations.gmail_service.get_gmail_service", return_value=gmail):
            records = await svc._fetch_gmail_data(make_config(integration_id="gmail"))
        assert len(records) == 1
        assert records[0]["type"] == "email"

    async def test_gmail_import_error(self):
        svc = make_service()
        with patch("integrations.gmail_service.get_gmail_service",
                   side_effect=ImportError("no google")):
            records = await svc._fetch_gmail_data(make_config(integration_id="gmail"))
        assert records == []

    async def test_notion_fetch(self):
        svc = make_service()
        notion = MagicMock()
        notion.search_pages_in_workspace.return_value = [{"id": "p1", "title": "Page", "url": "u"}]
        notion.get_block_children.return_value = {"results": [{"id": "b1"}, {"id": "b2"}]}
        notion.search_databases_in_workspace.return_value = [{"id": "d1"}]
        notion.get_database.return_value = {"title": [{"plain_text": "DB"}], "properties": {"a": 1}, "created_time": "t"}
        with patch("integrations.notion_service.NotionService", return_value=notion):
            records = await svc._fetch_notion_data(
                make_config(integration_id="notion", entity_types=["pages", "databases"]))
        assert len(records) == 2
        assert records[0]["content_blocks_count"] == 2
        assert records[1]["properties_count"] == 1

    async def test_notion_import_error(self):
        svc = make_service()
        with patch("integrations.notion_service.NotionService",
                   side_effect=ImportError("no notion")):
            records = await svc._fetch_notion_data(make_config(integration_id="notion"))
        assert records == []

    async def test_jira_fetch(self):
        svc = make_service()
        service = MagicMock()
        service.search_issues.return_value = {"issues": [
            {"key": "J-1", "fields": {
                "summary": "Sum", "status": {"name": "Open"},
                "assignee": {"displayName": "Alice"}, "priority": {"name": "High"}}},
            {"key": "J-2", "fields": {
                "summary": "Sum2", "status": {"name": "Open"},
                "assignee": None, "priority": None}},
        ]}
        with patch("integrations.jira_service.get_jira_service", return_value=service):
            records = await svc._fetch_jira_data(make_config(integration_id="jira"))
        assert len(records) == 2
        assert records[0]["assignee"] == "Alice"
        assert records[1]["assignee"] is None
        assert records[0]["status"] == "Open"

    async def test_jira_not_configured(self):
        svc = make_service()
        with patch("integrations.jira_service.get_jira_service", return_value=None):
            records = await svc._fetch_jira_data(make_config(integration_id="jira"))
        assert records == []


class TestSchemaDiscovery:
    async def test_base_inference_types(self):
        svc = make_service()
        svc.llm = None
        record = {
            "name": "x", "count": 5, "ratio": 1.5, "flag": True,
            "meta": {"a": 1}, "tags": ["a"], "raw_metadata": "skip me",
        }
        schema = await svc._discover_schema(record)
        props = schema["properties"]
        assert props["name"]["type"] == "string"
        assert props["count"]["type"] == "integer"
        assert props["ratio"]["type"] == "number"
        assert props["flag"]["type"] == "boolean"
        assert props["meta"]["type"] == "object"
        assert props["tags"]["type"] == "array"
        assert "raw_metadata" not in props
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"

    async def test_llm_refinement(self):
        svc = make_service()
        metadata = SimpleNamespace(
            display_names={"name": "Full Name"},
            descriptions={"name": "The person's name"})
        svc.llm.generate_structured_response = AsyncMock(return_value=metadata)
        schema = await svc._discover_schema({"name": "x"})
        assert schema["properties"]["name"]["title"] == "Full Name"
        assert schema["properties"]["name"]["description"] == "The person's name"

    async def test_llm_refinement_failure_tolerated(self):
        svc = make_service()
        svc.llm.generate_structured_response = AsyncMock(side_effect=RuntimeError("llm down"))
        schema = await svc._discover_schema({"name": "x"})
        assert schema["properties"]["name"]["type"] == "string"


class TestRecordToTextAndSummary:
    def test_record_to_text(self):
        svc = make_service()
        record = {"type": "contact", "name": "Alice", "title": "CEO",
                  "email": "a@b.c", "company": "ACME", "stage": "lead",
                  "status": "new", "amount": 100, "assignee": "Bob", "channel": "c"}
        text = svc._record_to_text(record, "hubspot")
        assert "Contact from hubspot" in text
        assert "name: Alice" in text
        assert "email: a@b.c" in text

    def test_get_usage_summary(self):
        svc = make_service()
        svc.record_integration_usage("slack", "Slack")
        svc.usage_stats["slack"].last_synced = datetime.now(timezone.utc)
        svc.usage_stats["slack"].auto_sync_enabled = True
        svc.sync_configs["slack"] = make_config(integration_id="slack", entity_types=["messages"])
        summary = svc.get_usage_summary()
        assert summary["workspace_id"] == "default"
        assert summary["auto_sync_enabled_count"] == 1
        assert summary["integrations"][0]["entity_types"] == ["messages"]
        assert summary["integrations"][0]["last_synced"] is not None


class TestScheduler:
    async def test_run_scheduled_syncs_one_pass(self):
        svc = make_service()
        svc._running = True
        stats = IntegrationUsageStats("slack", "Slack")
        stats.auto_sync_enabled = True
        stats.last_synced = datetime.now(timezone.utc) - timedelta(hours=2)
        svc.usage_stats["slack"] = stats
        svc.sync_configs["slack"] = make_config(integration_id="slack")

        async def _fake_sleep(*a, **k):
            svc._running = False

        with patch("asyncio.sleep", new=_fake_sleep), \
             patch.object(svc, "sync_integration_data", new=AsyncMock()) as sync:
            await svc.run_scheduled_syncs()
        sync.assert_called_once_with("slack")

    async def test_run_scheduled_syncs_error_tolerated(self):
        svc = make_service()
        svc._running = True
        stats = IntegrationUsageStats("x", "X")
        stats.auto_sync_enabled = True
        svc.usage_stats["x"] = stats
        svc.sync_configs["x"] = make_config(integration_id="x")

        async def _fake_sleep(*a, **k):
            svc._running = False

        with patch("asyncio.sleep", new=_fake_sleep), \
             patch.object(svc, "sync_integration_data",
                          new=AsyncMock(side_effect=RuntimeError("sync failed"))):
            await svc.run_scheduled_syncs()  # no crash

    def test_stop(self):
        svc = make_service()
        task = MagicMock()
        svc._sync_tasks["a"] = task
        svc._running = True
        svc.stop()
        assert svc._running is False
        task.cancel.assert_called_once()


class TestModuleFunctions:
    def test_get_service_singleton(self):
        global _ingestion_service
        from core import hybrid_data_ingestion as hdi
        hdi._ingestion_service = None
        s1 = get_hybrid_ingestion_service()
        s2 = get_hybrid_ingestion_service()
        assert s1 is s2
        s3 = get_hybrid_ingestion_service("other_ws")
        assert s3 is not s1
        assert s3.workspace_id == "other_ws"
        hdi._ingestion_service = None

    def test_record_integration_call(self):
        from core import hybrid_data_ingestion as hdi
        service = MagicMock()
        service.workspace_id = "default"
        # The getter resolves per-workspace instances from the map; the
        # module-global singleton is back-compat read-only.
        key = ("default", "default")
        hdi._ingestion_services[key] = service
        try:
            record_integration_call("slack", "Slack", success=False, user_id="u1")
        finally:
            hdi._ingestion_services.pop(key, None)
        service.record_integration_usage.assert_called_once_with("slack", "Slack", False, "u1")


# ---------------------------------------------------------------------------
# wave-26b — remaining fetchers (zendesk / zoho / shopify / onedrive /
#            google_drive / telegram)
# ---------------------------------------------------------------------------


class TestZendeskFetcher:
    async def test_tickets_and_users(self):
        svc = make_service()
        service = MagicMock()
        service.get_tickets = AsyncMock(return_value=[
            {"id": 1, "subject": "S", "status": "open", "priority": "high",
             "created_at": "t", "updated_at": "u", "requester_id": 9,
             "assignee_id": 8, "type": "question", "description": "d"}])
        service.get_users = AsyncMock(return_value=[
            {"id": 2, "name": "Bob", "email": "b@x", "role": "agent",
             "created_at": "t", "last_login_at": "l", "verified": True}])
        with patch("integrations.zendesk_service.ZendeskService", return_value=service):
            records = await svc._fetch_zendesk_data(
                make_config(integration_id="zendesk", entity_types=["tickets", "users"]))
        assert len(records) == 2
        assert records[0]["type"] == "ticket"
        assert records[0]["requester_id"] == 9
        assert records[1]["type"] == "user"
        assert records[1]["verified"] is True

    async def test_empty_entity_types_fetches_tickets(self):
        svc = make_service()
        service = MagicMock()
        service.get_tickets = AsyncMock(return_value=[])
        with patch("integrations.zendesk_service.ZendeskService", return_value=service):
            records = await svc._fetch_zendesk_data(
                SyncConfiguration(integration_id="zendesk", entity_types=[]))
        assert records == []
        service.get_tickets.assert_called_once()

    async def test_import_error(self):
        svc = make_service()
        with patch("integrations.zendesk_service.ZendeskService",
                   side_effect=ImportError("no zendesk")):
            records = await svc._fetch_zendesk_data(make_config(integration_id="zendesk"))
        assert records == []


class TestZohoMultiAppFetcher:
    def _adapter(self):
        adapter = MagicMock()
        adapter.ensure_token = AsyncMock()
        adapter.get_leads = AsyncMock(return_value=[{"id": "l1"}])
        adapter.get_deals = AsyncMock(return_value=[{"id": "d1"}])
        adapter.get_invoices = AsyncMock(return_value=[{"id": "i1"}])
        adapter.get_items = AsyncMock(return_value=[{"id": "it1"}])
        adapter.get_sales_orders = AsyncMock(return_value=[{"id": "so1"}])
        adapter.get_tasks = AsyncMock(return_value=[{"id": "t1"}])
        # Org discovery (Books/Inventory gating) and the per-module error
        # flag read by the suite fetcher.
        adapter.get_organizations = AsyncMock(return_value=[])
        adapter.get_portals = AsyncMock(return_value=[])
        adapter.last_error = None
        return adapter

    def _token(self, **meta):
        token = SimpleNamespace(instance_url="https://x", credential_metadata=meta)
        return token

    async def test_all_modules(self):
        svc = make_service()
        adapter = self._adapter()
        db = MagicMock()
        db.close = MagicMock()
        token = self._token(organization_id="org1", portal_id="p1",
                            active_projects=["prj1"])
        db.query.return_value.filter.return_value.first.return_value = token
        with patch("core.integrations.adapters.zoho.ZohoAdapter", return_value=adapter), \
             patch("core.hybrid_data_ingestion.SessionLocal", return_value=db):
            records = await svc._fetch_zoho_multi_app_data(make_config(
                integration_id="zoho",
                entity_types=["crm_leads", "crm_deals", "books_invoices",
                              "inventory_items", "inventory_sales_orders",
                              "projects_tasks"]))
        assert len(records) == 6
        # Books/Invoice modules page up to the per-module sync bound now,
        # not a fixed first-page 100; the incremental cursor rides along
        # (None when the workspace has no cursor yet).
        adapter.get_invoices.assert_called_once_with(
            organization_id="org1", limit=_ZOHO_PER_MODULE_SYNC_LIMIT,
            modified_since=None)
        adapter.get_tasks.assert_called_once()

    async def test_no_org_id_skips_books(self):
        svc = make_service()
        adapter = self._adapter()
        db = MagicMock()
        db.close = MagicMock()
        token = self._token()
        db.query.return_value.filter.return_value.first.return_value = token
        with patch("core.integrations.adapters.zoho.ZohoAdapter", return_value=adapter), \
             patch("core.hybrid_data_ingestion.SessionLocal", return_value=db):
            records = await svc._fetch_zoho_multi_app_data(make_config(
                integration_id="zoho", entity_types=["books_invoices", "crm_leads"]))
        assert len(records) == 1
        adapter.get_invoices.assert_not_called()

    async def test_discovery_mode_projects(self):
        svc = make_service()
        adapter = self._adapter()
        adapter.get_portals = AsyncMock(return_value=[{"id": "portal1"}])
        adapter.get_projects = AsyncMock(return_value=[{"id": "prj1"}, {"id": "prj2"}])
        db = MagicMock()
        db.close = MagicMock()
        token = self._token()
        db.query.return_value.filter.return_value.first.return_value = token
        with patch("core.integrations.adapters.zoho.ZohoAdapter", return_value=adapter), \
             patch("core.hybrid_data_ingestion.SessionLocal", return_value=db):
            records = await svc._fetch_zoho_multi_app_data(
                make_config(integration_id="zoho", entity_types=["projects_tasks"]),
                discovery_mode=True)
        assert len(records) == 2  # 2 projects × 1 task each (top 3)
        adapter.get_portals.assert_called_once()
        adapter.get_projects.assert_called_once_with("portal1")

    async def test_no_token(self):
        svc = make_service()
        db = MagicMock()
        db.close = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.integrations.adapters.zoho.ZohoAdapter") as adapter_cls, \
             patch("core.hybrid_data_ingestion.SessionLocal", return_value=db):
            records = await svc._fetch_zoho_multi_app_data(
                make_config(integration_id="zoho", entity_types=["crm_leads"]))
        assert records == []
        adapter_cls.assert_called_once()

    async def test_exception(self):
        svc = make_service()
        with patch("core.database.SessionLocal", side_effect=RuntimeError("db down")):
            records = await svc._fetch_zoho_multi_app_data(
                make_config(integration_id="zoho", entity_types=["crm_leads"]))
        assert records == []


class TestShopifyFetcher:
    async def test_all_entity_types(self):
        svc = make_service()
        service = MagicMock()
        service.config = {"access_token": "t"}
        service.shop_name = "x.myshopify.com"
        service.get_products = AsyncMock(return_value=[{"id": 1, "title": "P"}])
        service.get_orders = AsyncMock(return_value=[{"id": 2, "name": "O"}])
        service.get_customers = AsyncMock(return_value=[{"id": 3, "email": "c@x"}])
        with patch("integrations.shopify_service.ShopifyService", return_value=service):
            records = await svc._fetch_shopify_data(make_config(
                integration_id="shopify",
                entity_types=["products", "orders", "customers"]))
        assert len(records) == 3
        assert records[0]["type"] == "shopify_product"
        assert records[2]["type"] == "shopify_customer"
        assert records[0]["source"] == "shopify"

    async def test_missing_credentials(self):
        svc = make_service()
        service = MagicMock()
        service.config = {}
        service.shop_name = None
        with patch("integrations.shopify_service.ShopifyService", return_value=service), \
             patch("core.hybrid_data_ingestion.os.getenv", return_value=None):
            records = await svc._fetch_shopify_data(make_config(integration_id="shopify"))
        assert records == []

    async def test_entity_fetch_error(self):
        svc = make_service()
        service = MagicMock()
        service.config = {"access_token": "t"}
        service.shop_name = "x"
        service.get_products = AsyncMock(side_effect=RuntimeError("shopify down"))
        with patch("integrations.shopify_service.ShopifyService", return_value=service):
            records = await svc._fetch_shopify_data(
                make_config(integration_id="shopify", entity_types=["products"]))
        assert records == []


class TestOneDriveFetcher:
    async def test_success_with_doc_ingestion(self):
        svc = make_service()
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value="tok")
        service.list_files = AsyncMock(return_value={
            "status": "success",
            "data": {"value": [
                {"id": "f1", "name": "report.docx", "webUrl": "u", "size": 10},
                {"id": "f2", "name": "folder1", "webUrl": "u2", "folder": {}},  # folder → skipped
            ]}})
        service.download_file_bytes = AsyncMock(return_value=b"bytes")
        ingestor = MagicMock()
        ingestor.process_file_bytes = AsyncMock()
        with patch("integrations.onedrive_service.OneDriveService", return_value=service), \
             patch("core.auto_document_ingestion.AutoDocumentIngestionService",
                   return_value=ingestor):
            records = await svc._fetch_onedrive_data(make_config(integration_id="onedrive"))
        assert len(records) == 1
        assert records[0]["type"] == "onedrive_file"
        assert records[0]["properties"]["name"] == "report.docx"
        service.download_file_bytes.assert_called_once()
        ingestor.process_file_bytes.assert_called_once()

    async def test_no_token(self):
        svc = make_service()
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value=None)
        with patch("integrations.onedrive_service.OneDriveService", return_value=service):
            records = await svc._fetch_onedrive_data(make_config(integration_id="onedrive"))
        assert records == []

    async def test_list_failure(self):
        svc = make_service()
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value="tok")
        service.list_files = AsyncMock(return_value={"status": "error", "message": "nope"})
        with patch("integrations.onedrive_service.OneDriveService", return_value=service):
            records = await svc._fetch_onedrive_data(make_config(integration_id="onedrive"))
        assert records == []

    async def test_no_doc_ingestor(self):
        svc = make_service()
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value="tok")
        service.list_files = AsyncMock(return_value={
            "status": "success", "data": {"value": [{"id": "f1", "name": "a.docx"}]}})
        with patch("integrations.onedrive_service.OneDriveService", return_value=service), \
             patch("core.auto_document_ingestion.AutoDocumentIngestionService",
                   side_effect=RuntimeError("no ingestor")):
            records = await svc._fetch_onedrive_data(make_config(integration_id="onedrive"))
        assert len(records) == 1


class TestGoogleDriveFetcher:
    async def test_success(self):
        svc = make_service()
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value="tok")
        service.list_files = AsyncMock(return_value={
            "status": "success",
            "data": {"files": [
                {"id": "g1", "name": "doc.pdf", "mimeType": "application/pdf"},
                {"id": "g2", "name": "Folder", "mimeType": "application/vnd.google-apps.folder"},
            ]}})
        service.download_file_bytes = AsyncMock(return_value=b"pdf")
        ingestor = MagicMock()
        ingestor.process_file_bytes = AsyncMock()
        with patch("integrations.google_drive_service.GoogleDriveService", return_value=service), \
             patch("core.auto_document_ingestion.AutoDocumentIngestionService",
                   return_value=ingestor):
            records = await svc._fetch_google_drive_data(make_config(integration_id="google_drive"))
        assert len(records) == 2
        assert records[0]["object_type"] == "file"
        assert records[1]["object_type"] == "folder"
        service.download_file_bytes.assert_called_once()  # folder skipped

    async def test_no_token(self):
        svc = make_service()
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value=None)
        with patch("integrations.google_drive_service.GoogleDriveService", return_value=service):
            records = await svc._fetch_google_drive_data(make_config(integration_id="google_drive"))
        assert records == []


class TestTelegramFetcher:
    async def test_messages(self):
        svc = make_service()
        adapter = MagicMock()
        adapter.get_updates = AsyncMock(return_value=[
            {"message": {"message_id": 1, "text": "hi", "date": 123,
                         "chat": {"id": 9, "title": "Chat"},
                         "from": {"id": 7, "username": "alice"}}},
            {"channel_post": {"message_id": 2, "text": "announcement",
                              "chat": {"id": 9, "username": "chan"},
                              "from": {"first_name": "bot"}}},
            {"update_id": 3},  # no message/channel_post → skipped
        ])
        with patch("core.communication.adapters.telegram.TelegramAdapter", return_value=adapter):
            records = await svc._fetch_telegram_data(make_config(integration_id="telegram"))
        assert len(records) == 2
        assert records[0]["type"] == "telegram_message"
        assert records[0]["properties"]["sender_name"] == "alice"
        assert records[1]["properties"]["chat_title"] == "chan"

    async def test_no_updates(self):
        svc = make_service()
        adapter = MagicMock()
        adapter.get_updates = AsyncMock(return_value=[])
        with patch("core.communication.adapters.telegram.TelegramAdapter", return_value=adapter):
            records = await svc._fetch_telegram_data(make_config(integration_id="telegram"))
        assert records == []

    async def test_exception(self):
        svc = make_service()
        with patch("core.communication.adapters.telegram.TelegramAdapter",
                   side_effect=RuntimeError("tg down")):
            records = await svc._fetch_telegram_data(make_config(integration_id="telegram"))
        assert records == []
