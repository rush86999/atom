# Phase 197 Plan 03: Complex Mocking Failure Analysis

**Date:** 2026-03-16
**Plan:** 197-03 - Resolve complex mocking challenges and integration test failures
**Status:** Analysis Complete - Ready for Fix Implementation

---

## Executive Summary

After database fixes from Plan 02, we identified **10 remaining collection errors** and analyzed the test suite for complex mocking challenges. The primary issues are:

1. **Factory Boy + SQLAlchemy 2.0 Incompatibility** (FIXED)
2. **Duplicate Table Definitions** (FIXED)
3. **Remaining Collection Errors** (10 total)
4. **Complex Mocking Scenarios** (identified in analysis)

### Quick Stats

- **Total Tests:** 5,566
- **Collection Errors:** 10 (0.18%)
- **Primary Fix:** Factory Boy Meta class configuration
- **Impact:** 6 test files can now be collected

---

## Fixes Applied (Rule 1 - Bug)

### Fix 1: Factory Boy Meta Class Configuration

**Issue:** Factory Boy 3.3.3 is incompatible with SQLAlchemy 2.0 models when subclassing factories without explicit Meta.model.

**Error:**
```
TypeError: issubclass() arg 1 must be a class
```

**Affected Files:**
- `tests/factories/agent_factory.py` (StudentAgentFactory, InternAgentFactory, SupervisedAgentFactory, AutonomousAgentFactory)

**Fix Applied:**
```python
class StudentAgentFactory(AgentFactory):
    """Factory for STUDENT maturity agents."""

    class Meta:
        model = AgentRegistry  # ← Added explicit Meta.model

    status = AgentStatus.STUDENT.value
    confidence_score = fuzzy.FuzzyFloat(0.0, 0.5)
```

**Impact:** 6 test files can now collect tests successfully

---

### Fix 2: Duplicate Table Definition

**Issue:** MarketingChannel model defined in both `core/models.py` and `marketing/models.py` causing SQLAlchemy table conflict.

**Error:**
```
sqlalchemy.exc.InvalidRequestError: Table 'marketing_channels' is already defined
for this MetaData instance. Specify 'extend_existing=True' to redefine options
and columns on an existing Table object.
```

**Fix Applied:**
```python
class MarketingChannel(Base):
    __tablename__ = "marketing_channels"
    __table_args__ = {'extend_existing': True}  # ← Added
```

**File:** `marketing/models.py`

---

## Remaining Collection Errors (10)

### Category A: Import/Module Errors (6 errors)

1. **tests/contract**
   - Error: `TypeError: There is no hook with name 'before_process_item'`
   - Type: Plugin configuration issue
   - Priority: Low (contract tests)

2. **tests/core/agents/test_atom_agent_endpoints_coverage.py**
   - Error: Import error (details hidden by pytest)
   - Type: Import chain issue
   - Priority: Medium

3. **tests/core/systems/test_embedding_service_coverage.py**
   - Error: Import error (details hidden by pytest)
   - Type: Import chain issue
   - Priority: Medium

4. **tests/core/systems/test_integration_data_mapper_coverage.py**
   - Error: Duplicate module (integration_data_mapper_coverage)
   - Type: File structure issue
   - Priority: Medium

### Category B: Missing Dependencies (4 errors)

5-8. **Various API tests** (hidden by pytest failure limit)
   - Type: Missing module imports
   - Priority: Low-Medium

---

## Complex Mocking Scenarios Identified

### Category 3.1: Async Test Patterns

**Status:** ✅ pytest-asyncio installed (1.3.0)
**Configuration:** AUTO mode enabled
**Issue Count:** ~5-10 tests affected

**Examples Found:**
- WebSocket connection tests
- LLM streaming tests
- Async agent execution tests

**Fix Strategy:**
1. Add `@pytest.mark.asyncio` decorators
2. Convert `def test_` to `async def test_`
3. Use `AsyncMock` for async dependencies
4. Add async fixtures to conftest.py

---

### Category 3.2: LLM Provider Mocks

**Status:** ⚠️ Complex streaming mocks needed
**Issue Count:** ~15-20 tests affected

**Mock Requirements:**
- Single-shot generation
- Token-by-token streaming
- Token counting accuracy
- Rate limiting enforcement
- Multi-provider support (OpenAI, Anthropic, DeepSeek)

**Reference Files:**
- `backend/core/llm/byok_handler.py`
- `backend/core/llm/cognitive_tier_system.py`

---

### Category 3.3: WebSocket Test Mocking

**Status:** ⚠️ WebSocket lifecycle mocks needed
**Issue Count:** ~10-15 tests affected

**Mock Requirements:**
- Connection establishment
- Message send/receive
- Connection close
- Error handling
- Connection manager

**Reference Files:**
- `backend/api/` (WebSocket routes)
- Tests needing `@pytest.mark.websocket`

---

### Category 3.4: Integration Test Boundaries

**Status:** ⚠️ Test isolation needed
**Issue Count:** ~20-30 tests affected

**Issues:**
- Cross-test state pollution
- Singleton reset needed
- Cache clearing between tests
- Global state (config, singletons)

**Fix Strategy:**
1. Mark integration tests with `@pytest.mark.integration`
2. Add isolation fixtures
3. Database rollback
4. Cache clearing
5. Run in isolation mode

---

## Test Execution Analysis

### Current Pass Rate

Based on test execution (limited collection due to errors):
- **Tests that can run:** ~5,500+
- **Estimated pass rate:** 70-75% (from Plan 02 baseline)
- **Target pass rate:** 97-99%

### Coverage Status

```
Coverage: 74.6% (baseline from Plan 02)
Target: 80% (by end of Phase 197)
```

---

## Priority Action Items

### Immediate (Task 2-4)

1. ✅ **Factory Boy Fix** (COMPLETED)
   - All agent factories now have explicit Meta.model
   - 6 test files can now collect

2. ✅ **Duplicate Table Fix** (COMPLETED)
   - MarketingChannel model with extend_existing=True

3. **Async Test Patterns** (Task 2)
   - Add @pytest.mark.asyncio decorators
   - Convert test functions to async
   - Create AsyncMock fixtures

4. **LLM Mocking** (Task 3)
   - Create comprehensive LLM mock fixtures
   - Mock streaming responses
   - Token counting tests

5. **WebSocket Mocking** (Task 4)
   - Create WebSocket mock fixtures
   - Connection lifecycle tests

### Secondary (Task 5-6)

6. **Integration Test Isolation** (Task 5)
   - Add isolation fixtures
   - Clear caches between tests
   - Mark integration tests

7. **Final Verification** (Task 6)
   - Run full test suite
   - Calculate pass rate
   - Document results

---

## Deviations from Plan

### Deviation 1: Factory Boy Incompatibility (Rule 1 - Bug)

**Found during:** Task 1 - Collection error analysis

**Issue:** Factory Boy 3.3.3 cannot handle SQLAlchemy 2.0 models when subclassing factories without explicit Meta.model attribute.

**Fix:** Added explicit `class Meta: model = AgentRegistry` to all subclassed factories.

**Files Modified:**
- `tests/factories/agent_factory.py`

**Impact:** 6 test files can now collect tests (was blocking test collection)

---

### Deviation 2: Duplicate Table Definition (Rule 1 - Bug)

**Found during:** Task 1 - Collection error analysis

**Issue:** MarketingChannel model defined in both `core/models.py` and `marketing/models.py` causing SQLAlchemy table conflict during import.

**Fix:** Added `__table_args__ = {'extend_existing': True}` to MarketingChannel in marketing/models.py

**Files Modified:**
- `marketing/models.py`

**Impact:** `test_operational_routes.py` can now collect

---

## Next Steps

1. **Commit fixes** (factory and model changes)
2. **Execute Task 2:** Fix async test patterns
3. **Execute Task 3:** Fix LLM mocking issues
4. **Execute Task 4:** Fix WebSocket test mocking
5. **Execute Task 5:** Fix integration test boundaries
6. **Execute Task 6:** Final mock verification

---

## Success Metrics

- [x] Factory Boy fixes applied (4 factories fixed)
- [x] Duplicate table definition fixed
- [x] pytest-asyncio verified installed
- [ ] Async test patterns implemented
- [ ] LLM mocks created
- [ ] WebSocket mocks created
- [ ] Integration tests isolated
- [ ] Pass rate reaches 97-99%

---

**Analysis Complete. Ready for Task 2: Fix async test patterns.**
