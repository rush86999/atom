#!/usr/bin/env python3
"""Is the terminal event about THIS conversation and THIS execution?

WHY THIS IS A SEPARATE FILE
The C16 background case asserts `live_notification_received` — that an event
arrived. That is not attribution. An event can arrive on the right channel,
carry the right status, and still describe a different conversation, a different
canvas, or a different execution than the one that was requested, and every
"did the user get told" check would still be green. A user watching one
conversation must never be handed another one's outcome.

So the binding is checked here, on a C16 result artifact, as equality between
four independently-sourced identifiers:

  the request        -> the session id in the artifact's identity chain
  the canvas         -> the canvas the probe seeded for that session
  the durable row    -> the continuation's own AgentExecution row
  the notification   -> the `chat_continuation` event the subscriber received

They must agree, and they must be non-empty. Absence is a failure, not a pass:
an event that omits its ids cannot be attributed, so it cannot be claimed as
correct delivery.

    delivery_binding.py <c16_bg_result.json> [...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def verify(path: Path) -> Dict[str, Any]:
    doc = json.loads(path.read_text())
    bg = doc.get("case_bg-success") or doc.get("case_bg_success") or {}
    events: List[Dict[str, Any]] = bg.get("continuation_events") or []
    chain = bg.get("identity_chain") or {}
    terminal = bg.get("terminal") or {}
    canvas_id = chain.get("canvas_id")
    session_id = chain.get("session_id")
    continuation_id = chain.get("continuation_id")

    checks: Dict[str, Any] = {}
    checks["the run reached a terminal state"] = bool(terminal)
    checks["exactly ONE terminal event was delivered"] = len(events) == 1
    ev = (events[0].get("data") or {}) if events else {}

    checks["the event names the same continuation as the durable row"] = bool(
        continuation_id) and ev.get("continuation_id") == continuation_id, {
        "event": ev.get("continuation_id"), "durable_row": continuation_id}
    checks["the event names the same CONVERSATION as the request"] = bool(
        session_id) and ev.get("session_id") == session_id, {
        "event": ev.get("session_id"), "request": session_id}
    checks["the event names the same canvas as the one edited"] = bool(
        canvas_id) and ev.get("canvas_id") == canvas_id, {
        "event": ev.get("canvas_id"), "canvas": canvas_id}
    checks["the event's originating execution matches the terminal row"] = bool(
        ev.get("originating_execution_id")) and \
        ev.get("originating_execution_id") == terminal.get("originating_execution_id"), {
        "event": ev.get("originating_execution_id"),
        "terminal": terminal.get("originating_execution_id")}
    checks["the event's status agrees with the durable terminal status"] = (
        ev.get("status") == "applied" and terminal.get("status") == "completed"
    ) if events else False, {
        "event": ev.get("status"), "durable": terminal.get("status")}
    checks["the event carries a readable summary, not an internal diagnostic"] = (
        bool(ev.get("summary")) and "[background continuation" not in str(ev.get("summary"))
    ) if events else False, {"summary": str(ev.get("summary"))[:120]}

    failed = [k for k, v in checks.items() if not (v[0] if isinstance(v, tuple) else v)]
    return {"artifact": str(path), "checks": checks, "failed": failed,
            "passed": not failed}


def main(argv: List[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    out = []
    for arg in argv:
        out.append(verify(Path(arg)))
    payload = {
        "schema": "lane3-delivery-binding-v1",
        "claim": "the terminal event is about this conversation, this canvas and "
                 "this execution -- identity, not arrival",
        "results": out,
        "all_pass": all(r["passed"] for r in out),
    }
    dest = Path(argv[0]).parent / "delivery_binding.json"
    dest.write_text(json.dumps(payload, indent=1, default=str))
    for r in out:
        print(f"{'PASS' if r['passed'] else 'FAIL'}  {Path(r['artifact']).name}")
        for name, value in r["checks"].items():
            ok = value[0] if isinstance(value, tuple) else value
            print(f"  {'ok  ' if ok else 'FAIL'} {name}")
            if not ok and isinstance(value, tuple) and len(value) > 1:
                print(f"        {value[1]}")
    print(f"\n-> {dest}")
    return 0 if payload["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
