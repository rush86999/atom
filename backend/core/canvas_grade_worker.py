"""Runtime admission/status orchestration and polling worker for Canvas grades.

The durable store lives in ``core.canvas_grade_runs``. This module owns the
authorization/digest checks that admit a run, the status read, and the
background worker that claims pending rows and executes the same grading path
as ``mini_app_service.run_tests``.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from core.canvas_grade_runs import (
    CanvasGradeRun,
    CanvasGradeRunConflict,
    CanvasGradeRunError,
    CanvasGradeRunStatus,
    admit_run,
    claim_run,
    complete_run,
    fail_run,
    get_run,
    get_run_by_submission,
    recover_interrupted_runs,
)

logger = logging.getLogger(__name__)

# Reply statuses (never durable row states).
STATUS_NOT_FOUND = "not_found"
STATUS_REJECTED = "rejected"
STATUS_CONFLICT = "conflict"
STATUS_ERROR = "error"
STATUS_FORBIDDEN = "forbidden"
STATUS_INVALID_REQUEST = "invalid_request"

# Stable failure codes persisted on the run row / surfaced as ``error``.
FAILURE_USER_NOT_FOUND = "user_not_found"
FAILURE_USER_INACTIVE = "user_inactive"
FAILURE_APP_NOT_FOUND = "app_not_found"
FAILURE_OWNERSHIP_CHANGED = "ownership_changed"
FAILURE_SCOPE_MISMATCH = "scope_mismatch"
FAILURE_SOURCE_DIGEST_MISMATCH = "mini_app_logic_changed"
FAILURE_TESTS_DIGEST_MISMATCH = "mini_app_acceptance_tests_changed"
FAILURE_SAVED_TESTS_INVALID = "mini_app_saved_tests_invalid"
FAILURE_EXECUTION = "grade_execution_failed"
FAILURE_RUN_NOT_FOUND = "canvas_grade_run_not_found"
FAILURE_SUBMISSION_CONFLICT = "submission_digest_conflict"
FAILURE_WORKER_SHUTDOWN = "worker_shutdown"


def _norm(value: Any) -> Optional[str]:
    return None if value is None else str(value)


def _canonical_submission_id(value: Any) -> str:
    if value is None or not str(value).strip():
        raise ValueError("submission_id is required")
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("submission_id must be a UUID") from exc


def _user_is_active(user: Any) -> bool:
    return getattr(user, "is_active", True) is not False


def _load_user(db: Any, user_id: Any) -> Optional[Any]:
    from core.models import User

    if user_id is None:
        return None
    return db.query(User).filter(User.id == str(user_id)).first()


def _load_app(db: Any, app_id: Any) -> Optional[Any]:
    from core.models import MiniApp

    if app_id is None:
        return None
    return db.query(MiniApp).filter(MiniApp.id == str(app_id)).first()


def _authorize_app(
    db: Any, user_id: Any, app_id: Any
) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
    """Authorize the current actor for the app before looking at digest pins."""
    user = _load_user(db, user_id)
    if user is None:
        return None, None, FAILURE_USER_NOT_FOUND
    if not _user_is_active(user):
        return None, None, FAILURE_USER_INACTIVE
    app = _load_app(db, app_id)
    if app is None:
        return None, None, FAILURE_APP_NOT_FOUND
    if str(app.created_by) != str(user.id):
        return None, None, "not_app_owner"
    return user, app, None


def _nonempty_scope(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _scope_refusal(user: Any, app: Any) -> Optional[str]:
    """Refuse durable grading unless User and MiniApp share a nonempty scope.

    The durable store requires non-null tenant/workspace, so this is checked
    against the active DB rows before any submission or status lookup.
    """
    user_tenant = _nonempty_scope(getattr(user, "tenant_id", None))
    user_workspace = _nonempty_scope(getattr(user, "workspace_id", None))
    app_tenant = _nonempty_scope(getattr(app, "tenant_id", None))
    app_workspace = _nonempty_scope(getattr(app, "workspace_id", None))
    if (
        user_tenant is None
        or user_workspace is None
        or app_tenant is None
        or app_workspace is None
        or user_tenant != app_tenant
        or user_workspace != app_workspace
    ):
        return FAILURE_SCOPE_MISMATCH
    return None


def _scope_for_app(app: Any, user_id: Any) -> Dict[str, Any]:
    tenant_id = getattr(app, "tenant_id", None)
    if tenant_id is None:
        raise CanvasGradeRunError("app has no tenant scope")
    return {
        "tenant_id": str(tenant_id),
        "workspace_id": _norm(getattr(app, "workspace_id", None)),
        "user_id": str(user_id),
        "app_id": str(app.id),
    }


def source_digest_for_app(db: Any, app: Any) -> str:
    """Digest of the app's currently saved logic source."""
    from core.canvas_logic_service import CanvasLogicService
    from core.mini_app_service import logic_source_sha256

    canvas_id = getattr(app, "blueprint_canvas_id", None)
    if not canvas_id:
        return logic_source_sha256("")
    logic = CanvasLogicService(db).load_logic(canvas_id) or {}
    return logic_source_sha256(logic.get("source", ""))


def tests_digest_for_app(app: Any) -> str:
    """Digest of the app's currently saved acceptance-test suite."""
    from core.task_lifecycle import _approval_payload_hash

    tests = (getattr(app, "manifest", None) or {}).get("tests") or []
    return _approval_payload_hash(tests)


def tests_for_app(app: Any) -> List[Dict[str, Any]]:
    from core.mini_app_service import validate_tests

    tests = (getattr(app, "manifest", None) or {}).get("tests") or []
    validate_tests(tests)
    return tests


# ---------------------------------------------------------------------------
# Admission/status (authorization happens before digest checks)
# ---------------------------------------------------------------------------
def start_grade(
    db: Any,
    *,
    user_id: Any,
    app_id: Any,
    submission_id: Any,
    expected_source_digest: Any,
    expected_tests_digest: Any,
) -> Tuple[Optional[CanvasGradeRun], Optional[str]]:
    """Authorize, idempotently resolve, validate saved digests, then admit.

    Returns ``(run, error_code)``. A divergent same-submission retry raises
    ``CanvasGradeRunConflict``. Caller commits on success.
    """
    user, app, auth_error = _authorize_app(db, user_id, app_id)
    if auth_error is not None:
        return None, auth_error
    scope_error = _scope_refusal(user, app)
    if scope_error is not None:
        return None, scope_error
    scope = _scope_for_app(app, user.id)
    submission = _canonical_submission_id(submission_id)

    # Retry-first: an already admitted submission is returned by its pins even
    # if the app's saved source/tests changed after admission.
    existing = get_run_by_submission(db, **scope, submission_id=submission)
    if existing is not None:
        if (
            existing.source_digest == _norm(expected_source_digest)
            and existing.test_digest == _norm(expected_tests_digest)
        ):
            return existing, None
        raise CanvasGradeRunConflict(
            "submission id is already pinned to different source/test digests"
        )

    if expected_source_digest is None or expected_tests_digest is None:
        return None, "digest_required"

    current_source = source_digest_for_app(db, app)
    if current_source != str(expected_source_digest):
        return None, FAILURE_SOURCE_DIGEST_MISMATCH

    try:
        # Validate the saved suite before trusting any digest over it.
        tests_for_app(app)
        current_tests = tests_digest_for_app(app)
    except ValueError:
        return None, FAILURE_SAVED_TESTS_INVALID
    if current_tests != str(expected_tests_digest):
        return None, FAILURE_TESTS_DIGEST_MISMATCH

    row = admit_run(
        db,
        **scope,
        submission_id=submission,
        source_digest=str(expected_source_digest),
        test_digest=str(expected_tests_digest),
    )
    return row, None


def get_grade_status(
    db: Any,
    *,
    user_id: Any,
    app_id: Any,
    submission_id: Any = None,
    run_id: Any = None,
) -> Tuple[Optional[CanvasGradeRun], Optional[str]]:
    """Return a run by submission id or run id after current-user auth.

    Status is scoped to the authenticated user (``run.user_id``), so the
    original submitter can still read the outcome after an app ownership
    change. It is never a cross-scope lookup: another user's submission id
    simply misses. ``(None, None)`` means an exact-scope miss, distinguishable
    from a typed error.
    """
    user = _load_user(db, user_id)
    if user is None:
        return None, FAILURE_USER_NOT_FOUND
    if not _user_is_active(user):
        return None, FAILURE_USER_INACTIVE
    app = _load_app(db, app_id)
    if app is None:
        return None, FAILURE_APP_NOT_FOUND

    scope_error = _scope_refusal(user, app)
    if scope_error is not None:
        return None, scope_error
    scope = _scope_for_app(app, user.id)
    if submission_id is not None:
        row = get_run_by_submission(
            db, **scope, submission_id=_canonical_submission_id(submission_id)
        )
    elif run_id is not None:
        row = get_run(db, str(run_id), **scope)
    else:
        return None, "run_or_submission_required"

    if row is not None:
        return row, None
    # A non-owner cannot probe another owner's app for run ids.
    if str(app.created_by) != str(user.id):
        return None, "not_app_owner"
    return None, None


# ---------------------------------------------------------------------------
# Worker: reload the real actor, verify every scope id/ownership, re-check the
# saved digests, then reuse the synchronous grading execution.
# ---------------------------------------------------------------------------
def _same_scope_value(current: Any, expected: Any) -> bool:
    return _norm(current) == _norm(expected)


def _worker_preflight(
    db: Any, run: CanvasGradeRun
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Reload User/MiniApp and verify all scope ids + current ownership."""
    from core.models import MiniApp, User

    user = db.query(User).filter(User.id == str(run.user_id)).first()
    if user is None:
        return None, FAILURE_USER_NOT_FOUND
    if not _user_is_active(user):
        return None, FAILURE_USER_INACTIVE
    if str(user.id) != str(run.user_id):
        return None, FAILURE_SCOPE_MISMATCH
    if not _same_scope_value(getattr(user, "tenant_id", None), run.tenant_id):
        return None, FAILURE_SCOPE_MISMATCH
    if not _same_scope_value(getattr(user, "workspace_id", None), run.workspace_id):
        return None, FAILURE_SCOPE_MISMATCH

    app = db.query(MiniApp).filter(MiniApp.id == str(run.app_id)).first()
    if app is None:
        return None, FAILURE_APP_NOT_FOUND
    if str(app.id) != str(run.app_id):
        return None, FAILURE_SCOPE_MISMATCH
    if not _same_scope_value(getattr(app, "tenant_id", None), run.tenant_id):
        return None, FAILURE_SCOPE_MISMATCH
    if not _same_scope_value(getattr(app, "workspace_id", None), run.workspace_id):
        return None, FAILURE_SCOPE_MISMATCH
    if str(app.created_by) != str(run.user_id):
        return None, FAILURE_OWNERSHIP_CHANGED

    current_source = source_digest_for_app(db, app)
    if current_source != run.source_digest:
        return None, FAILURE_SOURCE_DIGEST_MISMATCH
    try:
        tests = tests_for_app(app)
        current_tests = tests_digest_for_app(app)
    except ValueError:
        return None, FAILURE_SAVED_TESTS_INVALID
    if current_tests != run.test_digest:
        return None, FAILURE_TESTS_DIGEST_MISMATCH

    blueprint_canvas_id = getattr(app, "blueprint_canvas_id", None)
    if not blueprint_canvas_id:
        return None, FAILURE_APP_NOT_FOUND

    viewer = SimpleNamespace(
        id=str(user.id),
        tenant_id=getattr(user, "tenant_id", None),
        workspace_id=getattr(user, "workspace_id", None),
        tier=getattr(user, "tier", None),
    )
    return {
        "app_id": str(app.id),
        "blueprint_canvas_id": str(blueprint_canvas_id),
        "source_digest": run.source_digest,
        "tests": tests,
        "viewer": viewer,
    }, None


def _finish_run(
    run_id: str,
    scope: Dict[str, Any],
    fence: int,
    *,
    report: Any = None,
    failure_code: Optional[str] = None,
) -> None:
    from core.database import get_db_session

    try:
        with get_db_session() as db:
            if failure_code is None:
                complete_run(db, run_id, **scope, fence=fence, report=report)
            else:
                fail_run(
                    db, run_id, **scope, fence=fence, failure_code=failure_code
                )
            db.commit()
    except CanvasGradeRunConflict:
        logger.warning(
            "canvas grade run %s was already resolved by another fence", run_id
        )
    except Exception as exc:  # noqa: BLE001 — a worker must not crash the loop
        logger.error("canvas grade run %s could not be finished: %s", run_id, exc)


async def _execute_claimed_run(
    run_id: str, scope: Dict[str, Any], fence: int
) -> None:
    from core.database import get_db_session

    preflight: Optional[Dict[str, Any]] = None
    failure: Optional[str] = None
    try:
        with get_db_session() as db:
            row = get_run(db, run_id, **scope)
            if (
                row is None
                or row.status != CanvasGradeRunStatus.RUNNING.value
                or int(row.fence or 0) != int(fence)
            ):
                return
            preflight, failure = _worker_preflight(db, row)
    except Exception as exc:  # noqa: BLE001
        logger.error("canvas grade preflight failed for %s: %s", run_id, exc)
        failure = FAILURE_EXECUTION

    if failure is not None or preflight is None:
        _finish_run(run_id, scope, fence, failure_code=failure or FAILURE_EXECUTION)
        return

    try:
        # Reuse the synchronous Chat grading execution exactly.
        from core.mini_app_service import run_tests

        report = await run_tests(
            preflight["app_id"],
            preflight["blueprint_canvas_id"],
            preflight["tests"],
            viewer=preflight["viewer"],
            expected_source_sha256=preflight["source_digest"],
        )
        if not isinstance(report, dict):
            _finish_run(run_id, scope, fence, failure_code=FAILURE_EXECUTION)
            return
        if report.get("interrupted"):
            _finish_run(
                run_id,
                scope,
                fence,
                failure_code=str(report.get("error") or FAILURE_EXECUTION),
            )
            return
        _finish_run(run_id, scope, fence, report=report)
    except asyncio.CancelledError:
        # Graceful shutdown: fence the run failed so a same-process lifespan
        # restart does not strand it. Crash recovery marks it interrupted.
        _finish_run(run_id, scope, fence, failure_code=FAILURE_WORKER_SHUTDOWN)
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("canvas grade execution failed for %s: %s", run_id, exc)
        _finish_run(run_id, scope, fence, failure_code=FAILURE_EXECUTION)


def _poll_batch_size() -> int:
    try:
        return max(1, int(os.getenv("CANVAS_GRADE_POLL_BATCH", "5")))
    except (TypeError, ValueError):
        return 5


def _poll_interval_seconds() -> float:
    try:
        return max(0.05, float(os.getenv("CANVAS_GRADE_POLL_SECONDS", "1.0")))
    except (TypeError, ValueError):
        return 1.0


async def process_pending_grades_once(limit: Optional[int] = None) -> int:
    """Poll a bounded batch of pending runs, claim each, and execute it.

    Returns the number of runs this call actually claimed/executed.
    """
    from core.database import get_db_session

    batch = _poll_batch_size() if limit is None else max(1, int(limit))
    try:
        with get_db_session() as db:
            rows = (
                db.query(CanvasGradeRun)
                .filter(
                    CanvasGradeRun.status == CanvasGradeRunStatus.PENDING.value
                )
                .order_by(CanvasGradeRun.created_at.asc(), CanvasGradeRun.id.asc())
                .limit(batch)
                .all()
            )
            candidates = [
                {
                    "run_id": str(row.id),
                    "tenant_id": row.tenant_id,
                    "workspace_id": row.workspace_id,
                    "user_id": row.user_id,
                    "app_id": row.app_id,
                }
                for row in rows
            ]
    except Exception as exc:  # noqa: BLE001 — table may not exist during early boot
        logger.debug("canvas grade pending poll skipped: %s", exc)
        return 0

    processed = 0
    for candidate in candidates:
        run_id = candidate.pop("run_id")
        fence: Optional[int] = None
        try:
            with get_db_session() as db:
                claimed = claim_run(db, run_id, **candidate)
                fence = int(claimed.fence or 0)
                db.commit()
        except (CanvasGradeRunConflict, CanvasGradeRunError):
            continue
        except Exception as exc:  # noqa: BLE001
            logger.error("canvas grade claim failed for %s: %s", run_id, exc)
            continue
        if fence is None:
            continue
        await _execute_claimed_run(run_id, candidate, fence)
        processed += 1
    return processed


def _recover_at_worker_start() -> List[str]:
    from core.database import get_db_session

    try:
        with get_db_session() as db:
            ids = recover_interrupted_runs(db)
            if ids:
                db.commit()
                logger.info(
                    "Canvas grading recovery marked %d interrupted run(s)", len(ids)
                )
            return ids
    except Exception as exc:  # noqa: BLE001 — startup must not block/fail
        logger.error("Canvas grading recovery skipped: %s", exc)
        return []


_worker_task: Optional[asyncio.Task] = None
_worker_stop: Optional[asyncio.Event] = None
_worker_requested = False


async def canvas_grade_worker_loop() -> None:
    """Long-lived bounded-poll worker. First pass marks interrupted runs."""
    global _worker_task, _worker_requested, _worker_stop
    _worker_task = asyncio.current_task()
    if _worker_stop is None:
        _worker_stop = asyncio.Event()
    interval = _poll_interval_seconds()
    try:
        _recover_at_worker_start()
        while _worker_stop is None or not _worker_stop.is_set():
            processed = 0
            try:
                processed = await process_pending_grades_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.error("Canvas grading poll failed: %s", exc)
            if processed:
                # Yield, then poll again immediately for a bounded backlog.
                await asyncio.sleep(0)
                continue
            try:
                assert _worker_stop is not None
                await asyncio.wait_for(_worker_stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
    except asyncio.CancelledError:
        raise
    finally:
        _worker_task = None
        _worker_requested = False


def start_canvas_grade_worker(*, spawn: Optional[Any] = None) -> bool:
    """Start the worker exactly once; a live worker is never duplicated."""
    global _worker_stop, _worker_requested
    if _worker_requested:
        return False
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("Canvas grading worker not started: no running event loop")
        return False

    _worker_requested = True
    _worker_stop = asyncio.Event()
    coro = canvas_grade_worker_loop()
    try:
        if spawn is not None:
            spawn(coro)
        else:
            asyncio.create_task(coro)
    except Exception:
        _worker_requested = False
        try:
            coro.close()
        except Exception:  # noqa: BLE001
            pass
        raise
    return True


async def stop_canvas_grade_worker() -> None:
    """Ask the worker to stop, then cancel it if an in-flight run is too long."""
    if _worker_stop is not None:
        _worker_stop.set()
    task = _worker_task
    if task is None or task.done() or task is asyncio.current_task():
        return
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        pass


__all__ = [
    "CanvasGradeRun",
    "CanvasGradeRunConflict",
    "CanvasGradeRunError",
    "CanvasGradeRunStatus",
    "STATUS_NOT_FOUND",
    "STATUS_REJECTED",
    "STATUS_CONFLICT",
    "STATUS_ERROR",
    "STATUS_FORBIDDEN",
    "STATUS_INVALID_REQUEST",
    "FAILURE_USER_NOT_FOUND",
    "FAILURE_USER_INACTIVE",
    "FAILURE_APP_NOT_FOUND",
    "FAILURE_OWNERSHIP_CHANGED",
    "FAILURE_SCOPE_MISMATCH",
    "FAILURE_SOURCE_DIGEST_MISMATCH",
    "FAILURE_TESTS_DIGEST_MISMATCH",
    "FAILURE_SAVED_TESTS_INVALID",
    "FAILURE_EXECUTION",
    "FAILURE_RUN_NOT_FOUND",
    "FAILURE_SUBMISSION_CONFLICT",
    "FAILURE_WORKER_SHUTDOWN",
    "source_digest_for_app",
    "tests_digest_for_app",
    "start_grade",
    "get_grade_status",
    "process_pending_grades_once",
    "canvas_grade_worker_loop",
    "start_canvas_grade_worker",
    "stop_canvas_grade_worker",
]
