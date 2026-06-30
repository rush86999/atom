"""Execution Sandbox Layer — Phase C (Round 45).

KillRun state machine: hard-terminates an in-flight AgentExecution when
a tripwire fires. Mirrors the "kill switch" pattern from cloud security
tooling.

Lifecycle:
  1. Tripwire fires → caller invokes ``trigger_killrun(run_id, reason)``
  2. ``RunSandbox`` row updated with ``killrun_at`` timestamp
  3. ``AgentExecution.status`` set to ``killed_sandbox``
  4. All in-flight tool calls for the run abort via ``CancelledError``
     (the next ``check()`` call for this run_id raises KillRunAborted)
  5. Audit row records tripwire pattern + evidence

Defense in depth: KillRun is the *last* line of defense. Phase A's
whitelist, Phase B's FS scope, Phase C's tripwires, Phase D's egress
proxy, and Phase E's ActionJudge all fire independently. KillRun is what
happens when tripwires fire — which is *after* the agent has already
attempted something unrecoverable.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


class KillRunAborted(Exception):
    """Raised by ``guard()`` when the calling run has been killed.

    Propagates up through the agent tool-dispatch loop and aborts the
    AgentExecution. Caught by the loop's ``except Exception`` handler and
    surfaced as a "run killed" message.
    """


@dataclass
class _KillRunState:
    """Per-run KillRun state."""

    run_id: str
    reason: str
    triggered_at: float
    tripwire_id: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)


class KillRunRegistry:
    """Process-wide registry of killed runs.

    A run_id in this registry means: any subsequent ``guard(run_id)``
    call raises ``KillRunAborted``. The registry is process-local; in
    multi-process deployments each worker tracks its own runs (a run
    only executes on one worker, so this is sufficient).
    """

    _instance: Optional["KillRunRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "KillRunRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._killed = {}  # type: ignore[attr-defined]
                    inst._killed_lock = threading.Lock()  # type: ignore[attr-defined]
                    cls._instance = inst
        return cls._instance

    def trigger(
        self,
        run_id: str,
        reason: str,
        *,
        tripwire_id: Optional[str] = None,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> _KillRunState:
        """Mark a run as killed.

        Idempotent — if the run is already killed, returns the existing
        state without overwriting (the first kill reason wins).
        """
        with self._killed_lock:  # type: ignore[attr-defined]
            if run_id in self._killed:  # type: ignore[attr-defined]
                return self._killed[run_id]  # type: ignore[attr-defined]
            state = _KillRunState(
                run_id=run_id,
                reason=reason,
                triggered_at=time.time(),
                tripwire_id=tripwire_id,
                evidence=evidence or {},
            )
            self._killed[run_id] = state  # type: ignore[attr-defined]
            logger.warning(
                "KillRun triggered: run=%s reason=%s tripwire=%s",
                run_id,
                reason,
                tripwire_id,
            )
            return state

    def is_killed(self, run_id: str) -> bool:
        with self._killed_lock:  # type: ignore[attr-defined]
            return run_id in self._killed  # type: ignore[attr-defined]

    def get_state(self, run_id: str) -> Optional[_KillRunState]:
        with self._killed_lock:  # type: ignore[attr-defined]
            return self._killed.get(run_id)  # type: ignore[attr-defined]

    def release(self, run_id: str) -> None:
        """Remove a run from the killed set (e.g. on rollback)."""
        with self._killed_lock:  # type: ignore[attr-defined]
            self._killed.pop(run_id, None)  # type: ignore[attr-defined]

    def reset(self) -> None:
        """Test helper — clears all killed state."""
        with self._killed_lock:  # type: ignore[attr-defined]
            self._killed.clear()  # type: ignore[attr-defined]


def get_registry() -> KillRunRegistry:
    return KillRunRegistry()


# ===========================================================================
# Public API
# ===========================================================================


def trigger_killrun(
    run_id: str,
    reason: str,
    *,
    tripwire_id: Optional[str] = None,
    evidence: Optional[Dict[str, Any]] = None,
    db: Any = None,
    execution_id: Optional[str] = None,
) -> None:
    """Trigger KillRun for a run.

    Marks the run as killed, attempts to update the AgentExecution row
    to ``killed_sandbox`` status (best-effort — DB may be unreachable),
    and records evidence.

    Never raises — KillRun is a defensive mechanism and must not break
    agent execution. All errors are logged at warning level.
    """
    try:
        registry = get_registry()
        registry.trigger(
            run_id,
            reason,
            tripwire_id=tripwire_id,
            evidence=evidence,
        )

        # Best-effort DB update
        try:
            from core.database import SessionLocal
            from core.models import AgentExecution, ExecutionStatus

            owns_session = db is None
            session = db or SessionLocal()
            try:
                exec_id = execution_id or run_id
                exec_row = (
                    session.query(AgentExecution)
                    .filter(AgentExecution.id == exec_id)
                    .first()
                )
                if exec_row is not None:
                    # Use raw status string to avoid enum coupling issues.
                    exec_row.status = "killed_sandbox"
                    session.commit()
            finally:
                if owns_session:
                    session.close()
        except Exception as e:  # noqa: BLE001
            logger.warning("KillRun DB update failed for run %s: %s", run_id, e)
    except Exception as e:  # noqa: BLE001
        logger.warning("KillRun trigger failed (run=%s): %s", run_id, e)


def guard(run_id: str) -> None:
    """Raise KillRunAborted if the run has been killed.

    Called by the tool-dispatch loop before each tool call. Cheap (single
    dict lookup under lock). When the run is killed, this raises
    KillRunAborted which propagates up and aborts the AgentExecution.
    """
    if run_id and get_registry().is_killed(run_id):
        state = get_registry().get_state(run_id)
        reason = state.reason if state else "unknown"
        raise KillRunAborted(f"Run {run_id} killed by sandbox: {reason}")


def is_killed(run_id: str) -> bool:
    """Predicate form of guard()."""
    return bool(run_id) and get_registry().is_killed(run_id)
