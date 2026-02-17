# Baseline Coverage Report

**Generated:** 2026-02-17
**Phase:** 01-foundation-infrastructure
**Plan:** 01-baseline-coverage

## Executive Summary

**Overall Coverage: 5.13%**

| Metric | Value |
|--------|-------|
| Lines Covered | 2,901 |
| Lines Missing | 53,628 |
| Total Lines | 56,529 |
| Coverage Gap to 80% Goal | 74.87% |

This baseline report establishes the starting point for Atom's 80% test coverage initiative. The current coverage of 5.13% indicates significant opportunity for improvement across all modules.

## Module Breakdown

### By Top-Level Directory

| Module | Covered | Total | Coverage |
|--------|---------|-------|----------|
| core | 2,540 | 48,372 | 5.25% |
| api | 284 | 7,435 | 3.82% |
| tools | 77 | 722 | 10.67% |

### Coverage Distribution

- **0% Coverage:** 312 files (93% of total files)
- **1-20% Coverage:** 12 files (4%)
- **21-50% Coverage:** 6 files (2%)
- **51-70% Coverage:** 3 files (1%)
- **71-90% Coverage:** 2 files (1%)
- **90%+ Coverage:** 1 file (<1%)

## AI Component Gaps

### Critical AI Services (0% Coverage)

| Component | Missing Lines | Total Lines | Priority |
|-----------|---------------|-------------|----------|
| `trigger_interceptor` | 141 | 141 | HIGH |
| `byok_handler` | 549 | 549 | HIGH |
| `agent_graduation_service` | 183 | 183 | HIGH |
| `episode_retrieval_service` | 242 | 242 | HIGH |
| `episode_lifecycle_service` | 97 | 97 | HIGH |
| `student_training_service` | 193 | 193 | HIGH |
| `episode_segmentation_service` | 422 | 422 | HIGH |
| `atom_agent_endpoints` | 754 | 754 | HIGH |
| `supervision_service` | 218 | 218 | HIGH |

### Low Coverage AI Services (<20%)

| Component | Coverage | Covered | Total | Priority |
|-----------|----------|---------|-------|----------|
| `governance_cache` | 19.5% | 51 | 262 | MEDIUM |
| `agent_context_resolver` | 15.8% | 15 | 95 | HIGH |
| `agent_governance_service` | 15.8% | 28 | 177 | HIGH |

### Missing AI Components (Not Found in Coverage)

| Component | Priority |
|-----------|----------|
| `streaming_handler` | HIGH |
| `canvas_tool` | MEDIUM |
| `browser_tool` | MEDIUM |
| `device_tool` | MEDIUM |
| `agent_social_layer` | HIGH |
| `host_shell_service` | MEDIUM |
| `local_agent_service` | HIGH |

## Zero-Coverage Files

### Largest Zero-Coverage Files (>300 lines)

1. **core/workflow_engine.py** - 1,163 lines (Priority: CRITICAL)
2. **core/atom_agent_endpoints.py** - 754 lines (Priority: CRITICAL)
3. **core/workflow_analytics_engine.py** - 595 lines (Priority: HIGH)
4. **core/llm/byok_handler.py** - 549 lines (Priority: CRITICAL)
5. **core/workflow_debugger.py** - 527 lines (Priority: MEDIUM)
6. **core/byok_endpoints.py** - 498 lines (Priority: HIGH)
7. **core/lancedb_handler.py** - 494 lines (Priority: HIGH)
8. **core/auto_document_ingestion.py** - 479 lines (Priority: MEDIUM)
9. **core/workflow_versioning_system.py** - 477 lines (Priority: MEDIUM)
10. **core/advanced_workflow_system.py** - 473 lines (Priority: MEDIUM)

### API Routes with Zero Coverage

All API routes currently have 0% coverage:
- `api/agent_governance_routes.py` (232 lines)
- `api/agent_guidance_routes.py` (194 lines)
- `api/agent_routes.py` (247 lines)
- `api/browser_routes.py` (246 lines)
- `api/canvas_routes.py` (73 lines)
- `api/device_capabilities.py` (248 lines)
- `api/episode_routes.py` (150 lines)
- `api/feedback_enhanced.py` (167 lines)
- And 50+ more API route files

## Priority Gap List

### Top 20 Files by Uncovered Lines

| Rank | File | Missing Lines | Coverage |
|------|------|---------------|----------|
| 1 | core/workflow_engine.py | 1,163 | 0.0% |
| 2 | core/atom_agent_endpoints.py | 754 | 0.0% |
| 3 | core/workflow_analytics_engine.py | 595 | 0.0% |
| 4 | core/llm/byok_handler.py | 549 | 0.0% |
| 5 | core/workflow_debugger.py | 527 | 0.0% |
| 6 | core/byok_endpoints.py | 498 | 0.0% |
| 7 | core/lancedb_handler.py | 494 | 0.0% |
| 8 | core/auto_document_ingestion.py | 479 | 0.0% |
| 9 | core/workflow_versioning_system.py | 477 | 0.0% |
| 10 | core/advanced_workflow_system.py | 473 | 0.0% |
| 11 | core/episode_segmentation_service.py | 422 | 0.0% |
| 12 | core/workflow_template_system.py | 356 | 0.0% |
| 13 | core/workflow_marketplace.py | 354 | 0.0% |
| 14 | core/proposal_service.py | 339 | 0.0% |
| 15 | core/integration_data_mapper.py | 338 | 0.0% |
| 16 | core/config.py | 336 | 0.0% |
| 17 | core/workflow_analytics_endpoints.py | 333 | 0.0% |
| 18 | core/atom_meta_agent.py | 331 | 0.0% |
| 19 | core/hybrid_data_ingestion.py | 314 | 0.0% |
| 20 | core/formula_extractor.py | 313 | 0.0% |

## Recommendations for Phase 2 Planning

### 1. Focus on Critical AI Components First

**Highest Priority (Governance & Safety):**
- `agent_governance_service.py` (15.8% → target 80%)
- `trigger_interceptor.py` (0% → target 80%)
- `governance_cache.py` (19.5% → target 80%)
- `agent_context_resolver.py` (15.8% → target 80%)

**Rationale:** These services control agent execution permissions and maturity routing. Zero coverage here means untested safety rails.

### 2. Prioritize LLM Integration Points

**Critical LLM Services:**
- `core/llm/byok_handler.py` (0% coverage, 549 lines)
- `core/atom_agent_endpoints.py` (0% coverage, 754 lines)

**Rationale:** LLM integration is central to Atom functionality. Untested LLM handlers risk:
- Incorrect provider routing (OpenAI vs Anthropic vs DeepSeek)
- Token streaming failures
- Cost calculation errors
- Rate limit violations

### 3. Episodic Memory System Coverage

**All Memory Services at 0%:**
- `episode_segmentation_service.py` (422 lines)
- `episode_retrieval_service.py` (242 lines)
- `episode_lifecycle_service.py` (97 lines)
- `agent_graduation_service.py` (183 lines)

**Rationale:** Episodic memory is the foundation of agent learning. Untested memory services risk:
- Data corruption in episode storage
- Incorrect retrieval semantics
- Graduation logic errors

### 4. Tools Layer Coverage

**Current State:** 10.67% coverage (best of all modules)

**Target Tools:**
- `tools/canvas_tool.py` (0% coverage expected)
- `tools/browser_tool.py` (0% coverage expected)
- `tools/device_tool.py` (0% coverage expected)

**Rationale:** Tools execute real-world actions (browser automation, device access). Zero coverage here is unacceptable for production safety.

### 5. API Routes Integration Testing

**Current State:** 0% across all API routes

**Recommendation:** Create integration tests for API endpoints using FastAPI TestClient. Focus on:
- Governance enforcement (maturity checks)
- Error handling (400, 401, 403, 404, 500)
- Input validation (Pydantic models)
- Response format consistency

## Coverage Targets by Phase

### Phase 2: Foundation Infrastructure (Target: 15-20%)
- Governance services: 80% coverage
- LLM handlers: 60% coverage
- Memory services: 50% coverage
- API routes: 20% coverage

### Phase 3: Core Property Tests (Target: 25-30%)
- Property-based tests for governance invariants
- Property-based tests for LLM cost calculations
- Property-based tests for episodic memory retrieval

### Phase 4: Platform Coverage (Target: 40-50%)
- Tools layer: 70% coverage
- API routes: 50% coverage
- Integration tests: 40% coverage

### Phase 5: Coverage Quality Validation (Target: 60-70%)
- Security-sensitive code: 90% coverage
- Financial operations: 95% coverage
- State management: 80% coverage

### Phase 8+: 80% Coverage Push (Target: 80%+)
- All modules: 80% minimum coverage
- Critical paths: 95% coverage
- Zero-coverage files eliminated

## Next Steps

1. **Immediate:** Create comprehensive test suite for `agent_governance_service.py` (Plan 02)
2. **This Week:** Implement coverage for `trigger_interceptor.py` and `governance_cache.py`
3. **This Month:** Achieve 20% overall coverage (4x improvement from baseline)
4. **This Quarter:** Achieve 50% overall coverage (10x improvement from baseline)

## Data Sources

- **Coverage Report:** `tests/coverage_reports/metrics/coverage.json`
- **HTML Report:** `tests/coverage_reports/html/index.html`
- **Trending Data:** `tests/coverage_reports/trending.json`
- **Test Execution Log:** `tests/coverage_reports/baseline/coverage_run.log`

---

**Report Generated By:** Atom Test Coverage Initiative
**Last Updated:** 2026-02-17T05:00:00Z
