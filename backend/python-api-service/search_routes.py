import os
import tempfile
import logging
from datetime import datetime
from typing import List, Dict, Any

# Set up logging
logger = logging.getLogger(__name__)

# Mock Flask for local testing when not available
try:
    from flask import Blueprint, request, jsonify  # type: ignore
except ImportError:
    logger.warning("Flask not available, using mock implementations")

    class Blueprint:
        def __init__(self, name, import_name):
            self.name = name
            self.import_name = import_name
            self._routes = {}

        def route(self, rule, **options):
            def decorator(f):
                self._routes[rule] = f
                return f
            return decorator

    class _Request:
        def __init__(self):
            self.json = {}
            self.args = {}

        def get_json(self):
            return self.json

    request = _Request()

    def jsonify(data):
        return data

# Mock ingestion_pipeline for local testing
class MockIngestionPipeline:
    # type: ignore[misc]
    @staticmethod
    def add_document(doc_path, user_id, db_uri):
        logger.info(f"Mock: Would add document {doc_path} for user {user_id}")
        return {"status": "success", "message": "Mock document added"}

    @staticmethod
    def add_youtube_transcript(url, user_id, db_uri):
        logger.info(f"Mock: Would add YouTube transcript from {url} for user {user_id}")
        return {"status": "success", "message": "Mock YouTube transcript added"}

# Mock note_utils for local testing
class MockNoteUtils:
    # type: ignore[misc]
    @staticmethod
    def get_text_embedding_openai(text_to_embed, openai_api_key_param=None, embedding_model="text-embedding-3-small"):
        if not text_to_embed:
            return {"status": "error", "message": "Text to embed cannot be empty."}
        # Return mock embedding vector with correct dimensions
        mock_vector = [0.01] * 1536  # Standard dimension for text-embedding-3-small
        return {"status": "success", "data": mock_vector}

    @staticmethod
    def create_note(user_id, title, content, tags=None):
        return {
            "id": f"mock_note_{user_id}_{datetime.now().timestamp()}",
            "title": title,
            "content": content,
            "tags": tags or [],
            "created_at": datetime.now().isoformat()
        }

    @staticmethod
    def update_note(note_id, title=None, content=None, tags=None):
        return {
            "id": note_id,
            "title": title,
            "content": content,
            "tags": tags,
            "updated_at": datetime.now().isoformat()
        }

    @staticmethod
    def delete_note(note_id):
        return {"status": "success", "message": f"Note {note_id} deleted"}

    @staticmethod
    def get_note(note_id):
        return {
            "id": note_id,
            "title": "Mock Note",
            "content": "This is mock note content",
            "tags": ["mock", "test"],
            "created_at": datetime.now().isoformat()
        }

# Mock LanceDB service for local testing
class MockLanceDBService:
    # type: ignore[misc]
    def __init__(self):
        self.db_path = None

    def search_meeting_transcripts(self, user_id: str, query_vector: List[float], limit: int = 10) -> List[Dict[str, Any]]:
        """Mock search for meeting transcripts"""
        return [
            {
                            "transcript_id": f"mock_transcript_{i}",
                            "meeting_title": f"Mock Meeting {i}",
                            "content": f"This is mock transcript content for meeting {i}",
                            "timestamp": datetime.now().isoformat(),
                            "score": 0.9 - (i * 0.1)
                        }
                        for i in range(min(limit, 3))
                    ]

    def hybrid_note_search(self, user_id: str, query_vector: List[float], text_query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Mock hybrid search for notes"""
        return [
            {
                "note_id": f"mock_note_{i}",
                "title": f"Mock Note {i}",
                "content": f"This is mock note content related to: {text_query}",
                "tags": ["mock", "test"],
                "score": 0.95 - (i * 0.05)
            }
            for i in range(min(limit, 5))
        ]

    def search_similar_notes(self, **kwargs) -> Dict[str, Any]:
        """Mock search for similar notes"""
        limit = kwargs.get('limit', 5)
        return {
            "status": "success",
            "results": [
                {
                    "note_id": f"mock_similar_{i}",
                    "title": f"Similar Note {i}",
                    "content": "Mock similar content",
                    "similarity": 0.9 - (i * 0.1)
                }
                for i in range(min(limit, 3))
            ]
        }

# Try to import real implementations, fall back to mocks
try:
    from ._utils import lancedb_service  # type: ignore
    logger.info("Successfully imported lancedb_service")
except ImportError:
    logger.warning("Could not import lancedb_service, using mock")
    lancedb_service = MockLanceDBService()

try:
    from .note_utils import get_text_embedding_openai, create_note, update_note, delete_note, get_note  # type: ignore
    note_utils = None  # We imported individual functions
    logger.info("Successfully imported note_utils functions")
except ImportError:
    logger.warning("Could not import note_utils, using mock")
    note_utils = MockNoteUtils()
    get_text_embedding_openai = note_utils.get_text_embedding_openai
    create_note = note_utils.create_note
    update_note = note_utils.update_note
    delete_note = note_utils.delete_note
    get_note = note_utils.get_note

try:
    import ingestion_pipeline  # type: ignore
    logger.info("Successfully imported ingestion_pipeline")
except ImportError:
    logger.warning("Could not import ingestion_pipeline  # type: ignore, using mock")
    ingestion_pipeline = MockIngestionPipeline()

# Create Blueprint
search_routes_bp = Blueprint('search_routes_bp', __name__)

@search_routes_bp.route('/semantic_search_meetings', methods=['POST'])
def semantic_search_meetings_route():
    """Search meeting transcripts using semantic similarity"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Request must be JSON."}), 400

        query_text = data.get('query')
        user_id = data.get('user_id')
        limit = data.get('limit', 5)

        if not query_text:
            return jsonify({"status": "error", "message": "Missing 'query' in request body."}), 400

        db_path = os.environ.get("LANCEDB_URI", "/tmp/mock_lancedb")

        # Get embedding for query
        openai_api_key = data.get('openai_api_key')
        embedding_response = get_text_embedding_openai(
            text_to_embed=query_text,
            openai_api_key_param=openai_api_key
        )

        if embedding_response.get('status') != 'success':
            return jsonify({
                "status": "error",
                "message": f"Failed to generate embedding: {embedding_response.get('message', 'Unknown error')}"
            }), 500

        query_vector = embedding_response.get('data', [])

        # Search meeting transcripts
        results = lancedb_service.search_meeting_transcripts(
            user_id=user_id,
            query_vector=query_vector,
            limit=limit
        )

        return jsonify({
            "status": "success",
            "results": results,
            "count": len(results)
        })

    except Exception as e:
        logger.error(f"Error in semantic_search_meetings_route: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@search_routes_bp.route('/hybrid_search_notes', methods=['POST'])
def hybrid_search_notes_route():
    """Hybrid search combining semantic and keyword search for notes"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Request must be JSON."}), 400

        query_text = data.get('query')
        user_id = data.get('user_id')
        limit = data.get('limit', 10)

        if not query_text:
            return jsonify({"status": "error", "message": "Missing 'query' in request body."}), 400

        # Get embedding for query
        openai_api_key = data.get('openai_api_key')
        embedding_response = get_text_embedding_openai(
            text_to_embed=query_text,
            openai_api_key_param=openai_api_key
        )

        if embedding_response.get('status') != 'success':
            return jsonify({
                "status": "error",
                "message": f"Failed to generate embedding: {embedding_response.get('message', 'Unknown error')}"
            }), 500

        query_vector = embedding_response.get('data', [])

        # Perform hybrid search
        results = lancedb_service.hybrid_note_search(
            user_id=user_id,
            query_vector=query_vector,
            text_query=query_text,
            limit=limit
        )

        return jsonify({
            "status": "success",
            "results": results,
            "count": len(results)
        })

    except Exception as e:
        logger.error(f"Error in hybrid_search_notes_route: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@search_routes_bp.route('/add_document', methods=['POST'])
def add_document_route():
    """Add a document to the search index"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Request must be JSON."}), 400

        doc_content = data.get('content')
        doc_title = data.get('title', 'Untitled Document')
        user_id = data.get('user_id')
        doc_type = data.get('type', 'text')

        if not doc_content:
            return jsonify({"status": "error", "message": "Missing 'content' in request body."}), 400

        if not user_id:
            return jsonify({"status": "error", "message": "Missing 'user_id' in request body."}), 400

        # Save content to temporary file for processing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_file:
            tmp_file.write(doc_content)
            tmp_file_path = tmp_file.name

        try:
            db_uri = os.environ.get("LANCEDB_URI", "/tmp/mock_lancedb")

            # Add document to index
            result = ingestion_pipeline.add_document(
                doc_path=tmp_file_path,
                user_id=user_id,
                db_uri=db_uri
            )

            # Create a note for the document
            note = create_note(
                user_id=user_id,
                title=doc_title,
                content=doc_content[:1000],  # Store first 1000 chars in note
                tags=[doc_type, 'imported']
            )

            return jsonify({
                "status": "success",
                "message": "Document added successfully",
                "note_id": note.get('id'),
                "ingestion_result": result
            })

        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    except Exception as e:
        logger.error(f"Error in add_document_route: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@search_routes_bp.route('/add_youtube_transcript', methods=['POST'])
def add_youtube_transcript_route():
    """Add a YouTube video transcript to the search index"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Request must be JSON."}), 400

        youtube_url = data.get('url')
        user_id = data.get('user_id')

        if not youtube_url:
            return jsonify({"status": "error", "message": "Missing 'url' in request body."}), 400

        if not user_id:
            return jsonify({"status": "error", "message": "Missing 'user_id' in request body."}), 400

        db_uri = os.environ.get("LANCEDB_URI", "/tmp/mock_lancedb")

        # Add YouTube transcript to index
        result = ingestion_pipeline.add_youtube_transcript(
            url=youtube_url,
            user_id=user_id,
            db_uri=db_uri
        )

        return jsonify({
            "status": "success",
            "message": "YouTube transcript added successfully",
            "url": youtube_url,
            "ingestion_result": result
        })

    except Exception as e:
        logger.error(f"Error in add_youtube_transcript_route: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@search_routes_bp.route('/search_similar_notes', methods=['POST'])
def search_similar_notes_route():
    """Search for similar notes"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Request must be JSON."}), 400

        note_id = data.get('note_id')
        query_text = data.get('query')
        user_id = data.get('user_id')
        limit = data.get('limit', 5)

        if not (note_id or query_text):
            return jsonify({"status": "error", "message": "Either 'note_id' or 'query' must be provided."}), 400

        # If note_id provided, get the note content as query
        if note_id and not query_text:
            note = get_note(note_id)
            if note:
                query_text = f"{note.get('title', '')} {note.get('content', '')}"
            else:
                return jsonify({"status": "error", "message": f"Note {note_id} not found."}), 404

        db_path = os.environ.get("LANCEDB_URI", "/tmp/mock_lancedb")

        # Search for similar notes
        result = lancedb_service.search_similar_notes(
            db_path=db_path,
            user_id=user_id,
            query_text=query_text,
            limit=limit
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in search_similar_notes_route: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Export the blueprint
__all__ = ['search_routes_bp']
