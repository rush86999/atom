"""
Comprehensive test coverage for APAR Engine (Accounts Payable/Receivable)
Target: 60%+ line coverage (177 lines)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from core.apar_engine import (
    APAREngine,
    APInvoice,
    ARInvoice,
    InvoiceStatus,
    ReminderTone,
)


# ==================== FIXTURES ====================

@pytest.fixture
def apar_engine():
    """Fresh APAR engine instance for each test."""
    return APAREngine()


@pytest.fixture
def sample_ap_data():
    """Sample AP invoice data."""
    return {
        "vendor": "Acme Corp",
        "amount": 250.00,
        "due_date": "2026-04-15",
        "line_items": [
            {"description": "Office Supplies", "amount": 150.00},
            {"description": "Consulting", "amount": 100.00},
        ],
        "payment_terms": "Net 30"
    }


@pytest.fixture
def sample_ar_data():
    """Sample AR invoice data."""
    return {
        "customer": "Global Tech Inc",
        "amount": 5000.00,
        "due_date": "2026-04-30",
        "line_items": [
            {"description": "Software Development", "amount": 4000.00},
            {"description": "Support", "amount": 1000.00},
        ]
    }


# ==================== TestAPAREngine: AP Invoice Lifecycle ====================

class TestAPAREngine:
    """Test APAR engine initialization and core operations."""

    def test_apar_engine_initialization(self, apar_engine):
        """Test engine initializes with empty invoice storage."""
        assert len(apar_engine._ap_invoices) == 0
        assert len(apar_engine._ar_invoices) == 0
        assert len(apar_engine._approval_rules) == 0
        assert apar_engine.AUTO_APPROVE_THRESHOLD == 500.0  # Class attribute

    def test_intake_invoice_from_email(self, apar_engine, sample_ap_data):
        """Test invoice intake from email source."""
        invoice = apar_engine.intake_invoice("email", sample_ap_data)

        assert invoice.id.startswith("ap_")
        assert invoice.vendor == "Acme Corp"
        assert invoice.amount == 250.00
        assert invoice.extracted_from == "email"
        assert invoice.payment_terms == "Net 30"
        assert invoice.status == InvoiceStatus.APPROVED  # Auto-approved under $500

    def test_intake_invoice_from_pdf(self, apar_engine, sample_ap_data):
        """Test invoice intake from PDF source."""
        sample_ap_data["amount"] = 750.00  # Over threshold
        invoice = apar_engine.intake_invoice("pdf", sample_ap_data)

        assert invoice.extracted_from == "pdf"
        assert invoice.status == InvoiceStatus.PENDING_APPROVAL  # Requires approval
        assert invoice.approved_by is None

    def test_intake_invoice_with_default_due_date(self, apar_engine):
        """Test invoice intake defaults due date to 30 days out."""
        data = {"vendor": "Test Vendor", "amount": 100.00}
        invoice = apar_engine.intake_invoice("portal", data)

        expected_due = datetime.now() + timedelta(days=30)
        assert abs((invoice.due_date - expected_due).total_seconds()) < 5  # Within 5 seconds

    def test_intake_invoice_default_vendor(self, apar_engine):
        """Test invoice intake uses default vendor name."""
        data = {"amount": 50.00}
        invoice = apar_engine.intake_invoice("email", data)

        assert invoice.vendor == "Unknown Vendor"
        assert invoice.line_items == []

    def test_auto_approve_threshold(self, apar_engine):
        """Test invoices under threshold auto-approve."""
        small_invoice_data = {"vendor": "Vendor A", "amount": 499.99}
        invoice = apar_engine.intake_invoice("email", small_invoice_data)

        assert invoice.status == InvoiceStatus.APPROVED
        assert invoice.approved_by == "auto"

    def test_pending_approval_over_threshold(self, apar_engine):
        """Test invoices over threshold require approval."""
        large_invoice_data = {"vendor": "Vendor B", "amount": 500.01}
        invoice = apar_engine.intake_invoice("email", large_invoice_data)

        assert invoice.status == InvoiceStatus.PENDING_APPROVAL
        assert invoice.approved_by is None

    def test_approve_invoice_successfully(self, apar_engine, sample_ap_data):
        """Test approving a pending invoice."""
        sample_ap_data["amount"] = 1000.00
        invoice = apar_engine.intake_invoice("email", sample_ap_data)

        approved_invoice = apar_engine.approve_invoice(invoice.id, "john.doe")

        assert approved_invoice.status == InvoiceStatus.APPROVED
        assert approved_invoice.approved_by == "john.doe"

    def test_approve_nonexistent_invoice(self, apar_engine):
        """Test approving invoice that doesn't exist raises error."""
        with pytest.raises(ValueError, match="Invoice .* not found"):
            apar_engine.approve_invoice("invalid_id", "user")


# ==================== TestAPARProcessing: Invoice Processing ====================

class TestAPARProcessing:
    """Test AP invoice processing and AR invoice generation."""

    def test_get_pending_approvals_empty(self, apar_engine):
        """Test getting pending approvals when none exist."""
        pending = apar_engine.get_pending_approvals()
        assert pending == []

    def test_get_pending_approvals_multiple(self, apar_engine):
        """Test getting multiple pending approvals."""
        # Create 3 invoices over threshold
        for i in range(3):
            data = {"vendor": f"Vendor {i}", "amount": 1000.00}
            apar_engine.intake_invoice("email", data)

        pending = apar_engine.get_pending_approvals()
        assert len(pending) == 3
        assert all(inv.status == InvoiceStatus.PENDING_APPROVAL for inv in pending)

    def test_get_upcoming_payments_next_7_days(self, apar_engine):
        """Test getting approved invoices due within 7 days."""
        # Create approved invoice due in 3 days
        data = {
            "vendor": "Vendor A",
            "amount": 100.00,
            "due_date": (datetime.now() + timedelta(days=3)).isoformat()
        }
        invoice = apar_engine.intake_invoice("email", data)
        invoice.status = InvoiceStatus.APPROVED

        upcoming = apar_engine.get_upcoming_payments(days=7)
        assert len(upcoming) == 1
        assert upcoming[0].id == invoice.id

    def test_get_upcoming_payments_excludes_future(self, apar_engine):
        """Test upcoming payments excludes invoices beyond cutoff."""
        # Create invoice due in 10 days
        data = {
            "vendor": "Vendor B",
            "amount": 100.00,
            "due_date": (datetime.now() + timedelta(days=10)).isoformat()
        }
        invoice = apar_engine.intake_invoice("email", data)
        invoice.status = InvoiceStatus.APPROVED

        upcoming = apar_engine.get_upcoming_payments(days=7)
        assert len(upcoming) == 0

    def test_generate_ar_invoice_from_contract(self, apar_engine, sample_ar_data):
        """Test generating AR invoice from contract source."""
        invoice = apar_engine.generate_invoice("contract", sample_ar_data)

        assert invoice.id.startswith("ar_")
        assert invoice.customer == "Global Tech Inc"
        assert invoice.amount == 5000.00
        assert invoice.source == "contract"
        assert invoice.status == InvoiceStatus.DRAFT

    def test_send_invoice_transitions_to_sent(self, apar_engine, sample_ar_data):
        """Test sending invoice transitions status to SENT."""
        invoice = apar_engine.generate_invoice("crm_deal", sample_ar_data)
        sent_invoice = apar_engine.send_invoice(invoice.id)

        assert sent_invoice.status == InvoiceStatus.SENT

    def test_send_nonexistent_invoice(self, apar_engine):
        """Test sending invoice that doesn't exist raises error."""
        with pytest.raises(ValueError, match="Invoice .* not found"):
            apar_engine.send_invoice("invalid_id")

    def test_mark_paid_transitions_to_paid(self, apar_engine, sample_ar_data):
        """Test marking invoice as paid."""
        invoice = apar_engine.generate_invoice("contract", sample_ar_data)
        paid_invoice = apar_engine.mark_paid(invoice.id)

        assert paid_invoice.status == InvoiceStatus.PAID

    def test_mark_paid_nonexistent_invoice(self, apar_engine):
        """Test marking paid for nonexistent invoice raises error."""
        with pytest.raises(ValueError, match="Invoice .* not found"):
            apar_engine.mark_paid("invalid_id")

    def test_get_overdue_invoices(self, apar_engine, sample_ar_data):
        """Test getting overdue AR invoices."""
        # Create past-due invoice
        data = {
            "customer": "Customer A",
            "amount": 1000.00,
            "due_date": (datetime.now() - timedelta(days=10)).isoformat()
        }
        invoice = apar_engine.generate_invoice("contract", data)
        invoice.status = InvoiceStatus.SENT

        overdue = apar_engine.get_overdue_invoices()
        assert len(overdue) == 1
        assert overdue[0].status == InvoiceStatus.OVERDUE


# ==================== TestAPARRouting: Collections & Reminders ====================

class TestAPARRouting:
    """Test intelligent collections and reminder generation."""

    def test_generate_reminder_friendly_tone(self, apar_engine, sample_ar_data):
        """Test first reminder uses friendly tone."""
        invoice = apar_engine.generate_invoice("contract", sample_ar_data)
        invoice.status = InvoiceStatus.SENT

        reminder = apar_engine.generate_reminder(invoice.id)

        assert reminder["tone"] == ReminderTone.FRIENDLY.value
        assert "Friendly Reminder" in reminder["subject"]
        assert reminder["reminders_sent"] == 1

    def test_generate_reminder_firm_tone(self, apar_engine, sample_ar_data):
        """Test second reminder uses firm tone."""
        invoice = apar_engine.generate_invoice("contract", sample_ar_data)
        invoice.reminders_sent = 1

        reminder = apar_engine.generate_reminder(invoice.id)

        assert reminder["tone"] == ReminderTone.FIRM.value
        assert "Second Notice" in reminder["subject"]
        assert reminder["reminders_sent"] == 2

    def test_generate_reminder_final_tone(self, apar_engine, sample_ar_data):
        """Test third reminder uses final tone."""
        invoice = apar_engine.generate_invoice("contract", sample_ar_data)
        invoice.reminders_sent = 2

        reminder = apar_engine.generate_reminder(invoice.id)

        assert reminder["tone"] == ReminderTone.FINAL.value
        assert "Final Notice" in reminder["subject"]  # Title case
        assert reminder["reminders_sent"] == 3

    def test_get_collection_summary(self, apar_engine):
        """Test getting collection summary."""
        # Create mixed invoice statuses
        sent_data = {
            "customer": "Customer A",
            "amount": 1000.00,
            "due_date": "2026-04-01"
        }
        sent_inv = apar_engine.generate_invoice("contract", sent_data)
        sent_inv.status = InvoiceStatus.SENT

        paid_data = {
            "customer": "Customer B",
            "amount": 2000.00,
            "due_date": "2026-03-01"
        }
        paid_inv = apar_engine.generate_invoice("contract", paid_data)
        paid_inv.status = InvoiceStatus.PAID

        summary = apar_engine.get_collection_summary()

        assert summary["total_outstanding"] == 1000.00
        assert summary["invoices_sent"] == 1
        assert summary["invoices_paid"] == 1
        assert summary["overdue_count"] == 0

    def test_get_all_invoices_mixed(self, apar_engine):
        """Test getting all invoices combines AP and AR."""
        # Create AP invoice
        ap_data = {"vendor": "Vendor A", "amount": 100.00}
        ap_inv = apar_engine.intake_invoice("email", ap_data)

        # Create AR invoice
        ar_data = {"customer": "Customer A", "amount": 500.00}
        ar_inv = apar_engine.generate_invoice("contract", ar_data)

        all_invoices = apar_engine.get_all_invoices()

        assert len(all_invoices) == 2
        # Should be sorted by creation date descending
        assert all_invoices[0].id == ar_inv.id  # Created later


# ==================== TestAPARErrors: Error Handling ====================

class TestAPARErrors:
    """Test error handling and edge cases."""

    def test_generate_invoice_content_for_ap(self, apar_engine, sample_ap_data):
        """Test generating text content for AP invoice."""
        invoice = apar_engine.intake_invoice("email", sample_ap_data)
        content = apar_engine.generate_invoice_content(invoice.id)

        assert "AP" in content
        assert "Acme Corp" in content
        assert "$250.00" in content
        assert "Office Supplies" in content

    def test_generate_invoice_content_for_ar(self, apar_engine, sample_ar_data):
        """Test generating text content for AR invoice."""
        invoice = apar_engine.generate_invoice("contract", sample_ar_data)
        content = apar_engine.generate_invoice_content(invoice.id)

        assert "AR" in content
        assert "Global Tech Inc" in content
        assert "$5000.00" in content  # No comma separator

    def test_generate_invoice_content_not_found(self, apar_engine):
        """Test generating content for nonexistent invoice raises error."""
        with pytest.raises(ValueError, match="Invoice .* not found"):
            apar_engine.generate_invoice_content("invalid_id")

    def test_generate_pdf_without_reportlab(self, apar_engine, sample_ar_data):
        """Test PDF generation fails without ReportLab."""
        invoice = apar_engine.generate_invoice("contract", sample_ar_data)

        with patch("core.apar_engine.HAS_REPORTLAB", False):
            with pytest.raises(ImportError, match="ReportLab is not installed"):
                apar_engine.generate_invoice_pdf(invoice.id)

    def test_generate_pdf_reportlab_import_error(self, apar_engine):
        """Test PDF generation with ReportLab import error."""
        data = {"customer": "Test", "amount": 100.00}
        invoice = apar_engine.generate_invoice("contract", data)

        # Mock ReportLab import failure
        with patch("core.apar_engine.HAS_REPORTLAB", False):
            with pytest.raises(ImportError):
                apar_engine.generate_invoice_pdf(invoice.id)

    def test_reminder_for_nonexistent_invoice(self, apar_engine):
        """Test generating reminder for nonexistent invoice raises error."""
        with pytest.raises(ValueError, match="Invoice .* not found"):
            apar_engine.generate_reminder("invalid_id")

    def test_intake_with_zero_amount(self, apar_engine):
        """Test invoice intake with zero amount."""
        data = {"vendor": "Test", "amount": 0.00}
        invoice = apar_engine.intake_invoice("email", data)

        assert invoice.amount == 0.00
        assert invoice.status == InvoiceStatus.APPROVED  # Under threshold

    def test_intake_with_negative_amount(self, apar_engine):
        """Test invoice intake with negative amount."""
        data = {"vendor": "Test", "amount": -100.00}
        invoice = apar_engine.intake_invoice("email", data)

        assert invoice.amount == -100.00
        assert invoice.status == InvoiceStatus.APPROVED  # Under threshold
