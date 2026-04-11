# Coverage Gap Analysis - Phase 251
**Generated**: 2026-04-11T14:46:56+00:00Z**Baseline Coverage**: 5.5%**Target Coverage**: 70.0%**Gap to Close**: 64.5 percentage points**Files Below Target**: 473**Total Missing Lines**: 63067
## Business Impact Breakdown
### Critical Impact
- Files: 23
- Missing Lines: 4707
**Top 10 Critical Files:**
| File | Coverage | Missing | Priority |
|------|----------|---------|----------|
| `core/llm/byok_handler.py` | 0.0% | 762 lines | 7620.0 |
| `core/episode_segmentation_service.py` | 0.0% | 593 lines | 5930.0 |
| `core/proposal_service.py` | 0.0% | 354 lines | 3540.0 |
| `core/episode_retrieval_service.py` | 0.0% | 320 lines | 3200.0 |
| `core/llm_service.py` | 0.0% | 294 lines | 2940.0 |
| `core/governance_cache.py` | 0.0% | 278 lines | 2780.0 |
| `core/agent_graduation_service.py` | 0.0% | 232 lines | 2320.0 |
| `core/supervision_service.py` | 0.0% | 218 lines | 2180.0 |
| `core/student_training_service.py` | 0.0% | 193 lines | 1930.0 |
| `core/episode_lifecycle_service.py` | 0.0% | 177 lines | 1770.0 |

### High Impact
- Files: 33
- Missing Lines: 4874
**Top 10 High Files:**
| File | Coverage | Missing | Priority |
|------|----------|---------|----------|
| `core/agent_world_model.py` | 0.0% | 598 lines | 4186.0 |
| `core/skill_registry_service.py` | 0.0% | 370 lines | 2590.0 |
| `core/enterprise_auth_service.py` | 0.0% | 291 lines | 2037.0 |
| `core/llm/registry/service.py` | 0.0% | 271 lines | 1897.0 |
| `core/llm/embedding/providers.py` | 0.0% | 250 lines | 1750.0 |
| `core/skill_adapter.py` | 0.0% | 229 lines | 1603.0 |
| `core/enterprise_security.py` | 0.0% | 200 lines | 1400.0 |
| `core/auth.py` | 0.0% | 170 lines | 1190.0 |
| `core/npm_package_installer.py` | 0.0% | 169 lines | 1183.0 |
| `core/auth_helpers.py` | 0.0% | 142 lines | 994.0 |

### Medium Impact
- Files: 405
- Missing Lines: 52052
**Top 10 Medium Files:**
| File | Coverage | Missing | Priority |
|------|----------|---------|----------|
| `core/workflow_engine.py` | 0.0% | 1204 lines | 6020.0 |
| `core/atom_agent_endpoints.py` | 0.0% | 773 lines | 3865.0 |
| `core/lancedb_handler.py` | 0.0% | 694 lines | 3470.0 |
| `core/workflow_analytics_engine.py` | 0.0% | 595 lines | 2975.0 |
| `core/workflow_debugger.py` | 0.0% | 527 lines | 2635.0 |
| `core/byok_endpoints.py` | 0.0% | 511 lines | 2555.0 |
| `core/episode_service.py` | 0.0% | 504 lines | 2520.0 |
| `core/advanced_workflow_system.py` | 0.0% | 499 lines | 2495.0 |
| `core/hybrid_data_ingestion.py` | 0.0% | 491 lines | 2455.0 |
| `core/atom_meta_agent.py` | 0.0% | 489 lines | 2445.0 |

### Low Impact
- Files: 12
- Missing Lines: 1434
**Top 10 Low Files:**
| File | Coverage | Missing | Priority |
|------|----------|---------|----------|
| `core/config.py` | 0.0% | 337 lines | 1011.0 |
| `core/email_utils.py` | 0.0% | 156 lines | 468.0 |
| `core/agent_utils.py` | 0.0% | 150 lines | 450.0 |
| `core/ab_testing_service.py` | 0.0% | 148 lines | 444.0 |
| `core/logging_config.py` | 0.0% | 148 lines | 444.0 |
| `core/governance_config.py` | 0.0% | 135 lines | 405.0 |
| `core/governance_helper.py` | 0.0% | 130 lines | 390.0 |
| `core/database_helper.py` | 0.0% | 102 lines | 306.0 |
| `core/governance_helpers.py` | 0.0% | 48 lines | 144.0 |
| `core/decimal_utils.py` | 0.0% | 38 lines | 114.0 |

## Top 50 Files by Priority Score
| Rank | File | Coverage | Impact | Missing | Priority |
|------|------|----------|--------|---------|----------|
| 1 | `core/llm/byok_handler.py` | 0.0% | Critical | 762 | 7620.0 |
| 2 | `core/workflow_engine.py` | 0.0% | Medium | 1204 | 6020.0 |
| 3 | `core/episode_segmentation_service.py` | 0.0% | Critical | 593 | 5930.0 |
| 4 | `core/agent_world_model.py` | 0.0% | High | 598 | 4186.0 |
| 5 | `core/atom_agent_endpoints.py` | 0.0% | Medium | 773 | 3865.0 |
| 6 | `core/proposal_service.py` | 0.0% | Critical | 354 | 3540.0 |
| 7 | `core/lancedb_handler.py` | 0.0% | Medium | 694 | 3470.0 |
| 8 | `core/episode_retrieval_service.py` | 0.0% | Critical | 320 | 3200.0 |
| 9 | `core/workflow_analytics_engine.py` | 0.0% | Medium | 595 | 2975.0 |
| 10 | `core/llm_service.py` | 0.0% | Critical | 294 | 2940.0 |
| 11 | `core/governance_cache.py` | 0.0% | Critical | 278 | 2780.0 |
| 12 | `core/workflow_debugger.py` | 0.0% | Medium | 527 | 2635.0 |
| 13 | `core/skill_registry_service.py` | 0.0% | High | 370 | 2590.0 |
| 14 | `core/byok_endpoints.py` | 0.0% | Medium | 511 | 2555.0 |
| 15 | `core/episode_service.py` | 0.0% | Medium | 504 | 2520.0 |
| 16 | `core/advanced_workflow_system.py` | 0.0% | Medium | 499 | 2495.0 |
| 17 | `core/hybrid_data_ingestion.py` | 0.0% | Medium | 491 | 2455.0 |
| 18 | `core/atom_meta_agent.py` | 0.0% | Medium | 489 | 2445.0 |
| 19 | `core/auto_document_ingestion.py` | 0.0% | Medium | 468 | 2340.0 |
| 20 | `core/agent_graduation_service.py` | 0.0% | Critical | 232 | 2320.0 |
| 21 | `core/workflow_versioning_system.py` | 0.0% | Medium | 442 | 2210.0 |
| 22 | `core/supervision_service.py` | 0.0% | Critical | 218 | 2180.0 |
| 23 | `core/enterprise_auth_service.py` | 0.0% | High | 291 | 2037.0 |
| 24 | `core/graphrag_engine.py` | 0.0% | Medium | 402 | 2010.0 |
| 25 | `core/student_training_service.py` | 0.0% | Critical | 193 | 1930.0 |
| 26 | `core/llm/registry/service.py` | 0.0% | High | 271 | 1897.0 |
| 27 | `core/learning_service_full.py` | 0.0% | Medium | 367 | 1835.0 |
| 28 | `core/episode_lifecycle_service.py` | 0.0% | Critical | 177 | 1770.0 |
| 29 | `core/llm/embedding/providers.py` | 0.0% | High | 250 | 1750.0 |
| 30 | `core/workflow_template_system.py` | 0.0% | Medium | 350 | 1750.0 |
| 31 | `core/workflow_marketplace.py` | 0.0% | Medium | 332 | 1660.0 |
| 32 | `core/atom_saas_websocket.py` | 0.0% | Medium | 328 | 1640.0 |
| 33 | `core/integration_data_mapper.py` | 0.0% | Medium | 325 | 1625.0 |
| 34 | `core/service_factory.py` | 0.0% | Medium | 325 | 1625.0 |
| 35 | `core/entity_type_service.py` | 0.0% | Medium | 324 | 1620.0 |
| 36 | `core/skill_adapter.py` | 0.0% | High | 229 | 1603.0 |
| 37 | `core/agent_governance_service.py` | 0.0% | Critical | 158 | 1580.0 |
| 38 | `core/workflow_analytics_endpoints.py` | 0.0% | Medium | 314 | 1570.0 |
| 39 | `core/formula_extractor.py` | 0.0% | Medium | 313 | 1565.0 |
| 40 | `core/workflow_ui_endpoints.py` | 0.0% | Medium | 304 | 1520.0 |
| 41 | `core/ai_accounting_engine.py` | 0.0% | Medium | 295 | 1475.0 |
| 42 | `core/cache.py` | 0.0% | Medium | 294 | 1470.0 |
| 43 | `core/agent_integration_gateway.py` | 0.0% | Medium | 290 | 1450.0 |
| 44 | `core/jit_verification_cache.py` | 0.0% | Medium | 289 | 1445.0 |
| 45 | `core/bulk_operations_processor.py` | 0.0% | Medium | 288 | 1440.0 |
| 46 | `core/llm/cognitive_tier_service.py` | 0.0% | Critical | 143 | 1430.0 |
| 47 | `core/workflow_parameter_validator.py` | 0.0% | Medium | 286 | 1430.0 |
| 48 | `core/meta_agent_training_orchestrator.py` | 0.0% | Critical | 142 | 1420.0 |
| 49 | `core/enhanced_execution_state_manager.py` | 0.0% | Medium | 281 | 1405.0 |
| 50 | `core/generic_agent.py` | 0.0% | Medium | 281 | 1405.0 |
