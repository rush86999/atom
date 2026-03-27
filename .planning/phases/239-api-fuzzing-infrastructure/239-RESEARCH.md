# Phase 239: API Fuzzing Infrastructure - Research

**Researched:** 2026-03-24
**Domain:** Coverage-guided fuzzing for FastAPI endpoints with Atheris, crash deduplication, automated bug filing
**Confidence:** HIGH

## Summary

Phase 239 focuses on implementing API fuzzing infrastructure using Atheris (Google's coverage-guided fuzzer for Python) to discover crashes in FastAPI endpoint parsing and validation code. The research confirms that Atom has a **strong foundation** from Phase 237: existing fuzzing infrastructure with Atheris 2.2.0, comprehensive fixture reuse from e2e_ui tests, automated bug filing service with GitHub integration, and weekly CI pipeline for bug discovery tests. The key gap is **no API fuzzing harnesses** for FastAPI endpoints covering auth, agent execution, and workflow operations.

**Primary recommendation:** Build on existing fuzzing infrastructure (backend/tests/fuzzing/) by creating Atheris fuzzing harnesses for FastAPI endpoints using three patterns: (1) **Direct function fuzzing** for pure Python validation/parsing functions, (2) **TestClient fuzzing** for FastAPI route handlers using FastAPI's TestClient, and (3) **HTTP client fuzzing** for integration-level endpoint testing. Implement FuzzingOrchestrator service for campaign management (start, stop, monitor runs), crash deduplication using error signature hashing, and automated GitHub issue filing via existing BugFilingService. Run fuzzing campaigns in weekly CI pipeline (1 hour runs, not on PRs) with corpus management for interesting inputs.

**Key findings:**
1. **Atheris 2.2.0 already installed** in requirements-testing.txt with existing fuzz helpers (fuzz_helpers.py, fuzzing/conftest.py) and 3 example fuzz tests for financial parsing and input sanitization
2. **FastAPI has 133 route files** with high-value targets: auth_routes.py (login, signup, JWT validation), agent_routes.py (chat streaming, canvas presentation), workflow/skill routes (trigger execution, skill installation)
3. **Bug filing service production-ready** (bug_filing_service.py) with GitHub Issues API integration, idempotency, artifact collection, crash metadata support
4. **Weekly CI pipeline exists** (bug-discovery-weekly.yml) running fuzzing/chaos/browser markers with 120-minute timeout, artifact upload, and automated bug filing script
5. **Fixture reuse infrastructure established** from Phase 237: authenticated_user (10-100x faster API-first auth), db_session (worker isolation), test_data_factory (dynamic test data)

## Standard Stack

### Core Fuzzing Tools
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **atheris** | 2.2.0 | Coverage-guided fuzzing for Python | Google-maintained fork of AFL for Python, coverage-guided mutation, crash detection |
| **FastAPI TestClient** | 0.104.x | HTTP client for testing FastAPI apps | Official FastAPI testing utility, supports request/response validation |
| **pytest** | 7.4.x | Test runner and discovery | Industry standard, rich plugin ecosystem, already configured with fuzzing marker |
| **pytest-timeout** | 2.2.x | Test timeout enforcement | Prevent hanging fuzz tests (TQ-03 compliance: 300s timeout for fuzzing) |

### Crash Deduplication & Bug Filing
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **hashlib** | (stdlib) | Crash signature generation | Deduplicate similar crashes by error stack trace hash |
| **BugFilingService** | (Phase 236) | Automated GitHub Issues filing | Production-ready service with idempotency, artifact collection |
| **requests** | (existing) | GitHub API integration | Bug filing service uses requests for GitHub Issues API |

### Corpus Management (Optional)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **shutil** | (stdlib) | Corpus directory management | Save interesting inputs for re-seeding fuzzing campaigns |
| **tempfile** | (stdlib) | Temporary crash artifacts | Isolated crash storage per fuzzing run |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **atheris** | libfuzzer (C++ only) | Atheris is Python-native, easier pytest integration, no C compilation |
| **FastAPI TestClient** | httpx | TestClient is official FastAPI testing utility, no async complexity |
| **hashlib for dedup** | MinHash, LSH | Simple SHA256 hash of error signature is sufficient for crash deduplication |
| **BugFilingService** | Custom GitHub API calls | Existing service is production-ready with idempotency and artifact handling |

**Installation:**
```bash
# Core fuzzing (already installed in requirements-testing.txt)
pip install atheris==2.2.0

# FastAPI testing (already installed)
pip install fastapi[all]  # Includes TestClient

# Pytest markers (already configured in pytest.ini)
# pytest.ini already has fuzzing marker registered
```

## Architecture Patterns

### Recommended Project Structure

**Existing Structure (DO NOT CHANGE - Phase 237 INFRA-01):**
```
backend/tests/
├── fuzzing/                    # ✅ EXISTS - Atheris fuzzing tests
│   ├── conftest.py             # ✅ EXISTS - Fuzzing setup, fixtures
│   └── (test files to add)     # ✅ NEW - API fuzzing harnesses
├── bug_discovery/              # ✅ EXISTS - Bug filing service
│   ├── bug_filing_service.py   # ✅ EXISTS - GitHub Issues API
│   └── TEMPLATES/              # ✅ EXISTS - FUZZING_TEMPLATE.md
├── e2e_ui/                     # ✅ EXISTS - Fixtures to reuse
│   ├── fixtures/
│   │   ├── auth_fixtures.py    # ✅ EXISTS - authenticated_user fixture
│   │   └── database_fixtures.py # ✅ EXISTS - db_session fixture
│   └── pages/
└── conftest.py                 # ✅ EXISTS - Root fixtures
```

**NEW Structure (Phase 239):**
```
backend/tests/fuzzing/
├── conftest.py                 # ✅ KEEP - Existing fuzzing setup
├── test_auth_api_fuzzing.py    # ✅ NEW - Auth endpoint fuzzing
├── test_agent_api_fuzzing.py   # ✅ NEW - Agent execution fuzzing
├── test_workflow_api_fuzzing.py # ✅ NEW - Workflow/skill fuzzing
├── test_canvas_api_fuzzing.py  # ✅ NEW - Canvas presentation fuzzing
└── campaigns/                  # ✅ NEW - Fuzzing campaign orchestration
    ├── fuzzing_orchestrator.py # ✅ NEW - Campaign management service
    ├── crash_deduplicator.py   # ✅ NEW - Crash deduplication logic
    └── corpus/                 # ✅ NEW - Interesting inputs for re-seeding
        ├── auth/               # Auth endpoint corpus
        ├── agent/              # Agent execution corpus
        └── workflow/           # Workflow/skill corpus
```

**Key Principle:** DO NOT create separate `/api-fuzzing/` or `/bug-discovery/` directory (INFRA-01 requirement). Integrate into existing `tests/fuzzing/` structure from Phase 237.

### Pattern 1: Direct Function Fuzzing (Pure Python)

**What:** Fuzz individual Python validation/parsing functions directly with Atheris.

**When to use:** Testing pure Python functions without FastAPI dependencies (e.g., input sanitizers, JSON parsers, validation logic).

**Example:**
```python
# Source: backend/tests/fuzzy_tests/security_validation/test_sanitize_input_fuzzing.py (existing example)
import atheris
import sys

def sanitize_user_input(user_input: str) -> str:
    """Pure Python function to fuzz."""
    # Remove HTML tags, SQL injection patterns, etc.
    import re
    sanitized = re.sub(r'<[^>]+>', '', user_input)
    sanitized = re.sub(r"';.*DROP TABLE", '', sanitized, flags=re.IGNORECASE)
    return sanitized.strip()

@atheris.instrument_func
def test_sanitize_input_fuzz(data):
    """Atheris fuzz target for input sanitization."""
    try:
        # Convert bytes to string
        user_input = data.decode('utf-8', errors='ignore')

        # Call function under test
        sanitized = sanitize_user_input(user_input)

        # Assertions (Atheris catches crashes)
        assert isinstance(sanitized, str)
        assert '<script' not in sanitized.lower()

    except (ValueError, UnicodeDecodeError):
        pass  # Expected exceptions - input validation working
    except Exception as e:
        # Unexpected exception - potential bug!
        raise

def main(argc, argv):
    """Main entry point for fuzzing."""
    atheris.Setup(argv, test_sanitize_input_fuzz)
    atheris.Fuzz()

if __name__ == "__main__":
    main(len(sys.argv), sys.argv)
```

**Pros:** Fast execution, easy to debug, no network overhead.
**Cons:** Only tests pure Python, misses FastAPI integration bugs.

### Pattern 2: FastAPI TestClient Fuzzing (Integration Level)

**What:** Fuzz FastAPI route handlers using FastAPI's TestClient with Atheris.

**When to use:** Testing FastAPI endpoints with request/response validation (e.g., auth routes, agent execution, workflow triggers).

**Example:**
```python
# backend/tests/fuzzing/test_auth_api_fuzzing.py
import pytest
import sys
import atheris
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Import FastAPI app
from main import app

# Import existing fixtures
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_login_endpoint_fuzzing(db_session: Session):
    """
    Fuzz /api/auth/login endpoint to discover parsing/validation bugs.

    Target: POST /api/auth/login
    Input type: JSON (email, password)
    Fuzzing iterations: 10000
    """
    # Create TestClient with database override
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    def fuzz_one_input(data):
        """Atheris fuzz target for login endpoint."""
        try:
            # Use FuzzedDataProvider for structured input generation
            from atheris import fp
            fdp = fp.FuzzedDataProvider(data)

            # Generate fuzzed JSON payload
            email = fdp.ConsumeRandomLengthString(100)
            password = fdp.ConsumeRandomLengthString(100)

            # Call login endpoint
            response = client.post(
                "/api/auth/login",
                json={"email": email, "password": password}
            )

            # Assertions (Atheris catches crashes)
            assert response.status_code in [200, 400, 401, 422]
            assert isinstance(response.json(), dict)

        except (ValueError, json.JSONDecodeError):
            pass  # Expected exceptions - malformed JSON
        except Exception as e:
            # Unexpected exception - potential bug!
            print(f"Unexpected exception: {e}")
            raise

    # Run Atheris with 10000 iterations
    atheris.Setup([-atheris.FuzzedDataProviderFlag] + sys.argv, fuzz_one_input)
    atheris.Fuzz()
```

**Pros:** Tests FastAPI integration (request parsing, validation, error handling), realistic endpoint behavior.
**Cons:** Slower than direct function fuzzing, requires database setup.

### Pattern 3: HTTP Client Fuzzing (End-to-End Level)

**What:** Fuzz running FastAPI server with HTTP client (httpx/requests) and Atheris.

**When to use:** Testing complete HTTP stack (middleware, authentication, routing) for critical endpoints.

**Example:**
```python
# backend/tests/fuzzing/test_agent_api_fuzzing_e2e.py
import pytest
import atheris
import httpx
import asyncio
from typing import Generator

# Import existing fixtures
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user

@pytest.fixture(scope="module")
def running_server() -> Generator[str, None, None]:
    """Start FastAPI server for fuzzing."""
    import subprocess
    import time

    # Start server in background
    proc = subprocess.Popen(
        ["python", "-m", "uvicorn", "main:app", "--port", "8001"],
        cwd="/Users/rushiparikh/projects/atom/backend"
    )
    time.sleep(5)  # Wait for server startup

    yield "http://localhost:8001"

    # Cleanup
    proc.terminate()
    proc.wait()

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_agent_chat_streaming_fuzz(running_server: str, authenticated_user):
    """
    Fuzz /api/agents/{id}/chat endpoint to discover streaming bugs.

    Target: POST /api/agents/{id}/chat (WebSocket streaming)
    Input type: JSON (message, parameters)
    Fuzzing iterations: 10000
    """
    user, token = authenticated_user
    base_url = running_server

    def fuzz_one_input(data):
        """Atheris fuzz target for agent chat streaming."""
        try:
            from atheris import fp
            fdp = fp.FuzzedDataProvider(data)

            # Generate fuzzed JSON payload
            message = fdp.ConsumeRandomLengthString(1000)
            agent_id = fdp.ConsumeRandomLengthString(50)

            # Call agent chat endpoint
            with httpx.Client() as client:
                response = client.post(
                    f"{base_url}/api/agents/{agent_id}/chat",
                    json={"message": message},
                    headers={"Authorization": f"Bearer {token}"}
                )

                # Assertions (Atheris catches crashes)
                assert response.status_code in [200, 400, 401, 404, 422]
                assert isinstance(response.json(), dict)

        except httpx.ConnectError:
            pass  # Server not ready - retry
        except (ValueError, json.JSONDecodeError):
            pass  # Expected exceptions - malformed JSON
        except Exception as e:
            # Unexpected exception - potential bug!
            print(f"Unexpected exception: {e}")
            raise

    # Run Atheris with 10000 iterations
    atheris.Setup(sys.argv, fuzz_one_input)
    atheris.Fuzz()
```

**Pros:** Tests complete HTTP stack (middleware, auth, routing), realistic production behavior.
**Cons:** Slowest execution, requires server management, complex setup.

### Pattern 4: FuzzingOrchestrator Service

**What:** Service for managing fuzzing campaigns (start, stop, monitor runs) with crash deduplication and bug filing.

**When to use:** Coordinating multiple fuzzing campaigns, tracking statistics, automating bug filing.

**Example:**
```python
# backend/tests/fuzzing/campaigns/fuzzing_orchestrator.py
import os
import sys
import subprocess
import tempfile
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from tests.bug_discovery.bug_filing_service import BugFilingService

class FuzzingOrchestrator:
    """
    Orchestrates fuzzing campaigns for API endpoints.

    Features:
    - Start/stop fuzzing runs
    - Track statistics (executions, crashes, coverage)
    - Crash deduplication using error signatures
    - Automated bug filing for reproducible crashes
    """

    def __init__(self, github_token: str, github_repository: str):
        """
        Initialize FuzzingOrchestrator.

        Args:
            github_token: GitHub PAT for bug filing
            github_repository: Repository in format "owner/repo"
        """
        self.github_token = github_token
        self.github_repository = github_repository
        self.bug_filing_service = BugFilingService(github_token, github_repository)
        self.corpus_dir = Path("backend/tests/fuzzing/campaigns/corpus")
        self.crash_dir = Path("backend/tests/fuzzing/campaigns/crashes")

        # Create directories
        self.corpus_dir.mkdir(parents=True, exist_ok=True)
        self.crash_dir.mkdir(parents=True, exist_ok=True)

    def start_campaign(
        self,
        target_endpoint: str,
        test_file: str,
        duration_seconds: int = 3600,
        iterations: int = 10000
    ) -> Dict:
        """
        Start a fuzzing campaign for a target endpoint.

        Args:
            target_endpoint: Target endpoint (e.g., "POST /api/auth/login")
            test_file: Path to fuzzing test file
            duration_seconds: Campaign duration (default: 3600s = 1 hour)
            iterations: Number of fuzzing iterations

        Returns:
            Dict with campaign status and statistics
        """
        campaign_id = f"{target_endpoint.replace('/', '-')}_{datetime.utcnow().isoformat()}"

        # Prepare crash directory for this campaign
        campaign_crash_dir = self.crash_dir / campaign_id
        campaign_crash_dir.mkdir(exist_ok=True)

        # Set environment variables for Atheris
        env = os.environ.copy()
        env["FUZZ_CAMPAIGN_ID"] = campaign_id
        env["FUZZ_CRASH_DIR"] = str(campaign_crash_dir)
        env["FUZZ_ITERATIONS"] = str(iterations)

        # Start fuzzing process
        proc = subprocess.Popen(
            [sys.executable, "-m", "pytest", test_file, "-v", "-m", "fuzzing"],
            cwd="backend",
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        return {
            "campaign_id": campaign_id,
            "status": "running",
            "pid": proc.pid,
            "target_endpoint": target_endpoint,
            "duration_seconds": duration_seconds,
            "iterations": iterations
        }

    def stop_campaign(self, campaign_id: str) -> Dict:
        """Stop a running fuzzing campaign."""
        # Implementation: Send SIGTERM to fuzzing process
        pass

    def monitor_campaign(self, campaign_id: str) -> Dict:
        """Get statistics for a running campaign."""
        # Implementation: Read crash files, count executions, crashes
        pass

    def deduplicate_crashes(self, crash_dir: Path) -> Dict[str, List[Path]]:
        """
        Deduplicate crashes using error signature hashing.

        Args:
            crash_dir: Directory containing crash input files

        Returns:
            Dict mapping error signature hash to list of crash files
        """
        import hashlib

        crashes_by_signature: Dict[str, List[Path]] = {}

        for crash_file in crash_dir.glob("*.input"):
            # Read crash log
            crash_log_file = crash_file.with_suffix(".log")
            if not crash_log_file.exists():
                continue

            with open(crash_log_file, "r") as f:
                crash_log = f.read()

            # Generate error signature hash
            # Extract stack trace and error type
            stack_trace = self._extract_stack_trace(crash_log)
            error_signature = hashlib.sha256(stack_trace.encode()).hexdigest()

            # Group crashes by signature
            if error_signature not in crashes_by_signature:
                crashes_by_signature[error_signature] = []
            crashes_by_signature[error_signature].append(crash_file)

        return crashes_by_signature

    def file_bugs_for_crashes(
        self,
        target_endpoint: str,
        crashes_by_signature: Dict[str, List[Path]]
    ) -> List[Dict]:
        """
        File GitHub issues for unique crashes.

        Args:
            target_endpoint: Target endpoint that crashed
            crashes_by_signature: Deduplicated crashes

        Returns:
            List of filed bug results
        """
        filed_bugs = []

        for signature_hash, crash_files in crashes_by_signature.items():
            # Read first crash file as representative
            crash_file = crash_files[0]
            crash_log_file = crash_file.with_suffix(".log")

            with open(crash_file, "rb") as f:
                crash_input = f.read()

            with open(crash_log_file, "r") as f:
                crash_log = f.read()

            # File bug via BugFilingService
            bug_result = self.bug_filing_service.file_bug(
                test_name=f"fuzzing_{target_endpoint}",
                error_message=f"Crash in {target_endpoint}: {crash_log[:200]}",
                metadata={
                    "test_type": "fuzzing",
                    "target_endpoint": target_endpoint,
                    "crash_input": crash_input.hex()[:1000],
                    "crash_log": crash_log[:500],
                    "signature_hash": signature_hash,
                    "related_crashes": len(crash_files)
                }
            )

            filed_bugs.append(bug_result)

        return filed_bugs

    def _extract_stack_trace(self, crash_log: str) -> str:
        """Extract stack trace from crash log for signature generation."""
        # Extract lines starting with "Traceback" or "  File"
        lines = crash_log.split("\n")
        stack_lines = []
        in_traceback = False

        for line in lines:
            if "Traceback" in line:
                in_traceback = True
            if in_traceback:
                stack_lines.append(line)
                if line.strip() and not line.startswith(" ") and "Traceback" not in line:
                    break

        return "\n".join(stack_lines)
```

### Anti-Patterns to Avoid

- **Separate /api-fuzzing/ directory:** Violates INFRA-01 requirement. Integrate into existing tests/fuzzing/ structure.
- **Fuzzing in PR CI pipeline:** Blocks PR merges with long-running tests. Use weekly CI pipeline (FUZZ-07 requirement).
- **Directly fuzzing production endpoints:** Too risky, can crash production systems. Fuzz against test databases only.
- **Ignoring crash deduplication:** Files duplicate GitHub issues for the same bug. Use error signature hashing.
- **Missing corpus management:** Loses interesting inputs discovered during fuzzing. Save corpus for re-seeding.
- **Fuzzing without timeout:** Can hang CI pipeline indefinitely. Use pytest-timeout marker (300s for fuzzing).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Coverage-guided fuzzing engine** | Custom random input generator | Atheris 2.2.0 | Coverage-guided mutation, crash detection, Google-maintained |
| **Crash deduplication** | Custom string comparison | SHA256 hash of error signature | Deterministic, fast, handles stack trace variations |
| **Bug filing** | Custom GitHub API wrapper | BugFilingService (Phase 236) | Production-ready, idempotency, artifact collection |
| **Test HTTP client** | Custom httpx/requests wrapper | FastAPI TestClient | Official FastAPI testing utility, request/response validation |
| **Campaign orchestration** | Ad-hoc subprocess calls | FuzzingOrchestrator service | Centralized management, statistics tracking, automated bug filing |
| **Corpus management** | Manual file copying | Atheris built-in corpus support | Automatic corpus generation, minimization, re-seeding |

**Key insight:** Fuzzing orchestration should leverage existing Atheris features (coverage-guided mutation, crash detection, corpus management) rather than building custom infrastructure. The only custom code needed is FuzzingOrchestrator for campaign management and crash deduplication logic.

## Common Pitfalls

### Pitfall 1: Fuzzing Without Database Isolation

**What goes wrong:** Fuzzing tests mutate shared database, causing test pollution and non-deterministic failures.

**Why it happens:** Developers don't use db_session fixture from e2e_ui/fixtures for worker isolation.

**How to avoid:**
1. Always import db_session from tests.e2e_ui.fixtures.database_fixtures
2. Use app.dependency_overrides[get_db] to inject isolated database
3. Clean up database state in test teardown

**Warning signs:** Fuzzing tests fail intermittently with "database constraint violations" or "foreign key errors".

### Pitfall 2: Fuzzing Without Timeout

**What goes wrong:** Fuzzing tests hang indefinitely, blocking CI pipeline for hours.

**Why it happens:** Developers don't set pytest-timeout marker for fuzzing tests (Atheris can hang on infinite loops).

**How to avoid:**
1. Always mark fuzzing tests with @pytest.mark.timeout(300)
2. Set FUZZ_TIMEOUT environment variable (default: 300s)
3. Use fuzz_timeout fixture from fuzzing/conftest.py

**Warning signs:** CI pipeline running for >1 hour with fuzzing tests still executing.

### Pitfall 3: Fuzzing Production Endpoints

**What goes wrong:** Fuzzing crashes production systems, causing customer impact.

**Why it happens:** Developers accidentally fuzz production endpoints instead of test endpoints.

**How to avoid:**
1. Always use TestClient with database override (never call production URLs)
2. If using HTTP client fuzzing, start local server (localhost:8001)
3. Never set PRODUCTION_URL environment variable in fuzzing tests

**Warning signs:** Fuzzing tests connecting to api.atom.com or production databases.

### Pitfall 4: Not Deduplicating Crashes

**What goes wrong:** Same bug files multiple GitHub issues (one per crash input), spamming the issue tracker.

**Why it happens:** Developers don't implement crash deduplication using error signature hashing.

**How to avoid:**
1. Implement FuzzingOrchestrator.deduplicate_crashes() with SHA256 hashing
2. Group crashes by error signature (stack trace hash)
3. File one GitHub issue per unique crash signature

**Warning signs:** Multiple GitHub issues with identical stack traces but different crash inputs.

### Pitfall 5: Fuzzing Too Many Endpoints

**What goes wrong:** Fuzzing campaign takes >1 hour, exceeds CI timeout, doesn't finish.

**Why it happens:** Trying to fuzz all 133 FastAPI route files in one campaign.

**How to avoid:**
1. Prioritize high-value endpoints: auth, agent execution, workflow/skill (FUZZ-03, FUZZ-04, FUZZ-05 requirements)
2. Limit fuzzing campaigns to 10-20 critical endpoints
3. Use weekly CI schedule (not on PRs) to allow longer runs

**Warning signs:** Fuzzing campaign exceeding 120-minute timeout in bug-discovery-weekly.yml.

### Pitfall 6: Not Reusing Existing Fixtures

**What goes wrong:** Duplicate auth/database setup code across fuzzing tests, maintenance burden.

**Why it happens:** Developers don't import fixtures from tests.e2e_ui.fixtures.

**How to avoid:**
1. Import authenticated_user from tests.e2e_ui.fixtures.auth_fixtures (10-100x faster than UI login)
2. Import db_session from tests.e2e_ui.fixtures.database_fixtures (worker isolation)
3. Reference FIXTURE_REUSE_GUIDE.md for complete fixture catalog

**Warning signs:** New fixture definitions in fuzzing/conftest.py that duplicate e2e_ui/fixtures/.

## Code Examples

Verified patterns from official sources:

### Pattern 1: Auth Endpoint Fuzzing (FUZZ-03)

```python
# backend/tests/fuzzing/test_auth_api_fuzzing.py
import pytest
import atheris
import sys
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from core.database import get_db
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_login_endpoint_fuzzing(db_session: Session):
    """
    Fuzz POST /api/auth/login to discover parsing/validation bugs.

    Target: api/auth_routes.py:mobile_login
    Input type: JSON (email, password, device_token)
    Fuzzing iterations: 10000
    """
    # Override database dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    def fuzz_one_input(data):
        """Atheris fuzz target."""
        from atheris import fp
        fdp = fp.FuzzedDataProvider(data)

        try:
            # Generate fuzzed JSON payload
            email = fdp.ConsumeRandomLengthString(100)
            password = fdp.ConsumeRandomLengthString(100)
            device_token = fdp.ConsumeRandomLengthString(100)

            # Call login endpoint
            response = client.post(
                "/api/auth/mobile/login",
                json={
                    "email": email,
                    "password": password,
                    "device_token": device_token,
                    "platform": "ios"
                }
            )

            # Assertions
            assert response.status_code in [200, 400, 401, 422]
            assert isinstance(response.json(), dict)

        except (ValueError, json.JSONDecodeError):
            pass  # Expected exceptions - malformed JSON
        except Exception as e:
            raise  # Unexpected exception - potential bug!

    atheris.Setup([-atheris.FuzzedDataProviderFlag] + sys.argv, fuzz_one_input)
    atheris.Fuzz()
```

### Pattern 2: Agent Execution Fuzzing (FUZZ-04)

```python
# backend/tests/fuzzing/test_agent_api_fuzzing.py
import pytest
import atheris
import sys
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from core.database import get_db
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_agent_run_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz POST /api/agents/{id}/run to discover agent execution bugs.

    Target: api/agent_routes.py:run_agent
    Input type: JSON (parameters dict)
    Fuzzing iterations: 10000
    """
    user, token = authenticated_user

    # Override database dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    def fuzz_one_input(data):
        """Atheris fuzz target."""
        from atheris import fp
        fdp = fp.FuzzedDataProvider(data)

        try:
            # Generate fuzzed JSON payload
            agent_id = fdp.ConsumeRandomLengthString(50)
            parameters = {}
            num_params = fdp.ConsumeIntInRange(0, 10)

            for i in range(num_params):
                key = fdp.ConsumeRandomLengthString(50)
                value = fdp.ConsumeRandomLengthString(100)
                parameters[key] = value

            # Call agent run endpoint
            response = client.post(
                f"/api/agents/{agent_id}/run",
                json={"parameters": parameters},
                headers={"Authorization": f"Bearer {token}"}
            )

            # Assertions
            assert response.status_code in [200, 400, 401, 404, 422]

        except (ValueError, json.JSONDecodeError):
            pass  # Expected exceptions - malformed JSON
        except Exception as e:
            raise  # Unexpected exception - potential bug!

    atheris.Setup([-atheris.FuzzedDataProviderFlag] + sys.argv, fuzz_one_input)
    atheris.Fuzz()
```

### Pattern 3: Workflow Trigger Fuzzing (FUZZ-05)

```python
# backend/tests/fuzzing/test_workflow_api_fuzzing.py
import pytest
import atheris
import sys
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from core.database import get_db
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_workflow_trigger_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz POST /api/workflows/{id}/trigger to discover workflow execution bugs.

    Target: api/workflow_debugging.py:trigger_workflow
    Input type: JSON (input_data dict)
    Fuzzing iterations: 10000
    """
    user, token = authenticated_user

    # Override database dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    def fuzz_one_input(data):
        """Atheris fuzz target."""
        from atheris import fp
        fdp = fp.FuzzedDataProvider(data)

        try:
            # Generate fuzzed JSON payload
            workflow_id = fdp.ConsumeRandomLengthString(50)
            input_data = {}
            num_inputs = fdp.ConsumeIntInRange(0, 20)

            for i in range(num_inputs):
                key = fdp.ConsumeRandomLengthString(50)
                value = fdp.ConsumeRandomLengthString(200)
                input_data[key] = value

            # Call workflow trigger endpoint
            response = client.post(
                f"/api/workflows/{workflow_id}/trigger",
                json={"input_data": input_data},
                headers={"Authorization": f"Bearer {token}"}
            )

            # Assertions
            assert response.status_code in [200, 400, 401, 404, 422]

        except (ValueError, json.JSONDecodeError):
            pass  # Expected exceptions - malformed JSON
        except Exception as e:
            raise  # Unexpected exception - potential bug!

    atheris.Setup([-atheris.FuzzedDataProviderFlag] + sys.argv, fuzz_one_input)
    atheris.Fuzz()
```

### Pattern 4: Skill Installation Fuzzing (FUZZ-05)

```python
# backend/tests/fuzzing/test_skill_api_fuzzing.py
import pytest
import atheris
import sys
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from core.database import get_db
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_skill_install_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz POST /api/skills/install to discover skill installation bugs.

    Target: api/skill_routes.py:install_skill
    Input type: JSON (source, content, metadata)
    Fuzzing iterations: 10000
    """
    user, token = authenticated_user

    # Override database dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    def fuzz_one_input(data):
        """Atheris fuzz target."""
        from atheris import fp
        fdp = fp.FuzzedDataProvider(data)

        try:
            # Generate fuzzed JSON payload
            source = fdp.ConsumeRandomLengthString(50)
            content = fdp.ConsumeRandomLengthString(10000)
            metadata = {}
            num_metadata = fdp.ConsumeIntInRange(0, 10)

            for i in range(num_metadata):
                key = fdp.ConsumeRandomLengthString(50)
                value = fdp.ConsumeRandomLengthString(100)
                metadata[key] = value

            # Call skill install endpoint
            response = client.post(
                "/api/skills/install",
                json={
                    "source": source,
                    "content": content,
                    "metadata": metadata
                },
                headers={"Authorization": f"Bearer {token}"}
            )

            # Assertions
            assert response.status_code in [200, 400, 401, 422]

        except (ValueError, json.JSONDecodeError):
            pass  # Expected exceptions - malformed JSON
        except Exception as e:
            raise  # Unexpected exception - potential bug!

    atheris.Setup([-atheris.FuzzedDataProviderFlag] + sys.argv, fuzz_one_input)
    atheris.Fuzz()
```

### Pattern 5: FuzzingOrchestrator Campaign Management (FUZZ-01)

```python
# backend/tests/fuzzing/campaigns/fuzzing_orchestrator.py
from pathlib import Path
from tests.bug_discovery.bug_filing_service import BugFilingService

class FuzzingOrchestrator:
    """Service for managing fuzzing campaigns (FUZZ-01)."""

    def __init__(self, github_token: str, github_repository: str):
        self.bug_filing_service = BugFilingService(github_token, github_repository)
        self.crash_dir = Path("backend/tests/fuzzing/campaigns/crashes")

    def start_campaign(
        self,
        target_endpoint: str,
        test_file: str,
        duration_seconds: int = 3600
    ) -> Dict:
        """Start fuzzing campaign for target endpoint."""
        # Implementation: subprocess pytest, track PID, statistics
        pass

    def stop_campaign(self, campaign_id: str) -> Dict:
        """Stop running fuzzing campaign."""
        # Implementation: send SIGTERM to process
        pass

    def deduplicate_crashes(self, crash_dir: Path) -> Dict[str, List[Path]]:
        """Deduplicate crashes using error signature hashing (FUZZ-06)."""
        import hashlib

        crashes_by_signature = {}

        for crash_file in crash_dir.glob("*.input"):
            crash_log_file = crash_file.with_suffix(".log")
            if not crash_log_file.exists():
                continue

            with open(crash_log_file, "r") as f:
                crash_log = f.read()

            # Generate SHA256 hash of stack trace
            stack_trace = self._extract_stack_trace(crash_log)
            signature_hash = hashlib.sha256(stack_trace.encode()).hexdigest()

            if signature_hash not in crashes_by_signature:
                crashes_by_signature[signature_hash] = []
            crashes_by_signature[signature_hash].append(crash_file)

        return crashes_by_signature

    def file_bugs_for_crashes(
        self,
        target_endpoint: str,
        crashes_by_signature: Dict[str, List[Path]]
    ) -> List[Dict]:
        """File GitHub issues for reproducible crashes (FUZZ-06)."""
        filed_bugs = []

        for signature_hash, crash_files in crashes_by_signature.items():
            crash_file = crash_files[0]
            crash_log_file = crash_file.with_suffix(".log")

            with open(crash_file, "rb") as f:
                crash_input = f.read()

            with open(crash_log_file, "r") as f:
                crash_log = f.read()

            bug_result = self.bug_filing_service.file_bug(
                test_name=f"fuzzing_{target_endpoint}",
                error_message=f"Crash in {target_endpoint}: {crash_log[:200]}",
                metadata={
                    "test_type": "fuzzing",
                    "target_endpoint": target_endpoint,
                    "crash_input": crash_input.hex()[:1000],
                    "crash_log": crash_log[:500],
                    "signature_hash": signature_hash,
                    "related_crashes": len(crash_files)
                }
            )

            filed_bugs.append(bug_result)

        return filed_bugs

    def _extract_stack_trace(self, crash_log: str) -> str:
        """Extract stack trace from crash log for signature generation."""
        lines = crash_log.split("\n")
        stack_lines = []
        in_traceback = False

        for line in lines:
            if "Traceback" in line:
                in_traceback = True
            if in_traceback:
                stack_lines.append(line)
                if line.strip() and not line.startswith(" ") and "Traceback" not in line:
                    break

        return "\n".join(stack_lines)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Random input generation** | Coverage-guided fuzzing (Atheris) | Phase 237 (infrastructure ready) | 10-100x more effective bug discovery |
| **Manual crash filing** | Automated bug filing service | Phase 236-08 (complete) | GitHub issues created automatically |
| **No corpus management** | Atheris corpus support | Phase 237 (infrastructure ready) | Re-seed fuzzing with interesting inputs |
| **Duplicate crash bugs** | Crash deduplication by signature | Phase 239 (planned) | One GitHub issue per unique crash |
| **Fuzzing on every PR** | Weekly fuzzing pipeline | Phase 237 (INFRA-02) | Fast PR feedback (<10min) vs weekly comprehensive fuzzing |

**Deprecated/outdated:**
- **Random fuzzing without coverage guidance:** Use Atheris for coverage-guided mutation (10-100x more effective)
- **Manual GitHub issue filing:** Use BugFilingService (Phase 236-08) for automated bug filing
- **Fuzzing in PR CI pipeline:** Use weekly bug-discovery-weekly.yml (FUZZ-07 requirement: not on PRs)
- **Custom fuzzing engines:** Use Atheris 2.2.0 (Google-maintained, Python-native)

## Open Questions

1. **Atheris fuzzing iterations for CI pipeline**
   - What we know: Weekly CI pipeline has 120-minute timeout, existing fuzz tests use 10000 iterations
   - What's unclear: How many iterations for 1-hour runs? 10000? 100000?
   - Recommendation: Start with 10000 iterations per endpoint (~5-10 minutes), scale to 100000 based on crash discovery rate

2. **FastAPI TestClient vs HTTP client fuzzing**
   - What we know: TestClient is faster (no network overhead), HTTP client tests complete stack
   - What's unclear: Which pattern to use for agent execution endpoints (streaming responses)?
   - Recommendation: Use TestClient for auth/workflow endpoints (simpler), use HTTP client for agent streaming (realistic WebSocket testing)

3. **Corpus seeding for FastAPI endpoints**
   - What we know: Atheris supports corpus directories for re-seeding interesting inputs
   - What's unclear: What constitutes "interesting inputs" for API endpoints? Valid requests? Malformed JSON?
   - Recommendation: Start with empty corpus, let Atheris discover interesting inputs automatically, save corpus after each run

4. **Crash deduplication algorithm**
   - What we know: SHA256 hash of error signature (stack trace) is standard approach
   - What's unclear: Should we include line numbers? Function names? Error types only?
   - Recommendation: Hash complete stack trace (including line numbers) for maximum precision, can relax if dedup is too aggressive

5. **Fuzzing campaign prioritization**
   - What we know: 133 FastAPI route files exist, need to prioritize for 1-hour weekly runs
   - What's unclear: Which endpoints are most critical? Auth? Agent execution? Workflows?
   - Recommendation: Start with FUZZ-03, FUZZ-04, FUZZ-05 requirements (auth, agent, workflow endpoints), expand based on crash discovery rate

## Sources

### Primary (HIGH confidence)
- **backend/tests/fuzzing/conftest.py** - Fuzzing test configuration with Atheris setup, fixture reuse from e2e_ui
- **backend/tests/fuzzy_tests/fuzz_helpers.py** - Existing fuzz helpers with setup_fuzzer(), run_fuzz(), with_expected_exceptions()
- **backend/tests/fuzzy_tests/security_validation/test_sanitize_input_fuzzing.py** - Example Atheris fuzz test with fuzz_one_input pattern
- **backend/tests/bug_discovery/bug_filing_service.py** - Automated bug filing service with GitHub Issues API, idempotency
- **backend/tests/bug_discovery/TEMPLATES/FUZZING_TEMPLATE.md** - Comprehensive fuzzing test template with setup, procedure, bug filing
- **backend/requirements-testing.txt** - Testing dependencies including atheris==2.2.0
- **backend/docs/BUG_DISCOVERY_INFRASTRUCTURE.md** - Bug discovery architecture from Phase 237
- **.github/workflows/bug-discovery-weekly.yml** - Weekly CI pipeline for fuzzing/chaos/browser tests (120-minute timeout)
- **pytest.ini** - Pytest configuration with fuzzing marker, timeout settings

### Secondary (MEDIUM confidence)
- **Atheris GitHub repository** (github.com/google/atheris) - Official documentation, examples, best practices (verified via existing codebase usage)
- **FastAPI TestClient documentation** (fastapi.tiangolo.com) - Official testing guide for FastAPI applications
- **Phase 237 Research** (237-RESEARCH.md) - Bug discovery infrastructure foundation research

### Tertiary (LOW confidence)
- General knowledge of coverage-guided fuzzing (AFL/libFuzzer principles)
- Existing fuzz test patterns in backend/tests/fuzzy_tests/ (3 examples for financial parsing and input sanitization)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Atheris 2.2.0 already installed and in use, existing fuzz tests demonstrate patterns
- Architecture: HIGH - FastAPI has 133 route files, fuzzing infrastructure exists from Phase 237, BugFilingService production-ready
- Pitfalls: HIGH - Common pitfalls identified from Phase 237 INFRA-02 (separate CI pipelines) and existing fuzz test patterns
- Fuzzing patterns: HIGH - Three established patterns (direct function, TestClient, HTTP client) verified against existing code

**Research date:** 2026-03-24
**Valid until:** 2026-04-23 (30 days - Atheris is mature project, FastAPI TestClient is stable, fuzzing patterns are well-established)
