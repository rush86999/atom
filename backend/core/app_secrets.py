"""
App Secrets Manager with Encryption Support
Provides access to secrets via environment variables or local persistence.
Supports Fernet encryption for secure storage.
"""

import json
import logging
import os
import base64
from typing import Optional

logger = logging.getLogger(__name__)

class SecretManager:
    """
    Manages application secrets with encryption support.
    Prioritizes environment variables, falls back to local storage.
    """
    def __init__(self):
        # Store secrets.json in the backend directory
        self._backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._secrets_file = os.path.join(self._backend_dir, "secrets.json")
        self._secrets_encrypted_file = os.path.join(self._backend_dir, "secrets.enc")
        self._secrets = {}
        self._encryption_enabled = False
        self._fernet = None

        self._init_encryption()
        self._load_secrets()

    def _init_encryption(self):
        """Initialize encryption if ENCRYPTION_KEY is set"""
        encryption_key = os.getenv('ENCRYPTION_KEY')
        environment = os.getenv('ENVIRONMENT', 'development')

        if encryption_key:
            try:
                from cryptography.fernet import Fernet
                from cryptography.hazmat.primitives import hashes
                from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

                kdf = PBKDF2(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'atom_salt',
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
                self._fernet = Fernet(key)
                self._encryption_enabled = True
                logger.info("✓ Secrets encryption enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize encryption: {e}")
                self._encryption_enabled = False
        else:
            if environment == 'production':
                logger.warning("⚠️ SECURITY: ENCRYPTION_KEY not set in production. Secrets will be stored in plaintext.")

    def _load_secrets(self):
        """Load secrets from file (encrypted or plaintext)"""
        # Try encrypted file first
        if self._encryption_enabled and os.path.exists(self._secrets_encrypted_file):
            try:
                with open(self._secrets_encrypted_file, 'rb') as f:
                    encrypted_data = f.read()
                    decrypted_data = self._fernet.decrypt(encrypted_data)
                    self._secrets = json.loads(decrypted_data.decode())
                logger.info("Loaded encrypted secrets from file")
                return
            except Exception as e:
                logger.error(f"Failed to load encrypted secrets: {e}")

        # Try plaintext file (legacy)
        if os.path.exists(self._secrets_file):
            try:
                with open(self._secrets_file, 'r') as f:
                    self._secrets = json.load(f)

                environment = os.getenv('ENVIRONMENT', 'development')
                if environment == 'production':
                    logger.warning("⚠️ SECURITY: Loaded secrets from plaintext file in production.")

                # Auto-migrate to encrypted
                if self._encryption_enabled:
                    logger.info("Migrating secrets to encrypted storage...")
                    self._save_secrets()
                    os.remove(self._secrets_file)

            except Exception as e:
                logger.error(f"Failed to load secrets: {e}")

    def _save_secrets(self):
        """Save secrets to file (encrypted if enabled)"""
        try:
            if self._encryption_enabled:
                data = json.dumps(self._secrets, indent=2).encode()
                encrypted_data = self._fernet.encrypt(data)

                with open(self._secrets_encrypted_file, 'wb') as f:
                    f.write(encrypted_data)

                os.chmod(self._secrets_encrypted_file, 0o600)
                logger.info("Saved encrypted secrets to file")
            else:
                with open(self._secrets_file, 'w') as f:
                    json.dump(self._secrets, f, indent=2)

                os.chmod(self._secrets_file, 0o600)

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

    def get_security_status(self):
        """Get security status of secrets storage"""
        return {
            "encryption_enabled": self._encryption_enabled,
            "storage_type": "encrypted" if self._encryption_enabled else "plaintext",
            "secrets_count": len(self._secrets),
            "environment": os.getenv('ENVIRONMENT', 'development')
        }

# Global instance
_secret_manager = SecretManager()

def get_secret_manager():
    """Get the global secret manager instance"""
    return _secret_manager
