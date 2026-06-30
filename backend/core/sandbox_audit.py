"""Execution Sandbox Layer — audit-row writer.

Persists ``SandboxDecision`` rows to the ``SandboxViolation`` table.
Separated from ``sandbox_policy.py`` to keep that module pure (no DB
imports) and to allow the writer to be lazy-imported only when the
sandbox is enabled (avoiding the SQLAlchemy import cost on the hot path
when the layer is off).

Mirrors the audit-writer pattern from
``core/llm_service.py:_write_self_consistency_audit`` (Round 42).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from core import sandbox_config
from core.sandbox_policy import SandboxDecision

logger = logging.getLogger(__name__)


def write_violation(
    decision: SandboxDecision,
    *,
    db: Any = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> None:
    """Write a SandboxViolation row for a non-allowed decision.

    Silently no-ops when:
      - decision is ALLOWED (allowed decisions are NOT audited — they're
        the common case and would drown the signal)
      - the sandbox layer is disabled (master switch off)
      - the DB session is unavailable

    Never raises — a broken audit writer must not break agent execution.
    All exceptions are caught and logged at warning level.
    """
    # No-op for allowed decisions — we only audit what we gate.
    from core.sandbox_policy import ALLOWED

    if decision.decision == ALLOWED:
        return

    if not sandbox_config.is_sandbox_enabled():
        return

    try:
        from core.database import SessionLocal
        from core.models import SandboxViolation

        owns_session = db is None
        session = db or SessionLocal()
        try:
            row = SandboxViolation(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                agent_id=agent_id,
                user_id=user_id,
                session_id=session_id,
                policy_id=decision.policy_id,
                run_id=run_id,
                phase=decision.phase,
                decision=decision.decision,
                tool_name=decision.tool_name,
                violation_type=decision.violation_type,
                violation_detail=decision.violation_detail,
                args_hash=decision.args_hash,
                enforced=decision.enforced,
                killrun_triggered=decision.killrun_triggered,
                metadata_json=decision.metadata_json or {},
            )
            session.add(row)
            session.commit()
        finally:
            if owns_session:
                session.close()
    except Exception as e:  # noqa: BLE001 — audit writer must never raise
        logger.warning(
            "sandbox audit write failed (decision=%s tool=%s phase=%s): %s",
            decision.decision,
            decision.tool_name,
            decision.phase,
            e,
        )


def write_run_policy(policy_dict: dict, **context: Any) -> Optional[str]:
    """Persist a RunSandbox row capturing the issued policy.

    Returns the policy_id (uuid) on success, None on failure. Used at
    agent-execution start so subsequent SandboxViolation rows can FK to
    this one.
    """
    if not sandbox_config.is_sandbox_enabled():
        return None

    try:
        from core.database import SessionLocal
        from core.models import RunSandbox
        from core.sandbox_policy import new_policy_id

        policy_id = new_policy_id()
        owns_session = context.get("db") is None
        db = context.pop("db", None) or SessionLocal()
        try:
            row = RunSandbox(
                id=policy_id,
                tenant_id=context.get("tenant_id"),
                workspace_id=context.get("workspace_id"),
                run_id=policy_dict.get("run_id"),
                agent_id=context.get("agent_id") or policy_dict.get("agent_id"),
                user_id=context.get("user_id"),
                session_id=context.get("session_id"),
                tier_at_issuance=policy_dict.get("tier_at_issuance", "student"),
                fs_roots=list(policy_dict.get("fs_roots", [])),
                fs_write_roots=list(policy_dict.get("fs_write_roots", [])),
                tool_whitelist=list(policy_dict.get("tool_whitelist", [])),
                egress_hosts=list(policy_dict.get("egress_hosts", [])),
                max_bytes_written=policy_dict.get("max_bytes_written"),
                max_exec_seconds=policy_dict.get("max_exec_seconds"),
                max_tool_calls=policy_dict.get("max_tool_calls"),
                max_cost_usd=policy_dict.get("max_cost_usd"),
                tripwire_actions=list(policy_dict.get("tripwire_actions", [])),
                policy_version=policy_dict.get("policy_version"),
                metadata_json={},
            )
            db.add(row)
            db.commit()
            return policy_id
        finally:
            if owns_session:
                db.close()
    except Exception as e:  # noqa: BLE001
        logger.warning("sandbox run-policy write failed: %s", e)
        return None
