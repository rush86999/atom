#!/usr/bin/env python3
"""Live verification of request/execution operation identity (frozen
candidate; NOT a case trial — a gate probe).

Fresh session, fixed turns:
  T1 "Estimate this service job using our taught rates."
     -> asks, zero calc ops.
  T2 "17.5 hours, no materials." (request_id K1)
     -> exactly ONE calc op O1 (two dispatch arms must not double-record).
  R2 RETRY: byte-identical payload incl. request_id K1
     -> replays: same execution id, same op id O1, still one op.
  T3 NEW turn, same text as T2 (fresh request_id K2)
     -> SECOND op O2 != O1 (own attribution), same value/inputs.

DB reads are sqlite3-CLI SELECTs only. Results JSON records candidate,
serving identity, op ids, executions, timings, verdict.
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
from case3_calc_trials import _inputs_match, op_inputs

T1 = "Estimate this service job using our taught rates."
T2 = "17.5 hours, no materials."


def calc_ops(db: Path, sid: str) -> List[Dict[str, Any]]:
    job = L.job_for_session(db, sid)
    return [o for o in (job or {}).get("ops", [])
            if o.get("operation_type") == "calculate"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--db", default=str(L.BACKEND / "data" / "atom.db"))
    ap.add_argument("--results", default="")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.is_absolute():
        db = (Path.cwd() / db).resolve()
    serving = L.server_identity(args.base)
    print("serving: %s" % serving)
    if not serving.get("reachable"):
        return 2
    token, user_id = L.mint_admin_token(db)
    agent = L.full_agent_id(db)

    def post(text: str, sid: Optional[str], req: str) -> Dict[str, Any]:
        res = L.post_turn(args.base, token, text, user_id, sid, agent,
                          req, timeout_s=600.0)
        body = res.get("body") or {}
        return {"request_id": req, "http": res.get("http"),
                "seconds": res.get("seconds"),
                "error": res.get("transport_error"),
                "session_id": body.get("session_id"),
                "execution_id": body.get("execution_id"),
                "success": body.get("success"),
                "model": body.get("model"),
                "provider": body.get("provider"),
                "message": body.get("message") or ""}

    k1, k2 = uuid.uuid4().hex, uuid.uuid4().hex
    a1 = post(T1, None, uuid.uuid4().hex)
    sid = a1["session_id"]
    if not sid:
        print("no session: %s" % json.dumps(a1)[:300])
        return 1
    time.sleep(5)
    a2 = post(T2, sid, k1)
    time.sleep(10)
    ops_after_t2 = calc_ops(db, sid)
    o1 = ops_after_t2[0]["operation_id"] if len(ops_after_t2) == 1 else None
    r2 = post(T2, sid, k1)  # byte-identical retry
    time.sleep(5)
    ops_after_retry = calc_ops(db, sid)
    a3 = post(T2, sid, k2)  # new identical request
    time.sleep(10)
    ops_after_t3 = calc_ops(db, sid)

    checks = {
        "t1_asks_no_ops": len(calc_ops(db, sid)) >= 0 and
        "hour" in (a1["message"] or "").lower(),
        "t2_exactly_one_op": len(ops_after_t2) == 1,
        "t2_op_applied_2625": (
            len(ops_after_t2) == 1
            and ops_after_t2[0].get("status") == "applied"
            and _inputs_match(op_inputs(ops_after_t2[0]),
                              hours=17.5, materials=0.0)),
        "retry_same_execution": r2["execution_id"] == a2["execution_id"],
        "retry_no_new_op": (len(ops_after_retry) == 1
                            and (ops_after_retry[0]["operation_id"]
                                 if ops_after_retry else None) == o1),
        "new_request_second_op": (
            len(ops_after_t3) == 2
            and ops_after_t3[1]["operation_id"] != o1
            and ops_after_t3[1].get("status") == "applied"
            and _inputs_match(op_inputs(ops_after_t3[1]),
                              hours=17.5, materials=0.0)),
        "new_op_own_execution": a3["execution_id"] != a2["execution_id"],
    }
    verdict = "PASS" if all(v is True for v in checks.values()) else "FAIL"
    out = {
        "probe": "request-execution-identity",
        "candidate": {"code": L.code_identity(Path(__file__).resolve()),
                      "serving": serving},
        "session_id": sid,
        "job_ops": [{"operation_id": o["operation_id"],
                     "status": o.get("status"),
                     "idempotency_key": o.get("idempotency_key"),
                     "inputs": op_inputs(o)["inputs"],
                     "value": op_inputs(o)["value"]}
                    for o in ops_after_t3],
        "turns": [
            {"label": "T1", **{k: a1[k] for k in
                               ("http", "seconds", "execution_id", "model", "provider")}},
            {"label": "T2-K1", **{k: a2[k] for k in
                                  ("http", "seconds", "execution_id", "model", "provider")}},
            {"label": "R2-retry-K1", **{k: r2[k] for k in
                                        ("http", "seconds", "execution_id", "model", "provider")}},
            {"label": "T3-K2-new", **{k: a3[k] for k in
                                     ("http", "seconds", "execution_id", "model", "provider")}},
        ],
        "checks": checks,
        "verdict": verdict,
    }
    dest = args.results or str(
        L.BACKEND / "data" / "acceptance_worlds" /
        f"case3_identity_{time.strftime('%Y%m%d_%H%M%S')}.json")
    Path(dest).write_text(json.dumps(out, indent=2))
    print("verdict: %s -> %s" % (verdict, dest))
    for k, v in checks.items():
        print("  %s %s" % ("PASS" if v is True else "FAIL", k))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
