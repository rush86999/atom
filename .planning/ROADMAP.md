# Roadmap: Atom E2E UI Testing Initiative

## 📋 Additional Roadmap

**Feature Development**: See [FEATURE_ROADMAP.md](./FEATURE_ROADMAP.md) for OpenClaw integration (IM adapters, local shell access, agent social layer, simplified installer).

---

## Overview

Comprehensive end-to-end testing initiative for Atom platform covering critical user workflows with Playwright. The roadmap follows a workflow-first approach: establish test infrastructure with fixtures and isolation, validate authentication flows, test agent chat and streaming, verify canvas presentations, test skills and workflows, and implement quality gates for production confidence.

**Milestone v3.1**: E2E UI Testing with Playwright for critical user workflows.

---

## Current Milestone: v3.1 E2E UI Testing

**Goal:** Implement comprehensive end-to-end UI tests with Playwright covering authentication, agent chat, canvas presentations, skills, and workflows with production-ready quality gates.

**Started:** 2026-02-23

**Phases:** 6 (75-80)

**Status:** Phase 75 - Test Infrastructure & Fixtures (READY TO START)

---

## Completed Milestones

### Milestone v1.0: Test Infrastructure & Property-Based Testing

**Timeline:** Phase 1-28

**Achievements:**
- 200/203 plans complete (99% completion)
- 81 tests passing in Phase 28
- Production-ready codebase with comprehensive testing infrastructure
- Property-based testing framework established with Hypothesis
- Integration test infrastructure with pytest-asyncio
- Browser automation tests (17 tests)
- Governance performance tests
- 15.87% coverage achieved (216% improvement from 4.4% baseline)

### Milestone v2.0: Feature Integration & Coverage Expansion

**Timeline:** Phase 29-74

**Achievements:**
- Community Skills Integration (Phase 14) - 5,000+ OpenClaw skills with Docker sandbox
- Agent Layer Testing (Phase 17) - Governance, graduation, execution
- Python Package Support (Phase 35) - 7 plans, security scanning, isolation
- npm Package Support (Phase 36) - 7 plans, package governance
- Advanced Skill Execution (Phase 60) - Marketplace, composition, E2E security
- Atom SaaS Marketplace Sync (Phase 61) - Real-time sync, WebSocket integration
- 80% Test Coverage Achievement (Phase 62) - Coverage analysis and strategy
- E2E Test Suite (Phase 64) - Docker environment, real service integration
- Personal Edition Enhancements (Phase 66) - Media, creative, smart home
- CI/CD Pipeline Fixes (Phase 67) - Comprehensive documentation and runbooks
- BYOK Cognitive Tier System (Phase 68) - 5-tier routing, cache optimization
- Autonomous Coding Agents (Phase 69) - Full SDLC implementation, 10 plans

**v2.0 Legacy Phases Archive:**
- Phases 29-74 are archived in ROADMAP.backup.md for historical reference
- All 46 plans completed successfully
- Production-ready codebase with comprehensive testing infrastructure

---

## Current Phases

**Phase Numbering:**
- Integer phases (75, 76, 77): Planned milestone work
- Decimal phases (75.1, 75.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 75: Test Infrastructure & Fixtures** - Playwright setup with fixtures, browser contexts, test data factories, database isolation, and configuration
- [ ] **Phase 76: Authentication & User Management** - Login, session persistence, logout, settings, and project management flows
- [ ] **Phase 77: Agent Chat & Streaming** - Chat interface, streaming responses, WebSocket connections, governance enforcement, and execution history
- [ ] **Phase 78: Canvas Presentations** - Canvas creation, component rendering, form submission, state API, accessibility, and dynamic content
- [ ] **Phase 79: Skills & Workflows** - Skill marketplace, installation, configuration, execution, and uninstallation
- [ ] **Phase 80: Quality Gates & CI/CD Integration** - Screenshots, videos, retries, flaky test detection, pass rate validation, and HTML reports

---

## Phase Details

### Phase 75: Test Infrastructure & Fixtures

**Goal**: Playwright environment is established with fixtures, browser contexts, test data factories, database isolation, and Docker configuration

**Depends on**: Nothing (first phase of v3.1)

**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, INFRA-07

**Success Criteria** (what must be TRUE):
  1. Developer can run tests with `pytest tests/e2e_ui/` and see Playwright browser execute tests
  2. Tests use fixtures for authenticated browser contexts, page objects, and test data
  3. Tests generate unique data per worker with UUID v4 to prevent parallel execution collisions
  4. Tests can use API-first setup for fast state initialization (bypassing UI for data setup)
  5. Database isolation ensures each test worker has separate database schema with rollback on cleanup
  6. Docker Compose environment starts all services (backend, frontend, PostgreSQL) for testing
  7. Playwright configuration includes base URL, browsers (Chromium, Firefox, WebKit), timeout settings, and retries

**Plans**: 7 plans in 2 waves

**Wave 1** (parallel): 75-01, 75-02, 75-03, 75-04, 75-05, 75-06
- [ ] 75-01-PLAN.md — Create E2E UI test directory and configuration files (conftest.py, pyproject.toml, playwright.config.ts)
- [ ] 75-02-PLAN.md — Create authentication fixtures and Page Object classes (auth_fixtures.py, page_objects.py)
- [ ] 75-03-PLAN.md — Create test data factories for unique, realistic test data (test_data_factory.py)
- [ ] 75-04-PLAN.md — Create worker-based database isolation fixtures (database_fixtures.py)
- [ ] 75-05-PLAN.md — Create API-first setup utilities for fast test state initialization (api_setup.py)
- [ ] 75-06-PLAN.md — Create Docker Compose environment for E2E UI testing (docker-compose-e2e-ui.yml, scripts)

**Wave 2**: 75-07 (depends on Wave 1 fixture creation)
- [ ] 75-07-PLAN.md — Update Playwright to 1.58.0 and finalize configuration (requirements.txt, pytest.ini, conftest.py updates)
  - Depends on: 75-01 (conftest.py), 75-02 (auth_fixtures), 75-03 (test_data_factory), 75-04 (database_fixtures), 75-05 (api_setup)

---

### Phase 76: Authentication & User Management

**Goal**: User can authenticate, manage sessions, update settings, and create projects through the UI

**Depends on**: Phase 75 (test infrastructure)

**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05

**Success Criteria** (what must be TRUE):
  1. User can log in via email and password through the login form
  2. User session persists across browser refresh (JWT token stored and validated)
  3. User can log out and session is cleared (token removed, redirected to login)
  4. User can access settings page and update preferences (theme, notifications, etc.)
  5. User can create new project and see it in project list
  6. User can edit and delete projects with proper confirmation dialogs

**Plans**: 5 plans in 2 waves

**Wave 1** (parallel): 076-01, 076-02, 076-03, 076-04
- [ ] 076-01-PLAN.md — Login flow E2E tests (valid credentials, invalid credentials, empty fields, remember me)
- [ ] 076-02-PLAN.md — Session persistence tests (refresh, protected routes, token expiration, multiple tabs)
- [ ] 076-03-PLAN.md — Logout flow tests (via menu, session clear, redirect, protected route blocking)
- [ ] 076-04-PLAN.md — Settings page tests (access, theme toggle, notifications, persistence)

**Wave 2**: 076-05 (depends on 076-01 for LoginPage pattern)
- [ ] 076-05-PLAN.md — Project management tests (create, edit, delete with confirmation, project list)

---

### Phase 77: Agent Chat & Streaming

**Goal**: User can interact with agents through chat interface with streaming responses and governance enforcement

**Depends on**: Phase 76 (authentication)

**Requirements**: AGENT-01, AGENT-02, AGENT-03, AGENT-04, AGENT-05, AGENT-06

**Success Criteria** (what must be TRUE):
  1. User can send chat message to agent through chat input and see message in chat history
  2. Agent response is displayed token-by-token via streaming (WebSocket connection verified)
  3. WebSocket connection is established for streaming (connection lifecycle tested)
  4. Governance enforcement blocks STUDENT agent from restricted actions (error message shown)
  5. INTERN agent requires approval before executing actions (approval dialog displayed)
  6. Agent execution history is displayed in chat interface (timestamp, status, result)

**Plans**: 6 plans in 2 waves

**Wave 1** (parallel): 077-01, 077-02, 077-03, 077-04
- [ ] 077-01-PLAN.md — Chat Interface Page Object (ChatPage with locators and methods)
- [ ] 077-02-PLAN.md — Chat message sending tests (AGENT-01: send, history, empty input, persistence)
- [ ] 077-03-PLAN.md — WebSocket connection lifecycle tests (AGENT-03: connect, events, disconnect, reconnect)
- [ ] 077-04-PLAN.md — Streaming response tests (AGENT-02: token-by-token, completion, indicator, errors)

**Wave 2**: 077-05, 077-06 (depends on Wave 1 Page Objects and tests)
- [ ] 077-05-PLAN.md — Governance enforcement tests (AGENT-04, AGENT-05: STUDENT blocking, INTERN approval, SUPERVISED auto-execute)
- [ ] 077-06-PLAN.md — Agent execution history tests (AGENT-06: display, timestamp, status, persistence)

---

### Phase 78: Canvas Presentations

**Goal**: User can create and interact with canvas presentations with forms, charts, and accessibility features

**Depends on**: Phase 77 (agent chat)

**Requirements**: CANVAS-01, CANVAS-02, CANVAS-03, CANVAS-04, CANVAS-05, CANVAS-06

**Success Criteria** (what must be TRUE):
  1. User can create new canvas presentation from agent chat or directly
  2. Canvas components render correctly (charts display data, markdown formatted, forms functional)
  3. User can submit canvas form and validation works (error messages, success feedback)
  4. Canvas state API (window.atom.canvas.getState) returns correct data structure
  5. AI accessibility tree exposes canvas state via role='log' and aria-live attributes
  6. Dynamic content loads correctly with auto-waiting (no flaky waits, proper selectors)

**Plans**: TBD

---

### Phase 79: Skills & Workflows

**Goal**: User can browse, install, configure, execute, and uninstall skills through the UI

**Depends on**: Phase 78 (canvas presentations)

**Requirements**: SKILL-01, SKILL-02, SKILL-03, SKILL-04, SKILL-05

**Success Criteria** (what must be TRUE):
  1. User can browse skill marketplace with search and category filters
  2. User can install skill from marketplace and see it in installed skills list
  3. User can configure skill settings (API keys, options, preferences)
  4. User can execute skill and verify output (result displayed, errors handled)
  5. User can uninstall skill and it's removed from installed list

**Plans**: TBD

---

### Phase 80: Quality Gates & CI/CD Integration

**Goal**: Test suite has quality gates for screenshots, videos, retries, flaky test detection, pass rate validation, and HTML reports

**Depends on**: Phase 79 (all workflows tested)

**Requirements**: QUAL-01, QUAL-02, QUAL-03, QUAL-04, QUAL-05, QUAL-06

**Success Criteria** (what must be TRUE):
  1. Screenshots are captured on test failure and saved to artifacts directory
  2. Video recordings are captured on test failure in CI environment only
  3. Tests retry up to 2 times on failure in CI environment only
  4. Flaky test detection identifies unstable tests across multiple runs
  5. Test suite achieves 100% pass rate on 3 consecutive runs (quality gate)
  6. HTML test reports are generated with screenshots embedded for failed tests

**Plans**: TBD

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 75. Test Infrastructure & Fixtures | 0/7 | Ready to start | - |
| 76. Authentication & User Management | 0/5 | Not started | - |
| 77. Agent Chat & Streaming | 0/6 | Planned | - |
| 78. Canvas Presentations | 0/6 | Not started | - |
| 79. Skills & Workflows | 0/5 | Not started | - |
| 80. Quality Gates & CI/CD Integration | 0/6 | Not started | - |

**Overall Progress**: 0/41 plans complete (0%)

**Phase 75 Breakdown** (7 plans, 2 waves):
- Wave 1 (6 plans, parallel): 75-01, 75-02, 75-03, 75-04, 75-05, 75-06 — Configuration, fixtures, factories, database isolation, API setup, Docker environment
- Wave 2 (1 plan): 75-07 — Playwright update and final configuration (depends on fixture creation from Wave 1)

**Phase 77 Breakdown** (6 plans, 2 waves):
- Wave 1 (4 plans, parallel): 077-01, 077-02, 077-03, 077-04 — ChatPage PO, message sending, WebSocket lifecycle, streaming responses
- Wave 2 (2 plans): 077-05, 077-06 — Governance enforcement, execution history (depends on Wave 1)

---

## Coverage Summary

**v3.1 Requirements**: 37 total
- Test Infrastructure: 7 requirements
- Authentication & User Management: 5 requirements
- Agent Chat & Streaming: 6 requirements
- Canvas Presentations: 6 requirements
- Skills & Workflows: 5 requirements
- Quality Gates: 6 requirements

**Coverage**: 100% (37/37 requirements mapped to phases 75-80)

---

## Out of Scope (v3.1)

Explicitly excluded from v3.1 to maintain focus. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Multi-agent orchestration E2E tests | HIGH complexity, requires separate research phase (v3.2) |
| Agent graduation criteria E2E tests | Defer to v3.2 after core workflows stable |
| Browser automation tool E2E tests | Covered in Phase 64 (backend E2E), UI not critical path |
| Visual regression tests | High maintenance burden, defer to v3.2 |
| Cross-browser tests (Firefox, Safari) | 3x execution time, Chromium only for v3.1 |
| Performance regression tests | Defer to v3.2 |
| Parallel execution optimization | Defer to v3.2 after tests stable |
| Load testing | Beyond E2E scope, separate initiative |
| Chaos engineering | Resilience testing, defer to future |
| Mobile E2E | React Native testing is different skillset, defer to mobile milestone |

---

## Research Context

Based on comprehensive E2E testing research (research/SUMMARY.md), v3.1 focuses on Playwright-based UI testing for critical user workflows. Research findings:

**Recommended Approach:**
- Playwright Python 1.58.0 with pytest-playwright plugin
- Docker Compose test environment with backend, frontend, PostgreSQL
- Test fixtures for authentication, browser context, page objects
- Worker-based database isolation for parallel execution
- API-first test setup utilities for fast state initialization
- Quality gates with screenshots, videos, retries, flaky test detection

**Critical Success Factors:**
- Test independence (no shared state between tests)
- Fast execution (<30s per test, <10min full suite)
- Reliable selectors (data-testid attributes over CSS/XPath)
- Proper async coordination (auto-waiting, explicit waits)
- Parallel execution from day one (catches state sharing issues)

**Research-Validated Patterns:**
- Page Object Model for UI abstractions
- Fixture-based test data generation (factory_boy pattern)
- Transaction rollback for database isolation
- API-first setup for expensive state initialization
- Retry logic with exponential backoff for flaky network operations

---

*Last updated: 2026-02-23*
*Milestone: v3.1 E2E UI Testing*
*Next action: Plan Phase 75 (/gsd:plan-phase 75)*
