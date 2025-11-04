import logging
from flask import Blueprint, request, jsonify, current_app
from asana_service_real import get_asana_service_real
import db_oauth_asana, crypto_utils

logger = logging.getLogger(__name__)

asana_bp = Blueprint("asana_bp", __name__)


async def get_asana_client(user_id: str, db_conn_pool):
    tokens = await db_oauth_asana.get_tokens(db_conn_pool, user_id)
    if not tokens:
        return None

    access_token = crypto_utils.decrypt_message(tokens[0])

    return get_asana_service_real(access_token)


@asana_bp.route("/api/asana/search", methods=["POST"])
async def search_asana_route():
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
        client = await get_asana_client(
            user_id, current_app.config["DB_CONNECTION_POOL"]
        )
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "User not authenticated with Asana.",
                    },
                }
            ), 401
        search_results = client.list_files(project_id=project_id, query=query)
        return jsonify({"ok": True, "data": search_results})
    except Exception as e:
        logger.error(f"Error searching Asana for user {user_id}: {e}", exc_info=True)
        return jsonify(
            {"ok": False, "error": {"code": "SEARCH_FILES_FAILED", "message": str(e)}}
        ), 500


@asana_bp.route("/api/asana/list-tasks", methods=["POST"])
async def list_tasks():
    data = request.get_json()
    user_id = data.get("user_id")
    project_id = data.get("project_id")
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
        client = await get_asana_client(
            user_id, current_app.config["DB_CONNECTION_POOL"]
        )
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "User not authenticated with Asana.",
                    },
                }
            ), 401
        list_results = client.list_files(project_id=project_id)
        return jsonify({"ok": True, "data": list_results})
    except Exception as e:
        logger.error(
            f"Error listing Asana tasks for user {user_id}: {e}", exc_info=True
        )
        return jsonify(
            {"ok": False, "error": {"code": "LIST_TASKS_FAILED", "message": str(e)}}
        ), 500


@asana_bp.route("/api/asana/health", methods=["GET"])
def asana_health():
    """Health check for Asana integration"""
    return jsonify(
        {
            "ok": True,
            "service": "asana",
            "status": "registered",
            "message": "Asana integration is registered and ready for OAuth configuration",
            "needs_oauth": True,
        }
    )


@asana_bp.route("/api/asana/projects", methods=["POST"])
async def get_projects():
    """Get Asana projects for a workspace or user"""
    data = request.get_json()
    user_id = data.get("user_id")
    workspace_id = data.get("workspace_id")
    limit = data.get("limit", 100)
    offset = data.get("offset")

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
        client = await get_asana_client(
            user_id, current_app.config["DB_CONNECTION_POOL"]
        )
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "User not authenticated with Asana.",
                    },
                }
            ), 401

        projects_result = client.get_projects(
            workspace_id=workspace_id, limit=limit, offset=offset
        )
        return jsonify({"ok": True, "data": projects_result})
    except Exception as e:
        logger.error(
            f"Error getting Asana projects for user {user_id}: {e}", exc_info=True
        )
        return jsonify(
            {"ok": False, "error": {"code": "GET_PROJECTS_FAILED", "message": str(e)}}
        ), 500


@asana_bp.route("/api/asana/sections", methods=["POST"])
async def get_sections():
    """Get sections for an Asana project"""
    data = request.get_json()
    user_id = data.get("user_id")
    project_id = data.get("project_id")
    limit = data.get("limit", 100)
    offset = data.get("offset")

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
        client = await get_asana_client(
            user_id, current_app.config["DB_CONNECTION_POOL"]
        )
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "User not authenticated with Asana.",
                    },
                }
            ), 401

        sections_result = client.get_sections(
            project_id=project_id, limit=limit, offset=offset
        )
        return jsonify({"ok": True, "data": sections_result})
    except Exception as e:
        logger.error(
            f"Error getting Asana sections for user {user_id}: {e}", exc_info=True
        )
        return jsonify(
            {"ok": False, "error": {"code": "GET_SECTIONS_FAILED", "message": str(e)}}
        ), 500


@asana_bp.route("/api/asana/teams", methods=["POST"])
async def get_teams():
    """Get teams for an Asana workspace"""
    data = request.get_json()
    user_id = data.get("user_id")
    workspace_id = data.get("workspace_id")
    limit = data.get("limit", 100)
    offset = data.get("offset")

    if not user_id or not workspace_id:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "user_id and workspace_id are required.",
                },
            }
        ), 400

    try:
        client = await get_asana_client(
            user_id, current_app.config["DB_CONNECTION_POOL"]
        )
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "User not authenticated with Asana.",
                    },
                }
            ), 401

        teams_result = client.get_teams(
            workspace_id=workspace_id, limit=limit, offset=offset
        )
        return jsonify({"ok": True, "data": teams_result})
    except Exception as e:
        logger.error(
            f"Error getting Asana teams for user {user_id}: {e}", exc_info=True
        )
        return jsonify(
            {"ok": False, "error": {"code": "GET_TEAMS_FAILED", "message": str(e)}}
        ), 500


@asana_bp.route("/api/asana/users", methods=["POST"])
async def get_users():
    """Get users for an Asana workspace"""
    data = request.get_json()
    user_id = data.get("user_id")
    workspace_id = data.get("workspace_id")
    limit = data.get("limit", 100)
    offset = data.get("offset")

    if not user_id or not workspace_id:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "user_id and workspace_id are required.",
                },
            }
        ), 400

    try:
        client = await get_asana_client(
            user_id, current_app.config["DB_CONNECTION_POOL"]
        )
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "User not authenticated with Asana.",
                    },
                }
            ), 401

        users_result = client.get_users(
            workspace_id=workspace_id, limit=limit, offset=offset
        )
        return jsonify({"ok": True, "data": users_result})
    except Exception as e:
        logger.error(
            f"Error getting Asana users for user {user_id}: {e}", exc_info=True
        )
        return jsonify(
            {"ok": False, "error": {"code": "GET_USERS_FAILED", "message": str(e)}}
        ), 500


@asana_bp.route("/api/asana/user-profile", methods=["POST"])
async def get_user_profile():
    """Get Asana user profile information"""
    data = request.get_json()
    user_id = data.get("user_id")
    target_user_id = data.get("target_user_id", "me")

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
        client = await get_asana_client(
            user_id, current_app.config["DB_CONNECTION_POOL"]
        )
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "User not authenticated with Asana.",
                    },
                }
            ), 401

        profile_result = client.get_user_profile(user_id=target_user_id)
        return jsonify({"ok": True, "data": profile_result})
    except Exception as e:
        logger.error(
            f"Error getting Asana user profile for user {user_id}: {e}", exc_info=True
        )
        return jsonify(
            {
                "ok": False,
                "error": {"code": "GET_USER_PROFILE_FAILED", "message": str(e)},
            }
        ), 500


@asana_bp.route("/api/asana/create-task", methods=["POST"])
async def create_task():
    """Create a new Asana task"""
    data = request.get_json()
    user_id = data.get("user_id")
    project_id = data.get("project_id")
    name = data.get("name")
    notes = data.get("notes", "")
    due_on = data.get("due_on")
    assignee = data.get("assignee")

    if not user_id or not project_id or not name:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "user_id, project_id, and name are required.",
                },
            }
        ), 400

    try:
        client = await get_asana_client(
            user_id, current_app.config["DB_CONNECTION_POOL"]
        )
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "User not authenticated with Asana.",
                    },
                }
            ), 401

        task_result = client.create_task(
            project_id=project_id,
            name=name,
            notes=notes,
            due_on=due_on,
            assignee=assignee,
        )
        return jsonify({"ok": True, "data": task_result})
    except Exception as e:
        logger.error(
            f"Error creating Asana task for user {user_id}: {e}", exc_info=True
        )
        return jsonify(
            {"ok": False, "error": {"code": "CREATE_TASK_FAILED", "message": str(e)}}
        ), 500


@asana_bp.route("/api/asana/update-task", methods=["POST"])
async def update_task():
    """Update an existing Asana task"""
    data = request.get_json()
    user_id = data.get("user_id")
    task_id = data.get("task_id")
    name = data.get("name")
    notes = data.get("notes")
    due_on = data.get("due_on")
    completed = data.get("completed")

    if not user_id or not task_id:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "user_id and task_id are required.",
                },
            }
        ), 400

    try:
        client = await get_asana_client(
            user_id, current_app.config["DB_CONNECTION_POOL"]
        )
        if not client:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "User not authenticated with Asana.",
                    },
                }
            ), 401

        update_result = client.update_task(
            task_id=task_id, name=name, notes=notes, due_on=due_on, completed=completed
        )
        return jsonify({"ok": True, "data": update_result})
    except Exception as e:
        logger.error(
            f"Error updating Asana task for user {user_id}: {e}", exc_info=True
        )
        return jsonify(
            {"ok": False, "error": {"code": "UPDATE_TASK_FAILED", "message": str(e)}}
        ), 500
