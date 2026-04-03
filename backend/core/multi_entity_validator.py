"""
Multi-Entity Relationship Validator for GraphRAG.

Validates entity relationships before executing multi-entity JOIN queries.
Prevents invalid JOINs and enforces user-level isolation.
"""
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from core.models import GraphNode, GraphEdge

logger = logging.getLogger(__name__)


class MultiEntityValidator:
    """
    Validate entity relationships using GraphRAG.

    Ensures relationships exist between entity types before executing
    multi-entity JOIN queries.
    """

    def __init__(self, db: Session, workspace_id: str):
        """
        Initialize multi-entity validator.

        Args:
            db: SQLAlchemy database session
            workspace_id: Workspace ID for isolation (Upstream primary key)
        """
        self.db = db
        self.workspace_id = workspace_id

    def validate_relationship_exists(
        self,
        entity_type_a: str,
        entity_type_b: str,
        relationship_type: Optional[str] = None
    ) -> bool:
        """Validate that a relationship exists between two entity types."""
        logger.info(f"Validating relationship: {entity_type_a} -> {entity_type_b}")

        node_a = self.db.query(GraphNode).filter(
            GraphNode.workspace_id == self.workspace_id,
            GraphNode.type == entity_type_a
        ).first()

        node_b = self.db.query(GraphNode).filter(
            GraphNode.workspace_id == self.workspace_id,
            GraphNode.type == entity_type_b
        ).first()

        if not node_a or not node_b:
            raise ValueError(f"Entity types not indexed in GraphRAG.")

        query = self.db.query(GraphEdge).filter(
            GraphEdge.workspace_id == self.workspace_id,
            GraphEdge.source_node_id.in_([node_a.id, node_b.id]),
            GraphEdge.target_node_id.in_([node_a.id, node_b.id])
        )

        if relationship_type:
            query = query.filter(GraphEdge.relationship_type == relationship_type)

        relationship = query.first()
        if not relationship:
            raise ValueError(f"No relationship found between {entity_type_a} and {entity_type_b}.")

        return True

    def get_relationship_metadata(
        self,
        entity_type_a: str,
        entity_type_b: str
    ) -> Dict[str, Any]:
        """Get relationship metadata between two entity types."""
        node_a = self.db.query(GraphNode).filter(
            GraphNode.workspace_id == self.workspace_id,
            GraphNode.type == entity_type_a
        ).first()

        node_b = self.db.query(GraphNode).filter(
            GraphNode.workspace_id == self.workspace_id,
            GraphNode.type == entity_type_b
        ).first()

        if not node_a or not node_b: return {}

        edge = self.db.query(GraphEdge).filter(
            GraphEdge.workspace_id == self.workspace_id,
            GraphEdge.source_node_id.in_([node_a.id, node_b.id]),
            GraphEdge.target_node_id.in_([node_a.id, node_b.id])
        ).first()

        if not edge: return {}

        metadata = {
            "relationship_type": edge.relationship_type,
            "weight": edge.weight,
            "properties": edge.properties or {}
        }
        if edge.properties and "description" in edge.properties:
            metadata["description"] = edge.properties["description"]

        return metadata
