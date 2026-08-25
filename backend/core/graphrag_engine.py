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
from datetime import datetime, timezone
from sqlalchemy import text, func
from sqlalchemy.exc import OperationalError
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
    from advanced_workflow_orchestrator import get_orchestrator
    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False
    logger.warning("Workflow automation integration unavailable")

orchestrator: Optional[Any] = None


def _get_workflow_orchestrator() -> Any:
    """Lazily resolve the workflow orchestrator singleton.

    The old `from advanced_workflow_orchestrator import orchestrator` could
    never succeed (that module exports get_orchestrator, not a bare name),
    so the ImportError was silently swallowed and AUTOMATION_AVAILABLE stayed
    False — graph_entity_upsert events never fired. Resolution is deferred to
    call time because the constructor touches the database.
    """
    global orchestrator
    if orchestrator is None:
        orchestrator = get_orchestrator()
    return orchestrator

# ==================== CONFIGURATION ====================

GRAPHRAG_LLM_ENABLED = os.getenv("GRAPHRAG_LLM_ENABLED", "true").lower() == "true"
GRAPHRAG_LLM_PROVIDER = os.getenv("GRAPHRAG_LLM_PROVIDER", "openai")
GRAPHRAG_LLM_MODEL = os.getenv("GRAPHRAG_LLM_MODEL", "gpt-4o-mini")


def _ontology_enforcement_strict() -> bool:
    """ATOM_ONTOLOGY_ENFORCEMENT=strict rejects ontology-violating edges at
    write time; the default 'warn' mode writes them flagged."""
    return os.getenv("ATOM_ONTOLOGY_ENFORCEMENT", "warn").strip().lower() == "strict"

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
    def __init__(self, workspace_id: Optional[str] = None, tenant_id: Optional[str] = None, db: Optional[Session] = None):
        """
        Initialize GraphRAG Engine.

        Args:
            workspace_id: Workspace identifier for multi-tenant isolation
            tenant_id: Tenant identifier for SaaS compatibility
            db: Optional database session
        """
        self.workspace_id = workspace_id or "default"
        self.tenant_id = tenant_id or "default"
        self.db = db
        # Strong refs for fire-and-forget automation triggers (prevent GC).
        self._bg_tasks: set = set()
        # Initialize LLMService for unified LLM interactions
        self.llm_service = LLMService(
            workspace_id=self.workspace_id,
            tenant_id=self.tenant_id,
            db=db
        )

    def get_stats(self, user_id: str = None) -> Dict[str, Any]:
        """Return basic GraphRAG engine statistics.

        The engine does not maintain an in-memory graph count; this returns
        engine metadata so the /stats endpoint responds meaningfully instead
        of crashing with AttributeError.
        """
        return {
            "workspace_id": self.workspace_id,
            "tenant_id": self.tenant_id,
            "status": "initialized",
            "nodes": 0,
            "edges": 0,
            "entities": 0,
        }

    def _validate_search_input(self, name: str, max_length: int = 500) -> str:
        """
        Validate and sanitize search input.

        Args:
            name: User input search term
            max_length: Maximum allowed length (default 500)

        Returns:
            Sanitized search term

        Raises:
            ValueError: If input is too long or contains invalid characters
        """
        if not name:
            return ""

        if len(name) > max_length:
            raise ValueError(
                f"Search term too long: {len(name)} characters (max {max_length}). "
                "This could cause performance issues or be a DoS attempt."
            )

        # Remove any control characters (except tab, newline for readability)
        # This prevents potential injection through control characters
        cleaned = ''.join(char for char in name if ord(char) >= 32 or char in ['\t', '\n', '\r'])

        return cleaned

    def _escape_like_pattern(self, pattern: str) -> str:
        """
        Escape SQL LIKE special characters in search pattern.

        Args:
            pattern: Search pattern that may contain % or _

        Returns:
            Escaped pattern where % and _ are escaped to \%

        Examples:
            "test%" -> "test\\%"
            "user_data" -> "user_data"
            "50%" -> "50\\%"
        """
        # In SQL LIKE, % matches any sequence and _ matches any single character
        # We escape them so users can search for literal % and _
        return pattern.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')

    def canonical_search(self, workspace_id: Optional[str] = None, tenant_id: Optional[str] = None,
                         entity_type: str = "unknown", query: str = "") -> List[Dict]:
        """Search for canonical records to anchor graph nodes."""
        ws_id = workspace_id or self.workspace_id
        tid = tenant_id or self.tenant_id

        registry = self._get_registry_entry(entity_type)
        if not registry:
            return []

        model = registry["model"]
        # Registry entries define the singular "search_field" key; fall back
        # to it when the plural "search_fields" list is absent.
        search_fields = registry.get("search_fields") or [registry.get("search_field", "name")]
        display_field = registry.get("display_field") or registry.get("search_field", "name")

        # BUG FIX: Validate and sanitize input before using in queries
        query = self._validate_search_input(query)

        with get_db_session() as session:
            try:
                # Use a combined OR filter for all search fields
                from sqlalchemy import or_
                # BUG FIX: Escape LIKE special characters to prevent wildcard injection
                escaped_query = self._escape_like_pattern(query)
                # Some models define Python properties (e.g. User.name) that are
                # not columns and cannot be used in .ilike() expressions; only
                # include real column attributes.
                filters = []
                for f_name in search_fields:
                    attr = getattr(model, f_name)
                    if isinstance(attr, property):
                        continue
                    filters.append(attr.ilike(f"%{escaped_query}%"))
                if not filters:
                    attr = getattr(model, registry.get("search_field", "name"))
                    if not isinstance(attr, property):
                        filters.append(attr.ilike(f"%{escaped_query}%"))
                if not filters:
                    return []

                # Check for tenant/workspace isolation if the model has a column for it
                # In personal edition, some models might not have workspace_id but use other links
                # For simplicity, we'll try to find workspace_id or tenant_id
                query_obj = session.query(model).filter(or_(*filters))

                if hasattr(model, 'workspace_id'):
                    query_obj = query_obj.filter(model.workspace_id == ws_id)
                elif hasattr(model, 'tenant_id'):
                    query_obj = query_obj.filter(model.tenant_id == tid)

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
        Extract entities and relationships using centralized KnowledgeExtractor.
        """
        try:
            from core.service_factory import ServiceFactory
            extractor = ServiceFactory.get_knowledge_extractor(
                workspace_id=workspace_id,
                tenant_id=self.tenant_id
            )
            extracted_data = await extractor.extract_knowledge(
                text,
                workspace_id=workspace_id,
                tenant_id=self.tenant_id,
                source=source
            )

            entities = []
            for e in extracted_data.get("entities", []):
                # Map raw extracted properties to Entity dataclass
                # Handle potential nested 'properties' or flattened structure
                props = e.get("properties", {})
                name = e.get("name") or props.get("name", "Unknown")
                e_type = e.get("type") or props.get("type", "unknown")
                desc = e.get("description") or props.get("description", "")

                # Enrich with source info if not already there
                if "source" not in props: props["source"] = source
                if "doc_id" not in props: props["doc_id"] = doc_id
                props["llm_extracted"] = True
                # Keep the LLM's own entity id so ingest_document can remap
                # relationship endpoints (which reference these ids) to names.
                if e.get("id"):
                    props["extractor_id"] = str(e["id"])

                entities.append(Entity(
                    id=str(uuid.uuid4()),
                    name=name,
                    entity_type=e_type,
                    description=desc,
                    properties=props
                ))

            relationships = []
            for r in extracted_data.get("relationships", []):
                relationships.append(Relationship(
                    id=str(uuid.uuid4()),
                    from_entity=r.get("from"),
                    to_entity=r.get("to"),
                    rel_type=r.get("type", "related_to"),
                    description=r.get("description", ""),
                    properties=r.get("properties", {"llm_extracted": True})
                ))

            logger.info(f"Unified extraction found {len(entities)} entities and {len(relationships)} relationships for doc {doc_id}")
            return entities, relationships
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
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

            # 3. Phone numbers (US format: 555-123-4567, (555) 123-4567, 5551234567)
            phone_pattern = r'(?:\(\d{3}\)\s*|\b\d{3}[-.]?)\d{3}[-.]?\d{4}\b'
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

            # 4. Dates (ISO format: YYYY-MM-DD)
            iso_date_pattern = r'\b\d{4}-\d{2}-\d{2}\b'
            for match in re.finditer(iso_date_pattern, text):
                date = match.group()
                if date not in entity_names:
                    entities.append(Entity(
                        id=str(uuid.uuid4()),
                        name=date,
                        entity_type="date",
                        description="ISO date found in document",
                        properties={"source": source, "doc_id": doc_id, "pattern_extracted": True}
                    ))
                    entity_names.add(date)

            # 5. Dates (US format: MM/DD/YYYY)
            us_date_pattern = r'\b\d{2}/\d{2}/\d{4}\b'
            for match in re.finditer(us_date_pattern, text):
                date = match.group()
                if date not in entity_names:
                    entities.append(Entity(
                        id=str(uuid.uuid4()),
                        name=date,
                        entity_type="date",
                        description="US format date found in document",
                        properties={"source": source, "doc_id": doc_id, "pattern_extracted": True}
                    ))
                    entity_names.add(date)

            # 6. Dates (Textual: Jan 15, 2024)
            textual_date_pattern = r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b'
            for match in re.finditer(textual_date_pattern, text):
                date = match.group()
                if date not in entity_names:
                    entities.append(Entity(
                        id=str(uuid.uuid4()),
                        name=date,
                        entity_type="date",
                        description="Textual date found in document",
                        properties={"source": source, "doc_id": doc_id, "pattern_extracted": True}
                    ))
                    entity_names.add(date)

            # 7. Currency amounts ($99.99, $1,234.56, 100 USD)
            currency_pattern = (
                r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?'      # $dollars with optional thousands + cents
                r'|\b\d+(?:\.\d+)?\s*(?:USD|EUR|GBP|JPY|CAD|AUD|CNY|INR|CHF)\b'  # ISO 4217 codes
            )
            for match in re.finditer(currency_pattern, text):
                currency = match.group()
                if currency not in entity_names:
                    entities.append(Entity(
                        id=str(uuid.uuid4()),
                        name=currency,
                        entity_type="currency",
                        description="Currency amount found in document",
                        properties={"source": source, "doc_id": doc_id, "pattern_extracted": True}
                    ))
                    entity_names.add(currency)

            # 8. File paths (/path/to/file.txt)
            # Negative lookbehind avoids matching URL substrings (e.g. the
            # '//example.com' inside 'http://example.com'). Pre-existing
            # behavior requires a file extension (the (?:\.\w+) tail).
            file_path_pattern = r'(?<![:/\w])[/\\][\w\-./]+(?:\.\w+)'
            for match in re.finditer(file_path_pattern, text):
                path = match.group()
                if path not in entity_names:
                    entities.append(Entity(
                        id=str(uuid.uuid4()),
                        name=path,
                        entity_type="file_path",
                        description="File path found in document",
                        properties={"source": source, "doc_id": doc_id, "pattern_extracted": True}
                    ))
                    entity_names.add(path)

            # 9. IP addresses (192.168.1.1) — octets validated to 0-255
            # so 999.999.999.999 is correctly rejected.
            ip_pattern = (
                r'\b(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)'
                r'(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}\b'
            )
            for match in re.finditer(ip_pattern, text):
                ip = match.group()
                if ip not in entity_names:
                    entities.append(Entity(
                        id=str(uuid.uuid4()),
                        name=ip,
                        entity_type="ip_address",
                        description="IP address found in document",
                        properties={"source": source, "doc_id": doc_id, "pattern_extracted": True}
                    ))
                    entity_names.add(ip)

            # 10. UUIDs (550e8400-e29b-41d4-a716-446655440000)
            uuid_pattern = r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b'
            for match in re.finditer(uuid_pattern, text):
                uuid_val = match.group()
                if uuid_val not in entity_names:
                    entities.append(Entity(
                        id=str(uuid.uuid4()),
                        name=uuid_val,
                        entity_type="uuid",
                        description="UUID found in document",
                        properties={"source": source, "doc_id": doc_id, "pattern_extracted": True}
                    ))
                    entity_names.add(uuid_val)

            logger.info(f"Pattern extraction found {len(entities)} entities")

        except Exception as e:
            logger.error(f"Pattern extraction failed: {e}")

        return entities, relationships

    # ==================== INGESTION ORCHESTRATOR ====================

    async def ingest_document(self, workspace_id: Optional[str] = None,
                             tenant_id: Optional[str] = None,
                             doc_id: str = "unknown", text: str = "", source: str = "unknown",
                             sensitivity: str = "internal"):
        """
        Ingest raw text -> Extract -> Store in Postgres.

        ``sensitivity`` (P4 ladder: public|internal|confidential|restricted)
        propagates to every node extracted from this document — taint rule:
        a node is as restricted as the most restrictive doc that mentions it.
        """
        ws_id = workspace_id or self.workspace_id
        tid = tenant_id or self.tenant_id

        # A3 (chunk grounding): chunk the document once so every extracted
        # entity/edge carries supporting chunk references — the relational
        # equivalent of RDF 1.2 rdf:reifies statement provenance. Research
        # (arXiv 2511.05991): chunk-in-node grounding was the decisive
        # accuracy factor (15-20% -> 90%).
        chunks = []
        try:
            from core.ontology.chunker import chunk_text, locate_name_chunks
            chunks = chunk_text(text)
        except Exception as chunk_err:
            logger.debug(f"chunking skipped: {chunk_err}")

        # 1. Extract
        if self._is_llm_available(ws_id):
            logger.info(f"Using LLM-based extraction for document {doc_id}")
            entities, relationships = await self._llm_extract_entities_and_relationships(text, doc_id, source, ws_id)
        else:
            entities, relationships = self._pattern_extract_entities_and_relationships(text, doc_id, source)

        if not entities and not relationships:
            logger.info("No entities extracted.")
            return {"entities": 0, "relationships": 0}

        # Attach chunk provenance to entities (substring match is cheap and
        # deterministic; misses are simply empty provenance, not errors).
        entity_chunk_ids: Dict[str, List[int]] = {}
        if chunks:
            try:
                for e in entities:
                    hit_ids = locate_name_chunks(e.name, chunks)
                    entity_chunk_ids[e.name] = hit_ids
                    if hit_ids:
                        e.properties["provenance"] = {
                            "doc_id": doc_id,
                            "source": source,
                            "chunk_ids": hit_ids,
                        }
            except Exception as prov_err:
                logger.debug(f"provenance attach skipped: {prov_err}")

        # Remap relationship endpoints from extractor ids to entity names —
        # ingest_structured_data keys its node map by name, and the LLM
        # references entities by its own ids (edges silently missed before).
        extractor_id_to_name = {
            e.properties.get("extractor_id"): e.name
            for e in entities if e.properties.get("extractor_id")
        }
        if extractor_id_to_name:
            for r in relationships:
                r.from_entity = extractor_id_to_name.get(r.from_entity, r.from_entity)
                r.to_entity = extractor_id_to_name.get(r.to_entity, r.to_entity)

        # Edge provenance: union of endpoint chunk references.
        if chunks:
            for r in relationships:
                endpoint_chunks = sorted(
                    set(entity_chunk_ids.get(r.from_entity, [])
                        + entity_chunk_ids.get(r.to_entity, []))
                )
                if endpoint_chunks:
                    props = dict(r.properties or {})
                    props.setdefault("provenance", {})["doc_id"] = doc_id
                    props["provenance"]["chunk_ids"] = endpoint_chunks[:10]
                    r.properties = props

        # 2. Store — surface the stats so callers (hybrid ingestion sync
        # results) report real extraction counts instead of always 0.
        e_dicts = [{"name": e.name, "type": e.entity_type, "description": e.description, "properties": e.properties, "sensitivity": sensitivity} for e in entities]
        r_dicts = [{"from": r.from_entity, "to": r.to_entity, "type": r.rel_type, "properties": r.properties} for r in relationships]
        return self.ingest_structured_data(ws_id, tid, e_dicts, r_dicts)

    @staticmethod
    def _raise_sensitivity(current: Optional[str], incoming: Optional[str]) -> str:
        """Return the more restrictive of two P4 classifications (never lowers)."""
        from core.org_data_bundle_service import SENSITIVITY_LADDER
        cur = current if current in SENSITIVITY_LADDER else "internal"
        inc = incoming if incoming in SENSITIVITY_LADDER else "internal"
        return max(cur, inc, key=SENSITIVITY_LADDER.index)

    # ==================== WRITE OPERATIONS (SQL) ====================

    def add_entity(self, entity: Entity, workspace_id: Optional[str] = None, 
                   tenant_id: Optional[str] = None) -> str:
        """Upsert entity to Postgres"""
        ws_id = workspace_id or self.workspace_id
        tid = tenant_id or self.tenant_id
        
        with get_db_session() as session:
            try:
                # Anchoring Logic
                canonical_type = entity.properties.get('canonical_type')
                canonical_id = entity.properties.get('canonical_id')
                
                if canonical_type:
                    resolved_id = canonical_id or self._resolve_canonical_entity(session, ws_id, entity.name, canonical_type)
                    
                    if not resolved_id:
                        created_id = self._create_canonical_entity_if_missing(session, ws_id, entity.name, canonical_type)
                        if created_id:
                            entity.properties['canonical_id'] = created_id
                    else:
                        entity.properties['canonical_id'] = resolved_id
                        # Update DB record with metadata if applicable
                        registry = self._get_registry_entry(canonical_type, ws_id)
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
                    workspace_id=ws_id, 
                    name=entity.name, 
                    type=entity.entity_type
                ).first()
                
                properties_copy = dict(entity.properties)
                embedding_val = properties_copy.pop("embedding", None)
                
                if existing:
                    existing.description = entity.description
                    existing.properties = properties_copy
                    if embedding_val is not None:
                        existing.embedding = embedding_val
                    entity.id = existing.id
                    is_new = False
                else:
                    is_new = True
                    node = GraphNode(
                        id=entity.id,
                        tenant_id=tid,
                        workspace_id=ws_id,
                        name=entity.name,
                        type=entity.entity_type,
                        description=entity.description,
                        properties=properties_copy,
                        embedding=embedding_val
                    )
                    session.add(node)
                    
                session.commit()

                # Vector index (P1.5): mirror the node into the LanceDB
                # graph_nodes table so local_search's vector leg works on
                # SQLite (the pgvector leg only ever ran on Postgres).
                self._index_node_vector(entity.id, entity.name, entity.entity_type, entity.description, ws_id)

                # Trigger Automation. Keep a strong ref so the task isn't
                # GC'd before the event fires.
                if AUTOMATION_AVAILABLE:
                    try:
                        _t = asyncio.create_task(_get_workflow_orchestrator().trigger_event("graph_entity_upsert", {
                            "entity_type": entity.entity_type,
                            "entity_id": entity.id,
                            "name": entity.name,
                            "is_new": is_new,
                            "workspace_id": ws_id,
                            "tenant_id": tid
                        }))
                        self._bg_tasks.add(_t)
                        _t.add_done_callback(self._bg_tasks.discard)
                    except Exception as trigger_err:
                        logger.warning(f"Failed to trigger automation: {trigger_err}")
                        
                return entity.id
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to add entity: {e}")
                return None

    def add_relationship(self, rel: Relationship, workspace_id: Optional[str] = None, 
                         tenant_id: Optional[str] = None) -> str:
        """Insert edge to Postgres"""
        ws_id = workspace_id or self.workspace_id
        tid = tenant_id or self.tenant_id or "default"
        
        with get_db_session() as session:
            try:
                # Bug #12: verify both endpoint nodes exist before inserting the
                # edge — prevents orphaned relationships that pollute traversals.
                # Endpoints may be node IDs OR names: the batch ingestion path
                # (ingest_document et al.) remaps relationship endpoints to
                # entity NAMES, so an id-only lookup made every external
                # add_relationship call from those producers fail with
                # "source node not found".
                from sqlalchemy import or_

                from core.models import GraphNode

                def _find_node(endpoint: str):
                    return (
                        session.query(GraphNode)
                        .filter(
                            or_(GraphNode.id == endpoint, GraphNode.name == endpoint),
                            GraphNode.workspace_id == ws_id,
                        )
                        .first()
                    )

                src = _find_node(rel.from_entity)
                tgt = _find_node(rel.to_entity)
                if not src:
                    logger.warning(f"add_relationship: source node '{rel.from_entity}' not found — skipping")
                    return None
                if not tgt:
                    logger.warning(f"add_relationship: target node '{rel.to_entity}' not found — skipping")
                    return None

                props = dict(rel.properties or {})
                now_iso = datetime.now(timezone.utc).isoformat()

                # Ontology validation (A1/A4) on the manual write path too.
                try:
                    from core.ontology import get_ontology_service
                    validation = get_ontology_service(tid).validate_relationship(
                        src.type, rel.rel_type, tgt.type)
                    if not validation.ok:
                        if _ontology_enforcement_strict():
                            logger.warning(f"edge rejected ({validation.reason})")
                            return None
                        props["ontology_violation"] = validation.reason
                    elif not validation.declared:
                        props["ontology_undeclared_relation"] = True
                except Exception as onto_err:
                    logger.debug(f"ontology validation skipped: {onto_err}")

                # Dedup with occurrence counts (A5) — same triple upserts.
                # Resolve to the found nodes' canonical IDs (endpoints may
                # have been passed as names).
                existing_edge = session.query(GraphEdge).filter(
                    GraphEdge.workspace_id == ws_id,
                    GraphEdge.source_node_id == src.id,
                    GraphEdge.target_node_id == tgt.id,
                    GraphEdge.relationship_type == rel.rel_type,
                ).first()
                if existing_edge:
                    ep = dict(existing_edge.properties or {})
                    ep["occurrence_count"] = int(ep.get("occurrence_count", 1)) + 1
                    ep["last_seen"] = now_iso
                    ep.update({k: v for k, v in props.items()
                               if k not in ("occurrence_count", "last_seen")})
                    existing_edge.properties = ep
                    existing_edge.weight = (existing_edge.weight or 1.0) + 1.0
                    session.commit()
                    return existing_edge.id

                props.setdefault("verification", "proposed")
                props.setdefault("occurrence_count", 1)
                props["first_seen"] = now_iso
                props["last_seen"] = now_iso
                edge = GraphEdge(
                    id=rel.id,
                    tenant_id=tid,
                    workspace_id=ws_id,
                    source_node_id=src.id,
                    target_node_id=tgt.id,
                    relationship_type=rel.rel_type,
                    properties=props
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

        # BUG FIX: Validate and sanitize input before using in queries
        name = self._validate_search_input(name)
        # BUG FIX: Escape LIKE special characters to prevent wildcard injection
        escaped_name = self._escape_like_pattern(name)
        search_term = f"%{escaped_name}%"

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

    def ingest_structured_data(self, workspace_id: Optional[str] = None, 
                              tenant_id: Optional[str] = None,
                              entities: List[Dict] = [], relationships: List[Dict] = []):
        """Batch ingestion using session."""
        ws_id = workspace_id or self.workspace_id
        tid = tenant_id or self.tenant_id or "default"
        
        with get_db_session() as session:
            try:
                # Ontology layer (A1/A2/A4): validation + alias resolution.
                onto = None
                try:
                    from core.ontology import get_ontology_service
                    onto = get_ontology_service(tid)
                except Exception as onto_err:
                    logger.debug(f"ontology layer unavailable: {onto_err}")

                # 1. Process Nodes
                node_map = {}
                node_types: Dict[str, str] = {}
                for e_data in entities:
                    if not isinstance(e_data, dict):
                        # Tolerate Entity/Relationship-style dataclasses from
                        # producers like historical_sync (their attributes map
                        # 1:1; passing them raw used to raise AttributeError
                        # inside the catch-all and silently drop the batch).
                        e_data = {
                            "name": getattr(e_data, "name", None),
                            "type": getattr(e_data, "entity_type", None) or getattr(e_data, "type", None),
                            "description": getattr(e_data, "description", "") or "",
                            "properties": getattr(e_data, "properties", None) or {},
                            "id": getattr(e_data, "id", None),
                        }
                    name = e_data.get("name")
                    if not name:
                        # Some producers (LLM extractor) nest the name in
                        # properties — fall back rather than skip.
                        _p0 = e_data.get("properties") or {}
                        name = _p0.get("name") or _p0.get("display_name") or _p0.get("title")
                    if not name: continue

                    properties = e_data.get("properties", {})
                    canonical_type = properties.get("canonical_type")

                    if canonical_type:
                        canonical_id = self._resolve_canonical_entity(session, ws_id, name, canonical_type)
                        if canonical_id:
                            properties["canonical_id"] = canonical_id

                    properties_copy = dict(properties)
                    embedding_val = properties_copy.pop("embedding", None)
                    sensitivity = e_data.get("sensitivity")
                    node_type = e_data.get("type", "unknown")
                    # A2/A5: canonicalize the type label through the ontology
                    # (alias resolution — "org" == "Organization") so upserts
                    # dedupe across alias spellings. R84: integration record
                    # types (crm_leads, books_invoices, onedrive_file …) map
                    # through the ontology bridge when the raw label isn't
                    # already resolvable — one funnel, every producer.
                    resolved = onto.resolve_entity_type(node_type) if onto else None
                    if not resolved:
                        try:
                            from core.integration_ontology_bridge import (
                                map_record_type,
                                type_map_enabled,
                            )
                            if type_map_enabled():
                                resolved = map_record_type(node_type)
                        except Exception:  # noqa: BLE001 — mapping must never block ingestion
                            resolved = None
                    if resolved:
                        node_type = resolved

                    # Upsert on (workspace, name, type): re-ingesting the same
                    # entity (or importing an org bundle) must merge, not
                    # duplicate. Sensitivity taint rule: never lowered.
                    # A5: alias-aware match — case-insensitive name, plus
                    # previously recorded also_known_as aliases on the node.
                    existing = self._find_existing_node(session, ws_id, name, node_type)
                    if existing:
                        existing.description = e_data.get("description", "") or existing.description
                        merged_props = dict(existing.properties or {})
                        merged_props.update(properties_copy)
                        # merge chunk provenance instead of overwriting
                        new_prov = properties_copy.get("provenance")
                        if new_prov:
                            old_prov = (existing.properties or {}).get("provenance") or {}
                            merged_ids = list(dict.fromkeys(
                                old_prov.get("chunk_ids", []) + new_prov.get("chunk_ids", [])))
                            new_prov["chunk_ids"] = merged_ids[:50]
                            merged_props["provenance"] = new_prov
                        existing.properties = merged_props
                        if embedding_val is not None:
                            existing.embedding = embedding_val
                        existing.sensitivity = self._raise_sensitivity(existing.sensitivity, sensitivity)
                        session.flush()
                        node_map[name] = existing.id
                        node_types[existing.id] = existing.type
                        # Alias the producer's entity id (if any) so
                        # id-keyed relationship endpoints resolve to this
                        # node too (names stay authoritative on collision).
                        _alias = e_data.get("id")
                        if _alias and str(_alias) not in node_map:
                            node_map[str(_alias)] = existing.id
                        continue

                    node = GraphNode(
                        tenant_id=tid,
                        workspace_id=ws_id,
                        name=name,
                        type=node_type,
                        description=e_data.get("description", ""),
                        properties=properties_copy,
                        embedding=embedding_val,
                        sensitivity=self._raise_sensitivity("internal", sensitivity),
                    )
                    session.add(node)
                    session.flush()
                    node_map[name] = node.id
                    node_types[node.id] = node.type
                    # See the existing-node branch: alias producer ids.
                    _alias = e_data.get("id")
                    if _alias and str(_alias) not in node_map:
                        node_map[str(_alias)] = node.id

                # 2. Process Edges (A1/A4/A6: ontology validation, dedup with
                # occurrence counts, hypothesis verification states)
                skipped_violations = 0
                for r_data in relationships:
                    if not isinstance(r_data, dict):
                        r_data = {
                            "from": getattr(r_data, "from_entity", None),
                            "to": getattr(r_data, "to_entity", None),
                            "type": getattr(r_data, "rel_type", None) or getattr(r_data, "type", None),
                            "properties": getattr(r_data, "properties", None) or {},
                        }
                    src = node_map.get(r_data.get("from"))
                    dst = node_map.get(r_data.get("to"))
                    if not (src and dst):
                        continue
                    rel_type = r_data.get("type", "related_to")
                    props = dict(r_data.get("properties", {}) or {})

                    if onto:
                        validation = onto.validate_relationship(
                            node_types.get(src, "unknown"), rel_type,
                            node_types.get(dst, "unknown"))
                        if not validation.ok:
                            if _ontology_enforcement_strict():
                                skipped_violations += 1
                                logger.warning(
                                    f"edge rejected ({validation.reason}): "
                                    f"{src} -[{rel_type}]-> {dst}")
                                continue
                            props["ontology_violation"] = validation.reason
                        elif not validation.declared:
                            props["ontology_undeclared_relation"] = True

                    now_iso = datetime.now(timezone.utc).isoformat()
                    confidence = props.get("confidence")

                    existing_edge = session.query(GraphEdge).filter(
                        GraphEdge.workspace_id == ws_id,
                        GraphEdge.source_node_id == src,
                        GraphEdge.target_node_id == dst,
                        GraphEdge.relationship_type == rel_type,
                    ).first()
                    if existing_edge:
                        # Dedup: repeated observations strengthen (occurrence
                        # count + weight) instead of duplicating rows.
                        ep = dict(existing_edge.properties or {})
                        ep["occurrence_count"] = int(ep.get("occurrence_count", 1)) + 1
                        ep["last_seen"] = now_iso
                        if confidence is not None:
                            ep["confidence"] = max(float(confidence),
                                                   float(ep.get("confidence", 0)))
                        new_prov = props.get("provenance")
                        if new_prov:
                            old_prov = ep.get("provenance") or {}
                            merged = list(dict.fromkeys(
                                old_prov.get("chunk_ids", []) + new_prov.get("chunk_ids", [])))
                            new_prov["chunk_ids"] = merged[:50]
                            ep["provenance"] = new_prov
                        ep.update({k: v for k, v in props.items()
                                   if k not in ("provenance", "occurrence_count",
                                                "last_seen", "confidence")})
                        existing_edge.properties = ep
                        existing_edge.weight = (existing_edge.weight or 1.0) + 1.0
                    else:
                        # A6 hypothesis lifecycle: extracted facts land as
                        # 'proposed'; promotion to 'verified' is an explicit
                        # act (human review / corroborating source).
                        props.setdefault("verification", "proposed")
                        props.setdefault("occurrence_count", 1)
                        props["first_seen"] = now_iso
                        props["last_seen"] = now_iso
                        edge = GraphEdge(
                            tenant_id=tid,
                            workspace_id=ws_id,
                            source_node_id=src,
                            target_node_id=dst,
                            relationship_type=rel_type,
                            properties=props,
                            # Bi-temporal (P2.2): new facts are valid from now
                            valid_from=datetime.utcnow(),
                        )
                        session.add(edge)

                session.commit()
                # A8 (incremental versioning): snapshot the graph every N
                # ingests via the previously-unwired DynamicGraphManager.
                self._maybe_snapshot_version(ws_id)
                logger.info(
                    f"Ingested {len(entities)} nodes, {len(relationships)} edges"
                    f"{' (' + str(skipped_violations) + ' rejected by ontology)' if skipped_violations else ''}"
                    f" for ws {ws_id}")
                return {"entities": len(entities), "relationships": len(relationships),
                        "edges_rejected": skipped_violations}
            except Exception as e:
                session.rollback()
                logger.error(f"Structured ingestion failed: {e}")
                return {"entities": 0, "relationships": 0}

    @staticmethod
    def _find_existing_node(session, ws_id: str, name: str, node_type: str):
        """Alias/case-insensitive node lookup for entity resolution (A5).

        Matches exact (legacy path, indexed), then case-insensitive name,
        then names recorded in the node's also_known_as property list.
        """
        from sqlalchemy import or_

        existing = session.query(GraphNode).filter_by(
            workspace_id=ws_id, name=name, type=node_type,
        ).first()
        if existing:
            return existing

        candidates = session.query(GraphNode).filter(
            GraphNode.workspace_id == ws_id,
            GraphNode.type == node_type,
            func.lower(GraphNode.name) == name.lower(),
        ).all()
        if not candidates:
            candidates = [
                n for n in session.query(GraphNode).filter(
                    GraphNode.workspace_id == ws_id,
                    GraphNode.type == node_type,
                ).limit(500).all()
                if name in ((n.properties or {}).get("also_known_as") or [])
            ]
        return candidates[0] if candidates else None

    _version_ingest_counter: Dict[str, int] = {}

    def _maybe_snapshot_version(self, ws_id: str, every: int = 10) -> None:
        """Create a graph version snapshot every ``every`` ingests (A8)."""
        try:
            count = self._version_ingest_counter.get(ws_id, 0) + 1
            self._version_ingest_counter[ws_id] = count
            if count % every != 0:
                return
            from core.graphrag.dynamic_graph import get_dynamic_graph_manager
            get_dynamic_graph_manager().create_version(
                ws_id, metadata={"trigger": "ingest", "ingest_count": count})
        except Exception as exc:
            logger.debug(f"graph version snapshot skipped: {exc}")

    # ==================== READ OPERATIONS (SQL) ====================

    # ---- Vector index (P1.5): LanceDB mirror of graph nodes ---------------
    # The pgvector vector leg only ever ran on Postgres (the `<=>` operator
    # fails on SQLite), leaving Personal Edition keyword-only. Nodes are
    # mirrored into a LanceDB `graph_nodes` table (id = node id) which works
    # on every backend.

    def _index_node_vector(self, node_id, name, entity_type, description, ws_id) -> bool:
        """Mirror a node into the LanceDB graph_nodes table. node_id/name/type
        ride in the metadata JSON (schema-safe against pre-existing tables);
        the row id is the node id. Returns add success."""
        try:
            from core.lancedb_handler import get_lancedb_handler

            handler = get_lancedb_handler(ws_id)
            text = f"{name} ({entity_type}): {description or ''}"
            return bool(handler.add_document(
                "graph_nodes",
                text,
                source="graphrag",
                metadata={"node_id": node_id, "name": name, "type": entity_type},
                extra_columns={"id": node_id},
            ))
        except Exception as e:
            logger.debug(f"graph node vector index failed for {node_id}: {e}")
            return False

    # ---- Bi-temporal edges (P2.2) -------------------------------------------
    def invalidate_edge(self, edge_id: str, reason: str) -> bool:
        """Mark an edge superseded (invalidated, never deleted — full history
        preserved for 'what was true as of date X' queries)."""
        try:
            with get_db_session() as session:
                edge = session.query(GraphEdge).filter(GraphEdge.id == edge_id).first()
                if not edge or edge.invalid_at is not None:
                    return False
                edge.invalid_at = datetime.utcnow()
                edge.invalidation_reason = reason or "superseded"
                session.commit()
                return True
        except Exception as e:
            logger.error(f"invalidate_edge failed: {e}")
            return False

    def edges_as_of(self, as_of: datetime, workspace_id: Optional[str] = None) -> List[Dict]:
        """Point-in-time edge list (bi-temporal read): edges whose valid_from
        ≤ as_of and (invalid_at is null or invalid_at > as_of)."""
        ws_id = workspace_id or self.workspace_id
        try:
            with get_db_session() as session:
                rows = session.query(GraphEdge).filter(
                    GraphEdge.workspace_id == ws_id,
                    GraphEdge.valid_from <= as_of,
                    (GraphEdge.invalid_at.is_(None)) | (GraphEdge.invalid_at > as_of),
                ).all()
                return [{
                    "id": r.id, "source": r.source_node_id, "target": r.target_node_id,
                    "type": r.relationship_type, "valid_from": str(r.valid_from),
                    "invalid_at": str(r.invalid_at),
                } for r in rows]
        except Exception as e:
            logger.error(f"edges_as_of failed: {e}")
            return []

    def backfill_node_vectors(self, workspace_id: Optional[str] = None) -> Dict[str, int]:
        """(Re)embed all graph nodes for a workspace into the LanceDB
        graph_nodes table. Idempotent per node id (LanceDB rows are
        appended — call drop_table('graph_nodes') first for a clean rebuild)."""
        ws_id = workspace_id or self.workspace_id
        embedded = skipped = 0
        try:
            with get_db_session() as session:
                nodes = session.query(GraphNode).filter(
                    GraphNode.workspace_id == ws_id
                ).all()
            for n in nodes:
                if self._index_node_vector(n.id, n.name, n.type, n.description, ws_id):
                    embedded += 1
                else:
                    skipped += 1
        except Exception as e:
            logger.error(f"backfill_node_vectors failed: {e}")
        return {"embedded": embedded, "skipped": skipped, "workspace": ws_id}

    def local_search(self, workspace_id: Optional[str] = None,
                     tenant_id: Optional[str] = None,
                     query: str = "", depth: int = 2,
                     exclude_doc_ids: Optional[set] = None,
                     include_stale: bool = False,
                     as_of: Optional[datetime] = None) -> Dict[str, Any]:
        """Perform Local Search using Recursive CTE (BFS) with Bidirectional Traversal.

        Freshness cascade: by default, graph nodes/edges whose origin document
        (recorded in ``properties->>'doc_id'``) is non-fresh are excluded from
        traversal. The non-fresh doc-id set is resolved from the
        ``ingested_documents`` table unless the caller supplies
        ``exclude_doc_ids``. Pass ``include_stale=True`` to bypass (admin/
        observability). See core/doc_freshness_service.py.

        W4 time travel: ``as_of`` prunes edges that were not alive at that
        instant from the CTE traversal and the relationship listing
        (``valid_from <= as_of`` and ``invalid_at`` null or ``> as_of``).
        Nodes carry no bi-temporal fields, so they are never time-filtered.
        ``None`` = legacy behavior (``invalid_at IS NULL`` only, byte-identical
        SQL). The cutoff is recorded in the result as ``as_of`` (ISO string).
        """
        ws_id = workspace_id or self.workspace_id
        tid = tenant_id or self.tenant_id or "default"

        # W4: edge-alive predicate. When as_of is absent the legacy fragment
        # ``e.invalid_at IS NULL`` is emitted verbatim (no params injected).
        as_of_extra: Dict[str, Any] = {}
        if as_of is not None:
            as_of_extra["as_of"] = as_of
        edge_alive = (
            "(e.invalid_at IS NULL OR e.invalid_at > :as_of)"
            " AND (e.valid_from IS NULL OR e.valid_from <= :as_of)"
            if as_of is not None
            else "e.invalid_at IS NULL"
        )

        def _run_sync(coro):
            import asyncio
            import concurrent.futures
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(lambda: asyncio.run(coro))
                    return future.result()
            else:
                return asyncio.run(coro)

        with get_db_session() as session:
            try:
                # 1. True Hybrid Start-Node Discovery: run vector AND keyword, union results.
                #    Vector anchors semantic matches; keyword ensures exact/partial name hits
                #    (IDs, acronyms, proper nouns) are never dropped.
                query_embedding = None
                try:
                    query_embedding = _run_sync(
                        self.llm_service.generate_embedding(
                            query, workspace_id=ws_id, tenant_id=tid
                        )
                    )
                except Exception as emb_err:
                    logger.debug(f"Could not generate query embedding for local_search: {emb_err}")

                is_postgres = (session.bind.dialect.name == "postgresql") if session.bind else True

                # --- Freshness cascade: resolve non-fresh doc ids to exclude ---
                # Graph nodes/edges carry their origin document in
                # properties->>'doc_id' (graphrag_engine.py:295,346). When a doc
                # goes stale/superseded/removed we hide the subgraph derived
                # from it. The set is resolved from ingested_documents unless
                # the caller supplies one; include_stale bypasses the filter.
                if not include_stale and exclude_doc_ids is None:
                    try:
                        from core.doc_freshness_service import (
                            DocFreshnessService,
                            FRESHNESS_FILTER_ENABLED,
                        )
                        if FRESHNESS_FILTER_ENABLED:
                            exclude_doc_ids = DocFreshnessService(
                                session, workspace_id=ws_id
                            ).non_fresh_doc_ids(ws_id) or None
                    except Exception as fresh_err:
                        logger.debug(f"Freshness exclude-set resolve failed: {fresh_err}")
                        exclude_doc_ids = None

                # Build SQL fragments excluding nodes whose origin doc is
                # non-fresh. Empty set → no-op fragments. Two variants are
                # produced because the anchor and recursive parts of the CTE
                # use different node aliases (``n`` vs ``target``).
                node_fresh_anchor = ""
                node_fresh_recursive = ""
                if exclude_doc_ids:
                    ids_csv = ", ".join(
                        "'" + str(d).replace("'", "''") + "'" for d in exclude_doc_ids
                    )
                    if is_postgres:
                        node_fresh_anchor = (
                            f" AND (n.properties->>'doc_id' IS NULL "
                            f"OR n.properties->>'doc_id' NOT IN ({ids_csv}))"
                        )
                        node_fresh_recursive = (
                            f" AND (target.properties->>'doc_id' IS NULL "
                            f"OR target.properties->>'doc_id' NOT IN ({ids_csv}))"
                        )
                    else:
                        node_fresh_anchor = (
                            f" AND (json_extract(n.properties, '$.doc_id') IS NULL "
                            f"OR json_extract(n.properties, '$.doc_id') NOT IN ({ids_csv}))"
                        )
                        node_fresh_recursive = (
                            f" AND (json_extract(target.properties, '$.doc_id') IS NULL "
                            f"OR json_extract(target.properties, '$.doc_id') NOT IN ({ids_csv}))"
                        )

                # -- Vector leg (LanceDB graph_nodes mirror — works on SQLite
                # and Postgres alike; the old pgvector `<=>` leg never ran
                # on SQLite, leaving Personal Edition keyword-only) --
                vector_nodes = []
                try:
                    import json as _json

                    from core.lancedb_handler import get_lancedb_handler

                    handler = get_lancedb_handler(ws_id)
                    vec_rows = handler.search("graph_nodes", query, limit=5) or []
                    seen: set = set()
                    vec_ids = []
                    for r in vec_rows:
                        # node_id rides in the metadata JSON (schema-safe)
                        raw_meta = r.get("metadata")
                        try:
                            meta = _json.loads(raw_meta) if isinstance(raw_meta, str) else (raw_meta or {})
                        except Exception:
                            meta = {}
                        nid = str(meta.get("node_id") or r.get("node_id") or r.get("id") or "")
                        if nid and nid not in seen:
                            seen.add(nid)
                            vec_ids.append(nid)
                    if vec_ids:
                        safe_ids = ", ".join(
                            "'" + str(i).replace("'", "''") + "'" for i in vec_ids
                        )
                        vector_nodes = session.execute(text(
                            f"SELECT id, name, type, description FROM graph_nodes "
                            f"WHERE id IN ({safe_ids})"
                        )).fetchall()
                    logger.info(f"Hybrid search: vector leg found {len(vector_nodes)} nodes")
                except Exception as lanc_err:
                    logger.debug(f"LanceDB graph vector leg failed: {lanc_err}")

                # -- Keyword leg (always runs) --
                # Match on extracted search terms, not the raw query: a
                # natural-language question ("What did ACME inquire about?")
                # is never a substring of a node name, so the old full-query
                # LIKE returned ~0 entities for every conversational lookup.
                like_op = "ILIKE" if is_postgres else "LIKE"
                _stop = {
                    "what", "which", "who", "whom", "whose", "when", "where",
                    "why", "how", "did", "does", "do", "is", "are", "was",
                    "were", "the", "a", "an", "of", "for", "about", "on",
                    "in", "to", "from", "with", "and", "or", "their", "they",
                    "our", "we", "you", "me", "tell", "give", "show", "find",
                    "any", "all", "that", "this", "it",
                }
                terms = [
                    w for w in query.replace("?", " ").replace(",", " ").split()
                    if len(w) > 2 and w.lower() not in _stop
                ][:8]
                if terms:
                    term_clauses = " OR ".join(
                        f"(name {like_op} :term_{i} OR description {like_op} :term_{i})"
                        for i in range(len(terms))
                    )
                    keyword_sql = text(f"""
                        SELECT id, name, type, description
                        FROM graph_nodes n
                        WHERE workspace_id = :ws_id
                        AND ({term_clauses})
                        {node_fresh_anchor}
                        LIMIT 5
                    """)
                    keyword_params = {
                        "ws_id": ws_id,
                        **{f"term_{i}": f"%{t}%" for i, t in enumerate(terms)},
                    }
                    keyword_nodes = session.execute(keyword_sql, keyword_params).fetchall()
                else:
                    keyword_nodes = []
                logger.info(f"Hybrid search: keyword leg found {len(keyword_nodes)} nodes")

                # -- Union & deduplicate by ID (vector-first) --
                # R83 #4 fusion arms (rrf/linear) were removed 2026-08-24:
                # measured inert by construction — legs are LIMIT 5 each
                # (≤10 fused nodes) while the context window is 15 entities,
                # so reordering the union cannot change retrieval output.
                # Verified empirically: byte-identical contexts across
                # off/rrf/linear on a 28-entity discriminating corpus
                # (core/memory_eval_hard.py). See R83_RELIABILITY_PLAN.md #4.
                seen_ids: set = set()
                start_nodes = []
                for n in list(vector_nodes) + list(keyword_nodes):
                    if n.id not in seen_ids:
                        seen_ids.add(n.id)
                        start_nodes.append(n)

                if not start_nodes:
                    return {
                        "mode": "local",
                        "entities": [],
                        "relationships": [],
                        "context": "No matching entities found.",
                        "count": 0
                    }

                start_ids = [n.id for n in start_nodes]
                # Escape single quotes via doubling ('') to prevent SQL
                # injection/filter-breakage. Node IDs are UUIDs (low risk) but
                # ingest_structured_data accepts caller-supplied data, so
                # defense-in-depth. Matches the LanceDB handler escape rule.
                start_ids_str = ", ".join(f"'{str(id_).replace(chr(39), chr(39)+chr(39))}'" for id_ in start_ids)


                if is_postgres:
                    # Recursive Traversal (Bidirectional with Cycle Detection for Postgres)
                    traversal_sql = text(f"""
                        WITH RECURSIVE traversal AS (
                            SELECT n.id, n.name, n.type, n.description, 0 as depth, ARRAY[n.id] as path
                            FROM graph_nodes n
                            WHERE n.id IN ({start_ids_str})
                            AND n.workspace_id = :ws_id
                            {node_fresh_anchor}

                            UNION

                            SELECT
                                target.id, target.name, target.type, target.description,
                                t.depth + 1,
                                t.path || target.id
                            FROM traversal t
                            JOIN graph_edges e ON ((e.source_node_id = t.id OR e.target_node_id = t.id) AND {edge_alive})
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
                            {node_fresh_recursive}
                        )
                        SELECT DISTINCT id, name, type, description, depth FROM traversal LIMIT 100;
                    """)

                    edges_sql = text("""
                        SELECT e.source_node_id, e.target_node_id, e.relationship_type, e.properties
                        FROM graph_edges e
                        WHERE (e.source_node_id = ANY(:node_ids) OR e.target_node_id = ANY(:node_ids))
                        AND e.workspace_id = :ws_id
                        AND {edge_alive}
                        LIMIT 50
                    """)

                    nodes_result = session.execute(traversal_sql, {
                        "max_depth": depth,
                        "ws_id": ws_id,
                        **as_of_extra,
                    }).fetchall()

                    found_node_ids = [n.id for n in nodes_result]
                    edges_result = session.execute(edges_sql, {"node_ids": found_node_ids, "ws_id": ws_id, **as_of_extra}).fetchall()
                else:
                    # SQLite / Fallback CTE with string path cycle detection
                    traversal_sql = text(f"""
                        WITH RECURSIVE traversal AS (
                            SELECT n.id, n.name, n.type, n.description, 0 as depth, ',' || n.id || ',' as path
                            FROM graph_nodes n
                            WHERE n.id IN ({start_ids_str})
                            AND n.workspace_id = :ws_id
                            {node_fresh_anchor}

                            UNION

                            SELECT
                                target.id, target.name, target.type, target.description,
                                t.depth + 1,
                                t.path || target.id || ','
                            FROM traversal t
                            JOIN graph_edges e ON ((e.source_node_id = t.id OR e.target_node_id = t.id) AND {edge_alive})
                            JOIN graph_nodes target ON (
                                CASE
                                    WHEN e.source_node_id = t.id THEN e.target_node_id = target.id
                                    ELSE e.source_node_id = target.id
                                END
                            )
                            WHERE t.depth < :max_depth
                            AND e.workspace_id = :ws_id
                            AND target.workspace_id = :ws_id
                            AND t.path NOT LIKE '%,' || target.id || ',%'
                            {node_fresh_recursive}
                        )
                        SELECT DISTINCT id, name, type, description, depth FROM traversal
                        LIMIT 100;
                    """)

                    nodes_result = session.execute(traversal_sql, {
                        "max_depth": depth,
                        "ws_id": ws_id,
                        **as_of_extra,
                    }).fetchall()

                    found_node_ids = [n.id for n in nodes_result]
                    if found_node_ids:
                        found_ids_str = ", ".join(f"'{str(id_)}'" for id_ in found_node_ids)
                        edges_sql = text(f"""
                            SELECT e.source_node_id, e.target_node_id, e.relationship_type, e.properties
                            FROM graph_edges e
                            WHERE (e.source_node_id IN ({found_ids_str}) OR e.target_node_id IN ({found_ids_str}))
                            AND e.workspace_id = :ws_id
                            AND {edge_alive}
                            LIMIT 50
                        """)
                        edges_result = session.execute(edges_sql, {"ws_id": ws_id, **as_of_extra}).fetchall()
                    else:
                        edges_result = []

                entities = [{"id": str(n.id), "name": n.name, "type": n.type, "description": n.description} for n in nodes_result]
                relationships = [{"from": str(e.source_node_id), "to": str(e.target_node_id), "type": e.relationship_type} for e in edges_result]

                # Phase 2: augment with scored multi-hop expansion from the top
                # seed node. The expander adds relationship-type prioritization,
                # per-hop relevance scoring with decay, and confidence propagation
                # — none of which the blind BFS above provides. Best-effort: a
                # failure here (e.g. expander unavailable) leaves the base results
                # intact.
                multi_hop_paths = []
                try:
                    from core.graphrag.multi_hop_expansion import get_sql_expander
                    expander = get_sql_expander()
                    top_seed = str(start_ids[0])
                    expansion = expander.expand_sql(
                        start_entity_id=top_seed,
                        workspace_id=ws_id,
                        max_depth=depth,
                        session=session,
                        as_of=as_of,
                    )
                    multi_hop_paths = [
                        {"nodes": p.node_ids, "relevance": p.relevance_score, "hops": p.hops}
                        for p in getattr(expansion, "paths", [])
                    ]
                except Exception as mh_err:
                    logger.debug(f"Multi-hop expansion skipped (non-fatal): {mh_err}")

                return {
                    "mode": "local",
                    "start_entities": [n.name for n in start_nodes],
                    "entities": entities,
                    "relationships": relationships,
                    "multi_hop_paths": multi_hop_paths,
                    "count": len(entities),
                    **({"as_of": as_of.isoformat()} if as_of is not None else {}),
                }
            except Exception as e:
                logger.error(f"Local search failed: {e}")
                return {"error": str(e), "mode": "local", "entities": [], "relationships": [], "count": 0}

    async def global_search(self, workspace_id: Optional[str] = None, 
                           tenant_id: Optional[str] = None,
                           query: str = "",
                           as_of: Optional[datetime] = None) -> Dict[str, Any]:
        """Global Search using LLM-based synthesis of Community Summaries.

        W7 time travel: ``as_of`` synthesizes from the archived community
        generation whose [valid_from, invalid_at) interval contains the
        instant (graph_community_snapshots); ``None`` reads the live
        ``graph_communities`` rows — byte-identical legacy behavior.
        """
        ws_id = workspace_id or self.workspace_id
        tid = tenant_id or self.tenant_id
        
        with get_db_session() as session:
            try:
                # 1. Fetch relevant communities
                if as_of is not None:
                    sql = text("""
                        SELECT id, summary, keywords, level
                        FROM graph_community_snapshots
                        WHERE workspace_id = :ws_id
                        AND valid_from <= :as_of
                        AND invalid_at > :as_of
                        ORDER BY invalid_at DESC
                        LIMIT 20
                    """)
                    try:
                        communities = session.execute(
                            sql, {"ws_id": ws_id, "as_of": as_of}
                        ).fetchall()
                    except OperationalError as oe:
                        # Snapshots table not yet created (fresh DB / tests)
                        if "graph_community_snapshots" in str(oe):
                            communities = []
                        else:
                            raise
                    if not communities:
                        # Outside archived intervals: the LIVE rows are the
                        # active generation from the last replacement onward
                        # (or from first creation when nothing was archived).
                        try:
                            boundary = session.execute(text(
                                "SELECT MAX(invalid_at) FROM graph_community_snapshots "
                                "WHERE workspace_id = :ws_id"
                            ), {"ws_id": ws_id}).scalar()
                            if boundary is None:
                                boundary = session.execute(text(
                                    "SELECT MIN(created_at) FROM graph_communities "
                                    "WHERE workspace_id = :ws_id"
                                ), {"ws_id": ws_id}).scalar()
                        except OperationalError:
                            boundary = None
                        if boundary is not None:
                            # Raw text() on SQLite yields strings + naive
                            # datetimes; normalize before comparing to as_of.
                            if isinstance(boundary, str):
                                boundary = datetime.fromisoformat(boundary)
                            if boundary.tzinfo is None:
                                boundary = boundary.replace(tzinfo=timezone.utc)
                            if as_of >= boundary:
                                communities = session.execute(text("""
                                    SELECT id, summary, keywords, level
                                    FROM graph_communities
                                    WHERE workspace_id = :ws_id
                                    ORDER BY created_at DESC
                                    LIMIT 20
                                """), {"ws_id": ws_id}).fetchall()
                else:
                    sql = text("""
                        SELECT id, summary, keywords, level
                        FROM graph_communities
                        WHERE workspace_id = :ws_id
                        ORDER BY created_at DESC
                        LIMIT 20
                    """)
                    try:
                        communities = session.execute(sql, {"ws_id": ws_id}).fetchall()
                    except OperationalError as oe:
                        # Communities table not yet created (fresh DB / tests) —
                        # global search degrades to the empty path, not an error.
                        if "graph_communities" in str(oe):
                            communities = []
                        else:
                            raise

                if not communities:
                    answer = (
                        "No community data available for global search."
                        if as_of is None
                        else "No community data available for global search at the requested time."
                    )
                    result = {"mode": "global", "summaries": [], "answer": answer}
                    if as_of is not None:
                        result["as_of"] = as_of.isoformat()
                    return result

                # 2. Filter/Rank communities by query relevance
                scored = []
                q_lower = query.lower()
                for c in communities:
                    score = 0
                    if c.keywords:
                        score += sum(1 for k in c.keywords if k.lower() in q_lower)
                    if q_lower in c.summary.lower():
                        score += 2
                    
                    if score > 0 or not q_lower:
                        scored.append({"summary": c.summary, "score": score})
                
                scored.sort(key=lambda x: x["score"], reverse=True)
                top_summaries = [s["summary"] for s in scored[:10]]
                
                if not top_summaries:
                    top_summaries = [c.summary for c in communities[:5]]

                # 3. Use LLM to synthesize the final answer
                context_str = "\n---\n".join(top_summaries)
                system_prompt = f"""
                You are a Global GraphRAG Assistant. Synthesize a comprehensive answer 
                based on these community summaries.
                
                **Query:** {query}
                
                **Community Summaries:**
                {context_str}
                """
                
                response = await self.llm_service.generate_completion(
                    messages=[{"role": "system", "content": system_prompt}],
                    temperature=0.3
                )
                
                answer = response.get("content", "Failed to synthesize global answer.")

                return {
                    "mode": "global",
                    "summaries": top_summaries,
                    "answer": answer,
                    "count": len(top_summaries),
                    **({"as_of": as_of.isoformat()} if as_of is not None else {}),
                }
            except Exception as e:
                logger.error(f"Global search failed: {e}")
                return {"error": str(e), "mode": "global", "answer": f"Error: {e}"}

    async def query(self, workspace_id: Optional[str] = None, 
                    tenant_id: Optional[str] = None,
                    query: str = "", mode: str = "auto",
                    as_of: Optional[datetime] = None) -> Dict[str, Any]:
        """Unified query entry point (Async).

        W4: ``as_of`` threads into local mode only — global mode answers from
        persisted community summaries, which carry no validity interval to
        filter on (documented in docs/architecture/TEMPORAL_EVOLUTION.md).
        """
        ws_id = workspace_id or self.workspace_id
        tid = tenant_id or self.tenant_id

        if mode == "auto":
            holistic = ["overview", "themes", "main", "all", "summary"]
            mode = "global" if any(kw in query.lower() for kw in holistic) else "local"

        if mode == "global":
            return await self.global_search(ws_id, tid, query)
        else:
            # to_thread: local_search's LanceDB vector leg calls the sync
            # embed_text, which no-ops in the event-loop thread (async-context
            # guard) — the vector leg silently returned [] from every async
            # caller. A worker thread embeds fine.
            return await asyncio.to_thread(
                self.local_search, ws_id, tid, query, 2, None, False, as_of
            )

    async def get_context_for_ai(self, workspace_id: Optional[str] = None, 
                               tenant_id: Optional[str] = None,
                               query: str = "",
                               as_of: Optional[datetime] = None) -> str:
        """Format context for AI prompt (Async).

        W4: ``as_of`` threads through to ``query`` (local mode only).
        """
        ws_id = workspace_id or self.workspace_id
        tid = tenant_id or self.tenant_id
        
        result = await self.query(ws_id, tid, query, as_of=as_of)
        if result.get("mode") == "global":
            return f"Global Context: {result.get('answer')}"
        
        entities = result.get("entities", [])
        rels = result.get("relationships", [])
        id_to_name = {e['id']: e['name'] for e in entities}
        
        context_lines = [f"Found {len(entities)} relevant entities:"]

        # Business properties (price, stock, sku, status…) live on the node's
        # `properties` JSON, which the search legs don't select. Re-hydrate
        # them so the injected context can answer "what's the price / stock"
        # questions — the most common employee lookup — without a second query.
        prop_map: Dict[str, Dict[str, Any]] = {}
        try:
            ent_ids = [e["id"] for e in entities[:15] if e.get("id")]
            if ent_ids:
                with get_db_session() as session:
                    rows = session.query(GraphNode).filter(
                        GraphNode.id.in_(ent_ids)
                    ).all()
                    prop_map = {r.id: (r.properties or {}) for r in rows}
        except Exception as prop_err:
            logger.debug(f"property hydration failed: {prop_err}")

        _PROP_EXCLUDE = {
            "id", "source", "created_at", "updated_at", "embedding",
            "sensitivity", "doc_id", "workspace_id", "tenant_id",
        }
        for e in entities[:15]:
            line = f"- {e['name']} ({e['type']}): {e.get('description', '')}"
            props = prop_map.get(e.get("id")) or {}
            salient = [
                f"{k}={v}" for k, v in props.items()
                if k not in _PROP_EXCLUDE and v not in (None, "", [], {})
            ][:12]
            if salient:
                line += " [" + "; ".join(str(s) for s in salient) + "]"
            context_lines.append(line)
            
        context_lines.append("\nRelationships:")
        for r in rels[:25]:
            from_name = id_to_name.get(r['from'], r['from'])
            to_name = id_to_name.get(r['to'], r['to'])
            context_lines.append(f"- {from_name} -> {r['type']} -> {to_name}")
            
        return "\n".join(context_lines)

    def enqueue_reindex_job(self, workspace_id: Optional[str] = None) -> bool:
        """Enqueue a background job to recompute communities and summaries."""
        ws_id = workspace_id or self.workspace_id
        
        # Redis connection
        redis_url = os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL")
        if not redis_url:
            return False
            
        try:
            import redis
            r = redis.from_url(redis_url)
            r.lpush("graph_reindex_jobs", workspace_id or self.workspace_id)
            return True
        except Exception:
            return False

    def build_communities(self, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """Build graph communities using the Phase 2 community-detection service.

        Populates the ``graph_communities`` and ``community_membership`` tables
        so that ``global_search`` returns community-synthesized answers. Uses
        the Leiden algorithm when ``leidenalg`` is installed, falling back to
        NetworkX greedy modularity (Louvain) otherwise. Called by the live
        ``/api/graphrag/communities`` route.
        """
        ws_id = workspace_id or self.workspace_id
        try:
            from core.graphrag.community_detection import get_community_detector
            detector = get_community_detector()
            result = detector.detect_communities(
                workspace_id=ws_id, store_results=True
            )
            return {
                "success": True,
                "communities": len(result.communities) if hasattr(result, "communities") else 0,
                "workspace_id": ws_id,
            }
        except Exception as e:
            logger.error(f"Community detection failed: {e}")
            return {"success": False, "error": "Community detection failed", "communities": 0}

    async def discover_failed_hypotheses_patterns(
        self,
        tenant_id: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Scan completed hypothesis trees for failed/pruned hypotheses using GraphRAG's LLM
        to identify common failure patterns and extract recurring negative constraints.
        """
        # Uses the module-level get_db_session so patch targets behave uniformly.
        if self.db:
            return await self._discover_patterns_with_session(self.db, tenant_id, limit)

        with get_db_session() as session:
            return await self._discover_patterns_with_session(session, tenant_id, limit)

    async def _discover_patterns_with_session(
        self,
        session: Session,
        tenant_id: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Internal helper executing pattern discovery over a given active DB session."""
        from core.auto_dev.models import HypothesisTreeRecord

        # Query recent trees with pruned nodes or failures
        records = (
            session.query(HypothesisTreeRecord)
            .filter(HypothesisTreeRecord.tenant_id == tenant_id)
            .filter(HypothesisTreeRecord.pruned_nodes > 0)
            .order_by(HypothesisTreeRecord.created_at.desc())
            .limit(limit)
            .all()
        )

        if not records:
            return {
                "success": True,
                "patterns": [],
                "summary": "No failed hypotheses recorded for this tenant yet."
            }

        # Collect constraints and task descriptions
        failed_contexts = []
        aggregated_constraints = set()
        for r in records:
            failed_contexts.append(
                f"Task: {r.task_description}\n"
                f"Type: {r.task_type}\n"
                f"Nodes explored: {r.total_nodes}, Pruned: {r.pruned_nodes}\n"
                f"Constraints learned: {r.negative_constraints or 'None'}"
            )
            if r.negative_constraints:
                aggregated_constraints.update(r.negative_constraints)

        # Use LLM to synthesize patterns if enabled and available
        context_text = "\n\n---\n\n".join(failed_contexts)
        summary = "LLM synthesis skipped."
        
        if GRAPHRAG_LLM_ENABLED:
            try:
                system_prompt = (
                    "You are the GraphRAG Hypothesis Analyzer. Review these records of "
                    "failed or pruned optimization branches and synthesize the key recurring "
                    "failure patterns or negative constraints to avoid."
                )
                user_prompt = (
                    f"Here are {len(records)} recent failed/pruned HTR optimization sessions:\n\n"
                    f"{context_text}\n\n"
                    "Synthesize the patterns now:"
                )
                
                response = await self.llm_service.generate_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    model=GRAPHRAG_LLM_MODEL,
                    task_type="reasoning"
                )
                summary = response.get("content", "Failed to generate synthesis.")
            except Exception as e:
                logger.error(f"Failed to synthesize patterns via LLM: {e}")
                summary = f"Synthesis error: {e}"

        return {
            "success": True,
            "sessions_analyzed": len(records),
            "aggregated_constraints": list(aggregated_constraints),
            "summary": summary
        }


# Global Instance
graphrag_engine = GraphRAGEngine()
