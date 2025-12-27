
from fastapi import APIRouter, HTTPException, Request, Query
from typing import Optional, Dict

from backend.integrations.universal.auth_handler import universal_auth, OAuthState

router = APIRouter(prefix="/api/v1/integrations/universal", tags=["Universal Integrations"])

@router.get("/callback")
async def universal_callback(
    code: str, 
    state: str,
    request: Request
):
    """
    Universal OAuth callback handler.
    Receives code and encrypted state, delegates to specific integration strategy.
    """
    try:
        # 1. Process callback using handler
        result = await universal_auth.handle_callback(code, state)
        
        # 2. Determine next steps
        # In a real implementation, we might redirect the user to a "success" page 
        # or close the popup window.
        
        # For now, return a success HTML page that postMessages back to the main window
        return {
            "status": "success", 
            "message": "Authentication successful", 
            "data": result
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal authentication error")

@router.get("/init")
async def init_auth(
    service_id: str,
    integration_type: str = "native", 
    redirect_path: Optional[str] = None
):
    """
    Helper to generate an OAuth start URL (for testing).
    """
    # This is a placeholder. In reality, the specific integration service 
    # (e.g. DropboxService) calls universal_auth.generate_oauth_url directly.
    return {"message": "Use specific integration endpoints to initiate auth"}
