from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    from .bamboohr_service import get_bamboohr_service, bamboohr_configured
    BAMBOOHR_AVAILABLE = True
except ImportError:
    BAMBOOHR_AVAILABLE = False

# Auth Type: API Key (basic auth with API key + 'x')
router = APIRouter(prefix="/api/bamboohr", tags=["bamboohr"])


class CreateEmployeeRequest(BaseModel):
    firstName: str
    lastName: str
    workEmail: Optional[str] = None
    jobTitle: Optional[str] = None


@router.get("/employees")
async def list_employees():
    """List employees from the BambooHR directory"""
    if not BAMBOOHR_AVAILABLE or not bamboohr_configured():
        return {
            "employees": [],
            "configured": bamboohr_configured() if BAMBOOHR_AVAILABLE else False,
            "message": "BambooHR not configured. Set BAMBOOHR_SUBDOMAIN and BAMBOOHR_API_KEY.",
            "timestamp": datetime.now().isoformat()
        }

    service = get_bamboohr_service()
    employees = await service.list_employees()
    return {
        "employees": employees,
        "count": len(employees),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/employees/{employee_id}")
async def get_employee(employee_id: str):
    """Get a single BambooHR employee by ID"""
    if not BAMBOOHR_AVAILABLE or not bamboohr_configured():
        return {"id": employee_id, "message": "BambooHR not configured (mock)"}

    service = get_bamboohr_service()
    return await service.get_employee(employee_id)


@router.post("/employees")
async def create_employee(request: CreateEmployeeRequest):
    """Create a BambooHR employee"""
    if not BAMBOOHR_AVAILABLE or not bamboohr_configured():
        return {
            "ok": True,
            "status": "success",
            "id": "mock_employee_id",
            "message": "Employee created (mock - BambooHR not configured)",
            "timestamp": datetime.now().isoformat()
        }

    service = get_bamboohr_service()
    result = await service.create_employee(
        first_name=request.firstName,
        last_name=request.lastName,
        work_email=request.workEmail,
        job_title=request.jobTitle,
    )
    return {
        "ok": True,
        "status": "success",
        "employee": result,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/time-off/requests")
async def get_time_off_requests(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Get BambooHR time-off requests"""
    if not BAMBOOHR_AVAILABLE or not bamboohr_configured():
        return {
            "requests": [],
            "configured": bamboohr_configured() if BAMBOOHR_AVAILABLE else False,
            "message": "BambooHR not configured (mock)",
            "timestamp": datetime.now().isoformat()
        }

    params = {}
    if start_date:
        params["start"] = start_date
    if end_date:
        params["end"] = end_date

    service = get_bamboohr_service()
    result = await service.get_time_off_requests(params=params or None)
    return result


@router.get("/status")
async def bamboohr_status():
    """Status check for BambooHR integration"""
    return {
        "status": "active",
        "service": "bamboohr",
        "version": "1.0.0",
        "available": BAMBOOHR_AVAILABLE,
        "configured": bamboohr_configured() if BAMBOOHR_AVAILABLE else False,
        "business_value": {
            "hr_management": True,
            "employee_directory": True,
            "time_off_tracking": True
        }
    }


@router.get("/health")
async def bamboohr_health():
    """Health check for BambooHR integration"""
    if BAMBOOHR_AVAILABLE:
        service = get_bamboohr_service()
        return await service.health_check()
    return await bamboohr_status()
