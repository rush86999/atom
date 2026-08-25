"""Reviewer re-delegation loop (W3, P4c).

When the REVIEW strategy (P4b, ``ReviewerVerifier``) rejects the winning
candidate, the winning answer is NOT swapped for another candidate — the
originating specialist is re-delegated with the reviewer's feedback and
given one more chance (up to ``MAX_REVIEWER_REDELEGATIONS``). The workflow
is parked in the WAITING state for the duration of a re-delegation
(RUNNING→WAITING is already a valid transition in
``WorkflowStateMachine.VALID_TRANSITIONS``; this module wires the
transition through the guard/pre-action/post-action hooks so review
metadata is observable) and resumed when the specialist re-runs the step.

Kill switch: ``ATOM_REVIEWER_LOOP_ENABLED=false`` (default) restores the
legacy behavior — a REVIEW rejection is folded into the voting fallback
by the orchestrator (the universal safety net).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, Optional

from core.orchestration.workflow_state_machine import (
    TransitionResult,
    WorkflowState,
    WorkflowStateMachine,
    get_state_machine,
)

logger = logging.getLogger(__name__)

# Kill switch. Read at call time (like ``core.hallucination_config._flag``) so
# tests can monkeypatch the env var; the module-level constant is kept for
# import-time readers.
REVIEWER_LOOP_ENABLED = os.getenv("ATOM_REVIEWER_LOOP_ENABLED", "false").lower() == "true"


def reviewer_loop_enabled() -> bool:
    # Env wins > runtime_settings DB row (UI admin) > default.
    from core.runtime_settings import get_bool_setting

    return get_bool_setting("ATOM_REVIEWER_LOOP_ENABLED", False)

# Number of re-delegations after the initial pass (1 initial + 2 retries).
MAX_REVIEWER_REDELEGATIONS = 2

_FEEDBACK_PARAM = "_review_feedback"

_hooked_machines: set[int] = set()


def is_review_rejection(result: Any) -> bool:
    """True iff ``result`` is a REVIEW verdict that rejected the candidate.

    The reviewer signals re-delegation via ``winner=None`` +
    ``details.accepted is False`` (see ``ReviewerVerifier.verify``).
    """
    strategy = getattr(result, "strategy", None)
    if strategy is None or getattr(strategy, "value", strategy) != "review":
        return False
    details = getattr(result, "details", None) or {}
    return details.get("accepted") is False


def attach_review_feedback(step: Any, feedback: str) -> None:
    """Stash the reviewer's feedback on the step for the re-delegated run."""
    if not isinstance(getattr(step, "parameters", None), dict):
        step.parameters = {}
    step.parameters[_FEEDBACK_PARAM] = feedback
    step.retry_count = getattr(step, "retry_count", 0) + 1


def get_review_feedback(step: Any) -> str:
    """Return the reviewer feedback previously attached to ``step``."""
    params = getattr(step, "parameters", None)
    if not isinstance(params, dict):
        return ""
    return str(params.get(_FEEDBACK_PARAM, ""))


def enter_review_waiting(
    machine: WorkflowStateMachine,
    workflow_id: str,
    execution_id: str,
    feedback: str,
) -> TransitionResult:
    """Park the workflow in WAITING while a re-delegation is in flight."""
    return machine.transition(
        workflow_id,
        execution_id or f"exec_{workflow_id}",
        WorkflowState.WAITING,
        reason="reviewer re-delegation pending",
        context={"pending_review": True, "review_feedback": feedback},
    )


def resume_after_review(
    machine: WorkflowStateMachine,
    workflow_id: str,
    execution_id: str,
) -> TransitionResult:
    """Return the workflow to RUNNING once the re-delegated step completes."""
    return machine.transition(
        workflow_id,
        execution_id or f"exec_{workflow_id}",
        WorkflowState.RUNNING,
        reason="reviewer re-delegation resolved",
        context={"pending_review": False},
    )


# ---------------------------------------------------------------------------
# State machine hooks (RUNNING → WAITING via guard/pre/post actions)
# ---------------------------------------------------------------------------


def _review_wait_guard(context: Dict[str, Any]) -> bool:
    """Guard for RUNNING→WAITING.

    Default-allow (external-input waits are legitimate without review
    metadata); review-parked transitions are always allowed. The guard
    exists so the hook is registered and any future policy (e.g. max
    concurrent re-delegations) has a single enforcement point.
    """
    return True


def _review_wait_pre_action(workflow_id: str, context: Dict[str, Any]) -> None:
    logger.debug(
        "Review wait pre-action: %s pending_review=%s",
        workflow_id, context.get("pending_review"),
    )


def _review_wait_post_action(workflow_id: str, context: Dict[str, Any]) -> None:
    """Record review metadata when the transition was review-driven."""
    if context.get("pending_review"):
        logger.info(
            "REVIEWER LOOP: workflow %s parked in WAITING (pending re-delegation, "
            "feedback=%r)", workflow_id, context.get("review_feedback", "")[:200],
        )


def install_state_machine_hooks(machine: WorkflowStateMachine) -> None:
    """Register the RUNNING→WAITING guard + pre/post actions (idempotent)."""
    key = id(machine)
    if key in _hooked_machines:
        return
    machine.add_guard(WorkflowState.RUNNING, WorkflowState.WAITING, _review_wait_guard)
    machine.add_pre_action(WorkflowState.RUNNING, WorkflowState.WAITING, _review_wait_pre_action)
    machine.add_post_action(WorkflowState.RUNNING, WorkflowState.WAITING, _review_wait_post_action)
    _hooked_machines.add(key)
    logger.debug("Installed reviewer-loop hooks on RUNNING→WAITING (%s)", key)


def get_review_loop_state_machine() -> WorkflowStateMachine:
    """Return the shared state machine with the reviewer-loop hooks installed."""
    machine = get_state_machine()
    install_state_machine_hooks(machine)
    return machine
