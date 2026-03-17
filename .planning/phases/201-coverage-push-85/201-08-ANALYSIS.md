# Phase 201 Plan 08: Wave 2 Coverage Analysis
**Generated:** 2026-03-17
**Baseline:** Phase 200 (final_coverage.json)
**Wave 2:** Plans 201-02 through 201-07

## Executive Summary
- **Baseline Coverage:** 5.21% (4,684/72,885 lines)
- **Wave 2 Coverage:** 20.13% (18,476/74,018 lines)
- **Improvement:** +14.92 percentage points
- **Lines Added:** +13,792 lines covered
- **Files Measured:** 547

## Overall Assessment
❌ **COVERAGE BELOW TARGET:** 20.13% < 60% (Wave 2 expected: 50-60%)

**Recommendation:** Extend Wave 2 with additional high-impact modules

## Module-Level Breakdown
| Module | Coverage | Lines | Files | Gap to 75% |
|--------|----------|-------|-------|-----------|
| api | 31.8% | 4,851/15,240 | 141 | 43.2% |
| core | 23.7% | 13,217/55,809 | 382 | 51.3% |
| cli | 18.9% | 136/718 | 6 | 56.1% |
| tools | 12.1% | 272/2,251 | 18 | 62.9% |

## Top 10 Most Improved Files
| Rank | Coverage | File | Lines |
|------|----------|------|-------|
| 1 | 98.2% | core/models.py | 3,935 |
| 2 | 78.3% | api/sync_admin_routes.py | 157 |
| 3 | 70.2% | api/admin/business_facts_routes.py | 149 |
| 4 | 64.2% | core/structured_logger.py | 92 |
| 5 | 60.3% | api/financial_ops_routes.py | 68 |
| 6 | 56.2% | core/config.py | 336 |
| 7 | 53.8% | api/canvas_orchestration_routes.py | 68 |
| 8 | 53.3% | api/social_routes.py | 90 |
| 9 | 52.5% | core/llm_usage_tracker.py | 53 |
| 10 | 51.6% | api/ab_testing.py | 79 |

## Files Still Below 50% Coverage (100+ lines)
| Coverage | File | Lines | Priority |
|----------|------|-------|----------|
| 0.0% | api/creative_routes.py | 157 | LOW |
| 0.0% | api/debug_routes.py | 296 | MEDIUM |
| 0.0% | api/productivity_routes.py | 156 | LOW |
| 0.0% | api/smarthome_routes.py | 188 | LOW |
| 0.0% | api/workflow_versioning_endpoints.py | 228 | MEDIUM |
| 0.0% | core/active_intervention_service.py | 112 | LOW |
| 0.0% | core/advanced_workflow_endpoints.py | 265 | MEDIUM |
| 0.0% | core/agent_execution_service.py | 134 | LOW |
| 0.0% | core/ai_workflow_optimization_endpoints.py | 137 | LOW |
| 0.0% | core/analytics_endpoints.py | 119 | LOW |
| 0.0% | core/analytics_engine.py | 130 | LOW |
| 0.0% | core/apar_engine.py | 177 | LOW |
| 0.0% | core/background_agent_runner.py | 121 | LOW |
| 0.0% | core/budget_enforcement_service.py | 151 | LOW |
| 0.0% | core/byok_competitive_endpoints.py | 137 | LOW |
| 0.0% | core/byok_cost_optimizer.py | 168 | LOW |
| 0.0% | core/chronological_integrity.py | 120 | LOW |
| 0.0% | core/communication_service.py | 145 | LOW |
| 0.0% | core/competitive_advantage_dashboard.py | 123 | LOW |
| 0.0% | core/constitutional_validator.py | 157 | LOW |
| 0.0% | core/database_helper.py | 102 | LOW |
| 0.0% | core/debug_alerting.py | 155 | LOW |
| 0.0% | core/debug_streaming.py | 123 | LOW |
| 0.0% | core/enterprise_user_management.py | 208 | MEDIUM |
| 0.0% | core/error_middleware.py | 137 | LOW |
| 0.0% | core/financial_audit_orchestrator.py | 112 | LOW |
| 0.0% | core/formula_memory.py | 147 | LOW |
| 0.0% | core/governance_helper.py | 130 | LOW |
| 0.0% | core/governance_wrapper.py | 111 | LOW |
| 0.0% | core/graduation_exam.py | 227 | MEDIUM |

## Zero Coverage Files (>100 lines)
Count: 47 files

| File | Lines |
|------|-------|
| core/workflow_versioning_system.py | 442 |
| core/workflow_marketplace.py | 332 |
| api/debug_routes.py | 296 |
| core/advanced_workflow_endpoints.py | 265 |
| core/workflow_template_endpoints.py | 243 |
| api/workflow_versioning_endpoints.py | 228 |
| core/graduation_exam.py | 227 |
| core/enterprise_user_management.py | 208 |
| api/smarthome_routes.py | 188 |
| core/industry_workflow_endpoints.py | 181 |
| core/apar_engine.py | 177 |
| core/byok_cost_optimizer.py | 168 |
| core/local_ocr_service.py | 164 |
| core/reconciliation_engine.py | 164 |
| api/creative_routes.py | 157 |
| core/constitutional_validator.py | 157 |
| api/productivity_routes.py | 156 |
| core/debug_alerting.py | 155 |
| core/budget_enforcement_service.py | 151 |
| core/logging_config.py | 148 |

## Gap Analysis to Targets
| Target | Current | Gap | Lines Needed |
|--------|---------|-----|-------------|
| 75% | 20.13% | 54.87% | 40,610 |
| 80% | 20.13% | 59.87% | 44,311 |
| 85% | 20.13% | 64.87% | 48,012 |

## Wave 3 Recommendation
**Current Coverage:** 20.13%
**Wave 2 Expected:** 50-60%
**Status:** ⚠️ Below target

### Recommendation: EXTEND WAVE 2
**Rationale:** Coverage below 50% threshold, need more high-impact tests before Wave 3.

**Next Steps:**
1. Target zero-coverage files >100 lines (easy wins)
2. Focus on core/ module (23.7% → 35%)
3. Add tests for API endpoints not yet covered
4. Prioritize files with 100-300 lines (medium complexity)
