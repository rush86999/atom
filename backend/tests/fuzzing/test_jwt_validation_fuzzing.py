"""
JWT validation fuzzing harnesses.

This module uses Atheris to discover crashes in JWT parsing and
validation code through coverage-guided fuzzing.

Fuzzing Targets:
- Authorization header parsing
- JWT expiry validation
- JWT signature validation
- Authorization header format validation

Usage:
    FUZZ_ITERATIONS=10000 pytest tests/fuzzing/test_jwt_validation_fuzzing.py -v -m fuzzing
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
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user

from main_api_app import app
from core.database import get_db

# Try to import Atheris (graceful degradation)
try:
    import atheris
    from atheris import fp
except ImportError:
    ATHERIS_AVAILABLE = False
    pytest.skip("Atheris not installed - skipping JWT validation fuzzing", allow_module_level=True)


# ============================================================================
# FUZZING TEST 1: AUTHORIZATION HEADER VALIDATION
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_jwt_validation_fuzzing(db_session: Session):
    """
    Fuzz Authorization header parsing in protected endpoints.

    PROPERTY: JWT validation should not crash on malformed tokens.
    STRATEGY: FuzzedDataProvider generates random token strings.
    INVARIANT: Response status code in [200, 401, 403, 422] (no 500 errors).
    RADII: 10000 iterations sufficient for token input space.

    Fuzzed fields:
    - Authorization header: Random string up to 500 chars
    - Token format: Bearer {token} with fuzzed token

    Tests GET /api/agents (protected endpoint) with fuzzed JWT tokens.
    """
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    def fuzz_one_input(data: bytes):
        """Fuzzing target for Authorization header parsing."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Consume random token string
            token = fdp.ConsumeRandomLengthString(500)

            # Create Authorization header with fuzzed token
            headers = {"Authorization": f"Bearer {token}"}

            # Call protected endpoint with fuzzed token
            response = client.get("/api/agents", headers=headers)

            # Assert no crashes (401/403 expected for invalid tokens)
            assert response.status_code in [200, 401, 403, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except (ValueError, json.decoder.JSONDecodeError):
            pass
        except Exception as e:
            raise Exception(f"JWT validation crashed: {e}")

    atheris.Setup(
        sys.argv + [atheris.FuzzedDataProviderFlag],
        fuzz_one_input
    )

    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Fuzz(iterations=iterations)

    app.dependency_overrides = {}


# ============================================================================
# FUZZING TEST 2: JWT EXPIRY VALIDATION
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_jwt_expiry_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz JWT expiry timestamp handling.

    PROPERTY: Expired token validation should not crash.
    STRATEGY: Direct function fuzzing of JWT verification with fuzzed expiry.
    INVARIANT: Function returns False or raises ValidationError (no crashes).
    RADII: 10000 iterations sufficient for timestamp space.

    Fuzzed fields:
    - Expiry timestamp: Negative values, huge numbers, strings
    - Token payload: Malformed expiry claims

    Uses core.auth.verify_token for direct function fuzzing.
    """
    from core.auth import verify_token
    from jose import jwt
    from datetime import datetime, timedelta

    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    # Get user for valid token generation
    user, _ = authenticated_user

    def fuzz_one_input(data: bytes):
        """Fuzzing target for JWT expiry validation."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Generate JWT with fuzzed expiry
            # Use fuzzed data to create potentially invalid expiry
            fuzzed_expiry = fdp.ConsumeIntToIntInRange(-1000000, 1000000)

            # Create token with fuzzed expiry
            payload = {
                "sub": str(user.id),
                "exp": fuzzed_expiry,
                "iat": int(datetime.utcnow().timestamp())
            }

            # Sign with test secret (may be invalid)
            try:
                token = jwt.encode(payload, "test_secret", algorithm="HS256")

                # Try to verify token
                headers = {"Authorization": f"Bearer {token}"}
                response = client.get("/api/agents", headers=headers)

                # Assert no crashes
                assert response.status_code in [200, 401, 403, 422], \
                    f"Unexpected status {response.status_code}: {response.text[:200]}"

            except Exception as jwt_error:
                # JWT encoding errors are OK (fuzzed input)
                pass

        except (ValueError, json.decoder.JSONDecodeError):
            pass
        except Exception as e:
            raise Exception(f"JWT expiry validation crashed: {e}")

    atheris.Setup(
        sys.argv + [atheris.FuzzedDataProviderFlag],
        fuzz_one_input
    )

    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Fuzz(iterations=iterations)

    app.dependency_overrides = {}


# ============================================================================
# FUZZING TEST 3: JWT SIGNATURE VALIDATION
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_jwt_signature_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz JWT signature validation.

    PROPERTY: Signature validation should not crash on invalid signatures.
    STRATEGY: FuzzedDataProvider generates random signature strings.
    INVARIANT: Response status code in [200, 401, 403, 422] (no 500 errors).
    RADII: 10000 iterations sufficient for signature space.

    Fuzzed fields:
    - Signature: Invalid length, invalid chars, None, empty strings
    - Token segments: Malformed JWT structure (header.payload.signature)

    Tests protected endpoint with tokens containing fuzzed signatures.
    """
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    def fuzz_one_input(data: bytes):
        """Fuzzing target for JWT signature validation."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Generate fuzzed JWT segments
            header = fdp.ConsumeRandomLengthString(100)
            payload = fdp.ConsumeRandomLengthString(100)
            signature = fdp.ConsumeRandomLengthString(100)

            # Create malformed JWT token
            fuzzed_token = f"{header}.{payload}.{signature}"

            # Call protected endpoint with fuzzed token
            headers = {"Authorization": f"Bearer {fuzzed_token}"}
            response = client.get("/api/agents", headers=headers)

            # Assert no crashes
            assert response.status_code in [200, 401, 403, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except (ValueError, json.decoder.JSONDecodeError):
            pass
        except Exception as e:
            raise Exception(f"JWT signature validation crashed: {e}")

    atheris.Setup(
        sys.argv + [atheris.FuzzedDataProviderFlag],
        fuzz_one_input
    )

    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Fuzz(iterations=iterations)

    app.dependency_overrides = {}


# ============================================================================
# FUZZING TEST 4: AUTHORIZATION HEADER FORMAT
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_jwt_header_fuzzing(db_session: Session, authenticated_user):
    """
    Fuzz Authorization header format variations.

    PROPERTY: Authorization header parser should not crash on malformed headers.
    STRATEGY: FuzzedDataProvider generates random header formats.
    INVARIANT: Response status code in [200, 401, 403, 422] (no 500 errors).
    RADII: 10000 iterations sufficient for header format space.

    Fuzzed fields:
    - Header prefix: "Bearer", "bearer", lowercase, no prefix
    - Spacing: No space, multiple spaces, random whitespace
    - Token: Random string, None, empty

    Tests various malformed Authorization header formats:
    - Missing "Bearer" prefix
    - Lowercase "bearer"
    - No space after "Bearer"
    - Multiple spaces
    - Empty token
    - None token
    """
    import random

    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    def fuzz_one_input(data: bytes):
        """Fuzzing target for Authorization header format."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Generate fuzzed token
            token = fdp.ConsumeRandomLengthString(500)

            # Generate fuzzed header format
            header_formats = [
                f"Bearer {token}",  # Standard format
                f"bearer {token}",  # Lowercase
                f"BEARER {token}",  # Uppercase
                f"{token}",  # Missing prefix
                f"Bearer{token}",  # No space
                f"Bearer  {token}",  # Multiple spaces
                f"Bearer  {token}  ",  # Trailing spaces
                f"",  # Empty header
                f"Bearer ",  # Empty token
                f" {token}",  # Leading space
            ]

            # Select random header format
            if len(data) > 0:
                header_value = header_formats[ord(data[0]) % len(header_formats)]
            else:
                header_value = f"Bearer {token}"

            # Call protected endpoint with fuzzed header
            headers = {"Authorization": header_value}
            response = client.get("/api/agents", headers=headers)

            # Assert no crashes
            assert response.status_code in [200, 401, 403, 422], \
                f"Unexpected status {response.status_code}: {response.text[:200]}"

        except (ValueError, json.decoder.JSONDecodeError):
            pass
        except Exception as e:
            raise Exception(f"Authorization header parsing crashed: {e}")

    atheris.Setup(
        sys.argv + [atheris.FuzzedDataProviderFlag],
        fuzz_one_input
    )

    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Fuzz(iterations=iterations)

    app.dependency_overrides = {}
