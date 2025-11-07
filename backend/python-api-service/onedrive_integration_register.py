"""
OneDrive Integration Registration

This module registers OneDrive integration with the main Flask application
and provides initialization functions for the integration.
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Import OneDrive handlers
try:
    from auth_handler_onedrive import onedrive_auth_bp, init_onedrive_oauth_table
    from onedrive_routes import onedrive_bp, register_onedrive_routes
    from onedrive_health_handler import (
        onedrive_health_bp,
        register_onedrive_health_routes,
    )

    ONEDRIVE_AVAILABLE = True
    logger.info("OneDrive handlers imported successfully")
except ImportError as e:
    ONEDRIVE_AVAILABLE = False
    logger.warning(f"OneDrive handlers not available: {e}")


def register_onedrive_integration(app) -> bool:
    """
    Register OneDrive integration with Flask application

    Args:
        app: Flask application instance

    Returns:
        bool: True if registration successful, False otherwise
    """
    try:
        if not ONEDRIVE_AVAILABLE:
            logger.warning("OneDrive integration not available - skipping registration")
            return False

        # Register authentication blueprint
        app.register_blueprint(
            onedrive_auth_bp, url_prefix="/api/auth", name="onedrive_auth"
        )
        logger.info("OneDrive authentication blueprint registered successfully")

        # Register main OneDrive routes
        register_onedrive_routes(app)
        logger.info("OneDrive routes registered successfully")

        # Register health endpoints
        register_onedrive_health_routes(app)
        logger.info("OneDrive health routes registered successfully")

        # Initialize OAuth table (placeholder for future implementation)
        init_onedrive_oauth_table()
        logger.info("OneDrive OAuth table initialized")

        logger.info("OneDrive integration registered successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to register OneDrive integration: {e}")
        return False


def get_onedrive_integration_status() -> Dict[str, Any]:
    """
    Get OneDrive integration status and configuration

    Returns:
        Dict with integration status and configuration details
    """
    status = {
        "service": "onedrive",
        "available": ONEDRIVE_AVAILABLE,
        "oauth_configured": bool(
            os.getenv("ONEDRIVE_CLIENT_ID") and os.getenv("ONEDRIVE_CLIENT_SECRET")
        ),
        "endpoints": {
            "auth_initiate": "/api/auth/onedrive/authorize",
            "auth_callback": "/api/auth/onedrive/callback",
            "connection_status": "/api/onedrive/connection-status",
            "list_files": "/api/onedrive/list-files",
            "search_files": "/api/onedrive/search",
            "file_metadata": "/api/onedrive/files/<file_id>",
            "download_file": "/api/onedrive/files/<file_id>/download",
            "ingest_document": "/api/onedrive/ingest-document",
            "health": "/api/onedrive/health",
        },
        "required_environment_variables": [
            "ONEDRIVE_CLIENT_ID",
            "ONEDRIVE_CLIENT_SECRET",
            "ONEDRIVE_REDIRECT_URI",
        ],
        "optional_environment_variables": ["ONEDRIVE_ACCESS_TOKEN"],
    }

    # Check individual environment variables
    for var in status["required_environment_variables"]:
        status[f"{var}_set"] = bool(os.getenv(var))

    for var in status["optional_environment_variables"]:
        status[f"{var}_set"] = bool(os.getenv(var))

    return status


def initialize_onedrive_integration() -> Dict[str, Any]:
    """
    Initialize OneDrive integration service

    Returns:
        Dict with initialization status
    """
    try:
        if not ONEDRIVE_AVAILABLE:
            return {
                "status": "error",
                "message": "OneDrive integration not available",
                "service": "onedrive",
            }

        # Check required configuration
        client_id = os.getenv("ONEDRIVE_CLIENT_ID")
        client_secret = os.getenv("ONEDRIVE_CLIENT_SECRET")
        redirect_uri = os.getenv("ONEDRIVE_REDIRECT_URI")

        if not all([client_id, client_secret, redirect_uri]):
            return {
                "status": "warning",
                "message": "OneDrive OAuth credentials not fully configured",
                "service": "onedrive",
                "missing_config": [
                    var
                    for var, value in {
                        "ONEDRIVE_CLIENT_ID": client_id,
                        "ONEDRIVE_CLIENT_SECRET": client_secret,
                        "ONEDRIVE_REDIRECT_URI": redirect_uri,
                    }.items()
                    if not value
                ],
            }

        # Initialize integration service
        from onedrive_integration_service import initialize_onedrive_integration_service

        success = initialize_onedrive_integration_service()

        if success:
            return {
                "status": "success",
                "message": "OneDrive integration initialized successfully",
                "service": "onedrive",
                "configuration": {
                    "client_id_configured": bool(client_id),
                    "client_secret_configured": bool(client_secret),
                    "redirect_uri_configured": bool(redirect_uri),
                },
            }
        else:
            return {
                "status": "error",
                "message": "Failed to initialize OneDrive integration service",
                "service": "onedrive",
            }

    except Exception as e:
        logger.error(f"Error initializing OneDrive integration: {e}")
        return {
            "status": "error",
            "message": f"Initialization failed: {str(e)}",
            "service": "onedrive",
        }


# Export functions for use in main application
__all__ = [
    "register_onedrive_integration",
    "get_onedrive_integration_status",
    "initialize_onedrive_integration",
    "ONEDRIVE_AVAILABLE",
]
