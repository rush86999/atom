"""MCP (Model Context Protocol) server for atom's LLM routing layer.

Exposes atom's routing, compression, governance, and health controls as MCP
tools so external AI agents (Claude Code, Cursor, etc.) can manage atom
autonomously.

Evidence basis: MCP adoption is at 41% production (Stacklok 2026), 28%
Fortune 500, top-5 priority for ~50% of enterprises. 56 production servers
span network automation, enterprise app integration, and infrastructure.
MCP is a protocol, not a data-mutation layer — no business-data risk.

Transport: HTTP+SSE with JSON-RPC 2.0 (hand-rolled, no external SDK).
Mounts at /mcp alongside the gateway in main_api_app.py.

See docs/architecture/MCP_SERVER.md.
"""
from __future__ import annotations

import os

# Default ON per user decision.
MCP_SERVER_ENABLED: bool = os.getenv("MCP_SERVER_ENABLED", "true").lower() == "true"

# Protocol version we advertise in the initialize handshake.
MCP_PROTOCOL_VERSION = "2026-07-28"

# Server identity.
MCP_SERVER_NAME = "atom-mcp-server"
MCP_SERVER_VERSION = "1.0.0"
