# Phase 214: Fix Remaining Test Failures - Context

## User Decisions

### Decisions (Locked)
1. **Fix A/B testing route tests** — Implement or register missing `/api/ab-tests/create` and `/api/ab-tests/{test_id}/start` endpoints
2. **Minimal API implementation** — Only implement endpoints needed to make tests pass
3. **Test stability first** — Ensure test suite passes with 0 failures before any other concerns

### Claude's Discretion
- Implementation approach (new routes vs registering existing ones)
- API design details (request/response format, validation)
- Whether to keep A/B testing infrastructure or remove tests

### Deferred Ideas
- Any A/B testing feature work beyond making tests pass
- API documentation for A/B testing endpoints
- Additional A/B testing tests beyond the 10 failing ones
