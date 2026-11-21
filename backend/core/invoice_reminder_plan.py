"""Server-owned builder for the stock invoice reminder/reply component.

This plan deliberately stops at the reply/commitment boundary. Settlement and
owner escalation are separate concerns and must be added before admission.
"""

from typing import Any, Dict

try:
    from core.assignment_plan import new_assignment, new_step
except ImportError:  # pragma: no cover - package imported relative to repo root
    from .assignment_plan import new_assignment, new_step

__all__ = ["build_invoice_reminder_plan"]


def _trusted(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonblank string")
    return value


def build_invoice_reminder_plan(
    *,
    invoice_number: str,
    user_id: str,
    workspace_id: str,
    tenant_id: str,
) -> Dict[str, Any]:
    """Build the reminder/reply portion of the stock invoice workflow."""
    invoice_number = _trusted(invoice_number, "invoice_number")
    user_id = _trusted(user_id, "user_id")
    workspace_id = _trusted(workspace_id, "workspace_id")
    tenant_id = _trusted(tenant_id, "tenant_id")

    steps = [
        new_step(
            step_id="lookup",
            title="Look up the invoice",
            operation_type="retrieve",
            adapter="invoice.lookup",
            effect="read_only",
            inputs={"invoice_number": invoice_number},
        ),
        new_step(
            step_id="prepare",
            title="Prepare the invoice reminder draft",
            operation_type="edit",
            adapter="invoice.prepare_reminder",
            effect="local",
            depends_on=["lookup"],
            inputs={
                "invoice_number": {"$ref": "lookup.data.invoice_number"},
                "expected_invoice_id": {"$ref": "lookup.data.invoice_id"},
            },
        ),
        new_step(
            step_id="send",
            title="Send the approved invoice reminder",
            operation_type="outbound",
            adapter="invoice.send_reminder",
            effect="external",
            approval_required=True,
            approval_purpose="Approve sending this exact invoice reminder draft",
            depends_on=["prepare"],
            inputs={
                "canvas_id": {"$ref": "prepare.draft.canvas_id"},
                "to": {"$ref": "prepare.draft.to"},
                "subject": {"$ref": "prepare.draft.subject"},
                "body": {"$ref": "prepare.draft.body"},
                "draft_revision": {"$ref": "prepare.artifact.revision"},
            },
        ),
        new_step(
            step_id="reply",
            title="Wait for the invoice reply",
            operation_type="retrieve",
            adapter="invoice.wait_for_reply",
            effect="read_only",
            depends_on=["send"],
            inputs={},
        ),
        new_step(
            step_id="commitment",
            title="Await the commitment decision",
            operation_type="retrieve",
            adapter="invoice.await_commitment",
            effect="read_only",
            depends_on=["reply"],
            inputs={},
        ),
    ]

    return new_assignment(
        objective=(
            "Prepare and send the invoice reminder, then await the reply and "
            f"commitment for invoice {invoice_number}"
        ),
        employee_id=user_id,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        authorized_actions=["edit", "outbound", "retrieve"],
        steps=steps,
    )
