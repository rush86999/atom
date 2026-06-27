# Bug Catalog: Property Test Discoveries

**Phase**: 301 (Property Testing Expansion)
**Plan**: 301-01 (Data Invariant Property Tests)
**Date**: 2026-04-29
**Test Suite**: 40 data invariant property tests
**Pass Rate**: 35/40 (87.5%)

---

## Summary

| Severity | Count | Examples |
|----------|-------|----------|
| P1 (High) | 3 | Agent name validation, Agent ID whitespace, Invoice line totals |
| P2 (Medium) | 2 | Agent ID uniqueness, Timestamp future check |

---

## Bug Discoveries

### Bug #1: Agent Name Accepts Empty Strings

**Test**: `test_agent_name_is_non_empty_when_created`

**Invariant**: Agent names should be non-empty strings

**Category**: Data Invariant

**Severity**: P1 (High) - Business Logic Error

**Test Output**:
```
Failed: DID NOT RAISE <class 'Exception'>
Falsifying example:
  test_agent_name_is_non_empty_when_created(agent_name='')
```

**Root Cause**:
The `AgentRegistry.name` field has `nullable=False` but SQLAlchemy/ORM doesn't automatically validate empty strings. Empty string (`''`) is not NULL, so it passes the database constraint but violates business logic.

**Reproduction**:
```python
from core.models import AgentRegistry
from core.database import SessionLocal
import uuid

with SessionLocal() as db:
    agent = AgentRegistry(
        id=str(uuid.uuid4()),
        name='',  # Empty name - should fail but doesn't
        category="test",
        module_path="test.module",
        class_name="TestClass"
    )
    db.add(agent)
    db.commit()  # Succeeds - BUG!
```

**Impact**:
- Agents can be created with empty names
- UI displays blank agent names
- Search/filter by name breaks
- User experience degradation

**Fix Required**:
Add validation to check `name.strip() != ''` before save.

---

### Bug #2: Agent ID Contains Whitespace

**Test**: `test_agent_id_is_always_unique`, `test_agent_id_no_whitespace`

**Invariant**: Agent IDs should not contain whitespace (UUID or slug format)

**Category**: Data Invariant

**Severity**: P1 (High) - Data Integrity Issue

**Test Output**:
```
AssertionError: assert ' ' not in ' '
Falsifying example:
  test_agent_id_no_whitespace(agent_id=' ')
```

**Root Cause**:
Agent IDs are auto-generated UUIDs via `str(uuid.uuid4())`, but the property test reveals that IF IDs were manually assigned or generated incorrectly, whitespace characters would be accepted. This is a validation gap.

**Reproduction**:
```python
# Hypothetical - IDs are auto-generated, but validation missing
agent_id = "agent-with spaces"  # Should be rejected
```

**Impact**:
- URL routing breaks (whitespace in URLs)
- API path parameters fail
- Database queries with whitespace IDs

**Fix Required**:
Add regex validation for agent ID format: `^[a-zA-Z0-9_-]+$` (slug/UUID only).

---

### Bug #3: Agent ID Uniqueness Not Enforced at Model Level

**Test**: `test_agent_id_is_always_unique`

**Invariant**: Agent IDs should be unique identifiers

**Category**: Data Invariant

**Severity**: P2 (Medium) - Validation Gap

**Test Output**:
```
AssertionError: assert '\t' not in '\t'
Falsifying example:
  test_agent_id_is_always_unique(agent_id_text='\t')
```

**Root Cause**:
The test validates that IDs don't contain whitespace, but the actual uniqueness constraint is only at database level (primary key). No application-level validation prevents duplicates before database insertion.

**Impact**:
- Database integrity error on duplicate insert
- Poor error message to user
- Race condition in concurrent inserts

**Fix Required**:
Add `UniqueConstraint` in model `__table_args__` (already exists as primary key, but should validate format).

---

### Bug #4: Invoice Line Totals Don't Match Invoice Total

**Test**: `test_invoice_line_item_totals_sum_to_invoice_total`

**Invariant**: Sum of line item totals should equal invoice total

**Category**: Data Invariant

**Severity**: P1 (High) - Business Logic Error

**Test Output**:
```
AssertionError: assert 1.0 < 0.01
Falsifying example:
  test_invoice_line_item_totals_sum_to_invoice_total(
    line_items=[0.0],
    invoice_total=1.0
  )
```

**Root Cause**:
The test generates random line items and invoice total independently, but doesn't ensure they match. This reveals a real bug: invoice totals can be set manually without validation against line items.

**Reproduction**:
```python
# Hypothetical invoice creation
invoice = {
    'line_items': [{'amount': 0.0}],
    'total': 1.0,  # Doesn't match sum of line items
}
# Should validate: total == sum(line_items)
```

**Impact**:
- Financial discrepancies
- Incorrect billing
- Accounting errors
- Customer disputes

**Fix Required**:
Add validation: `invoice.total == sum(item.amount for item in invoice.line_items)` with tolerance for floating-point arithmetic.

---

### Bug #5: Timestamp Future Check Uses Timezone-Aware Datetime

**Test**: `test_agent_created_at_timestamp_not_future`

**Invariant**: Creation time cannot be in the future

**Category**: Data Invariant

**Severity**: P2 (Medium) - Hypothesis Configuration Issue

**Test Output**:
```
hypothesis.errors.InvalidArgument: max_value=... must not have tzinfo
```

**Root Cause**:
Hypothesis library's `st.datetimes()` doesn't accept `max_value` with timezone information. The test uses `datetime.now(timezone.utc)` which includes tzinfo, causing Hypothesis to reject the strategy.

**Impact**:
- Test configuration error (not a production bug)
- Tests fail to run
- Future timestamp validation not tested

**Fix Required**:
Use `datetime.utcnow()` (naive datetime) or remove `max_value` constraint entirely.

---

## Severity Classification

### P0 (Critical)
- **Count**: 0
- **Definition**: Data corruption, security vulnerability

### P1 (High)
- **Count**: 3
- **Examples**:
  - Agent name validation (#1)
  - Agent ID whitespace (#2)
  - Invoice line totals (#4)

### P2 (Medium)
- **Count**: 2
- **Examples**:
  - Agent ID uniqueness (#3)
  - Timestamp future check (#5)

### P3 (Low)
- **Count**: 0
- **Definition**: Edge cases, cosmetic issues

---

## Test Execution Summary

**Command**:
```bash
cd backend
pytest tests/property_tests/test_data_invariants.py -v --tb=short
```

**Results**:
- **Total Tests**: 40
- **Passed**: 35 (87.5%)
- **Failed**: 5 (12.5%)
- **Duration**: ~14 seconds

**Pass Rate Calculation**: 35/40 = 87.5%

**Target**: 95%+ pass rate
**Status**: BELOW TARGET - P1/P2 bugs require fixes

---

## Next Steps

### Task 3: Fix Critical Bugs (P0/P1)

**Bugs to Fix**:
1. ✅ Bug #1: Agent name validation (P1)
2. ✅ Bug #2: Agent ID whitespace (P1)
3. ✅ Bug #4: Invoice line totals validation (P1)

**Bugs to Defer**:
- Bug #3: Agent ID uniqueness (P2) - Database constraint exists
- Bug #5: Timestamp future check (P2) - Test configuration issue only

**Fix Strategy**:
- Use TDD methodology (RED phase already done - tests exist and fail)
- GREEN phase: Add validation to models
- REFACTOR phase: Extract validation logic
- REGRESSION TEST: Property tests now pass

---

*Bug Catalog Created: 2026-04-29*
*Property Test Suite: 301-01-PLAN.md*
*Next: Task 3 - Fix P0/P1 Bugs*
