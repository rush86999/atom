"""
AP/AR API Routes - Phase 41
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from core.base_routes import BaseAPIRouter

router = BaseAPIRouter()

class APIntakeRequest(BaseModel):
    vendor: str
    amount: float
    due_date: Optional[str] = None
    line_items: List[Dict[str, Any]] = []
    payment_terms: str = "Net 30"
    source: str = "email"

class ARGenerateRequest(BaseModel):
    customer: str
    amount: float
    due_date: Optional[str] = None
    line_items: List[Dict[str, Any]] = []
    source: str = "manual"

# ==================== ACCOUNTS PAYABLE ====================

@router.post("/ap/intake")
async def intake_ap_invoice(request: APIntakeRequest):
    from core.apar_engine import apar_engine

    data = {
        "vendor": request.vendor,
        "amount": request.amount,
        "due_date": request.due_date,
        "line_items": request.line_items,
        "payment_terms": request.payment_terms
    }

    invoice = apar_engine.intake_invoice(request.source, data)

    return router.success_response(
        data={
            "id": invoice.id,
            "vendor": invoice.vendor,
            "amount": invoice.amount,
            "status": invoice.status.value,
            "auto_approved": invoice.approved_by == "auto"
        },
        message="AP invoice intake successful"
    )

@router.post("/ap/{invoice_id}/approve")
async def approve_ap_invoice(invoice_id: str, approver: str = "user"):
    from core.apar_engine import apar_engine

    invoice = apar_engine.approve_invoice(invoice_id, approver)
    return router.success_response(
        data={"status": "approved", "id": invoice_id},
        message="Invoice approved successfully"
    )

@router.get("/ap/pending")
async def get_pending_approvals():
    from core.apar_engine import apar_engine

    pending = apar_engine.get_pending_approvals()
    return router.success_response(
        data={
            "count": len(pending),
            "invoices": [
                {"id": inv.id, "vendor": inv.vendor, "amount": inv.amount}
                for inv in pending
            ]
        },
        message=f"Retrieved {len(pending)} pending approvals"
    )

@router.get("/ap/upcoming")
async def get_upcoming_payments(days: int = 7):
    from core.apar_engine import apar_engine

    upcoming = apar_engine.get_upcoming_payments(days)
    return router.success_response(
        data={
            "count": len(upcoming),
            "total_due": sum(inv.amount for inv in upcoming),
            "invoices": [
                {"id": inv.id, "vendor": inv.vendor, "amount": inv.amount, "due_date": inv.due_date.isoformat()}
                for inv in upcoming
            ]
        },
        message=f"Retrieved {len(upcoming)} upcoming payments"
    )

# ==================== ACCOUNTS RECEIVABLE ====================

@router.post("/ar/generate")
async def generate_ar_invoice(request: ARGenerateRequest):
    from core.apar_engine import apar_engine

    data = {
        "customer": request.customer,
        "amount": request.amount,
        "due_date": request.due_date,
        "line_items": request.line_items
    }

    invoice = apar_engine.generate_invoice(request.source, data)

    return router.success_response(
        data={
            "id": invoice.id,
            "customer": invoice.customer,
            "amount": invoice.amount
        },
        message="AR invoice generated successfully"
    )

@router.post("/ar/{invoice_id}/send")
async def send_ar_invoice(invoice_id: str):
    from core.apar_engine import apar_engine

    invoice = apar_engine.send_invoice(invoice_id)
    return router.success_response(
        data={"status": "sent", "id": invoice_id},
        message="Invoice sent successfully"
    )

@router.post("/ar/{invoice_id}/paid")
async def mark_ar_paid(invoice_id: str):
    from core.apar_engine import apar_engine

    invoice = apar_engine.mark_paid(invoice_id)
    return router.success_response(
        data={"status": "paid", "id": invoice_id},
        message="Invoice marked as paid"
    )

@router.get("/ar/overdue")
async def get_overdue_invoices():
    from core.apar_engine import apar_engine

    overdue = apar_engine.get_overdue_invoices()
    return router.success_response(
        data={
            "count": len(overdue),
            "invoices": [
                {"id": inv.id, "customer": inv.customer, "amount": inv.amount}
                for inv in overdue
            ]
        },
        message=f"Retrieved {len(overdue)} overdue invoices"
    )

@router.post("/ar/{invoice_id}/remind")
async def send_reminder(invoice_id: str):
    from core.apar_engine import apar_engine

    reminder = apar_engine.generate_reminder(invoice_id)
    return router.success_response(
        data=reminder,
        message="Reminder generated successfully"
    )

@router.get("/ar/summary")
async def get_collection_summary():
    from core.apar_engine import apar_engine
    summary = apar_engine.get_collection_summary()
    return router.success_response(
        data=summary,
        message="Collection summary retrieved successfully"
    )
