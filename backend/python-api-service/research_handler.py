import sys
import os
from flask import Flask, request, jsonify

# Adjust sys.path to allow imports from parent directories
# Assuming python_api_service is one level under 'functions'
# and 'atom-agent' and 'note_utils.py' are also under 'functions'
FUNCTIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ATOM_AGENT_DIR = os.path.join(FUNCTIONS_DIR, 'atom-agent')
if FUNCTIONS_DIR not in sys.path:
    sys.path.append(FUNCTIONS_DIR)
if ATOM_AGENT_DIR not in sys.path: # research_agent is inside atom-agent
    sys.path.append(ATOM_AGENT_DIR)

try:
    from atom_agent import research_agent
    import note_utils # Should be found if FUNCTIONS_DIR is in sys.path
except ImportError as e:
    # This provides a more informative startup error if paths are wrong
    print(f"Error importing research modules: {e}", file=sys.stderr)
    print(f"sys.path: {sys.path}", file=sys.stderr)
    # To prevent Flask from starting with broken imports, re-raise or exit
    raise


app = Flask(__name__)

# Centralized error handler for consistent JSON responses
@app.errorhandler(Exception)
def handle_exception(e):
    """Return JSON instead of HTML for any other server error."""
    print(f"Unhandled exception: {e}", file=sys.stderr) # Log the full error
    response = {
        "ok": False,
        "error": {
            "code": "PYTHON_UNHANDLED_ERROR",
            "message": "An unexpected error occurred on the server.",
            "details": str(e) # Add some detail for debugging, but be cautious in prod
        }
    }
    return jsonify(response), 500

@app.route('/initiate-research', methods=['POST'])
def initiate_research():
    """
    Initiates a new research project.
    Expects: topic, user_id, research_db_id, task_db_id,
             notion_api_token, openai_api_key.
    """
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

    required_params = ['topic', 'user_id', 'research_db_id', 'task_db_id',
                       'notion_api_token', 'openai_api_key']
    missing_params = [param for param in required_params if param not in data]
    if missing_params:
        return jsonify({"ok": False, "error": {"code": "MISSING_PARAMETERS", "message": f"Missing parameters: {', '.join(missing_params)}"}}), 400

    topic = data['topic']
    user_id = data['user_id']
    research_db_id = data['research_db_id']
    task_db_id = data['task_db_id']
    notion_api_token = data['notion_api_token']
    openai_api_key = data['openai_api_key']

    try:
        # Initialize Notion client for this request
        init_status = note_utils.init_notion(notion_api_token)
        if init_status["status"] != "success":
            return jsonify({"ok": False, "error": {"code": "NOTION_INIT_FAILED", "message": init_status["message"]}}), 500

        result = research_agent.initiate_research_project(
            user_query=topic,
            user_id=user_id,
            project_db_id=research_db_id,
            task_db_id=task_db_id,
            openai_api_key=openai_api_key
            # notion_api_token is used by init_notion, not directly by initiate_research_project
        )

        if result["status"] == "success":
            return jsonify({"ok": True, "data": result.get("data")}), 200
        else:
            # Prepend "PYTHON_ERROR_" to codes from the agent for clarity
            error_code = f"PYTHON_ERROR_{result.get('code', 'RESEARCH_AGENT_ERROR')}"
            return jsonify({"ok": False, "error": {"code": error_code, "message": result.get("message"), "details": result.get("details")}}), 500
    except Exception as e:
        print(f"Exception in /initiate-research: {e}", file=sys.stderr)
        # This will be caught by the generic app.errorhandler
        raise

@app.route('/process-research-queue', methods=['POST'])
def process_research_queue():
    """
    Monitors and executes pending research tasks, and triggers synthesis.
    Expects: research_db_id, task_db_id, notion_api_token,
             openai_api_key, search_api_key.
    (user_id is not strictly needed by monitor_and_execute_tasks itself but good for context/logging if added)
    """
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

    required_params = ['research_db_id', 'task_db_id', 'notion_api_token',
                       'openai_api_key', 'search_api_key']
    missing_params = [param for param in required_params if param not in data]
    if missing_params:
        return jsonify({"ok": False, "error": {"code": "MISSING_PARAMETERS", "message": f"Missing parameters: {', '.join(missing_params)}"}}), 400

    research_db_id = data['research_db_id']
    task_db_id = data['task_db_id']
    notion_api_token = data['notion_api_token']
    openai_api_key = data['openai_api_key']
    search_api_key = data['search_api_key'] # ATOM_SERPAPI_API_KEY

    try:
        # Initialize Notion client for this request
        init_status = note_utils.init_notion(notion_api_token)
        if init_status["status"] != "success":
            return jsonify({"ok": False, "error": {"code": "NOTION_INIT_FAILED", "message": init_status["message"]}}), 500

        # Call the refactored monitor_and_execute_tasks
        # Note: The refactored research_agent.monitor_and_execute_tasks no longer takes notion_api_token directly
        # because note_utils.notion is assumed to be initialized by the handler.
        result = research_agent.monitor_and_execute_tasks(
            task_db_id=task_db_id,
            project_db_id=research_db_id,
            search_api_key=search_api_key,
            openai_api_key=openai_api_key
        )

        if result["status"] == "success":
            return jsonify({"ok": True, "data": result.get("data")}), 200
        else:
            error_code = f"PYTHON_ERROR_{result.get('code', 'RESEARCH_PROCESS_ERROR')}"
            return jsonify({"ok": False, "error": {"code": error_code, "message": result.get("message"), "details": result.get("details")}}), 500
    except Exception as e:
        print(f"Exception in /process-research-queue: {e}", file=sys.stderr)
        # This will be caught by the generic app.errorhandler
        raise

if __name__ == '__main__':
    # For local testing. In a deployed environment (e.g., Docker container for a Lambda),
    # a proper WSGI server like Gunicorn would be used, and this __main__ block might not be run.
    # The Flask 'app' object would be imported by the WSGI server.
    flask_port = int(os.environ.get("RESEARCH_HANDLER_PORT", 5056))
    app.run(host='0.0.0.0', port=flask_port, debug=True)

[end of atomic-docker/project/functions/python_api_service/research_handler.py]
