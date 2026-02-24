# Coverage Report v3.2 - Baseline for Bug Finding & Coverage Expansion

**Generated:** 2026-02-24
**Phase:** 81-01

## Executive Summary

**Overall Coverage: 15.23%**

| Metric | Value |
|--------|-------|
| Lines Covered | 8,272 |
| Lines Missing | 37,094 |
| Total Lines | 45,366 |
| Coverage vs Baseline | +10.10% (+196.9% change) |
| Improvement Factor | 2.97x |

Coverage has **improved** by 10.10 percentage points since baseline (5.13%).

## Module Breakdown

| Module | Files | Lines | Covered | Coverage |
|--------|-------|-------|---------|----------|
| core | 301 | 43,980 | 7,996 | 18.18% |
| api | 0 | 0 | 0 | 0.00% |
| tools | 11 | 1,386 | 276 | 19.91% |

## Coverage Distribution

**Total Files Analyzed:** 312

- **0% coverage:** 181 files (58.0%)
- **1-20% coverage:** 39 files (12.5%)
- **21-50% coverage:** 65 files (20.8%)
- **51-70% coverage:** 22 files (7.1%)
- **71-90% coverage:** 3 files (1.0%)
- **90%+ coverage:** 2 files (0.6%)

## File-by-File Details (Top 50 by Uncovered Lines)

Sorted by number of uncovered lines (highest gap first).

| Rank | File | Total Lines | Covered | Coverage | Uncovered | Priority |
|------|------|-------------|---------|----------|-----------|----------|
| 1 | core/workflow_engine.py | 1163 | 169 | 14.53% | 994 | HIGH |
| 2 | core/atom_agent_endpoints.py | 774 | 262 | 33.85% | 512 | MED |
| 3 | core/auto_document_ingestion.py | 479 | 0 | 0.0% | 479 | HIGH |
| 4 | core/workflow_versioning_system.py | 476 | 0 | 0.0% | 476 | HIGH |
| 5 | core/advanced_workflow_system.py | 473 | 0 | 0.0% | 473 | HIGH |
| 6 | core/workflow_debugger.py | 527 | 62 | 11.76% | 465 | HIGH |
| 7 | core/lancedb_handler.py | 577 | 142 | 24.61% | 435 | HIGH |
| 8 | core/episode_segmentation_service.py | 463 | 83 | 17.93% | 380 | HIGH |
| 9 | core/workflow_marketplace.py | 354 | 0 | 0.0% | 354 | HIGH |
| 10 | core/llm/byok_handler.py | 549 | 207 | 37.7% | 342 | MED |
| 11 | core/proposal_service.py | 342 | 0 | 0.0% | 342 | HIGH |
| 12 | core/agent_social_layer.py | 376 | 38 | 10.11% | 338 | HIGH |
| 13 | core/integration_data_mapper.py | 338 | 0 | 0.0% | 338 | HIGH |
| 14 | core/workflow_analytics_endpoints.py | 333 | 0 | 0.0% | 333 | HIGH |
| 15 | core/atom_meta_agent.py | 331 | 0 | 0.0% | 331 | HIGH |
| 16 | core/embedding_service.py | 317 | 0 | 0.0% | 317 | HIGH |
| 17 | core/hybrid_data_ingestion.py | 314 | 0 | 0.0% | 314 | HIGH |
| 18 | core/formula_extractor.py | 313 | 0 | 0.0% | 313 | HIGH |
| 19 | core/bulk_operations_processor.py | 292 | 0 | 0.0% | 292 | HIGH |
| 20 | core/byok_endpoints.py | 498 | 210 | 42.17% | 288 | MED |
| 21 | core/enhanced_execution_state_manager.py | 286 | 0 | 0.0% | 286 | HIGH |
| 22 | core/workflow_parameter_validator.py | 282 | 0 | 0.0% | 282 | HIGH |
| 23 | core/workflow_template_endpoints.py | 276 | 0 | 0.0% | 276 | HIGH |
| 24 | core/advanced_workflow_endpoints.py | 275 | 0 | 0.0% | 275 | HIGH |
| 25 | core/agent_integration_gateway.py | 290 | 17 | 5.86% | 273 | HIGH |
| 26 | core/unified_message_processor.py | 272 | 0 | 0.0% | 272 | HIGH |
| 27 | core/enterprise_auth_service.py | 268 | 0 | 0.0% | 268 | HIGH |
| 28 | core/cross_platform_correlation.py | 265 | 0 | 0.0% | 265 | HIGH |
| 29 | core/validation_service.py | 264 | 0 | 0.0% | 264 | HIGH |
| 30 | core/ai_workflow_optimizer.py | 261 | 0 | 0.0% | 261 | HIGH |
| 31 | tools/browser_tool.py | 299 | 38 | 12.71% | 261 | HIGH |
| 32 | core/collaboration_service.py | 291 | 32 | 11.0% | 259 | HIGH |
| 33 | core/workflow_analytics_engine.py | 593 | 338 | 57.0% | 255 | OK |
| 34 | core/integration_dashboard.py | 252 | 0 | 0.0% | 252 | HIGH |
| 35 | core/agent_world_model.py | 298 | 53 | 17.79% | 245 | HIGH |
| 36 | tools/device_tool.py | 280 | 36 | 12.86% | 244 | HIGH |
| 37 | core/generic_agent.py | 242 | 0 | 0.0% | 242 | HIGH |
| 38 | core/graphrag_engine.py | 282 | 46 | 16.31% | 236 | HIGH |
| 39 | tools/canvas_tool.py | 406 | 173 | 42.61% | 233 | MED |
| 40 | core/predictive_insights.py | 231 | 0 | 0.0% | 231 | HIGH |
| 41 | core/workflow_ui_endpoints.py | 312 | 87 | 27.88% | 225 | HIGH |
| 42 | core/auto_invoicer.py | 224 | 0 | 0.0% | 224 | HIGH |
| 43 | core/feedback_service.py | 219 | 0 | 0.0% | 219 | HIGH |
| 44 | core/message_analytics_engine.py | 219 | 0 | 0.0% | 219 | HIGH |
| 45 | core/supervision_service.py | 216 | 0 | 0.0% | 216 | HIGH |
| 46 | core/enterprise_user_management.py | 213 | 0 | 0.0% | 213 | HIGH |
| 47 | core/supervisor_learning_service.py | 212 | 0 | 0.0% | 212 | HIGH |
| 48 | core/agent_graduation_service.py | 230 | 27 | 11.74% | 203 | HIGH |
| 49 | core/episode_retrieval_service.py | 240 | 37 | 15.42% | 203 | HIGH |
| 50 | core/health_monitoring_service.py | 228 | 27 | 11.84% | 201 | HIGH |

## Priority Files for Testing

### High Priority (>200 lines, <30% coverage)

These files have significant code with minimal coverage - prioritize for testing:

- **core/workflow_engine.py**
  - 1,163 lines, 14.53% coverage
  - 994 uncovered lines

- **core/auto_document_ingestion.py**
  - 479 lines, 0.00% coverage
  - 479 uncovered lines

- **core/workflow_versioning_system.py**
  - 476 lines, 0.00% coverage
  - 476 uncovered lines

- **core/advanced_workflow_system.py**
  - 473 lines, 0.00% coverage
  - 473 uncovered lines

- **core/workflow_debugger.py**
  - 527 lines, 11.76% coverage
  - 465 uncovered lines

- **core/lancedb_handler.py**
  - 577 lines, 24.61% coverage
  - 435 uncovered lines

- **core/episode_segmentation_service.py**
  - 463 lines, 17.93% coverage
  - 380 uncovered lines

- **core/workflow_marketplace.py**
  - 354 lines, 0.00% coverage
  - 354 uncovered lines

- **core/proposal_service.py**
  - 342 lines, 0.00% coverage
  - 342 uncovered lines

- **core/agent_social_layer.py**
  - 376 lines, 10.11% coverage
  - 338 uncovered lines

- **core/integration_data_mapper.py**
  - 338 lines, 0.00% coverage
  - 338 uncovered lines

- **core/workflow_analytics_endpoints.py**
  - 333 lines, 0.00% coverage
  - 333 uncovered lines

- **core/atom_meta_agent.py**
  - 331 lines, 0.00% coverage
  - 331 uncovered lines

- **core/embedding_service.py**
  - 317 lines, 0.00% coverage
  - 317 uncovered lines

- **core/hybrid_data_ingestion.py**
  - 314 lines, 0.00% coverage
  - 314 uncovered lines

- **core/formula_extractor.py**
  - 313 lines, 0.00% coverage
  - 313 uncovered lines

- **core/bulk_operations_processor.py**
  - 292 lines, 0.00% coverage
  - 292 uncovered lines

- **core/enhanced_execution_state_manager.py**
  - 286 lines, 0.00% coverage
  - 286 uncovered lines

- **core/workflow_parameter_validator.py**
  - 282 lines, 0.00% coverage
  - 282 uncovered lines

- **core/workflow_template_endpoints.py**
  - 276 lines, 0.00% coverage
  - 276 uncovered lines

## Data Sources

- **Coverage Report:** `tests/coverage_reports/metrics/coverage.json`
- **HTML Report:** `tests/coverage_reports/html/index.html`
- **Test Execution:** pytest with pytest-cov

---

**Report Generated:** 2026-02-24T07:03:23.852332
**Phase:** 81-01 (Coverage Analysis & Prioritization)
