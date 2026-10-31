"""Interoperability scenarios: MCP client, A2A, ACP, tracing."""
from __future__ import annotations

import json
import time

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

    # ---- IO-05 ACP handshake over WebSocket ---------------------------
    try:
        with ctx.client.websocket_connect(f"/acp/ws?token={ctx.token}") as ws:
            ws.send_json({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                          "params": {"protocolVersion": 1,
                                     "clientCapabilities": {}}})
            init = ws.receive_json()
            ws.send_json({"jsonrpc": "2.0", "id": 2, "method": "session/new",
                          "params": {"cwd": "/acceptance", "mcpServers": []}})
            new = ws.receive_json()
        ok = "result" in init and "result" in new
        ctx.record("IO-05", "verified" if ok else "partial",
                   [ctx.save("interop/acp.json", {"initialize": init, "session_new": new})],
                   notes=f"initialize={'result' in init} session/new={'result' in new}")
    except Exception as exc:
        ctx.record("IO-05", "failed",
                   [ctx.save("interop/acp.json", {"error": str(exc)})],
                   notes=f"ACP handshake failed: {exc}")

    # ---- IO-06 span tracing -------------------------------------------
    try:
        from core.observability.tracing import (
            record_span, get_recent_spans, langfuse_configured)
        record_span(
            trace_id="acceptance-trace-123",
            name="acceptance-span", kind="internal",
            attributes={"acceptance": True},
            started_at=time.time(), ended_at=time.time(), status="ok",
        )
        spans = get_recent_spans(limit=20, name_prefix="acceptance-span")
        ctx.record("IO-06", "verified" if spans else "partial",
                   [ctx.save("interop/tracing.json", {
                       "spans": spans[-3:], "langfuse_configured": langfuse_configured()})],
                   notes=f"spans={len(spans)}; Langfuse export is optional and "
                         f"{'configured' if langfuse_configured() else 'off'}")
    except Exception as exc:
        ctx.record("IO-06", "unverified", notes=f"tracer unavailable: {exc}")
