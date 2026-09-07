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
    except ValueError as e:
        # Caller-fixable input problems (bad base canvas_type slug, invalid
        # spec) must reach the agent verbatim — a generic "scaffold failed"
        # gives the loop nothing to correct.
        return {"success": False, "error": str(e)}
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
        from core.mini_app_service import record_logic_snapshot, syntax_check
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
            # Checkpoint the save so the agent can list/revert logic versions.
            snapshot = record_logic_snapshot(
                db,
                canvas_id=app.blueprint_canvas_id,
                tenant_id=app.tenant_id,
                app_id=app.id,
                source=source,
                actor_id=viewer.id,
            )
        return {
            "success": True,
            "app_id": app_id,
            "version": snapshot["version"],
            "message": f"Logic saved (syntax OK, checkpoint v{snapshot['version']})",
        }
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
            "version": result.get("version", 0),
            "state_changed": bool(result.get("state_changed", False)),
            "proposed_ops": result.get("proposed_ops") or [],
            "op_results": result.get("op_results") or [],
            "proposed_record_ops": result.get("proposed_record_ops") or [],
            "record_results": result.get("record_results") or [],
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "exit_code": result.get("exit_code", 0),
            "message": "dev-run completed (dry — no state/storage/records committed)",
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
            # Gap A fix: install requires owner OR (is_public AND is_approved).
            is_owner = str(app.created_by) == str(viewer.id)
            installable = bool(app.is_public) and bool(getattr(app, "is_approved", False))
            if not (is_owner or installable):
                if bool(app.is_public) and not bool(getattr(app, "is_approved", False)):
                    return {"success": False, "error": "App is pending review"}
                return {"success": False, "error": "Not authorized to install this app"}
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


# ---------------------------------------------------------------------------
# Agent harness — acceptance tests, logic checkpoints, constraint probe.
# Research-backed: the authoring loop is scaffold → write (checkpointed) →
# dev-run → run_tests (given-state→expected-state, pass/fail + diffs) →
# revert on failure → publish. mini_app_status surfaces the constraints the
# agent must satisfy before it iterates.
# ---------------------------------------------------------------------------
async def mini_app_set_tests(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Declare acceptance-test cases for an app (stored in the manifest)."""
    viewer = _require_actor(context)
    if not viewer.id:
        return _auth_error()
    app_id = args.get("app_id")
    tests = args.get("tests")
    if not app_id:
        return {"success": False, "error": "app_id is required"}
    if not isinstance(tests, list):
        return {"success": False, "error": "tests must be a list"}
    try:
        from core.database import get_db_session
        from core.mini_app_service import validate_tests
        from core.models import MiniApp

        validate_tests(tests)
        with get_db_session() as db:
            app = db.query(MiniApp).filter(MiniApp.id == app_id).first()
            if app is None:
                return {"success": False, "error": f"MiniApp {app_id} not found"}
            if str(app.created_by) != viewer.id:
                return {"success": False, "error": "Not the app owner"}
            # Reassign the whole manifest so the JSON column detects the change.
            manifest = dict(app.manifest or {})
            manifest["tests"] = tests
            app.manifest = manifest
            db.commit()
        return {
            "success": True,
            "app_id": app_id,
            "tests": len(tests),
            "message": f"Saved {len(tests)} acceptance test case(s)",
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        logger.error("mini_app_set_tests failed: %s", e)
        return {"success": False, "error": "Failed to save mini-app tests"}


async def mini_app_run_tests(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Run the app's acceptance tests in the microVM (dry) and grade each case."""
    viewer = _require_actor(context)
    if not viewer.id:
        return _auth_error()
    app_id = args.get("app_id")
    if not app_id:
        return {"success": False, "error": "app_id is required"}
    try:
        from core.database import get_db_session
        from core.mini_app_service import run_tests
        from core.models import MiniApp

        with get_db_session() as db:
            app = db.query(MiniApp).filter(MiniApp.id == app_id).first()
            if app is None:
                return {"success": False, "error": f"MiniApp {app_id} not found"}
            if str(app.created_by) != viewer.id:
                return {"success": False, "error": "Not the app owner"}
            blueprint_canvas_id = app.blueprint_canvas_id
            tests = (app.manifest or {}).get("tests") or []
        if not tests:
            return {
                "success": True,
                "app_id": app_id,
                "passed": 0,
                "total": 0,
                "results": [],
                "message": "No acceptance tests saved — use mini_app_set_tests first",
            }
        report = await run_tests(app_id, blueprint_canvas_id, tests, viewer=viewer)
        return {
            "success": True,
            "app_id": app_id,
            "passed": report["passed"],
            "total": report["total"],
            "all_passed": report["passed"] == report["total"],
            "results": report["results"],
            "message": (
                f"{report['passed']}/{report['total']} acceptance tests passed"
                if report["passed"] != report["total"]
                else f"All {report['total']} acceptance tests passed"
            ),
        }
    except Exception as e:  # noqa: BLE001
        logger.error("mini_app_run_tests failed: %s", e)
        return {"success": False, "error": "Mini-app test run failed"}


async def mini_app_logic_history(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """List the app's logic checkpoints (oldest → newest)."""
    viewer = _require_actor(context)
    if not viewer.id:
        return _auth_error()
    app_id = args.get("app_id")
    if not app_id:
        return {"success": False, "error": "app_id is required"}
    try:
        from core.database import get_db_session
        from core.mini_app_service import list_logic_history
        from core.models import MiniApp

        with get_db_session() as db:
            app = db.query(MiniApp).filter(MiniApp.id == app_id).first()
            if app is None:
                return {"success": False, "error": f"MiniApp {app_id} not found"}
            if str(app.created_by) != viewer.id:
                return {"success": False, "error": "Not the app owner"}
            history = list_logic_history(app, db)
        return {"success": True, "app_id": app_id, "history": history}
    except Exception as e:  # noqa: BLE001
        logger.error("mini_app_logic_history failed: %s", e)
        return {"success": False, "error": "Mini-app logic history read failed"}


async def mini_app_revert_logic(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Revert the app's logic to a previously checkpointed version."""
    viewer = _require_actor(context)
    if not viewer.id:
        return _auth_error()
    app_id = args.get("app_id")
    version = args.get("version")
    if not app_id:
        return {"success": False, "error": "app_id is required"}
    if version is None:
        return {"success": False, "error": "version is required"}
    try:
        from core.database import get_db_session
        from core.mini_app_service import revert_logic
        from core.models import MiniApp

        with get_db_session() as db:
            app = db.query(MiniApp).filter(MiniApp.id == app_id).first()
            if app is None:
                return {"success": False, "error": f"MiniApp {app_id} not found"}
            if str(app.created_by) != viewer.id:
                return {"success": False, "error": "Not the app owner"}
            result = revert_logic(app, db, int(version), actor_id=viewer.id)
        return {
            "success": True,
            "app_id": app_id,
            "version": result["version"],
            "message": f"Reverted logic to checkpoint v{result['version']}",
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        logger.error("mini_app_revert_logic failed: %s", e)
        return {"success": False, "error": "Mini-app logic revert failed"}


async def mini_app_status(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Probe an app's authoring constraints before iterating."""
    viewer = _require_actor(context)
    if not viewer.id:
        return _auth_error()
    app_id = args.get("app_id")
    if not app_id:
        return {"success": False, "error": "app_id is required"}
    try:
        from core.database import get_db_session
        from core.mini_app_service import status_probe
        from core.models import MiniApp

        with get_db_session() as db:
            app = db.query(MiniApp).filter(MiniApp.id == app_id).first()
            if app is None:
                return {"success": False, "error": f"MiniApp {app_id} not found"}
            if str(app.created_by) != viewer.id:
                return {"success": False, "error": "Not the app owner"}
            probe = status_probe(app, db, viewer=viewer)
        return {"success": True, "status": probe}
    except Exception as e:  # noqa: BLE001
        logger.error("mini_app_status failed: %s", e)
        return {"success": False, "error": "Mini-app status probe failed"}


# ---------------------------------------------------------------------------
# Mini-app DB store — agent access to instance record data.
#   mini_app_db_query  — read-only (query/count/get/list_series), INTERN+
#   mini_app_db_write  — mutations (append/update/update_many/delete/
#                        delete_series/clear), SUPERVISED+
# Owner-gated (canvas or app owner); identity always from context. The same
# host-validated op shape as the microVM record_ops envelope, so agents and
# app logic speak one vocabulary.
# ---------------------------------------------------------------------------
_TIER_RANK = {"student": 0, "intern": 1, "supervised": 2, "autonomous": 3}


def _context_tier(context: Dict[str, Any]) -> str:
    """The operating agent's tier (fail-closed: unknown → 'student')."""
    tier = (context or {}).get("tier")
    if tier is None:
        tier = getattr(_viewer(context), "tier", None)
    return str(tier or "student").lower()


def _require_tier(context: Dict[str, Any], minimum: str) -> Optional[str]:
    if _TIER_RANK.get(_context_tier(context), 0) < _TIER_RANK.get(minimum, 0):
        return f"Requires {minimum.upper()}+ maturity tier"
    return None


def _resolve_record_target(db: Any, viewer: Any, canvas_id: str) -> Any:
    """Resolve + owner-gate the instance canvas; return the Canvas row or None."""
    from core.models import Canvas, MiniApp

    canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
    if canvas is None:
        return None
    if not canvas.mini_app_id:
        return None
    app = db.query(MiniApp).filter(MiniApp.id == canvas.mini_app_id).first()
    is_owner = str(canvas.created_by) == str(viewer.id) or (
        app is not None and str(app.created_by) == str(viewer.id)
    )
    if not is_owner:
        return None
    return canvas


_QUERY_OPS = {"query", "count", "get", "list_series"}
_WRITE_OPS = {"append", "update", "update_many", "delete", "delete_series", "clear"}


async def mini_app_db_query(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Read records of a mini-app instance (query/count/get/list_series)."""
    viewer = _require_actor(context)
    if not viewer.id:
        return _auth_error()
    canvas_id = args.get("canvas_id")
    op = args.get("op") or "query"
    if not canvas_id:
        return {"success": False, "error": "canvas_id is required"}
    if op not in _QUERY_OPS:
        return {"success": False, "error": f"op must be one of {sorted(_QUERY_OPS)}"}
    tier_err = _require_tier(context, "intern")
    if tier_err:
        return {"success": False, "error": tier_err}
    try:
        from core.database import get_db_session
        from core.mini_app_db_service import db_store_enabled, get_record, list_series
        from core.mini_app_db_service import query_records, count_records

        if not db_store_enabled():
            return {"success": False, "error": "db_disabled"}
        with get_db_session() as db:
            canvas = _resolve_record_target(db, viewer, canvas_id)
            if canvas is None:
                return {"success": False, "error": "Mini-app instance not found or not owned"}
            series = args.get("series")
            if op != "list_series":
                from core.mini_app_db_service import validate_series

                if validate_series(series) is None:
                    return {"success": False, "error": "series must match ^[a-z0-9_]{1,64}$"}
            if op == "query":
                f = args.get("filter") or {}
                from core.mini_app_db_service import validate_filter

                if not validate_filter(f):
                    return {"success": False, "error": "filter must be an object of scalar values"}
                limit = int(args.get("limit", 100))
                order = args.get("order", "desc")
                if not (1 <= limit <= 10000) or order not in {"asc", "desc"}:
                    return {"success": False, "error": "limit must be 1..10000 and order asc|desc"}
                rows = query_records(db, canvas.id, series, f=f, limit=limit, order=order)
                return {"success": True, "records": rows, "count": len(rows)}
            if op == "count":
                f = args.get("filter") or {}
                from core.mini_app_db_service import validate_filter

                if not validate_filter(f):
                    return {"success": False, "error": "filter must be an object of scalar values"}
                return {"success": True, "count": count_records(db, canvas.id, series=series, f=f)}
            if op == "get":
                rid = args.get("record_id")
                if not rid:
                    return {"success": False, "error": "record_id is required"}
                row = get_record(db, canvas.id, series, rid)
                if row is None:
                    return {"success": False, "error": "record not found"}
                return {"success": True, "record": row}
            return {"success": True, "series": list_series(db, canvas.id)}
    except Exception as e:  # noqa: BLE001
        logger.error("mini_app_db_query failed: %s", e)
        return {"success": False, "error": "Mini-app record query failed"}


async def mini_app_db_write(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Mutate records of a mini-app instance (append/update/delete/clear)."""
    viewer = _require_actor(context)
    if not viewer.id:
        return _auth_error()
    canvas_id = args.get("canvas_id")
    op = args.get("op")
    if not canvas_id:
        return {"success": False, "error": "canvas_id is required"}
    if op not in _WRITE_OPS:
        return {"success": False, "error": f"op must be one of {sorted(_WRITE_OPS)}"}
    tier_err = _require_tier(context, "supervised")
    if tier_err:
        return {"success": False, "error": tier_err}
    try:
        from core.database import get_db_session
        from core.mini_app_db_service import db_store_enabled, validate_series

        if not db_store_enabled():
            return {"success": False, "error": "db_disabled"}
        with get_db_session() as db:
            canvas = _resolve_record_target(db, viewer, canvas_id)
            if canvas is None:
                return {"success": False, "error": "Mini-app instance not found or not owned"}
            from core.models import MiniApp

            app = db.query(MiniApp).filter(MiniApp.id == canvas.mini_app_id).first()
            if app is None:
                return {"success": False, "error": "Mini-app instance not found or not owned"}
            series = args.get("series")
            if op != "clear" and validate_series(series) is None:
                return {"success": False, "error": "series must match ^[a-z0-9_]{1,64}$"}
            from core.mini_app_service import _validate_record_op
            from core.mini_app_db_service import DEFAULT_MAX_RECORD_BYTES, DEFAULT_MAX_RECORDS_PER_SERIES

            manifest = (app.manifest or {}) if app is not None else {}
            db_cfg = manifest.get("db") or {}
            if not bool(db_cfg.get("enabled", True)):
                return {"success": False, "error": "db_disabled"}
            max_bytes = db_cfg.get("max_record_bytes", DEFAULT_MAX_RECORD_BYTES)
            op_args: Dict[str, Any] = {"op": op, "series": series}
            if op in {"append", "update", "update_many"}:
                op_args["data"] = args.get("data")
            if op in {"append", "update", "delete"}:
                op_args["id"] = args.get("record_id")
            if op in {"update_many", "query", "count"}:
                op_args["filter"] = args.get("filter") or {}
            if op == "append":
                op_args["id"] = args.get("id")
            valid = _validate_record_op(op_args, max_bytes)
            if valid is None:
                return {"success": False, "error": "invalid record op (bad data/series/filter shape)"}
            from core.mini_app_service import _execute_record_op

            result = _execute_record_op(
                valid, db, canvas, app, created_by=viewer.id,
                max_records=db_cfg.get("max_records_per_series", DEFAULT_MAX_RECORDS_PER_SERIES),
                max_record_bytes=max_bytes,
            )
            return {"success": bool(result.get("ok")), **result}
    except Exception as e:  # noqa: BLE001
        logger.error("mini_app_db_write failed: %s", e)
        return {"success": False, "error": "Mini-app record write failed"}
