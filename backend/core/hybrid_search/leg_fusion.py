"""Multi-leg rank fusion for retrieval legs (R83 #4).

``ATOM_RETRIEVAL_FUSION`` selects the combiner for multi-leg retrieval:

- ``off`` (default) — no fusion; the caller keeps its current union order.
- ``rrf``           — Reciprocal Rank Fusion (k=60, same constant as
                      ``core.hybrid_search.documents_hybrid``).
- ``linear``        — linear-weighted fusion over per-leg normalized rank
                      scores (``ATOM_RETRIEVAL_LINEAR_WEIGHTS``, default
                      ``0.5,0.5``).

This is an A/B arm, not an assumed win. The only in-repo benchmark data on
rank fusion (Hermes' LongMemEval-S subset, ``docs/architecture/
HERMES_COMPARISON.md``) actively disfavors RRF specifically — hybrid+RRF
scored 0.61 accuracy vs 0.66 for pure vector, while the cross-encoder
rerank leg carried the +0.02 accuracy win (at a recall@5 cost: 0.75 vs
0.80). Rank fusion therefore ships OFF and may only be enabled for a
deployment after the arm clears the P2.3 memory_eval recall@k gate
(``python -m core.memory_eval``) against the baseline — the Hermes
citation is deliberately NOT evidence here.

Callers log per-query leg scores in shadow mode so the A/B is analyzable
offline (see the ``retrieval_fusion`` log line in ``graphrag_engine.
local_search``).
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Mapping, Sequence, Tuple

logger = logging.getLogger(__name__)

RRF_K = 60
MODE_OFF = "off"
MODE_RRF = "rrf"
MODE_LINEAR = "linear"
_MODES = (MODE_OFF, MODE_RRF, MODE_LINEAR)


def get_fusion_mode() -> str:
    """Current fusion mode from ``ATOM_RETRIEVAL_FUSION`` (default ``off``).

    Invalid values fail closed to ``off`` — an unrecognized combiner must
    never change live retrieval ordering.
    """
    raw = (os.getenv("ATOM_RETRIEVAL_FUSION") or MODE_OFF).strip().lower()
    return raw if raw in _MODES else MODE_OFF


def get_linear_weights() -> Tuple[float, float]:
    """Per-leg weights for the linear arm (default ``0.5,0.5``).

    Parsed from ``ATOM_RETRIEVAL_LINEAR_WEIGHTS`` as ``<leg1>,<leg2>`` in
    the caller's leg-insertion order. Invalid input falls back to equal
    weights; weights are NOT renormalized (a deliberate sum≠1 config is a
    legitimate monotonic rescale, and renormalizing would hide it).
    """
    raw = os.getenv("ATOM_RETRIEVAL_LINEAR_WEIGHTS") or "0.5,0.5"
    try:
        parts = [float(p) for p in raw.split(",")]
        if len(parts) != 2:
            raise ValueError("expected exactly two weights")
        return parts[0], parts[1]
    except (TypeError, ValueError):
        return 0.5, 0.5


def fuse_legs(
    legs: Mapping[str, Sequence[str]],
    mode: str | None = None,
) -> Tuple[List[str], Dict[str, float]]:
    """Fuse ordered id lists per leg into one ranked list.

    Args:
        legs: leg name → ids in that leg's rank order (best first).
        mode: override; defaults to ``get_fusion_mode()``.

    Returns:
        ``(ranked_ids, scores)``. ``scores`` maps id → fused score for the
        rrf/linear arms and is ``{}`` for ``off`` (no fusion, no telemetry
        noise). ``off`` returns the union of ids in first-seen order across
        legs in mapping-insertion order — byte-identical to the legacy
        vector-then-keyword union when legs are passed in that order.

    Ties (and the ``off`` union order) break by first-seen position: leg
    insertion order, then rank within the leg.
    """
    mode = mode if mode is not None else get_fusion_mode()
    names = list(legs.keys())

    if mode == MODE_OFF:
        seen: set = set()
        ranked: List[str] = []
        for name in names:
            for i in legs[name]:
                if i not in seen:
                    seen.add(i)
                    ranked.append(i)
        return ranked, {}

    if mode == MODE_RRF:
        scores: Dict[str, float] = {}
        for name in names:
            for rank, i in enumerate(legs[name], start=1):
                scores[i] = scores.get(i, 0.0) + 1.0 / (RRF_K + rank)
        return _rank_by_scores(scores, legs), scores

    if mode == MODE_LINEAR:
        weights = get_linear_weights()
        combined: Dict[str, float] = {}
        for pos, name in enumerate(names):
            w = weights[pos] if pos < len(weights) else 0.0
            ids = list(legs[name])
            n = len(ids)
            for rank, i in enumerate(ids, start=1):
                # Rank position → [0, 1]: first → 1.0, last → 0.0. A
                # single-hit leg scores 1.0 — it is that leg's best.
                norm = 1.0 if n == 1 else (n - rank) / (n - 1)
                combined[i] = combined.get(i, 0.0) + w * norm
        return _rank_by_scores(combined, legs), combined

    logger.warning("retrieval_fusion: unknown mode %r; treating as off", mode)
    return fuse_legs(legs, MODE_OFF)


def _rank_by_scores(
    scores: Mapping[str, float],
    legs: Mapping[str, Sequence[str]],
) -> List[str]:
    """Sort ids by score desc; ties break by first-seen leg order then rank."""
    first_seen: Dict[str, Tuple[int, int]] = {}
    for leg_pos, name in enumerate(legs.keys()):
        for rank, i in enumerate(legs[name], start=1):
            if i not in first_seen:
                first_seen[i] = (leg_pos, rank)
    return sorted(scores.keys(), key=lambda i: (-scores[i], first_seen[i]))
