import logging
from flask import Blueprint, request, jsonify, current_app
from . import account_service

logger = logging.getLogger(__name__)

account_bp = Blueprint('account_bp', __name__)

@account_bp.route('/api/accounts', methods=['POST'])
async def create_account():
    data = request.get_json()
    user_id = data.get('user_id')
    account_name = data.get('account_name')
    account_type = data.get('account_type')
    balance = data.get('balance')

    if not all([user_id, account_name, account_type, balance]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, account_name, account_type, and balance are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await account_service.create_account(user_id, account_name, account_type, balance, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating account for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "ACCOUNT_CREATE_FAILED", "message": str(e)}}), 500

@account_bp.route('/api/accounts', methods=['GET'])
async def get_accounts():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await account_service.get_accounts(user_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting accounts for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "ACCOUNTS_GET_FAILED", "message": str(e)}}), 500
