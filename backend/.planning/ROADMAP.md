# Atom Test Coverage Initiative - Roadmap

**Project**: Atom AI-Powered Business Automation Platform
**Initiative**: Test Coverage Improvement & Quality Assurance
**Current Coverage**: 25.8% backend (measured), 18.18% frontend (as of 2026-04-25, Phase 299 completion)
**Target Coverage**: 45% backend, 25% frontend (coverage acceleration milestone)

---

## Current Milestone: Backend Coverage Expansion to 45%

**Goal**: Achieve 45% backend coverage through 7 focused phases (300-306) testing high-impact orchestration and service files

**Started**: 2026-04-25
**Status**: PLANNING Phase 300

**Strategy**: Test top 3 orchestration files per phase → Target 25-30% coverage per file → Progressive coverage growth toward 45%

**Completed Waves**:
- Wave 1 (Phase 293): 30% target achieved
- Wave 2-3 (Phase 295): +0.4pp increase (37.1% coverage)
- Wave 4 (Phase 296): +1.5-2.0pp increase (38.6-39.1% coverage, 143 new tests)
- Wave 5 (Phase 297): +1.2-1.5pp increase (39.8-40.6% coverage, 121 new tests)
- Wave 6 (Phase 298): 4 coordination/integration files tested (83 tests, 91.6% pass rate)
- Wave 7 (Phase 299): Coverage verification & roadmap creation (VERIFIED: 25.8% backend, 7 phases to 45%)

---

## Phases

### Legacy Phases (v5.5 Milestone - 80% target)
- [ ] **Phase 220: Fix Industry Workflow Test Failures** - Fix 10 failing tests in industry workflow endpoints
- [ ] **Phase 221: Fix 2FA Routes Test Errors** - Resolve 24 test errors in 2FA routes
- [ ] **Phase 222: Core Services Coverage Expansion** - Push core services coverage to 80%
- [ ] **Phase 223: API Routes Coverage Expansion** - Push API routes coverage to 80%
- [ ] **Phase 224: Tools & Integration Coverage** - Push tools and integration coverage to 80%
- [ ] **Phase 225: Coverage Verification & Reports** - Generate coverage reports and verify 80% target
- [ ] **Phase 226: Quality Gates Enforcement** - Ensure 98% pass rate and re-enable CI/CD

### Current Acceleration Phases (45% Backend Target)
- [x] **Phase 293: Coverage Wave 1 - 30% Target** - Achieve 30% backend coverage baseline
- [x] **Phase 295: Coverage Wave 2-3** - +0.4pp increase (37.1% coverage, 831 new tests)
- [x] **Phase 296: Backend Acceleration Wave 4** - +1.5-2.0pp increase (38.6-39.1% coverage, 143 new tests)
- [x] **Phase 297: Backend Acceleration Wave 5** - +1.2-1.5pp increase (39.8-40.6% coverage, 121 new tests)
- [x] **Phase 298: Backend Acceleration Wave 6** - Test 4 coordination/integration files (83 tests, 91.6% pass rate)
- [x] **Phase 299: Coverage Verification & Milestone Completion** - Comprehensive coverage reports, gap analysis, roadmap for Phase 300+ (VERIFIED: 25.8% backend, 7 phases to 45%)
- [ ] **Phase 300: Orchestration Wave 1 - Top 3 Files** - Test workflow_engine.py, atom_agent_endpoints.py, agent_world_model.py (target: 28.5% coverage)
- [ ] **Phase 301: Orchestration Wave 2 - Next 3 Files** - Test atom_meta_agent.py, workflow_debugger.py, hybrid_data_ingestion.py (target: 31.2% coverage)
- [ ] **Phase 302: Services Wave 1 - Top 3 Files** - Test llm/byok_handler.py, episode_segmentation_service.py, lancedb_handler.py (target: 33.9% coverage)
- [ ] **Phase 303: Services Wave 2 - Next 3 Files** - Test learning_service_full.py + 2 more (target: 36.6% coverage)
- [ ] **Phase 304: API Endpoints Wave 1** - Test 5-6 zero-coverage API files (target: 39.3% coverage)
- [ ] **Phase 305: API Endpoints Wave 2** - Test 5-6 zero-coverage API files (target: 42.0% coverage)
- [ ] **Phase 306: Final Push** - Test remaining high-impact files (target: 44.7% → 45% coverage)

---

## Phase Details

### Phase 300: Orchestration Wave 1 - Top 3 Files (PLANNING)

**Goal**: Create comprehensive tests for top 3 orchestration files with highest coverage gaps to achieve 25-30% coverage on each file

**Depends on**: Phase 299

**Requirements**: None (acceleration phase)

**Status**: PLANNING

**Success Criteria** (what must be TRUE):
1. 3 new test files created (test_workflow_engine.py, test_atom_agent_endpoints.py, test_agent_world_model.py)
2. 38-42 total tests across 3 files
3. Each file achieves 25-30% coverage (not 100%)
4. All tests pass (100% pass rate)
5. Backend coverage increases by +2.5-2.9pp (25.8% → 28.3-28.7%)
6. 954 lines of production code covered
7. Tests follow Phase 297-298 patterns (AsyncMock, patch at import, fixtures)

**Plans**: 1 plan
- [ ] 300-01-PLAN.md — Create comprehensive tests for top 3 orchestration files

**Target Files**:
- `core/workflow_engine.py` (1,219 lines, 6.81% → 30%, target: +465 lines)
- `core/atom_agent_endpoints.py` (779 lines, 12.32% → 30%, target: +254 lines)
- `core/agent_world_model.py` (712 lines, 11.94% → 30%, target: +235 lines)

**Expected Deliverables**:
- test_workflow_engine.py — 19 tests, ~500 lines, 30% coverage
- test_atom_agent_endpoints.py — 10 tests, ~350 lines, 30% coverage
- test_agent_world_model.py — 9 tests, ~350 lines, 30% coverage

**Expected Outcomes**:
- Total tests: 38 tests
- Total test lines: ~1,200 lines
- Lines covered: 954 lines
- Backend coverage: 28.3-28.7% (+2.5-2.9pp from 25.8% baseline)

---

### Phase 299: Coverage Verification & Milestone Completion (COMPLETE)

**Goal**: Run comprehensive coverage verification, identify gaps, fix failing tests, and create data-backed roadmap for next phase

**Depends on**: Phase 298

**Requirements**: None (verification and analysis phase)

**Status**: ✅ COMPLETE

**Achievements**:
- Comprehensive coverage reports generated (JSON, HTML, terminal)
- Actual backend coverage measured: 25.8% (23,498 of 91,078 lines)
- Top 10 files with highest coverage gaps identified
- Effort to 45% calculated: 17,486 lines, ~699 tests, 7 phases (300-306), ~14 hours
- 7 failing agent_governance_service tests fixed (100% pass rate achieved)
- 3 missing production modules documented (specialist_matcher, recruitment_analytics_service, fleet_optimization_service)
- Data-backed roadmap for Phase 300+ created (7 phases to 45%)
- Comprehensive VERIFICATION.md report generated

**Plans**: 1/1 complete
- [x] 299-01-PLAN.md — Coverage verification, gap analysis, test fixes, and roadmap creation

**Deliverables**:
- ✅ 299-COVERAGE-REPORT.md — Comprehensive coverage analysis with metrics
- ✅ 299-GAP-ANALYSIS.md — Top 10 files with highest coverage gaps
- ✅ 299-ROADMAP.md — Data-backed roadmap for Phase 300+ (7 phases to 45%)
- ✅ 299-VERIFICATION.md — Milestone completion verification report

---

### Phase 298: Backend Acceleration Wave 6 (COMPLETE)

**Goal**: Test 4 high-impact agent coordination and integration services to achieve 25-35% coverage per file

**Depends on**: Phase 297

**Requirements**: None (acceleration phase)

**Status**: ✅ COMPLETE

**Achievements**:
- 4 test files created (fleet_admiral, queen_agent, intent_classifier, agent_governance_service)
- 83 new tests (3,193 lines of test code)
- Combined coverage: 66% for Phase 298 files
- Test pass rate: 91.6% (76/83 passing, 7 failing in agent_governance_service)
- Backend coverage: ~26% (actual measured from comprehensive report)

**Plans**: 1/1 complete
- [x] 298-01-PLAN.md — Create comprehensive tests for 4 coordination/integration services

**Target Files**:
- `core/fleet_admiral.py` (~2000 lines) - Dynamic agent recruitment, unstructured task orchestration, blackboard coordination
- `core/agents/queen_agent.py` (~1500 lines) - Structured workflow automation, blueprint execution, governance integration
- `core/intent_classifier.py` (~800 lines) - Intent classification (CHAT/WORKFLOW/TASK), routing logic, confidence scoring
- `core/agent_governance_service.py` (~1200 lines) - Agent lifecycle, maturity checks, permission validation, governance cache

**Deviations**:
- Sys.modules mocking for missing production modules (specialist_matcher, recruitment_analytics_service, fleet_optimization_service)
- 7/12 agent_governance_service tests failing (budget enforcement integration complexity)
- Fixed in Phase 299

---

### Phase 297: Backend Acceleration Wave 5 (COMPLETE)

**Goal**: Test 4 high-impact orchestration and analytics services to achieve 25-35% coverage per file

**Depends on**: Phase 296

**Requirements**: None (acceleration phase)

**Status**: ✅ COMPLETE

**Achievements**:
- 4 test files created (atom_meta_agent, workflow_analytics_engine, fleet_coordinator_service, entity_type_service)
- 121 new tests (3,390 lines of test code)
- Backend coverage: ~39.8-40.6% (+1.2-1.5pp increase from 38.6-39.1% baseline)
- Gap to 45% target: ~4.4-5.2pp (reduced from 5.9-6.4pp)

**Plans**: 1/1 complete
- [x] 297-01-PLAN.md — Create comprehensive tests for 4 orchestration/analytics services

---

## Progress Table

### Acceleration Phases (Current Milestone)

| Phase | Plans Complete | Status | Backend Coverage | Increase |
|-------|----------------|--------|------------------|----------|
| 293. Coverage Wave 1 | 6/6 | Complete | 30.0% | - |
| 295. Coverage Wave 2-3 | 2/2 | Complete | 37.1% | +0.4pp |
| 296. Backend Acceleration Wave 4 | 3/3 | Complete | 38.6-39.1% | +1.5-2.0pp |
| 297. Backend Acceleration Wave 5 | 1/1 | Complete | 39.8-40.6% | +1.2-1.5pp |
| 298. Backend Acceleration Wave 6 | 1/1 | Complete | 25.8% (actual) | -13pp (scale issue) |
| 299. Coverage Verification & Milestone | 1/1 | Complete | 25.8% | 0pp (baseline verified) |
| 300. Orchestration Wave 1 | 0/1 | Planning | 28.3-28.7% | +2.5-2.9pp (target) |
| 301. Orchestration Wave 2 | 0/1 | Not started | 31.2% | +2.7pp (target) |
| 302. Services Wave 1 | 0/1 | Not started | 33.9% | +2.7pp (target) |
| 303. Services Wave 2 | 0/1 | Not started | 36.6% | +2.7pp (target) |
| 304. API Endpoints Wave 1 | 0/1 | Not started | 39.3% | +2.7pp (target) |
| 305. API Endpoints Wave 2 | 0/1 | Not started | 42.0% | +2.7pp (target) |
| 306. Final Push | 0/1 | Not started | 45.0% | +3.0pp (target) |

**Note**: Phase 298 shows apparent decrease due to comprehensive coverage measurement revealing actual baseline (91K total lines vs. previous estimates of ~50-60K lines). Phase 299 verified 25.8% as authoritative baseline.

### Legacy Phases (v5.5 Milestone - 80% target)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 220. Fix Industry Workflow Test Failures | 0/1 | Planning | - |
| 221. Fix 2FA Routes Test Errors | 0/1 | Planning | - |
| 222. Core Services Coverage Expansion | 0/0 | Not started | - |
| 223. API Routes Coverage Expansion | 0/0 | Not started | - |
| 224. Tools & Integration Coverage | 0/0 | Not started | - |
| 225. Coverage Verification & Reports | 0/0 | Not started | - |
| 226. Quality Gates Enforcement | 0/0 | Not started | - |

---

## Dependencies

**Acceleration Phases**: Phase 293 → Phase 295 → Phase 296 → Phase 297 → Phase 298 → Phase 299 → **Phase 300** → Phase 301 → Phase 302 → Phase 303 → Phase 304 → Phase 305 → Phase 306

- Phase 299 must complete before 300 (roadmap needed for execution)
- Phase 300-306 follow sequential execution (7 phases to 45% target)

**Legacy Phases**: Phase 220 → Phase 221 → Phase 222 → Phase 223 → Phase 224 → Phase 225 → Phase 226

---

## Coverage Metrics

### Actual Baseline (Phase 299 - April 2026) - AUTHORITATIVE
- **Backend Coverage**: 25.8% (23,498 of 91,078 lines) - **ACTUAL MEASURED**
- **Frontend Coverage**: 18.18% (no change - import issues remain)
- **Backend Scale**: 91,078 lines (major scale issue confirmed)
- **Frontend Scale**: ~26,275 lines
- **Backend Target**: 45% (19.2pp gap from current 25.8%)
- **Frontend Target**: 25% (6.82pp gap remaining)

### Phase 299 Achievements
- **Comprehensive Reports**: JSON, HTML, terminal coverage reports generated
- **Gap Analysis**: Top 10 files with highest coverage gaps identified
- **Effort Calculation**: 17,486 lines needed, ~699 tests, 7 phases (300-306), ~14 hours
- **Test Fixes**: 7 agent_governance_service tests fixed (100% pass rate)
- **Roadmap**: Data-backed 7-phase plan to 45% backend coverage
- **Missing Modules**: 3 documented (specialist_matcher, recruitment_analytics_service, fleet_optimization_service)

### Phase 300 Objectives (Orchestration Wave 1)
- **Target Files**: workflow_engine.py, atom_agent_endpoints.py, agent_world_model.py
- **Coverage Target**: 25-30% per file (not 100%)
- **Lines to Cover**: 954 lines (465 + 254 + 235)
- **Tests Needed**: ~38 tests (19 + 10 + 9)
- **Expected Coverage**: 28.3-28.7% (+2.5-2.9pp from 25.8% baseline)

### Ultimate Goals
- **Backend Coverage**: 45% (41,000 of 91,078 lines)
- **Frontend Coverage**: 25% (6,569 of ~26,275 lines)
- **Quality Gates**: 98%+ test pass rate, CI/CD enforcement

---

## Testing Strategy

### Backend Acceleration (Phases 293-298)
- Test high-impact backend files (25-35% coverage per file)
- Focus on orchestration, coordination, and integration logic
- Use AsyncMock for async services, patch at import location
- Follow established patterns from Phase 295-297
- Progressive coverage expansion toward 45% backend target

### Coverage Verification (Phase 299)
- Run actual coverage reports (pytest-cov with JSON, HTML, terminal)
- Measure real backend coverage percentage (not estimates)
- Identify scale issues (91K lines dilutes coverage impact)
- Calculate realistic effort to reach 45% target
- Fix failing tests (7 agent_governance_service budget integration tests)
- Document missing production modules

### Backend Expansion to 45% (Phases 300-306)
- **Wave 1 (Phase 300)**: Top 3 orchestration files (workflow_engine, atom_agent_endpoints, agent_world_model)
- **Wave 2 (Phase 301)**: Next 3 orchestration files (atom_meta_agent, workflow_debugger, hybrid_data_ingestion)
- **Wave 3 (Phase 302)**: Top 3 service files (llm/byok_handler, episode_segmentation_service, lancedb_handler)
- **Wave 4 (Phase 303)**: Next 3 service files (learning_service_full + 2 more)
- **Wave 5-6 (Phases 304-305)**: API endpoints (10-12 zero-coverage API files)
- **Wave 7 (Phase 306)**: Final push to 45% (remaining high-impact files)
- **Strategy**: Target 25-30% coverage per file (not 100% line coverage)
- **Pattern**: AsyncMock, patch at import, SQLAlchemy fixtures, success + error paths

### Frontend Unblock (Future Phase)
- Fix Jest import path configuration (@lib/ alias)
- Unblock 450 frontend tests (+1.5-2pp frontend coverage)
- Test existing high-impact files (api.ts, auth.ts, hubspotApi.ts)

### Quality Enforcement (Future Phase)
- Achieve 98%+ overall test pass rate
- Implement quality gates (pre-commit, CI, trend tracking)
- Re-enable CI/CD workflows with coverage enforcement

---

## Notes

### Key Insights
1. **Scale issue confirmed**: 91,078 backend lines (not 50-60K as estimated)
2. **Baseline verified**: 25.8% actual coverage (15.2pp lower than previous estimates)
3. **Phase 298 successful**: 83 tests, 100% pass rate after fixes, 66% combined coverage on target files
4. **Missing production modules**: 3 modules documented (specialist_matcher, recruitment_analytics_service, fleet_optimization_service)
5. **Patterns established**: AsyncMock, patch at import, fixtures working well
6. **Roadmap validated**: 7 phases (300-306) to reach 45% coverage, data-backed effort calculation

### Risks
1. **Timeline risk**: Coverage growth may be slower than estimated (1.1pp per phase in Phases 295-298)
2. **Complexity risk**: Orchestration files are complex (async, multi-agent, distributed systems)
3. **Quality risk**: Test pass rate may drop as more tests added (currently 100%)
4. **Missing modules risk**: Production code references non-existent modules (3 documented)
5. **Scale risk**: 91K line codebase dilutes overall coverage impact

### Opportunities
1. **Accurate baseline**: Phase 299 verified 25.8% as authoritative baseline
2. **Data-backed roadmap**: 7-phase plan to 45% with specific file targets
3. **High-impact files**: Top 10 files with highest gaps identified
4. **Test quality**: 100% pass rate achieved, patterns established
5. **Clear strategy**: Orchestration → Services → API progression

---

*Last Updated: 2026-04-25*
*Next Action: Execute Phase 300 - Orchestration Wave 1 (Top 3 Files)*
*Milestone: Backend Coverage Expansion to 45% (Actual: 25.8% backend, Target: 45% backend)*
