"""
Package Routes - REST API for Python package governance.

Endpoints:
- GET /api/packages/check - Check package permission for agent
- POST /api/packages/request - Request package approval
- POST /api/packages/approve - Approve package (admin only)
- POST /api/packages/ban - Ban package version (admin only)
- GET /api/packages - List all packages in registry

Governance enforcement happens in PackageGovernanceService with <1ms cache lookups.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.package_governance_service import PackageGovernanceService
from core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()
governance = PackageGovernanceService()


# ============================================================================
# Request/Response Models
# ============================================================================

class PackageCheckRequest(BaseModel):
    """Request to check package permission for an agent."""
    agent_id: str = Field(..., description="Agent ID requesting package access")
    package_name: str = Field(..., description="Python package name (e.g., 'numpy')")
    version: str = Field(..., description="Package version (e.g., '1.21.0')")


class PackageApprovalRequest(BaseModel):
    """Request to approve a package version."""
    package_name: str = Field(..., description="Python package name")
    version: str = Field(..., description="Package version")
    min_maturity: str = Field(
        ...,
        description="Minimum maturity level required (INTERN, SUPERVISED, AUTONOMOUS)"
    )
    approved_by: str = Field(..., description="User ID approving the package")


class PackageBanRequest(BaseModel):
    """Request to ban a package version."""
    package_name: str = Field(..., description="Python package name")
    version: str = Field(..., description="Package version")
    reason: str = Field(..., description="Reason for banning (security issue, malicious, etc.)")


class PackageRequest(BaseModel):
    """Request to create package approval request."""
    package_name: str = Field(..., description="Python package name")
    version: str = Field(..., description="Package version")
    requested_by: str = Field(..., description="User ID requesting approval")
    reason: str = Field(..., description="Reason for requesting the package")


class PackagePermissionResponse(BaseModel):
    """Response from package permission check."""
    allowed: bool = Field(..., description="Whether agent can use this package")
    maturity_required: str = Field(..., description="Minimum maturity required")
    reason: Optional[str] = Field(None, description="Reason if not allowed")


class PackageResponse(BaseModel):
    """Response for package details."""
    id: str = Field(..., description="Package ID (name:version)")
    name: str = Field(..., description="Package name")
    version: str = Field(..., description="Package version")
    min_maturity: str = Field(..., description="Required maturity level")
    status: str = Field(..., description="Package status (untrusted, active, banned, pending)")
    ban_reason: Optional[str] = Field(None, description="Reason if banned")
    approved_by: Optional[str] = Field(None, description="User who approved")
    approved_at: Optional[str] = Field(None, description="Approval timestamp (ISO format)")


class PackageListResponse(BaseModel):
    """Response for package list endpoint."""
    packages: list[PackageResponse] = Field(..., description="List of packages")
    count: int = Field(..., description="Total number of packages")


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/check", response_model=PackagePermissionResponse)
def check_package_permission(
    agent_id: str = Query(..., description="Agent ID"),
    package_name: str = Query(..., description="Package name"),
    version: str = Query(..., description="Package version"),
    db: Session = Depends(get_db)
):
    """
    Check if agent can use specific package version.

    Returns permission decision with maturity requirement and reason if blocked.
    Uses cached results for <1ms performance on repeat checks.

    Governance rules:
    - STUDENT agents: Always blocked
    - INTERN agents: Require explicit approval
    - SUPERVISED/AUTONOMOUS: Must meet min_maturity requirement
    - Banned packages: Always blocked
    """
    try:
        result = governance.check_package_permission(agent_id, package_name, version, db)

        logger.info(
            f"Package check: agent={agent_id}, package={package_name}@{version}, "
            f"allowed={result['allowed']}, maturity_required={result['maturity_required']}"
        )

        return result

    except Exception as e:
        logger.error(f"Error checking package permission: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/request")
def request_package_approval(
    request: PackageRequest,
    db: Session = Depends(get_db)
):
    """
    Request approval for a package version.

    Creates or updates package registry entry with status='pending'.
    Admins can then review and approve via POST /api/packages/approve.
    """
    try:
        package = governance.request_package_approval(
            package_name=request.package_name,
            version=request.version,
            requested_by=request.requested_by,
            reason=request.reason,
            db=db
        )

        logger.info(
            f"Package approval requested: {request.package_name}@{request.version} "
            f"by {request.requested_by}"
        )

        return {
            "package_id": package.id,
            "status": package.status,
            "message": "Package approval request created"
        }

    except Exception as e:
        logger.error(f"Error requesting package approval: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approve")
def approve_package(
    request: PackageApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Approve package for specified maturity level (admin endpoint).

    Grants permission for agents at or above the specified maturity level.
    Invalidates cache to ensure immediate effect.

    Requires admin privileges (implement authorization middleware).
    """
    try:
        package = governance.approve_package(
            package_name=request.package_name,
            version=request.version,
            min_maturity=request.min_maturity,
            approved_by=request.approved_by,
            db=db
        )

        logger.info(
            f"Package approved: {request.package_name}@{request.version} "
            f"for maturity {request.min_maturity}+ by {request.approved_by}"
        )

        return {
            "package_id": package.id,
            "status": package.status,
            "min_maturity": package.min_maturity,
            "approved_by": package.approved_by,
            "approved_at": package.approved_at.isoformat() if package.approved_at else None,
            "message": "Package approved successfully"
        }

    except ValueError as e:
        logger.error(f"Invalid maturity level: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error approving package: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ban")
def ban_package(
    request: PackageBanRequest,
    db: Session = Depends(get_db)
):
    """
    Ban package version (admin endpoint).

    Banned packages are blocked for ALL agents regardless of maturity.
    Use for security vulnerabilities, malicious code, or policy violations.
    Invalidates cache to ensure immediate effect.

    Requires admin privileges (implement authorization middleware).
    """
    try:
        package = governance.ban_package(
            package_name=request.package_name,
            version=request.version,
            reason=request.reason,
            db=db
        )

        logger.warning(
            f"Package banned: {request.package_name}@{request.version} "
            f"reason: {request.reason}"
        )

        return {
            "package_id": package.id,
            "status": package.status,
            "ban_reason": package.ban_reason,
            "message": "Package banned successfully"
        }

    except Exception as e:
        logger.error(f"Error banning package: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=PackageListResponse)
def list_packages(
    status: Optional[str] = Query(None, description="Filter by status (untrusted, active, banned, pending)"),
    db: Session = Depends(get_db)
):
    """
    List all packages in registry.

    Returns paginated list of packages with governance status.
    Optionally filter by status (e.g., status=pending for approval queue).
    """
    try:
        packages = governance.list_packages(status=status, db=db)

        package_responses = [
            PackageResponse(
                id=p.id,
                name=p.name,
                version=p.version,
                min_maturity=p.min_maturity,
                status=p.status,
                ban_reason=p.ban_reason,
                approved_by=p.approved_by,
                approved_at=p.approved_at.isoformat() if p.approved_at else None
            )
            for p in packages
        ]

        logger.info(f"Listed {len(package_responses)} packages (status filter: {status})")

        return {
            "packages": package_responses,
            "count": len(package_responses)
        }

    except Exception as e:
        logger.error(f"Error listing packages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
def get_cache_stats():
    """
    Get package governance cache statistics.

    Returns cache performance metrics including hit rate, size, evictions.
    Useful for monitoring governance cache effectiveness.
    """
    try:
        stats = governance.get_cache_stats()

        logger.info(f"Cache stats retrieved: hit_rate={stats.get('hit_rate', 0)}%")

        return stats

    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
