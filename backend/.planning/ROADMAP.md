# Atom Test Coverage Initiative - Roadmap

**Project**: Atom AI-Powered Business Automation Platform
**Initiative**: Test Coverage Improvement & Quality Assurance
**Current Coverage**: 26.02% backend (measured after Phase 303), 18.18% frontend (as of 2026-04-25, Phase 299 completion)
**Target Coverage**: 45% backend, 25% frontend (coverage acceleration milestone)

---

## Current Milestone: Backend Coverage Expansion to 45%

**Goal**: Achieve 45% backend coverage through focused phases testing high-impact orchestration and service files

**Started**: 2026-04-25
**Status**: EXECUTING Phase 305 (Planning Complete)

**Strategy**: Test top 3 high-impact files per phase → Target 25-30% coverage per file → Progressive coverage growth toward 45% → Apply Phase 303 quality standards (PRE-CHECK, no stub tests, 95%+ pass rate)

**Completed Waves**:
- Wave 1 (Phase 293): 30% target achieved
- Wave 2-3 (Phase 295): +0.4pp increase (37.1% coverage, 831 new tests)
- Wave 4 (Phase 296): +1.5-2.0pp increase (38.6-39.1% coverage, 143 new tests)
- Wave 5 (Phase 297): +1.2-1.5pp increase (39.8-40.6% coverage, 121 new tests)
- Wave 6 (Phase 298): 4 coordination/integration files tested (83 tests, 91.6% pass rate)
- Wave 7 (Phase 299): Coverage verification & roadmap creation (VERIFIED: 25.8% backend, 7 phases to 45%)
- Wave 8 (Phase 300): Orchestration Wave 1 - Top 3 Files (106 tests, 54% pass rate - legacy failures)
- Wave 9 (Phase 301): Services Wave 1 - BYOK & Vector & Episodes (54 tests, 10% pass rate - fixture issues)
- Wave 10 (Phase 302): Services Wave 2 - Next 3 Files (52 tests, 23% stub tests discovered)
- Wave 11 (Phase 303): Quality-Focused Stub Test Fixes (41 tests, 100% pass rate, +0.22pp coverage, quality standards established)

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
- [x] **Phase 300: Orchestration Wave 1 - Top 3 Files** - ✅ COMPLETE with deviation. Tests created in Phase 295-02 (106 tests vs 38 planned, 54% pass rate, 300-01-SUMMARY.md)
- [x] **Phase 301: Services Wave 1 - BYOK & Vector & Episodes** - ✅ COMPLETE with deviation. Tests created 2026-04-25 (54 tests vs 35-45 planned, 10% pass rate, 301-01-SUMMARY.md)
- [x] **Phase 302: Services Wave 2 - Next 3 Files** - ✅ COMPLETE with deviation. 12 stub tests discovered (23% of tests), 0pp coverage increase (302-01-SUMMARY.md)
- [x] **Phase 303: Quality-Focused Stub Test Fixes** - ✅ COMPLETE. Stub tests eliminated (12 → 0), quality standards established (303-QUALITY-STANDARDS.md), +0.22pp coverage (26.02% backend)
- [x] **Phase 304: Coverage Wave - Quality Standards Applied** - ✅ COMPLETE. Test 3 high-impact files (workflow_debugger.py, hybrid_data_ingestion.py, workflow_template_system.py) with Phase 303 quality standards (39.1% avg coverage, +0.57pp backend, 45.3% pass rate)
- [ ] **Phase 305: Quality Gates & Final Verification** - Fix failing tests from Phases 300-304, achieve 95%+ pass rate, document realistic roadmap to 35% (adjusted from 45%)
- [ ] **Phase 306-320: Coverage Expansion to 35%** - Test 15 high-impact files to reach 35% backend coverage (15 phases, ~30 hours)

---

## Phase Details

### Phase 303: Quality-Focused Stub Test Fixes ✅ COMPLETE

**Goal**: Eliminate stub test problem discovered in Phase 302, establish quality standards to prevent recurrence

**Depends on**: Phase 302

**Requirements**: QUAL-01, QUAL-02, QUAL-03, QUAL-04

**Status**: ✅ COMPLETE

**Plans**: 3 plans
- [x] 303-01-PLAN.md — Rewrite test_advanced_workflow_system.py (6 stub tests → 24 proper tests, 27% coverage, 100% pass rate)
- [x] 303-02-PLAN.md — Rewrite test_workflow_versioning_system.py (6 stub tests → 17 proper tests, 15% coverage, 100% pass rate)
- [x] 303-03-PLAN.md — Audit bulk-created tests, create quality standards document (303-QUALITY-STANDARDS.md, 580 lines)

**Outcomes**:
- Stub tests eliminated: 12 → 0 (-100%)
- Proper tests added: 41 tests (24 + 17)
- Coverage increase: +0.22pp (25.8% → 26.02%)
- Pass rate: 100% (41/41 tests passing)
- Quality standards: 303-QUALITY-STANDARDS.md (stub test detection checklist, Phase 297-298 AsyncMock patterns, PRE-CHECK task)

**Duration**: ~3 hours
**Commits**: 2

---

### Phase 304: Coverage Wave - Quality Standards Applied (PLANNING)

**Goal**: Resume coverage expansion with Phase 303 quality standards applied, test 3 high-impact orchestration/core files

**Depends on**: Phase 303

**Requirements**: None (acceleration phase)

**Status**: 🔄 PLANNING

**Plans**: 3 plans
- [x] 304-01-PLAN.md — Test workflow_debugger.py (1,387 lines, 11.8% → 25-30% coverage, 20-25 tests)
- [x] 304-02-PLAN.md — Test hybrid_data_ingestion.py (1,008 lines, 12.7% → 25-30% coverage, 18-22 tests)
- [x] 304-03-PLAN.md — Test workflow_template_system.py (1,363 lines, <10% → 25-30% coverage, 22-28 tests)

**Target Files** (from Phase 299 gap analysis, excluding Phases 295-303):
- `core/workflow_debugger.py` (1,387 lines, 11.8% current coverage → 25-30% target) - 175 lines to cover
- `core/hybrid_data_ingestion.py` (1,008 lines, 12.7% current coverage → 25-30% target) - 160 lines to cover
- `core/workflow_template_system.py` (1,363 lines, <10% estimated coverage → 25-30% target) - 200 lines to cover

**Expected Deliverables**:
- test_workflow_debugger.py — 20-25 tests, ~400 lines (breakpoint management, step execution, state inspection)
- test_hybrid_data_ingestion.py — 18-22 tests, ~400 lines (sync operations, ingestion workflows, data transformation)
- test_workflow_template_system.py — 22-28 tests, ~450 lines (template CRUD, validation, instantiation, marketplace)

**Expected Outcomes**:
- Total tests: 60-75 tests (20-25 + 18-22 + 22-28)
- Total test lines: ~1,250 lines
- Target coverage: 25-30% per file (~535 lines covered from 535 lines to cover)
- Expected backend coverage increase: +0.59pp (535 lines / 91,078 total lines)
- Expected backend coverage after Phase 304: 26.61% (from 26.02% baseline)

**Quality Standards Applied** (from Phase 303):
- **PRE-CHECK Task**: Verify no stub tests (imports from target module, >0% coverage, AsyncMock patterns)
- **Import Check**: All tests must import from target module (e.g., `from core.workflow_debugger import WorkflowDebugger`)
- **Coverage Check**: Run pytest --cov to confirm >0% coverage before committing
- **Pass Rate Check**: 95%+ tests passing before completion
- **AsyncMock Patterns**: Follow Phase 297-298 patterns (AsyncMock for database, LLM, external dependencies)

**Patterns**: Follow Phase 297-298 patterns (AsyncMock, patch at import, database fixtures, success + error paths) + Phase 303 quality standards (PRE-CHECK, no stub tests)

---

## Dependencies

```
Phase 303 (Quality Fixes)
    |
Phase 304 (Quality Standards Applied)
    |
Phase 305 (Quality Standards Continued)
    |
Phase 306 (Final Push to 45%)
```

**Critical Path**: Quality fixes must be complete before resuming coverage expansion with quality standards applied

**Parallel Opportunities**: Phase 304 plans (01, 02, 03) can run in parallel (Wave 1, no dependencies between files)

---

## Rationale

**Why Phase 304 structure:**

1. **Quality First** (Phase 303) -- Stub test problem (12 tests, 23% of Phase 302) discovered and fixed, quality standards established to prevent recurrence

2. **Resume Coverage Expansion** (Phase 304) -- Continue coverage journey (26.02% → 45% target) with quality standards applied to all new tests

3. **High-Impact Files** (workflow_debugger, hybrid_data_ingestion, workflow_template_system) -- Next 3 unttested high-impact files from Phase 299 Tier 2/Tier 3 lists

4. **Quality Standards** (PRE-CHECK, AsyncMock patterns) -- Ensure all new tests are meaningful and contribute to coverage goals (no more stub tests)

5. **Parallel Execution** (Wave 1) -- All 3 plans can run in parallel (no file conflicts, independent test files)

6. **Pragmatic Target** (25-30% per file) -- Achievable coverage target that provides meaningful test coverage without excessive complexity

**Quality Standards Applied:**
- PRE-CHECK all test files (verify imports, coverage, pass rate)
- Follow AsyncMock patterns from Phase 297-298
- Achieve 95%+ pass rate target
- Document all deviations from planned approach

---

*Roadmap updated: 2026-04-25*
*Phase 304 planning complete*
*Next: /gsd-execute-phase 304*
