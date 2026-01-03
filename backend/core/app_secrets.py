"""
App Secrets Manager
Provides access to secrets via environment variables or local persistence.
Named 'app_secrets.py' to avoid gitignore issues.
"""

import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SecretManager:
    """
    Manages application secrets.
    Prioritizes environment variables, falls back to local storage.
    """
    def __init__(self):
        # Store secrets.json in the backend directory
        self._backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._secrets_file = os.path.join(self._backend_dir, "secrets.json")
        self._secrets = {}
        self._load_secrets()

    def _load_secrets(self):
        """Load secrets from file"""
        if os.path.exists(self._secrets_file):
            try:
                with open(self._secrets_file, 'r') as f:
                    self._secrets = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load secrets: {e}")

    def _save_secrets(self):
        """Save secrets to file"""
        try:
            with open(self._secrets_file, 'w') as f:
                json.dump(self._secrets, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save secrets: {e}")

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret value.
        1. Check environment variable
        2. Check local storage
        3. Return default
        """
        # Try env var first
        val = os.getenv(key)
        if val is not None:
            return val
        
        # Try local store
        return self._secrets.get(key, default)

    def set_secret(self, key: str, value: str):
        """
        Set a secret value in local storage.
        Does NOT update environment variables.
        """
        self._secrets[key] = value
        self._save_secrets()

# Global instance
_secret_manager = SecretManager()

def get_secret_manager():
    """Get the global secret manager instance"""
    return _secret_manager
