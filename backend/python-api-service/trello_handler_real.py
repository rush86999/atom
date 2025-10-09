import logging
import os
from flask import Blueprint, request, jsonify, current_app
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

trello_bp = Blueprint("trello_bp", __name__)

# Import real trello service
from trello_service_real import get_real_trello_client, RealTrelloService


def _extract_trello_api_keys_from_request():
    """Extract Trello API keys from request headers"""
    api_key = request.headers.get("X-Trello-API-Key")
    api_token = request.headers.get("X-Trello-API-Token")

    if not api_key or not api_token:
        return None, None

    return api_key, api_token


async def get_trello_client() -> Optional[RealTrelloService]:
    """
    Get real Trello client using API keys from frontend headers.
    """
    try:
        api_key, api_token = _extract_trello_api_keys_from_request()

        if not api_key or not api_token:
            logger.warning("Trello API keys not provided in request headers")
            return None

        return get_real_trello_client(api_key, api_token)

    except Exception as e:
        logger.error(f"Error creating Trello client: {e}")
        return None


@trello_bp.route("/api/trello/search", methods=["POST"])
async def search_trello_route():
    """Search Trello cards with real implementation using frontend API keys"""
    try:
        data = request.get_json()
        if not data:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "JSON data is required",
                    },
                }
            ), 400

        user_id = data.get("user_id")
        board_id = data.get("board_id")
        query = data.get("query", "")

        if not user_id or not board_id:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "user_id and board_id are required",
                    },
                }
            ), 400

        logger.info(
            f"Searching Trello for user {user_id}, board {board_id}, query: {query}"
        )

        # Get real client using frontend API keys
        client = await get_trello_client()
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "Trello API keys not provided in headers (X-Trello-API-Key, X-Trello-API-Token)",
                    },
                }
            ), 401

        # Use real search functionality
        search_results = client.list_files(board_id=board_id, query=query)

        if search_results["status"] == "error":
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "SEARCH_FAILED",
                        "message": search_results["message"],
                    },
                }
            ), 500

        return jsonify(
            {
                "ok": True,
                "data": search_results["data"],
                "metadata": {
                    "user_id": user_id,
                    "board_id": board_id,
                    "query": query,
                    "is_mock": False,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error searching Trello: {e}", exc_info=True)
        return jsonify(
            {"ok": False, "error": {"code": "SEARCH_CARDS_FAILED", "message": str(e)}}
        ), 500


@trello_bp.route("/api/trello/list-cards", methods=["POST"])
async def list_cards():
    """List Trello cards with real implementation using frontend API keys"""
    try:
        data = request.get_json()
        if not data:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "JSON data is required",
                    },
                }
            ), 400

        user_id = data.get("user_id")
        board_id = data.get("board_id")

        if not user_id or not board_id:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "user_id and board_id are required",
                    },
                }
            ), 400

        logger.info(f"Listing Trello cards for user {user_id}, board {board_id}")

        # Get real client using frontend API keys
        client = await get_trello_client()
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "Trello API keys not provided in headers (X-Trello-API-Key, X-Trello-API-Token)",
                    },
                }
            ), 401

        # Use real list functionality
        list_results = client.list_files(board_id=board_id)

        if list_results["status"] == "error":
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "LIST_FAILED",
                        "message": list_results["message"],
                    },
                }
            ), 500

        return jsonify(
            {
                "ok": True,
                "data": list_results["data"],
                "metadata": {
                    "user_id": user_id,
                    "board_id": board_id,
                    "is_mock": False,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error listing Trello cards: {e}", exc_info=True)
        return jsonify(
            {"ok": False, "error": {"code": "LIST_CARDS_FAILED", "message": str(e)}}
        ), 500


@trello_bp.route("/api/trello/health", methods=["GET"])
async def trello_health():
    """Health check for Trello integration using frontend API keys"""
    try:
        user_id = request.args.get("user_id")

        if not user_id:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "user_id is required",
                    },
                }
            ), 400

        client = await get_trello_client()
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "service": "trello",
                    "status": "disconnected",
                    "message": "Trello API keys not provided in headers (X-Trello-API-Key, X-Trello-API-Token)",
                }
            ), 401

        status = client.get_service_status()

        return jsonify(
            {
                "ok": True,
                "service": "trello",
                "status": status["status"],
                "message": status["message"],
                "available": status["available"],
                "mock_data": status["mock_data"],
                "user": status.get("user"),
            }
        )

    except Exception as e:
        logger.error(f"Error checking Trello health: {e}")
        return jsonify(
            {
                "ok": False,
                "service": "trello",
                "status": "error",
                "message": f"Health check failed: {str(e)}",
            }
        ), 500


@trello_bp.route("/api/trello/boards", methods=["GET"])
async def list_boards():
    """List available Trello boards with real implementation using frontend API keys"""
    try:
        user_id = request.args.get("user_id")

        if not user_id:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "user_id is required",
                    },
                }
            ), 400

        logger.info(f"Listing Trello boards for user {user_id}")

        client = await get_trello_client()
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "Trello API keys not provided in headers (X-Trello-API-Key, X-Trello-API-Token)",
                    },
                }
            ), 401

        # Get all boards for the authenticated user
        trello_client = client.client
        boards = trello_client.list_boards()

        boards_data = []
        for board in boards:
            boards_data.append(
                {
                    "id": board.id,
                    "name": board.name,
                    "url": board.url,
                    "description": board.desc,
                    "closed": board.closed,
                    "last_activity": board.date_last_activity.isoformat()
                    if board.date_last_activity
                    else None,
                }
            )

        return jsonify(
            {
                "ok": True,
                "data": boards_data,
                "metadata": {
                    "user_id": user_id,
                    "is_mock": False,
                    "total_boards": len(boards_data),
                },
            }
        )

    except Exception as e:
        logger.error(f"Error listing Trello boards: {e}", exc_info=True)
        return jsonify(
            {"ok": False, "error": {"code": "LIST_BOARDS_FAILED", "message": str(e)}}
        ), 500


@trello_bp.route("/api/trello/card/<card_id>", methods=["GET"])
async def get_card(card_id: str):
    """Get detailed information about a specific Trello card using frontend API keys"""
    try:
        user_id = request.args.get("user_id")

        if not user_id:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "user_id is required",
                    },
                }
            ), 400

        logger.info(f"Getting Trello card {card_id} for user {user_id}")

        client = await get_trello_client()
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "Trello API keys not provided in headers (X-Trello-API-Key, X-Trello-API-Token)",
                    },
                }
            ), 401

        # Get card details
        card_result = client.get_file_metadata(card_id)

        if card_result["status"] == "error":
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "GET_CARD_FAILED",
                        "message": card_result["message"],
                    },
                }
            ), 500

        return jsonify(
            {
                "ok": True,
                "data": card_result["data"],
                "metadata": {"user_id": user_id, "card_id": card_id, "is_mock": False},
            }
        )

    except Exception as e:
        logger.error(f"Error getting Trello card {card_id}: {e}", exc_info=True)
        return jsonify(
            {"ok": False, "error": {"code": "GET_CARD_FAILED", "message": str(e)}}
        ), 500
