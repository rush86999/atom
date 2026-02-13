"""
Baseline unit tests for HybridDataIngestionService.

Tests cover initialization, data source routing, data transformation,
and error handling for hybrid data ingestion from integrations.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pytest

from core.hybrid_data_ingestion import (
    HybridDataIngestionService,
    IntegrationUsageStats,
    SyncConfiguration,
    DEFAULT_SYNC_CONFIGS,
    get_hybrid_ingestion_service,
    record_integration_call,
)


# ============================================================================
# Test Classes: Data Classes and Configuration
# ============================================================================

class TestIntegrationUsageStats:
    """Test IntegrationUsageStats dataclass."""

    def test_usage_stats_creation(self):
        """Test IntegrationUsageStats can be created with defaults."""
        stats = IntegrationUsageStats(
            integration_id="salesforce",
            integration_name="Salesforce",
            workspace_id="default"
        )
        assert stats.integration_id == "salesforce"
        assert stats.integration_name == "Salesforce"
        assert stats.workspace_id == "default"
        assert stats.total_calls == 0
        assert stats.successful_calls == 0
        assert stats.last_used is None
        assert stats.last_synced is None
        assert stats.auto_sync_enabled is False
        assert stats.sync_frequency_minutes == 60

    def test_usage_stats_with_values(self):
        """Test IntegrationUsageStats with specific values."""
        now = datetime.utcnow()
        stats = IntegrationUsageStats(
            integration_id="hubspot",
            integration_name="HubSpot",
            workspace_id="default",
            total_calls=100,
            successful_calls=95,
            last_used=now,
            auto_sync_enabled=True,
            sync_frequency_minutes=30
        )
        assert stats.total_calls == 100
        assert stats.successful_calls == 95
        assert stats.last_used == now
        assert stats.auto_sync_enabled is True
        assert stats.sync_frequency_minutes == 30


class TestSyncConfiguration:
    """Test SyncConfiguration dataclass."""

    def test_sync_config_defaults(self):
        """Test SyncConfiguration has correct defaults."""
        config = SyncConfiguration(
            integration_id="test"
        )
        assert config.integration_id == "test"
        assert config.entity_types == []
        assert config.sync_last_n_days == 30
        assert config.max_records_per_sync == 1000
        assert config.include_metadata is True

    def test_sync_config_with_entity_types(self):
        """Test SyncConfiguration with entity types."""
        config = SyncConfiguration(
            integration_id="salesforce",
            entity_types=["contacts", "leads", "opportunities"]
        )
        assert "contacts" in config.entity_types
        assert "leads" in config.entity_types
        assert "opportunities" in config.entity_types

    def test_sync_config_custom_limits(self):
        """Test SyncConfiguration with custom limits."""
        config = SyncConfiguration(
            integration_id="gmail",
            sync_last_n_days=14,
            max_records_per_sync=500
        )
        assert config.sync_last_n_days == 14
        assert config.max_records_per_sync == 500


class TestDefaultSyncConfigs:
    """Test default sync configurations for integrations."""

    def test_default_sync_configs_exist(self):
        """Test DEFAULT_SYNC_CONFIGS dict is populated."""
        assert isinstance(DEFAULT_SYNC_CONFIGS, dict)
        assert len(DEFAULT_SYNC_CONFIGS) > 0

    def test_salesforce_default_config(self):
        """Test Salesforce has default sync config."""
        assert "salesforce" in DEFAULT_SYNC_CONFIGS
        config = DEFAULT_SYNC_CONFIGS["salesforce"]
        assert config.integration_id == "salesforce"
        assert "contacts" in config.entity_types
        assert "leads" in config.entity_types

    def test_hubspot_default_config(self):
        """Test HubSpot has default sync config."""
        assert "hubspot" in DEFAULT_SYNC_CONFIGS
        config = DEFAULT_SYNC_CONFIGS["hubspot"]
        assert "contacts" in config.entity_types
        assert "deals" in config.entity_types

    def test_slack_default_config(self):
        """Test Slack has default sync config."""
        assert "slack" in DEFAULT_SYNC_CONFIGS
        config = DEFAULT_SYNC_CONFIGS["slack"]
        assert "messages" in config.entity_types
        assert config.sync_last_n_days == 7

    def test_gmail_default_config(self):
        """Test Gmail has default sync config."""
        assert "gmail" in DEFAULT_SYNC_CONFIGS
        config = DEFAULT_SYNC_CONFIGS["gmail"]
        assert "emails" in config.entity_types
        assert config.sync_last_n_days == 14


# ============================================================================
# Test Classes: HybridDataIngestionService
# ============================================================================

class TestHybridIngestionInit:
    """Test HybridDataIngestionService initialization."""

    def test_service_initialization(self):
        """Test service initializes with correct defaults."""
        service = HybridDataIngestionService()
        assert service.workspace_id == "default"
        assert isinstance(service.sync_configs, dict)
        assert isinstance(service._sync_tasks, dict)
        assert service._running is False
        assert service.AUTO_SYNC_USAGE_THRESHOLD == 10

    def test_service_has_required_attributes(self):
        """Test service has expected attributes."""
        service = HybridDataIngestionService()
        assert hasattr(service, 'workspace_id')
        assert hasattr(service, 'sync_configs')
        assert hasattr(service, '_sync_tasks')
        assert hasattr(service, 'record_integration_usage')


class TestDataSourceRouting:
    """Test data source selection and routing logic."""

    def test_record_usage_method_exists(self):
        """Test record_integration_usage method exists."""
        service = HybridDataIngestionService()
        assert hasattr(service, 'record_integration_usage')
        assert callable(service.record_integration_usage)

    def test_auto_sync_threshold_constant(self):
        """Test AUTO_SYNC_USAGE_THRESHOLD constant exists."""
        service = HybridDataIngestionService()
        assert hasattr(service, 'AUTO_SYNC_USAGE_THRESHOLD')
        assert service.AUTO_SYNC_USAGE_THRESHOLD == 10

    def test_enable_auto_sync_method_exists(self):
        """Test enable_auto_sync method exists."""
        service = HybridDataIngestionService()
        assert hasattr(service, 'enable_auto_sync')
        assert callable(service.enable_auto_sync)

    def test_disable_auto_sync_method_exists(self):
        """Test disable_auto_sync method exists."""
        service = HybridDataIngestionService()
        assert hasattr(service, 'disable_auto_sync')
        assert callable(service.disable_auto_sync)


class TestDataTransformation:
    """Test data transformation pipelines."""

    def test_record_to_text_method_exists(self):
        """Test _record_to_text method exists."""
        service = HybridDataIngestionService()
        assert hasattr(service, '_record_to_text')
        assert callable(service._record_to_text)

    def test_record_to_text_handles_missing_fields(self):
        """Test record to text handles missing fields gracefully."""
        service = HybridDataIngestionService()
        record = {"type": "lead"}
        text = service._record_to_text(record, "salesforce")
        # Just verify it returns a string
        assert isinstance(text, str)

    def test_record_to_text_includes_priority_fields(self):
        """Test priority fields are included in text."""
        service = HybridDataIngestionService()
        record = {
            "type": "ticket",
            "subject": "Issue #123",
            "status": "open",
            "priority": "high"
        }
        text = service._record_to_text(record, "zendesk")
        assert "subject" in text.lower() or "Issue #123" in text
        assert "status" in text.lower()


class TestSyncOperations:
    """Test sync operations and configuration."""

    def test_enable_auto_sync_method_callable(self):
        """Test enable_auto_sync is callable."""
        service = HybridDataIngestionService()
        assert callable(service.enable_auto_sync)

    def test_disable_auto_sync_method_callable(self):
        """Test disable_auto_sync is callable."""
        service = HybridDataIngestionService()
        assert callable(service.disable_auto_sync)

    def test_get_usage_summary_method_callable(self):
        """Test get_usage_summary is callable."""
        service = HybridDataIngestionService()
        assert callable(service.get_usage_summary)


class TestFetchMethods:
    """Test data fetching from integrations."""

    @pytest.mark.asyncio
    async def test_fetch_integration_data_unknown_returns_empty(self):
        """Test fetching from unknown integration returns empty list."""
        service = HybridDataIngestionService()
        config = SyncConfiguration(integration_id="unknown")
        records = await service._fetch_integration_data("unknown", config)
        assert records == []

    @pytest.mark.asyncio
    async def test_fetch_salesforce_data_method_exists(self):
        """Test _fetch_salesforce_data method exists and is async."""
        service = HybridDataIngestionService()
        import inspect
        assert inspect.iscoroutinefunction(service._fetch_salesforce_data)

    @pytest.mark.asyncio
    async def test_fetch_hubspot_data_method_exists(self):
        """Test _fetch_hubspot_data method exists and is async."""
        service = HybridDataIngestionService()
        import inspect
        assert inspect.iscoroutinefunction(service._fetch_hubspot_data)

    @pytest.mark.asyncio
    async def test_fetch_slack_data_method_exists(self):
        """Test _fetch_slack_data method exists and is async."""
        service = HybridDataIngestionService()
        import inspect
        assert inspect.iscoroutinefunction(service._fetch_slack_data)

    @pytest.mark.asyncio
    async def test_fetch_gmail_data_method_exists(self):
        """Test _fetch_gmail_data method exists and is async."""
        service = HybridDataIngestionService()
        import inspect
        assert inspect.iscoroutinefunction(service._fetch_gmail_data)

    @pytest.mark.asyncio
    async def test_fetch_notion_data_method_exists(self):
        """Test _fetch_notion_data method exists and is async."""
        service = HybridDataIngestionService()
        import inspect
        assert inspect.iscoroutinefunction(service._fetch_notion_data)

    @pytest.mark.asyncio
    async def test_fetch_jira_data_method_exists(self):
        """Test _fetch_jira_data method exists and is async."""
        service = HybridDataIngestionService()
        import inspect
        assert inspect.iscoroutinefunction(service._fetch_jira_data)

    @pytest.mark.asyncio
    async def test_fetch_zendesk_data_method_exists(self):
        """Test _fetch_zendesk_data method exists and is async."""
        service = HybridDataIngestionService()
        import inspect
        assert inspect.iscoroutinefunction(service._fetch_zendesk_data)


class TestScheduledSyncs:
    """Test scheduled sync operations."""

    def test_run_scheduled_syncs_is_async(self):
        """Test run_scheduled_syncs is an async method."""
        import inspect
        assert inspect.iscoroutinefunction(HybridDataIngestionService.run_scheduled_syncs)

    def test_stop_method_exists(self):
        """Test stop method exists."""
        service = HybridDataIngestionService()
        assert hasattr(service, 'stop')
        assert callable(service.stop)


class TestGlobalFunctions:
    """Test global convenience functions."""

    def test_get_hybrid_ingestion_service(self):
        """Test get_hybrid_ingestion_service returns service."""
        service = get_hybrid_ingestion_service()
        assert isinstance(service, HybridDataIngestionService)

    def test_get_hybrid_ingestion_service_returns_singleton(self):
        """Test get_hybrid_ingestion_service returns same instance."""
        service1 = get_hybrid_ingestion_service()
        service2 = get_hybrid_ingestion_service()
        assert service1 is service2

    def test_record_integration_call_callable(self):
        """Test record_integration_call is callable."""
        assert callable(record_integration_call)


class TestSyncErrors:
    """Test error handling in sync operations."""

    @pytest.mark.asyncio
    async def test_sync_integration_data_is_async(self):
        """Test sync_integration_data is async method."""
        service = HybridDataIngestionService()
        import inspect
        assert inspect.iscoroutinefunction(service.sync_integration_data)


class TestRecordToTextEdgeCases:
    """Test edge cases in record to text conversion."""

    def test_record_to_text_empty_record(self):
        """Test converting empty record to text."""
        service = HybridDataIngestionService()
        text = service._record_to_text({}, "test")
        assert isinstance(text, str)

    def test_record_to_text_with_none_values(self):
        """Test converting record with None values."""
        service = HybridDataIngestionService()
        record = {
            "type": "contact",
            "name": None,
            "email": None
        }
        text = service._record_to_text(record, "test")
        assert isinstance(text, str)

    def test_record_to_text_with_complex_values(self):
        """Test converting record with complex nested values."""
        service = HybridDataIngestionService()
        record = {
            "type": "account",
            "name": "Test Account",
            "custom_fields": {"field1": "value1", "field2": "value2"}
        }
        text = service._record_to_text(record, "test")
        assert "Test Account" in text
        assert isinstance(text, str)
