import logging
from typing import Any, Dict
from ecommerce.models import EcommerceCustomer
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class DiscountOptimizer:
    def __init__(self, db: Session):
        self.db = db

    def get_optimal_discount(self, customer_id: str, base_total: float, margin_floor: float = 0.0) -> float:
        """
        Determines the optimal discount percentage based on customer value and churn risk.
        """
        customer = self.db.query(EcommerceCustomer).filter(EcommerceCustomer.id == customer_id).first()
        if not customer:
            return 0.0

        risk_score = customer.risk_score or 0.0
        
        # 1. Churn Risk Logic
        if risk_score > 70:
            # If they are very high risk, a standard discount is unlikely to save them.
            # We suggest 0% here to save margin, or trigger a custom "Retention Deal" manually.
            logger.warning(f"Discount Optimizer: High risk customer {customer_id} (Score: {risk_score}). Suggesting 0% discount to protect margin.")
            return 0.0

        # 2. Volume Logic
        discount_pct = 0.0
        if base_total > 5000:
            discount_pct = 0.15
        elif base_total > 1000:
            discount_pct = 0.10
        elif base_total > 500:
            discount_pct = 0.05

        # 3. Loyalty Bonus (Low Risk)
        if risk_score < 20:
            discount_pct += 0.02 # Extra 2% for loyal customers
            logger.info(f"Discount Optimizer: Adding 2% loyalty bonus for low-risk customer {customer_id}.")

        # 4. Margin Protection
        discount_amount = base_total * discount_pct
        if base_total - discount_amount < margin_floor:
            # Cap discount to ensure we stay above the margin floor
            available_discount = max(0, base_total - margin_floor)
            discount_pct = (available_discount / base_total) if base_total > 0 else 0.0
            logger.info(f"Discount Optimizer: Capping discount at {discount_pct:.2%} to respect margin floor of {margin_floor}.")

        return round(discount_pct, 4)
