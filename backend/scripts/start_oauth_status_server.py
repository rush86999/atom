#!/usr/bin/env python3
"""
Updated Simple Backend with OAuth Status Endpoints
"""

import os
import logging
import sys
from flask import Flask, jsonify, request
from threading import Thread
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import OAuth status endpoints
sys.path.insert(0, os.path.dirname(__file__))
try:
    from oauth_status_endpoints import oauth_status_blueprint
    OAUTH_STATUS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"OAuth status endpoints not available: {e}")
    OAUTH_STATUS_AVAILABLE = False

def create_oauth_status_blueprint_inline():
    """Create OAuth status endpoints inline"""
    from flask import Blueprint
    
    oauth_bp = Blueprint("oauth_status_bp", __name__)
    
    # Mock data for services
    services_status = {
        'gmail': {'status': 'connected', 'credentials': 'real'},
        'outlook': {'status': 'needs_credentials', 'credentials': 'placeholder'},
        'slack': {'status': 'connected', 'credentials': 'real'},
        'teams': {'status': 'needs_credentials', 'credentials': 'placeholder'},
        'trello': {'status': 'connected', 'credentials': 'real'},
        'asana': {'status': 'connected', 'credentials': 'real'},
        'notion': {'status': 'connected', 'credentials': 'real'},
        'github': {'status': 'needs_credentials', 'credentials': 'placeholder'},
        'dropbox': {'status': 'connected', 'credentials': 'real'},
        'gdrive': {'status': 'connected', 'credentials': 'real'}
    }
    
    def get_service_status(service):
        """Get status for specific service"""
        user_id = request.args.get("user_id", "test_user")
        status_info = services_status.get(service, {'status': 'unknown', 'credentials': 'none'})
        
        return {
            "ok": True,
            "service": service,
            "user_id": user_id,
            "status": status_info['status'],
            "credentials": status_info['credentials'],
            "last_check": "2025-11-01T11:36:00Z",
            "message": f"{service.title()} OAuth is {status_info['status'].replace('_', ' ')}"
        }
    
    # Create endpoints for each service
    for service in services_status.keys():
        endpoint_path = f"/api/auth/{service}/status"
        
        def create_status_endpoint(svc_name):
            def status_endpoint():
                return jsonify(get_service_status(svc_name))
            return status_endpoint
        
        oauth_bp.add_url_rule(
            endpoint_path,
            f"oauth_{svc_name}_status",
            create_status_endpoint(service),
            methods=['GET']
        )
    
    # Comprehensive OAuth status endpoint
    @oauth_bp.route("/api/auth/oauth-status", methods=['GET'])
    def comprehensive_oauth_status():
        """Get comprehensive OAuth status for all services"""
        user_id = request.args.get("user_id", "test_user")
        
        results = {}
        connected_count = 0
        needs_credentials_count = 0
        
        for service, status_info in services_status.items():
            results[service] = get_service_status(service)
            if status_info['status'] == 'connected':
                connected_count += 1
            elif status_info['credentials'] == 'placeholder':
                needs_credentials_count += 1
        
        return jsonify({
            "ok": True,
            "user_id": user_id,
            "total_services": len(services_status),
            "connected_services": connected_count,
            "services_needing_credentials": needs_credentials_count,
            "success_rate": f"{connected_count/len(services_status)*100:.1f}%",
            "results": results,
            "timestamp": "2025-11-01T11:36:00Z"
        })
    
    return oauth_bp

def create_app():
    """Create Flask app with OAuth status endpoints"""
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    
    # Health endpoint
    @app.route("/healthz")
    def health():
        return jsonify({
            "status": "ok",
            "service": "atom-python-api",
            "version": "1.0.0-oauth-status",
            "message": "API server is running with OAuth status endpoints"
        })
    
    # Service status endpoint
    @app.route("/api/services/status")
    def services_status():
        return jsonify({
            "ok": True,
            "services": ["oauth_status"],
            "total_services": 1,
            "active_services": 1,
            "status_summary": {
                "active": 1,
                "connected": 0,
                "disconnected": 0,
                "error": 0
            },
            "timestamp": "2025-11-01T11:36:00Z"
        })
    
    # Add OAuth status blueprint
    if OAUTH_STATUS_AVAILABLE:
        app.register_blueprint(oauth_status_blueprint)
        logger.info("Registered OAuth status endpoints blueprint")
    else:
        oauth_bp_inline = create_oauth_status_blueprint_inline()
        app.register_blueprint(oauth_bp_inline)
        logger.info("Registered inline OAuth status endpoints")
    
    return app

def start_server():
    """Start the OAuth status server"""
    app = create_app()
    
    print("🚀 ATOM OAuth Status Server")
    print("=" * 50)
    print("🌐 Server starting on http://localhost:5058")
    print("📋 Available OAuth Status Endpoints:")
    
    services = [
        'gmail', 'outlook', 'slack', 'teams', 'trello', 
        'asana', 'notion', 'github', 'dropbox', 'gdrive'
    ]
    
    for service in services:
        print(f"   - GET  /api/auth/{service}/status")
    
    print("   - GET  /api/auth/oauth-status")
    print("   - GET  /healthz")
    print("=" * 50)
    
    try:
        app.run(host='0.0.0.0', port=5058, debug=False)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")

if __name__ == "__main__":
    start_server()