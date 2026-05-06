"""
Test suite for core.apar_engine module.

This module tests AP/AR invoice automation:
- InvoiceStatus and ReminderTone enums
- APInvoice and ARInvoice dataclasses
- Accounts Payable operations (intake, approval, payments)
- Accounts Receivable operations (generation, reminders)
- Reminder system and overdue detection

All functions in this module use dataclasses and pure business logic,
making them ideal for comprehensive unit testing.

Test Strategy:
- Test dataclass creation and validation
- Test approval workflows and thresholds
- Test reminder generation and tracking
- Test overdue detection
- Test invoice lifecycle
"""

import pytest
from datetime import datetime, timedelta
from core.apar_engine import (
    APAREngine,
    APInvoice,
    ARInvoice,
    InvoiceStatus,
    ReminderTone
)


# ==============================================================================
# Enum Tests
# ==============================================================================

class TestInvoiceStatus:
    """Test InvoiceStatus enum."""

    def test_invoice_status_draft_value(self):
        """Test DRAFT status value."""
        assert InvoiceStatus.DRAFT.value == "draft"

    def test_invoice_status_pending_approval_value(self):
        """Test PENDING_APPROVAL status value."""
        assert InvoiceStatus.PENDING_APPROVAL.value == "pending_approval"

    def test_invoice_status_approved_value(self):
        """Test APPROVED status value."""
        assert InvoiceStatus.APPROVED.value == "approved"

    def test_invoice_status_sent_value(self):
        """Test SENT status value."""
        assert InvoiceStatus.SENT.value == "sent"

    def test_invoice_status_paid_value(self):
        """Test PAID status value."""
        assert InvoiceStatus.PAID.value == "paid"

    def test_invoice_status_overdue_value(self):
        """Test OVERDUE status value."""
        assert InvoiceStatus.OVERDUE.value == "overdue"


class TestReminderTone:
    """Test ReminderTone enum."""

    def test_reminder_tone_friendly_value(self):
        """Test FRIENDLY tone value."""
        assert ReminderTone.FRIENDLY.value == "friendly"

    def test_reminder_tone_firm_value(self):
        """Test FIRM tone value."""
        assert ReminderTone.FIRM.value == "firm"

    def test_reminder_tone_final_value(self):
        """Test FINAL tone value."""
        assert ReminderTone.FINAL.value == "final"


# ==============================================================================
# Dataclass Tests
# ==============================================================================

class TestAPInvoiceDataclass:
    """Test APInvoice dataclass."""

    def test_ap_invoice_creation(self):
        """Create AP invoice with required fields."""
        invoice = APInvoice(
            id="ap-001",
            vendor="Acme Corp",
            amount=1500.00,
            due_date=datetime(2026, 6, 1),
            line_items=[{"description": "Consulting", "amount": 1500.00}]
        )

        assert invoice.id == "ap-001"
        assert invoice.vendor == "Acme Corp"
        assert invoice.amount == 1500.00
        assert invoice.status == InvoiceStatus.PENDING_APPROVAL

    def test_ap_invoice_with_custom_status(self):
        """Create AP invoice with custom status."""
        invoice = APInvoice(
            id="ap-002",
            vendor="Vendor Inc",
            amount=500.00,
            due_date=datetime(2026, 6, 1),
            line_items=[],
            status=InvoiceStatus.APPROVED
        )

        assert invoice.status == InvoiceStatus.APPROVED

    def test_ap_invoice_with_optional_fields(self):
        """Create AP invoice with optional fields."""
        invoice = APInvoice(
            id="ap-003",
            vendor="Test Vendor",
            amount=1000.00,
            due_date=datetime(2026, 6, 1),
            line_items=[],
            extracted_from="email",
            payment_terms="Net 45",
            approved_by="john.doe"
        )

        assert invoice.extracted_from == "email"
        assert invoice.payment_terms == "Net 45"
        assert invoice.approved_by == "john.doe"


class TestARInvoiceDataclass:
    """Test ARInvoice dataclass."""

    def test_ar_invoice_creation(self):
        """Create AR invoice with required fields."""
        invoice = ARInvoice(
            id="ar-001",
            customer="Customer LLC",
            amount=5000.00,
            due_date=datetime(2026, 6, 15),
            line_items=[{"description": "Services", "amount": 5000.00}]
        )

        assert invoice.id == "ar-001"
        assert invoice.customer == "Customer LLC"
        assert invoice.amount == 5000.00
        assert invoice.status == InvoiceStatus.DRAFT

    def test_ar_invoice_with_reminders(self):
        """Create AR invoice with reminder tracking."""
        invoice = ARInvoice(
            id="ar-002",
            customer="Slow Payer",
            amount=2500.00,
            due_date=datetime(2026, 5, 1),
            line_items=[],
            reminders_sent=2,
            last_reminder_date=datetime(2026, 5, 10)
        )

        assert invoice.reminders_sent == 2
        assert invoice.last_reminder_date is not None


# ==============================================================================
# Accounts Payable Tests
# ==============================================================================

class TestAccountsPayable:
    """Test Accounts Payable operations."""

    @pytest.fixture
    def engine(self):
        """Create APAREngine instance."""
        return APAREngine()

    def test_intake_invoice_stores_invoice(self, engine):
        """Intake invoice stores it in the engine."""
        data = {
            "vendor": "Acme Corp",
            "amount": 1500.00,
            "due_date": "2026-06-01",
            "line_items": [{"description": "Consulting", "amount": 1500.00}]
        }

        invoice = engine.intake_invoice("email", data)

        assert invoice.id in engine._ap_invoices
        assert invoice.vendor == "Acme Corp"
        assert invoice.amount == 1500.00

    def test_intake_invoice_auto_approve_under_threshold(self, engine):
        """Invoice under auto-approve threshold is auto-approved."""
        data = {
            "vendor": "Vendor Inc",
            "amount": 250.00,  # Under AUTO_APPROVE_THRESHOLD (500)
            "due_date": "2026-06-01",
            "line_items": []
        }

        invoice = engine.intake_invoice("email", data)

        assert invoice.status == InvoiceStatus.APPROVED
        assert invoice.approved_by == "auto"

    def test_intake_invoice_requires_approval_above_threshold(self, engine):
        """Invoice above threshold requires approval."""
        data = {
            "vendor": "Big Vendor",
            "amount": 1000.00,  # Above AUTO_APPROVE_THRESHOLD
            "due_date": "2026-06-01",
            "line_items": []
        }

        invoice = engine.intake_invoice("email", data)

        assert invoice.status == InvoiceStatus.PENDING_APPROVAL

    def test_approve_invoice(self, engine):
        """Approve invoice changes status to APPROVED."""
        data = {
            "vendor": "Test Vendor",
            "amount": 1000.00,
            "due_date": "2026-06-01",
            "line_items": []
        }

        invoice = engine.intake_invoice("email", data)
        approved = engine.approve_invoice(invoice.id, "john.doe")

        assert approved.status == InvoiceStatus.APPROVED
        assert approved.approved_by == "john.doe"

    def test_approve_nonexistent_invoice_raises_error(self, engine):
        """Approving non-existent invoice raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            engine.approve_invoice("nonexistent", "john.doe")

    def test_get_pending_approvals(self, engine):
        """Get list of invoices pending approval."""
        # Add two invoices
        engine.intake_invoice("email", {
            "vendor": "Vendor 1",
            "amount": 1000.00,
            "due_date": "2026-06-01",
            "line_items": []
        })

        engine.intake_invoice("email", {
            "vendor": "Vendor 2",
            "amount": 500.00,  # Auto-approved
            "due_date": "2026-06-01",
            "line_items": []
        })

        pending = engine.get_pending_approvals()

        assert len(pending) == 1
        assert pending[0].vendor == "Vendor 1"

    def test_get_upcoming_payments(self, engine):
        """Get approved invoices due soon."""
        # Add approved invoice due in 3 days
        invoice = APInvoice(
            id="ap-001",
            vendor="Vendor",
            amount=100.00,
            due_date=datetime.now() + timedelta(days=3),
            line_items=[],
            status=InvoiceStatus.APPROVED
        )
        engine._ap_invoices["ap-001"] = invoice

        # Add approved invoice due in 10 days
        invoice2 = APInvoice(
            id="ap-002",
            vendor="Vendor",
            amount=200.00,
            due_date=datetime.now() + timedelta(days=10),
            line_items=[],
            status=InvoiceStatus.APPROVED
        )
        engine._ap_invoices["ap-002"] = invoice2

        upcoming = engine.get_upcoming_payments(days=7)

        assert len(upcoming) == 1
        assert upcoming[0].id == "ap-001"


# ==============================================================================
# Accounts Receivable Tests
# ==============================================================================

class TestAccountsReceivable:
    """Test Accounts Receivable operations."""

    @pytest.fixture
    def engine(self):
        """Create APAREngine instance."""
        return APAREngine()

    def test_generate_invoice_stores_invoice(self, engine):
        """Generate AR invoice stores it in the engine."""
        data = {
            "customer": "Customer LLC",
            "amount": 5000.00,
            "due_date": "2026-06-15",
            "line_items": [{"description": "Services", "amount": 5000.00}]
        }

        invoice = engine.generate_invoice("contract", data)

        assert invoice.id in engine._ar_invoices
        assert invoice.customer == "Customer LLC"
        assert invoice.status == InvoiceStatus.DRAFT

    def test_send_reminder_increments_counter(self, engine):
        """Sending reminder increments reminder counter."""
        invoice = ARInvoice(
            id="ar-001",
            customer="Slow Payer",
            amount=2500.00,
            due_date=datetime.now() - timedelta(days=15),
            line_items=[],
            status=InvoiceStatus.SENT
        )

        engine._ar_invoices["ar-001"] = invoice
        engine.send_reminder("ar-001", tone=ReminderTone.FRIENDLY)

        assert engine._ar_invoices["ar-001"].reminders_sent == 1
        assert engine._ar_invoices["ar-001"].last_reminder_date is not None

    def test_mark_invoice_paid(self, engine):
        """Mark invoice as paid."""
        invoice = ARInvoice(
            id="ar-001",
            customer="Customer",
            amount=1000.00,
            due_date=datetime.now(),
            line_items=[],
            status=InvoiceStatus.SENT
        )

        engine._ar_invoices["ar-001"] = invoice
        engine.mark_invoice_paid("ar-001")

        assert engine._ar_invoices["ar-001"].status == InvoiceStatus.PAID

    def test_get_overdue_invoices(self, engine):
        """Get list of overdue invoices."""
        # Overdue invoice
        invoice1 = ARInvoice(
            id="ar-001",
            customer="Overdue Customer",
            amount=1000.00,
            due_date=datetime.now() - timedelta(days=15),
            line_items=[],
            status=InvoiceStatus.SENT
        )

        # Not overdue
        invoice2 = ARInvoice(
            id="ar-002",
            customer="Good Customer",
            amount=2000.00,
            due_date=datetime.now() + timedelta(days=15),
            line_items=[],
            status=InvoiceStatus.SENT
        )

        engine._ar_invoices["ar-001"] = invoice1
        engine._ar_invoices["ar-002"] = invoice2

        overdue = engine.get_overdue_invoices()

        assert len(overdue) == 1
        assert overdue[0].id == "ar-001"


# ==============================================================================
# Reminder System Tests
# ==============================================================================

class TestReminderSystem:
    """Test reminder system functionality."""

    @pytest.fixture
    def engine(self):
        """Create APAREngine instance."""
        return APAREngine()

    def test_generate_reminder_friendly_tone(self, engine):
        """Generate friendly reminder."""
        invoice = ARInvoice(
            id="ar-001",
            customer="Customer",
            amount=1000.00,
            due_date=datetime.now(),
            line_items=[]
        )

        engine._ar_invoices["ar-001"] = invoice
        reminder = engine.generate_reminder("ar-001", tone=ReminderTone.FRIENDLY)

        assert "friendly" in reminder.lower() or "hi" in reminder.lower()

    def test_send_multiple_reminders_increments_counter(self, engine):
        """Multiple reminders increment counter each time."""
        invoice = ARInvoice(
            id="ar-001",
            customer="Slow Payer",
            amount=1000.00,
            due_date=datetime.now() - timedelta(days=30),
            line_items=[],
            status=InvoiceStatus.SENT
        )

        engine._ar_invoices["ar-001"] = invoice

        # Send 3 reminders
        engine.send_reminder("ar-001", tone=ReminderTone.FRIENDLY)
        engine.send_reminder("ar-001", tone=ReminderTone.FIRM)
        engine.send_reminder("ar-001", tone=ReminderTone.FINAL)

        assert engine._ar_invoices["ar-001"].reminders_sent == 3


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestAPAREngineIntegration:
    """Integration tests for complete AP/AR workflows."""

    @pytest.fixture
    def engine(self):
        """Create APAREngine instance."""
        return APAREngine()

    def test_complete_ap_workflow(self, engine):
        """Test complete AP workflow: intake -> approve -> payment."""
        # Step 1: Intake invoice
        invoice = engine.intake_invoice("email", {
            "vendor": "Vendor Inc",
            "amount": 750.00,
            "due_date": "2026-06-01",
            "line_items": []
        })

        assert invoice.status == InvoiceStatus.PENDING_APPROVAL

        # Step 2: Approve invoice
        approved = engine.approve_invoice(invoice.id, "finance_manager")
        assert approved.status == InvoiceStatus.APPROVED

        # Step 3: Get upcoming payments
        upcoming = engine.get_upcoming_payments(days=30)
        assert invoice.id in [inv.id for inv in upcoming]

    def test_complete_ar_workflow(self, engine):
        """Test complete AR workflow: generate -> send -> remind -> paid."""
        # Step 1: Generate invoice
        invoice = engine.generate_invoice("contract", {
            "customer": "Customer LLC",
            "amount": 5000.00,
            "due_date": "2026-06-15",
            "line_items": []
        })

        assert invoice.status == InvoiceStatus.DRAFT

        # Step 2: Send invoice (would update status to SENT in real system)
        invoice.status = InvoiceStatus.SENT
        engine._ar_invoices[invoice.id] = invoice

        # Step 3: Send reminder
        engine.send_reminder(invoice.id, tone=ReminderTone.FRIENDLY)
        assert engine._ar_invoices[invoice.id].reminders_sent == 1

        # Step 4: Mark as paid
        engine.mark_invoice_paid(invoice.id)
        assert engine._ar_invoices[invoice.id].status == InvoiceStatus.PAID
