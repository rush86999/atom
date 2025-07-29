import logging
from flask import Blueprint, request, jsonify, current_app
from . import box_service

logger = logging.getLogger(__name__)

box_bp = Blueprint('box_bp', __name__)

# A mock function to get a Box client
# In a real application, this would involve OAuth and token management
def get_box_client(user_id: str):
    # This is a placeholder. In a real app, you'd fetch the user's token from a database.
    # For this example, we'll use a developer token from an environment variable.
    import os
    developer_token = os.getenv("BOX_DEVELOPER_TOKEN")
    if not developer_token:
        raise ValueError("BOX_DEVELOPER_TOKEN environment variable not set.")
    return box_service.BoxService(developer_token)

@box_bp.route('/api/box/search', methods=['POST'])
def search_box_route():
    data = request.get_json()
    user_id = data.get('user_id')
    query = data.get('query')
    if not user_id or not query:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and query are required."}}), 400

    try:
        client = get_box_client(user_id)
        search_results = client.list_files(query=query)
        return jsonify({"ok": True, "data": search_results})
    except Exception as e:
        logger.error(f"Error searching Box files for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "SEARCH_FILES_FAILED", "message": str(e)}}), 500

@box_bp.route('/api/box/list-files', methods=['POST'])
def list_files():
    data = request.get_json()
    user_id = data.get('user_id')
    folder_id = data.get('folder_id', '0')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    try:
        client = get_box_client(user_id)
        list_results = client.list_files(folder_id=folder_id)
        return jsonify({"ok": True, "data": list_results})
    except Exception as e:
        logger.error(f"Error listing Box files for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "LIST_FILES_FAILED", "message": str(e)}}), 500
