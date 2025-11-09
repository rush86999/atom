"""
AI Provider Analytics Dashboard

Provides comprehensive analytics for AI provider usage, cost optimization,
routing performance, and user behavior insights.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
import logging
import random

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """Types of analytics metrics"""
    USAGE = "usage"
    COST = "cost"
    PERFORMANCE = "performance"
    ROUTING = "routing"
    USER_BEHAVIOR = "user_behavior"
    OPTIMIZATION = "optimization"

class TimeRange(Enum):
    """Time ranges for analytics"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"

@dataclass
class ProviderMetric:
    """Individual provider metric"""
    provider_id: str
    provider_name: str
    requests: int
    success_rate: float
    average_response_time: float
    cost_per_1k_tokens: float
    total_cost: float
    cost_savings_percentage: float
    models_used: Dict[str, int]
    task_types: Dict[str, int]

@dataclass
class RoutingMetric:
    """Routing performance metric"""
    total_requests: int
    optimal_selections: int
    suboptimal_selections: int
    routing_accuracy: float
    cost_savings_achieved: float
    task_detection_accuracy: float
    user_override_rate: float

@dataclass
class UserAnalytics:
    """User-specific analytics"""
    user_id: str
    total_requests: int
    configured_providers: List[str]
    preferred_providers: Dict[str, int]
    cost_savings_achieved: float
    routing_confidence: float
    optimization_score: float

class AIProviderAnalytics:
    """Comprehensive analytics system for AI provider usage"""
    
    def __init__(self):
        self.providers = {
            "openai": {"name": "OpenAI", "base_cost": 0.03, "color": "#10A37F"},
            "deepseek": {"name": "DeepSeek AI", "base_cost": 0.0006, "color": "#0066CC"},
            "anthropic": {"name": "Anthropic Claude", "base_cost": 0.008, "color": "#CC785C"},
            "google_gemini": {"name": "Google Gemini", "base_cost": 0.0005, "color": "#4285F4"},
            "azure_openai": {"name": "Azure OpenAI", "base_cost": 0.036, "color": "#0078D4"},
            "glm_4_6": {"name": "GLM-4.6", "base_cost": 0.0036, "color": "#FF6B35"},
            "kimi_k2": {"name": "Kimi K2", "base_cost": 0.0075, "color": "#9B59B6"}
        }
        
        # Mock data storage (in production, use actual database)
        self.usage_data = {}
        self.routing_data = {}
        self.cost_data = {}
        self._initialize_mock_data()
    
    def _initialize_mock_data(self):
        """Initialize with realistic mock data for demonstration"""
        import random
        
        # Generate usage data for past 30 days
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
        for provider_id, provider_info in self.providers.items():
            daily_usage = {}
            current_date = start_date
            
            while current_date <= end_date:
                # Generate realistic usage patterns
                base_requests = random.randint(50, 500)
                if provider_id == "deepseek":
                    base_requests = int(base_requests * 1.5)  # Higher usage due to cost savings
                elif provider_id == "glm_4_6":
                    base_requests = int(base_requests * 1.3)  # Good adoption
                elif provider_id == "kimi_k2":
                    base_requests = int(base_requests * 1.1)  # Moderate adoption
                
                daily_usage[current_date.strftime("%Y-%m-%d")] = {
                    "requests": base_requests,
                    "success_rate": random.uniform(0.92, 0.99),
                    "avg_response_time": random.uniform(0.5, 2.5),
                    "tokens_used": random.randint(10000, 100000),
                    "models_used": self._get_provider_models(provider_id),
                    "task_types": self._get_provider_tasks(provider_id)
                }
                
                current_date += timedelta(days=1)
            
            self.usage_data[provider_id] = daily_usage
    
    def _get_provider_models(self, provider_id: str) -> Dict[str, int]:
        """Get realistic model usage distribution"""
        model_distributions = {
            "openai": {"gpt-4": 30, "gpt-3.5-turbo": 70},
            "deepseek": {"deepseek-chat": 60, "deepseek-coder": 40},
            "anthropic": {"claude-3-sonnet": 50, "claude-3-haiku": 50},
            "google_gemini": {"gemini-2.0-flash": 40, "gemini-2.0-pro": 60},
            "glm_4_6": {"glm-4.6": 40, "glm-4": 60},
            "kimi_k2": {"moonshot-v1-32k": 30, "moonshot-v1-8k": 70}
        }
        return model_distributions.get(provider_id, {})
    
    def _get_provider_tasks(self, provider_id: str) -> Dict[str, int]:
        """Get realistic task type distribution"""
        task_distributions = {
            "openai": {"chat": 40, "code_generation": 30, "reasoning": 30},
            "deepseek": {"chat": 20, "code_generation": 60, "reasoning": 20},
            "anthropic": {"chat": 30, "reasoning": 50, "long_context": 20},
            "google_gemini": {"chat": 50, "embeddings": 30, "reasoning": 20},
            "glm_4_6": {"chat": 30, "chinese_language": 40, "reasoning": 30},
            "kimi_k2": {"chat": 20, "long_context": 50, "document_analysis": 30}
        }
        return task_distributions.get(provider_id, {})
    
    def get_provider_metrics(self, time_range: TimeRange = TimeRange.WEEK, 
                          providers: List[str] = None) -> List[ProviderMetric]:
        """
        Get comprehensive metrics for providers
        
        Args:
            time_range: Time period for metrics
            providers: Specific providers to analyze (None = all)
        
        Returns:
            List of provider metrics
        """
        if providers is None:
            providers = list(self.providers.keys())
        
        metrics = []
        end_date = datetime.utcnow()
        start_date = self._get_start_date(end_date, time_range)
        
        for provider_id in providers:
            if provider_id not in self.providers:
                continue
            
            # Calculate metrics for time range
            total_requests = 0
            total_response_time = 0
            total_tokens = 0
            successful_requests = 0
            models_used = {}
            task_types = {}
            
            current_date = start_date
            while current_date <= end_date:
                date_key = current_date.strftime("%Y-%m-%d")
                
                if provider_id in self.usage_data and date_key in self.usage_data[provider_id]:
                    data = self.usage_data[provider_id][date_key]
                    total_requests += data["requests"]
                    total_response_time += data["avg_response_time"] * data["requests"]
                    total_tokens += data["tokens_used"]
                    successful_requests += int(data["requests"] * data["success_rate"])
                    
                    # Aggregate models and tasks
                    for model, count in data["models_used"].items():
                        models_used[model] = models_used.get(model, 0) + count
                    
                    for task, count in data["task_types"].items():
                        task_types[task] = task_types.get(task, 0) + count
                
                current_date += timedelta(days=1)
            
            if total_requests > 0:
                provider_info = self.providers[provider_id]
                
                # Calculate cost and savings
                total_cost = (total_tokens / 1000) * provider_info["base_cost"]
                openai_cost = (total_tokens / 1000) * self.providers["openai"]["base_cost"]
                cost_savings = ((openai_cost - total_cost) / openai_cost) * 100
                
                metrics.append(ProviderMetric(
                    provider_id=provider_id,
                    provider_name=provider_info["name"],
                    requests=total_requests,
                    success_rate=(successful_requests / total_requests) * 100,
                    average_response_time=total_response_time / total_requests,
                    cost_per_1k_tokens=provider_info["base_cost"],
                    total_cost=total_cost,
                    cost_savings_percentage=cost_savings,
                    models_used=models_used,
                    task_types=task_types
                ))
        
        # Sort by requests (descending)
        return sorted(metrics, key=lambda m: m.requests, reverse=True)
    
    def get_routing_analytics(self, time_range: TimeRange = TimeRange.WEEK) -> RoutingMetric:
        """
        Get routing performance analytics
        
        Args:
            time_range: Time period for analysis
        
        Returns:
            Comprehensive routing metrics
        """
        end_date = datetime.utcnow()
        start_date = self._get_start_date(end_date, time_range)
        
        total_requests = 0
        optimal_selections = 0
        routing_savings = 0
        task_detections = 0
        user_overrides = 0
        
        current_date = start_date
        while current_date <= end_date:
            # Mock routing data (in production, use actual routing logs)
            daily_requests = random.randint(100, 1000)
            optimal_rate = 0.89  # 89% routing accuracy
            
            total_requests += daily_requests
            optimal_selections += int(daily_requests * optimal_rate)
            routing_savings += random.uniform(75, 95)  # Average cost savings achieved
            task_detections += int(daily_requests * 0.94)  # 94% task detection accuracy
            user_overrides += int(daily_requests * 0.11)  # 11% user override rate
            
            current_date += timedelta(days=1)
        
        if total_requests > 0:
            return RoutingMetric(
                total_requests=total_requests,
                optimal_selections=optimal_selections,
                suboptimal_selections=total_requests - optimal_selections,
                routing_accuracy=(optimal_selections / total_requests) * 100,
                cost_savings_achieved=routing_savings,
                task_detection_accuracy=(task_detections / total_requests) * 100,
                user_override_rate=(user_overrides / total_requests) * 100
            )
        
        return RoutingMetric(0, 0, 0, 0, 0, 0, 0)
    
    def get_user_analytics(self, user_id: str, time_range: TimeRange = TimeRange.WEEK) -> UserAnalytics:
        """
        Get analytics for specific user
        
        Args:
            user_id: User identifier
            time_range: Time period for analysis
        
        Returns:
            User-specific analytics
        """
        # Mock user data (in production, use actual user data)
        user_data = {
            "total_requests": random.randint(50, 500),
            "configured_providers": ["deepseek", "glm_4_6", "google_gemini"],
            "preferred_providers": {
                "deepseek": 45,
                "glm_4_6": 35,
                "google_gemini": 20
            },
            "cost_savings": random.uniform(70, 95),
            "routing_confidence": random.uniform(0.8, 0.95),
            "optimization_score": random.uniform(0.75, 0.92)
        }
        
        return UserAnalytics(
            user_id=user_id,
            total_requests=user_data["total_requests"],
            configured_providers=user_data["configured_providers"],
            preferred_providers=user_data["preferred_providers"],
            cost_savings_achieved=user_data["cost_savings"],
            routing_confidence=user_data["routing_confidence"],
            optimization_score=user_data["optimization_score"]
        )
    
    def get_cost_optimization_report(self, time_range: TimeRange = TimeRange.MONTH) -> Dict[str, Any]:
        """
        Generate comprehensive cost optimization report
        
        Args:
            time_range: Time period for report
        
        Returns:
            Detailed cost optimization analysis
        """
        end_date = datetime.utcnow()
        start_date = self._get_start_date(end_date, time_range)
        
        provider_metrics = self.get_provider_metrics(time_range)
        
        total_requests = sum(m.requests for m in provider_metrics)
        total_cost = sum(m.total_cost for m in provider_metrics)
        
        # Calculate OpenAI baseline cost
        total_tokens = sum(m.total_cost * 1000 / m.cost_per_1k_tokens for m in provider_metrics)
        openai_baseline = (total_tokens / 1000) * self.providers["openai"]["base_cost"]
        
        cost_savings = openai_baseline - total_cost
        savings_percentage = (cost_savings / openai_baseline) * 100 if openai_baseline > 0 else 0
        
        return {
            "time_range": time_range.value,
            "period": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            },
            "summary": {
                "total_requests": total_requests,
                "total_cost": total_cost,
                "openai_baseline": openai_baseline,
                "cost_savings": cost_savings,
                "savings_percentage": savings_percentage,
                "providers_used": len(provider_metrics)
            },
            "provider_breakdown": [
                {
                    "id": m.provider_id,
                    "name": m.provider_name,
                    "requests": m.requests,
                    "cost": m.total_cost,
                    "savings_percentage": m.cost_savings_percentage,
                    "share_percentage": (m.total_cost / total_cost) * 100 if total_cost > 0 else 0
                }
                for m in provider_metrics
            ],
            "optimization_insights": self._generate_optimization_insights(provider_metrics),
            "recommendations": self._generate_cost_recommendations(provider_metrics)
        }
    
    def _get_start_date(self, end_date: datetime, time_range: TimeRange) -> datetime:
        """Get start date for given time range"""
        if time_range == TimeRange.HOUR:
            return end_date - timedelta(hours=1)
        elif time_range == TimeRange.DAY:
            return end_date - timedelta(days=1)
        elif time_range == TimeRange.WEEK:
            return end_date - timedelta(weeks=1)
        elif time_range == TimeRange.MONTH:
            return end_date - timedelta(days=30)
        elif time_range == TimeRange.QUARTER:
            return end_date - timedelta(days=90)
        elif time_range == TimeRange.YEAR:
            return end_date - timedelta(days=365)
        return end_date - timedelta(days=7)  # Default to week
    
    def _generate_optimization_insights(self, provider_metrics: List[ProviderMetric]) -> List[str]:
        """Generate insights from provider metrics"""
        insights = []
        
        if not provider_metrics:
            return insights
        
        # Most used provider
        most_used = max(provider_metrics, key=lambda m: m.requests)
        insights.append(f"Most used provider: {most_used.provider_name} ({most_used.requests} requests)")
        
        # Best cost savings
        best_savings = max(provider_metrics, key=lambda m: m.cost_savings_percentage)
        insights.append(f"Best cost savings: {best_savings.provider_name} ({best_savings.cost_savings_percentage:.1f}% savings)")
        
        # Highest success rate
        best_reliability = max(provider_metrics, key=lambda m: m.success_rate)
        insights.append(f"Highest reliability: {best_reliability.provider_name} ({best_reliability.success_rate:.1f}% success rate)")
        
        # GLM-4.6 and Kimi K2 specific insights
        glm_4_6_metrics = [m for m in provider_metrics if m.provider_id == "glm_4_6"]
        if glm_4_6_metrics:
            insights.append("GLM-4.6 showing strong adoption for multilingual tasks")
        
        kimi_k2_metrics = [m for m in provider_metrics if m.provider_id == "kimi_k2"]
        if kimi_k2_metrics:
            insights.append("Kimi K2 effectively handling long-context requests")
        
        return insights
    
    def _generate_cost_recommendations(self, provider_metrics: List[ProviderMetric]) -> List[str]:
        """Generate cost optimization recommendations"""
        recommendations = []
        
        if not provider_metrics:
            return recommendations
        
        provider_ids = [m.provider_id for m in provider_metrics]
        
        # Check for missing high-savings providers
        if "deepseek" not in provider_ids:
            recommendations.append("Add DeepSeek AI for 98% cost savings on code generation")
        
        if "google_gemini" not in provider_ids:
            recommendations.append("Add Google Gemini for 93% savings on embeddings")
        
        if "glm_4_6" not in provider_ids:
            recommendations.append("Add GLM-4.6 for 88% savings on Chinese language tasks")
        
        if "kimi_k2" not in provider_ids:
            recommendations.append("Add Kimi K2 for 75% savings on long-context analysis")
        
        # Provider-specific recommendations
        for metric in provider_metrics:
            if metric.success_rate < 95:
                recommendations.append(f"Monitor {metric.provider_name} reliability ({metric.success_rate:.1f}% success rate)")
            
            if metric.average_response_time > 2.0:
                recommendations.append(f"Consider optimizing {metric.provider_name} for faster response times")
        
        return recommendations
    
    def export_analytics_data(self, format_type: str = "json", time_range: TimeRange = TimeRange.MONTH) -> str:
        """
        Export analytics data in various formats
        
        Args:
            format_type: Export format ("json", "csv", "excel")
            time_range: Time period for data
        
        Returns:
            Exported data as string
        """
        cost_report = self.get_cost_optimization_report(time_range)
        provider_metrics = self.get_provider_metrics(time_range)
        routing_metrics = self.get_routing_analytics(time_range)
        
        export_data = {
            "export_date": datetime.utcnow().isoformat(),
            "time_range": time_range.value,
            "cost_optimization": cost_report,
            "provider_metrics": [
                {
                    "provider_id": m.provider_id,
                    "provider_name": m.provider_name,
                    "requests": m.requests,
                    "success_rate": m.success_rate,
                    "average_response_time": m.average_response_time,
                    "total_cost": m.total_cost,
                    "cost_savings_percentage": m.cost_savings_percentage,
                    "models_used": m.models_used,
                    "task_types": m.task_types
                }
                for m in provider_metrics
            ],
            "routing_performance": {
                "total_requests": routing_metrics.total_requests,
                "optimal_selections": routing_metrics.optimal_selections,
                "routing_accuracy": routing_metrics.routing_accuracy,
                "cost_savings_achieved": routing_metrics.cost_savings_achieved,
                "task_detection_accuracy": routing_metrics.task_detection_accuracy,
                "user_override_rate": routing_metrics.user_override_rate
            }
        }
        
        if format_type.lower() == "json":
            return json.dumps(export_data, indent=2)
        elif format_type.lower() == "csv":
            return self._export_to_csv(export_data)
        elif format_type.lower() == "excel":
            return self._export_to_excel(export_data)
        
        return json.dumps(export_data, indent=2)
    
    def _export_to_csv(self, data: Dict) -> str:
        """Export data to CSV format"""
        csv_lines = []
        
        # Headers
        csv_lines.append("Provider,Requests,Success Rate,Avg Response Time,Cost,Cost Savings")
        
        # Provider metrics
        for provider in data["provider_metrics"]:
            csv_lines.append(f"{provider['provider_name']},{provider['requests']},{provider['success_rate']:.1f},{provider['average_response_time']:.2f},{provider['total_cost']:.2f},{provider['cost_savings_percentage']:.1f}")
        
        return "\n".join(csv_lines)
    
    def _export_to_excel(self, data: Dict) -> str:
        """Export data to Excel format (placeholder)"""
        return "Excel export not implemented in this demo"


# Global analytics instance
analytics = AIProviderAnalytics()


def get_analytics() -> AIProviderAnalytics:
    """Get global analytics instance"""
    return analytics


# Example usage and testing
if __name__ == "__main__":
    print("📊 AI Provider Analytics Dashboard Test")
    print("=" * 60)
    
    # Test provider metrics
    print("📈 Provider Metrics (Last Week):")
    provider_metrics = analytics.get_provider_metrics(TimeRange.WEEK)
    
    for i, metric in enumerate(provider_metrics[:5], 1):
        print(f"   {i}. {metric.provider_name}")
        print(f"      📊 Requests: {metric.requests:,}")
        print(f"      ✅ Success Rate: {metric.success_rate:.1f}%")
        print(f"      ⏱️  Response Time: {metric.average_response_time:.2f}s")
        print(f"      💰 Cost: ${metric.total_cost:.2f}")
        print(f"      💸 Savings: {metric.cost_savings_percentage:.1f}%")
        print("   " + "-" * 30)
    
    # Test routing analytics
    print(f"\n🧠 Routing Performance (Last Week):")
    routing = analytics.get_routing_analytics(TimeRange.WEEK)
    print(f"   📊 Total Requests: {routing.total_requests:,}")
    print(f"   ✅ Routing Accuracy: {routing.routing_accuracy:.1f}%")
    print(f"   💰 Cost Savings Achieved: {routing.cost_savings_achieved:.1f}%")
    print(f"   🎯 Task Detection Accuracy: {routing.task_detection_accuracy:.1f}%")
    print(f"   👤 User Override Rate: {routing.user_override_rate:.1f}%")
    
    # Test cost optimization report
    print(f"\n💰 Cost Optimization Report (Last Month):")
    cost_report = analytics.get_cost_optimization_report(TimeRange.MONTH)
    summary = cost_report["summary"]
    
    print(f"   📊 Total Requests: {summary['total_requests']:,}")
    print(f"   💰 Total Cost: ${summary['total_cost']:.2f}")
    print(f"   📈 OpenAI Baseline: ${summary['openai_baseline']:.2f}")
    print(f"   💸 Cost Savings: ${summary['cost_savings']:.2f} ({summary['savings_percentage']:.1f}%)")
    print(f"   🔢 Providers Used: {summary['providers_used']}")
    
    print(f"\n💡 Optimization Insights:")
    for insight in cost_report["optimization_insights"]:
        print(f"   • {insight}")
    
    print(f"\n📋 Recommendations:")
    for rec in cost_report["recommendations"]:
        print(f"   • {rec}")
    
    print(f"\n🎉 Analytics Dashboard Test Complete!")