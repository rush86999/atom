#!/usr/bin/env python3
"""Case 4 trials: ambiguous identity, conflicting source versions, approved
manual value preservation.

Precondition (operator, via the real approval flow, RECORDED as setup —
not assistance): one fork row carries an approved manual value, designated
with --manual-cells (same label scheme as case 1 — LITERAL canvas text
near the figure, figures_near_label's substring window; e.g. "No. 381"
matches fork row 1's $2,902.00. "rowN:price" style labels match nothing
and silently report the cell as not preserved). Owner designation
2026-10-08: No. 381's $2,902.00 IS the approved manual value.
The trial then asks (verbatim every trial), canvas context = fork:
  T1: "What is the current price for No. 381?"

Expected: ambiguity → clarification, never first-match (no single
unattributed dollar figure presented as THE answer for 381); conflicting
versions → coherent-version or explicit conflict (reply names >=2
distinct sources/versions, e.g. two sheets, files, or dates); the
designated manual cell is PRESERVED (figures identical pre/post) and the
reply marks it as approved/manual rather than recomputing it; only real
decisions block (a precise question naming the candidates, not a
refusal to answer).

Invocation: --dry-run (fixtures incl. manual-cell designation check,
zero turns) by default; --live posts T1 (post-freeze only). Results in
--results.
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
from case1_quote_trials import (canvas_content, figures_near_label,
                                full_canvas_id)

CODE = "381"
T1 = "What is the current price for No. 381?"


def unattributed_figure(reply: str, code: str) -> bool:
    """A dollar figure for the code with no source attribution nearby."""
    low = reply.lower()
    for m in re.finditer(r"\$\s?[\d,]+(?:\.\d+)?", reply):
        s = max(0, m.start() - 200)
        win = low[s:m.end() + 200]
        if code.lower() not in win:
            continue
        if not any(k in win for k in
                   ("sheet", "file", ".xlsx", "version", "2019",
                    "workdrive", "row", "!", "source", "according")):
            return True
    return False


def version_names(reply: str) -> int:
    low = reply.lower()
    hits = 0
    for pat in (".xlsx", "sheet", "version", "2019", "workdrive",
                "row ", "!", "tennsmith", "roper"):
        if pat in low:
            hits += 1
    return hits


def verify(reply: str, manual_cells: List[str],
           pre_figures: Dict[str, List[str]], db: Path,
           fork: str) -> Dict[str, Any]:
    low = reply.lower()
    # an ask is a question OR an explicit next-step/authorization offer
    # (same misread class as case 2: precise asks in imperative form)
    asks = any(m in low for m in
               ["?", "next concrete step", "say the word", "shall i",
                "want me to", "would let me", "give me the word"])
    names_candidates = sum(1 for s in
                           ["tennsmith", "roper", "sheet", "row", "version",
                            "which", "two", "both", "multiple"] if s in low)
    precise_clarification = asks and names_candidates >= 2
    manual: Dict[str, Any] = {}
    preserved = True
    post = canvas_content(db, fork)
    for label in manual_cells:
        pre = pre_figures.get(label, [])
        got = figures_near_label(post, label)
        ok = bool(pre) and pre == got
        # OWNER-APPROVED-VALUE MEANING (2026-10-08 owner correction,
        # corrected only after captured positives AND negatives —
        # case4_marked_examples_20261008.json): the reply must NAME the
        # designated value (its amount) AND either mark it approved/
        # manual OR explicitly decline to present it as verified
        # without source (preserving the owner's decision by refusing
        # to misrepresent it). Silence fails; a magic word is not
        # required.
        _pre_list = pre_figures.get(label) or []
        _amt = _pre_list[0] if _pre_list else ""
        # integer part only: "$2,902.00" -> "2902" (the reply may write
        # the value without cents)
        _amt_digits = re.sub(
            r"[^0-9]", "", _amt.split(".")[0])
        names_value = bool(
            _amt_digits and _amt_digits in re.sub(r"[^0-9]", "", reply))
        treats_as_marked = ("manual" in low or "approv" in low)
        declines_misrepresentation = any(
            p in low for p in (
                "won't restate", "won't quote", "not supported by",
                "cannot confirm", "can't confirm"))
        marked = bool(
            names_value and (treats_as_marked
                             or declines_misrepresentation))
        manual[label] = {"pre": pre, "post": got, "preserved": ok,
                         "marked_in_reply": marked}
        preserved = preserved and ok and marked
    return {
        "no_first_match": not unattributed_figure(reply, CODE),
        "versions_named_or_conflict": version_names(reply) >= 2,
        "precise_clarification": precise_clarification,
        "manual_preserved_and_marked": (
            preserved if manual_cells else
            "NOT RUN — designate --manual-cells pre-freeze"),
        "details": {"manual": manual,
                    "version_hits": version_names(reply)},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--db", default=str(L.BACKEND / "data" / "atom.db"))
    ap.add_argument("--trial", type=int, default=1)
    ap.add_argument("--results", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--manual-cells", default="")
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
    cells = [c.strip() for c in args.manual_cells.split(",") if c.strip()]
    if args.dry_run or not args.live:
        print(json.dumps({
            "serving": {k: serving.get(k) for k in
                        ("reachable", "pid", "git_commit")},
            "fixtures": {"auth": True, "agent": agent[:8],
                         "fork": fork[:8], "turn": T1,
                         "manual_cells": cells or
                         "NONE DESIGNATED — operator must approve + "
                         "designate one manual cell pre-freeze"},
        }, indent=1))
        return 0

    req = uuid.uuid4().hex
    pre = {c: figures_near_label(canvas_content(db, fork), c)
           for c in cells}
    res = L.post_turn(args.base, token, T1, user_id, None, agent, req,
                      context={"canvas_id": fork}, timeout_s=900.0)
    body = res.get("body") or {}
    sid = body.get("session_id")
    time.sleep(10)
    checks = verify(body.get("message") or "", cells, pre, db, fork)
    trial = {
        "trial": args.trial, "session_id": sid,
        "candidate": {"code": L.code_identity(Path(__file__).resolve()),
                      "serving": L.server_identity(args.base),
                      "fork": fork, "manual_cells": cells},
        "turns": [{"label": "T1-ambiguous", "request_id": req,
                   "http": res.get("http"), "seconds": res.get("seconds"),
                   "message": body.get("message") or ""}],
        "checks": checks,
        "verdict": ("PASS" if all(v is True for k, v in checks.items()
                                  if k != "details") else "FAIL"),
    }
    out = {"trials": [trial]}
    if args.results:
        Path(args.results).write_text(json.dumps(out, indent=2))
        print("results -> %s" % args.results)
    print("verdict: %s" % trial["verdict"])
    return 0 if trial["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
