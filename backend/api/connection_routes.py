from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Dict, Any, Optional
from backend.core.connection_service import connection_service
from backend.core.auth import get_current_user
from backend.core.models import User
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
async def list_connections(integration_id: Optional[str] = None, current_user: User = Depends(get_current_user)):
    return connection_service.get_connections(current_user.id, integration_id)

@router.delete("/{connection_id}")
async def delete_connection(connection_id: str, current_user: User = Depends(get_current_user)):
    success = connection_service.delete_connection(connection_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"status": "success"}

class RenameConnectionRequest(BaseModel):
    name: str

@router.patch("/{connection_id}")
async def rename_connection(connection_id: str, req: RenameConnectionRequest, current_user: User = Depends(get_current_user)):
    success = connection_service.update_connection_name(connection_id, current_user.id, req.name)
    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"status": "success"}

@router.get("/{connection_id}/credentials")
async def get_credentials(connection_id: str, current_user: User = Depends(get_current_user)):
    """
    Internal use only / Dev only. In production, we should never expose raw credentials.
    """
    creds = connection_service.get_connection_credentials(connection_id, current_user.id)
    if not creds:
        raise HTTPException(status_code=404, detail="Connection not found")
    return creds
