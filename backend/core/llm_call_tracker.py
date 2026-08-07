"""
Per-call LLM provider usage tracking.

Records one row per LLM provider attempt (success or failure) across every
dispatch path in ``core.llm.byok_handler`` (generate_response, structured,
streaming, gateway chat_completion) for ALL providers — opencode-go, openai,
anthropic, deepseek, gemini, ollama, etc.

Each record carries the ten tracked fields:

    timestamp         when the call finished (aware UTC datetime)
    provider          provider id (e.g. "opencode-go")
    model             model name (e.g. "gpt-5")
    success           whether the attempt returned a usable result
    latency_ms        end-to-end attempt latency
    input_tokens      prompt tokens reported by the provider (0 if unknown)
    output_tokens     completion tokens reported by the provider (chunk
                      count for streams — real usage is not exposed there)
    fallback          True when this attempt was not the primary candidate
    fallback_provider primary provider id when fallback=True, else None
    error             truncated error message when success=False, else None

Design notes:

- Self-contained Prometheus metrics (module-level counters/histograms on the
  default registry, mirroring ``core/webhook_metrics.py`` /
  ``core/integration_metrics.py``) — scraped by the existing
  ``/health/metrics`` endpoint with no extra wiring.
- The in-memory buffer is thread-safe and bounded (most recent records
  kept) so the process-wide singleton never leaks memory, matching
  ``core/llm_usage_tracker.py`` and ``core/provider_health_monitor.py``.
- ``record`` never raises: failures are logged and swallowed so the hot LLM
  dispatch path is unaffected (graceful degradation, consistent with the
  rest of the codebase).
- Metrics are only labels — high-cardinality model names are bounded by the
  providers actually in use; records are capped for queries.
"""
import logging
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)

# Bound on retained records in the process-wide singleton.
DEFAULT_MAX_RECORDS = 5000
# Cap on error strings retained per record (bounds memory).
MAX_ERROR_LEN = 500


# ============================================================================
# PROMETHEUS METRICS (module-level, default registry — scraped by /health/metrics)
# ============================================================================

llm_calls_total = Counter(
    "llm_calls_total",
    "Total LLM provider calls",
    ["provider", "model", "success", "fallback"],
)

llm_call_duration_seconds = Histogram(
    "llm_call_duration_seconds",
    "LLM provider call latency",
    ["provider", "model"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120),
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total LLM tokens consumed by provider call",
    ["provider", "model", "direction"],  # direction: input | output
)

llm_fallbacks_total = Counter(
    "llm_fallbacks_total",
    "LLM calls served by a fallback provider",
    ["provider", "fallback_provider"],
)

llm_call_errors_total = Counter(
    "llm_call_errors_total",
    "Failed LLM provider calls",
    ["provider", "model"],
)


@dataclass
class LLMCallRecord:
    """One LLM provider attempt (success or failure)."""

    timestamp: datetime
    provider: str
    model: str
    success: bool
    latency_ms: float
    input_tokens: int
    output_tokens: int
    fallback: bool
    fallback_provider: Optional[str] = None
    error: Optional[str] = None


class LLMCallTracker:
    """Thread-safe, bounded per-call LLM usage tracker.

    Each ``record`` appends a :class:`LLMCallRecord` to the buffer (most
    recent kept) and emits the Prometheus metrics above. All methods are
    safe to call from the async dispatch loops (record is synchronous and
    O(1)-ish; metric emission is lock-protected inside prometheus_client).
    """

    def __init__(self, maxlen: int = DEFAULT_MAX_RECORDS) -> None:
        self._maxlen = max(int(maxlen), 1)
        self._records: Deque[LLMCallRecord] = deque(maxlen=self._maxlen)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def record(
        self,
        provider: str,
        model: str,
        success: bool,
        latency_ms: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        fallback: bool = False,
        fallback_provider: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Record one LLM provider attempt. Never raises."""
        try:
            ok = bool(success)
            inp = max(int(input_tokens or 0), 0)
            outp = max(int(output_tokens or 0), 0)
            latency = max(float(latency_ms or 0.0), 0.0)
            err = (str(error)[:MAX_ERROR_LEN]) if error else None
            if fallback and not fallback_provider:
                fallback_provider = None

            rec = LLMCallRecord(
                timestamp=datetime.now(timezone.utc),
                provider=str(provider),
                model=str(model),
                success=ok,
                latency_ms=latency,
                input_tokens=inp,
                output_tokens=outp,
                fallback=bool(fallback),
                fallback_provider=fallback_provider,
                error=err,
            )
            with self._lock:
                self._records.append(rec)

            self._emit_metrics(rec)
        except Exception as e:  # pragma: no cover - defensive
            logger.debug(f"LLM call tracking failed (non-fatal): {e}")

    def _emit_metrics(self, rec: LLMCallRecord) -> None:
        """Fire the Prometheus counters/histogram for one record."""
        try:
            llm_calls_total.labels(
                provider=rec.provider, model=rec.model,
                success="true" if rec.success else "false",
                fallback="true" if rec.fallback else "false",
            ).inc()
            llm_call_duration_seconds.labels(
                provider=rec.provider, model=rec.model
            ).observe(rec.latency_ms / 1000.0)
            if rec.input_tokens:
                llm_tokens_total.labels(
                    provider=rec.provider, model=rec.model, direction="input"
                ).inc(rec.input_tokens)
            if rec.output_tokens:
                llm_tokens_total.labels(
                    provider=rec.provider, model=rec.model, direction="output"
                ).inc(rec.output_tokens)
            if rec.fallback and rec.fallback_provider:
                llm_fallbacks_total.labels(
                    provider=rec.provider, fallback_provider=rec.fallback_provider
                ).inc()
            if not rec.success:
                llm_call_errors_total.labels(
                    provider=rec.provider, model=rec.model
                ).inc()
        except Exception as e:  # pragma: no cover - defensive
            logger.debug(f"LLM call metric emission failed (non-fatal): {e}")

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_recent_calls(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        limit: int = 100,
    ) -> List[LLMCallRecord]:
        """Most recent records (newest first), optionally filtered.

        ``limit`` is clamped to ``[1, maxlen]``.
        """
        with self._lock:
            records = list(self._records)
        if provider:
            records = [r for r in records if r.provider == provider]
        if model:
            records = [r for r in records if r.model == model]
        n = max(1, min(int(limit or 100), self._maxlen))
        return list(reversed(records[-n:]))

    def get_summary(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Aggregated stats over the retained records (optionally filtered).

        Returns totals plus per-provider and per-model rollups: call counts,
        success/failure/fallback counts, token totals, and avg latency.
        """
        with self._lock:
            records = list(self._records)
        if provider:
            records = [r for r in records if r.provider == provider]
        if model:
            records = [r for r in records if r.model == model]

        def rollup(items: List[LLMCallRecord]) -> Dict[str, Any]:
            total = len(items)
            ok = sum(1 for r in items if r.success)
            failed = total - ok
            fb = sum(1 for r in items if r.fallback)
            inp = sum(r.input_tokens for r in items)
            outp = sum(r.output_tokens for r in items)
            lat = sum(r.latency_ms for r in items)
            return {
                "total_calls": total,
                "successful_calls": ok,
                "failed_calls": failed,
                "fallback_calls": fb,
                "total_input_tokens": inp,
                "total_output_tokens": outp,
                "total_tokens": inp + outp,
                "avg_latency_ms": (lat / total) if total else 0.0,
                "last_call": records[-1].timestamp.isoformat() if records else None,
            }

        by_provider: Dict[str, List[LLMCallRecord]] = {}
        by_model: Dict[str, List[LLMCallRecord]] = {}
        for r in records:
            by_provider.setdefault(r.provider, []).append(r)
            by_model.setdefault(r.model, []).append(r)

        return {
            **rollup(records),
            "by_provider": {k: rollup(v) for k, v in by_provider.items()},
            "by_model": {k: rollup(v) for k, v in by_model.items()},
        }

    def clear(self) -> None:
        """Drop all retained records (metrics counters are NOT reset)."""
        with self._lock:
            self._records.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)


# ============================================================================
# SINGLETON
# ============================================================================

_singleton: Optional[LLMCallTracker] = None
_singleton_lock = threading.Lock()


def get_llm_call_tracker() -> LLMCallTracker:
    """Get the process-wide LLM call tracker singleton."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = LLMCallTracker()
                logger.info(
                    f"Created LLM call tracker singleton (maxlen={DEFAULT_MAX_RECORDS})"
                )
    return _singleton


# Export singleton for convenience (mirrors core/llm_usage_tracker.py).
llm_call_tracker = get_llm_call_tracker()

__all__ = [
    "LLMCallRecord",
    "LLMCallTracker",
    "get_llm_call_tracker",
    "llm_call_tracker",
    "llm_calls_total",
    "llm_call_duration_seconds",
    "llm_tokens_total",
    "llm_fallbacks_total",
    "llm_call_errors_total",
]
