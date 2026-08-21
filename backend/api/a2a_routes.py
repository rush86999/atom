"""
A2A (Agent2Agent) protocol bridge — agent-to-agent interoperability.

Implements the A2A baseline (JSON-RPC 2.0 over HTTP) so remote agents can
discover Atom via an Agent Card and exchange messages without first-party
tooling. Mirrors the conventions of the ACP bridge (api/acp_routes.py):
same JWT auth (Authorization: Bearer or ?token=), same ChatOrchestrator
execution path, camelCase wire keys.

Endpoints:
  - GET /.well-known/agent-card.json  (alias: GET /api/a2a/agent-card)
      Public Agent Card per the A2A spec shape.
  - POST /api/a2a
      JSON-RPC 2.0 endpoint. Supported method: message/send.
      Responses use the standard JSON-RPC envelope; errors:
        -32700 parse error, -32601 method not found,
        -32602 invalid params, -32001 unauthenticated (HTTP 401),
        -32002 rate limited (HTTP 429).
"""

import logging
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from core.database import SessionLocal
from core.auth import get_current_user_ws

logger = logging.getLogger(__name__)
router = APIRouter(tags=["A2A"])

_JSONRPC = "2.0"

A2A_VERSION = "1.0-a2a"

# Static capability domains (the agent_registry DB is not cheaply listable
# per-request for a public card; keep this small and descriptive).
_STATIC_SKILLS = [
    {
        "id": "chat",
        "name": "General Chat",
        "description": "Conversational access to Atom agents via the ChatOrchestrator.",
        "tags": ["chat", "conversation"],
    },
    {
        "id": "finance",
        "name": "Finance & Accounting",
        "description": "Accounting, invoicing and financial analysis capabilities.",
        "tags": ["finance", "accounting"],
    },
    {
        "id": "workflow",
        "name": "Workflow Automation",
        "description": "Create and drive automated multi-step workflows.",
        "tags": ["workflow", "automation"],
    },
    {
        "id": "analytics",
        "name": "Analytics & Reporting",
        "description": "Insights, metrics and reporting over platform data.",
        "tags": ["analytics", "reporting"],
    },
]

# --- Simple per-token in-memory rate limit (sliding window) -----------------
_RATE_LIMIT_MAX = 30          # requests
_RATE_LIMIT_WINDOW = 60.0     # seconds
_rate_buckets: Dict[str, list] = {}


def _rate_limited(token: str) -> bool:
    now = time.monotonic()
    bucket = [t for t in _rate_buckets.get(token, []) if now - t < _RATE_LIMIT_WINDOW]
    if len(bucket) >= _RATE_LIMIT_MAX:
        _rate_buckets[token] = bucket
        return True
    bucket.append(now)
    _rate_buckets[token] = bucket
    return False


def _result(req_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": _JSONRPC, "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": _JSONRPC, "id": req_id, "error": {"code": code, "message": message}}


def _build_agent_card(base_url: str) -> Dict[str, Any]:
    return {
        "name": "Atom",
        "description": "Atom Agent Workforce — multi-agent platform exposing chat, "
                       "finance, workflow and analytics capabilities over A2A.",
        "url": f"{base_url.rstrip('/')}/api/a2a",
        "version": A2A_VERSION,
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        },
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": _STATIC_SKILLS,
    }


@router.get("/.well-known/agent-card.json")
@router.get("/api/a2a/agent-card")
async def agent_card(request: Request):
    """Public Agent Card (A2A discovery)."""
    return _build_agent_card(str(request.base_url))


async def _extract_token(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip().strip('"')
    return request.query_params.get("token")


@router.post("/api/a2a")
async def a2a_endpoint(request: Request):
    """Authenticated A2A JSON-RPC 2.0 endpoint (message/send)."""
    token = await _extract_token(request)

    req_id = None
    body: Dict[str, Any] = {}
    if token is None:
        return JSONResponse(_error(None, -32001, "Unauthenticated"), status_code=401)

    # Authenticate with the same scheme the ACP bridge / platform WS use.
    db = SessionLocal()
    try:
        user = await get_current_user_ws(token, db)
    except Exception:
        user = None
    finally:
        db.close()
    if user is None:
        return JSONResponse(_error(None, -32001, "Unauthenticated"), status_code=401)

    if _rate_limited(token):
        return JSONResponse(
            _error(None, -32002, "Rate limit exceeded"), status_code=429
        )

    # Parse payload.
    raw = await request.body()
    try:
        import json

        body = json.loads(raw)
        req_id = body.get("id")
    except Exception:
        return _error(None, -32700, "Parse error")

    method = body.get("method", "")
    params = body.get("params") or {}

    if method == "message/send":
        message = params.get("message") or {}
        parts = message.get("parts") or []
        text = " ".join(
            p.get("text", "") for p in parts if p.get("kind") == "text"
        ).strip()
        if not text:
            return _error(req_id, -32602, "message with at least one text part is required")

        try:
            from integrations.chat_orchestrator import ChatOrchestrator

            orchestrator = ChatOrchestrator(tenant_id="default")
            response = await orchestrator.process_chat_message(
                user_id=str(user.id), message=text, session_id=str(uuid.uuid4())
            )
        except Exception as e:
            logger.warning(f"A2A execution error: {e}")
            return _error(req_id, -32603, f"Internal error: {e}")

        reply_text = response.get("message") or ""
        return _result(req_id, {
            "kind": "message",
            "messageId": str(uuid.uuid4()),
            "role": "agent",
            "parts": [{"kind": "text", "text": reply_text}],
            "contextId": message.get("contextId") or str(uuid.uuid4()),
        })

    return _error(req_id, -32601, "Method not found")
