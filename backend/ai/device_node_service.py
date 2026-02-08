
from datetime import datetime, timedelta
import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.models import DeviceNode, Workspace

logger = logging.getLogger("DEVICE_NODE_SERVICE")

class DeviceNodeService:
    def __init__(self):
        pass
        
    def get_db(self):
        # Helper to get DB session if not provided
        return SessionLocal()

    def register_node(self, db: Session, workspace_id: str, node_data: Dict[str, Any]) -> DeviceNode:
        """
        Register or update a device node.
        """
        device_id = node_data.get("deviceId")
        if not device_id:
            raise ValueError("deviceId is required")
            
        # Prepare data
        name = node_data.get("name", "Unknown Device")
        node_type = node_data.get("type", "desktop_marketing")
        capabilities = node_data.get("capabilities", [])
        metadata = node_data.get("metadata", {})
        
        # Check if exists
        node = db.query(DeviceNode).filter(
            DeviceNode.workspace_id == workspace_id,
            DeviceNode.device_id == device_id
        ).first()
        
        if node:
            # Update
            node.name = name
            node.node_type = node_type
            node.capabilities = capabilities
            node.metadata_json = metadata
            node.status = 'online'
            node.last_seen = datetime.utcnow()
            logger.info(f"Updated device node: {name} ({device_id})")
        else:
            # Create
            node = DeviceNode(
                workspace_id=workspace_id,
                device_id=device_id,
                name=name,
                node_type=node_type,
                capabilities=capabilities,
                metadata_json=metadata,
                status='online',
                last_seen=datetime.utcnow()
            )
            db.add(node)
            logger.info(f"Registered new device node: {name} ({device_id})")
            
        db.commit()
        db.refresh(node)
        return node
        
    def heartbeat(self, db: Session, workspace_id: str, device_id: str):
        """
        Update last_seen for a node.
        """
        node = db.query(DeviceNode).filter(
            DeviceNode.workspace_id == workspace_id,
            DeviceNode.device_id == device_id
        ).first()
        
        if node:
            node.last_seen = datetime.utcnow()
            node.status = 'online'
            db.commit()
            
    def get_active_nodes(self, db: Session, workspace_id: str, timeout_minutes: int = 5) -> List[DeviceNode]:
        """
        Get all online nodes for a workspace.
        """
        cutoff = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        return db.query(DeviceNode).filter(
            DeviceNode.workspace_id == workspace_id,
            DeviceNode.last_seen > cutoff
        ).all()
        
    def set_status(self, db: Session, workspace_id: str, device_id: str, status: str):
        """
        Manually set status (e.g. 'busy').
        """
        node = db.query(DeviceNode).filter(
            DeviceNode.workspace_id == workspace_id,
            DeviceNode.device_id == device_id
        ).first()
        
        if node:
            node.status = status
            db.commit()

# Singleton
device_node_service = DeviceNodeService()
