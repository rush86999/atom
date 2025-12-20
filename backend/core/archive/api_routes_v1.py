from typing import List, Optional, Dict, Any
import time
from datetime import datetime
import os

# Make psutil optional for system monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .database_manager import db_manager

# Initialize router
router = APIRouter()

# Pydantic models
class UserCreate(BaseModel):
    email: str
    name: Optional[str] = None


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Name of the workflow")
    description: Optional[str] = Field(None, max_length=1000, description="Description of the workflow")
    steps: Optional[List[Dict[str, Any]]] = Field(None, max_items=50, description="List of workflow steps")


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None


# User endpoints
@router.post("/users")
async def create_user(user: UserCreate):
    new_user = await db_manager.create_user(user.email, user.name)
    return {"user": new_user, "message": "User created successfully"}


@router.get("/users/me")
async def get_current_user():
    return {"user": {"id": "current_user_id", "email": "user@example.com"}}


# Workflow endpoints - DEPRECATED: Moved to workflow_endpoints.py
# In-memory workflow storage (for testing - would use DB in production)
# _workflows = {}
# _workflow_counter = 0

# @router.post("/workflows")
# async def create_workflow(workflow: WorkflowCreate):
#     global _workflow_counter
#     _workflow_counter += 1
#     workflow_id = f"workflow_{_workflow_counter}"
#     
#     workflow_data = {
#         "id": workflow_id,
#         "name": workflow.name,
#         "description": workflow.description,
#         "steps": workflow.steps or [],
#         "created_at": "2025-11-18T23:00:00Z",
#         "status": "active"
#     }
#     
#     # Store workflow in memory
#     _workflows[workflow_id] = workflow_data
#     
#     return {"workflow": workflow_data}


# @router.get("/workflows")
# async def get_workflows():
#     return {"workflows": list(_workflows.values()), "count": len(_workflows)}


# @router.get("/workflows/{workflow_id}")
# async def get_workflow(workflow_id: str):
#     """Get workflow by ID - fixes critical retrieval bug"""
#     if workflow_id not in _workflows:
#         raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
#     return {"workflow": _workflows[workflow_id]}


# @router.post("/workflows/execute")
# async def execute_workflow(request: Dict[str, Any]):
#     """Execute a workflow by ID or definition"""
#     workflow_id = request.get("workflow_id")
#     
#     # Simulate execution
#     return {
#         "execution_id": f"exec_{int(time.time())}",
#         "workflow_id": workflow_id,
#         "status": "completed",
#         "result": {"success": True, "steps_completed": 3},
#         "started_at": datetime.now().isoformat(),
#         "completed_at": datetime.now().isoformat()
#     }


# @router.post("/workflows/{workflow_id}/execute")
# async def execute_workflow_by_id(workflow_id: str):
#     """Execute a workflow by ID (path parameter)"""
#     # Simulate execution
#     return {
#         "execution_id": f"exec_{int(time.time())}",
#         "workflow_id": workflow_id,
#         "status": "completed",
#         "result": {"success": True, "steps_completed": 3},
#         "started_at": datetime.now().isoformat(),
#         "completed_at": datetime.now().isoformat()
#     }



# DEPRECATED: Task endpoints moved to unified_task_endpoints.py
# These routes were causing conflicts with /api/v1/tasks unified endpoints
# @router.post("/tasks")
# async def create_task(task: TaskCreate):
#     return {"task": {"id": "task_1", "title": task.title}}

# @router.get("/tasks")
# async def get_tasks():
#     return {"tasks": [], "count": 0}


# Service endpoints - DEPRECATED: Use service_integrations.py for comprehensive 16-service support
@router.get("/services")
async def get_connected_services():
    """Redirect to comprehensive service integrations for full 16-service support"""
    import httpx
    try:
        # Forward to comprehensive service integrations
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:5058/api/v1/services/", timeout=5.0)
            if response.status_code == 200:
                return response.json()
    except Exception:
        pass

    # Fallback to basic service list
    services = ["github", "google", "slack", "outlook", "teams"]
    return {"services": services, "count": len(services)}


# Platform Status and Health Endpoints
@router.get("/status")
async def get_platform_status():
    """Get platform status with system metrics"""
    try:
        # Platform status
        status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "environment": os.getenv("NODE_ENV", "development"),
            "services": {
                "database": "connected",
                "api": "running",
                "integrations": "active"
            }
        }

        # Add system metrics if psutil is available
        if PSUTIL_AVAILABLE:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')

                status["uptime"] = time.time() - psutil.boot_time()
                status["system"] = {
                    "cpu_usage_percent": cpu_percent,
                    "memory": {
                        "total_gb": round(memory.total / (1024**3), 2),
                        "available_gb": round(memory.available / (1024**3), 2),
                        "percent_used": memory.percent
                    },
                    "disk": {
                        "total_gb": round(disk.total / (1024**3), 2),
                        "free_gb": round(disk.free / (1024**3), 2),
                        "percent_used": round((disk.used / disk.total) * 100, 2)
                    }
                }
            except Exception as e:
                status["system_monitoring_error"] = str(e)
                status["system"] = None
        else:
            status["system_monitoring"] = "disabled - psutil not available"
            status["system"] = None

        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "service": "atom-api"
    }


@router.get("/integrations")
async def get_integrations_list():
    """Get list of available integrations"""
    integrations = [
        {
            "name": "slack",
            "display_name": "Slack",
            "category": "communication",
            "status": "available"
        },
        {
            "name": "gmail",
            "display_name": "Gmail",
            "category": "email",
            "status": "available"
        },
        {
            "name": "github",
            "display_name": "GitHub",
            "category": "development",
            "status": "available"
        },
        {
            "name": "asana",
            "display_name": "Asana",
            "category": "project_management",
            "status": "available"
        },
        {
            "name": "jira",
            "display_name": "Jira",
            "category": "project_management",
            "status": "available"
        },
        {
            "name": "notion",
            "display_name": "Notion",
            "category": "productivity",
            "status": "available"
        },
        {
            "name": "trello",
            "display_name": "Trello",
            "category": "project_management",
            "status": "available"
        },
        {
            "name": "dropbox",
            "display_name": "Dropbox",
            "category": "storage",
            "status": "available"
        },
        {
            "name": "shopify",
            "display_name": "Shopify",
            "category": "ecommerce",
            "status": "available"
        },
        {
            "name": "plaid",
            "display_name": "Plaid",
            "category": "financial",
            "status": "available"
        },
        {
            "name": "linkedin",
            "display_name": "LinkedIn",
            "category": "social",
            "status": "available"
        },
        {
            "name": "lux",
            "display_name": "LUX Computer Use",
            "category": "automation",
            "status": "available"
        }
    ]

    return {
        "integrations": integrations,
        "count": len(integrations),
        "categories": list(set(i["category"] for i in integrations))
    }
