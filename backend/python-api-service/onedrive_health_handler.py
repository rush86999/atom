"""
OneDrive Health Handler

This module provides health monitoring endpoints for OneDrive integration,
including service status, connectivity checks, and performance metrics.
"""

import os
import logging
import asyncio
import time
from typing import Dict, Any, Optional
from flask import Blueprint, jsonify
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Create blueprint for OneDrive health endpoints
onedrive_health_bp = Blueprint("onedrive_health", __name__)

# Microsoft Graph API endpoints for health checks
MICROSOFT_GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
ONEDRIVE_HEALTH_ENDPOINTS = {
    "user_info": "/me",
    "drive_info": "/me/drive",
    "recent_files": "/me/drive/recent",
}


class OneDriveHealthService:
    """Service for monitoring OneDrive integration health"""

    def __init__(self):
        self.access_token = os.getenv("ONEDRIVE_ACCESS_TOKEN")
        self.last_health_check = None
        self.health_status_cache = {}

    async def check_onedrive_connectivity(self) -> Dict[str, Any]:
        """Check connectivity to OneDrive service"""
        try:
            if not self.access_token:
                return {
                    "status": "disconnected",
                    "message": "No access token available",
                    "timestamp": time.time(),
                }

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            # Test basic connectivity
            start_time = time.time()
            response = requests.get(
                f"{MICROSOFT_GRAPH_BASE_URL}{ONEDRIVE_HEALTH_ENDPOINTS['user_info']}",
                headers=headers,
                timeout=10,
            )
            response_time = time.time() - start_time

            if response.status_code == 200:
                user_data = response.json()
                return {
                    "status": "connected",
                    "message": "Successfully connected to OneDrive",
                    "response_time_ms": round(response_time * 1000, 2),
                    "user_email": user_data.get("mail")
                    or user_data.get("userPrincipalName"),
                    "user_id": user_data.get("id"),
                    "timestamp": time.time(),
                }
            else:
                return {
                    "status": "error",
                    "message": f"OneDrive API returned status {response.status_code}",
                    "response_time_ms": round(response_time * 1000, 2),
                    "timestamp": time.time(),
                }

        except requests.exceptions.Timeout:
            return {
                "status": "timeout",
                "message": "OneDrive API request timed out",
                "response_time_ms": 10000,  # 10 seconds timeout
                "timestamp": time.time(),
            }
        except requests.exceptions.ConnectionError:
            return {
                "status": "connection_error",
                "message": "Failed to connect to OneDrive API",
                "response_time_ms": 0,
                "timestamp": time.time(),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
                "response_time_ms": 0,
                "timestamp": time.time(),
            }

    async def check_drive_access(self) -> Dict[str, Any]:
        """Check if we can access the user's OneDrive"""
        try:
            if not self.access_token:
                return {
                    "status": "disconnected",
                    "message": "No access token available",
                    "timestamp": time.time(),
                }

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            start_time = time.time()
            response = requests.get(
                f"{MICROSOFT_GRAPH_BASE_URL}{ONEDRIVE_HEALTH_ENDPOINTS['drive_info']}",
                headers=headers,
                timeout=10,
            )
            response_time = time.time() - start_time

            if response.status_code == 200:
                drive_data = response.json()
                return {
                    "status": "accessible",
                    "message": "OneDrive is accessible",
                    "response_time_ms": round(response_time * 1000, 2),
                    "drive_id": drive_data.get("id"),
                    "drive_type": drive_data.get("driveType"),
                    "quota": drive_data.get("quota", {}),
                    "timestamp": time.time(),
                }
            else:
                return {
                    "status": "inaccessible",
                    "message": f"Cannot access OneDrive: {response.status_code}",
                    "response_time_ms": round(response_time * 1000, 2),
                    "timestamp": time.time(),
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Error checking drive access: {str(e)}",
                "response_time_ms": 0,
                "timestamp": time.time(),
            }

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for OneDrive operations"""
        try:
            if not self.access_token:
                return {
                    "status": "disconnected",
                    "message": "No access token available",
                    "timestamp": time.time(),
                }

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            metrics = {}

            # Test list files performance
            start_time = time.time()
            response = requests.get(
                f"{MICROSOFT_GRAPH_BASE_URL}/me/drive/root/children?$top=10",
                headers=headers,
                timeout=10,
            )
            list_files_time = time.time() - start_time

            if response.status_code == 200:
                metrics["list_files_ms"] = round(list_files_time * 1000, 2)
                metrics["list_files_count"] = len(response.json().get("value", []))
            else:
                metrics["list_files_error"] = f"HTTP {response.status_code}"

            # Test search performance
            start_time = time.time()
            response = requests.get(
                f"{MICROSOFT_GRAPH_BASE_URL}/me/drive/root/search(q='test')?$top=5",
                headers=headers,
                timeout=10,
            )
            search_time = time.time() - start_time

            if response.status_code == 200:
                metrics["search_ms"] = round(search_time * 1000, 2)
                metrics["search_count"] = len(response.json().get("value", []))
            else:
                metrics["search_error"] = f"HTTP {response.status_code}"

            return {
                "status": "success",
                "metrics": metrics,
                "timestamp": time.time(),
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Error getting performance metrics: {str(e)}",
                "timestamp": time.time(),
            }

    async def get_comprehensive_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status for OneDrive integration"""
        try:
            # Run all health checks in parallel
            connectivity_task = asyncio.create_task(self.check_onedrive_connectivity())
            drive_access_task = asyncio.create_task(self.check_drive_access())
            performance_task = asyncio.create_task(self.get_performance_metrics())

            connectivity_status = await connectivity_task
            drive_access_status = await drive_access_task
            performance_metrics = await performance_task

            # Determine overall status
            overall_status = "healthy"
            if (
                connectivity_status["status"] != "connected"
                or drive_access_status["status"] != "accessible"
            ):
                overall_status = "degraded"
            if (
                "error" in connectivity_status["status"]
                or "error" in drive_access_status["status"]
            ):
                overall_status = "unhealthy"

            # Check OAuth configuration
            oauth_config = {
                "client_id_configured": bool(os.getenv("ONEDRIVE_CLIENT_ID")),
                "client_secret_configured": bool(os.getenv("ONEDRIVE_CLIENT_SECRET")),
                "redirect_uri_configured": bool(os.getenv("ONEDRIVE_REDIRECT_URI")),
                "access_token_available": bool(self.access_token),
            }

            health_status = {
                "service": "onedrive",
                "status": overall_status,
                "timestamp": time.time(),
                "connectivity": connectivity_status,
                "drive_access": drive_access_status,
                "performance": performance_metrics,
                "oauth_configuration": oauth_config,
                "environment": {
                    "client_id_configured": oauth_config["client_id_configured"],
                    "client_secret_configured": oauth_config[
                        "client_secret_configured"
                    ],
                },
            }

            # Cache the health status
            self.health_status_cache = health_status
            self.last_health_check = time.time()

            return health_status

        except Exception as e:
            logger.error(f"Error getting comprehensive health status: {e}")
            return {
                "service": "onedrive",
                "status": "error",
                "message": f"Health check failed: {str(e)}",
                "timestamp": time.time(),
            }


# Global health service instance
_health_service = OneDriveHealthService()


@onedrive_health_bp.route("/onedrive/health")
async def health_check():
    """Comprehensive health check endpoint"""
    try:
        health_status = await _health_service.get_comprehensive_health_status()
        return jsonify(health_status)

    except Exception as e:
        logger.error(f"Health check endpoint error: {e}")
        return jsonify(
            {
                "service": "onedrive",
                "status": "error",
                "message": f"Health check failed: {str(e)}",
                "timestamp": time.time(),
            }
        ), 500


@onedrive_health_bp.route("/onedrive/health/connectivity")
async def connectivity_check():
    """Quick connectivity check endpoint"""
    try:
        connectivity_status = await _health_service.check_onedrive_connectivity()
        return jsonify(connectivity_status)

    except Exception as e:
        logger.error(f"Connectivity check error: {e}")
        return jsonify(
            {
                "status": "error",
                "message": f"Connectivity check failed: {str(e)}",
                "timestamp": time.time(),
            }
        ), 500


@onedrive_health_bp.route("/onedrive/health/drive")
async def drive_access_check():
    """Drive access check endpoint"""
    try:
        drive_status = await _health_service.check_drive_access()
        return jsonify(drive_status)

    except Exception as e:
        logger.error(f"Drive access check error: {e}")
        return jsonify(
            {
                "status": "error",
                "message": f"Drive access check failed: {str(e)}",
                "timestamp": time.time(),
            }
        ), 500


@onedrive_health_bp.route("/onedrive/health/performance")
async def performance_check():
    """Performance metrics endpoint"""
    try:
        performance_metrics = await _health_service.get_performance_metrics()
        return jsonify(performance_metrics)

    except Exception as e:
        logger.error(f"Performance check error: {e}")
        return jsonify(
            {
                "status": "error",
                "message": f"Performance check failed: {str(e)}",
                "timestamp": time.time(),
            }
        ), 500


@onedrive_health_bp.route("/onedrive/health/config")
async def config_check():
    """Configuration check endpoint"""
    try:
        config_status = {
            "service": "onedrive",
            "timestamp": time.time(),
            "environment_variables": {
                "ONEDRIVE_CLIENT_ID": bool(os.getenv("ONEDRIVE_CLIENT_ID")),
                "ONEDRIVE_CLIENT_SECRET": bool(os.getenv("ONEDRIVE_CLIENT_SECRET")),
                "ONEDRIVE_REDIRECT_URI": bool(os.getenv("ONEDRIVE_REDIRECT_URI")),
                "ONEDRIVE_ACCESS_TOKEN": bool(os.getenv("ONEDRIVE_ACCESS_TOKEN")),
            },
            "required_configuration": {
                "client_id": "Required for OAuth authentication",
                "client_secret": "Required for OAuth authentication",
                "redirect_uri": "Required for OAuth callback",
                "access_token": "Required for API operations (can be obtained via OAuth)",
            },
        }

        # Check if all required config is present
        required_vars = [
            "ONEDRIVE_CLIENT_ID",
            "ONEDRIVE_CLIENT_SECRET",
            "ONEDRIVE_REDIRECT_URI",
        ]
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            config_status["status"] = "incomplete"
            config_status["message"] = (
                f"Missing configuration: {', '.join(missing_vars)}"
            )
        else:
            config_status["status"] = "complete"
            config_status["message"] = "All required configuration present"

        return jsonify(config_status)

    except Exception as e:
        logger.error(f"Config check error: {e}")
        return jsonify(
            {
                "service": "onedrive",
                "status": "error",
                "message": f"Config check failed: {str(e)}",
                "timestamp": time.time(),
            }
        ), 500


def register_onedrive_health_routes(app):
    """Register OneDrive health routes with Flask application"""
    app.register_blueprint(onedrive_health_bp, url_prefix="/api")
    logger.info("OneDrive health routes registered successfully")
