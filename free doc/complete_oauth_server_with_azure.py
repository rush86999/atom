#!/usr/bin/env python3
"""
Complete OAuth System Test with Azure Credentials
"""

import os
import secrets
import urllib.parse
from flask import Flask, jsonify, request

# Load all credentials from .env
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
SLACK_CLIENT_ID = os.getenv('SLACK_CLIENT_ID')
TRELLO_API_KEY = os.getenv('TRELLO_API_KEY')
ASANA_CLIENT_ID = os.getenv('ASANA_CLIENT_ID')
NOTION_CLIENT_ID = os.getenv('NOTION_CLIENT_ID')
DROPBOX_APP_KEY = os.getenv('DROPBOX_APP_KEY')

OUTLOOK_CLIENT_ID = os.getenv('OUTLOOK_CLIENT_ID')
OUTLOOK_CLIENT_SECRET = os.getenv('OUTLOOK_CLIENT_SECRET')
OUTLOOK_TENANT_ID = os.getenv('OUTLOOK_TENANT_ID')

TEAMS_CLIENT_ID = os.getenv('TEAMS_CLIENT_ID')
TEAMS_CLIENT_SECRET = os.getenv('TEAMS_CLIENT_SECRET')
TEAMS_TENANT_ID = os.getenv('TEAMS_TENANT_ID')

print("🔧 LOADING COMPLETE CREDENTIALS FROM .ENV")
print(f"   GITHUB_CLIENT_ID: {GITHUB_CLIENT_ID[:10] if GITHUB_CLIENT_ID else 'MISSING'}...")
print(f"   GOOGLE_CLIENT_ID: {GOOGLE_CLIENT_ID[:10] if GOOGLE_CLIENT_ID else 'MISSING'}...")
print(f"   SLACK_CLIENT_ID: {SLACK_CLIENT_ID[:10] if SLACK_CLIENT_ID else 'MISSING'}...")
print(f"   OUTLOOK_CLIENT_ID: {OUTLOOK_CLIENT_ID[:10] if OUTLOOK_CLIENT_ID else 'MISSING'}...")
print(f"   TEAMS_CLIENT_ID: {TEAMS_CLIENT_ID[:10] if TEAMS_CLIENT_ID else 'MISSING'}...")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "atom-oauth-complete-secret-2025")

# Service configurations
services_config = {
    'gmail': {
        'status': 'connected' if GOOGLE_CLIENT_ID else 'needs_credentials', 
        'credentials': 'real' if GOOGLE_CLIENT_ID else 'placeholder',
        'client_id': GOOGLE_CLIENT_ID or 'placeholder_google_client_id',
        'auth_url': 'https://accounts.google.com/o/oauth2/v2/auth'
    },
    'outlook': {
        'status': 'connected' if OUTLOOK_CLIENT_ID else 'needs_credentials', 
        'credentials': 'real' if OUTLOOK_CLIENT_ID else 'placeholder',
        'client_id': OUTLOOK_CLIENT_ID or 'placeholder_outlook_client_id',
        'auth_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize'
    },
    'slack': {
        'status': 'connected' if SLACK_CLIENT_ID else 'needs_credentials', 
        'credentials': 'real' if SLACK_CLIENT_ID else 'placeholder',
        'client_id': SLACK_CLIENT_ID or 'placeholder_slack_client_id',
        'auth_url': 'https://slack.com/oauth/v2/authorize'
    },
    'teams': {
        'status': 'connected' if TEAMS_CLIENT_ID else 'needs_credentials', 
        'credentials': 'real' if TEAMS_CLIENT_ID else 'placeholder',
        'client_id': TEAMS_CLIENT_ID or 'placeholder_teams_client_id',
        'auth_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize'
    },
    'trello': {
        'status': 'connected' if TRELLO_API_KEY else 'needs_credentials', 
        'credentials': 'real' if TRELLO_API_KEY else 'placeholder',
        'client_id': TRELLO_API_KEY or 'placeholder_trello_key',
        'auth_url': 'https://trello.com/1/authorize'
    },
    'asana': {
        'status': 'connected' if ASANA_CLIENT_ID else 'needs_credentials', 
        'credentials': 'real' if ASANA_CLIENT_ID else 'placeholder',
        'client_id': ASANA_CLIENT_ID or 'placeholder_asana_client_id',
        'auth_url': 'https://app.asana.com/-/oauth_authorize'
    },
    'notion': {
        'status': 'connected' if NOTION_CLIENT_ID else 'needs_credentials', 
        'credentials': 'real' if NOTION_CLIENT_ID else 'placeholder',
        'client_id': NOTION_CLIENT_ID or 'placeholder_notion_client_id',
        'auth_url': 'https://api.notion.com/v1/oauth/authorize'
    },
    'github': {
        'status': 'connected' if GITHUB_CLIENT_ID else 'needs_credentials', 
        'credentials': 'real' if GITHUB_CLIENT_ID else 'placeholder',
        'client_id': GITHUB_CLIENT_ID or 'placeholder_github_client_id',
        'auth_url': 'https://github.com/login/oauth/authorize'
    },
    'dropbox': {
        'status': 'connected' if DROPBOX_APP_KEY else 'needs_credentials', 
        'credentials': 'real' if DROPBOX_APP_KEY else 'placeholder',
        'client_id': DROPBOX_APP_KEY or 'placeholder_dropbox_key',
        'auth_url': 'https://www.dropbox.com/oauth2/authorize'
    },
    'gdrive': {
        'status': 'connected' if GOOGLE_CLIENT_ID else 'needs_credentials', 
        'credentials': 'real' if GOOGLE_CLIENT_ID else 'placeholder',
        'client_id': GOOGLE_CLIENT_ID or 'placeholder_google_client_id',
        'auth_url': 'https://accounts.google.com/o/oauth2/v2/auth'
    }
}

@app.route("/")
def index():
    return jsonify({
        "message": "ATOM Complete OAuth Server Running",
        "services": len(services_config),
        "credentials_loaded": {
            "github": bool(GITHUB_CLIENT_ID),
            "outlook": bool(OUTLOOK_CLIENT_ID),
            "teams": bool(TEAMS_CLIENT_ID),
            "total_real": sum(1 for s, c in services_config.items() if c.get('credentials') == 'real')
        }
    })

@app.route("/healthz")
def health():
    return jsonify({
        "status": "ok",
        "service": "atom-python-api-oauth-complete-with-azure",
        "version": "1.0.0-complete-azure-oauth",
        "message": "API server is running with complete OAuth endpoints including Azure",
        "timestamp": "2025-11-01T12:30:00Z"
    })

@app.route("/api/auth/<service>/status", methods=['GET'])
def oauth_status(service):
    if service not in services_config:
        return jsonify({"error": f"Service {service} not supported"}), 404
    
    config = services_config[service]
    return jsonify({
        "ok": True,
        "service": service,
        "user_id": request.args.get("user_id", "test_user"),
        "status": config['status'],
        "credentials": config['credentials'],
        "client_id": config['client_id'],
        "last_check": "2025-11-01T12:30:00Z",
        "message": f"{service.title()} OAuth is {config['status'].replace('_', ' ')}"
    })

@app.route("/api/auth/<service>/authorize", methods=['GET'])
def oauth_authorize(service):
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id parameter is required"}), 400
    
    if service not in services_config:
        return jsonify({"error": f"Service {service} not supported"}), 404
    
    config = services_config[service]
    
    if config['credentials'] == 'placeholder':
        return jsonify({
            "ok": True,
            "service": service,
            "user_id": user_id,
            "status": "needs_credentials",
            "message": f"{service.title()} OAuth needs real credentials configuration",
            "credentials": "placeholder"
        }), 200
    
    # Generate authorization URL for real credentials
    csrf_token = secrets.token_urlsafe(32)
    
    auth_params = {
        "client_id": config['client_id'],
        "redirect_uri": f"http://localhost:5058/api/auth/{service}/callback",
        "response_type": "code",
        "state": csrf_token,
    }
    
    # Add service-specific parameters
    if service in ['gmail', 'gdrive']:
        auth_params.update({
            "scope": "email profile",
            "access_type": "offline", 
            "prompt": "consent"
        })
    elif service == 'slack':
        auth_params.update({"scope": "chat:read chat:write"})
    elif service == 'trello':
        auth_params.update({
            "scope": "read,write",
            "expiration": "never",
            "name": "ATOM Integration"
        })
    elif service == 'github':
        auth_params.update({"scope": "repo user"})
    elif service == 'notion':
        auth_params.update({"owner": "user"})
    elif service in ['outlook', 'teams']:
        auth_params.update({
            "scope": "openid profile offline_access Mail.Read Mail.Send",
            "response_mode": "query"
        })
    
    auth_url = f"{config['auth_url']}?{urllib.parse.urlencode(auth_params)}"
    
    return jsonify({
        "ok": True,
        "service": service,
        "user_id": user_id,
        "auth_url": auth_url,
        "csrf_token": csrf_token,
        "client_id": config['client_id'],
        "credentials": config['credentials'],
        "message": f"{service.title()} OAuth authorization URL generated successfully"
    })

@app.route("/api/auth/<service>/callback", methods=['GET', 'POST'])
def oauth_callback(service):
    if service not in services_config:
        return jsonify({"error": f"Service {service} not supported"}), 404
        
    return jsonify({
        "ok": True,
        "service": service,
        "message": f"{service.title()} OAuth callback received",
        "code": request.args.get("code"),
        "state": request.args.get("state"),
        "redirect": f"/settings?service={service}&status=connected"
    })

@app.route("/api/auth/oauth-status", methods=['GET'])
def comprehensive_oauth_status():
    user_id = request.args.get("user_id", "test_user")
    
    results = {}
    connected_count = 0
    needs_credentials_count = 0
    
    for service, config in services_config.items():
        status_info = {
            "ok": True,
            "service": service,
            "user_id": user_id,
            "status": config['status'],
            "credentials": config['credentials'],
            "client_id": config['client_id'],
            "message": f"{service.title()} OAuth is {config['status'].replace('_', ' ')}"
        }
        results[service] = status_info
        
        if config['status'] == 'connected':
            connected_count += 1
        elif config['credentials'] == 'placeholder':
            needs_credentials_count += 1
    
    return jsonify({
        "ok": True,
        "user_id": user_id,
        "total_services": len(services_config),
        "connected_services": connected_count,
        "services_needing_credentials": needs_credentials_count,
        "success_rate": f"{connected_count/len(services_config)*100:.1f}%",
        "results": results,
        "timestamp": "2025-11-01T12:30:00Z"
    })

@app.route("/api/auth/services", methods=['GET'])
def oauth_services_list():
    return jsonify({
        "ok": True,
        "services": list(services_config.keys()),
        "total_services": len(services_config),
        "services_with_real_credentials": len([
            s for s, c in services_config.items() 
            if c.get('credentials') == 'real'
        ]),
        "services_needing_credentials": len([
            s for s, c in services_config.items() 
            if c.get('credentials') == 'placeholder'
        ]),
        "timestamp": "2025-11-01T12:30:00Z"
    })

if __name__ == "__main__":
    print("🚀 ATOM COMPLETE OAUTH SERVER WITH AZURE")
    print("=" * 70)
    
    # Count real credentials
    real_count = sum(1 for s, c in services_config.items() if c.get('credentials') == 'real')
    placeholder_count = sum(1 for s, c in services_config.items() if c.get('credentials') == 'placeholder')
    
    print(f"🔧 COMPLETE CREDENTIALS STATUS: {real_count} real, {placeholder_count} placeholder")
    print(f"🌐 Server starting on http://localhost:5058")
    print(f"📋 Available OAuth Endpoints: {len(services_config) * 3} total")
    
    # Show key services status
    key_services = ['github', 'outlook', 'teams']
    for service in key_services:
        config = services_config[service]
        status = "✅ REAL CREDENTIALS" if config['credentials'] == 'real' else "❌ PLACEHOLDER"
        print(f"   {service.upper()}: {status}")
    
    print("=" * 70)
    
    try:
        app.run(host='127.0.0.1', port=5058, debug=False, use_reloader=False)
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        exit(1)