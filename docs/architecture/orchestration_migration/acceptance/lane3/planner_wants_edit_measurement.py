#!/usr/bin/env python3
"""Measure the canvas-edit planner's `wants_edit` decision across models.

WHY MEASURE INSTEAD OF FIX
C16 is blocked one layer ABOVE the mutation machinery: the planner returns a
plan with `wants_edit=False` for an unambiguous request, so the app fails closed
and no edit is ever attempted. The planner's own prompt records the suspected
cause --

    "flash-tier models returned wants_edit=False for clear rebuild requests"
    -- chat_canvas_editor.py:2085

-- and the mitigation already applied (front-loading the user request) did not
fix it. So the open question is not "is the code broken" but "does the model
this workspace actually routes to make the right call, and does a different one
succeed". That is a routing-quality question, and the search work order is
explicit that these are settled by measurement, not by opinion:

    "No claimed accuracy percentage based only on ... agreement between two
     models."  AGENT_SEARCH_WORK_ORDER

So this calls the REAL planner, with the REAL prompt and a REAL canvas, once per
candidate model, and records what each one decided.

THE UNPINNED RUN IS THE CONTROL
`ATOM_ASYNC_EDIT_PLAN_MODEL` is empty in production, so the router ranks. That
first run reproduces the live decision exactly; every pinned run is measured
against it. A pin that also returns `wants_edit=False` is not a fix, and a pin
that returns True only once, on one prompt, is a hypothesis -- both are reported
as such rather than as a verdict.

    planner_wants_edit_measurement.py --world candidate_fix1 --out <dir>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
BACKEND = REPO / "backend"
WORLDS = BACKEND / "data" / "acceptance_worlds"
sys.path.insert(0, str(BACKEND))

USER_ID = "b83eb105-d9e7-41a5-83e3-a632b15b9ee3"

#: The exact production prompt shape that produced the refusal, so the
#: measurement is of the real decision and not a friendlier paraphrase.
EDIT_REQUEST = ("in the open canvas, change the quote validity from 15 days to "
                "30 days and mark the edit VALIDITY-30")

#: The canvas must be the REAL shape. An email canvas's content is a JSON
#: document; seeding bare HTML makes the canvas read fail ("Expecting value")
#: and a planner handed an unparseable canvas will decline for reasons that
#: have nothing to do with the model. The first run of this measurement used
#: bare HTML, which is a confound -- see the fixture note in the report.
CANVAS_CONTENT = json.dumps({
    "to": "steve@example.com",
    "cc": "",
    "subject": "Quote for Steve",
    "body": ("<div><p>Quote for Steve</p>"
             "<p><b>Quote validity: 15 days.</b></p>"
             "<p>Rows 1-5 are the requested machines.</p></div>"),
})

#: A deliberately small, decisive set. The point is the same-provider flash-vs-pro
#: A/B, not a leaderboard; a 400-model sweep would be a leaderboard.
CANDIDATE_PINS: List[Optional[str]] = [
    None,                                        # control: what runs today
    "deepseek/deepseek-flash",                   # the tier the prompt blames
    "deepseek/deepseek-v4-pro",                  # same provider, stronger tier
    "opencode-go/glm-5.3",
    "openrouter/anthropic/claude-sonnet-5",
]


def configure_world_env(world: str) -> Dict[str, Any]:
    """Point this process at a world, the way its server is configured.

    The planner needs the workspace's real provider credentials; without them
    every run would fail as a provider error and look like `wants_edit=False`.
    """
    state = json.loads((WORLDS / world / "preview_stack.json").read_text())
    run_dir = Path(state["run_dir"])
    data = run_dir / "data"
    os.environ.pop("TESTING", None)
    os.environ["DATABASE_URL"] = f"sqlite:///{data / 'atom.db'}"
    os.environ["ATOM_DATA_DIR"] = str(data)
    os.environ["LANCEDB_URI"] = str(data / "atom_memory")
    byok = data / "byok_keys.json"
    if byok.exists():
        os.environ["BYOK_KEYS_FILE"] = str(byok)
    return {"world": world, "run_dir": str(run_dir), "db": str(data / "atom.db"),
            "byok_present": byok.exists(),
            "source_id": (state.get("backend_health_identity") or {}).get("source_id")}


def canvas_dict() -> Dict[str, Any]:
    return {"canvas_id": "lane3-planner-probe", "canvas_type": "email",
            "title": "Quote for Steve", "content": CANVAS_CONTENT}


async def run_once(llm: Any, pin: Optional[str]) -> Dict[str, Any]:
    """One planner call, exactly as the orchestrator makes it."""
    from core.chat_canvas_editor import plan_canvas_edit
    if pin:
        os.environ["ATOM_ASYNC_EDIT_PLAN_MODEL"] = pin
    else:
        os.environ.pop("ATOM_ASYNC_EDIT_PLAN_MODEL", None)
    t0 = time.monotonic()
    rec: Dict[str, Any] = {"pin": pin or "(unpinned - production control)"}
    try:
        plan = await asyncio.wait_for(
            plan_canvas_edit(EDIT_REQUEST, [], canvas_dict(), llm),
            timeout=300)
    except Exception as exc:  # noqa: BLE001 - a failure mode is a result here
        rec.update({"ok": False, "error": f"{type(exc).__name__}: {exc}",
                    "latency_s": round(time.monotonic() - t0, 2)})
        return rec
    ops = getattr(plan, "ops", None) or []
    rec.update({
        "ok": True,
        "wants_edit": bool(getattr(plan, "wants_edit", False)),
        "edit_mode": str(getattr(plan, "edit_mode", "") or ""),
        "ops_count": len(ops),
        "op_kinds": sorted({str(getattr(o, "kind", None) or type(o).__name__)
                            for o in ops})[:6],
        "reply_head": str(getattr(plan, "reply", "") or "")[:200],
        "latency_s": round(time.monotonic() - t0, 2),
    })
    return rec


async def main_async(world: str, out: Path) -> int:
    env = configure_world_env(world)
    print(f"planner wants_edit measurement on {world}")
    print(f"  run_dir {env['run_dir']}")
    print(f"  byok    {env['byok_present']}")

    from core.llm_service import LLMService
    llm = LLMService(tenant_id=None)

    results: List[Dict[str, Any]] = []
    for pin in CANDIDATE_PINS:
        rec = await run_once(llm, pin)
        results.append(rec)
        if not rec["ok"]:
            print(f"  ERROR  {rec['pin']}: {rec['error'][:110]}")
        else:
            verdict = "WANTS EDIT" if rec["wants_edit"] else "declines"
            print(f"  {rec['pin']:42} {verdict:11} ops={rec['ops_count']} "
                  f"{rec['latency_s']}s")

    control = results[0]
    accepting = [r for r in results if r.get("ok") and r["wants_edit"]]
    declining = [r for r in results if r.get("ok") and not r["wants_edit"]]
    report: Dict[str, Any] = {
        "schema": "lane3-planner-wants-edit-v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "world": world,
        "env": env,
        "request": EDIT_REQUEST,
        "canvas": canvas_dict(),
        "canvas_content_is_json": True,
        "fixture_note": (
            "the canvas content is a JSON document, matching a real email "
            "canvas. An earlier run of this measurement used bare HTML, which "
            "makes canvas_crud_tool fail with 'Expecting value' and can make a "
            "planner decline for reasons unrelated to the model. That earlier "
            "run's verdict must not be relied on."),
        "pin_env_var": "ATOM_ASYNC_EDIT_PLAN_MODEL",
        "runs": results,
        "control": {
            "pin": control["pin"],
            "wants_edit": control.get("wants_edit"),
            "ops_count": control.get("ops_count"),
        },
        "summary": {
            "measured": sum(1 for r in results if r.get("ok")),
            "errors": sum(1 for r in results if not r.get("ok")),
            "accepts_edit": [r["pin"] for r in accepting],
            "declines_edit": [r["pin"] for r in declining],
        },
    }

    if control.get("ok") and control.get("wants_edit"):
        report["verdict"] = (
            "THE UNPINNED ROUTE ALREADY WANTS THE EDIT. The C16 refusal was not "
            "reproduced by calling the planner directly, so the decline depends "
            "on something the direct call does not carry (retrieved context, "
            "playbooks, provenance, the refreshed canvas, or the concurrency "
            "of the action-plan task). The divergence is ABOVE wants_edit, not "
            "in model quality.")
    elif accepting:
        report["verdict"] = (
            "MODEL-QUALITY BOUND. The unpinned router declines this unambiguous "
            f"edit; {len(accepting)} pinned model(s) accept it: "
            f"{[r['pin'] for r in accepting]}. A pin is a candidate fix, but "
            "this is ONE prompt on ONE canvas -- it is a lead, not a measured "
            "accuracy result, and it must be re-measured across a corpus "
            "before being adopted.")
    else:
        report["verdict"] = (
            "NOT MODEL QUALITY ALONE. No candidate model accepted the edit, so "
            "pinning cannot fix C16 and the cause lies in the prompt, the canvas "
            "shape, or the schema the plan must satisfy.")
    out.mkdir(parents=True, exist_ok=True)
    (out / "planner_wants_edit.json").write_text(json.dumps(report, indent=2))
    print(f"\nverdict: {report['verdict']}")
    print(f"-> {out/'planner_wants_edit.json'}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--world", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    return asyncio.run(main_async(args.world, Path(args.out)))


if __name__ == "__main__":
    raise SystemExit(main())
