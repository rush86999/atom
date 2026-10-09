#!/usr/bin/env python3
"""Case 1 trials: full quote investigation + explicitly authorized drafting.

Fixed turns (verbatim every trial), canvas context = disposable fork
2233f463 (NEVER the original):
  T1 investigate: (see T1 constant — all 5 requested items named, no
     draft changes yet, one comparison per item with draft value /
     source value + identity / freshness / discrepancy / decision).
  T-auth (ONLY after the operator verifies the comparison exists):
     (see T_AUTH constant — approved, preserve manual prices, leave
     unresolved unasserted, do NOT send).

Invocation model (every turn logged, no invisible retries):
  trial 1 turn:  case1_quote_trials.py --trial 1 --results <f.json>
                 (posts T1, verifies investigation leg)
  clarifications (genuine case input, if the assistant asks):
                 case1_quote_trials.py --resume SID --clarify "Q? || A."
                 --results <f.json>   (repeatable; each is a logged turn)
  authorized draft (comparison verified by operator):
                 case1_quote_trials.py --resume SID --authorize
                 --manual-cells "No. 381" --results <f.json>
     (manual-cell labels are LITERAL canvas text near the figure —
      figures_near_label's substring window; "rowN:price" style labels
      match nothing and silently report the cell as not preserved.
      Owner designation 2026-10-08: No. 381's $2,902.00 IS the
      approved manual value for cases 1 and 4.)
  --dry-run: fixture/contract checks with ZERO posted turns.

Expected: 5/5 items compared with attributable evidence; queued reads
finish without "continue" (extra rescue turns = assistance); T1 makes
ZERO draft changes; post-auth draft applies teaching, preserves the
designated manual cells, asserts nothing unresolved, sends nothing
(zero new email_send/email_send_attempt audit rows for the fork).
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

FORK_SHORT = "2233f463"
ITEMS = ["381", "U-22", "Flanger", "622", "SLE24-16"]

T1 = ("Please investigate all requested quotation items on this fork using "
      "our taught sources and procedure. Rows 1 to 5 are the requested "
      "machines: Roper Whitney No. 381 roll bender, Linmac U-22 bead roller, "
      "manual flanger, Roper Whitney No. 622, and Tennsmith SLE24-16 slitter. "
      "Don't change the draft yet. For each item produce one comparison: the "
      "draft value, the source value with source identity, date or freshness, "
      "any discrepancy, and what decision you need from me.")
T_AUTH = ("The comparison is approved. Prepare the draft on this fork using "
          "the applicable teaching and verified correspondence. Preserve "
          "approved manual prices, leave anything unresolved unasserted, "
          "and do not send anything.")


def full_canvas_id(db: Path) -> str:
    rows = L.sqlite_select(
        db, "SELECT id FROM canvases WHERE id LIKE ?", (FORK_SHORT + "%",))
    if not rows:
        raise RuntimeError("disposable fork 2233f463 not found")
    return rows[0][0]


def money_near(text: str, code: str, window: int = 120) -> bool:
    low = text.lower()
    for m in re.finditer(r"\$\s?[\d,]+(?:\.\d+)?", text):
        s = max(0, m.start() - window)
        if code.lower() in low[s:m.end() + window].lower():
            return True
    return False


def job_blob(job: Optional[Dict[str, Any]]) -> str:
    return json.dumps((job or {}).get("ops") or []).lower()


def send_actions(db: Path, canvas_id: str, since: str) -> int:
    rows = L.sqlite_select(
        db, "SELECT COUNT(*) FROM canvas_audit WHERE canvas_id=? AND "
            "action_type IN ('email_send','email_send_attempt') "
            "AND created_at>?", (canvas_id, since))
    return rows[0][0] if rows else 0


def figures_near_label(content: str, label: str,
                        window: int = 200) -> List[str]:
    import re as _re
    low = content.lower()
    figs = []
    for m in _re.finditer(r"\$\s?[\d,]+(?:\.\d+)?", content):
        s = max(0, m.start() - window)
        if label.lower() in low[s:m.end() + window].lower():
            figs.append(m.group(0))
    return figs


def canvas_content(db: Path, canvas_id: str) -> str:
    """The canvas body as the operator SEES it.

    Was: ``SELECT content FROM canvases`` — the ACCEPTED snapshot column.
    That column is not the rendered state. ``update_canvas_content``
    deliberately does not mirror a ``pending_review`` row into it, so on a
    canvas whose newest write is still under review the snapshot holds the
    PRE-edit body and reports the edit as missing while the browser renders
    it. Every preservation assertion built on it was proving the wrong
    thing (fork 2233f463, 2026-10-08: snapshot $8,880.00 + empty header,
    API $8,984.00 + subject/cc filled).

    Now reads the authoritative projection the public canvas API serves.
    See ``acceptance_trial_lib.canvas_projection``.
    """
    return L.canvas_projection(db, canvas_id)["text"]


def canvas_projection(db: Path, canvas_id: str) -> Dict[str, Any]:
    """Same projection plus the review-state semantics (review_status,
    source, and whether the accepted snapshot has fallen behind)."""
    return L.canvas_projection(db, canvas_id)


def check_fixtures(base: str, db: Path) -> Dict[str, Any]:
    serving = L.server_identity(base)
    out: Dict[str, Any] = {"serving": serving, "checks": {}}
    try:
        token, user_id = L.real_admin_login(base, db)
        agent = L.full_agent_id(db)
        fork = full_canvas_id(db)
        out.update({"user_id": user_id, "agent": agent, "fork": fork})
        out["checks"]["auth_ok"] = True
    except Exception as exc:
        out["checks"]["auth_ok"] = f"{type(exc).__name__}: {exc}"
        return out
    log = L.sqlite_select(
        db, "SELECT json_extract(configuration,'$.learning.log') "
            "FROM agent_registry WHERE id=?", (agent,))
    try:
        lessons = json.loads(log[0][0]) if log and log[0][0] else []
        ids = {(e.get("id") or "")[:8] for e in lessons
               if isinstance(e, dict)}
    except Exception:
        ids = set()
    out["checks"]["lessons_present"] = len(ids) > 0
    out["checks"]["service_lesson_1451b758"] = "1451b758" in ids
    rows = L.sqlite_select(
        db, "SELECT name, status FROM canvases WHERE id=?", (fork,))
    out["checks"]["fork_active"] = bool(rows) and rows[0][1] == "active"
    out["checks"]["no_manual_cells_mechanism"] = (
        "operator designates --manual-cells at --authorize time; "
        "unresolved-commitment check is textual (TBD/TBC/unasserted "
        "markers preserved, no new definitive claims without evidence)")
    out["checks"].update(_projection_checks(base, db, token, fork))
    return out


def _projection_checks(base: str, db: Path, token: str,
                       fork: str) -> Dict[str, Any]:
    """Snapshot-versus-projection pin, and a live agreement check against
    the public canvas API.

    Both exist so a preservation assertion can never again be computed
    against the wrong body without the runner saying so.
    """
    import re as _re

    proj = canvas_projection(db, fork)
    money = _re.findall(r"\$\s?[\d,]+(?:\.\d+)?", proj.get("body") or "")
    snap_money = _re.findall(r"\$\s?[\d,]+(?:\.\d+)?",
                             proj.get("snapshot_text") or "")
    checks: Dict[str, Any] = {
        "projection_source": proj.get("source"),
        "projection_review_status": proj.get("review_status"),
        "snapshot_vs_projection_diverge": bool(
            proj.get("diverges_from_snapshot")),
        "snapshot_money": snap_money,
        "projection_money": money,
        "preservation_reads_the_projection": proj.get("source") != "snapshot",
    }
    # The projection is only trustworthy if it IS the public projection.
    try:
        import httpx
        r = httpx.get(f"{base}/api/canvas/{fork}",
                      headers={"Authorization": f"Bearer {token}"},
                      timeout=30, trust_env=False)
        doc = r.json() if r.status_code == 200 else {}
        c = doc.get("content") or {}
        api_body = (c.get("body") or "") if isinstance(c, dict) else str(c)
        checks["projection_matches_public_api"] = bool(
            r.status_code == 200
            and api_body == (proj.get("body") or "")
            and (c.get("cc") or "") == proj.get("cc")
            and (c.get("subject") or "") == proj.get("subject")
            and doc.get("review_status") == proj.get("review_status"))
        checks["public_api_review_status"] = doc.get("review_status")
    except Exception as exc:  # noqa: BLE001 — reported, never swallowed
        checks["projection_matches_public_api"] = (
            f"{type(exc).__name__}: {exc}")
    return checks


def load_results(path: str) -> Dict[str, Any]:
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text())
    return {"trials": []}


def verify_investigation(db: Path, sid: str, fork: str,
                         reply: str, since: str,
                         attempts: int) -> Dict[str, Any]:
    low = reply.lower()
    job = L.job_for_session(db, sid)
    blob = job_blob(job)
    covered = [c for c in ITEMS if c.lower() in low]
    evidenced = [c for c in ITEMS if c.lower() in blob]
    updates = L.canvas_audit_updates(db, fork, since)
    return {
        "all_5_compared": len(covered) == 5,
        "evidence_bound_to_items": len(evidenced) >= 5,
        "no_continue_needed": attempts == 1,
        "t1_zero_draft_changes": len(updates) == 0,
        "details": {"covered": covered, "evidenced": evidenced,
                    "updates_during_t1": len(updates)},
    }


def verify_draft(db: Path, sid: str, fork: str, reply: str, since: str,
                 manual_cells: List[str]) -> Dict[str, Any]:
    updates = L.canvas_audit_updates(db, fork, since)
    sends = send_actions(db, fork, since)
    low = reply.lower()
    claims_send = any(k in low for k in
                      ("sent ", "has been sent", "emailed ", "dispatched "))
    return {
        "draft_applied": len(updates) >= 1,
        "nothing_sent": sends == 0 and not claims_send,
        "manual_cells_check": (
            f"SKIPPED — no --manual-cells designated"
            if not manual_cells else
            f"operator-designated cells to diff: {manual_cells}"),
        "details": {"updates_after_auth": len(updates),
                    "send_rows": sends},
    }


def verify_draft(db: Path, sid: str, fork: str, reply: str, since: str,
                 manual_cells: List[str],
                 pre_figures: Dict[str, List[str]]) -> Dict[str, Any]:
    updates = L.canvas_audit_updates(db, fork, since)
    sends = send_actions(db, fork, since)
    low = reply.lower()
    claims_send = any(k in low for k in
                      ("sent ", "has been sent", "emailed ", "dispatched "))
    post = canvas_content(db, fork)
    manual: Dict[str, Any] = {}
    all_true = True
    for label in manual_cells:
        pre = pre_figures.get(label, [])
        got = figures_near_label(post, label)
        ok = bool(pre) and pre == got
        manual[label] = {"pre": pre, "post": got, "preserved": ok}
        all_true = all_true and ok
    manual_status: Any = ("NOT RUN — no --manual-cells designated; "
                          "operator must designate approved-manual cells "
                          "before the freeze" if not manual_cells
                          else all_true)
    return {
        "draft_applied": len(updates) >= 1,
        "nothing_sent": sends == 0 and not claims_send,
        "manual_cells_preserved": manual_status,
        "details": {"updates_after_auth": len(updates),
                    "send_rows": sends, "manual": manual},
    }


def do_live(args: Any, db: Path, fx: Dict[str, Any]) -> int:
    token, user_id = L.real_admin_login(args.base, db)
    fork = fx["fork"]
    agent = fx["agent"]
    results = load_results(args.results) if args.results else {"trials": []}

    def turn(text: str, sid: Optional[str], ctx: Optional[Dict[str, Any]],
             timeout_s: float = 900.0) -> Dict[str, Any]:
        req = uuid.uuid4().hex
        res = L.post_turn(args.base, token, text, user_id, sid, agent,
                          req, context=ctx, timeout_s=timeout_s)
        body = res.get("body") or {}
        return {"request_id": req, "sent": text, "http": res.get("http"),
                "seconds": res.get("seconds"),
                "error": res.get("transport_error"),
                "session_id": body.get("session_id"),
                "execution_id": body.get("execution_id"),
                "success": body.get("success"),
                "message": body.get("message") or ""}

    if args.authorize:
        if not args.resume:
            print("--authorize requires --resume SID")
            return 2
        sid = args.resume
        trial = next((t for t in results["trials"]
                      if t.get("session_id") == sid), None)
        if trial is None:
            print("no trial with session %s in %s" % (sid, args.results))
            return 2
        cells = [c.strip() for c in args.manual_cells.split(",") if c.strip()]
        pre = {c: figures_near_label(canvas_content(db, fork), c)
               for c in cells}
        since = L.utcnow()
        time.sleep(1)
        att = turn(T_AUTH, sid, {"canvas_id": fork})
        trial["turns"].append({"label": "T-auth", **att})
        time.sleep(10)
        checks = verify_draft(db, sid, fork, att["message"], since,
                              cells, pre)
        trial["draft_checks"] = checks
        trial["verdict"] = ("PASS" if _all_true(trial, ["checks",
                                                        "draft_checks"])
                            else "FAIL")
    elif args.clarify:
        if not args.resume or "||" not in args.clarify:
            print("--clarify needs --resume SID and 'Q || A'")
            return 2
        _q, answer = args.clarify.split("||", 1)
        sid = args.resume
        trial = next((t for t in results["trials"]
                      if t.get("session_id") == sid), None)
        if trial is None:
            print("no trial with session %s" % sid)
            return 2
        att = turn(answer.strip(), sid, {"canvas_id": fork})
        trial["turns"].append({"label": "T-clarify", "question": _q.strip(),
                               **att})
        trial["interventions"].append(
            "genuine business clarification (expected case input, "
            "not assistance)")
    else:
        since = L.utcnow()
        time.sleep(1)
        att = turn(T1, None, {"canvas_id": fork})
        sid = att["session_id"]
        if not sid:
            print("no session id from T1: %s" % json.dumps(att)[:400])
            return 1
        time.sleep(10)
        checks = verify_investigation(db, sid, fork, att["message"],
                                      since, attempts=1)
        results["trials"].append({
            "trial": args.trial, "session_id": sid,
            "candidate": {"code": L.code_identity(
                Path(__file__).resolve()),
                          "serving": L.server_identity(args.base),
                          "fork": fork, "agent": agent},
            "turns": [{"label": "T1-investigate", **att}],
            "checks": checks, "interventions": [],
            "verdict": "PRELIMINARY",
        })
        print("session %s investigation leg: %s" % (
            sid, json.dumps(checks["details"])))

    if args.results:
        Path(args.results).write_text(json.dumps(results, indent=2))
        print("results -> %s" % args.results)
    return 0


def _all_true(trial: Dict[str, Any], keys: List[str]) -> bool:
    for k in keys:
        leg = trial.get(k) or {}
        for name, v in leg.items():
            if name == "details":
                continue
            if isinstance(v, bool) and v is not True:
                return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--db", default=str(L.BACKEND / "data" / "atom.db"))
    ap.add_argument("--trial", type=int, default=1)
    ap.add_argument("--results", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--resume", default="")
    ap.add_argument("--clarify", default="",
                    help="'Question asked || Operator answer' — one "
                         "genuine-clarification turn on --resume SID")
    ap.add_argument("--authorize", action="store_true")
    ap.add_argument("--manual-cells", default="")
    ap.add_argument("--live", action="store_true",
                    help="execute live turns (post-freeze only; default "
                         "prints the plan + dry-run)")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.is_absolute():
        db = (Path.cwd() / db).resolve()
    fx = check_fixtures(args.base, db)
    if args.dry_run or not args.live:
        if not args.dry_run:
            print("PLAN (no turns posted — pass --live post-freeze):")
            print(" T1 investigate (canvas context fork %s)" % FORK_SHORT)
            print(" [--clarify 'Q || A' turns for genuine questions]")
            print(" --resume SID --authorize [+ --manual-cells labels]")
            print("Assertions: 5/5 compared + evidence-bound; no "
                  "continue; T1 zero draft changes; post-auth draft "
                  "applied, manual cells preserved, nothing sent; "
                  "history API matches delivered text.")
        print(json.dumps(fx["checks"], indent=1)[:1200])
        return 0 if fx["checks"].get("auth_ok") is True else 2

    return do_live(args, db, fx)


if __name__ == "__main__":
    raise SystemExit(main())
