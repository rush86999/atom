"""
Self Evolution Service — upgraded to delegate to GEA group evolution.

Original: single-agent analysis via feedback + HITL history heuristics.
Upgraded: now wraps AgentEvolutionLoop so callers can trigger a full
Group-Evolving Agents cycle (multi-agent, domain-aware, benchmarked)
while keeping the legacy single-agent API intact.

Usage (legacy):
    from core.self_evolution_service import self_evolution_service
    insight = await self_evolution_service.analyze_agent_performance(agent_id)
    await self_evolution_service.apply_auto_tune(agent_id, insight)

Usage (GEA group evolution):
    result = await self_evolution_service.run_group_evolution(
        tenant_id="t-uuid", group_size=5
    )
    # result is an EvolutionCycleResult from AgentEvolutionLoop
"""

import logging
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from core.database import SessionLocal
from core.models import AgentRegistry, AgentFeedback, HITLAction, HITLActionStatus
from core.governance_engine import contact_governance

logger = logging.getLogger(__name__)


class SelfEvolutionService:
    """
    Service that enables agents to 'learn' from their history.

    Synthesizes feedback and execution traces to optimize agent performance.
    Delegates to AgentEvolutionLoop (GEA) for group-level collective intelligence.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # Legacy: Single-agent self-evolution (unchanged API)
    # ─────────────────────────────────────────────────────────────────────────

    async def analyze_agent_performance(self, agent_id: str) -> Dict[str, Any]:
        """
        Analyzes recent history for an agent and identifies improvement areas.
        """
        db = SessionLocal()
        try:
            agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
            if not agent:
                return {"error": "Agent not found"}

            # 1. Fetch recent user feedback
            feedbacks = db.query(AgentFeedback).filter(
                AgentFeedback.agent_id == agent_id,
                AgentFeedback.created_at >= datetime.utcnow() - timedelta(days=7)
            ).all()

            # 2. Fetch recent HITL actions
            hitls = db.query(HITLAction).filter(
                HITLAction.agent_id == agent_id,
                HITLAction.created_at >= datetime.utcnow() - timedelta(days=7)
            ).all()

            approval_rate = 0.0
            if hitls:
                approved = [h for h in hitls if h.status == HITLActionStatus.APPROVED.value]
                approval_rate = len(approved) / len(hitls)

            # 3. Simple heuristic analysis
            bottleneck = "none"
            recommendation = "Maintain current autonomy."

            if approval_rate < 0.5 and len(hitls) > 5:
                bottleneck = "low_approval_rate"
                recommendation = "Suggest refining system prompt to align with user expectations."
            elif len(feedbacks) > 3:
                bottleneck = "frequent_correction"
                recommendation = "Incorporate recent user corrections into specialized RAG context."

            return {
                "agent_id": agent_id,
                "confidence_score": agent.confidence_score,
                "approval_rate": approval_rate,
                "recent_feedback_count": len(feedbacks),
                "detected_bottleneck": bottleneck,
                "recommendation": recommendation,
                "last_analysis": datetime.utcnow().isoformat()
            }
        finally:
            db.close()

    async def apply_auto_tune(self, agent_id: str, insight: str):
        """
        Updates agent configuration based on evolution insights.
        """
        db = SessionLocal()
        try:
            agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
            if agent:
                config = agent.configuration or {}
                evolution_history = config.get("evolution_history", [])
                evolution_history.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "insight": insight
                })
                config["evolution_history"] = evolution_history

                if agent.confidence_score > 0.9:
                    config["elevated_privileges"] = True

                agent.configuration = config
                db.commit()
                logger.info(f"Auto-tuned agent {agent_id} with insight: {insight}")
        finally:
            db.close()

    # ─────────────────────────────────────────────────────────────────────────
    # GEA: Group evolution delegation
    # ─────────────────────────────────────────────────────────────────────────

    async def run_group_evolution(
        self,
        tenant_id: str,
        group_size: int = 5,
        target_agent_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Trigger a full GEA group evolution cycle for a tenant.

        Delegates to AgentEvolutionLoop which runs:
          Stage 1: Performance-Novelty parent group selection
          Stage 2: Shared experience pool gathering (domain-aware)
          Stage 3: Reflection Module → evolution directives
          Stage 4: Apply directives to cloned config (sandboxed + guardrail check)
          Stage 5: Benchmark evaluation
          Stage 6: Promote winner / archive trace

        Args:
            tenant_id: Tenant namespace to evolve
            group_size: Number of parent agents to select (default 5)
            target_agent_id: If set, only evolve this specific agent
            category: Domain category override (auto-detected from agent otherwise)

        Returns:
            Serialized EvolutionCycleResult dict with cycle_id, directives,
            benchmark_passed, benchmark_score, evolved_agent_id, trace_id.
        """
        with SessionLocal() as db:
            from core.agent_evolution_loop import AgentEvolutionLoop
            loop = AgentEvolutionLoop(db)
            result = await loop.run_evolution_cycle(
                tenant_id=tenant_id,
                group_size=group_size,
                target_agent_id=target_agent_id,
                category=category,
            )
            logger.info(
                "GEA group evolution complete: tenant=%s passed=%s score=%.3f",
                tenant_id, result.benchmark_passed, result.benchmark_score,
            )
            return result.to_dict()

    async def analyze_group_readiness(
        self,
        tenant_id: str,
        group_size: int = 5,
    ) -> Dict[str, Any]:
        """
        Preview the parent group that would be selected for the next GEA cycle
        WITHOUT running evolution (dry-run of Stage 1).

        Useful for dashboards that want to show "which agents are up for evolution".

        Returns:
            {
              "candidate_count": int,
              "parent_group": [{"agent_id", "name", "confidence_score", "category"}],
              "avg_performance": float,
              "evolution_recommended": bool  — True if avg perf < 0.75 (room to grow)
            }
        """
        with SessionLocal() as db:
            from core.agent_evolution_loop import AgentEvolutionLoop
            loop = AgentEvolutionLoop(db)
            group = loop.select_parent_group(tenant_id=tenant_id, n=group_size)

            if not group:
                return {
                    "candidate_count": 0,
                    "parent_group": [],
                    "avg_performance": 0.0,
                    "evolution_recommended": False,
                }

            avg_perf = sum(a.confidence_score for a in group) / len(group)
            return {
                "candidate_count": len(group),
                "parent_group": [
                    {
                        "agent_id": a.id,
                        "name": a.name,
                        "confidence_score": a.confidence_score,
                        "category": a.category,
                        "status": a.status,
                    }
                    for a in group
                ],
                "avg_performance": round(avg_perf, 4),
                "evolution_recommended": avg_perf < 0.75,
            }


# Singleton
self_evolution_service = SelfEvolutionService()
