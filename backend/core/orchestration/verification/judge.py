"""Judge verifier — LLM-as-judge ranking for open-ended prose.

For open-ended tasks (writing, summarisation, reviews) there is no
cheap ground-truth signal; "correct" is subjective quality. This
verifier asks an LLM to rank all N candidates for the task and returns
the top-ranked one (a Borda-style aggregation over a single ranking).

This is the right tool *only* when no stronger signal is available —
the Field Guide survey (§4.3) and the "LLMs as a Jury" comparison both
note LLM judges are subject to positional and verbosity biases. The
mitigations here are the standard ones: the prompt presents candidates
in a neutral, numbered form and shuffles the display order before each
call. The orchestrator only reaches this strategy for the PROSE domain
by default.

Mirrors the :class:`~core.llm.action_judge.ActionJudge` pattern:
duck-typed ``llm_service``, ``asyncio.wait_for`` timeout, circuit
breaker. On any failure, ``winner=None`` and the orchestrator falls
back to voting.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional

from core.orchestration.verification.base import (
    VerificationResult,
    VerificationStrategy,
    Verifier,
)

logger = logging.getLogger(__name__)


class _CircuitBreaker:
    """Minimal circuit breaker — mirrors action_judge._CircuitBreaker."""

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: int = 120) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._failures = 0
        self._opened_at: Optional[float] = None

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        if time.time() - self._opened_at >= self.cooldown_seconds:
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold and self._opened_at is None:
            self._opened_at = time.time()
            logger.warning(
                "JudgeVerifier circuit opened after %d failures", self._failures
            )


class JudgeVerifier(Verifier):
    """LLM-as-judge ranks the candidates; top-ranked wins."""

    strategy = VerificationStrategy.JUDGE

    def __init__(
        self,
        llm_service: Any = None,
        *,
        timeout_seconds: float = 10.0,
        circuit_threshold: int = 5,
        circuit_cooldown: int = 120,
    ) -> None:
        self.llm_service = llm_service
        self.timeout_seconds = timeout_seconds
        self._circuit = _CircuitBreaker(circuit_threshold, circuit_cooldown)

    async def verify(
        self,
        candidates: List[Any],
        step: Any,
        context: Any,
    ) -> VerificationResult:
        domain = getattr(context, "_resolved_domain", None) or "unknown"

        if not candidates:
            return VerificationResult.empty(domain, self.strategy, reason="no candidates")

        if len(candidates) == 1:
            # Nothing to judge — the single candidate is the answer.
            return VerificationResult(
                winner=candidates[0],
                strategy=self.strategy,
                domain=domain,
                confidence=1.0,
                details={"candidate_count": 1},
                reason="only one candidate",
            )

        if self.llm_service is None:
            return VerificationResult.empty(
                domain, self.strategy,
                reason="no LLM service configured for judging",
            )

        if not self._circuit.allow():
            return VerificationResult.empty(
                domain, self.strategy, reason="circuit open (fail-open)",
            )

        task_desc = self._task_description(step)
        display_order = list(range(len(candidates)))
        random.shuffle(display_order)

        try:
            ranking = await asyncio.wait_for(
                self._rank(candidates, display_order, task_desc),
                timeout=self.timeout_seconds,
            )
            self._circuit.record_success()
        except asyncio.TimeoutError:
            self._circuit.record_failure()
            return VerificationResult.empty(
                domain, self.strategy, reason=f"LLM timeout after {self.timeout_seconds}s",
            )
        except Exception as exc:  # noqa: BLE001 — never crash the swarm
            self._circuit.record_failure()
            return VerificationResult.empty(
                domain, self.strategy, reason=f"LLM error: {exc}",
            )

        if not ranking:
            return VerificationResult.empty(
                domain, self.strategy, reason="judge returned an unparseable ranking",
            )

        # ranking is a list of *display positions* best-first. Map back
        # to the original candidate index.
        winner_orig = display_order[ranking[0]]
        return VerificationResult(
            winner=candidates[winner_orig],
            strategy=self.strategy,
            domain=domain,
            confidence=1.0 / len(ranking) if len(ranking) > 1 else 1.0,
            details={
                "winning_index": winner_orig,
                "candidate_count": len(candidates),
                "ranking_display_positions": ranking,
                "display_order": display_order,
            },
            reason="top-ranked by LLM judge",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _task_description(step: Any) -> str:
        """Pull a free-text description of what the candidates should do."""
        for attr in ("description", "name", "capability"):
            val = getattr(step, attr, None)
            if val:
                return str(val)
        params = getattr(step, "parameters", None) or {}
        if isinstance(params, dict):
            prompt = params.get("prompt") or params.get("task")
            if prompt:
                return str(prompt)
        return "(no task description provided)"

    @staticmethod
    def _stringify(candidate: Any) -> str:
        if isinstance(candidate, dict):
            for key in ("output", "text", "answer", "result"):
                val = candidate.get(key)
                if val is not None:
                    return str(val)
        return str(candidate)

    async def _rank(
        self,
        candidates: List[Any],
        display_order: List[int],
        task_desc: str,
    ) -> List[int]:
        """Ask the LLM to rank candidates; return display positions best-first."""
        lines = [f"TASK: {task_desc}", "", "CANDIDATES (numbered for reference):"]
        for display_pos, orig_idx in enumerate(display_order):
            text = self._stringify(candidates[orig_idx])
            # Cap candidate length so a single verbose answer can't
            # blow the prompt budget.
            if len(text) > 4000:
                text = text[:4000] + "…[truncated]"
            lines.append(f"[{display_pos}] {text}")
        lines.append("")
        lines.append(
            "Rank these candidates from best to worst for the task. "
            "Reply with ONLY a comma-separated list of the bracketed numbers, "
            "best first. Example: 2, 0, 1"
        )
        prompt = "\n".join(lines)

        response = await self._call_llm(prompt)
        return self._parse_ranking(response, len(display_order))

    @staticmethod
    def _parse_ranking(response: str, n: int) -> List[int]:
        """Parse a response like '2, 0, 1' into [2, 0, 1]."""
        # Grab the first comma-separated run of integers we can find.
        text = response.strip()
        # tolerate leading prose by finding the first digit run.
        tokens: List[int] = []
        for tok in text.replace(";", ",").split(","):
            tok = tok.strip().lstrip("[").rstrip("]")
            if tok.isdigit():
                val = int(tok)
                if 0 <= val < n and val not in tokens:
                    tokens.append(val)
        # Backfill any candidates the judge omitted (ranked last).
        for i in range(n):
            if i not in tokens:
                tokens.append(i)
        return tokens

    async def _call_llm(self, prompt: str) -> str:
        svc = self.llm_service
        for method_name in ("complete", "generate", "invoke"):
            method = getattr(svc, method_name, None)
            if callable(method):
                try:
                    result = method(prompt)
                    if asyncio.iscoroutine(result):
                        result = await result
                    return str(result)
                except Exception:  # noqa: BLE001
                    continue
        raise RuntimeError(
            f"LLM service {type(svc).__name__} has no callable complete/generate/invoke"
        )


__all__ = ["JudgeVerifier"]
