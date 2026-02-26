# Project Research Summary

**Project:** Atom Test Coverage Initiative v4.0 — Platform Integration & Property-Based Testing
**Domain:** Multi-platform testing infrastructure (Next.js, React Native, Tauri, Python)
**Researched:** February 26, 2026
**Confidence:** HIGH

## Executive Summary

Atom v4.0 requires a unified testing architecture that integrates four distinct platforms (Python backend, Next.js frontend, React Native mobile, Tauri desktop) with property-based testing parity. The existing backend has comprehensive Hypothesis property tests (100+ files), while frontend/mobile have Jest configured but limited test coverage (40% pass rate, 21/35 frontend tests failing). The recommended approach uses a **platform-first testing strategy** where each platform runs tests independently in CI, then aggregates results via Python scripts for unified coverage reporting.

The most critical risk is **fragmented testing infrastructure** — frontend/mobile/desktop tests currently run in isolation without unified quality gates. Research shows this leads to inconsistent coverage, missed integration bugs, and slow feedback loops. Mitigation requires: (1) centralized coverage aggregation using pytest-cov as source of truth, (2) FastCheck for JavaScript/TypeScript property tests (matching Hypothesis patterns), (3) unified CI orchestration with parallel platform execution, and (4) incremental rollout starting with backend+frontend integration before adding mobile/desktop.

Key differentiator: Property-based testing for frontend state management (Redux/Zustand reducers, API contracts, data transformations) using FastCheck — an approach not widely adopted in production but highly recommended for catching edge cases in business logic invariants. This extends Atom's existing Hypothesis-based property test patterns to JavaScript/TypeScript platforms.

## Key Findings

### Recommended Stack

**Core technologies:**
- **Jest (30.0.5/29.7.0)** — Test runner for Next.js and React Native — Already configured with 80% coverage threshold, jsdom/jest-expo presets working
- **pytest (8.4.2)** — Backend orchestration and unified reporting — Existing infrastructure with CI/CD integration, coverage enforcement
- **Hypothesis (6.151.5)** — Python property-based testing — Already in use with 60+ property test files, proven patterns
- **FastCheck (4.5.3)** — TypeScript/JavaScript property-based testing — Hypothesis equivalent for JS/TS, integrates with Jest, type-safe
- **Playwright Python (1.58.0) + Node (1.58.2)** — Cross-platform E2E — Backend has 17 tests, frontend needs integration
- **Detox (20.47.0)** — React Native grey-box E2E — 10x faster than Appium, grey-box architecture
- **pytest-cov (4.1.0)** — Python coverage aggregation — Already configured, use as source of truth

**Integration strategy:** Frontend/mobile tests run in native Jest environments but report to unified pytest-based CI pipeline using JSON report aggregation. Python scripts parse all coverage formats (pytest JSON, Jest JSON) and produce unified reports.

### Expected Features

**Must have (table stakes):**
- **Component Integration Tests** — Verify components work together with state management, API calls, routing — React Testing Library for Next.js, React Native Testing Library for mobile
- **API Contract Validation** — Frontend must correctly call backend APIs and handle responses — Test request/response shapes, error handling, timeout scenarios
- **State Management Consistency** — Redux/Zustand/Context state must be predictable and consistent — Test state updates, selectors, async actions, middleware
- **Form Validation & Submission** — Forms must validate correctly and submit data to backend — Test validation rules, error display, success/error states
- **Navigation & Routing** — Users must navigate between screens/pages correctly — Test routing, navigation params, deep links, back navigation
- **Authentication Flow** — Login/register/logout must work correctly with token storage — Test auth flows, token refresh, session persistence, biometric auth
- **Offline Data Sync** — Mobile/desktop must handle offline mode gracefully — Test offline queue, sync on reconnect, conflict resolution
- **Device Feature Mocking** — Camera, location, notifications must work across platforms — Mock Expo modules, device APIs, test permissions

**Should have (competitive differentiators):**
- **Property-Based State Testing** — Use fast-check to generate random state transitions and verify invariants — State machines, Redux reducers, context providers should maintain invariants
- **Visual Regression Testing** — Detect unintended UI changes across releases — Percy, Chromatic, or Playwright screenshots
- **Cross-Platform Consistency** — Verify feature parity across web/mobile/desktop — Same tests run on multiple platforms, validate consistent behavior
- **Performance Regression Tests** — Detect rendering performance degradation — Lighthouse CI, render time budgets, bundle size tracking
- **Accessibility Testing** — Ensure WCAG compliance with automated tests — jest-axe, aria labels, keyboard navigation, screen reader tests
- **End-to-End User Flows** — Test complete workflows from UI to backend — Playwright for web, Detox for mobile

**Defer (v2+):**
- **Mutation Testing** — Verify test quality by mutating code — Requires baseline test quality first
- **Memory Leak Detection** — Find memory leaks in long-running sessions — Advanced performance testing

### Architecture Approach

**Platform-first testing architecture:** Each platform runs tests independently in CI (pytest for backend, Jest for frontend/mobile, cargo test for Tauri), then uploads coverage artifacts to a unified aggregation job. Python scripts parse multiple coverage formats and produce unified reports with per-platform breakdowns. Quality gates enforce 50% overall coverage + 98% pass rate across all platforms.

**Major components:**
1. **Platform-Specific Test Runners** — pytest (backend), Jest (frontend/mobile), cargo test (desktop Rust) — Each runs independently in parallel CI jobs
2. **Coverage Aggregator** — Python script (`backend/tests/scripts/aggregate_coverage.py`) — Parses pytest JSON, Jest JSON, Rust coverage; produces unified report
3. **Unified Quality Gates** — Python script (`unified_quality_gate.py`) — Enforces coverage thresholds, pass rate, flaky test detection
4. **Property Test Frameworks** — Hypothesis (Python), FastCheck (JavaScript/TypeScript) — Shared invariant testing patterns across platforms
5. **CI Orchestration** — GitHub Actions workflows — Parallel test execution, artifact upload/download, aggregation job

**Data flow:** Developer push → Trigger CI jobs (backend, frontend, mobile, desktop in parallel) → Upload coverage artifacts → Download all artifacts → Aggregate coverage → Quality gate evaluation → PR comment with breakdown

### Critical Pitfalls

1. **Monolithic Test Workflow** — Single CI job running all platforms sequentially causes 40+ minute feedback loops — **Avoid:** Use platform-specific jobs with parallel execution
2. **Coverage Without Context** — Reporting single percentage without breakdown masks regressions in specific platforms — **Avoid:** Provide detailed per-platform breakdown with trends
3. **Property Tests for Everything** — Replacing all unit tests with property tests slows execution 100x without proportional bug-finding value — **Avoid:** Use property tests for critical invariants only (state machines, data transformations, API contracts)
4. **Fragmented Coverage Reporting** — No unified view of coverage across platforms leads to inconsistent quality — **Avoid:** Centralize aggregation using Python scripts as source of truth
5. **Test Data Edge Cases Missing** — Financial test data uses typical values but misses critical edge cases (zero, negative, maximum limits) — **Avoid:** Use property-based testing with explicit min/max values in Hypothesis strategies

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Backend + Frontend Integration (Week 1-2)
**Rationale:** Backend has established property test patterns (Hypothesis) and CI infrastructure. Frontend shares TypeScript types with backend API, making integration highest impact. Fixes 21 failing frontend tests (40% → 100% pass rate).

**Delivers:**
- Unified coverage aggregation (pytest + Jest)
- Frontend integration tests (API contracts, state management, form validation)
- FastCheck property tests for frontend invariants (10-15 tests)

**Addresses:**
- Component Integration Tests, API Contract Validation, State Management Consistency (from FEATURES.md)
- Property-Based State Testing (differentiator)

**Uses:**
- FastCheck 4.5.3 for property tests, pytest-json-report 1.5.0 for unified reporting
- Playwright Node 1.58.2 for E2E, React Testing Library 16.3.0 for component tests

**Implements:**
- Coverage aggregator script (`backend/tests/scripts/aggregate_coverage.py`)
- Unified CI workflow (`.github/workflows/unified-tests.yml`)
- Frontend tests workflow (`.github/workflows/frontend-tests.yml`)

**Avoids:**
- Monolithic test workflow pitfall (parallel execution)
- Fragmented coverage reporting (unified aggregation)

### Phase 2: Mobile Integration (Week 3-4)
**Rationale:** Mobile has Jest infrastructure configured (jest-expo), just needs integration with unified coverage. Property test patterns from Phase 1 can be reused.

**Delivers:**
- Mobile integration tests (device features, offline sync, platform permissions)
- FastCheck property tests for mobile invariants (5-10 tests)
- Cross-platform consistency tests

**Addresses:**
- Offline Data Sync, Device Feature Mocking, Authentication Flow (from FEATURES.md)
- Cross-Platform Consistency (differentiator)

**Uses:**
- Detox 20.47.0 for grey-box E2E, React Native Testing Library 13.3.3
- expo-mock for device API mocking, detox-expo-helpers for Expo integration

**Implements:**
- Mobile tests workflow (modify existing `.github/workflows/mobile-ci.yml`)
- Extend coverage aggregator for jest-expo coverage format

**Avoids:**
- Test data edge cases missing (property tests with device-specific strategies)
- Fragmented coverage (mobile included in unified report)

### Phase 3: Desktop Testing (Week 5)
**Rationale:** Desktop is most complex (Rust + JavaScript), defer until patterns established from Phases 1-2. Tauri requires native module mocking and cross-platform validation.

**Delivers:**
- Tauri integration tests (native API mocks, cross-platform tests)
- Rust property tests (QuickCheck) + JavaScript property tests
- Desktop-specific feature tests (menu bar, notifications, auto-updates)

**Addresses:**
- Desktop integration (system APIs, filesystem access, Tauri commands)
- Cross-Platform Consistency (differentiator)

**Uses:**
- tauri-driver 2.10.1 for WebDriver E2E, cargo test for Rust backend
- Tauri API mocks for @tauri-apps/plugin-* modules

**Implements:**
- Desktop tests workflow (`.github/workflows/desktop-tests.yml`)
- Extend coverage aggregator for Rust coverage (tarpaulin or covector)

**Avoids:**
- Property tests for everything pitfall (focus on critical invariants only)
- Cross-platform inconsistencies (shared test suite where possible)

### Phase 4: Property Testing Expansion (Week 6)
**Rationale:** Property test patterns proven in Phases 1-3, now expand to cover critical invariants across all platforms. Requires deep understanding of business logic invariants.

**Delivers:**
- 30+ property tests across all platforms (backend Hypothesis, frontend/mobile FastCheck, desktop QuickCheck)
- Documented property testing patterns for each platform
- Invariant identification (state transitions, data validation, API contracts)

**Addresses:**
- Property-Based State Testing (differentiator — full implementation)
- Component Contract Tests, Data Transformation Invariants (differentiator)

**Uses:**
- Hypothesis 6.151.5 (backend), FastCheck 4.5.3 (frontend/mobile), QuickCheck (Rust)
- Existing Atom property test patterns (governance maturity invariants, financial invariants)

**Implements:**
- `frontend-nextjs/tests/property/` directory
- `mobile/src/__tests__/property/` directory
- `frontend-nextjs/src-tauri/tests/property_tests.rs`

**Avoids:**
- Property tests for everything pitfall (critical invariants only, 50-100 examples)
- Weak properties (require bug-finding evidence in docstrings)

### Phase 5: Cross-Platform Integration & E2E (Week 7-8)
**Rationale:** Depends on all platforms being testable. Validates backend API integration with frontend/mobile/desktop end-to-end.

**Delivers:**
- Cross-platform integration tests (same tests run on web/mobile/desktop)
- E2E user flows (authentication, navigation, data persistence)
- Visual regression testing (optional, if time permits)

**Addresses:**
- End-to-End User Flows (differentiator)
- Visual Regression Testing (differentiator, optional)

**Uses:**
- Playwright for web E2E, Detox for mobile E2E, tauri-driver for desktop E2E
- Percy/Chromatic for visual regression (optional)

**Implements:**
- Shared test suite for cross-platform validation
- E2E test workflows (`.github/workflows/e2e-tests.yml`)

**Avoids:**
- E2E tests for everything pitfall (critical user workflows only)
- Slow tests blocking CI (separate E2E job, run on merge to main)

### Phase Ordering Rationale

- **Backend + Frontend first:** Both use TypeScript (backend API + frontend share types), highest impact, fixes immediate pain point (21 failing frontend tests)
- **Mobile second:** Already has Jest infrastructure, easy integration, property test patterns reusable from Phase 1
- **Desktop third:** Most complex (Rust + JavaScript), need to establish patterns first, Tauri testing less documented
- **Property tests fourth:** Require deep understanding of invariants, better to write after integration tests stable
- **Cross-platform last:** Depends on all platforms being testable, validates end-to-end integration

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 2 (Mobile):** Device feature mocking patterns — Expo module APIs vary, iOS vs Android differences need research
- **Phase 3 (Desktop):** Tauri native module mocking strategies — Less documentation than web/mobile, may need prototype testing
- **Phase 4 (Property Tests):** Invariant identification for frontend state — FastCheck adoption low, few real-world examples, may need research into generator strategies for complex UI state

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Backend + Frontend):** Well-documented, established patterns — Jest, React Testing Library, pytest all have comprehensive documentation
- **Phase 5 (Cross-Platform E2E):** Standard E2E patterns — Playwright, Detox both mature tools with extensive guides

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack (Jest, pytest, FastCheck, Detox) | HIGH | All package versions verified via npm/pip, integration strategy based on existing working setup |
| Features (component integration, API contracts) | MEDIUM | Mix of official docs (React Testing Library, FastCheck) and codebase analysis (21 failing frontend tests, 25+ mobile tests) |
| Architecture (platform-first, aggregation) | HIGH | Based on existing Atom infrastructure (pytest, Hypothesis patterns, CI/CD workflows), proven architectural patterns |
| Pitfalls (monolithic workflow, fragmented coverage) | HIGH | Anti-patterns identified from existing infrastructure analysis, well-documented CI/CD best practices |

**Overall confidence:** HIGH (stack verification + existing infrastructure analysis + official documentation)

### Gaps to Address

- **FastCheck generator strategies for complex UI state:** FastCheck adoption is low in production, few real-world examples for React state management — May need prototype testing during Phase 1 planning
- **Tauri native module mocking:** Less documentation than web/mobile, may need spike research during Phase 3 planning — Mitigation: Start with cargo test for Rust logic, defer complex mocking if patterns unclear
- **Cross-platform test sharing:** Limited patterns for shared test suites across web/mobile/desktop — Mitigation: Start with platform-specific tests, consolidate shared patterns in Phase 5
- **Visual regression testing infrastructure:** Tool fragmentation (Percy vs Chromatic), unclear best practices — Defer to Phase 5 optional, skip if time-constrained

## Sources

### Primary (HIGH confidence)
- **Backend test infrastructure** — pytest 8.4.2, Hypothesis 6.151.5, pytest-playwright 1.58.0 verified via `pip list`
- **Frontend Testing Stack** — Jest 30.0.5, @testing-library/react 16.3.0 verified via frontend-nextjs/package.json
- **Mobile Testing Stack** — jest-expo 50.0.0, React Native 0.73.6 verified via mobile/package.json
- **FastCheck official documentation** — Property-based testing framework for TypeScript/JavaScript (https://fast-check.dev/)
- **Detox documentation** — React Native grey-box E2E testing (https://wix.github.io/Detox/)
- **Tauri Testing documentation** — Desktop application testing patterns (https://tauri.app/v2/guides/testing/)
- **Existing Atom property tests** — 1,205 lines of governance maturity tests, 814 lines of financial invariants, 705 lines of accounting invariants

### Secondary (MEDIUM confidence)
- **Playwright documentation** — Cross-browser automation (https://playwright.dev/)
- **React Testing Library** — Component testing patterns, queries, async utilities
- **pytest-json-report** — Unified JSON reporting (https://github.com/numirias/pytest-json-report)
- **CI/CD workflows** — `.github/workflows/ci.yml`, `test-coverage.yml`, `mobile-ci.yml` analysis showing existing backend/mobile integration

### Tertiary (LOW confidence — needs validation)
- **Property-based testing for React** — Limited adoption, few production examples (FastCheck ecosystem growing but not mainstream)
- **Cross-platform testing patterns** — Platform-specific differences hard to generalize, may need phase-specific research
- **Visual regression testing** — Multiple tools (Percy, Chromatic), unclear best practices (defer to Phase 5 optional)

---
*Research completed: February 26, 2026*
*Ready for roadmap: yes*
