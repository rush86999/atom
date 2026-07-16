"""
Journey 4: BYOK endpoint path discovery.

Tests that the BYOK API key endpoint is reachable at the documented path
(/api/ai/keys), not a double-prefixed path (/api/v1/api/ai/keys).
"""

import pytest


class TestByokEndpointPath:

    def test_byok_keys_endpoint_reachable(self, registered_user):
        """POST /api/ai/keys should be reachable (not 404 due to double prefix)."""
        client, email, password, token = registered_user

        resp = client.post("/api/ai/keys", json={
            "provider": "openai",
            "api_key": "sk-test-fake-key",
        }, headers={"Authorization": f"Bearer {token}"})

        # We don't care if the key is valid — we just care that the endpoint
        # is reachable (not 404). 400/422/500 are acceptable (they mean the
        # route exists but the input was rejected).
        assert resp.status_code != 404, \
            f"POST /api/ai/keys returned 404 — the BYOK router is likely " \
            f"double-prefixed (mounted at /api/v1 with routes already " \
            f"including /api/ai). Actual path is /api/v1/api/ai/keys."

    def test_byok_providers_list_reachable(self, registered_user):
        """GET /api/ai/providers should be reachable."""
        client, email, password, token = registered_user

        resp = client.get("/api/ai/providers",
                          headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code != 404, \
            f"GET /api/ai/providers returned 404 — BYOK router prefix issue."
