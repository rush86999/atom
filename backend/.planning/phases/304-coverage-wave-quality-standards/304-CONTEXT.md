# Phase 304 Context: Coverage Expansion with Quality Standards

**Phase**: 304 - Coverage Wave: Quality Standards Applied
**Date**: 2026-04-25
**Status**: Planning
**Strategy**: Resume coverage expansion with quality standards from Phase 303

---

## Executive Summary

Phase 304 resumes the coverage expansion journey (26.02% → 45% target) with the critical quality lessons learned from Phase 303. After discovering and fixing 12 stub tests that contributed 0% coverage, Phase 304 applies the 303-QUALITY-STANDARDS.md checklist to ensure all new tests are meaningful and contribute to coverage goals.

**Current Baseline**: 26.02% backend coverage (23,686 of 91,078 lines)
**Target**: 28.0-28.5% backend coverage (+2.0-2.5pp increase)
**Gap to 45%**: 18.98 percentage points (need ~17,283 lines)

---

## Phase 303 Key Outcomes

### Stub Test Problem Eliminated ✅
- **Fixed**: 12 stub tests → 41 proper tests
- **Coverage Increase**: +0.22pp (25.8% → 26.02%)
- **Quality Standards**: 303-QUALITY-STANDARDS.md (580 lines)
- **Pass Rate**: 100% (41/41 tests passing)

### Quality Standards Established ✅
**4 Critical Criteria for Stub Tests**:
1. ❌ No Import of Target Module
2. ❌ Tests Assert on Generic Python Operations (dict, list, eval)
3. ❌ No AsyncMock/Mock Patches of Target Module
4. ❌ 0% Coverage Despite Having Test Code

**Pre-CHECK Task** (NEW for Phase 304+):
- Verify test file imports from target module
- Verify tests assert on production code behavior
- Verify tests use AsyncMock/Mock patterns
- Run pytest to confirm >0% coverage before committing

---

## Top 10 Files Coverage Status (from Phase 299 Gap Analysis)

| Rank | File | Lines | Curr% | ToCover | Phase Status |
|------|------|-------|-------|---------|--------------|
| 1 | workflow_engine.py | 1,219 | 6.8% | 465 | ✅ Phase 300/295 |
| 2 | atom_agent_endpoints.py | 779 | 12.3% | 254 | ✅ Phase 300/295 |
| 3 | agent_world_model.py | 712 | 11.9% | 235 | ✅ Phase 300/295 |
| 4 | byok_handler.py | 760 | 14.6% | 231 | ⚠️ Phase 301 (fixture issues) |
| 5 | episode_segmentation_service.py | 600 | 12.0% | 198 | ⚠️ Phase 301 (fixture issues) |
| 6 | **learning_service_full.py** | 1,228 | 0.0% | 197 | ✅ Has tests (25 tests) |
| 7 | lancedb_handler.py | 694 | 16.7% | 196 | ⚠️ Phase 301 (fixture issues) |
| 8 | atom_meta_agent.py | 594 | 14.0% | 184 | ✅ Phase 297 |
| 9 | **workflow_debugger.py** | 1,387 | 11.8% | 175 | ❌ No tests |
| 10 | **hybrid_data_ingestion.py** | 1,008 | 12.7% | 160 | ❌ No tests |

**Next 3 Untested High-Impact Files**:
1. **workflow_debugger.py** (1,387 lines, 11.8% → 45% target, 175 lines to cover)
2. **hybrid_data_ingestion.py** (1,008 lines, 12.7% → 45% target, 160 lines to cover)
3. **learning_service_full.py** (1,228 lines, 0.0% → 45% target, 197 lines to cover) - HAS TESTS (25 tests)

**Need to identify 3 NEW files for Phase 304** that haven't been tested yet.

---

## Phase 304 Objectives

### Primary Goals
1. Test 3 high-impact files not yet covered (from Tier 2/Tier 3 list)
2. Apply 303-QUALITY-STANDARDS.md PRE-CHECK to all test files
3. Achieve 25-30% coverage on each file
4. Maintain 95%+ pass rate target
5. Expected impact: +2.0-2.5pp backend coverage increase

### Quality Gates
- **PRE-CHECK Task**: Verify no stub tests before implementation
- **Import Check**: All tests must import from target module
- **Coverage Check**: Run pytest --cov to confirm >0% coverage
- **Pass Rate Check**: 95%+ tests passing before completion

### File Selection Criteria
- From Phase 299 Tier 2/Tier 3 lists
- >400 lines (high-impact threshold)
- <20% current coverage (significant gap)
- NOT tested in Phases 295-303
- High business value (orchestration, services, core logic)

---

## Historical Context

### Phase 299: Coverage Verification (COMPLETE)
- **Actual Backend Coverage**: 25.8% (23,498 of 91,078 lines)
- **Gap to 45% Target**: 19.2 percentage points
- **Roadmap Created**: 7 phases (300-306) to reach 45%

### Phase 300: Orchestration Wave 1 (COMPLETE)
- **Files**: workflow_engine.py, atom_agent_endpoints.py, agent_world_model.py
- **Tests**: 106 existed vs 38 planned
- **Pass Rate**: 54% (57/106 passing, 49 failures)
- **Issue**: Legacy test failures from Phase 295

### Phase 301: Services Wave 1 (COMPLETE with deviation)
- **Files**: byok_handler.py, lancedb_handler.py, episode_segmentation_service.py
- **Tests**: 54 existed vs 35-45 planned
- **Pass Rate**: 10% (5.4/54 passing, 48.6 failures)
- **Issue**: Fixture issues, missing db argument

### Phase 302: Services Wave 2 (COMPLETE with critical deviation)
- **Files**: advanced_workflow_system.py, workflow_versioning_system.py, graphrag_engine.py
- **Tests**: 52 existed (6 + 6 + 40)
- **CRITICAL DISCOVERY**: 12 of 52 tests (23%) were stub tests
- **Coverage Impact**: 0pp increase (stub tests contribute 0%)

### Phase 303: Quality-Focused Stub Test Fixes (COMPLETE)
- **Plans**: 303-01 (advanced_workflow_system), 303-02 (workflow_versioning_system), 303-03 (audit + standards)
- **Stub Tests Fixed**: 12 → 0 (-100%)
- **Proper Tests Added**: 41 tests
- **Coverage Increase**: +0.22pp (25.8% → 26.02%)
- **Quality Standards**: 303-QUALITY-STANDARDS.md (580 lines)
- **Audit Report**: 303-AUDIT-REPORT.md (comprehensive review of 8 files)

---

## Quality Standards Reference

### From 303-QUALITY-STANDARDS.md

**Section 1: Stub Test Detection Checklist**
- 4 Critical Criteria for Stub Tests
- Auto-Detection Script
- Manual Review Checklist

**Section 2: Phase 297-298 AsyncMock Patterns**
- Proper Import Pattern
- AsyncMock for Database Operations
- AsyncMock for LLM Calls
- Mock for External APIs

**Section 3: Pre-CHECK Task (NEW)**
Before committing any test file:
1. Verify imports from target module
2. Verify tests assert on production code behavior
3. Verify tests use AsyncMock/Mock patterns
4. Run pytest --cov to confirm >0% coverage

**Section 4: Common Pitfalls**
- Testing dict operations instead of model validation
- Missing AsyncMock on database sessions
- Patching wrong import path
- Forgetting to await async functions

---

## Success Criteria for Phase 304

1. ✅ 3 high-impact files tested (25-30% coverage each)
2. ✅ All test files pass PRE-CHECK (no stub tests)
3. ✅ 95%+ pass rate achieved on all tests
4. ✅ Backend coverage increases by +2.0-2.5pp (26.02% → 28.0-28.5%)
5. ✅ Quality standards documented in plan summaries
6. ✅ All deviations documented with rationale

---

## Next Steps

1. Create 3 plans (304-01, 304-02, 304-03) for 3 high-impact files
2. Include PRE-CHECK task in each plan (before implementation)
3. Apply 303-QUALITY-STANDARDS.md to all test files
4. Execute plans sequentially with quality verification
5. Create Phase 304 completion summary

---

*Context created: 2026-04-25*
*Next: Create PLAN.md files for Phase 304*
