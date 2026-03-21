"""
GraphRAG API Routes - Phase 42
Endpoints for GraphRAG queries.
"""

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from core.base_routes import BaseAPIRouter

router = BaseAPIRouter(prefix="/api/graphrag", tags=["GraphRAG"])

class IngestRequest(BaseModel):
    doc_id: str
    text: str
    source: str = "api"
    user_id: str = "default_user"

class QueryRequest(BaseModel):
    query: str
    workspace_id: str = "default_workspace"
    mode: str = "auto"  # auto, global, local

class AddEntityRequest(BaseModel):
    name: str = Field(..., description="Entity name")
    type: str = Field(..., description="Entity type")
    description: str = Field("", description="Entity description")
    properties: Dict[str, Any] = Field(default_factory=dict)

class AddRelationshipRequest(BaseModel):
    from_entity: str = Field(..., description="Source entity name or ID")
    to_entity: str = Field(..., description="Target entity name or ID")
    relationship_type: str = Field(..., description="Relationship type")
    description: str = Field("", description="Relationship description")
    properties: Dict[str, Any] = Field(default_factory=dict)

@router.post("/ingest")
async def ingest_document(request: IngestRequest):
    """Ingest a document into GraphRAG"""
    from core.graphrag_engine import graphrag_engine

    graphrag_engine.ingest_document(
        workspace_id=request.user_id,
        doc_id=request.doc_id,
        text=request.text,
        source=request.source
    )
    return router.success_response(
        message="Document ingested successfully"
    )

@router.get("/entities")
async def list_entities(workspace_id: str, limit: int = 100):
    """List entities in the knowledge graph"""
    from core.database import get_db_session
    from core.models import GraphNode
    
    with get_db_session() as session:
        entities = session.query(GraphNode).filter_by(workspace_id=workspace_id).limit(limit).all()
        return router.success_response(
            data={"entities": [
                {"id": e.id, "name": e.name, "type": e.type, "description": e.description, "properties": e.properties}
                for e in entities
            ]}
        )

@router.post("/entities")
async def add_entity(workspace_id: str, request: AddEntityRequest):
    """Add or update an entity"""
    from core.graphrag_engine import graphrag_engine, Entity
    import uuid
    
    entity = Entity(
        id=str(uuid.uuid4()),
        name=request.name,
        entity_type=request.type,
        description=request.description,
        properties=request.properties
    )
    
    entity_id = graphrag_engine.add_entity(entity, workspace_id)
    if not entity_id:
        return router.error_response("INGESTION_FAILED", "Failed to add entity", status_code=500)
        
    return router.success_response(
        data={"id": entity_id},
        message="Entity added successfully"
    )

@router.get("/canonical-search")
async def canonical_search(workspace_id: str, type: str, q: str):
    """Search for existing DB records to anchor graph nodes"""
    from core.graphrag_engine import graphrag_engine
    
    results = graphrag_engine.canonical_search(workspace_id, type, q)
    return router.success_response(
        data={"results": results}
    )

@router.get("/relationships")
async def list_relationships(workspace_id: str, limit: int = 200):
    """List relationships in the knowledge graph"""
    from core.database import get_db_session
    from core.models import GraphEdge, GraphNode
    
    with get_db_session() as session:
        edges = session.query(GraphEdge).filter_by(workspace_id=workspace_id).limit(limit).all()
        
        # Map source/target IDs to names if possible
        node_ids = set()
        for e in edges:
            node_ids.add(e.source_node_id)
            node_ids.add(e.target_node_id)
            
        nodes = session.query(GraphNode).filter(GraphNode.id.in_(list(node_ids))).all()
        node_map = {n.id: n.name for n in nodes}
        
        return router.success_response(
            data={"relationships": [
                {
                    "id": e.id, 
                    "from_entity": node_map.get(e.source_node_id, e.source_node_id),
                    "to_entity": node_map.get(e.target_node_id, e.target_node_id),
                    "type": e.relationship_type,
                    "properties": e.properties
                }
                for e in edges
            ]}
        )

@router.post("/relationships")
async def add_relationship(workspace_id: str, request: AddRelationshipRequest):
    """Add a relationship between entities"""
    from core.graphrag_engine import graphrag_engine, Relationship
    from core.database import get_db_session
    from core.models import GraphNode
    import uuid
    
    with get_db_session() as session:
        # Resolve names to IDs
        src = session.query(GraphNode).filter_by(workspace_id=workspace_id, name=request.from_entity).first()
        dst = session.query(GraphNode).filter_by(workspace_id=workspace_id, name=request.to_entity).first()
        
        if not src:
            src = session.query(GraphNode).filter_by(workspace_id=workspace_id, id=request.from_entity).first()
        if not dst:
            dst = session.query(GraphNode).filter_by(workspace_id=workspace_id, id=request.to_entity).first()
            
        if not src or not dst:
            return router.error_response("NOT_FOUND", "Source or target entity not found", status_code=404)
            
        rel = Relationship(
            id=str(uuid.uuid4()),
            from_entity=src.id,
            to_entity=dst.id,
            rel_type=request.relationship_type,
            description=request.description,
            properties=request.properties
        )
        
        rel_id = graphrag_engine.add_relationship(rel, workspace_id)
        if not rel_id:
            return router.error_response("INGESTION_FAILED", "Failed to add relationship", status_code=500)
            
        return router.success_response(
            data={"id": rel_id},
            message="Relationship added successfully"
        )

@router.post("/build-communities")
async def build_communities(user_id: str):
    """Build communities for a user"""
    from core.graphrag_engine import graphrag_engine

    count = graphrag_engine.build_communities(user_id)
    return router.success_response(
        data={"user_id": user_id},
        message=f"Built {count} communities"
    )

@router.post("/query")
async def query_graphrag(request: QueryRequest):
    """Query GraphRAG (global or local search)"""
    from core.graphrag_engine import graphrag_engine

    result = graphrag_engine.query(request.workspace_id, request.query, request.mode)
    return router.success_response(
        data=result,
        message="Query executed successfully"
    )

@router.get("/entities/{entity_id}/neighbors")
async def get_entity_neighbors(workspace_id: str, entity_id: str, depth: int = 1):
    """Get the neighborhood of an entity"""
    from core.graphrag_engine import graphrag_engine
    from core.database import get_db_session
    from core.models import GraphNode
    
    with get_db_session() as session:
        entity = session.query(GraphNode).filter_by(workspace_id=workspace_id, id=entity_id).first()
        if not entity:
            return router.error_response("NOT_FOUND", "Entity not found", status_code=404)
            
        result = graphrag_engine.local_search(workspace_id, entity.name, depth=depth)
        return router.success_response(
            data=result,
            message="Neighborhood retrieved successfully"
        )

@router.get("/context")
async def get_ai_context(user_id: str, query: str):
    """Get context for AI nodes"""
    from core.graphrag_engine import get_graphrag_context

    context = get_graphrag_context(user_id, query)
    return router.success_response(
        data={"user_id": user_id, "context": context},
        message="Context retrieved successfully"
    )

@router.get("/stats")
async def get_stats(user_id: str = None):
    """Get GraphRAG stats"""
    from core.graphrag_engine import graphrag_engine

    result = graphrag_engine.get_stats(user_id)
    return router.success_response(
        data=result,
        message="Stats retrieved successfully"
    )
