"""
BYOK API with Intelligent Routing

Integrates the intelligent AI provider router with existing BYOK API endpoints
to provide automatic provider selection and optimization.
"""

from flask import Blueprint, request, jsonify
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

from user_api_key_service import get_user_api_key_service
from ai_provider_router import get_ai_router, TaskType

logger = logging.getLogger(__name__)

# Create blueprint for intelligent routing
intelligent_routing_bp = Blueprint("intelligent_routing", __name__, url_prefix="/api/v1/intelligent")

class IntelligentRoutingAPI:
    """API for intelligent AI provider routing and optimization"""
    
    def __init__(self):
        self.user_service = get_user_api_key_service()
        self.ai_router = get_ai_router()
    
    def _get_user_configured_providers(self, user_id: str) -> List[str]:
        """Get list of providers configured for user"""
        try:
            return self.user_service.list_user_services(user_id)
        except Exception as e:
            logger.error(f"Error getting user providers: {e}")
            return []
    
    def _validate_request(self, data: Dict) -> Dict[str, Any]:
        """Validate routing request parameters"""
        errors = []
        
        if not data.get("prompt"):
            errors.append("Prompt is required")
        
        if not data.get("user_id"):
            errors.append("User ID is required")
        
        # Validate context length if provided
        context_length = data.get("context_length", 0)
        if not isinstance(context_length, int) or context_length < 0:
            errors.append("Context length must be a non-negative integer")
        
        # Validate optional parameters
        task_types = data.get("task_types", [])
        if task_types and not isinstance(task_types, list):
            errors.append("Task types must be a list")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _format_provider_response(self, routing_result: Dict, user_providers: List[str]) -> Dict[str, Any]:
        """Format routing result for API response"""
        if not routing_result.get("success"):
            return {
                "success": False,
                "error": routing_result.get("error", "Unknown routing error"),
                "suggestion": routing_result.get("suggestion"),
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Add availability status
        provider_id = routing_result.get("provider_id")
        is_configured = provider_id in user_providers
        
        return {
            "success": True,
            "selected_provider": {
                "id": provider_id,
                "name": routing_result.get("provider", {}).get("name"),
                "configured": is_configured,
                "model": routing_result.get("model"),
                "score": routing_result.get("score"),
                "cost_savings": routing_result.get("provider", {}).get("cost_savings", 0),
                "specialization": routing_result.get("provider", {}).get("specialization"),
                "reliability": routing_result.get("provider", {}).get("reliability")
            },
            "routing_analysis": {
                "detected_tasks": routing_result.get("detected_tasks", []),
                "selection_reasons": routing_result.get("reasons", []),
                "selection_reasoning": routing_result.get("selection_reasoning"),
                "total_providers_available": len(user_providers),
                "alternative_providers": self._get_alternative_providers(
                    routing_result, user_providers
                )
            },
            "recommendations": self._get_recommendations(routing_result, user_providers),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _get_alternative_providers(self, routing_result: Dict, user_providers: List[str]) -> List[Dict]:
        """Get alternative providers if selected one isn't configured"""
        if routing_result.get("provider_id") in user_providers:
            return []
        
        # Return top 3 configured providers as alternatives
        from ai_provider_router import ProviderPriority
        
        alternatives = []
        for provider_id in user_providers[:3]:  # Top 3
            if provider_id != routing_result.get("provider_id"):
                # This would need provider data from router
                alternatives.append({
                    "id": provider_id,
                    "reason": "Configured fallback option"
                })
        
        return alternatives
    
    def _get_recommendations(self, routing_result: Dict, user_providers: List[str]) -> List[str]:
        """Get optimization recommendations"""
        recommendations = []
        
        if len(user_providers) < 3:
            recommendations.append(
                "Configure additional providers for better cost optimization and reliability"
            )
        
        detected_tasks = routing_result.get("detected_tasks", [])
        
        # Check for missing specialized providers
        if TaskType.CHINESE_LANGUAGE.value in detected_tasks and "glm_4_6" not in user_providers:
            recommendations.append(
                "Add GLM-4.6 for optimal Chinese language processing (88% cost savings)"
            )
        
        if TaskType.LONG_CONTEXT.value in detected_tasks and "kimi_k2" not in user_providers:
            recommendations.append(
                "Add Kimi K2 for long-context document analysis (75% cost savings)"
            )
        
        if TaskType.CODE_GENERATION.value in detected_tasks and "deepseek" not in user_providers:
            recommendations.append(
                "Add DeepSeek AI for cost-effective code generation (98% cost savings)"
            )
        
        if TaskType.EMBEDDINGS.value in detected_tasks and "google_gemini" not in user_providers:
            recommendations.append(
                "Add Google Gemini for high-performance embeddings (93% cost savings)"
            )
        
        return recommendations


# Initialize routing API
routing_api = IntelligentRoutingAPI()

@intelligent_routing_bp.route("/select-provider", methods=["POST"])
def select_provider():
    """
    Intelligently select the best AI provider for a given request
    
    Request Body:
    {
        "user_id": "string",
        "prompt": "string",
        "context_length": "integer (optional)",
        "task_types": ["string"] (optional),
        "user_preferences": {} (optional)
    }
    
    Response:
    {
        "success": true,
        "selected_provider": {...},
        "routing_analysis": {...},
        "recommendations": [...],
        "timestamp": "ISO8601"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400
        
        # Validate request
        validation = routing_api._validate_request(data)
        if not validation["valid"]:
            return jsonify({
                "success": False,
                "error": "Validation failed",
                "details": validation["errors"]
            }), 400
        
        # Get user's configured providers
        user_id = data["user_id"]
        configured_providers = routing_api._get_user_configured_providers(user_id)
        
        if not configured_providers:
            return jsonify({
                "success": False,
                "error": "No AI providers configured",
                "suggestion": "Please configure at least one AI provider in settings"
            }), 400
        
        # Select optimal provider
        routing_result = routing_api.ai_router.select_optimal_provider(
            prompt=data["prompt"],
            configured_providers=configured_providers,
            context_length=data.get("context_length", 0),
            user_preferences=data.get("user_preferences")
        )
        
        # Format and return response
        response = routing_api._format_provider_response(routing_result, configured_providers)
        
        logger.info(
            f"Intelligent routing for user {user_id}: selected {routing_result.get('provider_id')}"
        )
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in provider selection: {e}")
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@intelligent_routing_bp.route("/analyze-task", methods=["POST"])
def analyze_task():
    """
    Analyze task type from prompt without selecting provider
    
    Request Body:
    {
        "prompt": "string",
        "context_length": "integer (optional)"
    }
    
    Response:
    {
        "success": true,
        "task_analysis": {
            "detected_tasks": [...],
            "confidence_scores": {...},
            "recommendations": [...]
        }
    }
    """
    try:
        data = request.get_json()
        if not data or not data.get("prompt"):
            return jsonify({
                "success": False,
                "error": "Prompt is required"
            }), 400
        
        # Analyze task
        task_types = routing_api.ai_router.detect_task_type(
            data["prompt"],
            data.get("context_length", 0)
        )
        
        # Convert to response format
        detected_tasks = [task_type.value for task_type in task_types]
        
        response = {
            "success": True,
            "task_analysis": {
                "detected_tasks": detected_tasks,
                "primary_task": detected_tasks[0] if detected_tasks else "general",
                "task_count": len(detected_tasks)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in task analysis: {e}")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500


@intelligent_routing_bp.route("/cost-analysis/<user_id>", methods=["GET"])
def get_cost_analysis(user_id: str):
    """
    Get cost optimization analysis for a user
    
    Response:
    {
        "success": true,
        "cost_analysis": {
            "configured_providers": [...],
            "potential_savings": "...",
            "recommendations": [...]
        }
    }
    """
    try:
        configured_providers = routing_api._get_user_configured_providers(user_id)
        
        if not configured_providers:
            return jsonify({
                "success": False,
                "error": "No providers configured for analysis"
            }), 400
        
        # Generate cost analysis
        cost_report = routing_api.ai_router.get_cost_optimization_report(configured_providers)
        
        response = {
            "success": True,
            "cost_analysis": cost_report,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in cost analysis: {e}")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500


@intelligent_routing_bp.route("/routing-status/<user_id>", methods=["GET"])
def get_routing_status(user_id: str):
    """
    Get routing capabilities and status for a user
    
    Response:
    {
        "success": true,
        "routing_status": {
            "available_providers": [...],
            "total_providers": "number",
            "routing_capabilities": [...],
            "ready_for_intelligent_routing": "boolean"
        }
    }
    """
    try:
        configured_providers = routing_api._get_user_configured_providers(user_id)
        available_providers = routing_api.ai_router.available_providers
        
        # Check if ready for intelligent routing
        ready_for_routing = len(configured_providers) > 0
        
        response = {
            "success": True,
            "routing_status": {
                "configured_providers": [
                    {
                        "id": provider_id,
                        "name": available_providers[provider_id]["name"],
                        "capabilities": available_providers[provider_id]["capabilities"],
                        "cost_savings": available_providers[provider_id]["cost_savings"]
                    }
                    for provider_id in configured_providers
                    if provider_id in available_providers
                ],
                "total_providers": len(configured_providers),
                "max_providers_available": len(available_providers),
                "routing_capabilities": [
                    "task_type_detection",
                    "cost_optimization",
                    "provider_ranking",
                    "model_selection",
                    "fallback_recommendations"
                ],
                "ready_for_intelligent_routing": ready_for_routing
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in routing status: {e}")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500


# Export blueprint for registration
def get_intelligent_routing_blueprint() -> Blueprint:
    """Get the intelligent routing blueprint"""
    return intelligent_routing_bp


# Example usage and testing
if __name__ == "__main__":
    from flask import Flask
    
    app = Flask(__name__)
    app.register_blueprint(intelligent_routing_bp)
    
    print("🧠 Intelligent Routing API Test")
    print("=" * 50)
    
    # Test endpoint
    test_data = {
        "user_id": "test_user_123",
        "prompt": "Write a Python function to analyze this large dataset",
        "context_length": 15000,
        "user_preferences": {
            "cost_priority": "high",
            "chinese_support": False
        }
    }
    
    with app.test_client() as client:
        response = client.post(
            "/api/v1/intelligent/select-provider",
            json=test_data,
            content_type="application/json"
        )
        
        if response.status_code == 200:
            result = response.get_json()
            if result["success"]:
                print("✅ Intelligent Routing Test PASSED")
                print(f"Selected Provider: {result['selected_provider']['name']}")
                print(f"Model: {result['selected_provider']['model']}")
                print(f"Cost Savings: {result['selected_provider']['cost_savings']}%")
                print(f"Detected Tasks: {', '.join(result['routing_analysis']['detected_tasks'])}")
                print(f"Recommendations: {len(result['recommendations'])}")
            else:
                print(f"❌ Routing failed: {result['error']}")
        else:
            print(f"❌ API test failed: {response.status_code}")
    
    print("\n🧠 Intelligent Routing API Test Complete!")