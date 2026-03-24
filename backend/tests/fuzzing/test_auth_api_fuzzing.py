"""
Authentication endpoint fuzzing harnesses.

This module uses Atheris to discover crashes in authentication endpoint
parsing and validation code through coverage-guided fuzzing.

Fuzzing Targets:
- POST /api/auth/login - Login endpoint
- POST /api/auth/signup - Signup endpoint
- POST /api/auth/mobile/login - Mobile login endpoint

Usage:
    FUZZ_ITERATIONS=10000 pytest tests/fuzzing/test_auth_api_fuzzing.py -v -m fuzzing
"""

import os
import sys
import json
import pytest
from typing import Dict, Any

# Add backend to path
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Import fixtures and app
from tests.fuzzing.conftest import ATHERIS_AVAILABLE
from tests.e2e_ui.fixtures.database_fixtures import db_session
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user, test_user

from main_api_app import app
from core.database import get_db

# Try to import Atheris (graceful degradation)
try:
    import atheris
    from atheris import fp
except ImportError:
    ATHERIS_AVAILABLE = False
    pytest.skip("Atheris not installed - skipping auth endpoint fuzzing", allow_module_level=True)


# ============================================================================
# FUZZING TEST 1: LOGIN ENDPOINT
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_login_endpoint_fuzzing(db_session: Session):
    """
    Fuzz POST /api/auth/login endpoint.

    PROPERTY: Login endpoint should not crash on malformed input.
    STRATEGY: FuzzedDataProvider generates random email/password combinations.
    INVARIANT: Response status code in [200, 400, 401, 422] (no 500 errors).
    RADII: 10000 iterations sufficient for login input space (email + password).

    Fuzzed fields:
    - email: Random string up to 100 chars
    - password: Random string up to 100 chars
    """
    # Override database dependency for test isolation
    app.dependency_overrides[get_db] = lambda: db_session

    # Create TestClient for fuzzing
    client = TestClient(app)

    def fuzz_one_input(data: bytes):
        """Fuzzing target for login endpoint."""
        try:
            # Generate fuzzed payload using FuzzedDataProvider
            fdp = fp.FuzzedDataProvider(data)

            # Consume random strings for email and password
            email = fdp.ConsumeRandomLengthString(100)
            password = fdp.ConsumeRandomLengthString(100)

            # Call login endpoint with fuzzed data
            response = client.post(
                "/api/auth/login",
                json={"email": email, "password": password}
            )

            # Assert no crashes (status in expected range)
            assert response.status_code in [200, 400, 401, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except (ValueError, json.decoder.JSONDecodeError) as e:
            # Expected errors (malformed JSON)
            pass
        except Exception as e:
            # Potential bug - re-raise for Atheris to capture
            raise Exception(f"Login endpoint crashed: {e}")

    # Setup Atheris with libFuzzer
    atheris.Setup(
        sys.argv + [atheris.FuzzedDataProviderFlag],
        fuzz_one_input
    )

    # Run fuzzing (default 10000 iterations or FUZZ_ITERATIONS env var)
    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Fuzz(iterations=iterations)

    # Clean up dependency override
    app.dependency_overrides = {}


# ============================================================================
# FUZZING TEST 2: SIGNUP ENDPOINT
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_signup_endpoint_fuzzing(db_session: Session):
    """
    Fuzz POST /api/auth/signup endpoint.

    PROPERTY: Signup endpoint should not crash on malformed input.
    STRATEGY: FuzzedDataProvider generates random signup payloads.
    INVARIANT: Response status code in [200, 400, 409, 422] (no 500 errors).
    RADII: 10000 iterations sufficient for signup input space (email + password + confirm + name).

    Fuzzed fields:
    - email: Random string up to 100 chars
    - password: Random string up to 100 chars
    - confirm_password: Random string up to 100 chars
    - name: Random string up to 100 chars
    """
    import json

    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    def fuzz_one_input(data: bytes):
        """Fuzzing target for signup endpoint."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Consume random strings for signup fields
            email = fdp.ConsumeRandomLengthString(100)
            password = fdp.ConsumeRandomLengthString(100)
            confirm_password = fdp.ConsumeRandomLengthString(100)
            name = fdp.ConsumeRandomLengthString(100)

            # Call signup endpoint with fuzzed data
            response = client.post(
                "/api/auth/signup",
                json={
                    "email": email,
                    "password": password,
                    "confirm_password": confirm_password,
                    "name": name
                }
            )

            # Assert no crashes
            assert response.status_code in [200, 400, 409, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except (ValueError, json.decoder.JSONDecodeError):
            pass
        except Exception as e:
            raise Exception(f"Signup endpoint crashed: {e}")

    atheris.Setup(
        sys.argv + [atheris.FuzzedDataProviderFlag],
        fuzz_one_input
    )

    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Fuzz(iterations=iterations)

    app.dependency_overrides = {}


# ============================================================================
# FUZZING TEST 3: MOBILE LOGIN ENDPOINT
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_mobile_login_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz POST /api/auth/mobile/login endpoint.

    PROPERTY: Mobile login endpoint should not crash on malformed device tokens.
    STRATEGY: FuzzedDataProvider generates random device tokens and platforms.
    INVARIANT: Response status code in [200, 400, 401, 422] (no 500 errors).
    RADII: 10000 iterations sufficient for device token/platform space.

    Fuzzed fields:
    - device_token: Random string up to 100 chars
    - platform: Random string up to 20 chars (ios, android, or random)
    - device_info: Random dictionary with nested fuzzed data

    Uses authenticated_user fixture for valid credentials baseline.
    """
    import json

    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    # Get valid credentials from authenticated_user
    user, _ = authenticated_user
    valid_email = user.email

    def fuzz_one_input(data: bytes):
        """Fuzzing target for mobile login endpoint."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Consume random strings for device fields
            device_token = fdp.ConsumeRandomLengthString(100)
            platform = fdp.ConsumeRandomLengthString(20)

            # Generate fuzzed device_info dict
            device_info: Dict[str, Any] = {}
            if fdp.ConsumeBool():
                device_info["device_id"] = fdp.ConsumeRandomLengthString(50)
            if fdp.ConsumeBool():
                device_info["app_version"] = fdp.ConsumeRandomLengthString(20)
            if fdp.ConsumeBool():
                device_info["os_version"] = fdp.ConsumeRandomLengthString(20)

            # Call mobile login endpoint with fuzzed device data
            response = client.post(
                "/api/auth/mobile/login",
                json={
                    "email": valid_email,
                    "password": "TestPassword123!",  # Valid password from test_user fixture
                    "device_token": device_token,
                    "platform": platform,
                    "device_info": device_info
                }
            )

            # Assert no crashes
            assert response.status_code in [200, 400, 401, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except (ValueError, json.decoder.JSONDecodeError):
            pass
        except Exception as e:
            raise Exception(f"Mobile login endpoint crashed: {e}")

    atheris.Setup(
        sys.argv + [atheris.FuzzedDataProviderFlag],
        fuzz_one_input
    )

    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Fuzz(iterations=iterations)

    app.dependency_overrides = {}
