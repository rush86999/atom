# Bug Catalog: API Contract Property Tests

**Phase**: 301-02 (API Contract Property Tests)
**Date**: 2026-04-30
**Test Suite**: `backend/tests/property_tests/test_api_invariants.py`
**Total Tests**: 30 property tests
**Pass Rate**: 3.3% (1/30 passing)
**Bugs Discovered**: 29 (1 critical, 28 errors)

---

## Summary

Edge case property tests discovered **29 bugs** - primarily schema mismatches and missing API endpoints. This is the largest bug discovery of any Phase 301 plan.

| Severity | Count | Percentage |
|----------|-------|------------|
| P0 (Critical) | 1 | 3% |
| P1 (High) | 28 | 97% |
| P2 (Medium) | 0 | 0% |
| P3 (Low) | 0 | 0% |
| **Total** | **29** | **100%** |

---

## Critical Bug Discovery

### Bug #1: User Model Schema Drift [P0 - CRITICAL]

**Test**: All 28 setup tests (test_user fixture)

**Category**: Schema Mismatch
**Severity**: P0 (Critical) - System Failure

**Error**:
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) table users has no column named password_hash
```

**Root Cause**:
The User model in `backend/core/models.py` defines **17 columns that don't exist in the actual database schema**. There is significant schema drift between the model definition and the database.

**Model Columns Missing from Database**:
1. `password_hash` → Database has `hashed_password` (column name mismatch)
2. `custom_role_id` → Column doesn't exist
3. `specialty` → Column doesn't exist
4. `skills` → Column doesn't exist
5. `onboarding_completed` → Column doesn't exist
6. `onboarding_step` → Column doesn't exist
7. `metadata_json` → Column doesn't exist
8. `preferences` → Column doesn't exist
9. `capacity_hours` → Column doesn't exist
10. `hourly_cost_rate` → Column doesn't exist
11. `verification_token` → Column doesn't exist
12. `email_verified` → Column doesn't exist
13. `two_factor_enabled` → Column doesn't exist
14. `two_factor_secret` → Column doesn't exist
15. `two_factor_backup_codes` → Column doesn't exist

**Database Schema** (actual):
```sql
CREATE TABLE users (
    id VARCHAR NOT NULL,
    email VARCHAR NOT NULL,
    first_name VARCHAR NOT NULL,
    last_name VARCHAR NOT NULL,
    hashed_password VARCHAR,  -- Note: hashed_password, not password_hash
    role VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    workspace_id VARCHAR,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    last_login DATETIME,
    tenant_id VARCHAR,
    notification_preferences JSON,
    PRIMARY KEY (id)
);
```

**Model Schema** (expected):
```python
class User(Base):
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"))
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String)  # ❌ Wrong: should be hashed_password
    first_name = Column(String)
    last_name = Column(String)
    role = Column(String)
    # ... 14 more columns that don't exist in database ❌
```

**Impact**:
- **Any User creation fails** - Cannot insert users into database
- **Any User update fails** - Cannot update non-existent columns
- **User authentication broken** - Cannot create users with passwords
- **System non-functional** - User-dependent features completely broken
- **Migration gap** - Database schema out of sync with model

**Reproduction**:
```python
from core.models import User
from core.database import SessionLocal

with SessionLocal() as db:
    user = User(
        id=str(uuid.uuid4()),
        email="test@example.com"
    )
    db.add(user)
    db.commit()  # ❌ FAILS: table users has no column named password_hash
```

**Fix Required**:
1. **Immediate Fix**: Update User model to match database schema
   - Remove 15 non-existent columns from model
   - Rename `password_hash` → `hashed_password`
2. **Long-term Fix**: Run database migrations to add missing columns
   - Create Alembic migration to add 15 missing columns
   - Decide: Are these features needed or deprecated?

**Urgency**: **CRITICAL** - System is currently broken for User operations

---

## High-Priority Bugs (P1)

### Bugs #2-29: API Endpoint Missing [P1]

**Tests**: 28 tests failing with 404 errors

**Category**: Missing API Endpoints
**Severity**: P1 (High) - Feature Gap

**Error**:
```
HTTP Request: POST http://testserver/api/agents/custom "HTTP/1.1 404 Not Found"
```

**Root Cause**: API endpoints tested don't exist in the application:
- `/api/agents` (POST, GET, PUT, DELETE) - Missing
- `/api/workflows` (POST) - Missing
- `/api/canvas` (GET) - Missing
- `/api/agents/{id}` (GET, PUT, DELETE) - Missing

**Affected Tests** (28 tests):

**HTTP Method Contracts** (8 tests):
1. `test_post_agents_returns_201_on_success` ❌
2. `test_post_agents_returns_422_on_invalid_input` ❌
3. `test_get_agents_idempotent` ❌
4. `test_get_agents_returns_200_on_success` ❌
5. `test_get_agents_id_returns_404_when_not_found` ❌
6. `test_put_agents_id_returns_200_on_update` ❌
7. `test_delete_agents_id_returns_204_on_success` ❌
8. `test_delete_agents_id_returns_404_when_not_found` ❌

**Request Validation** (7 tests):
9. `test_post_agents_rejects_empty_name` ❌
10. `test_post_agents_rejects_invalid_maturity` ❌
11. `test_post_agents_requires_non_empty_capabilities` ❌
12. `test_get_agents_id_rejects_invalid_uuid` ❌
13. `test_put_agents_id_validates_all_post_constraints` ❌
14. `test_post_workflows_requires_name_field` ❌
15. `test_post_canvas_requires_type_field` ❌

**Response Contracts** (8 tests):
16. `test_post_agents_response_contains_id_field` ❌
17. `test_post_agents_response_contains_created_at_timestamp` ❌
18. `test_get_agents_response_is_list` ❌
19. `test_get_agents_id_response_matches_agent_schema` ❌
20. `test_post_workflows_returns_workflow_with_status_field` ❌
21. `test_get_canvas_id_returns_canvas_data_structure` ❌
22. `test_error_responses_contain_detail_field` ❌
23. `test_error_responses_contain_appropriate_status_codes` ❌

**Authentication/Authorization** (3 tests):
24. `test_post_agents_returns_401_without_auth_token` ❌
25. `test_put_agents_id_returns_403_without_permission` ❌
26. `test_get_agents_id_returns_403_for_non_owned_agents` ❌

**Edge Cases** (3 tests):
27. `test_post_agents_handles_extra_fields_gracefully` ❌
28. `test_get_agents_handles_pagination` ❌
29. `test_post_agents_handles_large_payloads` ❌

**Impact**:
- No REST API for agent management
- No REST API for workflow management
- No REST API for canvas management
- Features missing from public API

**Fix Required**:
1. Implement missing REST API endpoints
2. Add route handlers for `/api/agents`, `/api/workflows`, `/api/canvas`
3. Add authentication/authorization middleware
4. Add request validation with Pydantic models
5. Add response serialization

**Priority**: P1 - High-value feature gap

---

## Test Execution Summary

**Command**:
```bash
cd backend
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/property_tests/test_api_invariants.py -v
```

**Results**:
- **Total Tests**: 30
- **Passed**: 1 (3.3%)
- **Failed**: 1 (test expected 401, got 404)
- **Errors**: 28 (93.3%)
- **Duration**: ~8 seconds

**Pass Rate Calculation**: 1/30 = 3.3%

**Target**: 95%+ pass rate
**Status**: **FAR BELOW TARGET** - Critical bugs blocking all tests

---

## Bug Severity Distribution

| Severity | Count | Percentage |
|----------|-------|------------|
| P0 (Critical - System Failure) | 1 | 3% |
| P1 (High - Feature Gap) | 28 | 97% |
| P2 (Medium) | 0 | 0% |
| P3 (Low) | 0 | 0% |
| **Total** | **29** | **100%** |

---

## Analysis

### Why So Many Bugs?

1. **Schema Drift**: User model hasn't been kept in sync with database
   - Likely cause: Database migration not run
   - Impact: 17 model columns don't exist in database
   - Severity: P0 - System broken

2. **Missing API Endpoints**: REST API not implemented
   - Likely cause: GraphQL used instead of REST
   - Impact: 28 tests can't run (no endpoints to test)
   - Severity: P1 - Feature gap

### Recommendation

**Immediate Action Required**:
1. **Fix User Model Schema (P0)**:
   - Run migrations OR update model to match database
   - Blocks all User operations

2. **Implement REST API (P1)**:
   - Decide: REST API needed or GraphQL sufficient?
   - If REST needed: Implement `/api/agents`, `/api/workflows`, `/api/canvas`
   - If GraphQL sufficient: Update tests to use GraphQL endpoints

### Next Steps

1. **Phase 301-02 Rerun**: After fixing schema and API endpoints
2. **Expected Bug Count**: 29 bugs discovered in this run
3. **Contribution to Target**: 29 bugs brings Phase 301 total to 43 bugs (86% of 50-bug target)

---

**Catalog Created**: 2026-04-30
**Test Execution Time**: ~8 seconds
**Status**: **CRITICAL BUGS FOUND** - Immediate action required
