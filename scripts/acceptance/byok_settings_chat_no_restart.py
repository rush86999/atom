#!/usr/bin/env python3
"""Settings -> save BYOK key -> Chat, with NO process restart.

Uses the real FastAPI app and the same `/api/ai/providers/{id}/keys` route the
Settings UI calls, then posts a normal `/api/chat/message` turn. A bounded
local OpenAI-compatible server records the Authorization header so the test can
prove the cached chat handler rebuilt on save, replacement and removal. Key
values are never printed or persisted in evidence.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import logging
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.mkdtemp(prefix="atom-byok-settings-chat-"))
PORT = 59998
KEY_ONE = "sk-byok-refresh-first-1234567890"
KEY_TWO = "sk-byok-refresh-second-0987654321"


class Recorder(BaseHTTPRequestHandler):
    calls: list[str] = []
    auth_hashes: list[str] = []
    requests: list[dict] = []

    def log_message(self, *_args):
        return

    def _json(self, payload: dict, status: int = 200):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            # Advertise the provider's real model catalogue. The chat probe
            # deliberately does NOT pin a model: the normal router must pick a
            # model this provider actually serves.
            self._json({"object": "list", "data": [
                {"id": "gpt-4o-mini"},
                {"id": "gpt-5.6-luna-pro"},
                {"id": "gpt-5.6-luna"},
                {"id": "gpt-5.4-nano"},
                {"id": "gpt-5.4-mini"},
                {"id": "gpt-5.1"},
                {"id": "o3-mini"},
                {"id": "o4-mini"},
            ]})
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self.path.rstrip("/").endswith("/chat/completions"):
            self._json({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw or b"{}")
        except Exception:
            body = {}
        auth = str(self.headers.get("Authorization") or "")
        Recorder.calls.append(auth)
        Recorder.auth_hashes.append(hashlib.sha256(auth.encode()).hexdigest())
        Recorder.requests.append({
            "model": body.get("model"),
            "stream": bool(body.get("stream")),
            "has_tools": bool(body.get("tools")),
            "response_format": str(body.get("response_format") or "")[:80],
            "messages": len(body.get("messages") or []),
            "tool_names": [
                (t.get("function") or {}).get("name")
                for t in (body.get("tools") or [])[:3]
                if isinstance(t, dict)
            ],
            "tool_schema": (
                ((body.get("tools") or [{}])[0].get("function") or {}).get("parameters")
                if body.get("tools") else None
            ),
        })
        requested_model = str(body.get("model") or "gpt-4o-mini")
        planning = bool(body.get("tools")) or bool(body.get("response_format"))
        if planning:
            tool = (body.get("tools") or [{}])[0]
            function = (tool.get("function") or {}) if isinstance(tool, dict) else {}
            name = function.get("name") or "_Interpretation"
            arguments = json.dumps({
                "actions": [{
                    "kind": "conversation",
                    "subjects": [],
                    "note": "direct reply",
                }],
                "constraints": [],
                "requested_fields": [],
                "scope_change": "continue",
                "sources": [],
                "subjects": [],
            })
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_byok_refresh",
                    "type": "function",
                    "function": {"name": name, "arguments": arguments},
                }],
            }
            finish_reason = "tool_calls"
        else:
            message = {"role": "assistant", "content": "BYOK refresh OK"}
            finish_reason = "stop"
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            chunk = {
                "id": "chatcmpl-byok-refresh",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": requested_model,
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant", "content": "BYOK refresh OK"},
                    "finish_reason": None,
                }],
            }
            done = {
                "id": "chatcmpl-byok-refresh",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": requested_model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }],
            }
            self.wfile.write(
                f"data: {json.dumps(chunk)}\n\ndata: {json.dumps(done)}\n\ndata: [DONE]\n\n".encode())
            self.wfile.flush()
            self.close_connection = True
            return
        self._json({
            "id": "chatcmpl-byok-refresh",
            "object": "chat.completion",
            "created": 1,
            "model": "gpt-4o-mini",
            "choices": [{
                "index": 0,
                "message": message,
                "finish_reason": finish_reason,
            }],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                      "total_tokens": 2},
        })


def main() -> int:
    for name in (
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
        "OPENROUTER_API_KEY", "GOOGLE_API_KEY", "OPENCODE_API_KEY",
    ):
        os.environ.pop(name, None)
    os.environ.update({
        "TESTING": "1",
        "ADMIN_PASSWORD": "byok-settings-chat-pass",
        "SECRET_KEY": "byok-settings-chat-secret",
        "DATABASE_URL": f"sqlite:///{TMP}/atom.db",
        "ATOM_DATA_DIR": str(TMP / "data"),
        "LANCEDB_URI": str(TMP / "data" / "atom_memory"),
        "ATOM_OFFICE_DIR": str(TMP / "data" / "office"),
        "BYOK_KEYS_FILE": str(TMP / "byok_keys.json"),
        "BYOK_CONFIG_FILE": str(TMP / "byok_config.json"),
        "BYOK_ENC_KEY_FILE": str(TMP / "byok_encryption_key"),
        "OPENAI_BASE_URL": f"http://127.0.0.1:{PORT}/v1",
        "ATOM_LOCAL_ONLY": "false",
        "ATOM_PRODUCT_PROFILE": "core",
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        # The optional tool planner is not the subject of this probe; the
        # Settings->Chat BYOK path is. Keep the turn on the normal chat route
        # without a tool-planning detour.
    })
    (TMP / "data").mkdir(parents=True, exist_ok=True)

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Recorder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    log_buffer = io.StringIO()
    handler = logging.StreamHandler(log_buffer)
    handler.setLevel(logging.DEBUG)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    old_level = root_logger.level
    root_logger.setLevel(logging.INFO)

    try:
        sys.path.insert(0, str(ROOT / "backend"))
        from fastapi.testclient import TestClient
        from main_api_app import app

        with TestClient(app) as client:
            login = client.post("/api/auth/login", json={
                "username": "admin@example.com",
                "password": "byok-settings-chat-pass",
            })
            if login.status_code != 200:
                raise SystemExit(f"login failed: {login.status_code} {login.text[:300]}")
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            def save(key: str):
                res = client.post(
                    "/api/ai/providers/openai/keys",
                    json={"api_key": key, "key_name": "default"},
                    headers=headers,
                )
                if res.status_code >= 300:
                    raise SystemExit(f"save failed: {res.status_code} {res.text[:300]}")

            def chat(session: str, message: str):
                res = client.post("/api/chat/message", json={
                    "message": message,
                    "user_id": "admin",
                    "session_id": session,
                }, headers=chat_headers())
                return res

            PIN = (os.environ.get("BYOK_PROBE_PIN") or "").strip()

            def chat_headers():
                # The journey must work on normal routing. A pin exists only as
                # an explicit diagnostic override, never as the acceptance path.
                return ({**headers, "x-atom-model": PIN} if PIN else dict(headers))

            from integrations.chat_orchestrator import chat_orchestrator
            from integrations.chat_routes import chat_orchestrator as route_orchestrator

            def handler_state(orch=chat_orchestrator):
                handler = orch.llm_service._get_handler()
                client_obj = getattr(handler, "clients", {}).get("openai")
                return {
                    "handler_id": id(handler),
                    "has_openai": client_obj is not None,
                    "key_is_first": getattr(client_obj, "api_key", None) == KEY_ONE,
                    "key_is_second": getattr(client_obj, "api_key", None) == KEY_TWO,
                }

            before = handler_state()
            save(KEY_ONE)
            after_first_save = handler_state()
            route_after_first = handler_state(route_orchestrator)
            first = chat("byok-settings-chat-1", "Hello")
            first_calls = len(Recorder.calls)

            save(KEY_TWO)
            after_second_save = handler_state()
            route_after_second = handler_state(route_orchestrator)
            second = chat("byok-settings-chat-2", "Hello again")
            second_calls = len(Recorder.calls)

            removed = client.delete(
                "/api/ai/providers/openai/keys/default", headers=headers)
            after_removal = handler_state()
            third = chat("byok-settings-chat-3", "Goodbye")
            third_calls = len(Recorder.calls)

        first_auth = Recorder.calls[0] if Recorder.calls else ""
        second_auth = (
            Recorder.calls[first_calls]
            if len(Recorder.calls) > first_calls else "")
        log_text = log_buffer.getvalue()
        result = {
            "schema": "atom-byok-settings-chat-no-restart-1",
            "status": "passed",
            "first_chat_http": first.status_code,
            "second_chat_http": second.status_code,
            "third_chat_http": third.status_code,
            "delete_http": removed.status_code,
            "provider_calls_after_first": first_calls,
            "provider_calls_after_replacement": second_calls,
            "provider_calls_after_removal": third_calls,
            "first_key_seen": first_auth.endswith(KEY_ONE),
            "replacement_key_seen": second_auth.endswith(KEY_TWO),
            "removed_key_not_resent": third_calls == second_calls,
            "keys_absent_from_logs": (
                KEY_ONE not in log_text and KEY_TWO not in log_text),
            "log_chars": len(log_text),
            "handler_before": before,
            "handler_after_first_save": after_first_save,
            "handler_after_second_save": after_second_save,
            "handler_after_removal": after_removal,
            "route_handler_after_first_save": route_after_first,
            "route_handler_after_second_save": route_after_second,
            "first_payload_keys": sorted(first.json().keys()),
            "first_message": str(
                first.json().get("message")
                or first.json().get("content")
                or first.json().get("response")
                or "")[:300],
            "second_message": str(
                second.json().get("message")
                or second.json().get("content")
                or second.json().get("response")
                or "")[:300],
            "third_message": str(
                third.json().get("message")
                or third.json().get("content")
                or third.json().get("response")
                or "")[:300],
            "first_meta": {
                "outcome": first.json().get("outcome"),
                "error_code": first.json().get("error_code"),
                "failure_reason": str(first.json().get("failure_reason") or "")[:300],
                "model": first.json().get("model"),
                "provider": first.json().get("provider"),
                "metadata_keys": sorted((first.json().get("metadata") or {}).keys())[:30],
            },
            "second_meta": {
                "outcome": second.json().get("outcome"),
                "error_code": second.json().get("error_code"),
                "failure_reason": str(second.json().get("failure_reason") or "")[:300],
                "model": second.json().get("model"),
                "provider": second.json().get("provider"),
            },
            "request_models": [r.get("model") for r in Recorder.requests[:8]],
            "request_streams": [r.get("stream") for r in Recorder.requests[:8]],
            "request_tools": [r.get("has_tools") for r in Recorder.requests[:8]],
            "request_tool_names": [r.get("tool_names") for r in Recorder.requests[:8]],
            "first_tool_schema": Recorder.requests[0].get("tool_schema") if Recorder.requests else None,
        }
        passed = (
            first.status_code == 200
            and second.status_code == 200
            and removed.status_code < 300
            and first_calls >= 1
            and second_calls > first_calls
            and result["first_key_seen"]
            and result["replacement_key_seen"]
            and result["removed_key_not_resent"]
            and result["keys_absent_from_logs"]
        )
        result["status"] = "passed" if passed else "failed"
        out = Path(os.environ.get("BYOK_EVIDENCE_OUT") or (TMP / "result.json"))
        out.parent.mkdir(parents=True, exist_ok=True)
        safe_log = log_text.replace(KEY_ONE, "<redacted>").replace(KEY_TWO, "<redacted>")
        (out.parent / "app.log").write_text(safe_log[-2_000_000:])
        out.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return 0 if passed else 1
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(old_level)
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
