import os
import logging
import lancedb
import asyncio
import json # For icon_json in NotionPageSummaryModel
from lancedb.pydantic import LanceModel, vector
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone

# Configure logging
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Embedding Dimension (consistent with note_utils and existing schema) ---
EMBEDDING_DIMENSION = 1536 # For text-embedding-ada-002 or text-embedding-3-small

# --- LanceDB Connection ---
LANCEDB_URI = os.getenv("LANCEDB_URI", "./lance_data/prod_db")
_db_connection_lancedb: Optional[lancedb.DBConnection] = None

async def get_lancedb_connection() -> Optional[lancedb.DBConnection]:
    global _db_connection_lancedb
    if _db_connection_lancedb is None:
        logger.info(f"Connecting to LanceDB at URI: {LANCEDB_URI}")
        try:
            if not LANCEDB_URI.startswith("db://") and "://" not in LANCEDB_URI :
                db_dir = os.path.dirname(LANCEDB_URI)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
                    logger.info(f"Created LanceDB directory: {db_dir}")
            _db_connection_lancedb = await asyncio.to_thread(lancedb.connect, LANCEDB_URI)
        except Exception as e:
            logger.error(f"Failed to connect to LanceDB at {LANCEDB_URI}: {e}", exc_info=True)
            return None
    return _db_connection_lancedb

# --- Embedding Utility Import (Attempt) ---
# This is a placeholder for robustly accessing the embedding function.
# In a real setup, this might be a shared library or a service call.
try:
    import sys
    # Path to 'project/functions/' from 'python-api/ingestion_pipeline/'
    FUNCTIONS_DIR_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'project', 'functions'))
    if FUNCTIONS_DIR_PATH not in sys.path:
        sys.path.append(FUNCTIONS_DIR_PATH)
    from note_utils import get_text_embedding_openai
    EMBEDDING_FUNCTION_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import get_text_embedding_openai from note_utils: {e}. Embedding-dependent functions will fail if embedding_fn is not passed.")
    get_text_embedding_openai = None # Placeholder
    EMBEDDING_FUNCTION_AVAILABLE = False


# --- Table Names ---
MEETING_TRANSCRIPTS_TABLE_NAME = os.getenv("LANCEDB_TABLE_NAME", "meeting_transcripts_embeddings")
DOCUMENTS_TABLE_NAME = os.getenv("LANCEDB_DOCUMENTS_TABLE", "generic_documents")
DOCUMENT_CHUNKS_TABLE_NAME = os.getenv("LANCEDB_DOCUMENT_CHUNKS_TABLE", "document_chunks")
EMAIL_SNIPPETS_TABLE_NAME = os.getenv("LANCEDB_EMAIL_SNIPPETS_TABLE", "email_snippets")
NOTION_SUMMARIES_TABLE_NAME = os.getenv("LANCEDB_NOTION_SUMMARIES_TABLE", "notion_page_summaries")


# --- Pydantic Schemas for LanceDB ---
class TranscriptChunk(LanceModel): # Existing schema
    embedding: vector(EMBEDDING_DIMENSION) # type: ignore
    text_chunk: str; chunk_id: str; notion_page_id: str; notion_page_title: str
    notion_page_url: str; user_id: str
    created_at_notion: Optional[datetime] = None; last_edited_at_notion: Optional[datetime] = None
    ingested_at: datetime

class DocumentMetadataModel(LanceModel):
    doc_id: str # UUID for the document
    user_id: str
    source_uri: str
    doc_type: str
    title: Optional[str] = None
    metadata_json: Optional[str] = None
    created_at_source: Optional[datetime] = None
    last_modified_source: Optional[datetime] = None
    ingested_at: datetime
    processing_status: str
    error_message: Optional[str] = None

class DocumentChunkModel(LanceModel):
    embedding: vector(EMBEDDING_DIMENSION) # type: ignore
    doc_id: str
    user_id: str
    chunk_sequence: int
    text_content: str
    parent_doc_type: Optional[str] = None # Added for filtering by parent document type
    metadata_json: Optional[str] = None
    char_count: Optional[int] = None

class EmailSnippetModel(LanceModel):
    embedding: vector(EMBEDDING_DIMENSION) # type: ignore
    email_id: str
    user_id: str
    thread_id: Optional[str] = None
    subject: Optional[str] = None
    from_sender: Optional[str] = None
    email_date: Optional[datetime] = None
    snippet_text: str
    source_link: Optional[str] = None
    ingested_at: datetime

class NotionPageSummaryModel(LanceModel):
    embedding: vector(EMBEDDING_DIMENSION) # type: ignore
    notion_page_id: str
    user_id: str
    title: Optional[str] = None
    notion_url: Optional[str] = None
    preview_text: Optional[str] = None
    icon_json: Optional[str] = None
    last_edited_time_source: Optional[datetime] = None
    created_time_source: Optional[datetime] = None
    ingested_at: datetime

# --- Generic Table Operations ---
async def create_or_open_table(
    db_conn: lancedb.DBConnection, table_name: str, schema: Optional[Any] = None
) -> Optional[lancedb.table.Table]:
    try:
        table_names = await asyncio.to_thread(db_conn.table_names)
        if table_name in table_names:
            logger.debug(f"Opening existing LanceDB table: {table_name}")
            tbl = await asyncio.to_thread(db_conn.open_table, table_name)
        else:
            if not schema:
                logger.error(f"Schema required to create new LanceDB table: {table_name}")
                return None
            logger.info(f"Creating new LanceDB table: {table_name} with Pydantic schema: {schema.__name__}")
            tbl = await asyncio.to_thread(db_conn.create_table, table_name, schema=schema)
        return tbl
    except Exception as e:
        logger.error(f"Error creating or opening LanceDB table {table_name}: {e}", exc_info=True)
        return None

async def add_data_to_table(table: lancedb.table.Table, data_to_add: List[Dict[str, Any]]):
    if not data_to_add:
        logger.info(f"No data provided to add to table {table.name}.")
        return
    try:
        logger.info(f"Adding {len(data_to_add)} items to LanceDB table: {table.name}")
        await asyncio.to_thread(table.add, data_to_add)
        logger.info(f"Successfully added {len(data_to_add)} items to LanceDB table: {table.name}")
    except Exception as e:
        logger.error(f"Error adding data to LanceDB table {table.name}: {e}", exc_info=True)
        raise

# --- Generic Document Storage Functions ---
async def create_generic_document_tables_if_not_exist(db_conn: lancedb.DBConnection) -> bool:
    doc_table_ok = await create_or_open_table(db_conn, DOCUMENTS_TABLE_NAME, schema=DocumentMetadataModel)
    chunk_table_ok = await create_or_open_table(db_conn, DOCUMENT_CHUNKS_TABLE_NAME, schema=DocumentChunkModel)
    if doc_table_ok and chunk_table_ok:
        logger.info("Generic document tables ensured.")
        return True
    logger.error("Failed to ensure one or both generic document tables.")
    return False

async def add_processed_document(
    db_conn: lancedb.DBConnection,
    doc_meta_dict: Dict[str, Any],
    chunks_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    doc_id = doc_meta_dict.get("doc_id")
    if not doc_id: return {"status": "error", "message": "doc_id missing from document metadata."}

    if not await create_generic_document_tables_if_not_exist(db_conn): # Ensure tables first
        return {"status": "error", "message": "Failed to create/ensure document tables."}

    doc_table = await asyncio.to_thread(db_conn.open_table, DOCUMENTS_TABLE_NAME)
    chunk_table = await asyncio.to_thread(db_conn.open_table, DOCUMENT_CHUNKS_TABLE_NAME)

    try:
        await asyncio.to_thread(doc_table.delete, f"doc_id = '{doc_id}'")
        for dt_field in ["created_at_source", "last_modified_source", "ingested_at"]:
            if dt_field in doc_meta_dict and isinstance(doc_meta_dict[dt_field], str):
                iso_str = doc_meta_dict[dt_field]
                doc_meta_dict[dt_field] = datetime.fromisoformat(iso_str.replace("Z", "+00:00")) if iso_str else None
        await asyncio.to_thread(doc_table.add, [doc_meta_dict])
        logger.info(f"Stored metadata for document: {doc_id}")

        if chunks_data:
            await asyncio.to_thread(chunk_table.delete, f"doc_id = '{doc_id}'")
            await add_data_to_table(chunk_table, chunks_data) # Use generic add_data_to_table
            logger.info(f"Stored {len(chunks_data)} chunks for document: {doc_id}")
        return {"status": "success", "doc_id": doc_id, "num_chunks_added": len(chunks_data) if chunks_data else 0}
    except Exception as e:
        logger.error(f"Error storing processed document {doc_id}: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to store processed document: {str(e)}", "code": "LANCEDB_DOC_STORE_ERROR"}

# --- Email Snippet Storage Functions ---
async def upsert_email_snippet(db_conn: lancedb.DBConnection, email_data_ts: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    if not email_data_ts or not email_data_ts.get("id"):
        return {"status": "error", "message": "Email data or email ID missing."}
    if not EMBEDDING_FUNCTION_AVAILABLE or not get_text_embedding_openai:
        return {"status": "error", "message": "Embedding function not available.", "code": "EMBEDDING_SERVICE_UNAVAILABLE"}

    table = await create_or_open_table(db_conn, EMAIL_SNIPPETS_TABLE_NAME, schema=EmailSnippetModel)
    if not table: return {"status": "error", "message": f"Failed to open/create table {EMAIL_SNIPPETS_TABLE_NAME}."}

    email_id = email_data_ts["id"]
    snippet_text = email_data_ts.get("snippet","")
    if not snippet_text: return {"status": "warning", "message": f"Email {email_id} has no snippet to embed."} # Or error

    embedding_resp = get_text_embedding_openai(snippet_text) # Uses global key from note_utils
    if embedding_resp["status"] != "success":
        return {"status": "error", "message": f"Embedding failed for email {email_id}: {embedding_resp.get('message')}", "code": "EMBEDDING_ERROR"}

    db_entry = {
        "email_id": email_id, "user_id": user_id, "thread_id": email_data_ts.get("threadId"),
        "subject": email_data_ts.get("subject"), "from_sender": email_data_ts.get("from"),
        "snippet_text": snippet_text, "embedding": embedding_resp["data"],
        "source_link": email_data_ts.get("link"), "ingested_at": datetime.now(timezone.utc)
    }
    if email_data_ts.get("date") and isinstance(email_data_ts["date"], str):
        iso_str = email_data_ts["date"]
        try:
            db_entry["email_date"] = datetime.fromisoformat(iso_str.replace("Z", "+00:00")) if iso_str else None
        except ValueError: db_entry["email_date"] = None

    try:
        await asyncio.to_thread(table.delete, f"email_id = '{email_id}' AND user_id = '{user_id}'")
        await asyncio.to_thread(table.add, [db_entry])
        logger.info(f"Upserted email snippet: {email_id} for user {user_id}")
        return {"status": "success", "email_id": email_id}
    except Exception as e:
        logger.error(f"Error upserting email snippet {email_id}: {e}", exc_info=True)
        return {"status": "error", "message": f"LanceDB upsert failed for email: {str(e)}", "code": "LANCEDB_EMAIL_UPSERT_ERROR"}

# --- Notion Page Summary Storage Functions ---
async def upsert_notion_page_summary(db_conn: lancedb.DBConnection, page_data_ts: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    if not page_data_ts or not page_data_ts.get("id"):
        return {"status": "error", "message": "Notion page data or ID missing."}
    if not EMBEDDING_FUNCTION_AVAILABLE or not get_text_embedding_openai:
        return {"status": "error", "message": "Embedding function not available.", "code": "EMBEDDING_SERVICE_UNAVAILABLE"}

    table = await create_or_open_table(db_conn, NOTION_SUMMARIES_TABLE_NAME, schema=NotionPageSummaryModel)
    if not table: return {"status": "error", "message": f"Failed to open/create table {NOTION_SUMMARIES_TABLE_NAME}."}

    notion_page_id = page_data_ts["id"]
    text_to_embed = page_data_ts.get("preview_text") or page_data_ts.get("title") or ""

    db_entry = {
        "notion_page_id": notion_page_id, "user_id": user_id, "title": page_data_ts.get("title"),
        "notion_url": page_data_ts.get("url"), "preview_text": page_data_ts.get("preview_text"),
        "icon_json": json.dumps(page_data_ts.get("icon")) if page_data_ts.get("icon") else None,
        "ingested_at": datetime.now(timezone.utc)
    }

    for dt_field_db, dt_field_ts in [("last_edited_time_source", "last_edited_time"), ("created_time_source", "created_time")]:
        if page_data_ts.get(dt_field_ts) and isinstance(page_data_ts[dt_field_ts], str):
            iso_str = page_data_ts[dt_field_ts]
            try:
                db_entry[dt_field_db] = datetime.fromisoformat(iso_str.replace("Z", "+00:00")) if iso_str else None
            except ValueError: db_entry[dt_field_db] = None

    if not text_to_embed.strip():
        logger.warning(f"No text to embed for Notion page {notion_page_id}. Storing with zero vector.")
        db_entry["embedding"] = [0.0] * EMBEDDING_DIMENSION
    else:
        embedding_resp = get_text_embedding_openai(text_to_embed)
        if embedding_resp["status"] == "success":
            db_entry["embedding"] = embedding_resp["data"]
        else:
            return {"status": "error", "message": f"Embedding failed for Notion page {notion_page_id}: {embedding_resp.get('message')}", "code": "EMBEDDING_ERROR"}

    try:
        await asyncio.to_thread(table.delete, f"notion_page_id = '{notion_page_id}' AND user_id = '{user_id}'")
        await asyncio.to_thread(table.add, [db_entry])
        logger.info(f"Upserted Notion page summary: {notion_page_id} for user {user_id}")
        return {"status": "success", "notion_page_id": notion_page_id}
    except Exception as e:
        logger.error(f"Error upserting Notion page summary {notion_page_id}: {e}", exc_info=True)
        return {"status": "error", "message": f"LanceDB upsert failed for Notion page: {str(e)}", "code": "LANCEDB_NOTION_UPSERT_ERROR"}


# --- Existing TranscriptChunk functions (modified for clarity and consistency) ---
# Renamed TABLE_NAME to MEETING_TRANSCRIPTS_TABLE_NAME for clarity
async def delete_transcript_chunks_for_page(table: lancedb.table.Table, notion_page_id: str) -> bool: # Renamed
    # This is the original delete_chunks_for_page
    try:
        logger.info(f"Attempting to delete existing transcript chunks for notion_page_id: {notion_page_id} from table: {table.name}")
        await asyncio.to_thread(table.delete, f"notion_page_id = '{notion_page_id}'")
        logger.info(f"Successfully deleted existing transcript chunks for notion_page_id: {notion_page_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting transcript chunks for notion_page_id {notion_page_id} from table {table.name}: {e}", exc_info=True)
        return False

async def upsert_meeting_transcript_embeddings( # Renamed from upsert_page_embeddings_to_lancedb
    notion_page_id: str, notion_page_title: str, notion_page_url: str, user_id: str,
    created_at_notion_iso: Optional[str], last_edited_at_notion_iso: str,
    chunks_with_embeddings: List[Tuple[str, Optional[List[float]]]], # text_chunk, embedding_vector
    db_conn_override: Optional[lancedb.DBConnection] = None
) -> bool:
    db = db_conn_override or await get_lancedb_connection()
    if not db: return False

    table = await create_or_open_table(db, MEETING_TRANSCRIPTS_TABLE_NAME, schema=TranscriptChunk)
    if not table: return False

    if not await delete_transcript_chunks_for_page(table, notion_page_id): # Use renamed delete
        logger.warning(f"Failed to delete old transcript chunks for page {notion_page_id}.")

    lancedb_data_to_add: List[Dict[str, Any]] = []
    current_ingestion_time = datetime.now(timezone.utc)

    for i, (text_chunk, embedding_vector) in enumerate(chunks_with_embeddings):
        if embedding_vector is None: continue
        created_dt: Optional[datetime] = None
        if created_at_notion_iso:
            try: created_dt = datetime.fromisoformat(created_at_notion_iso.replace("Z", "+00:00"))
            except ValueError: logger.warning(f"Invalid ISO for created_at_notion: {created_at_notion_iso}")
        last_edited_dt: Optional[datetime] = None
        if last_edited_at_notion_iso and isinstance(last_edited_at_notion_iso, str):
            try: last_edited_dt = datetime.fromisoformat(last_edited_at_notion_iso.replace("Z", "+00:00"))
            except ValueError: logger.warning(f"Invalid ISO for last_edited_at_notion: {last_edited_at_notion_iso}")

        chunk_data = {
            "embedding": embedding_vector, "text_chunk": text_chunk,
            "chunk_id": f"{notion_page_id}_chunk_{i}", "notion_page_id": notion_page_id,
            "notion_page_title": notion_page_title, "notion_page_url": notion_page_url,
            "user_id": user_id, "created_at_notion": created_dt,
            "last_edited_at_notion": last_edited_dt, "ingested_at": current_ingestion_time,
        }
        lancedb_data_to_add.append(chunk_data)

    if not lancedb_data_to_add: return True # No valid chunks to add
    try:
        await add_data_to_table(table, lancedb_data_to_add) # Use generic add_data_to_table
        return True
    except Exception as e:
        logger.error(f"Failed during add_data_to_table for transcript page {notion_page_id}: {e}", exc_info=True)
        return False

# Main test function (modified to reflect new structure if needed)
if __name__ == '__main__':
    async def main_test_lancedb():
        # ... (existing test logic, may need updates to use new table names/schemas if testing generic docs)
        # For now, the existing test focuses on TranscriptChunk and upsert_meeting_transcript_embeddings
        # which is fine as a standalone test for that functionality.
        # New tests would be needed for generic document processing.
        logger.info("Original __main__ test for lancedb_handler.py for meeting transcripts is available but not run by default.")
        pass
    # asyncio.run(main_test_lancedb())
```
