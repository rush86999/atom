"""
GraphRAG Engine - PostgreSQL Backed (V2)
Stateless Graph Traversal using Recursive CTEs.
Replaces previous in-memory implementation.
"""

from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set
import uuid
from sqlalchemy import text
from sqlalchemy.orm import Session

# Import Database
from core.database import engine, get_db_session
from core.models import (
    CommunityMembership, GraphCommunity, GraphEdge, GraphNode,
    User, Workspace, Team, SupportTicket, Formula, UserTask
)

# Import LLMService for unified LLM interactions
from core.llm_service import LLMService

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

# ==================== CANONICAL ENTITY REGISTRY ====================

ENTITY_REGISTRY = {
    "user": {
        "model": User,
        "search_fields": ["email", "first_name", "last_name"],
        "display_field": "email",
        "updatable_fields": ["first_name", "last_name", "specialty"]
    },
    "workspace": {
        "model": Workspace,
        "search_fields": ["name"],
        "display_field": "name",
        "updatable_fields": ["name", "description"]
    },
    "team": {
        "model": Team,
        "search_fields": ["name"],
        "display_field": "name",
        "updatable_fields": ["name", "description"]
    },
    "ticket": {
        "model": SupportTicket,
        "search_fields": ["subject"],
        "display_field": "subject",
        "updatable_fields": ["status", "priority"]
    },
    "formula": {
        "model": Formula,
        "search_fields": ["name"],
        "display_field": "name",
        "updatable_fields": ["expression", "description"]
    },
    "task": {
        "model": UserTask,
        "search_fields": ["title"],
        "display_field": "title",
        "updatable_fields": ["status", "priority", "description"]
    }
}

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
        self.llm_service = LLMService(workspace_id=workspace_id)

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
  "entities": [{{"name": "string", "type": "string", "description": "string"}}],
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
                entities.append(Entity(
                    id=str(uuid.uuid4()),
                    name=e["name"],
                    entity_type=e["type"],
                    description=e.get("description", ""),
                    properties={"source": source, "doc_id": doc_id, "llm_extracted": True}
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
        Falls back to pattern matching for common entity types.
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

            # 2. URLs / Web addresses
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

            # 3. Phone numbers (US format)
            # Matches: 555-123-4567, (555) 123-4567, 555.123.4567, etc.
            # Must not be preceded by digit (to avoid matching UUIDs)
            phone_pattern = r'(?<!\d)(?:\+?1[-.\s]?)?\(?:?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'
            for match in re.finditer(phone_pattern, text):
                phone = match.group()
                if phone not in entity_names:
                    entities.append(Entity(
                        id=str(uuid.uuid4()),
                        name=phone,
                        entity_type="phone",
                        description="Phone number found in document",
                        properties={"source": source, "doc_id": doc_id, "pattern_extracted": True}
                    ))
                    entity_names.add(phone)

            # 4. Dates (multiple formats)
            date_patterns = [
                r'\b\d{4}-\d{2}-\d{2}\b',  # ISO format: 2024-01-15
                r'\b\d{2}/\d{2}/\d{4}\b',  # US format: 01/15/2024
                r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]+\d{1,2}[,\\s]+\d{4}\b',  # Jan 15, 2024
            ]
            for date_pattern in date_patterns:
                for match in re.finditer(date_pattern, text, re.IGNORECASE):
                    date_str = match.group()
                    if date_str not in entity_names:
                        entities.append(Entity(
                            id=str(uuid.uuid4()),
                            name=date_str,
                            entity_type="date",
                            description="Date found in document",
                            properties={"source": source, "doc_id": doc_id, "pattern_extracted": True}
                        ))
                        entity_names.add(date_str)

            # 5. Currency amounts
            currency_pattern = r'\$[\d,]+(?:\.\d{2})?|\b\d+\.?\d*\s?(?:USD|EUR|GBP|dollars?|euros?|pounds?)\b'
            for match in re.finditer(currency_pattern, text, re.IGNORECASE):
                amount = match.group()
                if amount not in entity_names:
                    entities.append(Entity(
                        id=str(uuid.uuid4()),
                        name=amount,
                        entity_type="currency",
                        description="Currency amount found in document",
                        properties={"source": source, "doc_id": doc_id, "pattern_extracted": True}
                    ))
                    entity_names.add(amount)

            # 6. File paths (avoid matching URLs by excluding //)
            file_path_pattern = r'(?<![a-zA-Z])[/\\][\w\-._/\\]*\.[\w]{2,4}\b(?![^\s])'
            for match in re.finditer(file_path_pattern, text):
                path = match.group()
                # Skip if looks like part of a URL (starts with //)
                if path.startswith('//'):
                    continue
                if path not in entity_names and len(path) > 5:  # Avoid false positives
                    entities.append(Entity(
                        id=str(uuid.uuid4()),
                        name=path,
                        entity_type="file_path",
                        description="File path found in document",
                        properties={"source": source, "doc_id": doc_id, "pattern_extracted": True}
                    ))
                    entity_names.add(path)

            # 7. IP addresses
            ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
            for match in re.finditer(ip_pattern, text):
                ip = match.group()
                # Validate IP range
                if all(0 <= int(octet) <= 255 for octet in ip.split('.')):
                    if ip not in entity_names:
                        entities.append(Entity(
                            id=str(uuid.uuid4()),
                            name=ip,
                            entity_type="ip_address",
                            description="IP address found in document",
                            properties={"source": source, "doc_id": doc_id, "pattern_extracted": True}
                        ))
                        entity_names.add(ip)

            # 8. Hash/UUID patterns
            uuid_pattern = r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b'
            for match in re.finditer(uuid_pattern, text):
                uuid_str = match.group()
                if uuid_str not in entity_names:
                    entities.append(Entity(
                        id=str(uuid.uuid4()),
                        name=uuid_str,
                        entity_type="uuid",
                        description="UUID found in document",
                        properties={"source": source, "doc_id": doc_id, "pattern_extracted": True}
                    ))
                    entity_names.add(uuid_str)

            # 9. Simple relationships (e.g., "X is Y", "X works at Y")
            relationship_patterns = [
                (r'(\w+(?:\s+\w+)*)\s+(?:is|works at|employed by|belongs to)\s+(\w+(?:\s+\w+)*)', "affiliated_with"),
                (r'(\w+(?:\s+\w+)*)\s+(?:reports to|managed by)\s+(\w+(?:\s+\w+)*)', "reports_to"),
                (r'(\w+(?:\s+\w+)*)\s+(?:located in|based in|at)\s+(\w+(?:\s+\w+)*)', "located_in"),
            ]

            for pattern, rel_type in relationship_patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    from_entity = match.group(1).strip()
                    to_entity = match.group(2).strip()

                    # Only create relationship if both entities were found
                    if from_entity in entity_names and to_entity in entity_names:
                        relationships.append(Relationship(
                            id=str(uuid.uuid4()),
                            from_entity=from_entity,
                            to_entity=to_entity,
                            rel_type=rel_type,
                            description="Relationship extracted via pattern matching",
                            properties={"pattern_extracted": True}
                        ))

            logger.info(f"Pattern extraction found {len(entities)} entities and {len(relationships)} relationships")

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
            logger.warning(f"LLM unavailable for workspace {workspace_id}, using pattern-based fallback")
            entities, relationships = self._pattern_extract_entities_and_relationships(text, doc_id, source)

        if not entities and not relationships:
            logger.info("No entities extracted.")
            return

        # 2. Store (Using existing structured ingestion methods)
        # Convert dataclasses to dicts for ingest_structured_data
        e_dicts = [{"name": e.name, "type": e.entity_type, "description": e.description, "properties": e.properties} for e in entities]
        r_dicts = [{"from": r.from_entity, "to": r.to_entity, "type": r.rel_type, "properties": r.properties} for r in relationships]

        self.ingest_structured_data(workspace_id, e_dicts, r_dicts)

    # ==================== WRITE OPERATIONS (SQL) ====================

    def add_entity(self, entity: Entity, workspace_id: str) -> str:
        """Upsert entity to Postgres"""
        with get_db_session() as session:
            try:
                # Check existence first (or use ON CONFLICT in raw SQL)
                # Using ORM for clarity, though bulk raw SQL is faster for mass ingestion
                
                # CANONICAL ANCHORING LOGIC
                canonical_type = entity.properties.get("canonical_type")
                canonical_id = entity.properties.get("canonical_id")
                
                db_record = None
                if canonical_type:
                    db_record = self._resolve_canonical_entity(
                        session, workspace_id, canonical_type, entity.name, canonical_id
                    )
                    
                    if db_record:
                        # Anchor the entity to the concrete ID
                        entity.properties["anchor_id"] = str(db_record.id)
                        entity.properties["anchor_type"] = canonical_type
                        
                        # BIDIRECTIONAL SYNC: Update the DB record with metadata from Graph UI if applicable
                        registry = self._get_registry_entry(canonical_type)
                        if registry:
                            update_data = self._sanitize_canonical_data(registry, entity.properties)
                            if update_data:
                                for k, v in update_data.items():
                                    setattr(db_record, k, v)
                                logger.info(f"Synced {len(update_data)} fields back to {canonical_type} {db_record.id}")

                existing = session.query(GraphNode).filter_by(
                    workspace_id=workspace_id,
                    name=entity.name,
                    type=entity.entity_type
                ).first()

                if existing:
                    # Update properties and metadata
                    existing.description = entity.description
                    
                    # Merge properties
                    merged_props = (existing.properties or {}).copy()
                    merged_props.update(entity.properties)
                    existing.properties = merged_props
                    
                    existing.updated_at = datetime.utcnow()
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
        with get_db_session() as session:
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
        with get_db_session() as session:
            try:
                # 1. Process Nodes
                node_map = {} # Name -> ID
                for e_data in entities:
                    name = e_data.get("name")
                    if not name: continue

                    # Deduplicate by name/type per workspace
                    existing = session.query(GraphNode).filter_by(
                        workspace_id=workspace_id,
                        name=name,
                        type=e_data.get("type", "unknown")
                    ).first()

                    if existing:
                        node_map[name] = existing.id
                        continue

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
                        # Optional: Deduplicate edges too
                        existing_edge = session.query(GraphEdge).filter_by(
                            workspace_id=workspace_id,
                            source_node_id=src,
                            target_node_id=dst,
                            relationship_type=r_data.get("type", "related_to")
                        ).first()
                        
                        if existing_edge:
                            continue

                        edge = GraphEdge(
                            workspace_id=workspace_id,
                            source_node_id=src,
                            target_node_id=dst,
                            relationship_type=r_data.get("type", "related_to"),
                            properties=r_data.get("properties", {})
                        )
                        session.add(edge)

                session.commit()
                logger.info(f"Ingested {len(entities)} nodes, {len(relationships)} edges to Postgres (with deduplication)")
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
        with get_db_session() as session:
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
        with get_db_session() as session:
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
