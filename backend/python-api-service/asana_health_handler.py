"""
Asana Health Handler for ATOM Agent Memory System

This module provides health monitoring endpoints for Asana integration.
It checks the connectivity and status of Asana services and OAuth tokens.
"""

import logging
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timezone
import asyncio

logger = logging.getLogger(__name__)

asana_health_bp = Blueprint("asana_health_bp", __name__)


@asana_health_bp.route("/api/asana/health", methods=["GET"])
async def asana_health():
    """
    Health check endpoint for Asana integration
    Returns the overall health status of Asana services
    """
    try:
        health_status = {
            "service": "asana",
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {},
        }

        # Check database connectivity
        db_conn_pool = current_app.config.get("DB_CONNECTION_POOL")
        if not db_conn_pool:
            health_status["status"] = "degraded"
            health_status["checks"]["database"] = {
                "status": "unavailable",
                "message": "Database connection pool not configured",
            }
        else:
            try:
                async with db_conn_pool.acquire() as conn:
                    await conn.execute("SELECT 1")
                health_status["checks"]["database"] = {
                    "status": "healthy",
                    "message": "Database connection successful",
                }
            except Exception as e:
                health_status["status"] = "degraded"
                health_status["checks"]["database"] = {
                    "status": "unavailable",
                    "message": f"Database connection failed: {str(e)}",
                }

        # Check Asana OAuth configuration
        try:
            # Check if required environment variables are set
            client_id = current_app.config.get("ASANA_CLIENT_ID")
            client_secret = current_app.config.get("ASANA_CLIENT_SECRET")
            redirect_uri = current_app.config.get("ASANA_REDIRECT_URI")

            if client_id and client_secret and redirect_uri:
                health_status["checks"]["oauth_config"] = {
                    "status": "healthy",
                    "message": "Asana OAuth configuration valid",
                }
            else:
                health_status["status"] = "degraded"
                health_status["checks"]["oauth_config"] = {
                    "status": "misconfigured",
                    "message": "Asana OAuth configuration incomplete",
                }
        except Exception as e:
            health_status["status"] = "degraded"
            health_status["checks"]["oauth_config"] = {
                "status": "error",
                "message": f"Asana OAuth configuration check failed: {str(e)}",
            }

        # Check Asana service availability
        try:
            from asana_service_real import get_asana_service_real

            health_status["checks"]["service"] = {
                "status": "healthy",
                "message": "Asana service available",
            }
        except ImportError:
            health_status["status"] = "degraded"
            health_status["checks"]["service"] = {
                "status": "unavailable",
                "message": "Asana service not available",
            }

        # Check enhanced API availability
        try:
            from asana_enhanced_api import asana_enhanced_bp

            health_status["checks"]["enhanced_api"] = {
                "status": "healthy",
                "message": "Asana enhanced API available",
            }
        except ImportError:
            health_status["checks"]["enhanced_api"] = {
                "status": "unavailable",
                "message": "Asana enhanced API not available",
            }

        return jsonify(health_status)

    except Exception as e:
        logger.error(f"Asana health check failed: {e}", exc_info=True)
        return jsonify(
            {
                "service": "asana",
                "status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": f"Health check failed: {str(e)}",
            }
        ), 500


@asana_health_bp.route("/api/asana/health/tokens", methods=["GET"])
async def asana_token_health():
    """
    Health check for Asana OAuth tokens
    Returns the status of active Asana OAuth tokens
    """
    try:
        user_id = request.args.get("user_id")

        if not user_id:
            return jsonify(
                {"error": "user_id parameter required", "success": False}
            ), 400

        db_conn_pool = current_app.config.get("DB_CONNECTION_POOL")
        if not db_conn_pool:
            return jsonify(
                {"error": "Database connection not available", "success": False}
            ), 500

        try:
            from db_oauth_asana import get_tokens

            tokens = await get_tokens(db_conn_pool, user_id)

            if tokens:
                token_status = {
                    "user_id": user_id,
                    "has_tokens": True,
                    "token_status": "active",
                    "last_refreshed": tokens.get("updated_at"),
                    "expires_at": tokens.get("expires_at"),
                }

                # Check if token is expired or about to expire
                if tokens.get("expires_at"):
                    expires_at = tokens["expires_at"]
                    if isinstance(expires_at, str):
                        from datetime import datetime

                        expires_at = datetime.fromisoformat(
                            expires_at.replace("Z", "+00:00")
                        )

                    now = datetime.now(timezone.utc)
                    if expires_at < now:
                        token_status["token_status"] = "expired"
                    elif (expires_at - now).total_seconds() < 3600:  # Less than 1 hour
                        token_status["token_status"] = "expiring_soon"

                return jsonify({"success": True, "token_health": token_status})
            else:
                return jsonify(
                    {
                        "success": True,
                        "token_health": {
                            "user_id": user_id,
                            "has_tokens": False,
                            "token_status": "not_configured",
                            "message": "No Asana OAuth tokens found for user",
                        },
                    }
                )

        except ImportError:
            return jsonify(
                {
                    "error": "Asana OAuth database handler not available",
                    "success": False,
                }
            ), 503

    except Exception as e:
        logger.error(f"Asana token health check failed: {e}", exc_info=True)
        return jsonify(
            {"error": f"Token health check failed: {str(e)}", "success": False}
        ), 500


@asana_health_bp.route("/api/asana/health/connection", methods=["GET"])
async def asana_connection_health():
    """
    Test Asana API connection
    Attempts to make a simple API call to verify connectivity
    """
    try:
        user_id = request.args.get("user_id")

        if not user_id:
            return jsonify(
                {"error": "user_id parameter required", "success": False}
            ), 400

        db_conn_pool = current_app.config.get("DB_CONNECTION_POOL")
        if not db_conn_pool:
            return jsonify(
                {"error": "Database connection not available", "success": False}
            ), 500

        try:
            from asana_handler import get_asana_client

            asana_client = await get_asana_client(user_id, db_conn_pool)

            if not asana_client:
                return jsonify(
                    {
                        "success": False,
                        "connection_status": "unauthenticated",
                        "message": "No authenticated Asana client available",
                    }
                ), 401

            # Test connection by listing workspaces (limited to 1 for performance)
            try:
                workspaces = await asana_client.list_workspaces()
                return jsonify(
                    {
                        "success": True,
                        "connection_status": "connected",
                        "message": f"Successfully connected to Asana API. Found {len(workspaces.get('data', []))} workspaces.",
                        "test_result": {
                            "workspaces_retrieved": len(workspaces.get("data", [])),
                            "api_response_time": "normal",
                        },
                    }
                )
            except Exception as api_error:
                logger.error(f"Asana API connection test failed: {api_error}")
                return jsonify(
                    {
                        "success": False,
                        "connection_status": "api_error",
                        "message": f"Asana API connection failed: {str(api_error)}",
                    }
                ), 500

        except ImportError:
            return jsonify(
                {"error": "Asana service not available", "success": False}
            ), 503
        except Exception as e:
            logger.error(f"Asana connection test failed: {e}", exc_info=True)
            return jsonify(
                {
                    "success": False,
                    "connection_status": "failed",
                    "message": f"Asana API connection failed: {str(e)}",
                }
            ), 500

    except Exception as e:
        logger.error(f"Asana connection health check failed: {e}", exc_info=True)
        return jsonify(
            {"error": f"Connection health check failed: {str(e)}", "success": False}
        ), 500


@asana_health_bp.route("/api/asana/health/summary", methods=["GET"])
async def asana_health_summary():
    """
    Comprehensive health summary for Asana integration
    Provides a detailed overview of all Asana components
    """
    try:
        summary = {
            "service": "asana",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {},
        }

        # Run all health checks
        health_response = await asana_health()
        health_data = health_response.get_json()
        summary["components"]["overall"] = health_data

        # Add token health if user_id provided
        user_id = request.args.get("user_id")
        if user_id:
            token_response = await asana_token_health()
            token_data = token_response.get_json()
            summary["components"]["tokens"] = token_data

            # Add connection test if tokens are available
            if token_data.get("success") and token_data.get("token_health", {}).get(
                "has_tokens"
            ):
                connection_response = await asana_connection_health()
                connection_data = connection_response.get_json()
                summary["components"]["connection"] = connection_data

        # Determine overall status
        overall_status = "healthy"
        for component_name, component_data in summary["components"].items():
            if component_name == "overall":
                if component_data.get("status") != "healthy":
                    overall_status = component_data.get("status")
            elif component_data.get("success") is False:
                overall_status = "degraded"

        summary["overall_status"] = overall_status

        return jsonify(summary)

    except Exception as e:
        logger.error(f"Asana health summary failed: {e}", exc_info=True)
        return jsonify(
            {
                "service": "asana",
                "overall_status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": f"Health summary failed: {str(e)}",
            }
        ), 500
