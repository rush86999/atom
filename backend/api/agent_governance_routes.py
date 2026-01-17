"""
Agent Governance API Routes
Exposes endpoints for frontend to query and interact with agent governance.
Used by AgentWorkflowGenerator.tsx to check maturity levels and approval requirements.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Import newly created intervention service
from core.intervention_service import intervention_service
from core.database import SessionLocal
from core.models import User, UserRole

router = APIRouter(prefix="/api/agent-governance", tags=["Agent Governance"])


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


# ==================== Mock Data (for frontend development) ====================
# In production, these would query the database

MOCK_AGENTS = {
    "sales-agent": {
        "agent_id": "sales-agent",
        "name": "Sales Agent",
        "category": "sales",
        "confidence_score": 0.85,
        "description": "CRM automation and lead management"
    },
    "marketing-agent": {
        "agent_id": "marketing-agent",
        "name": "Marketing Agent",
        "category": "marketing",
        "confidence_score": 0.72,
        "description": "Campaign automation and analytics"
    },
    "support-agent": {
        "agent_id": "support-agent",
        "name": "Support Agent",
        "category": "support",
        "confidence_score": 0.68,
        "description": "Ticket handling and customer response"
    },
    "engineering-agent": {
        "agent_id": "engineering-agent",
        "name": "Engineering Agent",
        "category": "engineering",
        "confidence_score": 0.45,
        "description": "CI/CD and issue tracking automation"
    },
    "hr-agent": {
        "agent_id": "hr-agent",
        "name": "HR Agent",
        "category": "hr",
        "confidence_score": 0.38,
        "description": "Onboarding and employee data automation"
    },
    "finance-agent": {
        "agent_id": "finance-agent",
        "name": "Finance Agent",
        "category": "finance",
        "confidence_score": 0.92,
        "description": "Invoice and expense automation"
    },
    "data-agent": {
        "agent_id": "data-agent",
        "name": "Data Agent",
        "category": "data",
        "confidence_score": 0.78,
        "description": "Data sync and reporting automation"
    },
    "productivity-agent": {
        "agent_id": "productivity-agent",
        "name": "Productivity Agent",
        "category": "productivity",
        "confidence_score": 0.55,
        "description": "Task and document automation"
    },
}


# ==================== API Endpoints ====================

@router.get("/rules")
async def get_governance_rules():
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
    category: Optional[str] = Query(None, description="Filter by category")
):
    """
    List all specialty agents with their maturity levels.
    Used by AgentWorkflowGenerator to display agent status.
    """
    try:
        # In production, query AgentRegistry from database
        # For now, use mock data
        agents = []
        for agent_id, data in MOCK_AGENTS.items():
            if category and data["category"] != category:
                continue
            
            score = data["confidence_score"]
            maturity = get_maturity_level_from_score(score)
            can_deploy = can_deploy_directly(maturity, score)
            
            agents.append(AgentMaturityResponse(
                agent_id=agent_id,
                name=data["name"],
                category=data["category"],
                maturity_level=maturity,
                confidence_score=score,
                can_deploy_directly=can_deploy,
                requires_approval=not can_deploy,
                description=data.get("description")
            ))
        
        return agents
    
    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_id}", response_model=AgentMaturityResponse)
async def get_agent_maturity(agent_id: str):
    """
    Get maturity status for a specific agent.
    Used by AgentWorkflowGenerator when an agent is selected.
    """
    try:
        # In production, query AgentRegistry from database
        if agent_id not in MOCK_AGENTS:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        
        data = MOCK_AGENTS[agent_id]
        score = data["confidence_score"]
        maturity = get_maturity_level_from_score(score)
        can_deploy = can_deploy_directly(maturity, score)
        
        return AgentMaturityResponse(
            agent_id=agent_id,
            name=data["name"],
            category=data["category"],
            maturity_level=maturity,
            confidence_score=score,
            can_deploy_directly=can_deploy,
            requires_approval=not can_deploy,
            description=data.get("description")
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-deployment", response_model=WorkflowApprovalResponse)
async def check_workflow_deployment(request: WorkflowApprovalRequest):
    """
    Check if a workflow can be deployed directly or requires approval.
    Called before deploying a generated workflow.
    """
    try:
        agent_id = request.agent_id
        
        if agent_id not in MOCK_AGENTS:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        
        data = MOCK_AGENTS[agent_id]
        score = data["confidence_score"]
        maturity = get_maturity_level_from_score(score)
        can_deploy = can_deploy_directly(maturity, score)
        
        if can_deploy:
            return WorkflowApprovalResponse(
                approval_id="",
                status="approved",
                requires_approval=False,
                can_deploy=True,
                message=f"Agent {data['name']} is {maturity} level. Workflow can be deployed directly."
            )
        else:
            # Generate approval request
            approval_id = f"apr_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{agent_id[:8]}"
            
            # Determine required approver role
            approver_role = "team_lead" if maturity in ["intern", "supervised"] else "admin"
            
            return WorkflowApprovalResponse(
                approval_id=approval_id,
                status="pending",
                requires_approval=True,
                can_deploy=False,
                message=f"Agent {data['name']} is a {maturity}. Workflow requires {approver_role} approval.",
                approver_role_required=approver_role
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check deployment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/submit-for-approval")
async def submit_workflow_for_approval(request: WorkflowApprovalRequest):
    """
    Submit a workflow for human approval.
    Creates an approval request in the system.
    """
    try:
        agent_id = request.agent_id
        
        if agent_id not in MOCK_AGENTS:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        
        data = MOCK_AGENTS[agent_id]
        score = data["confidence_score"]
        maturity = get_maturity_level_from_score(score)
        
        # Generate approval request
        approval_id = f"apr_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{agent_id[:8]}"
        
        # In production, this would:
        # 1. Create a HITLAction record
        # 2. Notify approvers via email/Slack
        # 3. Store the pending workflow
        
        logger.info(f"Workflow submitted for approval: {approval_id} by agent {agent_id}")
        
        return {
            "success": True,
            "approval_id": approval_id,
            "workflow_name": request.workflow_name,
            "agent_id": agent_id,
            "agent_name": data["name"],
            "maturity_level": maturity,
            "status": "pending",
            "message": "Workflow submitted for approval. You will be notified when reviewed.",
            "estimated_review_time": "24 hours"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit for approval: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback")
async def submit_agent_feedback(request: AgentFeedbackRequest):
    """
    Submit feedback on agent output.
    Used to improve agent confidence scores over time.
    """
    try:
        agent_id = request.agent_id
        
        if agent_id not in MOCK_AGENTS:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        
        # In production, this would call AgentGovernanceService.submit_feedback()
        # which triggers AI adjudication and updates confidence scores
        
        logger.info(f"Feedback submitted for agent {agent_id}")
        
        return {
            "success": True,
            "message": "Thank you for your feedback. It will be reviewed and may affect the agent's maturity level.",
            "agent_id": agent_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending-approvals")
async def list_pending_approvals(
    approver_id: Optional[str] = Query(None, description="Filter by approver")
):
    """
    List pending workflow approvals.
    Used by team leads/admins to review and approve workflows.
    """
    try:
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
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approve/{approval_id}")
async def approve_workflow(
    approval_id: str,
    approver_id: str = Query(..., description="ID of the approving user")
):
    """
    Approve a pending workflow.
    """
    try:
    try:
        # RBAC Check
        with SessionLocal() as db:
            user = db.query(User).filter(User.id == approver_id).first()
            if not user:
                raise HTTPException(status_code=404, detail="Approver user not found")
            
            # Require at least Team Lead
            allowed_roles = [UserRole.TEAM_LEAD.value, UserRole.WORKSPACE_ADMIN.value, UserRole.SUPER_ADMIN.value]
            if user.role not in allowed_roles:
                raise HTTPException(status_code=403, detail="Insufficient permissions. Approval requires Team Lead or Admin role.")

        # Use intervention service
        result = await intervention_service.approve_intervention(approval_id, approver_id)
        
        if not result.get("success"):
             raise HTTPException(status_code=400, detail=result.get("message"))
        
        return {
            "success": True,
            "approval_id": approval_id,
            "status": "approved",
            "approved_by": approver_id,
            "approved_at": datetime.utcnow().isoformat(),
            "message": "Action approved successfully"
        }
    
    except Exception as e:
        logger.error(f"Failed to approve workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reject/{approval_id}")
async def reject_workflow(
    approval_id: str,
    approver_id: str = Query(..., description="ID of the rejecting user"),
    reason: str = Query(..., description="Reason for rejection")
):
    """
    Reject a pending workflow.
    """
    try:
    try:
        # Use intervention service
        result = await intervention_service.reject_intervention(approval_id, approver_id, reason)
        
        if not result.get("success"):
             raise HTTPException(status_code=400, detail=result.get("message"))
             
        return {
            "success": True,
            "approval_id": approval_id,
            "status": "rejected",
            "rejected_by": approver_id,
            "rejected_at": datetime.utcnow().isoformat(),
            "reason": reason,
            "message": "Action rejected"
        }
    
    except Exception as e:
        logger.error(f"Failed to reject workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SKILL LEVEL ENFORCEMENT ENDPOINTS ====================

class ActionEnforceRequest(BaseModel):
    """Request to check if agent can perform an action"""
    agent_id: str
    action_type: str  # e.g., "delete", "send_email", "create", etc.
    action_details: Optional[Dict[str, Any]] = None


@router.get("/agents/{agent_id}/capabilities")
async def get_agent_capabilities(agent_id: str):
    """
    Get what actions an agent is allowed to perform based on maturity level.
    Returns allowed and restricted action types.
    """
    try:
        if agent_id not in MOCK_AGENTS:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        
        data = MOCK_AGENTS[agent_id]
        score = data["confidence_score"]
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
            "agent_name": data["name"],
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
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enforce-action")
async def enforce_action(request: ActionEnforceRequest):
    """
    Enforce governance before allowing an action.
    Main entry point for workflow execution to check if action is permitted.
    
    Returns:
        - proceed: bool - whether to proceed
        - status: APPROVED, PENDING_APPROVAL, or BLOCKED
        - action_required: what to do next
    """
    try:
        agent_id = request.agent_id
        action_type = request.action_type
        
        if agent_id not in MOCK_AGENTS:
            return {
                "proceed": False,
                "status": "BLOCKED",
                "reason": f"Agent {agent_id} not found",
                "action_required": "HUMAN_APPROVAL"
            }
        
        data = MOCK_AGENTS[agent_id]
        score = data["confidence_score"]
        maturity = get_maturity_level_from_score(score)
        
        # Determine action complexity
        action_complexity = {
            "search": 1, "read": 1, "list": 1, "get": 1, "fetch": 1, "summarize": 1,
            "analyze": 2, "suggest": 2, "draft": 2, "generate": 2, "recommend": 2,
            "create": 3, "update": 3, "send_email": 3, "post_message": 3, "schedule": 3,
            "delete": 4, "execute": 4, "deploy": 4, "transfer": 4, "payment": 4, "approve": 4,
        }
        
        # Find matching complexity
        complexity = 2  # Default medium
        action_lower = action_type.lower()
        for key, level in action_complexity.items():
            if key in action_lower:
                complexity = level
                break
        
        # Required maturity for complexity
        complexity_to_maturity = {1: "student", 2: "intern", 3: "supervised", 4: "autonomous"}
        required_maturity = complexity_to_maturity.get(complexity, "supervised")
        
        # Check if agent qualifies
        maturity_order = ["student", "intern", "supervised", "autonomous"]
        agent_level = maturity_order.index(maturity) if maturity in maturity_order else 0
        required_level = maturity_order.index(required_maturity) if required_maturity in maturity_order else 2
        
        is_allowed = agent_level >= required_level
        needs_approval = not is_allowed or (maturity == "supervised" and complexity >= 3)
        
        if not is_allowed:
            return {
                "proceed": False,
                "status": "BLOCKED",
                "reason": f"Agent {data['name']} ({maturity}) cannot perform {action_type}. Required: {required_maturity}",
                "action_required": "HUMAN_APPROVAL",
                "agent_status": maturity,
                "required_status": required_maturity,
                "action_complexity": complexity
            }
        
        if needs_approval:
            return {
                "proceed": True,
                "status": "PENDING_APPROVAL",
                "reason": f"Agent qualified but {action_type} (complexity {complexity}) requires oversight",
                "action_required": "WAIT_FOR_APPROVAL",
                "agent_status": maturity,
                "confidence": score
            }
        
        return {
            "proceed": True,
            "status": "APPROVED",
            "reason": f"Agent {data['name']} ({maturity}) approved for {action_type}",
            "action_required": None,
            "agent_status": maturity,
            "confidence": score
        }
    
    except Exception as e:
        logger.error(f"Failed to enforce action: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-workflow")
async def generate_workflow_from_description(
    description: str = Query(..., description="Natural language description of desired workflow"),
    agent_id: str = Query(..., description="Agent to use for generation")
):
    """
    Generate a workflow from natural language description.
    Connects specialty agents to actual workflow generation.
    """
    try:
        if agent_id not in MOCK_AGENTS:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        
        data = MOCK_AGENTS[agent_id]
        score = data["confidence_score"]
        maturity = get_maturity_level_from_score(score)
        
        # In production, this would call the workflow generation LLM
        # For now, return a mock generated workflow
        
        logger.info(f"Generating workflow for: {description} using {agent_id}")
        
        # Mock workflow generation
        workflow = {
            "name": f"Auto: {description[:30]}...",
            "agent_id": agent_id,
            "generated_by": data["name"],
            "trigger": {
                "type": "schedule",
                "config": {"cron": "0 9 * * 1-5"}
            },
            "steps": [
                {"type": "action", "service": data["category"], "action": "fetch_data"},
                {"type": "ai_node", "action": "analyze"},
                {"type": "action", "service": "slack", "action": "send_message"}
            ],
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Check if direct deployment is allowed
        can_deploy = can_deploy_directly(maturity, score)
        
        return {
            "success": True,
            "workflow": workflow,
            "agent": {
                "id": agent_id,
                "name": data["name"],
                "maturity": maturity,
                "confidence": score
            },
            "can_deploy_directly": can_deploy,
            "requires_approval": not can_deploy,
            "message": f"Workflow generated by {data['name']}. {'Ready to deploy.' if can_deploy else 'Requires approval.'}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))
