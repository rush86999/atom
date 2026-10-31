"""Bounded local OpenAI/Anthropic-compatible upstream for the acceptance world.

The harness never calls a cloud provider. This server answers the two wire
protocols the gateway and the LLM service speak, records every request, and can
emit a scripted tool call so agent loops can be exercised deterministically.

Run standalone:
    python -m scripts.readme_acceptance.mock_llm_server --port 59997
"""
from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List

_CALLS: List[Dict[str, Any]] = []
_CALLS_LOCK = threading.Lock()


def calls() -> List[Dict[str, Any]]:
    with _CALLS_LOCK:
        return list(_CALLS)


def reset() -> None:
    with _CALLS_LOCK:
        _CALLS.clear()


def _openai_completion(body: Dict[str, Any]) -> Dict[str, Any]:
    model = body.get("model") or "acceptance-model"
    messages = body.get("messages") or []
    tools = body.get("tools") or []
    prompt = json.dumps(messages)[-4000:]
    prompt_full = json.dumps(messages)
    content = f"acceptance reply for: {prompt[-120:]}"
    message: Dict[str, Any] = {"role": "assistant", "content": content}
    finish = "stop"
    # Deterministic tool call: if tools are offered and the caller has not
    # already used one, emit the first offered tool once.
    used_tool = any(m.get("role") == "tool" for m in messages if isinstance(m, dict))
    if tools and not used_tool:
        tool = tools[0]
        fn = tool.get("function") or tool
        name = fn.get("name") or "acceptance_tool"
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": f"call_{uuid.uuid4().hex[:12]}",
                "type": "function",
                "function": {"name": name, "arguments": "{}"},
            }],
        }
        finish = "tool_calls"
    low = prompt_full.lower()
    if "output only json" in low and "entities" in low:
        # KnowledgeExtractor contract: content must be a JSON object with
        # entities/relationships. Controlled extraction fixture.
        content = json.dumps({
            "entities": [
                {"id": "e1", "name": "Atlas", "type": "project",
                 "description": "acceptance project"},
                {"id": "e2", "name": "Borealis", "type": "project",
                 "description": "downstream project"},
                {"id": "e3", "name": "alice@example.com", "type": "email",
                 "description": "contact"},
            ],
            "relationships": [
                {"from": "e1", "to": "e2", "type": "DEPENDS_ON",
                 "description": "Atlas depends on Borealis"},
            ],
        })
        message = {"role": "assistant", "content": content}
        finish = "stop"
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }


def _anthropic_message(body: Dict[str, Any]) -> Dict[str, Any]:
    model = body.get("model") or "acceptance-model"
    return {
        "id": f"msg_{uuid.uuid4().hex[:12]}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": "acceptance anthropic reply"}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 9, "output_tokens": 5},
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "AtomAcceptanceLLM/1.0"

    def log_message(self, fmt, *args):  # silence the test server
        return

    def _read(self) -> Dict[str, Any]:
        length = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode() or "{}")
        except Exception:
            return {"_raw": raw.decode("latin1")}

    def _send(self, status: int, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _mcp(self, body: Dict[str, Any]) -> None:
        """Minimal MCP JSON-RPC 2.0 server (initialize/tools/list/tools/call)."""
        method = body.get("method")
        req_id = body.get("id")
        if method == "initialize":
            result = {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "acceptance-mcp", "version": "1.0.0"},
            }
        elif method == "tools/list":
            result = {"tools": [{
                "name": "echo",
                "description": "Echo the provided text",
                "inputSchema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            }]}
        elif method == "tools/call":
            args = (body.get("params") or {}).get("arguments") or {}
            result = {"content": [{"type": "text",
                                   "text": str(args.get("text", "echo"))}],
                      "isError": False}
        else:
            self._send(200, {"jsonrpc": "2.0", "id": req_id,
                             "error": {"code": -32601, "message": "method not found"}})
            return
        self._send(200, {"jsonrpc": "2.0", "id": req_id, "result": result})

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._send(200, {"object": "list", "data": [
                {"id": "acceptance-model", "object": "model", "owned_by": "acceptance"},
                {"id": "gpt-4o-mini", "object": "model", "owned_by": "acceptance"},
            ]})
            return
        self._send(404, {"error": {"message": "not found"}})

    def do_POST(self):
        body = self._read()
        path = self.path.split("?")[0].rstrip("/")
        with _CALLS_LOCK:
            _CALLS.append({"path": self.path, "body": body,
                           "authorization": self.headers.get("authorization")})
        if path.endswith("/mcp"):
            self._mcp(body)
            return
        if path.endswith("/chat/completions"):
            if body.get("model") == "fail-model":
                self._send(502, {"error": {"message": "acceptance upstream failure",
                                           "type": "upstream_error"}})
                return
            # OpenAI streaming is requested by some callers; answer with a
            # compact SSE stream when asked, otherwise a normal completion.
            if body.get("stream"):
                payload = _openai_completion(body)
                chunk = {
                    "id": payload["id"], "object": "chat.completion.chunk",
                    "created": payload["created"], "model": payload["model"],
                    "choices": [{"index": 0, "delta": {
                        "role": "assistant",
                        "content": payload["choices"][0]["message"].get("content") or ""},
                        "finish_reason": payload["choices"][0]["finish_reason"]}],
                }
                data = f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n".encode()
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self._send(200, _openai_completion(body))
            return
        if path.endswith("/messages"):
            self._send(200, _anthropic_message(body))
            return
        # OAuth controlled-provider token endpoint: /<provider>/token
        parts = [p for p in path.split("/") if p]
        if len(parts) == 2 and parts[1] == "token":
            provider = parts[0]
            self._send(200, {
                "access_token": f"mock-{provider}-access-{uuid.uuid4().hex[:10]}",
                "refresh_token": f"mock-{provider}-refresh-{uuid.uuid4().hex[:10]}",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "mockScope",
            })
            return
        self._send(404, {"error": {"message": "not found"}})


class Server:
    def __init__(self, port: int = 59997):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self) -> "Server":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    @property
    def base_url(self) -> str:
        host, port = self.httpd.server_address
        return f"http://{host}:{port}/v1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=59997)
    parser.add_argument("--record", type=Path)
    args = parser.parse_args()
    server = Server(args.port).start()
    print(server.base_url, flush=True)
    try:
        while True:
            time.sleep(1)
            if args.record:
                args.record.write_text(json.dumps(calls(), indent=2) + "\n")
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
