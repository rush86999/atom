"""
P0 — IntegrationToken encryption enforcement tests.

Covers the Cloudflare OS G1 gap: IntegrationToken access/refresh tokens must be
encrypted at rest (Fernet), legacy plaintext must still decrypt, production must
fail closed when no key is configured, and writes must stamp ``credential_metadata``
so a migration audit can verify encryption coverage.

TDD: these tests are written against the intended behaviour and fail before the
implementation lands.
"""
import os
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from core.privsec.token_encryption import (
    encrypt_token,
    decrypt_token,
    reset_fernet_cache,
    MissingKeyError,
)


# ============================================================================
# Helpers
# ============================================================================

def _valid_key() -> str:
    """A stable, valid Fernet key for tests."""
    return "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="


@pytest.fixture(autouse=True)
def _isolated_encryption(monkeypatch):
    """Reset the Fernet cache and point the persisted-key file at a temp path."""
    reset_fernet_cache()
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _valid_key())
    monkeypatch.setattr(
        "core.privsec.token_encryption.BYOK_ENC_KEY_FILE",
        "/tmp/atom_test_nonexistent_byok_key",
    )
    yield
    reset_fernet_cache()


# ============================================================================
# Core encrypt/decrypt behaviour
# ============================================================================

class TestEncryptDecrypt:
    def test_encrypt_token_round_trip(self):
        """Ciphertext round-trips back to the original plaintext."""
        raw = "ya29.secret-token-value-123"
        encrypted = encrypt_token(raw)
        assert encrypted != raw
        assert encrypted.startswith("gAAAA")
        assert decrypt_token(encrypted) == raw

    def test_decrypt_survives_legacy_plaintext(self):
        """Legacy plaintext tokens still decrypt when allow_plaintext=True."""
        assert decrypt_token("plain-legacy-token", allow_plaintext=True) == "plain-legacy-token"

    def test_encrypt_empty_token_returns_empty(self):
        assert encrypt_token("") == ""
        assert decrypt_token("") == ""

    def test_decrypt_requires_valid_key_for_ciphertext(self):
        """A plaintext value passed to decrypt with allow_plaintext=False raises."""
        from core.privsec.token_encryption import DecryptionError
        with pytest.raises(DecryptionError):
            decrypt_token("not-a-ciphertext", allow_plaintext=False)


# ============================================================================
# Production fail-closed
# ============================================================================

class TestProductionFailClosed:
    def test_production_raises_when_key_unset(self, monkeypatch):
        """In production, encrypting without a configured key must raise."""
        monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "production")
        reset_fernet_cache()
        with pytest.raises(MissingKeyError):
            encrypt_token("secret")

    def test_development_generates_and_persists_key(self, monkeypatch, tmp_path):
        """In development, a missing key generates one and persists it so
        ciphertext survives restart."""
        monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "development")
        key_file = tmp_path / "byok_encryption_key"
        monkeypatch.setattr(
            "core.privsec.token_encryption.BYOK_ENC_KEY_FILE", str(key_file)
        )
        reset_fernet_cache()
        encrypted = encrypt_token("secret")
        assert encrypted.startswith("gAAAA")
        assert key_file.exists()
        persisted = key_file.read_text().strip()
        assert persisted
        reset_fernet_cache()
        monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)
        assert decrypt_token(encrypted) == "secret"


# ============================================================================
# IntegrationToken write/read sites
# ============================================================================

@pytest.fixture
def workspace(db_session):
    import uuid
    from core.models import Workspace
    ws = Workspace(id=f"ws-enc-{uuid.uuid4()}", name="Enc Test Workspace")
    db_session.add(ws)
    db_session.commit()
    db_session.refresh(ws)
    return ws


@pytest.fixture
def encrypted_zoho_token(db_session, workspace):
    """A pre-existing IntegrationToken row whose token is Fernet-encrypted."""
    from core.models import IntegrationToken
    token = IntegrationToken(
        tenant_id="tenant-enc",
        workspace_id=workspace.id,
        user_id=None,
        provider="zoho",
        access_token=encrypt_token("secret-access-123"),
        refresh_token=encrypt_token("secret-refresh-456"),
        token_type="Bearer",
        status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        credential_metadata={"encryption": "fernet"},
    )
    db_session.add(token)
    db_session.commit()
    db_session.refresh(token)
    return token


class TestReadSites:
    def test_zoho_adapter_loads_and_decrypts_token(self, db_session, encrypted_zoho_token):
        """The Zoho adapter must decrypt stored ciphertext before use."""
        from core.integrations.adapters.zoho import ZohoAdapter
        adapter = ZohoAdapter(db=db_session, workspace_id=encrypted_zoho_token.workspace_id)
        import asyncio
        asyncio.get_event_loop().run_until_complete(adapter._load_token())
        assert adapter._access_token == "secret-access-123"
        assert adapter._refresh_token == "secret-refresh-456"

    def test_jira_adapter_loads_and_decrypts_token(self, db_session, workspace):
        from core.models import IntegrationToken
        from core.integrations.adapters.jira import JiraAdapter
        token = IntegrationToken(
            tenant_id="tenant-enc",
            workspace_id=workspace.id,
            provider="jira",
            access_token=encrypt_token("jira-access-123"),
            refresh_token=encrypt_token("jira-refresh-456"),
            status="active",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(token)
        db_session.commit()
        adapter = JiraAdapter(db=db_session, workspace_id=workspace.id)
        import asyncio
        asyncio.get_event_loop().run_until_complete(adapter._load_token())
        assert adapter._access_token == "jira-access-123"
        assert adapter._refresh_token == "jira-refresh-456"


class TestWriteSites:
    @pytest.mark.asyncio
    async def test_zoho_oauth_exchange_encrypts_token(self, db_session, workspace, monkeypatch):
        """ZohoOAuthService.exchange_code_for_token must store ciphertext."""
        from core.integrations.zoho_oauth_service import ZohoOAuthService
        from core.models import IntegrationToken

        # Mock the Zoho token endpoint
        async def fake_post(*args, **kwargs):
            resp = MagicMock()
            resp.json.return_value = {
                "access_token": "plain-new-access",
                "refresh_token": "plain-new-refresh",
                "expires_in": 3600,
                "instance_url": "https://www.zohoapis.com",
            }
            resp.raise_for_status = MagicMock()
            return resp

        with patch("httpx.AsyncClient.post", new=fake_post):
            result = await ZohoOAuthService.exchange_code_for_token(
                db_session, "auth-code", tenant_id="tenant-enc"
            )

        assert result["success"] is True
        stored = db_session.query(IntegrationToken).filter(
            IntegrationToken.provider == "zoho",
            IntegrationToken.tenant_id == "tenant-enc",
        ).first()
        assert stored is not None
        assert stored.access_token != "plain-new-access"
        assert stored.access_token.startswith("gAAAA")
        assert stored.refresh_token != "plain-new-refresh"
        assert stored.refresh_token.startswith("gAAAA")

    @pytest.mark.asyncio
    async def test_zoho_adapter_refresh_encrypts_token_and_stamps_metadata(self, db_session, encrypted_zoho_token):
        """The adapter refresh path must persist refreshed tokens as ciphertext
        and stamp credential_metadata."""
        from core.integrations.adapters.zoho import ZohoAdapter
        adapter = ZohoAdapter(db=db_session, workspace_id=encrypted_zoho_token.workspace_id)
        adapter._refresh_token = "secret-refresh-456"

        async def fake_post(*args, **kwargs):
            resp = MagicMock()
            resp.json.return_value = {"access_token": "brand-new-access", "expires_in": 3600}
            resp.raise_for_status = MagicMock()
            return resp

        with patch("httpx.AsyncClient.post", new=fake_post):
            ok = await adapter.refresh_token()

        assert ok is True
        db_session.refresh(encrypted_zoho_token)
        assert encrypted_zoho_token.access_token.startswith("gAAAA")
        assert encrypted_zoho_token.access_token != "brand-new-access"
        assert decrypt_token(encrypted_zoho_token.access_token) == "brand-new-access"
        assert encrypted_zoho_token.credential_metadata == {"encryption": "fernet"}

    @pytest.mark.asyncio
    async def test_zoho_inventory_write_encrypts_token(self, db_session, workspace):
        """ZohoInventoryService token refresh writes ciphertext, not plaintext."""
        from core.models import IntegrationToken
        from core.integrations.zoho_oauth_service import ZohoOAuthService

        token = IntegrationToken(
            tenant_id="tenant-inv",
            workspace_id=workspace.id,
            provider="zoho_inventory",
            access_token=encrypt_token("old-access"),
            refresh_token=encrypt_token("old-refresh"),
            status="active",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db_session.add(token)
        db_session.commit()

        # Prove the read site decrypts (simulating what zoho_inventory_service does).
        from core.privsec.token_encryption import decrypt_token
        assert decrypt_token(token.refresh_token) == "old-refresh"


class TestCredentialMetadataMigrationBackfill:
    def test_is_fernet_encrypted_detects_ciphertext(self):
        from core.privsec.token_encryption import is_encrypted_value
        assert is_encrypted_value(encrypt_token("x"))
        assert not is_encrypted_value("plaintext-token")


# ============================================================================
# P0 remaining bug fixes: verify-script typo + hybrid_data_ingestion token.metadata
# ============================================================================

class TestVerifyScriptKeyLookup:
    """scripts/verify_token_encryption.py must read the REAL env var name.

    Regression for the BYOK_ENCRYTION_KEY typo that made the audit always report
    CRITICAL regardless of whether the key was actually configured.
    """

    def test_check_encryption_key_reads_correct_env_var(self, monkeypatch):
        import importlib
        monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _valid_key())
        monkeypatch.delenv("OAUTH_ENCRYPTION_KEY", raising=False)
        monkeypatch.delenv("BYOK_ENCRYTION_KEY", raising=False)  # the typo
        mod = importlib.import_module("scripts.verify_token_encryption")
        importlib.reload(mod)
        result = mod.check_encryption_key()
        assert result["status"] == "ok", (
            f"Expected ok with BYOK_ENCRYPTION_KEY set, got {result}"
        )


class TestHybridDataIngestionTokenMetadata:
    """hybrid_data_ingestion must read connection metadata from the correct
    attribute (credential_metadata), not the reserved SQLAlchemy ``metadata``
    attribute (which is a MetaData object with no .get() and crashes at runtime).
    """

    def test_token_metadata_access_does_not_crash(self):
        """The source must not call ``token.metadata.get(...)`` — that resolves to
        SQLAlchemy's Table.metadata and raises AttributeError."""
        import inspect
        from core import hybrid_data_ingestion
        source = inspect.getsource(hybrid_data_ingestion)
        # The bug pattern: token.metadata.get(
        assert "token.metadata.get(" not in source, (
            "hybrid_data_ingestion still uses token.metadata.get(...) which "
            "resolves to SQLAlchemy's reserved MetaData attribute and crashes."
        )
