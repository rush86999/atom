import logging
from typing import Any, Dict, List, Optional
from service_delivery.models import ProjectTask
from sqlalchemy.orm import Session

from core.database import get_db_session
from core.models import Team, User

logger = logging.getLogger(__name__)

class ResourceMonitor:
    """
    Calculates and monitors resource utilization and capacity.
    """

    def calculate_utilization(self, user_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Calculates the utilization percentage for a specific user.
        Utilization = (Estimated Hours of Active Tasks / Weekly Capacity) * 100
        """
        should_close = False
        if db is None:
            with get_db_session() as db:
                should_close = True

                try:
                    user = db.query(User).filter(User.id == user_id).first()
                    if not user:
                        return {"status": "error", "message": "User not found"}

                    # Fetch active tasks (pending or in_progress)
                    active_tasks = db.query(ProjectTask).filter(
                        ProjectTask.assigned_to == user_id,
                        ProjectTask.status.in_(["pending", "in_progress"])
                    ).all()

                    # Sum up estimated hours.
                    # We assume metadata_json might contain 'estimated_hours'. Fallback to a default.
                    total_estimated_hours = 0.0
                    for task in active_tasks:
                        est = 5.0 # Default if not specified
                        if task.metadata_json and isinstance(task.metadata_json, dict):
                            est = task.metadata_json.get("estimated_hours", 5.0)
                        total_estimated_hours += float(est)

                    capacity = user.capacity_hours or 40.0
                    utilization_pct = (total_estimated_hours / capacity) * 100

                    return {
                        "user_id": user_id,
                        "user_name": f"{user.first_name} {user.last_name}",
                        "total_estimated_hours": total_estimated_hours,
                        "weekly_capacity": capacity,
                        "utilization_percentage": round(utilization_pct, 2),
                        "active_task_count": len(active_tasks),
                        "risk_level": "high" if utilization_pct > 100 else "medium" if utilization_pct > 80 else "low"
                    }
                except Exception as e:
                    return {"status": "error", "message": f"Failed to calculate utilization: {e}"}

    def get_team_utilization(self, team_id: str) -> Dict[str, Any]:
        """
        Aggregates utilization for an entire team.
        """
        with get_db_session() as db:
            team = db.query(Team).filter(Team.id == team_id).first()
            if not team:
                return {"status": "error", "message": "Team not found"}

            member_reports = []
            total_load = 0.0
            total_capacity = 0.0

            for member in team.members:
                report = self.calculate_utilization(member.id, db=db)
                member_reports.append(report)
                total_load += report.get("total_estimated_hours", 0.0)
                total_capacity += report.get("weekly_capacity", 40.0)

            team_utilization = (total_load / total_capacity) * 100 if total_capacity > 0 else 0

            return {
                "team_id": team_id,
                "team_name": team.name,
                "average_utilization": round(team_utilization, 2),
                "member_reports": member_reports,
                "total_tasks": sum(r.get("active_task_count", 0) for r in member_reports)
            }

# Global Instance
resource_monitor = ResourceMonitor()
