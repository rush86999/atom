import asyncio
import logging
from typing import Any, Dict, List, Optional
from enhanced_ai_workflow_endpoints import RealAIWorkflowService

from core.automation_settings import get_automation_settings
from core.knowledge_extractor import KnowledgeExtractor
from core.lancedb_handler import get_lancedb_handler

logger = logging.getLogger(__name__)


def _normalize_extractor_output(
    entities: Optional[List[Dict[str, Any]]],
    relationships: Optional[List[Dict[str, Any]]],
):
    """Normalize KnowledgeExtractor output to the ingest_structured_data shape.

    The LLM extractor emits entities as ``{id, type, properties: {name, ...}}``
    and relationships with **id-keyed** endpoints, while GraphRAGEngine keys
    nodes by top-level ``name`` and resolves edges through that same map.
    Without this, entities have no name (skipped) and every edge dangles.
    """
    id_to_name: Dict[str, str] = {}
    out_entities: List[Dict[str, Any]] = []
    for e in entities or []:
        if not isinstance(e, dict):
            continue
        props = dict(e.get("properties") or {})
        name = e.get("name") or props.get("name") or e.get("id")
        if not name:
            continue
        name = str(name)
        if e.get("id"):
            id_to_name[str(e["id"])] = name
        out_entities.append({
            "name": name,
            "type": e.get("type") or "unknown",
            "description": e.get("description", ""),
            "properties": props,
        })

    out_relationships: List[Dict[str, Any]] = []
    for r in relationships or []:
        if not isinstance(r, dict):
            continue
        src = id_to_name.get(str(r.get("from")), r.get("from"))
        dst = id_to_name.get(str(r.get("to")), r.get("to"))
        if not src or not dst or not r.get("type"):
            continue
        out_relationships.append({
            "from": str(src),
            "to": str(dst),
            "type": r["type"],
            "properties": r.get("properties") or {},
        })
    return out_entities, out_relationships


class KnowledgeIngestionManager:
    """
    Coordinates the extraction of knowledge from documents and 
    storing them as relationships in the knowledge graph.
    Now integrates with GraphRAG for hierarchical knowledge retrieval.
    """
    
    def __init__(self, workspace_id: Optional[str] = None):
        self.workspace_id = workspace_id
        self.handler = get_lancedb_handler(workspace_id)
        self.ai_service = RealAIWorkflowService()
        # Keyword arg: KnowledgeExtractor.__init__(workspace_id, tenant_id) —
        # the old positional call bound RealAIWorkflowService as workspace_id,
        # which surfaced as "Failed to fetch tenant plan: Error binding
        # parameter 1: type 'RealAIWorkflowService' is not supported" on
        # EVERY extraction (byok_handler's Workspace lookup).
        self.extractor = KnowledgeExtractor(workspace_id=self.workspace_id)
        # Initialize GraphRAG engine
        try:
            from core.graphrag_engine import graphrag_engine
            self.graphrag = graphrag_engine
        except ImportError:
            self.graphrag = None

    async def process_document(self, text: str, doc_id: str, source: str = "unknown", user_id: str = "default_user", workspace_id: Optional[str] = None):
        """
        Extracts knowledge from a document and updates both LanceDB and GraphRAG.
        """
        ws_id = workspace_id or self.workspace_id
        handler = get_lancedb_handler(ws_id)
        logger.info(f"Processing knowledge for document {doc_id} from {source} for user {user_id} in workspace {ws_id}")
        
        # 1. Extract knowledge
        knowledge = await self.extractor.extract_knowledge(text, tenant_id=ws_id, source=source)

        # 2. Store entities and relationships in LanceDB
        entities = knowledge.get("entities", [])
        relationships = knowledge.get("relationships", [])

        # R83: normalize extractor output to the shape ingest_structured_data
        # expects — the LLM extractor emits nested names (properties.name) and
        # id-keyed relationship endpoints, while the engine keys nodes by
        # top-level `name` and resolves edges through that same map.
        entities, relationships = _normalize_extractor_output(entities, relationships)

        # SYNC-OFF-LOOP: each add_knowledge_edge is a synchronous LanceDB
        # write (plus a sync embed attempt) — run per-relationship on this
        # loop task, they serialized the ENTIRE event loop during the
        # post-reconnect backlog (Sep 6, 2026: every endpoint stalled; the
        # lancedb_handler "embed_text (sync) called from the event-loop
        # thread" warnings fired per edge). One worker thread writes the
        # whole edge batch; on a drive-hosted store those writes are slow,
        # but the loop keeps serving.
        def _write_edges() -> int:
            written = 0
            for rel in relationships:
                from_id = rel.get("from")
                to_id = rel.get("to")
                rel_type = rel.get("type")
                props = rel.get("properties", {})

                description = f"{from_id} {rel_type} {to_id}"
                if props:
                    description += f" ({str(props)})"

                success = handler.add_knowledge_edge(
                    from_id=from_id,
                    to_id=to_id,
                    rel_type=rel_type,
                    description=description,
                    metadata={
                        "doc_id": doc_id,
                        "source": source,
                        "properties": props,
                        "workspace_id": ws_id # Label for within-DB context
                    },
                    user_id=user_id
                )
                if success:
                    written += 1
            return written

        success_count = await asyncio.to_thread(_write_edges)
        
        # 3. Also ingest into GraphRAG for hierarchical queries using structured data
        graphrag_stats = {"entities": 0, "relationships": 0}
        if self.graphrag:
            try:
                # Use the new structured ingestion method. NOTE: must be
                # keyword arguments — a positional call shifted entities into
                # tenant_id and silently dropped every relationship.
                # SYNC-OFF-LOOP: ingest_structured_data does Lance/Rust writes
                # synchronously; called directly from this loop task it froze
                # the ENTIRE event loop for its duration — every concurrent
                # request (right-panel tabs, health probes) hung with no
                # response (observed live 2026-09-01). to_thread keeps the
                # loop serving while the Rust side works in a worker thread.
                graphrag_stats = await asyncio.to_thread(
                    self.graphrag.ingest_structured_data,
                    workspace_id=ws_id,
                    tenant_id=ws_id,
                    entities=entities,
                    relationships=relationships,
                )
                logger.info(f"GraphRAG ingested {graphrag_stats['entities']} entities and {graphrag_stats['relationships']} relationships for workspace {ws_id}")
            except Exception as e:
                logger.warning(f"GraphRAG structured ingestion failed: {e}")
                
        # 4. Enrich external integrations if enabled
        settings = get_automation_settings()
        if settings.get_settings().get("enable_integration_enrichment"):
            try:
                self.enrich_integrations(user_id, knowledge)
            except Exception as e:
                logger.error(f"Integration enrichment failed: {e}")

        logger.info(f"Ingested {success_count} knowledge edges from document {doc_id}")
        return {"lancedb_edges": success_count, "graphrag": graphrag_stats}

    def enrich_integrations(self, user_id: str, knowledge: Dict[str, Any]):
        """
        Pushes extracted knowledge back to external systems (Salesforce, HubSpot, etc.)
        """
        entities = knowledge.get("entities", [])
        for entity in entities:
            props = entity.get("properties", {})
            ext_id = props.get("external_id")
            
            if ext_id and entity.get("type") in ["Lead", "Deal", "Person"]:
                logger.info(f"Enriching integration record {ext_id} for user {user_id}")
                # Mock integration update
                # In production: hubspot_client.crm.deals.basic_api.update(ext_id, props)
                pass
    
    def build_user_communities(self, user_id: str) -> int:
        """Build GraphRAG communities for a user after ingestion"""
        if self.graphrag:
            # R83: partition by WORKSPACE (engine convention), not user id —
            # recall sites query the workspace partition.
            return self.graphrag.build_communities(self.workspace_id or "default")
        return 0

    def query_graphrag(self, user_id: str, query: str, mode: str = "auto") -> Dict[str, Any]:
        """Query GraphRAG for a user - used by AI nodes and chat"""
        if self.graphrag:
            return self.graphrag.query(self.workspace_id or "default", query, mode)
        return {"error": "GraphRAG not available"}
    
    def get_ai_context(self, user_id: str, query: str) -> str:
        """Get context for AI nodes from GraphRAG"""
        if self.graphrag:
            return self.graphrag.get_context_for_ai(self.workspace_id or "default", query)
        return ""

# Global instance
knowledge_ingestion = KnowledgeIngestionManager()

def get_knowledge_ingestion() -> KnowledgeIngestionManager:
    return knowledge_ingestion
