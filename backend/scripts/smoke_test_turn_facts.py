#!/usr/bin/env python3
"""
Smoke test for the Turn Fact Extraction layer — exercises the REAL code paths
against the REAL dev DB (backend/atom_dev.db) with feature flags ON.

Two phases:
  1. FAILURE MODE (no LLM provider available) — proves graceful degradation:
     extraction returns [], increments failure counter, never raises.
  2. HAPPY PATH (mocked fast-model response at the LLM I/O boundary) — proves
     the full pipeline: extract → parse → dedup → SQL persist → vector write
     (best-effort) → Tier-1 retrieval → Tier-2 recall → pre-compress queue.

Run:
    cd backend && PYTHONPATH=..:. python3 scripts/smoke_test_turn_facts.py

No cloud API keys required. The LLM boundary is the only thing mocked;
everything else (DB, LanceDB, queue, retrieval) is real.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from unittest.mock import AsyncMock, patch

# Paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Load backend/.env so DATABASE_URL + flags resolve correctly
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# Force flags ON for this smoke test regardless of .env
os.environ["TURN_FACT_EXTRACTION_ENABLED"] = "true"
os.environ["TURN_FACT_PRE_COMPRESS_ENABLED"] = "true"
os.environ["TURN_FACT_VECTOR_RECALL_ENABLED"] = "true"

from core import turn_fact_extractor as tfe_mod
from core.turn_fact_extractor import (
    TurnFactExtractor,
    get_active_facts_for_prompt,
    get_failure_counts,
    prefetch_relevant_facts,
)
from core.turn_fact_queue import get_extraction_queue
from core.database import SessionLocal
from core.models import TurnFact

WS_ID = "smoke-test-ws"
PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
INFO = "\033[36m....\033[0m"

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    mark = PASS if ok else FAIL
    print(f"{mark} {name}" + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# PHASE 1 — graceful failure (no LLM provider configured)
# ---------------------------------------------------------------------------
async def phase1_failure_mode():
    print(f"\n{INFO} PHASE 1: Graceful failure (no LLM provider)")
    # Fresh extractor; real LLM service (no provider configured → call fails)
    with patch.object(tfe_mod, "get_llm_service") as gls:
        ex = TurnFactExtractor(workspace_id=WS_ID, tenant_id="default")
        # Real-ish: the LLM call will raise because no provider is wired.
        ex.llm.generate = AsyncMock(side_effect=RuntimeError("no provider configured"))
        gls.return_value = ex.llm
    before = get_failure_counts().get("llm_error", 0)
    rows = await ex.extract_from_turn(
        user_request="setup payments",
        thought="we must use Stripe for all payments, MRR is $50K",
        maturity="INTERN",
        execution_id="smoke-exec-1",
        reasoning_step_id="smoke-step-1",
    )
    after = get_failure_counts().get("llm_error", 0)
    check("no-provider extraction returns [] (never raises)", rows == [])
    check("llm_error counter incremented", after > before, f"{before} → {after}")


# ---------------------------------------------------------------------------
# PHASE 2 — happy path (mocked fast-model response)
# ---------------------------------------------------------------------------
# Canned response mimicking what haiku/4o-mini would return for a payments turn.
_MOCK_FAST_RESPONSE = (
    'Here are the durable facts:\n'
    '[\n'
    '  {"fact": "All payments must use Stripe", "category": "hard_constraint", '
    '"domain": "finance", "confidence": 0.95},\n'
    '  {"fact": "Current MRR is $50,000", "category": "exact_value", '
    '"domain": "finance", "confidence": 0.9},\n'
    '  {"fact": "Launch is scheduled for March 14", "category": "exact_value", '
    '"domain": "operations", "confidence": 0.85},\n'
    '  {"fact": "User prefers terse bullet-point responses", "category": "implicit_pref", '
    '"domain": "general", "confidence": 0.8}\n'
    ']\n'
)

# A lexically-equivalent paraphrase (same words, different case/punctuation).
# Dedup is lexical — normalizes case/punct/whitespace — so this MUST collide
# with "All payments must use Stripe" and trigger an EWMA bump, not a new row.
# (Semantic paraphrases like "we have to use Stripe" are a DIFFERENT hash and
# stored separately — semantic dedup is Tier-2's job via embeddings.)
_MOCK_PARAPHRASE_RESPONSE = (
    '[{"fact": "ALL payments MUST use stripe.", "category": "hard_constraint", '
    '"domain": "finance", "confidence": 0.92}]'
)


async def phase2_happy_path():
    print(f"\n{INFO} PHASE 2: Happy path (mocked fast-model response)")
    with patch.object(tfe_mod, "get_llm_service"):
        ex = TurnFactExtractor(workspace_id=WS_ID, tenant_id="default")
    ex.llm.generate = AsyncMock(return_value=_MOCK_FAST_RESPONSE)

    rows = await ex.extract_from_turn(
        user_request="setup payments and launch",
        thought="we must use Stripe, MRR is $50K, launch March 14, user wants bullets",
        maturity="INTERN",
        execution_id="smoke-exec-2",
        reasoning_step_id="smoke-step-2",
        user_id="smoke-user",
        session_id="smoke-session",
    )
    check("happy-path extraction persisted 4 facts", len(rows) == 4, f"got {len(rows)}")
    cats = {r.category for r in rows}
    check("categories include hard_constraint + exact_value + implicit_pref",
          {"hard_constraint", "exact_value", "implicit_pref"}.issubset(cats),
          str(sorted(cats)))
    check("all rows have content_hash", all(r.content_hash for r in rows))
    check("all rows reference the reasoning step", all(r.reasoning_step_id == "smoke-step-2" for r in rows))
    check("all rows active", all(r.status == "active" for r in rows))

    # --- Tier-1 retrieval ---
    print(f"\n{INFO} PHASE 2b: Tier-1 retrieval (pure SQL)")
    with SessionLocal() as db:
        durable = get_active_facts_for_prompt(db, WS_ID, limit=5)
    check("Tier-1 returns the persisted facts", len(durable) >= 4, f"got {len(durable)}")
    check("Tier-1 most-recent first (ordered by created_at desc)",
          all(durable[i].created_at >= durable[i + 1].created_at for i in range(len(durable) - 1)))

    # --- Dedup: paraphrase should NOT create a 5th row ---
    print(f"\n{INFO} PHASE 2c: Dedup (paraphrased constraint)")
    ex.llm.generate = AsyncMock(return_value=_MOCK_PARAPHRASE_RESPONSE)
    # Clear anti-thrashing window (simulates TTL expiry between turns)
    ex._recent_hashes._store.clear()
    dedup_rows = await ex.extract_from_turn(
        user_request="payments",
        thought="we have to use Stripe for payments",
        maturity="INTERN",
    )
    check("paraphrase did NOT create a duplicate row", len(dedup_rows) <= 1,
          f"returned {len(dedup_rows)}")
    with SessionLocal() as db:
        stripe_rows = (
            db.query(TurnFact)
            .filter(TurnFact.workspace_id == WS_ID, TurnFact.category == "hard_constraint")
            .all()
        )
    check("exactly one active Stripe constraint", len(stripe_rows) == 1,
          f"found {len(stripe_rows)}")
    if stripe_rows:
        bumped = stripe_rows[0]
        check("EWMA confidence bumped toward 0.92", 0.9 <= bumped.confidence <= 0.95,
              f"confidence={bumped.confidence:.3f}")

    # --- Pre-compress queue ---
    print(f"\n{INFO} PHASE 2d: Pre-compress extraction queue")
    q = get_extraction_queue()
    # Realistic over-long prompt: contains fact indicators (digits, currency,
    # modal verbs) so it passes the regex pre-filter, but is long enough to
    # trigger truncation (> context_window * 3 chars).
    fact_block = (
        "We must use Stripe for all payments. MRR is $50,000. "
        "Launch is March 14. The SLA is 7 days. "
    )
    big_prompt = (fact_block * 5000) + ("x" * 20000)
    enqueued = q.enqueue(prompt=big_prompt, workspace_id=WS_ID, execution_id="smoke-precomp")
    check("queue accepted the pre-truncation prompt", enqueued is True)
    # The queue instantiates its OWN extractor via get_turn_fact_extractor(),
    # which it imported into its own namespace — so we patch it where the
    # queue module looks it up, not where it's defined.
    from core import turn_fact_queue as qmod
    with patch.object(qmod, "get_turn_fact_extractor") as glo:
        glo.return_value = ex
        ex.llm.generate = AsyncMock(return_value=_MOCK_FAST_RESPONSE)
        n = await q.drain_once()
    check("queue worker drained + extracted", n >= 1, f"extracted {n}")
    stats = q.stats()
    check("queue stats report drained >= 1", stats["drained"] >= 1, str(stats))

    # --- Tier-2 vector recall (LanceDB may not be available → graceful) ---
    print(f"\n{INFO} PHASE 2e: Tier-2 vector recall (LanceDB)")
    recalled = prefetch_relevant_facts(workspace_id=WS_ID, query="payment processor choice", limit=5)
    # If LanceDB isn't initialized in this env, this returns [] gracefully —
    # that's an acceptable pass (graceful degradation). A non-empty result is a bonus.
    check("Tier-2 recall did not raise (empty ok if LanceDB unavailable)",
          isinstance(recalled, list), f"got {len(recalled)} rows")

    # --- STUDENT maturity gate ---
    print(f"\n{INFO} PHASE 2f: Maturity gate (STUDENT read-only)")
    ex.llm.generate = AsyncMock(return_value=_MOCK_FAST_RESPONSE)
    student_rows = await ex.extract_from_turn(
        user_request="test", thought="must use Stripe", maturity="STUDENT"
    )
    check("STUDENT agent blocked from extraction", student_rows == [])
    ex.llm.generate.assert_not_called()


async def phase3_db_verification():
    print(f"\n{INFO} PHASE 3: Final DB state")
    with SessionLocal() as db:
        all_facts = (
            db.query(TurnFact)
            .filter(TurnFact.workspace_id == WS_ID)
            .order_by(TurnFact.created_at.desc())
            .all()
        )
    active = [f for f in all_facts if f.status == "active"]
    print(f"   total rows for {WS_ID}: {len(all_facts)} (active: {len(active)})")
    for f in active:
        print(f"   - [{f.category}] conf={f.confidence:.2f} src={f.extraction_source} {f.fact_text[:60]}")
    check("smoke test produced durable facts in the real DB", len(active) >= 4)


async def cleanup():
    """Remove smoke-test rows so the DB is left clean."""
    try:
        with SessionLocal() as db:
            db.query(TurnFact).filter(TurnFact.workspace_id == WS_ID).delete()
            db.commit()
        print(f"\n{INFO} Cleaned up smoke-test rows from {WS_ID}")
    except Exception as e:
        print(f"\n{INFO} cleanup skipped: {e}")


async def main():
    print("=" * 70)
    print("TURN FACT EXTRACTION — END-TO-END SMOKE TEST")
    print(f"flags: EXTRACTION={os.getenv('TURN_FACT_EXTRACTION_ENABLED')} "
          f"PRE_COMPRESS={os.getenv('TURN_FACT_PRE_COMPRESS_ENABLED')} "
          f"VECTOR_RECALL={os.getenv('TURN_FACT_VECTOR_RECALL_ENABLED')}")
    print("=" * 70)
    try:
        await phase1_failure_mode()
        await phase2_happy_path()
        await phase3_db_verification()
    finally:
        await cleanup()

    print("\n" + "=" * 70)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    for name, ok, detail in results:
        mark = PASS if ok else FAIL
        print(f"  {mark} {name}" + (f" — {detail}" if detail else ""))
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
