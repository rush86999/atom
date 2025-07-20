import logging
import os
from typing import List, Dict, Any, Optional, Literal

from pydantic import BaseModel, Field
from datetime import datetime

# Assuming these modules are in the same directory or accessible via PYTHONPATH
try:
    import lancedb_search_service
    import meilisearch_handler
    import lancedb_handler
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
    meili_client: Optional[Any] = None, # Meilisearch client, passed in
    semantic_limit: int = 5,
    keyword_limit: int = 10,
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
                        db_conn=db_conn, query_vector=query_vector, user_id=user_id,
                        filters=filters if filters else {}, limit_total=semantic_limit
                    )
                except Exception as e_lance:
                    logger.error(f"Error during LanceDB search: {e_lance}", exc_info=True)
        else:
            logger.error(f"Failed to generate query embedding for semantic search: {embedding_response.get('message')}")

    # 2. Keyword Search (Meilisearch)
    if keyword_limit > 0:
        logger.info(f"Performing keyword search for query: '{query_text}' with limit: {keyword_limit}")
        if not meili_client: meili_client = meilisearch_handler.get_meilisearch_client()
        if meili_client:
            # Build Meilisearch filter string from the unified filter object
            meili_filter_string = _build_meilisearch_filter_string(filters) if filters else ""

            meili_search_params = {'limit': keyword_limit}
            if meili_filter_string:
                meili_search_params['filter'] = meili_filter_string

            try:
                keyword_hits_response = await meilisearch_handler.search_in_index(
                    index_name="atom_general_documents", query=query_text, search_params=meili_search_params
                )
                if keyword_hits_response.get("status") == "success":
                    keyword_hits_raw = keyword_hits_response.get("data", {}).get("hits", [])
                else:
                    logger.error(f"Meilisearch search failed: {keyword_hits_response.get('message')}")
            except Exception as e_meili:
                logger.error(f"Error during Meilisearch search: {e_meili}", exc_info=True)

    # 3. Process and Fuse Results
    # Process semantic results first to prioritize their metadata if a doc is in both lists
    for i, hit in enumerate(semantic_hits_raw):
        doc_id = hit.get('doc_id')
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

    # Process keyword results
    for i, hit in enumerate(keyword_hits_raw):
        doc_id = hit.get('doc_id')
        if not doc_id: continue

        # Add to RRF score
        rank = i + 1
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1 / (RRF_K + rank))

        # If seen for the first time, store it. If already present from semantic, update match_type
        if doc_id in all_results_map:
            all_results_map[doc_id].match_type = 'hybrid'
        else:
            consolidated_additional_props = {}
            if hit.get('metadata_json') and isinstance(hit.get('metadata_json'), str):
                try: consolidated_additional_props = json.loads(hit['metadata_json'])
                except json.JSONDecodeError: pass
            for k, v in hit.items():
                if k not in UnifiedSearchResultItem.model_fields and k not in consolidated_additional_props:
                    consolidated_additional_props[k] = v

            all_results_map[doc_id] = UnifiedSearchResultItem(
                doc_id=doc_id, user_id=hit.get('user_id', user_id), title=hit.get('title'),
                snippet=hit.get('_formatted', {}).get('extracted_text') or hit.get('_formatted', {}).get('title'),
                source_uri=hit.get('source_uri'), doc_type=hit.get('doc_type'),
                created_at_source=ensure_datetime(hit.get('created_at_source')),
                last_modified_source=ensure_datetime(hit.get('last_modified_source')),
                ingested_at=ensure_datetime(hit.get('ingested_at')) or datetime.now(),
                score=hit.get('_rankingScore'), match_type='keyword',
                extracted_text_preview=(hit.get('extracted_text')[:500] + '...') if hit.get('extracted_text') and len(hit.get('extracted_text')) > 500 else hit.get('extracted_text'),
                additional_properties=consolidated_additional_props
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

def _build_meilisearch_filter_string(filters: Dict[str, Any]) -> str:
    """
    Constructs a filter string for Meilisearch from a filter dictionary.
    """
    filter_parts = []

    # Handle doc_types
    if 'doc_types' in filters and filters['doc_types']:
        types_str = ', '.join([f'"{t}"' for t in filters['doc_types']])
        filter_parts.append(f'doc_type IN [{types_str}]')

    # Handle date filters
    date_field = filters.get('date_field_to_filter', 'ingested_at')
    meili_date_field = f"{date_field}_timestamp" # Meilisearch will use the timestamp version

    if 'date_after' in filters and filters['date_after']:
        try:
            dt = datetime.fromisoformat(filters['date_after'].replace("Z", "+00:00"))
            timestamp = int(dt.timestamp())
            filter_parts.append(f'{meili_date_field} >= {timestamp}')
        except (ValueError, TypeError):
            logger.warning(f"Could not parse date_after filter: {filters['date_after']}")

    if 'date_before' in filters and filters['date_before']:
        try:
            dt = datetime.fromisoformat(filters['date_before'].replace("Z", "+00:00"))
            timestamp = int(dt.timestamp())
            filter_parts.append(f'{meili_date_field} <= {timestamp}')
        except (ValueError, TypeError):
            logger.warning(f"Could not parse date_before filter: {filters['date_before']}")

    # Handle metadata_properties
    if 'metadata_properties' in filters and isinstance(filters['metadata_properties'], dict):
        for key, value in filters['metadata_properties'].items():
            # Basic sanitization for key and value
            # This assumes keys are valid attribute names in Meilisearch
            if isinstance(value, str):
                # Escape double quotes in the value string
                sanitized_value = value.replace('"', '\\"')
                filter_parts.append(f'{key} = "{sanitized_value}"')
            elif isinstance(value, (int, float)):
                filter_parts.append(f'{key} = {value}')
            elif isinstance(value, bool):
                filter_parts.append(f'{key} = {"true" if value else "false"}')

    return ' AND '.join(filter_parts)

def _build_lancedb_filter_clause(filters: Dict[str, Any]) -> str:
    """
    Constructs a SQL WHERE clause for LanceDB from a filter dictionary.
    NOTE: This implementation only supports top-level fields like doc_type and dates.
    It does NOT support filtering on the nested metadata_json field.
    """
    filter_parts = []

    # Handle doc_types
    if 'doc_types' in filters and filters['doc_types']:
        # Ensure values are sanitized to prevent SQL injection, although these are internal values.
        # Using f-strings is generally safe here as the inputs are from our defined structure, not raw user input.
        types_str = ', '.join([f"'{t}'" for t in filters['doc_types']])
        filter_parts.append(f'doc_type IN ({types_str})')

    # Handle date filters
    date_field = filters.get('date_field_to_filter', 'ingested_at')

    if 'date_after' in filters and filters['date_after']:
        # LanceDB can compare ISO 8601 strings directly in SQL
        date_str = filters['date_after']
        filter_parts.append(f"{date_field} >= '{date_str}'")

    if 'date_before' in filters and filters['date_before']:
        date_str = filters['date_before']
        filter_parts.append(f"{date_field} <= '{date_str}'")

    # metadata_properties is intentionally ignored for LanceDB as filtering
    # on a JSON string field is not efficient or standard in LanceDB's SQL.
    if 'metadata_properties' in filters and filters['metadata_properties']:
        logger.warning("Filtering by 'metadata_properties' is not supported for LanceDB search and will be ignored.")

    return ' AND '.join(filter_parts)
