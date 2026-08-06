"""
Sandbox Gate — shared dispatch-layer sandbox check (P9, Cloudflare OS G5).

Extracts the per-tool-call sandbox evaluation that lived inline in
``atom_meta_agent._meta_agent_sandbox_check`` into a reusable helper so ALL
dispatch paths route through it — not just the meta-agent. Today only
``atom_meta_agent`` (and the dead ``core.mcp_service``) enforce the sandbox; the
legacy dispatch (generic agents, fleet, workflow, business agents) bypasses it
because they go through ``integrations.mcp_service.call_tool`` with no gate.

``evaluate_tool_call`` is the single entry point invoked by
``integrations.mcp_service.call_tool`` (P9) and reused by ``atom_meta_agent``
(P9 refactor). It returns a ``SandboxDecision`` or ``None`` when no policy is in
scope (e.g. master switch off, no run_id). Never raises — a broken sandbox fails
open (returns ALLOWED with metadata_json.error), matching the meta-agent policy.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def evaluate_tool_call(
    tool_name: str,
    args: Dict[str, Any],
    context: Dict[str, Any],
) -> Optional[Any]:
    """Evaluate a tool call against the run's sandbox policy.

    Returns a ``SandboxDecision`` or ``None`` when no policy is in scope.
    Writes an audit row on any non-allowed decision. Never raises — a broken
    sandbox fails open (ALLOWED with metadata_json.error).

    Args:
        tool_name: the tool about to execute.
        args: the tool arguments.
        context: the dispatch context (run_id/execution_id, tier_at_issuance/
            tier, agent_id, tenant_id, workspace_id, user_id, session_id,
            workspace_data_root).

    Returns:
        ``SandboxDecision`` or ``None`` (no policy in scope -> allowed).
    """
    try:
        from core import sandbox_config
        from core.sandbox_policy import PolicyIssuer, SandboxDecision, ALLOWED
        from core.sandbox_audit import write_violation

        if not sandbox_config.is_sandbox_enabled():
            return None

        run_id = context.get("run_id") or context.get("execution_id")
        if not run_id:
            return None

        tier = (context.get("tier_at_issuance") or context.get("tier") or "").lower()
        if not tier:
            return None

        # KillRun guard. A killed run must never execute another tool call.
        # Return an enforced BLOCKED decision instead of raising
        # KillRunAborted: dispatch callers (integrations/mcp_service) catch
        # exceptions fail-open, which would otherwise let the killed run keep
        # executing tools.
        try:
            from core import sandbox_killrun
            from core.sandbox_killrun import KillRunAborted
            sandbox_killrun.guard(run_id)
        except KillRunAborted as exc:
            from core import sandbox_audit
            from core.sandbox_policy import BLOCKED, VT_TRIPWIRE
            decision = SandboxDecision(
                decision=BLOCKED,
                phase="C",
                violation_type=VT_TRIPWIRE,
                violation_detail=f"run killed by sandbox: {exc}",
                tool_name=tool_name,
                enforced=True,
                killrun_triggered=True,
                metadata_json={"killrun": True, "reason": str(exc)},
            )
            sandbox_audit.write_violation(
                decision,
                tenant_id=context.get("tenant_id"),
                workspace_id=context.get("workspace_id"),
                agent_id=context.get("agent_id"),
                user_id=context.get("user_id"),
                session_id=context.get("session_id"),
                run_id=run_id,
            )
            return decision

        issuer = PolicyIssuer()
        policy = issuer.issue(
            run_id=run_id,
            agent_id=context.get("agent_id", "atom_main"),
            tier_at_issuance=tier,
            workspace_data_root=context.get("workspace_data_root"),
        )
        if sandbox_config.is_sandbox_whitelist_enabled():
            decision = issuer.check(
                policy=policy,
                tool_name=tool_name,
                args=args,
                context=context,
                phase="A",
            )
        else:
            decision = SandboxDecision(
                decision=ALLOWED,
                phase="A",
                tool_name=tool_name,
                args_hash=PolicyIssuer._hash_args(args),
                metadata_json={"reason": "whitelist_disabled"},
            )

        # Phase B: filesystem scope check.
        if decision.is_allowed and sandbox_config.is_sandbox_fs_enabled():
            from core.sandbox_fs import validate as fs_validate
            fs_decision = fs_validate(policy, tool_name, args, context=context)
            if fs_decision.requires_review:
                decision = fs_decision

        # Phase C: tripwires.
        if decision.is_allowed and sandbox_config.is_sandbox_tripwires_enabled():
            from core import sandbox_tripwire
            tw_decision = sandbox_tripwire.check(
                tool_name=tool_name,
                args=args,
                args_hash=decision.args_hash,
                context=context,
            )
            if tw_decision.decision != "allowed":
                decision = tw_decision
                if decision.killrun_triggered and sandbox_config.is_sandbox_force_enforce_enabled():
                    from core import sandbox_killrun
                    sandbox_killrun.trigger_killrun(
                        run_id,
                        reason=decision.violation_detail or "tripwire",
                        tripwire_id=decision.metadata_json.get("tripwire_id"),
                        execution_id=run_id,
                    )

        # Phase C: resource caps.
        if decision.is_allowed and sandbox_config.is_sandbox_caps_enabled():
            from core import sandbox_caps
            cap_decision = sandbox_caps.check_caps(
                policy,
                tool_name=tool_name,
                args=args,
                args_hash=decision.args_hash,
                context=context,
            )
            if cap_decision.requires_review:
                decision = cap_decision

        # Phase D: egress allowlist (opt-in; off by default).
        if decision.is_allowed and sandbox_config.is_sandbox_egress_enabled():
            from core import sandbox_egress_proxy
            egress_decision = sandbox_egress_proxy.validate(
                policy,
                tool_name,
                args,
                context=context,
            )
            if egress_decision.requires_review:
                decision = egress_decision

        if decision.requires_review:
            write_violation(
                decision,
                tenant_id=context.get("tenant_id"),
                workspace_id=context.get("workspace_id"),
                agent_id=context.get("agent_id"),
                user_id=context.get("user_id"),
                session_id=context.get("session_id"),
                run_id=run_id,
            )
        return decision
    except Exception as e:  # noqa: BLE001
        # KillRunAborted must propagate — it's how tripwire kills abort the
        # AgentExecution. All other exceptions fail open.
        from core.sandbox_killrun import KillRunAborted
        if isinstance(e, KillRunAborted):
            raise
        logger.debug("sandbox gate failed open for %s: %s", tool_name, e)
        from core.sandbox_policy import SandboxDecision, ALLOWED
        return SandboxDecision(
            decision=ALLOWED,
            phase="A",
            tool_name=tool_name,
            metadata_json={"error": str(e)},
        )
