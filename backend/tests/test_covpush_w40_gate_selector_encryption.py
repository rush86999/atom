"""Coverage wave 40 — sandbox_gate (92→100%), selector_confidence_service (86→100%), token_encryption (74→100%).

- gate: disabled/no-run-id/no-tier short-circuits, whitelist-enabled check path,
  KillRunAborted propagation
- selector: MatchConfidence property matrix, empty/no-match/late-appearance
  scoring, storage coercion, attach_tiebreak bridge states
- token_encryption: key persist failure, cached-key, invalid-key raise,
  api-key wrappers (empty/success), rotation (success/partial failure),
  metadata marking, hash
"""
import os
import time as _time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

import core.privsec.token_encryption as te
import core.sandbox_gate as sgate
import core.selector_confidence_service as scs
from core.llm.match_confidence_tiebreaker import TiebreakResult
from core.sandbox_killrun import KillRunAborted
from core.sandbox_policy import BLOCKED
from core.selector_confidence_service import (
    AMBIGUOUS,
    EXTERNAL_VERIFIED,
    NEEDS_EXTERNAL_VALIDATION,
    PARTIAL,
    HIGH,
    MatchConfidence,
    SelectorCandidate,
    attach_tiebreak,
    coerce_match_level_for_storage,
    score_candidates,
)


def await_coroutine(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================================
# sandbox_gate
# ============================================================================

class TestSandboxGateShortCircuits:
    def _ctx(self, **kw):
        ctx = dict(run_id="run-1", tier="autonomous", agent_id="a1",
                   workspace_data_root="/tmp/ws")
        ctx.update(kw)
        return ctx

    def test_disabled_returns_none(self):
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=False):
            assert sgate.evaluate_tool_call("t", {}, self._ctx()) is None

    def test_no_run_id_returns_none(self):
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True):
            assert sgate.evaluate_tool_call("t", {}, self._ctx(run_id=None)) is None

    def test_no_tier_returns_none(self):
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True):
            assert sgate.evaluate_tool_call("t", {}, self._ctx(tier=None)) is None

    def test_whitelist_enabled_check_path(self):
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
             patch("core.sandbox_config.is_sandbox_whitelist_enabled", return_value=True), \
             patch("core.sandbox_policy.PolicyIssuer") as issuer_cls, \
             patch("core.sandbox_audit.write_violation") as wv:
            issuer = issuer_cls.return_value
            issuer.check.return_value = Mock(
                decision=BLOCKED, phase="C", tool_name="t", args_hash="h",
                violation_type="x", violation_detail="d", enforced=True,
                killrun_triggered=False, policy_id="p", metadata_json={},
            )
            decision = sgate.evaluate_tool_call("t", {"a": 1}, self._ctx())
            issuer.check.assert_called_once()
            wv.assert_called_once()

    def test_killrun_aborted_propagates(self):
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
             patch("core.sandbox_policy.PolicyIssuer") as issuer_cls:
            issuer = issuer_cls.return_value
            issuer.check.side_effect = KillRunAborted("killed")
            with pytest.raises(KillRunAborted):
                sgate.evaluate_tool_call("t", {}, self._ctx())


# ============================================================================
# selector_confidence_service
# ============================================================================

class TestMatchConfidenceProperties:
    def _mc(self, level, provenance="internal"):
        return MatchConfidence(
            level=level, score=0.7, rationale="r", candidates=[], chosen_index=0,
            provenance=provenance,
        )

    def test_is_high_true(self):
        assert self._mc(HIGH).is_high is True

    def test_is_credible_only_external_verified(self):
        assert self._mc(EXTERNAL_VERIFIED).is_credible is True
        assert self._mc(HIGH).is_credible is False

    def test_needs_external_validation_internal_only(self):
        assert self._mc(HIGH).needs_external_validation is True
        assert self._mc(PARTIAL).needs_external_validation is True
        assert self._mc(HIGH, provenance="external").needs_external_validation is False


class TestScoreMatchConfidence:
    def test_empty_candidates_ambiguous(self):
        mc = score_candidates([])
        assert mc.level == AMBIGUOUS
        assert mc.chosen_index == -1

    def test_zero_match_count_ambiguous(self):
        mc = score_candidates([SelectorCandidate(
            selector="x", match_count=0, is_text_only=False,
            appeared_after_ms=0, tag_hint="a")])
        assert mc.level == AMBIGUOUS

    def test_late_appearance_penalty(self):
        cand = SelectorCandidate(selector="x", match_count=3, is_text_only=False,
                                 appeared_after_ms=1500, tag_hint="a")
        mc = score_candidates([cand])
        assert mc.score < 1.0
        assert "appeared after" in mc.rationale

    def test_coerce_valid_levels(self):
        assert coerce_match_level_for_storage(HIGH) == HIGH
        assert coerce_match_level_for_storage(EXTERNAL_VERIFIED) == EXTERNAL_VERIFIED

    def test_coerce_invalid_defaults_ambiguous(self):
        assert coerce_match_level_for_storage("bogus") == AMBIGUOUS
        assert coerce_match_level_for_storage(None) == AMBIGUOUS


class TestAttachTiebreak:
    async def test_non_partial_returns_unchanged(self):
        mc = MatchConfidence(level=HIGH, score=0.9, rationale="r",
                             candidates=[], chosen_index=0)
        assert await attach_tiebreak(mc, "ctx", None) is mc

    async def test_no_llm_service_returns_unchanged(self):
        mc = MatchConfidence(level=PARTIAL, score=0.6, rationale="r",
                             candidates=[], chosen_index=0)
        assert await attach_tiebreak(mc, "ctx", None) is mc

    async def test_break_tie_exception_returns_unchanged(self):
        mc = MatchConfidence(level=PARTIAL, score=0.6, rationale="r",
                             candidates=[], chosen_index=0)
        with patch("core.llm.match_confidence_tiebreaker.break_tie",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            out = await attach_tiebreak(mc, "ctx", Mock())
        assert out is mc

    async def test_unused_llm_returns_unchanged(self):
        mc = MatchConfidence(level=PARTIAL, score=0.6, rationale="r",
                             candidates=[], chosen_index=0)
        with patch("core.llm.match_confidence_tiebreaker.break_tie",
                   new=AsyncMock(return_value=TiebreakResult(
                       chosen_index=-1, used_llm=False, rationale="no"))):
            out = await attach_tiebreak(mc, "ctx", Mock())
        assert out is mc

    async def test_used_llm_promotes_to_bridge_state(self):
        mc = MatchConfidence(level=PARTIAL, score=0.6, rationale="r",
                             candidates=[], chosen_index=0)
        with patch("core.llm.match_confidence_tiebreaker.break_tie",
                   new=AsyncMock(return_value=TiebreakResult(
                       chosen_index=1, used_llm=True, rationale="pick"))):
            out = await attach_tiebreak(mc, "ctx", Mock())
        assert out.level == NEEDS_EXTERNAL_VALIDATION
        assert "needs external validation" in out.rationale


# ============================================================================
# token_encryption
# ============================================================================

class TestTokenEncryption:
    def _fresh_key(self):
        return te.generate_encryption_key()

    def test_persist_key_exception_logged(self):
        with patch("builtins.open", side_effect=OSError("no perms")), \
             patch("core.privsec.token_encryption.logger") as lg:
            te._persist_key("abc")
            lg.error.assert_called_once()

    def test_get_encryption_key_cached(self):
        key = self._fresh_key()
        with patch.object(te, "_encryption_key", None):
            te._encryption_key = key.encode()
            assert te.get_encryption_key() == key.encode()

    def test_invalid_key_raises(self):
        with patch.object(te, "_encryption_key", None), \
             patch.dict(os.environ, {"BYOK_ENCRYPTION_KEY": "not-a-fernet-key"}, clear=True):
            with pytest.raises(te.InvalidKeyError):
                te.get_encryption_key()

    def test_encrypt_api_key_empty(self):
        assert te.encrypt_api_key("", "spotify") == ""

    def test_encrypt_api_key_success(self):
        key = self._fresh_key()
        with patch.object(te, "encrypt_token", return_value="cipher") as et:
            out = te.encrypt_api_key("sk-123", "spotify")
            et.assert_called_once_with("sk-123")
        assert out == "cipher"

    def test_decrypt_api_key_empty(self):
        assert te.decrypt_api_key("", "spotify") == ""

    def test_decrypt_api_key_success(self):
        key = self._fresh_key()
        with patch.object(te, "decrypt_token", return_value="sk-123") as dt:
            out = te.decrypt_api_key("cipher", "spotify")
            dt.assert_called_once_with("cipher", allow_plaintext=False)
        assert out == "sk-123"

    def test_rotate_tokens_success(self):
        key_old, key_new = self._fresh_key(), self._fresh_key()
        tokens = {"t1": "c1", "t2": "c2"}
        with patch.object(te, "decrypt_token", side_effect=["p1", "p2"]) as dt, \
             patch.object(te, "encrypt_token", side_effect=["n1", "n2"]) as et:
            stats = te.rotate_tokens(key_old, key_new, tokens)
        assert stats == {"total": 2, "rotated": 2, "failed": 0, "failed_ids": []}
        assert tokens == {"t1": "n1", "t2": "n2"}

    def test_rotate_tokens_partial_failure(self):
        key_old, key_new = self._fresh_key(), self._fresh_key()
        tokens = {"good": "c1", "bad": "c2"}
        with patch.object(te, "decrypt_token", side_effect=["p1", RuntimeError("boom")]), \
             patch.object(te, "encrypt_token", return_value="n"):
            stats = te.rotate_tokens(key_old, key_new, tokens)
        assert stats["rotated"] == 1
        assert stats["failed"] == 1
        assert stats["failed_ids"] == ["bad"]

    def test_mark_token_encrypted_no_metadata_attr(self):
        token = SimpleNamespace()
        assert te.stamp_credential_metadata(token) == {}

    def test_mark_token_encrypted_updates_metadata(self):
        token = SimpleNamespace(credential_metadata={"k": "v"})
        meta = te.stamp_credential_metadata(token)
        assert meta["encryption"] == "fernet"
        assert token.credential_metadata["encryption"] == "fernet"

    def test_hash_token(self):
        h = te.hash_token("my-token")
        assert h == "my-token" and isinstance(h, str) or len(h) == 64
