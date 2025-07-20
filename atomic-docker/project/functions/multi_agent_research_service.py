import asyncio
import os
from typing import List, Dict, Any, Optional

# Dynamically add the path to the ingestion_pipeline to sys.path
# This allows importing hybrid_search_service from a different directory
import sys
INGESTION_PIPELINE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'python-api', 'ingestion_pipeline'))
if INGESTION_PIPELINE_PATH not in sys.path:
    sys.path.append(INGESTION_PIPELINE_PATH)

try:
    from hybrid_search_service import hybrid_search_documents
except ImportError as e:
    print(f"Error: Failed to import search services. Make sure the ingestion_pipeline directory is structured correctly. Details: {e}")
    # Define a dummy function if the import fails
    async def hybrid_search_documents(*args, **kwargs):
        print("Error: hybrid_search_documents is not available due to import failure.")
        return []

# Assume note_utils is in the same directory or accessible
try:
    import note_utils
except ImportError:
    print("Warning: note_utils not found. Some functionalities might be limited.")
    note_utils = None


async def search_meeting_archives(user_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Performs a hybrid search on meeting archives for a given query.
    """
    if not query.strip():
        print("Query is empty, skipping meeting archive search.")
        return []

    print(f"Initiating hybrid search for meeting archives with query: '{query}' for user_id: {user_id}")

    try:
        # Utilize the existing hybrid_search_documents function
        # The key is to correctly set the filters to target meeting transcripts
        filters = {
            "doc_type": "meeting_transcript"  # Assuming 'meeting_transcript' is the doc_type for these archives
        }

        results = await hybrid_search_documents(
            user_id=user_id,
            query_text=query,
            openai_api_key_param=os.getenv("OPENAI_API_KEY"),
            db_conn=None,  # Let the service handle the connection
            meili_client=None,  # Let the service handle the connection
            semantic_limit=top_k,
            keyword_limit=top_k,
            filters=filters
        )

        # Convert Pydantic models to dictionaries
        results_as_dict = [res.dict() if hasattr(res, 'dict') else res for res in results]

        print(f"Found {len(results_as_dict)} results from meeting archives.")
        return results_as_dict[:top_k]

    except Exception as e:
        print(f"Error during meeting archive search: {e}")
        return []
