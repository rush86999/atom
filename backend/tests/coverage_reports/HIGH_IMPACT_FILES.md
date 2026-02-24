# High-Impact Files for Test Coverage Expansion v3.2

**Generated**: 2026-02-24 07:09:00 UTC
**Phase**: 81-02

## Summary

- **Total high-impact files identified**: 49
- **Combined uncovered lines**: 14,511
- **Total lines of code**: 15,599
- **Average coverage**: 6.2%
- **Filter criteria**: >200 lines, <30% coverage

### Distribution by Priority Tier

| Tier | Files | Description |
|------|-------|-------------|
| P0 | 2 | Governance, safety, LLM integration |
| P1 | 5 | Memory system, tools, training |
| P2 | 3 | Supporting services, infrastructure |
| P3 | 39 | Utility code, low-risk modules |

### Top 5 Files by Priority Score

| Rank | File | Lines | Coverage | Uncovered | Criticality | Priority Score | Tier |
|------|------|-------|----------|-----------|-------------|----------------|------|
| 1 | core/workflow_engine.py | 1163 | 14.53% | 994 | 6 | 59.64 | P2 |
| 2 | core/episode_segmentation_service.py | 463 | 17.93% | 380 | 9 | 34.2 | P0 |
| 3 | core/proposal_service.py | 342 | 0.0% | 342 | 7 | 23.94 | P1 |
| 4 | core/lancedb_handler.py | 577 | 24.61% | 435 | 5 | 21.75 | P2 |
| 5 | core/supervision_service.py | 216 | 0.0% | 216 | 9 | 19.44 | P0 |

## Priority Tiers

| Tier | Criticality | Description |
|------|-------------|-------------|
| P0 | 9-10 | Governance, safety, LLM integration |
| P1 | 7-8 | Memory system, tools, training |
| P2 | 5-6 | Supporting services, infrastructure |
| P3 | 3-4 | Utility code, low-risk modules |

## Priority Ranking - All High-Impact Files

| Rank | File | Lines | Coverage | Uncovered | Criticality | Priority Score | Tier |
|------|------|-------|----------|-----------|-------------|----------------|------|
| 1 | core/workflow_engine.py | 1163 | 14.53% | 994 | 6 | 59.64 | P2 |
| 2 | core/episode_segmentation_service.py | 463 | 17.93% | 380 | 9 | 34.2 | P0 |
| 3 | core/proposal_service.py | 342 | 0.0% | 342 | 7 | 23.94 | P1 |
| 4 | core/lancedb_handler.py | 577 | 24.61% | 435 | 5 | 21.75 | P2 |
| 5 | core/supervision_service.py | 216 | 0.0% | 216 | 9 | 19.44 | P0 |
| 6 | tools/browser_tool.py | 299 | 12.71% | 261 | 7 | 18.27 | P1 |
| 7 | tools/device_tool.py | 280 | 12.86% | 244 | 7 | 17.08 | P1 |
| 8 | core/agent_graduation_service.py | 230 | 11.74% | 203 | 8 | 16.24 | P1 |
| 9 | core/episode_retrieval_service.py | 240 | 15.42% | 203 | 8 | 16.24 | P1 |
| 10 | core/embedding_service.py | 317 | 0.0% | 317 | 5 | 15.85 | P2 |
| 11 | core/auto_document_ingestion.py | 479 | 0.0% | 479 | 3 | 14.37 | P3 |
| 12 | core/workflow_versioning_system.py | 476 | 0.0% | 476 | 3 | 14.28 | P3 |
| 13 | core/advanced_workflow_system.py | 473 | 0.0% | 473 | 3 | 14.19 | P3 |
| 14 | core/workflow_debugger.py | 527 | 11.76% | 465 | 3 | 13.95 | P3 |
| 15 | core/workflow_marketplace.py | 354 | 0.0% | 354 | 3 | 10.62 | P3 |
| 16 | core/agent_social_layer.py | 376 | 10.11% | 338 | 3 | 10.14 | P3 |
| 17 | core/integration_data_mapper.py | 338 | 0.0% | 338 | 3 | 10.14 | P3 |
| 18 | core/workflow_analytics_endpoints.py | 333 | 0.0% | 333 | 3 | 9.99 | P3 |
| 19 | core/atom_meta_agent.py | 331 | 0.0% | 331 | 3 | 9.93 | P3 |
| 20 | core/hybrid_data_ingestion.py | 314 | 0.0% | 314 | 3 | 9.42 | P3 |
| 21 | core/formula_extractor.py | 313 | 0.0% | 313 | 3 | 9.39 | P3 |
| 22 | core/bulk_operations_processor.py | 292 | 0.0% | 292 | 3 | 8.76 | P3 |
| 23 | core/enhanced_execution_state_manager.py | 286 | 0.0% | 286 | 3 | 8.58 | P3 |
| 24 | core/workflow_parameter_validator.py | 282 | 0.0% | 282 | 3 | 8.46 | P3 |
| 25 | core/workflow_template_endpoints.py | 276 | 0.0% | 276 | 3 | 8.28 | P3 |
| 26 | core/advanced_workflow_endpoints.py | 275 | 0.0% | 275 | 3 | 8.25 | P3 |
| 27 | core/agent_integration_gateway.py | 290 | 5.86% | 273 | 3 | 8.19 | P3 |
| 28 | core/unified_message_processor.py | 272 | 0.0% | 272 | 3 | 8.16 | P3 |
| 29 | core/enterprise_auth_service.py | 268 | 0.0% | 268 | 3 | 8.04 | P3 |
| 30 | core/cross_platform_correlation.py | 265 | 0.0% | 265 | 3 | 7.95 | P3 |
| 31 | core/validation_service.py | 264 | 0.0% | 264 | 3 | 7.92 | P3 |
| 32 | core/ai_workflow_optimizer.py | 261 | 0.0% | 261 | 3 | 7.83 | P3 |
| 33 | core/collaboration_service.py | 291 | 11.0% | 259 | 3 | 7.77 | P3 |
| 34 | core/integration_dashboard.py | 252 | 0.0% | 252 | 3 | 7.56 | P3 |
| 35 | core/agent_world_model.py | 298 | 17.79% | 245 | 3 | 7.35 | P3 |
| 36 | core/generic_agent.py | 242 | 0.0% | 242 | 3 | 7.26 | P3 |
| 37 | core/graphrag_engine.py | 282 | 16.31% | 236 | 3 | 7.08 | P3 |
| 38 | core/predictive_insights.py | 231 | 0.0% | 231 | 3 | 6.93 | P3 |
| 39 | core/workflow_ui_endpoints.py | 312 | 27.88% | 225 | 3 | 6.75 | P3 |
| 40 | core/auto_invoicer.py | 224 | 0.0% | 224 | 3 | 6.72 | P3 |
| 41 | core/feedback_service.py | 219 | 0.0% | 219 | 3 | 6.57 | P3 |
| 42 | core/message_analytics_engine.py | 219 | 0.0% | 219 | 3 | 6.57 | P3 |
| 43 | core/enterprise_user_management.py | 213 | 0.0% | 213 | 3 | 6.39 | P3 |
| 44 | core/supervisor_learning_service.py | 212 | 0.0% | 212 | 3 | 6.36 | P3 |
| 45 | core/health_monitoring_service.py | 228 | 11.84% | 201 | 3 | 6.03 | P3 |
| 46 | core/custom_components_service.py | 215 | 15.35% | 182 | 3 | 5.46 | P3 |
| 47 | core/recording_review_service.py | 206 | 11.65% | 182 | 3 | 5.46 | P3 |
| 48 | core/workflow_endpoints.py | 269 | 32.71% | 181 | 3 | 5.43 | P3 |
| 49 | core/webhook_handlers.py | 214 | 22.9% | 165 | 3 | 4.95 | P3 |

## Recommendations

### Test Development Strategy

1. **Start with P0 files** (governance, LLM, episodes)
   - These represent core business functionality
   - Highest risk if bugs exist
   - Maximum impact on system reliability

2. **Target 80% coverage on P0 files before moving to P1**
   - Each 10% coverage improvement on P0 files = significant overall gain
   - Focus on critical paths first

3. **Use property-based tests for complex logic**
   - Hypothesis for edge case discovery
   - Especially useful for governance and LLM routing logic

4. **Prioritize by priority_score within each tier**
   - Higher score = more uncovered lines * business impact
   - Maximum coverage gain per test added

## Next Steps

1. **Phase 82: Core Services Unit Testing**
   - Focus on P0 tier files (governance, LLM, episodes)
   - Unit tests with >80% coverage target

2. **Phase 86: Property-Based Testing**
   - Hypothesis tests for complex business logic
   - Edge case discovery in governance and routing

3. **Continuous Tracking**
   - Re-run priority ranking after each phase
   - Track progress against baseline (15.23% overall)
   - Adjust strategy based on coverage improvements

---

*Generated by priority_ranking.py*
*Phase: 81-02*
*Timestamp: 2026-02-24T07:09:00.958839*