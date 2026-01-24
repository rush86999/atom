"""
GraphRAG Engine - PostgreSQL Backed (V2)
Stateless Graph Traversal using Recursive CTEs.
Replaces previous in-memory implementation.
"""

import logging
import os
import json
import uuid
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session

# Import Database
from core.database import SessionLocal, engine
from core.models import GraphNode, GraphEdge, GraphCommunity, CommunityMembership

logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

GRAPHRAG_LLM_ENABLED = os.getenv("GRAPHRAG_LLM_ENABLED", "true").lower() == "true"
GRAPHRAG_LLM_PROVIDER = os.getenv("GRAPHRAG_LLM_PROVIDER", "openai")
GRAPHRAG_LLM_MODEL = os.getenv("GRAPHRAG_LLM_MODEL", "gpt-4o-mini")

# ==================== DATA CLASSES (Transient) ====================

@dataclass
class Entity:
    """Named entity wrapper for API signatures"""
    id: str
    name: str
    entity_type: str
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Relationship:
    """Relationship wrapper for API signatures"""
    id: str
    from_entity: str
    to_entity: str
    rel_type: str
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)

class GraphRAGEngine:
    """
    PostgreSQL-backed GraphRAG Engine.
    Uses SQL Recursive CTEs for traversal (Stateless).
    """
    
    def __init__(self):
        self._llm_client = None
        self._initialize_llm_client()
    
    def _initialize_llm_client(self):
        """Initialize LLM client"""
        # (Same as before - simplified for brevity in this refactor)
        try:
            from openai import OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self._llm_client = OpenAI(api_key=api_key)
        except ImportError:
            pass

    # ==================== WRITE OPERATIONS (SQL) ====================

    def add_entity(self, entity: Entity, workspace_id: str) -> str:
        """Upsert entity to Postgres"""
        session = SessionLocal()
        try:
            # Check existence first (or use ON CONFLICT in raw SQL)
            # Using ORM for clarity, though bulk raw SQL is faster for mass ingestion
            existing = session.query(GraphNode).filter_by(
                workspace_id=workspace_id, 
                name=entity.name, 
                type=entity.entity_type
            ).first()
            
            if existing:
                existing.description = entity.description
                existing.properties = entity.properties
                entity.id = existing.id
            else:
                node = GraphNode(
                    id=entity.id,
                    workspace_id=workspace_id,
                    name=entity.name,
                    type=entity.entity_type,
                    description=entity.description,
                    properties=entity.properties
                )
                session.add(node)
                
            session.commit()
            return entity.id
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to add entity: {e}")
            return None
        finally:
            session.close()

    def add_relationship(self, rel: Relationship, workspace_id: str) -> str:
        """Insert edge to Postgres"""
        session = SessionLocal()
        try:
            # Ensure nodes exist (basic check logic should be upstream, but foreign keys enforce it)
            # Here we assume IDs are valid GraphNode.ids
            edge = GraphEdge(
                id=rel.id,
                workspace_id=workspace_id,
                source_node_id=rel.from_entity,
                target_node_id=rel.to_entity,
                relationship_type=rel.rel_type,
                properties=rel.properties
            )
            session.add(edge)
            session.commit()
            return rel.id
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to add relationship: {e}")
            return None
        finally:
            session.close()

    def ingest_structured_data(self, workspace_id: str, entities: List[Dict], relationships: List[Dict]):
        """Batch ingestion using session"""
        session = SessionLocal()
        try:
            # 1. Process Nodes
            node_map = {} # Name -> ID
            for e_data in entities:
                name = e_data.get("name")
                if not name: continue
                
                # Deduplicate logic simplified:
                node = GraphNode(
                    workspace_id=workspace_id,
                    name=name,
                    type=e_data.get("type", "unknown"),
                    description=e_data.get("description", ""),
                    properties=e_data.get("properties", {})
                )
                session.add(node)
                session.flush() # Get ID
                node_map[name] = node.id
            
            # 2. Process Edges
            for r_data in relationships:
                src = node_map.get(r_data.get("from"))
                dst = node_map.get(r_data.get("to"))
                if src and dst:
                    edge = GraphEdge(
                        workspace_id=workspace_id,
                        source_node_id=src,
                        target_node_id=dst,
                        relationship_type=r_data.get("type", "related_to"),
                        properties=r_data.get("properties", {})
                    )
                    session.add(edge)
            
            session.commit()
            logger.info(f"Ingested {len(entities)} nodes, {len(relationships)} edges to Postgres")
        except Exception as e:
            session.rollback()
            logger.error(f"Structured ingestion failed: {e}")
        finally:
            session.close()

    # ==================== READ OPERATIONS (SQL) ====================

    def local_search(self, workspace_id: str, query: str, depth: int = 2) -> Dict[str, Any]:
        """
        Perform Local Search using Recursive CTE (BFS).
        Finds the neighborhood of entities matching the query.
        """
        session = SessionLocal()
        try:
            # 1. Find Start Nodes (Search by name fuzzy match)
            start_nodes_sql = text("""
                SELECT id, name, type, description 
                FROM graph_nodes 
                WHERE workspace_id = :ws_id 
                AND name ILIKE :query 
                LIMIT 5
            """)
            start_nodes = session.execute(start_nodes_sql, {"ws_id": workspace_id, "query": f"%{query}%"}).fetchall()
            
            if not start_nodes:
                return {"mode": "local", "entities": [], "relationships": [], "context": "No matching entities found."}

            start_ids = [n.id for n in start_nodes]
            
            # 2. Recursive Traversal
            # Note: Postgres RECURSIVE CTE syntax
            traversal_sql = text("""
                WITH RECURSIVE traversal AS (
                    -- Base Case: Start Nodes
                    SELECT n.id, n.name, n.type, n.description, 0 as depth
                    FROM graph_nodes n
                    WHERE n.id = ANY(:start_ids)
                    
                    UNION
                    
                    -- Recursive Step: Join Edges
                    SELECT target.id, target.name, target.type, target.description, t.depth + 1
                    FROM graph_nodes target
                    JOIN graph_edges e ON e.target_node_id = target.id
                    JOIN traversal t ON e.source_node_id = t.id
                    WHERE t.depth < :max_depth
                )
                SELECT DISTINCT * FROM traversal;
            """)
            
            # Also fetch edges for context
            edges_sql = text("""
                SELECT e.source_node_id, e.target_node_id, e.relationship_type, e.properties
                FROM graph_edges e
                WHERE e.source_node_id = ANY(:node_ids) OR e.target_node_id = ANY(:node_ids)
                LIMIT 50
            """)

            nodes_result = session.execute(traversal_sql, {
                "start_ids": start_ids, 
                "max_depth": depth
            }).fetchall()
            
            found_node_ids = [n.id for n in nodes_result]
            
            edges_result = session.execute(edges_sql, {"node_ids": found_node_ids}).fetchall()
            
            # Format Output
            entities = [
                {"id": str(n.id), "name": n.name, "type": n.type, "description": n.description} 
                for n in nodes_result
            ]
            relationships = [
                {"from": str(e.source_node_id), "to": str(e.target_node_id), "type": e.relationship_type}
                for e in edges_result
            ]
            
            return {
                "mode": "local",
                "start_entities": [n.name for n in start_nodes],
                "entities": entities,
                "relationships": relationships,
                "count": len(entities)
            }

        except Exception as e:
            logger.error(f"Local search failed: {e}")
            return {"error": str(e)}
        finally:
            session.close()

    def global_search(self, workspace_id: str, query: str) -> Dict[str, Any]:
        """
        Global Search using Pre-computed Communities.
        Queries 'graph_communities' table.
        """
        session = SessionLocal()
        try:
            # Simple keyword match on community keywords or summary
            # In a real impl, this would use pgvector on community summaries
            sql = text("""
                SELECT id, summary, keywords, level
                FROM graph_communities
                WHERE workspace_id = :ws_id
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            communities = session.execute(sql, {"ws_id": workspace_id}).fetchall()
            
            # Re-rank in Python (simplified)
            scored = []
            q_lower = query.lower()
            for c in communities:
                score = 0
                if c.keywords:
                    score += sum(1 for k in c.keywords if k.lower() in q_lower)
                if q_lower in c.summary.lower():
                    score += 1
                if score > 0 or not q_lower:
                    scored.append(c.summary)
            
            if not scored:
                # Fallback: Just return generic summaries
                scored = [c.summary for c in communities[:3]]

            return {
                "mode": "global",
                "summaries": scored,
                "answer": " | ".join(scored)
            }

        except Exception as e:
            logger.error(f"Global search failed: {e}")
            return {"error": str(e)}
        finally:
            session.close()

    def query(self, workspace_id: str, query: str, mode: str = "auto") -> Dict[str, Any]:
        """Unified query entry point"""
        if mode == "auto":
            holistic = ["overview", "themes", "main", "all", "summary"]
            mode = "global" if any(kw in query.lower() for kw in holistic) else "local"
        
        if mode == "global":
            return self.global_search(workspace_id, query)
        else:
            return self.local_search(workspace_id, query)

    def get_context_for_ai(self, workspace_id: str, query: str) -> str:
        """Format context for AI prompt"""
        result = self.query(workspace_id, query)
        
        if result.get("mode") == "global":
            return f"Global Context: {result.get('answer')}"
        
        # Format local structure
        entities = result.get("entities", [])
        rels = result.get("relationships", [])
        
        context_lines = []
        context_lines.append(f"Found {len(entities)} relevant entities:")
        for e in entities[:10]:
            context_lines.append(f"- {e['name']} ({e['type']}): {e.get('description', '')}")
            
        context_lines.append("\nRelationships:")
        for r in rels[:15]:
            # Map IDs to Names if possible, or just raw
            # For brevity, using ID references here but ideally we map
            context_lines.append(f"- {r['from']} -> {r['type']} -> {r['to']}")
            
        return "\n".join(context_lines)

    def enqueue_reindex_job(self, workspace_id: str) -> bool:
        """Push re-index job to Redis queue for background worker"""
        redis_url = os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL")
        if not redis_url:
            logger.warning("No Redis URL configured, cannot enqueue reindex job.")
            return False
            
        try:
            import redis
            r = redis.from_url(redis_url)
            # Push to head of list
            r.lpush("graph_reindex_jobs", workspace_id)
            logger.info(f"Enqueued re-index job for {workspace_id}")
            
            # Optional: Call Fly Machines API to start worker if needed
            # self._trigger_fly_worker()
            
            return True
        except ImportError:
            logger.error("redis-py not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to enqueue job: {e}")
            return False

# Global Instance
graphrag_engine = GraphRAGEngine()
