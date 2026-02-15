# Roadmap: Atom Test Coverage Initiative

## Overview

Atom's test coverage initiative transforms the platform from minimal test coverage (15.2%) to comprehensive production-ready testing (80% ultimate goal). Phase 09 achieved test suite stabilization with 0 collection errors, ~97% pass rate, and 3 quality gates operational. Phase 10 focuses on aggressive coverage expansion to 50% using a high-impact file strategy, targeting files with >200 lines of untested code for maximum coverage gain per test added.

## Milestones

- ✅ **v1.0 Test Suite Stabilization** - Phases 01-09 (shipped 2026-02-15, 80% substantial)
- 🚧 **v1.1 Coverage Expansion to 50%** - Phases 10-15 (in progress)
- 📋 **v1.2 Coverage Expansion to 65%** - Future phases (planned)
- 📋 **v1.3 Coverage Expansion to 80%** - Future phases (planned)

## Phases

<details>
<summary>✅ v1.0 Test Suite Stabilization (Phases 01-09) - SHIPPED 2026-02-15</summary>

### Phase 09: Test Suite Stabilization
**Goal**: Fix all failing tests and establish quality gates
**Plans**: 8 plans

Plans:
- [x] 09-01: Fix governance test collection errors
- [x] 09-02: Fix auth test collection errors
- [x] 09-03: Fix property test TypeErrors
- [x] 09-04: Fix governance test failures
- [x] 09-05: Fix auth endpoint test failures
- [x] 09-06: Establish quality gates
- [x] 09-07: Verify 98% pass rate
- [x] 09-08: Final integration and documentation

**Achievements**:
- Fixed all 356 collection errors (100% improvement)
- Fixed 30+ test failures (91% reduction, 324 → ~25)
- Established 3 quality gates (pre-commit, CI, trend tracking)
- Achieved ~97% pass rate (95.3% → ~97%)
- Identified AsyncMock usage pattern and fixed 19 governance tests
- Created coverage trend tracking infrastructure

</details>

### 🚧 v1.1 Coverage Expansion to 50% (In Progress)

**Milestone Goal:** Expand test coverage from 15.2% to 50% using high-impact file strategy with aggressive 1-week timeline

#### Phase 10: Fix Remaining Test Failures
**Goal**: All tests pass consistently at 98%+ rate
**Depends on**: Phase 09
**Requirements**: TQ-01, TQ-02, TQ-03, TQ-04
**Success Criteria** (what must be TRUE):
  1. All ~25-30 remaining test failures are fixed (governance graduation, proposal service, others)
  2. Test suite achieves 98%+ pass rate across 3 consecutive runs
  3. Test suite completes successfully in under 60 minutes
  4. No flaky tests detected across multiple runs
**Plans**: 2 plans

Plans:
- [ ] 10-01: Fix governance graduation test failures (18 tests)
- [ ] 10-02: Fix proposal service and other test failures (7-12 tests)

#### Phase 11: Coverage Analysis & Prioritization
**Goal**: Identify high-impact files for maximum coverage gain
**Depends on**: Phase 10
**Requirements**: COV-02
**Success Criteria** (what must be TRUE):
  1. Coverage report generated with detailed file-by-file breakdown
  2. All files >200 lines identified and ranked by coverage gap
  3. High-impact testing opportunities prioritized (largest untested files first)
  4. Testing strategy document created with file priorities and test types
**Plans**: 1 plan

Plans:
- [ ] 11-01: Analyze coverage and prioritize high-impact files

#### Phase 12: Unit Test Expansion for Core Services
**Goal**: Core services (governance, episodes, streaming) achieve >60% coverage
**Depends on**: Phase 11
**Requirements**: COV-01, COV-03
**Success Criteria** (what must be TRUE):
  1. Agent governance services have comprehensive unit tests (>60% coverage)
  2. Episodic memory services have comprehensive unit tests (>60% coverage)
  3. LLM streaming services have comprehensive unit tests (>60% coverage)
  4. Overall coverage increases from 15.2% to at least 35%
**Plans**: 3 plans

Plans:
- [ ] 12-01: Add unit tests for agent governance services
- [ ] 12-02: Add unit tests for episodic memory services
- [ ] 12-03: Add unit tests for LLM streaming services

#### Phase 13: Integration & API Test Expansion
**Goal**: API routes and tools achieve >50% coverage
**Depends on**: Phase 12
**Requirements**: COV-01, COV-04, COV-05
**Success Criteria** (what must be TRUE):
  1. Canvas API routes have comprehensive integration tests (>50% coverage)
  2. Browser and device API routes have integration tests (>50% coverage)
  3. Canvas, browser, and device tools have integration tests (>50% coverage)
  4. Overall coverage increases from 35% to at least 45%
**Plans**: 3 plans

Plans:
- [ ] 13-01: Add integration tests for canvas API routes
- [ ] 13-02: Add integration tests for browser and device API routes
- [ ] 13-03: Add integration tests for canvas, browser, and device tools

#### Phase 14: Property-Based Testing Implementation
**Goal**: Property tests validate system invariants using Hypothesis framework
**Depends on**: Phase 13
**Requirements**: PROP-01, PROP-02, PROP-03, PROP-04, PROP-05
**Success Criteria** (what must be TRUE):
  1. Governance system invariants tested with property tests (maturity levels, permissions)
  2. Episodic memory invariants tested with property tests (segmentation, retrieval, lifecycle)
  3. Streaming LLM invariants tested with property tests (token streaming, provider routing)
  4. Property tests run alongside unit/integration tests without regression
  5. Overall coverage increases from 45% to 50%
**Plans**: 3 plans

Plans:
- [ ] 14-01: Add property tests for governance system invariants
- [ ] 14-02: Add property tests for episodic memory invariants
- [ ] 14-03: Add property tests for streaming LLM invariants

#### Phase 15: Verification & Infrastructure Updates
**Goal**: 50% coverage target achieved with all infrastructure operational
**Depends on**: Phase 14
**Requirements**: COV-01, INF-01, INF-02, INF-03, INF-04
**Success Criteria** (what must be TRUE):
  1. Overall coverage reaches 50% (from 15.2%, +34.8 percentage points)
  2. Coverage trend tracking updates automatically after each test run
  3. Pre-commit coverage hook enforces 80% minimum for new code
  4. CI pass rate check provides detailed metrics (not just informational)
  5. Coverage reports include HTML, JSON, and trend analysis
**Plans**: 2 plans

Plans:
- [ ] 15-01: Verify 50% coverage target achieved
- [ ] 15-02: Update test infrastructure (trend tracking, CI metrics, reporting)

### 📋 v1.2 Coverage Expansion to 65% (Planned)

**Milestone Goal:** Expand test coverage from 50% to 65% with focus on edge cases and error handling

### 📋 v1.3 Coverage Expansion to 80% (Planned)

**Milestone Goal:** Expand test coverage from 65% to 80% for production-ready test suite

## Progress

**Execution Order:**
Phases execute in numeric order: 10 → 11 → 12 → 13 → 14 → 15

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 09. Test Suite Stabilization | v1.0 | 8/8 | Complete | 2026-02-15 |
| 10. Fix Remaining Test Failures | v1.1 | 0/2 | Not started | - |
| 11. Coverage Analysis & Prioritization | v1.1 | 0/1 | Not started | - |
| 12. Unit Test Expansion for Core Services | v1.1 | 0/3 | Not started | - |
| 13. Integration & API Test Expansion | v1.1 | 0/3 | Not started | - |
| 14. Property-Based Testing Implementation | v1.1 | 0/3 | Not started | - |
| 15. Verification & Infrastructure Updates | v1.1 | 0/2 | Not started | - |

---

## Phase Details

### Phase 10: Fix Remaining Test Failures
**Goal**: All tests pass consistently at 98%+ rate
**Depends on**: Phase 09
**Requirements**: TQ-01, TQ-02, TQ-03, TQ-04
**Success Criteria** (what must be TRUE):
  1. All ~25-30 remaining test failures are fixed (governance graduation, proposal service, others)
  2. Test suite achieves 98%+ pass rate across 3 consecutive runs
  3. Test suite completes successfully in under 60 minutes
  4. No flaky tests detected across multiple runs
**Plans**: 2 plans

Plans:
- [ ] 10-01: Fix governance graduation test failures (18 tests)
- [ ] 10-02: Fix proposal service and other test failures (7-12 tests)

### Phase 11: Coverage Analysis & Prioritization
**Goal**: Identify high-impact files for maximum coverage gain
**Depends on**: Phase 10
**Requirements**: COV-02
**Success Criteria** (what must be TRUE):
  1. Coverage report generated with detailed file-by-file breakdown
  2. All files >200 lines identified and ranked by coverage gap
  3. High-impact testing opportunities prioritized (largest untested files first)
  4. Testing strategy document created with file priorities and test types
**Plans**: 1 plan

Plans:
- [ ] 11-01: Analyze coverage and prioritize high-impact files

### Phase 12: Unit Test Expansion for Core Services
**Goal**: Core services (governance, episodes, streaming) achieve >60% coverage
**Depends on**: Phase 11
**Requirements**: COV-01, COV-03
**Success Criteria** (what must be TRUE):
  1. Agent governance services have comprehensive unit tests (>60% coverage)
  2. Episodic memory services have comprehensive unit tests (>60% coverage)
  3. LLM streaming services have comprehensive unit tests (>60% coverage)
  4. Overall coverage increases from 15.2% to at least 35%
**Plans**: 3 plans

Plans:
- [ ] 12-01: Add unit tests for agent governance services
- [ ] 12-02: Add unit tests for episodic memory services
- [ ] 12-03: Add unit tests for LLM streaming services

### Phase 13: Integration & API Test Expansion
**Goal**: API routes and tools achieve >50% coverage
**Depends on**: Phase 12
**Requirements**: COV-01, COV-04, COV-05
**Success Criteria** (what must be TRUE):
  1. Canvas API routes have comprehensive integration tests (>50% coverage)
  2. Browser and device API routes have integration tests (>50% coverage)
  3. Canvas, browser, and device tools have integration tests (>50% coverage)
  4. Overall coverage increases from 35% to at least 45%
**Plans**: 3 plans

Plans:
- [ ] 13-01: Add integration tests for canvas API routes
- [ ] 13-02: Add integration tests for browser and device API routes
- [ ] 13-03: Add integration tests for canvas, browser, and device tools

### Phase 14: Property-Based Testing Implementation
**Goal**: Property tests validate system invariants using Hypothesis framework
**Depends on**: Phase 13
**Requirements**: PROP-01, PROP-02, PROP-03, PROP-04, PROP-05
**Success Criteria** (what must be TRUE):
  1. Governance system invariants tested with property tests (maturity levels, permissions)
  2. Episodic memory invariants tested with property tests (segmentation, retrieval, lifecycle)
  3. Streaming LLM invariants tested with property tests (token streaming, provider routing)
  4. Property tests run alongside unit/integration tests without regression
  5. Overall coverage increases from 45% to 50%
**Plans**: 3 plans

Plans:
- [ ] 14-01: Add property tests for governance system invariants
- [ ] 14-02: Add property tests for episodic memory invariants
- [ ] 14-03: Add property tests for streaming LLM invariants

### Phase 15: Verification & Infrastructure Updates
**Goal**: 50% coverage target achieved with all infrastructure operational
**Depends on**: Phase 14
**Requirements**: COV-01, INF-01, INF-02, INF-03, INF-04
**Success Criteria** (what must be TRUE):
  1. Overall coverage reaches 50% (from 15.2%, +34.8 percentage points)
  2. Coverage trend tracking updates automatically after each test run
  3. Pre-commit coverage hook enforces 80% minimum for new code
  4. CI pass rate check provides detailed metrics (not just informational)
  5. Coverage reports include HTML, JSON, and trend analysis
**Plans**: 2 plans

Plans:
- [ ] 15-01: Verify 50% coverage target achieved
- [ ] 15-02: Update test infrastructure (trend tracking, CI metrics, reporting)

---

*Last Updated: 2026-02-15*
*Current Milestone: v1.1 Coverage Expansion to 50%*
*Next Action: Execute Phase 10 - Fix Remaining Test Failures*
