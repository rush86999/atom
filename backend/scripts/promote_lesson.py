#!/usr/bin/env python
"""Controlled lesson promotion through the EXISTING ledger (2026-09-24).

The ONE manual promotion path: attaches evaluation results, checks the
pre-registered gate, appends an ACCEPTED ledger row with runtime
overrides (consumed via core.lesson_runtime), or refuses. Rollback
(demote) appends a rolled_back row — the override disappears
immediately. Nothing here is autonomous; a human runs it.

Usage:
  python scripts/promote_lesson.py promote <candidate_id> --eval-file results.json
  python scripts/promote_lesson.py demote  <candidate_id>
"""
import argparse
import asyncio
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from core.database import get_db_session  # noqa: E402
from core.lesson_candidates import (  # noqa: E402
    all_candidates,
    evaluate_promotion_gate,
)


def _record(db, *, target, status, stage, reason, payload):
    from core.auto_dev.skill_impact_ledger import record_outcome

    return record_outcome(
        db,
        tenant_id="default",
        target=target,
        source="lesson_promotion",
        status=status,
        stage=stage,
        reason=reason,
        proposal_summary=payload.get("title", ""),
        payload=payload,
    )


def promote(candidate_id: str, eval_file: str) -> int:
    candidate = next(
        (c for c in all_candidates()
         if c.get("candidate_id") == candidate_id), None)
    if candidate is None:
        print(f"UNKNOWN candidate {candidate_id}")
        return 2
    try:
        with open(eval_file) as fh:
            results = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        print(f"eval file unreadable: {exc}")
        return 2
    gate = evaluate_promotion_gate(
        results.get("baseline") or {}, results.get("candidate") or {})
    overrides = candidate.get("runtime_overrides") or {}
    payload = {
        "title": candidate.get("title"),
        "candidate_id": candidate_id,
        "gate": gate,
        "overrides": overrides,
    }
    with get_db_session() as db:
        if gate.get("promote") is True:
            _record(
                db, target=f"lesson:{candidate_id}", status="accepted",
                stage="limited",
                reason=(
                    f"gate passed: gain={gate.get('goal_completion_gain')} "
                    f"threshold_hash={gate.get('threshold_hash')}"),
                payload=payload)
            print(f"PROMOTED (limited): {candidate_id} overrides={overrides}")
            return 0
        _record(
            db, target=f"lesson:{candidate_id}", status="rejected",
            stage="eval",
            reason=f"gate refused: {gate}",
            payload=payload)
        print(f"REFUSED (shadow retained): {gate}")
        return 1


def demote(candidate_id: str) -> int:
    from core.lesson_runtime import clear_cache

    with get_db_session() as db:
        row = _record(
            db, target=f"lesson:{candidate_id}", status="rolled_back",
            stage="runtime",
            reason="manual rollback — override removed from runtime",
            payload={"candidate_id": candidate_id, "overrides": {}})
    clear_cache()
    print(f"ROLLED BACK: {candidate_id} (ledger row {row})")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("promote")
    pr.add_argument("candidate_id")
    pr.add_argument("--eval-file", required=True)
    dm = sub.add_parser("demote")
    dm.add_argument("candidate_id")
    args = p.parse_args(argv)
    if args.cmd == "promote":
        return promote(args.candidate_id, args.eval_file)
    return demote(args.candidate_id)


if __name__ == "__main__":
    raise SystemExit(main())
