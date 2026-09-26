#!/usr/bin/env python3
"""Human ground-truth spot-checks for intent routing (correctness > agreement).

Runs a curated battery (raw text known — no PHI concern) through BOTH the
incumbent classifier and the local decision model, then asks a human to grade
each pair BLIND (sides shuffled per case, revealed after grading). Labels land
in ``decision_intent_labels``; read them with
``decision_automation.label_accuracy()``.

Usage:
    TESTING=1 PYTHONPATH=backend python3 scripts/spot_check_intent.py
    TESTING=1 PYTHONPATH=backend python3 scripts/spot_check_intent.py --show-only
    TESTING=1 PYTHONPATH=backend python3 scripts/spot_check_intent.py --labeler rush

--show-only prints the comparison table without prompting or storing
(useful for eyeballing; grading is what produces data).
Exit codes: 0 = done, 1 = error, 2 = nothing gradable (all sides failed).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import random
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

BATTERY = [
    "What is the weather today?",
    "Explain photosynthesis simply",
    "Tell me a joke",
    "Summarize this thread in three bullets",
    "Execute the monthly sales report automation",
    "Run the weekly backup now",
    "Schedule a daily standup reminder",
    "Generate the Q3 expense report",
    "Research our competitors and design a market entry strategy",
    "Investigate why churn spiked and propose fixes",
    "Design a hiring plan for the support team",
    "Analyze last quarter sales and draft a strategy",
    # Short action requests (baseline extension): single actions that could
    # read as chat, workflow steps, or small tasks — the ambiguous middle.
    "Book a flight to NYC tomorrow.",
    "Cancel my last order.",
    "Remind me to call mom at 6pm.",
    "Turn off the bedroom lights.",
]


def _norm(text: str) -> str:
    return " ".join(str(text).lower().split())


def _run_llm(classifier, text: str):
    import asyncio
    try:
        result = asyncio.run(classifier.classify_intent(text))
        cat = result.category.value if hasattr(result.category, "value") else str(result.category)
        return cat, round(float(result.confidence), 2)
    except Exception as exc:
        return None, f"{type(exc).__name__}"


def _run_ollaya(text: str):
    from core import decision_service as ds
    from core.decision_questions import INTENT_ROUTING_QUESTIONS, INTENT_CHOICE_TO_CATEGORY
    ds.reset_breaker()
    try:
        out = ds.decide(text, questions=INTENT_ROUTING_QUESTIONS, timeout_s=30.0)
        ans = (out.get("answers") or {}).get("intent", {})
        choice = INTENT_CHOICE_TO_CATEGORY.get(ans.get("choice"))
        conf = ans.get("confidence")
        return choice, (round(float(conf), 2) if choice else out.get("source"))
    except Exception as exc:
        return None, f"{type(exc).__name__}"


def build_sides(llm_pick, ollaya_pick, rng):
    """Shuffle (name, pick) pairs. Pure — unit-tested."""
    sides = [("LLM", llm_pick), ("ollaya", ollaya_pick)]
    rng.shuffle(sides)
    return sides[0], sides[1]


def _blind_conf(conf) -> str:
    """Render confidence for blind display.

    Failure paths carry model-identifying strings (ollaya's source flag can
    be literally ``"ollaya"`` / ``"fallback"`` / ``"breaker"`` /
    ``"disabled"``; the LLM path surfaces exception class names), so only
    numeric values are shown — anything else renders as ``n/a``.
    """
    try:
        return f"{float(conf):.2f}"
    except (TypeError, ValueError):
        return "n/a"


def format_blind(pick_a, pick_b):
    """Grading display: NO model names (blind)."""
    return [f"  A: {pick_a[0]} ({_blind_conf(pick_a[1])})",
            f"  B: {pick_b[0]} ({_blind_conf(pick_b[1])})"]


def grade_answer(answer, lname_a, lname_b):
    """Map a grade to (llm_ok, ollaya_ok). None = skip/invalid. Pure."""
    answer = (answer or "").strip().lower()
    if answer in ("", "skip"):
        return None
    if answer == "both":
        return True, True
    if answer == "neither":
        return False, False
    if answer == "a":
        return (lname_a == "LLM"), (lname_a == "ollaya")
    if answer == "b":
        return (lname_b == "LLM"), (lname_b == "ollaya")
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show-only", action="store_true")
    ap.add_argument("--labeler", default="human")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--limit", type=int, default=0,
                    help="grade only the first N battery cases (0 = all)")
    ap.add_argument("--offset", type=int, default=0,
                    help="start grading at battery index N (for split runs)")
    ap.add_argument("--collect-only", default="",
                    help="print blind A/B table and write side mapping JSON to PATH; "
                         "no prompting, nothing stored (pair with human grading)")
    args = ap.parse_args()

    try:
        from unittest.mock import Mock
        from core.intent_classifier import IntentClassifier
        from core import decision_automation as da
        from core.database import SessionLocal
    except Exception as exc:
        print(f"ERROR: imports failed: {exc}")
        return 1

    rng = random.Random(args.seed)
    session = SessionLocal()
    graded = 0
    try:
        classifier = IntentClassifier(db=Mock(), workspace_id="spot-check")
        cases = BATTERY[args.offset:]
        if args.limit:
            cases = cases[:args.limit]
        collected = []
        for i, text in enumerate(cases, args.offset + 1):
            llm_pick = _run_llm(classifier, text)
            ollaya_pick = _run_ollaya(text)
            (lname_a, pick_a), (lname_b, pick_b) = build_sides(llm_pick, ollaya_pick, rng)
            print(f"\n[{i}/{len(BATTERY)}] {text}")
            if args.collect_only:
                collected.append({"index": i, "text": text,
                                  "a": {"model": lname_a, "pick": pick_a},
                                  "b": {"model": lname_b, "pick": pick_b}})
                for line in format_blind(pick_a, pick_b):
                    print(line)
                continue
            if args.show_only:
                for line in format_blind(pick_a, pick_b):
                    print(line)
                continue
            for line in format_blind(pick_a, pick_b):
                print(line)
            try:
                answer = input("  correct? [a/b/both/neither/skip] ")
            except (EOFError, KeyboardInterrupt):
                print("\nstopped by user")
                break
            graded_pair = grade_answer(answer, lname_a, lname_b)
            print(f"  (A was {lname_a}, B was {lname_b})")
            if graded_pair is None:
                print("  (ignored — answer a/b/both/neither/skip)")
                continue
            llm_ok, oll_ok = graded_pair
            audit_id = f"battery:{hashlib.sha256(_norm(text).encode()).hexdigest()[:12]}"
            if da.record_intent_label(session, audit_id,
                                      hashlib.sha256(_norm(text).encode()).hexdigest(),
                                      llm_ok, oll_ok, args.labeler):
                graded += 1
        if args.show_only:
            print("\n(show-only: nothing stored)")
            return 0
        if args.collect_only:
            import json as _json
            with open(args.collect_only, "w") as fh:
                _json.dump(collected, fh, indent=2)
            print(f"\n(collected {len(collected)} blind cases -> {args.collect_only}; "
                  "nothing stored)")
            return 0
        print(f"\ngraded: {graded}/{len(cases)}")
        print("accuracy:", da.label_accuracy(session))
        return 0 if graded else 2
    finally:
        try:
            session.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
