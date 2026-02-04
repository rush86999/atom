
import logging
from typing import Any, Dict, List, Optional
from ai.device_node_service import device_node_service
from fastapi import BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import DeviceNode, User
from core.security import get_current_user


# Configure Pydantic models
class DeviceNodeRegister(BaseModel):
    deviceId: str
    name: Optional[str] = "Unknown Device"
    type: Optional[str] = "desktop"
    capabilities: List[str] = []
    metadata: Dict[str, Any] = {}

class DeviceNodeResponse(BaseModel):
    id: str
    name: str
    status: str
    type: str

router = BaseAPIRouter(prefix="/api/devices/nodes", tags=["Device Nodes"])
logger = logging.getLogger("DEVICE_API")

@router.post("/register")
async def register_node(
    node: DeviceNodeRegister,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Register a generic device node (desktop, mobile, cloud).
    """
    # Assuming user belongs to at least one workspace - simplified for upstream
    # In real upstream, we might need a workspace_id query param or header
    # For now, pick the first workspace or use a default
    workspace_id = current_user.workspaces[0].id if current_user.workspaces else "default"
    
    try:
        registered_node = device_node_service.register_node(
            db,
            workspace_id,
            node.dict()
        )
        return router.success_response(
            data={"node_id": registered_node.id},
            message="Device node registered successfully"
        )
    except Exception as e:
        logger.error(f"Failed to register node: {e}")
        raise router.internal_error(message=str(e))

@router.post("/{device_id}/heartbeat")
async def heartbeat(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ping from a device to keep it 'online'.
    """
    workspace_id = current_user.workspaces[0].id if current_user.workspaces else "default"
    device_node_service.heartbeat(db, workspace_id, device_id)
    return router.success_response(message="Heartbeat received")

@router.get("/", response_model=List[DeviceNodeResponse])
async def list_nodes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List active nodes for the user's workspace.
    """
    workspace_id = current_user.workspaces[0].id if current_user.workspaces else "default"
    nodes = device_node_service.get_active_nodes(db, workspace_id)
    
    return [
        {
            "id": n.id,
            "name": n.name,
            "status": n.status,
            "type": n.node_type
        } for n in nodes
    ]
