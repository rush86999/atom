from fastapi import APIRouter, HTTPException, Query, Body, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import asyncio
import os
import sys
import logging
from core.auth import get_current_user
from pathlib import Path

# Add parent directory to path for imports
backend_root = Path(__file__).parent.parent.resolve()
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

logger = logging.getLogger(__name__)

try:
    from integrations.asana_service import asana_service
    ASANA_AVAILABLE = True
    logger.info("Asana service loaded successfully")
except ImportError as e:
    ASANA_AVAILABLE = False
    asana_service = None
    logger.warning(f"Asana service not available: {e}")

router = APIRouter(prefix="/api/v1/tasks", tags=["unified_tasks"])
project_router = APIRouter(prefix="/api/v1/projects", tags=["unified_projects"])

# Configuration
ASANA_ACCESS_TOKEN = "2/1211551477617044/1211959900544452:04904fb3621a011e810dc1c21ef41890"
ASANA_WORKSPACE_GID = "1211551477617056"
ASANA_DEFAULT_PROJECT_GID = "1211551443885526"  # Cross-functional project plan

# --- Models ---

class Task(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    dueDate: datetime
    priority: str  # "high" | "medium" | "low"
    status: str  # "todo" | "in-progress" | "completed" | "blocked"
    project: Optional[str] = None
    tags: Optional[List[str]] = []
    assignee: Optional[str] = None
    estimatedHours: Optional[float] = 0
    actualHours: Optional[float] = 0
    dependencies: Optional[List[str]] = []
    platform: str = "local"  # "notion" | "trello" | "asana" | "jira" | "local"
    color: Optional[str] = "#3182CE"
    createdAt: datetime
    updatedAt: datetime
    metadata: Optional[Dict[str, Any]] = {}  # Store automation context (workflow_id, etc.)

class CreateTaskRequest(BaseModel):
    title: str
    description: Optional[str] = None
    dueDate: datetime
    priority: str = "medium"
    status: str = "todo"
    project: Optional[str] = None
    tags: Optional[List[str]] = []
    assignee: Optional[str] = None
    estimatedHours: Optional[float] = 0
    platform: str = "local"
    color: Optional[str] = "#3182CE"

class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    dueDate: Optional[datetime] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    project: Optional[str] = None
    tags: Optional[List[str]] = None
    assignee: Optional[str] = None
    estimatedHours: Optional[float] = None
    actualHours: Optional[float] = None
    platform: Optional[str] = None
    color: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class Project(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    color: str = "#3182CE"
    progress: float = 0
    task_count: int = 0

class CreateProjectRequest(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#3182CE"

class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None

# --- Mock Storage ---

MOCK_TASKS: List[Task] = [
    Task(
        id="1",
        title="Implement user authentication",
        description="Set up OAuth flow and user session management",
        dueDate=datetime(2025, 10, 25),
        priority="high",
        status="in-progress",
        project="project-1",
        tags=["backend", "security"],
        assignee="user1",
        estimatedHours=8,
        platform="local",
        color="#3182CE",
        createdAt=datetime(2025, 10, 18),
        updatedAt=datetime(2025, 10, 18),
    ),
    Task(
        id="2",
        title="Design dashboard UI",
        description="Create responsive dashboard components",
        dueDate=datetime(2025, 10, 22),
        priority="medium",
        status="todo",
        project="project-1",
        tags=["frontend", "design"],
        assignee="user2",
        estimatedHours=6,
        platform="local",
        color="#38A169",
        createdAt=datetime(2025, 10, 18),
        updatedAt=datetime(2025, 10, 18),
    ),
]

MOCK_PROJECTS: List[Project] = [
    Project(
        id="project-1",
        name="Web Application",
        description="Main web application development",
        color="#3182CE",
        progress=33,
        task_count=2
    ),
    Project(
        id="project-2",
        name="Documentation",
        description="Project documentation and guides",
        color="#38A169",
        progress=0,
        task_count=0
    ),
]

# --- Task Endpoints ---

@router.get("/")
async def get_tasks(platform: str = Query("all")):
    """Get tasks from specified platform or all platforms"""
    
    # If Asana is requested or all platforms, fetch from Asana
    if ASANA_AVAILABLE and platform in ["asana", "all"]:
        try:
            result = await asyncio.to_thread(
                asana_service._make_request,
                "GET",
                f"/projects/{ASANA_DEFAULT_PROJECT_GID}/tasks?opt_fields=name,notes,completed,due_on,assignee,tags,created_at,modified_at",
                ASANA_ACCESS_TOKEN
            )
            
            if result and result.get("data"):
                # Convert Asana tasks to unified format
                asana_tasks = []
                for asana_task in result.get("data", []):
                    status = "completed" if asana_task.get("completed") else "in-progress"
                    
                    # Parse dates safely
                    due_date = datetime.now()
                    if asana_task.get("due_on"):
                        try:
                            due_date = datetime.fromisoformat(asana_task["due_on"] + "T00:00:00")
                        except (ValueError, TypeError) as e:
                            logger.debug(f"Failed to parse due_date: {e}")
                    
                    created_at = datetime.now()
                    if asana_task.get("created_at"):
                        try:
                            created_str = asana_task["created_at"].replace("Z", "+00:00")
                            created_at = datetime.fromisoformat(created_str)
                        except (ValueError, TypeError) as e:
                            logger.debug(f"Failed to parse created_at: {e}")
                    
                    asana_tasks.append(Task(
                        id=asana_task.get("gid"),
                        title=asana_task.get("name"),
                        description=asana_task.get("notes", ""),
                        dueDate=due_date,
                        priority="medium",
                        status=status,
                        project=ASANA_DEFAULT_PROJECT_GID,
                        tags=[tag.get("name") for tag in asana_task.get("tags", [])],
                        assignee=asana_task.get("assignee", {}).get("name") if asana_task.get("assignee") else None,
                        estimatedHours=0,
                        actualHours=0,
                        dependencies=[],
                        platform="asana",
                        color="#3182CE",
                        createdAt=created_at,
                        updatedAt=created_at,
                    ))
                
                # Combine with mock tasks if "all" platforms
                if platform == "all":
                    all_tasks = asana_tasks + MOCK_TASKS
                else:
                    all_tasks = asana_tasks
                    
                return {"success": True, "tasks": all_tasks, "source": "asana"}
        except Exception as e:
            # Fall back to mock data on error
            logger.error(f"Error fetching Asana tasks: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    # Return mock tasks if Asana not available or error
    return {"success": True, "tasks": MOCK_TASKS, "source": "mock"}

@router.post("/", response_model=Dict[str, Any])
async def create_task(task_data: CreateTaskRequest, current_user: Any = Depends(get_current_user)):
    """Create a task in Asana or local mock system"""

    logger.info(f"CREATE_TASK called - Platform: {task_data.platform}, ASANA_AVAILABLE: {ASANA_AVAILABLE}")
    
    # If platform is Asana, create in Asana
    if task_data.platform == "asana" and ASANA_AVAILABLE:
        logger.info(f"[CREATE_TASK] Creating in Asana...")
        try:
            # Convert datetime to just date string
            due_date_str = task_data.dueDate.strftime("%Y-%m-%d") if isinstance(task_data.dueDate, datetime) else task_data.dueDate.split("T")[0]

            asana_task_data = {
                "name": task_data.title,
                "description": task_data.description or "",
                "due_on": due_date_str,
                "projects": [ASANA_DEFAULT_PROJECT_GID],
                "workspace": ASANA_WORKSPACE_GID,
            }

            logger.debug(f"[CREATE_TASK] Asana task data: {asana_task_data}")

            result = await asana_service.create_task(ASANA_ACCESS_TOKEN, asana_task_data)

            logger.info(f"[CREATE_TASK] Asana result: {result}")

            if result.get("ok"):
                asana_task = result.get("task")

                # Parse created_at and modified_at safely
                created_at = datetime.now()
                if asana_task.get("created_at"):
                    try:
                        # Remove milliseconds and Z for parsing
                        created_str = asana_task["created_at"].replace("Z", "+00:00")
                        created_at = datetime.fromisoformat(created_str)
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Failed to parse created_at: {e}")

                created_task = Task(
                    id=asana_task.get("gid"),
                    title=asana_task.get("name"),
                    description=asana_task.get("notes", ""),
                    dueDate=datetime.fromisoformat(asana_task.get("due_on") + "T00:00:00") if asana_task.get("due_on") else datetime.now(),
                    priority=task_data.priority,
                    status="todo",
                    project=ASANA_DEFAULT_PROJECT_GID,
                    tags=task_data.tags or [],
                    assignee=None,
                    estimatedHours=task_data.estimatedHours or 0,
                    platform="asana",
                    color=task_data.color,
                    createdAt=created_at,
                    updatedAt=datetime.now(),
                )
                logger.info(f"[CREATE_TASK] Successfully created in Asana: {created_task.id}")
                return {"success": True, "task": created_task, "platform": "asana"}
            else:
                logger.warning(f"[CREATE_TASK] Asana API returned not OK: {result}")
        except Exception as e:
            logger.error(f"[CREATE_TASK] Error creating Asana task: {e}")
            import traceback
            logger.error(traceback.format_exc())
            logger.info("[CREATE_TASK] Falling back to local mock task")
            # Don't raise, just fall through to local creation
            # raise HTTPException(status_code=500, detail=f"Failed to create Asana task: {str(e)}")
    
    # Otherwise create mock task locally
    logger.info(f"[CREATE_TASK] Creating local mock task")
    new_task = Task(
        id=str(uuid.uuid4()),
        **task_data.dict(),
        createdAt=datetime.now(),
        updatedAt=datetime.now()
    )
    MOCK_TASKS.append(new_task)
    
    if new_task.project:
        for p in MOCK_PROJECTS:
            if p.id == new_task.project:
                p.task_count += 1
                break
                
    # Log user action for behavior analysis
    from core.behavior_analyzer import get_behavior_analyzer
    analyzer = get_behavior_analyzer()
    analyzer.log_user_action(
        user_id=current_user.id,
        action_type="task_created",
        metadata={"task_id": new_task.id, "platform": new_task.platform}
    )
    
    return {"success": True, "task": new_task, "platform": "local"}

@router.put("/{task_id}", response_model=Dict[str, Any])
async def update_task(task_id: str, updates: UpdateTaskRequest, current_user: Any = Depends(get_current_user)):
    for i, task in enumerate(MOCK_TASKS):
        if task.id == task_id:
            update_data = updates.dict(exclude_unset=True)
            updated_task = task.copy(update=update_data)
            updated_task.updatedAt = datetime.now()
            MOCK_TASKS[i] = updated_task
            
            # Track manual override if this was an automated task
            if task.metadata and "workflow_id" in task.metadata:
                from core.workflow_analytics_engine import get_analytics_engine
                analytics = get_analytics_engine()
                analytics.track_manual_override(
                    workflow_id=task.metadata.get("workflow_id"),
                    execution_id=task.metadata.get("execution_id", "manual"),
                    resource_id=task_id,
                    action="task_updated",
                    user_id=current_user.id,
                    metadata={"updates": update_data}
                )
            
            return {"success": True, "task": updated_task}
    
    raise HTTPException(status_code=404, detail="Task not found")

@router.delete("/{task_id}", response_model=Dict[str, Any])
async def delete_task(task_id: str):
    global MOCK_TASKS
    task_to_delete = next((t for t in MOCK_TASKS if t.id == task_id), None)
    if not task_to_delete:
        raise HTTPException(status_code=404, detail="Task not found")
        
    MOCK_TASKS = [t for t in MOCK_TASKS if t.id != task_id]
    
    # Track manual override/deletion if this was an automated task
    if task_to_delete.metadata and "workflow_id" in task_to_delete.metadata:
        from core.workflow_analytics_engine import get_analytics_engine
        analytics = get_analytics_engine()
        analytics.track_manual_override(
            workflow_id=task_to_delete.metadata.get("workflow_id"),
            execution_id=task_to_delete.metadata.get("execution_id", "manual"),
            resource_id=task_id,
            action="task_deleted"
        )
    
    # Update project counts
    if task_to_delete.project:
        for p in MOCK_PROJECTS:
            if p.id == task_to_delete.project:
                p.task_count = max(0, p.task_count - 1)
                break
                
    return {"success": True, "id": task_id}

# --- Project Endpoints ---

@project_router.get("/", response_model=Dict[str, Any])
async def get_projects():
    # Recalculate progress/counts dynamically for accuracy
    for p in MOCK_PROJECTS:
        project_tasks = [t for t in MOCK_TASKS if t.project == p.id]
        p.task_count = len(project_tasks)
        if p.task_count > 0:
            completed = len([t for t in project_tasks if t.status == "completed"])
            p.progress = int((completed / p.task_count) * 100)
        else:
            p.progress = 0
            
    return {"success": True, "projects": MOCK_PROJECTS}

@project_router.post("/", response_model=Dict[str, Any])
async def create_project(project_data: CreateProjectRequest):
    new_project = Project(
        id=str(uuid.uuid4()),
        **project_data.dict(),
        progress=0,
        task_count=0
    )
    MOCK_PROJECTS.append(new_project)
    return {"success": True, "project": new_project}

@project_router.put("/{project_id}", response_model=Dict[str, Any])
async def update_project(project_id: str, updates: UpdateProjectRequest):
    for i, project in enumerate(MOCK_PROJECTS):
        if project.id == project_id:
            update_data = updates.dict(exclude_unset=True)
            updated_project = project.copy(update=update_data)
            MOCK_PROJECTS[i] = updated_project
            return {"success": True, "project": updated_project}
            
    raise HTTPException(status_code=404, detail="Project not found")
