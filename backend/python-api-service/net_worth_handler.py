import logging
from flask import Blueprint, request, jsonify, current_app
from . import net_worth_service

logger = logging.getLogger(__name__)

net_worth_bp = Blueprint('net_worth_bp', __name__)

@net_worth_bp.route('/api/financial/net_worth', methods=['GET'])
async def get_net_worth():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await net_worth_service.get_net_worth(user_id, db_conn_pool)
        return jsonify({"ok": True, "data": {"net_worth": result}})
    except Exception as e:
        logger.error(f"Error getting net worth for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_NET_WORTH_FAILED", "message": str(e)}}), 500
