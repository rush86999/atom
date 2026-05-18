from __future__ import annotations
"""
Integration Metrics

Collects and exports metrics for integration execution monitoring.

**Metrics:**
- integration_execution_duration: Histogram (p50, p95, p99)
- integration_execution_count: Counter (by connector_id, status, execution_path)
- integration_success_rate: Gauge (by connector_id)
- integration_failure_rate: Gauge (by connector_id)
- circuit_breaker_state: Gauge (by connector_id, tenant_id)
- rate_limit_remaining: Gauge (by connector_id, tenant_id)

**Requirements:**
- STD-11: Metrics exported by connector_id
- STD-12: Alert thresholds configured
"""
import json
import logging
import time
import asyncio
from collections import defaultdict
from typing import Optional, Union

logger = logging.getLogger(__name__)


class IntegrationMetrics:
    """
    Metrics collector for integration execution.

    **Features:**
    - Execution duration tracking (p50, p95, p99)
    - Success/failure counters by connector
    - Success/failure rate gauges
    - Distinguish workflow vs agent usage
    - In-memory storage (Redis-based in production)
    - Prometheus-compatible export format

    **Labels:**
    - connector_id: Integration identifier
    - tenant_id: Tenant UUID (first 8 chars)
    - execution_path: "workflow" or "agent"
    - operation: Operation name
    - status: "success" or "error"
    """

    def __init__(self):
        """Initialize metrics collector."""
        # Execution duration histogram (ms)
        self.duration_samples: dict[str, list] = defaultdict(list)

        # Execution counters
        self.execution_counters: dict[str, int] = defaultdict(int)

        # Success/failure tracking
        self.success_counts: dict[str, int] = defaultdict(int)
        self.failure_counts: dict[str, int] = defaultdict(int)

        # Circuit breaker state
        self.circuit_breaker_states: dict[str, str] = {}

        # Rate limit tracking
        self.rate_limit_remaining: dict[str, int] = {}
        self.rate_limit_exceeded_count: dict[str, int] = defaultdict(int)

        # Alert trigger cooldown (prevent Redis event storms)
        # key: (connector_id, tenant_id, metric_type), value: last_sent_timestamp
        self._last_trigger_sent: dict[tuple, float] = {}

    def _make_key(
        self,
        connector_id: str,
        tenant_id: str,
        execution_path: str,
        operation: Union[str, None] = None,
        status: Union[str, None] = None,
    ) -> str:
        """
        Create metrics key from labels.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID (will be truncated)
            execution_path: "workflow" or "agent"
            operation: Optional operation name
            status: Optional status ("success" or "error")

        Returns:
            Metrics key string
        """
        tenant_short = tenant_id[:8] if tenant_id else "unknown"
        key_parts = [connector_id, tenant_short, execution_path]

        if operation:
            key_parts.append(operation)

        if status:
            key_parts.append(status)

        return ":".join(key_parts)

    def record_execution_start(
        self, connector_id: str, tenant_id: str, execution_path: str, operation: str
    ) -> float:
        """
        Record execution start time.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID
            execution_path: "workflow" or "agent"
            operation: Operation name

        Returns:
            Start timestamp for duration calculation
        """
        return time.time()

    def record_execution_success(
        self,
        connector_id: str,
        tenant_id: str,
        execution_path: str,
        operation: str,
        start_time: float,
        redis_client=None,
    ):
        """
        Record successful integration execution.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID
            execution_path: "workflow" or "agent"
            operation: Operation name
            start_time: Start timestamp from record_execution_start
            redis_client: Optional Redis client for publishing alert triggers
        """
        duration_ms = (time.time() - start_time) * 1000

        # Record duration
        key = self._make_key(connector_id, tenant_id, execution_path, operation)
        self.duration_samples[key].append(duration_ms)

        # Keep only last 1000 samples per key
        if len(self.duration_samples[key]) > 1000:
            self.duration_samples[key] = self.duration_samples[key][-1000:]

        # Increment success counter
        success_key = self._make_key(connector_id, tenant_id, execution_path)
        self.success_counts[success_key] += 1

        # Increment execution counter
        exec_key = self._make_key(connector_id, tenant_id, execution_path, operation, "success")
        self.execution_counters[exec_key] += 1

        # Publish alert triggers for both error rate and latency
        self.publish_alert_trigger(connector_id, tenant_id, "error_rate", redis_client)
        self.publish_alert_trigger(connector_id, tenant_id, "latency_p95", redis_client)

    def record_execution_error(
        self,
        connector_id: str,
        tenant_id: str,
        execution_path: str,
        operation: str,
        error_code: str,
        start_time: float,
        redis_client=None,
    ):
        """
        Record failed integration execution.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID
            execution_path: "workflow" or "agent"
            operation: Operation name
            error_code: Structured error code
            start_time: Start timestamp from record_execution_start
            redis_client: Optional Redis client for publishing alert triggers
        """
        duration_ms = (time.time() - start_time) * 1000

        # Record duration (even for errors)
        key = self._make_key(connector_id, tenant_id, execution_path, operation)
        self.duration_samples[key].append(duration_ms)

        # Keep only last 1000 samples per key
        if len(self.duration_samples[key]) > 1000:
            self.duration_samples[key] = self.duration_samples[key][-1000:]

        # Increment failure counter
        failure_key = self._make_key(connector_id, tenant_id, execution_path)
        self.failure_counts[failure_key] += 1

        # Increment execution counter
        exec_key = self._make_key(connector_id, tenant_id, execution_path, operation, "error")
        self.execution_counters[exec_key] += 1

        # Publish alert triggers for both error rate and latency
        self.publish_alert_trigger(connector_id, tenant_id, "error_rate", redis_client)
        self.publish_alert_trigger(connector_id, tenant_id, "latency_p95", redis_client)

    def record_circuit_breaker_state(self, connector_id: str, tenant_id: str, state: str):
        """
        Record circuit breaker state.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID
            state: "closed", "open", or "half_open"
        """
        key = self._make_key(connector_id, tenant_id, "circuit_breaker")
        self.circuit_breaker_states[key] = state

    def record_rate_limit_remaining(self, connector_id: str, tenant_id: str, tokens_remaining: int):
        """
        Record rate limit token count.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID
            tokens_remaining: Current token count
        """
        key = self._make_key(connector_id, tenant_id, "rate_limit")
        self.rate_limit_remaining[key] = tokens_remaining

    def record_rate_limit_exceeded(self, connector_id: str, tenant_id: str):
        """
        Record rate limit exceeded event.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID
        """
        key = self._make_key(connector_id, tenant_id, "rate_limit")
        self.rate_limit_exceeded_count[key] += 1

    def publish_alert_trigger(
        self,
        connector_id: str,
        tenant_id: str,
        metric_type: str,
        redis_client=None
    ):
        """
        Publish alert trigger event to Redis pub/sub with throttling.

        This notifies the alert worker to evaluate thresholds for this metric.
        Uses an in-memory cooldown to prevent publishing massive amounts of events.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID
            metric_type: Type of metric ("error_rate", "latency_p95")
            redis_client: Optional Redis client (defaults to redis_cache if None)
        """
        # 1. Check in-memory cooldown (prevent event storm)
        now = time.time()
        cooldown_key = (connector_id, tenant_id, metric_type)
        last_sent = self._last_trigger_sent.get(cooldown_key, 0)

        # Default 30s cooldown for alert evaluations
        if now - last_sent < 30:
            return

        try:
            # Prepare evaluation task
            task_data = {
                "tenant_id": tenant_id,
                "connector_id": connector_id,
                "metric_type": metric_type,
                "timestamp": now,
                "trigger_source": "integration_metrics"
            }

            # Import QStash worker inside function to avoid circular imports
            try:
                from core.qstash_worker import enqueue_task
                
                # Enqueue a re-evaluation task
                # non-critical is fine here as it's an automated health check
                asyncio.create_task(enqueue_task(
                    "evaluate_alert", 
                    task_data,
                    critical=False
                ))
                
                # Update last sent timestamp to prevent flooding
                self._last_trigger_sent[cooldown_key] = now
                logger.debug(f"Enqueued throttled QStash evaluation for {connector_id}/{metric_type}")
                
            except ImportError:
                # Fallback to legacy Redis Pub/Sub if QStash is not available
                # this ensures we don't break functionality during migration
                if not redis_client:
                    # Try to get Redis client from cache
                    from core.cache import redis_cache
                    redis_client = redis_cache.client if hasattr(redis_cache, "client") else None
                
                if redis_client:
                    channel = f"alert_triggers:{tenant_id}:{connector_id}"
                    redis_client.publish(channel, json.dumps(task_data))
                    self._last_trigger_sent[cooldown_key] = now
                    logger.debug(f"Published fallback Redis trigger for {metric_type}")

        except Exception as e:
            logger.debug(f"Failed to publish alert trigger: {e}")

    def get_duration_percentiles(
        self, connector_id: str, tenant_id: str, execution_path: str, operation: str
    ) -> dict[str, float]:
        """
        Get duration percentiles for specific operation.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID
            execution_path: "workflow" or "agent"
            operation: Operation name

        Returns:
            Dict with p50, p95, p99 duration in milliseconds
        """
        key = self._make_key(connector_id, tenant_id, execution_path, operation)
        samples = self.duration_samples.get(key, [])

        if not samples:
            return {"p50": 0, "p95": 0, "p99": 0}

        samples_sorted = sorted(samples)
        n = len(samples_sorted)

        return {
            "p50": samples_sorted[int(n * 0.5)],
            "p95": samples_sorted[int(n * 0.95)],
            "p99": samples_sorted[int(n * 0.99)],
        }

    def get_success_rate(self, connector_id: str, tenant_id: str, execution_path: str) -> float:
        """
        Get success rate for connector.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID
            execution_path: "workflow" or "agent"

        Returns:
            Success rate as percentage (0-100)
        """
        key = self._make_key(connector_id, tenant_id, execution_path)
        successes = self.success_counts.get(key, 0)
        failures = self.failure_counts.get(key, 0)
        total = successes + failures

        if total == 0:
            return 100.0  # No failures yet = 100% success

        return (successes / total) * 100

    def export_prometheus(self) -> str:
        """
        Export metrics in Prometheus format.

        Returns:
            Prometheus-compatible metrics text
        """
        lines = []

        # Execution duration histograms
        for key, samples in self.duration_samples.items():
            if not samples:
                continue

            parts = key.split(":")
            connector_id, tenant_id, execution_path, operation = parts[:4]

            percentiles = self.get_duration_percentiles(
                connector_id, tenant_id, execution_path, operation
            )

            labels = f'connector_id="{connector_id}",tenant_id="{tenant_id}",execution_path="{execution_path}",operation="{operation}"'

            # Use format() to avoid f-string brace escaping issues
            lines.append(
                'integration_execution_duration_ms{{{labels},p="50"}} {p50}'.format(
                    labels=labels, p50=percentiles["p50"]
                )
            )
            lines.append(
                'integration_execution_duration_ms{{{labels},p="95"}} {p95}'.format(
                    labels=labels, p95=percentiles["p95"]
                )
            )
            lines.append(
                'integration_execution_duration_ms{{{labels},p="99"}} {p99}'.format(
                    labels=labels, p99=percentiles["p99"]
                )
            )

        # Execution counters
        for key, count in self.execution_counters.items():
            parts = key.split(":")
            connector_id, tenant_id, execution_path = parts[:3]
            operation = parts[3] if len(parts) > 3 else ""
            status = parts[4] if len(parts) > 4 else ""

            labels = f'connector_id="{connector_id}",tenant_id="{tenant_id}",execution_path="{execution_path}"'
            if operation:
                labels += f',operation="{operation}"'
            if status:
                labels += f',status="{status}"'

            lines.append(f"integration_execution_count{{{labels}}} {count}")

        # Success rates
        for key in self.success_counts.keys():
            parts = key.split(":")
            connector_id, tenant_id, execution_path = parts[:3]

            success_rate = self.get_success_rate(connector_id, tenant_id, execution_path)
            labels = f'connector_id="{connector_id}",tenant_id="{tenant_id}",execution_path="{execution_path}"'

            lines.append(f"integration_success_rate{{{labels}}} {success_rate}")

        # Circuit breaker states
        for key, state in self.circuit_breaker_states.items():
            parts = key.split(":")
            connector_id, tenant_id = parts[:2]

            state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state, 0)
            labels = f'connector_id="{connector_id}",tenant_id="{tenant_id}"'

            lines.append(f"circuit_breaker_state{{{labels}}} {state_value}")

        # Rate limit remaining
        for key, tokens in self.rate_limit_remaining.items():
            parts = key.split(":")
            connector_id, tenant_id = parts[:2]

            labels = f'connector_id="{connector_id}",tenant_id="{tenant_id}"'
            lines.append(f"rate_limit_tokens_remaining{{{labels}}} {tokens}")

        # Rate limit exceeded count
        for key, count in self.rate_limit_exceeded_count.items():
            parts = key.split(":")
            connector_id, tenant_id = parts[:2]

            labels = f'connector_id="{connector_id}",tenant_id="{tenant_id}"'
            lines.append(f"rate_limit_exceeded_count{{{labels}}} {count}")

        return "\n".join(lines)


# Singleton instance for convenient access
_integration_metrics = IntegrationMetrics()


def get_integration_metrics() -> IntegrationMetrics:
    """
    Get the singleton IntegrationMetrics instance.

    Returns:
        IntegrationMetrics instance
    """
    return _integration_metrics
