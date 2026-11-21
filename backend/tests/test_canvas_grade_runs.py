"""Focused regressions for the durable Canvas grading-run store.

These tests exercise the real Atom ``Base`` and ``JSONColumn`` dependencies so
the stored report has the same representation as it does in the application:
on both PostgreSQL (JSONB) and SQLite an unset JSON column can be a JSON
``null`` rather than SQL NULL.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import UniqueConstraint, create_engine, func, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.canvas_grade_runs import (  # noqa: E402
    CanvasGradeRun,
    CanvasGradeRunDigestConflict,
    CanvasGradeRunFenceConflict,
    CanvasGradeRunStateConflict,
    CanvasGradeRunStatus,
    admit_run,
    claim_run,
    complete_run,
    fail_run,
    get_run,
    get_run_by_submission,
    recover_interrupted_runs,
)
from core.database import Base  # noqa: E402
from core.execution_ownership import HOSTNAME, current_owner  # noqa: E402
from core.models import JSONColumn  # noqa: E402
import core.canvas_grade_runs as canvas_grade_runs  # noqa: E402


SCOPE = {
    "tenant_id": "tenant-a",
    "workspace_id": "workspace-a",
    "user_id": "user-a",
    "app_id": "app-a",
}
SOURCE_DIGEST = "sha256:source-a"
TEST_DIGEST = "sha256:test-a"


def _admit(session, **overrides):
    values = {
        **SCOPE,
        "submission_id": "submission-1",
        "source_digest": SOURCE_DIGEST,
        "test_digest": TEST_DIGEST,
    }
    values.update(overrides)
    return admit_run(session, **values)


def _in_scope(session, run_id, **overrides):
    values = {**SCOPE, **overrides}
    return get_run(session, run_id, **values)


def _by_submission(session, **overrides):
    values = {**SCOPE, "submission_id": "submission-1"}
    values.update(overrides)
    return get_run_by_submission(session, **values)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[CanvasGradeRun.__table__])
    factory = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_model_is_registered_on_the_shared_base():
    table = Base.metadata.tables["canvas_grade_runs"]
    assert table is CanvasGradeRun.__table__
    assert isinstance(table.c.report.type, JSONColumn)
    assert isinstance(table.c.owner_metadata.type, JSONColumn)
    named = {
        constraint.name for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert "_canvas_grade_runs_submission_uc" in named


def test_admission_is_idempotent_and_digest_bound(session):
    first = _admit(session)
    session.commit()

    second = _admit(session)
    session.commit()

    assert second.id == first.id
    assert session.scalar(
        select(func.count()).select_from(CanvasGradeRun)) == 1
    assert first.status == CanvasGradeRunStatus.PENDING.value
    assert first.fence == 0
    assert first.source_digest == SOURCE_DIGEST
    assert first.test_digest == TEST_DIGEST

    with pytest.raises(CanvasGradeRunDigestConflict):
        _admit(session, source_digest="sha256:different-source")
    with pytest.raises(CanvasGradeRunDigestConflict):
        _admit(session, test_digest="sha256:different-test")


def test_admission_absorbs_a_unique_key_collision(session):
    first = _admit(session)
    session.commit()

    real_lookup = canvas_grade_runs.get_run_by_submission
    calls = []

    def miss_once_then_lookup(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            return None
        return real_lookup(*args, **kwargs)

    canvas_grade_runs.get_run_by_submission = miss_once_then_lookup
    try:
        second = _admit(session)
        session.commit()
    finally:
        canvas_grade_runs.get_run_by_submission = real_lookup

    assert len(calls) >= 2
    assert second.id == first.id
    assert session.scalar(
        select(func.count()).select_from(CanvasGradeRun)) == 1


def test_submission_is_isolated_by_every_scope_id(session):
    first = _admit(session)
    session.commit()

    other_tenant = _admit(session, tenant_id="tenant-b")
    other_workspace = _admit(session, workspace_id="workspace-b")
    other_user = _admit(session, user_id="user-b")
    other_app = _admit(session, app_id="app-b")
    session.commit()

    ids = {
        first.id,
        other_tenant.id,
        other_workspace.id,
        other_user.id,
        other_app.id,
    }
    assert len(ids) == 5
    assert session.scalar(
        select(func.count()).select_from(CanvasGradeRun)) == 5

    assert _in_scope(session, first.id).id == first.id
    assert _in_scope(session, first.id, tenant_id="tenant-b") is None
    assert _in_scope(session, first.id, workspace_id="workspace-b") is None
    assert _in_scope(session, first.id, user_id="user-b") is None
    assert _in_scope(session, first.id, app_id="app-b") is None

    assert _by_submission(session).id == first.id
    assert _by_submission(session, tenant_id="tenant-b").id == other_tenant.id
    assert (
        _by_submission(session, workspace_id="workspace-b").id
        == other_workspace.id
    )
    assert _by_submission(session, user_id="user-b").id == other_user.id
    assert _by_submission(session, app_id="app-b").id == other_app.id

    # A run ID from one scope must never resolve through another scope, even
    # though those scopes do contain distinct runs for the same submission.
    assert _in_scope(session, other_tenant.id, tenant_id="tenant-a") is None
    assert (
        _in_scope(session, other_workspace.id, workspace_id="workspace-a")
        is None
    )
    assert _in_scope(session, other_user.id, user_id="user-a") is None
    assert _in_scope(session, other_app.id, app_id="app-a") is None


def test_both_terminal_paths_do_not_depend_on_sql_null_report(session):
    completing = _admit(session, submission_id="submission-completing")
    failing = _admit(session, submission_id="submission-failing")
    session.commit()

    # An unset JSON column can be the JSON literal null rather than SQL NULL on
    # both PostgreSQL (JSONB) and SQLite. A terminal guard that compared
    # ``report IS NULL`` would refuse both of the transitions below.
    session.execute(
        update(CanvasGradeRun)
        .where(CanvasGradeRun.id.in_([completing.id, failing.id]))
        .values(report=None)
    )
    session.commit()

    completing_claim = claim_run(session, completing.id, **SCOPE)
    failing_claim = claim_run(session, failing.id, **SCOPE)
    session.commit()

    completed = complete_run(
        session,
        completing.id,
        **SCOPE,
        fence=completing_claim.fence,
        report={"passed": True},
    )
    failed = fail_run(
        session,
        failing.id,
        **SCOPE,
        fence=failing_claim.fence,
        failure_code="tests_failed",
    )
    session.commit()

    assert completed.status == CanvasGradeRunStatus.COMPLETED.value
    assert completed.report == {"passed": True}
    assert failed.status == CanvasGradeRunStatus.FAILED.value
    assert failed.failure_code == "tests_failed"
    assert failed.report is None


def test_claim_fences_stale_workers_and_report_is_write_once(session):
    run = _admit(session)
    session.commit()

    claimed = claim_run(
        session,
        run.id,
        **SCOPE,
        owner_metadata={
            "pid": 1234,
            "token": "worker-a",
            "host": "test-host",
        },
    )
    session.commit()

    assert claimed.status == CanvasGradeRunStatus.RUNNING.value
    assert claimed.fence == 1
    assert claimed.started_at is not None
    assert claimed.owner_metadata["token"] == "worker-a"

    with pytest.raises(CanvasGradeRunStateConflict):
        claim_run(session, run.id, **SCOPE)

    with pytest.raises(CanvasGradeRunFenceConflict):
        complete_run(
            session,
            run.id,
            **SCOPE,
            fence=0,
            report={"passed": True},
        )

    completed = complete_run(
        session,
        run.id,
        **SCOPE,
        fence=claimed.fence,
        report={"passed": True, "score": 1.0},
    )
    session.commit()

    assert completed.status == CanvasGradeRunStatus.COMPLETED.value
    assert completed.report == {"passed": True, "score": 1.0}
    assert completed.failure_code is None
    assert completed.completed_at is not None

    # A retry after the terminal transition still returns the same durable run.
    assert _admit(session).id == run.id

    with pytest.raises(CanvasGradeRunStateConflict):
        complete_run(
            session,
            run.id,
            **SCOPE,
            fence=claimed.fence,
            report={"passed": False},
        )

    session.expire_all()
    stored = _in_scope(session, run.id)
    assert stored.report == {"passed": True, "score": 1.0}


def test_failure_requires_the_owning_fence(session):
    run = _admit(session)
    session.commit()

    with pytest.raises(CanvasGradeRunStateConflict):
        fail_run(
            session,
            run.id,
            **SCOPE,
            fence=0,
            failure_code="not_claimed",
        )

    claimed = claim_run(session, run.id, **SCOPE)
    session.commit()

    with pytest.raises(CanvasGradeRunFenceConflict):
        fail_run(
            session,
            run.id,
            **SCOPE,
            fence=claimed.fence - 1,
            failure_code="stale_worker",
        )

    failed = fail_run(
        session,
        run.id,
        **SCOPE,
        fence=claimed.fence,
        failure_code="tests_failed",
    )
    session.commit()

    assert failed.status == CanvasGradeRunStatus.FAILED.value
    assert failed.failure_code == "tests_failed"
    assert failed.report is None
    assert failed.completed_at is not None

    # A failed run is terminal: completion cannot write a report over it.
    with pytest.raises(CanvasGradeRunStateConflict):
        complete_run(
            session,
            run.id,
            **SCOPE,
            fence=claimed.fence,
            report={"passed": True},
        )
    session.expire_all()
    assert _in_scope(session, run.id).report is None


def test_recovery_interrupts_only_a_verified_dead_owner(session):
    dead = _admit(session, submission_id="submission-dead")
    live = _admit(session, submission_id="submission-live")
    unknown = _admit(session, submission_id="submission-unknown")
    session.commit()

    claim_run(
        session,
        dead.id,
        **SCOPE,
        owner_metadata={
            "pid": 99_999_999,
            "token": "dead-worker",
            "host": HOSTNAME,
        },
    )
    claim_run(
        session,
        live.id,
        **SCOPE,
        owner_metadata=current_owner(),
    )
    claim_run(
        session,
        unknown.id,
        **SCOPE,
        owner_metadata={},
    )
    session.commit()

    recovered = recover_interrupted_runs(session)
    session.commit()

    assert recovered == [dead.id]

    session.expire_all()
    dead_row = _in_scope(session, dead.id)
    live_row = _in_scope(session, live.id)
    unknown_row = _in_scope(session, unknown.id)

    assert dead_row.status == CanvasGradeRunStatus.INTERRUPTED.value
    assert dead_row.failure_code == "worker_lost"
    assert dead_row.completed_at is not None

    assert live_row.status == CanvasGradeRunStatus.RUNNING.value
    assert live_row.completed_at is None
    assert live_row.failure_code is None

    assert unknown_row.status == CanvasGradeRunStatus.RUNNING.value
    assert unknown_row.completed_at is None
    assert unknown_row.failure_code is None

    # Recovery is idempotent: nothing remains in a recoverable running state
    # for the dead owner, and the live/unknown rows stay exactly where they were.
    assert recover_interrupted_runs(session) == []
