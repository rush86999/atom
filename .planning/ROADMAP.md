# Roadmap: Atom Test Coverage Initiative

## Overview

A comprehensive testing initiative to achieve 80% code coverage across the Atom AI-powered business automation platform within 1-2 weeks. The roadmap follows a foundation-first approach: establish test infrastructure to prevent coverage churn, implement property-based tests for critical system invariants, build integration and security tests, extend coverage to mobile and desktop platforms, and validate 80% coverage on all critical paths (governance, security, episodic memory).

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Test Infrastructure** - Establish pytest configuration, parallel execution, test data factories, coverage reporting, quality gates, and CI integration
- [ ] **Phase 2: Core Property Tests** - Implement Hypothesis-based property tests for governance, episodic memory, database transactions, API contracts, state management, event handling, and file operations
- [ ] **Phase 3: Integration & Security Tests** - Build integration tests for API endpoints, database transactions, WebSockets, external services, and security flows (authentication, authorization, input validation, canvas security, JWT, OAuth, episode access)
- [ ] **Phase 4: Platform Coverage** - Extend test coverage to React Native mobile components and Tauri desktop/menu bar applications
- [ ] **Phase 5: Coverage & Quality Validation** - Achieve 80% coverage across all domains, validate test quality (parallel execution, no shared state, no flaky tests), and create comprehensive documentation

## Phase Details

### Phase 1: Test Infrastructure
**Goal**: Test infrastructure is established with pytest configuration, parallel execution, test data factories, coverage reporting, quality gates, and CI integration
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, INFRA-07, QUAL-06, DOCS-04, DOCS-05
**Success Criteria** (what must be TRUE):
  1. Developer can run full test suite with `pytest -v` and see all tests discovered and categorized by markers
  2. Developer can run tests in parallel with `pytest -n auto` and see tests complete successfully with no state sharing issues
  3. Developer can run `pytest --cov` and generate HTML, terminal, and JSON coverage reports showing current coverage metrics
  4. Test suite creates isolated test data using factory_boy patterns with no hardcoded IDs
  5. CI pipeline runs tests automatically on every push and PR with coverage enforcement
**Plans**: 5 plans
- [x] 01-test-infrastructure-01-PLAN.md — Install and configure pytest-xdist for parallel execution
- [x] 01-test-infrastructure-02-PLAN.md — Create factory_boy test data factories for all core models
- [x] 01-test-infrastructure-03-PLAN.md — Configure multi-format coverage reporting with quality gates
- [x] 01-test-infrastructure-04-PLAN.md — Enhance CI pipeline with full test suite and coverage enforcement
- [x] 01-test-infrastructure-05-PLAN.md — Implement assertion density quality gate and factory documentation

### Phase 2: Core Property Tests
**Goal**: Property-based tests verify critical system invariants for governance, episodic memory, database, API, state, events, and file operations
**Depends on**: Phase 1
**Requirements**: PROP-01, PROP-02, PROP-03, PROP-04, PROP-05, PROP-06, PROP-07, QUAL-04, QUAL-05, DOCS-02
**Success Criteria** (what must be TRUE):
  1. Property tests verify governance invariants (agent maturity levels, permissions matrix, confidence scores) with bug-finding evidence documented
  2. Property tests verify episodic memory invariants (segmentation boundaries, retrieval accuracy, graduation criteria) with bug-finding evidence documented
  3. Property tests verify database transaction invariants (ACID properties, constraints) with bug-finding evidence documented
  4. Each property test documents the invariant being tested and includes VALIDATED_BUG section in docstrings
  5. INVARIANTS.md documents all invariants externally with test locations and max_examples values
  6. Strategic max_examples: 200 for critical invariants (financial, security, data loss), 100 for standard, 50 for IO-bound
**Plans**: 7 plans
- [ ] 02-core-property-tests-01-PLAN.md — Enhance governance property tests with bug-finding evidence documentation
- [ ] 02-core-property-tests-02-PLAN.md — Enhance episodic memory property tests with bug-finding evidence documentation
- [ ] 02-core-property-tests-03-PLAN.md — Enhance database transaction property tests with ACID invariant documentation
- [ ] 02-core-property-tests-04-PLAN.md — Enhance API contract property tests with validation error documentation
- [ ] 02-core-property-tests-05-PLAN.md — Enhance state management property tests with rollback sync documentation
- [ ] 02-core-property-tests-06-PLAN.md — Enhance event handling property tests with ordering batching documentation
- [ ] 02-core-property-tests-07-PLAN.md — Enhance file operations property tests with security path documentation

### Phase 3: Integration & Security Tests
**Goal**: Integration tests validate component interactions and security tests validate authentication, authorization, input validation, and access control
**Depends on**: Phase 2
**Requirements**: INTG-01, INTG-02, INTG-03, INTG-04, INTG-05, INTG-06, INTG-07, SECU-01, SECU-02, SECU-03, SECU-04, SECU-05, SECU-06, SECU-07
**Success Criteria** (what must be TRUE):
  1. API integration tests validate all FastAPI endpoints with TestClient including request/response validation and error handling
  2. Database integration tests use transaction rollback pattern with no committed test data
  3. WebSocket integration tests validate real-time messaging and streaming with proper async coordination
  4. Security tests validate authentication flows (signup, login, logout, session management, JWT refresh)
  5. Security tests validate authorization (agent maturity permissions, action complexity matrix, episode access control, OAuth flows)
  6. Security tests validate input validation (SQL injection, XSS, path traversal prevention, canvas JavaScript security)
**Plans**: TBD

### Phase 4: Platform Coverage
**Goal**: Mobile and desktop applications have comprehensive test coverage for React Native and Tauri components
**Depends on**: Phase 3
**Requirements**: MOBL-01, MOBL-02, MOBL-03, MOBL-04, MOBL-05, DSKP-01, DSKP-02, DSKP-03, DSKP-04
**Success Criteria** (what must be TRUE):
  1. React Native component tests cover iOS and Android platforms with platform-specific fixtures
  2. Mobile tests validate device capabilities (Camera, Location, Notifications, Biometric) for both iOS and Android
  3. Mobile tests validate platform-specific permissions (iOS vs Android differences) and authentication flows
  4. Desktop tests validate Tauri app components and menu bar functionality
  5. Desktop tests validate desktop-backend integration and desktop-specific device capabilities
**Plans**: TBD

### Phase 5: Coverage & Quality Validation
**Goal**: All domains achieve 80% code coverage, test suite validates quality standards, and comprehensive documentation is created
**Depends on**: Phase 4
**Requirements**: COVR-01, COVR-02, COVR-03, COVR-04, COVR-05, COVR-06, COVR-07, QUAL-01, QUAL-02, QUAL-03, QUAL-07, DOCS-01, DOCS-03
**Success Criteria** (what must be TRUE):
  1. Governance domain achieves 80% coverage (agent_governance_service.py, agent_context_resolver.py, governance_cache.py, trigger_interceptor.py)
  2. Security domain achieves 80% coverage (auth/, crypto/, validation/)
  3. Episodic memory domain achieves 80% coverage (episode_segmentation_service.py, episode_retrieval_service.py, episode_lifecycle_service.py)
  4. Core backend achieves 80% overall coverage (backend/core/, backend/api/, backend/tools/)
  5. Mobile app achieves 80% coverage (mobile/src/) and desktop app achieves 80% coverage (desktop/, menu bar)
  6. Full test suite executes in parallel with zero shared state, zero flaky tests, and completes in <5 minutes
  7. Coverage trending setup tracks coverage.json over time with HTML reports for interpretation
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Test Infrastructure | 5/5 | **Complete** | 2026-02-11 |
| 2. Core Property Tests | 0/7 | Not started | - |
| 3. Integration & Security Tests | 0/TBD | Not started | - |
| 4. Platform Coverage | 0/TBD | Not started | - |
| 5. Coverage & Quality Validation | 0/TBD | Not started | - |
