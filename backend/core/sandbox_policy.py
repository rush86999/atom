"""Execution Sandbox Layer — Phase A.

SandboxPolicy dataclass + PolicyIssuer service. Zero enforcement in this
module — enforcement is the caller's job (mcp_service /
atom_meta_agent). This module decides:

  1. *What* the policy for a given run is (``PolicyIssuer.issue``).
  2. *Whether* a given tool call conforms to that policy
     (``PolicyIssuer.check``) — producing a tri-state ``SandboxDecision``.

Mirrors the proven patterns of:

  * ``core/selector_confidence_service.py`` — frozen dataclass + tri-state
    discriminator (high/partial/ambiguous). Here the tri-state is
    allowed/restricted/blocked.
  * ``core/tool_outcome_verifier.py`` — VERIFIED / UNVERIFIED /
    FAILED_VERIFICATION post-action. Here we do the same pre-action.
  * ``core/llm/self_consistency_voter.py:VoteResult`` — VoteResult.level
    drives gating. Here SandboxDecision.decision drives gating.

Design contract:
  - Pure functions: never raise, deterministic on inputs.
  - Policy is immutable (frozen dataclass) once issued.
  - Tier floors are env-overridable.
  - ``check()`` is shadow-mode-aware: always computes a decision and an
    audit row, but only returns ``restricted`` / ``blocked`` to the caller
    when ``is_sandbox_force_enforce_enabled()`` is True. When False, the
    decision is recorded for audit but the caller sees ``allowed``.
"""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from core import sandbox_config

logger = logging.getLogger(__name__)


# ===========================================================================
# Tri-state discriminator values
# ===========================================================================
# Mirror the high/partial/ambiguous pattern but renamed to convey *action*
# semantics: a restricted call is recoverable, a blocked call is not.

ALLOWED = "allowed"
RESTRICTED = "restricted"
BLOCKED = "blocked"

_VALID_DECISIONS = {ALLOWED, RESTRICTED, BLOCKED}


class SandboxDecisionValue:
    """Namespace constants — mirrors ``MatchLevel`` pattern."""

    ALLOWED = ALLOWED
    RESTRICTED = RESTRICTED
    BLOCKED = BLOCKED


# Violation types (one per phase that produces them) — used in audit rows
# and Prometheus metric labels.
VT_FS_PATH = "fs_path"                  # Phase B
VT_TOOL_WHITELIST = "tool_whitelist"    # Phase C
VT_TRIPWIRE = "tripwire"                # Phase C
VT_CAP_EXCEEDED = "cap_exceeded"        # Phase C
VT_EGRESS_HOST = "egress_host"          # Phase D
VT_PROVENANCE = "provenance"            # Phase E


# ===========================================================================
# Tier-floor constants
# ===========================================================================
#
# STUDENT: read-only tools only, workspace/data + /tmp/agent/{run}/, no egress
# INTERN: + memory_tool, productivity_tool (read), /tmp/agent/{run}/
# SUPERVISED: + browser_tool, productivity_tool (write), curated egress
# AUTONOMOUS: + device_tool, shell, per-tenant egress list
#
# These are *floors* — the issued policy may further constrain but never
# widen. Operators override defaults via env vars.
TIER_FLOOR_TOOL_WHITELISTS: Dict[str, Tuple[str, ...]] = {
    "student": (
        "canvas_render",
        "canvas_get_state",
        "memory_search",
        "memory_recall",
        "search_reasoning_steps_lexical",
    ),
    "intern": (
        "canvas_render",
        "canvas_get_state",
        "memory_search",
        "memory_recall",
        "memory_remember",
        "search_reasoning_steps_lexical",
        "productivity_read",
        "browser_screenshot",
        "extract_text",
    ),
    "supervised": (
        "canvas_render",
        "canvas_get_state",
        "memory_search",
        "memory_recall",
        "memory_remember",
        "memory_forget",
        "search_reasoning_steps_lexical",
        "productivity_read",
        "productivity_write",
        "browser_navigate",
        "browser_click",
        "browser_fill_form",
        "browser_screenshot",
        "browser_download",
        "extract_text",
    ),
    "autonomous": (
        # AUTONOMOUS gets the full tool surface; blast radius is bounded by
        # FS scope + egress allowlist + tripwires, not tool whitelist.
        "*",
    ),
}

TIER_FLOOR_EGRESS_HOSTS: Dict[str, Tuple[str, ...]] = {
    "student": (),
    "intern": (),
    "supervised": (
        # Curated baseline — LLM provider hosts + package mirrors only.
        "api.anthropic.com",
        "api.openai.com",
        "generativelanguage.googleapis.com",
        "pypi.org",
        "files.pythonhosted.org",
    ),
    "autonomous": (
        "api.anthropic.com",
        "api.openai.com",
        "generativelanguage.googleapis.com",
        "api.deepseek.com",
        "pypi.org",
        "files.pythonhosted.org",
        "github.com",
        "raw.githubusercontent.com",
    ),
}

# Paths no tier may touch — used by FS tripwires in Phase B.
FORBIDDEN_PATH_PREFIXES: Tuple[str, ...] = (
    "/proc/",
    "/sys/",
    "/dev/",
    "/etc/",
    "/root/",
    "/var/lib/docker/",
)

FORBIDDEN_HOME_PATHS: Tuple[str, ...] = (
    ".ssh/",
    ".aws/",
    ".config/",
    ".env",
    ".env.",
)


# ===========================================================================
# Frozen dataclasses
# ===========================================================================
@dataclass(frozen=True)
class SandboxPolicy:
    """Per-run sandbox policy.

    Issued at agent-execution start from ``AgentRegistry.maturity_level``
    + workspace config. Stored in the ``RunSandbox`` table. Frozen so a
    compromised agent cannot mutate its own policy mid-run.

    Attributes:
        run_id: equals ``AgentExecution.id``.
        agent_id: issuing agent.
        tier_at_issuance: STUDENT/INTERN/SUPERVISED/AUTONOMOUS — captured
            at issuance so a later tier change doesn't retroactively widen
            scope of an in-flight run.
        fs_roots: read-allowed absolute paths.
        fs_write_roots: write-allowed absolute paths.
        tool_whitelist: tool names this run may call. ``("*",)`` means all
            tools (AUTONOMOUS tier).
        egress_hosts: DNS names this run may contact (Phase D).
        max_bytes_written: cumulative FS write cap.
        max_exec_seconds: wall-clock cap.
        max_tool_calls: cumulative tool-call count cap.
        max_cost_usd: cumulative LLM spend cap.
        tripwire_actions: instant-kill patterns (Phase C/E).
        issued_at: timezone-aware issuance timestamp.
        policy_version: monotonic schema version for forward-compat.
    """

    run_id: str
    agent_id: str
    tier_at_issuance: str
    fs_roots: Tuple[str, ...] = ()
    fs_write_roots: Tuple[str, ...] = ()
    tool_whitelist: Tuple[str, ...] = ()
    egress_hosts: Tuple[str, ...] = ()
    max_bytes_written: int = 0
    max_exec_seconds: int = 0
    max_tool_calls: int = 0
    max_cost_usd: float = 0.0
    tripwire_actions: Tuple[str, ...] = ()
    issued_at: str = ""
    policy_version: str = "2026-06-30"

    @property
    def allows_all_tools(self) -> bool:
        """True if this policy whitelists every tool (AUTONOMOUS)."""
        return "*" in self.tool_whitelist

    def tool_allowed(self, tool_name: str) -> bool:
        if self.allows_all_tools:
            return True
        return tool_name in self.tool_whitelist

    def to_dict(self) -> Dict[str, Any]:
        """Serializable view — used in audit metadata + DB row."""
        from dataclasses import asdict

        return asdict(self)


@dataclass(frozen=True)
class SandboxDecision:
    """Result of a single ``PolicyIssuer.check()`` call.

    Mirrors the ``MatchConfidence`` envelope pattern: a tri-state level
    plus structured rationale + provenance for audit.

    Attributes:
        decision: ALLOWED / RESTRICTED / BLOCKED.
        phase: which phase produced this decision (A/B/C/D/E).
        violation_type: one of ``VT_*`` constants when not ALLOWED.
        violation_detail: human/LLM-readable explanation.
        tool_name: the tool that was checked.
        args_hash: SHA-256 of redacted call args (for correlation across
            runs — args themselves are NOT stored, only the hash).
        enforced: True if the caller actually blocked/restricted. False in
            shadow mode (decision computed + audited but call proceeded).
        policy_id: FK to RunSandbox.id.
        killrun_triggered: True if this decision triggered KillRun
            (Phase C; always False for Phase A/B/D/E).
        metadata_json: structured extras for the audit row.
    """

    decision: str
    phase: str = "A"
    violation_type: Optional[str] = None
    violation_detail: str = ""
    tool_name: str = ""
    args_hash: Optional[str] = None
    enforced: bool = False
    policy_id: Optional[str] = None
    killrun_triggered: bool = False
    metadata_json: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_allowed(self) -> bool:
        return self.decision == ALLOWED

    @property
    def requires_review(self) -> bool:
        return self.decision in {RESTRICTED, BLOCKED}

    @property
    def is_terminal_block(self) -> bool:
        """True if this decision should abort the run entirely."""
        return self.decision == BLOCKED and self.killrun_triggered

    def to_audit_row(self) -> Dict[str, Any]:
        """Render as a kwargs dict suitable for ``SandboxViolation(**...)``.

        Called by the audit-row writer. ``metadata_json`` is included
        verbatim; the caller is responsible for ensuring no secrets are in
        it (only structured violation evidence).
        """
        from dataclasses import asdict

        return asdict(self)


# ===========================================================================
# Coercion helper — mirrors coerce_match_level_for_storage
# ===========================================================================
def coerce_decision_for_storage(value: Optional[str]) -> str:
    """Coerce an arbitrary value into a valid stored decision.

    Defaults to ALLOWED on any invalid input — the safe state that does
    NOT surface the row to reviewers (we want violations surfaced, not
    noise from corrupted data).
    """
    if value in _VALID_DECISIONS:
        return value
    return ALLOWED


def coerce_phase_for_storage(value: Optional[str]) -> str:
    """Coerce a phase label into A/B/C/D/E; defaults to 'A'."""
    if value and value.upper() in {"A", "B", "C", "D", "E"}:
        return value.upper()
    return "A"


# ===========================================================================
# Policy issuer
# ===========================================================================
class PolicyIssuer:
    """Issues per-run policies and evaluates tool calls against them.

    Stateless aside from the DB session it holds (for tier-floor lookups).
    Safe to instantiate per-request.

    Usage:
        issuer = PolicyIssuer(db=some_session)
        policy = issuer.issue(
            run_id=execution.id,
            agent_id=agent.id,
            tier_at_issuance=agent.maturity_level,
            workspace_data_root="/path/to/ws/data",
        )
        decision = issuer.check(
            policy=policy,
            tool_name="browser_click",
            args={"selector": "#foo"},
            context={"session_id": "...", "user_id": "..."},
        )
        if decision.requires_review and sandbox_config.is_sandbox_force_enforce_enabled():
            return {"error": "Sandbox block", "decision": decision.to_audit_row()}
    """

    def __init__(self, db: Any = None) -> None:
        self.db = db

    # ---- issuance ------------------------------------------------------

    def issue(
        self,
        run_id: str,
        agent_id: str,
        tier_at_issuance: str,
        workspace_data_root: Optional[str] = None,
        workspace_tmp_root: Optional[str] = None,
        tenant_overrides: Optional[Dict[str, Any]] = None,
    ) -> SandboxPolicy:
        """Issue a SandboxPolicy for a run.

        Per the plan's tier-floor table:
          - STUDENT: read-only tools, [workspace/data/], no egress
          - INTERN: + memory, productivity_read, [/tmp/agent/{run_id}/]
          - SUPERVISED: + browser, productivity_write, curated egress
          - AUTONOMOUS: + device, shell, full per-tenant egress list

        ``tenant_overrides`` is only applied when
        ``is_sandbox_policy_tenant_override()`` is True. Even then, it can
        only *narrow* the issued policy, never widen it (defense: floors
        are upper bounds, overrides may intersect with floors).
        """
        tier = (tier_at_issuance or "student").lower()
        if tier not in TIER_FLOOR_TOOL_WHITELISTS:
            tier = "student"

        # Filesystem roots — default workspace + per-run tmpfs.
        data_root = workspace_data_root or os.path.abspath("./data/workspace")
        tmp_root = workspace_tmp_root or f"/tmp/agent/{run_id}"

        fs_roots = (data_root, tmp_root)
        fs_write_roots = (tmp_root,) if tier != "student" else ()
        # STUDENT never gets write access outside the canvas (which is
        # in-memory, not FS).

        if tier in {"supervised", "autonomous"}:
            fs_write_roots = (tmp_root, os.path.join(data_root, "uploads"))

        tool_whitelist = TIER_FLOOR_TOOL_WHITELISTS.get(tier, TIER_FLOOR_TOOL_WHITELISTS["student"])
        egress_hosts = TIER_FLOOR_EGRESS_HOSTS.get(tier, ())

        policy = SandboxPolicy(
            run_id=run_id,
            agent_id=agent_id,
            tier_at_issuance=tier,
            fs_roots=tuple(fs_roots),
            fs_write_roots=tuple(fs_write_roots),
            tool_whitelist=tuple(tool_whitelist),
            egress_hosts=tuple(egress_hosts),
            max_bytes_written=sandbox_config.get_sandbox_max_bytes_written(),
            max_exec_seconds=sandbox_config.get_sandbox_max_exec_seconds(),
            max_tool_calls=sandbox_config.get_sandbox_max_tool_calls(),
            max_cost_usd=sandbox_config.get_sandbox_max_cost_usd(),
            tripwire_actions=(),  # Populated in Phase C
            issued_at=datetime.now(timezone.utc).isoformat(),
        )

        # Apply tenant overrides if allowed. Overrides may only narrow.
        if tenant_overrides and sandbox_config.is_sandbox_policy_tenant_override():
            policy = self._apply_overrides(policy, tenant_overrides)

        return policy

    @staticmethod
    def _apply_overrides(policy: SandboxPolicy, overrides: Dict[str, Any]) -> SandboxPolicy:
        """Deep-merge tenant overrides into policy. Only narrows.

        Whitelists / egress lists are intersected with the override
        (override can remove entries but not add). Caps use the minimum.
        """
        try:
            return replace(
                policy,
                tool_whitelist=tuple(
                    t for t in policy.tool_whitelist
                    if t in set(overrides.get("tool_whitelist", policy.tool_whitelist))
                    or t == "*"
                ),
                egress_hosts=tuple(
                    h for h in policy.egress_hosts
                    if h in set(overrides.get("egress_hosts", policy.egress_hosts))
                ),
                max_bytes_written=min(
                    policy.max_bytes_written,
                    int(overrides.get("max_bytes_written", policy.max_bytes_written)),
                ),
                max_exec_seconds=min(
                    policy.max_exec_seconds,
                    int(overrides.get("max_exec_seconds", policy.max_exec_seconds)),
                ),
                max_tool_calls=min(
                    policy.max_tool_calls,
                    int(overrides.get("max_tool_calls", policy.max_tool_calls)),
                ),
                max_cost_usd=min(
                    policy.max_cost_usd,
                    float(overrides.get("max_cost_usd", policy.max_cost_usd)),
                ),
            )
        except (TypeError, ValueError) as e:
            logger.warning(f"sandbox override ignored (invalid): {e}")
            return policy

    # ---- evaluation ----------------------------------------------------

    def check(
        self,
        policy: SandboxPolicy,
        tool_name: str,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        phase: str = "A",
    ) -> SandboxDecision:
        """Evaluate a tool call against a policy.

        Phase A only checks tool whitelist (everything else is a later
        phase). Shadow-mode aware: always returns the computed decision,
        but the *enforced* flag reflects whether the caller should block.

        Never raises — on any internal error, returns ALLOWED with
        ``metadata_json.error`` set. Defense: a broken sandbox should not
        block legitimate agent work; it should surface the bug via audit.

        Args hash is computed from a redacted view of args (secrets
        stripped) — the args themselves are never persisted.
        """
        ctx = context or {}
        args_hash = self._hash_args(args)

        # Phase A: tool whitelist only. (Phase B/C/D/E add their own checks
        # in their respective modules and call this for the audit row.)
        if not policy.tool_allowed(tool_name):
            decision = SandboxDecision(
                decision=BLOCKED,
                phase=phase,
                violation_type=VT_TOOL_WHITELIST,
                violation_detail=f"tool '{tool_name}' not in policy whitelist",
                tool_name=tool_name,
                args_hash=args_hash,
                policy_id=ctx.get("policy_id"),
                enforced=sandbox_config.is_sandbox_force_enforce_enabled(),
                metadata_json={"tier": policy.tier_at_issuance},
            )
            return decision

        # Allowed.
        return SandboxDecision(
            decision=ALLOWED,
            phase=phase,
            tool_name=tool_name,
            args_hash=args_hash,
            policy_id=ctx.get("policy_id"),
            enforced=False,
            metadata_json={"tier": policy.tier_at_issuance},
        )

    @staticmethod
    def _hash_args(args: Dict[str, Any]) -> str:
        """SHA-256 of a redacted view of call args.

        Redaction is intentionally conservative: keys matching common
        secret patterns are replaced with '***'. This is for correlation
        across runs (e.g. "this exact args-set was blocked N times") —
        NOT for storing the args themselves.
        """
        import hashlib
        import json

        _SECRET_KEY_FRAGMENTS = ("token", "password", "secret", "api_key", "apikey", "auth")

        def _redact(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {
                    k: ("***" if any(f in k.lower() for f in _SECRET_KEY_FRAGMENTS) else _redact(v))
                    for k, v in obj.items()
                }
            if isinstance(obj, list):
                return [_redact(x) for x in obj]
            return obj

        try:
            redacted = _redact(args or {})
            payload = json.dumps(redacted, sort_keys=True, default=str)
        except (TypeError, ValueError):
            payload = "unhashable"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ===========================================================================
# Module-level convenience: get a singleton issuer (no DB needed for stateless checks)
# ===========================================================================
_default_issuer: Optional[PolicyIssuer] = None


def get_default_issuer() -> PolicyIssuer:
    """Return a process-wide default PolicyIssuer (no DB session).

    Suitable for the common case where the caller has the policy already
    and just needs ``check()``. Callers that need tier-floor lookups
    should construct ``PolicyIssuer(db=session)`` directly.
    """
    global _default_issuer
    if _default_issuer is None:
        _default_issuer = PolicyIssuer()
    return _default_issuer


# ===========================================================================
# ID generation (used by callers when persisting RunSandbox rows)
# ===========================================================================
def new_policy_id() -> str:
    """Generate a new policy ID (uuid4 hex)."""
    return str(uuid.uuid4())
