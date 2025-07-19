import os
import logging
from typing import List, Dict, Any

# Configure logging
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Mock functions for now
async def extract_data_from_local_storage(user_id: str, path: str) -> List[Dict[str, Any]]:
    logger.info(f"Extracting data from local storage for user {user_id} at path {path}")
    # In a real implementation, this would scan the local path for files,
    # read them, and extract their content.
    return [
        {
            "source": "local_storage",
            "document_id": "local_file_abc",
            "document_title": "My Local Document",
            "full_text": "This is a document stored on the local file system.",
            "user_id": user_id,
            "created_at": "2023-02-15T09:00:00Z",
            "last_edited_at": "2023-02-15T09:00:00Z",
            "url": f"file://{path}/my_local_document.txt"
        }
    ]
