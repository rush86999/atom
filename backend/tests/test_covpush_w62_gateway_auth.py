"""Coverage wave 62 — core/llm/gateway/auth.py (TDD, mocked db + request).

Locks in the identity-resolution contract: key hashing, prefix generation,
sliding-window rate limiting (window purge + dead-key purge), secret
extraction precedence (x-api-key -> Bearer -> JWT), api-key resolution
(revoked/expired-naive/user-missing/non-active/usage bump), JWT resolution
and the 401 fallthroughs. Also proves the rate-limit "0 = unlimited"
contract (``_check_rate_limit`` treats ``<=0`` as no limit; ``_resolve_api_key``
must not silently coerce an explicit 0 back to the 60 default).
"""
from collections import deque
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.exceptions import HTTPException

from core.llm.gateway.auth import (
    GatewayIdentity,
    _RATE_LIMIT_WINDOW_SECONDS,
    _check_rate_limit,
    _extract_secret,
    _rate_limit_state,
    _resolve_api_key,
    _resolve_jwt,
    generate_key_prefix,
    get_gateway_identity,
    hash_api_key,
)
from core.models import GatewayApiKey, User


def make_request(headers=None):
    raw = headers or {}
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/v1/chat/completions",
        "headers": [(k.lower().encode(), v.encode()) for k, v in raw.items()],
        "query_string": b"",
        "server": ("test", 80),
        "client": ("1.2.3.4", 1),
        "scheme": "http",
    })


def make_row(**kw):
    defaults = dict(
        id="key-1",
        key_hash=hash_api_key("atom_sk_test_key"),
        key_prefix="atom_sk_abcd",
        name="test",
        user_id="u-1",
        tenant_id=None,
        workspace_id=None,
        is_active=True,
        rate_limit_per_minute=60,
        expires_at=None,
        revoked_at=None,
        last_used=None,
        total_requests=None,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def make_user(**kw):
    defaults = dict(id="u-1", status="active")
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def make_db(api_key_row=None, user=None):
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()

    def _query(cls):
        q = MagicMock()
        q.filter.return_value.first.return_value = (
            api_key_row if cls is GatewayApiKey else user
        )
        return q

    db.query.side_effect = _query
    return db


@pytest.fixture(autouse=True)
def clean_rate_state():
    _rate_limit_state.clear()
    yield
    _rate_limit_state.clear()


class TestHashing:
    def test_hash_api_key_sha256_hex(self):
        digest = hash_api_key("atom_sk_secret")
        assert len(digest) == 64
        assert digest == hash_api_key("atom_sk_secret")
        assert digest != "atom_sk_secret"
        assert digest != hash_api_key("atom_sk_other")

    def test_generate_key_prefix(self):
        prefix = generate_key_prefix("atom_sk_secret")
        assert prefix.startswith("atom_sk_")
        assert len(prefix) == 12
        assert set(prefix[8:]).issubset(set("abcdefghijklmnopqrstuvwxyz0123456789"))

    def test_prefix_not_derived_from_secret_tail(self):
        # The prefix must not leak hex chars of the secret (previous bug used
        # plaintext[-4:]); with random alphabet chars it is independent.
        secret = "a" * 60
        prefix = generate_key_prefix(secret)
        assert prefix[8:] not in secret


class TestIdentityAudit:
    def test_to_audit_with_key(self):
        identity = GatewayIdentity(user_id="u-1", tenant_id="t-1",
                                   workspace_id="w-1", auth_method="api_key",
                                   api_key_id="key-1")
        assert identity.to_audit() == {
            "user_id": "u-1", "tenant_id": "t-1", "workspace_id": "w-1",
            "auth_method": "api_key", "api_key_id": "key-1",
        }

    def test_to_audit_without_key(self):
        identity = GatewayIdentity(user_id="u-1", tenant_id="t-1",
                                   workspace_id="w-1", auth_method="jwt")
        assert identity.to_audit()["api_key_id"] == ""


class TestRateLimit:
    def test_disabled_when_limit_non_positive(self):
        _check_rate_limit("hash-1", 0)
        _check_rate_limit("hash-2", -5)
        assert _rate_limit_state == {}

    def test_under_limit_appends(self):
        _check_rate_limit("hash-1", 60)
        _check_rate_limit("hash-1", 60)
        assert len(_rate_limit_state["hash-1"]) == 2

    def test_over_limit_raises_429(self):
        with pytest.raises(HTTPException) as exc:
            for _ in range(3):
                _check_rate_limit("hash-1", 2)
        assert exc.value.status_code == 429

    def test_window_slides(self):
        now = datetime.now(timezone.utc).timestamp()
        _rate_limit_state["hash-1"] = deque([
            now - (_RATE_LIMIT_WINDOW_SECONDS + 5),
            now - (_RATE_LIMIT_WINDOW_SECONDS + 3),
            now,
        ])
        _check_rate_limit("hash-1", 60)
        assert len(_rate_limit_state["hash-1"]) == 2  # old timestamps purged

    def test_stale_key_purge_when_many_keys(self):
        now = datetime.now(timezone.utc).timestamp()
        for i in range(1001):
            _rate_limit_state[f"key-{i}"] = deque([now - (_RATE_LIMIT_WINDOW_SECONDS + 1)])
        # One active key inside the window: it survives the purge.
        _rate_limit_state["active-key"] = deque([now])
        _check_rate_limit("hash-new", 60)
        assert "active-key" in _rate_limit_state
        assert len(_rate_limit_state) < 1001


class TestExtractSecret:
    def test_x_api_key_wins(self):
        req = make_request({"x-api-key": " atom_sk_abc ", "Authorization": "Bearer jwt.x.y"})
        assert _extract_secret(req) == "atom_sk_abc"

    def test_bearer_fallback(self):
        req = make_request({"Authorization": "Bearer atom_sk_bcd"})
        assert _extract_secret(req) == "atom_sk_bcd"

    def test_bearer_case_insensitive(self):
        req = make_request({"Authorization": "bearer   atom_sk_xyz"})
        assert _extract_secret(req) == "atom_sk_xyz"

    def test_missing(self):
        assert _extract_secret(make_request({})) is None
        assert _extract_secret(make_request({"Authorization": "Basic abc"})) is None


class TestResolveApiKey:
    @pytest.mark.asyncio
    async def test_unknown_key_rejected(self):
        db = make_db()
        with pytest.raises(HTTPException) as exc:
            await _resolve_api_key("atom_sk_unknown", db, None)
        assert exc.value.status_code == 401
        assert "invalid_api_key" in exc.value.detail["error"]["code"]

    @pytest.mark.asyncio
    async def test_inactive_key_rejected(self):
        db = make_db(api_key_row=make_row(is_active=False))
        with pytest.raises(HTTPException) as exc:
            await _resolve_api_key("atom_sk_test_key", db, None)
        assert "revoked" in exc.value.detail["error"]["message"]

    @pytest.mark.asyncio
    async def test_revoked_key_rejected(self):
        db = make_db(api_key_row=make_row(revoked_at=datetime.now(timezone.utc)))
        with pytest.raises(HTTPException) as exc:
            await _resolve_api_key("atom_sk_test_key", db, None)
        assert "revoked" in exc.value.detail["error"]["message"]

    @pytest.mark.asyncio
    async def test_expired_aware_key_rejected(self):
        db = make_db(api_key_row=make_row(
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
        with pytest.raises(HTTPException) as exc:
            await _resolve_api_key("atom_sk_test_key", db, None)
        assert "expired" in exc.value.detail["error"]["message"]

    @pytest.mark.asyncio
    async def test_expired_naive_key_rejected(self):
        # SQLite round-trips DateTime(timezone=True) as naive — normalize first.
        db = make_db(api_key_row=make_row(
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)))
        with pytest.raises(HTTPException) as exc:
            await _resolve_api_key("atom_sk_test_key", db, None)
        assert "expired" in exc.value.detail["error"]["message"]

    @pytest.mark.asyncio
    async def test_user_missing_rejected(self):
        db = make_db(api_key_row=make_row(), user=None)
        with pytest.raises(HTTPException) as exc:
            await _resolve_api_key("atom_sk_test_key", db, None)
        assert "invalid_api_key" in exc.value.detail["error"]["code"]

    @pytest.mark.asyncio
    async def test_non_active_user_rejected(self):
        db = make_db(api_key_row=make_row(), user=make_user(status="suspended"))
        with pytest.raises(HTTPException) as exc:
            await _resolve_api_key("atom_sk_test_key", db, None)
        assert "not active" in exc.value.detail["error"]["message"]

    @pytest.mark.asyncio
    async def test_success_identity_and_usage_bump(self):
        row = make_row()
        db = make_db(api_key_row=row, user=make_user())
        with patch("core.personal_scope.resolve_tenant_id", return_value="t-1"), \
             patch("core.personal_scope.resolve_workspace_id", return_value="w-1"):
            identity = await _resolve_api_key("atom_sk_test_key", db, None)
        assert identity.user_id == "u-1"
        assert identity.tenant_id == "t-1"
        assert identity.workspace_id == "w-1"
        assert identity.auth_method == "api_key"
        assert identity.api_key_id == "key-1"
        assert identity.rate_limit_per_minute == 60
        assert row.last_used is not None
        assert row.total_requests == 1
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_usage_bump_failure_rolls_back_and_still_succeeds(self):
        row = make_row()
        db = make_db(api_key_row=row, user=make_user())
        db.commit.side_effect = RuntimeError("commit failed")
        with patch("core.personal_scope.resolve_tenant_id", return_value="t-1"), \
             patch("core.personal_scope.resolve_workspace_id", return_value="w-1"):
            identity = await _resolve_api_key("atom_sk_test_key", db, None)
        assert identity.user_id == "u-1"
        db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_tenant_workspace_fallback_from_scope(self):
        row = make_row(tenant_id=None, workspace_id=None)
        db = make_db(api_key_row=row, user=make_user())
        with patch("core.personal_scope.resolve_tenant_id", return_value="t-scope"), \
             patch("core.personal_scope.resolve_workspace_id", return_value="w-scope"):
            identity = await _resolve_api_key("atom_sk_test_key", db, None)
        assert identity.tenant_id == "t-scope"
        assert identity.workspace_id == "w-scope"

    @pytest.mark.asyncio
    async def test_row_rate_limit_zero_means_unlimited(self):
        # Contract: _check_rate_limit treats <=0 as "no limit". A row with an
        # explicit 0 must keep that semantic — NOT be silently coerced to 60.
        row = make_row(rate_limit_per_minute=0)
        db = make_db(api_key_row=row, user=make_user())
        with patch("core.personal_scope.resolve_tenant_id", return_value="t-1"), \
             patch("core.personal_scope.resolve_workspace_id", return_value="w-1"):
            identity = await _resolve_api_key("atom_sk_test_key", db, None)
        assert identity.rate_limit_per_minute == 0

    @pytest.mark.asyncio
    async def test_rate_limit_enforced_per_key(self):
        row = make_row(rate_limit_per_minute=2)
        db = make_db(api_key_row=row, user=make_user())
        with patch("core.personal_scope.resolve_tenant_id", return_value="t-1"), \
             patch("core.personal_scope.resolve_workspace_id", return_value="w-1"):
            await _resolve_api_key("atom_sk_test_key", db, None)
            await _resolve_api_key("atom_sk_test_key", db, None)
            with pytest.raises(HTTPException) as exc:
                await _resolve_api_key("atom_sk_test_key", db, None)
        assert exc.value.status_code == 429


class TestResolveJwt:
    @pytest.mark.asyncio
    async def test_jwt_identity(self):
        db = make_db()
        user = make_user()
        with patch("core.auth.get_current_user", new=AsyncMock(return_value=user)), \
             patch("core.personal_scope.resolve_tenant_id", return_value="t-jwt"), \
             patch("core.personal_scope.resolve_workspace_id", return_value="w-jwt"):
            identity = await _resolve_jwt(None, "a.b.c", db)
        assert identity.user_id == "u-1"
        assert identity.tenant_id == "t-jwt"
        assert identity.workspace_id == "w-jwt"
        assert identity.auth_method == "jwt"
        assert identity.user is user


class TestGetGatewayIdentity:
    @pytest.mark.asyncio
    async def test_api_key_priority_over_bearer_jwt(self):
        req = make_request({"x-api-key": "atom_sk_test_key",
                            "Authorization": "Bearer a.b.c"})
        row = make_row()
        db = make_db(api_key_row=row, user=make_user())
        with patch("core.personal_scope.resolve_tenant_id", return_value="t-1"), \
             patch("core.personal_scope.resolve_workspace_id", return_value="w-1"), \
             patch("core.llm.gateway.auth._resolve_jwt", new=AsyncMock()) as jwt_mock:
            identity = await get_gateway_identity(req, db)
        assert identity.auth_method == "api_key"
        jwt_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_bearer_api_key(self):
        req = make_request({"Authorization": "Bearer atom_sk_test_key"})
        row = make_row()
        db = make_db(api_key_row=row, user=make_user())
        with patch("core.personal_scope.resolve_tenant_id", return_value="t-1"), \
             patch("core.personal_scope.resolve_workspace_id", return_value="w-1"):
            identity = await get_gateway_identity(req, db)
        assert identity.auth_method == "api_key"

    @pytest.mark.asyncio
    async def test_jwt_shaped_token_uses_standard_auth(self):
        req = make_request({"Authorization": "Bearer aaa.bbb.ccc"})
        db = make_db()
        with patch("core.llm.gateway.auth._resolve_jwt",
                   new=AsyncMock(return_value=GatewayIdentity(
                       user_id="u-9", tenant_id="t-9", workspace_id="w-9",
                       auth_method="jwt"))):
            identity = await get_gateway_identity(req, db)
        assert identity.auth_method == "jwt"
        assert identity.user_id == "u-9"

    @pytest.mark.asyncio
    async def test_non_key_non_jwt_401(self):
        req = make_request({"Authorization": "Bearer not-a-jwt"})
        with pytest.raises(HTTPException) as exc:
            await get_gateway_identity(req, make_db())
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_secret_401(self):
        with pytest.raises(HTTPException) as exc:
            await get_gateway_identity(make_request({}), make_db())
        assert exc.value.status_code == 401
        assert "Missing API key" in exc.value.detail["error"]["message"]
