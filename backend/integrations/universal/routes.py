import logging
from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
import httpx

from core.auth import get_current_user
from core.connection_service import connection_service
from core.models import User
from integrations.universal.auth_handler import OAuthState, universal_auth
from integrations.universal.config import get_oauth_config

router = APIRouter(prefix="/api/v1/integrations/universal", tags=["Universal Integrations"])
logger = logging.getLogger(__name__)

@router.get("/authorize")
async def authorize_service(
    service_id: str,
    integration_type: str = "activepieces",
    current_user: User = Depends(get_current_user),
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
        user_id=current_user.id,
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
        connection = connection_service.save_connection(
            user_id=oauth_state.user_id,
            integration_id=oauth_state.service_id,
            name=f"{oauth_state.service_id.split('/')[-1]} Connection",
            credentials=token_data
        )

        # 5. Record experience in World Model for Agent Memory
        try:
            from datetime import datetime
            import uuid

            from core.agent_world_model import AgentExperience, WorldModelService
            
            world_model = WorldModelService(workspace_id="default")
            experience = AgentExperience(
                id=str(uuid.uuid4()),
                agent_id="atom_system",
                task_type="service_connection",
                input_summary=f"Connected to {oauth_state.service_id}",
                outcome="Success",
                learnings=f"The agent now has authenticated access to {oauth_state.service_id} via connection '{connection.connection_name}'.",
                agent_role="Orchestrator",
                timestamp=datetime.now()
            )
            await world_model.record_experience(experience)
            logger.info(f"Recorded connection experience for {oauth_state.service_id}")
        except Exception as me:
            logger.warning(f"Failed to record connection experience: {me}")
        
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
