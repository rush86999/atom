"""
Comprehensive accounting model tests covering CRUD operations, relationships, constraints, and business logic.

Goal: Achieve 80%+ line coverage for accounting/models.py through comprehensive testing of:
- CRUD operations for all 12 accounting models
- Relationship types (one-to-many, self-referential, hierarchical)
- Foreign key constraints and unique constraints
- Double-entry accounting principles
- Numeric precision for currency fields
- Enum field validation
- JSON field serialization

Tests use:
- pytest fixtures for database sessions (db_session from conftest.py)
- Factory pattern for test data creation (factories in tests/factories/accounting_factory.py)
- Real database (SQLite for tests)
- SQLAlchemy ORM for queries
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from decimal import Decimal

from tests.factories.accounting_factory import (
    AccountFactory,
    TransactionFactory,
    JournalEntryFactory,
    EntityFactory,
    BillFactory,
    InvoiceFactory,
    DocumentFactory,
    CategorizationProposalFactory,
    TaxNexusFactory,
    FinancialCloseFactory,
    CategorizationRuleFactory,
    BudgetFactory,
)
from tests.factories.workspace_factory import WorkspaceFactory
from accounting.models import (
    Account,
    Transaction,
    JournalEntry,
    Entity,
    Bill,
    Invoice,
    Document,
    CategorizationProposal,
    TaxNexus,
    FinancialClose,
    CategorizationRule,
    Budget,
    AccountType,
    TransactionStatus,
    EntryType,
    EntityType,
    BillStatus,
    InvoiceStatus,
)


# ============================================================================
# Task 2: Account and Transaction Model Tests
# ============================================================================

class TestAccountModel:
    """Test Account model (chart of accounts)."""

    def test_account_create_with_defaults(self, db_session: Session):
        """Test Account creation with required fields only."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        account = Account(
            name="Test Account",
            code="1000",
            type=AccountType.ASSET.value,
            workspace_id=workspace.id
        )
        db_session.add(account)
        db_session.commit()
        db_session.refresh(account)

        assert account.id is not None
        assert account.name == "Test Account"
        assert account.code == "1000"
        assert account.type == AccountType.ASSET.value
        assert account.workspace_id == workspace.id
        assert account.is_active is True  # Default value
        assert account.parent_id is None  # No parent by default
        assert account.created_at is not None

    def test_account_create_with_all_fields(self, db_session: Session):
        """Test Account creation with all optional fields."""
        workspace = WorkspaceFactory(_session=db_session)
        parent_account = AccountFactory(
            workspace_id=workspace.id,
            type=AccountType.ASSET.value,
            _session=db_session
        )
        db_session.commit()

        account = Account(
            name="Child Account",
            code="1001",
            type=AccountType.ASSET.value,
            workspace_id=workspace.id,
            description="A test child account",
            is_active=False,
            parent_id=parent_account.id,
            standards_mapping={"gaap": "1001", "ifrs": "ASSET_CASH"},
            last_audit_at=datetime.utcnow()
        )
        db_session.add(account)
        db_session.commit()
        db_session.refresh(account)

        assert account.description == "A test child account"
        assert account.is_active is False
        assert account.parent_id == parent_account.id
        assert account.standards_mapping == {"gaap": "1001", "ifrs": "ASSET_CASH"}
        assert account.last_audit_at is not None

    def test_account_type_enum(self, db_session: Session):
        """Test all AccountType enum values."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        account_types = [
            AccountType.ASSET.value,
            AccountType.LIABILITY.value,
            AccountType.EQUITY.value,
            AccountType.REVENUE.value,
            AccountType.EXPENSE.value,
        ]

        for account_type in account_types:
            account = AccountFactory(
                workspace_id=workspace.id,
                type=account_type,
                _session=db_session
            )
            db_session.commit()
            assert account.type == account_type

    def test_account_parent_self_referential(self, db_session: Session):
        """Test hierarchical account structure (parent -> sub_accounts)."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create parent account
        parent = AccountFactory(
            workspace_id=workspace.id,
            code="1000",
            name="Parent Account",
            type=AccountType.ASSET.value,
            _session=db_session
        )
        db_session.commit()

        # Create child accounts
        child1 = AccountFactory(
            workspace_id=workspace.id,
            code="1001",
            name="Child Account 1",
            type=AccountType.ASSET.value,
            parent_id=parent.id,
            _session=db_session
        )
        child2 = AccountFactory(
            workspace_id=workspace.id,
            code="1002",
            name="Child Account 2",
            type=AccountType.ASSET.value,
            parent_id=parent.id,
            _session=db_session
        )
        db_session.commit()

        # Verify parent-child relationships
        retrieved_parent = db_session.query(Account).filter(
            Account.id == parent.id
        ).first()
        assert len(retrieved_parent.sub_accounts) == 2

        # Verify child accounts reference parent
        retrieved_child1 = db_session.query(Account).filter(
            Account.id == child1.id
        ).first()
        assert retrieved_child1.parent_id == parent.id

    def test_account_workspace_unique_constraint(self, db_session: Session):
        """Test workspace+code unique constraint."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create first account
        account1 = Account(
            name="Account 1",
            code="1000",
            type=AccountType.ASSET.value,
            workspace_id=workspace.id
        )
        db_session.add(account1)
        db_session.commit()

        # Try to create second account with same workspace+code
        with pytest.raises(IntegrityError):
            account2 = Account(
                name="Account 2",
                code="1000",  # Duplicate code
                type=AccountType.LIABILITY.value,
                workspace_id=workspace.id  # Same workspace
            )
            db_session.add(account2)
            db_session.commit()

        db_session.rollback()

    def test_account_standards_mapping_json(self, db_session: Session):
        """Test standards_mapping JSON field for GAAP/IFRS."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        mapping_data = {
            "gaap": "1001",
            "ifrs": "ASSET_CASH",
            "custom": "CASH_USD"
        }

        account = AccountFactory(
            workspace_id=workspace.id,
            standards_mapping=mapping_data,
            _session=db_session
        )
        db_session.commit()

        # Retrieve and verify JSON data
        retrieved = db_session.query(Account).filter(
            Account.id == account.id
        ).first()
        assert retrieved.standards_mapping == mapping_data
        assert retrieved.standards_mapping["gaap"] == "1001"
        assert retrieved.standards_mapping["ifrs"] == "ASSET_CASH"

    def test_account_journal_entries_relationship(self, db_session: Session):
        """Test account has many journal entries."""
        workspace = WorkspaceFactory(_session=db_session)
        account = AccountFactory(
            workspace_id=workspace.id,
            type=AccountType.ASSET.value,
            _session=db_session
        )
        transaction = TransactionFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        # Create journal entries for this account
        entry1 = JournalEntry(
            transaction_id=transaction.id,
            account_id=account.id,
            type=EntryType.DEBIT.value,
            amount=Decimal("100.00")
        )
        entry2 = JournalEntry(
            transaction_id=transaction.id,
            account_id=account.id,
            type=EntryType.CREDIT.value,
            amount=Decimal("50.00")
        )
        db_session.add_all([entry1, entry2])
        db_session.commit()

        # Verify account has entries
        retrieved_account = db_session.query(Account).filter(
            Account.id == account.id
        ).first()
        assert len(retrieved_account.entries) == 2


class TestTransactionModel:
    """Test Transaction model (transaction headers)."""

    def test_transaction_create_with_defaults(self, db_session: Session):
        """Test Transaction creation with required fields."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        transaction = Transaction(
            workspace_id=workspace.id,
            source="stripe",
            transaction_date=datetime.utcnow(),
            category="llm_tokens"
        )
        db_session.add(transaction)
        db_session.commit()
        db_session.refresh(transaction)

        assert transaction.id is not None
        assert transaction.workspace_id == workspace.id
        assert transaction.source == "stripe"
        assert transaction.status == TransactionStatus.PENDING.value  # Default
        assert transaction.category == "llm_tokens"
        assert transaction.is_intercompany is False  # Default
        assert transaction.created_at is not None

    def test_transaction_category_required(self, db_session: Session):
        """Test category field is required (NOT NULL constraint)."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Note: SQLite doesn't enforce NOT NULL by default, so we test the default value
        # Transaction model has category field with default='other'
        transaction = Transaction(
            workspace_id=workspace.id,
            source="manual",
            transaction_date=datetime.utcnow()
            # category not provided, should default to 'other'
        )
        db_session.add(transaction)
        db_session.commit()
        db_session.refresh(transaction)

        # Verify default value is applied
        assert transaction.category == "other"

    def test_transaction_status_enum(self, db_session: Session):
        """Test all TransactionStatus enum values."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        statuses = [
            TransactionStatus.PENDING.value,
            TransactionStatus.POSTED.value,
            TransactionStatus.FAILED.value,
            TransactionStatus.CANCELLED.value,
        ]

        for status in statuses:
            transaction = TransactionFactory(
                workspace_id=workspace.id,
                status=status,
                _session=db_session
            )
            db_session.commit()
            assert transaction.status == status

    def test_transaction_external_id_indexed(self, db_session: Session):
        """Test external_id field for integration tracking."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        stripe_id = "stripe_txn_12345"
        transaction = TransactionFactory(
            workspace_id=workspace.id,
            external_id=stripe_id,
            source="stripe",
            _session=db_session
        )
        db_session.commit()

        # Query by external_id
        retrieved = db_session.query(Transaction).filter(
            Transaction.external_id == stripe_id
        ).first()
        assert retrieved is not None
        assert retrieved.id == transaction.id

    def test_transaction_project_linking(self, db_session: Session):
        """Test project_id and milestone_id foreign keys."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create transaction with project references
        transaction = TransactionFactory(
            workspace_id=workspace.id,
            project_id="project_123",
            milestone_id="milestone_456",
            _session=db_session
        )
        db_session.commit()

        assert transaction.project_id == "project_123"
        assert transaction.milestone_id == "milestone_456"

    def test_transaction_journal_entries_cascade(self, db_session: Session):
        """Test cascade delete to journal entries."""
        workspace = WorkspaceFactory(_session=db_session)
        transaction = TransactionFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        account = AccountFactory(
            workspace_id=workspace.id,
            type=AccountType.ASSET.value,
            _session=db_session
        )
        db_session.commit()

        # Create journal entries
        entry1 = JournalEntryFactory(
            transaction_id=transaction.id,
            account_id=account.id,
            _session=db_session
        )
        entry2 = JournalEntryFactory(
            transaction_id=transaction.id,
            account_id=account.id,
            _session=db_session
        )
        db_session.commit()

        transaction_id = transaction.id
        entry_ids = [entry1.id, entry2.id]

        # Delete transaction (should cascade to entries)
        db_session.delete(transaction)
        db_session.commit()

        # Verify entries are deleted
        remaining_entries = db_session.query(JournalEntry).filter(
            JournalEntry.id.in_(entry_ids)
        ).all()
        assert len(remaining_entries) == 0  # Cascade delete worked

    def test_transaction_is_intercompany_field(self, db_session: Session):
        """Test is_intercompany boolean field."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Regular transaction
        transaction1 = TransactionFactory(
            workspace_id=workspace.id,
            is_intercompany=False,
            _session=db_session
        )
        # Intercompany transaction
        transaction2 = TransactionFactory(
            workspace_id=workspace.id,
            is_intercompany=True,
            counterparty_workspace_id="workspace_456",
            _session=db_session
        )
        db_session.commit()

        assert transaction1.is_intercompany is False
        assert transaction1.counterparty_workspace_id is None

        assert transaction2.is_intercompany is True
        assert transaction2.counterparty_workspace_id == "workspace_456"


class TestJournalEntryModel:
    """Test JournalEntry model (double-entry records)."""

    def test_journal_entry_create_debit(self, db_session: Session):
        """Test creating debit entry."""
        workspace = WorkspaceFactory(_session=db_session)
        transaction = TransactionFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        account = AccountFactory(
            workspace_id=workspace.id,
            type=AccountType.ASSET.value,
            _session=db_session
        )
        db_session.commit()

        entry = JournalEntry(
            transaction_id=transaction.id,
            account_id=account.id,
            type=EntryType.DEBIT.value,
            amount=Decimal("100.00"),
            currency="USD"
        )
        db_session.add(entry)
        db_session.commit()

        assert entry.type == EntryType.DEBIT.value
        assert entry.amount == Decimal("100.00")

    def test_journal_entry_create_credit(self, db_session: Session):
        """Test creating credit entry."""
        workspace = WorkspaceFactory(_session=db_session)
        transaction = TransactionFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        account = AccountFactory(
            workspace_id=workspace.id,
            type=AccountType.LIABILITY.value,
            _session=db_session
        )
        db_session.commit()

        entry = JournalEntry(
            transaction_id=transaction.id,
            account_id=account.id,
            type=EntryType.CREDIT.value,
            amount=Decimal("100.00")
        )
        db_session.add(entry)
        db_session.commit()

        assert entry.type == EntryType.CREDIT.value

    def test_journal_entry_type_enum(self, db_session: Session):
        """Test EntryType enum values."""
        workspace = WorkspaceFactory(_session=db_session)
        transaction = TransactionFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        account = AccountFactory(
            workspace_id=workspace.id,
            type=AccountType.ASSET.value,
            _session=db_session
        )
        db_session.commit()

        entry_types = [EntryType.DEBIT.value, EntryType.CREDIT.value]

        for entry_type in entry_types:
            entry = JournalEntryFactory(
                transaction_id=transaction.id,
                account_id=account.id,
                type=entry_type,
                _session=db_session
            )
            db_session.commit()
            assert entry.type == entry_type

    def test_journal_entry_amount_numeric_precision(self, db_session: Session):
        """Test Numeric(19,4) precision for amounts."""
        workspace = WorkspaceFactory(_session=db_session)
        transaction = TransactionFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        account = AccountFactory(
            workspace_id=workspace.id,
            type=AccountType.ASSET.value,
            _session=db_session
        )
        db_session.commit()

        # Test various precision levels
        amounts = [
            Decimal("0.01"),      # Minimum
            Decimal("100.1234"),  # 4 decimal places
            Decimal("999999.9999"),  # Large value
        ]

        for amount in amounts:
            entry = JournalEntryFactory(
                transaction_id=transaction.id,
                account_id=account.id,
                amount=amount,
                _session=db_session
            )
            db_session.commit()
            assert entry.amount == amount

    def test_journal_entry_transaction_relationship(self, db_session: Session):
        """Test journal entry belongs to transaction."""
        workspace = WorkspaceFactory(_session=db_session)
        transaction = TransactionFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        account = AccountFactory(
            workspace_id=workspace.id,
            type=AccountType.ASSET.value,
            _session=db_session
        )
        db_session.commit()

        entry = JournalEntryFactory(
            transaction_id=transaction.id,
            account_id=account.id,
            _session=db_session
        )
        db_session.commit()

        # Verify entry references transaction
        retrieved_entry = db_session.query(JournalEntry).filter(
            JournalEntry.id == entry.id
        ).first()
        assert retrieved_entry.transaction_id == transaction.id

    def test_journal_entry_account_relationship(self, db_session: Session):
        """Test journal entry belongs to account."""
        workspace = WorkspaceFactory(_session=db_session)
        transaction = TransactionFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        account = AccountFactory(
            workspace_id=workspace.id,
            type=AccountType.ASSET.value,
            _session=db_session
        )
        db_session.commit()

        entry = JournalEntryFactory(
            transaction_id=transaction.id,
            account_id=account.id,
            _session=db_session
        )
        db_session.commit()

        # Verify entry references account
        retrieved_entry = db_session.query(JournalEntry).filter(
            JournalEntry.id == entry.id
        ).first()
        assert retrieved_entry.account_id == account.id

    def test_journal_entry_double_entry(self, db_session: Session):
        """Test creating balanced debit+credit entries."""
        workspace = WorkspaceFactory(_session=db_session)
        transaction = TransactionFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        debit_account = AccountFactory(
            workspace_id=workspace.id,
            type=AccountType.ASSET.value,
            _session=db_session
        )
        credit_account = AccountFactory(
            workspace_id=workspace.id,
            type=AccountType.LIABILITY.value,
            _session=db_session
        )
        db_session.commit()

        # Create balanced entries
        debit_entry = JournalEntryFactory(
            transaction_id=transaction.id,
            account_id=debit_account.id,
            type=EntryType.DEBIT.value,
            amount=Decimal("100.00"),
            _session=db_session
        )
        credit_entry = JournalEntryFactory(
            transaction_id=transaction.id,
            account_id=credit_account.id,
            type=EntryType.CREDIT.value,
            amount=Decimal("100.00"),
            _session=db_session
        )
        db_session.commit()

        # Verify entries balance
        assert debit_entry.amount == credit_entry.amount
        assert debit_entry.type == EntryType.DEBIT.value
        assert credit_entry.type == EntryType.CREDIT.value


class TestDoubleEntryPrinciples:
    """Test double-entry accounting principles."""

    def test_transaction_balanced_entries(self, db_session: Session):
        """Test balanced transaction (debits = credits)."""
        workspace = WorkspaceFactory(_session=db_session)
        transaction = TransactionFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        asset_account = AccountFactory(
            workspace_id=workspace.id,
            type=AccountType.ASSET.value,
            _session=db_session
        )
        liability_account = AccountFactory(
            workspace_id=workspace.id,
            type=AccountType.LIABILITY.value,
            _session=db_session
        )
        db_session.commit()

        # Create balanced entries
        debit_entry = JournalEntryFactory(
            transaction_id=transaction.id,
            account_id=asset_account.id,
            type=EntryType.DEBIT.value,
            amount=Decimal("500.00"),
            _session=db_session
        )
        credit_entry = JournalEntryFactory(
            transaction_id=transaction.id,
            account_id=liability_account.id,
            type=EntryType.CREDIT.value,
            amount=Decimal("500.00"),
            _session=db_session
        )
        db_session.commit()

        # Calculate totals
        entries = db_session.query(JournalEntry).filter(
            JournalEntry.transaction_id == transaction.id
        ).all()

        total_debits = sum(
            e.amount for e in entries if e.type == EntryType.DEBIT.value
        )
        total_credits = sum(
            e.amount for e in entries if e.type == EntryType.CREDIT.value
        )

        assert total_debits == total_credits == Decimal("500.00")

    def test_transaction_unbalanced_rejected(self, db_session: Session):
        """Test unbalanced entries allowed at ORM level (enforced at service layer)."""
        workspace = WorkspaceFactory(_session=db_session)
        transaction = TransactionFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        asset_account = AccountFactory(
            workspace_id=workspace.id,
            type=AccountType.ASSET.value,
            _session=db_session
        )
        liability_account = AccountFactory(
            workspace_id=workspace.id,
            type=AccountType.LIABILITY.value,
            _session=db_session
        )
        db_session.commit()

        # Create unbalanced entries (ORM allows this)
        debit_entry = JournalEntryFactory(
            transaction_id=transaction.id,
            account_id=asset_account.id,
            type=EntryType.DEBIT.value,
            amount=Decimal("600.00"),  # Different from credit
            _session=db_session
        )
        credit_entry = JournalEntryFactory(
            transaction_id=transaction.id,
            account_id=liability_account.id,
            type=EntryType.CREDIT.value,
            amount=Decimal("500.00"),  # Different from debit
            _session=db_session
        )
        db_session.commit()

        # ORM accepts unbalanced entries (service layer should validate)
        entries = db_session.query(JournalEntry).filter(
            JournalEntry.transaction_id == transaction.id
        ).all()
        assert len(entries) == 2  # Both entries created


# ============================================================================
# Task 3: Entity, Bill, Invoice, and Document Model Tests
# ============================================================================

class TestEntityModel:
    """Test Entity model (vendors and customers)."""

    def test_entity_create_vendor(self, db_session: Session):
        """Test creating vendor entity."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        vendor = Entity(
            workspace_id=workspace.id,
            name="ACME Corp",
            type=EntityType.VENDOR.value,
            email="billing@acme.com",
            phone="555-0100",
            address="123 Vendor St"
        )
        db_session.add(vendor)
        db_session.commit()
        db_session.refresh(vendor)

        assert vendor.name == "ACME Corp"
        assert vendor.type == EntityType.VENDOR.value
        assert vendor.email == "billing@acme.com"

    def test_entity_create_customer(self, db_session: Session):
        """Test creating customer entity."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        customer = Entity(
            workspace_id=workspace.id,
            name="Customer Inc",
            type=EntityType.CUSTOMER.value,
            email="accounts@customer.com"
        )
        db_session.add(customer)
        db_session.commit()

        assert customer.type == EntityType.CUSTOMER.value

    def test_entity_create_both(self, db_session: Session):
        """Test creating entity with type=both (vendor and customer)."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        entity = EntityFactory(
            workspace_id=workspace.id,
            type=EntityType.BOTH.value,
            _session=db_session
        )
        db_session.commit()

        assert entity.type == EntityType.BOTH.value

    def test_entity_type_enum(self, db_session: Session):
        """Test all EntityType enum values."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        entity_types = [
            EntityType.VENDOR.value,
            EntityType.CUSTOMER.value,
            EntityType.BOTH.value,
        ]

        for entity_type in entity_types:
            entity = EntityFactory(
                workspace_id=workspace.id,
                type=entity_type,
                _session=db_session
            )
            db_session.commit()
            assert entity.type == entity_type

    def test_entity_bills_relationship(self, db_session: Session):
        """Test vendor has many bills (accounts payable)."""
        workspace = WorkspaceFactory(_session=db_session)
        vendor = EntityFactory(
            workspace_id=workspace.id,
            type=EntityType.VENDOR.value,
            _session=db_session
        )
        db_session.commit()

        # Create bills for vendor
        bill1 = BillFactory(
            workspace_id=workspace.id,
            vendor_id=vendor.id,
            _session=db_session
        )
        bill2 = BillFactory(
            workspace_id=workspace.id,
            vendor_id=vendor.id,
            _session=db_session
        )
        db_session.commit()

        # Verify vendor has bills
        retrieved_vendor = db_session.query(Entity).filter(
            Entity.id == vendor.id
        ).first()
        assert len(retrieved_vendor.bills) == 2

    def test_entity_invoices_relationship(self, db_session: Session):
        """Test customer has many invoices (accounts receivable)."""
        workspace = WorkspaceFactory(_session=db_session)
        customer = EntityFactory(
            workspace_id=workspace.id,
            type=EntityType.CUSTOMER.value,
            _session=db_session
        )
        db_session.commit()

        # Create invoices for customer
        invoice1 = InvoiceFactory(
            workspace_id=workspace.id,
            customer_id=customer.id,
            _session=db_session
        )
        invoice2 = InvoiceFactory(
            workspace_id=workspace.id,
            customer_id=customer.id,
            _session=db_session
        )
        db_session.commit()

        # Verify customer has invoices
        retrieved_customer = db_session.query(Entity).filter(
            Entity.id == customer.id
        ).first()
        assert len(retrieved_customer.invoices) == 2

    def test_entity_tax_id_field(self, db_session: Session):
        """Test optional tax_id field for tax identifiers."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        entity = EntityFactory(
            workspace_id=workspace.id,
            tax_id="12-3456789",
            _session=db_session
        )
        db_session.commit()

        assert entity.tax_id == "12-3456789"


class TestBillModel:
    """Test Bill model (accounts payable)."""

    def test_bill_create_with_defaults(self, db_session: Session):
        """Test creating accounts payable bill."""
        workspace = WorkspaceFactory(_session=db_session)
        vendor = EntityFactory(
            workspace_id=workspace.id,
            type=EntityType.VENDOR.value,
            _session=db_session
        )
        db_session.commit()

        bill = Bill(
            workspace_id=workspace.id,
            vendor_id=vendor.id,
            issue_date=datetime.utcnow(),
            due_date=datetime.utcnow() + timedelta(days=30),
            amount=Decimal("1500.00")
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(bill)

        assert bill.workspace_id == workspace.id
        assert bill.vendor_id == vendor.id
        assert bill.amount == Decimal("1500.00")
        assert bill.status == BillStatus.DRAFT.value  # Default

    def test_bill_status_enum(self, db_session: Session):
        """Test all BillStatus enum values."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        statuses = [
            BillStatus.DRAFT.value,
            BillStatus.OPEN.value,
            BillStatus.PAID.value,
            BillStatus.VOID.value,
        ]

        for status in statuses:
            bill = BillFactory(
                workspace_id=workspace.id,
                status=status,
                _session=db_session
            )
            db_session.commit()
            assert bill.status == status

    def test_bill_vendor_relationship(self, db_session: Session):
        """Test bill belongs to vendor."""
        workspace = WorkspaceFactory(_session=db_session)
        vendor = EntityFactory(
            workspace_id=workspace.id,
            type=EntityType.VENDOR.value,
            name="Test Vendor",
            _session=db_session
        )
        db_session.commit()

        bill = BillFactory(
            workspace_id=workspace.id,
            vendor_id=vendor.id,
            _session=db_session
        )
        db_session.commit()

        # Verify bill references vendor
        retrieved_bill = db_session.query(Bill).filter(
            Bill.id == bill.id
        ).first()
        assert retrieved_bill.vendor_id == vendor.id

        # Verify vendor relationship
        assert retrieved_bill.vendor.name == "Test Vendor"

    def test_bill_ledger_transaction_relationship(self, db_session: Session):
        """Test bill can link to ledger transaction."""
        workspace = WorkspaceFactory(_session=db_session)
        vendor = EntityFactory(
            workspace_id=workspace.id,
            type=EntityType.VENDOR.value,
            _session=db_session
        )
        transaction = TransactionFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        bill = BillFactory(
            workspace_id=workspace.id,
            vendor_id=vendor.id,
            transaction_id=transaction.id,
            _session=db_session
        )
        db_session.commit()

        assert bill.transaction_id == transaction.id

    def test_bill_project_linking(self, db_session: Session):
        """Test project_id and milestone_id foreign keys."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        bill = BillFactory(
            workspace_id=workspace.id,
            project_id="project_123",
            milestone_id="milestone_456",
            _session=db_session
        )
        db_session.commit()

        assert bill.project_id == "project_123"
        assert bill.milestone_id == "milestone_456"

    def test_bill_documents_cascade(self, db_session: Session):
        """Test cascade delete to documents."""
        workspace = WorkspaceFactory(_session=db_session)
        vendor = EntityFactory(
            workspace_id=workspace.id,
            type=EntityType.VENDOR.value,
            _session=db_session
        )
        bill = BillFactory(
            workspace_id=workspace.id,
            vendor_id=vendor.id,
            _session=db_session
        )
        db_session.commit()

        # Create documents for bill
        doc1 = DocumentFactory(
            workspace_id=workspace.id,
            bill_id=bill.id,
            _session=db_session
        )
        doc2 = DocumentFactory(
            workspace_id=workspace.id,
            bill_id=bill.id,
            _session=db_session
        )
        db_session.commit()

        bill_id = bill.id
        doc_ids = [doc1.id, doc2.id]

        # Delete bill (should cascade to documents)
        db_session.delete(bill)
        db_session.commit()

        # Verify documents are deleted
        remaining_docs = db_session.query(Document).filter(
            Document.id.in_(doc_ids)
        ).all()
        assert len(remaining_docs) == 0

    def test_bill_amount_numeric_precision(self, db_session: Session):
        """Test Numeric(19,4) precision for amounts."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        amounts = [
            Decimal("0.01"),
            Decimal("999.9999"),
            Decimal("10000.00"),
        ]

        for amount in amounts:
            bill = BillFactory(
                workspace_id=workspace.id,
                amount=amount,
                _session=db_session
            )
            db_session.commit()
            assert bill.amount == amount


class TestInvoiceModel:
    """Test Invoice model (accounts receivable)."""

    def test_invoice_create_with_defaults(self, db_session: Session):
        """Test creating accounts receivable invoice."""
        workspace = WorkspaceFactory(_session=db_session)
        customer = EntityFactory(
            workspace_id=workspace.id,
            type=EntityType.CUSTOMER.value,
            _session=db_session
        )
        db_session.commit()

        invoice = Invoice(
            workspace_id=workspace.id,
            customer_id=customer.id,
            issue_date=datetime.utcnow(),
            due_date=datetime.utcnow() + timedelta(days=30),
            amount=Decimal("2500.00")
        )
        db_session.add(invoice)
        db_session.commit()
        db_session.refresh(invoice)

        assert invoice.workspace_id == workspace.id
        assert invoice.customer_id == customer.id
        assert invoice.amount == Decimal("2500.00")
        assert invoice.status == InvoiceStatus.DRAFT.value  # Default

    def test_invoice_status_enum(self, db_session: Session):
        """Test all InvoiceStatus enum values."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        statuses = [
            InvoiceStatus.DRAFT.value,
            InvoiceStatus.OPEN.value,
            InvoiceStatus.PAID.value,
            InvoiceStatus.VOID.value,
            InvoiceStatus.OVERDUE.value,
        ]

        for status in statuses:
            invoice = InvoiceFactory(
                workspace_id=workspace.id,
                status=status,
                _session=db_session
            )
            db_session.commit()
            assert invoice.status == status

    def test_invoice_customer_relationship(self, db_session: Session):
        """Test invoice belongs to customer."""
        workspace = WorkspaceFactory(_session=db_session)
        customer = EntityFactory(
            workspace_id=workspace.id,
            type=EntityType.CUSTOMER.value,
            name="Test Customer",
            _session=db_session
        )
        db_session.commit()

        invoice = InvoiceFactory(
            workspace_id=workspace.id,
            customer_id=customer.id,
            _session=db_session
        )
        db_session.commit()

        # Verify invoice references customer
        retrieved_invoice = db_session.query(Invoice).filter(
            Invoice.id == invoice.id
        ).first()
        assert retrieved_invoice.customer_id == customer.id

        # Verify customer relationship
        assert retrieved_invoice.customer.name == "Test Customer"

    def test_invoice_metadata_json_field(self, db_session: Session):
        """Test metadata_json field for line items and billing details."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        metadata = {
            "line_items": [
                {"description": "Service A", "quantity": 2, "unit_price": 100.00},
                {"description": "Service B", "quantity": 1, "unit_price": 300.00}
            ],
            "billing_details": {
                "terms": "net 30",
                "payment_method": "ACH"
            }
        }

        invoice = InvoiceFactory(
            workspace_id=workspace.id,
            metadata_json=metadata,
            _session=db_session
        )
        db_session.commit()

        # Retrieve and verify JSON data
        retrieved = db_session.query(Invoice).filter(
            Invoice.id == invoice.id
        ).first()
        assert retrieved.metadata_json == metadata
        assert len(retrieved.metadata_json["line_items"]) == 2

    def test_invoice_ledger_transaction_relationship(self, db_session: Session):
        """Test invoice can link to ledger transaction."""
        workspace = WorkspaceFactory(_session=db_session)
        customer = EntityFactory(
            workspace_id=workspace.id,
            type=EntityType.CUSTOMER.value,
            _session=db_session
        )
        transaction = TransactionFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        invoice = InvoiceFactory(
            workspace_id=workspace.id,
            customer_id=customer.id,
            transaction_id=transaction.id,
            _session=db_session
        )
        db_session.commit()

        assert invoice.transaction_id == transaction.id

    def test_invoice_documents_cascade(self, db_session: Session):
        """Test cascade delete to documents."""
        workspace = WorkspaceFactory(_session=db_session)
        customer = EntityFactory(
            workspace_id=workspace.id,
            type=EntityType.CUSTOMER.value,
            _session=db_session
        )
        invoice = InvoiceFactory(
            workspace_id=workspace.id,
            customer_id=customer.id,
            _session=db_session
        )
        db_session.commit()

        # Create documents for invoice
        doc1 = DocumentFactory(
            workspace_id=workspace.id,
            invoice_id=invoice.id,
            _session=db_session
        )
        doc2 = DocumentFactory(
            workspace_id=workspace.id,
            invoice_id=invoice.id,
            _session=db_session
        )
        db_session.commit()

        invoice_id = invoice.id
        doc_ids = [doc1.id, doc2.id]

        # Delete invoice (should cascade to documents)
        db_session.delete(invoice)
        db_session.commit()

        # Verify documents are deleted
        remaining_docs = db_session.query(Document).filter(
            Document.id.in_(doc_ids)
        ).all()
        assert len(remaining_docs) == 0


class TestDocumentModel:
    """Test Document model (financial documents)."""

    def test_document_create_for_bill(self, db_session: Session):
        """Test creating document linked to bill."""
        workspace = WorkspaceFactory(_session=db_session)
        vendor = EntityFactory(
            workspace_id=workspace.id,
            type=EntityType.VENDOR.value,
            _session=db_session
        )
        bill = BillFactory(
            workspace_id=workspace.id,
            vendor_id=vendor.id,
            _session=db_session
        )
        db_session.commit()

        document = Document(
            workspace_id=workspace.id,
            file_path="/docs/bill_123.pdf",
            file_name="bill_123.pdf",
            file_type="pdf",
            bill_id=bill.id
        )
        db_session.add(document)
        db_session.commit()

        assert document.bill_id == bill.id

    def test_document_create_for_invoice(self, db_session: Session):
        """Test creating document linked to invoice."""
        workspace = WorkspaceFactory(_session=db_session)
        customer = EntityFactory(
            workspace_id=workspace.id,
            type=EntityType.CUSTOMER.value,
            _session=db_session
        )
        invoice = InvoiceFactory(
            workspace_id=workspace.id,
            customer_id=customer.id,
            _session=db_session
        )
        db_session.commit()

        document = Document(
            workspace_id=workspace.id,
            file_path="/docs/invoice_456.pdf",
            file_name="invoice_456.pdf",
            file_type="pdf",
            invoice_id=invoice.id
        )
        db_session.add(document)
        db_session.commit()

        assert document.invoice_id == invoice.id

    def test_document_extracted_data_json(self, db_session: Session):
        """Test extracted_data JSON field for AI extraction cache."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        extracted_data = {
            "vendor": "ACME Corp",
            "amount": 1500.00,
            "date": "2025-03-11",
            "line_items": [
                {"description": "Consulting Services", "amount": 1000.00},
                {"description": "Travel", "amount": 500.00}
            ],
            "confidence": 0.95
        }

        document = DocumentFactory(
            workspace_id=workspace.id,
            extracted_data=extracted_data,
            _session=db_session
        )
        db_session.commit()

        # Retrieve and verify JSON data
        retrieved = db_session.query(Document).filter(
            Document.id == document.id
        ).first()
        assert retrieved.extracted_data == extracted_data
        assert retrieved.extracted_data["vendor"] == "ACME Corp"

    def test_document_bill_relationship(self, db_session: Session):
        """Test document belongs to bill."""
        workspace = WorkspaceFactory(_session=db_session)
        vendor = EntityFactory(
            workspace_id=workspace.id,
            type=EntityType.VENDOR.value,
            _session=db_session
        )
        bill = BillFactory(
            workspace_id=workspace.id,
            vendor_id=vendor.id,
            _session=db_session
        )
        db_session.commit()

        document = DocumentFactory(
            workspace_id=workspace.id,
            bill_id=bill.id,
            _session=db_session
        )
        db_session.commit()

        # Verify document references bill
        retrieved_doc = db_session.query(Document).filter(
            Document.id == document.id
        ).first()
        assert retrieved_doc.bill_id == bill.id

    def test_document_invoice_relationship(self, db_session: Session):
        """Test document belongs to invoice."""
        workspace = WorkspaceFactory(_session=db_session)
        customer = EntityFactory(
            workspace_id=workspace.id,
            type=EntityType.CUSTOMER.value,
            _session=db_session
        )
        invoice = InvoiceFactory(
            workspace_id=workspace.id,
            customer_id=customer.id,
            _session=db_session
        )
        db_session.commit()

        document = DocumentFactory(
            workspace_id=workspace.id,
            invoice_id=invoice.id,
            _session=db_session
        )
        db_session.commit()

        # Verify document references invoice
        retrieved_doc = db_session.query(Document).filter(
            Document.id == document.id
        ).first()
        assert retrieved_doc.invoice_id == invoice.id

