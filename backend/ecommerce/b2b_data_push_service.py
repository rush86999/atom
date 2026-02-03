"""
B2B Data Push Service
Orchestrates the synchronization of B2B data (customers, draft orders) to external integrations like HubSpot and QuickBooks.
"""

import logging
from typing import Any, Dict, Optional
from ecommerce.models import EcommerceCustomer, EcommerceOrder, EcommerceOrderItem
from sqlalchemy.orm import Session

from integrations.atom_quickbooks_integration_service import AtomQuickBooksIntegrationService
from integrations.hubspot_service import hubspot_service

logger = logging.getLogger(__name__)

class B2BDataPushService:
    def __init__(self, db: Session):
        self.db = db
        # QuickBooks config would normally come from some settings/env
        self.qbo = AtomQuickBooksIntegrationService({
            "database": db,
            "quickbooks_client_id": "MOCK", # Use actual from env if available
            "quickbooks_client_secret": "MOCK",
            "quickbooks_company_id": "MOCK",
        })

    async def push_b2b_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Push a B2B customer profile to external CRM and Accounting integrations.
        """
        customer = self.db.query(EcommerceCustomer).filter(EcommerceCustomer.id == customer_id).first()
        if not customer:
            return {"error": "Customer not found"}

        results = {"hubspot": None, "quickbooks": None}

        # 1. Push to HubSpot (Company)
        try:
            company_name = f"{customer.first_name} {customer.last_name}" or customer.email
            domain = customer.email.split('@')[-1] if '@' in customer.email else None
            
            hs_company = await hubspot_service.create_company(name=company_name, domain=domain)
            results["hubspot"] = hs_company.get("id")
            customer.crm_contact_id = hs_company.get("id") # Store as reference
            logger.info(f"Pushed B2B customer {customer_id} to HubSpot: {results['hubspot']}")
        except Exception as e:
            logger.error(f"Failed to push to HubSpot: {e}")
            results["hubspot_error"] = str(e)

        # 2. Push to QuickBooks (Customer)
        try:
            display_name = f"{customer.first_name} {customer.last_name}" or customer.email
            qbo_res = await self.qbo.create_customer(display_name=display_name, email=customer.email)
            if qbo_res["success"]:
                results["quickbooks"] = qbo_res["customer_id"]
                customer.accounting_entity_id = qbo_res["customer_id"]
                logger.info(f"Pushed B2B customer {customer_id} to QuickBooks: {results['quickbooks']}")
            else:
                results["quickbooks_error"] = qbo_res.get("error")
        except Exception as e:
            logger.error(f"Failed to push to QuickBooks: {e}")
            results["quickbooks_error"] = str(e)

        self.db.commit()
        return results

    async def push_draft_order(self, order_id: str) -> Dict[str, Any]:
        """
        Push a B2B draft order to HubSpot (as Deal) and QuickBooks (as Invoice/Draft).
        """
        order = self.db.query(EcommerceOrder).filter(EcommerceOrder.id == order_id).first()
        if not order:
            return {"error": "Order not found"}

        customer = order.customer
        results = {"hubspot_deal": None, "quickbooks_invoice": None}

        # 1. Push to HubSpot as a Deal
        try:
            company_id = customer.crm_contact_id # HubSpot company ID stored in customer
            deal_name = f"B2B Order {order.order_number}"
            
            hs_deal = await hubspot_service.create_deal(
                name=deal_name, 
                amount=order.total_price, 
                company_id=company_id
            )
            results["hubspot_deal"] = hs_deal.get("id")
            logger.info(f"Pushed draft order {order_id} to HubSpot Deal: {results['hubspot_deal']}")
        except Exception as e:
            logger.error(f"Failed to push order to HubSpot Deal: {e}")
            results["hubspot_deal_error"] = str(e)

        # 2. Push to QuickBooks as an Invoice (Draft/Pending)
        try:
            line_items = []
            for item in order.items:
                line_items.append({
                    "Amount": item.price * item.quantity,
                    "Description": item.title,
                    "DetailType": "SalesItemLineDetail",
                    "SalesItemLineDetail": {
                        "ItemRef": {"value": item.product_id or "1"}, # Default item ref
                        "Qty": item.quantity,
                        "UnitPrice": item.price
                    }
                })

            invoice_data = {
                "customer_id": customer.accounting_entity_id,
                "amount": order.total_price,
                "line_items": line_items,
                "notes": f"Generated from B2B Draft {order.order_number}"
            }
            
            qbo_res = await self.qbo.create_invoice(invoice_data)
            if qbo_res["success"]:
                results["quickbooks_invoice"] = qbo_res["invoice_id"]
                order.ledger_transaction_id = qbo_res["invoice_id"]
                logger.info(f"Pushed draft order {order_id} to QuickBooks Invoice: {results['quickbooks_invoice']}")
            else:
                results["quickbooks_error"] = qbo_res.get("error")
        except Exception as e:
            logger.error(f"Failed to push order to QuickBooks: {e}")
            results["quickbooks_error"] = str(e)

        self.db.commit()
        return results
