import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import func
from core.database import SessionLocal
from core.models import User, Team
from service_delivery.models import ProjectTask, Project

logger = logging.getLogger(__name__)

class WorkforceAnalyticsService:
    """
    Analyzes team performance and identifies operational bottlenecks.
    """

    def __init__(self, db_session: Any = None):
        self.db = db_session

    def calculate_team_velocity(self, workspace_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Calculates throughput (tasks completed) and average cycle time.
        """
        db = self.db or SessionLocal()
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # 1. Total Completed Tasks
            completed_tasks = (
                db.query(ProjectTask)
                .filter(ProjectTask.workspace_id == workspace_id)
                .filter(ProjectTask.status == "completed")
                .filter(ProjectTask.completed_at >= start_date)
                .all()
            )
            
            total_completed = len(completed_tasks)
            
            # 2. Average Cycle Time (Created -> Completed)
            cycle_times = []
            for task in completed_tasks:
                if task.completed_at and task.created_at:
                    delta = (task.completed_at - task.created_at).total_seconds() / 3600.0 # hours
                    cycle_times.append(delta)
            
            avg_cycle_time = sum(cycle_times) / len(cycle_times) if cycle_times else 0.0
            
            return {
                "total_completed": total_completed,
                "avg_cycle_time_hours": avg_cycle_time,
                "throughput_per_day": total_completed / days if days > 0 else 0
            }
        finally:
            if not self.db:
                db.close()

    def detect_bottlenecks(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Identifies users with high task-to-capacity ratios or long-stalled tasks.
        """
        db = self.db or SessionLocal()
        try:
            # Find users with > 5 'in_progress' tasks
            bottlenecks = []
            
            in_progress_counts = (
                db.query(ProjectTask.assigned_to, func.count(ProjectTask.id).label("count"))
                .filter(ProjectTask.workspace_id == workspace_id)
                .filter(ProjectTask.status == "in_progress")
                .group_by(ProjectTask.assigned_to)
                .all()
            )
            
            for user_id, count in in_progress_counts:
                if count >= 5: # Arbitrary threshold for now
                    user = db.query(User).filter(User.id == user_id).first()
                    bottlenecks.append({
                        "user_id": user_id,
                        "user_name": f"{user.first_name} {user.last_name}" if user else "Unknown",
                        "reason": "high_workload",
                        "in_progress_count": count,
                        "severity": "high" if count >= 8 else "medium"
                    })
            
            # Add logic for 'Stalled' tasks (> 7 days in progress)
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            stalled_tasks = (
                db.query(ProjectTask)
                .filter(ProjectTask.workspace_id == workspace_id)
                .filter(ProjectTask.status == "in_progress")
                .filter(ProjectTask.updated_at <= seven_days_ago)
                .all()
            )
            
            for task in stalled_tasks:
                bottlenecks.append({
                    "task_id": task.id,
                    "task_name": task.name,
                    "reason": "stalled_progress",
                    "last_active": task.updated_at.isoformat(),
                    "severity": "medium"
                })
                
            return bottlenecks
        finally:
            if not self.db:
                db.close()

    def get_focus_score(self, user_id: str) -> float:
        """
        Calculates a 'Focus Score' (0-100) for a user.
        High switching between different projects/contexts lowers the score.
        """
        db = self.db or SessionLocal()
        try:
            # Analyze active tasks for different projects
            active_tasks = (
                db.query(ProjectTask)
                .filter(ProjectTask.assigned_to == user_id)
                .filter(ProjectTask.status == "in_progress")
                .all()
            )
            
            if not active_tasks:
                return 100.0
                
            project_ids = set([t.project_id for t in active_tasks])
            
            # Penalize for each project beyond 1
            penalty = (len(project_ids) - 1) * 15.0
            score = max(0.0, 100.0 - penalty)
            
            return score
        finally:
            if not self.db:
                db.close()
