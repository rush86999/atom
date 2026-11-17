"""Durable binding for a human-approved tool call (generic dispatch consumer).

The generic ReAct loop freezes the request, asks a human to review it, and
must then execute the material the human actually approved. A ``status ==
"approved"`` boolean is not authority: the durable row must still bind the
EXACT agent, tool, actor, execution scope, reviewer and reviewed/approved
payload. Edit-before-approve approves a modified payload, so the effective
material has to come from the row rather than from the model's original call.

This module is deliberately a thin seam over mechanisms that already exist:

* :func:`core.intervention_service.describe_parameter_history` reads the
  append-only review/approval receipt inside ``HITLAction.context_snapshot``
  (reviewed proposal + effective payload) without inventing a second store.
* :func:`core.goal_run_decision_service._resolve_actor` and
  ``canonical_scope_id`` resolve the CURRENT reviewer from a fresh session and
  canonicalise the Personal-Edition NULL/``default`` scope.
* ``core.security.rbac.persisted_required_roles`` / ``required_role_denial``
  enforce BOTH persisted ``required_role`` locations.
* :func:`core.oracle.request_expectations.strip_expected_fields` keeps the
  protected ``_oracle_expected_*`` namespace out of approved material, so an
  edit-before-approve can never mint server-owned proof fields.

There is no second approval registry and no integration-specific matching.
"""
from __future__ import annotations

import copy
import json
import logging
from typing import Any, Dict, Mapping, Optional

from core.models import HITLAction, HITLActionStatus, UserRole

logger = logging.getLogger(__name__)

_ACCEPTED_STATUSES = (HITLActionStatus.APPROVED.value,)
_INTERNAL_PLATFORM = "internal"


def _refusal(code: str, message: str) -> Dict[str, Any]:
    return {"ok": False, "code": str(code), "message": str(message)}


def _canonical(value: Any) -> Optional[str]:
    """Stable JSON text for equality, or ``None`` when the value is not JSON.

    Approval material is persisted in a JSON column, so a non-JSON value is
    not a receipt we can compare and must never be treated as equal.
    """
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        return None


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _history(action: Any) -> Dict[str, Any]:
    from core.intervention_service import describe_parameter_history

    return describe_parameter_history(action, redact=False)


def load_approved_material(
    action_id: str,
    *,
    agent_id: str,
    action_type: str,
    reviewed_params: Mapping[str, Any],
    actor_id: str = "",
    tenant_id: str = "",
    workspace_id: str = "",
    execution_id: str = "",
    run_id: str = "",
    db_factory: Any = None,
) -> Dict[str, Any]:
    """Re-read one durable approval and return its exact effective material.

    Returns ``{"ok": True, "effective_params": ..., "original_params": ...}``
    only when every binding is still true. Any missing/changed/foreign
    binding, unreadable authority, tampered payload or unreviewed payload
    change returns ``{"ok": False, "code": ..., "message": ...}`` — absence of
    authority, never a status-only shortcut.
    """
    from core.goal_run_decision_service import _resolve_actor, canonical_scope_id
    from core.oracle.request_expectations import (
        approved_payload_sha256,
        strip_expected_fields,
    )
    from core.security.rbac import (
        persisted_required_roles,
        required_role_denial,
        role_level,
    )

    factory = db_factory
    if factory is None:
        from core.database import get_db_session

        factory = get_db_session

    if not isinstance(reviewed_params, Mapping):
        return _refusal(
            "approval_request_unreadable",
            "The reviewed request is not a parameter mapping.")

    reviewed = strip_expected_fields(reviewed_params)
    reviewed_text = _canonical(reviewed)
    if reviewed_text is None:
        return _refusal(
            "approval_request_unreadable",
            "The reviewed request is not strict JSON.")

    try:
        with factory() as db:
            action = db.query(HITLAction).filter(
                HITLAction.id == str(action_id or "")).first()
            if action is None:
                return _refusal(
                    "approval_not_found",
                    "The durable approval record could not be found.")

            status = _text(action.status).lower()
            if status not in _ACCEPTED_STATUSES:
                return _refusal(
                    "approval_not_approved",
                    f"The approval is {status or 'unreadable'}, not approved.")

            if _text(action.platform) != _INTERNAL_PLATFORM:
                return _refusal(
                    "approval_platform_mismatch",
                    "The approval belongs to a different review surface.")

            bound_agent = _text(action.agent_id)
            current_agent = _text(agent_id)
            if not bound_agent or not current_agent or bound_agent != current_agent:
                return _refusal(
                    "approval_agent_mismatch",
                    "The approval is not bound to this agent.")

            bound_action = _text(action.action_type)
            current_action = _text(action_type)
            if not bound_action or bound_action != current_action:
                return _refusal(
                    "approval_action_mismatch",
                    "The approval is not bound to this action.")

            # Exact current scope. ``canonical_scope_id`` treats Personal
            # Edition NULL and the literal "default" as the same scope and
            # keeps every other workspace/tenant exact.
            bound_workspace = canonical_scope_id(action.workspace_id)
            bound_tenant = canonical_scope_id(action.tenant_id)
            if bound_workspace != canonical_scope_id(workspace_id):
                return _refusal(
                    "approval_scope_mismatch",
                    "The approval is outside this workspace.")
            if bound_tenant != canonical_scope_id(tenant_id):
                return _refusal(
                    "approval_scope_mismatch",
                    "The approval is outside this tenant.")

            # A persisted execution context is either a mapping or absent.
            # Any other shape is a corrupt authority row: treating it as
            # absent would silently down-grade a modern receipt to the legacy
            # no-history path, so it is a refusal instead.
            if (
                action.context_snapshot is not None
                and not isinstance(action.context_snapshot, Mapping)
            ):
                return _refusal(
                    "approval_material_unavailable",
                    "The approval's recorded execution context is unreadable.")
            snapshot = (
                action.context_snapshot
                if isinstance(action.context_snapshot, Mapping) else {})

            # The execution binding written by request_approval is
            # immutable. A caller that now runs under a different execution
            # (or suddenly has no execution identity at all) must not inherit
            # the old decision.
            bound_execution = _text(
                snapshot.get("execution_id") or snapshot.get("run_id"))
            current_execution = _text(execution_id or run_id)
            if bound_execution or current_execution:
                if (not bound_execution or not current_execution
                        or bound_execution != current_execution):
                    return _refusal(
                        "approval_execution_mismatch",
                        "The approval is not bound to this execution.")

            # Owner/actor binding. A row owner that this call cannot name is
            # not an actor-bound approval; a differing owner is foreign.
            bound_user = _text(action.user_id)
            snapshot_user = _text(
                snapshot.get("user_id") or snapshot.get("actor_id"))
            current_actor = _text(actor_id)
            if bound_user and snapshot_user and bound_user != snapshot_user:
                return _refusal(
                    "approval_owner_mismatch",
                    "The approval owner binding changed.")
            if current_actor:
                if bound_user and current_actor != bound_user:
                    return _refusal(
                        "approval_actor_mismatch",
                        "This approval belongs to a different user.")
                if snapshot_user and current_actor != snapshot_user:
                    return _refusal(
                        "approval_actor_mismatch",
                        "This approval belongs to a different user.")
            elif bound_user:
                return _refusal(
                    "approval_actor_unbound",
                    "The current run names no actor for this approval.")

            # The reviewer is re-resolved from the CURRENT durable actor row;
            # a stale request object or a foreign-scope reviewer is not
            # authority. The same owner-or-supervisor rule and BOTH required
            # role locations used by every other HITL decision apply.
            reviewer_id = _text(action.reviewed_by)
            if not reviewer_id or action.reviewed_at is None:
                return _refusal(
                    "approval_reviewer_missing",
                    "The approval has no durable reviewer decision.")
            authority = _resolve_actor(db, reviewer_id)
            if not authority.get("ok"):
                return _refusal(
                    "approval_reviewer_unavailable",
                    str(authority.get("message")
                        or "The reviewer's authority could not be confirmed."))
            if (
                canonical_scope_id(authority.get("workspace_id"))
                != bound_workspace
                or canonical_scope_id(authority.get("tenant_id"))
                != bound_tenant
            ):
                return _refusal(
                    "approval_reviewer_scope_denied",
                    "The reviewer is outside this approval's scope.")
            owner = bound_user or snapshot_user
            is_owner = bool(owner) and authority["id"] == owner
            is_supervisor = role_level(authority["role"]) >= role_level(
                UserRole.TEAM_LEAD)
            if not (is_owner or is_supervisor):
                return _refusal(
                    "approval_reviewer_not_authorized",
                    "Only this approval's owner or a supervisor can "
                    "authorize it.")
            denial = required_role_denial(
                authority["role"], persisted_required_roles(action),
                subject=bound_action or "action", actor_label="Reviewer")
            if denial:
                return _refusal(
                    "approval_reviewer_role_denied", denial)

            # Fresh requester authority resolution. The durable user row is
            # the CURRENT local authority, not the request object or the
            # context-supplied id: a caller that disappeared (deleted/
            # disabled) or moved tenant/workspace is no longer the admitted
            # actor the human reviewed this request for. ``_resolve_actor``
            # opens its own session and applies the repo's NULL/``default``
            # canonicalisation; an ownerless (background/bridge) approval
            # with no named actor is the declared legacy contract and keeps
            # its path below. A NAMED but missing/deleted caller is never
            # treated as an unknown synthetic principal.
            if current_actor:
                requester = _resolve_actor(db, current_actor)
                if not requester.get("ok"):
                    error_code = str(requester.get("error_code") or "")
                    if error_code == "ACCOUNT_INACTIVE":
                        return _refusal(
                            "approval_actor_inactive",
                            "The requesting user is not active.")
                    if error_code == "AUTHORITY_UNAVAILABLE":
                        return _refusal(
                            "approval_authority_unavailable",
                            "The requesting user's authority could not be "
                            "confirmed; no effect was attempted.")
                    return _refusal(
                        "approval_actor_unavailable",
                        "The requesting user no longer exists.")
                if canonical_scope_id(
                        requester.get("workspace_id")) != bound_workspace:
                    return _refusal(
                        "approval_actor_scope_denied",
                        "The requesting user is outside this "
                        "approval's workspace.")
                if canonical_scope_id(
                        requester.get("tenant_id")) != bound_tenant:
                    return _refusal(
                        "approval_actor_scope_denied",
                        "The requesting user is outside this "
                        "approval's tenant.")

            # Exact reviewed/effective material. ``describe_parameter_history``
            # reports the original as unknown (never reconstructed) for
            # historical approvals that predate the receipt.
            try:
                history = _history(action)
            except Exception as exc:  # noqa: BLE001 - unreadable is refusal
                logger.warning(
                    "approved material history unreadable for %s: %s",
                    action.id, type(exc).__name__)
                return _refusal(
                    "approval_material_unavailable",
                    "The approval's reviewed material could not be read.")

            original_known = bool(history.get("original_known"))
            original = history.get("original_params")
            effective = history.get("effective_params")
            if not isinstance(effective, Mapping):
                return _refusal(
                    "approval_material_unavailable",
                    "The approval has no durable effective payload.")

            if original_known:
                if not isinstance(original, Mapping):
                    return _refusal(
                        "approval_material_unavailable",
                        "The approval's reviewed payload is unreadable.")
                original_text = _canonical(strip_expected_fields(original))
                if original_text is None or original_text != reviewed_text:
                    return _refusal(
                        "approval_material_mismatch",
                        "This call is not the request the human reviewed.")
            else:
                # No receipt: only an UNCHANGED payload can be consumed. An
                # edit whose original was not recorded was never proved to be
                # reviewed, so it requires a fresh review. The historical
                # original is NOT reconstructed: ``original_text`` here is the
                # verified unchanged payload (the only original-shaped
                # statement a legacy row can prove), and the returned material
                # keeps ``original_known=False`` so no caller can present it
                # as a recorded historical original.
                unchanged_text = _canonical(strip_expected_fields(effective))
                if unchanged_text is None or unchanged_text != reviewed_text:
                    return _refusal(
                        "approval_material_unreviewed_change",
                        "The approved payload was edited without a recorded "
                        "review of the original request; a fresh review is "
                        "required.")
                original_text = unchanged_text

            # The row's live params are the effective payload execution
            # consumes; the receipt must still describe exactly those bytes.
            raw_effective_text = _canonical(action.params)
            receipt_effective_text = _canonical(effective)
            if (
                raw_effective_text is None
                or receipt_effective_text is None
                or raw_effective_text != receipt_effective_text
            ):
                return _refusal(
                    "approval_material_tampered",
                    "The approval's effective payload changed after the "
                    "reviewer decision; a fresh review is required.")

            effective_payload = strip_expected_fields(effective)
            effective_text = _canonical(effective_payload)
            if effective_text is None:
                return _refusal(
                    "approval_material_unavailable",
                    "The approved payload is not strict JSON.")

            return {
                "ok": True,
                "action_id": _text(action.id),
                "approved_by": authority["id"],
                "approved_role": str(authority.get("role") or ""),
                "reviewed_at": (
                    action.reviewed_at.isoformat()
                    if hasattr(action.reviewed_at, "isoformat")
                    else str(action.reviewed_at)),
                # Explicit provenance: a historical row without the receipt
                # has no recorded original. Callers must never present the
                # verified unchanged payload as that original.
                "original_known": original_known,
                "original_params": (
                    copy.deepcopy(original) if original_known else None),
                "reviewed_params": copy.deepcopy(reviewed),
                "effective_params": copy.deepcopy(effective_payload),
                "material_changed": original_text != effective_text,
                "reviewed_sha256": approved_payload_sha256(
                    dict(reviewed)),
                "effective_sha256": approved_payload_sha256(
                    dict(effective_payload)),
                "binding": {
                    "agent_id": bound_agent,
                    "action_type": bound_action,
                    "workspace_id": bound_workspace,
                    "tenant_id": bound_tenant,
                    "user_id": bound_user,
                    "execution_id": bound_execution,
                },
                "reviewer_scope": {
                    "workspace_id": canonical_scope_id(
                        authority.get("workspace_id")),
                    "tenant_id": canonical_scope_id(
                        authority.get("tenant_id")),
                },
            }
    except Exception as exc:  # noqa: BLE001 — unreadable authority fails closed
        logger.warning(
            "approved material read failed for %s: %s",
            action_id, type(exc).__name__)
        return _refusal(
            "approval_authority_unavailable",
            "The approval authority could not be read; no effect was "
            "attempted.")
