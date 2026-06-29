"""Self-consistency voter for irreversible-action decisions.

Phase 2 hallucination mitigation, Workstream C. Implements the Wang et al.
self-consistency pattern: sample the same structured-action prompt N times
at varying temperatures, then pick the majority-vote plan. The winning
plan is returned to the caller, which executes it exactly once.

Hard invariants (enforced by test C1):

  * This module imports ONLY ``BYOKHandler`` (and stdlib / typing). It
    MUST NOT import ``UnifiedActionExecutor`` or any adapter. The voter
    never executes anything — execution is the caller's job.
  * All N samples route through the same BYOKHandler instance, so the
    provider-family invariant is structural (preserved by BYOKHandler,
    not re-implemented here).

Cascade routing composes naturally: each sample call passes
``cascade=True`` to the handler, which means schema-validation failures
inside an individual sample escalate to the same-provider flagship
transparently to the voter.

Reference: Wang et al., "Self-Consistency Improves Chain of Thought
Reasoning in Language Models" (2022). See
``docs/architecture/CONTEXT_MEMORY.md`` for how this fits with the
broader hallucination-mitigation stack.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, TypeVar

from core.hallucination_config import (
    get_self_consistency_high_threshold,
    get_self_consistency_partial_threshold,
    get_self_consistency_samples,
    get_temperature_spread,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


# Tri-state level constants — mirror core.selector_confidence_service.
# Kept at module scope so callers (audit writers, ProposalService gating)
# can compare without re-importing the dataclass.
LEVEL_HIGH = "high"
LEVEL_PARTIAL = "partial"
LEVEL_AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class VoteResult:
    """Outcome of a self-consistency vote (shadow + audit shape).

    Mirrors the ``MatchConfidence`` shape from ``selector_confidence_service``
    so downstream gating logic (ProposalService dispatch, audit writing) can
    treat the two layers symmetrically.

    Attributes:
        winner: The modal plan (Pydantic model / dict / namespace), or
            ``None`` if every sample failed.
        agreement_ratio: ``winner_count / valid_count``. ``0.0`` when no
            valid samples were drawn.
        level: Tri-state — ``high`` / ``partial`` / ``ambiguous``. Derived
            from ``agreement_ratio`` via ``_level_from_agreement()``.
        sample_count: Total samples drawn (including failures).
        valid_count: Samples that returned non-None.
        winner_count: Samples sharing the modal hash (≥1).
        distinct_hashes: Unique plan hashes among valid samples.
        temperatures: The per-sample temperature spread used.
        winner_hash: SHA-256 (truncated to 16 hex chars for log readability)
            of the modal plan, or ``None`` if no winner.
        prompt_hash: SHA-256 (16 hex chars) of the input prompt — for
            audit-row correlation across the vote + execute lifecycle.
    """

    winner: Any
    agreement_ratio: float
    level: str
    sample_count: int
    valid_count: int
    winner_count: int
    distinct_hashes: int
    temperatures: list[float] = field(default_factory=list)
    winner_hash: str | None = None
    prompt_hash: str | None = None

    @property
    def is_high(self) -> bool:
        return self.level == LEVEL_HIGH

    @property
    def requires_review(self) -> bool:
        """True when the vote should route to ProposalService.

        Only true for partial/ambiguous outcomes. ``high`` auto-executes.
        """
        return self.level in {LEVEL_PARTIAL, LEVEL_AMBIGUOUS}

    @property
    def is_no_samples(self) -> bool:
        """True when every sample failed (no valid plan returned)."""
        return self.winner is None and self.valid_count == 0


# Heuristic list of action verbs/prefixes that mark a plan as irreversible.
# A plan is irreversible if any of its action-bearing fields matches one of
# these patterns (case-insensitive). Read-only verbs (search, browse, get,
# list, query) are intentionally absent.
_IRREVERSIBLE_PATTERNS: tuple[str, ...] = (
    "send_",
    "create_",
    "update_",
    "delete_",
    "remove_",
    "bulk_",
    "transfer",
    "payment",
    "charge",
    "refund",
    "purchase",
    "deploy",
    "execute_",
    "publish",
    "submit_",
)


class SelfConsistencyVoter:
    """N-sample majority vote on a structured action plan.

    The voter never executes anything. It only invokes
    ``BYOKHandler.generate_structured_response`` N times at varying
    temperatures and returns the modal result. The caller executes the
    winning plan exactly once.

    Usage (from ``LLMService.generate_structured``):

        voter = SelfConsistencyVoter(handler=handler, db=db, tenant_id=tid)
        winning_plan = await voter.vote(
            prompt=prompt,
            response_model=ActionPlan,
            temperature=0.7,
            max_tokens=1000,
            agent_id=agent_id,
            cascade=cascade_on,
        )
        # Caller executes winning_plan exactly once.
    """

    def __init__(self, handler: Any, db: Any = None, tenant_id: str | None = None) -> None:
        self.handler = handler
        self.db = db
        self.tenant_id = tenant_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def vote(
        self,
        prompt: str,
        response_model: type[T],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        agent_id: str | None = None,
        cascade: bool = False,
        sample_count: int | None = None,
        **kwargs: Any,
    ) -> T | None:
        """Draw N samples and return the majority-vote winner.

        Args:
            prompt: The decision/action-planning prompt.
            response_model: Pydantic (or equivalent) class the handler
                resolves the response into. Same model is used for all
                N samples.
            temperature: Base temperature. The actual per-sample
                temperatures come from ``get_temperature_spread(n)``
                centered around this value (default 0.7).
            max_tokens: Per-sample token cap.
            agent_id: Optional agent context, forwarded to the handler.
            cascade: When True, each sample call passes ``cascade=True``
                to the handler so individual samples can escalate on
                schema-validation failures.
            sample_count: Override the env-driven default
                (``ATOM_SELF_CONSISTENCY_SAMPLES``). Caller does not
                normally set this; the voter resolves it from config.

        Returns:
            The modal sample, or ``None`` if every sample failed.
        """
        n = sample_count if sample_count is not None else get_self_consistency_samples()
        n = max(1, n)
        temps = self._temperatures_for(n, base=temperature)

        async def _one(temp: float) -> T | None:
            try:
                return await self.handler.generate_structured_response(
                    prompt=prompt,
                    system_instruction=kwargs.pop("system_instruction", "You are a helpful assistant."),
                    response_model=response_model,
                    temperature=temp,
                    max_tokens=max_tokens,
                    task_type=kwargs.pop("task_type", None),
                    agent_id=agent_id,
                    chain_id=kwargs.pop("chain_id", None),
                    image_payload=kwargs.pop("image_payload", None),
                    cascade=cascade,
                    **kwargs,
                )
            except Exception as exc:
                # One sample failing must not crash the whole vote. The
                # majority is decided over the survivors; if every sample
                # fails, we return None and the caller falls back to its
                # normal "no plan" path.
                logger.warning(f"Self-consistency sample failed at temp={temp}: {exc}")
                return None

        samples = await asyncio.gather(*[_one(t) for t in temps])
        valid = [s for s in samples if s is not None]
        if not valid:
            return None
        if len(valid) == 1:
            return valid[0]
        return self._majority_vote(valid)

    async def vote_with_consensus(
        self,
        prompt: str,
        response_model: type[T],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        agent_id: str | None = None,
        cascade: bool = False,
        sample_count: int | None = None,
        **kwargs: Any,
    ) -> VoteResult:
        """Draw N samples and return the modal plan + agreement metadata.

        Shadow + audit variant. Use this (instead of ``vote``) when you need
        to write a ``SelfConsistencyVote`` audit row or gate execution on
        the agreement level. The bare ``vote()`` method is preserved for
        backward compatibility with simpler callers.

        Same hard invariants as ``vote()``: never executes anything, never
        imports the executor. Caller runs the winner exactly once.

        Args: same as ``vote()``.

        Returns:
            A ``VoteResult``. ``winner`` is ``None`` if every sample failed.
        """
        n = sample_count if sample_count is not None else get_self_consistency_samples()
        n = max(1, n)
        temps = self._temperatures_for(n, base=temperature)
        prompt_hash = self._hash_prompt(prompt)

        # Extract known kwargs ONCE outside the per-sample closure so the
        # second/third samples see the same values (kwargs.pop inside the
        # loop would mutate the captured dict across iterations).
        system_instruction = kwargs.pop("system_instruction", "You are a helpful assistant.")
        task_type = kwargs.pop("task_type", None)
        chain_id = kwargs.pop("chain_id", None)
        image_payload = kwargs.pop("image_payload", None)

        async def _one(temp: float) -> T | None:
            try:
                return await self.handler.generate_structured_response(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    response_model=response_model,
                    temperature=temp,
                    max_tokens=max_tokens,
                    task_type=task_type,
                    agent_id=agent_id,
                    chain_id=chain_id,
                    image_payload=image_payload,
                    cascade=cascade,
                )
            except Exception as exc:
                logger.warning(f"Self-consistency sample failed at temp={temp}: {exc}")
                return None

        samples = await asyncio.gather(*[_one(t) for t in temps])
        valid = [s for s in samples if s is not None]

        if not valid:
            return VoteResult(
                winner=None,
                agreement_ratio=0.0,
                level=LEVEL_AMBIGUOUS,
                sample_count=n,
                valid_count=0,
                winner_count=0,
                distinct_hashes=0,
                temperatures=temps,
                winner_hash=None,
                prompt_hash=prompt_hash,
            )

        if len(valid) == 1:
            single_hash = self._hash_sample(valid[0])
            return VoteResult(
                winner=valid[0],
                agreement_ratio=1.0,
                level=self._level_from_agreement(1.0),
                sample_count=n,
                valid_count=1,
                winner_count=1,
                distinct_hashes=1,
                temperatures=temps,
                winner_hash=single_hash[:16],
                prompt_hash=prompt_hash,
            )

        # Majority vote over hash-normalized samples.
        counts: dict[str, list[int]] = {}
        for idx, s in enumerate(valid):
            h = self._hash_sample(s)
            counts.setdefault(h, []).append(idx)

        winner_hash: str | None = None
        winner_count = 0
        for h, idxs in counts.items():
            if len(idxs) > winner_count:
                winner_hash = h
                winner_count = len(idxs)

        agreement = winner_count / len(valid)
        level = self._level_from_agreement(agreement)
        winner_idx = counts[winner_hash][0] if winner_hash is not None else 0

        if winner_count == 1:
            # All samples distinct — fall back to lowest-temperature sample
            # (samples are ordered by ascending temperature via the spread).
            logger.warning(
                f"Self-consistency vote: all {len(valid)} samples distinct; "
                f"falling back to lowest-temperature sample"
            )

        logger.info(
            f"Self-consistency vote: {winner_count}/{len(valid)} samples agreed "
            f"(level={level}, agreement={agreement:.2f}, hash={(winner_hash or 'none')[:8]})"
        )

        return VoteResult(
            winner=valid[winner_idx],
            agreement_ratio=agreement,
            level=level,
            sample_count=n,
            valid_count=len(valid),
            winner_count=winner_count,
            distinct_hashes=len(counts),
            temperatures=temps,
            winner_hash=(winner_hash or "")[:16] or None,
            prompt_hash=prompt_hash,
        )

    # ------------------------------------------------------------------
    # Irreversibility heuristic — exposed for callers that want to gate
    # self-consistency behind "is this action even irreversible?"
    # ------------------------------------------------------------------

    @staticmethod
    def is_irreversible(action_plan: Any) -> bool:
        """Return True if ``action_plan`` looks irreversible.

        Heuristic: walk the plan's fields looking for action-type /
        operation fields whose value matches a known destructive verb
        prefix. Anything that doesn't match returns False (the safe
        default is *not* to spend 3× LLM calls).

        Accepts dicts, pydantic models, or SimpleNamespace-like objects.
        """
        # Normalize to a dict of stringified field values.
        if action_plan is None:
            return False
        if isinstance(action_plan, dict):
            fields = action_plan
        elif hasattr(action_plan, "model_dump"):  # pydantic v2
            fields = action_plan.model_dump()
        elif hasattr(action_plan, "dict"):  # pydantic v1
            fields = action_plan.dict()
        elif hasattr(action_plan, "__dict__"):
            fields = action_plan.__dict__
        else:
            fields = {"value": str(action_plan)}

        for key, val in fields.items():
            key_l = str(key).lower()
            val_l = str(val).lower() if val is not None else ""
            # Match either the field name or its value against patterns.
            haystacks = (key_l, val_l)
            for h in haystacks:
                for pat in _IRREVERSIBLE_PATTERNS:
                    if pat in h:
                        return True
        return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _temperatures_for(n: int, base: float = 0.7) -> list[float]:
        """Spread of N temperatures centered on ``base``.

        Uses ``hallucination_config.get_temperature_spread(n)`` which
        produces values like ``[0.6, 0.7, 0.8]`` for n=3, centered on 0.7.
        The ``base`` argument offsets the spread if the caller specified a
        non-default base temperature.
        """
        spread = get_temperature_spread(n)
        if base == 0.7:
            return spread
        # Re-center on the caller's base temperature.
        offset = base - 0.7
        return [max(0.0, min(1.5, round(t + offset, 2))) for t in spread]

    @staticmethod
    def _hash_sample(sample: Any) -> str:
        """Stable hash of a sample for majority-vote equality.

        Uses ``json.dumps(..., sort_keys=True, default=str)`` so structurally
        equivalent plans hash identically regardless of field order.
        """
        if hasattr(sample, "model_dump"):  # pydantic v2
            payload = sample.model_dump(mode="json")
        elif hasattr(sample, "dict"):  # pydantic v1
            payload = sample.dict()
        elif isinstance(sample, dict):
            payload = sample
        else:
            payload = {"value": str(sample)}
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _level_from_agreement(agreement: float) -> str:
        """Map an agreement ratio to the tri-state level.

        Mirrors ``selector_confidence_service.level_from_score``:

            agreement ≥ HIGH_THRESHOLD     → high
            PARTIAL_THRESHOLD ≤ x < HIGH   → partial
            x < PARTIAL_THRESHOLD          → ambiguous
        """
        high_t = get_self_consistency_high_threshold()
        partial_t = get_self_consistency_partial_threshold()
        if agreement >= high_t:
            return LEVEL_HIGH
        if agreement >= partial_t:
            return LEVEL_PARTIAL
        return LEVEL_AMBIGUOUS

    @staticmethod
    def _hash_prompt(prompt: str) -> str:
        """Short hash of the input prompt for audit correlation."""
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]

    def _majority_vote(self, samples: list[Any]) -> Any:
        """Pick the most common sample; ties go to the first seen.

        If all N samples are distinct (no majority), we log a warning and
        return the first sample (lowest temperature). This is the
        conservative path documented in Wang et al. — better to act on a
        coherent plan from a low-temperature sample than to silently pick
        at random.
        """
        counts: dict[str, list[int]] = {}
        for idx, s in enumerate(samples):
            h = self._hash_sample(s)
            counts.setdefault(h, []).append(idx)

        # Find the hash with the most occurrences. Ties → first-seen wins
        # because we iterate samples in temperature-ascending order.
        winner_hash: str | None = None
        winner_count = 0
        for h, idxs in counts.items():
            if len(idxs) > winner_count:
                winner_hash = h
                winner_count = len(idxs)

        if winner_hash is None:
            return samples[0]

        if winner_count == 1:
            # All samples distinct. Log and return the first (lowest temp).
            logger.warning(
                f"Self-consistency vote: all {len(samples)} samples distinct; "
                f"falling back to lowest-temperature sample"
            )
            return samples[0]

        # Return the first sample with the winning hash (preserves order).
        winner_idx = counts[winner_hash][0]
        logger.info(
            f"Self-consistency vote: {winner_count}/{len(samples)} samples agreed "
            f"(hash={winner_hash[:8]})"
        )
        return samples[winner_idx]
