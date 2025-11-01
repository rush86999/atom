from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

router = APIRouter()

# Pydantic models
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    source: str  # github, google, slack
    priority: Optional[str] = "medium"
    due_date: Optional[datetime] = None

class Task(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: str  # pending, in_progress, completed
    source: str
    priority: str
    due_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None

@router.get("/tasks", response_model=Dict[str, Any])
async def get_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    source: Optional[str] = Query(None, description="Filter by source"),
    limit: int = Query(50, ge=1, le=200, description="Number of tasks")
) -> Dict[str, Any]:
    """Get all tasks from connected services"""
    
    # Mock tasks data
    tasks = [
        {
            "id": "task-1",
            "title": "Implement GitHub OAuth",
            "description": "Set up GitHub OAuth 2.0 authentication",
            "status": "in_progress",
            "source": "github",
            "priority": "high",
            "due_date": (datetime.now() + timedelta(days=2)).isoformat(),
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-15T00:00:00Z",
            "metadata": {
                "repository": "atom-auth",
                "assignee": "dev-team"
            }
        },
        {
            "id": "task-2",
            "title": "Design Automation Workflow",
            "description": "Create visual workflow builder interface",
            "status": "pending",
            "source": "google",
            "priority": "medium",
            "due_date": (datetime.now() + timedelta(days=5)).isoformat(),
            "created_at": "2024-01-10T00:00:00Z",
            "updated_at": "2024-01-10T00:00:00Z",
            "metadata": {
                "document_id": "workflow-design",
                "collaborators": ["team-a", "team-b"]
            }
        },
        {
            "id": "task-3",
            "title": "Review Slack Integration",
            "description": "Review and optimize Slack API integration",
            "status": "completed",
            "source": "slack",
            "priority": "low",
            "due_date": None,
            "created_at": "2024-01-05T00:00:00Z",
            "updated_at": "2024-01-12T00:00:00Z",
            "metadata": {
                "channel": "#dev-team",
                "message_count": 25
            }
        }
    ]
    
    # Apply filters
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    
    if source:
        tasks = [t for t in tasks if t["source"] == source]
    
    # Limit results
    limited_tasks = tasks[:limit]
    
    # Count status
    status_counts = {
        "pending": len([t for t in tasks if t["status"] == "pending"]),
        "in_progress": len([t for t in tasks if t["status"] == "in_progress"]),
        "completed": len([t for t in tasks if t["status"] == "completed"]),
        "total": len(tasks)
    }
    
    return {
        "tasks": limited_tasks,
        "total": len(tasks),
        "status_counts": status_counts,
        "filters": {
            "status": status,
            "source": source,
            "limit": limit
        },
        "timestamp": datetime.now().isoformat()
    }

@router.post("/tasks", response_model=Dict[str, Any])
async def create_task(task: TaskCreate) -> Dict[str, Any]:
    """Create a new task"""
    
    new_task = {
        "id": str(uuid.uuid4()),
        "title": task.title,
        "description": task.description,
        "status": "pending",
        "source": task.source,
        "priority": task.priority,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "metadata": {
            "created_by": "system",
            "version": "1.0"
        }
    }
    
    return {
        "task": new_task,
        "message": "Task created successfully",
        "status": "success",
        "timestamp": datetime.now().isoformat()
    }
