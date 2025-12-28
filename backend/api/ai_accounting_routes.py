"""
AI Accounting API Routes - Phase 39
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# ==================== REQUEST MODELS ====================

class TransactionRequest(BaseModel):
    id: str
    date: str  # ISO format
    amount: float
    description: str
    merchant: Optional[str] = None
    source: str = "bank"

class BankFeedRequest(BaseModel):
    transactions: List[TransactionRequest]

class CategorizeRequest(BaseModel):
    transaction_id: str
    category_id: str

# ==================== TRANSACTION INGESTION ====================

@router.post("/transactions")
async def ingest_transaction(request: TransactionRequest):
    """Ingest a single transaction"""
    from core.ai_accounting_engine import ai_accounting, Transaction, TransactionSource
    
    tx = Transaction(
        id=request.id,
        date=datetime.fromisoformat(request.date),
        amount=request.amount,
        description=request.description,
        merchant=request.merchant,
        source=TransactionSource(request.source)
    )
    
    result = ai_accounting.ingest_transaction(tx)
    
    return {
        "id": result.id,
        "status": result.status.value,
        "category": result.category_name,
        "confidence": round(result.confidence * 100, 1),
        "reasoning": result.reasoning,
        "requires_review": result.status.value == "review_required"
    }

@router.post("/bank-feed")
async def ingest_bank_feed(request: BankFeedRequest):
    """Bulk ingest from bank feed"""
    from core.ai_accounting_engine import ai_accounting
    
    tx_data = [
        {
            "id": tx.id,
            "date": tx.date,
            "amount": tx.amount,
            "description": tx.description,
            "merchant": tx.merchant,
            "source": tx.source
        }
        for tx in request.transactions
    ]
    
    results = ai_accounting.ingest_bank_feed(tx_data)
    
    auto_posted = sum(1 for r in results if r.confidence >= 0.85)
    review_required = sum(1 for r in results if r.status.value == "review_required")
    
    return {
        "ingested": len(results),
        "auto_categorized": auto_posted,
        "review_required": review_required
    }

# ==================== CATEGORIZATION ====================

@router.post("/categorize")
async def categorize_transaction(request: CategorizeRequest, user_id: str = "user"):
    """Manually categorize a transaction (teaches the system)"""
    from core.ai_accounting_engine import ai_accounting
    
    ai_accounting.learn_categorization(request.transaction_id, request.category_id, user_id)
    
    return {"status": "categorized", "transaction_id": request.transaction_id}

@router.get("/review-queue")
async def get_review_queue():
    """Get transactions pending review"""
    from core.ai_accounting_engine import ai_accounting
    
    pending = ai_accounting.get_pending_review()
    
    return {
        "count": len(pending),
        "transactions": [
            {
                "id": tx.id,
                "date": tx.date.isoformat(),
                "amount": tx.amount,
                "description": tx.description,
                "merchant": tx.merchant,
                "suggested_category": tx.category_name,
                "confidence": round(tx.confidence * 100, 1),
                "reasoning": tx.reasoning
            }
            for tx in pending
        ]
    }

# ==================== POSTING ====================

@router.post("/post/{transaction_id}")
async def post_transaction(transaction_id: str, user_id: str = "user"):
    """Post a transaction to the ledger"""
    from core.ai_accounting_engine import ai_accounting
    
    success = ai_accounting.post_transaction(transaction_id, user_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Cannot post: transaction requires review")
    
    return {"status": "posted", "transaction_id": transaction_id}

@router.post("/auto-post")
async def auto_post_high_confidence():
    """Auto-post all high confidence transactions"""
    from core.ai_accounting_engine import ai_accounting
    
    posted = ai_accounting.auto_post_high_confidence()
    
    return {"posted_count": posted}

# ==================== CHART OF ACCOUNTS ====================

@router.get("/chart-of-accounts")
async def get_chart_of_accounts():
    """Get the Chart of Accounts"""
    from core.ai_accounting_engine import ai_accounting
    
    coa = ai_accounting._chart_of_accounts
    
    return {
        "accounts": [
            {
                "id": a.account_id,
                "name": a.name,
                "type": a.type,
                "keywords": a.keywords
            }
            for a in coa.values()
        ]
    }

# ==================== AUDIT TRAIL ====================

@router.get("/audit-log")
async def get_audit_log(transaction_id: Optional[str] = None):
    """Get immutable audit log"""
    from core.ai_accounting_engine import ai_accounting
    
    return ai_accounting.get_audit_log(transaction_id)


# ==================== DASHBOARD SYNC ====================

@router.get("/dashboard/summary")
async def get_accounting_dashboard_summary(workspace_id: str = "default"):
    """
    Fetch aggregated finance stats from Postgres Cache (Sync Strategy).
    Aggregates data from Stripe, Xero, etc.
    """
    try:
        from core.database import SessionLocal
        from saas.models import IntegrationMetric
        
        db = SessionLocal()
        
        # Query cached metrics
        metrics = db.query(IntegrationMetric).filter(
            IntegrationMetric.workspace_id == workspace_id,
            IntegrationMetric.metric_key.in_(["total_revenue", "pending_revenue", "gross_profit"])
        ).all()
        
        total_revenue = 0.0
        pending_revenue = 0.0
        
        for m in metrics:
            if m.metric_key == "total_revenue":
                total_revenue += float(m.value) if m.value else 0.0
            elif m.metric_key == "pending_revenue":
                pending_revenue += float(m.value) if m.value else 0.0
                
        db.close()
        
        return {
            "total_revenue": total_revenue,
            "pending_revenue": pending_revenue,
            "runway_months": 12, # Placeholder or calc
            "currency": "USD",
            "source": "synced_database"
        }
            
    except Exception as e:
        logger.error(f"Error fetching accounting summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
