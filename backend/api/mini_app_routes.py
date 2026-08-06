"""Mini-app routes — stateful canvas-UI app authoring + install + assets.

Auth: every route requires ``get_current_user``. Owner-scoped mutations (save
logic, dev-run, update, publish, delete asset) require ``created_by == user``.
Asset routes require the instance canvas to carry ``mini_app_id`` and the
requester to own the canvas (or the app to be public).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import User, get_current_user
from core.blueprint_sanitizer import strip_credentials
from core.database import get_db
from core.mini_app_db_service import DEFAULT_MAX_RECORD_BYTES, db_store_enabled
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


class RecordAppendRequest(BaseModel):
    series: str
    data: Dict[str, Any]


class RecordQueryRequest(BaseModel):
    series: str
    filter: Optional[Dict[str, Any]] = None
    limit: int = 100
    order: str = "desc"


class RecordCountRequest(BaseModel):
    series: Optional[str] = None
    filter: Optional[Dict[str, Any]] = None


class RecordUpdateRequest(BaseModel):
    series: str
    data: Dict[str, Any]


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
    q: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Gap E: browse returns marketplace metadata (scopes/deps/integrations/desc)
    # so a user can see what an app does before installing. Optional ?q= search.
    query = db.query(MiniApp).filter(
        (MiniApp.created_by == str(current_user.id)) |
        (MiniApp.is_public.is_(True))
    )
    if q:
        like = f"%{q}%"
        query = query.filter(MiniApp.name.ilike(like) | MiniApp.description.ilike(like))
    apps = query.order_by(MiniApp.created_at.desc()).limit(100).all()
    out = []
    for a in apps:
        manifest = a.manifest or {}
        integrations = manifest.get("integrations")
        if integrations is None:
            integrations = manifest.get("mcp_servers") or []
        out.append({
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "version": a.version,
            "status": a.status,
            "is_public": a.is_public,
            "is_approved": getattr(a, "is_approved", False),
            "declared_scopes": manifest.get("declared_scopes") or [],
            "dependencies": manifest.get("dependencies") or [],
            "integrations_count": len(integrations),
            "created_by": a.created_by,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return {"success": True, "apps": out}


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
    public: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_service import publish

    app = _get_app(db, app_id)
    _require_owner(app, current_user)
    try:
        result = publish(app, db, public=public)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


# ---------------------------------------------------------------------------
# Marketplace — share/approve/install-by-token (Gaps C, D, F)
# ---------------------------------------------------------------------------
@router.post("/mini-apps/{app_id}/share")
async def toggle_app_sharing(
    app_id: str,
    public: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Owner toggles an app's public/share-token state (Gap C)."""
    import secrets

    app = _get_app(db, app_id)
    _require_owner(app, current_user)
    app.is_public = bool(public)
    if public and not app.share_token:
        app.share_token = secrets.token_urlsafe(32)
    if not public:
        app.share_token = None
    db.commit()
    return {"success": True, "is_public": app.is_public, "share_token": app.share_token}


@router.post("/mini-apps/{app_id}/approve")
async def approve_mini_app(
    app_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only approval gate for public install (Gap D)."""
    if not getattr(current_user, "is_admin", False) and not getattr(current_user, "is_staff", False):
        raise HTTPException(status_code=403, detail="Admin access required")
    app = _get_app(db, app_id)
    app.is_approved = True
    db.commit()
    return {"success": True, "app_id": app.id, "is_approved": True}


@router.post("/mini-apps/by-token/{share_token}/install")
async def install_by_share_token(
    share_token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Install a public+approved app via its share token (Gap C). The instance
    lands in the installer's tenant (Gap B)."""
    from core.mini_app_service import install

    app = db.query(MiniApp).filter(MiniApp.share_token == share_token).first()
    if app is None or not app.is_public:
        raise HTTPException(status_code=404, detail="App not found")
    if not getattr(app, "is_approved", False):
        raise HTTPException(status_code=403, detail="App is pending review")
    try:
        canvas_id = install(app, current_user, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "canvas_id": canvas_id}


@router.get("/mini-apps/instances/{canvas_id}/update-check")
async def check_instance_update(
    canvas_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Signal whether a newer app version is available (Gap F)."""
    from core.models import MiniAppInstallation

    canvas = _require_instance_canvas(db, canvas_id, current_user)
    inst = db.query(MiniAppInstallation).filter(
        MiniAppInstallation.canvas_id == canvas.id
    ).first()
    if inst is None:
        return {"success": True, "update_available": False, "reason": "no_installation_record"}
    app = db.query(MiniApp).filter(MiniApp.id == inst.app_id).first()
    if app is None:
        return {"success": True, "update_available": False, "reason": "app_deleted"}
    update_available = (
        (app.version or "1.0.0") != (inst.installed_version or "1.0.0")
        or (app.runtime_version or 0) != (inst.installed_runtime_version or 0)
    )
    return {
        "success": True,
        "update_available": update_available,
        "installed_version": inst.installed_version,
        "latest_version": app.version,
        "installed_runtime_version": inst.installed_runtime_version,
        "latest_runtime_version": app.runtime_version,
    }


@router.post("/mini-apps/{app_id}/install")
async def install_mini_app(
    app_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_service import install

    app = _get_app(db, app_id)
    # Gap A fix: install requires owner OR (is_public AND is_approved). A
    # non-owner installing a private app, or an unapproved public app, → 403.
    is_owner = str(app.created_by) == str(current_user.id)
    installable = bool(app.is_public) and bool(getattr(app, "is_approved", False))
    if not (is_owner or installable):
        if bool(app.is_public) and not bool(getattr(app, "is_approved", False)):
            raise HTTPException(status_code=403, detail="App is pending review")
        raise HTTPException(status_code=403, detail="Not authorized to install this app")
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


# ---------------------------------------------------------------------------
# Instance record store — the mini-app data layer (host-mediated CRUD).
# Reads: owner or public instance (via _require_instance_canvas). Mutations:
# owner-only. Kill switch (ATOM_MINIAPP_DB_ENABLED=false) → 503 db_disabled.
# No str(e) in any error body.
# ---------------------------------------------------------------------------
def _require_db_enabled() -> None:
    if not db_store_enabled():
        raise HTTPException(status_code=503, detail="db_disabled")


def _record_series_or_400(series: Any) -> str:
    from core.mini_app_db_service import validate_series

    s = validate_series(series)
    if s is None:
        raise HTTPException(status_code=400, detail="series must match ^[a-z0-9_]{1,64}$")
    return s


def _require_instance_owner(canvas: Canvas, user: User) -> None:
    if str(canvas.created_by) != str(user.id):
        raise HTTPException(status_code=403, detail="Not the instance owner")


def _manifest_db_caps(db: Session, canvas: Canvas) -> Dict[str, Any]:
    app = db.query(MiniApp).filter(MiniApp.id == canvas.mini_app_id).first()
    cfg = ((app.manifest or {}) if app is not None else {}).get("db") or {}
    return cfg


@router.get("/mini-apps/instances/{canvas_id}/records/series")
async def list_instance_record_series(
    canvas_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_db_service import list_series

    _require_db_enabled()
    canvas = _require_instance_canvas(db, canvas_id, current_user)
    return {"success": True, "series": list_series(db, canvas.id)}


@router.get("/mini-apps/instances/{canvas_id}/records")
async def query_instance_records(
    canvas_id: str,
    series: str = Query(...),
    limit: int = Query(100, ge=1, le=10000),
    order: str = Query("desc"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_db_service import query_records

    _require_db_enabled()
    canvas = _require_instance_canvas(db, canvas_id, current_user)
    s = _record_series_or_400(series)
    if order not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="order must be asc|desc")
    rows = query_records(db, canvas.id, s, limit=limit, order=order)
    return {"success": True, "series": s, "records": rows, "count": len(rows)}


@router.post("/mini-apps/instances/{canvas_id}/records")
async def append_instance_record(
    canvas_id: str,
    body: RecordAppendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_db_service import append_record, validate_record_data

    _require_db_enabled()
    canvas = _require_instance_canvas(db, canvas_id, current_user)
    _require_instance_owner(canvas, current_user)
    s = _record_series_or_400(body.series)
    cfg = _manifest_db_caps(db, canvas)
    if not bool(cfg.get("enabled", True)):
        raise HTTPException(status_code=503, detail="db_disabled")
    max_bytes = cfg.get("max_record_bytes", DEFAULT_MAX_RECORD_BYTES)
    if not validate_record_data(body.data, max_bytes):
        raise HTTPException(status_code=400, detail="record data must be an object within the size cap")
    app = db.query(MiniApp).filter(MiniApp.id == canvas.mini_app_id).first()
    row = append_record(
        db, canvas.id, canvas.tenant_id, app.id if app is not None else canvas.mini_app_id,
        s, body.data, created_by=str(current_user.id),
    )
    return {"success": True, "record": row}


@router.post("/mini-apps/instances/{canvas_id}/records/query")
async def query_instance_records_body(
    canvas_id: str,
    body: RecordQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_db_service import query_records, validate_filter

    _require_db_enabled()
    canvas = _require_instance_canvas(db, canvas_id, current_user)
    s = _record_series_or_400(body.series)
    if body.order not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="order must be asc|desc")
    if body.filter is not None and not validate_filter(body.filter):
        raise HTTPException(status_code=400, detail="filter must be an object of scalar values")
    rows = query_records(db, canvas.id, s, f=body.filter or {}, limit=body.limit, order=body.order)
    return {"success": True, "series": s, "records": rows, "count": len(rows)}


@router.post("/mini-apps/instances/{canvas_id}/records/count")
async def count_instance_records(
    canvas_id: str,
    body: RecordCountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_db_service import count_records, validate_filter

    _require_db_enabled()
    canvas = _require_instance_canvas(db, canvas_id, current_user)
    series = None
    if body.series is not None:
        series = _record_series_or_400(body.series)
    if body.filter is not None and not validate_filter(body.filter):
        raise HTTPException(status_code=400, detail="filter must be an object of scalar values")
    n = count_records(db, canvas.id, series=series, f=body.filter or {})
    return {"success": True, "count": n}


@router.get("/mini-apps/instances/{canvas_id}/records/{record_id}")
async def get_instance_record(
    canvas_id: str,
    record_id: str,
    series: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_db_service import get_record

    _require_db_enabled()
    canvas = _require_instance_canvas(db, canvas_id, current_user)
    s = _record_series_or_400(series)
    row = get_record(db, canvas.id, s, record_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"success": True, "record": row}


@router.put("/mini-apps/instances/{canvas_id}/records/{record_id}")
async def update_instance_record(
    canvas_id: str,
    record_id: str,
    body: RecordUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_db_service import update_record, validate_record_data

    _require_db_enabled()
    canvas = _require_instance_canvas(db, canvas_id, current_user)
    _require_instance_owner(canvas, current_user)
    s = _record_series_or_400(body.series)
    cfg = _manifest_db_caps(db, canvas)
    max_bytes = cfg.get("max_record_bytes", DEFAULT_MAX_RECORD_BYTES)
    if not validate_record_data(body.data, max_bytes):
        raise HTTPException(status_code=400, detail="record data must be an object within the size cap")
    row = update_record(db, canvas.id, s, record_id, body.data)
    if row is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"success": True, "record": row}


@router.delete("/mini-apps/instances/{canvas_id}/records/{record_id}")
async def delete_instance_record(
    canvas_id: str,
    record_id: str,
    series: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_db_service import delete_record

    _require_db_enabled()
    canvas = _require_instance_canvas(db, canvas_id, current_user)
    _require_instance_owner(canvas, current_user)
    s = _record_series_or_400(series)
    ok = delete_record(db, canvas.id, s, record_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"success": True, "record_id": record_id, "deleted": True}


@router.delete("/mini-apps/instances/{canvas_id}/records")
async def delete_instance_record_series(
    canvas_id: str,
    series: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.mini_app_db_service import delete_series

    _require_db_enabled()
    canvas = _require_instance_canvas(db, canvas_id, current_user)
    _require_instance_owner(canvas, current_user)
    s = _record_series_or_400(series)
    n = delete_series(db, canvas.id, s)
    return {"success": True, "series": s, "deleted": n}
