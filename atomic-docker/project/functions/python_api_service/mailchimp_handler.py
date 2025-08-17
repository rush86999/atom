import logging
from flask import Blueprint, request, jsonify, current_app
from . import mailchimp_service

logger = logging.getLogger(__name__)

mailchimp_bp = Blueprint('mailchimp_bp', __name__)

@mailchimp_bp.route('/api/mailchimp/lists', methods=['GET'])
async def get_all_lists():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        client = await mailchimp_service.get_mailchimp_client(user_id, db_conn_pool)
        if not client:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Mailchimp client."}}), 401

        result = await mailchimp_service.get_all_lists(client)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting Mailchimp lists for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "LISTS_FETCH_FAILED", "message": str(e)}}), 500

@mailchimp_bp.route('/api/mailchimp/lists/<list_id>/members', methods=['POST'])
async def add_list_member(list_id):
    data = request.get_json()
    user_id = data.get('user_id')
    member_data = data.get('member_data')

    if not all([user_id, member_data]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and member_data are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        client = await mailchimp_service.get_mailchimp_client(user_id, db_conn_pool)
        if not client:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Mailchimp client."}}), 401

        result = await mailchimp_service.add_list_member(client, list_id, member_data)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error adding member to Mailchimp list for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "MEMBER_ADD_FAILED", "message": str(e)}}), 500

@mailchimp_bp.route('/api/mailchimp/templates', methods=['GET'])
async def list_templates():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        client = await mailchimp_service.get_mailchimp_client(user_id, db_conn_pool)
        if not client:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Mailchimp client."}}), 401

        result = await mailchimp_service.list_templates(client)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error listing Mailchimp templates for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "TEMPLATES_FETCH_FAILED", "message": str(e)}}), 500

@mailchimp_bp.route('/api/mailchimp/credentials', methods=['POST'])
async def set_mailchimp_credentials():
    data = request.get_json()
    user_id = data.get('user_id')
    api_key = data.get('api_key')
    server_prefix = data.get('server_prefix')

    if not all([user_id, api_key, server_prefix]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, api_key, and server_prefix are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await mailchimp_service.set_mailchimp_credentials(user_id, api_key, server_prefix, db_conn_pool)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error setting Mailchimp credentials for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CREDENTIALS_SET_FAILED", "message": str(e)}}), 500
