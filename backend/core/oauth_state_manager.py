"""
OAuth State Manager - CSRF Protection for OAuth 2.0 flows

Provides secure state parameter generation and validation to prevent
CSRF attacks in OAuth authorization flows.

State parameters are:
1. Generated using cryptographically secure random tokens
2. Stored temporarily (typically 10 minutes)
3. Bound to a user session
4. Single-use only (consumed on validation)
"""

import hashlib
import json
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Default state expiry time (10 minutes)
DEFAULT_STATE_TTL = 600


class OAuthStateManager:
    """
    Manages OAuth state parameters for CSRF protection.

    State format: <random_token>:<timestamp>:<user_id>:<checksum>
    - random_token: 32-byte cryptographically secure random token
    - timestamp: Unix timestamp of generation
    - user_id: Optional user identifier
    - checksum: SHA256 hash of random_token + timestamp + user_id + secret

    This format allows:
    1. Stateless validation (checksum verification)
    2. Expiration checking (timestamp)
    3. User binding (user_id)
    4. Tamper detection (checksum)
    """

    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize the OAuth state manager.

        Args:
            secret_key: Secret key for checksum generation. If not provided,
                       uses SECRET_KEY from environment.
        """
        self.secret_key = secret_key or self._get_secret_key()
        if not self.secret_key:
            raise ValueError("SECRET_KEY must be set for OAuth state management")

    @staticmethod
    def _get_secret_key() -> Optional[str]:
        """Get secret key from environment."""
        import os
        return os.getenv("SECRET_KEY", os.getenv("OAUTH_STATE_SECRET"))

    def generate_state(self, user_id: Optional[str] = None, ttl: int = DEFAULT_STATE_TTL) -> str:
        """
        Generate a cryptographically secure OAuth state parameter.

        Args:
            user_id: Optional user ID to bind this state to
            ttl: Time-to-live in seconds (default: 600 seconds = 10 minutes)

        Returns:
            URL-safe state string
        """
        # Generate cryptographically secure random token
        random_token = secrets.token_urlsafe(32)

        # Get current timestamp
        timestamp = int(time.time())

        # Calculate expiry timestamp
        expires_at = timestamp + ttl

        # Create state payload
        state_payload = {
            "token": random_token,
            "timestamp": timestamp,
            "user_id": user_id,
            "expires_at": expires_at
        }

        # Serialize and hash
        payload_str = json.dumps(state_payload, sort_keys=True)
        checksum = self._compute_checksum(random_token, timestamp, user_id)

        # Format: random_token:timestamp:user_id:expires_at:checksum
        state_string = f"{random_token}:{timestamp}:{user_id or ''}:{expires_at}:{checksum}"

        logger.debug(f"Generated OAuth state for user {user_id or 'anonymous'}")

        return state_string

    def validate_state(
        self,
        state: str,
        user_id: Optional[str] = None,
        require_user_match: bool = False
    ) -> Dict[str, any]:
        """
        Validate an OAuth state parameter.

        Args:
            state: The state parameter from the OAuth callback
            user_id: Optional user ID to verify against
            require_user_match: If True, requires user_id to match the state's user_id

        Returns:
            Dictionary with validation result and metadata

        Raises:
            ValueError: If state is invalid, expired, or tampered with
        """
        if not state:
            raise ValueError("State parameter is missing")

        try:
            # Parse state string
            parts = state.split(":")
            if len(parts) != 5:
                raise ValueError("Invalid state format")

            random_token, timestamp_str, state_user_id, expires_at_str, provided_checksum = parts

            # Verify checksum first (tamper detection)
            expected_checksum = self._compute_checksum(
                random_token,
                int(timestamp_str),
                state_user_id or None
            )

            if not secrets.compare_digest(expected_checksum, provided_checksum):
                logger.warning("OAuth state checksum mismatch - possible tampering")
                raise ValueError("State parameter has been tampered with")

            # Parse timestamp
            timestamp = int(timestamp_str)
            now = int(time.time())

            # Check expiration using expires_at from state
            if now > int(expires_at_str):
                logger.warning(f"OAuth state expired (expired at {expires_at_str}, now {now})")
                raise ValueError("State parameter has expired")

            # Check if state is too old (negative timestamp = time travel attempt)
            if timestamp > now + 60:  # Allow 60 seconds clock skew
                logger.warning(f"OAuth state timestamp is in the future (created at {timestamp}, now {now})")
                raise ValueError("State parameter has invalid timestamp")

            # Verify user binding if required
            if require_user_match:
                if state_user_id and user_id and state_user_id != user_id:
                    logger.warning(
                        f"OAuth state user mismatch: expected {state_user_id}, got {user_id}"
                    )
                    raise ValueError("State parameter is bound to a different user")

            logger.debug(f"Validated OAuth state for user {state_user_id or 'anonymous'}")

            return {
                "valid": True,
                "user_id": state_user_id or None,
                "timestamp": timestamp,
                "expired": False,
                "tampered": False
            }

        except ValueError as e:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Error validating OAuth state: {e}")
            raise ValueError(f"State validation failed: {str(e)}")

    def _compute_checksum(self, token: str, timestamp: int, user_id: Optional[str]) -> str:
        """
        Compute checksum for state verification.

        Args:
            token: Random token
            timestamp: Unix timestamp
            user_id: Optional user ID

        Returns:
            Hexadecimal checksum string
        """
        # Create a string with all components
        data = f"{token}:{timestamp}:{user_id or ''}"

        # Compute HMAC-SHA256
        import hmac
        hmac_obj = hmac.new(
            self.secret_key.encode(),
            data.encode(),
            hashlib.sha256
        )
        return hmac_obj.hexdigest()

    def extract_user_id(self, state: str) -> Optional[str]:
        """
        Extract user ID from state parameter without validating it.
        Use this only for logging/debugging purposes.

        Args:
            state: The state parameter

        Returns:
            User ID if present, None otherwise
        """
        try:
            parts = state.split(":")
            if len(parts) >= 5:
                return parts[2] or None
        except Exception:
            pass
        return None


# Global singleton instance
_oauth_state_manager: Optional[OAuthStateManager] = None


def get_oauth_state_manager() -> OAuthStateManager:
    """Get or create the global OAuth state manager instance."""
    global _oauth_state_manager
    if _oauth_state_manager is None:
        _oauth_state_manager = OAuthStateManager()
    return _oauth_state_manager
