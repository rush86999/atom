import logging
from flask import Blueprint, request, jsonify, current_app
from . import legal_service

logger = logging.getLogger(__name__)

legal_bp = Blueprint('legal_bp', __name__)

@legal_bp.route('/api/legal/create-docusign-envelope-from-salesforce-opportunity', methods=['POST'])
async def create_docusign_envelope_from_salesforce_opportunity():
    data = request.get_json()
    user_id = data.get('user_id')
    salesforce_opportunity_id = data.get('salesforce_opportunity_id')
    if not all([user_id, salesforce_opportunity_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and salesforce_opportunity_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await legal_service.create_docusign_envelope_from_salesforce_opportunity(user_id, salesforce_opportunity_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Docusign envelope from Salesforce opportunity for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "ENVELOPE_CREATE_FAILED", "message": str(e)}}), 500

@legal_bp.route('/api/legal/docusign-envelope-status/<envelope_id>', methods=['GET'])
async def get_docusign_envelope_status(envelope_id):
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await legal_service.get_docusign_envelope_status(user_id, envelope_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting Docusign envelope status for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "STATUS_FETCH_FAILED", "message": str(e)}}), 500

@legal_bp.route('/api/legal/create-trello-card-from-docusign-envelope', methods=['POST'])
async def create_trello_card_from_docusign_envelope():
    data = request.get_json()
    user_id = data.get('user_id')
    envelope_id = data.get('envelope_id')
    trello_list_id = data.get('trello_list_id')
    if not all([user_id, envelope_id, trello_list_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, envelope_id, and trello_list_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await legal_service.create_trello_card_from_docusign_envelope(user_id, envelope_id, trello_list_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Trello card from Docusign envelope for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CARD_CREATE_FAILED", "message": str(e)}}), 500
