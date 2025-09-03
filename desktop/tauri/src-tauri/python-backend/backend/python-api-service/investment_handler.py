import logging
from flask import Blueprint, request, jsonify, current_app
from . import investment_service

logger = logging.getLogger(__name__)

investment_bp = Blueprint('investment_bp', __name__)

@investment_bp.route('/api/investments', methods=['POST'])
async def create_investment():
    data = request.get_json()
    account_id = data.get('account_id')
    investment_name = data.get('investment_name')
    investment_type = data.get('investment_type')

    if not all([account_id, investment_name, investment_type]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "account_id, investment_name, and investment_type are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await investment_service.create_investment(account_id, investment_name, investment_type, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating investment for account {account_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "INVESTMENT_CREATE_FAILED", "message": str(e)}}), 500

@investment_bp.route('/api/investments', methods=['GET'])
async def get_investments():
    account_id = request.args.get('account_id')
    if not account_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "account_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await investment_service.get_investments(account_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting investments for account {account_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "INVESTMENTS_GET_FAILED", "message": str(e)}}), 500

@investment_bp.route('/api/holdings', methods=['POST'])
async def create_holding():
    data = request.get_json()
    investment_id = data.get('investment_id')
    ticker = data.get('ticker')
    shares = data.get('shares')
    purchase_price = data.get('purchase_price')

    if not all([investment_id, ticker, shares, purchase_price]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "investment_id, ticker, shares, and purchase_price are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await investment_service.create_holding(investment_id, ticker, shares, purchase_price, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating holding for investment {investment_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "HOLDING_CREATE_FAILED", "message": str(e)}}), 500

@investment_bp.route('/api/holdings', methods=['GET'])
async def get_holdings():
    investment_id = request.args.get('investment_id')
    if not investment_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "investment_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await investment_service.get_holdings(investment_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting holdings for investment {investment_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "HOLDINGS_GET_FAILED", "message": str(e)}}), 500
