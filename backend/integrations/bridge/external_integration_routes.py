
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException

from core.external_integration_service import external_integration_service

router = APIRouter(prefix="/api/v1/external-integrations", tags=["External Integrations"])

@router.get("/")
async def list_external_integrations():
    """
    List all available external (Node.js) integrations.
    """
    return await external_integration_service.get_all_integrations()

@router.get("/{piece_name}")
async def get_external_integration_details(piece_name: str):
    """
    Get details for a specific piece (actions, triggers, auth).
    """
    details = await external_integration_service.get_piece_details(piece_name)
    if not details:
        raise HTTPException(status_code=404, detail="Integration not found")
    return details

@router.post("/execute")
async def execute_external_action(payload: Dict[str, Any]):
    """
    Execute an action on an external integration.
    """
    try:
        piece_name = payload.get("pieceName")
        action_name = payload.get("actionName")
        props = payload.get("props", {})
        auth = payload.get("auth", {})
        
        if not piece_name or not action_name:
            raise HTTPException(status_code=400, detail="Missing pieceName or actionName")
            
        result = await external_integration_service.execute_integration_action(
            integration_id=piece_name,
            action_id=action_name,
            params=props,
            credentials=auth
        )
        return {"status": "success", "output": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
