"""Round 79 — LLM gateway API-key auth hardening tests.

TDD targets:
- Expired keys on SQLite used to crash with a naive-vs-aware datetime
  TypeError (500 instead of 401) because ``DateTime(timezone=True)`` round-trips
  as a naive datetime through SQLite.
- ``generate_key_prefix`` must never leak key material (regression for the old
  ``plaintext[-4:]`` derivation).
- The Round-43 rule: non-ACTIVE users are rejected even with a valid key.
"""
import hashlib
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request

from core.llm.gateway.auth import (
    GatewayIdentity,
    _rate_limit_state,
    _resolve_api_key,
    generate_key_prefix,
    hash_api_key,
)
from core.models import GatewayApiKey


@pytest.fixture(autouse=True)
def _clean_rate_limit_state():
    _rate_limit_state.clear()
    yield
    _rate_limit_state.clear()


class TestHashApiKey:
    def test_deterministic_sha256_hex(self):
        h = hash_api_key("atom_sk_secret123")
        assert h == hashlib.sha256(b"atom_sk_secret123").hexdigest()
        assert len(h) == 64
        assert h != "atom_sk_secret123"

    def test_differs_between_keys(self):
        assert hash_api_key("atom_sk_aaa") != hash_api_key("atom_sk_bbb")

    def test_hash_is_not_the_plaintext(self):
        plaintext = "atom_sk_0123456789abcdef"
        assert hash_api_key(plaintext) != plaintext


class TestGenerateKeyPrefix:
    def test_prefix_shape(self):
        assert re.fullmatch(r"atom_sk_[a-z0-9]{4}", generate_key_prefix("atom_sk_anything"))

    def test_prefix_never_leaks_key_tail(self):
        """The displayed prefix must be independent of the secret material:
        a key tail outside the prefix alphabet can never appear in the prefix
        (regression: the old implementation used ``plaintext[-4:]``)."""
        plaintext = "atom_sk_0123456789abcdef-XYZ"
        assert plaintext[-4:] == "-XYZ"  # contains chars not in the prefix alphabet
        for _ in range(200):
            prefix = generate_key_prefix(plaintext)
            assert prefix != plaintext[-4:]
            assert not prefix.endswith(plaintext[-4:])
            assert re.fullmatch(r"atom_sk_[a-z0-9]{4}", prefix)


# --------------------------------------------------------------------------- #
# Real-DB resolution (SQLite in-memory): datetime tz handling + user status.
# --------------------------------------------------------------------------- #
class TestResolveApiKeyRealDb:
    @pytest.fixture
    def db(self, worker_database):
        from core.models import GatewayApiKey, User

        session = worker_database()
        session.query(GatewayApiKey).delete()
        session.query(User).delete()
        session.commit()
        yield session
        session.close()

    @staticmethod
    def _request(headers: dict) -> Request:
        raw_headers = [(k.encode(), v.encode()) for k, v in headers.items()]
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/chat/completions",
                "headers": raw_headers,
                "query_string": b"",
                "client": ("1.2.3.4", 1),
                "server": ("localhost", 8000),
                "scheme": "http",
            }
        )

    @staticmethod
    def _seed_user(db, status="active", user_id=None):
        import uuid

        from core.models import User

        if user_id is None:
            user_id = f"gw-user-{uuid.uuid4().hex[:10]}"
        user = User(
            id=user_id,
            email=f"{user_id}@test.com",
            first_name="G",
            last_name="W",
            role="user",
            status=status,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def _seed_key(
        db,
        plaintext,
        expires_at=None,
        revoked_at=None,
        is_active=True,
        rate_limit_per_minute=60,
        user_id=None,
    ):
        import uuid

        key = GatewayApiKey(
            id=f"gw-key-{uuid.uuid4().hex[:10]}",
            key_hash=hash_api_key(plaintext),
            key_prefix="atom_sk_abcd",
            name="t",
            user_id=user_id,
            is_active=is_active,
            expires_at=expires_at,
            revoked_at=revoked_at,
            rate_limit_per_minute=rate_limit_per_minute,
        )
        db.add(key)
        db.commit()
        db.refresh(key)
        return key

    @pytest.mark.asyncio
    async def test_expired_key_returns_401_not_500_with_sqlite_naive_datetime(self, db):
        """SQLite round-trips DateTime(timezone=True) as a NAIVE datetime; the
        aware ``datetime.now(timezone.utc)`` comparison used to raise TypeError
        (a 500), not the required 401."""
        user = self._seed_user(db)
        self._seed_key(
            db,
            "atom_sk_expiredkey001",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            user_id=user.id,
        )
        row = db.query(GatewayApiKey).first()
        assert row.expires_at.tzinfo is None  # naive as SQLite returns it
        with pytest.raises(HTTPException) as exc:
            await _resolve_api_key(
                "atom_sk_expiredkey001", db, self._request({"x-api-key": "atom_sk_expiredkey001"})
            )
        assert exc.value.status_code == 401
        assert "expired" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_active_key_resolves_identity(self, db):
        user = self._seed_user(db)
        self._seed_key(db, "atom_sk_goodkey000001", user_id=user.id)
        identity = await _resolve_api_key(
            "atom_sk_goodkey000001", db, self._request({"x-api-key": "atom_sk_goodkey000001"})
        )
        assert isinstance(identity, GatewayIdentity)
        assert identity.user_id == user.id
        assert identity.auth_method == "api_key"
        assert identity.rate_limit_per_minute == 60
        assert set(identity.to_audit()) == {"user_id", "tenant_id", "workspace_id", "auth_method", "api_key_id"}

    @pytest.mark.asyncio
    async def test_suspended_user_rejected_even_with_valid_key(self, db):
        user = self._seed_user(db, status="suspended")
        self._seed_key(db, "atom_sk_suspended001", user_id=user.id)
        with pytest.raises(HTTPException) as exc:
            await _resolve_api_key(
                "atom_sk_suspended001", db, self._request({"x-api-key": "atom_sk_suspended001"})
            )
        assert exc.value.status_code == 401
        assert "not active" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_pending_user_rejected_even_with_valid_key(self, db):
        user = self._seed_user(db, status="pending")
        self._seed_key(db, "atom_sk_pendingkey0001", user_id=user.id)
        with pytest.raises(HTTPException) as exc:
            await _resolve_api_key(
                "atom_sk_pendingkey0001", db, self._request({"x-api-key": "atom_sk_pendingkey0001"})
            )
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_revoked_key_rejected(self, db):
        user = self._seed_user(db)
        self._seed_key(db, "atom_sk_revokedkey001", revoked_at=datetime.now(timezone.utc), user_id=user.id)
        with pytest.raises(HTTPException) as exc:
            await _resolve_api_key(
                "atom_sk_revokedkey001", db, self._request({"x-api-key": "atom_sk_revokedkey001"})
            )
        assert exc.value.status_code == 401
        assert "revoked" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_inactive_key_rejected(self, db):
        user = self._seed_user(db)
        self._seed_key(db, "atom_sk_inactivekey01", is_active=False, user_id=user.id)
        with pytest.raises(HTTPException) as exc:
            await _resolve_api_key(
                "atom_sk_inactivekey01", db, self._request({"x-api-key": "atom_sk_inactivekey01"})
            )
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_unknown_key_rejected(self, db):
        user = self._seed_user(db)
        self._seed_key(db, "atom_sk_knownkey000001", user_id=user.id)
        with pytest.raises(HTTPException) as exc:
            await _resolve_api_key(
                "atom_sk_unknownkey001", db, self._request({"x-api-key": "atom_sk_unknownkey001"})
            )
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_rate_limit_enforced_per_key(self, db):
        user = self._seed_user(db)
        self._seed_key(db, "atom_sk_ratelimited01", rate_limit_per_minute=2, user_id=user.id)
        req = self._request({"x-api-key": "atom_sk_ratelimited01"})
        await _resolve_api_key("atom_sk_ratelimited01", db, req)
        await _resolve_api_key("atom_sk_ratelimited01", db, req)
        with pytest.raises(HTTPException) as exc:
            await _resolve_api_key("atom_sk_ratelimited01", db, req)
        assert exc.value.status_code == 429

    @pytest.mark.asyncio
    async def test_usage_count_bumped_on_success(self, db):
        user = self._seed_user(db)
        key = self._seed_key(db, "atom_sk_usagecount001", user_id=user.id)
        await _resolve_api_key(
            "atom_sk_usagecount001", db, self._request({"x-api-key": "atom_sk_usagecount001"})
        )
        db.refresh(key)
        assert key.total_requests == 1
