import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from analytics.fleet_analytics_service import FleetAnalyticsService
from core.llm.byok_handler import QueryComplexity

logger = logging.getLogger(__name__)

class FleetOptimizationService:
    """
    Upstream Optimization engine for Fleet Admiralty.
    Suggests agent configurations and model tiers based on historical telemetry.
    """

    def __init__(self, db: Session):
        self.db = db
        self.analytics = FleetAnalyticsService(db)

    def get_optimization_parameters(
        self, 
        tenant_id: str, 
        domain: str, 
        task_description: str,
        complexity_override: Optional[QueryComplexity] = None
    ) -> Dict[str, Any]:
        """
        Calculates optimized parameters for a fleet recruitment sub-task.
        
        Logic:
        - HIGH success rate (>95%) + LOW complexity: Downgrade to faster/cheaper model.
        - LOW success rate (<85%) or LOW HITL approval: Upgrade to higher reasoning model.
        - High latency: Suggest lower max_steps or parallelization.
        """
        logger.info(f"Optimizing recruitment for domain: {domain} (Tenant: {tenant_id})")
        
        # 1. Fetch domain history
        history = self.analytics.get_domain_performance_stats(tenant_id, domain)
        
        # Default parameters
        params = {
            "model": "auto",
            "max_steps": 8,
            "mentorship_mode": False,
            "optimized_context": {},
            "optimization_reason": "Default starting point (Standard Profiling)"
        }

        # 2. Heuristic-based Optimization
        success_rate = history.get("success_rate", 0.0)
        hitl_rate = history.get("hitl_approval_rate", 1.0)
        total_interactions = history.get("total_interactions", 0)

        # We need a minimum sample size to be confident (Combined Links + HITL)
        hitl_total = history.get("total_hitl_requests", 0)
        if (total_interactions + hitl_total) < 3:
            params["optimization_reason"] = "Insufficient data for domain optimization. Using defaults."
            return params

        # Optimization Rule 1: Reasoning Upgrade (Fail-Fast protection)
        if success_rate < 0.85 or hitl_rate < 0.8:
            params["model"] = "quality" # Force high-reasoning model
            params["max_steps"] = 10
            params["mentorship_mode"] = True
            params["optimization_reason"] = f"Low historical performance ({success_rate:.0%}) detected. Upgrading to high-reasoning tier."
            return params

        # Optimization Rule 2: Cost-Down (Efficiency gain)
        if success_rate >= 0.96 and hitl_rate >= 0.95:
            if len(task_description) < 150:
                params["model"] = "fast" # Downgrade to cheap model
                params["max_steps"] = 5
                params["optimization_reason"] = f"Efficiency gain: Excellent historical success ({success_rate:.0%}) with low task complexity. Downgrading for cost savings."
                return params

        params["optimization_reason"] = f"Standard parity maintained. Domain performance stable ({success_rate:.0%})."
        return params

    def analyze_bottlenecks(self, chain_id: str) -> List[Dict[str, Any]]:
        """
        Post-hoc analysis to identify which links in a chain were inefficient.
        
        Identifies:
        - Outlier latency (>150% domain average)
        - Execution failures
        - Frequent or rejected HITL interventions
        """
        from core.models import ChainLink, HITLAction, HITLActionStatus, DelegationChain
        
        # 1. Fetch all links in the chain
        links = self.db.query(ChainLink).filter(ChainLink.chain_id == chain_id).order_by(ChainLink.link_order).all()
        if not links:
            return []
            
        # 2. Get chain metadata for tenant scoping
        chain = self.db.query(DelegationChain).filter(DelegationChain.id == chain_id).first()
        tenant_id = chain.tenant_id if chain else None
        
        bottlenecks = []
        for link in links:
            # Extract domain from context
            domain = link.context_json.get('domain', 'general') if link.context_json else 'general'
            
            # Fetch domain baseline for comparison
            baseline = self.analytics.get_domain_performance_stats(tenant_id, domain)
            avg_ms = baseline.get('avg_duration_ms', 0)
            
            # Diagnostic Record
            diag = {
                "link_id": link.id,
                "domain": domain,
                "agent_id": link.child_agent_id,
                "status": link.status,
                "duration_ms": link.duration_ms or 0,
                "avg_domain_duration_ms": round(avg_ms, 2),
                "issues": [],
                "severity": "info"
            }
            
            # Criterion 1: Failure Detection
            if link.status == 'failed':
                diag["issues"].append("Execution failure detected in this link.")
                diag["severity"] = "critical"
            
            # Criterion 2: Latency Analysis
            if avg_ms > 0 and diag["duration_ms"] > (avg_ms * 2.5):
                diag["issues"].append(f"Critical latency outlier: Execution took {diag['duration_ms']}ms, which is >250% of the domain average ({avg_ms:.0f}ms).")
                diag["severity"] = "critical"
            elif avg_ms > 0 and diag["duration_ms"] > (avg_ms * 1.5):
                diag["issues"].append(f"Performance warning: Execution latency is {diag['duration_ms']}ms (>150% of domain average).")
                if diag["severity"] == "info":
                    diag["severity"] = "warning"

            # Criterion 3: HITL Friction Analysis
            # Find HITL actions for this agent in this chain
            hitl = self.db.query(HITLAction).filter(
                HITLAction.chain_id == chain_id,
                HITLAction.agent_id == link.child_agent_id
            ).first()
            
            if hitl:
                if hitl.status == HITLActionStatus.REJECTED.value:
                    diag["issues"].append("Human-in-the-loop: The agent's proposed action was REJECTED by user.")
                    diag["severity"] = "critical"
                else:
                    diag["issues"].append(f"Human-in-the-loop: Flow was paused for manual {hitl.status or 'pending'} intervention.")
                    if diag["severity"] == "info":
                        diag["severity"] = "warning"

            if diag["issues"]:
                bottlenecks.append(diag)
                
        return bottlenecks

    def get_fleet_health_summary(self, tenant_id: str) -> Dict[str, Any]:
        """
        Aggregates fleet-wide metrics for the real-time analytics dashboard.
        """
        from core.models import DelegationChain, ChainLink, FleetHealingEvent
        from sqlalchemy import func

        # 1. Chain Distribution
        status_counts = self.db.query(
            DelegationChain.status, func.count(DelegationChain.id)
        ).filter(DelegationChain.tenant_id == tenant_id).group_by(DelegationChain.status).all()
        
        chains_summary = {status: count for status, count in status_counts}
        total_chains = sum(chains_summary.values())

        # 2. Link Performance (Success Rate)
        link_stats = self.db.query(
            ChainLink.status, func.count(ChainLink.id)
        ).join(DelegationChain).filter(DelegationChain.tenant_id == tenant_id).group_by(ChainLink.status).all()
        
        links_summary = {status: count for status, count in link_stats}
        total_links = sum(links_summary.values())
        success_rate = (links_summary.get('completed', 0) / total_links) if total_links > 0 else 1.0

        # 3. Healing Insights
        healing_events = self.db.query(FleetHealingEvent).filter(FleetHealingEvent.tenant_id == tenant_id).all()
        total_heals = len(healing_events)
        
        heals_in_progress = len([h for h in healing_events if h.status == 'in_progress'])
        heals_succeeded = len([h for h in healing_events if h.status == 'succeeded'])
        heals_failed = len([h for h in healing_events if h.status == 'failed'])
        
        healing_success_rate = (heals_succeeded / (heals_succeeded + heals_failed)) if (heals_succeeded + heals_failed) > 0 else 1.0

        # 4. Bottleneck Frequency (Heuristic: Critical/Warning ratio)
        recent_chains = self.db.query(DelegationChain.id).filter(
            DelegationChain.tenant_id == tenant_id
        ).order_by(DelegationChain.created_at.desc()).limit(50).all()
        
        total_bottlenecks = 0
        critical_bottlenecks = 0
        for (c_id,) in recent_chains:
            b_list = self.analyze_bottlenecks(c_id)
            total_bottlenecks += len(b_list)
            critical_bottlenecks += len([b for b in b_list if b['severity'] == 'critical'])

        return {
            "chains": {
                "total": total_chains,
                "active": chains_summary.get('active', 0),
                "completed": chains_summary.get('completed', 0),
                "failed": chains_summary.get('failed', 0)
            },
            "performance": {
                "link_success_rate": round(success_rate, 4),
                "total_links": total_links
            },
            "healing": {
                "total_events": total_heals,
                "in_progress": heals_in_progress,
                "succeeded": heals_succeeded,
                "failed": heals_failed,
                "healing_success_rate": round(healing_success_rate, 4)
            },
            "diagnostics": {
                "recent_bottlenecks_total": total_bottlenecks,
                "recent_critical_count": critical_bottlenecks,
                "avg_bottlenecks_per_chain": round(total_bottlenecks / len(recent_chains), 2) if recent_chains else 0
            }
        }
