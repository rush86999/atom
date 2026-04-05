# Testing Documentation Index

**Last Updated:** March 7, 2026
**Milestone:** v5.2 Complete Codebase Coverage

Welcome to the central hub for all testing documentation at Atom. This index helps you find relevant documentation based on your goal, platform, or problem.

---

## I'm New Here (Start Here)

### Testing Onboarding Guide (15 min)
→ [TESTING_ONBOARDING.md](TESTING_ONBOARDING.md)

**What you'll learn:**
- How to verify your test setup works
- How to run your first test
- How to write your first test
- Common troubleshooting issues

**Time:** 15 minutes (setup) + 15 minutes (first test)

**Platforms covered:** Backend, Frontend, Mobile, Desktop

---

## I Want to Test [Specific Platform]

Choose your platform to find platform-specific testing guides, frameworks, and patterns.

### Frontend (Next.js/React)

→ [FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md) *(coming soon in Phase 152)*

**Frameworks:** Jest, React Testing Library, MSW, jest-axe
**Target Coverage:** 80%+ across all modules
**Test Count:** 1,753 tests
**Execution Time:** ~3-5 minutes

**Key Files:**
- `frontend-nextjs/jest.config.js` - Jest configuration
- `frontend-nextjs/tests/setup.ts` - Test setup with MSW
- `frontend-nextjs/tests/__mocks__` - Mock modules

**See Also:**
- [Frontend Coverage Guide](../frontend-nextjs/docs/FRONTEND_COVERAGE.md) - Per-module thresholds
- [API Robustness](../frontend-nextjs/docs/API_ROBUSTNESS.md) - MSW patterns

### Mobile (React Native)

→ [MOBILE_TESTING_GUIDE.md](MOBILE_TESTING_GUIDE.md) *(coming soon in Phase 152)*

**Frameworks:** jest-expo, React Native Testing Library
**Target Coverage:** 50%+ across all modules
**Test Count:** 398 tests
**Execution Time:** ~2-3 minutes

**Key Files:**
- `mobile/jest.config.js` - Jest configuration for React Native
- `mobile/tests/setup.js` - Test setup with expo mocks
- `mobile/src/__tests__/` - Test suites

**Platform-Specific Testing:**
- iOS device metrics (iPhone 8, 13 Pro, 14 Pro Max)
- Android navigation modes (gesture vs button)
- SafeAreaContext mocking

### Desktop (Tauri/Rust)

→ [DESKTOP_TESTING_GUIDE.md](DESKTOP_TESTING_GUIDE.md) *(coming soon in Phase 152)*

**Frameworks:** cargo test, proptest, tarpaulin, #[tauri::test]
**Target Coverage:** 40%+ across all modules
**Test Count:** 83 tests
**Execution Time:** ~3-4 minutes

**Key Files:**
- `frontend-nextjs/src-tauri/Cargo.toml` - Rust project configuration
- `frontend-nextjs/src-tauri/tests/` - Test suites
- `frontend-nextjs/src-tauri/tarpaulin.toml` - Coverage configuration

**Platform-Specific Testing:**
- Windows (file dialogs, path handling)
- macOS (menu bar, Touch ID)
- Linux (window managers, system tray)

### Backend (Python/FastAPI)

→ [backend/tests/docs/COVERAGE_GUIDE.md](TESTING_INDEX.md)

**Frameworks:** pytest, Hypothesis, Schemathesis
**Target Coverage:** 70%+ across all modules
**Test Count:** 500+ tests
**Execution Time:** ~8-10 minutes

**Key Files:**
- `backend/pytest.ini` - pytest configuration
- `backend/conftest.py` - Shared fixtures
- `backend/tests/` - Test suites organized by type

**Test Organization:**
- `tests/unit/` - Isolated unit tests
- `tests/integration/` - Service integration tests
- `tests/contract/` - API contract tests
- `tests/e2e_ui/` - Playwright UI tests

---

## I Want to Learn [Specific Technique]

Cross-platform testing techniques that apply to multiple platforms.

### Property Testing

→ [PROPERTY_TESTING_PATTERNS.md](PROPERTY_TESTING_PATTERNS.md)

**What you'll learn:**
- FastCheck (frontend/mobile/desktop) - 32 properties
- Hypothesis (backend) - Property-based testing for Python
- proptest (desktop) - Rust property testing

**Use cases:**
- Testing state machines
- Validating invariants
- Finding edge cases

**Examples:**
- Canvas state machine (FastCheck)
- Workflow engine (Hypothesis)
- File operations (proptest)

### E2E Testing

→ [E2E_TESTING_GUIDE.md](E2E_TESTING_GUIDE.md)

**What you'll learn:**
- Playwright (web) - Browser automation
- API-level tests (mobile) - Bypass Detox limitations
- Tauri integration (desktop) - Full app context

**Test Organization:**
- User flows across platforms
- Cross-platform orchestration
- Parallel execution strategies

### Cross-Platform Coverage

→ [CROSS_PLATFORM_COVERAGE.md](CROSS_PLATFORM_COVERAGE.md)

**What you'll learn:**
- Weighted coverage calculation (40/30/20/10%)
- Platform-specific thresholds
- Quality gates in CI/CD

**Coverage Targets:**
- Backend: ≥70%
- Frontend: ≥80%
- Mobile: ≥50%
- Desktop: ≥40%
- Overall: Weighted score (Platform × Weight)

### API Contract Testing

→ [backend/docs/API_CONTRACT_TESTING.md](../backend/docs/API_CONTRACT_TESTING.md)

**What you'll learn:**
- Schemathesis validation
- OpenAPI spec generation
- Breaking change detection

**Tools:**
- Schemathesis 4.11.0
- openapi-diff
- FastAPI TestClient

---

## I Have [Specific Problem]

Troubleshooting guides for common testing problems.

### Flaky Tests

→ [backend/tests/docs/FLAKY_TEST_QUARANTINE.md](TESTING_INDEX.md)

**Problem:** Tests pass sometimes, fail other times

**What you'll learn:**
- Multi-run detection (10 runs, 30% threshold)
- SQLite quarantine tracking
- Auto-removal policies (7 days, 5 consecutive passes)

**Tools:**
- `flaky_test_detector.py` - Detect flaky tests
- `flaky_test_tracker.py` - Track quarantine status
- `retry_policy.py` - Centralized retry configuration

**CI Integration:**
- 3-run quick detection in CI
- 10-run deep detection nightly
- PR comments with reliability scores (🟢🟡🔴)

### Slow Test Execution

→ [backend/tests/docs/PARALLEL_EXECUTION_GUIDE.md](E2E_TESTING_GUIDE.md)

**Problem:** Tests take too long to run

**What you'll learn:**
- Matrix strategy (4 platforms in parallel)
- Target: <15 min total execution time
- Platform-specific caching (pip, npm, cargo)

**CI/CD Workflow:**
- `unified-tests-parallel.yml` - Parallel execution
- max-parallel: 4 (resource limits)
- fail-fast: false (collect all results)

**Speed Improvements:**
- Backend: pytest-xdist (-n auto)
- Frontend/Mobile: Jest maxWorkers
- Desktop: cargo test --jobs

### Coverage Regression

→ [backend/tests/docs/COVERAGE_TRENDING_GUIDE.md](TESTING_INDEX.md)

**Problem:** Coverage decreased from last build

**What you'll learn:**
- 30-day trending history
- Regression detection (>1% threshold)
- Dashboard visualization

**Tools:**
- `coverage_trend_tracker.py` - Track coverage over time
- `compare_trend_reports.py` - Compare builds
- JSON export for dashboards

**Alerting:**
- PR comments with trend indicators (↑↓)
- Slack notifications on regression
- Monthly reports

### Test Isolation Issues

→ [backend/tests/docs/TEST_ISOLATION_PATTERNS.md](TESTING_INDEX.md)

**Problem:** Tests fail when run together but pass individually

**What you'll learn:**
- Independent tests (no shared state)
- Fixture patterns (pytest fixtures, React Testing Library)
- Resource conflict prevention

**Patterns:**
- Database cleanup (transactions, fixtures)
- Mock isolation (beforeEach, afterEach)
- Async timing (flushPromises, waitFor)

**Anti-Patterns:**
- Shared mutable state
- Global configuration
- Leaking resources

---

## Reference Documentation

Quality standards and reference materials for all platforms.

### Quality Standards

→ [backend/docs/TEST_QUALITY_STANDARDS.md](CODE_QUALITY_GUIDE.md)

**Standards:**
- TQ-01: Test Independence
- TQ-02: Pass Rate Requirements (≥95%)
- TQ-03: Performance Targets

**Enforcement:**
- CI/CD quality gates
- Pre-commit hooks
- Review checklists

### API Testing Guide

→ [backend/docs/API_TESTING_GUIDE.md](../backend/docs/API_TESTING_GUIDE.md)

**Topics:**
- Contract testing with Schemathesis
- Integration testing patterns
- API mocking strategies

---

## Platform-Specific Documentation

Deep dives into each platform's testing infrastructure.

### Frontend Documentation

**Location:** `frontend-nextjs/docs/`

- **[Frontend Coverage](../frontend-nextjs/docs/FRONTEND_COVERAGE.md)** - Per-module coverage breakdown
  - Canvas components: 90% target
  - Integration layer: 85% target
  - Dashboard: 80% target

- **[API Robustness](../frontend-nextjs/docs/API_ROBUSTNESS.md)** - MSW patterns
  - Request/response mocking
  - Error handling
  - Retry logic

### Backend Documentation

**Location:** `backend/tests/docs/`

1. **[COVERAGE_GUIDE.md](TESTING_INDEX.md)** (727 lines)
   - Coverage measurement
   - Gap analysis
   - Priority tiers

2. **[COVERAGE_TRENDING_GUIDE.md](TESTING_INDEX.md)** (759 lines)
   - 30-day trending
   - Regression detection
   - Dashboards

3. **[FLAKY_TEST_GUIDE.md](TESTING_INDEX.md)** (922 lines)
   - Detection strategies
   - Quarantine workflows
   - Fixing strategies

4. **[FLAKY_TEST_QUARANTINE.md](TESTING_INDEX.md)** (590 lines)
   - Multi-run detection
   - SQLite tracking
   - Auto-removal policies

5. **[PARALLEL_EXECUTION_GUIDE.md](E2E_TESTING_GUIDE.md)** (1,519 lines)
   - Matrix execution
   - <15 min feedback
   - Retry workflows

6. **[TEST_ISOLATION_PATTERNS.md](TESTING_INDEX.md)** (961 lines)
   - Independent tests
   - Fixture patterns
   - Resource conflicts

---

## Milestone Documentation

Phase completion reports and overall progress tracking.

### v5.2 Complete Codebase Coverage

**Phases:** 127-152 (Quality Infrastructure)

**Coverage Progress:**
- Backend: 26.15% → 80% (target)
- Frontend: 1.41% → 80%+ (target)
- Mobile: 16.16% → 50%+ (target)
- Desktop: <5% → 40%+ (target)

**Quality Infrastructure:**
- Parallel execution (Phase 149)
- Coverage trending (Phase 150)
- Flaky test quarantine (Phase 151)
- Documentation consolidation (Phase 152)

**Phase Summaries:**
- [Phase 146](../.planning/phases/146-cross-platform-weighted-coverage/146-SUMMARY.md) - Cross-platform coverage
- [Phase 147](../.planning/phases/147-shared-property-tests/147-SUMMARY.md) - Shared property tests
- [Phase 148](../.planning/phases/148-cross-platform-e2e-orchestration/148-SUMMARY.md) - E2E orchestration
- [Phase 149](../.planning/phases/149-quality-infrastructure-parallel/149-SUMMARY.md) - Parallel execution
- [Phase 150](../.planning/phases/150-quality-infrastructure-trending/150-SUMMARY.md) - Coverage trending
- [Phase 151](../.planning/phases/151-quality-infrastructure-reliability/151-SUMMARY.md) - Flaky test quarantine

---

## Quick Reference

### Test Execution Commands

| Platform | Command | Time | Notes |
|----------|---------|------|-------|
| **Backend** | `pytest tests/ -v -n auto` | ~8-10 min | pytest-xdist for parallelization |
| **Frontend** | `npm test -- --watchAll=false` | ~3-5 min | 1,753 tests |
| **Mobile** | `npm test -- --watchAll=false` | ~2-3 min | 398 tests |
| **Desktop** | `cargo test` | ~3-4 min | 83 tests |

**All platforms in parallel:** ~15 minutes (via `unified-tests-parallel.yml`)

### Coverage Commands

| Platform | Command | Output | Location |
|----------|---------|--------|----------|
| **Backend** | `pytest --cov=core --cov=api --cov-report=json` | coverage.json | Backend root |
| **Frontend** | `npm test -- --coverage` | coverage-final.json | `coverage/` directory |
| **Mobile** | `npm test -- --coverage` | coverage-final.json | `coverage/` directory |
| **Desktop** | `cargo tarpaulin --out Json` | tarpaulin-report.json | `coverage/` directory |

### Coverage Targets

| Platform | Target | Current | Gap |
|----------|--------|---------|-----|
| Backend | 70% | 26.15% | -43.85 pp |
| Frontend | 80% | 1.41% | -78.59 pp |
| Mobile | 50% | 16.16% | -33.84 pp |
| Desktop | 40% | <5% | -35+ pp |

**Weighted Overall:** 40% × Backend + 30% × Frontend + 20% × Mobile + 10% × Desktop

### CI/CD Workflows

| Workflow | Purpose | Platforms | Time |
|----------|---------|-----------|------|
| `unified-tests-parallel.yml` | Parallel test execution | All 4 | <15 min |
| `frontend-tests.yml` | Frontend-only tests | Frontend | ~5 min |
| `mobile-tests.yml` | Mobile-only tests | Mobile | ~3 min |
| `desktop-tests.yml` | Desktop-only tests | Desktop | ~4 min |
| `backend-tests.yml` | Backend-only tests | Backend | ~10 min |

---

## Need Help?

### Getting Help

- **Testing questions:** Slack #testing channel
- **Documentation issues:** [Open a docs issue on GitHub](https://github.com/rush86999/atom/issues/new?labels=documentation)
- **Onboarding sessions:** Weekly "Testing at Atom" office hours (Fridays 2-3 PM PT)

### Contributing to Documentation

When updating testing documentation:

1. **Keep it accurate:** Verify all commands work
2. **Keep it current:** Update during phase execution
3. **Keep it linked:** Cross-reference related docs
4. **Keep it simple:** Use progressive disclosure (quick start → deep dive)

### Documentation Maintenance

- **Review cycle:** Quarterly (March, June, September, December)
- **Version tags:** Tag docs with milestone versions (v5.1, v5.2)
- **Stale detection:** Check for broken links, outdated examples
- **Owner:** Testing Infrastructure Team

---

**Index last updated:** March 7, 2026
**Total documentation pages:** 15+ guides across 4 platforms
**Total lines of documentation:** 8,000+ lines

**See also:** [TESTING_ONBOARDING.md](TESTING_ONBOARDING.md) for the 15-minute quick start guide.
