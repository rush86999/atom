#!/usr/bin/env python3
"""Public-boundary acceptance for the AGENT LEARNING LOOP.

QUESTION THIS RUNNER ANSWERS. "Can the agent clearly learn from the chat in
the right panel, and from canvas changes?" — verified END TO END against an
isolated acceptance world (seatbelt, credential-free, provider shim), where
"learn" means: the rule is DURABLY journaled (AgentRegistry
configuration.learning.log) AND it actually reaches the model as a
"TRAINING LESSONS — PERMANENT INSTRUCTIONS" system block on a LATER turn.
Storage alone was the historical failure (the map: "storage only moved a
confidence score"), so every teaching channel is paired with a read-back.

The LLM boundary is the shim capture: with SHIM_CAPTURE_MESSAGES=1 the shim
records the full message lists it was ASKED, so "the lesson reached the
prompt" is an observation, not an inference from the reply text.

Cases:
  C1  canvas_edit_is_agent_authored   the hire's chat edit lands an
                                      agent-attributed audit row (the draft
                                      a correction can later attach to)
  C2  right_panel_teach               /teach in chat saves a permanent
                                      lesson, is deterministic (never
                                      routed to the reply model), and DEDUPS
  C3  cue_confirm_first               a detected teaching cue SUGGESTS and
                                      writes nothing until the human
                                      confirms via POST /api/agents/{id}/teach
  C4  canvas_correction_learns        a supervisor PUT over the hire's draft
                                      records the RLHF correction AND (the
                                      hire is a STUDENT) journals a permanent
                                      human_correction lesson
  C5  lessons_reach_the_model         the NEXT plain chat turn carries all
                                      taught rules to the LLM in one
                                      TRAINING LESSONS system block
  C6  teach_without_agent_asks        /teach with no agent bound refuses to
                                      guess and offers the pickable list
  C7  lessons_survive_restart         after a full server restart (fresh
                                      process, same durable DB) the lessons
                                      still reach the model

Usage:
    learning_loop_acceptance.py [--rebuild-world] [--name learning_loop_01]
                                [--port 8077] [--shim-port 8097]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

ACC = REPO / "docs" / "architecture" / "orchestration_migration" / "acceptance"
SHIM_SCRIPT = ACC / "fixtures" / "provider_shim" / "learning_loop.json"

#: The rule texts every later assertion is keyed on. Unique tokens so a
#: substring hit cannot come from fixture noise.
TEACH_RULE = ("ALWAYS address the client by their first name in every quote "
              "you draft zzq firstname rule zzq")
CUE_MESSAGE = ("Please draft the quote for Acme. "
               "From now on use USD for all machinery pricing zzq usd rule zzq")
EDIT_ASK = ("In the quote email, change the quote validity "
            "from 15 days to 30 days")
READ_BACK_ASK = "Please draft a one-line quote note for Acme."

INITIAL_BODY = ("Hi Steve,<br><br>Please find our quote attached. "
                "Quote validity: 15 days.<br><br>Regards,")

HIRE_NAME = "Sloan (Learning Loop Hire)"


class Case:
    def __init__(self, cid: str) -> None:
        self.cid = cid
        self.checks: Dict[str, Any] = {}
        self.details: Dict[str, Any] = {}
        self.notes: List[str] = []

    def check(self, name: str, ok: Any, detail: Any = None) -> bool:
        ok = ok is True
        self.checks[name] = ok
        if detail is not None:
            self.details[name] = detail
        return ok

    def note(self, text: str) -> None:
        self.notes.append(text)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(self.checks.values())

    def as_dict(self) -> Dict[str, Any]:
        return {"case": self.cid,
                "status": "PASS" if self.passed else "FAIL",
                "checks": self.checks, "details": self.details,
                "notes": self.notes}


# ---------------------------------------------------------------------------
# durable-state readers (isolated run DB ONLY — never the live dev DB)
# ---------------------------------------------------------------------------

def _connect(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def learning_log(db_path: str, agent_id: str) -> List[Dict[str, Any]]:
    """The agent's durable lesson log, oldest last."""
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT configuration FROM agent_registry WHERE id=?",
            (agent_id,)).fetchone()
    finally:
        con.close()
    if not row:
        return []
    try:
        config = json.loads(row[0] or "{}")
    except Exception:
        return []
    log = ((config or {}).get("learning") or {}).get("log") or []
    return [e for e in log if isinstance(e, dict)]


def log_text(entry: Dict[str, Any]) -> str:
    return str(entry.get("lesson") or entry.get("summary") or "")


def lesson_texts(db_path: str, agent_id: str) -> List[str]:
    return [log_text(e) for e in learning_log(db_path, agent_id)]


def canvas_audit_rows(db_path: str, canvas_id: str) -> List[Dict[str, Any]]:
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT action_type, agent_id, user_id, details_json, created_at "
            "FROM canvas_audit WHERE canvas_id=? ORDER BY created_at",
            (canvas_id,)).fetchall()
    finally:
        con.close()
    out = []
    for action, agent, user, details, created in rows:
        try:
            doc = json.loads(details or "{}")
        except Exception:
            doc = {}
        out.append({"action_type": action, "agent_id": agent,
                    "user_id": user, "details": doc, "created_at": created})
    return out


def correction_feedback_count(db_path: str, agent_id: str) -> int:
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT COUNT(*) FROM agent_feedback "
            "WHERE agent_id=? AND feedback_type='correction'",
            (agent_id,)).fetchone()
    finally:
        con.close()
    return int(row[0]) if row else 0


def context_corrections(db_path: str, canvas_id: str) -> List[Dict[str, Any]]:
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT user_corrections FROM canvas_contexts WHERE canvas_id=?",
            (canvas_id,)).fetchone()
    finally:
        con.close()
    if not row or not row[0]:
        return []
    try:
        doc = json.loads(row[0])
    except Exception:
        return []
    return doc if isinstance(doc, list) else []


# ---------------------------------------------------------------------------
# shim capture reader (the LLM boundary)
# ---------------------------------------------------------------------------

class ShimCapture:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.mark = self._count()

    def _count(self) -> int:
        if not self.path.exists():
            return 0
        return sum(1 for _ in self.path.open())

    def lines_since_mark(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        if not self.path.exists():
            return out
        with self.path.open() as f:
            for i, line in enumerate(f):
                if i < self.mark:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
        return out

    @staticmethod
    def blob(lines: List[Dict[str, Any]]) -> str:
        parts: List[str] = []
        for line in lines:
            for msg in line.get("messages_full") or []:
                parts.append(f"[{msg.get('role')}] {msg.get('content')}")
            parts.append(str(line.get("system_head") or ""))
        return "\n".join(parts)


def wait_for(predicate, timeout_s: float, interval: float = 2.0,
             desc: str = "condition"):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return None


# ---------------------------------------------------------------------------
# scenario
# ---------------------------------------------------------------------------

def seed_hire_and_canvas(run_dir: Path) -> Dict[str, str]:
    """Seed the hire and the quote canvas through the app's OWN model path
    (build_d5_minimal's convention — never raw SQL), into THIS run's
    isolated DB, before the server ever starts. Everything after this runs
    through the public HTTP API."""
    db_path = run_dir / "data" / "atom.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["ATOM_DATA_DIR"] = str(run_dir / "data")

    from core.database import get_db_session
    from core.models import AgentRegistry, AgentStatus, Canvas, CanvasAudit

    # The API-seeded small fixture is schema-ONLY (0 rows by storage policy):
    # create the admin through the app's own bootstrap, then look it up.
    from core.admin_bootstrap import ensure_admin_user
    ensure_admin_user()

    with get_db_session() as db:
        from core.models import User
        admin = db.query(User).filter(User.email == "admin@example.com").first()
        if admin is None:
            raise RuntimeError("run DB has no admin user — cannot seed the hire")
        admin_id = str(admin.id)

        hire = AgentRegistry(
            name=HIRE_NAME,
            description="Quote-drafting hire created by the learning-loop "
                        "acceptance runner.",
            category="Sales",
            module_path="sales.assistants.quotes",
            class_name="SalesAssistant",
            status=AgentStatus.STUDENT.value,
            capabilities=["canvas_edit", "email_draft"],
            user_id=admin_id,
            configuration={"system_prompt":
                           "You draft machinery quotes for clients."},
        )
        db.add(hire)

        import json as _json
        content = _json.dumps({
            "to": "steve@acme.test", "cc": "",
            "subject": "Machinery quote",
            "body": INITIAL_BODY,
        })
        canvas_id = str(uuid.uuid4())
        db.add(Canvas(
            id=canvas_id, tenant_id="default", workspace_id="default",
            created_by=admin_id, name="Acme quote", canvas_type="email",
            content=content, status="active",
        ))
        db.add(CanvasAudit(
            canvas_id=canvas_id, tenant_id="default", action_type="create",
            canvas_type="email", user_id=admin_id,
            details_json={"content": _json.loads(content)},
        ))
        db.commit()
        return {"hire_id": str(hire.id), "canvas_id": canvas_id,
                "admin_id": admin_id, "db_path": str(db_path)}


def run(args: argparse.Namespace) -> int:
    from scripts.orchestration_acceptance import run_isolated as R

    # This runner verifies the code AS IT SITS (working tree, uncommitted
    # wiring included) — declare snapshot mode BEFORE preflight, which reads
    # this flag to skip the pinned-HEAD equality guard (the guard exists for
    # archive mode, which exports PINNED_REV instead).
    R.build_world.snapshot_working_tree = True
    R.build_world.full_dev_db = False

    R.require_storage_ready()

    world = BACKEND / "data" / "acceptance_worlds" / args.name
    if args.rebuild_world or not (world / "MANIFEST.json").exists():
        world.mkdir(parents=True, exist_ok=True)
        R.build_world(world, refreeze_db=False)
    pre = R.preflight(world)
    print(f"[world] {world.name} rev={pre.get('source_revision', '')[:10]}")

    # Fresh run dir, seeded by us so the hire + canvas exist BEFORE launch.
    run_dir = world / "runs" / f"run-{uuid.uuid4().hex[:12]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    R._seed_run_data(world, run_dir)
    seeded = seed_hire_and_canvas(run_dir)
    hire_id, canvas_id = seeded["hire_id"], seeded["canvas_id"]
    db_path = seeded["db_path"]
    print(f"[seed] hire={hire_id[:8]} canvas={canvas_id[:8]}")

    os.environ["SHIM_CAPTURE_MESSAGES"] = "1"
    shim = R.launch_shim(SHIM_SCRIPT, args.shim_port,
                         capture=world / "shim_learning_loop.jsonl")
    print(f"[shim] pid {shim.pid} on :{args.shim_port}")

    capture = ShimCapture(world / "shim_learning_loop.jsonl")
    results: List[Dict[str, Any]] = []
    proc = None
    try:
        proc = R.launch_server(args.port, world, provider_shim=True,
                               reuse_run_dir=run_dir,
                               shim_port=args.shim_port)

        # Mint a token in the SERVER's signing domain (env already points at
        # this run's DB — set by seed_hire_and_canvas).
        from scripts.workbook_read_replay import mint_token
        token, admin_id = mint_token()
        if not token:
            print("could not mint a token against the run DB", file=sys.stderr)
            return 2

        import httpx
        base = f"http://127.0.0.1:{args.port}"
        client = httpx.Client(trust_env=False, timeout=300,
                              headers={"Authorization": f"Bearer {token}"})

        def chat(message: str, *, session: str, agent_id: Optional[str] = None,
                 canvas_ctx: Optional[Dict[str, Any]] = None,
                 no_agent: bool = False) -> Dict[str, Any]:
            body: Dict[str, Any] = {"message": message,
                                    "session_id": session,
                                    "user_id": admin_id}
            ctx: Dict[str, Any] = {"current_page": "/chat",
                                   "conversation_history": []}
            if canvas_ctx:
                ctx.update(canvas_ctx)
            if agent_id and not no_agent:
                body["agent_id"] = agent_id
            body["context"] = ctx
            r = client.post(f"{base}/api/chat/message", json=body)
            try:
                return {"status": r.status_code, **r.json()}
            except Exception:
                return {"status": r.status_code, "raw": r.text[:300]}

        stamp = int(time.time())

        # ------------------------------------------------ C1: agent-authored draft
        c = Case("C1_canvas_edit_is_agent_authored")
        canvas_ctx = {"canvas": {"id": canvas_id, "canvas_type": "email"},
                      "canvas_content": INITIAL_BODY}
        capture.mark = capture._count()
        r1 = chat(EDIT_ASK, session=f"ll-edit-{stamp}", agent_id=hire_id,
                  canvas_ctx=canvas_ctx)
        c.check("edit_turn_succeeded", r1.get("success") is True,
                {"status": r1.get("status"), "err": r1.get("error_code"),
                 "head": str(r1.get("message"))[:140]})
        got = wait_for(
            lambda: any("30 days" in json.dumps(row["details"])
                        for row in canvas_audit_rows(db_path, canvas_id)
                        if row["agent_id"] == hire_id),
            timeout_s=60, desc="agent-authored audit row with 30 days")
        c.check("audit_row_is_agent_attributed_with_the_edit", bool(got),
                [f"{r['action_type']}/agent={str(r['agent_id'])[:8]}"
                 for r in canvas_audit_rows(db_path, canvas_id)][-4:])
        read = client.get(f"{base}/api/canvas/{canvas_id}").json()
        c.check("canvas_read_shows_the_edit", "30 days" in json.dumps(read),
                str(read)[:200])
        shim_lines = capture.lines_since_mark()
        c.check("edit_planner_reached_the_llm_boundary",
                any("CanvasEditPlan" in (line.get("tool_names") or [])
                    for line in shim_lines),
                [{"tool": line.get("tool_names"),
                  "matched": line.get("matched"),
                  "by": line.get("selected_by")} for line in shim_lines][-6:])
        results.append(c.as_dict())
        _print(c)

        # ------------------------------------------------ C2: right-panel /teach
        c = Case("C2_right_panel_teach_saves_and_dedups")
        capture.mark = capture._count()
        r2 = chat(f"/teach {TEACH_RULE}", session=f"ll-teach-{stamp}",
                  agent_id=hire_id)
        teaching = ((r2.get("metadata") or {}).get("teaching") or {})
        c.check("teach_reply_is_deterministic_teaching_intent",
                r2.get("intent") == "teaching", r2.get("intent"))
        c.check("teach_saved", teaching.get("status") == "saved", teaching)
        texts = lesson_texts(db_path, hire_id)
        c.check("lesson_durably_journaled",
                any(TEACH_RULE in t for t in texts), texts)
        n_before = len(texts)
        r2b = chat(f"/teach {TEACH_RULE}", session=f"ll-teach-{stamp}",
                   agent_id=hire_id)
        teaching_b = ((r2b.get("metadata") or {}).get("teaching") or {})
        c.check("repeat_teach_is_duplicate_not_second_entry",
                teaching_b.get("status") == "duplicate"
                and len(lesson_texts(db_path, hire_id)) == n_before,
                {"status": teaching_b.get("status"),
                 "count": len(lesson_texts(db_path, hire_id))})
        c.check("teach_turn_bypassed_the_reply_model",
                all("CanvasEditPlan" not in (line.get("tool_names") or [])
                    for line in capture.lines_since_mark()),
                "no edit-plan leg fired for a teaching turn")
        results.append(c.as_dict())
        _print(c)

        # ------------------------------------------------ C3: cue → confirm-first
        c = Case("C3_cue_suggests_writes_nothing_until_confirmed")
        count_before = len(learning_log(db_path, hire_id))
        r3 = chat(CUE_MESSAGE, session=f"ll-cue-{stamp}", agent_id=hire_id)
        raw = json.dumps(r3)
        c.check("turn_succeeded", r3.get("success") is True,
                {"status": r3.get("status"), "head": str(r3.get("message"))[:120]})
        c.check("suggestion_rode_the_reply",
                "zzq usd rule zzq" in raw.lower()
                or "usd for all machinery pricing" in raw.lower(), raw[:400])
        c.check("detection_wrote_nothing",
                len(learning_log(db_path, hire_id)) == count_before,
                lesson_texts(db_path, hire_id))
        # The TeachingNotice confirm action: POST /api/agents/{id}/teach
        cue_lesson = CUE_MESSAGE.split(". ", 1)[1].strip()
        tr = client.post(f"{base}/api/agents/{hire_id}/teach",
                         json={"lesson": cue_lesson, "canvas_id": canvas_id})
        tjob = tr.json() if tr.status_code == 200 else {}
        tdata = tjob.get("data") if isinstance(tjob.get("data"), dict) else tjob
        c.check("confirm_endpoint_accepts_the_lesson",
                tr.status_code == 200
                and tdata.get("status") in ("saved", "ok"),
                {"status": tr.status_code, "body": str(tjob)[:200]})
        c.check("confirmed_lesson_journaled",
                any("usd rule zzq" in t.lower()
                    for t in lesson_texts(db_path, hire_id)),
                lesson_texts(db_path, hire_id))
        results.append(c.as_dict())
        _print(c)

        # ------------------------------------------------ C4: canvas correction
        c = Case("C4_canvas_correction_becomes_a_permanent_lesson")
        # The draft on the canvas NOW is the agent's edited version (C1):
        # "Quote validity: 30 days." The supervisor corrects THAT.
        agent_draft_body = INITIAL_BODY.replace(
            "Quote validity: 15 days.", "Quote validity: 30 days.")
        corrected_body = agent_draft_body.replace(
            "Quote validity: 30 days.",
            "Quote validity: 30 days from the signed order date; payment "
            "terms net-30 (zzq correction marker zzq).")
        c.check("corrected_content_differs_from_the_draft",
                corrected_body != agent_draft_body
                and "zzq correction marker zzq" in corrected_body,
                corrected_body[:200])
        corrected_content = json.dumps({
            "to": "steve@acme.test", "cc": "",
            "subject": "Machinery quote", "body": corrected_body})
        pr = client.put(f"{base}/api/canvas/{canvas_id}",
                        params={"canvas_type": "email"},
                        json=json.loads(corrected_content))
        c.check("supervisor_put_accepted", pr.status_code == 200,
                {"status": pr.status_code, "body": str(pr.text)[:160]})
        fb = wait_for(lambda: correction_feedback_count(db_path, hire_id) >= 1,
                      timeout_s=30, desc="AgentFeedback correction row")
        c.check("rlhf_correction_row_recorded", bool(fb),
                correction_feedback_count(db_path, hire_id))
        corr = wait_for(lambda: context_corrections(db_path, canvas_id),
                        timeout_s=15, desc="CanvasContext.user_corrections")
        c.check("correction_recorded_on_canvas_context", bool(corr),
                str(corr)[:200])
        # The hire is a STUDENT, so the distilled/fallback human_correction
        # lesson MUST land in the durable journal (background task — poll).
        got = wait_for(
            lambda: any("human_correction" == e.get("observation_type")
                        and "zzq correction marker zzq" in log_text(e)
                        for e in learning_log(db_path, hire_id)),
            timeout_s=60, desc="human_correction journal entry")
        c.check("correction_journaled_as_permanent_lesson", bool(got),
                lesson_texts(db_path, hire_id))
        results.append(c.as_dict())
        _print(c)

        # ------------------------------------------------ C5: read-back at the boundary
        c = Case("C5_lessons_reach_the_model_on_the_next_turn")
        capture.mark = capture._count()
        r5 = chat(READ_BACK_ASK, session=f"ll-readback-{stamp}",
                  agent_id=hire_id)
        c.check("readback_turn_succeeded", r5.get("success") is True,
                {"status": r5.get("status"), "head": str(r5.get("message"))[:120]})
        blob = ShimCapture.blob(capture.lines_since_mark())
        lessons_blob = blob
        c.check("training_lessons_block_reached_the_llm",
                "TRAINING LESSONS — PERMANENT INSTRUCTIONS" in lessons_blob,
                lessons_blob[:400])
        c.check("taught_rule_in_the_block", TEACH_RULE in lessons_blob,
                [t for t in lessons_blob.splitlines() if "zzq" in t][:4])
        c.check("confirmed_cue_rule_in_the_block",
                "usd rule zzq" in lessons_blob.lower(), None)
        c.check("canvas_correction_in_the_block",
                "zzq correction marker zzq" in lessons_blob, None)
        c.check("block_is_a_system_message",
                any((msg.get("role") == "system"
                     and "TRAINING LESSONS" in str(msg.get("content")))
                    for line in capture.lines_since_mark()
                    for msg in (line.get("messages_full") or [])),
                None)
        results.append(c.as_dict())
        _print(c)

        # ------------------------------------------------ C6: /teach with no agent
        c = Case("C6_teach_without_agent_refuses_to_guess")
        r6 = chat("/teach Always double-check totals before sending.",
                  session=f"ll-noagent-{stamp}", no_agent=True)
        teaching = ((r6.get("metadata") or {}).get("teaching") or {})
        c.check("needs_agent_notice", teaching.get("status") == "needs_agent",
                teaching)
        c.check("pickable_agent_list_offered",
                isinstance(teaching.get("agents"), list)
                and len(teaching.get("agents") or []) >= 1,
                teaching.get("agents"))
        c.check("no_lesson_was_written_anywhere",
                all("double-check totals" not in t
                    for t in lesson_texts(db_path, hire_id)),
                lesson_texts(db_path, hire_id))
        results.append(c.as_dict())
        _print(c)

        # ------------------------------------------------ C7: restart durability
        c = Case("C7_lessons_survive_a_server_restart")
        R.stop_server(proc)
        proc = R.launch_server(args.port, world, provider_shim=True,
                               reuse_run_dir=run_dir, shim_port=args.shim_port)
        capture.mark = capture._count()
        r7 = chat(READ_BACK_ASK + " (post-restart check)",
                  session=f"ll-restart-{stamp}", agent_id=hire_id)
        c.check("turn_after_restart_succeeded", r7.get("success") is True,
                {"status": r7.get("status"), "head": str(r7.get("message"))[:120]})
        blob7 = ShimCapture.blob(capture.lines_since_mark())
        c.check("lessons_still_injected_after_restart",
                "TRAINING LESSONS" in blob7 and TEACH_RULE in blob7
                and "zzq correction marker zzq" in blob7,
                blob7[:300])
        results.append(c.as_dict())
        _print(c)

    finally:
        if proc is not None:
            try:
                R.stop_server(proc)
            except Exception:
                pass
        shim.terminate()
        try:
            shim.wait(timeout=5)
        except Exception:
            shim.kill()

    npass = sum(1 for r in results if r["status"] == "PASS")
    out = {"world": str(world), "run_dir": str(run_dir), "db": db_path,
           "hire_id": hire_id, "canvas_id": canvas_id,
           "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "cases_passed": npass, "cases_total": len(results),
           "all_pass": npass == len(results) and bool(results),
           "results": results}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1))
    print(f"\n{npass}/{len(results)} cases pass -> {out_path}")
    return 0 if out["all_pass"] else 1


def _print(c: Case) -> None:
    print(f"\n[{c.as_dict()['status']}] {c.cid}")
    for k, v in c.checks.items():
        print(f"    {'ok ' if v else 'X  '} {k}")
    for n in c.notes:
        print(f"    note: {n}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="learning_loop_01")
    ap.add_argument("--port", type=int, default=8077)
    ap.add_argument("--shim-port", type=int, default=8097)
    ap.add_argument("--rebuild-world", action="store_true")
    ap.add_argument("--out",
                    default=str(ACC / "learning_loop_results.json"))
    args = ap.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
