"""Deterministic invoice reconciliation over accepted evidence payloads.

This is a bookkeeping capability, not a provider action: it compares the
invoice, purchase order and receiving observations and either returns a
material total receipt or opens one targeted obligation. It never creates or
posts a bill.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Mapping, Optional

from core.assignment_executor import (
    NeedsContext,
    WaitingForExternal,
    register_assignment_adapter,
)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _payload(value: Any, key: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    nested = value.get(key)
    if isinstance(nested, Mapping):
        return dict(nested)
    return dict(value)


def _mapped(payload: Mapping[str, Any], fields: Mapping[str, str],
            canonical: str) -> Any:
    key = str((fields or {}).get(canonical) or canonical)
    if key in payload:
        return payload.get(key)
    return payload.get(canonical)


def _decimal(value: Any, field: str) -> Decimal:
    text = _text(value)
    if not text:
        raise NeedsContext({
            "concept": "invoice_field",
            "reason": f"the evidence has no {field}",
            "question": f"What is the authoritative {field}?",
            "next_retrieval": "read the authoritative invoice/receiving record",
            "kind": "missing_evidence",
        })
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise NeedsContext({
            "concept": "invoice_field",
            "reason": f"the evidence {field} is not a decimal",
            "question": f"What is the authoritative {field}?",
            "kind": "missing_evidence",
        }) from exc
    if not number.is_finite() or number < 0:
        raise NeedsContext({
            "concept": "invoice_field",
            "reason": f"the evidence {field} is not a finite nonnegative value",
            "question": f"What is the authoritative {field}?",
            "kind": "missing_evidence",
        })
    return number


async def _invoice_reconcile(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    invoice = _payload(inputs.get("invoice"), "invoice")
    purchase = _payload(inputs.get("purchase_order"), "purchase_order")
    receiving = _payload(inputs.get("receiving"), "receiving")
    fields = {
        "invoice": inputs.get("invoice_fields") or {},
        "purchase": inputs.get("purchase_order_fields") or {},
        "receiving": inputs.get("receiving_fields") or {},
    }
    invoice_qty = _decimal(
        _mapped(invoice, fields["invoice"], "quantity"), "invoice quantity")
    received_qty = _decimal(
        _mapped(receiving, fields["receiving"], "received_quantity"),
        "received quantity")
    unit_price = _decimal(
        _mapped(invoice, fields["invoice"], "unit_price"), "invoice unit price")
    freight = _decimal(
        _mapped(invoice, fields["invoice"], "freight"), "invoice freight")
    currency = _text(
        _mapped(invoice, fields["invoice"], "currency")
        or inputs.get("currency")).upper()
    if not currency:
        raise NeedsContext({
            "concept": "currency",
            "reason": "the invoice does not state an explicit currency",
            "question": "Which currency governs this invoice?",
            "kind": "business_decision",
        })
    po_id = _text(_mapped(purchase, fields["purchase"], "po_id"))
    invoice_po = _text(_mapped(invoice, fields["invoice"], "po_id"))
    receiving_po = _text(
        _mapped(receiving, fields["receiving"], "po_id"))
    if invoice_po and po_id and invoice_po != po_id:
        raise NeedsContext({
            "concept": "invoice_identity",
            "reason": "invoice evidence belongs to a different purchase order",
            "question": "Which invoice belongs to this purchase order?",
            "checked_evidence": [f"po={po_id}", f"invoice_po={invoice_po}"],
            "kind": "missing_evidence",
        })
    if po_id and receiving_po and po_id != receiving_po:
        raise NeedsContext({
            "concept": "receiving_identity",
            "reason": "receiving evidence belongs to a different purchase order",
            "question": "Which receiving record belongs to this purchase order?",
            "checked_evidence": [f"po={po_id}", f"receiving_po={receiving_po}"],
            "kind": "missing_evidence",
        })
    if invoice_qty != received_qty:
        raise NeedsContext({
            "concept": "invoice_quantity",
            "reason": (
                f"invoice quantity {invoice_qty} differs from received "
                f"quantity {received_qty}"),
            "question": (
                "The invoice does not match received quantities. Provide the "
                "authoritative corrected invoice."),
            "next_retrieval": "request the supplied corrected invoice version",
            "kind": "missing_evidence",
            "waiting": {
                "state": "waiting_for_external",
                "party": "supplier",
                "resume_on": "corrected_invoice",
                "detail": "invoice/receiving quantity mismatch",
                "correlation_id": (
                    f"invoice-correction:"
                    f"{_text(_mapped(invoice, fields['invoice'], 'invoice_id')) or po_id}"),
            },
        })
    total = (invoice_qty * unit_price + freight).quantize(Decimal("0.01"))
    invoice_id = (
        _text(_mapped(invoice, fields["invoice"], "invoice_id")) or po_id)
    vendor_id = _text(_mapped(purchase, fields["purchase"], "vendor_id"))
    account = _text(_mapped(invoice, fields["invoice"], "account"))
    period = _text(_mapped(invoice, fields["invoice"], "period"))
    bill = {
        "vendor_id": vendor_id,
        "po_id": po_id,
        "invoice_id": invoice_id,
        "quantity": str(invoice_qty),
        "unit_price": str(unit_price),
        "freight": str(freight),
        "currency": currency,
        "total": str(total),
    }
    if account:
        bill["account"] = account
    if period:
        bill["period"] = period
    return {
        "status": "applied",
        "summary": (
            f"reconciled invoice total {total} {currency} against received "
            f"quantity {received_qty}"),
        "value": str(total),
        "unit": currency,
        "currency": currency,
        "invoice_quantity": str(invoice_qty),
        "received_quantity": str(received_qty),
        "purchase_order_id": po_id or None,
        "receiving_purchase_order_id": receiving_po or None,
        "verification": {
            "status": "verified",
            "resource_id": _text(_mapped(invoice, fields["invoice"],
                                        "resource_id")) or invoice_id,
            "version": _text(_mapped(invoice, fields["invoice"], "version")),
            "coverage": {"complete": True, "truncated": False},
        },
        "data": {
            "total": str(total),
            "currency": currency,
            "quantity": str(invoice_qty),
            "unit_price": str(unit_price),
            "freight": str(freight),
            "vendor_id": vendor_id,
            "po_id": po_id,
            "invoice_id": invoice_id,
            "invoice_version": _text(
                _mapped(invoice, fields["invoice"], "version")),
            "receiving_version": _text(
                _mapped(receiving, fields["receiving"], "version")),
            "bill": bill,
        },
        "evidence_refs": [
            {"kind": "bookkeeping_reconciliation",
             "resource_id": _text(
                 _mapped(invoice, fields["invoice"], "resource_id"))
             or "invoice",
             "version": _text(
                 _mapped(invoice, fields["invoice"], "version"))},
        ],
    }


def _persisted_step_operation_id(context: Mapping[str, Any]) -> str:
    """Return the executor-persisted operation id for this step.

    The operation id is execution identity, not a business argument.  The
    executor binds it to the durable step before invoking an adapter, so it is
    read only from the execution context (``context["step"]``) with the
    executor's compatibility fallback.  Adapter inputs are never consulted.
    """
    step = context.get("step")
    step = step if isinstance(step, Mapping) else {}
    return (
        _text(step.get("operation_id"))
        or _text(context.get("operation_id"))
    )


def _persisted_execution_authority(
    context: Mapping[str, Any],
) -> tuple[str, str, str]:
    """Return actor/tenant/workspace from the durable assignment context.

    Adapter inputs are untrusted business arguments.  Scope is read only from
    the execution context the executor built from the persisted assignment
    (and its provenance), never from an input override.
    """
    assignment = context.get("assignment")
    assignment = assignment if isinstance(assignment, Mapping) else {}
    provenance = context.get("provenance")
    provenance = provenance if isinstance(provenance, Mapping) else {}
    if not provenance:
        nested = assignment.get("provenance")
        provenance = nested if isinstance(nested, Mapping) else {}

    actor_id = (
        _text(context.get("employee_id"))
        or _text(context.get("actor_id"))
        or _text(provenance.get("actor_id"))
        or _text(provenance.get("user_id"))
        or _text(assignment.get("employee_id"))
    )
    tenant_id = (
        _text(context.get("tenant_id"))
        or _text(assignment.get("tenant_id"))
        or _text(provenance.get("tenant_id"))
    )
    workspace_id = (
        _text(context.get("workspace_id"))
        or _text(assignment.get("workspace_id"))
        or _text(provenance.get("workspace_id"))
    )
    return actor_id, tenant_id, workspace_id


_INVOICE_LOOKUP_ADAPTER = "invoice.lookup"
# Bounded ledger facts published by one lookup.  Everything else, including
# any customer join key, is deliberately not part of the adapter result.
_INVOICE_LOOKUP_FACTS = (
    "invoice_id",
    "invoice_number",
    "status",
    "amount",
    "currency",
    "due_date",
    "as_of",
    "workspace_id",
    "tenant_id",
    "workspace_name",
    "source",
    "source_table",
    "recorded_paid",
    "is_overdue",
    "days_overdue",
    "days_until_due",
    "aging_bucket",
)


def _invoice_lookup_gap(
    concept: str, reason: str, question: str, *, checked: Any = None,
) -> None:
    gap = {
        "concept": concept,
        "reason": reason,
        "question": question,
        "next_retrieval": "read the authoritative invoice record",
        "kind": "missing_evidence",
    }
    if checked:
        gap["checked_evidence"] = list(checked)
    raise NeedsContext(gap)


async def _invoice_lookup(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Read one recorded invoice by its exact number in the persisted scope.

    Read-only: caller-supplied scope and operation ids are never consulted.
    The exact invoice number is passed through unchanged to the existing
    ledger read, which owns all business decisions.  A known evidence refusal
    becomes a safe missing-evidence question; infrastructure faults propagate.
    """
    invoice_number = inputs.get("invoice_number")
    if type(invoice_number) is not str or invoice_number == "":
        _invoice_lookup_gap(
            "invoice_identity",
            "the lookup step has no exact nonempty invoice number",
            "Which recorded invoice should this lookup use?",
            checked=["invoice_number=missing"],
        )

    actor_id, tenant_id, workspace_id = _persisted_execution_authority(
        context)
    missing = [
        name for name, value in (
            ("actor_id", actor_id),
            ("tenant_id", tenant_id),
            ("workspace_id", workspace_id),
        ) if not value
    ]
    if missing:
        _invoice_lookup_gap(
            "authenticated_scope",
            "the persisted execution context has no " + ", ".join(missing),
            "Which authenticated actor, tenant and workspace authorize this "
            "invoice lookup?",
            checked=[f"missing={name}" for name in missing],
        )

    operation_id = _persisted_step_operation_id(context)
    if not operation_id:
        _invoice_lookup_gap(
            "execution_identity",
            "the persisted lookup step has no operation id",
            "Which persisted assignment operation authorizes this invoice "
            "lookup?",
            checked=["operation_id=missing"],
        )

    from accounting.invoice_evidence import (
        InvoiceEvidenceError,
        read_invoice_evidence,
    )
    from core.database import get_db_session

    try:
        with get_db_session() as db:
            recorded = read_invoice_evidence(
                db,
                actor_id=actor_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                invoice_number=invoice_number,
            )
    except InvoiceEvidenceError as exc:
        # Only the helper's stable refusal type becomes missing evidence.
        # Transaction, connection and other infrastructure faults propagate.
        reason = _text(getattr(exc, "reason", "")) or (
            "invoice_evidence_refused")
        _invoice_lookup_gap(
            "invoice_evidence",
            f"the scoped invoice lookup was refused: {reason}",
            "Which recorded invoice should this lookup use?",
            checked=[f"refused={reason}"],
        )

    facts = {
        key: recorded.get(key) for key in _INVOICE_LOOKUP_FACTS
        if key in recorded
    }
    invoice_ref = {
        "kind": "invoice",
        "resource_id": facts.get("invoice_id"),
        "invoice_number": facts.get("invoice_number"),
        "workspace_id": facts.get("workspace_id"),
        "tenant_id": facts.get("tenant_id"),
        "source": facts.get("source"),
        "source_table": facts.get("source_table"),
        "status": facts.get("status"),
        "recorded_paid": facts.get("recorded_paid"),
    }
    return {
        "status": "applied",
        "action_result": "applied",
        "summary": (
            f"read invoice {facts.get('invoice_number')} with recorded status "
            f"{facts.get('status')}"),
        "operation_id": operation_id,
        "invoice": dict(facts),
        "invoice_id": facts.get("invoice_id"),
        "invoice_number": facts.get("invoice_number"),
        "invoice_status": facts.get("status"),
        "recorded_paid": facts.get("recorded_paid"),
        "data": dict(facts),
        "provider_state": "read_only",
        "send_performed": False,
        "payment": False,
        "settled": False,
        "evidence": [invoice_ref],
        "evidence_refs": [invoice_ref],
        "verification": {
            "status": "verified",
            "resource_id": facts.get("invoice_id"),
            "version": facts.get("as_of"),
            "coverage": {"complete": True, "truncated": False},
        },
    }


_INVOICE_PREPARE_ADAPTER = "invoice.prepare_reminder"
_INVOICE_SEND_ADAPTER = "invoice.send_reminder"
_INVOICE_REPLY_ADAPTER = "invoice.wait_for_reply"
_INVOICE_SEND_ADAPTERS = frozenset({
    "invoice.send_reminder",
    "invoice.send_reminder_outlook",
    "invoice.dispatch_reminder",
})
# A reply probe is time-bounded.  The wait carries two clocks: ``deadline`` is
# the next executor wake and must stay in the future on every no-proof probe,
# while ``expires_at`` is the stable business expiry of the whole wait.  The
# executor's ``_resolve_waiting`` treats ``deadline`` as "wake now", so reusing
# an elapsed deadline would re-enter this adapter immediately in one resume.
_INVOICE_REPLY_RECHECK_SECONDS = 15 * 60
_INVOICE_REPLY_EXPIRY_SECONDS = 24 * 60 * 60
# Refusals that mean the persisted send source itself is missing, ambiguous or
# outside the authenticated scope.  These are integrity failures, never a
# reason to keep waiting.  Other read failures are transient.
_INVOICE_REPLY_SOURCE_REFUSALS = frozenset({
    "actor_required",
    "tenant_required",
    "workspace_required",
    "task_not_found",
    "operation_not_found",
    "operation_not_outbound",
    "operation_scope_missing",
    "operation_binding_invalid",
    "operation_binding_hash_mismatch",
    "operation_scope_mismatch",
    "send_marker_missing",
    "draft_id_missing",
    "draft_id_mismatch",
    "approved_recipient_missing",
    "approved_recipient_ambiguous",
    "mailbox_binding_missing",
    "mailbox_binding_invalid",
    "mailbox_scope_mismatch",
    "mailbox_identity_mismatch",
    "mailbox_identity_unavailable",
})


def _raw_text(value: Any) -> str:
    """Return content for exact comparison without trimming it."""
    return "" if value is None else str(value)


def _text_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    text = _text(value)
    return [item.strip() for item in text.split(",") if item.strip()]


def _draft_content(draft: Any) -> Dict[str, Any]:
    """Canonical visible draft fields, accepting native and route shapes."""
    source = draft if isinstance(draft, Mapping) else {}
    to_value = source.get("to") if "to" in source else source.get("to_emails")
    cc_value = source.get("cc") if "cc" in source else source.get("cc_emails")
    return {
        "to": _text_list(to_value),
        "cc": _text_list(cc_value),
        "subject": _raw_text(source.get("subject")),
        "body": _raw_text(source.get("body")),
    }


def _native_content(draft: Any) -> Dict[str, str]:
    content = _draft_content(draft)
    return {
        "to": ", ".join(content["to"]),
        "cc": ", ".join(content["cc"]),
        "subject": content["subject"],
        "body": content["body"],
    }


def _same_amount(left: Any, right: Any) -> bool:
    try:
        return Decimal(_text(left)) == Decimal(_text(right))
    except (InvalidOperation, ValueError):
        return _text(left) == _text(right)


def _invoice_evidence_gap(
    concept: str, reason: str, question: str, *, checked: Any = None,
) -> None:
    gap = {
        "concept": concept,
        "reason": reason,
        "question": question,
        "next_retrieval": (
            "resume the completed invoice reminder preparation step"),
        "kind": "missing_evidence",
    }
    if checked:
        gap["checked_evidence"] = list(checked)
    raise NeedsContext(gap)


def _trusted_invoice_draft(context: Mapping[str, Any]) -> Dict[str, Any]:
    """Return the exact persisted native draft produced by prepare_reminder.

    The result is read only from the durable assignment/step context.  Caller
    inputs are never used to select the invoice, canvas, operation, receipt or
    content: those are execution facts recorded by the local preparation
    adapter.  Ambiguous or incomplete evidence is refused rather than guessed.
    """
    assignment = context.get("assignment")
    assignment = assignment if isinstance(assignment, Mapping) else {}
    current = context.get("step")
    current = current if isinstance(current, Mapping) else {}

    steps = [
        step for step in (assignment.get("steps") or [])
        if isinstance(step, Mapping)
    ]
    dependency_ids = {
        _text(item) for item in (current.get("depends_on") or [])
        if _text(item)
    }

    if steps:
        candidates = [
            step for step in steps
            if _text(step.get("adapter")) == _INVOICE_PREPARE_ADAPTER
        ]
    else:
        # Direct adapter tests may pass only previous_results.  They still
        # have to name the completed dependency explicitly.
        previous = context.get("previous_results")
        previous = previous if isinstance(previous, Mapping) else {}
        dependency_ids = dependency_ids or (
            {_text(key) for key in previous if _text(key)}
            if len(previous) == 1 else set())
        candidates = []
        for step_id in dependency_ids:
            result = previous.get(step_id)
            if isinstance(result, Mapping):
                candidates.append({
                    "step_id": step_id,
                    "status": "applied",
                    "result": dict(result),
                })

    applied = [
        step for step in candidates
        if _text(step.get("status") or "applied") in ("applied", "skipped")
    ]
    if dependency_ids:
        direct = [
            step for step in applied
            if _text(step.get("step_id")) in dependency_ids
        ]
        if direct:
            applied = direct
    if len(applied) != 1:
        _invoice_evidence_gap(
            "invoice_draft_evidence",
            ("the send step has no unique completed invoice reminder draft"
             if not applied else
             "the send step has more than one possible invoice reminder draft"),
            "Which prepared invoice reminder draft was approved for sending?",
            checked=[f"candidates={len(applied)}"],
        )
    step = applied[0]
    result = step.get("result")
    if not isinstance(result, Mapping):
        _invoice_evidence_gap(
            "invoice_draft_evidence",
            "the invoice reminder step has no persisted result",
            "Which prepared invoice reminder draft was approved for sending?",
        )
    data = result.get("data")
    data = data if isinstance(data, Mapping) else {}
    draft = result.get("draft")
    draft = dict(draft) if isinstance(draft, Mapping) else {}
    invoice_raw = data.get("invoice") or result.get("invoice")
    invoice_raw = invoice_raw if isinstance(invoice_raw, Mapping) else {}

    refs = [
        dict(ref) for ref in (step.get("evidence_refs")
                              or result.get("evidence_refs") or [])
        if isinstance(ref, Mapping)
    ]
    canvas_ref = next(
        (ref for ref in refs if _text(ref.get("kind")) == "canvas"), {})
    invoice_ref = next(
        (ref for ref in refs if _text(ref.get("kind")) == "invoice"), {})
    draft_ref = next(
        (ref for ref in refs if _text(ref.get("kind")) == "draft"), {})

    receipt = data.get("receipt") or canvas_ref.get("receipt")
    receipt = dict(receipt) if isinstance(receipt, Mapping) else {}
    receipt_draft = receipt.get("draft")
    receipt_draft = (
        dict(receipt_draft) if isinstance(receipt_draft, Mapping) else {})
    verification = (
        data.get("verification") or canvas_ref.get("verification")
        or result.get("verification"))
    verification = (
        dict(verification) if isinstance(verification, Mapping) else {})

    canvas_id = _text(
        data.get("canvas_id") or draft.get("canvas_id")
        or canvas_ref.get("canvas_id"))
    audit_id = _text(
        data.get("audit_id") or draft.get("audit_id")
        or canvas_ref.get("audit_id"))
    operation_id = _text(
        data.get("operation_id") or draft.get("operation_id")
        or canvas_ref.get("operation_id"))
    draft_revision = _text(
        draft.get("draft_revision") or data.get("draft_revision")
        or step.get("artifact_revision") or draft_ref.get("revision"))
    draft_id = _text(
        canvas_ref.get("draft_id") or receipt_draft.get("draft_id")
        or draft.get("draft_id"))
    material_sha256 = _text(
        canvas_ref.get("material_sha256") or data.get("material_sha256")
        or receipt.get("material_sha256"))
    thread_id = _text(
        canvas_ref.get("thread_id") or receipt.get("thread_id")
        or data.get("thread_id"))

    invoice: Dict[str, Any] = {}
    if invoice_ref:
        invoice.update({
            "invoice_id": _text(invoice_ref.get("resource_id")),
            "invoice_number": _text(invoice_ref.get("invoice_number")),
            "source": _text(invoice_ref.get("source")),
            "source_table": _text(invoice_ref.get("source_table")),
            "workspace_id": _text(invoice_ref.get("workspace_id")),
            "tenant_id": _text(invoice_ref.get("tenant_id")),
            "amount": _text(invoice_ref.get("amount")),
            "currency": _text(invoice_ref.get("currency")),
            "due_date": _text(invoice_ref.get("due_date")),
            "status": _text(invoice_ref.get("status")),
            "recorded_paid": invoice_ref.get("recorded_paid"),
        })
    invoice.update({
        key: value for key, value in invoice_raw.items()
        if value is not None
    })
    invoice.setdefault("status", "open")
    invoice.setdefault("recorded_paid", False)

    content = _draft_content(draft)
    missing = [
        name for name, value in (
            ("canvas_id", canvas_id),
            ("audit_id", audit_id),
            ("prepare_operation_id", operation_id),
            ("draft_revision", draft_revision),
            ("invoice_id", _text(invoice.get("invoice_id"))),
            ("invoice_number", _text(invoice.get("invoice_number"))),
            ("amount", _text(invoice.get("amount"))),
            ("currency", _text(invoice.get("currency"))),
            ("due_date", _text(invoice.get("due_date"))),
            ("recipient", content["to"]),
            ("subject", content["subject"]),
            ("body", content["body"]),
            ("receipt", receipt),
            ("verification", verification),
        ) if not value
    ]
    if missing:
        _invoice_evidence_gap(
            "invoice_draft_evidence",
            "the prepared invoice reminder evidence is incomplete",
            "Which exact prepared invoice reminder draft was approved?",
            checked=[f"missing={name}" for name in missing],
        )

    disagreements = []
    if _text(canvas_ref.get("canvas_id")) and \
            _text(canvas_ref.get("canvas_id")) != canvas_id:
        disagreements.append("canvas_id")
    if _text(canvas_ref.get("audit_id")) and \
            _text(canvas_ref.get("audit_id")) != audit_id:
        disagreements.append("audit_id")
    if _text(canvas_ref.get("operation_id")) and \
            _text(canvas_ref.get("operation_id")) != operation_id:
        disagreements.append("operation_id")
    if _text(draft.get("canvas_id")) and \
            _text(draft.get("canvas_id")) != canvas_id:
        disagreements.append("draft_canvas_id")
    if _text(draft.get("audit_id")) and \
            _text(draft.get("audit_id")) != audit_id:
        disagreements.append("draft_audit_id")
    if _text(draft.get("operation_id")) and \
            _text(draft.get("operation_id")) != operation_id:
        disagreements.append("draft_operation_id")
    artifact = result.get("artifact")
    artifact = artifact if isinstance(artifact, Mapping) else {}
    if _text(artifact.get("revision")) and \
            _text(artifact.get("revision")) != draft_revision:
        disagreements.append("artifact_revision")
    if _text(receipt.get("operation_id")) != operation_id:
        disagreements.append("receipt_operation_id")
    if (_text(canvas_ref.get("material_sha256"))
            and material_sha256
            and _text(canvas_ref.get("material_sha256")) != material_sha256):
        disagreements.append("material_sha256")
    if (_text(receipt.get("material_sha256"))
            and material_sha256
            and _text(receipt.get("material_sha256")) != material_sha256):
        disagreements.append("receipt_material_sha256")
    if _text(verification.get("status")).lower() != "verified":
        disagreements.append("verification")
    if _text(data.get("provider_state")).lower() not in ("", "not_sent"):
        disagreements.append("provider_state")
    if data.get("send_performed") is True or draft.get("send_performed") is True:
        disagreements.append("send_performed")
    if draft.get("draft_only") is False:
        disagreements.append("draft_only")
    if receipt_draft and _draft_content(receipt_draft) != content:
        disagreements.append("receipt_content")
    if disagreements:
        _invoice_evidence_gap(
            "invoice_draft_evidence",
            "the prepared invoice reminder evidence is not internally exact",
            "Which exact prepared invoice reminder draft was approved?",
            checked=[f"disagreement={name}" for name in disagreements],
        )

    return {
        "step_id": _text(step.get("step_id")),
        "step_operation_id": _text(step.get("operation_id")),
        "operation_id": operation_id,
        "canvas_id": canvas_id,
        "audit_id": audit_id,
        "draft_id": draft_id,
        "draft_revision": draft_revision,
        "material_sha256": material_sha256,
        "thread_id": thread_id,
        "draft": draft,
        "content": content,
        "invoice": dict(invoice),
        "receipt": receipt,
        "verification": verification,
        "evidence_refs": refs,
    }


def _canonical_send_payload(
    payload: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    actor_id: str,
) -> Dict[str, Any]:
    """Bind the payload to the exact post-formatting visible material.

    The executor's preparation applies the teaching/protocol formatting. The
    Canvas send path additionally applies the user's current styled signature
    (and may replace an agent sign-off). Approval must cover that final body,
    not the pre-signature text, so we run the same canonicalisation here. A
    preference/signature change after approval then changes the payload hash
    or the send preflight refuses before any provider request.
    """
    data = dict(payload)
    to_emails = list(
        data.get("to_recipients") or data.get("to") or [])
    cc_emails = list(
        data.get("cc_recipients") or data.get("cc") or [])
    subject = data.get("subject") or ""
    body = data.get("body") or ""
    agent_id = _text(context.get("agent_id"))
    if agent_id:
        from core.canvas_email_service import EmailCanvasService
        from core.database import get_db_session

        try:
            with get_db_session() as db:
                content = EmailCanvasService(
                    db).canonical_outbound_content(
                        user_id=actor_id,
                        agent_id=agent_id,
                        to_emails=to_emails,
                        cc_emails=cc_emails,
                        subject=subject,
                        body=body,
                    )
        except Exception as exc:  # noqa: BLE001 — approval cannot be bound
            raise NeedsContext({
                "concept": "email_formatting",
                "reason": (
                    "the canonical post-formatting body and signature could "
                    f"not be resolved: {type(exc).__name__}: {exc}"),
                "question": (
                    "Which exact formatted reminder body and signature should "
                    "be approved?"),
                "next_retrieval": (
                    "re-authenticate the assignment owner and retry the "
                    "reminder preparation"),
                "kind": "missing_evidence",
            }) from exc
    else:
        content = {
            "to": to_emails,
            "cc": cc_emails,
            "subject": str(subject or ""),
            "body": str(body or ""),
        }
    data["user_id"] = actor_id
    data["to_recipients"] = list(content["to"])
    data["cc_recipients"] = list(content["cc"])
    data["bcc_recipients"] = list(data.get("bcc_recipients") or [])
    data["to"] = list(content["to"])
    data["cc"] = list(content["cc"])
    data["subject"] = content["subject"]
    data["body"] = content["body"]
    return data


def _invoice_send_reminder_prepare(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Prepare the approval-bound Outlook send from the trusted native draft.

    ``inputs`` are deliberately ignored for authority.  The approved payload
    is the previous operation-bound invoice reminder draft plus an invoice and
    native-draft binding, so an approval names exact persisted evidence rather
    than caller-supplied canvas ids, recipients or content.
    """
    from core.assignment_executor import _outlook_send_prepare

    actor_id, _tenant_id, _workspace_id = _persisted_execution_authority(
        context)
    trusted = _trusted_invoice_draft(context)
    draft = trusted["draft"]
    prepared = _outlook_send_prepare({
        "canvas_id": trusted["canvas_id"],
        "to": list(trusted["content"]["to"]),
        "cc": list(trusted["content"]["cc"]),
        "subject": trusted["content"]["subject"],
        "body": trusted["content"]["body"],
        "draft_revision": trusted["draft_revision"],
    }, context)
    payload = _canonical_send_payload(
        dict(prepared.get("payload") or {}), context, actor_id=actor_id)
    invoice = trusted["invoice"]
    payload["invoice"] = {
        key: invoice.get(key) for key in (
            "source", "source_table", "invoice_id", "invoice_number",
            "workspace_id", "tenant_id", "amount", "currency", "due_date",
            "status", "recorded_paid",
        )
    }
    payload["native_draft"] = {
        "canvas_id": trusted["canvas_id"],
        "audit_id": trusted["audit_id"],
        "operation_id": trusted["operation_id"],
        "draft_id": trusted["draft_id"],
        "draft_revision": trusted["draft_revision"],
        "material_sha256": trusted["material_sha256"],
        "step_id": trusted["step_id"],
    }
    return {
        "payload": payload,
        "artifact_revision": trusted["draft_revision"],
        "requested_by": (
            _text(context.get("employee_id"))
            or _text((context.get("assignment") or {}).get("employee_id"))
        ),
    }


def _invoice_send_refusal(
    message: str,
    *,
    reason: str,
    trusted: Optional[Mapping[str, Any]] = None,
    mismatches: Optional[list[Dict[str, Any]]] = None,
    error_class: str = "invoice_dispatch_refused",
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    trusted = trusted if isinstance(trusted, Mapping) else {}
    invoice = dict(trusted.get("invoice") or {})
    mismatches = list(mismatches or [])
    evidence = []
    if trusted:
        evidence = [
            {
                "kind": "invoice",
                "resource_id": _text(invoice.get("invoice_id")),
                "invoice_number": _text(invoice.get("invoice_number")),
                "workspace_id": _text(invoice.get("workspace_id")),
                "tenant_id": _text(invoice.get("tenant_id")),
                "amount": _text(invoice.get("amount")),
                "currency": _text(invoice.get("currency")),
                "due_date": _text(invoice.get("due_date")),
                "status": _text(invoice.get("status")),
            },
            {
                "kind": "canvas",
                "canvas_id": _text(trusted.get("canvas_id")),
                "audit_id": _text(trusted.get("audit_id")),
                "operation_id": _text(trusted.get("operation_id")),
                "draft_id": _text(trusted.get("draft_id")),
                "draft_revision": _text(trusted.get("draft_revision")),
                "material_sha256": _text(trusted.get("material_sha256")),
                "verification": dict(trusted.get("verification") or {}),
            },
        ]
    data = {
        "resolution": "refused",
        "reason": str(reason),
        "invoice": invoice,
        "canvas_id": _text(trusted.get("canvas_id")) or None,
        "audit_id": _text(trusted.get("audit_id")) or None,
        "operation_id": _text(trusted.get("operation_id")) or None,
        "draft_revision": _text(trusted.get("draft_revision")),
        "provider_state": "not_sent",
        "send_performed": False,
        "mismatches": mismatches,
    }
    if extra:
        data.update(dict(extra))
    return {
        "status": "failed",
        "action_result": "proven_not_applied",
        "error_class": error_class,
        "message": str(message),
        "reason": str(reason),
        "summary": str(message),
        "data": data,
        "evidence": evidence,
        "evidence_refs": evidence,
        "conflicts": mismatches,
        "provider_state": "not_sent",
        "send_performed": False,
    }


def _invoice_dispatch_outcome(
    result: Mapping[str, Any],
    *,
    trusted: Mapping[str, Any],
    invoice: Mapping[str, Any],
    operation_id: str,
) -> Dict[str, Any]:
    """Map one staged dispatch outcome without ever claiming more than proved.

    ``send_accepted`` means the provider returned 202: the send request was
    accepted, not that a Sent Items message was verified. ``sent_verified``
    requires the readback proof. Everything else is either a proven
    non-send or an unresolved outcome that must never be retried blindly.
    """
    result = result if isinstance(result, Mapping) else {}
    status = _text(result.get("status")).lower()
    provider_status = _text(
        result.get("provider_status") or result.get("status"))
    draft_id = _text(result.get("draft_id") or result.get("provider_ref"))
    accepted = result.get("accepted")
    # A verified send needs every verification flag the provider reported to
    # agree. One explicit false flag makes the claimed proof inconsistent.
    verification_flags = [
        value for value in (
            result.get("verified"), result.get("sent_items_verified"),
        ) if value is not None
    ]
    verified = bool(verification_flags) and all(
        bool(value) for value in verification_flags)
    unresolved = bool(
        result.get("unresolved") or result.get("outcome_uncertain"))
    confirmed_send = bool(
        status == "sent_verified" and verified and not unresolved)
    accepted_unverified = status == "send_accepted"
    unconfirmed_verification = status == "sent_verified" and not confirmed_send
    reason = _text(result.get("reason")) or status or "dispatch_unresolved"
    error = _text(result.get("error")) or _text(result.get("reason")) or status

    invoice_ref = {
        "kind": "invoice",
        "resource_id": _text(invoice.get("invoice_id")),
        "invoice_number": _text(invoice.get("invoice_number")),
        "source": _text(invoice.get("source")),
        "source_table": _text(invoice.get("source_table")),
        "workspace_id": _text(invoice.get("workspace_id")),
        "tenant_id": _text(invoice.get("tenant_id")),
        "amount": _text(invoice.get("amount")),
        "currency": _text(invoice.get("currency")),
        "due_date": _text(invoice.get("due_date")),
        "status": _text(invoice.get("status")),
        "recorded_paid": invoice.get("recorded_paid"),
    }
    canvas_ref = {
        "kind": "canvas",
        "canvas_id": _text(trusted.get("canvas_id")),
        "audit_id": _text(trusted.get("audit_id")),
        "operation_id": _text(trusted.get("operation_id")),
        "draft_id": _text(trusted.get("draft_id")),
        "draft_revision": _text(trusted.get("draft_revision")),
        "material_sha256": _text(trusted.get("material_sha256")),
        "verification": dict(trusted.get("verification") or {}),
    }
    outbound_ref = {
        "kind": "outbound",
        "provider_state": (
            "sent" if confirmed_send
            else "accepted" if accepted_unverified
            else "unknown" if status in (
                "sent_verified", "unknown", "draft_created")
            else "not_sent"),
        "provider_status": provider_status,
        "draft_id": draft_id or None,
        "provider_ref": draft_id or None,
        "accepted": accepted,
        "verified": verified,
        "unresolved": bool(
            unresolved or accepted_unverified or unconfirmed_verification),
        "dispatch_operation_id": _text(operation_id),
    }
    common = {
        "invoice": dict(invoice),
        "canvas_id": _text(trusted.get("canvas_id")) or None,
        "audit_id": _text(trusted.get("audit_id")) or None,
        "operation_id": _text(trusted.get("operation_id")) or None,
        "dispatch_operation_id": _text(operation_id),
        "draft_id": draft_id or None,
        "provider_ref": draft_id or None,
        "provider_status": provider_status,
        "accepted": accepted,
        "verified": verified,
        "native_draft": {
            "canvas_id": _text(trusted.get("canvas_id")),
            "audit_id": _text(trusted.get("audit_id")),
            "operation_id": _text(trusted.get("operation_id")),
            "draft_id": _text(trusted.get("draft_id")),
            "draft_revision": _text(trusted.get("draft_revision")),
            "material_sha256": _text(trusted.get("material_sha256")),
            "step_id": _text(trusted.get("step_id")),
        },
    }

    if accepted_unverified or unconfirmed_verification:
        # A 202 acceptance is not a sent message, and a bare verified label
        # without the Sent Items readback is not proof either. Both stay
        # uncertain so dependents cannot advance; the immutable provider draft
        # id is kept for a later read-only reconciliation.
        if accepted_unverified:
            provider_state = "accepted"
            accepted_value = True if accepted is None else bool(accepted)
            delivery_state = "accepted_unverified"
            reason_value = _text(result.get("reason")) or (
                "send_accepted_unverified")
            summary = (
                "provider accepted the invoice reminder (202); Sent Items "
                "verification is unresolved")
        else:
            provider_state = "unknown"
            accepted_value = bool(accepted) if accepted is not None else False
            delivery_state = "verification_unconfirmed"
            reason_value = _text(result.get("reason")) or (
                "sent_verified_unconfirmed")
            summary = (
                "the invoice reminder claims a verified send without "
                "confirmed Sent Items evidence")
        return {
            "status": "uncertain",
            "action_result": "uncertain",
            "reason": reason_value,
            "summary": summary,
            "provider_state": provider_state,
            "provider_status": provider_status,
            "provider_ref": draft_id or None,
            "draft_id": draft_id or None,
            "message_id": draft_id or None,
            "delivery_state": delivery_state,
            "accepted": accepted_value,
            "verified": False,
            "sent_items_verified": False,
            "sent_items_unresolved": True,
            "unresolved": True,
            "reconciliation_required": True,
            "send_performed": False,
            "retry": "do_not_retry",
            "resend": "do_not_resend",
            "reconciliation": {
                "mode": "read_only",
                "retry": "do_not_retry",
                "resend": "do_not_resend",
            },
            "invoice": dict(invoice),
            "native_draft": common["native_draft"],
            "data": {
                **common,
                "provider_state": provider_state,
                "resolution": "reconciliation_required",
                "accepted": accepted_value,
                "verified": False,
                "sent_items_verified": False,
                "unresolved": True,
                "reconciliation_required": True,
                "send_performed": False,
                "provider_result": dict(result),
            },
            "evidence": [invoice_ref, canvas_ref, outbound_ref],
            "evidence_refs": [invoice_ref, canvas_ref, outbound_ref],
            "verification": {
                **dict(trusted.get("verification") or {}),
                "provider": {
                    "status": provider_status,
                    "accepted": accepted_value,
                    "verified": False,
                    "unresolved": True,
                },
            },
        }

    if confirmed_send:
        provider_state = "sent"
        summary = "provider verified the invoice reminder in Sent Items"
        return {
            "status": "applied",
            "summary": summary,
            "provider_state": provider_state,
            "provider_status": provider_status,
            "provider_ref": draft_id or None,
            "draft_id": draft_id or None,
            "message_id": draft_id or None,
            "delivery_state": "sent_verified",
            "accepted": bool(accepted if accepted is not None else True),
            "verified": True,
            "sent_items_verified": True,
            "sent_items_unresolved": False,
            "unresolved": False,
            "reconciliation_required": False,
            "send_performed": True,
            "retry": "do_not_retry",
            "resend": "do_not_resend",
            "reconciliation": {
                "mode": "read_only",
                "retry": "do_not_retry",
                "resend": "do_not_resend",
            },
            "invoice": dict(invoice),
            "native_draft": common["native_draft"],
            "data": {
                **common,
                "provider_state": provider_state,
                "resolution": "sent_verified",
                "verified": True,
                "sent_items_verified": True,
                "send_performed": True,
                "unresolved": False,
                "reconciliation_required": False,
                "provider_result": dict(result),
            },
            "evidence": [invoice_ref, canvas_ref, outbound_ref],
            "evidence_refs": [invoice_ref, canvas_ref, outbound_ref],
            "verification": {
                **dict(trusted.get("verification") or {}),
                "provider": {
                    "status": provider_status,
                    "accepted": accepted,
                    "verified": True,
                    "unresolved": False,
                },
            },
        }

    if status in ("unknown", "draft_created") or unresolved:
        return {
            "status": "uncertain",
            "action_result": "uncertain",
            "reason": reason,
            "summary": error,
            "provider_state": "unknown",
            "provider_status": provider_status,
            "provider_ref": draft_id or None,
            "message_id": draft_id or None,
            "accepted": accepted,
            "verified": verified,
            "sent_items_verified": verified,
            "unresolved": True,
            "send_performed": bool(result.get("send_performed")),
            "invoice": dict(invoice),
            "native_draft": common["native_draft"],
            "data": {
                **common,
                "provider_state": "unknown",
                "resolution": "unresolved",
                "send_performed": bool(result.get("send_performed")),
                "unresolved": True,
                "provider_result": dict(result),
            },
            "evidence": [invoice_ref, canvas_ref, outbound_ref],
            "evidence_refs": [invoice_ref, canvas_ref, outbound_ref],
            "verification": {
                **dict(trusted.get("verification") or {}),
                "provider": {
                    "status": provider_status,
                    "accepted": accepted,
                    "verified": verified,
                    "unresolved": True,
                },
            },
        }

    refusal = _invoice_send_refusal(
        error or "the approved invoice reminder was not sent",
        reason=reason,
        trusted=trusted,
        error_class=(
            _text(result.get("blocked_by"))
            or "invoice_dispatch_not_applied"),
        extra={
            "provider_status": provider_status,
            "draft_id": draft_id or None,
            "provider_ref": draft_id or None,
            "accepted": accepted,
            "verified": verified,
            "native_draft": common["native_draft"],
            "provider_result": dict(result),
        },
    )
    refusal["evidence"] = [invoice_ref, canvas_ref, outbound_ref]
    refusal["evidence_refs"] = [invoice_ref, canvas_ref, outbound_ref]
    return refusal


def _invoice_snapshot_mismatches(
    approved: Mapping[str, Any], current: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    mismatches = []
    for field in (
        "source", "source_table", "invoice_id", "invoice_number",
        "workspace_id", "tenant_id", "currency", "due_date",
    ):
        if _text(approved.get(field)) != _text(current.get(field)):
            mismatches.append({
                "field": field,
                "approved": _text(approved.get(field)),
                "current": _text(current.get(field)),
            })
    if not _same_amount(approved.get("amount"), current.get("amount")):
        mismatches.append({
            "field": "amount",
            "approved": _text(approved.get("amount")),
            "current": _text(current.get("amount")),
        })
    approved_status = _text(approved.get("status") or "open").lower()
    current_status = _text(current.get("status")).lower()
    if approved_status != "open" or current_status != "open":
        mismatches.append({
            "field": "status",
            "approved": approved_status,
            "current": current_status,
        })
    if approved.get("recorded_paid") is True or current.get("recorded_paid") is True:
        mismatches.append({
            "field": "recorded_paid",
            "approved": bool(approved.get("recorded_paid")),
            "current": bool(current.get("recorded_paid")),
        })
    return mismatches


def _invoice_draft_mismatches(
    approved: Mapping[str, Any], current: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    mismatches = []
    for field in ("to", "cc", "subject", "body"):
        if approved.get(field) != current.get(field):
            mismatches.append({
                "field": f"draft_{field}",
                "approved": approved.get(field),
                "current": current.get(field),
            })
    return mismatches


def _read_native_email_evidence(
    db: Any, canvas_id: str, audit_id: str,
) -> tuple[Any, Any, Any]:
    from core.canvas_email_service import EmailCanvasService

    service = EmailCanvasService(db)
    reader = getattr(service, "_email_draft_readback", None)
    if callable(reader):
        canvas, audit = reader(canvas_id, audit_id)
        return service, canvas, audit
    from core.models import Canvas, CanvasAudit

    canvas = (
        db.query(Canvas)
        .filter(Canvas.id == canvas_id)
        .populate_existing()
        .first())
    audit = (
        db.query(CanvasAudit)
        .filter(CanvasAudit.id == audit_id)
        .populate_existing()
        .first())
    return service, canvas, audit


def _native_canvas_mismatches(
    canvas: Any,
    audit: Any,
    *,
    trusted: Mapping[str, Any],
    actor_id: str,
    tenant_id: str,
    workspace_id: str,
) -> list[Dict[str, Any]]:
    mismatches = []
    canvas_id = _text(trusted.get("canvas_id"))
    audit_id = _text(trusted.get("audit_id"))
    operation_id = _text(trusted.get("operation_id"))
    material_sha256 = _text(trusted.get("material_sha256"))
    expected_content = _native_content(trusted.get("draft"))
    expected_draft = dict(trusted.get("content") or {})

    if canvas is None:
        return [{"field": "native_canvas", "approved": canvas_id,
                 "current": "missing"}]
    if _text(getattr(canvas, "id", canvas_id)) != canvas_id:
        mismatches.append({
            "field": "native_canvas_id",
            "approved": canvas_id,
            "current": _text(getattr(canvas, "id", "")),
        })
    for attribute, expected in (
        ("created_by", actor_id),
        ("tenant_id", tenant_id),
        ("workspace_id", workspace_id),
    ):
        actual = getattr(canvas, attribute, None)
        if actual is not None and _text(actual) != _text(expected):
            mismatches.append({
                "field": f"native_canvas_{attribute}",
                "approved": _text(expected),
                "current": _text(actual),
            })
    content = getattr(canvas, "content", None)
    content = dict(content) if isinstance(content, Mapping) else {}
    for field in ("to", "cc", "subject", "body"):
        if _raw_text(content.get(field)) != expected_content[field]:
            mismatches.append({
                "field": f"native_canvas_{field}",
                "approved": expected_content[field],
                "current": _raw_text(content.get(field)),
            })

    if audit is None:
        mismatches.append({
            "field": "native_audit", "approved": audit_id, "current": "missing"})
        return mismatches
    if _text(getattr(audit, "id", audit_id)) != audit_id:
        mismatches.append({
            "field": "native_audit_id",
            "approved": audit_id,
            "current": _text(getattr(audit, "id", "")),
        })
    if _text(getattr(audit, "canvas_id", canvas_id)) != canvas_id:
        mismatches.append({
            "field": "native_audit_canvas_id",
            "approved": canvas_id,
            "current": _text(getattr(audit, "canvas_id", "")),
        })
    if _text(getattr(audit, "action_type", "create")) != "create":
        mismatches.append({
            "field": "native_audit_action",
            "approved": "create",
            "current": _text(getattr(audit, "action_type", "")),
        })
    if _text(getattr(audit, "canvas_type", "email")).lower() != "email":
        mismatches.append({
            "field": "native_audit_canvas_type",
            "approved": "email",
            "current": _text(getattr(audit, "canvas_type", "")),
        })
    audit_user = getattr(audit, "user_id", None)
    if audit_user is not None and _text(audit_user) != actor_id:
        mismatches.append({
            "field": "native_audit_actor",
            "approved": actor_id,
            "current": _text(audit_user),
        })

    details = getattr(audit, "details_json", None) or {}
    if isinstance(details, str):
        try:
            import json

            details = json.loads(details)
        except (TypeError, ValueError):
            details = {}
    details = details if isinstance(details, Mapping) else {}
    if _text(details.get("operation_id")) != operation_id:
        mismatches.append({
            "field": "native_audit_operation_id",
            "approved": operation_id,
            "current": _text(details.get("operation_id")),
        })
    stored_material = _text(details.get("material_sha256"))
    if stored_material and material_sha256 and stored_material != material_sha256:
        mismatches.append({
            "field": "native_audit_material_sha256",
            "approved": material_sha256,
            "current": stored_material,
        })
    stored_draft = details.get("draft")
    if isinstance(stored_draft, Mapping) and \
            _draft_content(stored_draft) != expected_draft:
        mismatches.append({
            "field": "native_audit_draft",
            "approved": expected_draft,
            "current": _draft_content(stored_draft),
        })
    return mismatches


async def _invoice_prepare_reminder(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    invoice_number = _text(inputs.get("invoice_number"))
    if not invoice_number:
        raise NeedsContext({
            "concept": "invoice_identity",
            "reason": "the reminder step has no invoice number",
            "question": "Which invoice should the payment reminder reference?",
            "next_retrieval": "read the authoritative invoice record",
            "kind": "missing_evidence",
        })

    actor_id, tenant_id, workspace_id = _persisted_execution_authority(context)
    missing = [
        name for name, value in (
            ("actor_id", actor_id),
            ("tenant_id", tenant_id),
            ("workspace_id", workspace_id),
        ) if not value
    ]
    if missing:
        raise NeedsContext({
            "concept": "authenticated_scope",
            "reason": (
                "the persisted execution context has no "
                + ", ".join(missing)),
            "question": (
                "Which authenticated actor, tenant and workspace authorize "
                "this invoice reminder?"),
            "checked_evidence": [f"missing={name}" for name in missing],
            "next_retrieval": "re-authenticate the assignment owner",
            "kind": "missing_evidence",
        })

    operation_id = _persisted_step_operation_id(context)
    if not operation_id:
        raise NeedsContext({
            "concept": "execution_identity",
            "reason": "the persisted reminder step has no operation id",
            "question": (
                "Which persisted assignment operation authorizes this local "
                "reminder draft?"),
            "checked_evidence": ["operation_id=missing"],
            "next_retrieval": "resume the persisted assignment step",
            "kind": "missing_evidence",
        })

    from accounting.invoice_evidence import prepare_invoice_reminder
    from core.database import get_db_session

    with get_db_session() as db:
        reminder = prepare_invoice_reminder(
            db,
            actor_id=actor_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            invoice_number=invoice_number,
        )

    # Compose through the executor's canonical local draft assembly so the
    # revision, teaching protocol, and draft-only flags match email.draft.
    from core.assignment_executor import _email_draft

    draft_result = await _email_draft(dict(reminder), context)
    if str(draft_result.get("status") or "") != "applied":
        return draft_result

    draft = dict(draft_result.get("draft") or {})
    invoice = dict(reminder.get("evidence") or {})
    # prepare_invoice_reminder only returns for a currently open, overdue
    # invoice.  Record that status explicitly so a later dispatch approval is
    # bound to the state that was prepared, not just its visible content.
    invoice.setdefault("status", "open")
    invoice.setdefault("recorded_paid", False)
    revision = _text(draft.get("draft_revision"))
    invoice_ref = {
        "kind": "invoice",
        "resource_id": _text(invoice.get("invoice_id")) or invoice_number,
        "invoice_number": _text(invoice.get("invoice_number")) or invoice_number,
        "source": _text(invoice.get("source")),
        "source_table": _text(invoice.get("source_table")),
        "workspace_id": _text(invoice.get("workspace_id")) or workspace_id,
        "tenant_id": _text(invoice.get("tenant_id")) or tenant_id,
        "amount": _text(invoice.get("amount")),
        "currency": _text(invoice.get("currency")),
        "due_date": _text(invoice.get("due_date")),
        "status": _text(invoice.get("status")) or "open",
        "recorded_paid": bool(invoice.get("recorded_paid")),
    }
    evidence_refs = [invoice_ref]
    for ref in draft_result.get("evidence_refs") or []:
        if isinstance(ref, Mapping):
            ref = dict(ref)
            if ref.get("kind") == "draft":
                ref.update({
                    "operation_id": operation_id,
                })
            evidence_refs.append(ref)
    if not any(ref.get("kind") == "draft" for ref in evidence_refs):
        evidence_refs.append({
            "kind": "draft",
            "revision": revision,
            "operation_id": operation_id,
        })

    # Persist through the operation-bound Canvas writer.  Its actor+operation
    # identity makes a retry an exact replay instead of a second draft, and it
    # reads the committed Canvas+audit back before reporting success.
    from core.canvas_email_service import EmailCanvasService

    persisted: Dict[str, Any] = {}
    try:
        with get_db_session() as db:
            service = EmailCanvasService(db)
            created = service.create_email_draft(
                user_id=actor_id,
                draft=dict(draft),
                operation_id=operation_id,
                agent_id=_text(context.get("agent_id")) or None,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
            )
            if inspect.isawaitable(created):
                created = await created
            if isinstance(created, Mapping):
                persisted = dict(created)
    except Exception as exc:  # noqa: BLE001 — a commit may have happened
        persisted = {
            "success": False,
            "status": "effect_unknown",
            "error": (
                "the local reminder draft could not be confirmed: "
                f"{type(exc).__name__}: {exc}"),
            "operation_id": operation_id,
            "verification": {
                "status": "not_attempted",
                "effect": "unknown",
                "replay": "do_not_repeat",
            },
        }

    verification = persisted.get("verification")
    verification = (
        dict(verification) if isinstance(verification, Mapping) else {})
    receipt = persisted.get("receipt")
    receipt = dict(receipt) if isinstance(receipt, Mapping) else {}
    service_status = _text(persisted.get("status")).lower()
    effect = _text(verification.get("effect")).lower()
    canvas_id = _text(persisted.get("canvas_id"))
    audit_id = _text(persisted.get("audit_id"))
    receipt_draft = receipt.get("draft")
    receipt_draft = (
        dict(receipt_draft) if isinstance(receipt_draft, Mapping) else {})
    draft_id = (
        _text(persisted.get("draft_id"))
        or _text(receipt_draft.get("draft_id"))
    )
    material_sha256 = _text(persisted.get("material_sha256"))
    verified = bool(
        persisted.get("success") is True
        and service_status in ("created", "replayed")
        and _text(verification.get("status")).lower() == "verified"
        and _text(persisted.get("operation_id")) == operation_id
        and canvas_id
        and audit_id
        and _text(receipt.get("operation_id")) == operation_id
        and (
            not material_sha256
            or _text(receipt.get("material_sha256")) == material_sha256
        )
    )
    refused = bool(
        not verified
        and persisted.get("success") is not True
        and service_status in (
            "refused", "failed", "not_applied", "proven_not_applied")
        and effect not in ("unknown", "committed")
    )

    canvas_ref = {
        "kind": "canvas",
        "canvas_id": canvas_id or None,
        "audit_id": audit_id or None,
        "operation_id": operation_id,
        "draft_id": draft_id,
        "material_sha256": material_sha256,
        "revision": revision,
        "status": service_status or "unverified",
        "receipt": receipt,
        "verification": verification,
    }
    error = _text(persisted.get("error")) or (
        "the local reminder draft operation could not be verified")
    common = {
        "invoice": invoice,
        "draft_revision": revision,
        "canvas_id": canvas_id or None,
        "audit_id": audit_id or None,
        "operation_id": operation_id,
        "receipt": receipt,
        "verification": verification,
        "provider_state": "not_sent",
        "send_performed": False,
    }

    if not verified:
        persisted_data = {
            **common,
            "resolution": service_status or "unverified",
            "persisted": persisted,
        }
        if refused:
            return {
                "status": "failed",
                "action_result": "proven_not_applied",
                "message": error,
                "error_class": "email_draft_refused",
                "data": persisted_data,
                "verification": verification,
                "canvas_id": canvas_id or None,
                "audit_id": audit_id or None,
                "operation_id": operation_id,
                "evidence": [invoice_ref, canvas_ref],
                "evidence_refs": evidence_refs + [canvas_ref],
                "provider_state": "not_sent",
                "send_performed": False,
            }
        return {
            "status": "uncertain",
            "action_result": "uncertain",
            "reason": error,
            "summary": error,
            "data": persisted_data,
            "verification": verification,
            "conflicts": list(persisted.get("conflicts") or []),
            "canvas_id": canvas_id or None,
            "audit_id": audit_id or None,
            "operation_id": operation_id,
            "evidence": [invoice_ref, canvas_ref],
            "evidence_refs": evidence_refs + [canvas_ref],
            "provider_state": "not_sent",
            "send_performed": False,
        }

    evidence_refs.append(canvas_ref)
    draft_with_identity = {
        **draft,
        "canvas_id": canvas_id,
        "audit_id": audit_id,
        "operation_id": operation_id,
    }
    return {
        "status": "applied",
        "summary": (
            f"prepared local reminder draft {revision} for invoice "
            f"{invoice_number} in canvas {canvas_id}"),
        "artifact": dict(draft_result.get("artifact") or {}),
        "draft": draft_with_identity,
        "invoice": invoice,
        "data": common,
        "evidence": [invoice_ref, canvas_ref],
        "evidence_refs": evidence_refs,
        "canvas_id": canvas_id,
        "audit_id": audit_id,
        "operation_id": operation_id,
        "receipt": receipt,
        "verification": verification,
        "provider_state": "not_sent",
        "send_performed": False,
    }


async def _invoice_send_reminder(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Send an approved invoice reminder through the existing Outlook path.

    Nothing in ``inputs`` authorizes or selects this effect.  The prior
    operation-bound native draft is the only source of the invoice, canvas and
    recipient.  Immediately before dispatch the scoped invoice preparation is
    re-run and the native Canvas is read back; any change since approval is a
    proven refusal, never a silent rewrite or re-approval.
    """
    from core.assignment_executor import (
        _approval_payload_hash,
        _email_draft,
    )

    actor_id, tenant_id, workspace_id = _persisted_execution_authority(context)
    missing = [
        name for name, value in (
            ("actor_id", actor_id),
            ("tenant_id", tenant_id),
            ("workspace_id", workspace_id),
        ) if not value
    ]
    if missing:
        raise NeedsContext({
            "concept": "authenticated_scope",
            "reason": (
                "the persisted execution context has no "
                + ", ".join(missing)),
            "question": (
                "Which authenticated actor, tenant and workspace authorize "
                "this invoice reminder send?"),
            "checked_evidence": [f"missing={name}" for name in missing],
            "next_retrieval": "re-authenticate the assignment owner",
            "kind": "missing_evidence",
        })

    operation_id = _persisted_step_operation_id(context)
    if not operation_id:
        raise NeedsContext({
            "concept": "execution_identity",
            "reason": "the persisted send step has no operation id",
            "question": (
                "Which persisted assignment operation authorizes this invoice "
                "reminder send?"),
            "checked_evidence": ["operation_id=missing"],
            "next_retrieval": "resume the persisted assignment step",
            "kind": "missing_evidence",
        })

    trusted = _trusted_invoice_draft(context)
    invoice = dict(trusted["invoice"])
    invoice_number = _text(invoice.get("invoice_number"))
    if not invoice_number:
        _invoice_evidence_gap(
            "invoice_identity",
            "the approved reminder draft has no invoice number",
            "Which invoice does the approved reminder draft reference?",
        )
    if (_text(invoice.get("workspace_id")) != workspace_id
            or _text(invoice.get("tenant_id")) != tenant_id):
        return _invoice_send_refusal(
            "the approved reminder draft belongs to a different scope",
            reason="scope_mismatch", trusted=trusted)

    # The approval must name this exact prepared payload, not inputs supplied
    # at send time and not a later native draft.
    prepared = _invoice_send_reminder_prepare({}, context)
    payload_sha256 = _approval_payload_hash(prepared["payload"])
    step = context.get("step")
    step = step if isinstance(step, Mapping) else {}
    approval = step.get("approval_request")
    approval = approval if isinstance(approval, Mapping) else {}
    approved_sha256 = _text(approval.get("payload_sha256"))
    approved_revision = _text(approval.get("artifact_revision"))
    if not approved_sha256 or not approved_revision:
        raise NeedsContext({
            "concept": "approval_binding",
            "reason": "the persisted send step has no approval binding",
            "question": (
                "Which explicit approval authorizes this invoice reminder "
                "send?"),
            "checked_evidence": ["approval_request=missing"],
            "next_retrieval": "request explicit approval of the prepared send",
            "kind": "missing_evidence",
        })
    if (approved_sha256 != payload_sha256
            or approved_revision != trusted["draft_revision"]):
        return _invoice_send_refusal(
            "the approval does not cover the approved invoice draft",
            reason="approval_binding_mismatch",
            trusted=trusted,
            mismatches=[{
                "field": "approval",
                "approved": approved_sha256,
                "current": payload_sha256,
            }],
        )

    # Rerun the same scoped preparation.  This proves the actor is still
    # active in the exact tenant/workspace and the invoice is still an open,
    # overdue invoice; a paid or otherwise changed invoice refuses here.
    from accounting.invoice_evidence import (
        InvoiceEvidenceError,
        prepare_invoice_reminder,
    )
    from core.database import get_db_session

    try:
        with get_db_session() as db:
            reminder = prepare_invoice_reminder(
                db,
                actor_id=actor_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                invoice_number=invoice_number,
            )
    except InvoiceEvidenceError as exc:
        return _invoice_send_refusal(
            (
                "the invoice can no longer be prepared for an approved "
                f"reminder: {exc.reason}"),
            reason=_text(exc.reason) or "invoice_evidence_refused",
            trusted=trusted,
            error_class="invoice_evidence_refused",
            extra={"evidence_error": exc.to_dict()},
        )
    except Exception as exc:  # noqa: BLE001 — no provider call happened
        return _invoice_send_refusal(
            "the scoped invoice preparation could not be re-run",
            reason="invoice_evidence_unavailable",
            trusted=trusted,
            error_class="invoice_dispatch_guard_error",
            extra={"error": f"{type(exc).__name__}: {exc}"},
        )

    fresh_invoice = dict(reminder.get("evidence") or {})
    fresh_invoice.setdefault("status", "open")
    fresh_invoice.setdefault("recorded_paid", False)
    mismatches = _invoice_snapshot_mismatches(invoice, fresh_invoice)
    if mismatches:
        return _invoice_send_refusal(
            "the invoice changed after the reminder draft was approved",
            reason="invoice_snapshot_changed",
            trusted=trusted,
            mismatches=mismatches,
        )

    draft_result = await _email_draft(dict(reminder), context)
    if str(draft_result.get("status") or "") != "applied":
        return _invoice_send_refusal(
            "the approved reminder draft can no longer be composed",
            reason="invoice_draft_unavailable",
            trusted=trusted,
            error_class="invoice_draft_changed",
        )
    fresh_draft = dict(draft_result.get("draft") or {})
    mismatches = _invoice_draft_mismatches(
        trusted["content"], _draft_content(fresh_draft))
    if mismatches:
        return _invoice_send_refusal(
            "the reminder content changed after the draft was approved",
            reason="draft_content_changed",
            trusted=trusted,
            mismatches=mismatches,
        )

    # The native Canvas is the approved draft.  It must still be the exact
    # content and create audit this operation prepared; an edit after approval
    # is refused rather than sent or silently re-approved.
    try:
        with get_db_session() as db:
            _service, canvas, audit = _read_native_email_evidence(
                db, trusted["canvas_id"], trusted["audit_id"])
    except Exception as exc:  # noqa: BLE001 — no provider call happened
        return _invoice_send_refusal(
            "the approved native invoice draft could not be read back",
            reason="native_draft_unavailable",
            trusted=trusted,
            error_class="invoice_native_draft_unavailable",
            extra={"error": f"{type(exc).__name__}: {exc}"},
        )
    mismatches = _native_canvas_mismatches(
        canvas,
        audit,
        trusted=trusted,
        actor_id=actor_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    if mismatches:
        return _invoice_send_refusal(
            "the native invoice draft changed after it was approved",
            reason="native_draft_changed",
            trusted=trusted,
            mismatches=mismatches,
        )

    # Reuse the existing Canvas send preflight (authority, live-send mode,
    # grounding, email policy/rate) but stage the provider effect through the
    # dedicated one-create/one-send helper. The generic direct Outlook path
    # stays untouched. Approval covers the exact post-formatting payload,
    # including the current styled signature and the canvas/invoice binding.
    from core.canvas_email_service import EmailCanvasService

    payload = dict(prepared["payload"])
    staging = {
        "payload": payload,
        "run_id": _text(context.get("run_id")),
        "operation_id": operation_id,
    }
    try:
        with get_db_session() as db:
            service = EmailCanvasService(db)
            result = await service.send_email(
                canvas_id=trusted["canvas_id"],
                user_id=actor_id,
                to_emails=list(
                    payload.get("to_recipients") or payload.get("to") or []),
                cc_emails=list(
                    payload.get("cc_recipients") or payload.get("cc") or []),
                subject=_text(payload.get("subject")),
                body=_raw_text(payload.get("body")),
                agent_id=_text(context.get("agent_id")) or None,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                approved_outlook_dispatch=staging,
            )
    except Exception as exc:  # noqa: BLE001 — outcome may be unresolved
        return _invoice_dispatch_outcome(
            {
                "status": "unknown",
                "reason": "invoice_staged_dispatch_unresolved",
                "error": f"{type(exc).__name__}: {exc}",
                "provider_state": "unknown",
                "unresolved": True,
            },
            trusted=trusted,
            invoice=invoice,
            operation_id=operation_id,
        )
    return _invoice_dispatch_outcome(
        dict(result or {}),
        trusted=trusted,
        invoice=invoice,
        operation_id=operation_id,
    )


register_assignment_adapter(
    "invoice.reconcile",
    description="Reconcile invoice, purchase order and receiving evidence",
    metadata={"effect": "local", "required_actions": ["calculate"],
              "required_inputs": [
                  "invoice", "purchase_order", "receiving",
                  "invoice_fields", "purchase_order_fields",
                  "receiving_fields"],
              "allow_standing_authorization": False},
)(_invoice_reconcile)


register_assignment_adapter(
    "invoice.prepare_reminder",
    description="Prepare a local invoice payment reminder draft",
    metadata={"effect": "local", "required_actions": ["edit"],
              "required_inputs": ["invoice_number"],
              "allow_standing_authorization": False},
)(_invoice_prepare_reminder)


register_assignment_adapter(
    _INVOICE_LOOKUP_ADAPTER,
    description="Read one recorded invoice by its exact number and scope",
    metadata={"effect": "read_only", "required_actions": ["retrieve"],
              "required_inputs": ["invoice_number"],
              "allow_standing_authorization": False},
)(_invoice_lookup)


_INVOICE_SEND_METADATA = {
    "effect": "external", "required_actions": ["outbound"],
    "requires_approval": True,
    "allow_standing_authorization": False,
}


def _register_invoice_send(name: str) -> None:
    register_assignment_adapter(
        name,
        prepare=_invoice_send_reminder_prepare,
        description=(
            "Send an approved invoice payment reminder through the existing "
            "Outlook path"),
        metadata=dict(_INVOICE_SEND_METADATA),
    )(_invoice_send_reminder)


for _invoice_send_name in (
    "invoice.send_reminder",
    "invoice.send_reminder_outlook",
    "invoice.dispatch_reminder",
):
    _register_invoice_send(_invoice_send_name)

# Function aliases keep direct imports stable for callers that name the
# dispatch rather than the send.  Both names are the one guarded implementation
# above; neither is a separate send path.
_invoice_dispatch_reminder = _invoice_send_reminder
_invoice_send_reminder_outlook = _invoice_send_reminder


def _invoice_reply_gap(
    concept: str, reason: str, question: str, *, checked: Any = None,
) -> None:
    gap = {
        "concept": concept,
        "reason": reason,
        "question": question,
        "next_retrieval": (
            "resume the completed approved invoice reminder send step"),
        "kind": "missing_evidence",
    }
    if checked:
        gap["checked_evidence"] = list(checked)
    raise NeedsContext(gap)


def _reply_step_applied(step: Mapping[str, Any]) -> bool:
    return _text(step.get("status") or "applied").lower() in (
        "applied", "skipped")


def _reply_run_id(context: Mapping[str, Any]) -> str:
    assignment = context.get("assignment")
    assignment = assignment if isinstance(assignment, Mapping) else {}
    provenance = context.get("provenance")
    provenance = provenance if isinstance(provenance, Mapping) else {}
    if not provenance:
        nested = assignment.get("provenance")
        provenance = nested if isinstance(nested, Mapping) else {}
    return (
        _text(context.get("run_id"))
        or _text(assignment.get("run_id"))
        or _text(provenance.get("run_id"))
    )


def _fresh_scoped_lifecycle(
    context: Mapping[str, Any],
    *,
    actor_id: str,
    tenant_id: str,
    workspace_id: str,
) -> Any:
    """Return a live lifecycle for a fresh, scoped task read.

    The executor normally supplies no lifecycle to adapters.  A worker/test
    may expose the already-scoped object on the execution context; otherwise
    construct the standard GoalRun-backed lifecycle for this tenant and
    workspace, exactly as the staged Canvas send does.  Caller inputs are
    never a source of this object.
    """
    provided = (
        context.get("task_lifecycle")
        or context.get("lifecycle")
    )
    if callable(getattr(provided, "get_task", None)):
        return provided

    from core.goals.goal_run_service import GoalRunService
    from core.task_lifecycle import TaskLifecycle

    return TaskLifecycle(GoalRunService(
        workspace_id=workspace_id,
        tenant_id=tenant_id,
    ))


def _unique_direct_send_predecessor(
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    """Return the one applied send step this wait directly depends on.

    A reply may only be read from the exact reminder that was sent.  The
    predecessor is selected from persisted assignment state (or an explicitly
    named previous result), never from adapter inputs.
    """
    assignment = context.get("assignment")
    assignment = assignment if isinstance(assignment, Mapping) else {}
    current = context.get("step")
    current = current if isinstance(current, Mapping) else {}
    steps = [
        dict(step) for step in (assignment.get("steps") or [])
        if isinstance(step, Mapping)
    ]
    dependency_ids = {
        _text(item) for item in (current.get("depends_on") or [])
        if _text(item)
    }

    if steps:
        candidates = [
            step for step in steps
            if _text(step.get("adapter")) in _INVOICE_SEND_ADAPTERS
            and _text(step.get("step_id")) != _text(current.get("step_id"))
        ]
        if dependency_ids:
            candidates = [
                step for step in candidates
                if _text(step.get("step_id")) in dependency_ids
            ]
    else:
        previous = context.get("previous_results")
        previous = previous if isinstance(previous, Mapping) else {}
        if not dependency_ids and len(previous) == 1:
            dependency_ids = {_text(key) for key in previous if _text(key)}
        candidates = []
        for step_id in sorted(dependency_ids):
            result = previous.get(step_id)
            if isinstance(result, Mapping):
                candidates.append({
                    "step_id": step_id,
                    "status": "applied",
                    "result": dict(result),
                })

    applied = [
        step for step in candidates if _reply_step_applied(step)
    ]
    if len(applied) != 1:
        _invoice_reply_gap(
            "invoice_reply_source",
            (
                "the reply wait has no unique directly applied invoice "
                "reminder send step"
                if not applied else
                "the reply wait has more than one possible invoice reminder "
                "send step"),
            "Which exact sent invoice reminder should this reply belong to?",
            checked=[
                f"send_candidates={len(candidates)}",
                f"applied_candidates={len(applied)}",
            ],
        )
    return applied[0]


def _send_step_operation_ids(step: Mapping[str, Any]) -> list[str]:
    """Read durable send-operation identities, never a caller argument."""
    result = step.get("result")
    result = result if isinstance(result, Mapping) else {}
    data = result.get("data")
    data = data if isinstance(data, Mapping) else {}
    values = (
        step.get("operation_id"),
        # ``operation_id`` in a send result is the preparation identity.  Only
        # the dispatch identity names the operation that actually sent.
        step.get("dispatch_operation_id"),
        result.get("dispatch_operation_id"),
        data.get("dispatch_operation_id"),
    )
    operation_ids = []
    for value in values:
        text = _text(value)
        if text and text not in operation_ids:
            operation_ids.append(text)
    return operation_ids


def _resolve_send_operation(
    record: Mapping[str, Any],
    send_step: Mapping[str, Any],
    *,
    assignment_id: str,
) -> Dict[str, Any]:
    """Resolve one applied send operation from a fresh task record."""
    operations = [
        dict(operation) for operation in (record.get("operations") or [])
        if isinstance(operation, Mapping)
    ]
    send_step_id = _text(send_step.get("step_id"))
    candidate_ids = set(_send_step_operation_ids(send_step))

    def find(*, use_candidates: bool) -> Dict[str, Dict[str, Any]]:
        def compatible(operation: Mapping[str, Any]) -> bool:
            operation_id = _text(operation.get("operation_id"))
            if use_candidates and candidate_ids \
                    and operation_id not in candidate_ids:
                return False
            operation_assignment = _text(operation.get("assignment_id"))
            if assignment_id and operation_assignment \
                    and operation_assignment != assignment_id:
                return False
            operation_step = _text(operation.get("step_id"))
            if send_step_id and operation_step \
                    and operation_step != send_step_id:
                return False
            if not use_candidates and send_step_id \
                    and operation_step != send_step_id:
                return False
            adapter = _text(operation.get("adapter"))
            if adapter and adapter not in _INVOICE_SEND_ADAPTERS:
                return False
            status = _text(operation.get("status"))
            if status and status not in ("applied", "skipped"):
                return False
            return bool(operation_id)

        found: Dict[str, Dict[str, Any]] = {}
        for operation in reversed(operations):
            if compatible(operation):
                found[_text(operation.get("operation_id"))] = operation
        return found

    matches = find(use_candidates=True)
    if not matches and candidate_ids:
        # A stale or preparation identity on the step must not hide the one
        # exact applied send operation recorded by the fresh lifecycle.
        matches = find(use_candidates=False)
    if len(matches) != 1:
        _invoice_reply_gap(
            "invoice_reply_source",
            (
                "the applied invoice reminder send step has no exact scoped "
                "operation"
                if not matches else
                "the applied invoice reminder send step has more than one "
                "possible operation"),
            "Which exact scoped invoice reminder send operation should be "
            "probed for a reply?",
            checked=[
                f"send_step_id={send_step_id or 'missing'}",
                f"operation_candidates={len(matches)}",
            ],
        )
    return next(iter(matches.values()))


def _check_send_operation_scope(
    operation: Mapping[str, Any],
    *,
    actor_id: str,
    tenant_id: str,
    workspace_id: str,
) -> str:
    """Prove the fresh operation belongs to the persisted execution scope."""
    binding = operation.get("operation_binding")
    if not isinstance(binding, Mapping) or not binding:
        _invoice_reply_gap(
            "invoice_reply_source",
            "the invoice reminder send operation has no scope binding",
            "Which scoped invoice reminder send operation should be probed?",
            checked=["operation_binding=missing"],
        )
    action_name = _text(binding.get("action_name"))
    if action_name and action_name not in _INVOICE_SEND_ADAPTERS:
        _invoice_reply_gap(
            "invoice_reply_source",
            "the persisted operation is not an invoice reminder send",
            "Which exact invoice reminder send operation should be probed?",
            checked=[f"action_name={action_name}"],
        )
    bound_actor = _text(binding.get("account_id"))
    bound_workspace = _text(binding.get("workspace_id"))
    bound_tenant = _text(binding.get("tenant_id"))
    if not bound_actor or not bound_workspace:
        _invoice_reply_gap(
            "invoice_reply_source",
            "the invoice reminder send operation has an incomplete scope",
            "Which scoped invoice reminder send operation should be probed?",
            checked=[
                f"account_id={bound_actor or 'missing'}",
                f"workspace_id={bound_workspace or 'missing'}",
            ],
        )
    if bound_actor != actor_id or bound_workspace != workspace_id or (
            bound_tenant and bound_tenant != tenant_id):
        _invoice_reply_gap(
            "invoice_reply_source",
            "the invoice reminder send operation belongs to a different scope",
            "Which invoice reminder send belongs to the current actor, tenant "
            "and workspace?",
            checked=[
                f"actor_match={bound_actor == actor_id}",
                f"tenant_match={not bound_tenant or bound_tenant == tenant_id}",
                f"workspace_match={bound_workspace == workspace_id}",
            ],
        )
    return _text(operation.get("operation_id"))


def _send_step_invoice(send_step: Mapping[str, Any]) -> Dict[str, Any]:
    result = send_step.get("result")
    result = result if isinstance(result, Mapping) else {}
    data = result.get("data")
    data = data if isinstance(data, Mapping) else {}
    invoice = result.get("invoice") or data.get("invoice")
    if not isinstance(invoice, Mapping):
        invoice = {}
        for ref in (
            send_step.get("evidence_refs")
            or result.get("evidence_refs") or []
        ):
            if isinstance(ref, Mapping) and _text(ref.get("kind")) == "invoice":
                invoice = ref
                break
    return dict(invoice) if isinstance(invoice, Mapping) else {}


def _existing_reply_wait(
    context: Mapping[str, Any], record: Mapping[str, Any],
    wait_step_id: str,
) -> Dict[str, Any]:
    """Return the persisted wait fields that must stay stable on re-entry."""
    step = context.get("step")
    step = step if isinstance(step, Mapping) else {}
    holders = [step.get("waiting"), step.get("reply_wait")]
    for operation in reversed(list(record.get("operations") or [])):
        if not isinstance(operation, Mapping):
            continue
        if not wait_step_id or _text(operation.get("step_id")) != wait_step_id:
            continue
        holders.append(operation.get("waiting"))
    existing: Dict[str, Any] = {}
    for holder in holders:
        if not isinstance(holder, Mapping):
            continue
        if not existing.get("correlation_id") and _text(
                holder.get("correlation_id")):
            existing["correlation_id"] = _text(holder.get("correlation_id"))
        if not existing.get("deadline") and _text(holder.get("deadline")):
            existing["deadline"] = _text(holder.get("deadline"))
        if not existing.get("expires_at") and _text(
                holder.get("expires_at")):
            existing["expires_at"] = _text(holder.get("expires_at"))
        if not existing.get("since") and _text(holder.get("since")):
            existing["since"] = _text(holder.get("since"))
    return existing


def _reply_wait_time(value: Any) -> Optional[datetime]:
    """Parse one persisted wait clock as an aware UTC datetime."""
    text = _text(value)
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _invoice_reply_waiting(
    *,
    context: Mapping[str, Any],
    record: Mapping[str, Any],
    send_step: Mapping[str, Any],
    operation_id: str,
    invoice: Mapping[str, Any],
    detail: str,
) -> Dict[str, Any]:
    """Build the next durable reply wait or escalate an expired one.

    ``deadline`` is only the next executor wake: every no-proof probe moves it
    forward.  ``expires_at`` is the stable business bound, anchored to the
    first ``since`` timestamp and never extended by a later probe.  Once that
    bound is reached the wait becomes an explicit owner question instead of
    another empty Inbox read.
    """
    step = context.get("step")
    step = step if isinstance(step, Mapping) else {}
    wait_step_id = _text(step.get("step_id"))
    existing = _existing_reply_wait(context, record, wait_step_id)
    now = datetime.now(timezone.utc)

    correlation_id = existing.get("correlation_id") or (
        f"invoice-reply:{operation_id}")
    since_text = _text(existing.get("since"))
    since = _reply_wait_time(since_text)
    if since is None:
        since = now
        since_text = now.isoformat()

    expires = _reply_wait_time(existing.get("expires_at"))
    if expires is not None:
        expires_text = _text(existing.get("expires_at"))
    else:
        # A wait written before the two-clock split used ``deadline`` as its
        # absolute bound.  Keep that bound only while it is still live;
        # otherwise anchor the new business expiry to the stable first
        # timestamp rather than to the elapsed wake that caused the bug.
        legacy_deadline = _reply_wait_time(existing.get("deadline"))
        if legacy_deadline is not None and legacy_deadline > now:
            expires = legacy_deadline
        else:
            expires = since + timedelta(
                seconds=_INVOICE_REPLY_EXPIRY_SECONDS)
        expires_text = expires.isoformat()

    invoice_number = _text(invoice.get("invoice_number"))
    vendor_id = _text(invoice.get("vendor_id"))
    waiting = {
        "event": "invoice_reply",
        "state": "waiting_for_external",
        "party": vendor_id or "supplier",
        "resume_on": "reply",
        "detail": detail,
        "correlation_id": correlation_id,
        "expires_at": expires_text,
        "operation_id": operation_id,
        "draft_id": _text(send_step.get("draft_id")),
        "reply_seen": False,
        "commitment": False,
        "payment": False,
        "send_performed": False,
        "since": since_text,
    }
    if invoice_number:
        waiting["invoice_number"] = invoice_number

    if now >= expires:
        # No wake is scheduled on the escalation itself: it is a person-owned
        # decision, not another timer probe.  Correlation and the first
        # timestamp stay intact so the owner sees the same business wait.
        waiting.update({
            "event": "invoice_reply_expired",
            "state": "waiting_for_person",
            "party": "owner",
            "resume_on": "owner_decision",
            "detail": (
                "no verified reply was received before the invoice reply "
                "wait expired"),
            "expired_at": now.isoformat(),
            "escalation": "owner",
            "reason": "invoice_reply_expired",
        })
        raise NeedsContext({
            "concept": "invoice_reply_expired",
            "reason": (
                "the invoice reminder reply wait expired without a verified "
                "reply"),
            "question": (
                "The invoice reminder reply wait has expired without a "
                "verified reply. Should the owner escalate collection or "
                "close the wait?"),
            "next_retrieval": (
                "the assignment owner must decide the next invoice collection "
                "action"),
            "resolver": "owner",
            "kind": "business_decision",
            "checked_evidence": [
                f"correlation_id={correlation_id}",
                f"operation_id={operation_id}",
                f"expires_at={expires_text}",
            ],
            "waiting": waiting,
        })

    deadline = min(
        now + timedelta(seconds=_INVOICE_REPLY_RECHECK_SECONDS),
        expires,
    )
    waiting["deadline"] = deadline.isoformat()
    return waiting


def _exact_verified_reply(
    evidence: Any, *, operation_id: str,
) -> Optional[Dict[str, Any]]:
    """Accept only the helper's exact, verified direct-reply result."""
    if not isinstance(evidence, Mapping):
        return None
    # The published typed evidence only proves a direct reply when every
    # provider flag is exactly positive and the status/kind pair is exact.
    if evidence.get("verified") is not True:
        return None
    if evidence.get("direct_reply_verified") is not True:
        return None
    if evidence.get("status") != "reply_verified":
        return None
    if evidence.get("kind") != "reply":
        return None
    returned_operation = evidence.get("operation_id")
    if not isinstance(returned_operation, str) \
            or not returned_operation.strip():
        return None
    returned_operation = returned_operation.strip()
    if returned_operation != operation_id:
        _invoice_reply_gap(
            "invoice_reply_source",
            "the reply evidence names a different send operation",
            "Which exact sent invoice reminder does this reply belong to?",
            checked=[f"expected_operation={operation_id}",
                     f"returned_operation={returned_operation}"],
        )
        return None
    message_id = evidence.get("message_id")
    reply_message_id = evidence.get("reply_message_id")
    # A reply is only real when it names a distinct sent message and reply
    # message, with the conversation and sender that carried it.
    if not isinstance(message_id, str) or not message_id.strip():
        return None
    if not isinstance(reply_message_id, str) \
            or not reply_message_id.strip():
        return None
    message_id = message_id.strip()
    reply_message_id = reply_message_id.strip()
    if message_id == reply_message_id:
        return None
    conversation_id = evidence.get("conversation_id")
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        return None
    reply_sender = evidence.get("reply_sender")
    if not isinstance(reply_sender, str) or not reply_sender.strip():
        return None
    return dict(evidence)


async def _invoice_wait_for_reply(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Read one exact reply to an already-sent invoice reminder.

    Opt-in and read-only: ``inputs`` never select a provider id, recipient,
    actor, tenant, workspace or operation.  The one directly applied
    ``invoice.send_reminder`` predecessor is re-resolved through a fresh
    scoped lifecycle, and only its exact verified reply becomes evidence.  If
    no reply is present the adapter schedules a new future next wake inside the
    stable business expiry, escalating to the owner at expiry.  It never sends,
    acknowledges a commitment, or settles a payment.
    """
    del inputs  # business arguments are deliberately not authority

    actor_id, tenant_id, workspace_id = _persisted_execution_authority(context)
    missing = [
        name for name, value in (
            ("actor_id", actor_id),
            ("tenant_id", tenant_id),
            ("workspace_id", workspace_id),
        ) if not value
    ]
    if missing:
        _invoice_reply_gap(
            "authenticated_scope",
            "the persisted execution context has no " + ", ".join(missing),
            "Which authenticated actor, tenant and workspace authorize this "
            "invoice reply read?",
            checked=[f"missing={name}" for name in missing],
        )

    run_id = _reply_run_id(context)
    if not run_id:
        _invoice_reply_gap(
            "execution_identity",
            "the persisted reply wait has no run id",
            "Which persisted assignment owns this invoice reply wait?",
            checked=["run_id=missing"],
        )

    send_step = _unique_direct_send_predecessor(context)
    lifecycle = _fresh_scoped_lifecycle(
        context,
        actor_id=actor_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    if lifecycle is None:
        _invoice_reply_gap(
            "invoice_reply_source",
            "the scoped lifecycle needed to re-read the sent reminder is "
            "unavailable",
            "Which persisted invoice reminder send should be probed for a "
            "reply?",
            checked=["lifecycle=unavailable"],
        )

    try:
        record = lifecycle.get_task(run_id) or {}
    except Exception as exc:  # noqa: BLE001 — no provider read happened
        _invoice_reply_gap(
            "invoice_reply_source",
            "the persisted task could not be re-read for the reply source: "
            f"{type(exc).__name__}: {exc}",
            "Which persisted invoice reminder send should be probed for a "
            "reply?",
        )
    if not record:
        # A scoped test/worker may expose the same freshly read record on the
        # execution context when its lifecycle is a thin adapter.
        candidate = context.get("task") or context.get("task_record")
        if isinstance(candidate, Mapping):
            record = dict(candidate)
    if not isinstance(record, Mapping) or not record:
        _invoice_reply_gap(
            "invoice_reply_source",
            "the persisted task for the reply wait is missing",
            "Which persisted invoice reminder send should be probed for a "
            "reply?",
            checked=[f"run_id={run_id}"],
        )

    assignment = context.get("assignment")
    assignment = assignment if isinstance(assignment, Mapping) else {}
    assignment_id = _text(assignment.get("assignment_id"))
    operation = _resolve_send_operation(
        record, send_step, assignment_id=assignment_id)
    operation_id = _check_send_operation_scope(
        operation,
        actor_id=actor_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    invoice = _send_step_invoice(send_step)
    invoice_workspace = _text(invoice.get("workspace_id"))
    invoice_tenant = _text(invoice.get("tenant_id"))
    if (invoice_workspace and invoice_workspace != workspace_id) or (
            invoice_tenant and invoice_tenant != tenant_id):
        _invoice_reply_gap(
            "invoice_reply_source",
            "the sent invoice belongs to a different workspace or tenant",
            "Which sent invoice reminder belongs to the current scope?",
            checked=[
                f"invoice_workspace={invoice_workspace or 'missing'}",
                f"invoice_tenant={invoice_tenant or 'missing'}",
            ],
        )

    # Enforce the business expiry before any provider read.  An expired wait
    # belongs to its owner, not to another empty Inbox probe.
    _invoice_reply_waiting(
        context=context,
        record=record,
        send_step=send_step,
        operation_id=operation_id,
        invoice=invoice,
        detail="the invoice reply wait has expired",
    )

    from core.outlook_draft_dispatch import (
        OutlookDispatchRefused,
        read_outlook_dispatch_evidence,
    )

    try:
        result = await read_outlook_dispatch_evidence(
            lifecycle,
            run_id,
            operation_id,
            actor_id=actor_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            reply=True,
        )
    except OutlookDispatchRefused as exc:
        reason = _text(getattr(exc, "reason", "")) or _text(exc)
        if reason in _INVOICE_REPLY_SOURCE_REFUSALS:
            _invoice_reply_gap(
                "invoice_reply_source",
                f"the sent invoice reminder source was refused: {reason}",
                "Which exact scoped invoice reminder send should be probed "
                "for a reply?",
                checked=[f"refused={reason}"],
            )
        raise WaitingForExternal(_invoice_reply_waiting(
            context=context,
            record=record,
            send_step=send_step,
            operation_id=operation_id,
            invoice=invoice,
            detail=(
                "the reply evidence is temporarily unavailable; the next "
                "probe is scheduled inside the reply wait expiry"),
        )) from exc
    except Exception as exc:  # noqa: BLE001 — transient read, never a send
        raise WaitingForExternal(_invoice_reply_waiting(
            context=context,
            record=record,
            send_step=send_step,
            operation_id=operation_id,
            invoice=invoice,
            detail=(
                "the reply evidence read is temporarily unavailable; the "
                "next probe is scheduled inside the reply wait expiry"),
        )) from exc

    reply = _exact_verified_reply(result, operation_id=operation_id)
    if reply is None:
        raise WaitingForExternal(_invoice_reply_waiting(
            context=context,
            record=record,
            send_step=send_step,
            operation_id=operation_id,
            invoice=invoice,
            detail="no exact verified reply has been received yet",
        ))

    step = context.get("step")
    step = step if isinstance(step, Mapping) else {}
    existing = _existing_reply_wait(
        context, record, _text(step.get("step_id")))
    correlation_id = existing.get("correlation_id") or (
        f"invoice-reply:{operation_id}")
    invoice_number = _text(invoice.get("invoice_number"))
    reply_message_id = _text(reply.get("reply_message_id"))
    reply_sender = _text(reply.get("reply_sender"))
    message_id = _text(reply.get("message_id"))
    draft_id = _text(reply.get("draft_id")) or _text(
        send_step.get("draft_id"))
    typed = {
        "kind": "invoice_reply",
        "verified": True,
        "reply_seen": True,
        "commitment": False,
        "payment": False,
        "settled": False,
        "send_performed": False,
        "correlation_id": correlation_id,
        "operation_id": operation_id,
        "draft_id": draft_id or None,
        "message_id": message_id or None,
        "reply_message_id": reply_message_id or None,
        "reply_sender": reply_sender or None,
        "conversation_id": reply.get("conversation_id"),
        "invoice_id": _text(invoice.get("invoice_id")) or None,
        "invoice_number": invoice_number or None,
    }
    return {
        "status": "applied",
        "summary": (
            f"received verified reply to invoice reminder "
            f"{invoice_number or operation_id}"),
        "data": dict(typed),
        "invoice": dict(invoice),
        "operation_id": operation_id,
        "dispatch_operation_id": operation_id,
        "correlation_id": correlation_id,
        "reply_seen": True,
        "commitment": False,
        "payment": False,
        "settled": False,
        "provider_state": "reply_received",
        "send_performed": False,
        "verification": {
            "status": "verified",
            "resource_id": reply_message_id or message_id or operation_id,
            "version": _text(reply.get("status")) or "reply_verified",
            "coverage": {"complete": True, "truncated": False},
        },
        "evidence": [typed],
        "evidence_refs": [typed],
    }


register_assignment_adapter(
    "invoice.wait_for_reply",
    description=(
        "Read one exact verified reply to an already-sent invoice reminder"),
    metadata={"effect": "read_only", "required_actions": ["retrieve"],
              "allow_standing_authorization": False},
)(_invoice_wait_for_reply)


_INVOICE_COMMITMENT_ADAPTER = "invoice.await_commitment"
_INVOICE_COMMITMENT_FIELD = "invoice_commitments"
_INVOICE_COMMITMENT_SCHEMA = "atom-invoice-commitment-1"
_INVOICE_COMMITMENT_VERDICTS = frozenset(
    {"confirmed", "no_commitment", "unclear"})


def _commitment_gap(
    concept: str, reason: str, question: str, *, checked: Any = None,
) -> None:
    gap = {
        "concept": concept,
        "reason": reason,
        "question": question,
        "next_retrieval": "request the invoice commitment reviewer decision",
        "kind": "missing_evidence",
    }
    if checked:
        gap["checked_evidence"] = list(checked)
    raise NeedsContext(gap)


def _commitment_text(
    value: Any, field: str, *, required: bool = False,
    nonblank: bool = False,
) -> Optional[str]:
    """Read one identity exactly; never coerce or substitute another value."""
    if value is None:
        if required:
            _commitment_gap(
                "invoice_commitment_source",
                f"invoice reply evidence is missing {field}",
                "Which exact verified invoice reply should be reviewed?",
                checked=[f"missing={field}"],
            )
        return None
    if type(value) is not str:
        _commitment_gap(
            "invoice_commitment_source",
            f"invoice reply evidence {field} must be an exact string",
            "Which exact verified invoice reply should be reviewed?",
            checked=[f"invalid={field}"],
        )
    if not value:
        if required:
            _commitment_gap(
                "invoice_commitment_source",
                f"invoice reply evidence is missing {field}",
                "Which exact verified invoice reply should be reviewed?",
                checked=[f"missing={field}"],
            )
        return None
    if nonblank and not value.strip():
        _commitment_gap(
            "invoice_commitment_source",
            f"invoice reply evidence is missing {field}",
            "Which exact verified invoice reply should be reviewed?",
            checked=[f"missing={field}"],
        )
    return value


def _commitment_assignment(
    record: Mapping[str, Any], context: Mapping[str, Any],
) -> Mapping[str, Any]:
    assignment = record.get("assignment")
    if not isinstance(assignment, Mapping):
        assignment = context.get("assignment")
    return assignment if isinstance(assignment, Mapping) else {}


def _commitment_step_applied(step: Mapping[str, Any]) -> bool:
    return _text(step.get("status") or "applied").lower() == "applied"


def _commitment_current_step(
    assignment: Mapping[str, Any], context: Mapping[str, Any],
) -> Dict[str, Any]:
    steps = [
        dict(step) for step in (assignment.get("steps") or [])
        if isinstance(step, Mapping)
    ]
    current = context.get("step")
    current = dict(current) if isinstance(current, Mapping) else {}
    step_id = _text(current.get("step_id"))
    if step_id:
        matches = [
            step for step in steps if _text(step.get("step_id")) == step_id
        ]
        if len(matches) == 1:
            current = matches[0]
    if not current:
        matches = [
            step for step in steps
            if _text(step.get("adapter")) == _INVOICE_COMMITMENT_ADAPTER
        ]
        if len(matches) == 1:
            current = matches[0]
    if not current or (
            current.get("adapter")
            and _text(current.get("adapter")) != _INVOICE_COMMITMENT_ADAPTER):
        _commitment_gap(
            "invoice_commitment_step",
            "the persisted step is not an invoice.await_commitment step",
            "Which persisted invoice commitment review is awaiting a verdict?",
        )
    return current


def _commitment_reply_predecessor(
    assignment: Mapping[str, Any], current: Mapping[str, Any],
) -> Dict[str, Any]:
    steps = [
        dict(step) for step in (assignment.get("steps") or [])
        if isinstance(step, Mapping)
    ]
    current_id = _text(current.get("step_id"))
    dependency_ids = {
        _text(item) for item in (current.get("depends_on") or [])
        if _text(item)
    }
    candidates = [
        step for step in steps
        if _text(step.get("adapter")) == _INVOICE_REPLY_ADAPTER
        and _text(step.get("step_id")) != current_id
    ]
    if dependency_ids:
        candidates = [
            step for step in candidates
            if _text(step.get("step_id")) in dependency_ids
        ]
    applied = [
        step for step in candidates if _commitment_step_applied(step)
    ]
    if len(applied) != 1:
        _commitment_gap(
            "invoice_commitment_source",
            (
                "the commitment review has no unique directly applied "
                "invoice.wait_for_reply predecessor"
                if not applied else
                "the commitment review has more than one directly applied "
                "invoice.wait_for_reply predecessor"),
            "Which exact verified invoice reply should be reviewed?",
            checked=[
                f"reply_candidates={len(candidates)}",
                f"applied_candidates={len(applied)}",
            ],
        )
    return applied[0]


def _commitment_packet(
    record: Mapping[str, Any],
    reply_step: Mapping[str, Any],
    assignment: Mapping[str, Any],
) -> Dict[str, Any]:
    """Derive the published source packet for one verified invoice reply."""
    if _text(reply_step.get("adapter")) != _INVOICE_REPLY_ADAPTER \
            or _text(reply_step.get("operation_type")) != "retrieve" \
            or _text(reply_step.get("status")) != "applied":
        _commitment_gap(
            "invoice_commitment_source",
            "the predecessor is not an applied invoice.wait_for_reply "
            "retrieve step",
            "Which exact verified invoice reply should be reviewed?",
        )

    reply_operation_id = _commitment_text(
        reply_step.get("operation_id"), "step operation_id", required=True)
    operations = [
        dict(operation) for operation in (record.get("operations") or [])
        if isinstance(operation, Mapping)
    ]
    operation_matches = [
        operation for operation in operations
        if _text(operation.get("operation_id")) == reply_operation_id
    ]
    if len(operation_matches) != 1:
        _commitment_gap(
            "invoice_commitment_source",
            (
                "the applied reply step has no exact source operation"
                if not operation_matches else
                "the reply source operation identity is ambiguous"),
            "Which exact verified invoice reply should be reviewed?",
            checked=[f"operation_candidates={len(operation_matches)}"],
        )
    operation = operation_matches[0]
    if _text(operation.get("adapter")) != _INVOICE_REPLY_ADAPTER \
            or _text(operation.get("operation_type")) != "retrieve" \
            or _text(operation.get("status")) != "applied":
        _commitment_gap(
            "invoice_commitment_source",
            "the reply source operation is not an applied retrieve",
            "Which exact verified invoice reply should be reviewed?",
        )

    result = reply_step.get("result")
    if not isinstance(result, Mapping):
        _commitment_gap(
            "invoice_commitment_source",
            "the invoice.wait_for_reply result is missing",
            "Which exact verified invoice reply should be reviewed?",
        )
    evidence = reply_step.get("evidence_refs")
    if not isinstance(evidence, list) or len(evidence) != 1:
        _commitment_gap(
            "invoice_commitment_source",
            "the invoice reply evidence is not unique",
            "Which exact verified invoice reply should be reviewed?",
        )
    typed = evidence[0]
    if not isinstance(typed, Mapping):
        _commitment_gap(
            "invoice_commitment_source",
            "the invoice reply evidence is not typed",
            "Which exact verified invoice reply should be reviewed?",
        )
    typed = dict(typed)
    if _text(typed.get("kind")) != "invoice_reply":
        _commitment_gap(
            "invoice_commitment_source",
            "the invoice reply evidence has the wrong type",
            "Which exact verified invoice reply should be reviewed?",
        )
    if typed.get("verified") is not True \
            or typed.get("reply_seen") is not True:
        _commitment_gap(
            "invoice_commitment_source",
            "the invoice reply evidence is not a verified seen reply",
            "Which exact verified invoice reply should be reviewed?",
        )
    for field in ("commitment", "payment", "settled", "send_performed"):
        if typed.get(field) is not False:
            _commitment_gap(
                "invoice_commitment_source",
                f"the invoice reply evidence must record {field}=false",
                "Which exact verified invoice reply should be reviewed?",
                checked=[f"{field}={typed.get(field)!r}"],
            )

    dispatch_operation_id = _commitment_text(
        typed.get("operation_id"), "evidence operation_id", required=True)
    if dispatch_operation_id == reply_operation_id:
        _commitment_gap(
            "invoice_commitment_source",
            "the invoice reply evidence does not name a distinct dispatch "
            "operation",
            "Which exact verified invoice reply should be reviewed?",
        )
    correlation_id = _commitment_text(
        typed.get("correlation_id"), "evidence correlation_id",
        required=True)
    if correlation_id != f"invoice-reply:{dispatch_operation_id}":
        _commitment_gap(
            "invoice_commitment_source",
            "the invoice reply evidence correlation is not bound to the "
            "dispatch operation",
            "Which exact verified invoice reply should be reviewed?",
        )
    message_id = _commitment_text(
        typed.get("message_id"), "evidence message_id", required=True)
    reply_message_id = _commitment_text(
        typed.get("reply_message_id"), "evidence reply_message_id",
        required=True)
    if message_id == reply_message_id:
        _commitment_gap(
            "invoice_commitment_source",
            "the invoice reply evidence does not name distinct sent and reply "
            "messages",
            "Which exact verified invoice reply should be reviewed?",
        )
    invoice_id = _commitment_text(
        typed.get("invoice_id"), "evidence invoice_id", required=True,
        nonblank=True)
    conversation_id = _commitment_text(
        typed.get("conversation_id"), "evidence conversation_id",
        required=True, nonblank=True)
    reply_sender = _commitment_text(
        typed.get("reply_sender"), "evidence reply_sender",
        required=True, nonblank=True)

    depends_on = reply_step.get("depends_on")
    if not isinstance(depends_on, list):
        _commitment_gap(
            "invoice_commitment_source",
            "the invoice.wait_for_reply step has no predecessor",
            "Which exact verified invoice reply should be reviewed?",
        )
    steps = [
        dict(step) for step in (assignment.get("steps") or [])
        if isinstance(step, Mapping)
    ]
    predecessor_matches = [
        step for step in steps
        if _text(step.get("operation_id")) == dispatch_operation_id
    ]
    if len(predecessor_matches) != 1:
        _commitment_gap(
            "invoice_commitment_source",
            (
                "the reply dispatch step was not found"
                if not predecessor_matches else
                "the reply dispatch step identity is ambiguous"),
            "Which exact invoice reminder send produced this reply?",
            checked=[f"dispatch_candidates={len(predecessor_matches)}"],
        )
    predecessor = predecessor_matches[0]
    if _text(predecessor.get("adapter")) not in _INVOICE_SEND_ADAPTERS \
            or _text(predecessor.get("operation_type")) != "outbound" \
            or _text(predecessor.get("status")) != "applied":
        _commitment_gap(
            "invoice_commitment_source",
            "the reply evidence does not point to an applied outbound "
            "invoice reminder step",
            "Which exact invoice reminder send produced this reply?",
        )
    if _text(predecessor.get("step_id")) not in depends_on:
        _commitment_gap(
            "invoice_commitment_source",
            "the invoice.wait_for_reply step does not depend on the reply "
            "dispatch step",
            "Which exact invoice reminder send produced this reply?",
        )

    dispatch_matches = [
        operation for operation in operations
        if _text(operation.get("operation_id")) == dispatch_operation_id
    ]
    if len(dispatch_matches) != 1:
        _commitment_gap(
            "invoice_commitment_source",
            (
                "the reply dispatch operation was not found"
                if not dispatch_matches else
                "the reply dispatch operation identity is ambiguous"),
            "Which exact invoice reminder send produced this reply?",
            checked=[f"dispatch_candidates={len(dispatch_matches)}"],
        )
    dispatch_operation = dispatch_matches[0]
    if _text(dispatch_operation.get("adapter")) not in _INVOICE_SEND_ADAPTERS \
            or _text(dispatch_operation.get("operation_type")) != "outbound" \
            or _text(dispatch_operation.get("status")) != "applied":
        _commitment_gap(
            "invoice_commitment_source",
            "the reply dispatch operation is not an applied outbound invoice "
            "reminder",
            "Which exact invoice reminder send produced this reply?",
        )

    verification = result.get("verification")
    if not isinstance(verification, Mapping) \
            or _text(verification.get("status")) != "verified":
        _commitment_gap(
            "invoice_commitment_source",
            "the invoice reply verification is not verified",
            "Which exact verified invoice reply should be reviewed?",
        )
    coverage = verification.get("coverage")
    if not isinstance(coverage, Mapping) \
            or coverage.get("complete") is not True \
            or coverage.get("truncated") is not False:
        _commitment_gap(
            "invoice_commitment_source",
            "the invoice reply verification is not complete",
            "Which exact verified invoice reply should be reviewed?",
        )

    source = {
        "operation_id": dispatch_operation_id,
        "reply_operation_id": reply_operation_id,
        "correlation_id": correlation_id,
        "reply_message_id": reply_message_id,
        "message_id": message_id,
        "draft_id": _commitment_text(
            typed.get("draft_id"), "evidence draft_id"),
        "reply_sender": reply_sender,
        "invoice_id": invoice_id,
        "invoice_number": _commitment_text(
            typed.get("invoice_number"), "evidence invoice_number"),
        "conversation_id": conversation_id,
        "evidence_kind": "invoice_reply",
    }
    return {
        "step": dict(reply_step),
        "operation": operation,
        "dispatch_step": predecessor,
        "evidence": typed,
        "source": source,
    }


def _commitment_revisions(
    assignment: Mapping[str, Any], reply_step_id: str,
) -> list[Dict[str, Any]]:
    """Read one reply step's append-only commitment revisions."""
    store = assignment.get(_INVOICE_COMMITMENT_FIELD)
    if store is None:
        return []
    if not isinstance(store, Mapping) \
            or store.get("schema") != _INVOICE_COMMITMENT_SCHEMA:
        _commitment_gap(
            "invoice_commitment_history",
            "invoice commitment history is malformed",
            "Which reviewed invoice commitment revision is current?",
        )
    revisions = store.get("revisions")
    if not isinstance(revisions, list):
        _commitment_gap(
            "invoice_commitment_history",
            "invoice commitment history is malformed",
            "Which reviewed invoice commitment revision is current?",
        )
    selected: list[Dict[str, Any]] = []
    for raw in revisions:
        if not isinstance(raw, Mapping):
            _commitment_gap(
                "invoice_commitment_history",
                "invoice commitment history is malformed",
                "Which reviewed invoice commitment revision is current?",
            )
        raw_step_id = raw.get("step_id")
        revision = raw.get("revision")
        if type(raw_step_id) is not str or not raw_step_id \
                or type(revision) is not int or revision < 1 \
                or raw.get("verdict") not in _INVOICE_COMMITMENT_VERDICTS \
                or type(raw.get("reviewed_by")) is not str \
                or not raw.get("reviewed_by") \
                or type(raw.get("reviewed_at")) is not str \
                or not raw.get("reviewed_at") \
                or not isinstance(raw.get("source"), Mapping):
            _commitment_gap(
                "invoice_commitment_history",
                "invoice commitment history is malformed",
                "Which reviewed invoice commitment revision is current?",
            )
        if raw_step_id == reply_step_id:
            selected.append(dict(raw))
    for index, item in enumerate(selected, start=1):
        if item.get("revision") != index:
            _commitment_gap(
                "invoice_commitment_history",
                "invoice commitment revisions are not contiguous",
                "Which reviewed invoice commitment revision is current?",
            )
    return selected


def _commitment_assert_source(
    source: Mapping[str, Any], history: list[Dict[str, Any]],
) -> None:
    """Keep every revision bound to the one published operation/reply pair."""
    for item in history:
        recorded = item.get("source")
        recorded = recorded if isinstance(recorded, Mapping) else {}
        for field in (
            "operation_id", "reply_operation_id", "reply_message_id",
        ):
            current = recorded.get(field)
            if _text(current) != _text(source.get(field)):
                _commitment_gap(
                    "invoice_commitment_source",
                    "the published invoice reply no longer matches the recorded "
                    "commitment source",
                    "Which exact verified invoice reply was reviewed?",
                    checked=[f"field={field}"],
                )
            if field in item \
                    and _text(item.get(field)) != _text(source.get(field)):
                _commitment_gap(
                    "invoice_commitment_source",
                    "the published invoice reply no longer matches the recorded "
                    "commitment source",
                    "Which exact verified invoice reply was reviewed?",
                    checked=[f"field={field}"],
                )


def _commitment_reviewer_waiting(
    *,
    context: Mapping[str, Any],
    record: Mapping[str, Any],
    source: Mapping[str, Any],
    step_id: str,
    revision: int,
    detail: str,
) -> Dict[str, Any]:
    """Build the durable reviewer wait, never a busy loop.

    The wait carries the exact workflow source and the revision the adapter
    last observed.  The executor wakes it only for a newer conclusive
    revision bound to that source, or at the single ``expires_at`` business
    timer; it never schedules the short reply-recheck interval.
    """
    existing = _existing_reply_wait(context, record, step_id)
    now = datetime.now(timezone.utc)

    correlation_id = existing.get("correlation_id") or (
        f"invoice-commitment:{source['reply_operation_id']}")
    since_text = _text(existing.get("since"))
    since = _reply_wait_time(since_text)
    if since is None:
        since = now
        since_text = now.isoformat()

    expires = _reply_wait_time(existing.get("expires_at"))
    if expires is not None:
        expires_text = _text(existing.get("expires_at"))
    else:
        legacy_deadline = _reply_wait_time(existing.get("deadline"))
        if legacy_deadline is not None and legacy_deadline > now:
            expires = legacy_deadline
        else:
            expires = since + timedelta(
                seconds=_INVOICE_REPLY_EXPIRY_SECONDS)
        expires_text = expires.isoformat()

    waiting = {
        "event": "invoice_commitment_review",
        "state": "waiting_for_person",
        "party": "reviewer",
        "resume_on": "reviewer_decision",
        "detail": detail,
        "correlation_id": correlation_id,
        "expires_at": expires_text,
        "operation_id": source["operation_id"],
        "reply_operation_id": source["reply_operation_id"],
        "reply_message_id": source["reply_message_id"],
        # The executor may wake this wait only from a newer conclusive
        # decision revision bound to this exact workflow source.  It is a
        # local review, never an approval or a provider poll.
        "wait_source": {
            "operation_id": _text(source.get("operation_id")),
            "reply_operation_id": _text(source.get("reply_operation_id")),
            "reply_message_id": _text(source.get("reply_message_id")),
        },
        "invoice_id": source.get("invoice_id"),
        "invoice_number": source.get("invoice_number"),
        "revision": revision,
        "commitment": False,
        "payment": False,
        "settled": False,
        "send_performed": False,
        "since": since_text,
    }

    if now >= expires:
        waiting.update({
            "event": "invoice_commitment_review_expired",
            "party": "owner",
            "resume_on": "owner_decision",
            "detail": (
                "the invoice commitment review did not receive a decision "
                "before the wait expired"),
            "expired_at": now.isoformat(),
            "escalation": "owner",
            "reason": "invoice_commitment_review_expired",
        })
        raise NeedsContext({
            "concept": "invoice_commitment_review_expired",
            "reason": (
                "the invoice commitment review expired without a reviewer "
                "decision"),
            "question": (
                "The invoice commitment review expired without a decision. "
                "Should the owner close the wait or follow up on the invoice "
                "reply?"),
            "next_retrieval": (
                "the assignment owner must decide the next invoice collection "
                "action"),
            "resolver": "owner",
            "kind": "business_decision",
            "checked_evidence": [
                f"correlation_id={correlation_id}",
                f"revision={revision}",
                f"expires_at={expires_text}",
            ],
            "waiting": waiting,
        })

    # A reviewer decision is durable assignment state, not a provider poll.
    # Park until the real business expiry.  The executor wakes early only
    # from a newer conclusive revision bound to the exact wait source; the
    # short reply-recheck interval must not re-enter this wait, because each
    # empty re-entry consumes an attempt before the reviewer can act.
    waiting["deadline"] = expires_text
    return waiting


async def _invoice_await_commitment(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Wait for or read the reviewer's verdict on one exact invoice reply.

    Read-only: ``inputs`` never authorize or select the source.  The unique
    directly applied ``invoice.wait_for_reply`` predecessor is re-read through
    the scoped lifecycle, its one typed evidence ref is revalidated, and the
    append-only ``invoice_commitments`` history supplies the current verdict.
    No provider is called and no payment or settlement is asserted.
    """
    del inputs  # caller arguments are deliberately not authority

    actor_id, tenant_id, workspace_id = _persisted_execution_authority(context)
    missing = [
        name for name, value in (
            ("actor_id", actor_id),
            ("tenant_id", tenant_id),
            ("workspace_id", workspace_id),
        ) if not value
    ]
    if missing:
        _commitment_gap(
            "authenticated_scope",
            "the persisted execution context has no " + ", ".join(missing),
            "Which authenticated actor, tenant and workspace authorize this "
            "invoice commitment review?",
            checked=[f"missing={name}" for name in missing],
        )

    run_id = _reply_run_id(context)
    if not run_id:
        _commitment_gap(
            "execution_identity",
            "the persisted commitment review has no run id",
            "Which persisted assignment owns this invoice commitment review?",
            checked=["run_id=missing"],
        )

    lifecycle = _fresh_scoped_lifecycle(
        context,
        actor_id=actor_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    if lifecycle is None:
        _commitment_gap(
            "invoice_commitment_source",
            "the scoped lifecycle needed to re-read the reviewed reply is "
            "unavailable",
            "Which persisted invoice reply should be reviewed?",
            checked=["lifecycle=unavailable"],
        )

    try:
        record = lifecycle.get_task(run_id) or {}
    except Exception as exc:  # noqa: BLE001 — no external read happened
        _commitment_gap(
            "invoice_commitment_source",
            "the persisted task could not be re-read for the commitment "
            f"review: {type(exc).__name__}: {exc}",
            "Which persisted invoice reply should be reviewed?",
        )
    if not record:
        candidate = context.get("task") or context.get("task_record")
        if isinstance(candidate, Mapping):
            record = dict(candidate)
    if not isinstance(record, Mapping) or not record:
        _commitment_gap(
            "invoice_commitment_source",
            "the persisted task for the commitment review is missing",
            "Which persisted invoice reply should be reviewed?",
            checked=[f"run_id={run_id}"],
        )

    assignment = _commitment_assignment(record, context)
    current_step = _commitment_current_step(assignment, context)
    reply_step = _commitment_reply_predecessor(assignment, current_step)
    packet = _commitment_packet(record, reply_step, assignment)
    source = packet["source"]
    history = _commitment_revisions(
        assignment, _text(reply_step.get("step_id")))
    _commitment_assert_source(source, history)
    current = history[-1] if history else None
    revision = current.get("revision") if current else 0
    verdict = current.get("verdict") if current else None

    if verdict is None or verdict == "unclear":
        detail = (
            "the invoice reply has not been reviewed for a commitment yet"
            if verdict is None else
            "the reviewer marked the invoice reply unclear; a reviewer "
            "decision is still required")
        raise WaitingForExternal(_commitment_reviewer_waiting(
            context=context,
            record=record,
            source=source,
            step_id=_text(current_step.get("step_id")),
            revision=revision,
            detail=detail,
        ))

    committed = verdict == "confirmed"
    commitment_date = current.get("commitment_date") if committed else None
    attention = "owner" if verdict == "no_commitment" else None
    resolution = (
        "owner_attention" if verdict == "no_commitment"
        else "commitment_confirmed")
    invoice = dict(_send_step_invoice(packet["dispatch_step"]))
    for field in ("invoice_id", "invoice_number"):
        if source.get(field):
            invoice.setdefault(field, source[field])
    commitment = {
        "verdict": verdict,
        "revision": revision,
        "commitment_date": commitment_date,
        "reviewed_by": current.get("reviewed_by"),
        "reviewed_at": current.get("reviewed_at"),
        "source": dict(source),
        "attention": attention,
        "route": resolution,
    }
    attention_evidence = None
    if verdict == "no_commitment":
        attention_evidence = {
            "kind": "invoice_commitment",
            "verdict": verdict,
            "revision": revision,
            "attention": "owner",
            "route": "owner_attention",
            "source": dict(source),
        }
    data = {
        **commitment,
        "resolution": resolution,
        "current_revision": revision,
        "operation_id": source["operation_id"],
        "reply_operation_id": source["reply_operation_id"],
        "reply_message_id": source["reply_message_id"],
        "correlation_id": source["correlation_id"],
        "invoice_id": source.get("invoice_id"),
        "invoice_number": source.get("invoice_number"),
        "requires_owner_attention": verdict == "no_commitment",
        "attention_evidence": attention_evidence,
        "commitment": committed,
        "payment": False,
        "settled": False,
        "send_performed": False,
        "payment_asserted": False,
        "settlement_asserted": False,
    }
    return {
        "status": "applied",
        "action_result": "applied",
        "resolution": resolution,
        "route": resolution,
        "summary": (
            f"invoice reply commitment {verdict} at revision {revision}"
            + (f" for {commitment_date}" if commitment_date else "")),
        "verdict": verdict,
        "revision": revision,
        "current_revision": revision,
        "commitment_date": commitment_date,
        "reviewed_by": current.get("reviewed_by"),
        "reviewed_at": current.get("reviewed_at"),
        "attention": attention,
        "requires_owner_attention": verdict == "no_commitment",
        "attention_evidence": attention_evidence,
        "source": dict(source),
        "invoice": invoice,
        "operation_id": source["operation_id"],
        "dispatch_operation_id": source["operation_id"],
        "reply_operation_id": source["reply_operation_id"],
        "reply_message_id": source["reply_message_id"],
        "correlation_id": source["correlation_id"],
        "commitment": committed,
        "payment": False,
        "settled": False,
        "send_performed": False,
        "provider_state": "read_only",
        "data": data,
        "evidence": [dict(packet["evidence"])],
        "evidence_refs": [dict(packet["evidence"])],
        "verification": {
            "status": "verified",
            "resource_id": source["reply_message_id"],
            "version": f"invoice_commitment:{revision}",
            "coverage": {"complete": True, "truncated": False},
        },
    }


register_assignment_adapter(
    "invoice.await_commitment",
    description=(
        "Read the reviewer's commitment verdict for one verified invoice "
        "reply"),
    metadata={"effect": "read_only", "required_actions": ["retrieve"],
              "allow_standing_authorization": False},
)(_invoice_await_commitment)
