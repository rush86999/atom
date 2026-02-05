"""
Financial & Ops API Routes - Phase 37
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from core.base_routes import BaseAPIRouter
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.api_governance import require_governance, ActionComplexity
from core.database import get_db

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/financial-ops", tags=["Financial Ops"])

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
@require_governance(
    action_complexity=ActionComplexity.MODERATE,
    action_name="add_subscription",
    feature="financial"
)
async def add_subscription(
    request: SubscriptionRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Add a subscription for cost leak detection.

    **Governance**: Requires INTERN+ maturity (MODERATE complexity).
    - Financial data modification is a moderate action
    - Requires INTERN maturity or higher
    """
    from core.financial_ops_engine import SaaSSubscription, cost_detector

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
    logger.info(f"Subscription added: {request.id}")
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
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="set_budget_limit",
    feature="financial"
)
async def set_budget_limit(
    request: BudgetLimitRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Set a budget limit for a spending category.

    **Governance**: Requires SUPERVISED+ maturity (HIGH complexity).
    - Budget policy modification is a high-complexity action
    - Requires SUPERVISED maturity or higher
    """
    from core.financial_ops_engine import BudgetLimit, budget_guardrails

    limit = BudgetLimit(
        category=request.category,
        monthly_limit=request.monthly_limit,
        deal_stage_required=request.deal_stage_required,
        milestone_required=request.milestone_required
    )
    budget_guardrails.set_limit(limit)
    logger.info(f"Budget limit set for category {request.category} by agent {agent_id or 'system'}")
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
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="add_invoice",
    feature="financial"
)
async def add_invoice(
    request: InvoiceRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Add an invoice for reconciliation.

    **Governance**: Requires SUPERVISED+ maturity (HIGH complexity).
    - Invoice data entry is a high-complexity action
    - Requires SUPERVISED maturity or higher
    """
    from core.financial_ops_engine import Invoice, invoice_reconciler

    inv = Invoice(
        id=request.id,
        vendor=request.vendor,
        amount=request.amount,
        date=datetime.fromisoformat(request.date),
        contract_id=request.contract_id
    )
    invoice_reconciler.add_invoice(inv)
    logger.info(f"Invoice added: {request.id} by agent {agent_id or 'system'}")
    return {"status": "added", "id": request.id}

@router.post("/contracts")
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="add_contract",
    feature="financial"
)
async def add_contract(
    request: ContractRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Add a contract for invoice reconciliation.

    **Governance**: Requires SUPERVISED+ maturity (HIGH complexity).
    - Contract management is a high-complexity action
    - Requires SUPERVISED maturity or higher
    """
    from core.financial_ops_engine import Contract, invoice_reconciler

    contract = Contract(
        id=request.id,
        vendor=request.vendor,
        monthly_amount=request.monthly_amount,
        start_date=datetime.fromisoformat(request.start_date),
        end_date=datetime.fromisoformat(request.end_date)
    )
    invoice_reconciler.add_contract(contract)
    logger.info(f"Contract added: {request.id} by agent {agent_id or 'system'}")
    return {"status": "added", "id": request.id}

@router.get("/invoices/reconcile")
async def reconcile_invoices():
    from core.financial_ops_engine import invoice_reconciler
    return invoice_reconciler.reconcile()
