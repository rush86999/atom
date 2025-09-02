import logging
from flask import Blueprint, request, jsonify, current_app
from . import financial_analyst_service

logger = logging.getLogger(__name__)

financial_analyst_bp = Blueprint('financial_analyst_bp', __name__)

@financial_analyst_bp.route('/api/financial/summary', methods=['GET'])
async def get_financial_summary():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await financial_analyst_service.get_financial_summary(user_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting financial summary for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "FINANCIAL_SUMMARY_FAILED", "message": str(e)}}), 500

@financial_analyst_bp.route('/api/financial/create-opportunity-from-invoice', methods=['POST'])
async def create_opportunity_from_invoice():
    data = request.get_json()
    user_id = data.get('user_id')
    invoice_id = data.get('invoice_id')
    if not all([user_id, invoice_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and invoice_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await financial_analyst_service.create_salesforce_opportunity_from_xero_invoice(user_id, invoice_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Salesforce opportunity from Xero invoice for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "OPPORTUNITY_CREATE_FAILED", "message": str(e)}}), 500

@financial_analyst_bp.route('/api/financial/create-card-from-invoice', methods=['POST'])
async def create_card_from_invoice():
    data = request.get_json()
    user_id = data.get('user_id')
    invoice_id = data.get('invoice_id')
    trello_list_id = data.get('trello_list_id')
    if not all([user_id, invoice_id, trello_list_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, invoice_id, and trello_list_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await financial_analyst_service.create_trello_card_from_xero_invoice(user_id, invoice_id, trello_list_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Trello card from Xero invoice for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CARD_CREATE_FAILED", "message": str(e)}}), 500
