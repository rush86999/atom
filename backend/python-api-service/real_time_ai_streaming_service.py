"""
ATOM Real-Time AI Intelligence Streaming Service
Live AI processing with WebSocket streaming and real-time insights
"""

import os
import json
import asyncio
import aiohttp
import hashlib
import uuid
import websockets
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
    StreamingChunk,
    ProcessingPriority,
    ModelCapability
)

# Existing Services
try:
    from cross_service_ai_service import create_cross_service_ai_service, IntegrationType
except ImportError:
    create_cross_service_ai_service = None
    IntegrationType = None

class StreamingEventType(Enum):
    """Streaming event types"""
    AI_RESPONSE = "ai_response"
    INSIGHT_GENERATED = "insight_generated"
    WORKFLOW_RECOMMENDATION = "workflow_recommendation"
    PREDICTION_UPDATE = "prediction_update"
    DATA_UPDATED = "data_updated"
    ERROR = "error"
    STATUS_UPDATE = "status_update"

class ConnectionStatus(Enum):
    """WebSocket connection status"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"

@dataclass
class StreamingClient:
    """Streaming WebSocket client"""
    client_id: str
    websocket: Any
    user_id: str
    connected_at: datetime
    last_activity: datetime
    subscriptions: Set[str]
    preferences: Dict[str, Any]
    status: ConnectionStatus
    metadata: Dict[str, Any]
    
    def __post_init__(self):
        if self.subscriptions is None:
            self.subscriptions = set()
        if self.preferences is None:
            self.preferences = {}
        if self.metadata is None:
            self.metadata = {}
        if self.last_activity is None:
            self.last_activity = datetime.utcnow()

@dataclass
class StreamingEvent:
    """Real-time streaming event"""
    event_id: str
    event_type: StreamingEventType
    data: Dict[str, Any]
    timestamp: datetime
    priority: ProcessingPriority
    target_clients: Optional[Set[str]] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.target_clients is None:
            self.target_clients = set()
        if self.metadata is None:
            self.metadata = {}

@dataclass
class RealTimeInsight:
    """Real-time AI insight"""
    insight_id: str
    insight_type: str
    title: str
    description: str
    confidence: float
    severity: str
    impact: str
    action_required: bool
    timeline: str
    affected_services: List[str]
    metrics: Dict[str, Any]
    generated_at: datetime
    expires_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.affected_services is None:
            self.affected_services = []
        if self.metrics is None:
            self.metrics = {}

@dataclass
class LivePrediction:
    """Live business prediction"""
    prediction_id: str
    prediction_type: str
    current_value: float
    predicted_value: float
    confidence_interval: Tuple[float, float]
    trend: str
    impact_level: str
    factors: List[Dict[str, Any]]
    updated_at: datetime
    next_update: datetime
    accuracy_history: List[float] = None
    
    def __post_init__(self):
        if self.accuracy_history is None:
            self.accuracy_history = []

@dataclass
class StreamingMetrics:
    """Streaming system metrics"""
    total_connections: int
    active_connections: int
    total_events: int
    events_per_second: float
    average_latency: float
    error_rate: float
    ai_requests_per_second: float
    insight_generation_rate: float
    uptime_percentage: float

class RealTimeAIStreamingService:
    """Real-time AI intelligence streaming service"""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        
        # AI services
        self.advanced_ai = create_advanced_ai_models_service()
        self.cross_service_ai = None
        if create_cross_service_ai_service:
            self.cross_service_ai = create_cross_service_ai_service()
        
        # WebSocket management
        self.clients = {}  # client_id -> StreamingClient
        self.user_connections = defaultdict(set)  # user_id -> set of client_ids
        self.websockets = {}  # websocket -> client_id
        
        # Event streaming
        self.event_queue = asyncio.Queue()
        self.active_streams = {}  # stream_id -> metadata
        self.subscriptions = defaultdict(set)  # subscription -> set of client_ids
        
        # Real-time data
        self.live_insights = {}  # insight_id -> RealTimeInsight
        self.live_predictions = {}  # prediction_id -> LivePrediction
        self.data_snapshots = {}  # service -> latest data snapshot
        self.trend_data = defaultdict(deque)  # metric -> deque of historical data
        
        # Performance tracking
        self.metrics = {
            "start_time": datetime.utcnow(),
            "total_events": 0,
            "total_connections": 0,
            "total_ai_requests": 0,
            "total_insights_generated": 0,
            "event_history": deque(maxlen=1000),
            "connection_history": deque(maxlen=100),
            "latency_history": deque(maxlen=100)
        }
        
        # Background tasks
        self.background_tasks = set()
        
        logger.info(f"Real-Time AI Streaming Service initialized on {host}:{port}")
    
    async def start_streaming_server(self):
        """Start WebSocket streaming server"""
        try:
            logger.info(f"Starting WebSocket server on {self.host}:{self.port}")
            
            # Start background processors
            # self._start_background_processors()
            
            # Start WebSocket server
            async with websockets.serve(
                self._handle_websocket_connection,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            ):
                logger.info(f"WebSocket server started on {self.host}:{self.port}")
                await asyncio.Future()  # Run forever
                
        except Exception as e:
            logger.error(f"Failed to start streaming server: {e}")
            raise
    
    def _start_background_processors(self):
        """Start background processing tasks"""
        tasks = [
            self._process_events_loop(),
            self._cleanup_connections_loop(),
            self._update_predictions_loop(),
            self._generate_real_time_insights_loop(),
            self._collect_metrics_loop()
        ]
        
        for task in tasks:
            background_task = asyncio.create_task(task)
            self.background_tasks.add(background_task)
            background_task.add_done_callback(self.background_tasks.discard)
    
    async def _handle_websocket_connection(self, websocket, path):
        """Handle new WebSocket connection"""
        try:
            client_id = str(uuid.uuid4())
            client = StreamingClient(
                client_id=client_id,
                websocket=websocket,
                user_id="",  # To be set after authentication
                connected_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                subscriptions=set(),
                preferences={},
                status=ConnectionStatus.CONNECTED,
                metadata={}
            )
            
            # Store connection
            self.clients[client_id] = client
            self.websockets[websocket] = client_id
            self.metrics["total_connections"] += 1
            self.metrics["connection_history"].append({
                "client_id": client_id,
                "action": "connected",
                "timestamp": datetime.utcnow()
            })
            
            logger.info(f"WebSocket client connected: {client_id}")
            
            # Send welcome message
            await self._send_to_client(client_id, {
                "type": "welcome",
                "client_id": client_id,
                "server_time": datetime.utcnow().isoformat(),
                "capabilities": self._get_streaming_capabilities()
            })
            
            # Handle messages
            try:
                async for message in websocket:
                    await self._handle_client_message(client_id, message)
            except websockets.exceptions.ConnectionClosed:
                logger.info(f"WebSocket client disconnected: {client_id}")
            finally:
                await self._cleanup_client(client_id)
                
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
    
    async def _handle_client_message(self, client_id: str, message: str):
        """Handle client message"""
        try:
            client = self.clients.get(client_id)
            if not client:
                return
            
            client.last_activity = datetime.utcnow()
            
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "authenticate":
                await self._handle_authentication(client_id, data)
            
            elif message_type == "subscribe":
                await self._handle_subscription(client_id, data)
            
            elif message_type == "unsubscribe":
                await self._handle_unsubscription(client_id, data)
            
            elif message_type == "ai_request":
                await self._handle_ai_request(client_id, data)
            
            elif message_type == "stream_start":
                await self._handle_stream_start(client_id, data)
            
            elif message_type == "stream_stop":
                await self._handle_stream_stop(client_id, data)
            
            elif message_type == "ping":
                await self._send_to_client(client_id, {"type": "pong"})
            
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except Exception as e:
            logger.error(f"Error handling client message: {e}")
    
    async def _handle_authentication(self, client_id: str, data: Dict[str, Any]):
        """Handle client authentication"""
        try:
            token = data.get("token")
            user_id = data.get("user_id")
            
            # In production, validate token with proper authentication
            # For now, accept any non-empty token
            if token and user_id:
                client = self.clients[client_id]
                client.user_id = user_id
                client.status = ConnectionStatus.CONNECTED
                
                # Add to user connections
                self.user_connections[user_id].add(client_id)
                
                # Send authentication success
                await self._send_to_client(client_id, {
                    "type": "authentication_success",
                    "user_id": user_id
                })
                
                logger.info(f"Client {client_id} authenticated as user {user_id}")
            else:
                await self._send_to_client(client_id, {
                    "type": "authentication_failed",
                    "error": "Invalid credentials"
                })
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
    
    async def _handle_subscription(self, client_id: str, data: Dict[str, Any]):
        """Handle subscription request"""
        try:
            client = self.clients[client_id]
            subscription = data.get("subscription")
            
            if subscription:
                client.subscriptions.add(subscription)
                self.subscriptions[subscription].add(client_id)
                
                await self._send_to_client(client_id, {
                    "type": "subscription_success",
                    "subscription": subscription
                })
                
                logger.info(f"Client {client_id} subscribed to {subscription}")
            else:
                await self._send_to_client(client_id, {
                    "type": "subscription_failed",
                    "error": "Invalid subscription"
                })
                
        except Exception as e:
            logger.error(f"Subscription error: {e}")
    
    async def _handle_unsubscription(self, client_id: str, data: Dict[str, Any]):
        """Handle unsubscription request"""
        try:
            client = self.clients[client_id]
            subscription = data.get("subscription")
            
            if subscription and subscription in client.subscriptions:
                client.subscriptions.remove(subscription)
                self.subscriptions[subscription].discard(client_id)
                
                await self._send_to_client(client_id, {
                    "type": "unsubscription_success",
                    "subscription": subscription
                })
                
                logger.info(f"Client {client_id} unsubscribed from {subscription}")
            else:
                await self._send_to_client(client_id, {
                    "type": "unsubscription_failed",
                    "error": "Invalid subscription"
                })
                
        except Exception as e:
            logger.error(f"Unsubscription error: {e}")
    
    async def _handle_ai_request(self, client_id: str, data: Dict[str, Any]):
        """Handle AI processing request"""
        try:
            client = self.clients[client_id]
            prompt = data.get("prompt")
            model_type = data.get("model_type", AIModelType.GPT_4_TURBO.value)
            stream = data.get("stream", False)
            priority = data.get("priority", ProcessingPriority.NORMAL.value)
            
            if not prompt:
                await self._send_to_client(client_id, {
                    "type": "ai_request_failed",
                    "error": "Prompt is required"
                })
                return
            
            # Create AI request
            ai_request = AIRequest(
                request_id=str(uuid.uuid4()),
                model_type=AIModelType(model_type),
                prompt=prompt,
                context={"client_id": client_id, "user_id": client.user_id},
                priority=ProcessingPriority(priority),
                stream=stream
            )
            
            self.metrics["total_ai_requests"] += 1
            
            # Process request
            if stream:
                await self._process_streaming_ai_request(client_id, ai_request)
            else:
                response = await self.advanced_ai.process_request(ai_request)
                
                # Send response
                await self._send_to_client(client_id, {
                    "type": "ai_response",
                    "request_id": ai_request.request_id,
                    "response": response.response,
                    "confidence": response.confidence,
                    "model_type": response.model_type.value,
                    "token_usage": response.token_usage,
                    "processing_time": response.processing_time,
                    "cost": response.cost
                })
                
        except Exception as e:
            logger.error(f"AI request error: {e}")
            await self._send_to_client(client_id, {
                "type": "ai_request_failed",
                "error": str(e)
            })
    
    async def _handle_stream_start(self, client_id: str, data: Dict[str, Any]):
        """Handle stream start request"""
        try:
            stream_type = data.get("stream_type")
            stream_config = data.get("config", {})
            
            stream_id = str(uuid.uuid4())
            self.active_streams[stream_id] = {
                "client_id": client_id,
                "stream_type": stream_type,
                "config": stream_config,
                "started_at": datetime.utcnow(),
                "status": "active"
            }
            
            await self._send_to_client(client_id, {
                "type": "stream_started",
                "stream_id": stream_id,
                "stream_type": stream_type
            })
            
            # Start stream processing based on type
            if stream_type == "real_time_insights":
                asyncio.create_task(self._stream_real_time_insights(stream_id, client_id))
            elif stream_type == "live_predictions":
                asyncio.create_task(self._stream_live_predictions(stream_id, client_id))
            elif stream_type == "data_updates":
                asyncio.create_task(self._stream_data_updates(stream_id, client_id))
            
            logger.info(f"Started stream {stream_id} for client {client_id}")
            
        except Exception as e:
            logger.error(f"Stream start error: {e}")
    
    async def _handle_stream_stop(self, client_id: str, data: Dict[str, Any]):
        """Handle stream stop request"""
        try:
            stream_id = data.get("stream_id")
            
            if stream_id in self.active_streams:
                self.active_streams[stream_id]["status"] = "stopped"
                del self.active_streams[stream_id]
                
                await self._send_to_client(client_id, {
                    "type": "stream_stopped",
                    "stream_id": stream_id
                })
                
                logger.info(f"Stopped stream {stream_id} for client {client_id}")
            
        except Exception as e:
            logger.error(f"Stream stop error: {e}")
    
    async def _process_streaming_ai_request(self, client_id: str, request: AIRequest):
        """Process streaming AI request"""
        try:
            # Start streaming
            await self._send_to_client(client_id, {
                "type": "ai_response_start",
                "request_id": request.request_id,
                "model_type": request.model_type.value
            })
            
            # Process with streaming
            await self.advanced_ai.process_streaming_request(request)
            
        except Exception as e:
            logger.error(f"Streaming AI request error: {e}")
            await self._send_to_client(client_id, {
                "type": "ai_request_failed",
                "request_id": request.request_id,
                "error": str(e)
            })
    
    async def _stream_real_time_insights(self, stream_id: str, client_id: str):
        """Stream real-time insights"""
        try:
            while stream_id in self.active_streams and self.active_streams[stream_id]["status"] == "active":
                # Generate new insights
                if self.cross_service_ai:
                    insights = await self.cross_service_ai.generate_cross_service_insights()
                    
                    for insight in insights[:3]:  # Limit to 3 insights
                        real_time_insight = RealTimeInsight(
                            insight_id=insight.insight_id,
                            insight_type=insight.insight_type,
                            title=insight.title,
                            description=insight.description,
                            confidence=insight.confidence_score,
                            severity="high" if insight.confidence_score > 0.8 else "medium",
                            impact=insight.business_impact,
                            action_required=len(insight.action_items) > 0,
                            timeline="immediate",
                            affected_services=[s.value for s in insight.services_involved],
                            metrics={"confidence": insight.confidence_score},
                            generated_at=insight.generated_at
                        )
                        
                        # Send insight
                        await self._send_to_client(client_id, {
                            "type": "real_time_insight",
                            "stream_id": stream_id,
                            "insight": asdict(real_time_insight)
                        })
                        
                        # Store insight
                        self.live_insights[insight.insight_id] = real_time_insight
                
                # Wait before next iteration
                await asyncio.sleep(30)  # Update every 30 seconds
                
        except Exception as e:
            logger.error(f"Real-time insights streaming error: {e}")
    
    async def _stream_live_predictions(self, stream_id: str, client_id: str):
        """Stream live predictions"""
        try:
            while stream_id in self.active_streams and self.active_streams[stream_id]["status"] == "active":
                # Generate predictions
                if self.cross_service_ai:
                    predictions = await self.cross_service_ai.predict_business_trends()
                    
                    for prediction in predictions:
                        live_prediction = LivePrediction(
                            prediction_id=prediction.prediction_id,
                            prediction_type=prediction.prediction_type,
                            current_value=0.0,  # Would calculate from real data
                            predicted_value=float(prediction.confidence_interval[0]),
                            confidence_interval=prediction.confidence_interval,
                            trend="increasing",
                            impact_level="high",
                            factors=prediction.influencing_factors,
                            updated_at=prediction.generated_at,
                            next_update=prediction.generated_at + timedelta(minutes=30)
                        )
                        
                        # Send prediction
                        await self._send_to_client(client_id, {
                            "type": "live_prediction",
                            "stream_id": stream_id,
                            "prediction": asdict(live_prediction)
                        })
                        
                        # Store prediction
                        self.live_predictions[prediction.prediction_id] = live_prediction
                
                # Wait before next iteration
                await asyncio.sleep(60)  # Update every minute
                
        except Exception as e:
            logger.error(f"Live predictions streaming error: {e}")
    
    async def _stream_data_updates(self, stream_id: str, client_id: str):
        """Stream data updates"""
        try:
            while stream_id in self.active_streams and self.active_streams[stream_id]["status"] == "active":
                # Collect latest data
                if self.cross_service_ai:
                    # Simulate data updates
                    for service in IntegrationType:
                        data_update = {
                            "service": service.value,
                            "timestamp": datetime.utcnow().isoformat(),
                            "data_count": np.random.randint(10, 100),
                            "new_items": np.random.randint(0, 10),
                            "updates": np.random.randint(0, 5)
                        }
                        
                        await self._send_to_client(client_id, {
                            "type": "data_update",
                            "stream_id": stream_id,
                            "service": service.value,
                            "update": data_update
                        })
                
                # Wait before next iteration
                await asyncio.sleep(15)  # Update every 15 seconds
                
        except Exception as e:
            logger.error(f"Data updates streaming error: {e}")
    
    async def _process_events_loop(self):
        """Process events from queue"""
        try:
            while True:
                event = await self.event_queue.get()
                await self._process_event(event)
                self.metrics["total_events"] += 1
                
        except Exception as e:
            logger.error(f"Event processing loop error: {e}")
    
    async def _process_event(self, event: StreamingEvent):
        """Process streaming event"""
        try:
            start_time = datetime.utcnow()
            
            # Determine target clients
            if event.target_clients:
                target_client_ids = event.target_clients
            else:
                target_client_ids = set()
                for subscription in self.subscriptions:
                    if any(sub in event.event_type.value for sub in subscription):
                        target_client_ids.update(self.subscriptions[subscription])
            
            # Send event to all target clients
            for client_id in target_client_ids:
                await self._send_to_client(client_id, {
                    "type": "streaming_event",
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "data": event.data,
                    "timestamp": event.timestamp.isoformat(),
                    "priority": event.priority.value
                })
            
            # Update metrics
            latency = (datetime.utcnow() - start_time).total_seconds()
            self.metrics["latency_history"].append(latency)
            
        except Exception as e:
            logger.error(f"Event processing error: {e}")
    
    async def _cleanup_connections_loop(self):
        """Cleanup inactive connections"""
        try:
            while True:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = datetime.utcnow()
                inactive_clients = []
                
                for client_id, client in self.clients.items():
                    # Check if client is inactive (no activity for 5 minutes)
                    if (current_time - client.last_activity).total_seconds() > 300:
                        inactive_clients.append(client_id)
                
                # Cleanup inactive clients
                for client_id in inactive_clients:
                    logger.info(f"Cleaning up inactive client: {client_id}")
                    await self._cleanup_client(client_id)
                
        except Exception as e:
            logger.error(f"Connection cleanup loop error: {e}")
    
    async def _update_predictions_loop(self):
        """Update live predictions"""
        try:
            while True:
                await asyncio.sleep(300)  # Update every 5 minutes
                
                if not self.cross_service_ai:
                    continue
                
                # Update existing predictions
                for prediction_id, prediction in self.live_predictions.items():
                    # Simulate prediction update
                    prediction.updated_at = datetime.utcnow()
                    prediction.next_update = prediction.updated_at + timedelta(minutes=30)
                    
                    # Broadcast prediction update
                    await self._broadcast_event(StreamingEventType.PREDICTION_UPDATE, {
                        "prediction_id": prediction_id,
                        "prediction": asdict(prediction)
                    })
                
        except Exception as e:
            logger.error(f"Prediction update loop error: {e}")
    
    async def _generate_real_time_insights_loop(self):
        """Generate real-time insights"""
        try:
            while True:
                await asyncio.sleep(180)  # Generate every 3 minutes
                
                if not self.cross_service_ai:
                    continue
                
                # Generate insights
                insights = await self.cross_service_ai.generate_cross_service_insights()
                
                for insight in insights:
                    # Create real-time insight
                    real_time_insight = RealTimeInsight(
                        insight_id=insight.insight_id,
                        insight_type=insight.insight_type,
                        title=insight.title,
                        description=insight.description,
                        confidence=insight.confidence_score,
                        severity="high" if insight.confidence_score > 0.8 else "medium",
                        impact=insight.business_impact,
                        action_required=len(insight.action_items) > 0,
                        timeline="immediate",
                        affected_services=[s.value for s in insight.services_involved],
                        metrics={"confidence": insight.confidence_score},
                        generated_at=insight.generated_at,
                        expires_at=insight.generated_at + timedelta(hours=24)
                    )
                    
                    # Store and broadcast
                    self.live_insights[insight.insight_id] = real_time_insight
                    self.metrics["total_insights_generated"] += 1
                    
                    await self._broadcast_event(StreamingEventType.INSIGHT_GENERATED, {
                        "insight": asdict(real_time_insight)
                    })
                
        except Exception as e:
            logger.error(f"Real-time insights generation loop error: {e}")
    
    async def _collect_metrics_loop(self):
        """Collect system metrics"""
        try:
            while True:
                await asyncio.sleep(30)  # Update every 30 seconds
                
                current_time = datetime.utcnow()
                uptime_seconds = (current_time - self.metrics["start_time"]).total_seconds()
                uptime_percentage = 100.0  # Simplified
                
                # Calculate metrics
                streaming_metrics = StreamingMetrics(
                    total_connections=self.metrics["total_connections"],
                    active_connections=len(self.clients),
                    total_events=self.metrics["total_events"],
                    events_per_second=len(self.metrics["event_history"]) / 60.0,
                    average_latency=np.mean(self.metrics["latency_history"]) if self.metrics["latency_history"] else 0.0,
                    error_rate=0.0,  # Would calculate from error events
                    ai_requests_per_second=self.metrics["total_ai_requests"] / uptime_seconds,
                    insight_generation_rate=self.metrics["total_insights_generated"] / uptime_seconds,
                    uptime_percentage=uptime_percentage
                )
                
                # Broadcast metrics
                await self._broadcast_event(StreamingEventType.STATUS_UPDATE, {
                    "metrics": asdict(streaming_metrics),
                    "active_streams": len(self.active_streams),
                    "live_insights": len(self.live_insights),
                    "live_predictions": len(self.live_predictions)
                })
                
        except Exception as e:
            logger.error(f"Metrics collection loop error: {e}")
    
    async def _send_to_client(self, client_id: str, data: Dict[str, Any]):
        """Send message to specific client"""
        try:
            client = self.clients.get(client_id)
            if not client:
                return
            
            await client.websocket.send(json.dumps(data))
            
        except Exception as e:
            logger.error(f"Error sending to client {client_id}: {e}")
            # Mark client for cleanup
            client.status = ConnectionStatus.ERROR
    
    async def _cleanup_client(self, client_id: str):
        """Cleanup disconnected client"""
        try:
            client = self.clients.get(client_id)
            if not client:
                return
            
            # Remove from subscriptions
            for subscription in client.subscriptions:
                self.subscriptions[subscription].discard(client_id)
            
            # Remove from user connections
            if client.user_id:
                self.user_connections[client.user_id].discard(client_id)
            
            # Remove from websockets
            if client.websocket in self.websockets:
                del self.websockets[client.websocket]
            
            # Remove client
            del self.clients[client_id]
            
            # Stop active streams for this client
            streams_to_stop = [sid for sid, stream in self.active_streams.items() 
                             if stream["client_id"] == client_id]
            for stream_id in streams_to_stop:
                del self.active_streams[stream_id]
            
            # Record disconnection
            self.metrics["connection_history"].append({
                "client_id": client_id,
                "action": "disconnected",
                "timestamp": datetime.utcnow()
            })
            
            logger.info(f"Cleaned up client: {client_id}")
            
        except Exception as e:
            logger.error(f"Error cleaning up client {client_id}: {e}")
    
    async def _broadcast_event(self, event_type: StreamingEventType, data: Dict[str, Any]):
        """Broadcast event to all subscribed clients"""
        try:
            event = StreamingEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                data=data,
                timestamp=datetime.utcnow(),
                priority=ProcessingPriority.NORMAL
            )
            
            await self.event_queue.put(event)
            
        except Exception as e:
            logger.error(f"Error broadcasting event: {e}")
    
    def _get_streaming_capabilities(self) -> Dict[str, Any]:
        """Get streaming capabilities"""
        model_capabilities = self.advanced_ai.get_model_capabilities()
        
        return {
            "supported_events": [e.value for e in StreamingEventType],
            "supported_models": model_capabilities["available_models"],
            "stream_types": [
                "real_time_insights",
                "live_predictions",
                "data_updates",
                "ai_responses"
            ],
            "max_concurrent_streams": 100,
            "supported_subscriptions": [
                "insights",
                "predictions",
                "workflows",
                "data_updates",
                "ai_responses",
                "metrics"
            ]
        }
    
    def get_streaming_status(self) -> Dict[str, Any]:
        """Get streaming system status"""
        return {
            "server_status": "running",
            "total_connections": len(self.clients),
            "active_connections": len([c for c in self.clients.values() if c.status == ConnectionStatus.CONNECTED]),
            "active_streams": len(self.active_streams),
            "live_insights": len(self.live_insights),
            "live_predictions": len(self.live_predictions),
            "total_events_processed": self.metrics["total_events"],
            "uptime_seconds": (datetime.utcnow() - self.metrics["start_time"]).total_seconds()
        }

# Factory function
def create_real_time_ai_streaming_service(host: str = "localhost", port: int = 8765) -> RealTimeAIStreamingService:
    """Create real-time AI streaming service instance"""
    return RealTimeAIStreamingService(host, port)