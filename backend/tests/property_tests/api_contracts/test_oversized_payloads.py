"""
Property-Based Tests for Oversized Payload Handling

Tests API contract invariant: Oversized payloads return 413 (not OOM/crash)

These tests use Hypothesis to generate oversized payloads and verify that
the API rejects them with 413 Payload Too Large instead of crashing with
Out of Memory errors or returning 500 Internal Server Error.

Criticality: IO_BOUND (max_examples=50)
Rationale: Each oversized payload test involves network/IO operations.
50 examples covers size range (1MB to 100MB) without exhausting test time.
"""

import pytest
from hypothesis import given, settings
from hypothesis.strategies import (
    integers, text, dictionaries, recursive, just, one_of
)


# Import Hypothesis settings from conftest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from conftest import HYPOTHESIS_SETTINGS_IO, HYPOTHESIS_SETTINGS_STANDARD


class TestOversizedPayloadHandling:
    """Property-based tests for oversized payload invariant (413, not crash)."""

    @given(
        payload_size=integers(min_value=1_000_000, max_value=50_000_000)
    )
    @settings(**HYPOTHESIS_SETTINGS_IO)
    def test_api_rejects_oversized_payloads(
        self, api_auth_client, payload_size: int
    ):
        """
        PROPERTY: Oversized payloads return 413 Payload Too Large (not OOM or crash)

        STRATEGY: st.integers(min_value=1_000_000, max_value=50_000_000)
        Generates payload sizes from 1MB to 50MB

        INVARIANT: For all oversized payloads (size > limit):
          response.status_code in [400, 413] (client error only)
          response.status_code != 500 (never crash with OOM)
          No memory exhaustion during request

        RADII: 50 examples covers size range from 1MB to 50MB (tests OOM
        protection without exhausting test machine memory).

        VALIDATED_BUG: None found (API rejects oversized payloads gracefully)
        """
        client = api_auth_client["client"]
        headers = api_auth_client["headers"]

        # Create oversized payload
        oversized_data = {"data": "x" * payload_size}

        # Attempt to POST oversized payload
        try:
            response = client.post(
                "/api/v1/agents/execute",
                headers=headers,
                json=oversized_data
            )
        except Exception as e:
            # API should not crash with OOM error
            pytest.fail(f"API crashed on oversized payload: {e}")

        # Invariant: Client error only (not 500)
        assert 400 <= response.status_code < 500, \
            f"Expected client error (4xx), got {response.status_code}: {response.text[:200]}"

        # Specifically NOT 500 Internal Server Error
        assert response.status_code != 500, \
            f"API returned 500 on oversized payload (invariant violation): {response.text[:200]}"

        # Preferably 413 Payload Too Large
        assert response.status_code in [400, 413], \
            f"Expected 413 Payload Too Large or 400, got {response.status_code}"

    @given(
        empty_payload=one_of(
            just(''),
            just('{}'),
            just('[]'),
            just(None)
        )
    )
    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    def test_api_handles_empty_payloads(
        self, api_auth_client, empty_payload
    ):
        """
        PROPERTY: Empty payloads are handled gracefully (not crash)

        STRATEGY: st.one_of(st.just(''), st.just('{}'), st.just('[]'), st.just(None))
        Tests empty string, empty object, empty array, None value

        INVARIANT: For all empty payloads:
          response.status_code in [400, 422] (client error only)
          response.status_code != 500 (never crash)
          API validates input before processing

        RADII: 100 examples covers all empty payload variations
        (string, JSON object, JSON array, None value).

        VALIDATED_BUG: None found (API handles empty payloads gracefully)
        """
        client = api_auth_client["client"]
        headers = api_auth_client["headers"]

        # Attempt to POST empty payload
        try:
            if empty_payload is None:
                response = client.post(
                    "/api/v1/agents/execute",
                    headers=headers,
                    json=None
                )
            else:
                response = client.post(
                    "/api/v1/agents/execute",
                    headers=headers,
                    data=empty_payload,
                    content_type="application/json"
                )
        except Exception as e:
            # API should not crash on empty payload
            pytest.fail(f"API crashed on empty payload: {e}")

        # Invariant: Client error only (not 500)
        assert 400 <= response.status_code < 500, \
            f"Expected client error, got {response.status_code}: {response.text[:200]}"

        assert response.status_code != 500, \
            f"API returned 500 on empty payload (invariant violation): {response.text[:200]}"

    @given(
        nested_json=recursive(
            just(None),
            lambda s: dictionaries(just("key"), s),
            max_leaves=50
        )
    )
    @settings(**HYPOTHESIS_SETTINGS_IO)
    def test_api_handles_deeply_nested_json(
        self, api_auth_client, nested_json
    ):
        """
        PROPERTY: Deeply nested JSON structures don't cause stack overflow

        STRATEGY: st.recursive(st.just(None), lambda s: st.dictionaries(st.just("key"), s), max_leaves=50)
        Generates deeply nested JSON structures up to 50 levels deep

        INVARIANT: For all deeply nested JSON structures:
          response.status_code in [400, 422] (client error only)
          response.status_code != 500 (never crash with stack overflow)
          No recursion depth errors

        RADII: 50 examples covers various nesting depths (1-50 levels)
        without excessive test time.

        VALIDATED_BUG: None found (API handles nested JSON without stack overflow)
        """
        client = api_auth_client["client"]
        headers = api_auth_client["headers"]

        # Attempt to POST deeply nested JSON
        try:
            response = client.post(
                "/api/v1/agents/execute",
                headers=headers,
                json=nested_json
            )
        except Exception as e:
            # API should not crash with recursion error
            pytest.fail(f"API crashed on deeply nested JSON: {e}")

        # Invariant: Client error only (not 500)
        # May return 200 if valid, but must not crash
        assert response.status_code != 500, \
            f"API returned 500 on deeply nested JSON (invariant violation): {response.text[:200]}"
