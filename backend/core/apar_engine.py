"""
AP/AR Automation Engine - Phase 41
Accounts Payable and Accounts Receivable automation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import io
import logging
from typing import Any, Dict, List, Optional

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

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
            due_date=datetime.fromisoformat(data["due_date"]) if data.get("due_date") else datetime.now() + timedelta(days=30),
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
    
    def get_all_invoices(self) -> List[Any]:
        """Get all AR and AP invoices combined and sorted by creation date"""
        all_invs = list(self._ar_invoices.values()) + list(self._ap_invoices.values())
        return sorted(all_invs, key=lambda inv: inv.created_at, reverse=True)
    
    def generate_invoice_content(self, invoice_id: str) -> str:
        """Generate text-based content for an invoice (simulates PDF generation)"""
        invoice = self._ar_invoices.get(invoice_id) or self._ap_invoices.get(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        content = f"--- INVOICE {invoice.id} ---\n"
        content += f"Type: {'AR' if invoice_id.startswith('ar') else 'AP'}\n"
        content += f"Entity: {invoice.customer if hasattr(invoice, 'customer') else invoice.vendor}\n"
        content += f"Amount: ${invoice.amount:.2f}\n"
        content += f"Due Date: {invoice.due_date.strftime('%Y-%m-%d')}\n"
        content += f"Status: {invoice.status.value}\n"
        content += "Line Items:\n"
        for item in invoice.line_items:
            content += f"- {item.get('description', 'Item')}: ${item.get('amount', 0.0):.2f}\n"
        content += "--- END ---\n"
        return content

    def generate_invoice_pdf(self, invoice_id: str) -> bytes:
        """Generates a professional PDF invoice using ReportLab."""
        invoice = self._ar_invoices.get(invoice_id) or self._ap_invoices.get(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        if not HAS_REPORTLAB:
            raise ImportError("ReportLab is not installed. Please install it to generate PDFs.")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Add custom styles for a cleaner look
        title_style = ParagraphStyle('InvoiceTitle', parent=styles['Heading1'], fontSize=24, spaceAfter=20)
        subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=10, textColor=colors.gray)
        bold_style = ParagraphStyle('BoldText', parent=styles['Normal'], fontName='Helvetica-Bold')

        # Company Header
        elements.append(Paragraph("<b>Atom Accounting</b>", title_style))
        elements.append(Paragraph("123 Financial District", subtitle_style))
        elements.append(Paragraph("New York, NY 10004", subtitle_style))
        elements.append(Paragraph("billing@atom.app", subtitle_style))
        elements.append(Spacer(1, 30))

        # Invoice Metadata
        invoice_type = 'Accts Receivable' if invoice_id.startswith('ar') else 'Accts Payable'
        entity_name = invoice.customer if hasattr(invoice, 'customer') else invoice.vendor
        
        meta_data = [
            ["INVOICE #:", invoice.id.upper()],
            ["TYPE:", invoice_type],
            ["DATE:", invoice.created_at.strftime('%Y-%m-%d')],
            ["DUE DATE:", invoice.due_date.strftime('%Y-%m-%d')],
            ["STATUS:", invoice.status.value.upper()]
        ]
        
        meta_table = Table(meta_data, colWidths=[100, 200])
        meta_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.dimgrey),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(Paragraph(f"<b>BILL TO:</b> {entity_name}", bold_style))
        elements.append(Spacer(1, 10))
        elements.append(meta_table)
        elements.append(Spacer(1, 30))

        # Line Items Table
        table_data = [['Description', 'Amount']]
        
        for item in invoice.line_items:
            desc = item.get('description', 'Item')
            amt = f"${item.get('amount', 0.0):,.2f}"
            table_data.append([desc, amt])
            
        # Add Total Row
        table_data.append(['TOTAL', f"${invoice.amount:,.2f}"])

        # Create the Table
        item_table = Table(table_data, colWidths=[350, 100])
        item_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')), # Slate 900
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')), # Slate 50
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'), # Align amounts to the right
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'), # Make Total bold
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black), # Line above total
            ('GRID', (0, 0), (-1, -2), 1, colors.HexColor('#e2e8f0')), # Grid lines for items
        ]))
        
        elements.append(item_table)
        elements.append(Spacer(1, 50))
        
        # Footer
        elements.append(Paragraph("Thank you for your business!", styles['Italic']))

        # Build PDF and return bytes
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes

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
