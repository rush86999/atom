import os
import sys
from flask import Flask, jsonify, request, redirect
import requests
import json
import time
from urllib.parse import urlencode
import secrets
from datetime import datetime, timedelta

# Set environment variables with your actual credentials
os.environ["ASANA_CLIENT_ID"] = "1211551350187489"
os.environ["ASANA_CLIENT_SECRET"] = "a4d944583e2e3fd199b678ece03762b0"
os.environ["ASANA_REDIRECT_URI"] = "http://localhost:8000/api/auth/asana/callback"

# Slack OAuth configuration
SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID", "YOUR_SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET", "YOUR_SLACK_CLIENT_SECRET")
SLACK_REDIRECT_URI = os.getenv(
    "SLACK_REDIRECT_URI", "http://localhost:8000/api/auth/slack/callback"
)

# Slack API endpoints
SLACK_AUTH_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"

# Slack API scopes
SLACK_SCOPES = [
    "channels:read",
    "channels:history",
    "groups:read",
    "groups:history",
    "im:read",
    "im:history",
    "mpim:read",
    "mpim:history",
    "chat:write",
    "chat:write.public",
    "users:read",
    "users:read.email",
    "team:read",
]

# Create Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "atom-backend-with-slack-integration"

# Store temporary session data (in production, use proper session management)
sessions = {}
slack_tokens = {}  # In production, use database


class SlackService:
    """Simple Slack service for basic operations"""

    def __init__(self, access_token=None):
        self.access_token = access_token
        self.base_url = "https://slack.com/api"

    def _make_request(self, endpoint, method="GET", data=None):
        """Make authenticated request to Slack API"""
        if not self.access_token:
            return {"ok": False, "error": "No access token available"}

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/{endpoint}"

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            else:
                response = requests.post(url, headers=headers, json=data, timeout=30)

            return response.json()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_channels(self):
        """Get list of channels"""
        return self._make_request(
            "conversations.list?types=public_channel,private_channel"
        )

    def get_users(self):
        """Get list of users"""
        return self._make_request("users.list")

    def send_message(self, channel, text):
        """Send message to channel"""
        data = {"channel": channel, "text": text}
        return self._make_request("chat.postMessage", method="POST", data=data)

    def get_channel_history(self, channel, limit=100):
        """Get channel message history"""
        return self._make_request(
            f"conversations.history?channel={channel}&limit={limit}"
        )

    def get_user_info(self, user_id):
        """Get user information"""
        return self._make_request(f"users.info?user={user_id}")


# Initialize Slack service
slack_service = SlackService()


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "atom-backend-with-slack-integration",
            "version": "1.0.0",
            "timestamp": time.time(),
            "asana_configured": bool(
                os.getenv("ASANA_CLIENT_ID") and os.getenv("ASANA_CLIENT_SECRET")
            ),
            "slack_configured": bool(
                SLACK_CLIENT_ID != "YOUR_SLACK_CLIENT_ID"
                and SLACK_CLIENT_SECRET != "YOUR_SLACK_CLIENT_SECRET"
            ),
        }
    )


@app.route("/")
def root():
    return jsonify(
        {
            "name": "ATOM Backend with Slack Integration",
            "status": "running",
            "asana_client_id": os.getenv("ASANA_CLIENT_ID", "not_set"),
            "slack_client_id": SLACK_CLIENT_ID
            if SLACK_CLIENT_ID != "YOUR_SLACK_CLIENT_ID"
            else "not_set",
            "endpoints": {
                "health": "/health",
                "asana_health": "/api/asana/health",
                "asana_oauth": "/api/auth/asana/authorize",
                "asana_callback": "/api/auth/asana/callback",
                "slack_health": "/api/slack/health",
                "slack_oauth": "/api/auth/slack/authorize",
                "slack_callback": "/api/auth/slack/callback",
                "slack_channels": "/api/slack/channels",
                "slack_users": "/api/slack/users",
                "slack_send_message": "/api/slack/send-message",
            },
        }
    )


# Asana Integration (existing)
@app.route("/api/asana/health")
def asana_health():
    client_id = os.getenv("ASANA_CLIENT_ID")
    return jsonify(
        {
            "ok": True,
            "service": "asana",
            "status": "ready",
            "client_id_configured": bool(client_id),
            "message": "Asana integration ready for OAuth flow",
            "endpoints": {
                "oauth_authorize": "/api/auth/asana/authorize",
                "oauth_callback": "/api/auth/asana/callback",
            },
        }
    )


@app.route("/api/auth/asana/authorize")
def asana_authorize():
    user_id = request.args.get("user_id", "default_user")
    client_id = os.getenv("ASANA_CLIENT_ID")
    redirect_uri = os.getenv("ASANA_REDIRECT_URI")

    if not client_id:
        return jsonify({"ok": False, "error": "ASANA_CLIENT_ID not configured"}), 400

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(16)
    sessions[state] = {"user_id": user_id, "timestamp": time.time()}

    # Build real Asana OAuth URL
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
        "scope": "default",
    }

    auth_url = f"https://app.asana.com/-/oauth_authorize?{urlencode(params)}"

    return jsonify(
        {
            "ok": True,
            "auth_url": auth_url,
            "user_id": user_id,
            "state": state,
        }
    )


@app.route("/api/auth/asana/callback")
def asana_callback():
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    if error:
        return jsonify({"ok": False, "error": error}), 400

    if not code:
        return jsonify({"ok": False, "error": "No authorization code received"}), 400

    if not state or state not in sessions:
        return jsonify({"ok": False, "error": "Invalid state parameter"}), 400

    user_session = sessions[state]
    user_id = user_session["user_id"]

    # Exchange code for access token
    client_id = os.getenv("ASANA_CLIENT_ID")
    client_secret = os.getenv("ASANA_CLIENT_SECRET")
    redirect_uri = os.getenv("ASANA_REDIRECT_URI")

    token_data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }

    try:
        response = requests.post("https://app.asana.com/-/oauth_token", data=token_data)
        token_info = response.json()

        if "access_token" in token_info:
            # Store token (in production, use database)
            sessions[f"asana_token_{user_id}"] = {
                "access_token": token_info["access_token"],
                "expires_at": time.time() + token_info.get("expires_in", 3600),
                "refresh_token": token_info.get("refresh_token"),
            }

            return jsonify(
                {
                    "ok": True,
                    "message": "Asana connected successfully",
                    "user_id": user_id,
                    "access_token": token_info["access_token"],
                }
            )
        else:
            return jsonify(
                {"ok": False, "error": token_info.get("error", "Token exchange failed")}
            ), 400

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# Slack Integration (new)
@app.route("/api/slack/health")
def slack_health():
    return jsonify(
        {
            "ok": True,
            "service": "slack",
            "status": "ready",
            "client_id_configured": bool(SLACK_CLIENT_ID != "YOUR_SLACK_CLIENT_ID"),
            "message": "Slack integration ready for OAuth flow",
            "endpoints": {
                "oauth_authorize": "/api/auth/slack/authorize",
                "oauth_callback": "/api/auth/slack/callback",
                "channels": "/api/slack/channels",
                "users": "/api/slack/users",
                "send_message": "/api/slack/send-message",
            },
        }
    )


@app.route("/api/auth/slack/authorize")
def slack_authorize():
    """Initiate Slack OAuth flow"""
    user_id = request.args.get("user_id", "default_user")

    if SLACK_CLIENT_ID == "YOUR_SLACK_CLIENT_ID":
        return jsonify({"ok": False, "error": "SLACK_CLIENT_ID not configured"}), 400

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    sessions[f"slack_state_{state}"] = {"user_id": user_id, "timestamp": time.time()}

    # Build authorization URL
    auth_params = {
        "client_id": SLACK_CLIENT_ID,
        "redirect_uri": SLACK_REDIRECT_URI,
        "scope": ",".join(SLACK_SCOPES),
        "state": state,
        "user_scope": "chat:write,users:read",
    }

    auth_url = f"{SLACK_AUTH_URL}?{urlencode(auth_params)}"

    return jsonify(
        {
            "ok": True,
            "auth_url": auth_url,
            "user_id": user_id,
            "state": state,
            "scopes": SLACK_SCOPES,
        }
    )


@app.route("/api/auth/slack/callback")
def slack_callback():
    """Handle Slack OAuth callback"""
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    if error:
        return jsonify({"ok": False, "error": error}), 400

    if not code:
        return jsonify({"ok": False, "error": "No authorization code received"}), 400

    state_key = f"slack_state_{state}"
    if not state or state_key not in sessions:
        return jsonify({"ok": False, "error": "Invalid state parameter"}), 400

    user_session = sessions[state_key]
    user_id = user_session["user_id"]

    # Exchange authorization code for tokens
    token_data = {
        "client_id": SLACK_CLIENT_ID,
        "client_secret": SLACK_CLIENT_SECRET,
        "code": code,
        "redirect_uri": SLACK_REDIRECT_URI,
    }

    try:
        response = requests.post(SLACK_TOKEN_URL, data=token_data)
        token_info = response.json()

        if token_info.get("ok"):
            access_token = token_info["access_token"]
            refresh_token = token_info.get("refresh_token")
            expires_in = token_info.get("expires_in", 3600)
            team_id = token_info.get("team", {}).get("id")
            team_name = token_info.get("team", {}).get("name")

            # Store tokens (in production, use database)
            slack_tokens[user_id] = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": time.time() + expires_in,
                "team_id": team_id,
                "team_name": team_name,
            }

            # Update Slack service with access token
            slack_service.access_token = access_token

            # Clean up session
            del sessions[state_key]

            return jsonify(
                {
                    "ok": True,
                    "message": "Slack connected successfully",
                    "user_id": user_id,
                    "team_name": team_name,
                    "team_id": team_id,
                    "access_token": access_token,
                }
            )
        else:
            return jsonify(
                {"ok": False, "error": token_info.get("error", "Token exchange failed")}
            ), 400

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/slack/channels")
def slack_channels():
    """Get list of Slack channels"""
    user_id = request.args.get("user_id", "default_user")

    if user_id not in slack_tokens:
        return jsonify({"ok": False, "error": "User not authenticated with Slack"}), 401

    # Update service with current token
    slack_service.access_token = slack_tokens[user_id]["access_token"]

    result = slack_service.get_channels()
    return jsonify(result)


@app.route("/api/slack/users")
def slack_users():
    """Get list of Slack users"""
    user_id = request.args.get("user_id", "default_user")

    if user_id not in slack_tokens:
        return jsonify({"ok": False, "error": "User not authenticated with Slack"}), 401

    # Update service with current token
    slack_service.access_token = slack_tokens[user_id]["access_token"]

    result = slack_service.get_users()
    return jsonify(result)


@app.route("/api/slack/send-message", methods=["POST"])
def slack_send_message():
    """Send message to Slack channel"""
    user_id = request.json.get("user_id", "default_user")
    channel = request.json.get("channel")
    text = request.json.get("text")

    if not channel or not text:
        return jsonify({"ok": False, "error": "Channel and text are required"}), 400

    if user_id not in slack_tokens:
        return jsonify({"ok": False, "error": "User not authenticated with Slack"}), 401

    # Update service with current token
    slack_service.access_token = slack_tokens[user_id]["access_token"]

    result = slack_service.send_message(channel, text)
    return jsonify(result)


@app.route("/api/slack/status")
def slack_status():
    """Get Slack connection status"""
    user_id = request.args.get("user_id", "default_user")

    if user_id in slack_tokens:
        token_info = slack_tokens[user_id]
        is_expired = time.time() > token_info["expires_at"]

        return jsonify(
            {
                "ok": True,
                "connected": True,
                "expired": is_expired,
                "team_name": token_info.get("team_name"),
                "team_id": token_info.get("team_id"),
            }
        )
    else:
        return jsonify({"ok": True, "connected": False, "expired": False})


if __name__ == "__main__":
    print("🚀 STARTING ATOM BACKEND WITH SLACK INTEGRATION")
    print("================================================")
    print("📋 Configuration:")
    print(f"   • Asana Client ID: {os.getenv('ASANA_CLIENT_ID', 'Not set')}")
    print(
        f"   • Slack Client ID: {SLACK_CLIENT_ID if SLACK_CLIENT_ID != 'YOUR_SLACK_CLIENT_ID' else 'Not set'}"
    )
    print("")
    print("🌐 Available Endpoints:")
    print("   • Health: http://localhost:8000/health")
    print(
        "   • Asana OAuth: http://localhost:8000/api/auth/asana/authorize?user_id=test"
    )
    print(
        "   • Slack OAuth: http://localhost:8000/api/auth/slack/authorize?user_id=test"
    )
    print("   • Slack Channels: http://localhost:8000/api/slack/channels?user_id=test")
    print("   • Slack Users: http://localhost:8000/api/slack/users?user_id=test")
    print("")
    print("🔐 OAuth Flows:")
    print("   1. Visit /api/auth/slack/authorize to get auth URL")
    print("   2. Complete authorization in Slack")
    print("   3. Slack redirects to /api/auth/slack/callback")
    print("   4. Backend exchanges code for access token")
    print("")

    app.run(host="0.0.0.0", port=8000, debug=True)
