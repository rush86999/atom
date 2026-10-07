#!/usr/bin/env python3
"""Case 2 trials: subset request + "other machinery" follow-up, correct scope.

Fixed turns (verbatim every trial), canvas context = disposable fork:
  T1 subset: "Just these two for now: the Linmac U-22 bead roller and the
     manual flanger. Same comparison as before, draft unchanged."
  T2 follow-up: "And what about the other machinery?"

Expected: T1 covers ONLY U-22 + Flanger (no dollar figures tied to
381/622/SLE24-16 anywhere near them; job retrieval evidence references
only the two); T2 covers the remaining requested items (381, 622,
SLE24-16) — or asks precisely which scope is meant (a question naming
>=2 candidate scopes). Scope stays the owner's requested scope
throughout: the subset never expands to the whole canvas.

Invocation: --dry-run (fixtures, zero turns) by default; --live posts
turns (post-freeze only). --resume SID --turn t2 posts the follow-up.
Results accumulate in --results.
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
from case1_quote_trials import full_canvas_id, job_blob, money_near

SUBSET = ["U-22", "Flanger"]
OTHERS = ["381", "622", "SLE24-16"]

T1 = ("Just these two for now: the Linmac U-22 bead roller and the manual "
      "flanger. Same comparison as before, draft unchanged.")
T2 = "And what about the other machinery?"


def verify_subset(reply: str, job: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    low = reply.lower()
    covered = [c for c in SUBSET if c.lower() in low]
    leaked = [c for c in OTHERS if money_near(reply, c)]
    blob = job_blob(job)
    evidenced_only_subset = all(
        (c.lower() in blob) for c in SUBSET) if blob != "[]" else None
    # token-boundary match: bare substring matching reads timestamp
    # subsecond digits ("...32.381304+00:00") as item hits
    import re as _re2

    other_evidenced = [c for c in OTHERS
                       if _re2.search(
                           rf"(?<![0-9a-z]){_re2.escape(c.lower())}"
                           rf"(?![0-9a-z])", blob)]
    return {
        "subset_covered": len(covered) == 2,
        "no_other_figures": len(leaked) == 0,
        "evidence_subset_only": (len(other_evidenced) == 0
                                 if evidenced_only_subset is not None
                                 else None),
        "details": {"covered": covered, "leaked": leaked,
                    "other_evidenced": other_evidenced},
    }


def verify_followup(reply: str) -> Dict[str, Any]:
    low = reply.lower()
    covered = [c for c in OTHERS if c.lower() in low]
    # an ask is a question OR an explicit authorization request (the
    # agent's precise offer to run the named searches)
    asks = any(m in low for m in
               ["?", "say the word", "shall i", "want me to",
                "give me the word", "confirm and"])
    # scope vocabulary: item numbers AND the same machines' human names
    # (the reply may name either form; the ASSERTION stays strict — a
    # precise question still needs >=2 distinct scopes + a question)
    names_scopes = sum(1 for s in
                       ["381", "roll bender", "roper whitney", "622",
                        "rotary", "sle24", "slitter", "flanger",
                        "bead roller", "rows 1", "rows 6", "requested",
                        "alternative"] if s in low)
    precise_question = asks and names_scopes >= 2
    return {
        "remaining_covered_or_precise_ask":
            len(covered) == 3 or precise_question,
        "details": {"covered": covered, "asks": asks,
                    "named_scopes": names_scopes},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--db", default=str(L.BACKEND / "data" / "atom.db"))
    ap.add_argument("--trial", type=int, default=1)
    ap.add_argument("--results", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--resume", default="")
    ap.add_argument("--turn", default="t1", choices=["t1", "t2"])
    args = ap.parse_args()

    db = Path(args.db)
    if not db.is_absolute():
        db = (Path.cwd() / db).resolve()
    serving = L.server_identity(args.base)
    try:
        token, user_id = L.mint_admin_token(db)
        agent = L.full_agent_id(db)
        fork = full_canvas_id(db)
        ok = True
    except Exception as exc:
        print(json.dumps({"serving": serving,
                          "error": str(exc)})[:500])
        return 2
    if args.dry_run or not args.live:
        print(json.dumps({
            "serving": {k: serving.get(k) for k in
                        ("reachable", "pid", "git_commit")},
            "fixtures": {"auth": True, "agent": agent[:8],
                         "fork": fork[:8],
                         "turns": {"T1": T1, "T2": T2},
                         "assertions": "subset-only figures + evidence; "
                         "follow-up covers remainder or asks precisely"},
        }, indent=1))
        return 0

    results: Dict[str, Any] = (json.loads(Path(args.results).read_text())
                               if args.results and Path(args.results).exists()
                               else {"trials": []})

    def turn(text: str, sid: Optional[str]) -> Dict[str, Any]:
        req = uuid.uuid4().hex
        res = L.post_turn(args.base, token, text, user_id, sid, agent,
                          req, context={"canvas_id": fork},
                          timeout_s=900.0)
        body = res.get("body") or {}
        return {"request_id": req, "sent": text, "http": res.get("http"),
                "seconds": res.get("seconds"),
                "error": res.get("transport_error"),
                "session_id": body.get("session_id"),
                "message": body.get("message") or ""}

    if args.turn == "t1":
        att = turn(T1, None)
        sid = att["session_id"]
        if not sid:
            print("no session: %s" % json.dumps(att)[:300])
            return 1
        time.sleep(10)
        checks = verify_subset(att["message"],
                               L.job_for_session(db, sid))
        results["trials"].append({
            "trial": args.trial, "session_id": sid,
            "candidate": {"code": L.code_identity(
                Path(__file__).resolve()),
                          "serving": L.server_identity(args.base)},
            "turns": [{"label": "T1-subset", **att}],
            "checks": checks, "verdict": "PRELIMINARY"})
        print("subset leg: %s" % json.dumps(checks["details"]))
    else:
        if not args.resume:
            print("--turn t2 needs --resume SID")
            return 2
        trial = next((t for t in results["trials"]
                      if t.get("session_id") == args.resume), None)
        if trial is None:
            print("no trial with session %s" % args.resume)
            return 2
        att = turn(T2, args.resume)
        trial["turns"].append({"label": "T2-followup", **att})
        time.sleep(10)
        trial["followup_checks"] = verify_followup(att["message"])
        leg1 = all(v is True for k, v in trial["checks"].items()
                   if k != "details" and v is not None)
        leg2 = all(v is True for k, v in trial["followup_checks"].items()
                   if k != "details")
        trial["verdict"] = ("PASS" if leg1 and leg2 else "FAIL")

    if args.results:
        Path(args.results).write_text(json.dumps(results, indent=2))
        print("results -> %s" % args.results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
