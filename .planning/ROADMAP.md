# Roadmap: Atom Test Coverage Initiative

## Overview

Comprehensive test coverage initiative for Atom platform backend services. The roadmap follows a systematic approach: analyze coverage gaps, prioritize high-impact files, add unit tests for core services, implement property-based tests with Hypothesis for edge case discovery, add integration tests for critical paths, and establish quality gates for sustained coverage growth.

**Milestone v3.2**: Bug Finding & Coverage Expansion through property-based testing and targeted backend test development.

---

## Milestones

- ✅ **v1.0 Test Infrastructure** - Phases 1-28 (shipped)
- ✅ **v2.0 Feature Integration** - Phases 29-74 (shipped)
- ✅ **v3.1 E2E UI Testing** - Phases 75-80 (shipped 2026-02-24)
- 🚧 **v3.2 Bug Finding & Coverage Expansion** - Phases 81-90 (in progress)

---

## Current Milestone: v3.2 Bug Finding & Coverage Expansion

**Goal:** Expand backend test coverage through property-based testing and targeted bug finding to achieve higher overall coverage and discover hidden edge cases.

**Started:** 2026-02-24

**Phases:** 10 (81-90)

**Strategy:** High-impact files first (>200 lines, <30% coverage), maximum coverage gain per test added

**Target:** Comprehensive backend coverage with Hypothesis property tests for edge case discovery

---

## Completed Milestones

<details>
<summary>✅ v3.1 E2E UI Testing (Phases 75-80) - SHIPPED 2026-02-24</summary>

**Achievements:**
- 61 phases executed (300 plans, 204 tasks)
- Production-ready E2E test suite with Playwright
- Comprehensive coverage: authentication, agent chat, canvas presentations, skills, workflows
- Quality gates: screenshots, videos, retries, flaky detection, HTML reports

</details>

<details>
<summary>✅ v2.0 Feature Integration (Phases 29-74) - SHIPPED</summary>

**Achievements:**
- Community Skills Integration (Phase 14)
- Agent Layer Testing (Phase 17)
- Python Package Support (Phase 35) - 7 plans
- npm Package Support (Phase 36) - 7 plans
- Advanced Skill Execution (Phase 60) - 7 plans
- BYOK Cognitive Tier System (Phase 68) - 8 plans
- Autonomous Coding Agents (Phase 69) - 10 plans

</details>

<details>
<summary>✅ v1.0 Test Infrastructure (Phases 1-28) - SHIPPED</summary>

**Achievements:**
- 200/203 plans complete (99% completion)
- 81 tests passing
- 15.87% coverage (216% improvement from baseline)
- Property-based testing framework with Hypothesis
- Integration test infrastructure with pytest-asyncio

</details>

---

## Current Phases (v3.2)

**Phase Numbering:**
- Integer phases (81, 82, 83): Planned milestone work
- Decimal phases (81.1, 81.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 81: Coverage Analysis & Prioritization** - Generate coverage reports, identify high-impact files, map gaps to critical paths
- [x] **Phase 82: Core Services Unit Testing (Governance & Episodes)** - Agent governance, episode segmentation, BYOK handler tests
- [x] **Phase 83: Core Services Unit Testing (Canvas & Browser)** - Canvas tool, browser automation, device capabilities tests
- [x] **Phase 84: Core Services Unit Testing (Training & Graduation)** - Student training service, graduation service tests
- [ ] **Phase 85: Database & Integration Testing** - Database models, migrations, transactions, critical path integration tests
- [ ] **Phase 86: Property-Based Testing (Core Services)** - Governance cache, episode segmentation, LLM streaming invariants
- [ ] **Phase 87: Property-Based Testing (Database & Auth)** - Database operations, authentication/authorization invariants
- [x] **Phase 88: Bug Discovery (Error Paths & Boundaries)** - Error code paths, boundary conditions, concurrent operations ✅ COMPLETE
- [ ] **Phase 89: Bug Discovery (Failure Modes & Security)** - Failure modes, security edge cases
- [ ] **Phase 90: Quality Gates & CI/CD** - Coverage enforcement, trend tracking, pass rate validation, documentation

---

## Phase Details

### Phase 81: Coverage Analysis & Prioritization

**Goal**: Comprehensive coverage analysis identifies gaps, prioritizes high-impact files, maps to critical paths

**Depends on**: Nothing (first phase of v3.2)

**Requirements**: COV-01, COV-02, COV-03, COV-04

**Success Criteria** (what must be TRUE):
  1. Coverage report generated showing all backend files with current coverage percentage
  2. High-impact files identified (>200 lines, <30% coverage) with priority ranking
  3. Coverage gaps mapped to critical business paths and potential failure modes
  4. Coverage baseline established with trend tracking infrastructure in place

**Plans**: 4 plans

- [ ] 081-01-PLAN.md — Generate comprehensive coverage report (coverage.json parsing, HTML report, file listing, coverage percentage calculation)
- [ ] 081-02-PLAN.md — Identify and prioritize high-impact files (>200 lines filter, <30% coverage filter, business criticality scoring, priority ranked list)
- [ ] 081-03-PLAN.md — Map coverage gaps to critical paths (agent execution flow, episode creation flow, canvas presentation flow, failure mode analysis)
- [ ] 081-04-PLAN.md — Establish coverage baseline and trend tracking (baseline metrics, tracking database/JSON, trend analysis script, CI integration)

---

### Phase 82: Core Services Unit Testing (Governance & Episodes)

**Goal**: Agent governance and episode services have comprehensive unit tests covering all code paths

**Depends on**: Phase 81 (coverage analysis)

**Requirements**: UNIT-01, UNIT-02, UNIT-03

**Success Criteria** (what must be TRUE):
  1. Agent governance service tests cover lifecycle, permissions, cache invalidation (90%+ coverage)
  2. Episode segmentation service tests cover time gaps, topic changes, task completion (90%+ coverage)
  3. BYOK LLM handler tests cover multi-provider routing, streaming, error handling (90%+ coverage)
  4. All tests use mocks appropriately (external services mocked, real database/session fixtures)
  5. Tests verify both success and failure paths (edge cases, error handling, boundary conditions)

**Plans**: 6 plans

- [x] 082-01-PLAN.md — Agent governance service unit tests (lifecycle methods, permission checks, cache invalidation, error handling, 30+ tests) ✅ COMPLETE
- [x] 082-02-PLAN.md — Episode segmentation service unit tests (time gap detection, topic change detection, task completion, episode lifecycle, 25+ tests) ✅ COMPLETE
- [x] 082-03-PLAN.md — BYOK LLM handler unit tests (provider selection, streaming responses, error recovery, timeout handling, token counting, 20+ tests) ✅ COMPLETE
- [x] 082-04-PLAN.md — Fix 49 failing BYOK handler tests (mock patches, async streaming, test isolation) ✅ COMPLETE
- [x] 082-05-PLAN.md — Expand BYOK handler coverage to 90%+ (cognitive tier, structured response, coordinated vision, cost tracking) ✅ COMPLETE
- [x] 082-06-PLAN.md — Expand episode segmentation coverage to 90%+ (canvas context extraction, skill episodes, edge cases) ✅ COMPLETE

---

### Phase 83: Core Services Unit Testing (Canvas & Browser)

**Goal**: Canvas, browser automation, and device services have comprehensive unit tests

**Depends on**: Phase 82 (governance/episodes tested)

**Requirements**: UNIT-04, UNIT-05, UNIT-06

**Success Criteria** (what must be TRUE):
  1. Canvas tool tests cover presentation types, governance enforcement, state management (90%+ coverage)
  2. Browser automation tool tests cover CDP integration, governance enforcement, error handling (90%+ coverage)
  3. Device capabilities tool tests cover permissions, maturity gates, device API interactions (90%+ coverage)
  4. Tests verify governance enforcement at maturity boundaries (STUDENT blocked, INTERN approval, SUPERVISED supervision)

**Plans**: 5 plans

- [x] 083-01-PLAN.md — Canvas tool unit tests (chart presentations, markdown rendering, form submission, governance enforcement, state management, 94 tests) ✅ COMPLETE (via 083-04 + 083-05 gap closure)
- [x] 083-02-PLAN.md — Browser automation tool unit tests (CDP integration, page navigation, element interaction, screenshots, governance, error handling, 92 tests) ✅ COMPLETE
- [x] 083-03-PLAN.md — Device capabilities tool unit tests (camera access, screen recording, location services, notifications, permission checks, maturity gates, 98 tests) ✅ COMPLETE
- [x] 083-04-PLAN.md — Fix canvas governance test assertions (2 assertion format fixes) ✅ COMPLETE
- [x] 083-05-PLAN.md — Complete canvas tool tests (66 deferred tests for specialized canvases, JavaScript security, state management, error handling, audit entries, wrapper functions) ✅ COMPLETE

---

### Phase 84: Core Services Unit Testing (Training & Graduation)

**Goal**: Student training and graduation services have comprehensive unit tests

**Depends on**: Phase 83 (canvas/browser tested)

**Requirements**: UNIT-07, UNIT-08

**Success Criteria** (what must be TRUE):
  1. Student training service tests cover proposal workflow, supervision integration, error handling (90%+ coverage)
  2. Graduation service tests cover criteria calculation, constitutional compliance, promotion decisions (90%+ coverage)
  3. Tests verify state transitions (STUDENT → INTERN → SUPERVISED → AUTONOMOUS)
  4. Tests validate graduation criteria (episode counts, intervention rates, constitutional scores)

**Plans**: 2 plans

- [x] 084-01-PLAN.md — Student training service unit tests (proposal generation, approval workflow, supervision monitoring, intervention tracking, 81 tests) ✅ COMPLETE
- [x] 084-02-PLAN.md — Graduation service unit tests (criteria calculation, constitutional scoring, eligibility checks, promotion decisions, state transitions, 88 tests) ✅ COMPLETE

---

### Phase 85: Database & Integration Testing

**Goal**: Database models, migrations, transactions, and critical integration paths have comprehensive tests

**Depends on**: Phase 84 (training/graduation tested)

**Requirements**: DB-01, DB-02, DB-03, DB-04

**Success Criteria** (what must be TRUE):
  1. Database model tests cover relationships, constraints, cascading deletes (90%+ coverage)
  2. Migration tests cover upgrade/downgrade paths, data preservation (all migrations)
  3. Transaction tests cover rollback scenarios, concurrent operations, isolation levels
  4. Integration tests cover critical paths (agent execution, episode creation, canvas presentation)

**Plans**: 4 plans

- [ ] 085-01-PLAN.md — Database model tests (relationships, foreign keys, constraints, cascading operations, ORM queries, 30+ tests)
- [ ] 085-02-PLAN.md — Migration tests (upgrade path, downgrade path, data preservation, schema validation, all migrations tested)
- [ ] 085-03-PLAN.md — Transaction tests (rollback on error, concurrent operations, isolation levels, deadlock handling, 15+ tests)
- [ ] 085-04-PLAN.md — Integration tests for critical paths (agent execution end-to-end, episode creation end-to-end, canvas presentation end-to-end, 20+ tests)

---

### Phase 86: Property-Based Testing (Core Services)

**Goal**: Core services have Hypothesis property tests for invariants and edge cases

**Depends on**: Phase 85 (database/integration tested)

**Requirements**: PROP-01, PROP-02, PROP-03

**Success Criteria** (what must be TRUE):
  1. Governance cache property tests verify idempotency, consistency, performance invariants
  2. Episode segmentation property tests verify monotonicity, completeness, ordering invariants
  3. LLM streaming property tests verify token ordering, error recovery, timeout handling
  4. Hypothesis finds edge cases that unit tests miss (documented bugs fixed)

**Plans**: 3 plans

- [ ] 086-01-PLAN.md — Governance cache property tests (cache hit idempotency, cache consistency across invalidations, performance degradation detection, 10+ properties)
- [ ] 086-02-PLAN.md — Episode segmentation property tests (monotonic episode growth, complete segment coverage, ordering preservation, 10+ properties)
- [ ] 086-03-PLAN.md — LLM streaming property tests (token ordering preserved, error recovery maintains state, timeout handling graceful, 8+ properties)

---

### Phase 87: Property-Based Testing (Database & Auth)

**Goal**: Database operations and authentication/authorization have property tests

**Depends on**: Phase 86 (core services property tested)

**Requirements**: PROP-04, PROP-05

**Success Criteria** (what must be TRUE):
  1. Database operation property tests verify CRUD invariants, foreign key constraints
  2. Authentication/authorization property tests verify permission matrix, maturity gate enforcement
  3. Hypothesis generates diverse inputs (unicode, special characters, boundary values)

**Plans**: 2 plans

- [x] 087-01-PLAN.md — Database operations property tests (CRUD invariants, foreign key constraints, unique constraints, transaction atomicity, 8+ properties) ✅ CREATED
- [x] 087-02-PLAN.md — Authentication/authorization property tests (permission matrix completeness, maturity gate enforcement, role-based access control, 8+ properties) ✅ CREATED

---

### Phase 88: Bug Discovery (Error Paths & Boundaries)

**Goal**: All error code paths, boundary conditions, and concurrent operations are tested

**Depends on**: Phase 87 (property tests complete)

**Requirements**: BUG-01, BUG-02, BUG-03

**Success Criteria** (what must be TRUE):
  1. All error code paths are tested (every exception raised, every error branch)
  2. Boundary conditions are tested (empty inputs, maximum values, unicode, special characters)
  3. Concurrent operations are tested (race conditions, deadlocks, resource cleanup)
  4. Tests discover bugs in production code (documented and fixed)

**Plans**: 3 plans

- [x] 088-01-PLAN.md — Error code path tests (every exception raised, every error return value, error propagation, error logging, 40+ tests) ✅ CREATED
- [x] 088-02-PLAN.md — Boundary condition tests (empty inputs, null inputs, maximum values, unicode strings, special characters, negative values, 30+ tests) ✅ CREATED
- [x] 088-03-PLAN.md — Concurrent operation tests (race conditions, deadlocks, resource cleanup, lock contention, 15+ tests) ✅ CREATED

---

### Phase 89: Bug Discovery (Failure Modes & Security)

**Goal**: All failure modes and security edge cases are tested

**Depends on**: Phase 88 (error paths tested)

**Requirements**: BUG-04, BUG-05

**Success Criteria** (what must be TRUE):
  1. Failure modes are tested (network timeouts, provider failures, database connection loss)
  2. Security edge cases are tested (injection attempts, permission bypass, malformed input)
  3. Tests verify graceful degradation (errors don't crash system, proper error messages)

**Plans**: 2 plans

- [ ] 089-01-PLAN.md — Failure mode tests (network timeouts, provider failures, database connection loss, out of memory, disk full, 20+ tests)
- [ ] 089-02-PLAN.md — Security edge case tests (SQL injection, XSS injection, path traversal, permission bypass, malformed input, DoS protection, 25+ tests)

---

### Phase 90: Quality Gates & CI/CD

**Goal**: Quality gates enforce coverage, track trends, maintain pass rate, and document strategy

**Depends on**: Phase 89 (failure modes tested)

**Requirements**: QUAL-01, QUAL-02, QUAL-03, QUAL-04, QUAL-05, QUAL-06

**Success Criteria** (what must be TRUE):
  1. Pre-commit hook enforces 80% coverage on new code
  2. Coverage trends tracked over time with automated regression detection
  3. Test suite maintains 98%+ pass rate across all tests
  4. Coverage reports generated with drill-down to uncovered lines
  5. Coverage metrics integrated into CI pipeline with failure thresholds
  6. Test coverage strategy documented with maintenance guidelines

**Plans**: 6 plans

- [ ] 090-01-PLAN.md — Pre-commit coverage hook (80% minimum enforcement, new code only, clear error messages, documentation)
- [ ] 090-02-PLAN.md — Coverage trend tracking (historical data storage, trend calculation, regression detection, alerting)
- [ ] 090-03-PLAN.md — Test pass rate validation (98%+ threshold, flaky test tracking, failure categorization, CI gate)
- [ ] 090-04-PLAN.md — Coverage report generation (HTML reports with drill-down, uncovered lines highlighted, missing branch coverage, JSON metrics)
- [ ] 090-05-PLAN.md — CI pipeline integration (coverage thresholds, pass rate gates, trend regression detection, artifact upload)
- [ ] 090-06-PLAN.md — Coverage strategy documentation (testing guidelines, maintenance procedures, coverage targets, quality standards)

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 81. Coverage Analysis & Prioritization | 4/4 | ✅ Complete | 2026-02-24 |
| 82. Core Services Unit Testing (Governance & Episodes) | 6/6 | ✅ Complete | 2026-02-24 |
| 83. Core Services Unit Testing (Canvas & Browser) | 5/5 | ✅ Complete | 2026-02-24 |
| 84. Core Services Unit Testing (Training & Graduation) | 2/2 | ✅ Complete | 2026-02-24 |
| 85. Database & Integration Testing | 0/4 | Not started | - |
| 86. Property-Based Testing (Core Services) | 0/3 | 📋 Planned | 2026-02-24 |
| 87. Property-Based Testing (Database & Auth) | 0/2 | Not started | - |
| 88. Bug Discovery (Error Paths & Boundaries) | 3/3 | ✅ Complete | 2026-02-24 |
| 89. Bug Discovery (Failure Modes & Security) | 0/2 | Not started | - |
| 90. Quality Gates & CI/CD | 0/6 | Not started | - |

**Overall Progress**: 20/34 plans complete (59%) | Phase 89 plans ready for planning

---

## Coverage Summary

**v3.2 Requirements**: 30 total
- Coverage Analysis & Prioritization: 4 requirements
- Core Services Unit Testing: 8 requirements
- Database & Integration Testing: 4 requirements
- Property-Based Testing: 5 requirements
- Bug Discovery & Edge Cases: 5 requirements
- Quality Gates & CI/CD: 6 requirements

**Coverage**: 100% (30/30 requirements mapped to phases 81-90)

---

## Out of Scope (v3.2)

Explicitly excluded from v3.2 to maintain focus. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Frontend test coverage | Separate frontend test suite with different tooling (Jest, React Testing Library) |
| Mobile test coverage | Mobile implementation in progress, separate test infrastructure |
| Performance/benchmark testing | Separate performance testing initiative planned for v4+ |
| End-to-end UI testing | Already complete in v3.1 (Playwright E2E suite) |
| LanceDB integration tests | Requires external LanceDB dependency, not yet in CI environment |

---

*Last updated: 2026-02-24*
*Milestone: v3.2 Bug Finding & Coverage Expansion*
*Status: 🚧 PLANNING COMPLETE - Phase 81 planned (4 plans ready for execution)*
