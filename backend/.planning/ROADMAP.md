# Atom Test Coverage Initiative - Roadmap

**Project**: Atom AI-Powered Business Automation Platform
**Initiative**: Test Coverage Improvement & Quality Assurance
**Current Coverage**: 38.6-39.1% backend, 18.18% frontend (as of 2026-04-25)
**Target Coverage**: 45% backend, 25% frontend (coverage acceleration milestone)

---

## Current Milestone: Backend Coverage Acceleration - Wave 5

**Goal**: Continue backend coverage acceleration through testing high-impact orchestration and analytics services

**Started**: 2026-04-25
**Status**: PLANNING

**Strategy**: Test high-impact backend files (25-35% coverage per file) → Close gap to 45% backend target → Verify progress

**Previous Waves**:
- Wave 1 (Phase 293): 30% target achieved
- Wave 2-3 (Phase 295): +0.4pp increase (37.1% coverage)
- Wave 4 (Phase 296): +1.5-2.0pp increase (38.6-39.1% coverage, 143 new tests)

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

### Current Acceleration Phases
- [x] **Phase 293: Coverage Wave 1 - 30% Target** - Achieve 30% backend coverage baseline
- [x] **Phase 295: Coverage Wave 2-3** - +0.4pp increase (37.1% coverage, 831 new tests)
- [x] **Phase 296: Backend Acceleration Wave 4** - +1.5-2.0pp increase (38.6-39.1% coverage, 143 new tests)
- [ ] **Phase 297: Backend Acceleration Wave 5** - Test 4 orchestration/analytics files (target 39.8-40.6%)

---

## Phase Details

### Phase 297: Backend Acceleration Wave 5

**Goal**: Test 4 high-impact orchestration and analytics services to achieve 25-35% coverage per file

**Depends on**: Phase 296

**Requirements**: None (acceleration phase)

**Success Criteria** (what must be TRUE):
1. 4 new test files created (atom_meta_agent, workflow_analytics_engine, fleet_coordinator_service, entity_type_service)
2. Individual file coverage: 25-35% per file
3. Total new coverage: ~1,490-1,770 lines across 4 files
4. Backend coverage increase: +1.2-1.5 percentage points
5. New backend coverage: ~39.8-40.6% (from 38.6-39.1% baseline)
6. Gap to 45% target reduced to ~4.4-5.2pp (from 5.9-6.4pp)

**Plans**: 1 plan
- [ ] 297-01-PLAN.md — Create comprehensive tests for 4 orchestration/analytics services (atom_meta_agent, workflow_analytics_engine, fleet_coordinator_service, entity_type_service)

**Target Files**:
- `core/atom_meta_agent.py` (1844 lines) - Domain creation, agent spawning, intent routing, fleet orchestration
- `core/workflow_analytics_engine.py` (1610 lines) - Workflow metrics, analytics aggregation, performance tracking
- `core/fleet_orchestration/fleet_coordinator_service.py` (1032 lines) - Fleet recruitment, task distribution, coordination
- `core/entity_type_service.py` (1079 lines) - Entity type CRUD, schema validation, dynamic model creation

**Expected Impact**:
- 160-180 new tests
- 1,150-1,350 lines of test code
- ~1,490-1,770 lines of backend code covered
- +1.2-1.5pp backend coverage increase

---

## Progress Table

### Acceleration Phases (Current Milestone)

| Phase | Plans Complete | Status | Backend Coverage | Increase |
|-------|----------------|--------|------------------|----------|
| 293. Coverage Wave 1 | 6/6 | Complete | 30.0% | - |
| 295. Coverage Wave 2-3 | 2/2 | Complete | 37.1% | +0.4pp |
| 296. Backend Acceleration Wave 4 | 3/3 | Complete | 38.6-39.1% | +1.5-2.0pp |
| 297. Backend Acceleration Wave 5 | 0/1 | Planning | 39.8-40.6% (target) | +1.2-1.5pp (target) |

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

**Acceleration Phases**: Phase 293 → Phase 295 → Phase 296 → **Phase 297** → Phase 298 (TBD)

- Phase 296 must complete before 297 (establish patterns, baseline coverage)
- Phase 297 must complete before 298 (progressive coverage expansion)

**Legacy Phases**: Phase 220 → Phase 221 → Phase 222 → Phase 223 → Phase 224 → Phase 225 → Phase 226

---

## Coverage Metrics

### Current Baseline (Phase 296 - April 2026)
- **Backend Coverage**: 38.6-39.1% (from 37.1% baseline, +1.5-2.0pp increase)
- **Frontend Coverage**: 18.18% (no change - import issues remain)
- **Backend Scale**: ~90,000 lines (dilutes overall impact)
- **Frontend Scale**: ~26,275 lines
- **Backend Target**: 45% (5.9-6.4pp gap remaining)
- **Frontend Target**: 25% (6.82pp gap remaining)

### Phase 297 Targets
- **Backend Coverage**: 39.8-40.6% (+1.2-1.5pp increase)
- **Files Tested**: 4 high-impact orchestration/analytics services
- **Tests Added**: 160-180 tests
- **Lines Covered**: ~1,490-1,770 lines across 4 files
- **Per-File Coverage**: 25-35% target for each file

### Ultimate Goals
- **Backend Coverage**: 45% (5.9-6.4pp gap from current 38.6-39.1%)
- **Frontend Coverage**: 25% (6.82pp gap from current 18.18%)
- **Quality Gates**: 98%+ test pass rate, CI/CD enforcement

---

## Testing Strategy

### Backend Acceleration (Phases 293-297)
- Test high-impact backend files (25-35% coverage per file)
- Focus on orchestration, analytics, and business logic
- Use AsyncMock for async services, patch at import location
- Follow established patterns from Phase 295-296
- Progressive coverage expansion toward 45% backend target

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
1. **Backend acceleration working**: +1.5-2.0pp increase in Phase 296 (143 new tests)
2. **Individual file improvements significant**: 28% coverage on agent_social_layer.py
3. **Backend scale dilutes impact**: ~90K lines requires ~5,300-5,800 lines for 5.9-6.4pp
4. **Frontend import issue unresolved**: 92.8% of tests blocked by configuration
5. **Patterns established**: AsyncMock, patch at import, fixtures working well

### Risks
1. **Backend scale challenge**: 5.9-6.4pp gap requires ~5,300-5,800 more lines
2. **Frontend structural issue**: Import path blocking 450 tests
3. **Diminishing returns**: Each percentage point requires more effort
4. **Timeline pressure**: Aggressive execution required for 45% target

### Opportunities
1. **Clear strategy**: Test high-impact files with 25-35% coverage targets
2. **Proven patterns**: Phase 295-296 established successful testing patterns
3. **Critical business logic**: Orchestration/analytics services have high value
4. **Alternative paths**: Can shift to quality gates if 45% proves unrealistic

---

*Last Updated: 2026-04-25*
*Next Action: Execute Phase 297 - Backend Acceleration Wave 5*
*Milestone: Backend Coverage Acceleration - Wave 5 (Target: 39.8-40.6%)*
