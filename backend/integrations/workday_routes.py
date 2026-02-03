from fastapi import APIRouter, HTTPException

from integrations.workday_service import workday_service

router = APIRouter(prefix="/api/workday", tags=["Workday"])

@router.get("/workers/{worker_id}")
async def get_workday_worker(worker_id: str):
    """Retrieve worker profile from Workday"""
    return await workday_service.get_worker_profile(worker_id)

@router.get("/health")
async def workday_health():
    """Get Workday integration health"""
    return await workday_service.check_health()
