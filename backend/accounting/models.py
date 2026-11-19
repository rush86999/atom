import enum
import uuid
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class AccountType(str, enum.Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"

class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    POSTED = "posted"
    FAILED = "failed"
    CANCELLED = "cancelled"

class EntryType(str, enum.Enum):
    DEBIT = "debit"
    CREDIT = "credit"

class EntityType(str, enum.Enum):
    VENDOR = "vendor"
    CUSTOMER = "customer"
    BOTH = "both"

class BillStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"

class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    OVERDUE = "overdue"

class Account(Base):
    __tablename__ = "accounting_accounts"
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    code = Column(String, nullable=False) # e.g., "1000", "5000"
    type = Column(SQLEnum(AccountType, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    parent_id = Column(String, ForeignKey("accounting_accounts.id"), nullable=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    standards_mapping = Column(JSON, nullable=True) # e.g. {"gaap": "1001", "ifrs": "ASSET_CASH"}
    last_audit_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('workspace_id', 'code', name='_workspace_code_uc'),
    )

    # Relationships
    parent = relationship("Account", remote_side=[id], backref="sub_accounts")
    entries = relationship("JournalEntry", back_populates="account")

class Transaction(Base):
    """Event-sourced transaction header

    All transactions MUST have a category for cost attribution accuracy.
    The category field enforces that every cost is properly categorized,
    preventing uncategorized transactions that would bypass budget tracking.
    """
    __tablename__ = "accounting_transactions"
    __table_args__ = {'extend_existing': True}  # Resolve SQLAlchemy metadata conflict with core/models.py

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    external_id = Column(String, nullable=True, index=True) # e.g. Stripe ID, Bank ID
    source = Column(String, nullable=False) # e.g. "stripe", "manual", "bank_feed"
    status = Column(SQLEnum(TransactionStatus, values_callable=lambda obj: [e.value for e in obj]), default=TransactionStatus.PENDING)
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    description = Column(Text, nullable=True)
    amount = Column(Numeric(precision=19, scale=4), nullable=True) # Denormalized for convenience
    metadata_json = Column(JSON, nullable=True)
    is_intercompany = Column(Boolean, default=False)
    counterparty_workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True)

    # Cost Attribution - Category is NOT NULL to enforce cost categorization
    # Standard categories: llm_tokens, compute, storage, network, labor, software,
    # infrastructure, support, sales, other
    category = Column(String(50), nullable=False, index=True, default='other')

    # Project Linking
    project_id = Column(String, ForeignKey("service_projects.id"), nullable=True)
    milestone_id = Column(String, ForeignKey("service_milestones.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    journal_entries = relationship("JournalEntry", back_populates="transaction", cascade="all, delete-orphan")

class JournalEntry(Base):
    """The double-entry record"""
    __tablename__ = "accounting_journal_entries"
    __table_args__ = {'extend_existing': True}  # Resolve SQLAlchemy metadata conflict with core/models.py

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = Column(String, ForeignKey("accounting_transactions.id"), nullable=False)
    account_id = Column(String, ForeignKey("accounting_accounts.id"), nullable=False)
    type = Column(SQLEnum(EntryType, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    amount = Column(Numeric(precision=19, scale=4), nullable=False)
    currency = Column(String, default="USD")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    transaction = relationship("Transaction", back_populates="journal_entries")
    account = relationship("Account", back_populates="entries")

class CategorizationProposal(Base):
    """AI-generated categorization suggestion"""
    __tablename__ = "accounting_categorization_proposals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = Column(String, ForeignKey("accounting_transactions.id"), nullable=False)
    suggested_account_id = Column(String, ForeignKey("accounting_accounts.id"), nullable=False)
    confidence = Column(Float, nullable=False) # 0.0 to 1.0
    reasoning = Column(Text, nullable=True)
    is_accepted = Column(Boolean, nullable=True) # True: accepted, False: rejected, None: pending
    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    transaction = relationship("Transaction", backref="proposals")
    suggested_account = relationship("Account")

class Entity(Base):
    """Vendors and Customers"""
    __tablename__ = "accounting_entities"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    type = Column(SQLEnum(EntityType, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    tax_id = Column(String, nullable=True) # e.g. TIN, VAT
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    bills = relationship("Bill", back_populates="vendor")
    invoices = relationship("Invoice", back_populates="customer")

class Bill(Base):
    """Accounts Payable (Obligation to pay a vendor)"""
    __tablename__ = "accounting_bills"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    vendor_id = Column(String, ForeignKey("accounting_entities.id"), nullable=False)
    bill_number = Column(String, nullable=True)
    issue_date = Column(DateTime(timezone=True), nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)
    amount = Column(Numeric(precision=19, scale=4), nullable=False)
    currency = Column(String, default="USD")
    status = Column(SQLEnum(BillStatus, values_callable=lambda obj: [e.value for e in obj]), default=BillStatus.DRAFT)
    description = Column(Text, nullable=True)
    transaction_id = Column(String, ForeignKey("accounting_transactions.id"), nullable=True) # Linked ledger tx
    
    # Project Linking
    project_id = Column(String, ForeignKey("service_projects.id"), nullable=True)
    milestone_id = Column(String, ForeignKey("service_milestones.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    vendor = relationship("Entity", back_populates="bills")
    ledger_transaction = relationship("Transaction")
    documents = relationship("Document", back_populates="bill", cascade="all, delete-orphan")

class Invoice(Base):
    """Accounts Receivable (Obligation to be paid by a customer)"""
    __tablename__ = "accounting_invoices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    customer_id = Column(String, ForeignKey("accounting_entities.id"), nullable=False)
    invoice_number = Column(String, nullable=True)
    issue_date = Column(DateTime(timezone=True), nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)
    amount = Column(Numeric(precision=19, scale=4), nullable=False)
    currency = Column(String, default="USD")
    status = Column(SQLEnum(InvoiceStatus, values_callable=lambda obj: [e.value for e in obj]), default=InvoiceStatus.DRAFT)
    description = Column(Text, nullable=True)
    transaction_id = Column(String, ForeignKey("accounting_transactions.id"), nullable=True) # Linked ledger tx
    metadata_json = Column(JSON, nullable=True) # Additional invoice metadata (line items, billing details, etc.)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    customer = relationship("Entity", back_populates="invoices")
    ledger_transaction = relationship("Transaction")
    documents = relationship("Document", back_populates="invoice", cascade="all, delete-orphan")

class Document(Base):
    """Financial documents (receipts, bills, invoices)"""
    __tablename__ = "accounting_documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    file_path = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=True) # e.g. "pdf", "image"
    bill_id = Column(String, ForeignKey("accounting_bills.id"), nullable=True)
    invoice_id = Column(String, ForeignKey("accounting_invoices.id"), nullable=True)
    extracted_data = Column(JSON, nullable=True) # Cache of AI extraction results
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    bill = relationship("Bill", back_populates="documents")
    invoice = relationship("Invoice", back_populates="documents")

class TaxNexus(Base):
    """Identified tax presence in a jurisdiction"""
    __tablename__ = "accounting_tax_nexus"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    region = Column(String, nullable=False) # e.g. "California", "NY", "UK"
    tax_type = Column(String, default="Sales Tax")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class FinancialClose(Base):
    """Tracks status of periodic financial closes"""
    __tablename__ = "accounting_closes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    period = Column(String, nullable=False) # e.g. "2025-10"
    is_closed = Column(Boolean, default=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    closed_by = Column(String, ForeignKey("users.id"), nullable=True)
    metadata_json = Column(JSON, nullable=True) # Checklists, blockers
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CategorizationRule(Base):
    """Learned or manual rules for auto-categorization"""
    __tablename__ = "accounting_rules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    merchant_pattern = Column(String, nullable=False) # e.g. "Amazon", "Starbucks"
    target_account_id = Column(String, ForeignKey("accounting_accounts.id"), nullable=False)
    confidence_weight = Column(Float, default=1.0) # Increases as user accepts more
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('workspace_id', 'merchant_pattern', name='_workspace_merchant_uc'),
    )

class Budget(Base):
    """Budget constraints for projects or departments"""
    __tablename__ = "accounting_budgets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    project_id = Column(String, nullable=True) # Linked to task systems
    category_id = Column(String, ForeignKey("accounting_accounts.id"), nullable=True)
    amount = Column(Numeric(precision=19, scale=4), nullable=False)
    period = Column(String, default="month") # "month", "quarter", "year"
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class InvoiceProviderBinding(Base):
    """Current local invoice -> provider invoice binding.

    A local invoice has at most one current binding per provider.  The
    ``(workspace_id, provider, provider_account_id, provider_mode,
    external_invoice_id)`` constraint is deliberately independent of the local
    invoice: one external invoice may not be claimed by two local invoices in
    the same provider account/mode.

    Provider credentials are intentionally absent.  Only the scoped connection
    identifier needed to look up credentials is stored.
    """

    __tablename__ = "accounting_invoice_provider_bindings"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "invoice_id",
            "provider",
            name="_accounting_invoice_provider_binding_uc",
        ),
        UniqueConstraint(
            "workspace_id",
            "provider",
            "provider_account_id",
            "provider_mode",
            "external_invoice_id",
            name="_accounting_provider_invoice_binding_uc",
        ),
        {"extend_existing": True},
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(
        String,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_id = Column(
        String,
        ForeignKey("accounting_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider = Column(String, nullable=False, index=True)
    provider_account_id = Column(String, nullable=False)
    provider_mode = Column(String, nullable=False)
    external_invoice_id = Column(String, nullable=False)
    connection_id = Column(
        String,
        ForeignKey("user_connections.id"),
        nullable=False,
        index=True,
    )

    # Starts at 1 and is incremented by the compare-and-swap update.  It is the
    # optimistic concurrency token used by ``invoice_provider_binding``.
    revision = Column(Integer, nullable=False, default=1, server_default="1")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    revisions = relationship(
        "InvoiceProviderBindingRevision",
        back_populates="binding",
        cascade="all, delete-orphan",
    )


class InvoiceProviderBindingRevision(Base):
    """Append-only receipt for a binding creation or correction.

    Each row records the exact provider identity before and after the change,
    including the scoped connection identifier, but never provider credentials
    or customer content.  The binding and its receipt are written in the same
    transaction/savepoint.
    """

    __tablename__ = "accounting_invoice_provider_binding_revisions"
    __table_args__ = (
        UniqueConstraint(
            "binding_id",
            "revision",
            name="_accounting_invoice_provider_binding_revision_uc",
        ),
        {"extend_existing": True},
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    binding_id = Column(
        String,
        ForeignKey("accounting_invoice_provider_bindings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(
        String,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_id = Column(
        String,
        ForeignKey("accounting_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    revision = Column(Integer, nullable=False)
    actor_id = Column(String, ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=True)

    prior_provider = Column(String, nullable=True)
    prior_provider_account_id = Column(String, nullable=True)
    prior_provider_mode = Column(String, nullable=True)
    prior_external_invoice_id = Column(String, nullable=True)
    prior_connection_id = Column(String, nullable=True)

    new_provider = Column(String, nullable=False)
    new_provider_account_id = Column(String, nullable=False)
    new_provider_mode = Column(String, nullable=False)
    new_external_invoice_id = Column(String, nullable=False)
    new_connection_id = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    binding = relationship("InvoiceProviderBinding", back_populates="revisions")
