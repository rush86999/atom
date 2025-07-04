import os
import logging
import lancedb
import asyncio # For asyncio.to_thread
from lancedb.pydantic import LanceModel, vector
from typing import List, Dict, Any, Optional, Tuple # Added Tuple
from datetime import datetime, timezone # Added timezone

# Configure logging
logger = logging.getLogger(__name__)
if not logger.hasHandlers(): # Basic configuration if run standalone
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

LANCEDB_URI = os.getenv("LANCEDB_URI", "./lance_data/prod_db") # Default to local directory, more specific path
TABLE_NAME = os.getenv("LANCEDB_TABLE_NAME", "meeting_transcripts_embeddings")
EMBEDDING_DIMENSION = 1536 # For text-embedding-ada-002

# Define Pydantic model for LanceDB table schema
# Ensure field names here match exactly what will be in the dictionaries added to LanceDB
class TranscriptChunk(LanceModel):
    embedding: vector(EMBEDDING_DIMENSION) # type: ignore

    text_chunk: str
    chunk_id: str
    notion_page_id: str
    notion_page_title: str
    notion_page_url: str
    user_id: str

    created_at_notion: Optional[datetime] = None # Stored as datetime
    last_edited_at_notion: Optional[datetime] = None # Stored as datetime
    ingested_at: datetime # Stored as datetime


_db_connection_lancedb: Optional[lancedb.DBConnection] = None

async def get_lancedb_connection() -> Optional[lancedb.DBConnection]:
    global _db_connection_lancedb
    if _db_connection_lancedb is None:
        logger.info(f"Connecting to LanceDB at URI: {LANCEDB_URI}")
        try:
            # Ensure parent directory for local LanceDB URI exists
            if not LANCEDB_URI.startswith("db://") and "://" not in LANCEDB_URI : # Basic check if it's a local path
                 # More robust check might be needed for other schemes like s3://
                db_dir = os.path.dirname(LANCEDB_URI)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
                    logger.info(f"Created LanceDB directory: {db_dir}")

            _db_connection_lancedb = await asyncio.to_thread(lancedb.connect, LANCEDB_URI)
        except Exception as e:
            logger.error(f"Failed to connect to LanceDB at {LANCEDB_URI}: {e}", exc_info=True)
            return None
    return _db_connection_lancedb

async def create_or_open_table(
    db_conn: lancedb.DBConnection,
    table_name: str = TABLE_NAME,
    schema: Optional[Any] = TranscriptChunk # schema is Pydantic model
) -> Optional[lancedb.table.Table]:
    """Creates a LanceDB table if it doesn't exist, or opens it."""
    try:
        table_names = await asyncio.to_thread(db_conn.table_names)
        if table_name in table_names:
            logger.info(f"Opening existing LanceDB table: {table_name}")
            tbl = await asyncio.to_thread(db_conn.open_table, table_name)
        else:
            logger.info(f"Creating new LanceDB table: {table_name} with Pydantic schema: {schema.__name__ if schema else 'No schema'}")
            tbl = await asyncio.to_thread(db_conn.create_table, table_name, schema=schema)
        return tbl
    except Exception as e:
        logger.error(f"Error creating or opening LanceDB table {table_name}: {e}", exc_info=True)
        # Not raising here, allowing caller to handle None table
        return None


async def delete_chunks_for_page(table: lancedb.table.Table, notion_page_id: str) -> bool:
    """Deletes all chunks associated with a specific notion_page_id from the table."""
    try:
        logger.info(f"Attempting to delete existing chunks for notion_page_id: {notion_page_id} from table: {table.name}")
        # The delete operation is synchronous
        await asyncio.to_thread(table.delete, f"notion_page_id = '{notion_page_id}'")
        logger.info(f"Successfully deleted existing chunks for notion_page_id: {notion_page_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting chunks for notion_page_id {notion_page_id} from table {table.name}: {e}", exc_info=True)
        return False

async def add_chunks_to_lancedb(table: lancedb.table.Table, data_to_add: List[Dict[str, Any]]):
    """Adds a list of processed chunk data (dictionaries) to the LanceDB table."""
    if not data_to_add:
        logger.info("No data provided to add_chunks_to_lancedb.")
        return

    try:
        logger.info(f"Adding {len(data_to_add)} chunks to LanceDB table: {table.name}")
        # The add operation is synchronous
        await asyncio.to_thread(table.add, data_to_add)
        logger.info(f"Successfully added {len(data_to_add)} chunks to LanceDB table: {table.name}")
    except Exception as e:
        logger.error(f"Error adding chunks to LanceDB table {table.name}: {e}", exc_info=True)
        raise # Re-raise to be handled by the caller

async def upsert_page_embeddings_to_lancedb(
    notion_page_id: str,
    notion_page_title: str,
    notion_page_url: str,
    user_id: str,
    created_at_notion_iso: Optional[str],
    last_edited_at_notion_iso: str,
    chunks_with_embeddings: List[Tuple[str, Optional[List[float]]]],
    db_conn_override: Optional[lancedb.DBConnection] = None
) -> bool:
    """
    Upserts text chunks and their embeddings for a given Notion page into LanceDB.
    Handles creation/opening of table and deletion of old chunks for the page.
    """
    db = db_conn_override or await get_lancedb_connection()
    if not db:
        logger.error("LanceDB connection not available. Cannot upsert embeddings.")
        return False

    table = await create_or_open_table(db, TABLE_NAME, schema=TranscriptChunk)
    if not table:
        logger.error(f"Failed to create or open LanceDB table {TABLE_NAME}.")
        return False

    if not await delete_chunks_for_page(table, notion_page_id):
        logger.warning(f"Failed to delete old chunks for page {notion_page_id}. Proceeding with add, may result in duplicates if not fully cleaned.")
        # Depending on strictness, might return False here.

    lancedb_data_to_add: List[Dict[str, Any]] = []
    current_ingestion_time = datetime.now(timezone.utc) # Use timezone-aware datetime

    for i, (text_chunk, embedding_vector) in enumerate(chunks_with_embeddings):
        if embedding_vector is None:
            logger.warning(f"Skipping chunk {i} for page {notion_page_id} due to missing embedding.")
            continue

        created_dt: Optional[datetime] = None
        if created_at_notion_iso:
            try:
                created_dt = datetime.fromisoformat(created_at_notion_iso.replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Invalid ISO format for created_at_notion: {created_at_notion_iso} for page {notion_page_id}. Setting to None.")

        last_edited_dt: Optional[datetime] = None
        try:
            # Ensure last_edited_at_notion_iso is not None and is a valid string before parsing
            if last_edited_at_notion_iso and isinstance(last_edited_at_notion_iso, str):
                 last_edited_dt = datetime.fromisoformat(last_edited_at_notion_iso.replace("Z", "+00:00"))
            else:
                logger.warning(f"last_edited_at_notion_iso is missing or not a string for page {notion_page_id}. Setting to None.")
        except ValueError as ve:
            logger.error(f"Invalid ISO format for last_edited_at_notion: {last_edited_at_notion_iso} for page {notion_page_id}. Error: {ve}. Setting to None.")


        chunk_data = {
            "embedding": embedding_vector,
            "text_chunk": text_chunk,
            "chunk_id": f"{notion_page_id}_chunk_{i}",
            "notion_page_id": notion_page_id,
            "notion_page_title": notion_page_title,
            "notion_page_url": notion_page_url,
            "user_id": user_id,
            "created_at_notion": created_dt,
            "last_edited_at_notion": last_edited_dt,
            "ingested_at": current_ingestion_time,
        }
        lancedb_data_to_add.append(chunk_data)

    if not lancedb_data_to_add:
        logger.info(f"No valid chunks with embeddings to add for page {notion_page_id}.")
        return True

    try:
        await add_chunks_to_lancedb(table, lancedb_data_to_add)
        logger.info(f"Successfully upserted {len(lancedb_data_to_add)} chunks for page {notion_page_id}.")
        return True
    except Exception as e:
        logger.error(f"Failed during final add_chunks_to_lancedb for page {notion_page_id}: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    # Example test (requires LanceDB, OpenAI API key, and sample data)
    async def main_test_lancedb():
        if not os.getenv("OPENAI_API_KEY"):
            print("Warning: OPENAI_API_KEY not set. Embedding generation might fail if used in test.")

        print(f"LanceDB URI will be: {LANCEDB_URI}")
        if LANCEDB_URI.startswith("./"):
            os.makedirs(os.path.dirname(LANCEDB_URI), exist_ok=True)

        db_conn = await get_lancedb_connection()
        if not db_conn:
            print("Failed to connect to LanceDB for test.")
            return

        # Use a distinct test table name
        test_table_name_lancedb = TABLE_NAME + "_test_run"
        try:
            current_tables = await asyncio.to_thread(db_conn.table_names)
            if test_table_name_lancedb in current_tables:
                await asyncio.to_thread(db_conn.drop_table, test_table_name_lancedb)
                logger.info(f"Dropped existing test table: {test_table_name_lancedb}")
        except Exception as e:
            logger.error(f"Error managing test table {test_table_name_lancedb}: {e}")
            # return # Allow test to proceed to create_or_open_table

        sample_page_id = "testpage_upsert_001"
        sample_user_id = "user_test_001"
        sample_title = "Test Page for LanceDB Upsert"
        sample_url = "http://example.com/testpage_upsert_001"

        # Ensure timestamps are in UTC and correctly formatted
        now_utc = datetime.now(timezone.utc)
        sample_created_iso = now_utc.isoformat()
        sample_edited_iso = now_utc.isoformat()

        # Dummy embeddings (replace with actual embeddings if testing full flow)
        dummy_embedding = [0.01 * i for i in range(EMBEDDING_DIMENSION)]

        sample_chunks_with_embeddings_v1 = [
            ("First version of chunk one.", dummy_embedding),
            ("First version of chunk two.", [d + 0.01 for d in dummy_embedding]),
        ]
        sample_chunks_with_embeddings_v2 = [ # Updated content
            ("Second version of chunk one, updated.", [d + 0.02 for d in dummy_embedding]),
            ("Brand new second chunk for v2.", [d + 0.03 for d in dummy_embedding]),
            ("An additional third chunk for v2.", [d + 0.04 for d in dummy_embedding]),
        ]

        print(f"\nAttempting to upsert initial embeddings for page: {sample_page_id}")
        success_v1 = await upsert_page_embeddings_to_lancedb(
            notion_page_id=sample_page_id, notion_page_title=sample_title,
            notion_page_url=sample_url, user_id=sample_user_id,
            created_at_notion_iso=sample_created_iso, last_edited_at_notion_iso=sample_edited_iso,
            chunks_with_embeddings=sample_chunks_with_embeddings_v1,
            db_conn_override=db_conn # Pass connection for consistent table name
        )

        table_to_check = await create_or_open_table(db_conn, TABLE_NAME, schema=TranscriptChunk) # Use default table name for check
        if not table_to_check:
            print("Failed to open table for verification.")
            return

        if success_v1:
            print("Initial upsert successful. Verifying table content...")
            df_v1 = await asyncio.to_thread(table_to_check.search().where(f"notion_page_id = '{sample_page_id}'").to_pandas)
            print(f"Table content (v1):\n{df_v1[['chunk_id', 'text_chunk', 'notion_page_title', 'last_edited_at_notion']]}")
            assert len(df_v1) == 2, f"Expected 2 chunks for v1, got {len(df_v1)}"
            assert df_v1["notion_page_id"].iloc[0] == sample_page_id
        else:
            print("Initial upsert failed.")
            return # Stop test if first upsert fails

        print(f"\nAttempting to upsert updated embeddings for page: {sample_page_id}")
        sample_edited_iso_v2 = datetime.now(timezone.utc).isoformat() # Ensure it's newer
        success_v2 = await upsert_page_embeddings_to_lancedb(
            notion_page_id=sample_page_id, notion_page_title=sample_title + " (Updated V2)",
            notion_page_url=sample_url, user_id=sample_user_id,
            created_at_notion_iso=sample_created_iso, last_edited_at_notion_iso=sample_edited_iso_v2,
            chunks_with_embeddings=sample_chunks_with_embeddings_v2,
            db_conn_override=db_conn
        )
        if success_v2:
            print("Second upsert (update) successful. Verifying table content...")
            df_v2 = await asyncio.to_thread(table_to_check.search().where(f"notion_page_id = '{sample_page_id}'").to_pandas)
            print(f"Table content (v2):\n{df_v2[['chunk_id', 'text_chunk', 'notion_page_title', 'last_edited_at_notion']]}")
            assert len(df_v2) == 3, f"Expected 3 chunks for v2, got {len(df_v2)}"
            assert df_v2["notion_page_title"].iloc[0] == sample_title + " (Updated V2)"
            assert df_v2["text_chunk"].iloc[0] == "Second version of chunk one, updated."
        else:
            print("Second upsert (update) failed.")

        # Clean up by dropping the specific test table if it was created by this test run
        # The main TABLE_NAME might be shared, so only drop if we used a unique test name
        # For this example, upsert_page_embeddings_to_lancedb uses TABLE_NAME.
        # Manual cleanup might be needed if running this test multiple times against a persistent DB.
        # logger.info(f"Test finished. Consider manual cleanup of table '{TABLE_NAME}' in '{LANCEDB_URI}' if needed.")


    # To run this test:
    # 1. Ensure OPENAI_API_KEY (if text_processor called directly) and LANCEDB_URI are set.
    # 2. pip install lancedb pydantic pyarrow pandas (pandas for test verification)
    # 3. Uncomment the line below.
    # asyncio.run(main_test_lancedb())
    pass
