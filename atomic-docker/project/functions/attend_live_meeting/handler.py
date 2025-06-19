import flask # Changed from 'import flask as flask' to just 'import flask'
import os
import sys
import importlib # Added for potential module reloading

# Add parent 'functions' directory to sys.path for sibling imports
PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
FUNCTIONS_DIR_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT))
if FUNCTIONS_DIR_PATH not in sys.path:
    sys.path.append(FUNCTIONS_DIR_PATH)

# --- Module Imports & Initializations ---
ZoomAgent = None
process_live_audio_for_notion = None
note_utils_module = None # To hold the reloaded module reference

# Set dummy env vars for note_utils client initializations BEFORE first import of note_utils
# These are fallbacks if not set in the function's actual runtime environment.
os.environ.setdefault('NOTION_API_TOKEN', 'dummy_notion_token_for_handler_execution')
os.environ.setdefault('NOTION_NOTES_DATABASE_ID', 'dummy_notion_db_id_for_handler_execution')
os.environ.setdefault('DEEPGRAM_API_KEY', 'dummy_deepgram_key_for_handler_execution')
os.environ.setdefault('OPENAI_API_KEY', 'dummy_openai_key_for_handler_execution')
os.environ.setdefault('OPENAI_API_ENDPOINT', 'https://api.openai.com/v1/chat/completions')
os.environ.setdefault('GPT_MODEL_NAME', 'gpt-3.5-turbo')

try:
    # It's important that agents.zoom_agent and note_utils are in the Python path.
    # For Hasura serverless functions, this means they need to be part of the deployment package.
    from agents.zoom_agent import ZoomAgent as ImportedZoomAgent
    ZoomAgent = ImportedZoomAgent

    # Reload note_utils to ensure it picks up env vars set just above,
    # as its clients (Notion, Deepgram, OpenAI config) are often initialized at module level.
    if 'note_utils' in sys.modules:
        note_utils_module = importlib.reload(sys.modules['note_utils'])
    else:
        import note_utils as nu_module # Initial import
        note_utils_module = nu_module

    if note_utils_module:
        process_live_audio_for_notion = getattr(note_utils_module, 'process_live_audio_for_notion', None)

    if ZoomAgent is None:
        print("Error: ZoomAgent failed to import.", file=sys.stderr)
    if process_live_audio_for_notion is None:
        print("Error: process_live_audio_for_notion not found in note_utils module after reload.", file=sys.stderr)

except ImportError as e:
    print(f"Critical Import Error in attend_live_meeting handler: {e}", file=sys.stderr)
    # ZoomAgent and process_live_audio_for_notion will remain None


app = flask.Flask(__name__)

@app.route('/', methods=['POST'])
def attend_live_meeting_route(): # Renamed function to avoid conflict with any potential module name
    if ZoomAgent is None or process_live_audio_for_notion is None:
        print("Error: Core components (ZoomAgent or process_live_audio_for_notion) not loaded.", file=sys.stderr)
        return flask.jsonify({
            "status": "Error",
            "error_message": "Agent components not loaded due to server-side import error."
        }), 500

    try:
        payload = flask.request.get_json()
        # Using 'action_input' based on the request_transform in actions.yaml
        action_input = payload.get('action_input', {})
        session_variables = payload.get('session_variables', {})

        platform = action_input.get('platform')
        meeting_identifier = action_input.get('meeting_identifier') # Changed from 'meeting_id' to match GraphQL input
        notion_note_title = action_input.get('notion_note_title')
        notion_source = action_input.get('notion_source')
        linked_event_id = action_input.get('linked_event_id') # Optional

        user_id = session_variables.get('x-hasura-user-id')

        if not all([platform, meeting_identifier, notion_note_title, notion_source, user_id]):
            missing_params = [k for k,v in {
                "platform": platform, "meeting_identifier": meeting_identifier,
                "notion_note_title": notion_note_title, "notion_source": notion_source,
                "user_id (from session)": user_id
            }.items() if not v]
            return flask.jsonify({
                "status": "Error",
                "error_message": f"Missing required parameters: {', '.join(missing_params)}"
            }), 400

        if platform.lower() != "zoom":
            return flask.jsonify({
                "status": "Error",
                "error_message": f"Platform '{platform}' is not supported for live attendance yet."
            }), 400

        # Note: Env vars for note_utils clients were set before its import attempt.
        # No need to reload note_utils again here unless specifically debugging module state per request.

        agent = ZoomAgent(user_id=user_id)

        print(f"Handler: Attempting to join meeting {meeting_identifier} for user {user_id}", file=sys.stderr)
        if agent.join_meeting(meeting_identifier):
            print(f"Handler: Successfully joined {meeting_identifier}. Starting live processing.", file=sys.stderr)

            # This call is blocking. For production, consider background tasks.
            notion_page_id_or_error = process_live_audio_for_notion(
                platform_module=agent,
                meeting_id=meeting_identifier, # Should match what agent.join_meeting used (parsed ID)
                                               # ZoomAgent's join_meeting stores the parsed ID in self.current_meeting_id
                                               # process_live_audio_for_notion will call agent.start_audio_capture(agent.current_meeting_id)
                                               # So, ensure this meeting_id is consistent or that agent uses its internal current_meeting_id
                notion_note_title=notion_note_title,
                notion_source=notion_source,
                linked_event_id=linked_event_id
            )

            print(f"Handler: Live processing completed for {meeting_identifier}. Ensuring agent leaves.", file=sys.stderr)
            agent.leave_meeting()

            # Check if notion_page_id_or_error is an error message string or a valid ID
            if isinstance(notion_page_id_or_error, str) and (notion_page_id_or_error.lower().startswith("error:") or notion_page_id_or_error.lower().startswith("failed")):
                print(f"Handler: Processing finished, but Notion page handling failed: {notion_page_id_or_error}", file=sys.stderr)
                return flask.jsonify({
                    "status": "Error",
                    "error_message": notion_page_id_or_error # Return the specific error from processing
                }), 500 # Or 200 with error status, depending on desired HTTP semantics for partial success
            elif notion_page_id_or_error: # Assuming it's a valid page ID
                 print(f"Handler: Notion page processed: {notion_page_id_or_error}", file=sys.stderr)
                 return flask.jsonify({
                    "status": "Processing complete. Notion page created/updated.", # Or more specific status from processing if available
                    "note_id": notion_page_id_or_error
                })
            else: # Should be covered by the error string check, but as a fallback
                print(f"Handler: Processing finished, but no Notion page ID returned and no specific error.", file=sys.stderr)
                return flask.jsonify({
                    "status": "Error",
                    "error_message": "Processing completed, but failed to create/update Notion page (unknown reason)."
                }), 500
        else:
            print(f"Handler: Failed to join meeting {meeting_identifier}", file=sys.stderr)
            return flask.jsonify({
                "status": "Error",
                "error_message": f"Failed to join Zoom meeting: {meeting_identifier}"
            }), 500 # Or a more specific error code if join_meeting provides one

    except Exception as e:
        print(f"Error in attend_live_meeting handler: {str(e)}", file=sys.stderr)
        # For debugging, you might want to print the full traceback:
        # import traceback
        # print(traceback.format_exc(), file=sys.stderr)
        return flask.jsonify({
            "status": "Error",
            "error_message": f"An internal error occurred: {str(e)}"
        }), 500

if __name__ == '__main__':
    # This block is for local development testing of the Flask app.
    # Ensure that when running this directly, the PYTHONPATH is set up so that
    # 'agents.zoom_agent' and 'note_utils' can be found from the 'functions' directory.
    # The sys.path manipulation at the top helps with this for direct execution.

    # The environment variables for Notion, Deepgram, OpenAI keys are critical.
    # They were set globally at the start of the script for the import-time client initializations
    # in note_utils.py. If those clients were instead initialized inside functions,
    # setting them here or just before app.run() would be another option.

    print("Starting local Flask server for attend_live_meeting handler on port 5000 (debug mode)...", file=sys.stderr)
    app.run(port=int(os.environ.get("PORT", 5000)), debug=True)
