from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from database_manager import db_manager

# Initialize router
router = APIRouter()

# Pydantic models
class UserCreate(BaseModel):
    email: str
    name: Optional[str] = None

class WorkflowCreate(BaseModel):
    name: str
    description: Optional[str] = None

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

# Workflow endpoints
@router.post("/workflows")
async def create_workflow(workflow: WorkflowCreate):
    return {"workflow": {"id": "workflow_1", "name": workflow.name}}

@router.get("/workflows")
async def get_workflows():
    return {"workflows": [], "count": 0}

# Task endpoints
@router.post("/tasks")
async def create_task(task: TaskCreate):
    return {"task": {"id": "task_1", "title": task.title}}

@router.get("/tasks")
async def get_tasks():
    return {"tasks": [], "count": 0}

# Service endpoints
@router.get("/services")
async def get_connected_services():
    services = ["github", "google", "slack", "outlook", "teams"]
    return {"services": services, "count": len(services)}
