import os
import logging
from typing import Optional, Dict, Any
from greenhouse import Greenhouse

logger = logging.getLogger(__name__)

async def get_greenhouse_client(user_id: str, db_conn_pool) -> Optional[Greenhouse]:
    # This is a placeholder. In a real application, you would fetch the user's Greenhouse credentials
    # from a secure database. For now, we'll use environment variables.
    # You'll need to create a table to store these credentials, similar to the Dropbox and Google Drive implementations.
    api_key = os.environ.get("GREENHOUSE_API_KEY")

    if not api_key:
        logger.error("Greenhouse API key is not configured in environment variables.")
        return None

    try:
        client = Greenhouse(api_key)
        return client
    except Exception as e:
        logger.error(f"Failed to create Greenhouse client: {e}", exc_info=True)
        return None

async def create_candidate(client: Greenhouse, candidate_data: Dict[str, Any]) -> Dict[str, Any]:
    response = client.candidates.add(candidate_data)
    return response

async def get_candidate(client: Greenhouse, candidate_id: str) -> Dict[str, Any]:
    response = client.candidates.get(candidate_id)
    return response
