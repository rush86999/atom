# Phase 217: Fix Auth Routes Test Failures - Research

## Problem Summary

**Tests Affected:** `tests/test_auth_routes_coverage.py` (67 total, 10 failing)
**Error:** 401 Unauthorized when expecting 200 OK for valid login attempts
**Error Message:** "Invalid username or password"

## Root Cause Analysis

### Test Setup Flow

1. **test_user fixture** creates user with:
   ```python
   auth_service = EnterpriseAuthService()
   password_hash = auth_service.hash_password("TestPassword123!")
   user = User(email="test@example.com", password_hash=password_hash, ...)
   test_db.add(user)
   test_db.commit()
   ```

2. **test_app fixture** mocks credential verification:
   ```python
   async def mock_verify_new(username: str, password: str):
       auth_service = EnterpriseAuthService()
       user_creds = auth_service.verify_credentials(test_db, username, password)
       return {...}
   
   with patch('api.enterprise_auth_endpoints._verify_enterprise_credentials_new', side_effect=mock_verify_new):
       yield app
   ```

3. **Login endpoint** (`/api/auth/login`):
   - Calls `_verify_enterprise_credentials_new()` (mocked)
   - Mocked version calls `verify_credentials(test_db, username, password)`
   - verify_credentials queries User from database and checks password hash

### Expected Behavior

- Password: "TestPassword123!" (plain text in login)
- Hash: bcrypt hash of "TestPassword123!" (stored in database)
- Verification: `bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))`

### Potential Issues

Based on analysis, the likely root causes are:

1. **Database Session Issue** ⚠️ MOST LIKELY
   - The mock uses `test_db` directly
   - But `verify_credentials()` might be creating a new session internally
   - User created in one session, queried in another → not found

2. **Mock Patching Issue**
   - Mock patches 'api.enterprise_auth_endpoints._verify_enterprise_credentials_new'
   - But there's also a wrapper function `_verify_enterprise_credentials()` that calls it
   - Mock might not be intercepting the call correctly

3. **Transaction Isolation**
   - test_db fixture might have uncommitted changes
   - User creation might not be visible to login endpoint
   - SQLite transaction isolation could be blocking reads

4. **Password Hash Encoding**
   - hash_password returns decoded string: `hashed.decode('utf-8')`
   - verify_password encodes again: `hashed_password.encode('utf-8')`
   - Double-encoding issue possible

## Investigation Steps

1. ✅ Check test_user fixture - Uses EnterpriseAuthService.hash_password() correctly
2. ✅ Check password hashing - bcrypt with rounds=12, encoding looks correct
3. ✅ Check mock setup - Patches _verify_enterprise_credentials_new with side_effect
4. ⚠️ **NEEDS VERIFICATION**: Does verify_credentials() use the same test_db session?
5. ⚠️ **NEEDS VERIFICATION**: Is user actually in database when login runs?
6. ⚠️ **NEEDS VERIFICATION**: Is mock being called during test execution?

## Fix Strategy

### Option 1: Fix Database Session Issue (Most Likely)

The mock passes `test_db` to `verify_credentials()`, but the login endpoint creates its own session via `get_db()`. This means:

- User created in session A (test_db)
- Login endpoint creates session B via `get_db()` dependency override
- But `verify_credentials()` is called with session A (test_db)
- Session A and B might be different SQLite connections

**Fix:** Ensure test_db is properly passed through entire flow:

```python
# In test_app fixture, ensure get_db returns test_db
def override_get_db():
    yield test_db  # Already there, but verify it's working

# In mock_verify_new, log what's happening
logger.info(f"Verifying credentials for {username} with test_db={id(test_db)}")
```

### Option 2: Fix Mock Patching

The mock might not be applied correctly. Try alternative patch locations:

```python
# Instead of patching the function, patch where it's imported
with patch('core.enterprise_auth_service.EnterpriseAuthService.verify_credentials') as mock_verify:
    mock_verify.return_value = expected_credentials
```

### Option 3: Debug Database State

Add assertions to verify user exists before login:

```python
def test_login_success_with_valid_credentials(self, client: TestClient, test_user: User, test_db: Session):
    # DEBUG: Verify user exists in database
    from core.models import User
    user_from_db = test_db.query(User).filter(User.email == test_user.email).first()
    assert user_from_db is not None, "User not found in test_db before login"
    assert user_from_db.password_hash is not None, "User has no password hash"
    
    # Now try login
    response = client.post("/api/auth/login", json={...})
```

## Recommended Approach

1. **Start with Option 3** - Add debug assertions to verify user exists
2. **If user exists but password fails** → Check password encoding/mocking
3. **If user doesn't exist** → Fix database session issue (Option 1)
4. **If mock not called** → Fix patch location (Option 2)

## Files to Modify

- `tests/test_auth_routes_coverage.py` - Add debug assertions, fix mock
- Possibly `api/enterprise_auth_endpoints.py` - Unlikely to need changes
- Possibly `tests/conftest.py` - If fixture needs adjustment

## Success Criteria

- All 10 failing auth tests pass
- Tests can create users and successfully log in
- No hardcoded workarounds or mocks that bypass real logic
