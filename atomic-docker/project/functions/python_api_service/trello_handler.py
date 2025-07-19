import logging
from flask import Blueprint, request, jsonify, current_app
from . import trello_service

logger = logging.getLogger(__name__)

trello_bp = Blueprint('trello_bp', __name__)

@trello_bp.route('/api/trello/boards', methods=['GET'])
async def get_boards():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        api_key, token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
        if not api_key or not token:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get Trello credentials. Please connect your Trello account."}}), 401

        boards = await trello_service.list_boards(api_key, token)
        return jsonify({"ok": True, "data": {"boards": boards}})
    except Exception as e:
        logger.error(f"Error getting Trello boards for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "BOARDS_FETCH_FAILED", "message": str(e)}}), 500

@trello_bp.route('/api/trello/lists', methods=['GET'])
async def get_lists():
    user_id = request.args.get('user_id')
    board_id = request.args.get('board_id')
    if not user_id or not board_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and board_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        api_key, token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
        if not api_key or not token:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get Trello credentials. Please connect your Trello account."}}), 401

        lists = await trello_service.list_lists(api_key, token, board_id)
        return jsonify({"ok": True, "data": {"lists": lists}})
    except Exception as e:
        logger.error(f"Error getting Trello lists for user {user_id}, board {board_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "LISTS_FETCH_FAILED", "message": str(e)}}), 500

@trello_bp.route('/api/trello/cards', methods=['GET', 'POST'])
async def handle_cards():
    if request.method == 'GET':
        user_id = request.args.get('user_id')
        list_id = request.args.get('list_id')
        if not user_id or not list_id:
            return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and list_id are required."}}), 400
    else: # POST
        data = request.get_json()
        user_id = data.get('user_id')
        list_id = data.get('list_id')
        name = data.get('name')
        if not user_id or not list_id or not name:
            return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, list_id, and name are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        api_key, token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
        if not api_key or not token:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get Trello credentials. Please connect your Trello account."}}), 401

        if request.method == 'GET':
            cards = await trello_service.list_cards(api_key, token, list_id)
            return jsonify({"ok": True, "data": {"cards": cards}})
        else: # POST
            desc = data.get('desc')
            card = await trello_service.create_card(api_key, token, list_id, name, desc)
            return jsonify({"ok": True, "data": card})
    except Exception as e:
        logger.error(f"Error handling Trello cards for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CARDS_HANDLING_FAILED", "message": str(e)}}), 500

@trello_bp.route('/api/trello/cards/<card_id>/move', methods=['PUT'])
async def move_card(card_id):
    data = request.get_json()
    user_id = data.get('user_id')
    new_list_id = data.get('list_id')
    if not user_id or not new_list_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and list_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        api_key, token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
        if not api_key or not token:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get Trello credentials. Please connect your Trello account."}}), 401

        card = await trello_service.move_card(api_key, token, card_id, new_list_id)
        return jsonify({"ok": True, "data": card})
    except Exception as e:
        logger.error(f"Error moving Trello card {card_id} for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CARD_MOVE_FAILED", "message": str(e)}}), 500
