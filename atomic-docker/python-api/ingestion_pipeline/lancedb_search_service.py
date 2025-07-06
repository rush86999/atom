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
    source_type_label: SearchResultSourceType,
    parent_doc_titles: Optional[Dict[str, str]] = None # For document_chunks
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

    # Apply additional filters (example for date range on a 'timestamp_field')
    # This needs to be adapted based on actual filterable fields in each schema
    if filters:
        date_after = filters.get("date_after")
        date_before = filters.get("date_before")
        # Assuming a common timestamp field like 'ingested_at' or specific ones like 'email_date'
        # This part needs to be more robust based on which fields are filterable and their types in LanceDB.
        # For simplicity, this example assumes 'ingested_at' is a primary date field for filtering.
        # LanceDB converts datetime to microseconds (int64) for storage.
        # So, date strings need to be converted to microseconds for filtering.

        # Example: if 'ingested_at' is the target field for date filtering
        timestamp_field_for_filtering = "ingested_at" # This should be schema-dependent
        if source_type_label == "email_snippet":
            timestamp_field_for_filtering = "email_date"
        elif source_type_label == "notion_summary":
            timestamp_field_for_filtering = "last_edited_time_source" # or created_time_source

        if date_after:
            try:
                dt_after = datetime.fromisoformat(date_after.replace("Z", "+00:00"))
                # Convert to microseconds for LanceDB int64 timestamp comparison
                filter_str += f" AND {timestamp_field_for_filtering} >= {int(dt_after.timestamp() * 1_000_000)}"
            except ValueError:
                logger.warning(f"Invalid date_after format: {date_after}")
        if date_before:
            try:
                dt_before = datetime.fromisoformat(date_before.replace("Z", "+00:00"))
                filter_str += f" AND {timestamp_field_for_filtering} <= {int(dt_before.timestamp() * 1_000_000)}"
            except ValueError:
                logger.warning(f"Invalid date_before format: {date_before}")

        if source_type_label == "document_chunk" and filters.get("doc_type_filter"):
            filter_str += f" AND parent_doc_type = '{filters['doc_type_filter']}'" # Requires parent_doc_type in chunk schema or join

    if filter_str:
        logger.debug(f"Applying filter to {table_name}: {filter_str}")
        search_req = search_req.where(filter_str)

    raw_results = await asyncio.to_thread(search_req.to_list)
    logger.info(f"Search on {table_name} for user {user_id} returned {len(raw_results)} raw results.")

    mapped_results: List[UniversalSearchResultItem] = []
    for record in raw_results:
        # LanceDB returns scores as _distance (lower is better). Invert for relevance (higher is better).
        # Simple inversion: 1.0 / (1.0 + distance). Needs normalization if combining diverse distances.
        # Or, just pass raw distance and let consumer decide. For now, pass raw.
        score = record.get("_distance", float('inf'))

        item: UniversalSearchResultItem = {
            "id": "", "user_id": record.get("user_id", user_id), "source_type": source_type_label,
            "title": "", "snippet": "", "vector_score": score,
        }

        if source_type_label == "document_chunk":
            item["id"] = record.get("chunk_id") or record.get("_rowid") # Assuming chunk_id or use rowid
            item["snippet"] = record.get("text_content", "")
            doc_id = record.get("doc_id")
            item["document_id"] = doc_id
            # To get parent_document_title, document_source_uri, document_doc_type,
            # we would need to fetch from DOCUMENTS_TABLE_NAME using doc_id, or denormalize.
            # For this iteration, these might be initially empty or fetched if parent_doc_titles is provided.
            if parent_doc_titles and doc_id in parent_doc_titles:
                item["title"] = parent_doc_titles[doc_id] # Parent doc title
                item["parent_document_title"] = parent_doc_titles[doc_id]
            else: # Fallback if not pre-fetched
                item["title"] = f"Chunk {record.get('chunk_sequence', '')} from Doc {doc_id}"
            item["chunk_sequence"] = record.get("chunk_sequence")
            # item["document_source_uri"] = ... (needs fetch or denormalization)
            # item["document_doc_type"] = ... (needs fetch or denormalization)
            # Timestamps would also come from parent document typically
            item["ingested_at"] = record.get("ingested_at").isoformat() if record.get("ingested_at") else None


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
```
