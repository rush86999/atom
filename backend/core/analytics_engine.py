from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

@dataclass
class WorkflowMetric:
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_duration_seconds: float = 0.0
    total_time_saved_seconds: float = 0.0
    total_business_value: float = 0.0
    last_executed: Optional[str] = None
    
    @property
    def success_rate(self) -> float:
        if self.execution_count == 0:
            return 0.0
        return (self.success_count / self.execution_count) * 100.0
        
    @property
    def average_duration(self) -> float:
        if self.execution_count == 0:
            return 0.0
        return self.total_duration_seconds / self.execution_count

@dataclass
class IntegrationMetric:
    call_count: int = 0
    error_count: int = 0
    total_response_time_ms: float = 0.0
    last_called: Optional[str] = None
    status: str = "UNKNOWN"  # READY, PARTIAL, ERROR, UNKNOWN
    
    @property
    def error_rate(self) -> float:
        if self.call_count == 0:
            return 0.0
        return (self.error_count / self.call_count) * 100.0
        
    @property
    def average_response_time(self) -> float:
        if self.call_count == 0:
            return 0.0
        return self.total_response_time_ms / self.call_count
        
    @property
    def uptime_percentage(self) -> float:
        return 100.0 - self.error_rate

class AnalyticsEngine:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AnalyticsEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "analytics_data")
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.workflow_metrics: Dict[str, WorkflowMetric] = {}
        self.integration_metrics: Dict[str, IntegrationMetric] = {}
        
        self._load_data()
        self._initialized = True
        
    def _load_data(self):
        """Load metrics from JSON files"""
        try:
            wf_path = os.path.join(self.data_dir, "workflow_metrics.json")
            if os.path.exists(wf_path):
                with open(wf_path, 'r') as f:
                    data = json.load(f)
                    for k, v in data.items():
                        self.workflow_metrics[k] = WorkflowMetric(**v)
                        
            int_path = os.path.join(self.data_dir, "integration_metrics.json")
            if os.path.exists(int_path):
                with open(int_path, 'r') as f:
                    data = json.load(f)
                    for k, v in data.items():
                        self.integration_metrics[k] = IntegrationMetric(**v)
                        
            logger.info(f"Loaded analytics data: {len(self.workflow_metrics)} workflows, {len(self.integration_metrics)} integrations")
        except Exception as e:
            logger.error(f"Error loading analytics data: {e}")
            
    def _save_data(self):
        """Save metrics to JSON files"""
        try:
            wf_path = os.path.join(self.data_dir, "workflow_metrics.json")
            with open(wf_path, 'w') as f:
                json.dump({k: asdict(v) for k, v in self.workflow_metrics.items()}, f, indent=2)
                
            int_path = os.path.join(self.data_dir, "integration_metrics.json")
            with open(int_path, 'w') as f:
                json.dump({k: asdict(v) for k, v in self.integration_metrics.items()}, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving analytics data: {e}")

    def track_workflow_execution(self, workflow_id: str, success: bool, duration_seconds: float, time_saved_seconds: float = 0.0, business_value: float = 0.0):
        """Track a workflow execution"""
        if workflow_id not in self.workflow_metrics:
            self.workflow_metrics[workflow_id] = WorkflowMetric()
            
        metric = self.workflow_metrics[workflow_id]
        metric.execution_count += 1
        if success:
            metric.success_count += 1
        else:
            metric.failure_count += 1
            
        metric.total_duration_seconds += duration_seconds
        metric.total_time_saved_seconds += time_saved_seconds
        metric.total_business_value += business_value
        metric.last_executed = datetime.utcnow().isoformat()
        
        self._save_data()
        
    def track_integration_call(self, integration_name: str, success: bool, response_time_ms: float):
        """Track an integration API call"""
        if integration_name not in self.integration_metrics:
            self.integration_metrics[integration_name] = IntegrationMetric()
            
        metric = self.integration_metrics[integration_name]
        metric.call_count += 1
        if not success:
            metric.error_count += 1
            
        metric.total_response_time_ms += response_time_ms
        metric.last_called = datetime.utcnow().isoformat()
        
        # Simple status logic
        if metric.error_rate > 10:
            metric.status = "ERROR"
        elif metric.error_rate > 0:
            metric.status = "PARTIAL"
        else:
            metric.status = "READY"
            
        self._save_data()
        
    def get_workflow_analytics(self) -> Dict[str, Any]:
        """Get summarized workflow analytics"""
        total_executions = sum(m.execution_count for m in self.workflow_metrics.values())
        total_saved = sum(m.total_time_saved_seconds for m in self.workflow_metrics.values())
        total_value = sum(m.total_business_value for m in self.workflow_metrics.values())
        
        return {
            "total_executions": total_executions,
            "total_time_saved_hours": round(total_saved / 3600, 2),
            "total_business_value": round(total_value, 2),
            "workflow_count": len(self.workflow_metrics),
            "workflows": {k: asdict(v) for k, v in self.workflow_metrics.items()}
        }
        
    def get_integration_health(self) -> Dict[str, Any]:
        """Get integration health summary"""
        ready_count = sum(1 for m in self.integration_metrics.values() if m.status == "READY")
        
        return {
            "total_integrations": len(self.integration_metrics),
            "ready_count": ready_count,
            "integrations": {k: asdict(v) for k, v in self.integration_metrics.items()}
        }

# Global instance
_analytics_engine = None

def get_analytics_engine() -> AnalyticsEngine:
    global _analytics_engine
    if _analytics_engine is None:
        _analytics_engine = AnalyticsEngine()
    return _analytics_engine
