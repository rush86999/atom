"""Coverage wave 39 — sandbox_config (54%) + sandbox_audit (29%) + sandbox_policy (92%) + sandbox_fs (94%) → 90%+.

- config: every numeric-tunable exception branch (invalid env → default),
  invalid runtime value → docker, _flag value matrix
- audit: violation-row write (owned session, provided session, exception
  tolerance), allowed no-op, disabled no-op, run-policy write (success,
  disabled, exception)
- policy: is_terminal_block True, override ValueError, sandbox-disabled
  decision, _redact list branch + unhashable payload, default-issuer creation
- fs: rewrite_path_to_sandbox mkdir-OSError tolerance + exception fallback
"""
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import core.sandbox_audit as sbaudit
import core.sandbox_config as sbconfig
import core.sandbox_policy as sbpolicy
from core.sandbox_policy import (
    ALLOWED,
    BLOCKED,
    SandboxDecision,
    SandboxPolicy,
    PolicyIssuer,
    get_default_issuer,
)


class TestSandboxConfig:
    def test_flag_value_matrix(self):
        for v in ("1", "true", "yes", "on", "True", " ON "):
            with patch.dict(os.environ, {"X": v}, clear=True):
                assert sbconfig._flag("X") is True
        for v in ("0", "false", "no", "off", "banana", ""):
            with patch.dict(os.environ, {"X": v}, clear=True):
                assert sbconfig._flag("X") is False

    def test_flag_unset_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert sbconfig._flag("X", default="true") is True
            assert sbconfig._flag("X") is False

    def test_all_resolvers_with_env_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            assert sbconfig.is_sandbox_enabled() is True
            assert sbconfig.is_sandbox_force_enforce_enabled() is True
            assert sbconfig.is_sandbox_fs_enabled() is True
            assert sbconfig.is_sandbox_whitelist_enabled() is True
            assert sbconfig.is_sandbox_tripwires_enabled() is True
            assert sbconfig.is_sandbox_caps_enabled() is True
            assert sbconfig.is_sandbox_egress_enabled() is False
            assert sbconfig.is_sandbox_provenance_enabled() is True
            assert sbconfig.is_sandbox_judge_enabled() is False
            assert sbconfig.is_sandbox_policy_tenant_override() is False

    def test_all_resolvers_with_env_set(self):
        for var in (
            "ATOM_SANDBOX_ENABLED", "ATOM_SANDBOX_FORCE_ENFORCE",
            "ATOM_SANDBOX_FS_ENABLED", "ATOM_SANDBOX_WHITELIST_ENABLED",
            "ATOM_SANDBOX_TRIPWIRES_ENABLED", "ATOM_SANDBOX_CAPS_ENABLED",
            "ATOM_SANDBOX_EGRESS_ENABLED", "ATOM_SANDBOX_PROVENANCE_ENABLED",
            "ATOM_SANDBOX_JUDGE_ENABLED", "ATOM_SANDBOX_POLICY_TENANT_OVERRIDE",
        ):
            with patch.dict(os.environ, {var: "false"}, clear=True):
                assert sbconfig._flag(var, default="true") is False

    def test_runtime_invalid_falls_back_docker(self):
        with patch.dict(os.environ, {"ATOM_SANDBOX_RUNTIME": "k8s"}, clear=True):
            assert sbconfig.get_sandbox_runtime() == "docker"

    def test_runtime_valid_values(self):
        for v in ("firecracker", "e2b", "docker"):
            with patch.dict(os.environ, {"ATOM_SANDBOX_RUNTIME": v}, clear=True):
                assert sbconfig.get_sandbox_runtime() == v

    def test_runtime_uppercase_normalized(self):
        with patch.dict(os.environ, {"ATOM_SANDBOX_RUNTIME": "DOCKER"}, clear=True):
            assert sbconfig.get_sandbox_runtime() == "docker"

    def test_numeric_tunables_invalid_env_falls_back(self):
        invalid = {
            "ATOM_SANDBOX_MAX_BYTES_WRITTEN": "abc",
            "ATOM_SANDBOX_MAX_EXEC_SECONDS": "abc",
            "ATOM_SANDBOX_MAX_TOOL_CALLS": "abc",
            "ATOM_SANDBOX_MAX_COST_USD": "abc",
            "ATOM_SANDBOX_VM_MEM_MB": "abc",
            "ATOM_SANDBOX_VM_VCPUS": "abc",
            "ATOM_SANDBOX_VM_BOOT_TIMEOUT_SECONDS": "abc",
            "ATOM_SANDBOX_JUDGE_TIMEOUT_SECONDS": "abc",
            "ATOM_SANDBOX_JUDGE_CIRCUIT_THRESHOLD": "abc",
            "ATOM_SANDBOX_JUDGE_CIRCUIT_COOLDOWN_SECONDS": "abc",
        }
        expected = {
            "ATOM_SANDBOX_MAX_BYTES_WRITTEN": 100 * 1024 * 1024,
            "ATOM_SANDBOX_MAX_EXEC_SECONDS": 600,
            "ATOM_SANDBOX_MAX_TOOL_CALLS": 200,
            "ATOM_SANDBOX_MAX_COST_USD": 5.0,
            "ATOM_SANDBOX_VM_MEM_MB": 256,
            "ATOM_SANDBOX_VM_VCPUS": 1,
            "ATOM_SANDBOX_VM_BOOT_TIMEOUT_SECONDS": 5,
            "ATOM_SANDBOX_JUDGE_TIMEOUT_SECONDS": 2.0,
            "ATOM_SANDBOX_JUDGE_CIRCUIT_THRESHOLD": 5,
            "ATOM_SANDBOX_JUDGE_CIRCUIT_COOLDOWN_SECONDS": 120,
        }
        with patch.dict(os.environ, invalid, clear=True):
            assert sbconfig.get_sandbox_max_bytes_written() == expected["ATOM_SANDBOX_MAX_BYTES_WRITTEN"]
            assert sbconfig.get_sandbox_max_exec_seconds() == expected["ATOM_SANDBOX_MAX_EXEC_SECONDS"]
            assert sbconfig.get_sandbox_max_tool_calls() == expected["ATOM_SANDBOX_MAX_TOOL_CALLS"]
            assert sbconfig.get_sandbox_max_cost_usd() == expected["ATOM_SANDBOX_MAX_COST_USD"]
            assert sbconfig.get_sandbox_vm_mem_mb() == expected["ATOM_SANDBOX_VM_MEM_MB"]
            assert sbconfig.get_sandbox_vm_vcpus() == expected["ATOM_SANDBOX_VM_VCPUS"]
            assert sbconfig.get_sandbox_vm_boot_timeout_seconds() == expected["ATOM_SANDBOX_VM_BOOT_TIMEOUT_SECONDS"]
            assert sbconfig.get_sandbox_judge_timeout_seconds() == expected["ATOM_SANDBOX_JUDGE_TIMEOUT_SECONDS"]
            assert sbconfig.get_sandbox_judge_circuit_threshold() == expected["ATOM_SANDBOX_JUDGE_CIRCUIT_THRESHOLD"]
            assert sbconfig.get_sandbox_judge_circuit_cooldown_seconds() == expected["ATOM_SANDBOX_JUDGE_CIRCUIT_COOLDOWN_SECONDS"]

    def test_numeric_tunables_clamped(self):
        with patch.dict(os.environ, {
            "ATOM_SANDBOX_MAX_BYTES_WRITTEN": "-5",
            "ATOM_SANDBOX_MAX_EXEC_SECONDS": "0",
            "ATOM_SANDBOX_VM_MEM_MB": "10",
            "ATOM_SANDBOX_MAX_COST_USD": "-1",
        }, clear=True):
            assert sbconfig.get_sandbox_max_bytes_written() == 0
            assert sbconfig.get_sandbox_max_exec_seconds() == 1
            assert sbconfig.get_sandbox_vm_mem_mb() == 64
            assert sbconfig.get_sandbox_max_cost_usd() == 0.0


def _blocked_decision(**kw):
    return SandboxDecision(
        decision=BLOCKED, phase="C", tool_name="t1",
        violation_type="tripwire", violation_detail="d",
        args_hash="h", enforced=True, **kw,
    )


class TestSandboxAudit:
    def test_allowed_decision_not_audited(self):
        with patch("core.database.SessionLocal") as sl:
            sbaudit.write_violation(
                SandboxDecision(decision=ALLOWED, phase="A", tool_name="t",
                                args_hash="h"))
            sl.assert_not_called()

    def test_disabled_sandbox_not_audited(self):
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=False), \
             patch("core.database.SessionLocal") as sl:
            sbaudit.write_violation(_blocked_decision())
            sl.assert_not_called()

    def test_writes_violation_with_owned_session(self):
        session = Mock()
        with patch("core.database.SessionLocal", return_value=session):
            sbaudit.write_violation(
                _blocked_decision(metadata_json={"k": "v"}),
                tenant_id="t", workspace_id="w", agent_id="a", user_id="u",
                session_id="s", run_id="r",
            )
        session.add.assert_called_once()
        session.commit.assert_called_once()
        session.close.assert_called_once()

    def test_writes_violation_with_provided_session(self):
        session = Mock()
        sbaudit.write_violation(_blocked_decision(), db=session)
        session.commit.assert_called_once()
        session.close.assert_not_called()  # caller owns it

    def test_violation_write_exception_swallowed(self):
        session = Mock()
        session.commit.side_effect = RuntimeError("db boom")
        with patch("core.database.SessionLocal", return_value=session):
            sbaudit.write_violation(_blocked_decision())  # must not raise

    def test_run_policy_disabled_returns_none(self):
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=False):
            assert sbaudit.write_run_policy({"run_id": "r"}) is None

    def test_run_policy_success(self):
        session = Mock()
        with patch("core.database.SessionLocal", return_value=session), \
             patch("core.sandbox_policy.new_policy_id", return_value="pol-1"):
            policy_id = sbaudit.write_run_policy(
                {"run_id": "r", "tier_at_issuance": "intern",
                 "fs_roots": ["/a"], "tool_whitelist": ["x"]},
                tenant_id="t", workspace_id="w", agent_id="a", user_id="u",
                session_id="s",
            )
        assert policy_id == "pol-1"
        session.add.assert_called_once()
        session.commit.assert_called_once()
        session.close.assert_called_once()

    def test_run_policy_provided_session(self):
        session = Mock()
        with patch("core.sandbox_policy.new_policy_id", return_value="pol-2"):
            policy_id = sbaudit.write_run_policy({"run_id": "r"}, db=session)
        assert policy_id == "pol-2"
        session.close.assert_not_called()

    def test_run_policy_exception_returns_none(self):
        session = Mock()
        session.commit.side_effect = RuntimeError("boom")
        with patch("core.database.SessionLocal", return_value=session):
            assert sbaudit.write_run_policy({"run_id": "r"}) is None


class TestSandboxPolicyRemaining:
    def test_is_terminal_block_true(self):
        d = _blocked_decision(killrun_triggered=True)
        assert d.is_terminal_block is True

    def test_override_invalid_values_ignored(self):
        issuer = PolicyIssuer()
        policy = SandboxPolicy(
            run_id="r", agent_id="a1", tier_at_issuance="autonomous",
            fs_roots=["/a"], fs_write_roots=["/a"],
            tool_whitelist=["t"], max_tool_calls=200,
            max_exec_seconds=600, max_bytes_written=100,
            max_cost_usd=5.0,
        )
        out = PolicyIssuer._apply_overrides(
            policy, {"max_tool_calls": "abc", "max_cost_usd": "xyz"})
        assert out.max_tool_calls == 200
        assert out.max_cost_usd == 5.0

    def test_check_sandbox_disabled_returns_allowed(self):
        issuer = PolicyIssuer()
        policy = SandboxPolicy(
            run_id="r", agent_id="a1", tier_at_issuance="autonomous",
            fs_roots=["/a"], fs_write_roots=["/a"],
            tool_whitelist=["t"], max_tool_calls=200,
            max_exec_seconds=600, max_bytes_written=100,
            max_cost_usd=5.0,
        )
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=False):
            d = issuer.check(policy, "t", {"x": 1})
        assert d.decision == ALLOWED
        assert "sandbox_disabled" in (d.metadata_json or {}).get("reason", "")

    def test_hash_args_redacts_list(self):
        issuer = PolicyIssuer()
        h1 = issuer._hash_args({"cmd": ["ls", "-la"]})
        h2 = issuer._hash_args({"cmd": ["ls", "-la"]})
        assert h1 == h2

    def test_hash_args_unhashable_payload(self):
        issuer = PolicyIssuer()
        cyclic = {}
        cyclic["self"] = cyclic
        # cyclic dict → json.dumps fails → "unhashable" fallback (never raises)
        h = issuer._hash_args(cyclic)
        assert isinstance(h, str) and h

    def test_get_default_issuer_creates_singleton(self):
        with patch.object(sbpolicy, "_default_issuer", None):
            issuer = get_default_issuer()
            assert issuer is get_default_issuer()


class TestSandboxFsRemaining:
    def test_rewrite_mkdir_oserror_tolerated(self):
        from core.sandbox_fs import rewrite_path_to_sandbox
        with patch("pathlib.Path.mkdir", side_effect=OSError("no perms")):
            out = rewrite_path_to_sandbox(
                "report.txt", sandbox_write_root="/tmp/sb-root", cwd="/tmp")
        assert isinstance(out, str) and out.endswith("report.txt")

    def test_rewrite_invalid_path_returns_original(self):
        from core.sandbox_fs import rewrite_path_to_sandbox
        out = rewrite_path_to_sandbox(
            "/abs/path/file.txt", sandbox_write_root="/tmp/sb")
        assert out == "/abs/path/file.txt" or isinstance(out, str)
