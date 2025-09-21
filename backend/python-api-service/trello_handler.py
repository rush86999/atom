import logging
from flask import Blueprint, request, jsonify, current_app
from typing import Dict, Any, Optional
import asyncio

logger = logging.getLogger(__name__)

trello_bp = Blueprint('trello_bp', __name__)

# Import mock trello service
import trello_service

async def get_trello_client(user_id: str, db_conn_pool=None) -> Optional[trello_service.TrelloService]:
    """
    Mock function to get Trello client for a user.
    In development mode, returns a mock client with demo data.
    """
    try:
        # In development, use mock client without requiring real credentials
        mock_client = trello_service.MockTrello(
            api_key="mock_trello_api_key",
            api_secret="mock_trello_api_secret",
            token="mock_trello_token"
        )
        return trello_service.TrelloService(mock_client)
    except Exception as e:
        logger.error(f"Error creating mock Trello client: {e}")
        return None

@trello_bp.route('/api/trello/search', methods=['POST'])
def search_trello_route():
    """Search Trello cards with mock implementation"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "JSON data is required"}}), 400

        user_id = data.get('user_id', 'demo_user')
        board_id = data.get('board_id', 'mock_board_1')
        query = data.get('query', '')

        logger.info(f"Searching Trello for user {user_id}, board {board_id}, query: {query}")

        # Get mock client
        client = asyncio.run(get_trello_client(user_id))
        if not client:
            return jsonify({"ok": False, "error": {"code": "CLIENT_ERROR", "message": "Failed to create Trello client"}}), 500

        # Use mock search functionality
        search_results = client.list_files(board_id=board_id, query=query)

        return jsonify({
            "ok": True,
            "data": search_results,
            "metadata": {
                "user_id": user_id,
                "board_id": board_id,
                "query": query,
                "is_mock": True
            }
        })

    except Exception as e:
        logger.error(f"Error searching Trello: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "SEARCH_CARDS_FAILED", "message": str(e)}}), 500

@trello_bp.route('/api/trello/list-cards', methods=['POST'])
def list_cards():
    """List Trello cards with mock implementation"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "JSON data is required"}}), 400

        user_id = data.get('user_id', 'demo_user')
        board_id = data.get('board_id', 'mock_board_1')

        logger.info(f"Listing Trello cards for user {user_id}, board {board_id}")

        # Get mock client
        client = asyncio.run(get_trello_client(user_id))
        if not client:
            return jsonify({"ok": False, "error": {"code": "CLIENT_ERROR", "message": "Failed to create Trello client"}}), 500

        # Use mock list functionality
        list_results = client.list_files(board_id=board_id)

        return jsonify({
            "ok": True,
            "data": list_results,
            "metadata": {
                "user_id": user_id,
                "board_id": board_id,
                "is_mock": True
            }
        })

    except Exception as e:
        logger.error(f"Error listing Trello cards: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "LIST_CARDS_FAILED", "message": str(e)}}), 500

@trello_bp.route('/api/trello/health', methods=['GET'])
def trello_health():
    """Health check for Trello integration"""
    return jsonify({
        "ok": True,
        "service": "trello",
        "status": "mock_mode",
        "message": "Trello integration running in mock mode for development"
    })

@trello_bp.route('/api/trello/boards', methods=['GET'])
def list_boards():
    """List available Trello boards (mock implementation)"""
    try:
        user_id = request.args.get('user_id', 'demo_user')

        logger.info(f"Listing Trello boards for user {user_id}")

        # Return mock boards data
        boards = [
            {
                "id": "mock_board_1",
                "name": "Project Board",
                "url": "https://trello.com/b/mock_board_1",
                "description": "Mock project management board"
            },
            {
                "id": "mock_board_2",
                "name": "Personal Tasks",
                "url": "https://trello.com/b/mock_board_2",
                "description": "Mock personal task board"
            }
        ]

        return jsonify({
            "ok": True,
            "data": boards,
            "metadata": {
                "user_id": user_id,
                "is_mock": True,
                "total_boards": len(boards)
            }
        })

    except Exception as e:
        logger.error(f"Error listing Trello boards: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "LIST_BOARDS_FAILED", "message": str(e)}}), 500
