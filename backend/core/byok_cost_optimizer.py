"""
BYOK Cost Optimization & Analytics Module
Enhanced cost tracking, optimization, and competitive analytics for ATOM's BYOK system
"""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

@dataclass
class CostOptimizationRecommendation:
    """AI-powered cost optimization recommendation"""
    task_type: str
    current_provider: str
    recommended_provider: str
    estimated_savings: float
    savings_percentage: float
    reasoning: str
    confidence: float
    alternative_providers: List[Dict[str, Any]]

@dataclass
class UsagePattern:
    """User's AI usage pattern analysis"""
    user_id: str
    task_distribution: Dict[str, float]  # task_type -> percentage
    peak_hours: List[int]  # hours of day
    preferred_providers: Dict[str, float]  # provider -> usage_count
    monthly_budget: Optional[float] = None
    cost_sensitivity: str = "medium"  # low, medium, high
    quality_preference: str = "balanced"  # cost, balanced, quality

@dataclass
class CompetitiveInsight:
    """Competitive intelligence on AI providers"""
    provider_id: str
    market_position: str  # budget, mid-range, premium
    unique_features: List[str]
    best_for_tasks: List[str]
    cost_efficiency_score: float  # 0-100
    quality_score: float  # 0-100
    reliability_score: float  # 0-100
    market_trend: str  # rising, stable, declining

class BYOKCostOptimizer:
    """Advanced cost optimization and analytics engine"""

    def __init__(self, byok_manager):
        self.byok_manager = byok_manager
        self.usage_patterns: Dict[str, UsagePattern] = {}
        self.competitive_insights: Dict[str, CompetitiveInsight] = {}
        self.optimization_cache = {}
        self._initialize_competitive_intelligence()
        self._load_usage_patterns()

    def _initialize_competitive_intelligence(self):
        """Initialize with market intelligence about AI providers"""
        insights = {
            "openai": CompetitiveInsight(
                provider_id="openai",
                market_position="premium",
                unique_features=["Superior reasoning", "Advanced coding", "Complex instruction following"],
                best_for_tasks=["code", "analysis", "complex_reasoning"],
                cost_efficiency_score=65,
                quality_score=95,
                reliability_score=90,
                market_trend="stable"
            ),
            "anthropic": CompetitiveInsight(
                provider_id="anthropic",
                market_position="premium",
                unique_features=["Context understanding", "Long conversations", "Creative writing"],
                best_for_tasks=["writing", "analysis", "chat"],
                cost_efficiency_score=75,
                quality_score=92,
                reliability_score=88,
                market_trend="rising"
            ),
            "moonshot": CompetitiveInsight(
                provider_id="moonshot",
                market_position="budget",
                unique_features=["Kimi thinking model", "Cost-effective", "Fast response"],
                best_for_tasks=["thinking", "reasoning", "general"],
                cost_efficiency_score=90,
                quality_score=80,
                reliability_score=75,
                market_trend="rising"
            ),
            "deepseek": CompetitiveInsight(
                provider_id="deepseek",
                market_position="budget",
                unique_features=["Specialized coding", "Mathematical reasoning", "Affordable"],
                best_for_tasks=["code", "math", "analysis"],
                cost_efficiency_score=95,
                quality_score=85,
                reliability_score=80,
                market_trend="rising"
            )
        }

        self.competitive_insights = insights

    def _load_usage_patterns(self):
        """Load historical usage patterns for analysis"""
        try:
            patterns_file = Path("./data/usage_patterns.json")
            if patterns_file.exists():
                with open(patterns_file, 'r') as f:
                    data = json.load(f)
                    for user_id, pattern_data in data.get("patterns", {}).items():
                        self.usage_patterns[user_id] = UsagePattern(**pattern_data)
        except Exception as e:
            logger.error(f"Failed to load usage patterns: {e}")

    def _save_usage_patterns(self):
        """Save usage patterns to disk"""
        try:
            patterns_file = Path("./data/usage_patterns.json")
            patterns_file.parent.mkdir(exist_ok=True)

            data = {
                "patterns": {
                    user_id: asdict(pattern)
                    for user_id, pattern in self.usage_patterns.items()
                },
                "last_updated": datetime.now().isoformat()
            }

            with open(patterns_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save usage patterns: {e}")

    def analyze_user_usage_pattern(self, user_id: str, days: int = 30) -> UsagePattern:
        """Analyze user's historical usage to create pattern profile"""
        # Get usage stats for the user (would need to be enhanced with actual user tracking)
        usage_stats = self.byok_manager.usage_stats

        # For demo, create a pattern based on available stats
        # In real implementation, this would analyze actual user history

        total_requests = sum(
            usage.total_requests for usage in usage_stats.values()
        )

        if total_requests == 0:
            # Default pattern for new users
            return UsagePattern(
                user_id=user_id,
                task_distribution={"general": 40, "chat": 30, "code": 20, "analysis": 10},
                peak_hours=[9, 10, 14, 15, 16],
                preferred_providers={},
                monthly_budget=50.0,
                cost_sensitivity="medium",
                quality_preference="balanced"
            )

        # Analyze task distribution from usage
        task_distribution = {}
        preferred_providers = {}

        for provider_id, usage in usage_stats.items():
            if usage.total_requests > 0:
                preferred_providers[provider_id] = usage.total_requests

        # Normalize provider usage to percentages
        if preferred_providers:
            total_provider_usage = sum(preferred_providers.values())
            preferred_providers = {
                k: (v / total_provider_usage) * 100
                for k, v in preferred_providers.items()
            }

        pattern = UsagePattern(
            user_id=user_id,
            task_distribution=task_distribution or {"general": 50, "chat": 30, "code": 20},
            peak_hours=[9, 10, 14, 15, 16, 20, 21],  # Common work hours
            preferred_providers=preferred_providers,
            monthly_budget=50.0,
            cost_sensitivity="medium",
            quality_preference="balanced"
        )

        self.usage_patterns[user_id] = pattern
        self._save_usage_patterns()

        return pattern

    def get_cost_optimization_recommendations(
        self,
        user_id: str,
        task_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> CostOptimizationRecommendation:
        """Get AI-powered cost optimization recommendations"""

        # Get user's usage pattern
        if user_id not in self.usage_patterns:
            self.analyze_user_usage_pattern(user_id)

        user_pattern = self.usage_patterns[user_id]

        # Get current optimal provider (user's usual choice)
        try:
            current_provider = self.byok_manager.get_optimal_provider(
                task_type,
                budget_constraint=user_pattern.monthly_budget / 30 if user_pattern.monthly_budget else None
            )
        except Exception as e:
            logger.error(f"Failed to get optimal provider: {e}", exc_info=True)
            current_provider = "openai"  # Fallback

        # Analyze all providers for this task
        suitable_providers = []
        for provider_id, provider in self.byok_manager.providers.items():
            if (provider.is_active and
                task_type in provider.supported_tasks and
                self.byok_manager.get_api_key(provider_id)):

                # Calculate suitability score
                cost_score = 100 - (provider.cost_per_token * 10000)  # Lower cost = higher score
                quality_score = self.competitive_insights.get(provider_id, CompetitiveInsight(provider_id, "", [], [], 70, 70, 70, "")).quality_score

                # Adjust based on user preferences
                if user_pattern.cost_sensitivity == "high":
                    weight_cost = 0.7
                    weight_quality = 0.3
                elif user_pattern.quality_preference == "quality":
                    weight_cost = 0.3
                    weight_quality = 0.7
                else:
                    weight_cost = weight_quality = 0.5

                suitability_score = (cost_score * weight_cost) + (quality_score * weight_quality)

                suitable_providers.append({
                    "provider_id": provider_id,
                    "suitability_score": suitability_score,
                    "cost_per_token": provider.cost_per_token,
                    "provider": provider
                })

        # Sort by suitability
        suitable_providers.sort(key=lambda x: x["suitability_score"], reverse=True)

        if not suitable_providers:
            raise ValueError(f"No suitable providers for task type: {task_type}")

        # Get recommended provider
        recommended = suitable_providers[0]
        recommended_provider = recommended["provider_id"]

        # Calculate estimated savings
        current_cost_per_token = self.byok_manager.providers.get(current_provider, {}).get("cost_per_token", 0.00003)
        recommended_cost_per_token = recommended["cost_per_token"]

        if current_cost_per_token > 0 and recommended_cost_per_token < current_cost_per_token:
            savings_percentage = ((current_cost_per_token - recommended_cost_per_token) / current_cost_per_token) * 100
            estimated_savings = savings_percentage  # Simplified calculation
        else:
            savings_percentage = 0
            estimated_savings = 0

        # Generate reasoning
        insight = self.competitive_insights.get(recommended_provider)
        if insight:
            reasoning = f"Best balance of cost and quality for {task_type} tasks. {insight.unique_features[0] if insight.unique_features else ''}"
        else:
            reasoning = f"Most cost-effective provider available for {task_type}"

        # Get alternative providers
        alternatives = []
        for alt in suitable_providers[1:4]:  # Top 3 alternatives
            alt_insight = self.competitive_insights.get(alt["provider_id"])
            alternatives.append({
                "provider_id": alt["provider_id"],
                "name": alt["provider"].name,
                "cost_per_token": alt["cost_per_token"],
                "suitability_score": alt["suitability_score"],
                "market_position": alt_insight.market_position if alt_insight else "unknown"
            })

        return CostOptimizationRecommendation(
            task_type=task_type,
            current_provider=current_provider,
            recommended_provider=recommended_provider,
            estimated_savings=estimated_savings,
            savings_percentage=savings_percentage,
            reasoning=reasoning,
            confidence=min(95, 70 + (recommended["suitability_score"] / 10)),
            alternative_providers=alternatives
        )

    def get_competitive_analysis_report(self) -> Dict[str, Any]:
        """Generate comprehensive competitive analysis report"""
        report = {
            "generated_at": datetime.now().isoformat(),
            "providers": {},
            "market_overview": {},
            "recommendations": []
        }

        # Provider analysis
        for provider_id, insight in self.competitive_insights.items():
            provider = self.byok_manager.providers.get(provider_id)
            usage = self.byok_manager.usage_stats.get(provider_id)

            provider_data = {
                **asdict(insight),
                "active": provider.is_active if provider else False,
                "has_keys": bool(self.byok_manager.get_api_key(provider_id)),
                "actual_usage": asdict(usage) if usage else None,
                "cost_ranking": 0,  # Will be calculated
                "quality_ranking": 0,  # Will be calculated
                "overall_score": (insight.cost_efficiency_score + insight.quality_score + insight.reliability_score) / 3
            }

            report["providers"][provider_id] = provider_data

        # Calculate rankings
        cost_ranked = sorted(
            report["providers"].items(),
            key=lambda x: x[1]["cost_efficiency_score"],
            reverse=True
        )
        quality_ranked = sorted(
            report["providers"].items(),
            key=lambda x: x[1]["quality_score"],
            reverse=True
        )

        for i, (provider_id, _) in enumerate(cost_ranked, 1):
            report["providers"][provider_id]["cost_ranking"] = i

        for i, (provider_id, _) in enumerate(quality_ranked, 1):
            report["providers"][provider_id]["quality_ranking"] = i

        # Market overview
        total_providers = len(report["providers"])
        active_providers = len([p for p in report["providers"].values() if p["active"]])
        providers_with_keys = len([p for p in report["providers"].values() if p["has_keys"]])

        report["market_overview"] = {
            "total_providers": total_providers,
            "active_providers": active_providers,
            "providers_with_keys": providers_with_keys,
            "market_segments": {
                "budget": len([p for p in report["providers"].values() if p["market_position"] == "budget"]),
                "mid_range": len([p for p in report["providers"].values() if p["market_position"] == "mid-range"]),
                "premium": len([p for p in report["providers"].values() if p["market_position"] == "premium"])
            },
            "average_quality_score": sum(p["quality_score"] for p in report["providers"].values()) / total_providers,
            "average_cost_efficiency": sum(p["cost_efficiency_score"] for p in report["providers"].values()) / total_providers
        }

        # Strategic recommendations
        recommendations = []

        # Cost optimization opportunities
        budget_providers = [p for p in report["providers"].values() if p["market_position"] == "budget" and p["has_keys"]]
        if budget_providers:
            top_budget = max(budget_providers, key=lambda x: x["cost_efficiency_score"])
            recommendations.append({
                "type": "cost_optimization",
                "title": f"Use {top_budget['provider_id']} for cost-sensitive tasks",
                "description": f"Save up to {100 - top_budget['cost_efficiency_score']}% on routine tasks",
                "priority": "high" if top_budget["cost_efficiency_score"] > 85 else "medium"
            })

        # Quality optimization opportunities
        premium_providers = [p for p in report["providers"].values() if p["market_position"] == "premium" and p["has_keys"]]
        if premium_providers:
            top_premium = max(premium_providers, key=lambda x: x["quality_score"])
            recommendations.append({
                "type": "quality_optimization",
                "title": f"Use {top_premium['provider_id']} for complex tasks",
                "description": f"Get {top_premium['quality_score']}% quality for critical workloads",
                "priority": "high" if top_premium["quality_score"] > 90 else "medium"
            })

        # Missing keys opportunities
        providers_without_keys = [p for p in report["providers"].values() if not p["has_keys"] and p["active"]]
        if providers_without_keys:
            recommendations.append({
                "type": "expansion_opportunity",
                "title": f"Add API keys for {len(providers_without_keys)} more providers",
                "description": "Unlock additional cost optimization and quality options",
                "priority": "medium",
                "providers": [p["provider_id"] for p in providers_without_keys]
            })

        report["recommendations"] = recommendations

        return report

    def simulate_cost_savings(
        self,
        user_id: str,
        months: int = 6,
        adoption_rate: float = 0.8
    ) -> Dict[str, Any]:
        """Simulate potential cost savings over time with optimization"""

        if user_id not in self.usage_patterns:
            self.analyze_user_usage_pattern(user_id)

        user_pattern = self.usage_patterns[user_id]

        # Get historical cost data
        historical_cost = sum(
            usage.cost_accumulated
            for usage in self.byok_manager.usage_stats.values()
        )

        if historical_cost == 0:
            # Estimate based on typical usage
            estimated_monthly_cost = user_pattern.monthly_budget or 50.0
        else:
            # Use actual data
            estimated_monthly_cost = historical_cost

        # Simulate optimization
        total_tasks = estimated_monthly_cost * 10  # Rough estimate of tasks per dollar
        optimized_cost = 0
        savings_details = {}

        for task_type, percentage in user_pattern.task_distribution.items():
            task_count = int(total_tasks * (percentage / 100) * adoption_rate)

            try:
                recommendation = self.get_cost_optimization_recommendations(user_id, task_type)

                if recommendation.savings_percentage > 0:
                    task_cost = (estimated_monthly_cost * (percentage / 100))
                    optimized_task_cost = task_cost * (1 - recommendation.savings_percentage / 100)
                    task_savings = task_cost - optimized_task_cost

                    optimized_cost += optimized_task_cost
                    savings_details[task_type] = {
                        "current_cost": task_cost,
                        "optimized_cost": optimized_task_cost,
                        "savings": task_savings,
                        "savings_percentage": recommendation.savings_percentage,
                        "recommended_provider": recommendation.recommended_provider
                    }
                else:
                    optimized_cost += estimated_monthly_cost * (percentage / 100)
                    savings_details[task_type] = {
                        "current_cost": estimated_monthly_cost * (percentage / 100),
                        "optimized_cost": estimated_monthly_cost * (percentage / 100),
                        "savings": 0,
                        "savings_percentage": 0,
                        "recommended_provider": "no_change"
                    }
            except Exception as e:
                logger.error(f"Failed to optimize for task {task_type}: {e}")
                optimized_cost += estimated_monthly_cost * (percentage / 100)

        total_monthly_savings = estimated_monthly_cost - optimized_cost
        total_savings_months = total_monthly_savings * months

        return {
            "user_id": user_id,
            "simulation_period_months": months,
            "adoption_rate": adoption_rate,
            "current_monthly_cost": estimated_monthly_cost,
            "optimized_monthly_cost": optimized_cost,
            "monthly_savings": total_monthly_savings,
            "total_projected_savings": total_savings_months,
            "savings_percentage": (total_monthly_savings / estimated_monthly_cost) * 100 if estimated_monthly_cost > 0 else 0,
            "task_breakdown": savings_details,
            "roi_calculation": {
                "implementation_cost": 0,  # BYOK optimization is free to implement
                "payback_period": "Immediate",
                "annualized_return": (total_savings_months / months) * 12
            }
        }