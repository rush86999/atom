# -*- coding: utf-8 -*-
"""Multi-scenario turn-decision evaluation on REAL ingested data
(2026-09-30): long competing-intent conversations and ambiguity cases,
scored against hand-labeled ground truth.

Scenarios (each a sequence of turns replayed with state carried between
them — mirrors live session semantics: stored task persists until
superseded; bindings/identity ride the task):

S1  competing-intent long conversation (the recorded incident shape,
    fresh ordering): research ask → confirmation → cross-source →
    row-assertion read → edit → conflict-retry → compound
    research+learning → formatting → ambiguous reference.
S2  source-vs-file competition: email-only ask, workbook-only ask,
    both-sources ask, ambiguous "check it" after both.
S3  ambiguity battery: vague pronoun targets, two-file ambiguity,
    unknown generic references, question-form requests, ellipsis
    approvals, teaching-vs-edit verb collisions.
S4  restart-shaped: state reconstructed ONLY from durable carriers
    (task + identity), no in-memory extras.

Metrics per the directive: correct requested actions, omitted actions,
unintended edit proposals, plus per-scenario agreement.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[6] / "backend"
sys.path.insert(0, str(BACKEND))

import logging

logging.disable(logging.CRITICAL)

from core.turn_decision import build_turn_decision  # noqa: E402

ASK8 = ("find the prices of these 8 machines in Consolidated Price List "
        "2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, "
        "TK 1624, TK Multi Wheel Gang Slitter and GSL48-16")
TASK8 = {
    "original_message": ASK8,
    "mention": "consolidated price list 2019.xlsx",
    "status": "delivered",
    "resolved_file": {
        "file_name": "Consolidated Price List 2019.xlsx",
        "file_id": "wd-77", "content_hash": "ff2597d2",
        "identity_verified": True},
    "confirmed_mention": "consolidated price list 2019.xlsx",
}
CANVAS = {"canvas_id": "0e4defa5-a0f3-4e56-b8a7-976c0a93d4fb"}


def fresh():
    return {"id": "s-eval", "_pending_file_task": json.loads(
        json.dumps(TASK8))}


def superseded():
    s = fresh()
    s["_superseded_file_task_context"] = s.pop("_pending_file_task")
    return s


S1 = [  # turn, state, ctx, expected kinds
    (ASK8, fresh(), {}, ["research"]),
    ("That filename is correct", fresh(), {}, ["research"]),
    ("check Chandrakant's email and or description in workbook to find "
     "correct sheet and row from workbook for confirmation",
     superseded(), CANVAS, ["research"]),
    ("roper whitney and tennsmith are 2 brands under 1 ownership and "
     "they sometimes mix the names. no. 381 is on Tennsmith sheet of "
     "the workbook under row 338. here's the data: 381 167072381 Roll "
     "Bending Machine, $3,254.00 . find this in the workbook",
     superseded(), CANVAS, ["research"]),
    ("as you found the latest price for the roper 381 roll bender, "
     "update the email price accordingly", superseded(), CANVAS,
     ["canvas_edit"]),
    ("repeat the search and learn to include tennsmith sheet for "
     "roper whitney searches", superseded(), CANVAS,
     ["research", "learning"]),
    ("make it cleaner", superseded(), CANVAS, ["presentation"]),
    ("find this in the tracker", superseded(), CANVAS, []),
]

S2 = [
    ("search Chandrakant's september emails for the quote",
     fresh(), {}, ["research"]),
    ("find the prices in the workbook", fresh(), {}, ["research"]),
    ("check his email and the workbook descriptions to confirm the row",
     fresh(), CANVAS, ["research"]),
    ("check it", fresh(), CANVAS, []),  # ambiguous pronoun: no invented target
    ("what does the supplier thread say about lead times",
     fresh(), CANVAS, ["research"]),
    ("compare the workbook values against the email quotes",
     fresh(), CANVAS, ["research"]),
]

S3 = [
    # two-file ambiguity
    ("find the machine prices in Copy of Consolidated Price List 2019 "
     "- Linmac Update.xlsx and tell me if they differ",
     fresh(), CANVAS, ["research"]),
    # unknown generic reference, no identity
    ("find this in the tracker", {"id": "s3"}, CANVAS, []),
    # question-form request (no authorization to act unilaterally,
    # but research is a read — question form still proposes research
    # when it names the file)
    ("what are the prices for No. 381 in the workbook?",
     fresh(), CANVAS, ["research"]),
    # ellipsis approval with pending (unresolved) task
    ("go ahead", {"id": "s3", "_pending_file_task": {
        "original_message": ASK8,
        "mention": "consolidated price list 2019.xlsx",
        "status": "pending"}}, {}, ["research"]),
    # teaching verb inside an edit-shaped sentence (the 02:28 defect)
    ("repeat the search and learn to include tennsmith sheet for "
     "roper whitney searches", superseded(), CANVAS,
     ["research", "learning"]),
    # pure edit, no teaching
    ("update the email price for No. 381 to $3,254.00",
     superseded(), CANVAS, ["canvas_edit"]),
    # ambiguous "it" after an edit conversation: no user-grounded
    # instruction -> needs grant, not granted
    ("apply it now", superseded(), CANVAS, ["canvas_edit"]),
]

S4 = [
    # durable-carrier-only state (restart projection)
    (ASK8, {"id": "s4"}, {}, ["research"]),
    ("Consolidated Price List 2019.xlsx is correct", {
        "id": "s4", "_pending_file_task": {
            "original_message": ASK8,
            "mention": "consolidated price list 2019.xlsx",
            "status": "pending",
            "resolved_file": TASK8["resolved_file"]}}, {}, ["research"]),
]


def run(name, scenario):
    rows = []
    m = {"n": 0, "correct": 0, "omitted": 0, "unintended_edit": 0}
    for msg, state, ctx, want in scenario:
        d = build_turn_decision(msg, state, [], ctx or {},
                                session_id=state.get("id", "s-eval"))
        kinds = [a["kind"] for a in d["requested_actions"]]
        m["n"] += 1
        missing = [k for k in want if k not in kinds]
        extra_edit = "canvas_edit" in kinds and "canvas_edit" not in want
        granted_edit = any(
            a["kind"] == "canvas_edit" and a["authorization"] == "granted"
            for a in d["requested_actions"])
        bad_grant = extra_edit and granted_edit
        ok = not missing and not extra_edit
        if ok:
            m["correct"] += 1
        else:
            m["omitted"] += len(missing)
            m["unintended_edit"] += int(bad_grant)
        rows.append({"msg": msg[:64], "decision": kinds, "expected": want,
                     "missing": missing, "unintended_edit": extra_edit,
                     "edit_granted": granted_edit})
    return {"scenario": name, "metrics": m, "rows": rows}


def main():
    out = {}
    total = {"n": 0, "correct": 0, "omitted": 0,
             "unintended_edit": 0}
    for name, sc in (("S1_competing_intents_long", S1),
                     ("S2_source_vs_file", S2),
                     ("S3_ambiguity_battery", S3),
                     ("S4_durable_restart_state", S4)):
        r = run(name, sc)
        out[name] = r
        for k in total:
            total[k] += r["metrics"][k]
        for row in r["rows"]:
            if row["missing"] or row["unintended_edit"]:
                print("MISS", name, row["msg"][:40], "decision=",
                      row["decision"], "expected=", row["expected"])
    out["TOTAL"] = {"metrics": total}
    print(json.dumps(total))
    out_path = Path(__file__).parent / (
        "turn_decision_scenario_evaluation.json")
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print("wrote", out_path)
    return 0 if total["omitted"] == 0 and total["unintended_edit"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
