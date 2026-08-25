"""Thin adapter: attach a lateral radio thread to a recruited fleet.

Mirrors the paper's "thin adapter that starts the workers, assigns identities,
connects them to the shared server, and manages final synthesis":
``_recruit_fleet`` creates the DelegationChain; this helper optionally creates
the matching ``AgentThread`` (one per fleet, chain-scoped) — but ONLY when the
task crosses a responsibility breakpoint (`radio_breaker`). A fixed team is
not the default; bounded local tasks get no thread and behave exactly as
before.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from core.agent_radio import radio_config, radio_service
from core.agent_radio.radio_breaker import should_attach_thread
from core.models import AgentExecution, AgentThread

logger = logging.getLogger(__name__)


def attach_thread_for_chain(
    db: Session,
    *,
    chain_id: str,
    task_description: str,
    team_agent_ids: List[str],
    created_by_agent_id: str = "atom_main",
    execution_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> Optional[AgentThread]:
    """Create a breakpoint-gated radio thread for a recruited fleet.

    Returns ``None`` when radio is disabled, the gate says no, or the task is
    bounded local work — in every such case fleet behavior is unchanged.
    """
    if not radio_config.radio_enabled():
        return None
    verdict = should_attach_thread(task_description)
    if not verdict.triggered:
        logger.debug(f"radio: no responsibility breakpoint for chain {chain_id}: {verdict.reasons}")
        return None

    thread = radio_service.create_thread(
        db,
        name=f"fleet-{chain_id[:8]}",
        created_by_agent_id=created_by_agent_id,
        member_agent_ids=team_agent_ids,
        chain_id=chain_id,
        tenant_id=tenant_id,
        metadata_json={"scope": "fleet", "breakpoint_reasons": verdict.reasons},
    )
    logger.info(f"radio: fleet thread {thread.id} attached to chain {chain_id}")

    # P0 org telemetry (write-only; never raises) — rides the caller's
    # transaction: _recruit_fleet commits moments later when propagating
    # radio_thread_id onto the ChainLinks.
    try:
        from core.org_telemetry_service import emit_org_event

        emit_org_event(
            db,
            "radio_thread_attach",
            actor_agent_id=created_by_agent_id,
            target_agent_id=chain_id,
            chain_id=chain_id,
            execution_id=execution_id,
            tenant_id=tenant_id,
            payload={"thread_id": thread.id, "team": list(team_agent_ids)},
            commit=False,
        )
    except Exception as e:  # noqa: BLE001 — telemetry must never raise
        logger.debug(f"org telemetry attach emit skipped: {e}")

    if execution_id:
        execution = (
            db.query(AgentExecution)
            .filter(AgentExecution.id == execution_id)
            .first()
        )
        if execution is not None:
            execution.thread_id = thread.id
            db.commit()
    return thread


def execution_thread_id(execution_id: str) -> Optional[str]:
    """Resolve the radio thread attached to an execution (loop-hook helper)."""
    try:
        from core.database import get_db_session

        with get_db_session() as db:
            execution = (
                db.query(AgentExecution)
                .filter(AgentExecution.id == execution_id)
                .first()
            )
            return execution.thread_id if execution else None
    except Exception as e:  # pragma: no cover - defensive
        logger.debug(f"radio execution thread lookup failed: {e}")
        return None