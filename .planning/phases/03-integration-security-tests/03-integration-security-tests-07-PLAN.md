# OAuth Flows and Episode Access Control Security Tests

**Phase**: 03 - Integration & Security Tests
**Plan**: 07 - OAuth Flows and Episode Access Control
**Status**: Pending
**Priority**: P1 (High)

## Objective

Build comprehensive security tests for OAuth authentication flows (third-party service integration) and episode access control (episodic memory privacy and permissions).

## Success Criteria

1. OAuth authorization flows are tested (authorization code, implicit, client credentials)
2. OAuth token handling is tested (access tokens, refresh tokens, token revocation)
3. OAuth scope validation is tested
4. OAuth callback handling is tested
5. Episode access control is tested (user can access own episodes)
6. Episode privacy is tested (users cannot access others' episodes)
7. Episode access logging is tested
8. Admin episode access is tested
9. At least 10% increase in overall code coverage

## Key Areas to Cover

### OAuth Authorization Flow Tests
```python
def test_oauth_authorization_code_flow():
    """Test OAuth authorization code flow"""
    # Step 1: Request authorization
    response = client.get("/api/oauth/authorize", params={
        "client_id": "test_client",
        "redirect_uri": "http://localhost:3000/callback",
        "response_type": "code",
        "scope": "read write",
        "state": "random_state"
    })
    assert response.status_code == 302  # Redirect to login

    # Step 2: User logs in and authorizes
    # (Simulated in test)

    # Step 3: Receive authorization code
    auth_code = "test_auth_code_123"

    # Step 4: Exchange code for access token
    response = client.post("/api/oauth/token", json={
        "grant_type": "authorization_code",
        "code": auth_code,
        "client_id": "test_client",
        "client_secret": "test_secret",
        "redirect_uri": "http://localhost:3000/callback"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

def test_oauth_implicit_flow():
    """Test OAuth implicit flow (deprecated but still supported)"""
    response = client.get("/api/oauth/authorize", params={
        "client_id": "test_client",
        "redirect_uri": "http://localhost:3000/callback",
        "response_type": "token",
        "scope": "read",
        "state": "random_state"
    })
    # Implicit flow returns token in URL fragment
    assert response.status_code == 302

def test_oauth_client_credentials_flow():
    """Test OAuth client credentials flow (machine-to-machine)"""
    response = client.post("/api/oauth/token", json={
        "grant_type": "client_credentials",
        "client_id": "test_client",
        "client_secret": "test_secret",
        "scope": "api_read"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data

def test_oauth_authorization_with_invalid_client():
    """Test OAuth authorization fails with invalid client"""
    response = client.post("/api/oauth/token", json={
        "grant_type": "authorization_code",
        "code": "test_code",
        "client_id": "invalid_client",
        "client_secret": "invalid_secret"
    })
    assert response.status_code == 401
    assert "invalid client" in response.json()["error_description"].lower()
```

### OAuth Token Handling Tests
```python
def test_oauth_access_token_usage():
    """Test OAuth access token can access protected resources"""
    # Get access token
    token_response = client.post("/api/oauth/token", json={
        "grant_type": "client_credentials",
        "client_id": "test_client",
        "client_secret": "test_secret"
    })
    access_token = token_response.json()["access_token"]

    # Use token to access protected resource
    response = client.get(
        "/api/protected/resource",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200

def test_oauth_access_token_expiration():
    """Test expired access tokens are rejected"""
    expired_token = create_expired_oauth_token()

    response = client.get(
        "/api/protected/resource",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401
    assert "token expired" in response.json()["error_description"].lower()

def test_oauth_refresh_token_flow():
    """Test refreshing access token with refresh token"""
    # Initial token request
    token_response = client.post("/api/oauth/token", json={
        "grant_type": "password",
        "username": "test@example.com",
        "password": "password123"
    })
    refresh_token = token_response.json()["refresh_token"]

    # Refresh access token
    response = client.post("/api/oauth/token", json={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": "test_client",
        "client_secret": "test_secret"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    # New access token is different from old one
    # (would need to store old token to verify)

def test_oauth_token_revocation():
    """Test OAuth token revocation"""
    # Get access token
    token_response = client.post("/api/oauth/token", json={
        "grant_type": "client_credentials",
        "client_id": "test_client",
        "client_secret": "test_secret"
    })
    access_token = token_response.json()["access_token"]

    # Revoke token
    response = client.post("/api/oauth/revoke", json={
        "token": access_token,
        "client_id": "test_client",
        "client_secret": "test_secret"
    })
    assert response.status_code == 200

    # Try to use revoked token
    response = client.get(
        "/api/protected/resource",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 401
```

### OAuth Scope Validation Tests
```python
def test_oauth_scope_validation():
    """Test OAuth scopes are properly validated"""
    # Request token with limited scope
    token_response = client.post("/api/oauth/token", json={
        "grant_type": "client_credentials",
        "client_id": "test_client",
        "client_secret": "test_secret",
        "scope": "read_only"
    })
    access_token = token_response.json()["access_token"]

    # Try to access read-write resource with read-only token
    response = client.post(
        "/api/protected/resource",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 403
    assert "insufficient_scope" in response.json()["error"]

def test_oauth_scope_inheritance():
    """Test OAuth scopes with inheritance (read includes read:basic)"""
    # Request token with broad scope
    token_response = client.post("/api/oauth/token", json={
        "grant_type": "client_credentials",
        "client_id": "test_client",
        "client_secret": "test_secret",
        "scope": "read"
    })
    access_token = token_response.json()["access_token"]

    # Access read:basic resource with read scope
    response = client.get(
        "/api/protected/basic",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
```

### OAuth Callback Tests
```python
def test_oauth_callback_handling():
    """Test OAuth callback handling after authorization"""
    # Simulate OAuth provider callback
    response = client.get("/api/oauth/callback", params={
        "code": "test_auth_code",
        "state": "random_state"
    })
    assert response.status_code == 302  # Redirect to app
    # Should set session cookies

def test_oauth_callback_with_error():
    """Test OAuth callback with error from provider"""
    response = client.get("/api/oauth/callback", params={
        "error": "access_denied",
        "error_description": "User denied access",
        "state": "random_state"
    })
    assert response.status_code == 302  # Redirect to app with error
    # App should display error to user

def test_oauth_callback_state_validation():
    """Test OAuth callback validates state parameter to prevent CSRF"""
    # Request authorization with state
    state = "random_state_123"

    # Callback with different state (CSRF attempt)
    response = client.get("/api/oauth/callback", params={
        "code": "test_auth_code",
        "state": "different_state"  # Invalid state
    })
    assert response.status_code == 400
    assert "invalid state" in response.json()["error"].lower()
```

### Episode Access Control Tests
```python
def test_user_can_access_own_episodes():
    """Test users can access their own episodes"""
    user = create_user()
    episode = create_episode(
        user=user,
        title="Test Episode",
        content="Private data"
    )

    response = client.get(
        f"/api/episodes/{episode.id}",
        headers={"Authorization": f"Bearer {user.token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["episode_id"] == episode.id
    assert data["title"] == "Test Episode"

def test_user_cannot_access_others_episodes():
    """Test users cannot access episodes created by other users"""
    user1 = create_user(email="user1@example.com")
    user2 = create_user(email="user2@example.com")

    episode = create_episode(
        user=user1,
        title="Private Episode",
        content="Sensitive data"
    )

    response = client.get(
        f"/api/episodes/{episode.id}",
        headers={"Authorization": f"Bearer {user2.token}"}
    )
    assert response.status_code == 403
    assert "forbidden" in response.json()["error"].lower()

def test_user_can_list_own_episodes():
    """Test users can list only their own episodes"""
    user = create_user()
    other_user = create_user()

    # Create episodes for user
    create_episode(user=user, title="Episode 1")
    create_episode(user=user, title="Episode 2")

    # Create episodes for other user
    create_episode(user=other_user, title="Other Episode 1")
    create_episode(user=other_user, title="Other Episode 2")

    response = client.get(
        "/api/episodes",
        headers={"Authorization": f"Bearer {user.token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["episodes"]) == 2
    assert all(ep["title"] in ["Episode 1", "Episode 2"] for ep in data["episodes"])

def test_admin_can_access_all_episodes():
    """Test admins can access all episodes"""
    admin = create_admin_user()
    user = create_user()

    episode = create_episode(
        user=user,
        title="User Episode",
        content="User data"
    )

    response = client.get(
        f"/api/episodes/{episode.id}",
        headers={"Authorization": f"Bearer {admin.token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["episode_id"] == episode.id

def test_episode_access_logging():
    """Test episode access is logged"""
    user = create_user()
    episode = create_episode(user=user)

    # Access episode
    response = client.get(
        f"/api/episodes/{episode.id}",
        headers={"Authorization": f"Bearer {user.token}"}
    )
    assert response.status_code == 200

    # Verify access log entry exists
    logs = get_episode_access_logs(episode.id)
    assert len(logs) == 1
    assert logs[0]["user_id"] == user.id
    assert logs[0]["access_type"] == "read"

def test_unauthorized_episode_access_attempt_logged():
    """Test unauthorized access attempts are logged"""
    user1 = create_user()
    user2 = create_user()
    episode = create_episode(user=user1)

    # Attempt unauthorized access
    response = client.get(
        f"/api/episodes/{episode.id}",
        headers={"Authorization": f"Bearer {user2.token}"}
    )
    assert response.status_code == 403

    # Verify access attempt was logged (even though it failed)
    logs = get_episode_access_logs(episode.id)
    unauthorized_logs = [log for log in logs if log["user_id"] == user2.id]
    assert len(unauthorized_logs) == 1
    assert unauthorized_logs[0]["access_type"] == "unauthorized_attempt"

def test_episode_search_respects_access_control():
    """Test episode search respects access control"""
    user1 = create_user()
    user2 = create_user()

    # Create episodes with similar content
    create_episode(user=user1, content="Confidential project plans")
    create_episode(user=user2, content="Confidential project plans")

    # User1 searches
    response = client.post(
        "/api/episodes/search",
        headers={"Authorization": f"Bearer {user1.token}"},
        json={"query": "project plans"}
    )
    assert response.status_code == 200
    data = response.json()
    # Should only return user1's episodes
    assert len(data["episodes"]) == 1
    assert data["episodes"][0]["user_id"] == user1.id

def test_episode_sharing():
    """Test episode sharing between users"""
    user1 = create_user()
    user2 = create_user()
    episode = create_episode(user=user1)

    # Share episode with user2
    response = client.post(
        f"/api/episodes/{episode.id}/share",
        headers={"Authorization": f"Bearer {user1.token}"},
        json={"share_with": user2.id, "permission": "read"}
    )
    assert response.status_code == 200

    # User2 can now access episode
    response = client.get(
        f"/api/episodes/{episode.id}",
        headers={"Authorization": f"Bearer {user2.token}"}
    )
    assert response.status_code == 200

def test_episode_sharing_with_invalid_permission():
    """Test episode sharing with invalid permission level"""
    user1 = create_user()
    user2 = create_user()
    episode = create_episode(user=user1)

    response = client.post(
        f"/api/episodes/{episode.id}/share",
        headers={"Authorization": f"Bearer {user1.token}"},
        json={"share_with": user2.id, "permission": "admin"}  # Invalid
    )
    assert response.status_code == 400
```

## Tasks

### Wave 1: OAuth Flow Tests (Priority: P0)

- [ ] **Task 1.1**: Create `backend/tests/security/oauth/test_oauth_flows.py`
  - Test authorization code flow
  - Test implicit flow
  - Test client credentials flow
  - Test resource owner password flow
  - **Acceptance**: All OAuth grant types tested

- [ ] **Task 1.2**: Create `backend/tests/security/oauth/test_oauth_tokens.py`
  - Test access token usage
  - Test access token expiration
  - Test refresh token flow
  - Test token revocation
  - **Acceptance**: All token lifecycle scenarios tested

- [ ] **Task 1.3**: Create `backend/tests/security/oauth/test_oauth_scopes.py`
  - Test scope validation
  - Test scope inheritance
  - Test scope restrictions
  - **Acceptance**: All scope scenarios tested

- [ ] **Task 1.4**: Create `backend/tests/security/oauth/test_oauth_callbacks.py`
  - Test callback handling
  - Test callback with error
  - Test callback state validation
  - **Acceptance**: All callback scenarios tested

### Wave 2: Episode Access Control Tests (Priority: P0)

- [ ] **Task 2.1**: Create `backend/tests/security/episodes/test_episode_access.py`
  - Test user can access own episodes
  - Test user cannot access others' episodes
  - Test user can list own episodes
  - Test admin can access all episodes
  - **Acceptance**: All basic access scenarios tested

- [ ] **Task 2.2**: Create `backend/tests/security/episodes/test_episode_search_access.py`
  - Test episode search respects access control
  - Test episode search with shared episodes
  - Test episode search privacy
  - **Acceptance**: All search access scenarios tested

- [ ] **Task 2.3**: Create `backend/tests/security/episodes/test_episode_sharing.py`
  - Test episode sharing
  - Test episode sharing with invalid permission
  - Test episode unsharing
  - Test episode shared access logging
  - **Acceptance**: All sharing scenarios tested

- [ ] **Task 2.4**: Create `backend/tests/security/episodes/test_episode_access_logging.py`
  - Test episode access logging
  - Test unauthorized access attempt logging
  - Test access log retrieval
  - **Acceptance**: All logging scenarios tested

### Wave 3: Coverage & Verification (Priority: P1)

- [ ] **Task 3.1**: Run coverage report
  - Generate coverage report
  - Identify uncovered lines
  - **Acceptance**: Coverage report generated

- [ ] **Task 3.2**: Add missing tests
  - Review uncovered lines
  - Add edge case tests
  - **Acceptance**: At least 10% increase in coverage

- [ ] **Task 3.3**: Verify all tests pass
  - Run full test suite
  - Fix failures
  - **Acceptance**: All OAuth and episode access tests passing

## Dependencies

- Phase 1 (Test Infrastructure) - Complete
- Phase 2 (Core Property Tests) - Complete
- OAuth system implemented
- Episode access control implemented

## Estimated Time

- Wave 1: 3-4 hours
- Wave 2: 3-4 hours
- Wave 3: 1-2 hours
- **Total**: 7-10 hours

## Definition of Done

1. OAuth authorization flows tested
2. OAuth token handling tested
3. OAuth scope validation tested
4. OAuth callback handling tested
5. Episode access control tested
6. Episode privacy tested
7. Episode access logging tested
8. Admin episode access tested
9. At least 10% increase in overall code coverage
10. All tests passing
11. Documentation updated

## Verification Checklist

- [ ] OAuth authorization flows tested
- [ ] OAuth tokens tested
- [ ] OAuth scopes tested
- [ ] OAuth callbacks tested
- [ ] Episode access control tested
- [ ] Episode privacy tested
- [ ] Episode sharing tested
- [ ] Episode access logging tested
- [ ] Coverage increased by at least 10%
- [ ] All tests passing
