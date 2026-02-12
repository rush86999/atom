# Coverage Priority Analysis Report

**Generated:** 2026-02-12
**Current Coverage:** 16.06% (10,817 / 55,115 lines)
**Target Coverage:** 80%
**Gap:** 63.94% (44,298 lines needed)

---

## Executive Summary

The Atom platform currently has **16.06% code coverage**. To reach the **80% target**, we need to add **44,298 lines of coverage** across **core**, **api**, and **tools** modules.

**Key Finding:** The **core/** module has the largest coverage gap (34,016 uncovered lines) and should be the top priority.

---

## Coverage by Module

| Module | Files | Covered | Total | Percent | Missing |
|--------|-------|---------|-------|---------|---------|
| **core** | 275 | 6,785 | 40,801 | 16.6% | **34,016** |
| **api** | 115 | 3,930 | 12,977 | 30.3% | **9,047** |
| **tools** | 11 | 102 | 1,337 | 7.6% | **1,235** |

---

## HIGH PRIORITY: Core Module (34,016 uncovered lines)

### Top 20 Files Requiring Coverage

| Rank | File | Covered | Total | % | Missing |
|------|------|---------|-------|---|---------|
| 1 | **core/workflow_engine.py** | 74 | 1,163 | 6.4% | 1,089 |
| 2 | **core/atom_agent_endpoints.py** | 0 | 736 | 0.0% | 736 |
| 3 | **core/auto_document_ingestion.py** | 0 | 479 | 0.0% | 479 |
| 4 | **core/workflow_versioning_system.py** | 0 | 476 | 0.0% | 476 |
| 5 | **core/advanced_workflow_system.py** | 0 | 473 | 0.0% | 473 |
| 6 | **core/workflow_analytics_engine.py** | 128 | 593 | 21.6% | 465 |
| 7 | **core/workflow_debugger.py** | 62 | 527 | 11.8% | 465 |
| 8 | **core/lancedb_handler.py** | 106 | 494 | 21.5% | 388 |
| 9 | **tools/canvas_tool.py** | 0 | 379 | 0.0% | 379 |
| 10 | **core/episode_segmentation_service.py** | 58 | 422 | 13.7% | 364 |
| 11 | **core/workflow_marketplace.py** | 0 | 354 | 0.0% | 354 |
| 12 | **core/proposal_service.py** | 0 | 339 | 0.0% | 339 |
| 13 | **core/integration_data_mapper.py** | 0 | 338 | 0.0% | 338 |
| 14 | **core/workflow_analytics_endpoints.py** | 0 | 333 | 0.0% | 333 |
| 15 | **core/atom_meta_agent.py** | 0 | 331 | 0.0% | 331 |
| 16 | **core/hybrid_data_ingestion.py** | 0 | 314 | 0.0% | 314 |
| 17 | **core/formula_extractor.py** | 0 | 313 | 0.0% | 313 |
| 18 | **core/byok_endpoints.py** | 195 | 498 | 39.2% | 303 |
| 19 | **core/bulk_operations_processor.py** | 0 | 292 | 0.0% | 292 |
| 20 | **core/episode_retrieval_service.py** | 117 | 400 | 29.3% | 283 |

---

## Recommended Test Strategy

### Phase 1: Zero-Coverage Files (Immediate Impact)

**Total Files:** 15 files with 0% coverage
**Total Uncovered:** 4,783 lines

These files have ZERO coverage and should be tested first:

1. **core/atom_agent_endpoints.py** (736 lines) - Core agent chat/streaming endpoints
2. **core/auto_document_ingestion.py** (479 lines) - Document processing
3. **core/workflow_versioning_system.py** (476 lines) - Workflow versioning
4. **core/advanced_workflow_system.py** (473 lines) - Advanced workflows
5. **core/workflow_marketplace.py** (354 lines) - Workflow templates
6. **core/proposal_service.py** (339 lines) - Agent proposals
7. **core/integration_data_mapper.py** (338 lines) - Data mapping
8. **core/workflow_analytics_endpoints.py** (333 lines) - Analytics API
9. **core/atom_meta_agent.py** (331 lines) - Meta-agent system
10. **core/hybrid_data_ingestion.py** (314 lines) - Hybrid ingestion
11. **core/formula_extractor.py** (313 lines) - Formula parsing
12. **core/bulk_operations_processor.py** (292 lines) - Bulk operations
13. **tools/canvas_tool.py** (379 lines) - Canvas presentations

**Approach:** Create **unit tests** for each public function and class method. Focus on:
- Input validation
- Error handling
- Business logic paths
- Edge cases

**Expected Impact:** +4,783 lines coverage (~8.7% increase)

---

### Phase 2: Workflow System (Largest Single File)

**File:** `core/workflow_engine.py`
**Uncovered:** 1,089 lines (93.6% uncovered)

**What needs testing:**
- Workflow execution engine
- Step orchestration
- Error recovery
- Parallel execution
- Workflow state management

**Approach:**
1. Test workflow execution lifecycle
2. Test step dependencies
3. Test error handling and rollback
4. Test parallel execution
5. Test workflow persistence

**Expected Impact:** +1,089 lines coverage (~2% increase)

---

### Phase 3: LLM & BYOK Handlers

**Files:**
- `core/llm/byok_handler.py` (491 uncovered, 10.6% covered)
- `core/byok_endpoints.py` (303 uncovered, 39.2% covered)

**What needs testing:**
- Multi-provider routing (OpenAI, Anthropic, DeepSeek, Gemini)
- Token streaming
- Error handling
- Provider failover
- API key rotation

**Approach:**
- Mock external LLM API calls
- Test provider selection logic
- Test streaming responses
- Test error scenarios

**Expected Impact:** +794 lines coverage (~1.4% increase)

---

### Phase 4: Episodic Memory Services

**Files:**
- `core/episode_segmentation_service.py` (364 uncovered, 13.7% covered)
- `core/episode_retrieval_service.py` (283 uncovered, 29.3% covered)
- `core/episode_lifecycle_service.py` (not listed, check coverage)

**What needs testing:**
- Episode creation and segmentation
- Vector search and retrieval
- Episode lifecycle (decay, consolidation)
- LanceDB integration
- PostgreSQL operations

**Approach:**
- Integration tests with real database
- Test segmentation algorithms
- Test retrieval accuracy
- Test lifecycle management

**Expected Impact:** +650+ lines coverage (~1.2% increase)

---

### Phase 5: Analytics & Debugging

**Files:**
- `core/workflow_analytics_engine.py` (465 uncovered, 21.6% covered)
- `core/workflow_debugger.py` (465 uncovered, 11.8% covered)

**What needs testing:**
- Workflow execution analytics
- Performance tracking
- Debug breakpoints
- Execution tracing
- Error diagnosis

**Expected Impact:** +930 lines coverage (~1.7% increase)

---

### Phase 6: API Module Coverage (9,047 uncovered lines)

**Current:** 30.3% covered
**Target:** 80%+

**Focus Areas:**
- Authentication endpoints
- Canvas endpoints
- Browser automation endpoints
- Device capability endpoints
- Episode endpoints

**Approach:**
- Integration tests using FastAPI TestClient
- Test all HTTP methods (GET, POST, PUT, DELETE)
- Test authentication/authorization
- Test error responses

**Expected Impact:** +6,000+ lines coverage (~11% increase)

---

### Phase 7: Tools Module Coverage (1,235 uncovered lines)

**Current:** 7.6% covered
**Target:** 80%+

**Focus Areas:**
- `tools/canvas_tool.py` (379 uncovered)
- `tools/browser_tool.py` (check coverage)
- `tools/device_tool.py` (check coverage)

**Approach:**
- Test tool execution
- Test governance checks
- Test error handling
- Test external service mocking

**Expected Impact:** +1,000+ lines coverage (~1.8% increase)

---

## Summary: Path to 80%

| Phase | Focus | Lines Added | Cumulative % |
|-------|-------|-------------|--------------|
| Current | - | 10,817 | 16.1% |
| Phase 1 | Zero-coverage files | +4,783 | 24.8% |
| Phase 2 | Workflow engine | +1,089 | 26.8% |
| Phase 3 | LLM/BYOK handlers | +794 | 28.2% |
| Phase 4 | Episodic memory | +650 | 29.4% |
| Phase 5 | Analytics/debugging | +930 | 31.1% |
| Phase 6 | API module | +6,000 | 42.0% |
| Phase 7 | Tools module | +1,000 | 43.8% |
| **Remaining** | **Other core files** | **+20,000** | **80%** |

**Estimated Effort:**
- **Phase 1:** 40-60 hours (15 files, unit tests)
- **Phase 2:** 10-15 hours (1 complex file)
- **Phase 3:** 15-20 hours (2 files, mocking required)
- **Phase 4:** 20-25 hours (3 files, integration tests)
- **Phase 5:** 20-25 hours (2 files, analytics)
- **Phase 6:** 40-60 hours (115 API files)
- **Phase 7:** 15-20 hours (3 tool files)
- **Remaining:** 200-300 hours (all other files)

**Total Estimated Effort:** 360-465 hours to reach 80% coverage

---

## Quick Wins (First Week)

Start with these **5 zero-coverage files** for maximum impact:

1. **tools/canvas_tool.py** (379 lines) - Simple tool, clear test cases
2. **core/formula_extractor.py** (313 lines) - Self-contained logic
3. **core/bulk_operations_processor.py** (292 lines) - CRUD operations
4. **core/atom_meta_agent.py** (331 lines) - Meta-agent orchestration
5. **core/integration_data_mapper.py** (338 lines) - Data transformation

**Total:** 1,653 lines (~3% coverage increase)
**Estimated Time:** 20-30 hours

---

## Next Steps

1. **Run detailed HTML coverage report:**
   ```bash
   pytest tests/ --cov=. --cov-report=html
   open htmlcov/index.html
   ```

2. **Start with Phase 1 (Zero-coverage files)**
3. **Create unit test templates for common patterns:**
   - CRUD operations
   - API endpoints
   - Service classes
   - Utility functions

4. **Set up coverage quality gates in CI:**
   - Fail PR if coverage decreases
   - Require 20% coverage for new files
   - Track coverage trends over time
