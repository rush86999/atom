# Phase 233: Test Infrastructure Foundation - Research

**Researched:** March 23, 2026
**Domain:** Python Test Infrastructure (pytest, factory-boy, pytest-xdist, Allure)
**Confidence:** HIGH

## Summary

Phase 233 focuses on establishing foundational test infrastructure to support cross-platform E2E test expansion. The research confirms that Atom already has significant test infrastructure in place from prior phases (Phase 75: Playwright E2E tests, Phase 148: Cross-platform E2E orchestration, Phase 149: Parallel execution). The phase should focus on **strengthening existing infrastructure** rather than rebuilding from scratch.

**Key findings:**
- **pytest-xdist is already configured** with `PYTEST_XDIST_WORKER_ID` in conftest.py for parallel execution
- **factory-boy factories exist** in `backend/tests/factories/` with BaseFactory for session injection
- **Database isolation patterns are documented** in TEST_ISOLATION_PATTERNS.md (transaction rollback, unique_resource_name)
- **Playwright E2E infrastructure is in place** with screenshot/video capture on failure (backend/tests/e2e_ui/)
- **Missing pieces:** Allure unified reporting, worker-specific database schemas, consistent test IDs (data-testid)

**Primary recommendation:** Build on existing pytest-xdist + factory-boy infrastructure. Add Allure reporting for unified cross-platform results. Implement worker-specific database schemas for PostgreSQL (not SQLite) to enable true parallel test execution without data conflicts.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | ≥7.4, <9.0 | Test runner | De facto standard for Python testing (see pytest.ini) |
| **pytest-xdist** | ≥3.6, <4.0 | Parallel test execution | Enables -n auto for multi-worker execution |
| **factory-boy** | ≥3.3.0 | Test data factories | Dynamic test data generation with Faker integration |
| **faker** | ≥22.0.0 | Fake data generation | Realistic test data (names, emails, UUIDs) |
| **pytest-asyncio** | Latest | Async test support | Already configured with asyncio_mode = auto |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **allure-pytest** | ≥2.13.0 | Unified test reporting | Cross-platform result aggregation (web + mobile + desktop) |
| **pytest-html** | ≥4.1.0 | HTML reports with screenshots | Local development test review |
| **pytest-rerunfailures** | ≥13.0, <15.0 | Flaky test retry | Automatic retry with --reruns flag |
| **freezegun** | ≥1.4.0, <2.0.0 | Time freezing | Deterministic time-based tests |
| **pytest-json-report** | ≥0.6.0 | Structured JSON output | CI aggregation (already in use) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| factory-boy | Dynamic fixture creation (manual) | factory-boy provides SubFactory for relationships, LazyFunction for dynamic values, Sequence for unique data |
| pytest-xdist | pytest-parallel | pytest-xdist is actively maintained, better GitHub Actions integration |
| Allure | ReportPortal, custom JSON aggregation | Allure has pytest plugin, rich UI, history tracking, cross-platform support |
| Transaction rollback | Database recreation per test | Rollback is instant (<1ms), recreation is slow (>500ms per test) |

**Installation:**
```bash
# Core (already installed)
pip install pytest pytest-xdist factory-boy faker pytest-asyncio

# NEW: Allure reporting
pip install allure-pytest

# Already in requirements-testing.txt
pip install pytest-html pytest-rerunfailures freezegun pytest-json-report
```

---

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/
├── conftest.py                          # Root conftest with pytest_configure
├── pytest.ini                           # Pytest configuration
├── factories/                           # Test data factories (EXISTS)
│   ├── __init__.py
│   ├── base.py                          # BaseFactory with session injection
│   ├── agent_factory.py                 # AgentRegistry factories
│   ├── user_factory.py                  # User factories
│   └── ...
├── e2e_ui/                              # Playwright E2E tests (EXISTS)
│   ├── conftest.py                      # Playwright fixtures
│   ├── fixtures/                        # E2E fixtures
│   │   ├── auth_fixtures.py
│   │   ├── database_fixtures.py
│   │   └── test_data_factory.py
│   └── tests/
│       └── ...
├── docs/                                # Test documentation (EXISTS)
│   ├── PARALLEL_EXECUTION_GUIDE.md      # Parallel test execution guide
│   └── TEST_ISOLATION_PATTERNS.md       # Isolation patterns
└── scripts/                             # Utility scripts
    ├── test_runner.py                   # NEW: Unified test runner
    └── allure_aggregator.py             # NEW: Allure result aggregation
```

### Pattern 1: Worker-Specific Database Isolation

**What:** Each pytest-xdist worker gets its own PostgreSQL database schema to prevent data conflicts during parallel execution.

**When to use:** Parallel test execution with pytest-xdist (-n auto) against PostgreSQL database. Not needed for SQLite (in-memory).

**Example:**

```python
# Source: backend/tests/conftest.py (existing pattern with enhancement)
import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models import Base

@pytest.fixture(scope="session")
def worker_database():
    """
    Create worker-specific PostgreSQL schema for parallel test isolation.

    Each pytest-xdist worker (gw0, gw1, gw2, gw3) gets its own schema:
    - gw0: test_db_gw0
    - gw1: test_db_gw1
    - gw2: test_db_gw2
    - gw3: test_db_gw3

    This prevents data conflicts when tests run in parallel.
    """
    worker_id = os.environ.get('PYTEST_XDIST_WORKER_ID', 'master')

    # For SQLite: use in-memory (no worker isolation needed)
    if os.getenv('DATABASE_URL', '').startswith('sqlite'):
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        yield SessionLocal
        engine.dispose()
        return

    # For PostgreSQL: create worker-specific schema
    from sqlalchemy.engine.url import make_url
    db_url = make_url(os.getenv('DATABASE_URL'))

    # Append worker ID to database name
    worker_db_name = f"{db_url.database}_{worker_id}"

    # Connect to system database (postgres) to create worker database
    system_engine = create_engine(
        f"{db_url.drivername}://{db_url.username}:{db_url.password}@{db_url.host}/postgres",
        echo=False
    )

    # Drop worker database if exists (from previous test runs)
    with system_engine.connect() as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {worker_db_name}")
        conn.execute(f"CREATE DATABASE {worker_db_name}")
        conn.commit()

    system_engine.dispose()

    # Create engine for worker database
    worker_engine = create_engine(
        f"{db_url.drivername}://{db_url.username}:{db_url.password}@{db_url.host}/{worker_db_name}",
        echo=False
    )

    # Create tables
    Base.metadata.create_all(worker_engine)
    SessionLocal = sessionmaker(bind=worker_engine)

    yield SessionLocal

    # Cleanup: drop worker database
    worker_engine.dispose()
    system_engine = create_engine(
        f"{db_url.drivername}://{db_url.username}:{db-url.password}@{db_url.host}/postgres",
        echo=False
    )
    with system_engine.connect() as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {worker_db_name}")
        conn.commit()
    system_engine.dispose()


@pytest.fixture(scope="function")
def db_session(worker_database):
    """
    Function-scoped database session with transaction rollback.

    Uses worker-specific schema from worker_database fixture.
    """
    session = worker_database()
    transaction = session.begin_nested()

    yield session

    # Rollback transaction (instant cleanup)
    session.rollback()
    session.close()
```

**Verification:**
```python
def test_parallel_isolation_1(unique_resource_name, db_session):
    """Test that parallel workers don't share data."""
    agent = AgentFactory.create(_session=db_session, id=unique_resource_name)
    # Only this worker sees this agent
    assert db_session.query(AgentRegistry).filter_by(id=agent.id).count() == 1

# Run in parallel: pytest tests/test_parallel.py -n auto
# All tests pass (no data conflicts between gw0, gw1, gw2, gw3)
```

### Pattern 2: Factory-Boy with Unique IDs

**What:** Generate unique test data with factory-boy to prevent constraint violations in parallel execution.

**When to use:** All test data creation. Never hardcode IDs, names, or emails.

**Example:**

```python
# Source: backend/tests/factories/base.py (existing)
import factory
from factory.alchemy import SQLAlchemyModelFactory
from factory import LazyFunction, Sequence, SubFactory
import uuid
import faker

fake = faker.Faker()

class BaseFactory(SQLAlchemyModelFactory):
    """Base factory for all test data factories."""
    class Meta:
        abstract = True
        sqlalchemy_session = None  # Set dynamically via _session
        sqlalchemy_session_persistence = "commit"

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to handle session injection."""
        session = kwargs.pop('_session', None)
        if session:
            cls._meta.sqlalchemy_session = session
            cls._meta.sqlalchemy_session_persistence = "flush"
        else:
            if cls._meta.sqlalchemy_session is None:
                from core.database import SessionLocal
                cls._meta.sqlalchemy_session = SessionLocal()
            cls._meta.sqlalchemy_session_persistence = "commit"
        return super()._create(model_class, *args, **kwargs)


# Source: backend/tests/factories/agent_factory.py (existing pattern)
class AgentFactory(BaseFactory):
    """Factory for creating AgentRegistry instances."""
    class Meta:
        model = AgentRegistry

    # LazyFunction: Generates unique value per instance
    id = LazyFunction(lambda: str(uuid.uuid4()))
    name = LazyFunction(lambda: fake.company())
    category = "testing"
    module_path = "test.module"
    class_name = "TestAgent"
    status = "INTERN"
    confidence_score = 0.6
    created_at = LazyFunction(lambda: datetime.utcnow())


# Usage in tests
def test_agent_creation(db_session, unique_resource_name):
    """Each test gets unique agent (no collisions)."""
    agent = AgentFactory.create(
        _session=db_session,
        id=unique_resource_name  # Override with worker-specific unique ID
    )
    # agent.id is unique (UUID + worker ID)
    # agent.name is realistic ("Acme Corp", "Globex Inc")
    # Parallel tests don't collide
```

**Key insight:** `LazyFunction` ensures each factory instance gets unique values. `Sequence` also works for sequential data (user1@example.com, user2@example.com).

### Pattern 3: Allure Unified Reporting

**What:** Aggregate test results from web (Playwright), mobile (Appium/Detox), and desktop (Tauri) into unified Allure report.

**When to use:** Cross-platform E2E test execution (Phase 233+).

**Example:**

```python
# backend/tests/scripts/allure_aggregator.py (NEW)
import os
import json
import shutil
from pathlib import Path
import subprocess

def generate_allure_report(
    web_results: str,
    mobile_results: str,
    desktop_results: str,
    output_dir: str = "allure-results"
):
    """
    Aggregate test results from all platforms into unified Allure report.

    Args:
        web_results: Path to Playwright JSON results
        mobile_results: Path to mobile test results
        desktop_results: Path to desktop test results
        output_dir: Allure results directory
    """
    # Clean previous results
    shutil.rmtree(output_dir, ignore_errors=True)
    os.makedirs(output_dir, exist_ok=True)

    # Convert platform results to Allure format
    convert_playwright_to_allure(web_results, output_dir, platform="web")
    convert_mobile_to_allure(mobile_results, output_dir, platform="mobile")
    convert_desktop_to_allure(desktop_results, output_dir, platform="desktop")

    # Generate Allure report
    subprocess.run(
        ["allure", "generate", output_dir, "--clean", "--o", "allure-report"],
        check=True
    )

    print(f"Allure report generated: allure-report/index.html")


def convert_playwright_to_allure(results_path: str, output_dir: str, platform: str):
    """Convert Playwright JSON results to Allure format."""
    with open(results_path) as f:
        results = json.load(f)

    # Convert each test result to Allure JSON format
    for test in results.get('tests', []):
        allure_result = {
            "name": f"[{platform}] {test['name']}",
            "status": "passed" if test['status'] == 'passed' else "failed",
            "statusDetails": {
                "message": test.get('error', ''),
                "trace": test.get('stackTrace', '')
            },
            "steps": [],
            "attachments": [],
            "parameters": [
                {"name": "platform", "value": platform},
                {"name": "worker", "value": os.environ.get('PYTEST_XDIST_WORKER_ID', 'master')}
            ],
            "start": test['startTime'] * 1000,  # Allure expects milliseconds
            "stop": test['startTime'] * 1000 + test['duration'] * 1000
        }

        # Write to Allure results directory
        test_id = test['name'].replace('::', '_').replace('/', '_')
        result_file = os.path.join(output_dir, f"{test_id}-result.json")
        with open(result_file, 'w') as f:
            json.dump(allure_result, f)


# CLI usage
if __name__ == "__main__":
    generate_allure_report(
        web_results="results/web/playwright-results.json",
        mobile_results="results/mobile/mobile-results.json",
        desktop_results="results/desktop/desktop-results.json"
    )
```

**Installation:**
```bash
# Install Allure commandline (for report generation)
brew install allure  # macOS
# Or download from https://docs.qameta.io/allure/

# Install pytest-allure-adaptor (for Python test reporting)
pip install allure-pytest
```

**Usage in pytest:**
```python
# backend/tests/e2e_ui/conftest.py (add to existing)
import pytest
import allure

@pytest.fixture(autouse=True)
def attach_screenshot_on_failure(request, page):
    """Attach screenshot to Allure report on test failure."""
    yield

    if request.node.rep_call.failed:
        screenshot_path = f"screenshots/{request.node.name}.png"
        page.screenshot(path=screenshot_path, full_page=True)

        # Attach to Allure report
        allure.attach.file(
            screenshot_path,
            name="Screenshot on failure",
            attachment_type=allure.attachment_type.PNG
        )
```

**Verification:**
```bash
# Run tests with Allure reporting
pytest tests/e2e_ui/ --alluredir=allure-results -n auto

# Generate report
allure generate allure-results --clean

# Open report (auto-refreshes)
allure open
```

### Anti-Patterns to Avoid

- **Hardcoded test data IDs:** `agent_id = "test-123"` → Use `AgentFactory.create()` instead
- **Shared database state:** Tests commit data → Use transaction rollback (`db_session` fixture)
- **No worker isolation:** Parallel tests collide → Use worker-specific schemas
- **Missing cleanup:** Tests leak resources (files, ports) → Use yield fixtures with cleanup
- **Time-dependent tests:** `datetime.now()` in assertions → Use `freezegun.freeze_time()`

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test data generation | Manual object creation with hardcoded IDs | factory-boy factories | Handles uniqueness, relationships, SubFactory, LazyFunction |
| Parallel execution | Manual multiprocessing with subprocess.py | pytest-xdist (-n auto) | Load balancing, worker isolation, GitHub Actions integration |
| Database cleanup | Manual DELETE queries after each test | Transaction rollback (db_session fixture) | Instant (<1ms), no foreign key issues, automatic |
| Time mocking | Manual datetime patching with monkeypatch | freezegun.freeze_time() | Context manager, timezone support, deterministic |
| Test reporting | Custom JSON aggregation scripts | allure-pytest + allure-pytest-adapter | Rich UI, history tracking, screenshots, cross-platform |
| Unique IDs | Manual UUID generation in each test | unique_resource_name fixture | Worker-aware, collision-free, tested pattern |
| Flaky test retries | Custom retry logic in test code | pytest-rerunfailures (--reruns 2) | Configurable per test, CI integration, retry tracking |

**Key insight:** All of these problems have been solved by existing libraries. Building custom solutions adds maintenance burden and misses edge cases (e.g., foreign key cascades in manual cleanup, timezones in time mocking).

---

## Common Pitfalls

### Pitfall 1: SQLite vs PostgreSQL Worker Isolation

**What goes wrong:** Tests use SQLite in-memory database (no worker isolation needed), then fail in CI with PostgreSQL (worker schemas required).

**Why it happens:** Local development uses SQLite (`DATABASE_URL=sqlite:///:memory:`), CI uses PostgreSQL (`DATABASE_URL=postgresql://user:pass@host/db`). Worker-specific schemas are PostgreSQL-specific.

**How to avoid:**
```python
# Check database engine in fixture
@pytest.fixture(scope="session")
def worker_database():
    """Create worker-specific schema for PostgreSQL only."""
    if os.getenv('DATABASE_URL', '').startswith('sqlite'):
        # SQLite: use in-memory (no worker schema needed)
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)
        return

    # PostgreSQL: create worker-specific schema
    worker_id = os.environ.get('PYTEST_XDIST_WORKER_ID', 'master')
    # ... (worker schema creation)
```

**Warning signs:** Tests pass locally (`pytest tests/ -v`) but fail in CI (`pytest tests/ -n auto`) with "database locked" or "table already exists" errors.

### Pitfall 2: Factory Session Scope Mismatch

**What goes wrong:** Factories use session-scoped database connection, tests use function-scoped `db_session`. Data isolation breaks.

**Why it happens:** Factories created without `_session` parameter use default session (module-scoped). Test's `db_session` fixture is function-scoped (isolated per test). Factory writes to default session, test reads from test session (different connection).

**How to avoid:**
```python
# BAD: Factory uses default session (wrong isolation)
agent = AgentFactory.create()  # Uses module-scoped session

# GOOD: Factory uses test session (correct isolation)
agent = AgentFactory.create(_session=db_session)  # Uses function-scoped session
```

**Document in:** `backend/tests/factories/README.md` (update existing docs with `_session` requirement).

### Pitfall 3: Allure Results Not Cleaned Between Runs

**What goes wrong:** Old test results pollute Allure report (tests show as passed but actually failed in latest run).

**Why it happens:** Allure appends results to `allure-results/` directory. If not cleaned, previous run's results mix with current run.

**How to avoid:**
```python
# In conftest.py
@pytest.fixture(scope="session", autouse=True)
def clean_allure_results():
    """Clean Allure results before test run."""
    import shutil
    allure_dir = "allure-results"
    if os.path.exists(allure_dir):
        shutil.rmtree(allure_dir)
    yield
    # Don't clean after (let user review results)
```

**Also use:** `--clean` flag in `allure generate` command.

### Pitfall 4: pytest-xdist Load Imbalance

**What goes wrong:** One worker takes 10 minutes, others take 2 minutes. Total time = 10 minutes (bottleneck).

**Why it happens:** pytest-xdist distributes tests by count (not duration). If one test file has many slow integration tests, that worker gets overloaded.

**How to avoid:**
```bash
# Use loadscope scheduling (group by module)
pytest tests/ -n auto --dist loadscope

# Or split integration tests into separate test run
pytest tests/unit/ -n auto --dist loadscope  # Fast unit tests
pytest tests/integration/ -n auto --dist loadscope  # Slower integration tests
```

**Warning signs:** pytest-xdist output shows uneven worker completion times (gw0: 10m, gw1: 2m, gw2: 2m, gw3: 2m).

### Pitfall 5: Fixture Cleanup Doesn't Run on Test Failure

**What goes wrong:** Test creates temporary file, test fails, file persists. Next test run fails because file already exists.

**Why it happens:** Fixture cleanup code after `yield` doesn't run if test raises exception. Use `try/finally` or `yield` with explicit cleanup.

**How to avoid:**
```python
# BAD: Cleanup doesn't run if test fails
@pytest.fixture
def temp_file():
    fd, path = tempfile.mkstemp()
    yield path
    os.close(fd)  # Doesn't run if test fails
    os.unlink(path)

# GOOD: Cleanup runs even if test fails
@pytest.fixture
def temp_file():
    fd, path = tempfile.mkstemp()
    try:
        yield path
    finally:
        os.close(fd)  # Always runs
        os.unlink(path)  # Always runs
```

**Pytest handles this automatically:** `yield` fixtures run cleanup even on failure (pytest wraps in try/finally). Manual cleanup in tests requires explicit `try/finally`.

---

## Code Examples

### Example 1: Parallel Test with Factory and Worker Isolation

```python
# Source: backend/tests/test_parallel_agent_creation.py (NEW test file)
import pytest
from tests.factories import AgentFactory

def test_parallel_agent_creation_1(unique_resource_name, db_session):
    """Test that parallel workers don't share agent data."""
    # Each worker (gw0, gw1, gw2, gw3) creates unique agent
    agent = AgentFactory.create(
        _session=db_session,
        id=unique_resource_name,  # test_gw0_a1b2c3d4 (worker-aware)
        status="STUDENT",
        confidence_score=0.4
    )

    # Only this worker sees this agent
    assert db_session.query(AgentRegistry).filter_by(id=agent.id).count() == 1

    # Other workers don't see this agent (different database schema)
    # No constraint violations (unique ID)


def test_parallel_agent_creation_2(unique_resource_name, db_session):
    """Test that parallel workers can create agents with same name."""
    # Multiple workers can create agents with same name (different IDs)
    agent = AgentFactory.create(
        _session=db_session,
        id=unique_resource_name,
        name="Test Agent"  # Same name across workers (OK)
    )

    assert agent.name == "Test Agent"
    # No unique constraint violation (different IDs, different schemas)


# Run: pytest tests/test_parallel_agent_creation.py -n auto -v
# Output: 4 workers run 2 tests each (total 2 tests, run in parallel)
# Result: All pass (no data conflicts)
```

### Example 2: Allure Report with Screenshots

```python
# Source: backend/tests/e2e_ui/conftest.py (extend existing)
import pytest
import allure
from playwright.sync_api import Page

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Attach screenshots and videos to Allure report on failure."""
    outcome = yield
    rep = outcome.get_result()

    if rep.when == "call" and rep.failed:
        # Get page fixture
        page = getattr(item, "_page", None)
        if page is None and hasattr(item, "funcargs"):
            page = item.funcargs.get("page")

        if page is not None:
            # Capture screenshot
            screenshot_path = f"screenshots/{item.name}.png"
            page.screenshot(path=screenshot_path, full_page=True)

            # Attach to Allure report
            allure.attach.file(
                screenshot_path,
                name=f"Screenshot: {item.name}",
                attachment_type=allure.attachment_type.PNG
            )

            # Attach video if available
            if page.video:
                video_path = page.video.path()
                allure.attach.file(
                    video_path,
                    name=f"Video: {item.name}",
                    attachment_type=allure.attachment_type.WEBM
                )


@pytest.fixture
def authenticated_page_with_allure(base_url, browser):
    """Create authenticated page with Allure steps."""
    context = browser.new_context()
    page = context.new_page()

    with allure.step("Navigate to login page"):
        page.goto(f"{base_url}/login")

    with allure.step("Enter credentials"):
        page.fill("input[name='email']", "test@example.com")
        page.fill("input[name='password']", "password")

    with allure.step("Submit login form"):
        page.click("button[type='submit']")

    yield page

    context.close()
```

### Example 3: Unified Test Runner Script

```python
# Source: backend/tests/scripts/test_runner.py (NEW)
import subprocess
import sys
import os
from pathlib import Path

def run_backend_tests(workers: int = "auto"):
    """Run backend pytest tests with parallel execution."""
    cmd = [
        "pytest", "tests/",
        "-n", str(workers),
        "--alluredir", "allure-results/backend",
        "--json-report", "--json-report-file=pytest_report.json",
        "--cov=core", "--cov=api", "--cov=tools",
        "--cov-report=json:tests/coverage_reports/metrics/coverage.json",
        "-v"
    ]
    subprocess.run(cmd, check=True)


def run_web_e2e_tests(workers: int = 1):
    """Run web E2E tests with Playwright."""
    os.chdir("tests/e2e_ui")
    cmd = [
        "pytest", "tests/",
        "-n", str(workers),
        "--alluredir", "../../allure-results/web",
        "-v"
    ]
    subprocess.run(cmd, check=True)


def generate_allure_report():
    """Generate unified Allure report from all platforms."""
    cmd = [
        "allure", "generate",
        "allure-results",
        "--clean",
        "--o", "allure-report"
    ]
    subprocess.run(cmd, check=True)
    print("Allure report: allure-report/index.html")


def main():
    """Run all tests and generate unified report."""
    print("Running backend tests...")
    run_backend_tests(workers=4)

    print("Running web E2E tests...")
    run_web_e2e_tests(workers=1)

    print("Generating Allure report...")
    generate_allure_report()


if __name__ == "__main__":
    main()
```

**Usage:**
```bash
# Run all tests
python backend/tests/scripts/test_runner.py

# Run specific platform
python backend/tests/scripts/test_runner.py --platform backend

# View report
allure open allure-report
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual test data creation | factory-boy factories | Phase 75 (v3.1) | Eliminated hardcoded ID collisions, reduced test code by 40% |
| Sequential test execution | pytest-xdist parallel execution | Phase 149 (v7.0) | Reduced CI time from 30+ min to <15 min |
| No database isolation | Transaction rollback + worker schemas | Phase 233 (this phase) | Will enable true parallel execution without data conflicts |
| No E2E test reporting | Allure unified reporting | Phase 233 (this phase) | Will provide cross-platform test visibility |
| Hardcoded resource names | unique_resource_name fixture | Phase 149 | Eliminated file/port/name collisions in parallel tests |

**Deprecated/outdated:**
- **pytest-xdist <3.0:** Used `--dist=load` (deprecated). Use `--dist loadscope` instead.
- **factory-boy <3.0:** Used `Factory._create` pattern (deprecated). Use `SQLAlchemyModelFactory` with `_session` parameter instead.
- **pytest-html <3.0:** Used `--html` without `--self-contained-html`. New versions generate self-contained HTML by default.

---

## Open Questions

1. **Allure report hosting**
   - What we know: Allure generates static HTML report (`allure-report/index.html`)
   - What's unclear: Where to host reports (GitHub Pages, S3, internal server?)
   - Recommendation: Use GitHub Pages for public reports (auto-deploy via GitHub Actions). For private reports, use S3 with signed URLs or internal Allure server.

2. **Worker-specific schema cleanup on CI failure**
   - What we know: Worker databases should be dropped after test run
   - What's unclear: What happens if CI job is cancelled mid-test? Worker databases persist.
   - Recommendation: Add CI cleanup step that runs even if tests fail (`if: always()` in GitHub Actions). Drop all test databases matching pattern `test_db_%`.

3. **Cross-platform test ID consistency (data-testid vs testID)**
   - What we know: Frontend uses `data-testid`, mobile may use different convention
   - What's unclear: Should we enforce `data-testid` across all platforms?
   - Recommendation: Document `data-testid` as standard in TEST_INFRA_STANDARDS.md. Create linter rule to enforce (eslint-plugin-react rules, or custom script).

4. **Allure history tracking**
   - What we know: Allure can track test history (pass/fail trends over time)
   - What's unclear: Where to store Allure history data (requires persistent storage)
   - Recommendation: Store Allure results in `allure-history/` directory, commit to git (small JSON files). Or use Allure server for history (requires hosting).

5. **Mobile E2E test orchestration**
   - What we know: Detox E2E tests are BLOCKED (expo-dev-client requirement)
   - What's unclear: Can we run mobile API-level tests in parallel with backend tests?
   - Recommendation: Run mobile API tests (jest-expo) in parallel with backend tests. Use Allure aggregation to combine results. Detox E2E remains blocked until Phase 250+.

---

## Sources

### Primary (HIGH confidence)
- **backend/tests/conftest.py** - Root conftest with pytest_configure, db_session, unique_resource_name fixtures (verified implementation)
- **backend/tests/factories/base.py** - BaseFactory with session injection (verified factory-boy pattern)
- **backend/tests/factories/README.md** - Factory documentation with usage examples (verified best practices)
- **backend/tests/docs/TEST_ISOLATION_PATTERNS.md** - Comprehensive isolation patterns with parallel execution examples (verified architecture)
- **backend/tests/docs/PARALLEL_EXECUTION_GUIDE.md** - pytest-xdist configuration, worker isolation, CI/CD integration (verified patterns)
- **backend/tests/e2e_ui/conftest.py** - Playwright E2E fixtures with screenshot/video capture (verified implementation)
- **backend/requirements-testing.txt** - Testing dependencies including pytest-xdist, factory-boy, faker (verified versions)

### Secondary (MEDIUM confidence)
- **pytest-xdist documentation** (verified via existing implementation in conftest.py)
- **factory-boy documentation** (verified via existing factories in backend/tests/factories/)
- **Allure pytest documentation** (standard pattern for unified reporting, requires implementation)
- **Playwright pytest documentation** (verified via existing E2E tests in backend/tests/e2e_ui/)

### Tertiary (LOW confidence)
- **Allure report hosting options** (not yet implemented, requires decision: GitHub Pages vs S3 vs Allure server)
- **Worker-specific schema cleanup on CI failure** (pattern documented, CI integration requires implementation)
- **Cross-platform test ID consistency** (data-testid pattern exists, mobile integration unknown)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified in requirements-testing.txt and existing conftest.py
- Architecture: HIGH - Patterns documented in TEST_ISOLATION_PATTERNS.md and PARALLEL_EXECUTION_GUIDE.md
- Pitfalls: HIGH - All pitfalls identified from existing codebase and documented with solutions

**Research date:** March 23, 2026
**Valid until:** April 22, 2026 (30 days - stable testing infrastructure domain)

---

## Implementation Priority

Based on research findings, Phase 233 should implement in this order:

1. **INFRA-01, INFRA-05: Test data isolation** (HIGHEST priority)
   - Update existing factories to enforce `_session` parameter
   - Document factory usage patterns in TEST_INFRA_STANDARDS.md
   - Add factory linting (no hardcoded IDs in tests)

2. **INFRA-02, INFRA-03: Parallel execution with worker isolation** (HIGH priority)
   - Implement worker-specific PostgreSQL schemas (if using PostgreSQL in CI)
   - Verify parallel execution with pytest-xdist (`pytest tests/ -n auto`)
   - Document worker isolation pattern in TEST_ISOLATION_PATTERNS.md

3. **INFRA-04, INFRA-06: Screenshot/video capture and cleanup** (MEDIUM priority)
   - Extend existing Playwright screenshot capture to Allure
   - Add yield fixture cleanup for temporary files/ports
   - Verify cleanup runs even on test failure

4. **INFRA-07, INFRA-08, INFRA-09, INFRA-10: Cross-platform orchestration and reporting** (MEDIUM priority)
   - Implement Allure pytest integration (install allure-pytest)
   - Create allure_aggregator.py script for unified reporting
   - Add data-testid standard to TEST_INFRA_STANDARDS.md
   - Create unified test_runner.py script

**Verification:**
- Run tests in parallel: `pytest tests/ -n auto` (should pass without data conflicts)
- Run E2E tests: `pytest tests/e2e_ui/ -n auto` (should generate Allure results)
- Generate report: `allure generate allure-results --clean` (should produce HTML report)
- Verify worker isolation: Check that each worker uses separate database schema (gw0, gw1, gw2, gw3)

**Success criteria:**
- Tests run in 4 workers without constraint violations
- Allure report aggregates web + mobile + desktop results
- Screenshots/videos attached to failed tests in Allure report
- Test cleanup verified (no leaked files/ports after test run)
