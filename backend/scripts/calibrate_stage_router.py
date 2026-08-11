#!/usr/bin/env python3
"""Per-workload calibration for the stage router (Switchyard port).

Consumes the outcome-joined ``llm_stage_router_audit`` rows (written by
``core/llm/stage_router.record_stage_outcome``) and recommends a per-workload
``confidence_threshold`` + picker before enforcement is flipped on.

Only rows with a populated outcome (``success IS NOT NULL``) are eligible.
The A/B harness (``ATOM_TRAFFIC_SPLIT`` / ``ATOM_STAGE_ROUTING_SPLIT``) is
what produces both arms of the RESCUE/LOSS comparison: for each workload we
compare what happened when the ``efficient`` arm ran vs. the ``capable`` arm.

Method (per workload, i.e. agent_id):
  - If capable's success-rate advantage over efficient is >= ``--success-gap``
    AND capable is not unreasonably more expensive (``--max-cost-ratio``),
    recommend a LOWER threshold (escalate more eagerly) / ``capable_first``.
  - Otherwise recommend ``efficient_first`` at the current threshold.

Output: a JSON config snippet per workload, ready to paste into the env
(``ATOM_STAGE_ROUTING_CONFIDENCE_THRESHOLD`` + ``ATOM_STAGE_ROUTING_PICKER``)
or a ``StageConfig`` override.

Usage:
  PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m scripts.calibrate_stage_router
  # optional: --min-rows 20 --success-gap 0.03 --max-cost-ratio 8.0
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("calibrate_stage_router")

EFFICIENT = "efficient"
CAPABLE = "capable"


def _load_rows() -> List[Dict[str, Any]]:
    from core.database import get_db_session
    from core.models import StageRouterAudit

    with get_db_session() as db:
        rows = (
            db.query(StageRouterAudit)
            .filter(StageRouterAudit.success.isnot(None))
            .all()
        )
        return [
            {
                "agent_id": r.agent_id or "unknown",
                "selected_group": r.selected_group,
                "applied_group": r.applied_group,
                "success": bool(r.success),
                "quality_satisfied": r.quality_satisfied,
                "cost": r.actual_cost,
                "latency_ms": r.actual_latency_ms,
            }
            for r in rows
        ]


def _arm_stats(rows: List[Dict[str, Any]], group: str) -> Dict[str, Any]:
    arm = [r for r in rows if r["applied_group"] == group]
    if not arm:
        return {"n": 0}
    costs = [r["cost"] for r in arm if r["cost"] is not None]
    latencies = [r["latency_ms"] for r in arm if r["latency_ms"] is not None]
    return {
        "n": len(arm),
        "success_rate": sum(r["success"] for r in arm) / len(arm),
        "quality_rate": (
            sum(1 for r in arm if r["quality_satisfied"]) / len(arm)
            if any(r["quality_satisfied"] is not None for r in arm)
            else None
        ),
        "avg_cost_usd": (sum(costs) / len(costs)) if costs else None,
        "avg_latency_ms": (sum(latencies) / len(latencies)) if latencies else None,
    }


def _recommend(
    efficient: Dict[str, Any],
    capable: Dict[str, Any],
    success_gap: float,
    max_cost_ratio: float,
) -> Dict[str, Any]:
    """RESCUE/LOSS-style recommendation for one workload."""
    if efficient["n"] == 0 or capable["n"] == 0:
        return {"verdict": "insufficient-data", "reason": "both arms need observations"}
    gain = capable["success_rate"] - efficient["success_rate"]
    eff_cost = efficient["avg_cost_usd"] or 0.0
    cap_cost = capable["avg_cost_usd"] or 0.0
    cost_ratio = (cap_cost / eff_cost) if eff_cost > 0 else None
    if gain >= success_gap and (cost_ratio is None or cost_ratio <= max_cost_ratio):
        return {
            "verdict": "escalate-more",
            "reason": (
                f"capable arm is +{gain:.1%} success at "
                f"{cost_ratio if cost_ratio is not None else 'unknown'}x cost — "
                "lower ATOM_STAGE_ROUTING_CONFIDENCE_THRESHOLD or use "
                "ATOM_STAGE_ROUTING_PICKER=capable_first"
            ),
        }
    return {
        "verdict": "efficient-first",
        "reason": (
            f"capable arm gains only {gain:.1%} success — keep "
            "efficient_first; escalate only on strong signals"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-rows", type=int, default=10, help="min outcome rows per workload to calibrate")
    parser.add_argument("--success-gap", type=float, default=0.03, help="min success-rate advantage to justify escalation")
    parser.add_argument("--max-cost-ratio", type=float, default=8.0, help="max capable/efficient cost ratio to justify escalation")
    args = parser.parse_args()

    rows = _load_rows()
    if not rows:
        logger.warning(
            "No outcome-joined stage router audit rows found. Enable "
            "ATOM_STAGE_ROUTING_ENABLED (+ ATOM_TRAFFIC_SPLIT for both arms) "
            "and let agents run for a while."
        )
        return 1

    by_workload: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_workload[row["agent_id"]].append(row)

    print(f"Calibrating {len(rows)} outcome-joined rows across {len(by_workload)} workload(s)\n")
    recommendations: Dict[str, Dict[str, Any]] = {}
    for workload, wrows in sorted(by_workload.items()):
        if len(wrows) < args.min_rows:
            print(f"[{workload}] skipped: {len(wrows)} rows < --min-rows {args.min_rows}")
            continue
        efficient = _arm_stats(wrows, EFFICIENT)
        capable = _arm_stats(wrows, CAPABLE)
        rec = _recommend(efficient, capable, args.success_gap, args.max_cost_ratio)
        recommendations[workload] = rec
        print(f"[{workload}] n={len(wrows)}")
        print(f"  efficient arm: {efficient}")
        print(f"  capable  arm: {capable}")
        print(f"  → {rec['verdict']}: {rec['reason']}\n")

    if not recommendations:
        logger.warning("Nothing calibrated — collect more outcome-joined rows first.")
        return 2

    print("=== Config snippet (paste per-workload into env / StageConfig) ===")
    print(
        json.dumps(
            {
                "recommendations": recommendations,
                "success_gap": args.success_gap,
                "max_cost_ratio": args.max_cost_ratio,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
