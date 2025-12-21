"""
AP/AR Automation Engine - Phase 41
Accounts Payable and Accounts Receivable automation.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

class InvoiceStatus(Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"

class ReminderTone(Enum):
    FRIENDLY = "friendly"
    FIRM = "firm"
    FINAL = "final"

@dataclass
class APInvoice:
    """Accounts Payable - Invoice from vendor"""
    id: str
    vendor: str
    amount: float
    due_date: datetime
    line_items: List[Dict[str, Any]]
    status: InvoiceStatus = InvoiceStatus.PENDING_APPROVAL
    extracted_from: Optional[str] = None  # email, pdf, portal
    payment_terms: str = "Net 30"
    approved_by: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class ARInvoice:
    """Accounts Receivable - Invoice to customer"""
    id: str
    customer: str
    amount: float
    due_date: datetime
    line_items: List[Dict[str, Any]]
    status: InvoiceStatus = InvoiceStatus.DRAFT
    source: Optional[str] = None  # contract, crm_deal, time_tracking
    reminders_sent: int = 0
    last_reminder_date: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

class APAREngine:
    """
    Accounts Payable and Accounts Receivable automation.
    - AP: Invoice intake, parsing, approval workflows
    - AR: Invoice generation, intelligent collections
    """
    
    AUTO_APPROVE_THRESHOLD = 500.0  # Auto-approve invoices under this amount
    
    def __init__(self):
        self._ap_invoices: Dict[str, APInvoice] = {}
        self._ar_invoices: Dict[str, ARInvoice] = {}
        self._approval_rules: Dict[str, float] = {}  # vendor -> max auto-approve
    
    # ==================== ACCOUNTS PAYABLE ====================
    
    def intake_invoice(self, source: str, data: Dict[str, Any]) -> APInvoice:
        """
        Intake invoice from email, PDF, or portal.
        Parses and creates AP invoice.
        """
        invoice_id = f"ap_{datetime.now().timestamp()}"
        
        # Parse invoice data (in production, use OCR/AI extraction)
        invoice = APInvoice(
            id=invoice_id,
            vendor=data.get("vendor", "Unknown Vendor"),
            amount=data.get("amount", 0.0),
            due_date=datetime.fromisoformat(data["due_date"]) if "due_date" in data else datetime.now() + timedelta(days=30),
            line_items=data.get("line_items", []),
            extracted_from=source,
            payment_terms=data.get("payment_terms", "Net 30")
        )
        
        # Auto-approve if under threshold
        if invoice.amount < self.AUTO_APPROVE_THRESHOLD:
            invoice.status = InvoiceStatus.APPROVED
            invoice.approved_by = "auto"
            logger.info(f"Auto-approved AP invoice {invoice_id}: ${invoice.amount} < ${self.AUTO_APPROVE_THRESHOLD}")
        else:
            invoice.status = InvoiceStatus.PENDING_APPROVAL
        
        self._ap_invoices[invoice_id] = invoice
        return invoice
    
    def approve_invoice(self, invoice_id: str, approver: str) -> APInvoice:
        """Approve an AP invoice"""
        invoice = self._ap_invoices.get(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        invoice.status = InvoiceStatus.APPROVED
        invoice.approved_by = approver
        return invoice
    
    def get_pending_approvals(self) -> List[APInvoice]:
        """Get invoices pending approval"""
        return [inv for inv in self._ap_invoices.values() if inv.status == InvoiceStatus.PENDING_APPROVAL]
    
    def get_upcoming_payments(self, days: int = 7) -> List[APInvoice]:
        """Get approved invoices due in next N days"""
        cutoff = datetime.now() + timedelta(days=days)
        return [
            inv for inv in self._ap_invoices.values()
            if inv.status == InvoiceStatus.APPROVED and inv.due_date <= cutoff
        ]
    
    # ==================== ACCOUNTS RECEIVABLE ====================
    
    def generate_invoice(self, source: str, data: Dict[str, Any]) -> ARInvoice:
        """
        Generate AR invoice from contract, CRM deal, or time tracking.
        """
        invoice_id = f"ar_{datetime.now().timestamp()}"
        
        invoice = ARInvoice(
            id=invoice_id,
            customer=data.get("customer", "Unknown Customer"),
            amount=data.get("amount", 0.0),
            due_date=datetime.fromisoformat(data["due_date"]) if "due_date" in data else datetime.now() + timedelta(days=30),
            line_items=data.get("line_items", []),
            source=source,
            status=InvoiceStatus.DRAFT
        )
        
        self._ar_invoices[invoice_id] = invoice
        return invoice
    
    def send_invoice(self, invoice_id: str) -> ARInvoice:
        """Mark invoice as sent"""
        invoice = self._ar_invoices.get(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        invoice.status = InvoiceStatus.SENT
        return invoice
    
    def mark_paid(self, invoice_id: str) -> ARInvoice:
        """Mark invoice as paid"""
        invoice = self._ar_invoices.get(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        invoice.status = InvoiceStatus.PAID
        return invoice
    
    # ==================== INTELLIGENT COLLECTIONS ====================
    
    def get_overdue_invoices(self) -> List[ARInvoice]:
        """Get overdue AR invoices"""
        now = datetime.now()
        overdue = []
        
        for inv in self._ar_invoices.values():
            if inv.status == InvoiceStatus.SENT and inv.due_date < now:
                inv.status = InvoiceStatus.OVERDUE
                overdue.append(inv)
        
        return overdue
    
    def generate_reminder(self, invoice_id: str) -> Dict[str, Any]:
        """
        Generate collection reminder with appropriate tone.
        Escalates: friendly → firm → final
        """
        invoice = self._ar_invoices.get(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        # Determine tone based on reminder count
        if invoice.reminders_sent == 0:
            tone = ReminderTone.FRIENDLY
            subject = "Friendly Reminder: Invoice Due"
            message = f"Just a friendly reminder that invoice #{invoice.id} for ${invoice.amount:.2f} is now due."
        elif invoice.reminders_sent == 1:
            tone = ReminderTone.FIRM
            subject = "Second Notice: Payment Overdue"
            message = f"This is a second notice regarding invoice #{invoice.id} for ${invoice.amount:.2f}. Please remit payment promptly."
        else:
            tone = ReminderTone.FINAL
            subject = "Final Notice: Immediate Attention Required"
            message = f"FINAL NOTICE: Invoice #{invoice.id} for ${invoice.amount:.2f} remains unpaid. Please contact us immediately."
        
        invoice.reminders_sent += 1
        invoice.last_reminder_date = datetime.now()
        
        return {
            "invoice_id": invoice_id,
            "customer": invoice.customer,
            "amount": invoice.amount,
            "tone": tone.value,
            "subject": subject,
            "message": message,
            "reminders_sent": invoice.reminders_sent
        }
    
    def get_collection_summary(self) -> Dict[str, Any]:
        """Get AR collection summary"""
        total_outstanding = sum(
            inv.amount for inv in self._ar_invoices.values()
            if inv.status in [InvoiceStatus.SENT, InvoiceStatus.OVERDUE]
        )
        overdue_count = sum(1 for inv in self._ar_invoices.values() if inv.status == InvoiceStatus.OVERDUE)
        
        return {
            "total_outstanding": total_outstanding,
            "overdue_count": overdue_count,
            "invoices_sent": sum(1 for inv in self._ar_invoices.values() if inv.status == InvoiceStatus.SENT),
            "invoices_paid": sum(1 for inv in self._ar_invoices.values() if inv.status == InvoiceStatus.PAID)
        }

# Global instance
apar_engine = APAREngine()
