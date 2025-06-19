import flask
import os
import sys
import importlib
import traceback # For more detailed error logging

# Add parent 'functions' directory to sys.path for sibling imports
PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
FUNCTIONS_DIR_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT))
if FUNCTIONS_DIR_PATH not in sys.path:
    sys.path.append(FUNCTIONS_DIR_PATH)

# --- Module Imports & Initializations ---
ZoomAgent = None
process_live_audio_for_notion = None
note_utils_module = None

# Set dummy env vars for note_utils client initializations BEFORE first import of note_utils
# These are fallbacks if not set in the function's actual runtime environment.
os.environ.setdefault('NOTION_API_TOKEN', 'dummy_notion_token_for_handler_execution')
os.environ.setdefault('NOTION_NOTES_DATABASE_ID', 'dummy_notion_db_id_for_handler_execution')
os.environ.setdefault('DEEPGRAM_API_KEY', 'dummy_deepgram_key_for_handler_execution')
os.environ.setdefault('OPENAI_API_KEY', 'dummy_openai_key_for_handler_execution')
os.environ.setdefault('OPENAI_API_ENDPOINT', 'https://api.openai.com/v1/chat/completions')
os.environ.setdefault('GPT_MODEL_NAME', 'gpt-3.5-turbo')

try:
    from agents.zoom_agent import ZoomAgent as ImportedZoomAgent
    ZoomAgent = ImportedZoomAgent

    if 'note_utils' in sys.modules:
        note_utils_module = importlib.reload(sys.modules['note_utils'])
    else:
        import note_utils as nu_module
        note_utils_module = nu_module

    if note_utils_module:
        process_live_audio_for_notion = getattr(note_utils_module, 'process_live_audio_for_notion', None)

    if ZoomAgent is None:
        print("Error: ZoomAgent failed to import.", file=sys.stderr)
    if process_live_audio_for_notion is None:
        print("Error: process_live_audio_for_notion not found in note_utils module after reload.", file=sys.stderr)

except ImportError as e:
    print(f"Critical Import Error in attend_live_meeting handler: {e}", file=sys.stderr)

app = flask.Flask(__name__)

@app.route('/', methods=['POST'])
def attend_live_meeting_route():
    # Standardized Python dictionary response structure:
    # Success: {"ok": True, "data": ...}
    # Error:   {"ok": False, "error": {"code": "...", "message": "...", "details": ...}}

    if ZoomAgent is None or process_live_audio_for_notion is None:
        print("Error: Core components (ZoomAgent or process_live_audio_for_notion) not loaded.", file=sys.stderr)
        return flask.jsonify({
            "ok": False,
            "error": {"code": "SERVICE_UNAVAILABLE", "message": "Agent components not loaded due to server-side import error."}
        }), 500

    try:
        payload = flask.request.get_json()
        action_input = payload.get('action_input', {})
        session_variables = payload.get('session_variables', {})

        platform = action_input.get('platform')
        meeting_identifier = action_input.get('meeting_identifier')
        notion_note_title = action_input.get('notion_note_title')
        notion_source = action_input.get('notion_source')
        linked_event_id = action_input.get('linked_event_id')
        user_id = session_variables.get('x-hasura-user-id')

        required_params = {
            "platform": platform, "meeting_identifier": meeting_identifier,
            "notion_note_title": notion_note_title, "notion_source": notion_source,
            "user_id (from session)": user_id
        }
        missing_params = [k for k, v in required_params.items() if not v]

        if missing_params:
            return flask.jsonify({
                "ok": False,
                "error": {"code": "VALIDATION_ERROR", "message": f"Missing required parameters: {', '.join(missing_params)}"}
            }), 400

        if platform.lower() != "zoom": # Currently only ZoomAgent is confirmed to be imported
            return flask.jsonify({
                "ok": False,
                "error": {"code": "NOT_IMPLEMENTED", "message": f"Platform '{platform}' is not supported for live attendance yet."}
            }), 400

        agent = ZoomAgent(user_id=user_id)

        print(f"Handler: Attempting to join meeting {meeting_identifier} for user {user_id}", file=sys.stderr)

        join_success = agent.join_meeting(meeting_identifier)
        # TODO: Refactor agent.join_meeting to return a structured response or throw specific errors.
        # For now, assuming it returns boolean and errors are handled internally or not critical for this step.

        if join_success:
            print(f"Handler: Successfully joined {meeting_identifier}. Starting live processing.", file=sys.stderr)

            processing_result = process_live_audio_for_notion(
                platform_module=agent,
                meeting_id=agent.get_current_meeting_id() or meeting_identifier,
                notion_note_title=notion_note_title,
                notion_source=notion_source,
                linked_event_id=linked_event_id
            )

            print(f"Handler: Live processing completed for {meeting_identifier}. Ensuring agent leaves.", file=sys.stderr)
            agent.leave_meeting()

            if processing_result and processing_result.get("status") == "success":
                print(f"Handler: Notion page processed: {processing_result.get('data')}", file=sys.stderr)
                return flask.jsonify({
                    "ok": True,
                    "data": processing_result.get("data")
                }), 200
            else:
                error_message = processing_result.get("message", "Processing failed with no specific message.") if processing_result else "Processing function returned None or unexpected format."
                error_details = processing_result.get("details") if processing_result else None
                error_code = "PROCESSING_FAILED"

                if isinstance(error_details, dict) and "code" in error_details: # If note_utils returned a code in details
                    error_code = error_details["code"]
                elif isinstance(error_details, str) and error_details.isupper(): # Heuristic for code in details string
                    error_code = error_details

                print(f"Handler: Processing finished with error: {error_message}", file=sys.stderr)
                return flask.jsonify({
                    "ok": False,
                    "error": {
                        "code": error_code,
                        "message": error_message,
                        "details": error_details if not isinstance(error_details, str) or error_code == "PROCESSING_FAILED" else None
                        }
                }), 500
        else:
            # Assuming agent.join_meeting failure implies an issue that should be reported as a server-side problem or specific join error
            print(f"Handler: Failed to join meeting {meeting_identifier}", file=sys.stderr)
            return flask.jsonify({
                "ok": False,
                "error": {"code": "JOIN_MEETING_FAILED", "message": f"Failed to join meeting: {meeting_identifier}. Check agent logs."}
            }), 500

    except Exception as e:
        print(f"Critical error in attend_live_meeting handler: {str(e)}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return flask.jsonify({
            "ok": False,
            "error": { "code": "INTERNAL_SERVER_ERROR", "message": f"An internal error occurred: {str(e)}" }
        }), 500

if __name__ == '__main__':
    print("Starting local Flask server for attend_live_meeting handler on port 5000 (debug mode)...", file=sys.stderr)
    app.run(port=int(os.environ.get("PORT", 5000)), debug=True)
