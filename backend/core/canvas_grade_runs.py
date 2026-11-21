"""Durable admission and ownership for Canvas mini-app grading runs.

One row represents one client submission for one mini-app inside one
tenant/workspace/user scope. The row is admitted before any grader work starts,
so a retried submission can always be answered with the same durable run.

The store deliberately contains no grader execution, scheduling, API or UI
code. It owns only the database contract:

* admission is unique on ``(tenant, workspace, user, app, submission)`` and is
  bound to the saved source and test digests;
* a retry with the same submission id and same digests returns the existing
  row, while either digest changing is a conflict;
* claims and terminal transitions are single conditional ``UPDATE`` statements
  fenced by a monotonically increasing integer, so a stale worker cannot write
  after another claim has won;
* the report is write-once: a terminal transition requires the running status
  and the owning fence, and a terminal run can never become running again. The
  guard deliberately does not inspect the report column, because an unset JSON
  column may be SQL NULL or a JSON ``null`` depending on the database;
* recovery interrupts only runs whose recorded owner is VERIFIED dead by
  :mod:`core.execution_ownership`; unknown or live owners are left untouched.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.database import Base
from core import execution_ownership
from core.models import JSONColumn


class CanvasGradeRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


_STATUS_VALUES = tuple(status.value for status in CanvasGradeRunStatus)


class CanvasGradeRun(Base):
    """One durable grading run for a client submission UUID."""

    __tablename__ = "canvas_grade_runs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "user_id",
            "app_id",
            "submission_id",
            name="_canvas_grade_runs_submission_uc",
        ),
        CheckConstraint(
            "status IN (" + ", ".join(f"'{value}'" for value in _STATUS_VALUES) + ")",
            name="ck_canvas_grade_runs_status",
        ),
        Index(
            "ix_canvas_grade_runs_status_updated_at",
            "status",
            "updated_at",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Immutable admission scope. These are the IDs the run is bound to; no
    # lookup accepts a run outside its caller's scope.
    tenant_id = Column(String, nullable=False, index=True)
    workspace_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    app_id = Column(String, nullable=False, index=True)
    submission_id = Column(String, nullable=False, index=True)

    # Saved inputs whose exact identity makes a retry idempotent.
    source_digest = Column(String, nullable=False)
    test_digest = Column(String, nullable=False)

    status = Column(
        String,
        nullable=False,
        default=CanvasGradeRunStatus.PENDING.value,
        server_default=CanvasGradeRunStatus.PENDING.value,
        index=True,
    )

    # Current (or last) worker claim, written by
    # :func:`core.execution_ownership.current_owner` for normal claims.
    owner_metadata = Column(JSONColumn, nullable=True)

    # Fencing token. Every successful claim increments it; every later
    # transition must present the fence issued by that claim.
    fence = Column(Integer, nullable=False, default=0, server_default="0")

    # Exactly one of these records a terminal outcome. ``report`` is write-once
    # and may only be written by the owning claim; ``failure_code`` is the
    # stable reason for a failed/interrupted run.
    report = Column(JSONColumn, nullable=True)
    failure_code = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<CanvasGradeRun(id={self.id}, submission_id={self.submission_id}, "
            f"status={self.status}, fence={self.fence})>"
        )


class CanvasGradeRunError(Exception):
    """Base error for the durable grading-run store."""


class CanvasGradeRunNotFound(CanvasGradeRunError):
    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"canvas grade run {run_id} was not found in scope")


class CanvasGradeRunConflict(CanvasGradeRunError):
    """The request collides with the durable state of an existing run."""


class CanvasGradeRunDigestConflict(CanvasGradeRunConflict):
    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(
            "submission UUID is already bound to different source/test digests "
            f"(run {run_id})"
        )


class CanvasGradeRunStateConflict(CanvasGradeRunConflict):
    def __init__(self, run_id: str, detail: str):
        self.run_id = run_id
        self.detail = detail
        super().__init__(f"canvas grade run {run_id}: {detail}")


class CanvasGradeRunFenceConflict(CanvasGradeRunStateConflict):
    def __init__(self, run_id: str, expected_fence: int, actual_fence: int):
        self.expected_fence = expected_fence
        self.actual_fence = actual_fence
        super().__init__(
            run_id,
            f"fencing token {expected_fence} is stale (current {actual_fence})",
        )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _submission_filters(
    *, tenant_id: str, workspace_id: str, user_id: str, app_id: str,
    submission_id: str,
) -> list[Any]:
    return [
        CanvasGradeRun.tenant_id == tenant_id,
        CanvasGradeRun.workspace_id == workspace_id,
        CanvasGradeRun.user_id == user_id,
        CanvasGradeRun.app_id == app_id,
        CanvasGradeRun.submission_id == submission_id,
    ]


def get_run(
    db: Session,
    run_id: str,
    *,
    tenant_id: str,
    workspace_id: str,
    user_id: str,
    app_id: str,
) -> Optional[CanvasGradeRun]:
    """Return a run by ID, but only inside the caller's full scope."""
    return db.execute(
        select(CanvasGradeRun).where(
            CanvasGradeRun.id == run_id,
            CanvasGradeRun.tenant_id == tenant_id,
            CanvasGradeRun.workspace_id == workspace_id,
            CanvasGradeRun.user_id == user_id,
            CanvasGradeRun.app_id == app_id,
        )
    ).scalar_one_or_none()


def get_run_by_submission(
    db: Session,
    *,
    tenant_id: str,
    workspace_id: str,
    user_id: str,
    app_id: str,
    submission_id: str,
) -> Optional[CanvasGradeRun]:
    """Return a run by its scoped client submission UUID."""
    return db.execute(
        select(CanvasGradeRun).where(
            *_submission_filters(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                user_id=user_id,
                app_id=app_id,
                submission_id=submission_id,
            )
        )
    ).scalar_one_or_none()


def _matching_run(
    run: CanvasGradeRun, source_digest: str, test_digest: str,
) -> CanvasGradeRun:
    if run.source_digest != source_digest or run.test_digest != test_digest:
        raise CanvasGradeRunDigestConflict(run.id)
    return run


def admit_run(
    db: Session,
    *,
    tenant_id: str,
    workspace_id: str,
    user_id: str,
    app_id: str,
    submission_id: str,
    source_digest: str,
    test_digest: str,
) -> CanvasGradeRun:
    """Admit a submission, returning its existing row when it is a retry.

    The unique constraint is the final arbiter. A normal retry is answered by
    the scoped read below; a concurrent inserter that loses the race catches
    the integrity error inside a savepoint, then reads the winner and checks
    its digests. The caller owns the outer transaction and commits once.
    """
    scope = dict(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_id=user_id,
        app_id=app_id,
        submission_id=submission_id,
    )
    existing = get_run_by_submission(db, **scope)
    if existing is not None:
        return _matching_run(existing, source_digest, test_digest)

    run = CanvasGradeRun(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_id=user_id,
        app_id=app_id,
        submission_id=submission_id,
        source_digest=source_digest,
        test_digest=test_digest,
        status=CanvasGradeRunStatus.PENDING.value,
        fence=0,
    )
    try:
        with db.begin_nested():
            db.add(run)
            db.flush()
    except IntegrityError:
        # Another worker admitted the same submission between the read above
        # and this insert. Its row is authoritative; only the digests decide
        # whether this is an idempotent retry or a conflict.
        existing = get_run_by_submission(db, **scope)
        if existing is None:
            raise
        return _matching_run(existing, source_digest, test_digest)
    return run


def claim_run(
    db: Session,
    run_id: str,
    *,
    tenant_id: str,
    workspace_id: str,
    user_id: str,
    app_id: str,
    owner_metadata: Optional[Dict[str, Any]] = None,
) -> CanvasGradeRun:
    """Move a pending run to running and issue its fencing token.

    The owner is recorded in the same conditional update that changes the
    status and increments the fence. A second claimant that read the same
    pending row matches zero rows and cannot become the owner.
    """
    run = get_run(
        db,
        run_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_id=user_id,
        app_id=app_id,
    )
    if run is None:
        raise CanvasGradeRunNotFound(run_id)
    if run.status != CanvasGradeRunStatus.PENDING.value:
        raise CanvasGradeRunStateConflict(
            run_id, f"only pending runs can be claimed (status is {run.status})")

    expected_fence = run.fence
    owner = (dict(owner_metadata) if owner_metadata is not None
             else execution_ownership.current_owner())
    now = _utcnow()
    result = db.execute(
        update(CanvasGradeRun)
        .where(
            CanvasGradeRun.id == run.id,
            CanvasGradeRun.status == CanvasGradeRunStatus.PENDING.value,
            CanvasGradeRun.fence == expected_fence,
        )
        .values(
            status=CanvasGradeRunStatus.RUNNING.value,
            owner_metadata=owner,
            fence=expected_fence + 1,
            started_at=now,
            completed_at=None,
            failure_code=None,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.refresh(run)
        if run.status != CanvasGradeRunStatus.PENDING.value:
            raise CanvasGradeRunStateConflict(
                run_id,
                f"only pending runs can be claimed (status is {run.status})",
            )
        raise CanvasGradeRunFenceConflict(run_id, expected_fence, run.fence)

    db.refresh(run)
    return run


def _raise_terminal_conflict(
    run: CanvasGradeRun, expected_fence: int,
) -> None:
    if run.status != CanvasGradeRunStatus.RUNNING.value:
        raise CanvasGradeRunStateConflict(
            run.id,
            f"only running runs can be finished (status is {run.status})",
        )
    if run.fence != expected_fence:
        raise CanvasGradeRunFenceConflict(
            run.id, expected_fence, run.fence)
    raise CanvasGradeRunStateConflict(
        run.id, "the transition conditions were not met")


def complete_run(
    db: Session,
    run_id: str,
    *,
    tenant_id: str,
    workspace_id: str,
    user_id: str,
    app_id: str,
    fence: int,
    report: Any,
) -> CanvasGradeRun:
    """Write the report and finish a running claim, exactly once."""
    if report is None:
        raise ValueError("a completed run requires a report")

    run = get_run(
        db,
        run_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_id=user_id,
        app_id=app_id,
    )
    if run is None:
        raise CanvasGradeRunNotFound(run_id)

    now = _utcnow()
    result = db.execute(
        update(CanvasGradeRun)
        .where(
            CanvasGradeRun.id == run.id,
            CanvasGradeRun.status == CanvasGradeRunStatus.RUNNING.value,
            CanvasGradeRun.fence == fence,
        )
        .values(
            status=CanvasGradeRunStatus.COMPLETED.value,
            report=report,
            failure_code=None,
            completed_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.refresh(run)
        _raise_terminal_conflict(run, fence)

    db.refresh(run)
    return run


def fail_run(
    db: Session,
    run_id: str,
    *,
    tenant_id: str,
    workspace_id: str,
    user_id: str,
    app_id: str,
    fence: int,
    failure_code: str,
) -> CanvasGradeRun:
    """Finish a running claim with a stable failure code."""
    if not failure_code:
        raise ValueError("a failed run requires a failure code")

    run = get_run(
        db,
        run_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_id=user_id,
        app_id=app_id,
    )
    if run is None:
        raise CanvasGradeRunNotFound(run_id)

    now = _utcnow()
    result = db.execute(
        update(CanvasGradeRun)
        .where(
            CanvasGradeRun.id == run.id,
            CanvasGradeRun.status == CanvasGradeRunStatus.RUNNING.value,
            CanvasGradeRun.fence == fence,
        )
        .values(
            status=CanvasGradeRunStatus.FAILED.value,
            failure_code=failure_code,
            completed_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.refresh(run)
        _raise_terminal_conflict(run, fence)

    db.refresh(run)
    return run


def recover_interrupted_runs(db: Session) -> List[str]:
    """Interrupt running runs whose recorded owner is VERIFIED dead.

    ``owner_liveness`` is the sole authority. Its ``live`` and ``self``
    verdicts belong to a worker that is still running, and ``unknown`` means
    ownership could not be established; all of those are left exactly as they
    are. Only ``dead`` (no such pid, or a confirmed pid reuse) is recovered.

    Each update is still conditional on the status and fence observed in this
    sweep, so a concurrently finishing run is not overwritten. The caller owns
    the transaction and may commit the whole sweep at once.
    """
    rows = db.execute(
        select(CanvasGradeRun).where(
            CanvasGradeRun.status == CanvasGradeRunStatus.RUNNING.value)
    ).scalars().all()

    recovered: List[str] = []
    now = _utcnow()
    for run in rows:
        owner_state, _detail = execution_ownership.owner_liveness(
            {"owner": run.owner_metadata})
        if owner_state != "dead":
            continue

        result = db.execute(
            update(CanvasGradeRun)
            .where(
                CanvasGradeRun.id == run.id,
                CanvasGradeRun.status == CanvasGradeRunStatus.RUNNING.value,
                CanvasGradeRun.fence == run.fence,
            )
            .values(
                status=CanvasGradeRunStatus.INTERRUPTED.value,
                failure_code="worker_lost",
                completed_at=now,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 1:
            recovered.append(run.id)

    return recovered


__all__ = [
    "CanvasGradeRun",
    "CanvasGradeRunConflict",
    "CanvasGradeRunDigestConflict",
    "CanvasGradeRunError",
    "CanvasGradeRunFenceConflict",
    "CanvasGradeRunNotFound",
    "CanvasGradeRunStateConflict",
    "CanvasGradeRunStatus",
    "admit_run",
    "claim_run",
    "complete_run",
    "fail_run",
    "get_run",
    "get_run_by_submission",
    "recover_interrupted_runs",
]
