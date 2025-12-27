from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import json

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])

class DynamicOptionsRequest(BaseModel):
    pieceId: str
    actionName: Optional[str] = None
    triggerName: Optional[str] = None
    propertyName: str
    connectionId: Optional[str] = None
    config: Dict[str, Any] = {}

class DynamicOption(BaseModel):
    label: str
    value: Any

class DynamicOptionsResponse(BaseModel):
    options: List[DynamicOption]
    placeholder: Optional[str] = None

@router.post("/dynamic-options", response_model=DynamicOptionsResponse)
async def get_dynamic_options(request: DynamicOptionsRequest):
    """
    Fetches dynamic options for a property (e.g., list of Slack channels) 
    by calling the Node piece engine with real credentials if available.
    """
    credentials = None
    if request.connectionId:
        from backend.core.connection_service import connection_service
        # Use demo_user for MVP
        credentials = connection_service.get_connection_credentials(request.connectionId, "demo_user")
    
    # In a real implementation, we'd call the Node engine's dynamic options endpoint.
    # For now, let's keep the mock for Slack if no credentials, 
    # but try to call the Node engine if we have them.
    
    if credentials:
        try:
            from backend.integrations.bridge.node_bridge_service import node_bridge
            
            # This requires a new endpoint in the node engine for dynamic options
            # For now, we will proxy this to a potential node endpoint or implement a bridge call
            result = await node_bridge.get_dynamic_options(
                piece_name=request.pieceId,
                property_name=request.propertyName,
                action_name=request.actionName,
                trigger_name=request.triggerName,
                config=request.config,
                auth=credentials
            )
            return {"options": result.get("options", []), "placeholder": result.get("placeholder")}
        except Exception as e:
            logger.error(f"Failed to fetch real dynamic options: {e}")
            # Fallback to mock logic
            pass

    # Mock logic for Slack channels
    if request.pieceId == "@activepieces/piece-slack" and request.propertyName == "channel":
        return {
            "options": [
                {"label": "# general", "value": "C12345"},
                {"label": "# random", "value": "C67890"},
                {"label": "# engineering", "value": "C11111"},
                {"label": "# product", "value": "C22222"},
                {"label": "# support", "value": "C33333"},
            ],
            "placeholder": "Select a channel"
        }
    
    # ... (rest of the mock Gmail logic)
    if request.pieceId == "@activepieces/piece-gmail" and request.propertyName == "label":
        return {
            "options": [
                {"label": "INBOX", "value": "INBOX"},
                {"label": "SENT", "value": "SENT"},
                {"label": "DRAFTS", "value": "DRAFTS"},
                {"label": "SPAM", "value": "SPAM"},
                {"label": "TRASH", "value": "TRASH"},
            ],
            "placeholder": "Select a label"
        }

    return {
        "options": [],
        "placeholder": f"No options found for {request.propertyName}"
    }
