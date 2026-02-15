# Phase 09 - Test Suite Stabilization Requirements

**Milestone**: Test Suite Stabilization & Quality Gates
**Timeline**: 1 week (aggressive - 2026-02-15 to 2026-02-22)
**Last Updated**: 2026-02-15

---

## Milestone Overview

**Goal**: Stabilize the test suite by fixing all failing tests and errors, then establish quality gates to prevent regression.

**Success Criteria**:
- ✅ 0 test collection errors (currently 356 errors)
- ✅ 0 test failures (currently 324 failed)
- ✅ 98%+ test pass rate
- ✅ Quality gates established and enforced
- ✅ Property tests fixed and passing

**Approach**: Fix-first strategy - stabilize existing test suite before expanding coverage.

---

## Requirements

### REQ-1: Fix All Test Collection Errors
**Priority**: CRITICAL (BLOCKING)
**Status**: PENDING
**Estimated Effort**: 2 days

**Description**:
Resolve all 356 test collection errors that prevent tests from running. These are primarily import errors, missing dependencies, and fixture issues.

**Acceptance Criteria**:
- [ ] `pytest --collect-only` completes with 0 errors
- [ ] All 10,176+ tests collect successfully
- [ ] No import errors in any test file
- [ ] All fixtures properly defined and accessible

**Files to Fix**:
- `tests/unit/governance/test_supervision_service.py` - 5 errors
- `tests/unit/governance/test_trigger_interceptor.py` - 20 errors
- `tests/unit/security/test_auth_endpoints.py` - 5 errors
- Property tests with TypeErrors - 10 errors
- Any additional files with collection errors

**Implementation Notes**:
- Focus on import statements and fixture availability
- Ensure all mock patches have correct paths
- Verify test factory dependencies are properly imported

**Testing**:
- Run `pytest --collect-only -q` to verify 0 errors
- Confirm all tests can be collected without failures

---

### REQ-2: Fix All Test Failures
**Priority**: CRITICAL (BLOCKING)
**Status**: PENDING
**Estimated Effort**: 2 days

**Description**:
Resolve all 324 test failures to achieve stable test suite. Failures include assertion errors, incorrect expectations, and logic bugs.

**Acceptance Criteria**:
- [ ] Full test suite runs with 0 failures
- [ ] 98%+ pass rate achieved (allowing for known skips)
- [ ] All integration tests passing (currently 301/303, need 303/303)
- [ ] All unit tests passing
- [ ] Property tests passing

**Known Failure Categories**:
1. **Governance Tests** (test_supervision_service.py, test_trigger_interceptor.py)
   - Missing fixtures
   - Incorrect mock setup
   - Wrong assertion expectations

2. **Auth Endpoint Tests** (test_auth_endpoints.py)
   - Missing database fixtures
   - Incorrect request/response expectations
   - Authentication/authorization setup issues

3. **Property Tests**
   - TypeError in hypothesis/property test setup
   - Missing strategy definitions
   - Incorrect test data generation

**Implementation Notes**:
- Run tests with `-v` flag to see detailed failure output
- Use `-x` flag to stop at first failure for debugging
- Fix failures systematically by module/feature area
- Ensure proper test isolation (no shared state)

**Testing**:
- Run `pytest tests/ -v` to verify all tests pass
- Run `pytest tests/unit/` and `pytest tests/integration/` separately
- Verify property tests run successfully

---

### REQ-3: Fix Property Test TypeErrors
**Priority**: HIGH (Included in REQ-1/REQ-2)
**Status**: PENDING
**Estimated Effort**: 1 day

**Description**:
Fix TypeError issues in property tests that prevent collection. Property tests provide strong correctness guarantees and are valuable for catching edge cases.

**Acceptance Criteria**:
- [ ] All property tests collect successfully
- [ ] Property tests run without TypeError
- [ ] Property tests pass with meaningful assertions
- [ ] Hypothesis strategies properly defined

**Files to Fix**:
- `tests/property_tests/input_validation/test_input_validation_invariants.py`
- `tests/property_tests/temporal/test_temporal_invariants.py`
- `tests/property_tests/tools/test_tool_governance_invariants.py`
- Any other property test files with errors

**Implementation Notes**:
- Check hypothesis strategy definitions (@given decorators)
- Verify custom strategies are properly typed
- Ensure property test functions have correct signatures
- Review hypothesis settings for timeouts and examples

**Testing**:
- Run `pytest tests/property_tests/ -v` to verify all property tests pass
- Run `pytest tests/property_tests/ --hypothesis-seed=0` for reproducibility

---

### REQ-4: Establish Coverage Quality Gates
**Priority**: HIGH (Enforcement)
**Status**: PENDING
**Estimated Effort**: 0.5 days

**Description**:
Implement quality gates to prevent coverage regression and ensure test quality standards are maintained.

**Acceptance Criteria**:
- [ ] Pre-commit hook enforces minimum coverage for new code
- [ ] CI pipeline requires 98%+ test pass rate
- [ ] Coverage trend tracking implemented
- [ ] Automated coverage reports generated
- [ ] Coverage decreases block merges

**Implementation**:

**4.1 Pre-commit Coverage Hook**
```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: pytest-cov
      name: pytest with coverage
      entry: pytest tests/ --cov=core --cov=api --cov=tools --cov-fail-under=80
      language: system
      pass_filenames: false
      always_run: true
```

**4.2 CI Pass Rate Threshold**
```yaml
# .github/workflows/test.yml
- name: Run tests
  run: |
    pytest tests/ --cov --cov-report=json
    pass_rate=$(python -c "import json; print(json.load(open('coverage.json'))['test_pass_rate'])")
    if (( $(echo "$pass_rate < 98" | bc -l) )); then
      echo "Test pass rate $pass_rate% is below 98% threshold"
      exit 1
    fi
```

**4.3 Coverage Trend Tracking**
- Create `tests/coverage_reports/trends.json` to track coverage over time
- Add script to generate trend reports
- Update trend data on each CI run

**4.4 Coverage Report in CI**
- Generate HTML coverage report in CI
- Upload as artifact for review
- Add coverage comment to PRs

**Testing**:
- Test pre-commit hook with low-coverage code
- Verify CI fails on test failures
- Confirm coverage trend tracking updates

---

### REQ-5: Achieve 98%+ Test Pass Rate
**Priority**: CRITICAL (Success Metric)
**Status**: PENDING
**Estimated Effort**: Included in REQ-2

**Description**:
Achieve and maintain 98%+ test pass rate across the entire test suite.

**Acceptance Criteria**:
- [ ] Full test suite runs with 98%+ pass rate
- [ ] No flaky tests (tests that pass/fail intermittently)
- [ ] Test isolation verified (tests can run in any order)
- [ ] Consistent results across multiple runs

**Implementation Notes**:
- Fix flaky tests by improving isolation
- Use pytest-rerun for known flaky tests (document why)
- Ensure proper cleanup in test fixtures
- Avoid shared state between tests

**Testing**:
- Run full test suite 3 times to verify consistency
- Run tests in random order: `pytest tests/ --random-order`
- Verify no tests depend on execution order

---

## Out of Scope

### Explicitly Excluded
1. **New Feature Tests**: Adding tests for untested features (deferred to Phase 10)
2. **Coverage Expansion**: Increasing coverage percentage (deferred to Phase 10)
3. **Performance Tests**: Load testing and benchmarking (separate initiative)
4. **Frontend Tests**: Next.js/React Native tests (separate test suite)

### Rationale
This milestone focuses on **stabilization** - fixing existing broken tests. Coverage expansion is deferred to Phase 10 to ensure we have a solid foundation.

---

## Dependencies

### Internal Dependencies
- **REQ-1 must complete before REQ-2**: Tests must collect before they can run
- **REQ-2 must complete before REQ-5**: Can't measure pass rate with failing tests
- **REQ-1, REQ-2, REQ-3 can run in parallel**: Different test files

### External Dependencies
- **Python 3.11+**: Test framework requires Python 3.11 or higher
- **pytest, pytest-cov, pytest-asyncio**: Must be installed
- **hypothesis**: Property testing framework
- **factory-boy**: Test data factories

---

## Risk Assessment

### High Risk
1. **Property Test Complexity**: Property tests may require significant refactoring
   - **Mitigation**: Focus on unit/integration tests first if property tests prove too complex

2. **Test Isolation Issues**: Tests may have hidden dependencies
   - **Mitigation**: Use pytest fixtures with proper scope, run tests in random order

### Medium Risk
1. **Time Pressure**: 1 week is aggressive for 356 errors + 324 failures
   - **Mitigation**: Focus on highest-impact fixes first, defer edge cases

2. **Fixture Complexity**: Some tests may require complex fixture setup
   - **Mitigation**: Reuse existing fixtures, create helper functions

### Low Risk
1. **CI Pipeline Changes**: Quality gates may break CI
   - **Mitigation**: Test quality gates in fork before enforcing

---

## Success Metrics

### Quantitative Metrics
- **Collection Errors**: 356 → 0
- **Test Failures**: 324 → 0
- **Pass Rate**: 95.3% → 98%+
- **Property Tests**: 10 errors → 0 errors, all passing
- **Flaky Tests**: Identify and fix all flaky tests

### Qualitative Metrics
- **Test Suite Stability**: Tests pass consistently across multiple runs
- **Developer Confidence**: Team trusts test results
- **CI Reliability**: Green builds mean working code
- **Quality Gates**: All gates enforced and functional

---

## Timeline

### Day 1-2: Fix Collection Errors (REQ-1, REQ-3)
- Fix import errors and fixture issues
- Fix property test TypeErrors
- Verify all tests collect successfully

### Day 3-4: Fix Test Failures (REQ-2)
- Fix governance test failures
- Fix auth endpoint test failures
- Fix any remaining test failures

### Day 5: Quality Gates (REQ-4) & Pass Rate Verification (REQ-5)
- Implement pre-commit coverage hook
- Implement CI pass rate threshold
- Implement coverage trend tracking
- Verify 98%+ pass rate

### Day 6-7: Buffer & Finalization
- Run full test suite multiple times
- Fix any remaining issues
- Document lessons learned
- Prepare for Phase 10 (Coverage Expansion)

---

## Definition of Done

A requirement is considered **DONE** when:
- [ ] Acceptance criteria met
- [ ] Tests passing locally
- [ ] Code committed to git
- [ ] Changes documented in commit message
- [ ] No regressions in other areas

A milestone is considered **DONE** when:
- [ ] All critical requirements (REQ-1, REQ-2, REQ-5) complete
- [ ] All high-priority requirements (REQ-3, REQ-4) complete
- [ ] Success metrics met
- [ ] Quality gates enforced
- [ ] Test suite stable at 98%+ pass rate
- [ ] Documentation updated

---

## Open Questions

### To Be Resolved
1. **Property Test Strategy**: If property tests prove too complex to fix in 1 day, should we defer to Phase 10?
2. **Flaky Test Tolerance**: Should we use pytest-rerun for known flaky tests or fix them outright?
3. **Coverage Gate Threshold**: Is 80% minimum coverage for new code appropriate or should it be higher/lower?

---

## References

**Project Documentation**:
- `.planning/PROJECT.md` - Project overview and context
- `.planning/STATE.md` - Current state and pending work
- `CLAUDE.md` - Development guidelines

**Testing Documentation**:
- `docs/TESTING.md` - Testing patterns and best practices
- `pytest.ini` - Test configuration
- `tests/conftest.py` - Shared test fixtures

**Related Work**:
- Phase 44: CI Pipeline Fix (completed 2026-02-15)
- Phase 43: Integration Tests (completed 2026-02-14)

---

*Last Updated: 2026-02-15*
*Requirements Author: GSD New-Milestone Workflow*
