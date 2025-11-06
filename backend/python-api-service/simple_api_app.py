#!/usr/bin/env python3
"""
🚀 SIMPLE API APP - Google Integration Testing Only
Minimal backend for Google integration tests
"""

import os
import logging
from datetime import datetime
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

# Import Google enhanced API
try:
    from google_enhanced_api import google_enhanced_bp
    app.register_blueprint(google_enhanced_bp, url_prefix="")
    logging.info("Enhanced Google API registered successfully")
except ImportError as e:
    logging.warning(f"Enhanced Google API not available: {e}")

# Basic health endpoint
@app.route("/health")
def health_check():
    """Basic health check"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "simple-api",
        "version": "1.0.0"
    })

# OAuth URL endpoint (needed for tests)
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

if __name__ == "__main__":
    port = int(os.getenv("PYTHON_API_PORT", 5058))
    logger.info(f"Starting simple API server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=True)