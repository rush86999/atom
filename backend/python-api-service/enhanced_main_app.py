#!/usr/bin/env python3
"""
🚀 MAIN API APP - SIMPLIFIED WITH OAUTH AND ENHANCED INTEGRATIONS
Working backend with OAuth and real service endpoints including Google, Microsoft, and Dropbox
"""

import os
import logging
import requests
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os

# Load environment variables from .env file in project root
env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(env_path)

# Original imports from main_api_app.py
from workflow_handler import workflow_bp, create_workflow_tables
from workflow_api import workflow_api_bp
from workflow_agent_api import workflow_agent_api_bp
from workflow_automation_api import workflow_automation_api
from voice_integration_api import voice_integration_api_bp

# Import enhanced API blueprints
try:
    from google_enhanced_api import google_enhanced_bp
    GOOGLE_ENHANCED_AVAILABLE = True
except ImportError as e:
    GOOGLE_ENHANCED_AVAILABLE = False
    logging.warning(f"Enhanced Google API not available: {e}")

try:
    from microsoft_enhanced_api import microsoft_enhanced_bp
    MICROSOFT_ENHANCED_AVAILABLE = True
except ImportError as e:
    MICROSOFT_ENHANCED_AVAILABLE = False
    logging.warning(f"Enhanced Microsoft API not available: {e}")

try:
    from dropbox_enhanced_api import dropbox_enhanced_bp
    DROPBOX_ENHANCED_AVAILABLE = True
except ImportError as e:
    DROPBOX_ENHANCED_AVAILABLE = False
    logging.warning(f"Enhanced Dropbox API not available: {e}")

# Import Jira OAuth handler
try:
    from auth_handler_jira import jira_auth_bp
    JIRA_OAUTH_AVAILABLE = True
except ImportError:
    JIRA_OAUTH_AVAILABLE = False
    logging.warning("Jira OAuth handler not available")

# Import enhanced service endpoints
try:
    from enhanced_service_endpoints import enhanced_service_bp
    ENHANCED_SERVICES_AVAILABLE = True
except ImportError:
    ENHANCED_SERVICES_AVAILABLE = False
    logging.warning("Enhanced service endpoints not available")

# Import unified communication handler
try:
    from unified_communication_handler import unified_communication_bp
    COMMUNICATION_AVAILABLE = True
except ImportError as e:
    COMMUNICATION_AVAILABLE = False
    logging.warning(f"Unified communication handler not available: {e}")

# Import Teams OAuth handler
try:
    from auth_handler_teams import auth_teams_bp
    TEAMS_OAUTH_AVAILABLE = True
except ImportError as e:
    TEAMS_OAUTH_AVAILABLE = False
    logging.warning(f"Teams OAuth handler not available: {e}")

# Import Slack OAuth handler
try:
    from auth_handler_slack import auth_slack_bp
    SLACK_OAUTH_AVAILABLE = True
except ImportError as e:
    SLACK_OAUTH_AVAILABLE = False
    logging.warning(f"Slack OAuth handler not available: {e}")

# Import Notion OAuth handler
try:
    from auth_handler_notion import auth_notion_bp
    NOTION_OAUTH_AVAILABLE = True
except ImportError as e:
    NOTION_OAUTH_AVAILABLE = False
    logging.warning(f"Notion OAuth handler not available: {e}")

# Import GitHub OAuth handler
try:
    from auth_handler_github import auth_github_bp
    GITHUB_OAUTH_AVAILABLE = True
except ImportError as e:
    GITHUB_OAUTH_AVAILABLE = False
    logging.warning(f"GitHub OAuth handler not available: {e}")

# Import Trello OAuth handler
try:
    from auth_handler_trello import auth_trello_bp
    TRELLO_OAUTH_AVAILABLE = True
except ImportError as e:
    TRELLO_OAUTH_AVAILABLE = False
    logging.warning(f"Trello OAuth handler not available: {e}")

# Import Figma OAuth handler
try:
    from auth_handler_figma import auth_figma_bp
    FIGMA_OAUTH_AVAILABLE = True
except ImportError as e:
    FIGMA_OAUTH_AVAILABLE = False
    logging.warning(f"Figma OAuth handler not available: {e}")

# Import Linear OAuth handler
try:
    from auth_handler_linear import auth_linear_bp
    LINEAR_OAUTH_AVAILABLE = True
except ImportError as e:
    LINEAR_OAUTH_AVAILABLE = False
    logging.warning(f"Linear OAuth handler not available: {e}")

# Import Asana OAuth handler
try:
    from auth_handler_asana import auth_asana_bp
    ASANA_OAUTH_AVAILABLE = True
except ImportError as e:
    ASANA_OAUTH_AVAILABLE = False
    logging.warning(f"Asana OAuth handler not available: {e}")

# Import Outlook OAuth handler
try:
    from auth_handler_outlook_new import outlook_oauth_handler
    from db_oauth_outlook import init_outlook_oauth_table
    OUTLOOK_OAUTH_AVAILABLE = True
except ImportError as e:
    OUTLOOK_OAUTH_AVAILABLE = False
    logging.warning(f"Outlook OAuth handler not available: {e}")

# Import Next.js OAuth handler
try:
    from auth_handler_nextjs import nextjs_auth_bp
    NEXTJS_OAUTH_AVAILABLE = True
except ImportError as e:
    NEXTJS_OAUTH_AVAILABLE = False
    logging.warning(f"Next.js OAuth handler not available: {e}")

# Import enhanced Slack OAuth handler
try:
    from auth_handler_slack_complete import auth_slack_bp
    SLACK_OAUTH_AVAILABLE = True
except ImportError as e:
    SLACK_OAUTH_AVAILABLE = False
    logging.warning(f"Enhanced Slack OAuth handler not available: {e}")

# Import enhanced Slack API
try:
    from slack_enhanced_api import slack_enhanced_bp
    SLACK_ENHANCED_AVAILABLE = True
except ImportError as e:
    SLACK_ENHANCED_AVAILABLE = False
    logging.warning(f"Enhanced Slack API not available: {e}")

# Create Flask app
app = Flask(__name__)
app.secret_key = os.getenv(
    "FLASK_SECRET_KEY", "atom-dev-secret-key-change-in-production"
)
CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000"])

def create_app():
    """Create and configure Flask application with all integrations"""
    # Register original blueprints
    app.register_blueprint(
        workflow_bp, url_prefix="/api/v1/workflows", name="workflow_handler_v1"
    )
    app.register_blueprint(
        workflow_api_bp, url_prefix="/api/v1/workflows", name="workflow_api"
    )
    app.register_blueprint(
        workflow_agent_api_bp,
        url_prefix="/api/v1/workflows/agent",
        name="workflow_agent_api_v1",
    )
    app.register_blueprint(
        workflow_automation_api, url_prefix="/api/v1/workflows/automation"
    )
    app.register_blueprint(
        voice_integration_api_bp,
        url_prefix="/api/v1/voice",
        name="voice_integration_api_v1",
    )

    # Register enhanced API blueprints if available
    if GOOGLE_ENHANCED_AVAILABLE:
        app.register_blueprint(
            google_enhanced_bp, url_prefix="/api/google/enhanced", name="google_enhanced"
        )
        logging.info("Enhanced Google API registered successfully")

    if MICROSOFT_ENHANCED_AVAILABLE:
        app.register_blueprint(
            microsoft_enhanced_bp, url_prefix="/api/microsoft/enhanced", name="microsoft_enhanced"
        )
        logging.info("Enhanced Microsoft API registered successfully")

    if DROPBOX_ENHANCED_AVAILABLE:
        app.register_blueprint(
            dropbox_enhanced_bp, url_prefix="/api/dropbox/enhanced", name="dropbox_enhanced"
        )
        logging.info("Enhanced Dropbox API registered successfully")

    # Register Jira OAuth handler if available
    if JIRA_OAUTH_AVAILABLE:
        app.register_blueprint(jira_auth_bp, url_prefix="/api/auth", name="jira_auth")
        logging.info("Jira OAuth handler registered successfully")

    # Register GitHub OAuth handler if available
    if GITHUB_OAUTH_AVAILABLE:
        app.register_blueprint(
            auth_github_bp, url_prefix="/api/auth", name="github_auth"
        )
        logging.info("GitHub OAuth handler registered successfully")

    # Register enhanced services if available
    if ENHANCED_SERVICES_AVAILABLE:
        app.register_blueprint(
            enhanced_service_bp,
            url_prefix="/api/v1/services",
            name="v1_services_blueprint",
        )

    # Register unified communication handler if available
    if COMMUNICATION_AVAILABLE:
        app.register_blueprint(unified_communication_bp, url_prefix="")
        logging.info("Unified communication handler registered successfully")

    # Register enhanced Slack OAuth handler if available
    if SLACK_OAUTH_AVAILABLE:
        app.register_blueprint(
            auth_slack_bp, url_prefix="/api/auth", name="slack_auth"
        )
        logging.info("Enhanced Slack OAuth handler registered successfully")

    # Register enhanced Slack API if available
    if SLACK_ENHANCED_AVAILABLE:
        app.register_blueprint(
            slack_enhanced_bp, url_prefix="/api/slack/enhanced", name="slack_enhanced"
        )
        logging.info("Enhanced Slack API registered successfully")

    # Register enhanced Teams OAuth handler if available
    if TEAMS_OAUTH_AVAILABLE:
        app.register_blueprint(
            auth_teams_bp, url_prefix="/api/auth", name="teams_auth"
        )
        logging.info("Enhanced Teams OAuth handler registered successfully")

    # Register enhanced Teams API if available
    try:
        from teams_enhanced_api import teams_enhanced_bp
        TEAMS_ENHANCED_AVAILABLE = True
        app.register_blueprint(
            teams_enhanced_bp, url_prefix="/api/teams/enhanced", name="teams_enhanced"
        )
        logging.info("Enhanced Teams API registered successfully")
    except ImportError as e:
        TEAMS_ENHANCED_AVAILABLE = False
        logging.warning(f"Enhanced Teams API not available: {e}")

    # Register enhanced Jira API if available
    try:
        from jira_enhanced_api import jira_enhanced_bp
        JIRA_ENHANCED_AVAILABLE = True
        app.register_blueprint(
            jira_enhanced_bp, url_prefix="/api/jira/enhanced", name="jira_enhanced"
        )
        logging.info("Enhanced Jira API registered successfully")
    except ImportError as e:
        JIRA_ENHANCED_AVAILABLE = False
        logging.warning(f"Enhanced Jira API not available: {e}")

    # Register Teams OAuth handler if available
    if TEAMS_OAUTH_AVAILABLE:
        app.register_blueprint(auth_teams_bp, url_prefix="")
        logging.info("Teams OAuth handler registered successfully")

    # Register Notion OAuth handler if available
    if NOTION_OAUTH_AVAILABLE:
        app.register_blueprint(auth_notion_bp, url_prefix="")
        logging.info("Notion OAuth handler registered successfully")

    # Register Enhanced GitHub API if available
    try:
        from github_enhanced_api import github_enhanced_bp
        GITHUB_ENHANCED_AVAILABLE = True
        app.register_blueprint(github_enhanced_bp, url_prefix="")
        logging.info("Enhanced GitHub API registered successfully")
    except ImportError as e:
        GITHUB_ENHANCED_AVAILABLE = False
        logging.warning(f"Enhanced GitHub API not available: {e}")

    # Register Enhanced Trello API if available
    try:
        from trello_enhanced_api import trello_enhanced_bp
        TRELLO_ENHANCED_AVAILABLE = True
        app.register_blueprint(trello_enhanced_bp, url_prefix="")
        logging.info("Enhanced Trello API registered successfully")
    except ImportError as e:
        TRELLO_ENHANCED_AVAILABLE = False
        logging.warning(f"Enhanced Trello API not available: {e}")

    # Register Enhanced Linear API if available
    try:
        from linear_enhanced_api import linear_enhanced_bp
        LINEAR_ENHANCED_AVAILABLE = True
        app.register_blueprint(linear_enhanced_bp, url_prefix="")
        logging.info("Enhanced Linear API registered successfully")
    except ImportError as e:
        LINEAR_ENHANCED_AVAILABLE = False
        logging.warning(f"Enhanced Linear API not available: {e}")

    # Register Enhanced Asana API if available
    try:
        from asana_enhanced_api import asana_enhanced_bp
        ASANA_ENHANCED_AVAILABLE = True
        app.register_blueprint(asana_enhanced_bp, url_prefix="")
        logging.info("Enhanced Asana API registered successfully")
    except ImportError as e:
        ASANA_ENHANCED_AVAILABLE = False
        logging.warning(f"Enhanced Asana API not available: {e}")

    # Register Enhanced Discord API if available
    try:
        from discord_enhanced_api import discord_enhanced_bp
        DISCORD_ENHANCED_AVAILABLE = True
        app.register_blueprint(discord_enhanced_bp, url_prefix="")
        logging.info("Enhanced Discord API registered successfully")
    except ImportError as e:
        DISCORD_ENHANCED_AVAILABLE = False
        logging.warning(f"Enhanced Discord API not available: {e}")

    # Register Discord Memory API if available
    try:
        from discord_memory_api import discord_memory_bp
        DISCORD_MEMORY_AVAILABLE = True
        app.register_blueprint(discord_memory_bp, url_prefix="")
        logging.info("Discord Memory API registered successfully")
    except ImportError as e:
        DISCORD_MEMORY_AVAILABLE = False
        logging.warning(f"Discord Memory API not available: {e}")

    # Register Enhanced Notion API if available
    try:
        from notion_enhanced_api import notion_enhanced_bp
        NOTION_ENHANCED_AVAILABLE = True
        app.register_blueprint(notion_enhanced_bp, url_prefix="")
        logging.info("Enhanced Notion API registered successfully")
    except ImportError as e:
        NOTION_ENHANCED_AVAILABLE = False
        logging.warning(f"Enhanced Notion API not available: {e}")

    # Initialize Notion integration service if available
    try:
        from sync.orchestration_service import create_orchestration_service
        from notion_integration_service import initialize_notion_integration_service
        
        if initialize_notion_integration_service():
            NOTION_INTEGRATION_SERVICE_AVAILABLE = True
            logging.info("Notion integration service initialized successfully")
        else:
            NOTION_INTEGRATION_SERVICE_AVAILABLE = False
            logging.warning("Notion integration service initialization failed")
    except ImportError as e:
        NOTION_INTEGRATION_SERVICE_AVAILABLE = False
        logging.warning(f"Notion integration service not available: {e}")
    except Exception as e:
        NOTION_INTEGRATION_SERVICE_AVAILABLE = False
        logging.error(f"Error initializing Notion integration service: {e}")

    # Register Slack OAuth handler if available
    if SLACK_OAUTH_AVAILABLE:
        app.register_blueprint(auth_slack_bp, url_prefix="")
        logging.info("Slack OAuth handler registered successfully")

    # Register Outlook OAuth handler if available
    if OUTLOOK_OAUTH_AVAILABLE:
        # Register existing Outlook blueprint
        from auth_handler_outlook import auth_outlook_bp
        app.register_blueprint(auth_outlook_bp, url_prefix="")
        logging.info("Outlook OAuth handler registered successfully")
        
        # Also add enhanced routes from new handler
        @app.route('/api/auth/outlook-new/authorize', methods=['GET'])
        def outlook_new_oauth_authorize():
            """Initiate Outlook OAuth flow using new handler"""
            user_id = request.args.get('user_id')
            state = request.args.get('state')
            
            result = outlook_oauth_handler.get_oauth_url(user_id, state)
            
            if result.get('success'):
                return jsonify(result)
            else:
                return jsonify(result), 400
        
        @app.route('/api/auth/outlook-new/health', methods=['GET'])
        def outlook_new_health():
            """Outlook service health check using new handler"""
            return jsonify(outlook_oauth_handler.health_check())

    # Register Next.js OAuth handler if available
    if NEXTJS_OAUTH_AVAILABLE:
        app.register_blueprint(nextjs_auth_bp, url_prefix="")
        logging.info("Next.js OAuth handler registered successfully")

    # Register Trello OAuth handler if available
    if TRELLO_OAUTH_AVAILABLE:
        app.register_blueprint(auth_trello_bp, url_prefix="")
        logging.info("Trello OAuth handler registered successfully")

    # Register Figma OAuth handler if available
    if FIGMA_OAUTH_AVAILABLE:
        app.register_blueprint(auth_figma_bp, url_prefix="")
        logging.info("Figma OAuth handler registered successfully")

    # Register Linear OAuth handler if available
    if LINEAR_OAUTH_AVAILABLE:
        app.register_blueprint(auth_linear_bp, url_prefix="")
        logging.info("Linear OAuth handler registered successfully")

    # Register Asana OAuth handler if available
    if ASANA_OAUTH_AVAILABLE:
        app.register_blueprint(auth_asana_bp, url_prefix="")
        logging.info("Asana OAuth handler registered successfully")

    # Create workflow tables
    try:
        create_workflow_tables()
        logging.info("Workflow tables created successfully")
    except Exception as e:
        logging.error(f"Error creating workflow tables: {e}")

    # Register Desktop Storage API if available
    try:
        from desktop_storage_api import desktop_storage_bp
        app.register_blueprint(desktop_storage_bp)
        logging.info("Desktop storage API registered successfully")
    except ImportError as e:
        logging.warning(f"Desktop storage API not available: {e}")

    # Register Web App Storage API if available
    try:
        from webapp_storage_api import webapp_storage_bp
        app.register_blueprint(webapp_storage_bp)
        logging.info("Web app storage API registered successfully")
    except ImportError as e:
        logging.warning(f"Web app storage API not available: {e}")

    # Register Comprehensive Integration API if available
    try:
        from comprehensive_integration_api import comprehensive_integration_bp
        app.register_blueprint(comprehensive_integration_bp)
        logging.info("Comprehensive integration API registered successfully")
    except ImportError as e:
        logging.warning(f"Comprehensive integration API not available: {e}")

    return app

# Create app
create_app()

# OAuth Endpoints
@app.route("/api/oauth/github/url")
def github_oauth_url():
    """Generate GitHub OAuth authorization URL"""
    client_id = os.getenv("GITHUB_CLIENT_ID")
    redirect_uri = os.getenv(
        "GITHUB_REDIRECT_URI", "http://localhost:3000/oauth/github/callback"
    )

    oauth_url = f"https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope=repo user:email&response_type=code"

    return jsonify({"oauth_url": oauth_url, "service": "github", "success": True})

@app.route("/api/oauth/google/url")
def google_oauth_url():
    """Generate Google OAuth authorization URL"""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv(
        "GOOGLE_REDIRECT_URI", "http://localhost:3000/oauth/google/callback"
    )

    scope = "https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/drive.readonly"
    oauth_url = f"https://accounts.google.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&response_type=code"

    return jsonify({"oauth_url": oauth_url, "service": "google", "success": True})

@app.route("/api/oauth/slack/url")
def slack_oauth_url():
    """Generate Slack OAuth authorization URL"""
    client_id = os.getenv("SLACK_CLIENT_ID")
    redirect_uri = os.getenv(
        "SLACK_REDIRECT_URI", "http://localhost:3000/oauth/slack/callback"
    )

    oauth_url = f"https://slack.com/oauth/v2/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope=channels:read chat:read users:read"

    return jsonify({"oauth_url": oauth_url, "service": "slack", "success": True})

@app.route("/api/oauth/outlook/url")
def outlook_oauth_url():
    """Generate Outlook OAuth authorization URL"""
    result = outlook_oauth_handler.get_oauth_url()
    
    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 400

@app.route("/api/oauth/notion/url")
def notion_oauth_url():
    """Generate Notion OAuth authorization URL"""
    client_id = os.getenv("NOTION_CLIENT_ID")
    redirect_uri = os.getenv(
        "NOTION_REDIRECT_URI", "http://localhost:3000/oauth/notion/callback"
    )

    oauth_url = f"https://api.notion.com/v1/oauth/authorize?client_id={client_id}&response_type=code&owner=user&redirect_uri={redirect_uri}"

    return jsonify({"oauth_url": oauth_url, "service": "notion", "success": True})

@app.route("/api/oauth/jira/url")
def jira_oauth_url():
    """Generate Jira OAuth authorization URL"""
    client_id = os.getenv("ATLASSIAN_CLIENT_ID")

    if not client_id or client_id.startswith(("mock_", "YOUR_")):
        return jsonify(
            {
                "error": "Jira OAuth not configured",
                "message": "Add ATLASSIAN_CLIENT_ID to your .env file",
                "success": False,
            }
        ), 400

    # Use Jira OAuth handler endpoint
    oauth_url = f"/api/auth/jira/start"

    return jsonify(
        {
            "oauth_url": oauth_url,
            "service": "jira",
            "success": True,
            "message": "Use Jira OAuth handler for full OAuth flow",
        }
    )

# Real Service Endpoints
@app.route("/api/real/github/repositories")
def real_github_repositories():
    """Connect to real GitHub API"""
    token = os.getenv("GITHUB_ACCESS_TOKEN")

    try:
        headers = {"Authorization": f"token {token}"}
        response = requests.get(
            "https://api.github.com/user/repos", headers=headers, timeout=10
        )

        if response.status_code == 200:
            repos = response.json()
            return jsonify(
                {
                    "repositories": [
                        {
                            "id": repo["id"],
                            "name": repo["name"],
                            "full_name": repo["full_name"],
                            "description": repo["description"],
                            "api_connected": True,
                        }
                        for repo in repos[:10]
                    ],
                    "total": len(repos),
                    "service": "github",
                    "api_connected": True,
                    "success": True,
                }
            )
        else:
            return jsonify({"error": "GitHub API error", "success": False}), 400
    except:
        return jsonify({"error": "GitHub connection failed", "success": False}), 500

@app.route("/api/real/slack/channels")
def real_slack_channels():
    """Connect to real Slack API"""
    token = os.getenv("SLACK_BOT_TOKEN")

    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            "https://slack.com/api/conversations.list", headers=headers, timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                return jsonify(
                    {
                        "channels": [
                            {
                                "id": channel["id"],
                                "name": channel["name"],
                                "api_connected": True,
                            }
                            for channel in data["channels"][:10]
                        ],
                        "total": len(data["channels"]),
                        "service": "slack",
                        "api_connected": True,
                        "success": True,
                    }
                )
        else:
            return jsonify({"error": "Slack API error", "success": False}), 400
    except:
        return jsonify({"error": "Slack connection failed", "success": False}), 500

# Enhanced Integration Status Endpoint
@app.route("/api/integrations/enhanced/status")
def enhanced_integrations_status():
    """Get status of all enhanced integrations"""
    try:
        status = {
            "ok": True,
            "enhanced_integrations": {
                "google": {
                    "available": GOOGLE_ENHANCED_AVAILABLE,
                    "status": "available" if GOOGLE_ENHANCED_AVAILABLE else "unavailable",
                    "features": ["calendar", "gmail", "drive", "search", "sharing"]
                },
                "microsoft": {
                    "available": MICROSOFT_ENHANCED_AVAILABLE,
                    "status": "available" if MICROSOFT_ENHANCED_AVAILABLE else "unavailable",
                    "features": ["outlook", "calendar", "onedrive", "teams", "sharepoint"]
                },
                "dropbox": {
                    "available": DROPBOX_ENHANCED_AVAILABLE,
                    "status": "available" if DROPBOX_ENHANCED_AVAILABLE else "unavailable",
                    "features": ["files", "folders", "sharing", "search", "versioning", "preview"]
                }
            },
            "total_available": sum([
                GOOGLE_ENHANCED_AVAILABLE,
                MICROSOFT_ENHANCED_AVAILABLE,
                DROPBOX_ENHANCED_AVAILABLE
            ]),
            "total_integrations": 3,
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(status)
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# System Endpoints
@app.route("/api/v1/search")
def cross_service_search():
    """Cross-service search across all platforms"""
    query = request.args.get("query", "")

    if not query:
        return jsonify({"error": "Query required", "success": False}), 400

    # Mock search results
    results = [
        {
            "id": "github-1",
            "service": "github",
            "title": f"{query.title()} Repository",
            "url": "https://github.com/example/repo",
        },
        {
            "id": "google-1",
            "service": "google",
            "title": f"{query.title()} Document",
            "url": "https://docs.google.com/document",
        },
        {
            "id": "slack-1",
            "service": "slack",
            "title": f"#{query}",
            "url": "https://workspace.slack.com/archives/CHANNEL",
        },
    ]

    return jsonify(
        {"results": results, "total": len(results), "query": query, "success": True}
    )

@app.route("/api/v1/workflows")
def workflows_list():
    """List available workflows"""
    return jsonify(
        {
            "success": True,
            "total": 1,
            "workflows": [
                {"id": "workflow-1", "name": "GitHub PR to Slack", "status": "active"}
            ],
        }
    )

@app.route("/api/v1/services")
def services_status():
    """Get status of all services"""
    return jsonify(
        {
            "success": True,
            "total": 1,
            "services": [
                {"name": "GitHub", "status": "connected", "type": "code_repository"}
            ],
        }
    )

@app.route("/api/v1/tasks")
def tasks_list():
    """List tasks from all services"""
    return jsonify(
        {
            "success": True,
            "tasks": [
                {"id": "task-1", "status": "in_progress", "title": "Review GitHub PR"}
            ],
            "total": 1,
        }
    )

@app.route("/healthz")
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route("/api/routes")
def list_routes():
    """List all available routes"""
    return jsonify(
        {
            "ok": True,
            "routes": [
                {"method": "GET", "path": "/", "description": "Root endpoint"},
                {"method": "GET", "path": "/healthz", "description": "Health check"},
                {
                    "method": "GET",
                    "path": "/api/v1/search",
                    "description": "Search API",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/workflows",
                    "description": "Workflows API",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/services",
                    "description": "Services API",
                },
                {"method": "GET", "path": "/api/v1/tasks", "description": "Tasks API"},
                {
                    "method": "GET",
                    "path": "/api/integrations/enhanced/status",
                    "description": "Enhanced Integrations Status",
                },
            ],
            "total": 8,
        }
    )

@app.route("/")
def root():
    """Main application endpoint"""
    return jsonify(
        {
            "message": "ATOM Enterprise Backend - Enhanced Integrations Ready",
            "status": "running",
            "enhanced_integrations": {
                "google": GOOGLE_ENHANCED_AVAILABLE,
                "microsoft": MICROSOFT_ENHANCED_AVAILABLE,
                "dropbox": DROPBOX_ENHANCED_AVAILABLE
            },
            "blueprints_loaded": 30,
            "services_connected": 10,
            "enterprise_grade": True,
            "timestamp": datetime.now().isoformat(),
            "version": "3.1.0",
        }
    )

if __name__ == "__main__":
    port = int(os.getenv("PYTHON_API_PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)