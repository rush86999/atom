"""
ATOM Advanced AI Models API Routes
Flask routes for advanced AI model integration, orchestration, and streaming
Following ATOM API patterns and conventions
"""

from flask import Blueprint, request, jsonify, Response
from flask.helpers import stream_with_context
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
import asyncio
import traceback
import json
import uuid

# Advanced AI Services
from advanced_ai_models_service import (
    create_advanced_ai_models_service,
    AIModelType,
    AIRequest,
    AIResponse,
    AIInsight,
    ModelCapability,
    ProcessingPriority
)
from multi_model_ai_orchestration_service import (
    create_multi_model_ai_orchestration_service,
    OrchestrationRequest,
    OrchestrationResponse,
    RoutingStrategy,
    EnsembleMethod
)
from real_time_ai_streaming_service import (
    create_real_time_ai_streaming_service,
    StreamingEventType
)

# Create blueprint
router = Blueprint('advanced_ai_models', __name__, url_prefix='/api/advanced-ai')

# Global instances
advanced_ai_service = create_advanced_ai_models_service()
orchestration_service = create_multi_model_ai_orchestration_service()
streaming_service = None

# Decorator for requiring AI API access
def require_ai_access(f):
    def decorated_function(*args, **kwargs):
        try:
            # Check API key or session
            api_key = request.headers.get('X-API-Key')
            if not api_key:
                # Check for session-based access
                if not hasattr(request, 'user_id') or not request.user_id:
                    return jsonify({
                        "ok": False,
                        "error": "API key or valid session required"
                    }), 401
            
            # Store in Flask's request context for route to use
            request.api_access = True
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"AI access decorator error: {e}")
            return jsonify({
                "ok": False,
                "error": f"Authentication failed: {str(e)}"
            }), 500
    
    return decorated_function

# Model management endpoints
@router.route("/models", methods=["GET"])
@require_ai_access
def get_available_models():
    """Get available AI models and capabilities"""
    try:
        capability_filter = request.args.get('capability')
        
        if capability_filter:
            try:
                cap = ModelCapability(capability_filter)
                models = advanced_ai_service.get_available_models(cap)
            except ValueError:
                return jsonify({
                    "ok": False,
                    "error": f"Invalid capability: {capability_filter}"
                }), 400
        else:
            models = advanced_ai_service.get_available_models()
        
        # Format model information
        model_info = []
        for config in models:
            model_info.append({
                "model_type": config.model_type.value,
                "model_name": config.model_name,
                "provider": config.provider,
                "capabilities": [c.value for c in config.capabilities],
                "max_tokens": config.max_tokens,
                "context_window": config.context_window,
                "quality_score": config.quality_score,
                "cost_per_token": config.cost_per_token,
                "speed": config.speed,
                "requires_api": config.requires_api
            })
        
        return jsonify({
            "ok": True,
            "data": {
                "models": model_info,
                "total_models": len(model_info),
                "capability_filter": capability_filter,
                "generated_at": datetime.utcnow().isoformat()
            },
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get available models: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@router.route("/models/capabilities", methods=["GET"])
@require_ai_access
def get_model_capabilities():
    """Get comprehensive model capabilities"""
    try:
        capabilities = advanced_ai_service.get_model_capabilities()
        
        return jsonify({
            "ok": True,
            "data": capabilities,
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get model capabilities: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# AI request processing endpoints
@router.route("/process", methods=["POST"])
@require_ai_access
def process_ai_request():
    """Process AI request with specified model"""
    try:
        if not request.is_json:
            return jsonify({
                "ok": False,
                "error": "JSON request body required"
            }), 400
        
        data = request.get_json()
        model_type = data.get('model_type')
        prompt = data.get('prompt')
        context = data.get('context')
        priority = data.get('priority', ProcessingPriority.NORMAL.value)
        max_tokens = data.get('max_tokens')
        temperature = data.get('temperature')
        stream = data.get('stream', False)
        
        if not prompt:
            return jsonify({
                "ok": False,
                "error": "Prompt is required"
            }), 400
        
        if not model_type:
            return jsonify({
                "ok": False,
                "error": "Model type is required"
            }), 400
        
        try:
            model_type = AIModelType(model_type)
        except ValueError:
            return jsonify({
                "ok": False,
                "error": f"Invalid model type: {model_type}"
            }), 400
        
        # Create AI request
        ai_request = AIRequest(
            request_id=str(uuid.uuid4()),
            model_type=model_type,
            prompt=prompt,
            context=context,
            priority=ProcessingPriority(priority),
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream,
            metadata={"api_request": True}
        )
        
        logger.info(f"Processing AI request with model {model_type}")
        
        if stream:
            # Handle streaming response
            return Response(
                stream_with_context(generate_streaming_response(ai_request)),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'Access-Control-Allow-Origin': '*'
                }
            )
        else:
            # Process normally
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                response = loop.run_until_complete(
                    advanced_ai_service.process_request(ai_request)
                )
            finally:
                loop.close()
            
            # Format response
            return jsonify({
                "ok": True,
                "data": {
                    "request_id": response.request_id,
                    "model_type": response.model_type.value,
                    "response": response.response,
                    "confidence": response.confidence,
                    "token_usage": response.token_usage,
                    "processing_time": response.processing_time,
                    "cost": response.cost,
                    "metadata": response.metadata
                },
                "service": "advanced_ai_models",
                "timestamp": datetime.utcnow().isoformat()
            })
        
    except Exception as e:
        logger.error(f"Failed to process AI request: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

async def generate_streaming_response(ai_request):
    """Generate streaming AI response"""
    try:
        # Create a streaming response generator
        async for chunk in advanced_ai_service.process_streaming_request(ai_request):
            chunk_data = json.dumps({
                'type': 'chunk',
                'content': chunk.content,
                'confidence': chunk.confidence,
                'is_complete': chunk.is_complete,
                'timestamp': chunk.timestamp.isoformat()
            })
            yield f"data: {chunk_data}\n\n"
            
            if chunk.is_complete:
                break
        
        yield "data: {\"type\": \"complete\"}\n\n"
        
    except Exception as e:
        logger.error(f"Streaming response error: {e}")
        error_data = json.dumps({'type': 'error', 'error': str(e)})
        yield f"data: {error_data}\n\n"

# Orchestration endpoints
@router.route("/orchestrate", methods=["POST"])
@require_ai_access
def process_orchestration_request():
    """Process multi-model orchestration request"""
    try:
        if not request.is_json:
            return jsonify({
                "ok": False,
                "error": "JSON request body required"
            }), 400
        
        data = request.get_json()
        prompt = data.get('prompt')
        context = data.get('context')
        routing_strategy = data.get('routing_strategy', RoutingStrategy.QUALITY_FIRST.value)
        ensemble_method = data.get('ensemble_method')
        max_models = data.get('max_models', 1)
        required_capabilities = data.get('required_capabilities', [])
        budget_limit = data.get('budget_limit')
        timeout = data.get('timeout')
        priority = data.get('priority', ProcessingPriority.NORMAL.value)
        
        if not prompt:
            return jsonify({
                "ok": False,
                "error": "Prompt is required"
            }), 400
        
        try:
            routing_strategy = RoutingStrategy(routing_strategy)
        except ValueError:
            return jsonify({
                "ok": False,
                "error": f"Invalid routing strategy: {routing_strategy}"
            }), 400
        
        if ensemble_method:
            try:
                ensemble_method = EnsembleMethod(ensemble_method)
            except ValueError:
                return jsonify({
                    "ok": False,
                    "error": f"Invalid ensemble method: {ensemble_method}"
                }), 400
        
        # Convert required capabilities
        caps = []
        for cap in required_capabilities:
            try:
                caps.append(ModelCapability(cap))
            except ValueError:
                return jsonify({
                    "ok": False,
                    "error": f"Invalid capability: {cap}"
                }), 400
        
        # Create orchestration request
        orch_request = OrchestrationRequest(
            request_id=str(uuid.uuid4()),
            prompt=prompt,
            context=context,
            routing_strategy=routing_strategy,
            ensemble_method=ensemble_method,
            max_models=max_models,
            required_capabilities=caps,
            budget_limit=budget_limit,
            timeout=timeout,
            priority=ProcessingPriority(priority),
            metadata={"api_request": True}
        )
        
        logger.info(f"Processing orchestration request with strategy {routing_strategy}")
        
        # Process request
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            response = loop.run_until_complete(
                orchestration_service.process_request(orch_request)
            )
        finally:
            loop.close()
        
        # Format response
        response_data = {
            "request_id": response.request_id,
            "responses": [],
            "selected_model": response.selected_model.value if response.selected_model else None,
            "ensemble_result": response.ensemble_result,
            "ensemble_confidence": response.ensemble_confidence,
            "routing_explanation": response.routing_explanation,
            "total_cost": response.total_cost,
            "total_time": response.total_time,
            "success": response.success
        }
        
        for resp in response.responses:
            response_data["responses"].append({
                "request_id": resp.request_id,
                "model_type": resp.model_type.value,
                "response": resp.response,
                "confidence": resp.confidence,
                "token_usage": resp.token_usage,
                "processing_time": resp.processing_time,
                "cost": resp.cost
            })
        
        return jsonify({
            "ok": True,
            "data": response_data,
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to process orchestration request: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@router.route("/orchestration/performance", methods=["GET"])
@require_ai_access
def get_orchestration_performance():
    """Get orchestration performance metrics"""
    try:
        metrics = orchestration_service.get_performance_metrics()
        
        return jsonify({
            "ok": True,
            "data": metrics,
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get orchestration performance: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@router.route("/orchestration/recommendations", methods=["POST"])
@require_ai_access
def get_model_recommendations():
    """Get model recommendations for specific context"""
    try:
        if not request.is_json:
            return jsonify({
                "ok": False,
                "error": "JSON request body required"
            }), 400
        
        data = request.get_json()
        request_context = data.get('context', {})
        
        recommendations = orchestration_service.get_model_recommendations(request_context)
        
        # Format recommendations
        formatted_recs = []
        for rec in recommendations:
            formatted_recs.append({
                "selected_models": [m.value for m in rec.selected_models],
                "selection_reason": rec.selection_reason,
                "confidence": rec.confidence,
                "cost_estimate": rec.cost_estimate,
                "time_estimate": rec.time_estimate,
                "fallback_options": [m.value for m in rec.fallback_options]
            })
        
        return jsonify({
            "ok": True,
            "data": {
                "recommendations": formatted_recs,
                "context": request_context,
                "total_recommendations": len(formatted_recs)
            },
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get model recommendations: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Advanced insights endpoints
@router.route("/insights/generate", methods=["POST"])
@require_ai_access
def generate_advanced_insights():
    """Generate advanced AI insights"""
    try:
        if not request.is_json:
            return jsonify({
                "ok": False,
                "error": "JSON request body required"
            }), 400
        
        data = request.get_json()
        data_context = data.get('context', {})
        insight_types = data.get('insight_types')
        
        logger.info(f"Generating advanced insights for {len(data_context)} data points")
        
        # Generate insights
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            insights = loop.run_until_complete(
                advanced_ai_service.generate_advanced_insights(data_context, insight_types)
            )
        finally:
            loop.close()
        
        # Format insights
        formatted_insights = []
        for insight in insights:
            formatted_insights.append({
                "insight_id": insight.insight_id,
                "model_type": insight.model_type.value,
                "insight_type": insight.insight_type,
                "title": insight.title,
                "description": insight.description,
                "analysis": insight.analysis,
                "confidence": insight.confidence,
                "business_impact": insight.business_impact,
                "action_items": insight.action_items,
                "predictions": insight.predictions,
                "reasoning": insight.reasoning,
                "data_sources": insight.data_sources,
                "generated_at": insight.generated_at.isoformat(),
                "processing_time": insight.processing_time,
                "cost": insight.cost
            })
        
        return jsonify({
            "ok": True,
            "data": {
                "insights": formatted_insights,
                "total_insights": len(formatted_insights),
                "context_data_points": len(data_context),
                "generation_time": datetime.utcnow().isoformat()
            },
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to generate advanced insights: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Streaming endpoints
@router.route("/streaming/status", methods=["GET"])
@require_ai_access
def get_streaming_status():
    """Get streaming service status"""
    try:
        global streaming_service
        if not streaming_service:
            streaming_service = create_real_time_ai_streaming_service()
        
        status = streaming_service.get_streaming_status()
        
        return jsonify({
            "ok": True,
            "data": status,
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get streaming status: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@router.route("/streaming/events", methods=["POST"])
@require_ai_access
def create_streaming_event():
    """Create and broadcast streaming event"""
    try:
        if not request.is_json:
            return jsonify({
                "ok": False,
                "error": "JSON request body required"
            }), 400
        
        data = request.get_json()
        event_type = data.get('event_type')
        event_data = data.get('data')
        priority = data.get('priority', ProcessingPriority.NORMAL.value)
        target_clients = data.get('target_clients')
        
        if not event_type or not event_data:
            return jsonify({
                "ok": False,
                "error": "Event type and data are required"
            }), 400
        
        try:
            event_type = StreamingEventType(event_type)
        except ValueError:
            return jsonify({
                "ok": False,
                "error": f"Invalid event type: {event_type}"
            }), 400
        
        global streaming_service
        if not streaming_service:
            streaming_service = create_real_time_ai_streaming_service()
        
        # Create and broadcast event
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(
                streaming_service._broadcast_event(event_type, event_data)
            )
        finally:
            loop.close()
        
        return jsonify({
            "ok": True,
            "data": {
                "event_type": event_type.value,
                "broadcast": True,
                "timestamp": datetime.utcnow().isoformat()
            },
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to create streaming event: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Performance and metrics endpoints
@router.route("/performance", methods=["GET"])
@require_ai_access
def get_performance_metrics():
    """Get AI model performance metrics"""
    try:
        metrics = advanced_ai_service.get_performance_metrics()
        
        return jsonify({
            "ok": True,
            "data": metrics,
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@router.route("/health", methods=["GET"])
def health_check():
    """Advanced AI models service health check"""
    try:
        capabilities = advanced_ai_service.get_model_capabilities()
        orchestration_status = orchestration_service.get_orchestration_status()
        
        # Check streaming service
        streaming_status = {"status": "not_initialized"}
        global streaming_service
        if streaming_service:
            streaming_status = streaming_service.get_streaming_status()
        
        return jsonify({
            "ok": True,
            "data": {
                "service": "advanced_ai_models",
                "status": "healthy",
                "models": {
                    "total_models": capabilities["total_models"],
                    "api_models": capabilities["api_models"],
                    "local_models": capabilities["local_models"],
                    "available_models": len(capabilities["available_models"])
                },
                "orchestration": orchestration_status,
                "streaming": streaming_status,
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Advanced AI models health check failed: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@router.route("/dashboard", methods=["GET"])
def get_dashboard_data():
    """Get dashboard summary data"""
    try:
        # Get performance metrics
        model_metrics = advanced_ai_service.get_performance_metrics()
        orch_metrics = orchestration_service.get_performance_metrics()
        
        # Get model capabilities
        capabilities = advanced_ai_service.get_model_capabilities()
        
        # Streaming status
        streaming_status = {"status": "not_initialized"}
        global streaming_service
        if streaming_service:
            streaming_status = streaming_service.get_streaming_status()
        
        # Calculate summary statistics
        total_requests = model_metrics.get("total_requests", 0) + orch_metrics.get("total_requests", 0)
        total_cost = model_metrics.get("total_cost", 0) + orch_metrics.get("total_cost", 0)
        average_processing_time = orch_metrics.get("average_response_time", 0)
        
        # Model breakdown
        model_breakdown = {}
        for model_info in capabilities.get("available_models", []):
            provider = model_info["provider"]
            if provider not in model_breakdown:
                model_breakdown[provider] = 0
            model_breakdown[provider] += 1
        
        return jsonify({
            "ok": True,
            "data": {
                "summary": {
                    "total_models": capabilities.get("total_models", 0),
                    "total_requests": total_requests,
                    "total_cost": total_cost,
                    "average_processing_time": average_processing_time,
                    "streaming_connections": streaming_status.get("active_connections", 0)
                },
                "model_breakdown": model_breakdown,
                "performance": {
                    "model_performance": model_metrics.get("models", {}),
                    "orchestration_performance": orch_metrics.get("models", {}),
                    "overall_success_rate": orch_metrics.get("overall_success_rate", 0)
                },
                "streaming": streaming_status,
                "last_updated": datetime.utcnow().isoformat()
            },
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get dashboard data: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "advanced_ai_models",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Export blueprint
def register_advanced_ai_models_routes(app):
    """Register advanced AI models API routes"""
    app.register_blueprint(router)
    logger.info("Advanced AI Models API routes registered")

if __name__ == "__main__":
    # Test the blueprint
    app = Flask(__name__)
    register_advanced_ai_models_routes(app)
    app.run(debug=True, port=8003)