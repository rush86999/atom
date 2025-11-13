import os
import sys
from flask import Flask, jsonify, request, redirect
import requests
import json
import time
from urllib.parse import urlencode

# Set environment variables with your actual credentials
os.environ["ASANA_CLIENT_ID"] = "1211551350187489"
os.environ["ASANA_CLIENT_SECRET"] = "a4d944583e2e3fd199b678ece03762b0"
os.environ["ASANA_REDIRECT_URI"] = "http://localhost:8000/api/auth/asana/callback"

# Create Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "real-asana-backend-secret"

# Store temporary session data (in production, use proper session management)
sessions = {}


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "atom-real-asana-backend",
            "version": "1.0.0",
            "timestamp": time.time(),
            "asana_configured": bool(
                os.getenv("ASANA_CLIENT_ID") and os.getenv("ASANA_CLIENT_SECRET")
            ),
        }
    )


@app.route("/")
def root():
    return jsonify(
        {
            "name": "ATOM Backend with Real Asana",
            "status": "running",
            "asana_client_id": os.getenv("ASANA_CLIENT_ID", "not_set"),
            "endpoints": {
                "health": "/health",
                "asana_health": "/api/asana/health",
                "asana_oauth": "/api/auth/asana/authorize",
                "asana_callback": "/api/auth/asana/callback",
            },
        }
    )


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
    import secrets

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
            "message": "Navigate to auth_url to complete OAuth flow",
        }
    )


@app.route("/api/auth/asana/callback")
def asana_callback():
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    if error:
        return jsonify({"ok": False, "error": f"OAuth error: {error}"}), 400

    if not code:
        return jsonify({"ok": False, "error": "No authorization code received"}), 400

    if not state or state not in sessions:
        return jsonify(
            {"ok": False, "error": "Invalid or missing state parameter"}
        ), 400

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
        response = requests.post(
            "https://app.asana.com/-/oauth_token",
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )

        if response.status_code == 200:
            token_info = response.json()

            # Get user info to verify the token works
            headers = {"Authorization": f"Bearer {token_info['access_token']}"}
            user_response = requests.get(
                "https://app.asana.com/api/1.0/users/me", headers=headers, timeout=10
            )

            user_info = user_response.json() if user_response.status_code == 200 else {}

            # Clean up session
            if state in sessions:
                del sessions[state]

            return jsonify(
                {
                    "ok": True,
                    "message": "Asana OAuth completed successfully!",
                    "user_id": sessions.get(state, {}).get("user_id", "unknown"),
                    "access_token": f"{token_info['access_token'][:10]}...",  # Don't expose full token
                    "token_type": token_info.get("token_type"),
                    "expires_in": token_info.get("expires_in"),
                    "user": {
                        "name": user_info.get("data", {}).get("name"),
                        "email": user_info.get("data", {}).get("email"),
                    },
                }
            )
        else:
            return jsonify(
                {
                    "ok": False,
                    "error": f"Token exchange failed: {response.status_code}",
                    "details": response.text,
                }
            ), 400

    except Exception as e:
        return jsonify({"ok": False, "error": f"OAuth callback failed: {str(e)}"}), 500


@app.route("/api/auth/asana/status")
def asana_status():
    user_id = request.args.get("user_id", "unknown")
    return jsonify(
        {
            "ok": True,
            "connected": False,  # This would check actual token storage in production
            "user_id": user_id,
            "client_configured": bool(os.getenv("ASANA_CLIENT_ID")),
            "message": "OAuth ready - use /api/auth/asana/authorize to connect",
        }
    )


@app.route("/api/services/status")
def services_status():
    return jsonify(
        {
            "ok": True,
            "services": {
                "asana": {
                    "registered": True,
                    "status": "oauth_ready",
                    "client_id": os.getenv("ASANA_CLIENT_ID", "not_set"),
                    "endpoints": ["/api/asana/*", "/api/auth/asana/*"],
                }
            },
        }
    )


if __name__ == "__main__":
    print("🚀 STARTING ATOM BACKEND WITH REAL ASANA CREDENTIALS")
    print("=" * 60)
    print(f"📋 Client ID: {os.getenv('ASANA_CLIENT_ID')}")
    print(f"📍 Redirect URI: {os.getenv('ASANA_REDIRECT_URI')}")
    print("")
    print("🌐 Available Endpoints:")
    print("   - http://localhost:8000/health")
    print("   - http://localhost:8000/api/asana/health")
    print("   - http://localhost:8000/api/auth/asana/authorize?user_id=test")
    print("   - http://localhost:8000/api/auth/asana/callback")
    print("")
    print("🔐 OAuth Flow:")
    print("   1. Visit /api/auth/asana/authorize to get auth URL")
    print("   2. Complete authorization in Asana")
    print("   3. Asana redirects to /api/auth/asana/callback")
    print("   4. Backend exchanges code for access token")
    print("")

    app.run(host="0.0.0.0", port=8000, debug=False)
