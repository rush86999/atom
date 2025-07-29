import logging
from flask import Blueprint, request, jsonify
from . import trello_service

logger = logging.getLogger(__name__)

trello_bp = Blueprint('trello_bp', __name__)

# A mock function to get a Trello client
# In a real application, this would involve OAuth and token management
def get_trello_client(user_id: str):
    # This is a placeholder. In a real app, you'd fetch the user's token from a database.
    # For this example, we'll use credentials from environment variables.
    import os
    api_key = os.getenv("TRELLO_API_KEY")
    api_secret = os.getenv("TRELLO_API_SECRET")
    token = os.getenv("TRELLO_TOKEN")
    if not all([api_key, api_secret, token]):
        raise ValueError("Trello API credentials not set in environment variables.")
    return trello_service.TrelloService(api_key, api_secret, token)

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
