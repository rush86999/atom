import asyncio
import logging

# Assuming handlers are in the same directory or path is configured
try:
    from . import meilisearch_handler
    from . import lancedb_handler
except ImportError:
    import meilisearch_handler
    import lancedb_handler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Centralized Index Configurations ---

MEILISEARCH_INDEX_NAME = "atom_general_documents"
MEILISEARCH_PRIMARY_KEY = "doc_id"

# Single source of truth for the Meilisearch index settings.
# This ensures consistency between ingestion and filtering.
MEILISEARCH_INDEX_SETTINGS = {
    'filterableAttributes': [
        'doc_id', 'user_id', 'doc_type', 'source_uri', 'title',
        'processing_status',
        # Timestamps for date filtering
        'ingested_at_timestamp',
        'created_at_source_timestamp',
        'last_modified_source_timestamp',
        # Common metadata properties from DOCX, etc.
        'author', 'category'
    ],
    'sortableAttributes': [
        'ingested_at_timestamp',
        'created_at_source_timestamp',
        'last_modified_source_timestamp',
        'title'
    ],
    'searchableAttributes': [
        'title', 'extracted_text', 'source_uri', 'doc_type', 'author', 'subject', 'keywords'
    ]
    # Add other settings like synonyms, stop-words etc. here as needed
}


async def setup_meilisearch():
    """
    Ensures the Meilisearch index exists and has the correct settings.
    This function is idempotent.
    """
    logger.info(f"--- Starting Meilisearch Setup for index: '{MEILISEARCH_INDEX_NAME}' ---")

    # The handler's get_or_create_index is already idempotent
    index = await meilisearch_handler.get_or_create_index(MEILISEARCH_INDEX_NAME, primary_key=MEILISEARCH_PRIMARY_KEY)

    if not index:
        logger.error("Failed to get or create Meilisearch index. Aborting setup.")
        return

    logger.info(f"Index '{MEILISEARCH_INDEX_NAME}' ensured. Now applying settings...")

    # The handler's update_index_settings is also idempotent
    settings_update_result = await meilisearch_handler.update_index_settings(MEILISEARCH_INDEX_NAME, MEILISEARCH_INDEX_SETTINGS)

    if settings_update_result.get("status") == "success":
        logger.info(f"Successfully applied settings for index '{MEILISEARCH_INDEX_NAME}'. Task UID: {settings_update_result.get('task_uid')}")
    else:
        logger.error(f"Failed to apply settings for index '{MEILISEARCH_INDEX_NAME}': {settings_update_result.get('message')}")

    logger.info("--- Meilisearch Setup Complete ---")


async def setup_lancedb():
    """
    Ensures all necessary LanceDB tables are created.
    """
    logger.info("--- Starting LanceDB Setup ---")
    db_conn = await lancedb_handler.get_lancedb_connection()
    if not db_conn:
        logger.error("Failed to connect to LanceDB. Aborting setup.")
        return

    # This function from the handler already checks for existence before creating
    success = await lancedb_handler.create_generic_document_tables_if_not_exist(db_conn)
    if success:
        logger.info("LanceDB generic document tables ensured.")
    else:
        logger.error("Failed to ensure LanceDB generic document tables.")

    logger.info("--- LanceDB Setup Complete ---")


async def main():
    """Main function to run all setup tasks."""
    logger.info("Starting all index setup tasks...")
    await setup_meilisearch()
    await setup_lancedb()
    logger.info("All index setup tasks finished.")


if __name__ == "__main__":
    # This allows the script to be run directly, e.g., during a Docker container's startup command.
    # Note: Ensure environment variables like MEILI_MASTER_KEY and LANCEDB_URI are available.
    if not meilisearch_handler.MEILI_MASTER_KEY:
        print("Error: MEILI_MASTER_KEY environment variable is not set. This script cannot run.")
    else:
        asyncio.run(main())
