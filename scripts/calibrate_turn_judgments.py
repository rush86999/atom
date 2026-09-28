#!/usr/bin/env python3
"""Summarize turn-judgment shadow telemetry (OLLAYA_DECISION_PLAN Phase 3d).

Read-only: aggregates ``decision_turn_audit`` rows — per-judgment coverage
and distribution, ollaya latency. There is no outcome join yet (facts
actually extracted / DoD reached land in Phase 4), so the verdict is always
HOLD until then; this script establishes the baseline distributions the
future gate will certify against.

Usage:
    TESTING=1 PYTHONPATH=backend python3 scripts/calibrate_turn_judgments.py

Exit codes: 2 = HOLD, 1 = error. (0/READY is reserved for the post-join gate.)

The --join-facts flag joins TurnFact rows per execution_id: this is the
certification data for a future extraction pre-filter (skip the LLM call
when has_durable_fact is low). It reports what a would-skip rule
(prob <= 0.2) would have saved vs the facts it would have missed.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

JUDGMENTS = ("has_durable_fact", "on_task", "task_done", "pending_question", "stuck")


def _pct(vals, p: float) -> float:
    if not vals:
        return float("nan")
    s = sorted(vals)
    return s[min(len(s) - 1, int(len(s) * p))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--join-facts", action="store_true",
                    help="join TurnFact counts per execution_id (pre-filter certification data)")
    args = ap.parse_args()

    try:
        from core.database import SessionLocal
        from core.models import DecisionTurnAudit
    except Exception as exc:
        print(f"ERROR: imports failed: {exc}")
        return 1

    session = SessionLocal()
    try:
        rows = (session.query(DecisionTurnAudit)
                .filter(DecisionTurnAudit.surface == "turn")
                .order_by(DecisionTurnAudit.created_at).all())
        fact_counts: dict[str, int] = {}
        if args.join_facts:
            try:
                from core.models import TurnFact
                from sqlalchemy import func as _func
                exec_ids = sorted({r.execution_id for r in rows if r.execution_id})
                if exec_ids:
                    for eid, cnt in (session.query(TurnFact.execution_id,
                                                   _func.count(TurnFact.id))
                                     .filter(TurnFact.execution_id.in_(exec_ids))
                                     .group_by(TurnFact.execution_id).all()):
                        fact_counts[eid] = cnt
            except Exception as exc:
                print(f"WARNING: fact join failed ({exc}) — continuing without it")
    except Exception as exc:
        print(f"ERROR: query failed (no shadow traffic recorded yet): {exc}")
        return 1
    finally:
        try:
            session.close()
        except Exception:
            pass

    print(f"rows: {len(rows)}")
    if not rows:
        print("verdict: HOLD (no turn rows — enable ATOM_OLLAYA_SHADOW_TURN + drive traffic)")
        return 2

    for name in JUDGMENTS:
        vals = [r.judgments.get(name) for r in rows
                if r.judgments and isinstance(r.judgments.get(name), (int, float))]
        cov = len(vals) / len(rows)
        if vals:
            print(f"  {name}: coverage={cov:.2f} mean={statistics.mean(vals):.3f} "
                  f"p50={statistics.median(vals):.3f} p90={_pct(vals, 0.90):.3f} n={len(vals)}")
        else:
            print(f"  {name}: coverage={cov:.2f} (no decided values)")

    lat = sorted(r.ollaya_latency_ms for r in rows if r.ollaya_latency_ms)
    if lat:
        print(f"ollaya latency ms: p50={statistics.median(lat):.0f} "
              f"p95={_pct(lat, 0.95):.0f} n={len(lat)}")

    if args.join_facts:
        _report_fact_join(rows, fact_counts)

    print("verdict: HOLD (record-only phase — outcome join for facts/DoD lands in Phase 4)")
    return 2


def _report_fact_join(rows, fact_counts: dict) -> None:
    """Would-skip certification data: has_durable_fact vs facts actually extracted."""
    scored = [(r, (r.judgments or {}).get("has_durable_fact"))
              for r in rows if r.execution_id]
    scored = [(r, p) for r, p in scored if isinstance(p, (int, float))]
    if not scored:
        print("fact join: no scored rows with execution_id — record more shadow traffic")
        return
    with_facts = [p for r, p in scored if fact_counts.get(r.execution_id, 0) > 0]
    without = [p for r, p in scored if fact_counts.get(r.execution_id, 0) == 0]
    print(f"fact join: {len(scored)} scored turns, "
          f"{len(with_facts)} produced facts, {len(without)} produced none")
    if with_facts:
        print(f"  has_durable_fact | facts>0: mean={statistics.mean(with_facts):.3f} n={len(with_facts)}")
    if without:
        print(f"  has_durable_fact | facts=0: mean={statistics.mean(without):.3f} n={len(without)}")
    skipped = [(r, p) for r, p in scored if p <= 0.2]
    if skipped:
        missed = sum(1 for r, _ in skipped if fact_counts.get(r.execution_id, 0) > 0)
        print(f"  would-skip (prob<=0.2): n={len(skipped)} "
              f"missed-facts={missed} precision={1 - missed / len(skipped):.3f} "
              f"coverage={len(skipped) / len(scored):.2f}")
    else:
        print("  would-skip (prob<=0.2): n=0 (no turns under threshold)")


if __name__ == "__main__":
    sys.exit(main())
