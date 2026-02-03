from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging

from core.auth import get_current_user
from core.models import User

router = APIRouter(prefix="/api/v1/integrations", tags=["Integrations"])
logger = logging.getLogger(__name__)

class DynamicOptionsRequest(BaseModel):
    pieceId: str
    propertyName: str
    actionName: Optional[str] = None
    triggerName: Optional[str] = None
    config: Optional[Dict[str, Any]] = {}
    connectionId: Optional[str] = None

class DynamicOptionsResponse(BaseModel):
    options: List[Dict[str, Any]]
    placeholder: Optional[str] = None

@router.post("/dynamic-options", response_model=DynamicOptionsResponse)
async def get_dynamic_options(
    request: DynamicOptionsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Fetches dynamic options for a property (e.g., list of Slack channels)
    by calling the Node piece engine with real credentials if available.

    This endpoint integrates with the Node.js engine to fetch real-time options
    from external services (Slack channels, Gmail labels, etc.).
    """
    credentials = None
    if request.connectionId:
        try:
            from core.connection_service import connection_service
            credentials = await connection_service.get_connection_credentials(
                request.connectionId,
                current_user.id
            )
        except Exception as e:
            logger.error(f"Failed to get connection credentials: {e}", exc_info=True)
            return {
                "options": [],
                "placeholder": "Failed to retrieve credentials"
            }

    # Try to fetch real options from Node engine
    try:
        from integrations.bridge.node_bridge_service import node_bridge

        result = await node_bridge.get_dynamic_options(
            piece_name=request.pieceId,
            property_name=request.propertyName,
            action_name=request.actionName,
            trigger_name=request.triggerName,
            config=request.config,
            auth=credentials
        )

        # If we got valid options, return them
        if result.get("options"):
            logger.info(f"Successfully fetched {len(result['options'])} options for {request.pieceId}.{request.propertyName}")
            return {
                "options": result["options"],
                "placeholder": result.get("placeholder")
            }

        # Log error if present but continue to fallback
        if result.get("error"):
            logger.warning(f"Node engine returned error for dynamic options: {result['error']}")

    except ImportError:
        logger.error("Node bridge service not available")
    except Exception as e:
        logger.error(f"Failed to fetch real dynamic options: {e}", exc_info=True)

    # Fallback: Return empty options with clear message
    # Note: Removed mock data as requested in the plan
    logger.warning(f"No options available for {request.pieceId}.{request.propertyName}")

    return {
        "options": [],
        "placeholder": f"Connect to {request.pieceId} to view {request.propertyName} options"
    }
