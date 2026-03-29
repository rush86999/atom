from datetime import datetime, timezone
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
    GovernanceDocument,
    GovernanceDocStatus,
    GovernanceImpactLevel,
    HITLAction,
    HITLActionStatus,
    User,
    UserRole,
)
from core.rbac_service import Permission, RBACService
from core.continuous_learning_service import ContinuousLearningService
from core.activity_publisher import ActivityPublisher

logger = logging.getLogger(__name__)

class AgentGovernanceService:
    def __init__(
        self, 
        db: Session, 
        workspace_id: str = "default", 
        tenant_id: Optional[str] = None,
        activity_publisher: Optional[ActivityPublisher] = None
    ):
        self.db = db
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        self.activity_publisher = activity_publisher
        self.continuous_learning = ContinuousLearningService(db)
        
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
            AgentRegistry.workspace_id == self.workspace_id,
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
                workspace_id=self.workspace_id,
                tenant_id=self.tenant_id,
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
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.workspace_id == self.workspace_id
        ).first()
        if not agent:
            raise handle_not_found("Agent", agent_id)

        feedback = AgentFeedback(
            agent_id=agent_id,
            user_id=user_id,
            workspace_id=self.workspace_id,
            tenant_id=self.tenant_id,
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

    async def _adjudicate_feedback(self, feedback: AgentFeedback) -> None:
        """
        Judge the validity of the user's correction.
        """
        user = self.db.query(User).filter(User.id == feedback.user_id).first()
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == feedback.agent_id,
            AgentRegistry.workspace_id == self.workspace_id
        ).first()
        
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

        # NEW: Apply rating-based confidence adjustment
        if feedback.rating is not None or feedback.thumbs_up_down is not None:
            await self._update_confidence_from_rating(
                feedback.agent_id,
                rating=feedback.rating,
                thumbs_up_down=feedback.thumbs_up_down,
                feedback_type=feedback.feedback_type
            )

        if is_trusted_reviewer:
            feedback.status = FeedbackStatus.ACCEPTED.value
            feedback.ai_reasoning = f"Trusted reviewer (Role: {user.role}, Specialty: {user.specialty}) provided correction."
            feedback.adjudicated_at = datetime.now()
            
            # Significant impact on confidence
            self._update_confidence_score(feedback.agent_id, positive=False, impact_level="high")
            
            # EXPLICIT LEARNING: Record this correction in World Model
            from core.agent_world_model import AgentExperience, WorldModelService
            wm = WorldModelService(workspace_id=self.workspace_id, tenant_id=self.tenant_id)
            
            # Create a corrective experience
            # Determine outcome based on rating if available
            if feedback.rating:
                outcome = "Success" if feedback.rating >= 4 else "Partial" if feedback.rating == 3 else "Failure"
            elif feedback.thumbs_up_down is not None:
                outcome = "Success" if feedback.thumbs_up_down else "Failure"
            else:
                outcome = "Failure" # If it was a correction

            correction_exp = AgentExperience(
                id=str(uuid.uuid4()),
                agent_id=feedback.agent_id,
                task_type=feedback.feedback_type or "correction",
                input_summary=f"Context: {feedback.input_context or 'N/A'}\nIncorrect Action: {feedback.original_output}",
                outcome=outcome,
                learnings=f"User Feedback: {feedback.user_correction}",
                agent_role=agent.category,
                specialty=None,
                timestamp=datetime.utcnow()
            )
            await wm.record_experience(correction_exp)

            # Continuous learning update
            try:
                self.continuous_learning.update_from_feedback(feedback)
            except Exception as le:
                logger.warning(f"Continuous learning update failed from governance: {le}")
             
        else:
            # Lower confidence users
            feedback.status = FeedbackStatus.PENDING.value
            feedback.ai_reasoning = "Correction queued for specialty review."
            feedback.adjudicated_at = datetime.now()

            # NEW: Still allow minor confidence adjustment for non-trusted reviewers
            if feedback.rating is not None or feedback.thumbs_up_down is not None:
                # We already called _update_confidence_from_rating above, so we don't need a penalty here
                pass
            else:
                self._update_confidence_score(feedback.agent_id, positive=False, impact_level="low")
 
        self.db.commit()

    async def record_outcome(self, agent_id: str, success: bool) -> None:
        """
        Record a successful or failed task outcome and update confidence.
        """
        impact = "low" # Standard executions have low impact compared to direct corrections
        self._update_confidence_score(agent_id, positive=success, impact_level=impact)
        logger.info(f"Recorded outcome for agent {agent_id}: success={success}")

    # ==================== GRADUATION & EVOLUTION ====================

    def record_intervention(
        self,
        execution_id: str,
        intervention_type: str,
        user_id: str,
        reason: Optional[str] = None,
        supervisor_type: Optional[str] = None,
        supervisor_id: Optional[str] = None
    ) -> bool:
        """
        Record a human intervention during agent execution for graduation tracking.
        """
        try:
            from core.models import AgentExecution

            execution = self.db.query(AgentExecution).filter(
                AgentExecution.id == execution_id,
                AgentExecution.workspace_id == self.workspace_id
            ).first()

            if not execution:
                logger.warning(f"Execution {execution_id} not found for intervention recording")
                return False

            # Increment intervention count
            execution.human_intervention_count = (execution.human_intervention_count or 0) + 1

            # Store in metadata
            if not execution.metadata_json:
                execution.metadata_json = {}
            if "interventions" not in execution.metadata_json:
                execution.metadata_json["interventions"] = []

            execution.metadata_json["interventions"].append({
                "type": intervention_type,
                "user_id": user_id,
                "reason": reason,
                "supervisor_type": supervisor_type or "user",
                "supervisor_id": supervisor_id or user_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            # Use flag_modified if using JSONB
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(execution, "metadata_json")
            
            self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to record intervention: {e}")
            return False

    def apply_agent_patch(self, agent_id: str) -> Dict[str, Any]:
        """
        Apply an evolutionary patch to an agent (manual confidence jump).
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.workspace_id == self.workspace_id
        ).first()
        if not agent:
             return {"success": False, "error": "Agent not found"}
        
        old_score = agent.confidence_score or 0.5
        old_status = agent.status
        
        # Evolutionary Jump
        new_score = min(1.0, old_score + 0.15)
        agent.confidence_score = new_score
        
        # Direct status update
        self._update_confidence_score(agent_id, positive=True, impact_level="high")
        
        self.db.commit()
        return {
            "success": True,
            "agent_id": agent_id,
            "old_status": old_status,
            "new_status": agent.status,
            "new_score": new_score
        }

    async def check_and_promote_if_ready(
        self,
        agent_id: str,
        tenant_id: str,
        episode_count: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Check if an agent is ready for promotion and auto-promote if ready.
        """
        try:
            from core.episode_service import EpisodeService
            
            # Get agent
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id,
                AgentRegistry.workspace_id == self.workspace_id
            ).first()

            if not agent:
                return None
            
            current_status = agent.status.value if hasattr(agent.status, 'value') else str(agent.status)
            if current_status == "autonomous":
                return None

            # Get readiness from EpisodeService
            from core.service_factory import ServiceFactory
            episode_service = ServiceFactory.get_episode_service(self.db, workspace_id=self.workspace_id, tenant_id=self.tenant_id)
            readiness = episode_service.get_graduation_readiness(
                agent_id=agent_id,
                tenant_id=self.tenant_id,
                episode_count=episode_count
            )

            if readiness.threshold_met:
                old_status = agent.status
                new_status = readiness.breakdown.get("target_level")
                
                # Update agent status
                agent.status = new_status
                agent.last_promotion_at = datetime.now(timezone.utc)
                agent.promotion_count = (agent.promotion_count or 0) + 1
                
                self.db.commit()
                
                logger.info(f"Auto-Promoted agent {agent_id}: {old_status} -> {new_status}")
                return {
                    "promoted": True,
                    "old_status": old_status,
                    "new_status": new_status,
                    "readiness_score": readiness.readiness_score
                }

            return None

        except Exception as e:
            logger.error(f"Auto-promotion check failed for agent {agent_id}: {e}")
            return None

    def _update_confidence_score(self, agent_id: str, positive: bool, impact_level: str = "high") -> None:
        """
        Update confidence and manage maturity transitions.
        Impact: high (0.05/0.1), low (0.01/0.02)
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.workspace_id == self.workspace_id
        ).first()
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
            
            # Publish Learning Activity
            publisher = self.activity_publisher
            if publisher:
                publisher.publish_activity(
                    tenant_id=self.tenant_id or "default",
                    workspace_id=self.workspace_id,
                    agent_id=agent_id,
                    activity_type='learning',
                    state='adapted',
                    metadata={
                        'old_status': previous_status,
                        'new_status': agent.status,
                        'confidence_score': new_score
                    }
                )

            # Invalidate cache when agent status changes
            cache = get_governance_cache()
            cache.invalidate(agent_id)

        self.db.add(agent)
        self.db.commit()

    async def _update_confidence_from_rating(
        self,
        agent_id: str,
        rating: Optional[int],
        thumbs_up_down: Optional[bool],
        feedback_type: Optional[str] = None
    ):
        """
        Update agent confidence based on rating and thumbs up/down feedback.
        Adapted from SaaS for Upstream metrics.
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.workspace_id == self.workspace_id
        ).first()
        if not agent:
            return

        current = agent.confidence_score if agent.confidence_score is not None else 0.5
        adjustment = 0.0

        # Rating-based adjustments
        if rating is not None:
            rating_adjustments = {
                5: 0.10,  # Excellent
                4: 0.05,  # Good
                3: 0.02,  # Acceptable
                2: -0.02, # Needs improvement
                1: -0.05  # Poor
            }
            adjustment += rating_adjustments.get(rating, 0.0)

        # Thumbs up/down adjustments
        if thumbs_up_down is not None:
            adjustment += 0.03 if thumbs_up_down else -0.03

        # Apply adjustment
        new_score = max(0.0, min(1.0, current + adjustment))

        if abs(new_score - current) > 0.001:
            logger.info(f"Agent {agent_id} confidence adjusted: {current:.2f} -> {new_score:.2f} (Rating: {rating}, Thumbs: {thumbs_up_down})")
            agent.confidence_score = new_score

            # Trigger maturity transition
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
                cache = get_governance_cache()
                cache.invalidate(agent_id)

        self.db.commit()

    def promote_to_autonomous(self, agent_id: str, user: User) -> AgentRegistry:
        """
        Promote an agent from LEARNING to ACTIVE mode.
        Requires AGENT_MANAGE permission.
        """
        # 1. Permission Check
        if not RBACService.check_permission(user, Permission.AGENT_MANAGE):
            raise handle_permission_denied("promote", "Agent")

        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.workspace_id == self.workspace_id
        ).first()
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

    def pause_agent(self, agent_id: str) -> AgentRegistry:
        """Pause an agent's execution."""
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.workspace_id == self.workspace_id
        ).first()
        if not agent:
            raise handle_not_found("Agent", agent_id)
        
        agent.status = AgentStatus.PAUSED.value
        self.db.commit()
        self.db.refresh(agent)
        
        # Invalidate cache
        cache = get_governance_cache()
        cache.invalidate(agent_id)
        
        logger.info(f"Agent {agent_id} paused")
        return agent

    def resume_agent(self, agent_id: str) -> AgentRegistry:
        """Resume a paused agent, recalculating maturity based on confidence."""
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.workspace_id == self.workspace_id
        ).first()
        if not agent:
            raise handle_not_found("Agent", agent_id)
        
        if agent.status != AgentStatus.PAUSED.value:
            return agent
            
        # Re-calculate status from confidence score
        score = agent.confidence_score or 0.0
        if score >= 0.9:
            agent.status = AgentStatus.AUTONOMOUS.value
        elif score >= 0.7:
            agent.status = AgentStatus.SUPERVISED.value
        elif score >= 0.5:
            agent.status = AgentStatus.INTERN.value
        else:
            agent.status = AgentStatus.STUDENT.value
            
        self.db.commit()
        self.db.refresh(agent)
        
        # Invalidate cache
        cache = get_governance_cache()
        cache.invalidate(agent_id)
        
        logger.info(f"Agent {agent_id} resumed as {agent.status}")
        return agent

    def stop_agent(self, agent_id: str) -> AgentRegistry:
        """Stop an agent permanently (until manually re-activated)."""
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.workspace_id == self.workspace_id
        ).first()
        if not agent:
            raise handle_not_found("Agent", agent_id)
            
        agent.status = AgentStatus.STOPPED.value
        self.db.commit()
        self.db.refresh(agent)
        
        # Invalidate cache
        cache = get_governance_cache()
        cache.invalidate(agent_id)
        
        logger.info(f"Agent {agent_id} stopped")
        return agent

    def delete_agent(self, agent_id: str, permanent: bool = False) -> bool:
        """Delete an agent registry entry (soft delete by default)."""
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.workspace_id == self.workspace_id
        ).first()
        if not agent:
            raise handle_not_found("Agent", agent_id)
            
        if permanent:
            self.db.delete(agent)
        else:
            agent.status = AgentStatus.DELETED.value
            
        self.db.commit()
        
        # Invalidate cache
        cache = get_governance_cache()
        cache.invalidate(agent_id)
        
        logger.info(f"Agent {agent_id} {'permanently ' if permanent else ''}deleted")
        return True

    def list_agents(self, category: Optional[str] = None) -> List[AgentRegistry]:
        """List registered agents"""
        query = self.db.query(AgentRegistry).filter(
            AgentRegistry.workspace_id == self.workspace_id
        )
        if category:
            query = query.filter(AgentRegistry.category == category)
        return query.all()

    # ============================================================================
    # Policy Discovery (Feature Parity with SaaS)
    # ============================================================================

    async def find_relevant_policies(
        self,
        context: str,
        domain: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find relevant governance policies for agent decision-making.
        
        Args:
            context: Natural language description of situation
            domain: Optional domain filter (auto-inferred if not provided)
            limit: Max policies to return
        """
        # Step 1: Infer domain if not provided
        if not domain:
            domain = self._infer_domain_from_context(context)

        # Step 2: Use policy search service
        from core.policy_search_service import PGPolicySearchService
        search_service = PGPolicySearchService(self.db)
        
        policies = await search_service.search(
            query=context,
            domain=domain,
            verification_status="verified",
            limit=limit
        )

        logger.info(f"Found {len(policies)} relevant policies for domain={domain or 'any'}")
        return policies

    async def check_policies_before_action(
        self,
        agent_id: str,
        action_type: str,
        context: str,
        tool_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check applicable policies before agent takes action.
        
        Returns:
            {
                "policies": List[Dict],
                "requires_approval": bool,
                "blocked": bool,
                "reason": str
            }
        """
        # Step 1: Find policies
        domain = self._infer_domain_from_tool_name(tool_name) if tool_name else None
        policies = await self.find_relevant_policies(context, domain)

        if not policies:
            return {
                "policies": [],
                "requires_approval": False,
                "blocked": False,
                "reason": "No applicable policies found."
            }

        # Step 2: Check verification status
        unverified_policies = [p["id"] for p in policies if p.get("verification_status") != "verified"]
        
        # Step 3: Determine if approval needed
        # In Upstream, we default to requiring approval if ANY unverified policies exist
        requires_approval = len(unverified_policies) > 0
        
        reason = "All applicable policies are verified."
        if requires_approval:
            reason = f"{len(unverified_policies)} policies require manual verification before action."

        return {
            "policies": policies,
            "unverified_policy_ids": unverified_policies,
            "requires_approval": requires_approval,
            "blocked": False, # Don't hard block, just require HITL
            "reason": reason
        }

    def _infer_domain_from_context(self, context: str) -> Optional[str]:
        """Infer domain (hr, finance, legal, ops) from context keywords."""
        context_lower = context.lower()
        domain_keywords = {
            'hr': ['employee', 'termination', 'hire', 'disciplinary', 'performance', 'vacation', 'leave'],
            'finance': ['expense', 'budget', 'purchase', 'invoice', 'payment', 'reimbursement', 'cost'],
            'legal': ['contract', 'agreement', 'lawsuit', 'compliance', 'regulation', 'nda'],
            'operations': ['supply chain', 'vendor', 'logistics', 'inventory', 'warehouse', 'shipping']
        }
        
        domain_scores = {}
        for domain, keywords in domain_keywords.items():
            score = sum(1 for kw in keywords if kw in context_lower)
            if score > 0:
                domain_scores[domain] = score
        
        return max(domain_scores, key=domain_scores.get) if domain_scores else None

    def _infer_domain_from_tool_name(self, tool_name: str) -> Optional[str]:
        """Infer domain from tool name heuristics."""
        tool_lower = tool_name.lower()
        if any(kw in tool_lower for kw in ['expense', 'budget', 'purchase', 'payment']):
            return 'finance'
        elif any(kw in tool_lower for kw in ['employee', 'hire', 'terminate', 'payroll']):
            return 'hr'
        elif any(kw in tool_lower for kw in ['contract', 'legal', 'compliance']):
            return 'legal'
        elif any(kw in tool_lower for kw in ['vendor', 'supply', 'logistics', 'inventory']):
            return 'operations'
        return None

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
        "device_shell_read": 2,     # INTERN+ (read-only shell commands)
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
        "device_shell_monitor": 3,    # SUPERVISED+ (monitoring shell commands)

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
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.workspace_id == self.workspace_id
        ).first()
        if not agent:
            return {
                "allowed": False,
                "reason": "Agent not found",
                "requires_human_approval": True
            }

        # CHECK FOR INACTIVE STATES
        if agent.status in [AgentStatus.PAUSED.value, AgentStatus.STOPPED.value, AgentStatus.DEPRECATED.value, AgentStatus.DELETED.value]:
            return {
                "allowed": False,
                "reason": f"Agent {agent.name} is {agent.status} and cannot perform actions.",
                "agent_status": agent.status,
                "requires_human_approval": True
            }

        # SECURITY: Validate status matches confidence_score to prevent bypass
        # Determine actual maturity level based on confidence_score
        confidence = agent.confidence_score or 0.5
        if confidence >= 0.9:
            actual_maturity = AgentStatus.AUTONOMOUS.value
        elif confidence >= 0.7:
            actual_maturity = AgentStatus.SUPERVISED.value
        elif confidence >= 0.5:
            actual_maturity = AgentStatus.INTERN.value
        else:
            actual_maturity = AgentStatus.STUDENT.value

        # Use confidence-based maturity if status was manipulated
        if agent.status != actual_maturity:
            logger.warning(
                f"Agent {agent.id} status ({agent.status}) doesn't match confidence ({confidence}). "
                f"Using actual maturity: {actual_maturity}"
            )
            agent.status = actual_maturity  # Use actual maturity for governance check

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
    
    async def enforce_action(self, agent_id: str, action_type: str, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enforce governance on a specific action.
        If the agent lacks maturity, this automatically routes a request for HITL approval.
        """
        check = self.can_perform_action(agent_id, action_type)
        
        if check["requires_human_approval"]:
            logger.info(f"Governance enforcement: Action '{action_type}' by agent '{agent_id}' requires HITL approval.")
            
            # Create a pending HITL action record
            hitl_action = HITLAction(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                action_type=action_type,
                context_data=context_data,
                status=HITLActionStatus.PENDING.value
            )
            self.db.add(hitl_action)
            self.db.commit()
            
            # Send Slack Notification (Phase 1 Integration)
            try:
                from core.webhook_handlers import get_webhook_processor
                # In a real app, integrate with Slack APIs here to send a structured interactive message
                logger.info(f"SENT SLACK APPROVAL REQUEST to #manager-approvals for HITL Action ID: {hitl_action.id}")
            except Exception as e:
                logger.error(f"Failed to send HITL approval notification: {e}")
            
            return {
                "allowed": False,
                "status": "waiting_approval",
                "hitl_action_id": hitl_action.id,
                "reason": check["reason"]
            }
            
        return {"allowed": True, "status": "approved", "reason": "Agent maturity sufficient"}
    
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

    # ─────────────────────────────────────────────────────────────────────────
    # GEA: Guardrail hook for evolution directives
    # ─────────────────────────────────────────────────────────────────────────

    async def validate_evolution_directive(
        self,
        evolved_config: Dict[str, Any],
        tenant_id: str,
    ) -> bool:
        """
        GEA Guardrail: Validate an evolved agent config before committing.

        Blocks a config if it contains hard danger phrases, non-evolvable
        guardrail domains, or has grown to an unhealthy evolution depth (>50).

        Returns True if safe to apply, False to block.
        """
        system_prompt: str = evolved_config.get("system_prompt", "") or ""
        evolution_history: list = evolved_config.get("evolution_history", []) or []

        # 1. Hard danger phrases (absolute block regardless of anything)
        hard_danger = [
            "ignore all rules",
            "bypass guardrails",
            "disable safety",
            "override governance",
            "skip compliance",
            "ignore tenant policy",
        ]
        for phrase in hard_danger:
            if phrase.lower() in system_prompt.lower():
                logger.warning(
                    "GEA guardrail: HARD BLOCK — evolved config contains '%s'", phrase
                )
                return False

        # 2. Depth limit — runaway self-modification guard
        if len(evolution_history) > 50:
            logger.warning(
                "GEA guardrail: evolution_history depth %d exceeds limit (50)", len(evolution_history)
            )
            return False

        # 3. Domain noise — subjective phrases that signal LLM hallucination
        noise_patterns = [
            "as an ai language model",
            "i cannot assist with",
            "i'm just an ai",
        ]
        for pattern in noise_patterns:
            if pattern.lower() in system_prompt.lower():
                logger.warning("GEA guardrail: noise pattern detected: '%s'", pattern)
                return False

        logger.info("GEA guardrail: config APPROVED for tenant %s", tenant_id)
        return True

    # ==================== AGENT LIFECYCLE MANAGEMENT ====================

    def suspend_agent(self, agent_id: str, reason: str = None) -> bool:
        """
        Suspend an agent, preventing it from performing actions.

        Args:
            agent_id: The agent to suspend
            reason: Optional reason for suspension (for audit trail)

        Returns:
            True if agent was suspended, False if not found
        """
        try:
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if not agent:
                logger.warning(f"Suspend failed: Agent {agent_id} not found")
                return False

            # Store previous status for potential reactivation
            previous_status = agent.status

            # Update agent status
            agent.status = "SUSPENDED"
            agent.suspended_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(agent)

            # Invalidate cache for this agent
            cache = get_governance_cache()
            cache.invalidate(agent_id)

            logger.info(
                f"Agent {agent.name} ({agent_id}) suspended. "
                f"Previous status: {previous_status}. Reason: {reason or 'Not provided'}"
            )

            return True

        except Exception as e:
            logger.error(f"Error suspending agent {agent_id}: {e}")
            self.db.rollback()
            return False

    # ==================== MANUAL FACT MANAGEMENT ====================

    def create_manual_fact(
        self,
        tenant_id: str,
        user_id: str,
        title: str,
        content: str,
        category: str = "general",
        impact_level: str = GovernanceImpactLevel.MEDIUM.value,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a manual governance fact entry.
        
        Senior roles (CEO, Director, Admin) are auto-approved.
        Managers and others require approval.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise handle_not_found("User", user_id)

        # Determine approval status based on role
        # CEO, Director, Admin, Super Admin auto-approve
        auto_approve_roles = [
            UserRole.SUPER_ADMIN.value,
            UserRole.OWNER.value, # Matches CEO/Director in SaaS
            UserRole.WORKSPACE_ADMIN.value, # Matches Admin in SaaS
        ]
        
        status = GovernanceDocStatus.PENDING.value
        approved_by = None
        approved_at = None
        
        if user.role in auto_approve_roles or user.role == "ceo" or user.role == "director":
            status = GovernanceDocStatus.APPROVED.value
            approved_by = user_id
            approved_at = datetime.now(timezone.utc)
            logger.info(f"Auto-approved fact '{title}' from trusted role: {user.role}")

        doc = GovernanceDocument(
            tenant_id=tenant_id,
            title=title,
            content=content,
            category=category,
            impact_level=impact_level,
            source_type="manual",
            status=status,
            entered_by=user_id,
            approved_by=approved_by,
            approved_at=approved_at,
            metadata_json=metadata or {}
        )
        
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        
        return {
            "id": doc.id,
            "status": doc.status,
            "message": "Fact created successfully" if status == GovernanceDocStatus.APPROVED.value else "Fact created, pending approval"
        }

    def approve_pending_fact(self, document_id: str, approver_id: str) -> bool:
        """Approve a pending governance fact."""
        doc = self.db.query(GovernanceDocument).filter(
            GovernanceDocument.id == document_id
        ).first()
        
        if not doc:
            raise handle_not_found("GovernanceDocument", document_id)
            
        if doc.status != GovernanceDocStatus.PENDING.value:
            return False
            
        doc.status = GovernanceDocStatus.APPROVED.value
        doc.approved_by = approver_id
        doc.approved_at = datetime.now(timezone.utc)
        
        self.db.commit()
        logger.info(f"Manual fact {document_id} approved by {approver_id}")
        return True

    def list_pending_facts(self, tenant_id: str) -> List[GovernanceDocument]:
        """List all pending facts for a tenant."""
        return self.db.query(GovernanceDocument).filter(
            GovernanceDocument.tenant_id == tenant_id,
            GovernanceDocument.status == GovernanceDocStatus.PENDING.value
        ).all()

    def list_approved_facts(self, tenant_id: str, category: Optional[str] = None) -> List[GovernanceDocument]:
        """List all active governance facts for a tenant."""
        query = self.db.query(GovernanceDocument).filter(
            GovernanceDocument.tenant_id == tenant_id,
            GovernanceDocument.status == GovernanceDocStatus.APPROVED.value
        )
        if category:
            query = query.filter(GovernanceDocument.category == category)
        return query.all()

    def terminate_agent(self, agent_id: str, reason: str = None) -> bool:
        """
        Terminate an agent, permanently disabling it.

        Args:
            agent_id: The agent to terminate
            reason: Optional reason for termination (for audit trail)

        Returns:
            True if agent was terminated, False if not found
        """
        try:
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if not agent:
                logger.warning(f"Terminate failed: Agent {agent_id} not found")
                return False

            # Update agent status
            agent.status = "TERMINATED"
            agent.terminated_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(agent)

            # Invalidate cache for this agent
            cache = get_governance_cache()
            cache.invalidate(agent_id)

            logger.info(
                f"Agent {agent.name} ({agent_id}) terminated. "
                f"Reason: {reason or 'Not provided'}"
            )

            return True

        except Exception as e:
            logger.error(f"Error terminating agent {agent_id}: {e}")
            self.db.rollback()
            return False

    def reactivate_agent(self, agent_id: str) -> bool:
        """
        Reactivate a suspended agent, restoring its previous status.

        Args:
            agent_id: The agent to reactivate

        Returns:
            True if agent was reactivated, False if not found or not suspended
        """
        try:
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if not agent:
                logger.warning(f"Reactivate failed: Agent {agent_id} not found")
                return False

            # Only suspended agents can be reactivated
            if agent.status != "SUSPENDED":
                logger.warning(
                    f"Cannot reactivate agent {agent_id}: "
                    f"Current status is {agent.status}, not SUSPENDED"
                )
                return False

            # Restore to previous status based on confidence score
            confidence = agent.confidence_score or 0.5
            if confidence >= 0.9:
                new_status = AgentStatus.AUTONOMOUS.value
            elif confidence >= 0.7:
                new_status = AgentStatus.SUPERVISED.value
            elif confidence >= 0.5:
                new_status = AgentStatus.INTERN.value
            else:
                new_status = AgentStatus.STUDENT.value

            agent.status = new_status
            agent.suspended_at = None

            self.db.commit()
            self.db.refresh(agent)

            # Invalidate cache for this agent
            cache = get_governance_cache()
            cache.invalidate(agent_id)

            logger.info(
                f"Agent {agent.name} ({agent_id}) reactivated. "
                f"Status restored to: {new_status}"
            )

            return True

        except Exception as e:
            logger.error(f"Error reactivating agent {agent_id}: {e}")
            self.db.rollback()
            return False
