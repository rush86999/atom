import httpx
from fastapi import APIRouter, HTTPException, Request, Query, Response
from fastapi.responses import HTMLResponse
from typing import Optional, Dict
import logging

from backend.integrations.universal.auth_handler import universal_auth, OAuthState
from backend.integrations.universal.config import get_oauth_config
from backend.core.connection_service import connection_service

router = APIRouter(prefix="/api/v1/integrations/universal", tags=["Universal Integrations"])
logger = logging.getLogger(__name__)

@router.get("/authorize")
async def authorize_service(
    service_id: str,
    integration_type: str = "activepieces",
    user_id: str = "demo_user", # In prod, get from request state
    redirect_path: Optional[str] = None
):
    """
    Step 1: Get the OAuth authorization URL for a service.
    """
    config = get_oauth_config(service_id)
    if not config:
        raise HTTPException(status_code=400, detail=f"No OAuth config found for {service_id}")
    
    state = OAuthState(
        integration_type=integration_type,
        service_id=service_id,
        user_id=user_id,
        redirect_path=redirect_path
    )
    
    auth_url = universal_auth.generate_oauth_url(
        auth_url=config["auth_url"],
        client_id=config["client_id"],
        scopes=config["scopes"],
        state_payload=state
    )
    
    return {"url": auth_url}

@router.get("/callback")
async def universal_callback(
    code: str, 
    state: str,
    request: Request
):
    """
    Step 2: Universal OAuth callback handler.
    Exchanges code for token and saves connection.
    """
    try:
        # 1. Decode state
        result = await universal_auth.handle_callback(code, state)
        oauth_state: OAuthState = result["state"]
        
        # 2. Get config
        config = get_oauth_config(oauth_state.service_id)
        if not config:
            raise HTTPException(status_code=400, detail="Configuration lost during OAuth flow")
            
        # 3. Exchange code for token
        async with httpx.AsyncClient() as client:
            exchange_resp = await client.post(
                config["token_url"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": result["callback_url"],
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"]
                },
                headers={"Accept": "application/json"}
            )
            
            if exchange_resp.status_code != 200:
                logger.error(f"Token exchange failed: {exchange_resp.text}")
                raise HTTPException(status_code=400, detail="Token exchange failed")
                
            token_data = exchange_resp.json()
            
        # 4. Save connection
        connection_service.save_connection(
            user_id=oauth_state.user_id,
            integration_id=oauth_state.service_id,
            name=f"{oauth_state.service_id.split('/')[-1]} Connection",
            credentials=token_data
        )
        
        # 5. Return success HTML to close popup
        html_content = """
        <html>
            <body>
                <script>
                    window.opener.postMessage({ type: 'AUTH_SUCCESS' }, '*');
                    window.close();
                </script>
                <p>Authentication successful! This window will close automatically.</p>
            </body>
        </html>
        """
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        return HTMLResponse(content=f"<html><body>Authentication failed: {str(e)}</body></html>", status_code=500)

@router.get("/init")
async def init_auth(
    service_id: str,
    integration_type: str = "native"
):
    """Legacy redirect to authorize"""
    return {"message": "Use /api/v1/integrations/universal/authorize"}
