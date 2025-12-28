"""
Phase 3 Performance Monitoring Dashboard
Real-time monitoring for AI-powered chat interface

Author: Atom Platform Engineering
Date: November 9, 2025
Version: 1.0.0
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


class SystemMetrics(BaseModel):
    timestamp: str
    phase3_ai_response_time: float
    main_chat_response_time: float
    websocket_response_time: float
    active_conversations: int
    total_messages_processed: int
    ai_analysis_utilization: float
    sentiment_distribution: Dict[str, float]
    error_rate: float
    system_load: float


class HealthStatus(BaseModel):
    service: str
    status: str
    response_time: float
    last_check: str
    features: Dict[str, bool]


class PerformanceAlert(BaseModel):
    alert_id: str
    severity: str
    service: str
    message: str
    timestamp: str
    metric: str
    threshold: float
    current_value: float


class Phase3MonitoringDashboard:
    def __init__(self):
        self.base_urls = {
            "phase3_ai": "http://localhost:5062",
            "main_chat": "http://localhost:8000",
            "websocket": "http://localhost:5060",
        }

        # Performance metrics storage
        self.metrics_history: List[SystemMetrics] = []
        self.health_status: Dict[str, HealthStatus] = {}
        self.active_alerts: List[PerformanceAlert] = []
        self.performance_thresholds = {
            "phase3_response_time": 100,  # ms
            "main_chat_response_time": 200,  # ms
            "websocket_response_time": 50,  # ms
            "error_rate": 0.05,  # 5%
            "system_load": 0.8,  # 80%
        }

        # Statistics
        self.total_messages = 0
        self.ai_analyses_performed = 0
        self.errors_encountered = 0

        # WebSocket connections for real-time updates
        self.active_connections: List[WebSocket] = []

    async def check_service_health(self, service_name: str, url: str) -> HealthStatus:
        """Check health of a specific service"""
        start_time = time.time()
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/health", timeout=5) as response:
                    response_time = (time.time() - start_time) * 1000

                    if response.status == 200:
                        data = await response.json()
                        features = (
                            data.get("features", {})
                            if service_name == "phase3_ai"
                            else {}
                        )

                        return HealthStatus(
                            service=service_name,
                            status="healthy",
                            response_time=response_time,
                            last_check=datetime.now().isoformat(),
                            features=features,
                        )
                    else:
                        return HealthStatus(
                            service=service_name,
                            status="unhealthy",
                            response_time=response_time,
                            last_check=datetime.now().isoformat(),
                            features={},
                        )
        except Exception as e:
            return HealthStatus(
                service=service_name,
                status="unavailable",
                response_time=(time.time() - start_time) * 1000,
                last_check=datetime.now().isoformat(),
                features={},
            )

    async def collect_system_metrics(self) -> SystemMetrics:
        """Collect comprehensive system metrics"""
        # Check all services
        health_checks = await asyncio.gather(
            self.check_service_health("phase3_ai", self.base_urls["phase3_ai"]),
            self.check_service_health("main_chat", self.base_urls["main_chat"]),
            self.check_service_health("websocket", self.base_urls["websocket"]),
        )

        # Get conversation statistics from Phase 3
        active_conversations = 0
        sentiment_distribution = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                # Get analytics from Phase 3
                async with session.get(
                    f"{self.base_urls['phase3_ai']}/api/v1/analytics/overview",
                    timeout=5,
                ) as response:
                    if response.status == 200:
                        analytics = await response.json()
                        active_conversations = analytics.get("total_conversations", 0)
                        self.total_messages = analytics.get("total_messages", 0)
                        self.ai_analyses_performed = analytics.get(
                            "total_ai_analyses", 0
                        )
        except:
            pass  # Use default values if analytics unavailable

        # Calculate utilization and error rates
        ai_utilization = (
            (self.ai_analyses_performed / self.total_messages)
            if self.total_messages > 0
            else 0
        )
        error_rate = self.errors_encountered / (
            self.total_messages + 1
        )  # +1 to avoid division by zero

        # Estimate system load based on response times
        system_load = min(
            1.0,
            (
                health_checks[0].response_time
                / self.performance_thresholds["phase3_response_time"]
                + health_checks[1].response_time
                / self.performance_thresholds["main_chat_response_time"]
            )
            / 2,
        )

        metrics = SystemMetrics(
            timestamp=datetime.now().isoformat(),
            phase3_ai_response_time=health_checks[0].response_time,
            main_chat_response_time=health_checks[1].response_time,
            websocket_response_time=health_checks[2].response_time,
            active_conversations=active_conversations,
            total_messages_processed=self.total_messages,
            ai_analysis_utilization=ai_utilization,
            sentiment_distribution=sentiment_distribution,
            error_rate=error_rate,
            system_load=system_load,
        )

        # Store metrics (keep last 1000 records)
        self.metrics_history.append(metrics)
        if len(self.metrics_history) > 1000:
            self.metrics_history.pop(0)

        # Update health status
        for health_check in health_checks:
            self.health_status[health_check.service] = health_check

        # Check for performance alerts
        await self.check_performance_alerts(metrics)

        return metrics

    async def check_performance_alerts(self, metrics: SystemMetrics):
        """Check for performance threshold violations"""
        alerts_to_add = []

        # Check Phase 3 response time
        if (
            metrics.phase3_ai_response_time
            > self.performance_thresholds["phase3_response_time"]
        ):
            alerts_to_add.append(
                PerformanceAlert(
                    alert_id=f"alert_{int(time.time())}",
                    severity="warning",
                    service="phase3_ai",
                    message="High response time detected",
                    timestamp=datetime.now().isoformat(),
                    metric="phase3_response_time",
                    threshold=self.performance_thresholds["phase3_response_time"],
                    current_value=metrics.phase3_ai_response_time,
                )
            )

        # Check main chat response time
        if (
            metrics.main_chat_response_time
            > self.performance_thresholds["main_chat_response_time"]
        ):
            alerts_to_add.append(
                PerformanceAlert(
                    alert_id=f"alert_{int(time.time())}",
                    severity="warning",
                    service="main_chat",
                    message="High response time detected",
                    timestamp=datetime.now().isoformat(),
                    metric="main_chat_response_time",
                    threshold=self.performance_thresholds["main_chat_response_time"],
                    current_value=metrics.main_chat_response_time,
                )
            )

        # Check error rate
        if metrics.error_rate > self.performance_thresholds["error_rate"]:
            alerts_to_add.append(
                PerformanceAlert(
                    alert_id=f"alert_{int(time.time())}",
                    severity="error",
                    service="system",
                    message="High error rate detected",
                    timestamp=datetime.now().isoformat(),
                    metric="error_rate",
                    threshold=self.performance_thresholds["error_rate"],
                    current_value=metrics.error_rate,
                )
            )

        # Check system load
        if metrics.system_load > self.performance_thresholds["system_load"]:
            alerts_to_add.append(
                PerformanceAlert(
                    alert_id=f"alert_{int(time.time())}",
                    severity="warning",
                    service="system",
                    message="High system load detected",
                    timestamp=datetime.now().isoformat(),
                    metric="system_load",
                    threshold=self.performance_thresholds["system_load"],
                    current_value=metrics.system_load,
                )
            )

        # Add new alerts and notify connected clients
        for alert in alerts_to_add:
            self.active_alerts.append(alert)
            await self.broadcast_alert(alert)

    async def broadcast_metrics(self, metrics: SystemMetrics):
        """Broadcast metrics to all connected WebSocket clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(
                    {"type": "metrics_update", "data": metrics.dict()}
                )
            except:
                disconnected.append(connection)

        # Remove disconnected clients
        for connection in disconnected:
            self.active_connections.remove(connection)

    async def broadcast_alert(self, alert: PerformanceAlert):
        """Broadcast alert to all connected WebSocket clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(
                    {"type": "performance_alert", "data": alert.dict()}
                )
            except:
                disconnected.append(connection)

        # Remove disconnected clients
        for connection in disconnected:
            self.active_connections.remove(connection)

    async def connect_websocket(self, websocket: WebSocket):
        """Handle new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)

        # Send current metrics and alerts
        if self.metrics_history:
            await websocket.send_json(
                {"type": "metrics_update", "data": self.metrics_history[-1].dict()}
            )

        if self.active_alerts:
            await websocket.send_json(
                {
                    "type": "alerts_snapshot",
                    "data": [
                        alert.dict() for alert in self.active_alerts[-10:]
                    ],  # Last 10 alerts
                }
            )

    def disconnect_websocket(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    def get_performance_summary(self, hours: int = 24) -> Dict:
        """Get performance summary for the specified time period"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [
            m
            for m in self.metrics_history
            if datetime.fromisoformat(m.timestamp) > cutoff_time
        ]

        if not recent_metrics:
            return {}

        # Calculate averages and trends
        avg_phase3_response = sum(
            m.phase3_ai_response_time for m in recent_metrics
        ) / len(recent_metrics)
        avg_main_chat_response = sum(
            m.main_chat_response_time for m in recent_metrics
        ) / len(recent_metrics)
        avg_websocket_response = sum(
            m.websocket_response_time for m in recent_metrics
        ) / len(recent_metrics)
        avg_ai_utilization = sum(
            m.ai_analysis_utilization for m in recent_metrics
        ) / len(recent_metrics)
        avg_error_rate = sum(m.error_rate for m in recent_metrics) / len(recent_metrics)

        # Calculate trends (comparing first half to second half)
        midpoint = len(recent_metrics) // 2
        if midpoint > 0:
            first_half = recent_metrics[:midpoint]
            second_half = recent_metrics[midpoint:]

            phase3_trend = sum(m.phase3_ai_response_time for m in second_half) / len(
                second_half
            ) - sum(m.phase3_ai_response_time for m in first_half) / len(first_half)
            utilization_trend = sum(
                m.ai_analysis_utilization for m in second_half
            ) / len(second_half) - sum(
                m.ai_analysis_utilization for m in first_half
            ) / len(first_half)
        else:
            phase3_trend = 0
            utilization_trend = 0

        return {
            "time_period_hours": hours,
            "metrics_count": len(recent_metrics),
            "average_response_times": {
                "phase3_ai": avg_phase3_response,
                "main_chat": avg_main_chat_response,
                "websocket": avg_websocket_response,
            },
            "average_utilization": avg_ai_utilization,
            "average_error_rate": avg_error_rate,
            "trends": {
                "phase3_response_time": phase3_trend,
                "ai_utilization": utilization_trend,
            },
            "threshold_violations": len(
                [
                    alert
                    for alert in self.active_alerts
                    if datetime.fromisoformat(alert.timestamp) > cutoff_time
                ]
            ),
            "overall_health": "healthy" if avg_error_rate < 0.01 else "degraded",
        }


# Initialize FastAPI app and monitoring dashboard
app = FastAPI(
    title="Phase 3 Performance Monitoring Dashboard",
    description="Real-time monitoring for AI-powered chat interface",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize monitoring dashboard
monitor = Phase3MonitoringDashboard()


# HTML dashboard
dashboard_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Phase 3 Performance Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .dashboard { max-width: 1200px; margin: 0 auto; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .metric-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .alert-card { background: #fff3cd; border-left: 4px solid #ffc107; }
        .error-card { background: #f8d7da; border-left: 4px solid #dc3545; }
        .health-status { display: flex; align-items: center; gap: 10px; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; }
        .healthy { background: #28a745; }
        .unhealthy { background: #dc3545; }
        .chart-container { height: 200px; margin-top: 10px; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="dashboard">
        <h1>Phase 3 Performance Monitoring Dashboard</h1>

        <div class="metrics-grid">
            <div class="metric-card">
                <h3>System Health</h3>
                <div id="health-status"></div>
            </div>

            <div class="metric-card">
                <h3>Response Times</h3>
                <div id="response-times"></div>
                <div class="chart-container">
                    <canvas id="responseTimeChart"></canvas>
                </div>
            </div>

            <div class="metric-card">
                <h3>AI Utilization</h3>
                <div id="utilization-stats"></div>
                <div class="chart-container">
                    <canvas id="utilizationChart"></canvas>
                </div>
            </div>

            <div class="metric-card">
                <h3>Active Alerts</h3>
                <div id="alerts-container"></div>
            </div>
        </div>

        <div class="metric-card">
            <h3>Performance Summary (24h)</h3>
            <div id="performance-summary"></div>
        </div>
    </div>

    <script>
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        let metricsHistory = [];

        // Initialize charts
        const responseTimeCtx = document.getElementById('responseTimeChart').getContext('2d');
        const responseTimeChart = new Chart(responseTimeCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    { label: 'Phase 3 AI', data: [], borderColor: 'rgb(75, 192, 192)', tension: 0.1 },
                    { label: 'Main Chat', data: [], borderColor: 'rgb(54, 162, 235)', tension: 0.1 },
                    { label: 'WebSocket', data: [], borderColor: 'rgb(153, 102, 255)', tension: 0.1 }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });

        const utilizationCtx = document.getElementById('utilizationChart').getContext('2d');
        const utilizationChart = new Chart(utilizationCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    { label: 'AI Utilization', data: [], borderColor: 'rgb(255, 159, 64)', tension: 0.1 }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });

        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);

            if (data.type === 'metrics_update') {
                updateMetrics(data.data);
            } else if (data.type === 'performance_alert') {
                addAlert(data.data);
            } else if (data.type === 'alerts_snapshot') {
                data.data.forEach(addAlert);
            }
        };

        function updateMetrics(metrics) {
            // Update health status
            document.getElementById('health-status').innerHTML = `
                <div class="health-status">
                    <div class="status-dot healthy"></div>
                    <span>All Systems Operational</span>
                </div>
                <p>Last Updated: ${new Date().toLocaleTimeString()}</p>
            `;

            // Update response times
            document.getElementById('response-times').innerHTML = `
                <p>Phase 3 AI: <strong>${metrics.phase3_ai_response_time.toFixed(2)}ms</strong></p>
                <p>Main Chat: <strong>${metrics.main_chat_response_time.toFixed(2)}ms</strong></p>
                <p>WebSocket: <strong>${metrics.websocket_response_time.toFixed(2)}ms</strong></p>
            `;

            // Update utilization stats
            document.getElementById('utilization-stats').innerHTML = `
                <p>AI Utilization: <strong>${(metrics.ai_analysis_utilization * 100).toFixed(1)}%</strong></p>
                <p>Active Conversations: <strong>${metrics.active_conversations}</strong></p>
                <p>Total Messages: <strong>${metrics.total_messages_processed}</strong></p>
            `;

            // Update charts
            updateCharts(metrics);
        }

        function updateCharts(metrics) {
            const now = new Date().toLocaleTimeString();

            // Update response time chart
            responseTimeChart.data.labels.push(now);
            responseTimeChart.data.datasets[0].data.push(metrics.phase3_ai_response_time);
            responseTimeChart.data.datasets[1].data.push(metrics.main_chat_response_time);
            responseTimeChart.data.datasets[2].data.push(metrics.websocket_response_time);

            // Update utilization chart
            utilizationChart.data.labels.push(now);
            utilizationChart.data.datasets[0].data.push(metrics.ai_analysis_utilization * 100);

            // Keep only last 20 data points
            if (responseTimeChart.data.labels.length > 20) {
                responseTimeChart.data.labels.shift();
                responseTimeChart.data.datasets.forEach(dataset => dataset.data.shift());
                utilizationChart.data.labels.shift();
                utilizationChart.data.datasets[0].data.shift();
            }

            responseTimeChart.update();
            utilizationChart.update();
        }

        function addAlert(alert) {
            const alertsContainer = document.getElementById('alerts-container');
            const alertClass = alert.severity === 'error' ? 'error-card' : 'alert-card';

            const alertElement = document.createElement('div');
            alertElement.className = `metric-card ${alertClass}`;
            alertElement.innerHTML = `
                <strong>${alert.severity.toUpperCase()}: ${alert.service}</strong>
                <p>${alert.message}</p>
                <small>${new Date(alert.timestamp).toLocaleString()}</small>
                <p>Current: ${alert.current_value.toFixed(2)} | Threshold: ${alert.threshold}</p>
            `;

            alertsContainer.insertBefore(alertElement, alertsContainer.firstChild);

            // Keep only last 5 alerts visible
            if (alertsContainer.children.length > 5) {
                alertsContainer.removeChild(alertsContainer.lastChild);
            }
        }

        // Load initial performance summary
        fetch('/api/performance/summary')
            .then(response => response.json())
            .then(data => {
                document.getElementById('performance-summary').innerHTML = `
                    <p>Average Response Times:</p>
                    <ul>
                        <li>Phase 3 AI: ${data.average_response_times?.phase3_ai?.toFixed(2) || 'N/A'}ms</li>
                        <li>Main Chat: ${data.average_response_times?.main_chat?.toFixed(2) || 'N/A'}ms</li>
                        <li>WebSocket: ${data.average_response_times?.websocket?.toFixed(2) || 'N/A'}ms</li>
                    </ul>
                    <p>AI Utilization: ${(data.average_utilization * 100 || 0).toFixed(1)}%</p>
                    <p>Error Rate: ${(data.average_error_rate * 100 || 0).toFixed(1)}%</p>
                    <p>Threshold Violations: ${data.threshold_violations || 0}</p>
                    <p>Overall Health: <strong>${data.overall_health || 'unknown'}</strong></p>
                `;
            });

        // Auto-refresh performance summary every 30 seconds
        setInterval(() => {
            fetch('/api/performance/summary')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('performance-summary').innerHTML = `
                        <p>Average Response Times:</p>
                        <ul>
                            <li>Phase 3 AI: ${data.average_response_times?.phase3_ai?.toFixed(2) || 'N/A'}ms</li>
                            <li>Main Chat: ${data.average_response_times?.main_chat?.toFixed(2) || 'N/A'}ms</li>
                            <li>WebSocket: ${data.average_response_times?.websocket?.toFixed(2) || 'N/A'}ms</li>
                        </ul>
                        <p>AI Utilization: ${(data.average_utilization * 100 || 0).toFixed(1)}%</p>
                        <p>Error Rate: ${(data.average_error_rate * 100 || 0).toFixed(1)}%</p>
                        <p>Threshold Violations: ${data.threshold_violations || 0}</p>
                        <p>Overall Health: <strong>${data.overall_health || 'unknown'}</strong></p>
                    `;
                });
        }, 30000);
    </script>
</body>
</html>
"""


# FastAPI Routes
@app.get("/")
async def dashboard():
    """Serve the monitoring dashboard"""
    return HTMLResponse(dashboard_html)


@app.get("/api/health")
async def get_health_status():
    """Get current health status of all services"""
    return {
        "timestamp": datetime.now().isoformat(),
        "services": monitor.health_status,
        "overall_status": "healthy"
        if all(status.status == "healthy" for status in monitor.health_status.values())
        else "degraded",
    }


@app.get("/api/metrics/current")
async def get_current_metrics():
    """Get current system metrics"""
    if not monitor.metrics_history:
        await monitor.collect_system_metrics()

    if monitor.metrics_history:
        return monitor.metrics_history[-1]
    else:
        raise HTTPException(status_code=503, detail="No metrics available")


@app.get("/api/metrics/history")
async def get_metrics_history(hours: int = 24):
    """Get metrics history for specified time period"""
    cutoff_time = datetime.now() - timedelta(hours=hours)
    recent_metrics = [
        m
        for m in monitor.metrics_history
        if datetime.fromisoformat(m.timestamp) > cutoff_time
    ]
    return {
        "time_period_hours": hours,
        "metrics": recent_metrics,
        "count": len(recent_metrics),
    }


@app.get("/api/performance/summary")
async def get_performance_summary(hours: int = 24):
    """Get performance summary for specified time period"""
    return monitor.get_performance_summary(hours)


@app.get("/api/alerts")
async def get_active_alerts():
    """Get current active alerts"""
    return {
        "timestamp": datetime.now().isoformat(),
        "active_alerts": monitor.active_alerts[-20:],  # Last 20 alerts
        "total_active": len(monitor.active_alerts),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await monitor.connect_websocket(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        monitor.disconnect_websocket(websocket)


# Background task for continuous monitoring
async def continuous_monitoring():
    """Continuous monitoring loop"""
    while True:
        try:
            metrics = await monitor.collect_system_metrics()
            await monitor.broadcast_metrics(metrics)
        except Exception as e:
            logging.error(f"Monitoring error: {e}")

        # Wait before next collection
        await asyncio.sleep(10)  # Collect every 10 seconds


@app.on_event("startup")
async def startup_event():
    """Start background monitoring on startup"""
    logging.info("Starting Phase 3 Performance Monitoring Dashboard")
    asyncio.create_task(continuous_monitoring())


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logging.info("Shutting down Phase 3 Performance Monitoring Dashboard")


if __name__ == "__main__":
    uvicorn.run(
        "phase3_monitoring_dashboard:app",
        host="0.0.0.0",
        port=5063,
        reload=True,
        log_level="info",
    )
