#!/usr/bin/env python3
"""Public-boundary tests for TASK CORRECTION (item replacement).

WHY THIS EXISTS. "Replace U-22 with U-38" was answered with the PREVIOUS list:
U-38 was not added, U-22 was not removed, the durable task was never revised,
and the turn was narrated by the model, which also reworded a sheet name the
structured evidence had exactly right (`Tinknock!R100` for
`Tinknocker!R100`). A user cannot tell a mangled coordinate from a real one,
so this was a correctness blocker, not a cosmetic gap, and the flow was
excluded from the verified support list until it passed.

These are PUBLIC-BOUNDARY tests: every assertion is made on what the HTTP
surface returned or what is durably persisted, never on an internal call.
Each case checks FOUR things, because any one of them alone would have passed
while the user still saw the wrong thing:

  1. the TASK REVISION actually changed (durable entity set, order preserved)
  2. a REAL RETRIEVAL happened (a new attempt, and evidence for the incoming
     item -- not the outgoing item's evidence reused)
  3. the EVIDENCE BINDINGS are right (identity cell + value cell, per item)
  4. the DISPLAYED LIST matches the revised set (no stale item, no invented
     item, and every citation grounded in the record)

Sequences covered: replacement, replacement->formatting, replacement->re-search,
and reload-after-replacement (the last two are what a user does next, and both
are ways a stale list can come back).

Usage:
    task_correction_acceptance.py --base http://127.0.0.1:8071 --db <path>
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

ACC = REPO / "docs" / "architecture" / "orchestration_migration" / "acceptance"
USER_ID = "b83eb105-d9e7-41a5-83e3-a632b15b9ee3"
BASE_ASK = ("find the prices of these 8 machines in Consolidated Price List "
            "2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, "
            "TK 1624, TK Multi Wheel Gang Slitter and GSL48-16")
BASE_ORDER = ["No. 381", "U-22", "No. 622", "TK Manual Flanger", "SLE24-16",
              "TK 1624", "TK Multi Wheel Gang Slitter", "GSL48-16"]
REPLACED_ORDER = ["No. 381", "U-38", "No. 622", "TK Manual Flanger", "SLE24-16",
                  "TK 1624", "TK Multi Wheel Gang Slitter", "GSL48-16"]
REPLACE_TURN = "Replace U-22 with U-38"


def mint(db_path: str) -> Optional[str]:
    """Mint a token against the given atom.db, via the app's own auth code.

    Takes the DB PATH (not a run dir): a run dir plus "/data/atom.db" is
    correct, but the caller already has the file, and assuming the shape here
    is how you end up pointing at <run>/data/data/atom.db.
    """
    db = str(Path(db_path).resolve())
    data_dir = str(Path(db).parent)
    os.environ["DATABASE_URL"] = f"sqlite:///{db}"
    os.environ["ATOM_DATA_DIR"] = data_dir
    os.environ.pop("BYOK_KEYS_FILE", None)
    from scripts.workbook_read_replay import mint_token
    return mint_token()[0]


class Case:
    def __init__(self, cid: str, expect: str) -> None:
        self.cid, self.expect = cid, expect
        self.checks: Dict[str, bool] = {}
        self.details: Dict[str, Any] = {}
        self.notes: List[str] = []

    def check(self, name: str, ok: Any, detail: Any = None) -> bool:
        ok = bool(ok)
        self.checks[name] = ok
        if detail is not None:
            self.details[name] = detail
        return ok

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(self.checks.values())

    def as_dict(self) -> Dict[str, Any]:
        return {"case": self.cid, "expect": self.expect,
                "status": "PASS" if self.passed else "FAIL",
                "checks": self.checks, "details": self.details,
                "notes": self.notes}


def ask(base: str, token: str, session: str, message: str,
        timeout: int = 420) -> Dict[str, Any]:
    import httpx
    r = httpx.post(f"{base}/api/chat/message", timeout=timeout, trust_env=False,
                   headers={"Authorization": f"Bearer {token}"},
                   json={"message": message, "session_id": session,
                         "user_id": USER_ID,
                         "context": {"current_page": "/chat",
                                     "conversation_history": []}})
    try:
        return {"status": r.status_code, **r.json()}
    except Exception:
        return {"status": r.status_code, "raw": r.text[:300]}


def structured_for(db: str, session: str,
                   execution_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT metadata_json FROM chat_messages WHERE conversation_id=? "
            "AND role='assistant' ORDER BY created_at DESC",
            (session,)).fetchall()
    finally:
        con.close()
    best = None
    for (meta,) in rows:
        try:
            doc = json.loads(meta or "{}")
        except Exception:
            continue
        rec = ((doc.get("pending_file_result") or {}).get("structured_result"))
        if not isinstance(rec, dict):
            continue
        if execution_id and str(doc.get("execution_id") or "") != str(execution_id):
            continue
        best = rec
        break
    return best


def task_entities(db: str, conversation_id: str) -> Optional[List[str]]:
    """The DURABLE entity set, read from goal_runs.parameters.task_lifecycle."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT parameters FROM goal_runs").fetchall()
    except Exception:
        return None
    finally:
        con.close()
    for (params,) in rows:
        try:
            doc = json.loads(params or "{}")
        except Exception:
            continue
        lc = (doc or {}).get("task_lifecycle") or {}
        if lc.get("conversation_id") == conversation_id:
            rev = lc.get("task_revision") or {}
            return [str(e.get("id")) for e in (rev.get("entities") or [])]
    return None


def visible_items(text: str) -> List[str]:
    sys.path.insert(0, str(BACKEND))
    from core.answer_presentation import _visible_items
    return _visible_items(text or "")


def binding_report(rec: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    sys.path.insert(0, str(BACKEND))
    from core.answer_presentation import _identity_cells
    out: Dict[str, Dict[str, Any]] = {}
    for t in rec.get("targets") or []:
        ident = t.get("identity") or {}
        cells: List[str] = []
        for cand in ident.get("candidates") or []:
            cells.extend(_identity_cells(cand))
        values = []
        for cand in ident.get("candidates") or []:
            for v in (cand.get("values") or []):
                if isinstance(v, dict) and v.get("value") is not None:
                    values.append((v.get("col"), v.get("basis"), v.get("value")))
        out[str(t.get("item"))] = {
            "status": ident.get("status"),
            "identity_cells": sorted(set(cells)),
            "values": values[:4],
        }
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8071")
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", default=str(ACC / "task_correction_results.json"))
    ap.add_argument("--prefix", default="tc")
    args = ap.parse_args(argv)

    token = mint(args.db)
    if not token:
        print("could not mint a token against the candidate world", file=sys.stderr)
        return 2
    stamp = int(time.time())
    results: List[Dict[str, Any]] = []
    print(f"task-correction acceptance against {args.base}\n")

    # ---------------------------------------------------------------- case 1
    c = Case("replacement_applies_to_task_and_display",
             "the requested item change reaches the durable task and the "
             "displayed list, with the outgoing item gone")
    sess = f"{args.prefix}-replace-{stamp}"
    r1 = ask(args.base, token, sess, BASE_ASK)
    c.check("base_lookup_succeeded", r1.get("success") is True,
            f"status={r1.get('status')} err={r1.get('error_code')}")
    base_items = visible_items(r1.get("message") or "")
    c.check("base_lookup_shows_all_eight_in_order", base_items == BASE_ORDER,
            base_items)
    base_exec = r1.get("execution_id")
    base_rec = structured_for(args.db, sess, base_exec)
    c.check("base_lookup_has_structured_evidence", bool(base_rec))
    base_task = task_entities(args.db, sess)
    c.check("durable_task_entities_match_base_order", base_task == BASE_ORDER,
            base_task)
    base_attempt = (base_rec or {}).get("attempt_id")

    r2 = ask(args.base, token, sess, REPLACE_TURN)
    c.check("replacement_turn_succeeded", r2.get("success") is True,
            f"status={r2.get('status')} err={r2.get('error_code')}")
    rep_exec = r2.get("execution_id")
    rec2 = structured_for(args.db, sess, rep_exec)
    c.check("replacement_produced_structured_evidence", bool(rec2))
    rep_attempt = (rec2 or {}).get("attempt_id")
    c.check("replacement_performed_a_REAL_retrieval",
            bool(rep_attempt) and rep_attempt != base_attempt,
            f"{base_attempt} -> {rep_attempt}")
    c.check("replacement_evidence_action_is_a_read",
            (rec2 or {}).get("evidence_action") in ("new_read", "read_failed"),
            (rec2 or {}).get("evidence_action"))

    task2 = task_entities(args.db, sess)
    c.check("durable_task_revised_to_the_new_set",
            task2 == REPLACED_ORDER, task2)
    c.check("durable_task_removed_the_outgoing_item",
            bool(task2) and "U-22" not in task2, task2)
    c.check("durable_task_preserved_the_other_items_and_order",
            bool(task2) and [i for i in task2 if i != "U-38"]
            == [i for i in BASE_ORDER if i != "U-22"], task2)

    rec2_items = [str(t.get("item")) for t in (rec2 or {}).get("targets") or []]
    c.check("replacement_record_carries_the_new_item",
            "U-38" in rec2_items and "U-22" not in rec2_items, rec2_items)
    b2 = binding_report(rec2 or {})
    c.check("incoming_item_has_its_own_identity_cell",
            bool(b2.get("U-38", {}).get("identity_cells")),
            b2.get("U-38"))
    c.check("incoming_item_has_a_value_binding",
            bool(b2.get("U-38", {}).get("values")), b2.get("U-38"))
    u22 = b2.get("U-22")
    c.check("outgoing_items_evidence_is_not_reused",
            u22 is None, "U-22 absent from the revised record entirely")

    shown2 = visible_items(r2.get("message") or "")
    c.check("displayed_list_matches_the_revised_set", shown2 == REPLACED_ORDER,
            shown2)
    c.check("displayed_list_does_not_show_the_outgoing_item",
            "U-22" not in shown2, shown2)
    msg2 = r2.get("message") or ""
    c.check("displayed_list_does_not_silently_report_the_change_as_applied_"
            "when_nothing_changed",
            not (shown2 == BASE_ORDER),
            "the previous list would equal the base order")
    from core.answer_presentation import validate_rendered_against_record
    v2 = validate_rendered_against_record(msg2, rec2)
    c.check("displayed_citations_are_grounded_in_the_record", v2["ok"],
            {"gating": v2["gating"], "violations": v2["violations"][:3]})
    c.notes.append(f"binding={r2.get('evidence_binding')}")
    results.append(c.as_dict())
    print(f"[{c.as_dict()['status']}] {c.cid}")
    for k, v in c.checks.items():
        print(f"    {'ok ' if v else 'X  '} {k}")

    # ---------------------------------------------------------------- case 2
    c2 = Case("replacement_then_formatting",
              "a formatting follow-up after a replacement re-renders the "
              "REVISED set and does not resurrect the replaced item")
    s2 = f"{args.prefix}-replace-fmt-{stamp}"
    a = ask(args.base, token, s2, BASE_ASK)
    b = ask(args.base, token, s2, REPLACE_TURN)
    c2.check("setup_base_then_replacement", a.get("success") and b.get("success"))
    d = ask(args.base, token, s2, "Make this easier to read")
    c2.check("formatting_turn_succeeded", d.get("success") is True,
             f"status={d.get('status')} err={d.get('error_code')}")
    fmt_items = visible_items(d.get("message") or "")
    c2.check("formatted_list_is_the_revised_set", fmt_items == REPLACED_ORDER,
             fmt_items)
    c2.check("formatted_list_does_not_resurrect_the_replaced_item",
             "U-22" not in fmt_items, fmt_items)
    task_fmt = task_entities(args.db, s2)
    c2.check("durable_task_still_the_revised_set",
             task_fmt == REPLACED_ORDER, task_fmt)
    from core.answer_presentation import validate_rendered_against_record
    recd = structured_for(args.db, s2, d.get("execution_id")) or \
        structured_for(args.db, s2)
    vd = validate_rendered_against_record(d.get("message") or "", recd)
    c2.check("formatted_citations_grounded", vd["ok"],
             {"gating": vd["gating"], "violations": vd["violations"][:3]})
    results.append(c2.as_dict())
    print(f"\n[{c2.as_dict()['status']}] {c2.cid}")
    for k, v in c2.checks.items():
        print(f"    {'ok ' if v else 'X  '} {k}")

    # ---------------------------------------------------------------- case 3
    c3 = Case("replacement_then_research",
              "an explicit re-search after a replacement re-reads and still "
              "returns the revised set")
    s3 = f"{args.prefix}-replace-research-{stamp}"
    ask(args.base, token, s3, BASE_ASK)
    ask(args.base, token, s3, REPLACE_TURN)
    e = ask(args.base, token, s3, "Search again and show the same items")
    c3.check("research_turn_succeeded", e.get("success") is True,
             f"status={e.get('status')} err={e.get('error_code')}")
    rs_items = visible_items(e.get("message") or "")
    c3.check("re_search_returns_the_revised_set", rs_items == REPLACED_ORDER,
             rs_items)
    c3.check("re_search_did_not_resurrect_the_replaced_item",
             "U-22" not in rs_items, rs_items)
    rec_e = structured_for(args.db, s3, e.get("execution_id"))
    c3.check("re_search_performed_a_new_attempt",
             (rec_e or {}).get("attempt_id") not in (None, rep_attempt),
             (rec_e or {}).get("attempt_id"))
    task_rs = task_entities(args.db, s3)
    c3.check("durable_task_still_the_revised_set",
             task_rs == REPLACED_ORDER, task_rs)
    from core.answer_presentation import validate_rendered_against_record
    ve = validate_rendered_against_record(e.get("message") or "", rec_e)
    c3.check("re_search_citations_grounded", ve["ok"],
             {"gating": ve["gating"], "violations": ve["violations"][:3]})
    results.append(c3.as_dict())
    print(f"\n[{c3.as_dict()['status']}] {c3.cid}")
    for k, v in c3.checks.items():
        print(f"    {'ok ' if v else 'X  '} {k}")

    # ---------------------------------------------------------------- case 4
    c4 = Case("reload_after_replacement",
              "reloading the session returns the revised final answer, with "
              "the same evidence association and no duplicate")
    s4 = f"{args.prefix}-replace-reload-{stamp}"
    ask(args.base, token, s4, BASE_ASK)
    f = ask(args.base, token, s4, REPLACE_TURN)
    import httpx
    h = httpx.get(f"{args.base}/api/chat/history/{s4}",
                  params={"user_id": USER_ID}, timeout=90, trust_env=False,
                  headers={"Authorization": f"Bearer {token}"})
    hj = h.json() if h.status_code == 200 else {}
    rows = hj.get("messages") or []
    replies = [((m.get("response") or {}).get("message") or "") for m in rows]
    c4.check("history_returns_after_reload", h.status_code == 200,
             f"status={h.status_code}")
    c4.check("history_has_no_duplicate_turns", len(rows) == 2, len(rows))
    final = replies[-1] if replies else ""
    reload_items = visible_items(final)
    c4.check("reloaded_final_answer_is_the_revised_set",
             reload_items == REPLACED_ORDER, reload_items)
    c4.check("reloaded_answer_does_not_resurrect_the_replaced_item",
             "U-22" not in reload_items, reload_items)
    c4.check("reloaded_answer_matches_what_was_delivered",
             bool(final) and final.strip() == (f.get("message") or "").strip(),
             f"history={len(final)} chars")
    from core.answer_presentation import validate_rendered_against_record
    rec_f = structured_for(args.db, s4, f.get("execution_id"))
    vf = validate_rendered_against_record(final, rec_f)
    c4.check("reloaded_citations_grounded", vf["ok"],
             {"gating": vf["gating"], "violations": vf["violations"][:3]})
    results.append(c4.as_dict())
    print(f"\n[{c4.as_dict()['status']}] {c4.cid}")
    for k, v in c4.checks.items():
        print(f"    {'ok ' if v else 'X  '} {k}")

    npass = sum(1 for r in results if r["status"] == "PASS")
    out = {"base": args.base, "db": args.db, "generated_at":
           time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "cases_passed": npass, "cases_total": len(results),
           "all_pass": npass == len(results), "results": results}
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"\n{npass}/{len(results)} cases pass -> {args.out}")
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
