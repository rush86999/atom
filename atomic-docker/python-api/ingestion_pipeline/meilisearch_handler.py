import meilisearch
import os
import logging
from typing import List, Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

MEILI_HTTP_ADDR = os.getenv("MEILI_HTTP_ADDR", "http://meilisearch:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY") # Should be set in the environment

# Global client instance
_meili_client: Optional[meilisearch.Client] = None

def get_meilisearch_client() -> Optional[meilisearch.Client]:
    """
    Initializes and returns a Meilisearch client instance.
    Reads URL and master key from environment variables.
    """
    global _meili_client
    if _meili_client is None:
        if not MEILI_MASTER_KEY:
            logger.error("MEILI_MASTER_KEY environment variable is not set. Cannot initialize Meilisearch client.")
            return None
        try:
            logger.info(f"Initializing Meilisearch client for URL: {MEILI_HTTP_ADDR}")
            _meili_client = meilisearch.Client(MEILI_HTTP_ADDR, MEILI_MASTER_KEY)
            if not _meili_client.is_healthy():
                logger.warning("Meilisearch client initialized but service is not healthy.")
            else:
                logger.info("Meilisearch client initialized and service is healthy.")
        except Exception as e:
            logger.error(f"Failed to initialize Meilisearch client: {e}", exc_info=True)
            return None
    return _meili_client

async def get_or_create_index(index_name: str, primary_key: Optional[str] = None) -> Optional[meilisearch.index.Index]:
    """
    Gets an existing index or creates it if it doesn't exist.
    Returns the index object or None on failure.
    """
    client = get_meilisearch_client()
    if not client:
        return None
    try:
        logger.info(f"Attempting to get or create index: {index_name} with primary key: {primary_key}")
        # get_index will raise an error if index does not exist, so we try/except
        try:
            index = client.get_index(uid=index_name)
            logger.info(f"Index '{index_name}' found.")
            # If primary_key is provided and differs from existing, it's an issue.
            # However, Meilisearch doesn't allow changing primary_key after creation easily.
            # For simplicity, we assume if index exists, its primary_key is correctly set.
        except meilisearch.errors.MeilisearchApiError as e:
            if e.code == "index_not_found":
                logger.info(f"Index '{index_name}' not found. Creating with primary key: {primary_key or 'None (auto-inferred by Meilisearch)'}.")
                task = client.create_index(uid=index_name, options={'primaryKey': primary_key} if primary_key else {})
                client.wait_for_task(task.task_uid) # Wait for index creation to complete
                index = client.get_index(uid=index_name)
                logger.info(f"Index '{index_name}' created successfully.")
            else:
                raise # Re-raise other API errors
        return index
    except Exception as e:
        logger.error(f"Error getting or creating index '{index_name}': {e}", exc_info=True)
        return None

async def add_documents_to_index(index_name: str, documents: List[Dict[str, Any]], primary_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Adds a list of documents to the specified index.
    'primary_key' can be specified if adding docs to a new index where Meili should infer it,
    or if you want to ensure it during the add operation (though usually set at index creation).
    """
    index = await get_or_create_index(index_name, primary_key=primary_key)
    if not index:
        return {"status": "error", "message": f"Failed to get or create index '{index_name}'."}

    if not documents:
        logger.info(f"No documents provided to add to index '{index_name}'.")
        return {"status": "success", "message": "No documents to add."}

    try:
        logger.info(f"Adding {len(documents)} documents to index '{index_name}'. First doc keys: {documents[0].keys() if documents else 'N/A'}")
        task_info = index.add_documents(documents, primary_key=primary_key)
        # Asynchronous operation, client can wait for task completion
        # For critical ops, waiting is good. For bulk, maybe not always.
        client = get_meilisearch_client()
        if client:
            final_task_status = client.wait_for_task(task_info.task_uid, timeout_in_ms=20000, interval_in_ms=100) # Wait up to 20s
            if final_task_status.status == 'succeeded':
                logger.info(f"Successfully added documents to index '{index_name}'. Task UID: {task_info.task_uid}")
                return {"status": "success", "task_uid": task_info.task_uid, "details": final_task_status.details}
            else:
                logger.error(f"Meilisearch task {task_info.task_uid} for adding documents to '{index_name}' did not succeed: {final_task_status.status}, Error: {final_task_status.error}")
                return {"status": "error", "message": f"Task failed: {final_task_status.status}", "task_uid": task_info.task_uid, "error_details": final_task_status.error}
        else: # Should not happen if index was retrieved
            return {"status": "error", "message": "Meilisearch client not available for waiting for task."}

    except Exception as e:
        logger.error(f"Error adding documents to index '{index_name}': {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

async def search_in_index(index_name: str, query: str, search_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Performs a search in the specified index.
    search_params can include options like 'limit', 'offset', 'filter', 'attributesToHighlight', etc.
    """
    client = get_meilisearch_client()
    if not client:
        return {"status": "error", "message": "Meilisearch client not available."}
    try:
        index = client.index(index_name) # More direct way to get index object if it's known to exist
        logger.info(f"Searching in index '{index_name}' for query: '{query}' with params: {search_params}")
        results = index.search(query, opt_params=search_params if search_params else {})
        return {"status": "success", "data": results}
    except meilisearch.errors.MeilisearchApiError as e:
        if e.code == "index_not_found":
            logger.warning(f"Search failed: Index '{index_name}' not found.")
            return {"status": "error", "message": f"Index '{index_name}' not found.", "code": e.code}
        logger.error(f"Meilisearch API error during search in '{index_name}': {e}", exc_info=True)
        return {"status": "error", "message": str(e), "code": e.code}
    except Exception as e:
        logger.error(f"Error searching in index '{index_name}': {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

async def update_index_settings(index_name: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Updates settings for a given index (e.g., filterableAttributes, sortableAttributes).
    """
    index = await get_or_create_index(index_name) # Ensure index exists
    if not index:
        return {"status": "error", "message": f"Failed to get or create index '{index_name}' for settings update."}

    try:
        logger.info(f"Updating settings for index '{index_name}': {settings}")
        task_info = index.update_settings(settings)
        client = get_meilisearch_client()
        if client:
            final_task_status = client.wait_for_task(task_info.task_uid)
            if final_task_status.status == 'succeeded':
                logger.info(f"Successfully updated settings for index '{index_name}'. Task UID: {task_info.task_uid}")
                return {"status": "success", "task_uid": task_info.task_uid}
            else:
                logger.error(f"Meilisearch task {task_info.task_uid} for updating settings for '{index_name}' did not succeed: {final_task_status.status}, Error: {final_task_status.error}")
                return {"status": "error", "message": f"Task failed: {final_task_status.status}", "task_uid": task_info.task_uid, "error_details": final_task_status.error}

        return {"status": "error", "message": "Meilisearch client not available for waiting for task."}
    except Exception as e:
        logger.error(f"Error updating settings for index '{index_name}': {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

# Example usage (for testing purposes, can be removed or run under if __name__ == '__main__')
async def example_meili_operations():
    client = get_meilisearch_client()
    if not client:
        logger.error("Cannot run example: Meilisearch client failed to initialize.")
        return

    index_name = "atom_documents_test"
    doc_id_field = "doc_id" # Assuming 'doc_id' will be our primary key

    # 1. Get or create index
    logger.info(f"\n--- Ensuring index '{index_name}' with primary key '{doc_id_field}' ---")
    index_obj = await get_or_create_index(index_name, primary_key=doc_id_field)
    if not index_obj: return

    # 2. Update settings (example: filterable and sortable attributes)
    # Important: Define these based on the actual fields you will store and need for searching/filtering.
    # For generic documents, common fields might be 'doc_type', 'user_id', 'source_uri_keyword' (if tokenized differently), 'title_keyword', 'created_at_source_timestamp'
    # For now, a simple example:
    logger.info(f"\n--- Updating settings for '{index_name}' ---")
    settings_to_update = {
        'filterableAttributes': ['doc_id', 'user_id', 'doc_type', 'title', 'source_uri'],
        'sortableAttributes': ['ingested_at', 'title'] # Example: if you store ingestion_at as sortable
    }
    # It's good practice to fetch current settings and merge, or decide to overwrite.
    # For simplicity, this example overwrites.
    # current_settings = index_obj.get_settings()
    # merged_settings = {**current_settings, **settings_to_update} # Example merge
    update_settings_result = await update_index_settings(index_name, settings_to_update)
    logger.info(f"Update settings result: {update_settings_result}")


    # 3. Add documents
    logger.info(f"\n--- Adding documents to '{index_name}' ---")
    documents_to_add = [
        {doc_id_field: "doc_123", "user_id": "user_alpha", "title": "First Test Document about AI", "content": "This document discusses artificial intelligence and machine learning.", "doc_type": "report", "ingested_at": "2023-01-15T10:00:00Z", "source_uri": "/path/to/doc1.pdf"},
        {doc_id_field: "doc_456", "user_id": "user_beta", "title": "Second Test Note on Python", "content": "Python is a versatile programming language used in AI and web development.", "doc_type": "note", "ingested_at": "2023-01-16T11:30:00Z", "source_uri": "http://example.com/note2"},
        {doc_id_field: "doc_789", "user_id": "user_alpha", "title": "Exploring Quantum AI", "content": "Quantum computing could revolutionize AI in the future.", "doc_type": "article", "ingested_at": "2023-01-17T14:20:00Z", "source_uri": "https://example.com/quantum_ai_article"}
    ]
    # Note: 'primary_key_on_add' is set to doc_id_field here.
    # If get_or_create_index already set it, this is redundant but harmless.
    # If index was auto-created by Meili on first add, this would set it.
    add_result = await add_documents_to_index(index_name, documents_to_add, primary_key_on_add=doc_id_field)
    logger.info(f"Add documents result: {add_result}")

    if add_result.get("status") == "success":
        # 4. Search documents
        logger.info(f"\n--- Searching in '{index_name}' for 'AI' ---")
        search_result_ai = await search_in_index(index_name, "AI")
        logger.info(f"Search for 'AI' result: {json.dumps(search_result_ai, indent=2)}")

        logger.info(f"\n--- Searching in '{index_name}' for 'Python' with filter ---")
        search_params_python = {'filter': "doc_type = 'note'"}
        search_result_python = await search_in_index(index_name, "Python", search_params=search_params_python)
        logger.info(f"Search for 'Python' (type:note) result: {json.dumps(search_result_python, indent=2)}")

        logger.info(f"\n--- Searching in '{index_name}' for 'Test' sorted by title ---")
        search_params_sort = {'sort': ['title:asc']}
        search_result_sort = await search_in_index(index_name, "Test", search_params=search_params_sort)
        logger.info(f"Search for 'Test' (sorted) result: {json.dumps(search_result_sort, indent=2)}")


if __name__ == "__main__":
    import asyncio
    import json # For pretty printing results in example
    # Setup basic logging for the example
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Note: Ensure MEILI_MASTER_KEY is set in your environment to run this example
    if not MEILI_MASTER_KEY:
        print("Error: MEILI_MASTER_KEY environment variable is not set. This example cannot run.")
        print("Please set it, e.g., export MEILI_MASTER_KEY='YourDevMasterKey'")
    else:
        asyncio.run(example_meili_operations())

# Considerations for production:
# - Robust error handling and retries for network issues.
# - Configuration for timeouts, connection pooling (if SDK supports/needs it).
# - More sophisticated logging and monitoring.
# - Handling of Meilisearch task queue and status checks more explicitly for critical operations.
# - Security: Ensure MEILI_MASTER_KEY is well-protected. Consider API keys with limited permissions for less sensitive operations if applicable.
# - For `add_documents_to_index`, the `primary_key_on_add` parameter is mostly useful if you let Meilisearch create the index
#   implicitly on the first add. If you use `get_or_create_index` first to explicitly create/retrieve it with a primary key,
#   then passing `primary_key` again to `add_documents` is not strictly necessary for that specific index.
#   However, it's good practice to be explicit, especially if the documents might target different indexes.
