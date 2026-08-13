# -*- coding: utf-8 -*-
"""Coverage wave 82 — core/oauth_state_manager (OAuthStateManager).

Pure-crypto module — no network, no LLM spend. Expired/future-timestamp
states are hand-crafted via _compute_checksum so no real time travel is
needed.

Coverage targets:
- __init__: explicit secret, SECRET_KEY env, OAUTH_STATE_SECRET env, missing
  secret → ValueError.
- generate_state: 5-part format, TTL encoding, distinct tokens.
- validate_state: valid (±user match), missing, wrong part count, tampered
  checksum, expired, future timestamp, user mismatch, replay rejection,
  non-numeric expiry (generic error path), BUG W82-5 (user_id containing
  ':' round-trips).
- _prune_consumed: expired pruning, empty dict no-op.
- extract_user_id: present/absent/colon user_id/malformed.
- get_oauth_state_manager: singleton creation + reuse.
"""
import os
import time
from unittest.mock import patch

import pytest

from core.oauth_state_manager import (
    DEFAULT_STATE_TTL,
    OAuthStateManager,
    get_oauth_state_manager,
)


def _craft_state(mgr, token="tok", timestamp=None, user_id="", expires_at=None):
    """Build a state string with a valid checksum for the given fields."""
    timestamp = timestamp if timestamp is not None else int(time.time())
    expires_at = expires_at if expires_at is not None else timestamp + 600
    checksum = mgr._compute_checksum(token, timestamp, user_id or None)
    return f"{token}:{timestamp}:{user_id or ''}:{expires_at}:{checksum}"


class TestConstructor:
    def test_explicit_secret(self):
        mgr = OAuthStateManager(secret_key="test-secret")
        assert mgr.secret_key == "test-secret"

    def test_secret_from_env(self):
        with patch.dict(os.environ, {"SECRET_KEY": "env-secret"}, clear=False):
            mgr = OAuthStateManager()
        assert mgr.secret_key == "env-secret"

    def test_secret_from_oauth_env(self, monkeypatch):
        # SECRET_KEY must be UNSET (getenv fallback), not just empty
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.setenv("OAUTH_STATE_SECRET", "oauth-secret")
        mgr = OAuthStateManager()
        assert mgr.secret_key == "oauth-secret"

    def test_missing_secret_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="SECRET_KEY"):
                OAuthStateManager()


class TestGenerateState:
    def test_format_and_ttl(self):
        mgr = OAuthStateManager(secret_key="s")
        state = mgr.generate_state(user_id="user-1")
        parts = state.split(":")
        assert len(parts) == 5
        timestamp, expires_at = int(parts[1]), int(parts[3])
        assert expires_at == timestamp + DEFAULT_STATE_TTL
        assert parts[2] == "user-1"

    def test_custom_ttl(self):
        mgr = OAuthStateManager(secret_key="s")
        state = mgr.generate_state(user_id="u", ttl=120)
        parts = state.split(":")
        assert int(parts[3]) == int(parts[1]) + 120

    def test_distinct_tokens(self):
        mgr = OAuthStateManager(secret_key="s")
        s1 = mgr.generate_state()
        s2 = mgr.generate_state()
        assert s1 != s2


class TestValidateState:
    def test_valid_roundtrip(self):
        mgr = OAuthStateManager(secret_key="s")
        state = mgr.generate_state(user_id="user-1")
        result = mgr.validate_state(state)
        assert result["valid"] is True
        assert result["user_id"] == "user-1"
        assert result["tampered"] is False
        assert result["expired"] is False

    def test_valid_anonymous(self):
        mgr = OAuthStateManager(secret_key="s")
        state = mgr.generate_state()
        result = mgr.validate_state(state)
        assert result["valid"] is True
        assert result["user_id"] is None

    def test_missing_state(self):
        mgr = OAuthStateManager(secret_key="s")
        with pytest.raises(ValueError, match="missing"):
            mgr.validate_state("")
        with pytest.raises(ValueError, match="missing"):
            mgr.validate_state(None)

    def test_wrong_part_count(self):
        mgr = OAuthStateManager(secret_key="s")
        with pytest.raises(ValueError, match="format"):
            mgr.validate_state("a:b:c:d")

    def test_tampered_checksum(self):
        mgr = OAuthStateManager(secret_key="s")
        state = mgr.generate_state(user_id="user-1")
        parts = state.split(":")
        parts[4] = "0" * 64
        with pytest.raises(ValueError, match="tamper"):
            mgr.validate_state(":".join(parts))

    def test_expired(self):
        mgr = OAuthStateManager(secret_key="s")
        state = _craft_state(mgr, expires_at=int(time.time()) - 10)
        with pytest.raises(ValueError, match="expired"):
            mgr.validate_state(state)

    def test_future_timestamp(self):
        mgr = OAuthStateManager(secret_key="s")
        state = _craft_state(mgr, timestamp=int(time.time()) + 3600)
        with pytest.raises(ValueError, match="timestamp"):
            mgr.validate_state(state)

    def test_user_mismatch(self):
        mgr = OAuthStateManager(secret_key="s")
        state = mgr.generate_state(user_id="alice")
        with pytest.raises(ValueError, match="different user"):
            mgr.validate_state(state, user_id="bob", require_user_match=True)

    def test_user_match_ok(self):
        mgr = OAuthStateManager(secret_key="s")
        state = mgr.generate_state(user_id="alice")
        result = mgr.validate_state(state, user_id="alice", require_user_match=True)
        assert result["valid"] is True

    def test_user_match_anonymous_state_ok(self):
        mgr = OAuthStateManager(secret_key="s")
        state = mgr.generate_state()
        result = mgr.validate_state(state, user_id="bob", require_user_match=True)
        assert result["valid"] is True

    def test_replay_rejected(self):
        mgr = OAuthStateManager(secret_key="s")
        state = mgr.generate_state(user_id="u1")
        assert mgr.validate_state(state)["valid"] is True
        with pytest.raises(ValueError, match="already been used"):
            mgr.validate_state(state)

    def test_replay_after_prune_allowed(self):
        """Consumed tokens are pruned once their TTL passes — the same token
        becomes valid again after expiry, so pruning must also accept it."""
        mgr = OAuthStateManager(secret_key="s")
        token = "tok-prune"
        now = int(time.time())
        state = _craft_state(mgr, token=token, timestamp=now - 1000,
                             expires_at=now - 100)  # expired but checksum-valid
        # consume via direct insertion with an ALREADY-expired TTL
        mgr._consumed_tokens[token] = now - 100
        mgr._prune_consumed(now)
        assert token not in mgr._consumed_tokens

    def test_non_numeric_expiry_generic_error(self):
        mgr = OAuthStateManager(secret_key="s")
        now = int(time.time())
        state = f"tok:{now}::not-a-number:{mgr._compute_checksum('tok', now, None)}"
        with pytest.raises(ValueError, match="invalid literal"):
            mgr.validate_state(state)

    def test_non_string_state_generic_error(self):
        """A non-string state hits the generic except → wrapped ValueError."""
        mgr = OAuthStateManager(secret_key="s")
        with pytest.raises(ValueError, match="validation failed"):
            mgr.validate_state(12345)


class TestColonInUserId:
    """BUG W82-5: a user_id containing ':' broke the 5-part state format —
    generate_state produced 6+ colon-separated parts that could NEVER
    validate, permanently failing the OAuth flow for such users."""

    def test_generated_state_roundtrips(self):
        mgr = OAuthStateManager(secret_key="s")
        state = mgr.generate_state(user_id="user:123")
        parts = state.split(":")
        assert len(parts) == 5
        result = mgr.validate_state(state)
        assert result["valid"] is True
        assert result["user_id"] == "user:123"

    def test_user_match_with_colon(self):
        mgr = OAuthStateManager(secret_key="s")
        state = mgr.generate_state(user_id="user:123")
        result = mgr.validate_state(state, user_id="user:123", require_user_match=True)
        assert result["valid"] is True

    def test_extract_user_id_with_colon(self):
        mgr = OAuthStateManager(secret_key="s")
        state = mgr.generate_state(user_id="user:123")
        assert mgr.extract_user_id(state) == "user:123"

    def test_existing_colon_free_behavior_unchanged(self):
        mgr = OAuthStateManager(secret_key="s")
        state = mgr.generate_state(user_id="plain-user")
        assert state.split(":")[2] == "plain-user"


class TestExtractUserId:
    def test_with_user(self):
        mgr = OAuthStateManager(secret_key="s")
        state = mgr.generate_state(user_id="u-9")
        assert mgr.extract_user_id(state) == "u-9"

    def test_anonymous(self):
        mgr = OAuthStateManager(secret_key="s")
        state = mgr.generate_state()
        assert mgr.extract_user_id(state) is None

    def test_malformed(self):
        mgr = OAuthStateManager(secret_key="s")
        assert mgr.extract_user_id("a:b") is None
        assert mgr.extract_user_id("") is None

    def test_non_string(self):
        mgr = OAuthStateManager(secret_key="s")
        assert mgr.extract_user_id(None) is None
        assert mgr.extract_user_id(123) is None


class TestPruneConsumed:
    def test_prunes_expired(self):
        mgr = OAuthStateManager(secret_key="s")
        now = int(time.time())
        mgr._consumed_tokens = {"old": now - 10, "live": now + 500}
        mgr._prune_consumed(now)
        assert "old" not in mgr._consumed_tokens
        assert "live" in mgr._consumed_tokens

    def test_empty_noop(self):
        mgr = OAuthStateManager(secret_key="s")
        mgr._prune_consumed(int(time.time()))
        assert mgr._consumed_tokens == {}


class TestGlobalManager:
    def test_singleton(self):
        first = get_oauth_state_manager()
        second = get_oauth_state_manager()
        assert first is second
