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

    # notion_db_id is optional for create_notion_note, will use global default if not set by init_notion or here
    result = note_utils.create_notion_note(
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

    if result["status"] == "success":
        return jsonify({"ok": True, "data": result.get("data")}), 201 # 201 Created
    else:
        return jsonify({"ok": False, "error": {"code": f"PYTHON_ERROR_{result.get('code', 'CREATE_NOTE_FAILED')}", "message": result.get("message"), "details": result.get("details")}}), 500


@app.route('/create-audio-note-url', methods=['POST'])
def create_audio_note_url_route():
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

    required_params = ['audio_url', 'title', 'notion_api_token'] # deepgram_api_key, openai_api_key are checked by note_utils
    missing_params = [param for param in required_params if param not in data]
    if missing_params:
        return jsonify({"ok": False, "error": {"code": "MISSING_PARAMETERS", "message": f"Missing parameters: {', '.join(missing_params)}"}}), 400

    init_error = _init_clients_from_request_data(data) # Initializes Notion & Deepgram if keys present
    if init_error: return jsonify(init_error), 500

    # API keys for Deepgram & OpenAI are passed to process_audio_url_for_notion
    # It will use these or fall back to globals (which might be an issue if globals not set in this env)
    # Best practice: ensure handlers always pass keys explicitly from request/secure config.
    deepgram_api_key = data.get('deepgram_api_key')
    openai_api_key = data.get('openai_api_key')

    if not deepgram_api_key:
        return jsonify({"ok": False, "error": {"code": "MISSING_PARAMETERS", "message": "Missing parameter: deepgram_api_key"}}), 400
    if not openai_api_key:
        return jsonify({"ok": False, "error": {"code": "MISSING_PARAMETERS", "message": "Missing parameter: openai_api_key"}}), 400


    result = note_utils.process_audio_url_for_notion(
        audio_url=data['audio_url'],
        title=data['title'],
        notion_db_id=data.get('notion_db_id'),
        notion_source_text=data.get('notion_source', 'Audio URL Note'),
        linked_task_id=data.get('linked_task_id'),
        linked_event_id=data.get('linked_event_id'),
        deepgram_api_key=deepgram_api_key,
        openai_api_key=openai_api_key
    )

    if result["status"] == "success":
        return jsonify({"ok": True, "data": result.get("data")}), 201
    else:
        return jsonify({"ok": False, "error": {"code": f"PYTHON_ERROR_{result.get('code', 'AUDIO_NOTE_FAILED')}", "message": result.get("message"), "details": result.get("details")}}), 500


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

[end of atomic-docker/project/functions/python_api_service/note_handler.py]
