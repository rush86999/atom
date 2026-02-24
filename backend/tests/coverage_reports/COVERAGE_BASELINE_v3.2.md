# Coverage Baseline v3.2 - Bug Finding & Coverage Expansion

**Baseline Date:** 2026-02-24
**Phase:** 81-04
**Milestone:** v3.2 Bug Finding & Coverage Expansion
**Baseline Established:** Phase 81, Plan 04

## Executive Summary

This document establishes the coverage baseline for the v3.2 milestone "Bug Finding & Coverage Expansion". The baseline represents the starting point from which all progress will be measured through Phase 90 completion.

**Baseline Coverage:** 15.23% overall (3x improvement from v1.0 baseline of 5.13%)

The baseline indicates significant opportunity for coverage expansion across all modules, with core services showing 18.18% coverage and tools at 19.91%.

## Baseline Metrics

| Metric | Value |
|--------|-------|
| **Overall Coverage** | 15.23% |
| **Lines Covered** | 8,272 |
| **Lines Total** | 45,366 |
| **Lines Missing** | 37,094 |
| **Files Analyzed** | 312 |
| **Trend vs v1.0 Baseline** | +10.10% (197% improvement) |
| **Trend vs Peak (Phase 19)** | -6.77% (regression from 22.0%) |

### Historical Context

| Milestone | Phase | Date | Coverage | Lines Covered | Lines Total |
|-----------|-------|------|----------|---------------|-------------|
| **v1.0 Baseline** | 01 | 2026-02-17 | 5.13% | 2,901 | 56,529 |
| **Peak Coverage** | 19 | 2026-02-17 | 22.0% | ~12,439 | ~56,560 |
| **Gap Closure** | 19 | 2026-02-18 | 15.23% | ~8,619 | ~56,560 |
| **Canvas Summaries** | 21 | 2026-02-18 | 21.59% | ~12,210 | ~56,560 |
| **v3.2 Baseline** | 81 | 2026-02-24 | 15.23% | 8,272 | 45,366 |

**Note:** The reduction in total lines (56,529 → 45,366) reflects codebase pruning and restructuring between v1.0 and v3.2. The current baseline represents a more focused, production-ready codebase.

## Module Breakdown

### By Top-Level Directory

| Module | Coverage | Lines Covered | Lines Total | Coverage Gap |
|--------|----------|---------------|-------------|--------------|
| **core** | 18.18% | 7,996 | 43,980 | 81.82% |
| **api** | 0.00% | 0 | 0 | N/A |
| **tools** | 19.91% | 276 | 1,386 | 80.09% |

**Note:** API routes show 0% in current measurement scope. API coverage requires separate test configuration.

### Coverage Distribution

| Range | File Count | Percentage |
|-------|------------|------------|
| **0% Coverage** | 275 | 88% |
| **1-20% Coverage** | 20 | 6% |
| **21-50% Coverage** | 10 | 3% |
| **51-70% Coverage** | 4 | 1% |
| **71-90% Coverage** | 2 | 1% |
| **90%+ Coverage** | 1 | <1% |

### High-Impact Files (>200 lines, <30% coverage)

From Phase 81-02 analysis, **49 high-impact files** identified with **14,511 uncovered lines**:

| Rank | File | Uncovered Lines | Total Lines | Coverage | Priority |
|------|------|-----------------|-------------|----------|----------|
| 1 | workflow_engine.py | 994 | 994 | 0% | P1 |
| 2 | episode_segmentation_service.py | 380 | 422 | 10% | P0 |
| 3 | agent_meta_agent.py | 331 | 331 | 0% | P1 |
| 4 | lancedb_handler.py | 324 | 494 | 34% | P1 |
| 5 | hybrid_data_ingestion.py | 314 | 314 | 0% | P2 |
| 6 | formula_extractor.py | 313 | 313 | 0% | P2 |
| 7 | proposal_service.py | 309 | 339 | 9% | P2 |
| 8 | student_training_service.py | 285 | 285 | 0% | P0 |
| 9 | supervision_service.py | 276 | 276 | 0% | P0 |
| 10 | auto_document_ingestion.py | 274 | 479 | 43% | P2 |

**P0 Tier (Governance & Safety):**
- episode_segmentation_service.py (380 uncovered)
- supervision_service.py (276 uncovered)
- student_training_service.py (285 uncovered)

**Total P0 Opportunity:** 941 uncovered lines across 3 critical files

## Target Coverage (v3.2 Completion)

### Overall Targets

| Metric | Baseline | Target | Gap | Incremental |
|--------|----------|--------|-----|-------------|
| **Overall Coverage** | 15.23% | **25%** | 9.77% | +4,434 lines |
| **Core Services** | 18.18% | **50%** | 31.82% | +13,993 lines |
| **High-Impact Files** | 10% avg | **60% avg** | 50% | ~7,255 lines |
| **P0 Tier Files** | 5% avg | **70% avg** | 65% | ~612 lines |

### File-Level Targets by Priority

| Priority Tier | File Count | Baseline Coverage | Target Coverage | Lines to Add |
|---------------|------------|-------------------|-----------------|--------------|
| **P0 (Critical)** | 3 | 5% avg | 70% | ~612 |
| **P1 (High)** | 14 | 8% avg | 60% | ~3,500 |
| **P2 (Medium)** | 23 | 12% avg | 50% | ~4,600 |
| **P3 (Low)** | 9 | 15% avg | 40% | ~2,200 |
| **TOTAL** | **49** | **10% avg** | **60% avg** | **~10,912** |

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

- [ ] **Overall coverage reaches 25%** (from baseline of 15.23%)
  - Gap: 9.77%
  - Lines to add: 4,434
  - Verification: `python tests/coverage_reports/trend_tracker.py`

- [ ] **High-impact files (>200 lines) reach 60% average coverage**
  - Files affected: 49
  - Current average: 10%
  - Target: ~7,255 lines added
  - Verification: Check coverage.json for file-level metrics

- [ ] **P0 tier files (governance, episodes, LLM) reach 70% coverage**
  - Files: episode_segmentation_service.py, supervision_service.py, student_training_service.py
  - Current average: 5%
  - Target: ~612 lines added
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

All 4 critical business paths currently at **0% coverage** (16/16 steps below 50% threshold):

1. **Agent Execution Path** - 0% (0/4 steps covered)
2. **Episode Creation Path** - 0% (0/4 steps covered)
3. **Canvas Presentation Path** - 0% (0/4 steps covered)
4. **Graduation Promotion Path** - 0% (0/4 steps covered)

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

**Baseline Established:** 2026-02-24
**Baseline Version:** v3.2
**Phase:** 81-04
**Milestone:** Bug Finding & Coverage Expansion

*For the latest coverage data, run: `python backend/tests/coverage_reports/trend_tracker.py`*
