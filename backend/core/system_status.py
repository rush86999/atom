from datetime import datetime
import os
import time
from typing import Any, Dict, List

try:
    import psutil
except ImportError:
    psutil = None
from fastapi import APIRouter, HTTPException

router = APIRouter()

class SystemStatus:
    """System status monitoring class"""

    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """Get system information"""
        try:
            return {
                "platform": {
                    "system": os.uname().sysname if hasattr(os, "uname") else "Unknown",
                    "node": os.uname().nodename if hasattr(os, "uname") else "Unknown",
                    "release": os.uname().release
                    if hasattr(os, "uname")
                    else "Unknown",
                    "version": os.uname().version
                    if hasattr(os, "uname")
                    else "Unknown",
                    "machine": os.uname().machine
                    if hasattr(os, "uname")
                    else "Unknown",
                },
                "python": {
                    "version": os.sys.version,
                    "implementation": os.sys.implementation.name,
                },
                "process": {
                    "pid": os.getpid(),
                    "create_time": datetime.fromtimestamp(
                        psutil.Process().create_time()
                    ).isoformat() if psutil else datetime.now().isoformat(),
                },
            }
        except Exception as e:
            return {"error": f"Failed to get system info: {str(e)}"}

    @staticmethod
    def get_resource_usage() -> Dict[str, Any]:
        """Get system resource usage"""
        try:
            if not psutil:
                return {"error": "psutil not installed"}
                
            process = psutil.Process()
            memory_info = process.memory_info()

            return {
                "cpu": {
                    "percent": psutil.cpu_percent(interval=0.1),
                    "count": psutil.cpu_count(),
                    "load_avg": os.getloadavg() if hasattr(os, "getloadavg") else "N/A",
                },
                "memory": {
                    "rss_mb": round(memory_info.rss / 1024 / 1024, 2),
                    "vms_mb": round(memory_info.vms / 1024 / 1024, 2),
                    "percent": process.memory_percent(),
                    "system_total_mb": round(
                        psutil.virtual_memory().total / 1024 / 1024, 2
                    ),
                    "system_available_mb": round(
                        psutil.virtual_memory().available / 1024 / 1024, 2
                    ),
                    "system_used_percent": psutil.virtual_memory().percent,
                },
                "disk": {
                    "total_gb": round(
                        psutil.disk_usage("/").total / 1024 / 1024 / 1024, 2
                    ),
                    "used_gb": round(
                        psutil.disk_usage("/").used / 1024 / 1024 / 1024, 2
                    ),
                    "free_gb": round(
                        psutil.disk_usage("/").free / 1024 / 1024 / 1024, 2
                    ),
                    "percent": psutil.disk_usage("/").percent,
                },
            }
        except Exception as e:
            return {"error": f"Failed to get resource usage: {str(e)}"}

    @staticmethod
    def get_service_status() -> Dict[str, Any]:
        """Get status of ATOM services"""
        services = {
            "backend_api": {
                "name": "Backend API",
                "port": 8000,
                "health_endpoint": "http://localhost:8000/health",
            },
            "oauth_server": {
                "name": "OAuth Server",
                "port": 5058,
                "health_endpoint": "http://localhost:5058/healthz",
            },
            "frontend": {
                "name": "Frontend",
                "port": 3000,
                "health_endpoint": "http://localhost:3000",
            },
        }

        import requests
        from requests.exceptions import RequestException

        service_status = {}

        for service_id, service_info in services.items():
            try:
                response = requests.get(
                    service_info["health_endpoint"],
                    timeout=5,
                    headers={"User-Agent": "ATOM-System-Status"},
                )

                service_status[service_id] = {
                    "name": service_info["name"],
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "status_code": response.status_code,
                    "response_time_ms": round(
                        response.elapsed.total_seconds() * 1000, 2
                    ),
                    "last_checked": datetime.now().isoformat(),
                }

            except RequestException as e:
                service_status[service_id] = {
                    "name": service_info["name"],
                    "status": "unreachable",
                    "error": str(e),
                    "last_checked": datetime.now().isoformat(),
                }

        return service_status

    @staticmethod
    def get_feature_status() -> Dict[str, Any]:
        """Get status of ATOM features"""
        return {
            "byok_system": {
                "status": "operational",
                "providers": 5,
                "description": "Bring Your Own Key AI Provider System",
            },
            "service_registry": {
                "status": "operational",
                "services_registered": 6,
                "description": "Service Integration Registry",
            },
            "workflow_system": {
                "status": "operational",
                "templates_available": 3,
                "description": "Natural Language Workflow Automation",
            },
            "oauth_integrations": {
                "status": "operational",
                "integrations_available": 33,
                "description": "OAuth Service Integrations",
            },
        }

    @staticmethod
    def get_overall_status() -> str:
        """Calculate overall system status"""
        try:
            service_status = SystemStatus.get_service_status()

            # Count healthy services
            healthy_count = sum(
                1
                for service in service_status.values()
                if service.get("status") in ["healthy", "operational"]
            )
            total_count = len(service_status)

            if healthy_count == total_count:
                return "healthy"
            elif healthy_count >= total_count * 0.7:  # 70% healthy
                return "degraded"
            else:
                return "unhealthy"

        except Exception:
            return "unknown"


@router.get("/api/system/status")
async def get_system_status():
    """Get comprehensive system status"""
    try:
        timestamp = datetime.now().isoformat()

        status_data = {
            "timestamp": timestamp,
            "overall_status": SystemStatus.get_overall_status(),
            "system": SystemStatus.get_system_info(),
            "resources": SystemStatus.get_resource_usage(),
            "services": SystemStatus.get_service_status(),
            "features": SystemStatus.get_feature_status(),
            "uptime": {
                "process_seconds": round(
                    time.time() - psutil.Process().create_time(), 2
                ) if psutil else 0,
                "system_seconds": round(time.time() - psutil.boot_time(), 2) if psutil else 0,
            },
            "version": {"api": "1.0.0", "platform": "ATOM v1.0.0"},
        }

        return status_data

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get system status: {str(e)}"
        )


@router.get("/api/system/health")
async def get_system_health():
    """Quick health check endpoint"""
    try:
        overall_status = SystemStatus.get_overall_status()

        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "message": "ATOM System Health Check",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "error": str(e)
        }

@router.get("/metrics")
async def get_metrics():
    """Get system metrics for monitoring"""
    try:
        resources = SystemStatus.get_resource_usage()
        # Return simple text format for E2E test
        return (
            f"# HELP system_cpu_usage System CPU usage percent\n"
            f"# TYPE system_cpu_usage gauge\n"
            f"system_cpu_usage {resources.get('cpu', {}).get('percent', 0)}\n"
            f"# HELP system_memory_usage System memory usage percent\n"
            f"# TYPE system_memory_usage gauge\n"
            f"system_memory_usage {resources.get('memory', {}).get('percent', 0)}\n"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

