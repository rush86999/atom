#!/usr/bin/env python3
"""
OAuth Status Endpoints Implementation
"""

from flask import Blueprint, jsonify, request

def create_oauth_status_blueprint():
    """Create OAuth status endpoints blueprint"""
    
    oauth_status_bp = Blueprint("oauth_status_bp", __name__)
    
    def mock_oauth_status(service_name):
        """Mock OAuth status for development"""
        user_id = request.args.get("user_id", "test_user")
        
        # Services with real credentials from .env file
        real_credential_services = [
            'gmail', 'slack', 'trello', 'asana', 'notion', 'dropbox', 'gdrive'
        ]
        
        if service_name in real_credential_services:
            return {
                "ok": True,
                "status": "connected",
                "service": service_name,
                "user_id": user_id,
                "credentials": "real_configured",
                "last_check": "2025-11-01T11:36:00Z",
                "message": f"{service_name.title()} OAuth is operational with real credentials"
            }
        else:
            return {
                "ok": True,
                "status": "needs_credentials",
                "service": service_name,
                "user_id": user_id,
                "credentials": "placeholder",
                "last_check": "2025-11-01T11:36:00Z",
                "message": f"{service_name.title()} OAuth needs real credentials configuration"
            }
    
    # OAuth status endpoints for all services
    services = [
        'gmail', 'outlook', 'slack', 'teams', 'trello', 
        'asana', 'notion', 'github', 'dropbox', 'gdrive'
    ]
    
    for service in services:
        def create_status_endpoint(svc_name):
            def status_endpoint():
                return jsonify(mock_oauth_status(svc_name))
            return status_endpoint
        
        endpoint_path = f"/api/auth/{service}/status"
        oauth_status_bp.add_url_rule(
            endpoint_path, 
            f"oauth_{service}_status", 
            create_status_endpoint(service), 
            methods=['GET']
        )
    
    # Comprehensive OAuth status endpoint
    @oauth_status_bp.route("/api/auth/oauth-status", methods=['GET'])
    def comprehensive_oauth_status():
        """Get comprehensive OAuth status for all services"""
        user_id = request.args.get("user_id", "test_user")
        
        status_results = {}
        for service in services:
            status_results[service] = mock_oauth_status(service)
        
        return jsonify({
            "ok": True,
            "user_id": user_id,
            "total_services": len(services),
            "connected_services": len([s for s in services if s in [
                'gmail', 'slack', 'trello', 'asana', 'notion', 'dropbox', 'gdrive'
            ]]),
            "services_needing_credentials": ['outlook', 'teams', 'github'],
            "results": status_results,
            "timestamp": "2025-11-01T11:36:00Z"
        })
    
    return oauth_status_bp

# Create the blueprint
oauth_status_blueprint = create_oauth_status_blueprint()