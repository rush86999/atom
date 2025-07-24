import logging
from flask import Blueprint, request, jsonify, current_app
from . import billing_service

logger = logging.getLogger(__name__)

billing_bp = Blueprint('billing_bp', __name__)

@billing_bp.route('/api/financial/bills', methods=['GET'])
async def get_bills():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await billing_service.get_bills(user_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting bills for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_BILLS_FAILED", "message": str(e)}}), 500

@billing_bp.route('/api/financial/bills', methods=['POST'])
async def create_bill():
    data = request.get_json()
    user_id = data.get('user_id')
    amount = data.get('amount')
    if not all([user_id, amount]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and amount are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await billing_service.create_bill(user_id, amount, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating bill for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CREATE_BILL_FAILED", "message": str(e)}}), 500
