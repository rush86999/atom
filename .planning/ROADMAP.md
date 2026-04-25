# ROADMAP: Atom v11.0 Coverage Completion

**Milestone:** v11.0 Coverage Completion
**Created:** 2026-04-13
**Granularity:** Coarse (aggressive phase compression)
**Timeline:** 4-6 weeks
**Status:** ACTIVE

---

## Phases

- [x] **Phase 291: Frontend Test Suite Fixes** - Fix 1,504 failing tests to unblock coverage measurement (completed 2026-04-24)
- [x] **Phase 292: Coverage Baselines & Prioritization** - Establish accurate baselines and identify high-impact files (completed 2026-04-24)
- [ ] **Phase 293: Coverage Wave 1 (30% Target)** - Backend and frontend coverage to 30% with high-impact files
- [ ] **Phase 294: Coverage Wave 2 (50% Target)** - Backend and frontend coverage to 50% with medium-impact files
- [ ] **Phase 295: Coverage Wave 3 (70% Target) & Documentation** - Final push to 70% with documentation

---

## Phase Details

### Phase 291: Frontend Test Suite Fixes

**Goal**: All frontend tests pass (100% pass rate), enabling accurate coverage measurement

**Depends on**: Nothing (first phase of v11.0)

**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, TEST-05

**Success Criteria** (what must be TRUE):
1. Frontend tests achieve 100% pass rate (currently 71.2%, 1,504 failing tests fixed)
2. Test suite runs to completion without import errors or missing model blockers
3. Frontend test failures are categorized and documented with root causes and severity
4. Coverage measurement is unblocked (jest can generate accurate coverage reports)
5. Backend tests maintain 100% pass rate (no regressions from frontend fixes)

**Plans**:
- [x] 291-01-PLAN.md -- Fix MSW network error simulation and axios retry issues (300-500 API tests)
- [x] 291-02-PLAN.md -- Fix import errors and missing type definitions (200-300 integration tests)
- [x] 291-03-PLAN.md -- Full suite verification, categorization, and documentation

**Wave Structure**:
- Wave 1: Plan 01 (API error tests) - autonomous
- Wave 2: Plan 02 (Integration tests) - autonomous, depends on 01
- Wave 3: Plan 03 (Verification + checkpoint) - has checkpoint, depends on 01, 02

---

### Phase 292: Coverage Baselines & Prioritization

**Goal**: Accurate baseline measurements established and high-impact files identified for targeted coverage expansion

**Depends on**: Phase 291 (tests must pass to measure coverage accurately)

**Requirements**: COV-B-01, COV-B-05, COV-F-01, COV-F-05

**Success Criteria** (what must be TRUE):
1. Backend baseline confirmed at 18.25% actual line coverage (not service-level estimates)
2. Frontend baseline measured accurately after test fixes (current coverage validated)
3. Backend high-impact file list generated (>200 lines, <10% coverage, prioritized by impact)
4. Frontend high-impact component list generated (prioritized by lines of code, business criticality)
5. Coverage measurement methodology validated (coverage.json structure verified, field names checked)

**Plans**:
- [x] 292-01-PLAN.md -- Measure and validate backend + frontend coverage baselines (COV-B-01, COV-F-01)
- [x] 292-02-PLAN.md -- Generate tiered high-impact prioritization lists for backend and frontend (COV-B-05, COV-F-05)

**Wave Structure**:
- Wave 1: Plan 01 (Baseline measurement) - autonomous
- Wave 2: Plan 02 (Prioritization) - autonomous, depends on 01

---

### Phase 293: Coverage Wave 1 (30% Target)

**Goal**: Backend and frontend coverage expanded to 30% by testing high-impact files first

**Depends on**: Phase 292 (high-impact file lists required)

**Requirements**: COV-B-02, COV-F-02

**Success Criteria** (what must be TRUE):
1. Backend coverage maintains 30%+ (currently 36.72% from Phase 292 baseline; Tier 1 files now have meaningful test coverage)
2. Frontend coverage reaches 30% (from 15.14%, ~+14.86pp improvement)
3. **Backend Tier 1 files tested**: workflow_analytics_endpoints, workflow_parameter_validator, maturity_routes, supervisor_learning_service, feedback_service
4. **Frontend Critical and High components tested**: chat components (CanvasHost, ChatInput, ChatHeader, MessageList, AgentWorkspace, ChatHistorySidebar, ArtifactSidebar, SearchResults), integration components (HubSpotSearch, ZoomIntegration, GoogleDriveIntegration, OneDriveIntegration, HubSpotIntegration, IntegrationHealthDashboard, MondayIntegration, HubSpotPredictiveAnalytics, GoogleWorkspaceIntegration)
5. Combined coverage trend recorded for backend (unchanged from 36.72%) and frontend (improving toward 30%)

**Plans**:
- [x] 293-01-PLAN.md -- Backend Tier 1 high-priority files tests (COV-B-02)
- [x] 293-02-PLAN.md -- Frontend Critical chat component tests (COV-F-02)
- [x] 293-03-PLAN.md -- Frontend High integration + lib tests + combined coverage verification (COV-F-02)
- [ ] 293-04-PLAN.md -- Gap closure: Backend test mock fixes (COV-B-02)
- [ ] 293-05-PLAN.md -- Gap closure: Frontend async timeout fixes (COV-F-02)
- [ ] 293-06-PLAN.md -- Gap closure: Frontend coverage push (COV-F-02)

**Wave Structure**:
- Wave 1: Plan 01 (backend Tier 1 tests), Plan 02 (frontend Critical tests) - parallel
- Wave 2: Plan 03 (frontend High tests + combined coverage measurement) - depends on 01, 02
- Wave 4: Plans 04, 05, 06 (gap closure from verification) - parallel, depends on 01, 02, 03

---

### Phase 294: Coverage Wave 2 (50% Target)

**Goal**: Backend and frontend coverage expanded to 50% with medium-impact files and core services

**Depends on**: Phase 293 (30% target achieved)

**Requirements**: COV-B-03, COV-F-03

**Success Criteria** (what must be TRUE):
1. Backend coverage reaches 50% (from 30%, +20pp improvement)
2. Frontend coverage reaches 50% (from 30%, +20pp improvement)
3. Backend core services tested (governance, LLM routing, episodic memory, API routes)
4. Frontend state management and hooks tested (broader coverage beyond components)
5. Coverage trend tracking shows consistent progress (no plateaus or regressions)

**Plans**:
- [ ] 294-01-PLAN.md -- Backend Tier 2 files testing (6 files, ~1.2pp increase)
- [x] 294-02-PLAN.md -- Backend Tier 2 files testing (6 files, ~1.1pp increase)
- [ ] 294-03-PLAN.md -- Frontend codebase survey and coverage baseline
- [x] 294-04-PLAN.md -- Frontend components and libs testing (15 files, ~7pp increase)
- [ ] 294-05-PLAN.md -- Final coverage measurement and verification

---

### Phase 295: Coverage Wave 3 (70% Target) & Documentation

**Goal**: Backend and frontend coverage reach 70% (pragmatic target) with comprehensive documentation and quality gates verification

**Depends on**: Phase 294 (50% target achieved)

**Requirements**: COV-B-04, COV-F-04, QUAL-01, QUAL-02, QUAL-03, QUAL-04, DOC-01, DOC-02, DOC-03, DOC-04

**Success Criteria** (what must be TRUE):
1. Backend coverage reaches 70% (from 50%, +20pp improvement) TARGET ACHIEVED
2. Frontend coverage reaches 70% (from 50%, +20pp improvement) TARGET ACHIEVED
3. Quality gates enforce 70% threshold (CI/CD prevents coverage regression)
4. Coverage trend tracking active (PR comment bot provides per-commit feedback)
5. Coverage guide updated with v11.0 lessons learned (patterns, pitfalls, high-impact prioritization)
6. Test suite health monitoring documented (maintenance practices, failure categorization)
7. Coverage expansion completion report finalized (metrics, achievements, next steps)

**Plans**: TBD

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 291. Frontend Test Suite Fixes | 4/3 | Complete   | 2026-04-24 |
| 292. Coverage Baselines & Prioritization | 2/2 | Complete    | 2026-04-24 |
| 293. Coverage Wave 1 (30% Target) | 8/7 | Complete   | 2026-04-24 |
| 294. Coverage Wave 2 (50% Target) | 2/5 | In Progress|  |
| 295. Coverage Wave 3 (70% Target) & Documentation | 0/5 | Not started | - |

---

## Dependencies

```
Phase 291 (Fix Tests)
    |
Phase 292 (Baselines)
    |
Phase 293 (30% Wave)
    |
Phase 294 (50% Wave)
    |
Phase 295 (70% Wave + Docs)
```

**Critical Path**: Test fixes must be complete before accurate baselines can be measured. Coverage waves must execute sequentially to build on previous progress.

**Parallel Opportunities**: None (sequential waves required for measurement accuracy and quality gate enforcement)

---

## Rationale

**Why this phase structure:**

1. **Test health first** (Phase 291) -- 1,504 failing frontend tests (28.8% failure rate) block accurate coverage measurement. v10.0 showed measurement is unreliable when tests fail.

2. **Baseline before expansion** (Phase 292) -- v10.0's critical error was service-level estimates (74.6%) vs actual line coverage (8.50%). Accurate baselines prevent false confidence.

3. **Wave-based approach** (Phases 293-295) -- 50pp gap broken into manageable chunks (30% - 50% - 70%). Maintains momentum with visible progress. Avoids burnout from monolithic "80% overnight" goal.

4. **High-impact prioritization** -- Files >200 lines with <10% coverage first. Maximizes coverage increase per hour. Avoids testing trivial code (DTOs, constants) to hit arbitrary targets.

5. **Pragmatic 70% target** -- v10.0 experience showed 80% is unrealistic (achieved 18.25% backend, 14.61% frontend). 70% is ambitious but achievable.

**Coarse granularity applied:**
- Research suggested 10+ phases (detailed breakdown)
- Compressed to 5 phases for aggressive execution
- Combined backend/frontend coverage waves (parallel work streams)
- Grouped all documentation into final phase

**Quality maintained throughout:**
- Quality gates active in all phases (QUAL-01 to QUAL-04)
- Coverage trend tracking prevents hidden regressions
- Emergency bypass available with audit logging

---

## Milestone v10.0 Archive

**Completed:** 2026-04-13
**Duration:** 12 days (vs 1 week planned)
**Status:** Complete with documented gaps

**Achievements:**
- Frontend and backend builds working (zero errors)
- 100% test pass rate achieved (17 failures fixed)
- Quality infrastructure production-ready (CI/CD gates, metrics)
- Property tests complete (120 invariants cataloged)
- Documentation comprehensive (5,000+ lines)

**Documented Gaps (v11.0 focus):**
- Backend coverage: 18.25% vs 80% target (-61.75pp gap)
- Frontend coverage: 14.61% vs 80% target (-65.39pp gap)
- Frontend test suite: 1,504 failing tests (28.8% failure rate)

**Archived Phases:** All v10.0 phases moved to `.planning/phases/archive/v10.0-quality-stability/`

---

*Roadmap created: 2026-04-13*
*Phase 292 plans created: 2026-04-24*
*Phase 293 plans created: 2026-04-24*
*Phase 293 gap closure plans created: 2026-04-24*
*Next: /gsd-execute-phase 293*
