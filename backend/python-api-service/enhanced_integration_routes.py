#!/usr/bin/env python3
"""
Enhanced Integration Routes
Unified routes that work with both Flask and FastAPI integrations
"""

from flask import Blueprint, jsonify, request, g
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from flask_fastapi_bridge import get_integration_bridge

# Create blueprint
enhanced_integrations_bp = Blueprint('enhanced_integrations', __name__)
logger = logging.getLogger(__name__)

def async_route(f):
    """Decorator to run async functions in Flask routes"""
    import asyncio
    from functools import wraps
    
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(f(*args, **kwargs))
        finally:
            loop.close()
    
    return wrapper

# Unified Health Endpoints
@enhanced_integrations_bp.route('/health/overview', methods=['GET'])
def health_overview():
    """Get comprehensive health overview of all integrations"""
    try:
        bridge = get_integration_bridge()
        if not bridge:
            return jsonify({
                "error": "Integration bridge not initialized",
                "status": "error"
            }), 503
        
        status_response, status_code = bridge._get_comprehensive_bridge_status()
        
        # Add enhanced metrics
        if status_code == 200:
            data = status_response[0] if isinstance(status_response[0], dict) else status_response.json()
            
            # Add additional health metrics
            health_metrics = {
                "uptime_check": True,
                "bridge_status": "active",
                "last_comprehensive_check": datetime.now(timezone.utc).isoformat(),
                "next_check_scheduled": datetime.fromtimestamp(
                    datetime.now().timestamp() + 300,  # 5 minutes from now
                    tz=timezone.utc
                ).isoformat()
            }
            
            data["enhanced_metrics"] = health_metrics
            
            return jsonify(data), 200
        else:
            return status_response
        
    except Exception as e:
        logger.error(f"Failed to get health overview: {e}")
        return jsonify({
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@enhanced_integrations_bp.route('/health/detailed', methods=['GET'])
@async_route
async def detailed_health_check():
    """Get detailed health status for all integrations with async checks"""
    try:
        bridge = get_integration_bridge()
        if not bridge:
            return jsonify({
                "error": "Integration bridge not initialized",
                "status": "error"
            }), 503
        
        # Get comprehensive status
        status_data = bridge._get_comprehensive_bridge_status()
        
        # Add async health checks
        enhanced_status = await _perform_enhanced_health_checks(bridge)
        
        # Merge data
        final_status = {
            **status_data[0] if isinstance(status_data[0], dict) else status_data.json(),
            "enhanced_checks": enhanced_status,
            "check_timestamp": datetime.now(timezone.utc).isoformat(),
            "check_type": "detailed_async"
        }
        
        return jsonify(final_status), 200
        
    except Exception as e:
        logger.error(f"Failed to perform detailed health check: {e}")
        return jsonify({
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

# Unified Integration Endpoints
@enhanced_integrations_bp.route('/integrations/<integration>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def unified_integration_handler(integration: str):
    """Unified handler for all integration requests"""
    try:
        bridge = get_integration_bridge()
        if not bridge:
            return jsonify({
                "error": "Integration bridge not initialized",
                "status": "error"
            }), 503
        
        # Forward request through bridge
        return bridge._forward_to_integration(integration)
        
    except Exception as e:
        logger.error(f"Failed to handle unified integration request for {integration}: {e}")
        return jsonify({
            "error": str(e),
            "integration": integration,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@enhanced_integrations_bp.route('/integrations/<integration>/<path:endpoint>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def unified_endpoint_handler(integration: str, endpoint: str):
    """Unified endpoint handler for specific integration endpoints"""
    try:
        bridge = get_integration_bridge()
        if not bridge:
            return jsonify({
                "error": "Integration bridge not initialized",
                "status": "error"
            }), 503
        
        # Handle through unified endpoint
        return bridge._unified_integration_handler(integration, endpoint)
        
    except Exception as e:
        logger.error(f"Failed to handle unified endpoint {integration}/{endpoint}: {e}")
        return jsonify({
            "error": str(e),
            "integration": integration,
            "endpoint": endpoint,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

# Framework-agnostic Integration Management
@enhanced_integrations_bp.route('/management/discover', methods=['GET'])
@async_route
async def discover_integrations():
    """Discover all available integrations regardless of framework"""
    try:
        bridge = get_integration_bridge()
        if not bridge:
            return jsonify({
                "error": "Integration bridge not initialized",
                "status": "error"
            }), 503
        
        # Get detailed discovery information
        discovery_data = await _perform_integration_discovery(bridge)
        
        return jsonify({
            "discovery_status": "completed",
            "total_integrations": len(discovery_data["integrations"]),
            "framework_distribution": discovery_data["framework_distribution"],
            "integrations": discovery_data["integrations"],
            "discovery_timestamp": datetime.now(timezone.utc).isoformat(),
            "bridge_version": "2.0.0"
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to discover integrations: {e}")
        return jsonify({
            "error": str(e),
            "discovery_status": "failed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@enhanced_integrations_bp.route('/management/status', methods=['GET'])
def get_management_status():
    """Get management status for all integrations"""
    try:
        bridge = get_integration_bridge()
        if not bridge:
            return jsonify({
                "error": "Integration bridge not initialized",
                "status": "error"
            }), 503
        
        # Get comprehensive status
        status_data, status_code = bridge._get_comprehensive_bridge_status()
        
        if status_code == 200:
            data = status_data[0] if isinstance(status_data[0], dict) else status_data.json()
            
            # Add management-specific information
            management_info = {
                "management_endpoints": {
                    "discover": "/api/enhanced/management/discover",
                    "status": "/api/enhanced/management/status",
                    "health_overview": "/api/enhanced/health/overview",
                    "health_detailed": "/api/enhanced/health/detailed"
                },
                "proxy_endpoints": [
                    f"/api/proxy/{integration}/<endpoint>" 
                    for integration in bridge.endpoint_mappings.keys()
                ],
                "unified_endpoints": [
                    f"/api/enhanced/integrations/{integration}/<endpoint>" 
                    for integration in bridge.endpoint_mappings.keys()
                ]
            }
            
            data["management_info"] = management_info
            data["last_status_update"] = datetime.now(timezone.utc).isoformat()
            
            return jsonify(data), 200
        else:
            return status_data
        
    except Exception as e:
        logger.error(f"Failed to get management status: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

# Enhanced Analytics and Monitoring
@enhanced_integrations_bp.route('/analytics/usage', methods=['GET'])
def get_usage_analytics():
    """Get usage analytics for all integrations"""
    try:
        bridge = get_integration_bridge()
        if not bridge:
            return jsonify({
                "error": "Integration bridge not initialized",
                "status": "error"
            }), 503
        
        # Get current status
        status_data, status_code = bridge._get_comprehensive_bridge_status()
        
        if status_code == 200:
            data = status_data[0] if isinstance(status_data[0], dict) else status_data.json()
            
            # Generate analytics
            analytics = {
                "integration_analytics": {},
                "framework_analytics": {
                    "total_requests": 0,
                    "success_rate": 0,
                    "average_response_time": 0
                },
                "health_trends": {
                    "current_health_score": 0,
                    "health_changes": []
                }
            }
            
            # Calculate per-integration analytics
            for integration_name, integration_info in data.get("integrations", {}).items():
                analytics["integration_analytics"][integration_name] = {
                    "framework": integration_info.get("framework"),
                    "status": integration_info.get("status"),
                    "endpoint_count": len(integration_info.get("available_endpoints", [])),
                    "health_score": 100 if integration_info.get("status") == "active" else 50 if integration_info.get("status") == "degraded" else 0,
                    "last_check": integration_info.get("last_check")
                }
            
            # Calculate framework analytics
            total_integrations = len(data.get("integrations", {}))
            active_integrations = sum(1 for info in data.get("integrations", {}).values() 
                                     if info.get("status") == "active")
            
            analytics["framework_analytics"]["total_integrations"] = total_integrations
            analytics["framework_analytics"]["active_integrations"] = active_integrations
            analytics["framework_analytics"]["success_rate"] = (active_integrations / total_integrations * 100) if total_integrations > 0 else 0
            
            # Calculate health trends
            analytics["health_trends"]["current_health_score"] = analytics["framework_analytics"]["success_rate"]
            
            return jsonify({
                "analytics": analytics,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "data_source": "integration_bridge"
            }), 200
        else:
            return status_data
        
    except Exception as e:
        logger.error(f"Failed to get usage analytics: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@enhanced_integrations_bp.route('/analytics/performance', methods=['GET'])
@async_route
async def get_performance_analytics():
    """Get performance analytics for all integrations"""
    try:
        bridge = get_integration_bridge()
        if not bridge:
            return jsonify({
                "error": "Integration bridge not initialized",
                "status": "error"
            }), 503
        
        # Perform performance checks
        performance_data = await _perform_performance_checks(bridge)
        
        return jsonify({
            "performance_analytics": performance_data,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "check_type": "comprehensive_performance"
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get performance analytics: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

# Helper Functions
async def _perform_enhanced_health_checks(bridge) -> Dict[str, Any]:
    """Perform enhanced health checks on all integrations"""
    try:
        enhanced_checks = {
            "async_health_checks": {},
            "connectivity_tests": {},
            "response_time_tests": {}
        }
        
        for integration_name, endpoint in bridge.endpoint_mappings.items():
            try:
                # Perform async health check
                health_result = await _check_integration_health_async(integration_name, endpoint)
                enhanced_checks["async_health_checks"][integration_name] = health_result
                
                # Perform connectivity test
                connectivity_result = await _test_connectivity_async(integration_name, endpoint)
                enhanced_checks["connectivity_tests"][integration_name] = connectivity_result
                
                # Perform response time test
                response_time_result = await _test_response_time_async(integration_name, endpoint)
                enhanced_checks["response_time_tests"][integration_name] = response_time_result
                
            except Exception as e:
                enhanced_checks["async_health_checks"][integration_name] = {"error": str(e)}
                enhanced_checks["connectivity_tests"][integration_name] = {"error": str(e)}
                enhanced_checks["response_time_tests"][integration_name] = {"error": str(e)}
        
        return enhanced_checks
        
    except Exception as e:
        logger.error(f"Failed to perform enhanced health checks: {e}")
        return {"error": str(e)}

async def _check_integration_health_async(integration_name: str, endpoint) -> Dict[str, Any]:
    """Check integration health asynchronously"""
    try:
        import httpx
        import time
        
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            if endpoint.type == 'flask':
                # For Flask, check if endpoint exists
                response = await client.get(
                    f"http://localhost:5058{endpoint.health_endpoint}",
                    follow_redirects=True
                )
            else:
                # For FastAPI, check external service
                response = await client.get(
                    f"http://localhost:8001{endpoint.health_endpoint}",
                    follow_redirects=True
                )
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "response_time": response_time,
                "status_code": response.status_code,
                "check_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "check_timestamp": datetime.now(timezone.utc).isoformat()
        }

async def _test_connectivity_async(integration_name: str, endpoint) -> Dict[str, Any]:
    """Test integration connectivity"""
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            if endpoint.type == 'flask':
                response = await client.head(
                    f"http://localhost:5058{endpoint.base_url}",
                    follow_redirects=True
                )
            else:
                response = await client.head(
                    f"http://localhost:8001{endpoint.base_url}",
                    follow_redirects=True
                )
            
            return {
                "connected": response.status_code < 400,
                "status_code": response.status_code,
                "test_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "test_timestamp": datetime.now(timezone.utc).isoformat()
        }

async def _test_response_time_async(integration_name: str, endpoint) -> Dict[str, Any]:
    """Test integration response time"""
    try:
        import httpx
        import time
        
        times = []
        
        # Make multiple requests to get average response time
        for _ in range(3):
            start_time = time.time()
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                if endpoint.type == 'flask':
                    await client.get(
                        f"http://localhost:5058{endpoint.health_endpoint}",
                        follow_redirects=True
                    )
                else:
                    await client.get(
                        f"http://localhost:8001{endpoint.health_endpoint}",
                        follow_redirects=True
                    )
            
            times.append((time.time() - start_time) * 1000)
        
        avg_time = sum(times) / len(times)
        
        return {
            "average_response_time": avg_time,
            "min_response_time": min(times),
            "max_response_time": max(times),
            "samples": len(times),
            "test_timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "test_timestamp": datetime.now(timezone.utc).isoformat()
        }

async def _perform_integration_discovery(bridge) -> Dict[str, Any]:
    """Perform comprehensive integration discovery"""
    try:
        discovery_data = {
            "integrations": {},
            "framework_distribution": {
                "flask": 0,
                "fastapi": 0,
                "external": 0
            },
            "discovery_metadata": {
                "start_time": datetime.now(timezone.utc).isoformat(),
                "discovery_method": "bridge_system"
            }
        }
        
        for integration_name, endpoint in bridge.endpoint_mappings.items():
            discovery_data["integrations"][integration_name] = {
                "name": integration_name,
                "framework": endpoint.type,
                "base_url": endpoint.base_url,
                "health_endpoint": endpoint.health_endpoint,
                "auth_required": endpoint.auth_required,
                "timeout": endpoint.timeout,
                "discovered_capabilities": await _discover_integration_capabilities(integration_name, endpoint)
            }
            
            discovery_data["framework_distribution"][endpoint.type] += 1
        
        discovery_data["discovery_metadata"]["end_time"] = datetime.now(timezone.utc).isoformat()
        discovery_data["discovery_metadata"]["duration_seconds"] = (
            datetime.fromisoformat(discovery_data["discovery_metadata"]["end_time"]) -
            datetime.fromisoformat(discovery_data["discovery_metadata"]["start_time"])
        ).total_seconds()
        
        return discovery_data
        
    except Exception as e:
        logger.error(f"Failed to perform integration discovery: {e}")
        return {"error": str(e)}

async def _discover_integration_capabilities(integration_name: str, endpoint) -> List[str]:
    """Discover capabilities of a specific integration"""
    try:
        capabilities = []
        
        # Try to discover available endpoints
        if endpoint.type == 'flask':
            # For Flask, check registered routes
            capabilities = bridge._get_available_flask_endpoints(integration_name)
        else:
            # For FastAPI, try to get OpenAPI spec or available endpoints
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(
                        f"http://localhost:8001{endpoint.base_url}/docs",
                        follow_redirects=True
                    )
                    if response.status_code == 200:
                        capabilities.append("openapi_docs")
            except:
                pass
            
            capabilities.append("fastapi_service")
        
        return capabilities
        
    except Exception as e:
        logger.warning(f"Failed to discover capabilities for {integration_name}: {e}")
        return []

async def _perform_performance_checks(bridge) -> Dict[str, Any]:
    """Perform performance checks on all integrations"""
    try:
        performance_data = {
            "response_time_analysis": {},
            "throughput_analysis": {},
            "error_rate_analysis": {},
            "resource_usage_analysis": {}
        }
        
        for integration_name, endpoint in bridge.endpoint_mappings.items():
            try:
                # Response time analysis
                response_time_data = await _analyze_response_times(integration_name, endpoint)
                performance_data["response_time_analysis"][integration_name] = response_time_data
                
                # Error rate analysis
                error_rate_data = await _analyze_error_rates(integration_name, endpoint)
                performance_data["error_rate_analysis"][integration_name] = error_rate_data
                
            except Exception as e:
                performance_data["response_time_analysis"][integration_name] = {"error": str(e)}
                performance_data["error_rate_analysis"][integration_name] = {"error": str(e)}
        
        return performance_data
        
    except Exception as e:
        logger.error(f"Failed to perform performance checks: {e}")
        return {"error": str(e)}

async def _analyze_response_times(integration_name: str, endpoint) -> Dict[str, Any]:
    """Analyze response times for an integration"""
    try:
        # Make multiple requests to analyze response times
        times = []
        
        for _ in range(10):
            time_data = await _test_response_time_async(integration_name, endpoint)
            if "average_response_time" in time_data:
                times.append(time_data["average_response_time"])
        
        if not times:
            return {"error": "No successful requests"}
        
        return {
            "average_response_time": sum(times) / len(times),
            "min_response_time": min(times),
            "max_response_time": max(times),
            "median_response_time": sorted(times)[len(times) // 2],
            "p95_response_time": sorted(times)[int(len(times) * 0.95)],
            "samples": len(times)
        }
        
    except Exception as e:
        return {"error": str(e)}

async def _analyze_error_rates(integration_name: str, endpoint) -> Dict[str, Any]:
    """Analyze error rates for an integration"""
    try:
        total_requests = 10
        successful_requests = 0
        error_types = {}
        
        for _ in range(total_requests):
            try:
                health_result = await _check_integration_health_async(integration_name, endpoint)
                if health_result.get("status") == "healthy":
                    successful_requests += 1
                else:
                    error_type = health_result.get("status", "unknown")
                    error_types[error_type] = error_types.get(error_type, 0) + 1
            except Exception as e:
                error_types["exception"] = error_types.get("exception", 0) + 1
        
        success_rate = (successful_requests / total_requests) * 100
        error_rate = 100 - success_rate
        
        return {
            "success_rate": success_rate,
            "error_rate": error_rate,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "error_types": error_types
        }
        
    except Exception as e:
        return {"error": str(e)}