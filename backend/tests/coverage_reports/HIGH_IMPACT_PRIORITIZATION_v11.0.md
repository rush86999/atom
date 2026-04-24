# High-Impact File Prioritization v11.0

**Generated**: 2026-04-24T17:33:32Z
**Phase**: 292-02
**Baseline**: {coverage_path.name}

## Executive Summary

- **Total files prioritized (>200 lines, <50% coverage)**: 83
- **Total uncovered lines**: 20,461

| Tier | Files | Definition |
|------|-------|------------|
| Tier 1 (must-fix) | 19 | < 10% coverage, > 200 lines (highest impact) |
| Tier 2 (should-fix) | 41 | 10-30% coverage, > 200 lines |
| Tier 3 (nice-to-fix) | 23 | 30-50% coverage, > 200 lines |

## Tier Definitions

| Tier | Coverage Range | Min Lines | Priority |
|------|---------------|-----------|----------|
| Tier 1 (must-fix) | < 10% | > 200 | Highest - maximize coverage gain per test |
| Tier 2 (should-fix) | 10-30% | > 200 | High - significant improvement possible |
| Tier 3 (nice-to-fix) | 30-50% | > 200 | Moderate - incremental gains |

## Tier 1 (must-fix): < 10% Coverage, > 200 Lines

**19 files** — 4,509 uncovered lines

| Rank | File | Coverage% | Uncovered | Impact | Priority Score | Business Tier |
|------|------|-----------|-----------|--------|----------------|---------------|
| 1 | core/workflow_analytics_endpoints.py | 0.00% | 314 | 5 | 1570.00 | Medium |
| 2 | core/workflow_parameter_validator.py | 0.00% | 286 | 5 | 1430.00 | Medium |
| 3 | api/workflow_versioning_endpoints.py | 0.00% | 228 | 5 | 1140.00 | Medium |
| 4 | core/learning_service_full.py | 0.00% | 367 | 3 | 1101.00 | Low |
| 5 | api/maturity_routes.py | 0.00% | 214 | 5 | 1070.00 | Medium |
| 6 | core/supervisor_learning_service.py | 0.00% | 212 | 5 | 1060.00 | Medium |
| 7 | api/mobile_agent_routes.py | 0.00% | 202 | 5 | 1010.00 | Medium |
| 8 | api/debug_routes.py | 0.00% | 296 | 3 | 888.00 | Low |
| 9 | core/llm/embedding/providers.py | 0.00% | 250 | 3 | 750.00 | Low |
| 10 | core/alert_service.py | 0.00% | 209 | 3 | 627.00 | Low |
| 11 | core/enhanced_learning_service.py | 0.00% | 208 | 3 | 624.00 | Low |
| 12 | core/feedback_service.py | 2.28% | 214 | 5 | 326.22 | Medium |
| 13 | api/user_templates_endpoints.py | 3.83% | 251 | 5 | 259.83 | Medium |
| 14 | core/custom_components_service.py | 4.02% | 215 | 5 | 214.14 | Medium |
| 15 | api/media_routes.py | 4.72% | 202 | 5 | 176.57 | Medium |
| 16 | api/learning_plan_routes.py | 5.19% | 201 | 5 | 162.36 | Medium |
| 17 | api/competitor_analysis_routes.py | 5.26% | 198 | 5 | 158.15 | Medium |
| 18 | tools/platform_management_tool.py | 7.62% | 206 | 3 | 71.69 | Low |
| 19 | core/integrations/adapters/airtable.py | 9.58% | 236 | 3 | 66.92 | Low |

## Tier 2 (should-fix): 10-30% Coverage, > 200 Lines

**41 files** — 10,972 uncovered lines

| Rank | File | Coverage% | Uncovered | Impact | Priority Score | Business Tier |
|------|------|-----------|-----------|--------|----------------|---------------|
| 1 | core/agent_world_model.py | 10.13% | 621 | 7 | 390.57 | High |
| 2 | core/proposal_service.py | 11.58% | 313 | 10 | 248.81 | Critical |
| 3 | core/hybrid_data_ingestion.py | 12.22% | 431 | 5 | 163.01 | Medium |
| 4 | core/workflow_engine.py | 27.97% | 878 | 5 | 151.54 | Medium |
| 5 | core/supervision_service.py | 12.39% | 191 | 10 | 142.64 | Critical |
| 6 | core/atom_meta_agent.py | 18.52% | 484 | 5 | 123.98 | Medium |
| 7 | core/lancedb_handler.py | 21.76% | 543 | 5 | 119.29 | Medium |
| 8 | core/episode_service.py | 14.37% | 441 | 3 | 86.08 | Low |
| 9 | core/generic_agent.py | 13.52% | 243 | 5 | 83.68 | Medium |
| 10 | core/productivity/notion_service.py | 13.72% | 239 | 5 | 81.18 | Medium |
| 11 | core/recording_review_service.py | 11.50% | 200 | 5 | 80.00 | Medium |
| 12 | core/formula_extractor.py | 16.61% | 261 | 5 | 74.11 | Medium |
| 13 | core/workflow_debugger.py | 26.19% | 389 | 5 | 71.53 | Medium |
| 14 | core/entity_type_service.py | 11.42% | 287 | 3 | 69.32 | Low |
| 15 | api/agent_governance_routes.py | 22.97% | 161 | 10 | 67.17 | Critical |
| 16 | core/graphrag_engine.py | 22.89% | 310 | 5 | 64.88 | Medium |
| 17 | core/fleet_orchestration/fleet_coordinator_service.py | 10.98% | 235 | 3 | 58.85 | Low |
| 18 | core/cross_platform_correlation.py | 17.25% | 211 | 5 | 57.81 | Medium |
| 19 | core/workflow_ui_endpoints.py | 20.39% | 242 | 5 | 56.57 | Medium |
| 20 | api/browser_routes.py | 29.36% | 166 | 10 | 54.68 | Critical |
| 21 | core/integrations/adapters/hubspot.py | 10.22% | 202 | 3 | 54.01 | Low |
| 22 | core/chat_session_manager.py | 17.32% | 191 | 5 | 52.13 | Medium |
| 23 | api/social_media_routes.py | 18.37% | 200 | 5 | 51.63 | Medium |
| 24 | core/integrations/adapters/jira.py | 10.53% | 187 | 3 | 48.66 | Low |
| 25 | core/ai_accounting_engine.py | 22.71% | 228 | 5 | 48.08 | Medium |
| 26 | core/llm/registry/service.py | 13.65% | 234 | 3 | 47.92 | Low |
| 27 | core/integration_data_mapper.py | 25.23% | 243 | 5 | 46.32 | Medium |
| 28 | core/budget_enforcement_service.py | 19.20% | 181 | 5 | 44.80 | Medium |
| 29 | core/enhanced_execution_state_manager.py | 23.84% | 214 | 5 | 43.08 | Medium |
| 30 | api/mobile_workflows.py | 19.00% | 162 | 5 | 40.50 | Medium |
| 31 | core/agents/skill_creation_agent.py | 13.02% | 187 | 3 | 40.01 | Low |
| 32 | core/circuit_breaker.py | 21.68% | 177 | 5 | 39.02 | Medium |
| 33 | core/debug_storage.py | 16.61% | 226 | 3 | 38.50 | Low |
| 34 | core/validation_service.py | 25.58% | 192 | 5 | 36.12 | Medium |
| 35 | core/atom_saas_client.py | 29.84% | 214 | 5 | 34.70 | Medium |
| 36 | core/cache.py | 29.83% | 207 | 5 | 33.57 | Medium |
| 37 | core/graduation_exam.py | 25.99% | 168 | 5 | 31.12 | Medium |
| 38 | core/ai_workflow_optimizer.py | 27.50% | 174 | 5 | 30.53 | Medium |
| 39 | api/menubar_routes.py | 27.27% | 160 | 5 | 28.30 | Medium |
| 40 | core/fleet_orchestration/fleet_scaler_service.py | 23.36% | 187 | 3 | 23.03 | Low |
| 41 | core/fleet_orchestration/scaling_proposal_service.py | 26.15% | 192 | 3 | 21.22 | Low |

## Tier 3 (nice-to-fix): 30-50% Coverage, > 200 Lines

**23 files** — 4,980 uncovered lines

| Rank | File | Coverage% | Uncovered | Impact | Priority Score | Business Tier |
|------|------|-----------|-----------|--------|----------------|---------------|
| 1 | core/llm/byok_handler.py | 46.58% | 406 | 10 | 85.33 | Critical |
| 2 | tools/canvas_tool.py | 33.56% | 291 | 10 | 84.20 | Critical |
| 3 | core/atom_agent_endpoints.py | 31.05% | 533 | 5 | 83.15 | Medium |
| 4 | core/advanced_workflow_system.py | 34.27% | 328 | 5 | 46.50 | Medium |
| 5 | core/auto_document_ingestion.py | 33.55% | 311 | 5 | 45.01 | Medium |
| 6 | core/agent_social_layer.py | 32.98% | 254 | 5 | 37.37 | Medium |
| 7 | core/llm_service.py | 44.86% | 161 | 10 | 35.11 | Critical |
| 8 | api/admin_routes.py | 35.03% | 243 | 5 | 33.72 | Medium |
| 9 | core/workflow_versioning_system.py | 39.59% | 267 | 5 | 32.89 | Medium |
| 10 | core/byok_endpoints.py | 43.88% | 289 | 5 | 32.20 | Medium |
| 11 | api/package_routes.py | 39.41% | 226 | 5 | 27.96 | Medium |
| 12 | core/enterprise_auth_service.py | 42.27% | 168 | 7 | 27.18 | High |
| 13 | core/workflow_endpoints.py | 30.61% | 170 | 5 | 26.89 | Medium |
| 14 | core/embedding_service.py | 34.35% | 151 | 5 | 21.36 | Medium |
| 15 | api/device_capabilities.py | 41.12% | 126 | 7 | 20.94 | High |
| 16 | api/integration_health_stubs.py | 36.17% | 150 | 5 | 20.18 | Medium |
| 17 | core/enterprise_user_management.py | 34.13% | 137 | 5 | 19.50 | Medium |
| 18 | core/workflow_template_endpoints.py | 39.92% | 146 | 5 | 17.84 | Medium |
| 19 | core/health_monitoring_service.py | 38.60% | 140 | 5 | 17.68 | Medium |
| 20 | api/workflow_debugging.py | 36.76% | 129 | 5 | 17.08 | Medium |

*Showing top 20 of 23 files*

## Priority Score Formula

```
priority_score = (uncovered_lines * impact_score) / (coverage_pct + 1)
```

### Why This Formula?

- **uncovered_lines**: More uncovered lines = more potential coverage gain
- **impact_score**: Higher business impact = more value per test
- **current_coverage_pct + 1**: Lower current coverage = higher priority
  - Adding 1 prevents division by zero for 0% coverage files
  - This creates a "quick wins" bias towards files with very low coverage

### Impact Score Mapping

| Business Tier | Score |
|---------------|-------|
| Critical | 10 |
| High | 7 |
| Medium | 5 |
| Low | 3 |

## Quick Wins (0% Coverage AND Critical/High Business Impact)

No files with 0% coverage AND Critical/High business impact found.

---

*Generated by coverage_to_prioritize.py*
*Phase: 292-02*
*Timestamp: 2026-04-24T17:33:32Z*