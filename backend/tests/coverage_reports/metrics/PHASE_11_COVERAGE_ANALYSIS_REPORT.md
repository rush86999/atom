# Phase 11 Coverage Analysis Report

**Generated:** 2026-02-16T00:15:27.261346Z
**Purpose:** Identify highest-impact testing opportunities for Phases 12-13

---

## Executive Summary

### Current Coverage Status

| Metric | Value |
|--------|-------|
| Overall Coverage | 0.48% |
| Covered Lines | 267 |
| Total Lines | 55,220 |
| Coverage Gap | 54,953 lines |
| Target Coverage (80%) | 44,176 lines |
| Remaining Gap | 43,909 lines |

### File Distribution by Size

| Tier | Size Range | File Count | Total Lines | Avg Coverage |
|------|------------|------------|-------------|--------------|
| Tier 1 | ≥500 lines | 6 | 5,919 | 0.0% |
| Tier 2 | 300-499 lines | 17 | 6,572 | 3.33% |
| Tier 3 | 200-299 lines | 54 | 13,277 | 0.0% |
| Tier 4 | 100-199 lines | 137 | 19,576 | 0.25% |
| Tier 5 | <100 lines | 187 | 9,876 | 0.0% |

---

## Top 20 High-Impact Files

Ranked by coverage gap (uncovered lines). **Target: 50% coverage per file** (Phase 8.6 proven sustainable).

| Rank | File | Lines | Current % | Uncovered | Priority | Tier | Test Type | Complexity |
|------|------|-------|-----------|-----------|----------|------|-----------|------------|
| 1 | core/models.py | 2351 | 0.0% | 2351 | 1.000 | Tier 1 | unit | high |
| 2 | core/workflow_engine.py | 1163 | 0.0% | 1163 | 1.000 | Tier 1 | property | high |
| 3 | core/atom_agent_endpoints.py | 736 | 0.0% | 736 | 1.000 | Tier 1 | integration | high |
| 4 | core/workflow_analytics_engine.py | 593 | 0.0% | 593 | 1.000 | Tier 1 | property | high |
| 5 | core/llm/byok_handler.py | 549 | 0.0% | 549 | 1.000 | Tier 1 | property | high |
| 6 | core/workflow_debugger.py | 527 | 0.0% | 527 | 1.000 | Tier 1 | property | high |
| 7 | core/byok_endpoints.py | 498 | 0.0% | 498 | 1.000 | Tier 2 | integration | high |
| 8 | core/lancedb_handler.py | 494 | 0.0% | 494 | 1.000 | Tier 2 | property | high |
| 9 | core/auto_document_ingestion.py | 479 | 0.0% | 479 | 1.000 | Tier 2 | unit | high |
| 10 | core/workflow_versioning_system.py | 476 | 0.0% | 476 | 1.000 | Tier 2 | property | high |
| 11 | core/advanced_workflow_system.py | 473 | 0.0% | 473 | 1.000 | Tier 2 | property | high |
| 12 | core/episode_segmentation_service.py | 422 | 0.0% | 422 | 1.000 | Tier 2 | unit | high |
| 13 | tools/canvas_tool.py | 406 | 0.0% | 406 | 1.000 | Tier 2 | unit | high |
| 14 | core/workflow_template_system.py | 355 | 0.0% | 355 | 1.000 | Tier 2 | property | medium |
| 15 | core/workflow_marketplace.py | 354 | 0.0% | 354 | 1.000 | Tier 2 | property | medium |
| 16 | core/proposal_service.py | 342 | 0.0% | 342 | 1.000 | Tier 2 | unit | medium |
| 17 | core/integration_data_mapper.py | 338 | 0.0% | 338 | 1.000 | Tier 2 | unit | medium |
| 18 | core/workflow_analytics_endpoints.py | 333 | 0.0% | 333 | 1.000 | Tier 2 | property | medium |
| 19 | core/atom_meta_agent.py | 331 | 0.0% | 331 | 1.000 | Tier 2 | unit | medium |
| 20 | core/hybrid_data_ingestion.py | 314 | 0.0% | 314 | 1.000 | Tier 2 | unit | medium |


---

## Zero Coverage Quick Wins

Files with **0% coverage** and >100 lines. Testing these to 50% coverage provides fast wins.

**Total zero-coverage files >100 lines:** 212

| File | Lines | Est. Gain (50%) | Test Type | Complexity |
|------|-------|-----------------|-----------|------------|
| core/models.py | 2351 | 1176 | unit | high |
| core/workflow_engine.py | 1163 | 582 | property | high |
| core/atom_agent_endpoints.py | 736 | 368 | integration | high |
| core/workflow_analytics_engine.py | 593 | 296 | property | high |
| core/llm/byok_handler.py | 549 | 274 | property | high |
| core/workflow_debugger.py | 527 | 264 | property | high |
| core/byok_endpoints.py | 498 | 249 | integration | high |
| core/lancedb_handler.py | 494 | 247 | property | high |
| core/auto_document_ingestion.py | 479 | 240 | unit | high |
| core/workflow_versioning_system.py | 476 | 238 | property | high |
| core/advanced_workflow_system.py | 473 | 236 | property | high |
| core/episode_segmentation_service.py | 422 | 211 | unit | high |
| tools/canvas_tool.py | 406 | 203 | unit | high |
| core/workflow_template_system.py | 355 | 178 | property | medium |
| core/workflow_marketplace.py | 354 | 177 | property | medium |
| core/proposal_service.py | 342 | 171 | unit | medium |
| core/integration_data_mapper.py | 338 | 169 | unit | medium |
| core/workflow_analytics_endpoints.py | 333 | 166 | property | medium |
| core/atom_meta_agent.py | 331 | 166 | unit | medium |
| core/hybrid_data_ingestion.py | 314 | 157 | unit | medium |
| core/formula_extractor.py | 313 | 156 | unit | medium |
| core/workflow_ui_endpoints.py | 312 | 156 | property | medium |
| tools/browser_tool.py | 299 | 150 | unit | medium |
| api/user_templates_endpoints.py | 298 | 149 | integration | medium |
| core/agent_world_model.py | 298 | 149 | unit | medium |


---

## Module Breakdown

### Core Module

**Files:** 277

| Metric | Value |
|--------|-------|
| Coverage | 0.7% |
| Covered Lines | 267 |
| Total Lines | 40,930 |
| Coverage Gap | 40,663 |

**Top 5 Gaps in core/:**
1. core/models.py: 2351 lines uncovered (0.0%)
2. core/workflow_engine.py: 1163 lines uncovered (0.0%)
3. core/atom_agent_endpoints.py: 736 lines uncovered (0.0%)
4. core/workflow_analytics_engine.py: 593 lines uncovered (0.0%)
5. core/llm/byok_handler.py: 549 lines uncovered (0.0%)


### API Module

**Files:** 113

| Metric | Value |
|--------|-------|
| Coverage | 0.0% |
| Covered Lines | 0 |
| Total Lines | 12,904 |
| Coverage Gap | 12,904 |

**Top 5 Gaps in api/:**
1. api/user_templates_endpoints.py: 298 lines uncovered (0.0%)
2. api/agent_routes.py: 282 lines uncovered (0.0%)
3. api/workflow_versioning_endpoints.py: 259 lines uncovered (0.0%)
4. api/workflow_collaboration.py: 253 lines uncovered (0.0%)
5. api/device_capabilities.py: 248 lines uncovered (0.0%)


### Tools Module

**Files:** 11

| Metric | Value |
|--------|-------|
| Coverage | 0.0% |
| Covered Lines | 0 |
| Total Lines | 1,386 |
| Coverage Gap | 1,386 |

**Top 5 Gaps in tools/:**
1. tools/canvas_tool.py: 406 lines uncovered (0.0%)
2. tools/browser_tool.py: 299 lines uncovered (0.0%)
3. tools/device_tool.py: 280 lines uncovered (0.0%)
4. tools/registry.py: 150 lines uncovered (0.0%)
5. tools/agent_guidance_canvas_tool.py: 112 lines uncovered (0.0%)


---

## Phase 12-13 Testing Strategy

### Strategy Overview

Based on Phase 8.6 validation (3.38x velocity acceleration), this analysis prioritizes **high-impact files** for maximum coverage gain.

**Key Principles:**
- Target 50% average coverage per file (proven sustainable)
- Prioritize largest files first (Tier 1 > Tier 2 > Tier 3)
- Use appropriate test types (property, integration, unit)
- 3-4 files per plan for focused execution

### Phase 12: Tier 1 Files

**Target:** 28% coverage (+5.2 percentage points)
**Focus:** Files ≥500 lines with <20% coverage
**Estimated Plans:** 4-5 plans
**Estimated Velocity:** +1.3-1.5% per plan

**Files:** 6 files

### Phase 13: Tier 2-3 + Zero Coverage

**Target:** 35% coverage (+7.0 percentage points)
**Focus:** Files 300-500 lines, <30% coverage + zero-coverage quick wins
**Estimated Plans:** 5-6 plans
**Estimated Velocity:** +1.2-1.4% per plan

**Files:** 30 files

### Test Type Recommendations

| Test Type | When to Use | Examples |
|-----------|-------------|----------|
| **Property Tests** | Stateful logic, workflows, handlers | workflow_engine, byok_handler, coordinators |
| **Integration Tests** | API endpoints, routes | atom_agent_endpoints, workflow_endpoints, API routes |
| **Unit Tests** | Isolated logic, services, utilities | lancedb_handler, auto_document_ingestion, services |

### Execution Plan

**Files Per Plan:** 3-4 high-impact files
**Target Coverage Per File:** 50% (Phase 8.6 proven sustainable)
**Estimated Velocity:** +1.5% per plan (maintaining Phase 8.6 acceleration)
**Estimated Duration:** 4-6 hours per plan

**Total Estimated Impact:**
- Phase 12: +5.2 percentage points
- Phase 13: +7.0 percentage points
- Combined: +12.2 percentage points

---

## Recommendations

1. **Start with Tier 1 files** (Phase 12) - Highest ROI with 3.38x velocity acceleration
2. **Target 50% coverage per file** - Proven sustainable from Phase 8.6
3. **Use appropriate test types** - Property tests for stateful logic, integration for APIs
4. **3-4 files per plan** - Focused execution without overwhelming complexity
5. **Leverage existing test infrastructure** - Property test patterns, AsyncMock, FastAPI TestClient

---

## Appendix: Data Sources

- **Coverage Data:** `tests/coverage_reports/metrics/coverage.json`
- **Analysis Script:** `tests/scripts/analyze_coverage_gaps.py`
- **Priority Files:** `tests/coverage_reports/priority_files_for_phases_12_13.json`

*Generated by Phase 11 Coverage Analysis - 2026-02-16*
