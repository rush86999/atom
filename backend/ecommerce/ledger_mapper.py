import logging
from datetime import datetime, timezone
from typing import Optional
from accounting.models import Account, AccountType, EntryType, JournalEntry, Transaction
from ecommerce.models import EcommerceOrder
from sqlalchemy.orm import Session

from core.identity_resolver import CustomerResolutionEngine

logger = logging.getLogger(__name__)

class OrderToLedgerMapper:
    def __init__(self, db: Session):
        self.db = db
        self.resolver = CustomerResolutionEngine(db)

    def process_order(self, order_id: str) -> Optional[str]:
        """
        Takes an EcommerceOrder and creates appropriate accounting entries.
        Returns the ID of the created Transaction.
        """
        order = self.db.query(EcommerceOrder).filter(EcommerceOrder.id == order_id).first()
        if not order:
            logger.error(f"Order {order_id} not found for ledger mapping")
            return None

        if order.is_ledger_synced:
            logger.info(f"Order {order_id} already synced to ledger")
            return order.ledger_transaction_id

        # 1. Resolve Identity to get Accounting Entity
        customer = self.resolver.resolve_customer(
            order.workspace_id, 
            order.customer.email, 
            order.customer.first_name, 
            order.customer.last_name
        )
        
        # 2. Find/Prepare Accounts
        # In a real system, these would be configured per workspace.
        # We'll use defaults or find by type.
        
        cash_account = self._get_account(order.workspace_id, AccountType.ASSET, "Bank")
        revenue_account = self._get_account(order.workspace_id, AccountType.REVENUE, "Service Revenue")
        tax_account = self._get_account(order.workspace_id, AccountType.LIABILITY, "Sales Tax Payable")
        shipping_account = self._get_account(order.workspace_id, AccountType.REVENUE, "Shipping Income")

        # 3. Create Aggregate Transaction
        tx = Transaction(
            workspace_id=order.workspace_id,
            transaction_date=order.created_at or datetime.now(timezone.utc),
            description=f"Shopify Order #{order.order_number}",
            amount=order.total_price,
            source="ecommerce"
        )
        self.db.add(tx)
        self.db.flush()

        # 4. Create Journal Entries (Double Entry)
        # DEBIT Cash (Asset)
        self.db.add(JournalEntry(
            transaction_id=tx.id,
            account_id=cash_account.id,
            type=EntryType.DEBIT,
            amount=order.total_price
        ))

        # CREDIT Revenue
        if order.subtotal_price > 0:
            self.db.add(JournalEntry(
                transaction_id=tx.id,
                account_id=revenue_account.id,
                type=EntryType.CREDIT,
                amount=order.subtotal_price
            ))

        # CREDIT Tax Liability
        if order.total_tax > 0:
            self.db.add(JournalEntry(
                transaction_id=tx.id,
                account_id=tax_account.id,
                type=EntryType.CREDIT,
                amount=order.total_tax
            ))

        # CREDIT Shipping Income
        if order.total_shipping > 0:
            self.db.add(JournalEntry(
                transaction_id=tx.id,
                account_id=shipping_account.id,
                type=EntryType.CREDIT,
                amount=order.total_shipping
            ))

        # 5. Link back to Order
        order.ledger_transaction_id = tx.id
        order.is_ledger_synced = True
        
        self.db.commit()
        logger.info(f"Successfully synced Order {order_id} to Ledger Transaction {tx.id}")
        return tx.id

    def _get_account(self, workspace_id: str, account_type: AccountType, default_name: str) -> Account:
        """Helper to find or create a default account for a given type and name."""
        account = self.db.query(Account).filter(
            Account.workspace_id == workspace_id,
            Account.type == account_type,
            Account.name == default_name
        ).first()
        
        if not account:
            # Fallback to any account of that type if name match fails
            account = self.db.query(Account).filter(
                Account.workspace_id == workspace_id,
                Account.type == account_type
            ).first()

        if not account:
            account = Account(
                workspace_id=workspace_id,
                name=default_name,
                type=account_type,
                code=f"{account_type.value[:1]}000-AUTO"
            )
            self.db.add(account)
            self.db.flush()
            logger.info(f"Created default {account_type} account: {default_name}")
            
        return account
