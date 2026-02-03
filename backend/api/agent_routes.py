
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import datetime
import asyncio
from core.database import SessionLocal, get_db_session
from core.agent_world_model import WorldModelService, AgentExperience

from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator
from core.notification_manager import notification_manager
from core.websockets import manager as ws_manager
from core.models import User
from core.security_dependencies import require_permission
from core.rbac_service import Permission
from core.enterprise_security import enterprise_security, AuditEvent, EventType, SecurityLevel
from core.database import get_db
from sqlalchemy.orm import Session
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, AgentFeedback, HITLAction, HITLActionStatus, AgentJob

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

class HITLApprovalRequest(BaseModel):
    decision: str # approved | rejected
    feedback: Optional[str] = None

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
    
    # Get last run times
    from sqlalchemy import func
    latest_jobs = db.query(AgentJob.agent_id, func.max(AgentJob.start_time).label('last_run'))\
        .group_by(AgentJob.agent_id)\
        .all()
    last_run_map = {job.agent_id: job.last_run.isoformat() for job in latest_jobs if job.last_run}

    return [
        AgentInfo(
            id=a.id,
            name=a.name,
            description=a.description,
            status=a.status,
            last_run=last_run_map.get(a.id),
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

    # Check if we should run synchronously (for testing)
    is_sync = run_req.parameters.get("sync", False)
    
    if is_sync:
        # Run immediately and return result
        # Note: calling execute_agent_task directly might have session issues if it creates its own session 
        # but execute_agent_task creates a SessionLocal(), so it is fine.
        # We need to capture the return value from execute_agent_task (which currently returns nothing/void, just logs/notifies).
        # We need to refactor execute_agent_task to return result if needed.
        # Let's import it or call the logic directly. 
        # Actually, let's just instantiate GenericAgent here if it's a generic agent to get the Result object?
        # Or better, refactor execute_agent_task to return the result.
        
        # Refactoring execute_agent_task is best.
        result = await execute_agent_task(agent_id, run_req.parameters)
        return {"status": "completed", "agent_id": agent_id, "result": result}

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

@router.get("/approvals/pending", response_model=List[Dict[str, Any]])
async def list_pending_approvals(
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
    db: Session = Depends(get_db)
):
    """List all actions waiting for human approval"""
    actions = db.query(HITLAction).filter(HITLAction.status == HITLActionStatus.PENDING.value).all()
    return [{
        "id": a.id,
        "agent_id": a.agent_id,
        "action_type": a.action_type,
        "params": a.params,
        "reason": a.reason,
        "created_at": a.created_at.isoformat() if a.created_at else None
    } for a in actions]

@router.post("/approvals/{action_id}")
async def decide_hitl_action(
    action_id: str,
    req: HITLApprovalRequest,
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
    db: Session = Depends(get_db)
):
    """Approve or Reject a paused agent action"""
    action = db.query(HITLAction).filter(HITLAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    
    if req.decision.lower() == "approved":
        action.status = HITLActionStatus.APPROVED.value
    else:
        action.status = HITLActionStatus.REJECTED.value
        
    action.user_feedback = req.feedback
    action.reviewed_at = datetime.datetime.now()
    action.reviewed_by = user.id
    
    db.commit()
    
    # Broadcast update to UI via WebSocket
    await ws_manager.broadcast("workspace:default", {
        "type": "hitl_decision",
        "action_id": action_id,
        "decision": action.status
    })
    
    return {"status": "success", "decision": action.status}

async def execute_agent_task(agent_id: str, params: Dict[str, Any]):
    """Background task to run the agent logic"""
    # Use context manager for background task
    with get_db_session() as db:
        result = None
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

            if isinstance(relevant_memories, dict):
                 # Extract the actual experiences list from the dictionary response
                 experiences = relevant_memories.get("experiences", [])

                 if experiences:
                    logger.info(f"Agents {agent.name} found {len(experiences)} relevant past experiences.")
                    for mem in experiences:
                        # Defensive check if mem is object or dict (mock vs real)
                        if hasattr(mem, "input_summary"):
                             logger.info(f"  [Memory] {mem.input_summary} -> {mem.learnings} ({mem.outcome})")
                        else:
                             logger.info(f"  [Memory] {str(mem)}")
            elif isinstance(relevant_memories, list):
                 # Legacy/Fallback support if it returns a list directly
                 logger.info(f"Agents {agent.name} found {len(relevant_memories)} relevant past experiences.")
                 for mem in relevant_memories:
                     if hasattr(mem, "input_summary"):
                        logger.info(f"  [Memory] {mem.input_summary} -> {mem.learnings} ({mem.outcome})")
                     else:
                        logger.info(f"  [Memory] {str(mem)}")

            # Dynamic Import
            # Unified Execution Logic using GenericAgent ReAct Loop
            from core.generic_agent import GenericAgent

            result = None
            try:
                # 1. Determine Tools based on Agent ID/Type (Migration compatibility)
                # If the agent is legacy and doesn't have tools configured, we inject them here.
                override_config = {}
                if agent.id == "competitive_intel":
                     override_config["tools"] = ["track_competitor_pricing"]
                     override_config["system_prompt"] = "You are a Competitive Intelligence Agent. Use the 'track_competitor_pricing' tool to gather market data."
                elif agent.id == "inventory_reconcile":
                     override_config["tools"] = ["reconcile_inventory"]
                     override_config["system_prompt"] = "You are an Inventory Manager. Use 'reconcile_inventory' to check for variance."
                elif agent.id == "payroll_guardian":
                     override_config["tools"] = ["reconcile_payroll"]
                     override_config["system_prompt"] = "You are a Payroll Guardian. Use 'reconcile_payroll' to verify accuracy."

                # 2. Instantiate Runtime
                if override_config:
                    if not agent.configuration:
                        agent.configuration = {}
                    # Merge defaults if not present
                    for k, v in override_config.items():
                        if k not in agent.configuration:
                            agent.configuration[k] = v

                runner = GenericAgent(agent)

                # 3. Determine Input
                # ReAct loop needs a natural language instruction.
                task_input = params.get("task_input") or params.get("request")

                # If input is missing but we have params, we construct a prompt
                if not task_input:
                    if agent.id == "competitive_intel":
                        task_input = f"Track pricing for {params.get('product', 'configured products')} against {params.get('competitors', 'competitors')}."
                    elif agent.id == "inventory_reconcile":
                        task_input = f"Reconcile inventory for {params.get('skus', 'all SKUs')}."
                    elif agent.id == "payroll_guardian":
                        task_input = f"Reconcile payroll for period {params.get('period', 'current')}."
                    else:
                         task_input = f"Execute task with params: {params}"

                # 4. Execute ReAct Loop with step streaming
                logger.info(f"Executing Agent {agent.name} with ReAct Loop. Input: {task_input}")

                async def streaming_callback(step_record):
                    await ws_manager.broadcast("workspace:default", {
                        "type": "agent_step_update",
                        "agent_id": agent_id,
                        "step": step_record
                    })

                result_obj = await runner.execute(task_input, context=params, step_callback=streaming_callback)

                # 5. Process Result
                result = result_obj

                # Success Notification
                await ws_manager.broadcast("workspace:default", {
                    "type": "agent_status_change",
                    "agent_id": agent_id,
                    "status": "success",
                    "result": result
                })

                # --- [NEW] External Bridge Response Routing ---
                source_platform = params.get("source_platform")
                recipient_id = params.get("recipient_id") or params.get("channel_id")

                if source_platform and recipient_id:
                    try:
                        from core.agent_integration_gateway import agent_integration_gateway, ActionType
                        final_output = result.get("final_output") if isinstance(result, dict) else str(result)

                        if final_output:
                            logger.info(f"Routing async agent result back to {source_platform}")
                            routing_params = {
                                "recipient_id": recipient_id,
                                "channel": params.get("channel_id") or recipient_id,
                                "content": f"✅ *{agent.name}* finished task:\n{final_output}",
                                "thread_ts": params.get("thread_ts")
                            }

                            # Phase 105: Include original sender for Agent-to-Agent loopback
                            if source_platform == "agent":
                                routing_params["sender_agent_id"] = params.get("agent_id") or params.get("sender_id")

                            await agent_integration_gateway.execute_action(
                                ActionType.SEND_MESSAGE,
                                source_platform,
                                routing_params
                            )
                    except Exception as route_err:
                        logger.error(f"Failed to route async agent result back to {source_platform}: {route_err}")

                # 6. Record Experience happens inside GenericAgent.execute() now.


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
            import traceback
            import sys
            error_msg = f"Agent execution FAILED: {str(e)}\n{traceback.format_exc()}"
            print(f"!!! CRITICAL AGENT ERROR !!!\n{error_msg}", file=sys.stderr)
            logger.error(f"Agent {agent_id} execution wrapper failed: {e}")

            # Urgent Notification (Phase 34 requirement)
            await notification_manager.send_urgent_notification(
                message=f"Agent execution FAILED: {str(e)}",
                workspace_id="default_workspace",
                channel="slack"
            )

            # Notify UI Status
            await ws_manager.broadcast("workspace:default", {
                "type": "agent_status_change",
                "agent_id": agent_id,
                "status": "failed",
                "error": str(e),
                "traceback": traceback.format_exc()
            })

        return result


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
    
    # Determine workspace from user context
    workspace_id = "default"

    result = await handle_manual_trigger(
        request=req.request,
        user=user,
        workspace_id=workspace_id
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
    return result

class CustomAgentRequest(BaseModel):
    name: str
    description: Optional[str] = "Custom Agent"
    category: str = "custom"
    configuration: Dict[str, Any]
    schedule_config: Optional[Dict[str, Any]] = None

@router.post("/custom")
async def create_custom_agent(
    req: CustomAgentRequest,
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
    db: Session = Depends(get_db)
):
    """Create a fully custom agent with configuration and schedule"""
    # 1. Create Agent
    registry_entry = AgentRegistry(
        name=req.name,
        description=req.description,
        category=req.category,
        configuration=req.configuration,
        schedule_config=req.schedule_config,
        module_path="core.generic_agent",
        class_name="GenericAgent",
        status=AgentStatus.STUDENT.value
    )
    db.add(registry_entry)
    db.commit()
    db.refresh(registry_entry)
    
    # 2. Schedule if needed
    if req.schedule_config and req.schedule_config.get("active"):
        from core.scheduler import AgentScheduler
        scheduler = AgentScheduler.get_instance()
        scheduler.schedule_agent(registry_entry.id, req.schedule_config)
        
    return {"status": "success", "agent_id": registry_entry.id}

@router.put("/{agent_id}")
async def update_agent(
    agent_id: str,
    req: CustomAgentRequest,
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
    db: Session = Depends(get_db)
):
    """Update an agent's config or schedule"""
    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    # Update fields
    agent.name = req.name
    agent.description = req.description
    agent.category = req.category
    agent.configuration = req.configuration
    agent.schedule_config = req.schedule_config
    
    db.commit()
    
    # Update Scheduler
    from core.scheduler import AgentScheduler
    scheduler = AgentScheduler.get_instance()
    # Ideally remove old job but for MVP we overwrite with new ID or let scheduler handle
    # A robust implementation would cancel the old job_id if we stored it
    if req.schedule_config and req.schedule_config.get("active"):
        scheduler.schedule_agent(agent.id, req.schedule_config)
    
    return {"status": "updated", "agent_id": agent.id}

@router.post("/{agent_id}/stop")
async def stop_agent(
    agent_id: str,
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
    db: Session = Depends(get_db)
):
    """
    Attempt to stop a running agent.
    Note: Async task cancellation is varying in reliability depending on the runner.
    For this implementation, we will mark the status in DB (if we tracked runs there) 
    or potentially signal the scheduler/meta-agent.
    """
    # For MVP, we'll log the request. In a full system, we'd look up the running task ID 
    # (stored in memory or Redis) and cancel the asyncio Task.
    logger.info(f"Stop request received for agent {agent_id} by user {user.id}")
    
    # Placeholder: if we had a task registry, we'd cancel it here.
    return {"status": "stop_requested", "message": "Signal sent to stop agent (Best Effort)."}
