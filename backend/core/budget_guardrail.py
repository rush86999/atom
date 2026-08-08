from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from accounting.models import Bill, Transaction
from service_delivery.models import BudgetStatus, Milestone, Project, ProjectTask
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database import SessionLocal

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
        # get_db_session() returns a context manager, NOT a Session — using it
        # as `db = self.db or get_db_session()` crashed with AttributeError on
        # the no-injected-session path. Own the session only when none was
        # injected (mirrors the marketing_agent fix, same bug shape).
        if self.db is not None:
            db = self.db
            owns_db = False
        else:
            db = SessionLocal()
            owns_db = True
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
            if owns_db:
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
                # `hourly_cost_rate` is not a live column on the User model
                # (commented out in core/models.py) — guard with getattr so the
                # default rate applies instead of an AttributeError.
                if user:
                    rate = getattr(user, "hourly_cost_rate", None) or 50.0
            total += (task.actual_hours or 0.0) * rate
        return total

    def _calculate_expense_burn(self, project_id: str, db: Session) -> float:
        """Sum of transactions and bills linked to project."""
        # func.sum on Numeric columns yields Decimal, while the `or 0.0`
        # fallback yields float — `float(tx + bill)` crashed with
        # TypeError when exactly one source had no rows. Convert each side.
        tx_burn = db.query(func.sum(Transaction.amount)).filter(Transaction.project_id == project_id).scalar()
        bill_burn = db.query(func.sum(Bill.amount)).filter(Bill.project_id == project_id).scalar()
        return float(tx_burn or 0.0) + float(bill_burn or 0.0)

    def _update_status(self, project: Project):
        """Updates Project.budget_status based on burn thresholds.

        Honors the per-project configurable thresholds
        (``warn_threshold_pct`` / ``block_threshold_pct``) declared on the
        Project model. Previously these columns were silently ignored and the
        thresholds were hard-coded to 80% / 100%, which let a project
        configured to block at, say, 70% keep reporting ``on_track`` well
        past its configured block threshold (an enforcement bypass).
        """
        if not project.budget_amount or project.budget_amount == 0:
            project.budget_status = BudgetStatus.ON_TRACK
            return

        ratio = project.actual_burn / project.budget_amount

        # Per-project thresholds (model defaults: warn=80, block=100).
        block_pct = getattr(project, "block_threshold_pct", None)
        warn_pct = getattr(project, "warn_threshold_pct", None)
        block_threshold = (float(block_pct) / 100.0) if block_pct else 1.0
        warn_threshold = (float(warn_pct) / 100.0) if warn_pct else 0.8

        if ratio >= block_threshold:
            project.budget_status = BudgetStatus.OVER_BUDGET
        elif ratio >= warn_threshold:
            project.budget_status = BudgetStatus.AT_RISK
        else:
            project.budget_status = BudgetStatus.ON_TRACK

        logger.info(f"Project {project.id} status updated to {project.budget_status.value} (Ratio: {ratio:.2f})")
