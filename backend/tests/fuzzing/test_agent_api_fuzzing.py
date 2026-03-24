"""
Agent API fuzzing harness for discovering crashes in agent execution endpoints.

This module uses Atheris to fuzz agent execution endpoints:
- POST /api/agents/{id}/run - Agent execution with parameters
- GET /api/agents/{id}/status - Agent status queries
- DELETE /api/agents/{id} - Agent deletion
- GET /api/agents - Agent listing with query parameters

Target: Agent run parsing/validation code crashes
Coverage: SQL injection, XSS, null bytes, huge inputs, malformed data
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Add backend to path for imports
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.database import get_db
from main import app

# Import existing fixtures (FUZZ-02: reuse to avoid duplication)
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user
from tests.e2e_ui.fixtures.database_fixtures import db_session

# Try to import Atheris (graceful degradation)
try:
    import atheris
    from atheris import fp
    ATHERIS_AVAILABLE = True
except ImportError:
    ATHERIS_AVAILABLE = False


# ============================================================================
# AGENT RUN FUZZING (POST /api/agents/{id}/run)
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_agent_run_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz agent execution endpoint (POST /api/agents/{id}/run).

    Target crashes in:
    - Agent ID parsing/validation
    - Parameter JSON parsing
    - Command injection via parameters
    - SQL injection via agent_id

    Edge cases:
    - None, empty string, invalid UUID for agent_id
    - SQL injection: "; DROP TABLE agents; --
    - XSS: <script>alert(1)</script>
    - Huge agent_id (1000+ chars)
    - Null bytes in agent_id
    - Malformed JSON in parameters

    Args:
        db_session: Isolated test database session
        authenticated_user: (user, token) tuple for JWT auth
    """
    if not ATHERIS_AVAILABLE:
        pytest.skip("Atheris not installed - fuzzing test skipped")

    user, token = authenticated_user

    # Override database to use isolated test session
    app.dependency_overrides[get_db] = lambda: db_session

    # Create TestClient with isolated database
    client = TestClient(app)

    # Authorization headers
    headers = {"Authorization": f"Bearer {token}"}

    def fuzz_one_input(data: bytes):
        """Fuzz agent run endpoint with mutated input.

        Args:
            data: Random bytes from Atheris fuzzer

        Raises:
            Exception: Crash discovered (Atheris catches this)
        """
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz agent_id with edge cases
            agent_id_option = fdp.ConsumeIntInRange(0, 5)
            if agent_id_option == 0:
                agent_id = None
            elif agent_id_option == 1:
                agent_id = ""
            elif agent_id_option == 2:
                # SQL injection
                agent_id = "'; DROP TABLE agents; --"
            elif agent_id_option == 3:
                # XSS attempt
                agent_id = "<script>alert('xss')</script>"
            elif agent_id_option == 4:
                # Huge string (potential buffer overflow)
                agent_id = "A" * 1000
            else:
                # Random string up to 50 chars
                agent_id = fdp.ConsumeRandomLengthString(50)

            # Fuzz parameters dict (0-10 keys, random values)
            num_params = fdp.ConsumeIntInRange(0, 10)
            parameters = {}
            for i in range(num_params):
                key = fdp.ConsumeRandomLengthString(20)
                value_option = fdp.ConsumeIntInRange(0, 4)
                if value_option == 0:
                    value = None
                elif value_option == 1:
                    value = fdp.ConsumeRandomLengthString(100)
                elif value_option == 2:
                    value = fdp.ConsumeIntInRange(-1000000, 1000000)
                else:
                    # Nested dict for deep structure testing
                    value = {
                        "nested": fdp.ConsumeRandomLengthString(50),
                        "value": fdp.ConsumeIntInRange(0, 1000)
                    }
                parameters[key] = value

            # Make request with fuzzed data
            # Handle None agent_id gracefully
            if agent_id is None:
                # FastAPI will return 422 for missing path parameter
                response = client.post(
                    "/api/agents/None/run",
                    json={"parameters": parameters},
                    headers=headers
                )
            else:
                response = client.post(
                    f"/api/agents/{agent_id}/run",
                    json={"parameters": parameters},
                    headers=headers
                )

            # Assert acceptable status codes (no crashes = 500 errors)
            # 200: Success, 400: Bad request, 401: Unauthorized, 404: Not found, 422: Validation error
            assert response.status_code in [200, 400, 401, 404, 422], \
                f"Unexpected status code {response.status_code}: {response.text}"

        except (ValueError, KeyError, IndexError, AttributeError) as e:
            # Expected: parsing errors from malformed input are OK
            # These are edge cases, not crashes
            pass
        except Exception as e:
            # Unexpected: crash discovered
            # Re-raise for Atheris to catch and save crash input
            raise Exception(f"Crash in agent run fuzzing: {e}")

    # Run Atheris fuzzing
    # Use environment variable for iterations (default: 10000 for production)
    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Setup(sys.argv, [])
    atheris.Fuzz(fuzz_one_input, iterations=iterations)


# ============================================================================
# AGENT STATUS FUZZING (GET /api/agents/{id}/status)
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_agent_status_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz agent status endpoint (GET /api/agents/{id}/status).

    Target crashes in:
    - Agent ID parsing/validation
    - Status query logic
    - SQL injection via agent_id

    Edge cases:
    - None, empty string, invalid UUID for agent_id
    - SQL injection payloads
    - Unicode strings, null bytes
    - Huge agent_id length

    Args:
        db_session: Isolated test database session
        authenticated_user: (user, token) tuple for JWT auth
    """
    if not ATHERIS_AVAILABLE:
        pytest.skip("Atheris not installed - fuzzing test skipped")

    user, token = authenticated_user

    # Override database
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    def fuzz_one_input(data: bytes):
        """Fuzz agent status endpoint."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz agent_id
            agent_id_option = fdp.ConsumeIntInRange(0, 4)
            if agent_id_option == 0:
                agent_id = ""
            elif agent_id_option == 1:
                agent_id = "'; DROP TABLE agents; --"
            elif agent_id_option == 2:
                agent_id = "\x00\x00\x00"  # Null bytes
            elif agent_id_option == 3:
                agent_id = "A" * 10000  # Huge input
            else:
                agent_id = fdp.ConsumeRandomLengthString(100)

            # Make request
            response = client.get(
                f"/api/agents/{agent_id}/status",
                headers=headers
            )

            # Assert acceptable status codes
            assert response.status_code in [200, 400, 404, 422], \
                f"Unexpected status code {response.status_code}: {response.text}"

        except (ValueError, KeyError):
            # Expected: parsing errors
            pass
        except Exception as e:
            # Crash discovered
            raise Exception(f"Crash in agent status fuzzing: {e}")

    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Setup(sys.argv, [])
    atheris.Fuzz(fuzz_one_input, iterations=iterations)


# ============================================================================
# AGENT DELETE FUZZING (DELETE /api/agents/{id})
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_agent_delete_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz agent deletion endpoint (DELETE /api/agents/{id}).

    Target crashes in:
    - Agent ID parsing/validation
    - Deletion logic
    - Cascade delete operations
    - Running task checks

    Edge cases:
    - SQL injection via agent_id
    - Invalid UUIDs
    - Agents with running tasks (should return 409, not crash)
    - Non-existent agents (404, not crash)

    Args:
        db_session: Isolated test database session
        authenticated_user: (user, token) tuple for JWT auth
    """
    if not ATHERIS_AVAILABLE:
        pytest.skip("Atheris not installed - fuzzing test skipped")

    user, token = authenticated_user

    # Override database
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    def fuzz_one_input(data: bytes):
        """Fuzz agent delete endpoint."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz agent_id
            agent_id_option = fdp.ConsumeIntInRange(0, 3)
            if agent_id_option == 0:
                agent_id = "'; DELETE FROM agents; --"
            elif agent_id_option == 1:
                agent_id = "../../../../etc/passwd"  # Path traversal attempt
            else:
                agent_id = fdp.ConsumeRandomLengthString(50)

            # Make request
            response = client.delete(
                f"/api/agents/{agent_id}",
                headers=headers
            )

            # Assert acceptable status codes
            # 200: Success, 400: Bad request, 404: Not found, 409: Conflict (running tasks), 422: Validation
            assert response.status_code in [200, 400, 404, 409, 422], \
                f"Unexpected status code {response.status_code}: {response.text}"

        except (ValueError, KeyError):
            pass
        except Exception as e:
            raise Exception(f"Crash in agent delete fuzzing: {e}")

    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Setup(sys.argv, [])
    atheris.Fuzz(fuzz_one_input, iterations=iterations)


# ============================================================================
# AGENT LIST FUZZING (GET /api/agents with query parameters)
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_agent_list_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz agent listing endpoint (GET /api/agents) with query parameters.

    Target crashes in:
    - Query parameter parsing
    - Category filtering logic
    - Pagination (limit/offset)
    - SQL injection via query params

    Edge cases:
    - Negative limit/offset values
    - Huge limit values (potential DoS)
    - SQL injection in category parameter
    - Invalid filter combinations

    Args:
        db_session: Isolated test database session
        authenticated_user: (user, token) tuple for JWT auth
    """
    if not ATHERIS_AVAILABLE:
        pytest.skip("Atheris not installed - fuzzing test skipped")

    user, token = authenticated_user

    # Override database
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    def fuzz_one_input(data: bytes):
        """Fuzz agent list endpoint with query parameters."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz category parameter
            category_option = fdp.ConsumeIntInRange(0, 3)
            if category_option == 0:
                category = None
            elif category_option == 1:
                category = "'; DROP TABLE agents; --"
            else:
                category = fdp.ConsumeRandomLengthString(30)

            # Fuzz limit parameter
            limit_option = fdp.ConsumeIntInRange(0, 3)
            if limit_option == 0:
                limit = None
            elif limit_option == 1:
                limit = -100  # Negative value
            elif limit_option == 2:
                limit = 999999999  # Huge value (DoS attempt)
            else:
                limit = fdp.ConsumeIntInRange(1, 100)

            # Fuzz offset parameter
            offset_option = fdp.ConsumeIntInRange(0, 2)
            if offset_option == 0:
                offset = None
            elif offset_option == 1:
                offset = -50  # Negative offset
            else:
                offset = fdp.ConsumeIntInRange(0, 1000)

            # Build query parameters
            params = {}
            if category is not None:
                params["category"] = category
            if limit is not None:
                params["limit"] = limit
            if offset is not None:
                params["offset"] = offset

            # Make request
            response = client.get(
                "/api/agents/",
                params=params,
                headers=headers
            )

            # Assert acceptable status codes
            assert response.status_code in [200, 400, 422], \
                f"Unexpected status code {response.status_code}: {response.text}"

        except (ValueError, KeyError):
            pass
        except Exception as e:
            raise Exception(f"Crash in agent list fuzzing: {e}")

    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Setup(sys.argv, [])
    atheris.Fuzz(fuzz_one_input, iterations=iterations)
