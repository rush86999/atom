"""
GraphRAG Engine - PostgreSQL Backed (V2)
Stateless Graph Traversal using Recursive CTEs.
Replaces previous in-memory implementation.
"""

import logging
import os
import json
import uuid
import asyncio
import re
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from sqlalchemy import text, func
from sqlalchemy.orm import Session

# Import Database
from core.database import engine, get_db_session
from core.models import (
    GraphNode, GraphEdge, GraphCommunity, CommunityMembership, EntityTypeDefinition,
    User, Workspace, Team, SupportTicket, Formula, UserTask
)

# Import LLMService for unified LLM interactions
from core.llm_service import LLMService

logger = logging.getLogger(__name__)

# Automation Integration (Optional check for upstream)
try:
    from advanced_workflow_orchestrator import orchestrator
    from core.atom_meta_agent import handle_data_event_trigger
    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False
    logger.warning("Workflow automation integration unavailable")

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
    def __init__(self, workspace_id: str = "default"):
        """
        Initialize GraphRAG Engine.

        Args:
            workspace_id: Workspace identifier for multi-tenant isolation
        """
        self.workspace_id = workspace_id
        # Initialize LLMService for unified LLM interactions
        self.llm_service = LLMService(tenant_id=workspace_id)

    def _get_registry_entry(self, entity_type: str) -> Optional[Dict]:
        """Get the registry configuration for a canonical type."""
        t_lower = entity_type.lower()
        if t_lower in ENTITY_REGISTRY:
            return ENTITY_REGISTRY[t_lower]
        return None

    def _sanitize_canonical_data(self, registry_entry: Dict, metadata: Dict) -> Dict:
        """Filter metadata to only allow updatable fields defined in the registry."""
        sanitized = {}
        updatable = registry_entry.get("updatable_fields", [])
        for field_name in updatable:
            if field_name in metadata and metadata[field_name] is not None:
                sanitized[field_name] = metadata[field_name]
        return sanitized

    def _resolve_canonical_entity(self, session: Session, workspace_id: str, 
                                 entity_type: str, name: str, 
                                 canonical_id: Optional[str] = None) -> Optional[Any]:
        """Resolve a semantic node to a concrete database record."""
        registry = self._get_registry_entry(entity_type)
        if not registry:
            return None

        model = registry["model"]
        
        # 1. Match by ID if provided
        if canonical_id:
            return session.query(model).filter(model.id == canonical_id).first()
        
        # 2. Match by Name/Search fields
        display_field = registry.get("display_field", "name")
        # Try exact match on display field first
        match = session.query(model).filter(
            getattr(model, display_field).ilike(name)
        ).first()
        
        if match:
            return match
            
        # 3. Fuzzy match across search fields
        for field_name in registry.get("search_fields", []):
            match = session.query(model).filter(
                getattr(model, field_name).ilike(f"%{name}%")
            ).first()
            if match:
                return match
                
        return None

    def canonical_search(self, workspace_id: str, entity_type: str, query: str) -> List[Dict]:
        """Search for canonical records to anchor graph nodes."""
        registry = self._get_registry_entry(entity_type)
        if not registry:
            return []

        model = registry["model"]
        search_fields = registry.get("search_fields", ["name"])
        display_field = registry.get("display_field", "name")
        
        with get_db_session() as session:
            try:
                # Use a combined OR filter for all search fields
                from sqlalchemy import or_
                filters = [getattr(model, f_name).ilike(f"%{query}%") for f_name in search_fields]
                
                # Check for tenant/workspace isolation if the model has a column for it
                # In personal edition, some models might not have workspace_id but use other links
                # For simplicity, we'll try to find workspace_id or tenant_id
                query_obj = session.query(model).filter(or_(*filters))
                
                if hasattr(model, 'workspace_id'):
                    query_obj = query_obj.filter(model.workspace_id == workspace_id)
                elif hasattr(model, 'tenant_id'):
                    # Map workspace_id to tenant_id if needed, or assume they are compatible strings here
                    query_obj = query_obj.filter(model.tenant_id == workspace_id)

                records = query_obj.limit(10).all()
                return [
                    {"id": str(r.id), "name": getattr(r, display_field)}
                    for r in records
                ]
            except Exception as e:
                logger.error(f"Canonical search failed: {e}")
                return []
            finally:
                session.close()
    
    def _get_llm_client(self, workspace_id: str) -> None:
        """
        LLM client management now handled by LLMService.

        This method returns None for compatibility. Actual LLM calls
        use self.llm_service.generate_completion which handles
        provider selection, API key resolution, and caching internally.
        """
        return None

    def _is_llm_available(self, workspace_id: str) -> bool:
        """
        Check if LLM is available for GraphRAG operations.
        LLMService handles provider availability internally.
        """
        # LLMService handles provider selection and availability
        # Always return True when GRAPHRAG_LLM_ENABLED is set
        # LLMService will handle errors if provider is unavailable
        return GRAPHRAG_LLM_ENABLED

    # ==================== LLM EXTRACTION (Migrated to LLMService) ====================

    async def _llm_extract_entities_and_relationships(
        self, text: str, doc_id: str, source: str, workspace_id: str
    ) -> tuple[List[Entity], List[Relationship]]:
        """
        Extract entities and relationships using LLMService.

        Uses unified LLM interface for BYOK support, provider selection,
        and cost tracking. JSON mode requested via system prompt.

        Cost tracking consideration:
        - GraphRAG entity/relationship extraction can be expensive (~$0.01-0.10 per document)
        - LLMService.generate_completion tracks tokens/cost automatically via unified telemetry
        - Consider adding monitoring alerts for high-cost GraphRAG operations
        """
        prompt = f"""Analyze the following text and extract knowledge graph elements.
Respond with valid JSON only.

Text:
\"\"\"
{text[:6000]}
\"\"\"

JSON Schema:
{{
  "entities": [{{"name": "string", "type": "string", "description": "string", "canonical_type": "string (optional: user, workspace, goal, project, task)"}}],
  "relationships": [{{"from": "string", "to": "string", "type": "string", "description": "string"}}]
}}"""

        try:
            # Use LLMService for unified LLM interaction
            response = await self.llm_service.generate_completion(
                messages=[
                    {"role": "system", "content": "You are a knowledge graph extractor. Output valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                model=GRAPHRAG_LLM_MODEL,
                temperature=0.1
            )

            # Extract content from LLMService response format
            content = response.get("content", "")
            if not content:
                logger.warning(f"LLM extraction returned empty content for doc {doc_id}")
                return [], []

            data = json.loads(content)

            entities = []
            for e in data.get("entities", []):
                properties = {"source": source, "doc_id": doc_id, "llm_extracted": True}
                if e.get("canonical_type"):
                    properties["canonical_type"] = e["canonical_type"]
                entities.append(Entity(
                    id=str(uuid.uuid4()),
                    name=e["name"],
                    entity_type=e["type"],
                    description=e.get("description", ""),
                    properties=properties
                ))

            relationships = []
            for r in data.get("relationships", []):
                relationships.append(Relationship(
                    id=str(uuid.uuid4()),
                    from_entity=r["from"], # Names for now, will map to IDs in ingestion
                    to_entity=r["to"],
                    rel_type=r["type"],
                    description=r.get("description", ""),
                    properties={"llm_extracted": True}
                ))

            logger.info(f"LLM extraction found {len(entities)} entities and {len(relationships)} relationships for doc {doc_id}")
            return entities, relationships

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON for doc {doc_id}: {e}")
            return [], []
        except Exception as e:
            logger.error(f"LLM extraction failed for doc {doc_id}: {e}")
            return [], []

    # ==================== PATTERN-BASED EXTRACTION FALLBACK ====================

    def _pattern_extract_entities_and_relationships(
        self, text: str, doc_id: str, source: str
    ) -> tuple[List[Entity], List[Relationship]]:
        """
        Extract entities using regex patterns when LLM is unavailable.
        """
        entities = []
        relationships = []
        entity_names = set()

        try:
            # 1. Email addresses
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            for match in re.finditer(email_pattern, text):
                email = match.group()
                if email not in entity_names:
                    entities.append(Entity(
                        id=str(uuid.uuid4()),
                        name=email,
                        entity_type="email",
                        description="Email address found in document",
                        properties={"source": source, "doc_id": doc_id, "pattern_extracted": True}
                    ))
                    entity_names.add(email)

            # 2. URLs
            url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))[^\s]*'
            for match in re.finditer(url_pattern, text):
                url = match.group()
                if url not in entity_names:
                    entities.append(Entity(
                        id=str(uuid.uuid4()),
                        name=url,
                        entity_type="url",
                        description="URL found in document",
                        properties={"source": source, "doc_id": doc_id, "pattern_extracted": True}
                    ))
                    entity_names.add(url)

            logger.info(f"Pattern extraction found {len(entities)} entities")

        except Exception as e:
            logger.error(f"Pattern extraction failed: {e}")

        return entities, relationships

    # ==================== INGESTION ORCHESTRATOR ====================

    async def ingest_document(self, workspace_id: str, doc_id: str, text: str, source: str = "unknown"):
        """
        Ingest raw text -> Extract -> Store in Postgres.

        Note: This method is now async due to LLMService.generate_completion being async.
        For backward compatibility, a sync wrapper can be added if needed.
        """

        # 1. Extract
        if self._is_llm_available(workspace_id):
            logger.info(f"Using LLM-based extraction for document {doc_id}")
            entities, relationships = await self._llm_extract_entities_and_relationships(text, doc_id, source, workspace_id)
        else:
            entities, relationships = self._pattern_extract_entities_and_relationships(text, doc_id, source)

        if not entities and not relationships:
            logger.info("No entities extracted.")
            return

        # 2. Store
        e_dicts = [{"name": e.name, "type": e.entity_type, "description": e.description, "properties": e.properties} for e in entities]
        r_dicts = [{"from": r.from_entity, "to": r.to_entity, "type": r.rel_type, "properties": r.properties} for r in relationships]
        
        self.ingest_structured_data(workspace_id, e_dicts, r_dicts)

    # ==================== WRITE OPERATIONS (SQL) ====================

    def add_entity(self, entity: Entity, workspace_id: str) -> str:
        """Upsert entity to Postgres"""
        with get_db_session() as session:
            try:
                # Anchoring Logic
                canonical_type = entity.properties.get('canonical_type')
                canonical_id = entity.properties.get('canonical_id')
                
                if canonical_type:
                    resolved_id = canonical_id or self._resolve_canonical_entity(session, workspace_id, entity.name, canonical_type)
                    
                    if not resolved_id:
                        created_id = self._create_canonical_entity_if_missing(session, workspace_id, entity.name, canonical_type)
                        if created_id:
                            entity.properties['canonical_id'] = created_id
                    else:
                        entity.properties['canonical_id'] = resolved_id
                        # Update DB record with metadata if applicable
                        registry = self._get_registry_entry(canonical_type, workspace_id)
                        if registry and registry.get("updatable_fields"):
                            model = registry["model"]
                            record = session.query(model).filter(model.id == resolved_id).first()
                            if record:
                                update_source = {"description": entity.description, **entity.properties}
                                update_data = self._sanitize_canonical_data(canonical_type, update_source)
                                for field in registry["updatable_fields"]:
                                    if field in update_data and update_data[field] is not None:
                                        setattr(record, field, update_data[field])

                existing = session.query(GraphNode).filter_by(
                    workspace_id=workspace_id, 
                    name=entity.name, 
                    type=entity.entity_type
                ).first()
                
                if existing:
                    existing.description = entity.description
                    existing.properties = entity.properties
                    entity.id = existing.id
                    is_new = False
                else:
                    is_new = True
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
                
                # Trigger Automation
                if AUTOMATION_AVAILABLE:
                    try:
                        asyncio.create_task(orchestrator.trigger_event("graph_entity_upsert", {
                            "entity_type": entity.entity_type,
                            "entity_id": entity.id,
                            "name": entity.name,
                            "is_new": is_new,
                            "tenant_id": workspace_id
                        }))
                    except Exception as trigger_err:
                        logger.warning(f"Failed to trigger automation: {trigger_err}")
                        
                return entity.id
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to add entity: {e}")
                return None

    def add_relationship(self, rel: Relationship, workspace_id: str) -> str:
        """Insert edge to Postgres"""
        with get_db_session() as session:
            try:
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

    def _get_entity_registry(self, workspace_id: Optional[str] = None):
        """Returns the dynamic Entity Factory Registry."""
        # Canonical entities (hardcoded)
        canonical_registry = {
            "user": {"model": User, "search_field": "email", "updatable_fields": ["first_name", "last_name", "specialty"]},
            "workspace": {"model": Workspace, "search_field": "name", "updatable_fields": ["description"]},
            "team": {"model": Team, "search_field": "name", "updatable_fields": ["description"]},
            "task": {"model": UserTask, "search_field": "title", "match_id": True, "updatable_fields": ["description", "status"]},
            "ticket": {"model": SupportTicket, "search_field": "subject", "match_id": True, "updatable_fields": ["status", "priority"]},
            "formula": {"model": Formula, "search_field": "name", "updatable_fields": ["expression", "description"]}
        }

        if workspace_id is None:
            return canonical_registry

        # Load custom entity types
        custom_types = self._load_custom_entity_types(workspace_id)
        return {**canonical_registry, **custom_types}

    def _load_custom_entity_types(self, workspace_id: str) -> Dict[str, Dict]:
        """Load custom types from database."""
        with get_db_session() as session:
            try:
                custom_types = session.query(EntityTypeDefinition).filter(
                    EntityTypeDefinition.tenant_id == workspace_id,
                    EntityTypeDefinition.is_active == True,
                    EntityTypeDefinition.is_system == False
                ).all()

                registry = {}
                for et in custom_types:
                    registry[et.slug] = {
                        "model": None,
                        "search_field": "name",
                        "is_custom": True,
                        "entity_type_id": str(et.id),
                        "display_name": et.display_name,
                        "json_schema": et.json_schema
                    }
                return registry
            except Exception as e:
                logger.error(f"Failed to load custom types: {e}")
                return {}

    def _get_registry_entry(self, canonical_type: str, workspace_id: Optional[str] = None):
        registry = self._get_entity_registry(workspace_id)
        if canonical_type in registry:
            entry = registry[canonical_type]
            if entry.get("is_custom"):
                return None
            return entry
        return None

    def _sanitize_canonical_data(self, canonical_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitizes input data based on entity type."""
        sanitized = {}
        for k, v in data.items():
            if isinstance(v, str):
                v = v.strip()
                if canonical_type.lower() == "user" and k == "email":
                    v = v.lower()
            sanitized[k] = v
        return sanitized

    def _create_canonical_entity_if_missing(self, session, workspace_id: str, name: str, canonical_type: str) -> Optional[str]:
        """Dynamically instantiates a SQL database record."""
        config = self._get_registry_entry(canonical_type, workspace_id)
        if not config or not config["model"]:
            return None
            
        model = config["model"]
        search_field = config["search_field"]
        
        try:
            init_kwargs = {}
            if hasattr(model, "workspace_id"):
                init_kwargs["workspace_id"] = workspace_id
            elif hasattr(model, "tenant_id"):
                init_kwargs["tenant_id"] = workspace_id
            
            init_kwargs[search_field] = name
            init_kwargs = self._sanitize_canonical_data(canonical_type, init_kwargs)
            
            new_record = model(**init_kwargs)
            session.add(new_record)
            session.commit()
            return new_record.id
        except Exception as e:
            session.rollback()
            logger.warning(f"Failed to auto-create SQL entity: {e}")
            return None

    def _resolve_canonical_entity(self, session, workspace_id: str, name: str, canonical_type: str) -> Optional[str]:
        """Resolve name to database record ID."""
        config = self._get_registry_entry(canonical_type, workspace_id)
        if not config or not config["model"]:
            return None
            
        model = config["model"]
        search_field = config["search_field"]
        search_term = f"%{name}%"
        
        try:
            query = session.query(model)
            if hasattr(model, "workspace_id"):
                query = query.filter(model.workspace_id == workspace_id)
            elif hasattr(model, "tenant_id"):
                query = query.filter(model.tenant_id == workspace_id)
                
            result = query.filter(getattr(model, search_field).ilike(search_term)).first()
            if not result and config.get("match_id"):
                result = query.filter(model.id == name).first()
                
            return result.id if result else None
        except Exception as e:
            logger.warning(f"Error resolving canonical entity: {e}")
        return None

    def ingest_structured_data(self, workspace_id: str, entities: List[Dict], relationships: List[Dict]):
        """Batch ingestion using session."""
        with get_db_session() as session:
            try:
                # 1. Process Nodes
                node_map = {} 
                for e_data in entities:
                    name = e_data.get("name")
                    if not name: continue
                    
                    properties = e_data.get("properties", {})
                    canonical_type = properties.get("canonical_type")
                    
                    if canonical_type:
                        canonical_id = self._resolve_canonical_entity(session, workspace_id, name, canonical_type)
                        if canonical_id:
                            properties["canonical_id"] = canonical_id

                    node = GraphNode(
                        workspace_id=workspace_id,
                        name=name,
                        type=e_data.get("type", "unknown"),
                        description=e_data.get("description", ""),
                        properties=properties
                    )
                    session.add(node)
                    session.flush() 
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
                logger.info(f"Ingested {len(entities)} nodes, {len(relationships)} edges.")
            except Exception as e:
                session.rollback()
                logger.error(f"Structured ingestion failed: {e}")

    # ==================== READ OPERATIONS (SQL) ====================

    def local_search(self, workspace_id: str, query: str, depth: int = 2) -> Dict[str, Any]:
        """Perform Local Search using Recursive CTE (BFS) with Bidirectional Traversal."""
        with get_db_session() as session:
            try:
                # 1. Find Start Nodes
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
                traversal_sql = text("""
                    WITH RECURSIVE traversal AS (
                        SELECT n.id, n.name, n.type, n.description, 0 as depth, ARRAY[n.id] as path
                        FROM graph_nodes n
                        WHERE n.id = ANY(:start_ids)
                        AND n.workspace_id = :ws_id
                        
                        UNION
                        
                        SELECT 
                            target.id, target.name, target.type, target.description, 
                            t.depth + 1,
                            t.path || target.id
                        FROM traversal t
                        JOIN graph_edges e ON (e.source_node_id = t.id OR e.target_node_id = t.id)
                        JOIN graph_nodes target ON (
                            CASE 
                                WHEN e.source_node_id = t.id THEN e.target_node_id = target.id
                                ELSE e.source_node_id = target.id
                            END
                        )
                        WHERE t.depth < :max_depth
                        AND e.workspace_id = :ws_id
                        AND target.workspace_id = :ws_id
                        AND NOT (target.id = ANY(t.path))
                    )
                    SELECT DISTINCT id, name, type, description, depth FROM traversal LIMIT 100;
                """)
                
                edges_sql = text("""
                    SELECT e.source_node_id, e.target_node_id, e.relationship_type, e.properties
                    FROM graph_edges e
                    WHERE (e.source_node_id = ANY(:node_ids) OR e.target_node_id = ANY(:node_ids))
                    AND e.workspace_id = :ws_id
                    LIMIT 50
                """)

                nodes_result = session.execute(traversal_sql, {
                    "start_ids": start_ids, 
                    "max_depth": depth,
                    "ws_id": workspace_id
                }).fetchall()
                
                found_node_ids = [n.id for n in nodes_result]
                edges_result = session.execute(edges_sql, {"node_ids": found_node_ids, "ws_id": workspace_id}).fetchall()
                
                entities = [{"id": str(n.id), "name": n.name, "type": n.type, "description": n.description} for n in nodes_result]
                relationships = [{"from": str(e.source_node_id), "to": str(e.target_node_id), "type": e.relationship_type} for e in edges_result]
                
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

    def global_search(self, workspace_id: str, query: str) -> Dict[str, Any]:
        """Global Search using Pre-computed Communities."""
        with get_db_session() as session:
            try:
                sql = text("""
                    SELECT id, summary, keywords, level
                    FROM graph_communities
                    WHERE workspace_id = :ws_id
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                communities = session.execute(sql, {"ws_id": workspace_id}).fetchall()
                
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
                    scored = [c.summary for c in communities[:3]]

                return {"mode": "global", "summaries": scored, "answer": " | ".join(scored)}
            except Exception as e:
                logger.error(f"Global search failed: {e}")
                return {"error": str(e)}

    def query(self, workspace_id: str, query: str, mode: str = "auto") -> Dict[str, Any]:
        """Unified query entry point."""
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
        
        entities = result.get("entities", [])
        rels = result.get("relationships", [])
        id_to_name = {e['id']: e['name'] for e in entities}
        
        context_lines = [f"Found {len(entities)} relevant entities:"]
        for e in entities[:15]:
            context_lines.append(f"- {e['name']} ({e['type']}): {e.get('description', '')}")
            
        context_lines.append("\nRelationships:")
        for r in rels[:25]:
            from_name = id_to_name.get(r['from'], r['from'])
            to_name = id_to_name.get(r['to'], r['to'])
            context_lines.append(f"- {from_name} -> {r['type']} -> {to_name}")
            
        return "\n".join(context_lines)

    def enqueue_reindex_job(self, workspace_id: str) -> bool:
        """Push re-index job to Redis queue."""
        redis_url = os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL")
        if not redis_url:
            return False
            
        try:
            import redis
            r = redis.from_url(redis_url)
            r.lpush("graph_reindex_jobs", workspace_id)
            return True
        except Exception:
            return False

# Global Instance
graphrag_engine = GraphRAGEngine()
