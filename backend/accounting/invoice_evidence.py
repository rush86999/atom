"""Read-only invoice evidence from the local accounting ledger.

This module is the first, independent stage of the stock invoice workflow.  It
answers one narrow question: "which ledger invoice did this workspace record
under this exact invoice number?"  It deliberately does not contact a customer,
mutate ledger rows, ask a payment provider for a status, or expose an HTTP
route.

The only payment state returned is the state *recorded on the Invoice row*
(``recorded_paid``).  A true value means only that the ledger row records
``InvoiceStatus.PAID``; this read makes no provider-side settlement claim.

The module also prepares local ``email.draft`` inputs for the stock
``htn_invoice_followup`` reminder.  That preparation reuses the same authority
and exact-workspace lookup, resolves the recipient from the stored invoice
customer, and returns draft content only; it never writes or sends.
"""
from __future__ import annotations

import enum
import re
from contextlib import nullcontext
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from email.utils import getaddresses
from typing import Any, Dict, Optional

from accounting.models import Invoice, InvoiceStatus
from core.models import User, Workspace

# Provenance labels for downstream consumers.  The former is the evidence
# source; the latter identifies the concrete ledger table the row came from.
LEDGER_SOURCE = "local_ledger"
INVOICE_SOURCE_TABLE = "accounting_invoices"


class InvoiceEvidenceError(ValueError, LookupError):
    """The only refusal type for an invoice evidence read.

    ``code`` is stable for every refusal so callers can branch on the type and
    code without depending on exception subclasses.  The specific condition is
    carried as data in ``reason``; only the explicit fields below become
    attributes, never arbitrary keys supplied by a caller.
    """

    code = "invoice_evidence_error"

    def __init__(self, message: str, *, reason: str, **details: Any):
        self.message = str(message)
        self.reason = str(reason)
        self.details = dict(details)
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Structured refusal for callers that need to surface a reason."""
        payload = dict(self.details)
        # Reserved fields always win over detail data, keeping ``code`` stable.
        payload.update(
            {
                "ok": False,
                "code": self.code,
                "reason": self.reason,
                "message": self.message,
            }
        )
        return payload


def _refuse(message: str, *, reason: str, **details: Any) -> InvoiceEvidenceError:
    return InvoiceEvidenceError(message, reason=reason, **details)


def _no_autoflush(db: Any) -> Any:
    """Suspend autoflush without expiring or writing any session state.

    A read must never flush an unrelated pending/dirty object.  SQLAlchemy
    sessions expose ``no_autoflush``; a simple adapter without it falls back to
    a no-op context.
    """
    manager = getattr(db, "no_autoflush", None)
    if manager is None:
        return nullcontext()
    if not hasattr(manager, "__enter__") and callable(manager):
        manager = manager()
    return manager


def _required_text(field: str, value: Any) -> str:
    """Return an explicitly supplied identifier, refusing missing values.

    Missing ids are not replaced with a Personal-Edition default here.  Scope
    must be proven from persisted rows, so "absent" is a refusal rather than an
    implicit namespace.
    """
    if value is None or str(value) == "":
        raise _refuse(
            f"{field} is required for invoice evidence",
            reason=f"{field}_required",
            field=field,
        )
    return str(value)


def _persisted_scope(field: str, value: Any, **details: Any) -> str:
    """Return a persisted scope id, refusing an absent value.

    This is deliberately different from a request-side lookup helper: a row
    whose tenant/workspace is NULL or blank has no exact scope and must not be
    treated as the "default" scope.
    """
    if value is None or str(value) == "":
        raise _refuse(
            f"persisted {field} is missing",
            reason=f"{field}_missing",
            field=field,
            **details,
        )
    return str(value)


def _require_current_actor(
    db: Any, *, actor_id: str, tenant_id: str, workspace_id: str
) -> None:
    """Verify the current persisted actor against the exact requested scope.

    The request snapshot is never authority.  Fresh scalar columns are read so
    a stale identity-map instance cannot authorize the request, and no
    ``expire_all``/flush is needed to obtain those values.
    """
    actor = (
        db.query(
            User.is_active,
            User.status,
            User.tenant_id,
            User.workspace_id,
        )
        .filter(User.id == actor_id)
        .first()
    )
    if actor is None:
        raise _refuse(
            "actor not found",
            reason="actor_not_found",
            actor_id=actor_id,
        )

    is_active, status, actor_tenant_raw, actor_workspace_raw = actor
    if not bool(is_active):
        raise _refuse(
            "actor is not active",
            reason="actor_inactive",
            actor_id=actor_id,
        )

    recorded_status = _recorded_status(status).strip().lower()
    if recorded_status not in ("", "active"):
        raise _refuse(
            "actor is not active",
            reason="actor_inactive",
            actor_id=actor_id,
            status=recorded_status,
        )

    actor_tenant = _persisted_scope(
        "actor_tenant_id",
        actor_tenant_raw,
        actor_id=actor_id,
    )
    actor_workspace = _persisted_scope(
        "actor_workspace_id",
        actor_workspace_raw,
        actor_id=actor_id,
    )
    if actor_tenant != tenant_id or actor_workspace != workspace_id:
        raise _refuse(
            "actor does not belong to the requested tenant and workspace",
            reason="actor_scope_mismatch",
            actor_id=actor_id,
            actor_tenant_id=actor_tenant,
            actor_workspace_id=actor_workspace,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )


def _require_workspace(db: Any, *, tenant_id: str, workspace_id: str) -> Any:
    """Resolve the persisted workspace and prove it belongs to the tenant."""
    workspace = (
        db.query(
            Workspace.id,
            Workspace.name,
            Workspace.tenant_id,
            Workspace.status,
        )
        .filter(Workspace.id == workspace_id)
        .first()
    )
    if workspace is None:
        raise _refuse(
            "workspace not found",
            reason="workspace_not_found",
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )

    _workspace_id, name, workspace_tenant_raw, status = workspace
    workspace_tenant = _persisted_scope(
        "workspace_tenant_id",
        workspace_tenant_raw,
        workspace_id=workspace_id,
    )
    if workspace_tenant != tenant_id:
        raise _refuse(
            "workspace does not belong to the requested tenant",
            reason="workspace_tenant_mismatch",
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            workspace_tenant_id=workspace_tenant,
        )

    workspace_status = _recorded_status(status).strip().lower()
    if workspace_status not in ("", "active", "trial"):
        raise _refuse(
            "workspace is not active",
            reason="workspace_inactive",
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            status=workspace_status,
        )
    return name


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Normalize a ledger timestamp to an aware UTC datetime.

    Naive timestamps (for example values round-tripped through SQLite) are the
    ledger's UTC values; aware timestamps are converted rather than relabelled.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _decimal_string(value: Any) -> str:
    """Render a recorded amount exactly, refusing missing/invalid values.

    Amounts are never defaulted to zero.  Decimal values are preserved at their
    recorded precision (including trailing zeros); non-finite values and
    booleans are ambiguous monetary data and are refused.
    """
    if value is None:
        raise _refuse(
            "invoice amount is missing",
            reason="invoice_amount_missing",
        )
    if isinstance(value, bool):
        raise _refuse(
            "invoice amount is not a valid decimal",
            reason="invoice_amount_invalid",
        )
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise _refuse(
            "invoice amount is not a valid decimal",
            reason="invoice_amount_invalid",
        ) from exc
    if not amount.is_finite():
        raise _refuse(
            "invoice amount is not a finite decimal",
            reason="invoice_amount_invalid",
        )
    return format(amount, "f")


def _recorded_status(value: Any) -> str:
    """Return the recorded status as its stored string value."""
    if isinstance(value, enum.Enum):
        return str(value.value)
    if value is None:
        return ""
    return str(value)


def _aging(
    due_date: Optional[datetime], *, as_of: datetime, recorded_paid: bool
) -> Dict[str, Any]:
    """Bounded aging facts derived only from the recorded due date."""
    if due_date is None:
        return {
            "is_overdue": False,
            "days_overdue": None,
            "days_until_due": None,
            "aging_bucket": "paid" if recorded_paid else "unknown",
        }

    delta_days = (as_of - due_date).days
    days_overdue = max(delta_days, 0)
    days_until_due = max(-delta_days, 0)
    is_overdue = bool(delta_days > 0 and not recorded_paid)

    if recorded_paid:
        bucket = "paid"
    elif delta_days <= 0:
        bucket = "current"
    elif delta_days <= 30:
        bucket = "overdue_30"
    elif delta_days <= 60:
        bucket = "overdue_60"
    else:
        bucket = "overdue_90"

    return {
        "is_overdue": is_overdue,
        "days_overdue": days_overdue,
        "days_until_due": days_until_due,
        "aging_bucket": bucket,
    }


def _load_invoice(
    db: Any,
    *,
    actor_id: Any,
    tenant_id: Any,
    workspace_id: Any,
    invoice_number: Any,
    as_of: Optional[datetime] = None,
    include_customer: bool = False,
) -> Dict[str, Any]:
    """Load one invoice under the read authority shared with ordinary reads.

    This is the private half of :func:`read_invoice_evidence`.  It performs the
    same actor/workspace proof and exact-workspace invoice lookup, then returns
    the bounded ledger facts plus the recorded ``customer_id`` for the local
    reminder preparer.  The customer id is internal: the public read removes it
    before returning.
    """
    tenant_id = _required_text("tenant_id", tenant_id)
    workspace_id = _required_text("workspace_id", workspace_id)
    actor_id = _required_text("actor_id", actor_id)
    invoice_number = _required_text("invoice_number", invoice_number)

    # A read must not autoflush pending changes belonging to someone else.
    with _no_autoflush(db):
        _require_current_actor(
            db,
            actor_id=actor_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        workspace_name = _require_workspace(
            db, tenant_id=tenant_id, workspace_id=workspace_id
        )

        # Exact match only: no case folding, trimming, prefix matching, or
        # cross-workspace fallback.  Fetch all matches so duplicate recorded
        # rows are refused as ambiguous rather than silently selecting first.
        columns = [
            Invoice.id,
            Invoice.workspace_id,
            Invoice.invoice_number,
            Invoice.status,
            Invoice.amount,
            Invoice.currency,
            Invoice.due_date,
        ]
        if include_customer:
            columns.append(Invoice.customer_id)
        matches = (
            db.query(*columns)
            .filter(
                Invoice.workspace_id == workspace_id,
                Invoice.invoice_number == invoice_number,
            )
            .all()
        )

    if not matches:
        raise _refuse(
            "invoice not found in this workspace",
            reason="invoice_not_found",
            invoice_number=invoice_number,
            workspace_id=workspace_id,
        )
    if len(matches) > 1:
        raise _refuse(
            "invoice number is ambiguous in this workspace",
            reason="invoice_ambiguous",
            invoice_number=invoice_number,
            workspace_id=workspace_id,
            candidate_ids=[str(row[0]) for row in matches],
        )

    (
        invoice_id,
        invoice_workspace_raw,
        recorded_number,
        recorded_status_raw,
        amount_raw,
        currency_raw,
        due_date_raw,
        *customer_columns,
    ) = matches[0]
    customer_id_raw = customer_columns[0] if customer_columns else None

    invoice_workspace = _persisted_scope(
        "invoice_workspace_id",
        invoice_workspace_raw,
        invoice_number=invoice_number,
    )
    if invoice_workspace != workspace_id:
        # Defense in depth: a query/session adapter must not leak a foreign
        # workspace row into this read.
        raise _refuse(
            "invoice does not belong to the requested workspace",
            reason="invoice_scope_mismatch",
            invoice_number=invoice_number,
            workspace_id=workspace_id,
            invoice_workspace_id=invoice_workspace,
        )

    status = _recorded_status(recorded_status_raw)
    recorded_paid = status.strip().lower() == InvoiceStatus.PAID.value

    due_date = _as_utc(due_date_raw)
    observation = (
        _as_utc(as_of)
        if as_of is not None
        else datetime.now(timezone.utc)
    )
    aging = _aging(due_date, as_of=observation, recorded_paid=recorded_paid)

    amount = _decimal_string(amount_raw)
    currency = None if currency_raw is None else str(currency_raw)

    return {
        # Recorded invoice identity and status.
        "invoice_id": str(invoice_id),
        "invoice_number": recorded_number,
        "status": status,
        # Exact recorded monetary value and the currency actually recorded.
        "amount": amount,
        "currency": currency,
        # UTC-normalized due date plus a stable observation timestamp.
        "due_date": due_date.isoformat() if due_date is not None else None,
        "as_of": observation.isoformat(),
        # Exact ledger scope and provenance.
        "workspace_id": invoice_workspace,
        "tenant_id": tenant_id,
        "workspace_name": workspace_name,
        "source": LEDGER_SOURCE,
        "source_table": INVOICE_SOURCE_TABLE,
        # Recorded payment state only; there is no provider claim here.
        "recorded_paid": recorded_paid,
        **aging,
        # Internal join key for the local preparer; stripped from public reads.
        "customer_id": (
            None if customer_id_raw is None else str(customer_id_raw)
        ),
    }


def read_invoice_evidence(
    db: Any,
    *,
    actor_id: Any,
    tenant_id: Any,
    workspace_id: Any,
    invoice_number: Any,
) -> Dict[str, Any]:
    """Read bounded evidence for one recorded invoice.

    Parameters are keyword-only.  The persisted actor row behind ``actor_id``
    must currently be active and its stored tenant/workspace must exactly match
    ``tenant_id``/``workspace_id``.  The workspace must belong to the tenant,
    and the invoice number must match exactly one row in that workspace.

    Returns a plain dictionary containing only bounded ledger facts: identifier,
    number, recorded status, exact decimal amount string, recorded currency,
    UTC due date, workspace provenance, aging facts, and ``recorded_paid``.
    Customer contact details and the free-form invoice description are never
    returned.

    Raises ``InvoiceEvidenceError`` (with a stable ``code`` and a specific
    ``reason``) instead of guessing when scope is not authoritative, the
    invoice is missing, or the exact number is ambiguous.  This function
    performs reads only: it never adds, updates, deletes, commits, flushes,
    expires, refreshes, or sends anything.
    """
    facts = _load_invoice(
        db,
        actor_id=actor_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        invoice_number=invoice_number,
    )
    # The customer join key is preparer-internal.  In particular, contact
    # details are never part of the ordinary evidence result.
    facts.pop("customer_id", None)
    return facts


_EMAIL_ADDRESS = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def _literal_text(field: str, value: Any) -> str:
    """Return a header/body-safe literal, refusing control characters.

    Stored ledger values are data, not formatting instructions.  Newlines and
    other control characters are refused rather than silently rewritten so a
    malformed invoice number cannot inject an email header or body line.
    """
    text = "" if value is None else str(value)
    if any(ord(character) < 32 or ord(character) == 127 for character in text):
        raise _refuse(
            f"{field} contains unsafe control characters",
            reason=f"{field}_unsafe",
            field=field,
        )
    return text


def _single_mailbox(value: Any, *, invoice_id: str, workspace_id: str) -> str:
    """Return the one stored recipient mailbox, never a caller-supplied list."""
    if value is None or not str(value).strip():
        raise _refuse(
            "invoice customer has no email address",
            reason="customer_email_missing",
            invoice_id=invoice_id,
            workspace_id=workspace_id,
        )

    raw_text = str(value)
    if any(ord(character) < 32 or ord(character) == 127
           for character in raw_text):
        raise _refuse(
            "invoice customer email is not a valid single mailbox",
            reason="customer_email_invalid",
            invoice_id=invoice_id,
            workspace_id=workspace_id,
        )
    text = raw_text.strip()
    parsed = getaddresses([text])
    if len(parsed) != 1:
        raise _refuse(
            "invoice customer email must be exactly one mailbox",
            reason="customer_email_invalid",
            invoice_id=invoice_id,
            workspace_id=workspace_id,
        )

    _display_name, address = parsed[0]
    address = str(address or "").strip()
    if (
        not address
        or address != str(parsed[0][1] or "")
        or _EMAIL_ADDRESS.fullmatch(address) is None
    ):
        raise _refuse(
            "invoice customer email is not a valid single mailbox",
            reason="customer_email_invalid",
            invoice_id=invoice_id,
            workspace_id=workspace_id,
        )
    return address


def _load_customer(
    db: Any, *, customer_id: str, workspace_id: str
) -> Any:
    """Read the exact stored invoice customer and prove same-workspace scope."""
    from accounting.models import Entity

    with _no_autoflush(db):
        customer = (
            db.query(Entity.id, Entity.workspace_id, Entity.email)
            .filter(Entity.id == customer_id)
            .first()
        )

    if customer is None:
        raise _refuse(
            "invoice customer not found",
            reason="customer_not_found",
            customer_id=customer_id,
            workspace_id=workspace_id,
        )

    _customer_id, customer_workspace_raw, email = customer
    customer_workspace = _persisted_scope(
        "customer_workspace_id",
        customer_workspace_raw,
        customer_id=customer_id,
    )
    if customer_workspace != workspace_id:
        raise _refuse(
            "invoice customer does not belong to the invoice workspace",
            reason="customer_scope_mismatch",
            customer_id=customer_id,
            workspace_id=workspace_id,
            customer_workspace_id=customer_workspace,
        )
    return email


def _reminder_content(facts: Dict[str, Any]) -> Dict[str, str]:
    """Compose deterministic plain-text reminder content from recorded facts."""
    invoice_number = _literal_text(
        "invoice_number", facts.get("invoice_number"))
    amount = _literal_text("invoice_amount", facts.get("amount"))
    currency_raw = facts.get("currency")
    if currency_raw is None or not str(currency_raw).strip():
        raise _refuse(
            "invoice currency is missing",
            reason="invoice_currency_missing",
            invoice_id=facts.get("invoice_id"),
            workspace_id=facts.get("workspace_id"),
        )
    currency = _literal_text("invoice_currency", currency_raw)
    due_date = _literal_text("invoice_due_date", facts.get("due_date"))

    subject = f"Payment reminder for invoice {invoice_number}"
    body = (
        "Hello,\n\n"
        f"This is a friendly reminder that invoice {invoice_number} for "
        f"{amount} {currency} remains outstanding. The recorded due date was "
        f"{due_date}.\n\n"
        "Please arrange payment at your earliest convenience.\n\n"
        "Thank you."
    )
    return {"subject": subject, "body": body}


def prepare_invoice_reminder(
    db: Any,
    *,
    actor_id: Any,
    tenant_id: Any,
    workspace_id: Any,
    invoice_number: Any,
    as_of: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Prepare local ``email.draft`` inputs for one overdue open invoice.

    The recipient is resolved only from the ``Invoice.customer_id`` row stored
    in the same workspace as the invoice.  The result is the canonical local
    draft input shape consumed by the assignment executor: a single ``to``
    recipient, empty ``cc``, a plain-text ``subject``/``body`` built from the
    exact recorded currency and amount, and stable invoice/workspace evidence.

    Refusals use the same ``InvoiceEvidenceError`` code as the evidence read.
    This function performs reads only; it does not write, send, contact a
    provider, or expose the customer mailbox through
    :func:`read_invoice_evidence`.
    """
    facts = _load_invoice(
        db,
        actor_id=actor_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        invoice_number=invoice_number,
        as_of=as_of,
        include_customer=True,
    )

    status = str(facts.get("status") or "").strip().lower()
    if status != InvoiceStatus.OPEN.value:
        raise _refuse(
            "invoice is not open",
            reason="invoice_not_open",
            invoice_id=facts.get("invoice_id"),
            invoice_number=facts.get("invoice_number"),
            workspace_id=facts.get("workspace_id"),
            status=status,
        )
    if not facts.get("is_overdue"):
        raise _refuse(
            "invoice is not overdue",
            reason="invoice_not_overdue",
            invoice_id=facts.get("invoice_id"),
            invoice_number=facts.get("invoice_number"),
            workspace_id=facts.get("workspace_id"),
            due_date=facts.get("due_date"),
        )

    customer_id = facts.get("customer_id")
    if customer_id is None or str(customer_id) == "":
        raise _refuse(
            "invoice has no stored customer",
            reason="customer_missing",
            invoice_id=facts.get("invoice_id"),
            invoice_number=facts.get("invoice_number"),
            workspace_id=facts.get("workspace_id"),
        )
    customer_id = str(customer_id)

    email = _load_customer(
        db, customer_id=customer_id, workspace_id=facts["workspace_id"])
    recipient = _single_mailbox(
        email,
        invoice_id=facts["invoice_id"],
        workspace_id=facts["workspace_id"],
    )
    content = _reminder_content(facts)

    return {
        # Canonical local email.draft inputs.  In particular there is no
        # sender override, provider, send flag, or external action here.
        "to": [recipient],
        "cc": [],
        "subject": content["subject"],
        "body": content["body"],
        # Stable provenance ties the draft to the exact ledger invoice and
        # workspace that authorized the read.
        "evidence": {
            "source": facts["source"],
            "source_table": facts["source_table"],
            "invoice_id": facts["invoice_id"],
            "invoice_number": facts["invoice_number"],
            "workspace_id": facts["workspace_id"],
            "tenant_id": facts["tenant_id"],
            "amount": facts["amount"],
            "currency": facts["currency"],
            "due_date": facts["due_date"],
        },
    }


# Names used by different callers for the same narrowly scoped local
# preparation.  They intentionally share one implementation and one authority.
prepare_invoice_followup = prepare_invoice_reminder
prepare_invoice_followup_reminder = prepare_invoice_reminder
prepare_invoice_reminder_draft = prepare_invoice_reminder
prepare_invoice_reminder_inputs = prepare_invoice_reminder
prepare_invoice_followup_reminder_inputs = prepare_invoice_reminder
