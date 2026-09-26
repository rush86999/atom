#!/usr/bin/env python3
"""Certify the intent-routing shadow (OLLAYA_DECISION_PLAN Phase 2d).

Read-only: aggregates ``decision_router_audit`` rows (incumbent pick vs the
local decision model's would-have pick) and reports agreement, Brier score,
ECE, a confidence-threshold sweep, and a READY/HOLD verdict.

Usage:
    TESTING=1 PYTHONPATH=backend python3 scripts/calibrate_decision_router.py
    TESTING=1 PYTHONPATH=backend python3 scripts/calibrate_decision_router.py --min-rows 30

Exit codes: 0 = READY (certify), 2 = HOLD (need more shadow traffic), 1 = error.
Gates mirror the trust-calibration certify convention (Brier <= 0.25, n >= 30).
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))


def _brier(rows) -> float | None:
    decided = [r for r in rows if r.ollaya_choice is not None and r.ollaya_confidence is not None]
    if not decided:
        return None
    return sum(((r.ollaya_confidence or 0.0) - (1.0 if r.agreement else 0.0)) ** 2
               for r in decided) / len(decided)


def _ece(rows, bins: int = 5) -> float | None:
    decided = [r for r in rows if r.ollaya_choice is not None and r.ollaya_confidence is not None]
    if not decided:
        return None
    ece, total = 0.0, len(decided)
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        bucket = [r for r in decided if (r.ollaya_confidence or 0.0) >= lo
                  and ((r.ollaya_confidence or 0.0) < hi or (b == bins - 1))]
        if not bucket:
            continue
        acc = sum(1.0 if r.agreement else 0.0 for r in bucket) / len(bucket)
        conf = sum(r.ollaya_confidence or 0.0 for r in bucket) / len(bucket)
        ece += (len(bucket) / total) * abs(acc - conf)
    return ece


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-rows", type=int, default=30)
    ap.add_argument("--min-agreement", type=float, default=0.8)
    ap.add_argument("--max-brier", type=float, default=0.25)
    args = ap.parse_args()

    try:
        from core.database import SessionLocal
        from core.models import DecisionRouterAudit
    except Exception as exc:
        print(f"ERROR: imports failed: {exc}")
        return 1

    session = SessionLocal()
    try:
        rows = (session.query(DecisionRouterAudit)
                .filter(DecisionRouterAudit.surface == "intent")
                .order_by(DecisionRouterAudit.created_at).all())
    except Exception as exc:
        print(f"ERROR: query failed (table may not exist yet — no shadow traffic recorded): {exc}")
        return 1
    finally:
        try:
            session.close()
        except Exception:
            pass

    n = len(rows)
    decided = [r for r in rows if r.ollaya_choice is not None]
    nd = len(decided)
    print(f"rows: {n} total, {nd} with ollaya choice")
    if nd == 0:
        print("verdict: HOLD (no decided rows — enable ATOM_OLLAYA_SHADOW_INTENT + drive traffic)")
        return 2

    agree = sum(1 for r in decided if r.agreement) / nd
    print(f"agreement (ollaya vs incumbent): {agree:.3f}")
    brier = _brier(rows)
    ece = _ece(rows)
    print(f"brier: {brier:.3f}  ece(5-bin): {ece:.3f}")

    lat = sorted(r.ollaya_latency_ms for r in decided if r.ollaya_latency_ms)
    if lat:
        print(f"ollaya latency ms: p50={statistics.median(lat):.0f} "
              f"p95={lat[min(len(lat) - 1, int(len(lat) * 0.95))]:.0f} n={len(lat)}")

    print("threshold sweep (act iff ollaya_confidence >= t):")
    for t in (0.5, 0.6, 0.7, 0.8, 0.9):
        acted = [r for r in decided if (r.ollaya_confidence or 0.0) >= t]
        if not acted:
            print(f"  t={t:.1f}: n=0")
            continue
        a = sum(1 for r in acted if r.agreement) / len(acted)
        print(f"  t={t:.1f}: n={len(acted)} agreement={a:.3f} coverage={len(acted) / nd:.2f}")

    by_cat: dict[str, list] = {}
    for r in decided:
        by_cat.setdefault(r.llm_category or "?", []).append(r)
    print("per-category agreement:")
    for cat in sorted(by_cat):
        rs = by_cat[cat]
        print(f"  {cat}: n={len(rs)} agreement={sum(1 for r in rs if r.agreement) / len(rs):.3f}")

    reasons = []
    if nd < args.min_rows:
        reasons.append(f"n={nd} < {args.min_rows}")
    if agree < args.min_agreement:
        reasons.append(f"agreement={agree:.3f} < {args.min_agreement}")
    if brier is not None and brier > args.max_brier:
        reasons.append(f"brier={brier:.3f} > {args.max_brier}")
    if reasons:
        print(f"verdict: HOLD ({'; '.join(reasons)})")
        return 2
    print("verdict: READY (certify per-workload thresholds, then pilot enforce)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
