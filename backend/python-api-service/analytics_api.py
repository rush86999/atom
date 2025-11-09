"""
Analytics Dashboard API

Provides API endpoints for the comprehensive analytics dashboard
including provider metrics, routing performance, and cost optimization.
"""

from flask import Blueprint, request, jsonify, Response
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

from analytics_dashboard import get_analytics, TimeRange, MetricType

logger = logging.getLogger(__name__)

# Create blueprint for analytics
analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/v1/analytics")

class AnalyticsAPI:
    """API for analytics dashboard endpoints"""
    
    def __init__(self):
        self.analytics = get_analytics()
    
    def _validate_time_range(self, time_range: str) -> TimeRange:
        """Validate and convert time range string"""
        time_ranges = {
            "hour": TimeRange.HOUR,
            "day": TimeRange.DAY,
            "week": TimeRange.WEEK,
            "month": TimeRange.MONTH,
            "quarter": TimeRange.QUARTER,
            "year": TimeRange.YEAR
        }
        
        return time_ranges.get(time_range.lower(), TimeRange.WEEK)
    
    def _validate_request(self, data: Dict) -> Dict[str, Any]:
        """Validate analytics request parameters"""
        errors = []
        
        # Validate time range if provided
        if "time_range" in data:
            try:
                self._validate_time_range(data["time_range"])
            except:
                errors.append("Invalid time range. Use: hour, day, week, month, quarter, year")
        
        # Validate provider list if provided
        if "providers" in data:
            providers = data["providers"]
            if not isinstance(providers, list):
                errors.append("Providers must be a list")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }


# Initialize analytics API
analytics_api = AnalyticsAPI()


@analytics_bp.route("/providers/metrics", methods=["GET", "POST"])
def get_provider_metrics():
    """
    Get comprehensive provider metrics
    
    Query Parameters (GET):
    - time_range: hour, day, week, month, quarter, year
    - providers: comma-separated list of provider IDs
    
    Request Body (POST):
    {
        "time_range": "week",
        "providers": ["deepseek", "glm_4_6"]
    }
    
    Response:
    {
        "success": true,
        "time_range": "week",
        "metrics": [
            {
                "provider_id": "deepseek",
                "provider_name": "DeepSeek AI",
                "requests": 2662,
                "success_rate": 96.5,
                "average_response_time": 1.57,
                "total_cost": 0.27,
                "cost_savings_percentage": 98.0,
                "models_used": {...},
                "task_types": {...}
            }
        ],
        "timestamp": "2025-11-09T..."
    }
    """
    try:
        # Get parameters from request
        if request.method == "POST":
            data = request.get_json() or {}
        else:
            data = {
                "time_range": request.args.get("time_range", "week"),
                "providers": request.args.get("providers", "").split(",") if request.args.get("providers") else None
            }
            
            # Remove empty provider from list
            if data["providers"] == [""]:
                data["providers"] = None
        
        # Validate request
        validation = analytics_api._validate_request(data)
        if not validation["valid"]:
            return jsonify({
                "success": False,
                "error": "Validation failed",
                "details": validation["errors"]
            }), 400
        
        # Get time range
        time_range = analytics_api._validate_time_range(data.get("time_range", "week"))
        providers = data.get("providers")
        
        # Get provider metrics
        metrics = analytics_api.analytics.get_provider_metrics(time_range, providers)
        
        # Format for response
        response_metrics = []
        for metric in metrics:
            response_metrics.append({
                "provider_id": metric.provider_id,
                "provider_name": metric.provider_name,
                "requests": metric.requests,
                "success_rate": metric.success_rate,
                "average_response_time": metric.average_response_time,
                "cost_per_1k_tokens": metric.cost_per_1k_tokens,
                "total_cost": metric.total_cost,
                "cost_savings_percentage": metric.cost_savings_percentage,
                "models_used": metric.models_used,
                "task_types": metric.task_types
            })
        
        return jsonify({
            "success": True,
            "time_range": time_range.value,
            "total_providers": len(response_metrics),
            "metrics": response_metrics,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in provider metrics: {e}")
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@analytics_bp.route("/routing/performance", methods=["GET", "POST"])
def get_routing_performance():
    """
    Get routing performance analytics
    
    Query Parameters (GET):
    - time_range: hour, day, week, month, quarter, year
    
    Request Body (POST):
    {
        "time_range": "week"
    }
    
    Response:
    {
        "success": true,
        "time_range": "week",
        "performance": {
            "total_requests": 5486,
            "optimal_selections": 4882,
            "suboptimal_selections": 604,
            "routing_accuracy": 89.0,
            "cost_savings_achieved": 661.4,
            "task_detection_accuracy": 93.9,
            "user_override_rate": 10.9
        },
        "timestamp": "2025-11-09T..."
    }
    """
    try:
        # Get parameters
        if request.method == "POST":
            data = request.get_json() or {}
        else:
            data = {"time_range": request.args.get("time_range", "week")}
        
        # Validate request
        validation = analytics_api._validate_request(data)
        if not validation["valid"]:
            return jsonify({
                "success": False,
                "error": "Validation failed",
                "details": validation["errors"]
            }), 400
        
        # Get time range
        time_range = analytics_api._validate_time_range(data.get("time_range", "week"))
        
        # Get routing analytics
        routing_metrics = analytics_api.analytics.get_routing_analytics(time_range)
        
        return jsonify({
            "success": True,
            "time_range": time_range.value,
            "performance": {
                "total_requests": routing_metrics.total_requests,
                "optimal_selections": routing_metrics.optimal_selections,
                "suboptimal_selections": routing_metrics.suboptimal_selections,
                "routing_accuracy": routing_metrics.routing_accuracy,
                "cost_savings_achieved": routing_metrics.cost_savings_achieved,
                "task_detection_accuracy": routing_metrics.task_detection_accuracy,
                "user_override_rate": routing_metrics.user_override_rate
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in routing performance: {e}")
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@analytics_bp.route("/cost/optimization", methods=["GET", "POST"])
def get_cost_optimization():
    """
    Get comprehensive cost optimization report
    
    Query Parameters (GET):
    - time_range: hour, day, week, month, quarter, year
    
    Request Body (POST):
    {
        "time_range": "month"
    }
    
    Response:
    {
        "success": true,
        "time_range": "month",
        "report": {
            "summary": {...},
            "provider_breakdown": [...],
            "optimization_insights": [...],
            "recommendations": [...]
        },
        "timestamp": "2025-11-09T..."
    }
    """
    try:
        # Get parameters
        if request.method == "POST":
            data = request.get_json() or {}
        else:
            data = {"time_range": request.args.get("time_range", "month")}
        
        # Validate request
        validation = analytics_api._validate_request(data)
        if not validation["valid"]:
            return jsonify({
                "success": False,
                "error": "Validation failed",
                "details": validation["errors"]
            }), 400
        
        # Get time range
        time_range = analytics_api._validate_time_range(data.get("time_range", "month"))
        
        # Get cost optimization report
        cost_report = analytics_api.analytics.get_cost_optimization_report(time_range)
        
        return jsonify({
            "success": True,
            "time_range": time_range.value,
            "report": cost_report,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in cost optimization: {e}")
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@analytics_bp.route("/user/<user_id>/analytics", methods=["GET"])
def get_user_analytics(user_id: str):
    """
    Get analytics for specific user
    
    Query Parameters:
    - time_range: hour, day, week, month, quarter, year
    
    Response:
    {
        "success": true,
        "user_id": "user123",
        "time_range": "week",
        "analytics": {
            "total_requests": 150,
            "configured_providers": ["deepseek", "glm_4_6"],
            "preferred_providers": {"deepseek": 45, "glm_4_6": 35},
            "cost_savings_achieved": 85.5,
            "routing_confidence": 0.88,
            "optimization_score": 0.82
        },
        "timestamp": "2025-11-09T..."
    }
    """
    try:
        # Get parameters
        time_range_str = request.args.get("time_range", "week")
        time_range = analytics_api._validate_time_range(time_range_str)
        
        # Get user analytics
        user_analytics = analytics_api.analytics.get_user_analytics(user_id, time_range)
        
        return jsonify({
            "success": True,
            "user_id": user_id,
            "time_range": time_range.value,
            "analytics": {
                "total_requests": user_analytics.total_requests,
                "configured_providers": user_analytics.configured_providers,
                "preferred_providers": user_analytics.preferred_providers,
                "cost_savings_achieved": user_analytics.cost_savings_achieved,
                "routing_confidence": user_analytics.routing_confidence,
                "optimization_score": user_analytics.optimization_score
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in user analytics: {e}")
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@analytics_bp.route("/export", methods=["POST"])
def export_analytics():
    """
    Export analytics data in various formats
    
    Request Body:
    {
        "format": "json" | "csv" | "excel",
        "time_range": "week",
        "include": ["providers", "routing", "cost", "users"]
    }
    
    Response:
    File download in requested format
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400
        
        # Validate format
        format_type = data.get("format", "json").lower()
        if format_type not in ["json", "csv", "excel"]:
            return jsonify({
                "success": False,
                "error": "Invalid format. Use: json, csv, excel"
            }), 400
        
        # Validate time range
        time_range_str = data.get("time_range", "month")
        time_range = analytics_api._validate_time_range(time_range_str)
        
        # Export data
        export_data = analytics_api.analytics.export_analytics_data(format_type, time_range)
        
        # Set appropriate headers for download
        filename = f"analytics-{time_range.value}-{datetime.utcnow().strftime('%Y%m%d')}.{format_type}"
        
        if format_type == "json":
            return Response(
                export_data,
                mimetype="application/json",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        elif format_type == "csv":
            return Response(
                export_data,
                mimetype="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        elif format_type == "excel":
            return Response(
                export_data,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        
    except Exception as e:
        logger.error(f"Error in export analytics: {e}")
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@analytics_bp.route("/dashboard/summary", methods=["GET"])
def get_dashboard_summary():
    """
    Get dashboard summary with key metrics
    
    Response:
    {
        "success": true,
        "summary": {
            "total_requests": 100000,
            "active_providers": 7,
            "average_cost_savings": 75.5,
            "routing_accuracy": 89.2,
            "top_providers": [...],
            "recent_activity": [...]
        },
        "timestamp": "2025-11-09T..."
    }
    """
    try:
        # Get recent metrics for dashboard
        provider_metrics = analytics_api.analytics.get_provider_metrics(TimeRange.DAY)
        routing_metrics = analytics_api.analytics.get_routing_analytics(TimeRange.DAY)
        cost_report = analytics_api.analytics.get_cost_optimization_report(TimeRange.DAY)
        
        # Calculate summary metrics
        total_requests = sum(m.requests for m in provider_metrics)
        active_providers = len([m for m in provider_metrics if m.requests > 0])
        
        if provider_metrics:
            avg_savings = sum(m.cost_savings_percentage for m in provider_metrics) / len(provider_metrics)
            top_providers = sorted(provider_metrics, key=lambda m: m.requests, reverse=True)[:3]
        else:
            avg_savings = 0
            top_providers = []
        
        summary = {
            "total_requests": total_requests,
            "active_providers": active_providers,
            "average_cost_savings": avg_savings,
            "routing_accuracy": routing_metrics.routing_accuracy,
            "cost_savings_achieved": routing_metrics.cost_savings_achieved,
            "top_providers": [
                {
                    "name": m.provider_name,
                    "requests": m.requests,
                    "savings": m.cost_savings_percentage
                }
                for m in top_providers
            ],
            "cost_summary": cost_report.get("summary", {}),
            "optimization_insights": cost_report.get("optimization_insights", [])
        }
        
        return jsonify({
            "success": True,
            "summary": summary,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in dashboard summary: {e}")
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }), 500


# Export blueprint for registration
def get_analytics_blueprint() -> Blueprint:
    """Get analytics dashboard blueprint"""
    return analytics_bp


# Example usage and testing
if __name__ == "__main__":
    from flask import Flask
    
    app = Flask(__name__)
    app.register_blueprint(analytics_bp)
    
    print("📊 Analytics Dashboard API Test")
    print("=" * 50)
    
    # Test endpoints
    endpoints = [
        ("/api/v1/analytics/dashboard/summary", "Dashboard Summary"),
        ("/api/v1/analytics/providers/metrics", "Provider Metrics"),
        ("/api/v1/analytics/routing/performance", "Routing Performance"),
        ("/api/v1/analytics/cost/optimization", "Cost Optimization")
    ]
    
    with app.test_client() as client:
        for endpoint, name in endpoints:
            print(f"\n🧪 Testing {name}:")
            
            response = client.get(endpoint)
            
            if response.status_code == 200:
                result = response.get_json()
                if result["success"]:
                    print(f"   ✅ {name} API working")
                    if "summary" in result:
                        summary = result["summary"]
                        print(f"      📊 Total Requests: {summary.get('total_requests', 0):,}")
                        print(f"      🔢 Active Providers: {summary.get('active_providers', 0)}")
                        print(f"      💰 Avg Savings: {summary.get('average_cost_savings', 0):.1f}%")
                        print(f"      🎯 Routing Accuracy: {summary.get('routing_accuracy', 0):.1f}%")
                else:
                    print(f"   ❌ {name} API failed: {result.get('error')}")
            else:
                print(f"   ❌ {name} API error: {response.status_code}")
    
    print("\n📊 Analytics Dashboard API Test Complete!")