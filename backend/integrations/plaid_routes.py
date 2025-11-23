from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/plaid", tags=["plaid"])

@router.get("/status")
async def plaid_status():
    """Status check for Plaid integration"""
    return {
        "status": "active",
        "service": "plaid",
        "version": "1.0.0",
        "business_value": {
            "financial_insights": True,
            "expense_tracking": True,
            "budget_management": True
        }
    }

@router.get("/health")
async def plaid_health():
    """Health check for Plaid integration"""
    return await plaid_status()
