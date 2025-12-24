import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from core.database import SessionLocal
from service_delivery.models import Project, ProjectTask, Milestone
from core.workforce_analytics import WorkforceAnalyticsService

logger = logging.getLogger(__name__)

class TimelinePredictionService:
    """
    Predicts project completion dates based on historical velocity and task complexity.
    """

    def __init__(self, db_session: Any = None, analytics_service: Any = None):
        self.db = db_session
        self.analytics = analytics_service or WorkforceAnalyticsService(db_session)

    def predict_completion(self, project_id: str) -> Optional[datetime]:
        """
        Estimates the completion date for a project.
        """
        db = self.db or SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                logger.error(f"Project {project_id} not found for timeline prediction")
                return None

            # 1. Calculate Remaining Work (Total hours of pending/in_progress tasks)
            # In a real system, we'd use 'estimated_hours' if available. 
            # Fallback: Assume average task duration is 4 hours if not specified.
            pending_tasks = (
                db.query(ProjectTask)
                .filter(ProjectTask.project_id == project_id)
                .filter(ProjectTask.status.notin_(["completed", "canceled"]))
                .all()
            )
            
            total_remaining_hours = sum([getattr(t, 'estimated_hours', 4.0) for t in pending_tasks])
            
            if total_remaining_hours == 0:
                return datetime.utcnow()

            # 2. Get Team Velocity (hours completed per week)
            # Using 30-day velocity from analytics
            velocity_data = self.analytics.calculate_team_velocity(project.workspace_id, days=30)
            # velocity_data: {"total_completed": N, "avg_cycle_time_hours": X, "throughput_per_day": Y}
            
            throughput_per_day = velocity_data.get("throughput_per_day", 0.5) # Default to 0.5 tasks/day
            if throughput_per_day == 0:
                throughput_per_day = 0.5 # Safety fallback
                
            # Convert throughput (tasks) to hours (assuming 4h/task)
            velocity_hours_per_day = throughput_per_day * 4.0
            
            # 3. Apply Multipliers (Complexity, Context Switching)
            # If the focus score is low, completion takes longer
            # (Note: In a multi-user project, we might aggregate focus scores)
            multiplier = 1.0
            
            # 4. Calculate Days to Finish
            days_to_finish = total_remaining_hours / velocity_hours_per_day
            
            predicted_date = datetime.utcnow() + timedelta(days=days_to_finish)
            
            # 5. Update Project
            project.predicted_end_date = predicted_date
            db.commit()
            
            return predicted_date
        finally:
            if not self.db:
                db.close()
