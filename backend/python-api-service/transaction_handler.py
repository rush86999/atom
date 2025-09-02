import logging
from flask import Blueprint, request, jsonify, current_app
from . import transaction_service

logger = logging.getLogger(__name__)

transaction_bp = Blueprint('transaction_bp', __name__)

@transaction_bp.route('/api/transactions', methods=['POST'])
async def create_transaction():
    data = request.get_json()
    account_id = data.get('account_id')
    amount = data.get('amount')
    description = data.get('description')
    date = data.get('date')
    category = data.get('category')

    if not all([account_id, amount, description, date, category]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "account_id, amount, description, date, and category are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await transaction_service.create_transaction(account_id, amount, description, date, category, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating transaction for account {account_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "TRANSACTION_CREATE_FAILED", "message": str(e)}}), 500

@transaction_bp.route('/api/transactions', methods=['GET'])
async def get_transactions():
    account_id = request.args.get('account_id')
    if not account_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "account_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await transaction_service.get_transactions(account_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting transactions for account {account_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "TRANSACTIONS_GET_FAILED", "message": str(e)}}), 500
