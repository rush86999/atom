
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import datetime
import asyncio
from core.database import SessionLocal 
from core.agent_world_model import WorldModelService, AgentExperience

from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator
from core.notification_manager import notification_manager
from core.models import User
from core.security_dependencies import require_permission
from core.rbac_service import Permission
from core.enterprise_security import enterprise_security, AuditEvent, EventType, SecurityLevel
from core.database import get_db
from sqlalchemy.orm import Session
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, AgentFeedback

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Data Models ---
class AgentRunRequest(BaseModel):
    parameters: Dict[str, Any] = {}

class AgentInfo(BaseModel):
    id: str
    name: str
    description: str
    status: str # idle, running, failed, success
    last_run: Optional[str] = None
    category: str

# --- Registry (Mock for MVP, real app would scan or register classes) ---
class AgentFeedbackRequest(BaseModel):
    user_correction: str
    input_context: Optional[str] = None
    original_output: str

# --- Endpoints ---

@router.get("/", response_model=List[AgentInfo])
async def list_agents(
    category: Optional[str] = None,
    user: User = Depends(require_permission(Permission.AGENT_VIEW)),
    db: Session = Depends(get_db)
):
    """List all available Computer Use Agents from Registry"""
    governance_service = AgentGovernanceService(db)
    agents_db = governance_service.list_agents(category)
    
    return [
        AgentInfo(
            id=a.id,
            name=a.name,
            description=a.description,
            status=a.status,
            last_run=None, # In real app, query AgentJob table
            category=a.category
        ) for a in agents_db
    ]

# --- Endpoints ---




@router.post("/{agent_id}/run")
async def run_agent(
    agent_id: str, 
    run_req: AgentRunRequest, 
    background_tasks: BackgroundTasks,
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
    db: Session = Depends(get_db)
):
    """Trigger an agent execution in the background"""
    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    # Check if agent is deprecated or paused
    if agent.status in [AgentStatus.DEPRECATED.value, AgentStatus.PAUSED.value]:
        raise HTTPException(status_code=400, detail=f"Agent is {agent.status}")
    
    if agent.status == "running": 
         raise HTTPException(status_code=409, detail="Agent is already running")

    # Run in background
    # We pass agent_id only, task will re-fetch to ensure fresh state/object access
    background_tasks.add_task(execute_agent_task, agent_id, run_req.parameters)
    
    return {"status": "started", "agent_id": agent_id}

@router.post("/{agent_id}/feedback")
async def submit_agent_feedback(
    agent_id: str,
    feedback: AgentFeedbackRequest,
    user: User = Depends(require_permission(Permission.AGENT_RUN)), # Members can submit feedback
    db: Session = Depends(get_db)
):
    """Submit feedback/corrections for an agent"""
    service = AgentGovernanceService(db)
    result = await service.submit_feedback(
        agent_id=agent_id,
        user_id=user.id,
        original_output=feedback.original_output,
        user_correction=feedback.user_correction,
        input_context=feedback.input_context
    )
    return {
        "status": "success", 
        "feedback_id": result.id, 
        "adjudication": result.status,
        "reasoning": result.ai_reasoning
    }

@router.post("/{agent_id}/promote")
async def promote_agent(
    agent_id: str,
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
    db: Session = Depends(get_db)
):
    """Promote agent to Autonomous mode"""
    service = AgentGovernanceService(db)
    agent = service.promote_to_autonomous(agent_id, user)
    return {"status": "success", "agent_status": agent.status}

async def execute_agent_task(agent_id: str, params: Dict[str, Any]):
    """Background task to run the agent logic"""
    # Create new DB session for background task
    db = SessionLocal() 
    try:
        agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if not agent:
            logger.error(f"Agent {agent_id} not found in background task")
            return

        logger.info(f"Starting agent {agent.name} (ID: {agent_id})...")
        
        # 1. World Model Retrieval
        wm_service = WorldModelService()
        
        # Build a context string from params to query memory
        task_context = f"Execute {agent.name} with params: {str(params)}"
        relevant_memories = await wm_service.recall_experiences(agent, task_context)
        
        if relevant_memories:
            logger.info(f"Agents {agent.name} found {len(relevant_memories)} relevant past experiences.")
            # In a real agent, we'd inject these into the prompt.
            # For now, we log them as 'Augmented Context'
            for mem in relevant_memories:
                logger.info(f"  [Memory] {mem.input_summary} -> {mem.learnings} ({mem.outcome})")

        # Dynamic Import
        module_name = agent.module_path
        class_name = agent.class_name
        
        try:
            mod = __import__(module_name, fromlist=[class_name])
            AgentClass = getattr(mod, class_name)
            
            # Instantiate
            agent_instance = AgentClass()
            
            # Determine method to call (Heuristic mapping)
            result = None
            # Need to re-map based on category or name since we lost specific ID keys if they changed
            # But the ID is still the PK.
            
            if agent_id == "competitive_intel":  # Use IDs that match seed data or created ones
                result = await agent_instance.track_competitor_pricing(
                    params.get("competitors", ["competitor-a", "competitor-b"]),
                    params.get("product", "widget-x")
                )
            elif agent_id == "inventory_reconcile":
                result = await agent_instance.reconcile_inventory(
                    params.get("skus", ["SKU-123", "SKU-999"])
                )
            elif agent_id == "payroll_guardian":
                result = await agent_instance.reconcile_payroll(
                    params.get("period", "2023-12")
                )
            else:
                # Generic fallback if class has 'run' method
                if hasattr(agent_instance, 'run'):
                    result = await agent_instance.run(params)
                else:
                    result = "Executed generic agent logic."

            # Success
            # Notify UI
            await notification_manager.broadcast({
                "type": "agent_status_change",
                "agent_id": agent_id,
                "status": "success",
                "result": result
            }, "default_workspace")
            
            # 2. Record Experience
            await wm_service.record_experience(AgentExperience(
                id=str(uuid.uuid4()),
                agent_id=agent.id,
                task_type=agent.class_name,
                input_summary=str(params),
                outcome="Success",
                learnings=f"Completed successfully. Result: {str(result)[:100]}...",
                agent_role=agent.category, # Using Category as Role Proxy
                specialty=None,
                timestamp=datetime.datetime.utcnow()
            ))
            
        except Exception as e:
            logger.error(f"Agent {agent_id} logic failed: {e}")
            
            # Record Failure
            await wm_service.record_experience(AgentExperience(
                id=str(uuid.uuid4()),
                agent_id=agent.id,
                task_type=agent.class_name,
                input_summary=str(params),
                outcome="Failure",
                learnings=f"Failed with error: {str(e)}",
                agent_role=agent.category,
                specialty=None,
                timestamp=datetime.datetime.utcnow()
            ))
            raise e

    except Exception as e:
        logger.error(f"Agent {agent_id} execution wrapper failed: {e}")
        
        # Urgent Notification (Phase 34 requirement)
        await notification_manager.send_urgent_notification(
            message=f"Agent execution FAILED: {str(e)}",
            workspace_id="default_workspace",
            channel="slack"
        )
        
        # Notify UI Status
        await notification_manager.broadcast({
            "type": "agent_status_change",
            "agent_id": agent_id,
            "status": "failed",
            "error": str(e)
        }, "default_workspace")
    finally:
        db.close()


# ==================== ATOM META-AGENT ENDPOINTS ====================

class AtomExecuteRequest(BaseModel):
    request: str
    context: Optional[Dict[str, Any]] = None

class AtomSpawnRequest(BaseModel):
    template: str  # e.g., "finance_analyst", "sales_assistant", "custom"
    custom_params: Optional[Dict[str, Any]] = None
    persist: bool = False

class AtomTriggerRequest(BaseModel):
    event_type: str
    data: Dict[str, Any]

@router.post("/atom/execute")
async def execute_atom(
    req: AtomExecuteRequest,
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
):
    """
    Execute the Atom Meta-Agent with a natural language request.
    Atom will analyze the request and spawn specialty agents as needed.
    """
    from core.atom_meta_agent import handle_manual_trigger
    
    result = await handle_manual_trigger(
        request=req.request,
        user=user,
        workspace_id="default"  # TODO: Get from user context
    )
    
    return result


@router.post("/spawn")
async def spawn_agent(
    req: AtomSpawnRequest,
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
):
    """
    Spawn a specialty agent on-demand from a template.
    """
    from core.atom_meta_agent import get_atom_agent
    
    atom = get_atom_agent()
    agent = await atom.spawn_agent(
        template_name=req.template,
        custom_params=req.custom_params,
        persist=req.persist
    )
    
    return {
        "status": "success",
        "agent_id": agent.id,
        "agent_name": agent.name,
        "category": agent.category,
        "persisted": req.persist
    }


@router.post("/atom/trigger")
async def trigger_atom_with_data(
    req: AtomTriggerRequest,
    # This endpoint may not require user auth if called by webhooks/internal systems
    # For now, require basic auth
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
):
    """
    Trigger Atom with new data (event-driven execution).
    Used for webhooks, ingestion events, integration callbacks.
    """
    from core.atom_meta_agent import handle_data_event_trigger
    
    result = await handle_data_event_trigger(
        event_type=req.event_type,
        data=req.data,
        workspace_id="default"
    )
    
    return result
