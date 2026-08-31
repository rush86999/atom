"""
RPC routes — P1 (Cloudflare OS foundation).

Exposes the unified action registry (``core.action_registry``) to the frontend
via a single ``POST /api/rpc/{action_name}`` endpoint. The frontend RPC client
(``frontend-nextjs/lib/rpc-client.ts``) calls this instead of bespoke per-feature
endpoints, giving a single enforcement point for capability gating (P2),
gatekeeper checks (P3), and sandbox enforcement (P9).

Auth: all routes require ``get_current_user`` (Bearer or NextAuth session).
The router declares its own ``/api`` prefix, so it is included BARE in
``main_api_app.py`` (mirroring the agent_routes.py pattern noted at L1366-1370).
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.action_registry import ActionNotFoundError, action_registry
from core.auth import User, get_current_user
from core.database import get_db
# Importing radio_actions registers the 3 `radio.*` actions via @register_action
# (side effect at import). Kept here so the radio surface loads with the RPC
# router and gets the same P2 capability + P9 sandbox gates as every action.
from core.agent_radio import radio_actions  # noqa: F401
# Importing bpe.actions registers the 4 `workspace.*` meta-actions via
# @register_action (side effect at import). Tool visibility is flag-gated in
# mcp_service.get_all_tools (ATOM_BPE_WORKSPACE_ENABLED, default ON).
from core.bpe import actions as bpe_actions  # noqa: F401

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["rpc"])


class RpcCallRequest(BaseModel):
    """Body for POST /api/rpc/{action_name}."""
    # Allow any keyword arguments for the action. Using a model with a single
    # ``params`` field (rather than **kwargs) keeps the wire format explicit and
    # survives FastAPI's body parsing for arbitrary shapes.
    params: Dict[str, Any] = {}


class RpcActionSummary(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]


@router.get("/rpc/actions")
async def list_actions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all registered actions available over RPC."""
    actions = [
        RpcActionSummary(
            name=a.name,
            description=a.description,
            parameters=a.parameters_schema,
        ).model_dump()
        for a in action_registry.get_all_definitions()
    ]
    return {"success": True, "data": actions, "count": len(actions)}


@router.post("/rpc/{action_name}")
async def call_action(
    action_name: str,
    body: RpcCallRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute a registered action by name.

    Returns 404 for unknown actions, 401 for unauthenticated callers.
    """
    action = action_registry.get_action(action_name)
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action '{action_name}' is not registered",
        )

    # Build the dispatch context. The authenticated user is the authoritative
    # actor — do NOT trust a user_id in ``body.params`` (R54 workspace-identity
    # fix principle).
    context: Dict[str, Any] = {
        "user": current_user,
        "user_id": str(current_user.id) if current_user.id else None,
        "db": db,
    }

    try:
        result = await action_registry.execute_action(action_name, body.params, context)
    except ActionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action '{action_name}' is not registered",
        )
    except Exception as e:
        # Never leak exception detail to the client (CLAUDE.md error-handling rule).
        logger.error("RPC action %s failed: %s", action_name, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Action '{action_name}' failed",
        )

    return {"success": True, "data": result, "action": action_name}
