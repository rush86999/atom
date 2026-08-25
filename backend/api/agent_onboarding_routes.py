"""
Employee-friendly agent onboarding and automation suggestions.

Design goal (per Brennan Machinery product direction):
- ANY employee (not just admins) can create an agent by describing the job
  in plain language. The guided factory designs the agent; it always starts
  at STUDENT maturity so it is spoon-fed until it graduates.
- Workflow automation suggestions are mined from real workspace history.
- Autonomous agents can use the same endpoint on their own behalf,
  gated by their trust policy / maturity: if governance denies, an HITL
  approval is created (pause-and-ask, never silent failure).
"""

import logging
from typing import Any, Dict, Optional

from fastapi import Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import User, get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.guided_automation_service import (
    get_automation_suggestion_service,
    get_guided_agent_factory,
)
from core.models import AgentRegistry, AgentStatus
from core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/agents", tags=["Agent Onboarding"])


class GuidedAgentRequest(BaseModel):
    """Plain-language agent creation request — one required field."""

    goal: str = Field(min_length=5, max_length=2000, description="What should this agent do, in plain language")
    context: Optional[str] = Field(None, max_length=4000, description="Optional extra context (tools, examples, constraints)")
    schedule_config: Optional[Dict[str, Any]] = None
    # Set when an AGENT (not a human employee) is creating on its own behalf.
    acting_agent_id: Optional[str] = None


class SuggestionCreateRequest(BaseModel):
    """Create a workflow/agent directly from a suggestion."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    trigger: Optional[str] = None
    steps: Optional[list] = None


@router.post("/guided", status_code=201)
async def create_guided_agent(
    req: GuidedAgentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create an agent from a plain-language goal. Available to any employee.

    No AGENT_MANAGE permission required — this is the self-serve on-ramp.
    The generated agent always starts at STUDENT maturity (guided/HITL-gated)
    regardless of who created it.

    When `acting_agent_id` is set, an agent is creating this helper itself:
    its trust policy decides create-now vs. HITL approval. AUTONOMOUS agents
    create directly; lower maturities get a pending approval instead.
    """
    workspace_id = getattr(current_user, "workspace_id", None) or "default"
    tenant_id = getattr(current_user, "tenant_id", None) or "default"

    # --- Trust/maturity gate for agent-initiated creation ---
    if req.acting_agent_id:
        governance = ServiceFactory.get_governance_service(db, workspace_id=workspace_id, tenant_id=tenant_id)
        decision = await governance.can_perform_action_async(
            agent_id=req.acting_agent_id,
            action_type="create_agent",
        )
        allowed = decision.get("allowed", False) if isinstance(decision, dict) else bool(decision)
        if not allowed:
            reason = (decision.get("reason") if isinstance(decision, dict) else None) or "Trust policy requires human approval for agent creation"
            hitl_action_id = None
            try:
                hitl_action_id = governance.request_approval(
                    agent_id=req.acting_agent_id,
                    action_type="create_agent",
                    params={
                        "goal": req.goal,
                        "context": req.context,
                        "created_by_user": str(getattr(current_user, "id", "unknown")),
                        "tenant_id": tenant_id,
                    },
                    reason=reason,
                )
            except Exception as e:
                logger.error(f"Failed to create HITL action for guided agent creation: {e}")
            # 202 Accepted: creation is queued behind human review, not done.
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=202,
                content=router.success_response(
                    data={
                        "status": "pending_approval",
                        "hitl_action_id": hitl_action_id,
                        "reason": reason,
                    },
                    message="Agent creation requires human approval — request queued for review",
                ),
            )

    # --- Design the agent from the goal ---
    factory = get_guided_agent_factory()
    blueprint = await factory.design_agent(goal=req.goal, context=req.context)

    configuration = blueprint.get("configuration") or {}
    if not isinstance(configuration, dict):
        configuration = {}
    # Learning contract: the Atom meta agent is the designated teacher (fast
    # pathway), but observation of workspace events is a first-class pathway
    # too — teaching accelerates, it does not gate. Promotion to higher
    # maturity still goes through the training/graduation system.
    configuration["learning"] = {
        "teacher_agent_id": "atom_main",
        "pathways": ["teacher", "observation"],
    }

    registry_entry = AgentRegistry(
        name=blueprint["name"],
        description=blueprint["description"],
        category=blueprint["category"],
        capabilities=blueprint.get("capabilities"),
        configuration=configuration,
        schedule_config=req.schedule_config,
        module_path="core.generic_agent",
        class_name="GenericAgent",
        # Always spoon-fed to start: employees and autonomous agents alike
        # get a STUDENT that must graduate before acting unattended.
        status=AgentStatus.STUDENT.value,
        user_id=str(getattr(current_user, "id", "unknown")),
        workspace_id=workspace_id,
        tenant_id=tenant_id,
    )
    if req.acting_agent_id:
        registry_entry.parent_agent_id = req.acting_agent_id

    db.add(registry_entry)
    db.commit()
    db.refresh(registry_entry)

    if req.schedule_config and req.schedule_config.get("active"):
        try:
            from core.scheduler import AgentScheduler
            AgentScheduler.get_instance().schedule_agent(registry_entry.id, req.schedule_config)
        except Exception as e:
            logger.warning(f"Failed to schedule guided agent {registry_entry.id}: {e}")

    return router.success_response(
        data={
            "agent_id": registry_entry.id,
            "name": registry_entry.name,
            "category": registry_entry.category,
            "template": blueprint.get("template"),
            "maturity": AgentStatus.STUDENT.value,
            "created_by": "agent" if req.acting_agent_id else "employee",
        },
        message=f"Agent '{registry_entry.name}' created — it starts as a STUDENT and learns with guidance",
    )


@router.get("/automation-suggestions")
async def get_automation_suggestions(
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Suggest workflow automations based on this workspace's real history.

    Mines frequent manual agent runs, frequently human-approved actions, and
    existing workflow volume, then proposes automations ranked by evidence.
    """
    workspace_id = getattr(current_user, "workspace_id", None) or "default"
    tenant_id = getattr(current_user, "tenant_id", None) or "default"

    service = get_automation_suggestion_service()
    result = await service.generate_suggestions(db, workspace_id=workspace_id, tenant_id=tenant_id, limit=limit)
    return router.success_response(
        data=result,
        message=f"{len(result.get('suggestions', []))} automation suggestions generated from workspace history",
    )
