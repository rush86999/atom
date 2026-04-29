# Testing Documentation Index

**Purpose:** Quick navigation for testing documentation and workflows
**Last Updated:** April 29, 2026

---

## 🚀 Quick Start

**New to Atom testing?** Start here:
1. **[Bug Fix Process](#bug-fix-process)** - TDD workflow for fixing bugs (READ THIS FIRST)
2. **[Test Patterns](#test-patterns)** - Common testing patterns in Atom
3. **[Phase 299 Summary](#phase-299-coverage-acceleration)** - Recent test infrastructure work

**Looking for something specific?** Use the index below or search by keyword.

---

## 📚 Documentation Index

### Bug Fix Process ⭐ START HERE
- **[Bug Fix Process](BUG_FIX_PROCESS.md)** - TDD-based bug fixing workflow
  - **When to use:** Fixing ANY bug in codebase
  - **What you'll learn:** Red-green-refactor cycle, TDD principles, common patterns
  - **Examples:** Python backend bugs, TypeScript frontend bugs
  - **Time investment:** 15 min to read, saves hours debugging

### Phase Summaries
- **[Phase 299: Frontend Coverage Acceleration](PHASE_299_GAP_CLOSURE_SUMMARY.md)** ⭐ NEW
  - **When to use:** Understanding current test failures, planning fixes
  - **What you'll learn:**
    - Why pass rate is 73.8% (not 95%)
    - Failure categories and counts (Element Not Found: 600-800 tests)
    - Roadmap to 95% pass rate (7-10 hours)
    - Lessons learned from import fixes
  - **Time investment:** 10 min read, saves hours of trial-and-error

### E2E Testing
- **[E2E Testing Guide](E2E_TESTING_PHASE_234.md)** - Complete E2E test infrastructure
  - **486 E2E test functions** across auth and agent workflows
  - **API-first authentication** (10-100x faster than UI login)
  - **Worker-based DB isolation** for parallel execution
  - **Page Object Model** for maintainable abstractions

- **[API Testing Guide](API_TESTING_GUIDE.md)** - API testing standards

### Bug Discovery
- **[Bug Discovery](BUG_DISCOVERY.md)** - Bug discovery guide
- **[Bug Discovery Infrastructure](BUG_DISCOVERY_INFRASTRUCTURE.md)** - AI-enhanced bug discovery

### Coverage & Quality
- **[Coverage Analysis](COVERAGE_ANALYSIS.md)** - Coverage measurement
- **[Coverage Enforcement](COVERAGE_ENFORCEMENT.md)** - Coverage requirements
- **[Coverage Guide](COVERAGE_GUIDE.md)** - Coverage improvement
- **[Coverage Report Guide](COVERAGE_REPORT_GUIDE.md)** - Coverage reporting

## 🧪 Test Suite Summary

### E2E Tests (Phase 234) ✨
- **91+ comprehensive tests** with Playwright Python 1.58.0
- **API-first authentication** (10-100x faster than UI login)
- **Worker-based DB isolation** for parallel execution
- **Page Object Model** for maintainable abstractions

**Coverage**:
- AUTH-01 to AUTH-07: Authentication workflows
- AGNT-01 to AGNT-08: Agent workflows
- Tests complete in under 10 minutes with parallel execution

### Bug Discovery (Phase 237) ✨
- **Automated fuzzing** with atheris (coverage-guided)
- **Mutation testing** with mutmut
- **Property-based testing** with Hypothesis (66+ invariants)
- **Chaos engineering** with locust
- **Automated bug filing** with GitHub Issues API

### Overall Test Metrics (April 29, 2026)
- **Backend:** ~5,000 tests, 99.3% pass rate, 36.7% coverage
- **Frontend:** 5,732 tests, 73.8% pass rate, 18.12% coverage
- **E2E:** 486 tests, 486 test functions, API-first auth
- **Bug Discovery:** 66+ property tests, fuzzing, mutation testing
- **<60min full suite** execution time
- **<30s per test** performance target

## 🚀 Quick Start

### Run E2E Tests
```bash
cd backend/tests/e2e_ui

# Run all E2E tests
pytest backend/tests/e2e_ui/ -v

# Run with 4 parallel workers (10x faster)
pytest backend/tests/e2e_ui/ -v -n 4

# Run specific test
pytest backend/tests/e2e_ui/tests/test_auth_login.py -v
```

### Run Bug Discovery
```bash
# Property-based testing
pytest tests/property/ -v

# Mutation testing
mutmut run --paths-to-mutate backend/core/

# Fuzzing
python tests/fuzzing/test_fuzzing.py
```

### Coverage Report
```bash
# Generate coverage report
pytest tests/ --cov=core --cov-report=html

# View report
open htmlcov/index.html
```

## 📋 Testing Standards

### TQ-01: Test Naming
- Test files: `test_<module>.py`
- Test functions: `test_specific_behavior()`
- Test classes: `Test<ClassName>`

### TQ-02: Pass Rate
- All tests must pass before merge (100% pass rate)
- Flaky tests must be fixed or removed

### TQ-03: Coverage
- New code must have ≥70% coverage
- Critical paths must have ≥90% coverage

### TQ-04: Test Quality
- Tests must be independent (no shared state)
- Tests must be reproducible
- Tests must be fast (<30s per test)

### TQ-05: Documentation
- Complex tests need docstrings
- Test fixtures must be documented

## 📖 Related Documentation

- **[Code Quality](../DEVELOPMENT/code-quality.md)** - Detailed testing standards
- **[Quality Assurance](../../backend/docs/QUALITY_ASSURANCE.md)** - QA practices
- **[Development](../DEVELOPMENT/README.md)** - Development setup

---

*Last Updated: April 12, 2026*
