import logging
from flask import Blueprint, request, jsonify, current_app
from . import recruiting_manager_service

logger = logging.getLogger(__name__)

recruiting_manager_bp = Blueprint('recruiting_manager_bp', __name__)

@recruiting_manager_bp.route('/api/recruiting/create-greenhouse-candidate-from-linkedin-profile', methods=['POST'])
async def create_greenhouse_candidate_from_linkedin_profile():
    data = request.get_json()
    user_id = data.get('user_id')
    linkedin_profile_url = data.get('linkedin_profile_url')
    if not all([user_id, linkedin_profile_url]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and linkedin_profile_url are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await recruiting_manager_service.create_greenhouse_candidate_from_linkedin_profile(user_id, linkedin_profile_url, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Greenhouse candidate from LinkedIn profile for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CANDIDATE_CREATE_FAILED", "message": str(e)}}), 500

@recruiting_manager_bp.route('/api/recruiting/greenhouse-candidate-summary/<candidate_id>', methods=['GET'])
async def get_greenhouse_candidate_summary(candidate_id):
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await recruiting_manager_service.get_greenhouse_candidate_summary(user_id, candidate_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting Greenhouse candidate summary for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "SUMMARY_FETCH_FAILED", "message": str(e)}}), 500

@recruiting_manager_bp.route('/api/recruiting/create-trello-card-from-greenhouse-candidate', methods=['POST'])
async def create_trello_card_from_greenhouse_candidate():
    data = request.get_json()
    user_id = data.get('user_id')
    candidate_id = data.get('candidate_id')
    trello_list_id = data.get('trello_list_id')
    if not all([user_id, candidate_id, trello_list_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, candidate_id, and trello_list_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await recruiting_manager_service.create_trello_card_from_greenhouse_candidate(user_id, candidate_id, trello_list_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Trello card from Greenhouse candidate for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CARD_CREATE_FAILED", "message": str(e)}}), 500
