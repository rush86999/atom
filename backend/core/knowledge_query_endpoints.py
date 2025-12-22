import logging
import json
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.lancedb_handler import get_lancedb_handler
from enhanced_ai_workflow_endpoints import RealAIWorkflowService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

class KnowledgeQueryRequest(BaseModel):
    query: str
    user_id: str
    workspace_id: Optional[str] = None

class KnowledgeQueryManager:
    """
    Traverses the knowledge graph to synthesize answers for complex queries.
    """
    
    def __init__(self, workspace_id: Optional[str] = None):
        self.workspace_id = workspace_id or "default"
        self.handler = get_lancedb_handler(self.workspace_id)
        self.ai_service = RealAIWorkflowService()

    async def answer_query(self, query: str, user_id: str = "default_user", workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Answers a natural language query using the knowledge graph context.
        Returns a dict with 'answer' and 'relevant_facts'.
        """
        # 1. Search the graph for relevant relationships
        related_edges = self.handler.query_knowledge_graph(query, user_id=user_id, limit=15)
        
        if not related_edges:
            return {
                "answer": "I couldn't find any specific information in your knowledge graph to answer that question.",
                "relevant_facts": []
            }
        
        # 2. Extract facts from edges
        facts = []
        for edge in related_edges:
            metadata = edge.get("metadata", {})
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            
            fact = f"- {edge.get('from_id')} {edge.get('type')} {edge.get('to_id')}"
            props = metadata.get("properties", {})
            if props:
                fact += f" (Details: {props})"
            facts.append(fact)
            
        context_str = "\n".join(facts)
        
        # 3. Use LLM to synthesize the answer
        system_prompt = f"""
        You are a Knowledge Graph Query Assistant. Answer the user's question based ONLY on the provided facts from their knowledge graph.
        
        **Facts:**
        {context_str}
        
        If the facts don't contain the answer, say you don't know based on the current records.
        """
        
        result = await self.ai_service.analyze_text(query, system_prompt=system_prompt)
        answer = "Failed to synthesize an answer from the knowledge graph."
        if result and result.get("success"):
            answer = result.get("response", "Internal error synthesizing answer.")
        
        return {
            "answer": answer,
            "relevant_facts": facts
        }

# Helper for factory pattern
def get_knowledge_query_manager(workspace_id: Optional[str] = None) -> KnowledgeQueryManager:
    return KnowledgeQueryManager(workspace_id=workspace_id)

# Legacy instance
knowledge_query_manager = get_knowledge_query_manager()

@router.post("/query")
async def knowledge_query(request: KnowledgeQueryRequest):
    """
    Natural language query endpoint for the knowledge graph.
    """
    try:
        manager = get_knowledge_query_manager(request.workspace_id)
        result = await manager.answer_query(request.query, user_id=request.user_id, workspace_id=request.workspace_id)
        return {"success": True, "answer": result.get("answer"), "relevant_facts": result.get("relevant_facts")}
    except Exception as e:
        logger.error(f"Knowledge query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def get_knowledge_query_manager() -> KnowledgeQueryManager:
    return knowledge_query_manager
