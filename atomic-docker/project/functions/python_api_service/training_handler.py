import sys
import os
from flask import Flask, request, jsonify

# Adjust sys.path to allow imports from parent 'functions' directory
FUNCTIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if FUNCTIONS_DIR not in sys.path:
    sys.path.append(FUNCTIONS_DIR)
ATOM_AGENT_DIR = os.path.join(FUNCTIONS_DIR, 'atom-agent') # For note_utils if it's there
if ATOM_AGENT_DIR not in sys.path: # research_agent is inside atom-agent
    sys.path.append(ATOM_AGENT_DIR)


try:
    import note_utils # For get_text_embedding_openai
    from _utils import lancedb_service # For upsert_training_event_vector
except ImportError as e:
    print(f"Error importing modules in training_handler: {e}", file=sys.stderr)
    print(f"sys.path: {sys.path}", file=sys.stderr)
    raise

app = Flask(__name__)

@app.errorhandler(Exception)
def handle_exception(e):
    """Return JSON instead of HTML for any other server error."""
    print(f"Unhandled exception: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    response = {
        "ok": False,
        "error": {
            "code": "PYTHON_UNHANDLED_ERROR",
            "message": "An unexpected error occurred on the server.",
            "details": str(e)
        }
    }
    return jsonify(response), 500

@app.route('/train-event-for-similarity', methods=['POST'])
def train_event_route():
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

    required_params = ['event_id', 'user_id', 'event_text', 'openai_api_key']
    missing_params = [param for param in required_params if param not in data]
    if missing_params:
        return jsonify({"ok": False, "error": {"code": "MISSING_PARAMETERS", "message": f"Missing parameters: {', '.join(missing_params)}"}}), 400

    event_id = data['event_id']
    user_id = data['user_id']
    event_text = data['event_text']
    openai_api_key = data['openai_api_key']

    lancedb_uri = os.environ.get('LANCEDB_URI')
    if not lancedb_uri:
        return jsonify({"ok": False, "error": {"code": "PYTHON_ERROR_CONFIG_ERROR", "message": "LANCEDB_URI environment variable not set."}}), 500

    # 1. Get embedding for the event text
    embedding_response = note_utils.get_text_embedding_openai(
        event_text, openai_api_key_param=openai_api_key
    )

    if embedding_response["status"] != "success":
        print(f"Failed to get embedding for training event {event_id}: {embedding_response.get('message')}")
        return jsonify({"ok": False, "error": {"code": f"PYTHON_ERROR_{embedding_response.get('code', 'EMBEDDING_FAILED')}", "message": embedding_response.get("message"), "details": embedding_response.get("details")}}), 500

    query_vector = embedding_response["data"]

    # 2. Upsert into LanceDB
    try:
        upsert_result = lancedb_service.upsert_training_event_vector(
            db_path=lancedb_uri,
            event_id=event_id,
            user_id=user_id,
            event_text=event_text, # Store the source text for reference
            vector_embedding=query_vector,
            table_name="training_events" # Explicitly use "training_events"
        )

        if upsert_result["status"] == "success":
            return jsonify({"ok": True, "data": {"message": "Event training data saved.", "event_id": event_id, "operation": upsert_result.get("operation")}}), 200
        else:
            print(f"LanceDB upsert failed for training event {event_id}: {upsert_result.get('message')}")
            return jsonify({"ok": False, "error": {"code": f"PYTHON_ERROR_{upsert_result.get('code', 'LANCEDB_UPSERT_FAILED')}", "message": upsert_result.get("message"), "details": upsert_result.get("details")}}), 500

    except Exception as e:
        # This will be caught by the generic app.errorhandler if not more specific
        message = f"Unexpected error during training event upsert for event {event_id}: {str(e)}"
        print(message)
        raise # Re-raise for the app error handler

if __name__ == '__main__':
    flask_port = int(os.environ.get("TRAINING_HANDLER_PORT", 5058))
    app.run(host='0.0.0.0', port=flask_port, debug=True)

[end of atomic-docker/project/functions/python_api_service/training_handler.py]
