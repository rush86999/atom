# High-Impact File Prioritization v5.0

**Generated**: 2026-02-27T16:13:11+00:00Z
**Phase**: 100-03

## Executive Summary

- **Total files below 80% coverage**: 50
- **Total uncovered lines**: 15,385

### Distribution by Impact Tier

| Tier | Files | Uncovered Lines | Description |
|------|-------|-----------------|-------------|
| Critical | 8 | 2,731 | Governance, LLM, security |
| High | 4 | 1,024 | Memory, tools, training |
| Medium | 38 | 11,630 | Supporting services |
| Low | 0 | 0 | Utility code |

### Top 3 Files by Priority Score

| Rank | File | Coverage | Uncovered | Impact | Priority Score | Tier |
|------|------|----------|-----------|--------|----------------|------|
| 1 | core/enterprise_user_management.py | 0.00% | 213 | 5 | 1065.00 | Medium |
| 2 | api/smarthome_routes.py | 0.00% | 205 | 5 | 1025.00 | Medium |
| 3 | core/workflow_engine.py | 4.78% | 1089 | 5 | 942.04 | Medium |

## Priority Score Formula

### Formula
```
priority_score = (uncovered_lines * impact_score) / (current_coverage_pct + 1)
```

### Why This Formula?

- **uncovered_lines**: More uncovered lines = more potential coverage gain
- **impact_score**: Higher business impact = more value per test
- **current_coverage_pct + 1**: Lower current coverage = higher priority
  - Adding 1 prevents division by zero for 0% coverage files
  - This creates a "quick wins" bias towards files with very low coverage

### Example Calculations

| Scenario | Uncovered | Impact | Coverage | Priority Score | Interpretation |
|----------|-----------|--------|----------|----------------|----------------|
| A: Large gap, critical | 1000 | 10 | 5% | 952.38 | Very high priority - lots of critical code to test |
| B: Small gap, critical | 100 | 10 | 20% | 47.62 | High priority - critical but small |
| C: Large gap, medium | 1000 | 5 | 5% | 476.19 | Medium-high priority - lots of code |
| D: Small gap, low | 100 | 3 | 50% | 6.00 | Low priority - small, low impact |
| E: Zero coverage, high | 200 | 7 | 0% | 1400.00 | Quick win - no coverage exists yet |

## Top 50 Ranked Files

| Rank | File | Coverage | Uncovered | Impact | Priority | Est. Tests | Tier |
|------|------|----------|-----------|--------|----------|------------|------|
| 1 | core/enterprise_user_management.py | 0.00% | 213 | 5 | 1065.00 | 10 | Medium |
| 2 | api/smarthome_routes.py | 0.00% | 205 | 5 | 1025.00 | 10 | Medium |
| 3 | core/workflow_engine.py | 4.78% | 1089 | 5 | 942.04 | 27 | Medium |
| 4 | tools/canvas_tool.py | 3.80% | 385 | 10 | 802.08 | 10 | Critical |
| 5 | core/llm/byok_handler.py | 8.72% | 582 | 10 | 598.77 | 14 | Critical |
| 6 | core/episode_segmentation_service.py | 8.25% | 510 | 10 | 551.35 | 12 | Critical |
| 7 | core/proposal_service.py | 7.64% | 309 | 10 | 357.64 | 10 | Critical |
| 8 | core/atom_agent_endpoints.py | 9.06% | 680 | 5 | 337.97 | 17 | Medium |
| 9 | core/skill_registry_service.py | 7.19% | 331 | 7 | 282.91 | 10 | High |
| 10 | core/episode_retrieval_service.py | 9.03% | 271 | 10 | 270.19 | 10 | Critical |
| 11 | core/agent_integration_gateway.py | 4.52% | 273 | 5 | 247.28 | 10 | Medium |
| 12 | core/lancedb_handler.py | 11.51% | 609 | 5 | 243.41 | 15 | Medium |
| 13 | tools/browser_tool.py | 9.92% | 261 | 10 | 239.01 | 10 | Critical |
| 14 | api/media_routes.py | 4.00% | 220 | 5 | 220.00 | 10 | Medium |
| 15 | core/workflow_debugger.py | 9.67% | 465 | 5 | 217.90 | 11 | Medium |
| 16 | core/agent_social_layer.py | 7.34% | 338 | 5 | 202.64 | 10 | Medium |
| 17 | core/agent_graduation_service.py | 9.44% | 203 | 10 | 194.44 | 10 | Critical |
| 18 | core/formula_extractor.py | 7.03% | 281 | 5 | 174.97 | 10 | Medium |
| 19 | tools/device_tool.py | 9.73% | 244 | 7 | 159.18 | 10 | High |
| 20 | core/auto_invoicer.py | 6.29% | 204 | 5 | 139.92 | 10 | Medium |
| 21 | core/auto_document_ingestion.py | 14.06% | 392 | 5 | 130.15 | 10 | Medium |
| 22 | core/collaboration_service.py | 9.22% | 259 | 5 | 126.71 | 10 | Medium |
| 23 | core/feedback_service.py | 7.07% | 198 | 5 | 122.68 | 10 | Medium |
| 24 | core/atom_meta_agent.py | 10.69% | 286 | 5 | 122.33 | 10 | Medium |
| 25 | core/embedding_service.py | 10.74% | 279 | 5 | 118.82 | 10 | Medium |
| 26 | core/agent_world_model.py | 14.02% | 245 | 7 | 114.18 | 10 | High |
| 27 | core/productivity/notion_service.py | 9.90% | 238 | 5 | 109.17 | 10 | Medium |
| 28 | core/generic_agent.py | 8.81% | 214 | 5 | 109.07 | 10 | Medium |
| 29 | core/atom_saas_websocket.py | 11.82% | 277 | 5 | 108.03 | 10 | Medium |
| 30 | core/hybrid_data_ingestion.py | 11.31% | 264 | 5 | 107.23 | 10 | Medium |
| 31 | core/workflow_versioning_system.py | 16.56% | 376 | 5 | 107.06 | 10 | Medium |
| 32 | core/workflow_parameter_validator.py | 10.37% | 237 | 5 | 104.22 | 10 | Medium |
| 33 | core/advanced_workflow_system.py | 18.21% | 378 | 5 | 98.39 | 10 | Medium |
| 34 | core/health_monitoring_service.py | 9.38% | 201 | 5 | 96.82 | 10 | Medium |
| 35 | core/governance_cache.py | 20.78% | 210 | 10 | 96.42 | 10 | Critical |
| 36 | core/graphrag_engine.py | 12.23% | 236 | 5 | 89.19 | 10 | Medium |
| 37 | core/bulk_operations_processor.py | 14.25% | 237 | 5 | 77.70 | 10 | Medium |
| 38 | core/integration_data_mapper.py | 16.80% | 254 | 5 | 71.35 | 10 | Medium |
| 39 | core/workflow_analytics_engine.py | 27.77% | 408 | 5 | 70.91 | 10 | Medium |
| 40 | core/cross_platform_correlation.py | 13.88% | 211 | 5 | 70.90 | 10 | Medium |
| 41 | core/enterprise_auth_service.py | 19.54% | 204 | 7 | 69.52 | 10 | High |
| 42 | core/workflow_ui_endpoints.py | 19.82% | 242 | 5 | 58.12 | 10 | Medium |
| 43 | core/enhanced_execution_state_manager.py | 18.28% | 218 | 5 | 56.54 | 10 | Medium |
| 44 | core/workflow_analytics_endpoints.py | 23.24% | 244 | 5 | 50.33 | 10 | Medium |
| 45 | api/agent_routes.py | 23.61% | 208 | 5 | 42.26 | 10 | Medium |
| 46 | core/advanced_workflow_endpoints.py | 23.20% | 201 | 5 | 41.53 | 10 | Medium |
| 47 | core/byok_endpoints.py | 38.01% | 293 | 5 | 37.55 | 10 | Medium |
| 48 | core/workflow_marketplace.py | 30.61% | 232 | 5 | 36.70 | 10 | Medium |
| 49 | api/package_routes.py | 33.18% | 230 | 5 | 33.65 | 10 | Medium |
| 50 | api/admin_routes.py | 37.77% | 240 | 5 | 30.95 | 10 | Medium |

## Quick Wins (0% Coverage, Critical/High Impact)

These 0 files have **zero coverage** but high business impact.
They are the "low hanging fruit" for Phase 101.

| Rank | File | Uncovered Lines | Impact | Tier | Est. Tests |
|------|------|-----------------|--------|------|------------|

## Phase Assignments (101-110)

### Phase 101: Backend Core

**Files**: 12

- tools/canvas_tool.py (Priority: 802.08)
- core/llm/byok_handler.py (Priority: 598.77)
- core/episode_segmentation_service.py (Priority: 551.35)
- core/proposal_service.py (Priority: 357.64)
- core/skill_registry_service.py (Priority: 282.91)
- core/episode_retrieval_service.py (Priority: 270.19)
- tools/browser_tool.py (Priority: 239.01)
- core/agent_graduation_service.py (Priority: 194.44)
- tools/device_tool.py (Priority: 159.18)
- core/agent_world_model.py (Priority: 114.18)
- ... and 2 more

### Phase 102: Backend Api

**Files**: 4

- api/media_routes.py (Priority: 220.00)
- api/agent_routes.py (Priority: 42.26)
- api/package_routes.py (Priority: 33.65)
- api/admin_routes.py (Priority: 30.95)

### Phase 103: Backend Property

**Files**: 12

- core/workflow_engine.py (Priority: 942.04)
- core/lancedb_handler.py (Priority: 243.41)
- core/workflow_debugger.py (Priority: 217.90)
- core/workflow_versioning_system.py (Priority: 107.06)
- core/workflow_parameter_validator.py (Priority: 104.22)
- core/advanced_workflow_system.py (Priority: 98.39)
- core/graphrag_engine.py (Priority: 89.19)
- core/workflow_analytics_engine.py (Priority: 70.91)
- core/workflow_ui_endpoints.py (Priority: 58.12)
- core/workflow_analytics_endpoints.py (Priority: 50.33)
- ... and 2 more

### Phase 104: Backend Error

**Files**: 1

- core/health_monitoring_service.py (Priority: 96.82)

### Phase 105: Frontend Core

**Files**: 10

- core/enterprise_user_management.py (Priority: 1065.00)
- api/smarthome_routes.py (Priority: 1025.00)
- core/atom_agent_endpoints.py (Priority: 337.97)
- core/agent_integration_gateway.py (Priority: 247.28)
- core/agent_social_layer.py (Priority: 202.64)
- core/formula_extractor.py (Priority: 174.97)
- core/auto_invoicer.py (Priority: 139.92)
- core/auto_document_ingestion.py (Priority: 130.15)
- core/collaboration_service.py (Priority: 126.71)
- core/feedback_service.py (Priority: 122.68)

### Phase 106: Frontend Api

**Files**: 10

- core/atom_meta_agent.py (Priority: 122.33)
- core/embedding_service.py (Priority: 118.82)
- core/productivity/notion_service.py (Priority: 109.17)
- core/generic_agent.py (Priority: 109.07)
- core/atom_saas_websocket.py (Priority: 108.03)
- core/hybrid_data_ingestion.py (Priority: 107.23)
- core/bulk_operations_processor.py (Priority: 77.70)
- core/integration_data_mapper.py (Priority: 71.35)
- core/cross_platform_correlation.py (Priority: 70.90)
- core/enhanced_execution_state_manager.py (Priority: 56.54)

### Phase 107: Frontend Components

**Files**: 1

- core/byok_endpoints.py (Priority: 37.55)

---

*Generated by prioritize_high_impact_files.py*
*Phase: 100-03*
*Timestamp: 2026-02-27T16:13:11+00:00Z*