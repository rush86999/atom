import logging
from flask import Blueprint, request, jsonify, current_app
from . import social_media_service

logger = logging.getLogger(__name__)

social_media_bp = Blueprint('social_media_bp', __name__)

@social_media_bp.route('/api/social/twitter/schedule-tweet', methods=['POST'])
async def schedule_tweet():
    data = request.get_json()
    user_id = data.get('user_id')
    status = data.get('status')
    send_at = data.get('send_at')
    if not all([user_id, status, send_at]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, status, and send_at are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await social_media_service.schedule_tweet(user_id, status, send_at, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error scheduling tweet for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "TWEET_SCHEDULE_FAILED", "message": str(e)}}), 500

@social_media_bp.route('/api/social/twitter/monitor-mentions', methods=['POST'])
async def monitor_mentions():
    data = request.get_json()
    user_id = data.get('user_id')
    trello_list_id = data.get('trello_list_id')
    if not all([user_id, trello_list_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and trello_list_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await social_media_service.monitor_twitter_mentions(user_id, trello_list_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error monitoring mentions for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "MENTIONS_MONITOR_FAILED", "message": str(e)}}), 500

@social_media_bp.route('/api/social/twitter/create-lead-from-tweet', methods=['POST'])
async def create_lead_from_tweet():
    data = request.get_json()
    user_id = data.get('user_id')
    tweet_id = data.get('tweet_id')
    if not all([user_id, tweet_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and tweet_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await social_media_service.create_salesforce_lead_from_tweet(user_id, tweet_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Salesforce lead from tweet for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "LEAD_CREATE_FAILED", "message": str(e)}}), 500
