"""
Per-provider & per-model rate and limit configuration for BYOK routing.

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

Per-model extension (OpenCode Go quota accounting):

- Each model carries a *quota weight* (see ``core.llm.opencode_model_limits``)
  so provider-level token consumption is weighted — a request to ``kimi-k3``
  counts ~43x a ``deepseek-v4-flash`` request against the shared TPM budget.
- Models can declare their own RPM/TPM limits (``OPENCODE_MODEL_LIMITS`` env or
  ``set_model_limits``) so one quota-hungry model is hard-skipped
  independently instead of taking the whole provider down.
- Consumption is optionally persisted (``RateUsagePersistence``) so monthly
  subscription allowances survive restarts; ``get_monthly_usage`` feeds the
  opt-in ``OPENCODE_MONTHLY_TPM`` hard-skip in the ranker.
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
    """Thread-safe sliding-window RPM/TPM tracker per provider (and model).

    Mirrors the ``ProviderHealthMonitor`` pattern: a process-global singleton
    with a bounded sliding window so routing can ask "how much of this
    provider's custom budget is still available right now?".

    Window entries are ``(timestamp, input_tokens, output_tokens, model_id)``
    tuples; legacy 3-tuples (pre-per-model) are still read correctly.
    """

    def __init__(self, window_seconds: int = RATE_WINDOW_SECONDS):
        self.window_seconds = window_seconds
        # provider_id -> deque of (timestamp, input_tokens, output_tokens, model_id)
        self._usage: Dict[str, deque] = {}
        self._lock = threading.Lock()
        self._limits: Dict[str, Dict[str, int]] = {
            k: dict(v) for k, v in PROVIDER_RATE_LIMITS.items()
        }
        self._persistence: Any = None
        self._model_registry: Any = None

    def set_persistence(self, persistence: Any) -> None:
        """Wire an optional usage persistence layer (monthly quota reads)."""
        self._persistence = persistence

    def _registry(self) -> Any:
        """Lazy-import the per-model limits registry (avoids import cycles)."""
        if self._model_registry is None:
            try:
                from core.llm.opencode_model_limits import get_opencode_model_limits

                self._model_registry = get_opencode_model_limits()
            except Exception as e:
                logger.debug(f"Per-model limits registry unavailable (non-fatal): {e}")
        return self._model_registry

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

    def set_model_limits(self, provider_id: str, model_id: str,
                         weight: Optional[float] = None,
                         rpm: Optional[int] = None,
                         tpm: Optional[int] = None) -> None:
        """Programmatically override a model's quota weight and/or limits."""
        registry = self._registry()
        if registry is not None:
            registry.set_model_limits(provider_id, model_id,
                                      weight=weight, rpm=rpm, tpm=tpm)

    def get_model_rate_limits(self, provider_id: str, model_id: Optional[str]) -> Dict[str, int]:
        """Per-model RPM/TPM limits ({} when none configured)."""
        registry = self._registry()
        if registry is None:
            return {}
        try:
            return registry.get_model_rate_limits(provider_id, model_id)
        except Exception:
            return {}

    def _model_weight(self, provider_id: str, model_id: Optional[str]) -> float:
        registry = self._registry()
        if registry is None:
            return 1.0
        try:
            return registry.get_weight(provider_id, model_id)
        except Exception:
            return 1.0

    def record_usage(self, provider_id: str, input_tokens: int, output_tokens: int,
                     model_id: Optional[str] = None) -> None:
        """Record a call's token usage in the sliding window (best-effort).

        ``model_id`` enables per-model accounting: the provider-level TPM
        consumption is weighted by the model's quota weight, and per-model
        limits can be enforced independently.
        """
        if not self._limits.get(provider_id):
            # No custom limits configured — nothing to track for routing.
            return
        try:
            now = datetime.now(timezone.utc)
            with self._lock:
                window = self._usage.setdefault(provider_id, deque())
                window.append((now, int(input_tokens or 0), int(output_tokens or 0), model_id))
                self._trim(provider_id, now)
        except Exception:
            logger.debug("Rate usage recording failed (non-fatal)", exc_info=True)
        # Persist monthly consumption (fire-and-forget) when wired.
        if self._persistence is not None:
            try:
                self._persistence.record(provider_id, model_id,
                                         int(input_tokens or 0), int(output_tokens or 0))
            except Exception:
                logger.debug("Rate usage persistence failed (non-fatal)", exc_info=True)

    def _trim(self, provider_id: str, now: Optional[datetime] = None) -> None:
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(seconds=self.window_seconds)
        window = self._usage.get(provider_id)
        while window and window[0][0] < cutoff:
            window.popleft()

    def _window_totals(self, provider_id: str, model_id: Optional[str] = None,
                       weighted: bool = True):
        """(requests, weighted_tokens) for a provider (or a single model).

        Entries may be 3-tuples (legacy) or 4-tuples (with model_id). When
        ``model_id`` is given, only matching 4-tuple entries count.
        """
        with self._lock:
            self._trim(provider_id)
            window = list(self._usage.get(provider_id, ()))
        if model_id is not None:
            window = [e for e in window if len(e) > 3 and e[3] == model_id]
        requests = len(window)
        tokens = 0.0
        for entry in window:
            inp = entry[1] or 0
            out = entry[2] or 0
            entry_model = entry[3] if len(entry) > 3 else None
            if weighted:
                tokens += (inp + out) * self._model_weight(provider_id, entry_model)
            else:
                tokens += inp + out
        return requests, tokens

    @staticmethod
    def _headroom_from(requests: int, tokens: float,
                       rpm_limit: int, tpm_limit: int) -> float:
        headroom = 1.0
        if rpm_limit > 0:
            headroom = min(headroom, max(0.0, 1.0 - requests / rpm_limit))
        if tpm_limit > 0:
            headroom = min(headroom, max(0.0, 1.0 - tokens / tpm_limit))
        return round(headroom, 4)

    def get_headroom(self, provider_id: str) -> float:
        """Fraction (0.0–1.0) of the provider's custom rate budget remaining.

        Token consumption is **weighted by each model's quota weight**, so a
        request to a quota-hungry model (e.g. ``kimi-k3``) depletes the shared
        budget faster than a ``deepseek-v4-flash`` request. 1.0 = full budget
        available; 0.0 = at/over limit (callers hard-skip). Providers without
        custom limits always report 1.0.
        """
        limits = self.get_rate_limits(provider_id)
        if not limits:
            return 1.0
        rpm_limit = limits.get("rpm") or 0
        tpm_limit = limits.get("tpm") or 0
        if rpm_limit <= 0 and tpm_limit <= 0:
            return 1.0
        requests, tokens = self._window_totals(provider_id, weighted=True)
        return self._headroom_from(requests, tokens, rpm_limit, tpm_limit)

    def get_model_headroom(self, provider_id: str, model_id: Optional[str]) -> float:
        """Per-model headroom (0.0–1.0) using the model's own RPM/TPM limits.

        Models without their own limits fall back to the provider headroom.
        """
        if model_id is None:
            return self.get_headroom(provider_id)
        limits = self.get_model_rate_limits(provider_id, model_id)
        if not limits:
            return self.get_headroom(provider_id)
        rpm_limit = limits.get("rpm") or 0
        tpm_limit = limits.get("tpm") or 0
        if rpm_limit <= 0 and tpm_limit <= 0:
            return self.get_headroom(provider_id)
        requests, tokens = self._window_totals(provider_id, model_id=model_id, weighted=True)
        return self._headroom_from(requests, tokens, rpm_limit, tpm_limit)

    def get_model_weight(self, provider_id: str, model_id: Optional[str]) -> float:
        """Quota weight for a model (1.0 = flash-equivalent, or default)."""
        return self._model_weight(provider_id, model_id)

    def get_max_context(self, provider_id: str) -> Optional[int]:
        """Provider-level context cap (None = no clamp)."""
        limits = self.get_rate_limits(provider_id)
        max_context = limits.get("max_context")
        return int(max_context) if max_context and max_context > 0 else None

    def get_monthly_usage(self, provider_id: str,
                          model_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Monthly aggregated usage for a provider/model (None when unavailable).

        Requires a wired persistence layer; used by the opt-in
        ``OPENCODE_MONTHLY_TPM`` hard-skip in the BPC ranker.
        """
        if self._persistence is None:
            return None
        try:
            return self._persistence.monthly_usage(provider_id, model_id)
        except Exception:
            logger.debug("Rate usage monthly read failed (non-fatal)", exc_info=True)
            return None

    def usage_summary(self, provider_id: str) -> Dict[str, Any]:
        """Diagnostics: requests/tokens in the current window + limits.

        Includes a per-model breakdown (window requests, weighted tokens,
        per-model headroom) and monthly totals when persistence is wired.
        """
        limits = self.get_rate_limits(provider_id)
        requests, tokens = self._window_totals(provider_id, weighted=True)
        summary: Dict[str, Any] = {
            "provider": provider_id,
            "requests_in_window": requests,
            "tokens_in_window": round(tokens, 1),
            "limits": limits,
            "headroom": self.get_headroom(provider_id),
        }
        # Per-model breakdown (models observed in the window + known registry).
        models: Dict[str, Any] = {}
        with self._lock:
            window = list(self._usage.get(provider_id, ()))
        seen = {e[3] for e in window if len(e) > 3 and e[3] is not None}
        for model_id in sorted(s for s in seen if s):
            m_req, m_tok = self._window_totals(provider_id, model_id=model_id, weighted=True)
            models[model_id] = {
                "requests_in_window": m_req,
                "tokens_in_window": round(m_tok, 1),
                "weight": self.get_model_weight(provider_id, model_id),
                "limits": self.get_model_rate_limits(provider_id, model_id),
                "headroom": self.get_model_headroom(provider_id, model_id),
            }
        if models:
            summary["models"] = models
        # Monthly totals (best-effort).
        monthly = self.get_monthly_usage(provider_id)
        if monthly:
            summary["monthly"] = monthly
        return summary


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
                try:
                    from core.llm.rate_usage_persistence import get_rate_usage_persistence

                    _rate_tracker.set_persistence(get_rate_usage_persistence())
                except Exception as e:
                    logger.debug(f"Rate usage persistence unavailable (non-fatal): {e}")
                logger.info("Created ProviderRateTracker singleton instance")
    return _rate_tracker
