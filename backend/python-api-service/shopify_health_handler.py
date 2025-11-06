"""
Shopify Health Handler for ATOM Agent Memory System

This module provides health monitoring endpoints for Shopify integration.
It checks the connectivity and status of Shopify services and OAuth tokens.
"""

import logging
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timezone
import asyncio

logger = logging.getLogger(__name__)

shopify_health_bp = Blueprint("shopify_health_bp", __name__)


@shopify_health_bp.route("/api/shopify/health", methods=["GET"])
async def shopify_health():
    """
    Health check endpoint for Shopify integration
    Returns the overall health status of Shopify services
    """
    try:
        health_status = {
            "service": "shopify",
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

        # Check Shopify OAuth configuration
        try:
            from auth_handler_shopify import SHOPIFY_API_KEY, SHOPIFY_API_SECRET

            if SHOPIFY_API_KEY and SHOPIFY_API_SECRET:
                health_status["checks"]["oauth_config"] = {
                    "status": "healthy",
                    "message": "Shopify OAuth configuration valid",
                }
            else:
                health_status["status"] = "degraded"
                health_status["checks"]["oauth_config"] = {
                    "status": "misconfigured",
                    "message": "Shopify OAuth configuration incomplete",
                }
        except ImportError:
            health_status["status"] = "degraded"
            health_status["checks"]["oauth_config"] = {
                "status": "unavailable",
                "message": "Shopify OAuth handler not available",
            }
        except Exception as e:
            health_status["status"] = "degraded"
            health_status["checks"]["oauth_config"] = {
                "status": "error",
                "message": f"Shopify OAuth configuration check failed: {str(e)}",
            }

        # Check Shopify service availability
        try:
            from shopify_service import get_shopify_client

            health_status["checks"]["service"] = {
                "status": "healthy",
                "message": "Shopify service available",
            }
        except ImportError:
            health_status["status"] = "degraded"
            health_status["checks"]["service"] = {
                "status": "unavailable",
                "message": "Shopify service not available",
            }

        # Check enhanced API availability
        try:
            from shopify_enhanced_api import shopify_enhanced_bp

            health_status["checks"]["enhanced_api"] = {
                "status": "healthy",
                "message": "Shopify enhanced API available",
            }
        except ImportError:
            health_status["checks"]["enhanced_api"] = {
                "status": "unavailable",
                "message": "Shopify enhanced API not available",
            }

        return jsonify(health_status)

    except Exception as e:
        logger.error(f"Shopify health check failed: {e}", exc_info=True)
        return jsonify(
            {
                "service": "shopify",
                "status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": f"Health check failed: {str(e)}",
            }
        ), 500


@shopify_health_bp.route("/api/shopify/health/tokens", methods=["GET"])
async def shopify_token_health():
    """
    Health check for Shopify OAuth tokens
    Returns the status of active Shopify OAuth tokens
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
            from db_oauth_shopify import get_user_shopify_tokens

            tokens = await get_user_shopify_tokens(db_conn_pool, user_id)

            if tokens:
                token_status = {
                    "user_id": user_id,
                    "has_tokens": True,
                    "token_status": "active",
                    "shop_domain": tokens.get("shop_domain"),
                    "shop_id": tokens.get("shop_id"),
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
                            "message": "No Shopify OAuth tokens found for user",
                        },
                    }
                )

        except ImportError:
            return jsonify(
                {
                    "error": "Shopify OAuth database handler not available",
                    "success": False,
                }
            ), 503

    except Exception as e:
        logger.error(f"Shopify token health check failed: {e}", exc_info=True)
        return jsonify(
            {"error": f"Token health check failed: {str(e)}", "success": False}
        ), 500


@shopify_health_bp.route("/api/shopify/health/connection", methods=["GET"])
async def shopify_connection_health():
    """
    Test Shopify API connection
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
            from shopify_service import get_shopify_client, get_shop_info

            shopify_client = await get_shopify_client(user_id, db_conn_pool)

            if not shopify_client:
                return jsonify(
                    {
                        "success": False,
                        "connection_status": "unauthenticated",
                        "message": "No authenticated Shopify client available",
                    }
                ), 401

            # Test connection by getting shop info
            shop_info = await get_shop_info(user_id, db_conn_pool)

            if shop_info.get("ok"):
                return jsonify(
                    {
                        "success": True,
                        "connection_status": "connected",
                        "message": f"Successfully connected to Shopify API. Shop: {shop_info.get('shop', {}).get('name', 'Unknown')}",
                        "test_result": {
                            "shop_name": shop_info.get("shop", {}).get("name"),
                            "shop_domain": shop_info.get("shop", {}).get("domain"),
                            "api_response_time": "normal",
                        },
                    }
                )
            else:
                return jsonify(
                    {
                        "success": False,
                        "connection_status": "failed",
                        "message": f"Shopify API connection failed: {shop_info.get('error', {}).get('message', 'Unknown error')}",
                    }
                ), 500

        except ImportError:
            return jsonify(
                {"error": "Shopify service not available", "success": False}
            ), 503
        except Exception as e:
            logger.error(f"Shopify connection test failed: {e}", exc_info=True)
            return jsonify(
                {
                    "success": False,
                    "connection_status": "failed",
                    "message": f"Shopify API connection failed: {str(e)}",
                }
            ), 500

    except Exception as e:
        logger.error(f"Shopify connection health check failed: {e}", exc_info=True)
        return jsonify(
            {"error": f"Connection health check failed: {str(e)}", "success": False}
        ), 500


@shopify_health_bp.route("/api/shopify/health/summary", methods=["GET"])
async def shopify_health_summary():
    """
    Comprehensive health summary for Shopify integration
    Provides a detailed overview of all Shopify components
    """
    try:
        summary = {
            "service": "shopify",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {},
        }

        # Run all health checks
        health_response = await shopify_health()
        health_data = health_response.get_json()
        summary["components"]["overall"] = health_data

        # Add token health if user_id provided
        user_id = request.args.get("user_id")
        if user_id:
            token_response = await shopify_token_health()
            token_data = token_response.get_json()
            summary["components"]["tokens"] = token_data

            # Add connection test if tokens are available
            if token_data.get("success") and token_data.get("token_health", {}).get(
                "has_tokens"
            ):
                connection_response = await shopify_connection_health()
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
        logger.error(f"Shopify health summary failed: {e}", exc_info=True)
        return jsonify(
            {
                "service": "shopify",
                "overall_status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": f"Health summary failed: {str(e)}",
            }
        ), 500
