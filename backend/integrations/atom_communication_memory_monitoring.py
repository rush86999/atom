"""
ATOM Communication Memory Production Monitoring System
Real-time monitoring, alerting, and performance tracking
"""

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import json
import logging
import time
from typing import Any, Dict, List, Optional

from integrations.atom_communication_ingestion_pipeline import ingestion_pipeline, memory_manager

logger = logging.getLogger(__name__)

@dataclass
class MonitoringMetric:
    """Monitoring metric data structure"""
    name: str
    value: float
    unit: str
    timestamp: datetime
    tags: Dict[str, str]
    threshold: Optional[float] = None

@dataclass
class Alert:
    """Alert data structure"""
    id: str
    severity: str  # info, warning, error, critical
    title: str
    message: str
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    tags: Dict[str, str]

class AtomCommunicationMemoryMonitoring:
    """Production monitoring system for ATOM communication memory"""
    
    def __init__(self):
        self.metrics: List[MonitoringMetric] = []
        self.alerts: List[Alert] = []
        self.is_running = False
        self.monitoring_interval = 60  # seconds
        self.alert_thresholds = {
            'ingestion_rate': 0.1,  # messages per second
            'error_rate': 0.05,  # 5% error rate
            'memory_usage': 0.8,  # 80% memory usage
            'search_latency': 1.0,  # 1 second
            'database_size': 100_000_000_000  # 100GB
        }
    
    async def start_monitoring(self):
        """Start the monitoring system"""
        self.is_running = True
        logger.info("Starting ATOM communication memory monitoring")
        
        while self.is_running:
            try:
                await self.collect_metrics()
                await self.check_alerts()
                await asyncio.sleep(self.monitoring_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                await asyncio.sleep(60)  # Wait longer on error
    
    def stop_monitoring(self):
        """Stop the monitoring system"""
        self.is_running = False
        logger.info("Stopping ATOM communication memory monitoring")
    
    async def collect_metrics(self):
        """Collect monitoring metrics"""
        try:
            timestamp = datetime.now()
            
            # Get ingestion stats
            stats = ingestion_pipeline.get_ingestion_stats()
            
            # Database metrics
            db_metrics = await self._collect_database_metrics(timestamp)
            
            # Ingestion metrics
            ingestion_metrics = await self._collect_ingestion_metrics(stats, timestamp)
            
            # Performance metrics
            performance_metrics = await self._collect_performance_metrics(timestamp)
            
            # Add all metrics
            self.metrics.extend(db_metrics + ingestion_metrics + performance_metrics)
            
            # Keep only last 24 hours of metrics
            cutoff_time = timestamp - timedelta(hours=24)
            self.metrics = [m for m in self.metrics if m.timestamp > cutoff_time]
            
            logger.info(f"Collected {len(db_metrics + ingestion_metrics + performance_metrics)} metrics")
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {str(e)}")
    
    async def _collect_database_metrics(self, timestamp: datetime) -> List[MonitoringMetric]:
        """Collect database-related metrics"""
        metrics = []
        
        try:
            if memory_manager.connections_table:
                # Get record count
                df = memory_manager.connections_table.to_pandas()
                record_count = len(df)
                
                metrics.append(MonitoringMetric(
                    name="database_record_count",
                    value=record_count,
                    unit="records",
                    timestamp=timestamp,
                    tags={"table": "atom_communications"},
                    threshold=self.alert_thresholds['database_size']
                ))
                
                # Get database size (estimated)
                estimated_size = record_count * 1024  # Estimate 1KB per record
                metrics.append(MonitoringMetric(
                    name="database_size",
                    value=estimated_size,
                    unit="bytes",
                    timestamp=timestamp,
                    tags={"table": "atom_communications"},
                    threshold=self.alert_thresholds['database_size']
                ))
                
                # App distribution
                app_dist = df["app_type"].value_counts().to_dict()
                for app, count in app_dist.items():
                    metrics.append(MonitoringMetric(
                        name=f"records_{app}",
                        value=count,
                        unit="records",
                        timestamp=timestamp,
                        tags={"app": app, "metric": "record_count"}
                    ))
        
        except Exception as e:
            logger.error(f"Error collecting database metrics: {str(e)}")
        
        return metrics
    
    async def _collect_ingestion_metrics(self, stats: Dict[str, Any], timestamp: datetime) -> List[MonitoringMetric]:
        """Collect ingestion-related metrics"""
        metrics = []
        
        try:
            # Total messages
            total_messages = stats.get('total_messages', 0)
            metrics.append(MonitoringMetric(
                name="total_messages_ingested",
                value=total_messages,
                unit="messages",
                timestamp=timestamp,
                tags={"metric": "total_ingestion"}
            ))
            
            # Active streams
            active_streams = len(stats.get('active_streams', []))
            metrics.append(MonitoringMetric(
                name="active_real_time_streams",
                value=active_streams,
                unit="streams",
                timestamp=timestamp,
                tags={"metric": "active_streams"}
            ))
            
            # Configured apps
            configured_apps = len(stats.get('configured_apps', []))
            metrics.append(MonitoringMetric(
                name="configured_apps",
                value=configured_apps,
                unit="apps",
                timestamp=timestamp,
                tags={"metric": "configured_apps"}
            ))
            
        except Exception as e:
            logger.error(f"Error collecting ingestion metrics: {str(e)}")
        
        return metrics
    
    async def _collect_performance_metrics(self, timestamp: datetime) -> List[MonitoringMetric]:
        """Collect performance-related metrics"""
        metrics = []
        
        try:
            # Ingestion rate (simplified)
            recent_metrics = [m for m in self.metrics 
                             if m.name == "total_messages_ingested" 
                             and (timestamp - m.timestamp).total_seconds() < 300]  # Last 5 minutes
            
            if len(recent_metrics) >= 2:
                recent_metrics.sort(key=lambda x: x.timestamp)
                latest_count = recent_metrics[-1].value
                earliest_count = recent_metrics[0].value
                time_diff = (recent_metrics[-1].timestamp - recent_metrics[0].timestamp).total_seconds()
                
                if time_diff > 0:
                    ingestion_rate = (latest_count - earliest_count) / time_diff
                    metrics.append(MonitoringMetric(
                        name="ingestion_rate",
                        value=ingestion_rate,
                        unit="messages/second",
                        timestamp=timestamp,
                        tags={"metric": "performance"},
                        threshold=self.alert_thresholds['ingestion_rate']
                    ))
            
            # Memory usage (simplified - would need actual monitoring)
            import psutil
            memory_percent = psutil.virtual_memory().percent / 100
            metrics.append(MonitoringMetric(
                name="memory_usage",
                value=memory_percent,
                unit="fraction",
                timestamp=timestamp,
                tags={"metric": "performance"},
                threshold=self.alert_thresholds['memory_usage']
            ))
            
        except Exception as e:
            logger.error(f"Error collecting performance metrics: {str(e)}")
        
        return metrics
    
    async def check_alerts(self):
        """Check thresholds and generate alerts"""
        try:
            timestamp = datetime.now()
            
            # Get latest metrics for each metric name
            latest_metrics = {}
            for metric in self.metrics:
                if metric.name not in latest_metrics or metric.timestamp > latest_metrics[metric.name].timestamp:
                    latest_metrics[metric.name] = metric
            
            # Check thresholds
            for metric_name, metric in latest_metrics.items():
                if metric.threshold and metric.value > metric.threshold:
                    await self._create_alert(
                        severity="warning",
                        title=f"Threshold exceeded for {metric_name}",
                        message=f"{metric_name}: {metric.value:.2f} {metric.unit} (threshold: {metric.threshold})",
                        timestamp=timestamp,
                        tags=metric.tags
                    )
            
            # Check for system health
            if not memory_manager.db:
                await self._create_alert(
                    severity="critical",
                    title="Database connection lost",
                    message="LanceDB database connection is not available",
                    timestamp=timestamp,
                    tags={"component": "database"}
                )
            
        except Exception as e:
            logger.error(f"Error checking alerts: {str(e)}")
    
    async def _create_alert(self, severity: str, title: str, message: str, 
                           timestamp: datetime, tags: Dict[str, str]):
        """Create a new alert"""
        alert_id = f"alert_{int(timestamp.timestamp())}_{len(self.alerts)}"
        
        # Check if similar alert already exists
        existing_alert = next((a for a in self.alerts if not a.resolved and a.title == title), None)
        
        if existing_alert:
            # Update existing alert
            existing_alert.timestamp = timestamp
            existing_alert.message = message
        else:
            # Create new alert
            alert = Alert(
                id=alert_id,
                severity=severity,
                title=title,
                message=message,
                timestamp=timestamp,
                tags=tags
            )
            
            self.alerts.append(alert)
            logger.warning(f"Alert created: {severity} - {title}")
    
    def get_metrics_summary(self, time_window: int = 3600) -> Dict[str, Any]:
        """Get summary of metrics for the last N seconds"""
        try:
            cutoff_time = datetime.now() - timedelta(seconds=time_window)
            recent_metrics = [m for m in self.metrics if m.timestamp > cutoff_time]
            
            # Group metrics by name
            metrics_by_name = {}
            for metric in recent_metrics:
                if metric.name not in metrics_by_name:
                    metrics_by_name[metric.name] = []
                metrics_by_name[metric.name].append(metric)
            
            # Calculate summaries
            summary = {
                "time_window": time_window,
                "metric_count": len(recent_metrics),
                "metrics": {}
            }
            
            for name, metric_list in metrics_by_name.items():
                values = [m.value for m in metric_list]
                summary["metrics"][name] = {
                    "latest": values[-1] if values else None,
                    "average": sum(values) / len(values) if values else None,
                    "min": min(values) if values else None,
                    "max": max(values) if values else None,
                    "count": len(values),
                    "unit": metric_list[0].unit if metric_list else None
                }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting metrics summary: {str(e)}")
            return {"error": str(e)}
    
    def get_alerts_summary(self, include_resolved: bool = False) -> Dict[str, Any]:
        """Get summary of alerts"""
        try:
            alerts = self.alerts if include_resolved else [a for a in self.alerts if not a.resolved]
            
            # Count by severity
            severity_counts = {}
            for alert in alerts:
                severity_counts[alert.severity] = severity_counts.get(alert.severity, 0) + 1
            
            return {
                "total_alerts": len(alerts),
                "unresolved_alerts": len([a for a in alerts if not a.resolved]),
                "severity_distribution": severity_counts,
                "recent_alerts": [
                    {
                        "id": alert.id,
                        "severity": alert.severity,
                        "title": alert.title,
                        "message": alert.message,
                        "timestamp": alert.timestamp.isoformat(),
                        "resolved": alert.resolved
                    }
                    for alert in sorted(alerts, key=lambda x: x.timestamp, reverse=True)[:10]
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting alerts summary: {str(e)}")
            return {"error": str(e)}
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        try:
            # Check critical components
            health_checks = {
                "database": memory_manager.db is not None,
                "ingestion_pipeline": len(ingestion_pipeline.ingestion_configs) > 0,
                "monitoring": self.is_running
            }
            
            # Check recent errors
            recent_alerts = [a for a in self.alerts 
                             if not a.resolved 
                             and a.severity in ["error", "critical"]
                             and (datetime.now() - a.timestamp).total_seconds() < 3600]
            
            overall_status = "healthy"
            if not all(health_checks.values()):
                overall_status = "unhealthy"
            elif recent_alerts:
                overall_status = "degraded"
            
            return {
                "overall_status": overall_status,
                "timestamp": datetime.now().isoformat(),
                "health_checks": health_checks,
                "recent_critical_alerts": len(recent_alerts),
                "monitoring_active": self.is_running
            }
            
        except Exception as e:
            logger.error(f"Error getting health status: {str(e)}")
            return {"error": str(e), "overall_status": "unknown"}

# Create global monitoring instance
atom_memory_monitoring = AtomCommunicationMemoryMonitoring()

# Export for use
__all__ = [
    'AtomCommunicationMemoryMonitoring',
    'atom_memory_monitoring',
    'MonitoringMetric',
    'Alert'
]
