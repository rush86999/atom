# Phase 221: High-Impact Coverage Expansion (Zero → 40%)

**Status**: PENDING
**Priority**: HIGH (primary coverage goal)
**Estimated Time**: 12-16 hours (2-3 days)
**Depends On**: Phase 220 (assertion density improved)

---

## Goal

Add test coverage to 10 largest zero-coverage modules, achieving minimum 40% coverage on each file to boost overall coverage from 21.35% toward 50% target.

---

## Requirements

- **REQ-007**: Critical code paths must have test coverage
- **REQ-008**: Target highest-impact files first (max coverage gain per test)

---

## Gap Closure

Closes largest coverage gap from 21.35% toward 50% target:
- 10 largest zero-coverage modules identified
- Target: Achieve 40% coverage on each file
- Expected outcome: Overall coverage increases to ~30%+

---

## Current Coverage: 21.35%

**Target After Phase 221**: ~30%+ overall coverage

---

## Target Files (Zero Coverage → 40%)

### Priority 1: Core Services (highest impact)

1. **core/agent_coordination.py** (131 lines, 0%)
   - Multi-agent message routing
   - Coordination primitives
   - Test strategy: Unit tests for coordination logic

2. **core/agent_learning_enhanced.py** (118 lines, 0%)
   - Agent learning algorithms
   - Training logic
   - Test strategy: Unit tests for learning methods

3. **core/agent_request_manager.py** (130 lines, 0%)
   - Request lifecycle management
   - Queue handling
   - Test strategy: Unit tests for request flow

### Priority 2: API Routes (user-facing)

4. **core/ai_workflow_optimization_endpoints.py** (137 lines, 0%)
   - Workflow optimization API
   - Test strategy: Integration tests for endpoints

5. **core/analytics_endpoints.py** (119 lines, 0%)
   - Analytics data API
   - Test strategy: Integration tests for endpoints

6. **api/agent_guidance_routes.py** (171 lines, 0%)
   - Agent guidance API
   - Test strategy: Integration tests with mocked governance

7. **api/analytics_dashboard_routes.py** (114 lines, 0%)
   - Dashboard data API
   - Test strategy: Integration tests for data retrieval

8. **api/debug_routes.py** (296 lines, 0%)
   - Debug information API
   - Test strategy: Integration tests for debug endpoints

### Priority 3: Tools (user-facing functionality)

9. **tools/calendar_tool.py** (123 lines, 0%)
   - Calendar operations
   - Test strategy: Unit tests for calendar logic

10. **api/financial_audit_routes.py** (66 lines, 0%)
    - Financial audit API
    - Test strategy: Integration tests for audit endpoints

---

## Tasks

### Task 1: Setup coverage measurement baseline

**Actions**:
1. Generate detailed coverage report
   ```bash
   pytest tests/ --cov=core --cov=api --cov=tools --cov-report=term-missing --cov-report=json
   ```
2. Record baseline coverage for each target file
3. Create coverage tracking spreadsheet

**Expected Outcome**: Clear baseline metrics

---

### Task 2: Write tests for core/agent_coordination.py (40% coverage)

**File**: `core/agent_coordination.py` (131 lines)

**Test Strategy**:
- Unit tests for message routing logic
- Tests for coordination primitives
- Mock agent dependencies

**Test File**: `tests/unit/agent/test_agent_coordination.py`

**Coverage Target**: 40% (~53 lines)

**Actions**:
1. Create test file with fixtures
2. Test message routing (happy path + edge cases)
3. Test coordination state management
4. Verify coverage ≥40%

---

### Task 3: Write tests for core/agent_learning_enhanced.py (40% coverage)

**File**: `core/agent_learning_enhanced.py` (118 lines)

**Test Strategy**:
- Unit tests for learning algorithms
- Test training logic with mock data
- Mock LLM calls

**Test File**: `tests/unit/agent/test_agent_learning_enhanced.py`

**Coverage Target**: 40% (~47 lines)

**Actions**:
1. Create test file with learning fixtures
2. Test learning algorithm logic
3. Test training session management
4. Verify coverage ≥40%

---

### Task 4: Write tests for core/agent_request_manager.py (40% coverage)

**File**: `core/agent_request_manager.py` (130 lines)

**Test Strategy**:
- Unit tests for request lifecycle
- Test queue handling
- Mock request/response

**Test File**: `tests/unit/agent/test_agent_request_manager.py`

**Coverage Target**: 40% (~52 lines)

**Actions**:
1. Create test file with request fixtures
2. Test request queuing/dequeuing
3. Test request state transitions
4. Verify coverage ≥40%

---

### Task 5: Write tests for core/ai_workflow_optimization_endpoints.py (40% coverage)

**File**: `core/ai_workflow_optimization_endpoints.py` (137 lines)

**Test Strategy**:
- Integration tests for API endpoints
- Test with FastAPI TestClient
- Mock optimization service

**Test File**: `tests/integration/test_ai_workflow_optimization_endpoints.py`

**Coverage Target**: 40% (~55 lines)

**Actions**:
1. Create test file with TestClient fixture
2. Test GET/POST endpoints
3. Test response validation
4. Verify coverage ≥40%

---

### Task 6: Write tests for core/analytics_endpoints.py (40% coverage)

**File**: `core/analytics_endpoints.py` (119 lines)

**Test Strategy**:
- Integration tests for analytics API
- Test data aggregation
- Mock database queries

**Test File**: `tests/integration/test_analytics_endpoints.py`

**Coverage Target**: 40% (~48 lines)

**Actions**:
1. Create test file with TestClient
2. Test analytics endpoints
3. Test data aggregation logic
4. Verify coverage ≥40%

---

### Task 7: Write tests for api/agent_guidance_routes.py (40% coverage)

**File**: `api/agent_guidance_routes.py` (171 lines)

**Test Strategy**:
- Integration tests for guidance API
- Test with mocked governance
- Mock guidance service

**Test File**: `tests/integration/test_agent_guidance_routes.py`

**Coverage Target**: 40% (~68 lines)

**Actions**:
1. Create test file with TestClient
2. Test guidance endpoints
3. Test governance integration
4. Verify coverage ≥40%

---

### Task 8: Write tests for api/analytics_dashboard_routes.py (40% coverage)

**File**: `api/analytics_dashboard_routes.py` (114 lines)

**Test Strategy**:
- Integration tests for dashboard API
- Test data retrieval
- Mock dashboard service

**Test File**: `tests/integration/test_analytics_dashboard_routes.py`

**Coverage Target**: 40% (~46 lines)

**Actions**:
1. Create test file with TestClient
2. Test dashboard endpoints
3. Test data serialization
4. Verify coverage ≥40%

---

### Task 9: Write tests for api/debug_routes.py (40% coverage)

**File**: `api/debug_routes.py` (296 lines)

**Test Strategy**:
- Integration tests for debug API
- Test debug information retrieval
- Mock debug service

**Test File**: `tests/integration/test_debug_routes.py`

**Coverage Target**: 40% (~118 lines)

**Actions**:
1. Create test file with TestClient
2. Test debug endpoints
3. Test debug data formatting
4. Verify coverage ≥40%

---

### Task 10: Write tests for tools/calendar_tool.py (40% coverage)

**File**: `tools/calendar_tool.py` (123 lines)

**Test Strategy**:
- Unit tests for calendar operations
- Mock calendar API
- Test event CRUD

**Test File**: `tests/unit/tools/test_calendar_tool.py`

**Coverage Target**: 40% (~49 lines)

**Actions**:
1. Create test file with tool fixtures
2. Test calendar operations
3. Test error handling
4. Verify coverage ≥40%

---

### Task 11: Write tests for api/financial_audit_routes.py (40% coverage)

**File**: `api/financial_audit_routes.py` (66 lines)

**Test Strategy**:
- Integration tests for audit API
- Test audit log retrieval
- Mock audit service

**Test File**: `tests/integration/test_financial_audit_routes.py`

**Coverage Target**: 40% (~26 lines)

**Actions**:
1. Create test file with TestClient
2. Test audit endpoints
3. Test audit log queries
4. Verify coverage ≥40%

---

### Task 12: Verify overall coverage improvement

**Actions**:
1. Run full coverage report
   ```bash
   pytest tests/ --cov=core --cov=api --cov=tools --cov-report=term --cov-report=json
   ```
2. Confirm overall coverage increased from 21.35% to ~30%+
3. Verify each target file ≥40% coverage
4. Check for regressions (no existing coverage dropped)

**Expected Outcome**: Significant coverage improvement, all targets met

---

## Success Criteria

- [ ] All 10 target files achieve ≥40% coverage
- [ ] Overall coverage increased from 21.35% to ~30%+ (minimum 8-10 percentage point gain)
- [ ] All new tests pass reliably
- [ ] No regressions in existing test coverage
- [ ] Coverage trend shows positive trajectory

---

## Acceptance Tests

```bash
# Test 1: Verify all new tests pass
pytest tests/unit/agent/test_agent_*.py \
      tests/integration/test_*_endpoints.py \
      tests/unit/tools/test_calendar_tool.py \
      -v

# Expected: All new tests pass

# Test 2: Check coverage improvement
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=term | tail -5

# Expected: Overall coverage ≥30%

# Test 3: Verify individual file coverage
python3 -m coverage report --sort=cover | grep -E "agent_coordination|agent_learning|agent_request|workflow_optimization|analytics_endpoints|agent_guidance|analytics_dashboard|debug_routes|calendar_tool|financial_audit"

# Expected: All files ≥40%

# Test 4: Check no regressions
pytest tests/ -q --tb=no 2>&1 | tail -3

# Expected: Pass rate maintained ≥98%
```

---

## Notes

- This is the primary coverage expansion phase
- Focus is on highest-impact files (max coverage gain per test)
- Target is 40% per file (not 100%) to maximize coverage velocity
- After this phase, will be at ~30% overall, on trajectory to 50%
- Uses high-impact strategy: largest files + critical paths first
- Phase 222 can continue with medium-impact files if needed

---

*Created: 2026-03-21*
*Next Action: Run Task 1 after Phase 220 completes*
