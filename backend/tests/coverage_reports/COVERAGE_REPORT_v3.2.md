# Coverage Report v3.2 - Baseline for Bug Finding & Coverage Expansion

**Generated:** 2026-04-27
**Phase:** 81-01

## Executive Summary

**Overall Coverage: 36.72%**

| Metric | Value |
|--------|-------|
| Lines Covered | 33,332 |
| Lines Missing | 57,438 |
| Total Lines | 90,770 |
| Coverage vs Baseline | +31.59% (+615.8% change) |
| Improvement Factor | 7.16x |

Coverage has **improved** by 31.59 percentage points since baseline (5.13%).

## Module Breakdown

| Module | Files | Lines | Covered | Coverage |
|--------|-------|-------|---------|----------|
| core | 527 | 72,233 | 27,786 | 38.47% |
| api | 147 | 16,047 | 4,449 | 27.72% |
| tools | 19 | 2,490 | 1,097 | 44.06% |

## Coverage Distribution

**Total Files Analyzed:** 684

- **0% coverage:** 144 files (21.1%)
- **1-20% coverage:** 116 files (17.0%)
- **21-50% coverage:** 236 files (34.5%)
- **51-70% coverage:** 95 files (13.9%)
- **71-90% coverage:** 58 files (8.5%)
- **90%+ coverage:** 35 files (5.1%)

## File-by-File Details (Top 50 by Uncovered Lines)

Sorted by number of uncovered lines (highest gap first).

| Rank | File | Total Lines | Covered | Coverage | Uncovered | Priority |
|------|------|-------------|---------|----------|-----------|----------|
| 1 | core/workflow_engine.py | 1219 | 341 | 27.97% | 878 | HIGH |
| 2 | core/agent_world_model.py | 691 | 70 | 10.13% | 621 | HIGH |
| 3 | core/lancedb_handler.py | 694 | 151 | 21.76% | 543 | HIGH |
| 4 | core/atom_agent_endpoints.py | 773 | 240 | 31.05% | 533 | MED |
| 5 | core/atom_meta_agent.py | 594 | 110 | 18.52% | 484 | HIGH |
| 6 | core/episode_service.py | 515 | 74 | 14.37% | 441 | HIGH |
| 7 | core/hybrid_data_ingestion.py | 491 | 60 | 12.22% | 431 | HIGH |
| 8 | core/llm/byok_handler.py | 760 | 354 | 46.58% | 406 | MED |
| 9 | core/workflow_debugger.py | 527 | 138 | 26.19% | 389 | HIGH |
| 10 | core/learning_service_full.py | 367 | 0 | 0.0% | 367 | HIGH |
| 11 | core/advanced_workflow_system.py | 499 | 171 | 34.27% | 328 | MED |
| 12 | core/workflow_analytics_endpoints.py | 314 | 0 | 0.0% | 314 | HIGH |
| 13 | core/proposal_service.py | 354 | 41 | 11.58% | 313 | HIGH |
| 14 | core/auto_document_ingestion.py | 468 | 157 | 33.55% | 311 | MED |
| 15 | core/graphrag_engine.py | 402 | 92 | 22.89% | 310 | HIGH |
| 16 | api/debug_routes.py | 296 | 0 | 0.0% | 296 | HIGH |
| 17 | tools/canvas_tool.py | 438 | 147 | 33.56% | 291 | MED |
| 18 | core/byok_endpoints.py | 515 | 226 | 43.88% | 289 | MED |
| 19 | core/entity_type_service.py | 324 | 37 | 11.42% | 287 | HIGH |
| 20 | core/workflow_parameter_validator.py | 286 | 0 | 0.0% | 286 | HIGH |
| 21 | core/workflow_versioning_system.py | 442 | 175 | 39.59% | 267 | MED |
| 22 | api/byok_routes.py | 539 | 276 | 51.21% | 263 | OK |
| 23 | core/formula_extractor.py | 313 | 52 | 16.61% | 261 | HIGH |
| 24 | core/agent_social_layer.py | 379 | 125 | 32.98% | 254 | MED |
| 25 | api/user_templates_endpoints.py | 261 | 10 | 3.83% | 251 | HIGH |
| 26 | core/llm/embedding/providers.py | 250 | 0 | 0.0% | 250 | HIGH |
| 27 | api/admin_routes.py | 374 | 131 | 35.03% | 243 | MED |
| 28 | core/generic_agent.py | 281 | 38 | 13.52% | 243 | HIGH |
| 29 | core/integration_data_mapper.py | 325 | 82 | 25.23% | 243 | HIGH |
| 30 | core/workflow_ui_endpoints.py | 304 | 62 | 20.39% | 242 | HIGH |
| 31 | core/productivity/notion_service.py | 277 | 38 | 13.72% | 239 | HIGH |
| 32 | core/integrations/adapters/airtable.py | 261 | 25 | 9.58% | 236 | HIGH |
| 33 | ...leet_orchestration/fleet_coordinator_service.py | 264 | 29 | 10.98% | 235 | HIGH |
| 34 | core/llm/registry/service.py | 271 | 37 | 13.65% | 234 | HIGH |
| 35 | api/workflow_versioning_endpoints.py | 228 | 0 | 0.0% | 228 | HIGH |
| 36 | core/ai_accounting_engine.py | 295 | 67 | 22.71% | 228 | HIGH |
| 37 | api/package_routes.py | 373 | 147 | 39.41% | 226 | MED |
| 38 | core/debug_storage.py | 271 | 45 | 16.61% | 226 | HIGH |
| 39 | core/custom_components_service.py | 224 | 9 | 4.02% | 215 | HIGH |
| 40 | api/maturity_routes.py | 214 | 0 | 0.0% | 214 | HIGH |
| 41 | core/atom_saas_client.py | 305 | 91 | 29.84% | 214 | HIGH |
| 42 | core/enhanced_execution_state_manager.py | 281 | 67 | 23.84% | 214 | HIGH |
| 43 | core/feedback_service.py | 219 | 5 | 2.28% | 214 | HIGH |
| 44 | core/supervisor_learning_service.py | 212 | 0 | 0.0% | 212 | HIGH |
| 45 | core/cross_platform_correlation.py | 255 | 44 | 17.25% | 211 | HIGH |
| 46 | core/alert_service.py | 209 | 0 | 0.0% | 209 | HIGH |
| 47 | core/enhanced_learning_service.py | 208 | 0 | 0.0% | 208 | HIGH |
| 48 | core/cache.py | 295 | 88 | 29.83% | 207 | HIGH |
| 49 | tools/platform_management_tool.py | 223 | 17 | 7.62% | 206 | HIGH |
| 50 | api/media_routes.py | 212 | 10 | 4.72% | 202 | HIGH |

## Priority Files for Testing

### High Priority (>200 lines, <30% coverage)

These files have significant code with minimal coverage - prioritize for testing:

- **core/workflow_engine.py**
  - 1,219 lines, 27.97% coverage
  - 878 uncovered lines

- **core/agent_world_model.py**
  - 691 lines, 10.13% coverage
  - 621 uncovered lines

- **core/lancedb_handler.py**
  - 694 lines, 21.76% coverage
  - 543 uncovered lines

- **core/atom_meta_agent.py**
  - 594 lines, 18.52% coverage
  - 484 uncovered lines

- **core/episode_service.py**
  - 515 lines, 14.37% coverage
  - 441 uncovered lines

- **core/hybrid_data_ingestion.py**
  - 491 lines, 12.22% coverage
  - 431 uncovered lines

- **core/workflow_debugger.py**
  - 527 lines, 26.19% coverage
  - 389 uncovered lines

- **core/learning_service_full.py**
  - 367 lines, 0.00% coverage
  - 367 uncovered lines

- **core/workflow_analytics_endpoints.py**
  - 314 lines, 0.00% coverage
  - 314 uncovered lines

- **core/proposal_service.py**
  - 354 lines, 11.58% coverage
  - 313 uncovered lines

- **core/graphrag_engine.py**
  - 402 lines, 22.89% coverage
  - 310 uncovered lines

- **api/debug_routes.py**
  - 296 lines, 0.00% coverage
  - 296 uncovered lines

- **core/entity_type_service.py**
  - 324 lines, 11.42% coverage
  - 287 uncovered lines

- **core/workflow_parameter_validator.py**
  - 286 lines, 0.00% coverage
  - 286 uncovered lines

- **core/formula_extractor.py**
  - 313 lines, 16.61% coverage
  - 261 uncovered lines

- **api/user_templates_endpoints.py**
  - 261 lines, 3.83% coverage
  - 251 uncovered lines

- **core/llm/embedding/providers.py**
  - 250 lines, 0.00% coverage
  - 250 uncovered lines

- **core/generic_agent.py**
  - 281 lines, 13.52% coverage
  - 243 uncovered lines

- **core/integration_data_mapper.py**
  - 325 lines, 25.23% coverage
  - 243 uncovered lines

- **core/workflow_ui_endpoints.py**
  - 304 lines, 20.39% coverage
  - 242 uncovered lines

## Data Sources

- **Coverage Report:** `tests/coverage_reports/metrics/coverage.json`
- **HTML Report:** `tests/coverage_reports/html/index.html`
- **Test Execution:** pytest with pytest-cov

---

**Report Generated:** 2026-04-27T07:52:45.233383
**Phase:** 81-01 (Coverage Analysis & Prioritization)
