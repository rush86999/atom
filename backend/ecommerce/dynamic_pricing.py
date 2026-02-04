import logging
from typing import Any, Dict
from sqlalchemy.orm import Session

from core.models import BusinessProductService

logger = logging.getLogger(__name__)

class DynamicPricingService:
    def __init__(self, db: Session):
        self.db = db

    def get_adjusted_price(self, product_id: str) -> float:
        """
        Calculates a dynamic price based on inventory, demand, and margin floors.
        """
        product = self.db.query(BusinessProductService).filter(BusinessProductService.id == product_id).first()
        if not product:
            return 0.0

        base_price = product.base_price
        stock = getattr(product, "stock_quantity", 50) # Default to 50 if field missing in some versions
        unit_cost = getattr(product, "unit_cost", 0.0)
        
        # Scarcity Multiplier (Low Stock)
        if stock > 0 and stock < 10:
            adjusted_price = base_price * 1.15
            logger.info(f"Dynamic Pricing: Scarcity adjustment (+15%) for {product_id}. New price: {adjusted_price}")
        # Liquidation Multiplier (High Stock)
        elif stock > 100:
            adjusted_price = base_price * 0.90
            logger.info(f"Dynamic Pricing: Liquidation adjustment (-10%) for {product_id}. New price: {adjusted_price}")
        else:
            adjusted_price = base_price

        # Competitor Matching (if available in metadata)
        metadata = product.metadata_json or {}
        competitor_price = metadata.get("competitor_price")
        if competitor_price:
            target_price = competitor_price * 0.98 # Undercut by 2%
            if target_price < adjusted_price:
                # Only undercut if it doesn't violate margin floor (10% above cost)
                margin_floor = unit_cost * 1.10
                if target_price >= margin_floor:
                    adjusted_price = target_price
                    logger.info(f"Dynamic Pricing: Competitor undercut (-2% vs {competitor_price}) for {product_id}. New price: {adjusted_price}")

        return round(adjusted_price, 2)
