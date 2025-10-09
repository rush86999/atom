import logging
import os
from flask import Blueprint, request, jsonify, current_app
from typing import Dict, Any, Optional


# Import database utilities for OAuth tokens
try:
    from db_utils import get_db_pool
    from db_oauth_notion import get_tokens

    DB_AVAILABLE = True
except ImportError:
    logger.warning(
        "Database utilities not available - OAuth tokens will not be available"
    )
    DB_AVAILABLE = False

logger = logging.getLogger(__name__)

notion_bp = Blueprint("notion_bp", __name__)

# Import real notion service
from notion_service_real import get_real_notion_client, RealNotionService


def _get_notion_access_token_for_user(user_id: str) -> Optional[str]:
    """Get Notion OAuth access token for a user from database"""
    if not DB_AVAILABLE:
        logger.warning("Database not available - cannot retrieve OAuth tokens")
        return None

    try:
        db_pool = get_db_pool()
        if not db_pool:
            logger.error("Database connection pool not available")
            return None

        tokens = get_tokens(db_pool, user_id)
        if tokens and tokens.get("access_token"):
            logger.info(f"Retrieved Notion OAuth token for user {user_id}")
            return tokens["access_token"]
        else:
            logger.warning(f"No Notion OAuth tokens found for user {user_id}")
            return None

    except Exception as e:
        logger.error(f"Error retrieving Notion tokens for user {user_id}: {e}")
        return None


def get_notion_client(user_id: str) -> Optional[RealNotionService]:
    """
    Get real Notion client using OAuth tokens from database.
    """
    try:
        if not user_id:
            logger.warning("User ID is required to get Notion OAuth tokens")
            return None

        access_token = _get_notion_access_token_for_user(user_id)

        if not access_token:
            logger.warning(f"No Notion OAuth access token found for user {user_id}")
            return None

        return get_real_notion_client(access_token)

    except Exception as e:
        logger.error(f"Error creating Notion client: {e}")
        return None


@notion_bp.route("/api/notion/search", methods=["POST"])
def search_notion_route():
    """Search Notion pages with real implementation using frontend API token"""
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
        query = data.get("query", "")

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

        logger.info(f"Searching Notion for user {user_id}, query: {query}")

        # Get real client using OAuth tokens from database
        client = get_notion_client(user_id)
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "Notion account not connected. Please connect your Notion account via OAuth.",
                    },
                }
            ), 401

        # Use real search functionality
        search_results = client.search_pages(query=query)

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
                "metadata": {"user_id": user_id, "query": query, "is_mock": False},
            }
        )

    except Exception as e:
        logger.error(f"Error searching Notion: {e}", exc_info=True)
        return jsonify(
            {"ok": False, "error": {"code": "SEARCH_PAGES_FAILED", "message": str(e)}}
        ), 500


@notion_bp.route("/api/notion/list-pages", methods=["POST"])
def list_pages():
    """List Notion pages from a database with real implementation using frontend API token"""
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
        database_id = data.get("database_id")

        if not user_id or not database_id:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "user_id and database_id are required",
                    },
                }
            ), 400

        logger.info(f"Listing Notion pages for user {user_id}, database {database_id}")

        # Get real client using OAuth tokens from database
        client = get_notion_client(user_id)
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "Notion account not connected. Please connect your Notion account via OAuth.",
                    },
                }
            ), 401

        # Use real list functionality
        list_results = client.list_files(database_id=database_id)

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
                    "database_id": database_id,
                    "is_mock": False,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error listing Notion pages: {e}", exc_info=True)
        return jsonify(
            {"ok": False, "error": {"code": "LIST_PAGES_FAILED", "message": str(e)}}
        ), 500


@notion_bp.route("/api/notion/health", methods=["GET"])
def notion_health():
    """Health check for Notion integration using frontend API token"""
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

        client = get_notion_client(user_id)
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "service": "notion",
                    "status": "disconnected",
                    "message": "Notion account not connected. Please connect your Notion account via OAuth.",
                }
            ), 401

        status = client.get_service_status()

        return jsonify(
            {
                "ok": True,
                "service": "notion",
                "status": status["status"],
                "message": status["message"],
                "available": status["available"],
                "mock_data": status["mock_data"],
                "user": status.get("user"),
            }
        )

    except Exception as e:
        logger.error(f"Error checking Notion health: {e}")
        return jsonify(
            {
                "ok": False,
                "service": "notion",
                "status": "error",
                "message": f"Health check failed: {str(e)}",
            }
        ), 500


@notion_bp.route("/api/notion/page/<page_id>", methods=["GET"])
def get_page(page_id: str):
    """Get detailed information about a specific Notion page using frontend API token"""
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

        logger.info(f"Getting Notion page {page_id} for user {user_id}")

        client = get_notion_client(user_id)
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "Notion account not connected. Please connect your Notion account via OAuth.",
                    },
                }
            ), 401

        # Get page details
        page_result = client.get_file_metadata(page_id)

        if page_result["status"] == "error":
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "GET_PAGE_FAILED",
                        "message": page_result["message"],
                    },
                }
            ), 500

        return jsonify(
            {
                "ok": True,
                "data": page_result["data"],
                "metadata": {"user_id": user_id, "page_id": page_id, "is_mock": False},
            }
        )

    except Exception as e:
        logger.error(f"Error getting Notion page {page_id}: {e}", exc_info=True)
        return jsonify(
            {"ok": False, "error": {"code": "GET_PAGE_FAILED", "message": str(e)}}
        ), 500


@notion_bp.route("/api/notion/page/<page_id>/download", methods=["GET"])
def download_page(page_id: str):
    """Download Notion page content as markdown using frontend API token"""
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

        logger.info(f"Downloading Notion page {page_id} for user {user_id}")

        client = get_notion_client(user_id)
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "Notion account not connected. Please connect your Notion account via OAuth.",
                    },
                }
            ), 401

        # Download page content
        download_result = client.download_file(page_id)

        if download_result["status"] == "error":
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "DOWNLOAD_PAGE_FAILED",
                        "message": download_result["message"],
                    },
                }
            ), 500

        return jsonify(
            {
                "ok": True,
                "data": download_result["data"],
                "metadata": {"user_id": user_id, "page_id": page_id, "is_mock": False},
            }
        )

    except Exception as e:
        logger.error(f"Error downloading Notion page {page_id}: {e}", exc_info=True)
        return jsonify(
            {"ok": False, "error": {"code": "DOWNLOAD_PAGE_FAILED", "message": str(e)}}
        ), 500


@notion_bp.route("/api/notion/databases", methods=["GET"])
def list_databases():
    """List available Notion databases using frontend API token"""
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

        logger.info(f"Listing Notion databases for user {user_id}")

        client = get_notion_client(user_id)
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "Notion account not connected. Please connect your Notion account via OAuth.",
                    },
                }
            ), 401

        # Search for databases (Notion API doesn't have a direct list databases endpoint)
        search_results = client.search_pages(query="", page_size=100)

        if search_results["status"] == "error":
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "LIST_DATABASES_FAILED",
                        "message": search_results["message"],
                    },
                }
            ), 500

        # Filter for databases only
        databases = []
        for item in search_results["data"].get("files", []):
            if item.get("object_type") == "database":
                databases.append(
                    {
                        "id": item["id"],
                        "name": item["name"],
                        "url": item["url"],
                        "description": item.get("description", ""),
                        "last_edited_time": item.get("last_edited_time"),
                    }
                )

        return jsonify(
            {
                "ok": True,
                "data": databases,
                "metadata": {
                    "user_id": user_id,
                    "is_mock": False,
                    "total_databases": len(databases),
                },
            }
        )

    except Exception as e:
        logger.error(f"Error listing Notion databases: {e}", exc_info=True)
        return jsonify(
            {"ok": False, "error": {"code": "LIST_DATABASES_FAILED", "message": str(e)}}
        ), 500
