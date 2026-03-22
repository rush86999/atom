# Phase 216: Fix Business Facts Test Failures - Research

## Problem Statement

10 tests failing in `tests/api/test_admin_business_facts_routes.py` with various errors:
- AttributeError: `'dict' object has no attribute 'lower'` — Response structure mismatch
- Mock/Fixture issues with S3/R2 and PDF extraction services
- Database and external service integration problems

## Failure Analysis

### Issue 1: Response Structure Mismatch (1+ tests)

**Error**:
```python
AttributeError: 'dict' object has no attribute 'lower'
```

**Location**: Line 495
```python
assert "not found" in response.json()["detail"].lower()
```

**Root Cause**:
The test expects `response.json()["detail"]` to be a string, but FastAPI's error responses wrap complex objects. The `detail` field contains a dict, not a string.

**Expected**: `response.json()["detail"]` = "Business fact not found: non-existent-id"
**Actual**: `response.json()["detail"]` = {...dict with error details...}

### Issue 2: Mock Fixture Gaps (10 tests)

**Affected Tests**:
1. `test_get_fact_not_found` — Response structure issue
2. `test_upload_and_extract_success` — PDF extraction mocking
3. `test_upload_invalid_file_type` — File validation mocking
4. `test_upload_extracts_multiple_facts` — PDF extraction mocking
5. `test_upload_extraction_fails` — PDF extraction error handling
6. `test_verify_citation_s3_exists` — S3 service mocking
7. `test_verify_citation_s3_missing` — S3 missing citation
8. `test_verify_citation_local_exists` — Local file citation
9. `test_verify_citation_mixed_sources` — Mixed S3/local
10. `test_verify_citation_all_valid` — All citations valid

**Root Cause**:
Tests require mocking of:
- **WorldModelService**: Business facts storage and retrieval
- **S3/R2 Services**: Citation file storage
- **PDF Extraction Service**: Document parsing and fact extraction

Current fixtures don't properly mock these services, leading to:
- Database queries when services aren't mocked
- Missing attributes on mock objects
- Incorrect response structure assumptions

## Current Test Infrastructure

### Fixtures Present
```python
@pytest.fixture
def authenticated_admin_client(db: Session):
    """Create authenticated admin TestClient for testing."""
    def override_get_current_user():
        return AgentRegistry(
            id="admin-user",
            name="Admin User",
            email="admin@atom.ai",
            role="admin",
            status="active",
            tenant_id="default"
        )

    app.dependency_overrides[get_current_user] = override_get_current_user
    from fastapi.testclient import TestClient
    return TestClient(main_api_app)

@pytest.fixture
def mock_world_model_service():
    """Mock WorldModelService for testing."""
    return AsyncMock()
```

### Missing Mocks

1. **WorldModelService Methods**:
   - `get_fact_by_id()` — Used in GET endpoint
   - `create_fact()` — Used in upload endpoint
   - `verify_citation()` — Used in verification endpoint
   - `get_all_facts()` — Used in list endpoint

2. **S3/R2 Services**:
   - File existence checks
   - File uploads
   - File downloads

3. **PDF Extraction Service**:
   - `extract_facts_from_pdf()` — Called during upload
   - Returns structured data from documents

## Solution Options

### Option 1: Fix Response Structure Assertions (Recommended)

**Approach**: Update test assertions to match actual FastAPI error response format

**Changes**:
```python
# Before (line 495):
assert "not found" in response.json()["detail"].lower()

# After:
assert "not found" in str(response.json()["detail"]).lower()
# Or better:
assert response.status_code == 404
```

**Pros**:
- Quick fix (1-2 lines per test)
- No service changes needed
- Tests align with FastAPI patterns

**Cons**:
- Doesn't fix underlying service mocking gaps

**Risk**: Low

### Option 2: Complete Service Mocking (Recommended for Full Fix)

**Approach**: Properly mock all WorldModelService methods used by endpoints

**Implementation**:
```python
@pytest.fixture
def mock_world_model_service():
    """Mock WorldModelService with all methods."""
    service = AsyncMock()

    # Mock get_fact_by_id
    service.get_fact_by_id.return_value = BusinessFact(
        id="test-fact-1",
        fact="Test fact",
        citations=[],
        reason="Test",
        source_agent_id="user:test",
        created_at=datetime.now(timezone.utc),
        last_verified=datetime.now(timezone.utc),
        verification_status="verified"
    )

    # Mock create_fact
    service.create_fact.return_value = BusinessFact(...)

    # Mock verify_citation
    service.verify_citation.return_value = {
        "citation_id": "citation-1",
        "source": "s3://test/file.pdf",
        "page": 1,
        verified": True
    }

    return service
```

**Pros**:
- Tests fully isolated
- No database dependencies
- Fast execution
- Reusable pattern for other tests

**Cons**:
- More verbose fixture setup
- Requires understanding all service methods

**Risk**: Low

### Option 3: Integration Tests with Fake Services

**Approach**: Create fake S3/R2 and PDF extraction services

**Pros**:
- Tests closer to production behavior
- Validates integration points

**Cons**:
- Slower execution
- More complex setup
- Overkill for unit tests

**Risk**: Medium

## Implementation Strategy

### Wave 1: Fix Response Structure Assertions (Quick Win)

Update all test assertions to handle response.json() returning dicts:
- `str(response.json()["detail"])` for string operations
- Direct status code assertions where possible

### Wave 2: Add Complete WorldModelService Mocking

For tests that need actual service responses:
- Mock `get_fact_by_id()` for GET endpoints
- Mock `create_fact()` for upload endpoints
- Mock `verify_citation()` for verification endpoints

### Wave 3: Mock S3/R2 and PDF Extraction (If Needed)

If tests still fail after Wave 2:
- Mock S3 file operations
- Mock PDF extraction results
- Use MagicMock for complex object structures

## Related Files

- `backend/tests/api/test_admin_business_facts_routes.py` — Test file to fix
- `backend/api/admin/business_facts_routes.py` — API endpoints (no changes needed)
- `backend/core/agent_world_model.py` — WorldModelService (no changes needed)
- `backend/core/models.py` — BusinessFact model (no changes needed)

## Test Count

- Total failing tests: 10
- Test classes affected: 4 (TestBusinessFactsGet, TestBusinessFactsUpload, TestBusinessFactsVerify, others)

## Impact

- **Scope**: Test fixtures and assertions only
- **Risk**: Low (no production code changes)
- **Coverage**: No change (tests already exist)
- **Time estimate**: 30-45 minutes

## Success Criteria

- [ ] All 10 business facts tests pass
- [ ] No AttributeError or Mock errors
- [ ] Tests remain fast (no real S3/R2 calls)
- [ ] No production code changes
- [ ] Mocking pattern documented for future tests

## Next Steps

1. Fix response structure assertions (Wave 1)
2. Add WorldModelService method mocks (Wave 2)
3. Add S3/R2 and PDF extraction mocks if needed (Wave 3)
4. Run full test suite verification
5. Document mocking patterns
