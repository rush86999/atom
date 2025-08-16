import logging
from flask import Blueprint, request, jsonify, current_app
from . import ad_manager_service

logger = logging.getLogger(__name__)

ad_manager_bp = Blueprint('ad_manager_bp', __name__)

@ad_manager_bp.route('/api/ads/create-google-ads-campaign', methods=['POST'])
async def create_google_ads_campaign():
    data = request.get_json()
    user_id = data.get('user_id')
    customer_id = data.get('customer_id')
    campaign_data = data.get('campaign_data')

    if not all([user_id, customer_id, campaign_data]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, customer_id, and campaign_data are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await ad_manager_service.create_google_ads_campaign(user_id, customer_id, campaign_data, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Google Ads campaign for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CAMPAIGN_CREATE_FAILED", "message": str(e)}}), 500
