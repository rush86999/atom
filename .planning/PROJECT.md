# Atom Test Coverage Initiative

## Current Milestone: Post-v4.0 Planning

**Status:** v4.0 Platform Integration & Property Testing SHIPPED (2026-02-27)
**Next:** Planning next milestone - questioning → research → requirements → roadmap

---

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

**v3.2 Bug Finding & Coverage Expansion (2026-02-26):**
- ✓ Coverage Analysis & Prioritization — Coverage reports, high-impact file identification, gap mapping — v3.2
- ✓ Core Services Unit Testing — Governance, episodes, canvas, browser, training, graduation (28+ tests) — v3.2
- ✓ Database & Integration Testing — Models, migrations, transactions, critical paths (135 tests) — v3.2
- ✓ Property-Based Testing — Core services, database, auth invariants (70+ property tests) — v3.2
- ✓ Bug Discovery — Error paths, boundaries, concurrent operations, failure modes, security (500+ tests) — v3.2
- ✓ Quality Gates & CI/CD — Coverage enforcement (80%), pass rate (98%), trend tracking, documentation — v3.2

**v3.3 Finance Testing & Bug Fixes (2026-02-25):**
- ✓ Core Accounting Logic — Decimal precision, double-entry validation, financial invariants (48 tests) — v3.3
- ✓ Payment Integrations — Mock servers, webhooks, idempotency, race conditions, payment flows (117 tests) — v3.3
- ✓ Cost Tracking & Budgets — Enforcement, attribution, leak detection, guardrails, concurrent safety (197 tests) — v3.3
- ✓ Audit Trails & Compliance — Transaction logging, chronological integrity, immutability, SOX compliance (22 tests) — v3.3
- ✓ Finance Bug Fixes — 5 bugs documented and fixed (FINANCE_BUG_FIXES.md) — v3.3

**v4.0 Platform Integration & Property Testing (2026-02-27):** ✅ SHIPPED
- ✓ Frontend testing (Next.js) — 528 tests (241 integration + 28 property + 27 validation + 32 component), 100% pass rate
- ✓ Mobile testing (React Native) — 320 tests (82 device features + 44 offline sync + 13 property + 55 cross-platform + 126 other)
- ✓ Desktop app testing (Tauri) — 90 tests (54 integration + 36 property), Rust proptest + FastCheck
- ✓ Property testing expansion — 361 total properties (84 frontend + 43 mobile + 53 desktop), 12x 30+ target
- ✓ Infrastructure reliability — 4-platform coverage aggregation, 6 CI workflows, Lighthouse CI, Percy visual regression

**Existing tested capabilities:**
- ✓ Property-based testing framework established (Hypothesis) — existing
- ✓ Integration test infrastructure in place — existing
- ✓ Browser automation tests (17 tests) — existing
- ✓ Governance performance tests — existing
- ✓ Trigger interceptor tests (11 tests) — existing
- ✓ Episode segmentation tests — existing

### Active

*Next milestone planning in progress. Run `/gsd:new-milestone` to define v5.0 scope.*

### Out of Scope

<!-- Explicit boundaries -->
- **New feature development** — This milestone focuses on testing existing features, not building new ones
- **Production deployment** — Infrastructure setup and deployment automation (separate initiative)

## Context

**Current State (v4.0 SHIPPED 2026-02-27):**
- ✅ 1,642 total tests passing (100% pass rate)
- ✅ 361 property tests across all platforms (12x 30+ target)
- ✅ 4-platform coverage aggregation operational (pytest, Jest, jest-expo, tarpaulin)
- ✅ 6 CI workflows (frontend-tests, mobile-tests, desktop-tests, unified, lighthouse-ci, visual-regression)
- ✅ Performance regression testing with Lighthouse CI (5 budgets enforced)
- ✅ Visual regression testing with Percy (5 pages × 3 widths)
- ✅ E2E test orchestration across web (Playwright), mobile (API-level), desktop (Tauri)

**Test Framework:**
- pytest 7.4+ with async support
- Hypothesis 6.151.5 for property-based testing (backend)
- FastCheck 4.5.3 for property-based testing (frontend/mobile)
- proptest 1.0+ for property-based testing (desktop Rust)
- pytest-cov for coverage reporting
- Coverage reports in `backend/tests/coverage_reports/`

**Coverage (v4.0 final):**
- Backend: 21.67%
- Frontend: 3.45%
- Mobile: 16.16%
- Desktop: TBD (requires x86_64 for tarpaulin)
- Overall: 20.81%

**Technical Debt (post-v4.0):**
- Detox mobile E2E testing deferred (expo-dev-client requirement)
- tauri-driver desktop E2E testing deferred (unavailable)
- Overall coverage below 80% target (infrastructure operational, expansion deferred)

## Constraints

- **Timeline**: 1-2 weeks for aggressive coverage push
- **Test Types**: Property-based, fuzzy, integration (no E2E/load/chaos yet)
- **Priority**: Critical paths first (governance, security, agents)
- **Scope**: Full codebase (backend, mobile, desktop, menu bar)
- **Performance**: Tests must run quickly (<5 min for full suite preferred)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|--------|
| Focus on critical paths first | Limited timeline (1-2 weeks), ensure highest impact | — Pending |
| Property-based tests for invariants | Catches edge cases unit tests miss, Hypothesis already installed | — Pending |
| Expand existing infrastructure | Test framework already in place, faster than building new | — Pending |
| Parallel test execution | Use pytest-xdist for speed (1-2 week timeline requires efficiency) | — Pending |
| Strategic max_examples (not 1000) | Research shows 1000 examples takes ~10 hours vs 30 min for 50 | **Adopted** (Phase 2) |
| max_examples=200 for critical invariants | Financial, security, data loss invariants need more coverage | **Adopted** (Phase 2) |
| max_examples=100 for standard invariants | Business logic, validation tests need moderate coverage | **Adopted** (Phase 2) |
| max_examples=50 for IO-bound tests | API, database tests bounded by IO, not example count | **Adopted** (Phase 2) |
| VALIDATED_BUG docstring pattern | Document bug-finding evidence per QUAL-05 requirement | **Adopted** (Phase 2) |
| INVARIANTS.md external documentation | Document invariants separately from tests per DOCS-02 | **Adopted** (Phase 2) |
| Comprehensive testing for AI-generated code | Research shows AI "writes like" experts but doesn't "think like" experts (pattern-matching vs genuine reasoning) | **Adopted** (Phase 90) |
| Hybrid AI-human validation workflow | 40% productivity boost requires expert validation; quality gates enforce 80% coverage, 98% pass rate | **Adopted** (Phase 90) |
| Property tests for AI pattern-matching failures | Chain-of-thought prompting has reliability limits; property tests catch semantic errors AI misses | **Adopted** (Phases 86-87) |

**Strategic max_examples Decision:**
Research revealed that increasing max_examples from 50 to 1000 would increase execution time from ~30 minutes to ~10 hours. The diminishing returns analysis shows that 50-100 examples capture 95%+ of bugs for most properties. The adopted strategy:
- **200 examples**: Critical invariants (financial calculations, security validation, data loss prevention)
- **100 examples**: Standard invariants (business logic, validation rules, caching)
- **50 examples**: IO-bound tests (API endpoints, database queries, file operations)
- **Priority 1**: Add bug-finding evidence documentation (QUAL-05) before increasing examples
- **Priority 2**: Create external invariant documentation (DOCS-02) for traceability

---
*Last updated: 2026-02-27 after Milestone v4.0 Platform Integration & Property Testing*
