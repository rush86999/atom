import logging
import json
from flask import Blueprint, request, jsonify, current_app
from jira_service_real import (
    RealJiraService,
    get_real_jira_client,
    get_real_jira_client_with_cloud_id,
)
import os
import db_oauth_jira, crypto_utils

logger = logging.getLogger(__name__)

jira_bp = Blueprint("jira_bp", __name__)


async def get_jira_client(user_id: str, db_conn_pool):
    """Get real Jira client with user's OAuth credentials and cloud ID"""
    try:
        # Try to get OAuth tokens from database first
        tokens = await db_oauth_jira.get_tokens(db_conn_pool, user_id)
        if tokens:
            encrypted_token_data = tokens[0]
            try:
                token_data_json = crypto_utils.decrypt_message(encrypted_token_data)
                token_data = json.loads(token_data_json)

                access_token = token_data.get("access_token")
                cloud_id = token_data.get("cloud_id")

                if access_token and cloud_id:
                    # Use the cloud ID for API calls with OAuth token
                    client = get_real_jira_client_with_cloud_id(cloud_id, access_token)
                    return RealJiraService(client, cloud_id)
                else:
                    logger.warning(
                        f"Invalid token data for user {user_id}: missing access_token or cloud_id"
                    )
            except Exception as e:
                logger.error(
                    f"Error decrypting Jira token data for user {user_id}: {e}"
                )

        # Fallback to basic auth if no valid OAuth tokens
        server_url = os.getenv("JIRA_SERVER_URL")
        username = os.getenv("JIRA_USERNAME")
        api_token = os.getenv("JIRA_API_TOKEN")

        if all([server_url, username, api_token]):
            client = get_real_jira_client(
                server_url, username=username, password=api_token
            )
            return RealJiraService(client)

        logger.warning(f"No Jira credentials found for user {user_id}")
        return None

    except Exception as e:
        logger.error(f"Error getting Jira client for user {user_id}: {e}")
        return None


@jira_bp.route("/api/jira/search", methods=["POST"])
async def search_jira_route():
    data = request.get_json()
    user_id = data.get("user_id")
    project_id = data.get("project_id")
    query = data.get("query")
    if not user_id or not query or not project_id:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "user_id, project_id, and query are required.",
                },
            }
        ), 400

    try:
        client = await get_jira_client(
            user_id, current_app.config["DB_CONNECTION_POOL"]
        )
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "User not authenticated with Jira.",
                    },
                }
            ), 401

        search_results = client.list_files(project_id=project_id, query=query)
        return jsonify({"ok": True, "data": search_results})
    except Exception as e:
        logger.error(f"Error searching Jira for user {user_id}: {e}", exc_info=True)
        return jsonify(
            {"ok": False, "error": {"code": "SEARCH_ISSUES_FAILED", "message": str(e)}}
        ), 500


@jira_bp.route("/api/jira/list-issues", methods=["POST"])
async def list_issues():
    data = request.get_json()
    user_id = data.get("user_id")
    project_id = data.get("project_id")
    page_size = data.get("page_size", 100)
    page_token = data.get("page_token")

    if not user_id or not project_id:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "user_id and project_id are required.",
                },
            }
        ), 400

    try:
        client = await get_jira_client(
            user_id, current_app.config["DB_CONNECTION_POOL"]
        )
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "User not authenticated with Jira.",
                    },
                }
            ), 401

        issues = client.list_files(
            project_id=project_id, page_size=page_size, page_token=page_token
        )
        return jsonify({"ok": True, "data": issues})
    except Exception as e:
        logger.error(
            f"Error listing Jira issues for user {user_id}: {e}", exc_info=True
        )
        return jsonify(
            {"ok": False, "error": {"code": "LIST_ISSUES_FAILED", "message": str(e)}}
        ), 500


@jira_bp.route("/api/jira/get-issue", methods=["POST"])
async def get_issue():
    data = request.get_json()
    user_id = data.get("user_id")
    issue_id = data.get("issue_id")

    if not user_id or not issue_id:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "user_id and issue_id are required.",
                },
            }
        ), 400

    try:
        client = await get_jira_client(
            user_id, current_app.config["DB_CONNECTION_POOL"]
        )
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "User not authenticated with Jira.",
                    },
                }
            ), 401

        issue_metadata = client.get_file_metadata(file_id=issue_id)
        return jsonify({"ok": True, "data": issue_metadata})
    except Exception as e:
        logger.error(
            f"Error getting Jira issue {issue_id} for user {user_id}: {e}",
            exc_info=True,
        )
        return jsonify(
            {"ok": False, "error": {"code": "GET_ISSUE_FAILED", "message": str(e)}}
        ), 500


@jira_bp.route("/api/jira/create-issue", methods=["POST"])
async def create_issue():
    data = request.get_json()
    user_id = data.get("user_id")
    project_id = data.get("project_id")
    summary = data.get("summary")
    description = data.get("description", "")
    issue_type = data.get("issue_type", "Task")
    priority = data.get("priority", "Medium")

    if not user_id or not project_id or not summary:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "user_id, project_id, and summary are required.",
                },
            }
        ), 400

    try:
        client = await get_jira_client(
            user_id, current_app.config["DB_CONNECTION_POOL"]
        )
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "User not authenticated with Jira.",
                    },
                }
            ), 401

        result = client.create_issue(
            project_id=project_id,
            summary=summary,
            description=description,
            issue_type=issue_type,
            priority=priority,
        )
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(
            f"Error creating Jira issue for user {user_id}: {e}", exc_info=True
        )
        return jsonify(
            {"ok": False, "error": {"code": "CREATE_ISSUE_FAILED", "message": str(e)}}
        ), 500


@jira_bp.route("/api/jira/update-issue", methods=["POST"])
async def update_issue():
    data = request.get_json()
    user_id = data.get("user_id")
    issue_id = data.get("issue_id")
    summary = data.get("summary")
    description = data.get("description")
    status = data.get("status")

    if not user_id or not issue_id:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "user_id and issue_id are required.",
                },
            }
        ), 400

    try:
        client = await get_jira_client(
            user_id, current_app.config["DB_CONNECTION_POOL"]
        )
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "User not authenticated with Jira.",
                    },
                }
            ), 401

        result = client.update_issue(
            issue_id=issue_id, summary=summary, description=description, status=status
        )
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(
            f"Error updating Jira issue {issue_id} for user {user_id}: {e}",
            exc_info=True,
        )
        return jsonify(
            {"ok": False, "error": {"code": "UPDATE_ISSUE_FAILED", "message": str(e)}}
        ), 500


@jira_bp.route("/api/jira/projects", methods=["POST"])
async def list_projects():
    data = request.get_json()
    user_id = data.get("user_id")

    if not user_id:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "user_id is required.",
                },
            }
        ), 400

    try:
        client = await get_jira_client(
            user_id, current_app.config["DB_CONNECTION_POOL"]
        )
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "User not authenticated with Jira.",
                    },
                }
            ), 401

        # Get projects from Jira client
        jira_client = client.client  # Get the underlying JIRA client
        projects = jira_client.projects()

        project_list = []
        for project in projects:
            project_list.append(
                {
                    "id": project.id,
                    "key": project.key,
                    "name": project.name,
                    "description": getattr(project, "description", None),
                }
            )

        return jsonify({"ok": True, "data": {"projects": project_list}})
    except Exception as e:
        logger.error(
            f"Error listing Jira projects for user {user_id}: {e}", exc_info=True
        )
        return jsonify(
            {"ok": False, "error": {"code": "LIST_PROJECTS_FAILED", "message": str(e)}}
        ), 500
