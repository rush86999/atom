import logging
from flask import Blueprint, request, jsonify
from . import trello_service

logger = logging.getLogger(__name__)

trello_bp = Blueprint('trello_bp', __name__)

from trello import TrelloClient
from . import db_oauth_trello, crypto_utils
import os

async def get_trello_client(user_id: str, db_conn_pool):
    tokens = await db_oauth_trello.get_tokens(db_conn_pool, user_id)
    if not tokens:
        return None

    access_token = crypto_utils.decrypt_message(tokens[0])
    access_token_secret = crypto_utils.decrypt_message(tokens[1])

    client = TrelloClient(
        api_key=os.getenv("TRELLO_API_KEY"),
        api_secret=os.getenv("TRELLO_API_SECRET"),
        token=access_token,
        token_secret=access_token_secret
    )
    return trello_service.TrelloService(client)

@trello_bp.route('/api/trello/search', methods=['POST'])
def search_trello_route():
    data = request.get_json()
    user_id = data.get('user_id')
    board_id = data.get('board_id')
    query = data.get('query')
    if not user_id or not query or not board_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, board_id, and query are required."}}), 400

    try:
        client = get_trello_client(user_id)
        search_results = client.list_files(board_id=board_id, query=query)
        return jsonify({"ok": True, "data": search_results})
    except Exception as e:
        logger.error(f"Error searching Trello for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "SEARCH_CARDS_FAILED", "message": str(e)}}), 500

@trello_bp.route('/api/trello/list-cards', methods=['POST'])
def list_cards():
    data = request.get_json()
    user_id = data.get('user_id')
    board_id = data.get('board_id')
    if not user_id or not board_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and board_id are required."}}), 400

    try:
        client = get_trello_client(user_id)
        list_results = client.list_files(board_id=board_id)
        return jsonify({"ok": True, "data": list_results})
    except Exception as e:
        logger.error(f"Error listing Trello cards for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "LIST_CARDS_FAILED", "message": str(e)}}), 500
