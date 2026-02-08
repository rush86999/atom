from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.error_handlers import handle_not_found, handle_permission_denied
from core.governance_cache import get_governance_cache
from core.models import (
    AgentFeedback,
    AgentRegistry,
    AgentStatus,
    FeedbackStatus,
    HITLAction,
    HITLActionStatus,
    User,
    UserRole,
)
from core.rbac_service import Permission, RBACService

logger = logging.getLogger(__name__)

class AgentGovernanceService:
    def __init__(self, db: Session):
        self.db = db
        
    def register_or_update_agent(
        self, 
        name: str, 
        category: str,
        module_path: str,
        class_name: str,
        description: str = None,
    ) -> AgentRegistry:
        """Register a new agent or update existing definition"""
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.module_path == module_path,
            AgentRegistry.class_name == class_name
        ).first()
        
        if not agent:
            # Create new
            agent = AgentRegistry(
                name=name,
                category=category,
                module_path=module_path,
                class_name=class_name,
                description=description,
                status=AgentStatus.STUDENT.value
            )
            self.db.add(agent)
            logger.info(f"Registered new agent: {name}")
        else:
            # Update meta
            agent.name = name
            agent.category = category
            agent.description = description
            
        self.db.commit()
        self.db.refresh(agent)
        return agent

    async def submit_feedback(
        self,
        agent_id: str,
        user_id: str,
        original_output: str,
        user_correction: str,
        input_context: Optional[str] = None
    ) -> AgentFeedback:
        """
        Submit user feedback for an agent's action.
        Triggers AI adjudication to check if the user is correct.
        """
        agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if not agent:
            raise handle_not_found("Agent", agent_id)

        feedback = AgentFeedback(
            agent_id=agent_id,
            user_id=user_id,
            original_output=original_output,
            user_correction=user_correction,
            input_context=input_context,
            status=FeedbackStatus.PENDING.value
        )
        self.db.add(feedback)
        self.db.commit()
        
        # Trigger Adjudication (Async)
        await self._adjudicate_feedback(feedback)
        
        return feedback

    async def _adjudicate_feedback(self, feedback: AgentFeedback):
        """
        Judge the validity of the user's correction.
        """
        user = self.db.query(User).filter(User.id == feedback.user_id).first()
        agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == feedback.agent_id).first()
        
        # Logic: "user confidence from the same role or admin"
        # 1. Admin/Super Admin are trusted.
        # 2. Specialty Match: User's specialty (e.g. "Accountant") matches Agent's category (e.g. "Finance" or "Accounting")
        # For MVP, simple string equality or containment
        
        is_admin = user.role in [UserRole.WORKSPACE_ADMIN, UserRole.SUPER_ADMIN]
        
        # Check Specialty Match
        # e.g. Agent Category="Finance", User Specialty="Accountant" (Maybe map or loose match?)
        # For now, let's assume if Specialty is set, we check if it relates to Category
        is_specialty_match = False
        if user.specialty and agent.category:
            # Simple check: accountant in finance?
            # Or simplified: User Specialty == Agent Category
            if user.specialty.lower() == agent.category.lower():
                is_specialty_match = True
        
        is_trusted_reviewer = is_admin or is_specialty_match

        if is_trusted_reviewer:
            feedback.status = FeedbackStatus.ACCEPTED.value
            feedback.ai_reasoning = f"Trusted reviewer (Role: {user.role}, Specialty: {user.specialty}) provided correction."
            feedback.adjudicated_at = datetime.now()
            
            # Significant impact on confidence
            self._update_confidence_score(feedback.agent_id, positive=False, impact_level="high")
            
            # EXPLICIT LEARNING: Record this correction in World Model
            from core.agent_world_model import AgentExperience, WorldModelService
            wm = WorldModelService()
            
            # Create a corrective experience
            # We treat the original input + incorrect output as the context, and correction as the "Learning"
            correction_exp = AgentExperience(
                id=str(uuid.uuid4()),
                agent_id=feedback.agent_id,
                task_type="correction",
                input_summary=f"Context: {feedback.input_context or 'N/A'}\nIncorrect Action: {feedback.original_output}",
                outcome="Failure", # It was a failure since it needed correction
                learnings=f"User Correction: {feedback.user_correction}",
                agent_role=agent.category,
                specialty=None,
                timestamp=datetime.utcnow()
            )
            # We use asyncio.create_task if we are in async context, but this method is async _adjudicate_feedback
            # So we can await it if we change signature? 
            # Wait, _adjudicate_feedback is defined as async on line 88. 
            await wm.record_experience(correction_exp)
             
        else:
            # Lower confidence users
            feedback.status = FeedbackStatus.PENDING.value
            feedback.ai_reasoning = "Correction queued for specialty review."
            feedback.adjudicated_at = datetime.now()
            self._update_confidence_score(feedback.agent_id, positive=False, impact_level="low")
 
        self.db.commit()

    async def record_outcome(self, agent_id: str, success: bool):
        """
        Record a successful or failed task outcome and update confidence.
        """
        impact = "low" # Standard executions have low impact compared to direct corrections
        self._update_confidence_score(agent_id, positive=success, impact_level=impact)
        logger.info(f"Recorded outcome for agent {agent_id}: success={success}")

    def _update_confidence_score(self, agent_id: str, positive: bool, impact_level: str = "high"):
        """
        Update confidence and manage maturity transitions.
        Impact: high (0.05/0.1), low (0.01/0.02)
        """
        agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if not agent:
            return

        # Use 0.5 only if confidence_score is None, not if it's 0.0
        current = agent.confidence_score if agent.confidence_score is not None else 0.5
        
        # Define multipliers
        boost = 0.05 if impact_level == "high" else 0.01
        penalty = 0.1 if impact_level == "high" else 0.02
        
        if positive:
            new_score = min(1.0, current + boost)
        else:
            new_score = max(0.0, current - penalty)
            
        agent.confidence_score = new_score
        
        # Maturity Model Logic
        # Student (<0.5) -> Intern (0.5-0.7) -> Supervised (0.7-0.9) -> Autonomous (>0.9)
        previous_status = agent.status
        
        if new_score >= 0.9:
            agent.status = AgentStatus.AUTONOMOUS.value
        elif new_score >= 0.7:
             agent.status = AgentStatus.SUPERVISED.value
        elif new_score >= 0.5:
             agent.status = AgentStatus.INTERN.value
        else:
             agent.status = AgentStatus.STUDENT.value
             
        if agent.status != previous_status:
            logger.info(f"Agent {agent.name} transitioned: {previous_status} -> {agent.status} (Score: {new_score:.2f})")
            # Invalidate cache when agent status changes
            cache = get_governance_cache()
            cache.invalidate(agent_id)

        self.db.add(agent)
        self.db.commit()

    def promote_to_autonomous(self, agent_id: str, user: User) -> AgentRegistry:
        """
        Promote an agent from LEARNING to ACTIVE mode.
        Requires AGENT_MANAGE permission.
        """
        # 1. Permission Check
        if not RBACService.check_permission(user, Permission.AGENT_MANAGE):
            raise handle_permission_denied("promote", "Agent")

        agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if not agent:
            raise handle_not_found("Agent", agent_id)
            
        # 2. Update Status
        agent.status = AgentStatus.AUTONOMOUS.value
        logger.info(f"Agent {agent.name} promoted to Autonomous check by {user.email}")

        # Invalidate cache when agent status changes
        cache = get_governance_cache()
        cache.invalidate(agent_id)

        self.db.commit()
        self.db.refresh(agent)
        return agent

    def list_agents(self, category: Optional[str] = None) -> List[AgentRegistry]:
        """List registered agents"""
        query = self.db.query(AgentRegistry)
        if category:
            query = query.filter(AgentRegistry.category == category)
        return query.all()

    # ==================== SKILL LEVEL ENFORCEMENT ====================
    
    # Action complexity levels - higher = more complex/risky
    ACTION_COMPLEXITY = {
        # Low risk - Student can do
        "search": 1,
        "read": 1,
        "list": 1,
        "get": 1,
        "fetch": 1,
        "summarize": 1,
        "present_chart": 1,        # STUDENT+ (read-only visualization)
        "present_markdown": 1,     # STUDENT+ (read-only content)

        # Medium-low - Intern level
        "analyze": 2,
        "suggest": 2,
        "draft": 2,
        "generate": 2,
        "recommend": 2,
        "stream_chat": 2,          # INTERN+ (LLM streaming)
        "present_form": 2,         # INTERN+ (moderate - form presentation)
        "llm_stream": 2,           # INTERN+ (cost implications)
        "browser_navigate": 2,     # INTERN+ (web navigation)
        "browser_screenshot": 2,   # INTERN+ (screenshot capture)
        "browser_extract": 2,      # INTERN+ (text extraction)
        "device_camera_snap": 2,   # INTERN+ (camera capture)
        "device_get_location": 2,  # INTERN+ (location services)
        "device_send_notification": 2,  # INTERN+ (system notifications)
        "update_canvas": 2,        # INTERN+ (bidirectional canvas update)

        # Medium - Supervised level
        "create": 3,
        "update": 3,
        "send_email": 3,
        "post_message": 3,
        "schedule": 3,
        "submit_form": 3,          # SUPERVISED+ (state change - form submission)
        "device_screen_record": 3, # SUPERVISED+ (screen recording - privacy concern)
        "device_screen_record_start": 3,  # SUPERVISED+ (screen recording start)
        "device_screen_record_stop": 3,   # SUPERVISED+ (screen recording stop)

        # High - Autonomous level only
        "delete": 4,
        "execute": 4,
        "deploy": 4,
        "transfer": 4,
        "payment": 4,
        "approve": 4,
        "device_execute_command": 4,  # AUTONOMOUS only (command execution - security critical)
        "canvas_execute_javascript": 4,  # AUTONOMOUS only (JavaScript execution - security critical)
    }
    
    # Minimum maturity level for each action complexity
    MATURITY_REQUIREMENTS = {
        1: AgentStatus.STUDENT,   # Anyone can do low-complexity
        2: AgentStatus.INTERN,    # Requires Intern+
        3: AgentStatus.SUPERVISED, # Requires Supervised+
        4: AgentStatus.AUTONOMOUS, # Only Autonomous can do
    }
    
    def can_perform_action(
        self,
        agent_id: str,
        action_type: str,
        require_approval: bool = False
    ) -> Dict[str, Any]:
        """
        Check if an agent has sufficient maturity to perform an action.

        Uses governance cache for sub-millisecond performance on repeated checks.

        Returns:
            {
                "allowed": bool,
                "reason": str,
                "agent_status": str,
                "action_complexity": int,
                "required_status": str,
                "requires_human_approval": bool
            }
        """
        # Check cache first (sub-millisecond lookup)
        cache = get_governance_cache()
        cached_result = cache.get(agent_id, action_type)
        if cached_result:
            logger.debug(f"Cache HIT for governance check: {agent_id}:{action_type}")
            # Update require_approval flag based on current request
            if require_approval:
                cached_result["requires_human_approval"] = True
            return cached_result

        logger.debug(f"Cache MISS for governance check: {agent_id}:{action_type}")
        agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if not agent:
            return {
                "allowed": False,
                "reason": "Agent not found",
                "requires_human_approval": True
            }
        
        # Determine action complexity (default to medium if unknown)
        action_lower = action_type.lower()
        complexity = 2  # Default medium-low
        for action_key, level in self.ACTION_COMPLEXITY.items():
            if action_key in action_lower:
                complexity = level
                break
        
        # Get required maturity level
        required_status = self.MATURITY_REQUIREMENTS.get(complexity, AgentStatus.SUPERVISED)
        
        # Maturity hierarchy
        maturity_order = [
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ]
        
        agent_index = maturity_order.index(agent.status) if agent.status in maturity_order else 0
        required_index = maturity_order.index(required_status.value)
        
        is_allowed = agent_index >= required_index
        requires_approval = not is_allowed or (agent.status == AgentStatus.SUPERVISED.value and complexity >= 3)
        
        if is_allowed:
            reason = f"Agent {agent.name} ({agent.status}) can perform {action_type} (complexity {complexity})"
        else:
            reason = f"Agent {agent.name} ({agent.status}) lacks maturity for {action_type}. Required: {required_status.value}"
        
        logger.info(f"Governance check: {reason} - Approval required: {requires_approval}")

        result = {
            "allowed": is_allowed,
            "reason": reason,
            "agent_status": agent.status,
            "action_complexity": complexity,
            "required_status": required_status.value,
            "requires_human_approval": requires_approval or require_approval,
            "confidence_score": agent.confidence_score or 0.5
        }

        # Cache the result for future lookups (sub-millisecond performance)
        cache.set(agent_id, action_type, result)
        logger.debug(f"Cached governance decision for {agent_id}:{action_type}")

        return result
    
    def get_agent_capabilities(self, agent_id: str) -> Dict[str, Any]:
        """
        Get what actions an agent is allowed to perform based on maturity.
        
        Returns list of allowed action types and complexity levels.
        """
        agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if not agent:
            raise handle_not_found("Agent", agent_id)
        
        maturity_order = [
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ]
        
        agent_index = maturity_order.index(agent.status) if agent.status in maturity_order else 0
        max_complexity = agent_index + 1  # Student=1, Intern=2, etc.
        
        allowed_actions = [
            action for action, complexity in self.ACTION_COMPLEXITY.items()
            if complexity <= max_complexity
        ]
        
        return {
            "agent_id": agent_id,
            "agent_name": agent.name,
            "maturity_level": agent.status,
            "confidence_score": agent.confidence_score or 0.5,
            "max_complexity": max_complexity,
            "allowed_actions": allowed_actions,
            "restricted_actions": [
                action for action, complexity in self.ACTION_COMPLEXITY.items()
                if complexity > max_complexity
            ]
        }
    
    def enforce_action(
        self, 
        agent_id: str, 
        action_type: str,
        action_details: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Enforce governance before allowing an action.
        
        This is the main entry point for workflow execution.
        Returns approval status and next steps.
        """
        check = self.can_perform_action(agent_id, action_type)
        
        if not check["allowed"]:
            # Queue for human approval
            return {
                "proceed": False,
                "status": "BLOCKED",
                "reason": check["reason"],
                "action_required": "HUMAN_APPROVAL",
                "agent_status": check["agent_status"],
                "required_status": check["required_status"]
            }
        
        if check["requires_human_approval"]:
            # Can do but needs oversight
            return {
                "proceed": True,
                "status": "PENDING_APPROVAL",
                "reason": f"Agent qualified but action requires approval",
                "action_required": "WAIT_FOR_APPROVAL",
                "agent_status": check["agent_status"],
                "confidence": check["confidence_score"]
            }
        
        # Full auto-proceed
        return {
            "proceed": True,
            "status": "APPROVED",
            "reason": check["reason"],
            "action_required": None,
            "agent_status": check["agent_status"],
            "confidence": check["confidence_score"]
        }

    def request_approval(
        self, 
        agent_id: str, 
        action_type: str, 
        params: Dict, 
        reason: str
    ) -> str:
        """Create a HITL action and return its ID"""
        hitl = HITLAction(
            id=str(uuid.uuid4()),
            workspace_id="default",
            agent_id=agent_id,
            action_type=action_type,
            platform="internal", # Generic internal platform
            params=params,
            status=HITLActionStatus.PENDING.value,
            reason=reason,
            confidence_score=0.0 # Initial
        )
        self.db.add(hitl)
        self.db.commit()
        logger.info(f"Requested HITL approval for {agent_id} -> {action_type} (ID: {hitl.id})")
        return hitl.id

    def get_approval_status(self, action_id: str) -> Dict[str, Any]:
        """Check if a HITL action has been decided"""
        hitl = self.db.query(HITLAction).filter(HITLAction.id == action_id).first()
        if not hitl:
            return {"status": "not_found"}
        
        return {
            "id": hitl.id,
            "status": hitl.status,
            "user_feedback": hitl.user_feedback,
            "reviewed_at": hitl.reviewed_at
        }

    def can_access_agent_data(self, user_id: str, agent_id: str) -> bool:
        """
        Check if a user can access data/sessions belonging to a specific agent.
        Rules (Ported from SaaS):
        1. Admins (super_admin, workspace_admin) -> ALLOW
        2. Specialty Match (user.specialty == agent.category) -> ALLOW
        3. Owners (context-dependent) -> ALLOW
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        
        if not user or not agent:
            return False
            
        # 1. Admin Override
        if user.role in [UserRole.SUPER_ADMIN, UserRole.WORKSPACE_ADMIN]:
            return True
            
        # 2. Specialty Match
        if user.specialty and agent.category:
            if user.specialty.lower() == agent.category.lower():
                return True
                
        return False
