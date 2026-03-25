import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.service_factory import ServiceFactory
from core.models import User

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
        self.engine = ServiceFactory.get_graphrag_engine(self.workspace_id)

    async def answer_query(self, query: str, user_id: str = "default_user", workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Answers a natural language query using the GraphRAGEngine.
        Automatically switches between local and global search based on intent.
        """
        ws_id = workspace_id or self.workspace_id
        
        # Use GraphRAGEngine's unified query method
        # This handles intent detection (local vs global) and LLM synthesis
        result = await self.engine.query(ws_id, query, mode="auto")
        
        if "error" in result:
            return {
                "answer": f"I encountered an error while searching: {result['error']}",
                "relevant_facts": []
            }
            
        answer = result.get("answer", "No answer could be synthesized.")
        
        # Format relevant facts for the UI
        facts = []
        if result.get("mode") == "local":
            entities = result.get("entities", [])
            relationships = result.get("relationships", [])
            for e in entities[:10]:
                facts.append(f"Entity: {e['name']} ({e['type']}) - {e.get('description', '')}")
            for r in relationships[:10]:
                facts.append(f"Relationship: {r['from']} -> {r['type']} -> {r['to']}")
        else:
            # Global mode: facts are the summaries used
            summaries = result.get("summaries", [])
            for s in summaries:
                facts.append(f"Community Summary: {s[:200]}...")
                
        return {
            "answer": answer,
            "relevant_facts": facts,
            "mode": result.get("mode")
        }

# Helper for factory pattern
def get_knowledge_query_manager(workspace_id: Optional[str] = None) -> KnowledgeQueryManager:
    return KnowledgeQueryManager(workspace_id=workspace_id)

@router.post("/query")
async def knowledge_query(
    request: KnowledgeQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Natural language query endpoint for the knowledge graph.
    Requires authentication.
    """
    try:
        manager = get_knowledge_query_manager(request.workspace_id)
        result = await manager.answer_query(request.query, user_id=request.user_id, workspace_id=request.workspace_id)
        return {"success": True, "answer": result.get("answer"), "relevant_facts": result.get("relevant_facts"), "mode": result.get("mode")}
    except Exception as e:
        logger.error(f"Knowledge query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
