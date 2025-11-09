#!/usr/bin/env python3
"""
AI-Powered Dashboard API Routes
FastAPI routes for real-time dashboard with AI predictions
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
import json

from realtime_dashboard import get_dashboard, DashboardClient
from ai_error_prediction import get_ai_predictor

logger = logging.getLogger(__name__)

# Create router
dashboard_router = APIRouter(prefix="/api/v2/dashboard", tags=["dashboard"])

# HTML template for dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 AI-Powered Integration Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .integration-card { transition: all 0.3s ease; }
        .integration-card:hover { transform: translateY(-2px); box-shadow: 0 8px 16px rgba(0,0,0,0.1); }
        .status-healthy { border-left: 4px solid #10b981; }
        .status-degraded { border-left: 4px solid #f59e0b; }
        .status-unhealthy { border-left: 4px solid #ef4444; }
        .alert-critical { animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
        .metric-value { font-size: 2rem; font-weight: bold; }
        .prediction-high { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); }
        .prediction-medium { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); }
        .prediction-low { background: linear-gradient(135deg, #10b981 0%, #059669 100%); }
    </style>
</head>
<body class="bg-gray-50">
    <!-- Header -->
    <div class="bg-gradient-to-r from-blue-600 to-purple-600 text-white p-6">
        <div class="max-w-7xl mx-auto">
            <h1 class="text-3xl font-bold mb-2">
                <i class="fas fa-robot mr-2"></i>AI-Powered Integration Dashboard
            </h1>
            <p class="opacity-90">Real-time monitoring with intelligent failure prediction</p>
        </div>
    </div>

    <!-- Main Content -->
    <div class="max-w-7xl mx-auto p-6">
        <!-- System Overview -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div class="bg-white rounded-lg p-6 shadow-sm">
                <div class="text-sm text-gray-600 mb-1">System Health</div>
                <div id="system-health" class="metric-value text-green-600">--%</div>
                <div id="system-trend" class="text-sm text-gray-500 mt-1">--</div>
            </div>
            <div class="bg-white rounded-lg p-6 shadow-sm">
                <div class="text-sm text-gray-600 mb-1">Active Integrations</div>
                <div id="active-integrations" class="metric-value text-blue-600">--/6</div>
                <div class="text-sm text-gray-500 mt-1">Connected</div>
            </div>
            <div class="bg-white rounded-lg p-6 shadow-sm">
                <div class="text-sm text-gray-600 mb-1">AI Risk Score</div>
                <div id="ai-risk-score" class="metric-value text-orange-600">--</div>
                <div id="risk-trend" class="text-sm text-gray-500 mt-1">--</div>
            </div>
            <div class="bg-white rounded-lg p-6 shadow-sm">
                <div class="text-sm text-gray-600 mb-1">Active Alerts</div>
                <div id="active-alerts" class="metric-value text-red-600">--</div>
                <div id="critical-alerts" class="text-sm text-gray-500 mt-1">-- critical</div>
            </div>
        </div>

        <!-- AI Predictions Section -->
        <div class="bg-white rounded-lg p-6 shadow-sm mb-6">
            <h2 class="text-xl font-semibold mb-4">
                <i class="fas fa-brain mr-2 text-purple-600"></i>AI Predictions
            </h2>
            <div id="ai-predictions" class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <!-- AI predictions will be populated here -->
            </div>
        </div>

        <!-- Integration Cards -->
        <div class="mb-6">
            <h2 class="text-xl font-semibold mb-4">
                <i class="fas fa-plug mr-2 text-blue-600"></i>Integration Status
            </h2>
            <div id="integration-cards" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <!-- Integration cards will be populated here -->
            </div>
        </div>

        <!-- Charts Section -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <div class="bg-white rounded-lg p-6 shadow-sm">
                <h3 class="text-lg font-semibold mb-4">Performance Trends</h3>
                <canvas id="performance-chart" width="400" height="200"></canvas>
            </div>
            <div class="bg-white rounded-lg p-6 shadow-sm">
                <h3 class="text-lg font-semibold mb-4">Error Rates</h3>
                <canvas id="error-chart" width="400" height="200"></canvas>
            </div>
        </div>

        <!-- Alerts Section -->
        <div class="bg-white rounded-lg p-6 shadow-sm">
            <h2 class="text-xl font-semibold mb-4">
                <i class="fas fa-exclamation-triangle mr-2 text-yellow-600"></i>Active Alerts
            </h2>
            <div id="alerts-container" class="space-y-2">
                <!-- Alerts will be populated here -->
            </div>
        </div>
    </div>

    <!-- Floating Notification -->
    <div id="notification" class="fixed bottom-4 right-4 bg-white rounded-lg shadow-lg p-4 hidden max-w-sm">
        <div class="flex items-center">
            <i id="notification-icon" class="fas fa-info-circle text-blue-500 mr-3 text-xl"></i>
            <div>
                <div id="notification-title" class="font-semibold"></div>
                <div id="notification-message" class="text-sm text-gray-600"></div>
            </div>
        </div>
    </div>

    <script>
        class AIDashboard {
            constructor() {
                this.ws = null;
                this.integrations = {};
                this.predictions = {};
                this.alerts = [];
                this.charts = {};
                
                this.initWebSocket();
                this.initCharts();
            }

            initWebSocket() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/api/v2/dashboard/ws`;
                
                this.ws = new WebSocket(wsUrl);
                
                this.ws.onopen = () => {
                    console.log('Connected to AI dashboard');
                    this.showNotification('Connected', 'Real-time monitoring active', 'success');
                };
                
                this.ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                };
                
                this.ws.onclose = () => {
                    console.log('Disconnected from AI dashboard');
                    this.showNotification('Disconnected', 'Attempting to reconnect...', 'warning');
                    setTimeout(() => this.initWebSocket(), 5000);
                };
            }

            handleMessage(data) {
                switch(data.type) {
                    case 'initial_metrics':
                        this.integrations = this.processMetrics(data.data);
                        this.updateIntegrationCards();
                        this.updateSystemOverview();
                        break;
                    case 'initial_predictions':
                        this.predictions = data.data.integrations;
                        this.updateAIPredictions();
                        break;
                    case 'metrics_update':
                        this.updateMetrics(data.data);
                        break;
                    case 'predictions_update':
                        this.predictions = data.data.integrations;
                        this.updateAIPredictions();
                        break;
                    case 'alert':
                        this.alerts.unshift(data.data);
                        this.updateAlerts();
                        this.showNotification(data.data.title, data.data.message, data.data.type);
                        break;
                }
            }

            processMetrics(metricsData) {
                const integrations = {};
                for (const [name, metrics] of Object.entries(metricsData)) {
                    integrations[name] = {
                        ...metrics,
                        last_update: new Date(metrics.last_update)
                    };
                }
                return integrations;
            }

            updateMetrics(metricsData) {
                this.integrations = this.processMetrics(metricsData);
                this.updateIntegrationCards();
                this.updateSystemOverview();
                this.updateCharts();
            }

            updateIntegrationCards() {
                const container = document.getElementById('integration-cards');
                container.innerHTML = '';

                for (const [name, integration] of Object.entries(this.integrations)) {
                    const statusClass = integration.status === 'healthy' ? 'status-healthy' :
                                     integration.status === 'degraded' ? 'status-degraded' : 'status-unhealthy';
                    
                    const statusIcon = integration.status === 'healthy' ? 'fa-check-circle text-green-500' :
                                      integration.status === 'degraded' ? 'fa-exclamation-triangle text-yellow-500' : 'fa-times-circle text-red-500';
                    
                    const healthColor = integration.health_score >= 80 ? 'text-green-600' :
                                      integration.health_score >= 50 ? 'text-yellow-600' : 'text-red-600';

                    const card = document.createElement('div');
                    card.className = `integration-card bg-white rounded-lg p-6 shadow-sm ${statusClass}`;
                    card.innerHTML = `
                        <div class="flex justify-between items-start mb-4">
                            <h3 class="text-lg font-semibold">${name.charAt(0).toUpperCase() + name.slice(1)}</h3>
                            <i class="fas ${statusIcon}"></i>
                        </div>
                        <div class="space-y-2">
                            <div class="flex justify-between">
                                <span class="text-sm text-gray-600">Health Score</span>
                                <span class="font-semibold ${healthColor}">${integration.health_score.toFixed(1)}%</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-sm text-gray-600">Response Time</span>
                                <span class="font-semibold">${integration.response_time.toFixed(0)}ms</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-sm text-gray-600">Error Rate</span>
                                <span class="font-semibold">${(integration.error_rate * 100).toFixed(1)}%</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-sm text-gray-600">Status</span>
                                <span class="font-semibold capitalize">${integration.status}</span>
                            </div>
                        </div>
                        <div class="mt-4 text-xs text-gray-500">
                            Last update: ${integration.last_update.toLocaleTimeString()}
                        </div>
                    `;
                    
                    container.appendChild(card);
                }
            }

            updateAIPredictions() {
                const container = document.getElementById('ai-predictions');
                container.innerHTML = '';

                for (const [name, prediction] of Object.entries(this.predictions)) {
                    if (!prediction) continue;

                    const riskClass = prediction.failure_probability > 0.8 ? 'prediction-high' :
                                    prediction.failure_probability > 0.5 ? 'prediction-medium' : 'prediction-low';
                    
                    const riskIcon = prediction.failure_probability > 0.8 ? 'fa-exclamation-triangle' :
                                    prediction.failure_probability > 0.5 ? 'fa-exclamation-circle' : 'fa-check-circle';

                    const card = document.createElement('div');
                    card.className = `${riskClass} text-white rounded-lg p-4`;
                    card.innerHTML = `
                        <div class="flex items-center mb-2">
                            <i class="fas ${riskIcon} mr-2"></i>
                            <h4 class="font-semibold">${name.charAt(0).toUpperCase() + name.slice(1)}</h4>
                        </div>
                        <div class="text-2xl font-bold mb-2">${(prediction.failure_probability * 100).toFixed(1)}%</div>
                        <div class="text-sm opacity-90">
                            ${prediction.predicted_failure_type}
                            ${prediction.time_to_failure ? `• ${prediction.time_to_failure}min` : ''}
                        </div>
                        <div class="text-xs opacity-75 mt-2">
                            Confidence: ${(prediction.confidence * 100).toFixed(1)}%
                        </div>
                    `;
                    
                    container.appendChild(card);
                }
            }

            updateSystemOverview() {
                // Calculate system health
                const healthScores = Object.values(this.integrations).map(i => i.health_score);
                const avgHealth = healthScores.length > 0 ? healthScores.reduce((a, b) => a + b) / healthScores.length : 0;
                
                // Count active integrations
                const activeCount = Object.values(this.integrations).filter(i => i.status !== 'unhealthy').length;
                
                // Count alerts
                const criticalAlerts = this.alerts.filter(a => a.type === 'critical').length;

                // Update UI
                document.getElementById('system-health').textContent = `${avgHealth.toFixed(1)}%`;
                document.getElementById('system-health').className = `metric-value ${avgHealth >= 80 ? 'text-green-600' : avgHealth >= 50 ? 'text-yellow-600' : 'text-red-600'}`;
                
                document.getElementById('active-integrations').textContent = `${activeCount}/6`;
                
                document.getElementById('ai-risk-score').textContent = `${(avgHealth * (1 - avgHealth/100) * 100).toFixed(0)}`;
                
                document.getElementById('active-alerts').textContent = this.alerts.length;
                document.getElementById('critical-alerts').textContent = `${criticalAlerts} critical`;
            }

            updateAlerts() {
                const container = document.getElementById('alerts-container');
                container.innerHTML = '';

                const recentAlerts = this.alerts.slice(0, 10);
                
                for (const alert of recentAlerts) {
                    const alertClass = alert.type === 'critical' ? 'alert-critical border-red-500 bg-red-50' :
                                    alert.type === 'error' ? 'border-red-400 bg-red-50' :
                                    alert.type === 'warning' ? 'border-yellow-400 bg-yellow-50' : 'border-blue-400 bg-blue-50';
                    
                    const alertIcon = alert.type === 'critical' ? 'fa-exclamation-triangle text-red-500' :
                                    alert.type === 'error' ? 'fa-times-circle text-red-500' :
                                    alert.type === 'warning' ? 'fa-exclamation-triangle text-yellow-500' : 'fa-info-circle text-blue-500';

                    const alertElement = document.createElement('div');
                    alertElement.className = `border rounded-lg p-4 ${alertClass}`;
                    alertElement.innerHTML = `
                        <div class="flex items-start">
                            <i class="fas ${alertIcon} mr-3 mt-1"></i>
                            <div class="flex-1">
                                <div class="flex justify-between items-start">
                                    <h4 class="font-semibold">${alert.title}</h4>
                                    <span class="text-xs text-gray-500">${new Date(alert.timestamp).toLocaleTimeString()}</span>
                                </div>
                                <p class="text-sm mt-1">${alert.message}</p>
                                ${alert.integration ? `<p class="text-xs text-gray-600 mt-1">Integration: ${alert.integration}</p>` : ''}
                            </div>
                        </div>
                    `;
                    
                    container.appendChild(alertElement);
                }
            }

            showNotification(title, message, type = 'info') {
                const notification = document.getElementById('notification');
                const icon = document.getElementById('notification-icon');
                const titleElement = document.getElementById('notification-title');
                const messageElement = document.getElementById('notification-message');

                // Set icon and color based on type
                const iconConfig = {
                    success: { icon: 'fa-check-circle', color: 'text-green-500' },
                    warning: { icon: 'fa-exclamation-triangle', color: 'text-yellow-500' },
                    error: { icon: 'fa-times-circle', color: 'text-red-500' },
                    info: { icon: 'fa-info-circle', color: 'text-blue-500' }
                };

                const config = iconConfig[type] || iconConfig.info;
                icon.className = `fas ${config.icon} ${config.color} mr-3 text-xl`;
                titleElement.textContent = title;
                messageElement.textContent = message;

                // Show notification
                notification.classList.remove('hidden');
                
                // Hide after 5 seconds
                setTimeout(() => {
                    notification.classList.add('hidden');
                }, 5000);
            }

            initCharts() {
                // Performance chart
                const performanceCtx = document.getElementById('performance-chart').getContext('2d');
                this.charts.performance = new Chart(performanceCtx, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: 'Avg Response Time',
                            data: [],
                            borderColor: 'rgb(59, 130, 246)',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            y: { beginAtZero: true }
                        }
                    }
                });

                // Error rate chart
                const errorCtx = document.getElementById('error-chart').getContext('2d');
                this.charts.errors = new Chart(errorCtx, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: 'Error Rate',
                            data: [],
                            borderColor: 'rgb(239, 68, 68)',
                            backgroundColor: 'rgba(239, 68, 68, 0.1)',
                            tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            y: { beginAtZero: true, max: 1 }
                        }
                    }
                });
            }

            updateCharts() {
                // Update chart data with current metrics
                const timestamp = new Date().toLocaleTimeString();
                const avgResponseTime = Object.values(this.integrations).reduce((sum, i) => sum + i.response_time, 0) / Object.keys(this.integrations).length;
                const avgErrorRate = Object.values(this.integrations).reduce((sum, i) => sum + i.error_rate, 0) / Object.keys(this.integrations).length;

                // Add new data points
                if (this.charts.performance.data.labels.length > 20) {
                    this.charts.performance.data.labels.shift();
                    this.charts.performance.data.datasets[0].data.shift();
                }
                this.charts.performance.data.labels.push(timestamp);
                this.charts.performance.data.datasets[0].data.push(avgResponseTime);
                this.charts.performance.update();

                if (this.charts.errors.data.labels.length > 20) {
                    this.charts.errors.data.labels.shift();
                    this.charts.errors.data.datasets[0].data.shift();
                }
                this.charts.errors.data.labels.push(timestamp);
                this.charts.errors.data.datasets[0].data.push(avgErrorRate);
                this.charts.errors.update();
            }
        }

        // Initialize dashboard when page loads
        document.addEventListener('DOMContentLoaded', () => {
            new AIDashboard();
        });
    </script>
</body>
</html>
"""

@dashboard_router.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve AI-powered dashboard HTML"""
    return DASHBOARD_HTML

@dashboard_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard"""
    dashboard = get_dashboard()
    
    try:
        client_id = await dashboard.connect_client(websocket, {
            'user_agent': websocket.headers.get('user-agent', 'unknown'),
            'connected_at': datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"Dashboard client {client_id} connected")
        
        # Keep connection alive
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_json()
                
                # Handle client messages
                if data.get('type') == 'heartbeat':
                    # Update client heartbeat
                    if client_id in dashboard.connected_clients:
                        dashboard.connected_clients[client_id].last_heartbeat = datetime.now(timezone.utc)
                
                elif data.get('type') == 'acknowledge_alert':
                    # Handle alert acknowledgment
                    alert_id = data.get('alert_id')
                    if alert_id:
                        await dashboard.acknowledge_alert(client_id, alert_id)
                
                elif data.get('type') == 'subscribe'):
                    # Handle subscription updates
                    subscriptions = data.get('subscriptions', [])
                    if client_id in dashboard.connected_clients:
                        dashboard.connected_clients[client_id].subscriptions = set(subscriptions)
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error for client {client_id}: {e}")
                break
    
    except WebSocketDisconnect:
        logger.info(f"Dashboard client {client_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        await dashboard.disconnect_client(client_id)

@dashboard_router.get("/summary")
async def get_dashboard_summary():
    """Get dashboard summary"""
    try:
        dashboard = get_dashboard()
        summary = dashboard.get_dashboard_summary()
        
        return {
            "status": "success",
            "data": summary,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get dashboard summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/metrics")
async def get_integration_metrics():
    """Get current integration metrics"""
    try:
        dashboard = get_dashboard()
        
        metrics_data = {
            integration: {
                'name': metrics.integration,
                'status': metrics.status,
                'health_score': metrics.health_score,
                'response_time': metrics.response_time,
                'request_rate': metrics.request_rate,
                'error_rate': metrics.error_rate,
                'last_update': metrics.last_update.isoformat(),
                'uptime_percentage': metrics.uptime_percentage,
                'active_connections': metrics.active_connections,
                'error_count': metrics.error_count,
                'success_count': metrics.success_count,
                'total_requests': metrics.total_requests
            }
            for integration, metrics in dashboard.integration_metrics.items()
        }
        
        return {
            "status": "success",
            "data": metrics_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get integration metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/predictions")
async def get_ai_predictions():
    """Get current AI predictions"""
    try:
        dashboard = get_dashboard()
        predictor = get_ai_predictor()
        
        predictions_data = {
            'integrations': {
                integration: {
                    'failure_probability': pred.failure_probability,
                    'predicted_failure_type': pred.predicted_failure_type,
                    'confidence': pred.confidence,
                    'time_to_failure': pred.time_to_failure,
                    'risk_factors': pred.risk_factors,
                    'suggested_actions': pred.suggested_actions,
                    'timestamp': pred.timestamp,
                    'model_version': pred.model_version
                }
                for integration, pred in dashboard.ai_predictions.items()
            },
            'system': {
                'overall_risk_score': dashboard.system_prediction.overall_risk_score if dashboard.system_prediction else 0.0,
                'high_risk_integrations': dashboard.system_prediction.high_risk_integrations if dashboard.system_prediction else [],
                'predicted_downtime_minutes': dashboard.system_prediction.predicted_downtime_minutes if dashboard.system_prediction else None,
                'system_stability_trend': dashboard.system_prediction.system_stability_trend if dashboard.system_prediction else 'unknown',
                'recommendations': dashboard.system_prediction.recommendations if dashboard.system_prediction else [],
                'timestamp': dashboard.system_prediction.timestamp if dashboard.system_prediction else datetime.now(timezone.utc).isoformat()
            },
            'model_info': {
                'model_version': predictor.model_version,
                'last_training_time': predictor.last_training_time,
                'total_predictions': predictor.prediction_count,
                'training_data_size': len(predictor.training_data)
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return {
            "status": "success",
            "data": predictions_data
        }
        
    except Exception as e:
        logger.error(f"Failed to get AI predictions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/alerts")
async def get_active_alerts():
    """Get active alerts"""
    try:
        dashboard = get_dashboard()
        
        alerts_data = {
            'alerts': [
                {
                    'id': alert.id,
                    'type': alert.type,
                    'integration': alert.integration,
                    'title': alert.title,
                    'message': alert.message,
                    'timestamp': alert.timestamp.isoformat(),
                    'acknowledged': alert.acknowledged,
                    'metadata': alert.metadata
                }
                for alert in dashboard.alerts
            ],
            'summary': {
                'total_alerts': len(dashboard.alerts),
                'critical_alerts': len([a for a in dashboard.alerts if a.type == 'critical']),
                'error_alerts': len([a for a in dashboard.alerts if a.type == 'error']),
                'warning_alerts': len([a for a in dashboard.alerts if a.type == 'warning']),
                'unacknowledged_alerts': len([a for a in dashboard.alerts if not a.acknowledged])
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return {
            "status": "success",
            "data": alerts_data
        }
        
    except Exception as e:
        logger.error(f"Failed to get active alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge an alert"""
    try:
        dashboard = get_dashboard()
        
        # Find alert
        alert = None
        for a in dashboard.alerts:
            if a.id == alert_id:
                alert = a
                break
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Acknowledge alert
        alert.acknowledged = True
        
        # Broadcast acknowledgment
        ack_data = {
            'type': 'alert_acknowledged',
            'data': {
                'alert_id': alert_id,
                'acknowledged': True,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }
        
        await dashboard._broadcast_message(ack_data)
        
        return {
            "status": "success",
            "message": f"Alert {alert_id} acknowledged",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to acknowledge alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/model/performance")
async def get_model_performance():
    """Get AI model performance metrics"""
    try:
        predictor = get_ai_predictor()
        performance = await predictor.evaluate_model_performance()
        
        performance_data = {
            'prediction_accuracy': performance.prediction_accuracy,
            'false_positive_rate': performance.false_positive_rate,
            'false_negative_rate': performance.false_negative_rate,
            'precision': performance.precision,
            'recall': performance.recall,
            'f1_score': performance.f1_score,
            'model_confidence': performance.model_confidence,
            'model_version': predictor.model_version,
            'last_training_time': predictor.last_training_time,
            'total_predictions': predictor.prediction_count,
            'training_data_size': len(predictor.training_data),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return {
            "status": "success",
            "data": performance_data
        }
        
    except Exception as e:
        logger.error(f"Failed to get model performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.post("/train")
async def train_models():
    """Trigger AI model training"""
    try:
        predictor = get_ai_predictor()
        success = await predictor.train_models(force_retrain=True)
        
        return {
            "status": "success" if success else "failed",
            "message": "Model training completed" if success else "Model training failed",
            "model_version": predictor.model_version,
            "last_training_time": predictor.last_training_time,
            "training_data_size": len(predictor.training_data),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to train models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@dashboard_router.get("/clients")
async def get_connected_clients():
    """Get information about connected dashboard clients"""
    try:
        dashboard = get_dashboard()
        
        clients_data = {
            'total_clients': len(dashboard.connected_clients),
            'clients': [
                {
                    'client_id': client.client_id,
                    'connected_at': client.connected_at.isoformat(),
                    'last_heartbeat': client.last_heartbeat.isoformat(),
                    'subscriptions': list(client.subscriptions),
                    'client_info': client.client_info
                }
                for client in dashboard.connected_clients.values()
            ],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return {
            "status": "success",
            "data": clients_data
        }
        
    except Exception as e:
        logger.error(f"Failed to get connected clients: {e}")
        raise HTTPException(status_code=500, detail=str(e))