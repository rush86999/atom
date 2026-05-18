from __future__ import annotations

"""
TDD Tests for Webhook Metrics Service (Task 2)

Tests webhook-specific metrics that extend IntegrationMetrics:
- WebhookMetrics.record_delivery() tracks successful webhook receipt
- WebhookMetrics.record_processing_error() tracks transformation/LLM failures
- WebhookMetrics.get_delivery_rate() returns % successful by provider
- WebhookMetrics.export_prometheus() includes webhook-specific labels
- Metrics distinguish between delivery (receipt) and processing (extraction)
"""

import time
from unittest.mock import MagicMock, AsyncMock

import pytest

from core.webhook_metrics import (
    WebhookMetrics,
    record_webhook_delivery,
    record_webhook_processing_success,
    record_webhook_processing_error,
)


@pytest.fixture
def webhook_metrics():
    """Create a fresh WebhookMetrics instance for each test."""
    return WebhookMetrics()


class TestRecordWebhookDelivery:
    """Test 1: WebhookMetrics.record_delivery() tracks successful webhook receipt"""

    def test_record_delivery_increments_counter(self, webhook_metrics):
        """record_delivery increments the delivery counter."""
        connector_id = "slack"
        tenant_id = "tenant-123"
        duration_ms = 45.0
        signature_valid = True

        webhook_metrics.record_delivery(
            connector_id=connector_id,
            tenant_id=tenant_id,
            duration_ms=duration_ms,
            signature_valid=signature_valid,
        )

        assert webhook_metrics.get_delivery_count(connector_id, tenant_id) == 1

    def test_record_delivery_tracks_duration(self, webhook_metrics):
        """record_delivery tracks delivery duration for percentiles."""
        connector_id = "slack"
        tenant_id = "tenant-123"

        durations = [10, 20, 30, 40, 50]
        for d in durations:
            webhook_metrics.record_delivery(
                connector_id=connector_id,
                tenant_id=tenant_id,
                duration_ms=float(d),
                signature_valid=True,
            )

        percentiles = webhook_metrics.get_delivery_percentiles(connector_id, tenant_id)
        assert percentiles["p50"] == 30
        assert percentiles["p95"] == 50
        assert percentiles["p99"] == 50

    def test_record_delivery_tracks_signature_validation(self, webhook_metrics):
        """record_delivery tracks signature verification failures."""
        connector_id = "slack"
        tenant_id = "tenant-123"

        webhook_metrics.record_delivery(
            connector_id=connector_id,
            tenant_id=tenant_id,
            duration_ms=10.0,
            signature_valid=False,
        )

        assert webhook_metrics.get_signature_failure_count(connector_id, tenant_id) == 1

    def test_record_delivery_multiple_tenants(self, webhook_metrics):
        """record_delivery correctly tracks metrics per tenant."""
        webhook_metrics.record_delivery("slack", "tenant-1", 10.0, True)
        webhook_metrics.record_delivery("slack", "tenant-2", 20.0, True)

        assert webhook_metrics.get_delivery_count("slack", "tenant-1") == 1
        assert webhook_metrics.get_delivery_count("slack", "tenant-2") == 1


class TestRecordWebhookProcessing:
    """Test 2: WebhookMetrics.record_processing_error() tracks transformation/LLM failures"""

    def test_record_processing_success_increments_counter(self, webhook_metrics):
        """record_processing_success increments processing counter."""
        connector_id = "slack"
        tenant_id = "tenant-123"
        duration_ms = 150.0
        entities_count = 5

        webhook_metrics.record_processing_success(
            connector_id=connector_id,
            tenant_id=tenant_id,
            duration_ms=duration_ms,
            entities_count=entities_count,
        )

        assert webhook_metrics.get_processing_success_count(connector_id, tenant_id) == 1

    def test_record_processing_success_tracks_entities(self, webhook_metrics):
        """record_processing_success tracks extracted entities count."""
        webhook_metrics.record_processing_success(
            connector_id="slack",
            tenant_id="tenant-123",
            duration_ms=100.0,
            entities_count=5,
        )
        webhook_metrics.record_processing_success(
            connector_id="slack",
            tenant_id="tenant-123",
            duration_ms=100.0,
            entities_count=3,
        )

        assert webhook_metrics.get_entities_extracted_count("slack", "tenant-123") == 8

    def test_record_processing_error_increments_error_counter(self, webhook_metrics):
        """record_processing_error increments error counter."""
        webhook_metrics.record_processing_error(
            connector_id="slack",
            tenant_id="tenant-123",
            error_type="transformation_error",
            duration_ms=50.0,
        )

        assert webhook_metrics.get_processing_error_count("slack", "tenant-123") == 1

    def test_record_processing_error_categorizes_by_type(self, webhook_metrics):
        """record_processing_error categorizes errors by type."""
        webhook_metrics.record_processing_error(
            connector_id="slack",
            tenant_id="tenant-123",
            error_type="transformation_error",
            duration_ms=50.0,
        )
        webhook_metrics.record_processing_error(
            connector_id="slack",
            tenant_id="tenant-123",
            error_type="llm_extraction_error",
            duration_ms=100.0,
        )

        errors = webhook_metrics.get_processing_errors_by_type("slack", "tenant-123")
        assert errors.get("transformation_error", 0) == 1
        assert errors.get("llm_extraction_error", 0) == 1


class TestGetDeliveryRate:
    """Test 3: WebhookMetrics.get_delivery_rate() returns % successful by provider"""

    def test_get_delivery_rate_all_successful(self, webhook_metrics):
        """get_delivery_rate returns 100% when all deliveries succeed."""
        connector_id = "slack"
        tenant_id = "tenant-123"

        webhook_metrics.record_delivery(connector_id, tenant_id, 10.0, True)
        webhook_metrics.record_delivery(connector_id, tenant_id, 10.0, True)
        webhook_metrics.record_delivery(connector_id, tenant_id, 10.0, True)

        rate = webhook_metrics.get_delivery_rate(connector_id, tenant_id)
        assert rate == 100.0

    def test_get_delivery_rate_with_failures(self, webhook_metrics):
        """get_delivery_rate calculates percentage with failures."""
        connector_id = "slack"
        tenant_id = "tenant-123"

        webhook_metrics.record_delivery(connector_id, tenant_id, 10.0, True)
        webhook_metrics.record_delivery(connector_id, tenant_id, 10.0, True)
        webhook_metrics.record_delivery(connector_id, tenant_id, 10.0, False)

        rate = webhook_metrics.get_delivery_rate(connector_id, tenant_id)
        assert rate == 66.66666666666666

    def test_get_delivery_rate_no_deliveries(self, webhook_metrics):
        """get_delivery_rate returns 100% when no deliveries recorded."""
        rate = webhook_metrics.get_delivery_rate("slack", "tenant-123")
        assert rate == 100.0

    def test_get_processing_success_rate(self, webhook_metrics):
        """get_processing_success_rate returns processing success percentage."""
        connector_id = "slack"
        tenant_id = "tenant-123"

        webhook_metrics.record_processing_success(connector_id, tenant_id, 100.0, 5)
        webhook_metrics.record_processing_success(connector_id, tenant_id, 100.0, 3)
        webhook_metrics.record_processing_error(
            connector_id, tenant_id, "llm_error", 50.0
        )

        rate = webhook_metrics.get_processing_success_rate(connector_id, tenant_id)
        assert rate == 66.66666666666666


class TestExportPrometheus:
    """Test 4: WebhookMetrics.export_prometheus() includes webhook-specific labels"""

    def test_export_prometheus_includes_delivery_metrics(self, webhook_metrics):
        """export_prometheus includes webhook delivery metrics."""
        webhook_metrics.record_delivery("slack", "tenant-123", 10.0, True)

        prometheus_output = webhook_metrics.export_prometheus()

        assert "webhook_delivery_count" in prometheus_output
        assert 'connector_id="slack"' in prometheus_output
        # Tenant ID is truncated to 8 characters
        assert 'tenant_id="tenant-1"' in prometheus_output

    def test_export_prometheus_includes_processing_metrics(self, webhook_metrics):
        """export_prometheus includes webhook processing metrics."""
        webhook_metrics.record_processing_success("slack", "tenant-456", 100.0, 5)

        prometheus_output = webhook_metrics.export_prometheus()

        assert "webhook_processing_count" in prometheus_output
        assert 'status="success"' in prometheus_output
        assert 'connector_id="slack"' in prometheus_output

    def test_export_prometheus_includes_entity_counts(self, webhook_metrics):
        """export_prometheus includes extracted entity counts."""
        webhook_metrics.record_processing_success("slack", "tenant-789", 100.0, 5)

        prometheus_output = webhook_metrics.export_prometheus()

        assert "webhook_entities_extracted" in prometheus_output
        assert "5" in prometheus_output  # Entity count is in the output

    def test_export_prometheus_includes_signature_failures(self, webhook_metrics):
        """export_prometheus includes signature verification failures."""
        webhook_metrics.record_delivery("slack", "tenant-abc", 10.0, False)

        prometheus_output = webhook_metrics.export_prometheus()

        assert "webhook_signature_verification_failures" in prometheus_output


class TestDeliveryVsProcessingDistinction:
    """Test 5: Metrics distinguish between delivery (receipt) and processing (extraction)"""

    def test_delivery_and_processing_are_separate(self, webhook_metrics):
        """Delivery and processing metrics are tracked separately."""
        connector_id = "slack"
        tenant_id = "tenant-123"

        # Record delivery
        webhook_metrics.record_delivery(connector_id, tenant_id, 10.0, True)

        # Record processing
        webhook_metrics.record_processing_success(connector_id, tenant_id, 100.0, 5)

        # Both should be tracked separately
        assert webhook_metrics.get_delivery_count(connector_id, tenant_id) == 1
        assert webhook_metrics.get_processing_success_count(connector_id, tenant_id) == 1

    def test_delivery_can_succeed_while_processing_fails(self, webhook_metrics):
        """Webhook can be delivered but processing can fail."""
        connector_id = "slack"
        tenant_id = "tenant-123"

        # Delivery succeeds (signature valid)
        webhook_metrics.record_delivery(connector_id, tenant_id, 10.0, True)

        # Processing fails
        webhook_metrics.record_processing_error(
            connector_id, tenant_id, "transformation_error", 50.0
        )

        assert webhook_metrics.get_delivery_rate(connector_id, tenant_id) == 100.0
        assert webhook_metrics.get_processing_success_rate(connector_id, tenant_id) == 0.0

    def test_end_to_end_webhook_flow_metrics(self, webhook_metrics):
        """Complete webhook flow tracks both delivery and processing."""
        connector_id = "slack"
        tenant_id = "tenant-123"

        # Webhook received and delivered
        webhook_metrics.record_delivery(connector_id, tenant_id, 10.0, True)

        # Payload processed successfully
        webhook_metrics.record_processing_success(connector_id, tenant_id, 150.0, 5)

        # Check combined metrics
        assert webhook_metrics.get_delivery_count(connector_id, tenant_id) == 1
        assert webhook_metrics.get_processing_success_count(connector_id, tenant_id) == 1
        assert webhook_metrics.get_entities_extracted_count(connector_id, tenant_id) == 5


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    def test_record_webhook_delivery_function(self, webhook_metrics):
        """Module-level record_webhook_delivery function works."""
        record_webhook_delivery("slack", "tenant-123", 10.0, True)

        # Verify it was recorded in singleton instance
        metrics = WebhookMetrics.get_instance()
        assert metrics.get_delivery_count("slack", "tenant-123") >= 1

    def test_record_webhook_processing_success_function(self, webhook_metrics):
        """Module-level record_webhook_processing_success function works."""
        record_webhook_processing_success("slack", "tenant-123", 100.0, 5)

        metrics = WebhookMetrics.get_instance()
        assert metrics.get_processing_success_count("slack", "tenant-123") >= 1

    def test_record_webhook_processing_error_function(self, webhook_metrics):
        """Module-level record_webhook_processing_error function works."""
        record_webhook_processing_error("slack", "tenant-123", "test_error", 50.0)

        metrics = WebhookMetrics.get_instance()
        assert metrics.get_processing_error_count("slack", "tenant-123") >= 1


class TestIntegrationWithIntegrationMetrics:
    """Test integration with base IntegrationMetrics class."""

    def test_extends_integration_metrics(self, webhook_metrics):
        """WebhookMetrics extends IntegrationMetrics functionality."""
        from core.integration_metrics import IntegrationMetrics

        assert isinstance(webhook_metrics, IntegrationMetrics)

    def test_uses_webhook_execution_path(self, webhook_metrics):
        """Webhook metrics use 'webhook' execution path."""
        webhook_metrics.record_processing_success("slack", "tenant-123", 100.0, 5)

        # Check that execution_path is set to webhook
        prometheus_output = webhook_metrics.export_prometheus()
        assert 'execution_path="webhook"' in prometheus_output


class TestMetricsPersistence:
    """Test metrics persistence and aggregation."""

    def test_metrics_persist_to_redis(self, webhook_metrics, mock_redis_client):
        """Metrics can be persisted to Redis."""
        webhook_metrics.record_delivery("slack", "tenant-123", 10.0, True)

        # Simulate Redis persistence
        webhook_metrics.persist_to_redis(mock_redis_client)

        # Verify Redis was called (setex is used for persistence)
        assert mock_redis_client.setex.called

    def test_metrics_aggregation_by_provider(self, webhook_metrics):
        """Metrics can be aggregated by provider across tenants."""
        webhook_metrics.record_delivery("slack", "tenant-1", 10.0, True)
        webhook_metrics.record_delivery("slack", "tenant-2", 10.0, True)
        webhook_metrics.record_delivery("hubspot", "tenant-1", 10.0, True)

        slack_total = webhook_metrics.get_total_deliveries("slack")
        hubspot_total = webhook_metrics.get_total_deliveries("hubspot")

        assert slack_total == 2
        assert hubspot_total == 1
