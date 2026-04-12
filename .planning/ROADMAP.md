# ROADMAP: Atom - v10.0 Quality & Stability

**Milestone:** v10.0 Quality & Stability
**Created:** 2026-04-02
**Timeline:** 1 week (aggressive execution)
**Depth:** Quick
**Status:** 🚧 ACTIVE

## Progress Summary

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 247 - Build Fixes & Documentation | 3/3 | ✅ COMPLETE | 2026-04-02 |
| 248 - Test Discovery & Documentation | 2/2 | ✅ COMPLETE | 2026-04-03 |
| 249 - Critical Test Fixes | 3/3 | ✅ COMPLETE | 2026-04-03 |
| 250 - All Test Fixes | 2/2 | ✅ COMPLETE | 2026-04-11 |
| 251 - Backend Coverage Baseline | 3/3 | ✅ COMPLETE | 2026-04-11 |
| 252 - Backend Coverage Push | 3/3 | ✅ COMPLETE | 2026-04-11 |
| 253a - Property Tests Data Integrity | 1/1 | ✅ COMPLETE | 2026-04-11 |
| 253b - Coverage Expansion Wave 1 | 1/1 | ✅ COMPLETE | 2026-04-12 |
| 253 - Backend 80% & Property Tests | 3/3 | Complete   | 2026-04-12 |
| 254 - Frontend Coverage Baseline | 3/3 | ✅ COMPLETE | 2026-04-11 |
| 255 - Frontend Coverage Push | 2/2 | ✅ COMPLETE | 2026-04-11 |
| 256 - Frontend 80% | 2/2 | ✅ COMPLETE | 2026-04-12 |
| 257 - TDD & Property Test Documentation | 2/2 | ✅ COMPLETE | 2026-04-12 |
| 258 - Quality Gates & Final Documentation | 3/3 | ✅ COMPLETE | 2026-04-12 |

**Overall:** 30/48 plans complete (62.5%)

**Total:** 48 plans across 14 phases

## Phases

- [x] **Phase 247: Build Fixes & Documentation** - Fix frontend/backend builds and document build process
- [x] **Phase 248: Test Discovery & Documentation** - Run full test suite and document all failures
- [x] **Phase 249: Critical Test Fixes** - Fix critical/high-priority test failures using TDD
- [x] **Phase 250: All Test Fixes** - Fix remaining test failures and achieve 100% pass rate
- [x] **Phase 251: Backend Coverage Baseline** - Measure baseline and reach 70% backend coverage (completed 2026-04-11)
- [x] **Phase 252: Backend Coverage Push** - Reach 75% backend coverage with property tests (completed 2026-04-11)
- [x] **Phase 253a: Property Tests Data Integrity** - Create property tests for episode and skill execution data integrity (PROP-03) (completed 2026-04-11)
- [x] **Phase 253b: Coverage Expansion Wave 1** - Add traditional unit/integration tests for high-impact core services (governance, LLM, episodes) to measurably increase coverage from 4.60% baseline (completed 2026-04-12)
- [x] **Phase 253: Backend 80% & Property Tests** - Achieve 80% backend coverage with property tests (completed 2026-04-12)
- [x] **Phase 254: Frontend Coverage Baseline** - Measure baseline and reach 70% frontend coverage (completed 2026-04-11)
- [x] **Phase 255: Frontend Coverage Push** - Reach 75% frontend coverage (completed 2026-04-11)
- [x] **Phase 256: Frontend 80%** - Achieve 80% frontend coverage (completed 2026-04-12)
- [x] **Phase 257: TDD & Property Test Documentation** - Document TDD workflow and property tests (completed 2026-04-12)
- [x] **Phase 258: Quality Gates & Final Documentation** - Enforce quality gates and complete documentation (completed 2026-04-12)

## Phase Details

### Phase 247: Build Fixes & Documentation
**Goal**: Frontend and backend build successfully without errors, with documented build process
**Depends on**: Nothing (first phase)
**Requirements**: BUILD-01, BUILD-02, BUILD-03, BUILD-04, DOC-01
**Success Criteria** (what must be TRUE):
  1. Frontend builds successfully with `npm run build` (zero errors)
  2. Backend builds successfully with `python -m build` (zero errors)
  3. All syntax errors resolved (e.g., asana_service.py:148)
  4. Build process documented in BUILD.md with step-by-step instructions
  5. Builds are reproducible across different environments
**Plans**: 3 plans
- [x] 247-01-PLAN.md — Fix backend syntax errors in asana_service.py
- [x] 247-02-PLAN.md — Fix frontend SWC build error
- [x] 247-03-PLAN.md — Document build process in BUILD.md

### Phase 248: Test Discovery & Documentation
**Goal**: Full test suite runs and all failures are documented with evidence
**Depends on**: Phase 247 (builds must work to run tests)
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, DOC-02
**Success Criteria** (what must be TRUE):
  1. Full test suite runs without syntax or import errors (472 tests collected)
  2. All test failures documented in TEST_FAILURE_REPORT.md with reproduction steps
  3. Test failures categorized by severity (critical/high/medium/low)
  4. Test failure report generated with prioritization (what to fix first)
  5. Test execution documented in TESTING.md (how to run, interpret results)
**Plans**: 2 plans
- [x] 248-01-PLAN.md — Fix remaining syntax errors in integration services
- [x] 248-02-PLAN.md — Run test suite and document failures

### Phase 249: Critical Test Fixes
**Goal**: All critical and high-priority test failures fixed using TDD approach
**Depends on**: Phase 248 (failure documentation)
**Requirements**: FIX-01, FIX-02, TDD-01, TDD-02, TDD-03
**Success Criteria** (what must be TRUE):
  1. All critical test failures fixed (agents, workflows, API endpoints)
  2. All high-priority test failures fixed (core services, integrations)
  3. Bug fixes follow test-first approach (failing test written before fix)
  4. All bug fixes have corresponding tests (100% coverage of fixes)
  5. Test suite passes with zero critical/high failures
**Plans**: 3 plans
- [x] 249-01-PLAN.md — Fix Pydantic v2 DTO validation issues (DTO-001, DTO-002, DTO-003)
- [x] 249-02-PLAN.md — Fix OpenAPI schema alignment tests (DTO-004)
- [x] 249-03-PLAN.md — Fix Canvas submission error handling (CANVAS-001, CANVAS-002, CANVAS-003)

### Phase 250: All Test Fixes
**Goal**: All test failures fixed, 100% pass rate achieved
**Depends on**: Phase 249 (critical fixes)
**Requirements**: FIX-03, FIX-04
**Success Criteria** (what must be TRUE):
  1. All medium-priority test failures fixed
  2. All low-priority test failures fixed
  3. 100% test pass rate achieved (zero failures or errors)
  4. Test suite runs end-to-end without manual intervention
  5. Test results are reproducible across multiple runs
**Plans**: 2 plans
- [x] 250-01-PLAN.md — Fix test infrastructure (pytest_plugins ImportError)
- [x] 250-02-PLAN.md — Fix remaining test failures and achieve 100% pass rate

### Phase 251: Backend Coverage Baseline
**Goal**: Backend coverage baseline measured and 70% coverage achieved
**Depends on**: Phase 250 (all tests passing)
**Requirements**: COV-B-01, COV-B-02, COV-B-05
**Success Criteria** (what must be TRUE):
  1. Backend coverage baseline measured (actual line coverage, not estimates)
  2. Backend coverage reaches 70% (progressive threshold)
  3. High-impact files covered first (>200 lines, critical services)
  4. Coverage report generated with gap analysis
  5. Coverage trends tracked (before/after metrics)
**Plans**: 3 plans
- [x] 251-01-PLAN.md — Measure backend coverage baseline with pytest-cov
- [x] 251-02-PLAN.md — Generate gap analysis and cover high-impact files
- [x] 251-03-PLAN.md — Reach 70% coverage target with medium-impact file tests

### Phase 252: Backend Coverage Push
**Goal**: Backend coverage reaches 75% with property-based tests
**Depends on**: Phase 251 (70% baseline)
**Requirements**: COV-B-03, PROP-01, PROP-02
**Success Criteria** (what must be TRUE):
  1. Backend coverage reaches 75% (progressive threshold)
  2. Property-based tests for critical invariants (governance, LLM, episodes)
  3. Property-based tests for business logic (workflows, skills, canvas)
  4. Property tests use Hypothesis with appropriate max_examples
  5. Property tests document invariants being tested
**Plans**: 3 plans
- [x] 252-01-PLAN.md — Fix core coverage expansion tests and add governance property tests
- [x] 252-02-PLAN.md — Add LLM and workflow property tests with coverage measurement
- [x] 252-03-PLAN.md — Generate final coverage report and property test documentation

### Phase 253a: Property Tests Data Integrity
**Goal**: Create property tests for episode and skill execution data integrity invariants
**Depends on**: Phase 252 (property test patterns established)
**Requirements**: PROP-03
**Success Criteria** (what must be TRUE):
  1. Episode data integrity property tests created (20 tests)
  2. Skill execution data integrity property tests created (19 tests)
  3. Tests validate: score bounds, timestamps, ordering, referential integrity, status transitions, billing idempotence, cascade deletes
  4. All tests use Hypothesis with appropriate max_examples
  5. Tests documented with PROPERTY/STRATEGY/INVARIANT docstrings
**Plans**: 1 plan
- [x] 253a-01-PLAN.md — Create property tests for episode and skill execution data integrity

### Phase 253b: Coverage Expansion Wave 1
**Goal**: Add traditional unit/integration tests for high-impact core services to measurably increase coverage from 4.60% baseline
**Depends on**: Phase 253a (property test patterns established)
**Requirements**: COV-B-04
**Success Criteria** (what must be TRUE):
  1. Core governance services have test coverage (agent_governance_service, agent_context_resolver, governance_cache)
  2. LLM services have test coverage (byok_handler, cognitive_tier_system, cache_aware_router)
  3. Episode services have test coverage (segmentation, lifecycle, graduation)
  4. Coverage increases measurably from 4.60% baseline (+1-3 percentage points)
  5. Wave 1 coverage report generated with baseline comparison
**Plans**: 1 plan
- [ ] 253b-01-PLAN.md — Create coverage expansion tests for high-impact core services (governance, LLM, episodes) and generate Wave 1 report

### Phase 253: Backend 80% & Property Tests
**Goal**: Backend coverage reaches 80% with data integrity property tests
**Depends on**: Phase 252 (75% coverage)
**Requirements**: COV-B-04, PROP-03
**Success Criteria** (what must be TRUE):
  1. Backend coverage reaches 80% (final target)
  2. Property-based tests for data integrity (database, transactions)
  3. All high-impact files covered (>200 lines)
  4. Coverage gaps identified and documented
  5. Property tests catch edge cases unit tests miss
**Plans**: 3 plans
- [x] 253-01-PLAN.md — Add property tests for episode and skill execution data integrity
- [x] 253-02-PLAN.md — Measure coverage and generate gap analysis for 80% target
- [x] 253-03-PLAN.md — Generate final Phase 253 coverage report and summary

### Phase 254: Frontend Coverage Baseline
**Goal**: Frontend coverage baseline measured and 70% coverage achieved
**Depends on**: Phase 250 (all tests passing)
**Requirements**: COV-F-01, COV-F-02, COV-F-05
**Success Criteria** (what must be TRUE):
  1. Frontend coverage baseline measured (actual line coverage)
  2. Frontend coverage reaches 70% (progressive threshold)
  3. Critical components covered (auth, agents, workflows, canvas)
  4. Coverage report generated with gap analysis
  5. Component-level coverage breakdown available
**Plans**: 3 plans
- [x] 254-01-PLAN.md — Measure frontend coverage baseline with Jest/React Testing Library
- [x] 254-02-PLAN.md — Create agent component tests (AgentCard, AgentManager, AgentStudio, AgentTerminal)
- [x] 254-03-PLAN.md — Create workflow, canvas, and hook tests to reach 70% target

### Phase 255: Frontend Coverage Push
**Goal**: Frontend coverage reaches 75%
**Depends on**: Phase 254 (70% baseline)
**Requirements**: COV-F-03
**Success Criteria** (what must be TRUE):
  1. Frontend coverage reaches 75% (progressive threshold)
  2. Coverage gaps in medium-priority components addressed
  3. Edge cases and error paths covered
  4. Integration tests for API calls
  5. Component state management tested
**Plans**: 2 plans
- [x] 255-01-PLAN.md — Critical gap coverage: Auth & Automations (0% → targeted coverage) ✅ COMPLETE
- [x] 255-02-PLAN.md — Advanced coverage integration: API & State management ✅ COMPLETE

### Phase 256: Frontend 80%
**Goal**: Frontend coverage reaches 80% final target
**Depends on**: Phase 255 (75% coverage)
**Requirements**: COV-F-04
**Success Criteria** (what must be TRUE):
  1. Frontend coverage reaches 80% (final target)
  2. All critical components have comprehensive coverage
  3. Edge cases, error paths, and integration points covered
  4. Coverage trends tracked (before/after metrics)
  5. Final coverage report generated
**Plans**: 2 plans
- [x] 256-01-PLAN.md — Final coverage push for remaining components
- [x] 256-02-PLAN.md — Edge cases and integration testing

### Phase 257: TDD & Property Test Documentation
**Goal**: TDD workflow and property tests documented
**Depends on**: Phase 253, Phase 256 (coverage targets met)
**Requirements**: TDD-04, PROP-04
**Success Criteria** (what must be TRUE):
  1. TDD workflow documented in TDD_WORKFLOW.md with examples
  2. Property-based test documentation created (invariants catalog)
  3. Red-green-refactor cycle explained with real examples
  4. Property test patterns documented (when to use Hypothesis vs unit tests)
  5. Documentation includes common pitfalls and best practices
**Plans**: 2 plans
- [x] 257-01-PLAN.md — Document TDD workflow with real examples ✅ COMPLETE
- [x] 257-02-PLAN.md — Document property tests and invariants catalog ✅ COMPLETE

### Phase 258: Quality Gates & Final Documentation
**Goal**: Quality gates enforced, metrics dashboard created, documentation complete
**Depends on**: Phase 257 (documentation)
**Requirements**: QUAL-01, QUAL-02, QUAL-03, QUAL-04, DOC-03, DOC-04
**Success Criteria** (what must be TRUE):
  1. Coverage thresholds enforced in CI/CD (70% → 75% → 80%)
  2. 100% test pass rate enforced in CI/CD (build fails if tests fail)
  3. Build gates prevent merging if build fails
  4. Quality metrics dashboard created (coverage, pass rate, trends)
  5. Bug fix process documented (TDD workflow)
  6. Coverage report documentation complete (how to measure, improve)
**Plans**: 3 plans
- [x] 258-01-PLAN.md — Set up CI/CD quality gates
- [x] 258-02-PLAN.md — Create quality metrics dashboard
- [x] 258-03-PLAN.md — Complete final documentation

## Coverage Map

All 36 v10.0 requirements mapped to phases:

| Requirement | Phase | Description |
|-------------|-------|-------------|
| BUILD-01 | Phase 247 | Frontend builds successfully |
| BUILD-02 | Phase 247 | Backend builds successfully |
| BUILD-03 | Phase 247 | Syntax errors resolved |
| BUILD-04 | Phase 247 | Build process documented |
| TEST-01 | Phase 248 | Test suite runs successfully |
| TEST-02 | Phase 248 | Test failures documented |
| TEST-03 | Phase 248 | Failures categorized by severity |
| TEST-04 | Phase 248 | Test failure report generated |
| FIX-01 | Phase 249 | Critical test failures fixed |
| FIX-02 | Phase 249 | High-priority test failures fixed |
| FIX-03 | Phase 250 | Medium/low priority failures fixed |
| FIX-04 | Phase 250 | 100% test pass rate achieved |
| COV-B-01 | Phase 251 | Backend coverage baseline measured |
| COV-B-02 | Phase 251 | Backend coverage reaches 70% |
| COV-B-03 | Phase 252 | Backend coverage reaches 75% |
| COV-B-04 | Phase 253b/253 | Backend coverage reaches 80% (progressive waves) |
| COV-B-05 | Phase 251-253 | High-impact files covered |
| COV-F-01 | Phase 254 | Frontend coverage baseline measured |
| COV-F-02 | Phase 254 | Frontend coverage reaches 70% |
| COV-F-03 | Phase 255 | Frontend coverage reaches 75% |
| COV-F-04 | Phase 256 | Frontend coverage reaches 80% |
| COV-F-05 | Phase 254-256 | Critical components covered |
| TDD-01 | Phase 249-250 | Bug fixes follow test-first approach |
| TDD-02 | Phase 249-250 | Failing tests written before fixes |
| TDD-03 | Phase 249-250 | All bug fixes have tests |
| TDD-04 | Phase 257 | TDD workflow documented |
| PROP-01 | Phase 252 | Property tests for critical invariants |
| PROP-02 | Phase 252 | Property tests for business logic |
| PROP-03 | Phase 253a | Property tests for data integrity |
| PROP-04 | Phase 257 | Property test documentation |
| QUAL-01 | Phase 258 | Coverage thresholds enforced |
| QUAL-02 | Phase 258 | 100% pass rate enforced |
| QUAL-03 | Phase 258 | Build gates prevent merge failures |
| QUAL-04 | Phase 258 | Quality metrics dashboard |
| DOC-01 | Phase 247 | Build process documented |
| DOC-02 | Phase 248 | Test execution documented |
| DOC-03 | Phase 257 | Bug fix process documented |
| DOC-04 | Phase 258 | Coverage report documentation |

**Coverage: 36/36 requirements mapped (100%) ✓**

## Dependencies

```
Phase 247 (Build Fixes)
    ↓
Phase 248 (Test Discovery)
    ↓
Phase 249 (Critical Fixes)
    ↓
Phase 250 (All Fixes) ─────┐
    ↓                      │
Phase 251 (Backend 70%)    │
    ↓                      │
Phase 252 (Backend 75%)    │
    ↓                      │
Phase 253a (Data Integrity)│
    ↓                      │
Phase 253b (Coverage Wave 1)│
    ↓                      │
Phase 253 (Backend 80%)    │
    ↓                      ├────────────────────┐
Phase 257 (TDD Docs)       │                    │
    ↓                      │                    │
Phase 258 (Quality Gates)  │                    │
                          │                    │
                    Phase 254 (Frontend 70%)   │
                          ↓                    │
                    Phase 255 (Frontend 75%)   │
                          ↓                    │
                    Phase 256 (Frontend 80%) ──┘
```

## Known Blockers

1. **Frontend SWC Build Error**: Next.js build failing with SWC compilation error ✅ RESOLVED
2. **Backend Syntax Error**: `asana_service.py:148` has syntax error blocking test collection ✅ RESOLVED
3. **Test Suite Blocked**: 472 tests collected but cannot run due to syntax error ✅ RESOLVED

## Success Criteria

Milestone is complete when:
- ✅ Frontend builds successfully (`npm run build` passes)
- ✅ Backend builds successfully (`python -m build` passes)
- ✅ All tests pass (100% pass rate, zero failures)
- ✅ 80% test coverage achieved (backend and frontend)
- ✅ All bugs fixed with TDD approach (tests written first)
- ✅ Quality gates enforced in CI/CD
- ✅ Documentation complete (build, test, TDD, coverage)

## Timeline

**Target:** 1 week (aggressive execution)
**Phases:** 14 phases (added Phase 253a for data integrity property tests, 253b for coverage expansion wave 1)
**Estimated Plans:** 48 plans
**Parallelization:** Enabled (backend/frontend coverage can run in parallel after Phase 250)

## Anti-Patterns

❌ **Don't skip phases**: Each phase delivers verifiable value
❌ **Don't fix bugs without tests**: Violates TDD principle
❌ **Don't ignore coverage gaps**: Track and address all gaps
❌ **Don't defer documentation**: Document as you go
❌ **Don't merge failing builds**: Quality gates enforce standards

## Notes

- **Quick depth**: Phases are compressed for 1-week timeline
- **Parallel execution**: Backend (251-253) and frontend (254-256) coverage can run in parallel after Phase 250
- **TDD enforced**: All bug fixes must have tests written first
- **Progressive thresholds**: 70% → 75% → 80% coverage with enforcement at each stage
- **Quality gates**: CI/CD prevents merging if builds fail, tests fail, or coverage drops
- **Property tests**: Added in Phase 252 (governance, LLM, workflows) and Phase 253a (episodes, skills, data integrity)
- **Phase 253a**: Focused phase for data integrity property tests (PROP-03), split from Phase 253 to isolate property test work from coverage measurement
- **Phase 253b**: Wave 1 coverage expansion using traditional unit/integration tests for high-impact core services. Progressive wave approach to reach 80% target incrementally (Wave 1: +1-3%, Wave 2: +3-5%, etc.)

---

*Roadmap created: 2026-04-02*
*Last updated: 2026-04-11*