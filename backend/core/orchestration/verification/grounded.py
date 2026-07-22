"""Grounded verifier — LLM faithfulness check for factual QA / RAG.

For factual QA, the swarm shouldn't vote on *facts* — it should check
each candidate's *faithfulness to the retrieved sources* and then
prefer a grounded answer. This verifier asks an LLM, for each
candidate, whether the answer is fully supported by the provided
sources; the first candidate judged grounded wins.

Sources are read from, in priority order:

  * ``step.parameters["sources"]`` — a list of strings or a single string.
  * ``context.shared_context.get("retrieved_context")`` — same shape.

Mirrors the :class:`~core.llm.action_judge.ActionJudge` pattern:
duck-typed ``llm_service`` (tries ``complete`` / ``generate`` /
``invoke``), ``asyncio.wait_for`` timeout, circuit breaker. The judge
never raises — on timeout, circuit-open, missing sources, or no LLM
service, ``winner=None`` is returned and the orchestrator falls back
to voting.

Note: the Field Guide survey's caveat that "Debate or Vote" found
debate adds little over voting applies here too — we use a single
faithfulness pass, not multi-round debate.
"""
from __future__ import annotations

import asyncio
import logging
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
            return True  # half-open probe
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold and self._opened_at is None:
            self._opened_at = time.time()
            logger.warning(
                "GroundedVerifier circuit opened after %d failures", self._failures
            )


class GroundedVerifier(Verifier):
    """LLM faithfulness check against retrieved sources."""

    strategy = VerificationStrategy.GROUNDED

    def __init__(
        self,
        llm_service: Any = None,
        *,
        timeout_seconds: float = 8.0,
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

        sources = self._collect_sources(step, context)
        if not sources:
            return VerificationResult.empty(
                domain, self.strategy,
                reason="no sources available for grounding check",
            )

        if self.llm_service is None:
            return VerificationResult.empty(
                domain, self.strategy,
                reason="no LLM service configured for grounding check",
            )

        if not self._circuit.allow():
            return VerificationResult.empty(
                domain, self.strategy, reason="circuit open (fail-open)",
            )

        checks: List[Dict[str, Any]] = []
        for idx, candidate in enumerate(candidates):
            answer = self._stringify(candidate)
            try:
                grounded = await asyncio.wait_for(
                    self._check_faithfulness(answer, sources),
                    timeout=self.timeout_seconds,
                )
                self._circuit.record_success()
            except asyncio.TimeoutError:
                self._circuit.record_failure()
                checks.append({"index": idx, "grounded": False, "reason": "timeout"})
                continue
            except Exception as exc:  # noqa: BLE001 — never crash the swarm
                self._circuit.record_failure()
                checks.append({"index": idx, "grounded": False, "reason": f"error: {exc}"})
                continue

            checks.append({
                "index": idx,
                "grounded": grounded["grounded"],
                "rationale": grounded["rationale"],
            })
            if grounded["grounded"]:
                return VerificationResult(
                    winner=candidate,
                    strategy=self.strategy,
                    domain=domain,
                    confidence=1.0,
                    details={
                        "winning_index": idx,
                        "candidate_count": len(candidates),
                        "checks": checks,
                    },
                    reason="first candidate judged grounded against the sources",
                )

        return VerificationResult(
            winner=None,
            strategy=self.strategy,
            domain=domain,
            confidence=0.0,
            details={"checks": checks, "candidate_count": len(candidates)},
            reason="no candidate judged grounded against the sources",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _collect_sources(step: Any, context: Any) -> str:
        params = getattr(step, "parameters", None) or {}
        raw = params.get("sources")
        if raw is None:
            shared = getattr(context, "shared_context", None) or {}
            if isinstance(shared, dict):
                raw = shared.get("retrieved_context")
        if raw is None:
            return ""
        if isinstance(raw, str):
            return raw
        if isinstance(raw, (list, tuple)):
            return "\n\n".join(str(s) for s in raw)
        return str(raw)

    @staticmethod
    def _stringify(candidate: Any) -> str:
        if isinstance(candidate, dict):
            for key in ("answer", "output", "text", "result"):
                val = candidate.get(key)
                if val is not None:
                    return str(val)
        return str(candidate)

    async def _check_faithfulness(self, answer: str, sources: str) -> Dict[str, Any]:
        """Ask the LLM whether ``answer`` is supported by ``sources``."""
        prompt = (
            "You are a strict fact-checker. Given the SOURCES below and a "
            "candidate ANSWER, decide whether every claim in the answer is "
            "fully supported by the sources. Respond on the first line with "
            "exactly YES or NO, then on the next line give a one-sentence "
            "rationale.\n\n"
            f"=== SOURCES ===\n{sources}\n\n"
            f"=== ANSWER ===\n{answer}\n\n"
            "Verdict (YES/NO) on the first line:"
        )
        response = await self._call_llm(prompt)
        first_line = (response.strip().splitlines() or [""])[0].strip().upper()
        grounded = first_line.startswith("YES")
        rationale = ""
        lines = response.strip().splitlines()
        if len(lines) > 1:
            rationale = lines[1].strip()
        return {"grounded": grounded, "rationale": rationale}

    async def _call_llm(self, prompt: str) -> str:
        """Duck-typed LLM call — mirrors action_judge._call_llm."""
        svc = self.llm_service
        for method_name in ("complete", "generate", "invoke"):
            method = getattr(svc, method_name, None)
            if callable(method):
                try:
                    result = method(prompt)
                    if asyncio.iscoroutine(result):
                        result = await result
                    return str(result)
                except Exception:  # noqa: BLE001 — try next method name
                    continue
        raise RuntimeError(
            f"LLM service {type(svc).__name__} has no callable complete/generate/invoke"
        )


__all__ = ["GroundedVerifier"]
