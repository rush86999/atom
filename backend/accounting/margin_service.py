import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from core.models import User
from service_delivery.models import Project, ProjectTask, Contract
from core.database import SessionLocal

logger = logging.getLogger(__name__)

class MarginCalculatorService:
    """
    Service for calculating project and product margins based on labor costs.
    """

    def calculate_project_labor_cost(self, project_id: str, db: Session = None) -> float:
        """Sum of (actual_hours * hourly_cost_rate) for all tasks in a project."""
        if not db:
            db = SessionLocal()
        
        try:
            tasks = db.query(ProjectTask).filter(ProjectTask.project_id == project_id).all()
            total_cost = 0.0
            for task in tasks:
                if task.assigned_to and task.actual_hours:
                    user = db.query(User).filter(User.id == task.assigned_to).first()
                    if user and user.hourly_cost_rate:
                        total_cost += (task.actual_hours * user.hourly_cost_rate)
            return round(total_cost, 2)
        finally:
            if not db:
                db.close()

    def get_project_margin(self, project_id: str, db: Session = None) -> Dict[str, Any]:
        """Returns Project Revenue - Labor Cost and margin percentage."""
        if not db:
            db = SessionLocal()
        
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return {"error": "Project not found"}
            
            revenue = project.budget_amount or 0.0
            labor_cost = self.calculate_project_labor_cost(project_id, db)
            
            margin_absolute = revenue - labor_cost
            margin_percentage = (margin_absolute / revenue * 100) if revenue > 0 else 0.0
            
            return {
                "project_id": project_id,
                "project_name": project.name,
                "revenue": revenue,
                "labor_cost": labor_cost,
                "gross_margin": round(margin_absolute, 2),
                "margin_percentage": round(margin_percentage, 2)
            }
        finally:
            if not db:
                db.close()

    def get_product_margins(self, workspace_id: str, db: Session = None) -> List[Dict[str, Any]]:
        """Aggregates margins across all projects for each BusinessProductService."""
        if not db:
            db = SessionLocal()
        
        try:
            from core.models import BusinessProductService
            products = db.query(BusinessProductService).filter(BusinessProductService.workspace_id == workspace_id).all()
            
            results = []
            for product in products:
                # Find all contracts for this product
                contracts = db.query(Contract).filter(Contract.product_service_id == product.id).all()
                contract_ids = [c.id for c in contracts]
                
                # Find projects for these contracts
                projects = db.query(Project).filter(Project.contract_id.in_(contract_ids)).all()
                
                total_revenue = 0.0
                total_cost = 0.0
                
                for project in projects:
                    total_revenue += (project.budget_amount or 0.0)
                    total_cost += self.calculate_project_labor_cost(project.id, db)
                
                # Also include tangible product sales cost if linked to orders
                from ecommerce.models import EcommerceOrderItem, EcommerceOrder
                order_items = db.query(EcommerceOrderItem).join(EcommerceOrder).filter(
                    EcommerceOrderItem.product_id == product.id,
                    EcommerceOrder.workspace_id == workspace_id
                ).all()
                
                for item in order_items:
                    total_revenue += (item.price * item.quantity)
                    total_cost += (product.unit_cost * item.quantity)
                
                margin_abs = total_revenue - total_cost
                margin_pct = (margin_abs / total_revenue * 100) if total_revenue > 0 else 0.0
                
                results.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "total_revenue": round(total_revenue, 2),
                    "total_labor_cost": round(total_cost, 2),
                    "gross_margin": round(margin_abs, 2),
                    "margin_percentage": round(margin_pct, 2)
                })
            
            return results
        finally:
            if not db:
                db.close()

margin_calculator = MarginCalculatorService()
