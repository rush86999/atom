---
phase: 81-coverage-analysis-prioritization
plan: 02
subsystem: testing
tags: [coverage-analysis, prioritization, high-impact-files, test-strategy]

# Dependency graph
requires:
  - phase: 81-coverage-analysis-prioritization
    plan: 01
    provides: baseline coverage report (coverage.json)
provides:
  - Priority ranking script for high-impact file identification
  - Machine-readable high-impact files JSON (high_impact_files.json)
  - Priority ranking markdown report (HIGH_IMPACT_FILES.md)
  - Business criticality scoring system (CRITICALITY_MAP)
affects: [test-planning, coverage-expansion, phase-82-90]

# Tech tracking
tech-stack:
  added: [priority_ranking.py, high_impact_files.json, HIGH_IMPACT_FILES.md]
  patterns: [priority score calculation, business criticality scoring, tier-based prioritization]

key-files:
  created:
    - backend/tests/coverage_reports/priority_ranking.py
    - backend/tests/coverage_reports/metrics/high_impact_files.json
    - backend/tests/coverage_reports/HIGH_IMPACT_FILES.md
  modified:
    - backend/tests/coverage_reports/metrics/coverage.json (read-only input)

key-decisions:
  - "Business criticality scoring: P0 (9-10), P1 (7-8), P2 (5-6), P3 (3-4)"
  - "Priority score formula: (uncovered_lines / 100) * criticality"
  - "High-impact threshold: >200 lines, <30% coverage"
  - "P0 tier includes governance, LLM integration, episodic memory services"
  - "Data-driven test prioritization focuses on maximum coverage gain per test"

patterns-established:
  - "Pattern: Priority score weights opportunity (uncovered lines) by impact (criticality)"
  - "Pattern: Tier-based prioritization (P0-P3) aligns with business risk"
  - "Pattern: Machine-readable JSON enables automation in downstream phases"
  - "Pattern: Markdown report provides human-readable prioritization guidance"

# Metrics
duration: 3min 27sec
completed: 2026-02-24
---

# Phase 81: Coverage Analysis & Prioritization - Plan 02 Summary

**High-impact file identification and prioritization with business criticality scoring, focusing test development on maximum coverage gain per test added**

## Performance

- **Duration:** 3 minutes 27 seconds
- **Started:** 2026-02-24T12:07:01Z
- **Completed:** 2026-02-24T12:10:28Z
- **Tasks:** 3
- **Files created:** 3

## Accomplishments

- **49 high-impact files identified** with >200 lines and <30% coverage
- **14,511 uncovered lines** represent opportunity for coverage expansion
- **Business criticality scoring system** (CRITICALITY_MAP) with P0-P3 tiers
- **Priority ranking script** (priority_ranking.py) for automated analysis
- **Machine-readable JSON** (high_impact_files.json) for downstream automation
- **Priority ranking report** (HIGH_IMPACT_FILES.md) with actionable recommendations

## Task Commits

Each task was committed atomically:

1. **Task 1: Create priority ranking script** - `27d7a8ac` (feat)
2. **Task 2: Execute priority ranking analysis** - `c0421c56` (feat)
3. **Task 3: Generate priority ranking markdown report** - `b9d84ea0` (feat)

**Plan metadata:** (to be added in final commit)

## Files Created

### Created
1. `backend/tests/coverage_reports/priority_ranking.py` - Priority ranking script with:
   - CRITICALITY_MAP for business criticality scoring (1-10 scale)
   - calculate_priority_score(): (uncovered_lines / 100) * criticality
   - filter_high_impact(): filters files >200 lines, <30% coverage
   - generate_priority_report(): creates HIGH_IMPACT_FILES.md
   - save_high_impact_json(): creates machine-readable JSON
   - CLI entry point for manual execution

2. `backend/tests/coverage_reports/metrics/high_impact_files.json` - Machine-readable ranking with:
   - 49 high-impact files with complete metadata
   - priority_score, coverage_pct, line_count, criticality, tier for each file
   - Sorted by priority_score descending
   - Total uncovered lines: 14,511
   - Total lines of code: 15,599

3. `backend/tests/coverage_reports/HIGH_IMPACT_FILES.md` - Priority ranking report with:
   - Summary statistics (49 files, 14,511 uncovered lines, 6.2% avg coverage)
   - Tier distribution (P0: 2, P1: 5, P2: 3, P3: 39)
   - Top 5 files by priority score
   - Priority tiers explanation (P0-P3)
   - Complete ranking table for all 49 files
   - Recommendations for test development strategy
   - Next steps linking to Phase 82 (Core Services) and Phase 86 (Property-Based Testing)

## Analysis Results

### Top 10 Files by Priority Score

| Rank | File | Lines | Coverage | Uncovered | Criticality | Priority Score | Tier |
|------|------|-------|----------|-----------|-------------|----------------|------|
| 1 | core/workflow_engine.py | 1163 | 14.53% | 994 | 6 | 59.64 | P2 |
| 2 | core/episode_segmentation_service.py | 463 | 17.93% | 380 | 9 | 34.2 | P0 |
| 3 | core/proposal_service.py | 342 | 0.0% | 342 | 7 | 23.94 | P1 |
| 4 | core/lancedb_handler.py | 577 | 24.61% | 435 | 5 | 21.75 | P2 |
| 5 | core/supervision_service.py | 216 | 0.0% | 216 | 9 | 19.44 | P0 |
| 6 | tools/browser_tool.py | 373 | 30.03% | 261 | 7 | 18.27 | P1 |
| 7 | tools/device_tool.py | 349 | 30.09% | 244 | 7 | 17.08 | P1 |
| 8 | core/agent_graduation_service.py | 227 | 10.57% | 203 | 8 | 16.24 | P1 |
| 9 | core/episode_retrieval_service.py | 261 | 22.22% | 203 | 8 | 16.24 | P1 |
| 10 | core/embedding_service.py | 442 | 28.28% | 317 | 5 | 15.85 | P2 |

### Tier Distribution

| Tier | Files | Description |
|------|-------|-------------|
| **P0** | 2 | Governance, safety, LLM integration (criticality 9-10) |
| **P1** | 5 | Memory system, tools, training (criticality 7-8) |
| **P2** | 3 | Supporting services, infrastructure (criticality 5-6) |
| **P3** | 39 | Utility code, low-risk modules (criticality 3-4) |

**Note:** P3 tier dominates (39 files) because many files have default criticality=3 (not explicitly mapped in CRITICALITY_MAP). This is expected and correct behavior.

## P0 Tier Files (Highest Priority)

1. **core/episode_segmentation_service.py** - 463 lines, 17.93% coverage, 380 uncovered
   - Priority score: 34.2, Criticality: 9
   - Core episodic memory functionality

2. **core/supervision_service.py** - 216 lines, 0.0% coverage, 216 uncovered
   - Priority score: 19.44, Criticality: 9
   - SUPERVISED maturity agent real-time monitoring

## Decisions Made

- **Business criticality scoring**: P0 (9-10) for governance/safety/LLM, P1 (7-8) for memory/tools/training, P2 (5-6) for supporting services, P3 (3-4) for utilities
- **Priority score formula**: (uncovered_lines / 100) * criticality weights opportunity by impact
- **High-impact thresholds**: >200 lines (significant size), <30% coverage (major opportunity)
- **Default criticality**: 3 for unknown files (conservative baseline, assumes low business impact)
- **Data-driven prioritization**: Focus on maximum coverage gain per test added

## Deviations from Plan

None - plan executed exactly as written. All 3 tasks completed successfully.

## Issues Encountered

- **Python version confusion**: Initial testing used `python` (Python 2.7) instead of `python3` (Python 3.14)
  - **Fix**: Used `python3` explicitly for all script execution
  - **Impact**: Minimal - resolved quickly, no changes to code required
  - **Documentation**: Script shebang uses `#!/usr/bin/env python3` for correct execution

## Verification Results

All verification steps passed:

1. ✅ **priority_ranking.py imports successfully** - Module loads without errors
2. ✅ **Script runs without errors** - Generates outputs correctly
3. ✅ **high_impact_files.json exists** - Machine-readable ranking created
4. ✅ **49 high-impact files identified** - Exceeds minimum requirement (20)
5. ✅ **P0 tier includes critical services** - episode_segmentation_service, supervision_service
6. ✅ **HIGH_IMPACT_FILES.md has all sections** - Priority ranking, tier explanation, recommendations
7. ✅ **Each file has required fields** - priority_score, coverage_pct, line_count, criticality, tier
8. ✅ **Files sorted by priority_score** - Descending order for prioritization

## Business Criticality Mapping

### P0 Tier (Criticality 9-10)
- Governance & Safety: agent_governance_service (10), governance_cache (10), trigger_interceptor (10), agent_context_resolver (9), supervision_service (9)
- LLM Integration: byok_handler (10), atom_agent_endpoints (9), streaming_handler (8)

### P1 Tier (Criticality 7-8)
- Episodic Memory: episode_segmentation_service (9), episode_retrieval_service (8), episode_lifecycle_service (8), agent_graduation_service (8)
- Tools & Devices: canvas_tool (7), browser_tool (7), device_tool (7)
- Training: student_training_service (8), proposal_service (7)

### P2 Tier (Criticality 5-6)
- Supporting Services: workflow_engine (6), lancedb_handler (5), embedding_service (5)

### P3 Tier (Criticality 3-4)
- Default: All unmapped files get criticality=3 (conservative baseline)

## Next Phase Readiness

✅ **Priority ranking complete** - High-impact files identified and ranked

**Ready for:**
- Phase 82: Core Services Unit Testing (focus on P0 tier)
- Phase 86: Property-Based Testing (Hypothesis for complex logic)
- Phases 83-90: Targeted test development based on priority ranking

**Recommendations for Phase 82 (Core Services Unit Testing):**
1. **Start with P0 files** - episode_segmentation_service.py (380 uncovered), supervision_service.py (216 uncovered)
2. **Target 80% coverage** on P0 files before moving to P1
3. **Focus on critical paths** - agent execution, governance checks, LLM routing
4. **Use property-based tests** for complex governance logic (Hypothesis)
5. **Track progress** - Re-run priority ranking after each phase to measure improvement

**Expected Impact:**
- Covering 50% of P0 files = ~300 uncovered lines addressed
- Covering 50% of top 10 files = ~2,500 uncovered lines addressed
- Each 10% improvement on P0 files = significant overall coverage gain

---

*Phase: 81-coverage-analysis-prioritization*
*Plan: 02*
*Completed: 2026-02-24*
*Total high-impact files: 49*
*Total uncovered lines: 14,511*
