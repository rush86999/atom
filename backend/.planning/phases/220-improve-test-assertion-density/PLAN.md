# Phase 220: Improve Test Assertion Density

**Status**: PENDING
**Priority**: HIGH (test quality)
**Estimated Time**: 4-6 hours
**Depends On**: Phase 219 (test failures fixed)

---

## Goal

Bring 5 test files with low assertion density above 0.15 threshold to ensure test quality.

---

## Requirements

- **REQ-005**: All test files must have assertion density ≥0.15
- **REQ-006**: Tests must validate behavior, not just execute code

---

## Gap Closure

Closes test quality gaps identified in coverage report:
- 5 test files below 0.15 assertion density threshold
- Low assertion density indicates tests may not be validating outcomes properly

---

## Current State

**Low Assertion Density Files**:
1. `test_user_management_monitoring.py` - 0.054 (target: 0.15)
2. `test_supervision_learning_integration.py` - 0.042 (target: 0.15)
3. `test_mcp_a2a_tools.py` - 0.141 (target: 0.15)
4. `test_email_api_ingestion.py` - 0.105 (target: 0.15)
5. `test_auth_routes_coverage.py` - 0.091 (target: 0.15)

**What is Assertion Density?**
- Ratio of assertions to total test code
- Higher density = more validation per line of test code
- Low density suggests tests execute code but don't validate results

---

## Tasks

### Task 1: Improve test_user_management_monitoring.py assertion density

**File**: `tests/test_user_management_monitoring.py`
**Current**: 0.054
**Target**: 0.15+

**Actions**:
1. Read test file and identify test functions without assertions
2. Add assertions for expected outcomes:
   ```python
   # Bad (no assertion):
   user = create_user("test@example.com")
   get_user(user.id)

   # Good (assertions):
   user = create_user("test@example.com")
   retrieved = get_user(user.id)
   assert retrieved.email == "test@example.com"
   assert retrieved.id == user.id
   ```
3. Remove no-op test code (code that doesn't validate anything)
4. Add state validation after actions

**Expected Outcome**: Assertion density ≥0.15

---

### Task 2: Improve test_supervision_learning_integration.py assertion density

**File**: `tests/test_supervision_learning_integration.py`
**Current**: 0.042
**Target**: 0.15+

**Actions**:
1. Add validation for learning outcomes
   - Assert learning metrics improve
   - Assert supervision states transition correctly
2. Add assertions for supervision states
   - Assert agent maturity changes
   - Assert intervention triggers fire
3. Verify side effects are validated

**Expected Outcome**: Assertion density ≥0.15

---

### Task 3: Improve test_mcp_a2a_tools.py assertion density

**File**: `tests/test_mcp_a2a_tools.py`
**Current**: 0.141 (close to threshold)
**Target**: 0.15+

**Actions**:
1. Add tool execution result assertions
   - Assert return values are correct
   - Assert tool side effects occurred
2. Validate tool parameters and responses
3. Add error case assertions

**Expected Outcome**: Assertion density ≥0.15

---

### Task 4: Improve test_email_api_ingestion.py assertion density

**File**: `tests/test_email_api_ingestion.py`
**Current**: 0.105
**Target**: 0.15+

**Actions**:
1. Add email processing assertions
   - Assert email parsed correctly
   - Assert attachments processed
2. Validate database state changes
   - Assert records created/updated
   - Assert email metadata stored
3. Add pipeline validation

**Expected Outcome**: Assertion density ≥0.15

---

### Task 5: Improve test_auth_routes_coverage.py assertion density

**File**: `tests/test_auth_routes_coverage.py`
**Current**: 0.091
**Target**: 0.15+

**Actions**:
1. Add auth outcome assertions
   - Assert login succeeds with valid credentials
   - Assert login fails with invalid credentials
2. Validate token/session creation
   - Assert tokens have correct structure
   - Assert sessions created in database
3. Add auth flow validation

**Expected Outcome**: Assertion density ≥0.15

---

### Task 6: Verify all files meet 0.15 threshold

**Actions**:
1. Run assertion density checker
   ```bash
   pytest tests/ --durations=0 -v 2>&1 | grep "Assertion Density"
   ```
2. Confirm all 5 files now ≥0.15
3. Check that no new files dropped below threshold

**Expected Outcome**: All files pass assertion density check

---

### Task 7: Document assertion density patterns

**Actions**:
1. Create best practices guide
   - Where to add assertions
   - What to assert in unit vs. integration tests
   - How to balance assertion density with readability
2. Add examples to testing docs
3. Document common patterns

**Expected Outcome**: Clear documentation for future test writers

---

## Success Criteria

- [ ] All 5 test files ≥0.15 assertion density
- [ ] No tests marked with low assertion density warning
- [ ] Test quality documentation updated
- [ ] Tests still pass after adding assertions

---

## Acceptance Tests

```bash
# Test 1: Check assertion density for all 5 files
pytest tests/test_user_management_monitoring.py \
      tests/test_supervision_learning_integration.py \
      tests/test_mcp_a2a_tools.py \
      tests/test_email_api_ingestion.py \
      tests/test_auth_routes_coverage.py \
      -v 2>&1 | grep -E "Assertion Density|PASSED"

# Expected: All files ≥0.15

# Test 2: Verify tests still pass
pytest tests/ -q --tb=no 2>&1 | tail -3

# Expected: High pass rate maintained

# Test 3: Check documentation exists
cat docs/TESTING_ASSERTIONS.md | head -50

# Expected: Best practices documented
```

---

## Notes

- Assertion density is a test quality metric, not a direct coverage measure
- High assertion density catches more bugs without adding more tests
- This phase improves test hygiene before major coverage expansion in Phase 221
- After this phase, test suite will be high-quality foundation for coverage work

---

*Created: 2026-03-21*
*Next Action: Run Task 1 after Phase 219 completes*
