import logging
from flask import Blueprint, request, jsonify, current_app
from . import it_manager_service

logger = logging.getLogger(__name__)

it_manager_bp = Blueprint('it_manager_bp', __name__)

@it_manager_bp.route('/api/it/create-jira-issue-from-salesforce-case', methods=['POST'])
async def create_jira_issue_from_salesforce_case():
    data = request.get_json()
    user_id = data.get('user_id')
    salesforce_case_id = data.get('salesforce_case_id')
    if not all([user_id, salesforce_case_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and salesforce_case_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await it_manager_service.create_jira_issue_from_salesforce_case(user_id, salesforce_case_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Jira issue from Salesforce case for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "ISSUE_CREATE_FAILED", "message": str(e)}}), 500

@it_manager_bp.route('/api/it/jira-issue-summary/<issue_id>', methods=['GET'])
async def get_jira_issue_summary(issue_id):
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await it_manager_service.get_jira_issue_summary(user_id, issue_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting Jira issue summary for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "SUMMARY_FETCH_FAILED", "message": str(e)}}), 500

@it_manager_bp.route('/api/it/create-trello-card-from-jira-issue', methods=['POST'])
async def create_trello_card_from_jira_issue():
    data = request.get_json()
    user_id = data.get('user_id')
    issue_id = data.get('issue_id')
    trello_list_id = data.get('trello_list_id')
    if not all([user_id, issue_id, trello_list_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, issue_id, and trello_list_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await it_manager_service.create_trello_card_from_jira_issue(user_id, issue_id, trello_list_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Trello card from Jira issue for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CARD_CREATE_FAILED", "message": str(e)}}), 500
