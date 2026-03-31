"""
Circuit Breaker - Automatically disable failing integrations

Supports:
- External integrations (Salesforce, Slack, etc.)
- Queue operations (QStash publish, schedule)

PERSISTENCE: Optional Redis for distributed coordination across API instances.
When Redis is not available, falls back to in-memory state (single-instance).

Ported from atom-saas with SaaS patterns removed (tenant isolation, tenant-scoped alerting).
"""
from collections import defaultdict
from dataclasses import dataclass, field
import logging
import time
import asyncio
import json
from typing import Dict, Set, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class IntegrationStats:
    """Statistics for an integration (single-tenant)"""
    total_calls: int = 0
    failures: int = 0
    last_failure_time: float = 0
    consecutive_failures: int = 0
    last_error_type: str = ""
    last_error_message: str = ""


class CircuitBreaker:
    """
    Circuit breaker pattern for integrations (single-tenant).
    Automatically disables integrations that fail repeatedly.

    Supports optional Redis for distributed coordination across instances.
    Falls back to in-memory state when Redis is not available.
    """

    def __init__(
        self,
        redis_client=None,
        failure_threshold: float = 0.5,  # 50% failure rate
        min_calls: int = 5,  # Minimum calls before checking
        consecutive_failure_limit: int = 3,  # Disable after N consecutive failures
        cooldown_seconds: int = 300  # 5 minutes cooldown before re-enabling
    ):
        self.failure_threshold = failure_threshold
        self.min_calls = min_calls
        self.consecutive_failure_limit = consecutive_failure_limit
        self.cooldown_seconds = cooldown_seconds

        self.redis = redis_client

        # In-memory fallback (used when Redis is not available)
        self.stats: Dict[str, IntegrationStats] = defaultdict(IntegrationStats)
        self.disabled: Set[str] = set()
        self.disabled_until: Dict[str, float] = {}

        # Callbacks for autonomous actions
        self._on_open_callbacks = []
        self._on_reset_callbacks = []
    
    def on_open(self, callback):
        """Register a callback for when circuit opens"""
        self._on_open_callbacks.append(callback)
        return callback

    def on_reset(self, callback):
        """Register a callback for when circuit resets/closes"""
        self._on_reset_callbacks.append(callback)
        return callback

    async def _get_stats_from_redis(self, integration: str) -> Optional[IntegrationStats]:
        """Get stats for an integration from Redis (global, not tenant-scoped)"""
        if not self.redis:
            return None

        cache_key = f"cb:stats:{integration}"
        try:
            data = await self.redis.get(cache_key)
            if data:
                return IntegrationStats(**json.loads(data))
        except Exception as e:
            logger.warning(f"Failed to get circuit breaker stats from Redis: {e}")
        return None

    async def _save_stats_to_redis(self, integration: str, stats: IntegrationStats):
        """Save stats for an integration to Redis (global, not tenant-scoped)"""
        if not self.redis:
            return

        cache_key = f"cb:stats:{integration}"
        try:
            await self.redis.set(cache_key, json.dumps(stats.__dict__), ex=86400)
        except Exception as e:
            logger.warning(f"Failed to save circuit breaker stats to Redis: {e}")

    async def record_success(self, integration: str):
        """Record a successful integration call"""
        # Try Redis first
        stats = await self._get_stats_from_redis(integration)
        if stats:
            stats.total_calls += 1
            stats.consecutive_failures = 0
            await self._save_stats_to_redis(integration, stats)
        else:
            # Fallback to in-memory
            stats = self.stats[integration]
            stats.total_calls += 1
            stats.consecutive_failures = 0

        # Re-enable if it was disabled and cooldown passed
        if integration in self.disabled:
            await self._try_reenable(integration)

    async def record_failure(self, integration: str, error: Exception = None):
        """Record a failed integration call"""
        # Try Redis first
        stats = await self._get_stats_from_redis(integration)
        if stats:
            stats.total_calls += 1
            stats.failures += 1
            stats.consecutive_failures += 1
            stats.last_failure_time = time.time()
            if error:
                stats.last_error_type = type(error).__name__
                stats.last_error_message = str(error)
            await self._save_stats_to_redis(integration, stats)
        else:
            # Fallback to in-memory
            stats = self.stats[integration]
            stats.total_calls += 1
            stats.failures += 1
            stats.consecutive_failures += 1
            stats.last_failure_time = time.time()

        # Check if should disable
        if await self._should_disable(integration, stats):
            await self._disable_integration(integration, stats)
            logger.error(
                f"Circuit breaker OPENED for {integration}: "
                f"{stats.failures}/{stats.total_calls} failures, "
                f"{stats.consecutive_failures} consecutive"
            )
    
    async def is_enabled(self, integration: str) -> bool:
        """Check if integration is enabled"""
        # Check Redis disabled state
        if self.redis:
            cache_key = f"cb:disabled:{integration}"
            try:
                disabled_until = await self.redis.get(cache_key)
                if disabled_until:
                    if time.time() >= float(disabled_until):
                        await self.redis.delete(cache_key)
                        logger.info(f"Integration {integration} re-enabled after cooldown")
                        return True
                    return False
            except Exception as e:
                logger.warning(f"Failed to check circuit breaker state in Redis: {e}")

        # Fallback to in-memory state
        if integration not in self.disabled:
            return True

        # Check if cooldown period has passed
        if await self._try_reenable(integration):
            return True

        return False
    
    async def get_stats(self, integration: str) -> Dict:
        """Get statistics for an integration"""
        # Try Redis first
        stats = await self._get_stats_from_redis(integration)
        if not stats:
            # Fallback to in-memory
            stats = self.stats[integration]

        failure_rate = stats.failures / stats.total_calls if stats.total_calls > 0 else 0

        return {
            "total_calls": stats.total_calls,
            "failures": stats.failures,
            "consecutive_failures": stats.consecutive_failures,
            "failure_rate": failure_rate,
            "is_enabled": await self.is_enabled(integration),
            "last_error_type": stats.last_error_type,
            "last_error_message": stats.last_error_message,
            "disabled_until": self.disabled_until.get(integration, 0)
        }
    
    async def get_all_stats(self) -> Dict[str, Dict]:
        """Get statistics for all integrations"""
        all_stats = {}

        # Try to get stats from Redis
        if self.redis:
            try:
                pattern = "cb:stats:*"
                if hasattr(self.redis, 'scan_iter'):
                    async for key in self.redis.scan_iter(match=pattern):
                        key_str = key.decode() if isinstance(key, bytes) else key
                        integration_name = key_str.split("cb:stats:")[-1]
                        all_stats[integration_name] = await self.get_stats(integration_name)
            except Exception as e:
                logger.error(f"Failed to scan circuit breaker stats from Redis: {e}")

        # Add in-memory stats
        for name in self.stats.keys():
            if name not in all_stats:
                all_stats[name] = await self.get_stats(name)

        return all_stats
    
    async def reset(self, integration: str = None):
        """Reset statistics for an integration or all integrations"""
        # Reset Redis state
        if self.redis:
            if integration:
                await self.redis.delete(f"cb:stats:{integration}")
                await self.redis.delete(f"cb:disabled:{integration}")
            else:
                # Delete all circuit breaker keys
                try:
                    if hasattr(self.redis, 'scan_iter'):
                        async for key in self.redis.scan_iter(match="cb:*"):
                            await self.redis.delete(key)
                except Exception as e:
                    logger.error(f"Failed to reset circuit breaker in Redis: {e}")

        # Reset in-memory state
        if integration:
            if integration in self.stats:
                del self.stats[integration]
            if integration in self.disabled:
                self.disabled.remove(integration)
            if integration in self.disabled_until:
                del self.disabled_until[integration]
            logger.info(f"Circuit breaker reset for {integration}")
        else:
            self.stats.clear()
            self.disabled.clear()
            self.disabled_until.clear()
            logger.info("Circuit breaker reset for all integrations")

        # Trigger reset callbacks
        for callback in self._on_reset_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(integration or "all")
                else:
                    callback(integration or "all")
            except Exception as e:
                logger.error(f"Error in circuit breaker on_reset callback: {e}")
    
    async def _should_disable(self, integration: str, stats: IntegrationStats) -> bool:
        """Check if integration should be disabled"""
        # Not enough calls yet
        if stats.total_calls < self.min_calls:
            return False

        # Too many consecutive failures
        if stats.consecutive_failures >= self.consecutive_failure_limit:
            return True

        # High failure rate
        failure_rate = stats.failures / stats.total_calls
        if failure_rate >= self.failure_threshold:
            return True

        return False

    async def _disable_integration(self, integration: str, stats: IntegrationStats):
        """Disable an integration (no tenant-scoped alerting in open-source version)"""
        # Set disabled state in Redis
        if self.redis:
            cache_key = f"cb:disabled:{integration}"
            disabled_until = time.time() + self.cooldown_seconds
            try:
                await self.redis.set(cache_key, str(disabled_until), ex=self.cooldown_seconds)
            except Exception as e:
                logger.warning(f"Failed to disable integration in Redis: {e}")

        # Fallback to in-memory state
        self.disabled.add(integration)
        self.disabled_until[integration] = time.time() + self.cooldown_seconds
        logger.warning(
            f"Integration {integration} disabled for {self.cooldown_seconds}s"
        )

        # Trigger callbacks (open-source version uses callbacks instead of tenant-scoped alerts)
        for callback in self._on_open_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(integration)
                else:
                    callback(integration)
            except Exception as e:
                logger.error(f"Error in circuit breaker on_open callback: {e}")

    async def _try_reenable(self, integration: str) -> bool:
        """Try to re-enable a disabled integration if cooldown passed"""
        # Check Redis state first
        if self.redis:
            cache_key = f"cb:disabled:{integration}"
            try:
                disabled_until = await self.redis.get(cache_key)
                if disabled_until and time.time() < float(disabled_until):
                    return False  # Still in cooldown
                elif disabled_until:
                    await self.redis.delete(cache_key)
            except Exception as e:
                logger.warning(f"Failed to check re-enable in Redis: {e}")

        # Check in-memory state
        if integration not in self.disabled:
            return True

        if time.time() >= self.disabled_until.get(integration, 0):
            self.disabled.remove(integration)
            if integration in self.disabled_until:
                del self.disabled_until[integration]
            logger.info(f"Integration {integration} re-enabled after cooldown")

            # Trigger callbacks
            for callback in self._on_reset_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(integration)
                    else:
                        callback(integration)
                except Exception as e:
                    logger.error(f"Error in circuit breaker on_reset callback: {e}")
            return True

        return False


# Global circuit breaker instance (no Redis by default in open-source)
circuit_breaker = CircuitBreaker()


def circuit_breaker_decorator(integration: str):
    """
    Decorator to apply circuit breaker to a function.

    Usage:
        @circuit_breaker_decorator(integration="gmail")
        async def send_email(**params):
            # ... implementation
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            breaker = kwargs.get('circuit_breaker', circuit_breaker)

            # Check if circuit is open
            if not await breaker.is_enabled(integration):
                logger.warning(f"Circuit breaker is OPEN for {integration}, skipping call")
                return {
                    "success": False,
                    "error": f"Integration {integration} is temporarily disabled due to failures"
                }

            try:
                result = await func(*args, **kwargs)
                await breaker.record_success(integration)
                return result
            except Exception as e:
                await breaker.record_failure(integration, e)
                raise

        return wrapper
    return decorator


# Convenience alias
circuit_breaker_func = circuit_breaker_decorator


# Global circuit breaker instance
circuit_breaker = CircuitBreaker()
