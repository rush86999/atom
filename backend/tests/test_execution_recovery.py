"""
Tests for execution crash-recovery sweep (core/execution_recovery.py).

Verifies that executions orphaned in a RUNNING state by a process crash are
reconciled to FAILED on startup — so they become visible to failure dashboards
and retry logic instead of ghosting forever. Covers both WorkflowExecution and
AgentExecution, plus idempotency (already-terminal rows untouched).
"""

import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from core.models import (
    AgentExecution,
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


def _make_agent_exec(
    db: Session, status: str = ExecutionStatus.RUNNING.value
) -> AgentExecution:
    row = AgentExecution(
        id=str(uuid.uuid4()),
        agent_id="atom_main",
        status=status,
        input_summary="test",
        triggered_by="manual",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


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
