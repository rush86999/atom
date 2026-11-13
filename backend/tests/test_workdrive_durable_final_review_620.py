# -*- coding: utf-8 -*-
"""Focused synthetic regressions for the durable-delivery review findings.

Each test reproduces ONE concrete failure mode from the 2026-11-12 review of
the issue-620 durable WorkDrive delivery, at the persistence boundary where it
happens — never through a live provider, workbook, or database:

* finding 2 — confirmation bookkeeping must never revert a concurrent claim
  (the unsynchronized read-modify-write of the job's ``metadata_json``);
* finding 3 — an ``unknown``-owner RUNNING zombie must be bounded (stale-run
  takeover / terminal finish) so its schedule gate can never wedge forever;
* finding 4 — a schedule gate whose owning job was terminalized OUTSIDE
  ``_finish_job`` (the generic boot sweep) must be released, not fail the
  request forever;
* finding 5 — ``failed`` is terminal for claims too, except for the explicit
  restart-recovery repair of an owner that is provably gone;
* finding 7 — a late result must not clobber a job whose terminal message was
  already written by a racing attempt.

Everything is a file-backed scratch database with a FRESH session per
``get_db_session()`` call (``NullPool``), which is the cross-process situation
the races need.  ``TESTING=1`` is set before application imports.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from core import workdrive_background_delivery as background
from core.pending_file_task import build_pending_task

RID = "u-background-620-review"
FILE_NAME = "Synthetic Price List 2026.xlsx"
SESSION = "session-bg-620-review"
WORKSPACE = "ws-620"
ORIGIN_EXECUTION = "exec-interactive-620-review"
ASK = "find the prices of U-22 and 622 in Synthetic Price List 2026.xlsx"
TARGETS = ["U-22", "622"]
CONFIRMATION = "yes, that is the workbook"


@contextmanager
def _db_session_factory(session_factory):
    """One context = one brand-new Session (a distinct database session)."""
    db = session_factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@pytest.fixture()
def scratch_db(tmp_path, monkeypatch):
    """File-backed scratch DB; every ``get_db_session()`` is a new session."""
    from core import database as database_module
    from core.models_registration import Base

    db_path = tmp_path / "workdrive-review-620.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def get_db_session():
        return _db_session_factory(session_factory)

    monkeypatch.setattr(database_module, "get_db_session", get_db_session)
    yield session_factory
    engine.dispose()


@pytest.fixture()
def active_grant():
    with patch(
        "core.integrations.token_store.connected_source_grant_state",
        return_value="active",
    ):
        yield


def _identity() -> dict:
    return {
        "service": "zoho_workdrive",
        "file_id": RID,
        "resource_id": RID,
        "file_name": FILE_NAME,
        "identity_verified": True,
    }


def _schedule(**overrides):
    kwargs = {
        "session_id": SESSION,
        "user_id": "u1",
        "workspace_id": WORKSPACE,
        "execution_id": ORIGIN_EXECUTION,
        "original_message": ASK,
        "query": ASK,
        "mention": FILE_NAME.lower(),
        "resource_id": RID,
        "file_name": FILE_NAME,
        "requested_targets": TARGETS,
        "identity": _identity(),
        "pending_task": build_pending_task(ASK, FILE_NAME.lower()),
        "history": [],
        "canvas": None,
        "tenant_id": "default",
        "spawn": False,
    }
    kwargs.update(overrides)
    return background.schedule_strict_workdrive_read(**kwargs)


def _job_row(job_id: str):
    from core.database import get_db_session
    from core.models import AgentExecution

    with get_db_session() as db:
        return db.query(AgentExecution).filter(
            AgentExecution.id == job_id).first()


def _job_metadata(job_id: str) -> dict:
    return dict(json.loads(json.dumps(_job_row(job_id).metadata_json))[
        background.JOB_METADATA_KEY])


def _assistant_rows(session_id: str = SESSION):
    from core.database import get_db_session
    from core.models import ChatMessage

    with get_db_session() as db:
        return list(db.query(ChatMessage).filter(
            ChatMessage.conversation_id == session_id,
            ChatMessage.role == "assistant",
        ).all())


def _gate_id(session_id: str = SESSION, **schedule_overrides) -> str:
    scope = background.request_scope_from_task(
        session_id=session_id,
        user_id="u1",
        workspace_id=WORKSPACE,
        resource_id=RID,
        file_name=FILE_NAME,
        original_message=ASK,
        requested_targets=TARGETS,
    )
    return background._schedule_gate_event_id(
        session_id, background.canonical_request_digest(scope))


def _gate_exists(gate_id: str) -> bool:
    from core.database import get_db_session
    from core.models import DeliveryEvent

    with get_db_session() as db:
        return db.query(DeliveryEvent).filter(
            DeliveryEvent.event_id == gate_id).first() is not None


def _set_job_state(
    job_id: str,
    *,
    job_status: str = None,
    attempts: int = None,
    last_attempt_at: str = None,
    row_status: str = None,
    drop_owner: bool = False,
) -> None:
    """Mutate the durable job exactly as another process/DB writer would."""
    from core.database import get_db_session
    from core.models import AgentExecution

    with get_db_session() as db:
        row = db.query(AgentExecution).filter(
            AgentExecution.id == job_id).first()
        meta = dict(row.metadata_json or {})
        job = dict(meta[background.JOB_METADATA_KEY])
        if job_status is not None:
            job["status"] = job_status
        if attempts is not None:
            job["attempts"] = attempts
        if last_attempt_at is not None:
            job["last_attempt_at"] = last_attempt_at
        meta[background.JOB_METADATA_KEY] = job
        if drop_owner:
            meta.pop("owner", None)
        row.metadata_json = meta
        if row_status is not None:
            row.status = row_status
        db.commit()


def _iso_ago(seconds: float) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(seconds=seconds)
    ).isoformat()


def _valid_background_row(job_id: str, sha: str) -> dict:
    scope = background.request_scope_from_task(
        session_id=SESSION,
        user_id="u1",
        workspace_id=WORKSPACE,
        resource_id=RID,
        file_name=FILE_NAME,
        original_message=ASK,
        requested_targets=TARGETS,
    )
    return {
        "status": "delivered",
        "rendered": f"answer for {job_id}",
        "identity": {"content_sha256": sha},
        "background_delivery": {
            "schema": background.SCHEMA,
            "job_id": job_id,
            "execution_id": job_id,
            "original_digest": background.canonical_request_digest(scope),
            "request_scope": scope,
            "content_sha256": sha,
            "proof_execution_id": job_id,
            "status": "delivered",
            "user_id": "u1",
            "workspace_id": WORKSPACE,
        },
        "direct_source_proof": {
            "status": "verified",
            "execution_id": job_id,
            "downloaded_sha256": sha,
            "receipt": {"sha256": sha, "execution_id": job_id},
            "materialized": False,
        },
    }


# ---------------------------------------------------------------------------
# Finding 2 — confirmation bookkeeping vs. the runner's claim
# ---------------------------------------------------------------------------

def test_confirmation_cannot_revert_a_concurrent_claim(
    scratch_db, active_grant,
):
    """The confirmation's read happens BEFORE the claim commits; its write
    lands AFTER.  The claim must survive (attempts, status, owner)."""
    scheduled = _schedule()
    job_id = scheduled["job_id"]

    from core.execution_ownership import current_owner
    from core.models import AgentExecution

    session_factory = scratch_db
    claimer = session_factory()
    try:
        row = claimer.query(AgentExecution).filter(
            AgentExecution.id == job_id).first()
        meta = dict(row.metadata_json or {})
        job = dict(meta[background.JOB_METADATA_KEY])
        # The runner's claim, VERIFIED but NOT YET COMMITTED.  This is the
        # window the confirmation used to read through.
        job["status"] = background._JOB_STATUS_RUNNING
        job["attempts"] = 1
        job["last_attempt_at"] = background._now_iso()
        meta[background.JOB_METADATA_KEY] = job
        meta["owner"] = current_owner()
        row.metadata_json = meta
        row.status = "running"
        claimer.flush()

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                background._record_confirmation_on_job,
                job_id,
                message=CONFIRMATION,
                mention=FILE_NAME.lower(),
                attach_mode="job_id",
            )
            # Give the confirmation time to read the pre-claim snapshot; it
            # then blocks waiting for this transaction's write lock.
            deadline = time.time() + 5.0
            while time.time() < deadline and not future.running():
                time.sleep(0.01)
            time.sleep(0.3)
            claimer.commit()
            future.result(timeout=30)
    finally:
        claimer.close()

    row = _job_row(job_id)
    job = _job_metadata(job_id)
    # The runner's claim is intact: no reverted attempt, no lost owner.
    assert job["attempts"] == 1
    assert job["status"] == background._JOB_STATUS_RUNNING
    assert row.status == "running"
    assert (row.metadata_json or {}).get("owner", {}).get("token")
    # ...and the confirmation was still recorded on top of it.
    assert job["confirmation_count"] == 1
    assert job["confirmed_mention"] == FILE_NAME.lower()
    assert job["confirmations"][-1]["message"] == CONFIRMATION


def test_orphaned_run_lease_is_self_repaired(scratch_db, active_grant):
    """The wedge's shape: a lease exists for attempt 1 while the counter says
    0 (a reverted job record).  A claim must self-repair, not fail forever."""
    from core.database import get_db_session
    from core.job_delivery import job_event_id
    from core.models import DeliveryEvent

    scheduled = _schedule()
    job_id = scheduled["job_id"]
    with get_db_session() as db:
        db.add(DeliveryEvent(
            event_id=job_event_id(
                job_id, "run:1", background._CLAIM_EVENT_TYPE),
            conversation_id=SESSION,
            job_id=job_id,
            result_revision="run:1",
        ))
        db.commit()

    claimed = background._claim_job_for_run(job_id)
    assert isinstance(claimed, dict)
    assert claimed["attempts"] == 1
    assert _job_metadata(job_id)["status"] == background._JOB_STATUS_RUNNING


# ---------------------------------------------------------------------------
# Finding 3 — unknown-owner zombie bounds
# ---------------------------------------------------------------------------

def test_recovery_bounds_a_stale_unknown_owner_zombie(
    scratch_db, active_grant, monkeypatch,
):
    scheduled = _schedule()
    job_id = scheduled["job_id"]
    _set_job_state(
        job_id,
        job_status=background._JOB_STATUS_RUNNING,
        attempts=1,
        last_attempt_at=_iso_ago(3600),
        row_status="running",
    )
    monkeypatch.setattr(background, "_STALE_RUN_SECONDS", 60.0)
    runs = []

    async def rerun(job):
        runs.append(job["job_id"])
        return {"ok": False, "error": "synthetic stop after the takeover"}

    with patch(
        "core.execution_ownership.owner_liveness",
        return_value=("unknown", {"reason": "owner is on another host"}),
    ):
        stats = asyncio.run(
            background.recover_pending_strict_workdrive_reads(
                read_runner=rerun))

    # The zombie could not be left holding the gate forever.
    assert runs == [job_id]
    assert stats["skipped_live"] == 0
    row = _job_row(job_id)
    assert row.status == "failed"
    assert _job_metadata(job_id)["status"] == background._JOB_STATUS_FAILED
    assert not _gate_exists(_gate_id())
    assert len(_assistant_rows()) == 1


def test_fresh_unknown_owner_run_is_still_not_taken_over(
    scratch_db, active_grant, monkeypatch,
):
    """The stale bound must not turn "cannot tell" into "take it now"."""
    scheduled = _schedule()
    job_id = scheduled["job_id"]
    _set_job_state(
        job_id,
        job_status=background._JOB_STATUS_RUNNING,
        attempts=1,
        last_attempt_at=_iso_ago(5),
        row_status="running",
    )
    monkeypatch.setattr(background, "_STALE_RUN_SECONDS", 3600.0)
    runs = []

    async def must_not_read(job):
        runs.append(job["job_id"])
        raise AssertionError("a fresh attempt must not be taken over")

    with patch(
        "core.execution_ownership.owner_liveness",
        return_value=("unknown", {"reason": "owner is on another host"}),
    ):
        stats = asyncio.run(
            background.recover_pending_strict_workdrive_reads(
                read_runner=must_not_read))

    assert runs == []
    assert _job_row(job_id).status == "running"
    assert _gate_exists(_gate_id())
    assert stats["details"][-1]["failed"] == "job_claim_failed"


# ---------------------------------------------------------------------------
# Finding 4 — gates orphaned by rows terminalized outside _finish_job
# ---------------------------------------------------------------------------

def test_reask_releases_a_gate_held_by_an_externally_failed_job(
    scratch_db, active_grant,
):
    first = _schedule()
    job_id = first["job_id"]
    gate = _gate_id()
    assert _gate_exists(gate)

    # The generic boot sweep marks the row failed and never touches the gate
    # or the workdrive metadata (exactly ``execution_recovery``'s behavior).
    _set_job_state(
        job_id,
        job_status=background._JOB_STATUS_FAILED,
        attempts=1,
        last_attempt_at=_iso_ago(30),
        row_status="failed",
    )

    second = _schedule()
    assert second["ok"] is True
    assert second["reused"] is False
    assert second["job_id"] != job_id
    # The stale gate now belongs to the NEW job, not the dead one.
    from core.database import get_db_session
    from core.models import DeliveryEvent

    with get_db_session() as db:
        event = db.query(DeliveryEvent).filter(
            DeliveryEvent.event_id == gate).first()
        assert event is not None
        assert event.job_id == second["job_id"]


def test_recovery_sweeps_gates_of_terminal_or_missing_jobs(
    scratch_db, active_grant,
):
    from core.database import get_db_session
    from core.models import AgentExecution, DeliveryEvent

    orphan_gate = background._schedule_gate_event_id(SESSION, "digest-orphan")
    live_gate = background._schedule_gate_event_id(SESSION, "digest-live")
    with get_db_session() as db:
        # A gate whose owner row no longer exists can never be released by
        # that row; only the sweep can reclaim it.
        db.add(DeliveryEvent(
            event_id=orphan_gate,
            conversation_id=SESSION,
            job_id="job-row-is-gone",
            result_revision=background._SCHEDULE_GATE_REVISION,
        ))
        # A live owner's gate must survive the sweep untouched.
        db.add(AgentExecution(
            id="live-job-620-review",
            status="running",
            triggered_by="manual",
            metadata_json={},
        ))
        db.add(DeliveryEvent(
            event_id=live_gate,
            conversation_id=SESSION,
            job_id="live-job-620-review",
            result_revision=background._SCHEDULE_GATE_REVISION,
        ))
        db.commit()

    async def must_not_read(_job):
        raise AssertionError("no workdrive candidate exists here")

    stats = asyncio.run(
        background.recover_pending_strict_workdrive_reads(
            read_runner=must_not_read))

    assert stats["candidates"] == 0
    assert stats["gates_released"] == 1
    assert not _gate_exists(orphan_gate)
    assert _gate_exists(live_gate)


# ---------------------------------------------------------------------------
# Finding 5 — terminality is consistent for claims too
# ---------------------------------------------------------------------------

def test_claim_refuses_a_failed_job(scratch_db, active_grant):
    scheduled = _schedule()
    job_id = scheduled["job_id"]
    background._finish_job(
        job_id, background._JOB_STATUS_FAILED, error="failed externally")

    assert background._claim_job_for_run(job_id) is None
    assert background._job_row_is_terminal(_job_row(job_id))

    # ``allow_failed`` is not a licence on its own: a FAILED row whose run
    # attempt has a live (here: this process's own) owner still refuses.
    _set_job_state(
        job_id,
        job_status=background._JOB_STATUS_FAILED,
        attempts=1,
        last_attempt_at=_iso_ago(5),
        row_status="failed",
    )
    assert background._claim_job_for_run(job_id, allow_failed=True) is None
    assert _job_metadata(job_id)["attempts"] == 1


def test_recovery_still_repairs_a_verified_dead_failed_row(
    scratch_db, active_grant,
):
    """The sweep's externally-failed row stays repairable by recovery."""
    scheduled = _schedule()
    job_id = scheduled["job_id"]
    _set_job_state(
        job_id,
        job_status=background._JOB_STATUS_RUNNING,
        attempts=1,
        last_attempt_at=_iso_ago(30),
        row_status="failed",
    )
    runs = []

    async def rerun(job):
        runs.append(job["job_id"])
        return {"ok": False, "error": "synthetic stop after the repair claim"}

    with patch(
        "core.execution_ownership.owner_liveness",
        return_value=("dead", {"reason": "no such process"}),
    ):
        stats = asyncio.run(
            background.recover_pending_strict_workdrive_reads(
                read_runner=rerun))

    assert runs == [job_id]
    assert stats["failed"] == 1
    assert len(_assistant_rows()) == 1
    assert _job_row(job_id).status == "failed"


# ---------------------------------------------------------------------------
# Finding 7 — a late result must not clobber a terminal delivery
# ---------------------------------------------------------------------------

def test_store_job_result_does_not_clobber_a_terminal_failure(
    scratch_db, active_grant,
):
    scheduled = _schedule()
    job_id = scheduled["job_id"]
    _row, job = background._get_job(job_id)
    background._deliver_failure(job, "the read failed for real")

    background._store_job_result(
        job_id, _valid_background_row(job_id, "d" * 64))

    meta = _job_metadata(job_id)
    assert meta.get("result") is None
    assert meta.get("status") != background._JOB_STATUS_COMPLETED
    assert _job_row(job_id).status != "completed"
    # And the job can never be re-claimed into a competing success.
    assert background._claim_job_for_run(
        job_id, allow_failed=True, allow_live_owner=True) is None
    rows = _assistant_rows()
    assert len(rows) == 1
    assert json.loads(rows[0].metadata_json)[
        "workdrive_background_read"]["status"] == "failed"


def test_post_delivery_finish_keeps_the_announced_failure(
    scratch_db, active_grant,
):
    scheduled = _schedule()
    job_id = scheduled["job_id"]
    _row, job = background._get_job(job_id)
    background._deliver_failure(job, "the read failed for real")

    background._finish_job(
        job_id, background._JOB_STATUS_COMPLETED,
        summary="late success from the losing attempt",
        respect_terminal=True)

    assert _job_metadata(job_id)["status"] == background._JOB_STATUS_FAILED
    assert _job_metadata(job_id)["error"]
    assert _job_row(job_id).status == "failed"
    assert not _gate_exists(_gate_id())
    assert len(_assistant_rows()) == 1


def test_post_delivery_finish_completes_after_a_success_delivery(
    scratch_db, active_grant,
):
    scheduled = _schedule()
    job_id = scheduled["job_id"]
    _row, job = background._get_job(job_id)
    assert background.deliver_persisted_result(
        job, _valid_background_row(job_id, "e" * 64)) is True

    background._finish_job(
        job_id, background._JOB_STATUS_COMPLETED, summary="delivered",
        respect_terminal=True)

    assert _job_metadata(job_id)["status"] == background._JOB_STATUS_COMPLETED
    assert _job_row(job_id).status == "completed"
    assert len(_assistant_rows()) == 1
