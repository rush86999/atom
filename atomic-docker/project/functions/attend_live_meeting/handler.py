import flask
import os
import sys
import importlib
import traceback
import asyncio

# Add parent 'functions' directory to sys.path for sibling imports
PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
FUNCTIONS_DIR_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT))
if FUNCTIONS_DIR_PATH not in sys.path:
    sys.path.append(FUNCTIONS_DIR_PATH)

# --- Module Imports & Initializations ---
ZoomAgent = None
GoogleMeetAgent = None
MSTeamsAgent = None # Added MSTeamsAgent
note_utils_module = None

try:
    from agents.zoom_agent import ZoomAgent as ImportedZoomAgent
    ZoomAgent = ImportedZoomAgent
except ImportError as e:
    print(f"Warning: ZoomAgent failed to import: {e}", file=sys.stderr)

try:
    from agents.google_meet_agent import GoogleMeetAgent as ImportedGoogleMeetAgent
    GoogleMeetAgent = ImportedGoogleMeetAgent
except ImportError as e:
    print(f"Warning: GoogleMeetAgent failed to import: {e}", file=sys.stderr)

try:
    from agents.ms_teams_agent import MSTeamsAgent as ImportedMSTeamsAgent # Import MSTeamsAgent
    MSTeamsAgent = ImportedMSTeamsAgent
except ImportError as e:
    print(f"Warning: MSTeamsAgent failed to import: {e}", file=sys.stderr)

try:
    import note_utils as nu_module
    note_utils_module = nu_module
    if not hasattr(note_utils_module, 'process_live_audio_for_notion'):
        print("Error: process_live_audio_for_notion not found in note_utils module.", file=sys.stderr)
        note_utils_module = None
except ImportError as e:
    print(f"Critical Import Error for note_utils in attend_live_meeting handler: {e}", file=sys.stderr)


app = flask.Flask(__name__)

def make_error_response(code: str, message: str, details: any = None, http_status: int = 500):
    return flask.jsonify({
        "ok": False,
        "error": {"code": code, "message": message, "details": details}
    }), http_status

@app.route('/', methods=['POST'])
async def attend_live_meeting_route():
    payload = {}
    agent = None
    try:
        payload = flask.request.get_json()
        if not payload:
            return make_error_response("INVALID_PAYLOAD", "Request must be JSON.", http_status=400)

        action_input = payload.get('action_input', {})
        session_variables = payload.get('session_variables', {})
        handler_input = payload.get('handler_input', {})

        platform = action_input.get('platform', '').lower()
        meeting_identifier = action_input.get('meeting_identifier')
        notion_note_title = action_input.get('notion_note_title')

        notion_source = action_input.get('notion_source', 'Live Meeting Transcription')
        linked_event_id = action_input.get('linked_event_id')
        notion_db_id = action_input.get('notion_db_id')

        user_id = session_variables.get('x-hasura-user-id')

        notion_api_token = handler_input.get('notion_api_token')
        deepgram_api_key = handler_input.get('deepgram_api_key')
        openai_api_key = handler_input.get('openai_api_key')

        required_params_map = {
            "platform": platform, "meeting_identifier": meeting_identifier,
            "notion_note_title": notion_note_title, "user_id": user_id,
            "notion_api_token": notion_api_token, "deepgram_api_key": deepgram_api_key,
            "openai_api_key": openai_api_key,
        }
        missing_params = [k for k, v in required_params_map.items() if not v]
        if missing_params:
            return make_error_response("VALIDATION_ERROR", f"Missing required parameters: {', '.join(missing_params)}", http_status=400)

        if not note_utils_module:
             return make_error_response("SERVICE_UNAVAILABLE", "Core note processing utilities are not loaded.", http_status=503)

        init_notion_resp = note_utils_module.init_notion(notion_api_token, database_id=notion_db_id)
        if init_notion_resp["status"] != "success":
            return make_error_response(
                f"NOTION_INIT_ERROR_{init_notion_resp.get('code', 'UNKNOWN')}",
                init_notion_resp.get('message', "Failed to initialize Notion client."),
                init_notion_resp.get('details')
            )

        platform_interface = None

        if platform == "zoom":
            if ZoomAgent is None:
                return make_error_response("SERVICE_UNAVAILABLE", "ZoomAgent component not loaded for 'zoom' platform.", http_status=503)
            agent = ZoomAgent(user_id=user_id)
            platform_interface = agent
        elif platform == "googlemeet" or platform == "google_meet":
            if GoogleMeetAgent is None:
                return make_error_response("SERVICE_UNAVAILABLE", "GoogleMeetAgent component not loaded for 'googlemeet' platform.", http_status=503)
            agent = GoogleMeetAgent(user_id=user_id)
            platform_interface = agent
        elif platform in ["msteams", "microsoft_teams", "teams"]: # Added MSTeams
            if MSTeamsAgent is None:
                return make_error_response("SERVICE_UNAVAILABLE", "MSTeamsAgent component not loaded for 'msteams' platform.", http_status=503)
            agent = MSTeamsAgent(user_id=user_id)
            platform_interface = agent
        else:
            return make_error_response("NOT_IMPLEMENTED", f"Platform '{platform}' is not supported. Supported platforms: zoom, googlemeet, msteams.", http_status=400)

        print(f"Handler: Attempting to join meeting {meeting_identifier} via {platform} for user {user_id}", file=sys.stderr)
        join_success = platform_interface.join_meeting(meeting_identifier)

        if not join_success:
            return make_error_response("JOIN_MEETING_FAILED", f"Agent failed to launch/join meeting: {meeting_identifier} on platform {platform}.", http_status=500)

        print(f"Handler: Successfully joined {meeting_identifier}. Starting live processing.", file=sys.stderr)

        process_live_audio_func = getattr(note_utils_module, 'process_live_audio_for_notion')
        if not process_live_audio_func:
             return make_error_response("SERVICE_UNAVAILABLE", "Live audio processing function not available in note_utils.", http_status=503)

        current_meeting_id = platform_interface.get_current_meeting_id() or meeting_identifier

        processing_result = await process_live_audio_func(
            platform_module=platform_interface,
            meeting_id=current_meeting_id,
            notion_note_title=notion_note_title,
            deepgram_api_key=deepgram_api_key,
            openai_api_key=openai_api_key,
            notion_db_id=notion_db_id,
            notion_source=notion_source,
            linked_event_id=linked_event_id
        )

        if processing_result and processing_result.get("status") == "success":
            print(f"Handler: Notion page processed: {processing_result.get('data')}", file=sys.stderr)
            return flask.jsonify({"ok": True, "data": processing_result.get("data")}), 200
        else:
            err_msg = processing_result.get("message", "Processing failed") if processing_result else "Processing function returned None."
            err_code = processing_result.get("code", "PROCESSING_FAILED") if processing_result else "PROCESSING_RETURNED_NONE"
            err_details = processing_result.get("details") if processing_result else None
            print(f"Handler: Processing finished with error for {current_meeting_id}: {err_msg}", file=sys.stderr)
            return make_error_response(f"PYTHON_ERROR_{err_code}", err_msg, err_details, http_status=500)

    except Exception as e:
        print(f"Critical error in attend_live_meeting_route: {str(e)}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return make_error_response("INTERNAL_SERVER_ERROR", f"An internal error occurred: {str(e)}", http_status=500)
    finally:
        if agent and hasattr(agent, 'current_meeting_id') and agent.current_meeting_id :
            # Check if agent was instantiated and successfully joined (current_meeting_id would be set)
            meeting_id_for_leave = agent.get_current_meeting_id() # Use the method now
            print(f"Handler: Live processing ended for {meeting_id_for_leave}. Ensuring agent leaves.", file=sys.stderr)
            if hasattr(agent, 'leave_meeting') and asyncio.iscoroutinefunction(agent.leave_meeting):
                await agent.leave_meeting()
            elif hasattr(agent, 'leave_meeting'): # Fallback for potential non-async leave_meeting
                agent.leave_meeting()


if __name__ == '__main__':
    print("Starting local Flask server for attend_live_meeting (async) handler on port 5000...", file=sys.stderr)
    app.run(port=int(os.environ.get("FLASK_PORT", 5000)), debug=True)

[end of atomic-docker/project/functions/attend_live_meeting/handler.py]
