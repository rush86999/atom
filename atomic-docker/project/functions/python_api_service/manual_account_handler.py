import logging
from flask import Blueprint, request, jsonify, current_app
from . import manual_account_service

logger = logging.getLogger(__name__)

manual_account_bp = Blueprint('manual_account_bp', __name__)

@manual_account_bp.route('/api/financial/manual_accounts', methods=['GET'])
async def get_manual_accounts():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await manual_account_service.get_manual_accounts(user_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting manual accounts for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_MANUAL_ACCOUNTS_FAILED", "message": str(e)}}), 500

@manual_account_bp.route('/api/financial/manual_accounts', methods=['POST'])
async def create_manual_account():
    data = request.get_json()
    user_id = data.get('user_id')
    name = data.get('name')
    balance = data.get('balance')
    if not all([user_id, name, balance]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, name, and balance are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await manual_account_service.create_manual_account(user_id, name, balance, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating manual account for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CREATE_MANUAL_ACCOUNT_FAILED", "message": str(e)}}), 500
