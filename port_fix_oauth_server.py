#!/usr/bin/env python3
"""
OAuth Server on Different Port
"""

import os
import socket
from flask import Flask, jsonify

def is_port_available(port):
    """Check if port is available"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', port))
            s.close()
        return True
    except:
        return False

# Find available port
TEST_PORT = 5058
if not is_port_available(TEST_PORT):
    TEST_PORT = 5059
    if not is_port_available(TEST_PORT):
        TEST_PORT = 5060
        if not is_port_available(TEST_PORT):
            TEST_PORT = 5061

print(f"🔧 Port 5058 available: {is_port_available(5058)}")
print(f"🔧 Using port: {TEST_PORT}")

# Load GitHub credentials
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')

app = Flask(__name__)

@app.route("/")
def index():
    return jsonify({
        "message": "OAuth Server Running",
        "port": TEST_PORT,
        "github_client_id": GITHUB_CLIENT_ID[:10] if GITHUB_CLIENT_ID else None,
        "status": "testing"
    })

@app.route("/healthz")
def health():
    return jsonify({
        "status": "ok",
        "message": "OAuth server is working",
        "port": TEST_PORT
    })

@app.route("/api/auth/github/status")
def github_status():
    return jsonify({
        "ok": True,
        "service": "github",
        "status": "connected" if GITHUB_CLIENT_ID else "needs_credentials",
        "credentials": "real" if GITHUB_CLIENT_ID else "placeholder",
        "client_id": GITHUB_CLIENT_ID,
        "message": "GitHub OAuth test working"
    })

@app.route("/api/auth/github/authorize")
def github_authorize():
    user_id = request.args.get("user_id", "test_user")
    
    if GITHUB_CLIENT_ID:
        return jsonify({
            "ok": True,
            "service": "github",
            "user_id": user_id,
            "credentials": "real",
            "client_id": GITHUB_CLIENT_ID,
            "auth_url": f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&redirect_uri=http://localhost:{TEST_PORT}/api/auth/github/callback&scope=repo user",
            "message": "GitHub OAuth working with real credentials"
        })
    else:
        return jsonify({
            "ok": True,
            "service": "github",
            "user_id": user_id,
            "credentials": "placeholder",
            "message": "GitHub OAuth needs real credentials"
        })

if __name__ == "__main__":
    print("🚀 OAUTH SERVER WITH PORT FIX")
    print("=" * 50)
    print(f"🌐 Starting on http://localhost:{TEST_PORT}")
    print(f"🔧 GitHub Client ID: {'LOADED' if GITHUB_CLIENT_ID else 'MISSING'}")
    print("=" * 50)
    
    try:
        app.run(host='127.0.0.1', port=TEST_PORT, debug=False)
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        exit(1)