"""
Bug-hunt + coverage tests for core.hybrid_data_ingestion (round 2).

The module had several bugs already fixed in prior sessions (await on
graphrag ingest, paginated fetch, sync success-gating). This round focuses
on raising coverage of the untested-but-correct branches and verifying the
fixed behavior stays fixed (regression guards).

Targets the previously-UNcovered lines:
- record_integration_usage / _check_auto_enable_sync / enable_auto_sync
- sync_integration_data success/partial/skip gating
- _estimate_api_cost
- _record_to_text / get_usage_summary
- _discover_schema (type inference)
- disable_auto_sync / stop
"""
import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, MagicMock, patch

from core.hybrid_data_ingestion import (
    HybridDataIngestionService,
    IntegrationUsageStats,
    SyncConfiguration,
    SyncMode,
    DEFAULT_SYNC_CONFIGS,
)


@pytest.fixture
def service():
    """Build a service without touching real LanceDB/GraphRAG/LLM singletons."""
    with patch("core.hybrid_data_ingestion.get_lancedb_handler") if False else patch.object(
        HybridDataIngestionService, "__init__", lambda self, *a, **kw: None
    ):
        svc = HybridDataIngestionService.__new__(HybridDataIngestionService)
        svc.workspace_id = "ws1"
        svc.tenant_id = "t1"
        svc.usage_stats = {}
        svc.sync_configs = {}
        svc._sync_tasks = {}
        svc._running = False
        svc.memory_handler = None
        svc.graphrag = None
        svc.llm = None
        return svc


# ============================================================================
# Coverage: record_integration_usage + auto-enable threshold
# ============================================================================
class TestRecordUsage:
    def test_records_successful_call(self, service):
        service.record_integration_usage("salesforce", "Salesforce", success=True)
        s = service.usage_stats["salesforce"]
        assert s.total_calls == 1
        assert s.successful_calls == 1
        assert s.last_used is not None
        # Below threshold -> auto-sync NOT enabled
        assert s.auto_sync_enabled is False

    def test_records_failed_call_does_not_increment_success(self, service):
        service.record_integration_usage("slack", "Slack", success=False)
        s = service.usage_stats["slack"]
        assert s.total_calls == 1
        assert s.successful_calls == 0

    def test_auto_enable_fires_at_threshold(self, service):
        # threshold = AUTO_SYNC_USAGE_THRESHOLD (10)
        for _ in range(service.AUTO_SYNC_USAGE_THRESHOLD):
            service.record_integration_usage("salesforce", "Salesforce")
        assert service.usage_stats["salesforce"].auto_sync_enabled is True

    def test_enable_auto_sync_uses_default_config_when_known(self, service):
        service.enable_auto_sync("salesforce")
        assert service.usage_stats["salesforce"].auto_sync_enabled is True
        # default config loaded
        assert "salesforce" in service.sync_configs
        assert "contacts" in service.sync_configs["salesforce"].entity_types

    def test_enable_auto_sync_basic_config_for_unknown(self, service):
        service.enable_auto_sync("custom_integration")
        cfg = service.sync_configs["custom_integration"]
        assert cfg.entity_types == ["records"]
        assert cfg.sync_last_n_days == 30

    def test_enable_auto_sync_with_explicit_config(self, service):
        custom = SyncConfiguration(integration_id="x", entity_types=["a"], sync_last_n_days=7)
        service.enable_auto_sync("x", config=custom)
        assert service.sync_configs["x"] is custom

    def test_disable_auto_sync(self, service):
        service.enable_auto_sync("salesforce")
        # simulate a tracked task (Future needs an explicit loop on Py3.14 —
        # no implicit event loop exists in sync tests)
        _loop = asyncio.new_event_loop()
        try:
            task = asyncio.Future(loop=_loop)
            service._sync_tasks["salesforce"] = task
            service.disable_auto_sync("salesforce")
            assert service.usage_stats["salesforce"].auto_sync_enabled is False
            assert "salesforce" not in service._sync_tasks
            assert task.cancelled() or task.done()
        finally:
            _loop.close()

    def test_disable_auto_sync_unknown_integration_no_crash(self, service):
        service.disable_auto_sync("never_seen")  # must not raise


# ============================================================================
# Regression: sync_integration_data success / partial / skip gating (Bug #7)
# ============================================================================
class TestSyncGating:
    @pytest.mark.asyncio
    async def test_no_config_returns_error(self, service):
        result = await service.sync_integration_data("unconfigured")
        assert result["error"].startswith("No sync config")

    @pytest.mark.asyncio
    async def test_skip_when_recently_synced(self, service):
        cfg = SyncConfiguration(integration_id="x")
        service.sync_configs["x"] = cfg
        stats = IntegrationUsageStats(
            integration_id="x", integration_name="x",
            last_synced=datetime.now(timezone.utc),
            sync_frequency_minutes=60,
        )
        service.usage_stats["x"] = stats
        result = await service.sync_integration_data("x", force=False)
        assert result.get("skipped") is True
        assert result["reason"] == "Recently synced"

    @pytest.mark.asyncio
    async def test_force_overrides_recent_sync(self, service):
        cfg = SyncConfiguration(integration_id="x")
        service.sync_configs["x"] = cfg
        stats = IntegrationUsageStats(
            integration_id="x", integration_name="x",
            last_synced=datetime.now(timezone.utc),
        )
        service.usage_stats["x"] = stats
        with patch.object(service, "_fetch_integration_data", AsyncMock(return_value=[])):
            result = await service.sync_integration_data("x", force=True)
        assert result.get("skipped") is not True
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_majority_errors_not_marked_synced(self, service):
        """Bug #7 regression: >50% record errors must NOT set last_synced
        (so the next run retries instead of skipping)."""
        cfg = SyncConfiguration(integration_id="x", max_records_per_sync=10)
        service.sync_configs["x"] = cfg
        stats = IntegrationUsageStats(integration_id="x", integration_name="x")
        service.usage_stats["x"] = stats

        # 4 records, all fail in the per-record loop
        records = [{"id": i, "type": "msg", "text": "x" * 20} for i in range(4)]
        # Make memory_handler.add_document raise to trigger per-record errors
        handler = Mock()
        handler.add_document.side_effect = RuntimeError("db down")
        service.memory_handler = handler

        with patch.object(service, "_fetch_integration_data", AsyncMock(return_value=records)):
            result = await service.sync_integration_data("x", force=True)

        assert result["success"] is False
        assert result["partial"] is True
        # Critical: last_synced must NOT be updated so retry is allowed
        assert stats.last_synced is None

    @pytest.mark.asyncio
    async def test_minority_errors_marked_success_partial(self, service):
        cfg = SyncConfiguration(integration_id="x", max_records_per_sync=10)
        service.sync_configs["x"] = cfg
        stats = IntegrationUsageStats(integration_id="x", integration_name="x")
        service.usage_stats["x"] = stats

        records = [{"id": i, "type": "msg", "text": "x" * 20} for i in range(4)]
        handler = Mock()
        # first call fails, rest succeed — a CALLABLE so the contract holds
        # regardless of how many times the upsert path invokes add_document
        # (a finite side_effect list raises StopIteration on any extra call,
        # which deadlocks the sync task instead of counting an error)
        calls = {"n": 0}
        def _add_document(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            return True
        handler.add_document.side_effect = _add_document
        service.memory_handler = handler

        with patch.object(service, "_fetch_integration_data", AsyncMock(return_value=records)):
            result = await service.sync_integration_data("x", force=True)

        assert result["success"] is True
        assert result["partial"] is True
        assert stats.last_synced is not None

    @pytest.mark.asyncio
    async def test_clean_sync_marks_success(self, service):
        cfg = SyncConfiguration(integration_id="x")
        service.sync_configs["x"] = cfg
        stats = IntegrationUsageStats(integration_id="x", integration_name="x")
        service.usage_stats["x"] = stats

        records = [{"id": i, "type": "msg", "text": "hello world text"} for i in range(2)]
        handler = Mock()
        handler.add_document.return_value = True
        service.memory_handler = handler

        with patch.object(service, "_fetch_integration_data", AsyncMock(return_value=records)):
            result = await service.sync_integration_data("x", force=True)
        assert result["success"] is True
        assert "partial" not in result
        assert result["records_ingested"] == 2
        assert stats.last_synced is not None


# ============================================================================
# Coverage: _estimate_api_cost (all modes)
# ============================================================================
class TestEstimateApiCost:
    @pytest.mark.asyncio
    async def test_all_modes(self, service):
        assert await service._estimate_api_cost("x", SyncMode.INCREMENTAL) == 10
        assert await service._estimate_api_cost("x", SyncMode.DISCOVERY) == 100
        assert await service._estimate_api_cost("x", SyncMode.HYBRID) == 30
        assert await service._estimate_api_cost("x", SyncMode.FULL) == 50

    @pytest.mark.asyncio
    async def test_invalid_string_mode_falls_back_to_incremental(self, service):
        assert await service._estimate_api_cost("x", "bogus_mode") == 10

    @pytest.mark.asyncio
    async def test_valid_string_mode_accepted(self, service):
        assert await service._estimate_api_cost("x", "discovery") == 100


# ============================================================================
# Coverage: _record_to_text
# ============================================================================
class TestRecordToText:
    def test_includes_key_fields(self, service):
        record = {
            "type": "contact",
            "name": "Alice",
            "email": "a@b.com",
            "company": "Acme",
            "amount": 100,
        }
        text = service._record_to_text(record, "salesforce")
        assert "Contact from salesforce" in text
        assert "name: Alice" in text
        assert "email: a@b.com" in text
        assert "company: Acme" in text
        assert "amount: 100" in text

    def test_skips_falsy_fields(self, service):
        record = {"type": "contact", "name": "", "email": None}
        text = service._record_to_text(record, "x")
        assert "name:" not in text
        assert "email:" not in text

    def test_missing_type_defaults_to_record(self, service):
        text = service._record_to_text({"name": "X"}, "slack")
        assert text.startswith("Record from slack")


# ============================================================================
# Coverage: _discover_schema (type inference, no LLM)
# ============================================================================
class TestDiscoverSchema:
    @pytest.mark.asyncio
    async def test_infers_types(self, service):
        record = {
            "active": True,
            "count": 5,
            "price": 9.99,
            "nested": {"a": 1},
            "tags": ["x"],
            "name": "Alice",
            "raw_metadata": {"secret": 1},  # must be skipped
        }
        schema = await service._discover_schema(record)
        props = schema["properties"]
        assert props["active"] == {"type": "boolean"}
        assert props["count"] == {"type": "integer"}
        assert props["price"] == {"type": "number"}
        assert props["nested"] == {"type": "object"}
        assert props["tags"] == {"type": "array"}
        assert props["name"] == {"type": "string"}
        # raw_metadata excluded
        assert "raw_metadata" not in props
        assert schema["$schema"].endswith("2020-12/schema")


# ============================================================================
# Coverage: get_usage_summary + stop
# ============================================================================
class TestUsageSummary:
    def test_summary_reflects_state(self, service):
        service.record_integration_usage("salesforce", "Salesforce")
        service.enable_auto_sync("salesforce")
        summary = service.get_usage_summary()
        assert summary["workspace_id"] == "ws1"
        assert summary["auto_sync_enabled_count"] == 1
        entry = next(i for i in summary["integrations"] if i["id"] == "salesforce")
        assert entry["total_calls"] == 1
        assert entry["auto_sync_enabled"] is True
        assert entry["entity_types"]  # from default config

    def test_stop_sets_running_false_and_cancels_tasks(self, service):
        service._running = True
        _loop = asyncio.new_event_loop()
        try:
            t = asyncio.Future(loop=_loop)
            service._sync_tasks["x"] = t
            service.stop()
            assert service._running is False
            assert t.cancelled() or t.done()
        finally:
            _loop.close()


# ============================================================================
# Coverage: DEFAULT_SYNC_CONFIGS sanity (regression guard for fetcher routing)
# ============================================================================
class TestDefaultConfigs:
    def test_known_integrations_have_configs(self):
        for iid in ["salesforce", "hubspot", "slack", "gmail", "notion", "jira",
                    "google_calendar", "zendesk", "zoho", "shopify", "onedrive",
                    "google_drive", "telegram"]:
            assert iid in DEFAULT_SYNC_CONFIGS, f"missing default config for {iid}"
            cfg = DEFAULT_SYNC_CONFIGS[iid]
            assert cfg.max_records_per_sync > 0
            assert cfg.sync_last_n_days > 0
            assert len(cfg.entity_types) > 0
