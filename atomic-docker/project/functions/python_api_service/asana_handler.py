import logging
from flask import Blueprint, request, jsonify
from . import asana_service

logger = logging.getLogger(__name__)

asana_bp = Blueprint('asana_bp', __name__)

# A mock function to get an Asana client
# In a real application, this would involve OAuth and token management
def get_asana_client(user_id: str):
    # This is a placeholder. In a real app, you'd fetch the user's token from a database.
    # For this example, we'll use a personal access token from an environment variable.
    import os
    personal_access_token = os.getenv("ASANA_PERSONAL_ACCESS_TOKEN")
    if not personal_access_token:
        raise ValueError("ASANA_PERSONAL_ACCESS_TOKEN environment variable not set.")
    return asana_service.AsanaService(personal_access_token)

@asana_bp.route('/api/asana/search', methods=['POST'])
def search_asana_route():
    data = request.get_json()
    user_id = data.get('user_id')
    project_id = data.get('project_id')
    query = data.get('query')
    if not user_id or not query or not project_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, project_id, and query are required."}}), 400

    try:
        client = get_asana_client(user_id)
        search_results = client.list_files(project_id=project_id, query=query)
        return jsonify({"ok": True, "data": search_results})
    except Exception as e:
        logger.error(f"Error searching Asana for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "SEARCH_FILES_FAILED", "message": str(e)}}), 500

@asana_bp.route('/api/asana/list-tasks', methods=['POST'])
def list_tasks():
    data = request.get_json()
    user_id = data.get('user_id')
    project_id = data.get('project_id')
    if not user_id or not project_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and project_id are required."}}), 400

    try:
        client = get_asana_client(user_id)
        list_results = client.list_files(project_id=project_id)
        return jsonify({"ok": True, "data": list_results})
    except Exception as e:
        logger.error(f"Error listing Asana tasks for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "LIST_TASKS_FAILED", "message": str(e)}}), 500
