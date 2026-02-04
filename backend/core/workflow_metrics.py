"""
Workflow Metrics - Phase 34
Track workflow execution metrics, success rates, and performance data.
"""

import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

@dataclass
class ExecutionRecord:
    """Record of a single workflow execution"""
    execution_id: str
    workflow_id: str
    template_id: Optional[str]
    status: str  # completed, failed, cancelled
    started_at: datetime
    completed_at: Optional[datetime]
    duration_ms: float
    steps_executed: int
    steps_failed: int
    error: Optional[str] = None
    retries_used: int = 0
    agent_fallback_used: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }

class WorkflowMetrics:
    """
    Collects and aggregates workflow execution metrics.
    """
    
    def __init__(self):
        self._executions: List[ExecutionRecord] = []
        self._template_usage: Dict[str, int] = defaultdict(int)
        self._success_count = 0
        self._failure_count = 0
    
    def record_execution(
        self,
        execution_id: str,
        workflow_id: str,
        status: str,
        started_at: datetime,
        completed_at: datetime,
        steps_executed: int,
        steps_failed: int = 0,
        template_id: Optional[str] = None,
        error: Optional[str] = None,
        retries_used: int = 0,
        agent_fallback_used: bool = False
    ):
        """Record a workflow execution"""
        duration_ms = (completed_at - started_at).total_seconds() * 1000
        
        record = ExecutionRecord(
            execution_id=execution_id,
            workflow_id=workflow_id,
            template_id=template_id,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            steps_executed=steps_executed,
            steps_failed=steps_failed,
            error=error,
            retries_used=retries_used,
            agent_fallback_used=agent_fallback_used
        )
        
        self._executions.append(record)
        
        if template_id:
            self._template_usage[template_id] += 1
        
        if status == "completed":
            self._success_count += 1
        else:
            self._failure_count += 1
        
        logger.info(f"Recorded execution {execution_id}: {status} ({duration_ms:.1f}ms)")
    
    def get_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get summary metrics for the last N days"""
        cutoff = datetime.now() - timedelta(days=days)
        recent = [e for e in self._executions if e.started_at >= cutoff]
        
        if not recent:
            return {
                "period_days": days,
                "total_executions": 0,
                "success_rate": 0,
                "avg_duration_ms": 0,
                "top_templates": [],
                "retries_total": 0,
                "agent_fallbacks": 0
            }
        
        total = len(recent)
        successes = sum(1 for e in recent if e.status == "completed")
        avg_duration = sum(e.duration_ms for e in recent) / total
        retries = sum(e.retries_used for e in recent)
        fallbacks = sum(1 for e in recent if e.agent_fallback_used)
        
        # Top templates
        template_counts = defaultdict(int)
        for e in recent:
            if e.template_id:
                template_counts[e.template_id] += 1
        
        top_templates = sorted(template_counts.items(), key=lambda x: -x[1])[:5]
        
        return {
            "period_days": days,
            "total_executions": total,
            "success_rate": round(successes / total * 100, 1),
            "avg_duration_ms": round(avg_duration, 1),
            "top_templates": [{"id": t[0], "count": t[1]} for t in top_templates],
            "retries_total": retries,
            "agent_fallbacks": fallbacks
        }
    
    def get_recent_executions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent execution records"""
        recent = sorted(self._executions, key=lambda e: e.started_at, reverse=True)[:limit]
        return [e.to_dict() for e in recent]
    
    def get_workflow_stats(self, workflow_id: str) -> Dict[str, Any]:
        """Get stats for a specific workflow"""
        workflow_execs = [e for e in self._executions if e.workflow_id == workflow_id]
        
        if not workflow_execs:
            return {"workflow_id": workflow_id, "executions": 0}
        
        total = len(workflow_execs)
        successes = sum(1 for e in workflow_execs if e.status == "completed")
        avg_duration = sum(e.duration_ms for e in workflow_execs) / total
        
        return {
            "workflow_id": workflow_id,
            "executions": total,
            "success_rate": round(successes / total * 100, 1),
            "avg_duration_ms": round(avg_duration, 1),
            "last_run": max(e.started_at for e in workflow_execs).isoformat()
        }

# Global metrics instance
metrics = WorkflowMetrics()
