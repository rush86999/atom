import logging
import os
from typing import List, Dict, Any, Optional, Literal

from pydantic import BaseModel, Field
from datetime import datetime

# Assuming these modules are in the same directory or accessible via PYTHONPATH
try:
    from . import lancedb_search_service
    from . import lancedb_handler # For DB connection if needed by lancedb_search_service directly
    # For embedding the query for LanceDB search
    # Adjust path if note_utils is located differently relative to this new service.
    # It's in 'project/functions/' so this might need sys.path adjustment if not already handled by runtime env.
    import sys
    FUNCTIONS_DIR_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'project', 'functions'))
    if FUNCTIONS_DIR_PATH not in sys.path:
        sys.path.append(FUNCTIONS_DIR_PATH)
    from note_utils import get_text_embedding_openai

except ImportError as e:
    logging.getLogger(__name__).error(f"Failed to import dependencies for HybridSearchService: {e}", exc_info=True)
    # Define mocks or raise if critical dependencies are missing
    # For now, let the program fail on import if they are truly missing at runtime and essential.
    raise


logger = logging.getLogger(__name__)

# --- Unified Search Result Model ---
class UnifiedSearchResultItem(BaseModel):
    doc_id: str
    user_id: str # For context, though might not always be directly filterable by agent
    title: Optional[str] = None
    snippet: Optional[str] = None # Could be chunk text from LanceDB or highlighted snippet from Meili
    source_uri: Optional[str] = None
    doc_type: Optional[str] = None
    created_at_source: Optional[datetime] = None
    last_modified_source: Optional[datetime] = None
    ingested_at: datetime
    score: Optional[float] = None # RRF score for final ranking
    match_type: Literal['semantic', 'keyword', 'hybrid']
    extracted_text_preview: Optional[str] = Field(None, max_length=500) # Short preview of full text for keyword matches
    additional_properties: Optional[Dict[str, Any]] = None # For other metadata

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
        # For Pydantic V2, use model_config = {"json_encoders": ...} if migrating later

async def hybrid_search_documents(
    user_id: str,
    query_text: str,
    openai_api_key_param: Optional[str] = None, # For generating query embedding
    db_conn: Optional[Any] = None, # LanceDB connection, passed in
    semantic_limit: int = 5,
    filters: Optional[Dict[str, Any]] = None # Common filters, needs mapping
) -> List[UnifiedSearchResultItem]:
    """
    Performs a hybrid search by combining results from LanceDB (semantic)
    and Meilisearch (keyword).
    """
    # --- RRF Implementation ---
    RRF_K = 60  # RRF constant
    rrf_scores: Dict[str, float] = {}
    all_results_map: Dict[str, UnifiedSearchResultItem] = {}

    semantic_hits_raw = []
    keyword_hits_raw = []

    # 1. Semantic Search (LanceDB)
    if semantic_limit > 0:
        logger.info(f"Performing semantic search for query: '{query_text}' with limit: {semantic_limit}")
        embedding_response = get_text_embedding_openai(text_to_embed=query_text, openai_api_key_param=openai_api_key_param)
        if embedding_response.get("status") == "success":
            query_vector = embedding_response["data"]
            if not db_conn: db_conn = await lancedb_handler.get_lancedb_connection()
            if db_conn:
                # Pass the filters dictionary directly to the service.
                # The service is responsible for interpreting the keys it understands (e.g., date_after, doc_type_filter).
                try:
                    semantic_hits_raw = await lancedb_search_service.search_lancedb_all(
                        db_conn=db_conn, query_vector=query_vector, query_text=query_text, user_id=user_id,
                        filters=filters if filters else {}, limit_total=semantic_limit
                    )
                    print(f"semantic_hits_raw: {semantic_hits_raw}")
                except Exception as e_lance:
                    logger.error(f"Error during LanceDB search: {e_lance}", exc_info=True)
        else:
            logger.error(f"Failed to generate query embedding for semantic search: {embedding_response.get('message')}")


    # 3. Process and Fuse Results
    # Process semantic results first to prioritize their metadata if a doc is in both lists
    for i, hit in enumerate(semantic_hits_raw):
        doc_id = hit.get('id')
        if not doc_id: continue

        # Add to RRF score
        rank = i + 1
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1 / (RRF_K + rank))

        # Store the unified item if not already seen
        if doc_id not in all_results_map:
            additional_props_dict = {}
            if hit.get('metadata_json') and isinstance(hit.get('metadata_json'), str):
                try: additional_props_dict = json.loads(hit['metadata_json'])
                except json.JSONDecodeError: pass

            all_results_map[doc_id] = UnifiedSearchResultItem(
                doc_id=doc_id, user_id=user_id, title=hit.get('title'),
                snippet=hit.get('text_content') or hit.get('snippet'),
                source_uri=hit.get('source_uri') or hit.get('document_source_uri'),
                doc_type=hit.get('doc_type') or hit.get('document_doc_type'),
                created_at_source=ensure_datetime(hit.get('created_at_source')),
                last_modified_source=ensure_datetime(hit.get('last_modified_source')),
                ingested_at=ensure_datetime(hit.get('ingested_at')) or datetime.now(),
                score=hit.get('score'), match_type='semantic',
                additional_properties=additional_props_dict
            )


    # 4. Combine, Sort, and Finalize
    final_results = list(all_results_map.values())

    # Update score to RRF score before sorting
    for item in final_results:
        item.score = rrf_scores.get(item.doc_id, 0.0)

    final_results.sort(key=lambda x: x.score, reverse=True)

    return final_results

# Helper to ensure datetime objects for Pydantic model
def ensure_datetime(dt_val: Any) -> Optional[datetime]:
    if isinstance(dt_val, datetime):
        return dt_val
    if isinstance(dt_val, str):
        try:
            return datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None

# Need to import json for parsing metadata_json strings from search results
import json

