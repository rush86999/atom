# Coverage Gap Dashboard v5.0

**Phase:** 100 (Coverage Analysis)
**Generated:** 2026-02-27 16:34:58 UTC
**Purpose:** Unified view of coverage gaps, prioritization, and trends for Phases 101-110

---

## Executive Summary

**Generated:** 2026-02-27 16:34:58 UTC

### Current Coverage State

| Metric | Value | Target | Gap |
|--------|-------|--------|-----|
| **Overall Coverage** | **21.67%** | 80% | 58.3% |
| Core Module | 24.28% | 80% | 55.72% |
| API Module | 36.38% | 80% | 43.62% |
| Tools Module | 12.93% | 80% | 67.07% |

### Files Below 80% Threshold

- **Total files:** 50 files below 80% coverage (top 50 shown)
- **Uncovered lines:** 50,865 lines
- **Priority files:** Top 50 files account for 15,385 uncovered lines

### Gap Analysis

The codebase currently has **58.3%** overall coverage gap to reach the 80% target.

**Quick Wins:** 50 files have 0% coverage and are prime candidates for rapid improvement.

---

## Impact Breakdown

### Files by Business Impact Tier

| Tier | Score | Files | Uncovered Lines |
|------|-------|-------|-----------------|
| **Critical** | 10 | 30 | 4,868 |
| **High** | 7 | 25 | 2,874 |
| **Medium** | 5 | 435 | 42,376 |
| **Low** | 3 | 13 | 747 |

### Top 5 Files by Priority Score

Priority formula: `(uncovered_lines × impact_score) / (coverage_pct + 1)`

| Rank | File | Coverage | Uncovered | Tier | Priority Score |
|------|------|----------|-----------|------|----------------|
| 1 | `core/enterprise_user_management.py` | 0.0% | 213 | Medium | 1,065 |
| 2 | `api/smarthome_routes.py` | 0.0% | 205 | Medium | 1,025 |
| 3 | `core/workflow_engine.py` | 4.8% | 1,089 | Medium | 942 |
| 4 | `tools/canvas_tool.py` | 3.8% | 385 | Critical | 802 |
| 5 | `core/llm/byok_handler.py` | 8.7% | 582 | Critical | 599 |

---

## Prioritized Files

### Top 20 Files for Phase 101 (Backend Core Services)

| Rank | File | Coverage | Uncovered | Tier | Priority |
|------|------|----------|-----------|------|----------|
| 1 | `core/enterprise_user_management.py` | 0.0% | 213 | Medium | 1,065 |
| 2 | `api/smarthome_routes.py` | 0.0% | 205 | Medium | 1,025 |
| 3 | `core/workflow_engine.py` | 4.8% | 1,089 | Medium | 942 |
| 4 | `tools/canvas_tool.py` | 3.8% | 385 | Critical | 802 |
| 5 | `core/llm/byok_handler.py` | 8.7% | 582 | Critical | 599 |
| 6 | `core/episode_segmentation_service.py` | 8.2% | 510 | Critical | 551 |
| 7 | `core/proposal_service.py` | 7.6% | 309 | Critical | 358 |
| 8 | `core/atom_agent_endpoints.py` | 9.1% | 680 | Medium | 338 |
| 9 | `core/skill_registry_service.py` | 7.2% | 331 | High | 283 |
| 10 | `core/episode_retrieval_service.py` | 9.0% | 271 | Critical | 270 |
| 11 | `core/agent_integration_gateway.py` | 4.5% | 273 | Medium | 247 |
| 12 | `core/lancedb_handler.py` | 11.5% | 609 | Medium | 243 |
| 13 | `tools/browser_tool.py` | 9.9% | 261 | Critical | 239 |
| 14 | `api/media_routes.py` | 4.0% | 220 | Medium | 220 |
| 15 | `core/workflow_debugger.py` | 9.7% | 465 | Medium | 218 |
| 16 | `core/agent_social_layer.py` | 7.3% | 338 | Medium | 203 |
| 17 | `core/agent_graduation_service.py` | 9.4% | 203 | Critical | 194 |
| 18 | `core/formula_extractor.py` | 7.0% | 281 | Medium | 175 |
| 19 | `tools/device_tool.py` | 9.7% | 244 | High | 159 |
| 20 | `core/auto_invoicer.py` | 6.3% | 204 | Medium | 140 |

### Quick Wins (0% Coverage, High Impact)

**0 files** with 0% coverage in Critical/High tiers:



### Phase 101 Recommendations

**Focus:** Backend Core Services Unit Tests

**Priority Files:**
- Top 20 files from prioritized list
- Estimated uncovered lines: 7,673
- Target coverage gain: +10-15 percentage points

**Strategy:**
1. Start with 0% coverage files (quick wins)
2. Focus on Critical tier (security, data access, agent governance)
3. Write unit tests for core business logic
4. Use property tests for state machines and data transformations

---

## Coverage Trend

### Current Status

| Metric | Value |
|--------|-------|
| **Current Coverage** | **21.67** |
| **Baseline** | 21.67 |
| **Delta** | N/A |
| **Target** | 80% |
| **Snapshots Tracked** | 5 |

### Trend Visualization

```
Coverage Trend (last 10 snapshots)
==================================================
2026-02-27 |  21.7% ██████████
2026-02-27 |  21.7% ██████████
2026-02-27 |  21.7% ██████████
2026-02-27 |  21.7% ██████████
2026-02-27 |  21.7% ██████████
==================================================
```

---

## Next Steps

### Phase 101: Backend Core Services

**Objective:** Unit tests for top 20 high-impact backend files

**Priority Files:** 12

**Estimated Coverage Gain:** +10-15 percentage points

**Test Types:**
- Unit tests for business logic
- Property tests for state machines
- Error path testing for critical failures

### Phase 102: Backend API Integration

**Objective:** API endpoint integration tests

**Priority Files:** 4

**Estimated Coverage Gain:** +5-8 percentage points

### Phase 103: Property-Based Testing

**Objective:** Property tests for state transformations

**Priority Files:** 12

**Focus Areas:**
- Workflow engine state transitions
- Agent governance state machines
- Data transformation functions

### Phase 104: Error Path Testing

**Objective:** Error handling and edge cases

**Priority Files:** 1

**Focus Areas:**
- Exception handling paths
- Boundary conditions
- Invalid input scenarios

### Phases 105-109: Frontend Coverage Expansion

**Focus:** Frontend component tests (React, Tauri)

**Current Frontend Coverage:** 3.45% (from baseline report)

**Estimated Coverage Gain:** +20-25 percentage points

### Phase 110: Quality Gates & Reporting

**Objective:** Enforce 80% coverage threshold in CI

**Deliverables:**
- Coverage quality gate in CI pipeline
- Regression detection alerts
- Automated coverage trend reporting

---

## Summary

**Phase 100 establishes the foundation for v5.0 Coverage Expansion:**

1. ✅ **Baseline Coverage:** 21.67% overall, 50 files below 80%
2. ✅ **Business Impact Scoring:** 4-tier system (Critical/High/Medium/Low) for prioritization
3. ✅ **File Prioritization:** Top 50 files ranked by (uncovered × impact / coverage)
4. ✅ **Trend Tracking:** Baseline established, history tracking operational

**Next:** Proceed to Phase 101 (Backend Core Services Unit Tests) using prioritized file list.

---

*Dashboard generated by Phase 100 Plan 05*
*See: .planning/phases/100-coverage-analysis/100-VERIFICATION.md for full verification*
