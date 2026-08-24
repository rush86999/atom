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

# Hash-algorithm identifiers (R83 #8). Recorded on VoteResult + the
# SelfConsistencyVote audit row. Rows written before the JCS switch have
# NULL hash_algo and implicitly used the legacy scheme — version, don't
# migrate: hashes under different algorithms are NOT interchangeable.
HASH_ALGO_JCS = "jcs-sha256"  # RFC 8785 canonicalization + SHA-256
HASH_ALGO_LEGACY = "sha256-sortkeys"  # json.dumps(sort_keys=True) — fits String(16)


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
        hash_algo: Algorithm that produced ``winner_hash`` — ``"jcs-sha256"``
            (RFC 8785 canonicalization, current) or ``"sha256-sortkeys"``
            (legacy pre-JCS rows persist with NULL ``hash_algo`` and must be
            compared only against other legacy rows). Hashes from different
            algorithms are NOT interchangeable — compare the pair
            (hash_algo, winner_hash), never the hash alone.
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
    hash_algo: str | None = None
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

        # Extract known kwargs ONCE outside the per-sample closure so every
        # sample sees the same values (kwargs.pop inside the loop would
        # mutate the captured dict across iterations — only the first sample
        # would receive the caller's system_instruction/task_type/etc. and
        # samples 2..N would silently fall back to defaults).
        system_instruction = kwargs.pop("system_instruction", "You are a helpful assistant.")
        task_type = kwargs.pop("task_type", None)
        chain_id = kwargs.pop("chain_id", None)
        image_payload = kwargs.pop("image_payload", None)

        # P4a (W3): diversity-aware init — rotate a perspective overlay per
        # sample so each sample approaches the problem differently
        # (arXiv 2601.19921). Disabled by default (kill-switch parity).
        from core.hallucination_config import is_moa_diversity_enabled
        overlays = self.diversity_overlays(n, enabled=is_moa_diversity_enabled())

        async def _one(temp: float, idx: int) -> T | None:
            overlay = overlays[idx] if idx < len(overlays) else ""
            sample_sys = f"{system_instruction}\n\n{overlay}" if overlay else system_instruction
            try:
                return await self.handler.generate_structured_response(
                    prompt=prompt,
                    system_instruction=sample_sys,
                    response_model=response_model,
                    temperature=temp,
                    max_tokens=max_tokens,
                    task_type=task_type,
                    agent_id=agent_id,
                    chain_id=chain_id,
                    image_payload=image_payload,
                    cascade=cascade,
                    # R72 F: voter samples must never re-trigger MoA.
                    allow_moa=False,
                    **kwargs,
                )
            except Exception as exc:
                # One sample failing must not crash the whole vote. The
                # majority is decided over the survivors; if every sample
                # fails, we return None and the caller falls back to its
                # normal "no plan" path.
                logger.warning(f"Self-consistency sample failed at temp={temp}: {exc}")
                return None

        samples = await asyncio.gather(*[_one(t, i) for i, t in enumerate(temps)])
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

        # P4a (W3): diversity-aware init — same per-sample overlay mechanism
        # as ``vote()`` (arXiv 2601.19921). Disabled by default.
        from core.hallucination_config import is_moa_diversity_enabled
        overlays = self.diversity_overlays(n, enabled=is_moa_diversity_enabled())

        async def _one(temp: float, idx: int) -> T | None:
            overlay = overlays[idx] if idx < len(overlays) else ""
            sample_sys = f"{system_instruction}\n\n{overlay}" if overlay else system_instruction
            try:
                return await self.handler.generate_structured_response(
                    prompt=prompt,
                    system_instruction=sample_sys,
                    response_model=response_model,
                    temperature=temp,
                    max_tokens=max_tokens,
                    task_type=task_type,
                    agent_id=agent_id,
                    chain_id=chain_id,
                    image_payload=image_payload,
                    cascade=cascade,
                    # R72 F: voter samples must never re-trigger MoA.
                    allow_moa=False,
                )
            except Exception as exc:
                logger.warning(f"Self-consistency sample failed at temp={temp}: {exc}")
                return None

        samples = await asyncio.gather(*[_one(t, i) for i, t in enumerate(temps)])
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
                hash_algo=None,
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
                hash_algo=self._effective_hash_algo(),
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
            hash_algo=self._effective_hash_algo() if winner_hash else None,
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

        # Bug #13: don't match substring-wise — "create_" inside
        # created_at/updated_at fields triggered 3× LLM cost on read-only
        # plans that merely carry timestamps. Match by PREFIX only, and skip
        # benign metadata fields (_at/_by/_time/_date/_count/_id...) entirely.
        # The module contract (docstring + original C5 spec) matches the
        # destructive verb in the VALUE as well as the field NAME — e.g.
        # {"action": "send_email"} — so both haystacks are checked with
        # startswith (never `in`, so mid-string occurrences stay inert).
        _BENIGN_FIELD_SUFFIXES = ("_at", "_by", "_time", "_date", "_timestamp", "_count", "_id")
        for key, val in fields.items():
            key_l = str(key).lower()
            # Skip fields that are clearly metadata (timestamps, counters, ids).
            if any(key_l.endswith(suffix) for suffix in _BENIGN_FIELD_SUFFIXES):
                continue
            val_l = str(val).lower() if isinstance(val, str) else ""
            for pat in _IRREVERSIBLE_PATTERNS:
                if key_l.startswith(pat) or val_l.startswith(pat):
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

    # ------------------------------------------------------------------
    # P4a (W3): diversity-aware initialization.
    # arXiv 2601.19921 ("Demystifying MAD"): diversity-aware init improves the
    # prior probability of MAD success WITHOUT changing update dynamics. The
    # win comes from starting samples with varied perspectives, not from more
    # rounds. This rotates a per-sample system_instruction overlay so each
    # sample approaches the problem from a different angle.
    # ------------------------------------------------------------------
    _DIVERSITY_PERSPECTIVES: list[str] = [
        "Approach this methodically, step by step.",
        "Consider edge cases and what could go wrong first.",
        "Be concise and direct; favor the simplest correct answer.",
        "Reason from first principles before committing to an approach.",
    ]

    @classmethod
    def diversity_overlays(cls, n: int, enabled: bool = False) -> list[str]:
        """Return N system_instruction overlays (diversity-aware init).

        When ``enabled`` is False (the default / current behavior), returns a
        list of empty strings so callers see no overlay (kill-switch parity).
        When True, cycles through perspective prompts so samples diverge.
        """
        if not enabled or n <= 0:
            return ["" for _ in range(max(1, n))]
        return [cls._DIVERSITY_PERSPECTIVES[i % len(cls._DIVERSITY_PERSPECTIVES)] for i in range(n)]

    @staticmethod
    def _sample_payload(sample: Any) -> Any:
        """Normalize a sample to a JSON-compatible payload for hashing."""
        if hasattr(sample, "model_dump"):  # pydantic v2
            return sample.model_dump(mode="json")
        if hasattr(sample, "dict"):  # pydantic v1
            return sample.dict()
        if isinstance(sample, dict):
            return sample
        return {"value": str(sample)}

    @staticmethod
    def _hash_sample_legacy(sample: Any) -> str:
        """Legacy hash: ``json.dumps(..., sort_keys=True)`` + SHA-256.

        Kept ONLY for comparing against historical audit rows (their
        ``winner_hash`` values were produced this way). Do not use for new
        votes — see ``_hash_sample``.
        """
        payload = SelfConsistencyVoter._sample_payload(sample)
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _hash_sample(sample: Any) -> str:
        """Stable hash of a sample for majority-vote equality.

        Default (``ATOM_SC_HASH_ALGO`` unset / ``jcs-sha256``): RFC 8785
        canonicalization via the vendored ``core.llm.jcs`` — structurally
        equivalent plans hash identically regardless of field order AND
        numeric literal form (1 ≡ 1.0 ≡ 1.00).

        Kill switch ``ATOM_SC_HASH_ALGO=sha256-sortkeys`` restores the exact
        pre-R83 hashes. Any canonicalization failure (NaN/Inf, exotic
        payloads) falls back to the legacy serialization — hashing must
        never raise inside a vote.
        """
        from core.hallucination_config import get_sc_hash_algo

        payload = SelfConsistencyVoter._sample_payload(sample)
        if get_sc_hash_algo() == HASH_ALGO_JCS:
            try:
                from core.llm.jcs import jcs_sha256_hex

                return jcs_sha256_hex(payload)
            except Exception as exc:  # NaN/Inf, exotic scalars → degrade
                logger.debug(f"JCS canonicalization failed ({exc}); using legacy hash")
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _effective_hash_algo() -> str:
        """The algorithm ``_hash_sample`` will use right now (for tagging)."""
        from core.hallucination_config import get_sc_hash_algo

        return get_sc_hash_algo()

    @staticmethod
    def hashes_match(
        row_algo: str | None,
        row_hash: str | None,
        vote_algo: str | None,
        vote_hash: str | None,
    ) -> bool:
        """Compare a stored (algo, hash) pair against a vote's pair.

        NULL ``row_algo`` means a legacy row (``sha256-sortkeys``). Hashes
        computed under different algorithms never match — legacy rows can
        only dedup against legacy hashes, never against new JCS hashes.
        """
        if not row_hash or not vote_hash:
            return False
        resolved_row_algo = row_algo or HASH_ALGO_LEGACY
        return resolved_row_algo == vote_algo and row_hash == vote_hash

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
