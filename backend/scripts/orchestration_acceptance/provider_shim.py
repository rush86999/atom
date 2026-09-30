#!/usr/bin/env python3
"""Local OpenAI-compatible provider shim for the acceptance rig.

Substitutes PROVIDER RESPONSES ONLY: the production execution, routing,
persistence, verification, and delivery paths run for real against this
endpoint. Scripts contain authored model completions — never manufactured
final outcomes. Serves /v1/chat/completions (streaming and non-streaming);
logs every request's message count and which scripted response was served.
"""
from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List


def load_script(path: Path) -> Dict[Any, Any]:
    """Index the authored responses for selection.

    Keyed by the declared ``tool`` when present, otherwise by the ``match``
    substring, so tool-scoped entries are reachable at all.

    A tool-scoped entry has no ``match`` key by design, and the previous
    comprehension required one: it raised KeyError on the first such entry, and
    because the script is loaded inside a broad try the whole load silently
    fell back -- the two authored CanvasEditPlan responses never entered the
    script, and every edit-planner request was served a ToolPlan decline from a
    catch-all substring instead. Measured on F03 (2026-09-28): 0 of 16
    CanvasEditPlan requests were served the authored plan.
    """
    doc = json.loads(path.read_text())
    out: Dict[Any, Any] = {}
    for entry in doc["responses"]:
        resp = entry.get("response")
        tool = resp.get("tool") if isinstance(resp, dict) else None
        match = entry.get("match")
        if tool and match is not None:
            # Several responses can answer the SAME tool (a script may author one
            # plan per scenario), so a bare tool key silently overwrites all but
            # the last. Key those by (tool, match) and prefer the (tool, match)
            # hit whenever the request's prompt carries the discriminator.
            out[(tool, str(match).lower())] = resp
        elif tool:
            out[tool] = resp
        elif match is not None:
            out[str(match).lower()] = resp
    return out


class ShimState:
    script: Dict[str, str] = {}
    default: str = ""
    log: List[Dict[str, object]] = []
    raw_completions: List[str] = []
    stall_counts: Dict[str, int] = {}
    #: Armed by /arm-stalls. Overrides the scripted stall so a stall can be
    #: aimed at ONE leg of a run instead of whichever request happens to be
    #: first (2026-09-27: case 1 and case 2 share one world launch and one
    #: interactive budget, so a stall armed at script time was always consumed
    #: by case 1 -- which then blew the shortened budget and was refused).
    armed: Dict[str, object] = {}
    #: Requests that did NOT advertise the armed tool. Recorded separately so a
    #: request that did not match the armed tool is visible rather than
    #: indistinguishable from a request that never happened.
    gate_missed: List[Dict[str, object]] = []
    #: Requests that actually consumed the armed stall.
    stall_hits: List[Dict[str, object]] = []


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_POST(self):
        if "/chat/completions" not in self.path:
            self.send_response(404); self._cors()
            self.wfile.write(b'{"error": "not found"}')
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        messages = body.get("messages") or []
        last_user = next((m.get("content", "") for m in reversed(messages)
                          if m.get("role") == "user"), "")
        blob = " ".join(str(m.get("content", "")) for m in messages).lower()
        tool_specs = body.get("tools") or []
        _tool_names = [t.get("function", {}).get("name") for t in tool_specs
                       if isinstance(t, dict)]
        # SELECTION ORDER: tool name first, prompt substring only as a fallback.
        #
        # A substring key is ambiguous by construction: the reply leg's prompt
        # also contains the edit planner's wording, so a substring key can be
        # consumed by the wrong call and the injection silently never reaches the
        # planner. An entry may therefore declare `"tool": "CanvasEditPlan"`, and
        # those entries are considered BEFORE any substring entry, so selection is
        # unambiguous whenever the script says which tool it is answering. The
        # capture records `selected_by` so "was the intended injection consumed,
        # and by what rule" is an observation rather than an inference.
        # Prefer a (tool, match) entry whose discriminator is in the prompt: a
        # script may author several responses for one tool, and a bare tool key
        # would serve whichever happened to be last. On F03 (2026-09-28) both
        # authored CanvasEditPlan plans collapsed to one key, so every
        # edit-planner request was served the OVLAP-B plan whose `find` text is
        # not in the canvas -- the product then correctly reported
        # "1/1 patch op(s) failed to match" and the case read as an effect-layer
        # failure when it was a selection failure.
        _by_tool_exact = [(k, r) for k, r in STATE.script.items()
                          if isinstance(k, tuple) and r.get("tool") in _tool_names
                          and k[1] in blob]
        # Only BARE tool keys are a fallback. Filtering on the response's tool
        # would also pull in the (tool, match) entries above, so a request with
        # no discriminator would still get an arbitrary one of the per-scenario
        # plans -- reintroducing the collision this whole split exists to avoid.
        _by_tool = [(k, r) for k, r in STATE.script.items()
                    if isinstance(k, str) and isinstance(r, dict)
                    and r.get("tool") == k and k in _tool_names]
        _by_text = [(k, r) for k, r in STATE.script.items()
                    if (isinstance(k, str) and k in blob)
                    or (isinstance(k, tuple) and all(x in blob for x in k))]
        entry = next(iter(_by_tool_exact), None)
        _selected_by = "tool+match" if entry is not None else "tool"
        if entry is None:
            entry = next(iter(_by_tool), None)
        if entry is None:
            entry = next(iter(_by_text), None)
            _selected_by = "substring" if entry is not None else None
        # TOOL_CALL ENTRIES REQUIRE A TOOL-ADVERTISING REQUEST (2026-09-28):
        # a tool_call entry served to a non-tool leg (reply/readback/answer)
        # yields message.content=None -> empty completion -> the byok handler
        # benches the (only) model for empty output and every later forked
        # leg dead-ends. Restrict tool_call-shaped entries to tool_mode
        # requests; non-tool legs fall through to the script's default text.
        if entry is not None and isinstance(entry[1], dict) \
                and ("tool_call" in entry[1]
                     or "tool_call" in (entry[1].get("response") or {})) \
                and not (tool_specs or body.get("tool_choice")):
            entry = None
            _selected_by = None
        # STALL GATE (2026-09-27). The stall is armed for ONE exact structured
        # call -- the edit planner's -- identified by the tool the request
        # ADVERTISES, never by prompt text. Matching on prompt text was wrong:
        # the reply leg's planner prompt also contains the tool's name, so the
        # reply leg drew the stall and burned the interactive budget itself,
        # which starved the edit leg before it ever started (the edit leg is
        # skipped outright when the budget cannot reserve
        # ATOM_REPLY_LEG_MIN_SECONDS for the answer). Requests that do not
        # carry the armed tool are recorded separately so an unmatched request
        # is visible instead of silently consuming the armed stall.
        _want_tool = STATE.armed.get("tool") if STATE.armed else None
        _gate_ok = (not _want_tool) or (_want_tool in _tool_names)
        if _want_tool and not _gate_ok:
            STATE.gate_missed.append({
                "t": time.strftime("%FT%T"), "tool_names": _tool_names,
                "stream": bool(body.get("stream")),
                "tool_mode": bool(tool_specs) or bool(body.get("tool_choice")),
            })
        if STATE.capture_path:
            with open(STATE.capture_path, "a") as cf:
                cf.write(json.dumps({
                    "t": time.strftime("%FT%T"), "model": body.get("model"),
                    "stream": bool(body.get("stream")),
                    "tool_mode": bool(tool_specs) or bool(body.get("tool_choice")),
                    "tool_names": [t.get("function", {}).get("name") for t in tool_specs
                                   if isinstance(t, dict)],
                    "system_head": str(next((m.get("content", "") for m in messages
                                             if m.get("role") == "system"), ""))[:400],
                    "last_user": str(last_user)[:800],
                    "matched": bool(entry),
                    "matched_key": (entry[0] if entry else None),
                    "selected_by": _selected_by,
                    "tool_scoped_entries": [k for k, _r in _by_tool],
                    "tool_gate_wanted": _want_tool,
                    "tool_gate_ok": bool(_gate_ok),
                    "served_head": (json.dumps(entry[1])[:200] if entry and not isinstance(entry[1], str)
                                    else str(entry[1])[:200]) if entry else None,
                }) + "\n")
        if entry and isinstance(entry[1], dict) and _gate_ok and (
                entry[1].get("stall_seconds") or STATE.armed):
            # `stall_first_n` scopes the stall to the FIRST n GATED matches --
            # requests that actually advertise the armed tool. The background
            # case needs the interactive edit leg to overrun its bound so the
            # real async fork is taken, while the BACKGROUND retry (same tool,
            # same script match) must answer promptly. A plain `stall_seconds`
            # stalls both and the continuation starves too.
            limit = entry[1].get("stall_first_n")
            secs = float(entry[1].get("stall_seconds") or 0) or None
            if STATE.armed:
                # Explicitly armed for a specific leg and a specific tool:
                # authoritative, so the script's own stall cannot fire first
                # and steal the budget.
                secs = float(STATE.armed.get("seconds") or 0) or None
                limit = STATE.armed.get("first_n")
            if secs:
                seen_key = f"stall:{entry[0]}"
                if limit is None:
                    time.sleep(secs)
                else:
                    seen = STATE.stall_counts.get(seen_key, 0)
                    if seen < int(limit):
                        STATE.stall_counts[seen_key] = seen + 1
                        STATE.stall_hits.append({
                            "t": time.strftime("%FT%T"), "seconds": secs,
                            "tool_names": _tool_names,
                        })
                        time.sleep(secs)
        if entry is None and STATE.fail_unmatched:
            # EXPLICIT failure (review round 22): unmatched requests must never
            # fall through to a success-shaped response.
            self.send_response(502)
            self._cors()
            self.wfile.write(json.dumps({"error": {"message":
                "shim: no scripted response matched this request",
                "type": "invalid_request_error"}}).encode())
            return
        if entry is None:
            content = STATE.default
        elif isinstance(entry[1], str):
            content = entry[1]
        else:
            # entry[1] IS the envelope (e.g. {"tool_call": {...}}). This used to
            # unwrap a "response" key that does not exist at this level, so it
            # evaluated to None and every structured call was answered with an
            # EMPTY completion: content=None, tool_calls=None, completion_tokens=1.
            # The capture file still recorded the correctly-selected entry, so the
            # run looked like the plan was served while the product received
            # nothing -- which reads as "the edit was planned but never applied"
            # and points at the effect layer instead of the shim. Accept the
            # wrapper shape too, for scripts that nest under "response".
            inner = entry[1]
            nested = inner.get("response") if isinstance(inner, dict) else None
            content = nested if isinstance(nested, (str, dict)) else inner
        nonce = f"shim-{int(time.time()*1000)}-{len(STATE.log)}"
        # A tool_call script entry is a DICT, not a string: it is the envelope
        # that becomes message.tool_calls below. Substituting {NONCE} (and
        # slicing for the log) is string-only, so doing it unconditionally raised
        # AttributeError and 500'd every structured call -- which looked exactly
        # like "the shim was never reached".
        if isinstance(content, str):
            content = content.replace("{NONCE}", nonce)
        completion_id = nonce
        served_head = (json.dumps(content)[:200] if not isinstance(content, str)
                       else content[:200])
        STATE.log.append({"epoch": time.time(), "t": time.strftime("%FT%T"), "model": body.get("model"),
                          "messages": len(messages), "stream": bool(body.get("stream")),
                          "tool_mode": bool(tool_specs) or bool(body.get("tool_choice")),
                          "tool_names": [t.get("function", {}).get("name") for t in tool_specs
                                         if isinstance(t, dict)],
                          "served": served_head, "nonce": completion_id,
                          "last_user_tail": str(last_user)[-80:]})
        STATE.raw_completions.append(
            content if isinstance(content, str) else json.dumps(content))
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            parts = [content[i:i + 24] for i in range(0, len(content), 24)] or [""]
            for part in parts:
                chunk = {"id": completion_id, "object": "chat.completion.chunk",
                         "choices": [{"index": 0, "delta": {"content": part}}]}
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            done = {"id": completion_id, "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
            self.wfile.write(f"data: {json.dumps(done)}\n\ndata: [DONE]\n\n".encode())
            return
        message_out: Dict[str, Any] = {"role": "assistant", "content": content}
        finish = "stop"
        if isinstance(content, dict) and "tool_call" in content:
            tc = content["tool_call"]
            message_out = {"role": "assistant", "content": None,
                           "tool_calls": [{"id": f"call-{completion_id}", "type": "function",
                                           "function": {"name": tc.get("name", "respond"),
                                                        "arguments": json.dumps(tc.get("arguments", {}))}}]}
            finish = "tool_calls"
        payload = {"id": completion_id, "object": "chat.completion",
                   "created": int(time.time()), "model": body.get("model") or "shim",
                   "choices": [{"index": 0, "message": message_out, "finish_reason": finish}],
                   "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
        self.send_response(200); self._cors()
        self.wfile.write(json.dumps(payload).encode())

    def do_GET(self):
        if self.path.startswith("/api/tags"):
            # Ollama-runtime probe (2026-09-28): when the harness points
            # OLLAMA_BASE_URL at this shim, the byok handler probes
            # /api/tags to decide the local-runtime lane is up. Answer with
            # the model the shim claims to serve so the pool gets a second
            # dispatchable route for forked/concurrent planner legs.
            body = json.dumps({"models": [{"name": "llama3:8b"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/arm-stalls"):
            # Arm the stall for ONE named leg and ONE exact tool. Query form:
            #   /arm-stalls?seconds=40&first_n=1&tool=CanvasEditPlan[&disarm=1]
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(self.path).query)
            if q.get("disarm"):
                STATE.armed = {}
            else:
                STATE.armed = {
                    "seconds": float((q.get("seconds") or ["0"])[0] or 0),
                    "first_n": int((q.get("first_n") or ["1"])[0] or 1),
                    "tool": (q.get("tool") or [""])[0] or "",
                }
            STATE.stall_counts.clear()
            STATE.gate_missed.clear()
            STATE.stall_hits.clear()
            self.send_response(200); self._cors()
            self.wfile.write(json.dumps({"armed": STATE.armed,
                                         "stall_counts": STATE.stall_counts}
                                        ).encode())
            return
        if self.path.endswith("/reset-stalls"):
            # RE-ARM the per-key stall counters (2026-09-27, acceptance c16).
            # `stall_first_n` is a GLOBAL counter over the shim's whole life, so
            # whichever request arrives first consumes the budget. Case 1 (sync)
            # runs before case 2 (background) in one shim session, so case 1
            # burned the single stall and the background request's planner
            # answered instantly -- inside the interactive budget, so NO fork.
            # That made the sync-vs-fork outcome depend on request order, which
            # is exactly the non-determinism that made case 2 untrustworthy.
            # Re-arming immediately before the background request makes the
            # fork deterministic without changing what any gate evaluates.
            STATE.stall_counts.clear()
            self.send_response(200); self._cors()
            self.wfile.write(json.dumps({"reset": True,
                                         "stall_counts": STATE.stall_counts}
                                        ).encode())
            return
        if self.path.endswith("/models"):
            STATE.log.append({"epoch": time.time(), "t": time.strftime("%FT%T"),
                              "model": "(catalog-discovery)", "messages": 0,
                              "stream": False, "served": "(models list)"})
            self.send_response(200); self._cors()
            # The router's provider catalog is discovered from this list —
            # advertise the model ids the chat path may request.
            models = ["shim-1", "gpt-6-astra", "gpt-5.2", "gpt-5-mini", "gpt-4o",
                      "gpt-4o-mini", "deepseek-chat", "deepseek-reasoner",
                      "qwen-max", "qwen-plus", "claude-sonnet-4", "claude-haiku-4"]
            self.wfile.write(json.dumps(
                {"object": "list", "data": [{"id": m, "object": "model"} for m in models]}).encode())
            return
        if self.path.endswith("/log"):
            self.send_response(200); self._cors()
            self.wfile.write(json.dumps({"log": STATE.log,
                                         "raw_completions": STATE.raw_completions,
                                         "gate_missed": STATE.gate_missed,
                                         "stall_hits": STATE.stall_hits,
                                         "armed": STATE.armed}).encode())
            return
        self.send_response(404); self._cors()

    def log_message(self, *a):
        pass


STATE = ShimState()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--script", required=True)
    ap.add_argument("--capture", default="")
    args = ap.parse_args()
    doc = json.loads(Path(args.script).read_text())
    # Use the shared loader. This block used to re-implement indexing with a
    # hard `e["match"]` requirement, which meant the `__main__` path -- the only
    # path that actually runs -- DROPPED every tool-scoped entry (they have no
    # `match` key) and indexed only substrings. So the authored CanvasEditPlan
    # responses were unreachable in practice even after load_script() was fixed,
    # and edit-planner requests fell through to a catch-all ToolPlan decline.
    # Measured on F03 (2026-09-28): 24 tool-selected vs 12 substring-declines
    # from an otherwise identical request shape.
    STATE.script = load_script(Path(args.script))
    STATE.default = doc.get("default", "")
    STATE.fail_unmatched = bool(doc.get("fail_unmatched"))
    STATE.capture_path = args.capture
    if STATE.capture_path:
        # Truncate once per shim process so the capture is THIS run's evidence.
        # The handler appends, and nothing ever truncated, so a reused world
        # accumulated every prior run's requests in one file. Per-run evidence
        # then read as cumulative: on F03 (2026-09-28) request totals grew
        # 21 -> 36 -> 72 -> 92 across runs while a stale 12-request group from
        # an earlier build looked like a live defect. Append stays for the
        # handler; only process start truncates.
        with open(STATE.capture_path, "w"):
            pass
    print(f"[shim] serving {len(STATE.script)} scripted responses on :{args.port} "
          f"(tool-scoped: {sorted(k for k in STATE.script if not isinstance(k, str))})")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
