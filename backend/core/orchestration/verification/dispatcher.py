"""Verification orchestrator — the cascade dispatcher.

This is the entry point the Conductor calls. For each step it:

  1. Resolves the task domain (explicit tag or heuristic inference).
  2. Resolves the verification strategy (explicit override or the
     domain→strategy map).
  3. Runs the matching verifier.
  4. If the verifier returns ``winner=None`` and the strategy wasn't
     VOTING, transparently falls back to voting.
  5. When the domain was *inferred* (not explicit), records a Field
     Guide insight noting the (domain, strategy, outcome) — so the
     workspace accumulates feedback on which inferences pay off.

The orchestrator never raises; verifier failures are logged and turned
into a voting fallback. This is the "universal safety net": the swarm
is never worse off than the original single-strategy behaviour.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.orchestration.verification.base import (
    VerificationResult,
    VerificationStrategy,
    Verifier,
    replace,
)
from core.orchestration.verification.code_pipeline import CodePipelineVerifier
from core.orchestration.verification.domain import (
    DOMAIN_STRATEGY_MAP,
    TaskDomain,
    infer_domain,
    resolve_domain,
    resolve_strategy,
)
from core.orchestration.verification.execution import ExecutionVerifier
from core.orchestration.verification.formal import FormalVerifier
from core.orchestration.verification.grounded import GroundedVerifier
from core.orchestration.verification.judge import JudgeVerifier
from core.orchestration.verification.schema_verifier import SchemaVerifier
from core.orchestration.verification.voting import VotingVerifier

logger = logging.getLogger(__name__)

_FIELD_GUIDE_TOPIC = "Verification Feedback"


class VerificationOrchestrator:
    """Pick a verifier per domain, run it, fall back to voting on failure.

    All collaborators (``llm_service``, ``sandbox_runtime``,
    ``field_guide_service``) are optional — the orchestrator works
    with none of them wired, in which case every domain-specific
    strategy degrades to voting. This is deliberate: it lets the
    cascade land in the codebase today and light up incrementally as
    dependencies are wired.
    """

    def __init__(
        self,
        *,
        llm_service: Any = None,
        field_guide_service: Any = None,
        sandbox_runtime: Any = None,
        domain_strategy_map: Optional[Dict[TaskDomain, VerificationStrategy]] = None,
        verifiers: Optional[Dict[VerificationStrategy, Verifier]] = None,
    ) -> None:
        self.llm_service = llm_service
        self.field_guide_service = field_guide_service
        self._domain_strategy_map = domain_strategy_map or dict(DOMAIN_STRATEGY_MAP)

        if verifiers is not None:
            # Test seam / advanced wiring — lets a caller override any
            # individual verifier (e.g. inject a mock sandbox runtime).
            self._verifiers = dict(verifiers)
        else:
            self._verifiers: Dict[VerificationStrategy, Verifier] = {
                VerificationStrategy.VOTING: VotingVerifier(),
                VerificationStrategy.SCHEMA: SchemaVerifier(),
                VerificationStrategy.EXECUTION: ExecutionVerifier(sandbox_runtime),
                VerificationStrategy.FORMAL: FormalVerifier(),
                VerificationStrategy.GROUNDED: GroundedVerifier(llm_service),
                VerificationStrategy.JUDGE: JudgeVerifier(llm_service),
                VerificationStrategy.CODE_PIPELINE: CodePipelineVerifier(sandbox_runtime),
            }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def verify(
        self,
        candidates: list,
        step: Any,
        context: Any,
    ) -> VerificationResult:
        """Verify ``candidates`` for ``step`` and return a result.

        Never raises. The winner is in ``result.winner`` (may be
        ``None`` only if voting itself produced nothing — e.g. an empty
        candidate list).
        """
        explicit_domain = self._explicit_domain(step)
        domain = resolve_domain(step) if explicit_domain is None else explicit_domain
        strategy = resolve_strategy(step, domain, self._domain_strategy_map)

        # Stash the resolved domain on the context so verifiers can
        # surface it in their results without each re-resolving it.
        # Duck-typed: tests pass a plain object that allows setattr.
        self._stamp_context(context, domain)

        try:
            result = await self._run_strategy(strategy, candidates, step, context)
        except Exception as exc:  # noqa: BLE001 — never crash the swarm
            logger.warning(
                "Strategy %s raised for step %s; falling back to voting: %s",
                strategy.value, getattr(step, "step_id", "?"), exc,
            )
            result = await self._run_strategy(
                VerificationStrategy.VOTING, candidates, step, context
            )
            result = replace(result, fallback_used=True, reason=f"strategy {strategy.value} raised: {exc}")

        # Universal fallback: any non-voting strategy that fails to pick
        # a winner falls through to voting.
        if result.winner is None and strategy != VerificationStrategy.VOTING:
            logger.info(
                "Strategy %s produced no winner for step %s; falling back to voting",
                strategy.value, getattr(step, "step_id", "?"),
            )
            vote_result = await self._run_strategy(
                VerificationStrategy.VOTING, candidates, step, context
            )
            # Preserve the original strategy + domain on the result so
            # callers can see *what was attempted*, but mark the fallback.
            result = replace(
                vote_result,
                fallback_used=True,
                strategy=strategy,
                domain=domain,
                reason=f"{strategy.value} → voting fallback",
                details={**(vote_result.details or {}), "attempted_strategy": strategy.value},
            )

        self._record_feedback(step, context, domain, strategy, result, explicit_domain)
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    async def _run_strategy(
        self,
        strategy: VerificationStrategy,
        candidates: list,
        step: Any,
        context: Any,
    ) -> VerificationResult:
        verifier = self._verifiers.get(strategy)
        if verifier is None:
            return VerificationResult.empty(
                getattr(context, "_resolved_domain", TaskDomain.UNKNOWN),
                strategy,
                reason=f"no verifier registered for strategy {strategy.value}",
            )
        return await verifier.verify(candidates, step, context)

    @staticmethod
    def _explicit_domain(step: Any) -> Optional[TaskDomain]:
        """Return the domain iff it was set explicitly, else None.

        Used to decide whether to record an inference-feedback insight.
        """
        params = getattr(step, "parameters", None)
        if not isinstance(params, dict):
            return None
        raw = params.get("task_domain")
        if raw is None:
            return None
        if isinstance(raw, TaskDomain):
            return raw
        if isinstance(raw, str):
            norm = raw.strip().lower()
            for member in TaskDomain:
                if member.value == norm or member.name.lower() == norm:
                    return member
        return None

    @staticmethod
    def _stamp_context(context: Any, domain: TaskDomain) -> None:
        """Attach the resolved domain to the context for verifiers to read.

        Best-effort: if the context is immutable or doesn't support
        attribute assignment, verifiers fall back to ``"unknown"``.
        """
        try:
            # Bypass __setattr__ restrictions where possible.
            object.__setattr__(context, "_resolved_domain", domain)
        except (AttributeError, TypeError):
            try:
                context._resolved_domain = domain
            except Exception:  # noqa: BLE001 — context stamping is best-effort
                pass

    def _record_feedback(
        self,
        step: Any,
        context: Any,
        domain: TaskDomain,
        strategy: VerificationStrategy,
        result: VerificationResult,
        explicit_domain: Optional[TaskDomain],
    ) -> None:
        """Record a Field Guide insight when the domain was *inferred*.

        Only inferred domains are recorded — explicit tags are caller
        intent, not learning signal. Uses the existing free-form
        ``update_field_guide`` API so no schema change is required.
        """
        if explicit_domain is not None:
            return
        if self.field_guide_service is None:
            return
        workspace_id = self._workspace_id(context, step)
        if not workspace_id:
            return

        insight = (
            f"inferred domain={domain.value} → strategy={strategy.value}; "
            f"winner={'yes' if result.winner is not None else 'no'}; "
            f"fallback={result.fallback_used}; confidence={result.confidence:.2f}; "
            f"step={getattr(step, 'step_id', '?')}"
        )
        try:
            self.field_guide_service.update_field_guide(
                workspace_id, _FIELD_GUIDE_TOPIC, insight,
                agent_id="verification-orchestrator",
            )
        except Exception as exc:  # noqa: BLE001 — feedback is best-effort
            logger.debug("Field Guide feedback write failed: %s", exc)

    @staticmethod
    def _workspace_id(context: Any, step: Any) -> Optional[str]:
        for src in (context, getattr(step, "parameters", None)):
            if src is None:
                continue
            val = getattr(src, "workspace_id", None)
            if val is None and isinstance(getattr(src, "parameters", None) if src is step else src, dict):
                # context may carry workspace_id directly; step.parameters may too
                pass
            if val:
                return str(val)
            if isinstance(src, dict):
                val = src.get("workspace_id")
                if val:
                    return str(val)
        return None


__all__ = ["VerificationOrchestrator"]
