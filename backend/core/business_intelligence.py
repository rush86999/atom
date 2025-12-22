import logging
from typing import Dict, Any, List, Optional
from core.database import SessionLocal
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
        db = self.db or SessionLocal()
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
        for ship in shipments:
            props = ship.get("properties", {})
            tracking = props.get("tracking_number")
            
            # Find relationships that link this shipment to an order
            # (Simplified for MVP: search for order mentioned in same context or via rel)
            # In a real system, we'd use the UPDATES_STATUS relationship
            
            # Mock logic: if tracked, update most recent order (or find by ID in metadata)
            # For the prototype, we look for an EcommerceOrder external_id or internal ID
            pass

    async def _handle_quotes(self, knowledge: Dict[str, Any], workspace_id: str, db: Any):
        """
        Handles quote requests and offers.
        """
        intents = [rel.get("to") for rel in knowledge.get("relationships", []) if rel.get("type") == "INTENT"]
        
        if "request_quote" in intents:
            logger.info(f"Quote request detected for workspace {workspace_id}")
            # Logic to notify owner or draft a quote
            pass
            
        if "offer_quote" in intents:
            logger.info(f"Quote offer detected for workspace {workspace_id}")
            pass

    async def _handle_orders(self, knowledge: Dict[str, Any], workspace_id: str, db: Any):
        """
        Links POs and Sales Orders.
        """
        pos = [e for e in knowledge.get("entities", []) if e.get("type") == "PurchaseOrder"]
        for po in pos:
            po_id = po.get("properties", {}).get("id")
            logger.info(f"Extracted PO {po_id}")
            # Link to Deal or Contract
            pass

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
