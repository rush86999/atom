"""
ATOM Multi-Model AI Orchestration Service
Advanced AI model orchestration with intelligent routing, model selection, and ensemble responses
"""

import os
import json
import asyncio
import aiohttp
import hashlib
import uuid
from typing import Dict, List, Optional, Any, Tuple, Union, Set
from datetime import datetime, timedelta, date
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
from loguru import logger
from collections import defaultdict, deque

# Advanced AI Models
from advanced_ai_models_service import (
    create_advanced_ai_models_service,
    AIModelType,
    AIRequest,
    AIResponse,
    AIInsight,
    ModelCapability,
    ProcessingPriority
)

# Existing Services
try:
    from cross_service_ai_service import create_cross_service_ai_service, IntegrationType
except ImportError:
    create_cross_service_ai_service = None
    IntegrationType = None

class RoutingStrategy(Enum):
    """AI model routing strategies"""
    ROUND_ROBIN = "round_robin"
    QUALITY_FIRST = "quality_first"
    COST_FIRST = "cost_first"
    SPEED_FIRST = "speed_first"
    CAPABILITY_BASED = "capability_based"
    ENSEMBLE = "ensemble"

class EnsembleMethod(Enum):
    """Ensemble combination methods"""
    MAJORITY_VOTE = "majority_vote"
    WEIGHTED_AVERAGE = "weighted_average"
    CONFIDENCE_WEIGHTED = "confidence_weighted"
    BEST_OF_N = "best_of_n"
    CONSENSUS = "consensus"

@dataclass
class ModelPerformance:
    """Model performance metrics"""
    model_type: AIModelType
    total_requests: int
    successful_requests: int
    average_response_time: float
    average_confidence: float
    total_cost: float
    error_rate: float
    quality_score: float
    last_updated: datetime
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.utcnow()

@dataclass
class OrchestrationRequest:
    """AI orchestration request"""
    request_id: str
    prompt: str
    context: Optional[Dict[str, Any]] = None
    routing_strategy: RoutingStrategy = RoutingStrategy.QUALITY_FIRST
    ensemble_method: Optional[EnsembleMethod] = None
    max_models: int = 1
    required_capabilities: List[ModelCapability] = None
    budget_limit: Optional[float] = None
    timeout: Optional[float] = None
    priority: ProcessingPriority = ProcessingPriority.NORMAL
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.required_capabilities is None:
            self.required_capabilities = []
        if self.metadata is None:
            self.metadata = {}

@dataclass
class OrchestrationResponse:
    """AI orchestration response"""
    request_id: str
    responses: List[AIResponse]
    selected_model: Optional[AIModelType] = None
    ensemble_result: Optional[str] = None
    ensemble_confidence: Optional[float] = None
    routing_explanation: str = ""
    total_cost: float = 0.0
    total_time: float = 0.0
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class ModelSelection:
    """Model selection result"""
    selected_models: List[AIModelType]
    selection_reason: str
    confidence: float
    cost_estimate: float
    time_estimate: float
    fallback_options: List[AIModelType]

class MultiModelAIOrchestrationService:
    """Multi-model AI orchestration service with intelligent routing"""
    
    def __init__(self):
        # AI services
        self.advanced_ai = create_advanced_ai_models_service()
        self.cross_service_ai = None
        if create_cross_service_ai_service:
            self.cross_service_ai = create_cross_service_ai_service()
        
        # Model performance tracking
        self.performance_metrics = {}  # AIModelType -> ModelPerformance
        self.routing_counters = defaultdict(int)
        
        # Request queues and processing
        self.request_queue = asyncio.Queue()
        self.active_requests = {}  # request_id -> OrchestrationRequest
        self.request_history = deque(maxlen=1000)
        
        # Model routing configuration
        self.routing_strategies = {
            RoutingStrategy.ROUND_ROBIN: self._route_round_robin,
            RoutingStrategy.QUALITY_FIRST: self._route_quality_first,
            RoutingStrategy.COST_FIRST: self._route_cost_first,
            RoutingStrategy.SPEED_FIRST: self._route_speed_first,
            RoutingStrategy.CAPABILITY_BASED: self._route_capability_based,
            RoutingStrategy.ENSEMBLE: self._route_ensemble
        }
        
        # Round robin state
        self.round_robin_index = 0
        self.available_models = []
        
        # Ensemble configuration
        self.ensemble_weights = {}  # model_type -> weight
        self.confidence_threshold = 0.7
        
        # Performance optimization
        self.model_caches = {}
        self.response_cache = {}
        
        # Initialize model performance
        self._initialize_performance_metrics()
        
        # Start background processor
        # self._start_background_processor()
        
        logger.info("Multi-Model AI Orchestration Service initialized")
    
    def _initialize_performance_metrics(self):
        """Initialize performance metrics for all models"""
        capabilities = self.advanced_ai.get_model_capabilities()
        
        # Extract model configurations from capabilities
        model_configs = {}
        for model_info in capabilities.get("available_models", []):
            model_type = AIModelType(model_info["model_type"])
            # Create a simple config object
            model_configs[model_type] = type('Config', (), {
                'model_type': model_type,
                'model_name': model_info["model_name"],
                'quality_score': model_info["quality_score"],
                'cost_per_token': model_info["cost_per_token"],
                'speed': model_info["speed"],
                'capabilities': model_info["capabilities"]
            })()
        
        for model_type, config in model_configs.items():
            self.performance_metrics[model_type] = ModelPerformance(
                model_type=model_type,
                total_requests=0,
                successful_requests=0,
                average_response_time=config.speed,
                average_confidence=config.quality_score,
                total_cost=0.0,
                error_rate=0.0,
                quality_score=config.quality_score,
                last_updated=datetime.utcnow()
            )
            
            self.available_models.append(model_type)
        
        # Initialize ensemble weights based on quality scores
        total_quality = sum(config.quality_score for config in model_configs.values())
        for model_type, config in model_configs.items():
            self.ensemble_weights[model_type] = config.quality_score / total_quality if total_quality > 0 else 0.33
        
        logger.info(f"Initialized performance metrics for {len(self.available_models)} models")
    
    def _start_background_processor(self):
        """Start background request processor"""
        asyncio.create_task(self._process_requests_loop())
        asyncio.create_task(self._update_performance_metrics_loop())
        asyncio.create_task(self._cleanup_cache_loop())
    
    async def process_request(self, request: OrchestrationRequest) -> OrchestrationResponse:
        """Process orchestration request"""
        try:
            logger.info(f"Processing orchestration request {request.request_id} with strategy {request.routing_strategy}")
            
            # Add to active requests
            self.active_requests[request.request_id] = request
            
            # Select models
            model_selection = await self._select_models(request)
            
            # Execute requests
            responses = []
            if request.ensemble_method and len(model_selection.selected_models) > 1:
                # Ensemble processing
                responses = await self._process_ensemble_request(request, model_selection)
            else:
                # Single model processing
                primary_model = model_selection.selected_models[0]
                ai_request = AIRequest(
                    request_id=request.request_id,
                    model_type=primary_model,
                    prompt=request.prompt,
                    context=request.context,
                    priority=request.priority
                )
                
                response = await self.advanced_ai.process_request(ai_request)
                responses.append(response)
                model_selection.selected_models = [primary_model]
            
            # Create orchestration response
            orchestration_response = OrchestrationResponse(
                request_id=request.request_id,
                responses=responses,
                selected_model=model_selection.selected_models[0] if len(model_selection.selected_models) == 1 else None,
                ensemble_result=self._create_ensemble_result(responses, request.ensemble_method) if len(responses) > 1 else None,
                ensemble_confidence=self._calculate_ensemble_confidence(responses) if len(responses) > 1 else None,
                routing_explanation=model_selection.selection_reason,
                total_cost=sum(r.cost for r in responses),
                total_time=max(r.processing_time for r in responses),
                success=True
            )
            
            # Update performance metrics
            self._update_request_metrics(model_selection, responses)
            
            # Add to history
            self.request_history.append({
                "request_id": request.request_id,
                "timestamp": datetime.utcnow(),
                "strategy": request.routing_strategy,
                "models_used": model_selection.selected_models,
                "success": True,
                "cost": orchestration_response.total_cost,
                "time": orchestration_response.total_time
            })
            
            # Remove from active requests
            del self.active_requests[request.request_id]
            
            logger.info(f"Completed orchestration request {request.request_id} using {len(responses)} models")
            return orchestration_response
            
        except Exception as e:
            logger.error(f"Failed to process orchestration request {request.request_id}: {e}")
            
            # Remove from active requests
            if request.request_id in self.active_requests:
                del self.active_requests[request.request_id]
            
            # Create error response
            error_response = OrchestrationResponse(
                request_id=request.request_id,
                responses=[],
                success=False,
                error_message=str(e),
                total_time=0.0,
                total_cost=0.0
            )
            
            return error_response
    
    async def _select_models(self, request: OrchestrationRequest) -> ModelSelection:
        """Select models based on routing strategy"""
        try:
            routing_function = self.routing_strategies.get(request.routing_strategy)
            if not routing_function:
                routing_function = self._route_quality_first
            
            # Filter models by required capabilities
            available_models = self.available_models
            if request.required_capabilities:
                available_models = self._filter_models_by_capabilities(
                    available_models, request.required_capabilities
                )
            
            # Apply routing strategy
            selected_models = await routing_function(request, available_models)
            
            # Apply budget limit
            if request.budget_limit:
                selected_models = self._apply_budget_limit(selected_models, request.budget_limit)
            
            # Limit to max_models
            selected_models = selected_models[:request.max_models]
            
            return ModelSelection(
                selected_models=selected_models,
                selection_reason=f"Selected using {request.routing_strategy.value} strategy",
                confidence=0.8,
                cost_estimate=0.0,
                time_estimate=0.0,
                fallback_options=self.available_models[:3]
            )
            
        except Exception as e:
            logger.error(f"Error in model selection: {e}")
            # Fallback to quality-first
            return await self._route_quality_first(request, self.available_models[:1])
    
    async def _route_round_robin(self, request: OrchestrationRequest, available_models: List[AIModelType]) -> List[AIModelType]:
        """Round robin routing"""
        if not available_models:
            return []
        
        # Get next model
        model = available_models[self.round_robin_index % len(available_models)]
        self.round_robin_index += 1
        
        return [model]
    
    async def _route_quality_first(self, request: OrchestrationRequest, available_models: List[AIModelType]) -> List[AIModelType]:
        """Quality-first routing"""
        # Sort by quality score
        model_scores = []
        for model_type in available_models:
            performance = self.performance_metrics.get(model_type)
            if performance:
                model_scores.append((model_type, performance.quality_score))
        
        # Sort by quality descending
        model_scores.sort(key=lambda x: x[1], reverse=True)
        
        return [model_scores[0][0]] if model_scores else []
    
    async def _route_cost_first(self, request: OrchestrationRequest, available_models: List[AIModelType]) -> List[AIModelType]:
        """Cost-first routing"""
        # Sort by cost per token
        capabilities = self.advanced_ai.get_model_capabilities()
        model_costs = []
        for model_type in available_models:
            # Find model info in capabilities
            model_info = None
            for m in capabilities.get("available_models", []):
                if m["model_type"] == model_type.value:
                    model_info = m
                    break
            
            if model_info:
                model_costs.append((model_type, model_info["cost_per_token"]))
        
        # Sort by cost ascending
        model_costs.sort(key=lambda x: x[1])
        
        return [model_type for model_type, _ in model_costs[:1]] if model_costs else []
    
    async def _route_speed_first(self, request: OrchestrationRequest, available_models: List[AIModelType]) -> List[AIModelType]:
        """Speed-first routing"""
        # Sort by response time
        model_speeds = []
        for model_type in available_models:
            performance = self.performance_metrics.get(model_type)
            if performance:
                model_speeds.append((model_type, performance.average_response_time))
        
        # Sort by speed ascending (lower time is faster)
        model_speeds.sort(key=lambda x: x[1])
        
        return [model_speeds[0][0]] if model_speeds else []
    
    async def _route_capability_based(self, request: OrchestrationRequest, available_models: List[AIModelType]) -> List[AIModelType]:
        """Capability-based routing"""
        # Filter models that support required capabilities
        capabilities = self.advanced_ai.get_model_capabilities()
        suitable_models = []
        
        for model_type in available_models:
            # Find model info in capabilities
            model_info = None
            for m in capabilities.get("available_models", []):
                if m["model_type"] == model_type.value:
                    model_info = m
                    break
            
            if model_info:
                # Check if model supports all required capabilities
                model_caps = [ModelCapability(c) for c in model_info["capabilities"]]
                has_all_caps = all(cap in model_caps for cap in request.required_capabilities)
                if has_all_caps:
                    suitable_models.append((model_type, model_info["quality_score"]))
        
        # Sort by quality
        suitable_models.sort(key=lambda x: x[1], reverse=True)
        
        return [model_type for model_type, _ in suitable_models[:request.max_models]]
    
    async def _route_ensemble(self, request: OrchestrationRequest, available_models: List[AIModelType]) -> List[AIModelType]:
        """Ensemble routing"""
        # Select top models based on ensemble weights
        model_weighted = []
        for model_type in available_models:
            weight = self.ensemble_weights.get(model_type, 0.0)
            performance = self.performance_metrics.get(model_type)
            if performance:
                # Combine ensemble weight with performance
                combined_score = (weight + performance.quality_score) / 2
                model_weighted.append((model_type, combined_score))
        
        # Sort by combined score
        model_weighted.sort(key=lambda x: x[1], reverse=True)
        
        # Return top models (up to max_models)
        return [model_type for model_type, _ in model_weighted[:min(request.max_models, 3)]]
    
    async def _process_ensemble_request(self, request: OrchestrationRequest, model_selection: ModelSelection) -> List[AIResponse]:
        """Process ensemble request with multiple models"""
        tasks = []
        
        for model_type in model_selection.selected_models:
            ai_request = AIRequest(
                request_id=f"{request.request_id}_{model_type.value}",
                model_type=model_type,
                prompt=request.prompt,
                context=request.context,
                priority=request.priority
            )
            
            # Create task
            task = asyncio.create_task(self._process_single_ai_request(ai_request))
            tasks.append(task)
        
        # Wait for all tasks with timeout
        if request.timeout:
            responses = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=request.timeout
            )
        else:
            responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful responses
        successful_responses = []
        for response in responses:
            if isinstance(response, AIResponse):
                successful_responses.append(response)
            else:
                logger.error(f"Ensemble request failed: {response}")
        
        return successful_responses
    
    async def _process_single_ai_request(self, request: AIRequest) -> AIResponse:
        """Process single AI request with error handling"""
        try:
            response = await self.advanced_ai.process_request(request)
            return response
        except Exception as e:
            logger.error(f"AI request failed for {request.model_type}: {e}")
            # Return error response
            return AIResponse(
                request_id=request.request_id,
                model_type=request.model_type,
                response="",
                confidence=0.0,
                token_usage={},
                processing_time=0.0,
                cost=0.0
            )
    
    def _create_ensemble_result(self, responses: List[AIResponse], method: Optional[EnsembleMethod]) -> str:
        """Create ensemble result from multiple responses"""
        if not responses:
            return ""
        
        if not method:
            # Default to best response
            best_response = max(responses, key=lambda r: r.confidence)
            return best_response.response
        
        if method == EnsembleMethod.MAJORITY_VOTE:
            # Simple majority voting (for classification-style responses)
            # For text responses, use best confidence
            best_response = max(responses, key=lambda r: r.confidence)
            return best_response.response
        
        elif method == EnsembleMethod.WEIGHTED_AVERAGE:
            # Weighted combination based on model weights
            weighted_text = ""
            total_weight = 0
            
            for response in responses:
                weight = self.ensemble_weights.get(response.model_type, 0.5)
                weighted_text += response.response * weight
                total_weight += weight
            
            return weighted_text / total_weight if total_weight > 0 else weighted_text
        
        elif method == EnsembleMethod.CONFIDENCE_WEIGHTED:
            # Weight by confidence
            weighted_text = ""
            total_confidence = sum(r.confidence for r in responses)
            
            for response in responses:
                if response.confidence > 0:
                    weight = response.confidence / total_confidence
                    weighted_text += response.response * weight
            
            return weighted_text
        
        elif method == EnsembleMethod.BEST_OF_N:
            # Return response with highest confidence
            best_response = max(responses, key=lambda r: r.confidence)
            return best_response.response
        
        elif method == EnsembleMethod.CONSENSUS:
            # Find common patterns and create consensus
            # Simplified: return longest response with highest confidence
            best_response = max(responses, key=lambda r: (r.confidence, len(r.response)))
            return best_response.response
        
        # Default
        return responses[0].response
    
    def _calculate_ensemble_confidence(self, responses: List[AIResponse]) -> float:
        """Calculate ensemble confidence"""
        if not responses:
            return 0.0
        
        # Weighted average of confidences
        total_confidence = 0.0
        total_weight = 0.0
        
        for response in responses:
            weight = self.ensemble_weights.get(response.model_type, 0.5)
            total_confidence += response.confidence * weight
            total_weight += weight
        
        return total_confidence / total_weight if total_weight > 0 else 0.0
    
    def _filter_models_by_capabilities(self, models: List[AIModelType], capabilities: List[ModelCapability]) -> List[AIModelType]:
        """Filter models by required capabilities"""
        suitable_models = []
        
        for model_type in models:
            config = self.advanced_ai.get_model_config(model_type)
            if config:
                # Check if model supports all required capabilities
                has_all_caps = all(cap in config.capabilities for cap in capabilities)
                if has_all_caps:
                    suitable_models.append(model_type)
        
        return suitable_models
    
    def _apply_budget_limit(self, models: List[AIModelType], budget_limit: float) -> List[AIModelType]:
        """Apply budget limit to model selection"""
        capabilities = self.advanced_ai.get_model_capabilities()
        affordable_models = []
        
        for model_type in models:
            # Find model info in capabilities
            model_info = None
            for m in capabilities.get("available_models", []):
                if m["model_type"] == model_type.value:
                    model_info = m
                    break
            
            if model_info and model_info["cost_per_token"] <= budget_limit:
                affordable_models.append(model_type)
        
        return affordable_models if affordable_models else models[:1]  # At least one model
    
    def _update_request_metrics(self, model_selection: ModelSelection, responses: List[AIResponse]):
        """Update performance metrics"""
        for response in responses:
            model_type = response.model_type
            performance = self.performance_metrics.get(model_type)
            
            if performance:
                # Update metrics
                performance.total_requests += 1
                if response.confidence > 0:
                    performance.successful_requests += 1
                
                # Update averages
                total_requests = performance.total_requests
                performance.average_response_time = (
                    (performance.average_response_time * (total_requests - 1) + response.processing_time) / total_requests
                )
                performance.average_confidence = (
                    (performance.average_confidence * (total_requests - 1) + response.confidence) / total_requests
                )
                
                performance.total_cost += response.cost
                performance.error_rate = 1.0 - (performance.successful_requests / total_requests)
                performance.last_updated = datetime.utcnow()
                
                # Update quality score based on confidence and success
                performance.quality_score = performance.average_confidence * (1.0 - performance.error_rate)
        
        # Update routing counters
        for model_type in model_selection.selected_models:
            self.routing_counters[model_type] += 1
    
    async def _process_requests_loop(self):
        """Process requests from queue"""
        try:
            while True:
                # Get request from queue
                request = await self.request_queue.get()
                
                # Process request
                response = await self.process_request(request)
                
                # Send response (in production, would send to callback or WebSocket)
                logger.info(f"Processed orchestration request {request.request_id}")
                
        except Exception as e:
            logger.error(f"Error in request processing loop: {e}")
    
    async def _update_performance_metrics_loop(self):
        """Update performance metrics periodically"""
        try:
            while True:
                await asyncio.sleep(300)  # Update every 5 minutes
                
                # Calculate recent performance
                current_time = datetime.utcnow()
                recent_cutoff = current_time - timedelta(hours=1)
                
                # Update quality scores based on recent performance
                for model_type, performance in self.performance_metrics.items():
                    # Adjust quality score based on recent performance
                    time_factor = 1.0
                    error_penalty = performance.error_rate * 0.5
                    speed_bonus = max(0, (30.0 - performance.average_response_time) / 30.0) * 0.1
                    
                    new_quality_score = performance.quality_score * (1.0 + speed_bonus - error_penalty)
                    performance.quality_score = max(0.1, min(1.0, new_quality_score))
                
                logger.info("Updated performance metrics")
                
        except Exception as e:
            logger.error(f"Error in performance metrics update loop: {e}")
    
    async def _cleanup_cache_loop(self):
        """Clean up expired cache entries"""
        try:
            while True:
                await asyncio.sleep(1800)  # Clean up every 30 minutes
                
                current_time = datetime.utcnow()
                cutoff_time = current_time - timedelta(hours=24)
                
                # Clean up response cache
                expired_keys = []
                for key, data in self.response_cache.items():
                    if data.get('timestamp', datetime.min) < cutoff_time:
                        expired_keys.append(key)
                
                for key in expired_keys:
                    del self.response_cache[key]
                
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
                
        except Exception as e:
            logger.error(f"Error in cache cleanup loop: {e}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for all models"""
        metrics = {
            "models": {},
            "routing_stats": dict(self.routing_counters),
            "total_requests": sum(p.total_requests for p in self.performance_metrics.values()),
            "total_cost": sum(p.total_cost for p in self.performance_metrics.values()),
            "average_response_time": np.mean([p.average_response_time for p in self.performance_metrics.values()]) if self.performance_metrics else 0.0,
            "overall_success_rate": 1.0 - np.mean([p.error_rate for p in self.performance_metrics.values()]) if self.performance_metrics else 0.0
        }
        
        for model_type, performance in self.performance_metrics.items():
            metrics["models"][model_type.value] = asdict(performance)
        
        return metrics
    
    def get_model_recommendations(self, request_context: Dict[str, Any]) -> List[ModelSelection]:
        """Get model recommendations based on context"""
        recommendations = []
        
        # Analyze context to determine best routing strategies
        if "cost_sensitive" in request_context and request_context["cost_sensitive"]:
            models = self._route_cost_first("", self.available_models)
            recommendations.append(ModelSelection(
                selected_models=models,
                selection_reason="Cost-sensitive request",
                confidence=0.8,
                cost_estimate=0.0,
                time_estimate=0.0,
                fallback_options=self.available_models[:3]
            ))
        
        if "speed_sensitive" in request_context and request_context["speed_sensitive"]:
            models = self._route_speed_first("", self.available_models)
            recommendations.append(ModelSelection(
                selected_models=models,
                selection_reason="Speed-sensitive request",
                confidence=0.8,
                cost_estimate=0.0,
                time_estimate=0.0,
                fallback_options=self.available_models[:3]
            ))
        
        if "quality_sensitive" in request_context and request_context["quality_sensitive"]:
            models = self._route_quality_first("", self.available_models)
            recommendations.append(ModelSelection(
                selected_models=models,
                selection_reason="Quality-sensitive request",
                confidence=0.8,
                cost_estimate=0.0,
                time_estimate=0.0,
                fallback_options=self.available_models[:3]
            ))
        
        return recommendations
    
    def update_ensemble_weights(self, weights: Dict[AIModelType, float]):
        """Update ensemble weights"""
        total_weight = sum(weights.values())
        if total_weight > 0:
            # Normalize weights
            for model_type, weight in weights.items():
                self.ensemble_weights[model_type] = weight / total_weight
        
        logger.info(f"Updated ensemble weights: {self.ensemble_weights}")
    
    def get_orchestration_status(self) -> Dict[str, Any]:
        """Get orchestration service status"""
        return {
            "status": "running",
            "available_models": [m.value for m in self.available_models],
            "active_requests": len(self.active_requests),
            "total_requests_processed": len(self.request_history),
            "performance_metrics": self.get_performance_metrics(),
            "ensemble_weights": {k.value: v for k, v in self.ensemble_weights.items()},
            "routing_strategies": [s.value for s in self.routing_strategies.keys()],
            "ensemble_methods": [e.value for e in EnsembleMethod]
        }

# Factory function
def create_multi_model_ai_orchestration_service() -> MultiModelAIOrchestrationService:
    """Create multi-model AI orchestration service instance"""
    return MultiModelAIOrchestrationService()