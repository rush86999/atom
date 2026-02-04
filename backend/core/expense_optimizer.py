import logging
from typing import Any, Dict, List
from accounting.models import Account, AccountType, Entity, Transaction
from sqlalchemy import func

from core.database import get_db_session

logger = logging.getLogger(__name__)

class ExpenseOptimizer:
    """
    Analyzes spend patterns to optimize expenses for small businesses.
    """

    def __init__(self, db_session: Any = None):
        self.db = db_session

    def analyze_vendor_spend(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Identifies recurring subscriptions and potential cost-saving opportunities.
        """
        db = self.db or get_db_session()
        try:
            # 1. Group transactions by description/merchant pattern
            # In a real system, we'd use 'merchant_name' from enriched transaction data
            spend_by_vendor = (
                db.query(Transaction.description, func.sum(Transaction.amount).label("total"), func.count(Transaction.id).label("count"))
                .filter(Transaction.workspace_id == workspace_id)
                .filter(Transaction.amount < 0)
                .group_by(Transaction.description)
                .all()
            )
            
            recommendations = []
            for desc, total, count in spend_by_vendor:
                total_abs = abs(total)
                
                # Heuristic 1: Recurring high-frequency small payments (possible subscriptions)
                if count >= 3:
                    # Look for cheaper alternatives for common categories (simulated)
                    if "aws" in desc.lower() or "google cloud" in desc.lower():
                        recommendations.append({
                            "vendor": desc,
                            "type": "infrastructure",
                            "monthly_spend": total_abs / count,
                            "finding": "recurring_infrastructure_spend",
                            "recommendation": "Review reserved instances or consider Spot instances to save ~30%."
                        })
                    elif "zoom" in desc.lower() or "slack" in desc.lower():
                        recommendations.append({
                            "vendor": desc,
                            "type": "saas",
                            "monthly_spend": total_abs / count,
                            "finding": "saas_subscription",
                            "recommendation": "Audit license usage. You may have 'Zombie' seats that are inactive."
                        })
                        
            return recommendations
        finally:
            if not self.db:
                db.close()

    def identify_tax_deductions(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Flags transactions that are likely business deductions but unmapped.
        """
        db = self.db or get_db_session()
        try:
            # Find transactions that are not yet categorized to an expense account
            # (Simplification: look for transactions with generic or missing account mapping)
            potential_deductions = []
            
            # Simulated NLP matching
            keywords = ["coffee", "dinner", "travel", "uber", "software", "office", "supplies"]
            
            transactions = (
                db.query(Transaction)
                .filter(Transaction.workspace_id == workspace_id)
                .filter(Transaction.amount < 0)
                .all()
            )
            
            for tx in transactions:
                lower_desc = tx.description.lower() if tx.description else ""
                matched_keyword = next((k for k in keywords if k in lower_desc), None)
                
                if matched_keyword:
                    potential_deductions.append({
                        "transaction_id": tx.id,
                        "description": tx.description,
                        "amount": abs(tx.amount),
                        "suggested_category": "Business Expense",
                        "reasoning": f"Keyword '{matched_keyword}' suggests a potential tax-deductible business expense."
                    })
                    
            return potential_deductions
        finally:
            if not self.db:
                db.close()
