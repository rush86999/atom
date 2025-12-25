from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import logging
import uuid

from core.models import (
    User, AgentRegistry, AgentFeedback, AgentStatus, 
    FeedbackStatus, UserRole
)
from core.rbac_service import RBACService, Permission

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
            raise HTTPException(status_code=404, detail="Agent not found")
            
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
        else:
            # Lower confidence users
            feedback.status = FeedbackStatus.PENDING.value
            feedback.ai_reasoning = "Correction queued for specialty review."
            feedback.adjudicated_at = datetime.now()
            self._update_confidence_score(feedback.agent_id, positive=False, impact_level="low")

        self.db.commit()

    def _update_confidence_score(self, agent_id: str, positive: bool, impact_level: str = "high"):
        """
        Update confidence and manage maturity transitions.
        Impact: high (0.05/0.1), low (0.01/0.02)
        """
        agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if not agent:
            return

        current = agent.confidence_score or 0.5
        
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

        self.db.add(agent)
        self.db.commit()

    def promote_to_autonomous(self, agent_id: str, user: User) -> AgentRegistry:
        """
        Promote an agent from LEARNING to ACTIVE mode.
        Requires AGENT_MANAGE permission.
        """
        # 1. Permission Check
        if not RBACService.check_permission(user, Permission.AGENT_MANAGE):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to promote agent."
            )
            
        agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
            
        # 2. Update Status
        agent.status = AgentStatus.AUTONOMOUS.value
        logger.info(f"Agent {agent.name} promoted to Autonomous check by {user.email}")
        
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def list_agents(self, category: Optional[str] = None) -> List[AgentRegistry]:
        """List registered agents"""
        query = self.db.query(AgentRegistry)
        if category:
            query = query.filter(AgentRegistry.category == category)
        return query.all()
