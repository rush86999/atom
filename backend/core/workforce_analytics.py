import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import func
from core.database import get_db_session
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
        db = self.db or get_db_session()
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
        db = self.db or get_db_session()
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
        db = self.db or get_db_session()
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

    def calculate_estimation_bias(self, workspace_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates the variance between planned and actual durations/hours for a user or workspace.
        """
        db = self.db or get_db_session()
        try:
            query = db.query(ProjectTask).filter(ProjectTask.workspace_id == workspace_id).filter(ProjectTask.status == "completed")
            if user_id:
                query = query.filter(ProjectTask.assigned_to == user_id)
            
            completed_tasks = query.all()
            
            if not completed_tasks:
                return {"bias_factor": 1.0, "sample_size": 0, "status": "no_data"}
            
            duration_variances = []
            hour_variances = []
            
            for task in completed_tasks:
                # 1. Duration Bias: (Actual Time Taken) / (Planned Duration)
                # Note: ProjectTask doesn't have planned_duration, but it has due_date and created_at
                if task.completed_at and task.due_date and task.created_at:
                    planned_delta = (task.due_date - task.created_at).total_seconds()
                    actual_delta = (task.completed_at - task.created_at).total_seconds()
                    
                    if planned_delta > 0:
                        duration_variances.append(actual_delta / planned_delta)
                
                # 2. Effort Bias: actual_hours / (budget_hours - derived from project/milestone if needed)
                # For now, we'll use actual_hours if available
                if task.actual_hours > 0:
                    # In this mock, we assume '1.0' is the baseline unless we have a specific 'estimated_hours' field
                    # Let's assume metadata_json might contain 'estimated_hours'
                    estimated = 1.0
                    if task.metadata_json and "estimated_hours" in task.metadata_json:
                        estimated = float(task.metadata_json["estimated_hours"])
                    
                    if estimated > 0:
                        hour_variances.append(task.actual_hours / estimated)
            
            avg_duration_bias = sum(duration_variances) / len(duration_variances) if duration_variances else 1.0
            avg_hour_bias = sum(hour_variances) / len(hour_variances) if hour_variances else 1.0
            
            # Combined Bias Factor (Weighted)
            bias_factor = (avg_duration_bias * 0.4) + (avg_hour_bias * 0.6)
            
            return {
                "user_id": user_id,
                "bias_factor": round(bias_factor, 2),
                "duration_bias": round(avg_duration_bias, 2),
                "hour_bias": round(avg_hour_bias, 2),
                "sample_size": len(completed_tasks),
                "category": "optimistic" if bias_factor > 1.1 else "pessimistic" if bias_factor < 0.9 else "accurate"
            }
        finally:
            if not self.db:
                db.close()

    def get_user_bias_profile(self, user_id: str, workspace_id: str) -> Dict[str, Any]:
        """Convenience method for PM engine to get adjustment factor"""
        bias_data = self.calculate_estimation_bias(workspace_id, user_id)
        return {
            "user_id": user_id,
            "adjustment_multiplier": bias_data.get("bias_factor", 1.0),
            "category": bias_data.get("category", "accurate")
        }

    def map_skill_gaps(self, workspace_id: str) -> Dict[str, Any]:
        """
        Identifies missing competencies by comparing task requirements against team skills.
        """
        db = self.db or get_db_session()
        try:
            # 1. Fetch all active users and their skills
            users = db.query(User).filter(User.status == "active").all()
            team_skills = {} # skill -> count
            user_skill_map = {} # user_id -> set(skills)
            
            for u in users:
                skills = set(s.strip().lower() for s in u.skills.split(",")) if u.skills else set()
                user_skill_map[u.id] = skills
                for s in skills:
                    team_skills[s] = team_skills.get(s, 0) + 1
            
            # 2. Fetch all project tasks
            tasks = db.query(ProjectTask).filter(ProjectTask.workspace_id == workspace_id).all()
            
            unmet_requirements = {} # skill -> list(task_ids)
            assignment_mismatches = []
            
            for task in tasks:
                # Extract required skills from metadata
                required = []
                if task.metadata_json and "required_skills" in task.metadata_json:
                    raw_req = task.metadata_json["required_skills"]
                    if isinstance(raw_req, list):
                        required = [s.strip().lower() for s in raw_req]
                    elif isinstance(raw_req, str):
                        required = [s.strip().lower() for s in raw_req.split(",")]
                
                # Check for unmet requirements (nobody in the team has it)
                for req in required:
                    if req not in team_skills:
                        if req not in unmet_requirements:
                            unmet_requirements[req] = []
                        unmet_requirements[req].append(task.id)
                
                # Check for assignment mismatches (assigned user lacks required skills)
                if task.assigned_to and task.status != "completed":
                    user_skills = user_skill_map.get(task.assigned_to, set())
                    missing_skills = [s for s in required if s not in user_skills]
                    if missing_skills:
                        assignment_mismatches.append({
                            "task_id": task.id,
                            "task_name": task.name,
                            "user_id": task.assigned_to,
                            "missing_skills": missing_skills
                        })
            
            return {
                "workspace_id": workspace_id,
                "unmet_requirements": unmet_requirements,
                "assignment_mismatches": assignment_mismatches,
                "competency_density": team_skills,
                "team_size": len(users)
            }
        finally:
            if not self.db:
                db.close()
