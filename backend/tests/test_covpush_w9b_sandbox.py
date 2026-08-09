"""
Coverage wave 9b — core/sandbox_config.py (60% -> 100%) +
core/sandbox_policy.py (93% -> 100%).
"""
import json
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# sandbox_config — flag resolvers + numeric tunables
# ============================================================================

class TestSandboxConfigFlags:
    def test_default_off_flags(self, monkeypatch):
        from core import sandbox_config as sc

        monkeypatch.delenv("ATOM_SANDBOX_EGRESS_ENABLED", raising=False)
        monkeypatch.delenv("ATOM_SANDBOX_JUDGE_ENABLED", raising=False)
        monkeypatch.delenv("ATOM_SANDBOX_POLICY_TENANT_OVERRIDE", raising=False)
        assert sc.is_sandbox_egress_enabled() is False
        assert sc.is_sandbox_judge_enabled() is False
        assert sc.is_sandbox_policy_tenant_override() is False

    def test_flag_on_variants(self, monkeypatch):
        from core import sandbox_config as sc

        for val in ("1", "TRUE", "yes", "on"):
            monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", val)
            assert sc.is_sandbox_egress_enabled() is True

    def test_flag_false_variants(self, monkeypatch):
        from core import sandbox_config as sc

        for val in ("0", "false", "no", "off", ""):
            monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", val)
            assert sc.is_sandbox_egress_enabled() is False

    def test_default_on_flags(self, monkeypatch):
        from core import sandbox_config as sc

        monkeypatch.delenv("ATOM_SANDBOX_FS_ENABLED", raising=False)
        monkeypatch.delenv("ATOM_SANDBOX_WHITELIST_ENABLED", raising=False)
        monkeypatch.delenv("ATOM_SANDBOX_TRIPWIRES_ENABLED", raising=False)
        monkeypatch.delenv("ATOM_SANDBOX_CAPS_ENABLED", raising=False)
        monkeypatch.delenv("ATOM_SANDBOX_PROVENANCE_ENABLED", raising=False)
        assert sc.is_sandbox_fs_enabled() is True
        assert sc.is_sandbox_whitelist_enabled() is True
        assert sc.is_sandbox_tripwires_enabled() is True
        assert sc.is_sandbox_caps_enabled() is True
        assert sc.is_sandbox_provenance_enabled() is True

    def test_master_switch_off(self, monkeypatch):
        from core import sandbox_config as sc

        monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "false")
        assert sc.is_sandbox_enabled() is False

    def test_force_enforce_off(self, monkeypatch):
        from core import sandbox_config as sc

        monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "false")
        assert sc.is_sandbox_force_enforce_enabled() is False


class TestSandboxConfigRuntime:
    def test_valid_runtimes(self, monkeypatch):
        from core import sandbox_config as sc

        for val in ("firecracker", "e2b", "docker", "  Docker "):
            monkeypatch.setenv("ATOM_SANDBOX_RUNTIME", val)
            assert sc.get_sandbox_runtime() == val.strip().lower()

    def test_invalid_runtime_falls_back(self, monkeypatch):
        from core import sandbox_config as sc

        monkeypatch.setenv("ATOM_SANDBOX_RUNTIME", "k8s")
        assert sc.get_sandbox_runtime() == "docker"

    def test_runtime_default(self, monkeypatch):
        from core import sandbox_config as sc

        monkeypatch.delenv("ATOM_SANDBOX_RUNTIME", raising=False)
        assert sc.get_sandbox_runtime() == "docker"


class TestSandboxConfigNumeric:
    def test_getters_with_env(self, monkeypatch):
        from core import sandbox_config as sc

        monkeypatch.setenv("ATOM_SANDBOX_MAX_BYTES_WRITTEN", "2048")
        monkeypatch.setenv("ATOM_SANDBOX_MAX_EXEC_SECONDS", "30")
        monkeypatch.setenv("ATOM_SANDBOX_MAX_TOOL_CALLS", "7")
        monkeypatch.setenv("ATOM_SANDBOX_MAX_COST_USD", "1.25")
        monkeypatch.setenv("ATOM_SANDBOX_VM_MEM_MB", "512")
        monkeypatch.setenv("ATOM_SANDBOX_VM_VCPUS", "2")
        monkeypatch.setenv("ATOM_SANDBOX_VM_BOOT_TIMEOUT_SECONDS", "9")
        monkeypatch.setenv("ATOM_SANDBOX_JUDGE_TIMEOUT_SECONDS", "3.5")
        monkeypatch.setenv("ATOM_SANDBOX_JUDGE_CIRCUIT_THRESHOLD", "3")
        monkeypatch.setenv("ATOM_SANDBOX_JUDGE_CIRCUIT_COOLDOWN_SECONDS", "60")

        assert sc.get_sandbox_max_bytes_written() == 2048
        assert sc.get_sandbox_max_exec_seconds() == 30
        assert sc.get_sandbox_max_tool_calls() == 7
        assert sc.get_sandbox_max_cost_usd() == 1.25
        assert sc.get_sandbox_vm_mem_mb() == 512
        assert sc.get_sandbox_vm_vcpus() == 2
        assert sc.get_sandbox_vm_boot_timeout_seconds() == 9
        assert sc.get_sandbox_judge_timeout_seconds() == 3.5
        assert sc.get_sandbox_judge_circuit_threshold() == 3
        assert sc.get_sandbox_judge_circuit_cooldown_seconds() == 60

    def test_getters_invalid_env_falls_back(self, monkeypatch):
        from core import sandbox_config as sc

        for var, default in [
            ("ATOM_SANDBOX_MAX_BYTES_WRITTEN", 100 * 1024 * 1024),
            ("ATOM_SANDBOX_MAX_EXEC_SECONDS", 600),
            ("ATOM_SANDBOX_MAX_TOOL_CALLS", 200),
            ("ATOM_SANDBOX_MAX_COST_USD", 5.0),
            ("ATOM_SANDBOX_VM_MEM_MB", 256),
            ("ATOM_SANDBOX_VM_VCPUS", 1),
            ("ATOM_SANDBOX_VM_BOOT_TIMEOUT_SECONDS", 5),
            ("ATOM_SANDBOX_JUDGE_TIMEOUT_SECONDS", 2.0),
            ("ATOM_SANDBOX_JUDGE_CIRCUIT_THRESHOLD", 5),
            ("ATOM_SANDBOX_JUDGE_CIRCUIT_COOLDOWN_SECONDS", 120),
        ]:
            monkeypatch.setenv(var, "not-a-number")
        assert sc.get_sandbox_max_bytes_written() == 100 * 1024 * 1024
        assert sc.get_sandbox_max_exec_seconds() == 600
        assert sc.get_sandbox_max_tool_calls() == 200
        assert sc.get_sandbox_max_cost_usd() == 5.0
        assert sc.get_sandbox_vm_mem_mb() == 256
        assert sc.get_sandbox_vm_vcpus() == 1
        assert sc.get_sandbox_vm_boot_timeout_seconds() == 5
        assert sc.get_sandbox_judge_timeout_seconds() == 2.0
        assert sc.get_sandbox_judge_circuit_threshold() == 5
        assert sc.get_sandbox_judge_circuit_cooldown_seconds() == 120

    def test_getters_clamp_bounds(self, monkeypatch):
        from core import sandbox_config as sc

        monkeypatch.setenv("ATOM_SANDBOX_MAX_BYTES_WRITTEN", "-5")
        monkeypatch.setenv("ATOM_SANDBOX_MAX_EXEC_SECONDS", "0")
        monkeypatch.setenv("ATOM_SANDBOX_MAX_TOOL_CALLS", "-1")
        monkeypatch.setenv("ATOM_SANDBOX_MAX_COST_USD", "-2.0")
        monkeypatch.setenv("ATOM_SANDBOX_VM_MEM_MB", "16")
        monkeypatch.setenv("ATOM_SANDBOX_VM_VCPUS", "0")
        monkeypatch.setenv("ATOM_SANDBOX_VM_BOOT_TIMEOUT_SECONDS", "0")
        monkeypatch.setenv("ATOM_SANDBOX_JUDGE_TIMEOUT_SECONDS", "0.01")
        monkeypatch.setenv("ATOM_SANDBOX_JUDGE_CIRCUIT_THRESHOLD", "0")

        assert sc.get_sandbox_max_bytes_written() == 0
        assert sc.get_sandbox_max_exec_seconds() == 1
        assert sc.get_sandbox_max_tool_calls() == 1
        assert sc.get_sandbox_max_cost_usd() == 0.0
        assert sc.get_sandbox_vm_mem_mb() == 64
        assert sc.get_sandbox_vm_vcpus() == 1
        assert sc.get_sandbox_vm_boot_timeout_seconds() == 1
        assert sc.get_sandbox_judge_timeout_seconds() == 0.1
        assert sc.get_sandbox_judge_circuit_threshold() == 1


# ============================================================================
# sandbox_policy — remaining branches
# ============================================================================

class TestSandboxDecision:
    def test_is_terminal_block(self):
        from core.sandbox_policy import SandboxDecision, BLOCKED, ALLOWED

        assert SandboxDecision(decision=BLOCKED, killrun_triggered=True).is_terminal_block is True
        assert SandboxDecision(decision=BLOCKED, killrun_triggered=False).is_terminal_block is False
        assert SandboxDecision(decision=ALLOWED, killrun_triggered=True).is_terminal_block is False


class TestPolicyIssuer:
    def test_override_invalid_types_ignored(self):
        from core.sandbox_policy import PolicyIssuer, SandboxPolicy

        issuer = PolicyIssuer()
        policy = SandboxPolicy(run_id="r", agent_id="a", tier_at_issuance="SUPERVISED",
                               fs_roots=("/data",), fs_write_roots=("/data",))
        bad = {
            "tool_whitelist": [None],   # non-str entries → TypeError on set()? No: set({None}) is fine; use int caps
            "max_cost_usd": "not-num",  # ValueError
            "max_tool_calls": "x",      # ValueError
        }
        result = issuer._apply_overrides(policy, bad)
        assert result is policy

    def test_hash_args_redacts_lists_and_unhashable(self):
        from core.sandbox_policy import PolicyIssuer

        issuer = PolicyIssuer()
        h1 = issuer._hash_args({"tags": ["a", "b"], "api_token": "sk-123", "ok": {"n": 1}})
        h2 = issuer._hash_args({"tags": ["a", "b"], "api_token": "REDACTED", "ok": {"n": 1}})
        assert h1 == h2  # token value not in the hash

        h3 = issuer._hash_args({"obj": MagicMock()})
        assert h3  # unhashable payload falls back, still a hash

    def test_get_default_issuer_singleton(self):
        from core import sandbox_policy as sp

        orig = sp._default_issuer
        sp._default_issuer = None
        try:
            first = sp.get_default_issuer()
            assert sp.get_default_issuer() is first
        finally:
            sp._default_issuer = orig

    def test_new_policy_id(self):
        from core.sandbox_policy import new_policy_id

        pid = new_policy_id()
        assert isinstance(pid, str)
        assert len(pid) == 36


class TestHashArgsNeverRaises:
    def test_cyclic_args_does_not_raise(self):
        """RED (bug): check() documents 'Never raises', but _hash_args only
        guards TypeError/ValueError — a cyclic args dict raises RecursionError
        from json.dumps, escaping check() and crashing the dispatch path."""
        from core.sandbox_policy import PolicyIssuer, SandboxPolicy, ALLOWED

        cyclic = {"k": {}}
        cyclic["k"]["self"] = cyclic

        policy = SandboxPolicy(
            run_id="r", agent_id="a", tier_at_issuance="AUTONOMOUS",
            tool_whitelist=("*",),
        )
        decision = PolicyIssuer().check(policy, "any_tool", cyclic)
        assert decision.decision == ALLOWED

    def test_cyclic_args_hash_is_stable_fallback(self):
        from core.sandbox_policy import PolicyIssuer

        cyclic = {"k": {}}
        cyclic["k"]["self"] = cyclic
        h = PolicyIssuer()._hash_args(cyclic)
        assert isinstance(h, str)
        assert h == PolicyIssuer()._hash_args(cyclic)
