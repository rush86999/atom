"""
Salesforce Integration Registration
Registers Salesforce integration with the main ATOM application
"""

import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)


def register_salesforce_integration(app):
    """
    Register Salesforce integration routes with the main FastAPI application

    Args:
        app: FastAPI application instance
    """
    try:
        # Import Salesforce routes
        from .salesforce_routes import router as salesforce_router

        # Include Salesforce router
        app.include_router(salesforce_router)

        logger.info("✅ Salesforce integration routes registered successfully")
        return True

    except ImportError as e:
        logger.warning(f"⚠️ Salesforce integration not available: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to register Salesforce integration: {e}")
        return False


def get_salesforce_integration_info():
    """
    Get information about the Salesforce integration

    Returns:
        Dictionary with integration information
    """
    return {
        "name": "Salesforce",
        "version": "1.0.0",
        "description": "Salesforce CRM integration",
        "features": [
            "account_management",
            "contact_management",
            "opportunity_management",
            "lead_management",
            "analytics",
            "search",
            "oauth_authentication",
        ],
        "endpoints": [
            "/api/salesforce/auth/callback",
            "/api/salesforce/auth/disconnect",
            "/api/salesforce/connection-status",
            "/api/salesforce/accounts",
            "/api/salesforce/accounts/{account_id}",
            "/api/salesforce/contacts",
            "/api/salesforce/contacts/{contact_id}",
            "/api/salesforce/opportunities",
            "/api/salesforce/opportunities/{opportunity_id}",
            "/api/salesforce/leads",
            "/api/salesforce/leads/{lead_id}",
            "/api/salesforce/search",
            "/api/salesforce/analytics/pipeline",
            "/api/salesforce/analytics/leads",
            "/api/salesforce/health",
            "/api/salesforce/config",
        ],
        "required_env_vars": [
            "SALESFORCE_CLIENT_ID",
            "SALESFORCE_CLIENT_SECRET",
            "SALESFORCE_REDIRECT_URI",
            "SALESFORCE_INSTANCE_URL",
        ],
        "status": "available",
    }
