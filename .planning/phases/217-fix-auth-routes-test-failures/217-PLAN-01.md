---
wave: 1
depends_on: []
files_modified:
  - tests/test_auth_routes_coverage.py
autonomous: false
---

# Plan 217-01: Debug Database State in Auth Tests

**Goal:** Add debug assertions to verify user exists and database state before login attempts.

## Problem

Auth tests fail with 401 Unauthorized. Need to verify:
1. User is actually created in database
2. User has password_hash
3. User is queryable by test_db session

## Tasks

### Task 1: Add Debug Assertion to test_login_success_with_valid_credentials

**File:** `tests/test_auth_routes_coverage.py`

**Changes:**
```python
def test_login_success_with_valid_credentials(self, client: TestClient, test_user: User, test_db: Session):
    """Test successful login with valid credentials."""
    # DEBUG: Verify user exists in database before login
    from core.models import User
    user_from_db = test_db.query(User).filter(User.email == test_user.email).first()
    assert user_from_db is not None, f"User not found in test_db: {test_user.email}"
    assert user_from_db.password_hash is not None, "User has no password hash"
    assert user_from_db.id == test_user.id, f"User ID mismatch: {user_from_db.id} vs {test_user.id}"

    # Now attempt login
    response = client.post("/api/auth/login", json={
        "username": test_user.email,
        "password": "TestPassword123!"
    })
    assert response.status_code == 200
```

### Task 2: Add Debug Logging to test_app Fixture Mock

**File:** `tests/test_auth_routes_coverage.py`

**Changes:**
```python
async def mock_verify_new(username: str, password: str):
    """Mock credential verification using test database."""
    from core.enterprise_auth_service import EnterpriseAuthService
    import logging
    logger = logging.getLogger(__name__)

    auth_service = EnterpriseAuthService()

    # DEBUG: Log what we're doing
    logger.info(f"[MOCK] verify_credentials called with username={username}")
    logger.info(f"[MOCK] test_db session id: {id(test_db)}")

    # Use the test database directly
    user_creds = auth_service.verify_credentials(test_db, username, password)

    logger.info(f"[MOCK] user_creds result: {user_creds is not None}")

    if not user_creds:
        logger.warning(f"[MOCK] verify_credentials returned None for username={username}")
        return None

    return {
        'user_id': user_creds.user_id,
        'username': user_creds.username,
        'email': user_creds.email,
        'roles': user_creds.roles,
        'security_level': user_creds.security_level,
        'permissions': user_creds.permissions
    }
```

### Task 3: Run Tests and Analyze Output

**Command:**
```bash
cd /Users/rushiparikh/projects/atom/backend
PYTHONPATH=. pytest tests/test_auth_routes_coverage.py::TestLoginEndpoint::test_login_success_with_valid_credentials -v -s 2>&1 | grep -E "DEBUG|MOCK|assert|FAILED"
```

**Expected:** Tests will fail with informative assertion messages showing:
- Whether user exists in database
- Whether password_hash is present
- Whether mock is being called
- What verify_credentials returns

## Verification

- [ ] Debug assertions added to 1-2 failing tests
- [ ] Tests run with verbose output showing database state
- [ ] Root cause confirmed (user not found, password wrong, or mock not called)

## Success Criteria

Test output clearly identifies which component is failing:
- If user not found → Database session issue
- If user found but creds None → Password hashing issue
- If mock not called → Patching issue
