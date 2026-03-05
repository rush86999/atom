---
phase: 127-backend-final-gap-closure
plan: 02
subsystem: backend-coverage
tags: [test-planning, gap-analysis, coverage-targeting, test-efficiency]

# Dependency graph
requires:
  - phase: 127-backend-final-gap-closure
    plan: 01
    provides: baseline coverage and gap analysis
provides:
  - Detailed test plan with file-to-test mapping
  - Estimated coverage gain per test for efficient targeting
  - Test distribution across implementation plans (127-04 through 127-06)
affects: [backend-coverage, test-strategy, gap-closure-planning]

# Tech tracking
tech-stack:
  added: [test plan generation script, coverage estimation algorithm]
  patterns: ["test efficiency factors by file type", "coverage gain estimation"]

key-files:
  created:
    - backend/tests/scripts/generate_test_plan.py
    - backend/tests/coverage_reports/metrics/phase_127_test_plan.json (gitignored)
  modified:
    - None (new planning artifacts)

key-decisions:
  - "Test efficiency factors vary by file type: models (0.5), workflows (0.6), endpoints (0.4), services (0.55)"
  - "Aggressive test targeting: ALL high/medium impact files, top 15 low impact files"
  - "Tests per file calculated as min(pattern_tests * 2, max(5, missing_lines / 50))"
  - "Coverage projection: baseline + (total_estimated_gain / total_missing_lines * 100)"

patterns-established:
  - "Pattern: File-to-test mapping enables efficient coverage gain targeting"
  - "Pattern: Test type selection based on file characteristics (unit/property/integration)"

# Metrics
duration: 2min
completed: 2026-03-03
---

# Phase 127: Backend Final Gap Closure - Plan 02 Summary

**Detailed test plan generation with file-to-test mapping and coverage gain estimation for efficient 80% target achievement**

## Performance

- **Duration:** 2 minutes
- **Started:** 2026-03-03T13:05:29Z
- **Completed:** 2026-03-03T13:07:18Z
- **Tasks:** 1
- **Files created:** 2 (script + test plan JSON)
- **Deviation:** 0

## Accomplishments

- **Test plan generation script** created with test patterns for different file types (models, workflows, endpoints, services)
- **File-to-test mapping** generated for 75 files with 403 tests planned
- **Coverage gain estimation** per test based on efficiency factors (0.4-0.6)
- **Test distribution** across implementation plans: 127-04 (30 files), 127-05 (30 files), 127-06 (15 files)
- **Projected coverage** calculated at 50.92% (realistic intermediate target before final sweep)

## Task Commits

Each task was committed atomically:

1. **Task 1: Generate Detailed Test Plan from Gap Analysis** - `cddddcedc` (feat)

**Plan metadata:** 1 task, 2 minutes execution time

## Test Plan Summary

### Overall Statistics
- **Total tests planned:** 403
- **Total files covered:** 75
- **Projected coverage:** 50.92% (baseline: 26.15%, gain: +24.77 pp)
- **Total estimated gain:** 13,340 lines

### Distribution by Implementation Plan
| Plan | Files | Tests | Focus |
|------|-------|-------|-------|
| 127-03 | 0 | 0 | (Skipped - no models.py in high priority) |
| 127-04 | 30 | 195 | High-impact files (workflow_engine, atom_agent_endpoints, episode services) |
| 127-05 | 30 | 156 | Medium-impact files (lancedb_handler, byok_handler, skill services) |
| 127-06 | 15 | 52 | Low-impact files (canvas_tool, device_tool, browser_tool) |

### Test Efficiency Factors by File Type
| File Type | Test Type | Efficiency | Tests Planned |
|-----------|-----------|------------|--------------|
| models.py | Unit (CRUD, validation) | 0.50 | 0 (not in top 75) |
| workflow_engine.py | Property (DAG validation) | 0.60 | 10 |
| endpoints.py | Integration (TestClient) | 0.40 | 108 |
| service.py | Unit (business logic) | 0.55 | 295 |

## Top 10 Files with Most Tests Planned

| Rank | File | Tests | Current Coverage | Missing Lines | Est. Gain/Test |
|------|------|-------|------------------|---------------|---------------|
| 1 | core/atom_agent_endpoints.py | 12 | 11.98% | 698 | 46.5 |
| 2 | core/workflow_engine.py | 10 | 6.36% | 1089 | 130.7 |
| 3 | core/episode_segmentation_service.py | 8 | 12.07% | 510 | 70.1 |
| 4 | core/workflow_analytics_engine.py | 8 | 31.43% | 408 | 49.0 |
| 5 | core/workflow_debugger.py | 6 | 11.76% | 465 | 62.0 |
| 6 | core/lancedb_handler.py | 6 | 14.10% | 609 | 81.2 |
| 7 | core/llm/byok_handler.py | 6 | 11.01% | 582 | 77.6 |
| 8 | core/advanced_workflow_system.py | 6 | 26.17% | 378 | 50.4 |
| 9 | core/auto_document_ingestion.py | 6 | 18.33% | 392 | 52.3 |
| 10 | core/skill_registry_service.py | 6 | 9.29% | 332 | 45.7 |

## Test Plan Structure

### Test Type Patterns
Each file type has predefined test patterns with specific test names:

**Models (models.py):**
- test_create_{model}
- test_read_{model}
- test_update_{model}
- test_delete_{model}
- test_{model}_relationships
- test_{model}_validation
- test_{model}_edge_cases

**Workflow Engines (workflow_engine.py):**
- test_dag_acyclic
- test_dag_topological_order
- test_workflow_execution_order
- test_parallel_steps_independent
- test_workflow_rollback_on_failure

**Endpoints (endpoints.py, routes.py, api/):**
- test_get_{resource}
- test_post_{resource}
- test_put_{resource}
- test_delete_{resource}
- test_{resource}_not_found
- test_{resource}_validation_error

**Services (service.py, _service.py):**
- test_{service}_happy_path
- test_{service}_error_handling
- test_{service}_edge_cases
- test_{service}_validation

### Coverage Projection Formula
```
estimated_gain_per_test = missing_lines × efficiency / len(pattern_tests)
coverage_gain_percentage = (total_estimated_gain / total_missing_lines) × 100
projected_coverage = baseline_coverage + coverage_gain_percentage
```

## Files Created

### Created
1. **backend/tests/scripts/generate_test_plan.py** (213 lines)
   - Test pattern definitions for 4 file types
   - Efficiency factors: models (0.5), workflows (0.6), endpoints (0.4), services (0.55)
   - Coverage projection calculation
   - Implementation plan assignment logic
   - Aggressive test targeting: ALL high/medium impact files

2. **backend/tests/coverage_reports/metrics/phase_127_test_plan.json** (gitignored)
   - 403 tests across 75 files
   - Projected coverage: 50.92%
   - Grouped by implementation plan (127-04 through 127-06)
   - Test names, estimated gain per test, complexity, business impact

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

1. **Aggressive test targeting**
   - Include ALL high and medium impact files (not just top 15-30)
   - Top 15 low impact files for completeness
   - Tests per file: min(pattern_tests * 2, max(5, missing_lines / 50))

2. **Test efficiency factors**
   - Models: 0.50 (CRUD operations cover 50% of lines per test)
   - Workflows: 0.60 (property tests highly effective for DAG validation)
   - Endpoints: 0.40 (API tests cover fewer lines per test due to routing overhead)
   - Services: 0.55 (business logic unit tests moderately efficient)

3. **Coverage projection formula**
   - More accurate than simple percentage
   - Accounts for actual lines covered vs. total missing lines
   - Realistic intermediate target (50.92%) before final sweep in 127-06

4. **Implementation plan distribution**
   - 127-03: Empty (no models.py in high priority files)
   - 127-04: All high-impact files (30 files, 195 tests)
   - 127-05: All medium-impact files (30 files, 156 tests)
   - 127-06: Top low-impact files (15 files, 52 tests)

## Issues Encountered

None - all tasks completed successfully.

## Verification Results

All verification steps passed:

1. ✅ **Test plan JSON exists and is valid** - phase_127_test_plan.json created
2. ✅ **Tests distributed across implementation plans** - 127-04 (30), 127-05 (30), 127-06 (15)
3. ✅ **Each plan entry has test names and estimated gain** - All 75 files have test_names array
4. ✅ **Projected coverage calculated** - 50.92% (baseline 26.15% + 24.77 pp gain)

## Coverage Analysis

### Gap to Target
- **Baseline:** 26.15%
- **Target:** 80.00%
- **Gap:** 53.85 percentage points
- **Projected after tests:** 50.92% (covers 46.1% of gap)

### Remaining Work
- **Remaining gap after tests:** 29.08 percentage points (80% - 50.92%)
- **Estimated additional tests needed:** ~400-500 (based on current efficiency)
- **Recommendation:** Extend phase with additional plans or increase test density in 127-06

## Next Phase Readiness

✅ **Test plan complete** - 403 tests mapped to 75 files with estimated coverage gain

**Ready for:**
- Phase 127 Plan 03: (Skipped - no models.py files)
- Phase 127 Plan 04: High-impact file testing (30 files, 195 tests)
- Phase 127 Plan 05: Medium-impact file testing (30 files, 156 tests)
- Phase 127 Plan 06: Low-impact file testing + final sweep (15+ files, 52+ tests)

**Recommendations for follow-up:**
1. **Execute 127-04 first** - Highest impact files with 195 tests for workflow_engine, atom_agent_endpoints, episode services
2. **Re-measure coverage** after each plan to adjust projections
3. **Extend 127-06** to include additional medium/low impact files if 80% target not reached
4. **Consider property-based tests** for workflow_engine.py (already planned in test patterns)
5. **Add integration tests** for API endpoints using FastAPI TestClient (already planned)

---

*Phase: 127-backend-final-gap-closure*
*Plan: 02*
*Completed: 2026-03-03*
