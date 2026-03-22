# API Route Testing Patterns - Mock Patching & Error Assertions

**Phase:** 216 - Fix Business Facts Test Failures
**Purpose:** Document patterns learned from fixing business facts route tests
**Last Updated:** March 20, 2026

---

## Overview

This document captures the key testing patterns learned from fixing 10 failing tests in `tests/api/test_admin_business_facts_routes.py`. These patterns apply to all API route tests using BaseAPIRouter and service mocking.

---

## Pattern 1: Mock Patching - Patch Where Imported, Not Where Defined

### The Problem

When mocking services in API route tests, you must patch the service at its **import location in the module under test**, not at its definition location.

### Example

**Route file:** `api/admin/business_facts_routes.py`
```python
# Module-level import (line 18)
from core.agent_world_model import BusinessFact, WorldModelService

# Module-level import (line 23)
from core.policy_fact_extractor import get_policy_fact_extractor

# Local import inside function (line 262)
from core.storage import get_storage_service
```

**Test file patch locations:**
```python
# ✅ CORRECT - Patch at import location in route module
patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_service)
patch('api.admin.business_facts_routes.get_policy_fact_extractor', return_value=mock_extractor)

# ❌ WRONG - Patch at definition location (doesn't work)
patch('core.agent_world_model.WorldModelService', return_value=mock_service)
patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_extractor)
```

### Why This Matters

When you patch the definition location (`core.agent_world_model.WorldModelService`), the route module has already imported the original class. The patch doesn't affect the already-imported reference. By patching at the import location (`api.admin.business_facts_routes.WorldModelService`), you intercept the reference that the route actually uses.

### Exception: Local Imports Inside Functions

For services imported inside functions (not at module level), patch at the original location:

```python
# Route function with local import
def upload_document(file: UploadFile):
    from core.storage import get_storage_service  # Local import
    storage = get_storage_service()
    ...

# Test patch location
patch('core.storage.get_storage_service', return_value=mock_storage)  # ✅ CORRECT
```

Since the import happens inside the function, patching the original module works correctly.

---

## Pattern 2: Error Response Assertions - BaseAPIRouter Structure

### The Problem

BaseAPIRouter.error_response() returns a structured error body dict, not a string. Tests must access nested fields for string operations.

### Error Response Structure

```json
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Business fact not found: fact-123",
    "timestamp": "2026-03-20T11:05:21.123456"
  }
}
```

### Example

**Before (Incorrect):**
```python
response = client.get("/api/admin/governance/facts/non-existent")
assert "not found" in response.json()["detail"].lower()  # ❌ AttributeError: 'dict' has no .lower()
```

**After (Correct):**
```python
response = client.get("/api/admin/governance/facts/non-existent")
assert response.status_code == 404
detail = response.json()["detail"]
assert "not found" in detail["error"]["message"].lower()  # ✅ Correct
```

### Reusable Pattern

```python
# For all BaseAPIRouter error responses:
response = client.get("/endpoint")
assert response.status_code == 404  # or 400, 500, etc.

detail = response.json()["detail"]
assert detail["success"] == False
assert detail["error"]["code"] == "NOT_FOUND"
assert "not found" in detail["error"]["message"].lower()  # String operations on message
```

### Common HTTP Status Codes

| Status | Error Code | Usage |
|--------|-----------|-------|
| 400 | VALIDATION_ERROR | Invalid input (BaseAPIRouter.validation_error) |
| 401 | UNAUTHORIZED | Missing/invalid auth |
| 403 | FORBIDDEN | Insufficient permissions |
| 404 | NOT_FOUND | Resource not found (BaseAPIRouter.not_found_error) |
| 500 | INTERNAL_ERROR | Server error |

---

## Pattern 3: Service Mock Fixture - Configure Returns in Fixture

### The Problem

Configure mock return values in fixtures, not in test methods. Keep tests clean and focused on behavior, not mock setup.

### Example

**Fixture Definition:**
```python
@pytest.fixture
def mock_world_model_service(sample_business_fact):
    """Mock WorldModelService with configured return values."""
    mock = AsyncMock()
    mock.get_fact_by_id.return_value = sample_business_fact
    mock.list_all_facts.return_value = [sample_business_fact]
    mock.create_fact.return_value = sample_business_fact
    return mock
```

**Test Usage:**
```python
def test_get_fact_success(authenticated_admin_client, mock_world_model_service):
    """Test getting a business fact by ID."""
    with patch('api.admin.business_facts_routes.WorldModelService',
               return_value=mock_world_model_service):

        response = authenticated_admin_client.get("/api/admin/governance/facts/fact-123")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"]["fact"] == "Invoices over $500 require VP approval"
```

### AsyncMock vs MagicMock

- **AsyncMock:** For async service methods (most API services)
- **MagicMock:** For sync methods or non-service objects

```python
# Async service methods (most common)
mock_service = AsyncMock()
mock_service.get_fact_by_id.return_value = fact  # ✅

# Sync methods
mock_storage = MagicMock()
mock_storage.upload_file.return_value = "s3://bucket/key"  # ✅
```

---

## Pattern 4: Configure Mocks Inside Patch Context

### The Problem

When overriding fixture defaults, configure mocks **inside** the patch context manager, not before.

### Example

**Before (Incorrect):**
```python
mock_extractor.extract_facts_from_document.return_value = result  # ❌ Outside context
with patch('api.admin.business_facts_routes.get_policy_fact_extractor',
           return_value=mock_extractor):
    response = client.post("/upload", files={"file": test_file})
    # mock_extractor uses fixture default, not this override
```

**After (Correct):**
```python
with patch('api.admin.business_facts_routes.get_policy_fact_extractor',
           return_value=mock_extractor) as patched_extractor:
    # Configure inside context for test-specific behavior
    patched_extractor.extract_facts_from_document.return_value = result

    response = client.post("/upload", files={"file": test_file})
    # mock_extractor uses test-specific configuration
```

### Why This Matters

When you configure the mock before entering the patch context, the patch context manager may reset or override your configuration. Configuring inside ensures your test-specific values are used.

---

## Pattern 5: S3/R2 Storage Mocking

### The Problem

Tests that verify citations from S3/R2 storage need mocked storage services that return deterministic URIs and existence checks.

### Example

**Fixture:**
```python
@pytest.fixture
def mock_storage_service():
    """Mock S3/R2 storage service for citation verification."""
    mock = MagicMock()
    mock.upload_file.return_value = "s3://atom-business-facts/uploads/test.pdf"
    mock.check_exists.return_value = True
    mock.download_file.return_value = b"PDF content bytes"
    return mock
```

**Test Usage:**
```python
def test_verify_citation_s3_exists(authenticated_admin_client, mock_storage_service):
    """Test citation verification for S3-stored files."""
    with patch('core.storage.get_storage_service', return_value=mock_storage_service):
        response = authenticated_admin_client.post(
            "/api/admin/governance/facts/fact-123/verify-citation",
            json={"citation_id": "citation-1"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["verified"] == True
```

### Common Mock Return Values

| Method | Return Value | Usage |
|--------|-------------|-------|
| `upload_file` | `"s3://bucket/key"` | Simulate successful upload |
| `check_exists` | `True` or `False` | Simulate file existence |
| `download_file` | `b"file bytes"` | Simulate file download |

---

## Pattern 6: PDF Extraction Mocking

### The Problem

Tests that upload documents need mocked PDF extraction services that return structured fact data.

### Example

**Fixture:**
```python
@pytest.fixture
def mock_policy_extractor():
    """Mock policy fact extractor for PDF parsing."""
    mock = AsyncMock()
    mock.extract_facts_from_document.return_value = {
        "facts": [
            {
                "fact": "Invoices over $500 require VP approval",
                "citations": ["s3://atom-business-facts/policies/ap-policy.pdf:page:5"],
                "reason": "Extracted from AP policy document",
                "confidence": 0.95
            }
        ],
        "metadata": {
            "source": "ap-policy.pdf",
            "page_count": 10,
            "extraction_method": "pdf_parser"
        }
    }
    return mock
```

**Test Usage:**
```python
def test_upload_and_extract_success(authenticated_admin_client,
                                   mock_policy_extractor,
                                   mock_storage_service):
    """Test successful document upload and fact extraction."""
    test_file = io.BytesIO(b"%PDF-1.4 ... test PDF content ...")

    with patch('api.admin.business_facts_routes.get_policy_fact_extractor',
               return_value=mock_policy_extractor):
        with patch('core.storage.get_storage_service', return_value=mock_storage_service):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": ("test.pdf", test_file, "application/pdf")}
            )

            assert response.status_code == 201
            data = response.json()
            assert len(data["data"]["facts"]) == 1
            assert "VP approval" in data["data"]["facts"][0]["fact"]
```

---

## Before/After Examples from Phase 216 Fixes

### Fix 1: Mock Patching Location

**Before (Wrong):**
```python
# Test file
patch('core.agent_world_model.WorldModelService', return_value=mock_service)

# Route file
from core.agent_world_model import WorldModelService

# Result: Route uses real WorldModelService, test fails
```

**After (Correct):**
```python
# Test file
patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_service)

# Route file
from core.agent_world_model import WorldModelService

# Result: Route uses mocked WorldModelService, test passes
```

### Fix 2: Error Response Assertion

**Before (Wrong):**
```python
response = client.get("/api/admin/governance/facts/non-existent")
assert "not found" in response.json()["detail"].lower()  # AttributeError
```

**After (Correct):**
```python
response = client.get("/api/admin/governance/facts/non-existent")
detail = response.json()["detail"]
assert "not found" in detail["error"]["message"].lower()  # Works!
```

### Fix 3: Mock Configuration Timing

**Before (Wrong):**
```python
mock_extractor.extract_facts_from_document.return_value = result
with patch('api.admin.business_facts_routes.get_policy_fact_extractor',
           return_value=mock_extractor):
    # Test - uses fixture default, not result
```

**After (Correct):**
```python
with patch('api.admin.business_facts_routes.get_policy_fact_extractor',
           return_value=mock_extractor) as patched_extractor:
    patched_extractor.extract_facts_from_document.return_value = result
    # Test - uses test-specific result
```

---

## Quick Reference Card

### Patch Location Decision Tree

```
Is the service imported in the route module?
├─ Yes, at module level (from x import y)
│  └─ Patch at: 'route_module.service_name'
│     Example: patch('api.admin.routes.WorldModelService')
│
└─ No, imported inside function
   └─ Patch at: 'original_module.service_name'
      Example: patch('core.storage.get_storage_service')
```

### Error Response Assertion Template

```python
# Success response
assert response.status_code == 200
data = response.json()
assert data["success"] == True
assert data["data"]["field"] == expected_value

# Error response
assert response.status_code in [400, 404, 500]
detail = response.json()["detail"]
assert detail["success"] == False
assert "error keyword" in detail["error"]["message"].lower()
```

---

## Related Documentation

- **Testing Standards:** `backend/docs/CODE_QUALITY_STANDARDS.md` - Section on API route testing
- **Business Facts Tests:** `backend/tests/api/test_admin_business_facts_routes.py` - Example implementations
- **BaseAPIRouter:** `backend/api/admin/base_routes.py` - Error response structure

---

## Impact

Using these patterns consistently across the codebase will:

✅ **Reduce debugging time** - Mock patches work correctly on first try
✅ **Improve test reliability** - Correct error response assertions
✅ **Maintain consistency** - Same patterns across all API route tests
✅ **Speed up development** - Less time fixing test infrastructure

---

*Last Updated: March 20, 2026*
*Phase: 216 - Fix Business Facts Test Failures*
*Status: Complete - All 37 tests passing (100%)*
