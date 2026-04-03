"""
Agent-Specific GraphRAG Integration Service.

Wraps GraphRAGEngine with agent-specific context retrieval, fail-fast validation,
and instance-level relationship checking to prevent agent hallucination.
"""
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from core.graphrag_engine import GraphRAGEngine
from core.models import GraphNode, GraphEdge

logger = logging.getLogger(__name__)


class AgentGraphRAGService:
    """
    Agent-specific GraphRAG integration service.
    
    Provides:
    - Context retrieval with agent-specific logging
    - Instance-level relationship validation
    - Fail-fast validation for empty results
    - Performance-optimized result limits
    """

    def __init__(self, db: Session, workspace_id: str, agent_id: str):
        """
        Initialize agent GraphRAG service.

        Args:
            db: SQLAlchemy database session
            workspace_id: Workspace ID for isolation (Upstream primary key)
            agent_id: Agent ID for audit logging
        """
        self.db = db
        self.workspace_id = workspace_id
        self.agent_id = agent_id
        self.graphrag = GraphRAGEngine()

    async def get_agent_context(
        self,
        query: str,
        mode: str = 'auto',
        max_entities: int = 15,
        max_relationships: int = 25
    ) -> Dict[str, Any]:
        """Get GraphRAG context for agent reasoning."""
        logger.info(f"Agent {self.agent_id} requesting GraphRAG context: {query[:50]}...")

        # Query GraphRAG (workspace-isolated)
        result = self.graphrag.query(
            workspace_id=self.workspace_id,
            query=query,
            mode=mode
        )

        if result.get("mode") == "local":
            entities = result.get("entities", [])
            relationships = result.get("relationships", [])

            if not entities and not relationships:
                raise ValueError(f"GraphRAG validation failed: No entities found for query '{query}'")

            result["entities"] = entities[:max_entities]
            result["relationships"] = relationships[:max_relationships]

        elif result.get("mode") == "global":
            answer = result.get("answer", "")
            if not answer or answer.strip() == "":
                raise ValueError(f"GraphRAG global search failed: No community summaries for '{query}'")

        result["agent_id"] = self.agent_id
        result["has_results"] = True
        result["context"] = self._format_context(result)

        return result

    async def validate_entity_relationship(
        self,
        entity_name_a: str,
        entity_name_b: str,
        relationship_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate that a relationship exists between two entity instances."""
        logger.info(f"Agent {self.agent_id} validating relationship: {entity_name_a} -> {entity_name_b}")

        node_a = self.db.query(GraphNode).filter(
            GraphNode.workspace_id == self.workspace_id,
            GraphNode.name == entity_name_a
        ).first()

        node_b = self.db.query(GraphNode).filter(
            GraphNode.workspace_id == self.workspace_id,
            GraphNode.name == entity_name_b
        ).first()

        if not node_a or not node_b:
            raise ValueError(f"Entities not found in GraphRAG for validation.")

        query = self.db.query(GraphEdge).filter(
            GraphEdge.workspace_id == self.workspace_id,
            GraphEdge.source_node_id == node_a.id,
            GraphEdge.target_node_id == node_b.id
        )

        if relationship_type:
            query = query.filter(GraphEdge.relationship_type == relationship_type)

        edge = query.first()

        if not edge:
            raise ValueError(f"No relationship found between '{entity_name_a}' and '{entity_name_b}'.")

        properties = edge.properties or {}
        return {
            "exists": True,
            "relationship_type": edge.relationship_type,
            "description": properties.get('description', f"{entity_name_a} -> {entity_name_b}"),
            "weight": edge.weight,
            "metadata": properties
        }

    def _format_context(self, result: Dict[str, Any]) -> str:
        """Format GraphRAG result as context string."""
        if result.get("mode") == "global":
            return f"Global Context: {result.get('answer', '')}"

        entities = result.get("entities", [])
        relationships = result.get("relationships", [])
        id_to_name = {e['id']: e['name'] for e in entities}

        lines = [f"Found {len(entities)} relevant entities:"]
        for e in entities[:15]:
            lines.append(f"- {e['name']} ({e['type']}): {e.get('description', '')}")

        lines.append(f"\n{len(relationships)} relationships:")
        for r in relationships[:25]:
            from_name = id_to_name.get(r['from'], r['from'])
            to_name = id_to_name.get(r['to'], r['to'])
            lines.append(f"- {from_name} -> {to_name} ({r.get('type', 'related')})")

        return "\n".join(lines)
