# Quality Assurance Guide

**Last Updated:** 2026-04-12
**Status:** Production Ready

---

## Overview

This guide provides a comprehensive overview of quality assurance (QA) practices at Atom, including quality gates, metrics, standards, and workflows. QA ensures that code meets high standards for reliability, maintainability, and performance.

---

## QA Philosophy

**Core Principles:**

1. **Quality is Everyone's Responsibility**
   - Developers write tests
   - Reviewers check quality
   - Automation enforces standards

2. **Test-Driven Development (TDD)**
   - Red: Write failing test
   - Green: Make test pass
   - Refactor: Improve code

3. **Continuous Improvement**
   - Measure everything
   - Track trends
   - Fix root causes

4. **Automation First**
   - Automated tests
   - Automated gates
   - Automated metrics

---

## Quality Standards

### Code Coverage Standards

| Component | Baseline | Current | Target | Status |
|-----------|----------|---------|--------|--------|
| **Backend** | 4.60% | 4.60% | 80% | 🚧 |
| **Frontend** | 14.12% | 14.12% | 80% | 🚧 |

**Progressive Targets:**
- Phase 1: 70% coverage (warn if below)
- Phase 2: 75% coverage (block if below)
- Phase 3: 80% coverage (block if below)

### Test Quality Standards

**Pass Rate:** 100% required
- Zero tolerance for test failures
- All tests must pass before merge
- Flaky tests must be fixed

**Test Types:**
- **Unit Tests:** Fast, isolated, specific
- **Integration Tests:** Component interactions
- **E2E Tests:** Full user workflows
- **Property Tests:** Invariant validation

**Test Coverage:**
- Critical paths: 100% required
- Error handling: 90%+ required
- Edge cases: 80%+ required

### Code Quality Standards

**Complexity Limits:**
- Cyclomatic complexity: <10 per function
- Nesting depth: <4 levels
- Function length: <50 lines
- File length: <500 lines

**Code Review:**
- All code requires review
- At least one approval required
- Automated checks must pass

**Documentation:**
- Public APIs: Documented
- Complex logic: Commented
- Breaking changes: Noted in CHANGELOG

---

## Quality Gates

### Automated Quality Gates

**Configuration:** `.github/workflows/quality-gate.yml`

**Gate 1: Test Pass Rate**
```yaml
# 100% pass rate required
if: tests.failed > 0
then: block_merge
```

**Gate 2: Coverage Threshold**
```yaml
# 70% coverage required (Phase 1)
if: coverage < 70%
then: block_merge
```

**Gate 3: Build Success**
```yaml
# Build must succeed
if: build.status != "success"
then: block_merge
```

### Manual Quality Gates

**Code Review Checklist:**
- [ ] Tests added for new code
- [ ] Coverage not decreased
- [ ] No test failures
- [ ] Code follows patterns
- [ ] Documentation updated
- [ ] No breaking changes (or documented)

**PR Requirements:**
- Descriptive title
- Clear description
- Link to issue (if applicable)
- Tests passing
- Coverage adequate
- Review approved

---

## Quality Metrics

### Dashboard

**Access:** `backend/docs/QUALITY_DASHBOARD.md`

**Metrics Tracked:**
1. **Coverage Percentage**
   - Backend line coverage
   - Frontend line coverage
   - Component breakdown

2. **Test Pass Rate**
   - Backend pass rate
   - Frontend pass rate
   - Test failure trends

3. **Test Count**
   - Total tests
   - By type (unit/integration/E2E)
   - Growth over time

4. **Trends**
   - Coverage improvement
   - Pass rate stability
   - Test growth rate

### Historical Data

**Storage:** `tests/coverage_reports/metrics/quality_metrics.json`

**Retention:** 90 days

**Updates:**
- Automatic: Daily at 00:00 UTC
- On push: Every commit to main
- On PR: Every pull request
- Manual: `python3 .github/scripts/calculate-quality-metrics.py`

---

## QA Workflows

### Bug Fix Workflow

**Process:** See `docs/BUG_FIX_PROCESS.md`

**Summary:**
1. Red: Write failing test
2. Green: Make test pass
3. Refactor: Improve code
4. Verify: All tests pass
5. Merge: With review approval

**Quality Gates:**
- Test must fail before fix
- Test must pass after fix
- Coverage must not decrease
- No regressions introduced

### Feature Development Workflow

**Process:**

1. **Design Phase**
   - Write specification
   - Define acceptance criteria
   - Plan tests

2. **TDD Phase**
   - Write test for API
   - Implement minimal code
   - Refactor for quality

3. **Integration Phase**
   - Add integration tests
   - Test with dependencies
   - Verify end-to-end

4. **Review Phase**
   - Code review
   - Quality gate check
   - Documentation review

5. **Merge Phase**
   - All gates passed
   - Review approved
   - Merge to main

### Release Workflow

**Process:**

1. **Pre-Release**
   - Full test suite passes
   - Coverage meets target
   - No critical bugs

2. **Quality Check**
   - Run quality metrics
   - Verify trends positive
   - Check dashboard

3. **Release**
   - Tag version
   - Generate release notes
   - Deploy to staging

4. **Post-Release**
   - Monitor for issues
   - Track metrics
   - Fix regressions quickly

---

## Quality Tools

### Testing Tools

**Backend:**
- **pytest:** Test framework
- **pytest-cov:** Coverage measurement
- **hypothesis:** Property-based testing
- **pytest-asyncio:** Async test support

**Frontend:**
- **vitest:** Test framework
- **@vitest/coverage:** Coverage measurement
- **testing-library:** Component testing
- **playwright:** E2E testing

### Quality Tools

**Code Quality:**
- **mypy:** Type checking
- **ruff:** Linting
- **black:** Code formatting
- **isort:** Import sorting

**Coverage Tools:**
- **coverage.py:** Backend coverage
- **@vitest/coverage:** Frontend coverage
- **codecov:** Coverage tracking (optional)

**CI/CD Tools:**
- **GitHub Actions:** Quality gates
- **quality-gate.yml:** Gate enforcement
- **quality-metrics.yml:** Metrics collection

---

## QA Best Practices

### For Developers

1. **Write Tests First**
   - Follow TDD red-green-refactor
   - Never commit without tests
   - Aim for high coverage

2. **Keep Tests Fast**
   - Unit tests: <1 second each
   - Integration tests: <5 seconds each
   - E2E tests: <30 seconds each

3. **Make Tests Reliable**
   - No flaky tests
   - Isolated (no dependencies)
   - Deterministic (same result every time)

4. **Review Quality Metrics**
   - Check dashboard regularly
   - Investigate coverage drops
   - Fix test failures immediately

### For Reviewers

1. **Check Test Coverage**
   - New code has tests
   - Coverage not decreased
   - Tests are meaningful

2. **Verify Quality**
   - Code follows patterns
   - No complexity violations
   - Documentation adequate

3. **Run Tests**
   - All tests pass locally
   - CI/CD checks pass
   - No warnings ignored

### For Team Leads

1. **Monitor Metrics**
   - Review quality dashboard
   - Track trends over time
   - Identify areas needing attention

2. **Enforce Standards**
   - Quality gates active
   - Review process followed
   - Documentation maintained

3. **Continuous Improvement**
   - Learn from failures
   - Update practices
   - Share knowledge

---

## Troubleshooting Quality Issues

### Issue: Coverage Decreased

**Diagnosis:**
```bash
# Compare with previous
git diff HEAD~1 tests/coverage_reports/metrics/coverage_latest.json
```

**Solution:**
- Add tests for new code
- Restore deleted tests
- Fix test exclusions

### Issue: Test Failures in CI

**Diagnosis:**
```bash
# Run tests locally
pytest tests/ -v

# Check for environment differences
python3 --version
pip list | grep pytest
```

**Solution:**
- Fix failing tests
- Update dependencies
- Check environment config

### Issue: Quality Gate Blocking

**Diagnosis:**
```bash
# Check gate status
gh run view --log-failed

# Identify which gate failed
# - Coverage threshold?
# - Test pass rate?
# - Build failure?
```

**Solution:**
- Improve coverage
- Fix failing tests
- Resolve build errors

---

## QA Resources

### Documentation

- **Testing Guide:** `TESTING.md`
- **TDD Workflow:** `docs/TDD_WORKFLOW.md`
- **Bug Fix Process:** `docs/BUG_FIX_PROCESS.md`
- **Coverage Guide:** `docs/COVERAGE_REPORT_GUIDE.md`
- **Quality Dashboard:** `docs/QUALITY_DASHBOARD.md`

### Tools and Scripts

- **Quality Gates:** `.github/workflows/quality-gate.yml`
- **Metrics Collection:** `.github/workflows/quality-metrics.yml`
- **Metrics Calculator:** `.github/scripts/calculate-quality-metrics.py`
- **Dashboard Generator:** `.github/scripts/generate-dashboard.py`

### External Resources

- **pytest Documentation:** https://docs.pytest.org/
- **Coverage.py:** https://coverage.readthedocs.io/
- **Hypothesis:** https://hypothesis.works/
- **GitHub Actions:** https://docs.github.com/en/actions

---

## QA Checklist

### Before Committing
- [ ] All tests pass
- [ ] Coverage adequate (≥70%)
- [ ] Code reviewed
- [ ] Documentation updated

### Before Merging
- [ ] CI/CD checks pass
- [ ] Quality gates pass
- [ ] Review approved
- [ ] No conflicts

### After Release
- [ ] Monitor for issues
- [ ] Track metrics
- [ ] Collect feedback
- [ ] Document lessons learned

---

**Quality Assurance Guide Version:** 1.0
**Last Updated:** 2026-04-12
**Maintained By:** Development Team
