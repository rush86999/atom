
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.financial_forensics import get_forensics_services
from core.auth import User, get_current_user
from core.personal_scope import (
    DocumentScopeResolutionError,
    DocumentScopeUnavailable,
    resolve_document_workspace_id,
)

# Forensics endpoints expose sensitive vendor/pricing/subscription analysis —
# they must be authenticated. Previously none had a get_current_user dependency.
router = BaseAPIRouter(prefix="/api/forensics", tags=["Forensics"], dependencies=[Depends(get_current_user)])


def _resolve_workspace_or_403(current_user: User) -> str:
    """Authoritative workspace for an authenticated forensics read.

    Reuses the Personal Edition document-scope resolver: a persisted binding is
    honoured first, only the server-owned bootstrap identity may fall back to
    the Personal workspace, and every other unbound account fails closed before
    the service is reached with a literal default.
    """
    try:
        workspace_id = resolve_document_workspace_id(current_user)
    except (DocumentScopeUnavailable, DocumentScopeResolutionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No workspace scope is bound to this account",
        ) from exc
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No workspace scope is bound to this account",
        )
    return str(workspace_id)


@router.get("/vendor-drift")
async def get_vendor_drift(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Detect vendors with increasing costs"""
    workspace_id = _resolve_workspace_or_403(current_user)
    try:
        services = get_forensics_services(db)
        drift_data = await services["vendor"].detect_price_drift(workspace_id)
        return router.success_response(
            data=drift_data,
            message="Vendor drift data retrieved successfully"
        )
    except Exception as e:
        raise router.internal_error(
            message="Failed to detect vendor drift"
        )

@router.get("/pricing-opportunities")
async def get_pricing_opportunities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recommendations for price optimization"""
    workspace_id = _resolve_workspace_or_403(current_user)
    try:
        services = get_forensics_services(db)
        opportunities = await services["pricing"].get_pricing_recommendations(workspace_id)
        return router.success_response(
            data=opportunities,
            message="Pricing opportunities retrieved successfully"
        )
    except Exception as e:
        raise router.internal_error(
            message="Failed to get pricing opportunities"
        )

@router.get("/subscription-waste")
async def get_subscription_waste(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Identify unused subscriptions"""
    workspace_id = _resolve_workspace_or_403(current_user)
    try:
        services = get_forensics_services(db)
        waste_data = await services["waste"].find_zombie_subscriptions(workspace_id)
        return router.success_response(
            data=waste_data,
            message="Subscription waste data retrieved successfully"
        )
    except Exception as e:
        raise router.internal_error(
            message="Failed to identify subscription waste"
        )
