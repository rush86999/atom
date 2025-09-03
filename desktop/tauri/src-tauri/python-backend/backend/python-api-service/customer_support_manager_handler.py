import logging
from flask import Blueprint, request, jsonify, current_app
from . import customer_support_manager_service

logger = logging.getLogger(__name__)

customer_support_manager_bp = Blueprint('customer_support_manager_bp', __name__)

@customer_support_manager_bp.route('/api/customer-support/create-zendesk-ticket-from-salesforce-case', methods=['POST'])
async def create_zendesk_ticket_from_salesforce_case():
    data = request.get_json()
    user_id = data.get('user_id')
    salesforce_case_id = data.get('salesforce_case_id')
    if not all([user_id, salesforce_case_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and salesforce_case_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await customer_support_manager_service.create_zendesk_ticket_from_salesforce_case(user_id, salesforce_case_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Zendesk ticket from Salesforce case for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "TICKET_CREATE_FAILED", "message": str(e)}}), 500

@customer_support_manager_bp.route('/api/customer-support/zendesk-ticket-summary/<ticket_id>', methods=['GET'])
async def get_zendesk_ticket_summary(ticket_id):
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await customer_support_manager_service.get_zendesk_ticket_summary(user_id, ticket_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting Zendesk ticket summary for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "SUMMARY_FETCH_FAILED", "message": str(e)}}), 500

@customer_support_manager_bp.route('/api/customer-support/create-trello-card-from-zendesk-ticket', methods=['POST'])
async def create_trello_card_from_zendesk_ticket():
    data = request.get_json()
    user_id = data.get('user_id')
    ticket_id = data.get('ticket_id')
    trello_list_id = data.get('trello_list_id')
    if not all([user_id, ticket_id, trello_list_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, ticket_id, and trello_list_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await customer_support_manager_service.create_trello_card_from_zendesk_ticket(user_id, ticket_id, trello_list_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Trello card from Zendesk ticket for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CARD_CREATE_FAILED", "message": str(e)}}), 500
