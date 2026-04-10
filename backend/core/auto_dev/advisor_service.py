"""
Auto-Dev Advisor Service

Provides AI-generated guidance and recommendations based on mutation
quality, fitness trends, and evolutionary progress. Architecturally
aligned with the SaaS AlphaEvolveAdvisor.

Uses the upstream LLMService for generation (instead of SaaS get_ai_service).
"""

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from core.auto_dev.models import ToolMutation, WorkflowVariant

logger = logging.getLogger(__name__)


class AdvisorService:
    """
    AI Advisor for the Auto-Dev evolutionary framework.

    Analyzes mutation/fitness data and generates human-readable guidance:
    - Why certain mutations are succeeding
    - When to synthesize findings vs. continue evolving
    - Risk detection (high failure rates, fitness plateaus)
    """

    def __init__(self, db: Session, llm_service: Any | None = None):
        self.db = db
        self.llm = llm_service

    async def generate_guidance(
        self,
        tenant_id: str,
        agent_id: str | None = None,
        llm_service: Any | None = None,
    ) -> dict[str, Any]:
        """
        Analyze current mutations and fitness data to provide advice.

        Args:
            tenant_id: Tenant to analyze
            agent_id: Optional specific agent (otherwise tenant-wide)
            llm_service: Override LLM service (useful for SaaS model routing)

        Returns:
            {
                "status": "success",
                "message": str,
                "data_summary": dict,
                "readiness_score": int (0-100),
            }
        """
        llm = llm_service or self.llm or self._get_llm_service()

        # 1. Fetch recent mutations
        mutations = (
            self.db.query(ToolMutation)
            .filter(ToolMutation.tenant_id == tenant_id)
            .order_by(ToolMutation.created_at.desc())
            .limit(10)
            .all()
        )

        # 2. Fetch variants for fitness trends
        variants = (
            self.db.query(WorkflowVariant)
            .filter(WorkflowVariant.tenant_id == tenant_id)
            .order_by(WorkflowVariant.created_at.desc())
            .limit(10)
            .all()
        )

        if not mutations and not variants:
            return {
                "status": "success",
                "message": (
                    "No evolutionary data found yet. "
                    "Start by triggering a tool mutation to see Auto-Dev in action."
                ),
                "readiness_score": 0,
            }

        # 3. Prepare data summary
        data_summary = {
            "num_mutations": len(mutations),
            "passed_mutations": len(
                [m for m in mutations if m.sandbox_status == "passed"]
            ),
            "failed_mutations": len(
                [m for m in mutations if m.sandbox_status == "failed"]
            ),
            "top_fitness_score": (
                max([v.fitness_score or 0 for v in variants]) if variants else 0
            ),
            "avg_fitness_score": (
                sum([v.fitness_score or 0 for v in variants]) / len(variants)
                if variants
                else 0
            ),
        }

        # 4. Generate AI guidance if LLM is available
        if llm:
            message = await self._generate_ai_guidance(llm, tenant_id, data_summary)
        else:
            message = self._generate_heuristic_guidance(data_summary)

        return {
            "status": "success",
            "message": message,
            "data_summary": data_summary,
            "readiness_score": min(100, int(data_summary["passed_mutations"] * 20)),
        }

    async def _generate_ai_guidance(
        self, llm: Any, tenant_id: str, data_summary: dict
    ) -> str:
        """Generate AI-powered guidance using LLM."""
        system_prompt = (
            "You are the Auto-Dev Research Advisor. "
            "Analyze the provided mutation/fitness data and give concise, "
            "expert guidance. Tell the user:\n"
            "- Why certain mutations are winning (latency, success rate)\n"
            "- Whether to synthesize findings now or continue researching\n"
            "- Any risks detected (high failure rate, fitness plateau)\n"
            "Be professional, technical, and helpful."
        )

        user_prompt = (
            f"Current Evolution Data for Tenant {tenant_id}:\n"
            f"{json.dumps(data_summary, indent=2)}\n\n"
            f"Provide your guidance:"
        )

        try:
            response = await llm.generate_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.5,
            )
            return response.get(
                "content",
                "Evolution is progressing. Continue monitoring signals.",
            )
        except Exception as e:
            logger.error(f"Failed to generate AI guidance: {e}")
            return self._generate_heuristic_guidance(data_summary)

    def _generate_heuristic_guidance(self, data_summary: dict) -> str:
        """Fallback guidance when LLM is unavailable."""
        total = data_summary["num_mutations"]
        passed = data_summary["passed_mutations"]
        failed = data_summary["failed_mutations"]
        avg_fitness = data_summary["avg_fitness_score"]

        if total == 0:
            return "No mutations generated yet. Trigger your first evolution cycle."

        success_rate = passed / total if total > 0 else 0

        if success_rate >= 0.8 and avg_fitness >= 0.6:
            return (
                f"Strong results: {passed}/{total} mutations passed "
                f"(avg fitness {avg_fitness:.2f}). Consider synthesizing findings."
            )
        elif success_rate >= 0.5:
            return (
                f"Moderate progress: {passed}/{total} mutations passed. "
                f"Continue evolutionary cycles for stronger signal."
            )
        else:
            return (
                f"High failure rate: {failed}/{total} mutations failed. "
                f"Review mutation prompts and base code quality."
            )

    def _get_llm_service(self) -> Any | None:
        """Attempt to get the upstream LLM service."""
        try:
            from core.llm_service import get_llm_service

            return get_llm_service()
        except Exception:
            return None
