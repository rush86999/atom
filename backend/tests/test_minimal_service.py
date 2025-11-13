#!/usr/bin/env python3
"""
Minimal Backend Test Service
Verifies frontend-backend integration
"""

from flask import Flask, jsonify
from flask_cors import CORS
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

@app.route('/healthz')
def health_check():
    """Basic health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': 'test-v1.0.0',
        'service': 'ATOM Backend Test'
    })

@app.route('/api/<service>/health')
def service_health(service):
    """Service health check endpoint"""
    # Simulate different service responses
    services = {
        'gmail': {'status': 'connected', 'provider': 'Google'},
        'slack': {'status': 'connected', 'provider': 'Slack'},
        'asana': {'status': 'connected', 'provider': 'Asana'},
        'github': {'status': 'connected', 'provider': 'GitHub'},
        'notion': {'status': 'connected', 'provider': 'Notion'},
        'trello': {'status': 'connected', 'provider': 'Trello'},
        'outlook': {'status': 'connected', 'provider': 'Microsoft'},
    }
    
    if service in services:
        return jsonify({
            'ok': True,
            'data': {
                'service': service,
                **services[service]
            },
            'timestamp': datetime.now().isoformat()
        })
    else:
        return jsonify({
            'ok': False,
            'error': {
                'code': 'SERVICE_NOT_FOUND',
                'message': f'Service {service} not available'
            }
        }), 404

@app.route('/api/test')
def test_endpoint():
    """General test endpoint"""
    return jsonify({
        'ok': True,
        'message': 'Backend API is working',
        'timestamp': datetime.now().isoformat(),
        'environment': os.getenv('NODE_ENV', 'development')
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5058))
    print(f"🚀 Starting ATOM Backend Test Service on port {port}")
    print(f"📊 Health check: http://localhost:{port}/healthz")
    print(f"🔗 API test: http://localhost:{port}/api/test")
    app.run(host='0.0.0.0', port=port, debug=True)