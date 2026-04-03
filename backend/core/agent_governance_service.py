from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Union
import uuid
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

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
    TokenUsage,
)
from core.rbac_service import Permission, RBACService
from core.continuous_learning_service import ContinuousLearningService
from core.activity_publisher import ActivityPublisher
from core.autonomous_guardrails import AutonomousGuardrailService
from core.policy_search_service import PGPolicySearchService

logger = logging.getLogger(__name__)

class AgentGovernanceService:
    # Action complexity levels - higher = more complex/risky
    # Reconciled from SaaS Phase 204
    ACTION_COMPLEXITY = {
        # Level 1: READ ONLY - Student Agents
        "search": 1,
        "read": 1,
        "list": 1,
        "get": 1,
        "fetch": 1,
        "summarize": 1,
        "check": 1,
        "verify": 1,
        "get_account": 1,
        "list_leads": 1,
        "get_contact": 1,
        "get_channels": 1,
        "get_messages": 1,
        "list_users": 1,
        "get_tasks": 1,
        "list_projects": 1,
        "fetch_page": 1,
        "get_deal": 1,
        "list_deals": 1,
        "get_ticket": 1,
        "list_tickets": 1,
        "get_email": 1,
        "list_emails": 1,
        "shell_read": 1,
        "shell_network": 1,
        
        # Level 2: PROPOSE / DRAFT - Intern Agents
        "analyze": 2,
        "suggest": 2,
        "draft": 2,
        "generate": 2,
        "recommend": 2,
        "propose": 2,
        "plan": 2,
        "suggest_reply": 2,
        "draft_message": 2,
        "analyze_lead": 2,
        "recommend_action": 2,
        "generate_report": 2,
        "draft_email": 2,
        "propose_lead": 2,
        "suggest_task": 2,
        
        # Level 3: EXECUTE (Supervised) - Supervised Agents
        "create": 3,
        "update": 3,
        "send_email": 3,
        "email_send": 3,
        "browser_navigate": 3,
        "browser_action": 3,
        "post_message": 3,
        "schedule": 3,
        "upload": 3,
        "create_lead": 3,
        "update_lead": 3,
        "send_message": 3,
        "create_task": 3,
        "update_task": 3,
        "create_deal": 3,
        "update_deal": 3,
        "update_contact": 3,
        "create_contact": 3,
        "add_comment": 3,
        "update_ticket": 3,
        "create_ticket": 3,
        "schedule_meeting": 3,
        "shell_write": 3,
        "shell_build": 3,
        "shell_devops": 3,
        
        # Level 4: CRITICAL (Autonomous) - Autonomous Agents
        "delete": 4,
        "execute": 4,
        "terminal_command": 4,
        "run_local_terminal": 4,
        "deploy": 4,
        "transfer": 4,
        "payment": 4,
        "approve": 4,
        "write_code_file": 4,
        "delete_lead": 4,
        "delete_task": 4,
        "delete_message": 4,
        "execute_workflow": 4,
        "transfer_record": 4,
        "bulk_delete": 4,
        "delete_contact": 4,
        "delete_deal": 4,
        "delete_ticket": 4,
        "bulk_update": 4,
        "transfer_owner": 4,
        "shell_delete": 4,
    }

    # Minimum maturity level for each action complexity
    MATURITY_REQUIREMENTS = {
        1: AgentStatus.STUDENT,
        2: AgentStatus.INTERN,
        3: AgentStatus.SUPERVISED,
        4: AgentStatus.AUTONOMOUS,
    }

    def __init__(
        self,
        db: Session,
        workspace_id: str = "default",
        activity_publisher: Optional[ActivityPublisher] = None
    ):
        self.db = db
        self.workspace_id = workspace_id
        self.activity_publisher = activity_publisher
        self.continuous_learning = ContinuousLearningService(db)

    def register_or_update_agent(
        self, 
        name: str, 
        category: str,
        module_path: str,
        class_name: str,
        description: str = None,
        handle: Optional[str] = None,
        display_name: Optional[str] = None,
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
                handle=handle,
                display_name=display_name,
                workspace_id=self.workspace_id,
                status=AgentStatus.STUDENT.value,
                confidence_score=0.5
            )
            self.db.add(agent)
            logger.info(f"Registered new agent: {name}")
        else:
            # Update meta
            agent.name = name
            agent.category = category
            agent.description = description
            if handle: agent.handle = handle
            if display_name: agent.display_name = display_name
            
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
        """Submit feedback and trigger continuous learning"""
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.workspace_id == self.workspace_id
        ).first()
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
        
        await self._adjudicate_feedback(feedback)
        return feedback

    async def _adjudicate_feedback(self, feedback: AgentFeedback) -> None:
        """Judge the validity of user feedback and update agent readiness"""
        user = self.db.query(User).filter(User.id == feedback.user_id).first()
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == feedback.agent_id,
            AgentRegistry.workspace_id == self.workspace_id
        ).first()
        
        is_admin = user.role in [UserRole.WORKSPACE_ADMIN, UserRole.SUPER_ADMIN]
        is_specialty_match = user.specialty and agent.category and user.specialty.lower() == agent.category.lower()
        is_trusted = is_admin or is_specialty_match

        if is_trusted:
            feedback.status = FeedbackStatus.ACCEPTED.value
            feedback.ai_reasoning = f"Accepted by trusted {user.role}."
            self._update_confidence_score(agent.id, positive=False, impact_level="high")
            
            try:
                self.continuous_learning.update_from_feedback(feedback)
            except Exception as e:
                logger.warning(f"Continuous learning update failed: {e}")
        else:
            feedback.status = FeedbackStatus.PENDING.value
            feedback.ai_reasoning = "Pending specialty review."
            self._update_confidence_score(agent.id, positive=False, impact_level="low")

        self.db.commit()

    def _update_confidence_score(self, agent_id: str, positive: bool, impact_level: str = "high") -> None:
        """Update confidence and manage maturity transitions"""
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.workspace_id == self.workspace_id
        ).first()
        if not agent: return

        current = agent.confidence_score or 0.5
        boost = 0.05 if impact_level == "high" else 0.01
        penalty = 0.1 if impact_level == "high" else 0.02
        
        new_score = min(1.0, current + boost) if positive else max(0.0, current - penalty)
        agent.confidence_score = new_score
        
        prev_status = agent.status
        if new_score >= 0.9: agent.status = AgentStatus.AUTONOMOUS.value
        elif new_score >= 0.7: agent.status = AgentStatus.SUPERVISED.value
        elif new_score >= 0.5: agent.status = AgentStatus.INTERN.value
        else: agent.status = AgentStatus.STUDENT.value

        if agent.status != prev_status:
            logger.info(f"Agent {agent.name} transitioned: {prev_status} -> {agent.status}")
            if self.activity_publisher:
                self.activity_publisher.publish_activity(
                    workspace_id=self.workspace_id,
                    agent_id=agent_id,
                    activity_type='learning',
                    state='adapted',
                    metadata={'old_status': prev_status, 'new_status': agent.status, 'confidence': new_score}
                )
            get_governance_cache().invalidate(agent_id)
        
        self.db.commit()

    # --- ADVANCED GOVERNANCE (SaaS Port) ---

    def can_perform_action(
        self,
        agent_id: str,
        action_type: str,
        require_approval: bool = False,
        chain_id: Optional[str] = None, # NEW Phase 10
    ) -> Dict[str, Any]:
        """Hybrid maturity check with complexity-based enforcement"""
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.workspace_id == self.workspace_id
        ).first()
        
        if not agent:
            return {"allowed": False, "reason": "Agent not found", "requires_approval": True}

        if agent.status in [AgentStatus.PAUSED.value, AgentStatus.STOPPED.value]:
            return {"allowed": False, "reason": f"Agent is {agent.status}", "requires_approval": True}

        # Find complexity (Level 1-4)
        action_lower = action_type.lower()
        complexity = 2 # Default
        matches = [lvl for act, lvl in self.ACTION_COMPLEXITY.items() if act in action_lower]
        if matches: complexity = max(matches)
        
        required_status = self.MATURITY_REQUIREMENTS.get(complexity, AgentStatus.SUPERVISED)
        
        maturity_order = [s.value for s in [AgentStatus.STUDENT, AgentStatus.INTERN, AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS]]
        agent_idx = maturity_order.index(agent.status) if agent.status in maturity_order else 0
        req_idx = maturity_order.index(required_status.value)

        allowed = agent_idx >= req_idx
        approval_needed = not allowed or (agent.status == AgentStatus.SUPERVISED.value and complexity >= 3) or require_approval

        # Budget Check (requires tenant_id - skip if not available)
        if allowed:
            try:
                import asyncio
                from core.budget_enforcement_service import BudgetEnforcementService
                budget_svc = BudgetEnforcementService(self.db)

                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                budget_check = loop.run_until_complete(
                    budget_svc.check_budget_before_action(
                        tenant_id=self.workspace_id,  # Use workspace_id as tenant_id
                        agent_id=agent_id,
                        action=action_type,
                        chain_id=chain_id
                    )
                )
                if not budget_check.get("allowed", True):
                    return {
                        "allowed": False,
                        "reason": budget_check.get("reason"),
                        "requires_approval": True,
                        "status_code": "BUDGET_EXCEEDED"
                    }
            except Exception as e:
                # Budget service not available or failed - log warning but continue
                logger.warning(f"Budget check skipped: {e}")

        # NEW Phase 10: Fleet-wide recursion guardrails
        if chain_id:
            from core.models import DelegationChain
            chain = self.db.query(DelegationChain).filter(DelegationChain.id == chain_id).first()
            if chain:
                if len(chain.links) >= chain.max_depth:
                    logger.warning(f"Recursion depth limit reached (chain: {chain_id}). Blocking recruitment.")
                    return {
                        "allowed": False,
                        "reason": f"Fleet recursion depth limit ({chain.max_depth}) reached.",
                        "requires_approval": True,
                        "status_code": "RECURSION_LIMIT"
                    }

        return {
            "allowed": allowed,
            "reason": f"Maturity check failed. Required: {required_status.value}" if not allowed else "Maturity check passed.",
            "agent_status": agent.status,
            "action_complexity": complexity,
            "required_status": required_status.value,
            "requires_approval": approval_needed,
            "confidence": agent.confidence_score or 0.5
        }

    def enforce_action(
        self,
        agent_id: str,
        action_type: str,
        action_details: Optional[Dict] = None,
        chain_id: Optional[str] = None # NEW Phase 10
    ) -> Dict[str, Any]:
        """Main entry point for action enforcement including guardrails"""
        check = self.can_perform_action(agent_id, action_type, chain_id=chain_id)
        
        if not check["allowed"]:
            return {"proceed": False, "status": "BLOCKED", "reason": check["reason"], "action_required": "HUMAN_APPROVAL"}
        
        if check["requires_approval"]:
            return {"proceed": True, "status": "PENDING_APPROVAL", "reason": "Requires oversight", "action_required": "WAIT_FOR_APPROVAL"}

        # Autonomous Guardrails
        if check["agent_status"] == AgentStatus.AUTONOMOUS.value:
            gr = AutonomousGuardrailService(self.db, workspace_id=self.workspace_id)
            gr_check = gr.check_guardrails(agent_id, action_type, action_details or {})
            if not gr_check["proceed"]:
                if gr_check.get("requires_downgrade"):
                    gr.handle_violation(agent_id, gr_check["violation_type"], gr_check["reason"])
                return {"proceed": False, "status": "BLOCKED_BY_GUARDRAIL", "reason": gr_check["reason"], "action_required": "HUMAN_APPROVAL"}

        return {"proceed": True, "status": "APPROVED", "reason": check["reason"], "action_required": None}

    # Policy Discovery
    async def find_relevant_policies(self, context: str, domain: Optional[str] = None, limit: int = 5) -> List[Dict]:
        search_svc = PGPolicySearchService(self.db)
        return await search_svc.search(query=context, domain=domain, limit=limit)

    def request_approval(
        self, 
        agent_id: str, 
        action_type: str, 
        params: Dict, 
        reason: str,
        chain_id: Optional[str] = None # NEW Phase 10
    ) -> str:
        hitl = HITLAction(
            id=str(uuid.uuid4()),
            workspace_id=self.workspace_id,
            agent_id=agent_id,
            action_type=action_type,
            platform="internal",
            params=params,
            status=HITLActionStatus.PENDING.value,
            reason=reason,
            # NEW Phase 10 association
            chain_id=chain_id
        )

        # Capture blackboard snapshot if it's a fleet operation
        if chain_id:
            from core.models import DelegationChain
            chain = self.db.query(DelegationChain).filter(DelegationChain.id == chain_id).first()
            if chain:
                hitl.context_snapshot = chain.metadata_json

        self.db.add(hitl)
        self.db.commit()
        return hitl.id

    def get_approval_status(self, action_id: str) -> Dict[str, Any]:
        """Check if a HITL action has been decided (Phase 10 Hardened)"""
        hitl = self.db.query(HITLAction).filter(HITLAction.id == action_id).first()
        if not hitl:
            return {"status": "not_found"}
        
        return {
            "id": hitl.id,
            "status": hitl.status,
            "chain_id": hitl.chain_id,
            "context_snapshot": hitl.context_snapshot,
            "user_feedback": hitl.user_feedback,
            "reviewed_at": hitl.reviewed_at
        }

    async def record_outcome(self, agent_id: str, success: bool) -> None:
        """Record the success/failure of an action for learning"""
        # Placeholder for outcome recording logic
        logger.info(f"Recorded outcome for {agent_id}: {'success' if success else 'failure'}")
        self._update_confidence_score(agent_id, positive=success, impact_level="low")
