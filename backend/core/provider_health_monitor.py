"""
Provider Health Monitor
Health tracking service for LLM provider API calls using Exponential Moving Average
"""
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class ProviderHealthMonitor:
    """
    Tracks provider API health (success rate, latency) using sliding window and EMA

    Health scoring combines:
    - 70% success rate (requests that succeeded)
    - 30% latency score (inverse of response time, 5s = 0 score)

    Uses sliding window (default 5 minutes) to prevent memory leaks
    and ensure health scores reflect recent performance.

    Connection failures additionally drive a short circuit breaker: a provider
    that fails ``CONN_FAIL_BREAKER_THRESHOLD`` consecutive connection attempts
    is skipped by routing entirely for ``CONN_FAIL_BREAKER_COOLDOWN_SECONDS``
    (half-open recovery: the first attempt after cooldown is allowed, and a
    failure re-opens the breaker). Without this, a dead gateway keeps ranking
    on cost/value alone and every LLM call stage re-pays the full
    connection-timeout retry cascade before falling over to the next provider.
    """

    CONN_FAIL_BREAKER_THRESHOLD = 1
    CONN_FAIL_BREAKER_COOLDOWN_SECONDS = 60.0

    def __init__(self, window_minutes: int = 5):
        """
        Initialize health monitor

        Args:
            window_minutes: Sliding window duration in minutes (default: 5)
        """
        self.window_minutes = window_minutes
        self.call_history: Dict[str, deque] = {}  # provider_id -> deque of (timestamp, success, latency_ms)
        self.health_scores: Dict[str, float] = {}  # provider_id -> 0.0-1.0 score
        # Guards call_history/health_scores. This monitor is a process-global
        # singleton shared across every BYOKHandler/async-task/thread, and
        # record_call does deque.append + popleft trim + dict write; without a
        # lock, concurrent calls corrupt the deque/dict (lost updates, and
        # "deque mutated during iteration" / RuntimeError during _update_health_score).
        self._lock = threading.Lock()
        # Connection-failure breaker state (guarded by _lock): consecutive
        # connection failures per provider and the monotonic deadline until
        # which routing must skip the provider.
        self._conn_fail_streak: Dict[str, int] = {}
        self._breaker_open_until: Dict[str, float] = {}

    def record_call(self, provider_id: str, success: bool, latency_ms: float,
                    connection_failure: bool = False):
        """
        Record API call outcome for health tracking

        Args:
            provider_id: Provider identifier (e.g. 'openai', 'anthropic')
            success: True if call succeeded, False if failed
            latency_ms: Response time in milliseconds
            connection_failure: True when the failure was a connect-level
                error (timeout, refused, unreachable). Counts toward the
                circuit breaker; ordinary failures (schema, rate limit) do not.
        """
        timestamp = datetime.now(timezone.utc)

        # All state mutation (deque append + trim + score write) is atomic under
        # the lock so concurrent record_call / get_* calls can't interleave on
        # the shared singleton (see __init__).
        with self._lock:
            # Initialize deque for new provider
            if provider_id not in self.call_history:
                self.call_history[provider_id] = deque()
                logger.debug(f"Initialized health tracking for provider: {provider_id}")

            history = self.call_history[provider_id]
            history.append((timestamp, success, latency_ms))

            # Trim old entries outside sliding window to prevent memory leaks
            self._trim_old_entries(provider_id)

            # Update health score using EMA calculation
            self._update_health_score(provider_id)

            if success:
                self._conn_fail_streak.pop(provider_id, None)
                if self._breaker_open_until.pop(provider_id, None) is not None:
                    logger.info(f"Circuit breaker closed for provider {provider_id} (call succeeded)")
            elif connection_failure:
                streak = self._conn_fail_streak.get(provider_id, 0) + 1
                self._conn_fail_streak[provider_id] = streak
                if (streak >= self.CONN_FAIL_BREAKER_THRESHOLD
                        and provider_id not in self._breaker_open_until):
                    self._breaker_open_until[provider_id] = (
                        time.monotonic() + self.CONN_FAIL_BREAKER_COOLDOWN_SECONDS
                    )
                    logger.warning(
                        f"Circuit breaker OPEN for provider {provider_id} "
                        f"({streak} consecutive connection failures) — skipping for "
                        f"{self.CONN_FAIL_BREAKER_COOLDOWN_SECONDS:.0f}s"
                    )

            score = self.health_scores[provider_id]

        logger.debug(
            f"Recorded call for {provider_id}: success={success}, "
            f"latency={latency_ms}ms, health_score={score:.3f}"
        )

    def get_health_score(self, provider_id: str) -> float:
        """
        Get current health score for provider (0.0-1.0)

        Args:
            provider_id: Provider identifier

        Returns:
            Health score from 0.0 (unhealthy) to 1.0 (healthy)
            Returns 1.0 for providers with no history (optimistic default)
        """
        if provider_id not in self.health_scores:
            logger.debug(f"No health history for {provider_id}, returning default 1.0")
            return 1.0
        with self._lock:
            # Snapshot under the lock so a concurrent record_call can't mutate
            # the dict mid-read.
            return round(self.health_scores[provider_id], 3)

    def is_breaker_open(self, provider_id: str) -> bool:
        """
        True while the provider is benched for recent connection failures.

        Read under the lock; the monotonic deadline makes expiry automatic —
        the first routing decision after the cooldown closes the breaker
        (half-open) and lets one attempt through.
        """
        with self._lock:
            deadline = self._breaker_open_until.get(provider_id)
            if deadline is None:
                return False
            if time.monotonic() >= deadline:
                # Cooldown elapsed — close (half-open); a failed attempt
                # re-opens via record_call(connection_failure=True).
                self._breaker_open_until.pop(provider_id, None)
                logger.info(f"Circuit breaker half-open for provider {provider_id} — allowing attempt")
                return False
            return True

    def get_healthy_providers(self, min_score: float = 0.5) -> List[str]:
        """
        Get providers with health score above threshold

        Args:
            min_score: Minimum health score (0.0-1.0), default 0.5

        Returns:
            List of provider IDs with health_score >= min_score
        """
        healthy = []
        with self._lock:
            # Iterate a snapshot of items so a concurrent record_call can't
            # mutate the dict during the comprehension.
            for provider_id, score in list(self.health_scores.items()):
                if score >= min_score:
                    healthy.append(provider_id)
        logger.debug(f"Healthy providers (min_score={min_score}): {healthy}")
        return healthy

    def _update_health_score(self, provider_id: str):
        """
        Calculate health score using EMA (70% success rate, 30% latency)

        Formula: health_score = (success_rate * 0.7) + (latency_score * 0.3)

        - success_rate: successful calls / total calls
        - latency_score: max(0, 1 - (avg_latency_ms / 5000))
          (5000ms latency = 0 score, 0ms latency = 1.0 score)
        """
        history = self.call_history.get(provider_id, deque())

        if not history:
            # No history means healthy (optimistic default for new providers)
            self.health_scores[provider_id] = 1.0
            return

        # Calculate success rate (70% weight)
        success_count = sum(1 for _, success, _ in history if success)
        success_rate = success_count / len(history)

        # Calculate average latency
        avg_latency = sum(lat for _, _, lat in history) / len(history)

        # Calculate latency score (30% weight, inverse relationship)
        # 5s latency = 0 score, 0ms latency = 1.0 score
        latency_score = max(0, 1 - (avg_latency / 5000))

        # Combined EMA score
        health_score = (success_rate * 0.7) + (latency_score * 0.3)

        # Round to 3 decimal places for consistency
        self.health_scores[provider_id] = round(health_score, 3)

        logger.debug(
            f"Updated health score for {provider_id}: "
            f"success_rate={success_rate:.3f}, latency_score={latency_score:.3f}, "
            f"combined={health_score:.3f}"
        )

    def _trim_old_entries(self, provider_id: str):
        """
        Remove entries outside sliding window to prevent memory leaks

        Args:
            provider_id: Provider identifier
        """
        if provider_id not in self.call_history:
            return

        history = self.call_history[provider_id]
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.window_minutes)

        # Remove old entries from left side of deque (O(1) operation)
        trimmed_count = 0
        while history and history[0][0] < cutoff:
            history.popleft()
            trimmed_count += 1

        if trimmed_count > 0:
            logger.debug(
                f"Trimmed {trimmed_count} old entries for {provider_id} "
                f"(window: {self.window_minutes} minutes)"
            )


# Singleton instance
_health_monitor: ProviderHealthMonitor | None = None
_singleton_lock = threading.Lock()


def get_provider_health_monitor() -> ProviderHealthMonitor:
    """
    Get or create singleton ProviderHealthMonitor instance

    Returns:
        Shared ProviderHealthMonitor instance
    """
    global _health_monitor
    if _health_monitor is None:
        # Double-checked locking: two concurrent first-callers would otherwise
        # each build a monitor and one (with whatever state it had accumulated)
        # would be discarded.
        with _singleton_lock:
            if _health_monitor is None:
                _health_monitor = ProviderHealthMonitor()
                logger.info("Created ProviderHealthMonitor singleton instance")
    return _health_monitor
