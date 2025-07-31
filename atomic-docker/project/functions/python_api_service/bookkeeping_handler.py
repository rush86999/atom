import logging
from flask import Blueprint, request, jsonify, current_app
from . import bookkeeping_service

logger = logging.getLogger(__name__)

bookkeeping_bp = Blueprint('bookkeeping_bp', __name__)

@bookkeeping_bp.route('/api/financial/bookkeeping', methods=['GET'])
async def get_bookkeeping_data():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await bookkeeping_service.get_bookkeeping_data(user_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting bookkeeping data for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_BOOKKEEPING_DATA_FAILED", "message": str(e)}}), 500

@bookkeeping_bp.route('/api/financial/bookkeeping', methods=['POST'])
async def create_bookkeeping_entry():
    data = request.get_json()
    user_id = data.get('user_id')
    entry_data = data.get('entry_data')
    if not all([user_id, entry_data]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and entry_data are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await bookkeeping_service.create_bookkeeping_entry(user_id, entry_data, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating bookkeeping entry for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CREATE_BOOKKEEPING_ENTRY_FAILED", "message": str(e)}}), 500
