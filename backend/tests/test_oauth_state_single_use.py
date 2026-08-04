"""
Tests for OAuth state single-use / replay protection (core/oauth_state_manager.py).

The module advertises "Single-use only (consumed on validation)" but validate_state
previously never recorded consumed tokens — so the same state validated successfully
on every call within its TTL, opening a CSRF replay window on the Slack OAuth path.
"""

import pytest

from core.oauth_state_manager import OAuthStateManager


@pytest.fixture
def mgr():
    return OAuthStateManager(secret_key="test-secret-key-for-oauth-state")


class TestOAuthStateSingleUse:
    def test_state_cannot_be_validated_twice(self, mgr):
        """A state consumed on first validation MUST be rejected on replay."""
        state = mgr.generate_state(user_id="user-A")
        # First use: valid.
        result = mgr.validate_state(state, user_id="user-A", require_user_match=True)
        assert result["valid"] is True

        # Replay: must be rejected (consumed).
        with pytest.raises(ValueError, match="(?i)consumed|reused|replay|already been used"):
            mgr.validate_state(state, user_id="user-A", require_user_match=True)

    def test_distinct_states_each_validate_once(self, mgr):
        """Two different states each validate on their first use."""
        s1 = mgr.generate_state(user_id="u1")
        s2 = mgr.generate_state(user_id="u1")
        assert mgr.validate_state(s1)["valid"] is True
        assert mgr.validate_state(s2)["valid"] is True  # different token, not consumed

    def test_consumed_state_rejected_even_without_user_match(self, mgr):
        """Consumption is tracked by token, independent of the user-match flag."""
        state = mgr.generate_state(user_id="u1")
        mgr.validate_state(state)  # consume (no user match required)
        with pytest.raises(ValueError):
            mgr.validate_state(state)  # replay must still be rejected
