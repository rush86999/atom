# -*- coding: utf-8 -*-
"""Replay the REAL incident conversation through the turn-decision
contract (2026-09-30, directive step 3 on actual traffic).

For each user turn of session replay-retry2-20260923 (the conversation
this whole effort was diagnosed from):
  - reconstruct the session state the turn saw (the durable assistant
    row BEFORE it carries pending_file_task / pending_file_result /
    resolved_file_identity — the same carriers the live session uses);
  - build the turn decision via core.turn_decision.build_turn_decision;
  - derive what the pipeline ACTUALLY did that turn from the same-turn
    assistant metadata (deterministic read / edit applied / continuation
    forked / teaching offered / narration);
  - ground-truth the expected action set from the diagnosis record.

Outputs a per-turn table + the directive metrics (correct requested
actions, omitted actions, unintended edit proposals) so migration
(steps 4-5) proceeds on measured agreement, not assumption.

Read-only against the dev DB (query_only + mode=ro).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[6] / "backend"
sys.path.insert(0, str(BACKEND))

import logging

logging.disable(logging.CRITICAL)

from core.turn_decision import (  # noqa: E402
    AUTH_GRANTED,
    build_turn_decision,
)

SESSION = "replay-retry2-20260923"
DB = BACKEND / "data" / "atom.db"


def load_turns():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    rows = con.execute(
        """SELECT role, created_at, content, metadata_json FROM chat_messages
           WHERE conversation_id=? ORDER BY created_at, rowid""",
        (SESSION,)).fetchall()
    con.close()
    return rows


def state_from_prior_meta(meta: dict) -> dict:
    """The in-memory session projection as the durable carriers define
    it — the same keys the contract consults."""
    state = {"id": SESSION}
    task = meta.get("pending_file_task")
    if isinstance(task, dict):
        state["_pending_file_task"] = task
    # a superseded objective lives in the stash; prior metadata carries
    # the task that WAS current, which the contract reads identically.
    ident = meta.get("resolved_file_identity")
    if isinstance(ident, dict):
        state["_resolved_file_identity"] = ident
    return state


def actual_outcome(meta: dict, model: str | None) -> str:
    cont = meta.get("continuation")
    if isinstance(cont, str):
        try:
            import ast

            rec = ast.literal_eval(cont)
            return f"bg_edit:{rec.get('outcome')}"
        except Exception:
            pass
    teaching = meta.get("teaching")
    pfr = meta.get("pending_file_result")
    wr = meta.get("workbook_result")
    edit = "n/a"
    if model == "deterministic" and (pfr or wr):
        edit = "read"
    elif model == "deterministic":
        edit = "deterministic"
    else:
        edit = "planning"
    if teaching:
        edit += "+teaching"
    return edit


def main() -> int:
    rows = load_turns()
    prior_meta: dict = {}
    sticky_task: dict = {}
    results = []
    for role, created, content, meta_json in rows:
        if role != "user":
            if meta_json:
                try:
                    m = json.loads(meta_json)
                except Exception:
                    m = {}
                t = m.get("pending_file_task")
                if isinstance(t, dict) and t.get("original_message"):
                    # STICKY TASK STATE: the live session keeps the
                    # stored task across turns until superseded — the
                    # durable projection only stamps rows that touch it,
                    # so replay carries the last-seen task forward.
                    sticky_task = t
                prior_meta = m
            continue
        meta_self = {}
        # find this turn's own assistant row (the next assistant row)
        # lazily: we capture it after the loop iteration; instead we
        # match by timestamp below.
        state_meta = dict(prior_meta)
        if sticky_task and "pending_file_task" not in state_meta:
            state_meta["pending_file_task"] = sticky_task
        results.append({
            "at": str(created)[:16],
            "message": (content or "")[:110].replace("\n", " "),
            "_full": content or "",
            "_state": state_meta,
        })
        # REPLY-LEG SYNTHESIS: a direct research ask with no stored task
        # CREATES one (the live reply leg stores the ask so a later
        # confirmation can resume it) — replay must do the same or every
        # post-ask turn loses its task state.
        from core.turn_decision import build_turn_decision as _btd

        _d = _btd((content or ""), {
            "id": SESSION,
            **({"pending_file_task": sticky_task} if sticky_task else {}),
        }, [], {}, session_id=SESSION)
        if any(a["kind"] == "research" and a.get("reason")
               == "direct_ask" for a in _d["requested_actions"]):
            sticky_task = {
                "original_message": content,
                "mention": ((_d["references"].get("file") or {})
                            .get("name")),
                "status": "pending",
            }

    # execution -> originating user message (for retry instructions)
    prior_user_before: dict = {}
    _last_user = ""
    for role, created, content, meta_json in rows:
        if role == "user":
            _last_user = content or ""
        else:
            try:
                m = json.loads(meta_json or "{}")
                for key in ("_current_execution_id", "execution_id"):
                    eid = m.get(key)
                    if eid:
                        prior_user_before[eid] = _last_user
            except Exception:
                pass

    # TIME-BOUNDED RETRY RECONSTRUCTION: the live detector is TTL-
    # bound relative to NOW; historical retries are invisible to a
    # naive replay. Reconstruct per-turn: was there a failed/conflict
    # continuation record within 30 minutes BEFORE this turn?
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    cont_rows = []
    for at, mj in con.execute(
            """SELECT created_at, metadata_json FROM chat_messages
                WHERE conversation_id=? AND role='assistant'
                  AND metadata_json LIKE '%continuation%'
                ORDER BY created_at""", (SESSION,)).fetchall():
        try:
            import ast as _ast

            rec = _ast.literal_eval(json.loads(mj).get("continuation", ""))
            cont_rows.append((str(at), rec))
        except Exception:
            try:
                rec = json.loads(json.loads(mj).get(
                    "continuation", 'null') or 'null')
                if isinstance(rec, dict):
                    cont_rows.append((str(at), rec))
            except Exception:
                pass
    con.close()
    import datetime as _dt

    def retry_context_at(turn_at: str):
        tt = _dt.datetime.fromisoformat(turn_at)
        for at, rec in reversed(cont_rows):
            if str(rec.get("outcome")) in ("failed", "conflict"):
                ct = _dt.datetime.fromisoformat(at)
                if _dt.timedelta(0) <= tt - ct <= _dt.timedelta(
                        minutes=30):
                    return rec
        return None

    # attach each turn's actual assistant outcome by timestamp
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    for r in results:
        row = con.execute(
            """SELECT metadata_json, metadata_json FROM chat_messages
               WHERE conversation_id=? AND role='assistant'
                 AND created_at >= ? ORDER BY created_at LIMIT 1""",
            (SESSION, r["at"])).fetchone()
        meta = {}
        if row and row[0]:
            try:
                meta = json.loads(row[0])
            except Exception:
                meta = {}
        model = None
        r["actual"] = actual_outcome(meta, model)
        # model rides metadata? fall back: deterministic outcome label
        r["_self_meta"] = meta
    con.close()

    # expected ground truth for the turns the diagnosis established
    EXPECTED = {
        "find all these prices": ["research"],
        "Consolidated Price List 2019.xlsx is correct": ["research"],
        "try excel file search again": ["research"],
        "go ahead": ["research"],
        "try search again": ["research"],
        "find the prices of these 8 machines": ["research"],
        "try the search again and give me a clean response":
            ["research", "presentation"],
        "check Chandrakant's email": ["research"],
        "try my request again": ["research"],
        "roper whitney and tennsmith": ["research"],
        "try it": ["research"],
        "try it again": ["research"],
        "as you found the latest price":
            ["canvas_edit"],
        "try again": ["canvas_edit"],
        "last search didn't reveal": [],
        "repeat the search and learn": ["research", "learning"],
        "update with actual prices": ["canvas_edit"],
        "update the canvas": ["canvas_edit"],
        "apply that priced draft": ["canvas_edit"],
        "apply the priced table": ["canvas_edit"],
        "rebuild the draft": ["canvas_edit"],
        "try again this task": ["canvas_edit", "research"],
    }

    def expected_for(msg: str):
        for prefix, want in EXPECTED.items():
            if msg.lower().startswith(prefix.lower()):
                return want
        return None  # unknown turn — decision recorded, not scored

    metrics = {"turns": 0, "scored": 0, "correct": 0, "omitted": 0,
               "unintended_edit": 0, "mismatches": []}
    table = []
    for r in results:
        state = state_from_prior_meta(r["_state"])
        # canvas context: the incident turns ran against the original
        # email canvas — attach it when the turn is edit/research-shaped
        # after 2026-09-23 (the canvas existed from then on).
        ctx = ({"canvas_id": "0e4defa5-a0f3-4e56-b8a7-976c0a93d4fb"}
               if r["at"] >= "2026-09-23 03:00" else {})
        retry_rec = retry_context_at(r["at"])
        ctx_eval = dict(ctx)
        if retry_rec is not None:
            # instruction = the user message that spawned the failed
            # continuation (nearest user row before its creation)
            inst = prior_user_before.get(
                retry_rec.get("originating_execution_id") or "", "")
            ctx_eval["failed_edit_retry"] = {
                "instruction": inst,
                "canvas_id": retry_rec.get("canvas_id"),
            }
        d = build_turn_decision(
            r["_full"], state, [], ctx_eval, session_id=SESSION)
        kinds = [a["kind"] for a in d["requested_actions"]]
        want = expected_for(r["message"])
        metrics["turns"] += 1
        row = {"at": r["at"], "msg": r["message"][:60],
               "decision": kinds, "actual": r["actual"],
               "expected": want}
        if want is not None:
            metrics["scored"] += 1
            missing = [k for k in want if k not in kinds]
            extra_edit = ("canvas_edit" in kinds
                          and "canvas_edit" not in want)
            if not missing and not extra_edit:
                metrics["correct"] += 1
            else:
                metrics["omitted"] += len(missing)
                metrics["unintended_edit"] += int(extra_edit)
                metrics["mismatches"].append(
                    {"at": r["at"], "msg": r["message"][:60],
                     "decision": kinds, "expected": want,
                     "missing": missing,
                     "unintended_edit": extra_edit})
        table.append(row)

    out = {
        "session": SESSION,
        "metrics": metrics,
        "table": table,
    }
    out_path = Path(__file__).parent / (
        "turn_decision_replay_evaluation.json")
    out_path.write_text(json.dumps(out, indent=2, default=str))
    m = metrics
    print(f"turns={m['turns']} scored={m['scored']} "
          f"correct={m['correct']} omitted={m['omitted']} "
          f"unintended_edit={m['unintended_edit']}")
    for mm in m["mismatches"][:10]:
        print(" MISMATCH", mm["at"], mm["msg"][:44],
              "decision=", mm["decision"], "expected=", mm["expected"],
              "missing=", mm["missing"])
    print("wrote", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
