from __future__ import annotations
"""
Webhook Metrics Service

Webhook-specific metrics that extend IntegrationMetrics for monitoring
webhook delivery and processing.

Tracks:
- Webhook delivery metrics (receipt, signature verification, duration)
- Webhook processing metrics (transformation, LLM extraction, entities)
- Delivery rate per provider
- Processing success rate per provider
- Prometheus export with webhook-specific labels

**Metrics:**
- webhook_delivery_count: Counter (by connector_id, tenant_id, status)
- webhook_delivery_duration_ms: Histogram (p50, p95, p99)
- webhook_signature_verification_failures: Counter (by connector_id, tenant_id)
- webhook_processing_count: Counter (by connector_id, tenant_id, status)
- webhook_processing_duration_ms: Histogram (p50, p95, p99)
- webhook_entities_extracted: Counter (by connector_id, tenant_id)
- webhook_transformation_errors: Counter (by connector_id, tenant_id, error_type)

**Requirements:**
- WEBHOOK-02: Metrics track webhook delivery rates
- WEBHOOK-04: Circuit breakers auto-disable failing webhooks
"""

import json
import logging
import time
from collections import defaultdict
from typing import Any, Optional

from core.integration_metrics import IntegrationMetrics, get_integration_metrics

logger = logging.getLogger(__name__)


# =============================================================================
# Webhook Metrics Class
# =============================================================================

class WebhookMetrics(IntegrationMetrics):
    """
    Webhook-specific metrics extending IntegrationMetrics.

    Tracks both webhook delivery (receipt from provider) and processing
    (transformation and LLM extraction) metrics separately.

    **Delivery Metrics** (provider -> webhook endpoint):
    - webhook_delivery_count: Counter by connector_id, tenant_id, status
    - webhook_delivery_duration_ms: Histogram (p50, p95, p99)
    - webhook_signature_verification_failures: Counter by connector_id, tenant_id

    **Processing Metrics** (webhook -> entities):
    - webhook_processing_count: Counter by connector_id, tenant_id, status
    - webhook_processing_duration_ms: Histogram (p50, p95, p99)
    - webhook_entities_extracted: Counter by connector_id, tenant_id
    - webhook_transformation_errors: Counter by connector_id, error_type

    **Usage:**
    ```python
    metrics = WebhookMetrics()

    # Track webhook delivery
    metrics.record_delivery("slack", tenant_id, 45.0, signature_valid=True)

    # Track processing success
    metrics.record_processing_success("slack", tenant_id, 150.0, entities_count=5)

    # Track processing error
    metrics.record_processing_error("slack", tenant_id, "transformation_error", 50.0)

    # Get rates
    delivery_rate = metrics.get_delivery_rate("slack", tenant_id)
    processing_rate = metrics.get_processing_success_rate("slack", tenant_id)

    # Export to Prometheus
    prometheus_output = metrics.export_prometheus()
    ```
    """

    # Singleton instance
    _instance: Optional[WebhookMetrics] = None

    def __init__(self):
        """Initialize webhook metrics collector."""
        super().__init__()

        # Delivery metrics
        self._delivery_counts: dict[str, int] = defaultdict(int)
        self._delivery_duration_samples: dict[str, list] = defaultdict(list)
        self._signature_failures: dict[str, int] = defaultdict(int)

        # Processing metrics
        self._processing_success_counts: dict[str, int] = defaultdict(int)
        self._processing_error_counts: dict[str, int] = defaultdict(int)
        self._processing_error_types: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._processing_duration_samples: dict[str, list] = defaultdict(list)
        self._entities_extracted: dict[str, int] = defaultdict(int)

    @classmethod
    def get_instance(cls) -> WebhookMetrics:
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _make_delivery_key(
        self, connector_id: str, tenant_id: str, status: str
    ) -> str:
        """Create key for delivery metrics."""
        tenant_short = tenant_id[:8] if tenant_id else "unknown"
        return f"{connector_id}:{tenant_short}:delivery:{status}"

    def _make_processing_key(
        self, connector_id: str, tenant_id: str, status: str
    ) -> str:
        """Create key for processing metrics."""
        tenant_short = tenant_id[:8] if tenant_id else "unknown"
        return f"{connector_id}:{tenant_short}:processing:{status}"

    def _make_duration_key(self, connector_id: str, tenant_id: str) -> str:
        """Create key for duration samples."""
        tenant_short = tenant_id[:8] if tenant_id else "unknown"
        return f"{connector_id}:{tenant_short}:duration"

    # -------------------------------------------------------------------------
    # Delivery Metrics
    # -------------------------------------------------------------------------

    def record_delivery(
        self,
        connector_id: str,
        tenant_id: str,
        duration_ms: float,
        signature_valid: bool,
    ) -> None:
        """
        Record webhook delivery (receipt from provider).

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID
            duration_ms: Delivery duration in milliseconds
            signature_valid: Whether signature verification passed
        """
        status = "success" if signature_valid else "signature_error"

        # Increment delivery counter
        key = self._make_delivery_key(connector_id, tenant_id, status)
        self._delivery_counts[key] += 1

        # Track duration
        duration_key = self._make_duration_key(connector_id, tenant_id)
        self._delivery_duration_samples[duration_key].append(duration_ms)

        # Keep only last 1000 samples
        if len(self._delivery_duration_samples[duration_key]) > 1000:
            self._delivery_duration_samples[duration_key] = \
                self._delivery_duration_samples[duration_key][-1000:]

        # Track signature failures
        if not signature_valid:
            sig_key = f"{connector_id}:{tenant_id[:8]}:signature_failures"
            self._signature_failures[sig_key] += 1

        # Also record in base IntegrationMetrics
        self.record_execution_success(
            connector_id=connector_id,
            tenant_id=tenant_id,
            execution_path="webhook",
            operation="delivery",
            start_time=time.time() - (duration_ms / 1000),
        )

    def get_delivery_count(self, connector_id: str, tenant_id: str) -> int:
        """
        Get total delivery count for connector.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID

        Returns:
            Total delivery count
        """
        success_key = self._make_delivery_key(connector_id, tenant_id, "success")
        error_key = self._make_delivery_key(connector_id, tenant_id, "signature_error")

        return self._delivery_counts.get(success_key, 0) + \
               self._delivery_counts.get(error_key, 0)

    def get_delivery_percentiles(
        self, connector_id: str, tenant_id: str
    ) -> dict[str, float]:
        """
        Get delivery duration percentiles.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID

        Returns:
            Dict with p50, p95, p99 duration in milliseconds
        """
        duration_key = self._make_duration_key(connector_id, tenant_id)
        samples = self._delivery_duration_samples.get(duration_key, [])

        if not samples:
            return {"p50": 0, "p95": 0, "p99": 0}

        samples_sorted = sorted(samples)
        n = len(samples_sorted)

        return {
            "p50": samples_sorted[int(n * 0.5)],
            "p95": samples_sorted[int(n * 0.95)],
            "p99": samples_sorted[int(n * 0.99)],
        }

    def get_signature_failure_count(self, connector_id: str, tenant_id: str) -> int:
        """Get signature verification failure count."""
        key = f"{connector_id}:{tenant_id[:8]}:signature_failures"
        return self._signature_failures.get(key, 0)

    # -------------------------------------------------------------------------
    # Processing Metrics
    # -------------------------------------------------------------------------

    def record_processing_success(
        self,
        connector_id: str,
        tenant_id: str,
        duration_ms: float,
        entities_count: int = 0,
    ) -> None:
        """
        Record successful webhook processing (transformation + extraction).

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID
            duration_ms: Processing duration in milliseconds
            entities_count: Number of entities extracted
        """
        key = self._make_processing_key(connector_id, tenant_id, "success")
        self._processing_success_counts[key] += 1

        # Track processing duration
        duration_key = self._make_duration_key(connector_id, tenant_id)
        self._processing_duration_samples[duration_key].append(duration_ms)

        # Keep only last 1000 samples
        if len(self._processing_duration_samples[duration_key]) > 1000:
            self._processing_duration_samples[duration_key] = \
                self._processing_duration_samples[duration_key][-1000:]

        # Track entities extracted
        entity_key = f"{connector_id}:{tenant_id[:8]}:entities"
        self._entities_extracted[entity_key] += entities_count

        # Also record in base IntegrationMetrics
        self.record_execution_success(
            connector_id=connector_id,
            tenant_id=tenant_id,
            execution_path="webhook",
            operation="processing",
            start_time=time.time() - (duration_ms / 1000),
        )

    def record_processing_error(
        self,
        connector_id: str,
        tenant_id: str,
        error_type: str,
        duration_ms: float = 0,
    ) -> None:
        """
        Record webhook processing error.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID
            error_type: Type of error (transformation_error, llm_error, etc.)
            duration_ms: Processing duration before error
        """
        key = self._make_processing_key(connector_id, tenant_id, "error")
        self._processing_error_counts[key] += 1

        # Track error by type
        error_type_key = f"{connector_id}:{tenant_id[:8]}:errors"
        self._processing_error_types[error_type_key][error_type] += 1

        # Track processing duration
        if duration_ms > 0:
            duration_key = self._make_duration_key(connector_id, tenant_id)
            self._processing_duration_samples[duration_key].append(duration_ms)

        # Also record in base IntegrationMetrics
        self.record_execution_error(
            connector_id=connector_id,
            tenant_id=tenant_id,
            execution_path="webhook",
            operation="processing",
            error_code=error_type,
            start_time=time.time() - (duration_ms / 1000),
        )

    def get_processing_success_count(self, connector_id: str, tenant_id: str) -> int:
        """Get processing success count."""
        key = self._make_processing_key(connector_id, tenant_id, "success")
        return self._processing_success_counts.get(key, 0)

    def get_processing_error_count(self, connector_id: str, tenant_id: str) -> int:
        """Get processing error count."""
        key = self._make_processing_key(connector_id, tenant_id, "error")
        return self._processing_error_counts.get(key, 0)

    def get_processing_errors_by_type(
        self, connector_id: str, tenant_id: str
    ) -> dict[str, int]:
        """Get processing errors broken down by type."""
        key = f"{connector_id}:{tenant_id[:8]}:errors"
        return dict(self._processing_error_types.get(key, {}))

    def get_processing_percentiles(
        self, connector_id: str, tenant_id: str
    ) -> dict[str, float]:
        """Get processing duration percentiles."""
        duration_key = self._make_duration_key(connector_id, tenant_id)
        samples = self._processing_duration_samples.get(duration_key, [])

        if not samples:
            return {"p50": 0, "p95": 0, "p99": 0}

        samples_sorted = sorted(samples)
        n = len(samples_sorted)

        return {
            "p50": samples_sorted[int(n * 0.5)],
            "p95": samples_sorted[int(n * 0.95)],
            "p99": samples_sorted[int(n * 0.99)],
        }

    def get_entities_extracted_count(self, connector_id: str, tenant_id: str) -> int:
        """Get total entities extracted count."""
        key = f"{connector_id}:{tenant_id[:8]}:entities"
        return self._entities_extracted.get(key, 0)

    # -------------------------------------------------------------------------
    # Rate Calculations
    # -------------------------------------------------------------------------

    def get_delivery_rate(self, connector_id: str, tenant_id: str) -> float:
        """
        Get webhook delivery success rate.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID

        Returns:
            Success rate as percentage (0-100)
        """
        success_key = self._make_delivery_key(connector_id, tenant_id, "success")
        error_key = self._make_delivery_key(connector_id, tenant_id, "signature_error")

        successes = self._delivery_counts.get(success_key, 0)
        failures = self._delivery_counts.get(error_key, 0)
        total = successes + failures

        if total == 0:
            return 100.0  # No failures yet

        return (successes / total) * 100

    def get_processing_success_rate(self, connector_id: str, tenant_id: str) -> float:
        """
        Get webhook processing success rate.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID

        Returns:
            Success rate as percentage (0-100)
        """
        success_key = self._make_processing_key(connector_id, tenant_id, "success")
        error_key = self._make_processing_key(connector_id, tenant_id, "error")

        successes = self._processing_success_counts.get(success_key, 0)
        failures = self._processing_error_counts.get(error_key, 0)
        total = successes + failures

        if total == 0:
            return 100.0  # No failures yet

        return (successes / total) * 100

    def get_total_deliveries(self, connector_id: str) -> int:
        """Get total deliveries across all tenants for a connector."""
        total = 0
        for key, count in self._delivery_counts.items():
            if key.startswith(f"{connector_id}:") and ":delivery:" in key:
                total += count
        return total

    # -------------------------------------------------------------------------
    # Prometheus Export
    # -------------------------------------------------------------------------

    def export_prometheus(self) -> str:
        """
        Export metrics in Prometheus format.

        Extends base IntegrationMetrics.export_prometheus() with
        webhook-specific metrics.

        Returns:
            Prometheus-compatible metrics text
        """
        lines = []

        # Get base metrics
        base_metrics = super().export_prometheus()
        if base_metrics:
            lines.append(base_metrics)

        # Webhook delivery counts
        for key, count in self._delivery_counts.items():
            parts = key.split(":")
            connector_id, tenant_id, _, status = parts[:4]

            labels = f'connector_id="{connector_id}",tenant_id="{tenant_id}",status="{status}"'
            lines.append(f"webhook_delivery_count{{{labels}}} {count}")

        # Webhook delivery duration percentiles
        for key, samples in self._delivery_duration_samples.items():
            if not samples:
                continue

            parts = key.split(":")
            connector_id, tenant_id = parts[:2]

            percentiles = self.get_delivery_percentiles(connector_id, tenant_id)
            labels = f'connector_id="{connector_id}",tenant_id="{tenant_id}"'

            lines.append('webhook_delivery_duration_ms{{{labels},p="50"}} {p50}'.format(labels=labels, p50=percentiles["p50"]))
            lines.append('webhook_delivery_duration_ms{{{labels},p="95"}} {p95}'.format(labels=labels, p95=percentiles["p95"]))
            lines.append('webhook_delivery_duration_ms{{{labels},p="99"}} {p99}'.format(labels=labels, p99=percentiles["p99"]))

        # Signature verification failures
        for key, count in self._signature_failures.items():
            parts = key.split(":")
            connector_id, tenant_id = parts[:2]

            labels = f'connector_id="{connector_id}",tenant_id="{tenant_id}"'
            lines.append(f"webhook_signature_verification_failures{{{labels}}} {count}")

        # Webhook processing counts
        for key, count in self._processing_success_counts.items():
            parts = key.split(":")
            connector_id, tenant_id, _, status = parts[:4]

            labels = f'connector_id="{connector_id}",tenant_id="{tenant_id}",status="{status}"'
            lines.append(f"webhook_processing_count{{{labels}}} {count}")

        # Webhook processing duration percentiles
        for key, samples in self._processing_duration_samples.items():
            if not samples:
                continue

            parts = key.split(":")
            connector_id, tenant_id = parts[:2]

            percentiles = self.get_processing_percentiles(connector_id, tenant_id)
            labels = f'connector_id="{connector_id}",tenant_id="{tenant_id}"'

            lines.append('webhook_processing_duration_ms{{{labels},p="50"}} {p50}'.format(labels=labels, p50=percentiles["p50"]))
            lines.append('webhook_processing_duration_ms{{{labels},p="95"}} {p95}'.format(labels=labels, p95=percentiles["p95"]))
            lines.append('webhook_processing_duration_ms{{{labels},p="99"}} {p99}'.format(labels=labels, p99=percentiles["p99"]))

        # Entities extracted
        for key, count in self._entities_extracted.items():
            parts = key.split(":")
            connector_id, tenant_id = parts[:2]

            labels = f'connector_id="{connector_id}",tenant_id="{tenant_id}"'
            lines.append(f"webhook_entities_extracted{{{labels}}} {count}")

        # Processing errors by type
        for key, errors in self._processing_error_types.items():
            parts = key.split(":")
            connector_id, tenant_id = parts[:2]

            for error_type, count in errors.items():
                labels = f'connector_id="{connector_id}",tenant_id="{tenant_id}",error_type="{error_type}"'
                lines.append(f"webhook_transformation_errors{{{labels}}} {count}")

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def persist_to_redis(self, redis_client) -> None:
        """
        Persist metrics to Redis.

        Args:
            redis_client: Redis client instance
        """
        if not redis_client:
            return

        # Persist all metrics to Redis
        metrics_data = {
            "delivery_counts": dict(self._delivery_counts),
            "processing_success_counts": dict(self._processing_success_counts),
            "processing_error_counts": dict(self._processing_error_counts),
            "signature_failures": dict(self._signature_failures),
            "entities_extracted": dict(self._entities_extracted),
        }

        try:
            redis_key = "webhook:metrics:current"
            redis_client.setex(
                redis_key,
                3600,  # 1 hour TTL
                json.dumps(metrics_data),
            )
            logger.debug(f"Persisted webhook metrics to {redis_key}")
        except Exception as e:
            logger.error(f"Failed to persist webhook metrics: {e}")


# =============================================================================
# Module-Level Convenience Functions
# =============================================================================

def record_webhook_delivery(
    connector_id: str,
    tenant_id: str,
    duration_ms: float,
    signature_valid: bool,
) -> None:
    """
    Record webhook delivery using singleton instance.

    Args:
        connector_id: Integration identifier
        tenant_id: Tenant UUID
        duration_ms: Delivery duration in milliseconds
        signature_valid: Whether signature verification passed
    """
    metrics = WebhookMetrics.get_instance()
    metrics.record_delivery(connector_id, tenant_id, duration_ms, signature_valid)


def record_webhook_processing_success(
    connector_id: str,
    tenant_id: str,
    duration_ms: float,
    entities_count: int = 0,
) -> None:
    """
    Record webhook processing success using singleton instance.

    Args:
        connector_id: Integration identifier
        tenant_id: Tenant UUID
        duration_ms: Processing duration in milliseconds
        entities_count: Number of entities extracted
    """
    metrics = WebhookMetrics.get_instance()
    metrics.record_processing_success(
        connector_id, tenant_id, duration_ms, entities_count
    )


def record_webhook_processing_error(
    connector_id: str,
    tenant_id: str,
    error_type: str,
    duration_ms: float = 0,
) -> None:
    """
    Record webhook processing error using singleton instance.

    Args:
        connector_id: Integration identifier
        tenant_id: Tenant UUID
        error_type: Type of error
        duration_ms: Processing duration before error
    """
    metrics = WebhookMetrics.get_instance()
    metrics.record_processing_error(connector_id, tenant_id, error_type, duration_ms)


# Singleton instance for convenient access
_webhook_metrics = WebhookMetrics()


def get_webhook_metrics() -> WebhookMetrics:
    """
    Get the singleton WebhookMetrics instance.

    Returns:
        WebhookMetrics instance
    """
    return _webhook_metrics
