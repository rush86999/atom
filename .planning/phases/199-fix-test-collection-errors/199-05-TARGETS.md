# Phase 199 Plan 05: High-Impact Coverage Targets

**Created:** 2026-03-16
**Purpose:** Data-driven module selection for Wave 3 coverage push to 85%
**Methodology:** Impact Score = (Lines × Coverage Gap) / Estimated Effort

---

## Executive Summary

After analyzing coverage data from Phase 199 baseline, **3 high-impact modules** identified for Wave 3 (Plans 06-08). These modules offer the best ROI for test effort, with expected contribution of **+3-5% overall coverage**.

**Key Finding:** `agent_governance_service.py` has the highest impact score (7.33), making it the top priority for Wave 3. `trigger_interceptor.py` and `agent_graduation_service.py` are medium-priority targets.

---

## Impact Score Methodology

**Formula:**
```
Impact Score = (Lines × Coverage Gap) / Estimated Effort
```

**Where:**
- **Lines** = Total executable lines in module
- **Coverage Gap** = 85% - current_coverage (for modules <85%)
- **Estimated Effort** = Number of tests needed (based on complexity)
  - Simple logic: 1 test per 20 lines
  - Medium complexity: 1 test per 30 lines (governance services)
  - High complexity: 1 test per 40 lines

**Priority Levels:**
- **HIGH** (impact > 5): Best ROI, target for Wave 3
- **MEDIUM** (impact 2-5): Moderate ROI, target for Wave 3-4
- **LOW** (impact < 2): Low ROI, defer to later phases
- **BLOCKED**: Schema/infrastructure issues, unblock first

---

## Module Analysis Results

### Candidate Modules (200+ lines, 40-85% coverage)

| Module | Coverage | Lines | Gap to 85% | Gap Lines | Est. Tests | Impact Score | Priority |
|--------|----------|-------|------------|-----------|------------|--------------|----------|
| `agent_governance_service.py` | 61.9% | 286 | 23.1% | 66 | 9 | **7.33** | **HIGH** |
| `trigger_interceptor.py` | 74.3% | 140 | 10.7% | 14 | 4 | **3.50** | **MEDIUM** |
| `agent_graduation_service.py` | 73.8% | 300 | 11.2% | 33 | 10 | **3.30** | **MEDIUM** |
| `episode_segmentation_service.py` | 83.8% | 300 | 1.2% | 3 | 10 | **0.30** | LOW |
| `student_training_service.py` | 0% | 400 | 85% | BLOCKED | Unknown | **Unknown** | **BLOCKED** |

**Notes:**
- `episode_segmentation_service.py` has LOW impact because it's already at 83.8% (only 1.2% gap)
- `student_training_service.py` is BLOCKED due to schema issues (needs unblocking before testing)

---

## Wave 3 Targets (Plans 06-08)

### Priority 1: agent_governance_service.py

**Current:** 61.9% coverage (177/286 lines)
**Target:** 85% coverage (243/286 lines)
**Gap:** 23.1 percentage points (+66 lines)

**Impact Score:** 7.33 (HIGH)
**Estimated Effort:** 9 tests (medium complexity)
**Expected Contribution:** +1.5-2% overall coverage

**Test Focus Areas:**
1. **Complex governance scenarios** (4-5 tests)
   - Concurrent permission checks
   - Cache invalidation edge cases
   - Multi-agent conflicts

2. **Error paths and edge cases** (3-4 tests)
   - Adjudication logic (currently 0% covered)
   - Agent suspension/termination (0% covered)
   - Agent reactivation (0% covered)

3. **Maturity transitions** (2-3 tests)
   - Confidence score updates (67% → 85%)
   - Promotion to autonomous scenarios

**Uncovered Functions (Priority):**
- `_adjudicate_feedback()`: 0% coverage (22 statements)
- `suspend_agent()`: 0% coverage (18 statements)
- `terminate_agent()`: 0% coverage (17 statements)
- `reactivate_agent()`: 0% coverage (28 statements)

**Plan Assignment:** 199-06

---

### Priority 2: trigger_interceptor.py

**Current:** 74.3% coverage (104/140 lines)
**Target:** 85% coverage (119/140 lines)
**Gap:** 10.7 percentage points (+14 lines)

**Impact Score:** 3.50 (MEDIUM)
**Estimated Effort:** 4 tests (medium complexity)
**Expected Contribution:** +0.5-1% overall coverage

**Test Focus Areas:**
1. **Routing edge cases** (2-3 tests)
   - Route to training (currently 0%)
   - Create proposal workflow (0%)
   - Execute with supervision (0%)

2. **Maturity transitions** (1-2 tests)
   - Trigger priority conflicts
   - Manual trigger edge cases

**Uncovered Functions (Priority):**
- `route_to_training()`: 0% coverage (4 statements)
- `create_proposal()`: 0% coverage (9 statements)
- `execute_with_supervision()`: 0% coverage (9 statements)
- `allow_execution()`: 0% coverage (5 statements)

**Plan Assignment:** 199-07

---

### Priority 3: agent_graduation_service.py

**Current:** 73.8% coverage (221/300 lines)
**Target:** 85% coverage (255/300 lines)
**Gap:** 11.2 percentage points (+33 lines)

**Impact Score:** 3.30 (MEDIUM)
**Estimated Effort:** 10 tests (medium complexity)
**Expected Contribution:** +0.5-1% overall coverage

**Test Focus Areas:**
1. **Graduation exam scenarios** (4-5 tests)
   - All three promotion paths (STUDENT→INTERN→SUPERVISED→AUTONOMOUS)
   - Readiness score edge cases
   - Constitutional compliance failures

2. **Edge case handling** (3-4 tests)
   - Insufficient episodes
   - Nonexistent agent
   - Corrupt data recovery

3. **Integration scenarios** (2-3 tests)
   - Episode linkage
   - Feedback aggregation
   - Training session integration

**Plan Assignment:** 199-08

---

## Wave 4 Targets (Plans 09-10)

### Priority 4: E2E Integration Tests

**Target:** Governance → Execution → Episodic Memory integration
**Tests:** 5-8 tests
**Expected Contribution:** +1-2% overall coverage

**Focus Areas:**
1. Agent execution with episode creation
2. Feedback linking to episodes
3. Canvas context in episodes
4. Multi-maturity agent workflows

**Plan Assignment:** 199-09

---

### Priority 5: Training + Supervision Integration

**Target:** Training → Supervision → Graduation workflow
**Tests:** 4-6 tests
**Expected Contribution:** +0.5-1% overall coverage

**Prerequisites:**
- Unblock `student_training_service.py` (schema fixes)
- Unblock `supervision_service.py` integration tests

**Focus Areas:**
1. Training session lifecycle
2. Supervision intervention workflows
3. Graduation criteria validation

**Plan Assignment:** 199-10

---

## Expected Coverage Contribution

### Wave 3 (Plans 06-08): +3-5% overall

| Plan | Module | Current | Target | Contribution |
|------|--------|---------|--------|--------------|
| 199-06 | agent_governance_service.py | 61.9% | 85% | +1.5-2% |
| 199-07 | trigger_interceptor.py | 74.3% | 85% | +0.5-1% |
| 199-08 | agent_graduation_service.py | 73.8% | 85% | +0.5-1% |
| 199-09 | E2E integration | N/A | N/A | +1-2% |
| 199-10 | Training + Supervision | N/A | N/A | +0.5-1% |

**Total Expected:** +4-7% overall coverage

**Baseline to Target:**
- Phase 199 Baseline: 74.6%
- Wave 3 Target: 78-80%
- Wave 4 Target: 80-82%
- **Phase 199 Final Target: 85%**

---

## Blocked Modules

### student_training_service.py

**Status:** BLOCKED (0% coverage)
**Issue:** Schema drift prevents test collection
**Required Action:** Fix schema issues before coverage push (see 199-RESEARCH.md)

**Impact if Unblocked:**
- 400 lines, 85% gap
- Estimated 15-20 tests
- Potential +0.5-1% overall coverage

**Recommendation:** Address in Wave 4 (Plan 199-10) after Wave 3 high-impact modules

---

## Plan Adjustments Based on Actual Coverage Data

### Original Estimates vs Actual

| Module | Est. Coverage | Actual Coverage | Est. Gap | Actual Gap | Adjustment |
|--------|---------------|-----------------|----------|------------|------------|
| agent_governance_service.py | 50% | 61.9% | 35% | 23.1% | **Reduce scope** (better than expected) |
| trigger_interceptor.py | 60% | 74.3% | 25% | 10.7% | **Reduce scope** (exceeds expectations) |
| agent_graduation_service.py | 70% | 73.8% | 15% | 11.2% | **On track** (matches estimates) |

**Implications:**
- Wave 3 test counts can be reduced (actual coverage better than estimated)
- Focus on quality over quantity (target uncovered functions, not blanket coverage)
- May achieve 85% target faster than planned

---

## Rationale for Target Selection

### Why agent_governance_service.py First?

1. **Highest Impact Score (7.33)**: Best ROI for test effort
2. **Large Gap (23.1%)**: Significant room for improvement
3. **Critical Path**: Core governance functionality used by all agents
4. **Uncovered Functions**: 4 major functions at 0% coverage (adjudication, suspension, termination, reactivation)

### Why trigger_interceptor.py Second?

1. **Medium-High Impact (3.50)**: Good ROI with fewer tests
2. **Small Gap (10.7%)**: Quick win to reach 85%
3. **Routing Logic**: Critical for STUDENT/INTERN agent safety
4. **Uncovered Paths**: 3 major routing functions at 0% coverage

### Why agent_graduation_service.py Third?

1. **Medium Impact (3.30)**: Moderate ROI, requires more tests
2. **Integration-Heavy**: Tests cover episodic memory integration
3. **Business Value**: Graduation framework is key differentiator
4. **Edge Cases**: Graduation exam logic needs comprehensive testing

### Why Defer episode_segmentation_service.py?

1. **Low Impact (0.30)**: Already at 83.8% (only 1.2% gap)
2. **Diminishing Returns**: 10 tests for 3 lines of coverage
3. **Lower Priority**: Other modules offer better ROI
4. **Future Phase**: Can address in Phase 200+ if needed

---

## Success Criteria

### Wave 3 (Plans 06-08)

- [ ] agent_governance_service.py: 61.9% → 85% (+23.1%)
- [ ] trigger_interceptor.py: 74.3% → 85% (+10.7%)
- [ ] agent_graduation_service.py: 73.8% → 85% (+11.2%)
- [ ] Overall coverage: 74.6% → 78-80% (+3-5%)
- [ ] All uncovered functions tested (0% → 85%+)
- [ ] Test pass rate >95%

### Wave 4 (Plans 09-10)

- [ ] E2E integration tests created and passing
- [ ] Training + Supervision integration tested
- [ ] student_training_service.py unblocked
- [ ] Overall coverage: 80-82% (+1-2%)
- [ ] Final push to 85% (Plan 199-11)

---

## Next Steps

1. **Execute Plan 199-06**: agent_governance_service.py coverage push
2. **Execute Plan 199-07**: trigger_interceptor.py coverage push
3. **Execute Plan 199-08**: agent_graduation_service.py coverage push
4. **Verify Wave 3 Results**: Measure actual coverage gains
5. **Adjust Wave 4 Scope**: Based on Wave 3 actual results

**Expected Outcome:** Wave 3 should achieve 78-80% overall coverage, setting up Wave 4 for final push to 85%.

---

*Phase: 199-fix-test-collection-errors*
*Plan: 05 - Identify High-Impact Targets*
*Created: 2026-03-16*
*Next: 199-06 - Agent Governance Service Coverage Push*
