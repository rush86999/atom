# Testing Documentation Index

**Last Updated:** March 7, 2026
**Milestone:** v5.2 Complete Codebase Coverage

---

## I'm New Here (Start Here)

### Testing Onboarding (15 min)
→ [TESTING_ONBOARDING.md](TESTING_ONBOARDING.md) *(to be created in 152-01)*
- Quick start for all platforms
- Run your first test in 15 minutes
- Write your first test in 30 minutes

## I Want to Test [Specific Platform]

### Frontend (Next.js/React)
→ [FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md) - Jest, React Testing Library, MSW, jest-axe patterns, component testing, hook testing, API mocking, accessibility testing (WCAG 2.1 AA), 80%+ coverage target

### Mobile (React Native)
→ [MOBILE_TESTING_GUIDE.md](MOBILE_TESTING_GUIDE.md) - jest-expo, React Native Testing Library, device mocks, platform-specific testing (iOS vs Android), 50%+ coverage target

### Desktop (Tauri/Rust)
→ [DESKTOP_TESTING_GUIDE.md](DESKTOP_TESTING_GUIDE.md) *(to be created in 152-04)*
- cargo test, proptest, tarpaulin
- Target: 40%+ coverage

### Backend (Python/FastAPI)
→ [backend/tests/docs/COVERAGE_GUIDE.md](../backend/tests/docs/COVERAGE_GUIDE.md)
- pytest, Hypothesis, Schemathesis
- Target: 70%+ coverage

## I Want to Learn [Specific Technique]

### Property Testing
→ [PROPERTY_TESTING_PATTERNS.md](PROPERTY_TESTING_PATTERNS.md)
- FastCheck (frontend/mobile/desktop)
- Hypothesis (backend)
- proptest (desktop)

### E2E Testing
→ [E2E_TESTING_GUIDE.md](E2E_TESTING_GUIDE.md)
- Playwright (web)
- API-level tests (mobile)
- Tauri integration (desktop)

### Cross-Platform Coverage
→ [CROSS_PLATFORM_COVERAGE.md](CROSS_PLATFORM_COVERAGE.md)
- Weighted overall score
- Platform minimums
- Quality gates

## I Have [Specific Problem]

### Flaky Tests
→ [backend/tests/docs/FLAKY_TEST_QUARANTINE.md](../backend/tests/docs/FLAKY_TEST_QUARANTINE.md)
- Multi-run detection (10 runs, 30% threshold)
- SQLite tracking with auto-removal
- Fixing strategies

### Slow Test Execution
→ [backend/tests/docs/PARALLEL_EXECUTION_GUIDE.md](../backend/tests/docs/PARALLEL_EXECUTION_GUIDE.md)
- Matrix strategy (4 platforms in parallel)
- Target: <15 min total execution
- Retry workflows

### Coverage Regression
→ [backend/tests/docs/COVERAGE_TRENDING_GUIDE.md](../backend/tests/docs/COVERAGE_TRENDING_GUIDE.md)
- 30-day trending history
- Regression detection (>1% threshold)
- Dashboard visualization

### Test Isolation Issues
→ [backend/tests/docs/TEST_ISOLATION_PATTERNS.md](../backend/tests/docs/TEST_ISOLATION_PATTERNS.md)
- Independent tests (no shared state)
- Fixture patterns
- Resource conflict prevention

## Reference Documentation

### Quality Standards
→ [backend/docs/TEST_QUALITY_STANDARDS.md](../backend/docs/TEST_QUALITY_STANDARDS.md)
- Test independence (TQ-01)
- Pass rate requirements (TQ-02)
- Performance targets (TQ-03)

### API Contract Testing
→ [backend/docs/API_CONTRACT_TESTING.md](../backend/docs/API_CONTRACT_TESTING.md)
- Schemathesis validation
- OpenAPI spec generation
- Breaking change detection

## Platform-Specific Documentation

### Frontend
- [Frontend Coverage](frontend-nextjs/docs/FRONTEND_COVERAGE.md)
- [API Robustness](frontend-nextjs/docs/API_ROBUSTNESS.md)

### Backend
- [Coverage Guide](../backend/tests/docs/COVERAGE_GUIDE.md)
- [Test Quality Standards](../backend/docs/TEST_QUALITY_STANDARDS.md)

## Milestone Documentation

### v5.2 Complete Codebase Coverage
- Phases 127-152 completion reports
- Coverage trends (26.15% → 80% backend, 1.41% → 80%+ frontend)
- Quality infrastructure (parallel execution, trending, flaky test quarantine)

## Quick Reference

### Test Execution Commands

| Platform | Command | Time |
|----------|---------|------|
| Backend | `pytest tests/ -v -n auto` | ~8-10 min |
| Frontend | `npm test -- --watchAll=false` | ~3-5 min |
| Mobile | `npm test -- --watchAll=false` | ~2-3 min |
| Desktop | `cargo test` | ~3-4 min |

### Coverage Commands

| Platform | Command | Output |
|----------|---------|--------|
| Backend | `pytest --cov=core --cov=api --cov-report=json` | coverage.json |
| Frontend | `npm test -- --coverage` | coverage/coverage-final.json |
| Mobile | `npm test -- --coverage` | coverage/coverage-final.json |
| Desktop | `cargo tarpaulin --out Json` | coverage/tarpaulin-report.json |

## Need Help?

- **Testing questions**: Slack #testing channel
- **Documentation issues**: Open docs issue on GitHub
- **Onboarding sessions**: Weekly "Testing at Atom" office hours

---

**Note:** This index is a placeholder created during Phase 152-03. Full index with complete links will be created in Phase 152-01.
