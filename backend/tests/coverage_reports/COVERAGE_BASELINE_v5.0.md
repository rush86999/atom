# Coverage Baseline Report v5.0
**Generated:** 2026-02-27T16:12:53+00:00Z UTC
**Purpose:** Establish baseline for v5.0 coverage expansion

---
## Executive Summary
- **Overall Coverage:** 21.67% (18,552 / 69,417 lines)
- **Coverage Gap:** 50,865 lines below 80%
- **Files Below 80%:** 499
- **Files Below 50%:** 453
- **Files Below 20%:** 266

## Module Breakdown
| Module | Coverage | Lines | Status |
|--------|----------|-------|--------|
| Core | 24.28% | 12,476/51,388 | ⚠️ |
| Api | 36.38% | 5,810/15,971 | ⚠️ |
| Tools | 12.93% | 266/2,058 | ⚠️ |
| Other | 0.0% | 0/0 | ⚠️ |

## Coverage Distribution
| Range | File Count | Percentage |
|-------|------------|------------|
| 0-20% | 266 | 52.9% |
| 21-50% | 187 | 37.2% |
| 51-80% | 46 | 9.1% |
| 80%+ | 4 | 0.8% |

## Files Below 80% Coverage
**Total:** 499 files below threshold

### Top 50 Files by Uncovered Lines
| Rank | File | Coverage | Uncovered | Total |
|------|------|----------|-----------|-------|
| 1 | `core/workflow_engine.py` | 4.78% | 1089 | 1163 |
| 2 | `core/atom_agent_endpoints.py` | 9.06% | 680 | 774 |
| 3 | `core/lancedb_handler.py` | 11.51% | 609 | 709 |
| 4 | `core/llm/byok_handler.py` | 8.72% | 582 | 654 |
| 5 | `core/episode_segmentation_service.py` | 8.25% | 510 | 580 |
| 6 | `core/workflow_debugger.py` | 9.67% | 465 | 527 |
| 7 | `core/workflow_analytics_engine.py` | 27.77% | 408 | 593 |
| 8 | `core/auto_document_ingestion.py` | 14.06% | 392 | 480 |
| 9 | `tools/canvas_tool.py` | 3.8% | 385 | 406 |
| 10 | `core/advanced_workflow_system.py` | 18.21% | 378 | 512 |
| 11 | `core/workflow_versioning_system.py` | 16.56% | 376 | 476 |
| 12 | `core/agent_social_layer.py` | 7.34% | 338 | 376 |
| 13 | `core/skill_registry_service.py` | 7.19% | 331 | 365 |
| 14 | `core/proposal_service.py` | 7.64% | 309 | 342 |
| 15 | `core/byok_endpoints.py` | 38.01% | 293 | 498 |
| 16 | `core/atom_meta_agent.py` | 10.69% | 286 | 331 |
| 17 | `core/formula_extractor.py` | 7.03% | 281 | 313 |
| 18 | `core/embedding_service.py` | 10.74% | 279 | 321 |
| 19 | `core/atom_saas_websocket.py` | 11.82% | 277 | 327 |
| 20 | `core/agent_integration_gateway.py` | 4.52% | 273 | 290 |
| 21 | `core/episode_retrieval_service.py` | 9.03% | 271 | 313 |
| 22 | `core/hybrid_data_ingestion.py` | 11.31% | 264 | 314 |
| 23 | `tools/browser_tool.py` | 9.92% | 261 | 299 |
| 24 | `core/collaboration_service.py` | 9.22% | 259 | 291 |
| 25 | `core/integration_data_mapper.py` | 16.8% | 254 | 338 |
| 26 | `core/agent_world_model.py` | 14.02% | 245 | 298 |
| 27 | `core/workflow_analytics_endpoints.py` | 23.24% | 244 | 333 |
| 28 | `tools/device_tool.py` | 9.73% | 244 | 280 |
| 29 | `core/workflow_ui_endpoints.py` | 19.82% | 242 | 331 |
| 30 | `api/admin_routes.py` | 37.77% | 240 | 433 |
| 31 | `core/productivity/notion_service.py` | 9.9% | 238 | 276 |
| 32 | `core/bulk_operations_processor.py` | 14.25% | 237 | 292 |
| 33 | `core/workflow_parameter_validator.py` | 10.37% | 237 | 282 |
| 34 | `core/graphrag_engine.py` | 12.23% | 236 | 282 |
| 35 | `core/workflow_marketplace.py` | 30.61% | 232 | 354 |
| 36 | `api/package_routes.py` | 33.18% | 230 | 373 |
| 37 | `api/media_routes.py` | 4.0% | 220 | 230 |
| 38 | `core/enhanced_execution_state_manager.py` | 18.28% | 218 | 286 |
| 39 | `core/generic_agent.py` | 8.81% | 214 | 242 |
| 40 | `core/enterprise_user_management.py` | 0.0% | 213 | 213 |
| 41 | `core/cross_platform_correlation.py` | 13.88% | 211 | 265 |
| 42 | `core/governance_cache.py` | 20.78% | 210 | 278 |
| 43 | `api/agent_routes.py` | 23.61% | 208 | 297 |
| 44 | `api/smarthome_routes.py` | 0.0% | 205 | 205 |
| 45 | `core/auto_invoicer.py` | 6.29% | 204 | 224 |
| 46 | `core/enterprise_auth_service.py` | 19.54% | 204 | 268 |
| 47 | `core/agent_graduation_service.py` | 9.44% | 203 | 230 |
| 48 | `core/advanced_workflow_endpoints.py` | 23.2% | 201 | 275 |
| 49 | `core/health_monitoring_service.py` | 9.38% | 201 | 228 |
| 50 | `core/feedback_service.py` | 7.07% | 198 | 219 |

## Unified Platform Breakdown
| Platform | Coverage | Lines | Status |
|----------|----------|-------|--------|
| Python | 21.672427945477878% | 18,552/69,417 | ⚠️ |
| Javascript | 0.0% | 0/0 | ⚠️ |
| **Overall** | **26.73%** | **18,552/69,417** | **📊** |

---

**Report Version:** v5.0 Baseline
**Next Steps:** See Phases 101-110 for coverage expansion plans
