from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

router = APIRouter(prefix="/api/v1/tasks", tags=["unified_tasks"])
project_router = APIRouter(prefix="/api/v1/projects", tags=["unified_projects"])

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

@router.get("/", response_model=Dict[str, Any])
async def get_tasks():
    return {"success": True, "tasks": MOCK_TASKS}

@router.post("/", response_model=Dict[str, Any])
async def create_task(task_data: CreateTaskRequest):
    new_task = Task(
        id=str(uuid.uuid4()),
        **task_data.dict(),
        createdAt=datetime.now(),
        updatedAt=datetime.now()
    )
    MOCK_TASKS.append(new_task)
    
    # Update project counts if applicable
    if new_task.project:
        for p in MOCK_PROJECTS:
            if p.id == new_task.project:
                p.task_count += 1
                break
                
    return {"success": True, "task": new_task}

@router.put("/{task_id}", response_model=Dict[str, Any])
async def update_task(task_id: str, updates: UpdateTaskRequest):
    for i, task in enumerate(MOCK_TASKS):
        if task.id == task_id:
            update_data = updates.dict(exclude_unset=True)
            updated_task = task.copy(update=update_data)
            updated_task.updatedAt = datetime.now()
            MOCK_TASKS[i] = updated_task
            return {"success": True, "task": updated_task}
    
    raise HTTPException(status_code=404, detail="Task not found")

@router.delete("/{task_id}", response_model=Dict[str, Any])
async def delete_task(task_id: str):
    global MOCK_TASKS
    task_to_delete = next((t for t in MOCK_TASKS if t.id == task_id), None)
    if not task_to_delete:
        raise HTTPException(status_code=404, detail="Task not found")
        
    MOCK_TASKS = [t for t in MOCK_TASKS if t.id != task_id]
    
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
