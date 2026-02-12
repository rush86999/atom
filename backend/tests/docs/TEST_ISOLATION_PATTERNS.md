# Test Isolation Patterns

**Purpose**: Comprehensive guide for writing isolated tests that run reliably in parallel.

**Last Updated**: 2026-02-11

---

## Overview

**Test isolation** ensures tests don't depend on each other. Isolated tests:
- Run independently (order doesn't matter)
- Run in parallel (no resource conflicts)
- Give consistent results (no false positives/negatives)
- Are easier to debug (failures are self-contained)

**Why It Matters**:
- **False positives**: Tests fail due to other tests' side effects
- **False negatives**: Tests pass only when run in specific order
- **Slow execution**: Sequential execution due to shared state
- **Flaky tests**: Intermittent failures from resource conflicts

**Project Infrastructure**:
- `pytest-xdist`: Parallel test execution
- `unique_resource_name` fixture: Collision-free resource names
- `db_session` fixture: Database transaction rollback
- Factories: Dynamic test data generation

---

## Why Test Isolation Matters

### False Positives from Shared State

**Problem**: Test fails because another test left behind state.

**Example**:
```python
# BAD: Test depends on global state
def test_create_agent_1():
    agent = AgentRegistry(id="test-agent", name="Agent 1")
    db.add(agent)
    db.commit()

def test_create_agent_2():
    # FAILS if test_create_agent_1 ran first (duplicate ID)
    agent = AgentRegistry(id="test-agent", name="Agent 2")
    db.add(agent)
    db.commit()  # IntegrityError: duplicate id
```

**Root Cause**: Hardcoded ID "test-agent" causes collision.

**Impact**: Test suite passes when run individually, fails in CI.

---

### False Negatives from Shared State

**Problem**: Test passes only because another test set up state.

**Example**:
```python
# BAD: Test depends on execution order
def test_update_agent():
    agent = db.query(AgentRegistry).first()
    # PASSES only if test_create_agent ran first
    agent.name = "Updated"
    db.commit()

# If run alone: agent = None → AttributeError
```

**Root Cause**: Assumes test_create_agent runs first.

**Impact**: Test passes in suite, fails individually.

---

### Flaky Tests from Resource Conflicts

**Problem**: Tests fail intermittently due to port/file/name conflicts.

**Example**:
```python
# BAD: Hardcoded port causes conflict
def test_api_server():
    server = start_server(port=8000)  # Port in use?

def test_websocket_server():
    server = start_server(port=8000)  # Fails if first test running
```

**Root Cause**: Both tests try to bind port 8000.

**Impact**: Tests pass in sequential execution, fail in parallel (`pytest -n auto`).

---

### Parallel Execution Requirements

**pytest-xdist** runs tests in parallel across multiple CPU cores.

**Requirement**: Tests must not share:
- Database rows (hardcoded IDs)
- File system paths (hardcoded filenames)
- Network ports (hardcoded ports)
- Global variables (mutable state)

**Verification**:
```bash
# Run tests sequentially
pytest tests/ -v

# Run tests in parallel (should give same results)
pytest tests/ -n auto -v

# If results differ → isolation problem
```

---

## Isolation Patterns

### Pattern 1: unique_resource_name Fixture

**Purpose**: Generate collision-free resource names for parallel execution.

**Source**: `backend/tests/conftest.py`

**Implementation**:
```python
@pytest.fixture(scope="function")
def unique_resource_name():
    """
    Generate unique resource name for parallel test execution.
    Combines worker ID with UUID to ensure no collisions.
    """
    worker_id = os.environ.get('PYTEST_XDIST_WORKER_ID', 'master')
    unique_id = str(uuid.uuid4())[:8]
    return f"test_{worker_id}_{unique_id}"
```

**How It Works**:
1. `PYTEST_XDIST_WORKER_ID` set by pytest-xdist (e.g., "gw0", "gw1")
2. UUID ensures uniqueness within worker
3. Combined format: `test_gw0_a1b2c3d4`

**Usage Example**:
```python
def test_create_agent_with_unique_id(unique_resource_name):
    # GOOD: No collision with parallel tests
    agent = AgentRegistry(
        id=unique_resource_name,  # "test_gw0_a1b2c3d4"
        name="Test Agent"
    )
    db.add(agent)
    db.commit()
```

**Before (Bad)**:
```python
def test_create_agent():
    agent = AgentRegistry(id="test-agent", ...)  # Collision!
```

**After (Good)**:
```python
def test_create_agent(unique_resource_name):
    agent = AgentRegistry(id=unique_resource_name, ...)  # Unique!
```

---

### Pattern 2: Database Transaction Rollback

**Purpose**: Isolate database operations with automatic cleanup.

**Implementation**:
```python
@pytest.fixture(scope="function")
def db_session():
    """
    Create isolated database session with automatic rollback.
    Ensures zero shared state between parallel tests.
    """
    from core.models import SessionLocal

    session = SessionLocal()
    transaction = session.begin()

    yield session

    # Rollback transaction to clean up test data
    session.rollback()
    session.close()
```

**How It Works**:
1. Begin transaction before test
2. Test executes with session
3. Rollback after test (undo all changes)
4. Close session

**Usage Example**:
```python
def test_agent_creation(db_session, unique_resource_name):
    # Create agent
    agent = AgentRegistry(
        id=unique_resource_name,
        name="Test Agent"
    )
    db_session.add(agent)
    db_session.commit()

    # Test logic...

    # Automatic rollback via fixture
    # No other test sees this agent
```

**Before (Bad)**:
```python
def test_agent_creation():
    agent = AgentRegistry(id="test-agent", ...)
    db.add(agent)
    db.commit()
    # Manual cleanup required (error-prone)
    db.delete(agent)
    db.commit()
```

**After (Good)**:
```python
def test_agent_creation(db_session, unique_resource_name):
    agent = AgentRegistry(id=unique_resource_name, ...)
    db_session.add(agent)
    db_session.commit()
    # Automatic rollback - no cleanup needed
```

**Benefits**:
- No manual cleanup
- No shared state between tests
- Fast (rollback is instant)
- Safe for parallel execution

---

### Pattern 3: Factory Pattern

**Purpose**: Generate dynamic test data with no hardcoded values.

**Source**: `backend/tests/factories/`

**Implementation**:
```python
class AgentFactory(BaseFactory):
    class Meta:
        model = AgentRegistry

    id = LazyFunction(lambda: str(uuid.uuid4()))
    name = LazyFunction(lambda: fake.company())
    status = "STUDENT"
    confidence = 0.5
```

**How It Works**:
- `LazyFunction`: Call function for each instance (not class-level)
- `Faker`: Generate realistic data (names, emails, companies)
- `SubFactory`: Handle relationships

**Usage Example**:
```python
from tests.factories import AgentFactory, UserFactory

def test_agent_governance(unique_resource_name):
    # GOOD: Unique IDs every time
    agent = AgentFactory.create(
        id=unique_resource_name,
        status="STUDENT",
        confidence=0.4
    )
    # agent.id is unique (UUID + worker ID)
    # agent.name is realistic (Faker-generated)

    user = UserFactory.create()
    # user.email is unique (Faker-generated)
    # No collision with parallel tests
```

**Before (Bad)**:
```python
def test_agent_governance():
    agent = AgentRegistry(
        id="test-agent-123",  # Hardcoded!
        name="Test Agent",     # Hardcoded!
        email="test@example.com"  # Hardcoded!
    )
```

**After (Good)**:
```python
def test_agent_governance(unique_resource_name):
    agent = AgentFactory.create(
        id=unique_resource_name  # Unique!
    )
    # All other fields auto-generated
```

**Benefits**:
- Unique data every time (no collisions)
- Realistic data (better than "test123")
- Easy to override specific fields
- Relationships handled automatically

**See**: `backend/tests/factories/README.md` for complete factory guide.

---

### Pattern 4: Mock External Dependencies

**Purpose**: Isolate tests from external systems (APIs, databases, file systems).

**Implementation**:
```python
from unittest.mock import patch, MagicMock

def test_external_api_call():
    # GOOD: Mock external API
    with patch('core.services.external_api_client') as mock_api:
        mock_api.call.return_value = {"status": "success"}

        result = service.process_data()

        assert result["status"] == "success"
        mock_api.call.assert_called_once()
```

**Before (Bad)**:
```python
def test_external_api_call():
    # BAD: Calls real API (slow, unreliable, requires auth)
    result = service.process_data()
    assert result["status"] == "success"
```

**After (Good)**:
```python
def test_external_api_call():
    # GOOD: Mocked API (fast, reliable, no auth)
    with patch('core.services.external_api_client') as mock_api:
        mock_api.call.return_value = {"status": "success"}
        result = service.process_data()
        assert result["status"] == "success"
```

**What to Mock**:
- External APIs (HTTP calls, third-party services)
- File system operations (if not testing file I/O)
- Database connections (use db_session instead)
- Time/date (use freezegun)
- Random values (use seed or mock)

**What NOT to Mock**:
- Business logic (you're testing this)
- Data structures (use real objects)
- Database operations (use transaction rollback)

---

### Pattern 5: Fixture Cleanup

**Purpose**: Ensure cleanup even if test fails.

**Implementation**:
```python
@pytest.fixture(scope="function")
def temp_file():
    """
    Create temporary file with automatic cleanup.
    Cleanup runs even if test fails.
    """
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".txt")

    yield path

    # Cleanup runs regardless of test result
    os.close(fd)
    os.unlink(path)

# Usage
def test_file_operations(temp_file):
    with open(temp_file, 'w') as f:
        f.write("test data")

    # Test logic...

    # Automatic cleanup via fixture
```

**Alternative: yield + try/finally**
```python
@pytest.fixture(scope="function")
def temp_directory():
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)  # Always runs
```

**Benefits**:
- No manual cleanup in tests
- Cleanup runs even if test fails
- No resource leaks (files, ports, connections)

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Hardcoded Test Data

**Problem**: Hardcoded values cause collisions in parallel execution.

**Example**:
```python
# BAD: Hardcoded ID
def test_create_agent():
    agent = AgentRegistry(id="test-agent-123", ...)
    # Fails if another test uses same ID

# BAD: Hardcoded filename
def test_file_operations():
    with open("test_file.txt", 'w') as f:
        f.write("data")
    # Fails if another test creates same file

# BAD: Hardcoded port
def test_server():
    server = start_server(port=8000)
    # Fails if another test binds port 8000
```

**Solution**: Use unique_resource_name or factories.

```python
# GOOD: Unique ID
def test_create_agent(unique_resource_name):
    agent = AgentRegistry(id=unique_resource_name, ...)

# GOOD: Unique filename
def test_file_operations(unique_resource_name):
    filename = f"{unique_resource_name}.txt"
    with open(filename, 'w') as f:
        f.write("data")

# GOOD: Dynamic port
def test_server():
    port = get_ephemeral_port()  # Get free port
    server = start_server(port=port)
```

---

### Anti-Pattern 2: Global State Mutations

**Problem**: Tests modify global variables, affecting other tests.

**Example**:
```python
# BAD: Modifying global variable
SETTINGS = {"debug": False}

def test_enable_debug():
    global SETTINGS
    SETTINGS["debug"] = True  # Affects other tests

def test_feature_flag():
    # FAILS if test_enable_debug ran first
    assert SETTINGS["debug"] == False
```

**Solution**: Use fixtures to reset state.

```python
# GOOD: Fixture with cleanup
@pytest.fixture(autouse=True)
def reset_settings():
    original = SETTINGS.copy()
    yield
    SETTINGS.clear()
    SETTINGS.update(original)

def test_enable_debug():
    SETTINGS["debug"] = True  # Isolated to this test

def test_feature_flag():
    assert SETTINGS["debug"] == False  # Passes (state reset)
```

---

### Anti-Pattern 3: Time-Based Tests Without Mocking

**Problem**: Tests depend on current time, causing non-deterministic results.

**Example**:
```python
# BAD: Depends on current time
def test_token_expiry():
    token = create_token(expiry_hours=24)
    assert token.expires_at > datetime.now()  # Flaky near boundary

# BAD: Uses sleep (slow, non-deterministic)
def test_cache_timeout():
    cache.set("key", "value", timeout=1)
    time.sleep(1)  # SLOW!
    assert cache.get("key") is None
```

**Solution**: Use freezegun to mock time.

```python
# GOOD: Freeze time
from freezegun import freeze_time

def test_token_expiry():
    with freeze_time("2026-02-11 10:00:00"):
        token = create_token(expiry_hours=24)
        assert token.expires_at == datetime(2026, 2, 12, 10, 0, 0)

# GOOD: Freeze time for timeout tests
def test_cache_timeout():
    with freeze_time("2026-02-11 10:00:00"):
        cache.set("key", "value", timeout=3600)

    with freeze_time("2026-02-11 11:00:00"):
        assert cache.get("key") is None  # Instant, no sleep
```

---

### Anti-Pattern 4: File System Operations Without Temp Directories

**Problem**: Tests create files in current directory, causing collisions.

**Example**:
```python
# BAD: Creates file in current directory
def test_export_data():
    export_to_file("data.json")  # Collisions with parallel tests

# BAD: Hardcoded path
def test_import_data():
    import_from_file("/tmp/test.json")  # May not exist, permissions issues
```

**Solution**: Use tempfile module.

```python
# GOOD: Temporary file
def test_export_data(unique_resource_name):
    temp_dir = tempfile.mkdtemp()
    try:
        filepath = os.path.join(temp_dir, f"{unique_resource_name}.json")
        export_to_file(filepath)
        assert os.path.exists(filepath)
    finally:
        shutil.rmtree(temp_dir)  # Cleanup

# GOOD: Fixture-based temp directory
@pytest.fixture
def temp_dir():
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path)

def test_import_data(temp_dir):
    filepath = os.path.join(temp_dir, "test.json")
    import_from_file(filepath)
```

---

### Anti-Pattern 5: Database Commits in Tests

**Problem**: Tests commit data, affecting other tests.

**Example**:
```python
# BAD: Commits data to database
def test_create_agent():
    agent = AgentRegistry(id="test-agent", ...)
    db.add(agent)
    db.commit()  # Data persists after test

# BAD: Manual cleanup (error-prone)
def test_create_agent():
    agent = AgentRegistry(id="test-agent", ...)
    db.add(agent)
    db.commit()
    # Test logic...
    db.delete(agent)  # May not run if test fails
    db.commit()
```

**Solution**: Use db_session with automatic rollback.

```python
# GOOD: Transaction rollback
def test_create_agent(db_session, unique_resource_name):
    agent = AgentRegistry(id=unique_resource_name, ...)
    db_session.add(agent)
    db_session.commit()  # Transaction rolled back after test
    # No manual cleanup needed
```

**Key Insight**: Rollback is instant (no actual DELETE queries).

---

## Examples

### Good: Using unique_resource_name for Filenames

```python
import tempfile
import os

def test_file_export(unique_resource_name):
    """Test file export with unique filename."""
    temp_dir = tempfile.mkdtemp()
    try:
        # GOOD: Unique filename (no collisions)
        filename = os.path.join(temp_dir, f"{unique_resource_name}.csv")
        export_data_to_csv(filename, data=[1, 2, 3])

        # Verify file exists and has correct content
        assert os.path.exists(filename)
        with open(filename, 'r') as f:
            assert f.read() == "1,2,3\n"
    finally:
        shutil.rmtree(temp_dir)  # Cleanup
```

**Bad Alternative**:
```python
def test_file_export():
    # BAD: Hardcoded filename (collisions in parallel)
    filename = "test_export.csv"
    export_data_to_csv(filename, data=[1, 2, 3])
    # File persists after test
```

---

### Good: Using db_session with Automatic Rollback

```python
def test_agent_deletion(db_session, unique_resource_name):
    """Test agent deletion with database isolation."""
    # Create agent
    agent = AgentFactory.create(_session=db_session, id=unique_resource_name)

    # Delete agent
    db_session.delete(agent)
    db_session.commit()

    # Verify deletion
    assert db_session.query(AgentRegistry).filter_by(id=agent.id).first() is None

    # Automatic rollback: other tests don't see this deletion
```

**Bad Alternative**:
```python
def test_agent_deletion():
    # BAD: Manual cleanup (error-prone)
    agent = AgentRegistry(id="test-agent-123")
    db.add(agent)
    db.commit()

    db.delete(agent)
    db.commit()

    # Manual cleanup (may not run if test fails)
    if db.query(AgentRegistry).filter_by(id="test-agent-123").first():
        db.delete(agent)
        db.commit()
```

---

### Good: Mocking External APIs

```python
from unittest.mock import patch, MagicMock

def test_payment_processing(unique_resource_name):
    """Test payment processing with mocked external API."""
    # GOOD: Mock external payment API
    with patch('core.services.payment_gateway.charge') as mock_charge:
        mock_charge.return_value = {
            "status": "success",
            "transaction_id": "txn_123"
        }

        # Process payment
        result = process_payment(
            user_id=unique_resource_name,
            amount=100.00
        )

        # Verify result
        assert result["status"] == "success"
        assert result["transaction_id"] == "txn_123"

        # Verify API was called
        mock_charge.assert_called_once_with(amount=100.00)
```

**Bad Alternative**:
```python
def test_payment_processing():
    # BAD: Calls real payment API (charges actual money!)
    result = process_payment(user_id="test-user", amount=100.00)
    assert result["status"] == "success"
```

---

## Debugging Isolation Issues

### Identifying Shared State Problems

**Symptom**: Tests pass alone but fail in suite.

**Diagnosis**:
```bash
# Run test alone (passes)
pytest tests/test_agent.py::test_create_agent -v

# Run in suite (fails)
pytest tests/ -v

# Run with fresh database (passes)
pytest tests/ -v --create-db
```

**Root Cause**: Previous tests left behind data.

**Solution**:
1. Use `db_session` fixture (automatic rollback)
2. Use `unique_resource_name` fixture (unique IDs)
3. Use factories (dynamic data)

---

### Finding Resource Conflicts

**Symptom**: "Port already in use", "File exists", "Duplicate key" errors.

**Diagnosis**:
```bash
# Run tests in parallel (fails)
pytest tests/ -n auto -v

# Run tests sequentially (passes)
pytest tests/ -v

# Check for hardcoded values
grep -r "port=8000\|\"test-agent\|\"test.txt" tests/
```

**Root Cause**: Hardcoded resource names/ports.

**Solution**:
1. Use `unique_resource_name` for dynamic names
2. Use `tempfile.mkdtemp()` for temporary files
3. Use `get_ephemeral_port()` for dynamic ports

---

### Verifying Isolation

**Step 1: Run Tests 10 Times**
```bash
for i in {1..10}; do
    pytest tests/ -v --tb=short
done

# If results vary → flaky test (isolation issue)
```

**Step 2: Run in Random Order**
```bash
pip install pytest-randomly

pytest tests/ -v

# If results vary → order dependency
```

**Step 3: Run in Parallel**
```bash
pytest tests/ -n auto -v

# If failures don't reproduce sequentially → resource conflict
```

**Step 4: Check for Global State**
```bash
grep -r "global\|GLOBALS\|_state" tests/

# Find mutable globals and reset with fixtures
```

---

## pytest-xdist Integration

### Worker ID Environment Variable

**PYTEST_XDIST_WORKER_ID**: Set by pytest-xdist to identify worker.

**Values**:
- `master`: Main process (sequential execution)
- `gw0`, `gw1`, `gw2`, ...: Worker IDs (parallel execution)

**Usage**:
```python
# In conftest.py
def pytest_configure(config):
    if hasattr(config, 'workerinput'):
        worker_id = config.workerinput.get('workerid', 'master')
        os.environ['PYTEST_XDIST_WORKER_ID'] = worker_id

# In fixtures
@pytest.fixture
def worker_log_file():
    worker_id = os.environ.get('PYTEST_XDIST_WORKER_ID', 'master')
    return f"test_{worker_id}.log"
```

---

### Load Scope Scheduling

**`--dist loadscope`**: Group tests by scope (test module, class, function).

**Configuration** (pytest.ini):
```ini
[pytest]
addopts = -n auto --dist loadscope
```

**Benefits**:
- Tests in same module run on same worker
- Reduces database lock contention
- Better isolation for module-level fixtures

**Example**:
```bash
# All tests in test_agent.py run on worker gw0
# All tests in test_user.py run on worker gw1
# Reduces database conflicts (agent tests don't interfere with user tests)
```

---

### Parallel Execution Verification

**Step 1: Verify pytest-xdist Installed**
```bash
pip install pytest-xdist
pytest --version  # Should show "pytest-xdist"
```

**Step 2: Run Tests in Parallel**
```bash
pytest tests/ -n auto -v

# Should see worker IDs in output (gw0, gw1, ...)
```

**Step 3: Verify Speedup**
```bash
# Sequential execution
time pytest tests/ -v

# Parallel execution
time pytest tests/ -n auto -v

# Parallel should be ~2-4x faster (depending on CPU cores)
```

**Step 4: Verify Consistency**
```bash
# Run sequential
pytest tests/ -v > sequential.txt

# Run parallel
pytest tests/ -n auto -v > parallel.txt

# Compare results
diff sequential.txt parallel.txt

# Should be identical (except for worker IDs)
```

---

## Related Documentation

- **[COVERAGE_GUIDE.md](./COVERAGE_GUIDE.md)** - Coverage report interpretation
- **[FLAKY_TEST_GUIDE.md](./FLAKY_TEST_GUIDE.md)** - Flaky test prevention
- **[../conftest.py](../conftest.py)** - Fixture definitions
- **[../factories/README.md](../factories/README.md)** - Test data factory usage

---

## Summary

**Key Takeaways**:
1. **unique_resource_name**: Collision-free resource names (worker ID + UUID)
2. **db_session**: Database isolation via transaction rollback
3. **Factories**: Dynamic test data generation (no hardcoded values)
4. **Mocking**: Isolate external dependencies (APIs, file systems)
5. **Fixture cleanup**: Ensure cleanup even if test fails

**Anti-Patterns**:
- Hardcoded test data → Use factories
- Global state mutations → Reset with fixtures
- Time-based tests → Mock with freezegun
- File operations → Use tempfile
- Database commits → Use db_session

**Quick Reference**:
```python
# GOOD: Isolated test
def test_agent_creation(db_session, unique_resource_name):
    agent = AgentFactory.create(
        _session=db_session,
        id=unique_resource_name
    )
    # Automatic cleanup, no shared state

# BAD: Non-isolated test
def test_agent_creation():
    agent = AgentRegistry(id="test-agent-123", ...)
    db.commit()  # Persists data
    # Manual cleanup required
```

**Next Steps**:
1. Run tests in parallel: `pytest tests/ -n auto -v`
2. Fix isolation issues using patterns above
3. Verify tests pass 10 times in a row
4. Add to CI/CD for continuous validation
