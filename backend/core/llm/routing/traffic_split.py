"""Weighted-random traffic split — the stage router's calibration harness.

Fixed-ratio A/B splits between candidate arms. This is the measurement tool
that answers "did the stage router actually save cost without losing quality
on *this* workload?" before enforcement is ever flipped on: forcing a known
traffic mix while the stage router shadows its would-have picks produces the
RESCUE/LOSS quadrant data the calibration script consumes
(``scripts/calibrate_stage_router.py``).

Mirrors Switchyard's ``random`` route type ("fixed traffic split for A/B
tests, baselines, or cost experiments") and the repo's ``offline_tuner.py``
style: pure functions + a summary-dict contract.

Two levels are supported:

1. **Group-level split** (v1, wired): ``get_traffic_split()`` returns the
   ``WeightedRandomSplit`` between the ``capable``/``efficient`` tier groups
   that ``core/llm/stage_router.py`` applies per turn
   (``ATOM_STAGE_ROUTING_SPLIT`` JSON weights).
2. **Option-level split** (harness API): ``pick_arm``/``assign_arm`` split
   across an arbitrary ranked option list (e.g. top-K BPC candidates) for
   future model-level calibration experiments.

Flags (all default off — the harness never runs without explicit opt-in):
- ``ATOM_TRAFFIC_SPLIT`` — master switch for the harness.
- ``ATOM_STAGE_ROUTING_SPLIT`` — JSON weights, e.g.
  ``'{"efficient": 0.7, "capable": 0.3}'``; presence also enables the harness.
- ``ATOM_STAGE_ROUTING_SPLIT_SEED`` — optional int for reproducible runs.
"""

from __future__ import annotations

import logging
import os
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.llm.stage_router import WeightedRandomSplit

logger = logging.getLogger(__name__)


def traffic_split_enabled() -> bool:
    """True when the A/B harness is opted in via either flag."""
    return (
        os.getenv("ATOM_TRAFFIC_SPLIT", "false").lower() == "true"
        or bool(os.getenv("ATOM_STAGE_ROUTING_SPLIT", ""))
    )


def get_traffic_split() -> Optional[WeightedRandomSplit]:
    """The group-level split (capable/efficient) configured for the harness."""
    if not traffic_split_enabled():
        return None
    return WeightedRandomSplit.from_env()


def pick_arm(
    options: Sequence[Tuple[str, str]],
    weights: Optional[Sequence[float]] = None,
    rng: Optional[random.Random] = None,
) -> Tuple[str, str]:
    """Pick one ``(arm_id, arm_label)`` from ``options`` by ``weights``.

    ``weights`` are normalized; when omitted the split is uniform. Invalid
    inputs fall back to the first option (never raises — the harness must
    never break the routing path).
    """
    if not options:
        raise ValueError("pick_arm requires at least one option")
    ids = [o[0] for o in options]
    if weights is None:
        weights = [1.0] * len(options)
    if len(weights) != len(options):
        logger.warning("pick_arm: weights length mismatch, falling back to uniform")
        weights = [1.0] * len(options)
    total = sum(max(w, 0.0) for w in weights)
    if total <= 0:
        logger.warning("pick_arm: non-positive weights, falling back to uniform")
        weights = [1.0] * len(options)
        total = float(len(options))
    normalized = [max(w, 0.0) / total for w in weights]
    rng = rng or random.Random()
    idx = rng.choices(range(len(options)), normalized, k=1)[0]
    return options[idx]


def assign_arm(
    decision_id: str,
    options: Sequence[Tuple[str, str]],
    *,
    top_k: int = 2,
    weights: Optional[Sequence[float]] = None,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    """Assign an A/B arm to a decision; returns the offline_tuner-style summary.

    ``options`` are ``(arm_id, arm_label)`` pairs, usually the top-K ranked
    candidates from BPC/learning-router scoring. The summary is the
    calibration record contract: it can be logged verbatim and correlated
    with the outcome downstream.
    """
    eligible = list(options[:top_k])
    arm_id, arm_label = pick_arm(eligible, weights, rng=rng)
    return {
        "decision_id": decision_id,
        "arm": arm_id,
        "arm_label": arm_label,
        "top_k": len(eligible),
        "weights": list(weights) if weights is not None else None,
        "deterministic": rng is not None,
    }
