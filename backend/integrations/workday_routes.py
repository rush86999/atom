from fastapi import APIRouter, Depends, HTTPException

from integrations.workday_service import workday_service
from core.auth import get_current_user
from core.models import User

router = APIRouter(prefix="/api/workday", tags=["Workday"])

@router.get("/workers/{worker_id}")
async def get_workday_worker(worker_id: str, current_user: User = Depends(get_current_user)):
    """Retrieve worker profile from Workday"""
    return await workday_service.get_worker_profile(worker_id)

@router.get("/health")
async def workday_health():
    """Get Workday integration health"""
    return workday_service.health_check()
