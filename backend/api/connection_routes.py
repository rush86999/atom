
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Dict, Any, Optional
from backend.core.connection_service import connection_service
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/connections", tags=["Connections"])

class ConnectionResponse(BaseModel):
    id: str
    name: str
    integration_id: str
    status: str
    created_at: Optional[str] = None
    last_used: Optional[str] = None

@router.get("/", response_model=List[ConnectionResponse])
async def list_connections(integration_id: Optional[str] = None):
    # In real app, get user_id from session/JWT
    # For MVP, using a demo user_id
    user_id = "demo_user" 
    return connection_service.get_connections(user_id, integration_id)

@router.delete("/{connection_id}")
async def delete_connection(connection_id: str):
    user_id = "demo_user"
    success = connection_service.delete_connection(connection_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"status": "success"}

@router.get("/{connection_id}/credentials")
async def get_credentials(connection_id: str):
    """
    Internal use only / Dev only. In production, we should never expose raw credentials.
    """
    user_id = "demo_user"
    creds = connection_service.get_connection_credentials(connection_id, user_id)
    if not creds:
        raise HTTPException(status_code=404, detail="Connection not found")
    return creds
