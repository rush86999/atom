# Coverage Gap Analysis - Phase 164
**Generated**: 2026-03-11T14:44:10+00:00Z**Baseline Coverage**: 7.92%**Target Coverage**: 80.0%**Gap to Close**: 72.08 percentage points**Files Below Target**: 520**Total Missing Lines**: 66747
## Business Impact Breakdown
### Critical Impact
- Files: 30
- Missing Lines: 5172
**Top 10 Critical Files:**
| File | Coverage | Missing | Priority |
|------|----------|---------|----------|
| `core/proposal_service.py` | 0.0% | 342 lines | 3420.0 |
| `tools/browser_tool.py` | 0.0% | 299 lines | 2990.0 |
| `core/agent_graduation_service.py` | 0.0% | 240 lines | 2400.0 |
| `api/browser_routes.py` | 0.0% | 235 lines | 2350.0 |
| `core/supervision_service.py` | 0.0% | 218 lines | 2180.0 |
| `api/agent_governance_routes.py` | 0.0% | 209 lines | 2090.0 |
| `api/cognitive_tier_routes.py` | 0.0% | 163 lines | 1630.0 |
| `core/constitutional_validator.py` | 0.0% | 157 lines | 1570.0 |
| `core/meta_agent_training_orchestrator.py` | 0.0% | 142 lines | 1420.0 |
| `core/llm/cognitive_tier_service.py` | 0.0% | 139 lines | 1390.0 |

### High Impact
- Files: 25
- Missing Lines: 3930
**Top 10 High Files:**
| File | Coverage | Missing | Priority |
|------|----------|---------|----------|
| `core/skill_registry_service.py` | 0.0% | 366 lines | 2562.0 |
| `core/agent_world_model.py` | 0.0% | 317 lines | 2219.0 |
| `tools/device_tool.py` | 0.0% | 308 lines | 2156.0 |
| `core/enterprise_auth_service.py` | 0.0% | 293 lines | 2051.0 |
| `core/skill_adapter.py` | 0.0% | 229 lines | 1603.0 |
| `api/device_capabilities.py` | 0.0% | 214 lines | 1498.0 |
| `core/enterprise_security.py` | 0.0% | 200 lines | 1400.0 |
| `api/enterprise_auth_endpoints.py` | 0.0% | 183 lines | 1281.0 |
| `api/oauth_routes.py` | 0.0% | 174 lines | 1218.0 |
| `core/npm_package_installer.py` | 0.0% | 169 lines | 1183.0 |

### Medium Impact
- Files: 452
- Missing Lines: 56134
**Top 10 Medium Files:**
| File | Coverage | Missing | Priority |
|------|----------|---------|----------|
| `core/workflow_engine.py` | 0.0% | 1163 lines | 5815.0 |
| `core/atom_agent_endpoints.py` | 0.0% | 787 lines | 3935.0 |
| `core/workflow_analytics_engine.py` | 0.0% | 561 lines | 2805.0 |
| `core/workflow_debugger.py` | 0.0% | 527 lines | 2635.0 |
| `core/advanced_workflow_system.py` | 0.0% | 495 lines | 2475.0 |
| `core/auto_document_ingestion.py` | 0.0% | 468 lines | 2340.0 |
| `core/workflow_versioning_system.py` | 0.0% | 442 lines | 2210.0 |
| `core/atom_meta_agent.py` | 0.0% | 422 lines | 2110.0 |
| `core/agent_social_layer.py` | 0.0% | 376 lines | 1880.0 |
| `api/admin_routes.py` | 0.0% | 374 lines | 1870.0 |

### Low Impact
- Files: 13
- Missing Lines: 1511
**Top 10 Low Files:**
| File | Coverage | Missing | Priority |
|------|----------|---------|----------|
| `core/config.py` | 0.0% | 336 lines | 1008.0 |
| `core/email_utils.py` | 0.0% | 156 lines | 468.0 |
| `core/agent_utils.py` | 0.0% | 150 lines | 450.0 |
| `core/ab_testing_service.py` | 0.0% | 148 lines | 444.0 |
| `core/logging_config.py` | 0.0% | 148 lines | 444.0 |
| `core/governance_config.py` | 0.0% | 135 lines | 405.0 |
| `core/governance_helper.py` | 0.0% | 130 lines | 390.0 |
| `core/database_helper.py` | 0.0% | 102 lines | 306.0 |
| `api/ab_testing.py` | 0.0% | 79 lines | 237.0 |
| `core/governance_helpers.py` | 0.0% | 47 lines | 141.0 |

## Top 50 Files by Priority Score
| Rank | File | Coverage | Impact | Missing | Priority |
|------|------|----------|--------|---------|----------|
| 1 | `core/workflow_engine.py` | 0.0% | Medium | 1163 | 5815.0 |
| 2 | `core/atom_agent_endpoints.py` | 0.0% | Medium | 787 | 3935.0 |
| 3 | `core/proposal_service.py` | 0.0% | Critical | 342 | 3420.0 |
| 4 | `tools/browser_tool.py` | 0.0% | Critical | 299 | 2990.0 |
| 5 | `core/workflow_analytics_engine.py` | 0.0% | Medium | 561 | 2805.0 |
| 6 | `core/workflow_debugger.py` | 0.0% | Medium | 527 | 2635.0 |
| 7 | `core/skill_registry_service.py` | 0.0% | High | 366 | 2562.0 |
| 8 | `core/advanced_workflow_system.py` | 0.0% | Medium | 495 | 2475.0 |
| 9 | `core/agent_graduation_service.py` | 0.0% | Critical | 240 | 2400.0 |
| 10 | `api/browser_routes.py` | 0.0% | Critical | 235 | 2350.0 |
| 11 | `core/auto_document_ingestion.py` | 0.0% | Medium | 468 | 2340.0 |
| 12 | `core/agent_world_model.py` | 0.0% | High | 317 | 2219.0 |
| 13 | `core/workflow_versioning_system.py` | 0.0% | Medium | 442 | 2210.0 |
| 14 | `core/supervision_service.py` | 0.0% | Critical | 218 | 2180.0 |
| 15 | `tools/device_tool.py` | 0.0% | High | 308 | 2156.0 |
| 16 | `core/atom_meta_agent.py` | 0.0% | Medium | 422 | 2110.0 |
| 17 | `api/agent_governance_routes.py` | 0.0% | Critical | 209 | 2090.0 |
| 18 | `core/enterprise_auth_service.py` | 0.0% | High | 293 | 2051.0 |
| 19 | `core/agent_social_layer.py` | 0.0% | Medium | 376 | 1880.0 |
| 20 | `api/admin_routes.py` | 0.0% | Medium | 374 | 1870.0 |
| 21 | `api/package_routes.py` | 0.0% | Medium | 373 | 1865.0 |
| 22 | `core/workflow_template_system.py` | 0.0% | Medium | 350 | 1750.0 |
| 23 | `core/workflow_marketplace.py` | 0.0% | Medium | 332 | 1660.0 |
| 24 | `core/atom_saas_websocket.py` | 0.0% | Medium | 328 | 1640.0 |
| 25 | `api/cognitive_tier_routes.py` | 0.0% | Critical | 163 | 1630.0 |
| 26 | `core/integration_data_mapper.py` | 0.0% | Medium | 325 | 1625.0 |
| 27 | `core/embedding_service.py` | 0.0% | Medium | 321 | 1605.0 |
| 28 | `core/skill_adapter.py` | 0.0% | High | 229 | 1603.0 |
| 29 | `core/constitutional_validator.py` | 0.0% | Critical | 157 | 1570.0 |
| 30 | `core/workflow_analytics_endpoints.py` | 0.0% | Medium | 314 | 1570.0 |
| 31 | `core/formula_extractor.py` | 0.0% | Medium | 313 | 1565.0 |
| 32 | `core/hybrid_data_ingestion.py` | 0.0% | Medium | 311 | 1555.0 |
| 33 | `core/workflow_ui_endpoints.py` | 0.0% | Medium | 304 | 1520.0 |
| 34 | `api/device_capabilities.py` | 0.0% | High | 214 | 1498.0 |
| 35 | `api/debug_routes.py` | 0.0% | Medium | 296 | 1480.0 |
| 36 | `core/ai_accounting_engine.py` | 0.0% | Medium | 295 | 1475.0 |
| 37 | `core/collaboration_service.py` | 0.0% | Medium | 291 | 1455.0 |
| 38 | `core/agent_integration_gateway.py` | 0.0% | Medium | 290 | 1450.0 |
| 39 | `core/bulk_operations_processor.py` | 0.0% | Medium | 288 | 1440.0 |
| 40 | `core/workflow_parameter_validator.py` | 0.0% | Medium | 286 | 1430.0 |
| 41 | `core/meta_agent_training_orchestrator.py` | 0.0% | Critical | 142 | 1420.0 |
| 42 | `api/agent_routes.py` | 0.0% | Medium | 283 | 1415.0 |
| 43 | `core/enhanced_execution_state_manager.py` | 0.0% | Medium | 281 | 1405.0 |
| 44 | `core/enterprise_security.py` | 0.0% | High | 200 | 1400.0 |
| 45 | `core/llm/cognitive_tier_service.py` | 0.0% | Critical | 139 | 1390.0 |
| 46 | `core/productivity/notion_service.py` | 0.0% | Medium | 277 | 1385.0 |
| 47 | `core/graphrag_engine.py` | 0.0% | Medium | 275 | 1375.0 |
| 48 | `core/local_llm_secrets_detector.py` | 0.0% | Critical | 137 | 1370.0 |
| 49 | `core/debug_storage.py` | 0.0% | Medium | 271 | 1355.0 |
| 50 | `core/unified_message_processor.py` | 0.0% | Medium | 267 | 1335.0 |
