"""
Comprehensive Integration API Endpoints for ATOM Agent Memory System

This module provides Flask API endpoints for all document and communication
integrations with the ATOM agent memory system.
"""

import asyncio
from flask import Blueprint, request, jsonify
from loguru import logger
from datetime import datetime, timezone

# Import integration services
try:
    from notion_integration_service import get_notion_integration_service
    NOTION_INTEGRATION_AVAILABLE = True
except ImportError:
    NOTION_INTEGRATION_AVAILABLE = False

try:
    from gdrive_integration_service import get_gdrive_integration_service
    GDRIVE_INTEGRATION_AVAILABLE = True
except ImportError:
    GDRIVE_INTEGRATION_AVAILABLE = False

try:
    from onedrive_integration_service import get_onedrive_integration_service
    ONEDRIVE_INTEGRATION_AVAILABLE = True
except ImportError:
    ONEDRIVE_INTEGRATION_AVAILABLE = False

try:
    from communication_integration_service import get_communication_integration_service
    COMMUNICATION_INTEGRATION_AVAILABLE = True
except ImportError:
    COMMUNICATION_INTEGRATION_AVAILABLE = False

# Create blueprint
comprehensive_integration_bp = Blueprint('comprehensive_integration_bp', __name__)


def async_route(f):
    """Decorator for async Flask routes"""
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(f(*args, **kwargs))
            return result
        finally:
            loop.close()
    wrapper.__name__ = f.__name__
    return wrapper


# -------------------------------------------------------------------------
# NOTION INTEGRATION ENDPOINTS
# -------------------------------------------------------------------------

@comprehensive_integration_bp.route("/api/integrations/notion/add", methods=["POST"])
def add_notion_integration():
    """Add Notion integration for user"""
    try:
        user_id = request.json.get("user_id")
        config_overrides = request.json.get("config", {})
        
        if not user_id:
            return jsonify({
                "error": "user_id required",
                "success": False
            }), 400
        
        if not NOTION_INTEGRATION_AVAILABLE:
            return jsonify({
                "error": "Notion integration service not available",
                "success": False
            }), 503
        
        service = get_notion_integration_service()
        result = asyncio.run(service.add_user_notion_integration(
            user_id, config_overrides
        ))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error adding Notion integration: {e}")
        return jsonify({
            "error": f"Failed to add Notion integration: {str(e)}",
            "success": False
        }), 500


@comprehensive_integration_bp.route("/api/integrations/notion/status")
def get_notion_integration_status():
    """Get Notion integration status for user"""
    try:
        user_id = request.args.get("user_id")
        
        if not user_id:
            return jsonify({
                "error": "user_id required",
                "success": False
            }), 400
        
        if not NOTION_INTEGRATION_AVAILABLE:
            return jsonify({
                "status": "service_unavailable",
                "message": "Notion integration service not available",
                "user_id": user_id,
            })
        
        service = get_notion_integration_service()
        result = asyncio.run(service.get_user_notion_status(user_id))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting Notion integration status: {e}")
        return jsonify({
            "error": f"Failed to get integration status: {str(e)}",
            "success": False
        }), 500


# -------------------------------------------------------------------------
# GOOGLE DRIVE INTEGRATION ENDPOINTS
# -------------------------------------------------------------------------

@comprehensive_integration_bp.route("/api/integrations/gdrive/add", methods=["POST"])
def add_gdrive_integration():
    """Add Google Drive integration for user"""
    try:
        user_id = request.json.get("user_id")
        config_overrides = request.json.get("config", {})
        
        if not user_id:
            return jsonify({
                "error": "user_id required",
                "success": False
            }), 400
        
        if not GDRIVE_INTEGRATION_AVAILABLE:
            return jsonify({
                "error": "Google Drive integration service not available",
                "success": False
            }), 503
        
        service = get_gdrive_integration_service()
        result = asyncio.run(service.add_user_gdrive_integration(
            user_id, config_overrides
        ))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error adding Google Drive integration: {e}")
        return jsonify({
            "error": f"Failed to add Google Drive integration: {str(e)}",
            "success": False
        }), 500


@comprehensive_integration_bp.route("/api/integrations/gdrive/status")
def get_gdrive_integration_status():
    """Get Google Drive integration status for user"""
    try:
        user_id = request.args.get("user_id")
        
        if not user_id:
            return jsonify({
                "error": "user_id required",
                "success": False
            }), 400
        
        if not GDRIVE_INTEGRATION_AVAILABLE:
            return jsonify({
                "status": "service_unavailable",
                "message": "Google Drive integration service not available",
                "user_id": user_id,
            })
        
        service = get_gdrive_integration_service()
        result = asyncio.run(service.get_user_gdrive_status(user_id))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting Google Drive integration status: {e}")
        return jsonify({
            "error": f"Failed to get integration status: {str(e)}",
            "success": False
        }), 500


# -------------------------------------------------------------------------
# ONEDRIVE INTEGRATION ENDPOINTS
# -------------------------------------------------------------------------

@comprehensive_integration_bp.route("/api/integrations/onedrive/add", methods=["POST"])
def add_onedrive_integration():
    """Add OneDrive integration for user"""
    try:
        user_id = request.json.get("user_id")
        config_overrides = request.json.get("config", {})
        
        if not user_id:
            return jsonify({
                "error": "user_id required",
                "success": False
            }), 400
        
        if not ONEDRIVE_INTEGRATION_AVAILABLE:
            return jsonify({
                "error": "OneDrive integration service not available",
                "success": False
            }), 503
        
        service = get_onedrive_integration_service()
        result = asyncio.run(service.add_user_onedrive_integration(
            user_id, config_overrides
        ))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error adding OneDrive integration: {e}")
        return jsonify({
            "error": f"Failed to add OneDrive integration: {str(e)}",
            "success": False
        }), 500


@comprehensive_integration_bp.route("/api/integrations/onedrive/status")
def get_onedrive_integration_status():
    """Get OneDrive integration status for user"""
    try:
        user_id = request.args.get("user_id")
        
        if not user_id:
            return jsonify({
                "error": "user_id required",
                "success": False
            }), 400
        
        if not ONEDRIVE_INTEGRATION_AVAILABLE:
            return jsonify({
                "status": "service_unavailable",
                "message": "OneDrive integration service not available",
                "user_id": user_id,
            })
        
        service = get_onedrive_integration_service()
        result = asyncio.run(service.get_user_onedrive_status(user_id))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting OneDrive integration status: {e}")
        return jsonify({
            "error": f"Failed to get integration status: {str(e)}",
            "success": False
        }), 500


# -------------------------------------------------------------------------
# COMMUNICATION APPS INTEGRATION ENDPOINTS
# -------------------------------------------------------------------------

@comprehensive_integration_bp.route("/api/integrations/communication/add", methods=["POST"])
def add_communication_integration():
    """Add communication app integration for user"""
    try:
        user_id = request.json.get("user_id")
        platform = request.json.get("platform")
        config_overrides = request.json.get("config", {})
        
        if not user_id or not platform:
            return jsonify({
                "error": "user_id and platform required",
                "success": False
            }), 400
        
        if not COMMUNICATION_INTEGRATION_AVAILABLE:
            return jsonify({
                "error": "Communication integration service not available",
                "success": False
            }), 503
        
        service = get_communication_integration_service()
        result = asyncio.run(service.add_user_communication_integration(
            user_id, platform, config_overrides
        ))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error adding communication integration: {e}")
        return jsonify({
            "error": f"Failed to add communication integration: {str(e)}",
            "success": False
        }), 500


@comprehensive_integration_bp.route("/api/integrations/communication/status")
def get_communication_integration_status():
    """Get communication app integration status for user"""
    try:
        user_id = request.args.get("user_id")
        platform = request.args.get("platform")
        
        if not user_id:
            return jsonify({
                "error": "user_id required",
                "success": False
            }), 400
        
        if not COMMUNICATION_INTEGRATION_AVAILABLE:
            return jsonify({
                "status": "service_unavailable",
                "message": "Communication integration service not available",
                "user_id": user_id,
            })
        
        service = get_communication_integration_service()
        result = asyncio.run(service.get_user_communication_status(
            user_id, platform
        ))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting communication integration status: {e}")
        return jsonify({
            "error": f"Failed to get integration status: {str(e)}",
            "success": False
        }), 500


# -------------------------------------------------------------------------
# COMPREHENSIVE INTEGRATION ENDPOINTS
# -------------------------------------------------------------------------

@comprehensive_integration_bp.route("/api/integrations/status")
def get_all_integration_status():
    """Get status of all integrations for user"""
    try:
        user_id = request.args.get("user_id")
        
        if not user_id:
            return jsonify({
                "error": "user_id required",
                "success": False
            }), 400
        
        all_status = {
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "integrations": {}
        }
        
        # Get Notion status
        if NOTION_INTEGRATION_AVAILABLE:
            notion_service = get_notion_integration_service()
            notion_status = asyncio.run(notion_service.get_user_notion_status(user_id))
            all_status["integrations"]["notion"] = notion_status
        
        # Get Google Drive status
        if GDRIVE_INTEGRATION_AVAILABLE:
            gdrive_service = get_gdrive_integration_service()
            gdrive_status = asyncio.run(gdrive_service.get_user_gdrive_status(user_id))
            all_status["integrations"]["google_drive"] = gdrive_status
        
        # Get OneDrive status
        if ONEDRIVE_INTEGRATION_AVAILABLE:
            onedrive_service = get_onedrive_integration_service()
            onedrive_status = asyncio.run(onedrive_service.get_user_onedrive_status(user_id))
            all_status["integrations"]["onedrive"] = onedrive_status
        
        # Get Communication status
        if COMMUNICATION_INTEGRATION_AVAILABLE:
            comm_service = get_communication_integration_service()
            comm_status = asyncio.run(comm_service.get_user_communication_status(user_id))
            all_status["integrations"]["communication"] = comm_status
        
        return jsonify(all_status)
        
    except Exception as e:
        logger.error(f"Error getting all integration status: {e}")
        return jsonify({
            "error": f"Failed to get integration status: {str(e)}",
            "success": False
        }), 500


@comprehensive_integration_bp.route("/api/integrations/statistics")
def get_all_integration_statistics():
    """Get overall integration statistics"""
    try:
        statistics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": {}
        }
        
        # Get Notion statistics
        if NOTION_INTEGRATION_AVAILABLE:
            notion_service = get_notion_integration_service()
            notion_stats = asyncio.run(notion_service.get_integration_statistics())
            statistics["services"]["notion"] = notion_stats
        
        # Get Google Drive statistics
        if GDRIVE_INTEGRATION_AVAILABLE:
            gdrive_service = get_gdrive_integration_service()
            gdrive_stats = {
                "status": "active" if gdrive_service.running else "inactive",
                "total_users": len(gdrive_service.processors),
            }
            statistics["services"]["google_drive"] = gdrive_stats
        
        # Get OneDrive statistics
        if ONEDRIVE_INTEGRATION_AVAILABLE:
            onedrive_service = get_onedrive_integration_service()
            onedrive_stats = {
                "status": "active" if onedrive_service.running else "inactive",
                "total_users": len(onedrive_service.processors),
            }
            statistics["services"]["onedrive"] = onedrive_stats
        
        # Get Communication statistics
        if COMMUNICATION_INTEGRATION_AVAILABLE:
            comm_service = get_communication_integration_service()
            comm_stats = asyncio.run(comm_service.get_integration_statistics())
            statistics["services"]["communication"] = comm_stats
        
        # Overall summary
        total_services = sum(1 for service in statistics["services"].values() 
                           if service.get("status") == "active")
        statistics["overall"] = {
            "total_available_services": len([s for s in [NOTION_INTEGRATION_AVAILABLE, 
                                                       GDRIVE_INTEGRATION_AVAILABLE,
                                                       ONEDRIVE_INTEGRATION_AVAILABLE,
                                                       COMMUNICATION_INTEGRATION_AVAILABLE] if s]),
            "active_services": total_services,
            "service_availability": {
                "notion": NOTION_INTEGRATION_AVAILABLE,
                "google_drive": GDRIVE_INTEGRATION_AVAILABLE,
                "onedrive": ONEDRIVE_INTEGRATION_AVAILABLE,
                "communication": COMMUNICATION_INTEGRATION_AVAILABLE,
            }
        }
        
        return jsonify(statistics)
        
    except Exception as e:
        logger.error(f"Error getting integration statistics: {e}")
        return jsonify({
            "error": f"Failed to get integration statistics: {str(e)}",
            "success": False
        }), 500


@comprehensive_integration_bp.route("/api/integrations/health")
def integration_health_check():
    """Health check for all integration services"""
    try:
        health_status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": {}
        }
        
        # Check Notion
        if NOTION_INTEGRATION_AVAILABLE:
            notion_service = get_notion_integration_service()
            health_status["services"]["notion"] = {
                "available": True,
                "running": notion_service.running,
                "status": "healthy" if notion_service.running else "stopped"
            }
        else:
            health_status["services"]["notion"] = {
                "available": False,
                "status": "unavailable"
            }
        
        # Check Google Drive
        if GDRIVE_INTEGRATION_AVAILABLE:
            gdrive_service = get_gdrive_integration_service()
            health_status["services"]["google_drive"] = {
                "available": True,
                "running": gdrive_service.running,
                "status": "healthy" if gdrive_service.running else "stopped"
            }
        else:
            health_status["services"]["google_drive"] = {
                "available": False,
                "status": "unavailable"
            }
        
        # Check OneDrive
        if ONEDRIVE_INTEGRATION_AVAILABLE:
            onedrive_service = get_onedrive_integration_service()
            health_status["services"]["onedrive"] = {
                "available": True,
                "running": onedrive_service.running,
                "status": "healthy" if onedrive_service.running else "stopped"
            }
        else:
            health_status["services"]["onedrive"] = {
                "available": False,
                "status": "unavailable"
            }
        
        # Check Communication
        if COMMUNICATION_INTEGRATION_AVAILABLE:
            comm_service = get_communication_integration_service()
            health_status["services"]["communication"] = {
                "available": True,
                "running": comm_service.running,
                "status": "healthy" if comm_service.running else "stopped"
            }
        else:
            health_status["services"]["communication"] = {
                "available": False,
                "status": "unavailable"
            }
        
        # Overall health
        active_services = sum(1 for service in health_status["services"].values()
                            if service.get("running", False))
        total_services = sum(1 for service in health_status["services"].values()
                            if service.get("available", False))
        
        health_status["overall"] = {
            "status": "healthy" if active_services == total_services and total_services > 0 else "degraded",
            "active_services": active_services,
            "total_services": total_services,
            "health_ratio": active_services / total_services if total_services > 0 else 0
        }
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Error in integration health check: {e}")
        return jsonify({
            "error": f"Failed health check: {str(e)}",
            "success": False
        }), 500


# -------------------------------------------------------------------------
# REMOVE INTEGRATION ENDPOINTS
# -------------------------------------------------------------------------

@comprehensive_integration_bp.route("/api/integrations/remove", methods=["POST"])
def remove_integration():
    """Remove any integration for user"""
    try:
        user_id = request.json.get("user_id")
        platform = request.json.get("platform")
        
        if not user_id or not platform:
            return jsonify({
                "error": "user_id and platform required",
                "success": False
            }), 400
        
        platform = platform.lower()
        result = {"status": "not_found", "message": f"Platform '{platform}' not recognized"}
        
        # Remove Notion
        if platform == "notion" and NOTION_INTEGRATION_AVAILABLE:
            notion_service = get_notion_integration_service()
            result = asyncio.run(notion_service.remove_user_notion_integration(user_id))
        
        # Remove Google Drive
        elif platform == "google_drive" and GDRIVE_INTEGRATION_AVAILABLE:
            gdrive_service = get_gdrive_integration_service()
            result = asyncio.run(gdrive_service.remove_user_gdrive_integration(user_id))
        
        # Remove OneDrive
        elif platform == "onedrive" and ONEDRIVE_INTEGRATION_AVAILABLE:
            onedrive_service = get_onedrive_integration_service()
            result = asyncio.run(onedrive_service.remove_user_onedrive_integration(user_id))
        
        # Remove Communication
        elif platform in ["slack", "teams", "gmail", "outlook"] and COMMUNICATION_INTEGRATION_AVAILABLE:
            comm_service = get_communication_integration_service()
            result = asyncio.run(comm_service.remove_user_communication_integration(
                user_id, platform
            ))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error removing integration: {e}")
        return jsonify({
            "error": f"Failed to remove integration: {str(e)}",
            "success": False
        }), 500


logger.info("Comprehensive integration API endpoints registered successfully")