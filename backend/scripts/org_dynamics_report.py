#!/usr/bin/env python3
"""Org-dynamics baseline report (AGENT_ORG_POLITICS_PLAN.md Phase 0).

Reads the append-only ``agent_org_events`` table and prints three baselines:
incumbency (repeat coordinator→specialist recruit pairs), reviewer favoritism
(accept/reject rates per specialist), and radio→recruitment conflict-of-interest
pairs. Telemetry only — informs Phase 3/5 calibration; gates nothing.

Usage:
    PYTHONPATH=backend ./backend/venv/bin/python backend/scripts/org_dynamics_report.py \
        [--window-hours 720] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-hours", type=int, default=24 * 30)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    from core.database import get_db_session
    from core.org_telemetry_service import AgentOrgTelemetryService

    with get_db_session() as db:
        svc = AgentOrgTelemetryService(db)
        report = {
            "window_hours": args.window_hours,
            "incumbency": svc.compute_incumbency(window_hours=args.window_hours),
            "review_rates": svc.compute_review_rates(window_hours=args.window_hours),
            "coi_pairs": svc.compute_coi_pairs(window_hours=args.window_hours),
        }

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    inc = report["incumbency"]
    print("== Incumbency (coordinator→specialist repeat recruitment) ==")
    print(
        f"recruits={inc['total_recruits']} pairs={inc['distinct_pairs']} "
        f"repeat_pairs={inc['repeat_pairs']} "
        f"ratio={inc['repeat_pair_ratio']:.2%} distinct_targets={inc['distinct_targets']}"
    )
    for p in inc["top_pairs"][:5]:
        print(f"  {p['actor']} -> {p['target']}: {p['count']}x")

    rr = report["review_rates"]
    print("\n== Reviewer verdicts per specialist ==")
    print(f"total_reviews={rr['total_reviews']}")
    for target, s in sorted(rr["by_target"].items()):
        total = s["accepted"] + s["rejected"]
        rate = s["accepted"] / total if total else 0.0
        print(f"  {target}: {s['accepted']}/{total} accepted ({rate:.0%})")

    print("\n== Radio→recruit conflict-of-interest pairs (shadow signal) ==")
    if not report["coi_pairs"]:
        print("  none")
    for c in report["coi_pairs"]:
        print(f"  {c['actor']} recruited {c['target']} after radio contact")

    return 0


if __name__ == "__main__":
    sys.exit(main())
