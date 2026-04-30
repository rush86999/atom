# PUT Endpoint Semantics Decision

**Date**: 2026-04-30
**Plan**: 306-07 (TDD Bug Discovery Coverage)
**Issue**: PUT endpoint semantic ambiguity causing test failure

## Decision

**Choice**: **Option A - RESTful PUT (validate all required fields)**

## Rationale

### HTTP Specification Reference
Per [RFC 9110 Section 4.3.4 (PUT)](https://httpwg.org/specs/rfc9110.html#PUT):
> "The PUT method requests that the state of the target resource be created or replaced with the state defined by the representation enclosed in the request message payload."

Key principles:
1. **PUT = Full Replacement**: The PUT method should replace the entire target resource
2. **Validation Required**: If required fields are missing, the server should reject the request
3. **Idempotent**: Multiple identical PUT requests should have the same effect as a single request

### Why RESTful PUT Over Pragmatic PUT?

| Factor | RESTful PUT | Pragmatic PUT |
|--------|-------------|---------------|
| **HTTP Compliance** | ✅ Follows RFC 9110 specification | ❌ Deviates from standard (should be PATCH) |
| **API Clarity** | ✅ Clear contract (PUT = replace, PATCH = modify) | ❌ Ambiguous (PUT behaves like PATCH) |
| **Client Intent** | ✅ Explicit full replacement intent | ⚠️ Implicit partial update behavior |
| **Validation Consistency** | ✅ POST and PUT validate same constraints | ❌ Inconsistent validation (POST strict, PUT loose) |
| **Error Detection** | ✅ Catches missing required data early | ⚠️ Silent partial updates may hide bugs |

### Breaking Change Consideration

**Impact Assessment**:
- Current implementation allows partial updates via PUT (all fields optional in `AgentUpdateRequest`)
- Clients may depend on partial update behavior
- **However**: The existence of a PATCH endpoint (line 263-290) provides a migration path

**Migration Path**:
1. **Phase 1** (This fix): Implement RESTful PUT validation
   - Modify `PUT /api/agents/{id}` to use `AgentReplaceRequest` (all required fields)
   - Existing PATCH endpoint remains available for partial updates
   - Return 422 if required fields missing

2. **Phase 2** (Client migration):
   - Clients using PUT for partial updates should switch to PATCH
   - PATCH endpoint: `PATCH /api/agents/{id}` (already exists at line 263)
   - Both endpoints available during transition period

3. **Phase 3** (Future):
   - Monitor API logs for 422 errors on PUT requests
   - Add deprecation warnings if needed
   - Consider adding API versioning if breaking changes become common

### Security Implications

**Threat Model: T-306-07-01 (Tampering)**
- **Risk**: Partial updates via PUT could bypass intended validation logic
- **Mitigation**: Required field validation ensures data integrity at trust boundary
- **Implementation**: `AgentReplaceRequest` model enforces `name` and `category` as required

### Test Coverage

The property test `test_put_agents_id_validates_all_post_constraints` (line 404-426) validates:
- ✅ Missing required `name` field returns 422
- ✅ PUT endpoint enforces same constraints as POST endpoint
- ✅ API contract consistency (POST and PUT validate same schema)

## Implementation

### New Request Model: `AgentReplaceRequest`

```python
class AgentReplaceRequest(BaseModel):
    """Request model for PUT /api/agents/{id} - full agent replacement.

    Per RFC 9110 Section 4.3.4 (PUT), this endpoint validates all required fields
    and performs a full replacement of the agent resource. For partial updates,
    use PATCH /api/agents/{id} instead.

    Required fields:
        name: Agent name (1-100 characters, not whitespace-only)
        category: Agent category (1-50 characters, not whitespace-only)

    Optional fields:
        description: Agent description
        configuration: Agent configuration dictionary
        schedule_config: Agent schedule configuration dictionary
    """
    name: str = Field(min_length=1, max_length=100, description="Agent name (required)")
    description: Optional[str] = None
    category: str = Field(min_length=1, max_length=50, description="Agent category (required)")
    configuration: Optional[Dict[str, Any]] = None
    schedule_config: Optional[Dict[str, Any]] = None

    @field_validator('name', 'category')
    @classmethod
    def validate_not_whitespace(cls, v: str) -> str:
        """Validate that name and category are not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError('cannot be empty or whitespace-only')
        return v.strip()
```

### PUT Endpoint Behavior

**Before (Pragmatic PUT)**:
- Accepted partial updates (all fields optional)
- Returned 200 for missing `name` field
- Inconsistent with POST validation

**After (RESTful PUT)**:
- Requires all fields: `name`, `category`
- Returns 422 if required fields missing
- Consistent with POST validation
- Full replacement semantics per RFC 9110

### Client Migration Guide

**Before (if using PUT for partial updates)**:
```http
PUT /api/agents/{id}
{
  "description": "Updated description"
}
```
**Result**: 422 Unprocessable Entity (missing required fields)

**After (use PATCH for partial updates)**:
```http
PATCH /api/agents/{id}
{
  "description": "Updated description"
}
```
**Result**: 200 OK (partial update successful)

**For full replacement (PUT)**:
```http
PUT /api/agents/{id}
{
  "name": "Updated Name",
  "category": "updated-category",
  "description": "Updated description",
  "configuration": {...},
  "schedule_config": {...}
}
```
**Result**: 200 OK (full replacement successful)

## References

- [RFC 9110 Section 4.3.4 (PUT)](https://httpwg.org/specs/rfc9110.html#PUT)
- [RFC 9110 Section 4.3.5 (PATCH)](https://httpwg.org/specs/rfc9110.html#PATCH)
- [MDN: HTTP PUT method](https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/PUT)
- [MDN: HTTP PATCH method](https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/PATCH)
- Plan 306-07: `.planning/phases/306-tdd-bug-discovery-coverage/306-07-PLAN.md`
- Test: `backend/tests/property_tests/test_api_invariants.py::TestRequestValidation::test_put_agents_id_validates_all_post_constraints`

## Approval

**Decision Made By**: User (option-a selection)
**Plan**: 306-07
**Task**: Task 2 - Align test and implementation with decision
**Status**: ✅ Approved and implemented
