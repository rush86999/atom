"""
Performance metrics service for adaptive fleet scaling.

This service tracks fleet performance metrics in real-time using Redis counters
with time-windowed aggregation and threshold-based alerting. It provides the
foundation for automatic fleet expansion/contraction proposals.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from pydantic import BaseModel, Field
import redis.asyncio as redis

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from core.database import Base
from core.models import FleetPerformanceMetric
from core.fleet_orchestration.fleet_execution_models import FleetExecutionResult

logger = logging.getLogger(__name__)

# ============================================================================
# Pydantic Models
# ============================================================================

class PerformanceMetrics(BaseModel):
    """
    Performance metrics for a fleet chain within a time window.

    Attributes:
        chain_id: ID of the delegation chain (fleet)
        success_rate: Success rate as percentage (0-100)
        avg_latency_ms: Average execution latency in milliseconds
        throughput_per_minute: Tasks completed per minute
        execution_count: Total number of executions in window
        window: Time window identifier (e.g., "1m", "5m", "1h")
        calculated_at: When metrics were calculated
    """
    chain_id: str
    success_rate: float = Field(ge=0.0, le=100.0)
    avg_latency_ms: float = Field(ge=0.0)
    throughput_per_minute: float = Field(ge=0.0)
    execution_count: int = Field(ge=0)
    window: str
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PerformanceAlert(BaseModel):
    """
    Alert triggered when performance thresholds are violated.

    Attributes:
        chain_id: ID of the delegation chain (fleet)
        alert_type: Type of alert (low_success_rate, high_latency, low_throughput)
        current_value: Current metric value
        threshold_value: Threshold that was violated
        severity: Alert severity (warning, critical)
        message: Human-readable alert message
        detected_at: When alert was detected
    """
    chain_id: str
    alert_type: str = Field(pattern="^(low_success_rate|high_latency|low_throughput)$")
    current_value: float
    threshold_value: float
    severity: str = Field(pattern="^(warning|critical)$")
    message: str
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ============================================================================
# Service
# ============================================================================

class PerformanceMetricsService:
    """
    Service for tracking and analyzing fleet performance metrics.

    Uses Redis for real-time counters and database for historical persistence.
    All operations are async and non-blocking to avoid impacting fleet execution.
    """

    # Time window configurations (in seconds)
    WINDOW_SECONDS = {
        "1m": 60,
        "5m": 300,
        "1h": 3600,
    }

    def __init__(self, db: Session, redis_url: Optional[str] = None):
        """
        Initialize performance metrics service.

        Args:
            db: Database session for historical persistence
            redis_url: Redis connection URL (optional, uses env if not provided)
        """
        self.db = db
        self.redis_url = redis_url
        self._redis_client: Optional[redis.Redis] = None

    async def _get_redis(self) -> Optional[redis.Redis]:
        """
        Get or create Redis connection.

        Returns:
            Redis client or None if connection fails
        """
        if self._redis_client is None:
            try:
                import os
                url = self.redis_url or os.getenv("DRAGONFLY_URL") or os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL")
                if url:
                    self._redis_client = redis.from_url(url, decode_responses=False)
                else:
                    logger.warning("No Redis URL configured, metrics tracking disabled")
            except Exception as e:
                logger.error(f"Failed to create Redis client: {e}")
                return None
        return self._redis_client

    async def record_execution(
        self,
        chain_id: str,
        result: FleetExecutionResult) -> None:
        """
        Record execution metrics to Redis counters.

        Non-blocking operation - increments counters and schedules DB persistence.

        Args:
            chain_id: ID of the delegation chain
            result: Fleet execution result with metrics
            tenant_id: Any ID for multi-tenancy
        """
        redis_client = await self._get_redis()
        if not redis_client:
            return

        try:
            # Calculate execution latency
            latency_ms = result.execution_time_ms or 0

            # Use Redis pipeline for atomic updates
            pipe = redis_client.pipeline()

            # Update counters for all time windows
            for window in ["1m", "5m", "1h"]:
                window_sec = self.WINDOW_SECONDS[window]

                # Increment success/failure counters
                if result.has_failures:
                    pipe.incrby(f"fleet:{chain_id}:metrics:{window}:failure", result.failed_count)
                else:
                    pipe.incrby(f"fleet:{chain_id}:metrics:{window}:success", result.completed_count)

                # Add latency to total
                pipe.incrbyfloat(f"fleet:{chain_id}:metrics:{window}:latency", latency_ms * result.total_tasks)

                # Increment execution count
                pipe.incrby(f"fleet:{chain_id}:metrics:{window}:count", result.total_tasks)

                # Set expiration (keep data for 2 hours to cover all windows)
                pipe.expire(f"fleet:{chain_id}:metrics:{window}:success", 7200)
                pipe.expire(f"fleet:{chain_id}:metrics:{window}:failure", 7200)
                pipe.expire(f"fleet:{chain_id}:metrics:{window}:latency", 7200)
                pipe.expire(f"fleet:{chain_id}:metrics:{window}:count", 7200)

            # Execute pipeline
            await pipe.execute()

            # Schedule non-blocking database persistence
            asyncio.create_task(self._persist_to_database(chain_id, result))

            logger.debug(f"Recorded metrics for chain {chain_id}: {result.total_tasks} tasks, {result.execution_time_ms}ms")

        except Exception as e:
            logger.error(f"Failed to record metrics for chain {chain_id}: {e}")
            # Don't raise - metrics failure shouldn't break fleet execution

    async def _persist_to_database(
        self,
        chain_id: str,
        result: FleetExecutionResult) -> None:
        """
        Persist aggregated metrics to database.

        Args:
            chain_id: ID of the delegation chain
            result: Fleet execution result
            tenant_id: Any ID for multi-tenancy
        """
        try:
            # Calculate window boundaries (5-minute windows)
            now = datetime.now(timezone.utc)
            window_start = now.replace(second=0, microsecond=0) - timedelta(minutes=now.minute % 5)
            window_end = window_start + timedelta(minutes=5)

            # Create metric records
            metrics = [
                FleetPerformanceMetric(
                    chain_id=chain_id,
                                        metric_type="success_rate",
                    metric_value=result.success_rate,
                    window_start=window_start,
                    window_end=window_end),
                FleetPerformanceMetric(
                    chain_id=chain_id,
                                        metric_type="avg_latency",
                    metric_value=result.execution_time_ms or 0,
                    window_start=window_start,
                    window_end=window_end),
                FleetPerformanceMetric(
                    chain_id=chain_id,
                                        metric_type="throughput",
                    metric_value=result.total_tasks,
                    window_start=window_start,
                    window_end=window_end),
            ]

            # Batch insert
            self.db.add_all(metrics)
            self.db.commit()

            logger.debug(f"Persisted {len(metrics)} metrics to database for chain {chain_id}")

        except Exception as e:
            logger.error(f"Failed to persist metrics to database for chain {chain_id}: {e}")
            self.db.rollback()

    async def get_metrics(self, chain_id: str, window: str = "5m") -> PerformanceMetrics:
        """
        Calculate performance metrics for a time window.

        Args:
            chain_id: ID of the delegation chain
            window: Time window ("1m", "5m", "1h")

        Returns:
            PerformanceMetrics object with calculated metrics

        Raises:
            ValueError: If window is invalid
        """
        if window not in self.WINDOW_SECONDS:
            raise ValueError(f"Invalid window: {window}. Must be one of {list(self.WINDOW_SECONDS.keys())}")

        redis_client = await self._get_redis()
        if not redis_client:
            # Return empty metrics if Redis unavailable
            return PerformanceMetrics(
                chain_id=chain_id,
                success_rate=0.0,
                avg_latency_ms=0.0,
                throughput_per_minute=0.0,
                execution_count=0,
                window=window)

        try:
            # Get counters from Redis
            success_key = f"fleet:{chain_id}:metrics:{window}:success"
            failure_key = f"fleet:{chain_id}:metrics:{window}:failure"
            latency_key = f"fleet:{chain_id}:metrics:{window}:latency"
            count_key = f"fleet:{chain_id}:metrics:{window}:count"

            # Pipeline for efficiency
            pipe = redis_client.pipeline()
            pipe.get(success_key)
            pipe.get(failure_key)
            pipe.get(latency_key)
            pipe.get(count_key)

            results = await pipe.execute()

            # Handle both bytes (from Redis with decode_responses=False) and strings
            def decode_value(val):
                if val is None:
                    return 0
                if isinstance(val, bytes):
                    return val.decode('utf-8')
                return val

            success_count = int(decode_value(results[0]) or 0)
            failure_count = int(decode_value(results[1]) or 0)
            total_latency = float(decode_value(results[2]) or 0.0)
            execution_count = int(decode_value(results[3]) or 0)

            # Calculate metrics
            total_tasks = success_count + failure_count
            success_rate = (success_count / total_tasks * 100) if total_tasks > 0 else 0.0
            avg_latency_ms = (total_latency / execution_count) if execution_count > 0 else 0.0

            window_sec = self.WINDOW_SECONDS[window]
            throughput_per_minute = (execution_count / window_sec) * 60 if execution_count > 0 else 0.0

            return PerformanceMetrics(
                chain_id=chain_id,
                success_rate=round(success_rate, 2),
                avg_latency_ms=round(avg_latency_ms, 2),
                throughput_per_minute=round(throughput_per_minute, 2),
                execution_count=execution_count,
                window=window)

        except Exception as e:
            logger.error(f"Failed to get metrics for chain {chain_id}: {e}")
            # Return empty metrics on error
            return PerformanceMetrics(
                chain_id=chain_id,
                success_rate=0.0,
                avg_latency_ms=0.0,
                throughput_per_minute=0.0,
                execution_count=0,
                window=window)

    async def check_thresholds(self, chain_id: str) -> List[PerformanceAlert]:
        """
        Check if performance metrics violate thresholds.

        Args:
            chain_id: ID of the delegation chain
            tenant_id: Any ID for loading custom thresholds

        Returns:
            List of PerformanceAlert for violated thresholds
        """
        thresholds = self._get_thresholds()
        alerts = []

        try:
            # Check all time windows
            for window in ["1m", "5m", "1h"]:
                metrics = await self.get_metrics(chain_id, window)

                # Check success rate
                if metrics.success_rate < thresholds["success_rate_critical"]:
                    alerts.append(PerformanceAlert(
                        chain_id=chain_id,
                        alert_type="low_success_rate",
                        current_value=metrics.success_rate,
                        threshold_value=thresholds["success_rate_critical"],
                        severity="critical",
                        message=f"Success rate ({metrics.success_rate:.1f}%) below critical threshold ({thresholds['success_rate_critical']:.1f}%) in {window} window"))
                elif metrics.success_rate < thresholds["success_rate_warning"]:
                    alerts.append(PerformanceAlert(
                        chain_id=chain_id,
                        alert_type="low_success_rate",
                        current_value=metrics.success_rate,
                        threshold_value=thresholds["success_rate_warning"],
                        severity="warning",
                        message=f"Success rate ({metrics.success_rate:.1f}%) below warning threshold ({thresholds['success_rate_warning']:.1f}%) in {window} window"))

                # Check latency (only if we have executions)
                if metrics.execution_count > 0:
                    if metrics.avg_latency_ms > thresholds["latency_critical_ms"]:
                        alerts.append(PerformanceAlert(
                            chain_id=chain_id,
                            alert_type="high_latency",
                            current_value=metrics.avg_latency_ms,
                            threshold_value=thresholds["latency_critical_ms"],
                            severity="critical",
                            message=f"Average latency ({metrics.avg_latency_ms:.0f}ms) above critical threshold ({thresholds['latency_critical_ms']:.0f}ms) in {window} window"))
                    elif metrics.avg_latency_ms > thresholds["latency_warning_ms"]:
                        alerts.append(PerformanceAlert(
                            chain_id=chain_id,
                            alert_type="high_latency",
                            current_value=metrics.avg_latency_ms,
                            threshold_value=thresholds["latency_warning_ms"],
                            severity="warning",
                            message=f"Average latency ({metrics.avg_latency_ms:.0f}ms) above warning threshold ({thresholds['latency_warning_ms']:.0f}ms) in {window} window"))

                # Check throughput (only if we have executions)
                if metrics.execution_count > 0:
                    if metrics.throughput_per_minute < thresholds["throughput_warning"]:
                        alerts.append(PerformanceAlert(
                            chain_id=chain_id,
                            alert_type="low_throughput",
                            current_value=metrics.throughput_per_minute,
                            threshold_value=thresholds["throughput_warning"],
                            severity="warning",
                            message=f"Throughput ({metrics.throughput_per_minute:.1f} tasks/min) below warning threshold ({thresholds['throughput_warning']:.1f} tasks/min) in {window} window"))

        except Exception as e:
            logger.error(f"Failed to check thresholds for chain {chain_id}: {e}")

        return alerts

    def _get_thresholds(self) -> Dict[str, float]:
        """
        Get performance thresholds for a tenant.

        Args:
            tenant_id: Any ID for loading custom thresholds

        Returns:
            Dictionary of threshold values
        """
        # TODO: Load from tenant settings in future iteration
        # For now, use defaults
        return {
            "success_rate_warning": 85.0,
            "success_rate_critical": 70.0,
            "latency_warning_ms": 20000.0,
            "latency_critical_ms": 45000.0,
            "throughput_warning": 5.0,
        }

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None

# ============================================================================
# Singleton Pattern
# ============================================================================

_service_instance: Optional[PerformanceMetricsService] = None

def get_performance_metrics_service(db: Session) -> PerformanceMetricsService:
    """
    Get singleton PerformanceMetricsService instance.

    Args:
        db: Database session

    Returns:
        PerformanceMetricsService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = PerformanceMetricsService(db)
    return _service_instance
