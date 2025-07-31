import logging
from flask import Blueprint, request, jsonify, current_app
from . import zoho_service

logger = logging.getLogger(__name__)

zoho_bp = Blueprint('zoho_bp', __name__)

@zoho_bp.route('/api/zoho/organizations', methods=['GET'])
async def get_zoho_organizations():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await zoho_service.get_zoho_organizations(user_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting Zoho organizations for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_ZOHO_ORGANIZATIONS_FAILED", "message": str(e)}}), 500
