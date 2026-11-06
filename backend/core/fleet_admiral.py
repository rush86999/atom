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

Ported from atom-saas
Changes: Removed SaaS-specific features (billing, quota, multi-tenancy)
"""

import hashlib
import logging
import uuid
import json
from datetime import datetime, timezone
from typing import Callable, Dict, Any, Optional, List
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from core.agent_fleet_service import AgentFleetService
from core.recruitment_intelligence_service import RecruitmentIntelligenceService
from core.llm_service import LLMService
from core.models import AgentRegistry, DelegationChain, ChainLink

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
        root_agent_id: str = "atom_main",
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
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
            tenant_id=tenant_id or user_id,
            root_agent_id=root_agent_id,
            root_task=task,
            initial_metadata={
                "task_analysis": task_analysis,
                "recruitment_phase": "in_progress",
                **({"workspace_id": workspace_id} if workspace_id else {}),
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


    @staticmethod
    def _specialist_task_digest(
        task: str, chain_id: str, roster: List[Dict[str, Any]],
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        roster_material = []
        for item in roster:
            roster_material.append({
                "agent_id": str(item.get("agent_id") or ""),
                "agent_name": str(item.get("agent_name") or ""),
                "domain": str(item.get("domain") or ""),
                "capability_score": item.get("capability_score"),
            })
        roster_material.sort(key=lambda item: (
            item["agent_id"], item["domain"], item["agent_name"]))
        basis = {}
        for key in (
            "source_basis", "teaching_basis", "authority_basis",
            "objective", "required_outcome",
        ):
            if context and context.get(key) is not None:
                basis[key] = context[key]
        payload = {
            "task": str(task or ""),
            "chain_id": str(chain_id or ""),
            "tenant_id": str(tenant_id or ""),
            "workspace_id": str(workspace_id or ""),
            "roster": roster_material,
            "basis": basis,
        }
        return hashlib.sha1(json.dumps(
            payload, sort_keys=True, separators=(",", ":"), default=str,
        ).encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _specialist_result_succeeded(raw: Dict[str, Any]) -> bool:
        status = str(raw.get("status") or "").strip().lower()
        failure_statuses = {
            "failed", "timeout", "budget_exceeded", "cancelled", "error",
            "killed_sandbox",
        }
        success_statuses = {
            "success", "objective_satisfied", "completed",
        }
        explicit = raw.get("success")
        if explicit is False:
            return False
        if status in failure_statuses:
            return False
        if explicit is True:
            return True
        return status in success_statuses

    async def execute_recruited_specialists(
        self,
        *,
        task: str,
        user_id: str,
        chain_id: str,
        roster: List[Dict[str, Any]],
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """Execute the recruited specialists and return their cited work.

        Reuses the existing GenericAgent/AgentRegistry/BYOK path. The response
        is deterministic synthesis of the specialists' actual outputs; it is
        not a second recruitment list. Missing/foreign specialists are refused
        before dispatch, failed specialists are preserved, cancellation stops
        before the next specialist, and a completed execution is cached on the
        delegation chain so duplicate continuation does not re-run work.
        """
        from core.generic_agent import GenericAgent

        context = context or {}
        roster = list(roster or [])
        chain = (
            self.db.query(DelegationChain)
            .filter(DelegationChain.id == str(chain_id))
            .first()
        )
        if chain is None:
            return {
                "success": False,
                "status": "no_suitable_specialists",
                "error": "delegation_chain_not_found",
                "final_output": (
                    "No recruited fleet was available to execute this task."),
                "specialist_results": [],
                "specialists_count": len(roster),
                "executed_count": 0,
                "cancelled": False,
                "chain_id": str(chain_id or ""),
            }

        def _cancelled() -> bool:
            if cancel_check is not None:
                try:
                    if cancel_check():
                        return True
                except Exception:
                    return True
            return bool(
                context.get("cancelled") or context.get("cancel_requested"))

        metadata = dict(chain.metadata_json or {})
        chain_tenant = str(chain.tenant_id or "")
        if tenant_id and chain_tenant and chain_tenant != str(tenant_id):
            return {
                "success": False,
                "status": "no_suitable_specialists",
                "error": "delegation_chain_scope_mismatch",
                "final_output": (
                    "The recruited fleet is outside the caller's scope."),
                "specialist_results": [],
                "specialists_count": len(roster),
                "executed_count": 0,
                "cancelled": False,
                "chain_id": str(chain_id or ""),
            }
        chain_workspace = metadata.get("workspace_id")
        if (
            workspace_id and chain_workspace
            and str(chain_workspace) != str(workspace_id)
        ):
            return {
                "success": False,
                "status": "no_suitable_specialists",
                "error": "delegation_chain_scope_mismatch",
                "final_output": (
                    "The recruited fleet is outside the caller's scope."),
                "specialist_results": [],
                "specialists_count": len(roster),
                "executed_count": 0,
                "cancelled": False,
                "chain_id": str(chain_id or ""),
            }
        chain_status = str(chain.status or "").strip().lower()
        if chain_status in ("cancelled", "failed"):
            return {
                "success": False,
                "status": "cancelled" if chain_status == "cancelled" else "failed",
                "error": "delegation_chain_terminal",
                "final_output": (
                    "The recruited fleet is already cancelled."
                    if chain_status == "cancelled"
                    else "The recruited fleet has already failed."),
                "specialist_results": [],
                "specialists_count": len(roster),
                "executed_count": 0,
                "cancelled": chain_status == "cancelled",
                "chain_id": str(chain_id or ""),
            }
        if _cancelled():
            return {
                "success": False,
                "status": "cancelled",
                "error": "fleet_specialist_execution_cancelled",
                "final_output": (
                    "Specialist work was cancelled before completion."),
                "specialist_results": [],
                "specialists_count": len(roster),
                "executed_count": 0,
                "cancelled": True,
                "chain_id": str(chain_id or ""),
            }

        digest = self._specialist_task_digest(
            task, chain_id, roster, tenant_id, workspace_id, context)
        cached = metadata.get("specialist_execution")
        if (
            isinstance(cached, dict)
            and cached.get("task_digest") == digest
            and cached.get("status") == "completed"
            and isinstance(cached.get("result"), dict)
        ):
            cached_result = dict(cached["result"])
            cached_result["cached"] = True
            return cached_result

        results: List[Dict[str, Any]] = []
        successful: List[Dict[str, Any]] = []
        cancelled = False
        for item in roster:
            if _cancelled():
                cancelled = True
                break
            agent_id = str(item.get("agent_id") or "")
            agent_name = str(item.get("agent_name") or agent_id or "Specialist")
            domain = str(item.get("domain") or "general")
            agent = (
                self.db.query(AgentRegistry)
                .filter(AgentRegistry.id == agent_id)
                .first()
                if agent_id else None
            )
            if agent is None:
                results.append({
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "domain": domain,
                    "status": "missing",
                    "output": "",
                    "error": "specialist_not_found",
                })
                continue
            agent_name = str(
                getattr(agent, "name", None)
                or getattr(agent, "display_name", None)
                or agent_id
                or "Specialist"
            )
            if getattr(agent, "enabled", True) is False:
                results.append({
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "domain": domain,
                    "status": "unavailable",
                    "output": "",
                    "error": "specialist_disabled",
                })
                continue
            if tenant_id and agent.tenant_id and str(
                    agent.tenant_id) != str(tenant_id):
                results.append({
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "domain": domain,
                    "status": "scope_mismatch",
                    "output": "",
                    "error": "specialist_tenant_mismatch",
                })
                continue
            if workspace_id and agent.workspace_id and str(
                    agent.workspace_id) != str(workspace_id):
                results.append({
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "domain": domain,
                    "status": "scope_mismatch",
                    "output": "",
                    "error": "specialist_workspace_mismatch",
                })
                continue
            capabilities = [
                str(c).lower() for c in (agent.capabilities or [])
                if str(c).strip()
            ]
            if agent.specialty:
                capabilities.append(str(agent.specialty).lower())
            domain_specific = domain.lower() not in ("", "general")
            if domain_specific and not capabilities:
                results.append({
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "domain": domain,
                    "status": "capability_mismatch",
                    "output": "",
                    "error": "specialist_capability_missing",
                })
                continue
            if domain_specific and not any(
                domain.lower() in cap or cap in domain.lower()
                for cap in capabilities
            ):
                results.append({
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "domain": domain,
                    "status": "capability_mismatch",
                    "output": "",
                    "error": "specialist_capability_mismatch",
                })
                continue

            prompt = (
                f"You are the {domain} specialist in a recruited fleet.\n"
                f"Original task: {task}\n"
                "Return a concise, concrete contribution for your domain. "
                "State assumptions and do not claim work you did not do."
            )
            try:
                runner = GenericAgent(
                    agent_model=agent,
                    workspace_id=agent.workspace_id or workspace_id or "default",
                )
                raw = await runner.execute(
                    task_input=prompt,
                    context={
                        "chain_id": str(chain_id),
                        "user_id": user_id,
                        "tenant_id": tenant_id,
                        "workspace_id": agent.workspace_id or workspace_id,
                        "agent_id": agent_id,
                        "orchestrated_by": "fleet_admiral",
                    },
                )
            except Exception as exc:  # noqa: BLE001 — preserve failure class
                results.append({
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "domain": domain,
                    "status": "failed",
                    "output": "",
                    "error": type(exc).__name__,
                })
                continue

            success = self._specialist_result_succeeded(raw)
            output = str(
                raw.get("final_output")
                or raw.get("output")
                or raw.get("response")
                or ""
            ).strip()
            if success and output:
                item_result = {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "domain": domain,
                    "status": "success",
                    "output": output,
                    "error": None,
                }
                successful.append(item_result)
            else:
                item_result = {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "domain": domain,
                    "status": "failed",
                    "output": output,
                    "error": str(
                        raw.get("error")
                        or raw.get("failure_reason")
                        or "specialist returned no usable output"
                    )[:200],
                }
            results.append(item_result)

        attempted = [
            item for item in results
            if item["status"] in ("success", "failed")]
        if cancelled:
            status = "cancelled"
            success = False
            error = "fleet_specialist_execution_cancelled"
        elif successful:
            status = "specialists_executed"
            success = True
            error = None
        elif attempted:
            status = "specialists_failed"
            success = False
            error = "all_recruited_specialists_failed"
        else:
            status = "no_suitable_specialists"
            success = False
            error = "no_suitable_specialist_available"

        if success:
            lines = [
                f"- {item['agent_name']} ({item['domain']}): {item['output']}"
                for item in successful
            ]
            final_output = (
                "Specialist contributions:\n"
                + "\n".join(lines)
                + "\n\nCombined result:\n"
                + "\n".join(item["output"] for item in successful)
            )
            failed = [
                item for item in results
                if item["status"] in ("failed", "missing", "scope_mismatch",
                                      "capability_mismatch", "unavailable")
            ]
            if failed:
                final_output += "\n\nNot completed:\n" + "\n".join(
                    f"- {item['agent_name']} ({item['domain']}): "
                    f"{item['error'] or item['status']}"
                    for item in failed
                )
        elif cancelled:
            partial = [
                f"- {item['agent_name']} ({item['domain']}): {item['output']}"
                for item in successful
            ]
            final_output = (
                "Specialist work was cancelled before completion."
                + ("\nPartial contributions:\n" + "\n".join(partial)
                   if partial else "")
            )
        elif status == "specialists_failed":
            failures = [
                f"- {item['agent_name']} ({item['domain']}): "
                f"{item['error'] or 'failed'}"
                for item in results if item["status"] == "failed"
            ]
            final_output = (
                "The recruited specialists could not complete this task.\n"
                + "\n".join(failures)
            )
        else:
            final_output = (
                "No suitable specialist was available to execute this task.")

        result_payload = {
            "success": success,
            "status": status,
            "error": error,
            "final_output": final_output,
            "specialist_results": results,
            "specialists_count": len(roster),
            "executed_count": len(attempted),
            "cancelled": cancelled,
            "chain_id": str(chain_id),
            "cached": False,
        }

        metadata["specialist_execution"] = {
            "task_digest": digest,
            "status": (
                "completed" if success
                else "cancelled" if cancelled else "failed"),
            "result": result_payload,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        chain.metadata_json = metadata
        chain.status = (
            "completed" if success
            else "cancelled" if cancelled else "failed")
        chain.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        return result_payload
