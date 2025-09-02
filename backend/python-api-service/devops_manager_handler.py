import logging
from flask import Blueprint, request, jsonify, current_app
from . import devops_manager_service

logger = logging.getLogger(__name__)

devops_manager_bp = Blueprint('devops_manager_bp', __name__)

@devops_manager_bp.route('/api/devops/create-github-issue-from-jira-issue', methods=['POST'])
async def create_github_issue_from_jira_issue():
    data = request.get_json()
    user_id = data.get('user_id')
    jira_issue_id = data.get('jira_issue_id')
    if not all([user_id, jira_issue_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and jira_issue_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await devops_manager_service.create_github_issue_from_jira_issue(user_id, jira_issue_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating GitHub issue from Jira issue for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "ISSUE_CREATE_FAILED", "message": str(e)}}), 500

@devops_manager_bp.route('/api/devops/github-pull-request-status', methods=['GET'])
async def get_github_pull_request_status():
    user_id = request.args.get('user_id')
    pull_request_url = request.args.get('pull_request_url')
    if not all([user_id, pull_request_url]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and pull_request_url are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await devops_manager_service.get_github_pull_request_status(user_id, pull_request_url, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting GitHub pull request status for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "STATUS_FETCH_FAILED", "message": str(e)}}), 500

@devops_manager_bp.route('/api/devops/create-trello-card-from-github-issue', methods=['POST'])
async def create_trello_card_from_github_issue():
    data = request.get_json()
    user_id = data.get('user_id')
    issue_url = data.get('issue_url')
    trello_list_id = data.get('trello_list_id')
    if not all([user_id, issue_url, trello_list_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, issue_url, and trello_list_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await devops_manager_service.create_trello_card_from_github_issue(user_id, issue_url, trello_list_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Trello card from GitHub issue for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CARD_CREATE_FAILED", "message": str(e)}}), 500
