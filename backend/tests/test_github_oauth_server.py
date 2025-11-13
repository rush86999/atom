#!/usr/bin/env python3
"""
OAuth Server with GitHub Credentials
"""

import os
import secrets
import urllib.parse
from flask import Flask, jsonify, request

# Load GitHub credentials from .env
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET')

print(f"🔧 GitHub Credentials Loaded:")
print(f"   Client ID: {GITHUB_CLIENT_ID[:10] if GITHUB_CLIENT_ID else 'NOT_FOUND'}...")
print(f"   Client Secret: {GITHUB_CLIENT_SECRET[:10] if GITHUB_CLIENT_SECRET else 'NOT_FOUND'}...")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-oauth-github")

@app.route("/api/auth/github/status", methods=['GET'])
def github_status():
    user_id = request.args.get("user_id", "test_user")
    
    if GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET:
        return jsonify({
            "ok": True,
            "service": "github",
            "user_id": user_id,
            "status": "connected" if GITHUB_CLIENT_ID else "needs_credentials",
            "credentials": "real" if GITHUB_CLIENT_ID else "placeholder",
            "client_id": GITHUB_CLIENT_ID,
            "last_check": "2025-11-01T12:15:00Z",
            "message": f"GitHub OAuth is {'connected' if GITHUB_CLIENT_ID else 'needs credentials'}"
        })
    else:
        return jsonify({
            "ok": True,
            "service": "github",
            "user_id": user_id,
            "status": "needs_credentials",
            "credentials": "placeholder",
            "client_id": "placeholder_github_client_id",
            "last_check": "2025-11-01T12:15:00Z",
            "message": "GitHub OAuth needs real credentials"
        })

@app.route("/api/auth/github/authorize", methods=['GET'])
def github_authorize():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id parameter is required"}), 400
    
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        return jsonify({
            "ok": True,
            "service": "github",
            "user_id": user_id,
            "status": "needs_credentials",
            "message": "GitHub OAuth needs real credentials configuration",
            "setup_guide": "Create GitHub OAuth app at https://github.com/settings/applications/new"
        }), 200
    
    # Generate authorization URL
    csrf_token = secrets.token_urlsafe(32)
    
    auth_params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": "http://localhost:5058/api/auth/github/callback",
        "response_type": "code",
        "scope": "repo user",
        "state": csrf_token,
    }
    
    auth_url = f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(auth_params)}"
    
    return jsonify({
        "ok": True,
        "service": "github",
        "user_id": user_id,
        "auth_url": auth_url,
        "csrf_token": csrf_token,
        "client_id": GITHUB_CLIENT_ID,
        "credentials": "real",
        "message": "GitHub OAuth authorization URL generated successfully"
    })

@app.route("/api/auth/github/callback", methods=['GET', 'POST'])
def github_callback():
    return jsonify({
        "ok": True,
        "service": "github",
        "message": "GitHub OAuth callback received",
        "code": request.args.get("code"),
        "state": request.args.get("state"),
        "redirect": f"/settings?service=github&status=connected"
    })

@app.route("/healthz")
def health():
    return jsonify({
        "status": "ok",
        "service": "atom-python-api-github-test",
        "version": "1.0.0-github-test",
        "message": "API server is running with GitHub OAuth test"
    })

if __name__ == "__main__":
    print("🚀 GitHub OAuth Test Server")
    print("=" * 40)
    print(f"🌐 Server starting on http://localhost:5058")
    print(f"📋 GitHub Credentials: {'LOADED' if GITHUB_CLIENT_ID else 'MISSING'}")
    print("📋 Available Endpoints:")
    print("   - GET  /api/auth/github/status")
    print("   - GET  /api/auth/github/authorize")
    print("   - GET/POST /api/auth/github/callback")
    print("   - GET  /healthz")
    print("=" * 40)
    
    app.run(host='0.0.0.0', port=5058, debug=False)