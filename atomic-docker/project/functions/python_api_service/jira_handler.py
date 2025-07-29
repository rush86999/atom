import logging
from flask import Blueprint, request, jsonify
from . import jira_service

logger = logging.getLogger(__name__)

jira_bp = Blueprint('jira_bp', __name__)

# A mock function to get a Jira client
# In a real application, this would involve OAuth and token management
def get_jira_client(user_id: str):
    # This is a placeholder. In a real app, you'd fetch the user's token from a database.
    # For this example, we'll use credentials from environment variables.
    import os
    server_url = os.getenv("JIRA_SERVER_URL")
    username = os.getenv("JIRA_USERNAME")
    api_token = os.getenv("JIRA_API_TOKEN")
    if not all([server_url, username, api_token]):
        raise ValueError("Jira credentials not set in environment variables.")
    return jira_service.JiraService(server_url, username, api_token)

@jira_bp.route('/api/jira/search', methods=['POST'])
def search_jira_route():
    data = request.get_json()
    user_id = data.get('user_id')
    project_id = data.get('project_id')
    query = data.get('query')
    if not user_id or not query or not project_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, project_id, and query are required."}}), 400

    try:
        client = get_jira_client(user_id)
        search_results = client.list_files(project_id=project_id, query=query)
        return jsonify({"ok": True, "data": search_results})
    except Exception as e:
        logger.error(f"Error searching Jira for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "SEARCH_ISSUES_FAILED", "message": str(e)}}), 500

@jira_bp.route('/api/jira/list-issues', methods=['POST'])
def list_issues():
    data = request.get_json()
    user_id = data.get('user_id')
    project_id = data.get('project_id')
    if not user_id or not project_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and project_id are required."}}), 400

    try:
        client = get_jira_client(user_id)
        list_results = client.list_files(project_id=project_id)
        return jsonify({"ok": True, "data": list_results})
    except Exception as e:
        logger.error(f"Error listing Jira issues for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "LIST_ISSUES_FAILED", "message": str(e)}}), 500
