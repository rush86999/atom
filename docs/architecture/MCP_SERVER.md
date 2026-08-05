# MCP Server

Atom exposes its LLM routing, compression, governance, and health controls as [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) tools, so external AI agents (Claude Code, Cursor, Cline, etc.) can manage atom autonomously.

> **Host vs Client (P6).** This document covers Atom as an MCP **host** (the
> outbound `/mcp` surface external agents call *into*). Atom is ALSO an MCP
> **client** — it can connect TO arbitrary external MCP servers (Cloudflare
> "MCP Server Portals") via `core/mcp_client.py` + `POST /api/mcp/servers`.
> See [External MCP Client (P6)](#external-mcp-client-p6) below.

## Evidence basis

- [Stacklok 2026 report](https://stacklok.com/wp-content/uploads/2026/01/State-of-MCP-in-Software-2026_FINAL.pdf): 41% production adoption, top-5 priority for ~50% of enterprises
- [CData](https://www.cdata.com/blog/2026-year-enterprise-ready-mcp-adoption): enterprise AI integration standard beyond coding
- [Itential](https://www.itential.com/resource/blog/mcp-101-understanding-the-model-context-protocol/): 56 production servers across network/infra
- MCP is a protocol, not a data-mutation layer — no business-data risk

## Transport

HTTP+SSE with JSON-RPC 2.0. Mounted at `/mcp` alongside the LLM gateway. No external MCP SDK dependency (hand-rolled JSON-RPC).

- `POST /mcp/` — JSON-RPC request/response (primary endpoint)
- `GET /mcp/sse` — SSE stream for server-push notifications

## Protocol methods

`initialize`, `tools/list`, `tools/call`, `ping`

## Tools

| Tool | Description |
|------|-------------|
| `resolve_route` | Dry-run routing: show which model+provider atom would pick for a prompt |
| `list_models` | Available models with quality/cost/capability metadata |
| `compress_text` | Compress terminal/tool output via RTK engine (shows savings metrics) |
| `set_compression` | Toggle token compression on/off |
| `get_spend` | Query current spend against budget |
| `get_health` | Provider health status and circuit breaker states |
| `fusion_generate` | Run a fusion (panel+judge) generation for high-stakes tasks |

## Usage

```bash
# Initialize handshake
curl -X POST https://your-atom/mcp/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'

# List tools
curl -X POST https://your-atom/mcp/ \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

# Call a tool
curl -X POST https://your-atom/mcp/ \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"resolve_route","arguments":{"prompt":"debug this function"}}}'
```

## Configuration

| Env var | Default | Effect |
|---------|---------|--------|
| `MCP_SERVER_ENABLED` | `true` | Enable/disable the MCP server |

## File layout

- `api/mcp_server_routes.py` — FastAPI router (HTTP+SSE endpoints)
- `core/mcp_server/handler.py` — JSON-RPC protocol handler
- `core/mcp_server/tools.py` — tool definitions + handler functions
- `core/mcp_server/__init__.py` — configuration + constants

---

## External MCP Client (P6)

In addition to hosting the `/mcp` server above, Atom can **connect to arbitrary
external MCP servers** as a client (Cloudflare "MCP Server Portals" equivalent) —
not just the 3 hardcoded pseudo-servers (`google-search`, `local-tools`,
`brightdata`).

### Transport

JSON-RPC 2.0 over **HTTP+SSE** (primary) or **stdio** (subprocess), hand-rolled
over `httpx`/`subprocess` (no external MCP SDK dependency — consistent with the
hand-rolled host above). The client speaks `initialize` → `tools/list` →
`tools/call`, mirroring the wire format the host handler produces.

### Registration + connection

Admins register an external server via the config surface; Atom performs the
handshake, fetches `tools/list`, and caches the live client + tool definitions:

```
POST /api/mcp/servers        { "name": "my-portal", "transport": "http", "url": "https://..." }
GET  /api/mcp/servers        -> list connected servers + tool counts
DELETE /api/mcp/servers/{id} -> disconnect
```

`core/mcp_service.register_server` (previously never called — the handshake was
a `# Placeholder`) now actually connects via `core/mcp_client.MCPClient` and
populates `tools_cache` + `external_clients`. Registered external tools are then
dispatchable through the same `integrations/mcp_service.call_tool` path as
native tools (after the action registry + capability/sandbox gates).

### File layout

- `core/mcp_client.py` — `MCPClient` (JSON-RPC transport, `initialize`/`list_tools`/`call_tool`)
- `core/mcp_service.py` — `MCPService` hub (`register_server`, `refresh_tools`, `call_external_tool`)
- `api/mcp_client_routes.py` — admin config router (`/api/mcp/servers`)

External tools are gated identically to local tools: they pass through the
capability gate (P2), the shared sandbox gate (P9), and the R67 critical-tool
`WORKFLOW_MANAGE` gate (`core/workflow_security.require_critical_tool`).
