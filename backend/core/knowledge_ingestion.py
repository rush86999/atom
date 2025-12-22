import logging
import asyncio
from typing import List, Dict, Any, Optional
from core.lancedb_handler import get_lancedb_handler
from core.knowledge_extractor import KnowledgeExtractor
from enhanced_ai_workflow_endpoints import RealAIWorkflowService

logger = logging.getLogger(__name__)

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
        self.extractor = KnowledgeExtractor(self.ai_service)
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
        knowledge = await self.extractor.extract_knowledge(text, source)
        
        # 1. Extract knowledge (LLM-based)
        knowledge = await self.extractor.extract_knowledge(text, source)
        
        # 2. Store entities and relationships in LanceDB
        entities = knowledge.get("entities", [])
        relationships = knowledge.get("relationships", [])
        
        success_count = 0
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
                success_count += 1
        
        # 3. Also ingest into GraphRAG for hierarchical queries using structured data
        graphrag_stats = {"entities": 0, "relationships": 0}
        if self.graphrag:
            try:
                # Use the new structured ingestion method
                graphrag_stats = self.graphrag.add_entities_and_relationships(user_id, entities, relationships)
                logger.info(f"GraphRAG ingested {graphrag_stats['entities']} entities and {graphrag_stats['relationships']} relationships for user {user_id}")
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
            return self.graphrag.build_communities(user_id)
        return 0
    
    def query_graphrag(self, user_id: str, query: str, mode: str = "auto") -> Dict[str, Any]:
        """Query GraphRAG for a user - used by AI nodes and chat"""
        if self.graphrag:
            return self.graphrag.query(user_id, query, mode)
        return {"error": "GraphRAG not available"}
    
    def get_ai_context(self, user_id: str, query: str) -> str:
        """Get context for AI nodes from GraphRAG"""
        if self.graphrag:
            return self.graphrag.get_context_for_ai(user_id, query)
        return ""

# Global instance
knowledge_ingestion = KnowledgeIngestionManager()

def get_knowledge_ingestion() -> KnowledgeIngestionManager:
    return knowledge_ingestion
