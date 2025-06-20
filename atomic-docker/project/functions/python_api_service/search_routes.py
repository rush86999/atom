import os
from flask import Blueprint, request, jsonify
from datetime import datetime

# Attempt to import utilities. Due to the project's structure,
# these imports might need adjustment based on the execution environment (PYTHONPATH).
try:
    from _utils import lancedb_service
    from note_utils import get_text_embedding_openai
except ImportError:
    print("Warning: Could not import lancedb_service or note_utils directly. Using mock for get_text_embedding_openai for subtask robustness.")

    class MockNoteUtilsProvider:
        def get_text_embedding_openai(self, text_to_embed, openai_api_key_param=None, embedding_model="text-embedding-3-small"):
            if not text_to_embed: return {"status": "error", "message": "Mock: Text to embed cannot be empty."}
            # Ensure the mock vector has the correct dimension, e.g., 1536 for text-embedding-3-small
            mock_vector = [0.01] * 1536
            return {"status": "success", "data": mock_vector}

    # Attempt to re-import lancedb_service specifically, assuming it might be in a path recognized by _utils
    # This structure is a bit fragile and depends heavily on PYTHONPATH setup during execution.
    if 'lancedb_service' not in locals():
        try:
            # Assuming _utils is a package relative to where this service runs from,
            # or that PYTHONPATH makes it available.
            from ._utils import lancedb_service # Changed to relative import
        except ImportError:
             # Fallback if relative import fails (e.g. when script is run directly and not as part of a package)
            try:
                from _utils import lancedb_service
            except ImportError as e:
                print(f"Error: Failed to import lancedb_service even with fallbacks: {e}")
                # Define a mock lancedb_service if critical for app to load, though search will fail
                class MockLanceDBService:
                    def search_similar_notes(self, **kwargs):
                        return {"status": "error", "message": "Mock: lancedb_service not available."}
                lancedb_service = MockLanceDBService()


    if 'get_text_embedding_openai' not in locals():
        _mock_nu = MockNoteUtilsProvider()
        get_text_embedding_openai = _mock_nu.get_text_embedding_openai


search_routes_bp = Blueprint('search_routes_bp', __name__)

@search_routes_bp.route('/semantic_search_meetings', methods=['POST'])
def semantic_search_meetings_route():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Request must be JSON."}), 400

    query_text = data.get('query')
    user_id = data.get('user_id') # Optional in search_similar_notes, but good to pass if available

    if not query_text:
        return jsonify({"status": "error", "message": "Missing 'query' in request body."}), 400

    db_path = os.environ.get("LANCEDB_URI")
    if not db_path:
        print("Error: LANCEDB_URI environment variable is not set for search.")
        return jsonify({"status": "error", "message": "Search service not configured (LANCEDB_URI missing)."}), 500

    # openai_api_key can be optional if the embedding function can get it from env,
    # but good practice to allow passing it for multi-tenant or specific key use.
    # The get_text_embedding_openai function in note_utils.py handles fetching from env if not provided.
    openai_api_key = data.get('openai_api_key')

    embedding_response = get_text_embedding_openai(
        text_to_embed=query_text,
        openai_api_key_param=openai_api_key # Pass it, function will use env if this is None
    )

    if embedding_response.get("status") == "error":
        print(f"Error generating query embedding: {embedding_response.get('message')}")
        return jsonify({"status": "error", "message": f"Failed to process query: {embedding_response.get('message')}"}), 500

    query_vector = embedding_response["data"]

    # Call lancedb_service.search_similar_notes
    # Ensure this function is correctly imported and available.
    search_results_response = lancedb_service.search_similar_notes(
        db_path=db_path,
        query_vector=query_vector,
        user_id=user_id, # Pass user_id for filtering if applicable
        table_name="meeting_transcripts",
        limit=5 # Or make limit configurable
    )

    if search_results_response.get("status") == "error":
        print(f"Error searching meeting transcripts: {search_results_response.get('message')}")
        return jsonify({"status": "error", "message": search_results_response.get('message')}), 500

    # Format results for the API response, matching agent's expectations
    formatted_api_results = []
    for item in search_results_response.get("data", []):
        # The 'item' here is expected to be the updated NoteSearchResult TypedDict:
        # {"id": str, "title": Optional[str], "date": Optional[str], "score": float, "user_id": Optional[str]}
        formatted_api_results.append({
            "notion_page_id": item.get("id"), # 'id' field from NoteSearchResult
            "meeting_title": item.get("title"),
            "meeting_date": item.get("date"), # This is already an ISO string
            "score": item.get("score")
        })

    return jsonify({"status": "success", "data": formatted_api_results})
