# Phase 215: Fix Remaining A/B Test Failures - Context

## User Decisions

### Decisions (Locked)
1. **Fix database schema issue** — Ensure test database has latest schema or mock database dependencies
2. **Fix test mocking gaps** — Update TestStartTest fixtures to properly mock ABTestingService
3. **Minimize production changes** — Prefer test fixture fixes over production code changes
4. **Achieve 100% test pass rate** — All 10 A/B tests should pass

### Claude's Discretion
- Approach for fixing database schema (migration vs. better mocking)
- Test fixture design patterns (mock service vs. mock database)
- Whether to update all test fixtures or just failing ones

### Deferred Ideas
- Refactoring A/B testing service architecture
- Adding more comprehensive A/B testing tests
- Performance optimizations for A/B testing queries
