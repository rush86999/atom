# Project Research Summary

**Project:** Atom Frontend Testing Coverage Expansion
**Domain:** Multi-platform testing architecture (React/Next.js, React Native, Tauri/Rust, Python)
**Researched:** March 3, 2026
**Confidence:** HIGH

## Executive Summary

Atom requires a unified 4-platform testing architecture to achieve consistent 80%+ coverage across backend (Python 74.6%), frontend (Next.js 89.84%), mobile (React Native 16.16%), and desktop (Tauri TBD). The existing infrastructure is production-ready with `aggregate_coverage.py` handling multi-format coverage aggregation, unified CI workflows, and comprehensive property testing (250+ Hypothesis tests in backend, 84 FastCheck tests in frontend). The recommended approach is **backend-first API contract testing** using OpenAPI as source of truth, followed by **shared test utilities via symlinks**, **platform-weighted coverage quality gates** (backend 70%, frontend 20%, mobile 5%, desktop 5%), and **cross-platform property testing** for state invariants.

Key risks include **platform-specific coverage gaps** (mobile at 16.16% dragging down overall metrics), **floating-point precision errors** in any financial calculations, **inadequate audit trail testing** for compliance, and **test utility duplication** across platforms causing maintenance burden. Mitigation strategies include **minimum per-platform coverage thresholds** (backend ≥70%, frontend ≥80%, mobile ≥50%, desktop ≥40%), **Decimal-first design** for all monetary values, **shared test helpers via symlinks** to ensure consistency, and **property-based testing** for financial invariants (double-entry bookkeeping, conservation of value).

## Key Findings

### Recommended Stack

**Core technologies:**
- **Jest 30.0.5** — Already configured with 80% thresholds, 37% faster than Jest 29, React 19 compatible
- **React Testing Library 16.3** — Current, industry-standard 2025 approach, avoids implementation details
- **FastCheck 4.5.3** — Property-based testing for state invariants, 84 tests already passing
- **@testing-library/react-hooks 8.0.1** — Isolated hook testing for custom hooks not fully covered by component tests
- **jest-axe 8.0.0 + @axe-core/react 4.10.0** — WCAG compliance testing, missing a11y coverage
- **MSW 1.3.5** — Already installed for API mocking, integration test patterns needed
- **WebdriverIO 9.24.0** — Already installed for E2E, use existing infrastructure (skip Cypress)
- **Schemathesis** — OpenAPI contract testing for backend APIs, generate TypeScript types automatically
- **openapi-typescript** — Auto-generate TypeScript types from backend OpenAPI spec for compile-time safety

**What NOT to add:**
- Vitest (Jest 30 is faster, already configured)
- Cypress (WebdriverIO already installed)
- Enzyme (deprecated 2022, React 19 incompatible)
- Visual regression tools (Percy/Chromatic deferred until post-80% coverage)
- XState (defer until state complexity warrants formal state machines)

### Expected Features

**Must have (table stakes):**
- **Leaf component tests** — Button, Input, Card components with render/props/interaction tests
- **Composite component tests** — Forms, modals, tables with data flow and event propagation
- **State management tests** — Redux/Context/hook tests for state transitions and error handling
- **API mocking with MSW** — Integration tests with loading/error/success states
- **Form validation tests** — Required fields, format validation, error messages
- **Hook isolation tests** — Custom hooks tested with renderHook, not just indirectly through components
- **Accessibility tests** — jest-axe for WCAG compliance, keyboard navigation, ARIA attributes
- **Error boundary tests** — Error catching, fallback UI, error logging
- **Routing tests** — Navigation, route parameters, query strings, deep links

**Should have (competitive):**
- **Property-based testing** — FastCheck for state machine invariants, reducer purity, data transformations
- **API contract testing** — OpenAPI spec validation, auto-generated TypeScript types, breaking change detection
- **Cross-platform state testing** — FastCheck invariants shared across frontend/mobile/desktop
- **Contract testing** — OpenAPI schema validation, request/response shape verification
- **Mutation testing** — StrykerJS to identify weak tests, dead code
- **Integration tests** — Component + state + API flows using MSW

**Defer (v2+):**
- **Visual regression testing** — Percy/Chromatic requires screenshot infrastructure, not coverage blocker
- **Performance regression testing** — Lighthouse CI, render time budgets
- **Cross-browser testing** — BrowserStack/Playwright, higher maintenance
- **Memory leak testing** — Specialized tooling, complex setup

### Architecture Approach

**Major components:**
1. **Backend Contract Foundation** — OpenAPI spec as source of truth, Schemathesis validates all endpoints, auto-generates TypeScript types for frontend/mobile/desktop
2. **Shared Test Utilities** — `frontend-nextjs/shared/` with test-helpers, api-clients, state-validators, symlinked by mobile/desktop to prevent duplication
3. **Coverage Aggregation** — `aggregate_coverage.py` parses pytest/Jest/jest-expo/tarpaulin formats, calculates weighted coverage (70% backend, 20% frontend, 5% mobile, 5% desktop), enforces minimum per-platform thresholds
4. **Property Testing Layer** — FastCheck for JS platforms (canvas state, agent maturity), Hypothesis for Python (financial invariants, governance), proptest for Rust
5. **Cross-Platform E2E** — Playwright (web), Detox (mobile), Tauri driver (desktop) unified in single workflow

**Integration points:**
- API contracts: Backend OpenAPI → openapi-typescript → frontend/src/types/api-generated.ts → SYMLINK → mobile/desktop
- Shared utilities: frontend-nextjs/shared/ → SYMLINK → mobile/src/shared, desktop/src/shared
- Coverage aggregation: All platforms → aggregate_coverage.py → unified report → PR comment
- State invariants: FastCheck tests in frontend → SYMLINK → mobile reuse

### Critical Pitfalls

1. **Floating-point precision in financial calculations** — Using `float` instead of `Decimal` causes accumulation errors that violate accounting standards (GAAP/IFRS) and create reconciliation failures. Prevention: Use `decimal.Decimal` for all monetary values, store amounts as integer cents, define banker's rounding (half-even) strategy, property test precision invariants.

2. **Inadequate audit trail testing** — Tests verify audit entries exist but don't validate completeness, integrity, or traceability. Prevention: Test audit trail completeness (every financial operation logged), property test audit invariants (count = operations, timestamps non-decreasing), end-to-end traceability tests, test audit entry immutability.

3. **Property testing without financial invariants** — Property tests focus on implementation details instead of domain-specific invariants (double-entry bookkeeping, conservation of value). Prevention: Identify financial invariants first (debits == credits, balance sheet equation), use established property patterns (round-trip, inductive, invariant preservation), require bug-finding evidence in docstrings.

4. **Payment integration mock mismatch** — Mocks don't match real provider behavior, missing race conditions, webhook failures, idempotency issues. Prevention: Use provider test mode (Stripe Test Mode, PayPal Sandbox), test failure modes (declined cards, timeouts), test webhook reliability, test idempotency explicitly, use VCR/recording.

5. **Sequential platform testing** — Single CI job running all platform tests sequentially causes 40+ minute feedback loops. Prevention: Platform-specific jobs with parallel execution (EXISTING in unified-tests.yml), fast feedback per platform.

6. **Duplicated test utilities across platforms** — Copy-pasting mock factories to frontend, mobile, desktop causes divergence and maintenance burden. Prevention: Shared test utilities via symlinks (frontend-nextjs/shared/), single source of truth.

7. **Ignoring platform-specific coverage gaps** — Overall 80% coverage masks mobile at 16.16% and desktop at TBD. Prevention: Weighted coverage calculation + minimum per-platform thresholds (backend ≥70%, frontend ≥80%, mobile ≥50%, desktop ≥40%).

8. **Rounding strategy inconsistency** — Different parts of system use different rounding strategies (traditional vs. banker's), causing reconciliation failures. Prevention: Document rounding strategy (banker's half-even), use explicit rounding, property test rounding invariants, cross-language consistency.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Core Accounting Logic & Foundation
**Rationale:** Precision errors are foundational — if caught late, require rewriting all financial calculations. Decimal-first design pattern must be established before any financial calculations are written.
**Delivers:** Decimal-based calculation functions, banker's rounding strategy, property tests for precision invariants, edge case testing (zero, negative, large amounts), rounding invariants.
**Addresses:** Table stakes — core numerical accuracy, financial correctness foundation
**Avoids:** Floating-point precision errors causing reconciliation failures and compliance violations, rounding strategy inconsistency, missing test data edge cases
**Features from FEATURES.md:** Core accounting logic, property testing for invariants, edge case testing

### Phase 2: Payment Integration Testing
**Rationale:** Payment integrations have complex race conditions that benefit from property tests. Idempotency and webhook reliability are critical for production.
**Delivers:** Payment integration tests with realistic failure modes, idempotency tests, webhook reliability tests, reconciliation tests with tolerance thresholds, discrepancy workflow tests
**Uses:** Stack from STACK.md — Schemathesis for API contracts, MSW for mocking, VCR/recording for real provider responses
**Implements:** Architecture component — API contract testing with OpenAPI, integration test patterns
**Addresses:** Critical pitfall — Payment integration mock mismatch, reconciliation test coverage gaps
**Features from FEATURES.md:** API mocking with MSW, integration tests, contract testing
**Avoids:** Production payment failures, duplicate charges, lost payments, reconciliation failures

### Phase 3: Cost Tracking & Budgets
**Rationale:** Budget tracking depends on accurate precision from Phase 1. Performance issues appear with large datasets, requiring benchmarks and parallel execution.
**Delivers:** Budget enforcement tests with concurrent checks, cost leak detection tests, savings calculation accuracy tests, performance benchmarks for large datasets (10,000+ transactions)
**Uses:** Hypothesis property tests for budget guardrail invariants, pytest-xdist for parallel execution, pytest-benchmark for performance validation
**Implements:** Architecture component — Property testing layer for financial invariants
**Addresses:** Moderate pitfall — Budget guardrail race conditions, slow financial tests blocking CI
**Features from FEATURES.md:** Property-based testing, performance tests
**Avoids:** Budget overruns, spend blocking, CI pipeline slowdowns

### Phase 4: Audit Trails & Compliance
**Rationale:** Audit trails span all phases and require complete implementation of all financial operations to test meaningfully. SOX compliance requires completeness testing.
**Delivers:** Audit trail completeness tests, integrity tests (immutability), traceability tests (reconstruct transaction from log), cross-service audit propagation tests, aging report tests with boundary conditions
**Uses:** Property tests for audit invariants (count, ordering, immutability), end-to-end integration tests
**Implements:** Architecture component — Cross-platform E2E testing
**Addresses:** Critical pitfall — Inadequate audit trail testing
**Features from FEATURES.md:** Integration tests, E2E critical path tests
**Avoids:** SOX compliance failures, untraceable transactions, forensic analysis failures, reconciliation nightmares

### Phase 5: Frontend Hook & Component Testing
**Rationale:** Frontend has high coverage (89.84%) but gaps in custom hooks and accessibility. Hook testing requires @testing-library/react-hooks, a11y testing requires jest-axe.
**Delivers:** Isolated hook tests for all custom hooks (useCanvasState, useAgentExecution, useAudioControl), accessibility tests with jest-axe for all critical components, leaf component coverage for missing UI elements
**Uses:** @testing-library/react-hooks for hook isolation, jest-axe for WCAG compliance, React Testing Library for component testing
**Implements:** Architecture component — Shared test utilities (test-helpers.ts)
**Addresses:** Table stakes gaps — Hook isolation, accessibility compliance
**Features from FEATURES.md:** Hook tests, accessibility tests, leaf component tests
**Avoids:** Accessibility violations, hook edge cases, component rendering bugs

### Phase 6: Shared Utilities & Cross-Platform Integration
**Rationale:** Shared test utilities prevent duplication across frontend/mobile/desktop. SYMLINK strategy ensures consistency and reduces maintenance burden.
**Delivers:** Shared test helpers (mockAgent, mockCanvasPresentation), shared API clients (type-safe wrappers), shared state validators (FastCheck invariants), SYMLINK setup for mobile/desktop
**Uses:** frontend-nextjs/shared/ as single source of truth, symlinks for cross-platform sharing
**Implements:** Architecture component — Shared test utilities integration point
**Addresses:** Anti-pattern — Duplicated test utilities across platforms
**Features from FEATURES.md:** Integration tests, cross-platform testing
**Avoids:** Test utility divergence, maintenance burden, inconsistent test data

### Phase 7: API Contract Testing & Type Generation
**Rationale:** Backend OpenAPI spec as source of truth enables compile-time type safety across all platforms. Breaking changes detected immediately during TypeScript compilation.
**Delivers:** OpenAPI spec generation from FastAPI, Schemathesis contract tests, auto-generated TypeScript types (api-generated.ts), CI workflow for contract validation
**Uses:** Schemathesis for Python contract testing, openapi-typescript for type generation, GitHub Actions for automated validation
**Implements:** Architecture component — Backend contract foundation integration point
**Addresses:** Should-have feature — API contract testing
**Features from FEATURES.md:** Contract testing, mutation testing
**Avoids:** Breaking changes in production, type mismatches between backend and frontend

### Phase 8: Weighted Coverage Quality Gates
**Rationale:** Overall 80% coverage masks platform-specific gaps (mobile at 16.16%). Weighted calculation enforces minimum per-platform thresholds.
**Delivers:** Weighted coverage calculation (backend 70%, frontend 20%, mobile 5%, desktop 5%), minimum per-platform thresholds (backend ≥70%, frontend ≥80%, mobile ≥50%, desktop ≥40%), CI quality gate enforcement
**Uses:** aggregate_coverage.py (existing, modified for weighting), ci_quality_gate.py (existing, modified for thresholds)
**Implements:** Architecture component — Coverage aggregation integration point
**Addresses:** Critical pitfall — Ignoring platform-specific coverage gaps
**Features from FEATURES.md:** Coverage targets by category
**Avoids:** Gaming the system with easy frontend tests, masking low coverage on minor platforms

### Phase 9: Cross-Platform Property Testing Expansion
**Rationale:** Property tests for state invariants catch edge cases unit tests miss. FastCheck invariants shared across frontend/mobile/desktop ensure consistency.
**Delivers:** FastCheck property tests for canvas state invariants, agent maturity invariants, offline queue invariants, cross-platform validation (frontend → mobile via SYMLINK), Rust proptest equivalents for desktop
**Uses:** FastCheck for JS/TS platforms, Hypothesis for Python, proptest for Rust, shared state-validators.ts
**Implements:** Architecture component — Property testing layer
**Addresses:** Should-have feature — Property-based testing, differentiator
**Features from FEATURES.md:** Property-based testing, state machine tests
**Avoids:** State corruption bugs, illegal transitions, inconsistent data across platforms

### Phase 10: Cross-Platform E2E Orchestration
**Rationale:** E2E tests validate end-to-end user experience across all platforms. Slowest tests, depend on stable unit/integration tests.
**Delivers:** Playwright E2E tests (web), Detox E2E tests (mobile), Tauri E2E tests (desktop), unified workflow with aggregation, critical workflow tests (agent execution, canvas presentation)
**Uses:** Playwright (existing), Detox (new for mobile), Tauri driver (new for desktop), e2e_unified.yml workflow
**Implements:** Architecture component — Cross-platform E2E testing
**Addresses:** Should-have feature — E2E critical path tests
**Features from FEATURES.md:** E2E critical path tests
**Avoids:** Integration bugs, API contract mismatches, state sync issues

### Phase Ordering Rationale

- **Backend-first foundation**: OpenAPI spec enables all downstream contract testing, single source of truth for types
- **Precision before payments**: Decimal-first design prevents rewriting all financial calculations later
- **Payments before budgets**: Budget tracking depends on accurate precision from Phase 1, payment race conditions benefit from property tests
- **Foundation before expansion**: Shared utilities reduce duplication before expanding test suite, prevent maintenance burden
- **Contracts before integration**: API contracts enable compile-time safety, breaking changes detected immediately
- **Weighted coverage before completion**: Platform minimums enforced after infrastructure ready, prevent gaming the system
- **Property tests after stable foundation**: Require domain knowledge, better after contract validation stable
- **E2E last**: Slowest tests, depend on stable unit/integration tests, used for smoke testing before deployment

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Payment Integration)**: MEDIUM risk — Payment provider testing patterns vary by provider (Stripe vs. PayPal vs. Braintree), need specific research on providers used in Atom
- **Phase 4 (Audit Trails)**: HIGH risk — SOX compliance requirements are strict, gaps are expensive to fix post-deployment
- **Phase 9 (Property Testing)**: MEDIUM risk — Property test performance may be slow with 100+ examples, need benchmarking with Atom's existing property test suite

Phases with standard patterns (skip research-phase):
- **Phase 1 (Core Accounting)**: HIGH confidence — Decimal-first design, banker's rounding, property testing invariants well-documented
- **Phase 5 (Frontend Hooks)**: HIGH confidence — @testing-library/react-hooks, jest-axe are industry standards with established patterns
- **Phase 6 (Shared Utilities)**: HIGH confidence — SYMLINK strategy, shared test helpers are straightforward DRY principle
- **Phase 7 (API Contracts)**: HIGH confidence — Schemathesis, openapi-typescript, FastAPI OpenAPI generation are well-documented
- **Phase 8 (Weighted Coverage)**: HIGH confidence — aggregate_coverage.py exists, weighting logic is straightforward math
- **Phase 10 (E2E Orchestration)**: HIGH confidence — Playwright existing, Detox and Tauri have standard patterns

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack (Jest, RTL, FastCheck) | HIGH | All package versions verified from package.json, official documentation, 2025 industry standards |
| Features (testing patterns) | HIGH | React Testing Library official docs, industry best practices from 2025-2026, existing Atom test infrastructure analysis |
| Architecture (cross-platform) | HIGH | Existing infrastructure analysis (aggregate_coverage.py, unified-tests.yml), 2026 ecosystem research, established integration patterns |
| Pitfalls (finance-specific) | HIGH | Multiple authoritative sources on IEEE 754 limitations, SOX compliance documentation, existing Atom property test patterns (38 tests in governance, 814 lines financial, 705 lines accounting) |

**Overall confidence:** HIGH

### Gaps to Address

- **Specific payment provider testing patterns**: Stripe/PayPal/Braintree have different webhook formats — Phase 2 should research specific providers used in Atom
- **Currency exchange rate precision**: Banker's rounding (half-even) research shows complexity — may need dedicated phase for multi-currency if Atom supports international payments
- **Property test performance**: 100+ examples for financial invariants may be slow — need benchmarking with Atom's existing property test suite (250+ Hypothesis tests)
- **Mobile E2E testing patterns**: Detox for React Native has iOS/Android differences — Phase 10 should research specific emulator/simulator requirements
- **Desktop coverage baseline**: Tauri/Rust coverage is TBD — need to establish baseline before setting minimum threshold (currently 40% in Phase 8)

## Sources

### Primary (HIGH confidence)
- **Jest 30 Documentation** — Test runner configuration, 37% faster than Jest 29, 77% less memory
- **React Testing Library** — Authoritative component testing patterns, avoid implementation details
- **@testing-library/react-hooks** — GitHub repository, isolated hook testing
- **jest-axe** — NPM package, WCAG 2.1 compliance testing
- **MSW (Mock Service Worker)** — Official documentation, API mocking for integration tests
- **FastCheck** — Official documentation, property-based testing for TypeScript/JavaScript
- **Schemathesis** — Python contract testing framework, OpenAPI validation
- **openapi-typescript** — TypeScript type generation from OpenAPI specs
- **Existing Atom infrastructure** — aggregate_coverage.py (755 lines), unified-tests.yml, api-contracts.test.ts, ci_quality_gate.py, e2e-unified.yml
- **Existing Atom property tests** — 250+ Hypothesis tests (backend), 84 FastCheck tests (frontend), 814 lines financial invariants, 705 lines accounting invariants, 1205 lines governance invariants

### Secondary (MEDIUM confidence)
- **React-Boilerplate测试体系** — 98% coverage standards (Feb 2026)
- **NextUI组件测试覆盖率提升** — From 70% to 95% coverage improvements
- **Vitest Component Testing Guide** — Modern error boundary testing patterns (Jan 2026)
- **React Error Boundary Testing Guide** — Error boundary testing with React Testing Library (Feb 2026)
- **Frontend Testing Anti-Patterns** — Brittle selectors, implementation details testing
- **Cross-Platform Testing Architecture Trends 2026** — AI-driven testing, distributed frameworks
- **React Native State Management: Zustand vs Redux** — Cross-platform state patterns
- **Detox for React Native E2E Testing** — Mobile E2E automation
- **Playwright + Detox + Tauri for Multi-Platform E2E** — Unified testing frameworks
- **Stripe Testing Documentation** — Comprehensive test cards for declines, disputes, refunds
- **pytest Mock Technology Complete Guide** — Payment gateway mock implementation (June 2025)
- **Common Problems in Payment Systems** — Testing challenges with third-party payment systems
- **CI/CD Performance Testing Pitfalls** — 6-10x CI performance improvements
- **Big Data Testing Challenges** — Performance testing with large datasets
- **致命精度陷阱:金融与科学计算中的数值准确性实战指南** — Numerical accuracy in financial trading, IEEE 754 limitations (Dec 2025)
- **Java精确计算实战(从浮点错误到BigDecimal完美解决方案)** — Floating-point errors in financial systems, audit inconsistencies, compliance risks (Oct 2025)
- **银行家舍入规则(IEEE 754 标准)详解** — IEEE 754 banker's rounding specification with examples
- **Float and Decimal Golden Rule** — Performance testing with 1M records comparing FLOAT vs DECIMAL (July 2025)
- **Audit Trail Testing - Walk-Through Testing** — Adequate audit trail documentation requirements (DOD Financial Management)
- **SOX Testing Best Practices** — SOX 404 control testing methodologies

### Tertiary (LOW confidence)
- **Hacker News: Floating Point in Financial Systems** — Community discussion on binary floating-point vs. fixed-point for accounting (May 2025)
- **Banker's rounding(银行家舍入法)** — Q&A format explaining half-even rounding
- **兑换外币小数点后的怎么算** — Q&A on foreign exchange precision requirements
- **Cross-platform testing patterns** — Limited patterns for shared test suites across web/mobile/desktop (needs validation)
- **Visual regression testing** — Tool fragmentation (Percy vs Chromatic), unclear industry standards
- **Performance regression testing** — Lighthouse CI patterns still evolving
- **Mutation testing adoption** — StrykerJS usage patterns not widely documented

---

*Research completed: March 3, 2026*
*Ready for roadmap: yes*
