# Testing Documentation

Comprehensive testing guides and quality assurance for Atom.

## 📚 Quick Navigation

### E2E Testing ✨ NEW
- **[E2E Testing Guide](E2E_TESTING_PHASE_234.md)** - Complete E2E test infrastructure (91+ tests)
- **[API Testing Guide](API_TESTING_GUIDE.md)** - API testing standards

### Bug Discovery ✨ NEW
- **[Bug Discovery](BUG_DISCOVERY.md)** - Bug discovery guide
- **[Bug Discovery Infrastructure](BUG_DISCOVERY_INFRASTRUCTURE.md)** - AI-enhanced bug discovery

### Bug Fix Process
- **[Bug Fix Process](BUG_FIX_PROCESS.md)** - TDD-based bug fixing workflow

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

### Overall Test Metrics
- **495+ tests** (unit, integration, E2E, bug discovery)
- **99%+ pass rate** (TQ-02 standard)
- **17-27% overall coverage** (expanding to 80%)
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
