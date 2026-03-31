"""
Capability Schema Service - Upstream Edition

Manages capability definitions stored as GraphNode entities.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.models import GraphNode
from core.database import SessionLocal
from core.capability_graduation_service import CapabilityGraduationService

logger = logging.getLogger(__name__)

class CapabilitySchemaService:
    """Service for managing capability schemas."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()

    def create_capability_node(self, tenant_id: str, capability: dict, created_by: str) -> GraphNode:
        """Create a GraphNode entity for a capability."""
        node = GraphNode(
            tenant_id=tenant_id,
            workspace_id=tenant_id,
            name=capability["name"],
            type="capability",
            description=capability.get("description", ""),
            properties={
                "capability_type": capability.get("type", "action"),
                "parameters": capability.get("parameters", {}),
                "returns": capability.get("returns"),
                "examples": capability.get("examples", []),
                "maturity_requirement": capability.get("maturity_requirement", "student"),
                "created_by": created_by,
                "created_at": datetime.utcnow().isoformat()
            }
        )
        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)
        return node

    def update_capability_node(self, tenant_id: str, capability_id: str, updates: dict, updated_by: str) -> GraphNode:
        """Update a capability and trigger maturity reset if implementation changed."""
        node = self.db.query(GraphNode).filter(
            and_(GraphNode.id == capability_id, GraphNode.type == "capability")
        ).first()
        
        if not node:
            raise ValueError(f"Capability node {capability_id} not found")

        old_props = node.properties.copy()
        logic_changed = False
        
        # Implementation change detection
        if "parameters" in updates and updates["parameters"] != old_props.get("parameters"):
            logic_changed = True
        if "type" in updates and updates["type"] != old_props.get("capability_type"):
            logic_changed = True

        # Apply updates
        if "name" in updates: node.name = updates["name"]
        if "description" in updates: node.description = updates["description"]
        
        prop_mapping = {"type": "capability_type", "parameters": "parameters", "returns": "returns"}
        for k, pk in prop_mapping.items():
            if k in updates: node.properties[pk] = updates[k]

        node.properties["updated_by"] = updated_by
        node.properties["updated_at"] = datetime.utcnow().isoformat()
        self.db.commit()

        if logic_changed:
            grad_service = CapabilityGraduationService(self.db)
            # Upstream: Reset all agents for this capability
            from core.models import AgentCapabilityRegistry
            affected = self.db.query(AgentCapabilityRegistry).filter(
                AgentCapabilityRegistry.capability_id == str(node.id)
            ).all()
            for link in affected:
                grad_service.reset_maturity(tenant_id, link.agent_id, node.name, "implementation_changed")

        return node

    def get_capability_by_id(self, tenant_id: str, capability_id: str) -> Optional[GraphNode]:
        return self.db.query(GraphNode).filter(
            and_(GraphNode.tenant_id == tenant_id, GraphNode.id == capability_id, GraphNode.type == "capability")
        ).first()
