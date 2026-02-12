# Flaky Test Prevention Guide

**Purpose**: Comprehensive guide for preventing, detecting, and fixing flaky tests.

**Last Updated**: 2026-02-11

---

## Overview

**Flaky Test**: A test that passes or fails non-deterministically without any code changes.

**Impact**:
- **Erodes confidence**: Developers ignore test failures
- **Wastes time**: Debugging non-existent bugs
- **Masks real failures**: Legitimate failures hidden among flakes
- **Slows development**: Re-running tests increases cycle time

**Common Symptoms**:
- Passes locally, fails in CI
- Passes alone, fails in suite
- Passes in suite, fails alone
- Intermittent failures (passes 9/10 times)

---

## What Are Flaky Tests

### Definition

**Flaky Test**: A test with non-deterministic outcome due to factors other than code changes.

**Non-Flaky Test**: Deterministic outcome (always passes or always fails for same code).

**Examples**:
```python
# FLAKY: Depends on timing
def test_async_operation():
    result = async_operation()
    time.sleep(0.1)  # May not be enough
    assert result.is_ready

# FLAKY: Depends on execution order
def test_user_count():
    assert User.query.count() == 0  # Fails if other test created users

# FLAKY: Depends on external service
def test_api_call():
    response = requests.get("https://api.example.com/data")
    assert response.status_code == 200  # Network may be slow/down
```

---

### Common Symptoms

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Passes locally, fails in CI | Environment differences (speed, resources, timezone) | Use mocks, increase timeouts |
| Passes alone, fails in suite | Shared state between tests | Use unique_resource_name, db_session |
| Passes in suite, fails alone | Depends on other tests' setup | Make tests independent |
| Intermittent failures | Race conditions, resource contention | Synchronize, use explicit waits |
| Fails in parallel, passes sequentially | Resource conflicts (ports, files) | Use unique resource names |
| Random failures | Time dependencies, randomness | Mock time, seed random generator |

---

### Impact

**Wasted Time**:
- Developer: 30 minutes debugging flaky test
- Team: 10 developers × 30 minutes = 5 hours/week
- CI: Re-running tests = slower builds

**Eroded Confidence**:
```
Scenario: Test fails in CI
Developer A: "Probably just flaky, ignore it"
Developer B: "No, that's a real bug!"
Result: Legitimate failures ignored
```

**Masked Real Failures**:
```
Build #123: FAILED (flaky)
Build #124: FAILED (flaky)
Build #125: FAILED (real bug) ← Hidden by flakes
Build #126: FAILED (flaky)
```

**Slowed Development**:
- Re-run tests 3-4 times to get "green" build
- Disable tests to unblock CI
- Merge without full test suite

---

## Common Causes

### 1. Race Conditions

**What**: Tests depend on timing between concurrent operations.

**Example**:
```python
# FLAKY: Race condition
def test_async_processing():
    queue.add_task("process_data")
    # May execute before task completes
    assert queue.get_result("process_data") is not None
```

**Root Cause**: No guarantee task completes before assertion.

**Fix**: Use explicit synchronization (events, barriers).

```python
# GOOD: Explicit synchronization
def test_async_processing():
    queue.add_task("process_data")
    queue.wait_for_completion("process_data", timeout=5.0)
    assert queue.get_result("process_data") is not None
```

---

### 2. Shared State

**What**: Tests modify global variables, database rows, or file system state.

**Example**:
```python
# FLAKY: Shared database state
def test_create_user():
    user = User(id=1, name="Alice")  # Hardcoded ID
    db.add(user)
    db.commit()

def test_update_user():
    user = db.query(User).get(1)  # Fails if test_create_user didn't run
    user.name = "Bob"
    db.commit()
```

**Root Cause**: Tests depend on execution order.

**Fix**: Use db_session with automatic rollback.

```python
# GOOD: Isolated database state
def test_create_user(db_session, unique_resource_name):
    user = UserFactory.create(_session=db_session, id=unique_resource_name)
    # Automatic rollback, no shared state
```

---

### 3. External Dependencies

**What**: Tests call external APIs, databases, or services.

**Example**:
```python
# FLAKY: External API call
def test_payment_processing():
    result = payment_gateway.charge(amount=100.00)
    assert result["status"] == "success"  # API may be down/slow
```

**Root Cause**: Network issues, service downtime, rate limits.

**Fix**: Mock external dependencies.

```python
# GOOD: Mocked API
@patch('core.services.payment_gateway.charge')
def test_payment_processing(mock_charge):
    mock_charge.return_value = {"status": "success"}
    result = payment_gateway.charge(amount=100.00)
    assert result["status"] == "success"
```

---

### 4. Time Dependencies

**What**: Tests depend on current time or use time.sleep().

**Example**:
```python
# FLAKY: Time-based assertion
def test_token_expiry():
    token = create_token(expiry_hours=24)
    assert token.expires_at > datetime.now()  # Flaky near boundary

# FLAKY: Uses sleep (non-deterministic)
def test_cache_timeout():
    cache.set("key", "value", timeout=1)
    time.sleep(1)  # May not be enough (slow CI)
    assert cache.get("key") is None
```

**Root Cause**: Time passes non-deterministically.

**Fix**: Use freezegun to mock time.

```python
# GOOD: Frozen time
from freezegun import freeze_time

def test_token_expiry():
    with freeze_time("2026-02-11 10:00:00"):
        token = create_token(expiry_hours=24)
        assert token.expires_at == datetime(2026, 2, 12, 10, 0, 0)

def test_cache_timeout():
    with freeze_time("2026-02-11 10:00:00"):
        cache.set("key", "value", timeout=3600)
    with freeze_time("2026-02-11 11:00:00"):
        assert cache.get("key") is None  # Instant, no sleep
```

---

### 5. Resource Contention

**What**: Tests compete for limited resources (ports, files, memory).

**Example**:
```python
# FLAKY: Port already in use
def test_server_start():
    server = start_server(port=8000)  # Fails if another test using port

# FLAKY: File already exists
def test_log_processing():
    with open("test.log", 'w') as f:  # Fails if another test created file
        f.write("log data")
```

**Root Cause**: Hardcoded resource names/ports.

**Fix**: Use unique resource names or ephemeral ports.

```python
# GOOD: Unique filename
def test_log_processing(unique_resource_name):
    filename = f"{unique_resource_name}.log"
    with open(filename, 'w') as f:
        f.write("log data")

# GOOD: Ephemeral port
def test_server_start():
    port = get_ephemeral_port()  # Get free port
    server = start_server(port=port)
```

---

### 6. Order Dependency

**What**: Tests assume specific execution order.

**Example**:
```python
# FLAKY: Depends on test_setup_data running first
def test_process_data():
    data = db.query(Data).first()  # None if test_setup_data didn't run
    assert process(data) == "result"

# FLAKY: Depends on global variable being set
def test_feature_flag():
    assert SETTINGS["feature_enabled"] == True  # Fails if previous test didn't set
```

**Root Cause**: Implicit dependencies between tests.

**Fix**: Make tests independent (use fixtures for setup).

```python
# GOOD: Explicit setup
def test_process_data(unique_resource_name):
    data = DataFactory.create(_session=db_session, id=unique_resource_name)
    assert process(data) == "result"

# GOOD: Fixture resets state
@pytest.fixture(autouse=True)
def reset_settings():
    original = SETTINGS.copy()
    yield
    SETTINGS.clear()
    SETTINGS.update(original)

def test_feature_flag():
    SETTINGS["feature_enabled"] = True  # Isolated
```

---

## Prevention Patterns

### Pattern 1: Explicit Synchronization

**Instead of sleep**: Use events, barriers, or condition variables.

**Bad**:
```python
# FLAKY: Arbitrary sleep
def test_worker_pool():
    pool = WorkerPool(size=2)
    pool.submit(task)
    time.sleep(0.5)  # Hope task completes
    assert pool.results[0] == "done"
```

**Good**:
```python
# GOOD: Explicit wait
def test_worker_pool():
    pool = WorkerPool(size=2)
    future = pool.submit(task)
    result = future.wait(timeout=5.0)  # Explicit synchronization
    assert result == "done"
```

---

### Pattern 2: Mock External Dependencies

**Instead of real API**: Use mocks, fixtures, or test doubles.

**Bad**:
```python
# FLAKY: Real API call
def test_send_email():
    result = email_service.send("user@example.com", "Hello")
    assert result["status"] == "sent"  # API may be down
```

**Good**:
```python
# GOOD: Mocked API
@patch('core.services.email_service.send')
def test_send_email(mock_send):
    mock_send.return_value = {"status": "sent"}
    result = email_service.send("user@example.com", "Hello")
    assert result["status"] == "sent"
```

---

### Pattern 3: Unique Resource Names

**Instead of hardcoded names**: Use unique_resource_name fixture.

**Bad**:
```python
# FLAKY: Hardcoded ID
def test_create_user():
    user = User(id="test-user", ...)  # Collision in parallel
```

**Good**:
```python
# GOOD: Unique ID
def test_create_user(unique_resource_name):
    user = UserFactory.create(id=unique_resource_name, ...)
```

---

### Pattern 4: Transaction Rollback

**Instead of manual cleanup**: Use db_session with rollback.

**Bad**:
```python
# FLAKY: Manual cleanup (may not run)
def test_create_agent():
    agent = Agent(id="test-agent", ...)
    db.add(agent)
    db.commit()
    try:
        # Test logic...
        pass
    finally:
        db.delete(agent)  # May not run
        db.commit()
```

**Good**:
```python
# GOOD: Automatic rollback
def test_create_agent(db_session, unique_resource_name):
    agent = AgentFactory.create(_session=db_session, id=unique_resource_name)
    # Test logic...
    # Automatic rollback via fixture
```

---

### Pattern 5: Avoid Global State

**Instead of globals**: Use fixtures to reset state.

**Bad**:
```python
# FLAKY: Global state
SETTINGS = {"debug": False}

def test_enable_debug():
    global SETTINGS
    SETTINGS["debug"] = True  # Affects other tests
```

**Good**:
```python
# GOOD: Fixture with cleanup
@pytest.fixture(autouse=True)
def reset_settings():
    original = SETTINGS.copy()
    yield
    SETTINGS.clear()
    SETTINGS.update(original)

def test_enable_debug():
    SETTINGS["debug"] = True  # Isolated
```

---

### Pattern 6: Make Tests Order-Independent

**Instead of order dependency**: Each test sets up its own data.

**Bad**:
```python
# FLAKY: Depends on test_create_user running first
def test_update_user():
    user = db.query(User).first()  # None if test_create_user didn't run
    user.name = "Bob"
    db.commit()
```

**Good**:
```python
# GOOD: Independent test
def test_update_user(unique_resource_name):
    user = UserFactory.create(id=unique_resource_name, name="Alice")
    user.name = "Bob"
    db.commit()
    assert user.name == "Bob"
```

---

## Detection Strategies

### Strategy 1: pytest-rerunfailures

**Purpose**: Automatically retry failed tests to detect flakiness.

**Installation**:
```bash
pip install pytest-rerunfailures
```

**Usage**:
```bash
# Retry all failed tests 3 times
pytest tests/ --reruns 3

# Retry with delay between retries
pytest tests/ --reruns 3 --reruns-delay 1

# Retry only specific tests
pytest tests/ --reruns 3 -m "flaky"

# Run without retries (to detect real failures)
pytest tests/ --reruns 0
```

**Marker Usage**:
```python
import pytest

@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_external_api():
    # May fail intermittently, will retry up to 3 times
    result = external_api_call()
    assert result["status"] == "success"
```

**When to Use**: Temporary workaround while fixing root cause (not permanent).

---

### Strategy 2: Run Tests Multiple Times

**Purpose**: Detect intermittent failures by running tests repeatedly.

**Bash Script**:
```bash
# Run tests 10 times, count failures
FAILURES=0
for i in {1..10}; do
    pytest tests/test_agent.py -v --tb=short
    if [ $? -ne 0 ]; then
        FAILURES=$((FAILURES + 1))
    fi
done

echo "Failures: $FAILURES/10"

# If FAILURES > 0 and < 10 → Flaky test
```

**Python Script**:
```python
import subprocess

failures = 0
runs = 10

for i in range(runs):
    result = subprocess.run(["pytest", "tests/test_agent.py", "-v"])
    if result.returncode != 0:
        failures += 1

if 0 < failures < runs:
    print(f"FLAKY TEST: {failures}/{runs} runs failed")
elif failures == runs:
    print("REAL FAILURE: All runs failed")
else:
    print("STABLE: All runs passed")
```

---

### Strategy 3: Run Tests in Parallel

**Purpose**: Reveal resource conflicts and shared state issues.

**Sequential (may pass)**:
```bash
pytest tests/ -v
# All tests pass (no resource conflicts)
```

**Parallel (may fail)**:
```bash
pytest tests/ -n auto -v
# Some tests fail (resource conflicts, shared state)
```

**Diagnosis**: Tests that fail in parallel but pass sequentially have isolation issues.

---

### Strategy 4: Run Tests in Random Order

**Purpose**: Detect order dependencies.

**Installation**:
```bash
pip install pytest-randomly
```

**Usage**:
```bash
pytest tests/ -v
# Tests run in random order each time

# If results vary → order dependency
```

**Seeded Random Order** (reproducible):
```bash
pytest tests/ -v --randomly-seed=1234
# Same random order each time with seed=1234
```

---

## Fixing Flaky Tests

### Step 1: Identify the Cause

**Add Logging**:
```python
def test_async_operation():
    result = async_operation()
    print(f"Result status: {result.status}")  # Debug output
    print(f"Result data: {result.data}")
    assert result.is_ready
```

**Run in Isolation**:
```bash
# Run test alone
pytest tests/test_agent.py::test_async_operation -v -s

# Run with pdb on failure
pytest tests/test_agent.py::test_async_operation -v --pdb
```

**Run Multiple Times**:
```bash
# Run 100 times to see intermittent pattern
for i in {1..100}; do
    pytest tests/test_agent.py::test_async_operation -v
done
```

---

### Step 2: Fix the Root Cause

**Race Condition**: Add synchronization (events, barriers).
```python
# Before: Flaky
def test_async_processing():
    queue.add_task("process_data")
    assert queue.get_result("process_data") is not None

# After: Fixed
def test_async_processing():
    queue.add_task("process_data")
    queue.wait_for_completion("process_data", timeout=5.0)
    assert queue.get_result("process_data") is not None
```

**Shared State**: Use db_session or unique_resource_name.
```python
# Before: Flaky
def test_create_user():
    user = User(id="test-user", ...)
    db.commit()

# After: Fixed
def test_create_user(db_session, unique_resource_name):
    user = UserFactory.create(_session=db_session, id=unique_resource_name)
```

**External Dependency**: Mock the dependency.
```python
# Before: Flaky
def test_api_call():
    result = requests.get("https://api.example.com/data")
    assert result.status_code == 200

# After: Fixed
@patch('requests.get')
def test_api_call(mock_get):
    mock_get.return_value.status_code = 200
    result = requests.get("https://api.example.com/data")
    assert result.status_code == 200
```

**Time Dependency**: Mock time with freezegun.
```python
# Before: Flaky
def test_token_expiry():
    token = create_token(expiry_hours=24)
    assert token.expires_at > datetime.now()

# After: Fixed
def test_token_expiry():
    with freeze_time("2026-02-11 10:00:00"):
        token = create_token(expiry_hours=24)
        assert token.expires_at == datetime(2026, 2, 12, 10, 0, 0)
```

---

### Step 3: Verify Fix

**Run 100 Times**:
```bash
for i in {1..100}; do
    pytest tests/test_agent.py::test_async_operation -v
done

# Should pass 100/100 times
```

**Run in Parallel**:
```bash
pytest tests/ -n auto -v

# Should pass in parallel too
```

**Run in Random Order**:
```bash
pytest tests/ -v  # With pytest-randomly

# Should pass regardless of order
```

---

### Step 4: Document Fix

**Add Comment**:
```python
def test_async_operation():
    """
    Test async operation completion.

    Note: Previously flaky due to race condition. Fixed by adding
    explicit wait_for_completion() instead of time.sleep().

    Bug: https://github.com/example/project/issues/123
    Fix: commit abc123 (2026-02-11)
    """
    queue.add_task("process_data")
    queue.wait_for_completion("process_data", timeout=5.0)
    assert queue.get_result("process_data") is not None
```

**Add to Changelog**:
```markdown
## Fixes
- Fix flaky test_async_operation by adding explicit synchronization
- Fix flaky test_create_user by using db_session fixture
```

---

## When to Use @pytest.mark.flaky

### Temporary Workaround

**Use Case**: Known flaky test while investigating root cause.

**Example**:
```python
import pytest

@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_external_api_integration():
    """
    Test external API integration.

    TODO: Fix flakiness (currently 10% failure rate)
    Issue: https://github.com/example/project/issues/456
    Root cause: API rate limiting
    Proposed fix: Add retry logic with exponential backoff
    """
    result = external_api_call()
    assert result["status"] == "success"
```

**Requirements**:
1. Must include TODO comment
2. Must link to GitHub issue
3. Must document root cause (if known)
4. Must NOT be permanent solution

---

### Known Issues Filed as Bugs

**Use Case**: Bug in production code, not test code.

**Example**:
```python
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_database_transaction():
    """
    Test database transaction rollback.

    FLAKY: Known bug in transaction handling (issue #789)
    Root cause: Race condition in connection pool
    Workaround: Retry test up to 3 times
    """
    with db.transaction():
        db.execute("INSERT INTO users (name) VALUES ('Alice')")
    # Bug: Transaction sometimes doesn't rollback
```

**Action**: Fix bug in production code, remove @flaky marker.

---

### NEVER a Permanent Solution

**Anti-Pattern**: Using @flaky to mask real issues.

**Bad**:
```python
# BAD: Permanent workaround (don't do this)
@pytest.mark.flaky(reruns=10)
def test_critical_payment_flow():
    result = process_payment(amount=100.00)
    assert result["status"] == "success"
```

**Why Bad**:
- Hides real bugs (payment failures!)
- Erodes confidence in test suite
- Slows CI (re-running flaky tests)
- Developers ignore failures

**Correct Approach**:
```python
# GOOD: Fix root cause
@patch('payment_gateway.charge')
def test_critical_payment_flow(mock_charge):
    mock_charge.return_value = {"status": "success"}
    result = process_payment(amount=100.00)
    assert result["status"] == "success"
```

---

## Real Examples from Codebase

### Example 1: Database Row Collision

**Flaky Test**:
```python
# FLAKY: Hardcoded ID causes collision
def test_create_agent():
    agent = AgentRegistry(id="test-agent", name="Test")
    db.add(agent)
    db.commit()
```

**Fixed**:
```python
# GOOD: Unique ID
def test_create_agent(unique_resource_name):
    agent = AgentFactory.create(id=unique_resource_name)
```

---

### Example 2: Race Condition in Async Test

**Flaky Test**:
```python
# FLAKY: Race condition
def test_episode_retrieval():
    episode = create_episode()
    results = search_service.search(episode.id)
    # May not be indexed yet
    assert episode.id in results
```

**Fixed**:
```python
# GOOD: Explicit wait
def test_episode_retrieval():
    episode = create_episode()
    search_service.wait_for_indexing(episode.id, timeout=5.0)
    results = search_service.search(episode.id)
    assert episode.id in results
```

---

### Example 3: Time-Dependent Token Expiry

**Flaky Test**:
```python
# FLAKY: Time-dependent
def test_token_expires_after_24_hours():
    token = create_token(expiry_hours=24)
    assert token.expires_at > datetime.now()  # Flaky near boundary
```

**Fixed**:
```python
# GOOD: Frozen time
def test_token_expires_after_24_hours():
    with freeze_time("2026-02-11 10:00:00"):
        token = create_token(expiry_hours=24)
        assert token.expires_at == datetime(2026, 2, 12, 10, 0, 0)
```

---

## Related Documentation

- **[TEST_ISOLATION_PATTERNS.md](./TEST_ISOLATION_PATTERNS.md)** - Test isolation patterns
- **[COVERAGE_GUIDE.md](./COVERAGE_GUIDE.md)** - Coverage interpretation
- **[../conftest.py](../conftest.py)** - Fixture definitions

---

## Summary

**Key Takeaways**:
1. **Flaky tests erode confidence**: Developers ignore failures, masking real bugs
2. **Root causes**: Race conditions, shared state, external deps, time, resources, order
3. **Prevention**: Explicit sync, mocks, unique names, rollback, no globals
4. **Detection**: pytest-rerunfailures, run 100x, parallel, random order
5. **Fixing**: Identify cause → Fix root → Verify 100x → Document fix

**Quick Reference**:
```python
# BAD: Flaky test
def test_async_operation():
    result = async_operation()
    time.sleep(0.1)  # Arbitrary
    assert result.is_ready

# GOOD: Fixed test
def test_async_operation():
    result = async_operation()
    result.wait_for_completion(timeout=5.0)  # Explicit
    assert result.is_ready
```

**Next Steps**:
1. Run tests 10 times to detect flakiness
2. Use pytest-rerunfailures to identify intermittent failures
3. Fix root causes (don't just add retries)
4. Verify fixes by running 100 times
5. Document fixes with comments and issue links
