# Atom Test Coverage Initiative

## What This Is

A comprehensive testing initiative to achieve 80% code coverage across the Atom AI-powered business automation platform using property-based tests, fuzzy tests, and integration tests. Coverage spans backend services, API routes, mobile app, desktop app, and menu bar components.

## Core Value

**Critical system paths are thoroughly tested and validated before production deployment.**

If everything else fails, the following must have comprehensive test coverage:
- Agent governance and maturity routing
- Security validation and authentication
- Episodic memory system
- Financial and data integrity operations

## Requirements

### Validated

<!-- Existing tested capabilities from codebase analysis -->
- ✓ Property-based testing framework established (Hypothesis) — existing
- ✓ Integration test infrastructure in place — existing
- ✓ Browser automation tests (17 tests) — existing
- ✓ Governance performance tests — existing
- ✓ Trigger interceptor tests (11 tests) — existing
- ✓ Episode segmentation tests — existing

### Active

<!-- Target 80% coverage across all modules -->
- [ ] **80% test coverage** across backend/core/, backend/api/, backend/tools/
- [ ] **Property-based tests** for all system invariants (database transactions, API contracts, state management)
- [ ] **Fuzzy tests** for input validation and security boundaries
- [ ] **Integration tests** for cross-service workflows
- [ ] **Desktop app coverage** for Tauri-based desktop application
- [ ] **Menu bar coverage** for desktop menu bar components
- [ ] **Mobile app coverage** for React Native components
- [ ] **Test documentation** for running and maintaining test suites

### Out of Scope

<!-- Explicit boundaries -->
- **E2E UI testing** — Requires separate tooling (Playwright/Cypress), defer to v2
- **Load testing** — Performance tests beyond coverage, defer to v2
- **Chaos engineering** — Resilience testing, defer to v2
- **Visual regression** — UI snapshot testing, defer to v2

## Context

**Current State (from codebase analysis):**
- Backend has extensive test infrastructure with pytest, pytest-asyncio, Hypothesis
- Property-based testing exists but needs expansion (currently ~28 tests)
- Integration tests present but inconsistent coverage
- Mobile tests structure exists but incomplete implementation
- Desktop/menu bar apps: no dedicated test coverage yet

**Test Framework:**
- pytest 7.4+ with async support
- Hypothesis 6.92+ for property-based testing
- pytest-cov for coverage reporting
- Coverage reports in `backend/tests/coverage_reports/`

**Current Coverage Gaps (from CONCERNS.md):**
- Canvas JavaScript security validation (critical)
- Mobile integration testing (user-facing)
- Large dataset performance testing (scalability)
- Complex service classes (accounting, consolidated modules)

## Constraints

- **Timeline**: 1-2 weeks for aggressive coverage push
- **Test Types**: Property-based, fuzzy, integration (no E2E/load/chaos yet)
- **Priority**: Critical paths first (governance, security, agents)
- **Scope**: Full codebase (backend, mobile, desktop, menu bar)
- **Performance**: Tests must run quickly (<5 min for full suite preferred)

## Key Decisions

| Decision | Rationale | Outcome |
|----------
| Focus on critical paths first | Limited timeline (1-2 weeks), ensure highest impact | — Pending |
| Property-based tests for invariants | Catches edge cases unit tests miss, Hypothesis already installed | — Pending |
| Expand existing infrastructure | Test framework already in place, faster than building new | — Pending |
| Parallel test execution | Use pytest-xdist for speed (1-2 week timeline requires efficiency) | — Pending |

---
*Last updated: 2026-02-10 after initialization*
