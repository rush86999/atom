import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
import httpx

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from accounting.models import Account, Entity, EntityType, EntryType, JournalEntry, Transaction
from ecommerce.models import EcommerceCustomer, EcommerceOrder
from sales.models import Lead

from core.database import SessionLocal
from core.models import Workspace

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Backend URL for webhook simulation
BASE_URL = "http://localhost:8000" # Assuming backend is running or we test via FastAPI TestClient

async def verify_e2e_shopify_flow():
    db = SessionLocal()
    unique_id = uuid.uuid4().hex[:8]
    workspace_id = "default" # The webhook currently defaults to 'default'
    
    try:
        print(f"--- Phase 1: Environment Readiness ---")
        # Ensure 'default' workspace exists
        ws = db.query(Workspace).filter(Workspace.id == "default").first()
        if not ws:
            ws = Workspace(id="default", name="Default Workspace")
            db.add(ws)
            db.commit()

        # Pre-seed a CRM Lead
        test_email = f"shopify_hero_{unique_id}@example.com"
        lead = Lead(workspace_id=workspace_id, first_name="Shopify", last_name="Hero", email=test_email)
        db.add(lead)
        db.commit()

        # 2. Simulate Webhook
        print(f"\n--- Phase 2: Simulating Shopify Webhook (Order Created) ---")
        webhook_payload = {
            "id": int(unique_id, 16) % 10**8, # Unique integer ID
            "order_number": f"SHOP-{unique_id}",
            "total_price": "150.00",
            "subtotal_price": "120.00",
            "total_tax": "15.00",
            "total_shipping_line_price": "15.00",
            "currency": "USD",
            "financial_status": "paid",
            "customer": {
                "email": test_email,
                "first_name": "Shopify",
                "last_name": "Hero"
            },
            "line_items": [
                {
                    "title": "Magic Wand",
                    "price": "120.00",
                    "quantity": 1,
                    "sku": "WAND-001"
                }
            ]
        }

        # We'll use FastAPI's TestClient if we were inside a test, 
        # but here we'll simulate the call to the running backend.
        # Alternatively, we can call the router function directly.
        
        from fastapi import Request

        from integrations.shopify_webhooks import shopify_order_created

        # Mocking Request is hard, let's just use httpx if backend is running 
        # OR call the logic directly if we want a unit-test style.

        # For simplicity and reliability in this environment, let's trigger the logic 
        # by manually calling the parts that the webhook would call.
        
        print("Calling shopify_order_created logic...")
        # Since we want to test the ORCHESTRATOR too, we need the background tasks to run.
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{BASE_URL}/api/webhooks/shopify/order-created",
                    json=webhook_payload,
                    headers={"X-Shopify-Shop-Domain": "test-store.myshopify.com"}
                )
                if response.status_code == 200:
                    print(f"Webhook response: {response.json()}")
                else:
                    print(f"Webhook failed with status {response.status_code}: {response.text}")
                    # If it failed because server isn't running, we'll fallback to manual stimulus
            except Exception as e:
                print(f"Could not reach backend via HTTP: {e}. Falling back to manual stimulus.")
                # Manual stimulus if backend isn't up
                from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator

                # Create the order and trigger workflow manually
                # (This mimics what shopify_webhooks.py does)
                pass

        # 3. Wait for Background Workflow (Wait for Ledger Sync)
        print(f"\n--- Phase 3: Verifying Results ---")
        # Polling for ledger sync status
        max_retries = 10
        synced = False
        for i in range(max_retries):
            db.expire_all()
            order = db.query(EcommerceOrder).filter(EcommerceOrder.order_number == f"SHOP-{unique_id}").first()
            if order and order.is_ledger_synced:
                print(f"✅ Order {order.order_number} synced to ledger!")
                synced = True
                
                # Verify Identity Resolution
                customer = db.query(EcommerceCustomer).filter(EcommerceCustomer.id == order.customer_id).first()
                assert customer.crm_contact_id == lead.id
                print(f"✅ Identity Resolver linked customer to CRM Lead {lead.id}")
                
                # Verify Journal Entries
                entries = db.query(JournalEntry).filter(JournalEntry.transaction_id == order.ledger_transaction_id).all()
                assert len(entries) == 4
                assert any(e.amount == 150.0 and e.type == EntryType.DEBIT for e in entries)
                print(f"✅ Ledger entries validated (Bank Debit: 150.0)")
                break
            
            print(f"Waiting for sync... ({i+1}/{max_retries})")
            await asyncio.sleep(1)

        if not synced:
            print("❌ Timeout waiting for ledger sync. Check backend logs.")
            # Let's check if the order even exists
            order = db.query(EcommerceOrder).filter(EcommerceOrder.order_number == f"SHOP-{unique_id}").first()
            if order:
                print(f"Order exists but not synced. Status: {order.status}, Ledger Synced: {order.is_ledger_synced}")
            else:
                print("Order was never created via webhook.")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(verify_e2e_shopify_flow())
