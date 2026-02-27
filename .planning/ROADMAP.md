# Roadmap: Atom Test Coverage Initiative

## Overview

Atom's testing initiative achieves 80% overall code coverage through systematic expansion targeting highest-impact files first. The journey begins with coverage analysis and gap identification, then expands backend core services, API routes, and business logic with property-based tests. Frontend coverage follows with component, state management, and integration tests. Quality gates enforce the 80% threshold with automated PR comments and coverage dashboards.

## Milestones

- ✅ **v1.0 Test Infrastructure** - Phases 1-28 (shipped)
- ✅ **v2.0 Feature Integration** - Phases 29-74 (shipped)
- ✅ **v3.1 E2E UI Testing** - Phases 75-80 (shipped 2026-02-24)
- ✅ **v3.2 Bug Finding & Coverage Expansion** - Phases 81-90 (shipped 2026-02-26)
- ✅ **v3.3 Finance Testing & Bug Fixes** - Phases 91-94 (shipped 2026-02-26)
- ✅ **v4.0 Platform Integration & Property Testing** - Phases 95-99 (shipped 2026-02-27)
- 🚧 **v5.0 Coverage Expansion** - Phases 100-110 (in progress)

## Phases

<details>
<summary>✅ v4.0 Platform Integration & Property Testing (Phases 95-99) - SHIPPED 2026-02-27</summary>

### Phase 95: Backend + Frontend Integration
**Goal**: Backend and frontend have unified coverage aggregation, frontend integration tests cover component interactions and API contracts, FastCheck property tests validate frontend invariants
**Plans**: 8 plans

### Phase 96: Mobile Integration
**Goal**: Mobile app has integration tests for device features, offline sync, and platform permissions, FastCheck property tests validate mobile invariants
**Plans**: 7 plans

### Phase 97: Desktop Testing
**Goal**: Desktop apps (Tauri) have integration tests for native APIs and system integration, Rust and JavaScript property tests validate desktop invariants
**Plans**: 7 plans

### Phase 98: Property Testing Expansion
**Goal**: All platforms have comprehensive property tests for critical invariants, property testing patterns documented and reusable
**Plans**: 6 plans

### Phase 99: Cross-Platform Integration & E2E
**Goal**: Cross-platform integration tests verify feature parity, E2E user flows validate complete workflows from UI to backend
**Plans**: 8 plans

**Total Impact (v4.0):**
- 1,048+ tests created (241 integration + 361 property + 42 E2E + 404 other)
- 1,642 total tests passing (100% pass rate)
- 20.81% overall coverage (21.67% backend, 3.45% frontend, 16.16% mobile)
- 36 plans executed across 5 phases
- Lighthouse CI performance budgets enforced
- Percy visual regression testing operational

</details>

### 🚧 v5.0 Coverage Expansion (In Progress)

**Milestone Goal:** Achieve 80% overall test coverage through systematic expansion targeting highest-impact files first

**Strategy:** Backend (Phases 101-104) → Frontend (Phases 105-109) → Quality Gates (Phase 110)

- ✅ **Phase 100: Coverage Analysis** - Establish baseline coverage, identify gaps, and prioritize high-impact files (2026-02-27)
- [ ] **Phase 101: Backend Core Services Unit Tests** ⚠️ PARTIAL - Tests created but coverage target not met (mock configuration issues)
- [ ] **Phase 102: Backend API Integration Tests** - Cover all API routes with request/response validation and error handling
- [ ] **Phase 103: Backend Property-Based Tests** - Validate business logic invariants using Hypothesis property-based testing
- [ ] **Phase 104: Backend Error Path Testing** - Comprehensive error path and edge case tests for critical services
- [ ] **Phase 105: Frontend Component Tests** - React Testing Library achieves 50%+ coverage for all components
- [ ] **Phase 106: Frontend State Management Tests** - Validate Redux/Zustand store logic and state transitions
- [ ] **Phase 107: Frontend API Integration Tests** - Mock backend and verify error handling for all API calls
- [ ] **Phase 108: Frontend Property Tests** - FastCheck property tests validate state machine invariants
- [ ] **Phase 109: Frontend Form Validation Tests** - Comprehensive form validation tests covering all form components with edge cases
- [ ] **Phase 110: Quality Gates & Reporting** - Automated coverage enforcement with PR comments, trend dashboards, and per-commit reports

## Phase Details

### ✅ Phase 100: Coverage Analysis (COMPLETE)
**Goal**: Establish baseline coverage, identify gaps, and prioritize high-impact files
**Depends on**: Phase 99
**Requirements**: COVR-01, COVR-02, COVR-03
**Success Criteria** (what must be TRUE):
  1. Coverage report identifies all files below 80% with business impact scores (critical/high/medium/low)
  2. Prioritized file list ranks files by (lines × impact_weight / current_coverage) for maximum coverage gain
  3. Coverage trend tracking system tracks per-commit coverage changes with baseline established
  4. Team can view coverage gap dashboard showing current state (Backend: 21.67%, Frontend: 3.45%, Overall: 20.81%)
**Plans**: 5 plans

Plans:
- [x] 100-01-PLAN.md — Coverage baseline report generation with per-file breakdown
- [x] 100-02-PLAN.md — Business impact scoring for all files (critical/high/medium/low)
- [x] 100-03-PLAN.md — High-impact file prioritization ranking (lines × impact / coverage)
- [x] 100-04-PLAN.md — Coverage trend tracking system setup
- [x] 100-05-PLAN.md — Phase verification and metrics summary

### Phase 101: Backend Core Services Unit Tests ⚠️ PARTIAL
**Goal**: Achieve 60%+ coverage for low-coverage core services (governance, episodes, canvas)
**Depends on**: Phase 100
**Requirements**: BACK-01
**Success Criteria** (what must be TRUE):
  1. Agent governance service (agent_governance_service.py) has 60%+ coverage with maturity routing tests
  2. Episode services (segmentation, retrieval, lifecycle) have 60%+ coverage with memory operations
  3. Canvas services (canvas_tool, agent_guidance_canvas) have 60%+ coverage with presentation tests
  4. All unit tests use property-based testing for invariants (e.g., governance cache <1ms lookup)
**Status**: ⚠️ PARTIAL - 182 tests created but coverage target not met (0/4 criteria)
**Plans**: 5 plans

Plans:
- [x] 101-01-PLAN.md — Agent governance service unit tests (46 tests created, 10.39% coverage)
- [x] 101-02-PLAN.md — Episode services unit tests (70 tests created, 9.37% avg coverage)
- [x] 101-03-PLAN.md — Canvas services unit tests (66 tests created, 9.24% avg coverage)
- [ ] 101-04-PLAN.md — Property-based invariants testing for core services (tests exist, execution not verified)
- [x] 101-05-PLAN.md — Phase verification and coverage metrics ✅

**Issues**: Mock configuration blocking test execution, 0% coverage improvement, see 101-VERIFICATION.md

### Phase 102: Backend API Integration Tests
**Goal**: Cover all API routes with request/response validation and error handling
**Depends on**: Phase 101
**Requirements**: BACK-02
**Success Criteria** (what must be TRUE):
  1. All API routes (agent_endpoints, canvas_routes, browser_routes, device_capabilities) have integration tests
  2. Request validation tests cover schema validation, authentication, and error responses
  3. Response validation tests verify success/error response structure and status codes
  4. Database transaction tests cover rollback scenarios and concurrent operations
**Plans**: 6 plans

Plans:
- [ ] 102-01-PLAN.md — Agent endpoints integration tests (chat, sessions, execution) — 40+ tests
- [ ] 102-02-PLAN.md — Canvas routes integration tests (submit, status, governance) — 30+ tests
- [ ] 102-03-PLAN.md — Browser routes integration tests (session, navigate, actions, audit) — 35+ tests
- [ ] 102-04-PLAN.md — Device routes integration tests (camera, screen, location, execute) — 40+ tests
- [ ] 102-05-PLAN.md — Request validation tests for all API endpoints — 35+ tests
- [ ] 102-06-PLAN.md — Database transactions and phase coverage summary — 20+ tests

### Phase 103: Backend Property-Based Tests
**Goal**: Validate business logic invariants using Hypothesis property-based testing
**Depends on**: Phase 102
**Requirements**: BACK-03
**Success Criteria** (what must be TRUE):
  1. Governance invariants tested (maturity levels, action complexity, permission checks)
  2. Episode invariants tested (segmentation time gaps, retrieval accuracy, lifecycle transitions)
  3. Financial invariants tested (decimal precision, double-entry validation, no data loss)
  4. Property tests use strategic max_examples (200 critical, 100 standard, 50 IO-bound)
**Plans**: TBD

Plans:
- [ ] 103-01: Governance property tests (maturity, permissions, action complexity)
- [ ] 103-02: Episode property tests (segmentation, retrieval, lifecycle)
- [ ] 103-03: Financial invariants property tests
- [ ] 103-04: Strategic max_examples optimization (200/100/50)
- [ ] 103-05: Phase verification and property test summary

### Phase 104: Backend Error Path Testing
**Goal**: Comprehensive error path and edge case tests for critical services
**Depends on**: Phase 103
**Requirements**: BACK-04
**Success Criteria** (what must be TRUE):
  1. Security service tests cover authentication failures, authorization bypasses, and boundary violations
  2. Auth service tests cover token expiration, refresh flow, and multi-session management
  3. Finance service tests cover payment failures, webhook race conditions, and idempotency
  4. All error paths have documented VALIDATED_BUG patterns showing bug-finding evidence
**Plans**: TBD

Plans:
- [ ] 104-01: Security error path tests (auth failures, authorization bypasses)
- [ ] 104-02: Auth service error tests (token expiration, refresh, sessions)
- [ ] 104-03: Finance service error tests (payment failures, webhooks, idempotency)
- [ ] 104-04: Edge case and boundary condition tests
- [ ] 104-05: VALIDATED_BUG documentation for all error paths
- [ ] 104-06: Phase verification and error path coverage summary

### Phase 105: Frontend Component Tests
**Goal**: React Testing Library achieves 50%+ coverage for all components
**Depends on**: Phase 100
**Requirements**: FRNT-01
**Success Criteria** (what must be TRUE):
  1. Canvas components (5 guidance components + chart components) have 50%+ coverage
  2. Form components have 50%+ coverage with validation and submission tests
  3. Layout components have 50%+ coverage with responsive design tests
  4. Component tests use user-centric queries (getByRole, getByLabelText) not implementation details
**Plans**: TBD

Plans:
- [ ] 105-01: Canvas guidance components tests (5 components)
- [ ] 105-02: Chart components tests (line, bar, pie charts)
- [ ] 105-03: Form components tests (validation, submission, error states)
- [ ] 105-04: Layout and responsive design tests
- [ ] 105-05: Phase verification and component coverage summary

### Phase 106: Frontend State Management Tests
**Goal**: Validate Redux/Zustand store logic and state transitions
**Depends on**: Phase 105
**Requirements**: FRNT-02
**Success Criteria** (what must be TRUE):
  1. Agent chat state tests cover message streaming, context updates, and error states
  2. Canvas state tests cover component registration, updates, and accessibility API
  3. Auth state tests cover login/logout, token refresh, and session persistence
  4. State transition tests verify no unreachable states and valid transitions only
**Plans**: TBD

Plans:
- [ ] 106-01: Agent chat state management tests (streaming, context, errors)
- [ ] 106-02: Canvas state management tests (registration, updates, accessibility)
- [ ] 106-03: Auth state management tests (login, logout, refresh, persistence)
- [ ] 106-04: State transition validation (no unreachable states)
- [ ] 106-05: Phase verification and state coverage summary

### Phase 107: Frontend API Integration Tests
**Goal**: Mock backend and verify error handling for all API calls
**Depends on**: Phase 106
**Requirements**: FRNT-03
**Success Criteria** (what must be TRUE):
  1. Agent API tests cover chat streaming, execution trigger, and status polling
  2. Canvas API tests cover presentation, form submission, and close operations
  3. Error handling tests cover network failures, timeout scenarios, and malformed responses
  4. MSW (Mock Service Worker) used for consistent mocking across tests
**Plans**: TBD

Plans:
- [ ] 107-01: Agent API integration tests (chat, execution, status)
- [ ] 107-02: Canvas API integration tests (present, submit, close)
- [ ] 107-03: Error handling tests (network failures, timeouts, malformed responses)
- [ ] 107-04: MSW setup and consistent mocking patterns
- [ ] 107-05: Phase verification and API integration summary

### Phase 108: Frontend Property Tests
**Goal**: FastCheck property tests validate state machine invariants
**Depends on**: Phase 107
**Requirements**: FRNT-04
**Success Criteria** (what must be TRUE):
  1. Chat state machine invariants tested (message ordering, context preservation)
  2. Canvas state machine invariants tested (component lifecycle, state consistency)
  3. Auth state machine invariants tested (session validity, permission checks)
  4. Property tests use 50-100 examples for state machine validation
**Plans**: TBD

Plans:
- [ ] 108-01: Chat state machine property tests (FastCheck)
- [ ] 108-02: Canvas state machine property tests
- [ ] 108-03: Auth state machine property tests
- [ ] 108-04: State machine invariant documentation
- [ ] 108-05: Phase verification and property test summary

### Phase 109: Frontend Form Validation Tests
**Goal**: Comprehensive form validation tests covering all form components with edge cases
**Depends on**: Phase 108
**Requirements**: FRNT-05
**Success Criteria** (what must be TRUE):
  1. All form components have validation tests for required fields, format validation, and custom rules
  2. Edge case tests cover boundary values (min/max length, character limits, numeric ranges)
  3. Error message tests verify user-friendly validation feedback
  4. Form submission tests cover success/error/invalid states with backend integration
**Plans**: TBD

Plans:
- [ ] 109-01: Required field validation tests (all forms)
- [ ] 109-02: Format validation tests (email, phone, dates, custom patterns)
- [ ] 109-03: Edge case and boundary value tests
- [ ] 109-04: Error message and user feedback tests
- [ ] 109-05: Form submission integration tests
- [ ] 109-06: Phase verification and form validation summary

### Phase 110: Quality Gates & Reporting
**Goal**: Automated coverage enforcement with PR comments, trend dashboards, and per-commit reports
**Depends on**: Phases 104, 109
**Requirements**: GATE-01, GATE-02, GATE-03, GATE-04
**Success Criteria** (what must be TRUE):
  1. Pull requests receive automated comments showing coverage delta with file-by-file breakdown on drops
  2. 80% overall coverage gate enforced on merge to main branch (CI fails if below threshold)
  3. Coverage trend dashboard shows progress toward 80% goal with historical graphs per module
  4. Automated coverage reports generated per commit and stored in coverage_reports/ directory
**Plans**: TBD

Plans:
- [ ] 110-01: PR comment bot for coverage delta (file-by-file breakdown on drops)
- [ ] 110-02: 80% coverage gate enforcement in CI (fail on merge if below threshold)
- [ ] 110-03: Coverage trend dashboard with historical graphs
- [ ] 110-04: Per-commit coverage report generation and storage
- [ ] 110-05: Phase verification and quality gates summary

## Progress

**Execution Order:**
Phases execute in numeric order: 100 → 101 → 102 → ... → 110

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 95. Backend + Frontend Integration | v4.0 | 8/8 | ✅ Complete | 2026-02-26 |
| 96. Mobile Integration | v4.0 | 7/7 | ✅ Complete | 2026-02-26 |
| 97. Desktop Testing | v4.0 | 7/7 | ✅ Complete | 2026-02-26 |
| 98. Property Testing Expansion | v4.0 | 6/6 | ✅ Complete | 2026-02-26 |
| 99. Cross-Platform Integration & E2E | v4.0 | 8/8 | ✅ Complete | 2026-02-27 |
| 100. Coverage Analysis | v5.0 | 5/5 | ✅ Complete | 2026-02-27 |
| 101. Backend Core Services Unit Tests | v5.0 | 0/TBD | Not started | - |
| 102. Backend API Integration Tests | v5.0 | 0/TBD | Not started | - |
| 103. Backend Property-Based Tests | v5.0 | 0/TBD | Not started | - |
| 104. Backend Error Path Testing | v5.0 | 0/TBD | Not started | - |
| 105. Frontend Component Tests | v5.0 | 0/TBD | Not started | - |
| 106. Frontend State Management Tests | v5.0 | 0/TBD | Not started | - |
| 107. Frontend API Integration Tests | v5.0 | 0/TBD | Not started | - |
| 108. Frontend Property Tests | v5.0 | 0/TBD | Not started | - |
| 109. Frontend Form Validation Tests | v5.0 | 0/TBD | Not started | - |
| 110. Quality Gates & Reporting | v5.0 | 0/TBD | Not started | - |

**Overall Progress**: v4.0 COMPLETE (36/36 plans) | v5.0 IN PLANNING (5/45 plans)

## Requirements Traceability

### v5.0 Requirements Coverage

**Total Requirements**: 17 (100% mapped to phases)

**Phase Distribution**:
- Phase 100 (Coverage Analysis): 3 requirements (COVR-01, COVR-02, COVR-03)
- Phase 101 (Backend Core Unit): 1 requirement (BACK-01)
- Phase 102 (Backend API Integration): 1 requirement (BACK-02)
- Phase 103 (Backend Property Tests): 1 requirement (BACK-03)
- Phase 104 (Backend Error Paths): 1 requirement (BACK-04)
- Phase 105 (Frontend Components): 1 requirement (FRNT-01)
- Phase 106 (Frontend State Mgmt): 1 requirement (FRNT-02)
- Phase 107 (Frontend API Integration): 1 requirement (FRNT-03)
- Phase 108 (Frontend Property Tests): 1 requirement (FRNT-04)
- Phase 109 (Frontend Forms): 1 requirement (FRNT-05)
- Phase 110 (Quality Gates): 4 requirements (GATE-01, GATE-02, GATE-03, GATE-04)

| Requirement | Phase | Status |
|-------------|-------|--------|
| COVR-01: Coverage gap analysis | 100 | Pending |
| COVR-02: High-impact file prioritization | 100 | Pending |
| COVR-03: Coverage trend tracking | 100 | Pending |
| BACK-01: Backend core services unit tests | 101 | Pending |
| BACK-02: Backend API integration tests | 102 | Pending |
| BACK-03: Backend property-based tests | 103 | Pending |
| BACK-04: Backend error path testing | 104 | Pending |
| FRNT-01: Frontend component tests | 105 | Pending |
| FRNT-02: Frontend state management tests | 106 | Pending |
| FRNT-03: Frontend API integration tests | 107 | Pending |
| FRNT-04: Frontend property tests | 108 | Pending |
| FRNT-05: Frontend form validation tests | 109 | Pending |
| GATE-01: PR coverage comments | 110 | Pending |
| GATE-02: 80% coverage gate enforcement | 110 | Pending |
| GATE-03: Coverage trend dashboard | 110 | Pending |
| GATE-04: Per-commit coverage reports | 110 | Pending |

**Coverage**: 17/17 requirements mapped (100%) | No orphaned requirements

---

*Last updated: 2026-02-27*
*Milestone: v5.0 Coverage Expansion*
*Status: 📋 PLANNING - Roadmap created, phase planning next*
