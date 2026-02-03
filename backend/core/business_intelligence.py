import logging
from typing import Dict, Any, List, Optional
from core.database import get_db_session
from ecommerce.models import EcommerceOrder
from sales.models import Deal
from core.models import BusinessRule
from core.auto_invoicer import AutoInvoicer

logger = logging.getLogger(__name__)

class BusinessEventIntelligence:
    """
    Processes extracted business events to update system state.
    """

    def __init__(self, db_session: Any = None):
        self.db = db_session
        self.invoicer = AutoInvoicer(db_session=db_session)

    async def process_extracted_events(self, knowledge: Dict[str, Any], workspace_id: str):
        """
        Analyzes extracted entities and relationships to trigger business logic.
        """
        db = self.db or get_db_session()
        try:
            # 1. Process Shipment Updates
            await self._handle_shipments(knowledge, workspace_id, db)
            
            # 2. Process Quoting Intents
            await self._handle_quotes(knowledge, workspace_id, db)
            
            # 3. Process Purchase/Sales Orders
            await self._handle_orders(knowledge, workspace_id, db)
            
            # 4. Process Business Rules
            await self._handle_rules(knowledge, workspace_id, db)
            
            db.commit()
        except Exception as e:
            logger.error(f"Error processing business events: {e}")
            db.rollback()
        finally:
            if not self.db:
                db.close()

    async def _handle_shipments(self, knowledge: Dict[str, Any], workspace_id: str, db: Any):
        """
        Updates order status based on extracted shipment info.
        """
        shipments = [e for e in knowledge.get("entities", []) if e.get("type") == "Shipment"]
        relationships = knowledge.get("relationships", [])

        for ship in shipments:
            props = ship.get("properties", {})
            tracking = props.get("tracking_number")
            carrier = props.get("carrier")
            status = props.get("status", "shipped")

            if not tracking:
                continue

            # Find relationships that link this shipment to an order
            ship_rel = [r for r in relationships if r.get("from") == ship.get("id") and r.get("type") == "UPDATES_STATUS"]

            for rel in ship_rel:
                order_entity_id = rel.get("to")
                order_entity = next((e for e in knowledge.get("entities", []) if e.get("id") == order_entity_id), None)

                if order_entity and order_entity.get("type") in ["EcommerceOrder", "Order"]:
                    # Try to find order by external_id or metadata
                    order_id = order_entity.get("properties", {}).get("id")
                    external_id = order_entity.get("properties", {}).get("external_id")

                    # Query database for order
                    from ecommerce.models import EcommerceOrder
                    order = None
                    if order_id:
                        order = db.query(EcommerceOrder).filter(
                            EcommerceOrder.id == order_id,
                            EcommerceOrder.workspace_id == workspace_id
                        ).first()
                    elif external_id:
                        order = db.query(EcommerceOrder).filter(
                            EcommerceOrder.external_id == external_id,
                            EcommerceOrder.workspace_id == workspace_id
                        ).first()

                    if order:
                        # Update order status and metadata
                        if status in ["shipped", "in_transit"]:
                            order.status = "fulfilled"
                        elif status == "delivered":
                            order.status = "delivered" if hasattr(order, 'status') and "delivered" in [s.value for s in order.__table__.columns.status.type.enums] else "fulfilled"

                        # Update metadata with shipment info
                        if not order.metadata_json:
                            order.metadata_json = {}
                        order.metadata_json.update({
                            "tracking_number": tracking,
                            "carrier": carrier,
                            "shipped_at": props.get("shipped_at"),
                            "estimated_delivery": props.get("estimated_delivery")
                        })

                        logger.info(f"Updated order {order.id} with shipment tracking {tracking}")
                    else:
                        logger.warning(f"Order not found for shipment {tracking}")

    async def _handle_quotes(self, knowledge: Dict[str, Any], workspace_id: str, db: Any):
        """
        Handles quote requests and offers.
        """
        intents = [rel.get("to") for rel in knowledge.get("relationships", []) if rel.get("type") == "INTENT"]
        entities = knowledge.get("entities", [])

        # Find quote entities
        quote_entities = [e for e in entities if e.get("type") in ["Quote", "QuoteRequest", "QuoteOffer"]]

        for quote_entity in quote_entities:
            props = quote_entity.get("properties", {})
            quote_type = props.get("quote_type", "estimate")  # estimate, proposal, offer

            # Extract quote details
            amount = props.get("amount")
            currency = props.get("currency", "USD")
            valid_until = props.get("valid_until")
            customer_id = props.get("customer_id")
            deal_id = props.get("deal_id")

            if "request_quote" in intents or quote_type == "request":
                # Create a new quote request in the system
                # For now, store in metadata of related deal or create a task
                if deal_id:
                    from sales.models import Deal
                    deal = db.query(Deal).filter(
                        Deal.id == deal_id,
                        Deal.workspace_id == workspace_id
                    ).first()

                    if deal:
                        if not deal.metadata_json:
                            deal.metadata_json = {}

                        # Track quote request in deal metadata
                        if "quote_requests" not in deal.metadata_json:
                            deal.metadata_json["quote_requests"] = []

                        deal.metadata_json["quote_requests"].append({
                            "requested_at": datetime.now().isoformat(),
                            "amount": amount,
                            "currency": currency,
                            "status": "pending"
                        })

                        logger.info(f"Quote request recorded for deal {deal.id}")

            elif "offer_quote" in intents or quote_type in ["offer", "proposal"]:
                # Process quote offer
                # Could create a document, send notification, or update deal value
                if deal_id:
                    from sales.models import Deal
                    deal = db.query(Deal).filter(
                        Deal.id == deal_id,
                        Deal.workspace_id == workspace_id
                    ).first()

                    if deal:
                        # Update deal with quote offer
                        if amount:
                            deal.value = amount

                        if not deal.metadata_json:
                            deal.metadata_json = {}

                        if "quotes" not in deal.metadata_json:
                            deal.metadata_json["quotes"] = []

                        deal.metadata_json["quotes"].append({
                            "offered_at": datetime.now().isoformat(),
                            "amount": amount,
                            "currency": currency,
                            "valid_until": valid_until,
                            "status": "sent"
                        })

                        logger.info(f"Quote offer recorded for deal {deal.id}: {amount} {currency}")

    async def _handle_orders(self, knowledge: Dict[str, Any], workspace_id: str, db: Any):
        """
        Links POs and Sales Orders.
        """
        entities = knowledge.get("entities", [])
        relationships = knowledge.get("relationships", [])

        # Find Purchase Orders
        pos = [e for e in entities if e.get("type") == "PurchaseOrder"]

        for po in pos:
            props = po.get("properties", {})
            po_id = props.get("id")
            po_number = props.get("po_number")
            amount = props.get("amount")
            vendor = props.get("vendor")

            # Find relationships linking PO to deals or sales orders
            po_rels = [r for r in relationships if r.get("from") == po.get("id") and r.get("type") in ["LINKS_TO", "REFERS_TO"]]

            for rel in po_rels:
                target_entity_id = rel.get("to")
                target_entity = next((e for e in entities if e.get("id") == target_entity_id), None)

                if target_entity and target_entity.get("type") in ["Deal", "SalesOrder", "Contract"]:
                    # Link PO to Deal
                    if target_entity.get("type") == "Deal":
                        from sales.models import Deal
                        deal_id = target_entity.get("properties", {}).get("id")

                        deal = db.query(Deal).filter(
                            Deal.id == deal_id,
                            Deal.workspace_id == workspace_id
                        ).first()

                        if deal:
                            if not deal.metadata_json:
                                deal.metadata_json = {}

                            # Store PO information in deal metadata
                            if "purchase_orders" not in deal.metadata_json:
                                deal.metadata_json["purchase_orders"] = []

                            deal.metadata_json["purchase_orders"].append({
                                "po_id": po_id,
                                "po_number": po_number,
                                "amount": amount,
                                "vendor": vendor,
                                "linked_at": datetime.now().isoformat()
                            })

                            logger.info(f"Linked PO {po_number} to deal {deal.id}")

                    # Could also link to ecommerce orders if Sales Order entity exists
                    elif target_entity.get("type") == "SalesOrder":
                        from ecommerce.models import EcommerceOrder
                        order_id = target_entity.get("properties", {}).get("id")

                        order = db.query(EcommerceOrder).filter(
                            EcommerceOrder.id == order_id,
                            EcommerceOrder.workspace_id == workspace_id
                        ).first()

                        if order:
                            if not order.metadata_json:
                                order.metadata_json = {}

                            order.metadata_json["purchase_order"] = {
                                "po_id": po_id,
                                "po_number": po_number,
                                "amount": amount,
                                "vendor": vendor
                            }

                            logger.info(f"Linked PO {po_number} to order {order.id}")

    async def _handle_rules(self, knowledge: Dict[str, Any], workspace_id: str, db: Any):
        """
        Stores extracted business rules and calculation logic.
        """
        rules = [e for e in knowledge.get("entities", []) if e.get("type") == "BusinessRule"]
        for rule_entity in rules:
            props = rule_entity.get("properties", {})
            desc = props.get("description", "Untitled Rule")
            
            # Simple upsert logic based on description for prototype
            existing = db.query(BusinessRule).filter(
                BusinessRule.workspace_id == workspace_id,
                BusinessRule.description == desc
            ).first()
            
            if existing:
                existing.rule_type = props.get("type", "pricing")
                existing.formula = props.get("value") or props.get("formula")
                existing.applies_to = props.get("applies_to")
            else:
                new_rule = BusinessRule(
                    workspace_id=workspace_id,
                    description=desc,
                    rule_type=props.get("type", "pricing"),
                    formula=props.get("value") or props.get("formula"),
                    applies_to=props.get("applies_to")
                )
                db.add(new_rule)
            
            logger.info(f"Processed BusinessRule: {desc}")
