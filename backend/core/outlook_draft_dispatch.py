"""Approved Outlook staged draft dispatch (internal).

The caller has already evaluated the canonical email policy, recorded human
approval for the exact immutable payload, and claimed the durable outbound
operation (status ``running``) under an execution id. This module owns only
the provider-effect staging; it never evaluates policy, creates approvals,
mints retries, or decides terminal task state.

Safety comes from four durable CAS markers on the SAME operation:

``outlook_dispatch_mailbox``
    The exact mailbox this operation may address: the scoped
    ``integration_tokens.id`` plus the stable Microsoft Graph /me id. It is
    reserved before any create/send and revalidated on resume. Operations
    whose provider phase already started without it are refused.

``outlook_dispatch_create_started``
    Reserved before the single create POST. Its presence means create was
    started, so a later call must never create another draft.

``outlook_dispatch_draft_id``
    The confirmed provider draft id, committed before any send reservation.

``outlook_dispatch_send_started``
    Reserved before the single send POST. Its presence means send was
    started, so a later call must never send again.

Every marker is written with :meth:`TaskLifecycle.attach_operation_field`'s
opt-in guarded attach (``expected_execution_id``), which refuses a cancelled
or mismatched claim and makes the reservation an atomic CAS.
"""
from __future__ import annotations

import inspect
import logging
from typing import Any, Dict, Mapping, Optional

from core.task_lifecycle import (
    TaskLifecycle,
    TaskLifecycleError,
    _approval_payload_hash,
    operation_binding_sha256,
)

logger = logging.getLogger(__name__)

CREATE_STARTED_FIELD = "outlook_dispatch_create_started"
DRAFT_ID_FIELD = "outlook_dispatch_draft_id"
SEND_STARTED_FIELD = "outlook_dispatch_send_started"
# The exact mailbox this operation may act through: the opaque
# ``integration_tokens.id`` selected by exact user/tenant/workspace scope plus
# the stable Microsoft Graph /me id observed for that row. It is written by
# the same guarded CAS as the phase markers and must exist before any provider
# draft/create/send. Operation ``account_id`` is the Atom actor, never a token
# row id.
MAILBOX_FIELD = "outlook_dispatch_mailbox"
# Explicit aliases used by callers/tests that name the marker by concept.
MAILBOX_BINDING_FIELD = MAILBOX_FIELD
OUTLOOK_MAILBOX_FIELD = MAILBOX_FIELD
# Read-only compatibility with an earlier/alternate spelling of the same
# marker. New writes always use MAILBOX_FIELD.
_MAILBOX_FIELDS = (
    MAILBOX_FIELD,
    "outlook_dispatch_mailbox_binding",
)
_MAILBOX_TOKEN_KEYS = ("token_row_id", "connection_id", "row_id")
_MAILBOX_GRAPH_KEYS = ("graph_user_id", "mailbox_id", "graph_id")

_SCOPE_KEYS = ("action_name", "workspace_id", "account_id")
_SCOPE_OPTIONAL_KEYS = ("authorization_ref",)
_PROVIDER_KEYS = frozenset({
    "user_id",
    "to_recipients",
    "cc_recipients",
    "bcc_recipients",
    "subject",
    "body",
    "conversation_id",
})
# A dedicated caller may bind extra approval-scope metadata (the invoice and
# Canvas draft identity) into the SAME approved payload digest. These fields
# are never sent to the provider; they exist so an approval cannot move to a
# different canvas/invoice with identical visible content.
_APPROVAL_METADATA_KEYS = frozenset({
    "canvas_id",
    "to",
    "cc",
    "thread_id",
    "reply_all",
    "attachment_ids",
    "attachment_hashes",
    "invoice",
    "native_draft",
})
_PAYLOAD_KEYS = _PROVIDER_KEYS | _APPROVAL_METADATA_KEYS
_TERMINAL_AUTHORIZATION = ("cancelled", "revoked")


class OutlookDispatchRefused(RuntimeError):
    """The durable operation does not authorize this provider effect."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _normalize_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise OutlookDispatchRefused("approved_payload_must_be_a_mapping")
    data = dict(payload)
    if set(data) - _PAYLOAD_KEYS:
        raise OutlookDispatchRefused("unsupported_payload_fields")

    user_id = data.get("user_id")
    if not isinstance(user_id, str) or not user_id.strip():
        raise OutlookDispatchRefused("payload_user_id_required")
    recipient_lists = {}
    for key in ("to_recipients", "cc_recipients", "bcc_recipients", "to", "cc"):
        if key not in data:
            continue
        value = data[key]
        if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value):
            raise OutlookDispatchRefused(f"payload_{key}_must_be_strings")
        recipient_lists[key] = value
    for canonical, alias, label in (
            ("to_recipients", "to", "to"),
            ("cc_recipients", "cc", "cc")):
        if (canonical in recipient_lists and alias in recipient_lists
                and recipient_lists[canonical] != recipient_lists[alias]):
            raise OutlookDispatchRefused(
                f"payload_conflicting_{label}_aliases")
    if not recipient_lists.get("to_recipients") and not recipient_lists.get("to"):
        raise OutlookDispatchRefused("payload_to_recipients_required")
    if not isinstance(data.get("subject"), str):
        raise OutlookDispatchRefused("payload_subject_must_be_a_string")
    if not isinstance(data.get("body"), str):
        raise OutlookDispatchRefused("payload_body_must_be_a_string")
    conversation_id = data.get("conversation_id")
    if conversation_id is not None and not isinstance(conversation_id, str):
        raise OutlookDispatchRefused(
            "payload_conversation_id_must_be_a_string")
    if data.get("attachment_ids") or data.get("attachment_hashes"):
        raise OutlookDispatchRefused("attachments_not_supported")
    return data


def _normalize_scope(scope: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(scope, Mapping):
        raise OutlookDispatchRefused("scope_must_be_a_mapping")
    data = dict(scope)
    if set(data) - set(_SCOPE_KEYS) - set(_SCOPE_OPTIONAL_KEYS):
        raise OutlookDispatchRefused("unsupported_scope_fields")
    normalized: Dict[str, Any] = {}
    for key in _SCOPE_KEYS:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise OutlookDispatchRefused(f"scope_{key}_required")
        normalized[key] = value
    if "authorization_ref" in data:
        reference = data["authorization_ref"]
        if reference is not None and not isinstance(reference, str):
            raise OutlookDispatchRefused(
                "scope_authorization_ref_must_be_a_string")
        normalized["authorization_ref"] = reference
    return normalized


def _operation(record: Any, operation_id: str) -> Dict[str, Any]:
    if not isinstance(record, dict):
        raise OutlookDispatchRefused("task_not_found")
    for operation in record.get("operations") or []:
        if (isinstance(operation, dict)
                and operation.get("operation_id") == operation_id):
            return operation
    raise OutlookDispatchRefused("operation_not_found")


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _profile_value(profile: Any, *keys: str) -> str:
    for key in keys:
        if isinstance(profile, Mapping):
            value = profile.get(key)
        else:
            value = getattr(profile, key, None)
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _accepts_parameter(method: Any, name: str) -> bool:
    """Whether a provider method can receive one explicit optional token."""
    try:
        parameters = inspect.signature(method).parameters
    except (TypeError, ValueError):
        return True
    return name in parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )


async def _invoke(method: Any, arguments: Dict[str, Any],
                  token: Optional[str], parameter: str) -> Any:
    """Call a provider method with the invocation token when it accepts it.

    Real connector methods take the token explicitly. Keeping this check lets
    older direct fakes and legacy callers stay source-compatible while the
    staged path still proves every provider request used the pinned token.
    """
    if token and _accepts_parameter(method, parameter):
        arguments = {**arguments, parameter: token}
    return await method(**arguments)


def mailbox_binding(operation: Mapping[str, Any]) -> tuple:
    """Return ``(field, normalized_binding)`` for an operation's mailbox.

    A present-but-malformed marker is returned as an empty normalized binding
    (never treated as absent), so a damaged durable record refuses instead of
    silently binding a new mailbox. ``account_id`` is deliberately ignored:
    it is the Atom actor, not a token row id.
    """
    if not isinstance(operation, Mapping):
        return None, None
    for field in _MAILBOX_FIELDS:
        if field not in operation:
            continue
        value = operation.get(field)
        if not isinstance(value, Mapping):
            return field, {}
        return field, {
            "token_row_id": _first_text(
                *(value.get(key) for key in _MAILBOX_TOKEN_KEYS)),
            "graph_user_id": _first_text(
                *(value.get(key) for key in _MAILBOX_GRAPH_KEYS)),
        }
    # A top-level split spelling is accepted for readback only.
    token_row_id = _first_text(operation.get("outlook_dispatch_token_row_id"))
    graph_user_id = _first_text(
        operation.get("outlook_dispatch_graph_user_id"),
        operation.get("outlook_dispatch_mailbox_id"),
    )
    if token_row_id or graph_user_id:
        return MAILBOX_FIELD, {
            "token_row_id": token_row_id,
            "graph_user_id": graph_user_id,
        }
    return None, None


def _operation_mailbox(operation_id: str, lifecycle: TaskLifecycle,
                       run_id: str) -> tuple:
    """Re-read the operation after a reservation race."""
    fresh = lifecycle.get_task(run_id) or {}
    try:
        fresh_operation = _operation(fresh, operation_id)
    except OutlookDispatchRefused:
        return None, None
    return mailbox_binding(fresh_operation)


def _expected_token_row_id(
    outlook_service: Any, connection_id: Optional[str],
) -> str:
    """The exact row this bound service addresses, when it exposes one."""
    supplied = _first_text(connection_id)
    service_row = _first_text(
        getattr(outlook_service, "token_row_id", None),
        getattr(outlook_service, "_token_row_id", None),
        getattr(outlook_service, "connection_id", None),
        getattr(outlook_service, "_bound_token_row_id", None),
    )
    if supplied and service_row and supplied != service_row:
        raise OutlookDispatchRefused("mailbox_scope_mismatch")
    return supplied or service_row


async def _pin_validated_access_token(
    outlook_service: Any, user_id: str,
) -> tuple:
    """Read one token, prove it via Graph /me, and pin it in memory.

    Returns ``(access_token, graph_user_id)``. The token is never persisted,
    logged, or copied into a result/receipt. The bound service has already
    revalidated the exact canonical row while resolving the token; proving
    /me additionally fixes the stable mailbox identity this operation may
    address.
    """
    getter = getattr(outlook_service, "_get_access_token", None)
    if not callable(getter):
        getter = getattr(outlook_service, "get_access_token", None)
    if not callable(getter):
        return None, None

    try:
        token = await getter(user_id)
    except Exception as exc:  # noqa: BLE001 — no provider effect yet
        logger.debug(
            "Outlook mailbox token lookup failed before staging: %s",
            type(exc).__name__)
        return None, None
    if not isinstance(token, str) or not token:
        return None, None

    profile_getter = getattr(outlook_service, "get_user_profile", None)
    if not callable(profile_getter):
        return token, None
    try:
        profile = await _invoke(
            profile_getter, {"user_id": user_id}, token, "token")
    except Exception as exc:  # noqa: BLE001 — no provider effect yet
        logger.debug(
            "Outlook mailbox /me validation failed before staging: %s",
            type(exc).__name__)
        return token, None
    graph_user_id = _profile_value(
        profile, "id", "graph_user_id", "mailbox_id")
    if not graph_user_id:
        return token, None

    # Memory-only for this invocation; never a DB write.
    try:
        outlook_service._pinned_access_token = token
    except Exception:
        pass
    return token, graph_user_id


def _mailbox_error(
    mailbox: Optional[Dict[str, str]], expected_token_row_id: str,
) -> Optional[str]:
    if mailbox is None:
        return "mailbox_binding_missing"
    if not mailbox.get("token_row_id") or not mailbox.get("graph_user_id"):
        return "mailbox_binding_invalid"
    if (expected_token_row_id
            and mailbox["token_row_id"] != expected_token_row_id):
        return "mailbox_scope_mismatch"
    return None


async def _ensure_mailbox_binding(
    *,
    lifecycle: TaskLifecycle,
    run_id: str,
    operation_id: str,
    execution_id: str,
    operation: Dict[str, Any],
    outlook_service: Any,
    user_id: str,
    connection_id: Optional[str],
    legacy_started: bool,
) -> tuple:
    """Return ``(token, mailbox)`` after the durable mailbox CAS.

    A new operation resolves the exact scoped row, proves it with Graph /me,
    then writes token-row + stable /me id before any create reservation. A
    resume validates that same binding. A legacy operation whose create/send
    phase already started but has no mailbox marker is refused: its credential
    cannot be proven to be the one that started the effect.
    """
    _, mailbox = mailbox_binding(operation)
    expected_token_row_id = _expected_token_row_id(
        outlook_service, connection_id)
    if mailbox is None:
        if legacy_started:
            raise OutlookDispatchRefused("mailbox_binding_missing")
        if not expected_token_row_id:
            raise OutlookDispatchRefused("mailbox_scope_unresolved")
        token, graph_user_id = await _pin_validated_access_token(
            outlook_service, user_id)
        if not token:
            raise OutlookDispatchRefused("mailbox_token_unavailable")
        if not graph_user_id:
            raise OutlookDispatchRefused("mailbox_identity_unavailable")

        candidate = {
            "token_row_id": expected_token_row_id,
            "graph_user_id": graph_user_id,
        }
        if _reserve(
            lifecycle,
            run_id,
            operation_id,
            execution_id,
            MAILBOX_FIELD,
            candidate,
        ):
            return token, candidate

        # A concurrent invocation may have won the absent-field CAS. Use the
        # winner only if it names the same row and the same /me identity we
        # just proved; otherwise this operation now belongs to another
        # mailbox and must be refused.
        _, mailbox = _operation_mailbox(operation_id, lifecycle, run_id)
        error = _mailbox_error(mailbox, expected_token_row_id)
        if error:
            raise OutlookDispatchRefused(error)
        if mailbox["graph_user_id"] != graph_user_id:
            raise OutlookDispatchRefused("mailbox_identity_mismatch")
        return token, mailbox

    error = _mailbox_error(mailbox, expected_token_row_id)
    if error:
        raise OutlookDispatchRefused(error)

    token, graph_user_id = await _pin_validated_access_token(
        outlook_service, user_id)
    if not token:
        raise OutlookDispatchRefused("mailbox_token_unavailable")
    if not graph_user_id:
        raise OutlookDispatchRefused("mailbox_identity_unavailable")
    if graph_user_id != mailbox["graph_user_id"]:
        raise OutlookDispatchRefused("mailbox_identity_mismatch")
    return token, mailbox


def _verify_operation(
    record: Dict[str, Any],
    operation: Dict[str, Any],
    *,
    execution_id: str,
    payload: Dict[str, Any],
    payload_hash: str,
    scope: Dict[str, Any],
) -> None:
    authorization = (record.get("task_revision") or {}).get("authorization")
    if authorization in _TERMINAL_AUTHORIZATION:
        raise OutlookDispatchRefused("task_authorization_cancelled")
    if operation.get("operation_type") != "outbound":
        raise OutlookDispatchRefused("operation_not_outbound")
    if operation.get("status") != "running":
        raise OutlookDispatchRefused("operation_not_running")
    if not isinstance(execution_id, str) or not execution_id:
        raise OutlookDispatchRefused("execution_claim_required")
    if operation.get("execution_id") != execution_id:
        raise OutlookDispatchRefused("execution_claim_mismatch")

    approval = operation.get("approval")
    request = operation.get("approval_request")
    if not isinstance(approval, dict) or not approval:
        raise OutlookDispatchRefused("approval_missing")
    if not str(approval.get("approved_by") or "").strip():
        raise OutlookDispatchRefused("approval_missing_approver")
    if not approval.get("approved_at"):
        raise OutlookDispatchRefused("approval_missing_timestamp")
    if approval.get("payload_sha256") != payload_hash:
        raise OutlookDispatchRefused("approval_payload_hash_mismatch")
    if operation.get("approved_payload_sha256") != payload_hash:
        raise OutlookDispatchRefused("approved_payload_hash_mismatch")
    if not isinstance(request, dict) or request.get(
            "payload_sha256") != payload_hash:
        raise OutlookDispatchRefused("approval_request_hash_mismatch")

    binding = operation.get("operation_binding")
    if not isinstance(binding, dict) or not binding:
        raise OutlookDispatchRefused("operation_scope_missing")
    for key in _SCOPE_KEYS:
        if str(binding.get(key) or "") != scope[key]:
            raise OutlookDispatchRefused("operation_scope_mismatch")
    if (scope.get("authorization_ref") is not None
            and str(binding.get("authorization_ref") or "")
            != scope["authorization_ref"]):
        raise OutlookDispatchRefused("operation_scope_mismatch")
    if str(payload.get("user_id") or "") != str(
            binding.get("account_id") or ""):
        raise OutlookDispatchRefused("payload_mailbox_scope_mismatch")


def _reserve(
    lifecycle: TaskLifecycle,
    run_id: str,
    operation_id: str,
    execution_id: str,
    field: str,
    value: Dict[str, Any],
) -> bool:
    """Atomically write one absent marker under the running claim."""
    try:
        lifecycle.attach_operation_field(
            run_id,
            operation_id,
            field,
            value,
            expected_execution_id=execution_id,
        )
        return True
    except TaskLifecycleError:
        return False


def _result(
    status: str,
    *,
    reason: Optional[str] = None,
    draft_id: Optional[str] = None,
    accepted: Optional[bool] = None,
    verified: bool = False,
    evidence: Optional[Dict[str, Any]] = None,
    provider_status: Optional[str] = None,
    http_status: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "draft_id": draft_id,
        "accepted": accepted,
        "verified": verified,
        "sent_items_verified": verified,
        "evidence": evidence,
        "provider_status": provider_status,
        "http_status": http_status,
    }


def _create_outcome(result: Any):
    if not isinstance(result, dict):
        return "unknown", "malformed_create_result", None, None
    status = result.get("status")
    draft_id = result.get("draft_id")
    if not isinstance(draft_id, str) or not draft_id:
        draft_id = None
    http_status = result.get("http_status")
    if status == "created" and draft_id:
        return "created", None, draft_id, http_status
    if status == "not_created":
        return (
            "not_created",
            str(result.get("reason") or "not_created"),
            draft_id,
            http_status,
        )
    return (
        "unknown",
        str(result.get("reason") or "unknown_create_outcome"),
        draft_id,
        http_status,
    )


async def _read_evidence(
    outlook_service: Any,
    user_id: str,
    draft_id: str,
    *,
    access_token: Optional[str] = None,
) -> tuple:
    try:
        evidence = await _invoke(
            outlook_service.get_sent_message_evidence,
            {"user_id": user_id, "immutable_message_id": draft_id},
            access_token,
            "access_token",
        )
    except Exception as exc:  # pragma: no cover - defensive only
        logger.debug(
            "Outlook sent-item evidence read failed: %s",
            type(exc).__name__)
        return None, False
    verified = bool(
        isinstance(evidence, dict) and evidence.get("resolved") is True)
    return evidence, verified


async def _send_outcome(
    outlook_service: Any,
    user_id: str,
    draft_id: str,
    sent: Any,
    *,
    access_token: Optional[str] = None,
) -> Dict[str, Any]:
    if not isinstance(sent, dict):
        return _result(
            "unknown",
            reason="malformed_send_result",
            draft_id=draft_id,
        )

    returned_id = sent.get("message_id")
    if isinstance(returned_id, str) and returned_id and returned_id != draft_id:
        return _result(
            "unknown",
            reason="send_message_id_mismatch",
            draft_id=draft_id,
            http_status=sent.get("http_status"),
        )

    status = sent.get("status")
    reason = sent.get("reason")
    http_status = sent.get("http_status")
    if status == "provider_accepted":
        evidence, verified = await _read_evidence(
            outlook_service, user_id, draft_id, access_token=access_token)
        return _result(
            "sent_verified" if verified else "send_accepted",
            reason=reason,
            draft_id=draft_id,
            accepted=True,
            verified=verified,
            evidence=evidence,
            provider_status=status,
            http_status=http_status,
        )
    if status == "not_sent":
        return _result(
            "not_sent",
            reason=reason,
            draft_id=draft_id,
            accepted=False,
            provider_status=status,
            http_status=http_status,
        )
    return _result(
        "unknown",
        reason=reason or "unknown_send_outcome",
        draft_id=draft_id,
        provider_status=status,
        http_status=http_status,
    )


async def _recover_started_send(
    outlook_service: Any,
    user_id: str,
    draft_id: str,
    *,
    access_token: Optional[str] = None,
) -> Dict[str, Any]:
    """A send was already reserved: read evidence, never send again."""
    evidence, verified = await _read_evidence(
        outlook_service, user_id, draft_id, access_token=access_token)
    if verified:
        return _result(
            "sent_verified",
            reason="send_phase_already_started",
            draft_id=draft_id,
            accepted=True,
            verified=True,
            evidence=evidence,
        )
    return _result(
        "unknown",
        reason="send_phase_already_started",
        draft_id=draft_id,
        evidence=evidence,
    )


_SENT_EVIDENCE_KEYS = (
    "status",
    "resolved",
    "message_id",
    "conversation_id",
    "internet_message_id",
    "sent_date_time",
    "received_date_time",
    "is_draft",
    "parent_folder_id",
    "sent_items_may_be_delayed",
    "reason",
    "http_status",
)
_EXACT_REPLY_EVIDENCE_KEYS = (
    "status",
    "resolved",
    "message_id",
    "conversation_id",
    "reply_message_id",
    "reply_sender",
    "reply_received_date_time",
    "reply_sent_date_time",
    "in_reply_to_matched",
    "pages_fetched",
    "candidates_examined",
    "match_count",
    "reason",
    "http_status",
    "anchor_reason",
    "sent_items_may_be_delayed",
)


def _typed_evidence(
    evidence: Any, allowed_keys: tuple,
) -> Optional[Dict[str, Any]]:
    """Copy only the typed correlation fields from provider evidence.

    Message bodies, raw Internet headers, access tokens and arbitrary provider
    fields are intentionally dropped: callers receive a fixed, read-only shape.
    """
    if not isinstance(evidence, Mapping):
        return None
    return {
        key: evidence[key]
        for key in allowed_keys
        if key in evidence
    }


def _recipient_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        direct = value.get("address")
        if isinstance(direct, str):
            return direct.strip()
        email = value.get("emailAddress")
        if isinstance(email, Mapping):
            address = email.get("address")
            if isinstance(address, str):
                return address.strip()
    return ""


def _approved_reply_recipient(binding: Mapping[str, Any]) -> str:
    """Return the one canonical approved ``arguments.to`` recipient.

    Native outbound operations record the exact approved recipients in
    ``operation_binding.arguments.to``. Reply evidence may address only that
    one recipient; this read-only API has no caller-supplied override.
    """
    arguments = binding.get("arguments")
    if not isinstance(arguments, Mapping):
        raise OutlookDispatchRefused("approved_recipient_missing")
    recipients = arguments.get("to")
    if not isinstance(recipients, list):
        raise OutlookDispatchRefused("approved_recipient_missing")
    addresses = []
    seen = set()
    for item in recipients:
        text = _recipient_text(item)
        normalized = text.casefold()
        if text and normalized not in seen:
            seen.add(normalized)
            addresses.append(text)
    if not addresses:
        raise OutlookDispatchRefused("approved_recipient_missing")
    if len(addresses) != 1:
        raise OutlookDispatchRefused("approved_recipient_ambiguous")
    return addresses[0]


def _evidence_result(
    *,
    kind: str,
    operation_id: str,
    draft_id: str,
    evidence: Optional[Dict[str, Any]],
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the only shape this read-only method ever returns."""
    verified = bool(
        isinstance(evidence, Mapping)
        and evidence.get("resolved") is True
        and evidence.get("status") in (None, "resolved")
    )
    if reason is None and isinstance(evidence, Mapping):
        reason = evidence.get("reason")
    if not verified and reason is None:
        reason = "evidence_unresolved"
    return {
        "status": (
            "reply_verified"
            if verified and kind == "reply"
            else "sent_verified"
            if verified
            else "unresolved"
        ),
        "kind": kind,
        "verified": verified,
        "sent_items_verified": verified if kind == "sent" else False,
        "direct_reply_verified": verified if kind == "reply" else False,
        "operation_id": operation_id,
        "draft_id": draft_id,
        "message_id": (
            evidence.get("message_id")
            if isinstance(evidence, Mapping)
            else draft_id
        ),
        "conversation_id": (
            evidence.get("conversation_id")
            if isinstance(evidence, Mapping)
            else None
        ),
        "reply_message_id": (
            evidence.get("reply_message_id")
            if isinstance(evidence, Mapping)
            else None
        ),
        "reply_sender": (
            evidence.get("reply_sender")
            if isinstance(evidence, Mapping)
            else None
        ),
        "reason": reason,
        "evidence": evidence,
    }


async def read_outlook_dispatch_evidence(
    lifecycle: TaskLifecycle,
    run_id: str,
    operation_id: str,
    *,
    actor_id: str,
    tenant_id: str,
    workspace_id: str,
    reply: bool = False,
) -> Dict[str, Any]:
    """Read typed evidence for one already-sent staged Outlook operation.

    This is a read-only probe. It never creates, sends, deletes, retries,
    refreshes a claim, or writes a durable marker. It validates the operation
    binding digest, proves the exact mailbox bound to this operation, pins that
    mailbox's validated access token in memory, and then performs exactly one
    evidence read:

    * sent mode (default): the operation must have a committed send marker and
      draft id; the evidence is Sent Items proof for that exact immutable id;
    * reply mode (``reply=True``): additionally requires exactly one canonical
      approved recipient from ``operation_binding.arguments.to`` and asks for
      exact ``In-Reply-To`` proof from that recipient.

    The caller supplies exactly the trusted actor, tenant and workspace; the
    operation binding must name the same actor and workspace, and the same
    tenant where recorded. A missing send marker, mismatched account/draft,
    missing mailbox binding or missing/ambiguous approved recipient is refused
    before any provider read. Returned evidence is a fixed typed shape with no
    access token, body, raw Internet headers, or arbitrary provider fields.
    """
    actor_id = _first_text(actor_id)
    tenant_id = _first_text(tenant_id)
    workspace_id = _first_text(workspace_id)

    if not actor_id:
        raise OutlookDispatchRefused("actor_required")
    if not tenant_id:
        raise OutlookDispatchRefused("tenant_required")
    if not workspace_id:
        raise OutlookDispatchRefused("workspace_required")

    reply_request = bool(reply)

    record = lifecycle.get_task(run_id)
    operation = _operation(record, operation_id)

    operation_type = operation.get("operation_type")
    if operation_type is not None and operation_type != "outbound":
        raise OutlookDispatchRefused("operation_not_outbound")

    binding = operation.get("operation_binding")
    if not isinstance(binding, Mapping) or not binding:
        raise OutlookDispatchRefused("operation_scope_missing")

    try:
        computed_binding_sha256 = operation_binding_sha256(dict(binding))
    except TaskLifecycleError as exc:
        raise OutlookDispatchRefused("operation_binding_invalid") from exc
    durable_binding_sha256 = _first_text(operation.get("binding_sha256"))
    if (not durable_binding_sha256
            or computed_binding_sha256 != durable_binding_sha256):
        raise OutlookDispatchRefused("operation_binding_hash_mismatch")

    bound_actor = _first_text(binding.get("account_id"))
    if bound_actor != actor_id:
        raise OutlookDispatchRefused("operation_scope_mismatch")
    bound_workspace = _first_text(binding.get("workspace_id"))
    if not bound_workspace or bound_workspace != workspace_id:
        raise OutlookDispatchRefused("operation_scope_mismatch")
    bound_tenant = _first_text(binding.get("tenant_id"))
    if bound_tenant and bound_tenant != tenant_id:
        raise OutlookDispatchRefused("operation_scope_mismatch")

    # The send marker is the durable proof that this operation actually
    # reached the provider send phase. Read-only evidence must never be issued
    # for a draft that was merely created or for a different draft id.
    send_started = operation.get(SEND_STARTED_FIELD)
    if send_started is None:
        raise OutlookDispatchRefused("send_marker_missing")
    draft_id = _first_text(operation.get(DRAFT_ID_FIELD))
    if not draft_id:
        raise OutlookDispatchRefused("draft_id_missing")
    if isinstance(send_started, Mapping):
        marked_draft = _first_text(send_started.get("draft_id"))
        if marked_draft and marked_draft != draft_id:
            raise OutlookDispatchRefused("draft_id_mismatch")
        marked_account = _first_text(
            send_started.get("account_id"),
            send_started.get("user_id"),
        )
        if marked_account and marked_account != actor_id:
            raise OutlookDispatchRefused("operation_scope_mismatch")

    requested_recipient: Optional[str] = None
    if reply_request:
        requested_recipient = _approved_reply_recipient(binding)

    _, mailbox = mailbox_binding(operation)
    if mailbox is None:
        raise OutlookDispatchRefused("mailbox_binding_missing")
    if not mailbox.get("token_row_id") or not mailbox.get("graph_user_id"):
        raise OutlookDispatchRefused("mailbox_binding_invalid")

    try:
        from integrations.outlook_service import OutlookService
        outlook_service = OutlookService.for_connection(
            connection_id=mailbox["token_row_id"],
            user_id=actor_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
    except Exception as exc:  # noqa: BLE001 — no provider effect yet
        logger.debug(
            "Outlook evidence service binding failed: %s",
            type(exc).__name__)
        raise OutlookDispatchRefused("mailbox_service_unavailable") from exc
    if outlook_service is None:
        raise OutlookDispatchRefused("mailbox_service_unavailable")

    expected_token_row_id = _expected_token_row_id(
        outlook_service, mailbox["token_row_id"])
    error = _mailbox_error(mailbox, expected_token_row_id)
    if error:
        raise OutlookDispatchRefused(error)

    token, graph_user_id = await _pin_validated_access_token(
        outlook_service, actor_id)
    if not token:
        raise OutlookDispatchRefused("mailbox_token_unavailable")
    if not graph_user_id:
        raise OutlookDispatchRefused("mailbox_identity_unavailable")
    if graph_user_id != mailbox["graph_user_id"]:
        raise OutlookDispatchRefused("mailbox_identity_mismatch")

    if reply_request:
        try:
            evidence = await _invoke(
                outlook_service.get_exact_reply_evidence,
                {
                    "user_id": actor_id,
                    "immutable_message_id": draft_id,
                    "expected_recipient": requested_recipient,
                },
                token,
                "access_token",
            )
        except Exception as exc:  # noqa: BLE001 — defensive read only
            logger.debug(
                "Outlook exact-reply evidence read failed: %s",
                type(exc).__name__)
            evidence = None
        typed = _typed_evidence(evidence, _EXACT_REPLY_EVIDENCE_KEYS)
        return _evidence_result(
            kind="reply",
            operation_id=operation_id,
            draft_id=draft_id,
            evidence=typed,
            reason=(None if typed is not None else "evidence_read_failed"),
        )

    evidence, _ = await _read_evidence(
        outlook_service,
        actor_id,
        draft_id,
        access_token=token,
    )
    typed = _typed_evidence(evidence, _SENT_EVIDENCE_KEYS)
    return _evidence_result(
        kind="sent",
        operation_id=operation_id,
        draft_id=draft_id,
        evidence=typed,
        reason=(None if typed is not None else "evidence_read_failed"),
    )


async def dispatch_approved_outlook_draft(
    *,
    lifecycle: TaskLifecycle,
    run_id: str,
    operation_id: str,
    execution_id: str,
    outlook_service: Any,
    payload: Mapping[str, Any],
    scope: Mapping[str, Any],
    connection_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create at most one Outlook draft and send it at most once.

    ``payload`` is the exact immutable mapping the caller approved; its hash
    must equal both the recorded approval request and the operation's
    approved payload digest. ``scope`` names the exact operation binding
    (``action_name``, ``workspace_id``, ``account_id``), and the payload's
    ``user_id`` must be that bound account.

    Before any create/send, the exact mailbox is durably bound on this same
    operation by the guarded CAS: the scoped ``integration_tokens.id`` plus
    the stable Microsoft Graph /me id. A resume revalidates that binding; a
    legacy operation with a started phase but no mailbox marker is refused.
    The access token proven by Graph /me is pinned in memory for the whole
    invocation and passed to every staged provider request, so a same-row
    credential rotation cannot change the credential between create and send.

    The two provider calls are each preceded by a durable CAS reservation on
    this same operation. Re-entering with either phase already started is a
    refusal to repeat that phase, including after a crash:

    * create started without a committed draft id -> ``unknown`` (the draft
      may exist, but its id cannot be recovered here);
    * draft id committed, send not started -> send the SAME draft once;
    * send started -> never resend; read sent-item evidence instead.

    The result keeps ``accepted`` (provider accepted the send request) and
    ``verified`` (Sent Items evidence resolved) separate, and always carries
    the known ``draft_id`` for later reconciliation. Access tokens are never
    returned, logged, or persisted.
    """
    approved = _normalize_payload(payload)
    expected_scope = _normalize_scope(scope)
    payload_hash = _approval_payload_hash(approved)

    record = lifecycle.get_task(run_id)
    operation = _operation(record, operation_id)
    _verify_operation(
        record,
        operation,
        execution_id=execution_id,
        payload=approved,
        payload_hash=payload_hash,
        scope=expected_scope,
    )

    create_started = operation.get(CREATE_STARTED_FIELD)
    draft_id = operation.get(DRAFT_ID_FIELD)
    send_started = operation.get(SEND_STARTED_FIELD)

    # A phase marker is bound to the approved payload that started it. A
    # later call with different content must not inherit an existing draft.
    if isinstance(create_started, dict) and create_started.get(
            "payload_sha256") not in (None, payload_hash):
        raise OutlookDispatchRefused("dispatch_payload_mismatch")
    if isinstance(send_started, dict) and send_started.get(
            "payload_sha256") not in (None, payload_hash):
        raise OutlookDispatchRefused("dispatch_payload_mismatch")

    legacy_started = (
        create_started is not None
        or bool(draft_id)
        or send_started is not None
    )
    pinned_token, _mailbox = await _ensure_mailbox_binding(
        lifecycle=lifecycle,
        run_id=run_id,
        operation_id=operation_id,
        execution_id=execution_id,
        operation=operation,
        outlook_service=outlook_service,
        user_id=approved["user_id"],
        connection_id=connection_id,
        legacy_started=legacy_started,
    )

    if create_started is None:
        if draft_id or send_started:
            raise OutlookDispatchRefused("inconsistent_dispatch_state")
        if not _reserve(
            lifecycle,
            run_id,
            operation_id,
            execution_id,
            CREATE_STARTED_FIELD,
            {"payload_sha256": payload_hash},
        ):
            raise OutlookDispatchRefused("create_reservation_conflict")

        created = await _invoke(
            outlook_service.create_draft_with_immutable_id,
            {
                "user_id": approved["user_id"],
                "to_recipients": list(
                    approved.get("to_recipients")
                    or approved.get("to") or []),
                "subject": approved["subject"],
                "body": approved["body"],
                "cc_recipients": (
                    approved.get("cc_recipients")
                    or approved.get("cc") or []),
                "bcc_recipients": approved.get("bcc_recipients") or [],
                "conversation_id": approved.get("conversation_id"),
            },
            pinned_token,
            "access_token",
        )
        create_state, reason, draft_id, http_status = _create_outcome(created)
        if create_state != "created":
            return _result(
                "not_created" if create_state == "not_created" else "unknown",
                reason=reason,
                draft_id=draft_id,
                http_status=http_status,
            )
        if not _reserve(
            lifecycle,
            run_id,
            operation_id,
            execution_id,
            DRAFT_ID_FIELD,
            draft_id,
        ):
            # The provider id is real but could not be committed. Never send
            # from an uncommitted identity; keep the id for reconciliation.
            return _result(
                "unknown",
                reason="draft_id_commit_failed",
                draft_id=draft_id,
                http_status=http_status,
            )
    elif not isinstance(draft_id, str) or not draft_id:
        # The create phase began but no confirmed draft id was committed.
        # Recreating could duplicate the draft, so stop here.
        return _result(
            "unknown",
            reason="create_phase_already_started",
        )

    if send_started is not None:
        return await _recover_started_send(
            outlook_service,
            approved["user_id"],
            draft_id,
            access_token=pinned_token,
        )

    if not _reserve(
        lifecycle,
        run_id,
        operation_id,
        execution_id,
        SEND_STARTED_FIELD,
        {"draft_id": draft_id, "payload_sha256": payload_hash},
    ):
        return _result(
            "draft_created",
            reason="send_reservation_conflict",
            draft_id=draft_id,
        )

    sent = await _invoke(
        outlook_service.send_existing_immutable_draft,
        {
            "user_id": approved["user_id"],
            "immutable_message_id": draft_id,
        },
        pinned_token,
        "access_token",
    )
    return await _send_outcome(
        outlook_service,
        approved["user_id"],
        draft_id,
        sent,
        access_token=pinned_token,
    )
