import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.workflow_analytics_engine import get_analytics_engine

logger = logging.getLogger(__name__)

class AutomationInsightManager:
    def __init__(self, db_path: str = "analytics.db"):
        self.db_path = Path(db_path).expanduser().absolute()
        self.analytics = get_analytics_engine()

    def get_drift_metrics(self, user_id: str, workflow_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Calculate drift metrics for workflows belonging to the user.
        Drift = (Manual Overrides / Successful Executions)
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT 
                workflow_id,
                COUNT(*) as total_events,
                SUM(CASE WHEN event_type = 'step_completed' THEN 1 ELSE 0 END) as success_steps,
                SUM(CASE WHEN event_type = 'manual_override' THEN 1 ELSE 0 END) as overrides
            FROM workflow_events
            WHERE timestamp > ? AND user_id = ?
        """
        params = [
            (datetime.now() - timedelta(days=30)).isoformat(),
            user_id
        ]

        if workflow_id:
            query += " AND workflow_id = ?"
            params.append(workflow_id)

        query += " GROUP BY workflow_id"

        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            insights = []
            for row in rows:
                success_steps = row['success_steps'] or 0
                overrides = row['overrides'] or 0
                
                drift_score = (overrides / success_steps) if success_steps > 0 else 0
                
                # Determine recommendation
                recommendation = "STABLE"
                if drift_score > 0.5:
                    recommendation = "OPTIMIZE (High Overrides)"
                elif success_steps > 10 and overrides == 0:
                    recommendation = "HIGH_CONFIDENCE"
                
                insights.append({
                    "workflow_id": row['workflow_id'],
                    "success_steps": success_steps,
                    "overrides": overrides,
                    "drift_score": round(drift_score, 2),
                    "recommendation": recommendation
                })
            
            return insights

        except Exception as e:
            logger.error(f"Error calculating drift metrics: {e}")
            return []
        finally:
            conn.close()

    def get_underutilization_insights(self) -> List[Dict[str, Any]]:
        """
        Find workflows that are rarely triggered despite being active.

        Returns:
            List of underutilized workflows with usage statistics
        """
        try:
            from core.database import get_db_session
            from core.models import WorkflowExecution

            with get_db_session() as db:
                # Get workflows from the last 14 days
                from datetime import datetime, timedelta
                cutoff_date = datetime.now() - timedelta(days=14)

                # Find workflows with low execution counts
                # This is a simplified implementation
                recent_executions = db.query(
                    WorkflowExecution.workflow_id,
                    db.func.count(WorkflowExecution.id).label('execution_count')
                ).filter(
                    WorkflowExecution.created_at >= cutoff_date
                ).group_by(
                    WorkflowExecution.workflow_id
                ).all()

                # Convert to dict for easier lookup
                execution_counts = {row.workflow_id: row.execution_count for row in recent_executions}

                # Find underutilized workflows (0-2 executions in 14 days)
                underutilized = []
                for workflow_id, count in execution_counts.items():
                    if count <= 2:
                        underutilized.append({
                            "workflow_id": workflow_id,
                            "executions_last_14_days": count,
                            "status": "UNDERUTILIZED",
                            "recommendation": "Consider reviewing if this workflow is still needed"
                        })

                logger.info(f"Found {len(underutilized)} underutilized workflows")
                return underutilized

        except Exception as e:
            logger.error(f"Failed to get underutilization insights: {e}")
            return []

    def generate_all_insights(self, user_id: str) -> Dict[str, Any]:
        """Generate a comprehensive report of automation health for the user"""
        drift = self.get_drift_metrics(user_id)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "drift_insights": drift,
            "summary": {
                "total_monitored": len(drift),
                "needs_optimization": len([d for d in drift if "OPTIMIZE" in d["recommendation"]]),
                "stable": len([d for d in drift if d["recommendation"] == "STABLE"])
            }
        }

# Global instance
_insight_manager = None

def get_insight_manager() -> AutomationInsightManager:
    global _insight_manager
    if _insight_manager is None:
        _insight_manager = AutomationInsightManager()
    return _insight_manager
