import logging
from flask import Blueprint, request, jsonify, current_app
from . import budgeting_service

logger = logging.getLogger(__name__)

budgeting_bp = Blueprint('budgeting_bp', __name__)

@budgeting_bp.route('/api/financial/budgets', methods=['GET'])
async def get_budgets():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await budgeting_service.get_budgets(user_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting budgets for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_BUDGETS_FAILED", "message": str(e)}}), 500

@budgeting_bp.route('/api/financial/budgets', methods=['POST'])
async def create_budget():
    data = request.get_json()
    user_id = data.get('user_id')
    category = data.get('category')
    amount = data.get('amount')
    if not all([user_id, category, amount]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, category, and amount are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await budgeting_service.create_budget(user_id, category, amount, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating budget for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CREATE_BUDGET_FAILED", "message": str(e)}}), 500
