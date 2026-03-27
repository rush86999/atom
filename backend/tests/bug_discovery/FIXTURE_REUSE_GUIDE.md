# Bug Discovery Fixture Reuse Guide

## Overview

Bug discovery tests MUST reuse existing fixtures from `tests/e2e_ui/fixtures/` to avoid duplication and ensure consistency. This guide documents all available fixtures and how to use them.

**Benefits:**

- **10-100x faster authentication**: API-first auth (JWT in localStorage) vs UI login (2-10s)
- **Worker-based database isolation**: Parallel test execution without conflicts
- **No duplication**: Single source of truth for test infrastructure
- **Consistent behavior**: All tests use same auth/db setup

**Why This Matters:**

Bug discovery tests (fuzzing, chaos engineering, property-based testing, browser discovery) are often created as separate test suites with their own fixtures. This leads to:
- Duplicate code (same fixtures defined multiple times)
- Inconsistent behavior (different fixtures work differently)
- Slower tests (UI login instead of API-first auth)
- Maintenance burden (changes must be synced across fixtures)

By reusing existing fixtures, bug discovery tests benefit from:
- Fast, reliable authentication (10-100x speedup)
- Proven database isolation (worker-specific schemas)
- Consistent test data (factories with realistic defaults)
- Single maintenance point (fix once, benefit all tests)

**Directory Structure:**

```
backend/tests/
├── e2e_ui/
│   ├── fixtures/
│   │   ├── auth_fixtures.py         # API-first authentication (test_user, authenticated_user, authenticated_page)
│   │   ├── database_fixtures.py     # Database isolation (db_session, clean_database, worker schemas)
│   │   ├── api_fixtures.py          # API setup utilities (setup_test_user, setup_test_project)
│   │   └── test_data_factory.py     # Factory functions (user_factory, agent_factory, skill_factory)
│   └── pages/
│       └── page_objects.py          # Page Object Model (LoginPage, DashboardPage, ChatPage)
├── fuzzing/                         # Atheris fuzzing tests
├── browser_discovery/               # Playwright bug discovery tests
├── chaos/                           # Chaos engineering tests
├── property_tests/                  # Hypothesis property-based tests
└── bug_discovery/                   # This directory (documentation, templates)
```

## Authentication Fixtures

### `test_user`

Creates a test user with UUID v4 email for uniqueness.

**Location:** `tests/e2e_ui/fixtures/auth_fixtures.py`

**Scope:** Function (new user per test)

**Returns:** `User` ORM instance

**Example:**

```python
from tests.e2e_ui.fixtures.auth_fixtures import test_user

def test_example(test_user):
    """test_user has unique email and is persisted to database."""
    assert test_user.email is not None
    assert "@example.com" in test_user.email
    assert test_user.email.startswith("test_")
    assert test_user.is_active is True
```

**Use In:** All bug discovery tests that need a user

**Key Features:**
- UUID v4 suffix prevents email collisions in parallel tests
- Active status by default
- Hashed password (uses `get_password_hash`)
- Persisted to database via `db_session` fixture

---

### `authenticated_user`

Creates user and returns (user, JWT token) tuple.

**Location:** `tests/e2e_ui/fixtures/auth_fixtures.py`

**Scope:** Function (new user per test)

**Returns:** `Tuple[User, str]` - (user instance, JWT access token)

**Example:**

```python
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user

def test_example(authenticated_user):
    """Get both user object and JWT token."""
    user, token = authenticated_user

    # Make authenticated API request
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get("http://localhost:8000/api/v1/users/me", headers=headers)
    assert response.status_code == 200
```

**Use In:** API fuzzing tests, property tests (when JWT token needed)

**Key Features:**
- Returns both user ORM instance and JWT token
- Token expires in 15 minutes (default)
- Token subject is user ID (`sub` claim)
- No need to call `/api/v1/auth/login` endpoint

---

### `authenticated_page` (MOST IMPORTANT FOR BROWSER DISCOVERY)

Creates Playwright page with JWT token in localStorage (bypasses UI login).

**Location:** `tests/e2e_ui/fixtures/auth_fixtures.py`

**Scope:** Function (new page per test)

**Returns:** `Page` - Playwright page with JWT token pre-set

**Performance:** 10-100x faster than UI login (saves 2-10 seconds per test)

**Example:**

```python
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_page
from playwright.sync_api import Page

@pytest.mark.browser
def test_console_errors(authenticated_page: Page):
    """Already authenticated, 10-100x faster than UI login."""
    authenticated_page.goto("http://localhost:3001/dashboard")

    # No redirect to login - JWT token already set
    assert authenticated_page.locator("h1").contains("Dashboard")

    # Check for console errors
    errors = authenticated_page.evaluate("() => window.consoleErrors || []")
    assert len(errors) == 0, f"Console errors: {errors}"
```

**Use In:** Browser discovery tests (console errors, accessibility, broken links)

**Key Features:**
- Bypasses UI login flow entirely
- JWT token set in localStorage before navigation
- Tokens set: `auth_token`, `next-auth.session-token`
- Browser context closed automatically after test
- No flaky waits for login redirects

**Why Use This:**

UI login is slow and fragile:
```python
# BAD: UI login takes 2-10 seconds
def test_slow_login(page: Page):
    page.goto("http://localhost:3001/login")
    page.fill("input[name='email']", "test@example.com")  # SLOW!
    page.fill("input[name='password']", "password")
    page.click("button[type='submit']")
    page.wait_for_navigation()  # Waits for redirect

# GOOD: API-first auth takes <100ms
def test_fast_auth(authenticated_page: Page):
    authenticated_page.goto("http://localhost:3001/dashboard")  # ALREADY AUTHENTICATED!
    assert authenticated_page.locator("h1").contains("Dashboard")
```

---

### `admin_user`

Creates admin user with elevated permissions.

**Location:** `tests/e2e_ui/fixtures/auth_fixtures.py`

**Scope:** Function (new admin per test)

**Returns:** `Tuple[User, str]` - (admin user instance, JWT token)

**Example:**

```python
from tests.e2e_ui.fixtures.auth_fixtures import admin_user

def test_admin_only_feature(admin_user):
    """Admin user can access admin-only features."""
    admin, token = admin_user
    assert admin.role == "super_admin"
    assert admin.is_superuser is True

    # Make admin API request
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get("http://localhost:8000/api/v1/admin/users", headers=headers)
    assert response.status_code == 200
```

**Use In:** Admin endpoint fuzzing, governance tests (superuser permissions)

**Key Features:**
- Email prefix: `admin_` (e.g., `admin_abc123@example.com`)
- Role: `super_admin`
- JWT token includes `is_superuser: True` claim
- Active status by default

---

## Database Fixtures

### `db_session`

SQLAlchemy session with worker-specific schema isolation.

**Location:** `tests/e2e_ui/fixtures/database_fixtures.py`

**Scope:** Function (new session per test)

**Returns:** `Session` - SQLAlchemy session with transaction rollback

**Example:**

```python
from tests.e2e_ui.fixtures.database_fixtures import db_session
from core.models import AgentRegistry

def test_database_isolation(db_session):
    """Each worker gets isolated database schema."""
    agent = AgentRegistry(
        name="Test Agent",
        category="testing",
        status="ACTIVE"
    )
    db_session.add(agent)
    db_session.commit()

    # Query to verify
    retrieved = db_session.query(AgentRegistry).filter_by(name="Test Agent").first()
    assert retrieved is not None
    assert retrieved.name == "Test Agent"

    # Transaction rolled back automatically after test
```

**Use In:** ALL bug discovery tests (fuzzing, chaos, property tests, browser discovery)

**Key Features:**
- Worker-specific schema isolation (PostgreSQL: `test_schema_gw0`, `test_schema_gw1`, etc.)
- Transaction rollback after test (no data pollution)
- REPEATABLE READ isolation level (PostgreSQL)
- Search path set to worker schema automatically
- SQLite support (shared DB with transaction rollback)

**Worker Isolation:**

When running tests with `pytest -n 4` (4 parallel workers):
- Worker 0 (`gw0`) uses schema `test_schema_gw0`
- Worker 1 (`gw1`) uses schema `test_schema_gw1`
- Worker 2 (`gw2`) uses schema `test_schema_gw2`
- Worker 3 (`gw3`) uses schema `test_schema_gw3`

Each worker has isolated data, preventing race conditions and test pollution.

---

### `clean_database`

Fresh database tables per test (function-scoped).

**Location:** `tests/e2e_ui/fixtures/database_fixtures.py` (via `db_session`)

**Scope:** Function (implicit via transaction rollback)

**Behavior:** `db_session` rolls back transaction after test

**Example:**

```python
from tests.e2e_ui.fixtures.database_fixtures import db_session

def test_with_clean_db(db_session):
    """Start with empty database for each test."""
    # No existing data
    assert db_session.query(AgentRegistry).count() == 0

    # Create agent
    agent = AgentRegistry(name="Test")
    db_session.add(agent)
    db_session.commit()

    # Agent exists
    assert db_session.query(AgentRegistry).count() == 1

    # After test: transaction rolled back, count back to 0
```

**Use In:** Tests that require clean state (most bug discovery tests)

**Key Features:**
- Implicit via `db_session` (no separate fixture needed)
- Transaction rollback is automatic
- No manual cleanup required
- Fast (no DROP TABLE operations)

---

## API Fixtures

### `setup_test_user`

Creates test user via API (returns user dict).

**Location:** `tests/e2e_ui/fixtures/api_fixtures.py`

**Scope:** Function (new user per test)

**Returns:** `Dict[str, Any]` with keys:
- `user`: User response from API
- `access_token`: JWT access token
- `email`: User email
- `password`: User password

**Example:**

```python
from tests.e2e_ui.fixtures.api_fixtures import setup_test_user

def test_api_user_creation(setup_test_user):
    """Create user via API endpoint."""
    user = setup_test_user["user"]
    token = setup_test_user["access_token"]

    assert user["id"] is not None
    assert setup_test_user["email"] is not None
    assert token is not None
```

**Use In:** API fuzzing tests, integration tests

**Key Features:**
- Creates user via `/api/v1/users` endpoint
- Authenticates via `/api/v1/auth/login` endpoint
- Returns JWT token for authenticated requests
- Email uses UUID v4 for uniqueness

---

### `setup_test_project`

Creates test project via API (returns project dict).

**Location:** `tests/e2e_ui/fixtures/api_fixtures.py`

**Scope:** Function (new project per test)

**Returns:** `Dict[str, Any]` with keys:
- `project`: Project response from API
- `name`: Project name
- `description`: Project description

**Example:**

```python
from tests.e2e_ui.fixtures.api_fixtures import setup_test_project

def test_api_project_creation(setup_test_project):
    """Create project via API endpoint."""
    project = setup_test_project["project"]
    name = setup_test_project["name"]

    assert project["id"] is not None
    assert project["name"] == name
```

**Use In:** API fuzzing tests (project endpoints)

**Key Features:**
- Creates project via `/api/v1/projects` endpoint
- Requires authenticated API client (uses `authenticated_api_client` internally)
- Project name uses UUID v4 for uniqueness

---

### `api_client_authenticated`

HTTP client with pre-set Authorization header.

**Location:** `tests/e2e_ui/fixtures/api_fixtures.py`

**Scope:** Function (new client per test)

**Returns:** `APIClient` instance with token already set

**Example:**

```python
from tests.e2e_ui.fixtures.api_fixtures import api_client_authenticated

def test_api_call_with_auth(api_client_authenticated):
    """HTTP client already has auth header set."""
    # No need to set Authorization header manually
    response = api_client_authenticated.get("/api/v1/users/me")
    assert response.status_code == 200

    # POST request also authenticated
    response = api_client_authenticated.post("/api/v1/projects", json={
        "name": "Test Project"
    })
    assert response.status_code == 201
```

**Use In:** API fuzzing tests, property tests (API contracts)

**Key Features:**
- Token set via `api_client.set_token(token)`
- Base URL: `http://localhost:8001`
- Methods: `get()`, `post()`, `put()`, `delete()`, `patch()`
- Automatically adds `Authorization: Bearer <token>` header

---

## Factory Fixtures

### `user_factory`

Factory function for test user data.

**Location:** `tests/e2e_ui/fixtures/test_data_factory.py`

**Scope:** Function (not a fixture, call directly)

**Returns:** `Dict[str, Any]` with user fields

**Example:**

```python
from tests.e2e_ui.fixtures.test_data_factory import user_factory

def test_factory_user(db_session):
    """Create user with factory function."""
    # Get unique_test_id from worker_id fixture
    unique_id = f"gw0_{str(uuid.uuid4())[:8]}"
    user_data = user_factory(unique_id)

    assert user_data["email"] is not None
    assert user_data["email"].startswith("test.user.")
    assert user_data["username"] is not None
    assert user_data["password"] == "SecureTestPassword123!"

    # Use user_data for API request or DB insertion
    # ...
```

**Use In:** Property tests, batch data creation

**Key Features:**
- Function-based (not a pytest fixture)
- Requires `unique_test_id` parameter (worker_id + uuid4)
- Returns dict (not ORM instance)
- Realistic default values (not "test1", "foo")
- Supports `**kwargs` for field overrides

**Default Fields:**
```python
{
    "email": "test.user.{unique_test_id}@example.com",
    "username": "testuser_{unique_test_id}",
    "display_name": "Test User {short_id}",
    "password": "SecureTestPassword123!",
    "first_name": "Test",
    "last_name": "User {short_id}",
    "role": "MEMBER",
    "specialty": "Quality Assurance",
    "status": "ACTIVE",
    "email_verified": True,
    "onboarding_completed": True
}
```

---

### `agent_factory`

Factory function for test agent data.

**Location:** `tests/e2e_ui/fixtures/test_data_factory.py`

**Scope:** Function (not a fixture, call directly)

**Returns:** `Dict[str, Any]` with agent fields

**Example:**

```python
from tests.e2e_ui.fixtures.test_data_factory import agent_factory

def test_factory_agent(db_session):
    """Create agent with factory function."""
    unique_id = f"gw0_{str(uuid.uuid4())[:8]}"
    agent_data = agent_factory(unique_id, maturity_level="AUTONOMOUS")

    assert agent_data["name"] is not None
    assert agent_data["maturity_level"] == "AUTONOMOUS"
    assert agent_data["confidence_score"] >= 0.9  # Auto-set based on maturity

    # Use agent_data for API request or DB insertion
    # ...
```

**Use In:** Property tests, agent governance tests

**Key Features:**
- Returns dict (not ORM instance)
- Maturity level defaults to "INTERN"
- Confidence score auto-set based on maturity:
  - STUDENT: 0.4
  - INTERN: 0.6
  - SUPERVISED: 0.8
  - AUTONOMOUS: 0.95
- Supports `**kwargs` for field overrides

**Default Fields:**
```python
{
    "name": "Test Agent {short_id}",
    "category": "testing",
    "maturity_level": "INTERN",
    "description": "Test agent created by {unique_test_id}",
    "capabilities": ["markdown", "charts"],
    "confidence_score": 0.6,
    "module_path": "test.module",
    "class_name": "TestClass",
    "status": "ACTIVE"
}
```

---

### `skill_factory`

Factory function for test skill data.

**Location:** `tests/e2e_ui/fixtures/test_data_factory.py`

**Scope:** Function (not a fixture, call directly)

**Returns:** `Dict[str, Any]` with skill fields

**Example:**

```python
from tests.e2e_ui.fixtures.test_data_factory import skill_factory

def test_factory_skill(db_session):
    """Create skill with factory function."""
    unique_id = f"gw0_{str(uuid.uuid4())[:8]}"
    skill_data = skill_factory(unique_id, category="automation")

    assert skill_data["name"] is not None
    assert skill_data["category"] == "automation"
    assert skill_data["status"] == "PUBLISHED"
```

**Use In:** Skill execution tests, security scan tests

**Default Fields:**
```python
{
    "name": "test-skill-{short_id}",
    "display_name": "Test Skill {short_id}",
    "description": "A test skill for {unique_test_id}",
    "category": "productivity",
    "permissions": ["read:basic", "write:basic"],
    "version": "1.0.0",
    "status": "PUBLISHED"
}
```

---

### `project_factory`

Factory function for test project data.

**Location:** `tests/e2e_ui/fixtures/test_data_factory.py`

**Scope:** Function (not a fixture, call directly)

**Returns:** `Dict[str, Any]` with project fields

**Example:**

```python
from tests.e2e_ui.fixtures.test_data_factory import project_factory

def test_factory_project(db_session):
    """Create project with factory function."""
    unique_id = f"gw0_{str(uuid.uuid4())[:8]}"
    project_data = project_factory(unique_id)

    assert project_data["name"] is not None
    assert project_data["status"] == "ACTIVE"
    assert project_data["type"] == "automation"
```

**Use In:** Workflow tests, project governance tests

**Default Fields:**
```python
{
    "name": "Test Project {short_id}",
    "description": "Test project description {unique_test_id}",
    "owner_id": "user_{short_id}",
    "status": "ACTIVE",
    "type": "automation",
    "priority": "medium",
    "budget": 10000.00,
    "currency": "USD",
    "team_size": 5
}
```

---

## Page Objects

### `LoginPage`

Page Object for login page (rarely needed - use `authenticated_page` instead).

**Location:** `tests/e2e_ui/pages/page_objects.py`

**Example:**

```python
from tests.e2e_ui.pages.page_objects import LoginPage
from playwright.sync_api import Page

def test_login_page_object(page: Page):
    """Use Page Object for login page interactions."""
    login_page = LoginPage(page)
    login_page.navigate()
    assert login_page.is_loaded()

    login_page.fill_email("test@example.com")
    login_page.fill_password("password123")
    login_page.click_submit()

    # Or use convenience method
    # login_page.login("test@example.com", "password123")
```

**Use In:** Tests that MUST verify UI login flow (rare for bug discovery)

**Key Methods:**
- `navigate()` - Go to login page
- `fill_email(email)` - Fill email input
- `fill_password(password)` - Fill password input
- `click_submit()` - Click submit button
- `login(email, password)` - Complete login flow
- `get_error_text()` - Get error message if present

**When NOT to Use:**

Most bug discovery tests should use `authenticated_page` instead (10-100x faster):
```python
# BAD: Slow UI login
login_page = LoginPage(page)
login_page.login("test@example.com", "password")  # 2-10 seconds

# GOOD: API-first auth
def test_fast_auth(authenticated_page: Page):
    authenticated_page.goto("/dashboard")  # Already authenticated!
```

---

### `DashboardPage`

Page Object for dashboard page.

**Location:** `tests/e2e_ui/pages/page_objects.py`

**Example:**

```python
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_page
from tests.e2e_ui.pages.page_objects import DashboardPage

def test_dashboard_page_object(authenticated_page: Page):
    """Use Page Object for dashboard interactions."""
    dashboard = DashboardPage(authenticated_page)
    dashboard.goto()
    assert dashboard.is_loaded()

    # Verify dashboard elements
    assert dashboard.welcome_message.is_visible()
    assert dashboard.navigation_menu.is_visible()
```

**Use In:** Browser discovery tests (dashboard console errors, accessibility)

**Key Methods:**
- `goto()` - Navigate to dashboard
- `is_loaded()` - Check if dashboard loaded
- Properties: `welcome_message`, `navigation_menu`, `user_menu`

---

### `ChatPage`

Page Object for chat page.

**Location:** `tests/e2e_ui/pages/page_objects.py`

**Example:**

```python
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_page
from tests.e2e_ui.pages.page_objects import ChatPage

def test_chat_page_object(authenticated_page: Page):
    """Use Page Object for chat interactions."""
    chat = ChatPage(authenticated_page)
    chat.goto()
    assert chat.is_loaded()

    chat.send_message("Hello, agent!")
    assert chat.has_response()
```

**Use In:** Browser discovery tests (chat console errors, streaming tests)

**Key Methods:**
- `goto()` - Navigate to chat page
- `is_loaded()` - Check if chat loaded
- `send_message(message)` - Send chat message
- `has_response()` - Check if agent responded

---

## Import Examples

### Fuzzing Tests

```python
# backend/tests/fuzzing/conftest.py
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user
from tests.e2e_ui.fixtures.database_fixtures import db_session

@pytest.fixture
def fuzz_target(db_session, authenticated_user):
    """Fuzz target with test database and authenticated user."""
    user, token = authenticated_user
    return {
        "db": db_session,
        "user": user,
        "token": token
    }

# Usage in fuzz test
def test_api_fuzz_authentication(fuzz_target):
    """Fuzz authentication endpoint with valid user token."""
    import sys
    sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

    # Use fuzz_target["token"] for authenticated fuzzing
    token = fuzz_target["token"]
    # Fuzzer will mutate API requests with this token
```

---

### Browser Discovery Tests

```python
# backend/tests/browser_discovery/conftest.py
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_page
from tests.e2e_ui.pages.page_objects import DashboardPage

@pytest.fixture
def test_dashboard(authenticated_page):
    """Dashboard page with API-first authentication."""
    return DashboardPage(authenticated_page)

# Usage in browser discovery test
@pytest.mark.browser
def test_console_errors_on_dashboard(test_dashboard):
    """Discover console errors on dashboard (API-first auth = 10-100x faster)."""
    test_dashboard.goto()

    # Check for console errors
    errors = test_dashboard.page.evaluate("() => window.consoleErrors || []")
    assert len(errors) == 0, f"Console errors: {errors}"
```

---

### Property Tests

```python
# backend/tests/property_tests/conftest.py
from tests.e2e_ui.fixtures.database_fixtures import db_session
from tests.e2e_ui.fixtures.test_data_factory import user_factory, agent_factory

@pytest.fixture
def test_workflow(db_session, worker_id):
    """Test workflow with isolated database."""
    import uuid
    unique_id = f"{worker_id}_{str(uuid.uuid4())[:8]}"

    # Create test data
    user_data = user_factory(unique_id)
    agent_data = agent_factory(unique_id, maturity_level="AUTONOMOUS")

    # Insert into database
    # ...

    return {
        "user": user_data,
        "agent": agent_data,
        "db": db_session
    }

# Usage in property test
@pytest.mark.property
def test_agent_workflow_invariant(test_workflow):
    """Property: Agent workflow should be idempotent."""
    from hypothesis import given, strategies as st

    # Use test_workflow for property-based testing
    # ...
```

---

### Chaos Engineering Tests

```python
# backend/tests/chaos/conftest.py
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_page
from tests.e2e_ui.fixtures.database_fixtures import db_session

@pytest.fixture
def chaos_target(authenticated_page, db_session):
    """Target for chaos testing (authenticated page + database)."""
    return {
        "page": authenticated_page,
        "db": db_session
    }

# Usage in chaos test
@pytest.mark.chaos
def test_database_drop_during_request(chaos_target):
    """Chaos: Drop database connection during API request."""
    # Simulate database drop
    # Verify graceful degradation
    # ...
```

---

## Anti-Patterns

### DON'T: Duplicate Authentication Fixtures

```python
# BAD: Duplicate fixture in bug_discovery/conftest.py
@pytest.fixture
def authenticated_user():
    """DUPLICATE CODE - Use existing fixture instead."""
    user = User(email="test@example.com")  # DUPLICATION!
    db.add(user)
    db.commit()
    token = create_access_token(data={"sub": str(user.id)})
    return user, token

# GOOD: Import existing fixture
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user
```

**Why This is Bad:**
- Duplicates existing code (maintenance burden)
- May have different behavior (inconsistent auth)
- Slower (may not use API-first optimizations)
- Bug fixes must be synced across fixtures

---

### DON'T: Use UI Login (Slow)

```python
# BAD: UI login takes 2-10 seconds
def test_slow_login(page: Page):
    page.goto("http://localhost:3001/login")
    page.fill("input[name='email']", "test@example.com")  # SLOW!
    page.fill("input[name='password']", "password")
    page.click("button[type='submit']")
    page.wait_for_navigation()  # Waits for redirect
    # Total time: 2-10 seconds (flaky!)

# GOOD: API-first auth takes <100ms
def test_fast_auth(authenticated_page: Page):
    authenticated_page.goto("http://localhost:3001/dashboard")  # ALREADY AUTHENTICATED!
    assert authenticated_page.locator("h1").contains("Dashboard")
    # Total time: <100ms (reliable!)
```

**Why This is Bad:**
- 10-100x slower than API-first auth
- Flaky (waits for navigation, page loads)
- Brittle (breaks if UI changes)
- Slows down test suite significantly

---

### DON'T: Create New Database Fixtures

```python
# BAD: Duplicate database setup
@pytest.fixture
def test_db():
    """DUPLICATE CODE - Use existing db_session fixture instead."""
    # Duplicates existing db_session fixture
    engine = create_engine("sqlite:///test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

# GOOD: Import existing fixture
from tests.e2e_ui.fixtures.database_fixtures import db_session
```

**Why This is Bad:**
- Loses worker-based isolation (parallel tests will conflict)
- No transaction rollback (data pollution between tests)
- Slower (creates new engine for each test)
- Inconsistent behavior (different from other tests)

---

### DON'T: Hardcode Test Data

```python
# BAD: Hardcoded test data (causes collisions in parallel tests)
def test_hardcoded_data(db_session):
    user = User(email="test@example.com")  # COLLISION!
    db_session.add(user)
    db_session.commit()

# GOOD: Use factory with unique_test_id
def test_factory_data(db_session, worker_id):
    import uuid
    unique_id = f"{worker_id}_{str(uuid.uuid4())[:8]}"
    user_data = user_factory(unique_id)
    # No collisions in parallel tests
```

**Why This is Bad:**
- Email collisions in parallel tests (test failure)
- Hard to debug (which test created this user?)
- Not realistic (no variety in test data)

---

### DON'T: Skip Worker Isolation

```python
# BAD: Direct database access (no worker isolation)
def test_no_isolation():
    engine = create_engine("postgresql://localhost/atom_test")
    conn = engine.connect()
    # POLLUTES DATABASE FOR OTHER WORKERS!

# GOOD: Use db_session (worker-specific schema)
def test_with_isolation(db_session):
    # Each worker gets isolated schema (test_schema_gw0, gw1, etc.)
    # No pollution, no race conditions
    agent = AgentRegistry(name="Test")
    db_session.add(agent)
    db_session.commit()
```

**Why This is Bad:**
- Data pollution between parallel workers
- Race conditions (test failures)
- Flaky tests (non-deterministic)
- Hard to debug (intermittent failures)

---

## Quick Reference

| Fixture | Location | Purpose | Use In | Returns |
|---------|----------|---------|--------|---------|
| `test_user` | auth_fixtures.py | Create test user | All bug discovery tests | `User` ORM instance |
| `authenticated_user` | auth_fixtures.py | Get user + JWT token | API fuzzing tests | `Tuple[User, str]` |
| `authenticated_page` | auth_fixtures.py | Authenticated Playwright page | Browser discovery | `Page` (JWT in localStorage) |
| `admin_user` | auth_fixtures.py | Create admin user | Admin endpoint tests | `Tuple[User, str]` |
| `db_session` | database_fixtures.py | Isolated database session | All bug discovery tests | `Session` (worker-specific) |
| `setup_test_user` | api_fixtures.py | Create user via API | API integration tests | `Dict` (user + token) |
| `setup_test_project` | api_fixtures.py | Create project via API | Project endpoint tests | `Dict` (project data) |
| `api_client_authenticated` | api_fixtures.py | Authenticated HTTP client | API fuzzing tests | `APIClient` (token set) |
| `user_factory` | test_data_factory.py | Factory for user data | Property tests | `Dict` (user fields) |
| `agent_factory` | test_data_factory.py | Factory for agent data | Property tests | `Dict` (agent fields) |
| `skill_factory` | test_data_factory.py | Factory for skill data | Skill tests | `Dict` (skill fields) |
| `project_factory` | test_data_factory.py | Factory for project data | Project tests | `Dict` (project fields) |
| `LoginPage` | page_objects.py | Login page object | UI login flow tests | `LoginPage` instance |
| `DashboardPage` | page_objects.py | Dashboard page object | Dashboard discovery | `DashboardPage` instance |
| `ChatPage` | page_objects.py | Chat page object | Chat discovery | `ChatPage` instance |

**Import Shortcuts:**

```python
# Authentication (most common)
from tests.e2e_ui.fixtures.auth_fixtures import test_user, authenticated_user, authenticated_page, admin_user

# Database (most common)
from tests.e2e_ui.fixtures.database_fixtures import db_session

# API setup
from tests.e2e_ui.fixtures.api_fixtures import setup_test_user, setup_test_project, api_client_authenticated

# Factory functions (for property tests)
from tests.e2e_ui.fixtures.test_data_factory import user_factory, agent_factory, skill_factory, project_factory

# Page objects (for browser discovery)
from tests.e2e_ui.pages.page_objects import LoginPage, DashboardPage, ChatPage
```

---

## See Also

### Documentation

- **backend/tests/e2e_ui/README.md** - E2E test documentation
- **backend/tests/bug_discovery/TEMPLATES/** - Bug discovery test templates
- **backend/docs/TEST_QUALITY_STANDARDS.md** - Test quality requirements

### Key Files

- **backend/tests/e2e_ui/fixtures/auth_fixtures.py** - API-first authentication fixtures
- **backend/tests/e2e_ui/fixtures/database_fixtures.py** - Worker-based database isolation
- **backend/tests/e2e_ui/fixtures/api_fixtures.py** - API setup utilities
- **backend/tests/e2e_ui/fixtures/test_data_factory.py** - Factory functions for test data
- **backend/tests/e2e_ui/pages/page_objects.py** - Page Object Model classes

### Related Plans

- **Phase 237-02** - Bug discovery test documentation templates (TQ-01 through TQ-05)
- **Phase 237-01** - Bug discovery test directory structure (fuzzing, chaos, property tests)

---

## Summary

**Key Principles:**

1. **Reuse, Don't Duplicate** - Import existing fixtures from `e2e_ui/fixtures/`
2. **API-First Auth** - Use `authenticated_page` (10-100x faster than UI login)
3. **Worker Isolation** - Use `db_session` for parallel test execution
4. **Factory Functions** - Use `user_factory`, `agent_factory` for test data
5. **Page Objects** - Use `DashboardPage`, `ChatPage` for maintainable UI tests

**Anti-Patterns to Avoid:**

1. Don't create duplicate fixtures (import existing ones)
2. Don't use UI login (use `authenticated_page`)
3. Don't hardcode test data (use factories with `unique_test_id`)
4. Don't skip worker isolation (use `db_session`)

**By following this guide, bug discovery tests will:**

- Run 10-100x faster (API-first auth)
- Execute in parallel without conflicts (worker isolation)
- Be consistent with E2E tests (same fixtures)
- Require minimal maintenance (single source of truth)
- Be easy to write and understand (clear examples)
