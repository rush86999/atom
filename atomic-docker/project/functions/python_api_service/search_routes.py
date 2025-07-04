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

    # Call lancedb_service.search_meeting_transcripts
    # Table name should match what the ingestion pipeline uses
    lancedb_table = os.environ.get("LANCEDB_TABLE_NAME", "meeting_transcripts_embeddings")
    limit_param = data.get('limit', 5) # Allow limit to be passed, default to 5

    if not user_id: # user_id is now mandatory for search_meeting_transcripts
        return jsonify({"status": "error", "message": "Missing 'user_id' in request body."}), 400

    search_results_response = lancedb_service.search_meeting_transcripts(
        db_path=db_path,
        query_vector=query_vector,
        user_id=user_id,
        table_name=lancedb_table,
        limit=limit_param
    )

    if search_results_response.get("status") == "error":
        print(f"Error searching meeting transcripts: {search_results_response.get('message')}")
        # Pass through the error code if available from lancedb_service
        error_code = search_results_response.get("code", "SEARCH_FAILED")
        return jsonify({
            "status": "error",
            "message": search_results_response.get('message'),
            "code": error_code
        }), 500

    # The data from search_meeting_transcripts is already a list of SemanticSearchResult TypedDicts.
    # We can return this directly if the agent expects this format.
    # SemanticSearchResult: {notion_page_id, notion_page_title, notion_page_url, text_chunk_preview, score, last_edited_at_notion, user_id}
    # The old response format was: {notion_page_id, meeting_title, meeting_date, score}
    # We need to align this with what atom-agent expects or update atom-agent.
    # For now, let's adapt to a similar structure to the old one for compatibility,
    # but using the new field names from SemanticSearchResult.

    api_response_data = []
    for result_item in search_results_response.get("data", []):
        api_response_data.append({
            "notion_page_id": result_item.get("notion_page_id"),
            "notion_page_title": result_item.get("notion_page_title"),
            "notion_page_url": result_item.get("notion_page_url"),
            "text_preview": result_item.get("text_chunk_preview"), # Added preview
            "last_edited": result_item.get("last_edited_at_notion"), # Changed from meeting_date
            "score": result_item.get("score")
            # user_id is not typically returned in search results list items to the agent
        })

    return jsonify({"status": "success", "data": api_response_data})

# Endpoint for processing agent-recorded in-person audio notes
@search_routes_bp.route('/internal/process_audio_note_data', methods=['POST'])
def process_audio_note_data_route():
    if 'audio_file' not in request.files:
        return jsonify({"ok": False, "error": {"message": "No audio file part in the request.", "code": "MISSING_AUDIO_FILE"}}), 400

    file = request.files['audio_file']
    if file.filename == '':
        return jsonify({"ok": False, "error": {"message": "No selected audio file.", "code": "EMPTY_FILENAME"}}), 400

    title = request.form.get('title', f"Audio Note - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    user_id = request.form.get('user_id')
    linked_event_id = request.form.get('linked_event_id') # Optional

    if not user_id: # user_id is crucial for associating the note
        return jsonify({"ok": False, "error": {"message": "user_id is required.", "code": "MISSING_USER_ID"}}), 400

    # Ensure note_utils has necessary API keys configured via environment variables
    # (DEEPGRAM_API_KEY, OPENAI_API_KEY, NOTION_API_TOKEN, NOTION_NOTES_DATABASE_ID)
    # These are accessed globally within note_utils.py or passed if functions are refactored.
    # For this example, we assume global environment variable access within note_utils.

    # Initialize Notion client if not already (note_utils.init_notion might be called elsewhere too)
    # This is a bit fragile; ideally, client init is handled more centrally or passed around.
    if not note_utils.notion: # Check if global `notion` client in note_utils is set
        notion_api_key = os.environ.get("NOTION_API_TOKEN")
        notion_db_id = os.environ.get("NOTION_NOTES_DATABASE_ID") # Or a specific DB ID for these notes
        if not notion_api_key or not notion_db_id:
            return jsonify({"ok": False, "error": {"message": "Notion API key or Database ID not configured on server.", "code": "NOTION_SERVER_CONFIG_ERROR"}}), 500
        init_status = note_utils.init_notion(api_token=notion_api_key, database_id=notion_db_id)
        if init_status.get("status") == "error":
            return jsonify({"ok": False, "error": {"message": f"Failed to initialize Notion client: {init_status.get('message')}", "code": init_status.get("code", "NOTION_INIT_FAILED")}}), 500

    # Save the uploaded file temporarily to pass its path to transcription
    temp_dir = tempfile.gettempdir()
    temp_audio_path = os.path.join(temp_dir, file.filename if file.filename else "uploaded_audio.tmp")

    try:
        file.save(temp_audio_path)
        print(f"Audio file saved temporarily to: {temp_audio_path}")

        # 1. Transcribe with Deepgram
        # note_utils.transcribe_audio_deepgram expects a file path.
        # It internally gets DEEPGRAM_API_KEY from env.
        print(f"Transcribing audio file: {temp_audio_path} for user {user_id}")
        transcript_resp = note_utils.transcribe_audio_deepgram(audio_file_path=temp_audio_path)

        if transcript_resp.get("status") == "error":
            os.remove(temp_audio_path) # Clean up temp file
            return jsonify({"ok": False, "error": {"message": f"Transcription failed: {transcript_resp.get('message')}", "code": transcript_resp.get("code", "TRANSCRIPTION_FAILED")}}), 500

        transcript = transcript_resp.get("data", {}).get("transcript", "")
        print(f"Transcription successful (first 100 chars): {transcript[:100]}")

        # 2. Summarize with OpenAI
        # note_utils.summarize_transcript_gpt internally gets OPENAI_API_KEY from env.
        summary_data = {"summary": "Summarization skipped or failed.", "decisions": [], "action_items": [], "key_points": ""}
        if transcript.strip(): # Only summarize if transcript is not empty
            print("Summarizing transcript...")
            summarize_resp = note_utils.summarize_transcript_gpt(transcript=transcript)
            if summarize_resp.get("status") == "success":
                summary_data = summarize_resp.get("data", summary_data)
                print("Summarization successful.")
            else:
                print(f"Warning: Summarization failed: {summarize_resp.get('message')}")
                # Continue with saving the note even if summarization fails
        else:
            print("Transcript was empty, skipping summarization.")
            summary_data["summary"] = "No speech detected or transcript was empty."


        # 3. Create Notion Note using the new specialized function
        print("Creating Notion note with structured content...")
        # NOTION_NOTES_DATABASE_ID from env will be used by default in create_processed_audio_note_in_notion
        # if not overridden by init_notion or a specific db_id param.
        create_note_resp = note_utils.create_processed_audio_note_in_notion(
            title=title,
            transcript=transcript,
            summary_data=summary_data, # Contains summary, decisions, action_items
            source="In-Person Agent Audio Note", # Default source
            linked_event_id=linked_event_id
        )

        os.remove(temp_audio_path) # Clean up temp file

        if create_note_resp.get("status") == "success":
            page_info = create_note_resp.get("data", {})
            print(f"Notion note created: {page_info.get('url')}")
            return jsonify({
                "ok": True,
                "message": "Audio note processed and saved to Notion.",
                "data": {
                    "notion_page_url": page_info.get("url"),
                    "notion_page_id": page_info.get("page_id"),
                    "title": title, # Return the title used/generated
                    "summary_preview": summary_data.get("summary", "")[:200] # Provide a preview
                }
            }), 200
        else:
            return jsonify({"ok": False, "error": {"message": f"Failed to create Notion note: {create_note_resp.get('message')}", "code": create_note_resp.get("code", "NOTION_CREATE_FAILED")}}), 500

    except Exception as e:
        if os.path.exists(temp_audio_path): # Ensure cleanup on any error
            os.remove(temp_audio_path)
        print(f"Error processing audio note data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": {"message": f"Internal server error processing audio: {str(e)}", "code": "AUDIO_PROCESSING_ERROR"}}), 500
