"""
Journey 5: Local model management — register, discover, set capabilities, test.

Tests the local model provider lifecycle end-to-end.
"""

import pytest


class TestLocalModelProviders:

    def test_register_and_list_provider(self, registered_user):
        """Register a local model provider and verify it appears in the list."""
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}

        # Register a provider.
        resp = client.post("/api/local-models", json={
            "name": "Test Ollama",
            "provider_type": "ollama",
            "base_url": "http://localhost:11434/v1",
        }, headers=headers)
        assert resp.status_code == 200, f"Register provider failed: {resp.text}"
        provider_id = resp.json().get("id")
        assert provider_id, "No provider ID returned"

        # List providers — should include the new one.
        resp = client.get("/api/local-models", headers=headers)
        assert resp.status_code == 200, f"List providers failed: {resp.text}"
        providers = resp.json()
        assert any(p["id"] == provider_id for p in providers), \
            f"Provider {provider_id} not in list: {providers}"

    def test_set_capabilities(self, registered_user):
        """Set capabilities for a model under a provider."""
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}

        # Register a provider first.
        resp = client.post("/api/local-models", json={
            "name": "Test LM Studio",
            "provider_type": "lm_studio",
            "base_url": "http://localhost:1234/v1",
        }, headers=headers)
        provider_id = resp.json()["id"]

        # Set capabilities for a model.
        resp = client.post(f"/api/local-models/{provider_id}/capabilities", json={
            "model_id": "test-model:7b",
            "supports_tools": True,
            "supports_vision": False,
            "supports_reasoning": True,
            "quality_score": 0.8,
            "speed_score": 0.6,
            "context_window": 8192,
        }, headers=headers)
        assert resp.status_code == 200, f"Set capabilities failed: {resp.text}"

        # Verify they're stored.
        resp = client.get(f"/api/local-models/{provider_id}/capabilities",
                          headers=headers)
        assert resp.status_code == 200, f"Get capabilities failed: {resp.text}"
        caps = resp.json()
        assert any(c["model_id"] == "test-model:7b" for c in caps), \
            f"Model not in capabilities: {caps}"

    def test_delete_provider(self, registered_user):
        """Delete a provider and verify it's gone."""
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}

        # Register.
        resp = client.post("/api/local-models", json={
            "name": "ToDelete",
            "provider_type": "custom",
            "base_url": "http://localhost:9999/v1",
        }, headers=headers)
        provider_id = resp.json()["id"]

        # Delete.
        resp = client.delete(f"/api/local-models/{provider_id}", headers=headers)
        assert resp.status_code == 200, f"Delete failed: {resp.text}"

        # Verify it's gone from the list.
        resp = client.get("/api/local-models", headers=headers)
        providers = resp.json()
        assert not any(p["id"] == provider_id for p in providers), \
            "Provider still in list after deletion"

    def test_test_connection_unreachable(self, registered_user):
        """Test connection to an unreachable provider returns reachable=false."""
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}

        # Register a provider at a port nothing is listening on.
        resp = client.post("/api/local-models", json={
            "name": "Unreachable",
            "provider_type": "custom",
            "base_url": "http://localhost:59999/v1",
        }, headers=headers)
        provider_id = resp.json()["id"]

        # Test connection.
        resp = client.post(f"/api/local-models/{provider_id}/test", headers=headers)
        assert resp.status_code == 200, f"Test connection failed: {resp.text}"
        data = resp.json()
        assert data.get("reachable") is False, \
            f"Expected unreachable, got: {data}"
