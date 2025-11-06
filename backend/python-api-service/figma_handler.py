"""
Figma API Handler
RESTful API endpoints for Figma integration
"""

import logging
import asyncio
from flask import Blueprint, request, jsonify, current_app
from typing import Dict, Any, Optional
from datetime import datetime

# Import Figma service
try:
    from figma_service_real import figma_service, FigmaFile, FigmaTeam, FigmaProject, FigmaUser, FigmaComponent
    FIGMA_SERVICE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Figma service not available: {e}")
    FIGMA_SERVICE_AVAILABLE = False
    figma_service = None

# Import database handlers
try:
    import db_oauth_figma
    FIGMA_DB_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Figma database handler not available: {e}")
    FIGMA_DB_AVAILABLE = False

logger = logging.getLogger(__name__)

# Create blueprint
figma_bp = Blueprint("figma_bp", __name__)


async def get_figma_service_for_user(user_id: str):
    """Get Figma service instance for user"""
    if not FIGMA_SERVICE_AVAILABLE:
        return None
    
    # In real implementation, get user's access token from database
    if FIGMA_DB_AVAILABLE:
        try:
            # This would be async in real implementation
            tokens = db_oauth_figma.get_tokens(None, user_id)  # db_conn_pool would be passed
            if tokens:
                access_token = tokens[0]  # First token is access token
                from figma_service_real import FigmaService
                return FigmaService(access_token)
        except Exception as e:
            logger.error(f"Error getting Figma tokens: {e}")
    
    # Return mock service for testing
    from figma_service_real import MockFigmaService
    return MockFigmaService()


@figma_bp.route("/api/figma/health", methods=["GET"])
def figma_health():
    """Figma integration health check"""
    return jsonify({
        "ok": True,
        "service": "figma",
        "status": "registered",
        "message": "Figma integration is registered and ready for OAuth configuration",
        "needs_oauth": True,
        "service_available": FIGMA_SERVICE_AVAILABLE,
        "database_available": FIGMA_DB_AVAILABLE
    })


@figma_bp.route("/api/figma/files", methods=["GET"])
async def list_files():
    """List user's Figma files"""
    try:
        user_id = request.args.get("user_id")
        team_id = request.args.get("team_id")
        include_archived = request.args.get("include_archived", "false").lower() == "true"
        limit = int(request.args.get("limit", 50))
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": {"code": "VALIDATION_ERROR", "message": "user_id is required"}
            }), 400
        
        # Get Figma service for user
        figma_svc = await get_figma_service_for_user(user_id)
        if not figma_svc:
            return jsonify({
                "ok": False,
                "error": {"code": "SERVICE_ERROR", "message": "Figma service not available"}
            }), 503
        
        # Get files
        if team_id:
            # Get team projects first, then files
            projects = await figma_svc.get_team_projects(user_id, team_id)
            all_files = []
            for project in projects:
                project_files = await figma_svc.get_user_files(user_id, team_id, include_archived, limit)
                all_files.extend(project_files)
            files = all_files[:limit] if limit > 0 else all_files
        else:
            files = await figma_svc.get_user_files(user_id, team_id, include_archived, limit)
        
        # Convert to response format
        files_data = []
        for file in files:
            files_data.append({
                "id": file.key,
                "name": file.name,
                "key": file.key,
                "thumbnail_url": file.thumbnail_url,
                "last_modified": file.last_modified,
                "workspace_id": file.workspace_id,
                "workspace_name": file.workspace_name,
                "file_id": file.file_id,
                "branch_id": file.branch_id,
                "content_readonly": file.content_readonly,
                "editor_type": file.editor_type
            })
        
        return jsonify({
            "ok": True,
            "files": files_data,
            "total_count": len(files_data),
            "team_id": team_id
        })
        
    except Exception as e:
        logger.error(f"Error listing Figma files: {e}")
        return jsonify({
            "ok": False,
            "error": {"code": "LIST_FILES_FAILED", "message": str(e)}
        }), 500


@figma_bp.route("/api/figma/projects", methods=["GET"])
async def list_projects():
    """List Figma projects"""
    try:
        user_id = request.args.get("user_id")
        team_id = request.args.get("team_id")
        limit = int(request.args.get("limit", 50))
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": {"code": "VALIDATION_ERROR", "message": "user_id is required"}
            }), 400
        
        if not team_id:
            return jsonify({
                "ok": False,
                "error": {"code": "VALIDATION_ERROR", "message": "team_id is required"}
            }), 400
        
        # Get Figma service for user
        figma_svc = await get_figma_service_for_user(user_id)
        if not figma_svc:
            return jsonify({
                "ok": False,
                "error": {"code": "SERVICE_ERROR", "message": "Figma service not available"}
            }), 503
        
        # Get projects
        projects = await figma_svc.get_team_projects(user_id, team_id, limit)
        
        # Convert to response format
        projects_data = []
        for project in projects:
            projects_data.append({
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "team_id": project.team_id,
                "team_name": project.team_name,
                "files_count": len(project.files) if project.files else 0
            })
        
        return jsonify({
            "ok": True,
            "projects": projects_data,
            "total_count": len(projects_data),
            "team_id": team_id
        })
        
    except Exception as e:
        logger.error(f"Error listing Figma projects: {e}")
        return jsonify({
            "ok": False,
            "error": {"code": "LIST_PROJECTS_FAILED", "message": str(e)}
        }), 500


@figma_bp.route("/api/figma/teams", methods=["GET"])
async def list_teams():
    """List user's Figma teams"""
    try:
        user_id = request.args.get("user_id")
        limit = int(request.args.get("limit", 50))
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": {"code": "VALIDATION_ERROR", "message": "user_id is required"}
            }), 400
        
        # Get Figma service for user
        figma_svc = await get_figma_service_for_user(user_id)
        if not figma_svc:
            return jsonify({
                "ok": False,
                "error": {"code": "SERVICE_ERROR", "message": "Figma service not available"}
            }), 503
        
        # Get teams
        teams = await figma_svc.get_user_teams(user_id, limit)
        
        # Convert to response format
        teams_data = []
        for team in teams:
            teams_data.append({
                "id": team.id,
                "name": team.name,
                "description": team.description,
                "profile_picture_url": team.profile_picture_url,
                "members_count": len(team.users) if team.users else 0,
                "members": [
                    {
                        "id": user.id,
                        "name": user.name,
                        "username": user.username,
                        "email": user.email,
                        "profile_picture_url": user.profile_picture_url,
                        "role": user.role,
                        "can_edit": user.can_edit,
                        "is_active": user.is_active
                    }
                    for user in (team.users or [])
                ]
            })
        
        return jsonify({
            "ok": True,
            "teams": teams_data,
            "total_count": len(teams_data)
        })
        
    except Exception as e:
        logger.error(f"Error listing Figma teams: {e}")
        return jsonify({
            "ok": False,
            "error": {"code": "LIST_TEAMS_FAILED", "message": str(e)}
        }), 500


@figma_bp.route("/api/figma/users", methods=["GET"])
async def list_users():
    """List users in a team (placeholder)"""
    try:
        user_id = request.args.get("user_id")
        team_id = request.args.get("team_id")
        limit = int(request.args.get("limit", 50))
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": {"code": "VALIDATION_ERROR", "message": "user_id is required"}
            }), 400
        
        # For now, return users from team endpoint
        if team_id:
            # Redirect to teams endpoint with team_id
            figma_svc = await get_figma_service_for_user(user_id)
            if not figma_svc:
                return jsonify({
                    "ok": False,
                    "error": {"code": "SERVICE_ERROR", "message": "Figma service not available"}
                }), 503
            
            teams = await figma_svc.get_user_teams(user_id, limit)
            
            # Find the specific team
            team_users = []
            for team in teams:
                if team.id == team_id and team.users:
                    team_users = team.users
                    break
            
            users_data = []
            for user in team_users:
                users_data.append({
                    "id": user.id,
                    "name": user.name,
                    "username": user.username,
                    "email": user.email,
                    "profile_picture_url": user.profile_picture_url,
                    "role": user.role,
                    "can_edit": user.can_edit,
                    "is_active": user.is_active
                })
            
            return jsonify({
                "ok": True,
                "users": users_data,
                "total_count": len(users_data),
                "team_id": team_id
            })
        else:
            # List all users across teams
            figma_svc = await get_figma_service_for_user(user_id)
            if not figma_svc:
                return jsonify({
                    "ok": False,
                    "error": {"code": "SERVICE_ERROR", "message": "Figma service not available"}
                }), 503
            
            teams = await figma_svc.get_user_teams(user_id, limit)
            all_users = []
            seen_users = set()
            
            for team in teams:
                for user in (team.users or []):
                    if user.id not in seen_users:
                        all_users.append(user)
                        seen_users.add(user.id)
            
            users_data = []
            for user in all_users:
                users_data.append({
                    "id": user.id,
                    "name": user.name,
                    "username": user.username,
                    "email": user.email,
                    "profile_picture_url": user.profile_picture_url,
                    "role": user.role,
                    "can_edit": user.can_edit,
                    "is_active": user.is_active
                })
            
            return jsonify({
                "ok": True,
                "users": users_data,
                "total_count": len(users_data)
            })
        
    except Exception as e:
        logger.error(f"Error listing Figma users: {e}")
        return jsonify({
            "ok": False,
            "error": {"code": "LIST_USERS_FAILED", "message": str(e)}
        }), 500


@figma_bp.route("/api/figma/users/profile", methods=["GET"])
async def get_user_profile():
    """Get user profile"""
    try:
        user_id = request.args.get("user_id")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": {"code": "VALIDATION_ERROR", "message": "user_id is required"}
            }), 400
        
        # Get Figma service for user
        figma_svc = await get_figma_service_for_user(user_id)
        if not figma_svc:
            return jsonify({
                "ok": False,
                "error": {"code": "SERVICE_ERROR", "message": "Figma service not available"}
            }), 503
        
        # Get user profile
        user = await figma_svc.get_user_profile(user_id)
        
        if not user:
            return jsonify({
                "ok": False,
                "error": {"code": "USER_NOT_FOUND", "message": "User profile not found"}
            }), 404
        
        return jsonify({
            "ok": True,
            "user": {
                "id": user.id,
                "name": user.name,
                "username": user.username,
                "email": user.email,
                "profile_picture_url": user.profile_picture_url,
                "role": user.role,
                "organization_id": user.organization_id,
                "can_edit": user.can_edit,
                "is_active": user.is_active
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting Figma user profile: {e}")
        return jsonify({
            "ok": False,
            "error": {"code": "GET_USER_PROFILE_FAILED", "message": str(e)}
        }), 500


@figma_bp.route("/api/figma/components", methods=["GET"])
async def list_components():
    """List components from a file"""
    try:
        user_id = request.args.get("user_id")
        file_key = request.args.get("file_key")
        limit = int(request.args.get("limit", 100))
        
        if not user_id or not file_key:
            return jsonify({
                "ok": False,
                "error": {"code": "VALIDATION_ERROR", "message": "user_id and file_key are required"}
            }), 400
        
        # Get Figma service for user
        figma_svc = await get_figma_service_for_user(user_id)
        if not figma_svc:
            return jsonify({
                "ok": False,
                "error": {"code": "SERVICE_ERROR", "message": "Figma service not available"}
            }), 503
        
        # Get components
        components = await figma_svc.get_file_components(user_id, file_key, limit)
        
        # Convert to response format
        components_data = []
        for component in components:
            components_data.append({
                "id": component.key,
                "key": component.key,
                "file_key": component.file_key,
                "node_id": component.node_id,
                "name": component.name,
                "description": component.description,
                "component_type": component.component_type,
                "thumbnail_url": component.thumbnail_url,
                "created_at": component.created_at,
                "modified_at": component.modified_at,
                "creator_id": component.creator_id
            })
        
        return jsonify({
            "ok": True,
            "components": components_data,
            "total_count": len(components_data),
            "file_key": file_key
        })
        
    except Exception as e:
        logger.error(f"Error listing Figma components: {e}")
        return jsonify({
            "ok": False,
            "error": {"code": "LIST_COMPONENTS_FAILED", "message": str(e)}
        }), 500


@figma_bp.route("/api/figma/styles", methods=["GET"])
async def list_styles():
    """List styles from a file (placeholder)"""
    try:
        user_id = request.args.get("user_id")
        file_key = request.args.get("file_key")
        limit = int(request.args.get("limit", 100))
        
        if not user_id or not file_key:
            return jsonify({
                "ok": False,
                "error": {"code": "VALIDATION_ERROR", "message": "user_id and file_key are required"}
            }), 400
        
        # For now, return mock styles data
        mock_styles = [
            {
                "id": "style-1",
                "name": "Primary Color",
                "file_key": file_key,
                "style_type": "color",
                "description": "Primary brand color",
                "value": "#3B82F6",
                "created_at": "2023-01-01T00:00:00Z",
                "modified_at": "2023-06-15T10:30:00Z"
            },
            {
                "id": "style-2",
                "name": "Heading Font",
                "file_key": file_key,
                "style_type": "text",
                "description": "Main heading typography",
                "value": {
                    "fontFamily": "Inter",
                    "fontSize": "24px",
                    "fontWeight": "700"
                },
                "created_at": "2023-01-01T00:00:00Z",
                "modified_at": "2023-06-15T10:30:00Z"
            }
        ]
        
        return jsonify({
            "ok": True,
            "styles": mock_styles[:limit] if limit > 0 else mock_styles,
            "total_count": len(mock_styles),
            "file_key": file_key,
            "message": "Mock data - real styles API would be implemented here"
        })
        
    except Exception as e:
        logger.error(f"Error listing Figma styles: {e}")
        return jsonify({
            "ok": False,
            "error": {"code": "LIST_STYLES_FAILED", "message": str(e)}
        }), 500


@figma_bp.route("/api/figma/search", methods=["POST"])
async def search_figma():
    """Search across Figma files and components"""
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id")
        query = data.get("query")
        search_type = data.get("search_type", "global")
        limit = int(data.get("limit", 50))
        
        if not user_id or not query:
            return jsonify({
                "ok": False,
                "error": {"code": "VALIDATION_ERROR", "message": "user_id and query are required"}
            }), 400
        
        # Get Figma service for user
        figma_svc = await get_figma_service_for_user(user_id)
        if not figma_svc:
            return jsonify({
                "ok": False,
                "error": {"code": "SERVICE_ERROR", "message": "Figma service not available"}
            }), 503
        
        # Perform search
        result = await figma_svc.search_figma(user_id, query, search_type, limit)
        
        if result.get("ok"):
            return jsonify({
                "ok": True,
                "results": result.get("results", []),
                "total_count": result.get("total_count", 0),
                "query": query,
                "search_type": search_type
            })
        else:
            return jsonify({
                "ok": False,
                "error": {"code": "SEARCH_FAILED", "message": result.get("error", "Search failed")}
            }), 500
        
    except Exception as e:
        logger.error(f"Error searching Figma: {e}")
        return jsonify({
            "ok": False,
            "error": {"code": "SEARCH_FAILED", "message": str(e)}
        }), 500


@figma_bp.route("/api/figma/comments", methods=["POST"])
async def add_comment():
    """Add comment to a file"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        file_key = data.get("file_key")
        comment = data.get("comment")
        position = data.get("position")
        
        if not all([user_id, file_key, comment]):
            return jsonify({
                "ok": False,
                "error": {"code": "VALIDATION_ERROR", "message": "user_id, file_key, and comment are required"}
            }), 400
        
        # For now, return mock success
        mock_comment = {
            "id": f"comment_{datetime.now().timestamp()}",
            "file_key": file_key,
            "message": comment,
            "user_id": user_id,
            "position": position,
            "created_at": datetime.now().isoformat(),
            "client_meta": {"x_fig_atom": "integration"}
        }
        
        return jsonify({
            "ok": True,
            "comment": mock_comment,
            "message": "Comment added successfully (mock implementation)"
        })
        
    except Exception as e:
        logger.error(f"Error adding Figma comment: {e}")
        return jsonify({
            "ok": False,
            "error": {"code": "ADD_COMMENT_FAILED", "message": str(e)}
        }), 500


@figma_bp.route("/api/figma/versions", methods=["GET"])
async def get_file_versions():
    """Get file version history"""
    try:
        user_id = request.args.get("user_id")
        file_key = request.args.get("file_key")
        limit = int(request.args.get("limit", 20))
        
        if not user_id or not file_key:
            return jsonify({
                "ok": False,
                "error": {"code": "VALIDATION_ERROR", "message": "user_id and file_key are required"}
            }), 400
        
        # For now, return mock version data
        mock_versions = [
            {
                "id": "version-3",
                "label": "Latest",
                "description": "Current version with final designs",
                "created_at": "2023-06-15T10:30:00Z",
                "created_by": {"id": "user-1", "name": "Alice Designer"},
                "thumbnail_url": "https://example.com/version3.png"
            },
            {
                "id": "version-2",
                "label": "Review",
                "description": "Version for design review",
                "created_at": "2023-06-14T15:45:00Z",
                "created_by": {"id": "user-2", "name": "Bob Designer"},
                "thumbnail_url": "https://example.com/version2.png"
            },
            {
                "id": "version-1",
                "label": "Initial",
                "description": "Initial design version",
                "created_at": "2023-06-13T09:20:00Z",
                "created_by": {"id": "user-1", "name": "Alice Designer"},
                "thumbnail_url": "https://example.com/version1.png"
            }
        ]
        
        return jsonify({
            "ok": True,
            "versions": mock_versions[:limit] if limit > 0 else mock_versions,
            "total_count": len(mock_versions),
            "file_key": file_key,
            "message": "Mock data - real versions API would be implemented here"
        })
        
    except Exception as e:
        logger.error(f"Error getting Figma file versions: {e}")
        return jsonify({
            "ok": False,
            "error": {"code": "GET_VERSIONS_FAILED", "message": str(e)}
        }), 500


@figma_bp.route("/api/figma/export", methods=["POST"])
async def export_file():
    """Export file in specified format"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        file_key = data.get("file_key")
        format_type = data.get("format", "png")
        
        if not user_id or not file_key:
            return jsonify({
                "ok": False,
                "error": {"code": "VALIDATION_ERROR", "message": "user_id and file_key are required"}
            }), 400
        
        # For now, return mock export URL
        export_url = f"https://example.com/exports/{file_key}.{format_type}"
        
        return jsonify({
            "ok": True,
            "export_url": export_url,
            "format": format_type,
            "file_key": file_key,
            "message": "Export URL generated (mock implementation)"
        })
        
    except Exception as e:
        logger.error(f"Error exporting Figma file: {e}")
        return jsonify({
            "ok": False,
            "error": {"code": "EXPORT_FAILED", "message": str(e)}
        }), 500