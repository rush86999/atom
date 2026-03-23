# Feature Landscape

**Domain:** Cross-Platform E2E Testing & Bug Discovery
**Researched:** March 23, 2026
**Overall confidence:** HIGH

## Executive Summary

Comprehensive cross-platform E2E testing and bug discovery for Atom requires a systematic approach across web (Playwright), mobile (React Native API-level), and desktop (Tauri) platforms. Based on analysis of existing v3.1 E2E implementation (30+ tests, Playwright basics, visual regression with Percy), E2E testing best practices, and the Atom codebase architecture, this document outlines table stakes features for production-ready testing, differentiators that distinguish excellent test suites, and anti-patterns to avoid.

**Key Findings:**
- **Current state**: Atom has v3.1 E2E with 30+ Playwright tests, Percy visual regression, API-first auth, database isolation, flaky test detection, but lacks stress testing, mobile E2E (Detox blocked), comprehensive cross-platform test reuse
- **Table stakes for comprehensive E2E**: Critical path coverage (auth, agent execution, canvas), test isolation & reproducibility, parallel execution, screenshots/videos on failure, cross-platform workflow parity
- **Critical gaps**: Stress testing for bug discovery, network simulation, mobile UI E2E (Detox blocked by expo-dev-client), desktop Tauri integration tests, cross-platform test reuse framework
- **Testing balance**: 10% E2E (critical flows only), 20% integration, 70% unit for optimal coverage and feedback speed
- **Key anti-patterns**: Brittle selectors (CSS classes), testing implementation details, shared state between tests, hard-coded waits, E2E tests for edge cases

## Table Stakes

Features expected in ANY production-ready E2E test suite covering cross-platform workflows. Missing = incomplete testing, missed bugs, slow feedback.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Authentication Flow Tests** | Users must login securely across all platforms (web/mobile/desktop) | Medium | JWT token validation, session persistence, logout, token refresh across platforms |
| **Agent Execution Critical Path** | Core product feature - agents must spawn, chat, stream responses | Medium | Spawn agent → send message → receive streaming response → verify output (happy path) |
| **Canvas Presentation Tests** | Core differentiator - 7 canvas types (charts, sheets, forms, docs, email, terminal, coding) | High | Present canvas → verify rendering → verify interactivity → close canvas (all types) |
| **Workflow Skill Execution** | Key feature - install skills, execute with parameters, verify output | Medium | Install skill → execute skill → parse output → verify business logic |
| **Test Isolation & Reproducibility** | Parallel execution requires isolated test data (no collisions) | Medium | Unique IDs per test (UUID suffixes), database cleanup, fresh state per test |
| **Parallel Test Execution** | CI/CD speed - 4 workers = 4x faster feedback | Low | pytest-xdist for web, separate worker schemas (gw0, gw1, gw2, gw3) |
| **Failure Artifacts (Screenshots/Videos)** | Debugging failed tests requires visual evidence | Low | Playwright: `screenshot: 'only-on-failure'`, `video: 'retain-on-failure'` |
| **API-First Authentication** | UI login is slow (10-60s) vs API auth (100-500ms) | Low | Set JWT token directly in localStorage, bypass UI login flow |
| **Database Isolation** | Parallel tests require separate data to avoid conflicts | Medium | Worker-specific schemas, transaction rollbacks, unique test data |
| **Cross-Platform Workflow Parity** | Users expect identical workflows on web/mobile/desktop | High | Shared test logic, platform-specific adapters, consistent test IDs (data-testid/testID) |
| **Smoke Tests** | Verify test infrastructure works before running full suite | Low | Fixtures loaded, browser launches, API works, DB connection valid |
| **Flaky Test Detection** | Flaky tests destroy trust in test suite | Medium | Track test outcomes across CI runs, flag <80% pass rate tests |

## Differentiators

Features that distinguish EXCELLENT E2E test suites (comprehensive bug discovery) from ADEQUATE ones (basic happy path). Not expected, but highly valuable for finding edge cases and production bugs.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Stress Testing for Bug Discovery** | Finds race conditions, memory leaks, resource exhaustion under load | High | Concurrent agent executions, rapid canvas present/close cycles, WebSocket connection churn |
| **Network Simulation Testing** | Tests app behavior under poor network conditions (offline, slow, flaky) | Medium | Playwright `context.route()`, slow 3G, offline mode, packet loss simulation |
| **Visual Regression Testing (Percy)** | Detects unintended CSS/layout changes across platforms | Medium | Automated screenshot comparison on every PR, review diffs in Percy dashboard |
| **Cross-Platform Test Reuse** | Write test once, run on web/mobile/desktop with platform adapters | High | Shared workflow definitions, platform-specific execution (Playwright/Detox/Tauri) |
| **Real User Interaction Simulation** | Finds bugs from realistic user behavior (mouse movement, typos, rapid clicks) | Medium | Playwright `userEvent` API (click, type, hover), realistic delays, keyboard navigation |
| **WebSocket/Streaming Testing** | Validates real-time features (agent streaming, canvas updates) under stress | High | Multiple concurrent streams, connection drops, reconnection logic, message ordering |
| **Canvas Accessibility Testing** | Ensures canvas state exposed to screen readers via hidden ARIA trees | Medium | `window.atom.canvas.getState()` API, accessibility tree validation |
| **Error Boundary & Edge Case Testing** | Tests app behavior under failures (401, 500, timeouts, malformed data) | Medium | Network errors, server errors, timeout handling, malformed API responses |
| **Performance Regression Testing** | Detects performance regressions (slow page loads, sluggish interactions) | Medium | Lighthouse CI, page load budgets, interaction timing thresholds |
| **Memory Leak Detection** | Finds memory leaks in long-running sessions (agent chats, canvas viewing) | High | Chrome DevTools Protocol (CDP), heap snapshots before/after operations |
| **Form Validation & Submission Testing** | Tests complex forms (agent creation, skill installation) with validation | Medium | Required fields, format validation, error messages, success states |
| **Deep Link Testing** | Validates deep links work across platforms (`atom://agent/{id}`, workflows) | Medium | Deep link resolution, routing, parameter passing, authentication state |

## Anti-Features

Testing approaches to explicitly AVOID. These create brittle, unmaintainable, slow, or ineffective test suites.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Brittle Selector Tests (CSS Classes)** | CSS classes change on refactor, test breaks, maintenance nightmare | Use `data-testid` attributes (stable), semantic selectors (`getByRole`, `getByLabelText`) |
| **Testing Implementation Details** | Tests break on internal refactoring, don't validate user behavior | Test user-facing behavior (what user sees/clicks), not internal state or component structure |
| **Shared State Between Tests** | Tests interfere with each other, non-deterministic failures, order-dependent | Isolate test data (unique IDs), cleanup after each test, each test is independent |
| **Hard-coded Waits (`time.sleep`)** | Unreliable (too short or too long), slow tests, flaky on slow CI | Use explicit waits (`wait_for_selector`, `wait_for_url`), Playwright auto-waiting |
| **E2E Tests for Edge Cases** | Slow feedback loop (minutes vs seconds), better suited for unit/integration tests | Unit tests for edge cases, E2E for critical happy paths only (5-10 flows) |
| **Over-Specific Selectors (Nested Paths)** | Brittle to DOM structure changes, breaks on layout refactor | Use stable selectors (`data-testid`, `aria-label`, text content) |
| **Testing Third-Party Libraries** | Don't test what library authors already test (React, Next.js, Chakra UI) | Trust library tests, test your code only (business logic, integration) |
| **Missing Error Path Tests** | Only testing happy path misses critical production bugs | Test 401 (auth expired), 500 (server error), network errors, timeouts, malformed responses |
| **Flaky Tests Ignored** | Flaky tests destroy trust, team disables tests, false sense of security | Track flaky tests, fix root cause (race conditions, timing issues, missing waits) |
| **E2E Tests Without Isolation** | Tests share database, conflicts cause random failures, can't run parallel | Database per worker, unique test data, cleanup fixtures, transaction rollbacks |
| **Testing Private Methods/Internals** | Implementation detail, breaks on refactor, doesn't validate user behavior | Test public API only, behavior over implementation, user-facing outcomes |
| **Mobile Detox E2E Without expo-dev-client** | BLOCKED - expo-dev-client requirement adds 15min CI time, complex setup | Use API-level mobile tests for Phase 148, defer Detox to Phase 150+ when infrastructure ready |

## Feature Categories

### Authentication Testing

**Table Stakes:**
- JWT token validation across platforms
- Login/logout workflows (web UI, mobile API, desktop IPC)
- Session persistence (refresh page, verify still logged in)
- Token refresh on expiry
- Protected route access (redirect to login if not authenticated)

**Differentiators:**
- Biometric auth testing (mobile Face ID/Touch ID)
- Session timeout handling (auto-logout after inactivity)
- Multi-device session management
- OAuth integration testing (Google, GitHub)
- SSO (Single Sign-On) testing

**Complexity:** **Medium** - Auth flows are critical but straightforward to test with API-first approach

---

### Agent Execution Testing

**Table Stakes:**
- Agent spawn workflow (create agent, verify in registry)
- Agent chat interaction (send message, receive response)
- Streaming response validation (chunks arrive in order)
- Agent execution history (verify logged in DB)
- Agent maturity enforcement (STUDENT/INTERN/SUPERVISED/AUTONOMOUS)

**Differentiators:**
- Concurrent agent execution stress test (spawn 10 agents simultaneously)
- Streaming interruption handling (network drop, reconnection)
- Agent timeout handling (long-running operations)
- Agent cancellation (stop execution mid-stream)
- Agent context switching (switch between agents, verify state isolation)

**Complexity:** **High** - Async operations, WebSocket streaming, concurrent executions

---

### Canvas Presentation Testing

**Table Stakes:**
- All 7 canvas types (charts, sheets, forms, docs, email, terminal, coding)
- Canvas rendering validation (verify DOM structure)
- Canvas interactivity (form submission, chart interactions)
- Canvas close workflow (verify cleanup)
- Canvas state API (`window.atom.canvas.getState()`)

**Differentiators:**
- Rapid canvas present/close stress test (memory leak detection)
- Canvas accessibility testing (ARIA tree validation)
- Visual regression for all canvas types (Percy screenshots)
- Canvas streaming updates (real-time data changes)
- Canvas error handling (malformed data, missing fields)

**Complexity:** **High** - 7 canvas types, dynamic content, visual validation

---

### Workflow & Skill Automation Testing

**Table Stakes:**
- Skill marketplace browsing
- Skill installation (verify in skill registry)
- Skill execution with parameters
- Skill output validation
- Skill uninstallation

**Differentiators:**
- Skill dependency resolution (install skills with dependencies)
- Skill version conflict detection
- Skill composition (DAG workflows with multiple skills)
- Skill execution under stress (concurrent skill execution)
- Dynamic skill loading (hot-reload, watchdog detection)

**Complexity:** **High** - Dynamic skill system, dependency management, composition

---

### Stress Testing & Bug Discovery

**Table Stakes:**
- Concurrent agent executions (spawn 5-10 agents simultaneously)
- Rapid canvas present/close cycles (100 iterations, memory leak check)
- WebSocket connection churn (connect/disconnect rapidly)
- Form submission spam (rapid submits, debounce validation)

**Differentiators:**
- Memory leak detection (heap snapshots before/after operations)
- Race condition detection (concurrent writes to same resource)
- Resource exhaustion testing (database connection pool, file handles)
- Network failure simulation (packet loss, high latency, offline mode)
- Performance regression testing (Lighthouse CI, page load budgets)

**Complexity:** **High** - Requires specialized tooling, complex test scenarios, resource monitoring

---

### Cross-Platform Test Reuse

**Table Stakes:**
- Shared workflow definitions (auth, agent execution, canvas)
- Platform-specific adapters (web: Playwright, mobile: Detox/API, desktop: Tauri)
- Consistent test IDs (web: `data-testid`, mobile: `testID`, desktop: `data-testid`)
- Cross-platform feature parity tests

**Differentiators:**
- Single test file, multiple platforms (write once, run everywhere)
- Platform-specific conditional logic (skip mobile-only features on web)
- Cross-platform visual regression (same UI on all platforms)
- Unified test reporting (aggregate web/mobile/desktop results)

**Complexity:** **High** - Abstraction layer, platform differences, test synchronization

---

## Feature Dependencies

```
Authentication Testing
    └──requires──> API-First Auth Fixtures
                    └──requires──> Database Isolation

Agent Execution Testing
    └──requires──> Authentication Testing
    └──requires──> WebSocket/Streaming Infrastructure
    └──enhances──> Stress Testing (concurrent executions)

Canvas Presentation Testing
    └──requires──> Agent Execution Testing
    └──enhances──> Visual Regression Testing
    └──enhances──> Accessibility Testing

Workflow & Skill Automation
    └──requires──> Authentication Testing
    └──requires──> Canvas Presentation Testing (skills present canvases)
    └──enhances──> Stress Testing (concurrent skill execution)

Stress Testing & Bug Discovery
    └──requires──> Agent Execution Testing (baseline)
    └──requires──> Canvas Presentation Testing (baseline)
    └──requires──> Workflow & Skill Automation (baseline)
    └──enhances──> All testing categories (finds race conditions, memory leaks)

Cross-Platform Test Reuse
    └──enhances──> All testing categories (write once, run everywhere)
    └──requires──> Consistent Test IDs (data-testid/testID)

Visual Regression Testing
    └──requires──> Canvas Presentation Testing
    └──requires──> Authentication Testing
    └──enhances──> Cross-Platform Parity (consistent UI)

Network Simulation Testing
    └──requires──> Agent Execution Testing (WebSocket reconnection)
    └──requires──> Canvas Presentation Testing (offline behavior)
    └──enhances──> Stress Testing (failure scenarios)
```

### Dependency Notes

- **Authentication Testing requires API-First Auth Fixtures:** UI login is too slow (10-60s) for E2E tests, need to set JWT token directly in localStorage for fast authentication
- **Agent Execution Testing requires Authentication Testing:** Agent spawn requires authenticated user session
- **Agent Execution Testing requires WebSocket/Streaming Infrastructure:** Streaming responses need WebSocket connection management, reconnection logic
- **Canvas Presentation Testing requires Agent Execution Testing:** Canvas is presented by agent, need agent spawn first
- **Stress Testing requires all baseline categories:** Stress tests build on happy path tests, add concurrent executions, rapid iterations
- **Cross-Platform Test Reuse enhances all categories:** Shared workflow definitions reduce duplication, ensure parity
- **Visual Regression Testing requires Canvas & Authentication:** Need authenticated user + canvas rendered to capture screenshots

## MVP Definition

### Launch With (v7.0 - Cross-Platform E2E Testing & Bug Discovery)

Minimum viable E2E test suite for comprehensive bug discovery across platforms.

- [ ] **Authentication Flow Tests** - Core foundation, all other tests depend on auth
- [ ] **Agent Execution Critical Path** - Core product feature, must work end-to-end
- [ ] **Canvas Presentation Tests (7 types)** - Core differentiator, complex UI components
- [ ] **Test Isolation & Reproducibility** - Parallel execution, speed, reliability
- [ ] **Failure Artifacts (Screenshots/Videos)** - Debugging failed tests
- [ ] **API-First Authentication** - Speed (100-500ms vs 10-60s UI login)
- [ ] **Database Isolation** - Parallel execution without conflicts
- [ ] **Cross-Platform Workflow Parity (Web + Mobile API)** - Verify workflows work on web and mobile (API-level)
- [ ] **Smoke Tests** - Verify test infrastructure works
- [ ] **Flaky Test Detection** - Track test outcomes, flag unreliable tests

### Add After Validation (v7.1 - Advanced Bug Discovery)

Features to add once core E2E is stable and passing.

- [ ] **Stress Testing (Concurrent Executions)** - Trigger: E2E suite passing consistently, need to find race conditions
- [ ] **Network Simulation Testing** - Trigger: Users reporting network-related bugs
- [ ] **Visual Regression Testing (Percy)** - Trigger: UI changes causing unintended regressions
- [ ] **Real User Interaction Simulation** - Trigger: E2E passing but users reporting UX bugs
- [ ] **Error Boundary & Edge Case Testing** - Trigger: Production errors from unhandled edge cases
- [ ] **WebSocket/Streaming Stress Tests** - Trigger: Streaming issues in production (dropouts, ordering)

### Future Consideration (v8.0 - Full Cross-Platform Coverage)

Features to defer until E2E infrastructure is mature and stable.

- [ ] **Cross-Platform Test Reuse Framework** - Defer: Requires abstraction layer, platform-specific adapters
- [ ] **Mobile Detox E2E (Full UI)** - Defer: BLOCKED by expo-dev-client requirement (15min CI overhead)
- [ ] **Desktop Tauri Integration Tests** - Defer: Requires Tauri test infrastructure, GUI context in CI
- [ ] **Performance Regression Testing (Lighthouse CI)** - Defer: Requires performance budgets, monitoring setup
- [ ] **Memory Leak Detection (CDP)** - Defer: Requires specialized tooling, complex test scenarios
- [ ] **Form Validation & Submission Testing** - Defer: Less critical than agent/canvas workflows
- [ ] **Deep Link Testing** - Defer: Edge case, less critical than core workflows

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Authentication Flow Tests | HIGH | Medium | **P1** |
| Agent Execution Critical Path | HIGH | Medium | **P1** |
| Canvas Presentation Tests (7 types) | HIGH | High | **P1** |
| Test Isolation & Reproducibility | HIGH | Medium | **P1** |
| API-First Authentication | HIGH | Low | **P1** |
| Database Isolation | HIGH | Medium | **P1** |
| Failure Artifacts (Screenshots/Videos) | MEDIUM | Low | **P1** |
| Cross-Platform Workflow Parity (Web + Mobile API) | HIGH | Medium | **P1** |
| Smoke Tests | MEDIUM | Low | **P1** |
| Flaky Test Detection | MEDIUM | Medium | **P1** |
| Stress Testing (Concurrent Executions) | HIGH | High | **P2** |
| Network Simulation Testing | MEDIUM | Medium | **P2** |
| Visual Regression Testing (Percy) | MEDIUM | Medium | **P2** |
| Real User Interaction Simulation | MEDIUM | Medium | **P2** |
| Error Boundary & Edge Case Testing | HIGH | Medium | **P2** |
| WebSocket/Streaming Stress Tests | MEDIUM | High | **P2** |
| Cross-Platform Test Reuse Framework | HIGH | High | **P3** |
| Mobile Detox E2E (Full UI) | MEDIUM | High | **P3** |
| Desktop Tauri Integration Tests | MEDIUM | High | **P3** |
| Performance Regression Testing | MEDIUM | Medium | **P3** |
| Memory Leak Detection | MEDIUM | High | **P3** |
| Form Validation & Submission Testing | LOW | Medium | **P3** |
| Deep Link Testing | LOW | Medium | **P3** |

**Priority key:**
- **P1: Must have for v7.0 launch** - Core E2E testing for critical workflows
- **P2: Should have for v7.1** - Advanced bug discovery techniques
- **P3: Nice to have for v8.0+** - Full cross-platform coverage, specialized testing

## Competitor Feature Analysis

| Feature | Selenium/Cypress | Playwright | Detox | Our Approach (Atom) |
|---------|-----------------|------------|-------|---------------------|
| **Cross-browser testing** | Excellent (all browsers) | Excellent (Chrome, Firefox, Safari, Edge) | N/A (mobile only) | Playwright for web (Chromium v3.1, expand to Firefox/Safari v3.2) |
| **Mobile testing** | Appium (complex setup) | N/A | Excellent (React Native) | API-level tests v7.0 (Detox BLOCKED, defer to v8.0) |
| **Desktop testing** | N/A | N/A | N/A | Tauri integration tests (defer to v8.0) |
| **Parallel execution** | Yes (with Selenium Grid) | Yes (built-in) | Yes | pytest-xdist (web), separate workers (mobile API, desktop) |
| **Auto-waiting** | No (manual waits) | Yes (auto-wait for elements) | Yes (auto-wait) | Playwright auto-waiting (web), explicit waits (mobile/desktop) |
| **Visual regression** | Third-party (Applitools) | Third-party (Percy) | Third-party (Detox screenshot) | Percy integration (v7.1) |
| **Network simulation** | Yes (manual) | Yes (`context.route()`) | Limited | Playwright network simulation (v7.1) |
| **Stress testing** | Manual (load testing tools) | Manual (k6, Artillery) | Manual | Custom stress tests (v7.1) |
| **Flaky test detection** | Manual | Manual | Manual | Custom FlakyTestTracker (v7.0) |
| **Test isolation** | Manual setup | Manual setup | Manual setup | Database per worker, unique IDs (v7.0) |

## Existing Atom E2E Infrastructure (v3.1)

**Already Implemented:**
- ✅ Playwright configuration (`playwright.config.ts`, `backend/tests/e2e_ui/playwright.config.ts`)
- ✅ 30+ E2E tests (auth, agent execution, canvas, skills, governance, WebSocket streaming)
- ✅ API-first authentication (`fixtures/auth_fixtures.py`, JWT token in localStorage)
- ✅ Database isolation (`fixtures/database_fixtures.py`, worker-specific schemas)
- ✅ Test data factory (`fixtures/test_data_factory.py`, Factory Boy pattern)
- ✅ Page Object Model (`pages/page_objects.py`, `pages/cross_platform_objects.py`)
- ✅ Smoke tests (`tests/test_smoke.py`, infrastructure validation)
- ✅ Flaky test detection (`scripts/detect_flaky_tests.py`, `scripts/flaky_test_tracker.py`)
- ✅ Quality gates (`scripts/quality_gate.py`, `scripts/pass_rate_validator.py`)
- ✅ Visual regression (Percy) (`tests/visual/test_visual_regression.py`)
- ✅ Cross-platform workflow tests (`tests/cross-platform/test_shared_workflows.py`, `tests/cross-platform/test_feature_parity.py`)
- ✅ CI/CD integration (`.github/workflows/e2e-unified.yml`, parallel platform jobs)

**Gaps for v7.0:**
- ❌ Stress testing for bug discovery (concurrent executions, rapid iterations)
- ❌ Network simulation testing (offline, slow 3G, packet loss)
- ❌ Real user interaction simulation (realistic delays, keyboard navigation)
- ❌ Error boundary & edge case testing (401, 500, timeouts, malformed responses)
- ❌ WebSocket/Streaming stress tests (connection churn, reconnection logic)
- ❌ Canvas accessibility testing (ARIA tree validation for all 7 canvas types)
- ❌ Memory leak detection (heap snapshots, long-running sessions)
- ❌ Performance regression testing (Lighthouse CI, page load budgets)
- ❌ Mobile Detox E2E (BLOCKED by expo-dev-client requirement)
- ❌ Desktop Tauri integration tests (GUI context required in CI)
- ❌ Cross-platform test reuse framework (shared test logic, platform adapters)

## Sources

### High Confidence (Official Documentation & Implementation)

- **[Playwright Python Documentation](https://playwright.dev/python/)** - Authoritative E2E testing patterns, auto-waiting, selectors
- **[Atom E2E Testing Guide](/Users/rushiparikh/projects/atom/docs/E2E_TESTING_GUIDE.md)** - Comprehensive E2E setup, patterns, troubleshooting (March 7, 2026)
- **[Atom v3.1 E2E Implementation](/Users/rushiparikh/projects/atom/backend/tests/e2e_ui/)** - 30+ production E2E tests, fixtures, page objects, flaky test detection
- **[Percy Documentation](https://docs.percy.io/)** - Visual regression testing best practices
- **[pytest-xdist Documentation](https://pytest-xdist.readthedocs.io/)** - Parallel test execution, worker isolation
- **[Factory Boy Documentation](https://factoryboy.readthedocs.io/)** - Test data factory patterns

### Medium Confidence (Codebase Analysis & Best Practices)

- **Atom E2E Test Suite** - 30+ tests covering auth, agent execution, canvas, skills, governance, WebSocket streaming
- **Atom Flaky Test Detection** - Custom FlakyTestTracker, detect_flaky_tests.py, quality gates, pass rate validation
- **Atom Cross-Platform Tests** - test_shared_workflows.py, test_feature_parity.py, cross_platform_objects.py
- **Atom Visual Regression Tests** - Percy integration, 5 critical pages (dashboard, agent chat, canvas sheets/charts/forms)
- **E2E Testing Anti-Patterns** - Brittle selectors, testing implementation details, shared state, hard-coded waits (from codebase analysis)

### Low Confidence (Industry Best Practices - Needs Validation)

- **Stress testing patterns for E2E** - Limited examples of stress testing in E2E suites (most use separate load testing tools)
- **Network simulation in E2E** - Playwright `context.route()` documented, but production patterns not widely available
- **Cross-platform test reuse frameworks** - Emerging pattern, few production examples of shared test logic across platforms
- **Mobile Detox E2E best practices** - BLOCKED by expo-dev-client requirement, deferred to Phase 150+
- **Memory leak detection in E2E** - Specialized tooling (Chrome DevTools Protocol), complex test scenarios

### Gaps Identified

- **Stress testing for E2E** - Need patterns for concurrent agent executions, rapid canvas iterations, WebSocket churn
- **Network simulation in production E2E** - Need examples of offline, slow 3G, packet loss testing in real apps
- **Cross-platform test reuse abstractions** - Need to design framework for shared workflow definitions, platform adapters
- **Mobile API-level testing patterns** - Need to validate API-level approach vs Detox E2E for mobile workflows
- **Performance budgets for E2E** - Need to define page load thresholds, interaction timing budgets for E2E tests

**Next Research Phases:**
- Phase-specific research needed for stress test design (concurrent execution patterns, resource exhaustion scenarios)
- Investigation into network simulation libraries (Playwright `context.route()` vs dedicated tools)
- Deep dive on cross-platform test reuse patterns (shared test logic, platform adapters, test ID conventions)
- Research on Mobile API-level testing vs Detox E2E tradeoffs (speed, coverage, maintenance)

---

*Feature research for: Atom v7.0 Cross-Platform E2E Testing & Bug Discovery*
*Researched: March 23, 2026*
*Confidence: HIGH (mix of official docs, existing implementation, codebase analysis, industry best practices)*
