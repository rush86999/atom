"""
Burnout Detection Engine
Analyzes productivity and communication patterns to detect signs of overload.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class WellnessScore(BaseModel):
    risk_level: str  # "Low", "Medium", "High", "Critical"
    score: float  # 0 to 100
    factors: Dict[str, float]
    recommendations: List[str]
    timestamp: datetime
    type: str = "burnout" # "burnout" | "deadline"

class BurnoutDetectionEngine:
    """Engine to detect signs of burnout and overload"""
    
    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        self.settings = settings or {
            "max_meeting_hours_daily": 5.0,
            "max_backlog_growth_rate": 1.2,
            "latency_threshold_hours": 4.0,
            "deadline_buffer_days": 2.0
        }

    async def calculate_burnout_risk(self, 
                                   meeting_metrics: Dict[str, Any],
                                   task_metrics: Dict[str, Any],
                                   comm_metrics: Dict[str, Any]) -> WellnessScore:
        # ... (rest of the existing method remains the same)
        factors = {}
        
        # 1. Meeting Density (Weight: 40%)
        avg_daily_meetings = meeting_metrics.get("total_hours", 0) / max(1, meeting_metrics.get("day_count", 1))
        meeting_density_score = min(100, (avg_daily_meetings / self.settings["max_meeting_hours_daily"]) * 100)
        factors["meeting_density"] = meeting_density_score
        
        # 2. Task Backlog Growth (Weight: 30%)
        open_tasks = task_metrics.get("open_tasks", 0)
        prev_open = task_metrics.get("previous_open_tasks", 0)
        growth_rate = open_tasks / max(1, prev_open)
        backlog_score = min(100, (growth_rate / self.settings["max_backlog_growth_rate"]) * 100)
        factors["backlog_growth"] = backlog_score
        
        # 3. Communication Latency (Weight: 30%)
        latency = comm_metrics.get("avg_response_latency_hours", 0)
        latency_score = min(100, (latency / self.settings["latency_threshold_hours"]) * 100)
        factors["comm_latency"] = latency_score
        
        # Weighted Average
        total_score = (meeting_density_score * 0.4) + (backlog_score * 0.3) + (latency_score * 0.3)
        
        # Determine Level
        if total_score >= 80:
            level = "Critical"
        elif total_score >= 60:
            level = "High"
        elif total_score >= 40:
            level = "Medium"
        else:
            level = "Low"
            
        # Recommendations
        recommendations = self._generate_recommendations(level, factors)
        
        return WellnessScore(
            risk_level=level,
            score=round(total_score, 2),
            factors=factors,
            recommendations=recommendations,
            timestamp=datetime.now(),
            type="burnout"
        )

    async def calculate_deadline_risk(self, tasks: List[Dict[str, Any]]) -> WellnessScore:
        """
        Analyze tasks to identify those likely to miss deadlines.
        tasks: [{"id": "1", "title": "X", "due_date": "...", "progress": 0.5, "estimated_hours": 10}]
        """
        high_risk_tasks = []
        factors = {"total_tasks": len(tasks), "at_risk_count": 0}
        total_risk_score = 0.0
        
        for task in tasks:
            due_date = task.get("due_date")
            if isinstance(due_date, str):
                due_date = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
            
            time_remaining = (due_date - datetime.now()).total_seconds() / 3600 # hours
            progress = task.get("progress", 0)
            est_hours = task.get("estimated_hours", 5)
            remaining_work_hours = est_hours * (1 - progress)
            
            # Risk ratio (Work / Time)
            # A ratio > 0.8 starts becoming risky assuming 8h work days
            risk_ratio = remaining_work_hours / max(1, time_remaining)
            
            if risk_ratio > 0.5:
                factors["at_risk_count"] += 1
                high_risk_tasks.append(task["title"])
                total_risk_score += (risk_ratio * 50) # Scale it
                
        avg_risk = min(100, total_risk_score / max(1, len(tasks)))
        
        if avg_risk >= 70:
            level = "Critical"
        elif avg_risk >= 40:
            level = "High"
        elif avg_risk >= 20:
            level = "Medium"
        else:
            level = "Low"
            
        recs = []
        if high_risk_tasks:
            recs.append(f"Send early reminders for: {', '.join(high_risk_tasks[:2])}")
            recs.append("Consider auto-rescheduling tasks with a risk ratio > 1.0.")
            recs.append("Escalate #1 priority tasks to collaborators for help.")
            
        return WellnessScore(
            risk_level=level,
            score=round(avg_risk, 2),
            factors=factors,
            recommendations=recs,
            timestamp=datetime.now(),
            type="deadline"
        )

    def _generate_recommendations(self, level: str, factors: Dict[str, float]) -> List[str]:
        recs = []
        if factors.get("meeting_density", 0) > 70:
            recs.append("Suggest rescheduling non-urgent meetings for next week.")
            recs.append("Block 2 hours of Focus Time on your calendar tomorrow.")
        
        if factors.get("backlog_growth", 0) > 70:
            recs.append("Consider delegating 3 high-effort tasks to available teammates.")
            recs.append("Declare a 'No-Meeting Friday' to clear the backlog.")
            
        if factors.get("comm_latency", 0) > 70:
            recs.append("Enable 'Do Not Disturb' mode for deep work blocks.")
            recs.append("Set expectations for delayed response times in your status.")
            
        if level == "Critical" and len(recs) == 0:
            recs.append("Take a mandatory unplugged day.")
            
        return recs

# Singleton instance
burnout_engine = BurnoutDetectionEngine()
