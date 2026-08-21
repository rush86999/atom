"""

Agent Governance API Routes

Exposes endpoints for frontend to query and interact with agent governance.

Used by AgentWorkflowGenerator.tsx to check maturity levels and approval requirements.

"""



from datetime import datetime, timezone

import logging

from typing import Any, Dict, List, Optional

from fastapi import Depends, Query

from fastapi import HTTPException

from pydantic import BaseModel

from sqlalchemy.orm import Session



from core.base_routes import BaseAPIRouter

from core.auth import get_current_user, User

from core.database import get_db, get_db_session



# R81: these endpoints previously served a hardcoded MOCK_AGENTS dict — the

# frontend maturity UI read fake data and /feedback was a documented no-op.

# They now query AgentRegistry and delegate decisions to AgentGovernanceService

# (same service the execution loops use), so displayed maturity and submitted

# feedback reflect — and feed — the real learning loop.

from core.agent_governance_service import AgentGovernanceService

from core.models import AgentRegistry



# Import newly created intervention service

from core.intervention_service import intervention_service

from core.models import User, UserRole



logger = logging.getLogger(__name__)



router = BaseAPIRouter(prefix="/api/agent-governance", tags=["Agent Governance"])





# ==================== Request/Response Models ====================



class AgentMaturityResponse(BaseModel):

    """Agent maturity status for frontend display"""

    agent_id: str

    name: str

    category: str

    maturity_level: str  # student, intern, supervised, autonomous

    confidence_score: float

    can_deploy_directly: bool

    requires_approval: bool

    description: Optional[str] = None





class WorkflowApprovalRequest(BaseModel):

    """Request to submit a workflow for approval"""

    agent_id: str

    workflow_name: str

    workflow_definition: Dict[str, Any]

    trigger_type: str

    actions: List[str]

    requested_by: str  # user_id





class WorkflowApprovalResponse(BaseModel):

    """Response after submitting workflow for approval"""

    approval_id: str

    status: str  # pending, approved, rejected

    requires_approval: bool

    can_deploy: bool

    message: str

    approver_role_required: Optional[str] = None





class AgentFeedbackRequest(BaseModel):

    """User feedback on agent output"""

    agent_id: str

    original_output: str

    user_correction: str

    input_context: Optional[str] = None





# ==================== Helper Functions ====================



def get_maturity_level_from_score(score: float) -> str:

    """Convert confidence score to maturity level string"""

    if score >= 0.9:

        return "autonomous"

    elif score >= 0.7:

        return "supervised"

    elif score >= 0.5:

        return "intern"

    else:

        return "student"





def can_deploy_directly(maturity_level: str, confidence_score: float) -> bool:

    """Determine if agent can deploy workflows without approval"""

    # Supervised (with high confidence) and Autonomous can deploy directly

    if maturity_level == "autonomous":

        return True

    if maturity_level == "supervised" and confidence_score >= 0.8:

        return True

    return False





# ==================== API Endpoints ====================



@router.get("/rules")

async def get_governance_rules(current_user: User = Depends(get_current_user)):

    """

    Get governance rules and maturity level definitions.

    Used by frontend to understand the governance framework.

    """

    return {

        "maturity_levels": {

            "student": {

                "description": "New agent, learning from examples",

                "confidence_threshold": 0.0,

                "max_complexity": 1,

                "allowed_actions": ["search", "read", "list", "get", "fetch", "summarize"],

                "requires_approval": True

            },

            "intern": {

                "description": "Basic proficiency, can suggest but not execute",

                "confidence_threshold": 0.5,

                "max_complexity": 2,

                "allowed_actions": ["analyze", "suggest", "draft", "generate", "recommend"],

                "requires_approval": True

            },

            "supervised": {

                "description": "Good performance, can execute with oversight",

                "confidence_threshold": 0.7,

                "max_complexity": 3,

                "allowed_actions": ["create", "update", "send_email", "post_message", "schedule"],

                "requires_approval": "for_complex_actions"

            },

            "autonomous": {

                "description": "Expert level, full autonomy",

                "confidence_threshold": 0.9,

                "max_complexity": 4,

                "allowed_actions": ["delete", "execute", "deploy", "transfer", "payment", "approve"],

                "requires_approval": False

            }

        },

        "action_complexity": {

            1: ["search", "read", "list", "get", "fetch", "summarize"],

            2: ["analyze", "suggest", "draft", "generate", "recommend"],

            3: ["create", "update", "send_email", "post_message", "schedule"],

            4: ["delete", "execute", "deploy", "transfer", "payment", "approve"]

        },

        "promotion_requirements": {

            "student_to_intern": {"min_executions": 50, "min_success_rate": 0.7},

            "intern_to_supervised": {"min_executions": 100, "min_success_rate": 0.8},

            "supervised_to_autonomous": {"min_executions": 200, "min_success_rate": 0.9, "requires_admin_approval": True}

        }

    }



@router.get("/agents", response_model=List[AgentMaturityResponse])

async def list_agents_with_maturity(

    category: Optional[str] = Query(None, description="Filter by category"),

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db)

):

    """

    List registered agents with their maturity levels (from AgentRegistry).

    Used by AgentWorkflowGenerator to display agent status.

    """

    try:

        query = db.query(AgentRegistry).order_by(AgentRegistry.name).limit(200)

        agents_rows = query.all()

        if category:

            agents_rows = [a for a in agents_rows if a.category == category]



        agents = []

        for agent in agents_rows:

            score = agent.confidence_score if agent.confidence_score is not None else 0.5

            maturity = get_maturity_level_from_score(score)

            can_deploy = can_deploy_directly(maturity, score)



            agents.append(AgentMaturityResponse(

                agent_id=agent.id,

                name=agent.name,

                category=agent.category or "general",

                maturity_level=maturity,

                confidence_score=score,

                can_deploy_directly=can_deploy,

                requires_approval=not can_deploy,

                description=getattr(agent, "description", None)

            ))



        return agents



    except Exception as e:

        logger.error(f"Failed to list agents: {e}")

        raise router.internal_error("Internal error")





@router.get("/agents/{agent_id}", response_model=AgentMaturityResponse)

async def get_agent_maturity(agent_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    """

    Get maturity status for a specific agent (from AgentRegistry).

    Used by AgentWorkflowGenerator when an agent is selected.

    """

    try:

        agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()

        if not agent:

            raise router.not_found_error("Agent", agent_id)



        score = agent.confidence_score if agent.confidence_score is not None else 0.5

        maturity = get_maturity_level_from_score(score)

        can_deploy = can_deploy_directly(maturity, score)



        return AgentMaturityResponse(

            agent_id=agent.id,

            name=agent.name,

            category=agent.category or "general",

            maturity_level=maturity,

            confidence_score=score,

            can_deploy_directly=can_deploy,

            requires_approval=not can_deploy,

            description=getattr(agent, "description", None)

        )



    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"Failed to get agent {agent_id}: {e}")

        raise router.internal_error("Internal error")





@router.post("/check-deployment", response_model=WorkflowApprovalResponse)

async def check_workflow_deployment(request: WorkflowApprovalRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    """

    Check if a workflow can be deployed directly or requires approval.

    Called before deploying a generated workflow.

    """

    try:

        agent_id = request.agent_id



        agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()

        if not agent:

            raise router.not_found_error("Agent", agent_id)



        score = agent.confidence_score if agent.confidence_score is not None else 0.5

        maturity = get_maturity_level_from_score(score)

        can_deploy = can_deploy_directly(maturity, score)



        if can_deploy:

            return WorkflowApprovalResponse(

                approval_id="",

                status="approved",

                requires_approval=False,

                can_deploy=True,

                message=f"Agent {agent.name} is {maturity} level. Workflow can be deployed directly."

            )

        # Generate approval request

        approval_id = f"apr_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{agent.id[:8]}"



        # Determine required approver role

        approver_role = "team_lead" if maturity in ["intern", "supervised"] else "admin"



        return WorkflowApprovalResponse(

            approval_id=approval_id,

            status="pending",

            requires_approval=True,

            can_deploy=False,

            message=f"Agent {agent.name} is a {maturity}. Workflow requires {approver_role} approval.",

            approver_role_required=approver_role

        )



    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"Failed to check deployment: {e}")

        raise router.internal_error("Internal error")





@router.post("/submit-for-approval")

async def submit_workflow_for_approval(request: WorkflowApprovalRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    """

    Submit a workflow for human approval.

    Creates an approval request in the system.

    """

    try:

        agent_id = request.agent_id



        agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()

        if not agent:

            raise router.not_found_error("Agent", agent_id)



        score = agent.confidence_score if agent.confidence_score is not None else 0.5

        maturity = get_maturity_level_from_score(score)



        # R81: create a real HITL action so the submission is reviewable via

        # /pending-approvals + /approve/{id} (intervention service) instead of

        # being a logged no-op.

        with get_db_session() as gov_db:

            governance = AgentGovernanceService(gov_db)

            approval_id = governance.request_approval(

                agent_id=agent.id,

                action_type="deploy_workflow",

                params={

                    "workflow_name": request.workflow_name,

                    "workflow_definition": request.workflow_definition,

                    "trigger_type": request.trigger_type,

                    "actions": request.actions,

                },

                reason=f"Workflow '{request.workflow_name}' submitted by {agent.name} ({maturity})",

            )



        logger.info(f"Workflow submitted for approval: {approval_id} by agent {agent_id}")



        return router.success_response(

            data={

                "approval_id": approval_id,

                "workflow_name": request.workflow_name,

                "agent_id": agent_id,

                "agent_name": agent.name,

                "maturity_level": maturity,

                "status": "pending",

                "estimated_review_time": "24 hours"

            },

            message="Workflow submitted for approval. You will be notified when reviewed."

        )



    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"Failed to submit for approval: {e}")

        raise router.internal_error("Internal error")





@router.post("/feedback")

async def submit_agent_feedback(

    request: AgentFeedbackRequest,

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db)

):

    """

    Submit feedback on agent output.

    Feeds AgentGovernanceService.submit_feedback → adjudication → confidence

    update, i.e. the same learning loop the execution paths use.

    """

    try:

        agent_id = request.agent_id



        agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()

        if not agent:

            raise router.not_found_error("Agent", agent_id)



        with get_db_session() as gov_db:

            governance = AgentGovernanceService(gov_db)

            await governance.submit_feedback(

                agent_id=agent.id,

                user_id=current_user.id,

                original_output=request.original_output,

                user_correction=request.user_correction,

                input_context=request.input_context,

            )



        logger.info(f"Feedback recorded for agent {agent_id}")



        return router.success_response(

            data={"agent_id": agent_id},

            message="Thank you for your feedback. It will be reviewed and may affect the agent's maturity level."

        )



    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"Failed to submit feedback: {e}")

        raise router.internal_error("Internal error")





@router.get("/pending-approvals")

async def list_pending_approvals(

    approver_id: Optional[str] = Query(None, description="Filter by approver"),

    current_user: User = Depends(get_current_user),

):

    """

    List pending workflow approvals.

    Used by team leads/admins to review and approve workflows.

    """

    try:

        # Use intervention service to get real pending actions

        pending = intervention_service.get_pending_interventions(approver_id)

        

        return {

            "pending_approvals": pending,

            "count": len(pending),

            "message": f"Found {len(pending)} pending approvals"

        }

    

    except Exception as e:

        logger.error(f"Failed to list pending approvals: {e}")

        raise router.internal_error("Internal error")





@router.post("/approve/{approval_id}")

async def approve_workflow(

    approval_id: str,

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db)

):

    """

    Approve a pending workflow.

    """

    try:

        # RBAC Check against the AUTHENTICATED user (identity from token,

        # never from client-supplied query/body params).

        user = db.query(User).filter(User.id == current_user.id).first()

        if not user:

            raise router.not_found_error("User", current_user.id)



        # Require at least Team Lead

        allowed_roles = [UserRole.TEAM_LEAD.value, UserRole.WORKSPACE_ADMIN.value, UserRole.SUPER_ADMIN.value]

        if user.role not in allowed_roles:

            raise router.permission_denied_error(

                action="approve_workflow",

                resource="Workflow Approval",

                details={"required_role": "TEAM_LEAD or ADMIN", "user_role": user.role}

            )



        # Use intervention service

        result = await intervention_service.approve_intervention(approval_id, current_user.id)



        if not result.get("success"):

             raise router.error_response(

                 error_code="APPROVAL_FAILED",

                 message=result.get("message", "Failed to approve workflow"),

                 status_code=400

             )



        return router.success_response(

            data={

                "approval_id": approval_id,

                "status": "approved",

                "approved_by": current_user.id,

                "approved_at": datetime.now(timezone.utc).isoformat()

            },

            message="Action approved successfully"

        )



    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"Failed to approve workflow: {e}")

        raise router.internal_error("Internal error")





@router.post("/reject/{approval_id}")

async def reject_workflow(

    approval_id: str,

    reason: str = Query(..., description="Reason for rejection"),

    current_user: User = Depends(get_current_user),

):

    """

    Reject a pending workflow.

    """

    try:

        # Use intervention service. Identity comes from the token, never from

        # a client-supplied approver_id (previously any anonymous caller could

        # reject approvals as any user).

        result = await intervention_service.reject_intervention(approval_id, current_user.id, reason)



        if not result.get("success"):

             raise router.error_response(

                 error_code="REJECTION_FAILED",

                 message=result.get("message", "Failed to reject workflow"),

                 status_code=400

             )



        return router.success_response(

            data={

                "approval_id": approval_id,

                "status": "rejected",

                "rejected_by": current_user.id,

                "rejected_at": datetime.now(timezone.utc).isoformat(),

                "reason": reason

            },

            message="Action rejected"

        )



    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"Failed to reject workflow: {e}")

        raise router.internal_error("Internal error")





# ==================== SKILL LEVEL ENFORCEMENT ENDPOINTS ====================



class ActionEnforceRequest(BaseModel):

    """Request to check if agent can perform an action"""

    agent_id: str

    action_type: str  # e.g., "delete", "send_email", "create", etc.

    action_details: Optional[Dict[str, Any]] = None





@router.get("/agents/{agent_id}/capabilities")

async def get_agent_capabilities(agent_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    """

    Get what actions an agent is allowed to perform based on maturity level.

    Returns allowed and restricted action types.

    """

    try:

        agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()

        if not agent:

            raise router.not_found_error("Agent", agent_id)



        score = agent.confidence_score if agent.confidence_score is not None else 0.5

        maturity = get_maturity_level_from_score(score)



        # Maturity to complexity mapping

        # Student=1, Intern=2, Supervised=3, Autonomous=4

        maturity_to_max = {

            "student": 1,

            "intern": 2,

            "supervised": 3,

            "autonomous": 4

        }

        max_complexity = maturity_to_max.get(maturity, 2)

        

        # Action complexity definitions

        action_complexity = {

            "search": 1, "read": 1, "list": 1, "get": 1, "fetch": 1, "summarize": 1,

            "analyze": 2, "suggest": 2, "draft": 2, "generate": 2, "recommend": 2,

            "create": 3, "update": 3, "send_email": 3, "post_message": 3, "schedule": 3,

            "delete": 4, "execute": 4, "deploy": 4, "transfer": 4, "payment": 4, "approve": 4,

        }

        

        allowed = [a for a, c in action_complexity.items() if c <= max_complexity]

        restricted = [a for a, c in action_complexity.items() if c > max_complexity]

        

        return {

            "agent_id": agent_id,

            "agent_name": agent.name,

            "maturity_level": maturity,

            "confidence_score": score,

            "max_complexity": max_complexity,

            "allowed_actions": allowed,

            "restricted_actions": restricted,

            "total_allowed": len(allowed),

            "total_restricted": len(restricted)

        }

    

    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"Failed to get capabilities: {e}")

        raise router.internal_error("Internal error")





@router.post("/enforce-action")

async def enforce_action(request: ActionEnforceRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    """

    Enforce governance before allowing an action.

    Main entry point for workflow execution to check if action is permitted.

    Delegates to AgentGovernanceService.enforce_action — the same decision

    path used at execution time (R81: previously a mock lookup).



    Returns:

        - proceed: bool - whether to proceed

        - status: APPROVED, PENDING_APPROVAL, or BLOCKED

        - action_required: what to do next

    """

    try:

        agent = db.query(AgentRegistry).filter(AgentRegistry.id == request.agent_id).first()

        if not agent:

            return {

                "proceed": False,

                "status": "BLOCKED",

                "reason": f"Agent {request.agent_id} not found",

                "action_required": "HUMAN_APPROVAL"

            }



        with get_db_session() as gov_db:

            governance = AgentGovernanceService(gov_db)

            result = governance.enforce_action(

                agent_id=request.agent_id,

                action_type=request.action_type,

                action_details=request.action_details,

            )

        # Normalize to the documented response contract.

        return {

            "proceed": bool(result.get("proceed")),

            "status": result.get("status", "BLOCKED"),

            "reason": result.get("reason"),

            "action_required": result.get("action_required"),

            "agent_status": str(agent.status).lower() if agent.status else None,
            "required_status": result.get("required_status"),
            "action_complexity": result.get("action_complexity"),
            "confidence": result.get("confidence"),
        }



    except Exception as e:

        logger.error(f"Failed to enforce action: {e}")


        raise router.internal_error("Internal error")





@router.post("/generate-workflow")

async def generate_workflow_from_description(

    description: str = Query(..., description="Natural language description of desired workflow"),

    agent_id: str = Query(..., description="Agent to use for generation"),

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db),

):

    """

    Generate a workflow from natural language description.

    Connects specialty agents to actual workflow generation.

    """

    try:

        agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()

        if not agent:

            raise router.not_found_error("Agent", agent_id)



        score = agent.confidence_score if agent.confidence_score is not None else 0.5

        maturity = get_maturity_level_from_score(score)



        # In production, this would call the workflow generation LLM

        # For now, return a mock generated workflow



        logger.info(f"Generating workflow for: {description} using {agent_id}")



        # Mock workflow generation

        workflow = {

            "name": f"Auto: {description[:30]}...",

            "agent_id": agent_id,

            "generated_by": agent.name,

            "trigger": {

                "type": "schedule",

                "config": {"cron": "0 9 * * 1-5"}

            },

            "steps": [

                {"type": "action", "service": agent.category or "general", "action": "fetch_data"},

                {"type": "ai_node", "action": "analyze"},

                {"type": "action", "service": "slack", "action": "send_message"}

            ],

            "created_at": datetime.now(timezone.utc).isoformat()

        }

        

        # Check if direct deployment is allowed

        can_deploy = can_deploy_directly(maturity, score)

        

        return router.success_response(

            data={

                "workflow": workflow,

                "agent": {

                    "id": agent_id,

                    "name": agent.name,

                    "maturity": maturity,

                    "confidence": score

                },

                "can_deploy_directly": can_deploy,

                "requires_approval": not can_deploy

            },

            message=f"Workflow generated by {agent.name}. {'Ready to deploy.' if can_deploy else 'Requires approval.'}"

        )

    

    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"Failed to generate workflow: {e}")

        raise router.internal_error("Internal error")
