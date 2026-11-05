"""Tenant budget control — admin API.

Exposes the per-tenant budget setting (spend limit + enforcement mode) so an
admin can configure and inspect it. The setting is persisted in
``TenantSetting['billing']`` (the same store ``BudgetEnforcementService`` reads
the enforcement mode from), so reads/writes here take effect immediately for
the in-loop budget gate.

Endpoints (super-admin only):
  GET  /api/admin/tenants/{tenant_id}/budget  → current limit, mode, spend, utilization
  PUT  /api/admin/tenants/{tenant_id}/budget  → set limit_usd and/or enforcement_mode
"""
from __future__ import annotations

import json
import logging
import math
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from core.admin_endpoints import get_platform_admin  # was get_super_admin — see 2026-09-08b role-journey pass
from core.admin_write_service import update_tenant_budget as _update_tenant_budget
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import Tenant, TenantSetting, User
from core.budget_enforcement_service import BudgetEnforcementMode

router = BaseAPIRouter(prefix="/api/admin/tenants", tags=["Admin Budget"])
logger = logging.getLogger(__name__)

_VALID_MODES = set(BudgetEnforcementMode.ALL)


class BudgetSettingUpdate(BaseModel):
    """Partial update for a tenant's budget control setting."""

    budget_limit_usd: Optional[float] = Field(
        default=None, ge=0, description="Monthly spend cap in USD. 0 = no limit."
    )
    enforcement_mode: Optional[str] = Field(
        default=None,
        description=(
            "How to enforce the limit: alert_only (never block), soft_stop "
            "(block new runs, let active finish — default), hard_stop (halt "
            "immediately), approval (require admin override)."
        ),
    )

    @field_validator("budget_limit_usd", mode="before")
    @classmethod
    def _finite_limit(cls, value):
        """Reject non-finite values without echoing them in a 422 payload.

        FastAPI's default validation-error renderer cannot serialize NaN/inf
        inputs; converting them to a plain sentinel keeps the refusal a safe
        JSON 422 while the service keeps its own finiteness guard.
        """
        if value is None:
            return value
        candidate = value
        if isinstance(value, str):
            try:
                candidate = float(value)
            except (TypeError, ValueError):
                return value
        if isinstance(candidate, float) and not math.isfinite(candidate):
            return "__non_finite_budget_limit__"
        return value


def _read_billing_setting(db: Session, tenant_id: str) -> Dict[str, Any]:
    """Read the parsed 'billing' TenantSetting, or {} if absent."""
    row = (
        db.query(TenantSetting)
        .filter(
            TenantSetting.tenant_id == tenant_id,
            TenantSetting.setting_key == "billing",
        )
        .first()
    )
    if not row or not row.setting_value:
        return {}
    try:
        parsed = json.loads(row.setting_value)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _write_billing_setting(db: Session, tenant_id: str, value: Dict[str, Any]) -> None:
    """Upsert the 'billing' TenantSetting with ``value`` (merged)."""
    existing = _read_billing_setting(db, tenant_id)
    existing.update(value)
    row = (
        db.query(TenantSetting)
        .filter(
            TenantSetting.tenant_id == tenant_id,
            TenantSetting.setting_key == "billing",
        )
        .first()
    )
    payload = json.dumps(existing)
    if row:
        row.setting_value = payload
    else:
        db.add(
            TenantSetting(
                tenant_id=tenant_id,
                setting_key="billing",
                setting_value=payload,
            )
        )


def _resolve_budget_state(db: Session, tenant_id: str) -> Dict[str, Any]:
    """Resolve the effective limit, mode, and current spend/utilization."""
    billing = _read_billing_setting(db, tenant_id)
    # Limit lives under billing.budget_limit_usd. Fall back to the (legacy,
    # often non-persisted) Tenant attribute if present.
    limit = billing.get("budget_limit_usd")
    if limit is None:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        limit = getattr(tenant, "budget_limit_usd", None) if tenant else None
    limit = float(limit) if limit is not None else 0.0

    mode = billing.get("enforcement", {}).get("mode", BudgetEnforcementMode.SOFT_STOP)
    if mode not in _VALID_MODES:
        mode = BudgetEnforcementMode.SOFT_STOP

    # Current spend / utilization via the spend service (best-effort).
    current_spend = 0.0
    utilization = 0.0
    try:
        from core.spend_aggregation_service import SpendAggregationService

        spend = SpendAggregationService(db).update_tenant_spend(tenant_id)
        if "error" not in spend:
            current_spend = float(spend.get("current_spend_usd", 0.0))
            utilization = (
                round((current_spend / limit) * 100, 2) if limit > 0 else 0.0
            )
    except Exception as e:
        logger.warning(f"Could not compute spend for tenant {tenant_id}: {e}")

    return {
        "tenant_id": tenant_id,
        "budget_limit_usd": round(limit, 4),
        "enforcement_mode": mode,
        "current_spend_usd": round(current_spend, 4),
        "utilization_percent": utilization,
    }


@router.get("/{tenant_id}/budget")
def get_tenant_budget(
    tenant_id: str,
    admin: User = Depends(get_platform_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get the tenant's budget limit, enforcement mode, and current spend."""
    if not db.query(Tenant).filter(Tenant.id == tenant_id).first():
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _resolve_budget_state(db, tenant_id)


def _raise_admin_budget(result: Dict[str, Any]) -> None:
    status = str(result.get("status") or "")
    if status == "refused":
        http_status = int(result.get("http_status") or 422)
        message = str(result.get("error") or "Budget request refused")
        raise HTTPException(status_code=http_status, detail=message)
    if status == "conflict":
        raise HTTPException(
            status_code=409,
            detail={
                "message": result.get("error") or "Tenant budget changed",
                "code": result.get("error_code"),
                "operation_id": result.get("operation_id"),
            },
        )
    if status in ("committed_unverified", "effect_unknown"):
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": (
                        "ADMIN_EFFECT_UNKNOWN"
                        if status == "effect_unknown"
                        else "ADMIN_COMMITTED_UNVERIFIED"),
                    "message": result.get("message") or (
                        "Tenant budget outcome is not confirmed."),
                },
                "verification": result.get("verification"),
                "operation_id": result.get("operation_id"),
                "audit_id": result.get("audit_id"),
                "replay": "do_not_repeat",
            },
        )


@router.put("/{tenant_id}/budget")
def update_tenant_budget(
    tenant_id: str,
    update: BudgetSettingUpdate,
    operation_id: Optional[str] = None,
    admin: User = Depends(get_platform_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update tenant billing under a material CAS and durable audit receipt."""
    result = _update_tenant_budget(
        db,
        actor=admin,
        tenant_id=tenant_id,
        budget_limit_usd=update.budget_limit_usd,
        enforcement_mode=update.enforcement_mode,
        operation_id=operation_id,
    )
    _raise_admin_budget(result)
    db.expire_all()
    response = _resolve_budget_state(db, tenant_id)
    response.update({
        "verification": result.get("verification"),
        "operation_id": result.get("operation_id"),
        "audit_id": result.get("audit_id"),
    })
    return response
