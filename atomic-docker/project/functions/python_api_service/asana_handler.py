import logging
from flask import Blueprint, request, jsonify
from . import asana_service

logger = logging.getLogger(__name__)

asana_bp = Blueprint('asana_bp', __name__)

import asana
from . import db_oauth_asana, crypto_utils

async def get_asana_client(user_id: str, db_conn_pool):
    tokens = await db_oauth_asana.get_tokens(db_conn_pool, user_id)
    if not tokens:
        return None

    access_token = crypto_utils.decrypt_message(tokens[0])

    client = asana.Client.access_token(access_token)
    return asana_service.AsanaService(client)

@asana_bp.route('/api/asana/search', methods=['POST'])
async def search_asana_route():
    data = request.get_json()
    user_id = data.get('user_id')
    project_id = data.get('project_id')
    query = data.get('query')
    if not user_id or not query or not project_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, project_id, and query are required."}}), 400

    try:
        client = await get_asana_client(user_id, current_app.config['DB_CONNECTION_POOL'])
        if not client:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "User not authenticated with Asana."}}), 401
        search_results = client.list_files(project_id=project_id, query=query)
        return jsonify({"ok": True, "data": search_results})
    except Exception as e:
        logger.error(f"Error searching Asana for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "SEARCH_FILES_FAILED", "message": str(e)}}), 500

@asana_bp.route('/api/asana/list-tasks', methods=['POST'])
async def list_tasks():
    data = request.get_json()
    user_id = data.get('user_id')
    project_id = data.get('project_id')
    if not user_id or not project_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and project_id are required."}}), 400

    try:
        client = await get_asana_client(user_id, current_app.config['DB_CONNECTION_POOL'])
        if not client:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "User not authenticated with Asana."}}), 401
        list_results = client.list_files(project_id=project_id)
        return jsonify({"ok": True, "data": list_results})
    except Exception as e:
        logger.error(f"Error listing Asana tasks for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "LIST_TASKS_FAILED", "message": str(e)}}), 500
