import logging
from flask import Blueprint, request, jsonify, current_app
from . import payroll_service

logger = logging.getLogger(__name__)

payroll_bp = Blueprint('payroll_bp', __name__)

@payroll_bp.route('/api/financial/payrolls', methods=['GET'])
async def get_payrolls():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await payroll_service.get_payrolls(user_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting payrolls for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_PAYROLLS_FAILED", "message": str(e)}}), 500

@payroll_bp.route('/api/financial/payrolls', methods=['POST'])
async def create_payroll():
    data = request.get_json()
    user_id = data.get('user_id')
    amount = data.get('amount')
    if not all([user_id, amount]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and amount are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await payroll_service.create_payroll(user_id, amount, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating payroll for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CREATE_PAYROLL_FAILED", "message": str(e)}}), 500
