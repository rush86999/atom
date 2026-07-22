"""Voting verifier — symbolic majority + per-key frequency reconciliation.

This is the **default strategy** and the universal fallback. It is a
behaviour-preserving extraction of the logic that previously lived
inline in ``ConductorAgent._execute_parallel_consensus`` (lines
629-664) and ``ConductorAgent._reconcile_branch_conflicts`` (lines
714-757). Output for the ``UNKNOWN`` domain is byte-for-byte identical
to the original.

Two responsibilities:

  * :meth:`VotingVerifier.verify` — the full pipeline: majority check
    (≥ 2/3) → on full divergence, per-key frequency reconciliation →
    on empty reconciliation, fall back to the majority winner. Used by
    the orchestrator.
  * :meth:`VotingVerifier.reconcile_only` — *just* the per-key
    frequency-merge half, preserving the original
    ``_reconcile_branch_conflicts`` contract (including the
    ``_reconciled`` / ``_reconciler`` / ``_branch_count`` / ``step_id``
    metadata tags). Used by the backward-compat shim in
    ``conductor_agent.py`` so existing tests keep passing.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from core.orchestration.verification.base import (
    VerificationResult,
    VerificationStrategy,
    Verifier,
    serialise,
)

logger = logging.getLogger(__name__)

# Preserved verbatim from the original — downstream tests assert on it.
_RECONCILER_TAG = "ConductorAgent._reconcile_branch_conflicts"


class VotingVerifier(Verifier):
    """Symbolic majority vote + per-key frequency reconciliation."""

    strategy = VerificationStrategy.VOTING

    async def verify(
        self,
        candidates: List[Any],
        step: Any,
        context: Any,
    ) -> VerificationResult:
        """Run the full majority → reconcile → majority-fallback pipeline.

        Mirrors ``run_consensus_step`` (conductor_agent.py:629-664):

          * Format each candidate via :func:`serialise`; count with
            ``Counter``.
          * If a majority (≥ 2/3) exists, or only one candidate is in
            play, return the majority winner directly.
          * Otherwise attempt per-key reconciliation. If that yields a
            non-empty merged dict, return it (tagged with the
            ``_reconciled`` metadata).
          * If reconciliation is empty / fails, fall back to the
            majority winner.
        """
        step_id = getattr(step, "step_id", "?")
        domain = getattr(context, "_resolved_domain", None) or "unknown"

        if not candidates:
            return VerificationResult.empty(domain, self.strategy, reason="no candidates")

        formatted = [serialise(r) for r in candidates]
        counts = Counter(formatted)
        majority_str, majority_count = counts.most_common(1)[0]

        majority_winner = self._match_winner(candidates, formatted, majority_str)

        if majority_count >= 2 or len(candidates) == 1:
            agreement = majority_count / len(candidates) if candidates else 0.0
            return VerificationResult(
                winner=majority_winner,
                strategy=self.strategy,
                domain=domain,
                confidence=agreement,
                details={
                    "mode": "majority",
                    "majority_count": majority_count,
                    "candidate_count": len(candidates),
                    "distinct": len(counts),
                },
                reason="clear majority",
            )

        # Full divergence — try per-key reconciliation.
        logger.info(
            "Parallel branches diverged for step %s; attempting reconciliation across %d candidates",
            step_id, len(candidates),
        )
        reconciled = self.reconcile_only_sync(step_id, candidates)
        if reconciled is not None:
            logger.info("Reconciliation succeeded for step %s", step_id)
            return VerificationResult(
                winner=reconciled,
                strategy=self.strategy,
                domain=domain,
                confidence=majority_count / len(candidates),
                details={
                    "mode": "reconciled",
                    "majority_count": majority_count,
                    "candidate_count": len(candidates),
                    "distinct": len(counts),
                },
                reason="merged non-conflicting portions of diverging branches",
            )

        # Reconciliation failed — fall back to the majority winner.
        logger.warning(
            "Reconciliation failed for step %s; falling back to majority winner", step_id
        )
        return VerificationResult(
            winner=majority_winner,
            strategy=self.strategy,
            domain=domain,
            confidence=majority_count / len(candidates),
            details={
                "mode": "majority_fallback",
                "majority_count": majority_count,
                "candidate_count": len(candidates),
                "distinct": len(counts),
            },
            reason="reconciliation empty; fell back to majority winner",
        )

    async def reconcile_only(
        self,
        step_id: str,
        branch_results: List[Any],
    ) -> Optional[Dict[str, Any]]:
        """Async wrapper around :meth:`reconcile_only_sync`.

        Preserved so the ``conductor_agent`` shim can ``await`` it,
        matching the original ``async def _reconcile_branch_conflicts``
        contract.
        """
        return self.reconcile_only_sync(step_id, branch_results)

    def reconcile_only_sync(
        self,
        step_id: str,
        branch_results: List[Any],
    ) -> Optional[Dict[str, Any]]:
        """Per-key frequency reconciliation — verbatim from the original.

        Algorithm (conductor_agent.py:700-757):

          1. Collect the union of keys across all branch-result dicts.
          2. For each key, if all branches agree → include directly
             ("safe zone").
          3. If branches disagree → pick the most frequent value.
          4. Tag the merged dict with ``_reconciled=True``,
             ``_reconciler``, ``_branch_count``, ``step_id``.
          5. Return ``None`` on empty input or empty merged output so
             the caller falls back to majority vote.
        """
        if not branch_results:
            return None

        try:
            all_keys: set = set()
            for r in branch_results:
                if isinstance(r, dict):
                    all_keys.update(r.keys())

            merged: Dict[str, Any] = {}
            for key in all_keys:
                values = [r.get(key) for r in branch_results if isinstance(r, dict) and key in r]
                if not values:
                    continue

                serialised = [
                    serialise(v) if isinstance(v, (dict, list)) else v
                    for v in values
                ]
                unique = list(dict.fromkeys(serialised))  # ordered dedup

                if len(unique) == 1:
                    # All branches agree on this key — safe to merge.
                    merged[key] = values[0]
                else:
                    # Disagreement — pick the most frequent value.
                    freq = Counter(serialised)
                    winner_serialised, _ = freq.most_common(1)[0]
                    for v, s in zip(values, serialised):
                        if s == winner_serialised:
                            merged[key] = v
                            break

            if not merged:
                return None

            merged["_reconciled"] = True
            merged["_reconciler"] = _RECONCILER_TAG
            merged["_branch_count"] = len(branch_results)
            merged["step_id"] = step_id
            return merged

        except Exception as exc:  # noqa: BLE001 — never raise from the reconciler
            logger.warning("Reconciler raised an exception for step %s: %s", step_id, exc)
            return None

    @staticmethod
    def _match_winner(
        candidates: List[Any],
        formatted: List[str],
        majority_str: str,
    ) -> Any:
        """Return the first candidate whose serialised form matches the winner."""
        for r, s in zip(candidates, formatted):
            if s == majority_str:
                return r
        return candidates[0]


__all__ = ["VotingVerifier"]
