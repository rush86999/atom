# -*- coding: utf-8 -*-
"""Coverage wave 82 — core/credential_vault.

Real Fernet cryptography with in-memory SQLite models (TenantSetting,
IntegrationToken). SETTINGS_ENCRYPTION_KEY is injected per test via
monkeypatch; singleton is reset between tests. No network, no LLM spend.

Coverage targets:
- CredentialVault: missing key → CredentialVaultError, invalid key →
  CredentialVaultError, encrypt/decrypt round trip, encrypt/decrypt error
  paths, JSON blob round trip.
- get_vault / reset_vault singleton lifecycle.
- save/load/delete_tenant_integration: upsert (new + update), load missing,
  delete existing/missing, corrupted stored blob on load.
- find_tenant_by_platform_id: IntegrationToken match, IntegrationToken scan
  error (warning + fallthrough), legacy TenantSetting match, corrupt legacy
  row skipped, legacy scan error, no match → None.
- list_tenant_integrations: redaction of secret fields, safe-field passthrough,
  corrupted setting → connected False, absent → connected False.
"""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock, patch

from core.database import Base
from core.models import IntegrationToken, TenantSetting  # noqa: F401

from core.credential_vault import (
    CredentialVault,
    CredentialVaultError,
    delete_tenant_integration,
    find_tenant_by_platform_id,
    get_vault,
    list_tenant_integrations,
    load_tenant_integration,
    reset_vault,
    save_tenant_integration,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def vault_key(monkeypatch):
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("SETTINGS_ENCRYPTION_KEY", key)
    reset_vault()
    yield key
    reset_vault()


class TestCredentialVault:
    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("SETTINGS_ENCRYPTION_KEY", raising=False)
        with pytest.raises(CredentialVaultError, match="SETTINGS_ENCRYPTION_KEY"):
            CredentialVault()

    def test_invalid_key_raises(self, monkeypatch):
        monkeypatch.setenv("SETTINGS_ENCRYPTION_KEY", "not-a-valid-fernet-key")
        with pytest.raises(CredentialVaultError, match="Invalid SETTINGS_ENCRYPTION_KEY"):
            CredentialVault()

    def test_round_trip(self, vault_key):
        vault = CredentialVault()
        blob = {"api_key": "sk-123", "channel": "C1"}
        ciphertext = vault.encrypt(blob)
        assert isinstance(ciphertext, str)
        assert "sk-123" not in ciphertext
        assert vault.decrypt(ciphertext) == blob

    def test_json_types_round_trip(self, vault_key):
        vault = CredentialVault()
        blob = {"int": 5, "bool": True, "none": None, "list": [1, 2], "nested": {"a": 1}}
        assert vault.decrypt(vault.encrypt(blob)) == blob

    def test_encrypt_error(self, vault_key):
        vault = CredentialVault()
        with patch.object(vault, "_fernet") as fernet:
            fernet.encrypt.side_effect = RuntimeError("boom")
            with pytest.raises(CredentialVaultError, match="Encryption failed"):
                vault.encrypt({"a": 1})

    def test_decrypt_error(self, vault_key):
        vault = CredentialVault()
        with pytest.raises(CredentialVaultError, match="Decryption failed"):
            vault.decrypt("garbage-ciphertext")

    def test_decrypt_corrupted_payload(self, vault_key):
        vault = CredentialVault()
        ciphertext = vault.encrypt({"a": 1})
        corrupted = ciphertext[:-4] + "AAAA"
        with pytest.raises(CredentialVaultError):
            vault.decrypt(corrupted)


class TestSingleton:
    def test_get_vault_creates_and_caches(self, vault_key):
        v1 = get_vault()
        v2 = get_vault()
        assert v1 is v2

    def test_reset_vault(self, vault_key):
        v1 = get_vault()
        reset_vault()
        v2 = get_vault()
        assert v1 is not v2


class TestTenantIntegrationCRUD:
    def test_save_new_and_load(self, db, vault_key):
        save_tenant_integration(db, "t1", "slack", {"api_key": "sk_secret_value_123", "channel": "C1"})
        row = db.query(TenantSetting).filter_by(tenant_id="t1", setting_key="messaging_slack").first()
        assert row is not None
        assert "sk_secret_value_123" not in row.setting_value
        assert load_tenant_integration(db, "t1", "slack") == {"api_key": "sk_secret_value_123", "channel": "C1"}

    def test_save_updates_existing(self, db, vault_key):
        save_tenant_integration(db, "t1", "slack", {"api_key": "v1"})
        save_tenant_integration(db, "t1", "slack", {"api_key": "v2"})
        assert db.query(TenantSetting).filter_by(
            tenant_id="t1", setting_key="messaging_slack").count() == 1
        assert load_tenant_integration(db, "t1", "slack") == {"api_key": "v2"}

    def test_load_missing_returns_none(self, db, vault_key):
        assert load_tenant_integration(db, "t1", "slack") is None

    def test_delete_existing(self, db, vault_key):
        save_tenant_integration(db, "t1", "slack", {"api_key": "x"})
        assert delete_tenant_integration(db, "t1", "slack") is True
        assert load_tenant_integration(db, "t1", "slack") is None

    def test_delete_missing(self, db, vault_key):
        assert delete_tenant_integration(db, "t1", "slack") is False

    def test_load_corrupted_blob_raises(self, db, vault_key):
        db.add(TenantSetting(tenant_id="t1", setting_key="messaging_slack",
                             setting_value="not-encrypted"))
        db.commit()
        with pytest.raises(CredentialVaultError):
            load_tenant_integration(db, "t1", "slack")


class TestFindTenantByPlatformId:
    def test_integration_token_match(self, db, vault_key):
        token = IntegrationToken(
            tenant_id="t-9",
            provider="whatsapp",
            access_token="enc-1",
            credential_metadata={"phone_number": "+15551234567"},
        )
        db.add(token)
        db.commit()
        assert find_tenant_by_platform_id(db, "whatsapp", "phone_number", "+15551234567") == "t-9"

    def test_integration_token_scan_error_falls_through(self, db, vault_key):
        db.add(IntegrationToken(
            tenant_id="t-1", provider="slack", access_token="enc-1",
            credential_metadata={"team_id": "T1"},
        ))
        db.commit()

        class BoomQuery:
            def filter(self, *a, **k):
                raise RuntimeError("db down")

        class BoomDB:
            def query(self, model):
                return BoomQuery()

        # IntegrationToken scan raises → warning → falls through to legacy
        assert find_tenant_by_platform_id(BoomDB(), "slack", "team_id", "T1") is None

    def test_legacy_setting_match(self, db, vault_key):
        save_tenant_integration(db, "t-7", "telegram", {"bot_token": "B1", "channel": "X"})
        assert find_tenant_by_platform_id(db, "telegram", "channel", "X") == "t-7"

    def test_legacy_corrupt_row_skipped(self, db, vault_key):
        db.add(TenantSetting(tenant_id="t-bad", setting_key="messaging_slack",
                             setting_value="garbage"))
        save_tenant_integration(db, "t-good", "slack", {"channel": "real"})
        db.commit()
        assert find_tenant_by_platform_id(db, "slack", "channel", "real") == "t-good"

    def test_legacy_scan_error(self, db, vault_key):
        class BoomQuery:
            def filter_by(self, **k):
                raise RuntimeError("db down")

        class BoomDB:
            def query(self, model):
                return BoomQuery()

        assert find_tenant_by_platform_id(BoomDB(), "slack", "channel", "X") is None

    def test_no_match(self, db, vault_key):
        assert find_tenant_by_platform_id(db, "slack", "channel", "X") is None


class TestListTenantIntegrations:
    def test_redaction(self, db, vault_key):
        save_tenant_integration(db, "t1", "slack", {
            "api_key": "secret", "refresh_token": "rt", "token": "tok",
            "password": "pw", "team_name": "ACME", "channel": "C1",
        })
        result = list_tenant_integrations(db, "t1")
        assert result["slack"]["connected"] is True
        assert result["slack"]["api_key"] == "***"
        assert result["slack"]["refresh_token"] == "***"
        assert result["slack"]["token"] == "***"
        assert result["slack"]["password"] == "***"
        assert result["slack"]["team_name"] == "ACME"
        assert result["slack"]["channel"] == "C1"

    def test_absent_platforms(self, db, vault_key):
        result = list_tenant_integrations(db, "t1")
        assert set(result.keys()) == {"whatsapp", "slack", "discord", "telegram", "teams", "sms"}
        assert all(entry["connected"] is False for entry in result.values())

    def test_corrupted_setting(self, db, vault_key):
        db.add(TenantSetting(tenant_id="t1", setting_key="messaging_slack",
                             setting_value="garbage"))
        db.commit()
        result = list_tenant_integrations(db, "t1")
        assert result["slack"] == {"connected": False, "error": "credential_corrupted"}
