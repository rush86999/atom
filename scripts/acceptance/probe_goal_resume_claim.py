#!/usr/bin/env python3
"""Independent probe: goal-run resume claims the exact pending generation.

Scenario A (simultaneous): two callers read the same pending decision; both
try to resume it. Exactly one may execute; the other retries as a no-op.

Scenario B (stale snapshot): a caller holds an older pending-decision
snapshot while a newer decision is installed. Its claim must fail and the
newer decision must remain pending.

Scratch SQLite only; no live DB, provider or external effect.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("TESTING", "1")

from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from core.goals import goal_run_executors  # noqa: E402
from core.goals.goal_run_service import GoalRunService  # noqa: E402
from core.models import (  # noqa: E402
    Canvas, CanvasAudit, GoalObjective, GoalRun, HITLAction,
)

PLAN = [{"id": "step-1", "kind": "canvas_work", "title": "Research"}]


def _database(path: Path):
    engine = create_engine(
        f"sqlite:///{path}", connect_args={"timeout": 30})

    @event.listens_for(engine, "connect")
    def _wal(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    for table in (GoalObjective.__table__, GoalRun.__table__,
                  HITLAction.__table__, Canvas.__table__, CanvasAudit.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add(GoalObjective(
            id="goal-probe", workspace_id="ws-probe", tenant_id="t-probe",
            title="Probe quote", status="active", criteria=[], key_results=[]))
        session.commit()
    return engine, factory


def _service(factory):
    return GoalRunService(
        workspace_id="ws-probe", tenant_id="t-probe",
        session_factory=factory)


def _hold(svc, run_id, rationale):
    return svc._hold_for_approval(
        run_id,
        {"decision": "ADVANCE", "rationale": rationale},
        reason="probe checkpoint")


def _approved(run):
    return [d for d in (run.get("decision_log") or [])
            if d.get("kind") == "approved"]


def _simultaneous(factory):
    barrier = threading.Barrier(2)
    lock = threading.Lock()
    state = {"race": False, "waiters": 0}
    calls = {"executor": 0}

    class RacingService(GoalRunService):
        def get_run(self, run_id):
            run = super().get_run(run_id)
            with lock:
                wait_here = bool(
                    state["race"] and run and run.get("pending_decision"))
                if wait_here:
                    state["waiters"] += 1
                    if state["waiters"] >= 2:
                        state["race"] = False
            if wait_here:
                barrier.wait(timeout=10)
            return run

    async def _execute(self, run, decision):
        calls["executor"] += 1
        time.sleep(0.2)
        return {"executed": decision.get("decision")}

    original = goal_run_executors.GoalRunExecutors.execute
    goal_run_executors.GoalRunExecutors.execute = _execute
    try:
        creator = _service(factory)
        run_id = creator.create_run(
            "goal-probe", role="sales", plan=PLAN)["id"]
        creator.transition(run_id, "active")
        held = _hold(creator, run_id, "simultaneous")
        review = {
            "decision_id": held["decision_id"],
            "decision_binding": held["decision_binding"],
        }
        state["race"] = True
        results = []

        def worker(reviewer):
            svc = RacingService(
                workspace_id="ws-probe", tenant_id="t-probe",
                session_factory=factory)
            try:
                results.append(asyncio.run(svc.resume(
                    run_id, approved=True, reviewer=reviewer,
                    expected_decision_id=review["decision_id"],
                    expected_decision_binding=review["decision_binding"])))
            except Exception as exc:  # noqa: BLE001
                results.append({"error": f"{type(exc).__name__}: {exc}"})

        threads = [threading.Thread(target=worker, args=(name,))
                   for name in ("review-a", "review-b")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        with factory() as session:
            row = session.query(GoalRun).filter(GoalRun.id == run_id).one()
            run = creator._to_dict(row)
        return {
            "run_id": run_id,
            "results": results,
            "executor_calls": calls["executor"],
            "approved_entries": len(_approved(run)),
            "pending": run.get("pending_decision"),
            "passed": (
                len(results) == 2
                and sum(1 for r in results if r.get("resumed")) == 1
                and calls["executor"] == 1
                and len(_approved(run)) == 1
                and run.get("pending_decision") is None
                and not any("error" in r for r in results)),
        }
    finally:
        goal_run_executors.GoalRunExecutors.execute = original


def _stale(factory):
    calls = {"executor": 0}

    async def _execute(self, run, decision):
        calls["executor"] += 1
        return {"executed": decision.get("decision")}

    original = goal_run_executors.GoalRunExecutors.execute
    goal_run_executors.GoalRunExecutors.execute = _execute
    try:
        writer = _service(factory)
        run_id = writer.create_run(
            "goal-probe", role="sales", plan=PLAN)["id"]
        writer.transition(run_id, "active")
        held = _hold(writer, run_id, "old")
        review = {
            "decision_id": held["decision_id"],
            "decision_binding": held["decision_binding"],
        }
        old_snapshot = writer.get_run(run_id)
        old_generation = old_snapshot["human_interventions"]

        class StaleService(GoalRunService):
            installed = False

            def get_run(self, run_id):
                if not self.installed:
                    self.installed = True
                    newer = _service(factory)
                    _hold(newer, run_id, "newer")
                    return old_snapshot
                return super().get_run(run_id)

        stale = StaleService(
            workspace_id="ws-probe", tenant_id="t-probe",
            session_factory=factory)
        out = asyncio.run(stale.resume(
            run_id, approved=True, reviewer="stale-reviewer",
            expected_decision_id=review["decision_id"],
            expected_decision_binding=review["decision_binding"]))
        current = writer.get_run(run_id)
        return {
            "run_id": run_id,
            "result": out,
            "executor_calls": calls["executor"],
            "old_generation": old_generation,
            "current_generation": current.get("human_interventions"),
            "pending": current.get("pending_decision"),
            "approved_entries": len(_approved(current)),
            "passed": (
                out.get("resumed") is False
                and calls["executor"] == 0
                and current.get("human_interventions") > old_generation
                and (current.get("pending_decision") or {}).get("rationale")
                == "newer"
                and len(_approved(current)) == 0),
        }
    finally:
        goal_run_executors.GoalRunExecutors.execute = original


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out", default="/private/tmp/goal-resume-claim-probe.json")
    parser.add_argument(
        "--db", default="/private/tmp/goal-resume-claim-probe.db")
    args = parser.parse_args()
    db_path = Path(args.db)
    if db_path.exists():
        db_path.unlink()
    engine, factory = _database(db_path)
    try:
        report = {
            "schema": "atom-goal-resume-claim-probe-1",
            "scenario_simultaneous": _simultaneous(factory),
            "scenario_stale_snapshot": _stale(factory),
        }
        report["status"] = (
            "passed" if all(
                report[key]["passed"] for key in
                ("scenario_simultaneous", "scenario_stale_snapshot"))
            else "failed")
        Path(args.out).write_text(
            json.dumps(report, indent=2, default=str) + "\n")
        print(json.dumps(report, indent=2, default=str))
        return 0 if report["status"] == "passed" else 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
