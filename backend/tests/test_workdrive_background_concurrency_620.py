# -*- coding: utf-8 -*-
"""Cross-session arbitration tests for issue-620 durable WorkDrive delivery.

The main 620 suite runs on one in-memory connection, so every function shares
a single SQLAlchemy identity map/connection and read-then-act races are
invisible.  These tests use a FILE-backed scratch database, ``NullPool`` and a
FRESH ``Session`` per ``get_db_session()`` call — the situation created by two
API processes against the same DB (restart overlap, a second dev instance, an
operator script) and by a near-simultaneous double-send.

Covered here:
* duplicate scheduling is arbitrated by the database schedule gate;
* a run lease is single-writer across distinct sessions (compare-and-swap);
* concurrent executions of one job run once and write one terminal message;
* a job's success delivery is per JOB, not per downloaded sha;
* a failure notice and a success share the same terminal identity;
* saved delivery is withheld when the workspace scope does not match;
* restart recovery still re-delivers persisted results and takes over a
  verified-dead run.

Everything is synthetic: no credentials, network, live workbook, or
production database.  ``TESTING=1`` is set before application imports.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from core import workdrive_background_delivery as background
from core.pending_file_task import build_pending_task

RID = "u-background-620"
FILE_NAME = "Synthetic Price List 2026.xlsx"
ORIGIN_EXECUTION = "exec-interactive-620-c"
SESSION = "session-bg-620-concurrency"
WORKSPACE = "ws-620"
ASK = (
    "find the prices of U-22 and 622 in Synthetic Price List 2026.xlsx"
)
TARGETS = ["U-22", "622"]


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

    db_path = tmp_path / "workdrive-concurrency-620.db"
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
    yield
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


def _job_rows():
    from core.database import get_db_session
    from core.models import AgentExecution

    with get_db_session() as db:
        return list(db.query(AgentExecution).filter(
            AgentExecution.triggered_by == background.TRIGGERED_BY).all())


def _assistant_rows(session_id: str = SESSION):
    from core.database import get_db_session
    from core.models import ChatMessage

    with get_db_session() as db:
        return list(db.query(ChatMessage).filter(
            ChatMessage.conversation_id == session_id,
            ChatMessage.role == "assistant",
        ).all())


def _valid_background_row(
    job_id: str, sha: str, *, workspace: str = WORKSPACE,
) -> dict:
    scope = background.request_scope_from_task(
        session_id=SESSION,
        user_id="u1",
        workspace_id=workspace,
        resource_id=RID,
        file_name=FILE_NAME,
        original_message=ASK,
        requested_targets=TARGETS,
    )
    digest = background.canonical_request_digest(scope)
    return {
        "status": "delivered",
        "rendered": f"answer for {job_id}",
        "identity": {"content_sha256": sha},
        "background_delivery": {
            "schema": background.SCHEMA,
            "job_id": job_id,
            "execution_id": job_id,
            "original_digest": digest,
            "request_scope": scope,
            "content_sha256": sha,
            "proof_execution_id": job_id,
            "status": "delivered",
            "user_id": "u1",
            "workspace_id": workspace,
        },
        "direct_source_proof": {
            "status": "verified",
            "execution_id": job_id,
            "downloaded_sha256": sha,
            "receipt": {"sha256": sha, "execution_id": job_id},
            "materialized": False,
        },
    }


def _job(job_id: str, *, workspace: str = WORKSPACE) -> dict:
    return {
        "job_id": job_id,
        "execution_id": job_id,
        "session_id": SESSION,
        "user_id": "u1",
        "workspace_id": workspace,
        "tenant_id": "default",
        "task": {},
    }


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------

def test_duplicate_schedule_is_arbitrated_across_sessions(
    scratch_db, active_grant,
):
    """Both scans miss (stale read), the gate still yields ONE durable job."""
    real = background._active_job_for
    scans = {"n": 0}

    def stale_then_real(session_id, original_digest):
        scans["n"] += 1
        # The two initial read-then-insert scans see nothing; only the
        # post-conflict re-read (third call) sees committed state.
        if scans["n"] <= 2:
            return None
        return real(session_id, original_digest)

    with patch.object(
            background, "_active_job_for", side_effect=stale_then_real):
        first = _schedule()
        second = _schedule()

    assert first["ok"] is True
    assert first["reused"] is False
    assert second["ok"] is True
    assert second["reused"] is True
    assert second["job_id"] == first["job_id"]
    assert len(_job_rows()) == 1


def test_terminal_finish_releases_the_schedule_gate(scratch_db, active_grant):
    first = _schedule()
    from core.database import get_db_session
    from core.models import DeliveryEvent

    gate = background._schedule_gate_event_id(
        SESSION,
        background.canonical_request_digest(
            background.request_scope_from_task(
                session_id=SESSION, user_id="u1", workspace_id=WORKSPACE,
                resource_id=RID, file_name=FILE_NAME,
                original_message=ASK, requested_targets=TARGETS)))
    with get_db_session() as db:
        assert db.query(DeliveryEvent).filter(
            DeliveryEvent.event_id == gate).count() == 1

    background._finish_job(
        first["job_id"], background._JOB_STATUS_COMPLETED, summary="test")

    with get_db_session() as db:
        assert db.query(DeliveryEvent).filter(
            DeliveryEvent.event_id == gate).count() == 0

    # A re-ask after the terminal state is a NEW job, not a revived one.
    second = _schedule()
    assert second["ok"] is True
    assert second["reused"] is False
    assert second["job_id"] != first["job_id"]


# ---------------------------------------------------------------------------
# Run claim (compare-and-swap on the shared arbiter)
# ---------------------------------------------------------------------------

def test_claim_lease_is_single_writer_across_sessions(scratch_db, active_grant):
    scheduled = _schedule()
    job_id = scheduled["job_id"]
    from core.database import get_db_session

    with get_db_session() as first:
        assert background._claim_run_lease(
            first, job_id=job_id, attempt=1, session_id=SESSION) is True
        first.commit()
    with get_db_session() as second:
        # A distinct database session, same attempt: the PK is the gate.
        assert background._claim_run_lease(
            second, job_id=job_id, attempt=1, session_id=SESSION) is False


def test_concurrent_executions_run_once_and_deliver_one_terminal(
    scratch_db, active_grant,
):
    scheduled = _schedule()
    job_id = scheduled["job_id"]
    start = threading.Barrier(2)
    runs = []

    def counting_runner(job):
        runs.append(job["job_id"])
        # Hold the winning run long enough for the sibling to reach its claim.
        time.sleep(0.25)
        return {"ok": False, "error": "synthetic stop after claiming"}

    def _run():
        start.wait(timeout=10)
        return asyncio.run(background.execute_background_read(
            job_id, read_runner=counting_runner))

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [f.result(timeout=30) for f in (
            pool.submit(_run), pool.submit(_run))]

    assert runs == [job_id]  # exactly one process entered the runner
    assert sum(1 for out in outcomes if out.get("ok")) == 0
    rows = _assistant_rows()
    assert len(rows) == 1
    marker = json.loads(rows[0].metadata_json)["workdrive_background_read"]
    assert marker["job_id"] == job_id
    assert marker["status"] == "failed"


# ---------------------------------------------------------------------------
# One terminal result per job
# ---------------------------------------------------------------------------

def test_success_delivery_is_per_job_not_per_content_sha(scratch_db):
    """Two concurrent reruns that saw different bytes collapse to one row."""
    from core.database import get_db_session
    from core.job_delivery import job_event_id
    from core.models import DeliveryEvent

    job_id = "job-terminal-race-620"
    job = _job(job_id)
    event_id = job_event_id(job_id, "terminal", "workdrive_read")

    # The first process already committed its terminal delivery event; the
    # second process's download produced DIFFERENT bytes (different sha).
    with get_db_session() as db:
        db.add(DeliveryEvent(
            event_id=event_id,
            conversation_id=SESSION,
            job_id=job_id,
            result_revision="terminal",
        ))
        db.commit()

    other_sha_row = _valid_background_row(job_id, "b" * 64)
    assert background.deliver_persisted_result(job, other_sha_row) is False
    assert _assistant_rows() == []

    # Positive control: another job with no terminal event delivers once.
    other_job_id = "job-terminal-control-620"
    assert background.deliver_persisted_result(
        _job(other_job_id),
        _valid_background_row(other_job_id, "c" * 64),
    ) is True
    assert len(_assistant_rows()) == 1


def test_failure_notice_and_success_share_one_terminal_event(scratch_db):
    from core.database import get_db_session
    from core.models import DeliveryEvent

    job_id = "job-failure-then-success-620"
    job = _job(job_id)
    background._deliver_failure(job, "synthetic failure")

    # Whatever a later rerun would persist, the job already has its terminal
    # message and cannot gain a second one.
    assert background.deliver_persisted_result(
        job, _valid_background_row(job_id, "d" * 64)) is False
    rows = _assistant_rows()
    assert len(rows) == 1
    assert json.loads(rows[0].metadata_json)[
        "workdrive_background_read"]["status"] == "failed"
    with get_db_session() as db:
        assert db.query(DeliveryEvent).filter(
            DeliveryEvent.job_id == job_id).count() == 1


# ---------------------------------------------------------------------------
# Workspace scope at saved delivery
# ---------------------------------------------------------------------------

def test_saved_delivery_checks_workspace_scope(scratch_db, active_grant):
    import integrations.chat_orchestrator as chat

    row = _valid_background_row("job-workspace-620", "a" * 64)
    assert background.persisted_delivery_is_valid(
        row, user_id="u1", workspace_id=WORKSPACE) is True
    assert background.persisted_delivery_is_valid(
        row, user_id="u1", workspace_id="ws-other") is False
    # Callers that cannot name a workspace keep the legacy behavior.
    assert background.persisted_delivery_is_valid(row, user_id="u1") is True

    from core.database import get_db_session
    from core.models import ChatMessage

    with get_db_session() as db:
        db.add(ChatMessage(
            conversation_id=SESSION,
            tenant_id="default",
            role="assistant",
            content="saved",
            metadata_json=json.dumps({"pending_file_result": row}),
        ))
        db.commit()

    orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
    assert orch._load_pending_file_result(
        SESSION, workspace_id="ws-other") is None
    loaded = orch._load_pending_file_result(
        SESSION, workspace_id=WORKSPACE)
    assert loaded is not None
    assert loaded["background_delivery"]["job_id"] == "job-workspace-620"


# ---------------------------------------------------------------------------
# Restart recovery is retained
# ---------------------------------------------------------------------------

def test_recovery_redelivers_persisted_result_across_sessions(
    scratch_db, active_grant,
):
    scheduled = _schedule()
    job_id = scheduled["job_id"]
    row = _valid_background_row(job_id, "e" * 64)
    background._store_job_result(job_id, row)

    async def must_not_read(_job):
        raise AssertionError("recovery must not re-download")

    stats = asyncio.run(background.recover_pending_strict_workdrive_reads(
        read_runner=must_not_read))

    assert stats["reused_result"] == 1
    assert stats["delivered"] == 1
    rows = _assistant_rows()
    assert len(rows) == 1
    assert json.loads(rows[0].metadata_json)[
        "pending_file_result"]["background_delivery"]["job_id"] == job_id


def test_recovery_takes_over_only_a_verified_dead_run(scratch_db, active_grant):
    from core.database import get_db_session
    from core.models import AgentExecution

    scheduled = _schedule()
    job_id = scheduled["job_id"]

    # The process that claimed attempt 1 died without finishing.
    with get_db_session() as db:
        row = db.query(AgentExecution).filter(
            AgentExecution.id == job_id).first()
        meta = dict(row.metadata_json or {})
        job = dict(meta[background.JOB_METADATA_KEY])
        job["status"] = background._JOB_STATUS_RUNNING
        job["attempts"] = 1
        meta[background.JOB_METADATA_KEY] = job
        row.metadata_json = meta
        row.status = "running"
        db.commit()

    runs = []

    async def rerun(job):
        runs.append(job["job_id"])
        return {"ok": False, "error": "recovered run stops honestly"}

    with patch(
        "core.execution_ownership.owner_liveness",
        return_value=("dead", {"reason": "no such process"}),
    ):
        stats = asyncio.run(background.recover_pending_strict_workdrive_reads(
            read_runner=rerun))

    assert stats["rerun"] == 0
    assert stats["failed"] == 1
    assert runs == [job_id]
    assert len(_assistant_rows()) == 1


def test_recovery_does_not_rerun_an_announced_failure(scratch_db, active_grant):
    scheduled = _schedule()
    job_id = scheduled["job_id"]

    def failing_runner(_job):
        return {"ok": False, "error": "synthetic permanent failure"}

    first = asyncio.run(background.execute_background_read(
        job_id, read_runner=failing_runner))
    assert first["ok"] is False
    assert len(_assistant_rows()) == 1

    async def must_not_read(_job):
        raise AssertionError("an announced failure is terminal")

    stats = asyncio.run(background.recover_pending_strict_workdrive_reads(
        read_runner=must_not_read))

    assert stats["rerun"] == 0
    assert stats["skipped_terminal"] == 1
    assert len(_assistant_rows()) == 1
