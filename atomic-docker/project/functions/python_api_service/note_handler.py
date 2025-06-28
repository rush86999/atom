import sys
import os
from flask import Flask, request, jsonify

# Adjust sys.path to allow imports from parent 'functions' directory
FUNCTIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if FUNCTIONS_DIR not in sys.path:
    sys.path.append(FUNCTIONS_DIR)

try:
    import note_utils
except ImportError as e:
    print(f"Error importing note_utils: {e}", file=sys.stderr)
    print(f"sys.path: {sys.path}", file=sys.stderr)
    raise

# Try to import search_routes blueprint
try:
    from .search_routes import search_routes_bp
except ImportError as e:
    print(f"Warning: Could not import search_routes_bp: {e}. Search routes will not be available.", file=sys.stderr)
    search_routes_bp = None

# Try to import task_routes blueprint
try:
    from .task_routes import task_bp
except ImportError as e:
    print(f"Warning: Could not import task_bp: {e}. Task routes will not be available.", file=sys.stderr)
    task_bp = None


app = Flask(__name__)

# Register the search blueprint if successfully imported
if search_routes_bp:
    app.register_blueprint(search_routes_bp, url_prefix='/api')
    print("Successfully registered search_routes_bp with /api prefix.")
else:
    print("Search routes blueprint (search_routes_bp) not registered as it failed to import.")

# Register the task blueprint if successfully imported
if task_bp:
    app.register_blueprint(task_bp, url_prefix='/api') # Using same /api prefix for now
    print("Successfully registered task_bp with /api prefix.")
else:
    print("Task routes blueprint (task_bp) not registered as it failed to import.")


@app.errorhandler(Exception)
def handle_exception(e):
    """Return JSON instead of HTML for any other server error."""
    print(f"Unhandled exception: {e}", file=sys.stderr)
    # Consider using traceback.format_exc() for more detailed logging in debug mode
    # import traceback
    # print(traceback.format_exc(), file=sys.stderr)
    response = {
        "ok": False,
        "error": {
            "code": "PYTHON_UNHANDLED_ERROR",
            "message": "An unexpected error occurred on the server.",
            "details": str(e)
        }
    }
    return jsonify(response), 500

def _init_clients_from_request_data(data: dict) -> dict | None:
    """Helper to initialize Notion and Deepgram from request data if tokens are present."""
    notion_api_token = data.get('notion_api_token')
    deepgram_api_key = data.get('deepgram_api_key') # For audio processing

    if notion_api_token:
        init_status = note_utils.init_notion(notion_api_token, data.get('notion_db_id')) # Pass DB ID for default
        if init_status["status"] != "success":
            return {"ok": False, "error": {"code": f"PYTHON_ERROR_NOTION_INIT_FAILED", "message": init_status["message"], "details": init_status.get("details")}}
    # else: some routes might not need Notion if only, e.g., transcribing. But most here do.

    if deepgram_api_key: # Only init if key is provided for relevant routes
        init_dg_status = note_utils.init_deepgram(deepgram_api_key)
        if init_dg_status["status"] != "success":
            return {"ok": False, "error": {"code": f"PYTHON_ERROR_DEEPGRAM_INIT_FAILED", "message": init_dg_status["message"], "details": init_dg_status.get("details")}}
    return None


@app.route('/create-note', methods=['POST'])
def create_note_route():
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

    required_params = ['title', 'content', 'notion_api_token']
    missing_params = [param for param in required_params if param not in data]
    if missing_params:
        return jsonify({"ok": False, "error": {"code": "MISSING_PARAMETERS", "message": f"Missing parameters: {', '.join(missing_params)}"}}), 400

    init_error = _init_clients_from_request_data(data)
    if init_error: return jsonify(init_error), 500

    user_id = data.get('user_id') # Optional, for LanceDB user context

    # notion_db_id is optional for create_notion_note, will use global default if not set by init_notion or here
    notion_result = note_utils.create_notion_note(
        title=data['title'],
        content=data['content'],
        notion_db_id=data.get('notion_db_id'), # Allows overriding default DB
        source=data.get('source', 'API'),
        linked_task_id=data.get('linked_task_id'),
        linked_event_id=data.get('linked_event_id'),
        transcription=data.get('transcription'),
        audio_file_link=data.get('audio_file_link'),
        summary=data.get('summary'),
        key_points=data.get('key_points')
    )

    if notion_result["status"] == "success":
        page_id = notion_result.get("data", {}).get("page_id")
        page_url = notion_result.get("data", {}).get("url")

        # --- Vector Embedding and Upsert ---
        vector_update_status = "skipped" # Default if no embedding attempted
        vector_error_message = None

        openai_api_key = data.get('openai_api_key') # Required for embedding
        lancedb_uri = os.environ.get('LANCEDB_URI') # Get from environment

        text_to_embed = data['content'] # Using the main content for embedding
        # Could also concatenate title + content or other fields if desired

        if not openai_api_key:
            vector_update_status = "failed"
            vector_error_message = "OpenAI API key not provided in request for embedding."
            print(f"Warning for note {page_id}: {vector_error_message}")
        elif not lancedb_uri:
            vector_update_status = "failed"
            vector_error_message = "LANCEDB_URI environment variable not set for vector upsert."
            print(f"Warning for note {page_id}: {vector_error_message}")
        elif page_id and text_to_embed:
            try:
                embedding_response = note_utils.get_text_embedding_openai(
                    text_to_embed, openai_api_key_param=openai_api_key
                )
                if embedding_response["status"] == "success":
                    vector = embedding_response["data"]
                    # Dynamically import lancedb_service here to keep its dependencies optional if not used
                    try:
                        from _utils import lancedb_service # Assuming _utils is in sys.path via FUNCTIONS_DIR
                        upsert_result = lancedb_service.upsert_note_vector(
                            db_path=lancedb_uri,
                            note_id=page_id,
                            user_id=user_id, # Pass user_id if available
                            text_content=text_to_embed,
                            vector_embedding=vector
                        )
                        if upsert_result["status"] == "success":
                            vector_update_status = upsert_result.get("operation", "success") # e.g., "added/updated", "skipped"
                        else:
                            vector_update_status = "failed"
                            vector_error_message = upsert_result.get("message", "LanceDB upsert failed.")
                            print(f"Error upserting vector for note {page_id}: {vector_error_message} (Code: {upsert_result.get('code')})")
                    except ImportError:
                        vector_update_status = "failed"
                        vector_error_message = "LanceDB service module not found or import error."
                        print(f"Error for note {page_id}: {vector_error_message}")
                    except Exception as ldb_e:
                        vector_update_status = "failed"
                        vector_error_message = f"LanceDB operation error: {str(ldb_e)}"
                        print(f"Error for note {page_id}: {vector_error_message}")

                else:
                    vector_update_status = "failed"
                    vector_error_message = embedding_response.get("message", "Embedding generation failed.")
                    print(f"Error generating embedding for note {page_id}: {vector_error_message} (Code: {embedding_response.get('code')})")
            except Exception as e:
                vector_update_status = "failed"
                vector_error_message = f"Unexpected error during vector processing: {str(e)}"
                print(f"Error for note {page_id}: {vector_error_message}")
        else:
            if not page_id: print("Warning: No page_id returned from Notion, skipping vector upsert.")
            if not text_to_embed: print(f"Warning: No text content to embed for note {page_id}, skipping vector upsert.")
            vector_update_status = "skipped_no_content_or_id"


        return jsonify({
            "ok": True,
            "data": {
                "page_id": page_id,
                "url": page_url,
                "vector_status": vector_update_status,
                "vector_message": vector_error_message
            }
        }), 201
    else: # Notion note creation failed
        return jsonify({"ok": False, "error": {"code": f"PYTHON_ERROR_{notion_result.get('code', 'CREATE_NOTE_FAILED')}", "message": notion_result.get("message"), "details": notion_result.get("details")}}), 500


@app.route('/create-audio-note-url', methods=['POST'])
def create_audio_note_url_route():
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

    required_params = ['audio_url', 'title', 'notion_api_token', 'deepgram_api_key', 'openai_api_key']
    missing_params = [param for param in required_params if param not in data]
    if missing_params:
        return jsonify({"ok": False, "error": {"code": "MISSING_PARAMETERS", "message": f"Missing parameters: {', '.join(missing_params)}"}}), 400

    init_error = _init_clients_from_request_data(data)
    if init_error: return jsonify(init_error), 500

    deepgram_api_key = data['deepgram_api_key']
    openai_api_key = data['openai_api_key']
    user_id = data.get('user_id') # Optional, for LanceDB user context for the audio note's content

    notion_result = note_utils.process_audio_url_for_notion(
        audio_url=data['audio_url'],
        title=data['title'],
        notion_db_id=data.get('notion_db_id'),
        notion_source_text=data.get('notion_source', 'Audio URL Note'),
        linked_task_id=data.get('linked_task_id'),
        linked_event_id=data.get('linked_event_id'),
        deepgram_api_key=deepgram_api_key,
        openai_api_key=openai_api_key
    )

    if notion_result["status"] == "success":
        page_id = notion_result.get("data", {}).get("notion_page_id")
        page_url = notion_result.get("data", {}).get("url")
        summary = notion_result.get("data", {}).get("summary")
        key_points = notion_result.get("data", {}).get("key_points")
        # For audio notes, the content to embed might be the transcription or summary.
        # Let's assume transcription is primary content for embedding if available.
        # The `process_audio_url_for_notion` needs to return the transcription text.
        # For now, let's assume the main content for embedding is summary or title if no transcript.
        # This part needs `process_audio_url_for_notion` to return the text used for embedding.
        # For now, we'll embed the summary if available.
        text_to_embed_for_audio = summary if summary else data['title']


        vector_update_status = "skipped"
        vector_error_message = None
        lancedb_uri = os.environ.get('LANCEDB_URI')

        if not lancedb_uri:
            vector_update_status = "failed"
            vector_error_message = "LANCEDB_URI environment variable not set."
            print(f"Warning for audio note {page_id}: {vector_error_message}")
        elif page_id and text_to_embed_for_audio:
            try:
                embedding_response = note_utils.get_text_embedding_openai(
                    text_to_embed_for_audio, openai_api_key_param=openai_api_key
                )
                if embedding_response["status"] == "success":
                    vector = embedding_response["data"]
                    try:
                        from _utils import lancedb_service
                        upsert_result = lancedb_service.upsert_note_vector(
                            db_path=lancedb_uri, note_id=page_id, user_id=user_id,
                            text_content=text_to_embed_for_audio, vector_embedding=vector
                        )
                        if upsert_result["status"] == "success": vector_update_status = upsert_result.get("operation", "success")
                        else:
                            vector_update_status = "failed"; vector_error_message = upsert_result.get("message")
                            print(f"Error upserting vector for audio note {page_id}: {vector_error_message}")
                    except ImportError:
                        vector_update_status = "failed"; vector_error_message = "LanceDB service module not found."
                        print(f"Error for audio note {page_id}: {vector_error_message}")
                    except Exception as ldb_e:
                        vector_update_status = "failed"; vector_error_message = f"LanceDB error: {str(ldb_e)}"
                        print(f"Error for audio note {page_id}: {vector_error_message}")
                else:
                    vector_update_status = "failed"; vector_error_message = embedding_response.get("message")
                    print(f"Error embedding audio note {page_id}: {vector_error_message}")
            except Exception as e:
                vector_update_status = "failed"; vector_error_message = f"Vector processing error: {str(e)}"
                print(f"Error for audio note {page_id}: {vector_error_message}")
        else:
            if not page_id: print("Warning: No page_id for audio note, skipping vector upsert.")
            if not text_to_embed_for_audio: print(f"Warning: No text content to embed for audio note {page_id}.")
            vector_update_status = "skipped_no_content_or_id"

        return jsonify({
            "ok": True,
            "data": {
                "page_id": page_id, "url": page_url, "summary": summary, "key_points": key_points,
                "vector_status": vector_update_status, "vector_message": vector_error_message
            }
        }), 201
    else: # Notion note creation from audio failed
        return jsonify({"ok": False, "error": {"code": f"PYTHON_ERROR_{notion_result.get('code', 'AUDIO_NOTE_FAILED')}", "message": notion_result.get("message"), "details": notion_result.get("details")}}), 500


@app.route('/search-notes', methods=['POST'])
def search_notes_route():
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

    required_params = ['query_text', 'notion_api_token']
    missing_params = [param for param in required_params if param not in data]
    if missing_params:
        return jsonify({"ok": False, "error": {"code": "MISSING_PARAMETERS", "message": f"Missing parameters: {', '.join(missing_params)}"}}), 400

    init_error = _init_clients_from_request_data(data)
    if init_error: return jsonify(init_error), 500

    result = note_utils.search_notion_notes(
        query=data['query_text'],
        notion_db_id=data.get('notion_db_id'), # Allows searching specific DB or default
        source=data.get('source')
    )

    if result["status"] == "success":
        return jsonify({"ok": True, "data": result.get("data")}), 200
    else:
        return jsonify({"ok": False, "error": {"code": f"PYTHON_ERROR_{result.get('code', 'SEARCH_NOTES_FAILED')}", "message": result.get("message"), "details": result.get("details")}}), 500

if __name__ == '__main__':
    flask_port = int(os.environ.get("NOTE_HANDLER_PORT", 5057))
    app.run(host='0.0.0.0', port=flask_port, debug=True)

# Note: For live transcription, the platform_module providing audio is conceptual.
# This endpoint assumes such a module can be resolved and used by note_utils.
# The actual audio capture mechanism is outside the scope of this handler.
import asyncio # For running async process_live_audio_for_notion
import tempfile # For handling temporary audio files
import shutil # For robustly removing temporary directories

# Helper function to ensure API keys are loaded from environment by note_utils
# This function will now primarily focus on initializing Notion client if needed,
# as Deepgram and OpenAI keys are expected to be picked up by note_utils from env.
def _ensure_notion_client(data: dict) -> dict | None:
    """
    Initializes the Notion client using a token from the request or environment.
    Ensures that critical API keys (Deepgram, OpenAI) are available in the environment
    for note_utils to consume.
    """
    # Critical Check: Ensure backend services have their API keys from the environment
    # These checks are more for developer awareness during startup/testing.
    # note_utils functions themselves will check for these global keys.
    if not note_utils.DEEPGRAM_API_KEY_GLOBAL:
        print("Warning: DEEPGRAM_API_KEY_GLOBAL is not set in the environment. Transcription will fail.", file=sys.stderr)
    if not note_utils.OPENAI_API_KEY_GLOBAL:
        print("Warning: OPENAI_API_KEY_GLOBAL is not set in the environment. Summarization/Embedding will fail.", file=sys.stderr)

    # Initialize Notion client - it requires an API token.
    # For this service, we'll prioritize environment variable for Notion token.
    # If a specific `notion_api_token` is passed in `data` for some reason (e.g. per-user override, legacy),
    # it could be used, but server-side config is preferred.
    notion_api_token_from_env = os.environ.get("NOTION_API_TOKEN")
    notion_api_token_from_req = data.get('notion_api_token') # Kept for flexibility if needed

    # Prioritize token from request if provided, otherwise from environment.
    # This behavior might need to be stricter depending on security policies.
    # For a service endpoint, relying solely on env var for its own Notion access is common.
    token_to_use = notion_api_token_from_req or notion_api_token_from_env

    if not token_to_use:
        return {"ok": False, "error": {"code": "PYTHON_ERROR_NOTION_CONFIG_FAILED", "message": "Notion API token not found in request or environment."}}

    # If notion client is already initialized with the same token, skip re-init
    # This simple check might need to be more robust if DB ID can change per request for the same token
    if note_utils.notion and note_utils.NOTION_API_TOKEN_GLOBAL == token_to_use:
         # If DB ID is also passed and different, re-init might be needed
        if data.get('notion_db_id') and data.get('notion_db_id') != note_utils.NOTION_NOTES_DATABASE_ID_GLOBAL:
            pass # proceed to init
        else:
            return None # Notion client already initialized correctly

    init_status = note_utils.init_notion(token_to_use, data.get('notion_db_id'))
    if init_status["status"] != "success":
        return {"ok": False, "error": {"code": "PYTHON_ERROR_NOTION_INIT_FAILED", "message": init_status["message"], "details": init_status.get("details")}}
    return None


@app.route('/api/process-recorded-audio-note', methods=['POST'])
def process_recorded_audio_note_route():
    temp_audio_path = None
    temp_dir = None

    try:
        if 'audio_file' not in request.files:
            return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Missing 'audio_file' in request."}}), 400

        audio_file = request.files['audio_file']
        if audio_file.filename == '':
            return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "No audio file selected."}}), 400

        # Metadata can be sent as form data fields alongside the file
        title = request.form.get('title', 'New Audio Note') # Default title
        user_id = request.form.get('user_id') # Important for context, LanceDB etc.
        linked_event_id = request.form.get('linked_event_id')
        notion_db_id_override = request.form.get('notion_db_id') # Optional: to use a specific DB

        # Ensure critical API keys are available via environment variables for note_utils
        # The `_ensure_notion_client` function also serves to initialize Notion client.
        # For Deepgram & OpenAI, note_utils directly uses os.environ.get() if no specific key is passed to its functions.
        # We will rely on those environment variables.
        client_init_error = _ensure_notion_client({'notion_db_id': notion_db_id_override}) # Pass DB ID if provided
        if client_init_error:
            return jsonify(client_init_error), 500

        # Securely save uploaded audio to a temporary file
        temp_dir = tempfile.mkdtemp()
        filename = audio_file.filename or "audio_note.tmp" # Use a default if filename is not obvious
        # It's good practice to secure the filename, but for temp files, less critical if access is restricted.
        # from werkzeug.utils import secure_filename
        # secure_name = secure_filename(filename)
        temp_audio_path = os.path.join(temp_dir, filename)
        audio_file.save(temp_audio_path)

        # --- Optional: Upload raw audio to S3 (V1.1 feature) ---
        audio_s3_url = None
        # s3_upload_result = note_utils.upload_audio_to_s3(temp_audio_path, user_id) # Conceptual
        # if s3_upload_result["status"] == "success":
        #    audio_s3_url = s3_upload_result["data"]["url"]
        # else:
        #    print(f"Warning: Failed to upload raw audio to S3: {s3_upload_result['message']}")
            # Decide if this is a critical failure or if we proceed without S3 link


        # --- Transcription ---
        # note_utils.transcribe_audio_deepgram will use DEEPGRAM_API_KEY_GLOBAL from env
        transcript_resp = note_utils.transcribe_audio_deepgram(audio_file_path=temp_audio_path)
        if transcript_resp["status"] == "error":
            return jsonify({"ok": False, "error": {"code": f"PYTHON_ERROR_TRANSCRIPTION_FAILED", "message": transcript_resp.get("message"), "details": transcript_resp.get("details")}}), 500
        transcript = transcript_resp.get("data", {}).get("transcript", "")

        # --- Summarization ---
        summary, key_points_str, decisions_list, action_items_list = "", "", [], []
        if transcript.strip():
            # note_utils.summarize_transcript_gpt will use OPENAI_API_KEY_GLOBAL from env
            summarize_resp = note_utils.summarize_transcript_gpt(transcript=transcript)
            if summarize_resp["status"] == "success":
                summary_data = summarize_resp.get("data", {})
                summary = summary_data.get("summary", "")
                key_points_str = summary_data.get("key_points", "") # Legacy key points string
                decisions_list = summary_data.get("decisions", [])
                action_items_list = summary_data.get("action_items", [])
            else:
                print(f"Warning: Summarization failed for transcript: {summarize_resp['message']}")
                # Proceed without summarization if it fails
        else:
            summary = "No speech detected or transcript was empty."

        # --- Notion Note Creation ---
        # notion_db_id_override will be used by create_notion_note if provided, else global default
        create_note_resp = note_utils.create_notion_note(
            title=title,
            content=f"Audio note recorded on {datetime.now().strftime('%Y-%m-%d %H:%M')}", # Placeholder content
            notion_db_id=notion_db_id_override,
            source="In-Person Audio Note via Agent",
            linked_event_id=linked_event_id,
            transcription=transcript,
            audio_file_link=audio_s3_url, # Will be None if S3 upload not implemented/failed
            summary=summary,
            key_points=key_points_str, # Passing legacy string, can be removed if frontend doesn't need
            decisions=decisions_list,
            action_items=action_items_list
        )

        if create_note_resp["status"] == "error":
            return jsonify({"ok": False, "error": {"code": f"PYTHON_ERROR_NOTION_CREATE_FAILED", "message": create_note_resp.get("message"), "details": create_note_resp.get("details")}}), 500

        notion_page_id = create_note_resp.get("data", {}).get("page_id")
        notion_page_url = create_note_resp.get("data", {}).get("url")

        # --- Optional: Vector Embedding and LanceDB Storage ---
        if notion_page_id and transcript.strip():
            # Construct meeting date for LanceDB - use current time for in-person notes
            meeting_date_iso = datetime.now().isoformat()
            # note_utils.embed_and_store_transcript_in_lancedb will use OPENAI_API_KEY_GLOBAL
            # and LANCEDB_URI from env
            embedding_store_result = note_utils.embed_and_store_transcript_in_lancedb(
                notion_page_id=notion_page_id,
                transcript_text=transcript,
                meeting_title=title,
                meeting_date_iso=meeting_date_iso,
                user_id=user_id
            )
            if embedding_store_result["status"] != "success":
                print(f"Warning: Failed to embed and store transcript in LanceDB: {embedding_store_result['message']}")
                # Non-critical failure, proceed with response

        return jsonify({
            "ok": True,
            "data": {
                "notion_page_id": notion_page_id,
                "notion_page_url": notion_page_url,
                "title": title,
                "summary_preview": summary[:200] if summary else "N/A",
                "transcript_preview": transcript[:200] if transcript else "N/A"
            }
        }), 201

    except Exception as e:
        # This will be caught by the generic app.errorhandler if not more specific
        print(f"Unhandled exception in /api/process-recorded-audio-note: {e}", file=sys.stderr)
        # import traceback
        # print(traceback.format_exc(), file=sys.stderr)
        # Let the app error handler manage the response
        raise
    finally:
        # Cleanup: Remove temporary audio file and directory
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except Exception as e_remove:
                print(f"Error removing temporary audio file {temp_audio_path}: {e_remove}", file=sys.stderr)
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e_rmdir:
                print(f"Error removing temporary directory {temp_dir}: {e_rmdir}", file=sys.stderr)


@app.route('/create-live-audio-note', methods=['POST'])
async def create_live_audio_note_route(): # Made async
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

    # For live audio note, API keys (Notion, Deepgram, OpenAI) are expected to be passed in request
    # This is because the "platform_module" might be external or require per-session keys.
    # This is different from process-recorded-audio-note which relies on server env keys.
    required_params = [
        'meeting_id', 'title', 'platform_module_name',
        'notion_api_token', 'deepgram_api_key', 'openai_api_key'
    ]
    missing_params = [param for param in required_params if param not in data]
    if missing_params:
        return jsonify({"ok": False, "error": {"code": "MISSING_PARAMETERS", "message": f"Missing parameters: {', '.join(missing_params)}"}}), 400

    # Initialize Notion client with token from request for this specific live audio context
    # Deepgram and OpenAI keys are passed directly to note_utils functions for live processing.
    init_error = note_utils.init_notion(data['notion_api_token'], data.get('notion_db_id'))
    if init_error["status"] != "success":
         return jsonify({"ok": False, "error": {"code": "PYTHON_ERROR_NOTION_INIT_FAILED", "message": init_error["message"], "details": init_error.get("details")}}), 500


    platform_module_name = data['platform_module_name']
    meeting_id = data['meeting_id']
    title = data['title']
    # notion_db_id is already passed to init_notion if present in data
    notion_source = data.get('notion_source', 'Live Meeting Transcription')
    linked_task_id = data.get('linked_task_id')
    linked_event_id = data.get('linked_event_id')
    deepgram_api_key_req = data['deepgram_api_key'] # Key from request
    openai_api_key_req = data['openai_api_key']     # Key from request

    # --- Conceptual Platform Module Import ---
    platform_module = None
    if platform_module_name == "conceptual_zoom_agent_module":
        try:
            pass
        except ImportError:
            print(f"Warning: Could not import platform module '{platform_module_name}'. Live transcription will likely fail unless note_utils has a fallback mock.")

    if platform_module is None:
        class MockPlatformModule:
            async def start_audio_capture(self, meeting_id_ignored):
                print("MockPlatformModule: Simulating start_audio_capture with no audio data.")
                if False: yield b''
            def stop_audio_capture(self):
                print("MockPlatformModule: Simulating stop_audio_capture.")
                pass
        platform_module = MockPlatformModule()

    try:
        result = await note_utils.process_live_audio_for_notion(
            platform_module=platform_module,
            meeting_id=meeting_id,
            notion_note_title=title,
            deepgram_api_key=deepgram_api_key_req, # Pass key from request
            openai_api_key=openai_api_key_req,     # Pass key from request
            notion_db_id=data.get('notion_db_id'), # Already handled by init_notion for default
            notion_source=notion_source,
            linked_task_id=linked_task_id,
            linked_event_id=linked_event_id
        )

        if result["status"] == "success":
            return jsonify({"ok": True, "data": result.get("data")}), 201
        else:
            return jsonify({"ok": False, "error": {"code": f"PYTHON_ERROR_{result.get('code', 'LIVE_AUDIO_NOTE_FAILED')}", "message": result.get("message"), "details": result.get("details")}}), 500

    except Exception as e:
        print(f"Exception in /create-live-audio-note route: {e}")
        raise


@app.route('/search-similar-notes', methods=['POST'])
def search_similar_notes_route():
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

    # For similarity search, OpenAI key might be passed if it's user-specific or per-query.
    # However, for consistency with process-recorded-audio-note, let's assume note_utils
    # will use OPENAI_API_KEY_GLOBAL from env for embedding the query text.
    # The request should contain user_id and query_text.
    required_params = ['query_text', 'user_id']
    # openai_api_key removed from required_params, will rely on env for query embedding

    missing_params = [param for param in required_params if param not in data]
    if missing_params:
        return jsonify({"ok": False, "error": {"code": "MISSING_PARAMETERS", "message": f"Missing parameters: {', '.join(missing_params)}"}}), 400

    query_text = data['query_text']
    user_id = data['user_id']
    # openai_api_key_req = data.get('openai_api_key') # Not using this from request for query embedding
    limit = data.get('limit', 5)
    if not isinstance(limit, int) or limit <= 0:
        limit = 5

    lancedb_uri = os.environ.get('LANCEDB_URI')
    if not lancedb_uri:
        return jsonify({"ok": False, "error": {"code": "PYTHON_ERROR_CONFIG_ERROR", "message": "LANCEDB_URI environment variable not set."}}), 500

    if not note_utils.OPENAI_API_KEY_GLOBAL:
         return jsonify({"ok": False, "error": {"code": "PYTHON_ERROR_CONFIG_ERROR", "message": "OpenAI API key not configured on server for query embedding."}}), 500


    # 1. Get embedding for the query text (using server-configured OpenAI key)
    embedding_response = note_utils.get_text_embedding_openai(
        text_to_embed=query_text
        # openai_api_key_param is not passed, so note_utils.get_text_embedding_openai uses OPENAI_API_KEY_GLOBAL
    )

    if embedding_response["status"] != "success":
        print(f"Failed to get embedding for similarity search: {embedding_response.get('message')}")
        return jsonify({"ok": False, "error": {"code": f"PYTHON_ERROR_{embedding_response.get('code', 'EMBEDDING_FAILED')}", "message": embedding_response.get("message"), "details": embedding_response.get("details")}}), 500

    query_vector = embedding_response["data"]

    # 2. Search in LanceDB
    try:
        from _utils import lancedb_service
        search_result = lancedb_service.search_similar_notes(
            db_path=lancedb_uri,
            query_vector=query_vector,
            user_id=user_id,
            limit=limit
        )

        if search_result["status"] == "success":
            return jsonify({"ok": True, "data": search_result.get("data", [])}), 200
        else:
            print(f"LanceDB similarity search failed: {search_result.get('message')}")
            return jsonify({"ok": False, "error": {"code": f"PYTHON_ERROR_{search_result.get('code', 'LANCEDB_SEARCH_FAILED')}", "message": search_result.get("message"), "details": search_result.get("details")}}), 500

    except ImportError:
        message = "LanceDB service module not found or import error for similarity search."
        print(message)
        return jsonify({"ok": False, "error": {"code": "PYTHON_ERROR_IMPORT_ERROR", "message": message}}), 500
    except Exception as e:
        message = f"Unexpected error during similarity search: {str(e)}"
        print(message)
        raise

[end of atomic-docker/project/functions/python_api_service/note_handler.py]
