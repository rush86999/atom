#!/usr/bin/env python3
"""
Real-Time Integration Dashboard with AI Predictions
WebSocket-based dashboard for monitoring all integrations with AI insights
"""

import os
import json
import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, asdict
from fastapi import WebSocket, WebSocketDisconnect
from fastapi import APIRouter
from collections import defaultdict, deque
import httpx
import uuid

from ai_error_prediction import get_ai_predictor, ErrorPrediction, SystemHealthPrediction

logger = logging.getLogger(__name__)

@dataclass
class DashboardClient:
    """Connected dashboard client"""
    websocket: WebSocket
    client_id: str
    connected_at: datetime
    last_heartbeat: datetime
    subscriptions: Set[str]
    client_info: Dict[str, Any]

@dataclass
class IntegrationMetrics:
    """Real-time integration metrics"""
    integration: str
    status: str
    health_score: float
    response_time: float
    request_rate: float
    error_rate: float
    last_update: datetime
    uptime_percentage: float
    active_connections: int
    error_count: int
    success_count: int
    total_requests: int

@dataclass
class AlertEvent:
    """Dashboard alert event"""
    id: str
    type: 'warning' | 'error' | 'info' | 'critical'
    integration: str
    title: str
    message: str
    timestamp: datetime
    acknowledged: bool
    metadata: Dict[str, Any]

class RealTimeDashboard:
    """Real-time dashboard with AI predictions"""
    
    def __init__(self):
        self.connected_clients: Dict[str, DashboardClient] = {}
        self.integration_metrics: Dict[str, IntegrationMetrics] = {}
        self.alerts: List[AlertEvent] = []
        self.ai_predictions: Dict[str, ErrorPrediction] = {}
        self.system_prediction: Optional[SystemHealthPrediction] = None
        
        # Configuration
        self.max_alerts = 100
        self.heartbeat_interval = 30  # seconds
        self.metrics_update_interval = 10  # seconds
        self.prediction_interval = 60  # seconds
        
        # Task references
        self.monitoring_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        
        # HTTP client for integration data
        self.http_client = httpx.AsyncClient(timeout=10.0)
        
        # Initialize
        self._initialize_integrations()
    
    def _initialize_integrations(self):
        """Initialize integration metrics"""
        integrations = ['hubspot', 'slack', 'jira', 'linear', 'salesforce', 'xero']
        
        for integration in integrations:
            self.integration_metrics[integration] = IntegrationMetrics(
                integration=integration,
                status='unknown',
                health_score=0.0,
                response_time=0.0,
                request_rate=0.0,
                error_rate=0.0,
                last_update=datetime.now(timezone.utc),
                uptime_percentage=100.0,
                active_connections=0,
                error_count=0,
                success_count=0,
                total_requests=0
            )
        
        logger.info(f"Initialized metrics for {len(integrations)} integrations")
    
    async def connect_client(self, websocket: WebSocket, client_info: Dict[str, Any] = None) -> str:
        """Connect new dashboard client"""
        await websocket.accept()
        
        client_id = str(uuid.uuid4())
        client = DashboardClient(
            websocket=websocket,
            client_id=client_id,
            connected_at=datetime.now(timezone.utc),
            last_heartbeat=datetime.now(timezone.utc),
            subscriptions=set(['metrics', 'alerts', 'predictions']),
            client_info=client_info or {}
        )
        
        self.connected_clients[client_id] = client
        
        # Send initial data
        await self._send_initial_data(client)
        
        logger.info(f"Client {client_id} connected to dashboard")
        
        return client_id
    
    async def disconnect_client(self, client_id: str):
        """Disconnect dashboard client"""
        if client_id in self.connected_clients:
            del self.connected_clients[client_id]
            logger.info(f"Client {client_id} disconnected from dashboard")
    
    async def start_monitoring(self):
        """Start real-time monitoring"""
        logger.info("Starting real-time dashboard monitoring")
        
        # Start monitoring tasks
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        # Start AI predictions
        asyncio.create_task(self._prediction_loop())
    
    async def stop_monitoring(self):
        """Stop real-time monitoring"""
        logger.info("Stopping real-time dashboard monitoring")
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
        
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                # Update integration metrics
                await self._update_integration_metrics()
                
                # Broadcast metrics to clients
                await self._broadcast_metrics()
                
                # Check for alerts
                await self._check_alerts()
                
                # Sleep until next update
                await asyncio.sleep(self.metrics_update_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(5)
    
    async def _heartbeat_loop(self):
        """Heartbeat loop for client connections"""
        while True:
            try:
                current_time = datetime.now(timezone.utc)
                expired_clients = []
                
                for client_id, client in self.connected_clients.items():
                    if (current_time - client.last_heartbeat).seconds > self.heartbeat_interval * 2:
                        expired_clients.append(client_id)
                    else:
                        # Send heartbeat
                        try:
                            await client.websocket.send_json({
                                'type': 'heartbeat',
                                'timestamp': current_time.isoformat()
                            })
                        except Exception as e:
                            logger.warning(f"Failed to send heartbeat to {client_id}: {e}")
                            expired_clients.append(client_id)
                
                # Remove expired clients
                for client_id in expired_clients:
                    await self.disconnect_client(client_id)
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
                await asyncio.sleep(10)
    
    async def _prediction_loop(self):
        """AI prediction loop"""
        while True:
            try:
                predictor = get_ai_predictor()
                
                # Update predictions for all integrations
                for integration, metrics in self.integration_metrics.items():
                    integration_data = {
                        'integration': integration,
                        'service': 'api',
                        'response_time': metrics.response_time,
                        'success_rate': 1.0 - metrics.error_rate,
                        'error_rate': metrics.error_rate,
                        'request_count': metrics.total_requests,
                        'consecutive_failures': metrics.error_count,
                        'health_score_1h': metrics.health_score,
                        'last_error_minutes': (datetime.now(timezone.utc) - metrics.last_update).total_seconds() / 60
                    }
                    
                    # Collect training data
                    predictor.collect_training_data({
                        **integration_data,
                        'failed': metrics.error_rate > 0.5
                    })
                    
                    # Generate prediction
                    prediction = await predictor.predict_failure(integration_data)
                    self.ai_predictions[integration] = prediction
                    
                    # Create alert if high risk
                    if prediction.failure_probability > 0.7:
                        await self._create_alert(
                            'warning',
                            integration,
                            'AI Failure Prediction',
                            f"High failure probability: {prediction.failure_probability:.1%} - {prediction.predicted_failure_type}",
                            {
                                'failure_probability': prediction.failure_probability,
                                'predicted_failure_type': prediction.predicted_failure_type,
                                'time_to_failure': prediction.time_to_failure,
                                'risk_factors': prediction.risk_factors,
                                'suggested_actions': prediction.suggested_actions
                            }
                        )
                
                # Update system prediction
                system_pred = await predictor.predict_system_health()
                self.system_prediction = system_pred
                
                # Broadcast predictions
                await self._broadcast_predictions()
                
                # Train models periodically
                await asyncio.sleep(self.prediction_interval * 10)  # Train every 10 minutes
                
                try:
                    await predictor.train_models()
                except Exception as e:
                    logger.warning(f"Model training failed: {e}")
                
                await asyncio.sleep(self.prediction_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Prediction loop error: {e}")
                await asyncio.sleep(30)
    
    async def _update_integration_metrics(self):
        """Update integration metrics from health endpoints"""
        base_url = os.getenv("PYTHON_API_SERVICE_BASE_URL", "http://localhost:5058")
        
        for integration in self.integration_metrics.keys():
            try:
                # Get health data
                health_url = f"{base_url}/api/integrations/{integration}/health"
                response = await self.http_client.get(health_url, timeout=5.0)
                
                if response.status_code == 200:
                    health_data = response.json()
                    
                    # Update metrics
                    metrics = self.integration_metrics[integration]
                    
                    metrics.status = health_data.get('status', 'unknown')
                    metrics.health_score = (health_data.get('connected_count', 0) / 
                                        max(health_data.get('total_services', 1), 1)) * 100
                    metrics.last_update = datetime.now(timezone.utc)
                    
                    # Calculate response time if available
                    services = health_data.get('services', {})
                    response_times = [s.get('response_time', 0) for s in services.values() 
                                   if s.get('response_time')]
                    if response_times:
                        metrics.response_time = sum(response_times) / len(response_times)
                    
                    # Update request counters (simplified)
                    if health_data.get('status') != 'unhealthy':
                        metrics.success_count += 1
                    else:
                        metrics.error_count += 1
                    
                    metrics.total_requests = metrics.success_count + metrics.error_count
                    
                    # Calculate rates (simplified)
                    time_diff = (datetime.now(timezone.utc) - metrics.last_update).total_seconds()
                    if time_diff > 0:
                        metrics.request_rate = metrics.total_requests / time_diff / 3600  # per hour
                        metrics.error_rate = metrics.error_count / max(metrics.total_requests, 1)
                
                else:
                    # Health check failed
                    metrics = self.integration_metrics[integration]
                    metrics.status = 'unhealthy'
                    metrics.error_count += 1
                    metrics.total_requests = metrics.success_count + metrics.error_count
                    metrics.error_rate = metrics.error_count / max(metrics.total_requests, 1)
                    metrics.last_update = datetime.now(timezone.utc)
                
            except Exception as e:
                logger.warning(f"Failed to update {integration} metrics: {e}")
                metrics = self.integration_metrics[integration]
                metrics.status = 'error'
                metrics.error_count += 1
                metrics.total_requests = metrics.success_count + metrics.error_count
                metrics.error_rate = metrics.error_count / max(metrics.total_requests, 1)
                metrics.last_update = datetime.now(timezone.utc)
    
    async def _check_alerts(self):
        """Check for new alerts"""
        for integration, metrics in self.integration_metrics.items():
            alerts_to_create = []
            
            # Health alerts
            if metrics.health_score < 50 and metrics.status != 'unhealthy':
                alerts_to_create.append({
                    'type': 'warning',
                    'title': 'Low Health Score',
                    'message': f"{integration.title()} health score: {metrics.health_score:.1f}%"
                })
            elif metrics.status == 'unhealthy':
                alerts_to_create.append({
                    'type': 'error',
                    'title': 'Integration Unhealthy',
                    'message': f"{integration.title()} integration is unhealthy"
                })
            
            # Performance alerts
            if metrics.response_time > 5000:  # 5 seconds
                alerts_to_create.append({
                    'type': 'warning',
                    'title': 'High Response Time',
                    'message': f"{integration.title()} response time: {metrics.response_time:.0f}ms"
                })
            
            # Error rate alerts
            if metrics.error_rate > 0.2:  # 20% error rate
                alerts_to_create.append({
                    'type': 'error',
                    'title': 'High Error Rate',
                    'message': f"{integration.title()} error rate: {metrics.error_rate:.1%}"
                })
            
            # AI prediction alerts
            if integration in self.ai_predictions:
                prediction = self.ai_predictions[integration]
                if prediction.failure_probability > 0.8:
                    alerts_to_create.append({
                        'type': 'critical',
                        'title': 'AI Critical Failure Prediction',
                        'message': f"AI predicts {prediction.failure_probability:.1%} failure probability for {integration.title()}"
                    })
            
            # Create alerts
            for alert_data in alerts_to_create:
                await self._create_alert(
                    alert_data['type'],
                    integration,
                    alert_data['title'],
                    alert_data['message']
                )
    
    async def _create_alert(self, alert_type: str, integration: str, title: str, 
                           message: str, metadata: Dict[str, Any] = None):
        """Create new alert"""
        alert = AlertEvent(
            id=str(uuid.uuid4()),
            type=alert_type,
            integration=integration,
            title=title,
            message=message,
            timestamp=datetime.now(timezone.utc),
            acknowledged=False,
            metadata=metadata or {}
        )
        
        # Add to alerts list (keep only recent alerts)
        self.alerts.append(alert)
        if len(self.alerts) > self.max_alerts:
            self.alerts = self.alerts[-self.max_alerts:]
        
        # Broadcast alert to clients
        await self._broadcast_alert(alert)
        
        logger.info(f"Created {alert_type} alert for {integration}: {title}")
    
    async def _send_initial_data(self, client: DashboardClient):
        """Send initial dashboard data to client"""
        try:
            # Send current metrics
            metrics_data = {
                'type': 'initial_metrics',
                'data': {
                    integration: asdict(metrics) for integration, metrics in self.integration_metrics.items()
                }
            }
            await client.websocket.send_json(metrics_data)
            
            # Send current alerts
            alerts_data = {
                'type': 'initial_alerts',
                'data': [asdict(alert) for alert in self.alerts]
            }
            await client.websocket.send_json(alerts_data)
            
            # Send current predictions
            predictions_data = {
                'type': 'initial_predictions',
                'data': {
                    'integrations': {k: asdict(v) for k, v in self.ai_predictions.items()},
                    'system': asdict(self.system_prediction) if self.system_prediction else None
                }
            }
            await client.websocket.send_json(predictions_data)
            
        except Exception as e:
            logger.error(f"Failed to send initial data to {client.client_id}: {e}")
    
    async def _broadcast_metrics(self):
        """Broadcast metrics updates to all clients"""
        if not self.connected_clients:
            return
        
        try:
            metrics_data = {
                'type': 'metrics_update',
                'data': {
                    integration: asdict(metrics) for integration, metrics in self.integration_metrics.items()
                },
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            await self._broadcast_message(metrics_data)
            
        except Exception as e:
            logger.error(f"Failed to broadcast metrics: {e}")
    
    async def _broadcast_predictions(self):
        """Broadcast AI predictions to all clients"""
        if not self.connected_clients:
            return
        
        try:
            predictions_data = {
                'type': 'predictions_update',
                'data': {
                    'integrations': {k: asdict(v) for k, v in self.ai_predictions.items()},
                    'system': asdict(self.system_prediction) if self.system_prediction else None
                },
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            await self._broadcast_message(predictions_data)
            
        except Exception as e:
            logger.error(f"Failed to broadcast predictions: {e}")
    
    async def _broadcast_alert(self, alert: AlertEvent):
        """Broadcast alert to all clients"""
        try:
            alert_data = {
                'type': 'alert',
                'data': asdict(alert),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            await self._broadcast_message(alert_data)
            
        except Exception as e:
            logger.error(f"Failed to broadcast alert: {e}")
    
    async def _broadcast_message(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        disconnected_clients = []
        
        for client_id, client in self.connected_clients.items():
            try:
                await client.websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to {client_id}: {e}")
                disconnected_clients.append(client_id)
        
        # Remove disconnected clients
        for client_id in disconnected_clients:
            await self.disconnect_client(client_id)
    
    async def acknowledge_alert(self, client_id: str, alert_id: str):
        """Acknowledge alert"""
        try:
            # Find and update alert
            for alert in self.alerts:
                if alert.id == alert_id:
                    alert.acknowledged = True
                    break
            
            # Broadcast acknowledgment
            ack_data = {
                'type': 'alert_acknowledged',
                'data': {
                    'alert_id': alert_id,
                    'acknowledged_by': client_id,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            }
            
            await self._broadcast_message(ack_data)
            
        except Exception as e:
            logger.error(f"Failed to acknowledge alert {alert_id}: {e}")
    
    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get dashboard summary"""
        try:
            # Calculate overall system health
            total_health = sum(m.health_score for m in self.integration_metrics.values())
            avg_health = total_health / len(self.integration_metrics) if self.integration_metrics else 0
            
            # Count active alerts
            active_alerts = [a for a in self.alerts if not a.acknowledged]
            critical_alerts = [a for a in active_alerts if a.type == 'critical']
            
            # Count integrations by status
            status_counts = defaultdict(int)
            for metrics in self.integration_metrics.values():
                status_counts[metrics.status] += 1
            
            return {
                'overall_health_score': avg_health,
                'total_integrations': len(self.integration_metrics),
                'connected_clients': len(self.connected_clients),
                'active_alerts': len(active_alerts),
                'critical_alerts': len(critical_alerts),
                'integration_status': dict(status_counts),
                'last_update': datetime.now(timezone.utc).isoformat(),
                'ai_predictions_active': len(self.ai_predictions) > 0,
                'system_risk_score': self.system_prediction.overall_risk_score if self.system_prediction else 0.0
            }
            
        except Exception as e:
            logger.error(f"Failed to get dashboard summary: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

# Global dashboard instance
dashboard: Optional[RealTimeDashboard] = None

def get_dashboard() -> RealTimeDashboard:
    """Get global dashboard instance"""
    global dashboard
    if dashboard is None:
        dashboard = RealTimeDashboard()
    return dashboard

async def initialize_dashboard():
    """Initialize real-time dashboard"""
    try:
        global dashboard
        dashboard = get_dashboard()
        
        # Start monitoring
        await dashboard.start_monitoring()
        
        logger.info("Real-time dashboard initialized")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize dashboard: {e}")
        return False