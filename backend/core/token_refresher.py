"""
Token Refresh Automation

Automatically refreshes OAuth tokens before they expire to prevent service interruptions.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
from pathlib import Path

from core.token_storage import TokenStorage
import httpx

logger = logging.getLogger(__name__)

class TokenRefresher:
    """
    Background service that monitors and refreshes OAuth tokens.
    """
    
    def __init__(self, token_storage: Optional[TokenStorage] = None):
        self.token_storage = token_storage or TokenStorage()
        self.refresh_config = self._load_refresh_config()
        self.running = False
        
    def _load_refresh_config(self) -> Dict[str, Dict]:
        """Load OAuth refresh configuration for each provider"""
        return {
            "google": {
                "token_url": "https://oauth2.googleapis.com/token",
                "refresh_threshold_hours": 1,  # Refresh if expires in < 1 hour
            },
            "microsoft": {
                "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                "refresh_threshold_hours": 1,
            },
            "salesforce": {
                "token_url": "https://login.salesforce.com/services/oauth2/token",
                "refresh_threshold_hours": 2,
            },
            "slack": {
                "token_url": "https://slack.com/api/oauth.v2.access",
                "refresh_threshold_hours": 6,
            },
            "github": {
                "token_url": "https://github.com/login/oauth/access_token",
                "refresh_threshold_hours": 12,
            }
        }
    
    async def check_and_refresh_token(
        self, 
        user_id: str, 
        provider: str, 
        token_data: Dict
    ) -> bool:
        """
        Check if token needs refresh and refresh if necessary.
        
        Returns:
            True if token was refreshed, False otherwise
        """
        config = self.refresh_config.get(provider)
        if not config:
            logger.debug(f"No refresh config for provider: {provider}")
            return False
        
        # Check if token has expiration info
        expires_at = token_data.get("expires_at")
        if not expires_at:
            logger.debug(f"Token for {provider} has no expiration info")
            return False
        
        # Parse expiration time
        try:
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            elif isinstance(expires_at, (int, float)):
                expires_at = datetime.fromtimestamp(expires_at)
        except Exception as e:
            logger.error(f"Error parsing expires_at for {provider}: {e}")
            return False
        
        # Check if token needs refresh
        threshold = timedelta(hours=config["refresh_threshold_hours"])
        if datetime.now() < expires_at - threshold:
            logger.debug(f"Token for {provider} is still valid, no refresh needed")
            return False
        
        # Attempt to refresh
        refresh_token = token_data.get("refresh_token")
        if not refresh_token:
            logger.warning(f"No refresh_token available for {provider}")
            return False
        
        try:
            new_token_data = await self._perform_refresh(provider, refresh_token, config)
            if new_token_data:
                # Update stored token
                self.token_storage.store_token(user_id, provider, new_token_data)
                logger.info(f"Successfully refreshed token for {user_id}/{provider}")
                return True
        except Exception as e:
            logger.error(f"Failed to refresh token for {provider}: {e}")
        
        return False
    
    async def _perform_refresh(
        self, 
        provider: str, 
        refresh_token: str,
        config: Dict
    ) -> Optional[Dict]:
        """
        Perform the actual token refresh request.
        """
        # Get client credentials from environment
        import os
        client_id = os.getenv(f"{provider.upper()}_CLIENT_ID")
        client_secret = os.getenv(f"{provider.upper()}_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            logger.warning(f"Missing client credentials for {provider}")
            return None
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config["token_url"],
                data=data,
                headers={"Accept": "application/json"}
            )
            
            if response.status_code == 200:
                new_data = response.json()
                
                # Calculate new expiration time
                if "expires_in" in new_data:
                    new_data["expires_at"] = (
                        datetime.now() + timedelta(seconds=new_data["expires_in"])
                    ).isoformat()
                
                # Preserve refresh_token if not included in response
                if "refresh_token" not in new_data:
                    new_data["refresh_token"] = refresh_token
                
                return new_data
            else:
                logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                return None
    
    async def run_refresh_cycle(self):
        """
        Run one cycle of checking and refreshing all tokens.
        """
        logger.info("Starting token refresh cycle")
        
        # Get all stored tokens
        all_tokens = self.token_storage.list_all_tokens()
        
        refresh_count = 0
        for user_id, provider, token_data in all_tokens:
            try:
                refreshed = await self.check_and_refresh_token(user_id, provider, token_data)
                if refreshed:
                    refresh_count += 1
            except Exception as e:
                logger.error(f"Error checking token for {user_id}/{provider}: {e}")
        
        logger.info(f"Token refresh cycle complete. Refreshed {refresh_count} tokens.")
    
    async def start_background_service(self, interval_minutes: int = 60):
        """
        Start the background token refresh service.
        
        Args:
            interval_minutes: How often to check for tokens to refresh
        """
        self.running = True
        logger.info(f"Starting token refresh background service (interval: {interval_minutes}m)")
        
        while self.running:
            try:
                await self.run_refresh_cycle()
            except Exception as e:
                logger.error(f"Error in refresh cycle: {e}")
            
            # Wait for next cycle
            await asyncio.sleep(interval_minutes * 60)
    
    def stop(self):
        """Stop the background service"""
        self.running = False
        logger.info("Token refresh service stopped")


# Global instance
_token_refresher = None

def get_token_refresher() -> TokenRefresher:
    """Get or create global TokenRefresher instance"""
    global _token_refresher
    if _token_refresher is None:
        _token_refresher = TokenRefresher()
    return _token_refresher
