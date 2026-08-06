"""
Per-provider rate & limit configuration for BYOK routing decisions.

Each provider can declare its own custom rates and limits (requests/minute,
tokens/minute, max context window). The BPC ranker in ``byok_handler`` uses
these to:

- clamp candidate models to the provider's context limit,
- apply a rate-headroom penalty to the value score when a provider is
  approaching its RPM/TPM ceiling, and
- hard-skip providers whose rate budget is exhausted.

``OpenCode Go`` (the low-cost opencoding subscription via the OpenCode Zen
gateway) ships with its own custom defaults, overridable via env vars:

- ``OPENCODE_RPM``            — max requests per minute (default 60)
- ``OPENCODE_TPM``            — max tokens per minute (default 2_000_000)
- ``OPENCODE_MAX_CONTEXT``    — max context tokens the gateway serves (default 200_000)

Usage is tracked in a process-wide sliding window (60s) so routing decisions
reflect recent observed traffic without any external dependency.
"""
import os
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = __import__("logging").getLogger(__name__)

# Rate-limit window (seconds) for RPM/TPM tracking.
RATE_WINDOW_SECONDS = 60


def _env_int(name: str, default: int) -> int:
    """Read an integer env var with a safe fallback."""
    try:
        return int(os.getenv(name, "").strip())
    except (TypeError, ValueError):
        return default


def _build_provider_rate_limits() -> Dict[str, Dict[str, int]]:
    """Build the custom per-provider rate/limit registry.

    Only providers that opt in get limits; providers absent from this map are
    treated as unlimited by the routing layer (headroom = 1.0, no context
    clamp), preserving existing behavior.
    """
    limits: Dict[str, Dict[str, int]] = {
        # OpenCode Go — low-cost subscription via https://opencode.ai/zen/v1.
        # Custom rates/limits tuned for the subscription plan; each is
        # overridable via env so operators can match their actual tier.
        "opencode-go": {
            "rpm": _env_int("OPENCODE_RPM", 60),
            "tpm": _env_int("OPENCODE_TPM", 2_000_000),
            "max_context": _env_int("OPENCODE_MAX_CONTEXT", 200_000),
        },
        # OpenRouter gateway — conservative shared-key defaults.
        "openrouter": {
            "rpm": _env_int("OPENROUTER_RPM", 50),
            "tpm": _env_int("OPENROUTER_TPM", 1_000_000),
            "max_context": _env_int("OPENROUTER_MAX_CONTEXT", 200_000),
        },
    }
    return limits


PROVIDER_RATE_LIMITS: Dict[str, Dict[str, int]] = _build_provider_rate_limits()


class ProviderRateTracker:
    """Thread-safe sliding-window RPM/TPM tracker per provider.

    Mirrors the ``ProviderHealthMonitor`` pattern: a process-global singleton
    with a bounded sliding window so routing can ask "how much of this
    provider's custom budget is still available right now?".
    """

    def __init__(self, window_seconds: int = RATE_WINDOW_SECONDS):
        self.window_seconds = window_seconds
        # provider_id -> deque of (timestamp, input_tokens, output_tokens)
        self._usage: Dict[str, deque] = {}
        self._lock = threading.Lock()
        self._limits: Dict[str, Dict[str, int]] = {
            k: dict(v) for k, v in PROVIDER_RATE_LIMITS.items()
        }

    def set_rate_limits(self, provider_id: str, rpm: Optional[int] = None,
                        tpm: Optional[int] = None,
                        max_context: Optional[int] = None) -> None:
        """Programmatically override a provider's custom limits."""
        with self._lock:
            limits = self._limits.setdefault(provider_id, {})
            if rpm is not None:
                limits["rpm"] = int(rpm)
            if tpm is not None:
                limits["tpm"] = int(tpm)
            if max_context is not None:
                limits["max_context"] = int(max_context)

    def get_rate_limits(self, provider_id: str) -> Dict[str, int]:
        """Return the custom limits for a provider ({} when unconfigured)."""
        with self._lock:
            return dict(self._limits.get(provider_id, {}))

    def record_usage(self, provider_id: str, input_tokens: int, output_tokens: int) -> None:
        """Record a call's token usage in the sliding window (best-effort)."""
        if not self._limits.get(provider_id):
            # No custom limits configured — nothing to track for routing.
            return
        try:
            now = datetime.now(timezone.utc)
            with self._lock:
                window = self._usage.setdefault(provider_id, deque())
                window.append((now, int(input_tokens or 0), int(output_tokens or 0)))
                self._trim(provider_id, now)
        except Exception:
            logger.debug("Rate usage recording failed (non-fatal)", exc_info=True)

    def _trim(self, provider_id: str, now: Optional[datetime] = None) -> None:
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(seconds=self.window_seconds)
        window = self._usage.get(provider_id)
        while window and window[0][0] < cutoff:
            window.popleft()

    def get_headroom(self, provider_id: str) -> float:
        """Fraction (0.0–1.0) of the provider's custom rate budget remaining.

        1.0 = full budget available; 0.0 = at/over limit (callers hard-skip).
        Providers without custom limits always report 1.0.
        """
        limits = self.get_rate_limits(provider_id)
        if not limits:
            return 1.0
        rpm_limit = limits.get("rpm") or 0
        tpm_limit = limits.get("tpm") or 0
        if rpm_limit <= 0 and tpm_limit <= 0:
            return 1.0
        with self._lock:
            self._trim(provider_id)
            window = list(self._usage.get(provider_id, ()))
        requests = len(window)
        tokens = sum(inp + out for _, inp, out in window)
        headroom = 1.0
        if rpm_limit > 0:
            headroom = min(headroom, max(0.0, 1.0 - requests / rpm_limit))
        if tpm_limit > 0:
            headroom = min(headroom, max(0.0, 1.0 - tokens / tpm_limit))
        return round(headroom, 4)

    def get_max_context(self, provider_id: str) -> Optional[int]:
        """Provider-level context cap (None = no clamp)."""
        limits = self.get_rate_limits(provider_id)
        max_context = limits.get("max_context")
        return int(max_context) if max_context and max_context > 0 else None

    def usage_summary(self, provider_id: str) -> Dict[str, Any]:
        """Diagnostics: requests/tokens in the current window + limits."""
        limits = self.get_rate_limits(provider_id)
        with self._lock:
            self._trim(provider_id)
            window = list(self._usage.get(provider_id, ()))
        requests = len(window)
        tokens = sum(inp + out for _, inp, out in window)
        return {
            "provider": provider_id,
            "requests_in_window": requests,
            "tokens_in_window": tokens,
            "limits": limits,
            "headroom": self.get_headroom(provider_id),
        }


# Singleton instance (mirrors get_provider_health_monitor)
_rate_tracker: Optional[ProviderRateTracker] = None
_singleton_lock = threading.Lock()


def get_provider_rate_tracker() -> ProviderRateTracker:
    """Get or create the singleton ProviderRateTracker instance."""
    global _rate_tracker
    if _rate_tracker is None:
        with _singleton_lock:
            if _rate_tracker is None:
                _rate_tracker = ProviderRateTracker()
                logger.info("Created ProviderRateTracker singleton instance")
    return _rate_tracker
