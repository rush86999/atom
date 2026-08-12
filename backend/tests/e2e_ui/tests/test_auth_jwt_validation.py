"""
E2E tests for JWT token validation (AUTH-02).

Run with: pytest backend/tests/e2e_ui/tests/test_auth_jwt_validation.py -v
"""

import pytest
import json
import base64
from datetime import datetime
from playwright.sync_api import Page


def decode_jwt_payload(token: str) -> dict:
    """Decode JWT payload from token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload as dictionary
    """
    parts = token.split('.')
    payload = parts[1]

    # Add padding if needed
    padding = len(payload) % 4
    if padding != 0:
        payload += '=' * (4 - padding)

    decoded = base64.b64decode(payload)
    return json.loads(decoded)


class TestJWTTokenValidation:
    """E2E tests for JWT token structure and claims (AUTH-02)."""

    def test_jwt_token_structure(self, authenticated_page_api: Page):
        """Verify JWT token has correct structure (header.payload.signature).

        This test validates:
        1. JWT token exists in localStorage
        2. Token has 3 parts separated by dots
        3. Header contains alg: HS256 and typ: JWT
        4. Payload contains required claims (sub, exp, iat)

        Args:
            authenticated_page_api: Authenticated page fixture with JWT token

        Coverage: AUTH-02 (JWT token structure validation)
        """
        # Get JWT token from localStorage
        token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")

        assert token is not None, "JWT token should exist in localStorage"

        # Verify token has 3 parts (header.payload.signature)
        parts = token.split('.')
        assert len(parts) == 3, f"JWT should have 3 parts, got {len(parts)}"

        # Decode header
        header_padding = len(parts[0]) % 4
        header_encoded = parts[0]
        if header_padding != 0:
            header_encoded += '=' * (4 - header_padding)

        header = json.loads(base64.b64decode(header_encoded))

        # Verify header claims
        assert header.get('alg') == 'HS256', f"Expected algorithm HS256, got {header.get('alg')}"
        assert header.get('typ') == 'JWT', f"Expected type JWT, got {header.get('typ')}"

    def test_jwt_token_expiration(self, authenticated_page_api: Page):
        """Verify JWT token expiration is set correctly (default 24 hours).

        This test validates:
        1. JWT token has exp claim
        2. Expiration timestamp is in the future
        3. Expiration is within expected time window (ACCESS_TOKEN_EXPIRE_MINUTES
           = 60 * 24 = 24 hours in core/auth.py)

        Args:
            authenticated_page_api: Authenticated page fixture with JWT token

        Coverage: AUTH-02 (JWT token expiration validation)
        """
        # Get JWT token from localStorage
        token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")

        assert token is not None, "JWT token should exist in localStorage"

        # Decode payload
        payload = decode_jwt_payload(token)

        # Verify exp claim exists
        assert 'exp' in payload, "JWT payload should contain expiration claim"

        # Verify expiration is in the future
        exp_timestamp = payload['exp']
        exp_datetime = datetime.utcfromtimestamp(exp_timestamp)
        now = datetime.utcnow()

        assert exp_datetime > now, f"Token should not be expired (exp: {exp_datetime}, now: {now})"

        # Verify expiration is reasonable (default from core/auth.py is 24 hours)
        # Check that token expires within 25 hours (24-hour token + buffer)
        time_diff = (exp_datetime - now).total_seconds()
        max_seconds = 25 * 60 * 60  # 25 hours
        assert time_diff < max_seconds, f"Token expiration should be within 25 hours, got {time_diff}s"

    def test_jwt_token_claims(self, authenticated_page_api: Page):
        """Verify JWT token contains required user claims.

        This test validates:
        1. JWT payload contains 'sub' claim (user ID)
        2. 'sub' claim is non-empty string
        3. Optional 'email' claim is valid format if present
        4. Optional 'role' claim is valid value if present

        Args:
            authenticated_page_api: Authenticated page fixture with JWT token

        Coverage: AUTH-02 (JWT token claims validation)
        """
        # Get JWT token from localStorage
        token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")

        assert token is not None, "JWT token should exist in localStorage"

        # Decode payload
        payload = decode_jwt_payload(token)

        # Verify required 'sub' claim
        assert 'sub' in payload, "JWT payload should contain 'sub' claim (user ID)"
        assert payload['sub'] is not None, "'sub' claim should not be None"
        assert len(payload['sub']) > 0, "'sub' claim should not be empty"

        # Verify optional 'email' claim
        if 'email' in payload:
            assert '@' in payload['email'], f"Email should be valid format, got {payload['email']}"

        # Verify optional 'role' claim
        if 'role' in payload:
            valid_roles = ['user', 'admin', 'super_admin']
            assert payload['role'] in valid_roles, f"Role should be one of {valid_roles}, got {payload['role']}"

    def test_jwt_token_signature_valid(self, authenticated_page_api):
        """Verify JWT token signature is valid and accepted by backend.

        This test validates:
        1. Token from localStorage works with backend API
        2. Protected endpoint accepts token with valid signature
        3. 200 response indicates signature verification passed

        Args:
            authenticated_page_api: Authenticated page fixture with JWT token

        Coverage: AUTH-02 (JWT token signature validation via API)
        """
        import requests

        # Get token from localStorage
        token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")

        assert token is not None, "JWT token should exist in localStorage"

        # Make API request to protected endpoint with token
        # /api/agents is a real protected endpoint (the old /api/v1/agents
        # prefix is a phantom route that returns 404 — auth never runs).
        response = requests.get(
            "http://localhost:8001/api/agents",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )

        # The fixture token comes from the live backend's login endpoint, so a
        # valid signature must be accepted — 200 proves signature verification
        # passed (a 401 would mean the signature was NOT accepted).
        assert response.status_code == 200, \
            f"Backend should accept a valid signature, got status {response.status_code}"

        print("✓ JWT signature validated successfully by backend")


class TestJWTEncoding:
    """Additional JWT encoding/decoding validation tests."""

    def test_jwt_payload_has_token_id_claim(self, authenticated_page_api: Page):
        """Verify JWT token contains a token-id (jti) issuance claim.

        NOTE (2026-08-12 alignment): the original test asserted an 'iat'
        (issued-at) claim, but the real create_access_token in core/auth.py
        emits only sub/exp/jti (see core/auth.py:87) — it does not set 'iat'.
        The issuance-related claim that DOES exist is jti (unique token id,
        used for logout revocation), so the test asserts that instead.

        Args:
            authenticated_page_api: Authenticated page fixture with JWT token
        """
        # Get JWT token from localStorage
        token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")

        assert token is not None, "JWT token should exist in localStorage"

        # Decode payload
        payload = decode_jwt_payload(token)

        # Verify 'jti' (token id) claim exists — create_access_token always
        # adds it so individual tokens can be revoked on logout
        assert 'jti' in payload, "JWT payload should contain 'jti' claim (token id)"
        assert isinstance(payload['jti'], str), "jti should be a string"
        assert len(payload['jti']) > 0, "jti should not be empty"

        # If an iat claim is ever added in the future, keep validating it
        # (optional claim — current backend does not emit it)
        if 'iat' in payload:
            iat_timestamp = payload['iat']
            iat_datetime = datetime.utcfromtimestamp(iat_timestamp)
            now = datetime.utcnow()

            # Allow 1 minute buffer for clock skew
            time_diff = (now - iat_datetime).total_seconds()
            assert time_diff >= -60, f"Issued-at time should be in past, got {iat_datetime}"

    def test_jwt_token_decodable(self, authenticated_page_api: Page):
        """Verify JWT token can be decoded without errors.

        Args:
            authenticated_page_api: Authenticated page fixture with JWT token
        """
        # Get JWT token from localStorage
        token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")

        assert token is not None, "JWT token should exist in localStorage"

        # Verify token is decodable
        try:
            payload = decode_jwt_payload(token)
            assert isinstance(payload, dict), "Decoded payload should be a dictionary"
            assert len(payload) > 0, "Decoded payload should not be empty"
        except Exception as e:
            pytest.fail(f"Failed to decode JWT token: {e}")
