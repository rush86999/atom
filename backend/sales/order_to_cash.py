import logging
from sqlalchemy.orm import Session
from typing import Dict, Any
from sales.models import Deal, DealStage
from integrations.zoho_books_service import ZohoBooksService
from core.automation_settings import get_automation_settings

logger = logging.getLogger(__name__)

class OrderToCashService:
    """
    Bridges Sales and Accounting (Order-to-Cash automation).
    """
    def __init__(self, db: Session):
        self.db = db
        self.zoho_books = ZohoBooksService()
        self.settings = get_automation_settings()

    async def handle_deal_closed_won(self, workspace_id: str, deal_id: str, credentials: Dict[str, Any]):
        """
        Triggered when a deal is CLOSED_WON.
        Creates customer and invoice in the accounting system.
        """
        if not self.settings.is_sales_enabled() or not self.settings.is_accounting_enabled():
            logger.info("Sales or Accounting automations disabled. Skipping Order-to-Cash.")
            return

        deal = self.db.query(Deal).filter(Deal.id == deal_id).first()
        if not deal:
            logger.error(f"Deal {deal_id} not found for Order-to-Cash.")
            return

        logger.info(f"🚀 Processing Order-to-Cash for won deal: {deal.name}")

        # 1. Create Contact in Zoho Books (Mock/Simplified)
        contact_data = {
            "contact_name": deal.metadata_json.get("company_name", deal.name),
            "contact_type": "customer",
            "currency_code": deal.currency or "USD"
        }
        
        try:
            # Note: In production, access_token/org_id would come from saved workspace credentials
            # For this automation, we assume credentials are passed or available.
            contact = await self.zoho_books.create_contact(
                credentials["access_token"],
                credentials["organization_id"],
                contact_data
            )
            logger.info(f"✅ Created customer in Zoho Books: {contact.get('contact_name')}")

            # 2. Create Invoice
            invoice_data = {
                "customer_id": contact.get("contact_id"),
                "line_items": [
                    {
                        "name": deal.name,
                        "rate": deal.value,
                        "quantity": 1
                    }
                ],
                "reason": "Automated invoice from WON deal in CRM"
            }
            
            invoice = await self.zoho_books.create_invoice(
                credentials["access_token"],
                credentials["organization_id"],
                invoice_data
            )
            logger.info(f"✅ Created invoice in Zoho Books: {invoice.get('invoice_number')}")

            # 3. Update Deal metadata with accounting links
            deal.metadata_json["zoho_invoice_id"] = invoice.get("invoice_id")
            deal.metadata_json["zoho_customer_id"] = contact.get("contact_id")
            self.db.commit()

        except Exception as e:
            logger.error(f"❌ Order-to-Cash failed for deal {deal_id}: {e}")
