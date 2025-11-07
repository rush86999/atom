"""
ATOM Cross-Service AI API Routes
Flask routes for unified AI intelligence across all integrations
Following ATOM API patterns and conventions
"""

from flask import Blueprint, request, jsonify
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
import asyncio
import traceback

from cross_service_ai_service import (
    create_cross_service_ai_service,
    IntegrationType,
    CrossServiceInsight,
    WorkflowRecommendation,
    BusinessPrediction
)

from atom_chat_ai_service import (
    create_atom_chat_ai_service,
    ChatResponse
)

# Create blueprint
router = Blueprint('cross_service_ai', __name__, url_prefix='/api/cross-service-ai')

# Global instances
cross_service_ai = create_cross_service_ai_service()
chat_ai_service = create_atom_chat_ai_service()

# Decorator for requiring valid tokens
def require_integration_auth(f):
    import functools
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Extract access tokens from request
            access_tokens = {}
            
            # Try query parameters first
            if request.args:
                for service in IntegrationType:
                    token = request.args.get(f'{service.value}_token')
                    if token:
                        access_tokens[service.value] = token
            
            # Try JSON body
            if request.is_json and not access_tokens:
                data = request.get_json()
                for service in IntegrationType:
                    token = data.get(f'{service.value}_token')
                    if token:
                        access_tokens[service.value] = token
            
            if not access_tokens:
                return jsonify({
                    "ok": False,
                    "error": "At least one access token is required. Provide tokens for services you want to analyze."
                }), 400
            
            # Store in Flask's request context for route to use
            request.access_tokens = access_tokens
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Integration auth decorator error: {e}")
            return jsonify({
                "ok": False,
                "error": f"Authentication failed: {str(e)}"
            }), 500
    
    return decorated_function

# Data collection endpoints
@router.route("/collect-data", methods=["POST"])
@require_integration_auth
def collect_service_data():
    """Collect data from specified services"""
    try:
        data = request.get_json()
        limit = data.get('limit', 20)
        
        # Parse access tokens with service types
        service_tokens = {}
        for service_name, token in request.access_tokens.items():
            if service_name in IntegrationType.__members__:
                service_tokens[IntegrationType[service_name]] = token
        
        if not service_tokens:
            return jsonify({
                "ok": False,
                "error": "No valid service tokens provided"
            }), 400
        
        logger.info(f"Collecting data from {len(service_tokens)} services with limit {limit}")
        
        # Run async data collection
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(
                cross_service_ai.collect_all_service_data(service_tokens, limit)
            )
        finally:
            loop.close()
        
        # Format results
        collected_data = []
        for data_item in results:
            collected_data.append({
                "service_type": data_item.service_type.value,
                "service_id": data_item.service_id,
                "item_id": data_item.item_id,
                "title": data_item.title,
                "content": data_item.content[:500] + "..." if len(data_item.content) > 500 else data_item.content,
                "metadata": data_item.metadata,
                "timestamp": data_item.timestamp.isoformat(),
                "tags": data_item.tags,
                "importance_score": data_item.importance_score,
                "relationships": data_item.relationships
            })
        
        return jsonify({
            "ok": True,
            "data": {
                "collected_items": len(collected_data),
                "items": collected_data,
                "services_analyzed": list(service_tokens.keys()),
                "collection_time": datetime.utcnow().isoformat()
            },
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to collect service data: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Insights endpoints
@router.route("/insights", methods=["GET"])
def get_insights():
    """Get cross-service AI insights"""
    try:
        limit = int(request.args.get('limit', 10))
        service_filter = request.args.get('service')
        
        # Use cached insights if available
        if not cross_service_ai.insights:
            return jsonify({
                "ok": False,
                "error": "No insights available. Please collect data first.",
                "action": "POST /api/cross-service-ai/collect-data"
            }), 404
        
        insights = cross_service_ai.insights
        
        # Filter by service if specified
        if service_filter:
            service_filter = service_filter.lower()
            insights = [i for i in insights if service_filter in [s.value for s in i.services_involved]]
        
        # Limit results
        insights = insights[:limit]
        
        # Format insights
        formatted_insights = []
        for insight in insights:
            formatted_insights.append({
                "insight_id": insight.insight_id,
                "insight_type": insight.insight_type,
                "title": insight.title,
                "description": insight.description,
                "confidence_score": insight.confidence_score,
                "business_impact": insight.business_impact,
                "action_items": insight.action_items,
                "related_data_count": len(insight.related_data),
                "generated_at": insight.generated_at.isoformat(),
                "services_involved": [s.value for s in insight.services_involved]
            })
        
        return jsonify({
            "ok": True,
            "data": {
                "insights": formatted_insights,
                "total_insights": len(formatted_insights),
                "available_insights": len(cross_service_ai.insights),
                "generated_for_services": list(set([s.value for i in cross_service_ai.insights for s in i.services_involved]))
            },
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get insights: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@router.route("/insights/generate", methods=["POST"])
@require_integration_auth
def generate_insights():
    """Generate new cross-service AI insights"""
    try:
        data = request.get_json()
        force = data.get('force', False)
        
        # Parse access tokens
        service_tokens = {}
        for service_name, token in request.access_tokens.items():
            if service_name in IntegrationType.__members__:
                service_tokens[IntegrationType[service_name]] = token
        
        logger.info(f"Generating insights with {len(service_tokens)} services")
        
        # Run async insight generation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # First collect data
            if force or not cross_service_ai.service_data:
                loop.run_until_complete(cross_service_ai.collect_all_service_data(service_tokens, limit=15))
            
            # Generate insights
            insights = loop.run_until_complete(cross_service_ai.generate_cross_service_insights())
        finally:
            loop.close()
        
        # Format insights
        formatted_insights = []
        for insight in insights:
            formatted_insights.append({
                "insight_id": insight.insight_id,
                "insight_type": insight.insight_type,
                "title": insight.title,
                "description": insight.description,
                "confidence_score": insight.confidence_score,
                "business_impact": insight.business_impact,
                "action_items": insight.action_items,
                "generated_at": insight.generated_at.isoformat(),
                "services_involved": [s.value for s in insight.services_involved]
            })
        
        return jsonify({
            "ok": True,
            "data": {
                "insights": formatted_insights,
                "total_generated": len(formatted_insights),
                "data_points_analyzed": len(cross_service_ai.service_data),
                "generation_time": datetime.utcnow().isoformat()
            },
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Generated {len(formatted_insights)} new insights"
        })
        
    except Exception as e:
        logger.error(f"Failed to generate insights: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Workflow recommendation endpoints
@router.route("/workflows", methods=["GET"])
def get_workflow_recommendations():
    """Get AI workflow recommendations"""
    try:
        limit = int(request.args.get('limit', 10))
        service_filter = request.args.get('service')
        
        # Use cached recommendations if available
        if not cross_service_ai.workflows:
            return jsonify({
                "ok": False,
                "error": "No workflow recommendations available. Please collect data first.",
                "action": "POST /api/cross-service-ai/workflows/generate"
            }), 404
        
        workflows = cross_service_ai.workflows
        
        # Filter by service if specified
        if service_filter:
            service_filter = service_filter.lower()
            workflows = [w for w in workflows if service_filter in [s.value for s in w.services]]
        
        # Limit results
        workflows = workflows[:limit]
        
        # Format workflows
        formatted_workflows = []
        for workflow in workflows:
            formatted_workflows.append({
                "workflow_id": workflow.workflow_id,
                "workflow_name": workflow.workflow_name,
                "description": workflow.description,
                "trigger_condition": workflow.trigger_condition,
                "services": [s.value for s in workflow.services],
                "steps": workflow.steps,
                "expected_benefit": workflow.expected_benefit,
                "confidence_score": workflow.confidence_score,
                "priority": workflow.priority
            })
        
        return jsonify({
            "ok": True,
            "data": {
                "workflows": formatted_workflows,
                "total_workflows": len(formatted_workflows),
                "available_workflows": len(cross_service_ai.workflows),
                "by_priority": {
                    "high": len([w for w in formatted_workflows if w["priority"] == "high"]),
                    "medium": len([w for w in formatted_workflows if w["priority"] == "medium"]),
                    "low": len([w for w in formatted_workflows if w["priority"] == "low"])
                }
            },
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get workflow recommendations: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@router.route("/workflows/generate", methods=["POST"])
@require_integration_auth
def generate_workflow_recommendations():
    """Generate new workflow recommendations"""
    try:
        data = request.get_json()
        force = data.get('force', False)
        
        # Parse access tokens
        service_tokens = {}
        for service_name, token in request.access_tokens.items():
            if service_name in IntegrationType.__members__:
                service_tokens[IntegrationType[service_name]] = token
        
        logger.info(f"Generating workflow recommendations with {len(service_tokens)} services")
        
        # Run async workflow generation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # First collect data
            if force or not cross_service_ai.service_data:
                loop.run_until_complete(cross_service_ai.collect_all_service_data(service_tokens, limit=15))
            
            # Generate workflows
            workflows = loop.run_until_complete(cross_service_ai.recommend_workflows())
        finally:
            loop.close()
        
        # Format workflows
        formatted_workflows = []
        for workflow in workflows:
            formatted_workflows.append({
                "workflow_id": workflow.workflow_id,
                "workflow_name": workflow.workflow_name,
                "description": workflow.description,
                "trigger_condition": workflow.trigger_condition,
                "services": [s.value for s in workflow.services],
                "steps": workflow.steps,
                "expected_benefit": workflow.expected_benefit,
                "confidence_score": workflow.confidence_score,
                "priority": workflow.priority
            })
        
        return jsonify({
            "ok": True,
            "data": {
                "workflows": formatted_workflows,
                "total_generated": len(formatted_workflows),
                "data_points_analyzed": len(cross_service_ai.service_data),
                "generation_time": datetime.utcnow().isoformat()
            },
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Generated {len(formatted_workflows)} workflow recommendations"
        })
        
    except Exception as e:
        logger.error(f"Failed to generate workflow recommendations: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Business prediction endpoints
@router.route("/predictions", methods=["GET"])
def get_business_predictions():
    """Get AI business predictions"""
    try:
        limit = int(request.args.get('limit', 10))
        prediction_type = request.args.get('type')
        
        # Use cached predictions if available
        # Note: In current implementation, predictions are generated on demand
        
        if not cross_service_ai.service_data:
            return jsonify({
                "ok": False,
                "error": "No predictions available. Please collect data first.",
                "action": "POST /api/cross-service-ai/predictions/generate"
            }), 404
        
        logger.info(f"Generating business predictions (type: {prediction_type})")
        
        # Run async prediction generation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            predictions = loop.run_until_complete(cross_service_ai.predict_business_trends())
        finally:
            loop.close()
        
        # Filter by type if specified
        if prediction_type:
            prediction_type = prediction_type.lower()
            predictions = [p for p in predictions if prediction_type in p.prediction_type.lower()]
        
        # Limit results
        predictions = predictions[:limit]
        
        # Format predictions
        formatted_predictions = []
        for prediction in predictions:
            formatted_predictions.append({
                "prediction_id": prediction.prediction_id,
                "prediction_type": prediction.prediction_type,
                "title": prediction.title,
                "prediction": prediction.prediction,
                "confidence_interval": {
                    "lower": prediction.confidence_interval[0],
                    "upper": prediction.confidence_interval[1]
                },
                "influencing_factors": prediction.influencing_factors,
                "business_impact": prediction.business_impact,
                "timeline": prediction.timeline,
                "generated_at": prediction.generated_at.isoformat(),
                "services_involved": [s.value for s in prediction.services_involved]
            })
        
        return jsonify({
            "ok": True,
            "data": {
                "predictions": formatted_predictions,
                "total_predictions": len(formatted_predictions),
                "by_type": {
                    "workload": len([p for p in formatted_predictions if "workload" in p["prediction_type"]]),
                    "financial": len([p for p in formatted_predictions if "financial" in p["prediction_type"]]),
                    "customer_behavior": len([p for p in formatted_predictions if "customer" in p["prediction_type"]])
                },
                "data_points_analyzed": len(cross_service_ai.service_data)
            },
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get business predictions: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@router.route("/predictions/generate", methods=["POST"])
@require_integration_auth
def generate_business_predictions():
    """Generate new business predictions"""
    try:
        data = request.get_json()
        force = data.get('force', False)
        
        # Parse access tokens
        service_tokens = {}
        for service_name, token in request.access_tokens.items():
            if service_name in IntegrationType.__members__:
                service_tokens[IntegrationType[service_name]] = token
        
        logger.info(f"Generating business predictions with {len(service_tokens)} services")
        
        # Run async prediction generation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # First collect data
            if force or not cross_service_ai.service_data:
                loop.run_until_complete(cross_service_ai.collect_all_service_data(service_tokens, limit=15))
            
            # Generate predictions
            predictions = loop.run_until_complete(cross_service_ai.predict_business_trends())
        finally:
            loop.close()
        
        # Format predictions
        formatted_predictions = []
        for prediction in predictions:
            formatted_predictions.append({
                "prediction_id": prediction.prediction_id,
                "prediction_type": prediction.prediction_type,
                "title": prediction.title,
                "prediction": prediction.prediction,
                "confidence_interval": {
                    "lower": prediction.confidence_interval[0],
                    "upper": prediction.confidence_interval[1]
                },
                "influencing_factors": prediction.influencing_factors,
                "business_impact": prediction.business_impact,
                "timeline": prediction.timeline,
                "generated_at": prediction.generated_at.isoformat(),
                "services_involved": [s.value for s in prediction.services_involved]
            })
        
        return jsonify({
            "ok": True,
            "data": {
                "predictions": formatted_predictions,
                "total_generated": len(formatted_predictions),
                "data_points_analyzed": len(cross_service_ai.service_data),
                "generation_time": datetime.utcnow().isoformat()
            },
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Generated {len(formatted_predictions)} business predictions"
        })
        
    except Exception as e:
        logger.error(f"Failed to generate business predictions: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Chat AI endpoints
@router.route("/chat", methods=["POST"])
def chat_with_ai():
    """Chat with ATOM AI assistant"""
    try:
        if not request.is_json:
            return jsonify({
                "ok": False,
                "error": "JSON request body required"
            }), 400
        
        data = request.get_json()
        query = data.get('query')
        user_id = data.get('user_id')
        conversation_id = data.get('conversation_id')
        
        if not query:
            return jsonify({
                "ok": False,
                "error": "Query parameter is required"
            }), 400
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User ID parameter is required"
            }), 400
        
        # Parse access tokens from request
        access_tokens = {}
        for service in IntegrationType:
            token = data.get(f'{service.value}_token')
            if token:
                access_tokens[service.value] = token
        
        logger.info(f"Processing chat query for user {user_id} (conversation: {conversation_id})")
        
        # Run async chat processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            response = loop.run_until_complete(
                chat_ai_service.process_query(query, user_id, conversation_id, access_tokens)
            )
        finally:
            loop.close()
        
        return jsonify({
            "ok": True,
            "data": {
                "response_id": response.response_id,
                "message": response.message,
                "response_type": response.response_type,
                "confidence": response.confidence,
                "data": response.data,
                "actions": response.actions,
                "follow_up_questions": response.follow_up_questions,
                "timestamp": response.timestamp.isoformat(),
                "conversation_id": conversation_id
            },
            "service": "atom_chat_ai",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to process chat query: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "atom_chat_ai",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@router.route("/chat/context", methods=["GET"])
def get_chat_context():
    """Get conversation context"""
    try:
        conversation_id = request.args.get('conversation_id')
        
        if not conversation_id:
            return jsonify({
                "ok": False,
                "error": "conversation_id parameter is required"
            }), 400
        
        context = chat_ai_service.get_conversation_context(conversation_id)
        
        if not context:
            return jsonify({
                "ok": False,
                "error": "Conversation not found"
            }), 404
        
        return jsonify({
            "ok": True,
            "data": {
                "conversation_id": context.conversation_id,
                "user_id": context.user_id,
                "message_count": len(context.messages),
                "last_query_time": context.last_query_time.isoformat(),
                "active_services": [s.value for s in context.active_services],
                "preferences": context.preferences,
                "recent_messages": context.messages[-10:] if len(context.messages) > 10 else context.messages
            },
            "service": "atom_chat_ai",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get chat context: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "atom_chat_ai",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Health and capabilities endpoints
@router.route("/health", methods=["GET"])
def health_check():
    """Cross-service AI service health check"""
    try:
        service_capabilities = cross_service_ai.get_service_capabilities()
        
        return jsonify({
            "ok": True,
            "data": {
                "service": "cross_service_ai",
                "status": "healthy",
                "capabilities": service_capabilities,
                "data_collected": len(cross_service_ai.service_data),
                "insights_available": len(cross_service_ai.insights),
                "workflows_available": len(cross_service_ai.workflows),
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Cross-service AI health check failed: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@router.route("/capabilities", methods=["GET"])
def get_capabilities():
    """Get cross-service AI capabilities"""
    try:
        service_capabilities = cross_service_ai.get_service_capabilities()
        
        return jsonify({
            "ok": True,
            "data": service_capabilities,
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get capabilities: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@router.route("/dashboard", methods=["GET"])
def get_dashboard_data():
    """Get dashboard summary data"""
    try:
        # Collect basic statistics
        data_count = len(cross_service_ai.service_data)
        insights_count = len(cross_service_ai.insights)
        workflows_count = len(cross_service_ai.workflows)
        
        # Service breakdown
        service_breakdown = {}
        for data in cross_service_ai.service_data:
            service = data.service_type.value
            if service not in service_breakdown:
                service_breakdown[service] = 0
            service_breakdown[service] += 1
        
        # Insight breakdown
        insight_breakdown = {}
        for insight in cross_service_ai.insights:
            insight_type = insight.insight_type
            if insight_type not in insight_breakdown:
                insight_breakdown[insight_type] = 0
            insight_breakdown[insight_type] += 1
        
        # Workflow breakdown
        workflow_breakdown = {"high": 0, "medium": 0, "low": 0}
        for workflow in cross_service_ai.workflows:
            workflow_breakdown[workflow.priority] += 1
        
        return jsonify({
            "ok": True,
            "data": {
                "summary": {
                    "total_data_points": data_count,
                    "active_insights": insights_count,
                    "workflow_recommendations": workflows_count,
                    "connected_services": list(service_breakdown.keys())
                },
                "service_breakdown": service_breakdown,
                "insight_breakdown": insight_breakdown,
                "workflow_priorities": workflow_breakdown,
                "last_updated": datetime.utcnow().isoformat()
            },
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get dashboard data: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "cross_service_ai",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Export blueprint
def register_cross_service_ai_routes(app):
    """Register cross-service AI API routes"""
    app.register_blueprint(router)
    logger.info("Cross-Service AI API routes registered")

if __name__ == "__main__":
    # Test the blueprint
    app = Flask(__name__)
    register_cross_service_ai_routes(app)
    app.run(debug=True, port=8002)