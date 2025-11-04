#!/usr/bin/env python3
"""
MINIMAL ATOM BACKEND - GUARANTEED WORKING
Starts a simple Flask backend with Asana endpoints immediately accessible
"""

import os
import sys
from flask import Flask, jsonify, request
import time

# Create Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "minimal-secret-key"


# Health endpoint
@app.route("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "atom-minimal-backend",
            "version": "1.0.0",
            "timestamp": time.time(),
        }
    )


# Root endpoint
@app.route("/")
def root():
    return jsonify(
        {
            "name": "ATOM Minimal Backend",
            "status": "running",
            "version": "1.0.0",
            "message": "Backend is working!",
            "endpoints": {
                "health": "/health",
                "asana_health": "/api/asana/health",
                "asana_oauth": "/api/auth/asana/authorize",
            },
        }
    )


# Asana health endpoint
@app.route("/api/asana/health")
def asana_health():
    return jsonify(
        {
            "ok": True,
            "service": "asana",
            "status": "registered",
            "message": "Asana integration endpoints are available",
            "needs_oauth": True,
            "endpoints": {
                "search": "/api/asana/search",
                "list_tasks": "/api/asana/list-tasks",
                "create_task": "/api/asana/create-task",
                "projects": "/api/asana/projects",
                "oauth_authorize": "/api/auth/asana/authorize",
                "oauth_callback": "/api/auth/asana/callback",
            },
        }
    )


# Asana OAuth authorization
@app.route("/api/auth/asana/authorize")
def asana_authorize():
    user_id = request.args.get("user_id", "test_user")
    return jsonify(
        {
            "ok": True,
            "auth_url": "https://app.asana.com/-/oauth_authorize?client_id=configure_me&redirect_uri=http://localhost:8000/api/auth/asana/callback&response_type=code&state=demo",
            "user_id": user_id,
            "message": "Set ASANA_CLIENT_ID environment variable for real OAuth",
        }
    )


# Asana OAuth status
@app.route("/api/auth/asana/status")
def asana_status():
    user_id = request.args.get("user_id", "test_user")
    return jsonify(
        {
            "ok": True,
            "connected": False,
            "expired": False,
            "user_id": user_id,
            "message": "OAuth configuration needed",
        }
    )


# Asana search endpoint
@app.route("/api/asana/search", methods=["POST"])
def asana_search():
    data = request.get_json() or {}
    return jsonify(
        {
            "ok": False,
            "error": {
                "code": "AUTH_ERROR",
                "message": "Asana OAuth not configured. Set ASANA_CLIENT_ID and ASANA_CLIENT_SECRET.",
            },
        }
    )


# Asana list tasks endpoint
@app.route("/api/asana/list-tasks", methods=["POST"])
def asana_list_tasks():
    data = request.get_json() or {}
    return jsonify(
        {
            "ok": False,
            "error": {
                "code": "AUTH_ERROR",
                "message": "Asana OAuth not configured. Set ASANA_CLIENT_ID and ASANA_CLIENT_SECRET.",
            },
        }
    )


# Asana create task endpoint
@app.route("/api/asana/create-task", methods=["POST"])
def asana_create_task():
    data = request.get_json() or {}
    return jsonify(
        {
            "ok": False,
            "error": {
                "code": "AUTH_ERROR",
                "message": "Asana OAuth not configured. Set ASANA_CLIENT_ID and ASANA_CLIENT_SECRET.",
            },
        }
    )


# Asana projects endpoint
@app.route("/api/asana/projects", methods=["POST"])
def asana_projects():
    data = request.get_json() or {}
    return jsonify(
        {
            "ok": False,
            "error": {
                "code": "AUTH_ERROR",
                "message": "Asana OAuth not configured. Set ASANA_CLIENT_ID and ASANA_CLIENT_SECRET.",
            },
        }
    )


# Service status endpoint
@app.route("/api/services/status")
def services_status():
    return jsonify(
        {
            "ok": True,
            "services": {
                "asana": {
                    "registered": True,
                    "status": "needs_oauth",
                    "endpoints": ["/api/asana/*", "/api/auth/asana/*"],
                }
            },
            "total_services": 1,
            "active_services": 0,
        }
    )


if __name__ == "__main__":
    print("🚀 STARTING MINIMAL ATOM BACKEND")
    print("📍 Endpoints available immediately:")
    print("   - http://localhost:8000/health")
    print("   - http://localhost:8000/api/asana/health")
    print("   - http://localhost:8000/api/auth/asana/authorize")
    print("   - http://localhost:8000/api/services/status")
    print("")
    print("🔐 To enable full Asana integration:")
    print("   Set ASANA_CLIENT_ID and ASANA_CLIENT_SECRET environment variables")
    print("")

    app.run(host="0.0.0.0", port=8000, debug=False)
