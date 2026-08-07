"""Mini-app integration dispatcher — unified native/piece/MCP resolution.

The single engine that decides WHERE a ``fetch_integration(service, action,
params)`` call goes and HOW it executes. Reused by both the run-time callback
handler (``_make_callback_handler``) and the manifest pre-fetch
(``_inject_integration_sources``).

Resolution order (first hit wins):
  1. ``native`` — ``service`` is a registered connector in
     ``IntegrationRegistry.DEFAULT_SERVICE_REGISTRY`` (63 first-party services:
     Notion, HubSpot, Salesforce, Slack, …). Credentials from ``IntegrationToken``.
  2. ``piece`` — an Activepieces piece ``@activepieces/piece-{service}`` exists
     in the Node-bridge catalog. Same ``IntegrationToken`` creds, reshaped.
  3. ``mcp`` — a tool named ``{service}_{action}`` or ``{service}.{action}`` is
     registered on an external MCP server (``core/mcp_service``). Server-config-
     scoped auth (no per-call creds).
  4. ``None`` — not resolvable.

Credentials are ALWAYS resolved host-side; tokens never reach the microVM guest.
Failures are isolated (logged + skipped) so a single bad backend never crashes
a run.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Backend labels.
NATIVE = "native"
PIECE = "piece"
MCP = "mcp"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _to_piece_name(service: str) -> str:
    """Normalize a friendly service name to an Activepieces package name.

    ``"slack"`` → ``"@activepieces/piece-slack"``. Already-package-shaped names
    pass through unchanged.
    """
    if service.startswith("@activepieces/piece-"):
        return service
    return f"@activepieces/piece-{service}"


def _mcp_tool_candidates(service: str, action: str) -> Tuple[str, ...]:
    """Candidate MCP tool names for a (service, action) pair."""
    return (f"{service}_{action}", f"{service}.{action}", action)


# ---------------------------------------------------------------------------
# Resolution probes
# ---------------------------------------------------------------------------
def _resolve_native(service: str) -> bool:
    """True if ``service`` is a registered native connector."""
    try:
        from core.integration_registry import DEFAULT_SERVICE_REGISTRY

        return service in DEFAULT_SERVICE_REGISTRY
    except Exception:  # noqa: BLE001
        return False


async def _resolve_piece(service: str) -> bool:
    """True if an Activepieces piece for ``service`` exists in the catalog."""
    try:
        from core.external_integration_service import ExternalIntegrationService

        details = await ExternalIntegrationService().get_piece_details(_to_piece_name(service))
        return details is not None
    except Exception:  # noqa: BLE001
        # Node bridge unavailable (not running in dev) → treat as "not a piece".
        return False


def _resolve_mcp(service: str, action: str) -> Optional[str]:
    """Return the ``server_id`` hosting the matching MCP tool, or None."""
    try:
        from core.mcp_service import mcp_service

        candidates = _mcp_tool_candidates(service, action)
        for server_id, tools in (mcp_service.tools_cache or {}).items():
            for tool in (tools or []):
                name = getattr(tool, "name", None) or (tool.get("name") if isinstance(tool, dict) else None)
                if name in candidates:
                    return server_id
    except Exception:  # noqa: BLE001
        pass
    return None


async def resolve_backend(service: str, action: str) -> Tuple[Optional[str], Optional[str]]:
    """Resolve which backend serves ``(service, action)``.

    Returns ``(backend, server_id)`` where ``server_id`` is only meaningful for
    the MCP backend. Order: native → piece → mcp → None.
    """
    if _resolve_native(service):
        return NATIVE, None
    if await _resolve_piece(service):
        return PIECE, None
    server_id = _resolve_mcp(service, action)
    if server_id is not None:
        return MCP, server_id
    return None, None


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
def _load_token_row(tenant_id: str, service: str, db: Any) -> Optional[Any]:
    """Load the most-recent ``IntegrationToken`` row for (tenant, provider)."""
    try:
        from core.models import IntegrationToken

        return (
            db.query(IntegrationToken)
            .filter(
                IntegrationToken.tenant_id == tenant_id,
                IntegrationToken.provider == service,
            )
            .order_by(IntegrationToken.updated_at.desc())
            .first()
        )
    except Exception:  # noqa: BLE001
        return None


def _creds_dict(row: Any) -> Dict[str, Any]:
    """Build the Activepieces-shaped credentials dict from a token row."""
    try:
        from core.privsec.token_encryption import decrypt_token

        return {
            "access_token": decrypt_token(row.access_token or ""),
            "refresh_token": decrypt_token(row.refresh_token or "") if row.refresh_token else None,
            "token_type": row.token_type,
            "instance_url": row.instance_url,
        }
    except Exception:  # noqa: BLE001
        # Encryption module unavailable → best-effort plaintext (dev only).
        return {
            "access_token": getattr(row, "access_token", None),
            "refresh_token": getattr(row, "refresh_token", None),
            "token_type": getattr(row, "token_type", None),
            "instance_url": getattr(row, "instance_url", None),
        }


async def execute_native(service: str, action: str, params: Dict[str, Any],
                         tenant_id: str, db: Any) -> Dict[str, Any]:
    """Execute via a native connector (IntegrationRegistry).

    Loads the token, constructs the service WITH credentials, and dispatches via
    ``execute_operation`` (the unified native entry point). The registry returns
    an UNAUTHENTICATED instance by default — we must thread creds explicitly.
    """
    try:
        from core.integration_registry import IntegrationRegistry

        row = _load_token_row(tenant_id, service, db)
        config = {"access_token": None}
        if row is not None:
            config = _creds_dict(row)
        registry = IntegrationRegistry()
        # Construct with credentials so the service is authenticated.
        service_cls = registry.get_service_class(service)
        if service_cls is None:
            return {"ok": False, "error": "native_service_not_found"}
        try:
            instance = service_cls(tenant_id=tenant_id, config=config)
        except TypeError:
            instance = service_cls(config=config)
        result = await instance.execute_operation(action, params, context={"tenant_id": tenant_id})
        return {"ok": True, "data": result, "backend": NATIVE, "service": service, "action": action}
    except Exception as e:  # noqa: BLE001
        logger.warning("native %s.%s failed: %s", service, action, e)
        return {"ok": False, "error": "failed", "backend": NATIVE, "service": service, "action": action}


async def execute_piece(service: str, action: str, params: Dict[str, Any],
                        tenant_id: str, db: Any) -> Dict[str, Any]:
    """Execute via an Activepieces piece (ExternalIntegrationService → Node bridge)."""
    try:
        from core.external_integration_service import ExternalIntegrationService

        row = _load_token_row(tenant_id, service, db)
        creds = _creds_dict(row) if row is not None else None
        result = await ExternalIntegrationService().execute_integration_action(
            integration_id=_to_piece_name(service),
            action_id=action,
            params=params,
            credentials=creds,
        )
        data = getattr(result, "data", None)
        if data is None and isinstance(result, dict):
            data = result.get("data")
        if data is None:
            data = result
        return {"ok": True, "data": data, "backend": PIECE, "service": service, "action": action}
    except Exception as e:  # noqa: BLE001
        logger.warning("piece %s.%s failed: %s", service, action, e)
        return {"ok": False, "error": "failed", "backend": PIECE, "service": service, "action": action}


async def execute_mcp(server_id: str, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute via the real MCP client (core/mcp_service)."""
    try:
        from core.mcp_service import mcp_service

        result = await mcp_service.call_external_tool(server_id, tool_name, args)
        return {"ok": True, "data": result, "backend": MCP, "service": server_id, "action": tool_name}
    except Exception as e:  # noqa: BLE001
        logger.warning("mcp %s.%s failed: %s", server_id, tool_name, e)
        return {"ok": False, "error": "failed", "backend": MCP, "service": server_id, "action": tool_name}


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
async def dispatch(service: str, action: str, params: Dict[str, Any],
                   *, tenant_id: str, db: Any) -> Dict[str, Any]:
    """Resolve the backend and execute. Returns a uniform result dict.

    On ``not_found`` returns ``{ok: False, error: "not_found"}`` so callers can
    react. Never raises — failures are isolated per-backend (each execute_*
    function catches internally, but we wrap defensively in case a backend's
    entry point itself raises before its internal guard).
    """
    try:
        backend, server_id = await resolve_backend(service, action)
        if backend == NATIVE:
            return await execute_native(service, action, params, tenant_id, db)
        if backend == PIECE:
            return await execute_piece(service, action, params, tenant_id, db)
        if backend == MCP and server_id is not None:
            # MCP tool name: use the first candidate that matched during resolution.
            tool_name = _mcp_tool_candidates(service, action)[0]
            return await execute_mcp(server_id, tool_name, params)
        return {"ok": False, "error": "not_found", "service": service, "action": action}
    except Exception as e:  # noqa: BLE001
        logger.warning("dispatch %s.%s raised: %s", service, action, e)
        return {"ok": False, "error": "failed", "service": service, "action": action}
