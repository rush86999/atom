# Phase 215: Fix Remaining A/B Test Failures - Research

## Problem Statement

After Phase 214 fixed the 404 routing errors, 10 A/B testing tests still fail due to:
1. **Database schema issue** (8 tests): Missing `diversity_profile` column in `agent_registry` table
2. **Test mocking gaps** (2 tests): `TestStartTest` fixtures don't mock service methods properly

## Failure Analysis

### Issue 1: Database Schema (8 TestCreateTest tests)

**Error**:
```
sqlalchemy.exc.OperationalError: no such column: agent_registry.diversity_profile
```

**Affected Tests**:
- test_create_test_success
- test_create_test_with_all_fields
- test_create_test_default_values
- test_create_test_prompt_type
- test_create_test_agent_config_type
- test_create_test_validation_error
- test_create_test_traffic_percentage_validation
- test_create_test_confidence_validation

**Root Cause**:
The `ABTestingService.create_test()` method queries the database to verify the agent exists:
```python
# core/ab_testing_service.py:84
agent = self.db.query(AgentRegistry).filter(
    AgentRegistry.id == agent_id
).first()
```

The `AgentRegistry` model has a `diversity_profile` field, but the test database doesn't have this column.

**Why Tests Hit Database**:
Tests mock `ABTestingService` but the mock returns a MagicMock, and when the service tries to query the database, it uses the REAL database session, not a mock.

### Issue 2: Test Mocking Gaps (2 TestStartTest tests)

**Error**:
```
WARNING: API Error: AB_TEST_ERROR - Test 'test-123' not found
Expected: 200
Actual: 400 Bad Request
```

**Affected Tests**:
- test_start_test_success
- test_start_test_includes_timestamp

**Root Cause**:
The test mocks `ABTestingService` but doesn't mock the `start_test()` method. When the endpoint calls `service.start_test(test_id)`, it uses the real service which queries the database and doesn't find the test.

**Test Code** (line 289):
```python
def test_start_test_success(self, client):
    with patch('core.ab_testing_service.ABTestingService') as MockService:
        mock_service = MagicMock()
        MockService.return_value = mock_service

        # Missing: mock_service.start_test.return_value = {...}
        # So when endpoint calls service.start_test(), it fails
```

## Solution Options

### Option 1: Fix Database Schema (Run Migrations)

**Approach**:
```bash
alembic upgrade head
```

**Pros**:
- Fixes the root cause
- All tests benefit from correct schema
- Production-ready approach

**Cons**:
- Requires migration to exist
- May fail if migration has issues
- Could affect other tests

**Risk**: Medium

### Option 2: Mock AgentRegistry Query (Service Layer)

**Approach**: Mock the database query in ABTestingService

**Pros**:
- No database changes needed
- Isolated to A/B testing tests
- Fast and safe

**Cons**:
- Requires modifying service code or test setup
- Doesn't fix underlying schema issue
- More complex mocking

**Risk**: Low

### Option 3: Mock Complete ABTestingService Methods (Recommended)

**Approach**: In test fixtures, properly mock all service methods that endpoints call

**For TestCreateTest**:
```python
mock_service.create_test.return_value = {...}  # Already done ✅
# Also need to mock agent query:
mock_service.db.query.return_value.filter.return_value.first.return_value = AgentRegistry(
    id="agent-1",
    name="Test Agent",
    ...
)
```

**For TestStartTest**:
```python
mock_service.start_test.return_value = {  # Add this! ❌
    "test_id": "test-123",
    "status": "running",
    "started_at": "2026-03-19T20:00:00Z"
}
```

**Pros**:
- No database changes needed
- Tests are properly isolated
- Follows unit testing best practices
- Fast execution

**Cons**:
- More verbose test fixtures
- Requires understanding of service internals

**Risk**: Low

**Recommendation**: Option 3 — Properly mock service methods in test fixtures

## Test File Analysis

### TestCreateTest Fixtures (8 failures)

**Current Mocking**:
```python
with patch('core.ab_testing_service.ABTestingService') as MockService:
    mock_service = MagicMock()
    MockService.return_value = mock_service

    mock_service.create_test.return_value = {...}  # ✅ Mocked
    # ❌ Missing: mock_service.db.query(...) for agent lookup
```

**What's Missing**:
When `create_test()` is called, the service verifies the agent exists:
```python
agent = self.db.query(AgentRegistry).filter(...).first()
if not agent:
    raise ValueError(f"Agent {agent_id} not found")
```

The mock needs to provide this agent lookup.

### TestStartTest Fixtures (2 failures)

**Current Mocking**:
```python
with patch('core.ab_testing_service.ABTestingService') as MockService:
    mock_service = MagicMock()
    MockService.return_value = mock_service

    # ❌ Missing: mock_service.start_test.return_value
```

**What's Missing**:
The endpoint calls `service.start_test(test_id)` which needs to return:
```python
{
    "test_id": "test-123",
    "status": "running",
    "started_at": "2026-03-19T20:00:00.000000Z"
}
```

## Implementation Strategy

### Wave 1: Fix TestCreateTest Fixtures (8 tests)

For each fixture, add agent lookup mock:
```python
# Create mock agent
mock_agent = MagicMock()
mock_agent.id = "agent-1"
mock_agent.name = "Test Agent"
mock_agent.status = "active"
mock_agent.confidence_score = 0.8

# Mock database query
mock_service.db.query.return_value.filter.return_value.first.return_value = mock_agent
```

### Wave 2: Fix TestStartTest Fixtures (2 tests)

For each fixture, add start_test mock:
```python
mock_service.start_test.return_value = {
    "test_id": "test-123",
    "status": "running",
    "started_at": datetime(2026, 3, 19, 20, 0, 0).isoformat()
}
```

## Related Files

- `backend/tests/api/test_ab_testing_routes.py` — Test file to fix
- `backend/core/ab_testing_service.py` — Service being mocked (no changes)
- `backend/core/models.py` — AgentRegistry model (no changes)

## Test Count

- Total failing tests: 10
- TestCreateTest: 8 tests
- TestStartTest: 2 tests

## Impact

- **Scope**: Test fixtures only (no production code changes)
- **Risk**: Low (proper test isolation)
- **Coverage**: No change (tests already exist)
- **Time estimate**: 30-45 minutes

## Success Criteria

- [ ] All 10 A/B testing tests pass
- [ ] No database schema errors
- [ ] No "test not found" errors
- [ ] Tests remain fast (no real DB queries)
- [ ] No production code changes

## Next Steps

1. Update TestCreateTest fixtures with agent lookup mocks (8 fixtures)
2. Update TestStartTest fixtures with start_test mocks (2 fixtures)
3. Run full test suite to verify all 10 tests pass
4. Document the mocking pattern for future reference
