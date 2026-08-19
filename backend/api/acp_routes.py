"""
ACP (Agent Client Protocol) bridge — standard-agent interoperability.

Implements the ACP v1 baseline (JSON-RPC 2.0) over an authenticated
WebSocket so standard ACP clients (Zed, Berd-style desktop shells, any
agent-client that speaks the protocol) can drive Atom agents without
first-party tooling.

Methods implemented (client → agent):
  - initialize            → versions + capabilities handshake
  - session/new           → creates a chat session (sessionId)
  - session/load          → resume an existing session (loadSession: true)
  - session/prompt        → runs a turn through the ChatOrchestrator and
                            streams session/update notifications
                            (agent_message_chunk) before the stopReason
  - session/cancel (nfn)  → cancels the active turn

Not yet emitted (agent → client): session/request_permission — Atom's
HITL pauses are resolved through the approvals queue instead. Tool-call
and plan updates are not streamed in this first slice (single
agent_message_chunk per turn); the wire shapes follow the spec so later
slices are additive.

Wire conventions per spec: JSON keys camelCase; discriminator values
snake_case. Connect: ws://host/acp/ws?token=<jwt>
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.database import SessionLocal
from core.auth import get_current_user_ws

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ACP"])

ACP_PROTOCOL_VERSION = 1
_JSONRPC = "2.0"

# In-flight turns by session, so session/cancel can reach the orchestrator
_active_turns: Dict[str, asyncio.Task] = {}


def _result(req_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": _JSONRPC, "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": _JSONRPC, "id": req_id, "error": {"code": code, "message": message}}


def _update_notification(session_id: str, update: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "jsonrpc": _JSONRPC,
        "method": "session/update",
        "params": {"sessionId": session_id, "update": update},
    }


def _text_block(text: str) -> Dict[str, Any]:
    return {"type": "text", "text": text}


@router.websocket("/acp/ws")
async def acp_websocket(websocket: WebSocket):
    """Authenticated ACP v1 endpoint. JWT via ?token= like the platform WS."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return
    db = SessionLocal()
    try:
        user = await get_current_user_ws(token, db)
    finally:
        db.close()
    if user is None:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    await websocket.accept()
    session_id: Optional[str] = None

    async def send(msg: Dict[str, Any]) -> None:
        await websocket.send_json(msg)

    try:
        while True:
            raw = await websocket.receive_json()
            req_id = raw.get("id")
            method = raw.get("method", "")

            if method == "initialize":
                await send(_result(req_id, {
                    "protocolVersion": ACP_PROTOCOL_VERSION,
                    "agentInfo": {"name": "Atom", "title": "Atom Agent Workforce", "version": "1.0-acp"},
                    "agentCapabilities": {
                        "loadSession": True,
                        "promptCapabilities": {"image": False, "audio": False, "embeddedContext": False},
                        "mcpCapabilities": {"http": True, "sse": False},
                    },
                    "authMethods": [],
                }))

            elif method == "session/new":
                session_id = str(uuid.uuid4())
                await send(_result(req_id, {
                    "sessionId": session_id,
                    "modes": None,
                    "configOptions": None,
                }))

            elif method == "session/load":
                requested = (raw.get("params") or {}).get("sessionId")
                session_id = requested or session_id or str(uuid.uuid4())
                await send(_result(req_id, {
                    "sessionId": session_id,
                    "modes": None,
                    "configOptions": None,
                }))

            elif method == "session/prompt":
                params = raw.get("params") or {}
                sid = params.get("sessionId") or session_id
                prompt_blocks = params.get("prompt") or []
                text = " ".join(
                    b.get("text", "") for b in prompt_blocks if b.get("type") == "text"
                ).strip()
                if not sid or not text:
                    await send(_error(req_id, -32602, "sessionId and a text prompt are required"))
                    continue
                session_id = sid

                async def _run_turn() -> Dict[str, Any]:
                    from integrations.chat_orchestrator import ChatOrchestrator

                    orchestrator = ChatOrchestrator(tenant_id="default")
                    return await orchestrator.process_chat_message(
                        user_id=str(user.id), message=text, session_id=sid
                    )

                task = asyncio.create_task(_run_turn())
                _active_turns[sid] = task
                try:
                    response = await task
                finally:
                    _active_turns.pop(sid, None)

                message = response.get("message") or ""
                # Stream the answer as spec-shaped chunks (single chunk in
                # this slice; token-level chunking is additive later).
                await send(_update_notification(sid, {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": message},
                }))
                await send(_result(req_id, {"stopReason": "end_turn"}))

            elif method == "session/cancel":
                sid = (raw.get("params") or {}).get("sessionId") or session_id
                if sid and sid in _active_turns:
                    _active_turns[sid].cancel()
                # Notification — no response.

            else:
                await send(_error(req_id, -32601, f"Method not found: {method}"))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"ACP bridge error: {e}")
        try:
            await websocket.close()
        except Exception:
            pass
