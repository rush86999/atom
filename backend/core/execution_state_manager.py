"""
Execution State Manager

Handles persistence of workflow execution state using SQLAlchemy async ORM.
Supports both SQLite and PostgreSQL backends.

MIGRATED: Now uses SQLAlchemy async ORM instead of raw SQL via database_manager
"""

from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
import uuid
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db_session
from core.models import WorkflowExecution
import threading

logger = logging.getLogger(__name__)

# Reserved execution-input key carrying the authenticated caller's frozen
# scope. The durable writer only persists it from the explicit, trusted
# ``identity`` argument; a copy already present in caller-supplied
# ``input_data`` is stripped. Defined here because the state manager is the
# component that stamps the persisted row and owns the durable channel.
EXECUTION_SCOPE_KEY = "_atom_execution_scope"

# Reserved execution-context key carrying the server-authored event admission
# for a deterministically reserved event receipt. Production recovery reads
# this key to claim the run. A caller-supplied copy in ``input_data`` is
# stripped; only the explicit ``admission`` argument is persisted, and it is
# never duplicated into the event input.
EVENT_ADMISSION_KEY = "_atom_event_admission"

_SCOPE_KEYS = ("tenant_id", "workspace_id", "user_id")

_EVENT_ID_PREFIX = "evt_"


def normalize_scope_token(value: Any) -> str:
    """Normalize an authoritative identity value to a JSON/pickle-safe token.

    Auth providers hand ids back as strings, ints or UUIDs. Anything else
    (an ORM object, a claim container, a boolean) is not a provable identity
    and is dropped instead of being stringified into the frozen scope.
    """
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, (str, int, uuid.UUID)):
        return str(value).strip()
    return ""


def normalize_execution_identity(
    identity: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """Normalize an explicit, trusted execution identity mapping.

    Only the scope keys are read. Missing or non-provable values are dropped;
    they are never invented from caller input.
    """
    if not isinstance(identity, dict):
        return {}
    normalized: Dict[str, str] = {}
    for key in _SCOPE_KEYS:
        token = normalize_scope_token(identity.get(key))
        if token:
            normalized[key] = token
    return normalized


def frozen_execution_identity(
    input_data: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """Return the trusted, server-frozen identity from execution inputs.

    Only the reserved scope key is read; plain caller keys named ``user_id``,
    ``owner_id`` or ``tenant_id`` in job input are never identity.
    """
    if not isinstance(input_data, dict):
        return {}
    return normalize_execution_identity(input_data.get(EXECUTION_SCOPE_KEY))


# ---------------------------------------------------------------------------
# Workflow event admissions
#
# Event runs are ordinary WorkflowExecution rows with a reserved id prefix and
# a server-owned admission record in the JSON ``context`` column.  Keeping the
# admission in ``context`` means no schema migration is needed; the prefix is
# also the fast, indexed discriminator used by the dispatcher lookup.
# ---------------------------------------------------------------------------

EVENT_EXECUTION_ID_PREFIX = "evt_"
EVENT_ADMISSION_CONTEXT_KEY = "_atom_event_admission"
EVENT_CLAIM_CONTEXT_KEY = "_atom_event_claim"

#: The dispatcher page is deliberately bounded even when a caller asks for more.
EVENT_LIST_MAX_LIMIT = 500
_EVENT_LIST_BATCH_SIZE = 100


def is_event_execution_id(execution_id: Any) -> bool:
    """Whether ``execution_id`` belongs to the reserved workflow-event space."""
    if execution_id is None:
        return False
    return str(execution_id).startswith(EVENT_EXECUTION_ID_PREFIX)


def decode_json_object(value: Any) -> Dict[str, Any]:
    """Return a persisted JSON value as a dict, tolerating every stored shape."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return {}
    return dict(value) if isinstance(value, dict) else {}


def event_admission(context: Any) -> Optional[Dict[str, Any]]:
    """Return the server-owned event admission record from a context value."""
    admission = decode_json_object(context).get(EVENT_ADMISSION_CONTEXT_KEY)
    return dict(admission) if isinstance(admission, dict) else None


def event_admission_matches(context: Any, execution_id: Any) -> bool:
    """Whether a persisted context carries the exact receipt for this row."""
    admission = event_admission(context)
    if admission is None:
        return False
    return str(admission.get("execution_id") or "") == str(execution_id or "")


def _current_event_owner(now: datetime) -> Dict[str, Any]:
    """Identify this process for a claim, without introducing a new table.

    Ownership metadata is advisory: recovery only acts on it when the normal
    ``owner_liveness`` check can prove the owner dead.  If the ownership module
    is unavailable the hostname still makes the claim auditable, while recovery
    treats the owner as UNKNOWN and leaves the row alone.
    """
    host = ""
    try:
        from core.execution_ownership import HOSTNAME
        host = HOSTNAME
    except Exception:  # noqa: BLE001 - ownership is optional for the claim itself
        import socket
        host = socket.gethostname()
    return {
        "pid": os.getpid(),
        "host": host,
        "token": str(uuid.uuid4()),
        "claimed_at": now.isoformat(),
    }


def _require_event_execution_id(execution_id: Any) -> str:
    """Return a valid ``evt_...`` row identity or reject the reservation."""
    if (
        not isinstance(execution_id, str)
        or not execution_id.startswith(_EVENT_ID_PREFIX)
        or len(execution_id) <= len(_EVENT_ID_PREFIX)
        or any(character.isspace() for character in execution_id)
    ):
        raise ValueError("execution_id must be a valid evt_ identity")
    return execution_id


def _require_event_admission(
    execution_id: str,
    admission: Any,
) -> Dict[str, Any]:
    """Copy the server-authored admission and require the exact row identity."""
    if not isinstance(admission, dict):
        raise ValueError("admission must be a dict")
    admitted_id = admission.get("execution_id")
    if not isinstance(admitted_id, str) or admitted_id != execution_id:
        raise ValueError(
            "admission.execution_id must exactly match the reserved execution id"
        )
    return dict(admission)


def _require_event_scope(
    identity: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """Require the complete normalized trusted tenant/workspace/user scope."""
    trusted = normalize_execution_identity(identity)
    if any(not trusted.get(key) for key in _SCOPE_KEYS):
        raise ValueError(
            "trusted execution scope must include tenant_id, workspace_id and user_id"
        )
    return trusted


def _validate_existing_reservation(
    existing: Dict[str, Any],
    *,
    execution_id: str,
    workflow_id: str,
    trusted: Dict[str, str],
    receipt: Dict[str, Any],
    stored_receipt: Optional[Dict[str, Any]],
) -> None:
    """Reject a duplicate row that does not describe the same reservation.

    A collision is only an idempotent replay when the stored row is the same
    workflow, carries exactly the requested trusted scope and receipt, and its
    context names this same event admission. The winning event payload and
    subscription are intentionally not compared: the first writer owns them.
    """
    if existing.get("workflow_id") != workflow_id:
        raise ValueError(
            f"Reservation collision for {execution_id}: stored workflow "
            "does not match the requested workflow"
        )

    stored_scope = frozen_execution_identity(existing.get("input_data"))
    if stored_scope != trusted:
        raise ValueError(
            f"Reservation collision for {execution_id}: stored trusted scope "
            "does not match the requested trusted scope"
        )

    if stored_receipt != receipt:
        raise ValueError(
            f"Reservation collision for {execution_id}: stored receipt "
            "does not match the requested receipt"
        )

    stored_context = existing.get("context")
    stored_admission = (
        stored_context.get(EVENT_ADMISSION_KEY)
        if isinstance(stored_context, dict)
        else None
    )
    stored_admission_id = (
        stored_admission.get("execution_id")
        if isinstance(stored_admission, dict)
        else None
    )
    if stored_admission_id != execution_id:
        raise ValueError(
            f"Reservation collision for {execution_id}: stored event admission "
            "id does not match the requested admission id"
        )


class ExecutionStateManager:
    """
    Manages the state of workflow executions.
    Persists state to database to allow resuming after restarts.

    Migrated to use SQLAlchemy async ORM instead of raw SQL.
    """

    async def create_execution(
        self,
        workflow_id: str,
        input_data: Dict[str, Any],
        *,
        identity: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Initialize a new execution state.

        ``identity`` is the explicit, trusted scope supplied by the caller that
        authenticated the run (``WorkflowEngine.start_workflow``). It is the
        only source of durable ownership; a reserved marker already present in
        ``input_data`` is untrusted and stripped, so a direct caller cannot
        stamp a receipt by crafting job input. The normalized trusted scope is
        kept in the persisted inputs for the engine (and every later resume).

        The row's ``user_id``/``owner_id``/``tenant_id`` are stamped only when
        the trusted scope proves an actor together with both tenant and
        workspace. A trusted ownerless scope (a legacy schedule with no actor)
        keeps its tenant/workspace in the inputs but leaves all receipt columns
        NULL: stamping the tenant alone would turn it into tenant-wide
        visibility in the read filter.
        """
        execution_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        durable_inputs = dict(input_data) if isinstance(input_data, dict) else {}
        durable_inputs.pop(EXECUTION_SCOPE_KEY, None)
        trusted = normalize_execution_identity(identity)
        if trusted:
            durable_inputs[EXECUTION_SCOPE_KEY] = trusted

        actor_user_id = trusted.get("user_id") or ""
        tenant_id = trusted.get("tenant_id") or ""
        workspace_id = trusted.get("workspace_id") or ""
        if actor_user_id and tenant_id and workspace_id:
            receipt = {
                "user_id": actor_user_id,
                "owner_id": actor_user_id,
                "tenant_id": tenant_id,
            }
        else:
            receipt = {"user_id": None, "owner_id": None, "tenant_id": None}

        async with get_async_db_session() as db:
            execution = WorkflowExecution(
                execution_id=execution_id,
                workflow_id=workflow_id,
                status="PENDING",
                input_data=json.dumps(durable_inputs),
                steps=json.dumps({}),  # steps
                outputs=json.dumps({}),  # outputs
                context=json.dumps({}),  # context
                version=1,  # initial version
                created_at=now,
                updated_at=now,
                **receipt,
            )

            db.add(execution)
            await db.commit()

        logger.debug(f"Created execution {execution_id} for workflow {workflow_id}")
        return execution_id

    async def reserve_event_execution(
        self,
        workflow_id: str,
        input_data: Dict[str, Any],
        *,
        execution_id: str,
        identity: Optional[Dict[str, Any]] = None,
        admission: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], bool]:
        """Atomically reserve one durable execution row for an event receipt.

        The caller owns the deterministic ``evt_...`` execution id, derived
        from the stable logical receipt key, so editing a subscription does
        not create a second execution for the same receipt. The primary key
        insert is the uniqueness test: the first writer persists its complete
        event input and server-authored admission context, and every later
        writer receives that same persisted state unchanged with
        ``created=False``.

        The admission is stored only in the row ``context`` because production
        recovery reads
        ``WorkflowExecution.context["_atom_event_admission"]["execution_id"]``
        to claim the run. The event input is kept separately and never carries
        a copy of the admission. A duplicate is only treated as an
        already-reserved receipt when the stored workflow, trusted scope,
        receipt columns and admission id all describe this same reservation.
        No queuing or execution is performed here; this method only reserves
        the row.
        """
        execution_id = _require_event_execution_id(execution_id)
        durable_admission = _require_event_admission(execution_id, admission)
        durable_admission["execution_id"] = execution_id
        trusted = _require_event_scope(identity)

        now = datetime.now(timezone.utc)

        durable_inputs = dict(input_data) if isinstance(input_data, dict) else {}
        durable_inputs.pop(EXECUTION_SCOPE_KEY, None)
        durable_inputs.pop(EVENT_ADMISSION_KEY, None)
        durable_inputs[EXECUTION_SCOPE_KEY] = trusted

        durable_context = {EVENT_ADMISSION_KEY: durable_admission}

        actor_user_id = trusted["user_id"]
        tenant_id = trusted["tenant_id"]
        receipt = {
            "user_id": actor_user_id,
            "owner_id": actor_user_id,
            "tenant_id": tenant_id,
        }

        try:
            async with get_async_db_session() as db:
                await db.execute(
                    insert(WorkflowExecution).values(
                        execution_id=execution_id,
                        workflow_id=workflow_id,
                        status="PENDING",
                        input_data=json.dumps(durable_inputs),
                        steps=json.dumps({}),
                        outputs=json.dumps({}),
                        context=json.dumps(durable_context),
                        version=1,
                        created_at=now,
                        updated_at=now,
                        **receipt,
                    )
                )
                await db.commit()
        except IntegrityError:
            existing = await self.get_execution_state(execution_id)
            if existing is None:
                raise
            stored_receipt = await self._get_execution_receipt(execution_id)
            if stored_receipt is None:
                raise
            _validate_existing_reservation(
                existing,
                execution_id=execution_id,
                workflow_id=workflow_id,
                trusted=trusted,
                receipt=receipt,
                stored_receipt=stored_receipt,
            )
            return existing, False

        state = await self.get_execution_state(execution_id)
        if state is None:
            raise RuntimeError(
                f"Reserved execution {execution_id} could not be read back"
            )
        return state, True

    async def _get_execution_receipt(
        self, execution_id: str
    ) -> Optional[Dict[str, Any]]:
        """Read only the durable receipt columns for a duplicate check."""
        async with get_async_db_session() as db:
            result = await db.execute(
                select(
                    WorkflowExecution.user_id,
                    WorkflowExecution.owner_id,
                    WorkflowExecution.tenant_id,
                ).where(WorkflowExecution.execution_id == execution_id)
            )
            row = result.one_or_none()

        if row is None:
            return None
        return {
            "user_id": row.user_id,
            "owner_id": row.owner_id,
            "tenant_id": row.tenant_id,
        }

    async def update_step_status(
        self,
        execution_id: str,
        step_id: str,
        status: str,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """Update the status and output of a specific step"""
        state = await self.get_execution_state(execution_id)
        if not state:
            raise ValueError(f"Execution {execution_id} not found")

        # Update steps map
        steps = state["steps"]
        if step_id not in steps:
            steps[step_id] = {
                "id": step_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            }

        step_state = steps[step_id]
        step_state["status"] = status
        step_state["updated_at"] = datetime.now(timezone.utc).isoformat()

        if output is not None:
            step_state["output"] = output
            state["outputs"][step_id] = output

        if error is not None:
            step_state["error"] = error

        # Update DB with version increment
        async with get_async_db_session() as db:
            await db.execute(
                update(WorkflowExecution)
                .where(WorkflowExecution.execution_id == execution_id)
                .values(
                    steps=json.dumps(steps),
                    outputs=json.dumps(state["outputs"]),
                    version=WorkflowExecution.version + 1,
                    updated_at=datetime.now(timezone.utc)
                )
            )
            await db.commit()

    async def update_execution_status(self, execution_id: str, status: str, error: Optional[str] = None) -> bool:
        """Update the overall execution status and report whether it matched.

        A durable ``CANCELLED`` is authoritative over later runner writes.
        Cancellation may be accepted by a different engine instance (or by an
        API/UI surface) than the one still executing the workflow, so a late
        ``RUNNING``, ``PAUSED``, ``COMPLETED``, ``PARTIAL`` or ``FAILED`` write
        must not replace it. Repeating the cancellation itself stays allowed.
        The check is part of the SQL update so two workers cannot race between
        reading the status and writing it.

        Returns ``True`` when the conditional UPDATE matched a row. ``False``
        means the write was rejected (for example the row is already
        ``CANCELLED``): callers must not publish or announce the status change
        they attempted. Older/fake managers that return ``None`` remain
        compatible; only an explicit ``False`` is a rejection.
        """
        async with get_async_db_session() as db:
            statement = update(WorkflowExecution).where(
                WorkflowExecution.execution_id == execution_id
            )
            if str(status or "").strip().upper() != "CANCELLED":
                statement = statement.where(
                    func.coalesce(
                        func.upper(WorkflowExecution.status), ""
                    ) != "CANCELLED"
                )
            result = await db.execute(
                statement.values(
                    status=status,
                    error=error,
                    version=WorkflowExecution.version + 1,
                    updated_at=datetime.now(timezone.utc)
                )
            )
            await db.commit()
            rowcount = getattr(result, "rowcount", 0)
            return bool(rowcount and rowcount > 0)

    async def claim_event_execution(
        self,
        execution_id: str,
        owner: Optional[Dict[str, Any]] = None,
        *,
        now: Optional[datetime] = None,
    ) -> bool:
        """Atomically claim one admitted event run by moving PENDING -> RUNNING.

        This is deliberately separate from :meth:`update_execution_status`:
        the manual/resume write is a general status assignment, while an event
        dispatch claim must be a single-winner compare-and-set.  Exactly one
        caller can observe ``True`` for a given PENDING row; every later or
        concurrent caller observes ``False`` and performs no work.

        Only the reserved ``evt_`` id space is eligible, and the persisted
        context must carry the exact server-owned admission receipt for this
        execution id.  Manual/cron rows (and evt_ rows with a missing or
        mismatched receipt) are never touched here.

        The winner records lightweight ownership in ``context``.  Because that
        rewrites a field read before the update, the CAS includes the observed
        version (and the observed context when it is stored as text) so a
        concurrent context writer makes the claim lose instead of being
        overwritten.  Nothing about an interrupted RUNNING run is replayed here.
        """
        execution_id = str(execution_id or "")
        if not is_event_execution_id(execution_id):
            return False

        timestamp = now or datetime.now(timezone.utc)
        claim_owner = owner
        if claim_owner is None:
            claim_owner = _current_event_owner(timestamp)
        if not isinstance(claim_owner, dict) or not claim_owner:
            return False

        async with get_async_db_session() as db:
            stored = await db.execute(
                select(
                    WorkflowExecution.execution_id,
                    WorkflowExecution.context,
                    WorkflowExecution.version,
                ).where(WorkflowExecution.execution_id == execution_id)
            )
            observed = stored.first()
            if observed is None:
                return False
            observed_id, observed_context, observed_version = observed

            # The receipt is the persisted admission record, not the id prefix
            # or anything supplied by this caller.
            if str(observed_id) != execution_id:
                return False
            if not event_admission_matches(observed_context, execution_id):
                return False

            context = decode_json_object(observed_context)
            context[EVENT_CLAIM_CONTEXT_KEY] = dict(claim_owner)

            conditions = [
                WorkflowExecution.execution_id == execution_id,
                func.upper(WorkflowExecution.status) == "PENDING",
                WorkflowExecution.version == observed_version,
            ]
            if observed_context is None:
                conditions.append(WorkflowExecution.context.is_(None))
            elif not isinstance(observed_context, (dict, list)):
                conditions.append(WorkflowExecution.context == observed_context)

            result = await db.execute(
                update(WorkflowExecution)
                .where(*conditions)
                .values(
                    status="RUNNING",
                    error=None,
                    version=WorkflowExecution.version + 1,
                    updated_at=timestamp,
                    context=json.dumps(context),
                )
            )
            await db.commit()
            rowcount = getattr(result, "rowcount", 0)
            return bool(rowcount and rowcount > 0)

    async def refuse_pending_event_execution(
        self,
        execution_id: str,
        *,
        expected_version: int,
        failure_code: str,
    ) -> bool:
        """Refuse only the observed PENDING event, preserving peer winners.

        A durable admission receipt and exact observed version are required.
        Temporary preflight failures must not call this method. No RUNNING,
        cancelled or newer row can be changed by a stale refusal.
        """
        if (not is_event_execution_id(execution_id)
                or type(expected_version) is not int or expected_version < 1
                or not isinstance(failure_code, str) or not failure_code.strip()):
            return False
        async with get_async_db_session() as db:
            result = await db.execute(select(
                WorkflowExecution.context, WorkflowExecution.version,
            ).where(WorkflowExecution.execution_id == execution_id))
            row = result.first()
            if row is None:
                return False
            context, version = row
            if version != expected_version or not event_admission_matches(context, execution_id):
                return False
            conditions = [
                WorkflowExecution.execution_id == execution_id,
                func.upper(WorkflowExecution.status) == "PENDING",
                WorkflowExecution.version == expected_version,
            ]
            if context is None:
                conditions.append(WorkflowExecution.context.is_(None))
            elif not isinstance(context, (dict, list)):
                conditions.append(WorkflowExecution.context == context)
            timestamp = datetime.now(timezone.utc)
            updated = await db.execute(update(WorkflowExecution).where(*conditions).values(
                status="FAILED", error=failure_code,
                version=WorkflowExecution.version + 1,
                updated_at=timestamp, completed_at=timestamp,
            ))
            await db.commit()
            return bool(getattr(updated, "rowcount", 0))

    async def list_admitted_event_executions(
        self,
        limit: int = 100,
        *,
        after_execution_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return admitted, unclaimed event runs using bounded keyset paging.

        A run is eligible only when all of the following hold:

        * ``execution_id`` starts with the reserved ``evt_`` prefix;
        * its durable status is still ``PENDING`` (nothing has claimed it);
        * its persisted ``context`` contains the server-owned
          ``_atom_event_admission`` record; and
        * that record names this exact ``execution_id``.

        Prefix and status are the only SQL filters.  Admission equality is
        parsed from the persisted JSON in Python rather than matched as a
        substring, because a malformed or mismatched admission can contain a
        nested ``execution_id`` that happens to equal a later valid row.  A
        plain ``LIMIT`` after such a prefilter would let those rows starve the
        valid one forever.

        Paging is therefore a keyset walk ordered by the unique execution id.
        Every batch advances the cursor even when rows are rejected, so a page
        full of invalid receipts cannot stall the scan.  The requested limit is
        capped, and each SQL page is independently bounded.

        ``after_execution_id`` continues a bounded scan after the last
        returned opaque id. A polling consumer can preserve this cursor across
        ticks and wrap after exhaustion, so temporarily deferred first pages
        do not permanently hide later runnable events. Omission retains the
        existing first-page behavior.

        This method only looks; it never claims, requeues or replays anything.
        A separate dispatcher is responsible for calling
        :meth:`claim_event_execution` for each returned id.
        """
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 100
        if limit <= 0:
            return []
        limit = min(limit, EVENT_LIST_MAX_LIMIT)
        batch_size = min(max(limit, 1), _EVENT_LIST_BATCH_SIZE)

        runs: List[Dict[str, Any]] = []
        cursor_id: Optional[str] = after_execution_id

        async with get_async_db_session() as db:
            while len(runs) < limit:
                statement = select(WorkflowExecution).where(
                    func.substr(
                        WorkflowExecution.execution_id,
                        1,
                        len(EVENT_EXECUTION_ID_PREFIX),
                    ) == EVENT_EXECUTION_ID_PREFIX,
                    func.upper(WorkflowExecution.status) == "PENDING",
                )
                if cursor_id is not None:
                    statement = statement.where(
                        WorkflowExecution.execution_id > cursor_id
                    )
                statement = (
                    statement.order_by(WorkflowExecution.execution_id.asc())
                    .limit(batch_size)
                )

                result = await db.execute(statement)
                rows = result.scalars().all()
                if not rows:
                    break

                for row in rows:
                    execution_id = getattr(row, "execution_id", None)
                    cursor_id = str(execution_id)
                    if not event_admission_matches(
                        getattr(row, "context", None), execution_id
                    ):
                        continue

                    context = decode_json_object(
                        getattr(row, "context", None)
                    )
                    admission = context[EVENT_ADMISSION_CONTEXT_KEY]
                    created_at = getattr(row, "created_at", None)
                    updated_at = getattr(row, "updated_at", None)
                    completed_at = getattr(row, "completed_at", None)
                    runs.append({
                        "execution_id": execution_id,
                        "workflow_id": getattr(row, "workflow_id", None),
                        "status": getattr(row, "status", None),
                        "version": getattr(row, "version", None),
                        "input_data": decode_json_object(
                            getattr(row, "input_data", None)
                        ),
                        "steps": decode_json_object(
                            getattr(row, "steps", None)
                        ),
                        "outputs": decode_json_object(
                            getattr(row, "outputs", None)
                        ),
                        "context": context,
                        "created_at": (
                            created_at.isoformat() if created_at else None
                        ),
                        "updated_at": (
                            updated_at.isoformat() if updated_at else None
                        ),
                        "completed_at": (
                            completed_at.isoformat() if completed_at else None
                        ),
                        "error": getattr(row, "error", None),
                        "admission": dict(admission),
                    })
                    if len(runs) >= limit:
                        break

                # A short page proves the scan reached the end; a full page
                # always made forward progress through the cursor above.
                if len(rows) < batch_size:
                    break

        return runs

    async def update_execution_inputs(self, execution_id: str, new_inputs: Dict[str, Any]):
        """Update execution inputs (e.g. for resume)"""
        state = await self.get_execution_state(execution_id)
        if not state:
            raise ValueError(f"Execution {execution_id} not found")

        current_inputs = state["input_data"]
        current_inputs.update(new_inputs)

        async with get_async_db_session() as db:
            await db.execute(
                update(WorkflowExecution)
                .where(WorkflowExecution.execution_id == execution_id)
                .values(
                    input_data=json.dumps(current_inputs),
                    version=WorkflowExecution.version + 1,
                    updated_at=datetime.now(timezone.utc)
                )
            )
            await db.commit()

    async def get_execution_state(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve execution state from storage"""
        async with get_async_db_session() as db:
            result = await db.execute(
                select(WorkflowExecution).where(WorkflowExecution.execution_id == execution_id)
            )
            execution = result.scalar_one_or_none()

            if not execution:
                return None

            # Deserialize JSON fields
            try:
                return {
                    "execution_id": execution.execution_id,
                    "workflow_id": execution.workflow_id,
                    "status": execution.status,
                    "version": execution.version,
                    "input_data": json.loads(execution.input_data) if execution.input_data else {},
                    "steps": json.loads(execution.steps) if execution.steps else {},
                    "outputs": json.loads(execution.outputs) if execution.outputs else {},
                    "context": json.loads(execution.context) if execution.context else {},
                    "created_at": execution.created_at.isoformat() if execution.created_at else None,
                    "updated_at": execution.updated_at.isoformat() if execution.updated_at else None,
                    "error": execution.error
                }
            except Exception as e:
                logger.error(f"Error deserializing execution state {execution_id}: {e}")
                return None

    async def get_step_output(self, execution_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        """Get the output of a specific step"""
        state = await self.get_execution_state(execution_id)
        if not state:
            return None
        return state["outputs"].get(step_id)


# Global instance
_state_manager = None
_state_manager_lock = __import__('threading').Lock()
def get_state_manager() -> ExecutionStateManager:
    global _state_manager
    if _state_manager is None:
        with _state_manager_lock:
            if _state_manager is None:
                _state_manager = ExecutionStateManager()
    return _state_manager
