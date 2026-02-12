# Authentication Flows and JWT Security Tests

**Phase**: 03 - Integration & Security Tests
**Plan**: 02 - Authentication Flows and JWT Security Tests
**Status**: Pending
**Priority**: P0 (Critical)

## Objective

Build comprehensive security tests for all authentication flows including signup, login, logout, session management, and JWT token refresh to ensure secure authentication across the Atom platform.

## Success Criteria

1. All authentication endpoints have security tests
2. JWT token generation and validation is tested
3. Token refresh flow is tested with expired tokens
4. Session management is tested (creation, validation, termination)
5. Authentication error conditions are tested (invalid credentials, expired tokens)
6. Security vulnerabilities are tested (SQL injection in auth, XSS in auth responses)
7. At least 20% increase in overall code coverage

## Current State

- **Coverage**: 16.06% overall
- **Authentication Files**: `backend/core/auth/`, `backend/api/auth_routes.py`
- **Test Infrastructure**: Phase 1 complete
- **JWT Library**: PyJWT or similar
- **Password Hashing**: bcrypt or similar

## Key Areas to Cover

### Authentication Endpoints
- `POST /api/auth/signup` - User registration
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `POST /api/auth/refresh` - JWT token refresh
- `GET /api/auth/me` - Get current user
- `POST /api/auth/change-password` - Change password
- `POST /api/auth/reset-password` - Reset password (forgot password)

### Test Patterns

#### Signup Flow Tests
```python
def test_signup_with_valid_data():
    """Test user signup with valid data"""
    response = client.post("/api/auth/signup", json={
        "email": "test@example.com",
        "password": "SecurePass123!",
        "name": "Test User"
    })
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["email"] == "test@example.com"

def test_signup_with_duplicate_email():
    """Test signup fails with duplicate email"""
    # First signup
    client.post("/api/auth/signup", json={
        "email": "test@example.com",
        "password": "SecurePass123!",
        "name": "Test User"
    })

    # Duplicate signup
    response = client.post("/api/auth/signup", json={
        "email": "test@example.com",
        "password": "DifferentPass123!",
        "name": "Different User"
    })
    assert response.status_code == 409
    assert "email already registered" in response.json()["detail"].lower()

def test_signup_with_weak_password():
    """Test signup fails with weak password"""
    response = client.post("/api/auth/signup", json={
        "email": "test@example.com",
        "password": "weak",  # Too short
        "name": "Test User"
    })
    assert response.status_code == 422
```

#### Login Flow Tests
```python
def test_login_with_valid_credentials():
    """Test login with valid credentials"""
    # Create user first
    create_test_user(email="test@example.com", password="SecurePass123!")

    # Login
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123!"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

def test_login_with_invalid_credentials():
    """Test login fails with invalid credentials"""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "WrongPassword123!"
    })
    assert response.status_code == 401
    assert "invalid credentials" in response.json()["detail"].lower()

def test_login_with_sql_injection():
    """Test login is protected against SQL injection"""
    response = client.post("/api/auth/login", json={
        "email": "'; DROP TABLE users; --",
        "password": "password"
    })
    assert response.status_code == 401
    # Verify users table still exists
    assert count_users() > 0
```

#### JWT Token Tests
```python
def test_jwt_token_structure():
    """Test JWT token has correct structure"""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123!"
    })
    data = response.json()
    token = data["access_token"]

    # Decode token (without verification for structure check)
    parts = token.split(".")
    assert len(parts) == 3  # header.payload.signature

def test_jwt_token_expiration():
    """Test JWT token expires after configured time"""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123!"
    })
    data = response.json()
    token = data["access_token"]

    # Decode and check expiration claim
    decoded = decode_jwt(token)
    assert "exp" in decoded
    assert decoded["exp"] > time.time()

def test_jwt_token_validation():
    """Test JWT token is validated on protected endpoints"""
    # Login to get token
    login_response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123!"
    })
    token = login_response.json()["access_token"]

    # Access protected endpoint with valid token
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200

    # Access with invalid token
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401

def test_jwt_token_refresh():
    """Test JWT token refresh flow"""
    # Login to get refresh token
    login_response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123!"
    })
    refresh_token = login_response.json()["refresh_token"]

    # Refresh tokens
    response = client.post("/api/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["access_token"] != login_response.json()["access_token"]

def test_jwt_token_refresh_with_expired_token():
    """Test token refresh fails with expired refresh token"""
    expired_token = create_expired_refresh_token()

    response = client.post("/api/auth/refresh", json={
        "refresh_token": expired_token
    })
    assert response.status_code == 401
    assert "token expired" in response.json()["detail"].lower()
```

#### Session Management Tests
```python
def test_session_creation():
    """Test session is created on login"""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123!"
    })
    assert response.status_code == 200

    # Verify session exists in database
    sessions = get_user_sessions("test@example.com")
    assert len(sessions) == 1

def test_session_termination():
    """Test session is terminated on logout"""
    # Login
    login_response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123!"
    })
    token = login_response.json()["access_token"]

    # Logout
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200

    # Verify session is terminated
    sessions = get_user_sessions("test@example.com")
    assert all(s.terminated for s in sessions)

def test_multiple_sessions():
    """Test user can have multiple active sessions"""
    # Create session 1
    client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123!"
    })

    # Create session 2
    client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123!"
    })

    # Verify 2 active sessions
    sessions = get_user_sessions("test@example.com")
    assert len(sessions) == 2
```

#### Password Change Tests
```python
def test_password_change_with_valid_current_password():
    """Test password change succeeds with valid current password"""
    # Login
    login_response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123!"
    })
    token = login_response.json()["access_token"]

    # Change password
    response = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "SecurePass123!",
            "new_password": "NewSecurePass456!"
        }
    )
    assert response.status_code == 200

    # Verify new password works
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "NewSecurePass456!"
    })
    assert response.status_code == 200

def test_password_change_with_invalid_current_password():
    """Test password change fails with invalid current password"""
    login_response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123!"
    })
    token = login_response.json()["access_token"]

    response = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "WrongPassword123!",
            "new_password": "NewSecurePass456!"
        }
    )
    assert response.status_code == 401
```

## Tasks

### Wave 1: Core Authentication Tests (Priority: P0)

- [ ] **Task 1.1**: Create `backend/tests/security/test_auth_signup.py`
  - Test signup with valid data
  - Test signup with duplicate email
  - Test signup with weak password
  - Test signup with invalid email format
  - Test signup with missing required fields
  - **Acceptance**: All signup scenarios tested, appropriate errors returned

- [ ] **Task 1.2**: Create `backend/tests/security/test_auth_login.py`
  - Test login with valid credentials
  - Test login with invalid email
  - Test login with invalid password
  - Test login with SQL injection attempt
  - Test login with XSS attempt
  - **Acceptance**: All login scenarios tested, security validated

- [ ] **Task 1.3**: Create `backend/tests/security/test_auth_logout.py`
  - Test logout terminates session
  - Test logout with invalid token
  - Test logout with expired token
  - **Acceptance**: All logout scenarios tested

### Wave 2: JWT Token Tests (Priority: P0)

- [ ] **Task 2.1**: Create `backend/tests/security/test_jwt_tokens.py`
  - Test JWT token structure
  - Test JWT token expiration
  - Test JWT token validation on protected endpoints
  - Test JWT token with invalid signature
  - Test JWT token with malformed structure
  - **Acceptance**: All JWT token scenarios tested

- [ ] **Task 2.2**: Create `backend/tests/security/test_jwt_refresh.py`
  - Test token refresh with valid refresh token
  - Test token refresh with expired refresh token
  - Test token refresh with invalid refresh token
  - Test token refresh generates new access token
  - **Acceptance**: All token refresh scenarios tested

- [ ] **Task 2.3**: Create `backend/tests/security/test_jwt_claims.py`
  - Test JWT contains user ID claim
  - Test JWT contains email claim
  - Test JWT contains expiration claim
  - Test JWT contains issued-at claim
  - **Acceptance**: All JWT claims validated

### Wave 3: Session Management Tests (Priority: P1)

- [ ] **Task 3.1**: Create `backend/tests/security/test_session_management.py`
  - Test session creation on login
  - Test session termination on logout
  - Test multiple concurrent sessions
  - Test session expiration
  - Test session validation
  - **Acceptance**: All session scenarios tested

- [ ] **Task 3.2**: Create `backend/tests/security/test_password_change.py`
  - Test password change with valid current password
  - Test password change with invalid current password
  - Test password change with weak new password
  - Test password change updates all sessions
  - **Acceptance**: All password change scenarios tested

- [ ] **Task 3.3**: Create `backend/tests/security/test_password_reset.py`
  - Test password reset request sends email
  - Test password reset with valid token
  - Test password reset with expired token
  - Test password reset with invalid token
  - **Acceptance**: All password reset scenarios tested

### Wave 4: Security Vulnerability Tests (Priority: P0)

- [ ] **Task 4.1**: Create `backend/tests/security/test_auth_sql_injection.py`
  - Test SQL injection in login email
  - Test SQL injection in login password
  - Test SQL injection in signup email
  - **Acceptance**: All SQL injection attempts blocked

- [ ] **Task 4.2**: Create `backend/tests/security/test_auth_xss.py`
  - Test XSS in user name during signup
  - Test XSS in error responses
  - Test XSS in auth responses
  - **Acceptance**: All XSS attempts sanitized

### Wave 5: Coverage & Verification (Priority: P1)

- [ ] **Task 5.1**: Run coverage report on auth tests
  - Generate coverage report
  - Identify uncovered lines in auth code
  - **Acceptance**: Coverage report generated

- [ ] **Task 5.2**: Add missing tests for uncovered auth lines
  - Review uncovered lines
  - Add tests for edge cases
  - **Acceptance**: At least 20% increase in overall coverage

- [ ] **Task 5.3**: Verify all auth tests pass
  - Run full auth test suite
  - Fix any failing tests
  - **Acceptance**: All auth security tests passing

## Dependencies

- Phase 1 (Test Infrastructure) - Complete
- Phase 2 (Core Property Tests) - Complete
- Authentication endpoints implemented
- JWT token system implemented
- Session management implemented

## Estimated Time

- Wave 1: 2-3 hours
- Wave 2: 2-3 hours
- Wave 3: 1-2 hours
- Wave 4: 1-2 hours
- Wave 5: 1-2 hours
- **Total**: 7-12 hours

## Risks & Mitigations

**Risk**: JWT token expiration timing issues in tests
**Mitigation**: Use fixed time mocking for consistent test results

**Risk**: Email dependency for password reset tests
**Mitigation**: Mock email service, verify email content without sending

**Risk**: Session state complexity
**Mitigation**: Use database rollback to clean up sessions

## Definition of Done

1. All authentication endpoints have security tests
2. JWT token generation, validation, and refresh tested
3. Session management tested
4. Security vulnerabilities tested (SQL injection, XSS)
5. At least 20% increase in overall code coverage
6. All tests passing consistently
7. Documentation updated with security test patterns

## Verification Checklist

- [ ] Signup flow tested with all scenarios
- [ ] Login flow tested with all scenarios
- [ ] Logout flow tested with all scenarios
- [ ] JWT tokens tested (structure, expiration, validation, refresh)
- [ ] Session management tested
- [ ] Password change and reset tested
- [ ] SQL injection protection tested
- [ ] XSS protection tested
- [ ] Coverage increased by at least 20%
- [ ] All tests passing
- [ ] Documentation updated
