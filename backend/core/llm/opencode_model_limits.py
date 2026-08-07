"""
Per-model usage levels for OpenCode Go quota-aware routing.

OpenCode Go is a flat-rate subscription, so every request's *marginal* cost is
~$0 — but not every model burns the subscription's token allowance at the same
rate. A reasoning model such as ``kimi-k3`` consumes 30-40x the tokens of
``deepseek-v4-flash`` for the same nominal request, so routing treats each
model's *quota weight* separately:

- weights are derived from the gateway's per-token price table (normalized to
  ``deepseek-v4-flash`` = 1.0), which tracks the real token-allowance burn;
- operators can override weights and add per-model RPM/TPM limits via the
  ``OPENCODE_MODEL_LIMITS`` JSON env var (e.g. to cap a notoriously
  quota-hungry model while leaving the cheap ones unlimited);
- the BPC ranker uses the weight as a value-score penalty (Phase 3) and the
  rate tracker uses per-model limits for hard-skip decisions (Phase 2).
"""
import json
import logging
import os
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Baseline: deepseek-v4-flash input+output price per 1M tokens ($0.14 + $0.28).
# All weights are (in+out per 1M) / baseline, so weight 1.0 = flash-equivalent.
OPCODE_BASELINE_PRICE_PER_1M = 0.42

# Price-derived default quota weights for the OpenCode Zen catalog (Aug 2026).
# Kept in sync with ``DynamicPricingFetcher._opencode_static_fallback``.
OPCODE_DEFAULT_MODEL_WEIGHTS: Dict[str, float] = {
    "deepseek-v4-flash": 1.0,     # $0.14 + $0.28
    "minimax-m2.7": 3.6,          # $0.30 + $1.20
    "minimax-m3": 3.6,            # $0.30 + $1.20
    "qwen3.7-plus": 4.8,          # $0.40 + $1.60
    "kimi-k2.7-code": 11.8,       # $0.95 + $4.00
    "kimi-k2.6": 11.8,            # $0.95 + $4.00
    "deepseek-v4-pro": 12.4,      # $1.74 + $3.48
    "glm-5.1": 13.8,              # $1.40 + $4.40
    "glm-5.2": 13.8,              # $1.40 + $4.40
    "qwen3.7-max": 23.8,          # $2.50 + $7.50
    "kimi-k3": 42.9,              # $3.00 + $15.00
}

# Rate-limit window (seconds) reused by model-scoped tracking.
RATE_WINDOW_SECONDS = 60

# Providers the quota registry applies to (OpenCode Go today; extensible).
QUOTA_PROVIDERS = ("opencode-go",)


def weight_from_prices(input_cost_per_token: float, output_cost_per_token: float) -> float:
    """Derive a quota weight from per-token prices (1.0 = flash-equivalent).

    Unknown/zero pricing yields the default weight 1.0 so routing never
    over-penalizes a model it cannot price.
    """
    try:
        per_1m = float(input_cost_per_token or 0) * 1e6 + float(output_cost_per_token or 0) * 1e6
    except (TypeError, ValueError):
        return 1.0
    if per_1m <= 0:
        return 1.0
    return max(1.0, per_1m / OPCODE_BASELINE_PRICE_PER_1M)


class OpencodeModelLimits:
    """Registry of per-model quota weights + per-model rate limits.

    Thread-safe, process-global. Per-model limits are merged with the
    provider-level RPM/TPM limits at routing time: a model with its own limits
    is hard-skipped independently, so one quota-hungry model cannot take the
    whole provider down.

    Env override (``OPENCODE_MODEL_LIMITS``, JSON)::

        {"deepseek-v4-pro": {"weight": 3.0, "rpm": 20, "tpm": 500000},
         "kimi-k3": {"weight": 15.0, "tpm": 200000}}

    Unknown keys log a warning and are ignored (forward-compat safety).
    """

    def __init__(self) -> None:
        self._weights: Dict[str, float] = dict(OPCODE_DEFAULT_MODEL_WEIGHTS)
        # (provider_id, model_id) -> {rpm, tpm}
        self._model_limits: Dict[tuple, Dict[str, int]] = {}
        self._lock = threading.Lock()
        self._load_env_overrides()

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def _load_env_overrides(self) -> None:
        raw = os.getenv("OPENCODE_MODEL_LIMITS", "").strip()
        if not raw:
            return
        try:
            overrides = json.loads(raw)
        except (ValueError, TypeError) as e:
            logger.warning(f"OPENCODE_MODEL_LIMITS is not valid JSON — ignoring ({e})")
            return
        if not isinstance(overrides, dict):
            logger.warning("OPENCODE_MODEL_LIMITS must be a JSON object — ignoring")
            return
        for model_id, cfg in overrides.items():
            if not isinstance(cfg, dict):
                logger.warning(f"OPENCODE_MODEL_LIMITS[{model_id}] not an object — skipping")
                continue
            weight = cfg.get("weight")
            try:
                self.set_model_limits(
                    "opencode-go",
                    model_id,
                    weight=float(weight) if weight is not None else None,
                    rpm=int(cfg["rpm"]) if cfg.get("rpm") is not None else None,
                    tpm=int(cfg["tpm"]) if cfg.get("tpm") is not None else None,
                )
            except (TypeError, ValueError) as e:
                logger.warning(f"OPENCODE_MODEL_LIMITS[{model_id}] invalid values — skipping ({e})")

    def set_model_limits(
        self,
        provider_id: str,
        model_id: str,
        weight: Optional[float] = None,
        rpm: Optional[int] = None,
        tpm: Optional[int] = None,
    ) -> None:
        """Programmatically override a model's quota weight and/or limits."""
        if not model_id:
            return
        with self._lock:
            if weight is not None:
                w = float(weight)
                self._weights[model_id] = w if w > 0 else 1.0
            limits = self._model_limits.setdefault((provider_id, model_id), {})
            if rpm is not None:
                limits["rpm"] = int(rpm)
            if tpm is not None:
                limits["tpm"] = int(tpm)
            if not limits:
                self._model_limits.pop((provider_id, model_id), None)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_weight(self, provider_id: str, model_id: Optional[str]) -> float:
        """Quota weight for a model (1.0 default — flash-equivalent)."""
        if not model_id:
            return 1.0
        with self._lock:
            return float(self._weights.get(model_id, 1.0))

    def get_model_rate_limits(self, provider_id: str, model_id: Optional[str]) -> Dict[str, int]:
        """Per-model RPM/TPM limits ({} when none configured)."""
        if not model_id:
            return {}
        with self._lock:
            return dict(self._model_limits.get((provider_id, model_id), {}))

    def apply_pricing_weight(self, provider_id: str, model_id: str,
                             input_cost_per_token: Optional[float],
                             output_cost_per_token: Optional[float]) -> float:
        """Update a model's weight from live pricing (overrides env/defaults).

        Returns the effective weight. Price-derived weights only apply when the
        operator did not set an explicit weight override for the model.
        """
        with self._lock:
            has_explicit = (
                (provider_id, model_id) in self._model_limits
                or model_id in self._weights
            )
            if has_explicit and model_id in self._weights:
                return float(self._weights[model_id])
        derived = weight_from_prices(input_cost_per_token, output_cost_per_token)
        if derived > 1.0:
            with self._lock:
                self._weights[model_id] = derived
        return self.get_weight(provider_id, model_id)

    def summary(self, provider_id: str = "opencode-go") -> Dict[str, Any]:
        """Diagnostics: weights + per-model limits for a provider."""
        with self._lock:
            weights = {m: w for m, w in self._weights.items()}
            limits = {
                m: dict(lim)
                for (prov, m), lim in self._model_limits.items()
                if prov == provider_id
            }
        return {
            "provider": provider_id,
            "weights": weights,
            "model_limits": limits,
        }


# Singleton instance
_opencode_model_limits: Optional[OpencodeModelLimits] = None
_singleton_lock = threading.Lock()


def get_opencode_model_limits() -> OpencodeModelLimits:
    """Get or create the singleton OpencodeModelLimits instance."""
    global _opencode_model_limits
    if _opencode_model_limits is None:
        with _singleton_lock:
            if _opencode_model_limits is None:
                _opencode_model_limits = OpencodeModelLimits()
                logger.info("Created OpencodeModelLimits singleton instance")
    return _opencode_model_limits
