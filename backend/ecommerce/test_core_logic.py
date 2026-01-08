import sys
import os
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from core.database import SessionLocal, engine
from core.models import Workspace
from ecommerce.models import EcommerceOrder, EcommerceCustomer, EcommerceOrderItem
from accounting.models import Account, AccountType, Transaction, JournalEntry, EntryType, Entity, EntityType
from sales.models import Lead
from core.identity_resolver import CustomerResolutionEngine
from ecommerce.ledger_mapper import OrderToLedgerMapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_ecommerce_flow():
    db = SessionLocal()
    unique_id = uuid.uuid4().hex[:8]
    workspace_id = f"test-ws-ecommerce-{unique_id}"
    
    try:
        # 1. Setup Environment
        print(f"--- Phase 1: Setting up Test Environment (WS: {workspace_id}) ---")
        ws = Workspace(id=workspace_id, name=f"Ecommerce Test {unique_id}")
        db.add(ws)
        db.commit() # MUST commit workspace first for FKs to work
        
        # Pre-seed a CRM Lead to test resolution
        test_email = f"customer_{unique_id}@example.com"
        lead = Lead(workspace_id=workspace_id, first_name="John", last_name="Doe", email=test_email)
        db.add(lead)
        
        # Pre-seed an Accounting Entity to test resolution
        entity = Entity(workspace_id=workspace_id, name="John Doe", type=EntityType.CUSTOMER)
        db.add(entity)
        db.commit()

        # 2. Simulate Order Arrival
        print(f"\n--- Phase 2: Simulating Shopify Order Arrival ---")
        customer = EcommerceCustomer(
            workspace_id=workspace_id,
            email=test_email,
            first_name="John",
            last_name="Doe",
            external_id=f"sh_cust_{unique_id}"
        )
        db.add(customer)
        db.flush()

        order = EcommerceOrder(
            workspace_id=workspace_id,
            customer_id=customer.id,
            external_id=f"sh_ord_{unique_id}",
            order_number="1001",
            total_price=120.0,
            subtotal_price=100.0,
            total_tax=10.0,
            total_shipping=10.0,
            currency="USD",
            status="paid"
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        # 3. Resolve Identity
        print(f"\n--- Phase 3: Resolving Identity ---")
        resolver = CustomerResolutionEngine(db)
        resolved_cust = resolver.resolve_customer(workspace_id, test_email, "John", "Doe")
        
        assert resolved_cust.crm_contact_id == lead.id
        assert resolved_cust.accounting_entity_id == entity.id
        print("✅ Identity Resolution Verified!")

        # 4. Map to Ledger
        print(f"\n--- Phase 4: Mapping to Ledger ---")
        mapper = OrderToLedgerMapper(db)
        tx_id = mapper.process_order(order.id)
        
        assert tx_id is not None
        
        # Verify Journal Entries
        tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
        entries = db.query(JournalEntry).filter(JournalEntry.transaction_id == tx_id).all()
        
        print(f"Transaction: {tx.description}, Amount: {tx.amount}")
        for je in entries:
            acc = db.query(Account).filter(Account.id == je.account_id).first()
            print(f"  Entry: {je.type} {je.amount} -> {acc.name} ({acc.type})")

        # Expectations:
        # DEBIT Bank 120.0
        # CREDIT Service Revenue 100.0
        # CREDIT Sales Tax Payable 10.0
        # CREDIT Shipping Income 10.0
        
        assert len(entries) == 4
        assert any(e.amount == 120.0 and e.type == EntryType.DEBIT for e in entries)
        assert any(e.amount == 100.0 and e.type == EntryType.CREDIT for e in entries)
        
        print("✅ Ledger Mapping Verified!")

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        import traceback
        traceback.print_exc()
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(verify_ecommerce_flow())
