"""
Integration Dashboard System
Provides real-time metrics, health monitoring, and configuration management
for all communication platform integrations.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class IntegrationStatus(Enum):
    """Integration health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ERROR = "error"
    DISABLED = "disabled"
    NOT_CONFIGURED = "not_configured"


@dataclass
class IntegrationMetrics:
    """Metrics for a single integration"""
    # Message counts
    messages_fetched: int = 0
    messages_processed: int = 0
    messages_failed: int = 0
    messages_duplicate: int = 0

    # Timing metrics (milliseconds)
    avg_fetch_time_ms: float = 0.0
    avg_process_time_ms: float = 0.0
    p99_fetch_time_ms: float = 0.0
    p99_process_time_ms: float = 0.0

    # Health metrics
    last_fetch_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    last_error_time: Optional[datetime] = None
    last_error_message: Optional[str] = None

    # Rate limiting
    rate_limit_hits: int = 0
    rate_limit_resets: List[datetime] = field(default_factory=list)

    # Data quality
    fetch_size_bytes: int = 0
    attachment_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "messages_fetched": self.messages_fetched,
            "messages_processed": self.messages_processed,
            "messages_failed": self.messages_failed,
            "messages_duplicate": self.messages_duplicate,
            "success_rate": self._calculate_success_rate(),
            "duplicate_rate": self._calculate_duplicate_rate(),
            "avg_fetch_time_ms": round(self.avg_fetch_time_ms, 2),
            "avg_process_time_ms": round(self.avg_process_time_ms, 2),
            "p99_fetch_time_ms": round(self.p99_fetch_time_ms, 2),
            "p99_process_time_ms": round(self.p99_process_time_ms, 2),
            "last_fetch_time": self.last_fetch_time.isoformat() if self.last_fetch_time else None,
            "last_success_time": self.last_success_time.isoformat() if self.last_success_time else None,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "last_error_message": self.last_error_message,
            "rate_limit_hits": self.rate_limit_hits,
            "rate_limit_resets": [r.isoformat() for r in self.rate_limit_resets],
            "fetch_size_bytes": self.fetch_size_bytes,
            "attachment_count": self.attachment_count
        }

    def _calculate_success_rate(self) -> float:
        """Calculate success rate as percentage"""
        total = self.messages_processed + self.messages_failed
        if total == 0:
            return 100.0
        return (self.messages_processed / total) * 100

    def _calculate_duplicate_rate(self) -> float:
        """Calculate duplicate rate as percentage"""
        if self.messages_fetched == 0:
            return 0.0
        return (self.messages_duplicate / self.messages_fetched) * 100


@dataclass
class IntegrationHealth:
    """Health status for a single integration"""
    status: IntegrationStatus = IntegrationStatus.NOT_CONFIGURED
    enabled: bool = False
    configured: bool = False
    last_check: Optional[datetime] = None
    last_error_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0

    # Configuration validation
    has_valid_token: bool = False
    has_required_permissions: bool = False
    token_expiry: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "status": self.status.value,
            "enabled": self.enabled,
            "configured": self.configured,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "has_valid_token": self.has_valid_token,
            "has_required_permissions": self.has_required_permissions,
            "token_expiry": self.token_expiry.isoformat() if self.token_expiry else None
        }


class IntegrationDashboard:
    """
    Dashboard for monitoring communication platform integrations.

    Features:
    - Real-time metrics collection
    - Health status monitoring
    - Configuration management
    - Alert thresholds
    """

    def __init__(self):
        # Metrics per integration
        self.metrics: Dict[str, IntegrationMetrics] = {
            "slack": IntegrationMetrics(),
            "teams": IntegrationMetrics(),
            "gmail": IntegrationMetrics(),
            "outlook": IntegrationMetrics()
        }

        # Health status per integration
        self.health: Dict[str, IntegrationHealth] = {
            "slack": IntegrationHealth(),
            "teams": IntegrationHealth(),
            "gmail": IntegrationHealth(),
            "outlook": IntegrationHealth()
        }

        # Timing history for percentile calculation
        self.fetch_times: Dict[str, List[float]] = defaultdict(list)
        self.process_times: Dict[str, List[float]] = defaultdict(list)

        # Configuration
        self.configurations: Dict[str, Dict[str, Any]] = {}

        # Alert thresholds
        self.thresholds = {
            "consecutive_failures_warning": 3,
            "consecutive_failures_critical": 5,
            "fetch_time_warning_ms": 5000,
            "fetch_time_critical_ms": 10000,
            "error_rate_warning": 10.0,  # percentage
            "error_rate_critical": 25.0
        }

    def record_fetch(
        self,
        integration: str,
        message_count: int,
        fetch_time_ms: float,
        success: bool = True,
        error_message: Optional[str] = None,
        rate_limited: bool = False
    ):
        """
        Record a message fetch operation.

        Args:
            integration: Integration name (slack, teams, gmail, outlook)
            message_count: Number of messages fetched
            fetch_time_ms: Time taken to fetch in milliseconds
            success: Whether fetch was successful
            error_message: Error message if failed
            rate_limited: Whether request was rate limited
        """
        now = datetime.now()

        # Initialize metrics if needed
        if integration not in self.metrics:
            self.metrics[integration] = IntegrationMetrics()
        if integration not in self.health:
            self.health[integration] = IntegrationHealth()
        if integration not in self.fetch_times:
            self.fetch_times[integration] = []

        metrics = self.metrics[integration]
        health = self.health[integration]

        # Update metrics
        metrics.messages_fetched += message_count
        metrics.last_fetch_time = now

        # Track timing
        self.fetch_times[integration].append(fetch_time_ms)

        # Keep only last 1000 samples
        if len(self.fetch_times[integration]) > 1000:
            self.fetch_times[integration] = self.fetch_times[integration][-1000:]

        # Update timing metrics
        metrics.avg_fetch_time_ms = sum(self.fetch_times[integration]) / len(self.fetch_times[integration])
        sorted_times = sorted(self.fetch_times[integration])
        if len(sorted_times) > 0:
            p99_idx = int(len(sorted_times) * 0.99)
            metrics.p99_fetch_time_ms = sorted_times[p99_idx]

        # Update health based on success/failure
        if success:
            metrics.messages_processed += message_count
            metrics.last_success_time = now
            health.last_check = now
            health.consecutive_successes += 1
            health.consecutive_failures = 0
        else:
            metrics.messages_failed += message_count
            metrics.last_error_time = now
            metrics.last_error_message = error_message
            health.last_check = now
            health.last_error_time = now
            health.consecutive_failures += 1
            health.consecutive_successes = 0

        # Track rate limiting
        if rate_limited:
            metrics.rate_limit_hits += 1
            # Record reset time (estimate after 1 hour)
            reset_time = now + timedelta(hours=1)
            metrics.rate_limit_resets.append(reset_time)

        # Update health status
        self._update_health_status(integration)

    def record_processing(
        self,
        integration: str,
        processed_count: int,
        duplicate_count: int,
        process_time_ms: float,
        attachment_count: int = 0,
        data_size_bytes: int = 0
    ):
        """
        Record message processing metrics.

        Args:
            integration: Integration name
            processed_count: Number of messages processed
            duplicate_count: Number of duplicates found
            process_time_ms: Time taken to process
            attachment_count: Number of attachments
            data_size_bytes: Size of data in bytes
        """
        if integration not in self.metrics:
            self.metrics[integration] = IntegrationMetrics()
        if integration not in self.process_times:
            self.process_times[integration] = []

        metrics = self.metrics[integration]

        # Update metrics
        metrics.messages_duplicate += duplicate_count
        metrics.attachment_count += attachment_count
        metrics.fetch_size_bytes += data_size_bytes

        # Track timing
        self.process_times[integration].append(process_time_ms)

        # Keep only last 1000 samples
        if len(self.process_times[integration]) > 1000:
            self.process_times[integration] = self.process_times[integration][-1000:]

        # Update timing metrics
        metrics.avg_process_time_ms = sum(self.process_times[integration]) / len(self.process_times[integration])
        sorted_times = sorted(self.process_times[integration])
        if len(sorted_times) > 0:
            p99_idx = int(len(sorted_times) * 0.99)
            metrics.p99_process_time_ms = sorted_times[p99_idx]

    def update_health(
        self,
        integration: str,
        enabled: bool = None,
        configured: bool = None,
        has_valid_token: bool = None,
        has_required_permissions: bool = None,
        token_expiry: Optional[datetime] = None
    ):
        """
        Update health status for an integration.

        Args:
            integration: Integration name
            enabled: Whether integration is enabled
            configured: Whether integration is configured
            has_valid_token: Whether token is valid
            has_required_permissions: Whether required permissions are granted
            token_expiry: Token expiry time
        """
        if integration not in self.health:
            self.health[integration] = IntegrationHealth()

        health = self.health[integration]

        if enabled is not None:
            health.enabled = enabled
        if configured is not None:
            health.configured = configured
        if has_valid_token is not None:
            health.has_valid_token = has_valid_token
        if has_required_permissions is not None:
            health.has_required_permissions = has_required_permissions
        if token_expiry is not None:
            health.token_expiry = token_expiry

        health.last_check = datetime.now()
        self._update_health_status(integration)

    def _update_health_status(self, integration: str):
        """Update health status based on metrics"""
        if integration not in self.health:
            self.health[integration] = IntegrationHealth()

        health = self.health[integration]
        metrics = self.metrics.get(integration)

        if not health.enabled:
            health.status = IntegrationStatus.DISABLED
            return

        if not health.configured:
            health.status = IntegrationStatus.NOT_CONFIGURED
            return

        # Check consecutive failures
        if health.consecutive_failures >= self.thresholds["consecutive_failures_critical"]:
            health.status = IntegrationStatus.ERROR
            return

        if health.consecutive_failures >= self.thresholds["consecutive_failures_warning"]:
            health.status = IntegrationStatus.DEGRADED
            return

        # Check error rate
        if metrics:
            error_rate = 100 - metrics._calculate_success_rate()
            if error_rate >= self.thresholds["error_rate_critical"]:
                health.status = IntegrationStatus.ERROR
                return
            if error_rate >= self.thresholds["error_rate_warning"]:
                health.status = IntegrationStatus.DEGRADED
                return

        # Check token expiry
        if health.token_expiry:
            time_until_expiry = health.token_expiry - datetime.now()
            if time_until_expiry < timedelta(hours=1):
                health.status = IntegrationStatus.DEGRADED
                return

        # All checks passed
        health.status = IntegrationStatus.HEALTHY

    def get_metrics(self, integration: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metrics for integrations.

        Args:
            integration: Specific integration name, or None for all

        Returns:
            Dictionary of metrics
        """
        if integration:
            if integration not in self.metrics:
                return {}
            return self.metrics[integration].to_dict()

        return {
            name: metrics.to_dict()
            for name, metrics in self.metrics.items()
        }

    def get_health(self, integration: Optional[str] = None) -> Dict[str, Any]:
        """
        Get health status for integrations.

        Args:
            integration: Specific integration name, or None for all

        Returns:
            Dictionary of health status
        """
        if integration:
            if integration not in self.health:
                return {}
            return self.health[integration].to_dict()

        return {
            name: health.to_dict()
            for name, health in self.health.items()
        }

    def get_overall_status(self) -> Dict[str, Any]:
        """
        Get overall system status.

        Returns:
            Dictionary with overall system health
        """
        total_integrations = len(self.health)
        healthy_count = sum(
            1 for h in self.health.values()
            if h.status == IntegrationStatus.HEALTHY
        )
        degraded_count = sum(
            1 for h in self.health.values()
            if h.status == IntegrationStatus.DEGRADED
        )
        error_count = sum(
            1 for h in self.health.values()
            if h.status == IntegrationStatus.ERROR
        )
        disabled_count = sum(
            1 for h in self.health.values()
            if h.status == IntegrationStatus.DISABLED
        )

        # Aggregate metrics
        total_messages = sum(m.messages_fetched for m in self.metrics.values())
        total_processed = sum(m.messages_processed for m in self.metrics.values())
        total_failed = sum(m.messages_failed for m in self.metrics.values())

        return {
            "overall_status": "healthy" if error_count == 0 and degraded_count == 0 else "degraded" if error_count == 0 else "error",
            "total_integrations": total_integrations,
            "healthy_count": healthy_count,
            "degraded_count": degraded_count,
            "error_count": error_count,
            "disabled_count": disabled_count,
            "total_messages_fetched": total_messages,
            "total_messages_processed": total_processed,
            "total_messages_failed": total_failed,
            "overall_success_rate": (total_processed / (total_processed + total_failed) * 100) if (total_processed + total_failed) > 0 else 100.0,
            "integrations": {
                name: health.to_dict()
                for name, health in self.health.items()
            }
        }

    def get_configuration(self, integration: Optional[str] = None) -> Dict[str, Any]:
        """
        Get configuration for integrations.

        Args:
            integration: Specific integration name, or None for all

        Returns:
            Dictionary of configurations
        """
        if integration:
            return self.configurations.get(integration, {})

        return self.configurations.copy()

    def update_configuration(
        self,
        integration: str,
        config: Dict[str, Any]
    ) -> bool:
        """
        Update configuration for an integration.

        Args:
            integration: Integration name
            config: Configuration dictionary

        Returns:
            True if successful
        """
        if integration not in self.configurations:
            self.configurations[integration] = {}

        self.configurations[integration].update(config)
        logger.info(f"Updated configuration for {integration}: {list(config.keys())}")

        return True

    def reset_metrics(self, integration: Optional[str] = None):
        """
        Reset metrics for integration(s).

        Args:
            integration: Specific integration name, or None for all
        """
        if integration:
            if integration in self.metrics:
                self.metrics[integration] = IntegrationMetrics()
            if integration in self.fetch_times:
                self.fetch_times[integration] = []
            if integration in self.process_times:
                self.process_times[integration] = []
        else:
            for name in self.metrics:
                self.metrics[name] = IntegrationMetrics()
            self.fetch_times.clear()
            self.process_times.clear()

        logger.info(f"Reset metrics for {integration or 'all integrations'}")

    def get_alerts(self) -> List[Dict[str, Any]]:
        """
        Get active alerts based on thresholds.

        Returns:
            List of alert dictionaries
        """
        alerts = []
        now = datetime.now()

        for integration, health in self.health.items():
            metrics = self.metrics.get(integration)

            # Check consecutive failures
            if health.consecutive_failures >= self.thresholds["consecutive_failures_critical"]:
                alerts.append({
                    "integration": integration,
                    "severity": "critical",
                    "type": "consecutive_failures",
                    "message": f"{integration} has {health.consecutive_failures} consecutive failures",
                    "value": health.consecutive_failures,
                    "threshold": self.thresholds["consecutive_failures_critical"],
                    "timestamp": health.last_error_time.isoformat() if health.last_error_time else now.isoformat()
                })
            elif health.consecutive_failures >= self.thresholds["consecutive_failures_warning"]:
                alerts.append({
                    "integration": integration,
                    "severity": "warning",
                    "type": "consecutive_failures",
                    "message": f"{integration} has {health.consecutive_failures} consecutive failures",
                    "value": health.consecutive_failures,
                    "threshold": self.thresholds["consecutive_failures_warning"],
                    "timestamp": health.last_error_time.isoformat() if health.last_error_time else now.isoformat()
                })

            # Check fetch times
            if metrics:
                if metrics.p99_fetch_time_ms >= self.thresholds["fetch_time_critical_ms"]:
                    alerts.append({
                        "integration": integration,
                        "severity": "critical",
                        "type": "slow_fetch",
                        "message": f"{integration} P99 fetch time is {metrics.p99_fetch_time_ms:.0f}ms",
                        "value": metrics.p99_fetch_time_ms,
                        "threshold": self.thresholds["fetch_time_critical_ms"],
                        "timestamp": now.isoformat()
                    })
                elif metrics.p99_fetch_time_ms >= self.thresholds["fetch_time_warning_ms"]:
                    alerts.append({
                        "integration": integration,
                        "severity": "warning",
                        "type": "slow_fetch",
                        "message": f"{integration} P99 fetch time is {metrics.p99_fetch_time_ms:.0f}ms",
                        "value": metrics.p99_fetch_time_ms,
                        "threshold": self.thresholds["fetch_time_warning_ms"],
                        "timestamp": now.isoformat()
                    })

                # Check error rate
                error_rate = 100 - metrics._calculate_success_rate()
                if error_rate >= self.thresholds["error_rate_critical"]:
                    alerts.append({
                        "integration": integration,
                        "severity": "critical",
                        "type": "high_error_rate",
                        "message": f"{integration} error rate is {error_rate:.1f}%",
                        "value": error_rate,
                        "threshold": self.thresholds["error_rate_critical"],
                        "timestamp": now.isoformat()
                    })
                elif error_rate >= self.thresholds["error_rate_warning"]:
                    alerts.append({
                        "integration": integration,
                        "severity": "warning",
                        "type": "high_error_rate",
                        "message": f"{integration} error rate is {error_rate:.1f}%",
                        "value": error_rate,
                        "threshold": self.thresholds["error_rate_warning"],
                        "timestamp": now.isoformat()
                    })

            # Check token expiry
            if health.token_expiry:
                time_until_expiry = health.token_expiry - now
                if time_until_expiry < timedelta(minutes=15):
                    alerts.append({
                        "integration": integration,
                        "severity": "critical",
                        "type": "token_expiry",
                        "message": f"{integration} token expires in {int(time_until_expiry.total_seconds() / 60)} minutes",
                        "value": time_until_expiry.total_seconds(),
                        "threshold": 900,  # 15 minutes
                        "timestamp": now.isoformat()
                    })
                elif time_until_expiry < timedelta(hours=1):
                    alerts.append({
                        "integration": integration,
                        "severity": "warning",
                        "type": "token_expiry",
                        "message": f"{integration} token expires in {int(time_until_expiry.total_seconds() / 3600)} hours",
                        "value": time_until_expiry.total_seconds(),
                        "threshold": 3600,  # 1 hour
                        "timestamp": now.isoformat()
                    })

        return alerts

    def get_statistics_summary(self) -> Dict[str, Any]:
        """
        Get a summary statistics for dashboard.

        Returns:
            Dictionary with summary statistics
        """
        now = datetime.now()
        last_24h = now - timedelta(hours=24)

        total_messages_24h = 0
        active_integrations = 0
        rate_limit_count = 0

        for integration, metrics in self.metrics.items():
            # Count messages from last 24h
            if metrics.last_fetch_time and metrics.last_fetch_time > last_24h:
                total_messages_24h += metrics.messages_fetched
                active_integrations += 1

            rate_limit_count += metrics.rate_limit_hits

        return {
            "total_messages_24h": total_messages_24h,
            "active_integrations": active_integrations,
            "rate_limit_hits_24h": rate_limit_count,
            "overall_status": self.get_overall_status()["overall_status"],
            "alert_count": len(self.get_alerts()),
            "timestamp": now.isoformat()
        }


# Singleton instance
integration_dashboard = IntegrationDashboard()


def get_integration_dashboard() -> IntegrationDashboard:
    """Get the singleton integration dashboard"""
    return integration_dashboard
