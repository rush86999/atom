# Phase 197 Plan 03: Complex Mocking Results

**Date:** 2026-03-16
**Plan:** 197-03 - Resolve complex mocking challenges and integration test failures
**Status:** Partially Complete - Architectural Blocker Identified

---

## Executive Summary

Plan 197-03 encountered a **critical architectural blocker** that prevents completion of Tasks 3-6. The plan successfully completed Tasks 1-2 but cannot proceed without resolving the missing ActiveToken/RevokedToken models.

### Completion Status

- ✅ **Task 1:** Analyze complex mocking failures (COMPLETE)
- ✅ **Task 2:** Fix async test patterns (PARTIAL - fixtures created, blocker found)
- ❌ **Task 3:** Fix LLM mocking issues (BLOCKED)
- ❌ **Task 4:** Fix WebSocket test mocking (BLOCKED)
- ❌ **Task 5:** Fix integration test boundaries (BLOCKED)
- ❌ **Task 6:** Final mock verification (BLOCKED)

---

## Achievements (Tasks 1-2)

### Task 1: Complex Mocking Failure Analysis ✅

**Deliverables:**
- Created comprehensive failure analysis document
- Fixed Factory Boy + SQLAlchemy 2.0 incompatibility
- Fixed duplicate MarketingChannel table definition
- Identified 10 remaining collection errors
- Analyzed complex mocking scenarios (async, LLM, WebSocket, integration)

**Impact:**
- 6 test files can now collect tests successfully
- 4 agent factories fixed (StudentAgentFactory, InternAgentFactory, SupervisedAgentFactory, AutonomousAgentFactory)
- Foundation for async mocking established

**Commits:**
- `1a86dff50`: fix(197-03): resolve factory boy and sqlalchemy 2.0 incompatibility

---

### Task 2: Async Test Pattern Fixes ⚠️

**Deliverables:**
- Added pytest-asyncio plugin configuration to conftest.py
- Created 4 async test fixtures:
  - `async_client`: FastAPI async test client
  - `mock_llm`: AsyncMock LLM handler with streaming support
  - `mock_websocket`: AsyncMock WebSocket connection
  - `mock_connection_manager`: Mock WebSocket connection manager
- Fixed import errors in tests/unit/security/conftest.py

**Impact:**
- pytest-asyncio properly configured (AUTO mode)
- Async fixtures available for all tests
- 1 import error fixed (removed non-existent ActiveToken/RevokedToken from conftest)

**Commits:**
- `f3168ecfc`: test(197-03): add pytest-asyncio configuration and async test fixtures

---

## Critical Blocker (Rule 4 - Architectural)

### Issue: Missing ActiveToken and RevokedToken Models

**Found during:** Task 2 - Attempting to run async auth tests

**Location:** `core/auth_helpers.py`

**Error:**
```python
ImportError: cannot import name 'ActiveToken' from 'core.models'
```

**Impact:**
- `core/auth_helpers.py` has 10+ references to ActiveToken and RevokedToken
- `tests/unit/security/test_auth_helpers.py` cannot run (9 async tests blocked)
- Any test that imports auth_helpers will fail
- Affects authentication, token revocation, and token cleanup functionality

**Usage in auth_helpers.py:**
- Line 269: Query RevokedToken by jti
- Line 275: Create RevokedToken instance
- Line 340-344: Query ActiveToken by user_id with filters
- Line 357-363: Check and create RevokedToken
- Line 440: Query ActiveToken by jti
- Line 446: Create ActiveToken instance
- Line 495-496: Delete expired RevokedToken
- Line 538-539: Delete expired ActiveToken

**Available Token Models in core/models.py:**
- LinkToken
- TokenUsage
- PushToken
- IntegrationToken
- PasswordResetToken
- OAuthToken

**None of these match ActiveToken or RevokedToken.**

---

## Resolution Options

### Option A: Create ActiveToken and RevokedToken Models

**Pros:**
- Minimal code changes
- Maintains existing auth_helpers.py functionality
- Tests can run immediately

**Cons:**
- Requires database migration
- Need to define model schema (fields, relationships)
- May overlap with OAuthToken functionality

**Effort:** 2-3 hours (schema design + migration + tests)

**Schema Proposal:**
```python
class ActiveToken(Base):
    __tablename__ = "active_tokens"

    jti = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    token = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    jti = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    revoked_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    reason = Column(String, nullable=True)
```

---

### Option B: Refactor auth_helpers.py to Use OAuthToken

**Pros:**
- Reuses existing OAuthToken model
- No new database tables needed
- Simplifies token management

**Cons:**
- Requires significant refactoring of auth_helpers.py
- OAuthToken may not have all required fields
- Risk of breaking existing OAuth functionality

**Effort:** 4-6 hours (refactor + test + verify)

---

### Option C: Remove Token Management Features

**Pros:**
- Eliminates blocker immediately
- Reduces code complexity

**Cons:**
- Loss of token revocation functionality
- Loss of active token tracking
- Security regression

**Effort:** 2-3 hours (remove + test)

**NOT RECOMMENDED** - Security regression

---

## Remaining Work (Tasks 3-6)

### Task 3: Fix LLM Mocking Issues

**Status:** BLOCKED by auth_helpers.py import

**Required Work:**
- Create comprehensive LLM mock fixtures
- Mock streaming responses
- Test token counting
- Mock rate limiting

**Estimated Effort:** 1-2 hours (unblocked)

**Test Impact:** ~15-20 tests

---

### Task 4: Fix WebSocket Test Mocking

**Status:** BLOCKED by auth_helpers.py import

**Required Work:**
- WebSocket connection mocks (already created in Task 2)
- Message send/receive tests
- Connection lifecycle tests
- Error handling tests

**Estimated Effort:** 1 hour (unblocked)

**Test Impact:** ~10-15 tests

---

### Task 5: Fix Integration Test Boundaries

**Status:** BLOCKED by auth_helpers.py import

**Required Work:**
- Mark integration tests with @pytest.mark.integration
- Add isolation fixtures
- Clear caches between tests
- Database rollback
- Run in isolation mode

**Estimated Effort:** 2-3 hours (unblocked)

**Test Impact:** ~20-30 tests

---

### Task 6: Final Mock Verification

**Status:** BLOCKED by auth_helpers.py import

**Required Work:**
- Run full test suite
- Calculate pass rate
- Verify 97-99% target
- Document results

**Estimated Effort:** 30 minutes (unblocked)

---

## Test Suite Statistics

### Current State

- **Total Tests:** 5,566
- **Collection Errors:** 10 (0.18%)
- **Blocker:** ActiveToken/RevokedToken imports
- **Estimated Pass Rate:** Unknown (cannot run full suite)

### After Task 1-2 Fixes

- **Factory Boy:** Fixed (4 factories)
- **Duplicate Tables:** Fixed (MarketingChannel)
- **pytest-asyncio:** Configured
- **Async Fixtures:** Created (4 fixtures)
- **Import Errors:** 1 fixed (conftest.py), 1 critical (auth_helpers.py)

---

## Deviations from Plan

### Deviation 1: Factory Boy Incompatibility (Rule 1 - Bug) ✅

**Found during:** Task 1

**Issue:** Factory Boy 3.3.3 cannot handle SQLAlchemy 2.0 models when subclassing factories without explicit Meta.model attribute.

**Fix:** Added explicit `class Meta: model = AgentRegistry` to all subclassed factories.

**Files:**
- `backend/tests/factories/agent_factory.py`

**Impact:** 6 test files can now collect

---

### Deviation 2: Duplicate Table Definition (Rule 1 - Bug) ✅

**Found during:** Task 1

**Issue:** MarketingChannel model defined in both `core/models.py` and `marketing/models.py`

**Fix:** Added `__table_args__ = {'extend_existing': True}`

**Files:**
- `backend/marketing/models.py`

**Impact:** test_operational_routes.py can now collect

---

### Deviation 3: Missing ActiveToken/RevokedToken Models (Rule 4 - Architectural) ❌

**Found during:** Task 2

**Issue:** core/auth_helpers.py imports non-existent ActiveToken and RevokedToken models

**Status:** BLOCKER - Requires architectural decision

**Impact:** Cannot complete Tasks 3-6

---

## Recommendations

### Immediate Action Required

1. **DECISION NEEDED:** Choose Option A (create models) or Option B (refactor to OAuthToken)
2. **IMPLEMENTATION:** 2-6 hours depending on option chosen
3. **RESUME TASKS:** Complete Tasks 3-6 after blocker resolved

### Proposed Path Forward

**Recommended: Option A** (Create ActiveToken and RevokedToken models)

**Rationale:**
- Minimal code changes
- Maintains existing functionality
- Fastest path to unblocking tests
- Clear separation of concerns (JWT tokens vs OAuth tokens)

**Implementation Plan:**
1. Create ActiveToken and RevokedToken models in core/models.py
2. Generate Alembic migration
3. Run migration
4. Verify auth_helpers.py imports work
5. Run async auth tests
6. Resume Tasks 3-6

**Estimated Total Time:** 3-4 hours (including Tasks 3-6)

---

## Success Metrics

### Completed
- [x] Factory Boy fixes applied (4 factories)
- [x] Duplicate table definition fixed
- [x] pytest-asyncio configured
- [x] Async fixtures created (4 fixtures)
- [x] Complex failure analysis documented

### Blocked
- [ ] ActiveToken/RevokedToken models created or refactored
- [ ] LLM mocks implemented
- [ ] WebSocket mocks implemented
- [ ] Integration tests isolated
- [ ] Pass rate reaches 97-99%

---

## Conclusion

Plan 197-03 successfully established the foundation for complex mocking (Tasks 1-2) but encountered an **unforeseen architectural blocker** (missing ActiveToken/RevokedToken models) that prevents completion of Tasks 3-6.

**Recommendation:** Create ActiveToken and RevokedToken models (Option A) to unblock the plan, then resume with Tasks 3-6 to achieve the 97-99% pass rate target.

**Next Phase:** After blocker resolution, complete Tasks 3-6 to achieve final pass rate improvement.

---

**Status:** Awaiting architectural decision - plan execution paused at Task 2.
