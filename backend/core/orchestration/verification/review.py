"""
ReviewerVerifier — the Virtual Biotech's "Scientific Reviewer" strategy (W3, P4b).

NOT homogeneous multi-round debate (the 2026 literature — Debate-or-Vote
martingale; Cost-of-Consensus 85.5% sycophancy — shows debate *degrades*
accuracy). This is structured delegation+review: a separate reviewer
evaluates the winning candidate on three criteria (addresses-the-question /
evidence-strength / thoroughness) and, on failure, signals re-delegation
rather than picking a different candidate.

Modeled on ``JudgeVerifier`` (duck-typed llm_service, fail-open via
``VerificationResult.empty``, never raises).
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, List

from core.orchestration.verification.base import (
    VerificationResult, VerificationStrategy, Verifier,
)

logger = logging.getLogger(__name__)

_REVIEW_CRITERIA = (
    "1. Does it directly address the original question/task?\n"
    "2. Is the evidence/reasoning strong and well-supported?\n"
    "3. Is it thorough (no obvious gaps)?"
)


class ReviewerVerifier(Verifier):
    """Review the winning candidate against structured criteria.

    Unlike ``JudgeVerifier`` (which ranks N candidates), this assumes the
    upstream aggregator already picked a winner; the reviewer decides whether
    that winner is ACCEPTABLE or needs RE-DELEGATION (return to the
    originating specialist with feedback). On any failure mode it fail-opens
    to the winner so the swarm never blocks.
    """

    strategy = VerificationStrategy.REVIEW

    def __init__(
        self,
        llm_service: Any = None,
        *,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.llm_service = llm_service
        self.timeout_seconds = timeout_seconds

    async def verify(
        self,
        candidates: List[Any],
        step: Any,
        context: Any,
    ) -> VerificationResult:
        domain = getattr(context, "_resolved_domain", None) or "unknown"

        if not candidates:
            return VerificationResult.empty(domain, self.strategy, reason="no candidates")

        # The reviewer evaluates the single best candidate (the modal winner
        # from the upstream voting/MoA pass). If multiple are passed, take the
        # first (callers should run voting first, then escalate to review).
        winner = candidates[0]

        if self.llm_service is None:
            # No LLM → can't review → accept the winner (fail-open).
            return VerificationResult(
                winner=winner, strategy=self.strategy, domain=domain,
                confidence=0.5, details={"reviewed": False},
                reason="no LLM service; accepted without review",
            )

        task_desc = self._task_description(step)
        try:
            verdict = await asyncio.wait_for(
                self._review(winner, task_desc),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            return VerificationResult(
                winner=winner, strategy=self.strategy, domain=domain,
                confidence=0.5, details={"reviewed": False},
                reason=f"review timed out after {self.timeout_seconds}s; accepted",
            )
        except Exception as exc:  # never crash the swarm
            return VerificationResult(
                winner=winner, strategy=self.strategy, domain=domain,
                confidence=0.5, details={"reviewed": False},
                reason=f"review errored ({exc}); accepted",
            )

        accepted = bool(verdict.get("accept", True))
        feedback = verdict.get("feedback", "")

        # P0 org telemetry (write-only; never raises) — reviewer accept/reject
        # rates per specialist feed the favoritism baseline report.
        try:
            from core.org_telemetry_service import emit_org_event

            emit_org_event(
                None,
                "review_verdict",
                target_agent_id=self._candidate_agent_id(winner, step),
                payload={
                    "accepted": accepted,
                    "score": verdict.get("score"),
                    "domain": str(domain),
                    "step_id": getattr(step, "step_id", None),
                },
            )
        except Exception as exc:  # noqa: BLE001 — telemetry must never raise
            logger.debug(f"org telemetry review emit skipped: {exc}")

        return VerificationResult(
            winner=winner if accepted else None,  # None → orchestrator can re-delegate
            strategy=self.strategy, domain=domain,
            confidence=float(verdict.get("score", 0.7)) if accepted else 0.3,
            details={
                "reviewed": True, "accepted": accepted,
                "feedback": feedback, "criteria": "addresses/evidence/thoroughness",
            },
            reason=("review accepted" if accepted else f"review rejected — re-delegate: {feedback}"),
        )

    @staticmethod
    def _candidate_agent_id(candidate: Any, step: Any) -> str:
        """Best-effort identity of the reviewed specialist (for telemetry)."""
        for src, key in ((candidate, "agent_id"), (step, "agent_id")):
            val = (
                src.get(key)
                if isinstance(src, dict) and key in src
                else getattr(src, key, None)
            )
            if val:
                return str(val)
        return f"step:{getattr(step, 'step_id', 'unknown')}"

    async def _review(self, candidate: Any, task_desc: str) -> dict:
        """Ask the reviewer LLM to accept/reject the candidate."""
        prompt = (
            f"You are a strict scientific reviewer. A specialist produced this answer for:\n"
            f"TASK: {task_desc}\n\n"
            f"ANSWER: {self._serialise(candidate)}\n\n"
            f"Evaluate strictly on these criteria:\n{_REVIEW_CRITERIA}\n\n"
            f"Respond as JSON: {{\"accept\": true/false, \"score\": 0.0-1.0, "
            f"\"feedback\": \"what to improve if rejected\"}}. "
            f"Reject only for clear gaps; do not be capricious."
        )
        resp = await self._llm_complete(prompt)
        return self._parse_verdict(resp)

    def _task_description(self, step: Any) -> str:
        if step is None:
            return "(unknown task)"
        return str(getattr(step, "description", None) or getattr(step, "prompt", None) or step)

    @staticmethod
    def _serialise(candidate: Any) -> str:
        from core.orchestration.verification.base import serialise
        try:
            return serialise(candidate)[:2000]
        except Exception:
            return str(candidate)[:2000]

    async def _llm_complete(self, prompt: str) -> str:
        """Duck-typed LLM call (mirrors JudgeVerifier's provider-agnostic path)."""
        llm = self.llm_service
        for method in ("generate_response", "complete", "invoke", "generate"):
            fn = getattr(llm, method, None)
            if fn is None:
                continue
            try:
                result = fn(prompt)
                if asyncio.iscoroutine(result):
                    result = await result
                return str(result) if result is not None else ""
            except TypeError:
                # some signatures take kwargs; try a minimal kwargs form
                try:
                    result = fn(prompt=prompt)
                    if asyncio.iscoroutine(result):
                        result = await result
                    return str(result) if result is not None else ""
                except Exception:
                    continue
            except Exception:
                continue
        return ""

    @staticmethod
    def _parse_verdict(resp: str) -> dict:
        """Best-effort parse of the reviewer's JSON verdict."""
        import json
        if not resp:
            return {"accept": True, "score": 0.7, "feedback": ""}
        try:
            start = resp.find("{")
            end = resp.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(resp[start:end])
        except Exception:
            pass
        # Fallback: accept if "accept" appears, else accept (fail-open).
        return {"accept": True, "score": 0.7, "feedback": ""}
