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

    Increments the tool-call counter (this call counts). Returns
    RESTRICTED if any cap is exceeded. Never raises.

    Order of checks (cheap-first):
      1. tool_calls count
      2. elapsed wall-clock seconds
      3. bytes_written (cumulative)
      4. cost_usd (cumulative)
    """
    try:
        registry = get_registry()
        counters = registry.get(policy.run_id)

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

        # 3. Bytes written — cumulative
        if policy.max_bytes_written > 0 and counters.bytes_written >= policy.max_bytes_written:
            return SandboxDecision(
                decision=RESTRICTED,
                phase="C",
                violation_type=VT_CAP_EXCEEDED,
                violation_detail=(
                    f"max_bytes_written cap exceeded: {counters.bytes_written} >= "
                    f"{policy.max_bytes_written}"
                ),
                tool_name=tool_name,
                args_hash=args_hash,
                enforced=sandbox_config.is_sandbox_force_enforce_enabled(),
                metadata_json={
                    "cap": "max_bytes_written",
                    "current": counters.bytes_written,
                    "limit": policy.max_bytes_written,
                },
            )

        # 4. Cost USD — cumulative
        if policy.max_cost_usd > 0 and counters.cost_usd >= policy.max_cost_usd:
            return SandboxDecision(
                decision=RESTRICTED,
                phase="C",
                violation_type=VT_CAP_EXCEEDED,
                violation_detail=(
                    f"max_cost_usd cap exceeded: ${counters.cost_usd:.4f} >= "
                    f"${policy.max_cost_usd:.4f}"
                ),
                tool_name=tool_name,
                args_hash=args_hash,
                enforced=sandbox_config.is_sandbox_force_enforce_enabled(),
                metadata_json={
                    "cap": "max_cost_usd",
                    "current": counters.cost_usd,
                    "limit": policy.max_cost_usd,
                },
            )

        # All caps OK — count this call.
        counters.incr_tool_calls()

        return SandboxDecision(
            decision=ALLOWED,
            phase="C",
            tool_name=tool_name,
            args_hash=args_hash,
            metadata_json={
                "tool_calls_after_incr": counters.tool_calls,
                "elapsed_seconds": counters.elapsed_seconds(),
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
