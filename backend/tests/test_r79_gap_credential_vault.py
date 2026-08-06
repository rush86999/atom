# -*- coding: utf-8 -*-
"""
Round 79 — gap coverage: core/credential_vault.py (Fernet credential vault +
TenantSetting helpers; zero test references before this file).
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

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

KEY = "-qnenNkn_XYxTlA_3D9BW8zL9mABYE9VKkAu8sZAigk="


@pytest.fixture(autouse=True)
def _reset():
    reset_vault()
    yield
    reset_vault()


@pytest.fixture()
def _key(monkeypatch):
    monkeypatch.setenv("SETTINGS_ENCRYPTION_KEY", KEY)
    return KEY


class TestVault:
    def test_missing_key_raises(self):
        with patch.dict("os.environ", {}, clear=False):
            with patch("os.getenv", return_value=None):
                with pytest.raises(CredentialVaultError):
                    CredentialVault()

    def test_invalid_key_raises_with_diagnostics(self, _key, monkeypatch):
        monkeypatch.setenv("SETTINGS_ENCRYPTION_KEY", "not-a-fernet-key!")
        with pytest.raises(CredentialVaultError):
            CredentialVault()

    def test_encrypt_decrypt_roundtrip(self, _key):
        vault = CredentialVault()
        payload = {"access_token": "secret-abc", "scope": "read"}
        cipher = vault.encrypt(payload)
        assert cipher != "secret-abc"
        assert "secret-abc" not in cipher
        assert vault.decrypt(cipher) == payload

    def test_encrypt_non_json_serializable_raises(self, _key):
        vault = CredentialVault()
        with pytest.raises(CredentialVaultError):
            vault.encrypt({"bad": object()})

    def test_decrypt_wrong_key_fails(self, _key):
        vault = CredentialVault()
        cipher = vault.encrypt({"a": 1})
        reset_vault()
        with patch.dict("os.environ", {}, clear=False):
            with patch("os.getenv", return_value="yTwhipmMzVdIq5-bpmX6LAlL1j2aTqYIO6lcDytDGqQ="):
                other = CredentialVault()
        with pytest.raises(CredentialVaultError):
            other.decrypt(cipher)

    def test_get_vault_singleton(self, _key):
        assert get_vault() is get_vault()
        assert isinstance(get_vault(), CredentialVault)

    def test_reset_vault_reloads(self, _key):
        v1 = get_vault()
        reset_vault()
        v2 = get_vault()
        assert v1 is not v2


class TestTenantHelpers:
    @pytest.fixture()
    def db(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from core.database import Base
        from core.models import TenantSetting

        engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=engine, tables=[TenantSetting.__table__])
        session = sessionmaker(bind=engine)()
        yield session
        session.close()

    def test_save_and_load_roundtrip(self, db, _key):
        creds = {"access_token": "tok-1", "phone_number": "+1555000", "platform": "whatsapp"}
        save_tenant_integration(db, "t1", "whatsapp", creds)
        loaded = load_tenant_integration(db, "t1", "whatsapp")
        assert loaded == creds

    def test_load_missing_returns_none(self, db, _key):
        assert load_tenant_integration(db, "t1", "slack") is None

    def test_save_upserts_instead_of_duplicating(self, db, _key):
        save_tenant_integration(db, "t1", "slack", {"token": "v1"})
        save_tenant_integration(db, "t1", "slack", {"token": "v2"})
        assert load_tenant_integration(db, "t1", "slack") == {"token": "v2"}

    def test_delete_returns_true_then_false(self, db, _key):
        save_tenant_integration(db, "t1", "discord", {"token": "x"})
        assert delete_tenant_integration(db, "t1", "discord") is True
        assert delete_tenant_integration(db, "t1", "discord") is False

    def test_find_tenant_by_platform_id_via_legacy_setting(self, db, _key):
        save_tenant_integration(db, "t42", "slack", {"bot_user_id": "B123"})
        assert find_tenant_by_platform_id(db, "slack", "bot_user_id", "B123") == "t42"

    def test_find_tenant_no_match_returns_none(self, db, _key):
        save_tenant_integration(db, "t42", "slack", {"bot_user_id": "B123"})
        assert find_tenant_by_platform_id(db, "slack", "bot_user_id", "NOPE") is None

    def test_list_integrations_redacts_secrets(self, db, _key):
        save_tenant_integration(
            db, "t1", "slack", {"api_key": "sk-live-123", "phone_number": "+1", "bot_user_id": "B1"}
        )
        result = list_tenant_integrations(db, "t1")
        assert result["slack"]["connected"] is True
        assert result["slack"]["api_key"] == "***"
        assert result["slack"]["phone_number"] == "+1"
        assert result["slack"]["bot_user_id"] == "B1"

    def test_list_integrations_unconfigured_platforms(self, db, _key):
        result = list_tenant_integrations(db, "t1")
        for platform in ("whatsapp", "slack", "discord", "telegram", "teams", "sms"):
            assert platform in result
            assert result[platform]["connected"] is False

    def test_corrupted_credential_reported_not_crashing(self, db, _key):
        save_tenant_integration(db, "t1", "telegram", {"token": "x"})
        with patch.object(CredentialVault, "decrypt", side_effect=CredentialVaultError("bad")):
            result = list_tenant_integrations(db, "t1")
        assert result["telegram"] == {"connected": False, "error": "credential_corrupted"}
