"""
User API Key Management Service

This service handles user-specific API key storage and management for the BYOK (Bring Your Own Keys) system.
It allows each user to configure their own API keys for different AI providers and services.
"""

import os
import sqlite3
import base64
import json
import logging
from typing import Dict, List, Optional, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class UserAPIKeyService:
    """Service for managing user-specific API keys with secure encryption"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv(
            "DATABASE_URL", "sqlite:///./data/atom_development.db"
        ).replace("sqlite:///", "")
        self.encryption_key = self._get_encryption_key()
        self._init_database()

    def _get_encryption_key(self) -> bytes:
        """Get or generate encryption key for API key storage"""
        env_key = os.getenv("ATOM_OAUTH_ENCRYPTION_KEY")
        if env_key:
            # Use existing key from environment
            return base64.urlsafe_b64decode(env_key)
        else:
            # Generate new key (for development)
            key = Fernet.generate_key()
            logger.warning(
                "Using auto-generated encryption key - not secure for production!"
            )
            return base64.urlsafe_b64decode(key)

    def _init_database(self):
        """Initialize the SQLite database for API key storage"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create user_api_keys table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_api_keys (
                    user_id TEXT NOT NULL,
                    service_name TEXT NOT NULL,
                    encrypted_key TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, service_name)
                )
            """)

            # Create index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_api_keys_user_service
                ON user_api_keys(user_id, service_name)
            """)

            conn.commit()
            conn.close()
            logger.info("User API key database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize user API key database: {e}")
            raise

    def _encrypt_key(self, api_key: str) -> str:
        """Encrypt an API key using Fernet encryption"""
        fernet = Fernet(base64.urlsafe_b64encode(self.encryption_key))
        encrypted = fernet.encrypt(api_key.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def _decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt an API key using Fernet encryption"""
        try:
            fernet = Fernet(base64.urlsafe_b64encode(self.encryption_key))
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_key.encode())
            decrypted = fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt API key: {e}")
            raise

    def save_api_key(self, user_id: str, service_name: str, api_key: str) -> bool:
        """
        Save a user's API key for a specific service

        Args:
            user_id: The user's unique identifier
            service_name: The service name (e.g., 'openai', 'deepseek', 'google_gemini')
            api_key: The API key to save

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            encrypted_key = self._encrypt_key(api_key)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO user_api_keys
                (user_id, service_name, encrypted_key, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (user_id, service_name, encrypted_key),
            )

            conn.commit()
            conn.close()

            logger.info(
                f"Successfully saved API key for user {user_id}, service {service_name}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to save API key for user {user_id}, service {service_name}: {e}"
            )
            return False

    def get_api_key(self, user_id: str, service_name: str) -> Optional[str]:
        """
        Retrieve a user's API key for a specific service

        Args:
            user_id: The user's unique identifier
            service_name: The service name

        Returns:
            Optional[str]: The decrypted API key, or None if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT encrypted_key FROM user_api_keys
                WHERE user_id = ? AND service_name = ?
            """,
                (user_id, service_name),
            )

            result = cursor.fetchone()
            conn.close()

            if result:
                encrypted_key = result[0]
                return self._decrypt_key(encrypted_key)
            else:
                return None

        except Exception as e:
            logger.error(
                f"Failed to retrieve API key for user {user_id}, service {service_name}: {e}"
            )
            return None

    def delete_api_key(self, user_id: str, service_name: str) -> bool:
        """
        Delete a user's API key for a specific service

        Args:
            user_id: The user's unique identifier
            service_name: The service name

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM user_api_keys
                WHERE user_id = ? AND service_name = ?
            """,
                (user_id, service_name),
            )

            conn.commit()
            conn.close()

            logger.info(
                f"Successfully deleted API key for user {user_id}, service {service_name}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to delete API key for user {user_id}, service {service_name}: {e}"
            )
            return False

    def list_user_services(self, user_id: str) -> List[str]:
        """
        List all services for which a user has configured API keys

        Args:
            user_id: The user's unique identifier

        Returns:
            List[str]: List of service names
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT service_name FROM user_api_keys
                WHERE user_id = ?
                ORDER BY service_name
            """,
                (user_id,),
            )

            results = cursor.fetchall()
            conn.close()

            return [row[0] for row in results]

        except Exception as e:
            logger.error(f"Failed to list services for user {user_id}: {e}")
            return []

    def get_all_user_keys(self, user_id: str) -> Dict[str, str]:
        """
        Get all API keys for a user (for internal use only)

        Args:
            user_id: The user's unique identifier

        Returns:
            Dict[str, str]: Dictionary mapping service names to API keys
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT service_name, encrypted_key FROM user_api_keys
                WHERE user_id = ?
            """,
                (user_id,),
            )

            results = cursor.fetchall()
            conn.close()

            user_keys = {}
            for service_name, encrypted_key in results:
                try:
                    user_keys[service_name] = self._decrypt_key(encrypted_key)
                except Exception as e:
                    logger.error(
                        f"Failed to decrypt key for service {service_name}: {e}"
                    )
                    continue

            return user_keys

        except Exception as e:
            logger.error(f"Failed to get all keys for user {user_id}: {e}")
            return {}

    def test_api_key(self, user_id: str, service_name: str) -> Dict[str, Any]:
        """
        Test if an API key is valid by making a simple API call

        Args:
            user_id: The user's unique identifier
            service_name: The service name

        Returns:
            Dict[str, Any]: Test result with success status and message
        """
        api_key = self.get_api_key(user_id, service_name)
        if not api_key:
            return {"success": False, "message": "No API key found for this service"}

        try:
            # Import service handlers dynamically
            if service_name == "openai":
                from openai_handler_real import OpenAIServiceReal

                service = OpenAIServiceReal()
                service.api_key = api_key
                result = service.test_connection()

            elif service_name == "deepseek":
                from deepseek_handler_real import DeepSeekServiceReal

                service = DeepSeekServiceReal()
                service.api_key = api_key
                result = service.test_connection()

            elif service_name == "anthropic":
                from anthropic_handler_real import AnthropicServiceReal

                service = AnthropicServiceReal()
                service.api_key = api_key
                result = service.test_connection()

            elif service_name == "google_gemini":
                from google_handler_real import GoogleGeminiServiceReal

                service = GoogleGeminiServiceReal()
                service.api_key = api_key
                result = service.test_connection()

            else:
                return {
                    "success": False,
                    "message": f"Service {service_name} not supported for testing",
                }

            return result

        except ImportError:
            return {
                "success": False,
                "message": f"Service handler for {service_name} not available",
            }
        except Exception as e:
            logger.error(
                f"API key test failed for user {user_id}, service {service_name}: {e}"
            )
            return {"success": False, "message": f"Test failed: {str(e)}"}


# Global instance for easy access
user_api_key_service = UserAPIKeyService()


def get_user_api_key_service() -> UserAPIKeyService:
    """Get the global user API key service instance"""
    return user_api_key_service


# Example usage and testing
if __name__ == "__main__":
    # Test the service
    service = UserAPIKeyService()

    # Test data
    test_user_id = "test_user_123"
    test_service = "openai"
    test_api_key = "sk-test-key-123456789"

    # Test saving
    print("Testing API key save...")
    success = service.save_api_key(test_user_id, test_service, test_api_key)
    print(f"Save successful: {success}")

    # Test retrieval
    print("Testing API key retrieval...")
    retrieved_key = service.get_api_key(test_user_id, test_service)
    print(f"Retrieved key: {retrieved_key}")
    print(f"Keys match: {retrieved_key == test_api_key}")

    # Test listing
    print("Testing service listing...")
    services = service.list_user_services(test_user_id)
    print(f"User services: {services}")

    # Test deletion
    print("Testing API key deletion...")
    delete_success = service.delete_api_key(test_user_id, test_service)
    print(f"Delete successful: {delete_success}")

    # Verify deletion
    final_key = service.get_api_key(test_user_id, test_service)
    print(f"Key after deletion: {final_key}")
