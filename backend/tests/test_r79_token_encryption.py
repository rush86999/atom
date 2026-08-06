"""Round 79 — token_encryption edge cases, key persistence, and fail-closed tests.

Regression coverage for the P0 credential-encryption module:
- explicit-key roundtrip + wrong-key failure
- is_encrypted_value edge cases
- persisted key file mode 0600
- production honors a persisted key file (env unset) instead of failing
"""
import os
import stat

import pytest

from core.privsec.token_encryption import (
    DecryptionError,
    InvalidKeyError,
    MissingKeyError,
    decrypt_token,
    encrypt_token,
    is_encrypted_value,
    reset_fernet_cache,
)

KEY_A = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
KEY_B = "tBLEgwN8O-GFdX3zgFiaSfso-DCl_vMGFvyhhreTI0s="


@pytest.fixture(autouse=True)
def _isolated_encryption(monkeypatch, tmp_path):
    """Reset the Fernet cache, pin a valid env key, and point the persisted-key
    file at a temp path so tests never touch ./data/byok_encryption_key."""
    reset_fernet_cache()
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", KEY_A)
    monkeypatch.setattr(
        "core.privsec.token_encryption.BYOK_ENC_KEY_FILE",
        str(tmp_path / "byok_encryption_key"),
    )
    yield
    reset_fernet_cache()


class TestExplicitKeyRoundtrip:
    def test_roundtrip_with_explicit_key(self):
        ct = encrypt_token("token-abc", key=KEY_A)
        assert decrypt_token(ct, key=KEY_A) == "token-abc"

    def test_decrypt_with_wrong_key_raises(self):
        ct = encrypt_token("topsecret", key=KEY_A)
        with pytest.raises(DecryptionError):
            decrypt_token(ct, key=KEY_B)

    def test_default_key_and_explicit_key_cross_fail(self):
        """Ciphertext minted with the env key must NOT decrypt under a
        different explicit key (and vice versa)."""
        ct = encrypt_token("secret-1")  # env KEY_A
        with pytest.raises(DecryptionError):
            decrypt_token(ct, key=KEY_B)

    def test_encrypt_with_invalid_key_format_raises(self):
        with pytest.raises(InvalidKeyError):
            encrypt_token("x", key="not-a-fernet-key")

    def test_decrypt_with_invalid_key_format_raises(self):
        with pytest.raises(InvalidKeyError):
            decrypt_token(encrypt_token("x", key=KEY_A), key="garbage")


class TestIsEncryptedValue:
    def test_empty_is_false(self):
        assert is_encrypted_value("") is False

    def test_short_value_is_false(self):
        assert is_encrypted_value("gAAAA") is False
        assert is_encrypted_value("short") is False

    def test_plaintext_not_starting_with_gAAAA_is_false(self):
        long_plain = "x" * 60
        assert is_encrypted_value(long_plain) is False

    def test_gAAAA_prefix_with_invalid_base64_is_false(self):
        assert is_encrypted_value("gAAAA" + "!" * 50) is False

    def test_real_ciphertext_is_true(self):
        ct = encrypt_token("anything")
        assert is_encrypted_value(ct) is True

    def test_round_trip_through_detection(self):
        ct = encrypt_token("detect-me")
        assert is_encrypted_value(ct) is True
        assert decrypt_token(ct) == "detect-me"


class TestKeyPersistence:
    def test_persisted_key_file_has_0600_permissions(self, monkeypatch, tmp_path):
        """Development key generation must persist the key with mode 0600."""
        monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "development")
        key_file = tmp_path / "byok_encryption_key"
        monkeypatch.setattr(
            "core.privsec.token_encryption.BYOK_ENC_KEY_FILE", str(key_file)
        )
        reset_fernet_cache()
        encrypt_token("secret")
        assert key_file.exists()
        assert stat.S_IMODE(os.stat(key_file).st_mode) == 0o600

    def test_production_uses_persisted_key_when_env_missing(self, monkeypatch, tmp_path):
        """Fail-closed is about not MINTING a throwaway key — a persisted key
        file must still be honored in production."""
        monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "production")
        key_file = tmp_path / "byok_encryption_key"
        key_file.write_text(KEY_A)
        monkeypatch.setattr(
            "core.privsec.token_encryption.BYOK_ENC_KEY_FILE", str(key_file)
        )
        reset_fernet_cache()
        ct = encrypt_token("secret")
        assert decrypt_token(ct) == "secret"

    def test_production_fails_closed_without_any_key(self, monkeypatch, tmp_path):
        monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "production")
        key_file = tmp_path / "missing_key_file"
        monkeypatch.setattr(
            "core.privsec.token_encryption.BYOK_ENC_KEY_FILE", str(key_file)
        )
        reset_fernet_cache()
        with pytest.raises(MissingKeyError):
            encrypt_token("secret")

    def test_ciphertext_survives_cache_reset_via_persisted_key(self, monkeypatch, tmp_path):
        """After reset_fernet_cache (process restart), the persisted key file
        keeps ciphertext decryptable even without the env var."""
        monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "development")
        key_file = tmp_path / "byok_encryption_key"
        monkeypatch.setattr(
            "core.privsec.token_encryption.BYOK_ENC_KEY_FILE", str(key_file)
        )
        reset_fernet_cache()
        ct = encrypt_token("durable")
        reset_fernet_cache()  # simulate restart: env still unset
        assert decrypt_token(ct) == "durable"
