import logging
from typing import Optional, Tuple
from accounting.models import Entity, EntityType
from ecommerce.models import EcommerceCustomer
from sales.models import Lead
from sqlalchemy import or_
from sqlalchemy.orm import Session

# Assuming a CRM contact model or similar exists, but using Lead for now as proxy
# In a real system, we'd have a unified 'Contact' model.

logger = logging.getLogger(__name__)

class CustomerResolutionEngine:
    def __init__(self, db: Session):
        self.db = db

    def resolve_customer(self, workspace_id: str, email: str, first_name: str = None, last_name: str = None) -> EcommerceCustomer:
        """
        Resolves or creates an EcommerceCustomer and attempts to link to CRM and Accounting.
        """
        # 1. Check if EcommerceCustomer exists
        customer = self.db.query(EcommerceCustomer).filter(
            EcommerceCustomer.workspace_id == workspace_id,
            EcommerceCustomer.email == email
        ).first()

        if not customer:
            customer = EcommerceCustomer(
                workspace_id=workspace_id,
                email=email,
                first_name=first_name,
                last_name=last_name
            )
            self.db.add(customer)
            self.db.flush() # Get ID
            logger.info(f"Created new EcommerceCustomer: {email}")

        # 2. Attempt Cross-System Linking if missing
        changed = False
        
        # Link to CRM (Lead/Contact)
        if not customer.crm_contact_id:
            lead = self.db.query(Lead).filter(
                Lead.workspace_id == workspace_id,
                Lead.email == email
            ).first()
            if lead:
                customer.crm_contact_id = lead.id
                changed = True
                logger.info(f"Linked EcommerceCustomer {email} to CRM Lead {lead.id}")

        # Link to Accounting (Entity)
        if not customer.accounting_entity_id:
            # Look for CUSTOMER entity with same email
            # We assume Entity metadata might store email or we match by name as fallback
            # For now, let's assume we match by exact name or similar signals if available
            # In Phase 12 we added Lead/Deal, Phase 10 we added Entity.
            
            # Simple heuristic: Match by first+last name if provided
            entity = self.db.query(Entity).filter(
                Entity.workspace_id == workspace_id,
                Entity.type == EntityType.CUSTOMER,
                Entity.name.ilike(f"{first_name} {last_name}")
            ).first()
            
            if entity:
                customer.accounting_entity_id = entity.id
                changed = True
                logger.info(f"Linked EcommerceCustomer {email} to Accounting Entity {entity.id}")

        if changed:
            self.db.commit()
            
        return customer

    def get_unified_identity(self, customer_id: str) -> dict:
        """Returns a unified view of the customer across systems."""
        customer = self.db.query(EcommerceCustomer).filter(EcommerceCustomer.id == customer_id).first()
        if not customer:
            return {}
            
        return {
            "ecommerce_id": customer.id,
            "external_id": customer.external_id,
            "email": customer.email,
            "crm_contact_id": customer.crm_contact_id,
            "accounting_entity_id": customer.accounting_entity_id,
            "name": f"{customer.first_name} {customer.last_name}"
        }
