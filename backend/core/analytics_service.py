import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from core.database import SessionLocal
from core.models import AgentModelMetrics, AgentRegistry, AgentFeedback, AgentExecution

logger = logging.getLogger(__name__)

class AnalyticsService:
    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()

    def get_agent_performance(self, tenant_id: str) -> Dict[str, Any]:
        """
        Aggregate operational performance metrics for a tenant's agents.
        """
        try:
            # 1. Global Status
            metrics = self.db.query(AgentModelMetrics).filter(
                AgentModelMetrics.tenant_id == tenant_id
            ).all()

            if not metrics:
                return {
                    "globalStatus": {
                        "avgAccuracy": 0.0,
                        "avgConfidence": 0.0,
                        "totalTasks": 0,
                        "successRate": 0.0
                    },
                    "agentTrends": [],
                    "agentBreakdown": []
                }

            total_tasks = sum(m.total_experiences for m in metrics)
            total_success = sum(m.success_count for m in metrics)
            avg_accuracy = sum(m.accuracy for m in metrics) / len(metrics)
            avg_confidence = sum(m.confidence for m in metrics) / len(metrics)
            
            global_status = {
                "avgAccuracy": round(avg_accuracy, 2),
                "avgConfidence": round(avg_confidence, 2),
                "totalTasks": total_tasks,
                "successRate": round(total_success / total_tasks, 2) if total_tasks > 0 else 0.0
            }

            # 2. Agent Breakdown
            agent_breakdown = []
            for m in metrics:
                agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == m.agent_id).first()
                agent_name = agent.name if agent else "Unknown Agent"
                
                # Fetch recent feedback for this agent
                feedback_count = self.db.query(AgentFeedback).filter(
                    AgentFeedback.agent_id == m.agent_id,
                    AgentFeedback.tenant_id == tenant_id
                ).count()

                agent_breakdown.append({
                    "agentId": m.agent_id,
                    "agentName": agent_name,
                    "successRate": round(m.success_count / m.total_experiences, 2) if m.total_experiences > 0 else 0.0,
                    "confidence": round(m.confidence, 2),
                    "accuracy": round(m.accuracy, 2),
                    "feedbackCount": feedback_count
                })

            # 3. Trends (Aggregated from AgentExecutions)
            # Fetch last 7 days of performance trends
            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
            
            # Simple aggregation by date using started_at
            # In a massive scale system, this would come from a dedicated metrics/OLAP table
            trend_data = self.db.query(
                func.date(AgentExecution.started_at).label('date'),
                func.count(AgentExecution.id).label('total'),
                func.sum(case((AgentExecution.status == 'completed', 1), else_=0)).label('success')
            ).filter(
                AgentExecution.tenant_id == tenant_id,
                AgentExecution.started_at >= seven_days_ago
            ).group_by(
                func.date(AgentExecution.started_at)
            ).order_by(
                func.date(AgentExecution.started_at).asc()
            ).all()

            agent_trends = []
            for day in trend_data:
                success_rate = round(day.success / day.total, 2) if day.total > 0 else 0.0
                agent_trends.append({
                    "date": day.date.isoformat() if hasattr(day.date, 'isoformat') else str(day.date),
                    "success_rate": success_rate,
                    "confidence": global_status["avgConfidence"] # Simplified confidence trend for now
                })

            # If no trend data exists, return empty or minimal set
            if not agent_trends:
                agent_trends = [{
                    "date": datetime.now(timezone.utc).date().isoformat(),
                    "success_rate": global_status["successRate"],
                    "confidence": global_status["avgConfidence"]
                }]

            return {
                "globalStatus": global_status,
                "agentTrends": agent_trends,
                "agentBreakdown": agent_breakdown
            }
        except Exception as e:
            logger.error(f"Error fetching agent performance: {e}")
            return {"error": str(e)}
        finally:
            if not self.db: # Only close if we created it
                self.db.close()

    def record_performance_update(self, agent_id: str, tenant_id: str, success: bool, db: Optional[Session] = None):
        """
        Update AgentModelMetrics for an agent step.
        """
        target_db = db or self.db
        try:
            metric = target_db.query(AgentModelMetrics).filter(
                AgentModelMetrics.agent_id == agent_id,
                AgentModelMetrics.tenant_id == tenant_id
            ).first()

            if not metric:
                # Create initial metric from AgentRegistry
                agent = target_db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
                metric = AgentModelMetrics(
                    model_id=f"model_{agent_id}",
                    agent_id=agent_id,
                    tenant_id=tenant_id,
                    confidence=agent.confidence_score if agent else 0.5,
                    accuracy=0.5,
                    success_count=1 if success else 0,
                    failure_count=0 if success else 1,
                    total_experiences=1
                )
                self.db.add(metric)
            else:
                metric.total_experiences += 1
                if success:
                    metric.success_count += 1
                else:
                    metric.failure_count += 1
                
                # Dynamic Accuracy Calculation (Running Average)
                metric.accuracy = metric.success_count / metric.total_experiences
                
                # Sync confidence from registry (which implements the complex maturity logic)
                agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
                if agent:
                    metric.confidence = agent.confidence_score
                
                metric.last_updated = datetime.now(timezone.utc)

            target_db.commit()
        except Exception as e:
            logger.error(f"Error recording performance update: {e}")
            target_db.rollback()
        finally:
            # We don't close here as this is typically called within an active transaction or service loop
            pass

# Global instance
analytics_service = AnalyticsService()
