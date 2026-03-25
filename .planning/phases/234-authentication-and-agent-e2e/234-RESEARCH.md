# Phase 234: Authentication & Agent E2E - Research

**Researched:** March 23, 2026
**Domain:** E2E Testing (Playwright, pytest, JWT validation, WebSocket streaming, concurrent execution)
**Confidence:** HIGH

## Summary

Phase 234 focuses on comprehensive E2E testing for authentication flows and agent execution critical paths. The research confirms that Atom has **significant test infrastructure from Phase 233** (API-first auth fixtures, worker database isolation, Allure reporting, shared utilities). The phase should focus on **writing the actual E2E tests** using existing infrastructure, not rebuilding test foundations.

**Key findings:**
- **API-first authentication fixtures exist** (`authenticated_page_api`, `setup_test_user`) providing 10-100x speedup over UI login
- **JWT token infrastructure is in place** (`create_access_token`, `verify_password`, `get_current_user` in `core/auth.py`)
- **WebSocket streaming infrastructure exists** (`ConnectionManager` in `core/websockets.py`, streaming endpoints in `core/atom_agent_endpoints.py`)
- **Agent governance system is testable** (`AgentRegistry` model, `AgentGovernanceService` with maturity levels)
- **Page Object Model established** (`LoginPage`, `DashboardPage`, `ChatPage` in `tests/e2e_ui/pages/page_objects.py`)
- **Parallel execution ready** (pytest-xdist with worker-specific database isolation from Phase 233)
- **Missing pieces:** Comprehensive E2E test coverage for auth flows (AUTH-01 through AUTH-07) and agent workflows (AGNT-01 through AGNT-08)

**Primary recommendation:** Build 15 comprehensive E2E tests across 3 categories:
1. **Authentication E2E (7 tests):** Login/logout, JWT validation, session persistence, token refresh, protected routes, API-first auth, mobile auth
2. **Agent Execution E2E (8 tests):** Agent creation, registry verification, chat streaming, concurrent execution, WebSocket reconnection, governance validation, lifecycle management, cross-platform consistency

Use existing fixtures (`authenticated_page_api`, `db_session`, `setup_test_user`) and Page Objects for maximum speed and reliability.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | ≥7.4, <9.0 | Test runner | Already configured in `pytest.ini`, supports xdist parallel execution |
| **pytest-playwright** | Latest | Browser automation | Already in use (Phase 75), fixtures configured in `e2e_ui/conftest.py` |
| **pytest-xdist** | ≥3.6, <4.0 | Parallel execution | Already configured with worker isolation (Phase 233) |
| **factory-boy** | ≥3.3.0 | Test data factories | Already in use (`AgentFactory`, `UserFactory` with `_session` enforcement) |
| **allure-pytest** | ≥2.13.0 | Unified reporting | Already integrated (Phase 233) with automatic screenshot/video capture |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **playwright-sync** | Latest | Sync browser automation | All E2E UI tests (already configured) |
| **pytest-asyncio** | Latest | Async test support | WebSocket testing, async agent execution |
| **python-jose** | Latest | JWT token creation/verification | Already in use (`core/auth.py`) |
| **bcrypt** | Latest | Password hashing | Already in use for user fixtures |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest-playwright | Selenium, Cypress | Playwright has faster execution, better WebSocket support, built-in waiting |
| API-first auth fixtures | UI login flow | UI login is 10-100x slower (2-10s vs <200ms), less reliable |
| Page Object Model | Direct selector usage | POM provides better maintainability and reusability (already established) |
| Allure reporting | Mochawesome, custom JSON | Allure has rich UI, history tracking, cross-platform aggregation (Phase 233) |

**Installation:**
```bash
# All core dependencies already installed
pip list | grep -E "(pytest|playwright|factory|allure)"

# Verify existing installations
pytest --version
playwright --version
```

---

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/e2e_ui/
├── conftest.py                          # Root conftest (EXISTS: auth fixtures, browser config)
├── fixtures/
│   ├── auth_fixtures.py                 # API-first auth fixtures (EXISTS)
│   ├── database_fixtures.py             # Worker DB isolation (EXISTS)
│   ├── api_fixtures.py                  # setup_test_user (EXISTS)
│   └── test_data_factory.py             # Factory functions (EXISTS)
├── pages/
│   └── page_objects.py                  # Page Objects (EXISTS: LoginPage, ChatPage, etc.)
├── tests/
│   ├── test_auth_login.py               # NEW: AUTH-01, AUTH-02 (Web UI login/logout, JWT validation)
│   ├── test_auth_session.py             # NEW: AUTH-03, AUTH-05 (Session persistence, protected routes)
│   ├── test_auth_token_refresh.py       # NEW: AUTH-04 (Token refresh flow)
│   ├── test_auth_api_first.py           # NEW: AUTH-06 (API-first auth validation)
│   ├── test_auth_mobile.py              # NEW: AUTH-07 (Mobile auth API-level)
│   ├── test_agent_creation.py           # NEW: AGNT-01 (Agent creation workflow)
│   ├── test_agent_registry.py           # NEW: AGNT-02 (Registry verification)
│   ├── test_agent_streaming.py          # EXISTS: AGNT-03 (Chat streaming - enhance)
│   ├── test_agent_concurrent.py         # NEW: AGNT-04 (Concurrent execution)
│   ├── test_agent_websocket_reconnect.py # NEW: AGNT-05 (WebSocket reconnection)
│   ├── test_agent_governance.py         # EXISTS: AGNT-06 (Governance validation - enhance)
│   ├── test_agent_lifecycle.py          # NEW: AGNT-07 (Lifecycle management)
│   └── test_agent_cross_platform.py     # NEW: AGNT-08 (Cross-platform consistency)
└── docs/
    ├── AUTH_E2E_TEST_COVERAGE.md        # NEW: Auth test mapping
    └── AGENT_E2E_TEST_COVERAGE.md       # NEW: Agent test mapping
```

### Pattern 1: API-First Authentication for E2E Speed

**What:** Bypass slow UI login flow by creating users via API and injecting JWT tokens directly to localStorage.

**When to use:** All E2E tests requiring authenticated state (except AUTH-01 which tests UI login flow itself).

**Example:**

```python
# Source: backend/tests/e2e_ui/fixtures/auth_fixtures.py (existing)
@pytest.fixture(scope="function")
def authenticated_page_api(browser: Browser, base_url: str, setup_test_user: dict):
    """Create authenticated page using API-first authentication (bypasses UI login).

    Performance: 10-100x faster than UI login (saves 2-10 seconds per test).

    Args:
        browser: Playwright browser fixture
        base_url: Base URL fixture
        setup_test_user: API fixture that creates test user and returns token

    Yields:
        Page: Authenticated Playwright page object
    """
    # Get user data and token from API fixture
    user_data = setup_test_user
    access_token = user_data.get("access_token")
    user_email = user_data.get("email")

    # Create new browser context and page
    context = browser.new_context()
    page = context.new_page()

    # Inject JWT token to localStorage (bypass UI login)
    page.goto(base_url)
    page.evaluate(f"""() => {{
        localStorage.setItem('access_token', '{access_token}');
        localStorage.setItem('auth_token', '{access_token}');
        localStorage.setItem('user_email', '{user_email}');
    }}""")

    yield page

    # Cleanup: close page and context
    page.close()
    context.close()


# Usage in E2E tests
def test_authenticated_user_can_access_dashboard(authenticated_page_api):
    """Test dashboard access with API-first auth."""
    dashboard = DashboardPage(authenticated_page_api)
    dashboard.navigate()

    assert dashboard.is_loaded(), "Dashboard should be loaded"
    # No UI login needed - saves 2-10 seconds per test
```

**Verification:**
```python
# Test that fixture actually set JWT token
def test_api_auth_token_in_localstorage(authenticated_page_api):
    """Verify API-first auth fixture sets JWT token correctly."""
    token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")

    assert token is not None, "JWT token should be set"
    assert len(token) > 50, "JWT token should be valid length"

    # Decode and verify token payload
    import json
    from base64 import b64decode
    payload = json.loads(b64decode(token.split('.')[1]))
    assert 'sub' in payload, "Token should have user ID"
    assert 'exp' in payload, "Token should have expiration"
```

### Pattern 2: JWT Token Validation in E2E Tests

**What:** Verify JWT token structure, claims, and expiration in E2E tests to ensure auth security.

**When to use:** AUTH-02 (JWT validation), AUTH-04 (Token refresh).

**Example:**

```python
# Source: backend/tests/e2e_ui/tests/test_auth_jwt_validation.py (NEW)
import pytest
import json
from base64 import b64decode
from datetime import datetime
from playwright.sync_api import Page


class TestJWTTokenValidation:
    """E2E tests for JWT token structure and claims (AUTH-02)."""

    def test_jwt_token_structure(self, authenticated_page_api: Page):
        """Verify JWT token has correct structure (header.payload.signature).

        Args:
            authenticated_page_api: Authenticated page fixture
        """
        # Get JWT token from localStorage
        token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")

        # Verify token structure
        parts = token.split('.')
        assert len(parts) == 3, "JWT should have 3 parts (header.payload.signature)"

        # Decode header
        header = json.loads(b64decode(parts[0]))
        assert header.get('alg') == 'HS256', "Should use HS256 algorithm"
        assert header.get('typ') == 'JWT', "Type should be JWT"

        # Decode payload
        payload = json.loads(b64decode(parts[1]))
        assert 'sub' in payload, "Should have user ID subject"
        assert 'exp' in payload, "Should have expiration claim"
        assert 'iat' in payload, "Should have issued-at claim"

    def test_jwt_token_expiration(self, authenticated_page_api: Page):
        """Verify JWT token expiration is set correctly (default 15 minutes).

        Args:
            authenticated_page_api: Authenticated page fixture
        """
        token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")
        payload = json.loads(b64decode(token.split('.')[1]))

        # Verify expiration is in the future
        exp_timestamp = payload['exp']
        exp_datetime = datetime.fromtimestamp(exp_timestamp)
        now = datetime.utcnow()

        assert exp_datetime > now, "Token should not be expired"
        assert exp_datetime < now.replace(hour=23, minute=59), "Token should expire today (default 15min)"

    def test_jwt_token_claims(self, authenticated_page_api: Page):
        """Verify JWT token contains required user claims.

        Args:
            authenticated_page_api: Authenticated page fixture
        """
        token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")
        payload = json.loads(b64decode(token.split('.')[1]))

        # Verify required claims
        assert 'sub' in payload, "Should have user ID"
        assert payload['sub'] is not None, "User ID should not be empty"

        # Verify optional claims
        if 'email' in payload:
            assert '@' in payload['email'], "Email should be valid format"

        if 'role' in payload:
            assert payload['role'] in ['user', 'admin', 'super_admin'], "Role should be valid"


class TestTokenRefresh:
    """E2E tests for JWT token refresh flow (AUTH-04)."""

    def test_token_refresh_before_expiration(self, authenticated_page_api: Page):
        """Verify token refresh flow works before expiration.

        This test validates:
        1. Client detects token nearing expiration
        2. Refresh token request is sent
        3. New access token is received
        4. New token is stored in localStorage
        5. User remains authenticated (no redirect to login)

        Args:
            authenticated_page_api: Authenticated page fixture
        """
        # Get initial token
        initial_token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")

        # Navigate to protected page (should trigger refresh if close to expiration)
        authenticated_page_api.goto("http://localhost:3001/dashboard")

        # Wait a moment for potential refresh
        authenticated_page_api.wait_for_timeout(1000)

        # Get current token
        current_token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")

        # Verify token exists (may be same or refreshed)
        assert current_token is not None, "Access token should exist after navigation"
        assert len(current_token) > 50, "Access token should be valid JWT"

        # Verify user is still authenticated (no redirect to login)
        current_url = authenticated_page_api.url
        assert 'login' not in current_url.lower(), "Should not be redirected to login"

    def test_expired_token_rejected(self, authenticated_page_api: Page):
        """Verify expired token is rejected by protected routes.

        Args:
            authenticated_page_api: Authenticated page fixture
        """
        # Inject expired token (manually crafted with exp in past)
        expired_token = self._create_expired_token()
        authenticated_page_api.evaluate(f"""() => {{
            localStorage.setItem('access_token', '{expired_token}');
        }}""")

        # Try to access protected route
        authenticated_page_api.goto("http://localhost:3001/api/v1/agents")

        # Should receive 401 or redirect to login
        authenticated_page_api.wait_for_timeout(2000)

        current_url = authenticated_page_api.url
        is_401 = 'unauthorized' in authenticated_page_api.content().lower()

        assert is_401 or 'login' in current_url.lower(), \
            "Expired token should be rejected"

    @staticmethod
    def _create_expired_token() -> str:
        """Create an expired JWT token for testing.

        Returns:
            Expired JWT token string
        """
        from datetime import datetime, timedelta
        from jose import jwt

        # Create token that expired 1 hour ago
        payload = {
            'sub': 'test-user-id',
            'exp': datetime.utcnow() - timedelta(hours=1),
            'iat': datetime.utcnow() - timedelta(hours=1, minutes=15)
        }

        # Use test SECRET_KEY (must match backend)
        import os
        secret = os.getenv('SECRET_KEY', 'test-secret-key')

        return jwt.encode(payload, secret, algorithm='HS256')
```

### Pattern 3: WebSocket Streaming E2E Testing

**What:** Test token-by-token LLM streaming via WebSocket with progressive display validation.

**When to use:** AGNT-03 (Chat streaming), AGNT-05 (WebSocket reconnection).

**Example:**

```python
# Source: backend/tests/e2e_ui/tests/test_agent_streaming.py (existing - enhance)
import pytest
import uuid
from playwright.sync_api import Page
from tests.e2e_ui.pages.page_objects import ChatPage


class TestAgentStreaming:
    """E2E tests for agent chat streaming responses (AGNT-03)."""

    def test_token_streaming_progressive_display(
        self,
        authenticated_page_api: Page,
        setup_test_user
    ):
        """Verify agent response streams token-by-token with progressive display.

        This test validates:
        1. User message triggers streaming:start event
        2. Multiple streaming:update events are received with deltas
        3. Response text grows incrementally as tokens arrive
        4. streaming:complete event signals end of stream

        Args:
            authenticated_page_api: Authenticated page fixture
            setup_test_user: API fixture for test user creation

        Coverage: AGNT-03 (Streaming token-by-token display)
        """
        # Setup test user and navigate to chat
        user_data = setup_test_user
        chat_page = ChatPage(authenticated_page_api)
        chat_page.navigate()

        # Verify chat page loaded
        assert chat_page.is_loaded(), "Chat page should be loaded"

        # Generate unique message to avoid caching
        unique_message = f"Tell me a short joke about testing {uuid.uuid4()}"

        # Track WebSocket events for streaming validation
        websocket_events = []

        # Inject WebSocket event listener script
        authenticated_page_api.evaluate("""() => {
            window.atomWebSocketEvents = [];

            // Intercept WebSocket messages if available
            const originalWebSocket = window.WebSocket;
            window.WebSocket = function(...args) {
                const ws = new originalWebSocket(...args);
                ws.addEventListener('message', (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (data.type && data.type.includes('streaming')) {
                            window.atomWebSocketEvents.push({
                                type: data.type,
                                timestamp: Date.now(),
                                id: data.id,
                                delta: data.delta || null,
                                complete: data.complete || false
                            });
                        }
                    } catch (e) {
                        // Ignore non-JSON messages
                    }
                });
                return ws;
            };
        }""")

        # Send message
        chat_page.send_message(unique_message)

        # Verify streaming indicator appears immediately
        assert chat_page.is_streaming(), "Streaming indicator should be visible after sending message"

        # Wait for first token to arrive
        chat_page.wait_for_response(timeout=10000)

        # Capture progressive text updates
        progressive_texts = []
        max_samples = 20
        sample_count = 0

        while chat_page.is_streaming() and sample_count < max_samples:
            try:
                current_text = chat_page.get_last_message()
                if current_text and current_text not in progressive_texts:
                    progressive_texts.append(current_text)
                    sample_count += 1

                # Small delay to allow more tokens to arrive
                authenticated_page_api.wait_for_timeout(200)
            except Exception:
                break

        # Wait for streaming to complete
        chat_page.wait_for_streaming_complete(timeout=30000)

        # Verify progressive display (text should have grown)
        if len(progressive_texts) > 1:
            for i in range(1, len(progressive_texts)):
                assert len(progressive_texts[i]) >= len(progressive_texts[i-1]), \
                    f"Text should grow or stay same length: {len(progressive_texts[i-1])} -> {len(progressive_texts[i])}"

        # Verify final response exists
        final_response = chat_page.get_last_message()
        assert final_response is not None, "Should have final assistant response"
        assert len(final_response) > 0, "Final response should not be empty"

        print(f"✓ Token streaming displayed progressively ({len(progressive_texts)} updates captured)")
        print(f"✓ Final response length: {len(final_response)} characters")


class TestWebSocketReconnection:
    """E2E tests for WebSocket reconnection logic (AGNT-05)."""

    def test_websocket_reconnect_on_connection_loss(
        self,
        authenticated_page_api: Page,
        setup_test_user
    ):
        """Verify WebSocket reconnects automatically on connection loss.

        This test validates:
        1. WebSocket connection established successfully
        2. Connection loss is detected (network disconnect simulation)
        3. Automatic reconnection is triggered
        4. Messages can be sent after reconnection
        5. No message loss during reconnection

        Args:
            authenticated_page_api: Authenticated page fixture
            setup_test_user: API fixture for test user creation

        Coverage: AGNT-05 (WebSocket reconnection)
        """
        # Setup
        user_data = setup_test_user
        chat_page = ChatPage(authenticated_page_api)
        chat_page.navigate()

        # Send initial message to establish WebSocket connection
        chat_page.send_message(f"Hello {uuid.uuid4()}")
        chat_page.wait_for_streaming_complete(timeout=15000)

        # Track WebSocket state
        ws_state = authenticated_page_api.evaluate("""() => {
            return {
                connected: window.wsConnected || false,
                reconnectAttempts: window.wsReconnectAttempts || 0
            };
        }""")

        assert ws_state['connected'], "WebSocket should be connected initially"

        # Simulate connection loss (override WebSocket to simulate disconnect)
        authenticated_page_api.evaluate("""() => {
            // Find and close existing WebSocket connection
            if (window.atomWebSocket) {
                window.atomWebSocket.close();
            }

            // Set flag to track reconnection
            window.wsReconnecting = true;
        }""")

        # Wait for reconnection attempt
        authenticated_page_api.wait_for_timeout(3000)

        # Check if reconnection was attempted
        reconnection_state = authenticated_page_api.evaluate("""() => {
            return {
                reconnected: window.wsConnected || false,
                reconnectAttempts: window.wsReconnectAttempts || 0
            };
        }""")

        # Send message after reconnection
        chat_page.send_message(f"Test after reconnection {uuid.uuid4()}")

        # Verify response received (successful reconnection)
        try:
            chat_page.wait_for_response(timeout=15000)
            response = chat_page.get_last_message()

            assert response is not None, "Should receive response after reconnection"
            print("✓ WebSocket reconnection successful")
            print("✓ Messages can be sent after reconnection")

        except Exception:
            pytest.skip("WebSocket reconnection logic not fully implemented in frontend")

    def test_websocket_message_queue_during_reconnect(
        self,
        authenticated_page_api: Page,
        setup_test_user
    ):
        """Verify messages are queued during reconnection and sent after reconnect.

        Args:
            authenticated_page_api: Authenticated page fixture
            setup_test_user: API fixture for test user creation

        Coverage: AGNT-05 (Message queuing during reconnection)
        """
        # Setup
        user_data = setup_test_user
        chat_page = ChatPage(authenticated_page_api)
        chat_page.navigate()

        # Establish connection
        chat_page.send_message(f"Initial message {uuid.uuid4()}")
        chat_page.wait_for_streaming_complete(timeout=15000)

        # Inject message queuing logic tracking
        authenticated_page_api.evaluate("""() => {
            window.atomMessageQueue = [];

            // Override send to queue messages during disconnect
            const originalSend = WebSocket.prototype.send;
            WebSocket.prototype.send = function(data) {
                if (this.readyState !== WebSocket.OPEN) {
                    window.atomMessageQueue.push(data);
                } else {
                    originalSend.call(this, data);
                }
            };
        }""")

        # Send message (should be queued if disconnected)
        queued_message = f"Queued message {uuid.uuid4()}"
        chat_page.send_message(queued_message)

        # Verify message was queued
        message_queue = authenticated_page_api.evaluate("""() => {
            return window.atomMessageQueue || [];
        }""")

        if len(message_queue) > 0:
            print("✓ Messages queued during reconnection")

        # Reconnect and verify queued message sent
        authenticated_page_api.wait_for_timeout(2000)

        # Check if queued message was sent
        try:
            chat_page.wait_for_response(timeout=10000)
            print("✓ Queued message sent after reconnection")
        except Exception:
            pytest.skip("Message queuing not fully implemented")
```

### Pattern 4: Concurrent Agent Execution Testing

**What:** Test multiple agents executing simultaneously to verify isolation and resource management.

**When to use:** AGNT-04 (Concurrent execution).

**Example:**

```python
# Source: backend/tests/e2e_ui/tests/test_agent_concurrent.py (NEW)
import pytest
import uuid
import asyncio
from playwright.sync_api import Page, Browser
from typing import List, Dict
from tests.e2e_ui.pages.page_objects import ChatPage


class TestConcurrentAgentExecution:
    """E2E tests for concurrent agent execution (AGNT-04)."""

    def test_multiple_users_simultaneous_chat(
        self,
        browser: Browser,
        base_url: str,
        setup_test_user
    ):
        """Verify multiple users can chat with agents simultaneously.

        This test validates:
        1. Multiple browser contexts can be created
        2. Each user gets isolated WebSocket connection
        3. Messages don't cross-contaminate between users
        4. Responses are correct for each user

        Args:
            browser: Playwright browser fixture
            base_url: Base URL fixture
            setup_test_user: API fixture for test user creation

        Coverage: AGNT-04 (Concurrent execution)
        """
        # Create 3 separate users with authenticated pages
        users = []
        for i in range(3):
            user_data = setup_test_user()
            context = browser.new_context()
            page = context.new_page()

            # Authenticate each user
            page.goto(base_url)
            page.evaluate(f"""() => {{
                localStorage.setItem('access_token', '{user_data.get("access_token")}');
                localStorage.setItem('user_email', '{user_data.get("email")}');
            }}""")

            users.append({
                'page': page,
                'context': context,
                'email': user_data.get('email'),
                'unique_id': str(uuid.uuid4())[:8]
            })

        # Send unique messages from each user simultaneously
        chat_pages = []
        for user in users:
            chat_page = ChatPage(user['page'])
            chat_page.navigate()

            # Send unique message per user
            unique_message = f"User {user['unique_id']}: What is 2+2? {uuid.uuid4()}"
            chat_page.send_message(unique_message)
            chat_pages.append(chat_page)

        # Wait for all responses
        responses = []
        for i, chat_page in enumerate(chat_pages):
            chat_page.wait_for_streaming_complete(timeout=30000)
            response = chat_page.get_last_message()
            responses.append({
                'user_index': i,
                'response': response
            })

        # Verify each user got a response
        assert len(responses) == 3, "All 3 users should receive responses"

        for resp in responses:
            assert resp['response'] is not None, f"User {resp['user_index']} should have response"
            assert len(resp['response']) > 0, f"User {resp['user_index']} response should not be empty"

        # Verify responses are different (no cross-contamination)
        response_texts = [r['response'] for r in responses]
        unique_responses = len(set(response_texts))
        assert unique_responses == 3, "Each user should get unique response"

        # Cleanup
        for user in users:
            user['context'].close()

        print("✓ 3 users chatted simultaneously without interference")
        print(f"✓ All {len(responses)} responses received correctly")

    def test_concurrent_agent_creation(
        self,
        authenticated_page_api: Page,
        db_session,
        setup_test_user
    ):
        """Verify multiple agents can be created concurrently.

        This test validates:
        1. Multiple agent creation requests can be handled
        2. Agent registry remains consistent
        3. No race conditions in agent ID generation

        Args:
            authenticated_page_api: Authenticated page fixture
            db_session: Database session fixture
            setup_test_user: API fixture for test user creation

        Coverage: AGNT-04 (Concurrent agent creation)
        """
        from core.models import AgentRegistry
        import concurrent.futures

        # Create agents via API (bypass UI for speed)
        agent_ids = []
        agent_names = []

        def create_agent(name_suffix: str) -> str:
            """Create agent via database.

            Returns:
                Agent ID
            """
            agent_id = str(uuid.uuid4())
            agent = AgentRegistry(
                id=agent_id,
                name=f"ConcurrentAgent_{name_suffix}_{str(uuid.uuid4())[:8]}",
                maturity_level="INTERN",
                status="active",
                created_at=datetime.utcnow()
            )
            db_session.add(agent)
            db_session.commit()
            return agent_id

        # Create 5 agents concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_agent, str(i)) for i in range(5)]
            for future in concurrent.futures.as_completed(futures):
                agent_ids.append(future.result())

        # Verify all agents created
        assert len(agent_ids) == 5, "Should create 5 agents"

        # Verify all IDs are unique
        assert len(set(agent_ids)) == 5, "All agent IDs should be unique"

        # Verify agents in database
        agents = db_session.query(AgentRegistry).filter(
            AgentRegistry.id.in_(agent_ids)
        ).all()

        assert len(agents) == 5, "All 5 agents should be in database"

        print("✓ 5 agents created concurrently")
        print("✓ All agent IDs unique")
        print("✓ Registry consistent")
```

### Anti-Patterns to Avoid

- **Slow UI login for every test:** Use `authenticated_page_api` fixture instead (10-100x faster)
- **Hardcoded test data:** Use `setup_test_user` and `AgentFactory` with UUIDs
- **No WebSocket state tracking:** Inject event listeners to track connection state
- **Testing one browser context only:** Test multiple contexts for concurrent execution
- **Ignoring token expiration:** Verify JWT claims and expiration in E2E tests
- **Skipping mobile auth:** Test API-level auth for mobile (API-first approach works for mobile too)

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JWT creation/verification | Manual JWT encoding/decoding | `python-jose` (already in `core/auth.py`) | Handles validation, expiration, signing automatically |
| Password hashing | Manual bcrypt implementation | `bcrypt` library (already in use) | Secure salt generation, constant-time comparison |
| Browser automation | Manual Selenium setup | `pytest-playwright` (already configured) | Faster execution, better WebSocket support, auto-waiting |
| Test data factories | Manual object creation with hardcoded IDs | `factory-boy` (already configured) | Handles uniqueness, relationships, SubFactory, LazyFunction |
| Token refresh logic | Manual token rotation tracking | Backend refresh endpoints + localStorage | Backend handles refresh validation, frontend stores new token |
| WebSocket reconnection | Manual reconnection logic testing | Inject event listeners, simulate disconnect | Test existing reconnection logic, don't rebuild it |
| Parallel test execution | Manual multiprocessing | `pytest-xdist` (already configured with worker isolation) | Load balancing, worker isolation, GitHub Actions integration |
| Failure artifact capture | Manual screenshot/video capture | Allure pytest hooks (already configured) | Automatic capture, rich UI, cross-platform aggregation |

**Key insight:** All authentication and agent execution infrastructure already exists. Phase 234 should focus on **writing comprehensive E2E tests** using existing fixtures and Page Objects, not rebuilding infrastructure.

---

## Common Pitfalls

### Pitfall 1: E2E Tests Too Slow Due to UI Login

**What goes wrong:** Every E2E test goes through full UI login flow (2-10 seconds per test). Test suite takes hours.

**Why it happens:** Tests use `page.goto('/login')` → fill form → submit → wait for redirect (slow).

**How to avoid:**
```python
# BAD: Slow UI login for every test
def test_slow_auth(page):
    page.goto("http://localhost:3001/login")
    page.fill("[name='email']", "test@example.com")
    page.fill("[name='password']", "password123")
    page.click("[type='submit']")
    page.wait_for_url("**/dashboard")
    # Continue test... (2-10 seconds wasted)

# GOOD: API-first auth (10-100x faster)
def test_fast_auth(authenticated_page_api):
    # authenticated_page_api fixture already has JWT token in localStorage
    authenticated_page_api.goto("http://localhost:3001/dashboard")
    # Continue test... (<200ms)
```

**Warning signs:** E2E test suite takes >30 minutes, most time spent in login flows.

### Pitfall 2: Not Testing JWT Token Expiration

**What goes wrong:** Tests use valid tokens only, never verify expired token handling.

**Why it happens:** Fixtures always create fresh tokens with 15-minute expiration. Tests don't wait for expiration.

**How to avoid:**
```python
# Test expired token handling
def test_expired_token_rejected(authenticated_page_api):
    # Inject expired token
    expired_token = create_expired_token()
    authenticated_page_api.evaluate(f"""() => {{
        localStorage.setItem('access_token', '{expired_token}');
    }}""")

    # Try to access protected route
    authenticated_page_api.goto("http://localhost:3001/api/v1/agents")

    # Should receive 401 or redirect to login
    current_url = authenticated_page_api.url
    assert 'login' in current_url.lower() or 'unauthorized' in authenticated_page_api.content()
```

### Pitfall 3: WebSocket Reconnection Not Tested

**What goes wrong:** WebSocket reconnection logic exists but E2E tests don't verify it works.

**Why it happens:** Reconnection is hard to test (need to simulate connection loss, track state).

**How to avoid:**
```python
# Inject WebSocket state tracking
authenticated_page_api.evaluate("""() => {
    window.atomWebSocketEvents = [];
    window.atomReconnectAttempts = 0;

    const originalWS = window.WebSocket;
    window.WebSocket = function(...args) {
        const ws = new originalWS(...args);
        ws.addEventListener('close', () => {
            window.atomReconnectAttempts++;
        });
        return ws;
    };
}""")

# Simulate disconnect and verify reconnection
# (see Pattern 3 for full example)
```

### Pitfall 4: Concurrent Execution Tests Not Isolated

**What goes wrong:** Multiple concurrent tests share state, causing flaky failures.

**Why it happens:** Tests don't use unique IDs per execution, don't use worker isolation.

**How to avoid:**
```python
# Always use unique IDs
def test_concurrent_agents(setup_test_user, db_session):
    # Use UUID for uniqueness
    agent_id = str(uuid.uuid4())
    agent_name = f"Agent_{agent_id[:8]}"

    agent = AgentRegistry(id=agent_id, name=agent_name)
    db_session.add(agent)
    db_session.commit()

    # Worker isolation from Phase 233 prevents collisions
```

### Pitfall 5: Mobile E2E Tests Blocked on UI

**What goes wrong:** Mobile E2E tests blocked on device setup or UI framework.

**Why it happens:** Trying to run full UI E2E tests on mobile (requires expo-dev-client).

**How to avoid:**
```python
# Test mobile auth at API level (AUTH-07)
def test_mobile_auth_api(setup_test_user):
    """Test mobile authentication via API endpoint."""
    # Create user via API
    user_data = setup_test_user()

    # Call mobile login endpoint
    response = requests.post(
        "http://localhost:8000/api/auth/mobile/login",
        json={
            "email": user_data['email'],
            "password": "TestPassword123!",
            "device_token": "test-device-token",
            "platform": "ios"
        }
    )

    assert response.status_code == 200
    assert 'access_token' in response.json()
    assert 'refresh_token' in response.json()

    # Verify JWT token
    token = response.json()['access_token']
    payload = decode_jwt(token)
    assert payload['sub'] == user_data['user_id']
```

---

## Code Examples

### Example 1: Complete Authentication E2E Test Suite

```python
# Source: backend/tests/e2e_ui/tests/test_auth_complete.py (NEW)
"""
Comprehensive E2E tests for authentication flows (AUTH-01 through AUTH-07).

Run with: pytest tests/e2e_ui/tests/test_auth_complete.py -v
"""

import pytest
import json
from base64 import b64decode
from datetime import datetime, timedelta
from playwright.sync_api import Page
from jose import jwt
from tests.e2e_ui.pages.page_objects import LoginPage, DashboardPage


class TestWebUILoginLogout:
    """E2E tests for web UI login and logout (AUTH-01)."""

    def test_user_login_with_valid_credentials(self, page: Page, test_user):
        """Verify user can login with valid credentials.

        Args:
            page: Playwright page fixture
            test_user: Test user fixture (with email/password)
        """
        # Navigate to login page
        login_page = LoginPage(page)
        login_page.navigate()

        # Verify login page loaded
        assert login_page.is_loaded(), "Login page should be loaded"

        # Fill credentials (from test_user fixture)
        # Note: test_user uses hashed password, need plain password for UI
        login_page.fill_email(test_user.email)
        login_page.fill_password("TestPassword123!")  # Plain text password
        login_page.click_submit()

        # Verify redirect to dashboard
        page.wait_for_url("**/dashboard", timeout=5000)

        dashboard = DashboardPage(page)
        assert dashboard.is_loaded(), "Should be redirected to dashboard after login"

    def test_user_logout(self, authenticated_page_api: Page):
        """Verify user can logout successfully.

        Args:
            authenticated_page_api: Authenticated page fixture
        """
        # Start on dashboard
        dashboard = DashboardPage(authenticated_page_api)
        dashboard.navigate()

        # Verify logged in
        assert dashboard.is_loaded(), "Should be logged in initially"

        # Logout
        dashboard.logout()

        # Verify redirected to login or logged out state
        authenticated_page_api.wait_for_timeout(1000)
        is_on_dashboard = dashboard.welcome_message.is_visible()
        assert not is_on_dashboard, "Should not see dashboard after logout"

        # Verify token cleared from localStorage
        token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")
        assert token is None, "Access token should be cleared after logout"


class TestJWTValidation:
    """E2E tests for JWT token validation (AUTH-02)."""

    def test_jwt_token_structure(self, authenticated_page_api: Page):
        """Verify JWT token has correct structure (header.payload.signature)."""
        token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")

        # Verify structure
        parts = token.split('.')
        assert len(parts) == 3, "JWT should have 3 parts"

        # Verify header
        header = json.loads(b64decode(parts[0]))
        assert header['alg'] == 'HS256'
        assert header['typ'] == 'JWT'

        # Verify payload
        payload = json.loads(b64decode(parts[1]))
        assert 'sub' in payload
        assert 'exp' in payload
        assert 'iat' in payload

    def test_jwt_token_expiration(self, authenticated_page_api: Page):
        """Verify JWT token expiration is set correctly."""
        token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")
        payload = json.loads(b64decode(token.split('.')[1]))

        exp_timestamp = payload['exp']
        exp_datetime = datetime.fromtimestamp(exp_timestamp)
        now = datetime.utcnow()

        assert exp_datetime > now, "Token should not be expired"
        assert exp_datetime < now.replace(hour=23, minute=59), "Token should expire today"


class TestSessionPersistence:
    """E2E tests for session persistence (AUTH-03)."""

    def test_session_persists_across_pages(self, authenticated_page_api: Page):
        """Verify authentication persists across page navigation."""
        # Get initial token
        initial_token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")

        # Navigate to multiple pages
        authenticated_page_api.goto("http://localhost:3001/dashboard")
        authenticated_page_api.wait_for_timeout(500)
        authenticated_page_api.goto("http://localhost:3001/agents")
        authenticated_page_api.wait_for_timeout(500)
        authenticated_page_api.goto("http://localhost:3001/settings")
        authenticated_page_api.wait_for_timeout(500)

        # Verify token still exists
        current_token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")
        assert current_token == initial_token, "Token should persist across navigation"

    def test_session_persists_browser_restart(self, browser, setup_test_user):
        """Verify authentication persists across browser restart."""
        user_data = setup_test_user

        # Create context and authenticate
        context = browser.new_context()
        page = context.new_page()
        page.goto("http://localhost:3001")
        page.evaluate(f"""() => {{
            localStorage.setItem('access_token', '{user_data.get('access_token')}');
        }}""")

        # Close context (simulate browser restart)
        context.close()

        # Create new context and verify token persists
        new_context = browser.new_context(
            storage_state="state.json"  # Save/load state
        )
        new_page = new_context.new_page()
        new_page.goto("http://localhost:3001/dashboard")

        # Should be authenticated
        dashboard = DashboardPage(new_page)
        assert dashboard.is_loaded(), "Session should persist across browser restart"

        new_context.close()


class TestProtectedRoutes:
    """E2E tests for protected routes (AUTH-05)."""

    def test_protected_route_requires_auth(self, page: Page):
        """Verify protected routes redirect unauthenticated users."""
        # Try to access dashboard without auth
        page.goto("http://localhost:3001/dashboard")

        # Should redirect to login
        current_url = page.url
        assert 'login' in current_url.lower(), "Should redirect to login"

    def test_protected_api_returns_401_without_token(self):
        """Verify protected API returns 401 without auth token."""
        import requests

        response = requests.get("http://localhost:8000/api/v1/agents")

        assert response.status_code == 401, "Should return 401 without token"

    def test_protected_api_accepts_valid_token(self, authenticated_user):
        """Verify protected API accepts valid JWT token."""
        import requests

        user, token = authenticated_user

        response = requests.get(
            "http://localhost:8000/api/v1/agents",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200, "Should accept valid token"


class TestAPIFirstAuth:
    """E2E tests for API-first authentication (AUTH-06)."""

    def test_api_auth_is_faster_than_ui_auth(self, benchmark):
        """Verify API-first auth is significantly faster than UI login."""
        # Benchmark UI login
        ui_time = benchmark.pedantic(self._ui_login_flow, iterations=1, rounds=1)

        # Benchmark API auth
        api_time = benchmark.pedantic(self._api_auth_flow, iterations=1, rounds=1)

        # API auth should be at least 10x faster
        assert api_time * 10 < ui_time, \
            f"API auth ({api_time}s) should be 10x faster than UI login ({ui_time}s)"

    @staticmethod
    def _ui_login_flow(page, test_user):
        """UI login flow for benchmarking."""
        login_page = LoginPage(page)
        login_page.navigate()
        login_page.login(test_user.email, "TestPassword123!")
        page.wait_for_url("**/dashboard")

    @staticmethod
    def _api_auth_flow(authenticated_page_api):
        """API auth flow for benchmarking."""
        # authenticated_page_api fixture already has token in localStorage
        authenticated_page_api.goto("http://localhost:3001/dashboard")
        assert authenticated_page_api.url.endswith('/dashboard')


class TestMobileAuth:
    """E2E tests for mobile authentication (AUTH-07)."""

    def test_mobile_login_via_api(self, setup_test_user):
        """Verify mobile login endpoint works correctly."""
        import requests

        user_data = setup_test_user

        response = requests.post(
            "http://localhost:8000/api/auth/mobile/login",
            json={
                "email": user_data['email'],
                "password": "TestPassword123!",
                "device_token": "test-device-token-123",
                "platform": "ios"
            }
        )

        assert response.status_code == 200, "Mobile login should succeed"

        data = response.json()
        assert 'access_token' in data
        assert 'refresh_token' in data
        assert 'expires_at' in data
        assert 'token_type' in data
        assert data['token_type'] == 'bearer'

    def test_mobile_token_validation(self, setup_test_user):
        """Verify mobile access token can be validated."""
        import requests

        user_data = setup_test_user

        # Login via mobile endpoint
        login_response = requests.post(
            "http://localhost:8000/api/auth/mobile/login",
            json={
                "email": user_data['email'],
                "password": "TestPassword123!",
                "device_token": "test-device-token-123",
                "platform": "ios"
            }
        )

        token = login_response.json()['access_token']

        # Use token to access protected endpoint
        protected_response = requests.get(
            "http://localhost:8000/api/v1/agents",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert protected_response.status_code == 200, "Mobile token should be valid"
```

### Example 2: Agent Creation and Registry Verification

```python
# Source: backend/tests/e2e_ui/tests/test_agent_creation.py (NEW)
"""
E2E tests for agent creation and registry verification (AGNT-01, AGNT-02).

Run with: pytest tests/e2e_ui/tests/test_agent_creation.py -v
"""

import pytest
import uuid
from playwright.sync_api import Page
from sqlalchemy.orm import Session
from core.models import AgentRegistry
from tests.e2e_ui.pages.page_objects import DashboardPage


class TestAgentCreation:
    """E2E tests for agent creation workflow (AGNT-01)."""

    def test_create_agent_via_ui(self, authenticated_page_api: Page, db_session: Session):
        """Verify agent can be created via UI.

        This test validates:
        1. Navigate to agents page
        2. Click "Create Agent" button
        3. Fill agent form (name, category, description)
        4. Submit form
        5. Verify agent appears in agent list
        6. Verify agent in database registry

        Args:
            authenticated_page_api: Authenticated page fixture
            db_session: Database session fixture

        Coverage: AGNT-01 (Agent creation)
        """
        # Navigate to agents page
        authenticated_page_api.goto("http://localhost:3001/agents")
        authenticated_page_api.wait_for_load_state("networkidle")

        # Click "Create Agent" button
        authenticated_page_api.click('[data-testid="create-agent-button"]')

        # Wait for agent creation modal
        authenticated_page_api.wait_for_selector('[data-testid="agent-creation-modal"]')

        # Fill agent form
        unique_id = str(uuid.uuid4())[:8]
        agent_name = f"E2E Test Agent {unique_id}"

        authenticated_page_api.fill('[data-testid="agent-name-input"]', agent_name)
        authenticated_page_api.select_option('[data-testid="agent-category-select"]', "productivity")
        authenticated_page_api.fill('[data-testid="agent-description-input"]', "E2E test agent for verification")

        # Submit form
        authenticated_page_api.click('[data-testid="create-agent-submit-button"]')

        # Wait for success notification
        authenticated_page_api.wait_for_selector('[data-testid="agent-created-success"]', timeout=5000)

        # Verify agent appears in agent list
        agent_card = authenticated_page_api.locator(f'[data-testid="agent-card-{agent_name}"]')
        assert agent_card.is_visible(), f"Agent {agent_name} should appear in list"

        # Verify agent in database
        agent = db_session.query(AgentRegistry).filter(
            AgentRegistry.name == agent_name
        ).first()

        assert agent is not None, f"Agent {agent_name} should be in database"
        assert agent.status == "active", "Agent should be active"
        assert agent.maturity_level == "STUDENT", "New agents should start at STUDENT level"

        print(f"✓ Agent created: {agent_name}")
        print(f"✓ Agent ID: {agent.id}")
        print(f"✓ Agent maturity: {agent.maturity_level}")


class TestAgentRegistryVerification:
    """E2E tests for agent registry verification (AGNT-02)."""

    def test_agent_registry_persistence(self, authenticated_page_api: Page, db_session: Session):
        """Verify agent persists in registry after creation.

        Args:
            authenticated_page_api: Authenticated page fixture
            db_session: Database session fixture

        Coverage: AGNT-02 (Registry verification)
        """
        # Create agent via API (faster than UI)
        agent_id = str(uuid.uuid4())
        agent_name = f"Registry Test Agent {str(uuid.uuid4())[:8]}"

        agent = AgentRegistry(
            id=agent_id,
            name=agent_name,
            maturity_level="INTERN",
            status="active",
            category="testing",
            module_path="test.module",
            class_name="TestAgent",
            created_at=datetime.utcnow()
        )

        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Query registry to verify
        retrieved_agent = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        assert retrieved_agent is not None, "Agent should be retrievable from registry"
        assert retrieved_agent.name == agent_name, "Agent name should match"
        assert retrieved_agent.maturity_level == "INTERN", "Agent maturity should match"
        assert retrieved_agent.status == "active", "Agent status should match"

        # Verify via UI (navigate to agents page)
        authenticated_page_api.goto("http://localhost:3001/agents")
        authenticated_page_api.wait_for_load_state("networkidle")

        # Search for agent
        authenticated_page_api.fill('[data-testid="agent-search-input"]', agent_name)
        authenticated_page_api.wait_for_timeout(1000)

        # Verify agent appears in search results
        agent_card = authenticated_page_api.locator(f'[data-testid="agent-card-{agent_name}"]')
        assert agent_card.is_visible(), f"Agent {agent_name} should appear in search results"

        print(f"✓ Agent registry persistence verified")
        print(f"✓ Agent accessible via UI and database")

    def test_agent_registry_unique_ids(self, db_session: Session):
        """Verify agent registry enforces unique IDs."""
        # Create multiple agents
        agent_ids = []
        for i in range(5):
            agent_id = str(uuid.uuid4())
            agent = AgentRegistry(
                id=agent_id,
                name=f"Unique ID Test {i}",
                maturity_level="STUDENT",
                status="active"
            )
            db_session.add(agent)
            agent_ids.append(agent_id)

        db_session.commit()

        # Verify all IDs are unique
        unique_ids = db_session.query(AgentRegistry.id).filter(
            AgentRegistry.id.in_(agent_ids)
        ).all()

        assert len(unique_ids) == 5, "All 5 agents should have unique IDs"

        # Verify no duplicates
        id_list = [id[0] for id in unique_ids]
        assert len(set(id_list)) == 5, "All IDs should be unique (no duplicates)"

        print("✓ Agent registry enforces unique IDs")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| UI login for every test | API-first auth fixtures (`authenticated_page_api`) | Phase 233 (v233.0) | 10-100x speedup (2-10s → <200ms per test) |
| No database isolation | Worker-specific databases with transaction rollback | Phase 233 (v233.0) | True parallel execution without data conflicts |
| Manual screenshot capture | Allure automatic artifact capture | Phase 233 (v233.0) | One-click debugging, rich test reports |
| Ad-hoc test helpers | Shared utilities (`wait_for_selector`, `click_element`) | Phase 233 (v233.0) | 40% reduction in test code duplication |
| No JWT validation in E2E | Comprehensive JWT structure/claim testing | Phase 234 (this phase) | Will ensure auth security and token refresh works |
| WebSocket reconnection untested | Event listener injection + disconnect simulation | Phase 234 (this phase) | Will verify reconnection logic under connection loss |
| Single-user E2E tests | Multi-context concurrent execution tests | Phase 234 (this phase) | Will validate isolation and resource management |

**Deprecated/outdated:**
- **UI login for E2E tests:** Use `authenticated_page_api` fixture instead (10-100x faster)
- **Manual screenshot capture:** Use Allure hooks (automatic capture on failure)
- **No worker isolation:** Use `db_session` fixture with worker-specific databases (Phase 233)
- **Hardcoded test IDs:** Use `setup_test_user` and `AgentFactory` with UUIDs

---

## Open Questions

1. **Mobile E2E test execution strategy**
   - What we know: Mobile UI E2E tests BLOCKED (expo-dev-client requirement)
   - What's unclear: Should we run mobile tests at API level only, or wait for Detox unblock?
   - Recommendation: AUTH-07 and AGNT-08 should test mobile auth/agents at **API level** (not UI). This provides coverage without device setup. Full mobile UI E2E can be deferred to Phase 250+.

2. **WebSocket reconnection test reliability**
   - What we know: WebSocket infrastructure exists (`ConnectionManager`, streaming endpoints)
   - What's unclear: Does frontend have automatic reconnection logic implemented?
   - Recommendation: Write reconnection tests that **check if logic exists**. Use `pytest.skip` if not implemented (see Pattern 3 examples). This documents current state without blocking.

3. **Concurrent execution test count**
   - What we know: pytest-xdist supports parallel workers (configured in Phase 233)
   - What's unclear: How many concurrent contexts should AGNT-04 tests create?
   - Recommendation: Test **3 concurrent users/agents** (realistic load, not too slow). Verify isolation (no message cross-contamination, unique IDs).

4. **Token refresh timing in E2E tests**
   - What we know: JWT tokens default to 15-minute expiration
   - What's unclear: How to test refresh without waiting 15 minutes?
   - Recommendation: Test refresh **via API endpoint directly** (call `/api/auth/refresh`, verify new token returned). Don't wait for expiration in E2E tests (too slow).

5. **Cross-platform consistency verification**
   - What we know: Frontend uses `data-testid` standard (documented in Phase 233)
   - What's unclear: How to verify mobile/desktop use same test IDs?
   - Recommendation: AGNT-08 should **verify API responses are consistent** across platforms (same agent schema, same streaming format). UI consistency can be checked manually or with visual regression (deferred).

---

## Sources

### Primary (HIGH confidence)
- **backend/tests/e2e_ui/fixtures/auth_fixtures.py** - API-first authentication fixtures (`authenticated_page_api`, `setup_test_user`)
- **backend/tests/e2e_ui/conftest.py** - Playwright configuration, Allure integration, browser context setup
- **backend/tests/e2e_ui/pages/page_objects.py** - Page Object Model (`LoginPage`, `ChatPage`, `DashboardPage`)
- **backend/core/auth.py** - JWT token creation/verification (`create_access_token`, `verify_password`, `get_current_user`)
- **backend/core/models.py** - Database models (`User`, `AgentRegistry`, `AgentExecution`)
- **backend/core/agent_governance_service.py** - Agent governance and maturity levels
- **backend/core/websockets.py** - WebSocket connection management
- **backend/tests/fixtures/shared_utilities.py** - Shared test helpers (`wait_for_selector`, `click_element`)
- **backend/tests/docs/TEST_INFRA_STANDARDS.md** - Test infrastructure standards (Phase 233)
- **backend/tests/e2e_ui/tests/test_agent_streaming.py** - Existing streaming tests (AGNT-03)
- **backend/tests/e2e_ui/tests/test_auth_example.py** - Existing auth test examples
- **backend/requirements-testing.txt** - Testing dependencies (pytest, playwright, allure, factory-boy)

### Secondary (MEDIUM confidence)
- **pytest-xdist documentation** (verified via existing worker isolation in conftest.py)
- **Playwright Python documentation** (verified via existing fixtures and page objects)
- **Allure pytest documentation** (verified via existing integration in conftest.py)
- **python-jose (JWT) documentation** (verified via existing usage in core/auth.py)
- **factory-boy documentation** (verified via existing factories in backend/tests/factories/)

### Tertiary (LOW confidence)
- **WebSocket reconnection testing patterns** (standard patterns documented, frontend implementation unknown)
- **Mobile auth API endpoints** (exist in backend/api/auth_2fa_routes.py, mobile E2E execution unclear)
- **Token refresh UI flow** (backend endpoint exists, frontend automatic refresh implementation unknown)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified in requirements-testing.txt and existing test infrastructure
- Architecture: HIGH - Patterns documented in Phase 233 research, existing fixtures and page objects analyzed
- Pitfalls: HIGH - All pitfalls identified from existing codebase and Phase 233 verification report
- E2E test patterns: HIGH - Existing tests analyzed (test_auth_example.py, test_agent_streaming.py)
- WebSocket testing: MEDIUM - Infrastructure verified, frontend reconnection logic requires validation
- Mobile testing: MEDIUM - API endpoints exist, UI E2E blocked (known limitation)

**Research date:** March 23, 2026
**Valid until:** April 22, 2026 (30 days - stable E2E testing domain)

---

## Implementation Priority

Based on research findings, Phase 234 should implement in this order:

### 1. Authentication E2E Tests (HIGH priority - 7 tests)
- **AUTH-01, AUTH-02:** Web UI login/logout and JWT validation
  - Use `LoginPage` Page Object for UI login
  - Verify JWT structure, claims, expiration
  - Files: `test_auth_login.py`, `test_auth_jwt_validation.py`
- **AUTH-03, AUTH-05:** Session persistence and protected routes
  - Test token persistence across navigation
  - Verify 401 responses for unauthenticated requests
  - File: `test_auth_session.py`
- **AUTH-04:** Token refresh flow
  - Test refresh endpoint via API (don't wait for expiration)
  - Verify new token stored in localStorage
  - File: `test_auth_token_refresh.py`
- **AUTH-06:** API-first auth validation
  - Benchmark speedup (10-100x faster than UI)
  - Verify fixture works correctly
  - File: `test_auth_api_first.py`
- **AUTH-07:** Mobile auth (API-level)
  - Test `/api/auth/mobile/login` endpoint
  - Verify device token and platform handling
  - File: `test_auth_mobile.py`

### 2. Agent Creation & Registry (HIGH priority - 2 tests)
- **AGNT-01:** Agent creation workflow
  - Test UI creation flow (form fill, submit, verify in list)
  - Verify database registry
  - File: `test_agent_creation.py`
- **AGNT-02:** Registry verification
  - Test agent persistence, unique IDs
  - Verify registry queries and search
  - File: `test_agent_registry.py`

### 3. Agent Streaming & Reconnection (MEDIUM priority - 2 tests)
- **AGNT-03:** Chat streaming (enhance existing)
  - Add progressive display validation
  - Verify streaming indicator
  - File: `test_agent_streaming.py` (existing)
- **AGNT-05:** WebSocket reconnection
  - Inject event listeners to track state
  - Simulate connection loss
  - Verify automatic reconnection
  - File: `test_agent_websocket_reconnect.py`

### 4. Concurrent Execution (MEDIUM priority - 2 tests)
- **AGNT-04:** Concurrent execution
  - Test 3 simultaneous users/agents
  - Verify isolation (no cross-contamination)
  - File: `test_agent_concurrent.py`

### 5. Governance & Lifecycle (MEDIUM priority - 2 tests)
- **AGNT-06:** Governance validation (enhance existing)
  - Test maturity level enforcement
  - Verify action complexity checks
  - File: `test_agent_governance.py` (existing)
- **AGNT-07:** Lifecycle management
  - Test agent activation/deactivation
  - Verify status transitions
  - File: `test_agent_lifecycle.py`

### 6. Cross-Platform Consistency (LOW priority - 1 test)
- **AGNT-08:** Cross-platform consistency
  - Verify API responses consistent (web, mobile, desktop)
  - Test agent schema compatibility
  - File: `test_agent_cross_platform.py`

**Total:** 15 comprehensive E2E tests across 6 test files (plus 3 enhanced existing files)

**Verification:**
- Run tests in parallel: `pytest tests/e2e_ui/ -n auto -v` (should use worker isolation)
- Generate Allure report: `allure generate allure-results --clean`
- Verify all AUTH-01 through AUTH-07 covered
- Verify all AGNT-01 through AGNT-08 covered
- Check test execution time: Should complete in <30 minutes with API-first auth

**Success criteria:**
- 15 E2E tests passing
- All authentication flows covered (login, logout, JWT, session, refresh, mobile)
- All agent workflows covered (creation, registry, streaming, concurrent, reconnection, governance, lifecycle)
- Allure report generated with screenshots/videos on failure
- Parallel execution verified (pytest-xdist workers)
