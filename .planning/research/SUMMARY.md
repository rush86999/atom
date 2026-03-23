# Project Research Summary

**Project:** Atom v7.0 - Cross-Platform E2E Testing & Bug Discovery
**Domain:** Cross-Platform End-to-End Testing & Quality Assurance
**Researched:** March 23, 2026
**Confidence:** HIGH (Web/pytest: HIGH, Mobile/Desktop/Stress: MEDIUM)

## Executive Summary

Atom is an AI-powered business automation platform requiring comprehensive cross-platform E2E testing across web (Next.js/Playwright), mobile (React Native/Detox), and desktop (Tauri) with a focus on stress testing and automated bug discovery. **Key insight**: Build on existing v3.1 E2E infrastructure (30+ Playwright tests, Percy visual regression, pytest backend tests) rather than replacing it. Add mobile/desktop testing layers and stress testing infrastructure incrementally for cost-effective bug discovery.

The recommended approach leverages **Playwright for web** (already configured with v3.1 E2E), **Detox for React Native mobile** (available but requires expo-dev-client setup), **Tauri's built-in testing for desktop**, and **k6 for API stress testing**. Integrate all with pytest for unified orchestration and Allure for comprehensive reporting. This combination provides excellent cross-platform coverage with minimal tooling complexity, building on Atom's existing investment in Playwright and pytest.

**Critical risks**: Mobile Detox testing is blocked by expo-dev-client requirement (15min CI overhead), cross-platform test reuse requires abstraction layer complexity, and stress testing patterns for E2E are not well-documented. Mitigation strategy: Start with web E2E expansion (300+ tests), add mobile API-level tests instead of Detox for Phase 148, implement cross-platform orchestration with shared test data management, and defer full mobile Detox UI tests to Phase 150+ when infrastructure is ready.

## Key Findings

### Recommended Stack

**Summary from STACK.md**: Atom requires a layered testing approach building on existing v3.1 E2E infrastructure. Playwright is the foundation for web testing (already installed), with Detox for mobile (available), Tauri for desktop (built-in), and k6 for stress testing. pytest orchestrates all runners with Allure for unified reporting.

**Core technologies:**
- **Playwright (^1.57.0)** — Web E2E testing with auto-waiting, cross-browser support, tracing/debugging — Already configured with v3.1 E2E, excellent TypeScript support, built-in HTML reporter with traces
- **Detox (^20.47.0)** — React Native mobile E2E testing — Gray-box testing framework faster than black-box tools, already in mobile package.json, but BLOCKED by expo-dev-client requirement
- **k6 (^0.52.0)** — Load/stress testing — JS-based scripting, CI-friendly, supports HTTP/WebSocket, excellent for API stress testing, cost-effective bug discovery ($149/month for cloud scaling)
- **pytest (^7.4.0)** — Cross-platform orchestration — Already installed for backend tests, can orchestrate all E2E runners with fixtures, parallel execution via pytest-xdist
- **Allure Report (^2.27.0)** — Unified test reporting — Framework-agnostic, rich HTML reports with screenshots/videos, integrates with CI/CD, supports severity/suite/epic tags for bug tracking

**Integration with existing Atom infrastructure:**
- Backend API (FastAPI) for test data setup, agent operations
- Authentication (JWT) with API-first approach (bypass UI login for speed)
- Database (SQLite/PostgreSQL) with test isolation via worker-specific schemas
- CI/CD (GitHub Actions) with matrix strategy for parallel platform execution

### Expected Features

**Summary from FEATURES.md**: Atom already has v3.1 E2E with 30+ tests covering auth, agent execution, canvas, skills, governance, and WebSocket streaming. Critical gaps include stress testing, network simulation, mobile Detox E2E (blocked), desktop Tauri tests, and cross-platform test reuse framework.

**Must have (table stakes):**
- **Authentication Flow Tests** — Users expect secure login across all platforms (JWT validation, session persistence, logout, token refresh)
- **Agent Execution Critical Path** — Core product feature (spawn agent → send message → receive streaming response → verify output)
- **Canvas Presentation Tests** — Core differentiator (7 canvas types: charts, sheets, forms, docs, email, terminal, coding)
- **Test Isolation & Reproducibility** — Parallel execution requires isolated test data (unique IDs, database cleanup, fresh state per test)
- **API-First Authentication** — Speed optimization (100-500ms vs 10-60s UI login) by setting JWT token directly in localStorage
- **Failure Artifacts (Screenshots/Videos)** — Debugging failed tests requires visual evidence (Playwright: `screenshot: 'only-on-failure'`)
- **Database Isolation** — Parallel tests require separate data (worker-specific schemas, transaction rollbacks)

**Should have (competitive):**
- **Stress Testing for Bug Discovery** — Finds race conditions, memory leaks, resource exhaustion under load (concurrent agent executions, rapid canvas cycles, WebSocket churn)
- **Network Simulation Testing** — Tests app behavior under poor network conditions (Playwright `context.route()`, slow 3G, offline mode)
- **Visual Regression Testing (Percy)** — Detects unintended CSS/layout changes (already configured in v3.1 for 5 critical pages)
- **Real User Interaction Simulation** — Finds bugs from realistic user behavior (Playwright `userEvent` API, realistic delays, keyboard navigation)
- **WebSocket/Streaming Testing** — Validates real-time features under stress (multiple concurrent streams, connection drops, reconnection logic)

**Defer (v2+):**
- **Cross-Platform Test Reuse Framework** — Requires abstraction layer, platform-specific adapters
- **Mobile Detox E2E (Full UI)** — BLOCKED by expo-dev-client requirement (15min CI overhead)
- **Desktop Tauri Integration Tests** — Requires Tauri test infrastructure, GUI context in CI
- **Performance Regression Testing (Lighthouse CI)** — Requires performance budgets, monitoring setup

### Architecture Approach

**Summary from ARCHITECTURE.md**: Atom's existing architecture (Python backend, Next.js frontend, React Native mobile, Tauri desktop) provides solid foundation for E2E testing. Key components needed: test orchestration layer, shared test data management, stress testing infrastructure, and bug discovery tools.

**Major components:**
1. **Unified Test Runner** — Orchestrates test execution across platforms, manages parallelization, aggregates results (custom Node.js CLI or Python orchestrator calling platform-specific runners)
2. **Test Data Manager** — Creates, seeds, and cleans test data using fixtures, factories, and seed data (pytest fixtures + factory-boy + TestDataManager service)
3. **Web E2E Runner** — Executes browser-based tests with Playwright multi-browser support (Chromium, Firefox, WebKit)
4. **Mobile E2E Runner** — Executes React Native tests with Detox on iOS/Android simulators (gray-box testing, auto-wait mechanisms)
5. **Desktop E2E Runner** — Executes Tauri desktop tests using Playwright WebDriver protocol or CDP connection
6. **Stress Test Runner** — Generates load with k6/Locust, injects failures with chaos tools, validates performance degradation
7. **Bug Discovery Engine** — Analyzes test failures, generates reproducible test cases, documents bugs via GitHub Issues integration

**Key architectural patterns:**
- **Test Orchestration with Unified Runner**: Central coordination of cross-platform test execution with parallelization and result aggregation
- **Shared Test Data Management**: Centralized fixtures, factories, and seed data used across all E2E test platforms
- **Cross-Platform Test Reuse**: Share test logic across platforms using abstraction layers with platform-specific UI implementations
- **Stress Testing with Load Generation**: Concurrent user simulation, failure injection, and performance baseline tracking
- **Bug Discovery with Failure Analysis**: Automated analysis of test failures with GitHub Issues integration

### Critical Pitfalls

**Summary from PITFALLS.md**: Atom's existing backend testing has a 71.5 percentage point gap between service-level estimates (74.6%) and actual line coverage (8.50%), illustrating the critical methodology pitfall of coverage estimation without actual execution data. The highest-impact pitfalls focus on methodology errors, fixture leaks, testing anti-patterns, coverage gaming, and process failures.

1. **Service-Level Coverage Estimation Masking True Gaps** — Atom's episode services appeared at 74.6% estimated but actual line coverage was only 8.50% (71.5 point gap). Prevention: **ALWAYS use actual coverage.py execution data** with `pytest --cov=backend --cov-report=json`, require coverage JSON as source of truth, calculate coverage at function/line level not service level.

2. **Fixture Scope Leaks and Database Session Pollution** — Tests share database sessions or state due to incorrect pytest fixture scoping, causing passes in isolation but failures in parallel. Prevention: Use `scope="function"` for all database fixtures, use `yield` fixtures with cleanup code after yield, implement transaction rollback in teardown.

3. **Over-Mocking External Dependencies** — Tests mock everything (database, HTTP, LLM) and verify implementation details rather than behavior, creating brittle tests. Prevention: Only mock external services (LLM providers, S3), use real database (SQLite in-memory), test observable behavior (return values, DB state) not call sequences.

4. **Coverage Gaming - Excluding Untestable Code** — Adding `# pragma: no cover` to avoid testing difficult code (error handlers, async paths) inflates coverage while leaving critical paths untested. Prevention: Audit coverage exclusions quarterly, only exclude genuinely untestable code (generated protocols), require PR review for new pragmas.

5. **Flaky Tests Masking Real Issues** — Tests fail intermittently due to timing issues, race conditions, or async coordination but are marked as flaky and auto-retried. Prevention: Use `pytest-asyncio` with explicit event loop management, mock time-dependent code, use unique resource names for parallel tests, fix root cause don't add retries.

6. **Wrong Coverage Metrics - Line vs Branch Coverage** — Focusing only on line coverage (80% target) while ignoring branch coverage creates false confidence. Line coverage measures "lines executed" but branch coverage measures "decision outcomes tested." Prevention: **ALWAYS enable branch coverage** with `pytest --cov=backend --cov-branch`, set separate targets (80% line, 70% branch as Atom does).

7. **Async Testing Without Proper Event Loop Management** — Async tests without proper event loop configuration cause hangs or failures in parallel runs. Prevention: Use `pytest-asyncio` with `asyncio_mode = auto`, use `async def` for fixtures and tests, never manually create/close event loops.

8. **Test Data Factories Creating Duplicate Records** — Factories using hardcoded names or sequential IDs cause unique constraint violations in parallel pytest-xdist runs. Prevention: Use UUIDs or random suffixes for all unique fields, include worker ID in parallel tests, use database transactions with rollback.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Test Infrastructure Foundation
**Rationale:** Must establish test data management, shared utilities, and unified reporting before expanding test coverage. Without proper fixtures, factories, and isolation, adding tests creates maintenance burden.

**Delivers:** Test data manager with factory-boy factories, shared test utilities for common operations, unified reporter foundation aggregating existing test reports.

**Addresses:** Test Isolation & Reproducibility, Database Isolation, API-First Authentication

**Avoids:** Pitfall 2 (Fixture Scope Leaks), Pitfall 8 (Test Data Factories Creating Duplicates)

**Stack Elements:** pytest fixtures, factory-boy, SQLite in-memory, TestDataManager service

**Implements:** Shared Test Data Management architecture pattern

### Phase 2: Web E2E Expansion (300+ tests)
**Rationale:** Web is most critical platform and has existing Playwright infrastructure. Expanding from 30+ to 300+ tests covers all critical user flows before adding mobile/desktop complexity.

**Delivers:** Comprehensive web E2E test suite covering auth flows, agent interactions, workflow execution, canvas presentations (7 types), episodic memory flows.

**Addresses:** Authentication Flow Tests, Agent Execution Critical Path, Canvas Presentation Tests, Workflow Skill Execution

**Uses:** Playwright (existing), API-First Auth Fixtures, Test Data Manager

**Avoids:** Pitfall 3 (Over-Mocking), Pitfall 5 (Coverage Gaming), Anti-Pattern 1 (Testing Implementation Details)

**Implements:** Web E2E Runner architecture pattern

### Phase 3: Mobile API-Level Testing (defer Detox UI)
**Rationale:** Detox E2E is blocked by expo-dev-client requirement (15min CI overhead). API-level tests provide mobile workflow coverage without infrastructure complexity. Defer Detox UI tests to Phase 150+.

**Delivers:** Mobile API-level test suite covering auth, agent execution, workflows, device features (camera, location, notifications) via backend API calls.

**Addresses:** Cross-Platform Workflow Parity (Web + Mobile API), Authentication Flow Tests

**Uses:** pytest for backend API testing, existing mobile API endpoints

**Avoids:** Pitfall 7 (Async Event Loop Issues), Detox expo-dev-client blocker

**Implements:** Mobile API test patterns (defer Mobile E2E Runner to Phase 150+)

### Phase 4: Desktop Tauri Integration Tests
**Rationale:** Desktop testing requires Tauri test infrastructure and GUI context in CI. Add after web and mobile foundations are stable.

**Delivers:** Desktop E2E test suite covering window management, native features (file system, system tray), cross-platform behavior (Win/Mac/Linux).

**Addresses:** Desktop Tauri Integration Tests, Cross-Platform Workflow Parity

**Uses:** Tauri built-in testing (`cargo test`), Playwright with CDP connection or Tauri Driver

**Implements:** Desktop E2E Runner architecture pattern

### Phase 5: Cross-Platform Orchestration
**Rationale:** Once platform-specific tests exist, implement unified test runner for coordination, parallelization, and result aggregation. Doing this earlier would require constant refactoring as tests added.

**Delivers:** Unified test runner orchestrating web, mobile, and desktop tests with parallelization, cross-platform test reuse framework, CI/CD integration with GitHub Actions matrix strategy.

**Addresses:** Cross-Platform Test Reuse Framework, Parallel Test Execution, Unified Reporting

**Uses:** Test Orchestrator, pytest for orchestration, GitHub Actions matrix strategy

**Implements:** Test Orchestration with Unified Runner architecture pattern, Cross-Platform Test Reuse pattern

**Avoids:** Pitfall 2 (Fixture Scope Leaks), Pitfall 8 (Test Data Duplicates), Anti-Pattern 2 (Shared State Between Tests)

### Phase 6: Stress Testing & Bug Discovery
**Rationale:** Stress testing requires stable baseline E2E tests. Building on phases 2-5, this phase adds load generation and failure injection to find race conditions and memory leaks.

**Delivers:** Load generation with k6 (10, 50, 100 concurrent users), failure injection (network delays, DB drops), automated bug filing via GitHub Issues, performance degradation alerts.

**Addresses:** Stress Testing for Bug Discovery, Network Simulation Testing, WebSocket/Streaming Testing, Real User Interaction Simulation

**Uses:** k6 for load testing, Chaos tools for failure injection, Octokit for GitHub Issues integration

**Implements:** Stress Testing with Load Generation pattern, Bug Discovery with Failure Analysis pattern

**Avoids:** Pitfall 1 (Coverage Estimation False Positives), Pitfall 5 (Flaky Tests)

### Phase 7: Advanced Bug Discovery (v7.1)
**Rationale:** Once stress testing infrastructure is stable, add advanced bug discovery techniques for production-quality testing.

**Delivers:** Visual regression testing with Percy (expanded from 5 to 20+ pages), error boundary testing (401, 500, timeouts), performance regression testing with Lighthouse CI, memory leak detection with CDP.

**Addresses:** Visual Regression Testing, Error Boundary & Edge Case Testing, Performance Regression Testing, Memory Leak Detection

**Uses:** Percy (existing), Lighthouse CI, Chrome DevTools Protocol (CDP)

### Phase Ordering Rationale

- **Foundation first (Phase 1)**: Proper test data management, fixtures, and isolation prevents Pitfall 2 (fixture leaks) and Pitfall 8 (duplicate records) which cause flaky tests in parallel execution
- **Web before mobile/desktop (Phase 2 → 3 → 4)**: Web has existing infrastructure, is most critical platform, and establishes test patterns that can be reused for mobile/desktop
- **API-level mobile before Detox UI (Phase 3)**: Detox E2E blocked by expo-dev-client requirement, API-level tests provide mobile coverage without 15min CI overhead
- **Orchestration after platform tests (Phase 5)**: Unified runner requires stable platform-specific tests to orchestrate, building it earlier would require constant refactoring
- **Stress testing last (Phase 6)**: Stress testing requires stable baseline E2E tests, doing it earlier would waste effort on flaky tests
- **Advanced features deferred (Phase 7)**: Visual regression, performance testing, memory leak detection are differentiators but not critical for v7.0 launch

This order avoids Pitfall 5 (Flaky Tests Masking Real Issues) by establishing stable tests first, and Anti-Pattern 6 (E2E Tests for Everything) by focusing on critical paths only (10% E2E, 20% integration, 70% unit).

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 3 (Mobile API Testing)**: Mobile API-level testing patterns vs Detox E2E tradeoffs (speed, coverage, maintenance) — MEDIUM confidence, needs validation
- **Phase 4 (Desktop Tauri Tests)**: Tauri E2E testing patterns with Playwright CDP connection stability — MEDIUM confidence, limited production examples
- **Phase 5 (Cross-Platform Orchestration)**: Cross-platform test reuse abstractions, shared test logic strategies — MEDIUM confidence, emerging pattern
- **Phase 6 (Stress Testing)**: Stress test design patterns (concurrent execution scenarios, resource exhaustion), acceptable stress test failure rates — LOW confidence, industry standards unclear

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Test Infrastructure)**: Well-documented pytest patterns, factory-boy documentation — HIGH confidence
- **Phase 2 (Web E2E Expansion)**: Playwright official docs, existing Atom v3.1 E2E implementation — HIGH confidence
- **Phase 7 (Advanced Bug Discovery)**: Percy, Lighthouse CI, CDP documentation — HIGH confidence

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | **HIGH** | Web/pytest: HIGH (Playwright official docs, existing v3.1 implementation). Mobile/Desktop/Stress: MEDIUM (limited by web search rate limiting, Detox expo-dev-client blocker) |
| Features | **HIGH** | Based on official docs (Playwright, Detox, k6), existing Atom v3.1 E2E implementation (30+ tests, Percy), codebase analysis (61 shipped phases), industry best practices |
| Architecture | **HIGH** | Based on official docs (Playwright, Detox, Tauri, GitHub Actions, k6, factory-boy), existing Atom architecture (Python backend, Next.js frontend, React Native mobile, Tauri desktop), industry best patterns |
| Pitfalls | **HIGH** | Based on pytest/coverage.py official docs, existing Atom coverage analysis (71.5 point gap), Atom's pytest.ini configuration, conftest.py patterns, industry best practices |

**Overall confidence:** **HIGH** (mix of official documentation, existing implementation verification, codebase analysis, industry best practices)

### Gaps to Address

- **Stress test design patterns**: Need patterns for concurrent agent executions, rapid canvas iterations, WebSocket churn scenarios — MEDIUM confidence, limited E2E stress testing examples
- **Cross-platform test reuse abstractions**: Need to design framework for shared workflow definitions, platform adapters — MEDIUM confidence, emerging pattern with few production examples
- **Mobile API-level testing vs Detox E2E**: Need to validate API-level approach tradeoffs (speed, coverage, maintenance) — MEDIUM confidence, defer Detox to Phase 150+ due to expo-dev-client blocker
- **Tauri Playwright integration stability**: Need to validate CDP connection patterns for desktop E2E — MEDIUM confidence, limited production examples
- **Automated bug filing thresholds**: Risk of GitHub Issues noise, false positives in automated bug filing — need to define reproduction criteria (2+ failures)

**How to handle during planning/execution:**
- Phase-specific `/gsd:research-phase` for stress test design (Phase 6), cross-platform test reuse (Phase 5), Tauri integration (Phase 4)
- Validation spikes for mobile API-level testing patterns (Phase 3) before committing to approach
- Conservative bug filing thresholds (require 3+ reproductions) to avoid GitHub Issues noise
- Incremental implementation: start with web E2E (Phase 2) before adding cross-platform complexity

## Sources

### Primary (HIGH confidence)
- [Playwright Python Documentation](https://playwright.dev/python/) - Authoritative E2E testing patterns, auto-waiting, selectors
- [Atom E2E Testing Guide](/Users/rushiparikh/projects/atom/docs/E2E_TESTING_GUIDE.md) - Comprehensive E2E setup, patterns, troubleshooting (March 7, 2026)
- [Atom v3.1 E2E Implementation](/Users/rushiparikh/projects/atom/backend/tests/e2e_ui/) - 30+ production E2E tests, fixtures, page objects, flaky test detection
- [pytest Fixtures Documentation](https://docs.pytest.org/en/stable/how-to/fixtures.html) - Fixture scopes, teardown, finalizers, yield patterns
- [Coverage.py Documentation](https://coverage.readthedocs.io/) - Line vs branch coverage, exclude patterns, reporting
- [Atom Backend Coverage Reports](/Users/rushiparikh/projects/atom/backend/coverage.json) - Actual coverage data: episode_segmentation_service.py at 27.41% line coverage
- [Atom pytest.ini Configuration](/Users/rushiparikh/projects/atom/backend/pytest.ini) - Flaky test reruns, branch coverage enabled
- [Detox Documentation](https://wix.github.io/Detox/) - React Native gray-box E2E testing framework
- [k6 Documentation](https://k6.io/docs/) - Load testing and stress testing framework
- [Tauri Testing Guide](https://tauri.app/v1/guides/testing/) - Official Tauri testing documentation

### Secondary (MEDIUM confidence)
- Atom CI/CD Pipeline - GitHub Actions workflows, deployment automation, health checks
- Atom Monitoring Setup - `/Users/rushiparikh/projects/atom/backend/docs/MONITORING_SETUP.md` - Health check endpoints, Prometheus metrics
- Atom Deployment Runbook - `/Users/rushiparikh/projects/atom/backend/docs/DEPLOYMENT_RUNBOOK.md` - Deployment procedures, rollback strategies
- Percy Documentation - Visual regression testing best practices
- pytest-xdist Documentation - Parallel test execution, worker isolation
- Factory Boy Documentation - Test data factory patterns
- Cross-Platform Testing Patterns - Shared test logic across platforms, platform-specific abstractions
- Stress Testing Best Practices - Load generation, failure injection, chaos engineering

### Tertiary (LOW confidence)
- Stress testing patterns for E2E - Limited examples of stress testing in E2E suites (most use separate load testing tools)
- Network simulation in E2E - Playwright `context.route()` documented, but production patterns not widely available
- Cross-platform test reuse frameworks - Emerging pattern, few production examples of shared test logic across platforms
- Mobile Detox E2E best practices - BLOCKED by expo-dev-client requirement, deferred to Phase 150+
- Tauri Playwright integration - Tauri supports CDP but Playwright driver stability unknown

---
*Research completed: March 23, 2026*
*Ready for roadmap: yes*
