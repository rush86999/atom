"""
Coverage + security bug-hunt tests for core.llm_oauth_handler.

Exercises:
- Authorization URL generation (incl. CSRF state, PKCE flag, redirect_uri)
- Code-for-token exchange (httpx mocked — NO real network)
- Credential storage, retrieval, tenant isolation, credential_type scoping
- Token encryption/decryption round-trips (Fernet) + plaintext dev path +
  production refusal
- Refresh flow (success + all failure branches)
- validate_and_refresh_if_needed (fresh / expired / refresh-fail)
- revoke + list

Security bug-hunt:
- Production must refuse to store tokens without an encryption key (plaintext).
- Tenant scoping must prevent cross-tenant credential leakage.
- credential_type scoping must not let a 'subscription' reconnect revoke an
  active 'oauth' grant (and vice versa).
"""

import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm_oauth_handler import LLMOAuthHandler
from core.models import LLMOAuthCredential


# A valid Fernet key (same one conftest sets as BYOK_ENCRYPTION_KEY).
VALID_KEY = b"MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="


# ---------------------------------------------------------------------------
# DB context-manager helper
# ---------------------------------------------------------------------------

def _db_ctx(db):
    @contextmanager
    def fake_ctx():
        yield db

    return fake_ctx()


def _mock_db(cred=None, creds_list=None, all_creds=None):
    """Build a fake DB session used by get_db_session()."""
    db = MagicMock()

    # query(...).filter(...).all() -> list of existing creds (for deactivation)
    # query(...).filter(...).first() -> single cred (for refresh/revoke/get)
    query = MagicMock()
    filtered = MagicMock()
    query.filter.return_value = filtered
    filtered.all.return_value = creds_list if creds_list is not None else []
    filtered.first.return_value = cred
    db.query.return_value = query

    # For list_credentials -> query.all()
    db.query.return_value.all.return_value = all_creds if all_creds is not None else ([cred] if cred else [])

    # When user_id/provider_id chains are added, keep returning the same filtered obj
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db._cred = cred
    return db


# ---------------------------------------------------------------------------
# OAuth config env setup helper
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Real in-memory SQLite DB helpers (for tests that must exercise actual
# SQLAlchemy filter conditions — e.g. credential_type / tenant scoping).
# ---------------------------------------------------------------------------

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
    """Build a real LLMOAuthCredential row for the in-memory DB."""
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


# ---------------------------------------------------------------------------
# get_authorization_url
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_authorization_url_generates_state(monkeypatch):
    _configure_provider("google", monkeypatch)
    h = LLMOAuthHandler(encryption_key=VALID_KEY)
    res = h.get_authorization_url("google")
    assert "authorization_url" in res
    assert "client_id=test-client-id" in res["authorization_url"]
    assert "response_type=code" in res["authorization_url"]
    # state auto-generated and present in both URL and response
    assert "state=" in res["authorization_url"]
    assert res["state"]
    assert res["provider_id"] == "google"


@pytest.mark.asyncio
async def test_get_authorization_url_uses_caller_state_csrf(monkeypatch):
    """BUG-hunt: when the caller supplies a state, the handler MUST echo that
    exact state back (the CSRF check on callback depends on it)."""
    _configure_provider("google", monkeypatch)
    h = LLMOAuthHandler(encryption_key=VALID_KEY)
    res = h.get_authorization_url("google", state="csrf-nonce-123")
    assert res["state"] == "csrf-nonce-123"
    assert "state=csrf-nonce-123" in res["authorization_url"]


@pytest.mark.asyncio
async def test_get_authorization_url_unknown_provider_raises(monkeypatch):
    h = LLMOAuthHandler()
    with pytest.raises(ValueError, match="Unknown provider"):
        h.get_authorization_url("not-a-provider")


@pytest.mark.asyncio
async def test_get_authorization_url_not_configured_raises(monkeypatch):
    # Valid provider id but no env credentials configured
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)
    h = LLMOAuthHandler()
    with pytest.raises(ValueError, match="OAuth not configured"):
        h.get_authorization_url("google")


@pytest.mark.asyncio
async def test_get_authorization_url_custom_redirect_uri(monkeypatch):
    _configure_provider("openai", monkeypatch)
    h = LLMOAuthHandler()
    res = h.get_authorization_url("openai", redirect_uri="https://app.example.com/cb")
    assert "redirect_uri=https%3A%2F%2Fapp.example.com%2Fcb" in res["authorization_url"]


@pytest.mark.asyncio
async def test_get_authorization_url_default_redirect_uri_used(monkeypatch):
    from core.llm_oauth_config import DEFAULT_OAUTH_REDIRECT_URI
    _configure_provider("anthropic", monkeypatch)
    h = LLMOAuthHandler()
    res = h.get_authorization_url("anthropic")
    # default redirect URI present (urlencoded)
    from urllib.parse import urlencode
    assert urlencode({"redirect_uri": DEFAULT_OAUTH_REDIRECT_URI}) in res["authorization_url"]


@pytest.mark.asyncio
async def test_get_authorization_url_pkce_flag_does_not_crash(monkeypatch):
    """BUG-hunt: google has pkce=True but the handler's PKCE branch is a TODO
    (no challenge generated). The URL must still build without error; we assert
    current behavior and that no code_challenge leaks an empty value."""
    _configure_provider("google", monkeypatch)
    h = LLMOAuthHandler()
    res = h.get_authorization_url("google")
    # PKCE is declared but not implemented; ensure no empty/malformed
    # code_challenge parameter is added.
    assert "code_challenge=" not in res["authorization_url"]


@pytest.mark.asyncio
async def test_get_authorization_url_scopes_joined(monkeypatch):
    _configure_provider("huggingface", monkeypatch)
    h = LLMOAuthHandler()
    res = h.get_authorization_url("huggingface")
    # HuggingFace scopes joined by space, urlencoded
    assert "scope=read-repos" in res["authorization_url"]


# ---------------------------------------------------------------------------
# exchange_code_for_tokens (httpx mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exchange_code_for_tokens_success(monkeypatch):
    _configure_provider("google", monkeypatch)
    h = LLMOAuthHandler()

    fake_response = MagicMock()
    fake_response.json.return_value = {"access_token": "AT", "refresh_token": "RT", "expires_in": 3600}
    fake_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=fake_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("core.llm_oauth_handler.httpx.AsyncClient", return_value=mock_client):
        tokens = await h.exchange_code_for_tokens("google", "auth-code-123")

    assert tokens["access_token"] == "AT"
    assert tokens["refresh_token"] == "RT"
    # verify post was called with grant_type=authorization_code
    _, kwargs = mock_client.post.call_args
    assert kwargs["data"]["grant_type"] == "authorization_code"
    assert kwargs["data"]["code"] == "auth-code-123"
    assert kwargs["data"]["client_id"] == "test-client-id"
    assert kwargs["data"]["client_secret"] == "test-client-secret"


@pytest.mark.asyncio
async def test_exchange_code_for_tokens_unknown_provider(monkeypatch):
    h = LLMOAuthHandler()
    with pytest.raises(ValueError, match="Unknown provider"):
        await h.exchange_code_for_tokens("bogus", "code")


@pytest.mark.asyncio
async def test_exchange_code_for_tokens_http_error_propagates(monkeypatch):
    """BUG-hunt: a non-2xx from the token endpoint must raise (not silently
    return an error body as if it were tokens)."""
    import httpx
    _configure_provider("google", monkeypatch)
    h = LLMOAuthHandler()

    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "400 Bad Request", request=MagicMock(), response=MagicMock()
    )

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=fake_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("core.llm_oauth_handler.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(httpx.HTTPError):
            await h.exchange_code_for_tokens("google", "bad-code")


# ---------------------------------------------------------------------------
# store_oauth_credentials + encryption
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_store_oauth_credentials_creates_new(monkeypatch):
    _configure_provider("google", monkeypatch)
    h = LLMOAuthHandler(encryption_key=VALID_KEY)
    db = _mock_db(creds_list=[])

    with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
        cred = h.store_oauth_credentials(
            user_id="user-1",
            tenant_id="tenant-1",
            provider_id="google",
            tokens={"access_token": "AT", "refresh_token": "RT", "expires_in": 3600, "scope": "s", "token_type": "Bearer"},
            account_info={"email": "u@example.com", "name": "User"},
        )

    db.add.assert_called_once()
    db.commit.assert_called()
    # Stored access token must be encrypted (not plaintext)
    assert cred.access_token != "AT"
    # And must round-trip back to the plaintext via the handler.
    assert h._decrypt_token(cred.access_token) == "AT"
    assert h._decrypt_token(cred.refresh_token) == "RT"
    assert cred.account_email == "u@example.com"
    assert cred.expires_at is not None


@pytest.mark.asyncio
async def test_store_deactivates_existing_same_type_only(monkeypatch):
    """BUG-hunt: storing a new credential must deactivate prior ACTIVE creds
    of the SAME credential_type only. A 'subscription' reconnect must NOT
    revoke a live 'oauth' grant (and vice versa). We use a real in-memory DB
    so the actual SQLAlchemy credential_type filter is exercised."""
    _configure_provider("google", monkeypatch)
    h = LLMOAuthHandler(encryption_key=VALID_KEY)
    engine, Session = _real_db()
    s = Session()
    # Seed an active oauth grant and an active subscription grant for the
    # same user/provider/tenant.
    s.add(_real_cred(id="old-oauth", credential_type="oauth"))
    s.add(_real_cred(id="old-sub", credential_type="subscription"))
    s.commit()

    @contextmanager
    def fake_ctx():
        yield s

    with patch("core.llm_oauth_handler.get_db_session", return_value=fake_ctx()):
        # Store a NEW oauth credential -> only the oauth one should be deactivated.
        h.store_oauth_credentials(
            user_id="user-1", tenant_id="tenant-1", provider_id="google",
            tokens={"access_token": "new"},
            credential_type="oauth",
        )

    s.expire_all()
    oauth_row = s.query(LLMOAuthCredential).filter_by(id="old-oauth").one()
    sub_row = s.query(LLMOAuthCredential).filter_by(id="old-sub").one()
    # The existing oauth cred was deactivated; the subscription was NOT.
    assert oauth_row.is_active is False
    assert oauth_row.revoked_at is not None
    assert sub_row.is_active is True
    assert sub_row.revoked_at is None
    s.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_store_without_refresh_token(monkeypatch):
    _configure_provider("google", monkeypatch)
    h = LLMOAuthHandler(encryption_key=VALID_KEY)
    db = _mock_db(creds_list=[])
    with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
        cred = h.store_oauth_credentials(
            user_id="u", tenant_id="t", provider_id="google",
            tokens={"access_token": "AT"},  # no refresh token
        )
    assert cred.refresh_token is None
    assert cred.expires_at is None  # no expires_in


@pytest.mark.asyncio
async def test_store_refresh_expires_in_recorded(monkeypatch):
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
# Encryption / Decryption (incl. dev plaintext + production refusal)
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_roundtrip():
    h = LLMOAuthHandler(encryption_key=VALID_KEY)
    enc = h._encrypt_token("super-secret-token")
    assert enc != "super-secret-token"
    assert h._decrypt_token(enc) == "super-secret-token"


def test_encrypt_plaintext_dev_no_key():
    """In non-production with no key, tokens are stored plaintext (with a
    loud warning). This is the documented dev fallback."""
    h = LLMOAuthHandler(encryption_key=None)
    # Ensure we are NOT in production for this test.
    with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
        enc = h._encrypt_token("plain")
    assert enc == "plain"


def test_encrypt_production_refuses_plaintext():
    """BUG: in production, refusing to store tokens in plaintext must raise
    (a DB read otherwise = full account takeover). This was Bug 7 — the old
    code warned and stored plaintext. The fix raises."""
    h = LLMOAuthHandler(encryption_key=None)
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
        with pytest.raises(ValueError, match="encryption_key not configured"):
            h._encrypt_token("plain")


def test_decrypt_no_key_returns_plaintext():
    h = LLMOAuthHandler(encryption_key=None)
    assert h._decrypt_token("plain") == "plain"


def test_decrypt_corrupted_token_raises():
    h = LLMOAuthHandler(encryption_key=VALID_KEY)
    with pytest.raises(ValueError, match="Failed to decrypt"):
        h._decrypt_token("not-a-valid-encrypted-token!!!")


def test_decrypt_bytes_input():
    """_decrypt_token must handle a non-base64-encoded string via the
    fallback branch (treats it as raw Fernet bytes)."""
    h = LLMOAuthHandler(encryption_key=VALID_KEY)
    import base64
    enc = h._encrypt_token("payload")
    # Strip the base64 wrapper: decode to raw Fernet bytes, then re-feed the
    # raw bytes directly (bytes input skips the b64 decode attempt entirely).
    raw = base64.urlsafe_b64decode(enc.encode())
    assert h._decrypt_token(raw) == "payload"


def test_encrypt_invalid_key_token_raises():
    """An InvalidToken from Fernet during encrypt surfaces as ValueError."""
    h = LLMOAuthHandler(encryption_key=VALID_KEY)
    with patch("cryptography.fernet.Fernet") as mock_fernet:
        mock_fernet.return_value.encrypt.side_effect = Exception("bad key")
        # The encrypt path catches InvalidToken specifically and re-raises as
        # ValueError; a generic Exception from the patched Fernet propagates
        # through the InvalidToken handler only if it IS an InvalidToken.
        from cryptography.fernet import InvalidToken
        mock_fernet.return_value.encrypt.side_effect = InvalidToken("bad")
        with pytest.raises(ValueError, match="Failed to encrypt token"):
            h._encrypt_token("x")


def test_encrypt_decrypt_cryptography_missing(monkeypatch):
    """If cryptography isn't importable, tokens fall back to plaintext."""
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


def test_decrypt_access_token_wrapper():
    h = LLMOAuthHandler(encryption_key=VALID_KEY)
    cred = _make_credential(access_token=h._encrypt_token("AT"))
    assert h.decrypt_access_token(cred) == "AT"


# ---------------------------------------------------------------------------
# get_active_credentials (tenant isolation + credential_type scoping)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_active_credentials_returns_and_updates_usage(monkeypatch):
    _configure_provider("google", monkeypatch)
    h = LLMOAuthHandler()
    cred = _make_credential(usage_count=3)
    db = _mock_db(cred=cred)
    with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
        result = h.get_active_credentials(user_id="user-1", provider_id="google")
    assert result is cred
    # usage tracking updated
    assert cred.usage_count == 4
    assert cred.last_used_at is not None
    db.commit.assert_called()


@pytest.mark.asyncio
async def test_get_active_credentials_none_when_not_found(monkeypatch):
    h = LLMOAuthHandler()
    db = _mock_db(cred=None)
    with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
        result = h.get_active_credentials(user_id="x", provider_id="google")
    assert result is None


@pytest.mark.asyncio
async def test_get_active_credentials_tenant_scoped(monkeypatch):
    """BUG-hunt: in a multi-tenant deployment, requesting credentials must be
    scoped by tenant_id to prevent cross-tenant leakage. A credential in
    tenant-B must NOT be returned when tenant_id='tenant-A' is requested.
    Uses a real in-memory DB so the actual SQLAlchemy filter runs."""
    h = LLMOAuthHandler()
    engine, Session = _real_db()
    s = Session()
    s.add(_real_cred(id="mine", tenant_id="tenant-A"))
    s.add(_real_cred(id="theirs", tenant_id="tenant-B"))
    s.commit()

    @contextmanager
    def fake_ctx():
        yield s

    with patch("core.llm_oauth_handler.get_db_session", return_value=fake_ctx()):
        result = h.get_active_credentials(
            user_id="user-1", provider_id="google", tenant_id="tenant-A"
        )
    assert result is not None
    assert result.id == "mine"
    assert result.tenant_id == "tenant-A"

    # And asking for tenant-B returns the other tenant's cred, never tenant-A's.
    with patch("core.llm_oauth_handler.get_db_session", return_value=fake_ctx()):
        result_b = h.get_active_credentials(
            user_id="user-1", provider_id="google", tenant_id="tenant-B"
        )
    assert result_b.id == "theirs"
    s.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_get_active_credentials_oauth_includes_legacy_null(monkeypatch):
    """credential_type='oauth' must also match legacy NULL rows (rows created
    before the column existed). Real DB so the OR(...) filter is exercised."""
    h = LLMOAuthHandler()
    engine, Session = _real_db()
    s = Session()
    # Insert a legacy row with credential_type = NULL.
    legacy = _real_cred(id="legacy", credential_type="oauth")
    s.add(legacy)
    s.commit()
    # Force the column to NULL to simulate a pre-migration row.
    s.execute(LLMOAuthCredential.__table__.update()
              .where(LLMOAuthCredential.id == "legacy")
              .values(credential_type=None))
    s.commit()

    @contextmanager
    def fake_ctx():
        yield s

    with patch("core.llm_oauth_handler.get_db_session", return_value=fake_ctx()):
        result = h.get_active_credentials(
            user_id="user-1", provider_id="google", credential_type="oauth"
        )
    assert result is not None
    assert result.id == "legacy"
    s.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_get_active_credentials_subscription_filter(monkeypatch):
    """Asking for credential_type='subscription' must NOT return an oauth
    grant (and vice versa). Real DB so the type filter is exercised."""
    h = LLMOAuthHandler()
    engine, Session = _real_db()
    s = Session()
    s.add(_real_cred(id="o", credential_type="oauth"))
    s.add(_real_cred(id="s", credential_type="subscription"))
    s.commit()

    @contextmanager
    def fake_ctx():
        yield s

    with patch("core.llm_oauth_handler.get_db_session", return_value=fake_ctx()):
        result = h.get_active_credentials(
            user_id="user-1", provider_id="google", credential_type="subscription"
        )
    assert result is not None
    assert result.id == "s"
    assert result.credential_type == "subscription"
    s.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_get_active_credentials_no_tenant_searches_all(monkeypatch):
    """When tenant_id is None (single-tenant backward compat), no tenant
    filter is applied and a credential from any tenant is returned."""
    h = LLMOAuthHandler()
    engine, Session = _real_db()
    s = Session()
    s.add(_real_cred(id="any", tenant_id="some-tenant"))
    s.commit()

    @contextmanager
    def fake_ctx():
        yield s

    with patch("core.llm_oauth_handler.get_db_session", return_value=fake_ctx()):
        result = h.get_active_credentials(user_id="user-1", provider_id="google")
    assert result is not None
    assert result.id == "any"
    s.close()
    engine.dispose()


# ---------------------------------------------------------------------------
# refresh_access_token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_access_token_success(monkeypatch):
    _configure_provider("google", monkeypatch)
    h = LLMOAuthHandler(encryption_key=VALID_KEY)
    cred = _make_credential(
        access_token=h._encrypt_token("old-AT"),
        refresh_token=h._encrypt_token("old-RT"),
    )
    db = _mock_db(cred=cred)

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "access_token": "new-AT",
        "refresh_token": "new-RT",  # rotated
        "expires_in": 7200,
    }
    fake_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=fake_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)), \
         patch("core.llm_oauth_handler.httpx.AsyncClient", return_value=mock_client):
        ok = await h.refresh_access_token("cred-1")

    assert ok is True
    # access token rotated + encrypted
    assert h._decrypt_token(cred.access_token) == "new-AT"
    assert h._decrypt_token(cred.refresh_token) == "new-RT"
    assert cred.expires_at is not None
    assert cred.last_validated_at is not None


@pytest.mark.asyncio
async def test_refresh_credential_not_found(monkeypatch):
    h = LLMOAuthHandler()
    db = _mock_db(cred=None)
    with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
        ok = await h.refresh_access_token("missing")
    assert ok is False


@pytest.mark.asyncio
async def test_refresh_no_refresh_token(monkeypatch):
    h = LLMOAuthHandler()
    cred = _make_credential(refresh_token=None)
    db = _mock_db(cred=cred)
    with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
        ok = await h.refresh_access_token("cred-1")
    assert ok is False


@pytest.mark.asyncio
async def test_refresh_unknown_provider(monkeypatch):
    h = LLMOAuthHandler()
    cred = _make_credential(provider_id="bogus")
    db = _mock_db(cred=cred)
    with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
        ok = await h.refresh_access_token("cred-1")
    assert ok is False


@pytest.mark.asyncio
async def test_refresh_http_error_returns_false(monkeypatch):
    """BUG-hunt: a failed refresh must return False, not raise (callers rely
    on the boolean). The exception is swallowed and logged."""
    _configure_provider("google", monkeypatch)
    h = LLMOAuthHandler()
    cred = _make_credential(refresh_token="enc")
    db = _mock_db(cred=cred)

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("network down"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)), \
         patch("core.llm_oauth_handler.httpx.AsyncClient", return_value=mock_client):
        ok = await h.refresh_access_token("cred-1")
    assert ok is False


# ---------------------------------------------------------------------------
# validate_and_refresh_if_needed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_and_refresh_when_expired(monkeypatch):
    _configure_provider("google", monkeypatch)
    # Use a no-key handler so the plaintext refresh_token decrypts to itself.
    h = LLMOAuthHandler(encryption_key=None)
    # Expired 1 minute ago -> within refresh threshold
    cred = _make_credential(
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        refresh_token="plain-RT",
    )
    db = _mock_db(cred=cred)

    fake_response = MagicMock()
    fake_response.json.return_value = {"access_token": "fresh", "expires_in": 3600}
    fake_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=fake_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)), \
         patch("core.llm_oauth_handler.httpx.AsyncClient", return_value=mock_client):
        ok = await h.validate_and_refresh_if_needed(cred)
    assert ok is True


@pytest.mark.asyncio
async def test_validate_skips_refresh_when_valid(monkeypatch):
    """A token expiring >5min out must NOT trigger a refresh; it just records
    last_validated_at."""
    h = LLMOAuthHandler()
    cred = _make_credential(
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    fresh_cred = _make_credential(id="cred-1")
    db = _mock_db(cred=fresh_cred)

    with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
        ok = await h.validate_and_refresh_if_needed(cred)
    assert ok is True
    # The DB-backed credential got last_validated_at stamped (no refresh).
    assert fresh_cred.last_validated_at is not None


@pytest.mark.asyncio
async def test_validate_no_expiry_treated_as_valid(monkeypatch):
    h = LLMOAuthHandler()
    cred = _make_credential(expires_at=None)
    fresh_cred = _make_credential(id="cred-1")
    db = _mock_db(cred=fresh_cred)
    with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
        ok = await h.validate_and_refresh_if_needed(cred)
    assert ok is True


@pytest.mark.asyncio
async def test_validate_refresh_failure_returns_false(monkeypatch):
    """If the token is expired AND refresh fails, validate must return False."""
    _configure_provider("google", monkeypatch)
    h = LLMOAuthHandler()
    cred = _make_credential(
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        refresh_token="enc",
    )
    db = _mock_db(cred=cred)
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("boom"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)), \
         patch("core.llm_oauth_handler.httpx.AsyncClient", return_value=mock_client):
        ok = await h.validate_and_refresh_if_needed(cred)
    assert ok is False


# ---------------------------------------------------------------------------
# revoke_credentials + list_credentials
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_revoke_credentials_success(monkeypatch):
    h = LLMOAuthHandler()
    cred = _make_credential(is_active=True)
    db = _mock_db(cred=cred)
    with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
        ok = h.revoke_credentials("cred-1")
    assert ok is True
    assert cred.is_active is False
    assert cred.revoked_at is not None


@pytest.mark.asyncio
async def test_revoke_credentials_not_found(monkeypatch):
    h = LLMOAuthHandler()
    db = _mock_db(cred=None)
    with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
        ok = h.revoke_credentials("missing")
    assert ok is False


@pytest.mark.asyncio
async def test_list_credentials_all(monkeypatch):
    h = LLMOAuthHandler()
    c1, c2 = _make_credential(id="1"), _make_credential(id="2")
    db = _mock_db(all_creds=[c1, c2])
    # list_credentials chains .filter().all(); wire the filtered chain.
    db.query.return_value.filter.return_value.all.return_value = [c1, c2]
    with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
        result = h.list_credentials(user_id="user-1")
    assert result == [c1, c2]


@pytest.mark.asyncio
async def test_list_credentials_filtered_by_provider(monkeypatch):
    h = LLMOAuthHandler()
    cred = _make_credential(provider_id="google")
    db = _mock_db(all_creds=[cred])
    db.query.return_value.filter.return_value.all.return_value = [cred]
    with patch("core.llm_oauth_handler.get_db_session", return_value=_db_ctx(db)):
        result = h.list_credentials(user_id="user-1", provider_id="google")
    assert result == [cred]
