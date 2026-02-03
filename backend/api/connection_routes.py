import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.api_governance import require_governance, ActionComplexity
from core.auth import get_current_user
from core.connection_service import connection_service
from core.database import get_db
from core.models import User

router = APIRouter(prefix="/api/v1/connections", tags=["Connections"])
logger = logging.getLogger(__name__)

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
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="delete_connection",
    feature="connection"
)
async def delete_connection(
    connection_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Delete a connection.

    **Governance**: Requires SUPERVISED+ maturity (HIGH complexity).
    - Connection deletion is a state-changing operation
    - Requires SUPERVISED maturity or higher
    """
    success = connection_service.delete_connection(connection_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")

    logger.info(f"Connection deleted: {connection_id}")
    return {"status": "success"}

class RenameConnectionRequest(BaseModel):
    name: str

@router.patch("/{connection_id}")
@require_governance(
    action_complexity=ActionComplexity.MODERATE,
    action_name="rename_connection",
    feature="connection"
)
async def rename_connection(
    connection_id: str,
    req: RenameConnectionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Rename a connection.

    **Governance**: Requires INTERN+ maturity (MODERATE complexity).
    - Connection modification is a moderate action
    - Requires INTERN maturity or higher
    """
    success = connection_service.update_connection_name(connection_id, current_user.id, req.name)
    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")

    logger.info(f"Connection renamed: {connection_id}")
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
