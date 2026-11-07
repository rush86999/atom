"""Registered ``radio.send_message`` producer and material projection.

The predecessor action committed a ``LateralMessage`` and returned the raw
success envelope.  This module keeps the same service/persistence path and adds
only what the shared claim/Oracle layer needs:

* a canonical authorized message payload (thread, server-owned sender, content,
  normalized mention set, target, response flag, tenant);
* an exact by-id re-read of the ``LateralMessage`` row plus its thread scope;
* an explicit applied/uncertain envelope.  Missing or contradictory readback is
  never turned into success.

Contract: ``docs/architecture/AGENT_RADIO.md`` §Protocol (mention-first,
thread-scoped, no broadcast) and ``agent_threads``/``lateral_messages``.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Mapping, Optional

from core.agent_radio import radio_server, radio_service
from core.agent_radio.radio_service import (
    RadioAccessError,
    RadioBudgetExceeded,
    RadioError,
    RadioPolicyError,
)

#: Material fields the Oracle compares.  The message id locates the row; it is
#: not caller-authorized material.
RADIO_MESSAGE_MATERIAL_FIELDS = (
    "thread_id", "from_agent_id", "to_agent_id", "content", "mentions",
    "requires_response", "tenant_id",
)


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _normalized_mentions(
    mention_agent_ids: Any,
    to_agent_id: Any,
    from_agent_id: Any,
) -> List[str]:
    """The service's mention set, canonicalized for comparison.

    ``radio_service.send_message`` prepends ``to_agent_id``, removes the sender
    and de-duplicates while preserving first occurrence.  Mentions are a set
    for identity purposes, so the material sorts them.
    """
    sender = _text(from_agent_id)
    mentions: List[str] = []
    for item in mention_agent_ids or []:
        text = _text(item)
        if text and text != sender and text not in mentions:
            mentions.append(text)
    target = _text(to_agent_id).strip()
    if target and target != sender and target not in mentions:
        mentions.insert(0, target)
    return sorted(set(mentions))


def radio_payload(
    arguments: Mapping[str, Any] | None,
    *,
    agent_id: Any,
    tenant_id: Any,
) -> Dict[str, Any]:
    """The exact authorized message material and request digest input."""
    args = arguments if isinstance(arguments, Mapping) else {}
    return {
        "thread_id": _text(args.get("thread_id")).strip(),
        "from_agent_id": _text(agent_id),
        "to_agent_id": _text(args.get("to_agent_id")).strip(),
        "content": _text(args.get("content")),
        "mentions": _normalized_mentions(
            args.get("mention_agent_ids"),
            args.get("to_agent_id"),
            agent_id,
        ),
        "requires_response": bool(args.get("requires_response")),
        "tenant_id": _text(tenant_id),
    }


def _payload_digest(payload: Mapping[str, Any]) -> str:
    from core.task_lifecycle import _approval_payload_hash

    return _approval_payload_hash(dict(payload))


def read_message(db, message_id: str):
    """Read the exact LateralMessage row in the supplied session."""
    from core.models import LateralMessage

    return db.query(LateralMessage).filter(
        LateralMessage.id == message_id).first()


def read_thread(db, thread_id: str):
    """Read the thread scope row in the supplied session."""
    from core.models import AgentThread

    return db.query(AgentThread).filter(
        AgentThread.id == thread_id).first()


def observed_message_material(message, thread) -> Dict[str, Any]:
    meta = getattr(message, "metadata_json", None) or {}
    requires_response = bool(
        meta.get("priority") == "high" and meta.get("is_response") is False)
    return {
        "thread_id": _text(getattr(message, "thread_id", "")).strip(),
        "from_agent_id": _text(getattr(message, "from_agent_id", "")),
        "to_agent_id": _text(getattr(message, "to_agent_id", "")).strip(),
        "content": _text(getattr(message, "content", "")),
        "mentions": sorted({
            _text(item) for item in (getattr(message, "mentions", None) or [])
            if _text(item)
        }),
        "requires_response": requires_response,
        "tenant_id": _text(getattr(thread, "tenant_id", "")),
    }


def radio_material_mismatches(
    expected: Mapping[str, Any] | None,
    observed: Mapping[str, Any] | None,
) -> List[str]:
    """Names of authorized message fields the current row contradicts."""
    want = expected if isinstance(expected, Mapping) else {}
    got = observed if isinstance(observed, Mapping) else {}
    mismatches: List[str] = []
    for field in RADIO_MESSAGE_MATERIAL_FIELDS:
        if field not in want:
            continue
        expected_value = want.get(field)
        observed_value = got.get(field)
        if field == "mentions":
            if sorted(set(expected_value or [])) != sorted(
                    set(observed_value or [])):
                mismatches.append(field)
        elif field == "requires_response":
            if bool(expected_value) is not bool(observed_value):
                mismatches.append(field)
        elif field == "tenant_id":
            # Single-tenant compatibility: a null/empty thread tenant is not a
            # conflict; two different non-empty tenants are.
            if (str(expected_value or "").strip()
                    and str(observed_value or "").strip()
                    and str(expected_value).strip() != str(
                        observed_value).strip()):
                mismatches.append(field)
        else:
            if _text(expected_value) != _text(observed_value):
                mismatches.append(field)
    return mismatches


def durable_radio_receipt_projection(
    result: Mapping[str, Any] | None,
    expected: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Provider-specific material for a durable radio claim receipt."""
    expected = expected if isinstance(expected, Mapping) else {}
    material = expected.get("_oracle_expected_radio_message")
    return {
        "authorized_material": (
            copy.deepcopy(dict(material))
            if isinstance(material, Mapping) else None),
    }


def durable_radio_material_conflicts(
    expected: Mapping[str, Any] | None,
    durable_result: Mapping[str, Any] | None,
) -> List[str]:
    """Conflicts between stored authorized radio material and this request."""
    expected = expected if isinstance(expected, Mapping) else {}
    durable_result = (
        durable_result if isinstance(durable_result, Mapping) else {})
    expected_material = expected.get("_oracle_expected_radio_message")
    if not isinstance(expected_material, Mapping) or not expected_material:
        return []
    stored = durable_result.get("authorized_material")
    if not isinstance(stored, Mapping) or not stored:
        return ["authorized_material"]
    return radio_material_mismatches(expected_material, stored)


def _failed_before_effect(
    *, operation_id: str, payload_sha256: str, error: str, message: str,
    error_kind: str,
) -> Dict[str, Any]:
    return {
        "success": False,
        "status": "failed_before_effect",
        "action_result": "proven_not_applied",
        "effect_possible": False,
        "provider": "agent_radio",
        "operation": "send_message",
        "error": error,
        "error_kind": error_kind,
        "message": message,
        "retryable": False,
        "remote_id": "",
        "payload_sha256": payload_sha256,
        "provider_receipt": {
            "provider": "agent_radio",
            "operation": "send_message",
            "operation_id": operation_id,
            "payload_sha256": payload_sha256,
            "remote_id": "",
        },
    }


def _uncertain(
    *, operation_id: str, payload_sha256: str, message_id: str,
    message: Optional[Dict[str, Any]], error_kind: str, error: str,
    verification: Dict[str, Any],
    read_receipt: Optional[Dict[str, Any]] = None,
    evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "success": False,
        "status": "uncertain",
        "action_result": "uncertain",
        "effect_possible": True,
        "provider": "agent_radio",
        "operation": "send_message",
        "error": error,
        "error_kind": error_kind,
        "retryable": False,
        "remote_id": message_id,
        "payload_sha256": payload_sha256,
        "provider_receipt": {
            "provider": "agent_radio",
            "operation": "send_message",
            "operation_id": operation_id,
            "payload_sha256": payload_sha256,
            "remote_id": message_id,
        },
        "read_receipt": read_receipt,
        "verification": verification,
        "message": message,
        "evidence": [evidence] if evidence else [],
    }


def _applied(
    *, operation_id: str, payload_sha256: str, message_id: str,
    observed: Dict[str, Any], read_receipt: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "success": True,
        "status": "success",
        "action_result": "applied",
        "provider": "agent_radio",
        "operation": "send_message",
        "remote_id": message_id,
        "message_id": message_id,
        "thread_id": str(observed.get("thread_id") or ""),
        "mentions": list(observed.get("mentions") or []),
        "payload_sha256": payload_sha256,
        "provider_receipt": {
            "provider": "agent_radio",
            "operation": "send_message",
            "operation_id": operation_id,
            "payload_sha256": payload_sha256,
            "remote_id": message_id,
            "tenant_id": str(observed.get("tenant_id") or ""),
        },
        "read_receipt": read_receipt,
        "verification": {
            "status": "verified",
            "missing_fields": [],
            "mismatches": [],
        },
        "message": observed,
    }


async def send_message(
    arguments: Mapping[str, Any] | None,
    context: Mapping[str, Any] | None,
    *,
    operation_id: str = "",
) -> Dict[str, Any]:
    """Send one radio message, then re-read the exact id/material."""
    from core.database import get_db_session

    ctx = context or {}
    agent_id = _text(ctx.get("agent_id"))
    tenant_id = _text(ctx.get("tenant_id"))
    payload = radio_payload(
        arguments, agent_id=agent_id, tenant_id=tenant_id)
    digest = _payload_digest(payload)
    operation = str(
        operation_id or ctx.get("operation_id")
        or (arguments or {}).get("operation_id") or "")

    if not agent_id:
        return _failed_before_effect(
            operation_id=operation, payload_sha256=digest,
            error="Context agent_id is required to send a message.",
            message="Context agent_id is required to send a message.",
            error_kind="agent_id_required",
        )
    if not payload["thread_id"]:
        return _failed_before_effect(
            operation_id=operation, payload_sha256=digest,
            error="thread_id is required",
            message="thread_id is required",
            error_kind="invalid_request",
        )

    metadata: Dict[str, Any] = {}
    if payload["requires_response"]:
        metadata = {"is_response": False, "priority": "high"}

    try:
        with get_db_session() as db:
            message = radio_service.send_message(
                db,
                thread_id=payload["thread_id"],
                from_agent_id=agent_id,
                content=payload["content"],
                mention_agent_ids=list(payload["mentions"]),
                to_agent_id=payload["to_agent_id"] or None,
                metadata_json=metadata or None,
            )
            message_id = _text(getattr(message, "id", ""))
        with get_db_session() as db:
            observed_message = read_message(db, message_id) if message_id else None
            observed_thread = read_thread(db, payload["thread_id"])
    except RadioPolicyError as exc:
        return _failed_before_effect(
            operation_id=operation, payload_sha256=digest,
            error="policy_error", message=str(exc),
            error_kind="policy_error",
        )
    except RadioAccessError as exc:
        return _failed_before_effect(
            operation_id=operation, payload_sha256=digest,
            error="access_error", message=str(exc),
            error_kind="access_error",
        )
    except RadioBudgetExceeded as exc:
        return _failed_before_effect(
            operation_id=operation, payload_sha256=digest,
            error="budget_exceeded", message=str(exc),
            error_kind="budget_exceeded",
        )
    except RadioError as exc:
        return _failed_before_effect(
            operation_id=operation, payload_sha256=digest,
            error="radio_error", message=str(exc),
            error_kind="radio_error",
        )
    except Exception as exc:  # noqa: BLE001 - the row may have committed
        return _uncertain(
            operation_id=operation, payload_sha256=digest, message_id="",
            message=None, error_kind="provider_error",
            error="internal_error",
            verification={
                "status": "incomplete",
                "missing_fields": ["transport_confirmation"],
                "mismatches": [],
            },
            evidence={
                "kind": "radio_send_transport_error",
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            },
        )

    # The row is the durable effect; the relay wakeup is additive and must not
    # turn a committed row into a failure.
    try:
        await radio_server.get_radio_server().publish(message)
    except Exception:  # noqa: BLE001 - wakeup is not the business effect
        pass

    if not message_id:
        return _uncertain(
            operation_id=operation, payload_sha256=digest, message_id="",
            message=None, error_kind="unidentified_effect",
            error=(
                "Radio accepted the send but returned no message id; the "
                "effect cannot be identified and is not safe to recreate"),
            verification={
                "status": "incomplete",
                "missing_fields": ["remote_id"],
                "mismatches": [],
            },
            evidence={"kind": "radio_send_missing_id"},
        )
    if observed_message is None or observed_thread is None:
        return _uncertain(
            operation_id=operation, payload_sha256=digest,
            message_id=message_id, message=None,
            error_kind="readback_unavailable",
            error=(
                "Radio message was written but the exact row/thread could not "
                "be read back"),
            verification={
                "status": "incomplete",
                "missing_fields": ["readback"],
                "mismatches": [],
            },
            evidence={
                "kind": "radio_send_readback_unavailable",
                "remote_id": message_id,
            },
        )

    observed = observed_message_material(observed_message, observed_thread)
    mismatches = radio_material_mismatches(payload, observed)
    observed_id = _text(getattr(observed_message, "id", ""))
    if observed_id != message_id:
        mismatches.append("remote_id")
    read_receipt = {
        "provider": "agent_radio",
        "operation": "get_message",
        "resource_id": observed_id,
        "requested_remote_id": message_id,
        "observed_remote_id": observed_id,
        "coverage": "single",
        "account_id": str(observed.get("tenant_id") or ""),
        "tenant_id": str(observed.get("tenant_id") or ""),
        "fields": observed,
    }
    if mismatches:
        return _uncertain(
            operation_id=operation, payload_sha256=digest,
            message_id=message_id, message=observed,
            error_kind="readback_mismatch",
            error=(
                "The radio readback did not match the authorized message: "
                + ", ".join(mismatches)),
            verification={
                "status": "mismatch",
                "missing_fields": [],
                "mismatches": mismatches,
            },
            read_receipt=read_receipt,
            evidence={
                "kind": "radio_send_readback_mismatch",
                "remote_id": message_id,
                "mismatches": mismatches,
            },
        )
    return _applied(
        operation_id=operation, payload_sha256=digest,
        message_id=message_id, observed=observed,
        read_receipt=read_receipt,
    )
