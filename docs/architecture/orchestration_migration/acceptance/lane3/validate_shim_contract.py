#!/usr/bin/env python3
"""Validate the shim's response through the PRODUCTION parser, in isolation.

WHY THIS EXISTS
The acceptance run could not tell these two apart:

    (a) the shim served a response and the planner ACCEPTED it
    (b) the shim served a response, the parser REJECTED it, and the pinned
        call's documented "returned no result -- retrying unpinned" fallback
        quietly let a REAL provider supply a replacement plan

(b) is invisible in the chat response: the user sees a decline either way, and
"the shim was reached" is provable from the shim's own log while "the planner
accepted it" is not. So the acceptance harness now asserts the two separately,
and this script establishes which one is true by driving the same production
entry point with no orchestrator, no auth, and no canvas in the way.

Redaction: no API key, no Authorization header, and no BYOK secret is ever read
or printed here; the shim's key is a literal placeholder.

    python validate_shim_contract.py --world <w> --out <dir>
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
BACKEND = REPO / "backend"
WORLDS = BACKEND / "data" / "acceptance_worlds"
SHIM = BACKEND / "scripts" / "orchestration_acceptance" / "provider_shim.py"
SHIM_MODEL = "shim-1"
WORKSPACE_ID = os.environ.get("LANE3_WORKSPACE_ID", "default")
TENANT_ID = os.environ.get("LANE3_TENANT_ID", "default")

REDACT = ("sk-", "Bearer ", "api_key", "authorization")


def redact(obj: Any) -> Any:
    if isinstance(obj, str):
        out = obj
        for token in REDACT:
            i = out.lower().find(token.lower())
            while i != -1:
                out = out[:i] + token + "<REDACTED>"
                nxt = out.lower().find(token.lower(), i + len(token) + 10)
                i = nxt
        return out
    if isinstance(obj, dict):
        return {k: ("<REDACTED>" if any(t in k.lower() for t in REDACT)
                    else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--world", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    state = json.loads((WORLDS / args.world / "preview_stack.json").read_text())
    db = str(Path(state["db_path"]).resolve())
    if "acceptance_worlds" not in db:
        raise SystemExit(f"refusing to touch anything outside a world: {db}")

    plan_args = {
        "wants_edit": True, "edit_mode": "patch",
        "ops": [{"field": "body", "find": "Quote validity: 15 days.",
                 "replace": "Quote validity: 30 days."}],
        "restore_audit_id": None, "updated_content_json": None, "title": None,
        "reply": "Updated the quote validity to 30 days.",
    }
    script = out / "shim_script.json"
    script.write_text(json.dumps({"responses": [{
        "match": "CanvasEditPlan",
        "response": {"response": {"tool_call": {"name": "CanvasEditPlan",
                                                 "arguments": plan_args}}}}]},
                  indent=2))
    capture = out / "capture.jsonl"
    port = free_port()
    proc = subprocess.Popen(
        [str(BACKEND / "venv314" / "bin" / "python"), str(SHIM),
         "--port", str(port), "--script", str(script), "--capture", str(capture)],
        stdout=(out / "shim.log").open("ab"), stderr=subprocess.STDOUT,
        start_new_session=True)

    os.environ.pop("TESTING", None)
    os.environ["DATABASE_URL"] = f"sqlite:///{db}"
    os.environ["ATOM_DATA_DIR"] = str(Path(db).parent)
    os.environ["ENVIRONMENT"] = "development"
    sys.path.insert(0, str(BACKEND))

    import uuid
    from core.database import get_db_session
    from core.models import LocalModelProvider
    provider_id = str(uuid.uuid4())
    with get_db_session() as s:
        s.add(LocalModelProvider(
            id=provider_id, workspace_id=WORKSPACE_ID,
            tenant_id=state.get("tenant_id") or TENANT_ID,
            name="C16 contract-validator shim", provider_type="openai",
            base_url=f"http://127.0.0.1:{port}/v1",
            api_key="shim-not-a-secret", is_active=True))
        s.commit()
    key = f"local_{provider_id[:8]}"

    # Reload the handler so _load_local_providers() sees the new row.
    for mod in [m for m in list(sys.modules) if m.startswith("core.llm")]:
        del sys.modules[mod]

    # Go through the real service singleton, not a hand-built handler, so the
    # provider registry, workspace scoping and dispatch are the production ones.
    from core.llm_service import get_llm_service
    from core.chat_canvas_editor import CanvasEditPlan
    service = get_llm_service()
    handler = service._get_handler(workspace_id=WORKSPACE_ID,
                                   tenant_id=state.get("tenant_id") or TENANT_ID)
    handler._initialize_clients()

    report: Dict[str, Any] = {
        "schema": "lane3-c16-shim-contract-v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "world": args.world, "provider_key": key, "model": SHIM_MODEL,
        "scripted_arguments": plan_args,
    }

    try:
        report["provider_client_registered"] = key in getattr(handler, "clients", {})
        if not report["provider_client_registered"]:
            report["error"] = ("the shim provider is not a client, so any pin "
                               "naming it resolves to {} and routing falls back")

        # Ask for the plan by the SAME production entry point the editor uses.
        result = None
        err = None
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                handler.generate_structured_response(
                    prompt=("USER REQUEST: change the quote validity from 15 "
                            "days to 30 days (produce a CanvasEditPlan)"),
                    system_instruction="You return only the requested JSON object.",
                    response_model=CanvasEditPlan,
                    temperature=0.0, task_type="planning",
                    provider_model=(key, SHIM_MODEL),
                    disable_reasoning=True, max_tokens=14000))
            loop.close()
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"
        report["parse_error"] = redact(err) if err else None

        # Same call again, but straight through instructor so the ValidationError
        # surfaces instead of being swallowed into the unpinned fallback. Three
        # shim requests for one logical call means instructor retried, i.e. the
        # envelope was REJECTED -- that retry count is itself the evidence.
        import instructor as _ins
        try:
            _client = handler.clients[key]
            _ic = _ins.from_openai(_client)
            direct = _ic.chat.completions.create(
                model=SHIM_MODEL,
                messages=[{"role": "user",
                           "content": "change the quote validity 15 -> 30 "
                                      "(produce a CanvasEditPlan)"}],
                response_model=CanvasEditPlan, max_retries=1)
            report["direct_instructor"] = {
                "ok": True, "type": type(direct).__name__,
                "parsed": redact(direct.model_dump())}
        except Exception as e:  # noqa: BLE001
            report["direct_instructor"] = {"ok": False,
                                           "error": redact(f"{type(e).__name__}: {e}")}
        report["parsed_type"] = type(result).__name__ if result is not None else None
        report["parsed"] = redact(
            result.model_dump() if hasattr(result, "model_dump")
            else (json.loads(result) if isinstance(result, str) else result))
        report["accepted_wants_edit"] = bool(
            getattr(result, "wants_edit", False))
        report["ops_preserved"] = len(getattr(result, "ops", []) or [])
    finally:
        try:
            proc.terminate()
        except Exception:
            pass

    if capture.exists():
        rows = [json.loads(line) for line in capture.read_text().splitlines() if line]
        report["captured_requests"] = [
            {"tool_names": r.get("tool_names"), "tool_mode": r.get("tool_mode"),
             "model": r.get("model"), "stream": r.get("stream"),
             "matched": r.get("matched"),
             "served_head": redact(str(r.get("served_head") or ""))[:200]}
            for r in rows][-6:]
    report["verdict"] = {
        "shim_served": bool(report.get("captured_requests")),
        "parser_accepted": report.get("accepted_wants_edit") is True,
    }
    report["verdict"]["both_green"] = all(report["verdict"].values())
    (out / "shim_contract.json").write_text(json.dumps(redact(report), indent=2))
    print(json.dumps(redact({k: v for k, v in report.items()
                             if k != "captured_requests"}), indent=2)[:2200])
    print("\ncaptured request tool_names:",
          [r.get("tool_names") for r in report.get("captured_requests", [])])
    return 0 if report["verdict"]["both_green"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
