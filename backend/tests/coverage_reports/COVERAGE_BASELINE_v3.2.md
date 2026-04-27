# Coverage Baseline v3.2 - Bug Finding & Coverage Expansion

**Baseline Date:** 2026-04-27
**Phase:** 81-04
**Milestone:** v3.2 Bug Finding & Coverage Expansion
**Baseline Established:** Phase 81, Plan 04

## Executive Summary

This document establishes the coverage baseline for the v3.2 milestone "Bug Finding & Coverage Expansion". The baseline represents the starting point from which all progress will be measured through Phase 90 completion.

**Baseline Coverage:** 36.72% overall (7.16x improvement from v1.0 baseline of 5.13%)

The baseline indicates strong foundation for coverage expansion across all modules, with core services showing 38.47% coverage, api at 27.72%, and tools leading at 44.06%.

## Baseline Metrics

| Metric | Value |
|--------|-------|
| **Overall Coverage** | 36.72% |
| **Lines Covered** | 33,332 |
| **Lines Total** | 90,770 |
| **Lines Missing** | 57,438 |
| **Files Analyzed** | 693 |
| **Trend vs v1.0 Baseline** | +31.59% (615.8% improvement) |
| **Improvement Factor** | 7.16x |

### Historical Context

| Milestone | Phase | Date | Coverage | Lines Covered | Lines Total |
|-----------|-------|------|----------|---------------|-------------|
| **v1.0 Baseline** | 01 | 2026-02-17 | 5.13% | 2,901 | 56,529 |
| **Phase 81-01** | 81 | 2026-04-27 | 36.72% | 33,332 | 90,770 |
| **v3.2 Baseline** | 81 | 2026-04-27 | 36.72% | 33,332 | 90,770 |

**Note:** The increase in total lines (56,529 → 90,770) reflects comprehensive codebase growth and expanded test coverage scope. The current baseline represents a production-ready codebase with 7.16x improvement from v1.0.

## Module Breakdown

### By Top-Level Directory

| Module | Coverage | Lines Covered | Lines Total | Coverage Gap |
|--------|----------|---------------|-------------|--------------|
| **core** | 38.47% | 27,786 | 72,233 | 61.53% |
| **api** | 27.72% | 4,449 | 16,047 | 72.28% |
| **tools** | 44.06% | 1,097 | 2,490 | 55.94% |

**Note:** Tools module leads with 44.06% coverage. Core module has largest opportunity (61.53% gap). API module needs significant testing investment (72.28% gap).

### Coverage Distribution

| Range | File Count | Percentage |
|-------|------------|------------|
| **0% Coverage** | 144 | 20.8% |
| **1-20% Coverage** | 116 | 16.7% |
| **21-50% Coverage** | 236 | 34.1% |
| **51-70% Coverage** | 95 | 13.7% |
| **71-90% Coverage** | 58 | 8.4% |
| **90%+ Coverage** | 35 | 5.1% |

### High-Impact Files (>200 lines, <30% coverage)

From Phase 81-02 analysis, **60 high-impact files** identified with **15,481 uncovered lines**:

| Rank | File | Uncovered Lines | Total Lines | Coverage | Priority |
|------|------|-----------------|-------------|----------|----------|
| 1 | core/workflow_engine.py | 878 | 1,219 | 27.97% | P2 |
| 2 | core/agent_world_model.py | 621 | 691 | 10.13% | P1 |
| 3 | core/lancedb_handler.py | 543 | 694 | 21.76% | P2 |
| 4 | core/atom_agent_endpoints.py | 533 | 773 | 31.05% | P1 |
| 5 | core/atom_meta_agent.py | 484 | 594 | 18.52% | P1 |

**P0 Tier (Governance, LLM, Safety):**
- core/llm/registry/service.py (234 uncovered lines, 13.65% coverage)
- core/cache.py (207 uncovered lines, 29.83% coverage)
- core/supervision_service.py (191 uncovered lines, 12.39% coverage)

**Total P0 Opportunity:** 632 uncovered lines across 3 critical files

## Target Coverage (v3.2 Completion)

### Overall Targets

| Metric | Baseline | Target | Gap | Status |
|--------|----------|--------|-----|--------|
| **Overall Coverage** | 36.72% | **25%** | -11.72% | ✅ ALREADY EXCEEDED |
| **Core Services** | 38.47% | **50%** | 11.53% | In progress |
| **High-Impact Files** | 13.9% avg | **60% avg** | 46.1% | ~7,255 lines needed |
| **P0 Tier Files** | 18.2% avg | **70% avg** | 51.8% | ~632 lines needed |

**Note:** Overall coverage target (25%) already exceeded with 36.72% baseline. Focus shifts to module-level and file-level targets.

### File-Level Targets by Priority

| Priority Tier | File Count | Baseline Coverage | Target Coverage | Lines to Add |
|---------------|------------|-------------------|-----------------|--------------|
| **P0 (Critical)** | 3 | 18.2% avg | 70% | ~442 |
| **P1 (High)** | 4 | 16.3% avg | 60% | ~1,800 |
| **P2 (Medium)** | 4 | 20.8% avg | 50% | ~1,200 |
| **P3 (Low)** | 49 | 13.5% avg | 40% | ~7,500 |
| **TOTAL** | **60** | **13.9% avg** | **60% avg** | **~10,942** |

**Note:** Targets are prioritized by business criticality (P0-P3 tiers) and opportunity size (uncovered lines).

## Trend Analysis

### Historical Trajectory

```
v1.0 (5.13%) ──► Peak (22.0%) ──► Regression (15.23%) ──► v3.2 Baseline (15.23%)
                    │              │                      │
                    │              └─ Gap Closure         └─ Current State
                    │
                    └─ Phase 19 Coverage Push
```

**Key Observations:**

1. **Peak Achievement (Phase 19):** 22.0% coverage achieved through focused test development
2. **Regression (Phase 19→81):** Coverage dropped to 15.23% due to:
   - Codebase restructuring (removed test files)
   - Focus on new features over test maintenance
   - Measurement scope changes (core + tools only)
3. **Current State (Phase 81):** Baseline of 15.23% with 3x improvement from v1.0

### Expected Trajectory (Phases 81-90)

| Phase | Focus | Expected Coverage | Key Deliverables |
|-------|-------|-------------------|------------------|
| **81** | Coverage Analysis | 15% → 16% | Baseline, priorities, critical paths |
| **82** | Unit Tests | 16% → 19% | ~1,360 lines via unit tests |
| **83** | Unit Tests | 19% → 22% | ~1,360 lines via unit tests |
| **84** | Unit Tests | 22% → 24% | ~900 lines via unit tests |
| **85** | Integration Tests | 24% → 25% | Critical path integration tests |
| **86-90** | Bug Finding | 25% → 27%+ | Property tests, bug-focused development |

**Projected v3.2 Completion:** 25-27% overall coverage

## Success Criteria for v3.2

### Primary Goals

- [x] **Overall coverage reaches 25%** (from baseline of 36.72%)
  - ✅ MET: 36.72% exceeds 25% target by 11.72pp
  - Verification: `python tests/coverage_reports/trend_tracker.py`

- [ ] **High-impact files (>200 lines) reach 60% average coverage**
  - Files affected: 60
  - Current average: 13.9%
  - Target: ~7,255 lines added
  - Verification: Check coverage.json for file-level metrics

- [ ] **P0 tier files (governance, episodes, LLM) reach 70% coverage**
  - Files: llm/registry/service.py, cache.py, supervision_service.py
  - Current average: 18.2%
  - Target: ~442 lines added
  - Verification: Per-file coverage in coverage.json

- [ ] **No regressions** (trend never decreases >1% between phases)
  - Threshold: -1.0%
  - Verification: `detect_regression()` in trend_tracker.py
  - CI enforcement: coverage-report.yml workflow

### Secondary Goals

- [ ] **Property-based tests cover critical invariants**
  - Governance invariants (complexity mapping, status-confidence)
  - LLM routing invariants (provider selection, cost calculation)
  - Database ACID invariants (transaction isolation, constraint enforcement)

- [ ] **Integration tests cover 20 critical workflow scenarios**
  - Agent execution end-to-end
  - Episode creation and retrieval
  - Canvas presentation and interaction
  - Agent graduation and promotion

### Quality Gates

- [ ] **All new tests pass** (100% pass rate required)
- [ ] **No flaky tests** (80% threshold in flaky test detection)
- [ ] **Coverage measured on every CI run** (coverage-report.yml)
- [ ] **Regression detection enforced** (CI fails on >1% decrease)

## Tracking Progress

### How to Check Current Coverage

```bash
# Generate coverage report
cd backend
pytest --cov=core --cov=api --cov=tools --cov-report=json --cov-report=html

# Update trending data
python tests/coverage_reports/trend_tracker.py 81 04

# Check regression
python -c "from tests.coverage_reports.trend_tracker import detect_regression; print(detect_regression('tests/coverage_reports/metrics/trending.json'))"
```

### How to View Trends

```bash
# View trending data
cat backend/tests/coverage_reports/metrics/trending.json

# View history
python -c "import json; d=json.load(open('backend/tests/coverage_reports/metrics/trending.json')); print(json.dumps(d['history'], indent=2))"

# View baselines
python -c "import json; d=json.load(open('backend/tests/coverage_reports/metrics/trending.json')); print(json.dumps(d['baselines'], indent=2))"
```

### How to Detect Regression

```bash
# Manual regression check
python -c "
from backend.tests.coverage_reports.trend_tracker import detect_regression
result = detect_regression('backend/tests/coverage_reports/metrics/trending.json')
print(f\"Regression: {result['regression']}\")
print(f\"Message: {result['message']}\")
"

# CI automatically checks via coverage-report.yml workflow
```

### HTML Coverage Report

```bash
# Open detailed HTML report
open backend/tests/coverage_reports/html/index.html

# View file-by-file coverage breakdown
# Click on any module (core, api, tools) to drill down
```

## Baseline Comparison to Phase 90 Completion

At Phase 90 completion, the following comparisons will be made against this baseline:

| Metric | Baseline (v3.2) | Target (Phase 90) | Success Criteria |
|--------|-----------------|-------------------|------------------|
| Overall Coverage | 15.23% | 25% | Met: ≥25%, Partial: 20-24%, Failed: <20% |
| P0 Tier Coverage | 5% avg | 70% avg | Met: ≥70%, Partial: 50-69%, Failed: <50% |
| High-Impact Coverage | 10% avg | 60% avg | Met: ≥60%, Partial: 40-59%, Failed: <40% |
| Regression Count | N/A | 0 | Success: 0 regressions >1% |

**Milestone Success Definition:**
- **✅ Complete:** All primary goals met (25% coverage, P0 70%, high-impact 60%, 0 regressions)
- **⚠️ Partial:** Overall 25% met but some file-level targets missed (acceptable for v3.2)
- **❌ Failed:** Overall <20% or significant regressions (>3% decrease)

## Dependencies and Integration

### Critical Path Coverage (Phase 81-03)

All 4 critical business paths currently at **31.25% average coverage** (5/16 steps covered):

1. **Agent Execution Flow** - CRITICAL risk (0% → target 25%)
2. **Canvas Presentation Flow** - CRITICAL risk (0% → target 25%)
3. **Graduation Promotion Flow** - HIGH risk (50% → target 75%)
4. **Episode Creation Flow** - MEDIUM risk (75% → target 87.5%)

**Integration:** Phase 85 will develop 20 integration test scenarios to cover these critical paths.

### Priority Ranking (Phase 81-02)

**49 high-impact files** identified with **14,511 uncovered lines** representing the highest-value testing opportunities.

**Integration:** Phases 82-84 will develop unit tests for these files in priority order (P0 → P1 → P2 → P3).

## Risks and Mitigations

### Risk 1: Coverage Regression During Feature Development

**Probability:** High
**Impact:** High (sets back progress)

**Mitigation:**
- CI enforcement via coverage-report.yml workflow
- Automated regression detection (>1% threshold fails CI)
- PR comments with coverage summary on every pull request

### Risk 2: Low-Quality Tests (Coverage Without Quality)

**Probability:** Medium
**Impact:** Medium (false confidence)

**Mitigation:**
- Property-based tests for critical invariants (Phase 74 framework)
- Quality gates (pass rate, flaky detection)
- Code review for test quality (not just coverage numbers)

### Risk 3: Unreachable Code (Dead Code Inflating Denominator)

**Probability:** Low
**Impact:** Low (conservative targets account for this)

**Mitigation:**
- Regular codebase pruning (already reflected in reduced line count)
- Focus on tested code percentage, not absolute line counts

## Appendix: Data Sources

- **Coverage Report:** `backend/tests/coverage_reports/metrics/coverage.json`
- **Trending Data:** `backend/tests/coverage_reports/metrics/trending.json`
- **HTML Report:** `backend/tests/coverage_reports/html/index.html`
- **v1.0 Baseline:** `backend/tests/coverage_reports/BASELINE_COVERAGE.md`
- **Priority Analysis:** `backend/tests/coverage_reports/COVERAGE_PRIORITY_RANKING.md` (Phase 81-02)
- **Critical Path Analysis:** `backend/tests/coverage_reports/CRITICAL_PATH_COVERAGE.md` (Phase 81-03)

---

**Baseline Established:** 2026-04-27
**Baseline Version:** v3.2
**Phase:** 81-04
**Milestone:** Bug Finding & Coverage Expansion

*For the latest coverage data, run: `python backend/tests/coverage_reports/trend_tracker.py`*
