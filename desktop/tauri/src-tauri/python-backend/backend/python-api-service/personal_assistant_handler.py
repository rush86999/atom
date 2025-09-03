import logging
from flask import Blueprint, request, jsonify, current_app
from . import personal_assistant_service

logger = logging.getLogger(__name__)

personal_assistant_bp = Blueprint('personal_assistant_bp', __name__)

@personal_assistant_bp.route('/api/personal/weather', methods=['GET'])
async def get_weather():
    user_id = request.args.get('user_id')
    location = request.args.get('location')
    if not all([user_id, location]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and location are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await personal_assistant_service.get_weather(user_id, location, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting weather for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "WEATHER_FETCH_FAILED", "message": str(e)}}), 500

@personal_assistant_bp.route('/api/personal/news', methods=['GET'])
async def get_news():
    user_id = request.args.get('user_id')
    query = request.args.get('q')
    if not all([user_id, query]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and q are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await personal_assistant_service.get_news(user_id, query, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting news for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "NEWS_FETCH_FAILED", "message": str(e)}}), 500

@personal_assistant_bp.route('/api/personal/set-reminder', methods=['POST'])
async def set_reminder():
    data = request.get_json()
    user_id = data.get('user_id')
    reminder = data.get('reminder')
    remind_at = data.get('remind_at')
    if not all([user_id, reminder, remind_at]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, reminder, and remind_at are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await personal_assistant_service.set_reminder(user_id, reminder, remind_at, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error setting reminder for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "REMINDER_SET_FAILED", "message": str(e)}}), 500
