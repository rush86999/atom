import logging
from flask import Blueprint, request, jsonify, current_app
from . import financial_service
from . import plaid_service

logger = logging.getLogger(__name__)

financial_bp = Blueprint('financial_bp', __name__)

@financial_bp.route('/api/financial/plaid/create_link_token', methods=['POST'])
async def create_link_token():
    data = request.get_json()
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    try:
        link_token = plaid_service.create_link_token(user_id)
        return jsonify({"ok": True, "data": {"link_token": link_token}})
    except Exception as e:
        logger.error(f"Error creating Plaid link token for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CREATE_LINK_TOKEN_FAILED", "message": str(e)}}), 500

@financial_bp.route('/api/financial/plaid/exchange_public_token', methods=['POST'])
async def exchange_public_token():
    data = request.get_json()
    user_id = data.get('user_id')
    public_token = data.get('public_token')
    if not all([user_id, public_token]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and public_token are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await financial_service.create_plaid_integration(user_id, public_token, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error exchanging Plaid public token for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "EXCHANGE_PUBLIC_TOKEN_FAILED", "message": str(e)}}), 500

@financial_bp.route('/api/financial/summary', methods=['GET'])
async def get_financial_summary():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await financial_service.get_financial_summary(user_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting financial summary for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "FINANCIAL_SUMMARY_FAILED", "message": str(e)}}), 500

@financial_bp.route('/api/financial/accounts', methods=['GET'])
async def get_accounts():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await financial_service.get_accounts(user_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting accounts for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_ACCOUNTS_FAILED", "message": str(e)}}), 500

@financial_bp.route('/api/financial/transactions', methods=['GET'])
async def get_transactions():
    user_id = request.args.get('user_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    if not all([user_id, start_date, end_date]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, start_date, and end_date are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await financial_service.get_transactions(user_id, start_date, end_date, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting transactions for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_TRANSACTIONS_FAILED", "message": str(e)}}), 500

@financial_bp.route('/api/financial/investments', methods=['GET'])
async def get_investments():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await financial_service.get_investments(user_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting investments for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_INVESTMENTS_FAILED", "message": str(e)}}), 500

@financial_bp.route('/api/financial/liabilities', methods=['GET'])
async def get_liabilities():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await financial_service.get_liabilities(user_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting liabilities for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_LIABILITIES_FAILED", "message": str(e)}}), 500
