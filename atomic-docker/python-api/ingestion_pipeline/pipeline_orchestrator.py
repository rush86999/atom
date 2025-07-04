import os
import asyncio
import logging
from datetime import datetime, timezone # Ensure timezone is imported
from typing import Optional, Any, List # Added List for type hint

# Assuming modules are in the same package or PYTHONPATH is set up correctly.
# If running as a script directly within the directory, relative imports might need adjustment
# or the directory added to sys.path. For a proper package, this should work.
try:
    from .notion_extractor import extract_structured_data_from_db, get_notion_client as get_notion_ext_client
    from .text_processor import process_text_for_embeddings, get_openai_client as get_tp_openai_client
    from .lancedb_handler import (
        upsert_page_embeddings_to_lancedb,
        get_lancedb_connection,
        TABLE_NAME as lancedb_default_table_name, # Use the default table name from handler
        TranscriptChunk # Schema for type checking if needed, though not directly used here
    )
except ImportError: # Fallback for direct script execution if . is not recognized
    from notion_extractor import extract_structured_data_from_db, get_notion_client as get_notion_ext_client
    from text_processor import process_text_for_embeddings, get_openai_client as get_tp_openai_client
    from lancedb_handler import (
        upsert_page_embeddings_to_lancedb,
        get_lancedb_connection,
        TABLE_NAME as lancedb_default_table_name,
        TranscriptChunk
    )


# Configure logging
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()] # Ensure logs go to console
    )


# Environment Variables for Orchestrator
NOTION_TRANSCRIPTS_DATABASE_ID = os.getenv("NOTION_TRANSCRIPTS_DATABASE_ID")
ATOM_USER_ID_FOR_INGESTION = os.getenv("ATOM_USER_ID_FOR_INGESTION", "default_atom_user")
PROCESSING_MODE = os.getenv("PROCESSING_MODE", "incremental").lower()
# How often to check for updates if in a polling incremental mode (not used by this manual trigger version yet)
# POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "3600"))


async def get_latest_page_edit_time_from_lancedb(
    db_conn: Any, # lancedb.DBConnection type, but use Any to avoid circular import issues if type hints are complex
    table_name: str,
    notion_page_id: str
) -> Optional[datetime]:
    """
    Queries LanceDB for the 'last_edited_at_notion' timestamp of the most recently ingested chunk
    for a given notion_page_id.
    """
    if not db_conn:
        logger.error("LanceDB connection not provided to get_latest_page_edit_time_from_lancedb.")
        return None
    try:
        tbl = await asyncio.to_thread(db_conn.open_table, table_name)

        # Select the last_edited_at_notion field, filter by notion_page_id,
        # order by ingested_at descending (if available and reliable) or just take any record's last_edited_at_notion
        # as it should be the same for all chunks of a given page version.
        # LanceDB Pydantic integration stores datetimes as int64 (nanoseconds since epoch).
        # When converting to pandas, it becomes pandas.Timestamp.

        query_result = await asyncio.to_thread(
            tbl.search()
            .where(f"notion_page_id = '{notion_page_id}'")
            .select(["last_edited_at_notion"]) # Only fetch this column
            .limit(1) # We only need one record for this page
            .to_pandas()
        )

        if not query_result.empty and 'last_edited_at_notion' in query_result.columns:
            timestamp_val = query_result['last_edited_at_notion'].iloc[0]
            if timestamp_val is not None:
                # Pandas to_datetime can often handle various formats including direct datetime objects or ISO strings
                # If it's already a datetime object from LanceDB Pydantic model, this should be fine.
                # LanceDB stores datetimes as nanoseconds (int64). When read via to_pandas(),
                # it becomes a pandas Timestamp (datetime64[ns]).
                if hasattr(timestamp_val, 'to_pydatetime'): # It's a pandas Timestamp
                    dt_object = timestamp_val.to_pydatetime()
                elif isinstance(timestamp_val, datetime):
                    dt_object = timestamp_val
                else:
                    logger.warning(f"Unexpected type for last_edited_at_notion from LanceDB: {type(timestamp_val)} for page {notion_page_id}")
                    return None # Or attempt parsing if it's a string

                # Ensure it's timezone-aware (UTC)
                if dt_object.tzinfo is None:
                    return dt_object.replace(tzinfo=timezone.utc)
                return dt_object.astimezone(timezone.utc)
        return None
    except Exception as e:
        # This can happen if the table doesn't exist yet or other DB errors.
        if "Table not found" in str(e) or "does not exist" in str(e): # More specific error checking
            logger.info(f"Table {table_name} not found or page {notion_page_id} not yet in LanceDB. Will process as new.")
        else:
            logger.error(f"Error fetching last ingested timestamp for page {notion_page_id} from LanceDB table {table_name}: {e}", exc_info=True)
        return None


async def run_ingestion_pipeline():
    logger.info(f"Starting ingestion pipeline in '{PROCESSING_MODE}' mode for user '{ATOM_USER_ID_FOR_INGESTION}'.")

    if not NOTION_TRANSCRIPTS_DATABASE_ID:
        logger.error("NOTION_TRANSCRIPTS_DATABASE_ID environment variable is not set. Aborting pipeline.")
        return

    notion_client = get_notion_ext_client()
    openai_client = get_tp_openai_client()
    lancedb_conn = await get_lancedb_connection()

    if not notion_client or not openai_client or not lancedb_conn:
        logger.error("One or more clients (Notion, OpenAI, LanceDB) failed to initialize. Aborting pipeline.")
        return

    logger.info(f"Fetching page structures from Notion database: {NOTION_TRANSCRIPTS_DATABASE_ID}")
    # `extract_structured_data_from_db` fetches metadata and full text for all non-archived pages.
    notion_pages_data: List[dict] = await extract_structured_data_from_db(
        database_id=NOTION_TRANSCRIPTS_DATABASE_ID,
        atom_user_id=ATOM_USER_ID_FOR_INGESTION,
        notion_client_override=notion_client
    )

    if not notion_pages_data:
        logger.info("No pages found or extracted from Notion database. Pipeline finished.")
        return

    processed_pages_count = 0
    skipped_pages_count = 0
    failed_pages_count = 0

    for page_data in notion_pages_data:
        notion_page_id = page_data["notion_page_id"]
        page_title = page_data["notion_page_title"]
        current_page_last_edited_iso = page_data["last_edited_at_notion"] # ISO string from Notion

        logger.info(f"Evaluating page: '{page_title}' (ID: {notion_page_id})")

        if PROCESSING_MODE == "incremental":
            if not current_page_last_edited_iso:
                logger.warning(f"Page '{page_title}' (ID: {notion_page_id}) has no last_edited_time from Notion. Processing it to be safe.")
            else:
                try:
                    # Ensure current_page_last_edited_iso is a string before replacing 'Z'
                    if not isinstance(current_page_last_edited_iso, str):
                        raise ValueError("last_edited_at_notion from Notion is not a string.")
                    current_page_last_edited_dt = datetime.fromisoformat(current_page_last_edited_iso.replace("Z", "+00:00"))

                    # Ensure it's timezone-aware (UTC)
                    if current_page_last_edited_dt.tzinfo is None:
                         current_page_last_edited_dt = current_page_last_edited_dt.replace(tzinfo=timezone.utc)
                    else:
                        current_page_last_edited_dt = current_page_last_edited_dt.astimezone(timezone.utc)

                    last_ingested_lancedb_dt = await get_latest_page_edit_time_from_lancedb(
                        lancedb_conn, lancedb_default_table_name, notion_page_id
                    )

                    if last_ingested_lancedb_dt and current_page_last_edited_dt <= last_ingested_lancedb_dt:
                        logger.info(f"Page '{page_title}' (ID: {notion_page_id}) has not been updated since last ingestion (Notion: {current_page_last_edited_dt}, LanceDB: {last_ingested_lancedb_dt}). Skipping.")
                        skipped_pages_count += 1
                        continue
                except ValueError as ve:
                    logger.error(f"Invalid date format for page '{page_title}' (ID: {notion_page_id}), last_edited_at_notion: {current_page_last_edited_iso}. Error: {ve}. Will process page to be safe.")
                except Exception as e_check:
                    logger.error(f"Error checking last ingested timestamp for page '{page_title}' (ID: {notion_page_id}): {e_check}. Will process page to be safe.", exc_info=True)

        full_text = page_data.get("full_text", "")
        if not full_text.strip():
            logger.info(f"Page '{page_title}' (ID: {notion_page_id}) has no text content. Skipping embedding.")
            skipped_pages_count +=1
            continue

        logger.info(f"Generating embeddings for page: '{page_title}' (ID: {notion_page_id})")
        chunks_with_embeddings = await process_text_for_embeddings(
            full_text=full_text,
            openai_client_override=openai_client
        )

        valid_chunks_for_storage = [(chk, emb) for chk, emb in chunks_with_embeddings if emb is not None]
        if not valid_chunks_for_storage:
            logger.warning(f"No embeddings successfully generated for page '{page_title}' (ID: {notion_page_id}). Skipping LanceDB storage.")
            # Consider if this should be a failure or just a skip
            failed_pages_count +=1 # Counting as failed if embeddings are crucial
            continue

        logger.info(f"Upserting {len(valid_chunks_for_storage)} embedding(s) for page: '{page_title}' (ID: {notion_page_id}) to LanceDB.")
        upsert_success = await upsert_page_embeddings_to_lancedb(
            notion_page_id=notion_page_id,
            notion_page_title=page_title,
            notion_page_url=page_data["notion_page_url"],
            user_id=page_data["user_id"],
            created_at_notion_iso=page_data["created_at_notion"],
            last_edited_at_notion_iso=current_page_last_edited_iso,
            chunks_with_embeddings=valid_chunks_for_storage, # Pass only chunks with successful embeddings
            db_conn_override=lancedb_conn
        )

        if upsert_success:
            logger.info(f"Successfully processed and stored page: '{page_title}' (ID: {notion_page_id})")
            processed_pages_count += 1
        else:
            logger.error(f"Failed to store embeddings for page: '{page_title}' (ID: {notion_page_id}) in LanceDB.")
            failed_pages_count += 1

    logger.info(f"Ingestion pipeline finished. Successfully processed pages: {processed_pages_count}. Skipped/up-to-date pages: {skipped_pages_count}. Failed pages: {failed_pages_count}.")


async def main():
    # Example of how to run the pipeline.
    # For actual deployment, this would be triggered by an API call or a scheduler.

    # Load .env file if it exists (for local development)
    # You might need to install python-dotenv: pip install python-dotenv
    try:
        from dotenv import load_dotenv
        dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(dotenv_path):
            logger.info(f"Loading .env file from {dotenv_path}")
            load_dotenv(dotenv_path)
        else:
            logger.info(".env file not found at expected location, relying on environment variables set externally.")
    except ImportError:
        logger.info("python-dotenv not installed, .env file will not be loaded. Relying on external environment variables.")

    # Check for required environment variables before running
    required_vars = ["NOTION_API_KEY", "OPENAI_API_KEY", "NOTION_TRANSCRIPTS_DATABASE_ID", "LANCEDB_URI"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}. Aborting pipeline.")
        print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}. Please set them to run the pipeline.")
        return

    await run_ingestion_pipeline()

if __name__ == "__main__":
    # This allows running the pipeline directly, e.g., for testing or a cron job.
    # Example: python -m atomic-docker.python-api.ingestion_pipeline.pipeline_orchestrator
    # (Adjust python -m path based on how you run it relative to your project root)
    # Or simply: python pipeline_orchestrator.py if in the directory

    # Ensure the logger for this module specifically shows output
    # logging.getLogger("pipeline_orchestrator").setLevel(logging.INFO) # Already set by basicConfig

    # For testing, you might want to set env vars here if not using .env or system env
    # os.environ["NOTION_API_KEY"] = "your_key"
    # os.environ["OPENAI_API_KEY"] = "your_key"
    # os.environ["NOTION_TRANSCRIPTS_DATABASE_ID"] = "your_db_id"
    # os.environ["LANCEDB_URI"] = "./lance_db_pipeline_run" # Test with a local path
    # os.environ["ATOM_USER_ID_FOR_INGESTION"] = "test_user_pipeline_run"
    # os.environ["PROCESSING_MODE"] = "full"

    asyncio.run(main())
    pass
