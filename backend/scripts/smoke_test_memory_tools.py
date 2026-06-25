#!/usr/bin/env python3
"""
Smoke test for the agent-callable memory tools — exercises memory_remember
and memory_forget end-to-end against the REAL dev DB (backend/atom_dev.db).

Validates the full tool surface that an agent would hit via MCP:
  - memory_remember: happy path, invalid category, dedup reuse, default workspace
  - memory_forget: by fact_id, by substring, deletion-safety refusal, no-match
  - registry: both tools discoverable with correct metadata + maturity gating
  - SQL + audit: invalidated rows are soft-deleted (status, superseded_at)

No LLM keys required — the tools bypass extraction (agent-initiated writes).
Run:
    cd backend && PYTHONPATH=..:. python3 scripts/smoke_test_memory_tools.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from core.database import SessionLocal
from core.models import TurnFact
from tools.memory_tool import memory_forget, memory_remember, register_memory_tool
from tools.registry import ToolRegistry

WS = "smoke-mem-tools"
PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
INFO = "\033[36m....\033[0m"
_results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    _results.append((name, ok, detail))
    mark = PASS if ok else FAIL
    print(f"{mark} {name}" + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# PHASE 1 — Registry discovery + metadata
# ---------------------------------------------------------------------------
def phase1_registry():
    print(f"\n{INFO} PHASE 1: Registry discovery + governance metadata")
    reg = ToolRegistry()
    register_memory_tool(reg)

    remember = reg.get("memory_remember")
    forget = reg.get("memory_forget")
    check("memory_remember registered", remember is not None)
    check("memory_forget registered", forget is not None)
    if remember:
        check("remember category=memory", remember.category == "memory", remember.category)
        check("remember complexity=2 (MODERATE)", remember.complexity == 2, str(remember.complexity))
        check("remember maturity=INTERN", remember.maturity_required == "INTERN", remember.maturity_required)
        check("remember has tool function", callable(remember.function))
    if forget:
        check("forget complexity=3 (HIGH)", forget.complexity == 3, str(forget.complexity))
        check("forget maturity=SUPERVISED", forget.maturity_required == "SUPERVISED", forget.maturity_required)
        check("forget tags include 'delete'", "delete" in (forget.tags or []), str(forget.tags))


# ---------------------------------------------------------------------------
# PHASE 2 — memory_remember (the agent explicitly stores facts)
# ---------------------------------------------------------------------------
async def phase2_remember():
    print(f"\n{INFO} PHASE 2: memory_remember (agent-initiated persist)")
    # Happy path — a hard constraint
    r1 = await memory_remember(
        fact_text="All production deploys require VP approval",
        category="hard_constraint",
        domain="operations",
        workspace_id=WS,
        user_id="smoke-user",
        session_id="smoke-session",
    )
    check("remember hard_constraint succeeds", r1["success"] is True, r1.get("message", ""))
    check("returns a fact_id", bool(r1.get("fact_id")), r1.get("fact_id", "")[:8])
    fact_id_1 = r1.get("fact_id")

    # Exact value
    r2 = await memory_remember(
        fact_text="AWS monthly spend is $42,000",
        category="exact_value",
        domain="finance",
        workspace_id=WS,
    )
    check("remember exact_value succeeds", r2["success"] is True)

    # Implicit preference
    r3 = await memory_remember(
        fact_text="Prefers communication via Slack not email",
        category="implicit_pref",
        workspace_id=WS,
    )
    check("remember implicit_pref succeeds", r3["success"] is True)

    # Decision reasoning
    r4 = await memory_remember(
        fact_text="Chose Postgres over MySQL for JSONB + CTE support",
        category="decision_reason",
        workspace_id=WS,
    )
    check("remember decision_reason succeeds", r4["success"] is True)

    # Cross-task dependency
    r5 = await memory_remember(
        fact_text="Onboarding v2 blocks on the auth refactor",
        category="cross_task_dep",
        workspace_id=WS,
    )
    check("remember cross_task_dep succeeds", r5["success"] is True)

    # Invalid category — must be rejected with a helpful message
    r_bad = await memory_remember(
        fact_text="something",
        category="bogus",
        workspace_id=WS,
    )
    check("invalid category rejected", r_bad["success"] is False)
    check("error lists valid categories", "exact_value" in r_bad.get("message", ""))

    # Empty fact — rejected
    r_empty = await memory_remember(fact_text="   ", category="exact_value", workspace_id=WS)
    check("empty fact rejected", r_empty["success"] is False)

    # Dedup: exact duplicate returns the SAME fact_id (EWMA bump, no new row)
    r_dup = await memory_remember(
        fact_text="All production deploys require VP approval",
        category="hard_constraint",
        workspace_id=WS,
    )
    check("duplicate returns same fact_id (dedup)", r_dup["fact_id"] == fact_id_1,
          f"{fact_id_1[:8]} vs {r_dup.get('fact_id','')[:8]}")

    return fact_id_1


# ---------------------------------------------------------------------------
# PHASE 3 — SQL verification (the rows actually landed)
# ---------------------------------------------------------------------------
def phase3_sql_verify():
    print(f"\n{INFO} PHASE 3: SQL verification (rows in real DB)")
    with SessionLocal() as db:
        rows = (
            db.query(TurnFact)
            .filter(TurnFact.workspace_id == WS, TurnFact.status == "active")
            .order_by(TurnFact.created_at.desc())
            .all()
        )
    check("5 active facts persisted (not 6 — dedup)", len(rows) == 5, f"found {len(rows)}")
    cats = {r.category for r in rows}
    check("all 5 categories present",
          cats == {"hard_constraint", "exact_value", "implicit_pref", "decision_reason", "cross_task_dep"},
          str(sorted(cats)))
    check("all sourced as agent_explicit",
          all(r.extraction_source == "agent_explicit" for r in rows))
    check("confidence is high (explicit default 0.95)",
          all(r.confidence >= 0.9 for r in rows))
    for r in rows:
        print(f"   - [{r.category}] conf={r.confidence:.2f} {r.fact_text[:55]}")


# ---------------------------------------------------------------------------
# PHASE 4 — memory_forget (agent-initiated deletion)
# ---------------------------------------------------------------------------
async def phase4_forget(fact_id_1: str):
    print(f"\n{INFO} PHASE 4: memory_forget (deletion + safety)")
    # By exact fact_id (preferred path)
    r_by_id = await memory_forget(fact_id=fact_id_1, workspace_id=WS)
    check("forget by fact_id succeeds", r_by_id["success"] is True, r_by_id.get("message", ""))
    check("invalidated exactly 1", r_by_id["invalidated_count"] == 1)

    # Verify soft-delete in DB (audit preserved)
    with SessionLocal() as db:
        row = db.get(TurnFact, fact_id_1)
    check("forgotten fact is soft-deleted (status=invalidated)", row.status == "invalidated")
    check("superseded_at timestamp set", row.superseded_at is not None)
    check("fact_text still present (audit history)", bool(row.fact_text))

    # By substring — invalidates all matches in the workspace
    r_by_substr = await memory_forget(fact_text_contains="Postgres", workspace_id=WS)
    check("forget by substring succeeds", r_by_substr["success"] is True)
    check("invalidated the Postgres decision_reason", r_by_substr["invalidated_count"] == 1)

    # Deletion safety: no target → refused
    r_blank = await memory_forget(workspace_id=WS)
    check("blank forget refused (deletion safety)", r_blank["success"] is False)
    check("refusal message explains why", "specific target" in r_blank.get("message", ""))

    # No match
    r_nomatch = await memory_forget(fact_text_contains="nonexistent junk xyzzy", workspace_id=WS)
    check("no-match returns success=false", r_nomatch["success"] is False)
    check("no-match count is 0", r_nomatch["invalidated_count"] == 0)

    # Cross-workspace isolation: forgetting in WS-A doesn't touch WS-B
    await memory_remember(
        fact_text="Shared fact for isolation test",
        category="exact_value",
        workspace_id=f"{WS}-A",
    )
    await memory_forget(fact_text_contains="Shared fact", workspace_id=WS)  # different ws
    with SessionLocal() as db:
        isolated = (
            db.query(TurnFact)
            .filter(TurnFact.workspace_id == f"{WS}-A", TurnFact.status == "active")
            .count()
        )
    check("cross-workspace isolation (WS-A untouched)", isolated == 1, f"{isolated} active in WS-A")


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
def cleanup():
    try:
        with SessionLocal() as db:
            db.query(TurnFact).filter(
                TurnFact.workspace_id.in_([WS, f"{WS}-A"])
            ).delete(synchronize_session=False)
            db.commit()
        print(f"\n{INFO} Cleaned up smoke-test rows")
    except Exception as e:
        print(f"\n{INFO} cleanup skipped: {e}")


async def main():
    print("=" * 70)
    print("MEMORY TOOLS — END-TO-END SMOKE TEST (real dev DB)")
    print("=" * 70)
    try:
        phase1_registry()
        fid = await phase2_remember()
        phase3_sql_verify()
        await phase4_forget(fid)
    finally:
        cleanup()

    print("\n" + "=" * 70)
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    for name, ok, detail in _results:
        mark = PASS if ok else FAIL
        print(f"  {mark} {name}" + (f" — {detail}" if detail else ""))
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
