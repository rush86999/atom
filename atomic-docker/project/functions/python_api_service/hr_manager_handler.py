import logging
from flask import Blueprint, request, jsonify, current_app
from . import hr_manager_service

logger = logging.getLogger(__name__)

hr_manager_bp = Blueprint('hr_manager_bp', __name__)

@hr_manager_bp.route('/api/hr/create-bamboohr-employee-from-greenhouse-candidate', methods=['POST'])
async def create_bamboohr_employee_from_greenhouse_candidate():
    data = request.get_json()
    user_id = data.get('user_id')
    greenhouse_candidate_id = data.get('greenhouse_candidate_id')
    if not all([user_id, greenhouse_candidate_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and greenhouse_candidate_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await hr_manager_service.create_bamboohr_employee_from_greenhouse_candidate(user_id, greenhouse_candidate_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating BambooHR employee from Greenhouse candidate for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "EMPLOYEE_CREATE_FAILED", "message": str(e)}}), 500

@hr_manager_bp.route('/api/hr/bamboohr-employee-summary/<employee_id>', methods=['GET'])
async def get_bamboohr_employee_summary(employee_id):
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await hr_manager_service.get_bamboohr_employee_summary(user_id, employee_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting BambooHR employee summary for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "SUMMARY_FETCH_FAILED", "message": str(e)}}), 500

@hr_manager_bp.route('/api/hr/create-trello-card-from-bamboohr-employee', methods=['POST'])
async def create_trello_card_from_bamboohr_employee():
    data = request.get_json()
    user_id = data.get('user_id')
    employee_id = data.get('employee_id')
    trello_list_id = data.get('trello_list_id')
    if not all([user_id, employee_id, trello_list_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, employee_id, and trello_list_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await hr_manager_service.create_trello_card_from_bamboohr_employee(user_id, employee_id, trello_list_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Trello card from BambooHR employee for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CARD_CREATE_FAILED", "message": str(e)}}), 500
