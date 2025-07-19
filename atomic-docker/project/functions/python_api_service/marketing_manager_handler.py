import logging
from flask import Blueprint, request, jsonify, current_app
from . import marketing_manager_service

logger = logging.getLogger(__name__)

marketing_manager_bp = Blueprint('marketing_manager_bp', __name__)

@marketing_manager_bp.route('/api/marketing/create-mailchimp-campaign-from-salesforce-campaign', methods=['POST'])
async def create_mailchimp_campaign_from_salesforce_campaign():
    data = request.get_json()
    user_id = data.get('user_id')
    salesforce_campaign_id = data.get('salesforce_campaign_id')
    if not all([user_id, salesforce_campaign_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and salesforce_campaign_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await marketing_manager_service.create_mailchimp_campaign_from_salesforce_campaign(user_id, salesforce_campaign_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Mailchimp campaign from Salesforce campaign for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CAMPAIGN_CREATE_FAILED", "message": str(e)}}), 500

@marketing_manager_bp.route('/api/marketing/mailchimp-campaign-summary/<campaign_id>', methods=['GET'])
async def get_mailchimp_campaign_summary(campaign_id):
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await marketing_manager_service.get_mailchimp_campaign_summary(user_id, campaign_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting Mailchimp campaign summary for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "SUMMARY_FETCH_FAILED", "message": str(e)}}), 500

@marketing_manager_bp.route('/api/marketing/create-trello-card-from-mailchimp-campaign', methods=['POST'])
async def create_trello_card_from_mailchimp_campaign():
    data = request.get_json()
    user_id = data.get('user_id')
    campaign_id = data.get('campaign_id')
    trello_list_id = data.get('trello_list_id')
    if not all([user_id, campaign_id, trello_list_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, campaign_id, and trello_list_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await marketing_manager_service.create_trello_card_from_mailchimp_campaign(user_id, campaign_id, trello_list_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Trello card from Mailchimp campaign for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CARD_CREATE_FAILED", "message": str(e)}}), 500
