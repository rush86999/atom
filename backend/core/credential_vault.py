from __future__ import annotations
"""
CredentialVault: Encrypt/decrypt tenant integration credentials at rest
using Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).

Generate a key with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Then set SETTINGS_ENCRYPTION_KEY in your environment / Fly.io secrets.
"""

import json
import logging
import os
from typing import Any, Union

logger = logging.getLogger(__name__)


class CredentialVaultError(Exception):
    pass


class CredentialVault:
    """
    Wraps cryptography.fernet.Fernet for JSON credential blobs.
    Requires SETTINGS_ENCRYPTION_KEY env var (URL-safe base64 Fernet key).
    """

    def __init__(self):
        key = os.getenv("SETTINGS_ENCRYPTION_KEY")
        if not key:
            raise CredentialVaultError(
                "SETTINGS_ENCRYPTION_KEY environment variable is not set. "
                'Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        try:
            from cryptography.fernet import Fernet

            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            # Enhanced diagnostics for debugging malformed keys (e.g. padding issues)
            key_preview = str(key)[:10] + "..." if key else "None"
            key_len = len(str(key)) if key else 0
            err_msg = f"Invalid SETTINGS_ENCRYPTION_KEY (len={key_len}, preview='{key_preview}'): {e}"
            logger.error(f"CredentialVault: {err_msg}")
            raise CredentialVaultError(err_msg)


    def encrypt(self, data: dict[str, Any]) -> str:
        """Encrypt a dictionary to a URL-safe base64 ciphertext string."""
        try:
            plaintext = json.dumps(data).encode("utf-8")
            return self._fernet.encrypt(plaintext).decode("utf-8")
        except Exception as e:
            raise CredentialVaultError(f"Encryption failed: {e}")

    def decrypt(self, ciphertext: str) -> dict[str, Any]:
        """Decrypt a ciphertext string back to a dictionary."""
        try:
            plaintext = self._fernet.decrypt(ciphertext.encode("utf-8"))
            return json.loads(plaintext.decode("utf-8"))
        except Exception as e:
            raise CredentialVaultError(f"Decryption failed (key mismatch or corrupted data): {e}")


# ---------------------------------------------------------------------------
# Module-level singleton — lazy init so startup doesn't fail if key is absent
# ---------------------------------------------------------------------------

_vault_instance: Union[CredentialVault, None] = None


def get_vault() -> CredentialVault:
    """Returns the singleton CredentialVault, initializing it on first call."""
    global _vault_instance
    if _vault_instance is None:
        _vault_instance = CredentialVault()
    return _vault_instance


def reset_vault() -> None:
    """Clears the singleton vault instance. Useful for tests to reload configuration."""
    global _vault_instance
    _vault_instance = None


# ---------------------------------------------------------------------------
# High-level helpers (used by OAuth routes & CommunicationService)
# ---------------------------------------------------------------------------


def save_tenant_integration(db, tenant_id: str, platform: str, credentials: dict[str, Any]) -> None:
    """
    Encrypts and upserts a platform integration config into TenantSetting.
    `platform` should be the bare name, e.g. 'whatsapp', 'slack', 'discord'.
    """
    from core.models import TenantSetting

    vault = get_vault()
    encrypted = vault.encrypt(credentials)
    key = f"messaging_{platform}"

    existing = db.query(TenantSetting).filter_by(tenant_id=tenant_id, setting_key=key).first()
    if existing:
        existing.setting_value = encrypted
    else:
        db.add(TenantSetting(tenant_id=tenant_id, setting_key=key, setting_value=encrypted))
    db.commit()
    logger.info(f"Saved encrypted {platform} config for tenant {tenant_id}")


def load_tenant_integration(db, tenant_id: str, platform: str) -> Union[dict[str, Any], None]:
    """
    Loads and decrypts a platform integration config from TenantSetting.
    Returns None if not configured.
    """
    from core.models import TenantSetting

    key = f"messaging_{platform}"
    setting = db.query(TenantSetting).filter_by(tenant_id=tenant_id, setting_key=key).first()
    if not setting:
        return None
    vault = get_vault()
    return vault.decrypt(setting.setting_value)


def delete_tenant_integration(db, tenant_id: str, platform: str) -> bool:
    """Removes a platform integration from TenantSetting. Returns True if a row was deleted."""
    from core.models import TenantSetting

    key = f"messaging_{platform}"
    deleted = db.query(TenantSetting).filter_by(tenant_id=tenant_id, setting_key=key).delete()
    db.commit()
    return deleted > 0


def find_tenant_by_platform_id(db, platform: str, field: str, value: str) -> Union[str, Any, None]:
    """
    Search both IntegrationToken (new) and TenantSetting (legacy) for a platform identifier.
    Returns the tenant_id (UUID or str) associated with the identifier.
    """
    from core.models import TenantSetting, IntegrationToken

    # 1. Check IntegrationToken (Modern Registry) - High Priority
    # For IntegrationToken, 'platform' is 'provider'
    # and we look inside the 'credential_metadata' JSONB column.
    try:
        tokens = db.query(IntegrationToken).filter(IntegrationToken.provider == platform).all()
        for t in tokens:
            meta = t.credential_metadata or {}
            if meta.get(field) == value:
                logger.info(f"Resolved tenant {t.tenant_id} from IntegrationToken for {platform}:{field}={value}")
                return t.tenant_id
    except Exception as e:
        logger.warning(f"Error scanning IntegrationToken for webhook resolution: {e}")

    # 2. Check TenantSetting (Legacy Fallback)
    key = f"messaging_{platform}"
    vault = get_vault()

    try:
        settings = db.query(TenantSetting).filter_by(setting_key=key).all()
        for setting in settings:
            try:
                data = vault.decrypt(setting.setting_value)
                if data.get(field) == value:
                    logger.info(f"Resolved tenant {setting.tenant_id} from TenantSetting for {platform}:{field}={value}")
                    return setting.tenant_id
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Error scanning TenantSetting for webhook resolution: {e}")

    return None


def list_tenant_integrations(db, tenant_id: str) -> dict[str, dict[str, Any]]:
    """
    Returns all connected platforms for a tenant, with secrets redacted.
    Safe to expose to the frontend.
    """
    from core.models import TenantSetting

    REDACTED_FIELDS = {
        "access_token",
        "bot_token",
        "app_secret",
        "client_secret",
        "auth_token",
        "app_password",
        "secret_token",
    }
    platforms = ["whatsapp", "slack", "discord", "telegram", "teams", "sms"]
    vault = get_vault()
    result = {}

    for platform in platforms:
        key = f"messaging_{platform}"
        setting = db.query(TenantSetting).filter_by(tenant_id=tenant_id, setting_key=key).first()
        if setting:
            try:
                data = vault.decrypt(setting.setting_value)
                # Redact secrets before returning
                safe_data = {k: ("***" if k in REDACTED_FIELDS else v) for k, v in data.items()}
                result[platform] = {"connected": True, **safe_data}
            except Exception:
                result[platform] = {"connected": False, "error": "credential_corrupted"}
        else:
            result[platform] = {"connected": False}

    return result
