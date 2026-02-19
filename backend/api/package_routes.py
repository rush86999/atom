"""
Package Routes - REST API for Python package governance and management.

Endpoints:
Governance (Plan 01):
- GET /api/packages/check - Check package permission for agent
- POST /api/packages/request - Request package approval
- POST /api/packages/approve - Approve package (admin only)
- POST /api/packages/ban - Ban package version (admin only)
- GET /api/packages - List all packages in registry

Package Management (Plan 04):
- POST /api/packages/install - Install packages for skill
- POST /api/packages/execute - Execute skill with packages
- DELETE /api/packages/{skill_id} - Cleanup skill image
- GET /api/packages/{skill_id}/status - Get skill image status
- GET /api/packages/audit - List package operations

Governance enforcement happens in PackageGovernanceService with <1ms cache lookups.
Package installation happens in PackageInstaller with per-skill Docker image isolation.
"""

import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from packaging.requirements import Requirement

from core.package_governance_service import PackageGovernanceService
from core.package_dependency_scanner import PackageDependencyScanner
from core.package_installer import PackageInstaller
from core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()
_governance = None
_scanner = None
_installer = None


def get_governance():
    """Lazy load governance service."""
    global _governance
    if _governance is None:
        _governance = PackageGovernanceService()
    return _governance


def get_scanner():
    """Lazy load scanner."""
    global _scanner
    if _scanner is None:
        _scanner = PackageDependencyScanner()
    return _scanner


def get_installer():
    """Lazy load installer."""
    global _installer
    if _installer is None:
        _installer = PackageInstaller()
    return _installer


# ============================================================================
# Request/Response Models
# ============================================================================

class PackageCheckRequest(BaseModel):
    """Request to check package permission for an agent."""
    agent_id: str = Field(..., description="Agent ID requesting package access")
    package_name: str = Field(..., description="Python package name (e.g., 'numpy')")
    version: str = Field(..., description="Package version (e.g., '1.21.0')")


class NpmPackageCheckRequest(BaseModel):
    """Request to check npm package permission for an agent."""
    agent_id: str = Field(..., description="Agent ID requesting package access")
    package_name: str = Field(..., description="npm package name (e.g., 'lodash')")
    version: str = Field(..., description="Package version (e.g., '4.17.21')")


class PackageInstallRequest(BaseModel):
    """Request to install Python packages for a skill."""
    agent_id: str = Field(..., description="Agent ID requesting package installation")
    skill_id: str = Field(..., description="Skill identifier (for image tagging)")
    requirements: list[str] = Field(..., description="List of package specifiers (e.g., ['numpy==1.21.0', 'pandas>=1.3.0'])")
    scan_for_vulnerabilities: bool = Field(True, description="Run vulnerability scan before installation")
    base_image: str = Field("python:3.11-slim", description="Base Docker image")


class NpmPackageInstallRequest(BaseModel):
    """Request to install npm packages for a skill."""
    agent_id: str = Field(..., description="Agent ID requesting package installation")
    skill_id: str = Field(..., description="Skill identifier (for image tagging)")
    packages: list[str] = Field(..., description="List of npm package specifiers (e.g., ['lodash@4.17.21', 'express@^4.18.0'])")
    package_manager: str = Field("npm", description="Package manager: npm, yarn, or pnpm")
    scan_for_vulnerabilities: bool = Field(True, description="Run vulnerability scan before installation")
    base_image: str = Field("node:20-alpine", description="Base Node.js Docker image")


class PackageExecuteRequest(BaseModel):
    """Request to execute skill code with packages."""
    agent_id: str = Field(..., description="Agent ID executing skill")
    skill_id: str = Field(..., description="Skill identifier (must have called install first)")
    code: str = Field(..., description="Python code to execute")
    inputs: dict[str, Any] = Field(default_factory=dict, description="Input variables for execution")
    timeout_seconds: int = Field(30, description="Maximum execution time")
    memory_limit: str = Field("256m", description="Memory limit for container")
    cpu_limit: float = Field(0.5, description="CPU quota (0.5 = 50% of one core)")


class NpmPackageExecuteRequest(BaseModel):
    """Request to execute Node.js skill code with packages."""
    agent_id: str = Field(..., description="Agent ID executing skill")
    skill_id: str = Field(..., description="Skill identifier (must have called install first)")
    code: str = Field(..., description="Node.js code to execute")
    inputs: dict[str, Any] = Field(default_factory=dict, description="Input variables for execution")
    timeout_seconds: int = Field(30, description="Maximum execution time")
    memory_limit: str = Field("256m", description="Memory limit for container")
    cpu_limit: float = Field(0.5, description="CPU quota (0.5 = 50% of one core)")


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


class PackageInstallResponse(BaseModel):
    """Response from package installation."""
    success: bool = Field(..., description="Whether installation succeeded")
    skill_id: str = Field(..., description="Skill identifier")
    image_tag: str = Field(..., description="Docker image tag")
    packages_installed: list[dict[str, str]] = Field(..., description="List of installed packages")
    vulnerabilities: list[dict[str, Any]] = Field(..., description="Vulnerabilities found during scan")
    build_logs: list[str] = Field(..., description="Docker build logs")


class PackageExecuteResponse(BaseModel):
    """Response from package execution."""
    success: bool = Field(..., description="Whether execution succeeded")
    skill_id: str = Field(..., description="Skill identifier")
    output: str = Field(..., description="Execution output")


# ============================================================================
# Governance Endpoints (Plan 01)
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
        result = get_governance().check_package_permission(agent_id, package_name, version, db)

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
        package = get_governance().request_package_approval(
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
        package = get_governance().approve_package(
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
        package = get_governance().ban_package(
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
        packages = get_governance().list_packages(status=status, db=db)

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
        stats = get_governance().get_cache_stats()

        logger.info(f"Cache stats retrieved: hit_rate={stats.get('hit_rate', 0)}%")

        return stats

    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Package Management Endpoints (Plan 04)
# ============================================================================

@router.post("/install", response_model=PackageInstallResponse)
def install_packages(
    request: PackageInstallRequest,
    db: Session = Depends(get_db)
):
    """
    Install Python packages for skill in dedicated Docker image.

    Workflow:
    1. Check permissions for all packages using PackageGovernanceService
    2. Scan for vulnerabilities using PackageDependencyScanner
    3. Build Docker image with packages using PackageInstaller
    4. Return image tag and build logs

    Returns 403 if agent lacks maturity for any package.
    Returns 400 if vulnerabilities detected.

    Security: Each skill gets isolated image to prevent dependency conflicts.
    """
    package_specs = []

    # Step 1: Parse requirements and check permissions
    for req_str in request.requirements:
        try:
            req = Requirement(req_str)
            name = req.name
            # Get version specifier (e.g., "==1.21.0", ">=1.3.0", or "latest" if none)
            version_spec = str(req.specifier) if req.specifier else "latest"

            # Check permission for each package
            permission = get_governance().check_package_permission(
                request.agent_id,
                name,
                version_spec,
                db
            )

            if not permission["allowed"]:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "Package permission denied",
                        "package": name,
                        "version": version_spec,
                        "reason": permission["reason"]
                    }
                )

            package_specs.append({
                "name": name,
                "version": version_spec,
                "original": req_str
            })

            logger.info(f"Permission granted for {name}@{version_spec} to agent {request.agent_id}")

        except Exception as e:
            if "Package permission denied" in str(e):
                raise
            raise HTTPException(
                status_code=400,
                detail={"error": f"Invalid requirement '{req_str}': {str(e)}"}
            )

    # Step 2: Install packages (includes vulnerability scanning if enabled)
    result = get_installer().install_packages(
        skill_id=request.skill_id,
        requirements=request.requirements,
        scan_for_vulnerabilities=request.scan_for_vulnerabilities,
        base_image=request.base_image
    )

    if not result["success"]:
        # Determine appropriate status code
        if "Vulnerabilities detected" in result.get("error", ""):
            status_code = 400
        else:
            status_code = 500

        raise HTTPException(
            status_code=status_code,
            detail={
                "error": result["error"],
                "vulnerabilities": result.get("vulnerabilities", [])
            }
        )

    logger.info(
        f"Successfully installed {len(package_specs)} packages for skill {request.skill_id}, "
        f"image: {result['image_tag']}"
    )

    return {
        "success": True,
        "skill_id": request.skill_id,
        "image_tag": result["image_tag"],
        "packages_installed": package_specs,
        "vulnerabilities": result.get("vulnerabilities", []),
        "build_logs": result.get("build_logs", [])
    }


@router.post("/execute", response_model=PackageExecuteResponse)
def execute_with_packages(
    request: PackageExecuteRequest,
    db: Session = Depends(get_db)
):
    """
    Execute skill code using its dedicated image with pre-installed packages.

    Skill must have called POST /install first to build image.

    Returns 404 if skill image not found.
    Returns execution output or error message.

    Security: Executes in isolated container with resource limits.
    """
    try:
        output = get_installer().execute_with_packages(
            skill_id=request.skill_id,
            code=request.code,
            inputs=request.inputs,
            timeout_seconds=request.timeout_seconds,
            memory_limit=request.memory_limit,
            cpu_limit=request.cpu_limit
        )

        logger.info(f"Successfully executed skill {request.skill_id} with packages")

        return {
            "success": True,
            "skill_id": request.skill_id,
            "output": output
        }

    except RuntimeError as e:
        if "not found" in str(e):
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Skill image not found",
                    "skill_id": request.skill_id,
                    "message": "Run POST /api/packages/install first to build skill image"
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail={"error": str(e)}
            )
    except Exception as e:
        logger.error(f"Error executing skill {request.skill_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": f"Execution failed: {str(e)}"}
        )


@router.delete("/{skill_id}")
def cleanup_skill_image(
    skill_id: str,
    agent_id: str = Query(..., description="Agent ID requesting cleanup")
):
    """
    Remove skill's Docker image to free disk space.

    Image must not be in use by active executions.

    Returns success even if image not found (idempotent).
    """
    success = get_installer().cleanup_skill_image(skill_id)

    if success:
        logger.info(f"Agent {agent_id} cleaned up image for skill {skill_id}")
        return {
            "success": True,
            "skill_id": skill_id,
            "message": "Image removed successfully"
        }
    else:
        logger.warning(f"Cleanup for skill {skill_id}: image not found or already removed")
        return {
            "success": False,
            "skill_id": skill_id,
            "message": "Image not found or already removed"
        }


@router.get("/{skill_id}/status")
def get_skill_image_status(skill_id: str):
    """
    Check if skill image exists and get image details.

    Returns image metadata (size, created_at, tags).

    Useful for checking if POST /install has been called for a skill.
    """
    import docker

    image_tag = f"atom-skill:{skill_id.replace('/', '-')}-v1"

    try:
        client = docker.from_env()
        image = client.images.get(image_tag)

        return {
            "skill_id": skill_id,
            "image_exists": True,
            "image_tag": image_tag,
            "size_bytes": image.attrs.get("Size", 0),
            "created": image.attrs.get("Created", ""),
            "tags": image.attrs.get("RepoTags", [])
        }

    except docker.errors.ImageNotFound:
        return {
            "skill_id": skill_id,
            "image_exists": False,
            "image_tag": image_tag,
            "message": "Image not found - run POST /api/packages/install first"
        }
    except Exception as e:
        logger.error(f"Error checking image status for {skill_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to check image status: {str(e)}"}
        )


@router.get("/audit")
def list_package_operations(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    skill_id: Optional[str] = Query(None, description="Filter by skill ID"),
    db: Session = Depends(get_db)
):
    """
    List package installation/execution operations from audit trail.

    Optional filters by agent_id or skill_id.

    Returns recent operations with metadata.
    """
    from core.models import SkillExecution

    query = db.query(SkillExecution)

    # Filter by skill source (community skills use packages)
    query = query.filter(SkillExecution.skill_source == "community")

    if agent_id:
        # Filter by agent_id in execution metadata (JSON field)
        query = query.filter(SkillExecution.metadata["agent_id"].astext == agent_id)

    if skill_id:
        query = query.filter(SkillExecution.skill_id == skill_id)

    operations = query.order_by(SkillExecution.created_at.desc()).limit(100).all()

    return {
        "operations": [
            {
                "id": op.id,
                "skill_id": op.skill_id,
                "agent_id": op.metadata.get("agent_id") if op.metadata else None,
                "status": op.status,
                "sandbox_enabled": op.sandbox_enabled,
                "created_at": op.created_at.isoformat()
            }
            for op in operations
        ],
        "count": len(operations)
    }
