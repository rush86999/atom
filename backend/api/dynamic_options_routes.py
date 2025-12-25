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
    Fetches dynamic options for a property (e.g., list of Slack channels).
    In a real implementation, this would call the 'options' function of the Activepiece.
    For now, we implement mock logic for high-priority pieces.
    """
    
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
    
    # Mock logic for Gmail labels
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

    # Default fallback
    return {
        "options": [],
        "placeholder": f"No options found for {request.propertyName}"
    }
