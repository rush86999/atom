import logging
from flask import Blueprint, request, jsonify, current_app
from . import project_manager_service

logger = logging.getLogger(__name__)

project_manager_bp = Blueprint('project_manager_bp', __name__)

@project_manager_bp.route('/api/project/create-gdrive-folder-from-trello-board', methods=['POST'])
async def create_gdrive_folder_from_trello_board():
    data = request.get_json()
    user_id = data.get('user_id')
    board_id = data.get('board_id')
    if not all([user_id, board_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and board_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await project_manager_service.create_google_drive_folder_from_trello_board(user_id, board_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Google Drive folder from Trello board for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "FOLDER_CREATE_FAILED", "message": str(e)}}), 500

@project_manager_bp.route('/api/project/upload-trello-attachments-to-gdrive', methods=['POST'])
async def upload_trello_attachments_to_gdrive():
    data = request.get_json()
    user_id = data.get('user_id')
    card_id = data.get('card_id')
    folder_id = data.get('folder_id')
    if not all([user_id, card_id, folder_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, card_id, and folder_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await project_manager_service.upload_trello_attachments_to_google_drive(user_id, card_id, folder_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error uploading Trello attachments to Google Drive for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "UPLOAD_FAILED", "message": str(e)}}), 500
