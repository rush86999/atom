#!/usr/bin/env python3
"""
Enhanced Integration Bridge System
Bridges Flask main app with FastAPI-based integrations
Provides unified interface across all integration types
"""

import os
import json
import logging
import httpx
import asyncio
import threading
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from flask import Flask, Blueprint, request, jsonify, g
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

@dataclass
class IntegrationEndpoint:
    """Integration endpoint configuration"""
    name: str
    type: 'flask' | 'fastapi' | 'external'
    base_url: str
    health_endpoint: str
    auth_required: bool = True
    timeout: float = 30.0
    retry_attempts: int = 3

@dataclass
class ServiceBridgeStatus:
    """Bridge status for a service"""
    service_name: str
    framework_type: str
    endpoint_url: str
    status: 'active' | 'inactive' | 'error' | 'degraded'
    last_check: str
    response_time: Optional[float] = None
    error_message: Optional[str] = None
    available_endpoints: List[str] = None

class FlaskFastAPIBridge:
    """Bridge system for Flask and FastAPI integrations"""
    
    def __init__(self, flask_app: Flask):
        self.flask_app = flask_app
        self.registered_endpoints: Dict[str, IntegrationEndpoint] = {}
        self.bridge_status: Dict[str, ServiceBridgeStatus] = {}
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.endpoint_mappings = self._discover_integrations()
        
        # Register bridge endpoints
        self._register_bridge_routes()
        
    def _discover_integrations(self) -> Dict[str, IntegrationEndpoint]:
        """Discover all integration endpoints and their types"""
        endpoints = {}
        
        # Define known integration endpoints
        integration_configs = {
            'hubspot': {
                'flask': {
                    'base_url': '/api/hubspot',
                    'health_endpoint': '/api/hubspot/health',
                    'type': 'flask'
                },
                'fastapi': {
                    'base_url': '/api/v2/hubspot',
                    'health_endpoint': '/api/v2/hubspot/health',
                    'type': 'fastapi'
                }
            },
            'slack': {
                'flask': {
                    'base_url': '/api/slack',
                    'health_endpoint': '/api/slack/health',
                    'type': 'flask'
                },
                'fastapi': {
                    'base_url': '/api/v2/slack',
                    'health_endpoint': '/api/v2/slack/health',
                    'type': 'fastapi'
                }
            },
            'jira': {
                'flask': {
                    'base_url': '/api/jira',
                    'health_endpoint': '/api/jira/health',
                    'type': 'flask'
                },
                'fastapi': {
                    'base_url': '/api/v2/jira',
                    'health_endpoint': '/api/v2/jira/health',
                    'type': 'fastapi'
                }
            },
            'linear': {
                'flask': {
                    'base_url': '/api/linear',
                    'health_endpoint': '/api/linear/health',
                    'type': 'flask'
                },
                'fastapi': {
                    'base_url': '/api/v2/linear',
                    'health_endpoint': '/api/v2/linear/health',
                    'type': 'fastapi'
                }
            },
            'salesforce': {
                'flask': {
                    'base_url': '/api/salesforce',
                    'health_endpoint': '/api/salesforce/health',
                    'type': 'flask'
                },
                'fastapi': {
                    'base_url': '/api/v2/salesforce',
                    'health_endpoint': '/api/v2/salesforce/health',
                    'type': 'fastapi'
                }
            },
            'xero': {
                'flask': {
                    'base_url': '/api/xero',
                    'health_endpoint': '/api/xero/health',
                    'type': 'flask'
                },
                'fastapi': {
                    'base_url': '/api/v2/xero',
                    'health_endpoint': '/api/v2/xero/health',
                    'type': 'fastapi'
                }
            }
        }
        
        # Detect which endpoints are available
        for integration, configs in integration_configs.items():
            # Check for Flask endpoints (registered in main app)
            if self._check_flask_endpoint_exists(configs['flask']['base_url']):
                endpoints[integration] = IntegrationEndpoint(
                    name=integration,
                    type='flask',
                    base_url=configs['flask']['base_url'],
                    health_endpoint=configs['flask']['health_endpoint']
                )
            
            # Check for FastAPI endpoints (might be running on different port)
            elif self._check_fastapi_endpoint_available(configs['fastapi']['base_url']):
                endpoints[integration] = IntegrationEndpoint(
                    name=integration,
                    type='fastapi',
                    base_url=configs['fastapi']['base_url'],
                    health_endpoint=configs['fastapi']['health_endpoint']
                )
        
        logger.info(f"Discovered {len(endpoints)} integration endpoints")
        return endpoints
    
    def _check_flask_endpoint_exists(self, endpoint_url: str) -> bool:
        """Check if Flask endpoint is registered"""
        try:
            with self.flask_app.app_context():
                # Check if URL rule exists
                for rule in self.flask_app.url_map.iter_rules():
                    if rule.rule == endpoint_url or rule.rule.startswith(endpoint_url.rstrip('/')):
                        return True
            return False
        except Exception as e:
            logger.warning(f"Failed to check Flask endpoint {endpoint_url}: {e}")
            return False
    
    def _check_fastapi_endpoint_available(self, endpoint_url: str) -> bool:
        """Check if FastAPI endpoint is available"""
        try:
            # This would typically check if FastAPI service is running
            # For now, we'll assume FastAPI endpoints might be available
            # In a real implementation, you might check environment variables
            # or try a health check
            return os.getenv(f"{endpoint_url.upper().replace('/API/V2/', '')}_FASTAPI_AVAILABLE", "false").lower() == "true"
        except Exception:
            return False
    
    def _register_bridge_routes(self):
        """Register bridge routes in Flask app"""
        
        @self.flask_app.route('/api/bridge/health', methods=['GET'])
        def bridge_health():
            """Overall bridge health status"""
            return jsonify({
                "status": "healthy",
                "bridge_type": "flask-fastapi",
                "registered_endpoints": len(self.registered_endpoints),
                "endpoint_mappings": list(self.endpoint_mappings.keys()),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        @self.flask_app.route('/api/bridge/status', methods=['GET'])
        def bridge_status():
            """Detailed bridge status for all integrations"""
            return self._get_comprehensive_bridge_status()
        
        @self.flask_app.route('/api/bridge/forward/<integration>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
        def forward_request(integration: str):
            """Forward requests to appropriate integration endpoint"""
            return self._forward_to_integration(integration)
        
        @self.flask_app.route('/api/bridge/unified/<integration>/<path:endpoint>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
        def unified_endpoint(integration: str, endpoint: str):
            """Unified endpoint that handles both Flask and FastAPI integrations"""
            return self._unified_integration_handler(integration, endpoint)
        
        # Register individual integration proxy endpoints
        for integration_name, endpoint_config in self.endpoint_mappings.items():
            self._register_integration_proxy(integration_name, endpoint_config)
    
    def _register_integration_proxy(self, integration_name: str, endpoint_config: IntegrationEndpoint):
        """Register proxy endpoints for a specific integration"""
        
        @self.flask_app.route(f'/api/proxy/{integration_name}/<path:endpoint>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
        def integration_proxy(endpoint: str, int_name=integration_name, config=endpoint_config):
            """Proxy requests to integration regardless of framework"""
            return self._proxy_request(int_name, config, endpoint)
    
    def _get_comprehensive_bridge_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all bridge endpoints"""
        try:
            # Get status for all registered endpoints
            status_report = {
                "bridge_status": "active",
                "total_integrations": len(self.endpoint_mappings),
                "framework_distribution": {
                    "flask": 0,
                    "fastapi": 0,
                    "external": 0
                },
                "integrations": {}
            }
            
            for integration_name, endpoint in self.endpoint_mappings.items():
                status_report["framework_distribution"][endpoint.type] += 1
                
                # Get integration status
                integration_status = self._get_integration_status(integration_name, endpoint)
                status_report["integrations"][integration_name] = integration_status
            
            # Calculate overall health
            healthy_count = sum(1 for status in status_report["integrations"].values() 
                              if status.get("status") == "active")
            total_count = len(status_report["integrations"])
            
            status_report["overall_health"] = {
                "status": "healthy" if healthy_count == total_count else "degraded" if healthy_count > 0 else "unhealthy",
                "healthy_integrations": healthy_count,
                "total_integrations": total_count,
                "health_percentage": (healthy_count / total_count * 100) if total_count > 0 else 0
            }
            
            status_report["timestamp"] = datetime.now(timezone.utc).isoformat()
            
            return jsonify(status_report), 200
            
        except Exception as e:
            logger.error(f"Failed to get bridge status: {e}")
            return jsonify({
                "bridge_status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }), 500
    
    def _get_integration_status(self, integration_name: str, endpoint: IntegrationEndpoint) -> Dict[str, Any]:
        """Get status for a specific integration"""
        try:
            if endpoint.type == 'flask':
                return self._check_flask_integration_status(integration_name, endpoint)
            elif endpoint.type == 'fastapi':
                return self._check_fastapi_integration_status(integration_name, endpoint)
            else:
                return {
                    "status": "unknown",
                    "framework": endpoint.type,
                    "error": f"Unknown framework type: {endpoint.type}"
                }
        except Exception as e:
            return {
                "status": "error",
                "framework": endpoint.type,
                "error": str(e),
                "last_check": datetime.now(timezone.utc).isoformat()
            }
    
    def _check_flask_integration_status(self, integration_name: str, endpoint: IntegrationEndpoint) -> Dict[str, Any]:
        """Check Flask integration status"""
        try:
            # For Flask, we can check if the route exists and try a simple health check
            if self._check_flask_endpoint_exists(endpoint.base_url):
                return {
                    "status": "active",
                    "framework": "flask",
                    "endpoint": endpoint.base_url,
                    "health_endpoint": endpoint.health_endpoint,
                    "last_check": datetime.now(timezone.utc).isoformat(),
                    "available_endpoints": self._get_available_flask_endpoints(integration_name)
                }
            else:
                return {
                    "status": "inactive",
                    "framework": "flask",
                    "endpoint": endpoint.base_url,
                    "error": "Endpoint not registered",
                    "last_check": datetime.now(timezone.utc).isoformat()
                }
        except Exception as e:
            return {
                "status": "error",
                "framework": "flask",
                "endpoint": endpoint.base_url,
                "error": str(e),
                "last_check": datetime.now(timezone.utc).isoformat()
            }
    
    def _check_fastapi_integration_status(self, integration_name: str, endpoint: IntegrationEndpoint) -> Dict[str, Any]:
        """Check FastAPI integration status"""
        try:
            # For FastAPI, we'd typically check if the service is running
            # This might involve checking a different port or service discovery
            fastapi_base_url = os.getenv("FASTAPI_BASE_URL", "http://localhost:8001")
            health_url = f"{fastapi_base_url}{endpoint.health_endpoint}"
            
            # Try to connect to FastAPI service
            import requests
            response = requests.get(health_url, timeout=5)
            
            if response.status_code == 200:
                return {
                    "status": "active",
                    "framework": "fastapi",
                    "endpoint": f"{fastapi_base_url}{endpoint.base_url}",
                    "health_endpoint": health_url,
                    "last_check": datetime.now(timezone.utc).isoformat(),
                    "available_endpoints": response.json().get("available_endpoints", [])
                }
            else:
                return {
                    "status": "degraded",
                    "framework": "fastapi",
                    "endpoint": f"{fastapi_base_url}{endpoint.base_url}",
                    "error": f"HTTP {response.status_code}",
                    "last_check": datetime.now(timezone.utc).isoformat()
                }
        except requests.exceptions.ConnectionError:
            return {
                "status": "inactive",
                "framework": "fastapi",
                "endpoint": "FastAPI service not reachable",
                "error": "Connection refused",
                "last_check": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "framework": "fastapi",
                "error": str(e),
                "last_check": datetime.now(timezone.utc).isoformat()
            }
    
    def _get_available_flask_endpoints(self, integration_name: str) -> List[str]:
        """Get available endpoints for a Flask integration"""
        endpoints = []
        try:
            with self.flask_app.app_context():
                for rule in self.flask_app.url_map.iter_rules():
                    if integration_name in rule.rule:
                        endpoints.append(rule.rule)
        except Exception as e:
            logger.warning(f"Failed to get Flask endpoints for {integration_name}: {e}")
        return endpoints
    
    def _forward_to_integration(self, integration: str):
        """Forward request to appropriate integration endpoint"""
        try:
            if integration not in self.endpoint_mappings:
                return jsonify({
                    "error": f"Integration '{integration}' not found",
                    "available_integrations": list(self.endpoint_mappings.keys())
                }), 404
            
            endpoint_config = self.endpoint_mappings[integration]
            
            if endpoint_config.type == 'flask':
                # Handle Flask integration internally
                return self._handle_flask_integration(integration, endpoint_config)
            elif endpoint_config.type == 'fastapi':
                # Forward to FastAPI service
                return self._forward_to_fastapi(integration, endpoint_config)
            else:
                return jsonify({
                    "error": f"Unknown integration type: {endpoint_config.type}"
                }), 400
                
        except Exception as e:
            logger.error(f"Failed to forward request to {integration}: {e}")
            return jsonify({
                "error": str(e),
                "integration": integration
            }), 500
    
    def _unified_integration_handler(self, integration: str, endpoint: str):
        """Unified handler for both Flask and FastAPI integrations"""
        try:
            if integration not in self.endpoint_mappings:
                return jsonify({
                    "error": f"Integration '{integration}' not found",
                    "available_integrations": list(self.endpoint_mappings.keys())
                }), 404
            
            endpoint_config = self.endpoint_mappings[integration]
            full_endpoint = f"/{endpoint}"
            
            if endpoint_config.type == 'flask':
                # Check if Flask endpoint exists and call it
                return self._call_flask_endpoint(integration, full_endpoint, endpoint_config)
            elif endpoint_config.type == 'fastapi':
                # Forward to FastAPI
                return self._forward_to_fastapi_endpoint(integration, full_endpoint, endpoint_config)
            else:
                return jsonify({
                    "error": f"Unknown integration type: {endpoint_config.type}"
                }), 400
                
        except Exception as e:
            logger.error(f"Failed to handle unified endpoint {integration}/{endpoint}: {e}")
            return jsonify({
                "error": str(e),
                "integration": integration,
                "endpoint": endpoint
            }), 500
    
    def _proxy_request(self, integration_name: str, endpoint_config: IntegrationEndpoint, endpoint: str):
        """Proxy request to integration regardless of framework"""
        try:
            if endpoint_config.type == 'flask':
                return self._call_flask_endpoint(integration_name, f"/{endpoint}", endpoint_config)
            elif endpoint_config.type == 'fastapi':
                return self._forward_to_fastapi_endpoint(integration_name, f"/{endpoint}", endpoint_config)
            else:
                return jsonify({
                    "error": f"Unknown integration type: {endpoint_config.type}"
                }), 400
                
        except Exception as e:
            logger.error(f"Failed to proxy request to {integration_name}/{endpoint}: {e}")
            return jsonify({
                "error": str(e),
                "integration": integration_name,
                "endpoint": endpoint
            }), 500
    
    def _handle_flask_integration(self, integration: str, endpoint_config: IntegrationEndpoint):
        """Handle Flask-based integration"""
        try:
            # This would call the actual Flask integration
            # For now, return integration info
            return jsonify({
                "message": f"Flask integration '{integration}' handled",
                "type": "flask",
                "base_url": endpoint_config.base_url,
                "health_endpoint": endpoint_config.health_endpoint,
                "status": "active"
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    def _call_flask_endpoint(self, integration: str, endpoint: str, endpoint_config: IntegrationEndpoint):
        """Call specific Flask endpoint"""
        try:
            # In a real implementation, you would dispatch to the actual Flask endpoint
            # For now, provide a unified response format
            return jsonify({
                "integration": integration,
                "framework": "flask",
                "endpoint": endpoint,
                "method": request.method,
                "args": dict(request.args),
                "json": request.get_json(silent=True) or {},
                "status": "handled_by_flask_bridge",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    def _forward_to_fastapi(self, integration: str, endpoint_config: IntegrationEndpoint):
        """Forward request to FastAPI service"""
        try:
            fastapi_base_url = os.getenv("FASTAPI_BASE_URL", "http://localhost:8001")
            target_url = f"{fastapi_base_url}{endpoint_config.base_url}{request.full_path.split(f'/api/forward/{integration}')[1] if '/forward' in request.full_path else ''}"
            
            # Forward request to FastAPI
            response = httpx.request(
                method=request.method,
                url=target_url,
                params=dict(request.args),
                json=request.get_json() if request.is_json else None,
                data=request.form if request.form else None,
                files=request.files if request.files else None,
                headers=dict(request.headers)
            )
            
            return jsonify({
                "integration": integration,
                "framework": "fastapi",
                "forwarded_to": target_url,
                "response": response.json() if response.content else {},
                "status_code": response.status_code,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }), response.status_code
            
        except Exception as e:
            return jsonify({
                "error": str(e),
                "integration": integration,
                "framework": "fastapi"
            }), 500
    
    def _forward_to_fastapi_endpoint(self, integration: str, endpoint: str, endpoint_config: IntegrationEndpoint):
        """Forward to specific FastAPI endpoint"""
        try:
            fastapi_base_url = os.getenv("FASTAPI_BASE_URL", "http://localhost:8001")
            target_url = f"{fastapi_base_url}{endpoint_config.base_url}{endpoint}"
            
            # Forward request to FastAPI
            response = httpx.request(
                method=request.method,
                url=target_url,
                params=dict(request.args),
                json=request.get_json() if request.is_json else None,
                data=request.form if request.form else None,
                files=request.files if request.files else None,
                headers=dict(request.headers)
            )
            
            return jsonify({
                "integration": integration,
                "framework": "fastapi",
                "endpoint": endpoint,
                "method": request.method,
                "forwarded_to": target_url,
                "response": response.json() if response.content else {},
                "status_code": response.status_code,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }), response.status_code
            
        except Exception as e:
            return jsonify({
                "error": str(e),
                "integration": integration,
                "framework": "fastapi",
                "endpoint": endpoint
            }), 500
    
    async def shutdown(self):
        """Cleanup resources"""
        await self.http_client.aclose()

# Global bridge instance
_bridge_instance: Optional[FlaskFastAPIBridge] = None

def init_integration_bridge(flask_app: Flask) -> FlaskFastAPIBridge:
    """Initialize the integration bridge system"""
    global _bridge_instance
    
    if _bridge_instance is None:
        _bridge_instance = FlaskFastAPIBridge(flask_app)
        logger.info("Integration bridge system initialized")
    
    return _bridge_instance

def get_integration_bridge() -> Optional[FlaskFastAPIBridge]:
    """Get the global integration bridge instance"""
    return _bridge_instance