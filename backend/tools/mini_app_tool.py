"""Mini-app authoring harness — AGENT-facing tools (agent-driven coding).

Agents running inside Atom create, author, test, publish, install, and run
stateful mini-apps through the same service layer as the API routes. Every
handler follows the unified action-registry contract ``(args, context)`` and
is dispatched by the agent MCP loop (``integrations/mcp_service``) and the
frontend RPC surface (``api/rpc_routes``).

Attribution is the requesting user (extracted from ``context``) — never a
client-supplied actor id (R54 workspace-identity principle). Fail-closed: a
missing/unknown user rejects authoring mutations; an app owner is enforced
for mutations.

This is the "coding harness": the agent loop is scaffold → write logic
(syntax-gated) → dev-run (dry) → iterate → publish → install → run. The
human-facing Monaco review surface is a secondary, optional layer on top.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------
def _context_user_id(context: Dict[str, Any]) -> Optional[str]:
    """Best-effort user_id extraction from a dispatch context (mirrors the
    action-registry helper — never trusts a client-supplied actor in args)."""
    if not context:
        return None
    for key in ("user_id", "userId", "actor_id"):
        val = context.get(key)
        if val:
            return str(val)
    user = context.get("user")
    if user is not None:
        uid = getattr(user, "id", None)
        if uid:
            return str(uid)
    return None


def _viewer(context: Dict[str, Any]) -> SimpleNamespace:
    """Build a viewer proxy from the requesting user's identity.

    Loads the ``User`` row so tenant/workspace/tier flow through to the
    service (scaffold attribution, scope caps). Falls back to the id alone
    when the row is missing.
    """
    user_id = _context_user_id(context)
    if not user_id:
        return SimpleNamespace(id=None, tenant_id=None, workspace_id=None, tier=None)
    try:
        from core.database import get_db_session
        from core.models import User

        with get_db_session() as db:
            row = db.query(User).filter(User.id == user_id).first()
        if row is not None:
            return SimpleNamespace(
                id=user_id,
                tenant_id=getattr(row, "tenant_id", None) or "default",
                workspace_id=getattr(row, "workspace_id", None),
                tier=getattr(row, "tier", None),
            )
    except Exception as e:  # noqa: BLE001
        logger.debug("mini_app_tool viewer lookup failed: %s", e)
    return SimpleNamespace(id=user_id, tenant_id=None, workspace_id=None, tier=None)


def _require_actor(context: Dict[str, Any]) -> SimpleNamespace:
    viewer = _viewer(context)
    if not viewer.id:
        return viewer
    return viewer


def _auth_error() -> Dict[str, Any]:
    return {"success": False, "error": "Authenticated user is required"}


# ---------------------------------------------------------------------------
# Authoring loop (the harness)
# ---------------------------------------------------------------------------
async def mini_app_scaffold(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Scaffold a draft mini-app: source canvas + starter logic + manifest."""
    viewer = _require_actor(context)
    if not viewer.id:
        return _auth_error()
    name = (args.get("name") or "").strip()
    if not name:
        return {"success": False, "error": "name is required"}
    spec = args.get("spec") or {}
    declared_scopes = [str(s) for s in (args.get("declared_scopes") or [])]
    dependencies = [str(d) for d in (args.get("dependencies") or [])]
    if "base_image" in spec and not spec.get("base_image"):
        spec["base_image"] = "python:3.11-slim"
    try:
        from core.canvas_logic_service import CanvasLogicService
        from core.database import get_db_session
        from core.mini_app_service import scaffold

        with get_db_session() as db:
            from core.models import MiniApp

            app, canvas_id = scaffold(
                spec=spec,
                name=name,
                declared_scopes=declared_scopes,
                dependencies=dependencies,
                viewer=viewer,
                db=db,
            )
            # Re-query for a fresh attached instance: the caller's session may
            # expire attributes on commit (expire_on_commit=True), which would
            # make post-commit attribute access on ``app`` raise "not bound".
            fresh = db.query(MiniApp).filter(MiniApp.id == app.id).first()
            manifest = fresh.manifest or {} if fresh is not None else {}
            # The starter logic lives in CanvasLogic on the source canvas — not
            # the manifest blueprint (which is only populated at publish). Return
            # the real source so the agent can read and iterate on it.
            logic = CanvasLogicService(db).load_logic(canvas_id) or {}
            logic_source = logic.get("source", "")
        return {
            "success": True,
            "app_id": app.id,
            "canvas_id": canvas_id,
            "name": app.name,
            "logic_source": logic_source,
            "manifest": manifest,
            "message": f"Scaffolded mini-app '{name}' — edit logic, dev-run, then publish",
        }
    except Exception as e:  # noqa: BLE001
        logger.error("mini_app_scaffold failed: %s", e)
        return {"success": False, "error": "Mini-app scaffold failed"}


async def mini_app_write_logic(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Syntax-gated save of the app's logic on its blueprint canvas."""
    viewer = _require_actor(context)
    if not viewer.id:
        return _auth_error()
    app_id = args.get("app_id")
    source = args.get("source") or ""
    if not app_id:
        return {"success": False, "error": "app_id is required"}
    try:
        from core.canvas_logic_service import CanvasLogicService
        from core.database import get_db_session
        from core.mini_app_service import syntax_check
        from core.models import MiniApp

        with get_db_session() as db:
            app = db.query(MiniApp).filter(MiniApp.id == app_id).first()
            if app is None:
                return {"success": False, "error": f"MiniApp {app_id} not found"}
            if str(app.created_by) != viewer.id:
                return {"success": False, "error": "Not the app owner"}
            if not app.blueprint_canvas_id:
                return {"success": False, "error": "App has no blueprint canvas"}
            try:
                syntax_check(source)
            except SyntaxError as e:
                return {"success": False, "error": f"SyntaxError: {e}"}
            CanvasLogicService(db).save_logic(
                canvas_id=app.blueprint_canvas_id,
                source=source,
                created_by=viewer.id,
            )
        return {"success": True, "app_id": app_id, "message": "Logic saved (syntax OK)"}
    except Exception as e:  # noqa: BLE001
        logger.error("mini_app_write_logic failed: %s", e)
        return {"success": False, "error": "Failed to save mini-app logic"}


async def mini_app_dev_run(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Dry-run the app logic in the microVM (no state commit, no storage side effects).

    Fail-closed: dependencies must scan clean AND the per-app rootfs must
    already exist (operator-built via scripts/build_miniapp_rootfs.sh).
    """
    viewer = _require_actor(context)
    if not viewer.id:
        return _auth_error()
    app_id = args.get("app_id")
    if not app_id:
        return {"success": False, "error": "app_id is required"}
    try:
        from core.database import get_db_session
        from core.mini_app_service import prepare_runtime, run_stateful
        from core.models import MiniApp

        with get_db_session() as db:
            app = db.query(MiniApp).filter(MiniApp.id == app_id).first()
            if app is None:
                return {"success": False, "error": f"MiniApp {app_id} not found"}
            if str(app.created_by) != viewer.id:
                return {"success": False, "error": "Not the app owner"}
            if not app.blueprint_canvas_id:
                return {"success": False, "error": "App has no blueprint canvas"}
            prepare_runtime(app, db)  # raises when deps unsafe or rootfs missing

        result = await run_stateful(
            app.blueprint_canvas_id,
            inputs=args.get("inputs") or {},
            user_id=viewer.id,
            persist=False,
        )
        if not result.get("success"):
            return {"success": False, "error": result.get("error", "dev-run failed")}
        return {
            "success": True,
            "state": result.get("state"),
            "proposed_ops": result.get("proposed_ops"),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "exit_code": result.get("exit_code", 0),
            "message": "dev-run completed (dry — no state/storage committed)",
        }
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        logger.error("mini_app_dev_run failed: %s", e)
        return {"success": False, "error": "Mini-app dev-run failed"}


async def mini_app_publish(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Publish the app: deps scan + rootfs gate, snapshot initial_state + blueprint."""
    viewer = _require_actor(context)
    if not viewer.id:
        return _auth_error()
    app_id = args.get("app_id")
    if not app_id:
        return {"success": False, "error": "app_id is required"}
    try:
        from core.database import get_db_session
        from core.mini_app_service import publish
        from core.models import MiniApp

        with get_db_session() as db:
            app = db.query(MiniApp).filter(MiniApp.id == app_id).first()
            if app is None:
                return {"success": False, "error": f"MiniApp {app_id} not found"}
            if str(app.created_by) != viewer.id:
                return {"success": False, "error": "Not the app owner"}
            result = publish(app, db)
        return {
            "success": True,
            "app_id": app_id,
            "version": result.get("version"),
            "message": f"Mini-app {app_id} published (v{result.get('version')})",
        }
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        logger.error("mini_app_publish failed: %s", e)
        return {"success": False, "error": "Mini-app publish failed"}


async def mini_app_install(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Install a published app — hydrates a fresh instance canvas (copy-on-install)."""
    viewer = _require_actor(context)
    if not viewer.id:
        return _auth_error()
    app_id = args.get("app_id")
    if not app_id:
        return {"success": False, "error": "app_id is required"}
    try:
        from core.database import get_db_session
        from core.mini_app_service import install
        from core.models import MiniApp

        with get_db_session() as db:
            app = db.query(MiniApp).filter(MiniApp.id == app_id).first()
            if app is None:
                return {"success": False, "error": f"MiniApp {app_id} not found"}
            canvas_id = install(app, viewer, db)
        return {
            "success": True,
            "app_id": app_id,
            "canvas_id": canvas_id,
            "message": f"Installed mini-app '{app.name}' — instance canvas {canvas_id}",
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        logger.error("mini_app_install failed: %s", e)
        return {"success": False, "error": "Mini-app install failed"}


async def mini_app_run(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Run an installed mini-app instance statefully (persists state + broadcasts).

    This is the runtime execution an agent invokes to drive a mini-app's
    controller on behalf of the requesting user.
    """
    viewer = _require_actor(context)
    if not viewer.id:
        return _auth_error()
    canvas_id = args.get("canvas_id")
    if not canvas_id:
        return {"success": False, "error": "canvas_id is required"}
    from core.mini_app_service import run_stateful

    result = await run_stateful(
        canvas_id,
        inputs=args.get("inputs") or {},
        agent_id=(context or {}).get("agent_id"),
        user_id=viewer.id,
        persist=True,
    )
    return result


async def mini_app_list(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """List mini-apps the requesting user owns (or that are public)."""
    viewer = _require_actor(context)
    if not viewer.id:
        return _auth_error()
    try:
        from core.database import get_db_session
        from core.models import MiniApp

        with get_db_session() as db:
            apps = (
                db.query(MiniApp)
                .filter((MiniApp.created_by == viewer.id) | (MiniApp.is_public.is_(True)))
                .order_by(MiniApp.created_at.desc())
                .limit(100)
                .all()
            )
            return {
                "success": True,
                "apps": [
                    {
                        "id": a.id,
                        "name": a.name,
                        "version": a.version,
                        "status": a.status,
                        "is_public": a.is_public,
                        "blueprint_canvas_id": a.blueprint_canvas_id,
                    }
                    for a in apps
                ],
            }
    except Exception as e:  # noqa: BLE001
        logger.error("mini_app_list failed: %s", e)
        return {"success": False, "error": "Mini-app listing failed", "apps": []}


async def mini_app_get_state(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Read the current state of a mini-app instance canvas."""
    viewer = _require_actor(context)
    if not viewer.id:
        return _auth_error()
    canvas_id = args.get("canvas_id")
    if not canvas_id:
        return {"success": False, "error": "canvas_id is required"}
    try:
        from core.database import get_db_session
        from core.models import Canvas, CanvasState

        with get_db_session() as db:
            canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
            if canvas is None:
                return {"success": False, "error": f"Canvas {canvas_id} not found"}
            if not canvas.mini_app_id:
                return {"success": False, "error": f"Canvas {canvas_id} is not a mini-app instance"}
            row = (
                db.query(CanvasState)
                .filter(CanvasState.canvas_id == canvas_id)
                .order_by(CanvasState.updated_at.desc())
                .first()
            )
            return {
                "success": True,
                "canvas_id": canvas_id,
                "state": row.state if row is not None else {},
                "version": row.version if row is not None else 0,
            }
    except Exception as e:  # noqa: BLE001
        logger.error("mini_app_get_state failed: %s", e)
        return {"success": False, "error": "Mini-app state read failed"}
