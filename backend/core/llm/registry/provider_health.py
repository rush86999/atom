"""Provider health tracking for LLM routing decisions.

Tracks success/error rates, latency, and consecutive failures per provider.
Implements circuit breaker pattern to prevent routing to failing providers.
"""

import logging
import json
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime

from core.cache import UniversalCacheService

logger = logging.getLogger(__name__)

# Health state thresholds
CONSECUTIVE_FAILURES_THRESHOLD = 5  # Mark unhealthy after this many failures
CONSECUTIVE_SUCCESSES_RECOVERY = 10  # Mark healthy after this many successes
DEGRADED_ERROR_RATE = 0.1  # 10% error rate = degraded
UNHEALTHY_ERROR_RATE = 0.3  # 30% error rate = unhealthy

# Health state TTL (how long metrics persist without updates)
HEALTH_STATE_TTL = 3600  # 1 hour



class HealthState(Enum):
    """Provider health states."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RATE_LIMITED = "rate_limited"



class ProviderHealthService:
    """Tracks and manages provider health state.

    Health data stored in Redis with keys: llm_registry:provider_health:{provider}

    Metrics tracked:
    - success_count: Total successful requests
    - error_count: Total failed requests
    - consecutive_failures: Current failure streak
    - consecutive_successes: Current success streak (for recovery)
    - last_success_ts: Timestamp of last success
    - last_error_ts: Timestamp of last error
    - avg_latency_ms: Rolling average latency in milliseconds
    - current_state: HealthState enum value

    Usage:
        health = ProviderHealthService()
        await health.record_success('openai', latency_ms=250)
        await health.record_failure('anthropic', error='rate_limited')
        state = health.get_health_state('openai')
    """

    HEALTH_KEY_PREFIX = "llm_registry:provider_health"

    def __init__(self, cache_service: Optional[UniversalCacheService] = None):
        self.cache = cache_service or UniversalCacheService()

    def _get_key(self, provider: str) -> str:
        return f"{self.HEALTH_KEY_PREFIX}:{provider}"

    async def record_success(
        self,
        provider: str,
        latency_ms: float,
        tenant_id: Optional[str] = None
    ):
        """Record a successful request for a provider.

        Args:
            provider: Provider name (e.g., 'openai', 'anthropic')
            latency_ms: Request latency in milliseconds
            tenant_id: Optional tenant ID for tenant-scoped metrics
        """
        key = self._get_key(provider)
        data = await self._get_health_data(provider)

        # Update counters
        data['success_count'] = data.get('success_count', 0) + 1
        data['consecutive_successes'] = data.get('consecutive_successes', 0) + 1
        data['consecutive_failures'] = 0  # Reset failure streak
        data['last_success_ts'] = datetime.utcnow().isoformat()

        # Update rolling average latency
        current_avg = data.get('avg_latency_ms', latency_ms)
        success_count = data['success_count']
        data['avg_latency_ms'] = (
            (current_avg * (success_count - 1) + latency_ms) / success_count
        )

        # Check for recovery
        if data.get('current_state') in (HealthState.UNHEALTHY.value, HealthState.DEGRADED.value):
            if data['consecutive_successes'] >= CONSECUTIVE_SUCCESSES_RECOVERY:
                data['current_state'] = HealthState.HEALTHY.value
                logger.info(f"Provider {provider} recovered to HEALTHY state")

        # Set to healthy if this is the first request
        if data.get('current_state') is None:
            data['current_state'] = HealthState.HEALTHY.value

        await self.cache.set_async(key, json.dumps(data), HEALTH_STATE_TTL)

    async def record_failure(
        self,
        provider: str,
        error: str,
        tenant_id: Optional[str] = None
    ):
        """Record a failed request for a provider.

        Args:
            provider: Provider name
            error: Error type (e.g., 'rate_limited', 'timeout', 'api_error')
            tenant_id: Optional tenant ID for tenant-scoped metrics
        """
        key = self._get_key(provider)
        data = await self._get_health_data(provider)

        # Update counters
        data['error_count'] = data.get('error_count', 0) + 1
        data['consecutive_failures'] = data.get('consecutive_failures', 0) + 1
        data['consecutive_successes'] = 0  # Reset success streak
        data['last_error_ts'] = datetime.utcnow().isoformat()
        data['last_error'] = error

        # Update state based on error type and patterns
        if error == 'rate_limited':
            data['current_state'] = HealthState.RATE_LIMITED.value
        elif data['consecutive_failures'] >= CONSECUTIVE_FAILURES_THRESHOLD:
            data['current_state'] = HealthState.UNHEALTHY.value
            logger.warning(
                f"Provider {provider} marked UNHEALTHY: "
                f"{data['consecutive_failures']} consecutive failures"
            )
        else:
            # Check error rate for degraded state
            total = data.get('success_count', 0) + data.get('error_count', 0)
            if total > 10:  # Need minimum samples
                error_rate = data['error_count'] / total
                if error_rate >= UNHEALTHY_ERROR_RATE:
                    data['current_state'] = HealthState.UNHEALTHY.value
                elif error_rate >= DEGRADED_ERROR_RATE:
                    data['current_state'] = HealthState.DEGRADED.value

        await self.cache.set_async(key, json.dumps(data), HEALTH_STATE_TTL)

    async def _get_health_data(self, provider: str) -> Dict[str, Any]:
        """Get health data for a provider, returning empty dict if not exists."""
        key = self._get_key(provider)
        data = await self.cache.get_async(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {}
        return {}

    async def get_health_state(self, provider: str) -> HealthState:
        """Get current health state for a provider.

        Args:
            provider: Provider name

        Returns:
            HealthState enum (defaults to HEALTHY if no data)
        """
        data = await self._get_health_data(provider)
        state_value = data.get('current_state', HealthState.HEALTHY.value)
        return HealthState(state_value)

    async def get_health_metrics(self, provider: str) -> Dict[str, Any]:
        """Get full health metrics for a provider.

        Args:
            provider: Provider name

        Returns:
            Dict with all health metrics
        """
        data = await self._get_health_data(provider)
        if not data:
            return {
                'provider': provider,
                'state': HealthState.HEALTHY.value,
                'success_count': 0,
                'error_count': 0,
                'consecutive_failures': 0,
                'avg_latency_ms': None
            }
        return {
            'provider': provider,
            'state': data.get('current_state', HealthState.HEALTHY.value),
            'success_count': data.get('success_count', 0),
            'error_count': data.get('error_count', 0),
            'consecutive_failures': data.get('consecutive_failures', 0),
            'consecutive_successes': data.get('consecutive_successes', 0),
            'last_success_ts': data.get('last_success_ts'),
            'last_error_ts': data.get('last_error_ts'),
            'avg_latency_ms': data.get('avg_latency_ms'),
            'last_error': data.get('last_error')
        }

    async def get_all_health(self, providers: list[str]) -> Dict[str, Dict[str, Any]]:
        """Get health metrics for multiple providers.

        Args:
            providers: List of provider names

        Returns:
            Dict mapping provider name to health metrics
        """
        result = {}
        for provider in providers:
            result[provider] = await self.get_health_metrics(provider)
        return result

    def get_health_priority(self, state: HealthState) -> int:
        """Get routing priority for a health state.

        Lower = higher priority for routing.

        Args:
            state: HealthState enum

        Returns:
            Priority value (0=best, 3=worst)
        """
        priorities = {
            HealthState.HEALTHY: 0,
            HealthState.DEGRADED: 1,
            HealthState.RATE_LIMITED: 2,
            HealthState.UNHEALTHY: 3
        }
        return priorities.get(state, 3)
