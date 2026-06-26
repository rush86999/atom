#!/usr/bin/env python3
"""
Smoke test for the verified-outcome gating contract — exercises the real
code paths against the REAL dev DB (backend/atom_dev.db).

Validates the full "silent no-op cannot graduate" contract:
  1. parse_tool_outcome classifies the tri-state correctly across return shapes
  2. AgentReasoningStep persists the verified state + evidence
  3. CapabilityGraduationService gates graduation on verified='verified' only
     - 5 verified successes promote STUDENT → INTERN
     - 20 unverified successes do NOT promote (the critic's exact scenario)
     - failed_verification never increments verified_success
  4. The silent no-op scenario end-to-end: {success:true} without evidence
     lands as 'unverified' and cannot inflate capability stats

No LLM keys required — this tests the contract layer, not the LLM layer.
Run:
    cd backend && PYTHONPATH=..:. python3 scripts/smoke_test_verified_gating.py
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
from core.models import AgentRegistry, AgentExecution, AgentReasoningStep, ExecutionStatus
from core.tool_outcome_verifier import (
    FAILED_VERIFICATION,
    UNVERIFIED,
    VERIFIED,
    parse_tool_outcome,
)
from core.capability_graduation_service import (
    CapabilityGraduationService,
    CapabilityMaturityLevel,
)

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
INFO = "\033[36m....\033[0m"
_results: list[tuple[str, bool, str]] = []
AGENTS_CREATED: list[str] = []
STEPS_CREATED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    _results.append((name, ok, detail))
    mark = PASS if ok else FAIL
    print(f"{mark} {name}" + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# PHASE 1 — parse_tool_outcome across the contract surface
# ---------------------------------------------------------------------------
def phase1_parser():
    print(f"\n{INFO} PHASE 1: parse_tool_outcome — tool-return classification")

    # The silent no-op: the critic's exact scenario
    noop = parse_tool_outcome({"success": True, "message": "Email sent"})
    check("silent no-op → unverified (NOT verified)", noop.kind == UNVERIFIED, noop.kind)
    check("no-op still records self-reported success", noop.success is True)

    # Verified with evidence
    v = parse_tool_outcome({
        "success": True, "verified": True, "evidence": "row id 42 inserted"
    })
    check("verified + evidence → VERIFIED", v.kind == VERIFIED)
    check("evidence captured", v.evidence == "row id 42 inserted")

    # Explicit failed verification
    fv = parse_tool_outcome({"success": True, "verified": False, "evidence": "DOM unchanged"})
    check("explicit verify-fail → FAILED_VERIFICATION", fv.kind == FAILED_VERIFICATION)

    # Python-repr string (tools commonly return str(dict))
    s = parse_tool_outcome("{'success': True, 'verified': True, 'evidence': 'file exists'}")
    check("python-repr string → VERIFIED", s.kind == VERIFIED, s.kind)

    # Plain string (backward-compat — existing tools)
    plain = parse_tool_outcome("created the file")
    check("plain string → unverified", plain.kind == UNVERIFIED)

    # None / garbage never raises
    check("None → unverified, no raise", parse_tool_outcome(None).kind == UNVERIFIED)
    check("garbage → unverified, no raise", parse_tool_outcome(object()).kind == UNVERIFIED)


# ---------------------------------------------------------------------------
# PHASE 2 — persistence: AgentReasoningStep.verified lands in the real DB
# ---------------------------------------------------------------------------
def phase2_persistence():
    print(f"\n{INFO} PHASE 2: verified state persists to real DB")
    with SessionLocal() as db:
        # Need a parent execution
        exec_row = AgentExecution(
            id="smoke-verified-exec",
            agent_id="smoke-verified-agent",
            status=ExecutionStatus.COMPLETED.value,
            input_summary="verified gating smoke",
        )
        db.add(exec_row)
        db.commit()

        cases = [
            ("step-verified", VERIFIED, "screenshot hash abc123"),
            ("step-unverified", UNVERIFIED, None),
            ("step-failed-verif", FAILED_VERIFICATION, "DOM unchanged after click"),
        ]
        for step_id, kind, evidence in cases:
            step = AgentReasoningStep(
                id=step_id,
                execution_id="smoke-verified-exec",
                step_number=1,
                step_type="action",
                observation="tool output",
                verified=kind,
                verification_evidence=evidence,
            )
            db.add(step)
            STEPS_CREATED.append(step_id)
        db.commit()

        # Read back
        for step_id, expected_kind, expected_ev in cases:
            row = db.get(AgentReasoningStep, step_id)
            ok = row.verified == expected_kind and row.verification_evidence == expected_ev
            check(f"persisted {step_id} ({expected_kind})", ok,
                  f"got verified={row.verified}, evidence={row.verification_evidence!r}")

    # cleanup the execution
    with SessionLocal() as db:
        db.query(AgentExecution).filter_by(id="smoke-verified-exec").delete()
        db.commit()


# ---------------------------------------------------------------------------
# PHASE 3 — graduation gating: the core defense
# ---------------------------------------------------------------------------
def _make_agent(db, agent_id: str, capability: str) -> str:
    agent = AgentRegistry(
        id=agent_id,
        name=f"smoke-{agent_id}",
        category="test",
        module_path="test.module",
        class_name="TestClass",
    )
    agent.configuration = {"capability_stats": {}, "capability_maturities": {}}
    db.add(agent)
    db.commit()
    AGENTS_CREATED.append(agent_id)
    return agent_id


def phase3_graduation_gating():
    print(f"\n{INFO} PHASE 3: graduation gates on verified='verified'")

    # --- 3a: 5 VERIFIED successes promote STUDENT → INTERN ---
    with SessionLocal() as db:
        aid = _make_agent(db, "smoke-verified-grad", "send_email")
        svc = CapabilityGraduationService(db)
        for _ in range(5):
            svc.record_usage(aid, "send_email", success=True, verified=VERIFIED)
        maturity = svc.get_maturity(aid, "send_email")
    check("5 verified successes → INTERN", maturity == CapabilityMaturityLevel.INTERN, maturity)

    # --- 3b: the critic's exact scenario — many UNVERIFIED successes do NOT promote ---
    with SessionLocal() as db:
        aid = _make_agent(db, "smoke-noop-grad", "send_email")
        svc = CapabilityGraduationService(db)
        for _ in range(20):  # well past the 5-success threshold
            svc.record_usage(aid, "send_email", success=True, verified=UNVERIFIED)
        maturity = svc.get_maturity(aid, "send_email")
    check("20 unverified successes stay STUDENT (no-op defense)", maturity == CapabilityMaturityLevel.STUDENT, maturity)

    # --- 3c: failed_verification never counts toward graduation ---
    with SessionLocal() as db:
        aid = _make_agent(db, "smoke-failverif-grad", "deploy")
        svc = CapabilityGraduationService(db)
        for _ in range(50):  # way past any threshold
            svc.record_usage(aid, "deploy", success=True, verified=FAILED_VERIFICATION)
        maturity = svc.get_maturity(aid, "deploy")
    check("50 failed-verification → stays STUDENT", maturity == CapabilityMaturityLevel.STUDENT, maturity)

    # --- 3d: mixed — only the verified ones count toward threshold ---
    with SessionLocal() as db:
        aid = _make_agent(db, "smoke-mixed-grad", "create_invoice")
        svc = CapabilityGraduationService(db)
        # 4 verified + 30 unverified → still STUDENT (needs 5 verified)
        for _ in range(4):
            svc.record_usage(aid, "create_invoice", success=True, verified=VERIFIED)
        for _ in range(30):
            svc.record_usage(aid, "create_invoice", success=True, verified=UNVERIFIED)
        maturity = svc.get_maturity(aid, "create_invoice")
    check("4 verified + 30 unverified → still STUDENT (needs 5 verified)", maturity == CapabilityMaturityLevel.STUDENT, maturity)

    # one more verified tips it over (reopen a session to keep it clean)
    with SessionLocal() as db:
        svc = CapabilityGraduationService(db)
        svc.record_usage(aid, "create_invoice", success=True, verified=VERIFIED)
        maturity = svc.get_maturity(aid, "create_invoice")
    check("+1 more verified (5 total) → INTERN", maturity == CapabilityMaturityLevel.INTERN, maturity)

    # --- 3e: stats are recorded honestly ---
    with SessionLocal() as db:
        agent = db.query(AgentRegistry).get("smoke-mixed-grad")
        stats = agent.configuration["capability_stats"]["create_invoice"]
    check("stats.total counts everything", stats["total"] == 35, str(stats["total"]))
    check("stats.success counts self-reported", stats["success"] == 35, str(stats["success"]))
    check("stats.verified_success counts only verified", stats["verified_success"] == 5, str(stats["verified_success"]))


# ---------------------------------------------------------------------------
# PHASE 4 — end-to-end silent no-op scenario
# ---------------------------------------------------------------------------
def phase4_noop_e2e():
    print(f"\n{INFO} PHASE 4: silent no-op end-to-end (the critic's scenario)")
    # Simulate: a buggy tool returns {success:true} but did nothing.
    buggy_tool_return = {"success": True, "message": "Invoice created"}
    outcome = parse_tool_outcome(buggy_tool_return)
    check("no-op return parsed as unverified", outcome.kind == UNVERIFIED)

    # Persist as a reasoning step would
    with SessionLocal() as db:
        exec_row = AgentExecution(
            id="smoke-noop-exec",
            agent_id="smoke-noop-agent",
            status=ExecutionStatus.COMPLETED.value,
        )
        db.add(exec_row)
        step = AgentReasoningStep(
            id="smoke-noop-step",
            execution_id="smoke-noop-exec",
            step_number=1,
            step_type="action",
            observation=str(buggy_tool_return),
            verified=outcome.kind,        # 'unverified'
            verification_evidence=outcome.evidence,  # None
        )
        db.add(step)
        STEPS_CREATED.append("smoke-noop-step")
        db.commit()
        row = db.get(AgentReasoningStep, "smoke-noop-step")
        check("no-op persisted as unverified", row.verified == UNVERIFIED)
        check("no-op evidence is null", row.verification_evidence is None)

        # Now feed that outcome to graduation 20 times — must NOT promote
        aid = _make_agent(db, "smoke-noop-e2e-agent", "create_invoice")
        svc = CapabilityGraduationService(db)
        for _ in range(20):
            svc.record_usage(aid, "create_invoice", success=outcome.success, verified=outcome.kind)
        maturity = svc.get_maturity(aid, "create_invoice")
    check("20 no-op 'successes' cannot graduate the capability", maturity == CapabilityMaturityLevel.STUDENT, maturity)

    # cleanup
    with SessionLocal() as db:
        db.query(AgentExecution).filter_by(id="smoke-noop-exec").delete()
        db.commit()


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
def cleanup():
    try:
        with SessionLocal() as db:
            for aid in AGENTS_CREATED:
                db.query(AgentRegistry).filter_by(id=aid).delete()
            for sid in STEPS_CREATED:
                db.query(AgentReasoningStep).filter_by(id=sid).delete()
            db.commit()
        print(f"\n{INFO} Cleaned up {len(AGENTS_CREATED)} agents + {len(STEPS_CREATED)} steps")
    except Exception as e:
        print(f"\n{INFO} cleanup skipped: {e}")


def main():
    print("=" * 72)
    print("VERIFIED-GATING SMOKE TEST — silent no-op cannot graduate")
    print("=" * 72)
    try:
        phase1_parser()
        phase2_persistence()
        phase3_graduation_gating()
        phase4_noop_e2e()
    finally:
        cleanup()

    print("\n" + "=" * 72)
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 72)
    for name, ok, detail in _results:
        mark = PASS if ok else FAIL
        print(f"  {mark} {name}" + (f" — {detail}" if detail else ""))
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
