# Test Infrastructure Standards

**Purpose**: Consistent, reliable test patterns across Atom codebase.

Last Updated: 2026-03-23

## data-testid Standard (INFRA-07)

### Why data-testid?
- Stable selectors (don't change with CSS refactors)
- Cross-platform (Web, Mobile, Desktop)
- Semantic (describe element purpose)

### Format
- kebab-case: `submit-button`, `agent-card`, `email-input`
- Descriptive: what element does, not how it looks
- Unique within page

### Examples
<!-- HTML -->
<button data-testid="submit-button">Submit</button>
<input data-testid="email-input" type="email" />

<!-- Test selector -->
await click_element(page, "[data-testid='submit-button']")

### Cross-Platform Mapping
| Platform | Attribute | Example |
|----------|-----------|---------|
| Web | data-testid | [data-testid='submit-button'] |
| Mobile (React Native) | testID | testID='submit-button' |
| Desktop (Tauri) | data-testid | [data-testid='submit-button'] |

## API-First Authentication

### Performance Comparison
- UI Login: 10-60 seconds (form fill, navigation, redirect)
- API Login: 10-100 milliseconds (API call, localStorage injection)

### Usage
```python
def test_protected_route(authenticated_page_api):
    # Already authenticated, no login overhead
    authenticated_page_api.goto("/agents")
    assert authenticated_page_api.locator("[data-testid='agent-list']").visible
```

### When to Use UI Login
- Testing login flow itself (validation, error messages)
- Testing OAuth flows (can't bypass redirect)

## Test Cleanup Patterns

### Fixture Cleanup (Preferred)
```python
@pytest.fixture
def temp_resource():
    resource = create_resource()
    try:
        yield resource
    finally:
        # Always runs, even if test fails
        cleanup_resource(resource)
```

### Manual Cleanup
```python
def test_with_cleanup():
    resource = create_resource()
    try:
        # Test code
        pass
    finally:
        cleanup_resource(resource)
```

## Factory Usage (from 233-01)

### Required _session Parameter
```python
def test_agent_creation(db_session):
    agent = AgentFactory.create(
        _session=db_session,  # REQUIRED
        id=unique_resource_name
    )
```

## Parallel Execution

### Worker Isolation
- Each worker gets own database (test_db_gw0, test_db_gw1, etc.)
- Use unique_resource_name for unique IDs
- No shared state between tests

### Worker-Specific Fixtures
```python
# Each pytest-xdist worker gets isolated database
@pytest.fixture(scope="function")
def db_session(worker_schema, get_engine, init_db):
    # Automatically uses worker-specific schema
    # Transactions rolled back after test
    yield session
    session.rollback()
```

## Shared Utilities

### Import Common Helpers
```python
from tests.fixtures.shared_utilities import (
    wait_for_selector,
    click_element,
    fill_input,
    wait_for_text,
    get_test_id
)
```

### Use data-testid Selectors
```python
# Preferred
click_element(page, "[data-testid='submit-button']")

# Avoid
click_element(page, ".btn-primary")  # CSS class can change
click_element(page, "//button[@type='submit']")  # XPath is brittle
```

## Best Practices

### 1. Prefer API-First Setup
```python
# Good: 10-100ms
def test_fast(authenticated_page_api):
    authenticated_page_api.goto("/dashboard")

# Slow: 10-60s
def test_slow(authenticated_page):
    # Fills login form, navigates, waits...
    pass
```

### 2. Use Explicit Timeouts
```python
# Good
wait_for_selector(page, "[data-testid='status']", timeout=5000)

# Bad (relies on global timeout)
page.wait_for_selector(".status")
```

### 3. Prefer data-testid Over CSS/XPath
```python
# Good: Stable
page.click("[data-testid='submit-button']")

# Bad: Brittle
page.click(".btn.btn-primary")  # Changes if CSS refactored
page.click("//button[contains(@class, 'btn')]")  # XPath is slow
```

### 4. Always Clean Up Resources
```python
# Good: Explicit cleanup
@pytest.fixture
def temp_file():
    path = create_temp_file()
    try:
        yield path
    finally:
        os.unlink(path)  # Always runs

# Bad: No cleanup
def test_with_file():
    path = create_temp_file()
    # If test fails, file remains
```

### 5. Use Transaction Rollback for Database
```python
# Good: Automatic rollback
def test_database(db_session):
    agent = Agent(name="test")
    db_session.add(agent)
    db_session.commit()
    # Automatically rolled back after test

# Bad: Manual cleanup
def test_database_manual(db_session):
    agent = Agent(name="test")
    db_session.add(agent)
    db_session.commit()
    db_session.delete(agent)  # Unnecessary
    db_session.commit()
```

## Quick Reference

### Fixture Scopes
- `function`: Clean state for every test (default)
- `session`: Shared across all tests (use sparingly)
- `module`: Shared across tests in same module

### Common Fixtures
- `db_session`: Database session with rollback
- `authenticated_page_api`: Fast API-first authentication
- `browser`: Playwright browser (session-scoped)
- `base_url`: Test application base URL

### Utility Functions
- `get_test_id(id)`: Generate data-testid selector
- `wait_for_selector(page, selector, timeout)`: Wait for element
- `click_element(page, selector)`: Click element
- `fill_input(page, selector, value)`: Fill input
- `wait_for_text(page, selector, text)`: Wait for text content

## See Also
- [PARALLEL_EXECUTION_GUIDE.md](PARALLEL_EXECUTION_GUIDE.md): Worker isolation and parallel testing
- [TEST_ISOLATION_PATTERNS.md](TEST_ISOLATION_PATTERNS.md): Database and resource isolation
- [FLAKY_TEST_GUIDE.md](FLAKY_TEST_GUIDE.md): Dealing with flaky tests
