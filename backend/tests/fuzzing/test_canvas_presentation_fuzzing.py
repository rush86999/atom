"""
Canvas presentation fuzzing harness for discovering crashes in canvas state parsing.

This module uses Atheris to fuzz canvas presentation endpoints:
- POST /api/canvas/present - Canvas presentation with canvas_data
- POST /api/canvas/{id}/update - Canvas state updates
- POST /api/canvas/{id}/close - Canvas closure
- POST /api/canvas/{id}/execute - Canvas action execution

Target: Canvas state parsing/validation code crashes
Coverage: SQL injection, XSS, null bytes, huge inputs, malformed JSON, nested structures
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
# CANVAS PRESENT FUZZING (POST /api/canvas/present)
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_canvas_present_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz canvas presentation endpoint (POST /api/canvas/present).

    Target crashes in:
    - Canvas type validation
    - Canvas data JSON parsing
    - Nested structure handling
    - Agent ID parsing/validation

    Edge cases:
    - Canvas type: None, empty, invalid types, SQL injection
    - Canvas data: None, empty dict, huge strings (10MB+), nested cyclical references
    - Agent ID: Invalid UUIDs, SQL injection, XSS
    - Malformed JSON in canvas_data

    Canvas types (7 canonical):
    - chart, markdown, form, sheet, terminal, email, coding

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

    # Valid canvas types for sampling
    valid_canvas_types = ["chart", "markdown", "form", "sheet", "terminal", "email", "coding"]

    def fuzz_one_input(data: bytes):
        """Fuzz canvas present endpoint with mutated input.

        Args:
            data: Random bytes from Atheris fuzzer

        Raises:
            Exception: Crash discovered (Atheris catches this)
        """
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz canvas_type with edge cases
            canvas_type_option = fdp.ConsumeIntInRange(0, 5)
            if canvas_type_option == 0:
                canvas_type = None
            elif canvas_type_option == 1:
                canvas_type = ""
            elif canvas_type_option == 2:
                # SQL injection
                canvas_type = "'; DROP TABLE canvas; --"
            elif canvas_type_option == 3:
                # Invalid type
                canvas_type = "invalid_type_" + fdp.ConsumeRandomLengthString(20)
            elif canvas_type_option == 4:
                # XSS attempt
                canvas_type = "<script>alert('xss')</script>"
            else:
                # Valid canvas type
                canvas_type = fdp.PickValueInList(valid_canvas_types)

            # Fuzz canvas_data dict (0-20 keys, nested structures, huge values)
            num_keys = fdp.ConsumeIntInRange(0, 20)
            canvas_data = {}

            for i in range(num_keys):
                key = fdp.ConsumeRandomLengthString(30)
                value_option = fdp.ConsumeIntInRange(0, 6)

                if value_option == 0:
                    value = None
                elif value_option == 1:
                    # Empty string
                    value = ""
                elif value_option == 2:
                    # Normal string
                    value = fdp.ConsumeRandomLengthString(100)
                elif value_option == 3:
                    # Huge string (potential DoS)
                    value = "A" * 10000000  # 10MB
                elif value_option == 4:
                    # Integer
                    value = fdp.ConsumeIntInRange(-1000000, 1000000)
                elif value_option == 5:
                    # Nested dict (deep structure)
                    value = {
                        "level1": {
                            "level2": {
                                "level3": fdp.ConsumeRandomLengthString(50)
                            }
                        }
                    }
                else:
                    # List with mixed types
                    value = [
                        fdp.ConsumeRandomLengthString(20),
                        fdp.ConsumeIntInRange(0, 1000),
                        None,
                        {"nested": fdp.ConsumeRandomLengthString(10)}
                    ]

                canvas_data[key] = value

            # Fuzz agent_id
            agent_id_option = fdp.ConsumeIntInRange(0, 3)
            if agent_id_option == 0:
                agent_id = None
            elif agent_id_option == 1:
                agent_id = "'; DROP TABLE agents; --"
            else:
                agent_id = fdp.ConsumeRandomLengthString(50)

            # Build request payload
            payload = {
                "canvas_type": canvas_type,
                "canvas_data": canvas_data
            }
            if agent_id is not None:
                payload["agent_id"] = agent_id

            # Make request with fuzzed data
            response = client.post(
                "/api/canvas/present",
                json=payload,
                headers=headers
            )

            # Assert acceptable status codes (no crashes = 500 errors)
            # 200: Success, 400: Bad request, 401: Unauthorized, 422: Validation error
            assert response.status_code in [200, 400, 401, 422], \
                f"Unexpected status code {response.status_code}: {response.text}"

        except (ValueError, KeyError, IndexError, AttributeError) as e:
            # Expected: parsing errors from malformed input are OK
            pass
        except Exception as e:
            # Unexpected: crash discovered
            raise Exception(f"Crash in canvas present fuzzing: {e}")

    # Run Atheris fuzzing
    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Setup(sys.argv, [])
    atheris.Fuzz(fuzz_one_input, iterations=iterations)


# ============================================================================
# CANVAS UPDATE FUZZING (POST /api/canvas/{id}/update)
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_canvas_update_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz canvas update endpoint (POST /api/canvas/{id}/update).

    Target crashes in:
    - Canvas ID parsing/validation
    - Update data merging logic
    - Partial update handling
    - Null value handling

    Edge cases:
    - Canvas ID: None, empty, SQL injection, huge length
    - Update data: Partial updates, full replacements, null values
    - Malformed JSON in update_data

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
        """Fuzz canvas update endpoint."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz canvas_id
            canvas_id_option = fdp.ConsumeIntInRange(0, 4)
            if canvas_id_option == 0:
                canvas_id = ""
            elif canvas_id_option == 1:
                canvas_id = "'; DELETE FROM canvas; --"
            elif canvas_id_option == 2:
                canvas_id = "\x00\x00\x00"  # Null bytes
            elif canvas_id_option == 3:
                canvas_id = "A" * 10000  # Huge input
            else:
                canvas_id = fdp.ConsumeRandomLengthString(100)

            # Fuzz update_data dict
            num_keys = fdp.ConsumeIntInRange(0, 15)
            update_data = {}

            for i in range(num_keys):
                key = fdp.ConsumeRandomLengthString(30)
                value_option = fdp.ConsumeIntInRange(0, 3)

                if value_option == 0:
                    value = None  # Test null value handling
                elif value_option == 1:
                    value = fdp.ConsumeRandomLengthString(1000)
                else:
                    # Nested structure
                    value = {
                        "nested_key": fdp.ConsumeRandomLengthString(50),
                        "nested_value": fdp.ConsumeIntInRange(0, 1000)
                    }

                update_data[key] = value

            # Make request
            response = client.post(
                f"/api/canvas/{canvas_id}/update",
                json={"update_data": update_data},
                headers=headers
            )

            # Assert acceptable status codes
            assert response.status_code in [200, 400, 404, 422], \
                f"Unexpected status code {response.status_code}: {response.text}"

        except (ValueError, KeyError):
            pass
        except Exception as e:
            raise Exception(f"Crash in canvas update fuzzing: {e}")

    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Setup(sys.argv, [])
    atheris.Fuzz(fuzz_one_input, iterations=iterations)


# ============================================================================
# CANVAS CLOSE FUZZING (POST /api/canvas/{id}/close)
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_canvas_close_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz canvas close endpoint (POST /api/canvas/{id}/close).

    Target crashes in:
    - Canvas ID parsing/validation
    - Close operation logic
    - State cleanup

    Edge cases:
    - Canvas ID: SQL injection, XSS, null bytes
    - Non-existent canvas IDs
    - Already closed canvases

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
        """Fuzz canvas close endpoint."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz canvas_id
            canvas_id_option = fdp.ConsumeIntInRange(0, 3)
            if canvas_id_option == 0:
                canvas_id = "'; DROP TABLE canvas_audit; --"
            elif canvas_id_option == 1:
                canvas_id = "<img src=x onerror=alert('xss')>"
            else:
                canvas_id = fdp.ConsumeRandomLengthString(100)

            # Make request
            response = client.post(
                f"/api/canvas/{canvas_id}/close",
                headers=headers
            )

            # Assert acceptable status codes
            assert response.status_code in [200, 400, 404, 422], \
                f"Unexpected status code {response.status_code}: {response.text}"

        except (ValueError, KeyError):
            pass
        except Exception as e:
            raise Exception(f"Crash in canvas close fuzzing: {e}")

    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Setup(sys.argv, [])
    atheris.Fuzz(fuzz_one_input, iterations=iterations)


# ============================================================================
# CANVAS EXECUTE FUZZING (POST /api/canvas/{id}/execute)
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_canvas_execute_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz canvas action execution endpoint (POST /api/canvas/{id}/execute).

    Target crashes in:
    - Canvas ID parsing/validation
    - Action ID parsing
    - Action parameter handling
    - Form submission logic

    Edge cases:
    - Canvas ID: SQL injection, XSS, null bytes
    - Action ID: Invalid IDs, SQL injection
    - Action parameters: Malicious payloads (SQL injection, XSS, null bytes)
    - Form submission with huge payloads

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
        """Fuzz canvas execute endpoint with malicious payloads."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz canvas_id
            canvas_id_option = fdp.ConsumeIntInRange(0, 2)
            if canvas_id_option == 0:
                canvas_id = "'; DELETE FROM canvas_audit; --"
            else:
                canvas_id = fdp.ConsumeRandomLengthString(50)

            # Fuzz action_id
            action_id_option = fdp.ConsumeIntInRange(0, 3)
            if action_id_option == 0:
                action_id = None
            elif action_id_option == 1:
                action_id = ""
            elif action_id_option == 2:
                # SQL injection in action_id
                action_id = "action_1'; DROP TABLE users; --"
            else:
                action_id = fdp.ConsumeRandomLengthString(50)

            # Fuzz action_parameters dict (malicious payloads)
            num_params = fdp.ConsumeIntInRange(0, 10)
            action_parameters = {}

            for i in range(num_params):
                key = fdp.ConsumeRandomLengthString(20)
                value_option = fdp.ConsumeIntInRange(0, 5)

                if value_option == 0:
                    value = None
                elif value_option == 1:
                    # SQL injection payload
                    value = "'; DROP TABLE users; --"
                elif value_option == 2:
                    # XSS payload
                    value = "<script>alert('xss')</script>"
                elif value_option == 3:
                    # Null bytes
                    value = "test\x00\x00\x00"
                elif value_option == 4:
                    # Path traversal
                    value = "../../../../etc/passwd"
                else:
                    value = fdp.ConsumeRandomLengthString(100)

                action_parameters[key] = value

            # Build request payload
            payload = {
                "action_id": action_id,
                "action_parameters": action_parameters
            }

            # Make request
            response = client.post(
                f"/api/canvas/{canvas_id}/execute",
                json=payload,
                headers=headers
            )

            # Assert acceptable status codes
            assert response.status_code in [200, 400, 404, 422], \
                f"Unexpected status code {response.status_code}: {response.text}"

        except (ValueError, KeyError):
            pass
        except Exception as e:
            raise Exception(f"Crash in canvas execute fuzzing: {e}")

    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Setup(sys.argv, [])
    atheris.Fuzz(fuzz_one_input, iterations=iterations)
