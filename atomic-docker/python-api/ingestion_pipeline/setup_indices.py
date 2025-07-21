import asyncio
import logging

# Assuming handlers are in the same directory or path is configured
try:
    from . import lancedb_handler
except ImportError:
    import lancedb_handler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    await setup_lancedb()
    logger.info("All index setup tasks finished.")


if __name__ == "__main__":
    # This allows the script to be run directly, e.g., during a Docker container's startup command.
    # Note: Ensure environment variables like LANCEDB_URI are available.
    asyncio.run(main())
