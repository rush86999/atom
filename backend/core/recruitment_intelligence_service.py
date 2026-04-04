"""
Recruitment Intelligence Service - LLM-based Domain Analysis (Single-Tenant)

Orchestrates intelligent fleet recruitment using LLM-based domain analysis.
This replaces the hardcoded _recruit_fleet() method with automatic
specialist discovery and matching.

SINGLE-TENANT ARCHITECTURE:
- Uses user_id instead of tenant_id
- No BudgetEnforcementService (no billing/quota in upstream)
- Budget checks are optional and gracefully skipped
- Self-hosted deployment

Ported from atom-saas
Changes: Removed SaaS-specific features (billing, quota, multi-tenancy)
"""

from typing import List, Dict, Optional, Set, Any
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging
import json

from core.llm_service import LLMService
from core.specialist_matcher import SpecialistMatcher
from core.recruitment_analytics_service import RecruitmentAnalyticsService
from core.agent_fleet_service import AgentFleetService
from analytics.fleet_optimization_service import FleetOptimizationService
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, DelegationChain, ChainLink

logger = logging.getLogger(__name__)


# Pydantic models for structured LLM output
class RecruitmentPlan(BaseModel):
    """Structured output from LLM recruitment analysis."""
    goal_analysis: str = Field(description="Summary of what the goal requires")
    required_domains: List[str] = Field(description="List of domains needed")
    domain_rationale: Dict[str, str] = Field(description="Why each domain is needed")
    complexity_estimate: str = Field(description="low/medium/high")
    estimated_parallelizable: bool = Field(description="Can sub-tasks run in parallel")
    suggested_specialist_count: int = Field(description="How many specialists recommended", ge=1, le=10)


class RecruitmentIntelligenceService:
    """
    Orchestrates intelligent fleet recruitment using LLM-based domain analysis.

    This replaces the hardcoded _recruit_fleet() method with automatic
    specialist discovery and matching.

    SINGLE-TENANT ARCHITECTURE:
    - budget parameter is optional (None in upstream)
    - No quota enforcement
    - Uses user_id instead of tenant_id

    Ported from atom-saas
    Changes: Made budget optional, removed quota checks, replaced tenant_id with user_id
    """

    # Available domains (should match DOMAIN_ALIASES in SpecialistMatcher)
    AVAILABLE_DOMAINS = [
        "finance", "sales", "marketing", "operations", "legal",
        "engineering", "hr", "procurement", "communications", "intelligence"
    ]

    def __init__(
        self,
        db: Session,
        llm: LLMService,
        specialist_matcher: SpecialistMatcher,
        analytics: RecruitmentAnalyticsService,
        fleet_service: AgentFleetService,
        optimizer: FleetOptimizationService,
        governance: AgentGovernanceService,
        budget: Optional[Any] = None  # Made optional, no BudgetEnforcementService in upstream
    ):
        self.db = db
        self.llm = llm
        self.matcher = specialist_matcher
        self.analytics = analytics
        self.fleet_service = fleet_service
        self.optimizer = optimizer
        self.governance = governance
        self.budget = budget  # Optional: None in upstream (no billing)

    async def analyze_goal_domains(
        self,
        goal: str,
        user_id: str,  # Changed from tenant_id
        max_specialists: int = 5
    ) -> RecruitmentPlan:
        """
        Use LLM to analyze goal and identify required specialist domains.

        This is the core intelligence - replaces manual sub-task breakdown.

        Args:
            goal: Goal description
            user_id: User identifier (single-tenant deployment)
            max_specialists: Maximum number of specialists to recruit

        Returns:
            RecruitmentPlan with domain analysis
        """
        # Build domain catalog for LLM
        available_domains_info = self._build_domain_catalog(user_id)

        prompt = f"""You are a Fleet Recruitment Strategist. Analyze this goal and recommend which specialist domains are required.

GOAL: {goal}

AVAILABLE SPECIALIST DOMAINS:
{available_domains_info}

RECRUITMENT RULES:
1. Identify which domains are truly required for this goal (be selective)
2. For each domain, explain why it's needed (one sentence)
3. Estimate if sub-tasks can run in parallel
4. Assess overall complexity (low/medium/high)
5. Recommend how many specialists (max {max_specialists})

Return JSON matching the RecruitmentPlan schema."""

        try:
            result = await self.llm.generate_structured_response(
                prompt=prompt,
                system_instruction="You are an expert at multi-agent task decomposition and domain analysis.",
                response_model=RecruitmentPlan,
                temperature=0.3,
                user_id=user_id  # Changed from tenant_id
            )

            # Validate domains are available
            valid_domains = [d for d in result.required_domains if d in self.AVAILABLE_DOMAINS]
            if len(valid_domains) < len(result.required_domains):
                logger.warning(
                    f"[RecruitmentIntelligence] Filtered unavailable domains: "
                    f"{set(result.required_domains) - set(valid_domains)}"
                )

            result.required_domains = valid_domains

            return result

        except Exception as e:
            logger.error(f"[RecruitmentIntelligence] LLM analysis failed: {e}")
            # Fallback to simple keyword matching
            return self._fallback_domain_analysis(goal, user_id, max_specialists)

    def _build_domain_catalog(self, user_id: str) -> str:
        """Build formatted catalog of available domains for LLM."""
        domains = self.matcher.get_all_available_domains(user_id)

        catalog_lines = []
        for domain in domains:
            # Count agents for this domain
            agent_count = self.db.query(AgentRegistry).filter(
                AgentRegistry.user_id == user_id,
                AgentRegistry.category.ilike(f"%{domain}%")
            ).count()

            catalog_lines.append(f"- {domain.title()}: {agent_count} specialist(s) available")

        return "\n".join(catalog_lines)

    def _fallback_domain_analysis(
        self,
        goal: str,
        user_id: str,
        max_specialists: int
    ) -> RecruitmentPlan:
        """
        Fallback domain analysis using keyword matching when LLM fails.

        This ensures recruitment always works even if LLM is down.
        """
        goal_lower = goal.lower()

        # Simple keyword matching
        matched_domains = []
        domain_rationale = {}

        for domain in self.AVAILABLE_DOMAINS:
            # Check domain name and aliases
            keywords = [domain] + self.matcher.DOMAIN_ALIASES.get(domain, [])

            for keyword in keywords:
                if keyword in goal_lower:
                    matched_domains.append(domain)
                    domain_rationale[domain] = f"Goal mentions '{keyword}'"
                    break

        # Limit to max_specialists
        if len(matched_domains) > max_specialists:
            # Sort by keyword match strength (simple heuristic)
            matched_domains = matched_domains[:max_specialists]

        return RecruitmentPlan(
            goal_analysis=f"Keyword-based analysis (LLM fallback)",
            required_domains=matched_domains,
            domain_rationale=domain_rationale,
            complexity_estimate="medium",
            estimated_parallelizable=False,
            suggested_specialist_count=len(matched_domains)
        )

    async def orchestrate_recruitment(
        self,
        goal: str,
        user_id: str,
        context: Dict,
        max_specialists: int = 5,
        chain_id: Optional[str] = None
    ) -> Dict:
        """
        Orchestrate full recruitment flow: analysis -> matching -> governance -> optimization.

        This is the main entry point for intelligent recruitment.

        SINGLE-TENANT: Budget checks are gracefully skipped if budget service not available.

        Args:
            goal: Goal description
            user_id: User identifier (single-tenant deployment)
            context: Additional context for recruitment
            max_specialists: Maximum number of specialists to recruit
            chain_id: Optional delegation chain ID

        Returns:
            Dict with recruitment success/failure status and roster
        """
        try:
            # Step 1: Analyze goal to identify domains
            recruitment_plan = await self.analyze_goal_domains(
                goal=goal,
                user_id=user_id,
                max_specialists=max_specialists
            )

            logger.info(
                f"[RecruitmentIntelligence] Goal: {goal}\n"
                f"Domains: {recruitment_plan.required_domains}\n"
                f"Complexity: {recruitment_plan.complexity_estimate}\n"
                f"Specialists: {recruitment_plan.suggested_specialist_count}"
            )

            # Step 2: Match domains to available specialists
            specialist_matches = self.matcher.find_specialists_for_domains(
                domains=recruitment_plan.required_domains,
                user_id=user_id,
                limit_per_domain=3
            )

            # Validate we have specialists for all required domains
            missing_domains = [
                domain for domain, matches in specialist_matches.items()
                if not matches
            ]

            if missing_domains:
                return {
                    "success": False,
                    "error": f"No specialists available for domains: {missing_domains}",
                    "recruitment_plan": recruitment_plan.dict()
                }

            # Step 3: Governance checks
            # Check if recruitment is allowed (maturity, permissions)
            for domain, matches in specialist_matches.items():
                for specialist in matches:
                    # Check governance
                    can_recruit = await self.governance.can_perform_action(
                        user_id=user_id,
                        agent_id=specialist["agent_id"],
                        action="recruit_specialist"
                    )

                    if not can_recruit:
                        return {
                            "success": False,
                            "error": f"Governance blocked recruitment of {specialist['name']} for {domain}",
                            "recruitment_plan": recruitment_plan.dict()
                        }

            # Step 4: Budget check (upstream: no budget enforcement)
            # SaaS version checks budget here, but upstream skips this step
            estimated_cost = 0.0
            if self.budget:
                estimated_cost = self._estimate_fleet_cost(specialist_matches, user_id)

                if chain_id:
                    chain = self.db.query(DelegationChain).get(chain_id)
                    if chain and chain.budget_limit_usd:
                        current_spend = self.fleet_service.get_fleet_spend(chain_id)

                        if (current_spend + estimated_cost) > chain.budget_limit_usd:
                            return {
                                "success": False,
                                "error": f"Fleet budget exceeded: ${current_spend + estimated_cost:.2f} > ${chain.budget_limit_usd:.2f}",
                                "recruitment_plan": recruitment_plan.dict()
                            }
            else:
                # Upstream: No budget checks, fleet recruitment is unlimited
                logger.debug("[RecruitmentIntelligence] No budget enforcement (single-tenant)")

            # Step 5: Build recruitment roster with optimization
            recruitment_roster = []

            for domain, matches in specialist_matches.items():
                # Take top specialist for this domain
                if matches:
                    top_specialist = matches[0]

                    # Get optimization parameters
                    sub_task = recruitment_plan.domain_rationale.get(
                        domain,
                        f"Handle {domain} aspects of: {goal}"
                    )

                    opt_params = await self.optimizer.get_optimization_parameters(
                        user_id=user_id,
                        domain=domain,
                        task_description=sub_task
                    )

                    recruitment_roster.append({
                        "domain": domain,
                        "agent_id": top_specialist["agent_id"],
                        "agent_name": top_specialist["name"],
                        "capability_score": top_specialist["capability_score"],
                        "optimization": opt_params
                    })

            # Step 6: Record recruitment decision
            if chain_id:
                self.analytics.record_recruitment_decision(
                    chain_id=chain_id,
                    user_id=user_id,
                    goal=goal,
                    identified_domains=recruitment_plan.required_domains,
                    domain_rationale=recruitment_plan.domain_rationale,
                    selected_specialists=recruitment_roster,
                    recruitment_metadata={
                        "complexity": recruitment_plan.complexity_estimate,
                        "parallelizable": recruitment_plan.estimated_parallelizable,
                        "llm_used": True
                    }
                )

            return {
                "success": True,
                "recruitment_plan": recruitment_plan.dict(),
                "recruitment_roster": recruitment_roster,
                "estimated_cost": estimated_cost
            }

        except Exception as e:
            logger.error(f"[RecruitmentIntelligence] Recruitment orchestration failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "recruitment_plan": None
            }

    def _estimate_fleet_cost(
        self,
        specialist_matches: Dict[str, List[Dict]],
        user_id: str
    ) -> float:
        """
        Estimate fleet cost based on specialist optimization parameters.

        Simplified estimation - actual cost will vary.
        NOTE: This method is not used in upstream (no billing), but kept for
        code parity with SaaS version.
        """
        total_cost = 0.0

        for domain, matches in specialist_matches.items():
            if matches:
                # Use optimization parameters if available
                top_specialist = matches[0]
                opt = top_specialist.get("optimization", {})

                # Estimate: $0.10 base + optimization premium
                specialist_cost = 0.10
                if opt.get("optimization_reason"):
                    specialist_cost += 0.05  # Premium for optimization

                total_cost += specialist_cost

        return total_cost
