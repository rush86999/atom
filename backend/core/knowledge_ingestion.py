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
    """
    
    def __init__(self):
        self.handler = get_lancedb_handler()
        self.ai_service = RealAIWorkflowService()
        self.extractor = KnowledgeExtractor(self.ai_service)

    async def process_document(self, text: str, doc_id: str, source: str = "unknown"):
        """
        Extracts knowledge from a document and updates the graph.
        """
        logger.info(f"Processing knowledge for document {doc_id} from {source}")
        
        # 1. Extract knowledge
        knowledge = await self.extractor.extract_knowledge(text, source)
        
        # 2. Store entities and relationships
        entities = knowledge.get("entities", [])
        relationships = knowledge.get("relationships", [])
        
        # For now, let's store relationships as edges
        # We might want to store entities as documents in a separate table later
        # but the request focuses on Person <-> Project <-> Task <-> File
        
        success_count = 0
        for rel in relationships:
            from_id = rel.get("from")
            to_id = rel.get("to")
            rel_type = rel.get("type")
            props = rel.get("properties", {})
            
            # Create a description for the embedding
            description = f"{from_id} {rel_type} {to_id}"
            if props:
                description += f" ({str(props)})"
            
            # Store in LanceDB
            success = self.handler.add_knowledge_edge(
                from_id=from_id,
                to_id=to_id,
                rel_type=rel_type,
                description=description,
                metadata={
                    "doc_id": doc_id,
                    "source": source,
                    "properties": props
                }
            )
            if success:
                success_count += 1
                
        logger.info(f"Ingested {success_count} knowledge edges from document {doc_id}")
        return success_count

# Global instance
knowledge_ingestion = KnowledgeIngestionManager()

def get_knowledge_ingestion() -> KnowledgeIngestionManager:
    return knowledge_ingestion
