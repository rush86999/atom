
from flask import Blueprint, jsonify
import logging

logger = logging.getLogger(__name__)

outlook_bp = Blueprint("outlook", __name__)

@outlook_bp.route("/api/outlook/health", methods=["GET"])
def outlook_health():
    """Health check for Outlook integration"""
    try:
        # Check if Outlook OAuth is configured
        # In a real implementation, this would test actual Outlook API connectivity
        
        return jsonify({
            "success": True,
            "service": "outlook",
            "status": "healthy",
            "message": "Outlook health endpoint available",
            "oauth_configured": False,  # Would check actual OAuth config
            "api_accessible": False,    # Would test actual API access
            "timestamp": "2025-10-31T10:00:00Z"
        }), 200
    except Exception as e:
        logger.error(f"Outlook health check failed: {e}")
        return jsonify({
            "success": False,
            "service": "outlook",
            "status": "unhealthy",
            "error": str(e),
            "timestamp": "2025-10-31T10:00:00Z"
        }), 500
