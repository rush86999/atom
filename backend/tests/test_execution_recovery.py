"""
Tests for execution crash-recovery sweep (core/execution_recovery.py).

Verifies that executions orphaned in a RUNNING state by a process crash are
reconciled to FAILED on startup — so they become visible to failure dashboards
and retry logic instead of ghosting forever. Covers both WorkflowExecution and
AgentExecution, plus idempotency (already-terminal rows untouched).

WHY THE AGENT FIXTURES CARRY AN OWNER
=====================================
`reconcile_orphaned_executions` does not select by status alone any more: it
consults `core.execution_ownership.owner_liveness` and only reconciles a row
whose owner is VERIFIED dead. A row inserted by THIS process is stamped with
this process as its owner (`core/models.py` before_insert listener), so the
sweep classifies it ``self`` — a live worker — and leaves it running, which is
correct and is why an unstamped-by-the-test fixture row no longer reconciles.

That is not a reason to weaken the gate. "I cannot see who owns this" is not
evidence that it died, and failing a running turn because of it is data
corruption. So the fixtures below build rows whose owner is a process that has
actually exited, recorded with the OS start time it had while alive: both
verdicts the sweep accepts are then reachable (no such pid, or a confirmed pid
reuse) and the tests still measure real reconciliation rather than a stub.
"""

import json
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.chat_transport import IN_PROGRESS
from core.execution_ownership import HOSTNAME, _os_process_start
from core.models import (
    AgentExecution,
    ChatRequestRecord,
    ExecutionStatus,
    WorkflowExecution,
    WorkflowExecutionStatus,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db(worker_database):
    """Isolated in-memory DB session."""
    SessionLocal = worker_database
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def session_factory(worker_database):
    """The SessionLocal factory bound to the same in-memory engine.

    The recovery sweep opens its own session internally, so tests patch
    execution_recovery.SessionLocal with this factory to point it at the
    test's in-memory DB.
    """
    return worker_database


def _make_workflow_exec(
    db: Session, status: str = WorkflowExecutionStatus.RUNNING.value
) -> WorkflowExecution:
    row = WorkflowExecution(
        execution_id=str(uuid.uuid4()),
        workflow_id="wf_test",
        status=status,
        input_data="{}",
        steps="{}",
        outputs="{}",
        context="{}",
        version=1,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _dead_owner() -> Dict[str, Any]:
    """An owner block the sweep can VERIFY is dead.

    A real process is started, its OS start time is read while it is alive, and
    it is then reaped. From then on the pid is either gone -- the sweep reads
    "no such process" -- or has been reused by an unrelated process, in which
    case the recorded start time no longer matches and the sweep reads
    "pid reuse". Those are the only two verdicts that may fail another worker's
    turn, and neither is fabricated here: the pid really existed and really
    exited. A made-up pid number would be a guess, which is the direction this
    whole gate exists to refuse.
    """
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    try:
        start = _os_process_start(proc.pid)
    finally:
        proc.wait()
    return {
        "pid": proc.pid,
        "token": f"exited-{uuid.uuid4().hex}",
        "host": HOSTNAME,
        "process_started_at": datetime.now(timezone.utc).isoformat(),
        # Read while it was alive. If the pid has since been reused this value
        # cannot match, which is the second VERIFIED-dead route.
        "os_process_start": start or f"proc:unreadable-at-exit-{proc.pid}",
    }


@contextmanager
def _live_owner():
    """An owner block naming a process that is genuinely still running.

    Yield ``(pid, owner)`` and reap the process on exit. A "live" owner that
    had in fact exited would make the hands-off test pass for the wrong reason,
    so the process is real and outlives the assertion.
    """
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        yield proc.pid, {
            "pid": proc.pid,
            "token": f"other-{uuid.uuid4().hex}",
            "host": HOSTNAME,
            "process_started_at": datetime.now(timezone.utc).isoformat(),
            "os_process_start": _os_process_start(proc.pid),
        }
    finally:
        proc.kill()
        proc.wait()


def _make_agent_exec(
    db: Session,
    status: str = ExecutionStatus.RUNNING.value,
    metadata: Optional[Dict[str, Any]] = None,
) -> AgentExecution:
    """An AgentExecution row, owned by a VERIFIED DEAD process by default.

    The default owner is the point of this fixture: an orphaned running row is
    one whose worker exited, so that -- and only that -- is what the sweep is
    allowed to reconcile. Pass ``metadata`` to model any other owner state
    (a live pid, another host, no stamp at all).
    """
    row = AgentExecution(
        id=str(uuid.uuid4()),
        agent_id="atom_main",
        status=status,
        input_summary="test",
        triggered_by="manual",
        metadata_json=(
            metadata if metadata is not None
            else ({"owner": _dead_owner()}
                  if status == ExecutionStatus.RUNNING.value else {})
        ),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _strip_owner(db: Session, execution_id: str, metadata: Dict[str, Any]) -> None:
    """Overwrite a row's metadata with raw SQL, bypassing the insert listener.

    Every AgentExecution insert is stamped with the creating process
    (`core/models.py`), so an owner-less row cannot be produced through the ORM
    at all -- which is exactly right for the product and wrong for this test.
    Rows written before the listener existed are the real population this case
    models, and they are reachable only underneath the mapper.
    """
    db.execute(
        text("UPDATE agent_executions SET metadata_json=:m WHERE id=:i"),
        {"m": json.dumps(metadata), "i": execution_id},
    )
    db.commit()


def _keyed_request(db: Session, request_id: str) -> None:
    """An in-progress keyed chat request, as a live turn would have claimed."""
    db.add(ChatRequestRecord(
        tenant_id="t", user_id="u", session_id="s", request_id=request_id,
        payload_sha256="d", state=IN_PROGRESS,
    ))
    db.commit()


def _request_state(db: Session, request_id: str) -> Optional[str]:
    row = (db.query(ChatRequestRecord)
           .filter(ChatRequestRecord.request_id == request_id).first())
    return row.state if row else None


# ============================================================================
# Recovery sweep tests
# ============================================================================

class TestReconcileOrphanedExecutions:
    def test_recovers_running_workflow_execution(self, db, session_factory, monkeypatch):
        # Patch SessionLocal to use the test session's factory so the sweep
        # (which opens its own session) operates on the same in-memory DB.
        from core import execution_recovery as er

        SessionLocal = session_factory
        monkeypatch.setattr(er, "SessionLocal", SessionLocal)

        orphan = _make_workflow_exec(db, status="RUNNING")

        result = er.reconcile_orphaned_executions()

        assert result["workflow_recovered"] == 1
        db.refresh(orphan)
        assert orphan.status == "FAILED"
        assert orphan.error == "Process restarted while execution was running (crashed)"
        assert orphan.completed_at is not None
        # Recovery marker in context JSON
        ctx = json.loads(orphan.context) if orphan.context else {}
        assert ctx.get("recovery", {}).get("crashed") is True

    def test_recovers_running_agent_execution(self, db, session_factory, monkeypatch):
        from core import execution_recovery as er

        SessionLocal = session_factory
        monkeypatch.setattr(er, "SessionLocal", SessionLocal)

        orphan = _make_agent_exec(db, status="running")

        result = er.reconcile_orphaned_executions()

        assert result["agent_recovered"] == 1
        db.refresh(orphan)
        assert orphan.status == "failed"
        assert orphan.error_message is not None
        assert "crashed" in orphan.error_message.lower()
        assert orphan.completed_at is not None

    def test_agent_recovery_stamps_metadata_marker(self, db, session_factory, monkeypatch):
        """Crash-recovered agent executions must carry a recovery marker in
        metadata_json so operators can distinguish them from genuine logic
        failures — mirroring the workflow path which stamps ``context``.

        Without this, every crash-recovered run is indistinguishable from a
        real failure, polluting failure dashboards and root-cause analysis.
        """
        from core import execution_recovery as er

        SessionLocal = session_factory
        monkeypatch.setattr(er, "SessionLocal", SessionLocal)
        monkeypatch.setattr(er, "RECOVERY_ENABLED", True)

        orphan = _make_agent_exec(db, status="running")

        er.reconcile_orphaned_executions()

        db.refresh(orphan)
        meta = orphan.metadata_json or {}
        assert meta.get("recovery", {}).get("crashed") is True, (
            "Recovered AgentExecution must stamp metadata_json.recovery.crashed=true"
        )

    def test_does_not_touch_completed_executions(self, db, session_factory, monkeypatch):
        """Idempotency: terminal rows are left alone."""
        from core import execution_recovery as er

        SessionLocal = session_factory
        monkeypatch.setattr(er, "SessionLocal", SessionLocal)

        wf_done = _make_workflow_exec(db, status="COMPLETED")
        wf_failed = _make_workflow_exec(db, status="FAILED")
        agent_done = _make_agent_exec(db, status="completed")

        result = er.reconcile_orphaned_executions()

        assert result["workflow_recovered"] == 0
        assert result["agent_recovered"] == 0
        db.refresh(wf_done)
        db.refresh(wf_failed)
        db.refresh(agent_done)
        assert wf_done.status == "COMPLETED"
        assert wf_failed.status == "FAILED"
        assert agent_done.status == "completed"

    def test_idempotent_second_run_is_noop(self, db, session_factory, monkeypatch):
        """Running the sweep twice doesn't re-process already-recovered rows."""
        from core import execution_recovery as er

        SessionLocal = session_factory
        monkeypatch.setattr(er, "SessionLocal", SessionLocal)

        orphan = _make_workflow_exec(db, status="RUNNING")

        first = er.reconcile_orphaned_executions()
        assert first["workflow_recovered"] == 1

        second = er.reconcile_orphaned_executions()
        assert second["workflow_recovered"] == 0

        db.refresh(orphan)
        assert orphan.status == "FAILED"

    def test_respects_disabled_flag(self, db, session_factory, monkeypatch):
        """When ATOM_EXECUTION_RECOVERY_ENABLED=false, sweep is a no-op."""
        from core import execution_recovery as er

        monkeypatch.setattr(er, "RECOVERY_ENABLED", False)
        SessionLocal = session_factory
        monkeypatch.setattr(er, "SessionLocal", SessionLocal)

        orphan = _make_workflow_exec(db, status="RUNNING")
        result = er.reconcile_orphaned_executions()

        assert result["enabled"] is False
        db.refresh(orphan)
        assert orphan.status == "RUNNING"  # untouched

    def test_recovers_both_types_in_one_sweep(self, db, session_factory, monkeypatch):
        from core import execution_recovery as er

        SessionLocal = session_factory
        monkeypatch.setattr(er, "SessionLocal", SessionLocal)
        # Ensure enabled (prior tests may have flipped the flag).
        monkeypatch.setattr(er, "RECOVERY_ENABLED", True)

        # Clear any leftover RUNNING rows from other tests so counts are exact.
        er.reconcile_orphaned_executions()

        w1 = _make_workflow_exec(db, status="RUNNING")
        w2 = _make_workflow_exec(db, status="RUNNING")
        a1 = _make_agent_exec(db, status="running")

        result = er.reconcile_orphaned_executions()
        assert result["workflow_recovered"] == 2
        assert result["agent_recovered"] == 1
        for row in (w1, w2):
            db.refresh(row)
            assert row.status == "FAILED"
        db.refresh(a1)
        assert a1.status == "failed"


# ============================================================================
# OWNERSHIP: the three verdicts, pinned
# ============================================================================
# The sweep selects RUNNING rows by status, but acts on them only when
# `core.execution_ownership.owner_liveness` VERIFIES the owner is dead. The
# three cases below are the whole policy. The middle one is the defect this
# gate was added for: reconciling a row this process cannot account for is how
# a live turn is failed underneath itself, and neither writes -- a status
# change or a released request key -- may happen on an unverified owner.


class TestOwnerLivenessGate:
    # NOTE ON COUNTS. The `worker_database` fixture is session-scoped, so rows
    # created by earlier tests in this file are still in the table. Every
    # assertion below is therefore scoped to the row THIS test created
    # (or to a count that is exact regardless: nothing recovered), because a
    # count that happens to be right today is not a statement about the gate.

    def test_a_verified_dead_owner_is_reconciled_and_stamped(
        self, db, session_factory, monkeypatch
    ):
        """The positive case, kept explicit: a worker that really exited.

        The marker is what makes the recovery distinguishable from a genuine
        logic failure on a dashboard, and it records the verdict that justified
        it, so an operator reading the row can see WHY the sweep touched it.
        """
        from core import execution_recovery as er

        monkeypatch.setattr(er, "SessionLocal", session_factory)
        owner = _dead_owner()
        orphan = _make_agent_exec(db, status="running", metadata={"owner": owner})

        result = er.reconcile_orphaned_executions()

        assert result["agent_recovered"] >= 1
        db.refresh(orphan)
        assert orphan.status == "failed"
        assert orphan.completed_at is not None
        meta = orphan.metadata_json or {}
        assert meta["recovery"]["crashed"] is True
        assert meta["recovery"]["owner_state"] == "dead"
        # The original owner claim survives, so the row still says whose turn
        # this was -- and it is the dead pid, not this process.
        assert meta["owner"]["pid"] == owner["pid"]
        assert orphan.id not in [
            d.get("execution_id") for d in result["agent_untouched_detail"]
        ]
        assert orphan.id not in [
            d.get("execution_id") for d in result["agent_unknown_detail"]
        ]

    def test_a_verified_live_owner_is_left_running(
        self, db, session_factory, monkeypatch
    ):
        """A second process on this database must never fail a running turn."""
        from core import execution_recovery as er

        monkeypatch.setattr(er, "SessionLocal", session_factory)
        with _live_owner() as (pid, owner):
            live = _make_agent_exec(db, status="running", metadata={"owner": owner})

            result = er.reconcile_orphaned_executions()

            db.refresh(live)
            assert live.status == "running", "a live worker's turn was failed"
            assert live.completed_at is None
            assert (live.metadata_json or {}).get("recovery") is None
            mine = [d for d in result["agent_untouched_detail"]
                    if d.get("execution_id") == live.id]
            assert mine, "a live owner was not reported as untouched"
            assert mine[0]["owner_state"] == "live"
            assert mine[0]["pid"] == pid

    @pytest.mark.parametrize("case", ["unstamped", "other_host"])
    def test_an_unknown_owner_is_reported_not_reconciled(
        self, db, session_factory, monkeypatch, case
    ):
        """"I cannot see who owns this" is not "it died".

        Two real populations land here: rows written before the insert listener
        existed, and rows whose owner is on another host (cross-host execution
        is unsupported, and an unfamiliar host is not a death certificate).
        Both are REPORTED -- so whoever can resolve them can see them -- and
        neither is touched.
        """
        from core import execution_recovery as er

        monkeypatch.setattr(er, "SessionLocal", session_factory)
        if case == "unstamped":
            row = _make_agent_exec(db, status="running",
                                   metadata={"request_id": "req-unknown"})
            _strip_owner(db, row.id, {"request_id": "req-unknown"})
        else:
            row = _make_agent_exec(db, status="running", metadata={
                "owner": {"pid": os.getpid(), "token": "x",
                          "host": "some-other-host"}})

        result = er.reconcile_orphaned_executions()

        db.refresh(row)
        assert row.status == "running", (
            f"{case}: an unverified owner was declared crashed")
        assert row.completed_at is None
        assert (row.metadata_json or {}).get("recovery") is None
        mine = [d for d in result["agent_unknown_detail"]
                if d.get("execution_id") == row.id]
        assert mine, f"{case}: an unknown owner was not reported at all"
        assert mine[0]["owner_state"] == "unknown"
        assert mine[0]["reason"], f"{case}: the report must say WHY it is unknown"
        if case == "other_host":
            assert "another host" in mine[0]["reason"]

    def test_an_unknown_owner_does_not_release_its_request_key(
        self, db, session_factory, monkeypatch
    ):
        """The key is the user's retry. Releasing it on an unverified owner
        invites a SECOND execution of a turn that is still running somewhere,
        which is a duplicate side effect, not a recovery."""
        from core import execution_recovery as er

        monkeypatch.setattr(er, "SessionLocal", session_factory)
        request_id = f"req-unknown-{uuid.uuid4().hex[:8]}"
        row = _make_agent_exec(db, status="running",
                               metadata={"request_id": request_id})
        _strip_owner(db, row.id, {"request_id": request_id})
        _keyed_request(db, request_id)

        result = er.reconcile_orphaned_executions()

        assert _request_state(db, request_id) == IN_PROGRESS, (
            "a key was released on the strength of an unverified owner")

    def test_a_verified_dead_owner_does_release_its_request_key(
        self, db, session_factory, monkeypatch
    ):
        """The other side of the same gate: with a dead owner VERIFIED, the
        indefinite "in progress" answer has to end, or a same-id retry is told
        it is already running forever."""
        from core import execution_recovery as er
        from core.chat_transport import CRASHED

        monkeypatch.setattr(er, "SessionLocal", session_factory)
        request_id = f"req-dead-{uuid.uuid4().hex[:8]}"
        _make_agent_exec(db, status="running",
                         metadata={"request_id": request_id,
                                   "owner": _dead_owner()})
        _keyed_request(db, request_id)

        result = er.reconcile_orphaned_executions()

        assert result["chat_requests_released"] >= 1
        assert _request_state(db, request_id) == CRASHED

