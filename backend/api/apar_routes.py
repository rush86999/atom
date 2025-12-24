"""
AP/AR API Routes - Phase 41
"""

from fastapi import APIRouter
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime
import logging

router = APIRouter()

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
    
    return {
        "id": invoice.id,
        "vendor": invoice.vendor,
        "amount": invoice.amount,
        "status": invoice.status.value,
        "auto_approved": invoice.approved_by == "auto"
    }

@router.post("/ap/{invoice_id}/approve")
async def approve_ap_invoice(invoice_id: str, approver: str = "user"):
    from core.apar_engine import apar_engine
    
    invoice = apar_engine.approve_invoice(invoice_id, approver)
    return {"status": "approved", "id": invoice_id}

@router.get("/ap/pending")
async def get_pending_approvals():
    from core.apar_engine import apar_engine
    
    pending = apar_engine.get_pending_approvals()
    return {
        "count": len(pending),
        "invoices": [
            {"id": inv.id, "vendor": inv.vendor, "amount": inv.amount}
            for inv in pending
        ]
    }

@router.get("/ap/upcoming")
async def get_upcoming_payments(days: int = 7):
    from core.apar_engine import apar_engine
    
    upcoming = apar_engine.get_upcoming_payments(days)
    return {
        "count": len(upcoming),
        "total_due": sum(inv.amount for inv in upcoming),
        "invoices": [
            {"id": inv.id, "vendor": inv.vendor, "amount": inv.amount, "due_date": inv.due_date.isoformat()}
            for inv in upcoming
        ]
    }

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
    
    return {"id": invoice.id, "customer": invoice.customer, "amount": invoice.amount}

@router.post("/ar/{invoice_id}/send")
async def send_ar_invoice(invoice_id: str):
    from core.apar_engine import apar_engine
    
    invoice = apar_engine.send_invoice(invoice_id)
    return {"status": "sent", "id": invoice_id}

@router.post("/ar/{invoice_id}/paid")
async def mark_ar_paid(invoice_id: str):
    from core.apar_engine import apar_engine
    
    invoice = apar_engine.mark_paid(invoice_id)
    return {"status": "paid", "id": invoice_id}

@router.get("/ar/overdue")
async def get_overdue_invoices():
    from core.apar_engine import apar_engine
    
    overdue = apar_engine.get_overdue_invoices()
    return {
        "count": len(overdue),
        "invoices": [
            {"id": inv.id, "customer": inv.customer, "amount": inv.amount}
            for inv in overdue
        ]
    }

@router.post("/ar/{invoice_id}/remind")
async def send_reminder(invoice_id: str):
    from core.apar_engine import apar_engine
    
    reminder = apar_engine.generate_reminder(invoice_id)
    return reminder

@router.get("/ar/summary")
async def get_collection_summary():
    from core.apar_engine import apar_engine
    return apar_engine.get_collection_summary()
