import os
import logging
import lancedb
import asyncio
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime, timezone

# Assuming lancedb_handler.py is in the same directory or path is adjusted
try:
    from .lancedb_handler import (
        get_lancedb_connection,
        create_or_open_table,
        DocumentChunkModel,
        EmailSnippetModel,
        NotionPageSummaryModel,
        DOCUMENTS_TABLE_NAME, # For fetching parent doc title
        DOCUMENT_CHUNKS_TABLE_NAME,
        EMAIL_SNIPPETS_TABLE_NAME,
        NOTION_SUMMARIES_TABLE_NAME,
        EMBEDDING_DIMENSION # Though not directly used here, good for context
    )
except ImportError:
    # Fallback for direct execution or if paths differ
    from lancedb_handler import (
        get_lancedb_connection,
        create_or_open_table,
        DocumentChunkModel,
        EmailSnippetModel,
        NotionPageSummaryModel,
        DOCUMENTS_TABLE_NAME,
        DOCUMENT_CHUNKS_TABLE_NAME,
        EMAIL_SNIPPETS_TABLE_NAME,
        NOTION_SUMMARIES_TABLE_NAME,
        EMBEDDING_DIMENSION
    )


logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

SearchResultSourceType = Literal["document_chunk", "email_snippet", "notion_summary"]

class UniversalSearchResultItem(Dict): # Using Dict as base for TypedDict-like behavior
    id: str
    user_id: str
    source_type: SearchResultSourceType
    title: str
    snippet: str
    vector_score: float
    original_url_or_link: Optional[str]
    created_at: Optional[str] # ISO 8601
    last_modified_at: Optional[str] # ISO 8601
    ingested_at: Optional[str] # ISO 8601

    # Document specific
    document_id: Optional[str]
    parent_document_title: Optional[str]
    chunk_sequence: Optional[int]
    document_source_uri: Optional[str]
    document_doc_type: Optional[str]

    # Email specific
    email_thread_id: Optional[str]
    email_from_sender: Optional[str]
    email_date: Optional[str] # ISO 8601

    # Notion specific
    notion_icon_json: Optional[str]

    metadata_json: Optional[str]


async def _search_single_table(
    db_conn: lancedb.DBConnection,
    table_name: str,
    schema: Any, # Pydantic LanceModel
    query_vector: List[float],
    user_id: str,
    filters: Optional[Dict[str, Any]], # Table-specific filters
    limit: int,
    source_type_label: SearchResultSourceType
) -> List[UniversalSearchResultItem]:
    """Helper to search a single LanceDB table and map results."""
    if not query_vector: return []

    table = await create_or_open_table(db_conn, table_name, schema=schema)
    if not table:
        logger.warning(f"Could not open or create table {table_name} for searching.")
        return []

    search_req = table.search(query_vector).limit(limit)

    # Basic user_id filter (always apply)
    filter_str = f"user_id = '{user_id}'"

    # Apply additional filters
    if filters:
        date_after = filters.get("date_after")
        date_before = filters.get("date_before")

        # Determine the timestamp field for filtering based on source type
        timestamp_field_for_filtering = None
        if source_type_label == "email_snippet":
            timestamp_field_for_filtering = "email_date" # Assumes this field exists and is datetime in LanceDB
        elif source_type_label == "notion_summary":
            # Prefer last_edited_time_source, fallback to created_time_source.
            # These need to be filterable timestamps in LanceDB (e.g. int64 microseconds).
            # This example assumes last_edited_time_source is the primary one to filter on.
            timestamp_field_for_filtering = "last_edited_time_source"
        elif source_type_label == "document_chunk":
            # Document chunks themselves don't have inherent creation/modification dates
            # suitable for typical user-facing date filters. Filtering would usually be
            # on the parent document's dates, which requires denormalization onto chunks
            # or a join capability not used here for simple LanceDB filtering.
            # The original code attempted to use 'ingested_at' from DocumentChunkModel,
            # which might not be what users expect for "document date".
            # For now, we explicitly disable direct date_after/date_before filtering on chunks
            # unless a clear, chunk-specific filterable date field is defined and intended.
            # If 'ingested_at' on chunks *is* desired for filtering, this logic can be changed.
            logger.debug(f"Date filtering (date_after/date_before) for source_type 'document_chunk' is currently not applied directly to chunks. Filter by parent document date if implemented via denormalization or pre-filtering of doc_ids.")
            pass # No default timestamp field for document_chunk for date_after/before filters

        if timestamp_field_for_filtering and (date_after or date_before):
            # Ensure the field is valid for the current schema (conceptual check)
            # In a real system, you might introspect schema or have a predefined map.
            # For now, we assume the chosen field is correctly stored as filterable timestamp (microseconds)

            if date_after:
                try:
                    # Handle date-only strings by assuming start of day UTC
                    dt_after_str = date_after if 'T' in date_after else f"{date_after}T00:00:00"
                    # Assume UTC if no explicit timezone offset
                    if not date_after.endswith("Z") and "+" not in date_after[10:] and "-" not in date_after[10:]:
                        dt_after_str += "Z"

                    dt_obj_after = datetime.fromisoformat(dt_after_str.replace("Z", "+00:00"))
                    filter_str += f" AND {timestamp_field_for_filtering} >= {int(dt_obj_after.timestamp() * 1_000_000)}"
                except ValueError as ve:
                    logger.warning(f"Invalid date_after format: '{date_after}'. Error: {ve}")
            if date_before:
                try:
                    # Handle date-only strings by assuming end of day UTC
                    dt_before_str = date_before if 'T' in date_before else f"{date_before}T23:59:59.999999"
                     # Assume UTC if no explicit timezone offset
                    if not date_before.endswith("Z") and "+" not in date_before[10:] and "-" not in date_before[10:]:
                        dt_before_str += "Z"

                    dt_obj_before = datetime.fromisoformat(dt_before_str.replace("Z", "+00:00"))
                    filter_str += f" AND {timestamp_field_for_filtering} <= {int(dt_obj_before.timestamp() * 1_000_000)}"
                except ValueError as ve:
                    logger.warning(f"Invalid date_before format: '{date_before}'. Error: {ve}")
        elif (date_after or date_before) and not timestamp_field_for_filtering:
            # This case is hit if date filters are provided for a source_type (like document_chunk)
            # for which we haven't defined a timestamp_field_for_filtering.
            logger.warning(f"Date filters (date_after/date_before) provided for {source_type_label}, but no suitable timestamp field is configured for direct filtering on this source type.")

        if source_type_label == "document_chunk" and filters.get("doc_type_filter"):
            # This filter relies on 'parent_doc_type' being available in the DocumentChunkModel schema
            # or through a mechanism that makes it filterable for chunks.
            # If 'parent_doc_type' is not in DocumentChunkModel, this filter will fail at LanceDB query time.
            # This will be addressed in the 'parent document info' step.
            filter_str += f" AND parent_doc_type = '{filters['doc_type_filter']}'"

    if filter_str:
        logger.debug(f"Applying filter to {table_name}: {filter_str}")
        search_req = search_req.where(filter_str)

    raw_results = await asyncio.to_thread(search_req.to_list)
    logger.info(f"Search on {table_name} for user {user_id} returned {len(raw_results)} raw results.")

    parent_docs_metadata = {}
    if source_type_label == "document_chunk" and raw_results:
        doc_ids_to_fetch = list(set(r.get("doc_id") for r in raw_results if r.get("doc_id")))
        if doc_ids_to_fetch:
            try:
                # Assuming DocumentMetadataModel is available from lancedb_handler imports
                docs_table = await create_or_open_table(db_conn, DOCUMENTS_TABLE_NAME, schema=DocumentMetadataModel)
                if docs_table:
                    if len(doc_ids_to_fetch) == 1:
                        parent_filter_str = f"doc_id = '{doc_ids_to_fetch[0]}'"
                    else:
                        # Ensure doc_ids are properly quoted for the IN clause
                        quoted_doc_ids = [f"'{str(id_val)}'" for id_val in doc_ids_to_fetch]
                        parent_filter_str = f"doc_id IN ({', '.join(quoted_doc_ids)})"

                    logger.debug(f"Fetching parent document metadata with filter: {parent_filter_str}")
                    parent_docs_raw = await asyncio.to_thread(
                        docs_table.search() # No vector search needed, attribute lookup
                        .where(parent_filter_str)
                        .select(["doc_id", "title", "source_uri", "doc_type"]) # Select only needed fields
                        .to_list()
                    )
                    for p_doc in parent_docs_raw:
                        parent_docs_metadata[p_doc["doc_id"]] = p_doc
                else:
                    logger.warning(f"Could not open documents table '{DOCUMENTS_TABLE_NAME}' to fetch parent metadata.")
            except Exception as e_parent:
                logger.error(f"Error fetching parent document metadata: {e_parent}", exc_info=True)

    mapped_results: List[UniversalSearchResultItem] = []
    for record in raw_results:
        score = record.get("_distance", float('inf')) # LanceDB _distance, lower is better

        item: UniversalSearchResultItem = {
            "id": "", "user_id": record.get("user_id", user_id), "source_type": source_type_label,
            "title": "", "snippet": "", "vector_score": score,
        }

        if source_type_label == "document_chunk":
            item["id"] = record.get("chunk_id") or record.get("_rowid")
            item["snippet"] = record.get("text_content", "")
            doc_id = record.get("doc_id")
            item["document_id"] = doc_id
            item["chunk_sequence"] = record.get("chunk_sequence")

            parent_info = parent_docs_metadata.get(doc_id, {})
            parent_title = parent_info.get("title") # Use actual parent title if available
            if not parent_title: # Fallback if title is None or empty from parent_info
                 parent_title = f"Document {doc_id}"


            item["title"] = f"Chunk {record.get('chunk_sequence', 'N/A')} of \"{parent_title}\""
            item["parent_document_title"] = parent_title
            item["document_source_uri"] = parent_info.get("source_uri")
            # Use parent_doc_type from the chunk record itself (denormalized during ingestion)
            # Fallback to parent_info.get("doc_type") if somehow missing on chunk.
            item["document_doc_type"] = record.get("parent_doc_type") or parent_info.get("doc_type")

            # Timestamps for chunks generally refer to the parent document.
            # If 'ingested_at' is on the chunk schema, it's chunk ingestion time.
            # For created_at/last_modified_at, they should come from parent_info if needed here.
            # item["created_at"] = parent_info.get("created_at_source").isoformat() if parent_info.get("created_at_source") else None
            # item["last_modified_at"] = parent_info.get("last_modified_source").isoformat() if parent_info.get("last_modified_source") else None
            # ingested_at on the chunk record itself (if it exists in DocumentChunkModel schema)
            if "ingested_at" in record and hasattr(record["ingested_at"], 'isoformat'):
                 item["ingested_at"] = record["ingested_at"].isoformat()


        elif source_type_label == "email_snippet":
            item["id"] = record.get("email_id", "")
            item["title"] = record.get("subject", "No Subject")
            item["snippet"] = record.get("snippet_text", "")
            item["original_url_or_link"] = record.get("source_link")
            item["email_thread_id"] = record.get("thread_id")
            item["email_from_sender"] = record.get("from_sender")
            item["email_date"] = record.get("email_date").isoformat() if record.get("email_date") else None
            item["created_at"] = item["email_date"] # Email date is effectively its creation
            item["last_modified_at"] = item["email_date"] # Emails typically aren't "modified" in this context
            item["ingested_at"] = record.get("ingested_at").isoformat() if record.get("ingested_at") else None

        elif source_type_label == "notion_summary":
            item["id"] = record.get("notion_page_id", "")
            item["title"] = record.get("title", "Untitled Notion Page")
            item["snippet"] = record.get("preview_text", "")
            item["original_url_or_link"] = record.get("notion_url")
            item["notion_icon_json"] = record.get("icon_json") # Already a string
            item["created_at"] = record.get("created_time_source").isoformat() if record.get("created_time_source") else None
            item["last_modified_at"] = record.get("last_edited_time_source").isoformat() if record.get("last_edited_time_source") else None
            item["ingested_at"] = record.get("ingested_at").isoformat() if record.get("ingested_at") else None

        mapped_results.append(item)
    return mapped_results

async def search_lancedb_all(
    db_conn: lancedb.DBConnection,
    query_vector: List[float],
    user_id: str,
    filters: Optional[Dict[str, Any]] = None,
    limit_total: int = 10
) -> List[UniversalSearchResultItem]:
    """
    Searches across multiple configured LanceDB tables, combines, and re-ranks results.
    """
    if not filters: filters = {}

    # Determine which sources to search based on filters or default to all
    source_types_to_search = filters.get("source_types", ["document_chunk", "email_snippet", "notion_summary"])

    # Distribute limit: e.g., if limit_total is 10 and 3 sources, search ~3-4 from each.
    # A more sophisticated approach might weight this.
    limit_per_source = (limit_total // len(source_types_to_search)) + (limit_total % len(source_types_to_search) > 0)
    limit_per_source = max(1, limit_per_source) # Ensure at least 1

    all_results: List[UniversalSearchResultItem] = []

    search_tasks = []

    if "document_chunk" in source_types_to_search:
        # Optimization: If searching document_chunks, fetch parent doc titles first if filtering by doc_type or for display
        # This is complex as it requires knowing which doc_ids will result from chunk search.
        # For now, parent_doc_titles will be simple or fetched post-hoc if needed by _search_single_table.
        # Or, the `title` for document_chunk results can be "Chunk X from Doc Y" and parent_document_title can be fetched later by consumer.
        # Let's keep it simple: parent_doc_titles is not pre-fetched here.
        search_tasks.append(
            _search_single_table(db_conn, DOCUMENT_CHUNKS_TABLE_NAME, DocumentChunkModel,
                                 query_vector, user_id, filters, limit_per_source, "document_chunk")
        )
    if "email_snippet" in source_types_to_search:
        search_tasks.append(
            _search_single_table(db_conn, EMAIL_SNIPPETS_TABLE_NAME, EmailSnippetModel,
                                 query_vector, user_id, filters, limit_per_source, "email_snippet")
        )
    if "notion_summary" in source_types_to_search:
        search_tasks.append(
            _search_single_table(db_conn, NOTION_SUMMARIES_TABLE_NAME, NotionPageSummaryModel,
                                 query_vector, user_id, filters, limit_per_source, "notion_summary")
        )

    gathered_results = await asyncio.gather(*search_tasks)
    for result_list in gathered_results:
        all_results.extend(result_list)

    # Re-sort all collected results by vector_score (LanceDB _distance, lower is better)
    all_results.sort(key=lambda x: x["vector_score"])

    return all_results[:limit_total]

# Example usage (conceptual, would be called by a Flask route)
async def example_search_flow():
    db = await get_lancedb_connection()
    if not db:
        print("Failed to connect to DB for example.")
        return

    # Dummy query vector
    dummy_q_vector = [0.05] * EMBEDDING_DIMENSION
    user = "test_user_123"

    # Example filters
    # filters = {"date_after": "2023-01-01T00:00:00Z", "source_types": ["email_snippet", "notion_summary"]}
    filters = {}

    results = await search_lancedb_all(db, dummy_q_vector, user, filters, limit_total=5)

    if results:
        print(f"\nFound {len(results)} combined results:")
        for res_item in results:
            print(f"  ID: {res_item['id']}, Type: {res_item['source_type']}, Score: {res_item['vector_score']:.4f}, Title: {res_item['title']}")
            print(f"     Snippet: {res_item['snippet'][:100]}...")
    else:
        print("No results found from combined search.")

if __name__ == "__main__":
    # To run example:
    # Ensure LANCEDB_URI is set (e.g., export LANCEDB_URI=/path/to/your/lance_db)
    # And that tables exist and have some data.
    # asyncio.run(example_search_flow())
    pass
