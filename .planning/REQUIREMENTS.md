# Requirements: Atom v7.0 - Cross-Platform E2E Testing & Bug Discovery

**Defined:** 2026-03-23
**Core Value:** Cross-platform user flows work reliably across web, mobile, and desktop with comprehensive bug discovery through E2E testing

## v1 Requirements

Requirements for v7.0 milestone. Each maps to roadmap phases.

### Authentication (AUTH)

- [ ] **AUTH-01**: User can log in via web UI with email and password (JWT token validation)
- [ ] **AUTH-02**: User session persists across browser refresh (localStorage JWT verification)
- [ ] **AUTH-03**: User can log out via web UI (token invalidation)
- [ ] **AUTH-04**: Protected routes redirect to login if not authenticated (web UI)
- [ ] **AUTH-05**: JWT token refresh works on expiry (automatic re-authentication)
- [ ] **AUTH-06**: API-first authentication bypasses UI login (100-500ms vs 10-60s)
- [ ] **AUTH-07**: Authentication tests work across web, mobile (API-level), and desktop platforms

### Agent Execution (AGNT)

- [ ] **AGNT-01**: User can spawn agent via web UI (agent creation flow)
- [ ] **AGNT-02**: Agent appears in agent registry after creation (verification)
- [ ] **AGNT-03**: User can send chat message to agent (web UI interaction)
- [ ] **AGNT-04**: Agent returns streaming response (WebSocket validation)
- [ ] **AGNT-05**: Agent output displays correctly in chat interface (rendering verification)
- [ ] **AGNT-06**: Multiple agents can be spawned concurrently (parallel execution)
- [ ] **AGNT-07**: Agent tests work on web (Playwright), mobile (API), and desktop (Tauri)
- [ ] **AGNT-08**: WebSocket reconnection logic works on connection drop (error handling)

### Canvas & Presentation (CANV)

- [ ] **CANV-01**: Chart canvas renders correctly (line, bar, pie charts)
- [ ] **CANV-02**: Sheet canvas displays data grid (pagination, sorting)
- [ ] **CANV-03**: Form canvas validates input and submits (required fields, error messages)
- [ ] **CANV-04**: Docs canvas renders markdown content (formatting, links)
- [ ] **CANV-05**: Email canvas drafts and sends (to, subject, body validation)
- [ ] **CANV-06**: Terminal canvas executes commands (output verification)
- [ ] **CANV-07**: Coding canvas displays code with syntax highlighting
- [ ] **CANV-08**: All canvas types are interactive (click, type, close)
- [ ] **CANV-09**: Canvas state is accessible via ARIA hidden trees (window.atom.canvas.getState())
- [ ] **CANV-10**: Rapid canvas present/close cycles work (stress testing)
- [ ] **CANV-11**: Canvas tests work across web, mobile (API), and desktop platforms

### Workflow & Skill Automation (WORK)

- [ ] **WORK-01**: User can install skill via web UI (skill installation flow)
- [ ] **WORK-02**: Skill appears in skill registry after installation (verification)
- [ ] **WORK-03**: User can execute skill with parameters (API-level testing)
- [ ] **WORK-04**: Skill output parses correctly (JSON response validation)
- [ ] **WORK-05**: Skill business logic executes correctly (side effects verification)
- [ ] **WORK-06**: User can create workflow with multiple skills (workflow composition)
- [ ] **WORK-07**: Workflow DAG validates correctly (acyclic graph verification)
- [ ] **WORK-08**: Workflow executes skills in correct order (orchestration verification)
- [ ] **WORK-09**: Workflow triggers fire correctly (manual, scheduled, event-based)
- [ ] **WORK-10**: Workflow tests work on web, mobile (API), and desktop platforms

### Cross-Platform Infrastructure (INFRA)

- [ ] **INFRA-01**: Tests have isolated data (unique IDs per test, UUID suffixes)
- [ ] **INFRA-02**: Tests run in parallel (pytest-xdist, 4 workers)
- [ ] **INFRA-03**: Database isolation works (worker-specific schemas, transaction rollbacks)
- [ ] **INFRA-04**: Failed tests capture screenshots (Playwright screenshot: 'only-on-failure')
- [ ] **INFRA-05**: Failed tests capture videos (Playwright video: 'retain-on-failure')
- [ ] **INFRA-06**: Test fixtures are reusable (factory-boy factories, pytest fixtures)
- [ ] **INFRA-07**: Test cleanup runs after each test (yield fixtures, teardown)
- [ ] **INFRA-08**: Cross-platform tests use consistent test IDs (data-testid/testID)
- [ ] **INFRA-09**: Unified test runner orchestrates web, mobile, and desktop tests
- [ ] **INFRA-10**: Allure reporting aggregates results from all platforms

### Stress Testing & Bug Discovery (STRESS)

- [ ] **STRESS-01**: Load testing with k6 simulates 10 concurrent users (baseline)
- [ ] **STRESS-02**: Load testing with k6 simulates 50 concurrent users (moderate load)
- [ ] **STRESS-03**: Load testing with k6 simulates 100 concurrent users (high load)
- [ ] **STRESS-04**: Network simulation tests slow 3G connection (Playwright context.route())
- [ ] **STRESS-05**: Network simulation tests offline mode (app behavior without network)
- [ ] **STRESS-06**: Failure injection tests database connection drops (error handling)
- [ ] **STRESS-07**: Failure injection tests API timeouts (504 gateway timeout)
- [ ] **STRESS-08**: Memory leak detection uses CDP heap snapshots (before/after comparison)
- [ ] **STRESS-09**: Performance regression testing with Lighthouse CI (page load budgets)
- [ ] **STRESS-10**: Automated bug filing creates GitHub Issues for reproducible failures
- [ ] **STRESS-11**: Stress tests run on schedule (nightly/weekly CI jobs)

### Mobile & Desktop Testing (MOBILE)

- [ ] **MOBILE-01**: Mobile API-level tests authenticate via backend endpoints
- [ ] **MOBILE-02**: Mobile API-level tests execute agent operations (chat, streaming)
- [ ] **MOBILE-03**: Mobile API-level tests execute workflow operations (install skills, trigger workflows)
- [ ] **MOBILE-04**: Mobile device features work (camera, location, notifications - API-level)
- [ ] **MOBILE-05**: Desktop Tauri tests verify window management (open, close, minimize, maximize)
- [ ] **MOBILE-06**: Desktop Tauri tests verify native features (file system, system tray)
- [ ] **MOBILE-07**: Desktop tests work cross-platform (Windows, macOS, Linux)

### Visual Regression & Accessibility (A11Y)

- [ ] **A11Y-01**: Percy visual regression tests cover 5 critical pages (existing from v3.1)
- [ ] **A11Y-02**: Percy visual regression tests expand to 20+ pages (comprehensive coverage)
- [ ] **A11Y-03**: Canvas accessibility trees expose state to screen readers (ARIA validation)
- [ ] **A11Y-04**: jest-axe tests verify WCAG 2.1 AA compliance (frontend accessibility)
- [ ] **A11Y-05**: Color contrast meets WCAG AA standards (4.5:1 for normal text)
- [ ] **A11Y-06**: Keyboard navigation works for all interactive elements (Tab, Enter, Escape)
- [ ] **A11Y-07**: Focus indicators are visible for all interactive elements

## v2 Requirements

Deferred to v7.1+ milestone. Tracked but not in current roadmap.

### Advanced Features

- **AUTH-08**: Biometric auth testing (Face ID/Touch ID on mobile)
- **AUTH-09**: OAuth integration testing (Google, GitHub)
- **AUTH-10**: SSO (Single Sign-On) testing
- **MOBILE-08**: Detox E2E UI tests for React Native (deferred - expo-dev-client blocked)
- **INFRA-11**: Cross-platform test reuse framework (shared workflow definitions, platform adapters)
- **STRESS-12**: WebSocket stress testing with connection churn patterns
- **STRESS-13**: Chaos engineering with random failure injection

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Mobile Detox E2E UI tests | BLOCKED by expo-dev-client requirement (15min CI overhead), deferred to Phase 150+ |
| E2E tests for edge cases | Better suited for unit/integration tests (faster feedback loop) |
| Testing third-party libraries | Don't test what React, Next.js, Chakra UI authors already test |
| Brittle CSS selector tests | Use data-testid attributes instead (stable across refactors) |
| Testing implementation details | Test user-facing behavior, not internal component structure |
| Shared state between tests | Causes non-deterministic failures, each test must be isolated |
| Hard-coded waits (time.sleep) | Use explicit waits and Playwright auto-waiting instead |
| Performance regression budgets (v7.0) | Defer to v7.1+ after happy path E2E tests stable |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 through AUTH-07 | Phase 234 | Pending |
| AGNT-01 through AGNT-08 | Phase 234 | Pending |
| CANV-01 through CANV-11 | Phase 235 | Pending |
| WORK-01 through WORK-10 | Phase 235 | Pending |
| INFRA-01 through INFRA-10 | Phase 233 | Pending |
| STRESS-01 through STRESS-11 | Phase 236 | Pending |
| MOBILE-01 through MOBILE-07 | Phase 236 | Pending |
| A11Y-01 through A11Y-07 | Phase 236 | Pending |

**Coverage:**
- v1 requirements: 58 total
- Mapped to phases: 58
- Unmapped: 0 ✓

**Requirement Count by Category:**
- Authentication (AUTH): 7 requirements
- Agent Execution (AGNT): 8 requirements
- Canvas & Presentation (CANV): 11 requirements
- Workflow & Skill Automation (WORK): 10 requirements
- Cross-Platform Infrastructure (INFRA): 10 requirements
- Stress Testing & Bug Discovery (STRESS): 11 requirements
- Mobile & Desktop Testing (MOBILE): 7 requirements
- Visual Regression & Accessibility (A11Y): 7 requirements

---
*Requirements defined: 2026-03-23*
*Last updated: 2026-03-23 after roadmap creation (v7.0)*