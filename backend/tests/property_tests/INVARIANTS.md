# Property Test Invariants

This document catalogs all invariants tested by the property-based test suite.

## Purpose

Property-based tests verify system invariants - properties that must always hold true regardless of input. This document provides:

- **Invariant definitions**: What property is being tested
- **Test locations**: Where to find the test implementation
- **Criticality**: Which invariants are safety-critical vs. optimization
- **Bug evidence**: Real bugs found through property testing
- **Test configuration**: Hypothesis settings (max_examples, deadlines)

## Criticality Levels

- **Critical**: System failure or data corruption if violated (e.g., financial transactions)
- **Important**: Data integrity issues if violated (e.g., constraints)
- **Optimization**: Performance issues if violated (e.g., index usage)

## Database Transaction Domain

### Transaction Atomicity (ACID - A)
**Invariant**: Transactions must be atomic - all-or-nothing execution.
**Test**: `test_transaction_atomicity` (TestTransactionConsistencyInvariants)
**File**: `test_database_invariants.py`
**Critical**: Yes (financial transactions require atomicity)
**max_examples**: 200 (critical for data integrity)
**Bug Found**: Negative balance from partial transaction (debit failed, credit succeeded)
**Scenario**: Overdraft protection - balance=100, debit=150 should rollback to 100, not become -50

### Transaction Isolation (ACID - I)
**Invariant**: Transactions must be isolated - concurrent operations shouldn't interfere.
**Test**: `test_transaction_isolation` (TestTransactionConsistencyInvariants)
**File**: `test_database_invariants.py`
**Critical**: Yes (concurrent transaction safety)
**max_examples**: 200 (critical for concurrency bugs)
**Bug Found**: Dirty reads when transaction A read uncommitted data from transaction B
**Scenario**: Transfer shows intermediate state - account 1 debited but account 2 not yet credited

### Transaction Durability (ACID - D)
**Invariant**: Committed transactions must be durable - survive system failures.
**Test**: `test_transaction_durability` (TestTransactionConsistencyInvariants)
**File**: `test_database_invariants.py`
**Critical**: Yes (data persistence guarantee)
**max_examples**: 100 (important but not latency-critical)
**Bug Found**: Committed data lost after crash due to delayed fsync
**Scenario**: 1000 records committed, power loss, only 750 recovered on restart

### Transaction Consistency (ACID - C)
**Invariant**: Transactions must maintain consistency - database transitions between valid states.
**Test**: `test_transaction_consistency` (TestTransactionConsistencyInvariants)
**File**: `test_database_invariants.py`
**Critical**: Yes (financial consistency)
**max_examples**: 200 (critical for data integrity)
**Bug Found**: Total balance changed due to integer overflow in credit operation
**Scenario**: Transfer 100 from A to B - A decreased by 100, B increased by 99 (off-by-one)

### Foreign Key Constraints
**Invariant**: Child records must reference existing parent records.
**Test**: `test_foreign_key_constraint` (TestDataIntegrityInvariants)
**File**: `test_database_invariants.py`
**Critical**: Yes (referential integrity)
**max_examples**: 100
**Bug Found**: Orphaned child records with FK=999 when parents were {1, 2, 3}
**Scenario**: Missing FK constraint validation in bulk_insert() allowed orphans

### Unique Constraints
**Invariant**: Constrained columns must contain unique values (no duplicates).
**Test**: `test_unique_constraint` (TestDataIntegrityInvariants)
**File**: `test_database_invariants.py`
**Critical**: Yes (data integrity)
**max_examples**: 100
**Bug Found**: Duplicate email addresses due to race condition in INSERT
**Scenario**: Two concurrent users register with same email - both succeeded

### Check Constraints
**Invariant**: Values must satisfy defined conditions (e.g., balance >= 0).
**Test**: `test_check_constraint` (TestDataIntegrityInvariants)
**File**: `test_database_invariants.py`
**Critical**: Yes (data validity)
**max_examples**: 100
**Bug Found**: Negative balances allowed despite CHECK(balance >= 0) constraint
**Scenario**: PRAGMA foreign_keys=OFF disabled constraint silently

### Enum Constraints
**Invariant**: Only valid values accepted for ENUM columns.
**Test**: `test_enum_constraint` (TestDataIntegrityInvariants)
**File**: `test_database_invariants.py`
**Critical**: Yes (type safety)
**max_examples**: 100
**Bug Found**: Invalid status='cancelled' allowed when ENUM defined only 3 values
**Scenario**: Missing CHECK constraint in schema, only validated in application code

### Optimistic Locking
**Invariant**: Stale updates must be rejected (version conflict detection).
**Test**: `test_optimistic_locking` (TestConcurrencyControlInvariants)
**File**: `test_database_invariants.py`
**Critical**: No (concurrency optimization, not safety)
**max_examples**: 100
**Bug Found**: Stale updates overwrote newer data due to wrong version comparison
**Scenario**: version=3 updating record at version=5 should fail with 409 Conflict

### Pessimistic Locking
**Invariant**: Lock holder has exclusive access; others must wait.
**Test**: `test_pessimistic_locking` (TestConcurrencyControlInvariants)
**File**: `test_database_invariants.py`
**Critical**: Yes (prevents lost updates)
**max_examples**: 100
**Bug Found**: Concurrent transactions modified same row due to missing FOR UPDATE
**Scenario**: Lock acquisition skipped for performance, lost update anomaly occurred

### Deadlock Detection
**Invariant**: Circular wait chains must be detected and broken.
**Test**: `test_deadlock_detection` (TestConcurrencyControlInvariants)
**File**: `test_database_invariants.py`
**Critical**: Yes (prevents system hang)
**max_examples**: 100
**Bug Found**: Infinite hang due to missing timeout in lock acquisition
**Scenario**: A waits for B, B waits for C, C waits for A - deadlock never detected

### Isolation Levels
**Invariant**: Isolation levels must prevent anomalies appropriate to their level.
**Test**: `test_isolation_levels` (TestConcurrencyControlInvariants)
**File**: `test_database_invariants.py`
**Critical**: Yes (concurrency correctness)
**max_examples**: 100
**Bug Found**: Non-repeatable reads at READ_COMMITTED due to missing snapshot
**Scenario**: Transaction A reads row twice, sees different values after B updates

## Domain Summary

**Total Database Invariants**: 12
**Critical Invariants**: 10 (atomicity, isolation, durability, consistency, all constraints, locking, deadlocks, isolation)
**Non-Critical Invariants**: 2 (optimistic locking is optimization, not safety)
**Bugs Documented**: 12 validated bugs across ACID properties, constraints, and concurrency
**Test Coverage**: ACID (4), Constraints (4), Concurrency (4)

## ACID Properties Breakdown

- **Atomicity (A)**: 1 invariant - Transaction atomicity
- **Consistency (C)**: 1 invariant - Transaction consistency
- **Isolation (I)**: 2 invariants - Transaction isolation, Isolation levels
- **Durability (D)**: 1 invariant - Transaction durability

## Constraint Categories

- **Referential**: Foreign key constraints
- **Uniqueness**: Unique constraints (no duplicates)
- **Domain**: Check constraints (value ranges)
- **Type**: Enum constraints (valid values)

## Concurrency Control Categories

- **Optimistic**: Version conflict detection
- **Pessimistic**: Lock-based exclusive access
- **Deadlock**: Circular wait detection and resolution
- **Isolation**: Anomaly prevention by level

## Test Configuration Guidelines

### max_examples Selection

- **200**: Critical financial invariants (atomicity, isolation, consistency)
- **100**: Important but not latency-critical (durability, constraints, concurrency)
- **50**: Non-critical performance optimizations (query optimization, index usage)

### @example() Decorators

Each invariant test includes specific edge cases:
- **Boundary conditions**: Empty sets, maximum values, zero/negative cases
- **Bug reproductions**: Exact scenarios that triggered historical bugs
- **Typical operations**: Normal usage patterns for regression testing

## Bug-Finding Evidence Format

All VALIDATED_BUG sections document:
1. **Symptom**: What went wrong
2. **Root cause**: Why it happened
3. **Fix**: Commit hash and solution description
4. **Scenario**: Concrete example that reproduces the bug

## Related Documentation

- Property Tests README: `backend/tests/property_tests/README.md`
- Hypothesis Documentation: https://hypothesis.readthedocs.io/
- ACID Properties: See database transaction theory

## Maintenance

When adding new invariants:
1. Update this document with invariant definition
2. Mark criticality level
3. Document any bugs found during testing
4. Justify max_examples selection
5. Add @example() decorators for edge cases
