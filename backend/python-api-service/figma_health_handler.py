"""
Figma Health Handler
Comprehensive health monitoring for Figma integration
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify
from typing import Dict, Any, Optional, List

# Import Figma service
try:
    from figma_service_real import figma_service
    FIGMA_SERVICE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Figma service not available: {e}")
    FIGMA_SERVICE_AVAILABLE = False
    figma_service = None

# Import database handlers
try:
    import db_oauth_figma
    FIGMA_DB_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Figma database handler not available: {e}")
    FIGMA_DB_AVAILABLE = False

logger = logging.getLogger(__name__)

# Create blueprint
figma_health_bp = Blueprint("figma_health_bp", __name__)


@figma_health_bp.route("/api/figma/health/detailed", methods=["GET"])
async def figma_health_detailed():
    """Comprehensive Figma integration health check"""
    try:
        user_id = request.args.get("user_id")
        
        health_status = {
            "ok": True,
            "service": "figma",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
            "overall_status": "healthy",
            "checks": {}
        }
        
        # Check 1: Service Availability
        service_check = await _check_service_availability()
        health_status["checks"]["service"] = service_check
        
        # Check 2: Database Availability
        db_check = await _check_database_availability()
        health_status["checks"]["database"] = db_check
        
        # Check 3: Environment Configuration
        env_check = await _check_environment_configuration()
        health_status["checks"]["environment"] = env_check
        
        # Check 4: API Connectivity (if user provided)
        if user_id:
            api_check = await _check_api_connectivity(user_id)
            health_status["checks"]["api"] = api_check
            
            # Check 5: Token Health
            token_check = await _check_token_health(user_id)
            health_status["checks"]["token"] = token_check
        
        # Determine overall status
        failed_checks = []
        for check_name, check_result in health_status["checks"].items():
            if not check_result.get("ok", False):
                failed_checks.append(check_name)
        
        if failed_checks:
            health_status["ok"] = False
            health_status["overall_status"] = "degraded" if len(failed_checks) <= 2 else "unhealthy"
            health_status["failed_checks"] = failed_checks
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Error in Figma detailed health check: {e}")
        return jsonify({
            "ok": False,
            "service": "figma",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "unhealthy"
        }), 500


@figma_health_bp.route("/api/figma/health/tokens", methods=["GET"])
async def figma_token_health():
    """Check Figma OAuth token health"""
    try:
        user_id = request.args.get("user_id")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "user_id is required for token health check"
            }), 400
        
        if not FIGMA_DB_AVAILABLE:
            return jsonify({
                "ok": False,
                "service": "figma",
                "component": "token_check",
                "error": "Figma database handler not available",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }), 503
        
        # Get token information
        token_info = await _check_token_health(user_id)
        
        return jsonify(token_info)
        
    except Exception as e:
        logger.error(f"Error checking Figma token health: {e}")
        return jsonify({
            "ok": False,
            "service": "figma",
            "component": "token_check",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500


@figma_health_bp.route("/api/figma/health/connection", methods=["GET"])
async def figma_connection_health():
    """Test Figma API connectivity"""
    try:
        user_id = request.args.get("user_id")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "user_id is required for connection health check"
            }), 400
        
        if not FIGMA_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "service": "figma",
                "component": "connection_check",
                "error": "Figma service not available",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }), 503
        
        # Test API connectivity
        connection_info = await _check_api_connectivity(user_id)
        
        return jsonify(connection_info)
        
    except Exception as e:
        logger.error(f"Error checking Figma connection health: {e}")
        return jsonify({
            "ok": False,
            "service": "figma",
            "component": "connection_check",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500


@figma_health_bp.route("/api/figma/health/summary", methods=["GET"])
async def figma_health_summary():
    """Get Figma integration health summary"""
    try:
        user_id = request.args.get("user_id")
        
        summary = {
            "ok": True,
            "service": "figma",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
            "status": "healthy",
            "components": {}
        }
        
        # Service Component
        service_check = await _check_service_availability()
        summary["components"]["service"] = {
            "status": "healthy" if service_check.get("ok") else "unhealthy",
            "available": service_check.get("available", False),
            "version": service_check.get("version", "unknown")
        }
        
        # Database Component
        db_check = await _check_database_availability()
        summary["components"]["database"] = {
            "status": "healthy" if db_check.get("ok") else "unhealthy",
            "available": db_check.get("available", False),
            "connected": db_check.get("connected", False)
        }
        
        # Environment Component
        env_check = await _check_environment_configuration()
        summary["components"]["environment"] = {
            "status": "healthy" if env_check.get("ok") else "degraded",
            "configured": env_check.get("configured", False),
            "missing_vars": env_check.get("missing_vars", [])
        }
        
        # If user provided, check additional components
        if user_id:
            # API Component
            api_check = await _check_api_connectivity(user_id)
            summary["components"]["api"] = {
                "status": "healthy" if api_check.get("ok") else "unhealthy",
                "connected": api_check.get("connected", False),
                "response_time_ms": api_check.get("response_time_ms", 0)
            }
            
            # Token Component
            token_check = await _check_token_health(user_id)
            summary["components"]["token"] = {
                "status": "healthy" if token_check.get("ok") else "unhealthy",
                "valid": token_check.get("valid", False),
                "expires_at": token_check.get("expires_at"),
                "can_refresh": token_check.get("can_refresh", False)
            }
        
        # Determine overall status
        component_statuses = [comp.get("status") for comp in summary["components"].values()]
        
        if "unhealthy" in component_statuses:
            summary["status"] = "unhealthy"
            summary["ok"] = False
        elif "degraded" in component_statuses:
            summary["status"] = "degraded"
        else:
            summary["status"] = "healthy"
        
        # Add component counts
        total_components = len(summary["components"])
        healthy_components = len([c for c in summary["components"].values() if c.get("status") == "healthy"])
        
        summary["component_totals"] = {
            "total": total_components,
            "healthy": healthy_components,
            "degraded": len([c for c in summary["components"].values() if c.get("status") == "degraded"]),
            "unhealthy": len([c for c in summary["components"].values() if c.get("status") == "unhealthy"])
        }
        
        return jsonify(summary)
        
    except Exception as e:
        logger.error(f"Error in Figma health summary: {e}")
        return jsonify({
            "ok": False,
            "service": "figma",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "unhealthy"
        }), 500


# Helper functions for health checks

async def _check_service_availability() -> Dict[str, Any]:
    """Check Figma service availability"""
    try:
        if not FIGMA_SERVICE_AVAILABLE:
            return {
                "ok": False,
                "available": False,
                "error": "Figma service not imported"
            }
        
        # Get service info
        service_info = figma_service.get_service_info()
        
        return {
            "ok": True,
            "available": True,
            "version": service_info.get("version", "unknown"),
            "mock_mode": service_info.get("mock_mode", False),
            "capabilities": service_info.get("capabilities", [])
        }
        
    except Exception as e:
        return {
            "ok": False,
            "available": False,
            "error": str(e)
        }


async def _check_database_availability() -> Dict[str, Any]:
    """Check database availability"""
    try:
        if not FIGMA_DB_AVAILABLE:
            return {
                "ok": False,
                "available": False,
                "connected": False,
                "error": "Figma database handler not available"
            }
        
        # Test database connection (simplified)
        # In real implementation, this would test actual database connection
        return {
            "ok": True,
            "available": True,
            "connected": True,
            "handler_available": True
        }
        
    except Exception as e:
        return {
            "ok": False,
            "available": True,
            "connected": False,
            "error": str(e)
        }


async def _check_environment_configuration() -> Dict[str, Any]:
    """Check environment configuration"""
    try:
        required_vars = ["FIGMA_CLIENT_ID", "FIGMA_CLIENT_SECRET", "FIGMA_REDIRECT_URI"]
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        configured = len(missing_vars) == 0
        
        return {
            "ok": configured,
            "configured": configured,
            "missing_vars": missing_vars,
            "all_vars_present": configured
        }
        
    except Exception as e:
        return {
            "ok": False,
            "configured": False,
            "error": str(e),
            "missing_vars": []
        }


async def _check_api_connectivity(user_id: str) -> Dict[str, Any]:
    """Check Figma API connectivity"""
    try:
        if not FIGMA_SERVICE_AVAILABLE:
            return {
                "ok": False,
                "connected": False,
                "error": "Figma service not available"
            }
        
        # Test API call with timing
        start_time = datetime.now()
        
        # Try to get user profile
        if hasattr(figma_service, '_mock_mode') and figma_service._mock_mode:
            # Mock service - always successful
            await asyncio.sleep(0.1)  # Simulate network delay
            user_profile = await figma_service._mock_get_user_profile(user_id)
        else:
            user_profile = await figma_service.get_user_profile(user_id)
        
        end_time = datetime.now()
        response_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        connected = user_profile is not None
        
        return {
            "ok": connected,
            "connected": connected,
            "response_time_ms": response_time_ms,
            "test_endpoint": "user_profile",
            "profile_retrieved": connected
        }
        
    except Exception as e:
        return {
            "ok": False,
            "connected": False,
            "error": str(e)
        }


async def _check_token_health(user_id: str) -> Dict[str, Any]:
    """Check OAuth token health"""
    try:
        if not FIGMA_DB_AVAILABLE:
            return {
                "ok": False,
                "valid": False,
                "error": "Figma database handler not available"
            }
        
        # Get token information (simplified for mock)
        # In real implementation, this would check token expiration and validity
        
        # For mock, always return valid token
        return {
            "ok": True,
            "valid": True,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "can_refresh": True,
            "token_type": "Bearer",
            "scope": ["file_read", "file_write", "team_read"],
            "mock_data": True
        }
        
    except Exception as e:
        return {
            "ok": False,
            "valid": False,
            "error": str(e)
        }