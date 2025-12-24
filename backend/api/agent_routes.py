from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any
from pydantic import BaseModel
import contextlib
import logging

# Import Agents directly for this iteration
from operations.automations.competitive_intel import CompetitiveIntelWorkflow
from finance.automations.payroll_guardian import PayrollReconciliationWorkflow
from operations.automations.inventory_reconcile import InventoryReconciliationWorkflow

router = APIRouter()
logger = logging.getLogger(__name__)

class AgentRunRequest(BaseModel):
    parameters: Dict[str, Any] = {}

class AgentSchema(BaseModel):
    id: str
    name: str
    description: str
    category: str
    status: str = "idle"

# Registry of available agents
AGENTS = {
    "competitive_intel": {
        "name": "Competitive Intelligence",
        "description": "Scrapes competitor pricing and detects changes.",
        "category": "Operations",
        "class": CompetitiveIntelWorkflow,
        "default_params": {"competitor_name": "TestComp", "target_url": "about:blank"}
    },
    "payroll_guardian": {
        "name": "Payroll Guardian",
        "description": "Reconciles Payroll Portal vs Accounting Ledger.",
        "category": "Finance",
        "class": PayrollReconciliationWorkflow,
        "default_params": {"portal_url": "about:blank", "period": "2025-10"}
    },
    "inventory_omni": {
        "name": "Inventory Omni-Check",
        "description": "Reconciles Shopify vs WMS inventory counts.",
        "category": "Operations",
        "class": InventoryReconciliationWorkflow,
        "default_params": {"sku": "SKU-123", "shopify_url": "about:blank", "wms_url": "about:blank"}
    }
}

@router.get("/", response_model=List[AgentSchema])
async def list_agents():
    """List all available Computer Use Agents"""
    return [
        AgentSchema(
            id=key,
            name=val["name"],
            description=val["description"],
            category=val["category"]
        ) for key, val in AGENTS.items()
    ]

@router.post("/{agent_id}/run")
async def run_agent(agent_id: str, request: AgentRunRequest, background_tasks: BackgroundTasks):
    """Trigger an agent run manually"""
    if agent_id not in AGENTS:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent_def = AGENTS[agent_id]
    
    # Run in background to avoid blocking API
    background_tasks.add_task(execute_agent_task, agent_id, agent_def, request.parameters)
    
    return {"status": "started", "message": f"Agent {agent_def['name']} started"}

from core.scheduler import AgentScheduler
from core.database import SessionLocal
from core.models import AgentJob

class ScheduleRequest(BaseModel):
    cron_expression: str 

@router.post("/{agent_id}/schedule")
async def schedule_agent(agent_id: str, request: ScheduleRequest):
    """Schedule a recurring agent run"""
    if agent_id not in AGENTS:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    try:
        scheduler = AgentScheduler.get_instance()
        agent_def = AGENTS[agent_id]
        
        # We pass the execute_agent_task wrapper, but scheduler runs in separate thread/process
        # APScheduler typically needs a pickleable function. execute_agent_task is async.
        # Our scheduler wrapper handles the async conversion.
        # But we need to pass the function *reference*. 
        # Since execute_agent_task is defined below, we might need to move it up or reference it carefully.
        # However, AgentScheduler's managed_execution expects 'func', which is execute_agent_task.
        
        job_id = scheduler.schedule_job(
            agent_id, 
            request.cron_expression, 
            execute_agent_task, 
            # Args for execute_agent_task: agent_id, agent_def, params
            args=[agent_id, agent_def, agent_def["default_params"]] 
        )
        
        return {"status": "scheduled", "job_id": job_id, "cron": request.cron_expression}
    except Exception as e:
        logger.error(f"Scheduling failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history", response_model=List[Dict[str, Any]])
async def get_agent_history():
    """Get execution history for all agents"""
    db = SessionLocal()
    try:
        jobs = db.query(AgentJob).order_by(AgentJob.start_time.desc()).limit(50).all()
        return [{
            "id": job.id,
            "agent_id": job.agent_id,
            "status": job.status,
            "start_time": job.start_time,
            "end_time": job.end_time,
            "logs": job.logs,
            "result_summary": job.result_summary
        } for job in jobs]
    finally:
        db.close()

async def execute_agent_task(agent_id: str, agent_def: Dict, params: Dict):
    """Execution wrapper to run the agent logic"""
    try:
        logger.info(f"Starting execution for agent: {agent_id}")
        
        # Instantiate
        workflow_cls = agent_def["class"]
        agent_instance = workflow_cls()
        
        # Map parameters dynamically based on agent type
        result = None
        merged_params = {**agent_def["default_params"], **params}
        
        if agent_id == "competitive_intel":
            result = await agent_instance.run_surveillance(
                merged_params.get("competitor_name"), 
                merged_params.get("target_url")
            )
        elif agent_id == "payroll_guardian":
            result = await agent_instance.reconcile_payroll(
                merged_params.get("portal_url"),
                merged_params.get("period")
            )
        elif agent_id == "inventory_omni":
            result = await agent_instance.reconcile_sku(
                merged_params.get("sku"),
                merged_params.get("shopify_url"),
                merged_params.get("wms_url")
            )
            
        logger.info(f"Agent {agent_id} completed: {result}")
        return result # Return for scheduler logging
        
    except Exception as e:
        logger.error(f"Agent {agent_id} failed: {e}")
        raise e # Re-raise for scheduler logging
