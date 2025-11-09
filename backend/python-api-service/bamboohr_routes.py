"""
ATOM BambooHR API Routes
Comprehensive HR management API endpoints
Following ATOM API patterns and standards
"""

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta
from loguru import logger
import asyncio
from pydantic import BaseModel

# Create router
bamboohr_router = APIRouter(prefix="/api/bamboohr", tags=["BambooHR"])

# BambooHR service import
from bamboohr_service import create_bamboohr_service
from db_oauth_bamboohr import create_bamboohr_tables, get_user_bamboohr_tokens

# Pydantic models for request/response
class EmployeeCreate(BaseModel):
    firstName: str
    lastName: str
    workEmail: str
    jobTitle: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None

class EmployeeUpdate(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    workEmail: Optional[str] = None
    jobTitle: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None

class TimeOffRequest(BaseModel):
    employeeId: str
    start: str
    end: str
    type: str
    notes: Optional[str] = None

# Dependency for database connection
async def get_db_pool():
    # This should be imported from main app
    from main_api_app import db_pool
    return db_pool

# Utility functions
async def get_user_id() -> str:
    """Get current user ID - in production, this would come from auth token"""
    return "demo-user"

async def get_bamboohr_service():
    """Get authenticated BambooHR service"""
    user_id = await get_user_id()
    db_pool = await get_db_pool()
    
    service = create_bamboohr_service(user_id)
    if not service:
        raise HTTPException(status_code=401, detail="BambooHR not authenticated")
    
    await service.initialize(db_pool)
    return service

# Health endpoint
@bamboohr_router.get("/health", summary="BambooHR health check")
async def health_check():
    """Check BambooHR service health"""
    try:
        db_pool = await get_db_pool()
        await create_bamboohr_tables(db_pool)
        
        return {
            "status": "healthy",
            "service": "bamboohr",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"BambooHR health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

# Authentication status
@bamboohr_router.get("/auth-status", summary="Check authentication status")
async def get_auth_status():
    """Check if BambooHR is authenticated"""
    try:
        user_id = await get_user_id()
        db_pool = await get_db_pool()
        
        tokens = get_user_bamboohr_tokens(db_pool, user_id)
        if tokens:
            return {
                "ok": True,
                "authenticated": True,
                "service": "bamboohr",
                "subdomain": tokens.get("subdomain")
            }
        else:
            return {
                "ok": True,
                "authenticated": False,
                "service": "bamboohr"
            }
    except Exception as e:
        logger.error(f"Failed to check auth status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Dashboard data
@bamboohr_router.get("/dashboard", summary="Get HR dashboard data")
async def get_dashboard():
    """Get comprehensive HR dashboard data"""
    try:
        service = await get_bamboohr_service()
        dashboard_data = await service.get_dashboard_data()
        
        return {
            "ok": True,
            "data": dashboard_data,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Employee management endpoints
@bamboohr_router.get("/employees", summary="Get all employees")
async def get_employees(
    limit: int = Query(50, ge=1, le=200, description="Number of employees to return"),
    department: Optional[str] = Query(None, description="Filter by department")
):
    """Get employee directory with optional filtering"""
    try:
        service = await get_bamboohr_service()
        result = await service.get_employee_directory(limit)
        
        # Apply department filter if provided
        if department and result.get("employees"):
            filtered_employees = [
                emp for emp in result["employees"]
                if emp.get("department", "").lower() == department.lower()
            ]
            result["employees"] = filtered_employees
            result["total"] = len(filtered_employees)
        
        return {
            "ok": True,
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get employees: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@bamboohr_router.get("/employees/search", summary="Search employees")
async def search_employees(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Number of results to return")
):
    """Search employees by name or email"""
    try:
        service = await get_bamboohr_service()
        result = await service.search_employees(q)
        
        return {
            "ok": True,
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to search employees: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Register routes function
def register_bamboohr_routes(app):
    """Register BambooHR routes"""
    app.include_router(bamboohr_router)
    logger.info("BambooHR API routes registered")