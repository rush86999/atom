import logging
from flask import Blueprint, request, jsonify, current_app
from . import content_marketer_service

logger = logging.getLogger(__name__)

content_marketer_bp = Blueprint('content_marketer_bp', __name__)

@content_marketer_bp.route('/api/content/create-wordpress-post-from-google-drive-document', methods=['POST'])
async def create_wordpress_post_from_google_drive_document():
    data = request.get_json()
    user_id = data.get('user_id')
    google_drive_document_id = data.get('google_drive_document_id')
    if not all([user_id, google_drive_document_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and google_drive_document_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await content_marketer_service.create_wordpress_post_from_google_drive_document(user_id, google_drive_document_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating WordPress post from Google Drive document for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "POST_CREATE_FAILED", "message": str(e)}}), 500

@content_marketer_bp.route('/api/content/wordpress-post-summary/<post_id>', methods=['GET'])
async def get_wordpress_post_summary(post_id):
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await content_marketer_service.get_wordpress_post_summary(user_id, post_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting WordPress post summary for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "SUMMARY_FETCH_FAILED", "message": str(e)}}), 500

@content_marketer_bp.route('/api/content/create-trello-card-from-wordpress-post', methods=['POST'])
async def create_trello_card_from_wordpress_post():
    data = request.get_json()
    user_id = data.get('user_id')
    post_id = data.get('post_id')
    trello_list_id = data.get('trello_list_id')
    if not all([user_id, post_id, trello_list_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, post_id, and trello_list_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await content_marketer_service.create_trello_card_from_wordpress_post(user_id, post_id, trello_list_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Trello card from WordPress post for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CARD_CREATE_FAILED", "message": str(e)}}), 500
