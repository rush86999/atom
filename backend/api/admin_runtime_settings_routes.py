"""Admin Runtime Settings API — env vars as UI-administrable settings.

Surface for the ``core/runtime_settings.py`` resolver + the declarative
``core/settings_catalog.py``:

- GET  /api/v1/admin/settings            → full catalog + resolved values
- GET  /api/v1/admin/settings/categories → distinct category list
- GET  /api/v1/admin/settings/audit      → last 100 change-audit rows
- PUT  /api/v1/admin/settings/{key}      → persist an override (DB row)
- DELETE /api/v1/admin/settings/{key}    → remove override (falls back
                                           to explicit env or default)

Semantics preserved from the flag system: an explicit environment
variable ALWAYS wins over a stored row (kill switch), so operators can
revert any UI change by exporting the var. Secrets (API keys, webhook
secrets, credential paths) are listed but never returned nor writable.

All mutating endpoints require an admin role
(super_admin/owner/admin/workspace_admin).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth import get_current_user
from core.database import get_db
from core.models import RuntimeSetting, SettingChangeAudit, User, UserRole
from core.runtime_settings import (
    invalidate_settings_cache,
    resolve_setting,
)
from core.settings_catalog import (
    SETTING_CATALOG,
    find_spec,
    serialize_catalog,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/settings", tags=["Admin Settings"])

_ADMIN_ROLES = (
    UserRole.SUPER_ADMIN.value,
    UserRole.OWNER.value,
    UserRole.ADMIN.value,
    UserRole.WORKSPACE_ADMIN.value,
)


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Admin gate (super_admin/owner/admin/workspace_admin)."""
    role = getattr(current_user, "role", None)
    if role not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


class SettingUpdate(BaseModel):
    value: Any


def _serialize_all(db: Any) -> list[dict]:
    resolved = {s.key: resolve_setting(s.key, db=db) for s in SETTING_CATALOG}
    return serialize_catalog(SETTING_CATALOG, resolved=resolved)


@router.get("")
async def list_settings(
    _admin: User = Depends(_require_admin),
    db: Any = Depends(get_db),
) -> Dict[str, Any]:
    """Catalog with current resolved value + source per entry."""
    try:
        entries = _serialize_all(db)
        categories = sorted({e["category"] for e in entries})
        return {
            "success": True,
            "data": {"settings": entries, "categories": categories},
        }
    except Exception as e:
        logger.error(f"Settings listing failed: {e}")
        raise HTTPException(status_code=500, detail="Settings unavailable")


@router.get("/categories")
async def list_categories(
    _admin: User = Depends(_require_admin),
) -> Dict[str, Any]:
    """Distinct category names (for tabbed UI navigation)."""
    return {
        "success": True,
        "data": {
            "categories": sorted({s.category for s in SETTING_CATALOG}),
            "count": len(SETTING_CATALOG),
        },
    }


@router.get("/audit")
async def audit_history(
    limit: int = 50,
    setting_key: Optional[str] = None,
    _admin: User = Depends(_require_admin),
    db: Any = Depends(get_db),
) -> Dict[str, Any]:
    """Recent changes (append-only trail). Limit clamped to 200."""
    try:
        q = db.query(SettingChangeAudit)
        if setting_key:
            q = q.filter(SettingChangeAudit.setting_key == setting_key)
        rows = q.order_by(SettingChangeAudit.changed_at.desc()).limit(min(max(limit, 1), 200)).all()
        return {
            "success": True,
            "data": {
                "changes": [
                    {
                        "id": r.id,
                        "setting_key": r.setting_key,
                        "old_value_json": r.old_value_json,
                        "new_value_json": r.new_value_json,
                        "changed_by": r.changed_by,
                        "changed_at": r.changed_at.isoformat() if r.changed_at else None,
                    }
                    for r in rows
                ]
            },
        }
    except Exception as e:
        logger.error(f"Settings audit read failed: {e}")
        raise HTTPException(status_code=500, detail="Audit unavailable")


@router.put("/{key}")
async def update_setting(
    key: str,
    payload: SettingUpdate,
    admin: User = Depends(_require_admin),
    db: Any = Depends(get_db),
) -> Dict[str, Any]:
    """Persist a UI override for one setting.

    Validation: unknown key → 404; secret/locked → 403; type mismatch
    → 400. Writes a ``runtime_settings`` row + audit row and invalidates
    the resolver cache so the next flag check observes the change.
    """
    spec = find_spec(key)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown setting: {key}")
    if spec.secret:
        raise HTTPException(
            status_code=403,
            detail=f"{key} is managed by environment configuration",
        )

    # Validate against the spec's type BEFORE persisting.
    from core.runtime_settings import _coerce

    try:
        coerced = _coerce(payload.value, spec.type)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid value for {key} (expected {spec.type}): {exc}",
        )

    old_row = db.get(RuntimeSetting, key)
    old_value = old_row.value_json if old_row else None

    try:
        if old_row is None:
            old_row = RuntimeSetting(key=key, value_json=coerced, updated_by=getattr(admin, "email", None))
            db.add(old_row)
        else:
            old_row.value_json = coerced
            old_row.updated_by = admin.email
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Setting write failed for {key}: {e}")
        raise HTTPException(status_code=500, detail="Setting write failed")

    _write_audit(db, key=key, old=old_value, new=coerced, changed_by=getattr(admin, "email", None))
    invalidate_settings_cache()

    resolved = resolve_setting(key, db=db)
    return {
        "success": True,
        "message": f"{key} updated",
        "data": {"key": key, "value": resolved.value, "source": resolved.source},
    }


@router.delete("/{key}")
async def reset_setting(
    key: str,
    admin: User = Depends(_require_admin),
    db: Any = Depends(get_db),
) -> Dict[str, Any]:
    """Remove a stored override — resolution falls back to explicit env
    var or the catalog default."""
    spec = find_spec(key)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown setting: {key}")

    old_row = db.get(RuntimeSetting, key)
    if old_row is None:
        return {
            "success": True,
            "message": f"{key} has no stored override",
            "data": {"key": key, "source": resolve_setting(key, db=db).source},
        }

    old_value = old_row.value_json
    try:
        db.delete(old_row)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Setting reset failed for {key}: {e}")
        raise HTTPException(status_code=500, detail="Setting reset failed")

    _write_audit(db, key=key, old=old_value, new=None, changed_by=getattr(admin, "email", None))
    invalidate_settings_cache()

    resolved = resolve_setting(key, db=db)
    return {
        "success": True,
        "message": f"{key} reset ({resolved.source})",
        "data": {"key": key, "value": resolved.value, "source": resolved.source},
    }


def _write_audit(db: Any, key: str, old: Any, new: Any, changed_by: Any) -> None:
    """Best-effort audit row — never blocks the mutation itself."""
    try:
        db.add(
            SettingChangeAudit(
                setting_key=key,
                old_value_json=old,
                new_value_json=new,
                changed_by=changed_by,
            )
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Settings audit write failed for {key}: {e}")
