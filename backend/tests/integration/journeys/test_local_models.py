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


MODEL_ID = "whisper-local:base"


def _register_audio_provider(client, headers, name="Audio Ollama"):
    resp = client.post("/api/local-models", json={
        "name": name,
        "provider_type": "ollama",
        "base_url": "http://localhost:11434/v1",
    }, headers=headers)
    assert resp.status_code == 200, f"Register provider failed: {resp.text}"
    return resp.json()["id"]


def _set_capabilities(client, headers, provider_id, payload):
    return client.post(
        f"/api/local-models/{provider_id}/capabilities",
        json={"model_id": MODEL_ID, **payload},
        headers=headers,
    )


def _get_capability(client, headers, provider_id):
    resp = client.get(f"/api/local-models/{provider_id}/capabilities", headers=headers)
    assert resp.status_code == 200, f"Get capabilities failed: {resp.text}"
    matches = [c for c in resp.json() if c["model_id"] == MODEL_ID]
    assert matches, f"Model {MODEL_ID} not in capabilities: {resp.text}"
    return matches[0]


class TestLocalModelAudioSettings:
    """Per-model transcription opt-in and per-second audio rate."""

    def test_defaults_disabled_with_unset_rate(self, registered_user):
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}
        provider_id = _register_audio_provider(client, headers)

        resp = _set_capabilities(client, headers, provider_id, {})
        assert resp.status_code == 200, resp.text

        cap = _get_capability(client, headers, provider_id)
        assert cap["supports_transcription"] is False
        assert cap["audio_input_cost_per_second_usd"] is None

    def test_enabling_transcription_requires_explicit_rate(self, registered_user):
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}
        provider_id = _register_audio_provider(client, headers)

        resp = _set_capabilities(client, headers, provider_id, {
            "supports_transcription": True,
        })
        assert resp.status_code == 400, resp.text
        assert "audio_input_cost_per_second_usd" in resp.json()["detail"]

        # The rejected write must not create a half-configured row.
        resp = client.get(
            f"/api/local-models/{provider_id}/capabilities", headers=headers
        )
        assert resp.status_code == 200
        assert not any(c["model_id"] == MODEL_ID for c in resp.json())

    def test_zero_rate_is_explicit_and_distinct_from_unset(self, registered_user):
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}
        provider_id = _register_audio_provider(client, headers)

        resp = _set_capabilities(client, headers, provider_id, {
            "supports_transcription": True,
            "audio_input_cost_per_second_usd": 0,
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["audio_input_cost_per_second_usd"] == 0
        assert resp.json()["supports_transcription"] is True

        cap = _get_capability(client, headers, provider_id)
        assert cap["supports_transcription"] is True
        assert cap["audio_input_cost_per_second_usd"] is not None
        assert cap["audio_input_cost_per_second_usd"] == 0.0

    def test_old_client_edit_preserves_only_audio_fields(self, registered_user):
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}
        provider_id = _register_audio_provider(client, headers)

        resp = _set_capabilities(client, headers, provider_id, {
            "supports_tools": True,
            "supports_vision": True,
            "supports_reasoning": True,
            "supports_transcription": True,
            "audio_input_cost_per_second_usd": 0.00025,
            "quality_score": 0.4,
            "speed_score": 0.3,
            "context_window": 8192,
        })
        assert resp.status_code == 200, resp.text

        # A legacy client sends only the fields it knows about.
        resp = _set_capabilities(client, headers, provider_id, {
            "supports_tools": False,
            "quality_score": 0.9,
        })
        assert resp.status_code == 200, resp.text

        cap = _get_capability(client, headers, provider_id)
        # Original non-audio fields keep their replacement semantics.
        assert cap["supports_tools"] is False  # explicit change applied
        assert cap["quality_score"] == 0.9
        assert cap["supports_vision"] is False  # omitted -> request default
        assert cap["supports_reasoning"] is False
        assert cap["speed_score"] == 0.5
        assert cap["context_window"] == 4096
        # Only the newer audio fields are omission-preserving.
        assert cap["supports_transcription"] is True
        assert cap["audio_input_cost_per_second_usd"] == 0.00025

    def test_capability_and_rate_can_be_turned_off_deliberately(self, registered_user):
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}
        provider_id = _register_audio_provider(client, headers)

        resp = _set_capabilities(client, headers, provider_id, {
            "supports_transcription": True,
            "audio_input_cost_per_second_usd": 0.0001,
        })
        assert resp.status_code == 200, resp.text

        # Clearing the rate while transcription is still enabled is refused.
        resp = _set_capabilities(client, headers, provider_id, {
            "audio_input_cost_per_second_usd": None,
        })
        assert resp.status_code == 400, resp.text

        # Disabling and clearing in one edit is allowed.
        resp = _set_capabilities(client, headers, provider_id, {
            "supports_transcription": False,
            "audio_input_cost_per_second_usd": None,
        })
        assert resp.status_code == 200, resp.text

        cap = _get_capability(client, headers, provider_id)
        assert cap["supports_transcription"] is False
        assert cap["audio_input_cost_per_second_usd"] is None

    def test_invalid_audio_rates_are_rejected(self, registered_user):
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}
        provider_id = _register_audio_provider(client, headers)

        negative = _set_capabilities(client, headers, provider_id, {
            "audio_input_cost_per_second_usd": -0.1,
        })
        assert negative.status_code == 422, negative.text

        non_numeric = _set_capabilities(client, headers, provider_id, {
            "audio_input_cost_per_second_usd": "not-a-number",
        })
        assert non_numeric.status_code == 422, non_numeric.text

        # Rejected writes must not persist anything.
        resp = client.get(
            f"/api/local-models/{provider_id}/capabilities", headers=headers
        )
        assert resp.status_code == 200
        assert not any(c["model_id"] == MODEL_ID for c in resp.json())

    def test_capabilities_are_scoped_to_owned_providers(self, registered_user):
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}

        get_resp = client.get("/api/local-models/not-a-provider/capabilities",
                              headers=headers)
        assert get_resp.status_code == 404, get_resp.text

        post_resp = _set_capabilities(client, headers, "not-a-provider", {})
        assert post_resp.status_code == 404, post_resp.text
