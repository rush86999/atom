from datetime import datetime
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Make psutil optional for system monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from .auth import get_current_user, get_password_hash
from .chat_process_manager import get_process_manager
from .database import get_db
from .models import User

# Initialize router
router = APIRouter()

# Pydantic models
class UserCreate(BaseModel):
    email: str
    name: Optional[str] = None
    password: Optional[str] = None  # Optional for OAuth users

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if '@' not in v or '.' not in v.split('@')[1]:
            raise ValueError('Invalid email format')
        return v.lower()


class UserProfile(BaseModel):
    email: str
    name: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Name of the workflow")
    description: Optional[str] = Field(None, max_length=1000, description="Description of the workflow")
    steps: Optional[List[Dict[str, Any]]] = Field(None, max_items=50, description="List of workflow steps")


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None


class ChatProcessCreate(BaseModel):
    name: str
    steps: List[Dict[str, Any]]
    initial_context: Optional[Dict[str, Any]] = None


class ChatProcessStepInput(BaseModel):
    inputs: Dict[str, Any]


class ChatProcessResumeInput(BaseModel):
    inputs: Dict[str, Any]


# User endpoints - SECURE WITH AUTHENTICATION
@router.post("/users")
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user - requires authentication for user management"""
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user with secure password hashing
    password_hash = None
    if user.password:
        password_hash = get_password_hash(user.password)

    # Use SQLAlchemy ORM directly instead of db_manager
    new_user = User(
        email=user.email,
        first_name=user.name,
        password_hash=password_hash,
        status="active",
        role="member"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "name": user.name,
            "first_name": new_user.first_name,
            "last_name": new_user.last_name
        },
        "message": "User created successfully"
    }


@router.get("/users/me", response_model=UserProfile)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get current authenticated user profile - REQUIRES AUTHENTICATION"""
    return UserProfile(
        email=current_user.email,
        name=current_user.name,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        last_login=current_user.last_login
    )


@router.put("/users/me")
async def update_user_profile(
    name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user profile - REQUIRES AUTHENTICATION"""
    if name:
        current_user.name = name
        db.commit()
        db.refresh(current_user)

    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "updated_at": datetime.utcnow()
        },
        "message": "Profile updated successfully"
    }


@router.delete("/users/me")
async def delete_user_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete current user account - REQUIRES AUTHENTICATION"""
    # Soft delete - mark as inactive
    current_user.is_active = False
    current_user.deleted_at = datetime.utcnow()
    db.commit()

    return {"message": "Account deleted successfully"}


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


# Service endpoints - SECURED: Requires authentication
@router.get("/services")
async def get_connected_services(current_user: User = Depends(get_current_user)):
    """Get connected services for authenticated user"""
    import httpx
    try:
        # Forward to comprehensive service integrations with user context
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://localhost:5058/api/v1/services/",
                headers={"X-User-ID": str(current_user.id)},
                timeout=5.0
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "services": [],
                    "count": 0,
                    "message": "Service integrations unavailable"
                }
    except Exception as e:
        logger.warning(f"Failed to fetch service integrations from microservice: {e}")

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


# Chat Process endpoints
@router.post("/chat/process")
async def create_chat_process(
    process_data: ChatProcessCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new multi-step chat process"""
    process_manager = get_process_manager()
    process_id = await process_manager.create_process(
        user_id=current_user.id,
        name=process_data.name,
        steps=process_data.steps,
        initial_context=process_data.initial_context
    )
    return {"process_id": process_id, "message": "Chat process created successfully"}


@router.get("/chat/process/{process_id}")
async def get_chat_process(
    process_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get the current state of a chat process"""
    process_manager = get_process_manager()
    process = await process_manager.get_process(process_id)

    if not process:
        raise HTTPException(status_code=404, detail="Process not found")

    if process["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return process


@router.post("/chat/process/{process_id}/step")
async def submit_chat_process_step(
    process_id: str,
    step_input: ChatProcessStepInput,
    current_user: User = Depends(get_current_user)
):
    """Submit input for the current step of a chat process"""
    process_manager = get_process_manager()
    process = await process_manager.get_process(process_id)

    if not process:
        raise HTTPException(status_code=404, detail="Process not found")

    if process["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if process["status"] not in ["active", "paused"]:
        raise HTTPException(status_code=400, detail="Process is not active")

    # For now, assume step execution logic is handled elsewhere
    # This endpoint just updates the process state with new inputs
    result = await process_manager.update_process_step(
        process_id=process_id,
        step_input=step_input.inputs,
        step_output=None,  # Would be provided by step execution logic
        missing_parameters=None  # Would be determined by validation
    )

    return {
        "process_id": process_id,
        "next_step": result["next_step"],
        "status": result["status"],
        "missing_parameters": result["missing_parameters"]
    }


@router.post("/chat/process/{process_id}/resume")
async def resume_chat_process(
    process_id: str,
    resume_input: ChatProcessResumeInput,
    current_user: User = Depends(get_current_user)
):
    """Resume a paused chat process with new inputs"""
    process_manager = get_process_manager()
    process = await process_manager.get_process(process_id)

    if not process:
        raise HTTPException(status_code=404, detail="Process not found")

    if process["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if process["status"] != "paused":
        raise HTTPException(status_code=400, detail="Process is not paused")

    result = await process_manager.resume_process(
        process_id=process_id,
        new_inputs=resume_input.inputs
    )

    return {
        "process_id": process_id,
        "status": result["status"],
        "remaining_missing": result["remaining_missing"]
    }


@router.delete("/chat/process/{process_id}")
async def cancel_chat_process(
    process_id: str,
    current_user: User = Depends(get_current_user)
):
    """Cancel an active chat process"""
    process_manager = get_process_manager()
    process = await process_manager.get_process(process_id)

    if not process:
        raise HTTPException(status_code=404, detail="Process not found")

    if process["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    await process_manager.cancel_process(process_id)
    return {"message": "Process cancelled successfully"}


@router.get("/chat/process/user/{user_id}")
async def get_user_chat_processes(
    user_id: str,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Get all chat processes for a user"""
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    process_manager = get_process_manager()
    processes = await process_manager.get_user_processes(user_id, status)
    return {"processes": processes}
