# Domain Pitfalls: Test Coverage Expansion for Existing Codebases

**Domain:** Testing Quality & Coverage Expansion
**Researched:** April 13, 2026
**Overall confidence:** HIGH

## Executive Summary

Adding comprehensive test coverage (70-80% targets) to existing Python backend and Next.js frontend codebases introduces specific pitfalls beyond general testing challenges. The primary risks are **coverage gaming** (testing trivial code to hit numbers), **brittle test suites** (over-coupled tests that break during refactoring), **CI/CD performance degradation** (slower pipelines as test count grows), and **test suite maintenance burden** (tests becoming harder to maintain than production code).

Based on v10.0 audit findings and authoritative sources (Martin Fowler, Google Testing Blog), the key insight is that **coverage is a tool for finding untested code, not a metric of test quality**. High coverage numbers (70-80%+) are "too easy to reach with low quality testing" and create "ignorance-promoting dashboards."

**Critical recommendation:** Focus on testing **critical business logic** and **edge cases**, not arbitrary percentage targets. Use coverage as a diagnostic tool to find gaps, not as a goal to maximize. Prioritize high-impact files (>200 lines with <10% coverage) over blanket percentage targets.

**v10.0 Critical Lessons:**
- Service-level coverage estimates (74.6%) vs actual line coverage (8.50%) = 66.1pp false confidence gap
- 1,504 failing frontend tests (28.8% failure rate) block coverage measurement
- 80% targets unrealistic: achieved 18.25% backend, 14.61% frontend
- Mock inconsistencies: 66 tests affected by mock vs float comparison errors

---

## Key Findings

**Stack:** pytest/pytest-cov (Python), Jest/React Testing Library (Next.js), pytest-xdist (parallelization), MSW (API mocking)
**Architecture:** Test pyramid (70% unit, 20% integration, 10% E2E), parallel execution infrastructure, quality gates with enforcement
**Critical pitfall:** Coverage gaming — testing trivial code (DTOs, constants) to hit arbitrary 70-80% targets while missing critical business logic
**Integration challenge:** CI/CD performance degradation as test suite grows without smart selection or parallelization optimization
**v10.0 lesson:** 1,504 failing frontend tests (28.8% failure rate) block coverage measurement; must fix test suite health before expanding coverage

## Implications for Roadmap

Based on research and v10.0 audit, suggested phase structure for v11.0:

1. **Test Suite Health First** — Fix failing tests, address brittleness, optimize performance **before** adding new coverage
   - Addresses: 1,504 failing frontend tests, flaky tests, slow test execution
   - Avoids: Building on shaky foundation that will require rework
   - **Evidence from v10.0:** Frontend coverage 14.61% with 28.8% test failure rate means coverage measurement is blocked

2. **High-Impact File Prioritization** — Focus on files >200 lines with <10% coverage (critical business logic)
   - Addresses: Coverage gaming (testing trivial code)
   - Avoids: Diminishing returns from testing DTOs/constants
   - **Strategy:** Backend governance, LLM routing, episodic memory services first; utilities later

3. **Quality Over Quantity** — Require meaningful assertions, not just coverage percentage
   - Addresses: Coverage without quality, assertion-free testing
   - Avoids: False confidence from high coverage numbers
   - **Implementation:** Mutation testing for critical paths, assertion density checks

4. **Parallel Execution Maintenance** — Keep <15 min feedback as test suite grows
   - Addresses: CI/CD performance degradation
   - Avoids: Pipeline slowing to hours as coverage expands
   - **Current status:** pytest-xdist operational, Jest worker farms configured

5. **Pragmatic Targets** — 70% instead of 80% based on v10.0 experience
   - Addresses: Unrealistic expectations from previous milestone
   - Avoids: Missing targets causing morale/velocity issues
   - **Evidence:** v10.0 aimed for 80%, achieved 18.25% backend and 14.61% frontend

**Phase ordering rationale:**
- Test health fixes unblock coverage measurement (can't measure with 28.8% failure rate)
- High-impact prioritization prevents coverage gaming
- Quality gates prevent assertion-free tests
- Parallelization maintenance prevents CI slowdown
- Pragmatic targets reflect reality of existing codebase constraints

**Research flags for phases:**
- Phase 250 (All Test Fixes): HIGH value — Fixes 1,504 failing frontend tests, unblocks coverage measurement
- Phase 251-253 (Backend Coverage): HIGH risk — Coverage gaming if not focused on high-impact files
- Phase 254-256 (Frontend Coverage): HIGH risk — 1,504 failing tests block measurement; must fix first
- Phase 258 (Quality Gates): HIGH value — Maintains enforcement throughout expansion

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Coverage Gaming Pitfalls | HIGH | Martin Fowler's authoritative blog post + v10.0 audit evidence |
| Test Pyramid & CI Performance | HIGH | Google Testing Blog official guidance + existing infrastructure documented |
| Brittle Test Anti-Patterns | HIGH | v10.0 audit findings (mock inconsistencies, 66 tests affected) + Fowler |
| Frontend Test Failures | HIGH | v10.0 audit: 1,504 failing tests (28.8% failure rate) documented |
| pytest-xdist Parallelization | HIGH | Existing infrastructure operational, documented in guides |
| Jest Worker Farms | HIGH | Frontend coverage guide documents CI/CD integration |
| Coverage Measurement Pitfalls | HIGH | v10.0 audit: service-level estimates (74.6%) vs actual line coverage (8.50%) gap |
| Flaky Test Patterns | HIGH | Existing FLAKY_TEST_GUIDE.md (923 lines) with comprehensive patterns |

---

## Critical Pitfalls

Mistakes that cause rewrites, major issues, or significantly impact velocity during coverage expansion.

### Pitfall 1: Coverage Gaming (Testing the Wrong Things)

**What goes wrong:** Teams write meaningless tests to hit coverage targets instead of testing what matters. This creates high coverage numbers with low quality assurance.

**Why it happens:**
- Management mandates arbitrary percentage targets (e.g., "70% coverage required")
- Coverage dashboards become "ignorance-promoting metrics" (Fowler)
- Developers game the system to satisfy gates
- Path of least resistance: test trivial code (DTOs, constants), avoid complex logic
- "High coverage numbers are too easy to reach with low quality testing"

**Evidence from Atom:**
- v10.0 documented: Service-level estimates showed 74.6% coverage, actual line coverage was 8.50% (66.1pp gap)
- Gap caused by measuring coverage per service (boolean aggregation) instead of actual line execution
- False confidence masked thousands of untested lines

**Consequences:**
- **False sense of security:** High coverage but production bugs increase
- **Trivial code tested:** Getters/setters, constants, auto-generated code, DTOs
- **Complex logic untested:** Error paths, race conditions, edge cases in business logic
- Tests become coverage exercises rather than quality validation
- **"Ignorance-promoting dashboards"** — Coverage percentage masks quality issues

**Prevention:**
1. **Use coverage as a diagnostic tool, not a target** — Run coverage tools to find untested code, then ask: "Does this worry me?"
2. **Focus on critical paths first** — Prioritize testing high-risk, high-value code (governance, LLM routing, episodic memory) over utility functions
3. **High-impact file prioritization** — Target files >200 lines with <10% coverage first (not 100-line files with 50%)
4. **Quality over quantity** — A few well-tested edge cases beat 100 trivial tests
5. **Test desirability matrix** — Kent Beck's framework: value of test × likelihood of catching bugs
6. **Audit test assertions** — Regularly review tests for actual verification vs. just executing code
7. **Risk-based coverage targets** — 70% coverage for critical paths, <50% acceptable for trivial utilities

**Detection:**
- Coverage increases but bug rate doesn't decrease
- Tests for trivial code (DTOs, constants) outnumber tests for complex logic
- High coverage percentage but low confidence in code changes
- Coverage dashboard is primary quality metric
- Managers ask "what's our coverage percentage?" not "what are we testing?"
- Service-level aggregation masks low actual line coverage (Atom v10.0: 74.6% estimate vs 8.50% actual)

**Phase to address:**
**Phase 250 (All Test Fixes)** — Fix 1,504 failing frontend tests first, then focus on high-impact files (>200 lines, <10% coverage). Phase 251-253 (Backend Coverage) must prioritize governance, LLM, episodes over DTOs and utilities.

**Sources:**
- [Martin Fowler: Test Coverage](https://martinfowler.com/bliki/TestCoverage.html) — HIGH confidence (official source, authoritative perspective)
- [Atom v10.0 Audit](/.planning/MILESTONE-v10.0-AUDIT.md) — HIGH confidence (documented evidence)

---

### Pitfall 2: Brittle Tests (Over-Coupling to Implementation)

**What goes wrong:** Tests break during refactoring even when behavior hasn't changed, creating refactoring resistance and maintenance burden.

**Why it happens:**
- Testing implementation details (private methods, internal state) instead of public interfaces
- Over-mocking dependencies creates tight coupling to structure
- Tests verify exact call sequences instead of outcomes
- Chained mocking (`when(a.getB().getC().getValue())`) couples to implementation structure
- Tests "require excessively long changes" for simple code changes

**Evidence from Atom:**
- v10.0 Phase 101: Mock vs float comparison errors affected 66 tests
- Canvas tests failing with mock inconsistencies (expo-sharing mock, MMKV getString issues)
- Frontend tests: Over-mocking components causes brittleness

**Consequences:**
- **Refactoring pain:** Simple changes break dozens of tests
- **Developers hesitate to improve code** due to test maintenance cost
- **Loss of trust:** Flaky tests teach teams to ignore failures
- **"You are testing too much if you can remove tests while still having enough"** (Fowler)
- **Maintenance burden > feature development time**

**Prevention:**
1. **Test behavior, not implementation** — Focus on inputs/outputs, not how code achieves results
2. **Black-box testing** — Test public interfaces only; treat code under test as opaque
3. **Mock only external dependencies** — Don't mock your own domain classes; use real implementations
4. **Avoid chained mocking** — Law of Demeter violations in tests indicate coupling
5. **Integration tests for complex interactions** — Some logic is better tested at integration level
6. **Refactor tests regularly** — Apply same cleanup practices to tests as production code

**Detection:**
- Tests break when code is refactored (behavior unchanged)
- Test setup requires 5+ mock objects for simple operations
- Tests verify method calls but not actual outcomes
- High test-to-code ratio but low confidence
- "I'm afraid to change this code because it will break so many tests"

**Phase to address:**
**All phases** — Brittle tests are a systemic issue. Audit existing tests for coupling during Phase 250 (test fixes). Establish test design guidelines: test behavior not implementation, mock only external dependencies (APIs, databases), use real objects for domain logic.

**Sources:**
- [Martin Fowler: Test Coverage](https://martinfowler.com/bliki/TestCoverage.html) — HIGH confidence (official source)
- [Atom v10.0 Audit](/.planning/MILESTONE-v10.0-AUDIT.md) — HIGH confidence (Phase 101 mock issues documented)

---

### Pitfall 3: CI/CD Performance Degradation

**What goes wrong:** Test suite growth slows CI/CD pipelines, reducing feedback speed and deployment velocity. "Tests are slowing you down" is a sign of testing too much.

**Why it happens:**
- Adding tests without optimizing execution time
- Too many E2E/UI tests (slow by nature)
- No test parallelization or sharding
- All tests run on every commit (no smart test selection)
- E2E tests dominate test suite (violate test pyramid)
- Test suite grows linearly with coverage targets

**Evidence from Atom:**
- v10.0 established parallel execution infrastructure (<15 min feedback target)
- pytest-xdist operational for backend
- Jest worker farms configured for frontend
- v10.0 audit: Test suite health impacts CI reliability

**Consequences:**
- **Feedback loops slow** from minutes to hours
- **Deployment velocity drops** as teams wait for test results
- **Developers run tests less frequently** before committing
- **"A simple change to code causes excessively long changes to tests"** (Fowler)
- **Google's scenario:** 3+ days lost debugging E2E test failures before release

**Prevention:**
1. **Follow the test pyramid** — 70% unit tests, 20% integration, 10% E2E (Google Testing Blog)
2. **Parallel execution** — Distribute tests across multiple CI agents (Atom has <15 min feedback with parallelization)
3. **Test sharding** — Split test suite by runtime, dependencies, or historical data
4. **Smart test selection** — Run only tests affected by code changes
5. **Fast feedback tiers** — Quick smoke tests first, full suite later in pipeline
6. **Monitor test execution time** — Add performance budgets to CI pipeline
7. **Categorize slow tests** — Mark with `@pytest.mark.slow`, run in separate CI job

**Detection:**
- Pipeline time increases linearly with test count
- Developers skip running tests locally due to slowness
- E2E tests take >30 minutes
- No parallelization or test selection strategy
- "I'll just let CI handle the tests" (developers not running locally)

**Phase to address:**
**Phase 258 (Quality Gates)** — Maintain <15 min feedback as test suite grows. Monitor execution time trends. Phase 149 (Quality Infrastructure Parallel) established operational parallelization — must maintain this during expansion.

**Sources:**
- [Google Testing Blog: Just Say No to More End-to-End Tests](https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html) — HIGH confidence (official source)
- [Atom v10.0 Documentation](/.planning/PROJECT.md) — HIGH confidence (infrastructure documented)

---

### Pitfall 4: Measurement Methodology Errors (Service-Level vs Line Coverage)

**What goes wrong:** Using service-level coverage estimates (aggregated boolean coverage per service) instead of actual line coverage creates false confidence and masks thousands of untested lines.

**Why it happens:**
- Coverage tools aggregate measurements differently
- Service-level estimates show "74.6% coverage" when actual line coverage is 8.50%
- Teams don't validate coverage.json structure before trusting metrics
- Different coverage.py versions use different field names
- Misunderstanding of what "coverage percentage" represents

**Evidence from Atom:**
- v10.0 Phase 160-162: Service-level estimates showed 74.6% coverage for episode services
- Actual line coverage: 8.50% (66.1 percentage point gap)
- Gap caused by measuring coverage per service (boolean: covered/not) vs actual line execution counts
- **Root cause:** coverage.json missing `files` array, only `totals` section present
- Impact: Thousands of untested lines masked by misleading high percentage

**Consequences:**
- **False confidence:** Team thinks 74.6% covered, reality is 8.50%
- **Misguided prioritization:** Effort spent on already-covered services instead of uncovered lines
- **Milestone delays:** Targets appear closer than they are
- **Wasted effort:** Testing already-covered code instead of finding gaps
- **Broken audit trail:** Coverage trending data is meaningless

**Prevention:**
1. **Always validate coverage.json structure** — Check for `files` array (not just `totals`)
2. **Use actual line coverage** — Parse `line_covered / num_statements` from coverage.json
3. **Baseline with correct methodology** — Document baseline using actual line execution counts
4. **Cross-validate measurements** — Compare HTML report, JSON, and terminal output
5. **Field name validation** — Handle coverage.py version differences (`covered_lines` vs `line_covered`)
6. **Documentation standards** — Require methodology documentation in verification reports

**Detection:**
```python
# Validation check (from backend/docs/COVERAGE_GUIDE.md)
assert 'files' in cov, "coverage.json missing 'files' array - service-level aggregation detected"
assert 'num_statements' in cov['totals'], "totals missing num_statements - not actual line coverage"
```

**Phase to address:**
**Phase 251 (Backend Coverage Baseline)** — MUST establish baseline using actual line coverage methodology (documented in `backend/docs/COVERAGE_GUIDE.md`). All subsequent phases must validate coverage.json has `files` array before trusting metrics.

**Sources:**
- [Backend Coverage Guide](/backend/docs/COVERAGE_GUIDE.md) — HIGH confidence (methodology documented)
- [Atom v10.0 Audit](/.planning/MILESTONE-v10.0-AUDIT.md) — HIGH confidence (gap quantified)

---

### Pitfall 5: Flaky Tests Eroding Confidence

**What goes wrong:** Tests with non-deterministic outcomes (pass/fail without code changes) teach teams to ignore failures, masking real bugs and wasting debugging time.

**Why it happens:**
- Race conditions in async operations
- Shared state between tests (database, globals)
- Time-dependent assertions without mocking
- External service dependencies (APIs, databases)
- Resource contention (ports, files) in parallel execution
- Order dependency (tests assume specific execution sequence)

**Evidence from Atom:**
- Existing FLAKY_TEST_GUIDE.md (923 lines) documents comprehensive patterns
- v10.0 Phase 101: 66 tests affected by mock inconsistencies (flaky behavior)
- pytest-rerunfailures configured: `--reruns 2 --reruns-delay 1`
- pytest-xdist parallel execution increases flakiness risk

**Consequences:**
- **"Cry wolf" effect:** Teams ignore test failures
- **Wasted time:** Developers debug non-existent bugs (30 min × 10 developers = 5 hours/week)
- **Masked real failures:** Legitimate bugs hidden among flaky failures
- **Slowed CI:** Re-running tests increases cycle time
- **Eroded confidence:** "Probably just flaky, ignore it"

**Prevention:**
1. **Explicit synchronization** — Use events, barriers, explicit waits (not `time.sleep()`)
2. **Mock external dependencies** — APIs, databases, file systems, time
3. **Unique resource names** — UUID-based test data, include worker ID in parallel tests
4. **Transaction rollback** — Use db_session fixtures with automatic cleanup
5. **Avoid global state** — Reset state in autouse fixtures
6. **Order independence** — Each test sets up its own data
7. **Fix root cause** — Don't just add `@pytest.mark.flaky` as permanent workaround

**Detection:**
- Test passes locally, fails in CI (environment differences)
- Test passes alone, fails in suite (shared state)
- Intermittent failures (passes 9/10 times)
- Test fails in parallel, passes sequentially (resource conflicts)
- Random failures (time dependencies, randomness)

**Phase to address:**
**Phase 250 (All Test Fixes)** — Fix flaky tests before expanding coverage. Use existing FLAKY_TEST_GUIDE.md patterns. Establish "no permanent flaky markers" policy.

**Sources:**
- [Flaky Test Guide](/backend/tests/docs/FLAKY_TEST_GUIDE.md) — HIGH confidence (923 lines, comprehensive patterns)
- [Atom v10.0 Audit](/.planning/MILESTONE-v10.0-AUDIT.md) — HIGH confidence (flaky test issues documented)

---

### Pitfall 6: Frontend Test Suite Health Blocking Coverage

**What goes wrong:** Failing frontend tests block coverage measurement, making it impossible to assess current state or measure progress.

**Why it happens:**
- Tests written without proper maintenance
- Component updates break tests
- Mock inconsistencies (MSW handlers outdated)
- Test dependencies not updated (React Testing Library, Jest versions)
- Async timing issues (waitFor, act() wrappers)

**Evidence from Atom:**
- v10.0 audit: 1,504 failing frontend tests (28.8% failure rate)
- Frontend coverage 14.61% but measurement blocked by test failures
- Cannot assess actual coverage or track progress until tests fixed
- MSW handlers: 30+ services organized but may be outdated

**Consequences:**
- **Coverage measurement blocked** — Cannot determine baseline or progress
- **False confidence** — Team doesn't know actual coverage
- **Wasted effort** — Adding tests when existing tests broken
- **Milestone delays** — Cannot verify coverage targets

**Prevention:**
1. **Fix test suite first** — Address all failing tests before adding coverage
2. **Regular test maintenance** — Update tests with component changes
3. **Mock validation** — Ensure MSW handlers match current API contracts
4. **Dependency updates** — Keep test libraries in sync with production
5. **Test health monitoring** — Track pass rate, flaky test rate, execution time
6. **Async best practices** — Use waitFor, act() wrappers properly

**Detection:**
- Test failure rate >5%
- Coverage measurement fails or produces inconsistent results
- Tests skipped due to known failures
- CI passes but coverage reports incomplete
- `npm test` exits with non-zero code

**Phase to address:**
**Phase 250 (All Test Fixes)** — MUST fix 1,504 failing frontend tests before Phase 254-256 (Frontend Coverage). Cannot measure coverage without passing test suite.

**Sources:**
- [Atom v10.0 Audit](/.planning/MILESTONE-v10.0-AUDIT.md) — HIGH confidence (documented)
- [Frontend Coverage Guide](/frontend-nextjs/docs/FRONTEND_COVERAGE.md) — HIGH confidence (strategies documented)

---

### Pitfall 7: Unrealistic Coverage Targets

**What goes wrong:** Setting 80% coverage targets without considering codebase constraints leads to missed milestones and morale issues.

**Why it happens:**
- Industry benchmarks (80% is "standard")
- Leadership mandates without technical input
- Failure to account for existing technical debt
- Not considering code complexity and dependencies
- Greenfield expectations applied to brownfield codebase

**Evidence from Atom:**
- v10.0 targeted 80% coverage
- Achieved: 18.25% backend, 14.61% frontend
- Gap: 61.75pp backend, 65.39pp frontend
- Timeline: 12 days actual vs 1 week planned (2x overrun)
- Result: Milestone complete "with documented gaps"

**Consequences:**
- **Missed milestones** — Targets not achieved despite best effort
- **Morale impact** — Team feels failure despite significant progress
- **Poor planning** — Future milestones based on unrealistic assumptions
- **Technical debt accumulation** — Rush to meet target leads to brittle tests
- **Credibility loss** — Management loses trust in engineering estimates

**Prevention:**
1. **Pragmatic targets** — Use 70% instead of 80% for v11.0 (based on v10.0 experience)
2. **Incremental approach** — 60% → 70% → 80% progressive rollout
3. **Baseline measurement** — Understand starting point before setting targets
4. **High-impact focus** — Prioritize critical files over blanket percentage
5. **Timeline reality** — Plan based on actual velocity, not wishful thinking
6. **Brownfield adjustments** — Existing code harder to test than new code

**Detection:**
- Milestone targets consistently missed
- Coverage plateaus despite effort
- Team burnout from chasing unrealistic numbers
- Quality sacrificed for quantity
- Estimates consistently wrong (2x+ overruns)

**Phase to address:**
**v11.0 Planning** — Set pragmatic 70% targets based on v10.0 lessons. Use progressive rollout (70% → 75% → 80%) with timeline based on actual velocity from high-impact file testing.

**Sources:**
- [Atom v10.0 Audit](/.planning/MILESTONE-v10.0-AUDIT.md) — HIGH confidence (documented)
- [Atom v10.0 Completion Summary](/.planning/v10.0-COMPLETION-SUMMARY.md) — HIGH confidence (lessons learned)

---

## Moderate Pitfalls

### Pitfall 8: Coverage Without Quality (Assertion-Free Testing)

**What goes wrong:** Tests execute code but don't verify behavior, creating high coverage with zero quality assurance.

**Why it happens:**
- Pressure to hit coverage targets
- Tests written without proper assertions
- "AssertionFreeTesting" — code runs but no verification
- Developers focus on "making tests green" not "finding bugs"

**Consequences:**
- High coverage percentage but production bugs persist
- Tests provide false confidence
- Mutation testing would fail (mutants not killed)
- Coverage tools show 80%+ but tests catch nothing

**Prevention:**
1. **Require meaningful assertions** — Every test must verify expected behavior
2. **Mutation testing** — Verify tests catch bugs, not just execute code (consider for critical paths)
3. **Code review test quality** — Review tests for assertions, not just coverage
4. **Test effectiveness metrics** — Track bug detection rate, not just coverage
5. **Ban assertion-free tests** — Linter or pre-commit hook to catch tests without assertions

**Detection:**
- Tests have no assertions or trivial assertions (`assert True`)
- High coverage but low bug detection
- Code review shows tests without verification
- "All tests pass but we still have bugs"

**Phase to address:**
**Phase 258 (Quality Gates)** — Add quality checks to CI: require assertions in tests, flag assertion-free tests in PR reviews. Phase 252 (Property Tests) helps by requiring invariant verification.

**Sources:**
- [Martin Fowler: Test Coverage](https://martinfowler.com/bliki/TestCoverage.html) — HIGH confidence (official source)

---

### Pitfall 9: Over-Mocking vs. Under-Mocking

**What goes wrong:** Tests either mock too much (brittle, coupled) or too little (slow, unreliable), missing the balance between isolation and realism.

**Over-mocking:**
- **Symptom:** Tests require 5+ mock setups for simple operations
- **Problem:** Brittle tests that break on refactoring; tests fake code they should verify
- **Smell:** Chained mocking (`a.getB().getC().getValue()`)
- **Fix:** Use real objects for simple dependencies; mock only external systems

**Under-mocking:**
- **Symptom:** Tests hit databases, filesystems, or network
- **Problem:** Slow, unreliable tests with external dependencies
- **Smell:** Tests take >1 second for unit tests
- **Fix:** Mock databases, APIs, file systems for unit tests

**Evidence from Atom:**
- v10.0 Phase 101: 66 tests affected by mock vs float comparison errors
- expo-sharing mock inconsistencies
- MMKV getString mock issues
- Canvas tests over-mocked (brittle)

**Consequences:**
- Over-mocking: Brittle tests, refactoring resistance, false confidence
- Under-mocking: Slow tests, external dependencies, flaky failures

**Prevention:**
1. **Mock only external dependencies** — Databases, APIs, file systems, time
2. **Use real objects for simple dependencies** — DTOs, entities, value objects
3. **Integration tests for complex interactions** — Don't mock everything
4. **Test pyramid guidance** — More unit tests (with mocks), fewer E2E (with real systems)

**Detection:**
- Over-mocking: Test setup is longer than test code; tests break on refactoring
- Under-mocking: Unit tests take seconds; tests fail due to network/database issues

**Phase to address:**
**Phase 250 (All Test Fixes)** — Fix mock inconsistencies documented in v10.0. Establish guidelines: mock external dependencies (APIs, databases), use real objects for domain logic.

**Sources:**
- [Backend Testing Guide](/backend/tests/TESTING_GUIDE.md) — HIGH confidence (patterns documented)
- [Atom v10.0 Audit](/.planning/MILESTONE-v10.0-AUDIT.md) — HIGH confidence (mock issues documented)

---

### Pitfall 10: Testing Trivial Code

**What goes wrong:** Teams waste effort testing auto-generated code, constants, and simple getters/setters to inflate coverage numbers.

**Why it happens:**
- Path of least resistance to hit coverage targets
- Tools flag uncovered lines as "problems"
- Lack of understanding of what's valuable to test
- Coverage tools don't distinguish between critical and trivial code

**Consequences:**
- **Diminishing returns:** Effort spent on trivial code instead of complex logic
- **Coverage gaming:** High percentage with low value
- **Maintenance burden:** Tests break when trivial code changes (e.g., property renamed)

**Prevention:**
1. **Focus on complex business logic** — Prioritize testing decision points, algorithms, error paths
2. **Ignore generated code** — Don't test auto-generated getters, constructors, constants
3. **Risk-based testing** — Test what's most likely to break or cause damage
4. **Coverage exclusions** — Configure tools to exclude trivial code from coverage calculations
5. **High-impact file prioritization** — Files >200 lines with <10% coverage first

**Detection:**
- Tests for simple getters/setters outnumber tests for business logic
- High coverage but low cyclomatic complexity coverage
- Time spent writing tests for trivial code > time for complex code

**Phase to address:**
**Phase 251-253 (Backend Coverage)** — Implement weighted coverage that down-weights or excludes trivial code. Focus coverage efforts on high-risk components (agent governance, LLM routing, episodic memory) not DTOs and constants.

**Sources:**
- [Martin Fowler: Test Coverage](https://martinfowler.com/bliki/TestCoverage.html) — HIGH confidence (official source)

---

## Minor Pitfalls

### Pitfall 11: Test Maintenance Burden

**What goes wrong:** Tests become harder to maintain than production code, slowing development velocity.

**Why it happens:**
- Test duplication across files
- Brittle tests over-coupled to implementation
- No test refactoring (tests treated as immutable)
- Test utilities/fixtures become complex

**Consequences:**
- **"Excessively long changes to tests"** for simple code changes (Fowler)
- Developers delete tests to reduce maintenance burden
- Test suite becomes legacy code

**Prevention:**
1. **Refactor tests** — Apply same cleanup practices to tests as production code
2. **Test utilities** — Extract common setup into shared fixtures (but avoid over-abstraction)
3. **Page Object Model** — For UI tests, separate test logic from page structure
4. **Test data builders** — Use test factories instead of hardcoded data

**Detection:**
- Test files larger than production files
- Test setup > test assertions
- Fear of changing tests

**Phase to address:**
**All phases** — Treat tests as production code. Refactor duplicates during Phase 250. Establish test maintenance as ongoing practice, not one-time effort.

**Sources:**
- [Martin Fowler: Test Coverage](https://martinfowler.com/bliki/TestCoverage.html) — HIGH confidence (official source)

---

### Pitfall 12: Ignoring Edge Cases

**What goes wrong:** Tests cover happy paths but miss edge cases, error conditions, and boundary values — exactly where bugs live.

**Why it happens:**
- Focus on "making it work" not "breaking it"
- Time pressure to ship features
- Edge cases harder to identify than main flows
- Coverage tools don't distinguish edge cases from main paths

**Consequences:**
- High coverage but production bugs from untested scenarios
- **"I rarely get bugs that escape into production"** — Fowler's test sufficiency criteria #1
- Tests verify functionality, not robustness

**Prevention:**
1. **Test checklist** — Standard edge cases: null/empty, boundary values, error paths
2. **Property-based testing** — Generate random inputs to find edge cases
3. **Error scenarios** — Test what happens when dependencies fail
4. **Boundary analysis** — Test limits (0, 1, max, max+1)

**Detection:**
- All tests pass with valid inputs but fail with edge cases
- No tests for error paths or exception handling
- Missing null/empty checks in tests

**Phase to address:**
**All phases** — Edge case testing is fundamental to quality. Require edge cases in test definitions during Phase 251 (high-impact file prioritization).

**Sources:**
- [Martin Fowler: Test Coverage](https://martinfowler.com/bliki/TestCoverage.html) — HIGH confidence (official source)

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| **Phase 250: Frontend Test Fixes** | Rushing to add tests without fixing 1,504 failing tests | Fix test suite health FIRST; cannot measure coverage with 28.8% failure rate |
| **Phase 251-253: Backend Coverage** | Coverage gaming (testing DTOs, constants) | Focus on high-impact files (>200 lines, <10% coverage); governance, LLM, episodes first |
| **Phase 254-256: Frontend Coverage** | Test suite blocks measurement | Ensure 100% pass rate before coverage expansion; MSW handlers must be current |
| **Parallel Execution** | CI performance degradation as tests grow | Maintain <15 min feedback; use pytest-xdist, Jest worker farms; monitor execution time |
| **Quality Gates (258)** | Enforcement without quality checks | Require assertions, not just coverage; mutation testing for critical paths |
| **Coverage Measurement** | Service-level aggregation errors | Always use actual line coverage; validate coverage.json has `files` array |
| **Test Infrastructure** | Mock inconsistencies across platforms | Standardize mock factories; validate MSW handlers; use unique_resource_name |
| **Flaky Tests** | Eroding confidence, masking real bugs | Fix root causes; don't use @pytest.mark.flaky as permanent workaround |
| **Frontend Async Tests** | waitFor timing issues, act() wrapper missing | Use React Testing Library patterns; waitFor for async operations |
| **Property Tests (252)** | max_examples set too high (slow) | Use 50 for IO-bound, 100 for standard, 200 for critical invariants |

---

## Roadmap Implications

Based on research pitfalls and v10.0 audit findings, the coverage expansion phases should:

1. **Start with test suite health** — Fix 1,504 failing frontend tests before adding coverage (Phase 250)
2. **Use correct measurement methodology** — Always actual line coverage, never service-level estimates (Phase 251)
3. **Focus on high-impact files** — Files >200 lines with <10% coverage, not trivial code (Phases 251-253)
4. **Implement quality gates** — Require meaningful assertions, not just coverage percentage (Phase 258)
5. **Monitor test suite health** — Track pass rate, flaky test rate, execution time alongside coverage
6. **Use pragmatic targets** — 70% based on v10.0 experience, not 80% (all phases)

### Warning Signs to Monitor

| Warning Sign | Indicates | Action |
|--------------|-----------|--------|
| Coverage increases but bug rate doesn't change | Coverage gaming (Pitfall 1) | Audit test quality; focus on critical paths |
| Tests break during refactoring (behavior unchanged) | Brittle tests (Pitfall 2) | Review test coupling; test behavior not implementation |
| Pipeline time increases linearly with test count | CI degradation (Pitfall 3) | Implement parallelization; smart test selection |
| coverage.json missing `files` array | Measurement error (Pitfall 4) | Use actual line coverage; validate structure |
| Tests pass/fail non-deterministically | Flaky tests (Pitfall 5) | Fix root cause; don't just add retries |
| Test failure rate >5% | Test suite health (Pitfall 6) | Fix failing tests before adding coverage |
| Milestone targets consistently missed | Unrealistic targets (Pitfall 7) | Use pragmatic 70% target; incremental approach |
| High coverage but low confidence in changes | Coverage without quality (Pitfall 8) | Add mutation testing; review test assertions |
| Test setup > test assertions | Over-mocking (Pitfall 9) | Mock only external dependencies |
| Tests for DTOs outnumber business logic tests | Testing trivial code (Pitfall 10) | Focus on high-impact files |
| Test files larger than production files | Maintenance burden (Pitfall 11) | Refactor tests; extract utilities |
| All tests pass with valid inputs but fail with edge cases | Ignoring edge cases (Pitfall 12) | Add edge case tests; use property-based testing |

### Integration with v11.0 Strategy

**Frontend-First Approach:**
1. Phase 250: Fix 1,504 failing tests (unblock coverage measurement)
2. Phase 254-256: Frontend coverage expansion (14.61% → 70%)
3. Parallel backend coverage expansion (18.25% → 70%)

**High-Impact Prioritization:**
1. Identify files >200 lines with <10% coverage
2. Prioritize: Agent governance, LLM routing, episodic memory (critical business logic)
3. Defer: DTOs, constants, utilities (trivial code)

**Quality Maintenance:**
1. Flaky test detection and quarantine (infrastructure exists)
2. Parallel execution maintenance (<15 min feedback target)
3. Mutation testing for critical paths (governance, security, data integrity)

**Pragmatic Targets:**
1. 70% backend coverage (from 18.25%, +51.75pp)
2. 70% frontend coverage (from 14.61%, +55.39pp)
3. 100% test pass rate maintained throughout
4. Timeline: 4-6 weeks (based on v10.0 velocity)

---

## Sources

| Source | Confidence | Notes |
|--------|------------|-------|
| [Martin Fowler: Test Coverage](https://martinfowler.com/bliki/TestCoverage.html) | HIGH | Authoritative, current perspective on coverage pitfalls |
| [Google Testing Blog: Just Say No to More End-to-End Tests](https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html) | HIGH | Official guidance on test pyramid and CI performance |
| [Atom v10.0 Audit](/.planning/MILESTONE-v10.0-AUDIT.md) | HIGH | Documented evidence of pitfalls (mock issues, measurement errors, unrealistic targets) |
| [Backend Coverage Guide](/backend/docs/COVERAGE_GUIDE.md) | HIGH | Methodology documentation for actual line coverage vs service-level estimates |
| [Frontend Coverage Guide](/frontend-nextjs/docs/FRONTEND_COVERAGE.md) | HIGH | Frontend testing patterns and CI/CD integration |
| [Flaky Test Guide](/backend/tests/docs/FLAKY_TEST_GUIDE.md) | HIGH | Comprehensive flaky test prevention and detection patterns (923 lines) |
| [Atom PROJECT.md](/.planning/PROJECT.md) | HIGH | v10.0 lessons learned, current coverage status |
| [pytest Documentation](https://docs.pytest.org/) | HIGH | Fixture patterns, async testing, parallelization |
| [Jest Documentation](https://jestjs.io/) | HIGH | Frontend testing patterns, worker farms |
| [React Testing Library](https://testing-library.com/react) | HIGH | Frontend testing best practices |

**Overall Assessment:** Core findings backed by authoritative sources (Fowler, Google) and documented evidence from Atom's v10.0 milestone. Specific anti-patterns and implementation details validated against project documentation, audit reports, and existing testing guides (923-line flaky test guide, comprehensive coverage guides).

---

## Key Takeaways for Atom v11.0

Given Atom's context (AI automation platform, 18.25% backend coverage, 14.61% frontend coverage, 1,504 failing frontend tests):

1. **Fix test suite health FIRST** — Cannot measure coverage with 28.8% test failure rate
2. **Focus on high-impact files** — Governance, LLM routing, episodic memory (>200 lines, <10% coverage)
3. **Use actual line coverage** — Never service-level estimates (v10.0 showed 66.1pp gap)
4. **Maintain parallel execution** — Keep <15 min feedback as test suite grows
5. **Quality over quantity** — Meaningful assertions, not just coverage percentage
6. **Pragmatic targets** — 70% based on v10.0 experience, not 80%
7. **Fix flaky tests** — Don't use @pytest.mark.flaky as permanent workaround
8. **Mock only external dependencies** — Use real objects for domain logic

**Specific recommendation:** Start with Phase 250 (fix 1,504 failing frontend tests), then focus on high-impact backend files (governance, LLM, episodes) before tackling utilities and DTOs. Use weighted coverage targets to prioritize critical business logic over trivial code.

---

*Domain Pitfalls Research for: Test Coverage Expansion for Existing Codebases*
*Researched: April 13, 2026*
*Confidence: HIGH*
*Context: Atom v11.0 Coverage Completion Milestone*
