"""
Zoom Integration Registration
Registers Zoom integration with the main ATOM application
"""

import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)


def register_zoom_integration(app):
    """
    Register Zoom integration routes with the main FastAPI application

    Args:
        app: FastAPI application instance
    """
    try:
        # Import Zoom routes
        from .zoom_routes import router as zoom_router

        # Include Zoom router
        app.include_router(zoom_router)

        logger.info("✅ Zoom integration routes registered successfully")
        return True

    except ImportError as e:
        logger.warning(f"⚠️ Zoom integration not available: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to register Zoom integration: {e}")
        return False


def get_zoom_integration_info():
    """
    Get information about the Zoom integration

    Returns:
        Dictionary with integration information
    """
    return {
        "name": "Zoom",
        "version": "1.0.0",
        "description": "Zoom video conferencing integration",
        "features": [
            "meeting_management",
            "user_management",
            "webhooks",
            "analytics",
            "recordings",
            "oauth_authentication",
        ],
        "endpoints": [
            "/api/zoom/auth/callback",
            "/api/zoom/auth/disconnect",
            "/api/zoom/connection-status",
            "/api/zoom/users",
            "/api/zoom/users/{user_id}",
            "/api/zoom/meetings",
            "/api/zoom/meetings/{meeting_id}",
            "/api/zoom/webhooks",
            "/api/zoom/analytics/meetings",
            "/api/zoom/recordings",
            "/api/zoom/health",
            "/api/zoom/config",
        ],
        "required_env_vars": [
            "ZOOM_CLIENT_ID",
            "ZOOM_CLIENT_SECRET",
            "ZOOM_REDIRECT_URI",
        ],
        "status": "available",
    }
