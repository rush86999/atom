import os
import sys
from flask import Flask, request, jsonify

# Add the parent directory (functions) to sys.path to allow sibling imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from note_utils import process_audio_for_note
except ImportError:
    # Fallback for environments where the above path adjustment might not be enough
    # or if running this script directly for testing (though imports might still fail without more context)
    print("Error: Could not import process_audio_for_note. Ensure note_utils.py is accessible.")
    # Define a dummy function if import fails, so Flask can still start for basic testing
    def process_audio_for_note(*args, **kwargs):
        return "Error: process_audio_for_note function not loaded."

app = Flask(__name__)

@app.route('/', methods=['POST']) # Default endpoint for the service
def handle_action():
    try:
        req_data = request.get_json()

        # Hasura sends action arguments inside input.arg1 (default behavior)
        # Or directly in input if request_transform is configured differently.
        # Based on the YAML, we expect input.arg1
        action_args = req_data.get("input", {}).get("arg1")

        if not action_args:
            return jsonify({
                "status": "error",
                "error": "Invalid request structure: 'input.arg1' is missing."
            }), 400

        audio_file_path = action_args.get("audio_file_path")
        if not audio_file_path:
            return jsonify({
                "status": "error",
                "error": "Missing required argument: audio_file_path"
            }), 400

        # Optional arguments
        note_id = action_args.get("note_id")
        title = action_args.get("title")
        content = action_args.get("content")
        source = action_args.get("source")
        linked_task_id = action_args.get("linked_task_id")
        linked_event_id = action_args.get("linked_event_id")

        # Call the core logic function
        # Ensure all arguments are passed correctly, using defaults from process_audio_for_note if not provided
        result_note_id_or_error = process_audio_for_note(
            audio_file_path=audio_file_path,
            note_id=note_id,
            title=title if title is not None else "New Audio Note", # Pass defaults if None
            content=content if content is not None else "",
            source=source if source is not None else "Audio Upload",
            linked_task_id=linked_task_id,
            linked_event_id=linked_event_id
        )

        if "Error:" in result_note_id_or_error or "failed:" in result_note_id_or_error.lower() or result_note_id_or_error is None:
            return jsonify({
                "status": "error",
                "error": str(result_note_id_or_error)
            })
        else:
            return jsonify({
                "note_id": result_note_id_or_error,
                "status": "success"
            })

    except Exception as e:
        app.logger.error(f"Error processing action: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "error": f"An unexpected error occurred: {str(e)}"
        }), 500

if __name__ == '__main__':
    # This is for local development/testing.
    # In a serverless environment, a WSGI server like Gunicorn would run the app.
    # The port should be configurable via environment variable for production.
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=True, host='0.0.0.0', port=port)
