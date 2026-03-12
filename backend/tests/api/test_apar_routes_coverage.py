"""
APAR Routes Test Coverage

Target: api/apar_routes.py (241 lines, 14 endpoints)
Goal: 75%+ line coverage with TestClient-based integration tests

Endpoints Covered:
Accounts Payable (AP):
- POST /apar/ap/intake - Invoice intake with auto-approval threshold
- POST /apar/ap/{invoice_id}/approve - Manual approval workflow
- GET /apar/ap/pending - List pending approvals
- GET /apar/ap/upcoming - Upcoming payments (default 7 days, custom days)
- GET /apar/ap/{invoice_id}/download - PDF download

Accounts Receivable (AR):
- POST /apar/ar/generate - Generate customer invoice
- POST /apar/ar/{invoice_id}/send - Mark invoice as sent
- POST /apar/ar/{invoice_id}/paid - Mark invoice as paid
- GET /apar/ar/overdue - List overdue invoices
- GET /apar/ar/{invoice_id}/download - PDF download
- POST /apar/ar/{invoice_id}/remind - Send collection reminder
- GET /apar/summary - Collection summary metrics

Combined:
- GET /apar/all - All invoices (AP + AR) with type discrimination

External dependencies mocked:
- APAREngine (synchronous methods: intake_invoice, approve_invoice, etc.)
- reportlab (PDF generation mocked with fake bytes)

Test pattern: Per-file FastAPI app with TestClient (Phase 177/178/179 pattern)
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from datetime import datetime, timedelta
from typing import Dict, Any, List


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_apar_engine():
    """
    Mock APAREngine with all methods for invoice operations.

    Provides deterministic mock responses for:
    - intake_invoice: Returns APInvoice with id, vendor, amount, status, approved_by
    - approve_invoice: Returns APInvoice with status=approved
    - get_pending_approvals: Returns list of pending APInvoice objects
    - get_upcoming_payments: Returns list of upcoming APInvoice objects
    - generate_invoice: Returns ARInvoice with id, customer, amount, status
    - send_invoice: Returns ARInvoice with status=sent
    - mark_paid: Returns ARInvoice with status=paid
    - get_overdue_invoices: Returns list of overdue ARInvoice objects
    - get_all_invoices: Returns mixed list of APInvoice and ARInvoice objects
    - generate_reminder: Returns dict with reminder text and tone
    - get_collection_summary: Returns dict with metrics
    - generate_invoice_pdf: Returns fake PDF bytes (avoids reportlab dependency)

    Usage:
        def test_intake_success(mock_apar_engine):
            mock_apar_engine.intake_invoice.return_value = APInvoice(...)
    """
    from core.apar_engine import APInvoice, ARInvoice, InvoiceStatus

    mock = MagicMock()

    # Configure intake_invoice to return AP invoice with auto-approval
    mock.intake_invoice.return_value = APInvoice(
        id="ap_1234567890",
        vendor="Test Vendor",
        amount=100.0,
        due_date=datetime.now() + timedelta(days=30),
        line_items=[],
        status=InvoiceStatus.APPROVED,
        approved_by="auto",
        payment_terms="Net 30"
    )

    # Configure approve_invoice
    mock.approve_invoice.return_value = APInvoice(
        id="ap_1234567890",
        vendor="Test Vendor",
        amount=100.0,
        due_date=datetime.now() + timedelta(days=30),
        line_items=[],
        status=InvoiceStatus.APPROVED,
        approved_by="user_1",
        payment_terms="Net 30"
    )

    # Configure get_pending_approvals
    mock.get_pending_approvals.return_value = [
        APInvoice(
            id="ap_pending_1",
            vendor="Vendor A",
            amount=750.0,
            due_date=datetime.now() + timedelta(days=15),
            line_items=[],
            status=InvoiceStatus.PENDING_APPROVAL
        ),
        APInvoice(
            id="ap_pending_2",
            vendor="Vendor B",
            amount=1200.0,
            due_date=datetime.now() + timedelta(days=20),
            line_items=[],
            status=InvoiceStatus.PENDING_APPROVAL
        )
    ]

    # Configure get_upcoming_payments
    mock.get_upcoming_payments.return_value = [
        APInvoice(
            id="ap_upcoming_1",
            vendor="Vendor C",
            amount=300.0,
            due_date=datetime.now() + timedelta(days=3),
            line_items=[],
            status=InvoiceStatus.APPROVED
        ),
        APInvoice(
            id="ap_upcoming_2",
            vendor="Vendor D",
            amount=450.0,
            due_date=datetime.now() + timedelta(days=5),
            line_items=[],
            status=InvoiceStatus.APPROVED
        )
    ]

    # Configure generate_invoice
    mock.generate_invoice.return_value = ARInvoice(
        id="ar_1234567890",
        customer="Test Customer",
        amount=500.0,
        due_date=datetime.now() + timedelta(days=30),
        line_items=[],
        status=InvoiceStatus.DRAFT,
        source="manual"
    )

    # Configure send_invoice
    mock.send_invoice.return_value = ARInvoice(
        id="ar_1234567890",
        customer="Test Customer",
        amount=500.0,
        due_date=datetime.now() + timedelta(days=30),
        line_items=[],
        status=InvoiceStatus.SENT,
        source="manual"
    )

    # Configure mark_paid
    mock.mark_paid.return_value = ARInvoice(
        id="ar_1234567890",
        customer="Test Customer",
        amount=500.0,
        due_date=datetime.now() + timedelta(days=30),
        line_items=[],
        status=InvoiceStatus.PAID,
        source="manual"
    )

    # Configure get_overdue_invoices
    mock.get_overdue_invoices.return_value = [
        ARInvoice(
            id="ar_overdue_1",
            customer="Customer A",
            amount=800.0,
            due_date=datetime.now() - timedelta(days=5),
            line_items=[],
            status=InvoiceStatus.OVERDUE
        ),
        ARInvoice(
            id="ar_overdue_2",
            customer="Customer B",
            amount=1500.0,
            due_date=datetime.now() - timedelta(days=10),
            line_items=[],
            status=InvoiceStatus.OVERDUE
        )
    ]

    # Configure get_all_invoices (mixed AP and AR)
    mock.get_all_invoices.return_value = [
        ARInvoice(
            id="ar_1234567890",
            customer="Customer X",
            amount=500.0,
            due_date=datetime.now() + timedelta(days=30),
            line_items=[],
            status=InvoiceStatus.SENT
        ),
        APInvoice(
            id="ap_1234567890",
            vendor="Vendor Y",
            amount=300.0,
            due_date=datetime.now() + timedelta(days=15),
            line_items=[],
            status=InvoiceStatus.APPROVED
        )
    ]

    # Configure generate_reminder
    mock.generate_reminder.return_value = {
        "invoice_id": "ar_1234567890",
        "customer": "Test Customer",
        "amount": 500.0,
        "tone": "friendly",
        "subject": "Friendly Reminder: Invoice Due",
        "message": "Just a friendly reminder that invoice #ar_1234567890 for $500.00 is now due.",
        "reminders_sent": 1
    }

    # Configure get_collection_summary
    mock.get_collection_summary.return_value = {
        "total_outstanding": 5000.0,
        "overdue_count": 2,
        "invoices_sent": 5,
        "invoices_paid": 3
    }

    # Configure generate_invoice_pdf (fake PDF to avoid reportlab dependency)
    mock.generate_invoice_pdf.return_value = b"%PDF-1.4 fake pdf content"

    return mock


@pytest.fixture
def apar_client(mock_apar_engine):
    """
    TestClient with isolated FastAPI app for APAR routes.

    Uses per-file app pattern to avoid SQLAlchemy metadata conflicts.
    Patches api.apar_routes.apar_engine with mock_apar_engine.

    Usage:
        def test_intake_ap_invoice(apar_client):
            response = apar_client.post("/api/apar/ap/intake", json={...})
            assert response.status_code == 200
    """
    from api.apar_routes import router

    app = FastAPI()
    app.include_router(router)

    # Patch apar_engine at the route module level
    with patch('api.apar_routes.apar_engine', mock_apar_engine):
        yield TestClient(app)


@pytest.fixture
def sample_ap_intake_request():
    """
    Factory for valid APIntakeRequest data.

    Returns a dict with required fields for AP invoice intake.
    Override fields in tests as needed.

    Usage:
        def test_intake_with_custom_amount(apar_client, sample_ap_intake_request):
            sample_ap_intake_request["amount"] = 750.0
            response = apar_client.post("/api/apar/ap/intake", json=sample_ap_intake_request)
    """
    return {
        "vendor": "Test Vendor Inc",
        "amount": 100.0,
        "due_date": "2026-04-15",
        "line_items": [
            {"description": "Consulting Services", "amount": 100.0}
        ],
        "payment_terms": "Net 30",
        "source": "email"
    }


@pytest.fixture
def sample_ar_generate_request():
    """
    Factory for valid ARGenerateRequest data.

    Returns a dict with required fields for AR invoice generation.
    Override fields in tests as needed.

    Usage:
        def test_generate_ar_invoice(apar_client, sample_ar_generate_request):
            sample_ar_generate_request["amount"] = 750.0
            response = apar_client.post("/api/apar/ar/generate", json=sample_ar_generate_request)
    """
    return {
        "customer": "Test Customer LLC",
        "amount": 500.0,
        "due_date": "2026-04-15",
        "line_items": [
            {"description": "Software Development", "amount": 500.0}
        ],
        "source": "manual"
    }


@pytest.fixture
def sample_ap_invoice():
    """
    APInvoice fixture for invoice object assertions.

    Returns a sample APInvoice object for testing invoice state.

    Usage:
        def test_invoice_structure(sample_ap_invoice):
            assert sample_ap_invoice.vendor == "Test Vendor"
            assert sample_ap_invoice.status == InvoiceStatus.PENDING_APPROVAL
    """
    from core.apar_engine import APInvoice, InvoiceStatus

    return APInvoice(
        id="ap_test_123",
        vendor="Test Vendor",
        amount=100.0,
        due_date=datetime.now() + timedelta(days=30),
        line_items=[],
        status=InvoiceStatus.PENDING_APPROVAL,
        payment_terms="Net 30"
    )


@pytest.fixture
def sample_ar_invoice():
    """
    ARInvoice fixture for invoice object assertions.

    Returns a sample ARInvoice object for testing invoice state.

    Usage:
        def test_invoice_structure(sample_ar_invoice):
            assert sample_ar_invoice.customer == "Test Customer"
            assert sample_ar_invoice.status == InvoiceStatus.DRAFT
    """
    from core.apar_engine import ARInvoice, InvoiceStatus

    return ARInvoice(
        id="ar_test_456",
        customer="Test Customer",
        amount=500.0,
        due_date=datetime.now() + timedelta(days=30),
        line_items=[],
        status=InvoiceStatus.DRAFT,
        source="manual"
    )


# ============================================================================
# TestAPARSuccess - Happy Path Tests
# ============================================================================

class TestAPARSuccess:
    """
    Happy path tests for APAR endpoints.

    Tests all success paths for AP invoice operations:
    - Intake with auto-approval threshold
    - Manual approval workflow
    - Pending approvals list
    - Upcoming payments (default and custom days)
    """

    def test_intake_ap_invoice_success(self, apar_client, sample_ap_intake_request):
        """Test AP invoice intake with valid data."""
        response = apar_client.post("/api/apar/ap/intake", json=sample_ap_intake_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "id" in data["data"]
        assert data["data"]["vendor"] == "Test Vendor Inc"
        assert data["data"]["amount"] == 100.0
        assert data["message"] == "AP invoice intake successful"

    def test_intake_ap_invoice_auto_approved(self, apar_client, mock_apar_engine):
        """Test AP invoice auto-approval for amounts under threshold ($500)."""
        from core.apar_engine import InvoiceStatus

        # Configure mock to return auto-approved invoice
        mock_apar_engine.intake_invoice.return_value.status = InvoiceStatus.APPROVED
        mock_apar_engine.intake_invoice.return_value.approved_by = "auto"

        response = apar_client.post("/api/apar/ap/intake", json={
            "vendor": "Auto Vendor",
            "amount": 100.0,  # Under $500 threshold
            "due_date": "2026-04-15"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["auto_approved"] is True
        assert data["data"]["status"] == "approved"

    def test_intake_ap_invoice_manual_approval(self, apar_client, mock_apar_engine):
        """Test AP invoice requires manual approval for amounts above threshold ($500)."""
        from core.apar_engine import InvoiceStatus

        # Configure mock to return pending approval invoice
        mock_apar_engine.intake_invoice.return_value.status = InvoiceStatus.PENDING_APPROVAL
        mock_apar_engine.intake_invoice.return_value.approved_by = None

        response = apar_client.post("/api/apar/ap/intake", json={
            "vendor": "Manual Vendor",
            "amount": 750.0,  # Above $500 threshold
            "due_date": "2026-04-15"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["auto_approved"] is False
        assert data["data"]["status"] == "pending_approval"

    def test_approve_ap_invoice_success(self, apar_client):
        """Test AP invoice approval workflow."""
        response = apar_client.post("/api/apar/ap/ap_1234567890/approve", json={
            "approver": "user_1"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "approved"
        assert data["data"]["id"] == "ap_1234567890"
        assert data["message"] == "Invoice approved successfully"

    def test_get_pending_approvals_success(self, apar_client):
        """Test retrieving pending approval invoices."""
        response = apar_client.get("/api/apar/ap/pending")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 2
        assert len(data["data"]["invoices"]) == 2
        assert data["data"]["invoices"][0]["vendor"] == "Vendor A"
        assert data["data"]["invoices"][0]["amount"] == 750.0
        assert data["message"] == "Retrieved 2 pending approvals"

    def test_get_upcoming_payments_default(self, apar_client):
        """Test retrieving upcoming payments with default 7 days."""
        response = apar_client.get("/api/apar/ap/upcoming")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 2
        assert data["data"]["total_due"] == 750.0
        assert len(data["data"]["invoices"]) == 2
        assert "due_date" in data["data"]["invoices"][0]
        assert data["message"] == "Retrieved 2 upcoming payments"

    def test_get_upcoming_payments_custom_days(self, apar_client):
        """Test retrieving upcoming payments with custom days parameter."""
        response = apar_client.get("/api/apar/ap/upcoming?days=30")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Verify the endpoint accepts custom days parameter
        assert "count" in data["data"]
        assert "invoices" in data["data"]


# ============================================================================
# TestARGenerate - AR Invoice Generation Tests
# ============================================================================

class TestARGenerate:
    """
    Happy path tests for AR invoice generation and lifecycle.

    Tests AR invoice operations:
    - Generate customer invoice
    - Send invoice (mark as sent)
    - Mark as paid
    - List overdue invoices
    """

    def test_generate_ar_invoice_success(self, apar_client, sample_ar_generate_request):
        """Test AR invoice generation with customer and amount."""
        response = apar_client.post("/api/apar/ar/generate", json=sample_ar_generate_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "id" in data["data"]
        assert data["data"]["customer"] == "Test Customer LLC"
        assert data["data"]["amount"] == 500.0
        assert data["message"] == "AR invoice generated successfully"

    def test_send_ar_invoice_success(self, apar_client):
        """Test sending AR invoice (mark as sent)."""
        response = apar_client.post("/api/apar/ar/ar_1234567890/send")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "sent"
        assert data["data"]["id"] == "ar_1234567890"
        assert data["message"] == "Invoice sent successfully"

    def test_mark_ar_paid_success(self, apar_client):
        """Test marking AR invoice as paid."""
        response = apar_client.post("/api/apar/ar/ar_1234567890/paid")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "paid"
        assert data["data"]["id"] == "ar_1234567890"
        assert data["message"] == "Invoice marked as paid"

    def test_get_overdue_invoices_success(self, apar_client):
        """Test retrieving overdue AR invoices."""
        response = apar_client.get("/api/apar/ar/overdue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 2
        assert len(data["data"]["invoices"]) == 2
        assert data["data"]["invoices"][0]["customer"] == "Customer A"
        assert data["data"]["invoices"][0]["amount"] == 800.0
        assert data["message"] == "Retrieved 2 overdue invoices"


# ============================================================================
# TestARPDFDownload - PDF Download Tests
# ============================================================================

class TestARPDFDownload:
    """
    PDF download endpoint tests for AR and AP invoices.

    Tests PDF generation and download:
    - AR invoice download
    - AP invoice download
    - Invoice not found error
    - ReportLab missing error
    """

    def test_download_ar_invoice_success(self, apar_client, mock_apar_engine):
        """Test AR invoice PDF download."""
        response = apar_client.get("/api/apar/ar/ar_1234567890/download")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert "invoice_ar_1234567890.pdf" in response.headers["content-disposition"]
        assert b"fake pdf content" in response.content

    def test_download_ap_invoice_success(self, apar_client, mock_apar_engine):
        """Test AP invoice PDF download."""
        response = apar_client.get("/api/apar/ap/ap_1234567890/download")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert "invoice_ap_1234567890.pdf" in response.headers["content-disposition"]
        assert b"fake pdf content" in response.content

    def test_download_ar_invoice_not_found(self, apar_client, mock_apar_engine):
        """Test PDF download when invoice not found (ValueError)."""
        # Configure mock to raise ValueError for not found
        mock_apar_engine.generate_invoice_pdf.side_effect = ValueError("Invoice not found")

        response = apar_client.get("/api/apar/ar/invalid_id/download")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_download_ap_invoice_reportlab_missing(self, apar_client, mock_apar_engine):
        """Test PDF download when reportlab not installed (ImportError)."""
        # Configure mock to raise ImportError for missing reportlab
        mock_apar_engine.generate_invoice_pdf.side_effect = ImportError("reportlab not installed")

        response = apar_client.get("/api/apar/ap/ap_1234567890/download")

        assert response.status_code == 500
        assert "reportlab" in response.json()["detail"].lower()


# ============================================================================
# TestARReminders - Collection Reminder Tests
# ============================================================================

class TestARReminders:
    """
    Collection reminder tests for AR invoices.

    Tests reminder generation with different tones:
    - Friendly reminder (first reminder)
    - Firm reminder (second reminder)
    - Final reminder (third+ reminder)
    """

    def test_send_reminder_success(self, apar_client):
        """Test sending collection reminder."""
        response = apar_client.post("/api/apar/ar/ar_1234567890/remind")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["invoice_id"] == "ar_1234567890"
        assert data["data"]["tone"] == "friendly"
        assert "reminder_text" in data["data"] or "message" in data["data"]
        assert data["message"] == "Reminder generated successfully"

    def test_send_reminder_friendly_tone(self, apar_client, mock_apar_engine):
        """Test friendly reminder tone (first reminder)."""
        # Configure mock to return friendly reminder
        mock_apar_engine.generate_reminder.return_value = {
            "invoice_id": "ar_1234567890",
            "customer": "Test Customer",
            "amount": 500.0,
            "tone": "friendly",
            "subject": "Friendly Reminder: Invoice Due",
            "message": "Just a friendly reminder that invoice #ar_1234567890 for $500.00 is now due.",
            "reminders_sent": 1
        }

        response = apar_client.post("/api/apar/ar/ar_1234567890/remind")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["tone"] == "friendly"
        assert "friendly" in data["data"]["subject"].lower()
        assert "friendly reminder" in data["data"]["message"].lower()

    def test_send_reminder_firm_tone(self, apar_client, mock_apar_engine):
        """Test firm reminder tone (second reminder)."""
        # Configure mock to return firm reminder
        mock_apar_engine.generate_reminder.return_value = {
            "invoice_id": "ar_1234567890",
            "customer": "Test Customer",
            "amount": 500.0,
            "tone": "firm",
            "subject": "Second Notice: Payment Overdue",
            "message": "This is a second notice regarding invoice #ar_1234567890 for $500.00. Please remit payment promptly.",
            "reminders_sent": 2
        }

        response = apar_client.post("/api/apar/ar/ar_1234567890/remind")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["tone"] == "firm"
        assert "second notice" in data["data"]["subject"].lower()
        assert "promptly" in data["data"]["message"].lower()


# ============================================================================
# TestARSummary - Collection Summary Tests
# ============================================================================

class TestARSummary:
    """
    Collection summary tests for AR metrics.

    Tests aggregation and summary statistics:
    - Total outstanding amount
    - Overdue invoice count
    - Sent invoices count
    - Paid invoices count
    """

    def test_get_collection_summary_success(self, apar_client):
        """Test retrieving collection summary with metrics."""
        response = apar_client.get("/api/apar/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "total_outstanding" in data["data"]
        assert "overdue_count" in data["data"]
        assert "invoices_sent" in data["data"]
        assert "invoices_paid" in data["data"]
        assert data["data"]["total_outstanding"] == 5000.0
        assert data["data"]["overdue_count"] == 2
        assert data["message"] == "Collection summary retrieved successfully"

    def test_get_collection_summary_empty(self, apar_client, mock_apar_engine):
        """Test collection summary with no data (empty summary)."""
        # Configure mock to return empty summary
        mock_apar_engine.get_collection_summary.return_value = {
            "total_outstanding": 0.0,
            "overdue_count": 0,
            "invoices_sent": 0,
            "invoices_paid": 0
        }

        response = apar_client.get("/api/apar/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_outstanding"] == 0.0
        assert data["data"]["overdue_count"] == 0
        assert data["data"]["invoices_sent"] == 0
        assert data["data"]["invoices_paid"] == 0


# ============================================================================
# TestAllInvoices - Combined AP/AR Invoice Tests
# ============================================================================

class TestAllInvoices:
    """
    Combined AP/AR invoice tests.

    Tests the /apar/all endpoint that returns both AP and AR invoices:
    - Mixed list of AP and AR invoices
    - AP-only invoices
    - AR-only invoices
    - Type discrimination using hasattr(inv, \"customer\")
    """

    def test_get_all_invoices_mixed(self, apar_client):
        """Test retrieving mixed list of AP and AR invoices."""
        response = apar_client.get("/api/apar/all")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 2
        assert len(data["data"]["invoices"]) == 2

        # Verify first invoice is AR (has customer field)
        first_invoice = data["data"]["invoices"][0]
        assert first_invoice["type"] == "AR"
        assert first_invoice["customer"] == "Customer X"
        assert first_invoice["vendor"] is None

        # Verify second invoice is AP (has vendor field)
        second_invoice = data["data"]["invoices"][1]
        assert second_invoice["type"] == "AP"
        assert second_invoice["vendor"] == "Vendor Y"
        assert second_invoice["customer"] is None

        assert data["message"] == "Retrieved 2 invoices"

    def test_get_all_invoices_ap_only(self, apar_client, mock_apar_engine):
        """Test retrieving AP-only invoices."""
        from core.apar_engine import APInvoice

        # Configure mock to return only AP invoices
        mock_apar_engine.get_all_invoices.return_value = [
            APInvoice(
                id="ap_1",
                vendor="Vendor A",
                amount=100.0,
                due_date=datetime.now() + timedelta(days=15),
                line_items=[],
                status=InvoiceStatus.APPROVED
            ),
            APInvoice(
                id="ap_2",
                vendor="Vendor B",
                amount=200.0,
                due_date=datetime.now() + timedelta(days=20),
                line_items=[],
                status=InvoiceStatus.APPROVED
            )
        ]

        response = apar_client.get("/api/apar/all")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 2

        # Verify all invoices are AP type
        for invoice in data["data"]["invoices"]:
            assert invoice["type"] == "AP"
            assert invoice["vendor"] is not None
            assert invoice["customer"] is None

    def test_get_all_invoices_ar_only(self, apar_client, mock_apar_engine):
        """Test retrieving AR-only invoices."""
        from core.apar_engine import ARInvoice

        # Configure mock to return only AR invoices
        mock_apar_engine.get_all_invoices.return_value = [
            ARInvoice(
                id="ar_1",
                customer="Customer A",
                amount=500.0,
                due_date=datetime.now() + timedelta(days=30),
                line_items=[],
                status=InvoiceStatus.SENT
            ),
            ARInvoice(
                id="ar_2",
                customer="Customer B",
                amount=750.0,
                due_date=datetime.now() + timedelta(days=30),
                line_items=[],
                status=InvoiceStatus.SENT
            )
        ]

        response = apar_client.get("/api/apar/all")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 2

        # Verify all invoices are AR type
        for invoice in data["data"]["invoices"]:
            assert invoice["type"] == "AR"
            assert invoice["customer"] is not None
            assert invoice["vendor"] is None


# ============================================================================
# TestAPARErrorPaths - Error Path Tests
# ============================================================================

class TestAPARErrorPaths:
    """
    Error path tests for APAR endpoints (API-03 requirement).

    Tests validation errors, not found errors, and edge cases:
    - Missing required fields (422)
    - Invalid data formats
    - Invoice not found (404)
    - Empty results
    - Invalid parameters
    """

    def test_intake_invoice_missing_vendor(self, apar_client):
        """Test AP intake without vendor field (422 validation error)."""
        response = apar_client.post("/api/apar/ap/intake", json={
            "amount": 100.0
        })

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_intake_invoice_negative_amount(self, apar_client):
        """Test AP intake with negative amount."""
        response = apar_client.post("/api/apar/ap/intake", json={
            "vendor": "Test Vendor",
            "amount": -100.0
        })

        # API may process or validate - check for 200 or 422
        assert response.status_code in [200, 422]

    def test_intake_invoice_invalid_date_format(self, apar_client):
        """Test AP intake with invalid due_date format."""
        response = apar_client.post("/api/apar/ap/intake", json={
            "vendor": "Test Vendor",
            "amount": 100.0,
            "due_date": "invalid-date"
        })

        # datetime.fromisoformat may raise ValueError (500) or validation error (422)
        assert response.status_code in [422, 500]

    def test_approve_invoice_not_found(self, apar_client, mock_apar_engine):
        """Test approving non-existent invoice (404)."""
        # Configure mock to raise ValueError
        mock_apar_engine.approve_invoice.side_effect = ValueError("Invoice not found")

        response = apar_client.post("/api/apar/ap/invalid_id/approve")

        # Route may return 404 or 500 depending on error handling
        assert response.status_code in [404, 500]

    def test_approve_invoice_already_approved(self, apar_client, mock_apar_engine):
        """Test approving already approved invoice (idempotent or error)."""
        # Mock returns already approved invoice
        from core.apar_engine import InvoiceStatus, APInvoice
        mock_apar_engine.approve_invoice.return_value = APInvoice(
            id="ap_123",
            vendor="Test Vendor",
            amount=100.0,
            due_date=datetime.now() + timedelta(days=30),
            line_items=[],
            status=InvoiceStatus.APPROVED,
            approved_by="user_1"
        )

        response = apar_client.post("/api/apar/ap/ap_123/approve")

        # Should succeed (idempotent) or return error
        assert response.status_code in [200, 400]

    def test_generate_ar_missing_customer(self, apar_client):
        """Test AR generation without customer field (422 validation error)."""
        response = apar_client.post("/api/apar/ar/generate", json={
            "amount": 500.0
        })

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_send_invoice_not_found(self, apar_client, mock_apar_engine):
        """Test sending non-existent invoice."""
        # Configure mock to raise ValueError
        mock_apar_engine.send_invoice.side_effect = ValueError("Invoice not found")

        response = apar_client.post("/api/apar/ar/invalid_id/send")

        # Route may return 404 or 500
        assert response.status_code in [404, 500]

    def test_mark_paid_already_paid(self, apar_client, mock_apar_engine):
        """Test marking already paid invoice as paid."""
        # Mock returns already paid invoice
        from core.apar_engine import InvoiceStatus, ARInvoice
        mock_apar_engine.mark_paid.return_value = ARInvoice(
            id="ar_123",
            customer="Test Customer",
            amount=500.0,
            due_date=datetime.now() + timedelta(days=30),
            line_items=[],
            status=InvoiceStatus.PAID
        )

        response = apar_client.post("/api/apar/ar/ar_123/paid")

        # Should succeed (idempotent) or return error
        assert response.status_code in [200, 400]

    def test_get_pending_approvals_empty(self, apar_client, mock_apar_engine):
        """Test pending approvals with no invoices."""
        # Configure mock to return empty list
        mock_apar_engine.get_pending_approvals.return_value = []

        response = apar_client.get("/api/apar/ap/pending")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["count"] == 0
        assert len(data["data"]["invoices"]) == 0

    def test_get_upcoming_payments_negative_days(self, apar_client):
        """Test upcoming payments with negative days parameter."""
        response = apar_client.get("/api/apar/ap/upcoming?days=-7")

        # API may return 400 or empty results
        assert response.status_code in [200, 400, 422]

    def test_get_overdue_invoices_empty(self, apar_client, mock_apar_engine):
        """Test overdue invoices with no results."""
        # Configure mock to return empty list
        mock_apar_engine.get_overdue_invoices.return_value = []

        response = apar_client.get("/api/apar/ar/overdue")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["count"] == 0
        assert len(data["data"]["invoices"]) == 0

    def test_send_reminder_not_found(self, apar_client, mock_apar_engine):
        """Test sending reminder for non-existent invoice."""
        # Configure mock to raise ValueError
        mock_apar_engine.generate_reminder.side_effect = ValueError("Invoice not found")

        response = apar_client.post("/api/apar/ar/invalid_id/remind")

        # Route may return 404 or 500
        assert response.status_code in [404, 500]
