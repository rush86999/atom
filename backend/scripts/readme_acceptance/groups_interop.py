"""Interoperability scenarios: MCP client, A2A, ACP, tracing."""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .common import Ctx


def interop(ctx: Ctx) -> None:
    # ---- IO-01 register an external MCP server + tools/list ------------
    register = ctx.post("/api/mcp/servers", json={
        "name": "acceptance-mcp",
        "transport": "http",
        "url": "http://127.0.0.1:59997/mcp",
        "headers": {"X-Acceptance": "1"},
    })
    rbody = register.json() if register.headers.get("content-type", "").startswith("application/json") else {}
    server_id = (rbody.get("server_id") or (rbody.get("data") or {}).get("server_id")
                 or rbody.get("id") or "acceptance-mcp")
    listed = ctx.get("/api/mcp/servers")
    lbody = listed.json() if listed.status_code == 200 else {}
    servers = lbody.get("data") if isinstance(lbody, dict) else lbody
    found = None
    if isinstance(servers, list):
        found = next((s for s in servers if s.get("server_id") == server_id), None)
    tools = ctx.get(f"/api/mcp/servers/{server_id}/tools")
    tbody = tools.json() if tools.status_code == 200 else {}
    tools_text = json.dumps(tbody)
    ok = (register.status_code == 200 and found is not None
          and (found.get("tool_count") or 0) >= 1)
    ctx.record("IO-01", "verified" if ok else "failed",
               [ctx.save("interop/mcp_register.json", {
                   "register": {"status": register.status_code, "body": rbody},
                   "servers": {"status": listed.status_code, "body": servers},
                   "tools": {"status": tools.status_code, "body": tbody}})],
               notes=f"server={server_id} listed={found is not None} "
                     f"tool_count={(found or {}).get('tool_count')}")

    # ---- IO-02 execute the discovered MCP tool -------------------------
    execute = ctx.post("/api/mcp/execute", json={
        "server_id": server_id, "tool_name": "echo",
        "arguments": {"text": "acceptance-echo-123"}})
    ebody = execute.json() if execute.headers.get("content-type", "").startswith("application/json") else {}
    ok = execute.status_code == 200 and "acceptance-echo-123" in json.dumps(ebody)
    ctx.record("IO-02", "verified" if ok else "partial",
               [ctx.save("interop/mcp_execute.json", {
                   "status": execute.status_code, "body": ebody})],
               notes=f"execute={execute.status_code} result_echoed={ok}")

    # ---- IO-03 A2A agent card -----------------------------------------
    card = ctx.client.get("/api/a2a/agent-card")
    cbody = card.json() if card.status_code == 200 else {}
    wellknown = ctx.client.get("/.well-known/agent-card.json")
    ok = (card.status_code == 200 and cbody.get("skills")
          and wellknown.status_code == 200)
    ctx.record("IO-03", "verified" if ok else "failed",
               [ctx.save("interop/a2a_card.json", {
                   "card": {"status": card.status_code, "body": cbody},
                   "well_known": {"status": wellknown.status_code}})],
               notes=f"skills={len(cbody.get('skills') or [])}")

    # ---- IO-04 A2A message/send ---------------------------------------
    send = ctx.client.post("/api/a2a", headers=ctx.headers, json={
        "jsonrpc": "2.0", "id": "acc-1", "method": "message/send",
        "params": {"message": {"role": "user", "parts": [
            {"kind": "text", "text": "acceptance greeting"}]}}})
    sbody = send.json() if send.headers.get("content-type", "").startswith("application/json") else {}
    unauthorized = ctx.client.post("/api/a2a", json={
        "jsonrpc": "2.0", "id": "acc-2", "method": "message/send",
        "params": {}})
    method_error = ctx.client.post("/api/a2a", headers=ctx.headers, json={
        "jsonrpc": "2.0", "id": "acc-3", "method": "not/a/method", "params": {}})
    ok = (send.status_code == 200 and "result" in sbody
          and unauthorized.status_code in (401, 403)
          and method_error.json().get("error", {}).get("code") == -32601)
    ctx.record("IO-04", "verified" if ok else "partial",
               [ctx.save("interop/a2a_send.json", {
                   "send": {"status": send.status_code, "body": sbody},
                   "unauthorized": unauthorized.status_code,
                   "method_error": method_error.json()})],
               notes=f"send={send.status_code} result={'result' in sbody} "
                     f"unauth={unauthorized.status_code}")

    # ---- IO-05 ACP handshake + prompt/reply ---------------------------
    try:
        with ctx.client.websocket_connect(f"/acp/ws?token={ctx.token}") as ws:
            ws.send_json({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                          "params": {"protocolVersion": 1,
                                     "clientCapabilities": {}}})
            init = ws.receive_json()
            ws.send_json({"jsonrpc": "2.0", "id": 2, "method": "session/new",
                          "params": {"cwd": "/acceptance", "mcpServers": []}})
            new = ws.receive_json()
            session_id = (new.get("result") or {}).get("sessionId")
            updates = []
            prompt_result = None
            if session_id:
                ws.send_json({
                    "jsonrpc": "2.0", "id": 3, "method": "session/prompt",
                    "params": {"sessionId": session_id, "prompt": [
                        {"type": "text", "text": "Reply with the word acceptance."}]},
                })
                # One session/update notification, then the JSON-RPC result.
                for _ in range(4):
                    msg = ws.receive_json()
                    if msg.get("method") == "session/update":
                        updates.append(msg)
                    elif msg.get("id") == 3:
                        prompt_result = msg
                        break
        delivered = any(
            (u.get("params") or {}).get("update", {}).get("sessionUpdate")
            == "agent_message_chunk" for u in updates)
        stop = ((prompt_result or {}).get("result") or {}).get("stopReason")
        ok = ("result" in init and "result" in new and delivered
              and stop == "end_turn")
        ctx.record("IO-05", "verified" if ok else "partial",
                   [ctx.save("interop/acp.json", {
                       "initialize": init, "session_new": new,
                       "updates": updates, "prompt_result": prompt_result})],
                   notes=f"initialize={'result' in init} session/new={'result' in new} "
                         f"agent_chunk={delivered} stopReason={stop}")
    except Exception as exc:
        ctx.record("IO-05", "failed",
                   [ctx.save("interop/acp.json", {"error": str(exc)})],
                   notes=f"ACP session/prompt failed: {exc}")

    # ---- IO-06 request-level span + optional local export --------------
    io06_error = None
    request_spans = []
    collector_body = None
    export_recorded = []
    try:
        from core.observability.tracing import (
            clear_spans, get_recent_spans, langfuse_configured)

        clear_spans()
        key_resp = ctx.post("/api/gateway/keys", json={
            "name": f"trace-{uuid.uuid4().hex[:6]}",
            "rate_limit_per_minute": 60})
        key_body = (key_resp.json()
                    if key_resp.status_code in (200, 201) else {})
        gateway_key = key_body.get("key")
        call = (ctx.client.post("/v1/chat/completions", headers={
            "Authorization": f"Bearer {gateway_key}"}, json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "trace acceptance"}],
            }) if gateway_key else None)
        status = ctx.get("/api/observability/spans",
                         params={"name_prefix": "llm.gateway.request"})
        status_body = status.json() if status.status_code == 200 else {}
        request_spans = status_body.get("spans") or []
        status_flag = ctx.get("/api/observability/status")
        status_flag_body = status_flag.json() if status_flag.status_code == 200 else {}

        class _Collector(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def do_POST(self):
                length = int(self.headers.get("content-length") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    export_recorded.append(json.loads(raw.decode() or "{}"))
                except Exception:
                    export_recorded.append({"_raw": raw[:500].decode("latin1")})
                payload = b'{"ok":true}'
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        collector = ThreadingHTTPServer(("127.0.0.1", 0), _Collector)
        thread = threading.Thread(target=collector.serve_forever, daemon=True)
        thread.start()
        collector_port = collector.server_address[1]
        old_env = {k: os.environ.get(k) for k in (
            "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")}
        os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-acceptance"
        os.environ["LANGFUSE_SECRET_KEY"] = "sk-acceptance"
        os.environ["LANGFUSE_HOST"] = f"http://127.0.0.1:{collector_port}"
        try:
            call2 = (ctx.client.post("/v1/chat/completions", headers={
                "Authorization": f"Bearer {gateway_key}"}, json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "trace export acceptance"}],
                }) if gateway_key else None)
            time.sleep(1.0)
            collector_body = export_recorded[-1] if export_recorded else None
        finally:
            collector.shutdown()
            collector.server_close()
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        span_names = [s.get("name") for s in request_spans]
        span_attrs = (request_spans[0].get("attributes") or {}) if request_spans else {}
        batch = (collector_body or {}).get("batch") or []
        batch_types = [event.get("type") for event in batch]
        io06_ok = (call is not None and call.status_code == 200
                   and request_spans
                   and "llm.gateway.request" in span_names
                   and span_attrs.get("model") == "gpt-4o-mini"
                   and "provider" in span_attrs and "status_code" in span_attrs
                   and status_flag.status_code == 200
                   and status_flag_body.get("langfuse_export", {}).get("configured") is False
                   and call2 is not None and call2.status_code == 200
                   and collector_body is not None
                   and "trace-create" in batch_types
                   and "span-create" in batch_types
                   and "sk-acceptance" not in json.dumps(collector_body))
        ctx.record("IO-06", "verified" if io06_ok else "failed",
                   [ctx.save("interop/tracing.json", {
                       "controlled_collector": True,
                       "request": None if call is None else call.status_code,
                       "export_request": None if call2 is None else call2.status_code,
                       "spans": request_spans,
                       "observability_status": status_flag_body,
                       "collector_batch_types": batch_types,
                       "collector_received": collector_body is not None,
                       "error": io06_error,
                   })],
                   notes=f"request={None if call is None else call.status_code} "
                         f"spans={len(request_spans)} "
                         f"export={None if call2 is None else call2.status_code} "
                         f"batch_types={batch_types} "
                         f"error={io06_error}")
    except Exception as exc:
        import traceback as _tb
        io06_error = f"{type(exc).__name__}: {exc}"
        ctx.save("interop/tracing_error.txt", _tb.format_exc())
        ctx.record("IO-06", "failed", notes=f"tracer unavailable: {io06_error}")
