"""TDD bug-hunt + coverage tests for core/atom_meta_agent.py.

Focuses on UNcovered regions where undetected bugs hide:
- _get_communication_instruction: UnboundLocalError in finally when
  SessionLocal() raises (db never bound)
- module-level _is_error_observation heuristics
- module-level _meta_agent_sandbox_check gating paths
"""

import sys
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

import core.atom_meta_agent as ama
from core.atom_meta_agent import (
    AtomMetaAgent,
    _is_error_observation,
    _meta_agent_sandbox_check,
)


# ---------------------------------------------------------------------------
# BUG 1 (PRIMARY): _get_communication_instruction raises UnboundLocalError
# in finally when SessionLocal() itself raises.
# ---------------------------------------------------------------------------
def test_get_communication_instruction_sessionlocal_failure_does_not_raise():
    """BUG: _get_communication_instruction does `db = SessionLocal()` inside a
    try, but the `finally: db.close()` runs unconditionally. If SessionLocal()
    raises (e.g. DB down / misconfig), `db` is never bound and the finally
    raises UnboundLocalError, masking the original error and crashing the
    caller (the ReAct prompt builder) instead of returning ""."""

    agent = AtomMetaAgent.__new__(AtomMetaAgent)
    agent.user = None  # forces context.get("user_id") path

    with patch.object(ama, "SessionLocal", side_effect=RuntimeError("db unavailable")):
        # Must return "" (graceful degradation), NOT raise UnboundLocalError.
        result = agent._get_communication_instruction({"user_id": "u-1"})
    assert result == ""


def test_get_communication_instruction_returns_style_when_configured():
    """Coverage: the happy path — user has personalization enabled."""
    agent = AtomMetaAgent.__new__(AtomMetaAgent)
    agent.user = None

    fake_user = MagicMock()
    fake_user.metadata_json = {
        "communication_style": {
            "enable_personalization": True,
            "style_guide": "Be concise.",
        }
    }
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = fake_user

    with patch.object(ama, "SessionLocal", return_value=fake_db):
        result = agent._get_communication_instruction({"user_id": "u-1"})
    assert "Be concise." in result
    fake_db.close.assert_called_once()


def test_get_communication_instruction_no_user_id_returns_empty():
    """No user_id in context and no self.user → empty string, no DB call."""
    agent = AtomMetaAgent.__new__(AtomMetaAgent)
    agent.user = None
    with patch.object(ama, "SessionLocal") as sess:
        assert agent._get_communication_instruction({}) == ""
        sess.assert_not_called()


def test_get_communication_instruction_query_exception_returns_empty():
    """Coverage: a DB query error is swallowed and returns "" (db still closed)."""
    agent = AtomMetaAgent.__new__(AtomMetaAgent)
    agent.user = None
    fake_db = MagicMock()
    fake_db.query.side_effect = RuntimeError("query failed")
    with patch.object(ama, "SessionLocal", return_value=fake_db):
        assert agent._get_communication_instruction({"user_id": "u-1"}) == ""
    fake_db.close.assert_called_once()


def test_get_communication_instruction_personalization_disabled():
    """Coverage: user exists but personalization off → empty string."""
    agent = AtomMetaAgent.__new__(AtomMetaAgent)
    agent.user = None
    fake_user = MagicMock()
    fake_user.metadata_json = {"communication_style": {"enable_personalization": False}}
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = fake_user
    with patch.object(ama, "SessionLocal", return_value=fake_db):
        assert agent._get_communication_instruction({"user_id": "u-1"}) == ""


def test_get_communication_instruction_user_with_no_metadata():
    """Coverage: user exists but metadata_json is None → empty string."""
    agent = AtomMetaAgent.__new__(AtomMetaAgent)
    agent.user = None
    fake_user = MagicMock()
    fake_user.metadata_json = None
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = fake_user
    with patch.object(ama, "SessionLocal", return_value=fake_db):
        assert agent._get_communication_instruction({"user_id": "u-1"}) == ""


# ---------------------------------------------------------------------------
# Coverage: _is_error_observation (module-level helper)
# ---------------------------------------------------------------------------
def test_is_error_observation_none_is_false():
    assert _is_error_observation(None) is False


def test_is_error_observation_tool_error_marker():
    assert _is_error_observation("Tool error. Please retry.") is True


def test_is_error_observation_governance_blocked():
    assert _is_error_observation("Governance blocked: delete") is True


def test_is_error_observation_sandbox():
    assert _is_error_observation("Sandbox blocked: fs write") is True


def test_is_error_observation_rejected():
    assert _is_error_observation("Action was rejected or timed out.") is True


def test_is_error_observation_normal_result_is_false():
    """A normal result that merely contains 'error' inside JSON must NOT match
    (avoids false positives — the heuristic anchors on canonical phrasings)."""
    assert _is_error_observation('{"error_code": 0, "ok": true}') is False


def test_is_error_observation_empty_string_is_false():
    assert _is_error_observation("") is False


def test_is_error_observation_non_string():
    """Non-string observations are stringified first."""
    assert _is_error_observation({"msg": "tool error."}) is True
    assert _is_error_observation(42) is False


# ---------------------------------------------------------------------------
# Coverage: _meta_agent_sandbox_check gating (returns None when disabled or
# missing run_id / tier — fail-open behavior).
# ---------------------------------------------------------------------------
def test_meta_agent_sandbox_check_disabled_returns_none():
    """When the sandbox master switch is off, the check is a no-op (None)."""
    # Patch the real module directly: the source resolves sandbox_config via
    # `from core import sandbox_config` (parent-package attribute), so
    # replacing sys.modules only works if the module was never imported
    # earlier in the process (order-dependent under xdist).
    from core import sandbox_config as _sandbox_config
    with patch.object(_sandbox_config, "is_sandbox_enabled", return_value=False):
        result = _meta_agent_sandbox_check("read_file", {}, {"run_id": "r1", "tier": "executive"})
    assert result is None


def test_meta_agent_sandbox_check_no_run_id_returns_none():
    """No run_id in context → no policy in scope → None (fail open)."""
    fake_sandbox_config = MagicMock()
    fake_sandbox_config.is_sandbox_enabled.return_value = True
    with patch.dict("sys.modules", {"core.sandbox_config": fake_sandbox_config}):
        result = _meta_agent_sandbox_check("read_file", {}, {"tier": "executive"})
    assert result is None


def test_meta_agent_sandbox_check_no_tier_returns_none():
    """No tier in context → no policy in scope → None (fail open)."""
    fake_sandbox_config = MagicMock()
    fake_sandbox_config.is_sandbox_enabled.return_value = True
    with patch.dict("sys.modules", {"core.sandbox_config": fake_sandbox_config}):
        result = _meta_agent_sandbox_check("read_file", {}, {"run_id": "r1"})
    assert result is None


def test_meta_agent_sandbox_check_broken_policy_fails_open():
    """A broken policy issuer must NEVER raise and must NEVER block the call —
    it fails open by returning an ALLOWED-style SandboxDecision carrying the
    error in metadata_json.error (per the documented contract). This guards
    the fail-open behavior so a buggy sandbox can't deadlock the agent."""
    fake_sandbox_config = MagicMock()
    fake_sandbox_config.is_sandbox_enabled.return_value = True

    # A real ALLOWED sentinel + SandboxDecision ctor the function can construct.
    ALLOWED = "allowed"
    constructed = {}

    class SandboxDecision:
        def __init__(self, decision=None, phase=None, tool_name=None,
                     metadata_json=None, **kw):
            constructed["decision"] = decision
            constructed["metadata_json"] = metadata_json
            self.is_allowed = decision == ALLOWED
            self.requires_review = False

    fake_policy_issuer = MagicMock()
    fake_policy_issuer.issue.side_effect = RuntimeError("policy engine down")

    fake_policy_module = MagicMock()
    fake_policy_module.PolicyIssuer = MagicMock(return_value=fake_policy_issuer)
    fake_policy_module.SandboxDecision = SandboxDecision
    fake_policy_module.ALLOWED = ALLOWED

    fake_killrun_module = MagicMock()
    fake_killrun_module.KillRunAborted = type("KillRunAborted", (Exception,), {})

    with patch.dict("sys.modules", {
        "core.sandbox_config": fake_sandbox_config,
        "core.sandbox_policy": fake_policy_module,
        "core.sandbox_audit": MagicMock(write_violation=MagicMock()),
        "core.sandbox_killrun": fake_killrun_module,
    }):
        result = _meta_agent_sandbox_check(
            "read_file", {}, {"run_id": "r1", "tier": "executive"}
        )

    # Fail-open: decision is ALLOWED with the error captured in metadata.
    assert constructed["decision"] == ALLOWED
    assert "policy engine down" in constructed["metadata_json"]["error"]
    assert result is not None
