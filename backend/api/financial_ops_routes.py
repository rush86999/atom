"""
Financial & Ops API Routes - Phase 37
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# Governance feature flags
FINANCIAL_GOVERNANCE_ENABLED = os.getenv("FINANCIAL_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"

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
async def add_subscription(request: SubscriptionRequest, agent_id: Optional[str] = None):
    """
    Add a subscription for cost leak detection.

    **Governance**: Requires INTERN+ maturity for financial data modifications.
    """
    # Governance check for financial operations
    if FINANCIAL_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="add_subscription",
                resource_type="financial_data",
                complexity=2  # MODERATE - financial data modification
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for add_subscription by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

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
    logger.info(f"Subscription added: {request.id} by agent {agent_id or 'system'}")
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
async def set_budget_limit(request: BudgetLimitRequest, agent_id: Optional[str] = None):
    """
    Set a budget limit for a spending category.

    **Governance**: Requires SUPERVISED+ maturity for budget policy changes.
    """
    # Governance check for budget policy changes
    if FINANCIAL_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="set_budget_limit",
                resource_type="budget_policy",
                complexity=3  # HIGH - budget policy modification
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for set_budget_limit by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

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
async def add_invoice(request: InvoiceRequest, agent_id: Optional[str] = None):
    """
    Add an invoice for reconciliation.

    **Governance**: Requires INTERN+ maturity for invoice data entry.
    """
    # Governance check for invoice entry
    if FINANCIAL_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="add_invoice",
                resource_type="financial_data",
                complexity=2  # MODERATE - financial data entry
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for add_invoice by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

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
async def add_contract(request: ContractRequest, agent_id: Optional[str] = None):
    """
    Add a contract for invoice reconciliation.

    **Governance**: Requires SUPERVISED+ maturity for contract management.
    """
    # Governance check for contract entry
    if FINANCIAL_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="add_contract",
                resource_type="contract_data",
                complexity=3  # HIGH - contract management
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for add_contract by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

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
