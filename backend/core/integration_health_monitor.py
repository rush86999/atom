"""
Integration health monitor — tracks per-integration API success rate and latency.

Mirrors ProviderHealthMonitor but for non-LLM integrations (Slack, Gmail,
HubSpot, Salesforce, etc.). Fed automatically by IntegrationHTTP.request().

A sliding 5-minute window of outcomes produces a health score:
  score = 0.7 * success_rate + 0.3 * latency_score
  where latency_score = 1.0 if p95 < 2s, scaling down to 0 at 10s+.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional

logger = logging.getLogger(__name__)

_WINDOW_SECONDS = 300  # 5-minute sliding window
_MAX_SAMPLES = 500     # cap per integration to bound memory


class _Sample:
    __slots__ = ("timestamp", "success", "latency_ms")

    def __init__(self, success: bool, latency_ms: float):
        self.timestamp = time.monotonic()
        self.success = success
        self.latency_ms = latency_ms


class IntegrationHealthMonitor:
    """Tracks per-integration health via a sliding-window of call outcomes."""

    def __init__(self, window_seconds: int = _WINDOW_SECONDS):
        self._window = window_seconds
        self._samples: Dict[str, Deque[_Sample]] = defaultdict(
            lambda: deque(maxlen=_MAX_SAMPLES)
        )

    def record(self, integration: str, success: bool, latency_ms: float) -> None:
        """Record a single API call outcome."""
        self._samples[integration].append(_Sample(success, latency_ms))

    def get_health(self, integration: str) -> float:
        """Health score 0.0–1.0 for an integration.

        0.0 = all failures; 1.0 = all successes with <2s latency.
        Returns 1.0 if no data (assume healthy until proven otherwise).
        """
        samples = self._prune(integration)
        if not samples:
            return 1.0

        success_count = sum(1 for s in samples if s.success)
        success_rate = success_count / len(samples)

        # Latency score: 1.0 at 0-2s, linear down to 0 at 10s+.
        latencies = sorted(s.latency_ms for s in samples if s.success)
        if latencies:
            p95_idx = int(len(latencies) * 0.95)
            p95 = latencies[min(p95_idx, len(latencies) - 1)]
            latency_score = max(0.0, 1.0 - max(0.0, (p95 - 2000)) / 8000)
        else:
            latency_score = 0.0

        return 0.7 * success_rate + 0.3 * latency_score

    def get_unhealthy(self, threshold: float = 0.5) -> List[str]:
        """List integrations below the health threshold."""
        return [
            name for name in self._samples
            if self.get_health(name) < threshold
        ]

    def get_stats(self) -> Dict[str, Dict]:
        """Summary stats for all tracked integrations (for dashboards)."""
        result = {}
        for name in self._samples:
            samples = self._prune(name)
            if not samples:
                continue
            success_count = sum(1 for s in samples if s.success)
            latencies = [s.latency_ms for s in samples if s.success]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            result[name] = {
                "health_score": round(self.get_health(name), 3),
                "total_calls": len(samples),
                "success_rate": round(success_count / len(samples), 3),
                "avg_latency_ms": round(avg_latency, 1),
                "status": "healthy" if self.get_health(name) >= 0.5 else "unhealthy",
            }
        return result

    def _prune(self, integration: str) -> List[_Sample]:
        """Remove expired samples and return the remaining list."""
        cutoff = time.monotonic() - self._window
        samples = self._samples.get(integration)
        if not samples:
            return []
        # Pop from left while expired (deque is append-ordered).
        while samples and samples[0].timestamp < cutoff:
            samples.popleft()
        return list(samples)


# Singleton.
_integration_health_monitor: Optional[IntegrationHealthMonitor] = None


def get_integration_health_monitor() -> IntegrationHealthMonitor:
    global _integration_health_monitor
    if _integration_health_monitor is None:
        _integration_health_monitor = IntegrationHealthMonitor()
    return _integration_health_monitor
