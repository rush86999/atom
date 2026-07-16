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

    def _get_registry_entry(self, entity_type: str) -> Optional[Dict]:
        """Get the registry configuration for a canonical type."""
        t_lower = entity_type.lower()
        if t_lower in ENTITY_REGISTRY:
            return ENTITY_REGISTRY[t_lower]
        return None

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

        # BUG FIX: Validate and sanitize input before using in queries
        name = self._validate_search_input(name)

        # 1. Match by ID if provided
        if canonical_id:
            return session.query(model).filter(model.id == canonical_id).first()

        # 2. Match by Name/Search fields
        display_field = registry.get("display_field", "name")
        # BUG FIX: Escape LIKE special characters to prevent wildcard injection
        escaped_name = self._escape_like_pattern(name)
        # Try exact match on display field first
        match = session.query(model).filter(
            getattr(model, display_field).ilike(escaped_name)
        ).first()

        if match:
            return match

        # 3. Fuzzy match across search fields
        for field_name in registry.get("search_fields", []):
            # BUG FIX: Escape LIKE special characters to prevent wildcard injection
            escaped_pattern = self._escape_like_pattern(name)
            match = session.query(model).filter(
                getattr(model, field_name).ilike(f"%{escaped_pattern}%")
            ).first()
            if match:
                return match

        return None

    def canonical_search(self, workspace_id: Optional[str] = None, tenant_id: Optional[str] = None,
                         entity_type: str = "unknown", query: str = "") -> List[Dict]:
        """Search for canonical records to anchor graph nodes."""
        ws_id = workspace_id or self.workspace_id
        tid = tenant_id or self.tenant_id

        registry = self._get_registry_entry(entity_type)
        if not registry:
            return []

        model = registry["model"]
        search_fields = registry.get("search_fields", ["name"])
        display_field = registry.get("display_field", "name")

        # BUG FIX: Validate and sanitize input before using in queries
        query = self._validate_search_input(query)

        with get_db_session() as session:
            try:
                # Use a combined OR filter for all search fields
                from sqlalchemy import or_
                # BUG FIX: Escape LIKE special characters to prevent wildcard injection
                escaped_query = self._escape_like_pattern(query)
                filters = [getattr(model, f_name).ilike(f"%{escaped_query}%") for f_name in search_fields]

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
                             doc_id: str = "unknown", text: str = "", source: str = "unknown"):
        """
        Ingest raw text -> Extract -> Store in Postgres.
        """
        ws_id = workspace_id or self.workspace_id
        tid = tenant_id or self.tenant_id

        # 1. Extract
        if self._is_llm_available(ws_id):
            logger.info(f"Using LLM-based extraction for document {doc_id}")
            entities, relationships = await self._llm_extract_entities_and_relationships(text, doc_id, source, ws_id)
        else:
            entities, relationships = self._pattern_extract_entities_and_relationships(text, doc_id, source)

        if not entities and not relationships:
            logger.info("No entities extracted.")
            return

        # 2. Store
        e_dicts = [{"name": e.name, "type": e.entity_type, "description": e.description, "properties": e.properties} for e in entities]
        r_dicts = [{"from": r.from_entity, "to": r.to_entity, "type": r.rel_type, "properties": r.properties} for r in relationships]
        
        self.ingest_structured_data(ws_id, tid, e_dicts, r_dicts)

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
                
                # Trigger Automation
                if AUTOMATION_AVAILABLE:
                    try:
                        asyncio.create_task(orchestrator.trigger_event("graph_entity_upsert", {
                            "entity_type": entity.entity_type,
                            "entity_id": entity.id,
                            "name": entity.name,
                            "is_new": is_new,
                            "workspace_id": ws_id,
                            "tenant_id": tid
                        }))
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
                edge = GraphEdge(
                    id=rel.id,
                    tenant_id=tid,
                    workspace_id=ws_id,
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
                # 1. Process Nodes
                node_map = {} 
                for e_data in entities:
                    name = e_data.get("name")
                    if not name: continue
                    
                    properties = e_data.get("properties", {})
                    canonical_type = properties.get("canonical_type")
                    
                    if canonical_type:
                        canonical_id = self._resolve_canonical_entity(session, ws_id, name, canonical_type)
                        if canonical_id:
                            properties["canonical_id"] = canonical_id

                    properties_copy = dict(properties)
                    embedding_val = properties_copy.pop("embedding", None)

                    node = GraphNode(
                        tenant_id=tid,
                        workspace_id=ws_id,
                        name=name,
                        type=e_data.get("type", "unknown"),
                        description=e_data.get("description", ""),
                        properties=properties_copy,
                        embedding=embedding_val
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
                            tenant_id=tid,
                            workspace_id=ws_id,
                            source_node_id=src,
                            target_node_id=dst,
                            relationship_type=r_data.get("type", "related_to"),
                            properties=r_data.get("properties", {})
                        )
                        session.add(edge)
                
                session.commit()
                logger.info(f"Ingested {len(entities)} nodes, {len(relationships)} edges for ws {ws_id}")
                return {"entities": len(entities), "relationships": len(relationships)}
            except Exception as e:
                session.rollback()
                logger.error(f"Structured ingestion failed: {e}")
                return {"entities": 0, "relationships": 0}

    # ==================== READ OPERATIONS (SQL) ====================

    def local_search(self, workspace_id: Optional[str] = None,
                     tenant_id: Optional[str] = None,
                     query: str = "", depth: int = 2) -> Dict[str, Any]:
        """Perform Local Search using Recursive CTE (BFS) with Bidirectional Traversal."""
        ws_id = workspace_id or self.workspace_id
        tid = tenant_id or self.tenant_id or "default"

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

                # -- Vector leg --
                vector_nodes = []
                if query_embedding:
                    try:
                        vector_sql = text("""
                            SELECT id, name, type, description
                            FROM graph_nodes
                            WHERE workspace_id = :ws_id
                            AND embedding IS NOT NULL
                            ORDER BY embedding <=> :query_embedding
                            LIMIT 5
                        """)
                        vector_nodes = session.execute(
                            vector_sql, {
                                "ws_id": ws_id,
                                "query_embedding": query_embedding
                            }
                        ).fetchall()
                        logger.info(f"Hybrid search: vector leg found {len(vector_nodes)} nodes")
                    except Exception as pg_err:
                        logger.debug(f"pgvector query failed (hybrid): {pg_err}")

                # -- Keyword leg (always runs) --
                like_op = "ILIKE" if is_postgres else "LIKE"
                keyword_sql = text(f"""
                    SELECT id, name, type, description
                    FROM graph_nodes
                    WHERE workspace_id = :ws_id
                    AND name {like_op} :query
                    LIMIT 5
                """)
                keyword_nodes = session.execute(
                    keyword_sql, {"ws_id": ws_id, "query": f"%{query}%"}
                ).fetchall()
                logger.info(f"Hybrid search: keyword leg found {len(keyword_nodes)} nodes")

                # -- Union & deduplicate by ID --
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
                start_ids_str = ", ".join(f"'{str(id_)}'" for id_ in start_ids)


                if is_postgres:
                    # Recursive Traversal (Bidirectional with Cycle Detection for Postgres)
                    traversal_sql = text(f"""
                        WITH RECURSIVE traversal AS (
                            SELECT n.id, n.name, n.type, n.description, 0 as depth, ARRAY[n.id] as path
                            FROM graph_nodes n
                            WHERE n.id IN ({start_ids_str})
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
                        "max_depth": depth,
                        "ws_id": ws_id
                    }).fetchall()

                    found_node_ids = [n.id for n in nodes_result]
                    edges_result = session.execute(edges_sql, {"node_ids": found_node_ids, "ws_id": ws_id}).fetchall()
                else:
                    # SQLite / Fallback CTE with string path cycle detection
                    traversal_sql = text(f"""
                        WITH RECURSIVE traversal AS (
                            SELECT n.id, n.name, n.type, n.description, 0 as depth, ',' || n.id || ',' as path
                            FROM graph_nodes n
                            WHERE n.id IN ({start_ids_str})
                            AND n.workspace_id = :ws_id

                            UNION

                            SELECT
                                target.id, target.name, target.type, target.description,
                                t.depth + 1,
                                t.path || target.id || ','
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
                            AND t.path NOT LIKE '%,' || target.id || ',%'
                        )
                        SELECT DISTINCT id, name, type, description, depth FROM traversal
                        LIMIT 100;
                    """)

                    nodes_result = session.execute(traversal_sql, {
                        "max_depth": depth,
                        "ws_id": ws_id
                    }).fetchall()

                    found_node_ids = [n.id for n in nodes_result]
                    if found_node_ids:
                        found_ids_str = ", ".join(f"'{str(id_)}'" for id_ in found_node_ids)
                        edges_sql = text(f"""
                            SELECT e.source_node_id, e.target_node_id, e.relationship_type, e.properties
                            FROM graph_edges e
                            WHERE (e.source_node_id IN ({found_ids_str}) OR e.target_node_id IN ({found_ids_str}))
                            AND e.workspace_id = :ws_id
                            LIMIT 50
                        """)
                        edges_result = session.execute(edges_sql, {"ws_id": ws_id}).fetchall()
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
                    "count": len(entities)
                }
            except Exception as e:
                logger.error(f"Local search failed: {e}")
                return {"error": str(e), "mode": "local", "entities": [], "relationships": [], "count": 0}

    async def global_search(self, workspace_id: Optional[str] = None, 
                           tenant_id: Optional[str] = None,
                           query: str = "") -> Dict[str, Any]:
        """Global Search using LLM-based synthesis of Community Summaries."""
        ws_id = workspace_id or self.workspace_id
        tid = tenant_id or self.tenant_id
        
        with get_db_session() as session:
            try:
                # 1. Fetch relevant communities
                sql = text("""
                    SELECT id, summary, keywords, level
                    FROM graph_communities
                    WHERE workspace_id = :ws_id
                    ORDER BY created_at DESC
                    LIMIT 20
                """)
                communities = session.execute(sql, {"ws_id": workspace_id}).fetchall()
                
                if not communities:
                    return {"mode": "global", "summaries": [], "answer": "No community data available for global search."}

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
                    "count": len(top_summaries)
                }
            except Exception as e:
                logger.error(f"Global search failed: {e}")
                return {"error": str(e), "mode": "global", "answer": f"Error: {e}"}

    async def query(self, workspace_id: Optional[str] = None, 
                    tenant_id: Optional[str] = None,
                    query: str = "", mode: str = "auto") -> Dict[str, Any]:
        """Unified query entry point (Async)."""
        ws_id = workspace_id or self.workspace_id
        tid = tenant_id or self.tenant_id

        if mode == "auto":
            holistic = ["overview", "themes", "main", "all", "summary"]
            mode = "global" if any(kw in query.lower() for kw in holistic) else "local"

        if mode == "global":
            return await self.global_search(ws_id, tid, query)
        else:
            return self.local_search(ws_id, tid, query)

    async def get_context_for_ai(self, workspace_id: Optional[str] = None, 
                               tenant_id: Optional[str] = None,
                               query: str = "") -> str:
        """Format context for AI prompt (Async)."""
        ws_id = workspace_id or self.workspace_id
        tid = tenant_id or self.tenant_id
        
        result = await self.query(ws_id, tid, query)
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
            r.lpush("graph_reindex_jobs", workspace_id)
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
            return {"success": False, "error": str(e), "communities": 0}

# Global Instance
graphrag_engine = GraphRAGEngine()
