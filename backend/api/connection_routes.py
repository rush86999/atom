import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core.auth import get_current_user
from core.connection_service import connection_service
from core.models import User

router = APIRouter(prefix="/api/v1/connections", tags=["Connections"])
logger = logging.getLogger(__name__)

# Governance feature flags
CONNECTION_GOVERNANCE_ENABLED = os.getenv("CONNECTION_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"

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
async def delete_connection(connection_id: str, current_user: User = Depends(get_current_user), agent_id: Optional[str] = None):
    """
    Delete a connection.

    **Governance**: Requires SUPERVISED+ maturity for connection deletion.
    """
    # Governance check for connection deletion
    if CONNECTION_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="delete_connection",
                resource_type="connection",
                complexity=3  # HIGH - connection deletion
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for delete_connection by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

    success = connection_service.delete_connection(connection_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")

    logger.info(f"Connection deleted: {connection_id} by agent {agent_id or 'system'}")
    return {"status": "success"}

class RenameConnectionRequest(BaseModel):
    name: str

@router.patch("/{connection_id}")
async def rename_connection(connection_id: str, req: RenameConnectionRequest, current_user: User = Depends(get_current_user), agent_id: Optional[str] = None):
    """
    Rename a connection.

    **Governance**: Requires INTERN+ maturity for connection modification.
    """
    # Governance check for connection modification
    if CONNECTION_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="rename_connection",
                resource_type="connection",
                complexity=2  # MODERATE - connection modification
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for rename_connection by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

    success = connection_service.update_connection_name(connection_id, current_user.id, req.name)
    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")

    logger.info(f"Connection renamed: {connection_id} by agent {agent_id or 'system'}")
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
