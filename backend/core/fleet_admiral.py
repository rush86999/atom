"""
Fleet Admiral - Dynamic Agent Recruitment Orchestrator (Single-Tenant)

Wraps AgentFleetService with meta-agent responsibilities:
- Analyzes task requirements
- Recruits specialist agents
- Coordinates fleet execution
- Manages blackboard state

SINGLE-TENANT ARCHITECTURE:
- Uses user_id instead of tenant_id
- No BudgetEnforcementService (no billing/quota in upstream)
- No multi-tenant isolation
- Self-hosted deployment

Ported from: rush86999/atom-saas@6c5f4e3d4
Changes: Removed SaaS-specific features (billing, quota, multi-tenancy)
"""

import logging
import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from core.agent_fleet_service import AgentFleetService
from core.recruitment_intelligence_service import RecruitmentIntelligenceService
from core.llm_service import LLMService
from core.models import DelegationChain, ChainLink

logger = logging.getLogger(__name__)


class TaskAnalysis(BaseModel):
    """Structured output from LLM task analysis."""
    complexity: str = Field(description="Task complexity: low/medium/high")
    required_capabilities: List[str] = Field(description="List of capabilities needed")
    estimated_duration: str = Field(description="Estimated time: minutes/hours/days")
    specialist_count: int = Field(description="Recommended number of specialists", ge=1, le=10)
    reasoning: str = Field(description="Explanation of the analysis")


class FleetAdmiral:
    """
    Fleet Admiral - Dynamic Agent Recruitment Orchestrator (Single-Tenant)

    Wraps AgentFleetService with meta-agent responsibilities for intelligent
    task decomposition and specialist recruitment.

    Architecture:
    - Uses AgentFleetService for fleet initialization and member recruitment
    - Uses RecruitmentIntelligenceService for intelligent team selection
    - Uses LLMService for task analysis
    - Manages blackboard state through AgentFleetService

    This avoids reimplementing fleet orchestration logic by delegating to
    existing services.

    SINGLE-TENANT: Uses user_id instead of tenant_id. No billing/quota checks.
    """

    def __init__(self, db: Session, llm: LLMService):
        """
        Initialize FleetAdmiral with required services.

        Args:
            db: Database session
            llm: LLM service for task analysis
        """
        self.db = db
        self.llm = llm

        # Initialize fleet service for delegation chain management
        self.fleet_service = AgentFleetService(db)

        # Initialize recruitment intelligence for specialist matching
        self.recruitment_intelligence: Optional[RecruitmentIntelligenceService] = None

    def _initialize_recruitment_intelligence(self):
        """
        Lazy initialize RecruitmentIntelligenceService with all dependencies.

        This is done lazily to avoid circular dependencies and expensive initialization
        until actually needed.

        SINGLE-TENANT: No BudgetEnforcementService dependency (removed from upstream)
        """
        if self.recruitment_intelligence is not None:
            return

        from core.specialist_matcher import SpecialistMatcher
        from core.recruitment_analytics_service import RecruitmentAnalyticsService
        from analytics.fleet_optimization_service import FleetOptimizationService
        from core.agent_governance_service import AgentGovernanceService

        self.recruitment_intelligence = RecruitmentIntelligenceService(
            db=self.db,
            llm=self.llm,
            specialist_matcher=SpecialistMatcher(self.db),
            analytics=RecruitmentAnalyticsService(self.db),
            fleet_service=self.fleet_service,
            optimizer=FleetOptimizationService(self.db),
            governance=AgentGovernanceService(self.db)
            # budget parameter removed - no billing/quota in upstream
        )

        logger.info("[FleetAdmiral] RecruitmentIntelligenceService initialized (single-tenant mode)")

    async def analyze_task_requirements(
        self,
        task: str,
        user_id: str  # Changed from tenant_id
    ) -> Dict[str, Any]:
        """
        Analyze task to determine complexity and required capabilities.

        Args:
            task: Task description
            user_id: User identifier (single-tenant deployment)

        Returns:
            Dict with:
                - complexity: low/medium/high
                - required_capabilities: List of capabilities
                - estimated_duration: Time estimate
                - specialist_count: Recommended number of specialists
                - reasoning: Analysis explanation
        """
        prompt = f"""Analyze this task and provide a structured assessment:

TASK: {task}

Assess:
1. Complexity level (low/medium/high)
2. Required capabilities (e.g., data_analysis, web_scraping, integration)
3. Estimated duration (e.g., "5 minutes", "1 hour", "2-3 hours")
4. How many specialist agents are needed (1-10)
5. Reasoning for your assessment

Return JSON matching the TaskAnalysis schema."""

        try:
            analysis: TaskAnalysis = await self.llm.generate_structured_response(
                prompt=prompt,
                system_instruction="You are an expert at task decomposition and multi-agent orchestration.",
                response_model=TaskAnalysis,
                temperature=0.3,
                user_id=user_id  # Changed from tenant_id
            )

            return {
                "complexity": analysis.complexity,
                "required_capabilities": analysis.required_capabilities,
                "estimated_duration": analysis.estimated_duration,
                "specialist_count": analysis.specialist_count,
                "reasoning": analysis.reasoning
            }

        except Exception as e:
            logger.error(f"[FleetAdmiral] Task analysis failed: {e}")
            # Fallback to basic assessment
            return {
                "complexity": "medium",
                "required_capabilities": ["general"],
                "estimated_duration": "30 minutes",
                "specialist_count": 2,
                "reasoning": f"LLM analysis failed, using default assessment. Error: {e}"
            }

    async def recruit_and_execute(
        self,
        task: str,
        user_id: str,  # Changed from tenant_id
        root_agent_id: str = "atom_main"
    ) -> Dict[str, Any]:
        """
        Analyze task, recruit specialist agents, and initialize fleet execution.

        This is the main entry point for meta-agent routing. It:
        1. Analyzes task requirements
        2. Initializes a delegation chain (fleet)
        3. Uses RecruitmentIntelligenceService to select optimal specialists
        4. Recruits specialists to the fleet
        5. Updates blackboard with task analysis

        Args:
            task: Task description
            user_id: User identifier (single-tenant deployment)
            root_agent_id: Root agent ID (default: atom_main)

        Returns:
            Dict with:
                - chain_id: Delegation chain ID
                - specialists_count: Number of recruited specialists
                - fleet_status: Fleet status
                - task_analysis: Task analysis results
                - recruitment_roster: List of recruited specialists
        """
        logger.info(f"[FleetAdmiral] Recruiting fleet for task: {task[:50]}...")

        # Step 1: Analyze task requirements
        task_analysis = await self.analyze_task_requirements(task, user_id)
        logger.info(f"[FleetAdmiral] Task analysis: {task_analysis}")

        # Step 2: Initialize delegation chain (fleet)
        chain = self.fleet_service.initialize_fleet(
            user_id=user_id,  # Changed from tenant_id
            root_agent_id=root_agent_id,
            root_task=task,
            initial_metadata={
                "task_analysis": task_analysis,
                "recruitment_phase": "in_progress"
            }
        )

        logger.info(f"[FleetAdmiral] Initialized fleet chain: {chain.id}")

        # Step 3: Recruit specialists using RecruitmentIntelligenceService
        self._initialize_recruitment_intelligence()

        recruitment_result = await self.recruitment_intelligence.orchestrate_recruitment(
            goal=task,
            user_id=user_id,  # Changed from tenant_id
            context={"chain_id": chain.id},
            max_specialists=task_analysis.get("specialist_count", 5),
            chain_id=chain.id
        )

        if not recruitment_result.get("success"):
            logger.error(f"[FleetAdmiral] Recruitment failed: {recruitment_result.get('error')}")
            # Update chain status to failed
            self.fleet_service.complete_chain(chain.id, "failed")
            return {
                "chain_id": chain.id,
                "specialists_count": 0,
                "fleet_status": "failed",
                "error": recruitment_result.get("error"),
                "task_analysis": task_analysis
            }

        # Step 4: Recruit specialists to fleet
        recruitment_roster = recruitment_result.get("recruitment_roster", [])
        specialists_recruited = []

        for specialist in recruitment_roster:
            link = self.fleet_service.recruit_member(
                chain_id=chain.id,
                parent_agent_id=root_agent_id,
                child_agent_id=specialist["agent_id"],
                task_description=f"{specialist['domain']}: {specialist.get('capability_score', 'N/A')}",
                context_json={
                    "domain": specialist["domain"],
                    "optimization": specialist.get("optimization")
                },
                link_order=len(specialists_recruited)
            )
            specialists_recruited.append(link)
            logger.info(f"[FleetAdmiral] Recruited {specialist['agent_name']} for {specialist['domain']}")

        # Step 5: Update blackboard with recruitment results
        self.fleet_service.update_blackboard(
            chain_id=chain.id,
            updates={
                "task_analysis": task_analysis,
                "recruitment_phase": "complete",
                "specialists_recruited": [
                    {
                        "agent_id": s["agent_id"],
                        "agent_name": s["agent_name"],
                        "domain": s["domain"]
                    }
                    for s in recruitment_roster
                ],
                "recruitment_completed_at": datetime.now(timezone.utc).isoformat()
            }
        )

        logger.info(
            f"[FleetAdmiral] Fleet recruitment complete: "
            f"{len(specialists_recruited)} specialists, chain {chain.id}"
        )

        return {
            "chain_id": chain.id,
            "specialists_count": len(specialists_recruited),
            "fleet_status": chain.status,
            "task_analysis": task_analysis,
            "recruitment_roster": recruitment_roster,
            "specialists": [
                {
                    "agent_id": s["agent_id"],
                    "agent_name": s["agent_name"],
                    "domain": s["domain"]
                }
                for s in recruitment_roster
            ]
        }
