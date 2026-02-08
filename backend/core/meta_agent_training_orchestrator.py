"""
Meta Agent Training Orchestrator

Extends Atom Meta Agent with training and proposal capabilities.
Generates training scenarios, reviews INTERN proposals, and conducts training sessions.
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.models import (
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    BlockedTriggerContext,
    ProposalStatus,
    ProposalType,
    TrainingSession,
)

logger = logging.getLogger(__name__)


class TrainingProposal:
    """Generated training proposal for STUDENT agents"""
    def __init__(
        self,
        title: str,
        description: str,
        learning_objectives: List[str],
        capability_gaps: List[str],
        estimated_duration_hours: float,
        training_steps: List[Dict[str, Any]]
    ):
        self.title = title
        self.description = description
        self.learning_objectives = learning_objectives
        self.capability_gaps = capability_gaps
        self.estimated_duration_hours = estimated_duration_hours
        self.training_steps = training_steps


class ProposalReview:
    """Meta Agent's review of INTERN agent proposal"""
    def __init__(
        self,
        recommendation: str,  # "approve", "modify", "reject"
        confidence: float,  # 0.0 to 1.0
        reasoning: str,
        suggested_modifications: Optional[List[str]] = None,
        concerns: Optional[List[str]] = None
    ):
        self.recommendation = recommendation
        self.confidence = confidence
        self.reasoning = reasoning
        self.suggested_modifications = suggested_modifications or []
        self.concerns = concerns or []


class TrainingResult:
    """Result of training session"""
    def __init__(
        self,
        session_id: str,
        success: bool,
        performance_score: float,
        capabilities_developed: List[str],
        supervisor_feedback: str,
        should_promote: bool
    ):
        self.session_id = session_id
        self.success = success
        self.performance_score = performance_score
        self.capabilities_developed = capabilities_developed
        self.supervisor_feedback = supervisor_feedback
        self.should_promote = should_promote


class MetaAgentTrainingOrchestrator:
    """
    Meta Agent capabilities for training and proposal management.

    Key responsibilities:
    - Generate training proposals for STUDENT agents
    - Review INTERN agent proposals
    - Conduct training sessions with human supervisors
    - Select appropriate training scenario templates
    """

    # Training scenario templates
    SCENARIO_TEMPLATES = {
        "Finance": {
            "name": "Finance Fundamentals",
            "scenarios": [
                "Reconciliation Training",
                "Financial Analysis",
                "Transaction Categorization",
                "Report Generation"
            ]
        },
        "Sales": {
            "name": "Sales Operations",
            "scenarios": [
                "Lead Scoring Exercise",
                "CRM Update Training",
                "Outreach Communication",
                "Pipeline Management"
            ]
        },
        "Operations": {
            "name": "Process Automation",
            "scenarios": [
                "Inventory Management",
                "Logistics Coordination",
                "Process Optimization",
                "Scheduling Tasks"
            ]
        },
        "HR": {
            "name": "HR Management",
            "scenarios": [
                "Onboarding Workflow",
                "Policy Q&A Training",
                "Employee Data Management",
                "Documentation Tasks"
            ]
        },
        "Support": {
            "name": "Customer Support",
            "scenarios": [
                "Ticket Resolution",
                "Customer Communication",
                "Escalation Handling",
                "Knowledge Base Usage"
            ]
        }
    }

    def __init__(self, db: Session):
        self.db = db

    async def propose_training_scenario(
        self,
        student_agent_id: str,
        blocked_task: Dict[str, Any],
        agent_capabilities: List[str]
    ) -> TrainingProposal:
        """
        Analyze blocked trigger and generate training proposal for STUDENT agents.

        Process:
        1. Analyze what the student was supposed to do
        2. Identify capability gaps
        3. Select appropriate training scenario template
        4. Personalize based on agent's current capabilities
        5. Generate learning objectives
        6. Create proposal with clear steps
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == student_agent_id
        ).first()

        if not agent:
            raise ValueError(f"Agent {student_agent_id} not found")

        logger.info(
            f"Generating training proposal for STUDENT agent {agent.id} "
            f"(category: {agent.category}, confidence: {agent.confidence_score:.2f})"
        )

        # Identify capability gaps
        capability_gaps = await self._analyze_capability_gaps(
            blocked_task, agent_capabilities, agent.category
        )

        # Select scenario template
        scenario_template = self._select_scenario_template(
            agent.category, blocked_task
        )

        # Generate learning objectives
        learning_objectives = await self._generate_learning_objectives(
            agent, blocked_task, capability_gaps
        )

        # Generate training steps
        training_steps = await self._generate_training_steps(
            scenario_template, capability_gaps, blocked_task
        )

        # Estimate duration
        estimated_hours = len(training_steps) * 4  # ~4 hours per step

        title = f"Training: {agent.name} - {scenario_template['name']}"

        description = f"""
This training plan addresses the agent's inability to handle automated triggers.

**Agent Status:** STUDENT (confidence: {agent.confidence_score:.2f})
**Blocked Task:** {blocked_task.get('trigger_type', 'Unknown')}
**Capability Gaps:** {len(capability_gaps)} identified

**Training Focus:** {scenario_template['name']}

After completing this training, the agent will be able to:
{chr(10).join(f'- {obj}' for obj in learning_objectives[:5])}
        """.strip()

        logger.info(
            f"Generated training proposal with {len(training_steps)} steps, "
            f"estimated {estimated_hours} hours"
        )

        return TrainingProposal(
            title=title,
            description=description,
            learning_objectives=learning_objectives,
            capability_gaps=capability_gaps,
            estimated_duration_hours=estimated_hours,
            training_steps=training_steps
        )

    async def review_intern_proposal(
        self,
        proposal: AgentProposal
    ) -> ProposalReview:
        """
        Review INTERN agent's action proposal.

        Meta Agent evaluates:
        - Is the proposed action appropriate?
        - Are there any risks or concerns?
        - Should modifications be suggested?
        - Provide recommendation (approve/modify/reject)

        Returns recommendation with confidence score and reasoning.
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == proposal.agent_id
        ).first()

        if not agent:
            raise ValueError(f"Agent {proposal.agent_id} not found")

        logger.info(
            f"Reviewing INTERN proposal {proposal.id} from agent {agent.id}"
        )

        # Analyze proposed action
        proposed_action = proposal.proposed_action or {}
        action_type = proposed_action.get("action_type", "unknown")

        # Risk assessment
        risk_level = await self._assess_proposal_risk(proposed_action, agent)

        # Check for appropriateness
        is_appropriate = await self._check_action_appropriateness(
            proposed_action, agent.category
        )

        # Generate review
        if risk_level == "low" and is_appropriate:
            # Approve
            recommendation = "approve"
            confidence = 0.9
            reasoning = f"""
Proposal appears appropriate and low-risk.

**Action Type:** {action_type}
**Agent Category:** {agent.category}
**Agent Confidence:** {agent.confidence_score:.2f}

The proposed action aligns with the agent's capabilities and category.
Recommend proceeding with human approval.
            """.strip()
            suggested_modifications = None
            concerns = None

        elif risk_level == "medium" or not is_appropriate:
            # Suggest modifications
            recommendation = "modify"
            confidence = 0.7
            reasoning = f"""
Proposal requires modifications before approval.

**Action Type:** {action_type}
**Risk Level:** {risk_level}
**Concerns:** See suggested modifications

The agent should address the following concerns before execution.
            """.strip()

            suggested_modifications = await self._generate_modifications(
                proposed_action, agent
            )
            concerns = suggested_modifications

        else:  # high risk
            # Reject
            recommendation = "reject"
            confidence = 0.8
            reasoning = f"""
Proposal is too high-risk for approval.

**Action Type:** {action_type}
**Risk Level:** {risk_level}

This action requires additional training or human intervention.
            """.strip()
            suggested_modifications = None
            concerns = ["High risk detected", "Agent capabilities insufficient"]

        logger.info(
            f"Review complete: {recommendation} (confidence: {confidence:.2f})"
        )

        return ProposalReview(
            recommendation=recommendation,
            confidence=confidence,
            reasoning=reasoning.strip(),
            suggested_modifications=suggested_modifications,
            concerns=concerns
        )

    async def conduct_training_session(
        self,
        proposal: AgentProposal,
        human_supervisor_id: str
    ) -> TrainingResult:
        """
        Facilitate human-in-the-loop training session for STUDENT agents.

        Process:
        1. Present training scenario step-by-step
        2. Allow student agent to attempt each step
        3. Supervisor provides real-time guidance
        4. Track performance and errors
        5. Assess readiness for autonomy

        Note: This is a framework method. Actual session execution
        is handled by frontend UI with WebSocket events.
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == proposal.agent_id
        ).first()

        if not agent:
            raise ValueError(f"Agent {proposal.agent_id} not found")

        logger.info(
            f"Conducting training session for agent {agent.id} "
            f"with supervisor {human_supervisor_id}"
        )

        # This method creates the training session structure
        # Actual execution is interactive via WebSocket
        session = self.db.query(TrainingSession).filter(
            TrainingSession.proposal_id == proposal.id
        ).first()

        if not session:
            raise ValueError(f"Training session for proposal {proposal.id} not found")

        # Initialize session
        session.status = "in_progress"
        session.started_at = datetime.now()
        session.supervisor_id = human_supervisor_id
        self.db.commit()

        logger.info(f"Training session {session.id} initialized")

        # Return result structure (will be populated as training progresses)
        return TrainingResult(
            session_id=session.id,
            success=False,  # Will be updated on completion
            performance_score=0.0,
            capabilities_developed=[],
            supervisor_feedback="",
            should_promote=False
        )

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    async def _analyze_capability_gaps(
        self,
        blocked_task: Dict[str, Any],
        agent_capabilities: List[str],
        agent_category: str
    ) -> List[str]:
        """Analyze what capabilities the agent is missing"""
        gaps = []

        # Task-specific gaps
        task_type = blocked_task.get("trigger_type", "")
        if "workflow" in task_type.lower():
            gaps.extend(["workflow_automation", "task_coordination"])
        if "form" in task_type.lower():
            gaps.extend(["form_processing", "data_validation"])

        # Category-specific gaps
        category_gaps = {
            "Finance": ["financial_analysis", "reconciliation", "reporting"],
            "Sales": ["lead_management", "crm_operations", "sales_process"],
            "Operations": ["process_automation", "inventory_management", "scheduling"],
            "HR": ["policy_knowledge", "onboarding", "employee_data"],
            "Support": ["ticket_resolution", "customer_communication", "escalation_handling"]
        }

        if agent_category in category_gaps:
            # Filter out capabilities agent already has
            for gap in category_gaps[agent_category]:
                if gap not in agent_capabilities:
                    gaps.append(gap)

        return list(set(gaps))  # Dedupe

    def _select_scenario_template(
        self,
        agent_category: str,
        blocked_task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Select appropriate training scenario template"""
        # Default to General Operations if category not found
        return self.SCENARIO_TEMPLATES.get(
            agent_category,
            {
                "name": "General Operations",
                "scenarios": ["Basic Task Execution", "Data Processing", "Decision Making"]
            }
        )

    async def _generate_learning_objectives(
        self,
        agent: AgentRegistry,
        blocked_task: Dict[str, Any],
        capability_gaps: List[str]
    ) -> List[str]:
        """Generate clear learning objectives"""
        objectives = [
            f"Understand {blocked_task.get('trigger_type', 'task')} execution flow",
            "Demonstrate reliable task completion",
            "Show consistent decision-making patterns"
        ]

        # Add capability-specific objectives (top 5)
        for gap in capability_gaps[:5]:
            objectives.append(f"Develop proficiency in {gap.replace('_', ' ')}")

        return objectives

    async def _generate_training_steps(
        self,
        scenario_template: Dict[str, Any],
        capability_gaps: List[str],
        blocked_task: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate step-by-step training plan"""
        steps = []

        # Step 1: Introduction and context
        steps.append({
            "step_number": 1,
            "title": "Introduction and Context",
            "description": f"Understand the {scenario_template['name']} domain and why this training matters",
            "type": "theory",
            "estimated_minutes": 30
        })

        # Step 2: Concept walkthrough
        steps.append({
            "step_number": 2,
            "title": "Concept Walkthrough",
            "description": "Learn the core concepts and best practices",
            "type": "theory",
            "estimated_minutes": 45
        })

        # Step 3-N: Practical exercises for each capability gap
        for i, gap in enumerate(capability_gaps[:5], start=3):
            steps.append({
                "step_number": i,
                "title": f"Practice: {gap.replace('_', ' ').title()}",
                "description": f"Hands-on exercise to develop {gap} skills",
                "type": "practice",
                "estimated_minutes": 60
            })

        # Final step: Assessment
        steps.append({
            "step_number": len(steps) + 1,
            "title": "Comprehensive Assessment",
            "description": "Demonstrate all learned skills in a realistic scenario",
            "type": "assessment",
            "estimated_minutes": 90
        })

        return steps

    async def _assess_proposal_risk(
        self,
        proposed_action: Dict[str, Any],
        agent: AgentRegistry
    ) -> str:
        """Assess risk level of proposed action"""
        action_type = proposed_action.get("action_type", "")

        # High-risk actions
        if action_type in ["delete", "payment", "data_export", "permissions_change"]:
            return "high"

        # Medium-risk actions
        if action_type in ["update", "create", "send", "publish"]:
            if agent.confidence_score < 0.6:
                return "medium"
            return "low"

        # Low-risk actions
        return "low"

    async def _check_action_appropriateness(
        self,
        proposed_action: Dict[str, Any],
        agent_category: str
    ) -> bool:
        """Check if action is appropriate for agent's category"""
        action_type = proposed_action.get("action_type", "")

        # Simple category-action mapping
        appropriate_actions = {
            "Finance": ["reconciliation", "analysis", "report", "categorize"],
            "Sales": ["lead_update", "crm_update", "outreach", "pipeline"],
            "Operations": ["inventory", "logistics", "scheduling", "process"],
            "HR": ["onboarding", "policy", "employee_data", "documentation"],
            "Support": ["ticket", "response", "escalation", "communication"]
        }

        if agent_category in appropriate_actions:
            return any(
                act in action_type.lower()
                for act in appropriate_actions[agent_category]
            )

        return True  # Default to appropriate if no mapping

    async def _generate_modifications(
        self,
        proposed_action: Dict[str, Any],
        agent: AgentRegistry
    ) -> List[str]:
        """Generate suggested modifications for proposal"""
        modifications = []

        # Low confidence agents need more guidance
        if agent.confidence_score < 0.6:
            modifications.append("Add more detailed reasoning for the proposed action")
            modifications.append("Include step-by-step execution plan")

        # Check for missing information
        if "reasoning" not in proposed_action or not proposed_action["reasoning"]:
            modifications.append("Provide detailed reasoning for this action")

        if "expected_outcome" not in proposed_action:
            modifications.append("Describe the expected outcome of this action")

        return modifications
