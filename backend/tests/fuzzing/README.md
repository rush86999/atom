# API Fuzzing Infrastructure

**Coverage-guided crash discovery for FastAPI endpoints using Atheris**

## Overview

API fuzzing is a automated testing technique that generates malformed, unexpected, or random inputs to discover crashes, vulnerabilities, and edge cases in API endpoints. Atom uses **Atheris** (Google's coverage-guided fuzzer for Python) to perform intelligent fuzzing on critical API endpoints.

### Why Atheris?

- **Coverage-guided**: Uses code coverage to intelligently mutate inputs and explore new code paths
- **Python-native**: Direct integration with pytest and Python codebase
- **Crash discovery**: Finds memory corruption, assertion failures, and unhandled exceptions
- **Performance**: 10,000+ iterations per endpoint in ~5-10 minutes
- **CI/CD integration**: Automated weekly campaigns with crash deduplication and bug filing

### Goal

Discover crashes in parsing, validation, and business logic code before attackers do. Fuzzing complements unit tests, integration tests, and property-based testing by exploring input spaces that human-written tests miss.

## Quick Start

### Install Dependencies

```bash
# Install Atheris (fuzzing engine)
pip install atheris

# Or install with testing dependencies
cd backend
pip install -r requirements-testing.txt
```

### Run Single Fuzz Test

```bash
# Quick verification (100 iterations)
FUZZ_ITERATIONS=100 pytest tests/fuzzing/test_auth_api_fuzzing.py::test_login_endpoint_fuzzing -v -m fuzzing

# Full fuzzing campaign (10,000 iterations)
FUZZ_ITERATIONS=10000 pytest tests/fuzzing/test_auth_api_fuzzing.py::test_login_endpoint_fuzzing -v -m fuzzing
```

### Run All Fuzz Tests

```bash
# Run all fuzzing tests (quick verification)
FUZZ_ITERATIONS=100 pytest tests/fuzzing/ -v -m fuzzing

# Run all fuzzing tests (full campaign)
FUZZ_ITERATIONS=10000 pytest tests/fuzzing/ -v -m fuzzing
```

### Run Fuzzing Campaign

```bash
# Run all campaigns for 60 seconds (quick test)
python3 tests/fuzzing/scripts/run_fuzzing_campaigns.py --duration 60

# Run all campaigns for 1 hour (full campaign)
python3 tests/fuzzing/scripts/run_fuzzing_campaigns.py --duration 3600

# Run single campaign
python3 tests/fuzzing/scripts/run_fuzzing_campaigns.py --duration 3600 --campaign "POST /api/auth/login"
```

## Fuzzing Infrastructure

### FuzzingOrchestrator

**Location**: `tests/fuzzing/campaigns/fuzzing_orchestrator.py`

Service for managing fuzzing campaigns:

```python
from tests.fuzzing.campaigns.fuzzing_orchestrator import FuzzingOrchestrator

orchestrator = FuzzingOrchestrator(github_token="...", github_repository="owner/repo")

# Start campaign
result = orchestrator.start_campaign(
    target_endpoint="POST /api/auth/login",
    test_file="tests/fuzzing/test_auth_api_fuzzing.py::test_login_endpoint_fuzzing",
    duration_seconds=3600
)

# Monitor campaign
stats = orchestrator.monitor_campaign(result["campaign_id"])

# Stop campaign
orchestrator.stop_campaign(result["campaign_id"])
```

**Features**:
- Campaign lifecycle management (start, stop, monitor)
- Subprocess management with graceful shutdown (SIGTERM → SIGKILL)
- Crash deduplication integration
- Automated bug filing via BugFilingService
- Campaign statistics tracking (executions, crashes, coverage)

### CrashDeduplicator

**Location**: `tests/fuzzing/campaigns/crash_deduplicator.py`

Crash deduplication using SHA256 hashing of error signatures:

```python
from tests.fuzzing.campaigns.crash_deduplicator import CrashDeduplicator

deduplicator = CrashDeduplicator()
crashes_by_signature = deduplicator.deduplicate_crashes(crash_dir)

# Get unique crashes
unique_crashes = deduplicator.get_unique_crashes(crashes_by_signature)

# Get signature summary
summary = deduplicator.get_signature_summary(crashes_by_signature)
```

**Features**:
- SHA256-based crash deduplication
- Stack trace extraction from crash logs
- Normalized error signatures (line numbers removed for stable hashing)
- Unique crash identification for bug filing

### BugFilingService

**Location**: `tests/bug_discovery/bug_filing_service.py` (from Phase 236)

Automated GitHub issue filing for discovered crashes:

```python
from tests.bug_discovery.bug_filing_service import BugFilingService

bug_service = BugFilingService(github_token, github_repository)

bug_result = bug_service.file_bug(
    test_name="fuzzing_POST_api_auth_login",
    error_message="Crash in POST /api/auth/login: AssertionError...",
    metadata={
        "test_type": "fuzzing",
        "target_endpoint": "POST /api/auth/login",
        "crash_input": "deadbeef...",
        "crash_log": "Traceback...",
        "signature_hash": "abc123..."
    }
)
```

**Features**:
- Duplicate bug detection (via existing issues)
- Automatic labeling (bug-discovery, fuzzing)
- Crash metadata attachment (input hex, stack trace, signature)
- CI/CD integration (automatic filing on crashes)

### Corpus Management

**Location**: `tests/fuzzing/campaigns/corpus/`

Corpus files contain interesting inputs discovered during fuzzing:

```bash
# Corpus directory structure
tests/fuzzing/campaigns/corpus/
├── auth/
│   ├── login_valid.input
│   ├── login_sql_injection.input
│   └── login_null_bytes.input
├── agent/
│   ├── agent_run_malformed.input
│   └── agent_run_huge_payload.input
└── workflow/
    ├── workflow_create_cyclic.input
    └── workflow_create_xss.input
```

**Purpose**:
- Re-seeding: Use corpus to speed up future campaigns
- Coverage: Corpus inputs explore interesting code paths
- Reproduction: Each input is reproducible crash trigger

**Usage**:
```bash
# Re-seed campaign with corpus
FUZZ_CORPUS_DIR="tests/fuzzing/campaigns/corpus/auth" \
FUZZ_ITERATIONS=10000 \
pytest tests/fuzzing/test_auth_api_fuzzing.py -v -m fuzzing
```

## Fuzzing Test Structure

### Test File Pattern

```
tests/fuzzing/test_<endpoint>_fuzzing.py
```

**Examples**:
- `test_auth_api_fuzzing.py` - Authentication endpoints
- `test_agent_api_fuzzing.py` - Agent execution endpoints
- `test_canvas_presentation_fuzzing.py` - Canvas presentation endpoints
- `test_workflow_api_fuzzing.py` - Workflow management endpoints
- `test_skill_installation_fuzzing.py` - Skill import endpoints

### Pytest Markers

All fuzzing tests use three markers:

```python
@pytest.mark.fuzzing      # Identifies fuzzing tests
@pytest.mark.slow         # Indicates long-running tests
@pytest.mark.timeout(300) # 5-minute timeout per test
```

**Usage**:
```bash
# Run only fuzzing tests
pytest tests/fuzzing/ -v -m fuzzing

# Run fuzzing + chaos tests
pytest tests/ -v -m "fuzzing or chaos"

# Exclude fuzzing from quick test runs
pytest tests/ -v -m "not fuzzing"
```

### Fixtures

Fuzzing tests reuse fixtures from `tests/e2e_ui/fixtures/`:

```python
from tests.e2e_ui.fixtures.database_fixtures import db_session
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user, test_user
```

**Benefits**:
- No duplication (reuse existing fixtures)
- Worker-based database isolation
- API-first auth (10-100x faster than UI login)
- Transaction rollback for cleanup

**Example**:
```python
@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_login_endpoint_fuzzing(db_session, authenticated_user):
    """Fuzz POST /api/auth/login endpoint."""
    # db_session: Isolated database session
    # authenticated_user: Pre-created user with valid credentials
    pass
```

### Crash Artifacts

Crash artifacts are saved to `FUZZ_CRASH_DIR` environment variable:

```bash
export FUZZ_CRASH_DIR=/tmp/fuzz_crashes

# Crashes saved to:
# - /tmp/fuzz_crashes/login_*.input (crashing input)
# - /tmp/fuzz_crashes/login_*.log (stack trace)
```

**Artifact Format**:
- `*.input` - Binary input that triggered crash
- `*.log` - Python stack trace and error message

**Usage in CI**:
```yaml
- name: Upload crash artifacts
  uses: actions/upload-artifact@v3
  with:
    name: fuzzing-crashes
    path: backend/tests/fuzzing/campaigns/crashes/
    retention-days: 90
```

## Coverage

### Authentication Endpoints (FUZZ-03)

**Test File**: `test_auth_api_fuzzing.py`

- ✅ POST /api/auth/login - Login with email/password
- ✅ POST /api/auth/signup - User registration
- ✅ POST /api/auth/mobile/login - Mobile login with device token

**Test File**: `test_jwt_validation_fuzzing.py`

- ✅ GET /api/agents - Protected endpoint (JWT validation)
- ✅ JWT token parsing (header, payload, signature)
- ✅ JWT expiry validation (timestamp handling)
- ✅ JWT signature validation (crypto verification)
- ✅ Authorization header format (Bearer prefix, spacing)

**Test File**: `test_password_reset_fuzzing.py`

- ✅ POST /api/auth/reset-password/request - Password reset request
- ✅ POST /api/auth/reset-password/confirm - Password reset confirmation
- ✅ Reset token validation (token format, expiry)
- ✅ Password strength validation (security payloads)
- ✅ Token replay attack detection

### Agent Endpoints (FUZZ-04)

**Test File**: `test_agent_api_fuzzing.py`

- ✅ POST /api/agents/{id}/run - Agent execution
- ✅ GET /api/agents/{id}/status - Agent status polling
- ✅ DELETE /api/agents/{id} - Agent deletion

**Test File**: `test_agent_streaming_fuzzing.py`

- ✅ WebSocket /api/agents/{id}/stream - Agent streaming responses
- ✅ SSE /api/agents/{id}/events - Agent events streaming

### Canvas & Workflow Endpoints (FUZZ-05)

**Test File**: `test_canvas_presentation_fuzzing.py`

- ✅ POST /api/canvas/present - Canvas presentation
- ✅ POST /api/canvas/{id}/submit - Form submission
- ✅ POST /api/canvas/{id}/execute - Canvas command execution

**Test File**: `test_workflow_api_fuzzing.py`

- ✅ POST /api/workflows - Workflow creation
- ✅ PUT /api/workflows/{id} - Workflow update
- ✅ POST /api/workflows/{id}/trigger - Workflow trigger
- ✅ POST /api/workflows/{id}/schedule - Workflow scheduling

**Test File**: `test_skill_installation_fuzzing.py`

- ✅ POST /api/skills/import - Skill import (npm + Python)
- ✅ POST /api/skills/{id}/execute - Skill execution
- ✅ POST /api/skills/{id}/promote - Skill promotion

**Test File**: `test_trigger_execution_fuzzing.py`

- ✅ POST /api/triggers/validate - Trigger validation
- ✅ POST /api/triggers/execute - Trigger execution
- ✅ POST /api/triggers/schedule - Trigger scheduling
- ✅ POST /api/triggers/webhook - Webhook trigger
- ✅ POST /api/triggers/events - Event-based triggers

### Input Space Coverage

**Fuzzed Input Types**:
- Random strings (100-500 chars)
- None/null values
- Empty strings
- Malformed JSON
- Invalid base64
- Unicode normalization issues
- Huge inputs (1000-10000000 chars)

**Security Payloads**:
- SQL injection: `'; DROP TABLE users; --`
- XSS: `<script>alert(1)</script>`
- Null bytes: `\x00`
- Path traversal: `../../etc/passwd`
- Command injection: `; rm -rf /`
- Code injection: `__import__('os').system('rm -rf /')`

**Edge Cases**:
- Negative timestamps
- Huge numbers
- Missing required fields
- Type mismatches (int instead of str)
- Duplicate fields
- Malformed JWT structure
- Cyclical dependencies (workflows)
- Webhook URL validation (javascript:, file://, etc.)

## CI/CD Integration

### Weekly Pipeline

**Workflow**: `.github/workflows/bug-discovery-weekly.yml`

**Schedule**: Sunday 3 AM UTC (cron `0 3 * * 0`)

**Duration**: 1 hour per campaign (5 campaigns = ~5 hours total)

**Jobs**:
1. **api-fuzzing** (90 min timeout)
   - Run fuzzing campaigns: `run_fuzzing_campaigns.py --duration 3600`
   - Upload crash artifacts (90 day retention)
   - Upload corpus artifacts (90 day retention)
   - Aggregate crash reports: `aggregate_crash_reports.py`
   - Upload fuzzing reports (90 day retention)
   - File bugs for crashes: `file_bugs_from_artifacts.py`

2. **bug-discovery** (150 min timeout)
   - Run pytest with markers: `-m "fuzzing or chaos or browser"`
   - Upload test results, screenshots, logs
   - Generate test report
   - File bugs for failures

### FUZZ-07 Compliance

**Requirement**: Fuzzing does NOT run on PR CI pipeline

**Rationale**: Fuzzing is resource-intensive (1-5 hours) and would slow down PR feedback. Fast PR tests (<10 min) enable rapid development, while weekly fuzzing provides comprehensive crash discovery.

**Implementation**:
- ✅ Fuzzing in weekly pipeline only (`bug-discovery-weekly.yml`)
- ✅ NOT in PR pipeline (`ci.yml`, `pr.yml`)
- ✅ Manual trigger support (`workflow_dispatch`)

**Verification**:
```bash
# Verify fuzzing not in PR workflows
grep -L "fuzzing" .github/workflows/*.yml | grep -E "(pr|pull|check)"
```

### Manual Trigger

```bash
# Trigger weekly workflow manually (via GitHub UI)
# https://github.com/owner/repo/actions/workflows/bug-discovery-weekly.yml
# Click "Run workflow" button
```

## Corpus Management

### What is Corpus?

Corpus files contain **interesting inputs** discovered during fuzzing that exercise specific code paths or trigger edge cases.

**Example**:
```
tests/fuzzing/campaigns/corpus/auth/login_sql_injection.input
```

Content (binary):
```
admin' OR '1'='1'--
```

### Corpus Directory Structure

```
tests/fuzzing/campaigns/corpus/
├── auth/              # Authentication corpus
├── agent/             # Agent execution corpus
├── workflow/          # Workflow management corpus
├── canvas/            # Canvas presentation corpus
└── skill/             # Skill installation corpus
```

### Re-seeding Campaigns

Use corpus to speed up future campaigns:

```bash
# Set corpus directory
export FUZZ_CORPUS_DIR="tests/fuzzing/campaigns/corpus/auth"

# Run campaign with corpus
FUZZ_ITERATIONS=10000 pytest tests/fuzzing/test_auth_api_fuzzing.py -v -m fuzzing
```

**Benefits**:
- Faster coverage (corpus inputs explore interesting paths immediately)
- Reproducible crashes (corpus inputs are reproducible test cases)
- Regression testing (corpus grows with discovered bugs)

### Corpus Management Best Practices

1. **Add interesting inputs**: When crashes are discovered, add *.input files to corpus
2. **Organize by endpoint**: Use subdirectories (auth/, agent/, workflow/)
3. **Commit to git**: Corpus is version-controlled with tests
4. **Update regularly**: Add new inputs after each fuzzing campaign

## Crash Analysis

### Crash Artifacts

**Location**: `tests/fuzzing/campaigns/crashes/`

**Format**:
```
tests/fuzzing/campaigns/crashes/POST_api_auth_login_2026-03-24T12-34-56/
├── crash-00001.input  # Binary input that triggered crash
├── crash-00001.log    # Stack trace and error message
├── crash-00002.input
├── crash-00002.log
└── ...
```

### Crash Deduplication

**Tool**: `CrashDeduplicator` in `tests/fuzzing/campaigns/crash_deduplicator.py`

**Method**: SHA256 hash of normalized error signature

```python
# Normalize stack trace (remove line numbers)
normalized_trace = re.sub(r' line \d+', ' line N', stack_trace)

# Generate SHA256 hash
signature_hash = hashlib.sha256(normalized_trace.encode('utf-8')).hexdigest()
```

**Benefits**:
- Groups duplicate crashes (same root cause)
- Reduces bug filing noise
- Identifies high-frequency crashes

### Bug Filing

**Tool**: `BugFilingService` in `tests/bug_discovery/bug_filing_service.py`

**Trigger**: Automatic on crash discovery (via FuzzingOrchestrator)

**Bug Template**:
```markdown
## Fuzzing Crash: POST /api/auth/login

**Test Type**: Fuzzing
**Target Endpoint**: POST /api/auth/login
**Signature Hash**: `abc123...`

### Crash Metadata
- **Crash Input**: `deadbeef...` (hex)
- **Stack Trace**: ```
Traceback (most recent call last):
  File "...", line 123, in test_login_endpoint_fuzzing
    ...
AssertionError: Expected status 200, got 500
```

### Reproduction
```bash
FUZZ_ITERATIONS=1 pytest tests/fuzzing/test_auth_api_fuzzing.py::test_login_endpoint_fuzzing -v
```

### Environment
- **Commit**: abc123...
- **Date**: 2026-03-24T12:34:56Z
- **Campaign ID**: POST_api_auth_login_2026-03-24T12-34-56
```

### Crash Reports

**Tool**: `aggregate_crash_reports.py`

**Usage**:
```bash
python3 tests/fuzzing/scripts/aggregate_crash_reports.py \
  --crash-dirs "tests/fuzzing/campaigns/crashes/*" \
  --output fuzzing-report.md
```

**Report Sections**:
1. **Summary**: Total crashes, unique crashes, affected endpoints
2. **Crashes by Endpoint**: Grouped by API endpoint
3. **Top Crash Signatures**: Sorted by frequency
4. **Bug Filing Status**: Filed, duplicate, skipped
5. **Trend Analysis**: Comparison with previous week

## Best Practices

### 1. Start Small, Scale Up

**Quick verification** (100 iterations, ~10 seconds):
```bash
FUZZ_ITERATIONS=100 pytest tests/fuzzing/test_auth_api_fuzzing.py -v -m fuzzing
```

**Full campaign** (10000 iterations, ~5-10 minutes):
```bash
FUZZ_ITERATIONS=10000 pytest tests/fuzzing/test_auth_api_fuzzing.py -v -m fuzzing
```

**Scale based on crash discovery**:
- If crashes found: Increase iterations to 100000+
- If no crashes: Decrease iterations to 1000 (speed up)

### 2. Use TestClient Pattern

**Correct** (fast, no network overhead):
```python
from fastapi.testclient import TestClient

app.dependency_overrides[get_db] = lambda: db_session
client = TestClient(app)
response = client.post("/api/auth/login", json={...})
assert response.status_code in [200, 400, 401, 422]
```

**Incorrect** (slow, network overhead):
```python
import httpx

response = httpx.post("http://localhost:8000/api/auth/login", json={...})
# Don't do this - network overhead is 10-100x slower
```

**Exception**: Use httpx for streaming endpoints (WebSocket, SSE)

### 3. Reuse Fixtures from e2e_ui

**Correct** (no duplication, 10-100x faster):
```python
from tests.e2e_ui.fixtures.database_fixtures import db_session
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user

def test_login_endpoint_fuzzing(db_session, authenticated_user):
    # db_session: Isolated database session
    # authenticated_user: Pre-created user with valid credentials
    pass
```

**Incorrect** (duplication, slower):
```python
def test_login_endpoint_fuzzing():
    # Don't create fixtures inline - duplication!
    db_session = SessionLocal()
    user = User(email="test@example.com", password="...")
    db_session.add(user)
    db_session.commit()
    # ...
```

### 4. NEVER Fuzz Production URLs

**Correct** (TestClient with database override):
```python
app.dependency_overrides[get_db] = lambda: db_session
client = TestClient(app)
response = client.post("/api/auth/login", json={...})
```

**Incorrect** (production URL, dangerous):
```python
import httpx

response = httpx.post("https://api.atom.ai/api/auth/login", json={...})
# NEVER DO THIS - fuzzing production is dangerous!
```

### 5. Set Reasonable Timeouts

```python
@pytest.mark.timeout(300)  # 5 minutes per test
def test_login_endpoint_fuzzing(db_session, authenticated_user):
    pass
```

**Reasoning**:
- Prevents infinite loops (10000 iterations)
- Allows CI to detect hangs
- 5 minutes is sufficient for 10000 iterations

### 6. Test Status Codes, Not Just Crashes

```python
# Good: Test all expected status codes
assert response.status_code in [200, 400, 401, 409, 422]

# Bad: Only test for success (misses 500 errors)
assert response.status_code == 200
```

**Reasoning**:
- Crashes are not the only bugs
- 500 errors indicate unhandled exceptions
- 422 errors indicate validation issues
- 400/401/409 errors indicate business logic bugs

## Troubleshooting

### Fuzzing Hangs

**Symptom**: Test runs forever, never completes

**Solutions**:
1. Reduce iterations: `FUZZ_ITERATIONS=100`
2. Check timeout config: `@pytest.mark.timeout(300)`
3. Check for infinite loops in endpoint code
4. Use `pytest --timeout` to enforce global timeout

**Example**:
```bash
# Add 10-minute global timeout
pytest --timeout=600 tests/fuzzing/test_auth_api_fuzzing.py -v -m fuzzing
```

### No Crashes Found

**Symptom**: Fuzzing completes with 0 crashes

**Solutions**:
1. Increase iterations: `FUZZ_ITERATIONS=100000`
2. Expand input space (fuzz more fields)
3. Check endpoint code (overly defensive?)
4. Add security payloads (SQLi, XSS, null bytes)
5. Check status code assertions (too permissive?)

**Example**:
```python
# Bad: Too permissive (misses crashes)
assert response.status_code in range(200, 600)

# Good: Explicit status codes
assert response.status_code in [200, 400, 401, 409, 422, 500]
```

### Duplicate Bugs Filed

**Symptom**: Multiple GitHub issues for same crash

**Solutions**:
1. Check deduplication logic: `CrashDeduplicator.deduplicate_crashes()`
2. Verify signature hash is stable (line numbers removed?)
3. Check BugFilingService duplicate detection
4. Review signature normalization regex

**Example**:
```python
# Check normalization logic
normalized_trace = re.sub(r' line \d+', ' line N', stack_trace)
# Should remove line numbers for stable hashing
```

### CI Timeout

**Symptom**: CI workflow fails with timeout

**Solutions**:
1. Reduce campaign duration: `--duration 1800` (30 min)
2. Run fewer endpoints: `--campaign "POST /api/auth/login"`
3. Increase CI timeout: `timeout-minutes: 180`
4. Parallelize campaigns (run multiple jobs)

**Example**:
```yaml
# Reduce timeout
- name: Run fuzzing campaigns
  run: |
    python3 tests/fuzzing/scripts/run_fuzzing_campaigns.py --duration 1800
  timeout-minutes: 45
```

### Fuzzing Skipped in CI

**Symptom**: Tests skip with "atheris not installed"

**Solutions**:
1. Verify atheris in requirements-testing.txt
2. Check CI workflow installs atheris: `pip install atheris`
3. Verify pytest markers: `@pytest.mark.fuzzing`
4. Check test collection: `pytest --collect-only tests/fuzzing/`

**Example**:
```yaml
# Verify CI installs atheris
- name: Install dependencies
  run: |
    pip install atheris  # Fuzzing support
```

## Further Reading

### Research Documentation

- **RESEARCH.md**: `backend/tests/fuzzing/RESEARCH.md` - Fuzzing research and evaluation
- **Phase 239 Plans**: `.planning/phases/239-api-fuzzing-infrastructure/` - Implementation plans

### Related Documentation

- **Bug Discovery Infrastructure**: `docs/testing/BUG_DISCOVERY_INFRASTRUCTURE.md`
- **Property-Based Testing**: `backend/tests/property/README.md`
- **E2E Testing**: `backend/tests/e2e_ui/README.md`

### External Resources

- **Atheris**: https://github.com/google/atheris - Google's coverage-guided fuzzer for Python
- **Fuzzing Book**: https://www.fuzzingbook.org/ - "The Fuzzing Book" by Andreas Zeller
- **OSS-Fuzz**: https://github.com/google/oss-fuzz - Google's continuous fuzzing service

## Summary

API fuzzing with Atheris provides **coverage-guided crash discovery** for FastAPI endpoints, complementing unit tests, integration tests, and property-based tests. Key takeaways:

1. **Start small**: 100 iterations for quick verification, 10000 for full campaign
2. **Use TestClient**: Fast, no network overhead, database override for isolation
3. **Reuse fixtures**: db_session, authenticated_user from e2e_ui (10-100x faster)
4. **NEVER fuzz production**: Use TestClient, not httpx with production URLs
5. **CI/CD integration**: Weekly campaigns (1 hour), NOT in PR pipeline (FUZZ-07)
6. **Corpus management**: Re-seed campaigns with interesting inputs
7. **Crash analysis**: Deduplicate by signature, file bugs automatically

**Fuzzing is not a silver bullet**, but it's a powerful tool for discovering crashes in parsing, validation, and business logic code that human-written tests miss.
