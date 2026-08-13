"""
Coverage wave 64f — core/llm_oauth_handler + core/llm_oauth_config (TDD).

Locks in the OAuth 2.0 contract for LLM providers:
- Authorization URL generation (state/CSRF, PKCE flag, redirect_uri fallback)
- Code-for-token exchange (httpx mocked — NO real network)
- Credential storage (encrypted at rest, credential_type-scoped deactivation)
- Token refresh (rotation, error mapping), validation, revoke, list
- Encryption: Fernet round-trip, dev plaintext fallback, production refusal
- Config helpers: redirect URI builder, env lookups, provider listing

Also covers core.llm_oauth_config standalone (build_redirect_uri both
branches, unknown-provider returns, display-name fallback).
"""

import base64
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.llm_oauth_config as oauth_config
from core.llm_oauth_handler import LLMOAuthHandler
from core.models import LLMOAuthCredential

VALID_KEY = b"MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _db_ctx(db):
    @contextmanager
    def fake_ctx():
        yield db

    return fake_ctx()


def _mock_db(cred=None, creds_list=None, all_creds=None):
    db = MagicMock()
    query = MagicMock()
    filtered = MagicMock()
    query.filter.return_value = filtered
    filtered.all.return_value = creds_list if creds_list is not None else []
    filtered.first.return_value = cred
    db.query.return_value = query
    db.query.return_value.all.return_value = all_creds if all_creds is not None else ([cred] if cred else [])
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    return db


def _configure_provider(provider_id, monkeypatch):
    cfgs = {
        "google": ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"),
        "openai": ("OPENAI_OAUTH_CLIENT_ID", "OPENAI_OAUTH_CLIENT_SECRET"),
        "anthropic": ("ANTHROPIC_OAUTH_CLIENT_ID", "ANTHROPIC_OAUTH_CLIENT_SECRET"),
        "huggingface": ("HUGGINGFACE_OAUTH_CLIENT_ID", "HUGGINGFACE_OAUTH_CLIENT_SECRET"),
    }
    cid_env, sec_env = cfgs[provider_id]
    monkeypatch.setenv(cid_env, "test-client-id")
    monkeypatch.setenv(sec_env, "test-client-secret")


def _make_credential(**overrides):
    base = dict(
        id="cred-1",
        user_id="user-1",
        tenant_id="tenant-1",
        provider_id="google",
        access_token="enc-access",
        refresh_token="enc-refresh",
        token_type="Bearer",
        credential_type="oauth",
        scope="read",
        expires_at=None,
        refresh_expires_at=None,
        account_email="u@example.com",
        account_name="User",
        is_active=True,
        last_validated_at=None,
        last_used_at=None,
        usage_count=0,
        revoked_at=None,
    )
    base.update(overrides)
    cred = MagicMock(spec=LLMOAuthCredential)
    for k, v in base.items():
        setattr(cred, k, v)
    return cred


def _real_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from core.models_registration import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)


def _real_cred(**overrides):
    base = dict(
        id="cred-1",
        user_id="user-1",
        tenant_id="tenant-1",
        provider_id="google",
        access_token="enc-access",
        refresh_token="enc-refresh",
        token_type="Bearer",
        credential_type="oauth",
        scope="read",
        is_active=True,
        usage_count=0,
    )
    base.update(overrides)
    return LLMOAuthCredential(**base)


def _http_client_mock(response=None, post_side_effect=None):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=response, side_effect=post_side_effect)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def _json_response(payload):
    fake_response = MagicMock()
    fake_response.json.return_value = payload
    fake_response.raise_for_status = MagicMock()
    return fake_response


# ---------------------------------------------------------------------------
# core.llm_oauth_config — standalone
# ---------------------------------------------------------------------------

class TestOAuthConfig:
    def test_build_redirect_uri_substitutes_provider(self, monkeypatch):
        monkeypatch.setattr(
            oauth_config, "DEFAULT_OAUTH_REDIRECT_URI",
            "http://localhost:8000/api/v1/llm-oauth/{provider}/callback",
        )
        assert oauth_config.build_redirect_uri("google") == (
            "http://localhost:8000/api/v1/llm-oauth/google/callback"
        )

    def test_build_redirect_uri_fixed_uri_passthrough(self, monkeypatch):
        monkeypatch.setattr(
            oauth_config, "DEFAULT_OAUTH_REDIRECT_URI",
            "https://app.example.com/cb",
        )
        assert oauth_config.build_redirect_uri("openai") == "https://app.example.com/cb"

    def test_get_oauth_config_known_provider(self):
        cfg = oauth_config.get_oauth_config("google")
        assert cfg is not None
        assert cfg["token_type"] == "Bearer"
        assert "scopes" in cfg

    def test_get_oauth_config_unknown_provider(self):
        assert oauth_config.get_oauth_config("bogus") is None

    def test_get_provider_client_id_unknown_provider(self):
        assert oauth_config.get_provider_client_id("bogus") is None

    def test_get_provider_client_secret_unknown_provider(self):
        assert oauth_config.get_provider_client_secret("bogus") is None

    def test_get_provider_client_id_missing_env(self, monkeypatch):
        monkeypatch.delenv("OPENAI_OAUTH_CLIENT_ID", raising=False)
        assert oauth_config.get_provider_client_id("openai") is None

    def test_is_provider_oauth_configured_false(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_OAUTH_CLIENT_ID", raising=False)
        monkeypatch.delenv("ANTHROPIC_OAUTH_CLIENT_SECRET", raising=False)
        assert oauth_config.is_provider_oauth_configured("anthropic") is False

    def test_is_provider_oauth_configured_true(self, monkeypatch):
        _configure_provider("google", monkeypatch)
        assert oauth_config.is_provider_oauth_configured("google") is True

    def test_list_supported_providers(self):
        assert set(oauth_config.list_supported_providers()) == {
            "google", "openai", "anthropic", "huggingface"
        }

    def test_get_provider_display_name_known(self):
        assert oauth_config.get_provider_display_name("google") == "Google AI Studio"

    def test_get_provider_display_name_fallback(self):
        assert oauth_config.get_provider_display_name("bogus") == "bogus"


# ---------------------------------------------------------------------------
# get_authorization_url
# ---------------------------------------------------------------------------

class TestAuthorizationUrl:
    def test_generates_state(self, monkeypatch):
        _configure_provider("google", monkeypatch)
        h = LLMOAuthHandler(encryption_key=VALID_KEY)
        res = h.get_authorization_url("google")
        assert "client_id=test-client-id" in res["authorization_url"]
        assert "response_type=code" in res["authorization_url"]
        assert "state=" in res["authorization_url"]
        assert res["state"]
        assert res["provider_id"] == "google"

    def test_uses_caller_state(self, monkeypatch):
        _configure_provider("google", monkeypatch)
        h = LLMOAuthHandler(encryption_key=VALID_KEY)
        res = h.get_authorization_url("google", state="csrf-nonce-123")
        assert res["state"] == "csrf-nonce-123"
        assert "state=csrf-nonce-123" in res["authorization_url"]

    def test_unknown_provider_raises(self):
        h = LLMOAuthHandler()
        with pytest.raises(ValueError, match="Unknown provider"):
            h.get_authorization_url("not-a-provider")

    def test_not_configured_raises(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)
        h = LLMOAuthHandler()
        with pytest.raises(ValueError, match="OAuth not configured"):
            h.get_authorization_url("google")

    def test_custom_redirect_uri(self, monkeypatch):
        _configure_provider("openai", monkeypatch)
        h = LLMOAuthHandler()
        res = h.get_authorization_url("openai", redirect_uri="https://app.example.com/cb")
        assert "redirect_uri=https%3A%2F%2Fapp.example.com%2Fcb" in res["authorization_url"]

    def test_default_redirect_uri_used(self, monkeypatch):
        _configure_provider("anthropic", monkeypatch)
        h = LLMOAuthHandler()
        res = h.get_authorization_url("anthropic")
        from urllib.parse import urlencode
        assert urlencode({"redirect_uri": oauth_config.DEFAULT_OAUTH_REDIRECT_URI}) in res["authorization_url"]

    def test_pkce_flag_does_not_crash(self, monkeypatch):
        _configure_provider("google", monkeypatch)
        h = LLMOAuthHandler()
        res = h.get_authorization_url("google")
        assert "code_challenge=" not in res["authorization_url"]

    def test_scopes_joined(self, monkeypatch):
        _configure_provider("huggingface", monkeypatch)
        h = LLMOAuthHandler()
        res = h.get_authorization_url("huggingface")
        assert "scope=read-repos" in res["authorization_url"]


# ---------------------------------------------------------------------------
# exchange_code_for_tokens
# ---------------------------------------------------------------------------

class TestTokenExchange:
    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        _configure_provider("google", monkeypatch)
        h = LLMOAuthHandler()
        mock_client = _http_client_mock(
            response=_json_response({"access_token": "AT", "refresh_token": "RT", "expires_in": 3600})
        )
        with patch("core.llm_oauth_handler.httpx.AsyncClient", return_value=mock_client):
            tokens = await h.exchange_code_for_tokens("google", "auth-code-123")
        assert tokens["access_token"] == "AT"
        _, kwargs = mock_client.post.call_args
        assert kwargs["data"]["grant_type"] == "authorization_code"
        assert kwargs["data"]["code"] == "auth-code-123"
        assert kwargs["data"]["client_id"] == "test-client-id"
        assert kwargs["data"]["client_secret"] == "test-client-secret"

    @pytest.mark.asyncio
    async def test_custom_redirect_uri(self, monkeypatch):
        _configure_provider("google", monkeypatch)
        h = LLMOAuthHandler()
        mock_client = _http_client_mock(response=_json_response({"access_token": "AT"}))
        with patch("core.llm_oauth_handler.httpx.AsyncClient", return_value=mock_client):
            await h.exchange_code_for_tokens("google", "code", "https://cb.example.com/x")
        _, kwargs = mock_client.post.call_args
        assert kwargs["data"]["redirect_uri"] == "https://cb.example.com/x"

    @pytest.mark.asyncio
    async def test_unknown_provider(self):
        h = LLMOAuthHandler()
        with pytest.raises(ValueError, match="Unknown provider"):
            await h.exchange_code_for_tokens("bogus", "code")

    @pytest.mark.asyncio
    async def test_http_error_propagates(self, monkeypatch):
        import httpx
        _configure_provider("google", monkeypatch)
        h = LLMOAuthHandler()
        fake_response = MagicMock()
        fake_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400 Bad Request", request=MagicMock(), response=MagicMock()
        )
        mock_client = _http_client_mock(response=fake_response)
        with patch("core.llm_oauth_handler.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPError):
                await h.exchange_code_for_tokens("google", "bad-code")


# ---------------------------------------------------------------------------
# store_oauth_credentials
# ---------------------------------------------------------------------------

class TestStoreCredentials:
    def test_creates_new_encrypted(self, monkeypatch):
        _configure_provider("google", monkeypatch)
        h = LLMOAuthHandler(encryption_key=VALID_KEY)
        db = _mock_db(creds_list=[])
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
            cred = h.store_oauth_credentials(
                user_id="user-1", tenant_id="tenant-1", provider_id="google",
                tokens={"access_token": "AT", "refresh_token": "RT", "expires_in": 3600,
                        "scope": "s", "token_type": "Bearer"},
                account_info={"email": "u@example.com", "name": "User"},
            )
        db.add.assert_called_once()
        db.commit.assert_called()
        assert cred.access_token != "AT"
        assert h._decrypt_token(cred.access_token) == "AT"
        assert h._decrypt_token(cred.refresh_token) == "RT"
        assert cred.account_email == "u@example.com"
        assert cred.expires_at is not None
        assert cred.credential_type == "oauth"

    def test_deactivates_existing_same_type_only(self, monkeypatch):
        _configure_provider("google", monkeypatch)
        h = LLMOAuthHandler(encryption_key=VALID_KEY)
        engine, Session = _real_db()
        s = Session()
        s.add(_real_cred(id="old-oauth", credential_type="oauth"))
        s.add(_real_cred(id="old-sub", credential_type="subscription"))
        s.commit()
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(s)):
            h.store_oauth_credentials(
                user_id="user-1", tenant_id="tenant-1", provider_id="google",
                tokens={"access_token": "new"}, credential_type="oauth",
            )
        s.expire_all()
        oauth_row = s.query(LLMOAuthCredential).filter_by(id="old-oauth").one()
        sub_row = s.query(LLMOAuthCredential).filter_by(id="old-sub").one()
        assert oauth_row.is_active is False
        assert oauth_row.revoked_at is not None
        assert sub_row.is_active is True
        s.close()
        engine.dispose()

    def test_store_without_refresh_token_or_account_info(self, monkeypatch):
        _configure_provider("google", monkeypatch)
        h = LLMOAuthHandler(encryption_key=VALID_KEY)
        db = _mock_db(creds_list=[])
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
            cred = h.store_oauth_credentials(
                user_id="u", tenant_id="t", provider_id="google",
                tokens={"access_token": "AT"},
            )
        assert cred.refresh_token is None
        assert cred.expires_at is None
        assert cred.account_email is None
        assert cred.account_name is None
        assert cred.token_type == "Bearer"

    def test_store_refresh_token_expires_in(self, monkeypatch):
        _configure_provider("google", monkeypatch)
        h = LLMOAuthHandler(encryption_key=VALID_KEY)
        db = _mock_db(creds_list=[])
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
            cred = h.store_oauth_credentials(
                user_id="u", tenant_id="t", provider_id="google",
                tokens={"access_token": "AT", "refresh_token": "RT",
                        "refresh_token_expires_in": 86400},
            )
        assert cred.refresh_expires_at is not None


# ---------------------------------------------------------------------------
# encryption / decryption
# ---------------------------------------------------------------------------

class TestEncryption:
    def test_roundtrip(self):
        h = LLMOAuthHandler(encryption_key=VALID_KEY)
        enc = h._encrypt_token("super-secret-token")
        assert enc != "super-secret-token"
        assert h._decrypt_token(enc) == "super-secret-token"

    def test_encrypt_plaintext_dev_no_key(self):
        h = LLMOAuthHandler(encryption_key=None)
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            assert h._encrypt_token("plain") == "plain"

    def test_encrypt_production_refuses_plaintext(self):
        h = LLMOAuthHandler(encryption_key=None)
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            with pytest.raises(ValueError, match="encryption_key not configured"):
                h._encrypt_token("plain")

    def test_decrypt_no_key_returns_plaintext(self):
        h = LLMOAuthHandler(encryption_key=None)
        assert h._decrypt_token("plain") == "plain"

    def test_decrypt_corrupted_token_raises(self):
        h = LLMOAuthHandler(encryption_key=VALID_KEY)
        with pytest.raises(ValueError, match="Failed to decrypt"):
            h._decrypt_token("not-a-valid-encrypted-token!!!")

    def test_decrypt_raw_bytes_input(self):
        h = LLMOAuthHandler(encryption_key=VALID_KEY)
        enc = h._encrypt_token("payload")
        raw = base64.urlsafe_b64decode(enc.encode())
        assert h._decrypt_token(raw) == "payload"

    def test_encrypt_invalid_key_raises(self):
        from cryptography.fernet import InvalidToken
        h = LLMOAuthHandler(encryption_key=VALID_KEY)
        with patch("cryptography.fernet.Fernet") as mock_fernet:
            mock_fernet.return_value.encrypt.side_effect = InvalidToken("bad")
            with pytest.raises(ValueError, match="Failed to encrypt token"):
                h._encrypt_token("x")

    def test_cryptography_missing_falls_back_to_plaintext(self, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "cryptography.fernet":
                raise ImportError("no cryptography")
            return real_import(name, *args, **kwargs)

        h = LLMOAuthHandler(encryption_key=VALID_KEY)
        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert h._encrypt_token("x") == "x"
        assert h._decrypt_token("x") == "x"

    def test_decrypt_access_token_wrapper(self):
        h = LLMOAuthHandler(encryption_key=VALID_KEY)
        cred = _make_credential(access_token=h._encrypt_token("AT"))
        assert h.decrypt_access_token(cred) == "AT"


# ---------------------------------------------------------------------------
# get_active_credentials
# ---------------------------------------------------------------------------

class TestGetActiveCredentials:
    def test_found_updates_usage(self):
        h = LLMOAuthHandler()
        cred = _make_credential(usage_count=3)
        db = _mock_db(cred=cred)
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
            result = h.get_active_credentials(user_id="user-1", provider_id="google")
        assert result is cred
        assert cred.usage_count == 4
        assert cred.last_used_at is not None
        db.commit.assert_called()

    def test_not_found_returns_none(self):
        h = LLMOAuthHandler()
        db = _mock_db(cred=None)
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
            result = h.get_active_credentials(user_id="x", provider_id="google")
        assert result is None

    def test_tenant_scoped(self):
        h = LLMOAuthHandler()
        engine, Session = _real_db()
        s = Session()
        s.add(_real_cred(id="mine", tenant_id="tenant-A"))
        s.add(_real_cred(id="theirs", tenant_id="tenant-B"))
        s.commit()
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(s)):
            result = h.get_active_credentials(
                user_id="user-1", provider_id="google", tenant_id="tenant-A")
        assert result.id == "mine"
        s.close()
        engine.dispose()

    def test_oauth_type_excludes_subscription(self):
        h = LLMOAuthHandler()
        engine, Session = _real_db()
        s = Session()
        s.add(_real_cred(id="o", credential_type="oauth"))
        s.add(_real_cred(id="s", credential_type="subscription"))
        s.commit()
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(s)):
            result = h.get_active_credentials(
                user_id="user-1", provider_id="google", credential_type="oauth")
        assert result.id == "o"
        s.close()
        engine.dispose()

    def test_subscription_type_excludes_oauth(self):
        h = LLMOAuthHandler()
        engine, Session = _real_db()
        s = Session()
        s.add(_real_cred(id="o", credential_type="oauth"))
        s.add(_real_cred(id="s", credential_type="subscription"))
        s.commit()
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(s)):
            result = h.get_active_credentials(
                user_id="user-1", provider_id="google", credential_type="subscription")
        assert result.id == "s"
        s.close()
        engine.dispose()

    def test_no_tenant_searches_all(self):
        h = LLMOAuthHandler()
        engine, Session = _real_db()
        s = Session()
        s.add(_real_cred(id="any", tenant_id="some-tenant"))
        s.commit()
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(s)):
            result = h.get_active_credentials(user_id="user-1", provider_id="google")
        assert result.id == "any"
        s.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# refresh_access_token
# ---------------------------------------------------------------------------

class TestRefresh:
    @pytest.mark.asyncio
    async def test_success_with_rotation(self, monkeypatch):
        _configure_provider("google", monkeypatch)
        h = LLMOAuthHandler(encryption_key=VALID_KEY)
        cred = _make_credential(
            access_token=h._encrypt_token("old-AT"),
            refresh_token=h._encrypt_token("old-RT"),
        )
        db = _mock_db(cred=cred)
        mock_client = _http_client_mock(response=_json_response(
            {"access_token": "new-AT", "refresh_token": "new-RT", "expires_in": 7200}
        ))
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)), \
             patch("core.llm_oauth_handler.httpx.AsyncClient", return_value=mock_client):
            ok = await h.refresh_access_token("cred-1")
        assert ok is True
        assert h._decrypt_token(cred.access_token) == "new-AT"
        assert h._decrypt_token(cred.refresh_token) == "new-RT"
        assert cred.expires_at is not None
        assert cred.last_validated_at is not None

    @pytest.mark.asyncio
    async def test_success_without_rotation_fields(self, monkeypatch):
        _configure_provider("google", monkeypatch)
        h = LLMOAuthHandler(encryption_key=None)
        cred = _make_credential(refresh_token="rt", expires_at=None)
        db = _mock_db(cred=cred)
        mock_client = _http_client_mock(response=_json_response({"access_token": "new-AT"}))
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)), \
             patch("core.llm_oauth_handler.httpx.AsyncClient", return_value=mock_client):
            ok = await h.refresh_access_token("cred-1")
        assert ok is True
        assert cred.expires_at is None
        assert cred.refresh_token == "rt"

    @pytest.mark.asyncio
    async def test_credential_not_found(self):
        h = LLMOAuthHandler()
        db = _mock_db(cred=None)
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
            ok = await h.refresh_access_token("missing")
        assert ok is False

    @pytest.mark.asyncio
    async def test_no_refresh_token(self):
        h = LLMOAuthHandler()
        cred = _make_credential(refresh_token=None)
        db = _mock_db(cred=cred)
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
            ok = await h.refresh_access_token("cred-1")
        assert ok is False

    @pytest.mark.asyncio
    async def test_unknown_provider(self):
        h = LLMOAuthHandler()
        cred = _make_credential(provider_id="bogus")
        db = _mock_db(cred=cred)
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
            ok = await h.refresh_access_token("cred-1")
        assert ok is False

    @pytest.mark.asyncio
    async def test_http_error_returns_false(self, monkeypatch):
        _configure_provider("google", monkeypatch)
        h = LLMOAuthHandler()
        cred = _make_credential(refresh_token="enc")
        db = _mock_db(cred=cred)
        mock_client = _http_client_mock(post_side_effect=Exception("network down"))
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)), \
             patch("core.llm_oauth_handler.httpx.AsyncClient", return_value=mock_client):
            ok = await h.refresh_access_token("cred-1")
        assert ok is False


# ---------------------------------------------------------------------------
# validate_and_refresh_if_needed
# ---------------------------------------------------------------------------

class TestValidateAndRefresh:
    @pytest.mark.asyncio
    async def test_expired_triggers_refresh(self, monkeypatch):
        _configure_provider("google", monkeypatch)
        h = LLMOAuthHandler(encryption_key=None)
        cred = _make_credential(
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            refresh_token="plain-RT",
        )
        db = _mock_db(cred=cred)
        mock_client = _http_client_mock(response=_json_response({"access_token": "fresh", "expires_in": 3600}))
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)), \
             patch("core.llm_oauth_handler.httpx.AsyncClient", return_value=mock_client):
            ok = await h.validate_and_refresh_if_needed(cred)
        assert ok is True

    @pytest.mark.asyncio
    async def test_valid_skips_refresh_stamps_validation(self):
        h = LLMOAuthHandler()
        cred = _make_credential(expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        fresh_cred = _make_credential(id="cred-1")
        db = _mock_db(cred=fresh_cred)
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
            ok = await h.validate_and_refresh_if_needed(cred)
        assert ok is True
        assert fresh_cred.last_validated_at is not None

    @pytest.mark.asyncio
    async def test_no_expiry_treated_as_valid(self):
        h = LLMOAuthHandler()
        cred = _make_credential(expires_at=None)
        fresh_cred = _make_credential(id="cred-1")
        db = _mock_db(cred=fresh_cred)
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
            ok = await h.validate_and_refresh_if_needed(cred)
        assert ok is True

    @pytest.mark.asyncio
    async def test_credential_vanished_from_db(self):
        h = LLMOAuthHandler()
        cred = _make_credential(expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        db = _mock_db(cred=None)
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
            ok = await h.validate_and_refresh_if_needed(cred)
        assert ok is True

    @pytest.mark.asyncio
    async def test_refresh_failure_returns_false(self, monkeypatch):
        _configure_provider("google", monkeypatch)
        h = LLMOAuthHandler()
        cred = _make_credential(
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            refresh_token="enc",
        )
        db = _mock_db(cred=cred)
        mock_client = _http_client_mock(post_side_effect=Exception("boom"))
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)), \
             patch("core.llm_oauth_handler.httpx.AsyncClient", return_value=mock_client):
            ok = await h.validate_and_refresh_if_needed(cred)
        assert ok is False


# ---------------------------------------------------------------------------
# revoke + list
# ---------------------------------------------------------------------------

class TestRevokeAndList:
    def test_revoke_success(self):
        h = LLMOAuthHandler()
        cred = _make_credential(is_active=True)
        db = _mock_db(cred=cred)
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
            ok = h.revoke_credentials("cred-1")
        assert ok is True
        assert cred.is_active is False
        assert cred.revoked_at is not None

    def test_revoke_not_found(self):
        h = LLMOAuthHandler()
        db = _mock_db(cred=None)
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
            ok = h.revoke_credentials("missing")
        assert ok is False

    def test_list_all(self):
        h = LLMOAuthHandler()
        engine, Session = _real_db()
        s = Session()
        s.add(_real_cred(id="c1", provider_id="google"))
        s.add(_real_cred(id="c2", provider_id="openai"))
        s.add(_real_cred(id="c3", user_id="other-user", provider_id="google"))
        s.commit()
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(s)):
            result = h.list_credentials(user_id="user-1")
        assert {c.id for c in result} == {"c1", "c2"}
        s.close()
        engine.dispose()

    def test_list_filtered_by_provider(self):
        h = LLMOAuthHandler()
        engine, Session = _real_db()
        s = Session()
        s.add(_real_cred(id="g", provider_id="google"))
        s.add(_real_cred(id="o", provider_id="openai"))
        s.commit()
        with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(s)):
            result = h.list_credentials(user_id="user-1", provider_id="google")
        assert len(result) == 1
        assert result[0].id == "g"
        s.close()
        engine.dispose()
