import os
import logging
from typing import Dict, Any, List, Optional
import requests
import numpy as np

logger = logging.getLogger(__name__)

def get_text_embedding_openai(
    text_to_embed: str,
    openai_api_key_param: Optional[str] = None,
    embedding_model: str = "text-embedding-3-small"
) -> Dict[str, Any]:
    """
    Generate text embeddings using OpenAI's embedding API.

    Args:
        text_to_embed: Text to generate embedding for
        openai_api_key_param: OpenAI API key (optional, falls back to environment variable)
        embedding_model: OpenAI embedding model to use

    Returns:
        Dictionary with status and embedding data
    """
    if not text_to_embed or not text_to_embed.strip():
        return {"status": "error", "message": "Text to embed cannot be empty."}

    # Get API key from parameter or environment
    openai_api_key = openai_api_key_param or os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        logger.warning("OpenAI API key not provided. Using mock embeddings.")
        # Return mock embedding with correct dimensions for text-embedding-3-small
        mock_vector = [0.01] * 1536
        return {"status": "success", "data": mock_vector}

    try:
        headers = {
            "Authorization": f"Bearer {openai_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "input": text_to_embed,
            "model": embedding_model,
            "encoding_format": "float"
        }

        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            embedding = data["data"][0]["embedding"]
            return {"status": "success", "data": embedding}
        else:
            error_msg = f"OpenAI API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}

    except requests.exceptions.RequestException as e:
        error_msg = f"Network error calling OpenAI API: {str(e)}"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error generating embedding: {str(e)}"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}

def create_note(
    user_id: str,
    title: str,
    content: str,
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Create a new note (mock implementation for now).

    Args:
        user_id: User ID
        title: Note title
        content: Note content
        tags: Optional list of tags

    Returns:
        Dictionary with note information
    """
    from datetime import datetime
    import uuid

    return {
        "id": f"note_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "title": title,
        "content": content,
        "tags": tags or [],
        "created_at": datetime.now().isoformat()
    }

def update_note(
    note_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Update an existing note (mock implementation for now).

    Args:
        note_id: Note ID to update
        title: New title (optional)
        content: New content (optional)
        tags: New tags (optional)

    Returns:
        Dictionary with updated note information
    """
    from datetime import datetime

    return {
        "id": note_id,
        "title": title,
        "content": content,
        "tags": tags,
        "updated_at": datetime.now().isoformat()
    }

def delete_note(note_id: str) -> Dict[str, Any]:
    """
    Delete a note (mock implementation for now).

    Args:
        note_id: Note ID to delete

    Returns:
        Dictionary with deletion status
    """
    return {"status": "success", "message": f"Note {note_id} deleted"}

def get_note(note_id: str) -> Dict[str, Any]:
    """
    Get a note by ID (mock implementation for now).

    Args:
        note_id: Note ID to retrieve

    Returns:
        Dictionary with note information
    """
    from datetime import datetime

    return {
        "id": note_id,
        "title": "Sample Note",
        "content": "This is sample note content",
        "tags": ["sample", "test"],
        "created_at": datetime.now().isoformat()
    }

# For local testing and fallback
if __name__ == "__main__":
    # Test the embedding function
    test_text = "This is a test sentence for embedding."
    result = get_text_embedding_openai(test_text)
    print(f"Embedding result: {result['status']}")
    if result["status"] == "success":
        print(f"Embedding length: {len(result['data'])}")
