"""
ATOM Advanced AI Models Service
Enterprise integration of GPT-4, Claude, LLaMA, and custom models
Real-time streaming intelligence with multi-model orchestration
"""

import os
import json
import asyncio
import aiohttp
import hashlib
import uuid
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta, date
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
from loguru import logger

# Advanced AI Models
try:
    import openai
    from openai import OpenAI
except ImportError:
    openai = None
    OpenAI = None

try:
    import anthropic
    from anthropic import Anthropic
except ImportError:
    anthropic = None
    Anthropic = None

try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
except ImportError:
    torch = None
    AutoTokenizer = AutoModelForCausalLM = pipeline = None

# Existing AI Services
try:
    from cross_service_ai_service import create_cross_service_ai_service, IntegrationType
except ImportError:
    create_cross_service_ai_service = None
    IntegrationType = None

class AIModelType(Enum):
    """Supported AI model types"""
    GPT_4 = "gpt4"
    GPT_4_TURBO = "gpt4_turbo"
    CLAUDE_3 = "claude_3"
    CLAUDE_3_SONNET = "claude_3_sonnet"
    CLAUDE_3_HAIKU = "claude_3_haiku"
    LLAMA_2_70B = "llama2_70b"
    LLAMA_3_70B = "llama3_70b"
    CUSTOM = "custom"

class ModelCapability(Enum):
    """AI model capabilities"""
    TEXT_GENERATION = "text_generation"
    ANALYSIS = "analysis"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    CODING = "coding"
    REASONING = "reasoning"
    MULTIMODAL = "multimodal"
    STREAMING = "streaming"

class ProcessingPriority(Enum):
    """Processing priority levels"""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10

@dataclass
class AIModelConfig:
    """AI model configuration"""
    model_id: str
    model_type: AIModelType
    model_name: str
    provider: str
    capabilities: List[ModelCapability]
    max_tokens: int
    temperature: float
    context_window: int
    cost_per_token: float
    speed: float  # tokens per second
    quality_score: float
    requires_api: bool
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    local_model_path: Optional[str] = None

@dataclass
class AIRequest:
    """AI processing request"""
    request_id: str
    model_type: AIModelType
    prompt: str
    context: Optional[Dict[str, Any]] = None
    priority: ProcessingPriority = ProcessingPriority.NORMAL
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stream: bool = False
    metadata: Dict[str, Any] = None
    timestamp: datetime = None
    callback_url: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}
        if self.context is None:
            self.context = {}

@dataclass
class AIResponse:
    """AI processing response"""
    request_id: str
    model_type: AIModelType
    response: str
    confidence: float
    token_usage: Dict[str, int]
    processing_time: float
    cost: float
    reasoning: Optional[str] = None
    metadata: Dict[str, Any] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}

@dataclass
class AIInsight:
    """Advanced AI-generated insight"""
    insight_id: str
    model_type: AIModelType
    insight_type: str
    title: str
    description: str
    analysis: str
    confidence: float
    business_impact: str
    action_items: List[Dict[str, Any]]
    predictions: List[Dict[str, Any]]
    reasoning: str
    data_sources: List[str]
    generated_at: datetime
    processing_time: float
    cost: float
    
    def __post_init__(self):
        if self.action_items is None:
            self.action_items = []
        if self.predictions is None:
            self.predictions = []

@dataclass
class StreamingChunk:
    """Streaming AI response chunk"""
    chunk_id: str
    request_id: str
    model_type: AIModelType
    content: str
    is_complete: bool
    confidence: float
    timestamp: datetime
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}

class AdvancedAIModelsService:
    """Enterprise advanced AI models service with multi-model orchestration"""
    
    def __init__(self):
        # API keys
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        
        # Model configurations
        self.model_configs = self._initialize_model_configs()
        
        # AI model instances
        self.ai_models = {}
        self.tokenizers = {}
        
        # Initialize AI models
        self._initialize_ai_models()
        
        # Processing queues
        self.request_queue = asyncio.Queue()
        self.response_queue = asyncio.Queue()
        self.streaming_connections = {}
        
        # Performance tracking
        self.performance_metrics = {}
        self.cost_tracking = {}
        
        # Existing services
        self.cross_service_ai = None
        if create_cross_service_ai_service:
            self.cross_service_ai = create_cross_service_ai_service()
        
        logger.info(f"Advanced AI Models Service initialized with {len(self.model_configs)} models")
    
    def _initialize_model_configs(self) -> Dict[AIModelType, AIModelConfig]:
        """Initialize AI model configurations"""
        configs = {}
        
        # GPT-4 models
        if self.openai_api_key:
            configs[AIModelType.GPT_4] = AIModelConfig(
                model_id="gpt4-main",
                model_type=AIModelType.GPT_4,
                model_name="gpt-4",
                provider="OpenAI",
                capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.ANALYSIS, 
                          ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.STREAMING],
                max_tokens=8192,
                temperature=0.7,
                context_window=8192,
                cost_per_token=0.00006,
                speed=25.0,
                quality_score=0.95,
                requires_api=True,
                api_endpoint="https://api.openai.com/v1",
                api_key=self.openai_api_key
            )
            
            configs[AIModelType.GPT_4_TURBO] = AIModelConfig(
                model_id="gpt4-turbo",
                model_type=AIModelType.GPT_4_TURBO,
                model_name="gpt-4-turbo",
                provider="OpenAI",
                capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.ANALYSIS,
                          ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.STREAMING],
                max_tokens=128000,
                temperature=0.7,
                context_window=128000,
                cost_per_token=0.00003,
                speed=50.0,
                quality_score=0.92,
                requires_api=True,
                api_endpoint="https://api.openai.com/v1",
                api_key=self.openai_api_key
            )
        
        # Claude models
        if self.anthropic_api_key:
            configs[AIModelType.CLAUDE_3] = AIModelConfig(
                model_id="claude3-opus",
                model_type=AIModelType.CLAUDE_3,
                model_name="claude-3-opus-20240229",
                provider="Anthropic",
                capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.ANALYSIS,
                          ModelCapability.REASONING, ModelCapability.SUMMARIZATION, ModelCapability.STREAMING],
                max_tokens=4096,
                temperature=0.7,
                context_window=200000,
                cost_per_token=0.000075,
                speed=30.0,
                quality_score=0.96,
                requires_api=True,
                api_endpoint="https://api.anthropic.com",
                api_key=self.anthropic_api_key
            )
            
            configs[AIModelType.CLAUDE_3_SONNET] = AIModelConfig(
                model_id="claude3-sonnet",
                model_type=AIModelType.CLAUDE_3_SONNET,
                model_name="claude-3-sonnet-20240229",
                provider="Anthropic",
                capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.ANALYSIS,
                          ModelCapability.REASONING, ModelCapability.SUMMARIZATION, ModelCapability.STREAMING],
                max_tokens=4096,
                temperature=0.7,
                context_window=200000,
                cost_per_token=0.000015,
                speed=40.0,
                quality_score=0.90,
                requires_api=True,
                api_endpoint="https://api.anthropic.com",
                api_key=self.anthropic_api_key
            )
            
            configs[AIModelType.CLAUDE_3_HAIKU] = AIModelConfig(
                model_id="claude3-haiku",
                model_type=AIModelType.CLAUDE_3_HAIKU,
                model_name="claude-3-haiku-20240307",
                provider="Anthropic",
                capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.ANALYSIS,
                          ModelCapability.REASONING, ModelCapability.SUMMARIZATION, ModelCapability.STREAMING],
                max_tokens=4096,
                temperature=0.7,
                context_window=200000,
                cost_per_token=0.00000025,
                speed=60.0,
                quality_score=0.82,
                requires_api=True,
                api_endpoint="https://api.anthropic.com",
                api_key=self.anthropic_api_key
            )
        
        # LLaMA models (local)
        if torch and AutoTokenizer:
            configs[AIModelType.LLAMA_3_70B] = AIModelConfig(
                model_id="llama3-70b-local",
                model_type=AIModelType.LLAMA_3_70B,
                model_name="meta-llama/Llama-2-70b-chat-hf",  # Update to Llama 3 when available
                provider="Meta",
                capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.ANALYSIS,
                          ModelCapability.REASONING, ModelCapability.STREAMING],
                max_tokens=4096,
                temperature=0.7,
                context_window=4096,
                cost_per_token=0.0,  # Local model
                speed=15.0,
                quality_score=0.85,
                requires_api=False,
                local_model_path="/models/llama3-70b"  # Configure as needed
            )
        
        logger.info(f"Initialized {len(configs)} AI model configurations")
        return configs
    
    def _initialize_ai_models(self):
        """Initialize AI model instances"""
        try:
            # Initialize OpenAI models
            if self.openai_api_key and OpenAI:
                openai_client = OpenAI(api_key=self.openai_api_key)
                self.ai_models[AIModelType.GPT_4] = openai_client
                self.ai_models[AIModelType.GPT_4_TURBO] = openai_client
                logger.info("OpenAI GPT models initialized")
            
            # Initialize Anthropic models
            if self.anthropic_api_key and Anthropic:
                anthropic_client = Anthropic(api_key=self.anthropic_api_key)
                self.ai_models[AIModelType.CLAUDE_3] = anthropic_client
                self.ai_models[AIModelType.CLAUDE_3_SONNET] = anthropic_client
                self.ai_models[AIModelType.CLAUDE_3_HAIKU] = anthropic_client
                logger.info("Anthropic Claude models initialized")
            
            # Initialize local models
            if torch and AutoTokenizer:
                # Note: LLaMA models require local setup and GPU resources
                # This is a placeholder for local model initialization
                logger.info("Local AI models placeholder initialized")
                
        except Exception as e:
            logger.error(f"Failed to initialize AI models: {e}")
    
    def get_model_config(self, model_type: AIModelType) -> Optional[AIModelConfig]:
        """Get configuration for specific model type"""
        return self.model_configs.get(model_type)
    
    def get_available_models(self, capability: Optional[ModelCapability] = None) -> List[AIModelConfig]:
        """Get available AI models"""
        models = list(self.model_configs.values())
        
        if capability:
            models = [m for m in models if capability in m.capabilities]
        
        # Sort by quality score and cost
        models.sort(key=lambda x: (-x.quality_score, x.cost_per_token))
        return models
    
    async def process_request(self, request: AIRequest) -> AIResponse:
        """Process AI request with specified model"""
        try:
            model_config = self.get_model_config(request.model_type)
            if not model_config:
                raise ValueError(f"Model {request.model_type} not available")
            
            logger.info(f"Processing AI request {request.request_id} with model {request.model_type}")
            start_time = datetime.utcnow()
            
            # Route to appropriate model processor
            if request.model_type in [AIModelType.GPT_4, AIModelType.GPT_4_TURBO]:
                response = await self._process_openai_request(request, model_config)
            elif request.model_type in [AIModelType.CLAUDE_3, AIModelType.CLAUDE_3_SONNET, AIModelType.CLAUDE_3_HAIKU]:
                response = await self._process_anthropic_request(request, model_config)
            elif request.model_type in [AIModelType.LLAMA_2_70B, AIModelType.LLAMA_3_70B]:
                response = await self._process_local_model_request(request, model_config)
            else:
                raise ValueError(f"Unsupported model type: {request.model_type}")
            
            # Calculate processing metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            response.processing_time = processing_time
            response.cost = self._calculate_cost(request.model_type, response.token_usage)
            
            # Update performance metrics
            self._update_performance_metrics(request.model_type, processing_time, response.cost)
            
            logger.info(f"Completed AI request {request.request_id} in {processing_time:.2f}s")
            return response
            
        except Exception as e:
            logger.error(f"Failed to process AI request {request.request_id}: {e}")
            raise
    
    async def _process_openai_request(self, request: AIRequest, config: AIModelConfig) -> AIResponse:
        """Process OpenAI GPT request"""
        try:
            client = self.ai_models[request.model_type]
            
            # Prepare messages
            messages = [{"role": "user", "content": request.prompt}]
            
            # Add context if provided
            if request.context:
                context_str = self._format_context(request.context)
                messages.insert(0, {"role": "system", "content": context_str})
            
            # Make API call
            completion = client.chat.completions.create(
                model=config.model_name,
                messages=messages,
                max_tokens=request.max_tokens or config.max_tokens,
                temperature=request.temperature or config.temperature,
                stream=request.stream
            )
            
            if request.stream:
                # Handle streaming response
                response_text = ""
                for chunk in completion:
                    if chunk.choices[0].delta.content:
                        response_text += chunk.choices[0].delta.content
                        
                        # Create streaming chunk
                        stream_chunk = StreamingChunk(
                            chunk_id=str(uuid.uuid4()),
                            request_id=request.request_id,
                            model_type=request.model_type,
                            content=chunk.choices[0].delta.content,
                            is_complete=False,
                            confidence=0.8,
                            timestamp=datetime.utcnow()
                        )
                        await self._handle_streaming_chunk(stream_chunk)
            else:
                response_text = completion.choices[0].message.content
            
            # Create response
            response = AIResponse(
                request_id=request.request_id,
                model_type=request.model_type,
                response=response_text,
                confidence=0.85,  # OpenAI doesn't provide confidence
                token_usage={
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                    "total_tokens": completion.usage.total_tokens
                },
                processing_time=0.0,  # Will be set by caller
                cost=0.0  # Will be set by caller
            )
            
            return response
            
        except Exception as e:
            logger.error(f"OpenAI request failed: {e}")
            raise
    
    async def _process_anthropic_request(self, request: AIRequest, config: AIModelConfig) -> AIResponse:
        """Process Anthropic Claude request"""
        try:
            client = self.ai_models[request.model_type]
            
            # Prepare messages
            messages = []
            
            # Add context if provided
            if request.context:
                context_str = self._format_context(request.context)
                messages.append({"role": "user", "content": f"Context: {context_str}"})
            
            # Add main prompt
            messages.append({"role": "user", "content": request.prompt})
            
            # Make API call
            if request.stream:
                # Handle streaming response
                response_text = ""
                with client.messages.stream(
                    model=config.model_name,
                    max_tokens=request.max_tokens or config.max_tokens,
                    temperature=request.temperature or config.temperature,
                    messages=messages
                ) as stream:
                    for text in stream.text_stream:
                        response_text += text
                        
                        # Create streaming chunk
                        stream_chunk = StreamingChunk(
                            chunk_id=str(uuid.uuid4()),
                            request_id=request.request_id,
                            model_type=request.model_type,
                            content=text,
                            is_complete=False,
                            confidence=0.85,
                            timestamp=datetime.utcnow()
                        )
                        await self._handle_streaming_chunk(stream_chunk)
            else:
                response = client.messages.create(
                    model=config.model_name,
                    max_tokens=request.max_tokens or config.max_tokens,
                    temperature=request.temperature or config.temperature,
                    messages=messages
                )
                response_text = response.content[0].text
            
            # Create response
            token_count = self._estimate_tokens(response_text)
            
            ai_response = AIResponse(
                request_id=request.request_id,
                model_type=request.model_type,
                response=response_text,
                confidence=0.88,  # Claude doesn't provide confidence
                token_usage={
                    "prompt_tokens": self._estimate_tokens(request.prompt),
                    "completion_tokens": token_count,
                    "total_tokens": token_count + self._estimate_tokens(request.prompt)
                },
                processing_time=0.0,  # Will be set by caller
                cost=0.0  # Will be set by caller
            )
            
            return ai_response
            
        except Exception as e:
            logger.error(f"Anthropic request failed: {e}")
            raise
    
    async def _process_local_model_request(self, request: AIRequest, config: AIModelConfig) -> AIResponse:
        """Process local model request (placeholder)"""
        try:
            # This is a placeholder for local model processing
            # In production, this would use transformers pipeline
            
            logger.info(f"Processing local model request {request.model_type}")
            
            # Simulate processing time
            await asyncio.sleep(2.0)
            
            # Mock response (replace with actual local model inference)
            mock_response = f"Local model {request.model_type} response to: {request.prompt[:100]}..."
            
            # Create response
            token_count = self._estimate_tokens(mock_response)
            
            response = AIResponse(
                request_id=request.request_id,
                model_type=request.model_type,
                response=mock_response,
                confidence=0.75,  # Local models typically have lower confidence
                token_usage={
                    "prompt_tokens": self._estimate_tokens(request.prompt),
                    "completion_tokens": token_count,
                    "total_tokens": token_count + self._estimate_tokens(request.prompt)
                },
                processing_time=0.0,  # Will be set by caller
                cost=0.0  # Local models have no API cost
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Local model request failed: {e}")
            raise
    
    async def generate_advanced_insights(self, data_context: Dict[str, Any], 
                                     insight_types: List[str] = None) -> List[AIInsight]:
        """Generate advanced AI insights using multiple models"""
        try:
            if insight_types is None:
                insight_types = ["trend_analysis", "correlation", "prediction", "optimization"]
            
            insights = []
            
            # Use the best available model for each insight type
            best_model = self._get_best_model_for_capability(ModelCapability.ANALYSIS)
            
            for insight_type in insight_types:
                prompt = self._create_insight_prompt(data_context, insight_type)
                
                request = AIRequest(
                    request_id=str(uuid.uuid4()),
                    model_type=best_model.model_type,
                    prompt=prompt,
                    context=data_context,
                    priority=ProcessingPriority.HIGH
                )
                
                response = await self.process_request(request)
                
                # Parse insight from response
                insight = self._parse_insight_response(response, insight_type, best_model.model_type)
                if insight:
                    insights.append(insight)
            
            logger.info(f"Generated {len(insights)} advanced AI insights")
            return insights
            
        except Exception as e:
            logger.error(f"Failed to generate advanced insights: {e}")
            return []
    
    async def process_streaming_request(self, request: AIRequest) -> None:
        """Process streaming AI request"""
        try:
            model_config = self.get_model_config(request.model_type)
            if not model_config or ModelCapability.STREAMING not in model_config.capabilities:
                raise ValueError(f"Model {request.model_type} does not support streaming")
            
            logger.info(f"Starting streaming request {request.request_id}")
            
            # Route to appropriate model processor
            if request.model_type in [AIModelType.GPT_4, AIModelType.GPT_4_TURBO]:
                await self._process_openai_request(request, model_config)
            elif request.model_type in [AIModelType.CLAUDE_3, AIModelType.CLAUDE_3_SONNET, AIModelType.CLAUDE_3_HAIKU]:
                await self._process_anthropic_request(request, model_config)
            else:
                raise ValueError(f"Streaming not supported for model {request.model_type}")
            
            # Send completion signal
            completion_chunk = StreamingChunk(
                chunk_id=str(uuid.uuid4()),
                request_id=request.request_id,
                model_type=request.model_type,
                content="",
                is_complete=True,
                confidence=0.9,
                timestamp=datetime.utcnow()
            )
            await self._handle_streaming_chunk(completion_chunk)
            
            logger.info(f"Completed streaming request {request.request_id}")
            
        except Exception as e:
            logger.error(f"Streaming request failed: {e}")
            raise
    
    async def _handle_streaming_chunk(self, chunk: StreamingChunk):
        """Handle streaming response chunk"""
        # Add to streaming queue
        await self.response_queue.put(("streaming", chunk))
        
        # Send to connected clients if any
        if chunk.request_id in self.streaming_connections:
            connections = self.streaming_connections[chunk.request_id]
            for connection in connections:
                try:
                    await connection.send_json({
                        "type": "streaming_chunk",
                        "chunk_id": chunk.chunk_id,
                        "request_id": chunk.request_id,
                        "model_type": chunk.model_type.value,
                        "content": chunk.content,
                        "is_complete": chunk.is_complete,
                        "confidence": chunk.confidence,
                        "timestamp": chunk.timestamp.isoformat()
                    })
                except:
                    # Remove failed connection
                    connections.remove(connection)
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context for AI models"""
        context_parts = []
        
        for key, value in context.items():
            if isinstance(value, (list, dict)):
                context_parts.append(f"{key}: {json.dumps(value, indent=2)}")
            else:
                context_parts.append(f"{key}: {value}")
        
        return "\n".join(context_parts)
    
    def _create_insight_prompt(self, data_context: Dict[str, Any], insight_type: str) -> str:
        """Create insight generation prompt"""
        base_prompt = f"""
You are an advanced business intelligence AI analyzing enterprise data across multiple services.

DATA CONTEXT:
{self._format_context(data_context)}

INSIGHT TYPE: {insight_type}

Please provide a comprehensive analysis including:
1. Key findings and patterns
2. Business impact assessment
3. Actionable recommendations
4. Predictions if relevant
5. Confidence levels

Format your response as a structured JSON object with fields:
- title
- description
- analysis
- business_impact
- action_items (array)
- predictions (array)
- confidence (0-1)
"""
        
        return base_prompt
    
    def _parse_insight_response(self, response: AIResponse, insight_type: str, model_type: AIModelType) -> Optional[AIInsight]:
        """Parse AI response into insight object"""
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response.response, re.DOTALL)
            if json_match:
                insight_data = json.loads(json_match.group())
                
                insight = AIInsight(
                    insight_id=str(uuid.uuid4()),
                    model_type=model_type,
                    insight_type=insight_type,
                    title=insight_data.get('title', 'Generated Insight'),
                    description=insight_data.get('description', ''),
                    analysis=insight_data.get('analysis', ''),
                    confidence=insight_data.get('confidence', 0.8),
                    business_impact=insight_data.get('business_impact', ''),
                    action_items=insight_data.get('action_items', []),
                    predictions=insight_data.get('predictions', []),
                    reasoning=response.response,
                    data_sources=[],  # To be filled by caller
                    generated_at=response.timestamp,
                    processing_time=response.processing_time,
                    cost=response.cost
                )
                
                return insight
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to parse insight response: {e}")
            return None
    
    def _get_best_model_for_capability(self, capability: ModelCapability) -> Optional[AIModelConfig]:
        """Get best available model for specific capability"""
        available_models = self.get_available_models(capability)
        return available_models[0] if available_models else None
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        # Simple estimation (in production, use proper tokenizer)
        return len(text.split()) * 1.3  # Rough estimate
    
    def _calculate_cost(self, model_type: AIModelType, token_usage: Dict[str, int]) -> float:
        """Calculate cost for model usage"""
        config = self.get_model_config(model_type)
        if not config:
            return 0.0
        
        total_tokens = token_usage.get('total_tokens', 0)
        return total_tokens * config.cost_per_token
    
    def _update_performance_metrics(self, model_type: AIModelType, processing_time: float, cost: float):
        """Update performance metrics for model"""
        if model_type not in self.performance_metrics:
            self.performance_metrics[model_type] = {
                'total_requests': 0,
                'total_time': 0.0,
                'total_cost': 0.0,
                'average_time': 0.0,
                'average_cost': 0.0
            }
        
        metrics = self.performance_metrics[model_type]
        metrics['total_requests'] += 1
        metrics['total_time'] += processing_time
        metrics['total_cost'] += cost
        metrics['average_time'] = metrics['total_time'] / metrics['total_requests']
        metrics['average_cost'] = metrics['total_cost'] / metrics['total_requests']
    
    def get_model_capabilities(self) -> Dict[str, Any]:
        """Get capabilities of all available models"""
        capabilities = {
            "available_models": [],
            "total_models": len(self.model_configs),
            "api_models": len([m for m in self.model_configs.values() if m.requires_api]),
            "local_models": len([m for m in self.model_configs.values() if not m.requires_api]),
            "capabilities": {}
        }
        
        for model_type, config in self.model_configs.items():
            model_info = {
                "model_type": model_type.value,
                "model_name": config.model_name,
                "provider": config.provider,
                "capabilities": [c.value for c in config.capabilities],
                "max_tokens": config.max_tokens,
                "context_window": config.context_window,
                "quality_score": config.quality_score,
                "cost_per_token": config.cost_per_token,
                "speed": config.speed,
                "requires_api": config.requires_api
            }
            capabilities["available_models"].append(model_info)
            
            # Track capabilities
            for cap in config.capabilities:
                if cap.value not in capabilities["capabilities"]:
                    capabilities["capabilities"][cap.value] = []
                capabilities["capabilities"][cap.value].append(model_type.value)
        
        return capabilities
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for all models"""
        return {
            "models": self.performance_metrics,
            "total_requests": sum(m['total_requests'] for m in self.performance_metrics.values()),
            "total_cost": sum(m['total_cost'] for m in self.performance_metrics.values()),
            "average_processing_time": np.mean([m['average_time'] for m in self.performance_metrics.values()]) if self.performance_metrics else 0.0
        }

# Factory function
def create_advanced_ai_models_service() -> AdvancedAIModelsService:
    """Create advanced AI models service instance"""
    return AdvancedAIModelsService()