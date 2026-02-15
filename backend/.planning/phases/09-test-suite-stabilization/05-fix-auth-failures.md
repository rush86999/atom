# Plan 09-5: Fix Auth Endpoint Test Failures

**Phase**: Phase 09 - Test Suite Stabilization
**Status**: 📋 PENDING
**Priority**: CRITICAL
**Estimated**: 1 day
**Dependencies**: 09-2 (must complete first)
**Wave**: 2
**File**: `.planning/phases/09-test-suite-stabilization/05-fix-auth-failures.md`

---

## Overview

Fix all failing auth endpoint unit tests to achieve stable test suite.

**Goal**: Resolve all failures in test_auth_endpoints.py.

---

## Problem Statement

### Current Failures

Auth tests have collection errors (fixed in 09-2) but will likely have failures when run:
- Incorrect test assertions
- Mock setup issues
- Wrong expected behavior
- Missing test data

---

## Solution Approach

### Step 1: Run Tests and Collect Failures

```bash
pytest tests/unit/security/test_auth_endpoints.py -v
```

### Step 2: Analyze Failures

For each failure:
- Read the error message
- Understand what's being tested
- Identify why it's failing

### Step 3: Fix Failures

Fix issues systematically:
1. Fix incorrect assertions
2. Fix mock setup
3. Fix test data
4. Fix test logic

---

## Implementation Plan

### Task 1: Fix test_auth_endpoints.py Failures
**Estimated**: 8 hours

**Actions**:
1. Run tests and collect failures
2. Analyze each failure
3. Fix issues one by one
4. Verify each fix

**Expected Output**: All auth endpoint tests passing

---

## Acceptance Criteria

- [ ] `pytest tests/unit/security/test_auth_endpoints.py -v` passes with 0 failures
- [ ] All auth tests stable across multiple runs

---

## Notes

### Dependencies
- **09-2 must complete first**: Tests must collect before they can run

---

*Plan Created: 2026-02-15*
