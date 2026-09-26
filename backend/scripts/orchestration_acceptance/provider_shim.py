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


def load_script(path: Path) -> Dict[str, str]:
    doc = json.loads(path.read_text())
    return {entry["match"].lower(): entry["response"] for entry in doc["responses"]}


class ShimState:
    script: Dict[str, str] = {}
    default: str = ""
    log: List[Dict[str, object]] = []
    raw_completions: List[str] = []


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
        entry = next(((key, resp) for key, resp in STATE.script.items()
                      if (isinstance(key, str) and key in blob)
                      or (isinstance(key, tuple) and all(k in blob for k in key))), None)
        tool_specs = body.get("tools") or []
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
                    "served_head": (json.dumps(entry[1])[:200] if entry and not isinstance(entry[1], str)
                                    else str(entry[1])[:200]) if entry else None,
                }) + "\n")
        if entry and isinstance(entry[1], dict) and entry[1].get("stall_seconds"):
            time.sleep(float(entry[1]["stall_seconds"]))
        if entry is None and STATE.fail_unmatched:
            # EXPLICIT failure (review round 22): unmatched requests must never
            # fall through to a success-shaped response.
            self.send_response(502)
            self._cors()
            self.wfile.write(json.dumps({"error": {"message":
                "shim: no scripted response matched this request",
                "type": "invalid_request_error"}}).encode())
            return
        content = entry[1] if entry and isinstance(entry[1], str) else (
            entry[1].get("response") if entry and isinstance(entry[1], dict) else STATE.default)
        nonce = f"shim-{int(time.time()*1000)}-{len(STATE.log)}"
        content = content.replace("{NONCE}", nonce)
        STATE.log.append({"epoch": time.time(), "t": time.strftime("%FT%T"), "model": body.get("model"),
                          "messages": len(messages), "stream": bool(body.get("stream")),
                          "served": content[:80], "nonce": nonce,
                          "last_user_tail": str(last_user)[-80:]})
        STATE.raw_completions.append(content)
        completion_id = nonce
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
                                         "raw_completions": STATE.raw_completions}).encode())
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
    STATE.script = {}
    for e in doc["responses"]:
        key = e["all"] if e.get("all") else e["match"]
        STATE.script[tuple(k.lower() for k in key) if isinstance(key, list) else key.lower()] = e["response"]
    STATE.default = doc.get("default", "")
    STATE.fail_unmatched = bool(doc.get("fail_unmatched"))
    STATE.capture_path = args.capture
    print(f"[shim] serving {len(STATE.script)} scripted responses on :{args.port}")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
