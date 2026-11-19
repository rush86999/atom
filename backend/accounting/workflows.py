from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, List
from accounting.models import Entity, Invoice, InvoiceStatus
from sqlalchemy.orm import Session

from core.websockets import manager

logger = logging.getLogger(__name__)


def _as_utc(value: datetime) -> datetime:
    """Treat naive (e.g. SQLite round-tripped) timestamps as UTC; leave aware ones as-is."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _as_decimal(value: Any) -> Decimal:
    """Coerce an invoice amount to Decimal without binary-float arithmetic.

    ORM amounts are Decimal while existing fixtures use int/float.  Building
    from ``str(float)`` keeps the fixture's visible value instead of inheriting
    the binary float's full expansion.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return Decimal(int(value))
    return Decimal(str(value))


def _json_number(value: Any) -> float:
    """Render an amount as a plain JSON number (never Decimal or a string)."""
    return float(_as_decimal(value))


class CollectionAgent:
    """
    Automated agent for monitoring Accounts Receivable and preparing internal follow-up previews.
    """

    def __init__(self, db: Session):
        self.db = db

    async def check_overdue_invoices(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Flag invoices that are past their due date and prepare internal reminder previews.

        This does not deliver reminders outbound; it only updates invoice state and
        broadcasts previews for internal display.
        """
        now = datetime.now(timezone.utc)
        overdue_invoices = self.db.query(Invoice).filter(
            Invoice.workspace_id == workspace_id,
            Invoice.status == InvoiceStatus.OPEN,
            Invoice.due_date < now
        ).all()

        reminder_previews = []

        for invoice in overdue_invoices:
            # 1. Update status to OVERDUE
            invoice.status = InvoiceStatus.OVERDUE

            # 2. Generate an internal reminder preview
            reminder = self._generate_reminder_message(invoice)

            # 3. Broadcast the preview to the workspace UI (no outbound delivery)
            logger.info(
                "Flagged Invoice %s as overdue for %s; internal reminder preview prepared "
                "(delivery status: not sent)",
                invoice.invoice_number,
                invoice.customer.name,
            )

            # Internal notification for the user (preview only; not sent outbound)
            await manager.broadcast(f"workspace:{workspace_id}", {
                "type": "accounting.reminder_prepared",
                "data": {
                    "invoice_id": invoice.id,
                    "customer": invoice.customer.name,
                    # Wire boundary: send_json uses the standard encoder,
                    # which cannot serialize the ORM's Decimal amount.
                    "amount": _json_number(invoice.amount),
                    "reminder": reminder,
                    "delivery_status": "not_sent"
                }
            })

            reminder_previews.append({
                "invoice_id": invoice.id,
                "customer": invoice.customer.name,
                "amount": invoice.amount
            })

        self.db.commit()
        return reminder_previews

    def _generate_reminder_message(self, invoice: Invoice) -> str:
        """AI-assisted (template for now) reminder generation"""
        days_overdue = (datetime.now(timezone.utc) - _as_utc(invoice.due_date)).days
        return (
            f"Hello {invoice.customer.name}, this is a reminder that Invoice {invoice.invoice_number} "
            f"for ${invoice.amount:,.2f} is now {days_overdue} days overdue. "
            "Please process the payment at your earliest convenience."
        )

    def generate_aging_report(self, workspace_id: str) -> Dict[str, Any]:
        """Generate a summary of AR aging"""
        invoices = self.db.query(Invoice).filter(
            Invoice.workspace_id == workspace_id,
            Invoice.status.in_([InvoiceStatus.OPEN, InvoiceStatus.OVERDUE])
        ).all()

        now = datetime.now(timezone.utc)
        # Accumulate in Decimal so ORM amounts never mix with float seeds.
        totals = {
            "current": Decimal("0"),      # 0-30 days
            "overdue_30": Decimal("0"),   # 31-60 days
            "overdue_60": Decimal("0"),   # 61-90 days
            "overdue_90": Decimal("0"),   # 90+ days
            "total_ar": Decimal("0")
        }

        for inv in invoices:
            days = (now - _as_utc(inv.due_date)).days
            amount = _as_decimal(inv.amount)
            totals["total_ar"] += amount
            if days <= 0:
                totals["current"] += amount
            elif days <= 30:
                totals["overdue_30"] += amount
            elif days <= 60:
                totals["overdue_60"] += amount
            else:
                totals["overdue_90"] += amount

        # Output boundary keeps the existing JSON-numeric values/keys.
        return {key: _json_number(value) for key, value in totals.items()}
