"""
Edition Routes - REST API for Personal/Enterprise edition management.

Endpoints:
- GET /api/edition - Get current edition and features
- POST /api/edition/enable - Enable Enterprise features
- GET /api/edition/features - List all features with availability
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from core.models import get_db
from core.package_feature_service import (
    get_package_feature_service,
    Feature,
    Edition
)

router = APIRouter(prefix="/api/edition", tags=["Edition"])


class EditionInfo(BaseModel):
    """Current edition information."""
    edition: str  # "personal" or "enterprise"
    is_enterprise: bool
    database_url: Optional[str]
    features_enabled: int
    features_total: int


class FeatureInfo(BaseModel):
    """Feature information."""
    id: str
    name: str
    description: str
    available: bool
    edition: str
    dependencies: List[str]


class FeaturesList(BaseModel):
    """List of features."""
    features: List[FeatureInfo]
    edition: str
    available_count: int
    total_count: int


class EnableEnterpriseRequest(BaseModel):
    """Request to enable Enterprise edition."""
    database_url: Optional[str] = None
    workspace_id: Optional[str] = None
    skip_dependencies: bool = False


class EnableEnterpriseResponse(BaseModel):
    """Response from enabling Enterprise."""
    success: bool
    message: str
    requires_restart: bool
    next_steps: List[str]


@router.get("/info", response_model=EditionInfo)
async def get_edition_info():
    """
    Get current edition information.

    Returns:
    - Current edition (personal/enterprise)
    - Enterprise status
    - Database configuration
    - Feature counts
    """
    import os

    service = get_package_feature_service()

    # Count available features
    available = service.get_available_features()
    all_features = set(Feature)  # All defined features

    return EditionInfo(
        edition=service.edition.value,
        is_enterprise=service.is_enterprise,
        database_url=os.getenv("DATABASE_URL", "Not configured"),
        features_enabled=len(available),
        features_total=len(all_features)
    )


@router.get("/features", response_model=FeaturesList)
async def list_features():
    """
    List all features with availability status.

    Returns all features (Personal and Enterprise) with:
    - Feature ID, name, description
    - Availability in current edition
    - Edition requirement
    - Dependencies
    """
    service = get_package_feature_service()

    features = service.list_features()
    available = [f for f in features if f["available"]]

    return FeaturesList(
        features=features,
        edition=service.edition.value,
        available_count=len(available),
        total_count=len(features)
    )


@router.get("/features/{feature_id}")
async def get_feature_info(feature_id: str):
    """
    Get detailed information about a specific feature.

    Args:
        feature_id: Feature ID (e.g., "multi_user", "sso")

    Returns:
        Feature metadata and availability
    """
    service = get_package_feature_service()

    try:
        feature = Feature(feature_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown feature: {feature_id}"
        )

    info = service.get_feature_info(feature)
    if not info:
        raise HTTPException(
            status_code=404,
            detail=f"Feature metadata not found: {feature_id}"
        )

    return {
        "id": feature_id,
        "name": info.name,
        "description": info.description,
        "edition": info.edition.value,
        "dependencies": [d.value for d in info.dependencies],
        "available": service.is_feature_enabled(feature)
    }


@router.post("/enable", response_model=EnableEnterpriseResponse)
async def enable_enterprise(
    request: EnableEnterpriseRequest
):
    """
    Enable Enterprise Edition features.

    This endpoint provides programmatic access to enable Enterprise features.
    Equivalent to running: atom enable enterprise

    **Note:** After enabling, restart the Atom service for changes to take effect.

    Args:
        request: Enterprise enable request with optional database URL

    Returns:
        Success status, message, restart requirement, next steps
    """
    service = get_package_feature_service()

    if service.is_enterprise:
        return EnableEnterpriseResponse(
            success=True,
            message="Enterprise Edition is already enabled",
            requires_restart=False,
            next_steps=["Configure enterprise features in .env"]
        )

    # In a real implementation, this would:
    # 1. Install enterprise dependencies
    # 2. Update .env file
    # 3. Update database schema if needed

    # For now, return instructions
    next_steps = [
        "Run: atom enable enterprise",
        "Or install dependencies: pip install atom-os[enterprise]",
        "Update .env: ATOM_EDITION=enterprise",
        "Restart Atom service"
    ]

    if request.database_url:
        next_steps.insert(0, f"Set DATABASE_URL={request.database_url}")

    return EnableEnterpriseResponse(
        success=False,
        message="Use CLI to enable Enterprise: atom enable enterprise",
        requires_restart=True,
        next_steps=next_steps
    )


@router.get("/check/{feature_id}")
async def check_feature(feature_id: str):
    """
    Check if a specific feature is enabled.

    Args:
        feature_id: Feature ID to check

    Returns:
        Feature availability status
    """
    service = get_package_feature_service()

    try:
        feature = Feature(feature_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown feature: {feature_id}"
        )

    available = service.is_feature_enabled(feature)
    info = service.get_feature_info(feature)

    return {
        "feature": feature_id,
        "name": info.name if info else feature_id,
        "available": available,
        "edition_required": info.edition.value if info else "unknown",
        "enable_command": f"atom enable enterprise" if not available else None
    }


def register_edition_routes(app):
    """Register edition routes with FastAPI app."""
    app.include_router(router)
