"""
AI-Powered Workflow Optimization System
Intelligent analysis and optimization recommendations for workflows
"""

import asyncio
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class OptimizationType(Enum):
    """Types of workflow optimizations"""
    PERFORMANCE = "performance"
    COST = "cost"
    RELIABILITY = "reliability"
    EFFICIENCY = "efficiency"
    SECURITY = "security"
    SCALABILITY = "scalability"

class ImpactLevel(Enum):
    """Impact level of recommendations"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class OptimizationRecommendation:
    """AI-generated optimization recommendation"""
    id: str
    type: OptimizationType
    title: str
    description: str
    impact_level: ImpactLevel
    estimated_improvement: Dict[str, float]  # metric -> percentage_improvement
    implementation_effort: str  # "easy", "medium", "complex"
    steps: List[str]
    prerequisites: List[str]
    risks: List[str]
    workflow_section: Optional[str] = None
    confidence_score: float = 0.0  # 0-100
    supporting_data: Optional[Dict[str, Any]] = None

@dataclass
class WorkflowAnalysis:
    """Analysis of a workflow's performance and characteristics"""
    workflow_id: str
    workflow_name: str
    total_nodes: int
    total_edges: int
    integrations_used: List[str]
    complexity_score: float  # 0-100
    estimated_execution_time: float  # seconds
    failure_points: List[Dict[str, Any]]
    bottlenecks: List[Dict[str, Any]]
    optimization_opportunities: List[OptimizationRecommendation]
    analysis_timestamp: datetime

class AIWorkflowOptimizer:
    """AI-powered workflow optimization engine"""

    def __init__(self):
        self.optimization_rules = self._initialize_optimization_rules()
        self.performance_benchmarks = self._initialize_benchmarks()
        self.integration_patterns = self._initialize_integration_patterns()

    def _initialize_optimization_rules(self) -> Dict[OptimizationType, List[Dict]]:
        """Initialize AI optimization rules"""
        return {
            OptimizationType.PERFORMANCE: [
                {
                    "pattern": r"sequential.*api.*calls",
                    "condition": lambda data: self._count_sequential_api_calls(data) > 3,
                    "recommendation": self._recommend_parallel_processing,
                    "impact": ImpactLevel.HIGH,
                    "improvement": {"execution_time": 40, "throughput": 60}
                },
                {
                    "pattern": r"large.*data.*processing",
                    "condition": lambda data: self._has_large_data_processing(data),
                    "recommendation": self._recommend_batch_processing,
                    "impact": ImpactLevel.MEDIUM,
                    "improvement": {"memory_usage": 50, "processing_time": 30}
                },
                {
                    "pattern": r"redundant.*validations",
                    "condition": lambda data: self._has_redundant_validations(data),
                    "recommendation": self._recommend_validation_optimization,
                    "impact": ImpactLevel.LOW,
                    "improvement": {"execution_time": 15}
                }
            ],
            OptimizationType.COST: [
                {
                    "pattern": r"frequent.*ai.*calls",
                    "condition": lambda data: self._has_frequent_ai_calls(data),
                    "recommendation": self._recommend_ai_optimization,
                    "impact": ImpactLevel.HIGH,
                    "improvement": {"cost_reduction": 35}
                },
                {
                    "pattern": r"premium.*integration.*low.*usage",
                    "condition": lambda data: self._has_underutilized_premium_integrations(data),
                    "recommendation": self._recommend_integration_downgrade,
                    "impact": ImpactLevel.MEDIUM,
                    "improvement": {"cost_reduction": 25}
                }
            ],
            OptimizationType.RELIABILITY: [
                {
                    "pattern": r"single.*point.*failure",
                    "condition": lambda data: self._has_single_points_of_failure(data),
                    "recommendation": self._recommend_redundancy,
                    "impact": ImpactLevel.CRITICAL,
                    "improvement": {"reliability": 80}
                },
                {
                    "pattern": r"no.*error.*handling",
                    "condition": lambda data: self._lacks_error_handling(data),
                    "recommendation": self._recommend_error_handling,
                    "impact": ImpactLevel.HIGH,
                    "improvement": {"error_rate": 90}
                }
            ],
            OptimizationType.EFFICIENCY: [
                {
                    "pattern": r"manual.*approval.*required",
                    "condition": lambda data: self._has_manual_bottlenecks(data),
                    "recommendation": self._recommend_automation,
                    "impact": ImpactLevel.MEDIUM,
                    "improvement": {"cycle_time": 50, "manual_effort": 70}
                },
                {
                    "pattern": r"unnecessary.*data.*transformations",
                    "condition": lambda data: self._has_unnecessary_transformations(data),
                    "recommendation": self._recommend_streamlining,
                    "impact": ImpactLevel.LOW,
                    "improvement": {"execution_time": 20}
                }
            ]
        }

    def _initialize_benchmarks(self) -> Dict[str, Dict]:
        """Initialize performance benchmarks"""
        return {
            "api_response_time": {"good": 0.5, "average": 2.0, "poor": 5.0},  # seconds
            "workflow_success_rate": {"good": 0.99, "average": 0.95, "poor": 0.90},
            "daily_executions": {"small": 100, "medium": 1000, "large": 10000},
            "complexity_threshold": {"simple": 20, "moderate": 50, "complex": 100}
        }

    def _initialize_integration_patterns(self) -> Dict[str, Dict]:
        """Initialize known integration performance patterns"""
        return {
            "salesforce": {
                "avg_response_time": 1.2,
                "rate_limit": 5000,  # per hour
                "batch_size": 200,
                "cost_per_call": 0.00025
            },
            "slack": {
                "avg_response_time": 0.3,
                "rate_limit": 10000,
                "batch_size": 1000,
                "cost_per_call": 0.00001
            },
            "openai": {
                "avg_response_time": 2.5,
                "rate_limit": 3500,
                "batch_size": 20,
                "cost_per_1k_tokens": 0.002
            },
            "gmail": {
                "avg_response_time": 0.8,
                "rate_limit": 2500,
                "batch_size": 100,
                "cost_per_call": 0.00005
            }
        }

    async def analyze_workflow(
        self,
        workflow_data: Dict[str, Any],
        performance_metrics: Optional[Dict[str, Any]] = None
    ) -> WorkflowAnalysis:
        """Perform comprehensive workflow analysis"""
        workflow_id = workflow_data.get("id", "unknown")
        workflow_name = workflow_data.get("name", "Unnamed Workflow")

        # Basic analysis
        nodes = workflow_data.get("nodes", [])
        edges = workflow_data.get("edges", [])
        integrations = self._extract_integrations(nodes)

        # Complexity assessment
        complexity_score = self._calculate_complexity_score(workflow_data)

        # Performance analysis
        execution_time = self._estimate_execution_time(workflow_data, performance_metrics)

        # Identify issues
        failure_points = self._identify_failure_points(workflow_data)
        bottlenecks = self._identify_bottlenecks(workflow_data, performance_metrics)

        # Generate optimization recommendations
        recommendations = await self._generate_recommendations(workflow_data, performance_metrics)

        return WorkflowAnalysis(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            total_nodes=len(nodes),
            total_edges=len(edges),
            integrations_used=integrations,
            complexity_score=complexity_score,
            estimated_execution_time=execution_time,
            failure_points=failure_points,
            bottlenecks=bottlenecks,
            optimization_opportunities=recommendations,
            analysis_timestamp=datetime.now(timezone.utc)
        )

    async def optimize_workflow_plan(
        self,
        workflow_data: Dict[str, Any],
        optimization_goals: List[OptimizationType],
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create an optimization plan with specific goals"""
        analysis = await self.analyze_workflow(workflow_data)

        # Filter recommendations by goals
        relevant_recommendations = [
            rec for rec in analysis.optimization_opportunities
            if rec.type in optimization_goals
        ]

        # Sort by impact and effort ratio
        recommendations_by_priority = sorted(
            relevant_recommendations,
            key=lambda x: self._calculate_priority_score(x),
            reverse=True
        )

        # Create optimization phases
        phases = self._create_implementation_phases(recommendations_by_priority, constraints)

        return {
            "workflow_analysis": asdict(analysis),
            "optimization_plan": {
                "goals": [goal.value for goal in optimization_goals],
                "phases": phases,
                "estimated_total_improvement": self._calculate_total_improvement(recommendations_by_priority),
                "implementation_timeline": self._estimate_implementation_timeline(recommendations_by_priority)
            },
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

    async def monitor_workflow_performance(
        self,
        workflow_id: str,
        metrics: Dict[str, Any],
        time_window: int = 24  # hours
    ) -> Dict[str, Any]:
        """Monitor workflow performance and suggest real-time optimizations"""
        # Analyze performance trends
        trends = self._analyze_performance_trends(metrics, time_window)

        # Identify performance degradation
        issues = self._identify_performance_issues(trends)

        # Generate immediate recommendations
        urgent_recommendations = []
        for issue in issues:
            if issue["severity"] in ["high", "critical"]:
                recommendation = await self._generate_urgent_recommendation(issue, metrics)
                urgent_recommendations.append(recommendation)

        return {
            "workflow_id": workflow_id,
            "time_window_hours": time_window,
            "performance_trends": trends,
            "identified_issues": issues,
            "urgent_recommendations": urgent_recommendations,
            "health_score": self._calculate_health_score(metrics, issues),
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        }

    # Helper methods for analysis

    def _extract_integrations(self, nodes: List[Dict]) -> List[str]:
        """Extract integrations used in workflow"""
        integrations = set()
        for node in nodes:
            config = node.get("config", {})
            integration = config.get("integration")
            if integration:
                integrations.add(integration)
        return list(integrations)

    def _calculate_complexity_score(self, workflow_data: Dict[str, Any]) -> float:
        """Calculate workflow complexity score"""
        nodes = workflow_data.get("nodes", [])
        edges = workflow_data.get("edges", [])

        # Base complexity from size
        size_score = min(len(nodes) / 10, 10) * 5 + min(len(edges) / 10, 10) * 5

        # Complexity from node types
        node_types = set(node.get("type", "") for node in nodes)
        type_score = len(node_types) * 3

        # Complexity from conditions and loops
        conditional_nodes = len([n for n in nodes if n.get("type") == "condition"])
        condition_score = conditional_nodes * 8

        # Integration complexity
        integrations = self._extract_integrations(nodes)
        integration_score = len(integrations) * 4

        total_score = size_score + type_score + condition_score + integration_score
        return min(total_score, 100)

    def _estimate_execution_time(
        self,
        workflow_data: Dict[str, Any],
        performance_metrics: Optional[Dict[str, Any]] = None
    ) -> float:
        """Estimate workflow execution time"""
        nodes = workflow_data.get("nodes", [])
        total_time = 0.0

        for node in nodes:
            node_type = node.get("type", "")
            config = node.get("config", {})
            integration = config.get("integration")

            # Base time by node type
            if node_type == "trigger":
                continue  # Triggers don't add to execution time
            elif node_type == "action":
                if integration in self.integration_patterns:
                    total_time += self.integration_patterns[integration]["avg_response_time"]
                else:
                    total_time += 1.0  # Default estimate
            elif node_type == "condition":
                total_time += 0.1  # Minimal time for conditions
            else:
                total_time += 0.5  # Default for other types

        # Apply performance multipliers if metrics available
        if performance_metrics:
            success_rate = performance_metrics.get("success_rate", 1.0)
            avg_time = performance_metrics.get("avg_execution_time", total_time)

            # Use historical average if available and reliable
            if success_rate > 0.8 and avg_time > 0:
                total_time = avg_time

        return total_time

    def _identify_failure_points(self, workflow_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify potential failure points in workflow"""
        failure_points = []
        nodes = workflow_data.get("nodes", [])

        for i, node in enumerate(nodes):
            issues = []

            # Check for missing error handling
            if node.get("type") == "action" and not node.get("config", {}).get("error_handling"):
                issues.append("No error handling defined")

            # Check for hardcoded values
            config = node.get("config", {})
            if any(isinstance(v, str) and "test" in v.lower() for v in config.values()):
                issues.append("Contains test values in production")

            # Check for API rate limits
            integration = config.get("integration")
            if integration in self.integration_patterns:
                rate_limit = self.integration_patterns[integration]["rate_limit"]
                if rate_limit < 100:  # Low rate limit
                    issues.append(f"Low rate limit ({rate_limit}/hour) may cause throttling")

            if issues:
                failure_points.append({
                    "node_id": node.get("id", f"node_{i}"),
                    "node_type": node.get("type", "unknown"),
                    "issues": issues,
                    "risk_level": "high" if len(issues) > 1 else "medium"
                })

        return failure_points

    def _identify_bottlenecks(
        self,
        workflow_data: Dict[str, Any],
        performance_metrics: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Identify performance bottlenecks"""
        bottlenecks = []

        # Analyze sequential dependencies
        nodes = workflow_data.get("nodes", [])
        edges = workflow_data.get("edges", [])

        # Find longest path
        longest_path = self._find_longest_path(nodes, edges)
        if len(longest_path) > 5:
            bottlenecks.append({
                "type": "sequential_depth",
                "description": f"Long sequential path with {len(longest_path)} nodes",
                "impact": "high",
                "suggestion": "Consider parallel processing where possible"
            })

        # Check for data processing bottlenecks
        for node in nodes:
            config = node.get("config", {})
            if config.get("process_large_data") or config.get("batch_size", 1) > 1000:
                bottlenecks.append({
                    "type": "data_processing",
                    "node_id": node.get("id"),
                    "description": "Large data processing without optimization",
                    "impact": "medium",
                    "suggestion": "Implement batch processing or streaming"
                })

        return bottlenecks

    async def _generate_recommendations(
        self,
        workflow_data: Dict[str, Any],
        performance_metrics: Optional[Dict[str, Any]] = None
    ) -> List[OptimizationRecommendation]:
        """Generate AI-powered optimization recommendations"""
        recommendations = []
        data_context = {
            "workflow": workflow_data,
            "metrics": performance_metrics or {}
        }

        # Apply optimization rules
        for opt_type, rules in self.optimization_rules.items():
            for rule in rules:
                try:
                    if rule["condition"](data_context):
                        recommendation = rule["recommendation"](data_context, rule)
                        recommendation.type = opt_type
                        recommendations.append(recommendation)
                except Exception as e:
                    logger.error(f"Error applying optimization rule: {e}")

        # Sort by impact and confidence
        recommendations.sort(
            key=lambda x: (x.impact_level.value, x.confidence_score),
            reverse=True
        )

        return recommendations

    # Recommendation generation methods

    def _recommend_parallel_processing(self, data: Dict, rule: Dict) -> OptimizationRecommendation:
        """Recommend parallel processing for sequential API calls"""
        return OptimizationRecommendation(
            id="parallel_processing",
            type=OptimizationType.PERFORMANCE,
            title="Implement Parallel Processing",
            description="Multiple sequential API calls can be executed in parallel to reduce execution time",
            impact_level=rule["impact"],
            estimated_improvement=rule["improvement"],
            implementation_effort="medium",
            steps=[
                "Identify independent API calls in workflow",
                "Group calls that can be executed simultaneously",
                "Implement parallel execution pattern",
                "Add error handling for parallel calls",
                "Test with different batch sizes"
            ],
            prerequisites=["API access for parallel execution", "Error handling framework"],
            risks=["Rate limiting issues", "Increased complexity"],
            confidence_score=85,
            supporting_data={"sequential_calls": self._count_sequential_api_calls(data)}
        )

    def _recommend_ai_optimization(self, data: Dict, rule: Dict) -> OptimizationRecommendation:
        """Recommend AI usage optimization"""
        return OptimizationRecommendation(
            id="ai_optimization",
            type=OptimizationType.COST,
            title="Optimize AI Usage",
            description="Reduce AI API costs through smart caching and provider selection",
            impact_level=rule["impact"],
            estimated_improvement=rule["improvement"],
            implementation_effort="medium",
            steps=[
                "Implement response caching for repeated queries",
                "Use cost-effective AI providers for simple tasks",
                "Batch multiple AI requests where possible",
                "Implement request deduplication",
                "Monitor and optimize prompt lengths"
            ],
            prerequisites=["AI provider access", "Caching infrastructure"],
            risks=["Cache staleness", "Reduced accuracy with cheaper models"],
            confidence_score=90
        )

    def _recommend_redundancy(self, data: Dict, rule: Dict) -> OptimizationRecommendation:
        """Recommend adding redundancy for reliability"""
        return OptimizationRecommendation(
            id="add_redundancy",
            type=OptimizationType.RELIABILITY,
            title="Add Redundancy and Fallbacks",
            description="Implement fallback mechanisms to prevent single points of failure",
            impact_level=rule["impact"],
            estimated_improvement=rule["improvement"],
            implementation_effort="complex",
            steps=[
                "Identify critical failure points",
                "Implement backup integration providers",
                "Add retry logic with exponential backoff",
                "Create manual override procedures",
                "Set up monitoring and alerts"
            ],
            prerequisites=["Multiple integration options", "Monitoring system"],
            risks=["Increased complexity", "Higher costs"],
            confidence_score=95
        )

    def _recommend_automation(self, data: Dict, rule: Dict) -> OptimizationRecommendation:
        """Recommend automation of manual steps"""
        return OptimizationRecommendation(
            id="automation_opportunity",
            type=OptimizationType.EFFICIENCY,
            title="Automate Manual Approvals",
            description="Replace manual approval steps with automated decision rules",
            impact_level=rule["impact"],
            estimated_improvement=rule["improvement"],
            implementation_effort="medium",
            steps=[
                "Analyze approval patterns and criteria",
                "Define automated decision rules",
                "Implement rule-based approval system",
                "Create exception handling workflows",
                "Monitor and adjust rules"
            ],
            prerequisites=["Clear approval criteria", "Stakeholder buy-in"],
            risks=["Errors in automated decisions", "Loss of human oversight"],
            confidence_score=75
        )

    # Utility methods

    def _count_sequential_api_calls(self, data: Dict) -> int:
        """Count sequential API calls in workflow"""
        # Simplified implementation
        nodes = data.get("workflow", {}).get("nodes", [])
        api_nodes = [n for n in nodes if n.get("config", {}).get("integration")]
        return len(api_nodes)

    def _has_large_data_processing(self, data: Dict) -> bool:
        """Check if workflow processes large amounts of data"""
        nodes = data.get("workflow", {}).get("nodes", [])
        for node in nodes:
            config = node.get("config", {})
            if config.get("batch_size", 1) > 1000 or config.get("process_large_files"):
                return True
        return False

    def _has_frequent_ai_calls(self, data: Dict) -> bool:
        """Check if workflow makes frequent AI calls"""
        nodes = data.get("workflow", {}).get("nodes", [])
        ai_nodes = [n for n in nodes if "openai" in str(n.get("config", {})).lower()]
        return len(ai_nodes) > 2

    def _has_single_points_of_failure(self, data: Dict) -> bool:
        """Check for single points of failure"""
        # Simplified implementation
        return len(data.get("workflow", {}).get("nodes", [])) > 5

    def _lacks_error_handling(self, data: Dict) -> bool:
        """Check if workflow lacks proper error handling"""
        nodes = data.get("workflow", {}).get("nodes", [])
        for node in nodes:
            if not node.get("config", {}).get("error_handling"):
                return True
        return False

    def _has_manual_bottlenecks(self, data: Dict) -> bool:
        """Check for manual approval bottlenecks"""
        nodes = data.get("workflow", {}).get("nodes", [])
        for node in nodes:
            if "approval" in str(node.get("label", "")).lower():
                return True
        return False

    def _find_longest_path(self, nodes: List[Dict], edges: List[Dict]) -> List[str]:
        """Find longest path in workflow graph"""
        # Simplified implementation
        # In practice, this would use graph algorithms
        return [n.get("id", f"node_{i}") for i, n in enumerate(nodes)]

    def _calculate_priority_score(self, recommendation: OptimizationRecommendation) -> float:
        """Calculate priority score for recommendation"""
        impact_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        effort_weights = {"easy": 3, "medium": 2, "complex": 1}

        impact_score = impact_weights.get(recommendation.impact_level.value, 1)
        effort_score = effort_weights.get(recommendation.implementation_effort, 1)

        return (impact_score * recommendation.confidence_score) / (6 - effort_score)

    def _create_implementation_phases(
        self,
        recommendations: List[OptimizationRecommendation],
        constraints: Optional[Dict[str, Any]]
    ) -> List[Dict]:
        """Create phased implementation plan"""
        phases = [
            {
                "phase": 1,
                "name": "Quick Wins",
                "duration_weeks": 1,
                "recommendations": [r for r in recommendations if r.implementation_effort == "easy"][:3],
                "description": "High-impact, low-effort optimizations"
            },
            {
                "phase": 2,
                "name": "Core Optimizations",
                "duration_weeks": 2,
                "recommendations": [r for r in recommendations if r.implementation_effort == "medium"][:5],
                "description": "Significant improvements requiring moderate effort"
            },
            {
                "phase": 3,
                "name": "Advanced Enhancements",
                "duration_weeks": 4,
                "recommendations": [r for r in recommendations if r.implementation_effort == "complex"][:3],
                "description": "Complex optimizations for maximum benefit"
            }
        ]
        return [p for p in phases if p["recommendations"]]

    def _calculate_total_improvement(self, recommendations: List[OptimizationRecommendation]) -> Dict[str, float]:
        """Calculate total expected improvements"""
        improvements = {}
        for rec in recommendations:
            for metric, improvement in rec.estimated_improvement.items():
                improvements[metric] = improvements.get(metric, 0) + improvement
        return improvements

    def _estimate_implementation_timeline(self, recommendations: List[OptimizationRecommendation]) -> str:
        """Estimate total implementation timeline"""
        effort_days = {"easy": 1, "medium": 3, "complex": 7}
        total_days = sum(effort_days.get(rec.implementation_effort, 3) for rec in recommendations)
        return f"{total_days} days"

    def _analyze_performance_trends(self, metrics: Dict[str, Any], time_window: int) -> Dict:
        """Analyze performance trends over time"""
        # Simplified trend analysis
        return {
            "execution_time": "stable",
            "success_rate": "improving",
            "error_rate": "stable",
            "throughput": "increasing"
        }

    def _identify_performance_issues(self, trends: Dict) -> List[Dict]:
        """Identify performance issues from trends"""
        issues = []

        # Example issue detection logic
        if trends.get("success_rate") == "declining":
            issues.append({
                "type": "success_rate_decline",
                "severity": "high",
                "description": "Workflow success rate is declining"
            })

        return issues

    async def _generate_urgent_recommendation(self, issue: Dict, metrics: Dict) -> OptimizationRecommendation:
        """Generate urgent recommendation for performance issue"""
        return OptimizationRecommendation(
            id=f"urgent_{issue['type']}",
            type=OptimizationType.RELIABILITY,
            title="Urgent: Address Performance Issue",
            description=issue["description"],
            impact_level=ImpactLevel.CRITICAL,
            estimated_improvement={"reliability": 50},
            implementation_effort="easy",
            steps=["Investigate root cause", "Apply immediate fix", "Monitor closely"],
            prerequisites=["Access to metrics", "Debugging tools"],
            risks=["Temporary disruption"],
            confidence_score=95
        )

    def _calculate_health_score(self, metrics: Dict, issues: List[Dict]) -> float:
        """Calculate overall workflow health score"""
        base_score = 100

        # Deduct points for issues
        for issue in issues:
            if issue["severity"] == "critical":
                base_score -= 30
            elif issue["severity"] == "high":
                base_score -= 20
            elif issue["severity"] == "medium":
                base_score -= 10

        return max(0, base_score)

# Global AI workflow optimizer instance
_ai_workflow_optimizer = None

def get_ai_workflow_optimizer() -> AIWorkflowOptimizer:
    """Get the global AI workflow optimizer instance"""
    global _ai_workflow_optimizer
    if _ai_workflow_optimizer is None:
        _ai_workflow_optimizer = AIWorkflowOptimizer()
    return _ai_workflow_optimizer