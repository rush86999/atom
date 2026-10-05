#!/usr/bin/env python3
"""F02 — the wrong-field (subject vs body) change: reproduce or explain.

The reported incident: a run applied a SUBJECT-LINE change while the request
concerned quote validity in the BODY, attributed to a mismatched scripted
`find` string. That attribution is unproven. The historical fixture is
preserved verbatim — the canvas still does NOT contain "Quote validity: 99
days." — so the failure condition is reproduced rather than erased.

Each case is one fresh API-created email canvas, one fresh session, one
authored planner script, and a verdict read from the DURABLE canvas, the
canvas_audit rows and the served response. Nothing is graded on the script.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pa_probe as P  # noqa: E402

REQUEST = ("in the open canvas, change the quote validity from 15 days "
           "to 30 days")

#: Sentences that assert a completed change. Used only to detect a SUCCESS
#: CLAIM in a case that must not make one; the authoritative signal is the
#: response's own `canvas_edit.updated` / `no_apply` block.
SUCCESS_PHRASES = (
    "i've updated", "i have updated", "i updated", "updated the quote",
    "i applied", "applied the edit", "the canvas is now", "is now updated",
    "successfully updated", "done —", "done -",
)


def body_text(new: bool = False, marker: str = "MARKER") -> str:
    line = P.BODY_NEW if new else P.BODY_OLD
    return (f"<div><p>Quote for Steve</p><p><b>{line}</b></p>"
            f"<p>Rows 1-5 are the requested machines.</p>"
            f"<!-- {marker} --></div>")


def wreck_payload(marker: str) -> Dict[str, Any]:
    """A full replacement that changes the SUBJECT and leaves the body alone."""
    return {"to": "steve@example.com", "cc": "",
            "subject": P.SUBJECT_WRECKED, "body": body_text(marker=marker)}


def body_only_payload(marker: str) -> Dict[str, Any]:
    """A full replacement that changes ONLY the body — inside the field the
    discarded ops named."""
    return {"to": "steve@example.com", "cc": "", "subject": P.SUBJECT,
            "body": body_text(new=True, marker=marker)}


def arm(harness: Dict[str, Any], script: Dict[str, Any], tag: str) -> None:
    """Re-arm the shim on the SAME port with a new script.

    The provider row already points at this port, so the running server reaches
    the new script without a restart: provider discovery happens once, at
    server startup, and does not need repeating.
    """
    proc: subprocess.Popen = harness.get("shim_proc")
    if proc is not None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass
        try:
            proc.wait(timeout=15)
        except Exception:
            pass
    for _ in range(80):  # the port must be free before the replacement binds
        s = socket.socket()
        try:
            s.connect(("127.0.0.1", harness["shim_port"]))
            s.close()
            time.sleep(0.25)
        except Exception:
            s.close()
            break
    path = Path(harness["out"]) / f"script_{tag}.json"
    path.write_text(json.dumps(script, indent=2))
    harness["shim_proc"] = P.RIG.start_shim(
        path, harness["shim_port"],
        capture=Path(harness["out"]) / f"shim_{tag}.jsonl")
    harness["script"] = str(path)
    time.sleep(1.0)


def negative_checks(res: Dict[str, Any], *, expect_subject_change: bool) -> Dict[str, bool]:
    st = res["durable_after"]
    reply = str(res["served_response"].get("message") or "").lower()
    ce = res["canvas_edit_meta"]
    terminal = str(res.get("continuation_terminal_text") or "").lower()
    return {
        "injection_consumed": res["shim_requests_served"] > 0,
        "zero_mutation_audits_on_canvas": len(
            res["mutation_audit_rows_after_baseline"]) == 0,
        "subject_is_original": st["subject_is_original"],
        "body_target_unchanged": st["body_has_old"] and not st["body_has_new"],
        "response_says_no_change": bool(
            (ce.get("no_apply") is True) or (ce.get("updated") is False)),
        "no_success_phrase_in_reply": not any(
            p in reply for p in SUCCESS_PHRASES),
        "reply_is_nonempty": len(reply) > 10,
        # The interactive reply may say "still running in the background", so
        # the no-apply is only judged once the background leg is terminal — and
        # it must not have turned into a change either.
        "background_leg_terminal": bool(
            res.get("continuation_terminal", {}).get("terminal", True)),
        "no_success_phrase_in_terminal_message": not any(
            p in terminal for p in SUCCESS_PHRASES),
    }


def st_flag(res: Dict[str, Any], key: str, want: bool) -> bool:
    return bool(res["durable_after"].get(key)) is want


def positive_checks(res: Dict[str, Any], *, expect_body: bool) -> Dict[str, bool]:
    st = res["durable_after"]
    ce = res["canvas_edit_meta"]
    return {
        "injection_consumed": res["shim_requests_served"] > 0,
        "exactly_one_mutation_audit": len(
            res["mutation_audit_rows_after_baseline"]) == 1,
        "body_target_present": st["body_has_new"],
        "old_text_gone_from_body": not st["body_has_old"],
        "subject_unchanged": st["subject_is_original"],
        "response_confirms_write": ce.get("updated") is True,
    }


def await_continuations(db: str, session_id: str, budget: float = 90.0) -> Dict[str, Any]:
    """Wait for every continuation of this session to leave 'running'.

    The interactive reply can legitimately say "still running in the
    background", so the user-visible outcome of a negative case is not settled
    until the continuation's TERMINAL message exists. Judging the no-apply on
    the interactive reply alone would let a background leg write something.
    """
    deadline = time.time() + budget
    rows: List[Dict[str, Any]] = []
    while True:
        rows = P.continuations(db, session_id or "")
        if not rows or all(r["status"] != "running" for r in rows):
            return {"terminal": True, "rows": rows}
        if time.time() > deadline:
            return {"terminal": False, "rows": rows}
        time.sleep(2.0)


def run_case(name: str, script: Dict[str, Any], marker: str, request: str,
             harness: Dict[str, Any], world: str, mode: str,
             settle: float = 25.0) -> Dict[str, Any]:
    base = f"http://127.0.0.1:{harness['port']}"
    arm(harness, script, name)
    auth = P.login(base, harness["port"])
    canvas = P.seed(base, harness["port"], auth["token"], auth["user_id"], marker)
    base_state = P.baseline(harness["db"], canvas["canvas_id"])
    off = P.RIG.log_offset(world)

    turn = P.post_turn(base, harness["port"], auth["token"], auth["user_id"],
                       f"{request} (marker {marker})",
                       f"f02-{name}-{int(time.time())}", canvas)

    deadline = time.time() + settle
    state = P.canvas_state(harness["db"], canvas["canvas_id"])
    while time.time() < deadline and not (state["body_has_new"]
                                           or state["subject_changed"]):
        time.sleep(2.0)
        state = P.canvas_state(harness["db"], canvas["canvas_id"])
    time.sleep(2.0)
    state = P.canvas_state(harness["db"], canvas["canvas_id"])
    new_rows = P.mutation_audits(harness["db"], canvas["canvas_id"],
                                 base_state["after"])
    all_rows = P.all_canvas_audits(harness["db"], canvas["canvas_id"],
                                   base_state["after"])
    cont = await_continuations(harness["db"], turn.get("session_id") or "")
    time.sleep(2.0)
    state = P.canvas_state(harness["db"], canvas["canvas_id"])
    new_rows = P.mutation_audits(harness["db"], canvas["canvas_id"],
                                 base_state["after"])
    all_rows = P.all_canvas_audits(harness["db"], canvas["canvas_id"],
                                   base_state["after"])
    terminal_text = " | ".join(
        str((r.get("continuation") or {}).get("summary") or r.get("result_summary") or "")
        for r in cont["rows"])
    history = P.chat_messages(harness["db"], turn.get("session_id") or "")
    shim = P.shim_report(harness["shim_port"])
    served = [e for e in (shim.get("log") or [])
              if e.get("served") not in (None, "", "(models list)")]

    res: Dict[str, Any] = {
        "case": name,
        "mode": mode,
        "request": request,
        "marker": marker,
        "canvas_id": canvas["canvas_id"],
        "canvas_content_at_seed": canvas["content"],
        "session_id": turn.get("session_id"),
        "execution_id": turn.get("execution_id"),
        "baseline": base_state,
        "served_response": turn,
        "canvas_edit_meta": turn.get("canvas_edit"),
        "durable_after": state,
        "mutation_audit_rows_after_baseline": new_rows,
        "all_audit_rows_after_baseline": all_rows,
        "continuation_terminal": cont,
        "continuation_terminal_text": terminal_text[:900],
        "session_history": history[-6:],
        "shim_requests_served": len(served),
        "shim_served_heads": [str(e.get("served"))[:200] for e in served][:8],
        "boundary_lines": P.boundary_lines(world, off),
        "fallback_markers": P.RIG.fallback_markers(world, off),
    }
    if mode == "negative":
        res["checks"] = negative_checks(res, expect_subject_change=False)
    elif mode == "subject_positive":
        res["checks"] = {
            "injection_consumed": res["shim_requests_served"] > 0,
            "exactly_one_mutation_audit": len(
                res["mutation_audit_rows_after_baseline"]) == 1,
            "subject_applied": st_flag(res, "subject_changed", True),
            "body_target_unchanged": (res["durable_after"]["body_has_old"]
                                      and not res["durable_after"]["body_has_new"]),
            "response_confirms_write": res["canvas_edit_meta"].get(
                "updated") is True,
        }
    else:
        res["checks"] = positive_checks(res, expect_body=True)
    res["pass"] = all(res["checks"].values())
    return res


def build_matrix(marker: str) -> Dict[str, Tuple[Dict[str, Any], str, str]]:
    PATCH_BODY = {"field": "body", "find": P.BODY_OLD, "replace": P.BODY_NEW}

    # ---- N1: missing target, nothing else -----------------------------
    n1 = P.build_script([
        {"match": P.REASK_MARK, "response": {"response": {"tool_call": {
            "name": "CanvasEditPlan",
            "arguments": P.patch_plan(find=P.ABSENT_FIND,
                                      replace=P.BODY_NEW)}}}},
        {"match": "CanvasEditPlan", "response": {"response": {"tool_call": {
            "name": "CanvasEditPlan",
            "arguments": P.patch_plan(find=P.ABSENT_FIND,
                                      replace=P.BODY_NEW)}}}},
    ])

    # ---- N2: THE REPORTED SHAPE ---------------------------------------
    # Same missing target; the recovery re-ask is answered with a full
    # replacement payload that changes the SUBJECT and leaves the body alone.
    # The recovery re-ask is the only scripted path in the product that hands
    # a model authorship of fields the user never named.
    n2 = P.build_script([
        {"match": P.REASK_MARK, "response": {"response": {"tool_call": {
            "name": "CanvasEditPlan",
            "arguments": P.replace_plan(
                updated=wreck_payload(marker),
                reply="Updated the canvas and refreshed the subject line.")}}}},
        {"match": "CanvasEditPlan", "response": {"response": {"tool_call": {
            "name": "CanvasEditPlan",
            "arguments": P.patch_plan(find=P.ABSENT_FIND,
                                      replace=P.BODY_NEW)}}}},
    ])

    # ---- N3: the plan itself targets the subject ------------------------
    # Control: a plan that NAMES `subject` is authoritative, so applying it is
    # correct. Establishes that F02 is about an UNREQUESTED field, not about
    # the subject being immutable.
    n3 = P.build_script([
        {"match": "CanvasEditPlan", "response": {"response": {"tool_call": {
            "name": "CanvasEditPlan",
            "arguments": P.patch_plan(
                find=P.SUBJECT, replace=P.SUBJECT_WRECKED, field="subject",
                reply="Updated the subject line.")}}}},
    ])

    # ---- N4: the contract-repair leg, answered out of scope -------------
    # A self-contradictory plan (wants_edit=false carrying ops) triggers the
    # bounded consistency repair; the repair is answered with a replacement
    # payload that changes the subject.
    n4 = P.build_script([
        {"match": P.CONTRACT_REPAIR_MARK, "response": {"response": {"tool_call": {
            "name": "CanvasEditPlan",
            "arguments": P.replace_plan(
                updated=wreck_payload(marker),
                reply="Updated the canvas and refreshed the subject line.")}}}},
        {"match": "CanvasEditPlan", "response": {"response": {"tool_call": {
            "name": "CanvasEditPlan",
            "arguments": {
                "wants_edit": False, "edit_mode": "patch", "ops": [PATCH_BODY],
                "restore_audit_id": None, "updated_content_json": None,
                "title": None, "reply": "Nothing to do."}}}}},
    ])

    # ---- N5: in-scope recovery (the control that must still work) -------
    n5 = P.build_script([
        {"match": P.REASK_MARK, "response": {"response": {"tool_call": {
            "name": "CanvasEditPlan",
            "arguments": P.replace_plan(
                updated=body_only_payload(marker),
                reply="Updated the quote validity to 30 days.")}}}},
        {"match": "CanvasEditPlan", "response": {"response": {"tool_call": {
            "name": "CanvasEditPlan",
            "arguments": P.patch_plan(find=P.ABSENT_FIND,
                                      replace=P.BODY_NEW)}}}},
    ])

    return {
        "n1_missing_target": (n1, REQUEST, "negative"),
        "n2_recovery_rewrites_subject": (n2, REQUEST, "negative"),
        "n3_plan_names_subject": (
            n3, "in the open canvas, update the subject line", "subject_positive"),
        "n4_contract_repair_rewrites_subject": (n4, REQUEST, "negative"),
        "n5_recovery_in_scope": (n5, REQUEST, "body_positive"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", required=True)
    ap.add_argument("--port", type=int, default=8086)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cases", default="all")
    ap.add_argument("--keep-shim", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    marker = f"PAF02-{int(time.time())}"
    harness = P.bootstrap(args.world, args.port, P.build_script(
        [{"match": "CanvasEditPlan", "response": {"response": {"tool_call": {}}}}]),
        out)
    harness["out"] = str(out)
    report = P.sanity(harness, args.world)
    report["case_matrix"] = []

    matrix = build_matrix(marker)
    wanted = (list(matrix) if args.cases == "all"
              else [c for c in args.cases.split(",") if c in matrix])
    for name in wanted:
        script, req, mode = matrix[name]
        print(f"\n=== F02 case {name} ({mode}) ===", flush=True)
        result = run_case(name, script, marker, req, harness, args.world, mode)
        report["case_matrix"].append(result)
        for k, v in result["checks"].items():
            print(f"    {'OK ' if v else 'NO '} {k}")
        st = result["durable_after"]
        print(f"    -> {'PASS' if result['pass'] else 'FAIL'}"
              f"  subject_changed={st['subject_changed']}"
              f"  body_new={st['body_has_new']}"
              f"  mutations={len(result['mutation_audit_rows_after_baseline'])}")
        (out / f"f02_{name}.json").write_text(
            json.dumps(result, indent=2, default=str))
        (out / "f02_report.json").write_text(
            json.dumps(report, indent=2, default=str))

    report["accounting"] = {c["case"]: ("PASS" if c["pass"] else "FAIL")
                            for c in report["case_matrix"]}
    (out / "f02_report.json").write_text(json.dumps(report, indent=2, default=str))
    print("\n" + json.dumps(report["accounting"], indent=2))
    if not args.keep_shim and harness.get("shim_proc"):
        try:
            os.killpg(os.getpgid(harness["shim_proc"].pid), signal.SIGKILL)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
