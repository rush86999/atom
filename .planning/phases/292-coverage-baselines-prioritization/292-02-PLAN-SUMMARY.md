---
phase: 292-coverage-baselines-prioritization
plan: 02
subsystem: test-coverage
tags: [prioritization, high-impact-files, tiered-ranking, business-criticality]
requires:
  - 292-01 (backend + frontend baselines)
provides:
  - prioritized_files_v11.0.json (backend 3-tier ranked file list)
  - HIGH_IMPACT_PRIORITIZATION_v11.0.md (backend human-readable report)
  - prioritized_frontend_components_v11.0.json (frontend criticality-ranked component list)
  - HIGH_IMPACT_FRONTEND_COMPONENTS_v11.0.md (frontend human-readable report)
affects:
  - coverage expansion phases (293-295)
tech-stack:
  added:
    - coverage_to_prioritize.py (wrapper converting raw coverage.json to prioritize_high_impact_files.py input)
    - prioritize_frontend_components.py (frontend-specific criticality-based prioritization)
  patterns:
    - Wrapper pattern: thin conversion layer reuses existing prioritize_high_impact_files.py (D-05)
    - Same priority formula for frontend as backend for consistency (D-05 spirit)
key-files:
  created:
    - backend/tests/scripts/coverage_to_prioritize.py
    - backend/tests/scripts/prioritize_frontend_components.py
    - backend/tests/coverage_reports/metrics/prioritized_files_v11.0.json
    - backend/tests/coverage_reports/HIGH_IMPACT_PRIORITIZATION_v11.0.md
    - frontend-nextjs/coverage/prioritized_frontend_components_v11.0.json
    - frontend-nextjs/coverage/HIGH_IMPACT_FRONTEND_COMPONENTS_v11.0.md
  modified: []
decisions:
  - D-04: 3-tier prioritization (<10%, 10-30%, 30-50%, all >200 lines) applied via post-processing step
  - D-05: Reused prioritize_high_impact_files.py -- wrapper pattern kept existing script unchanged
  - D-07: Frontend prioritized by business criticality (Canvas/Chat/Agent Dashboard > Integrations > UI > Hooks)
metrics:
  plan_duration_seconds: ~600
  completed_date: "2026-04-24"
---

# Phase 292 Coverage Baselines & Prioritization Plan 02: Prioritization Summary

**Generated prioritized high-impact file lists for backend and frontend to guide coverage expansion in Phases 293-295.**

Backend uses the proven `priority_score = (uncovered_lines * impact_score) / (coverage_pct + 1)` formula with 3-tier thresholds. Frontend uses business criticality (Critical/High/Medium/Low) as the primary sort key. Both lists delivered in JSON and Markdown formats.

### Deliverables

| # | Artifact | Location | Status |
|---|----------|----------|--------|
| 1 | Backend wrapper script | `backend/tests/scripts/coverage_to_prioritize.py` | Created |
| 2 | Frontend prioritization script | `backend/tests/scripts/prioritize_frontend_components.py` | Created |
| 3 | Backend tiered JSON | `backend/tests/coverage_reports/metrics/prioritized_files_v11.0.json` | Created |
| 4 | Backend Markdown | `backend/tests/coverage_reports/HIGH_IMPACT_PRIORITIZATION_v11.0.md` | Created |
| 5 | Frontend tiered JSON | `frontend-nextjs/coverage/prioritized_frontend_components_v11.0.json` | Created |
| 6 | Frontend Markdown | `frontend-nextjs/coverage/HIGH_IMPACT_FRONTEND_COMPONENTS_v11.0.md` | Created |

### Key Results

**Backend high-impact files** (83 files prioritized, 20,461 uncovered lines):
- Tier 1 (must-fix, <10% coverage): 19 files, 4,509 uncovered lines
- Tier 2 (should-fix, 10-30% coverage): 41 files, 10,972 uncovered lines
- Tier 3 (nice-to-fix, 30-50% coverage): 23 files, 4,980 uncovered lines
- Top 3: `core/workflow_analytics_endpoints.py` (priority 1570), `core/workflow_parameter_validator.py` (1430), `api/workflow_versioning_endpoints.py` (1140)
- Source: Phase 292 backend baseline (18.25% overall coverage)

**Frontend high-impact components** (707 components analyzed, 15.14% overall line coverage):
- Critical (Canvas, Chat, Agent Dashboard): 19 components
- High (Integrations): 17 components
- Medium (UI, Pages, Lib): 631 components
- Low (Hooks, Shared): 40 components
- Top 3: `chat/canvas-host.tsx`, `chat/CanvasHost.tsx`, `chat/AgentWorkspace.tsx`
- Source: Jest coverage-summary from Phase 292 frontend baseline

**Cross-check** confirmed zero file overlap between backend and frontend lists (Python vs TS/TSX).

## Tasks

### Task 1: Create backend prioritization wrapper and generate tiered list

Created `backend/tests/scripts/coverage_to_prioritize.py` which:
1. Reads raw coverage.json from pytest-cov output
2. Converts to `files_below_threshold` format with >200 line filter (D-06)
3. Invokes existing `prioritize_high_impact_files.py` with `--min-coverage 50`
4. Post-processes into 3 tiers (Tier 1: <10%, Tier 2: 10-30%, Tier 3: 30-50%)
5. Writes `prioritized_files_v11.0.json` and `HIGH_IMPACT_PRIORITIZATION_v11.0.md`

Validation: All 3 tiers present, sorted by priority_score descending, tier boundary checks pass.

**Commit:** `eb906c320`

### Task 2: Create frontend high-impact component list by business criticality

Created `backend/tests/scripts/prioritize_frontend_components.py` which:
1. Reads frontend coverage-summary JSON (with `total` key and `lines.pct` format)
2. Maps files to criticality tiers: Critical (Canvas/Chat/Agent Dashboard), High (Integrations), Medium (UI/pages/lib), Low (hooks/shared)
3. Computes `priority_score = (uncovered_lines * criticality_score) / (coverage_pct + 1)`
4. Sorts by criticality_score desc, then priority_score desc
5. Writes `prioritized_frontend_components_v11.0.json` and `HIGH_IMPACT_FRONTEND_COMPONENTS_v11.0.md`

Design decision: Input uses `phase_292_frontend_summary.json` (coverage-summary format with `lines.pct` fields) rather than `coverage-final.json` (raw Istanbul format with statement/function/branch maps).

Validation: All 4 criticality tiers present, sorted by priority_score descending, Critical tier prioritizes Canvas/Chat components.

**Commit:** `b1a32ac9a`

### Task 3: Cross-check outputs and finalize deliverables

- Backend JSON: 83 Python files (83 unique)
- Frontend JSON: 707 TS/TSX files (707 unique)
- Overlap: 0 (zero overlap -- different file types and directories)
- All output JSON parseable by `json.load()` without errors

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Frontend coverage input format mismatch**

- **Found during:** Task 2
- **Issue:** The plan specified `frontend-nextjs/coverage/coverage-final.json` as input, but that file is Istanbul raw format (file entries have `statementMap`, `fnMap`, `branchMap`, `s`, `f`, `b` -- no `lines.pct` fields). It also lacks the `total` key expected by the script.
- **Fix:** Updated the script to accept the coverage-summary format (`phase_292_frontend_summary.json` which has `total` key and `lines.pct` format). The `process_coverage_data` function now strips absolute path prefixes from entries (e.g., `/Users/rushiparikh/projects/atom/frontend-nextjs/...`) before matching criticality patterns.
- **Files modified:** `backend/tests/scripts/prioritize_frontend_components.py`
- **Commit:** Included in Task 2 commit `b1a32ac9a`

**2. [Rule 3 - Blocking] Python2 vs Python3 default**

- **Found during:** Task 1 execution
- **Issue:** Default `python` on the system is Python 2.7.16, which doesn't support `argparse.Namespace` type annotations.
- **Fix:** Used `python3` explicitly in all invocation commands.
- **Files modified:** None (invocation fix only)
- **Commit:** N/A

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None -- all outputs are generated from real coverage data using the defined formulas. No hardcoded or placeholder values.

## Threat Surface

No threat flags. All scripts are analysis tooling that read coverage data and produce reports. No new network endpoints, auth paths, or data storage patterns introduced.

## Self-Check: PASSED

- [x] `backend/tests/scripts/coverage_to_prioritize.py` exists and is executable
- [x] `backend/tests/scripts/prioritize_frontend_components.py` exists and is executable
- [x] `backend/tests/coverage_reports/metrics/prioritized_files_v11.0.json` exists, has tier_1/tier_2/tier_3 keys, sorted desc
- [x] `backend/tests/coverage_reports/HIGH_IMPACT_PRIORITIZATION_v11.0.md` exists, contains "Tier 1"
- [x] `frontend-nextjs/coverage/prioritized_frontend_components_v11.0.json` exists, has by_criticality with 4 tiers, sorted desc
- [x] `frontend-nextjs/coverage/HIGH_IMPACT_FRONTEND_COMPONENTS_v11.0.md` exists, contains "Critical"
- [x] Backend tiers correct: T1 files <10%, T2 files 10-30%, T3 files 30-50%
- [x] Zero overlap between backend and frontend file lists
- [x] All JSON output parseable by `json.load()`
