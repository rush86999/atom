"""Coverage wave 41 — tool_outcome_verifier (34% → 100%) + agent_context_resolver (91% → 100%).

- verifier: None/dict/JSON-string/python-repr/plain/other returns, tri-state
  verified flags, evidence normalization, success inference, storage coercion
- resolver: legacy-row workspace/tenant backfill, exception tolerance in
  system-default-agent resolution
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.tool_outcome_verifier import (
    FAILED_VERIFICATION,
    UNVERIFIED,
    VERIFIED,
    VerifiedOutcome,
    coerce_verified_for_storage,
    parse_tool_outcome,
)


class TestParseToolOutcome:
    def test_none_returns_unverified_false(self):
        out = parse_tool_outcome(None)
        assert out.kind == UNVERIFIED and out.success is False
        assert out.raw is None

    def test_dict_verified_true(self):
        out = parse_tool_outcome({"success": True, "verified": True, "evidence": "stat'd"})
        assert out.kind == VERIFIED
        assert out.is_verified is True
        assert out.evidence == "stat'd"

    def test_dict_verified_false(self):
        out = parse_tool_outcome({"success": True, "verified": False})
        assert out.kind == FAILED_VERIFICATION

    def test_dict_no_verified_key_unverified(self):
        out = parse_tool_outcome({"success": True})
        assert out.kind == UNVERIFIED

    def test_dict_success_false(self):
        out = parse_tool_outcome({"success": False})
        assert out.success is False

    def test_dict_evidence_list_jsonified(self):
        out = parse_tool_outcome({"success": True, "evidence": [1, 2]})
        assert json.loads(out.evidence) == [1, 2]

    def test_dict_evidence_dict_jsonified(self):
        out = parse_tool_outcome({"success": True, "evidence": {"a": 1}})
        assert json.loads(out.evidence) == {"a": 1}

    def test_dict_verification_evidence_fallback(self):
        out = parse_tool_outcome({"success": True, "verification_evidence": "via"})
        assert out.evidence == "via"

    def test_json_string_dict(self):
        out = parse_tool_outcome('{"success": true, "verified": true}')
        assert out.kind == VERIFIED and out.success is True

    def test_python_repr_string_normalized(self):
        out = parse_tool_outcome("{'success': True, 'verified': False}")
        assert out.kind == FAILED_VERIFICATION
        assert out.success is True

    def test_python_repr_none_value(self):
        out = parse_tool_outcome("{'success': True, 'evidence': None}")
        assert out.kind == UNVERIFIED

    def test_plain_string_unverified(self):
        out = parse_tool_outcome("just a message")
        assert out.kind == UNVERIFIED
        assert out.success is True
        assert out.raw == "just a message"

    def test_empty_string_success_false(self):
        out = parse_tool_outcome("")
        assert out.success is False

    def test_non_string_object(self):
        out = parse_tool_outcome(42)
        assert out.kind == UNVERIFIED
        assert out.raw == "42"

    def test_never_raises_on_bad_json(self):
        out = parse_tool_outcome("not json {unbalanced")
        assert out.kind == UNVERIFIED

    def test_python_repr_unparseable_after_normalize(self):
        # trailing comma is valid Python, invalid JSON — both parses fail
        out = parse_tool_outcome("{'success': True,}")
        assert out.kind == UNVERIFIED
        assert out.success is True  # raw string truthy


class TestCoerceForStorage:
    def test_valid_states_pass_through(self):
        for v in (VERIFIED, UNVERIFIED, FAILED_VERIFICATION):
            assert coerce_verified_for_storage(v) == v

    def test_invalid_defaults_unverified(self):
        assert coerce_verified_for_storage("bogus") == UNVERIFIED
        assert coerce_verified_for_storage(None) == UNVERIFIED


class TestVerifiedOutcomeProperty:
    def test_is_verified(self):
        assert VerifiedOutcome(kind=VERIFIED, success=True).is_verified is True
        assert VerifiedOutcome(kind=UNVERIFIED, success=True).is_verified is False


class TestAgentContextResolverRemaining:
    def _resolver(self, db):
        from core.agent_context_resolver import AgentContextResolver
        return AgentContextResolver(db)

    def test_heals_legacy_agent_scope(self):
        agent = SimpleNamespace(
            id="a1", workspace_id=None, tenant_id=None,
        )
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = agent
        resolver = self._resolver(db)
        from core.personal_scope import PERSONAL_TENANT_ID, PERSONAL_WORKSPACE_ID
        out = resolver._get_or_create_system_default()
        assert out is agent
        assert agent.workspace_id == PERSONAL_WORKSPACE_ID
        assert agent.tenant_id == PERSONAL_TENANT_ID
        db.commit.assert_called_once()

    def test_exception_returns_none(self):
        db = Mock()
        db.query.side_effect = RuntimeError("db down")
        resolver = self._resolver(db)
        assert resolver._get_or_create_system_default() is None
