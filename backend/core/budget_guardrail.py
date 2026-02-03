import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from service_delivery.models import Project, Milestone, ProjectTask, BudgetStatus
from accounting.models import Transaction, Bill
from core.database import get_db_session

logger = logging.getLogger(__name__)

class BudgetGuardrailService:
    """
    Monitors project budgets against real-time actual burn (labor + expenses).
    """

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session

    async def calculate_project_burn(self, project_id: str) -> Dict[str, Any]:
        """
        Aggregates costs for the project.
        """
        db = self.db or get_db_session()
        try:
            # 1. Labor Costs (Calculated from project tasks)
            # In a real system, we'd join with User.hourly_cost_rate
            # For this MVP, we'll use a default cost rate or metadata
            labor_burn = self._calculate_labor_burn(project_id, db)
            
            # 2. Expenses (Transactions/Bills linked to project)
            expense_burn = self._calculate_expense_burn(project_id, db)
            
            total_burn = labor_burn + expense_burn
            
            # Update Project Record
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.actual_burn = total_burn
                self._update_status(project)
                db.commit()
            
            return {
                "project_id": project_id,
                "labor_burn": labor_burn,
                "expense_burn": expense_burn,
                "total_burn": total_burn,
                "status": project.budget_status.value if project else "unknown"
            }
        finally:
            if not self.db:
                db.close()

    def _calculate_labor_burn(self, project_id: str, db: Session) -> float:
        """Sum of actual_hours * user.hourly_cost_rate for all tasks in project."""
        from core.models import User
        
        # Simplified for MVP: sum(task.actual_hours * (user.hourly_cost_rate or 50.0))
        # Note: In a real query, we'd use a join
        tasks = db.query(ProjectTask).filter(ProjectTask.project_id == project_id).all()
        total = 0.0
        for task in tasks:
            rate = 50.0 # Default hourly rate if user not found/no rate
            if task.assigned_to:
                user = db.query(User).filter(User.id == task.assigned_to).first()
                if user and user.hourly_cost_rate:
                    rate = user.hourly_cost_rate
            total += (task.actual_hours or 0.0) * rate
        return total

    def _calculate_expense_burn(self, project_id: str, db: Session) -> float:
        """Sum of transactions and bills linked to project."""
        tx_burn = db.query(func.sum(Transaction.amount)).filter(Transaction.project_id == project_id).scalar() or 0.0
        bill_burn = db.query(func.sum(Bill.amount)).filter(Bill.project_id == project_id).scalar() or 0.0
        return float(tx_burn + bill_burn)

    def _update_status(self, project: Project):
        """Updates Project.budget_status based on burn thresholds."""
        if not project.budget_amount or project.budget_amount == 0:
            project.budget_status = BudgetStatus.ON_TRACK
            return

        ratio = project.actual_burn / project.budget_amount
        
        if ratio >= 1.0:
            project.budget_status = BudgetStatus.OVER_BUDGET
        elif ratio >= 0.8:
            project.budget_status = BudgetStatus.AT_RISK
        else:
            project.budget_status = BudgetStatus.ON_TRACK
        
        logger.info(f"Project {project.id} status updated to {project.budget_status.value} (Ratio: {ratio:.2f})")
