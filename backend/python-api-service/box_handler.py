import logging
from flask import Blueprint, request, jsonify, current_app
from . import box_service

logger = logging.getLogger(__name__)

box_bp = Blueprint('box_bp', __name__)

from boxsdk import OAuth2
from . import db_oauth_box, crypto_utils

async def get_box_client(user_id: str, db_conn_pool):
    tokens = await db_oauth_box.get_tokens(db_conn_pool, user_id)
    if not tokens:
        return None

    access_token = crypto_utils.decrypt_message(tokens[0])
    refresh_token = crypto_utils.decrypt_message(tokens[1]) if tokens[1] else None

    oauth = OAuth2(
        client_id=os.getenv("BOX_CLIENT_ID"),
        client_secret=os.getenv("BOX_CLIENT_SECRET"),
        access_token=access_token,
        refresh_token=refresh_token,
    )
    return box_service.BoxService(oauth)

@box_bp.route('/api/box/search', methods=['POST'])
async def search_box_route():
    data = request.get_json()
    user_id = data.get('user_id')
    query = data.get('query')
    if not user_id or not query:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and query are required."}}), 400

    try:
        client = await get_box_client(user_id, current_app.config['DB_CONNECTION_POOL'])
        if not client:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "User not authenticated with Box."}}), 401
        search_results = client.list_files(query=query)
        return jsonify({"ok": True, "data": search_results})
    except Exception as e:
        logger.error(f"Error searching Box files for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "SEARCH_FILES_FAILED", "message": str(e)}}), 500

@box_bp.route('/api/box/list-files', methods=['POST'])
async def list_files():
    data = request.get_json()
    user_id = data.get('user_id')
    folder_id = data.get('folder_id', '0')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    try:
        client = await get_box_client(user_id, current_app.config['DB_CONNECTION_POOL'])
        if not client:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "User not authenticated with Box."}}), 401
        list_results = client.list_files(folder_id=folder_id)
        return jsonify({"ok": True, "data": list_results})
    except Exception as e:
        logger.error(f"Error listing Box files for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "LIST_FILES_FAILED", "message": str(e)}}), 500
