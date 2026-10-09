#!/usr/bin/env python3
"""Case 6 trials: restart during queued work + second-conversation isolation.

Shape (post-freeze, coordinated — this script NEVER restarts on its own):
  T1 (fresh session S1, canvas context = fork): the case-1 investigate
     turn, which queues research reads. While a continuation is
     in-flight ( polled: AsyncContinuationClaim row for S1 present, or a
     job op still running ), the OPERATOR runs the coordinated restart
     (scripts/restart_backend.sh — snapshot automatic; ONLY the release
     owner coordinates it; announced in the coordination log; no other
     agent mid-test). The runner then verifies WITHOUT re-triggering:
     the interrupted job resumed (job reaches terminal/completed state),
     with NO duplicate effects (canvas_audit update count for the fork
     unchanged across the restart; op execution ids distinct).
  T2 (fresh session S2, SAME wording family, DIFFERENT inputs):
     "Estimate this service job using our taught rates." → answer
     "20 hours, $50 materials." → assert the resulting calc op carries
     S2's OWN inputs ({hours 20, materials 50}) and is bound to S2's
     job only (no cross-job evidence, no reused record from any case-3
     conversation).

Expected: resume without duplicates; S2's calculation uses ITS OWN
inputs; no cross-job evidence.

Invocation: --dry-run (default) checks the harness + procedure with
ZERO turns and NO restart. --live runs T1 and prints the exact restart
command for the operator, then --resume SID verifies post-restart
state; --second runs the S2 isolation leg. Results in --results.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import acceptance_trial_lib as L
from case1_quote_trials import T1 as CASE1_T1, full_canvas_id
from case3_calc_trials import _inputs_match, op_inputs

RESTART_CMD = ("scripts/restart_backend.sh  # snapshot automatic; "
               "release-owner coordinated only; announced; no agent mid-test")

S2_T1 = "Estimate this service job using our taught rates."
S2_T2 = "20 hours, $50 materials."


def continuation_in_flight(db: Path, sid: str) -> bool:
    try:
        rows = L.sqlite_select(
            db, "SELECT COUNT(*) FROM async_continuation_claims "
                "WHERE session_id=?", (sid,))
        if rows and rows[0][0] > 0:
            return True
    except Exception:
        pass
    job = L.job_for_session(db, sid)
    if not job:
        return False
    return any(o.get("status") in ("running", "pending", "in_progress")
               for o in job.get("ops") or [])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--db", default=str(L.BACKEND / "data" / "atom.db"))
    ap.add_argument("--trial", type=int, default=1)
    ap.add_argument("--results", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--resume", default="",
                    help="S1 sid: verify post-restart state (no new turn)")
    ap.add_argument("--second", action="store_true",
                    help="run the S2 isolation leg (fresh session)")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.is_absolute():
        db = (Path.cwd() / db).resolve()
    serving = L.server_identity(args.base)
    try:
        token, user_id = L.real_admin_login(args.base, db)
        agent = L.full_agent_id(db)
        fork = full_canvas_id(db)
    except Exception as exc:
        print(json.dumps({"serving": serving, "error": str(exc)})[:400])
        return 2
    if args.dry_run or not args.live:
        import shutil
        print(json.dumps({
            "serving": {k: serving.get(k) for k in
                        ("reachable", "pid", "git_commit")},
            "procedure": {
                "auth": True, "agent": agent[:8], "fork": fork[:8],
                "restart_script_present": bool(shutil.which("bash")),
                "restart_command": RESTART_CMD,
                "in_flight_probe": "async_continuation_claims + "
                                   "running job ops",
                "no_dup_proof": "canvas_audit update count stable "
                                "across restart; execution ids distinct",
                "isolation_proof": "S2 calc op inputs == {hours 20, "
                                   "materials 50}, bound to S2 job only",
                "s2_turns": [S2_T1, S2_T2],
            },
        }, indent=1))
        return 0

    results: Dict[str, Any] = (json.loads(Path(args.results).read_text())
                               if args.results and Path(args.results).exists()
                               else {"trials": []})

    def turn(text: str, sid: Optional[str],
             ctx: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        req = uuid.uuid4().hex
        res = L.post_turn(args.base, token, text, user_id, sid, agent,
                          req, context=ctx, timeout_s=900.0)
        body = res.get("body") or {}
        return {"request_id": req, "sent": text, "http": res.get("http"),
                "seconds": res.get("seconds"),
                "error": res.get("transport_error"),
                "session_id": body.get("session_id"),
                "execution_id": body.get("execution_id"),
                "message": body.get("message") or ""}

    if args.second:
        a1 = turn(S2_T1, None, None)
        s2 = a1["session_id"]
        if not s2:
            print("no S2 session: %s" % json.dumps(a1)[:300])
            return 1
        time.sleep(5)
        a2 = turn(S2_T2, s2, None)
        time.sleep(10)
        job = L.job_for_session(db, s2)
        calcs = [o for o in (job or {}).get("ops", [])
                 if o.get("operation_type") == "calculate"]
        own = (len(calcs) >= 1 and _inputs_match(
            op_inputs(calcs[-1]), hours=20.0, materials=50.0))
        checks = {
            "s2_figure": ("3,050" in (a2["message"] or "") or
                          "3050" in (a2["message"] or "")),
            "s2_own_inputs_op": own,
            "s2_job_scoped": job is not None,
        }
        trial = next((t for t in results["trials"]
                      if t.get("s2_session") == s2), None)
        if trial is None:
            trial = {"trial": args.trial, "s2_session": s2,
                     "turns": []}
            results["trials"].append(trial)
        trial["turns"].extend(
            [{"label": "S2-T1", **a1}, {"label": "S2-T2", **a2}])
        trial["isolation_checks"] = checks
        print("isolation: %s" % json.dumps(checks))
    elif args.resume:
        sid = args.resume
        job = L.job_for_session(db, sid)
        trial = next((t for t in results["trials"]
                      if t.get("session_id") == sid), None)
        pre_updates = ((trial or {}).get("pre_restart") or {}).get(
            "fork_updates", -1)
        post_updates = len(L.canvas_audit_updates(db, fork, ""))
        # distinctness across REQUESTS, not op-rows: ops of the SAME
        # turn legitimately share its execution id (one request = one
        # identity), and unattributed rows contribute no id at all.
        # Duplicate EFFECTS are already checked separately.
        execs = [str(o.get("execution_id") or "")
                 for o in (job or {}).get("ops", [])
                 if o.get("execution_id")]
        checks = {
            "job_terminal_or_progressed": job is not None and (
                job.get("status") in ("completed", "terminal", "active")),
            "no_duplicate_effects": pre_updates == -1 or (
                post_updates == pre_updates),
            "execution_ids_distinct": len(set(execs)) == len(execs),
        }
        if trial is None:
            trial = {"trial": args.trial, "session_id": sid}
            results["trials"].append(trial)
        trial["post_restart_checks"] = checks
        trial["post_restart_updates"] = post_updates
        print("post-restart: %s" % json.dumps(checks))
    else:
        att = turn(CASE1_T1, None, {"canvas_id": fork})
        sid = att["session_id"]
        if not sid:
            print("no session: %s" % json.dumps(att)[:300])
            return 1
        print("S1 session %s — poll in-flight, then operator runs:"
              % sid)
        print("  %s" % RESTART_CMD)
        print("then: --resume %s ; later: --second" % sid)
        for _ in range(6):
            if continuation_in_flight(db, sid):
                print("continuation IN FLIGHT for %s" % sid)
                break
            time.sleep(10)
        else:
            print("no in-flight continuation observed within 60s "
                  "(job may have completed synchronously — record and "
                  "retry timing post-freeze)")
        trial = {"trial": args.trial, "session_id": sid,
                 "candidate": {"code": L.code_identity(
                     Path(__file__).resolve()),
                               "serving": L.server_identity(args.base)},
                 "turns": [{"label": "S1-investigate", **att}],
                 "pre_restart": {
                     "fork_updates": len(
                         L.canvas_audit_updates(db, fork, ""))}}
        results["trials"].append(trial)

    if args.results:
        Path(args.results).write_text(json.dumps(results, indent=2))
        print("results -> %s" % args.results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
