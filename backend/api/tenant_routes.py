"""
Tenant/Multi-tenancy API Routes
Handles tenant context and subdomain-based routing
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.models import Tenant, User

router = APIRouter(prefix="/api/tenants", tags=["Tenants"])


# Request/Response Models
class TenantResponse(BaseModel):
    """Tenant information"""
    id: str
    name: str
    subdomain: str
    plan_type: str
    status: str

    class Config:
        from_attributes = True


class TenantContextResponse(BaseModel):
    """Tenant context for current user"""
    tenant: Optional[TenantResponse]
    user_role: str


# Endpoints
@router.get("/by-subdomain/{subdomain}", response_model=TenantResponse)
async def get_tenant_by_subdomain(
    subdomain: str,
    db: Session = Depends(get_db)
):
    """
    Get tenant by subdomain

    Used for subdomain-based routing in multi-tenant deployments.
    Returns tenant configuration for the given subdomain.
    """
    tenant = db.query(Tenant).filter(
        Tenant.subdomain == subdomain,
        Tenant.status == "active"
    ).first()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )

    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        subdomain=tenant.subdomain,
        plan_type=tenant.plan_type,
        status=tenant.status
    )


@router.get("/context", response_model=TenantContextResponse)
async def get_tenant_context(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's tenant context

    Returns tenant information and user role for context-aware UI rendering.
    Useful for applying tenant-specific branding and permissions.
    """
    tenant_id = getattr(current_user, 'tenant_id', None)

    if not tenant_id:
        return TenantContextResponse(
            tenant=None,
            user_role=current_user.role
        )

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return TenantContextResponse(
            tenant=None,
            user_role=current_user.role
        )

    return TenantContextResponse(
        tenant=TenantResponse(
            id=tenant.id,
            name=tenant.name,
            subdomain=tenant.subdomain,
            plan_type=tenant.plan_type,
            status=tenant.status
        ),
        user_role=current_user.role
    )
