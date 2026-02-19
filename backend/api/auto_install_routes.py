"""
Auto-Install API Routes - Automatic package installation.

Endpoints:
- POST /auto-install/install - Install dependencies for a skill
- POST /auto-install/batch - Batch install for multiple skills
- GET /auto-install/status/{skill_id} - Get installation status

Reference: Phase 60 Plan 04
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional

from core.database import get_db
from core.auto_installer_service import AutoInstallerService

router = APIRouter(prefix="/auto-install", tags=["auto-install"])


class InstallRequest(BaseModel):
    skill_id: str = Field(..., description="Skill ID for installation")
    packages: List[str] = Field(..., min_items=1, description="Package specifiers")
    package_type: str = Field("python", description="Package type: python or npm")
    agent_id: str = Field(..., description="Agent ID requesting installation")
    scan_for_vulnerabilities: bool = Field(True, description="Run security scan")


class BatchInstallRequest(BaseModel):
    installations: List[InstallRequest] = Field(..., min_items=1, description="Installation specs")
    agent_id: str = Field(..., description="Agent ID requesting installations")


@router.post("/install")
async def install_skill_dependencies(
    request: InstallRequest,
    db: Session = Depends(get_db)
):
    """Install dependencies for a single skill."""
    service = AutoInstallerService(db)

    result = await service.install_dependencies(
        skill_id=request.skill_id,
        packages=request.packages,
        package_type=request.package_type,
        agent_id=request.agent_id,
        scan_for_vulnerabilities=request.scan_for_vulnerabilities
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)

    return result


@router.post("/batch")
async def batch_install_dependencies(
    request: BatchInstallRequest,
    db: Session = Depends(get_db)
):
    """Install dependencies for multiple skills."""
    service = AutoInstallerService(db)

    installations = [
        {
            "skill_id": req.skill_id,
            "packages": req.packages,
            "package_type": req.package_type
        }
        for req in request.installations
    ]

    result = await service.batch_install(
        installations=installations,
        agent_id=request.agent_id
    )

    return result


@router.get("/status/{skill_id}")
def get_installation_status(
    skill_id: str,
    package_type: str = "python",
    db: Session = Depends(get_db)
):
    """Check if skill packages are installed (image exists)."""
    service = AutoInstallerService(db)

    image_tag = service._get_image_tag(skill_id, package_type)
    exists = service._image_exists(image_tag, package_type)

    return {
        "skill_id": skill_id,
        "package_type": package_type,
        "installed": exists,
        "image_tag": image_tag if exists else None
    }
