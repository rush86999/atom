# Roadmap: Atom Production Readiness

## Overview

Achieving production-ready stability for the Atom AI-powered business automation platform by fixing all runtime errors, achieving 80% test coverage across critical system paths, and establishing CI/CD quality gates. This milestone ensures every core service, API endpoint, and data operation is thoroughly tested before production deployment.

## Milestones

- 📋 **v3.0 Production Readiness** - Phases 70-74 (planned)

## Phases

**Phase Numbering:**
- Integer phases (70, 71, 72, 73, 74): Planned milestone work
- Decimal phases (70.1, 70.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 70: Runtime Error Fixes** - Fix all crashes, exceptions, and runtime errors across backend services
- [ ] **Phase 71: Core AI Services Coverage** - Achieve 80%+ test coverage for orchestration, governance, LLM routing, autonomous coding, and episodes
- [ ] **Phase 72: API & Data Layer Coverage** - Achieve 80%+ test coverage for REST endpoints, WebSocket, and database operations
- [ ] **Phase 73: Test Suite Stability** - Fix flaky tests and ensure 100% pass rate with parallel execution
- [ ] **Phase 74: Quality Gates & Property Testing** - Enforce 80% coverage in CI/CD and implement property-based tests for critical invariants

## Phase Details

### Phase 70: Runtime Error Fixes
**Goal**: All runtime crashes, exceptions, import errors, and type errors are fixed and tested
**Depends on**: Nothing (first phase)
**Requirements**: RUNTIME-01, RUNTIME-02, RUNTIME-03, RUNTIME-04
**Success Criteria** (what must be TRUE):
  1. Backend services run without crashes or unhandled exceptions during normal operation
  2. All ImportError and missing dependency issues are resolved across the codebase
  3. All TypeError and AttributeError issues in production code paths are fixed
  4. Fixes are validated with regression tests to prevent reoccurrence
**Plans**: 4 plans

Plans:
- [ ] 70-01-PLAN.md — Fix SQLAlchemy relationship errors (FFmpegJob.user, HueBridge.user) causing 76 test failures
- [ ] 70-02-PLAN.md — Resolve ImportError and missing dependency issues with proper error handling
- [ ] 70-03-PLAN.md — Fix NameError and undefined variables by eliminating wildcard imports
- [ ] 70-04-PLAN.md — Replace bare except clauses with specific exception types

### Phase 71: Core AI Services Coverage
**Goal**: Core AI services (orchestration, governance, LLM routing, autonomous coding, episodes) achieve 80%+ test coverage
**Depends on**: Phase 70
**Requirements**: AICOV-01, AICOV-02, AICOV-03, AICOV-04, AICOV-05
**Success Criteria** (what must be TRUE):
  1. Agent orchestration service has comprehensive tests covering 80%+ of code paths
  2. Agent governance and maturity routing logic is tested with 80%+ coverage
  3. LLM routing and BYOK handler tests cover 80%+ of provider selection and streaming logic
  4. Autonomous coding agents workflow (parse → research → plan → code → test → fix) has 80%+ coverage
  5. Episode and memory management services achieve 80%+ test coverage
**Plans**: 8 plans (5 original + 3 gap closure)

Plans:
- [x] 71-01-PLAN.md — Agent orchestration service tests (agent_execution_service.py, agent_context_resolver.py)
- [x] 71-02-PLAN.md — Agent governance and maturity routing tests (agent_governance_service.py, agent_graduation_service.py, governance_cache.py)
- [x] 71-03-PLAN.md — LLM routing and BYOK handler tests (byok_handler.py, cognitive_tier_system.py, cache_aware_router.py)
- [x] 71-04-PLAN.md — Autonomous coding agents workflow tests (autonomous_coding_orchestrator.py and 7 specialized agents)
- [x] 71-05-PLAN.md — Episode and memory management services tests (episode_lifecycle_service.py, episode_segmentation_service.py, episode_retrieval_service.py)
- [ ] 71-06-PLAN.md — Gap closure: Agent execution service error edge cases (71.03% -> 80%+)
- [ ] 71-07-PLAN.md — Gap closure: BYOK handler coverage documentation (10.88% rationale)
- [ ] 71-08-PLAN.md — Gap closure: Episode services edge cases (72% -> 80%+)

**References for Autonomous Coding with AI:**
- [How to Effectively Write Quality Code with AI](https://heidenstedt.org/posts/2026/how-to-effectively-write-quality-code-with-ai/) - 12 practices including establishing clear vision, maintaining precise documentation, building debug systems, marking code review levels, using context-specific prompts (CLAUDE.md), and marking high-security-risk functions
- [Red/Green TDD for Agentic Engineering](https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/) - Test-first development pattern for AI coding agents to protect against non-working code and unnecessary features
- See also: `docs/AUTONOMOUS_CODING_TDD_PATTERNS.md`

### Phase 72: API & Data Layer Coverage
**Goal**: All REST API routes, WebSocket endpoints, and database operations achieve 80%+ test coverage
**Depends on**: Phase 71
**Requirements**: APICOV-01, APICOV-02, APICOV-03, APICOV-04, APICOV-05, DATACOV-01, DATACOV-02, DATACOV-03, DATACOV-04, DATACOV-05
**Success Criteria** (what must be TRUE):
  1. All REST API routes have tests covering 80%+ of request handling, responses, and error cases
  2. Authentication and authorization endpoints are tested with 80%+ coverage
  3. WebSocket endpoints and real-time update logic have 80%+ test coverage
  4. API request validation and sanitization are tested with edge cases
  5. Database models have tests covering 80%+ of fields, relationships, and constraints
  6. Database migrations are tested for both forward and rollback scenarios
  7. SQLAlchemy operations and queries achieve 80%+ test coverage
  8. Database transactions and rollback scenarios are tested
  9. Data integrity constraints (foreign keys, unique constraints) are validated in tests
**Plans**: 5 plans (3 waves)

Plans:
- [ ] 72-01-PLAN.md — Achieve 80%+ coverage for REST API routes (agent, canvas, workflow, project)
- [ ] 72-02-PLAN.md — Achieve 80%+ coverage for authentication and WebSocket endpoints
- [ ] 72-03-PLAN.md — Achieve 80%+ coverage for database models and SQLAlchemy operations
- [ ] 72-04-PLAN.md — Test database migrations for forward and rollback scenarios
- [ ] 72-05-PLAN.md — Test database transactions, rollbacks, and data integrity constraints

### Phase 73: Test Suite Stability
**Goal**: Test suite achieves 100% pass rate consistently with execution under 60 minutes and parallel execution support
**Depends on**: Phase 72
**Requirements**: STABLE-01, STABLE-02, STABLE-03, STABLE-04, STABLE-05
**Success Criteria** (what must be TRUE):
  1. All flaky tests are identified and fixed with stable assertions
  2. Test suite passes 100% on 3 consecutive full runs
  3. Full test suite executes in under 60 minutes
  4. No tests require hardcoded environment assumptions (use fixtures/mocks)
  5. All tests can run in parallel without race conditions or shared state issues
**Plans**: 5 plans (2 waves)

Plans:
- [ ] 73-01-PLAN.md — Fix ModuleNotFoundError and stabilize fixture imports (blocks all testing)
- [ ] 73-02-PLAN.md — Replace hardcoded resource IDs with unique_resource_name fixture
- [ ] 73-03-PLAN.md — Configure pytest-xdist for parallel execution and flaky test detection
- [ ] 73-04-PLAN.md — Replace environment variable usage with monkeypatch fixture
- [ ] 73-05-PLAN.md — Verify 100% pass rate and <60min execution with parallel tests

### Phase 74: Quality Gates & Property Testing
**Goal**: CI/CD pipeline enforces 80% coverage threshold and property-based tests validate critical invariants
**Depends on**: Phase 73
**Requirements**: GATES-01, GATES-02, GATES-03, GATES-04, GATES-05, PROP-01, PROP-02, PROP-03, PROP-04, PROP-05
**Success Criteria** (what must be TRUE):
  1. CI pipeline blocks deployment if coverage drops below 80%
  2. All tests must pass before merge is allowed
  3. Coverage report is generated and viewable in CI/CD pipeline output
  4. Pre-commit hooks enforce local testing standards before commits
  5. Coverage regression (drop below 80%) blocks deployment
  6. Critical governance invariants are tested with Hypothesis property-based tests
  7. LLM routing invariants are tested with property-based tests
  8. Database transaction invariants are tested with Hypothesis
  9. API contract invariants are tested with property-based tests
  10. All property tests document bug-finding evidence (VALIDATED_BUG docstrings)
**Plans**: 8 plans (3 waves)

Plans:
- [ ] 74-01-PLAN.md — Enforce 80% coverage threshold in CI pipeline with deployment blocking
- [ ] 74-02-PLAN.md — Require all tests to pass before merge with coverage reports
- [ ] 74-03-PLAN.md — Implement pre-commit hooks for local testing standards (80% coverage)
- [ ] 74-04-PLAN.md — Create property-based tests for governance invariants (PROP-01)
- [ ] 74-05-PLAN.md — Create property-based tests for LLM routing invariants (PROP-02)
- [ ] 74-06-PLAN.md — Create property-based tests for database transaction invariants (PROP-03)
- [ ] 74-07-PLAN.md — Create property-based tests for API contract invariants (PROP-04)
- [ ] 74-08-PLAN.md — Document bug-finding evidence (VALIDATED_BUG) in all property tests (PROP-05)

## Progress

**Execution Order:**
Phases execute in numeric order: 70 → 71 → 72 → 73 → 74

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 70. Runtime Error Fixes | 4/4 | Ready for verification | 2025-02-22 |
| 71. Core AI Services Coverage | 0/5 | Ready to execute | - |
| 72. API & Data Layer Coverage | 0/5 | Ready to execute | - |
| 73. Test Suite Stability | 0/5 | Plans created | - |
| 74. Quality Gates & Property Testing | 0/8 | Plans created | - |
