"""
ATOM Slack Service - Basic Service Interface
Compatibility layer that imports from enhanced Slack service
"""

import os
import logging
from typing import Dict, Any, List, Optional
from loguru import logger

try:
    # Import the enhanced service implementation
    from slack_enhanced_service import (
        SlackEnhancedService,
        SlackEventType,
        SlackPermission,
        slack_enhanced_service
    )

    # Re-export for backward compatibility
    class SlackService(SlackEnhancedService):
        """Basic Slack service interface - uses enhanced implementation"""

        def __init__(self):
            super().__init__()
            logger.info("Slack service initialized using enhanced implementation")

    # Create global instance for backward compatibility
    slack_service = SlackService()

    ENHANCED_AVAILABLE = True
    logger.info("Enhanced Slack service imported successfully")

except ImportError as e:
    logger.warning(f"Enhanced Slack service not available: {e}")

    # Fallback basic service
    class SlackService:
        """Basic Slack service fallback"""

        def __init__(self):
            self.client_id = os.getenv("SLACK_CLIENT_ID", "")
            self.client_secret = os.getenv("SLACK_CLIENT_SECRET", "")
            self.signing_secret = os.getenv("SLACK_SIGNING_SECRET", "")
            logger.info("Slack service initialized with basic fallback implementation")

        async def health_check(self) -> Dict[str, Any]:
            """Basic health check"""
            return {
                "status": "healthy" if self.client_id else "incomplete",
                "service": "slack_basic",
                "client_configured": bool(self.client_id),
                "timestamp": "2025-01-01T00:00:00Z"
            }

        async def get_oauth_url(self, redirect_uri: str, state: str) -> str:
            """Get OAuth URL"""
            return f"https://slack.com/oauth/v2/authorize?client_id={self.client_id}&redirect_uri={redirect_uri}&state={state}"

        async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
            """Exchange authorization code for access token"""
            return {"error": "Enhanced service not available for token exchange"}

    # Create global instance
    slack_service = SlackService()
    ENHANCED_AVAILABLE = False
    logger.info("Basic Slack service fallback initialized")

# Export service instance for routes
__all__ = ['slack_service', 'SlackService', 'ENHANCED_AVAILABLE']