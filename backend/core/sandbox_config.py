"""Execution Sandbox Layer — feature-flag resolvers.

Closes the "tier is routing, not security" gap documented in
``docs/security/TRUST_VS_SANDBOX.md`` and
``docs/security/PROMPT_INJECTION_DEFENSE_PLAN.md``.

The maturity system uses past clean executions to decide what an agent is
*normally* allowed to do. It does **not** bound blast radius — a
prompt-injected agent at any tier uses the full scope that tier permits on
the next call. This module is the deterministic sandbox layer that runs
alongside the tier to actually bound blast radius.

Five phases (Rounds 43-47), each independently shippable and landed in
shadow mode (matching the proven rollout pattern of Round 41
match-confidence and Round 42 self-consistency voter):

  * **Phase A — Foundation** (Round 43): data model + policy resolvers +
    audit table. Compute + audit always on; enforcement off.
  * **Phase B — FS scope** (Round 44): enforce ``fs_roots`` /
    ``fs_write_roots`` on every tool that touches the filesystem.
  * **Phase C — Whitelist + caps + tripwires + KillRun** (Round 45):
    enforce ``tool_whitelist``, ``max_tool_calls``, ``max_exec_seconds``,
    ``max_bytes_written``, ``max_cost_usd``; full tripwire registry;
    hard-terminate runs on tripwire fire.
  * **Phase D — Firecracker microVM + egress proxy** (Round 46): replace
    Docker-based execution with dedicated-kernel microVMs; HTTP CONNECT
    egress proxy with domain allowlist.
  * **Phase E — Provenance + ActionJudge** (Round 47): tag every
    context-window chunk by trust level; constrain tool invocation to
    USER/SYSTEM provenance only; LLM-as-judge for irreversible actions.

Resolution: env var only. This is the Personal / single-tenant edition;
per-tenant overrides are a SaaS concern and live in the SaaS fork.

This module has no database surface and no side effects. It is safe to
import from anywhere, including the policy module.
"""
from __future__ import annotations

import os
from typing import Tuple


# ---------------------------------------------------------------------------
# Master switch + per-phase kill switches
# ---------------------------------------------------------------------------


def is_sandbox_enabled() -> bool:
    """Master switch for the entire sandbox layer (Phase A+).

    When False, ``PolicyIssuer.check()`` short-circuits to ``allowed`` and
    no audit rows are written. Equivalent to pre-Round-43 behavior.
    Default: off (Personal edition — opt-in).
    """
    return _flag("ATOM_SANDBOX_ENABLED")


def is_sandbox_force_enforce_enabled() -> bool:
    """Force-enforce mode for the sandbox layer.

    Shadow mode (default ``False``): policy is computed and audit rows are
    written, but calls are never actually blocked. This gives telemetry on
    violation rates before flipping the gate. Mirrors
    ``ATOM_SELF_CONSISTENCY_FORCE_PROPOSAL`` and
    ``MATCH_CONFIDENCE_FORCE_PROPOSAL``.
    """
    return _flag("ATOM_SANDBOX_FORCE_ENFORCE")


def is_sandbox_fs_enabled() -> bool:
    """Phase B — filesystem scope enforcement (default: off in Phase A)."""
    return _flag("ATOM_SANDBOX_FS_ENABLED")


def is_sandbox_whitelist_enabled() -> bool:
    """Phase C — tool whitelist enforcement (default: off)."""
    return _flag("ATOM_SANDBOX_WHITELIST_ENABLED")


def is_sandbox_tripwires_enabled() -> bool:
    """Phase C — tripwire pattern enforcement (default: off)."""
    return _flag("ATOM_SANDBOX_TRIPWIRES_ENABLED")


def is_sandbox_caps_enabled() -> bool:
    """Phase C — resource cap enforcement (default: off)."""
    return _flag("ATOM_SANDBOX_CAPS_ENABLED")


def is_sandbox_egress_enabled() -> bool:
    """Phase D — egress proxy enforcement (default: off)."""
    return _flag("ATOM_SANDBOX_EGRESS_ENABLED")


def is_sandbox_provenance_enabled() -> bool:
    """Phase E — provenance tagging in context assembly (default: off)."""
    return _flag("ATOM_SANDBOX_PROVENANCE_ENABLED")


def is_sandbox_judge_enabled() -> bool:
    """Phase E — LLM ActionJudge for irreversible actions (default: off)."""
    return _flag("ATOM_SANDBOX_JUDGE_ENABLED")


def is_sandbox_policy_tenant_override() -> bool:
    """Allow tenant metadata_json to override sandbox policies.

    Default: off. When enabled, ``AgentRegistry.metadata_json`` may carry
    a ``sandbox_overrides`` key whose dict is deep-merged into the policy
    at issuance. SaaS deployments may flip this; Personal edition leaves
    it off for predictability.
    """
    return _flag("ATOM_SANDBOX_POLICY_TENANT_OVERRIDE")


# ---------------------------------------------------------------------------
# SandboxRuntime selection (Phase D)
# ---------------------------------------------------------------------------

# Valid runtime backends. ``docker`` falls back to the pre-Round-46 path.
_VALID_RUNTIMES: Tuple[str, ...] = ("firecracker", "e2b", "docker")


def get_sandbox_runtime() -> str:
    """Which SandboxRuntime backend to use for executable tools.

    Default: ``docker`` (preserves existing behavior — no behavior change
    on rollout). Operators flip to ``firecracker`` (self-hosted microVM)
    or ``e2b`` (managed) after Phase D lands and the host is provisioned.
    """
    val = os.getenv("ATOM_SANDBOX_RUNTIME", "docker").strip().lower()
    if val not in _VALID_RUNTIMES:
        return "docker"
    return val


# ---------------------------------------------------------------------------
# Numeric tunables — resource caps
# ---------------------------------------------------------------------------


def get_sandbox_max_bytes_written() -> int:
    """Default cumulative FS write cap per run, in bytes (default 100 MiB).

    Per-run policy may override; this is the floor for tier-floor issuance
    when the caller supplies no explicit cap.
    """
    try:
        return max(0, int(os.getenv("ATOM_SANDBOX_MAX_BYTES_WRITTEN", str(100 * 1024 * 1024))))
    except (TypeError, ValueError):
        return 100 * 1024 * 1024


def get_sandbox_max_exec_seconds() -> int:
    """Default wall-clock cap per run, in seconds (default 600 = 10min)."""
    try:
        return max(1, int(os.getenv("ATOM_SANDBOX_MAX_EXEC_SECONDS", "600")))
    except (TypeError, ValueError):
        return 600


def get_sandbox_max_tool_calls() -> int:
    """Default cumulative tool-call count cap per run (default 200)."""
    try:
        return max(1, int(os.getenv("ATOM_SANDBOX_MAX_TOOL_CALLS", "200")))
    except (TypeError, ValueError):
        return 200


def get_sandbox_max_cost_usd() -> float:
    """Default cumulative LLM spend cap per run, in USD (default 5.0)."""
    try:
        return max(0.0, float(os.getenv("ATOM_SANDBOX_MAX_COST_USD", "5.0")))
    except (TypeError, ValueError):
        return 5.0


# ---------------------------------------------------------------------------
# Numeric tunables — microVM (Phase D)
# ---------------------------------------------------------------------------


def get_sandbox_vm_mem_mb() -> int:
    """Per-microVM memory in MiB (default 256)."""
    try:
        return max(64, int(os.getenv("ATOM_SANDBOX_VM_MEM_MB", "256")))
    except (TypeError, ValueError):
        return 256


def get_sandbox_vm_vcpus() -> int:
    """Per-microVM vCPU count (default 1)."""
    try:
        return max(1, int(os.getenv("ATOM_SANDBOX_VM_VCPUS", "1")))
    except (TypeError, ValueError):
        return 1


def get_sandbox_vm_boot_timeout_seconds() -> int:
    """MicroVM boot timeout in seconds (default 5)."""
    try:
        return max(1, int(os.getenv("ATOM_SANDBOX_VM_BOOT_TIMEOUT_SECONDS", "5")))
    except (TypeError, ValueError):
        return 5


# ---------------------------------------------------------------------------
# ActionJudge (Phase E)
# ---------------------------------------------------------------------------


def get_sandbox_judge_timeout_seconds() -> float:
    """ActionJudge LLM call timeout in seconds (default 2.0).

    Mirrors the ``MATCH_CONFIDENCE_TIEBREAKER_TIMEOUT`` pattern — budget
    tier, fail-open on timeout.
    """
    try:
        return max(0.1, float(os.getenv("ATOM_SANDBOX_JUDGE_TIMEOUT_SECONDS", "2.0")))
    except (TypeError, ValueError):
        return 2.0


def get_sandbox_judge_circuit_threshold() -> int:
    """Failures before ActionJudge circuit opens (default 5).

    Mirrors ``_CircuitBreaker`` in ``match_confidence_tiebreaker.py`` and
    ``turn_fact_extractor.py``.
    """
    try:
        return max(1, int(os.getenv("ATOM_SANDBOX_JUDGE_CIRCUIT_THRESHOLD", "5")))
    except (TypeError, ValueError):
        return 5


def get_sandbox_judge_circuit_cooldown_seconds() -> int:
    """Open-circuit cooldown in seconds (default 120)."""
    try:
        return max(1, int(os.getenv("ATOM_SANDBOX_JUDGE_CIRCUIT_COOLDOWN_SECONDS", "120")))
    except (TypeError, ValueError):
        return 120


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _flag(env_var: str) -> bool:
    """Parse env var as boolean (true/false/1/0/yes/no/on/off).

    Identical to the helper in ``hallucination_config.py``. Duplicated
    intentionally to avoid cross-module coupling between feature areas.
    """
    return os.getenv(env_var, "false").strip().lower() in {"1", "true", "yes", "on"}
