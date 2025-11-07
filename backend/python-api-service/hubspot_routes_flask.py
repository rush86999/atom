"""
ATOM HubSpot Integration Routes (Flask Version)
Flask routes for HubSpot marketing and CRM functionality
Following ATOM API patterns and conventions
"""

from flask import Blueprint, request, jsonify
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, date
from loguru import logger
import asyncio
import traceback

from hubspot_service import create_hubspot_service, HubSpotService
from db_oauth_hubspot import create_hubspot_db_handler, HubSpotOAuthToken
from auth_handler_hubspot import HubSpotAuthHandler

# Create blueprint
router = Blueprint('hubspot', __name__, url_prefix='/api/hubspot')

# Global instances
hubspot_service = create_hubspot_service()
db_handler = create_hubspot_db_handler()
auth_handler = HubSpotAuthHandler()

# Decorator for requiring valid tokens
def require_hubspot_auth(f):
    def decorated_function(*args, **kwargs):
        try:
            # Extract user_id from request
            user_id = request.args.get('user_id')
            if not user_id and request.is_json:
                data = request.get_json()
                user_id = data.get('user_id')
            
            if not user_id:
                return jsonify({
                    "ok": False,
                    "error": "user_id parameter is required"
                }), 400
            
            # Run async function to get tokens
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                tokens = loop.run_until_complete(db_handler.get_tokens(user_id))
            finally:
                loop.close()
            
            if not tokens:
                return jsonify({
                    "ok": False,
                    "error": "HubSpot not authenticated for this user"
                }), 401
            
            if not tokens.hub_id:
                return jsonify({
                    "ok": False,
                    "error": "HubSpot hub ID not configured"
                }), 400
            
            # Store in Flask's request context for route to use
            request.hubspot_tokens = tokens
            request.hubspot_access_token = tokens.access_token
            request.hubspot_hub_id = tokens.hub_id
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"HubSpot auth decorator error: {e}")
            return jsonify({
                "ok": False,
                "error": f"Authentication failed: {str(e)}"
            }), 500
    
    return decorated_function

# Health check endpoint
@router.route("/health", methods=["GET"])
def health_check():
    """HubSpot integration health check"""
    try:
        # Check service configuration
        config_status = bool(
            hubspot_service.config.client_id and
            hubspot_service.config.client_secret
        )
        
        return jsonify({
            "ok": True,
            "data": {
                "service": "hubspot",
                "status": "healthy" if config_status else "misconfigured",
                "configured": config_status,
                "database_connected": db_handler is not None,
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"HubSpot health check failed: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Export blueprint
def register_hubspot_routes(app):
    """Register HubSpot API routes"""
    app.register_blueprint(router)
    logger.info("HubSpot API routes registered")
