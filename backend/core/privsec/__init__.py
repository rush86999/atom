"""
Privacy and Security Utilities for Local-First Operation

This package provides local-first privacy architecture with encrypted token
storage, local-only mode enforcement, and comprehensive audit logging.

Modules:
- local_only_guard: Local-only mode enforcement for external service blocking
- token_encryption: Centralized Fernet-based token encryption utilities
- audit_logger: Structured audit logging for device/media/smarthome actions

Usage:
    from core.privsec import (
        LocalOnlyGuard,
        require_local_allowed,
        encrypt_token,
        decrypt_token,
        AuditLogger
    )

    # Check local-only mode
    guard = LocalOnlyGuard()
    if guard.is_local_only_enabled():
        print("Local-only mode active")

    # Encrypt token
    encrypted = encrypt_token("my-secret-token")

    # Log action
    audit = AuditLogger()
    audit.log_media_action(
        user_id="user_123",
        agent_id="agent_456",
        action="pause_playback",
        service="spotify",
        details={"device_id": "device_abc"},
        result="success"
    )

Key Features:
- Local-only mode: Block all external API calls (Spotify, Notion, etc.)
- Encrypted storage: All tokens encrypted with Fernet at rest
- Audit logging: Complete audit trail for all sensitive operations
- Zero cloud dependencies: Everything runs locally

Environment Variables:
- ATOM_LOCAL_ONLY: Enable local-only mode (true/false)
- BYOK_ENCRYPTION_KEY: Fernet encryption key (generate with: openssl rand -base64 32)
- AUDIT_LOG_PATH: Audit log file path (default: logs/audit.log)
- AUDIT_LOG_RETENTION_DAYS: Log retention period (default: 90)
"""

from core.privsec.local_only_guard import (
    LocalOnlyGuard,
    LocalOnlyModeError,
    require_local_allowed,
    get_local_only_guard,
)
from core.privsec.token_encryption import (
    MissingKeyError,
    InvalidKeyError,
    DecryptionError,
    encrypt_token,
    decrypt_token,
    encrypt_api_key,
    decrypt_api_key,
    rotate_tokens,
    is_encrypted_value,
    hash_token,
    get_encryption_key,
    generate_encryption_key,
    validate_encryption_key,
)
from core.privsec.audit_logger import (
    AuditLogger,
    get_audit_logger,
    log_media_action_async,
    log_smarthome_action_async,
)

__all__ = [
    # Local-Only Guard
    "LocalOnlyGuard",
    "LocalOnlyModeError",
    "require_local_allowed",
    "get_local_only_guard",
    # Token Encryption
    "MissingKeyError",
    "InvalidKeyError",
    "DecryptionError",
    "encrypt_token",
    "decrypt_token",
    "encrypt_api_key",
    "decrypt_api_key",
    "rotate_tokens",
    "is_encrypted_value",
    "hash_token",
    "get_encryption_key",
    "generate_encryption_key",
    "validate_encryption_key",
    # Audit Logger
    "AuditLogger",
    "get_audit_logger",
    "log_media_action_async",
    "log_smarthome_action_async",
]

# Version info
__version__ = "1.0.0"
__author__ = "Atom Team"
__description__ = "Local-first privacy and security utilities for Personal Edition"
