# Phase 216: Fix Business Facts Test Failures - Context

## User Decisions

### Decisions (Locked)
1. **Fix business facts route tests** — Mock S3/R2 dependencies and PDF extraction service
2. **Minimal production changes** — Prefer test fixture improvements over service changes
3. **Achieve 100% pass rate** — All 10 business facts tests should pass
4. **Document S3/R2 mocking pattern** — Create reusable patterns for future tests

### Claude's Discretion
- Approach for mocking external services (S3, R2, PDF extraction)
- Whether to use integration tests vs improved unit tests
- Test organization (keep in test_admin_business_facts_routes.py or separate)

### Deferred Ideas
- Actual S3/R2 integration setup
- PDF extraction service improvements
- Additional business facts tests beyond fixing failures
