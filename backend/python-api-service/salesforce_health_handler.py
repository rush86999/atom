"""
Salesforce Health Handler for ATOM Agent Memory System

This module provides health monitoring endpoints for Salesforce integration.
It checks the connectivity and status of Salesforce services and OAuth tokens.
"""

import logging
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timezone
import asyncio

logger = logging.getLogger(__name__)

salesforce_health_bp = Blueprint("salesforce_health_bp", __name__)


@salesforce_health_bp.route("/api/salesforce/health", methods=["GET"])
async def salesforce_health():
    """
    Health check endpoint for Salesforce integration
    Returns the overall health status of Salesforce services
    """
    try:
        health_status = {
            "service": "salesforce",
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

        # Check Salesforce OAuth configuration
        try:
            from auth_handler_salesforce import SalesforceOAuthHandler

            oauth_handler = SalesforceOAuthHandler()
            config_valid = oauth_handler._validate_config()

            if config_valid:
                health_status["checks"]["oauth_config"] = {
                    "status": "healthy",
                    "message": "Salesforce OAuth configuration valid",
                }
            else:
                health_status["status"] = "degraded"
                health_status["checks"]["oauth_config"] = {
                    "status": "misconfigured",
                    "message": "Salesforce OAuth configuration incomplete",
                }
        except ImportError:
            health_status["status"] = "degraded"
            health_status["checks"]["oauth_config"] = {
                "status": "unavailable",
                "message": "Salesforce OAuth handler not available",
            }
        except Exception as e:
            health_status["status"] = "degraded"
            health_status["checks"]["oauth_config"] = {
                "status": "error",
                "message": f"Salesforce OAuth configuration check failed: {str(e)}",
            }

        # Check Salesforce service availability
        try:
            from salesforce_service import get_salesforce_client

            health_status["checks"]["service"] = {
                "status": "healthy",
                "message": "Salesforce service available",
            }
        except ImportError:
            health_status["status"] = "degraded"
            health_status["checks"]["service"] = {
                "status": "unavailable",
                "message": "Salesforce service not available",
            }

        # Check enhanced API availability
        try:
            from salesforce_enhanced_api import salesforce_enhanced_bp

            health_status["checks"]["enhanced_api"] = {
                "status": "healthy",
                "message": "Salesforce enhanced API available",
            }
        except ImportError:
            health_status["checks"]["enhanced_api"] = {
                "status": "unavailable",
                "message": "Salesforce enhanced API not available",
            }

        return jsonify(health_status)

    except Exception as e:
        logger.error(f"Salesforce health check failed: {e}", exc_info=True)
        return jsonify(
            {
                "service": "salesforce",
                "status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": f"Health check failed: {str(e)}",
            }
        ), 500


@salesforce_health_bp.route("/api/salesforce/health/tokens", methods=["GET"])
async def salesforce_token_health():
    """
    Health check for Salesforce OAuth tokens
    Returns the status of active Salesforce OAuth tokens
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
            from db_oauth_salesforce import get_user_salesforce_tokens

            tokens = await get_user_salesforce_tokens(db_conn_pool, user_id)

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
                            "message": "No Salesforce OAuth tokens found for user",
                        },
                    }
                )

        except ImportError:
            return jsonify(
                {
                    "error": "Salesforce OAuth database handler not available",
                    "success": False,
                }
            ), 503

    except Exception as e:
        logger.error(f"Salesforce token health check failed: {e}", exc_info=True)
        return jsonify(
            {"error": f"Token health check failed: {str(e)}", "success": False}
        ), 500


@salesforce_health_bp.route("/api/salesforce/health/connection", methods=["GET"])
async def salesforce_connection_health():
    """
    Test Salesforce API connection
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
            from salesforce_service import get_salesforce_client, list_accounts

            sf_client = await get_salesforce_client(user_id, db_conn_pool)

            if not sf_client:
                return jsonify(
                    {
                        "success": False,
                        "connection_status": "unauthenticated",
                        "message": "No authenticated Salesforce client available",
                    }
                ), 401

            # Test connection by listing accounts (limited to 1 for performance)
            accounts = await list_accounts(sf_client)

            return jsonify(
                {
                    "success": True,
                    "connection_status": "connected",
                    "message": f"Successfully connected to Salesforce API. Found {len(accounts)} accounts.",
                    "test_result": {
                        "accounts_retrieved": len(accounts),
                        "api_response_time": "normal",  # Could be enhanced with actual timing
                    },
                }
            )

        except ImportError:
            return jsonify(
                {"error": "Salesforce service not available", "success": False}
            ), 503
        except Exception as e:
            logger.error(f"Salesforce connection test failed: {e}", exc_info=True)
            return jsonify(
                {
                    "success": False,
                    "connection_status": "failed",
                    "message": f"Salesforce API connection failed: {str(e)}",
                }
            ), 500

    except Exception as e:
        logger.error(f"Salesforce connection health check failed: {e}", exc_info=True)
        return jsonify(
            {"error": f"Connection health check failed: {str(e)}", "success": False}
        ), 500


@salesforce_health_bp.route("/api/salesforce/health/summary", methods=["GET"])
async def salesforce_health_summary():
    """
    Comprehensive health summary for Salesforce integration
    Provides a detailed overview of all Salesforce components
    """
    try:
        summary = {
            "service": "salesforce",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {},
        }

        # Run all health checks
        health_response = await salesforce_health()
        health_data = health_response.get_json()
        summary["components"]["overall"] = health_data

        # Add token health if user_id provided
        user_id = request.args.get("user_id")
        if user_id:
            token_response = await salesforce_token_health()
            token_data = token_response.get_json()
            summary["components"]["tokens"] = token_data

            # Add connection test if tokens are available
            if token_data.get("success") and token_data.get("token_health", {}).get(
                "has_tokens"
            ):
                connection_response = await salesforce_connection_health()
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
        logger.error(f"Salesforce health summary failed: {e}", exc_info=True)
        return jsonify(
            {
                "service": "salesforce",
                "overall_status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": f"Health summary failed: {str(e)}",
            }
        ), 500
