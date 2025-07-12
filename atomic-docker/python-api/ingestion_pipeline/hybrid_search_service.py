import logging
import os
from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field
from datetime import datetime

# Assuming these modules are in the same directory or accessible via PYTHONPATH
try:
    from . import lancedb_search_service
    from . import meilisearch_handler
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
    score: Optional[float] = None # Original score from the source system
    match_type: str # 'semantic' or 'keyword'
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
    final_results: List[UnifiedSearchResultItem] = []
    semantic_doc_ids = set()

    # 1. Semantic Search (LanceDB)
    if semantic_limit > 0:
        logger.info(f"Performing semantic search for query: '{query_text}' with limit: {semantic_limit}")
        embedding_response = get_text_embedding_openai(
            text_to_embed=query_text,
            openai_api_key_param=openai_api_key_param
        )
        if embedding_response.get("status") != "success":
            logger.error(f"Failed to generate query embedding for semantic search: {embedding_response.get('message')}")
            # Depending on desired behavior, could return empty or raise error
        else:
            query_vector = embedding_response["data"]

            # Ensure db_conn is available; if not passed, try to get one.
            # This depends on how lancedb_search_service expects its connection.
            # For now, assume db_conn is passed or lancedb_search_service handles it.
            if not db_conn:
                 current_db_conn = await lancedb_handler.get_lancedb_connection()
                 if not current_db_conn:
                     logger.error("Failed to get LanceDB connection for semantic search.")
                     # Handle error or proceed without semantic results
                 else:
                     db_conn = current_db_conn # Use the fetched connection

            if db_conn: # Proceed only if connection is available
                # Note: lancedb_search_service.search_lancedb_all expects filters in a specific format.
                # The 'filters' param here is generic; mapping might be needed.
                # For simplicity, this example assumes filters for LanceDB are handled by search_lancedb_all or are basic.
                # search_lancedb_all returns a list of dicts that should conform to UniversalSearchResultItem
                # from lancedb_search_service, which is slightly different from our UnifiedSearchResultItem here.
                # We need to map them.

                # TODO: Adapt filters for lancedb_search_service.search_lancedb_all
                # For now, passing a simplified or potentially empty filter dict.
                lancedb_filters = filters.get("lancedb_filters", {}) if filters else {}


                try:
                    semantic_hits_raw = await lancedb_search_service.search_lancedb_all(
                        db_conn=db_conn,
                        query_vector=query_vector,
                        user_id=user_id,
                        filters=lancedb_filters, # Pass mapped filters
                        limit_total=semantic_limit
                    )

                    for hit in semantic_hits_raw:
                        # Map lancedb_search_service.UniversalSearchResultItem to UnifiedSearchResultItem
                        # Assuming 'hit' is a dict from search_lancedb_all
                        # Key fields to map: doc_id, title, source_uri, doc_type, score, ingested_at, text_content for snippet
                        # Also need to handle additional_properties if present in hit['metadata_json']

                        # Parse metadata_json if it exists in the hit
                        additional_props_dict = {}
                        if hit.get('metadata_json') and isinstance(hit.get('metadata_json'), str):
                            try:
                                additional_props_dict = json.loads(hit['metadata_json'])
                            except json.JSONDecodeError:
                                logger.warning(f"Could not parse metadata_json for doc_id {hit.get('doc_id')} from LanceDB result.")

                        unified_item = UnifiedSearchResultItem(
                            doc_id=hit.get('doc_id', 'unknown_lancedb_id'), # Ensure doc_id is present
                            user_id=user_id, # user_id is part of the query, not always in hit directly
                            title=hit.get('title'),
                            snippet=hit.get('text_content') or hit.get('snippet'), # Use text_content as snippet
                            source_uri=hit.get('source_uri') or hit.get('document_source_uri'),
                            doc_type=hit.get('doc_type') or hit.get('document_doc_type'),
                            # Ensure datetime fields are correctly parsed if they are strings
                            created_at_source=datetime.fromisoformat(hit['created_at_source']) if hit.get('created_at_source') and isinstance(hit['created_at_source'], str) else hit.get('created_at_source'),
                            last_modified_source=datetime.fromisoformat(hit['last_modified_source']) if hit.get('last_modified_source') and isinstance(hit['last_modified_source'], str) else hit.get('last_modified_source'),
                            ingested_at=datetime.fromisoformat(hit['ingested_at']) if hit.get('ingested_at') and isinstance(hit['ingested_at'], str) else hit.get('ingested_at', datetime.now()), # Fallback for ingested_at
                            score=hit.get('score'),
                            match_type='semantic',
                            extracted_text_preview=None, # Not typically available from chunk-based semantic search directly
                            additional_properties=additional_props_dict
                        )
                        final_results.append(unified_item)
                        semantic_doc_ids.add(unified_item.doc_id)
                    logger.info(f"Retrieved {len(final_results)} semantic results.")
                except Exception as e_lance:
                    logger.error(f"Error during LanceDB search: {e_lance}", exc_info=True)


    # 2. Keyword Search (Meilisearch)
    if keyword_limit > 0:
        logger.info(f"Performing keyword search for query: '{query_text}' with limit: {keyword_limit}")

        if not meili_client:
            current_meili_client = meilisearch_handler.get_meilisearch_client()
            if not current_meili_client:
                logger.error("Failed to get Meilisearch client for keyword search.")
                # Handle error or proceed without keyword results
            else:
                meili_client = current_meili_client

        if meili_client: # Proceed only if client is available
            # TODO: Adapt filters for Meilisearch (e.g., 'filter' string format)
            # For now, passing a simplified or potentially empty filter dict for Meili.
            meili_search_params = {'limit': keyword_limit}
            if filters and filters.get("meilisearch_filter_string"):
                meili_search_params['filter'] = filters["meilisearch_filter_string"]

            try:
                keyword_hits_response = await meilisearch_handler.search_in_index(
                    index_name=meilisearch_handler.MEILISEARCH_INDEX_NAME, # Assuming a default index name in handler or config
                    query=query_text,
                    search_params=meili_search_params
                )

                if keyword_hits_response.get("status") == "success":
                    keyword_hits_raw = keyword_hits_response.get("data", {}).get("hits", [])
                    for hit in keyword_hits_raw:
                        if hit.get('doc_id') not in semantic_doc_ids: # De-duplication
                            # Meilisearch hits are typically dicts of the stored document.
                            # The 'extracted_text' field itself might be large.
                            # Meilisearch can also return formatted snippets if requested in search_params.

                            # If 'metadata_json' (string) is in the hit, parse it for additional_properties
                            additional_props_meili = {}
                            if hit.get('metadata_json') and isinstance(hit.get('metadata_json'), str):
                                try:
                                    additional_props_meili = json.loads(hit['metadata_json'])
                                except json.JSONDecodeError:
                                     logger.warning(f"Could not parse metadata_json for doc_id {hit.get('doc_id')} from Meili result.")
                            # If metadata fields are already flat in the Meili document, they'll be in 'hit' directly.
                            # We should merge 'hit' fields with what 'additional_props_meili' might contain.
                            # For UnifiedSearchResultItem, we prefer specific fields and then dump others into additional_properties.

                            # Consolidate additional properties: start with parsed metadata_json, then update with other hit fields
                            # that are not already top-level fields in UnifiedSearchResultItem.
                            consolidated_additional_props = additional_props_meili.copy()
                            for k, v in hit.items():
                                if k not in UnifiedSearchResultItem.model_fields and k not in consolidated_additional_props:
                                     consolidated_additional_props[k] = v


                            unified_item = UnifiedSearchResultItem(
                                doc_id=hit.get('doc_id', 'unknown_meili_id'),
                                user_id=hit.get('user_id', user_id), # Meili doc should have user_id
                                title=hit.get('title'),
                                snippet=hit.get('_formatted', {}).get('extracted_text') or hit.get('_formatted', {}).get('title'), # Example if using highlights
                                source_uri=hit.get('source_uri'),
                                doc_type=hit.get('doc_type'),
                                created_at_source=datetime.fromisoformat(hit['created_at_source']) if hit.get('created_at_source') and isinstance(hit['created_at_source'], str) else hit.get('created_at_source'),
                                last_modified_source=datetime.fromisoformat(hit['last_modified_source']) if hit.get('last_modified_source') and isinstance(hit['last_modified_source'], str) else hit.get('last_modified_source'),
                                ingested_at=datetime.fromisoformat(hit['ingested_at']) if hit.get('ingested_at') and isinstance(hit['ingested_at'], str) else hit.get('ingested_at', datetime.now()), # Fallback for ingested_at
                                score=hit.get('_rankingScore'), # Meilisearch internal score
                                match_type='keyword',
                                extracted_text_preview=(hit.get('extracted_text')[:500] + '...') if hit.get('extracted_text') and len(hit.get('extracted_text')) > 500 else hit.get('extracted_text'),
                                additional_properties=consolidated_additional_props
                            )
                            final_results.append(unified_item)
                    logger.info(f"Retrieved {len(keyword_hits_raw)} keyword results, added {len(final_results) - len(semantic_doc_ids)} new results after de-duplication.")
                else:
                    logger.error(f"Meilisearch search failed: {keyword_hits_response.get('message')}")
            except Exception as e_meili:
                logger.error(f"Error during Meilisearch search: {e_meili}", exc_info=True)

    # TODO: Implement re-ranking if desired in the future.
    # For now, results are semantic first, then unique keyword results.

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

```
