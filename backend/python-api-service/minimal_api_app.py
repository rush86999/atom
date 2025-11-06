#!/usr/bin/env python3
"""
🚀 MINIMAL API APP - Google Integration Testing Only
Minimal backend with mock endpoints for Google integration tests
"""

import os
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables from .env file in project root
env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(env_path)

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Basic health endpoint
@app.route("/health")
def health_check():
    """Basic health check"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "minimal-api",
        "version": "1.0.0"
    })

@app.route("/api/integrations/google/health")
def google_health_check():
    """Google integration health check"""
    return jsonify({
        "status": "healthy",
        "service_available": True,
        "database_available": True,
        "timestamp": datetime.now().isoformat()
    })

# OAuth URL endpoint
@app.route("/api/oauth/google/url")
def google_oauth_url():
    """Generate Google OAuth authorization URL"""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv(
        "GOOGLE_REDIRECT_URI", "http://localhost:3000/oauth/google/callback"
    )

    if not client_id:
        return jsonify({"error": "Google client ID not configured", "success": False}), 500

    scope = "https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/drive.readonly"
    oauth_url = f"https://accounts.google.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&response_type=code"

    return jsonify({"oauth_url": oauth_url, "service": "google", "success": True})

# Gmail endpoint
@app.route("/api/integrations/google/gmail/messages", methods=["POST"])
def gmail_messages():
    """Mock Gmail messages endpoint"""
    data = request.get_json() or {}
    operation = data.get("operation", "list")
    
    if operation == "list":
        messages = [
            {
                "id": "msg_001",
                "threadId": "thread_001", 
                "subject": "Test Email 1",
                "from": "test1@example.com",
                "date": datetime.now().isoformat(),
                "snippet": "This is a test email for integration testing"
            },
            {
                "id": "msg_002",
                "threadId": "thread_002",
                "subject": "Test Email 2", 
                "from": "test2@example.com",
                "date": (datetime.now() - timedelta(days=1)).isoformat(),
                "snippet": "Another test email for Google integration testing"
            }
        ]
        return jsonify({
            "success": True,
            "data": {"messages": messages},
            "operation": "list"
        })
    else:
        return jsonify({
            "success": True,
            "data": {"message": f"Mock Gmail {operation} operation completed"},
            "operation": operation
        })

# Calendar endpoint
@app.route("/api/integrations/google/calendar/events", methods=["POST"])
def calendar_events():
    """Mock Calendar events endpoint"""
    data = request.get_json() or {}
    operation = data.get("operation", "list")
    
    if operation == "list":
        events = [
            {
                "id": "evt_001",
                "summary": "Test Meeting 1",
                "start": {"dateTime": (datetime.now() + timedelta(hours=1)).isoformat() + "Z"},
                "end": {"dateTime": (datetime.now() + timedelta(hours=2)).isoformat() + "Z"},
                "location": "Test Location 1"
            },
            {
                "id": "evt_002", 
                "summary": "Test Meeting 2",
                "start": {"dateTime": (datetime.now() + timedelta(days=1)).isoformat() + "Z"},
                "end": {"dateTime": (datetime.now() + timedelta(days=1, hours=1)).isoformat() + "Z"},
                "location": "Test Location 2"
            }
        ]
        return jsonify({
            "success": True,
            "data": {"events": events},
            "operation": "list"
        })
    elif operation == "create":
        event_data = data.get("data", {})
        return jsonify({
            "success": True,
            "data": {
                "event": {
                    "id": "evt_new_001",
                    "summary": event_data.get("summary", "New Event"),
                    "start": event_data.get("start", {"dateTime": datetime.now().isoformat()}),
                    "end": event_data.get("end", {"dateTime": (datetime.now() + timedelta(hours=1)).isoformat()})
                }
            },
            "operation": "create"
        })
    else:
        return jsonify({
            "success": True,
            "data": {"message": f"Mock Calendar {operation} operation completed"},
            "operation": operation
        })

# Drive endpoint
@app.route("/api/integrations/google/drive/files", methods=["POST"])
def drive_files():
    """Mock Drive files endpoint"""
    data = request.get_json() or {}
    operation = data.get("operation", "list")
    
    if operation == "list":
        files = [
            {
                "id": "file_001",
                "name": "Test Document.txt",
                "mimeType": "text/plain",
                "size": "1024",
                "createdTime": datetime.now().isoformat(),
                "modifiedTime": datetime.now().isoformat(),
                "webViewLink": "https://drive.google.com/file/d/file_001/view"
            },
            {
                "id": "file_002",
                "name": "Test Folder",
                "mimeType": "application/vnd.google-apps.folder", 
                "size": None,
                "createdTime": (datetime.now() - timedelta(days=1)).isoformat(),
                "modifiedTime": (datetime.now() - timedelta(days=1)).isoformat(),
                "webViewLink": "https://drive.google.com/drive/folders/file_002"
            }
        ]
        return jsonify({
            "success": True,
            "data": {"files": files},
            "operation": "list"
        })
    else:
        return jsonify({
            "success": True,
            "data": {"message": f"Mock Drive {operation} operation completed"},
            "operation": operation
        })

# Search endpoint
@app.route("/api/integrations/google/search", methods=["POST"])
def google_search():
    """Mock cross-service search endpoint"""
    data = request.get_json() or {}
    query = data.get("query", "")
    services = data.get("services", ["gmail", "drive", "calendar"])
    
    results = [
        {
            "id": "search_001",
            "title": f"Test Result for '{query}'",
            "snippet": f"This is a mock search result from Gmail for query: {query}",
            "service": "gmail",
            "type": "message",
            "url": "https://gmail.com/message/search_001"
        },
        {
            "id": "search_002",
            "title": f"Another {query} Result",
            "snippet": f"This is a mock search result from Drive for query: {query}",
            "service": "drive", 
            "type": "file",
            "url": "https://drive.google.com/file/search_002"
        }
    ]
    
    return jsonify({
        "success": True,
        "data": {"results": results},
        "query": query,
        "services": services
    })

# User profile endpoint
@app.route("/api/integrations/google/user/profile", methods=["POST"])
def user_profile():
    """Mock user profile endpoint"""
    data = request.get_json() or {}
    user_id = data.get("user_id", "")
    
    return jsonify({
        "success": True,
        "data": {
            "user": {
                "id": user_id,
                "email": f"{user_id}@gmail.com",
                "name": "Test User",
                "picture": "https://lh3.googleusercontent.com/a/default-user"
            },
            "services": {
                "gmail": True,
                "calendar": True, 
                "drive": True
            }
        }
    })

@app.route("/api/integrations/asana/health")
def asana_health_check():
    """Asana integration health check"""
    return jsonify({
        "status": "healthy",
        "service_available": True,
        "database_available": True,
        "timestamp": datetime.now().isoformat()
    })

@app.route("/api/oauth/asana/url")
def asana_oauth_url():
    """Generate Asana OAuth authorization URL"""
    client_id = os.getenv("ASANA_CLIENT_ID")
    redirect_uri = os.getenv(
        "ASANA_REDIRECT_URI", "http://localhost:3000/oauth/asana/callback"
    )

    if not client_id:
        return jsonify({"error": "Asana client ID not configured", "success": False}), 500

    oauth_url = f"https://app.asana.com/-/oauth_authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope=default"

    return jsonify({"oauth_url": oauth_url, "service": "asana", "success": True})

@app.route("/api/integrations/asana/tasks", methods=["POST"])
def asana_tasks():
    """Mock Asana tasks endpoint"""
    data = request.get_json() or {}
    operation = data.get("operation", "list")
    
    if operation == "list":
        tasks = [
            {
                "gid": "task_001",
                "name": "Test Task 1",
                "notes": "This is a test task for integration testing",
                "completed": False,
                "due_on": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            },
            {
                "gid": "task_002", 
                "name": "Test Task 2",
                "notes": "Another test task for Asana integration testing",
                "completed": False,
                "due_on": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
            }
        ]
        return jsonify({
            "success": True,
            "data": {"tasks": tasks},
            "operation": "list"
        })
    elif operation == "create":
        task_data = data.get("data", {})
        return jsonify({
            "success": True,
            "data": {
                "task": {
                    "gid": "task_new_001",
                    "name": task_data.get("name", "New Task"),
                    "notes": task_data.get("notes", ""),
                    "due_on": task_data.get("due_on", (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"))
                }
            },
            "operation": "create"
        })
    else:
        return jsonify({
            "success": True,
            "data": {"message": f"Mock Asana {operation} operation completed"},
            "operation": operation
        })

@app.route("/api/integrations/asana/projects", methods=["POST"])
def asana_projects():
    """Mock Asana projects endpoint"""
    data = request.get_json() or {}
    operation = data.get("operation", "list")
    
    if operation == "list":
        projects = [
            {
                "gid": "proj_001",
                "name": "Test Project 1",
                "notes": "This is a test project for integration testing"
            },
            {
                "gid": "proj_002",
                "name": "Test Project 2", 
                "notes": "Another test project for Asana integration testing"
            }
        ]
        return jsonify({
            "success": True,
            "data": {"projects": projects},
            "operation": "list"
        })
    else:
        return jsonify({
            "success": True,
            "data": {"message": f"Mock Asana {operation} operation completed"},
            "operation": operation
        })

@app.route("/api/integrations/asana/user/profile", methods=["POST"])
def asana_user_profile():
    """Mock Asana user profile endpoint"""
    data = request.get_json() or {}
    user_id = data.get("user_id", "")
    
    return jsonify({
        "success": True,
        "data": {
            "user": {
                "gid": user_id,
                "name": "Test Asana User",
                "email": f"{user_id}@asana.com"
            },
            "workspaces": [
                {
                    "gid": "ws_001",
                    "name": "Test Workspace"
                }
            ]
        }
    })

@app.route("/api/integrations/slack/health")
def slack_health_check():
    """Slack integration health check"""
    return jsonify({
        "status": "healthy",
        "service_available": True,
        "database_available": True,
        "timestamp": datetime.now().isoformat()
    })

@app.route("/api/oauth/slack/url")
def slack_oauth_url():
    """Generate Slack OAuth authorization URL"""
    client_id = os.getenv("SLACK_CLIENT_ID")
    redirect_uri = os.getenv(
        "SLACK_REDIRECT_URI", "http://localhost:3000/oauth/slack/callback"
    )

    if not client_id:
        return jsonify({"error": "Slack client ID not configured", "success": False}), 500

    oauth_url = f"https://slack.com/oauth/v2/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope=channels:read chat:read users:read&response_type=code"

    return jsonify({"oauth_url": oauth_url, "service": "slack", "success": True})

@app.route("/api/integrations/slack/channels", methods=["POST"])
def slack_channels():
    """Mock Slack channels endpoint"""
    data = request.get_json() or {}
    operation = data.get("operation", "list")
    
    if operation == "list":
        channels = [
            {
                "id": "C001",
                "name": "general",
                "is_general": True,
                "purpose": "Company-wide announcements and work-based matters",
                "created": (datetime.now() - timedelta(days=365)).isoformat()
            },
            {
                "id": "C002",
                "name": "random",
                "is_general": False,
                "purpose": "Non-work banter and water cooler conversation",
                "created": (datetime.now() - timedelta(days=300)).isoformat()
            },
            {
                "id": "C003",
                "name": "dev-team",
                "is_general": False,
                "purpose": "Development team discussions and code reviews",
                "created": (datetime.now() - timedelta(days=200)).isoformat()
            }
        ]
        return jsonify({
            "success": True,
            "data": {"channels": channels},
            "operation": "list"
        })
    else:
        return jsonify({
            "success": True,
            "data": {"message": f"Mock Slack {operation} operation completed"},
            "operation": operation
        })

@app.route("/api/integrations/slack/messages", methods=["POST"])
def slack_messages():
    """Mock Slack messages endpoint"""
    data = request.get_json() or {}
    operation = data.get("operation", "list")
    channel = data.get("channel", "general")
    
    if operation == "list":
        messages = [
            {
                "ts": "1638500000.000100",
                "user": "U001",
                "text": "Welcome to the ATOM Slack integration test!",
                "type": "message",
                "channel": channel,
                "thread_ts": None,
                "reply_count": 0,
                "reactions": []
            },
            {
                "ts": "1638500100.000200",
                "user": "U002",
                "text": "This is a test message from the integration test suite.",
                "type": "message",
                "channel": channel,
                "thread_ts": None,
                "reply_count": 0,
                "reactions": [{"name": "thumbsup", "count": 2}]
            }
        ]
        return jsonify({
            "success": True,
            "data": {"messages": messages},
            "operation": "list"
        })
    elif operation == "send":
        message_data = {
            "ts": str(datetime.now().timestamp()) + ".000300",
            "user": "U003",
            "text": data.get("text", "Test message from ATOM"),
            "type": "message",
            "channel": channel,
            "thread_ts": None,
            "reply_count": 0,
            "reactions": []
        }
        return jsonify({
            "success": True,
            "data": {"message": message_data},
            "operation": "send"
        })
    else:
        return jsonify({
            "success": True,
            "data": {"message": f"Mock Slack {operation} operation completed"},
            "operation": operation
        })

@app.route("/api/integrations/slack/user/profile", methods=["POST"])
def slack_user_profile():
    """Mock Slack user profile endpoint"""
    data = request.get_json() or {}
    user_id = data.get("user_id", "")
    
    return jsonify({
        "success": True,
        "data": {
            "user": {
                "id": user_id,
                "name": "Test Slack User",
                "real_name": "Test User",
                "email": f"{user_id}@slack.com",
                "display_name": "Test User",
                "avatar": "https://ca.slack-edge.com/img/test-avatar.png",
                "timezone": "America/New_York"
            },
            "teams": [
                {
                    "id": "T001",
                    "name": "ATOM Workspace",
                    "domain": "atom-workspace"
                }
            ]
        }
    })

@app.route("/api/integrations/slack/workspace", methods=["POST"])
def slack_workspace():
    """Mock Slack workspace endpoint"""
    data = request.get_json() or {}
    
    return jsonify({
        "success": True,
        "data": {
            "workspace": {
                "id": "T001",
                "name": "ATOM Workspace",
                "domain": "atom-workspace",
                "url": "https://atom-workspace.slack.com",
                "email_domain": "atom-workspace.com",
                "icon": {
                    "image_132": "https://ca.slack-edge.com/img/test-workspace-icon.png"
                }
            }
        }
    })

@app.route("/api/integrations/notion/health")
def notion_health_check():
    """Notion integration health check"""
    return jsonify({
        "status": "healthy",
        "service_available": True,
        "database_available": True,
        "timestamp": datetime.now().isoformat()
    })

@app.route("/api/oauth/notion/url")
def notion_oauth_url():
    """Generate Notion OAuth authorization URL"""
    client_id = os.getenv("NOTION_CLIENT_ID")
    redirect_uri = os.getenv(
        "NOTION_REDIRECT_URI", "http://localhost:3000/oauth/notion/callback"
    )

    if not client_id:
        return jsonify({"error": "Notion client ID not configured", "success": False}), 500

    oauth_url = f"https://api.notion.com/v1/oauth/authorize?client_id={client_id}&response_type=code&owner=user&redirect_uri={redirect_uri}"

    return jsonify({"oauth_url": oauth_url, "service": "notion", "success": True})

@app.route("/api/integrations/notion/pages", methods=["POST"])
def notion_pages():
    """Mock Notion pages endpoint"""
    data = request.get_json() or {}
    operation = data.get("operation", "list")
    
    if operation == "list":
        pages = [
            {
                "id": "page_001",
                "title": {"text": [{"text": {"content": "Test Page 1"}}]},
                "created_time": (datetime.now() - timedelta(days=7)).isoformat(),
                "last_edited_time": (datetime.now() - timedelta(days=1)).isoformat(),
                "url": "https://notion.so/test-page-1"
            },
            {
                "id": "page_002",
                "title": {"text": [{"text": {"content": "Test Page 2"}}]},
                "created_time": (datetime.now() - timedelta(days=14)).isoformat(),
                "last_edited_time": (datetime.now() - timedelta(days=2)).isoformat(),
                "url": "https://notion.so/test-page-2"
            }
        ]
        return jsonify({
            "success": True,
            "data": {"pages": pages},
            "operation": "list"
        })
    elif operation == "create":
        page_data = data.get("data", {})
        return jsonify({
            "success": True,
            "data": {
                "page": {
                    "id": "page_new_001",
                    "properties": page_data.get("properties", {}),
                    "created_time": datetime.now().isoformat(),
                    "last_edited_time": datetime.now().isoformat(),
                    "url": f"https://notion.so/page-new-{datetime.now().timestamp()}"
                }
            },
            "operation": "create"
        })
    else:
        return jsonify({
            "success": True,
            "data": {"message": f"Mock Notion {operation} operation completed"},
            "operation": operation
        })

@app.route("/api/integrations/notion/databases", methods=["POST"])
def notion_databases():
    """Mock Notion databases endpoint"""
    data = request.get_json() or {}
    operation = data.get("operation", "list")
    
    if operation == "list":
        databases = [
            {
                "id": "db_001",
                "title": {"text": [{"text": {"content": "Test Database 1"}}]},
                "description": {"text": [{"text": {"content": "This is a test database for integration testing"}}]},
                "created_time": (datetime.now() - timedelta(days=30)).isoformat(),
                "last_edited_time": (datetime.now() - timedelta(days=1)).isoformat(),
                "url": "https://notion.so/test-database-1"
            },
            {
                "id": "db_002",
                "title": {"text": [{"text": {"content": "Test Database 2"}}]},
                "description": {"text": [{"text": {"content": "Another test database for Notion integration testing"}}]},
                "created_time": (datetime.now() - timedelta(days=60)).isoformat(),
                "last_edited_time": (datetime.now() - timedelta(days=2)).isoformat(),
                "url": "https://notion.so/test-database-2"
            }
        ]
        return jsonify({
            "success": True,
            "data": {"databases": databases},
            "operation": "list"
        })
    else:
        return jsonify({
            "success": True,
            "data": {"message": f"Mock Notion {operation} operation completed"},
            "operation": operation
        })

@app.route("/api/integrations/notion/search", methods=["POST"])
def notion_search():
    """Mock Notion search endpoint"""
    data = request.get_json() or {}
    query = data.get("query", "")
    
    results = [
        {
            "id": "search_001",
            "title": {"text": [{"text": {"content": f"Test Result for '{query}'"}}]},
            "object": "page",
            "last_edited_time": (datetime.now() - timedelta(hours=1)).isoformat(),
            "url": "https://notion.so/search-result-1"
        },
        {
            "id": "search_002",
            "title": {"text": [{"text": {"content": f"Another {query} Result"}}]},
            "object": "database",
            "last_edited_time": (datetime.now() - timedelta(hours=2)).isoformat(),
            "url": "https://notion.so/search-result-2"
        }
    ]
    
    return jsonify({
        "success": True,
        "data": {"results": results},
        "query": query
    })

@app.route("/api/integrations/notion/user/profile", methods=["POST"])
def notion_user_profile():
    """Mock Notion user profile endpoint"""
    data = request.get_json() or {}
    user_id = data.get("user_id", "")
    
    return jsonify({
        "success": True,
        "data": {
            "user": {
                "id": user_id,
                "name": "Test Notion User",
                "email": f"{user_id}@notion.com",
                "avatar_url": "https://s3-us-west-2.amazonaws.com/public.notion.prod/test-avatar.png"
            },
            "workspaces": [
                {
                    "id": "ws_001",
                    "name": "Test Workspace",
                    "icon": {"type": "emoji", "emoji": "🧪"}
                }
            ]
        }
    })

@app.route("/api/integrations/teams/health")
def teams_health_check():
    """Microsoft Teams integration health check"""
    return jsonify({
        "status": "healthy",
        "service_available": True,
        "database_available": True,
        "timestamp": datetime.now().isoformat()
    })

@app.route("/api/oauth/teams/url")
def teams_oauth_url():
    """Generate Microsoft Teams OAuth authorization URL"""
    client_id = os.getenv("MICROSOFT_CLIENT_ID")
    redirect_uri = os.getenv(
        "TEAMS_REDIRECT_URI", "http://localhost:3000/oauth/teams/callback"
    )

    if not client_id:
        return jsonify({"error": "Microsoft client ID not configured", "success": False}), 500

    oauth_url = f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&response_mode=query&scope=https://graph.microsoft.com/User.Read%20https://graph.microsoft.com/Chat.Read%20https://graph.microsoft.com/Team.ReadBasic.All"

    return jsonify({"oauth_url": oauth_url, "service": "teams", "success": True})

@app.route("/api/integrations/teams/teams", methods=["POST"])
def teams_teams():
    """Mock Teams teams listing endpoint"""
    data = request.get_json() or {}
    operation = data.get("operation", "list")
    
    if operation == "list":
        teams = [
            {
                "id": "team_001",
                "displayName": "Test Team 1",
                "description": "This is a test team for integration testing",
                "createdDateTime": (datetime.now() - timedelta(days=365)).isoformat(),
                "memberCount": 15
            },
            {
                "id": "team_002",
                "displayName": "Test Team 2",
                "description": "Another test team for Teams integration testing",
                "createdDateTime": (datetime.now() - timedelta(days=200)).isoformat(),
                "memberCount": 8
            },
            {
                "id": "team_003",
                "displayName": "Development Team",
                "description": "Development team discussions and collaboration",
                "createdDateTime": (datetime.now() - timedelta(days=180)).isoformat(),
                "memberCount": 12
            }
        ]
        return jsonify({
            "success": True,
            "data": {"teams": teams},
            "operation": "list"
        })
    else:
        return jsonify({
            "success": True,
            "data": {"message": f"Mock Teams {operation} operation completed"},
            "operation": operation
        })

@app.route("/api/integrations/teams/channels", methods=["POST"])
def teams_channels():
    """Mock Teams channels listing endpoint"""
    data = request.get_json() or {}
    operation = data.get("operation", "list")
    team_id = data.get("team_id", "team_001")
    
    if operation == "list":
        channels = [
            {
                "id": "channel_001",
                "displayName": "General",
                "description": "General team channel",
                "teamId": team_id,
                "createdDateTime": (datetime.now() - timedelta(days=365)).isoformat(),
                "membershipType": "standard"
            },
            {
                "id": "channel_002",
                "displayName": "Random",
                "description": "Random discussions and team banter",
                "teamId": team_id,
                "createdDateTime": (datetime.now() - timedelta(days=300)).isoformat(),
                "membershipType": "standard"
            },
            {
                "id": "channel_003",
                "displayName": "Development",
                "description": "Development discussions and code reviews",
                "teamId": team_id,
                "createdDateTime": (datetime.now() - timedelta(days=250)).isoformat(),
                "membershipType": "standard"
            }
        ]
        return jsonify({
            "success": True,
            "data": {"channels": channels},
            "operation": "list"
        })
    else:
        return jsonify({
            "success": True,
            "data": {"message": f"Mock Teams {operation} operation completed"},
            "operation": operation
        })

@app.route("/api/integrations/teams/messages", methods=["POST"])
def teams_messages():
    """Mock Teams messages endpoint"""
    data = request.get_json() or {}
    operation = data.get("operation", "list")
    channel_id = data.get("channel_id", "channel_001")
    
    if operation == "list":
        messages = [
            {
                "id": "message_001",
                "contentType": "text",
                "content": "Welcome to ATOM Teams integration test!",
                "from": {"displayName": "Test User", "id": "user_001"},
                "createdDateTime": (datetime.now() - timedelta(hours=2)).isoformat(),
                "channelId": channel_id
            },
            {
                "id": "message_002",
                "contentType": "text",
                "content": "This is a test message from the integration test suite.",
                "from": {"displayName": "Integration Bot", "id": "bot_001"},
                "createdDateTime": (datetime.now() - timedelta(hours=1)).isoformat(),
                "channelId": channel_id
            }
        ]
        return jsonify({
            "success": True,
            "data": {"messages": messages},
            "operation": "list"
        })
    elif operation == "send":
        message_data = {
            "id": "message_new_001",
            "contentType": "text",
            "content": data.get("content", "Test message from ATOM"),
            "from": {"displayName": "Test User", "id": "user_001"},
            "createdDateTime": datetime.now().isoformat(),
            "channelId": channel_id
        }
        return jsonify({
            "success": True,
            "data": {"message": message_data},
            "operation": "send"
        })
    else:
        return jsonify({
            "success": True,
            "data": {"message": f"Mock Teams {operation} operation completed"},
            "operation": operation
        })

@app.route("/api/integrations/teams/meetings", methods=["POST"])
def teams_meetings():
    """Mock Teams meetings endpoint"""
    data = request.get_json() or {}
    operation = data.get("operation", "list")
    
    if operation == "list":
        meetings = [
            {
                "id": "meeting_001",
                "subject": "Daily Standup",
                "start": {"dateTime": (datetime.now() + timedelta(hours=1)).isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": (datetime.now() + timedelta(hours=1, minutes=30)).isoformat(), "timeZone": "UTC"},
                "isOnlineMeeting": True,
                "onlineMeetingUrl": "https://teams.microsoft.com/l/meetup-join/meeting_001"
            },
            {
                "id": "meeting_002",
                "subject": "Development Planning",
                "start": {"dateTime": (datetime.now() + timedelta(days=1)).isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": (datetime.now() + timedelta(days=1, hours=2)).isoformat(), "timeZone": "UTC"},
                "isOnlineMeeting": True,
                "onlineMeetingUrl": "https://teams.microsoft.com/l/meetup-join/meeting_002"
            }
        ]
        return jsonify({
            "success": True,
            "data": {"meetings": meetings},
            "operation": "list"
        })
    else:
        return jsonify({
            "success": True,
            "data": {"message": f"Mock Teams {operation} operation completed"},
            "operation": operation
        })

@app.route("/api/integrations/teams/user/profile", methods=["POST"])
def teams_user_profile():
    """Mock Teams user profile endpoint"""
    data = request.get_json() or {}
    user_id = data.get("user_id", "")
    
    return jsonify({
        "success": True,
        "data": {
            "user": {
                "id": user_id,
                "displayName": "Test Teams User",
                "mail": f"{user_id}@teams.com",
                "userPrincipalName": f"{user_id}@teams.com",
                "jobTitle": "Software Engineer",
                "department": "Engineering",
                "officeLocation": "Remote"
            },
            "teams": [
                {
                    "id": "team_001",
                    "displayName": "Test Team 1"
                },
                {
                    "id": "team_003", 
                    "displayName": "Development Team"
                }
            ]
        }
    })

@app.route("/api/integrations/github/health")
def github_health_check():
    """GitHub integration health check"""
    return jsonify({
        "status": "healthy",
        "service_available": True,
        "database_available": True,
        "timestamp": datetime.now().isoformat()
    })

@app.route("/api/oauth/github/url")
def github_oauth_url():
    """Generate GitHub OAuth authorization URL"""
    client_id = os.getenv("GITHUB_CLIENT_ID")
    redirect_uri = os.getenv(
        "GITHUB_REDIRECT_URI", "http://localhost:3000/oauth/github/callback"
    )

    if not client_id:
        return jsonify({"error": "GitHub client ID not configured", "success": False}), 500

    oauth_url = f"https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope=repo,user:email,read:org"

    return jsonify({"oauth_url": oauth_url, "service": "github", "success": True})

@app.route("/api/integrations/github/repositories", methods=["POST"])
def github_repositories():
    """Mock GitHub repositories listing endpoint"""
    data = request.get_json() or {}
    operation = data.get("operation", "list")
    
    if operation == "list":
        repos = [
            {
                "id": 1,
                "name": "atom-platform",
                "full_name": "test-user/atom-platform",
                "description": "ATOM integration platform",
                "private": False,
                "language": "TypeScript",
                "stars": 42,
                "forks": 15,
                "created_at": (datetime.now() - timedelta(days=365)).isoformat(),
                "updated_at": (datetime.now() - timedelta(hours=2)).isoformat(),
                "clone_url": "https://github.com/test-user/atom-platform.git"
            },
            {
                "id": 2,
                "name": "integration-tests",
                "full_name": "test-user/integration-tests",
                "description": "Comprehensive integration testing suite",
                "private": True,
                "language": "Python",
                "stars": 8,
                "forks": 3,
                "created_at": (datetime.now() - timedelta(days=180)).isoformat(),
                "updated_at": (datetime.now() - timedelta(hours=6)).isoformat(),
                "clone_url": "https://github.com/test-user/integration-tests.git"
            },
            {
                "id": 3,
                "name": "api-clients",
                "full_name": "test-user/api-clients",
                "description": "API client libraries and utilities",
                "private": False,
                "language": "JavaScript",
                "stars": 25,
                "forks": 7,
                "created_at": (datetime.now() - timedelta(days=120)).isoformat(),
                "updated_at": (datetime.now() - timedelta(hours=1)).isoformat(),
                "clone_url": "https://github.com/test-user/api-clients.git"
            }
        ]
        return jsonify({
            "success": True,
            "data": {"repositories": repos},
            "operation": "list"
        })
    else:
        return jsonify({
            "success": True,
            "data": {"message": f"Mock GitHub {operation} operation completed"},
            "operation": operation
        })

@app.route("/api/integrations/github/user/profile", methods=["POST"])
def github_user_profile():
    """Mock GitHub user profile endpoint"""
    data = request.get_json() or {}
    user_id = data.get("user_id", "")
    
    return jsonify({
        "success": True,
        "data": {
            "user": {
                "id": 123456,
                "login": "test-github-user",
                "name": "Test GitHub User",
                "email": f"{user_id}@github.com",
                "bio": "Software developer passionate about integrations",
                "location": "San Francisco, CA",
                "company": "ATOM Technologies",
                "public_repos": 12,
                "private_repos": 8,
                "followers": 245,
                "following": 189,
                "created_at": (datetime.now() - timedelta(days=1825)).isoformat(),
                "updated_at": (datetime.now() - timedelta(hours=4)).isoformat(),
                "avatar_url": "https://avatars.githubusercontent.com/u/123456?v=4",
                "html_url": "https://github.com/test-github-user"
            }
        }
    })

@app.route("/api/integrations/outlook/health")
def outlook_health_check():
    """Outlook integration health check"""
    return jsonify({
        "status": "healthy",
        "service_available": True,
        "database_available": True,
        "timestamp": datetime.now().isoformat()
    })

@app.route("/api/oauth/outlook/url")
def outlook_oauth_url():
    """Generate Outlook OAuth authorization URL"""
    client_id = os.getenv("OUTLOOK_CLIENT_ID")
    redirect_uri = os.getenv(
        "OUTLOOK_REDIRECT_URI", "http://localhost:3000/oauth/outlook/callback"
    )

    if not client_id:
        return jsonify({"error": "Outlook client ID not configured", "success": False}), 500

    oauth_url = f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&response_mode=query&scope=https://graph.microsoft.com/Mail.Read%20https://graph.microsoft.com/Calendar.Read%20https://graph.microsoft.com/Contacts.Read%20https://graph.microsoft.com/User.Read"

    return jsonify({"oauth_url": oauth_url, "service": "outlook", "success": True})

@app.route("/api/integrations/outlook/emails", methods=["POST"])
def outlook_emails():
    """Mock Outlook emails endpoint"""
    data = request.get_json() or {}
    operation = data.get("operation", "list")
    
    if operation == "list":
        emails = [
            {
                "id": "message_001",
                "subject": "Test Email 1 - ATOM Integration",
                "from": {"emailAddress": {"name": "Test Sender", "address": "test@outlook.com"}},
                "toRecipients": [{"emailAddress": {"name": "Test User", "address": "test_user_outlook@outlook.com"}}],
                "body": {"content": "This is a test email from ATOM integration testing.", "contentType": "text"},
                "receivedDateTime": (datetime.now() - timedelta(hours=2)).isoformat(),
                "isRead": False,
                "importance": "normal"
            },
            {
                "id": "message_002",
                "subject": "Meeting Reminder - Development Team",
                "from": {"emailAddress": {"name": "Project Manager", "address": "pm@outlook.com"}},
                "toRecipients": [{"emailAddress": {"name": "Test User", "address": "test_user_outlook@outlook.com"}}],
                "body": {"content": "Don't forget about our development team meeting today.", "contentType": "text"},
                "receivedDateTime": (datetime.now() - timedelta(hours=4)).isoformat(),
                "isRead": True,
                "importance": "high"
            },
            {
                "id": "message_003",
                "subject": "Weekly Report - Development Progress",
                "from": {"emailAddress": {"name": "Development Team", "address": "dev-team@outlook.com"}},
                "toRecipients": [{"emailAddress": {"name": "Test User", "address": "test_user_outlook@outlook.com"}}],
                "body": {"content": "Here's the weekly development progress report.", "contentType": "text"},
                "receivedDateTime": (datetime.now() - timedelta(days=1)).isoformat(),
                "isRead": True,
                "importance": "normal"
            }
        ]
        return jsonify({
            "success": True,
            "data": {"emails": emails},
            "operation": "list"
        })
    else:
        return jsonify({
            "success": True,
            "data": {"message": f"Mock Outlook {operation} operation completed"},
            "operation": operation
        })

@app.route("/api/integrations/outlook/calendar", methods=["POST"])
def outlook_calendar():
    """Mock Outlook calendar endpoint"""
    data = request.get_json() or {}
    operation = data.get("operation", "list")
    
    if operation == "list":
        events = [
            {
                "id": "event_001",
                "subject": "Development Team Standup",
                "start": {"dateTime": (datetime.now() + timedelta(hours=1)).isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": (datetime.now() + timedelta(hours=1, minutes=30)).isoformat(), "timeZone": "UTC"},
                "location": {"displayName": "Conference Room A"},
                "attendees": [
                    {"emailAddress": {"name": "Test User", "address": "test_user_outlook@outlook.com"}},
                    {"emailAddress": {"name": "Team Lead", "address": "lead@outlook.com"}}
                ],
                "isOnlineMeeting": False,
                "importance": "normal"
            },
            {
                "id": "event_002",
                "subject": "Project Planning Meeting",
                "start": {"dateTime": (datetime.now() + timedelta(days=1, hours=14)).isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": (datetime.now() + timedelta(days=1, hours=16)).isoformat(), "timeZone": "UTC"},
                "location": {"displayName": "Virtual - Teams"},
                "attendees": [
                    {"emailAddress": {"name": "Test User", "address": "test_user_outlook@outlook.com"}},
                    {"emailAddress": {"name": "Project Manager", "address": "pm@outlook.com"}},
                    {"emailAddress": {"name": "Stakeholder", "address": "stakeholder@outlook.com"}}
                ],
                "isOnlineMeeting": True,
                "importance": "high"
            }
        ]
        return jsonify({
            "success": True,
            "data": {"events": events},
            "operation": "list"
        })
    else:
        return jsonify({
            "success": True,
            "data": {"message": f"Mock Outlook {operation} operation completed"},
            "operation": operation
        })

@app.route("/api/integrations/outlook/contacts", methods=["POST"])
def outlook_contacts():
    """Mock Outlook contacts endpoint"""
    data = request.get_json() or {}
    operation = data.get("operation", "list")
    
    if operation == "list":
        contacts = [
            {
                "id": "contact_001",
                "displayName": "John Doe",
                "emailAddresses": [{"address": "john.doe@outlook.com", "name": "John Doe"}],
                "phones": [{"number": "+1-555-0101", "type": "mobile"}],
                "companyName": "Tech Corp",
                "jobTitle": "Software Engineer"
            },
            {
                "id": "contact_002",
                "displayName": "Jane Smith",
                "emailAddresses": [{"address": "jane.smith@outlook.com", "name": "Jane Smith"}],
                "phones": [{"number": "+1-555-0102", "type": "business"}],
                "companyName": "Design Studio",
                "jobTitle": "UX Designer"
            },
            {
                "id": "contact_003",
                "displayName": "Mike Johnson",
                "emailAddresses": [{"address": "mike.johnson@outlook.com", "name": "Mike Johnson"}],
                "phones": [{"number": "+1-555-0103", "type": "home"}],
                "companyName": "Freelance",
                "jobTitle": "Consultant"
            }
        ]
        return jsonify({
            "success": True,
            "data": {"contacts": contacts},
            "operation": "list"
        })
    else:
        return jsonify({
            "success": True,
            "data": {"message": f"Mock Outlook {operation} operation completed"},
            "operation": operation
        })

@app.route("/api/integrations/outlook/user/profile", methods=["POST"])
def outlook_user_profile():
    """Mock Outlook user profile endpoint"""
    data = request.get_json() or {}
    user_id = data.get("user_id", "")
    
    return jsonify({
        "success": True,
        "data": {
            "user": {
                "id": user_id,
                "displayName": "Test Outlook User",
                "mail": f"{user_id}@outlook.com",
                "userPrincipalName": f"{user_id}@outlook.com",
                "jobTitle": "Software Developer",
                "companyName": "ATOM Technologies",
                "department": "Engineering",
                "officeLocation": "San Francisco, CA",
                "mobilePhone": "+1-555-0100"
            }
        }
    })

if __name__ == "__main__":
    port = int(os.getenv("PYTHON_API_PORT", 5058))
    logger.info(f"Starting minimal API server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=True)