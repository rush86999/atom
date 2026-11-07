"""Registered ``radio.create_thread`` producer and authority material.

The predecessor action called ``radio_service.create_thread`` and returned the
raw success envelope.  It did not re-read the exact ``AgentThread`` row, did not
check the creator/member ``AgentRegistry`` scope, and bound no operation
identity, so the shared Oracle could only report the effect as unverified.

This module keeps the same service/model persistence and adds only what the
existing claim/Oracle layer needs:

* a canonical authorized thread payload (server-owned creator, name, normalized
  roster, scope, tenant/workspace scope);
* pre-effect authority checks against real ``AgentRegistry`` rows using the
  single-tenant null/``default`` compatibility already used by
  ``AgentGovernanceService._workspace_scope_condition``;
* an exact by-id fresh-session re-read after commit;
* a durable operation-id binding in thread metadata so same-operation replay
  can locate the original row without creating a second thread.

The row id locates the thread; it does not supply authority.  The shared
``postcondition_verifiers`` layer re-reads the row and the current authority
from a fresh session.

Ported from the accepted radio send work at
``3a188840d:backend/core/agent_radio/radio_mutations.py``:
``_text``, ``read_thread`` (by-id fresh read) and the durable-receipt
projector/matcher shape.  These are unchanged general helpers; no send-message
code or receipt state is duplicated.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Mapping, Optional, Sequence

from core.agent_radio import radio_service
from core.agent_radio.radio_service import RadioError

#: Material the Oracle compares.  The thread id locates the row; it is not
#: caller-authorized material.  ``workspace_id`` is authority context, not a
#: column on AgentThread, so it is compared separately.
THREAD_MATERIAL_FIELDS = (
    "name",
    "created_by_agent_id",
    "member_agent_ids",
    "scope_hint",
    "tenant_id",
)

SCOPE_HINTS = ("fleet", "task", "manual")

#: Statuses that are explicitly not usable for a new coordination thread.
DISABLED_AGENT_STATUSES = frozenset({
    "paused", "stopped", "deprecated", "deleted",
})

#: Mirrors the existing radio action tier floor.
TIER_RANK = {"student": 0, "intern": 1, "supervised": 2, "autonomous": 3}

#: Single-tenant / personal scope aliases.  The schema keeps workspace_id and
#: tenant_id distinct, but both treat NULL and the literal "default" as the
#: personal scope.
_PERSONAL_SCOPE = ("", "default")


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _norm_scope(value: Any) -> str:
    return _text(value).strip()


def _scope_compatible(requested: Any, actual: Any) -> bool:
    """Single-tenant scope compatibility.

    A request scoped to the personal ``default`` (or no workspace/tenant) may
    see rows with NULL or ``default``.  A request scoped to a concrete id must
    match that id exactly.  This is the same visibility rule already used by
    ``AgentGovernanceService._workspace_scope_condition``; it is not a new
    multi-tenant product gate.
    """
    requested_text = _norm_scope(requested)
    actual_text = _norm_scope(actual)
    if requested_text in _PERSONAL_SCOPE:
        return actual_text in _PERSONAL_SCOPE
    return actual_text == requested_text


def _normalized_roster(creator_id: str, raw_members: Any) -> List[str]:
    creator = _text(creator_id).strip()
    members: List[str] = []
    if isinstance(raw_members, (list, tuple, set)):
        for item in raw_members:
            text = _text(item).strip()
            if text and text not in members:
                members.append(text)
    if creator:
        if creator in members:
            members.remove(creator)
        members.insert(0, creator)
    return members


def thread_payload(
    arguments: Mapping[str, Any] | None,
    *,
    agent_id: Any,
    workspace_id: Any = "",
    tenant_id: Any = "",
) -> Dict[str, Any]:
    """The exact authorized thread material and request digest input.

    The creator is server-owned (dispatch context), never a business argument.
    The roster is normalized exactly as ``radio_service.create_thread`` does:
    creator first, de-duplicated, empty ids dropped.
    """
    args = arguments if isinstance(arguments, Mapping) else {}
    creator = _text(agent_id).strip()
    return {
        "name": _text(args.get("name")).strip(),
        "created_by_agent_id": creator,
        "member_agent_ids": _normalized_roster(
            creator, args.get("member_agent_ids")),
        "scope_hint": (
            _text(args.get("scope_hint")).strip().lower() or "manual"),
        # The server-owned identity uses the personal "default" alias when
        # the context carries no tenant/workspace.  Normalize the frozen
        # material the same way; the AgentThread row may still store NULL,
        # which the compatibility comparison treats as the same personal scope.
        "tenant_id": _norm_scope(tenant_id) or "default",
        "workspace_id": _norm_scope(workspace_id) or "default",
    }


def _payload_digest(payload: Mapping[str, Any]) -> str:
    from core.task_lifecycle import _approval_payload_hash

    return _approval_payload_hash(dict(payload))


def _load_agent(db, agent_id: str):
    from core.models import AgentRegistry

    return db.query(AgentRegistry).filter(
        AgentRegistry.id == str(agent_id)).first()


def _agent_problems(
    agent: Any,
    *,
    role: str,
    workspace_id: Any,
    tenant_id: Any,
    require_intern: bool = False,
    context_tier: str = "",
    allow_unknown_tier: bool = False,
) -> List[str]:
    """Current authority/scope problems for one AgentRegistry row.

    Single-tenant rules only: the row must exist, must not be explicitly
    disabled, and its workspace/tenant must be compatible with the request.
    No new role/SaaS gate is introduced.  The creator additionally keeps the
    existing INTERN+ action floor; members only need to be active recipients.
    """
    if agent is None:
        return [f"{role} agent is not registered"]

    problems: List[str] = []
    if getattr(agent, "enabled", True) is False:
        problems.append(f"{role} agent is disabled")

    status = _text(getattr(agent, "status", None)).strip().lower()
    if status in DISABLED_AGENT_STATUSES:
        problems.append(f"{role} agent is {status}")

    if not _scope_compatible(workspace_id, getattr(agent, "workspace_id", None)):
        problems.append(f"{role} agent belongs to another workspace")
    if not _scope_compatible(tenant_id, getattr(agent, "tenant_id", None)):
        problems.append(f"{role} agent belongs to another tenant")

    if require_intern:
        tier = status if status in TIER_RANK else _text(context_tier).strip().lower()
        if tier in TIER_RANK:
            if TIER_RANK[tier] < TIER_RANK["intern"]:
                problems.append(f"{role} agent is below INTERN maturity")
        elif not allow_unknown_tier:
            problems.append(f"{role} agent has no usable maturity tier")
    return problems


def authorize_thread_material(
    db,
    creator_id: str,
    member_ids: Sequence[str],
    *,
    workspace_id: Any = "",
    tenant_id: Any = "",
    context_tier: str = "",
    allow_unknown_tier: bool = False,
) -> tuple[List[str], Any]:
    """Return (problems, creator_row) for a would-be thread roster.

    Runs before any write.  The caller turns a non-empty problem list into an
    explicit ``failed_before_effect`` refusal; the verifier re-runs the same
    helper in a fresh session so a later authority change is refuted.
    """
    creator = _load_agent(db, creator_id)
    problems = _agent_problems(
        creator,
        role="creator",
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        require_intern=True,
        context_tier=context_tier,
        allow_unknown_tier=allow_unknown_tier,
    )
    for member_id in member_ids:
        if _text(member_id).strip() == _text(creator_id).strip():
            continue
        member = _load_agent(db, member_id)
        problems.extend(_agent_problems(
            member,
            role=f"member '{_text(member_id).strip()}'",
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            require_intern=False,
            allow_unknown_tier=True,
        ))
    return problems, creator


def read_thread(db, thread_id: str):
    """Read the exact AgentThread row in the supplied session.

    Ported unchanged from the accepted send-message work at
    ``3a188840d:backend/core/agent_radio/radio_mutations.py::read_thread``.
    """
    from core.models import AgentThread

    return db.query(AgentThread).filter(
        AgentThread.id == thread_id).first()


def find_threads_by_operation(
    db, operation_id: str, creator_id: str,
) -> List[Any]:
    """All create-thread rows bound to one server-owned operation id.

    Used by the verifier on a legacy/replay result that carries no thread id.
    The scan is bounded to one creator and filtered in Python so it does not
    depend on a vendor-specific JSON query.
    """
    operation = _text(operation_id).strip()
    creator = _text(creator_id).strip()
    if not operation or not creator:
        return []
    from core.models import AgentThread

    rows = db.query(AgentThread).filter(
        AgentThread.created_by_agent_id == creator).all()
    matched = []
    for row in rows:
        meta = getattr(row, "metadata_json", None)
        if isinstance(meta, Mapping) and _text(
                meta.get("operation_id")).strip() == operation:
            matched.append(row)
    return matched


def find_thread_by_operation(db, operation_id: str, creator_id: str):
    """First row for an operation id (compatibility helper)."""
    rows = find_threads_by_operation(db, operation_id, creator_id)
    return rows[0] if rows else None


def observed_thread_material(thread: Any) -> Dict[str, Any]:
    """Material present in the authoritative AgentThread row."""
    meta = getattr(thread, "metadata_json", None)
    meta = meta if isinstance(meta, Mapping) else {}
    roster = [
        _text(item).strip()
        for item in (getattr(thread, "member_agent_ids", None) or [])
        if _text(item).strip()
    ]
    return {
        "name": _text(getattr(thread, "name", "")).strip(),
        "created_by_agent_id": _text(
            getattr(thread, "created_by_agent_id", "")).strip(),
        "member_agent_ids": roster,
        "scope_hint": (
            _text(meta.get("scope")).strip().lower() or "manual"),
        "tenant_id": _text(getattr(thread, "tenant_id", "")).strip(),
    }


def thread_material_mismatches(
    expected: Mapping[str, Any] | None,
    observed: Mapping[str, Any] | None,
) -> List[str]:
    """Names of authorized thread fields the current row contradicts."""
    want = expected if isinstance(expected, Mapping) else {}
    got = observed if isinstance(observed, Mapping) else {}
    mismatches: List[str] = []
    for field in THREAD_MATERIAL_FIELDS:
        if field not in want:
            continue
        expected_value = want.get(field)
        observed_value = got.get(field)
        if field == "member_agent_ids":
            if sorted(set(expected_value or [])) != sorted(
                    set(observed_value or [])):
                mismatches.append(field)
        elif field == "tenant_id":
            if not _scope_compatible(expected_value, observed_value):
                mismatches.append(field)
        elif field == "scope_hint":
            if _text(expected_value).strip().lower() != _text(
                    observed_value).strip().lower():
                mismatches.append(field)
        else:
            if _text(expected_value) != _text(observed_value):
                mismatches.append(field)
    return mismatches


def durable_thread_receipt_projection(
    result: Mapping[str, Any] | None,
    expected: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Provider-specific material for a durable create-thread claim receipt."""
    expected = expected if isinstance(expected, Mapping) else {}
    material = expected.get("_oracle_expected_radio_thread")
    return {
        "authorized_material": (
            copy.deepcopy(dict(material))
            if isinstance(material, Mapping) else None),
    }


def durable_thread_material_conflicts(
    expected: Mapping[str, Any] | None,
    durable_result: Mapping[str, Any] | None,
) -> List[str]:
    """Conflicts between stored authorized thread material and this request."""
    expected = expected if isinstance(expected, Mapping) else {}
    durable_result = (
        durable_result if isinstance(durable_result, Mapping) else {})
    expected_material = expected.get("_oracle_expected_radio_thread")
    if not isinstance(expected_material, Mapping) or not expected_material:
        return []
    stored = durable_result.get("authorized_material")
    if not isinstance(stored, Mapping) or not stored:
        return ["authorized_material"]
    conflicts = thread_material_mismatches(expected_material, stored)
    if not _scope_compatible(
            expected_material.get("workspace_id"),
            stored.get("workspace_id")):
        conflicts.append("workspace_id")
    return sorted(set(conflicts))


def _failed_before_effect(
    *,
    operation_id: str,
    payload_sha256: str,
    error: str,
    message: str,
    error_kind: str,
    problems: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "success": False,
        "status": "failed_before_effect",
        "action_result": "proven_not_applied",
        "effect_possible": False,
        "provider": "agent_radio",
        "operation": "create_thread",
        "error": error,
        "error_kind": error_kind,
        "message": message,
        "problems": list(problems or []),
        "retryable": False,
        "remote_id": "",
        "payload_sha256": payload_sha256,
        "provider_receipt": {
            "provider": "agent_radio",
            "operation": "create_thread",
            "operation_id": operation_id,
            "payload_sha256": payload_sha256,
            "remote_id": "",
        },
    }


def _uncertain(
    *,
    operation_id: str,
    payload_sha256: str,
    thread_id: str,
    error: str,
    error_kind: str,
    verification: Dict[str, Any],
    read_receipt: Optional[Dict[str, Any]] = None,
    evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "success": False,
        "status": "uncertain",
        "action_result": "uncertain",
        "business_success": False,
        "effect_possible": True,
        "provider": "agent_radio",
        "operation": "create_thread",
        "error": error,
        "error_kind": error_kind,
        "retryable": False,
        "thread_id": thread_id,
        "remote_id": thread_id,
        "payload_sha256": payload_sha256,
        "provider_receipt": {
            "provider": "agent_radio",
            "operation": "create_thread",
            "operation_id": operation_id,
            "payload_sha256": payload_sha256,
            "remote_id": thread_id,
        },
        "read_receipt": read_receipt,
        "verification": verification,
        "evidence": [evidence] if evidence else [],
    }


def _applied(
    *,
    operation_id: str,
    payload_sha256: str,
    thread_id: str,
    observed: Dict[str, Any],
    read_receipt: Dict[str, Any],
) -> Dict[str, Any]:
    roster = list(observed.get("member_agent_ids") or [])
    return {
        "success": True,
        "status": "success",
        "action_result": "applied",
        "provider": "agent_radio",
        "operation": "create_thread",
        "thread_id": thread_id,
        "remote_id": thread_id,
        "name": observed.get("name"),
        "member_agent_ids": roster,
        "message": (
            f"Thread '{observed.get('name')}' created with "
            f"{len(roster)} member(s)."),
        "payload_sha256": payload_sha256,
        "provider_receipt": {
            "provider": "agent_radio",
            "operation": "create_thread",
            "operation_id": operation_id,
            "payload_sha256": payload_sha256,
            "remote_id": thread_id,
            "tenant_id": str(observed.get("tenant_id") or ""),
        },
        "read_receipt": read_receipt,
        "verification": {
            "status": "verified",
            "missing_fields": [],
            "mismatches": [],
        },
    }


def _read_receipt(thread_id: str, observed: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "provider": "agent_radio",
        "operation": "get_thread",
        "resource_id": thread_id,
        "requested_remote_id": thread_id,
        "observed_remote_id": thread_id,
        "coverage": "single",
        "account_id": str(observed.get("tenant_id") or ""),
        "tenant_id": str(observed.get("tenant_id") or ""),
        "fields": observed,
    }


async def create_thread(
    arguments: Mapping[str, Any] | None,
    context: Mapping[str, Any] | None,
    *,
    operation_id: str = "",
) -> Dict[str, Any]:
    """Create one radio thread, then re-read the exact row/material.

    Pre-effect refusals are explicit ``proven_not_applied`` results.  Once the
    service has committed, a missing/mismatched/unavailable readback is
    ``uncertain`` and keeps the known thread id; it is never fabricated into
    success or retried automatically.
    """
    from core.database import get_db_session

    ctx = context if isinstance(context, Mapping) else {}
    creator_id = _text(ctx.get("agent_id")).strip()
    workspace_id = _norm_scope(ctx.get("workspace_id")) or "default"
    raw_tenant_id = _norm_scope(ctx.get("tenant_id"))
    context_tier = _text(ctx.get("tier")).strip().lower()
    payload = thread_payload(
        arguments,
        agent_id=creator_id,
        workspace_id=workspace_id,
        tenant_id=raw_tenant_id,
    )
    digest = _payload_digest(payload)
    args_map = arguments if isinstance(arguments, Mapping) else {}
    operation = _text(
        operation_id or ctx.get("operation_id")
        or args_map.get("operation_id")).strip()

    if not creator_id:
        return _failed_before_effect(
            operation_id=operation, payload_sha256=digest,
            error="Context agent_id is required to create a thread.",
            message="Context agent_id is required to create a thread.",
            error_kind="agent_id_required",
        )
    if not payload["name"]:
        return _failed_before_effect(
            operation_id=operation, payload_sha256=digest,
            error="name is required",
            message="name is required",
            error_kind="invalid_request",
        )
    if len(payload["name"]) > 255:
        return _failed_before_effect(
            operation_id=operation, payload_sha256=digest,
            error="name exceeds 255 characters",
            message="name exceeds 255 characters",
            error_kind="invalid_request",
        )
    if payload["scope_hint"] not in SCOPE_HINTS:
        return _failed_before_effect(
            operation_id=operation, payload_sha256=digest,
            error="scope_hint must be one of fleet, task, manual",
            message="scope_hint must be one of fleet, task, manual",
            error_kind="invalid_request",
        )
    if len(payload["member_agent_ids"]) < 2:
        return _failed_before_effect(
            operation_id=operation, payload_sha256=digest,
            error=(
                "member_agent_ids must list at least one other agent"),
            message=(
                "member_agent_ids must list at least one other agent"),
            error_kind="invalid_request",
        )

    metadata: Dict[str, Any] = {"scope": payload["scope_hint"]}
    if operation:
        metadata["operation_id"] = operation

    # Authority is checked BEFORE the write against the real registry rows and
    # in the SAME session/transaction as the insert, so a peer scope change
    # cannot slip between the check and the effect.  The fresh readback below
    # independently re-checks the committed row.
    try:
        with get_db_session() as db:
            try:
                problems, _creator = authorize_thread_material(
                    db,
                    creator_id,
                    payload["member_agent_ids"],
                    workspace_id=payload["workspace_id"],
                    tenant_id=payload["tenant_id"],
                    context_tier=context_tier,
                )
            except Exception as exc:  # noqa: BLE001 - no write attempted yet
                return _failed_before_effect(
                    operation_id=operation, payload_sha256=digest,
                    error="authority_unavailable",
                    message=(
                        "Creator/member authority could not be read; no "
                        f"thread was created ({type(exc).__name__})."),
                    error_kind="authority_unavailable",
                )
            if problems:
                return _failed_before_effect(
                    operation_id=operation, payload_sha256=digest,
                    error="authority_refused",
                    message="; ".join(problems),
                    error_kind="authority_refused",
                    problems=problems,
                )
            thread = radio_service.create_thread(
                db,
                name=payload["name"],
                created_by_agent_id=creator_id,
                member_agent_ids=list(payload["member_agent_ids"]),
                tenant_id=raw_tenant_id or None,
                metadata_json=metadata,
            )
            thread_id = _text(getattr(thread, "id", "")).strip()
    except RadioError as exc:
        return _failed_before_effect(
            operation_id=operation, payload_sha256=digest,
            error="radio_error",
            message=str(exc),
            error_kind="radio_error",
        )
    except Exception as exc:  # noqa: BLE001 - the row may have committed
        return _uncertain(
            operation_id=operation, payload_sha256=digest,
            thread_id="",
            error="internal_error",
            error_kind="provider_error",
            verification={
                "status": "incomplete",
                "missing_fields": ["transport_confirmation"],
                "mismatches": [],
            },
            evidence={
                "kind": "radio_create_thread_transport_error",
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            },
        )

    if not thread_id:
        return _uncertain(
            operation_id=operation, payload_sha256=digest,
            thread_id="",
            error=(
                "Radio accepted the thread but returned no id; the effect "
                "cannot be identified"),
            error_kind="unidentified_effect",
            verification={
                "status": "incomplete",
                "missing_fields": ["remote_id"],
                "mismatches": [],
            },
            evidence={"kind": "radio_create_thread_missing_id"},
        )

    # Exact durable readback in a FRESH session (never the writer's identity
    # map).  A failure here is not a pre-effect refusal: the row may exist.
    try:
        with get_db_session() as db:
            observed_thread = read_thread(db, thread_id)
    except Exception as exc:  # noqa: BLE001 - readback failure is not pre-effect
        return _uncertain(
            operation_id=operation, payload_sha256=digest,
            thread_id=thread_id,
            error="internal_error",
            error_kind="readback_unavailable",
            verification={
                "status": "incomplete",
                "missing_fields": ["readback"],
                "mismatches": [],
            },
            evidence={
                "kind": "radio_create_thread_readback_unavailable",
                "remote_id": thread_id,
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            },
        )

    if observed_thread is None:
        return _uncertain(
            operation_id=operation, payload_sha256=digest,
            thread_id=thread_id,
            error="internal_error",
            error_kind="readback_missing",
            verification={
                "status": "incomplete",
                "missing_fields": ["readback"],
                "mismatches": [],
            },
            evidence={
                "kind": "radio_create_thread_row_absent",
                "remote_id": thread_id,
            },
        )

    observed = observed_thread_material(observed_thread)
    observed_id = _text(getattr(observed_thread, "id", "")).strip()
    mismatches = thread_material_mismatches(payload, observed)
    if observed_id != thread_id:
        mismatches.append("remote_id")
    read_receipt = _read_receipt(thread_id, observed)
    if mismatches:
        return _uncertain(
            operation_id=operation, payload_sha256=digest,
            thread_id=thread_id,
            error="internal_error",
            error_kind="readback_mismatch",
            verification={
                "status": "mismatch",
                "missing_fields": [],
                "mismatches": mismatches,
            },
            read_receipt=read_receipt,
            evidence={
                "kind": "radio_create_thread_readback_mismatch",
                "remote_id": thread_id,
                "mismatches": mismatches,
            },
        )

    return _applied(
        operation_id=operation,
        payload_sha256=digest,
        thread_id=thread_id,
        observed=observed,
        read_receipt=read_receipt,
    )
