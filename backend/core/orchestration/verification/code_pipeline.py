"""CODE_PIPELINE verifier — reconcile agent action dicts, then execute code.

Coding steps have two distinct concerns that a single strategy conflates:

  1. **Coordination** — when 3 parallel coding agents disagree on *what to
     do* (which file to read, which action to take), the per-key frequency
     reconciler (originally ``ConductorAgent._reconcile_branch_conflicts``)
     merges the non-conflicting portions of their action dicts.
  2. **Correctness** — once you have a merged candidate that *contains code*,
     you still need to verify the code actually runs and passes tests
     (AlphaCodium: the sandbox is the oracle).

This verifier composes those two stages. It is the strategy the orchestrator
routes the :attr:`~core.orchestration.verification.domain.TaskDomain.CODE`
domain to by default.

Flow:
::

    candidates (coding-agent outputs: action dicts and/or code)
       │
       ├─ Stage 1 — RECONCILE  (VotingVerifier)
       │    merge divergent action dicts via majority + per-key freq vote
       │    → merged_candidate (or majority winner if all-distinct)
       │
       ├─ Stage 2 — EXECUTE  (ExecutionVerifier)
       │    extract code from merged_candidate (code/source/output keys)
       │    if code found → run in sandbox against the step's tests spec
       │       passes → return merged_candidate (verified)           ✓
       │       fails  → winner=None (correctness gate → orchestrator
       │                                    falls back to voting)
       │    if no code found → return reconciled winner (stage 2 n/a)
       │
       └─ result.details carries both stages' diagnostics

Graceful degradation:
  * Stage 1 always returns something (VotingVerifier falls back to the
    majority winner on empty reconciliation).
  * If the merged candidate carries no code (a pure action plan, e.g.
    ``{"action":"read","target":"f.py"}``), stage 2 is skipped and the
    reconciled winner is returned — preserving the original reconciler's
    behaviour for coordination-only steps.
  * If the sandbox is unavailable, stage 2 is skipped (not fatal) and the
    reconciled winner is returned.
  * If code is present but fails tests, ``winner=None`` is returned — this
    is the correctness gate the original reconciler lacked. The
    orchestrator's universal voting fallback then applies.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from core.orchestration.verification.base import (
    VerificationResult,
    VerificationStrategy,
    Verifier,
)
from core.orchestration.verification.execution import ExecutionVerifier
from core.orchestration.verification.voting import VotingVerifier

logger = logging.getLogger(__name__)


class CodePipelineVerifier(Verifier):
    """Two-stage CODE verifier: reconcile agent action dicts, then execute code."""

    strategy = VerificationStrategy.CODE_PIPELINE

    def __init__(
        self,
        sandbox_runtime: Any = None,
        *,
        voting_verifier: Optional[VotingVerifier] = None,
        execution_verifier: Optional[ExecutionVerifier] = None,
    ) -> None:
        # Allow tests / advanced wiring to inject either stage; otherwise
        # build fresh instances that share the (optional) sandbox runtime.
        self._voting = voting_verifier or VotingVerifier()
        if execution_verifier is not None:
            self._execution = execution_verifier
        else:
            self._execution = ExecutionVerifier(sandbox_runtime=sandbox_runtime)

    async def verify(
        self,
        candidates: list,
        step: Any,
        context: Any,
    ) -> VerificationResult:
        domain = getattr(context, "_resolved_domain", None) or "unknown"

        if not candidates:
            return VerificationResult.empty(
                domain, self.strategy, reason="no candidates",
            )

        # ── Stage 1: reconcile divergent action dicts ────────────────────
        stage1 = await self._voting.verify(candidates, step, context)
        reconciled = stage1.winner

        if reconciled is None:
            # Voting itself produced nothing (e.g. empty candidate list —
            # already handled above, but defensive). No point executing.
            return VerificationResult(
                winner=None,
                strategy=self.strategy,
                domain=domain,
                confidence=0.0,
                details={"stage_1": stage1.details, "stage_2": {"skipped": True}},
                reason="reconcile stage produced no candidate",
            )

        # ── Stage 2: execute the reconciled code ─────────────────────────
        code = ExecutionVerifier._extract_code(reconciled)
        if not code:
            # Pure action plan (e.g. {"action":"read","target":"f.py"}) —
            # there's nothing to execute. The reconciled winner is the
            # answer, exactly as the original reconciler returned.
            return VerificationResult(
                winner=reconciled,
                strategy=self.strategy,
                domain=domain,
                confidence=stage1.confidence,
                details={
                    "stage_1": stage1.details,
                    "stage_2": {"skipped": True, "reason": "no code in reconciled candidate"},
                },
                reason="reconciled action dicts; no code to execute",
            )

        # Run the execution verifier against just the reconciled winner.
        exec_result = await self._execution.verify([reconciled], step, context)

        if exec_result.winner is not None:
            # Code compiled/ran and passed the tests spec.
            return VerificationResult(
                winner=reconciled,
                strategy=self.strategy,
                domain=domain,
                confidence=1.0,
                details={
                    "stage_1": stage1.details,
                    "stage_2": exec_result.details,
                },
                reason="reconciled action dicts; code passed execution verification",
            )

        # Execution produced no winner. Distinguish two cases:
        #   * sandbox infra unavailable (no Docker, runtime raised at
        #     acquisition) → NOT a correctness failure. Skip stage 2 and
        #     return the reconciled winner; reconcile-only is still
        #     valuable and the original reconciler had no execution gate
        #     at all.
        #   * code ran but failed the tests spec → correctness gate
        #     trips. Return winner=None so the orchestrator falls back
        #     to voting. This is the new signal the original reconciler
        #     lacked.
        reason = exec_result.reason or ""
        if "sandbox runtime unavailable" in reason or "sandbox unavailable" in reason:
            logger.info(
                "CODE_PIPELINE: sandbox unavailable for step %s; skipping execution stage "
                "(returning reconciled winner)",
                getattr(step, "step_id", "?"),
            )
            return VerificationResult(
                winner=reconciled,
                strategy=self.strategy,
                domain=domain,
                confidence=stage1.confidence,
                details={
                    "stage_1": stage1.details,
                    "stage_2": {"skipped": True, "reason": reason},
                },
                reason=f"reconciled action dicts; execution skipped ({reason})",
            )

        # Code present but failed execution — correctness gate trips.
        logger.info(
            "CODE_PIPELINE: reconciled candidate failed execution for step %s; "
            "returning winner=None (correctness gate)",
            getattr(step, "step_id", "?"),
        )
        return VerificationResult(
            winner=None,
            strategy=self.strategy,
            domain=domain,
            confidence=0.0,
            details={
                "stage_1": stage1.details,
                "stage_2": exec_result.details,
                "stage_2_reason": exec_result.reason,
            },
            reason=f"reconciled code failed execution: {exec_result.reason}",
        )


__all__ = ["CodePipelineVerifier"]
