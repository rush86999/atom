"""
BYOK Competitive Differentiation Endpoints
Enhanced endpoints focused on cost optimization, competitive intelligence, and value proposition
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from dataclasses import asdict

from .byok_endpoints import get_byok_manager, BYOKManager
from .byok_cost_optimizer import BYOKCostOptimizer

router = APIRouter()

# Global cost optimizer instance
_cost_optimizer = None

def get_cost_optimizer(byok_manager: BYOKManager = Depends(get_byok_manager)) -> BYOKCostOptimizer:
    """Get the global cost optimizer instance"""
    global _cost_optimizer
    if _cost_optimizer is None:
        _cost_optimizer = BYOKCostOptimizer(byok_manager)
    return _cost_optimizer

@router.get("/api/v1/byok/competitive-analysis")
async def get_competitive_analysis(
    cost_optimizer: BYOKCostOptimizer = Depends(get_cost_optimizer)
):
    """Get comprehensive competitive analysis of AI providers"""
    try:
        report = cost_optimizer.get_competitive_analysis_report()
        return {
            "success": True,
            "report": report,
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate competitive analysis: {str(e)}"
        )

@router.post("/api/v1/byok/optimize-costs")
async def optimize_costs(
    request: Dict[str, Any],
    cost_optimizer: BYOKCostOptimizer = Depends(get_cost_optimizer)
):
    """Get personalized cost optimization recommendations"""
    user_id = request.get("user_id", "default")
    task_type = request.get("task_type", "general")
    context = request.get("context", {})

    try:
        # Analyze user pattern if not exists
        if user_id not in cost_optimizer.usage_patterns:
            cost_optimizer.analyze_user_usage_pattern(user_id)

        # Get recommendation
        recommendation = cost_optimizer.get_cost_optimization_recommendations(
            user_id, task_type, context
        )

        return {
            "success": True,
            "recommendation": asdict(recommendation),
            "user_pattern": asdict(cost_optimizer.usage_patterns[user_id]),
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate cost optimization: {str(e)}"
        )

@router.post("/api/v1/byok/simulate-savings")
async def simulate_cost_savings(
    request: Dict[str, Any],
    cost_optimizer: BYOKCostOptimizer = Depends(get_cost_optimizer)
):
    """Simulate potential cost savings with optimization strategies"""
    user_id = request.get("user_id", "default")
    months = request.get("months", 6)
    adoption_rate = request.get("adoption_rate", 0.8)

    try:
        simulation = cost_optimizer.simulate_cost_savings(user_id, months, adoption_rate)
        return {
            "success": True,
            "simulation": simulation,
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to simulate savings: {str(e)}"
        )

@router.get("/api/v1/byok/value-proposition")
async def get_value_proposition(
    cost_optimizer: BYOKCostOptimizer = Depends(get_cost_optimizer)
):
    """Get ATOM's unique value proposition compared to competitors"""
    try:
        # Get competitive analysis
        analysis = cost_optimizer.get_competitive_analysis_report()

        # Calculate unique advantages
        total_providers = len(analysis["providers"])
        providers_with_keys = analysis["market_overview"]["providers_with_keys"]
        avg_quality = analysis["market_overview"]["average_quality_score"]
        avg_cost_efficiency = analysis["market_overview"]["average_cost_efficiency"]

        # Value proposition metrics
        byok_advantages = [
            "No markup on AI services - you pay directly to providers",
            "Privacy-first with your own API keys",
            "Multi-provider optimization automatically finds best value",
            "No vendor lock-in - switch providers anytime",
            "Transparent cost tracking and optimization",
            "Access to budget-friendly alternatives like Kimi and DeepSeek"
        ]

        competitive_advantages = []

        # Check for unique provider combinations
        has_budget = any(p["market_position"] == "budget" for p in analysis["providers"].values())
        has_premium = any(p["market_position"] == "premium" for p in analysis["providers"].values())

        if has_budget and has_premium:
            competitive_advantages.append("Unique access to both budget and premium AI providers")

        if avg_cost_efficiency > 75:
            competitive_advantages.append("Superior cost efficiency compared to single-provider platforms")

        if providers_with_keys >= 3:
            competitive_advantages.append("Multi-provider redundancy and optimization")

        # Calculate potential savings
        total_monthly_cost = sum(
            usage.cost_accumulated
            for usage in cost_optimizer.byok_manager.usage_stats.values()
        )

        estimated_savings = total_monthly_cost * 0.15  # Conservative 15% savings estimate

        return {
            "success": True,
            "value_proposition": {
                "byok_advantages": byok_advantages,
                "competitive_advantages": competitive_advantages,
                "metrics": {
                    "active_providers": providers_with_keys,
                    "total_available": total_providers,
                    "average_quality_score": round(avg_quality, 1),
                    "average_cost_efficiency": round(avg_cost_efficiency, 1),
                    "estimated_monthly_savings": round(estimated_savings, 2)
                },
                "market_differentiators": [
                    "Bring Your Own Key - complete cost transparency",
                    "AI-powered provider optimization",
                    "No subscription markup on AI services",
                    "Enterprise-grade security with user-controlled keys",
                    "Instant access to latest AI models without waiting"
                ]
            },
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate value proposition: {str(e)}"
        )

@router.get("/api/v1/byok/provider-intelligence/{provider_id}")
async def get_provider_intelligence(
    provider_id: str,
    cost_optimizer: BYOKCostOptimizer = Depends(get_cost_optimizer)
):
    """Get detailed intelligence about a specific AI provider"""
    try:
        # Get provider status
        status = cost_optimizer.byok_manager.get_provider_status(provider_id)

        # Get competitive insight
        insight = cost_optimizer.competitive_insights.get(provider_id)

        if not insight:
            raise HTTPException(
                status_code=404,
                detail=f"Provider {provider_id} not found"
            )

        # Get usage patterns
        usage = cost_optimizer.byok_manager.usage_stats.get(provider_id)

        # Provider intelligence report
        intelligence = {
            "provider_info": status["provider"],
            "market_intelligence": asdict(insight),
            "usage_stats": asdict(usage) if usage else None,
            "recommendations": [],
            "best_use_cases": [],
            "cost_analysis": {
                "cost_per_token": status["provider"]["cost_per_token"],
                "estimated_cost_per_1k_tokens": status["provider"]["cost_per_token"] * 1000,
                "relative_cost": "Low" if status["provider"]["cost_per_token"] < 0.00001 else "Medium" if status["provider"]["cost_per_token"] < 0.00003 else "High"
            }
        }

        # Generate recommendations based on provider characteristics
        if insight.market_position == "budget":
            intelligence["recommendations"].append("Ideal for high-volume, routine tasks")
            intelligence["best_use_cases"].extend(["Data processing", "Simple queries", "Batch operations"])

        if insight.market_position == "premium":
            intelligence["recommendations"].append("Best for critical, complex tasks")
            intelligence["best_use_cases"].extend(["Complex reasoning", "Code generation", "Strategic analysis"])

        if "reasoning" in insight.best_for_tasks:
            intelligence["recommendations"].append("Excellent for multi-step problem solving")

        if insight.market_trend == "rising":
            intelligence["recommendations"].append("Emerging provider with improving capabilities")

        return {
            "success": True,
            "provider_id": provider_id,
            "intelligence": intelligence,
            "generated_at": datetime.now().isoformat()
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get provider intelligence: {str(e)}"
        )

@router.post("/api/v1/byok/workflow-optimization")
async def optimize_workflow_costs(
    workflow: Dict[str, Any],
    cost_optimizer: BYOKCostOptimizer = Depends(get_cost_optimizer)
):
    """Optimize AI provider selection for an entire workflow"""
    user_id = workflow.get("user_id", "default")
    workflow_steps = workflow.get("steps", [])

    if not workflow_steps:
        raise HTTPException(
            status_code=400,
            detail="Workflow must contain at least one step"
        )

    try:
        optimizations = []
        total_current_cost = 0
        total_optimized_cost = 0

        for step in workflow_steps:
            step_name = step.get("name", f"step_{len(optimizations)}")
            task_type = step.get("task_type", "general")
            estimated_tokens = step.get("estimated_tokens", 1000)
            current_provider = step.get("current_provider", "openai")

            # Get optimization recommendation
            recommendation = cost_optimizer.get_cost_optimization_recommendations(
                user_id, task_type
            )

            # Calculate costs
            current_cost = estimated_tokens * cost_optimizer.byok_manager.providers.get(
                current_provider, cost_optimizer.byok_manager.providers.get("openai")
            ).cost_per_token

            optimized_cost = estimated_tokens * cost_optimizer.byok_manager.providers.get(
                recommendation.recommended_provider
            ).cost_per_token

            total_current_cost += current_cost
            total_optimized_cost += optimized_cost

            optimizations.append({
                "step_name": step_name,
                "task_type": task_type,
                "current_provider": current_provider,
                "recommended_provider": recommendation.recommended_provider,
                "current_cost": current_cost,
                "optimized_cost": optimized_cost,
                "savings": current_cost - optimized_cost,
                "savings_percentage": ((current_cost - optimized_cost) / current_cost) * 100 if current_cost > 0 else 0,
                "confidence": recommendation.confidence,
                "reasoning": recommendation.reasoning
            })

        total_savings = total_current_cost - total_optimized_cost
        total_savings_percentage = (total_savings / total_current_cost) * 100 if total_current_cost > 0 else 0

        return {
            "success": True,
            "workflow_id": workflow.get("id", "unnamed"),
            "optimizations": optimizations,
            "summary": {
                "total_current_cost": total_current_cost,
                "total_optimized_cost": total_optimized_cost,
                "total_savings": total_savings,
                "total_savings_percentage": total_savings_percentage,
                "steps_optimized": len(optimizations),
                "estimated_monthly_savings": total_savings * 30 if workflow.get("frequency") == "daily" else total_savings
            },
            "recommendations": [
                f"Switch to {opt['recommended_provider']} for {opt['step_name']} to save {opt['savings_percentage']:.1f}%"
                for opt in optimizations if opt['savings_percentage'] > 10
            ],
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to optimize workflow: {str(e)}"
        )

@router.get("/api/v1/byok/market-insights")
async def get_market_insights(
    cost_optimizer: BYOKCostOptimizer = Depends(get_cost_optimizer)
):
    """Get market insights and trends in AI providers"""
    try:
        analysis = cost_optimizer.get_competitive_analysis_report()

        # Extract market insights
        insights = {
            "provider_trends": {},
            "market_segments": {},
            "cost_trends": {},
            "quality_trends": {},
            "strategic_recommendations": []
        }

        # Provider trends
        for provider_id, provider_data in analysis["providers"].items():
            insights["provider_trends"][provider_id] = {
                "trend": provider_data["market_trend"],
                "position": provider_data["market_position"],
                "quality_ranking": provider_data["quality_ranking"],
                "cost_ranking": provider_data["cost_ranking"]
            }

        # Market segment analysis
        insights["market_segments"] = analysis["market_overview"]["market_segments"]

        # Cost trends
        sorted_by_cost = sorted(
            analysis["providers"].items(),
            key=lambda x: x[1]["cost_efficiency_score"],
            reverse=True
        )
        insights["cost_trends"] = {
            "most_cost_effective": sorted_by_cost[0][0] if sorted_by_cost else None,
            "average_efficiency": analysis["market_overview"]["average_cost_efficiency"],
            "cost_leaders": [p[0] for p in sorted_by_cost[:3]]
        }

        # Quality trends
        sorted_by_quality = sorted(
            analysis["providers"].items(),
            key=lambda x: x[1]["quality_score"],
            reverse=True
        )
        insights["quality_trends"] = {
            "highest_quality": sorted_by_quality[0][0] if sorted_by_quality else None,
            "average_quality": analysis["market_overview"]["average_quality_score"],
            "quality_leaders": [p[0] for p in sorted_by_quality[:3]]
        }

        # Strategic recommendations
        recommendations = []

        # Rising providers
        rising_providers = [
            p_id for p_id, p_data in analysis["providers"].items()
            if p_data["market_trend"] == "rising"
        ]
        if rising_providers:
            recommendations.append({
                "type": "opportunity",
                "title": "Watch rising providers",
                "description": f"Consider adding keys for {', '.join(rising_providers)}",
                "priority": "medium"
            })

        # Cost optimization
        high_cost_providers = [
            p_id for p_id, p_data in analysis["providers"].items()
            if p_data["cost_efficiency_score"] < 70 and p_data["has_keys"]
        ]
        if high_cost_providers:
            recommendations.append({
                "type": "cost_optimization",
                "title": "Replace high-cost providers",
                "description": f"Consider alternatives to {', '.join(high_cost_providers)}",
                "priority": "high"
            })

        insights["strategic_recommendations"] = recommendations

        return {
            "success": True,
            "insights": insights,
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate market insights: {str(e)}"
        )