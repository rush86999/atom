"""
B2B Procurement Service
Handles Purchase Order (PO) extraction and personalized pricing for B2B customers.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from ecommerce.b2b_data_push_service import B2BDataPushService
from ecommerce.models import EcommerceCustomer, EcommerceOrderItem
from sqlalchemy.orm import Session

from integrations.ai_enhanced_service import (
    AIModelType,
    AIRequest,
    AIServiceType,
    AITaskType,
    ai_enhanced_service,
)

logger = logging.getLogger(__name__)

class B2BProcurementService:
    def __init__(self, db: Session):
        self.db = db

    async def extract_po_from_text(self, text: str) -> Dict[str, Any]:
        """
        Use AI to extract PO details from unstructured email text.
        """
        try:
            ai_request = AIRequest(
                request_id=f"po_extraction_{json.dumps(text[:20])}",
                task_type=AITaskType.CONTENT_ANALYSIS,
                model_type=AIModelType.GPT_4,
                service_type=AIServiceType.OPENAI,
                input_data={
                    "text": text,
                    "extraction_schema": {
                        "items": [
                            {"sku": "string", "quantity": "integer", "unit_price": "float", "description": "string"}
                        ],
                        "po_number": "string",
                        "customer_name": "string",
                        "confidence_score": "float (0.0 to 1.0)",
                        "reasoning": "string"
                    }
                },
                prompt_override="""
                Extract Purchase Order details from the following email text. 
                If items are found, map them to SKUs if possible. 
                Provide a confidence_score based on how certain you are of the item quantities and pricing.
                Return a JSON object matching the extraction_schema.
                """
            )
            
            ai_response = await ai_enhanced_service.process_ai_request(ai_request)
            
            if ai_response.ok and ai_response.output_data:
                # Ensure confidence_score is present
                data = ai_response.output_data
                if "confidence_score" not in data:
                    data["confidence_score"] = 0.7 # Default conservative score
                return data
            else:
                logger.error(f"AI PO extraction failed: {ai_response.error_message}")
                return {"items": [], "error": "AI extraction failed", "confidence_score": 0.0}
        except Exception as e:
            logger.error(f"Error extracting PO from text: {e}")
            return {"items": [], "error": str(e), "confidence_score": 0.0}

    def calculate_personalized_price(self, customer_id: str, product_id: str, sku: str, base_price: float) -> Dict[str, Any]:
        """
        Apply personalized pricing logic for a B2B customer.
        Returns the optimized price and the source of the pricing (price_list_id).
        """
        customer = self.db.query(EcommerceCustomer).filter(EcommerceCustomer.id == customer_id).first()
        if not customer or not customer.is_b2b or not customer.pricing_config:
            return {"price": base_price, "price_list_id": "standard"}

        config = customer.pricing_config
        final_price = base_price
        price_source = "standard"

        # 1. Check for SKU-specific override
        sku_overrides = config.get("sku_overrides", {})
        if sku in sku_overrides:
            final_price = sku_overrides[sku]
            price_source = f"personalized_sku_{sku}"
        elif product_id in sku_overrides:
            final_price = sku_overrides[product_id]
            price_source = f"personalized_prod_{product_id}"
        
        # 2. Apply global discount if no SKU override
        elif "global_discount" in config:
            discount = float(config["global_discount"]) # e.g. 0.1 for 10%
            final_price = base_price * (1 - discount)
            price_source = "global_b2b_discount"

        return {
            "price": round(final_price, 2),
            "price_list_id": price_source
        }

    async def create_draft_order_from_po(self, workspace_id: str, customer_email: str, po_data: Dict[str, Any]) -> str:
        """
        Create a draft order from extracted PO data.
        Returns the ID of the created draft order.
        """
        # 1. Resolve Customer
        from core.identity_resolver import CustomerResolutionEngine
        resolver = CustomerResolutionEngine(self.db)
        customer = resolver.resolve_customer(
            workspace_id,
            customer_email,
            po_data.get("customer_name", "").split()[0] if po_data.get("customer_name") else "",
            po_data.get("customer_name", "").split()[-1] if po_data.get("customer_name") and " " in po_data.get("customer_name") else ""
        )

        # 2. Create Order Header
        from ecommerce.models import EcommerceOrder
        confidence = float(po_data.get("confidence_score", 0.0))
        
        # Determine status: if low confidence or in learning mode, require review
        # In a real system, 'learning_mode' would be a workspace setting
        LEARNING_MODE = True 
        CONFIDENCE_THRESHOLD = 0.9
        
        status = "draft"
        if LEARNING_MODE or confidence < CONFIDENCE_THRESHOLD:
            status = "awaiting_review"
            logger.info(f"Order status set to '{status}' (Confidence: {confidence}, Learning Mode: {LEARNING_MODE})")

        order = EcommerceOrder(
            workspace_id=workspace_id,
            customer_id=customer.id,
            order_number=f"DRAFT-{po_data.get('po_number', uuid.uuid4().hex[:6])}",
            status=status,
            confidence_score=confidence,
            metadata_json={"po_source": po_data}
        )
        self.db.add(order)
        self.db.flush()

        # 3. Add Items with Personalized Pricing
        total_price = 0.0
        for item in po_data.get("items", []):
            sku = item.get("sku")
            base_price = float(item.get("unit_price", 0.0))
            
            # Apply B2B Pricing
            pricing = self.calculate_personalized_price(customer.id, item.get("product_id"), sku, base_price)
            
            order_item = EcommerceOrderItem(
                order_id=order.id,
                product_id=item.get("product_id"),
                title=item.get("description") or sku,
                sku=sku,
                quantity=item.get("quantity", 1),
                price=pricing["price"],
                price_list_id=pricing["price_list_id"],
                metadata_json=item
            )
            self.db.add(order_item)
            total_price += pricing["price"] * item.get("quantity", 1)

        order.total_price = total_price
        self.db.commit()
        
        # 4. Trigger Integration Push (Phase 15) - ONLY if not in learning mode and high confidence
        if status == "draft": # 'draft' means it passed the automated check
            try:
                push_service = B2BDataPushService(self.db)
                await push_service.push_b2b_customer(customer.id)
                await push_service.push_draft_order(order.id)
            except Exception as e:
                logger.error(f"Failed to push B2B data to integrations: {e}")
        else:
            logger.info(f"Skipping integration push for order {order.id} due to '{status}' status.")

        logger.info(f"Created B2B Draft Order {order.order_number} for {customer_email}")
        return order.id

        logger.info(f"Created B2B Draft Order {order.order_number} for {customer_email}")
        return order.id
