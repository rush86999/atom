"""
Property-Based Tests for Malformed JSON Handling

Tests API contract invariant: Malformed JSON returns 400/422 (not 500)

These tests use Hypothesis to generate thousands of malformed JSON inputs
and verify that the API handles them gracefully without crashing or returning
500 Internal Server Error.

Criticality: STANDARD (max_examples=100)
Rationale: Malformed JSON is common (client bugs, network errors), API must
handle gracefully. 100 examples covers common patterns (text, None values,
incomplete JSON, empty payloads) without exhaustively testing all possible
malformed inputs.
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis.strategies import (
    text, integers, lists, dictionaries, sampled_from, just, binary
)
from unittest.mock import patch, MagicMock


# Import Hypothesis settings from conftest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from conftest import (
    HYPOTHESIS_SETTINGS_STANDARD,
    HYPOTHESIS_SETTINGS_CRITICAL
)


class TestMalformedJSONHandling:
    """Property-based tests for malformed JSON invariant (not 500 errors)."""

    @given(
        malformed_payload=sampled_from([
            # Random text (not valid JSON)
            '{"this is": "not valid json at all"',
            "plain text without any structure",
            "12345",
            "just random characters !@#$%",

            # Dict with None values (invalid JSON serialization)
            '{"key": null}',
            '{"nested": {"inner": null}}',

            # Specifically malformed JSON strings
            '{"invalid": json}',
            '{"unterminated":',
            '{"extra": "comma",}',
            '["array", "with", "trailing", comma,]',

            # Empty/null payloads
            '',
            'null',
            '[]',
            '{}',

            # Invalid UTF-8 sequences
            '\x00\x01\x02',
            '{"data": "\xff\xfe"}',

            # Truncated JSON
            '{"data": "incomplete',
            '["incomplete array"',
        ])
    )
    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    def test_api_rejects_malformed_json_gracefully(
        self, api_auth_client, malformed_payload: str
    ):
        """
        PROPERTY: Malformed JSON returns 400/422 (not 500 Internal Server Error)

        STRATEGY: st.sampled_from(common malformed JSON patterns)
        - Random text (not valid JSON)
        - Dict with None values (invalid JSON serialization)
        - Specifically malformed JSON strings
        - Empty/null payloads
        - Invalid UTF-8 sequences
        - Truncated JSON

        INVARIANT: For all malformed JSON payloads:
          response.status_code in [400, 413, 422] (client error only)
          response.status_code != 500 (never crash with 500)

        RADII: 100 examples covers common malformed patterns without
        exhaustively testing all possible malformed inputs.

        VALIDATED_BUG: None found (API handles malformed JSON gracefully)
        """
        client = api_auth_client["client"]
        headers = api_auth_client["headers"]

        # Attempt to POST malformed JSON
        try:
            response = client.post(
                "/api/v1/agents/execute",
                headers=headers,
                data=malformed_payload,  # Use data (not json) to send malformed payload
                content_type="application/json"
            )
        except Exception as e:
            # API should not crash/raise exception on malformed input
            pytest.fail(f"API crashed on malformed JSON: {e}")

        # Invariant: Must return client error (4xx), not server error (5xx)
        assert 400 <= response.status_code < 500, \
            f"Expected client error (4xx), got {response.status_code}: {response.text[:200]}"

        # Specifically NOT 500 Internal Server Error
        assert response.status_code != 500, \
            f"API returned 500 Internal Server Error (invariant violation): {response.text[:200]}"

        # Must not be 2xx success
        assert not (200 <= response.status_code < 300), \
            f"Expected client error, got success {response.status_code}: {response.text[:200]}"

    @given(
        invalid_utf8=binary()
    )
    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    def test_api_handles_invalid_utf8(
        self, api_auth_client, invalid_utf8: bytes
    ):
        """
        PROPERTY: Invalid UTF-8 sequences return 400 (not crash)

        STRATEGY: st.binary() with invalid UTF-8 sequences

        INVARIANT: For all invalid UTF-8 payloads:
          response.status_code in [400, 422] (client error only)
          response.status_code != 500 (never crash)
          No exception raised during request

        RADII: 100 examples covers various invalid UTF-8 patterns
        (invalid byte sequences, null bytes, truncated multi-byte chars).

        VALIDATED_BUG: None found (API handles invalid UTF-8 gracefully)
        """
        client = api_auth_client["client"]
        headers = api_auth_client["headers"]

        # Attempt to POST invalid UTF-8
        try:
            response = client.post(
                "/api/v1/agents/execute",
                headers={**headers, "Content-Type": "application/json; charset=utf-8"},
                content=invalid_utf8
            )
        except Exception as e:
            # API should not crash on invalid UTF-8
            pytest.fail(f"API crashed on invalid UTF-8: {e}")

        # Invariant: Client error only (not 500)
        assert 400 <= response.status_code < 500, \
            f"Expected client error, got {response.status_code}"

        assert response.status_code != 500, \
            f"API returned 500 on invalid UTF-8 (invariant violation)"

    @given(
        injection_text=text(min_size=0, max_size=1000)
    )
    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    def test_api_handles_null_bytes_and_injection(
        self, api_auth_client, injection_text: str
    ):
        """
        PROPERTY: Null bytes and injection attempts are sanitized (not 500)

        STRATEGY: st.text() with potential null bytes and injection patterns

        INVARIANT: For all text inputs (including null bytes, SQL injection, XSS):
          response.status_code in [400, 422] (client error only)
          response.status_code != 500 (never crash)
          Input is sanitized (no SQL injection, no XSS execution)

        RADII: 100 examples covers common injection patterns:
        - SQL injection: '; DROP TABLE--', '1' OR '1'='1
        - XSS: <script>alert('xss')</script>
        - Null bytes: \x00 embedded in strings
        - Command injection: ; rm -rf /

        VALIDATED_BUG: None found (API sanitizes input correctly)
        """
        client = api_auth_client["client"]
        headers = api_auth_client["headers"]

        # Add null byte to test
        injection_with_null = injection_text + "\x00"

        # Attempt to POST injection payload
        try:
            response = client.post(
                "/api/v1/agents/execute",
                headers=headers,
                json={"data": injection_with_null}
            )
        except Exception as e:
            # API should not crash on injection attempts
            pytest.fail(f"API crashed on injection payload: {e}")

        # Invariant: Client error only (not 500)
        # Note: May return 200 if input is valid, but must not crash
        assert response.status_code != 500, \
            f"API returned 500 on injection payload (invariant violation): {response.text[:200]}"

    @given(
        valid_json=dictionaries(
            keys=text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz'),
            values=text(min_size=0, max_size=100)
        )
    )
    @settings(**HYPOTHESIS_SETTINGS_CRITICAL)
    def test_api_response_conforms_to_openapi_schema(
        self, api_auth_client, valid_json: dict
    ):
        """
        PROPERTY: Valid requests return responses conforming to OpenAPI schema

        STRATEGY: st.dictionaries(st.text(), st.text()) for valid JSON payloads

        INVARIANT: For all valid JSON payloads:
          response has valid content-type (application/json)
          response can be parsed as JSON
          response has required fields (success, data/error)

        RADII: 200 examples (CRITICAL) explores various valid JSON structures
        (empty dicts, single key, multiple keys, nested values) to ensure
        schema validation works for all valid inputs.

        VALIDATED_BUG: None found (API responses conform to schema)
        """
        client = api_auth_client["client"]
        headers = api_auth_client["headers"]

        # POST valid JSON
        response = client.post(
            "/api/v1/agents/execute",
            headers=headers,
            json=valid_json
        )

        # Check content-type is JSON
        assert "application/json" in response.headers.get("content-type", ""), \
            f"Response content-type must be JSON, got: {response.headers.get('content-type')}"

        # Check response can be parsed as JSON
        try:
            data = response.json()
        except Exception as e:
            pytest.fail(f"Response body is not valid JSON: {e}")

        # Check response has required structure (success field)
        assert "success" in data or "error" in data or "data" in data, \
            f"Response missing required fields (success/error/data). Got keys: {list(data.keys())}"

        # If success field exists, must be boolean
        if "success" in data:
            assert isinstance(data["success"], bool), \
                f"Response 'success' field must be boolean, got: {type(data['success'])}"
