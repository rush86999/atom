# API and Database Integration Tests

**Phase**: 03 - Integration & Security Tests
**Plan**: 01 - API and Database Integration Tests
**Status**: Pending
**Priority**: P0 (Critical)

## Objective

Build comprehensive integration tests for all FastAPI endpoints using TestClient, ensuring request/response validation, error handling, and database transaction rollback patterns.

## Success Criteria

1. All FastAPI endpoints have integration tests using TestClient
2. Request/response validation is tested for all endpoints
3. Error handling is tested for all error conditions
4. Database integration tests use transaction rollback (no committed test data)
5. Tests cover both success and failure paths
6. At least 30% increase in overall code coverage

## Current State

- **Coverage**: 16.06% overall
- **FastAPI Endpoints**: ~100+ endpoints across multiple route files
- **Test Infrastructure**: Phase 1 complete (pytest, TestClient available)
- **Database Models**: SQLAlchemy 2.0 with async support

## Key Areas to Cover

### API Route Files
- `backend/core/atom_agent_endpoints.py` - Chat/streaming endpoints
- `backend/api/canvas_routes.py` - Canvas presentation endpoints
- `backend/api/browser_routes.py` - Browser automation endpoints
- `backend/api/device_capabilities.py` - Device capability endpoints
- `backend/api/maturity_routes.py` - Agent maturity and training endpoints
- `backend/api/episode_routes.py` - Episodic memory endpoints
- `backend/api/feedback_enhanced.py` - Feedback endpoints
- `backend/api/ab_testing.py` - A/B testing endpoints

### Test Patterns

#### Request Validation Tests
```python
def test_create_canvas_with_invalid_data():
    """Test canvas creation rejects invalid data"""
    response = client.post("/api/canvas", json={
        "title": "",  # Empty title should fail
        "canvas_type": "invalid_type"  # Invalid type
    })
    assert response.status_code == 422
```

#### Response Validation Tests
```python
def test_create_canvas_returns_correct_schema():
    """Test canvas creation returns valid response schema"""
    response = client.post("/api/canvas", json=valid_canvas_data)
    assert response.status_code == 200
    data = response.json()
    assert "canvas_id" in data
    assert data["title"] == valid_canvas_data["title"]
```

#### Error Handling Tests
```python
def test_create_canvas_handles_database_error():
    """Test canvas creation handles database errors gracefully"""
    # Mock database error
    with patch("core.models.SessionLocal") as mock_db:
        mock_db.side_effect = Exception("Database connection failed")
        response = client.post("/api/canvas", json=valid_canvas_data)
        assert response.status_code == 500
```

#### Database Transaction Rollback Tests
```python
@pytest.fixture
def db_session():
    """Create a test database session with rollback"""
    session = SessionLocal()
    try:
        yield session
        session.rollback()  # Rollback after test
    finally:
        session.close()

def test_create_canvas_in_transaction(db_session):
    """Test canvas creation is rolled back after test"""
    canvas_id = create_canvas(db_session, test_data)
    assert canvas_id is not None

    # Verify data exists in transaction
    canvas = db_session.query(Canvas).filter_by(id=canvas_id).first()
    assert canvas is not None

    # After rollback, data should not exist
    db_session.rollback()
    canvas = db_session.query(Canvas).filter_by(id=canvas_id).first()
    assert canvas is None
```

## Tasks

### Wave 1: Core API Integration Tests (Priority: P0)

- [ ] **Task 1.1**: Create `backend/tests/integration/api/test_agent_endpoints.py`
  - Test chat endpoint (`POST /api/agent/chat`)
  - Test streaming endpoint (`POST /api/agent/stream`)
  - Test agent list endpoint (`GET /api/agents`)
  - Test agent detail endpoint (`GET /api/agents/{agent_id}`)
  - Test agent creation endpoint (`POST /api/agents`)
  - Test agent update endpoint (`PUT /api/agents/{agent_id}`)
  - Test agent deletion endpoint (`DELETE /api/agents/{agent_id}`)
  - **Acceptance**: All endpoints tested with valid and invalid data, errors handled correctly

- [ ] **Task 1.2**: Create `backend/tests/integration/api/test_canvas_endpoints.py`
  - Test canvas creation endpoint (`POST /api/canvas`)
  - Test canvas retrieval endpoint (`GET /api/canvas/{canvas_id}`)
  - Test canvas update endpoint (`PUT /api/canvas/{canvas_id}`)
  - Test canvas deletion endpoint (`DELETE /api/canvas/{canvas_id}`)
  - Test canvas list endpoint (`GET /api/canvas`)
  - Test canvas component addition (`POST /api/canvas/{canvas_id}/components`)
  - **Acceptance**: All canvas CRUD operations tested with governance validation

- [ ] **Task 1.3**: Create `backend/tests/integration/api/test_browser_endpoints.py`
  - Test browser session creation (`POST /api/browser/session`)
  - Test browser navigation (`POST /api/browser/navigate`)
  - Test browser screenshot (`POST /api/browser/screenshot`)
  - Test browser form fill (`POST /api/browser/fill`)
  - Test browser session termination (`DELETE /api/browser/session`)
  - **Acceptance**: All browser automation endpoints tested with maturity validation

### Wave 2: Database Integration Tests (Priority: P0)

- [ ] **Task 2.1**: Create `backend/tests/integration/database/test_transaction_rollback.py`
  - Test transaction rollback for agent creation
  - Test transaction rollback for canvas creation
  - Test transaction rollback for episode creation
  - Test transaction rollback for browser session creation
  - **Acceptance**: All database changes rolled back after tests, no test data pollution

- [ ] **Task 2.2**: Create `backend/tests/integration/database/test_agent_queries.py`
  - Test agent CRUD operations with database
  - Test agent filtering and sorting
  - Test agent pagination
  - Test agent relationship queries (executions, feedback)
  - **Acceptance**: All query patterns tested with actual database

- [ ] **Task 2.3**: Create `backend/tests/integration/database/test_canvas_queries.py`
  - Test canvas CRUD operations with database
  - Test canvas component queries
  - Test canvas audit trail queries
  - Test canvas filtering by type
  - **Acceptance**: All canvas query patterns tested

### Wave 3: Additional API Endpoints (Priority: P1)

- [ ] **Task 3.1**: Create `backend/tests/integration/api/test_device_endpoints.py`
  - Test camera access endpoint (`POST /api/device/camera`)
  - Test location endpoint (`GET /api/device/location`)
  - Test notification endpoint (`POST /api/device/notify`)
  - Test command execution endpoint (`POST /api/device/execute`)
  - **Acceptance**: All device capability endpoints tested with maturity validation

- [ ] **Task 3.2**: Create `backend/tests/integration/api/test_episode_endpoints.py`
  - Test episode creation endpoint (`POST /api/episodes`)
  - Test episode retrieval endpoint (`GET /api/episodes/{episode_id}`)
  - Test episode search endpoint (`POST /api/episodes/search`)
  - Test episode graduation endpoint (`POST /api/episodes/{episode_id}/graduate`)
  - **Acceptance**: All episodic memory endpoints tested

- [ ] **Task 3.3**: Create `backend/tests/integration/api/test_feedback_endpoints.py`
  - Test feedback submission endpoint (`POST /api/feedback`)
  - Test feedback analytics endpoint (`GET /api/feedback/analytics`)
  - Test A/B test participation endpoint (`POST /api/ab-test/participate`)
  - **Acceptance**: All feedback and A/B testing endpoints tested

### Wave 4: Integration Test Coverage (Priority: P1)

- [ ] **Task 4.1**: Run coverage report on new integration tests
  - Generate coverage report: `pytest --cov=backend --cov-report=html`
  - Identify uncovered lines in API endpoints
  - **Acceptance**: Coverage report generated, gaps identified

- [ ] **Task 4.2**: Add missing tests for uncovered lines
  - Review uncovered lines in API endpoints
  - Add tests for error paths
  - Add tests for edge cases
  - **Acceptance**: At least 30% increase in overall coverage

- [ ] **Task 4.3**: Verify all tests pass
  - Run full test suite: `pytest tests/integration/ -v`
  - Fix any failing tests
  - **Acceptance**: All integration tests passing

## Dependencies

- Phase 1 (Test Infrastructure) - Complete
- Phase 2 (Core Property Tests) - Complete
- FastAPI TestClient - Available
- Database test fixtures - Available

## Estimated Time

- Wave 1: 3-4 hours
- Wave 2: 2-3 hours
- Wave 3: 2-3 hours
- Wave 4: 1-2 hours
- **Total**: 8-12 hours

## Risks & Mitigations

**Risk**: Test data cleanup issues
**Mitigation**: Use transaction rollback pattern for all database tests

**Risk**: Async endpoint testing complexity
**Mitigation**: Use TestClient with async support, follow FastAPI testing patterns

**Risk**: Mock complexity for external dependencies
**Mitigation**: Use pytest fixtures for consistent mocking, keep mocks simple

## Definition of Done

1. All 7 API endpoint test files created with comprehensive tests
2. All 3 database integration test files created with transaction rollback
3. At least 30% increase in overall code coverage
4. All tests passing consistently
5. Documentation updated with integration test patterns
6. No test data pollution (all changes rolled back)

## Verification Checklist

- [ ] All FastAPI endpoints have integration tests
- [ ] Request/response validation tested for all endpoints
- [ ] Error handling tested for all error conditions
- [ ] Database tests use transaction rollback
- [ ] Coverage increased by at least 30%
- [ ] All tests passing
- [ ] Documentation updated
