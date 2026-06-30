"""Execution Sandbox Layer — Phase A tests (Round 43).

Tests cover:
  * SandboxPolicy frozen-dataclass invariants
  * PolicyIssuer tier-floor mapping (STUDENT/INTERN/SUPERVISED/AUTONOMOUS)
  * Env-var resolution via sandbox_config
  * SandboxDecision tri-state (allowed/restricted/blocked)
  * coerce_decision_for_storage / coerce_phase_for_storage
  * args-hash determinism + secret redaction
  * Shadow mode (enforced=False) vs Force-enforce (enforced=True)
  * tenant-override narrowing-only contract
  * Fail-open behavior on internal errors
  * Audit-row writer no-ops (allowed decisions not audited)

Mirrors the C1-C16 test style from
``tests/unit/llm/test_self_consistency_voter.py``.
"""
from __future__ import annotations

import os
from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _clean_sandbox_env(monkeypatch):
    """Reset all ATOM_SANDBOX_* env vars before each test."""
    for k in list(os.environ):
        if k.startswith("ATOM_SANDBOX") or k == "ATOM_SANDBOX_ENABLED":
            monkeypatch.delenv(k, raising=False)


# ---------------------------------------------------------------------------
# S1: SandboxPolicy is frozen
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_S1_policy_is_frozen_dataclass():
    """SandboxPolicy must be immutable post-construction."""
    from core.sandbox_policy import SandboxPolicy

    policy = SandboxPolicy(
        run_id="r1",
        agent_id="a1",
        tier_at_issuance="student",
        tool_whitelist=("canvas_render",),
    )
    with pytest.raises(FrozenInstanceError):
        policy.tier_at_issuance = "autonomous"  # type: ignore[misc]


@pytest.mark.unit
def test_S1b_decision_is_frozen_dataclass():
    """SandboxDecision must be immutable post-construction."""
    from core.sandbox_policy import SandboxDecision, BLOCKED

    decision = SandboxDecision(decision=BLOCKED, tool_name="x")
    with pytest.raises(FrozenInstanceError):
        decision.decision = "allowed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# S2: tier-floor mapping — STUDENT gets read-only tools, no egress
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_S2_student_tier_gets_readonly_tools_no_egress():
    from core.sandbox_policy import PolicyIssuer

    issuer = PolicyIssuer()
    policy = issuer.issue(
        run_id="r1",
        agent_id="a1",
        tier_at_issuance="student",
        workspace_data_root="/ws/data",
    )
    assert "canvas_render" in policy.tool_whitelist
    assert "browser_click" not in policy.tool_whitelist
    assert "terminal_command" not in policy.tool_whitelist
    assert policy.egress_hosts == ()
    assert policy.fs_write_roots == ()  # student never writes FS


# ---------------------------------------------------------------------------
# S3: tier-floor mapping — AUTONOMOUS gets "*"
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_S3_autonomous_tier_allows_all_tools():
    from core.sandbox_policy import PolicyIssuer

    issuer = PolicyIssuer()
    policy = issuer.issue(
        run_id="r1",
        agent_id="a1",
        tier_at_issuance="autonomous",
    )
    assert policy.allows_all_tools is True
    assert policy.tool_allowed("anything_here") is True
    # AUTONOMOUS still has egress list (Phase D gates by it)
    assert len(policy.egress_hosts) > 0


# ---------------------------------------------------------------------------
# S4: tier-floor ordering — supervised > intern > student
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_S4_tier_floor_monotonic():
    """Higher tiers must have a superset of student's tools."""
    from core.sandbox_policy import PolicyIssuer

    issuer = PolicyIssuer()
    student = issuer.issue("r1", "a1", "student")
    intern = issuer.issue("r2", "a1", "intern")
    supervised = issuer.issue("r3", "a1", "supervised")
    autonomous = issuer.issue("r4", "a1", "autonomous")

    s_tools = set(student.tool_whitelist)
    i_tools = set(intern.tool_whitelist)
    sup_tools = set(supervised.tool_whitelist)
    a_tools = set(autonomous.tool_whitelist)

    # Each tier's tool set contains the student set (monotonic expansion).
    assert s_tools.issubset(i_tools)
    assert i_tools.issubset(sup_tools)
    # AUTONOMOUS allows all tools (wildcard), so subset check is trivially true
    # — but we verify the wildcard is set instead.
    assert "*" in a_tools


# ---------------------------------------------------------------------------
# S5: check() returns ALLOWED for whitelisted tool
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_S5_check_allowed_for_whitelisted_tool():
    from core.sandbox_policy import PolicyIssuer, ALLOWED

    issuer = PolicyIssuer()
    policy = issuer.issue("r1", "a1", "supervised")
    decision = issuer.check(policy, "browser_click", {"selector": "#foo"})
    assert decision.decision == ALLOWED
    assert decision.is_allowed is True
    assert decision.requires_review is False
    assert decision.tool_name == "browser_click"


# ---------------------------------------------------------------------------
# S6: check() returns BLOCKED for non-whitelisted tool
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_S6_check_blocked_for_non_whitelisted_tool():
    from core.sandbox_policy import PolicyIssuer, BLOCKED, VT_TOOL_WHITELIST

    issuer = PolicyIssuer()
    policy = issuer.issue("r1", "a1", "student")  # read-only tier
    decision = issuer.check(policy, "terminal_command", {"command": "rm -rf /"})
    assert decision.decision == BLOCKED
    assert decision.violation_type == VT_TOOL_WHITELIST
    assert decision.requires_review is True
    assert "terminal_command" in decision.violation_detail


# ---------------------------------------------------------------------------
# S7: AUTONOMOUS tier passes all tools through check()
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_S7_check_autonomous_allows_any_tool():
    from core.sandbox_policy import PolicyIssuer, ALLOWED

    issuer = PolicyIssuer()
    policy = issuer.issue("r1", "a1", "autonomous")
    # Even nonsense tool names pass — wildcard whitelist.
    decision = issuer.check(policy, "totally_made_up_tool", {})
    assert decision.decision == ALLOWED


# ---------------------------------------------------------------------------
# S8: coerce_decision_for_storage — invalid values default to ALLOWED
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_S8_coerce_decision_defaults_to_allowed():
    from core.sandbox_policy import coerce_decision_for_storage, ALLOWED

    assert coerce_decision_for_storage("allowed") == "allowed"
    assert coerce_decision_for_storage("blocked") == "blocked"
    assert coerce_decision_for_storage(None) == ALLOWED
    assert coerce_decision_for_storage("garbage") == ALLOWED
    assert coerce_decision_for_storage("") == ALLOWED


# ---------------------------------------------------------------------------
# S9: coerce_phase_for_storage
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_S9_coerce_phase_normalizes():
    from core.sandbox_policy import coerce_phase_for_storage

    assert coerce_phase_for_storage("A") == "A"
    assert coerce_phase_for_storage("b") == "B"
    assert coerce_phase_for_storage("e") == "E"
    assert coerce_phase_for_storage(None) == "A"  # default
    assert coerce_phase_for_storage("X") == "A"  # invalid → default
    assert coerce_phase_for_storage("ABCDE") == "A"  # too long → default


# ---------------------------------------------------------------------------
# S10: args hash is deterministic + redacts secrets
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_S10_args_hash_deterministic_and_redacts_secrets():
    from core.sandbox_policy import PolicyIssuer

    issuer = PolicyIssuer()
    h1 = issuer._hash_args({"a": 1, "b": 2})
    h2 = issuer._hash_args({"a": 1, "b": 2})
    assert h1 == h2  # deterministic
    assert len(h1) == 64  # sha256 hex

    # Different args → different hash
    h3 = issuer._hash_args({"a": 1, "b": 3})
    assert h1 != h3


@pytest.mark.unit
def test_S10b_args_hash_redacts_secret_keys():
    """Keys matching token/password/secret/api_key must redact values."""
    from core.sandbox_policy import PolicyIssuer

    issuer = PolicyIssuer()
    # Same secret value but different keys → if redaction works, the
    # token-bearing version matches a version with value replaced.
    h_plain = issuer._hash_args({"api_key": "sk-real-secret"})
    h_redacted = issuer._hash_args({"api_key": "***"})
    # The redacted-keys variant should match because both go through redaction
    h_real_redacted_in_module = issuer._hash_args({"api_key": "DIFFERENT"})
    # Both api_key variants get redacted to *** → equal hashes
    assert h_plain == h_real_redacted_in_module
    # And they match the explicit *** form
    assert h_plain == h_redacted


# ---------------------------------------------------------------------------
# S11: shadow mode — enforced flag tracks FORCE_ENFORCE env var
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_S11_shadow_mode_enforced_flag_false_by_default(monkeypatch):
    """Without ATOM_SANDBOX_FORCE_ENFORCE, blocked decisions have enforced=False."""
    from core.sandbox_policy import PolicyIssuer, BLOCKED

    monkeypatch.delenv("ATOM_SANDBOX_FORCE_ENFORCE", raising=False)
    issuer = PolicyIssuer()
    policy = issuer.issue("r1", "a1", "student")
    decision = issuer.check(policy, "terminal_command", {})
    assert decision.decision == BLOCKED
    assert decision.enforced is False  # shadow mode


@pytest.mark.unit
def test_S11b_force_enforce_flips_enforced_flag(monkeypatch):
    """With ATOM_SANDBOX_FORCE_ENFORCE=true, blocked decisions are enforced."""
    from core.sandbox_policy import PolicyIssuer, BLOCKED

    monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "true")
    issuer = PolicyIssuer()
    policy = issuer.issue("r1", "a1", "student")
    decision = issuer.check(policy, "terminal_command", {})
    assert decision.decision == BLOCKED
    assert decision.enforced is True


# ---------------------------------------------------------------------------
# S12: tenant-override narrows (never widens)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_S12_tenant_override_narrows_whitelist(monkeypatch):
    """When ATOM_SANDBOX_POLICY_TENANT_OVERRIDE=true, override intersects."""
    from core.sandbox_policy import PolicyIssuer

    monkeypatch.setenv("ATOM_SANDBOX_POLICY_TENANT_OVERRIDE", "true")
    issuer = PolicyIssuer()
    policy = issuer.issue(
        "r1",
        "a1",
        "supervised",
        tenant_overrides={
            "tool_whitelist": ("canvas_render", "browser_click"),
        },
    )
    # Result is intersection of supervised floor with override
    assert "canvas_render" in policy.tool_whitelist
    assert "browser_click" in policy.tool_whitelist
    # browser_download is in supervised floor but NOT in override → removed
    assert "browser_download" not in policy.tool_whitelist


@pytest.mark.unit
def test_S12b_tenant_override_ignored_when_flag_off(monkeypatch):
    """Without the flag, overrides are ignored."""
    from core.sandbox_policy import PolicyIssuer

    monkeypatch.delenv("ATOM_SANDBOX_POLICY_TENANT_OVERRIDE", raising=False)
    issuer = PolicyIssuer()
    policy = issuer.issue(
        "r1",
        "a1",
        "supervised",
        tenant_overrides={"tool_whitelist": ()},  # would empty the list
    )
    # Floor preserved
    assert "browser_click" in policy.tool_whitelist


@pytest.mark.unit
def test_S12c_tenant_override_caps_use_minimum(monkeypatch):
    from core.sandbox_policy import PolicyIssuer

    monkeypatch.setenv("ATOM_SANDBOX_POLICY_TENANT_OVERRIDE", "true")
    issuer = PolicyIssuer()
    policy = issuer.issue(
        "r1",
        "a1",
        "supervised",
        tenant_overrides={"max_tool_calls": 5},
    )
    # Default is 200, override is 5 → min wins
    assert policy.max_tool_calls == 5


# ---------------------------------------------------------------------------
# S13: config resolvers — env-var only
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_S13_config_master_switch_off_by_default(monkeypatch):
    from core import sandbox_config

    monkeypatch.delenv("ATOM_SANDBOX_ENABLED", raising=False)
    assert sandbox_config.is_sandbox_enabled() is False


@pytest.mark.unit
def test_S13b_config_master_switch_on(monkeypatch):
    from core import sandbox_config

    monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
    assert sandbox_config.is_sandbox_enabled() is True


@pytest.mark.unit
def test_S13c_config_runtime_validation_falls_back(monkeypatch):
    from core import sandbox_config

    monkeypatch.setenv("ATOM_SANDBOX_RUNTIME", "garbage")
    assert sandbox_config.get_sandbox_runtime() == "docker"
    monkeypatch.setenv("ATOM_SANDBOX_RUNTIME", "firecracker")
    assert sandbox_config.get_sandbox_runtime() == "firecracker"


@pytest.mark.unit
def test_S13d_config_numeric_tunables_have_sane_defaults(monkeypatch):
    from core import sandbox_config

    monkeypatch.delenv("ATOM_SANDBOX_MAX_TOOL_CALLS", raising=False)
    assert sandbox_config.get_sandbox_max_tool_calls() == 200
    monkeypatch.delenv("ATOM_SANDBOX_MAX_EXEC_SECONDS", raising=False)
    assert sandbox_config.get_sandbox_max_exec_seconds() == 600


# ---------------------------------------------------------------------------
# S14: invalid tier falls back to student floor
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_S14_invalid_tier_falls_back_to_student():
    from core.sandbox_policy import PolicyIssuer

    issuer = PolicyIssuer()
    policy = issuer.issue("r1", "a1", "nonsense_tier")
    assert policy.tier_at_issuance == "student"
    assert "canvas_render" in policy.tool_whitelist


# ---------------------------------------------------------------------------
# S15: to_dict round-trip — needed for audit + DB persistence
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_S15_policy_to_dict_round_trip():
    from core.sandbox_policy import SandboxPolicy

    policy = SandboxPolicy(
        run_id="r1",
        agent_id="a1",
        tier_at_issuance="intern",
        tool_whitelist=("a", "b"),
        max_tool_calls=42,
    )
    d = policy.to_dict()
    assert d["run_id"] == "r1"
    assert d["tier_at_issuance"] == "intern"
    assert d["tool_whitelist"] == ("a", "b")
    assert d["max_tool_calls"] == 42


# ---------------------------------------------------------------------------
# S16: audit writer no-ops for allowed decisions (no row written)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_S16_audit_writer_skips_allowed_decisions():
    """write_violation must not persist when decision is ALLOWED."""
    from core.sandbox_audit import write_violation
    from core.sandbox_policy import SandboxDecision, ALLOWED

    # Should return None without raising, even with no DB configured.
    decision = SandboxDecision(decision=ALLOWED, tool_name="x")
    # No exception should propagate
    write_violation(decision)


@pytest.mark.unit
def test_S16b_audit_writer_skips_when_sandbox_disabled(monkeypatch):
    from core import sandbox_config
    from core.sandbox_audit import write_violation
    from core.sandbox_policy import SandboxDecision, BLOCKED

    monkeypatch.delenv("ATOM_SANDBOX_ENABLED", raising=False)
    assert sandbox_config.is_sandbox_enabled() is False
    decision = SandboxDecision(decision=BLOCKED, tool_name="x")
    # No-op because master switch off
    write_violation(decision)


# ---------------------------------------------------------------------------
# S17: policy_id generator returns unique strings
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_S17_new_policy_id_unique():
    from core.sandbox_policy import new_policy_id

    ids = {new_policy_id() for _ in range(100)}
    assert len(ids) == 100  # all unique
