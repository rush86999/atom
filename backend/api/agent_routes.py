
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from services.agent_service import agent_service

router = APIRouter(prefix="/api/agent", tags=["agent"])

class AgentRunRequest(BaseModel):
    goal: str
    mode: Optional[str] = "thinker"  # thinker, actor, tasker

class AgentStopRequest(BaseModel):
    task_id: str

@router.post("/run")
async def run_agent(request: AgentRunRequest):
    """
    Start a computer use agent task.
    """
    try:
        result = await agent_service.execute_task(request.goal, request.mode)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{task_id}")
async def get_agent_status(task_id: str):
    """
    Get the status and logs of a running agent task.
    """
    status = agent_service.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    return status

@router.post("/stop")
async def stop_agent(request: AgentStopRequest):
    """
    Stop a running agent task.
    """
    success = agent_service.stop_task(request.task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or not running")
    return {"message": "Task stopped successfully"}
