from fastapi import APIRouter, HTTPException

from datetime import datetime

# Auth Type: OAuth2
router = APIRouter(prefix="/api/plaid", tags=["plaid"])

class PlaidService:
    def __init__(self):
        self.client_id = "mock_client_id"
        
    async def get_link_token(self):
        return "mock_link_token"

plaid_service = PlaidService()

@router.get("/auth/url")
async def get_auth_url():
    """Get Plaid Link URL (mock)"""
    return {
        "url": "https://cdn.plaid.com/link/v2/stable/link.html?isWebview=true&token=link-sandbox-mock",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/callback")
async def handle_oauth_callback(public_token: str):
    """Handle Plaid Link callback (mock)"""
    return {
        "ok": True,
        "status": "success",
        "public_token": public_token,
        "message": "Plaid authentication successful (mock)",
        "timestamp": datetime.now().isoformat()
    }

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
