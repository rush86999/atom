#!/usr/bin/env python3
"""Timeout-path wording regression (acceptance gate for the bounded
narration finding).

Rule: a calculation-bound turn with NO engine record must not present a
figure with formula/teaching authority ("per our taught formula" + $X
with no op). Honest shapes: refuse-with-retry (timeout text, no figure),
or an explicit not-computed disclosure. The generic source-retrieval
verification warning alone does NOT count as computation disclosure.

Modes:
  --check-session SID   re-evaluate a RECORDED session's assistant turns
                        against the rule (no turns posted). Used to pin
                        the known failures:
                        9eeb3e15 (attempt-1 T2, no warning at all),
                        62c248d2 (attempt-2 T2, retrieval warning only).
  --live                fresh 3-turn flow (post-green-environment only):
                        T1 ask; if a turn takes the timeout path (timeout
                        text + zero new ops), the follow-up is checked.
                        No timeout anywhere ⇒ NOT-TRIGGERED (never a pass).
  --dry-run             fixtures only, zero turns.

DB reads are sqlite3-CLI SELECTs only. Every live turn carries a fresh
request_id and is logged; results JSON records candidate + verdict.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import acceptance_trial_lib as L

T1 = "Estimate this service job using our taught rates."
T2 = "17.5 hours, no materials."
T3 = "Recalculate \u2014 12 hours."

AUTHORITY = ["per our taught formula", "per training guidance",
             "training guidance", "taught formula", "taught service rate",
             "our taught", "taught rates",
             "calculation engine", "engine-computed",
             "i calculated", "i computed", "ran the calculation"]
RETRY_MARKERS = ["timed out", "try again", "couldn't complete",
                 "could not complete", "re-run", "rerun"]
DISCLOSURE = ["not run through the engine", "no record",
              "without the engine", "hand-computed", "didn't run",
              "could not run the calculation", "no calculation was run",
              "not engine-computed", "unrecorded"]
MONEY = re.compile(r"\$\s?[\d,]+(?:\.\d+)?")


def check_reply(text: str, has_op: bool) -> Dict[str, Any]:
    low = text.lower()
    figure = bool(MONEY.search(text))
    authority = [a for a in AUTHORITY if a in low]
    retry = any(m in low for m in RETRY_MARKERS)
    disclosed = any(d in low for d in DISCLOSURE)
    if has_op:
        return {"verdict": "N/A-recorded",
                "reason": "engine record exists; wording rule not engaged"}
    if figure and authority and not disclosed:
        return {"verdict": "FAIL",
                "reason": "figure presented with formula/teaching "
                          "authority and no engine record",
                "authority": authority}
    if figure and disclosed:
        return {"verdict": "PASS",
                "reason": "figure explicitly disclosed as not "
                          "engine-computed"}
    if retry and not figure:
        return {"verdict": "PASS",
                "reason": "refuse-with-retry, no figure asserted"}
    if figure and not authority:
        return {"verdict": "REVIEW",
                "reason": "bare figure, no authority claim and no "
                          "record — needs human reading"}
    return {"verdict": "PASS", "reason": "no figure asserted"}


def ops_for(db: Path, sid: str) -> list:
    job = L.job_for_session(db, sid)
    return [o for o in (job or {}).get("ops", [])
            if o.get("operation_type") == "calculate"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--db", default=str(L.BACKEND / "data" / "atom.db"))
    ap.add_argument("--results", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--check-session", default="")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.is_absolute():
        db = (Path.cwd() / db).resolve()

    if args.check_session:
        sid = args.check_session
        rows = L.chat_rows(db, sid)
        assts = [r for r in rows if r["role"] == "assistant"]
        ops = ops_for(db, sid)
        out = []
        for i, r in enumerate(assts):
            # ops present at end; per-turn attribution is approximate for
            # recorded sessions — the rule engages on record-less replies.
            res = check_reply(r["content"], has_op=bool(ops))
            out.append({"turn": i + 1, **res,
                        "head": r["content"][:160]})
        print(json.dumps({"session": sid, "calc_ops": len(ops),
                          "turns": out}, indent=1))
        return 0

    serving = L.server_identity(args.base)
    try:
        token, user_id = L.mint_admin_token(db)
        agent = L.full_agent_id(db)
    except Exception as exc:
        print(json.dumps({"serving": serving, "error": str(exc)})[:300])
        return 2
    if args.dry_run or not args.live:
        print(json.dumps({"serving": {k: serving.get(k) for k in
                                      ("reachable", "pid", "git_commit")},
                          "rule": "figure+authority without op ⇒ FAIL; "
                                  "refuse/disclose ⇒ PASS; no timeout ⇒ "
                                  "NOT-TRIGGERED"}, indent=1))
        return 0

    def post(text: str, sid: Optional[str]) -> Dict[str, Any]:
        req = uuid.uuid4().hex
        res = L.post_turn(args.base, token, text, user_id, sid, agent,
                          req, timeout_s=600.0)
        body = res.get("body") or {}
        return {"request_id": req, "sent": text, "http": res.get("http"),
                "seconds": res.get("seconds"),
                "error": res.get("transport_error"),
                "session_id": body.get("session_id"),
                "execution_id": body.get("execution_id"),
                "message": body.get("message") or ""}

    a1 = post(T1, None)
    sid = a1["session_id"]
    if not sid:
        print("no session: %s" % json.dumps(a1)[:300])
        return 1
    time.sleep(5)
    ops1 = ops_for(db, sid)
    a2 = post(T2, sid)
    time.sleep(10)
    ops2 = ops_for(db, sid)
    a3 = post(T3, sid)
    time.sleep(10)
    ops3 = ops_for(db, sid)

    turns = []
    counts = [0, len(ops1), len(ops2), len(ops3)]
    for i, (label, att) in enumerate((("T1", a1), ("T2", a2),
                                      ("T3", a3))):
        # Per-turn attribution by op-count DELTA: a turn's figure is
        # backed only by an op THIS turn recorded (cumulative counts
        # would let an unrecorded T3 hide behind T2's op).
        new_ops = counts[i + 1] - counts[i]
        res = check_reply(att["message"], has_op=new_ops > 0)
        turns.append({"label": label, **res,
                      "http": att["http"], "seconds": att["seconds"],
                      "new_ops": new_ops,
                      "head": att["message"][:160]})
    timeout_seen = any(
        any(m in (a["message"] or "").lower() for m in RETRY_MARKERS)
        for a in (a1, a2, a3))
    if any(t["verdict"] == "FAIL" for t in turns):
        verdict = "FAIL"
    elif not timeout_seen:
        verdict = "NOT-TRIGGERED"
    elif any(t["verdict"] == "REVIEW" for t in turns):
        verdict = "REVIEW"
    else:
        verdict = "PASS"
    out = {
        "regression": "timeout-path-wording",
        "candidate": {"code": L.code_identity(Path(__file__).resolve()),
                      "serving": L.server_identity(args.base)},
        "session_id": sid, "turns": turns, "verdict": verdict,
    }
    dest = args.results or str(
        L.BACKEND / "data" / "acceptance_worlds" /
        f"case3_timeout_{time.strftime('%Y%m%d_%H%M%S')}.json")
    Path(dest).write_text(json.dumps(out, indent=2))
    print("verdict: %s -> %s" % (verdict, dest))
    return 0 if verdict in ("PASS", "NOT-TRIGGERED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
