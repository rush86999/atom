"""
Agent Status API Endpoints
Provides status monitoring for AI agents and task execution
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime
import uuid
import asyncio
import json
import os
from pathlib import Path

router = APIRouter()

# In-memory storage for agent status (for MVP)
AGENT_STATUS_FILE = Path(__file__).parent.parent / "agent_status.json"

class AgentTask(BaseModel):
    task_id: str
    agent_id: str
    status: str  # pending, running, completed, failed, cancelled
    progress: float = 0.0  # 0.0 to 1.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = {}

class AgentInfo(BaseModel):
    agent_id: str
    name: str
    type: str
    status: str  # idle, busy, offline
    last_active: Optional[datetime] = None
    current_task: Optional[str] = None
    capabilities: List[str] = []
    health_score: float = 1.0  # 0.0 to 1.0

def load_agent_status() -> Dict[str, Any]:
    """Load agent status from file"""
    if not AGENT_STATUS_FILE.exists():
        return {"agents": {}, "tasks": {}}

    try:
        with open(AGENT_STATUS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        return {"agents": {}, "tasks": {}}

def save_agent_status(data: Dict[str, Any]):
    """Save agent status to file"""
    try:
        with open(AGENT_STATUS_FILE, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        print(f"Error saving agent status: {e}")

@router.get("/agent/status/{task_id}", response_model=AgentTask)
async def get_agent_status(task_id: str):
    """Get status of a specific agent task"""
    data = load_agent_status()

    if task_id not in data.get("tasks", {}):
        # Return a default status for unknown tasks
        return AgentTask(
            task_id=task_id,
            agent_id="unknown",
            status="not_found",
            error_message="Task not found"
        )

    task_data = data["tasks"][task_id]
    return AgentTask(**task_data)

@router.get("/agent/status", response_model=List[AgentTask])
async def get_all_agent_tasks():
    """Get status of all agent tasks"""
    data = load_agent_status()

    tasks = []
    for task_data in data.get("tasks", {}).values():
        tasks.append(AgentTask(**task_data))

    return tasks

@router.get("/agents", response_model=List[AgentInfo])
async def get_all_agents():
    """Get information about all agents"""
    data = load_agent_status()

    agents = []
    for agent_data in data.get("agents", {}).values():
        agents.append(AgentInfo(**agent_data))

    return agents

@router.get("/agents/{agent_id}", response_model=AgentInfo)
async def get_agent_info(agent_id: str):
    """Get information about a specific agent"""
    data = load_agent_status()

    if agent_id not in data.get("agents", {}):
        # Create a default agent if not found
        default_agent = AgentInfo(
            agent_id=agent_id,
            name=f"Agent {agent_id}",
            type="general",
            status="idle",
            last_active=datetime.now(),
            capabilities=["text_processing", "analysis"]
        )

        # Save the default agent
        data.setdefault("agents", {})[agent_id] = default_agent.dict()
        save_agent_status(data)

        return default_agent

    agent_data = data["agents"][agent_id]
    return AgentInfo(**agent_data)

@router.post("/agent/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str, status: Dict[str, Any]):
    """Update agent heartbeat and status"""
    data = load_agent_status()

    # Update or create agent info
    agent_info = {
        "agent_id": agent_id,
        "name": status.get("name", f"Agent {agent_id}"),
        "type": status.get("type", "general"),
        "status": status.get("status", "idle"),
        "last_active": datetime.now(),
        "current_task": status.get("current_task"),
        "capabilities": status.get("capabilities", []),
        "health_score": status.get("health_score", 1.0)
    }

    data.setdefault("agents", {})[agent_id] = agent_info
    save_agent_status(data)

    return {"status": "success", "timestamp": datetime.now()}

@router.post("/agent/task/{task_id}/update")
async def update_task_status(task_id: str, update: Dict[str, Any]):
    """Update status of a specific task"""
    data = load_agent_status()

    if task_id not in data.get("tasks", {}):
        raise HTTPException(status_code=404, detail="Task not found")

    # Update task fields
    task_data = data["tasks"][task_id]

    if "status" in update:
        task_data["status"] = update["status"]
        if update["status"] == "running" and not task_data.get("started_at"):
            task_data["started_at"] = datetime.now().isoformat()
        elif update["status"] in ["completed", "failed", "cancelled"]:
            task_data["completed_at"] = datetime.now().isoformat()

    if "progress" in update:
        task_data["progress"] = update["progress"]

    if "error_message" in update:
        task_data["error_message"] = update["error_message"]

    if "result" in update:
        task_data["result"] = update["result"]

    data["tasks"][task_id] = task_data
    save_agent_status(data)

    return {"status": "success"}

@router.post("/agent/task")
async def create_task(task: AgentTask):
    """Create a new agent task"""
    data = load_agent_status()

    # Set timestamps
    if not task.started_at and task.status == "running":
        task.started_at = datetime.now()

    # Convert to dict and save
    task_dict = task.dict()
    task_dict["started_at"] = task_dict["started_at"].isoformat() if task_dict["started_at"] else None
    task_dict["completed_at"] = task_dict["completed_at"].isoformat() if task_dict["completed_at"] else None

    data.setdefault("tasks", {})[task.task_id] = task_dict
    save_agent_status(data)

    return {"status": "success", "task_id": task.task_id}

@router.delete("/agent/task/{task_id}")
async def delete_task(task_id: str):
    """Delete a task"""
    data = load_agent_status()

    if task_id in data.get("tasks", {}):
        del data["tasks"][task_id]
        save_agent_status(data)
        return {"status": "success"}
    else:
        raise HTTPException(status_code=404, detail="Task not found")

@router.get("/agent/metrics")
async def get_agent_metrics():
    """Get agent performance metrics"""
    data = load_agent_status()

    total_agents = len(data.get("agents", {}))
    active_agents = len([
        a for a in data.get("agents", {}).values()
        if a.get("status") in ["running", "busy"]
    ])

    total_tasks = len(data.get("tasks", {}))
    completed_tasks = len([
        t for t in data.get("tasks", {}).values()
        if t.get("status") == "completed"
    ])
    failed_tasks = len([
        t for t in data.get("tasks", {}).values()
        if t.get("status") == "failed"
    ])

    return {
        "agents": {
            "total": total_agents,
            "active": active_agents,
            "idle": total_agents - active_agents
        },
        "tasks": {
            "total": total_tasks,
            "completed": completed_tasks,
            "failed": failed_tasks,
            "pending": total_tasks - completed_tasks - failed_tasks
        },
        "success_rate": completed_tasks / max(total_tasks, 1),
        "timestamp": datetime.now()
    }