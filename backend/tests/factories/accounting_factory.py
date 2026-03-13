"""
Factory Boy factories for accounting models.

Provides factories for all 12 accounting models:
- Account (chart of accounts)
- Transaction (transaction headers)
- JournalEntry (double-entry records)
- Entity (vendors and customers)
- Bill (accounts payable)
- Invoice (accounts receivable)
- Document (financial documents)
- CategorizationProposal (AI categorization suggestions)
- TaxNexus (tax jurisdictions)
- FinancialClose (period close tracking)
- CategorizationRule (auto-categorization rules)
- Budget (budget constraints)
"""

import factory
from factory import fuzzy
from datetime import datetime, timedelta, timezone
from tests.factories.base import BaseFactory

# Import accounting models
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

# Import related models for foreign keys
from tests.factories.workspace_factory import WorkspaceFactory


class AccountFactory(BaseFactory):
    """Factory for Account model (chart of accounts)."""

    class Meta:
        model = Account

    # Required fields
    id = factory.Faker('uuid4')
    name = factory.Faker('company')
    code = factory.Faker('numerify', text='####')
    type = fuzzy.FuzzyChoice([t.value for t in AccountType])
    workspace_id = factory.LazyAttribute(
        lambda o: WorkspaceFactory(_session=o._session).id
    )

    # Optional fields
    description = factory.Faker('sentence')
    is_active = True
    parent_id = None  # Self-referential, set manually if needed
    standards_mapping = factory.LazyFunction(
        lambda: {"gaap": "1001", "ifrs": "ASSET_CASH"}
    )
    last_audit_at = factory.LazyFunction(
        lambda: datetime.now(timezone.utc) - timedelta(days=30)
    )


class TransactionFactory(BaseFactory):
    """Factory for Transaction model (transaction headers)."""

    class Meta:
        model = Transaction

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.LazyAttribute(
        lambda o: WorkspaceFactory(_session=o._session).id
    )
    source = fuzzy.FuzzyChoice(['stripe', 'manual', 'bank_feed', 'api'])
    transaction_date = factory.Faker('date_time_this_year')
    category = fuzzy.FuzzyChoice([
        'llm_tokens', 'compute', 'storage', 'network', 'labor',
        'software', 'infrastructure', 'support', 'sales', 'other'
    ])

    # Optional fields
    external_id = factory.Faker('uuid4')
    status = fuzzy.FuzzyChoice([s.value for s in TransactionStatus])
    description = factory.Faker('sentence')
    amount = fuzzy.FuzzyFloat(0.01, 10000.0)
    metadata_json = factory.LazyFunction(dict)
    is_intercompany = False
    counterparty_workspace_id = None
    project_id = None
    milestone_id = None


class JournalEntryFactory(BaseFactory):
    """Factory for JournalEntry model (double-entry records)."""

    class Meta:
        model = JournalEntry

    # Required fields
    id = factory.Faker('uuid4')
    transaction_id = factory.LazyAttribute(
        lambda o: TransactionFactory(_session=o._session).id
    )
    account_id = factory.LazyAttribute(
        lambda o: AccountFactory(_session=o._session).id
    )
    type = fuzzy.FuzzyChoice([t.value for t in EntryType])
    amount = fuzzy.FuzzyFloat(0.01, 5000.0)

    # Optional fields
    currency = "USD"
    description = factory.Faker('sentence')


class EntityFactory(BaseFactory):
    """Factory for Entity model (vendors and customers)."""

    class Meta:
        model = Entity

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.LazyAttribute(
        lambda o: WorkspaceFactory(_session=o._session).id
    )
    name = factory.Faker('company')
    type = fuzzy.FuzzyChoice([t.value for t in EntityType])

    # Optional fields
    email = factory.Faker('email')
    phone = factory.Faker('phone_number')
    address = factory.Faker('address')
    tax_id = factory.Faker('numerify', text='##-#######')


class BillFactory(BaseFactory):
    """Factory for Bill model (accounts payable)."""

    class Meta:
        model = Bill

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.LazyAttribute(
        lambda o: WorkspaceFactory(_session=o._session).id
    )
    vendor_id = factory.LazyAttribute(
        lambda o: EntityFactory(type='vendor', _session=o._session).id
    )
    issue_date = factory.Faker('date_time_this_year')
    due_date = factory.LazyAttribute(
        lambda o: datetime.now(timezone.utc) + timedelta(days=30)
    )
    amount = fuzzy.FuzzyFloat(100.0, 10000.0)

    # Optional fields
    bill_number = factory.Faker('numerify', text='BILL-####')
    status = fuzzy.FuzzyChoice([s.value for s in BillStatus])
    description = factory.Faker('sentence')
    transaction_id = None
    project_id = None
    milestone_id = None


class InvoiceFactory(BaseFactory):
    """Factory for Invoice model (accounts receivable)."""

    class Meta:
        model = Invoice

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.LazyAttribute(
        lambda o: WorkspaceFactory(_session=o._session).id
    )
    customer_id = factory.LazyAttribute(
        lambda o: EntityFactory(type='customer', _session=o._session).id
    )
    issue_date = factory.Faker('date_time_this_year')
    due_date = factory.LazyAttribute(
        lambda o: datetime.now(timezone.utc) + timedelta(days=30)
    )
    amount = fuzzy.FuzzyFloat(100.0, 10000.0)

    # Optional fields
    invoice_number = factory.Faker('numerify', text='INV-####')
    status = fuzzy.FuzzyChoice([s.value for s in InvoiceStatus])
    description = factory.Faker('sentence')
    transaction_id = None
    metadata_json = factory.LazyFunction(
        lambda: {
            "line_items": [
                {"description": "Service A", "quantity": 1, "unit_price": 100.0}
            ],
            "billing_details": {"terms": "net 30"}
        }
    )


class DocumentFactory(BaseFactory):
    """Factory for Document model (financial documents)."""

    class Meta:
        model = Document

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.LazyAttribute(
        lambda o: WorkspaceFactory(_session=o._session).id
    )
    file_path = factory.Faker('file_path', extension='pdf')
    file_name = factory.Faker('file_name', extension='pdf')

    # Optional fields
    file_type = fuzzy.FuzzyChoice(['pdf', 'jpg', 'png', 'docx'])
    bill_id = None
    invoice_id = None
    extracted_data = factory.LazyFunction(
        lambda: {
            "vendor": "ACME Corp",
            "amount": 1500.00,
            "date": "2025-03-11",
            "line_items": ["Service A", "Service B"]
        }
    )


class CategorizationProposalFactory(BaseFactory):
    """Factory for CategorizationProposal model (AI suggestions)."""

    class Meta:
        model = CategorizationProposal

    # Required fields
    id = factory.Faker('uuid4')
    transaction_id = factory.LazyAttribute(
        lambda o: TransactionFactory(_session=o._session).id
    )
    suggested_account_id = factory.LazyAttribute(
        lambda o: AccountFactory(_session=o._session).id
    )
    confidence = fuzzy.FuzzyFloat(0.5, 1.0)

    # Optional fields
    reasoning = factory.Faker('sentence')
    is_accepted = None  # None=pending, True=accepted, False=rejected
    reviewed_by = None
    reviewed_at = None


class TaxNexusFactory(BaseFactory):
    """Factory for TaxNexus model (tax jurisdictions)."""

    class Meta:
        model = TaxNexus

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.LazyAttribute(
        lambda o: WorkspaceFactory(_session=o._session).id
    )
    region = fuzzy.FuzzyChoice([
        'California', 'New York', 'Texas', 'UK', 'Germany', 'France'
    ])

    # Optional fields
    tax_type = fuzzy.FuzzyChoice(['Sales Tax', 'VAT', 'GST'])
    is_active = True


class FinancialCloseFactory(BaseFactory):
    """Factory for FinancialClose model (period close tracking)."""

    class Meta:
        model = FinancialClose

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.LazyAttribute(
        lambda o: WorkspaceFactory(_session=o._session).id
    )
    period = factory.Faker('numerify', text='2025-##')

    # Optional fields
    is_closed = False
    closed_at = None
    closed_by = None
    metadata_json = factory.LazyFunction(
        lambda: {
            "checklist": ["journal_entries", "reconciliations", "reports"],
            "blockers": []
        }
    )


class CategorizationRuleFactory(BaseFactory):
    """Factory for CategorizationRule model (auto-categorization rules)."""

    class Meta:
        model = CategorizationRule

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.LazyAttribute(
        lambda o: WorkspaceFactory(_session=o._session).id
    )
    merchant_pattern = fuzzy.FuzzyChoice([
        'Amazon', 'Starbucks', 'AWS', 'Google Cloud', 'Microsoft Azure'
    ])
    target_account_id = factory.LazyAttribute(
        lambda o: AccountFactory(_session=o._session).id
    )

    # Optional fields
    confidence_weight = fuzzy.FuzzyFloat(1.0, 10.0)
    is_active = True


class BudgetFactory(BaseFactory):
    """Factory for Budget model (budget constraints)."""

    class Meta:
        model = Budget

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.LazyAttribute(
        lambda o: WorkspaceFactory(_session=o._session).id
    )
    amount = fuzzy.FuzzyFloat(1000.0, 50000.0)
    start_date = factory.LazyAttribute(
        lambda o: datetime.now(timezone.utc).replace(day=1)
    )
    end_date = factory.LazyAttribute(
        lambda o: (datetime.now(timezone.utc).replace(day=1) + timedelta(days=90))
    )

    # Optional fields
    project_id = None
    category_id = factory.LazyAttribute(
        lambda o: AccountFactory(_session=o._session).id
    )
    period = fuzzy.FuzzyChoice(['month', 'quarter', 'year'])
