"""Execution Sandbox Layer — Phase C (Round 45).

Resource caps: per-run counters for tool-call count, wall-clock seconds,
bytes written, and LLM cost. Counters live in-memory (process-local) with
best-effort DB persistence on flush.

Design contract:
  * Pure functions where possible; counters are the only stateful thing.
  * Counter increments are atomic under the GIL (Python int += is atomic).
  * Cap exceeded → SandboxDecision RESTRICTED (recoverable: caller may
    start a new run).
  * Never raises — a broken counter fails open (returns ALLOWED).
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from core import sandbox_config
from core.sandbox_policy import (
    ALLOWED,
    RESTRICTED,
    SandboxDecision,
    SandboxPolicy,
    VT_CAP_EXCEEDED,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# Per-call resource estimation (bytes written / LLM cost)
#
# The caps layer evaluates tool calls BEFORE they execute, so byte/cost
# accounting is estimated from the call's own arguments at the choke point
# (mirrors the pre-action philosophy of the match-confidence layer). This is
# the ONLY production caller of the byte/cost counters — record_write /
# record_cost remain available for post-action actuals.
# ===========================================================================

# Tools known to write to the filesystem. Mirrors
# sandbox_fs._DEFAULT_WRITE_TOOLS plus the productivity/office writers; a
# tool NOT in this set never accrues bytes_written.
_WRITE_TOOLS: Tuple[str, ...] = (
    "write_code_file",
    "browser_download",
    "device_save_photo",
    "device_take_screenshot",
    "memory_remember",
    "canvas_export",
    "atom_cli_skill",
    "productivity_write",
    "office_save",
)

# Arg keys that carry the payload being written / sent to an LLM.
_WRITE_CONTENT_KEYS: Tuple[str, ...] = (
    "content",
    "source",
    "code",
    "html",
    "text",
    "body",
    "data",
    "file_content",
    "markdown",
    "csv",
    "json",
)

# Tool-name fragments indicating an LLM call (cost accrues). Matches
# documents.ask_image, llm_*, generate_*, summarize* etc.
_LLM_TOOL_FRAGMENTS: Tuple[str, ...] = (
    "llm",
    "generate",
    "summar",
    "ask_",
    "ask_image",
    "classify",
    "embed",
    "translate",
)

# Cost keys for LLM-ish tools; anything else in args is not prompt content.
_COST_PROMPT_KEYS: Tuple[str, ...] = (
    "prompt",
    "question",
    "query",
    "request",
    "text",
    "content",
    "messages",
    "instruction",
    "summarize",
)

# Flat conservative estimate: $10 per 1M tokens. Actual billing attribution
# happens elsewhere; this only bounds a runaway run.
_ESTIMATED_USD_PER_TOKEN = 0.00001


def _payload_char_count(args: Dict[str, Any], keys: Tuple[str, ...]) -> int:
    """Sum the character size of the payload-bearing args."""
    total = 0
    for key, value in (args or {}).items():
        if key not in keys:
            continue
        if isinstance(value, (str, bytes)):
            total += len(value)
        elif isinstance(value, (dict, list)):
            total += len(str(value))
    return total


def estimate_write_bytes(tool_name: str, args: Dict[str, Any]) -> int:
    """Best-effort bytes this call will write, from the args alone.

    Only write-capable tools accrue; the payload is the content-bearing
    args. Returns 0 for read-only tools and tools without a payload.
    """
    if tool_name not in _WRITE_TOOLS:
        return 0
    return _payload_char_count(args, _WRITE_CONTENT_KEYS)


def estimate_cost_usd(tool_name: str, args: Dict[str, Any]) -> float:
    """Best-effort LLM cost this call will incur, from the args alone.

    Only LLM-invoking tools (by name fragment) accrue; the prompt is the
    content-bearing args. chars//4 approximates tokens (the same heuristic
    as cognitive_tier_service). Returns 0.0 for non-LLM tools.
    """
    name = str(tool_name or "").lower()
    if not any(frag in name for frag in _LLM_TOOL_FRAGMENTS):
        return 0.0
    chars = _payload_char_count(args, _COST_PROMPT_KEYS)
    tokens = max(1, chars // 4)
    return round(tokens * _ESTIMATED_USD_PER_TOKEN, 6)


def estimate_tool_usage(tool_name: str, args: Dict[str, Any]) -> Tuple[int, float]:
    """Pre-action estimate of (bytes_written, cost_usd) for this call.

    Never raises — a broken estimator fails open to (0, 0.0).
    """
    try:
        return estimate_write_bytes(tool_name, args), estimate_cost_usd(tool_name, args)
    except Exception as e:  # noqa: BLE001
        logger.debug("sandbox usage estimate failed for %s: %s", tool_name, e)
        return 0, 0.0


# ===========================================================================
# Per-run counter state
# ===========================================================================
@dataclass
class _RunCounters:
    """Mutable per-run counters. NOT frozen — these change every call."""

    run_id: str
    tool_calls: int = 0
    bytes_written: int = 0
    exec_seconds_started_at: float = field(default_factory=time.time)
    cost_usd: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def incr_tool_calls(self) -> int:
        with self.lock:
            self.tool_calls += 1
            return self.tool_calls

    def add_bytes_written(self, n: int) -> int:
        with self.lock:
            self.bytes_written += max(0, int(n))
            return self.bytes_written

    def add_cost(self, usd: float) -> float:
        with self.lock:
            self.cost_usd += max(0.0, float(usd))
            return self.cost_usd

    def elapsed_seconds(self) -> float:
        return time.time() - self.exec_seconds_started_at


# ===========================================================================
# Counter registry — keyed on run_id
# ===========================================================================
class CounterRegistry:
    """Process-wide registry of per-run counters.

    Counters are created lazily on first check() for a given run_id and
    cleaned up via ``release(run_id)`` at run end. Stale counters (>
    24h old) are GC'd by a background task in production; in tests they
    persist for the lifetime of the process which is fine.
    """

    _instance: Optional["CounterRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "CounterRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._counters = {}  # type: ignore[attr-defined]
                    inst._counters_lock = threading.Lock()  # type: ignore[attr-defined]
                    cls._instance = inst
        return cls._instance

    def get(self, run_id: str) -> _RunCounters:
        with self._counters_lock:  # type: ignore[attr-defined]
            if run_id not in self._counters:  # type: ignore[attr-defined]
                self._counters[run_id] = _RunCounters(run_id=run_id)  # type: ignore[attr-defined]
            return self._counters[run_id]  # type: ignore[attr-defined]

    def release(self, run_id: str) -> None:
        with self._counters_lock:  # type: ignore[attr-defined]
            self._counters.pop(run_id, None)  # type: ignore[attr-defined]

    def reset(self) -> None:
        """Test helper — clears all counters."""
        with self._counters_lock:  # type: ignore[attr-defined]
            self._counters.clear()  # type: ignore[attr-defined]


def get_registry() -> CounterRegistry:
    """Return the singleton counter registry."""
    return CounterRegistry()


# ===========================================================================
# Cap evaluation
# ===========================================================================


def check_caps(
    policy: SandboxPolicy,
    *,
    tool_name: str,
    args: Dict[str, Any],
    args_hash: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> SandboxDecision:
    """Evaluate the run's resource caps against the policy.

    Increments the tool-call counter (this call counts) and accrues the
    call's estimated bytes/cost (``estimate_tool_usage``). Returns
    RESTRICTED if any cap is exceeded — including when the current call
    itself would push a cumulative budget over its limit. Never raises.

    Order of checks (cheap-first):
      1. tool_calls count
      2. elapsed wall-clock seconds
      3. bytes_written (cumulative + this call's estimate)
      4. cost_usd (cumulative + this call's estimate)
    """
    try:
        registry = get_registry()
        counters = registry.get(policy.run_id)
        est_bytes, est_cost = estimate_tool_usage(tool_name, args)

        # 1. Tool-call count — check BEFORE incrementing so a call that
        # would put us over the cap is denied.
        if policy.max_tool_calls > 0 and counters.tool_calls >= policy.max_tool_calls:
            return SandboxDecision(
                decision=RESTRICTED,
                phase="C",
                violation_type=VT_CAP_EXCEEDED,
                violation_detail=(
                    f"max_tool_calls cap exceeded: {counters.tool_calls} >= "
                    f"{policy.max_tool_calls}"
                ),
                tool_name=tool_name,
                args_hash=args_hash,
                enforced=sandbox_config.is_sandbox_force_enforce_enabled(),
                metadata_json={
                    "cap": "max_tool_calls",
                    "current": counters.tool_calls,
                    "limit": policy.max_tool_calls,
                },
            )

        # 2. Wall-clock seconds
        if policy.max_exec_seconds > 0:
            elapsed = counters.elapsed_seconds()
            if elapsed >= policy.max_exec_seconds:
                return SandboxDecision(
                    decision=RESTRICTED,
                    phase="C",
                    violation_type=VT_CAP_EXCEEDED,
                    violation_detail=(
                        f"max_exec_seconds cap exceeded: {elapsed:.1f}s >= "
                        f"{policy.max_exec_seconds}s"
                    ),
                    tool_name=tool_name,
                    args_hash=args_hash,
                    enforced=sandbox_config.is_sandbox_force_enforce_enabled(),
                    metadata_json={
                        "cap": "max_exec_seconds",
                        "current": elapsed,
                        "limit": policy.max_exec_seconds,
                    },
                )

        # 3. Bytes written — cumulative + this call's estimate
        if policy.max_bytes_written > 0 and counters.bytes_written + est_bytes >= policy.max_bytes_written:
            return SandboxDecision(
                decision=RESTRICTED,
                phase="C",
                violation_type=VT_CAP_EXCEEDED,
                violation_detail=(
                    f"max_bytes_written cap exceeded: {counters.bytes_written} + "
                    f"{est_bytes} (this call) >= {policy.max_bytes_written}"
                ),
                tool_name=tool_name,
                args_hash=args_hash,
                enforced=sandbox_config.is_sandbox_force_enforce_enabled(),
                metadata_json={
                    "cap": "max_bytes_written",
                    "current": counters.bytes_written,
                    "pending": est_bytes,
                    "limit": policy.max_bytes_written,
                },
            )

        # 4. Cost USD — cumulative + this call's estimate
        if policy.max_cost_usd > 0 and counters.cost_usd + est_cost >= policy.max_cost_usd:
            return SandboxDecision(
                decision=RESTRICTED,
                phase="C",
                violation_type=VT_CAP_EXCEEDED,
                violation_detail=(
                    f"max_cost_usd cap exceeded: ${counters.cost_usd:.4f} + "
                    f"${est_cost:.4f} (this call) >= ${policy.max_cost_usd:.4f}"
                ),
                tool_name=tool_name,
                args_hash=args_hash,
                enforced=sandbox_config.is_sandbox_force_enforce_enabled(),
                metadata_json={
                    "cap": "max_cost_usd",
                    "current": counters.cost_usd,
                    "pending": est_cost,
                    "limit": policy.max_cost_usd,
                },
            )

        # All caps OK — count this call. The final check + increment are
        # atomic under the counter lock so concurrent tool calls cannot both
        # pass the same cap slot (the earlier read above is a fast-path deny).
        if policy.max_tool_calls > 0:
            with counters.lock:
                if counters.tool_calls >= policy.max_tool_calls:
                    return SandboxDecision(
                        decision=RESTRICTED,
                        phase="C",
                        violation_type=VT_CAP_EXCEEDED,
                        violation_detail=(
                            f"max_tool_calls cap exceeded: {counters.tool_calls} >= "
                            f"{policy.max_tool_calls}"
                        ),
                        tool_name=tool_name,
                        args_hash=args_hash,
                        enforced=sandbox_config.is_sandbox_force_enforce_enabled(),
                        metadata_json={
                            "cap": "max_tool_calls",
                            "current": counters.tool_calls,
                            "limit": policy.max_tool_calls,
                        },
                    )
                counters.tool_calls += 1
                tool_calls_after_incr = counters.tool_calls
                if est_bytes:
                    counters.bytes_written += est_bytes
                if est_cost:
                    counters.cost_usd += est_cost
        else:
            tool_calls_after_incr = counters.incr_tool_calls()
            if est_bytes:
                counters.add_bytes_written(est_bytes)
            if est_cost:
                counters.add_cost(est_cost)

        return SandboxDecision(
            decision=ALLOWED,
            phase="C",
            tool_name=tool_name,
            args_hash=args_hash,
            metadata_json={
                "tool_calls_after_incr": tool_calls_after_incr,
                "elapsed_seconds": counters.elapsed_seconds(),
                "bytes_written": counters.bytes_written,
                "cost_usd": counters.cost_usd,
            },
        )
    except Exception as e:  # noqa: BLE001 — fail open
        logger.debug("cap check failed open for %s: %s", tool_name, e)
        return SandboxDecision(
            decision=ALLOWED,
            phase="C",
            tool_name=tool_name,
            args_hash=args_hash,
            metadata_json={"error": str(e)},
        )


def record_write(policy: SandboxPolicy, byte_count: int) -> None:
    """Record that a write of ``byte_count`` bytes happened under this run."""
    try:
        get_registry().get(policy.run_id).add_bytes_written(byte_count)
    except Exception as e:  # noqa: BLE001
        logger.debug("record_write failed: %s", e)


def record_cost(policy: SandboxPolicy, usd: float) -> None:
    """Record that an LLM call costing ``usd`` happened under this run."""
    try:
        get_registry().get(policy.run_id).add_cost(usd)
    except Exception as e:  # noqa: BLE001
        logger.debug("record_cost failed: %s", e)


def release_run(run_id: str) -> None:
    """Release counters for a run that has ended."""
    try:
        get_registry().release(run_id)
    except Exception as e:  # noqa: BLE001
        logger.debug("release_run failed: %s", e)
