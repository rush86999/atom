import logging
from flask import Blueprint, request, jsonify, current_app
from . import manual_transaction_service

logger = logging.getLogger(__name__)

manual_transaction_bp = Blueprint('manual_transaction_bp', __name__)

@manual_transaction_bp.route('/api/financial/manual_transactions', methods=['GET'])
async def get_manual_transactions():
    user_id = request.args.get('user_id')
    account_id = request.args.get('account_id')
    if not all([user_id, account_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and account_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await manual_transaction_service.get_manual_transactions(user_id, account_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting manual transactions for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_MANUAL_TRANSACTIONS_FAILED", "message": str(e)}}), 500

@manual_transaction_bp.route('/api/financial/manual_transactions', methods=['POST'])
async def create_manual_transaction():
    data = request.get_json()
    user_id = data.get('user_id')
    account_id = data.get('account_id')
    description = data.get('description')
    amount = data.get('amount')
    if not all([user_id, account_id, description, amount]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, account_id, description, and amount are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await manual_transaction_service.create_manual_transaction(user_id, account_id, description, amount, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating manual transaction for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CREATE_MANUAL_TRANSACTION_FAILED", "message": str(e)}}), 500
