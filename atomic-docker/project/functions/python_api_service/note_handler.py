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

app = Flask(__name__)

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

@app.route('/create-live-audio-note', methods=['POST'])
async def create_live_audio_note_route(): # Made async
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

    required_params = [
        'meeting_id', 'title', 'platform_module_name', # platform_module_name to dynamically import
        'notion_api_token', 'deepgram_api_key', 'openai_api_key'
    ]
    missing_params = [param for param in required_params if param not in data]
    if missing_params:
        return jsonify({"ok": False, "error": {"code": "MISSING_PARAMETERS", "message": f"Missing parameters: {', '.join(missing_params)}"}}), 400

    # Initialize Notion (Deepgram is initialized within transcribe_audio_deepgram_stream)
    init_error = _init_clients_from_request_data(data)
    if init_error: return jsonify(init_error), 500

    platform_module_name = data['platform_module_name']
    meeting_id = data['meeting_id']
    title = data['title']
    notion_db_id = data.get('notion_db_id')
    notion_source = data.get('notion_source', 'Live Meeting Transcription')
    linked_task_id = data.get('linked_task_id')
    linked_event_id = data.get('linked_event_id')
    deepgram_api_key = data['deepgram_api_key']
    openai_api_key = data['openai_api_key']

    # --- Conceptual Platform Module Import ---
    # This is a placeholder for how a real system might load the correct audio source.
    # In a real scenario, this might involve a registry or more secure import mechanism.
    platform_module = None
    if platform_module_name == "conceptual_zoom_agent_module": # Example
        # from project.functions.agents import zoom_agent # Example import
        # platform_module = zoom_agent.ZoomAudioCaptureModule() # Conceptual
        # For this test, we'll mock it if it's not a real module.
        try:
            # Attempt to import if it's a real, accessible module path
            # This is generally not safe for arbitrary strings.
            # A fixed mapping or registry would be better.
            # import importlib
            # platform_module = importlib.import_module(platform_module_name)
            pass # For now, we don't have a real module to import here
        except ImportError:
            print(f"Warning: Could not import platform module '{platform_module_name}'. Live transcription will likely fail unless note_utils has a fallback mock.")
            # Allow to proceed if note_utils has a test/mock mode not requiring real module

    if platform_module is None:
        # If no real module, use a mock that simulates an empty async iterator
        # This allows testing the flow of process_live_audio_for_notion without a real audio source.
        class MockPlatformModule:
            async def start_audio_capture(self, meeting_id_ignored):
                print("MockPlatformModule: Simulating start_audio_capture with no audio data.")
                # Yield nothing to simulate an empty or immediately finished stream
                if False: # Ensure it's an async generator
                    yield b''
            def stop_audio_capture(self):
                print("MockPlatformModule: Simulating stop_audio_capture.")
                pass
        platform_module = MockPlatformModule()
    # --- End Conceptual Platform Module ---

    try:
        # Run the async function using asyncio.run() or ensure Flask is async compatible (e.g. Quart, or run in thread)
        # For simplicity with standard Flask, run in a new event loop if needed,
        # though ideally Flask itself would be async (e.g. Quart).
        # For this subtask, we'll assume the environment can call asyncio.run or similar.
        # If this handler is part of a larger async app, direct await might be fine.
        # A simple way for standard Flask:
        # result = asyncio.run(note_utils.process_live_audio_for_notion(...))
        # However, Flask routes are typically synchronous.
        # To call async code from sync Flask, you might use:
        # loop = asyncio.new_event_loop()
        # asyncio.set_event_loop(loop)
        # result = loop.run_until_complete(note_utils.process_live_audio_for_notion(...))
        # loop.close()
        # This can be problematic with nested loops or existing loops.
        # For now, let's assume the calling environment/WSGI server handles async properly or this is simplified.
        # The `await` keyword suggests this handler itself is async.

        result = await note_utils.process_live_audio_for_notion(
            platform_module=platform_module, # Pass the conceptual or mock module
            meeting_id=meeting_id,
            notion_note_title=title,
            deepgram_api_key=deepgram_api_key,
            openai_api_key=openai_api_key,
            notion_db_id=notion_db_id,
            notion_source=notion_source,
            linked_task_id=linked_task_id,
            linked_event_id=linked_event_id
        )

        if result["status"] == "success":
            return jsonify({"ok": True, "data": result.get("data")}), 201
        else:
            return jsonify({"ok": False, "error": {"code": f"PYTHON_ERROR_{result.get('code', 'LIVE_AUDIO_NOTE_FAILED')}", "message": result.get("message"), "details": result.get("details")}}), 500

    except Exception as e:
        # This will be caught by the generic app.errorhandler if not more specific
        print(f"Exception in /create-live-audio-note route: {e}")
        raise


@app.route('/search-similar-notes', methods=['POST'])
def search_similar_notes_route():
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

    required_params = ['query_text', 'user_id', 'openai_api_key']
    missing_params = [param for param in required_params if param not in data]
    if missing_params:
        return jsonify({"ok": False, "error": {"code": "MISSING_PARAMETERS", "message": f"Missing parameters: {', '.join(missing_params)}"}}), 400

    query_text = data['query_text']
    user_id = data['user_id'] # Required for user-specific search
    openai_api_key = data['openai_api_key']
    limit = data.get('limit', 5)
    if not isinstance(limit, int) or limit <= 0:
        limit = 5

    lancedb_uri = os.environ.get('LANCEDB_URI')
    if not lancedb_uri:
        return jsonify({"ok": False, "error": {"code": "PYTHON_ERROR_CONFIG_ERROR", "message": "LANCEDB_URI environment variable not set."}}), 500

    # 1. Get embedding for the query text
    embedding_response = note_utils.get_text_embedding_openai(
        query_text, openai_api_key_param=openai_api_key
    )

    if embedding_response["status"] != "success":
        print(f"Failed to get embedding for similarity search: {embedding_response.get('message')}")
        return jsonify({"ok": False, "error": {"code": f"PYTHON_ERROR_{embedding_response.get('code', 'EMBEDDING_FAILED')}", "message": embedding_response.get("message"), "details": embedding_response.get("details")}}), 500

    query_vector = embedding_response["data"]

    # 2. Search in LanceDB
    try:
        from _utils import lancedb_service # Assuming _utils is in sys.path
        search_result = lancedb_service.search_similar_notes(
            db_path=lancedb_uri,
            query_vector=query_vector,
            user_id=user_id, # Filter by user_id
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
        # This will be caught by the generic app.errorhandler if not caught more specifically
        raise

[end of atomic-docker/project/functions/python_api_service/note_handler.py]
