import logging
from flask import Blueprint, request, jsonify, current_app
from . import sales_manager_service

logger = logging.getLogger(__name__)

sales_manager_bp = Blueprint('sales_manager_bp', __name__)

@sales_manager_bp.route('/api/sales/create-invoice-from-opportunity', methods=['POST'])
async def create_invoice_from_opportunity():
    data = request.get_json()
    user_id = data.get('user_id')
    opportunity_id = data.get('opportunity_id')
    if not all([user_id, opportunity_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and opportunity_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await sales_manager_service.create_xero_invoice_from_salesforce_opportunity(user_id, opportunity_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Xero invoice from Salesforce opportunity for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "INVOICE_CREATE_FAILED", "message": str(e)}}), 500

@sales_manager_bp.route('/api/sales/create-card-from-opportunity', methods=['POST'])
async def create_card_from_opportunity():
    data = request.get_json()
    user_id = data.get('user_id')
    opportunity_id = data.get('opportunity_id')
    trello_list_id = data.get('trello_list_id')
    if not all([user_id, opportunity_id, trello_list_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, opportunity_id, and trello_list_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await sales_manager_service.create_trello_card_from_salesforce_opportunity(user_id, opportunity_id, trello_list_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Trello card from Salesforce opportunity for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CARD_CREATE_FAILED", "message": str(e)}}), 500

@sales_manager_bp.route('/api/sales/create-salesforce-contact-from-xero-contact', methods=['POST'])
async def create_salesforce_contact_from_xero_contact():
    data = request.get_json()
    user_id = data.get('user_id')
    xero_contact_id = data.get('xero_contact_id')
    if not all([user_id, xero_contact_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and xero_contact_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await sales_manager_service.create_salesforce_contact_from_xero_contact(user_id, xero_contact_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Salesforce contact from Xero contact for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CONTACT_CREATE_FAILED", "message": str(e)}}), 500

@sales_manager_bp.route('/api/sales/open-opportunities-for-account/<account_id>', methods=['GET'])
async def get_open_opportunities_for_account(account_id):
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await sales_manager_service.get_open_opportunities_for_account(user_id, account_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting open opportunities for account {account_id} for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "OPPORTUNITIES_FETCH_FAILED", "message": str(e)}}), 500
