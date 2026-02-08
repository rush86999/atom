"""
OAuth Token Refresh Service
Automatically refreshes OAuth tokens before they expire
"""

import asyncio
from datetime import datetime, timedelta
import logging
import os
from typing import Dict, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

class TokenRefresher:
    """Manages automatic OAuth token refresh for all configured integrations"""
    
    def __init__(self):
        self.token_metadata = {}  # service_name -> {expires_at, refresh_token, etc}
        self.refresh_handlers = {}  # service_name -> refresh_function
    
    def register_service(
        self,
        service_name: str,
        refresh_handler: callable,
        expires_at: Optional[datetime] = None,
        refresh_token: Optional[str] = None
    ):
        """Register a service for automatic token refresh"""
        self.refresh_handlers[service_name] = refresh_handler
        self.token_metadata[service_name] = {
            "expires_at": expires_at,
            "refresh_token": refresh_token,
            "last_refreshed": None
        }
        logger.info(f"Registered {service_name} for automatic token refresh")
    
    def should_refresh(self, service_name: str, buffer_minutes: int = 15) -> bool:
        """Check if a token should be refreshed"""
        if service_name not in self.token_metadata:
            return False
        
        metadata = self.token_metadata[service_name]
        expires_at = metadata.get("expires_at")
        
        if not expires_at:
            return False
        
        # Refresh if expiring within buffer_minutes
        return datetime.now() + timedelta(minutes=buffer_minutes) >= expires_at
    
    async def refresh_token(self, service_name: str) -> bool:
        """Refresh OAuth token for a service"""
        if service_name not in self.refresh_handlers:
            logger.error(f"No refresh handler registered for {service_name}")
            return False
        
        try:
            handler = self.refresh_handlers[service_name]
            new_token_data = await handler(self.token_metadata[service_name])
            
            # Update metadata
            if new_token_data:
                self.token_metadata[service_name].update({
                    "expires_at": new_token_data.get("expires_at"),
                    "refresh_token": new_token_data.get("refresh_token"),
                    "last_refreshed": datetime.now()
                })
                logger.info(f"Successfully refreshed token for {service_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to refresh token for {service_name}: {str(e)}")
            return False
        
        return False
    
    async def check_and_refresh_all(self):
        """Check all services and refresh tokens as needed"""
        refresh_tasks = []
        
        for service_name in self.token_metadata.keys():
            if self.should_refresh(service_name):
                logger.info(f"Token for {service_name} needs refresh")
                refresh_tasks.append(self.refresh_token(service_name))
        
        if refresh_tasks:
            results = await asyncio.gather(*refresh_tasks, return_exceptions=True)
            successful = sum(1 for r in results if r is True)
            logger.info(f"Refreshed {successful}/{len(refresh_tasks)} tokens")
    
    def get_status(self) -> Dict:
        """Get status of all registered tokens"""
        status = {}
        for service_name, metadata in self.token_metadata.items():
            expires_at = metadata.get("expires_at")
            status[service_name] = {
                "expires_at": expires_at.isoformat() if expires_at else None,
                "needs_refresh": self.should_refresh(service_name),
                "last_refreshed": metadata.get("last_refreshed").isoformat() if metadata.get("last_refreshed") else None
            }
        return status


# OAuth token refresh handlers for major integrations
async def refresh_google_token(metadata: Dict) -> Optional[Dict]:
    """Refresh Google OAuth token using OAuthHandler"""
    from core.oauth_handler import GOOGLE_OAUTH_CONFIG, OAuthHandler

    refresh_token = metadata.get("refresh_token")
    if not refresh_token:
        logger.error("No refresh_token available for Google")
        return None

    try:
        handler = OAuthHandler(GOOGLE_OAUTH_CONFIG)
        logger.info("Refreshing Google OAuth token...")

        token_response = await handler.refresh_access_token(refresh_token)

        # Calculate expires_at from expires_in
        expires_in = token_response.get("expires_in", 3600)  # Default 1 hour
        return {
            "expires_at": datetime.now() + timedelta(seconds=expires_in),
            "refresh_token": token_response.get("refresh_token", refresh_token),
            "access_token": token_response.get("access_token")
        }
    except Exception as e:
        logger.error(f"Failed to refresh Google token: {e}")
        return None

async def refresh_microsoft_token(metadata: Dict) -> Optional[Dict]:
    """Refresh Microsoft OAuth token using OAuthHandler"""
    from core.oauth_handler import MICROSOFT_OAUTH_CONFIG, OAuthHandler

    refresh_token = metadata.get("refresh_token")
    if not refresh_token:
        logger.error("No refresh_token available for Microsoft")
        return None

    try:
        handler = OAuthHandler(MICROSOFT_OAUTH_CONFIG)
        logger.info("Refreshing Microsoft OAuth token...")

        token_response = await handler.refresh_access_token(refresh_token)

        # Calculate expires_at from expires_in
        expires_in = token_response.get("expires_in", 3600)  # Default 1 hour
        return {
            "expires_at": datetime.now() + timedelta(seconds=expires_in),
            "refresh_token": token_response.get("refresh_token", refresh_token),
            "access_token": token_response.get("access_token")
        }
    except Exception as e:
        logger.error(f"Failed to refresh Microsoft token: {e}")
        return None

async def refresh_salesforce_token(metadata: Dict) -> Optional[Dict]:
    """Refresh Salesforce OAuth token using OAuthHandler"""
    from core.oauth_handler import SALESFORCE_OAUTH_CONFIG, OAuthHandler

    refresh_token = metadata.get("refresh_token")
    if not refresh_token:
        logger.error("No refresh_token available for Salesforce")
        return None

    try:
        handler = OAuthHandler(SALESFORCE_OAUTH_CONFIG)
        logger.info("Refreshing Salesforce OAuth token...")

        token_response = await handler.refresh_access_token(refresh_token)

        # Salesforce tokens typically last longer
        expires_in = token_response.get("expires_in", 7200)  # Default 2 hours
        return {
            "expires_at": datetime.now() + timedelta(seconds=expires_in),
            "refresh_token": token_response.get("refresh_token", refresh_token),
            "access_token": token_response.get("access_token")
        }
    except Exception as e:
        logger.error(f"Failed to refresh Salesforce token: {e}")
        return None


# Global token refresher instance
token_refresher = TokenRefresher()

# Register OAuth services for auto-refresh
# In production, this would be configured with actual token data
if os.getenv("GMAIL_CLIENT_ID"):
   token_refresher.register_service("google", refresh_google_token)

if os.getenv("OUTLOOK_CLIENT_ID"):
    token_refresher.register_service("microsoft", refresh_microsoft_token)

if os.getenv("SALESFORCE_CLIENT_ID"):
    token_refresher.register_service("salesforce", refresh_salesforce_token)
