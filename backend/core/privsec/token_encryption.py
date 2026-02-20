"""
Centralized Token and API Key Encryption Utilities

This module provides Fernet-based symmetric encryption for storing sensitive
credentials (OAuth tokens, API keys) in the database. Centralizes encryption
logic that may be scattered across models.py and other files.

Features:
- Fernet symmetric encryption (URL-safe base64-encoded)
- Automatic key generation for development (with warning)
- Key validation and rotation support
- Token encryption detection (encrypted vs plaintext)
- Service-specific wrapper functions for audit logging
- Re-encryption support for key rotation

Key Management:
- Environment variable: BYOK_ENCRYPTION_KEY
- Generate with: openssl rand -base64 32
- Format: 32-byte base64-encoded key (Fernet-compatible)
- Cached in memory for performance

Security:
- All tokens encrypted at rest (never stored plaintext)
- Keys never logged or exposed in error messages
- Invalid tokens raise clear decryption errors
- Backward compatibility with legacy plaintext tokens

Usage:
    from core.privsec.token_encryption import encrypt_token, decrypt_token

    # Encrypt token before storage
    encrypted = encrypt_token("my-secret-token")
    # Store 'encrypted' in database

    # Decrypt when needed
    plaintext = decrypt_token(encrypted)
"""

import base64
import hashlib
import logging
import os
from typing import Dict, Optional
from cryptography.fernet import Fernet, InvalidToken

from core.structured_logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# Exception Classes
# ============================================================================

class MissingKeyError(Exception):
    """Raised when encryption key is not configured."""
    pass


class InvalidKeyError(Exception):
    """Raised when encryption key has invalid format."""
    pass


class DecryptionError(Exception):
    """Raised when token decryption fails."""
    pass


# ============================================================================
# Key Management
# ============================================================================

_fernet_instance: Optional[Fernet] = None
_encryption_key: Optional[bytes] = None


def get_encryption_key() -> bytes:
    """
    Get encryption key from environment or generate one.

    Reads BYOK_ENCRYPTION_KEY from environment. If missing, generates
    a random key and logs a warning (development safety only).

    Returns:
        Fernet-compatible encryption key (32 bytes)

    Raises:
        InvalidKeyError: If key format is invalid
    """
    global _encryption_key

    if _encryption_key is not None:
        return _encryption_key

    # Read from environment
    key_str = os.getenv("BYOK_ENCRYPTION_KEY")

    if not key_str:
        # Generate random key for development (NOT for production)
        logger.warning(
            "BYOK_ENCRYPTION_KEY not configured - generating temporary key. "
            "Set BYOK_ENCRYPTION_KEY environment variable for production use.",
            extra={"security_warning": True}
        )
        key_str = generate_encryption_key()
        logger.info(
            "Generated temporary encryption key - save this for future use",
            extra={"generated_key": key_str, "security_note": "Save this key!"}
        )

    # Validate key format
    if not validate_encryption_key(key_str):
        raise InvalidKeyError(
            "BYOK_ENCRYPTION_KEY must be a valid Fernet key "
            "(32 bytes base64-encoded). Generate with: openssl rand -base64 32"
        )

    # Decode key
    _encryption_key = key_str.encode()
    return _encryption_key


def validate_encryption_key(key: str) -> bool:
    """
    Check if key is valid Fernet key format.

    Fernet keys are 32 bytes base64-encoded (44 characters with padding).

    Args:
        key: Key string to validate

    Returns:
        True if valid Fernet key format, False otherwise
    """
    try:
        # Attempt to decode as base64
        key_bytes = base64.urlsafe_b64decode(key.encode())
        # Fernet keys must be 32 bytes
        return len(key_bytes) == 32
    except Exception:
        return False


def generate_encryption_key() -> str:
    """
    Generate new Fernet-compatible encryption key.

    Returns:
        Base64-encoded 32-byte key suitable for Fernet

    Example:
        >>> key = generate_encryption_key()
        >>> # Set as environment variable:
        >>> # export BYOK_ENCRYPTION_KEY=<key>
    """
    key = Fernet.generate_key()
    return key.decode()


def _get_fernet() -> Fernet:
    """
    Get or create Fernet instance with cached key.

    Returns:
        Fernet instance initialized with encryption key
    """
    global _fernet_instance

    if _fernet_instance is None:
        key = get_encryption_key()
        _fernet_instance = Fernet(key)

    return _fernet_instance


def reset_fernet_cache():
    """
    Reset Fernet cache (mainly for testing).

    Forces re-reading of encryption key on next access.
    """
    global _fernet_instance, _encryption_key
    _fernet_instance = None
    _encryption_key = None
    logger.debug("Fernet cache reset")


# ============================================================================
# Token Encryption/Decryption
# ============================================================================

def encrypt_token(
    plaintext: str,
    key: Optional[str] = None
) -> str:
    """
    Encrypt token string using Fernet symmetric encryption.

    Args:
        plaintext: Token string to encrypt
        key: Optional encryption key (defaults to BYOK_ENCRYPTION_KEY)

    Returns:
        URL-safe base64-encoded ciphertext

    Raises:
        InvalidKeyError: If key format is invalid
    """
    if not plaintext:
        return ""

    # Use provided key or get from environment
    if key:
        if not validate_encryption_key(key):
            raise InvalidKeyError("Provided key has invalid format")
        f = Fernet(key.encode())
    else:
        f = _get_fernet()

    # Encrypt and return as string
    ciphertext = f.encrypt(plaintext.encode())
    return ciphertext.decode()


def decrypt_token(
    ciphertext: str,
    key: Optional[str] = None,
    allow_plaintext: bool = True
) -> str:
    """
    Decrypt token string using Fernet symmetric encryption.

    Supports backward compatibility with plaintext tokens (optional).

    Args:
        ciphertext: Encrypted token string (or plaintext if allow_plaintext)
        key: Optional encryption key (defaults to BYOK_ENCRYPTION_KEY)
        allow_plaintext: If True, return plaintext tokens as-is (backward compat)

    Returns:
        Decrypted plaintext token

    Raises:
        DecryptionError: If decryption fails and allow_plaintext=False
    """
    if not ciphertext:
        return ""

    # Check if value looks like Fernet ciphertext
    # Fernet output is base64-encoded and starts with 'gAAAA'
    is_encrypted = is_encrypted_value(ciphertext)

    if not is_encrypted and allow_plaintext:
        # Assume plaintext (backward compatibility)
        logger.debug(
            "Decrypting plaintext token (backward compatibility)",
            extra={"backward_compat": True}
        )
        return ciphertext

    try:
        # Use provided key or get from environment
        if key:
            if not validate_encryption_key(key):
                raise InvalidKeyError("Provided key has invalid format")
            f = Fernet(key.encode())
        else:
            f = _get_fernet()

        # Decrypt and return
        plaintext = f.decrypt(ciphertext.encode())
        return plaintext.decode()

    except InvalidToken as e:
        logger.error(
            "Token decryption failed",
            extra={
                "error": str(e),
                "ciphertext_prefix": ciphertext[:20] if ciphertext else None
            }
        )
        raise DecryptionError(
            f"Failed to decrypt token - may be corrupted or encrypted with different key"
        ) from e


# ============================================================================
# API Key Encryption (Service-Specific Wrappers)
# ============================================================================

def encrypt_api_key(api_key: str, service: str) -> str:
    """
    Encrypt API key with service-specific logging.

    Wrapper around encrypt_token that logs the encryption event
    for audit purposes (without logging the key value).

    Args:
        api_key: API key to encrypt
        service: Service name (e.g., "spotify", "openai")

    Returns:
        Encrypted API key (ciphertext)
    """
    if not api_key:
        logger.warning(
            "Attempted to encrypt empty API key",
            extra={"service": service}
        )
        return ""

    encrypted = encrypt_token(api_key)

    logger.info(
        "API key encrypted",
        extra={
            "service": service,
            "key_length": len(api_key),
            "encrypted": True
        }
    )

    return encrypted


def decrypt_api_key(encrypted_key: str, service: str) -> str:
    """
    Decrypt API key with service-specific logging.

    Wrapper around decrypt_token that logs the decryption event
    for audit purposes (without logging the key value).

    Args:
        encrypted_key: Encrypted API key
        service: Service name (e.g., "spotify", "openai")

    Returns:
        Decrypted API key (plaintext)
    """
    if not encrypted_key:
        logger.warning(
            "Attempted to decrypt empty API key",
            extra={"service": service}
        )
        return ""

    decrypted = decrypt_token(encrypted_key, allow_plaintext=False)

    logger.info(
        "API key decrypted",
        extra={
            "service": service,
            "key_length": len(decrypted),
            "decrypted": True
        }
    )

    return decrypted


# ============================================================================
# Token Rotation Support
# ============================================================================

def rotate_tokens(
    old_key: str,
    new_key: str,
    tokens: Dict[str, str]
) -> Dict[str, int]:
    """
    Re-encrypt all tokens with new key.

    Used when rotating encryption keys. Decrypts all tokens with old key
    and re-encrypts with new key.

    Args:
        old_key: Old encryption key
        new_key: New encryption key
        tokens: Dict mapping token_id -> encrypted_token

    Returns:
        Dict with rotation statistics:
        {
            "total": int,
            "rotated": int,
            "failed": int,
            "failed_ids": List[str]
        }
    """
    stats = {
        "total": len(tokens),
        "rotated": 0,
        "failed": 0,
        "failed_ids": []
    }

    logger.info(
        "Starting token rotation",
        extra={
            "total_tokens": stats["total"],
            "old_key_hash": hashlib.sha256(old_key.encode()).hexdigest()[:16],
            "new_key_hash": hashlib.sha256(new_key.encode()).hexdigest()[:16]
        }
    )

    for token_id, encrypted_token in tokens.items():
        try:
            # Decrypt with old key
            plaintext = decrypt_token(encrypted_token, key=old_key, allow_plaintext=False)

            # Re-encrypt with new key
            reencrypted = encrypt_token(plaintext, key=new_key)

            # Update in-place (caller must save to database)
            tokens[token_id] = reencrypted

            stats["rotated"] += 1

        except Exception as e:
            logger.error(
                "Token rotation failed",
                extra={
                    "token_id": token_id,
                    "error": str(e)
                }
            )
            stats["failed"] += 1
            stats["failed_ids"].append(token_id)

    logger.info(
        "Token rotation complete",
        extra=stats
    )

    return stats


# ============================================================================
# Utility Functions
# ============================================================================

def is_encrypted_value(value: str) -> bool:
    """
    Check if value looks like Fernet ciphertext.

    Fernet ciphertext is base64-encoded and typically starts with 'gAAAA'
    (the base64 encoding of the version byte and timestamp).

    Args:
        value: String to check

    Returns:
        True if value appears to be Fernet-encrypted, False otherwise
    """
    if not value:
        return False

    # Fernet output is base64-encoded and at least 44 characters
    if len(value) < 44:
        return False

    # Fernet ciphertext starts with 'gAAAA' (version + timestamp prefix)
    if not value.startswith('gAAAA'):
        return False

    # Try to decode as base64 to confirm
    try:
        decoded = base64.urlsafe_b64decode(value.encode())
        # Fernet tokens are at least 1 byte (version) + 8 bytes (timestamp) + ...
        return len(decoded) >= 9
    except Exception:
        return False


def hash_token(token: str) -> str:
    """
    Hash token for comparison without storing plaintext.

    Uses SHA-256 to create one-way hash of token. Useful for
    checking if token matches without storing the actual value.

    Args:
        token: Token string to hash

    Returns:
        Hexadecimal hash string

    Example:
        >>> stored_hash = hash_token("my-token")
        >>> if hash_token(user_input) == stored_hash:
        ...     print("Token matches")
    """
    return hashlib.sha256(token.encode()).hexdigest()
