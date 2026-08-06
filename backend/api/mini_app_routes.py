"""Mini-app routes — stateful canvas-UI app authoring + install + assets.

Auth: every route requires ``get_current_user``. Owner-scoped mutations (save
logic, dev-run, update, publish, delete asset) require ``created_by == user``.
Asset routes require the instance canvas to carry ``mini_app_id`` and the
requester to own the canvas (or the app to be public).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import User, get_current_user
from core.blueprint_sanitizer import strip_credentials
from core.database import get_db
from core.mini_app_storage import get_max_object_bytes, get_mini_app_storage
from core.models import Canvas, CanvasLogic, MiniApp, MiniAppAsset

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["mini-apps"])


class MiniAppCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    version: Optional[str] = "1.0.0"
    manifest: Dict[str, Any]
    source_canvas_id: Optional[str] = None


class MiniAppScaffoldRequest(BaseModel):
    name: str
    spec: Dict[str, Any] = {}
    declared_scopes: List[str] = []
    dependencies: List[str] = []
    base_image: Optional[str] = "python:3.11-slim"


class MiniAppLogicRequest(BaseModel):
    source: str


class MiniAppUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    manifest: Optional[Dict[str, Any]] = None


class MiniAppDevRunRequest(BaseModel):
    inputs: Dict[str, Any] = {}


def _get_app(db: Session, app_id: str) -> MiniApp:
    app = db.query(MiniApp).filter(MiniApp.id == app_id).first()
    if app is None:
        raise HTTPException(status_code=404, detail=f"MiniApp {app_id} not found")
    return app


def _require_owner(app: MiniApp, user: User) -> None:
    if str(app.created_by) != str(user.id):
        raise HTTPException(status_code=403, detail="Not the app owner")


def _require_instance_canvas(db: Session, canvas_id: str, user: User) -> Canvas:
    canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
    if canvas is None or not canvas.mini_app_id:
        raise HTTPException(status_code=404, detail="Mini-app instance canvas not found")
    app = db.query(MiniApp).filter(MiniApp.id == canvas.mini_app_id).first()
    is_owner = str(canvas.created_by) == str(user.id)
    is_public = bool(app and app.is_public)
    if not (is_owner or is_public):
        raise HTTPException(status_code=403, detail="Not authorized to access this instance")
    return canvas


@router.post("/mini-apps")
async def create_mini_app(
    body: MiniAppCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_service import validate_manifest

    try:
        validate_manifest(body.manifest)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    app = MiniApp(
        tenant_id=getattr(current_user, "tenant_id", None) or "default",
        workspace_id=getattr(current_user, "workspace_id", None),
        created_by=str(current_user.id),
        name=body.name,
        description=body.description,
        version=body.version or "1.0.0",
        manifest=body.manifest,
        blueprint_canvas_id=body.source_canvas_id,
        status="draft",
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return {"success": True, "app": {"id": app.id, "name": app.name, "status": app.status}}


@router.post("/mini-apps/scaffold")
async def scaffold_mini_app(
    body: MiniAppScaffoldRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_service import scaffold

    app, canvas_id = scaffold(
        spec=body.spec,
        name=body.name,
        declared_scopes=body.declared_scopes,
        dependencies=body.dependencies,
        viewer=current_user,
        db=db,
    )
    return {
        "success": True,
        "app": {"id": app.id, "name": app.name, "status": app.status},
        "canvas_id": canvas_id,
        "logic_source": (app.manifest or {}).get("blueprint", {}).get("logic_source", ""),
        "manifest": app.manifest,
    }


@router.post("/mini-apps/{app_id}/logic")
async def save_mini_app_logic(
    app_id: str,
    body: MiniAppLogicRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.canvas_logic_service import CanvasLogicService
    from core.mini_app_service import syntax_check

    app = _get_app(db, app_id)
    _require_owner(app, current_user)
    if not app.blueprint_canvas_id:
        raise HTTPException(status_code=400, detail="App has no blueprint canvas")
    try:
        syntax_check(body.source)
    except SyntaxError as e:
        raise HTTPException(status_code=400, detail=f"SyntaxError: {e}")
    CanvasLogicService(db).save_logic(
        canvas_id=app.blueprint_canvas_id,
        source=body.source,
        created_by=str(current_user.id),
    )
    return {"success": True}


@router.post("/mini-apps/{app_id}/dev-run")
async def dev_run_mini_app(
    app_id: str,
    body: MiniAppDevRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_service import prepare_runtime, run_stateful

    app = _get_app(db, app_id)
    _require_owner(app, current_user)
    if not app.blueprint_canvas_id:
        raise HTTPException(status_code=400, detail="App has no blueprint canvas")
    # Fail-closed: deps must scan clean AND the rootfs must exist.
    prepare_runtime(app, db)
    result = await run_stateful(
        app.blueprint_canvas_id,
        inputs=body.inputs,
        user_id=str(current_user.id),
        persist=False,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "dev-run failed"))
    return {"success": True, "state": result.get("state"), "proposed_ops": result.get("proposed_ops")}


@router.get("/mini-apps")
async def list_mini_apps(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    apps = db.query(MiniApp).filter(
        (MiniApp.created_by == str(current_user.id)) |
        (MiniApp.is_public.is_(True))
    ).order_by(MiniApp.created_at.desc()).limit(100).all()
    return {
        "success": True,
        "apps": [
            {
                "id": a.id,
                "name": a.name,
                "version": a.version,
                "status": a.status,
                "is_public": a.is_public,
                "created_by": a.created_by,
            }
            for a in apps
        ],
    }


@router.get("/mini-apps/{app_id}")
async def get_mini_app(
    app_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = _get_app(db, app_id)
    return {
        "success": True,
        "app": {
            "id": app.id,
            "name": app.name,
            "description": app.description,
            "version": app.version,
            "status": app.status,
            "is_public": app.is_public,
            "runtime_image": app.runtime_image,
            "runtime_version": app.runtime_version,
            "blueprint_canvas_id": app.blueprint_canvas_id,
            "manifest": strip_credentials(app.manifest or {}),
            "created_at": app.created_at.isoformat() if app.created_at else None,
        },
    }


@router.put("/mini-apps/{app_id}")
async def update_mini_app(
    app_id: str,
    body: MiniAppUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_service import validate_manifest

    app = _get_app(db, app_id)
    _require_owner(app, current_user)
    if body.name is not None:
        app.name = body.name
    if body.description is not None:
        app.description = body.description
    if body.version is not None:
        app.version = body.version
    if body.manifest is not None:
        try:
            validate_manifest(body.manifest)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        old_deps = (app.manifest or {}).get("dependencies") or []
        new_deps = body.manifest.get("dependencies") or []
        if new_deps != old_deps:
            # Dependency change → clear runtime_image to force rootfs rebuild.
            app.runtime_image = None
        app.manifest = body.manifest
    db.commit()
    return {"success": True, "app_id": app.id}


@router.post("/mini-apps/{app_id}/publish")
async def publish_mini_app(
    app_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_service import publish

    app = _get_app(db, app_id)
    _require_owner(app, current_user)
    try:
        result = publish(app, db)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.post("/mini-apps/{app_id}/install")
async def install_mini_app(
    app_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_service import install

    app = _get_app(db, app_id)
    try:
        canvas_id = install(app, current_user, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "canvas_id": canvas_id}


# ---------------------------------------------------------------------------
# Instance asset routes
# ---------------------------------------------------------------------------
@router.post("/mini-apps/instances/{canvas_id}/assets")
async def upload_instance_asset(
    canvas_id: str,
    key: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_storage import validate_key

    canvas = _require_instance_canvas(db, canvas_id, current_user)
    cap = get_max_object_bytes()
    data = await file.read()
    if len(data) > cap:
        raise HTTPException(status_code=413, detail=f"Asset exceeds {cap} byte limit")
    try:
        validate_key(key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    storage = get_mini_app_storage(canvas.tenant_id, canvas_id)
    uri = storage.store(key, data, content_type=file.content_type)
    row = db.query(MiniAppAsset).filter(
        MiniAppAsset.canvas_id == canvas_id,
        MiniAppAsset.key == key,
    ).first()
    if row is None:
        db.add(MiniAppAsset(
            canvas_id=canvas_id,
            tenant_id=canvas.tenant_id,
            key=key,
            uri=uri,
            content_type=file.content_type,
            size=len(data),
            created_by=str(current_user.id),
        ))
    else:
        row.uri = uri
        row.content_type = file.content_type
        row.size = len(data)
    db.commit()
    return {"success": True, "key": key, "uri": uri}


@router.get("/mini-apps/instances/{canvas_id}/assets")
async def list_instance_assets(
    canvas_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    canvas = _require_instance_canvas(db, canvas_id, current_user)
    rows = db.query(MiniAppAsset).filter(MiniAppAsset.canvas_id == canvas_id).all()
    return {
        "success": True,
        "assets": [
            {
                "key": r.key,
                "uri": r.uri,
                "content_type": r.content_type,
                "size": r.size,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/mini-apps/instances/{canvas_id}/assets/{key}")
async def download_instance_asset(
    canvas_id: str,
    key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from fastapi import Response

    canvas = _require_instance_canvas(db, canvas_id, current_user)
    storage = get_mini_app_storage(canvas.tenant_id, canvas_id)
    data = storage.retrieve(key)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Asset '{key}' not found")
    row = db.query(MiniAppAsset).filter(
        MiniAppAsset.canvas_id == canvas_id,
        MiniAppAsset.key == key,
    ).first()
    media_type = row.content_type if row and row.content_type else "application/octet-stream"
    return Response(content=data, media_type=media_type)


@router.delete("/mini-apps/instances/{canvas_id}/assets/{key}")
async def delete_instance_asset(
    canvas_id: str,
    key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    canvas = _require_instance_canvas(db, canvas_id, current_user)
    if str(canvas.created_by) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not the instance owner")
    storage = get_mini_app_storage(canvas.tenant_id, canvas_id)
    ok = storage.delete(key)
    row = db.query(MiniAppAsset).filter(
        MiniAppAsset.canvas_id == canvas_id,
        MiniAppAsset.key == key,
    ).first()
    if row is not None:
        db.delete(row)
        db.commit()
    return {"success": True, "key": key, "deleted": ok}
