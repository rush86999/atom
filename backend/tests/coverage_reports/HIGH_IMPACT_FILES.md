# High-Impact Files for Test Coverage Expansion v3.2

**Generated**: 2026-04-27 08:01:30 UTC
**Phase**: 81-02

## Summary

- **Total high-impact files identified**: 60
- **Combined uncovered lines**: 15,481
- **Total lines of code**: 18,267
- **Average coverage**: 13.9%
- **Filter criteria**: >200 lines, <30% coverage

### Distribution by Priority Tier

| Tier | Files | Description |
|------|-------|-------------|
| P0 | 3 | Governance, safety, LLM integration |
| P1 | 4 | Memory system, tools, training |
| P2 | 4 | Supporting services, infrastructure |
| P3 | 49 | Utility code, low-risk modules |

### Top 5 Files by Priority Score

| Rank | File | Lines | Coverage | Uncovered | Criticality | Priority Score | Tier |
|------|------|-------|----------|-----------|-------------|----------------|------|
| 1 | core/workflow_engine.py | 1219 | 27.97% | 878 | 6 | 52.68 | P2 |
| 2 | core/agent_world_model.py | 691 | 10.13% | 621 | 7 | 43.47 | P1 |
| 3 | core/episode_service.py | 515 | 14.37% | 441 | 8 | 35.28 | P1 |
| 4 | core/atom_meta_agent.py | 594 | 18.52% | 484 | 7 | 33.88 | P1 |
| 5 | core/lancedb_handler.py | 694 | 21.76% | 543 | 5 | 27.15 | P2 |

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
| 1 | core/workflow_engine.py | 1219 | 27.97% | 878 | 6 | 52.68 | P2 |
| 2 | core/agent_world_model.py | 691 | 10.13% | 621 | 7 | 43.47 | P1 |
| 3 | core/episode_service.py | 515 | 14.37% | 441 | 8 | 35.28 | P1 |
| 4 | core/atom_meta_agent.py | 594 | 18.52% | 484 | 7 | 33.88 | P1 |
| 5 | core/lancedb_handler.py | 694 | 21.76% | 543 | 5 | 27.15 | P2 |
| 6 | core/llm/registry/service.py | 271 | 13.65% | 234 | 10 | 23.4 | P0 |
| 7 | core/proposal_service.py | 354 | 11.58% | 313 | 7 | 21.91 | P1 |
| 8 | core/cache.py | 295 | 29.83% | 207 | 10 | 20.7 | P0 |
| 9 | core/graphrag_engine.py | 402 | 22.89% | 310 | 6 | 18.6 | P2 |
| 10 | core/entity_type_service.py | 324 | 11.42% | 287 | 6 | 17.22 | P2 |
| 11 | core/supervision_service.py | 218 | 12.39% | 191 | 9 | 17.19 | P0 |
| 12 | core/hybrid_data_ingestion.py | 491 | 12.22% | 431 | 3 | 12.93 | P3 |
| 13 | core/workflow_debugger.py | 527 | 26.19% | 389 | 3 | 11.67 | P3 |
| 14 | core/learning_service_full.py | 367 | 0.0% | 367 | 3 | 11.01 | P3 |
| 15 | core/workflow_analytics_endpoints.py | 314 | 0.0% | 314 | 3 | 9.42 | P3 |
| 16 | api/debug_routes.py | 296 | 0.0% | 296 | 3 | 8.88 | P3 |
| 17 | core/workflow_parameter_validator.py | 286 | 0.0% | 286 | 3 | 8.58 | P3 |
| 18 | core/formula_extractor.py | 313 | 16.61% | 261 | 3 | 7.83 | P3 |
| 19 | api/user_templates_endpoints.py | 261 | 3.83% | 251 | 3 | 7.53 | P3 |
| 20 | core/llm/embedding/providers.py | 250 | 0.0% | 250 | 3 | 7.5 | P3 |
| 21 | core/generic_agent.py | 281 | 13.52% | 243 | 3 | 7.29 | P3 |
| 22 | core/integration_data_mapper.py | 325 | 25.23% | 243 | 3 | 7.29 | P3 |
| 23 | core/workflow_ui_endpoints.py | 304 | 20.39% | 242 | 3 | 7.26 | P3 |
| 24 | core/productivity/notion_service.py | 277 | 13.72% | 239 | 3 | 7.17 | P3 |
| 25 | core/integrations/adapters/airtable.py | 261 | 9.58% | 236 | 3 | 7.08 | P3 |
| 26 | core/fleet_orchestration/fleet_coordinator_service.py | 264 | 10.98% | 235 | 3 | 7.05 | P3 |
| 27 | api/workflow_versioning_endpoints.py | 228 | 0.0% | 228 | 3 | 6.84 | P3 |
| 28 | core/ai_accounting_engine.py | 295 | 22.71% | 228 | 3 | 6.84 | P3 |
| 29 | core/debug_storage.py | 271 | 16.61% | 226 | 3 | 6.78 | P3 |
| 30 | core/custom_components_service.py | 224 | 4.02% | 215 | 3 | 6.45 | P3 |
| 31 | api/maturity_routes.py | 214 | 0.0% | 214 | 3 | 6.42 | P3 |
| 32 | core/atom_saas_client.py | 305 | 29.84% | 214 | 3 | 6.42 | P3 |
| 33 | core/enhanced_execution_state_manager.py | 281 | 23.84% | 214 | 3 | 6.42 | P3 |
| 34 | core/feedback_service.py | 219 | 2.28% | 214 | 3 | 6.42 | P3 |
| 35 | core/supervisor_learning_service.py | 212 | 0.0% | 212 | 3 | 6.36 | P3 |
| 36 | core/cross_platform_correlation.py | 255 | 17.25% | 211 | 3 | 6.33 | P3 |
| 37 | core/alert_service.py | 209 | 0.0% | 209 | 3 | 6.27 | P3 |
| 38 | core/enhanced_learning_service.py | 208 | 0.0% | 208 | 3 | 6.24 | P3 |
| 39 | tools/platform_management_tool.py | 223 | 7.62% | 206 | 3 | 6.18 | P3 |
| 40 | api/media_routes.py | 212 | 4.72% | 202 | 3 | 6.06 | P3 |
| 41 | api/mobile_agent_routes.py | 202 | 0.0% | 202 | 3 | 6.06 | P3 |
| 42 | core/integrations/adapters/hubspot.py | 225 | 10.22% | 202 | 3 | 6.06 | P3 |
| 43 | api/learning_plan_routes.py | 212 | 5.19% | 201 | 3 | 6.03 | P3 |
| 44 | api/social_media_routes.py | 245 | 18.37% | 200 | 3 | 6.0 | P3 |
| 45 | core/recording_review_service.py | 226 | 11.5% | 200 | 3 | 6.0 | P3 |
| 46 | api/competitor_analysis_routes.py | 209 | 5.26% | 198 | 3 | 5.94 | P3 |
| 47 | core/fleet_orchestration/scaling_proposal_service.py | 260 | 26.15% | 192 | 3 | 5.76 | P3 |
| 48 | core/validation_service.py | 258 | 25.58% | 192 | 3 | 5.76 | P3 |
| 49 | core/chat_session_manager.py | 231 | 17.32% | 191 | 3 | 5.73 | P3 |
| 50 | core/agents/skill_creation_agent.py | 215 | 13.02% | 187 | 3 | 5.61 | P3 |
| 51 | core/fleet_orchestration/fleet_scaler_service.py | 244 | 23.36% | 187 | 3 | 5.61 | P3 |
| 52 | core/integrations/adapters/jira.py | 209 | 10.53% | 187 | 3 | 5.61 | P3 |
| 53 | core/budget_enforcement_service.py | 224 | 19.2% | 181 | 3 | 5.43 | P3 |
| 54 | core/circuit_breaker.py | 226 | 21.68% | 177 | 3 | 5.31 | P3 |
| 55 | core/ai_workflow_optimizer.py | 240 | 27.5% | 174 | 3 | 5.22 | P3 |
| 56 | core/graduation_exam.py | 227 | 25.99% | 168 | 3 | 5.04 | P3 |
| 57 | api/browser_routes.py | 235 | 29.36% | 166 | 3 | 4.98 | P3 |
| 58 | api/mobile_workflows.py | 200 | 19.0% | 162 | 3 | 4.86 | P3 |
| 59 | api/agent_governance_routes.py | 209 | 22.97% | 161 | 3 | 4.83 | P3 |
| 60 | api/menubar_routes.py | 220 | 27.27% | 160 | 3 | 4.8 | P3 |

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
*Timestamp: 2026-04-27T08:01:30.559422*