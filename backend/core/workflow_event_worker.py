"""Drain durable admitted events through the concrete existing runtime APIs."""
from __future__ import annotations
import asyncio
import copy
import json
import logging
from typing import Any
from core.execution_state_manager import frozen_execution_identity
from core.workflow_engine import get_workflow_engine
from core.workflow_event_admission import payload_digest

logger = logging.getLogger(__name__)
FAILURE_WORKFLOW_INVALID = "workflow_invalid"
FAILURE_EXECUTION_BLOCKED = "workflow_execution_blocked"
FAILURE_WORKFLOW_NOT_FOUND = "workflow_not_found"
FAILURE_WORKFLOW_CHANGED = "workflow_definition_changed"
FAILURE_AUTHORIZATION_REVOKED = "workflow_authorization_revoked"

class _PermanentRefusal(Exception):
    def __init__(self, failure_code, detail=None):
        self.failure_code = failure_code
        super().__init__(failure_code)

def _open_db():
    from core.database import get_db_session

    return get_db_session()

def _load_current_actor(db: Any, user_id: str) -> Any:
    from core.models import User

    return db.query(User).filter(User.id == str(user_id)).first()

def _load_current_workflow(db: Any, workflow_id: str, actor: Any) -> Any:
    from core import workflow_endpoints

    # A corrupt/unreadable catalog is temporary unavailability, not proof
    # that an admitted definition disappeared. Do not use the tolerant UI
    # reader, which deliberately converts that failure into an empty list.
    workflow = None
    for candidate in workflow_endpoints.load_workflows_strict():
        if candidate.get("id") == workflow_id or candidate.get("workflow_id") == workflow_id:
            if workflow_endpoints._is_visible_to_user(candidate, actor):
                workflow = candidate
            break
    if workflow is None:
        # Same template fallback as the normal execute route.
        workflow = workflow_endpoints._load_template_definition(
            str(workflow_id), actor, db)
    return workflow

def _actor_has_run_permission(actor: Any) -> bool:
    from core.rbac_service import Permission, RBACService

    return bool(RBACService.check_permission(actor, Permission.WORKFLOW_RUN))

def _actor_is_active(actor: Any) -> bool:
    if getattr(actor, "is_active", True) is False:
        return False
    status = str(getattr(actor, "status", "") or "").lower()
    return status in ("", "active")

async def _validate_definition(
    db: Any, actor: Any, workflow_id: str, workflow: Any
) -> None:
    """Reuse the normal execute-route checks for the current definition.

    The caller's frozen snapshot is deliberately not replaced here. A copy is
    validated so caching/linearization cannot rewrite the snapshot the engine
    retained for effects.
    """
    if not isinstance(workflow, dict):
        raise _PermanentRefusal(
            FAILURE_WORKFLOW_INVALID, "workflow definition is not a mapping")

    from core import workflow_endpoints

    definition = copy.deepcopy(workflow)
    if definition.get("enabled") is False:
        raise _PermanentRefusal(
            FAILURE_EXECUTION_BLOCKED, "workflow is disabled")

    try:
        workflow_endpoints._validate_workflow_dag(definition)
        steps = workflow_endpoints._resolve_workflow_steps(definition)
    except Exception as exc:  # noqa: BLE001 - malformed definition is final
        raise _PermanentRefusal(FAILURE_WORKFLOW_INVALID, exc) from exc

    deployment = definition.get("deployment")
    if isinstance(deployment, dict) and deployment.get(
            "canonical_workflow_id"):
        from core.workflow_blueprint_service import load_blueprint

        scope = workflow_endpoints._caller_scope(actor)
        view = load_blueprint(
            db,
            workflow_id=str(workflow_id),
            tenant_id=scope["tenant_id"],
            workspace_id=scope["workspace_id"],
        )
        if view is None:
            raise _PermanentRefusal(
                FAILURE_WORKFLOW_NOT_FOUND,
                "canonical workflow blueprint is unavailable",
            )
        stored_digest = str(view.get("definition_digest") or "")
        try:
            recomputed_digest = (
                workflow_endpoints._recompute_definition_digest(view))
        except Exception as exc:  # noqa: BLE001
            raise _PermanentRefusal(FAILURE_WORKFLOW_INVALID, exc) from exc
        if not stored_digest or recomputed_digest != stored_digest:
            raise _PermanentRefusal(
                FAILURE_WORKFLOW_CHANGED,
                "canonical blueprint no longer matches its definition digest",
            )
        if str(deployment.get("definition_digest")) != stored_digest:
            raise _PermanentRefusal(
                FAILURE_WORKFLOW_CHANGED,
                "deployed reference no longer matches the canonical blueprint",
            )
        if not view.get("execution_ready", True):
            raise _PermanentRefusal(
                FAILURE_EXECUTION_BLOCKED,
                list(view.get("execution_blockers") or []),
            )
        steps = list(view.get("steps") or [])
    elif definition.get("_template_catalog"):
        from core.workflow_template_preflight import preflight_template_steps

        blockers = preflight_template_steps(
            steps, target="workflow_engine")
        if blockers:
            raise _PermanentRefusal(FAILURE_EXECUTION_BLOCKED, blockers)

    try:
        await workflow_endpoints.require_workflow_executor(actor, steps)
    except Exception as exc:
        if getattr(exc, "status_code", None) in (401, 403, 404, 409, 422):
            raise _PermanentRefusal(FAILURE_AUTHORIZATION_REVOKED) from exc
        raise

async def dispatch_preflight(execution_id, state, workflow):
    """Recheck current owner and current definition; dispatch only frozen work."""
    from core import workflow_endpoints
    identity = frozen_execution_identity(state.get("input_data"))
    admission = state.get("context", {}).get("_atom_event_admission", {})
    if (any(not identity.get(k) for k in ("user_id", "tenant_id", "workspace_id"))
            or admission.get("execution_id") != execution_id
            or admission.get("workflow_id") != state.get("workflow_id")
            or any(admission.get(a) != identity.get(i) for a, i in (
                ("owner_id", "user_id"), ("tenant_id", "tenant_id"), ("workspace_id", "workspace_id")))):
        raise _PermanentRefusal("frozen_scope_missing")
    with _open_db() as db:
        actor = _load_current_actor(db, identity["user_id"])
        if actor is None or not _actor_is_active(actor):
            raise _PermanentRefusal("owner_unavailable")
        if workflow_endpoints._caller_scope(actor) != identity:
            raise _PermanentRefusal("scope_mismatch")
        if not _actor_has_run_permission(actor):
            raise _PermanentRefusal(FAILURE_AUTHORIZATION_REVOKED)
        from core.connection_service import ConnectionService
        if ConnectionService.get_scoped_connection_metadata(
                db, user_id=identity["user_id"], tenant_id=getattr(actor, "tenant_id", None),
                workspace_id=getattr(actor, "workspace_id", None),
                connection_id=admission.get("connection_id"), integration_id=admission.get("source")) is None:
            raise _PermanentRefusal("source_connection_unavailable")
        current = _load_current_workflow(db, state["workflow_id"], actor)
        if current is None:
            raise _PermanentRefusal(FAILURE_WORKFLOW_NOT_FOUND)
        snapshot = admission.get("workflow_snapshot")
        if not isinstance(snapshot, dict) or payload_digest(current) != payload_digest(snapshot):
            raise _PermanentRefusal(FAILURE_WORKFLOW_CHANGED)
        await _validate_definition(db, actor, state["workflow_id"], current)
    return True


async def process_pending_event_executions_once(limit=100, *, engine=None, preflight=None):
    engine = engine if engine is not None else get_workflow_engine()
    preflight = preflight if preflight is not None else dispatch_preflight
    manager = engine.state_manager
    cursor = getattr(manager, "_pending_event_scan_cursor", None)
    states = await manager.list_admitted_event_executions(
        limit=limit, after_execution_id=cursor)
    if not states:
        manager._pending_event_scan_cursor = None
        return 0
    processed = 0
    for state in states:
        execution_id = state["execution_id"]
        manager._pending_event_scan_cursor = execution_id
        refusal = None
        async def checked_preflight(run_id, persisted, frozen):
            nonlocal refusal
            try:
                return await preflight(run_id, persisted, frozen)
            except _PermanentRefusal as exc:
                refusal = exc.failure_code
                return False
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Event preflight deferred (%s)", type(exc).__name__)
                return False
        try:
            launched = await engine.launch_reserved_event_execution(
                execution_id, state, checked_preflight)
            if launched:
                processed += 1
            elif refusal is not None:
                await manager.refuse_pending_event_execution(
                    execution_id, expected_version=state["version"], failure_code=refusal)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Event dispatch deferred (%s)", type(exc).__name__)
    return processed


SOURCE_LEASE_BATCH_LIMIT = 25
SOURCE_LEASE_SOURCE_TIMEOUT_SECONDS = 15.0
SOURCE_LEASE_INTERVAL_SECONDS = 60.0
EVENT_POLL_INTERVAL_SECONDS = 2.0


def _source_reference(row):
    from core.workflow_event_source_registration import _key
    try:
        document = json.loads(row.setting_value)
        if (not isinstance(document, dict) or document.get('schema') != 'workflow.event_source.v1'
                or document.get('phase') != 'registered' or document.get('enabled') is not True
                or not isinstance(document.get('identity'), dict)
                or document['identity'].get('tenant_id') != row.tenant_id
                or any(not isinstance(document.get(k), str) or not document[k].strip()
                       for k in ('connection_id', 'source', 'operation_id'))
                or row.setting_key != _key(document['connection_id'], document['source'])):
            return None
        return document['connection_id'], document['operation_id'], document['source']
    except (ValueError, TypeError, KeyError):
        return None


async def maintain_source_leases_once(after_id=None, limit=SOURCE_LEASE_BATCH_LIMIT,
                                     db_factory=None, adapter_factory=None):
    """One bounded keyset page; close the listing transaction before provider I/O.

    Every listed row advances the cursor, including unreadable/disabled/refused
    entries. Each source has its own timeout so a slow first source cannot
    discard completed page progress. The operation ledger owns uncertain PATCH.
    """
    from core.models import TenantSetting
    from core.workflow_event_source_renewal import renew_source
    from core.workflow_event_source_adapters import source_adapter
    if db_factory is None:
        from core.database import get_db_session
        db_factory = get_db_session
    adapter_factory = source_adapter if adapter_factory is None else adapter_factory
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Invalid source maintenance page size')
    with db_factory() as db:
        query = db.query(TenantSetting).filter(TenantSetting.setting_key.startswith(
            'workflow_event_source:', autoescape=True))
        if after_id is not None:
            query = query.filter(TenantSetting.id > after_id)
        rows = query.order_by(TenantSetting.id).limit(limit).all()
        cursor = rows[-1].id if len(rows) == limit else None
        references = [ref for ref in (_source_reference(row) for row in rows) if ref is not None]
        scanned = len(rows)
    attempted = 0
    for connection_id, operation_id, source in references:
        try:
            adapter = adapter_factory(source)
            attempted += 1
            await asyncio.wait_for(renew_source(connection_id, operation_id, adapter,
                db_factory=db_factory), timeout=SOURCE_LEASE_SOURCE_TIMEOUT_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning('Source lease maintenance deferred (%s)', type(exc).__name__)
    return {'scanned': scanned, 'attempted': attempted, 'after_id': cursor}


_worker_task = None
_worker_stop = None
_maintenance_task = None


async def workflow_event_worker_loop():
    # One lifespan owner, with independent bounded maintenance work so source
    # I/O cannot hold up the existing PENDING execution drain.
    global _maintenance_task
    cursor = None
    next_maintenance = 0.0
    loop = asyncio.get_running_loop()
    try:
        while not _worker_stop.is_set():
            if _maintenance_task is not None and _maintenance_task.done():
                try:
                    cursor = _maintenance_task.result()['after_id']
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    logger.warning('Source maintenance page deferred (%s)', type(exc).__name__)
                _maintenance_task = None
                next_maintenance = loop.time() + SOURCE_LEASE_INTERVAL_SECONDS
            try:
                await process_pending_event_executions_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning('Event poll deferred (%s)', type(exc).__name__)
            if (not _worker_stop.is_set() and _maintenance_task is None
                    and loop.time() >= next_maintenance):
                _maintenance_task = asyncio.create_task(maintain_source_leases_once(after_id=cursor))
            try:
                await asyncio.wait_for(_worker_stop.wait(), timeout=EVENT_POLL_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                pass
    finally:
        owned = _maintenance_task
        _maintenance_task = None
        if owned is not None:
            if not owned.done():
                owned.cancel()
            try:
                await owned
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.warning('Source maintenance stopped (%s)', type(exc).__name__)


def start_workflow_event_worker():
    global _worker_task, _worker_stop
    if _worker_task is not None and not _worker_task.done():
        return False
    if _maintenance_task is not None and not _maintenance_task.done():
        return False
    _worker_stop = asyncio.Event()
    _worker_task = asyncio.create_task(workflow_event_worker_loop())
    return True


async def stop_workflow_event_worker():
    global _worker_task
    if _worker_stop is not None:
        _worker_stop.set()
    task = _worker_task
    if task is None or task is asyncio.current_task():
        return
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    finally:
        _worker_task = None
