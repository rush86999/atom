"""
Workflow Analytics Engine
Comprehensive analytics and monitoring system for workflow performance and usage
"""

import asyncio
import json
import logging
import sqlite3
import statistics
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"

class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class WorkflowStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

@dataclass
class WorkflowMetric:
    """Base metric data structure"""
    workflow_id: str
    metric_name: str
    metric_type: MetricType
    value: Union[int, float, str]
    timestamp: datetime
    tags: Dict[str, str] = None
    step_id: Optional[str] = None
    step_name: Optional[str] = None
    user_id: str = "default_user"

@dataclass
class WorkflowExecutionEvent:
    """Workflow execution event for tracking"""
    event_id: str
    workflow_id: str
    execution_id: str
    event_type: str  # "started", "completed", "failed", "step_started", "step_completed", "manual_override"
    timestamp: datetime
    step_id: Optional[str] = None
    step_name: Optional[str] = None
    duration_ms: Optional[int] = None
    status: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    resource_id: Optional[str] = None  # ID of the produced resource (e.g., task_id)
    user_id: str = "default_user"  # ID of the user who owns this execution

@dataclass
class PerformanceMetrics:
    """Performance metrics aggregation"""
    workflow_id: str
    time_window: str  # "1h", "24h", "7d", "30d"

    # Execution metrics
    total_executions: int
    successful_executions: int
    failed_executions: int
    average_duration_ms: float
    median_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float

    # Error metrics
    error_rate: float
    most_common_errors: List[Dict[str, Any]]

    # Resource metrics
    average_cpu_usage: float
    peak_memory_usage: float
    average_step_duration: Dict[str, float]

    # User metrics
    unique_users: int
    executions_by_user: Dict[str, int]

    timestamp: datetime

@dataclass
class Alert:
    """Analytics alert definition"""
    alert_id: str
    name: str
    description: str
    severity: AlertSeverity
    condition: str  # Python expression for alert condition
    threshold_value: Union[int, float]
    metric_name: str
    workflow_id: Optional[str] = None
    step_id: Optional[str] = None
    enabled: bool = True
    created_at: datetime = None
    triggered_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    notification_channels: List[str] = None

class WorkflowAnalyticsEngine:
    """Advanced analytics engine for workflow monitoring and insights"""

    def __init__(self, db_path: str = "analytics.db"):
        self.db_path = Path(db_path)
        self.db_path.expanduser().absolute()

        # Initialize database
        self._init_database()

        # Metrics storage
        self.metrics_buffer: deque = deque(maxlen=10000)
        self.events_buffer: deque = deque(maxlen=50000)

        # Performance cache
        self.performance_cache: Dict[str, PerformanceMetrics] = {}
        self.cache_ttl = 300  # 5 minutes

        # Active alerts
        self.active_alerts: Dict[str, Alert] = {}

        # Start background processing
        self._start_background_processing()

        logger.info(f"Workflow Analytics Engine initialized with database: {self.db_path}")

    def _init_database(self):
        """Initialize SQLite database for analytics storage"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                value TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                tags TEXT,
                step_id TEXT,
                step_name TEXT,
                user_id TEXT NOT NULL DEFAULT 'default_user',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                workflow_id TEXT NOT NULL,
                execution_id TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT 'default_user',
                event_type TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                step_id TEXT,
                step_name TEXT,
                duration_ms INTEGER,
                status TEXT,
                error_message TEXT,
                metadata TEXT,
                resource_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analytics_alerts (
                alert_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                severity TEXT NOT NULL,
                condition TEXT NOT NULL,
                threshold_value TEXT,
                metric_name TEXT NOT NULL,
                workflow_id TEXT,
                step_id TEXT,
                enabled BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                triggered_at DATETIME,
                resolved_at DATETIME,
                notification_channels TEXT
            )
        """)

        # Migrations: Add user_id column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE workflow_metrics ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default_user'")
        except sqlite3.OperationalError:
            pass # Column might already exist
            
        try:
            cursor.execute("ALTER TABLE workflow_events ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default_user'")
        except sqlite3.OperationalError:
            pass # Column might already exist

        # Indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_workflow_time ON workflow_metrics(workflow_id, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_workflow_time ON workflow_events(workflow_id, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON workflow_events(event_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_user ON workflow_metrics(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_user ON workflow_events(user_id)")

        conn.commit()
        conn.close()

    def track_workflow_start(self, workflow_id: str, execution_id: str,
                           user_id: Optional[str] = "default_user", metadata: Optional[Dict] = None):
        """Track workflow execution start"""
        event = WorkflowExecutionEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            execution_id=execution_id,
            user_id=user_id,
            event_type="workflow_started",
            timestamp=datetime.now(),
            metadata=metadata or {}
        )

        self.events_buffer.append(event)

        # Track counter metric
        metric = WorkflowMetric(
            workflow_id=workflow_id,
            metric_name="workflow_executions",
            metric_type=MetricType.COUNTER,
            value=1,
            timestamp=datetime.now(),
            tags={"event_type": "started"},
            user_id=user_id
        )
        self.metrics_buffer.append(metric)

    def track_workflow_completion(self, workflow_id: str, execution_id: str,
                                status: WorkflowStatus, duration_ms: int,
                                step_outputs: Optional[Dict] = None,
                                error_message: Optional[str] = None,
                                user_id: str = "default_user"):
        """Track workflow execution completion"""
        event = WorkflowExecutionEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            execution_id=execution_id,
            user_id=user_id,
            event_type="workflow_completed",
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            status=status.value,
            error_message=error_message,
            metadata={"step_count": len(step_outputs) if step_outputs else 0}
        )

        self.events_buffer.append(event)

        # Track execution duration
        metric = WorkflowMetric(
            workflow_id=workflow_id,
            metric_name="execution_duration_ms",
            metric_type=MetricType.HISTOGRAM,
            value=duration_ms,
            timestamp=datetime.now(),
            tags={"status": status.value},
            user_id=user_id
        )
        self.metrics_buffer.append(metric)

        # Track success/failure counter
        status_metric = WorkflowMetric(
            workflow_id=workflow_id,
            metric_name="successful_executions" if status == WorkflowStatus.COMPLETED else "failed_executions",
            metric_type=MetricType.COUNTER,
            value=1,
            timestamp=datetime.now(),
            tags={"status": status.value},
            user_id=user_id
        )
        self.metrics_buffer.append(status_metric)

    def track_step_execution(self, workflow_id: str, execution_id: str, step_id: str,
                           step_name: str, event_type: str, duration_ms: Optional[int] = None,
                           status: Optional[str] = None, error_message: Optional[str] = None,
                           resource_id: Optional[str] = None, user_id: str = "default_user"):
        """Track individual step execution"""
        event = WorkflowExecutionEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            execution_id=execution_id,
            user_id=user_id,
            event_type=event_type,
            timestamp=datetime.now(),
            step_id=step_id,
            step_name=step_name,
            duration_ms=duration_ms,
            status=status,
            error_message=error_message,
            resource_id=resource_id
        )

        self.events_buffer.append(event)

        # Track step duration
        if duration_ms is not None:
            metric = WorkflowMetric(
                workflow_id=workflow_id,
                metric_name=f"step_duration_ms",
                metric_type=MetricType.HISTOGRAM,
                value=duration_ms,
                timestamp=datetime.now(),
                tags={"step_id": step_id, "step_name": step_name, "event_type": event_type},
                user_id=user_id
            )
            self.metrics_buffer.append(metric)

    def track_manual_override(self, workflow_id: str, execution_id: str, resource_id: str, 
                             action: str, original_value: Any = None, new_value: Any = None,
                             user_id: str = "default_user"):
        """Track when a user manually overrides an automated action"""
        event = WorkflowExecutionEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            execution_id=execution_id,
            user_id=user_id,
            event_type="manual_override",
            timestamp=datetime.now(),
            resource_id=resource_id,
            metadata={
                "action": action,
                "original_value": original_value,
                "new_value": new_value
            },
            status="OVERRIDDEN",
            step_name=action # Using step_name to store the override action (e.g., "modified_deadline")
        )
        
        self.events_buffer.append(event)
        
        # Also increment a specific metric for easy reporting
        self.track_metric(
            workflow_id=workflow_id,
            metric_name="manual_override_count",
            metric_type=MetricType.COUNTER,
            value=1,
            user_id=user_id,
            tags={"resource_id": resource_id, "action": action}
        )

    def track_resource_usage(self, workflow_id: str, cpu_usage: float, memory_usage: float,
                           step_id: Optional[str] = None,
                           disk_io: Optional[int] = None, network_io: Optional[int] = None,
                           user_id: str = "default_user"):
        """Track resource usage during workflow execution"""
        timestamp = datetime.now()

        # CPU usage metric
        cpu_metric = WorkflowMetric(
            workflow_id=workflow_id,
            metric_name="cpu_usage_percent",
            metric_type=MetricType.GAUGE,
            value=cpu_usage,
            timestamp=timestamp,
            step_id=step_id,
            user_id=user_id
        )
        self.metrics_buffer.append(cpu_metric)

        # Memory usage metric
        memory_metric = WorkflowMetric(
            workflow_id=workflow_id,
            metric_name="memory_usage_mb",
            metric_type=MetricType.GAUGE,
            value=memory_usage,
            timestamp=timestamp,
            step_id=step_id,
            user_id=user_id
        )
        self.metrics_buffer.append(memory_metric)

        # Disk I/O metric
        if disk_io is not None:
            disk_metric = WorkflowMetric(
                workflow_id=workflow_id,
                metric_name="disk_io_bytes",
                metric_type=MetricType.COUNTER,
                value=disk_io,
                timestamp=timestamp,
                step_id=step_id,
                user_id=user_id
            )
            self.metrics_buffer.append(disk_metric)

        # Network I/O metric
        if network_io is not None:
            network_metric = WorkflowMetric(
                workflow_id=workflow_id,
                metric_name="network_io_bytes",
                metric_type=MetricType.COUNTER,
                value=network_io,
                timestamp=timestamp,
                step_id=step_id,
                user_id=user_id
            )
            self.metrics_buffer.append(network_metric)

    def track_user_activity(self, user_id: str, action: str, workflow_id: Optional[str] = None,
                          metadata: Optional[Dict] = None, workspace_id: Optional[str] = None):
        """Track user activity for analytics"""
        metric = WorkflowMetric(
            workflow_id=workflow_id or "system",
            metric_name="user_activity",
            metric_type=MetricType.COUNTER,
            value=1,
            timestamp=datetime.now(),
            tags={"user_id": user_id, "action": action, "workspace_id": workspace_id or "default"},
            user_id=user_id
        )
        self.metrics_buffer.append(metric)

    def track_metric(self, workflow_id: str, metric_name: str, metric_type: MetricType,
                     value: Any, tags: Dict[str, str] = None, step_id: str = None,
                     step_name: str = None, user_id: str = "default_user"):
        """Track a general workflow metric"""
        metric = WorkflowMetric(
            workflow_id=workflow_id,
            metric_name=metric_name,
            metric_type=metric_type,
            value=value,
            timestamp=datetime.now(),
            tags=tags,
            step_id=step_id,
            step_name=step_name,
            user_id=user_id
        )
        self.metrics_buffer.append(metric)

    def get_workflow_performance_metrics(self, workflow_id: str, time_window: str = "24h") -> PerformanceMetrics:
        """Get aggregated performance metrics for a workflow"""
        cache_key = f"{workflow_id}_{time_window}"

        # Check cache
        if cache_key in self.performance_cache:
            cached = self.performance_cache[cache_key]
            if (datetime.now() - cached.timestamp).seconds < self.cache_ttl:
                return cached

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Calculate time window
        time_map = {
            "1h": datetime.now() - timedelta(hours=1),
            "24h": datetime.now() - timedelta(days=1),
            "7d": datetime.now() - timedelta(days=7),
            "30d": datetime.now() - timedelta(days=30)
        }

        start_time = time_map.get(time_window, datetime.now() - timedelta(days=1))

        try:
            # Get execution events
            cursor.execute("""
                SELECT execution_id, event_type, timestamp, duration_ms, status, error_message
                FROM workflow_events
                WHERE workflow_id = ? AND timestamp >= ?
                ORDER BY timestamp
            """, (workflow_id, start_time.isoformat()))

            events = cursor.fetchall()

            # Analyze executions
            executions = defaultdict(list)
            for event in events:
                executions[event[1]].append(event)

            completed_events = executions.get("workflow_completed", [])
            started_events = executions.get("workflow_started", [])

            total_executions = len(started_events)
            successful_executions = len([e for e in completed_events if e[4] == "completed"])
            failed_executions = len([e for e in completed_events if e[4] == "failed"])

            # Calculate duration statistics
            durations = [e[3] for e in completed_events if e[3] is not None]
            avg_duration = statistics.mean(durations) if durations else 0
            median_duration = statistics.median(durations) if durations else 0
            p95_duration = statistics.quantiles(durations, n=20)[18] if len(durations) > 20 else 0
            p99_duration = statistics.quantiles(durations, n=100)[98] if len(durations) > 100 else 0

            # Error rate
            error_rate = (failed_executions / total_executions * 100) if total_executions > 0 else 0

            # Get most common errors
            error_messages = [e[5] for e in completed_events if e[5] is not None]
            error_counts = defaultdict(int)
            for error in error_messages:
                error_counts[error] += 1

            most_common_errors = [
                {"error": error, "count": count, "percentage": count/len(error_messages)*100}
                for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            ]

            # Get resource metrics
            cursor.execute("""
                SELECT AVG(CAST(value AS REAL)), MAX(CAST(value AS REAL))
                FROM workflow_metrics
                WHERE workflow_id = ? AND timestamp >= ? AND metric_name IN ('cpu_usage_percent', 'memory_usage_mb')
            """, (workflow_id, start_time.isoformat()))

            resource_data = cursor.fetchone()
            avg_cpu = resource_data[0] if resource_data and resource_data[0] else 0
            peak_memory = resource_data[1] if resource_data and resource_data[1] else 0

            # Get step performance
            cursor.execute("""
                SELECT step_name, AVG(CAST(value AS REAL))
                FROM workflow_metrics
                WHERE workflow_id = ? AND timestamp >= ? AND metric_name = 'step_duration_ms'
                GROUP BY step_name
            """, (workflow_id, start_time.isoformat()))

            step_performance = dict(cursor.fetchall())

            # Create performance metrics
            metrics = PerformanceMetrics(
                workflow_id=workflow_id,
                time_window=time_window,
                total_executions=total_executions,
                successful_executions=successful_executions,
                failed_executions=failed_executions,
                average_duration_ms=avg_duration,
                median_duration_ms=median_duration,
                p95_duration_ms=p95_duration,
                p99_duration_ms=p99_duration,
                error_rate=error_rate,
                most_common_errors=most_common_errors,
                average_cpu_usage=avg_cpu,
                peak_memory_usage=peak_memory,
                average_step_duration=step_performance,
                unique_users=0,  # Would need to implement user tracking
                executions_by_user={},
                timestamp=datetime.now()
            )

            # Cache result
            self.performance_cache[cache_key] = metrics

            return metrics

        except Exception as e:
            logger.error(f"Error calculating performance metrics for {workflow_id}: {e}")
            raise
        finally:
            conn.close()

    def get_system_overview(self, time_window: str = "24h") -> Dict[str, Any]:
        """Get system-wide analytics overview"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        start_time = datetime.now() - timedelta(days=1)  # Default to 24h

        try:
            # Total workflows
            cursor.execute("SELECT COUNT(DISTINCT workflow_id) FROM workflow_metrics WHERE timestamp >= ?",
                         (start_time.isoformat(),))
            total_workflows = cursor.fetchone()[0]

            # Total executions
            cursor.execute("""
                SELECT COUNT(*) FROM workflow_events
                WHERE event_type = 'workflow_started' AND timestamp >= ?
            """, (start_time.isoformat(),))
            total_executions = cursor.fetchone()[0]

            # Success rate
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM workflow_events
                WHERE event_type = 'workflow_completed' AND timestamp >= ?
            """, (start_time.isoformat(),))

            success_data = cursor.fetchone()
            successful = success_data[0] or 0
            failed = success_data[1] or 0
            total_completed = successful + failed
            success_rate = (successful / total_completed * 100) if total_completed > 0 else 0

            # Average execution time
            cursor.execute("""
                SELECT AVG(duration_ms) FROM workflow_events
                WHERE event_type = 'workflow_completed' AND duration_ms IS NOT NULL AND timestamp >= ?
            """, (start_time.isoformat(),))

            avg_duration = cursor.fetchone()[0] or 0

            # Top performing workflows
            cursor.execute("""
                SELECT workflow_id, COUNT(*) as executions
                FROM workflow_events
                WHERE event_type = 'workflow_started' AND timestamp >= ?
                GROUP BY workflow_id
                ORDER BY executions DESC
                LIMIT 10
            """, (start_time.isoformat(),))

            top_workflows = [
                {"workflow_id": row[0], "executions": row[1]}
                for row in cursor.fetchall()
            ]

            # Recent errors
            cursor.execute("""
                SELECT workflow_id, error_message, timestamp
                FROM workflow_events
                WHERE status = 'failed' AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 10
            """, (start_time.isoformat(),))

            recent_errors = [
                {
                    "workflow_id": row[0],
                    "error_message": row[1],
                    "timestamp": row[2]
                }
                for row in cursor.fetchall()
            ]

            return {
                "total_workflows": total_workflows,
                "total_executions": total_executions,
                "success_rate": round(success_rate, 2),
                "average_execution_time_ms": round(avg_duration, 2),
                "top_workflows": top_workflows,
                "recent_errors": recent_errors,
                "time_window": time_window,
                "generated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating system overview: {e}")
            raise
        finally:
            conn.close()

    def create_alert(self, name: str, description: str, severity: AlertSeverity,
                    condition: str, threshold_value: Union[int, float],
                    metric_name: str, workflow_id: Optional[str] = None,
                    step_id: Optional[str] = None,
                    notification_channels: Optional[List[str]] = None) -> Alert:
        """Create a new analytics alert"""
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            name=name,
            description=description,
            severity=severity,
            condition=condition,
            threshold_value=threshold_value,
            metric_name=metric_name,
            workflow_id=workflow_id,
            step_id=step_id,
            notification_channels=notification_channels or [],
            created_at=datetime.now()
        )

        # Save to database
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO analytics_alerts
            (alert_id, name, description, severity, condition, threshold_value,
             metric_name, workflow_id, step_id, notification_channels)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            alert.alert_id, alert.name, alert.description, alert.severity.value,
            alert.condition, str(alert.threshold_value), alert.metric_name,
            alert.workflow_id, alert.step_id, json.dumps(alert.notification_channels)
        ))

        conn.commit()
        conn.close()

        self.active_alerts[alert.alert_id] = alert

        logger.info(f"Created alert: {alert.name} ({alert.alert_id})")
        return alert

    def check_alerts(self):
        """Check all active alerts against current metrics"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            # Get active alerts
            cursor.execute("SELECT * FROM analytics_alerts WHERE enabled = 1")
            alerts_data = cursor.fetchall()

            for alert_data in alerts_data:
                alert_id = alert_data[0]

                try:
                    # Get latest metric for alert
                    cursor.execute("""
                        SELECT value, timestamp FROM workflow_metrics
                        WHERE metric_name = ? AND workflow_id = COALESCE(?, workflow_id)
                        ORDER BY timestamp DESC LIMIT 1
                    """, (alert_data[5], alert_data[6]))

                    metric_data = cursor.fetchone()
                    if metric_data:
                        metric_value = float(metric_data[0])

                        # Evaluate alert condition
                        # Simple threshold check for now
                        if metric_value > float(alert_data[5]):  # threshold_value
                            # Trigger alert
                            self._trigger_alert(alert_id)
                        else:
                            # Resolve alert if it was triggered
                            self._resolve_alert(alert_id)

                except Exception as e:
                    logger.error(f"Error checking alert {alert_id}: {e}")

        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
        finally:
            conn.close()

    def _trigger_alert(self, alert_id: str):
        """Trigger an alert"""
        if alert_id not in self.active_alerts:
            return

        alert = self.active_alerts[alert_id]
        if alert.triggered_at is None:
            alert.triggered_at = datetime.now()

            # Update database
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE analytics_alerts SET triggered_at = ? WHERE alert_id = ?",
                (alert.triggered_at.isoformat(), alert_id)
            )
            conn.commit()
            conn.close()

            # Send notifications
            self._send_alert_notification(alert)

            logger.warning(f"Alert triggered: {alert.name}")

    def _resolve_alert(self, alert_id: str):
        """Resolve an alert"""
        if alert_id not in self.active_alerts:
            return

        alert = self.active_alerts[alert_id]
        if alert.triggered_at is not None and alert.resolved_at is None:
            alert.resolved_at = datetime.now()

            # Update database
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE analytics_alerts SET resolved_at = ? WHERE alert_id = ?",
                (alert.resolved_at.isoformat(), alert_id)
            )
            conn.commit()
            conn.close()

            logger.info(f"Alert resolved: {alert.name}")

    def _send_alert_notification(self, alert: Alert):
        """Send notification for triggered alert"""
        # Implementation would depend on notification channels
        # For now, just log the alert
        logger.critical(f"ALERT: {alert.name} - {alert.description} (Severity: {alert.severity.value})")

    def _start_background_processing(self):
        """Start background processing for analytics"""
        async def background_task():
            while True:
                try:
                    # Process metrics buffer
                    if self.metrics_buffer:
                        metrics = list(self.metrics_buffer)
                        self.metrics_buffer.clear()
                        await self._process_metrics_batch(metrics)

                    # Process events buffer
                    if self.events_buffer:
                        events = list(self.events_buffer)
                        self.events_buffer.clear()
                        await self._process_events_batch(events)

                    # Check alerts
                    self.check_alerts()

                    # Clean old data
                    await self._cleanup_old_data()

                except Exception as e:
                    logger.error(f"Error in background processing: {e}")

                # Sleep for 30 seconds
                await asyncio.sleep(30)

        # Start background task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(background_task())

        # Run in background thread
        import threading
        thread = threading.Thread(target=lambda: loop.run_forever(), daemon=True)
        thread.start()

    async def _process_metrics_batch(self, metrics: List[WorkflowMetric]):
        """Process a batch of metrics"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            for metric in metrics:
                cursor.execute("""
                    INSERT INTO workflow_metrics
                    (workflow_id, metric_name, metric_type, value, timestamp, tags, step_id, step_name, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metric.workflow_id,
                    metric.metric_name,
                    metric.metric_type.value,
                    str(metric.value),
                    metric.timestamp.isoformat(),
                    json.dumps(metric.tags) if metric.tags else None,
                    metric.step_id,
                    metric.step_name,
                    metric.user_id
                ))

            conn.commit()

        except Exception as e:
            logger.error(f"Error processing metrics batch: {e}")
            conn.rollback()
        finally:
            conn.close()

    async def _process_events_batch(self, events: List[WorkflowExecutionEvent]):
        """Process a batch of events"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            for event in events:
                cursor.execute("""
                    INSERT OR REPLACE INTO workflow_events
                    (event_id, workflow_id, execution_id, user_id, event_type, timestamp,
                     step_id, step_name, duration_ms, status, error_message, metadata, resource_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id,
                    event.workflow_id,
                    event.execution_id,
                    event.user_id,
                    event.event_type,
                    event.timestamp.isoformat(),
                    event.step_id,
                    event.step_name,
                    event.duration_ms,
                    event.status,
                    event.error_message,
                    json.dumps(event.metadata) if event.metadata else None,
                    event.resource_id
                ))

            conn.commit()

        except Exception as e:
            logger.error(f"Error processing events batch: {e}")
            conn.rollback()
        finally:
            conn.close()

    async def _cleanup_old_data(self):
        """Clean up old analytics data"""
        # Keep data for 90 days
        cutoff_date = datetime.now() - timedelta(days=90)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM workflow_metrics WHERE timestamp < ?", (cutoff_date.isoformat(),))
            cursor.execute("DELETE FROM workflow_events WHERE timestamp < ?", (cutoff_date.isoformat(),))
            conn.commit()

        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            conn.rollback()
        finally:
            conn.close()


    async def flush(self):
        """Manually flush all buffers to database"""
        if self.metrics_buffer:
            metrics = list(self.metrics_buffer)
            self.metrics_buffer.clear()
            await self._process_metrics_batch(metrics)

        if self.events_buffer:
            events = list(self.events_buffer)
            self.events_buffer.clear()
            await self._process_events_batch(events)

    # ============== ANALYTICS DASHBOARD HELPER METHODS ==============

    def get_performance_metrics(self, workflow_id: str, time_window: str = "24h") -> Optional[PerformanceMetrics]:
        """
        Get performance metrics for a workflow or all workflows.
        Wrapper for get_workflow_performance_metrics for compatibility.
        """
        if workflow_id == "*":
            # Aggregate metrics for all workflows
            return self._get_all_workflows_metrics(time_window)
        return self.get_workflow_performance_metrics(workflow_id, time_window)

    def _get_all_workflows_metrics(self, time_window: str = "24h") -> PerformanceMetrics:
        """Get aggregated metrics across all workflows."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        time_map = {
            "1h": timedelta(hours=1),
            "24h": timedelta(days=1),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }
        time_delta = time_map.get(time_window, timedelta(days=1))
        start_time = datetime.now() - time_delta

        try:
            # Get all workflow execution events
            cursor.execute("""
                SELECT execution_id, event_type, timestamp, duration_ms, status, user_id
                FROM workflow_events
                WHERE timestamp >= ?
                ORDER BY timestamp
            """, (start_time.isoformat(),))

            events = cursor.fetchall()

            # Analyze executions
            executions = defaultdict(list)
            for event in events:
                executions[event[1]].append(event)

            completed_events = executions.get("workflow_completed", [])
            started_events = executions.get("workflow_started", [])

            total_executions = len(started_events)
            successful_executions = len([e for e in completed_events if e[4] == "completed"])
            failed_executions = len([e for e in completed_events if e[4] == "failed"])

            # Calculate duration statistics
            durations = [e[3] for e in completed_events if e[3] is not None]
            avg_duration = statistics.mean(durations) if durations else 0
            median_duration = statistics.median(durations) if durations else 0
            p95_duration = statistics.quantiles(durations, n=20)[18] if len(durations) > 20 else 0
            p99_duration = statistics.quantiles(durations, n=100)[98] if len(durations) > 100 else 0

            # Error rate
            error_rate = (failed_executions / total_executions * 100) if total_executions > 0 else 0

            # Get unique users
            unique_users = len(set([e[5] for e in events if e[5]]))

            # Get most common errors
            error_messages = [e[5] for e in completed_events if e[5] is not None]
            error_counts = defaultdict(int)
            for error in error_messages:
                error_counts[error] += 1

            most_common_errors = [
                {"error": error, "count": count, "percentage": count/len(error_messages)*100 if error_messages else 0}
                for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            ]

            return PerformanceMetrics(
                workflow_id="*",
                time_window=time_window,
                total_executions=total_executions,
                successful_executions=successful_executions,
                failed_executions=failed_executions,
                average_duration_ms=avg_duration,
                median_duration_ms=median_duration,
                p95_duration_ms=p95_duration,
                p99_duration_ms=p99_duration,
                error_rate=error_rate,
                most_common_errors=most_common_errors,
                average_cpu_usage=0.0,
                peak_memory_usage=0.0,
                average_step_duration={},
                unique_users=unique_users,
                executions_by_user={},
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.error(f"Error calculating all workflows metrics: {e}")
            raise
        finally:
            conn.close()

    def get_unique_workflow_count(self, time_window: str = "24h") -> int:
        """Get count of unique workflows in time window."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        time_map = {
            "1h": timedelta(hours=1),
            "24h": timedelta(days=1),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }
        time_delta = time_map.get(time_window, timedelta(days=1))
        start_time = datetime.now() - time_delta

        try:
            cursor.execute("""
                SELECT COUNT(DISTINCT workflow_id)
                FROM workflow_events
                WHERE timestamp >= ?
            """, (start_time.isoformat(),))
            result = cursor.fetchone()
            return result[0] if result else 0
        finally:
            conn.close()

    def get_workflow_name(self, workflow_id: str) -> Optional[str]:
        """
        Get workflow name from metadata or events.
        Returns workflow_id if no name found.
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            # Try to get from metadata (if we have a workflows table)
            # For now, return workflow_id as fallback
            # In production, this would query a workflows table
            return workflow_id
        finally:
            conn.close()

    def get_all_workflow_ids(self, time_window: str = "24h") -> List[str]:
        """Get list of all workflow IDs in time window."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        time_map = {
            "1h": timedelta(hours=1),
            "24h": timedelta(days=1),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }
        time_delta = time_map.get(time_window, timedelta(days=1))
        start_time = datetime.now() - time_delta

        try:
            cursor.execute("""
                SELECT DISTINCT workflow_id
                FROM workflow_events
                WHERE timestamp >= ?
                ORDER BY workflow_id
            """, (start_time.isoformat(),))

            results = cursor.fetchall()
            return [row[0] for row in results]
        finally:
            conn.close()

    def get_last_execution_time(self, workflow_id: str) -> Optional[datetime]:
        """Get timestamp of last execution for workflow."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT MAX(timestamp)
                FROM workflow_events
                WHERE workflow_id = ?
            """, (workflow_id,))

            result = cursor.fetchone()
            if result and result[0]:
                return datetime.fromisoformat(result[0])
            return None
        finally:
            conn.close()

    def get_execution_timeline(self, workflow_id: str, time_window: str = "24h", interval: str = "1h") -> List[Dict[str, Any]]:
        """
        Get execution timeline data grouped by interval.
        Returns list of data points with timestamp, count, success/failure counts, avg duration.
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        time_map = {
            "1h": timedelta(hours=1),
            "24h": timedelta(days=1),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }
        time_delta = time_map.get(time_window, timedelta(days=1))
        start_time = datetime.now() - time_delta

        # SQLite doesn't have date_trunc, so we'll group manually
        try:
            if workflow_id == "*":
                cursor.execute("""
                    SELECT timestamp, event_type, duration_ms, status
                    FROM workflow_events
                    WHERE timestamp >= ? AND event_type IN ('workflow_started', 'workflow_completed')
                    ORDER BY timestamp
                """, (start_time.isoformat(),))
            else:
                cursor.execute("""
                    SELECT timestamp, event_type, duration_ms, status
                    FROM workflow_events
                    WHERE workflow_id = ? AND timestamp >= ? AND event_type IN ('workflow_started', 'workflow_completed')
                    ORDER BY timestamp
                """, (workflow_id, start_time.isoformat()))

            events = cursor.fetchall()

            # Group by interval
            interval_map = {
                "5m": timedelta(minutes=5),
                "15m": timedelta(minutes=15),
                "1h": timedelta(hours=1),
                "1d": timedelta(days=1)
            }
            interval_delta = interval_map.get(interval, timedelta(hours=1))

            # Create time buckets
            timeline_data = []
            current_time = start_time
            end_time = datetime.now()

            while current_time <= end_time:
                bucket_end = current_time + interval_delta

                # Filter events in this bucket
                bucket_events = [
                    e for e in events
                    if current_time <= datetime.fromisoformat(e[0]) < bucket_end
                ]

                # Count events
                count = len([e for e in bucket_events if e[1] == "workflow_started"])
                success_count = len([e for e in bucket_events if e[1] == "workflow_completed" and e[3] == "completed"])
                failure_count = len([e for e in bucket_events if e[1] == "workflow_completed" and e[3] == "failed"])

                # Calculate average duration
                durations = [e[2] for e in bucket_events if e[2] is not None]
                avg_duration = statistics.mean(durations) if durations else 0

                timeline_data.append({
                    "timestamp": current_time,
                    "count": count,
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "average_duration_ms": avg_duration
                })

                current_time = bucket_end

            return timeline_data

        except Exception as e:
            logger.error(f"Error getting execution timeline: {e}")
            return []
        finally:
            conn.close()

    def get_error_breakdown(self, workflow_id: str, time_window: str = "24h") -> Dict[str, Any]:
        """
        Get error breakdown by type and workflow.
        Returns error types with counts, workflows with most errors, recent error messages.
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        time_map = {
            "1h": timedelta(hours=1),
            "24h": timedelta(days=1),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }
        time_delta = time_map.get(time_window, timedelta(days=1))
        start_time = datetime.now() - time_delta

        try:
            if workflow_id == "*":
                # Get errors by workflow
                cursor.execute("""
                    SELECT workflow_id, COUNT(*) as error_count
                    FROM workflow_events
                    WHERE timestamp >= ? AND status = 'failed'
                    GROUP BY workflow_id
                    ORDER BY error_count DESC
                    LIMIT 10
                """, (start_time.isoformat(),))

                workflows_with_errors = [
                    {"workflow_id": row[0], "error_count": row[1]}
                    for row in cursor.fetchall()
                ]

                # Get recent errors
                cursor.execute("""
                    SELECT workflow_id, error_message, timestamp
                    FROM workflow_events
                    WHERE timestamp >= ? AND error_message IS NOT NULL
                    ORDER BY timestamp DESC
                    LIMIT 20
                """, (start_time.isoformat(),))

                recent_errors = [
                    {
                        "workflow_id": row[0],
                        "error_message": row[1],
                        "timestamp": row[2]
                    }
                    for row in cursor.fetchall()
                ]

                # Aggregate error types
                error_types = defaultdict(int)
                for error in recent_errors:
                    error_type = error["error_message"][:50] if error["error_message"] else "Unknown"
                    error_types[error_type] += 1

                return {
                    "error_types": [{"type": k, "count": v} for k, v in sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:10]],
                    "workflows_with_errors": workflows_with_errors,
                    "recent_errors": recent_errors
                }
            else:
                # Get errors for specific workflow
                cursor.execute("""
                    SELECT error_message, timestamp, step_name
                    FROM workflow_events
                    WHERE workflow_id = ? AND timestamp >= ? AND error_message IS NOT NULL
                    ORDER BY timestamp DESC
                    LIMIT 50
                """, (workflow_id, start_time.isoformat()))

                errors = cursor.fetchall()

                # Group by error type
                error_types = defaultdict(int)
                recent_errors = []
                for error_msg, timestamp, step_name in errors:
                    error_type = error_msg[:50] if error_msg else "Unknown"
                    error_types[error_type] += 1
                    recent_errors.append({
                        "error_message": error_msg,
                        "timestamp": timestamp,
                        "step_name": step_name
                    })

                return {
                    "workflow_id": workflow_id,
                    "error_types": [{"type": k, "count": v} for k, v in sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:10]],
                    "recent_errors": recent_errors
                }

        except Exception as e:
            logger.error(f"Error getting error breakdown: {e}")
            return {}
        finally:
            conn.close()

    def get_all_alerts(self, workflow_id: Optional[str] = None, enabled_only: bool = False) -> List[Alert]:
        """
        Get all configured alerts, optionally filtered by workflow and enabled status.
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            query = "SELECT * FROM analytics_alerts WHERE 1=1"
            params = []

            if workflow_id:
                query += " AND workflow_id = ?"
                params.append(workflow_id)

            if enabled_only:
                query += " AND enabled = 1"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            alerts = []
            for row in rows:
                alert = Alert(
                    alert_id=row[0],
                    name=row[1],
                    description=row[2],
                    severity=AlertSeverity(row[3]),
                    condition=row[4],
                    threshold_value=float(row[5]) if row[5] else None,
                    metric_name=row[6],
                    workflow_id=row[7],
                    step_id=row[8],
                    enabled=bool(row[9]),
                    created_at=datetime.fromisoformat(row[10]) if row[10] else None,
                    triggered_at=datetime.fromisoformat(row[11]) if row[11] else None,
                    resolved_at=datetime.fromisoformat(row[12]) if row[12] else None,
                    notification_channels=json.loads(row[13]) if row[13] else []
                )
                alerts.append(alert)

            return alerts

        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            return []
        finally:
            conn.close()

    def get_recent_events(self, limit: int = 50, workflow_id: Optional[str] = None) -> List[WorkflowExecutionEvent]:
        """
        Get recent execution events for real-time feed.
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            if workflow_id:
                cursor.execute("""
                    SELECT event_id, workflow_id, execution_id, user_id, event_type, timestamp,
                           step_id, step_name, duration_ms, status, error_message, metadata, resource_id
                    FROM workflow_events
                    WHERE workflow_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (workflow_id, limit))
            else:
                cursor.execute("""
                    SELECT event_id, workflow_id, execution_id, user_id, event_type, timestamp,
                           step_id, step_name, duration_ms, status, error_message, metadata, resource_id
                    FROM workflow_events
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))

            rows = cursor.fetchall()

            events = []
            for row in rows:
                event = WorkflowExecutionEvent(
                    event_id=row[0],
                    workflow_id=row[1],
                    execution_id=row[2],
                    user_id=row[3],
                    event_type=row[4],
                    timestamp=datetime.fromisoformat(row[5]),
                    step_id=row[6],
                    step_name=row[7],
                    duration_ms=row[8],
                    status=row[9],
                    error_message=row[10],
                    metadata=json.loads(row[11]) if row[11] else None,
                    resource_id=row[12]
                )
                events.append(event)

            return events

        except Exception as e:
            logger.error(f"Error getting recent events: {e}")
            return []
        finally:
            conn.close()

    # Create and update alert methods (wrappers for compatibility with API)
    def create_alert(self, alert: Alert):
        """Create a new alert (wrapper for compatibility)."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO analytics_alerts
                (alert_id, name, description, severity, condition, threshold_value,
                 metric_name, workflow_id, step_id, enabled, notification_channels)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id, alert.name, alert.description, alert.severity.value,
                alert.condition, str(alert.threshold_value) if alert.threshold_value else None,
                alert.metric_name, alert.workflow_id, alert.step_id,
                1 if alert.enabled else 0, json.dumps(alert.notification_channels or [])
            ))

            conn.commit()
            self.active_alerts[alert.alert_id] = alert

            logger.info(f"Created alert: {alert.name} ({alert.alert_id})")
            return alert

        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_alert(self, alert_id: str, enabled: Optional[bool] = None, threshold_value: Optional[float] = None):
        """Update an existing alert."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            updates = []
            params = []

            if enabled is not None:
                updates.append("enabled = ?")
                params.append(1 if enabled else 0)

            if threshold_value is not None:
                updates.append("threshold_value = ?")
                params.append(str(threshold_value))

            if updates:
                params.append(alert_id)
                cursor.execute(f"UPDATE analytics_alerts SET {', '.join(updates)} WHERE alert_id = ?", params)
                conn.commit()

                # Update in-memory alert
                if alert_id in self.active_alerts:
                    alert = self.active_alerts[alert_id]
                    if enabled is not None:
                        alert.enabled = enabled
                    if threshold_value is not None:
                        alert.threshold_value = threshold_value

        except Exception as e:
            logger.error(f"Error updating alert: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete_alert(self, alert_id: str):
        """Delete an alert."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM analytics_alerts WHERE alert_id = ?", (alert_id,))
            conn.commit()

            if alert_id in self.active_alerts:
                del self.active_alerts[alert_id]

            logger.info(f"Deleted alert: {alert_id}")

        except Exception as e:
            logger.error(f"Error deleting alert: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()


# Global analytics engine instance
_analytics_engine = None

def get_analytics_engine() -> WorkflowAnalyticsEngine:
    global _analytics_engine
    if _analytics_engine is None:
        _analytics_engine = WorkflowAnalyticsEngine()
    return _analytics_engine
