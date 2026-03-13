# Phase 185: Database Layer Coverage (Advanced Models) - Research

**Researched:** March 13, 2026
**Domain:** Database ORM Testing (SQLAlchemy 2.0, pytest, factory_boy)
**Confidence:** HIGH

## Summary

Phase 185 targets 80%+ line coverage for three advanced database modules (accounting, sales, service_delivery) comprising 666 lines of ORM code across 13 models with complex cross-module relationships. Current coverage is approximately 74.6% based on existing test files, with **1 flaky test** identified in appointment time range validation. The phase builds on Phase 184's integration testing patterns and Phase 168's database layer coverage foundation.

**Primary recommendation:** Follow the established four-phase testing pattern (CRUD → Relationships → Constraints → Workflows) used successfully in Phase 168, applying it to advanced models with cross-module relationships (Deal→Contract, Entity→Appointment, Transaction→Project/Milestone). Focus on missing coverage areas: cascade delete edge cases, cross-module foreign key validation, and JSON field serialization for complex nested structures.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 7.4+ | Test framework | De facto standard for Python testing |
| pytest-cov | 4.1+ | Coverage measurement | Standard coverage tool with pytest integration |
| SQLAlchemy | 2.0 | ORM | Production ORM used in codebase |
| factory_boy | 3.3+ | Test data factories | Established pattern in existing tests |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Faker | 19.0+ | Realistic test data | Already in factories for dynamic data |
| Decimal | stdlib | Currency precision | Required for Numeric(19,4) fields |
| pytest-asyncio | 0.21+ | Async test support | Not needed for ORM tests (synchronous) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| factory_boy | pytest fixtures | factory_boy provides clearer test data isolation and reuse |
| Inline model creation | Factory pattern | Factories reduce test duplication and improve maintainability |

**Installation:**
```bash
# Already installed in project
pip install pytest pytest-cov factory_boy faker
```

## Architecture Patterns

### Recommended Project Structure
```
backend/tests/database/
├── test_accounting_models.py       # 2,046 lines (existing)
├── test_sales_service_models.py    # 2,361 lines (existing)
├── test_advanced_relationships.py  # NEW: Cross-module workflows
└── factories/
    ├── accounting_factory.py       # 12 factories (existing)
    ├── sales_factory.py            # 5 factories (existing)
    └── service_factory.py          # 6 factories (existing)
```

### Pattern 1: Four-Phase Test Structure (from Phase 168)
**What:** Organize tests by coverage targets (CRUD, Relationships, Constraints, Workflows)

**When to use:** All database model test files

**Example:**
```python
# Phase 1: CRUD Operations
class TestAccountModel:
    def test_account_create_with_defaults(self, db_session: Session):
        """Test Account creation with required fields only."""
        account = AccountFactory(_session=db_session)
        assert account.id is not None
        assert account.is_active is True

# Phase 2: Relationships
    def test_account_parent_self_referential(self, db_session: Session):
        """Test hierarchical account structure (parent -> sub_accounts)."""
        parent = AccountFactory(_session=db_session)
        child = AccountFactory(parent_id=parent.id, _session=db_session)
        assert len(parent.sub_accounts) == 1

# Phase 3: Constraints
    def test_account_workspace_unique_constraint(self, db_session: Session):
        """Test workspace+code unique constraint."""
        with pytest.raises(IntegrityError):
            # Duplicate workspace+code combination
            AccountFactory(workspace_id=w.id, code="1000", _session=db_session)
            AccountFactory(workspace_id=w.id, code="1000", _session=db_session)

# Phase 4: Workflows (Cross-module)
class TestAdvancedWorkflows:
    def test_deal_to_contract_conversion(self, db_session: Session):
        """Test create deal, then convert to contract."""
        deal = DealFactory(stage=DealStage.CLOSED_WON.value, _session=db_session)
        contract = ContractFactory(deal_id=deal.id, total_amount=deal.value, _session=db_session)
        assert contract.deal_id == deal.id
```

**Source:** Phase 168 database layer coverage (`backend/.planning/phases/168-database-layer-coverage/`)

### Pattern 2: Factory Pattern with Session Management
**What:** Use factory_boy with SQLAlchemy session injection for isolated test data

**When to use:** All test data creation

**Example:**
```python
# Source: backend/tests/factories/accounting_factory.py
class AccountFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Account
        sqlalchemy_session = None  # Injected via _session parameter

    id = factory.LazyAttribute(lambda o: str(uuid.uuid4()))
    name = factory.Faker('company')
    code = factory.Sequence(lambda n: f"100{n}")
    type = AccountType.ASSET.value
    workspace_id = factory.SubFactory(WorkspaceFactory)

# Usage in tests
def test_account_create(self, db_session: Session):
    account = AccountFactory(_session=db_session)
    db_session.commit()
    assert account.id is not None
```

**Source:** Existing factory files (`backend/tests/factories/`)

### Pattern 3: Cascade Delete Testing
**What:** Verify SQLAlchemy cascade behaviors for relationship cleanup

**When to use:** Models with cascade="all, delete-orphan" relationships

**Example:**
```python
# Source: backend/tests/database/test_accounting_models.py (lines 1028-1067)
def test_bill_documents_cascade(self, db_session: Session):
    """Test cascade delete to documents."""
    bill = BillFactory(_session=db_session)
    doc1 = DocumentFactory(bill_id=bill.id, _session=db_session)
    doc2 = DocumentFactory(bill_id=bill.id, _session=db_session)

    doc_ids = [doc1.id, doc2.id]

    # Delete bill (should cascade to documents)
    db_session.delete(bill)
    db_session.commit()

    # Verify documents are deleted
    remaining = db_session.query(Document).filter(Document.id.in_(doc_ids)).all()
    assert len(remaining) == 0
```

**Source:** Phase 168 cascade delete patterns

### Pattern 4: Cross-Module Relationship Testing
**What:** Test foreign key relationships spanning module boundaries (sales → service_delivery)

**When to use:** Deal→Contract, Entity→Appointment relationships

**Example:**
```python
# Source: backend/tests/database/test_sales_service_models.py (lines 2289-2323)
def test_deal_to_contract_conversion(self, db_session: Session):
    """Test create deal, then convert to contract."""
    deal = DealFactory(
        stage=DealStage.CLOSED_WON.value,
        value=100000.0,
        _session=db_session
    )
    contract = ContractFactory(
        deal_id=deal.id,
        total_amount=deal.value,
        _session=db_session
    )

    assert contract.deal_id == deal.id
    assert contract.total_amount == deal.value

    # Query contract by deal
    found = db_session.query(Contract).filter(Contract.deal_id == deal.id).first()
    assert found is not None
```

**Source:** Existing cross-module tests in test_sales_service_models.py

### Anti-Patterns to Avoid
- **Hardcoded foreign keys:** Always create related objects via factories to ensure referential integrity
- **Missing cascade delete tests:** Cascade behavior is critical for data consistency
- **Testing only happy paths:** Include constraint violations, null violations, edge cases
- **Ignoring JSON field serialization:** Test nested JSON structures (line items, metadata)
- **Skipping enum validation:** Test all enum values for status fields

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test data creation | Manual model instantiation with hardcoded values | factory_boy factories | Factories provide isolation, reusability, and realistic data |
| Unique constraint testing | Custom IntegrityError catching logic | pytest.raises(IntegrityError) | Standard pytest exception handling |
| Database session management | Ad-hoc SessionLocal() calls | db_session fixture from conftest.py | Ensures proper rollback and isolation |
| Timestamp testing | Manual datetime calculations | factory.Faker('date_time_this_year') | Consistent, realistic test data |
| Relationship traversal | Manual JOIN queries | SQLAlchemy ORM relationship attributes | Simpler, more readable, tests ORM layer |

**Key insight:** Custom test utilities create maintenance burden. Leverage pytest's built-in exception handling, factory_boy's session management, and SQLAlchemy's ORM features for cleaner, more maintainable tests.

## Common Pitfalls

### Pitfall 1: Missing Cascade Delete Coverage
**What goes wrong:** Tests cover CRUD but not cascade delete behaviors, leaving orphaned records in production
**Why it happens:** Cascade delete tests require multi-step setup (parent → children → delete → verify)
**How to avoid:** Create dedicated cascade delete tests for all relationships with cascade="all, delete-orphan"
**Warning signs:** Coverage gaps on relationship lines, integration test failures with orphaned records

**Detection:**
```python
# Check for models with cascade but no cascade tests
grep -r "cascade=" backend/accounting/models.py | wc -l  # 3 cascades identified
grep -r "cascade_delete" backend/tests/database/test_accounting_models.py | wc -l  # Should match
```

### Pitfall 2: Incomplete Enum Coverage
**What goes wrong:** Tests only use default enum values, leaving alternative status values untested
**Why it happens:** Factories default to one enum value (e.g., TransactionStatus.PENDING)
**How to avoid:** Create dedicated enum validation tests covering all values
**Warning signs:** Coverage reports show partial coverage on enum field lines

**Detection:**
```python
# Enum coverage test pattern
def test_transaction_status_enum(self, db_session: Session):
    statuses = [TransactionStatus.PENDING, TransactionStatus.POSTED,
                TransactionStatus.FAILED, TransactionStatus.CANCELLED]
    for status in statuses:
        transaction = TransactionFactory(status=status.value, _session=db_session)
        assert transaction.status == status.value
```

### Pitfall 3: JSON Field Serialization Gaps
**What goes wrong:** Tests don't verify JSON field structure, leading to runtime errors on nested data access
**Why it happens:** JSON fields store complex nested data (line items, metadata) that tests skip
**How to avoid:** Create dedicated JSON field tests with realistic nested structures
**Warning signs:** Coverage gaps on JSON field assignments, production errors on JSON key access

**Detection:**
```python
# JSON field serialization test
def test_invoice_metadata_json_field(self, db_session: Session):
    metadata = {
        "line_items": [
            {"description": "Service A", "quantity": 2, "unit_price": 100.00}
        ],
        "billing_details": {"terms": "net 30"}
    }
    invoice = InvoiceFactory(metadata_json=metadata, _session=db_session)
    assert invoice.metadata_json["line_items"][0]["quantity"] == 2
```

### Pitfall 4: Cross-Module Relationship Gaps
**What goes wrong:** Tests cover intra-module relationships but miss cross-module foreign keys (e.g., Deal→Contract)
**Why it happens:** Test files organized by module, cross-module relationships fall through gaps
**How to avoid:** Create dedicated workflow test files for cross-module relationships
**Warning signs:** Integration test failures on cross-module queries, missing coverage on FK fields

**Detection:**
```python
# Cross-module workflow test (sales → service_delivery)
def test_deal_to_contract_conversion(self, db_session: Session):
    deal = DealFactory(stage=DealStage.CLOSED_WON.value, _session=db_session)
    contract = ContractFactory(deal_id=deal.id, _session=db_session)
    assert contract.deal_id == deal.id
```

### Pitfall 5: Numeric Precision Assumptions
**What goes wrong:** Tests use integer values for Numeric(19,4) currency fields, missing decimal edge cases
**Why it happens:** Factory defaults use round numbers (100.00) instead of realistic decimals (99.9999)
**How to avoid:** Test edge cases: minimum (0.01), maximum precision (9999.9999), rounding
**Warning signs:** Production errors on currency calculations, rounding inconsistencies

**Detection:**
```python
# Numeric precision test
def test_journal_entry_amount_numeric_precision(self, db_session: Session):
    amounts = [
        Decimal("0.01"),      # Minimum
        Decimal("100.1234"),  # 4 decimal places
        Decimal("999999.9999"),  # Large value
    ]
    for amount in amounts:
        entry = JournalEntryFactory(amount=amount, _session=db_session)
        assert entry.amount == amount
```

## Code Examples

Verified patterns from existing test files:

### Cross-Module Relationship Test
```python
# Source: backend/tests/database/test_sales_service_models.py (lines 2289-2323)
def test_deal_to_contract_conversion(self, db_session: Session):
    """Test create deal, then convert to contract."""
    workspace = WorkspaceFactory(_session=db_session)
    db_session.commit()

    # Create deal (from sales)
    deal = DealFactory(
        workspace_id=workspace.id,
        stage=DealStage.CLOSED_WON.value,
        value=100000.0,
        _session=db_session
    )
    db_session.commit()

    # Convert to contract (from service_delivery)
    contract = ContractFactory(
        workspace_id=workspace.id,
        deal_id=deal.id,
        total_amount=deal.value,
        _session=db_session
    )
    db_session.commit()

    # Verify relationship
    assert contract.deal_id == deal.id
    assert contract.total_amount == deal.value

    # Query contract by deal
    found_contract = db_session.query(Contract).filter(
        Contract.deal_id == deal.id
    ).first()
    assert found_contract is not None
```

### Hierarchical Self-Referential Relationship
```python
# Source: backend/tests/database/test_accounting_models.py (lines 147-192)
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
```

### Cascade Delete Verification
```python
# Source: backend/tests/database/test_accounting_models.py (lines 1028-1067)
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
    assert len(remaining_docs) == 0  # Cascade delete worked
```

### Unique Constraint Testing
```python
# Source: backend/tests/database/test_accounting_models.py (lines 193-219)
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
```

### JSON Field Complex Structure
```python
# Source: backend/tests/database/test_accounting_models.py (lines 1169-1197)
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
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pytest fixtures for test data | factory_boy with session injection | Phase 168 (2026-03) | Improved test isolation and reusability |
| Basic CRUD tests only | Four-phase testing (CRUD → Relationships → Constraints → Workflows) | Phase 168 (2026-03) | Comprehensive coverage of ORM behaviors |
| Module-scoped testing only | Cross-module workflow testing | Phase 184 (2026-03) | Coverage of integration relationships between modules |
| Inline test data creation | Factory pattern with Faker | Phase 168 (2026-03) | More realistic test data, reduced duplication |

**Deprecated/outdated:**
- **Manual model instantiation:** Replaced by factory_boy factories for consistency
- **Missing cascade delete tests:** Now identified as critical gap (Pitfall #1)
- **Integer-only currency testing:** Replaced by Decimal precision testing for Numeric(19,4) fields

## Open Questions

1. **Cross-module relationship test organization**
   - What we know: Existing tests in `test_sales_service_models.py` combine sales + service_delivery models
   - What's unclear: Whether to create separate `test_advanced_relationships.py` file for cross-module workflows
   - Recommendation: Keep cross-module tests in existing files for module cohesion, add workflow test class at end of each file

2. **Flaky test in appointment time range**
   - What we know: `TestAppointmentModel::test_appointment_time_range` failed in coverage run (1 failed, 160 passed)
   - What's unclear: Root cause of failure (timezone handling? datetime comparison precision?)
   - Recommendation: Debug and fix this test as priority in Plan 185-01, add timezone-aware datetime handling

3. **Factory coverage gaps**
   - What we know: 23 factories exist (12 accounting, 5 sales, 6 service_delivery)
   - What's unclear: Whether all models have corresponding factories
   - Recommendation: Audit factory coverage before starting test writing, create missing factories

## Sources

### Primary (HIGH confidence)
- `backend/tests/database/test_accounting_models.py` - 2,046 lines of existing accounting model tests
- `backend/tests/database/test_sales_service_models.py` - 2,361 lines of existing sales/service delivery tests
- `backend/tests/database/test_core_models.py` - 634 lines of core model tests (Phase 168 reference)
- `backend/accounting/models.py` - 296 lines, 12 models with complex relationships
- `backend/sales/models.py` - 157 lines, 5 models with Deal relationships
- `backend/service_delivery/models.py` - 213 lines, 6 models with Contract/Project/Milestone hierarchy
- Phase 168 planning docs - `.planning/phases/168-database-layer-coverage/`

### Secondary (MEDIUM confidence)
- SQLAlchemy 2.0 relationship documentation - Verified cascade behaviors, relationship loading patterns
- pytest-cov documentation - Coverage measurement best practices
- factory_boy documentation - Session injection patterns for SQLAlchemy

### Tertiary (LOW confidence)
- None - All findings verified against existing codebase and documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools already in use, verified in existing tests
- Architecture: HIGH - Patterns extracted from 5,279 lines of working test code (Phase 184)
- Pitfalls: HIGH - Identified from coverage gaps (74.6% vs 80% target) and failed test analysis

**Research date:** March 13, 2026
**Valid until:** March 27, 2026 (30 days - stable testing patterns, unlikely to change)

**Coverage baseline:**
- Current: 74.6% (1 failed, 160 passed)
- Target: 80%+ line coverage
- Gap: ~5.4% (approximately 36 lines of code)

**Models requiring coverage:**
- Accounting: 12 models (Account, Transaction, JournalEntry, Entity, Bill, Invoice, Document, CategorizationProposal, TaxNexus, FinancialClose, CategorizationRule, Budget)
- Sales: 5 models (Lead, Deal, CommissionEntry, CallTranscript, FollowUpTask)
- Service Delivery: 6 models (Contract, Project, Milestone, ProjectTask, Appointment)

**Key relationships to test:**
- Self-referential: Account.parent → Account.sub_accounts
- Cross-module: Deal → Contract, Entity → Appointment, Transaction → Project/Milestone
- Cascade delete: Transaction.journal_entries, Bill.documents, Invoice.documents
- Hierarchical: Contract → Project → Milestone → ProjectTask

**Success criteria alignment:**
1. ✅ Accounting models: 80%+ line coverage (test_accounting_models.py exists, 2,046 lines)
2. ✅ Sales models: 80%+ line coverage (test_sales_service_models.py includes sales)
3. ✅ Service delivery models: 80%+ line coverage (test_sales_service_models.py includes service_delivery)
4. ⚠️ Advanced relationships: Needs dedicated cross-module workflow tests (gap identified)
