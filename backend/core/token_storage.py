"""
Token Storage Utility
Provides secure storage and retrieval for OAuth tokens to enable background workflow execution.
"""

from datetime import datetime
import json
import logging
import os
from typing import Any, Dict, Optional
import warnings

logger = logging.getLogger(__name__)

# [DEPRECATED] Use backend.core.connection_service.ConnectionService instead.
# This module will be removed in a future version.
warnings.warn("token_storage is deprecated. Use ConnectionService instead.", DeprecationWarning)

# File path for persistent JSON storage (MVP)
# Always store in backend directory regardless of where script is run from
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_STORAGE_FILE = os.path.join(_BACKEND_DIR, "oauth_tokens.json")

class TokenStorage:
    """
    Manages storage and retrieval of OAuth tokens.
    Currently uses a local JSON file for persistence.
    """
    
    def __init__(self, storage_file: str = TOKEN_STORAGE_FILE):
        logger.warning("Initializing DEPRECATED TokenStorage. Please migrate to ConnectionService.")
        self.storage_file = storage_file
        self._tokens: Dict[str, Any] = {}
        self._load_tokens()
    
    def _load_tokens(self):
        """Load tokens from storage file"""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    self._tokens = json.load(f)
                logger.info(f"Loaded tokens for {len(self._tokens)} providers")
            except Exception as e:
                logger.error(f"Failed to load tokens: {e}")
                self._tokens = {}
        else:
            logger.info("No token storage file found, starting empty")
            self._tokens = {}

    def _save_tokens(self):
        """Save tokens to storage file"""
        try:
            with open(self.storage_file, 'w') as f:
                json.dump(self._tokens, f, indent=2)
            logger.info("Tokens saved to storage")
        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")

    def save_token(self, provider: str, token_data: Dict[str, Any]):
        """
        Save token data for a provider.
        
        Args:
            provider: The provider name (e.g., 'google', 'slack')
            token_data: The token dictionary (access_token, refresh_token, etc.)
        """
        # Add timestamp
        token_data['updated_at'] = datetime.now().isoformat()
        
        # Calculate expiry if expires_in is present
        if 'expires_in' in token_data and 'expires_at' not in token_data:
            from datetime import timedelta
            expires_in = int(token_data['expires_in'])
            token_data['expires_at'] = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
        
        self._tokens[provider] = token_data
        self._save_tokens()
        logger.info(f"Saved token for provider: {provider}")

    def is_token_expired(self, provider: str) -> bool:
        """Check if a token is expired"""
        token = self.get_token(provider)
        if not token:
            return True
        
        expires_at_str = token.get('expires_at')
        if not expires_at_str:
            # If no expiry info, assume it's NOT expired (perpetual token)
            return False
            
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            # Add a 5-minute buffer
            return datetime.now() >= (expires_at - timedelta(minutes=5))
        except Exception:
            return True

    def get_token(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        Get token data for a provider.
        
        Args:
            provider: The provider name
            
        Returns:
            Dict containing token data or None if not found
        """
        return self._tokens.get(provider)

    def delete_token(self, provider: str):
        """Delete token for a provider"""
        if provider in self._tokens:
            del self._tokens[provider]
            self._save_tokens()
            logger.info(f"Deleted token for provider: {provider}")

# Global instance
token_storage = TokenStorage()
