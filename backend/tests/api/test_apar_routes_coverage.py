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
