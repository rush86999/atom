"""
Financial & Ops API Routes - Phase 37
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# ==================== COST LEAK DETECTION ====================

class SubscriptionRequest(BaseModel):
    id: str
    name: str
    monthly_cost: float
    last_used: str  # ISO date
    user_count: int
    active_users: int = 0
    category: str = "general"

@router.post("/cost/subscriptions")
async def add_subscription(request: SubscriptionRequest):
    from core.financial_ops_engine import cost_detector, SaaSSubscription
    
    sub = SaaSSubscription(
        id=request.id,
        name=request.name,
        monthly_cost=request.monthly_cost,
        last_used=datetime.fromisoformat(request.last_used),
        user_count=request.user_count,
        active_users=request.active_users,
        category=request.category
    )
    cost_detector.add_subscription(sub)
    return {"status": "added", "id": request.id}

@router.get("/cost/savings-report")
async def get_savings_report():
    from core.financial_ops_engine import cost_detector
    return cost_detector.get_savings_report()

# ==================== BUDGET GUARDRAILS ====================

class BudgetLimitRequest(BaseModel):
    category: str
    monthly_limit: float
    deal_stage_required: Optional[str] = None
    milestone_required: Optional[str] = None

class SpendCheckRequest(BaseModel):
    category: str
    amount: float
    deal_stage: Optional[str] = None
    milestone: Optional[str] = None

@router.post("/budget/limits")
async def set_budget_limit(request: BudgetLimitRequest):
    from core.financial_ops_engine import budget_guardrails, BudgetLimit
    
    limit = BudgetLimit(
        category=request.category,
        monthly_limit=request.monthly_limit,
        deal_stage_required=request.deal_stage_required,
        milestone_required=request.milestone_required
    )
    budget_guardrails.set_limit(limit)
    return {"status": "set", "category": request.category}

@router.post("/budget/check")
async def check_spend(request: SpendCheckRequest):
    from core.financial_ops_engine import budget_guardrails
    
    result = budget_guardrails.check_spend(
        request.category,
        request.amount,
        request.deal_stage,
        request.milestone
    )
    return result

# ==================== INVOICE RECONCILIATION ====================

class InvoiceRequest(BaseModel):
    id: str
    vendor: str
    amount: float
    date: str  # ISO date
    contract_id: Optional[str] = None

class ContractRequest(BaseModel):
    id: str
    vendor: str
    monthly_amount: float
    start_date: str
    end_date: str

@router.post("/invoices")
async def add_invoice(request: InvoiceRequest):
    from core.financial_ops_engine import invoice_reconciler, Invoice
    
    inv = Invoice(
        id=request.id,
        vendor=request.vendor,
        amount=request.amount,
        date=datetime.fromisoformat(request.date),
        contract_id=request.contract_id
    )
    invoice_reconciler.add_invoice(inv)
    return {"status": "added", "id": request.id}

@router.post("/contracts")
async def add_contract(request: ContractRequest):
    from core.financial_ops_engine import invoice_reconciler, Contract
    
    contract = Contract(
        id=request.id,
        vendor=request.vendor,
        monthly_amount=request.monthly_amount,
        start_date=datetime.fromisoformat(request.start_date),
        end_date=datetime.fromisoformat(request.end_date)
    )
    invoice_reconciler.add_contract(contract)
    return {"status": "added", "id": request.id}

@router.get("/invoices/reconcile")
async def reconcile_invoices():
    from core.financial_ops_engine import invoice_reconciler
    return invoice_reconciler.reconcile()
