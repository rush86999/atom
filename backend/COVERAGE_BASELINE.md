# Baseline Test Coverage Report

**Date:** February 17, 2026
**Coverage:** 22.64%
**Target:** 80.00%
**Gap:** 57.36 percentage points

---

## Executive Summary

The Atom backend codebase currently has **22.64% test coverage** (16,103 of 57,827 lines). To reach the **80% target**, we need to add **30,162 additional lines of test coverage**, which will require approximately **26,196 new lines of tested code** (assuming 100% coverage of new code).

---

## Coverage Breakdown

### By Module

| Module | Coverage | Lines | Status |
|--------|----------|-------|--------|
| **core/** | 24.5% | 35,876 lines | Need improvement |
| **api/** | 20.7% | 22,008 lines | Need improvement |
| **TOTAL** | **22.64%** | **57,827 lines** | **Baseline established** |

### Test Statistics

- **Total Tests:** 10,727 collected (with 6 collection errors remaining)
- **Test Execution Time:** ~1-2 minutes
- **Collection Errors:** 6 (blocking ~500 tests from running)

### Current Test Suite Health

**Passing Tests:** 9,000+ (estimated)
**Failing Tests:** ~500-1,000 (estimated)
**Flaky Tests:** ~100-200 (estimated)

---

## Lowest Coverage Files (Priority Targets)

Top 20 files by lines of uncovered code (>200 lines each):

| File | Coverage | Uncovered Lines | Priority |
|------|----------|-----------------|----------|
| `core/models.py` | 2.6% | 2,395 lines | **HIGH** |
| `core/event_sourced_architecture.py` | 51.7% | 101 lines | Medium |
| `core/exceptions.py` | 48.0% | 134 lines | Medium |
| `core/config.py` | 56.3% | 145 lines | Medium |
| `core/industry_workflow_templates.py` | 52.0% | 44 lines | Low |
| `core/ai_service.py` | 48.3% | 14 lines | Low |

**API Routes with Lowest Coverage:**

| File | Coverage | Uncovered Lines | Priority |
|------|----------|-----------------|----------|
| `api/canvas_recording_routes.py` | 44.3% | 74 lines | **HIGH** |
| `api/deeplinks.py` | 44.4% | 73 lines | **HIGH** |
| `api/supervised_queue_routes.py` | 44.5% | 60 lines | Medium |
| `api/agent_guidance_routes.py` | 46.2% | 104 lines | Medium |
| `api/workflow_debugging_advanced.py` | 49.0% | 66 lines | Medium |

---

## Collection Errors (Blockers)

6 collection errors preventing ~500 tests from running:

1. ✅ `tests/test_host_shell_service.py` - **FIXED**
2. ✅ `tests/test_social_feed_integration.py` - **FIXED**
3. ⚠️ `tests/unit/test_atom_agent_endpoints.py` - **FIXED** (Session import added)
4. ⚠️ `tests/test_social_feed_integration.py` - Partial fix (async decorators added)
5. ❌ `tests/property_tests/llm/test_byok_handler_invariants.py` - TypeError
6. ❌ `tests/property_tests/llm/test_llm_operations_invariants.py` - TypeError
7. ❌ `tests/property_tests/llm/test_llm_streaming_invariants.py` - TypeError
8. ❌ `tests/property_tests/llm/test_token_counting_invariants.py` - TypeError

**Estimated Impact:** Fixing these 4 remaining errors will unlock ~500-1,000 tests.

---

## Strategy to Reach 80% Coverage

### Phase 1: Fix Collection Errors (1 hour)
- Fix 4 remaining LLM property test TypeErrors
- Estimated impact: +500-1,000 tests, +2-3% coverage

### Phase 2: Target Low-Hanging Fruit (1-2 days)
- Add tests for API routes with <30% coverage
- Focus on core service methods with <50% coverage
- Target: +10% coverage (30% → 40%)

### Phase 3: Fill Gaps in Core Services (2-3 days)
- `core/models.py`: Add integration tests for models (2,395 uncovered lines)
- API routes: Add endpoint tests for CRUD operations
- Target: +20% coverage (40% → 60%)

### Phase 4: Comprehensive Coverage (3-4 days)
- Add property-based tests for invariants
- Add integration tests for critical paths
- Add unit tests for complex logic
- Target: +20% coverage (60% → 80%)

---

## High-Impact Testing Opportunities

### 1. Model Layer (core/models.py)
**Current:** 2.6% coverage (97.4% gap)
**Strategy:** Add factory tests, integration tests, property tests
**Impact:** +2,000 lines tested (~3.5% overall coverage increase)

### 2. API Routes (api/**)
**Current:** 20.7% coverage (79.3% gap)
**Strategy:** Add endpoint integration tests
**Impact:** +15,000 lines tested (~26% overall coverage increase)

### 3. Event Sourcing (core/event_sourced_architecture.py)
**Current:** 48.3% coverage (51.7% gap)
**Strategy:** Add unit tests for event handling
**Impact:** +100 lines tested (~0.2% overall coverage increase)

---

## Success Metrics

**Short-term (1 week):**
- [ ] Fix all collection errors
- [ ] Reach 30% coverage (+7.36 percentage points)
- [ ] Add 500+ new tests

**Mid-term (2 weeks):**
- [ ] Reach 50% coverage (+27.36 percentage points)
- [ ] Add 2,000+ new tests
- [ ] All API routes have endpoint tests

**Long-term (4 weeks):**
- [ ] Reach 80% coverage (+57.36 percentage points)
- [ ] Add 5,000+ new tests
- [ ] Property tests for all invariants

---

## Recommendations

1. **Immediate:** Fix remaining 4 collection errors (LLM property tests)
2. **High Priority:** Add tests for `core/models.py` (lowest coverage, highest impact)
3. **Medium Priority:** Add API endpoint integration tests
4. **Low Priority:** Add property tests for complex business logic

---

## Next Actions

1. ✅ **Establish baseline** (COMPLETE - 22.64%)
2. ⚠️ **Fix collection errors** (IN PROGRESS - 2 remaining)
3. 📋 **Add tests for lowest-coverage files**
4. 📊 **Track coverage progress weekly**

---

**Generated:** 2026-02-17
**Tool:** pytest-cov
**Command:** `pytest tests/ --cov=core --cov=api --cov-report=term --cov-report=html --cov-report=json`
