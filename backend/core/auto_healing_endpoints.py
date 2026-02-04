"""
Auto-Healing API Endpoints
Expose health monitoring and auto-healing status via REST API
"""

from typing import Dict, List
from fastapi import APIRouter
from pydantic import BaseModel

from core.auto_healing import auto_healing_engine
from core.health_monitor import health_monitor
from core.token_refresher import token_refresher

router = APIRouter(prefix="/api/auto-healing", tags=["auto-healing"])

class ServiceHealthResponse(BaseModel):
    total_services: int
    healthy: int
    degraded: int
    unhealthy: int
    health_percentage: float
    services: List[Dict]
    last_updated: str

@router.get("/health", response_model=ServiceHealthResponse)
async def get_health_status():
    """Get current health status of all monitored services"""
    return health_monitor.get_health_summary()

@router.post("/health/check")
async def trigger_health_check():
    """Manually trigger health checks for all services"""
    results = await health_monitor.check_all_services()
    return {
        "message": f"Health check completed for {len(results)} services",
        "results": results
    }

@router.get("/circuit-breakers")
async def get_circuit_breaker_status():
    """Get status of all circuit breakers"""
    return {
        "circuit_breakers": auto_healing_engine.get_service_status()
    }

@router.get("/tokens")
async def get_token_status():
    """Get OAuth token refresh status"""
    return {
        "tokens": token_refresher.get_status()
    }

@router.post("/tokens/refresh")
async def trigger_token_refresh():
    """Manually trigger token refresh check for all services"""
    await token_refresher.check_and_refresh_all()
    return {
        "message": "Token refresh check completed",
        "status": token_refresher.get_status()
    }

@router.get("/status")
async def get_auto_healing_status():
    """Get comprehensive auto-healing system status"""
    return {
        "health_monitor": health_monitor.get_health_summary(),
        "circuit_breakers": auto_healing_engine.get_service_status(),
        "token_refresh": token_refresher.get_status()
    }
