# TDD Code Review Checklist

**Purpose**: Ensure code reviews enforce TDD compliance and quality standards.

**Version**: 1.0
**Milestone**: v12.0

---

## Section 1: TDD Process Compliance

### Red Phase (Test Written First)
- [ ] Test written **before** implementation code
- [ ] Test fails with expected error (validates test works)
- [ ] Test name describes behavior (e.g., `test_agent_maturity_blocks_demotion`)
- [ ] Test is minimal (one behavior, one assertion)

**Review Questions**:
- Can you see the commit where test was added before implementation?
- Does the test fail if you revert the implementation?
- Is the test name descriptive (not `test_feature_1`)?

### Green Phase (Minimal Fix)
- [ ] Implementation is minimal (no over-engineering)
- [ ] Only code needed to pass test added
- [ ] No extra features added (YAGNI principle)
- [ ] Hardcoded values acceptable (generalize in refactor)

**Review Questions**:
- Is the implementation the simplest possible code to make test pass?
- Are there any unnecessary features added in this PR?
- Can any code be deferred to refactor phase?

### Refactor Phase (Code Quality)
- [ ] Code structure improved while tests pass
- [ ] Extracted methods for clarity
- [ ] Renamed for readability
- [ ] No behavior changes (tests still pass)

**Review Questions**:
- Is the code more readable after refactoring?
- Are methods extracted for reusability?
- Do all tests still pass (no behavior changes)?

---

## Section 2: Test Quality

### Backend Tests (Python/pytest)
- [ ] Tests behavior, not implementation (public API, not private methods)
- [ ] Only mocks external dependencies (LLM, database, network)
- [ ] Uses descriptive assertions (assert `x == y`, not `assertTrue(x)`)
- [ ] Test files follow naming convention (`test_*.py`)
- [ ] Tests are independent (no shared state between tests)

**Review Questions**:
- Are you testing public methods (not `private` methods)?
- Are mocks only for external services (LLM, database)?
- Do tests use `assertEqual`, not `assertTrue(a == b)`?
- Can tests run in parallel (no shared state)?

### Frontend Tests (TypeScript/React Testing Library)
- [ ] Uses accessible queries (`getByRole`, not `getByTestId`)
- [ ] Tests user interactions (click, type), not component state
- [ ] No testing of internal state (useState, useContext)
- [ ] Tests describe user behavior, not implementation
- [ ] Uses `userEvent` (not `fireEvent`) for interactions

**Review Questions**:
- Are queries using `getByRole`, `getByLabelText` (not `getByTestId`)?
- Are tests clicking buttons, not calling component methods?
- Is test code focused on user behavior (not component internals)?
- Are you using `userEvent` for realistic interactions?

---

## Section 3: Bug Fix Validation

### Bug Reproduction
- [ ] Failing test reproduces bug (can demonstrate bug before fix)
- [ ] Test fails with expected error message
- [ ] Bug is clearly described in test docstring
- [ ] Test commit is separate from fix commit

**Review Questions**:
- Can you run the test before the fix and see it fail?
- Is the bug described in the test docstring?
- Is the test in a separate commit from the fix?

### Root Cause Fix
- [ ] Fix addresses root cause (not just symptom)
- [ ] Test prevents regression (will catch if bug reoccurs)
- [ ] Fix is minimal (no unrelated changes)
- [ ] Side effects considered (no new bugs introduced)

**Review Questions**:
- Does the fix address why the bug occurred (not just what broke)?
- Will this test catch the bug if someone reintroduces it?
- Are there any unrelated changes in this PR?

### Documentation
- [ ] Bug documented in code comments (why it occurred)
- [ ] Fix pattern documented (how to prevent similar bugs)
- [ ] Test explains bug (docstring describes issue)
- [ ] Related issues linked (GitHub issue, bug tracker)

**Review Questions**:
- Is there a comment explaining the root cause?
- Is the test name/docstring descriptive of the bug?
- Are related issues linked in the PR description?

---

## Section 4: Anti-Pattern Detection

### ❌ Testing Implementation Details
**Symptoms**:
- Testing private methods (`_private_method`)
- Testing component state (`useState` values)
- Asserting on mock calls (`mock.called_with`)

**What to Say**:
> "This test is checking implementation details. Let's test the public API instead. Users won't care if the private method changes, but they do care if the output is correct."

### ❌ Over-Mocking
**Symptoms**:
- Mocking datetime, random, simple functions
- Mocks that drift from real implementation
- Tests pass but code is broken

**What to Say**:
> "We're mocking too much here. Let's only mock external dependencies (LLM, database). For datetime, use `freeze_time` fixture. For simple functions, test real behavior."

### ❌ Brittle Selectors (React)
**Symptoms**:
- Using `getByTestId`, `getByClassName`
- Tests break on CSS/HTML changes
- Not testing accessibility

**What to Say**:
> "This selector is brittle. Let's use `getByRole` or `getByLabelText` instead. This also tests accessibility and won't break on CSS changes."

### ❌ Skipping Red Phase
**Symptoms**:
- Test and implementation in same commit
- Test passes immediately (no failing state)
- No evidence test ran before implementation

**What to Say**:
> "I don't see a failing test state. Can you revert the implementation and show the test failing? This validates the test works."

---

## Section 5: Quality Gates

### Test Coverage
- [ ] New code has test coverage (backend: 70%+, frontend: 18.75%+)
- [ ] Critical paths tested (API endpoints, business logic)
- [ ] Bug fixes have 100% test coverage (no exceptions)

**Review Questions**:
- Does coverage report show new code covered?
- Are critical paths (APIs, business logic) tested?
- Do bug fixes have regression tests?

### Test Pass Rate
- [ ] All tests pass (100% pass rate required)
- [ ] No flaky tests (tests that sometimes fail)
- [ ] No skipped tests without explanation

**Review Questions**:
- Do all tests pass in CI?
- Are there any tests that fail intermittently?
- Are skipped tests documented with reason?

### Performance
- [ ] Tests run quickly (<5 minutes for backend, <10 minutes for frontend)
- [ ] No expensive operations in tests (no real LLM calls, no real database queries)
- [ ] Parallel execution supported (tests can run concurrently)

**Review Questions**:
- Do tests run quickly (can developers run them frequently)?
- Are external services mocked (LLM, database)?
- Can tests run in parallel (no shared state)?

---

## Section 6: Example Review Comments

### Good TDD (Praise)
```markdown
Great TDD workflow here! ✅

1. ✅ Test written before implementation (commit abc123)
2. ✅ Test fails with expected error (verified locally)
3. ✅ Minimal fix in green phase (no over-engineering)
4. ✅ Refactoring improves clarity (extracted `_validate_maturity`)
5. ✅ Test prevents regression (will catch if bug reintroduced)

This is a perfect example of red-green-refactor cycle.
```

### Bad TDD (Feedback)
```markdown
This PR needs TDD improvements: ⚠️

**Issues**:
1. ❌ No failing test state (test passes immediately)
2. ❌ Testing implementation details (private method `_validate_input`)
3. ❌ Over-mocked (mocking datetime, should use `freeze_time`)

**Action Items**:
1. Add commit showing test failing before implementation
2. Refactor test to check public API behavior, not private method
3. Use `@freeze_time` fixture instead of mocking datetime

Please address and we'll re-review.
```

### Bug Fix Feedback
```markdown
Bug fix looks good, but test needs improvement: ⚠️

**What's Good**:
- ✅ Test reproduces bug
- ✅ Fix addresses root cause
- ✅ Minimal fix

**What Needs Improvement**:
- ❌ Test name doesn't describe bug (`test_agent_service` → `test_agent_maturity_blocks_demotion`)
- ❌ No docstring explaining bug
- ❌ Test and fix in same commit (separate commits for review clarity)

**Action Items**:
1. Rename test to describe bug behavior
2. Add docstring: "BUG: Agent maturity allows demotion (security risk)"
3. Separate into 2 commits: test (failing) → fix (passing)

Otherwise, fix looks solid! 🎯
```

---

## Section 7: Quick Reference

### TDD Compliance Summary
- [ ] Test written before implementation
- [ ] Test fails before fix
- [ ] Minimal fix (no over-engineering)
- [ ] Refactoring while tests pass
- [ ] All tests pass (no regressions)

### Test Quality Summary
- [ ] Tests behavior (not implementation)
- [ ] Accessible queries (getByRole)
- [ ] Only mocks external dependencies
- [ ] Descriptive test names
- [ ] Independent tests (no shared state)

### Bug Fix Summary
- [ ] Test reproduces bug
- [ ] Root cause fixed
- [ ] Regression test added
- [ ] Bug documented

---

## Appendix: Code Review Template

```markdown
## TDD Compliance

- [ ] Test written before implementation
- [ ] Test fails before fix
- [ ] Minimal fix
- [ ] Refactoring while tests pass
- [ ] All tests pass

## Test Quality

- [ ] Tests behavior, not implementation
- [ ] Accessible queries used
- [ ] Only mocks external dependencies
- [ ] Descriptive test names

## Bug Fixes (if applicable)

- [ ] Test reproduces bug
- [ ] Root cause fixed
- [ ] Regression test added
- [ ] Bug documented

## Overall Assessment

**Strengths**:
-

**Areas for Improvement**:
-

**Decision**: APPROVED / CHANGES REQUESTED
```

---

*Code Review Checklist created for Atom v12.0*
*Purpose: Enforce TDD compliance in code reviews*
